"""Revocable read-only dashboard links (P2/W8).

Only the SHA-256 hash of a link token is stored.  The raw token is returned to
the admin once when the link is created.  The public payload intentionally
contains aggregates only: no listing titles, images, addresses or contact
details, and every response is marked ``X-Robots-Tag: noindex``.
"""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Listing, ListingStatus, ShareLink
from app.services import admin_service

TOKEN_PREFIX = "rr_share_"


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def issue_token() -> tuple[str, str, str]:
    """Return (raw_token, hash, short_prefix)."""
    raw = f"{TOKEN_PREFIX}{secrets.token_urlsafe(24)}"
    return raw, hash_token(raw), raw[: len(TOKEN_PREFIX) + 6]


def _link_dict(link: ShareLink, *, include_token: str | None = None) -> dict:
    result = {
        "id": link.id,
        "label": link.label,
        "token_prefix": link.token_prefix,
        "scope": link.scope,
        "created_at": link.created_at,
        "expires_at": link.expires_at,
        "revoked_at": link.revoked_at,
        "last_used_at": link.last_used_at,
        "use_count": link.use_count,
        "active": link.revoked_at is None
        and (link.expires_at is None or link.expires_at > datetime.now(UTC)),
    }
    if include_token is not None:
        result["token"] = include_token
    return result


async def create_link(
    db: AsyncSession,
    *,
    label: str,
    expires_days: int,
    user_id: int | None,
) -> dict:
    raw, digest, prefix = issue_token()
    link = ShareLink(
        token_hash=digest,
        token_prefix=prefix,
        label=label[:64] or "只读看板",
        created_by=user_id,
        expires_at=datetime.now(UTC) + timedelta(days=max(1, expires_days)),
    )
    db.add(link)
    await db.commit()
    await db.refresh(link)
    return _link_dict(link, include_token=raw)


async def list_links(db: AsyncSession) -> list[dict]:
    rows = (
        (await db.execute(select(ShareLink).order_by(ShareLink.created_at.desc())))
        .scalars()
        .all()
    )
    return [_link_dict(item) for item in rows]


async def revoke_link(db: AsyncSession, link_id: int) -> dict | None:
    link = await db.get(ShareLink, link_id)
    if link is None:
        return None
    link.revoked_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(link)
    return _link_dict(link)


async def resolve_token(db: AsyncSession, token: str) -> ShareLink | None:
    if not token.startswith(TOKEN_PREFIX):
        return None
    link = await db.scalar(
        select(ShareLink).where(ShareLink.token_hash == hash_token(token))
    )
    if link is None or link.revoked_at is not None:
        return None
    if link.expires_at is not None:
        expires = link.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        if expires <= datetime.now(UTC):
            return None
    link.last_used_at = datetime.now(UTC)
    link.use_count = int(link.use_count or 0) + 1
    await db.commit()
    return link


def _median(values: list[int]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[middle])
    return (ordered[middle - 1] + ordered[middle]) / 2


def aggregate_dashboard(
    *,
    active: int,
    scored: int,
    communities: int,
    districts: list[tuple[str, int, int | None, float | None]],
    price_bands: dict[str, int] | None,
    line5: dict | None,
    generated_at: datetime,
) -> dict:
    """Build the public payload from already aggregated rows (unit tested)."""
    district_rows = []
    for name, count, median_rent, avg_score in districts:
        district_rows.append(
            {
                "name": name,
                "listings": int(count),
                "median_rent": int(median_rent) if median_rent is not None else None,
                "avg_score": round(float(avg_score), 1) if avg_score is not None else None,
            }
        )
    bands = {
        "<=3000": 0,
        "3000-5000": 0,
        "5000-8000": 0,
        ">8000": 0,
        "unknown": 0,
        **(price_bands or {}),
    }
    line_summary = (line5 or {}).get("summary") or {}
    return {
        "generated_at": generated_at.isoformat(),
        "totals": {
            "active_listings": int(active),
            "scored_listings": int(scored),
            "communities": int(communities),
            "districts": len(district_rows),
            "scored_ratio": round(scored / active, 3) if active else 0,
        },
        "districts": sorted(
            district_rows, key=lambda item: item["listings"], reverse=True
        ),
        "price_bands": bands,
        "line5": {
            "shards": int(line_summary.get("shards") or 0),
            "listings": int(line_summary.get("listings") or 0),
            "complete": int(line_summary.get("complete") or 0),
            "scanned": int(line_summary.get("scanned") or 0),
        },
        "data_note": (
            "仅聚合数据：不含房源标题、图片、地址或联系方式；数据来自本地库存，"
            "覆盖与价格以最近一轮采集为准。"
        ),
        "source": {"name": "贝壳租房（App 列表）", "url": "https://sz.zu.ke.com/"},
    }


async def public_dashboard(db: AsyncSession) -> dict:
    active = int(
        await db.scalar(
            select(func.count())
            .select_from(Listing)
            .where(Listing.status == ListingStatus.active)
        )
        or 0
    )
    scored = int(
        await db.scalar(
            select(func.count())
            .select_from(Listing)
            .where(Listing.status == ListingStatus.active, Listing.score.is_not(None))
        )
        or 0
    )
    communities = int(
        await db.scalar(
            select(func.count(func.distinct(Listing.community_id))).where(
                Listing.status == ListingStatus.active,
                Listing.community_id.is_not(None),
            )
        )
        or 0
    )
    rows = (
        await db.execute(
            select(
                Listing.district,
                func.count(),
                func.percentile_cont(0.5).within_group(Listing.rent),
                func.avg(Listing.score),
            )
            .where(
                Listing.status == ListingStatus.active,
                Listing.district.is_not(None),
                Listing.district != "",
            )
            .group_by(Listing.district)
        )
    ).all()
    districts = [
        (str(name), int(count), int(median) if median is not None else None, avg)
        for name, count, median, avg in rows
    ]
    rents = (
        (
            await db.execute(
                select(Listing.rent).where(
                    Listing.status == ListingStatus.active,
                    Listing.rent.is_not(None),
                )
            )
        )
        .scalars()
        .all()
    )
    bands = {"<=3000": 0, "3000-5000": 0, "5000-8000": 0, ">8000": 0, "unknown": 0}
    for rent in rents:
        if rent is None:
            bands["unknown"] += 1
        elif rent <= 3000:
            bands["<=3000"] += 1
        elif rent <= 5000:
            bands["3000-5000"] += 1
        elif rent <= 8000:
            bands["5000-8000"] += 1
        else:
            bands[">8000"] += 1
    try:
        coverage = await admin_service.crawl_coverage(db)
    except Exception:  # pragma: no cover - public page must not fail on ops data
        coverage = {}
    return aggregate_dashboard(
        active=active,
        scored=scored,
        communities=communities,
        districts=districts,
        price_bands=bands,
        line5=coverage,
        generated_at=datetime.now(UTC),
    )
