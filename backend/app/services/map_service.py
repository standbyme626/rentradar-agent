"""Real map data and Tianditu WMTS tile cache (P1/W7).

Listings are stored in GCJ-02; Tianditu's WMTS matrix set ``w`` is Web
Mercator over CGCS2000/WGS-84.  Plotting GCJ-02 coordinates directly would
shift every marker by roughly 500 m, so the map payload converts to WGS-84 and
the frontend receives a single, explicit ``wgs84`` coordinate system.

Tiles are fetched server-side through the same 10943 egress as geocoding, so
the key never reaches the browser, and cached on disk for
``APP_MAP_TILE_TTL_DAYS``.  The endpoint is authenticated by the existing
access cookie; the frontend only requests tiles after login.
"""

import math
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from statistics import mean, median

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.geo.coords import gcj02_to_wgs84
from app.integrations.base import Capability, ProviderError
from app.models import Community, Listing, ListingStatus
from app.services import commute_service, provider_runtime
from app.services.settings_service import get_commute_destination

log = get_logger("maps")

TILE_LAYERS = {"vec", "img", "ter", "cva", "cia", "cta"}
LABEL_LAYERS = {"cva", "cia", "cta"}
MAX_COMMUNITIES = 800
MIN_ZOOM = 3
MAX_ZOOM = 18


def _tile_dir(layer: str, z: int, x: int, y: int) -> Path:
    return Path(settings.map_tile_cache_dir) / layer / str(z) / str(x) / f"{y}.png"


def validate_tile(layer: str, z: int, x: int, y: int) -> None:
    if layer not in TILE_LAYERS:
        raise HTTPException(status_code=404, detail="unknown tile layer")
    if not (MIN_ZOOM <= z <= MAX_ZOOM):
        raise HTTPException(status_code=404, detail="zoom out of range")
    limit = 1 << z
    if not (0 <= x < limit and 0 <= y < limit):
        raise HTTPException(status_code=404, detail="tile out of range")


def _content_type(data: bytes) -> str:
    if data.startswith(b"\x89PNG"):
        return "image/png"
    if data.startswith(b"\xff\xd8"):
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/png"


def _fresh(path: Path) -> bool:
    if not path.is_file():
        return False
    age = datetime.now(UTC) - datetime.fromtimestamp(path.stat().st_mtime, UTC)
    return age < timedelta(days=max(1, settings.map_tile_ttl_days))


async def get_tile(
    db: AsyncSession, layer: str, z: int, x: int, y: int
) -> tuple[bytes, str, str]:
    """Return (content, content_type, cache_state); ``hit`` skips provider calls."""
    validate_tile(layer, z, x, y)
    path = _tile_dir(layer, z, x, y)
    if _fresh(path):
        data = path.read_bytes()
        return data, _content_type(data), "hit"
    if not settings.tianditu_api_key:
        raise HTTPException(status_code=503, detail="未配置 TIANDITU_API_KEY")
    try:
        result = await provider_runtime.invoke(
            db,
            Capability.map_tile,
            "fetch_tile",
            layer,
            z,
            x,
            y,
            units=1,
        )
    except ProviderError as exc:
        log.warning("tile_fetch_failed", layer=layer, z=z, x=x, y=y, error=str(exc)[:200])
        raise HTTPException(status_code=502, detail="天地图瓦片不可用") from exc
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_bytes(result["content"])
    tmp.replace(path)
    return result["content"], result.get("content_type") or "image/png", "miss"


async def communities(
    db: AsyncSession,
    *,
    limit: int = MAX_COMMUNITIES,
    max_commute: float | None = None,
) -> dict:
    rows = (
        (
            await db.execute(
                select(Community)
                .where(Community.lng.is_not(None), Community.lat.is_not(None))
                .order_by(Community.id)
                .limit(max(1, min(limit, MAX_COMMUNITIES)))
            )
        )
        .scalars()
        .all()
    )
    listings = (
        (
            await db.execute(
                select(Listing)
                .where(
                    Listing.status == ListingStatus.active,
                    Listing.community_id.is_not(None),
                    Listing.score.is_not(None),
                )
                .order_by(Listing.score.desc().nullslast(), Listing.id.desc())
            )
        )
        .scalars()
        .all()
    )
    grouped: dict[int, list[Listing]] = {}
    for listing in listings:
        grouped.setdefault(listing.community_id, []).append(listing)
    destination = await get_commute_destination(db)
    key = None
    if destination:
        from app.services.settings_service import destination_key

        key = destination_key(destination)
    commute = (
        await commute_service.bulk_stats(db, key, destination=destination)
        if key
        else {}
    )
    features = []
    for community in rows:
        community_listings = grouped.get(community.id) or []
        if not community_listings:
            continue
        rents = [item.rent for item in community_listings if item.rent]
        scores = [item.score for item in community_listings if item.score is not None]
        stats = commute.get(community.id)
        p50 = stats["p50_min"] if stats else None
        if max_commute is not None and (p50 is None or p50 > max_commute):
            continue
        lng, lat = gcj02_to_wgs84(float(community.lng), float(community.lat))
        sample = community_listings[0]
        features.append(
            {
                "id": community.id,
                "name": community.name,
                "district": community.district,
                "lng": round(lng, 6),
                "lat": round(lat, 6),
                "coord_system": "wgs84",
                "listings": len(community_listings),
                "min_rent": min(rents) if rents else None,
                "median_rent": round(median(rents)) if rents else None,
                "avg_score": round(mean(scores), 1) if scores else None,
                "commute_p50": p50,
                "commute_p90": stats["p90_min"] if stats else None,
                "commute_buckets": stats["bucket_count"] if stats else 0,
                "commute_static": stats["static"] if stats else None,
                "sample_listing": {
                    "id": sample.id,
                    "title": sample.title,
                    "rent": sample.rent,
                    "score": sample.score,
                    "image_url": sample.image_url,
                    "url": sample.url,
                },
            }
        )
    if features:
        center = (
            round(mean(item["lng"] for item in features), 6),
            round(mean(item["lat"] for item in features), 6),
        )
    else:
        center = (114.0579, 22.5431)
    return {
        "communities": features,
        "center": list(center),
        "coord_system": "wgs84",
        "tiles": {
            "enabled": bool(settings.tianditu_api_key),
            "layers": ["vec", "cva"],
            "attribution": "© 天地图",
            "max_zoom": MAX_ZOOM,
            "cache_days": settings.map_tile_ttl_days,
        },
        "stats": {
            "communities": len(features),
            "listings": sum(item["listings"] for item in features),
            "with_commute": sum(1 for item in features if item["commute_p50"] is not None),
        },
    }


def tile_cache_stats() -> dict:
    root = Path(settings.map_tile_cache_dir)
    if not root.is_dir():
        return {"tiles": 0, "bytes": 0, "dir": str(root)}
    files = list(root.rglob("*.png"))
    return {
        "tiles": len(files),
        "bytes": sum(item.stat().st_size for item in files),
        "dir": str(root),
    }


def _mercator(lng: float, lat: float) -> tuple[float, float]:
    """Web Mercator normalised coordinates; used by tests and debugging."""
    x = (lng + 180.0) / 360.0
    sin_lat = math.sin(math.radians(lat))
    y = 0.5 - math.log((1 + sin_lat) / (1 - sin_lat)) / (4 * math.pi)
    return x, y
