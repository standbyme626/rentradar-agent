"""Community reputation evidence (P1/W6).

The reputation score is only as good as its evidence.  This module stores
community-level mentions with source, URL, excerpt, severity and confidence;
aggregation is time-decayed, source-agnostic and never treats an "uncertain"
entity match as a scored fact.  Communities without evidence keep a neutral
score and explicitly say "数据不足" instead of pretending 0.5 is a finding.
"""

import json
import math
import re
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Community, Listing, ListingStatus, ReputationMention
from app.services import provider_runtime

ISSUE_TYPES = {
    "noise": "噪音/施工",
    "security": "治安/门禁",
    "hygiene": "卫生/异味",
    "property": "物业/维修",
    "management": "管理/收费",
    "parking": "停车",
    "delivery": "外卖/快递",
    "other": "其他",
}
SOURCES = {"douban", "xiaohongshu", "12345", "dianping", "web", "manual"}
SEVERITIES = {"low": 0.35, "medium": 0.65, "high": 1.0}
MATCH_STATUSES = {"verified", "uncertain", "rejected"}
HALF_LIFE_DAYS = 180.0
EXPIRE_DAYS = 365
MIN_SCORED_MENTIONS = 1


def _aware(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def decay_weight(mention: ReputationMention, now: datetime | None = None) -> float:
    now = now or datetime.now(UTC)
    published = _aware(mention.published_at or mention.created_at)
    age_days = max(0.0, (now - published).total_seconds() / 86400)
    return math.pow(0.5, age_days / HALF_LIFE_DAYS)


def summarize_mentions(
    mentions: list[ReputationMention], *, now: datetime | None = None
) -> dict:
    """Aggregate verified mentions into a 0-1 reputation score."""
    now = now or datetime.now(UTC)
    verified = [
        item
        for item in mentions
        if item.match_status == "verified"
        and (item.expires_at is None or _aware(item.expires_at) > now)
    ]
    uncertain = sum(1 for item in mentions if item.match_status == "uncertain")
    if len(verified) < MIN_SCORED_MENTIONS:
        return {
            "count": 0,
            "uncertain": uncertain,
            "score": 0.5,
            "status": "insufficient",
            "label": "口碑数据不足（中性分）",
            "risk": "unknown",
            "sources": [],
            "issue_types": {},
            "top_issue": None,
            "latest_at": None,
        }
    weighted_confidence = 0.0
    weighted_risk = 0.0
    sources: set[str] = set()
    issues: dict[str, int] = {}
    latest: datetime | None = None
    for item in verified:
        weight = decay_weight(item, now)
        confidence = float(item.confidence or 0.5)
        severity = SEVERITIES.get(item.severity, 0.35)
        weighted_confidence += weight * confidence
        weighted_risk += weight * confidence * severity
        sources.add(item.source)
        if item.issue_type:
            issues[item.issue_type] = issues.get(item.issue_type, 0) + 1
        published = _aware(item.published_at or item.created_at)
        if latest is None or published > latest:
            latest = published
    risk_ratio = weighted_risk / (weighted_confidence + 2.0)
    score = max(0.05, min(1.0, 1.0 - 0.9 * risk_ratio))
    if score >= 0.8:
        status, label, risk = "low", "口碑风险低", "low"
    elif score >= 0.55:
        status, label, risk = "watch", "口碑有少量负面", "medium"
    else:
        status, label, risk = "high", "口碑风险高", "high"
    top_issue = max(issues, key=issues.get) if issues else None
    return {
        "count": len(verified),
        "uncertain": uncertain,
        "score": round(score, 3),
        "status": status,
        "label": label,
        "risk": risk,
        "sources": sorted(sources),
        "issue_types": issues,
        "top_issue": top_issue,
        "top_issue_label": ISSUE_TYPES.get(top_issue, top_issue) if top_issue else None,
        "latest_at": latest,
    }


async def community_summary(db: AsyncSession, community_id: int | None) -> dict | None:
    if community_id is None:
        return None
    cache = db.info.setdefault("reputation_summary", {})
    if community_id in cache:
        return cache[community_id]
    mentions = list(
        (
            await db.execute(
                select(ReputationMention).where(
                    ReputationMention.community_id == community_id,
                    ReputationMention.match_status != "rejected",
                )
            )
        )
        .scalars()
        .all()
    )
    summary = summarize_mentions(mentions)
    cache[community_id] = summary
    return summary


async def bulk_summaries(db: AsyncSession, community_ids: list[int]) -> dict[int, dict]:
    ids = [int(item) for item in community_ids if item is not None]
    if not ids:
        return {}
    rows = (
        (
            await db.execute(
                select(ReputationMention).where(
                    ReputationMention.community_id.in_(ids),
                    ReputationMention.match_status != "rejected",
                )
            )
        )
        .scalars()
        .all()
    )
    grouped: dict[int, list[ReputationMention]] = {item: [] for item in ids}
    for mention in rows:
        grouped.setdefault(mention.community_id, []).append(mention)
    return {key: summarize_mentions(value) for key, value in grouped.items()}


async def mentions_for_community(
    db: AsyncSession, community_id: int, *, limit: int = 8
) -> list[dict]:
    rows = (
        (
            await db.execute(
                select(ReputationMention)
                .where(
                    ReputationMention.community_id == community_id,
                    ReputationMention.match_status != "rejected",
                )
                .order_by(ReputationMention.created_at.desc())
                .limit(max(1, min(limit, 50)))
            )
        )
        .scalars()
        .all()
    )
    return [mention_dict(item) for item in rows]


def mention_dict(item: ReputationMention) -> dict:
    return {
        "id": item.id,
        "source": item.source,
        "url": item.url,
        "title": item.title,
        "excerpt": item.excerpt,
        "issue_type": item.issue_type,
        "issue_label": ISSUE_TYPES.get(item.issue_type or "", item.issue_type),
        "severity": item.severity,
        "confidence": float(item.confidence or 0),
        "match_status": item.match_status,
        "published_at": item.published_at,
        "created_at": item.created_at,
        "expires_at": item.expires_at,
    }


def _clean_text(value: str | None, limit: int = 500) -> str:
    return " ".join(str(value or "").split())[:limit]


async def create_mention(db: AsyncSession, community_id: int, payload: dict) -> dict:
    community = await db.get(Community, int(community_id))
    if community is None:
        raise ValueError("小区不存在")
    source = str(payload.get("source") or "manual").strip()
    if source not in SOURCES:
        raise ValueError(f"不支持的来源：{source}")
    severity = str(payload.get("severity") or "low")
    if severity not in SEVERITIES:
        raise ValueError(f"不支持的严重度：{severity}")
    match_status = str(payload.get("match_status") or "verified")
    if match_status not in MATCH_STATUSES:
        raise ValueError(f"不支持的匹配状态：{match_status}")
    issue_type = payload.get("issue_type")
    if issue_type and issue_type not in ISSUE_TYPES:
        raise ValueError(f"不支持的问题类型：{issue_type}")
    excerpt = _clean_text(payload.get("excerpt"))
    if len(excerpt) < 4:
        raise ValueError("证据原文太短")
    confidence = float(payload.get("confidence") or 0.5)
    confidence = max(0.05, min(1.0, confidence))
    url = str(payload.get("url") or "").strip() or None
    if url is not None and not re.match(r"^https?://", url):
        raise ValueError("证据链接必须是 http(s) URL")
    if url:
        existing = await db.scalar(
            select(func.count())
            .select_from(ReputationMention)
            .where(
                ReputationMention.community_id == community.id,
                ReputationMention.url == url[:512],
            )
        )
        if existing:
            raise ValueError("该链接已录入")
    published_at = payload.get("published_at")
    if isinstance(published_at, str) and published_at:
        try:
            published_at = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        except ValueError:
            published_at = None
    elif not isinstance(published_at, datetime):
        published_at = None
    mention = ReputationMention(
        community_id=community.id,
        source=source,
        url=url[:512] if url else None,
        title=_clean_text(payload.get("title"), 255) or None,
        excerpt=excerpt,
        issue_type=issue_type,
        severity=severity,
        confidence=confidence,
        match_status=match_status,
        published_at=published_at,
        evidence={"entered_by": "admin", "raw": _clean_text(payload.get("raw"), 2000)},
        expires_at=datetime.now(UTC) + timedelta(days=EXPIRE_DAYS),
    )
    db.add(mention)
    await db.commit()
    await db.refresh(mention)
    db.info.pop("reputation_summary", None)
    return mention_dict(mention)


async def update_match_status(
    db: AsyncSession, mention_id: int, match_status: str
) -> dict | None:
    if match_status not in MATCH_STATUSES:
        raise ValueError(f"不支持的匹配状态：{match_status}")
    mention = await db.get(ReputationMention, int(mention_id))
    if mention is None:
        return None
    mention.match_status = match_status
    await db.commit()
    await db.refresh(mention)
    db.info.pop("reputation_summary", None)
    return mention_dict(mention)


async def delete_mention(db: AsyncSession, mention_id: int) -> bool:
    mention = await db.get(ReputationMention, int(mention_id))
    if mention is None:
        return False
    await db.delete(mention)
    await db.commit()
    db.info.pop("reputation_summary", None)
    return True


_EXTRACT_SYSTEM = (
    "你是小区口碑证据抽取器。输入一段网页/帖子原文和小区名，只输出 JSON："
    '{"mentions":[{"excerpt":"原文中支持结论的短句","issue_type":"noise|security|'
    'hygiene|property|management|parking|delivery|other","severity":"low|medium|high",'
    '"confidence":0到1}]}。只抽取明确提到该小区、且能引用原文的证据；'
    "没有证据返回空数组；不要推断，不要输出 markdown。"
)


async def extract_mentions(db: AsyncSession, text: str, community_name: str) -> list[dict]:
    """Use the configured chat provider to turn raw text into evidence drafts."""
    snippet = _clean_text(text, 6000)
    if not snippet:
        return []
    try:
        result = await provider_runtime.invoke_chat(
            db,
            [
                {"role": "system", "content": _EXTRACT_SYSTEM},
                {"role": "user", "content": f"小区：{community_name}\n原文：{snippet}"},
            ],
            max_tokens=900,
            temperature=0.0,
        )
    except Exception:
        return []
    content = str(result.get("content") or "")
    data = _extract_json(content)
    if not isinstance(data, dict):
        return []
    drafts = []
    for item in data.get("mentions") or []:
        if not isinstance(item, dict):
            continue
        excerpt = _clean_text(item.get("excerpt"), 500)
        if len(excerpt) < 4:
            continue
        issue_type = str(item.get("issue_type") or "other")
        if issue_type not in ISSUE_TYPES:
            issue_type = "other"
        severity = str(item.get("severity") or "low")
        if severity not in SEVERITIES:
            severity = "low"
        try:
            confidence = float(item.get("confidence") or 0.5)
        except (TypeError, ValueError):
            confidence = 0.5
        drafts.append(
            {
                "excerpt": excerpt,
                "issue_type": issue_type,
                "severity": severity,
                "confidence": round(max(0.05, min(1.0, confidence)), 2),
            }
        )
    return drafts[:10]


def _extract_json(text: str) -> dict | None:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        value = json.loads(cleaned)
        return value if isinstance(value, dict) else None
    except ValueError:
        match = re.search(r"\{.*\}", cleaned, re.S)
        if not match:
            return None
        try:
            value = json.loads(match.group(0))
            return value if isinstance(value, dict) else None
        except ValueError:
            return None


async def overview(db: AsyncSession, limit: int = 12) -> dict:
    now = datetime.now(UTC)
    communities = (
        (await db.execute(select(Community).order_by(Community.id))).scalars().all()
    )
    mention_rows = (
        (
            await db.execute(
                select(ReputationMention).where(
                    ReputationMention.match_status != "rejected"
                )
            )
        )
        .scalars()
        .all()
    )
    grouped: dict[int, list[ReputationMention]] = {}
    for mention in mention_rows:
        grouped.setdefault(mention.community_id, []).append(mention)
    summaries = {
        community.id: summarize_mentions(grouped.get(community.id, []), now=now)
        for community in communities
    }
    with_evidence = [item for item in communities if summaries[item.id]["count"]]
    risky = sorted(
        (
            {
                "community_id": community.id,
                "name": community.name,
                "district": community.district,
                **summaries[community.id],
            }
            for community in with_evidence
        ),
        key=lambda item: item["score"],
    )[:limit]
    listing_counts = dict(
        (
            await db.execute(
                select(Listing.community_id, func.count())
                .where(Listing.status == ListingStatus.active)
                .group_by(Listing.community_id)
            )
        ).all()
    )
    missing = sorted(
        (
            {
                "community_id": community.id,
                "name": community.name,
                "district": community.district,
                "listings": int(listing_counts.get(community.id) or 0),
            }
            for community in communities
            if not summaries[community.id]["count"]
        ),
        key=lambda item: item["listings"],
        reverse=True,
    )[:limit]
    recent = sorted(
        mention_rows,
        key=lambda item: _aware(item.created_at),
        reverse=True,
    )[:limit]
    return {
        "stats": {
            "communities": len(communities),
            "with_evidence": len(with_evidence),
            "without_evidence": len(communities) - len(with_evidence),
            "verified": sum(
                1 for item in mention_rows if item.match_status == "verified"
            ),
            "uncertain": sum(
                1 for item in mention_rows if item.match_status == "uncertain"
            ),
            "high_risk": sum(1 for item in summaries.values() if item["risk"] == "high"),
            "sources": len({item.source for item in mention_rows}),
        },
        "risky": risky,
        "missing": missing,
        "recent": [mention_dict(item) for item in recent],
        "issue_types": ISSUE_TYPES,
        "sources": sorted(SOURCES),
        "half_life_days": HALF_LIFE_DAYS,
    }


async def find_communities(db: AsyncSession, q: str, limit: int = 10) -> list[dict]:
    stmt = select(Community).order_by(Community.id)
    if q.strip():
        stmt = stmt.where(Community.name.ilike(f"%{q.strip()}%"))
    rows = (await db.execute(stmt.limit(max(1, min(limit, 30))))).scalars().all()
    return [
        {"id": item.id, "name": item.name, "district": item.district}
        for item in rows
    ]


async def listing_reputation(
    db: AsyncSession, community_id: int | None, *, limit: int = 6
) -> dict | None:
    if community_id is None:
        return None
    summary = await community_summary(db, community_id)
    mentions = await mentions_for_community(db, community_id, limit=limit)
    return {**(summary or {}), "mentions": mentions}


def summarize_for_score(summary: dict | None) -> tuple[float, str, str]:
    """Return (0-1 score, human reason, status) for the score service."""
    if not summary or summary.get("status") == "insufficient":
        return 0.5, "口碑数据不足（中性分）", "insufficient"
    score = float(summary.get("score") or 0.5)
    label = str(summary.get("label") or "口碑")
    count = int(summary.get("count") or 0)
    return score, f"{label} · {count} 条证据（{','.join(summary.get('sources') or [])}）", str(
        summary.get("status")
    )
