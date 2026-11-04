"""Official / semi-official rent references (P3).

There is no approved 住建局 API key in this environment, so this module
implements the data contract and manual import path.  When a reference exists
the price component uses it instead of the listing median; otherwise the
existing median fallback is unchanged.
"""

import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import City, Community, Listing, ReferenceRent

LAYOUT_RE = re.compile(r"(\d)\s*室")
CONFIDENCE_FLOOR = 0.5


def normalize_layout(layout: str | None) -> str:
    match = LAYOUT_RE.search(str(layout or ""))
    return f"{match.group(1)}室" if match else str(layout or "").strip()[:32]


def _reference_dict(row: ReferenceRent) -> dict:
    return {
        "id": row.id,
        "city_id": row.city_id,
        "community_id": row.community_id,
        "community_name": row.community_name,
        "district": row.district,
        "layout": row.layout,
        "monthly_rent": int(row.monthly_rent),
        "reference_month": row.reference_month,
        "source": row.source,
        "url": row.url,
        "confidence": float(row.confidence),
        "updated_at": row.updated_at,
    }


async def import_rows(
    db: AsyncSession, city_code: str, rows: list[dict]
) -> dict:
    city = await db.scalar(select(City).where(City.code == city_code))
    if city is None:
        raise ValueError(f"unknown city: {city_code}")
    created = 0
    updated = 0
    for row in rows:
        community_id = row.get("communityId") or row.get("community_id")
        community_name = row.get("communityName") or row.get("community_name")
        community = None
        if community_id:
            community = await db.get(Community, int(community_id))
        elif community_name:
            community = await db.scalar(
                select(Community).where(
                    Community.city_id == city.id, Community.name == community_name
                )
            )
        layout = normalize_layout(row.get("layout"))
        reference_month = str(
            row.get("referenceMonth") or row.get("reference_month") or ""
        ).strip()
        monthly_rent = row.get("monthlyRent") or row.get("monthly_rent")
        if not reference_month or monthly_rent is None:
            raise ValueError("each reference row needs referenceMonth and monthlyRent")
        source = row.get("source", "manual")
        existing = await db.scalar(
            select(ReferenceRent).where(
                ReferenceRent.city_id == city.id,
                ReferenceRent.community_id
                == (community.id if community else None),
                ReferenceRent.layout == layout,
                ReferenceRent.reference_month == reference_month,
                ReferenceRent.source == source,
            )
        )
        values = {
            "city_id": city.id,
            "community_id": community.id if community else None,
            "community_name": community.name if community else community_name,
            "district": row.get("district")
            or (community.district if community else None),
            "layout": layout,
            "monthly_rent": int(monthly_rent),
            "reference_month": reference_month,
            "source": source,
            "url": row.get("url"),
            "confidence": float(row.get("confidence", 0.8)),
        }
        if existing is None:
            db.add(ReferenceRent(**values))
            created += 1
        else:
            for key, value in values.items():
                setattr(existing, key, value)
            existing.updated_at = datetime.now(UTC)
            updated += 1
    await db.commit()
    return {"created": created, "updated": updated, "total": created + updated}


async def list_references(
    db: AsyncSession, *, city_code: str | None = None, layout: str | None = None, limit: int = 200
) -> list[dict]:
    stmt = select(ReferenceRent).order_by(
        ReferenceRent.reference_month.desc(), ReferenceRent.id.desc()
    )
    if city_code:
        city = await db.scalar(select(City).where(City.code == city_code))
        if city is None:
            return []
        stmt = stmt.where(ReferenceRent.city_id == city.id)
    if layout:
        stmt = stmt.where(ReferenceRent.layout == normalize_layout(layout))
    rows = (await db.execute(stmt.limit(max(1, min(limit, 1000))))).scalars().all()
    return [_reference_dict(row) for row in rows]


async def delete_reference(db: AsyncSession, reference_id: int) -> bool:
    row = await db.get(ReferenceRent, reference_id)
    if row is None:
        return False
    await db.delete(row)
    await db.commit()
    return True


def pick_latest(rows: list[ReferenceRent]) -> ReferenceRent | None:
    if not rows:
        return None
    return sorted(
        rows, key=lambda item: (item.reference_month, float(item.confidence)), reverse=True
    )[0]


async def latest_for_listing(
    db: AsyncSession, listing: Listing
) -> dict | None:
    layout = normalize_layout(listing.layout)
    if not layout:
        return None
    rows = (
        (
            await db.execute(
                select(ReferenceRent).where(
                    ReferenceRent.city_id == listing.city_id,
                    ReferenceRent.layout == layout,
                    ReferenceRent.confidence >= CONFIDENCE_FLOOR,
                )
            )
        )
        .scalars()
        .all()
    )
    matched = [
        row
        for row in rows
        if (listing.community_id and row.community_id == listing.community_id)
        or (
            not row.community_id
            and listing.community_name
            and row.community_name == listing.community_name
        )
    ]
    if not matched and listing.district:
        matched = [
            row
            for row in rows
            if not row.community_id
            and not row.community_name
            and row.district == listing.district
        ]
    picked = pick_latest(matched)
    return _reference_dict(picked) if picked else None
