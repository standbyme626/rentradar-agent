from typing import Any

import httpx

from app.core.config import settings

BASE = "https://restapi.amap.com"


class AmapError(Exception):
    pass


async def _get(path: str, params: dict[str, Any]) -> dict:
    if not settings.amap_web_key:
        raise AmapError("AMAP_WEB_KEY is not configured")
    query = {**params, "key": settings.amap_web_key}
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(f"{BASE}{path}", params=query)
        response.raise_for_status()
        data = response.json()
    if str(data.get("status")) != "1":
        raise AmapError(f"{data.get('info')} ({data.get('infocode')})")
    return data


async def geocode(address: str, city: str = "深圳") -> dict | None:
    data = await _get("/v3/geocode/geo", {"address": address, "city": city})
    geocodes = data.get("geocodes") or []
    if not geocodes:
        return None
    item = geocodes[0]
    location = str(item.get("location") or "")
    if "," not in location:
        return None
    lng, lat = location.split(",", 1)
    return {
        "lng": float(lng),
        "lat": float(lat),
        "level": item.get("level"),
        "adcode": item.get("adcode"),
        "formatted_address": item.get("formatted_address"),
    }


async def search_poi(keywords: str, city: str = "深圳", types: str = "120000") -> dict | None:
    data = await _get(
        "/v3/place/text",
        {
            "keywords": keywords,
            "city": city,
            "types": types,
            "offset": 10,
            "page": 1,
            "extensions": "base",
        },
    )
    pois = data.get("pois") or []
    if not pois:
        return None
    item = pois[0]
    location = str(item.get("location") or "")
    if "," not in location:
        return None
    lng, lat = location.split(",", 1)
    return {
        "name": item.get("name"),
        "address": item.get("address"),
        "lng": float(lng),
        "lat": float(lat),
        "adcode": item.get("adcode"),
    }


async def around_count(location: str, types: str, radius: int = 1000) -> int:
    data = await _get(
        "/v3/place/around",
        {
            "location": location,
            "types": types,
            "radius": radius,
            "offset": 1,
            "page": 1,
            "extensions": "base",
        },
    )
    try:
        return int(data.get("count") or 0)
    except (TypeError, ValueError):
        return 0


async def transit(origin: str, destination: str, city: str = "0755") -> dict | None:
    data = await _get(
        "/v3/direction/transit/integrated",
        {
            "origin": origin,
            "destination": destination,
            "city": city,
            "cityd": city,
            "strategy": 0,
        },
    )
    transits = (data.get("route") or {}).get("transits") or []
    if not transits:
        return None
    item = transits[0]
    return {
        "duration_s": int(item.get("duration") or 0),
        "distance_m": int(item.get("distance") or 0),
        "transfers": int(item.get("transfers") or 0),
    }
