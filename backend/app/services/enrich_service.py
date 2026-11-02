import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.integrations.base import Capability, ProviderError, ProviderQuotaExceeded
from app.models import City, Community, CommuteSample, Listing, PoiCache, Source, Task
from app.services import provider_runtime
from app.services.score_service import score_listing
from app.services.settings_service import (
    destination_key,
    get_admin_settings,
    get_commute_destination,
)

log = get_logger("enrich")

POI_TTL_DAYS = 30
COMMUTE_TTL_DAYS = 7
DAILY_TYPES = "060200|060300|060400"


async def _ensure_geocode(db: AsyncSession, community: Community, city: City) -> bool:
    if community.lng is not None and community.lat is not None:
        return True
    try:
        poi = await provider_runtime.invoke(
            db,
            Capability.poi_search,
            "search_poi",
            community.name,
            city.name,
            cap_key="amapMonthlyCap",
        )
    except ProviderQuotaExceeded:
        raise
    except ProviderError as exc:
        log.warning("poi_geocode_failed", community=community.name, error=str(exc))
        poi = None
    if poi is not None:
        community.lng = poi["lng"]
        community.lat = poi["lat"]
        community.adcode = poi.get("adcode")
        community.geocode_confidence = 0.85
        await db.flush()
        return True

    query = f"{community.name} {community.district or ''}".strip()
    try:
        result = await provider_runtime.invoke(
            db,
            Capability.geocode,
            "geocode",
            query,
            city.name,
            cap_key="amapMonthlyCap",
        )
    except ProviderQuotaExceeded:
        raise
    except ProviderError as exc:
        log.warning("geocode_failed", community=community.name, error=str(exc))
        return False
    if result is None:
        log.warning("geocode_empty", community=community.name, query=query)
        return False
    community.lng = result["lng"]
    community.lat = result["lat"]
    community.adcode = result.get("adcode")
    community.geocode_confidence = 0.4 if result.get("level") in {"区县", "城市", "省份"} else 0.7
    await db.flush()
    return True


async def _ensure_poi(db: AsyncSession, community: Community) -> PoiCache | None:
    if community.lng is None or community.lat is None:
        return None
    cache = await db.get(PoiCache, community.id)
    if cache is not None:
        fetched = cache.fetched_at
        if fetched.tzinfo is None:
            fetched = fetched.replace(tzinfo=UTC)
        if datetime.now(UTC) - fetched < timedelta(days=POI_TTL_DAYS):
            return cache

    location = f"{community.lng},{community.lat}"
    try:
        dining = await provider_runtime.invoke(
            db,
            Capability.poi_search,
            "around_count",
            location,
            "050000",
            radius=1000,
            cap_key="amapMonthlyCap",
        )
        await asyncio.sleep(0.15)
        daily = await provider_runtime.invoke(
            db,
            Capability.poi_search,
            "around_count",
            location,
            DAILY_TYPES,
            radius=1000,
            cap_key="amapMonthlyCap",
        )
        await asyncio.sleep(0.15)
        nightlife = await provider_runtime.invoke(
            db,
            Capability.poi_search,
            "around_count",
            location,
            "050600",
            radius=1000,
            cap_key="amapMonthlyCap",
        )
    except ProviderQuotaExceeded:
        raise
    except ProviderError as exc:
        log.warning("poi_failed", community=community.name, error=str(exc))
        return cache

    raw = {"dining": dining, "daily": daily, "nightlife": nightlife, "radius": 1000}
    if cache is None:
        cache = PoiCache(community_id=community.id)
        db.add(cache)
    cache.dining_count = dining
    cache.daily_count = daily
    cache.nightlife_count = nightlife
    cache.raw = raw
    cache.fetched_at = datetime.now(UTC)
    await db.flush()
    return cache


async def _ensure_commute(
    db: AsyncSession, community: Community, city: City, destination: dict | None
) -> None:
    if not destination or community.lng is None or community.lat is None:
        return
    key = destination_key(destination)
    if key is None:
        return
    latest = await db.scalar(
        select(CommuteSample)
        .where(CommuteSample.community_id == community.id, CommuteSample.destination_key == key)
        .order_by(CommuteSample.fetched_at.desc())
        .limit(1)
    )
    if latest is not None:
        fetched = latest.fetched_at
        if fetched.tzinfo is None:
            fetched = fetched.replace(tzinfo=UTC)
        age = datetime.now(UTC) - fetched
        # 高德样本逐步替换为深圳地铁官方；旧样本超过 1 天后优先重采
        if latest.provider == "szmc":
            if age < timedelta(days=COMMUTE_TTL_DAYS):
                return
        elif age < timedelta(days=1):
            return
    try:
        route = await provider_runtime.invoke(
            db,
            Capability.route_transit,
            "transit",
            f"{community.lng},{community.lat}",
            f"{destination['lng']},{destination['lat']}",
            city_code(city.code),
            cap_key="amapMonthlyCap",
        )
    except ProviderQuotaExceeded:
        raise
    except ProviderError as exc:
        log.warning("commute_failed", community=community.name, error=str(exc))
        return
    if route is None:
        return
    db.add(
        CommuteSample(
            community_id=community.id,
            destination_key=key,
            mode=str(route.get("mode") or "transit"),
            duration_s=route["duration_s"],
            distance_m=route.get("distance_m"),
            transfers=route.get("transfers"),
            provider=str(route.get("provider") or "amap"),
            raw={
                "destination": destination.get("address"),
                "walk_min": route.get("walk_min"),
                **(route.get("raw") or {}),
            },
        )
    )
    await db.flush()


def city_code(code: str) -> str:
    return {"sz": "0755", "sh": "021", "bj": "010", "gz": "020"}.get(code, "0755")


async def enrich_task(db: AsyncSession, task: Task, limit: int = 100) -> dict:
    admin_settings = await get_admin_settings(db)
    limit = max(1, min(limit, int(admin_settings.get("batchCap") or 10)))
    city = await db.get(City, task.city_id)
    source = await db.get(Source, task.source_id)
    if city is None or source is None:
        raise ValueError("task city or source missing")

    community_ids = (
        (
            await db.execute(
                select(Listing.community_id)
                .where(
                    Listing.city_id == city.id,
                    Listing.source_id == source.id,
                    Listing.community_id.is_not(None),
                )
                .distinct()
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    destination = await get_commute_destination(db)
    stats = {
        "communities": 0,
        "geocoded": 0,
        "poi": 0,
        "commute": 0,
        "destination": bool(destination),
    }
    for community_id in community_ids:
        community = await db.get(Community, community_id)
        if community is None:
            continue
        before_geo = community.lng is not None
        if not await _ensure_geocode(db, community, city):
            continue
        if not before_geo:
            stats["geocoded"] += 1
        cache = await _ensure_poi(db, community)
        if cache is not None:
            stats["poi"] += 1
        before_commute = await db.scalar(
            select(CommuteSample.id).where(CommuteSample.community_id == community.id).limit(1)
        )
        await _ensure_commute(db, community, city, destination)
        after_commute = await db.scalar(
            select(CommuteSample.id).where(CommuteSample.community_id == community.id).limit(1)
        )
        if after_commute and not before_commute:
            stats["commute"] += 1
        stats["communities"] += 1
        await db.commit()
        log.info("enrich_community", community=community.name, **stats)
    return stats


async def rescore_task(db: AsyncSession, task: Task, limit: int = 2000) -> dict:
    city = await db.get(City, task.city_id)
    source = await db.get(Source, task.source_id)
    if city is None or source is None:
        raise ValueError("task city or source missing")
    listings = (
        (
            await db.execute(
                select(Listing)
                .where(Listing.city_id == city.id, Listing.source_id == source.id)
                .order_by(Listing.id.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    scored = 0
    for listing in listings:
        result = await score_listing(db, listing, task.filters or {})
        if result is None:
            listing.score = None
            listing.score_reasons = {"filter": "未通过硬过滤"}
        else:
            listing.score, listing.score_reasons = result
            scored += 1
    await db.commit()
    return {"listings": len(listings), "scored": scored}


async def enrich_communities(
    db: AsyncSession, community_ids: list[int], limit: int | None = None
) -> dict:
    destination = await get_commute_destination(db)
    key = destination_key(destination)
    stats = {
        "communities": 0,
        "geocoded": 0,
        "poi": 0,
        "commute": 0,
        "destination": bool(destination),
    }
    ids = community_ids[:limit] if limit else community_ids
    for community_id in ids:
        community = await db.get(Community, community_id)
        if community is None:
            continue
        city = await db.get(City, community.city_id)
        if city is None:
            continue
        before_geo = community.lng is not None
        if not await _ensure_geocode(db, community, city):
            continue
        if not before_geo:
            stats["geocoded"] += 1
        if await _ensure_poi(db, community) is not None:
            stats["poi"] += 1
        before_commute = None
        if key:
            before_commute = await db.scalar(
                select(CommuteSample.id)
                .where(
                    CommuteSample.community_id == community.id,
                    CommuteSample.destination_key == key,
                )
                .limit(1)
            )
        await _ensure_commute(db, community, city, destination)
        after_commute = None
        if key:
            after_commute = await db.scalar(
                select(CommuteSample.id)
                .where(
                    CommuteSample.community_id == community.id,
                    CommuteSample.destination_key == key,
                )
                .limit(1)
            )
        if after_commute and not before_commute:
            stats["commute"] += 1
        stats["communities"] += 1
        await db.commit()
        log.info("enrich_community", community=community.name, **stats)
    return stats


async def rescore_listings(db: AsyncSession, task: Task, listing_ids: list[int]) -> dict:
    city = await db.get(City, task.city_id)
    source = await db.get(Source, task.source_id)
    if city is None or source is None:
        raise ValueError("task city or source missing")
    if not listing_ids:
        return {"listings": 0, "scored": 0}
    listings = (
        (
            await db.execute(
                select(Listing).where(
                    Listing.id.in_(listing_ids),
                    Listing.city_id == city.id,
                    Listing.source_id == source.id,
                )
            )
        )
        .scalars()
        .all()
    )
    scored = 0
    for listing in listings:
        result = await score_listing(db, listing, task.filters or {})
        if result is None:
            listing.score = None
            listing.score_reasons = {"filter": "未通过硬过滤"}
        else:
            listing.score, listing.score_reasons = result
            scored += 1
    await db.commit()
    return {"listings": len(listings), "scored": scored}
