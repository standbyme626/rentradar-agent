"""Cities and housing sources (P2/W9).

Cities and sources already existed in the schema but only one of each was
usable.  These helpers expose them to the admin UI, enforce the per-object
enable switch and keep source support explicit (``beike`` + ``manual``).
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import City, Community, Listing, ListingStatus, Source, Task

SUPPORTED_HOUSING_SOURCES = {
    "beike": "贝壳 App 列表 API",
    "manual": "手动导入（品牌公寓/线下房源）",
}
RESERVED_HOUSING_SOURCES = {
    "ziroom": "自如（预留，未接入）",
}


def _city_dict(city: City, *, listings: int, communities: int, tasks: int) -> dict:
    return {
        "id": city.id,
        "code": city.code,
        "name": city.name,
        "domain_template": city.domain_template,
        "center_lng": float(city.center_lng) if city.center_lng is not None else None,
        "center_lat": float(city.center_lat) if city.center_lat is not None else None,
        "enabled": bool(city.enabled),
        "listings": int(listings),
        "communities": int(communities),
        "tasks": int(tasks),
    }


def _source_dict(source: Source, *, listings: int, tasks: int) -> dict:
    code = source.code
    return {
        "id": source.id,
        "code": code,
        "name": source.name,
        "kind": source.kind,
        "enabled": bool(source.enabled),
        "rate_limit": source.rate_limit or {},
        "listings": int(listings),
        "tasks": int(tasks),
        "supported": code in SUPPORTED_HOUSING_SOURCES,
        "reserved": code in RESERVED_HOUSING_SOURCES,
        "note": SUPPORTED_HOUSING_SOURCES.get(code)
        or RESERVED_HOUSING_SOURCES.get(code)
        or "保留来源",
    }


async def list_cities(db: AsyncSession) -> list[dict]:
    rows = (await db.execute(select(City).order_by(City.id))).scalars().all()
    result = []
    for city in rows:
        listings = int(
            await db.scalar(
                select(func.count())
                .select_from(Listing)
                .where(Listing.city_id == city.id)
            )
            or 0
        )
        communities = int(
            await db.scalar(
                select(func.count())
                .select_from(Community)
                .where(Community.city_id == city.id)
            )
            or 0
        )
        tasks = int(
            await db.scalar(
                select(func.count()).select_from(Task).where(Task.city_id == city.id)
            )
            or 0
        )
        result.append(
            _city_dict(city, listings=listings, communities=communities, tasks=tasks)
        )
    return result


async def update_city(db: AsyncSession, code: str, enabled: bool) -> dict | None:
    city = await db.scalar(select(City).where(City.code == code))
    if city is None:
        return None
    city.enabled = enabled
    await db.commit()
    rows = [item for item in await list_cities(db) if item["code"] == code]
    return rows[0] if rows else None


async def list_sources(db: AsyncSession) -> list[dict]:
    rows = (await db.execute(select(Source).order_by(Source.id))).scalars().all()
    result = []
    for source in rows:
        listings = int(
            await db.scalar(
                select(func.count())
                .select_from(Listing)
                .where(Listing.source_id == source.id)
            )
            or 0
        )
        tasks = int(
            await db.scalar(
                select(func.count()).select_from(Task).where(Task.source_id == source.id)
            )
            or 0
        )
        result.append(_source_dict(source, listings=listings, tasks=tasks))
    return result


async def update_source(db: AsyncSession, code: str, enabled: bool) -> dict | None:
    source = await db.scalar(select(Source).where(Source.code == code))
    if source is None:
        return None
    source.enabled = enabled
    await db.commit()
    rows = [item for item in await list_sources(db) if item["code"] == code]
    return rows[0] if rows else None


async def active_city_codes(db: AsyncSession) -> set[str]:
    return set(
        (await db.execute(select(City.code).where(City.enabled.is_(True)))).scalars().all()
    )


async def city_health(db: AsyncSession) -> list[dict]:
    """Per-city isolation view: any failure stays with the failing city."""
    rows = []
    for city in await list_cities(db):
        active = int(
            await db.scalar(
                select(func.count())
                .select_from(Listing)
                .where(
                    Listing.city_id == city["id"],
                    Listing.status == ListingStatus.active,
                )
            )
            or 0
        )
        enabled_tasks = int(
            await db.scalar(
                select(func.count())
                .select_from(Task)
                .where(Task.city_id == city["id"], Task.enabled.is_(True))
            )
            or 0
        )
        rows.append(
            {**city, "active_listings": active, "enabled_tasks": enabled_tasks}
        )
    return rows
