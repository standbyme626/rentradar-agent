import re
import time
import uuid
from collections import Counter
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models import (
    AgentMonitor,
    AgentSession,
    City,
    CommuteSample,
    Listing,
    ListingStatus,
    PoiCache,
    Source,
)
from app.services import listing_service, llm_service
from app.services.settings_service import (
    destination_key,
    get_admin_settings,
    get_commute_destination,
)

log = get_logger("agent")

DISTRICTS = {
    "福田区": "福田区",
    "罗湖区": "罗湖区",
    "南山区": "南山区",
    "宝安区": "宝安区",
    "龙华区": "龙华区",
    "龙岗区": "龙岗区",
    "盐田区": "盐田区",
    "光明区": "光明区",
    "坪山区": "坪山区",
    "大鹏新区": "大鹏新区",
    "福田": "福田区",
    "罗湖": "罗湖区",
    "南山": "南山区",
    "宝安": "宝安区",
    "龙华": "龙华区",
    "龙岗": "龙岗区",
    "盐田": "盐田区",
    "光明": "光明区",
    "坪山": "坪山区",
    "大鹏": "大鹏新区",
}
LAYOUTS = (
    (r"(两居|二居|2居|两室|2室)", "2室"),
    (r"(一居|1居|一室|1室)", "1室"),
    (r"(三居|3居|三室|3室)", "3室"),
    (r"(单间|开间)", "1室"),
)


def _extract_budget(text: str) -> int | None:
    patterns = (
        r"预算\s*(?:压到|降到|控制在|改到)?\s*(\d{3,5})",
        r"(\d{3,5})\s*(?:元|块)(?:/月|每月)?",
        r"(?:≤|<=|不超过|以内|以下)\s*(\d{3,5})",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            value = int(match.group(1))
            if 500 <= value <= 50000:
                return value
    for value in re.findall(r"(?<!\d)(\d{4})(?!\d)", text):
        number = int(value)
        if 1000 <= number <= 20000:
            return number
    return None


def _extract_commute(text: str) -> int | None:
    match = re.search(r"(\d{1,3})\s*(?:分钟|分|min)", text)
    if not match:
        return None
    value = int(match.group(1))
    return value if 5 <= value <= 180 else None


def _extract_layout(text: str) -> str | None:
    compact = text.replace(" ", "")
    for pattern, label in LAYOUTS:
        if re.search(pattern, compact):
            return label
    return None


def _extract_district(text: str) -> str | None:
    for key, value in DISTRICTS.items():
        if key in text:
            return value
    return None


def _extract_must(text: str) -> list[str]:
    must = []
    for tag in ("电梯", "近地铁", "精装"):
        if tag in text:
            must.append(tag)
    if "南向" in text or "朝南" in text:
        must.append("南向")
    return must


def parse_conditions(message: str, base: dict | None = None) -> dict:
    base = dict(base or {})
    conditions = {
        "company": base.get("company", "深圳会展中心"),
        "line": "5号线" if "5号线" in message else base.get("line", "5号线"),
        "budget": base.get("budget"),
        "commute": base.get("commute"),
        "layout": base.get("layout"),
        "district": base.get("district"),
        "must": sorted(set(base.get("must") or [])),
    }
    budget = _extract_budget(message)
    commute = _extract_commute(message)
    layout = _extract_layout(message)
    district = _extract_district(message)
    if budget is not None:
        conditions["budget"] = budget
    if commute is not None:
        conditions["commute"] = commute
    if layout is not None:
        conditions["layout"] = layout
    if district is not None:
        conditions["district"] = district
    if "会展中心" in message:
        conditions["company"] = "深圳会展中心"
    conditions["must"] = sorted(set(conditions["must"]) | set(_extract_must(message)))
    conditions["isLong"] = conditions["district"] == "龙岗区" or bool(
        conditions.get("budget") and conditions["budget"] <= 3000
    )
    return conditions


def conditions_summary(conditions: dict) -> str:
    parts = []
    if conditions.get("budget"):
        parts.append(f"预算≤{conditions['budget']}")
    if conditions.get("commute"):
        parts.append(f"通勤≤{conditions['commute']}min")
    if conditions.get("layout"):
        parts.append(str(conditions["layout"]))
    if conditions.get("district"):
        parts.append(str(conditions["district"]))
    if conditions.get("must"):
        parts.append("/".join(str(item) for item in conditions["must"]))
    return " · ".join(parts) or "未限定条件"


def _ui_conditions(conditions: dict) -> dict:
    budget = conditions.get("budget")
    commute = conditions.get("commute")
    layout = conditions.get("layout")
    must = conditions.get("must") or []
    return {
        "company": conditions.get("company") or "深圳会展中心",
        "budget": f"{int(budget)} 元/月以内" if budget else "不限",
        "line": conditions.get("line") or "5号线",
        "commute": f"≤ {int(commute)} 分钟" if commute else "不限",
        "layout": layout or "不限",
        "district": conditions.get("district") or "",
        "must": " / ".join(str(item) for item in must) if must else "无硬条件",
        "isLong": bool(conditions.get("isLong")),
    }


async def _latest_commute(db: AsyncSession) -> tuple[dict[int, int], Counter[int]]:
    destination = await get_commute_destination(db)
    key = destination_key(destination)
    stmt = select(
        CommuteSample.community_id, CommuteSample.duration_s, CommuteSample.fetched_at
    ).order_by(CommuteSample.community_id, CommuteSample.fetched_at.desc())
    if key:
        stmt = stmt.where(CommuteSample.destination_key == key)
    rows = (await db.execute(stmt)).all()
    latest: dict[int, int] = {}
    counts: Counter[int] = Counter()
    for community_id, duration_s, _ in rows:
        counts[community_id] += 1
        latest.setdefault(community_id, duration_s)
    return latest, counts


async def _query_cards(
    db: AsyncSession,
    conditions: dict,
    *,
    limit: int = 4,
    sort_by_commute: bool = False,
) -> tuple[list[dict], dict]:
    total = int(
        await db.scalar(
            select(func.count())
            .select_from(Listing)
            .where(Listing.status == ListingStatus.active, Listing.score.is_not(None))
        )
        or 0
    )
    stmt = (
        select(Listing, Source.code, City.code, PoiCache)
        .join(Source, Listing.source_id == Source.id)
        .join(City, Listing.city_id == City.id)
        .outerjoin(PoiCache, PoiCache.community_id == Listing.community_id)
        .where(Listing.status == ListingStatus.active, Listing.score.is_not(None))
    )
    if conditions.get("budget"):
        stmt = stmt.where(Listing.rent <= int(conditions["budget"]))
    if conditions.get("layout"):
        stmt = stmt.where(Listing.layout.ilike(f"%{conditions['layout']}%"))
    if conditions.get("district"):
        stmt = stmt.where(Listing.district == conditions["district"])
    must = set(conditions.get("must") or [])
    for tag in must - {"南向"}:
        stmt = stmt.where(Listing.tags.contains([tag]))
    if "南向" in must:
        stmt = stmt.where(Listing.orientation.ilike("%南%"))
    stmt = stmt.order_by(Listing.score.desc().nullslast(), Listing.id.desc()).limit(100)
    rows = (await db.execute(stmt)).all()
    latest, samples = await _latest_commute(db)
    max_commute = conditions.get("commute")
    cards = []
    for listing, source_code, city_code, poi in rows:
        duration = latest.get(listing.community_id)
        minutes = round(duration / 60) if duration else None
        if max_commute is not None and (minutes is None or minutes > int(max_commute)):
            continue
        item = listing_service._listing_dict(listing, source_code, city_code)
        item["score_reasons"] = listing.score_reasons or {}
        item["commute_min"] = minutes
        item["samples"] = samples.get(listing.community_id, 0)
        item["dining_count"] = poi.dining_count if poi else None
        item["daily_count"] = poi.daily_count if poi else None
        item["nightlife_count"] = poi.nightlife_count if poi else None
        cards.append(item)
    if sort_by_commute:
        cards.sort(key=lambda item: item["commute_min"] if item["commute_min"] is not None else 999)
    counts = {
        "total": total,
        "filtered": len(rows),
        "final": min(len(cards), limit),
    }
    return cards[:limit], counts


def _plan_steps(conditions: dict, counts: dict) -> list[dict]:
    summary = conditions_summary(conditions)
    return [
        {"id": "parse", "label": "解析需求", "desc": summary, "status": "done", "time": "0ms"},
        {
            "id": "search",
            "label": "本地检索",
            "desc": f"{counts['total']} 套已评分",
            "status": "done",
            "time": "local",
        },
        {
            "id": "filter",
            "label": "硬过滤",
            "desc": f"{counts['filtered']} 套",
            "status": "done",
            "time": "local",
        },
        {
            "id": "commute",
            "label": "算通勤",
            "desc": "最新缓存 · 0 外部调用",
            "status": "done",
            "time": "cache",
        },
        {
            "id": "detail",
            "label": "抓详情",
            "desc": "详情图/AI 未接入",
            "status": "pending",
            "time": "—",
        },
        {
            "id": "answer",
            "label": "推荐",
            "desc": f"{counts['final']} 套",
            "status": "done",
            "time": "local",
        },
    ]


def _answer_for(cards: list[dict], conditions: dict) -> str:
    if not cards:
        return (
            f"没有找到同时满足「{conditions_summary(conditions)}」的房源。"
            "建议放宽预算、通勤或户型，或者去掉电梯/精装等硬条件。"
        )
    lines = []
    for card in cards[:3]:
        commute = card.get("commute_min")
        commute_text = f"通勤 {commute} 分钟" if commute is not None else "通勤样本待补"
        lines.append(
            f"{card.get('community_name') or '房源'} · ¥{card.get('rent')} · "
            f"{commute_text} · {card.get('score')} 分"
        )
    return "；".join(lines) + "。本次只查本地库存，未调用高德；详情图/AI 未接入。"


def _tools_list(conditions: dict, counts: dict) -> list[list[str]]:
    return [
        ["search_listings", conditions_summary(conditions), "local", f"{counts['filtered']} 套"],
        ["commute_cache", "最新通勤样本", "cache", f"{counts['final']} 套有通勤"],
    ]


def _monitor_name(conditions: dict) -> str:
    return f"{conditions.get('line', '5号线')} · {conditions_summary(conditions)}"[:128]


def _session_amap_cap(settings: dict) -> int:
    return max(1, int(settings.get("sessionAmapCap") or 15))


def _merge_llm_conditions(rule: dict, intent: dict | None) -> dict:
    if not intent:
        return rule
    merged = dict(rule)
    for key in ("budget", "commute", "layout", "district", "company"):
        value = intent.get(key)
        if value is not None:
            merged[key] = value
    if intent.get("must"):
        merged["must"] = sorted(set(merged.get("must") or []) | set(intent["must"]))
    merged["isLong"] = merged.get("district") == "龙岗区" or bool(
        merged.get("budget") and merged.get("budget") <= 3000
    )
    return merged


def _session_title(message: str) -> str:
    return " ".join(message.split())[:24] or "找房会话"


async def _save_session(
    db: AsyncSession,
    session: AgentSession,
    *,
    stage: str,
    conditions: dict,
    candidates: str,
    plan: list[dict],
    tools: list[list[str]],
    result: str,
    latency_ms: int,
    llm: dict | None = None,
) -> None:
    session.status = "done"
    session.stage = stage
    session.conditions = conditions
    session.candidates = candidates
    session.tools_count = len(tools)
    session.amap_count = 0
    session.latency_ms = latency_ms
    session.plan = plan
    session.tools_list = tools
    session.result = result
    if llm:
        if llm.get("model"):
            session.model = str(llm["model"])[:128]
        session.prompt_tokens = int(session.prompt_tokens or 0) + int(
            llm.get("prompt_tokens") or 0
        )
        session.completion_tokens = int(session.completion_tokens or 0) + int(
            llm.get("completion_tokens") or 0
        )
        session.cost = float(session.cost or 0) + float(llm.get("cost") or 0)
        session.llm_fallback = bool(llm.get("fallback", True))
    session.updated_at = datetime.now(UTC)
    await db.commit()


async def stream(
    db: AsyncSession, session_id: str | None, message: str, *, user_id: int
) -> AsyncIterator[dict]:
    started = time.monotonic()
    session: AgentSession | None = None
    try:
        if session_id:
            session = await db.get(AgentSession, session_id)
        new_session = session is None
        if new_session:
            rule = parse_conditions(message)
            intent, parse_meta = await llm_service.parse_intent(db, message, {})
            conditions = _merge_llm_conditions(rule, intent)
            llm_meta = parse_meta
            session = AgentSession(
                id=f"S-{uuid.uuid4().hex[:8].upper()}",
                user_id=user_id,
                title=_session_title(message),
                prompt=message,
                conditions={},
                status="running",
            )
            db.add(session)
            await db.commit()
            await db.refresh(session)
        yield {"type": "session", "sessionId": session.id, "title": session.title}

        if new_session:
            cards, counts = await _query_cards(db, conditions)
            plan = _plan_steps(conditions, counts)
            yield {"type": "conditions", "conditions": _ui_conditions(conditions)}
            yield {"type": "plan", "steps": plan}
            yield {
                "type": "budget",
                "amap": 0,
                "cap": _session_amap_cap(await get_admin_settings(db)),
            }
            yield {
                "type": "cards",
                "cards": cards,
                "longgang": bool(conditions.get("isLong")),
            }
            llm_answer, answer_meta = await llm_service.answer(db, cards, conditions)
            llm_meta = llm_service.merge_meta(llm_meta, answer_meta)
            answer = llm_answer or _answer_for(cards, conditions)
            yield {"type": "message", "text": answer}
            latency = int((time.monotonic() - started) * 1000)
            tools = _tools_list(conditions, counts) + llm_meta["calls"]
            await _save_session(
                db,
                session,
                stage="已推荐" if cards else "无匹配",
                conditions=conditions,
                candidates=f"{counts['total']} → {counts['filtered']} → {counts['final']}",
                plan=plan,
                tools=tools,
                result=answer,
                latency_ms=latency,
                llm=llm_meta,
            )
            yield {"type": "done"}
            return

        base = dict(session.conditions or {})
        lower = message.lower()
        if "对比" in message:
            text = "已经切到对比视图。差异主要在通勤、租金和面积；如果两个人住，优先看两居。"
            yield {"type": "tab", "tab": "compare"}
            yield {"type": "message", "text": text}
            latency = int((time.monotonic() - started) * 1000)
            await _save_session(
                db,
                session,
                stage="对比视图",
                conditions=base,
                candidates=session.candidates or "",
                plan=session.plan or [],
                tools=session.tools_list or [],
                result=text,
                latency_ms=latency,
            )
            yield {"type": "done"}
            return
        if "图片" in message or "ai" in lower:
            text = (
                "图片分析尚未接入。计划只对候选详情抓 3–6 张图，"
                "做 pHash 和视觉标签；当前版本先用列表字段。"
            )
            yield {"type": "ai", "text": text}
            yield {
                "type": "message",
                "text": "图片管线在 Phase 4 接入；当前推荐仍基于价格、通勤和标签。",
            }
            latency = int((time.monotonic() - started) * 1000)
            await _save_session(
                db,
                session,
                stage="图片未接入",
                conditions=base,
                candidates=session.candidates or "",
                plan=session.plan or [],
                tools=session.tools_list or [],
                result=text,
                latency_ms=latency,
            )
            yield {"type": "done"}
            return
        if "保存" in message or "监控" in message:
            name = _monitor_name(base)
            await create_monitor(db, name, base, user_id=user_id)
            yield {"type": "toast", "message": f"已保存监控：{name}"}
            yield {"type": "message", "text": "已保存为监控条件。新匹配/降价推送在后续接入。"}
            latency = int((time.monotonic() - started) * 1000)
            await _save_session(
                db,
                session,
                stage="监控已保存",
                conditions=base,
                candidates=session.candidates or "",
                plan=session.plan or [],
                tools=session.tools_list or [],
                result="已保存监控条件。",
                latency_ms=latency,
            )
            yield {"type": "done"}
            return

        rule = parse_conditions(message, base)
        intent, parse_meta = await llm_service.parse_intent(db, message, base)
        conditions = _merge_llm_conditions(rule, intent)
        llm_meta = parse_meta
        sort_by_commute = "通勤" in message or "近" in message
        cards, counts = await _query_cards(
            db, conditions, sort_by_commute=sort_by_commute
        )
        yield {"type": "conditions", "conditions": _ui_conditions(conditions)}
        yield {"type": "budget", "amap": 0, "cap": _session_amap_cap(await get_admin_settings(db))}
        yield {
            "type": "cards",
            "cards": cards,
            "longgang": bool(conditions.get("isLong")),
        }
        llm_answer, answer_meta = await llm_service.answer(db, cards, conditions)
        llm_meta = llm_service.merge_meta(llm_meta, answer_meta)
        answer = llm_answer or _answer_for(cards, conditions)
        yield {"type": "message", "text": answer}
        latency = int((time.monotonic() - started) * 1000)
        await _save_session(
            db,
            session,
            stage="已重排" if sort_by_commute else "已更新",
            conditions=conditions,
            candidates=f"{counts['total']} → {counts['filtered']} → {counts['final']}",
            plan=session.plan or [],
            tools=_tools_list(conditions, counts) + llm_meta["calls"],
            result=answer,
            latency_ms=latency,
            llm=llm_meta,
        )
        yield {"type": "done"}
    except Exception as exc:
        if session is not None:
            session.status = "failed"
            session.stage = "失败"
            session.result = f"{type(exc).__name__}: {exc}"[:500]
            session.updated_at = datetime.now(UTC)
            await db.commit()
        yield {"type": "error", "message": f"{type(exc).__name__}: {exc}"[:200]}
        yield {"type": "done"}


async def list_chat_sessions(
    db: AsyncSession, user_id: int, limit: int = 30
) -> list[dict]:
    rows = (
        (
            await db.execute(
                select(AgentSession)
                .where(AgentSession.user_id == user_id)
                .order_by(AgentSession.updated_at.desc())
                .limit(max(1, min(limit, 100)))
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": item.id,
            "title": item.title,
            "prompt": item.prompt,
            "updatedAt": item.updated_at,
        }
        for item in rows
    ]


async def list_monitors(db: AsyncSession, user_id: int, limit: int = 50) -> list[dict]:
    rows = (
        (
            await db.execute(
                select(AgentMonitor)
                .where(AgentMonitor.user_id == user_id)
                .order_by(AgentMonitor.created_at.desc())
                .limit(max(1, min(limit, 100)))
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": item.id,
            "name": item.name,
            "conditions": item.conditions or {},
            "createdAt": item.created_at,
            "newMatches": item.new_matches,
        }
        for item in rows
    ]


async def create_monitor(
    db: AsyncSession, name: str, conditions: dict, *, user_id: int
) -> dict:
    monitor = AgentMonitor(
        id=f"M-{uuid.uuid4().hex[:6].upper()}",
        user_id=user_id,
        name=name[:128],
        conditions=conditions,
    )
    db.add(monitor)
    await db.commit()
    await db.refresh(monitor)
    return {
        "id": monitor.id,
        "name": monitor.name,
        "conditions": monitor.conditions or {},
        "createdAt": monitor.created_at,
        "newMatches": monitor.new_matches,
    }


async def delete_monitor(
    db: AsyncSession, monitor_id: str, *, user_id: int, is_admin: bool = False
) -> bool:
    monitor = await db.get(AgentMonitor, monitor_id)
    if monitor is None:
        return False
    if not is_admin and monitor.user_id != user_id:
        return False
    await db.delete(monitor)
    await db.commit()
    return True


async def list_admin_sessions(db: AsyncSession, limit: int = 50) -> list[dict]:
    rows = (
        (
            await db.execute(
                select(AgentSession)
                .order_by(AgentSession.updated_at.desc())
                .limit(max(1, min(limit, 100)))
            )
        )
        .scalars()
        .all()
    )
    result = []
    for item in rows:
        plan = [
            [
                step.get("label", ""),
                step.get("desc", ""),
                step.get("status", "pending"),
                step.get("time", ""),
            ]
            for step in (item.plan or [])
            if isinstance(step, dict)
        ]
        result.append(
            {
                "id": item.id,
                "query": item.prompt,
                "stage": item.stage or "—",
                "cand": item.candidates or "—",
                "tools": item.tools_count,
                "amap": item.amap_count,
                "latency": f"{item.latency_ms / 1000:.1f}s" if item.latency_ms else "—",
                "status": item.status,
                "model": item.model or "规则版",
                "promptTokens": item.prompt_tokens,
                "completionTokens": item.completion_tokens,
                "cost": float(item.cost or 0),
                "fallback": item.llm_fallback,
                "plan": plan,
                "toolsList": item.tools_list or [],
                "result": item.result or "",
            }
        )
    return result


async def annotate_session(db: AsyncSession, session_id: str, label: str) -> bool:
    session = await db.get(AgentSession, session_id)
    if session is None:
        return False
    session.label = label[:32]
    await db.commit()
    return True
