"""Postgres cache for SZMC subway lines/stations (P3)."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models import TransitLine, TransitStation
from app.services import provider_runtime

log = get_logger("transit")
CACHE_TTL = timedelta(hours=24)


def line_key(city_code: str, line_code: str) -> str:
    return f"{city_code}:{line_code}"[:64]


async def sync_catalog(
    db: AsyncSession, catalog: dict, city_code: str = "sz"
) -> dict:
    lines = catalog.get("lines") or []
    if not lines:
        raise ValueError("empty transit catalog")
    now = datetime.now(UTC)
    keys: set[str] = set()
    for line in lines:
        code = str(line.get("id") or "").strip()
        if not code:
            continue
        key = line_key(city_code, code)
        keys.add(key)
        row = await db.get(TransitLine, key)
        if row is None:
            row = TransitLine(line_key=key, city_code=city_code, line_code=code)
            db.add(row)
        row.name = str(line.get("name") or code)[:128]
        row.color = str(line.get("color") or "2f7d5b").lstrip("#")[:16]
        row.updated_at = now
        await db.flush()
        await db.execute(delete(TransitStation).where(TransitStation.line_key == key))
        for seq, station in enumerate(line.get("stations") or []):
            sid = str(station.get("sid") or "").strip()
            if not sid:
                continue
            db.add(
                TransitStation(
                    line_key=key,
                    station_code=sid[:64],
                    name=str(station.get("name") or sid)[:128],
                    seq=seq,
                    lng=float(station["lng"]),
                    lat=float(station["lat"]),
                    coord_system="GCJ02",
                )
            )
    if keys:
        await db.execute(
            delete(TransitLine).where(
                TransitLine.city_code == city_code,
                TransitLine.line_key.not_in(keys),
            )
        )
    await db.commit()
    log.info("transit_catalog_synced", city=city_code, lines=len(keys))
    return await read_catalog(db, city_code=city_code)


async def read_catalog(db: AsyncSession, city_code: str = "sz") -> dict:
    lines = (
        (
            await db.execute(
                select(TransitLine)
                .where(TransitLine.city_code == city_code)
                .order_by(TransitLine.line_code)
            )
        )
        .scalars()
        .all()
    )
    if not lines:
        return {"lines": [], "station_count": 0, "updated_at": None}
    keys = [line.line_key for line in lines]
    stations = (
        (
            await db.execute(
                select(TransitStation)
                .where(TransitStation.line_key.in_(keys))
                .order_by(TransitStation.line_key, TransitStation.seq)
            )
        )
        .scalars()
        .all()
    )
    grouped: dict[str, list[dict]] = {key: [] for key in keys}
    for station in stations:
        grouped[station.line_key].append(
            {
                "sid": station.station_code,
                "name": station.name,
                "lng": station.lng,
                "lat": station.lat,
            }
        )
    updated = max((line.updated_at for line in lines if line.updated_at), default=None)
    if updated is not None and updated.tzinfo is None:
        updated = updated.replace(tzinfo=UTC)
    return {
        "lines": [
            {
                "id": line.line_code,
                "name": line.name,
                "color": line.color,
                "stations": grouped.get(line.line_key, []),
            }
            for line in lines
        ],
        "station_count": sum(len(items) for items in grouped.values()),
        "updated_at": updated.isoformat() if updated else None,
    }


async def ensure_catalog(db: AsyncSession, city_code: str = "sz") -> dict:
    """Read the DB cache; refresh from SZMC when empty or older than 24h."""
    current = await read_catalog(db, city_code=city_code)
    age_ok = False
    if current.get("updated_at"):
        try:
            age_ok = datetime.now(UTC) - datetime.fromisoformat(
                current["updated_at"]
            ) < CACHE_TTL
        except ValueError:
            age_ok = False
    if current["lines"] and age_ok:
        return current
    try:
        provider = await provider_runtime.ensure_enabled(db, "szmc")
        catalog = await provider.station_catalog()
        return await sync_catalog(db, catalog, city_code=city_code)
    except Exception as exc:
        await db.rollback()
        if current["lines"]:
            log.warning("transit_catalog_refresh_failed", error=str(exc)[:200])
            return {**current, "stale": True}
        raise


async def last_synced(db: AsyncSession, city_code: str = "sz") -> datetime | None:
    return await db.scalar(
        select(func.max(TransitLine.updated_at)).where(
            TransitLine.city_code == city_code
        )
    )
