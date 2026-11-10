"""Commute sampling and aggregation (SZMC / AMap samples).

The SZMC ``MinTimeJson`` endpoint is a scheduled minimum-time estimate: it has
no departure-time parameter, so sampling different ``depart_bucket`` values
yields the same duration. We still record the bucket requested by the plan,
compute p50/p90 over the collected samples and expose ``static`` so the UI can
label the value honestly instead of implying real-time traffic variance.
"""

import math
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.integrations.base import Capability, ProviderError, ProviderQuotaExceeded
from app.models import City, Community, CommuteSample
from app.services import provider_runtime
from app.services.settings_service import destination_key

log = get_logger("commute")

COMMUTE_BUCKETS = ("07:30", "08:00", "08:30", "09:00")
DIRECTION = "community_to_destination"
DIRECTION_LABEL = "小区→公司"
STATS_WINDOW_DAYS = 30
SZMC_TTL_DAYS = 7
AMAP_TTL_DAYS = 1
CITY_CODES = {"sz": "0755", "sh": "021", "bj": "010", "gz": "020"}


def city_code(code: str) -> str:
    return CITY_CODES.get(code, "0755")


def percentile(values: list[float], ratio: float) -> float | None:
    """Linear-interpolation percentile; deterministic for small samples."""
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * ratio
    low = math.floor(position)
    high = math.ceil(position)
    if low == high:
        return ordered[low]
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def _window_start() -> datetime:
    return datetime.now(UTC) - timedelta(days=STATS_WINDOW_DAYS)


def summarize(rows: list[CommuteSample]) -> dict | None:
    if not rows:
        return None
    # Prefer SZMC once it exists so old AMap samples do not mix into the p50.
    szmc = [row for row in rows if row.provider == "szmc"]
    chosen = szmc or rows
    durations = [row.duration_s for row in chosen]
    latest = max(chosen, key=lambda row: _aware(row.fetched_at))
    buckets = sorted({row.depart_bucket for row in chosen if row.depart_bucket})
    p50 = percentile(durations, 0.5)
    p90 = percentile(durations, 0.9)
    raw = latest.raw or {}
    return {
        "samples": len(chosen),
        "buckets": buckets,
        "bucket_count": len(buckets),
        "multi_bucket": len(buckets) >= 3,
        "p50_s": int(round(p50)),
        "p90_s": int(round(p90)),
        "p50_min": round(p50 / 60, 1),
        "p90_min": round(p90 / 60, 1),
        "static": (max(durations) - min(durations)) <= 1,
        "provider": latest.provider,
        "mode": latest.mode,
        "direction": latest.direction or DIRECTION,
        "transfers": latest.transfers,
        "walk_min": raw.get("walk_min"),
        "fetched_at": _aware(latest.fetched_at),
    }


def with_destination(stats: dict | None, destination: dict | None) -> dict | None:
    if stats is None:
        return None
    stats = dict(stats)
    stats["destination"] = (destination or {}).get("address")
    stats["example"] = bool((destination or {}).get("example"))
    stats["direction_label"] = DIRECTION_LABEL
    return stats


async def _samples(
    db: AsyncSession, key: str, *, community_id: int | None = None
) -> list[CommuteSample]:
    stmt = (
        select(CommuteSample)
        .where(
            CommuteSample.destination_key == key,
            CommuteSample.direction == DIRECTION,
            CommuteSample.fetched_at >= _window_start(),
        )
        .order_by(CommuteSample.community_id, CommuteSample.fetched_at.desc())
    )
    if community_id is not None:
        stmt = stmt.where(CommuteSample.community_id == community_id)
    return list((await db.execute(stmt)).scalars().all())


async def community_stats(
    db: AsyncSession,
    community_id: int,
    key: str,
    *,
    destination: dict | None = None,
) -> dict | None:
    rows = await _samples(db, key, community_id=community_id)
    if not rows:
        fallback = await nearest_destination_key(db, key, min_communities=1)
        if fallback and fallback != key:
            rows = await _samples(db, fallback, community_id=community_id)
    return with_destination(summarize(rows), destination)


async def bulk_stats(
    db: AsyncSession, key: str, *, destination: dict | None = None
) -> dict[int, dict]:
    rows = await _samples(db, key)
    grouped: dict[int, list[CommuteSample]] = defaultdict(list)
    for row in rows:
        grouped[row.community_id].append(row)
    if len(grouped) < 50:
        fallback = await nearest_destination_key(db, key)
        if fallback and fallback != key:
            rows = await _samples(db, fallback)
            grouped = defaultdict(list)
            for row in rows:
                grouped[row.community_id].append(row)
    result: dict[int, dict] = {}
    for community_id, rows in grouped.items():
        stats = with_destination(summarize(rows), destination)
        if stats is not None:
            result[community_id] = stats
    return result


def _distance_m(lng1: float, lat1: float, lng2: float, lat2: float) -> float:
    radius = 6_371_000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


async def nearest_destination_key(
    db: AsyncSession,
    key: str,
    *,
    max_meters: float = 2500.0,
    min_communities: int = 50,
) -> str | None:
    """Reuse commute samples from a nearby destination key.

    The workspace geocoder can return a POI a few hundred metres from the
    station used for the existing samples, producing a new exact key with no
    samples. Falling back to the nearest sampled destination keeps the chat
    usable instead of hard-filtering every listing out.
    """
    try:
        lng, lat = (float(part) for part in key.split(",", 1))
    except (AttributeError, TypeError, ValueError):
        return None
    counts = {
        str(candidate): int(count)
        for candidate, count in (
            await db.execute(
                select(
                    CommuteSample.destination_key,
                    func.count(func.distinct(CommuteSample.community_id)),
                )
                .where(
                    CommuteSample.direction == DIRECTION,
                    CommuteSample.fetched_at >= _window_start(),
                )
                .group_by(CommuteSample.destination_key)
            )
        ).all()
    }
    if counts.get(key, 0) >= min_communities:
        return key
    best: str | None = None
    best_count = -1
    best_distance = max_meters
    for candidate, count in counts.items():
        try:
            candidate_lng, candidate_lat = (
                float(part) for part in candidate.split(",", 1)
            )
        except (AttributeError, TypeError, ValueError):
            continue
        distance = _distance_m(lng, lat, candidate_lng, candidate_lat)
        if distance > max_meters:
            continue
        if count > best_count or (count == best_count and distance < best_distance):
            best = candidate
            best_count = count
            best_distance = distance
    return best or key


def _is_fresh(sample: CommuteSample, now: datetime) -> bool:
    ttl = SZMC_TTL_DAYS if sample.provider == "szmc" else AMAP_TTL_DAYS
    return now - _aware(sample.fetched_at) < timedelta(days=ttl)


def _latest_by_bucket(rows: list[CommuteSample]) -> dict[str, CommuteSample]:
    latest: dict[str, CommuteSample] = {}
    for row in rows:
        if row.depart_bucket and row.depart_bucket not in latest:
            latest[row.depart_bucket] = row
    return latest


async def ensure_commute(
    db: AsyncSession,
    community: Community,
    city: City,
    destination: dict | None,
    *,
    buckets: list[str] | tuple[str, ...] | None = None,
) -> dict:
    """Sample the requested departure buckets for one community.

    A community has at most one fresh sample per bucket. SZMC buckets are
    cheap (zero quota) but time-independent; a non-SZMC fallback gets one
    sample because the old providers are not part of the plan.
    """
    key = destination_key(destination)
    empty = {"sampled": 0, "provider": None, "buckets": []}
    if not destination or key is None or community.lng is None or community.lat is None:
        return empty
    rows = list(
        (
            await db.execute(
                select(CommuteSample)
                .where(
                    CommuteSample.community_id == community.id,
                    CommuteSample.destination_key == key,
                    CommuteSample.direction == DIRECTION,
                )
                .order_by(CommuteSample.fetched_at.desc())
            )
        )
        .scalars()
        .all()
    )
    latest = _latest_by_bucket(rows)
    now = datetime.now(UTC)
    wanted = [str(item) for item in (buckets or COMMUTE_BUCKETS) if str(item).strip()]
    sampled = 0
    provider = None
    for bucket in dict.fromkeys(wanted):
        current = latest.get(bucket)
        if current is not None and _is_fresh(current, now):
            continue
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
            log.warning(
                "commute_failed",
                community=community.name,
                bucket=bucket,
                error=str(exc)[:200],
            )
            break
        if route is None:
            break
        provider = str(route.get("provider") or "amap")
        db.add(
            CommuteSample(
                community_id=community.id,
                destination_key=key,
                mode=str(route.get("mode") or "transit"),
                duration_s=route["duration_s"],
                distance_m=route.get("distance_m"),
                transfers=route.get("transfers"),
                provider=provider,
                depart_bucket=bucket,
                direction=DIRECTION,
                raw={
                    "destination": destination.get("address"),
                    "depart_bucket": bucket,
                    "direction": DIRECTION_LABEL,
                    "walk_min": route.get("walk_min"),
                    **(route.get("raw") or {}),
                },
            )
        )
        sampled += 1
        await db.flush()
        if provider != "szmc":
            # AMap/CDP fallbacks have no departure bucket; one sample is enough.
            break
    return {"sampled": sampled, "provider": provider, "buckets": wanted}
