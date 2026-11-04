import math
import time

import httpx

from app.integrations.base import (
    BaseProvider,
    Capability,
    ProviderDomain,
    ProviderMeta,
    ProviderTestResult,
    ProviderUnavailable,
    QuotaPolicy,
)

STATION_URL = "https://www.szmc.net/styles/index/sz-subway/mcdata/shentie.json"
MIN_TIME_URL = "https://www.szmc.net/algorithm/Ticketing/MinTimeJson.do"
STATION_CACHE_SECONDS = 24 * 3600
MAX_WALK_METERS = 3000
WALK_METERS_PER_MINUTE = 80.0


def parse_lonlat(value: str) -> tuple[float, float]:
    try:
        lng, lat = (float(item) for item in value.split(",", 1))
    except ValueError as exc:
        raise ProviderUnavailable(f"坐标格式错误：{value}") from exc
    return lng, lat


def haversine_m(lng1: float, lat1: float, lng2: float, lat2: float) -> float:
    radius = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * radius * math.asin(math.sqrt(a))


def build_station_index(payload: dict) -> dict[str, dict]:
    index: dict[str, dict] = {}
    for line in payload.get("l") or []:
        for station in line.get("st") or []:
            sid = str(station.get("sid") or "")
            name = str(station.get("n") or "")
            value = str(station.get("sl") or "")
            code = str(station.get("poiid") or "")
            if not sid or not name or "," not in value or not code:
                continue
            try:
                lng, lat = (float(item) for item in value.split(",", 1))
            except ValueError:
                continue
            item = index.setdefault(
                sid, {"sid": sid, "name": name, "lng": lng, "lat": lat, "codes": []}
            )
            if code not in item["codes"]:
                item["codes"].append(code)
    return index


def nearest_station(
    index: dict[str, dict], lng: float, lat: float
) -> tuple[dict, float] | None:
    best: tuple[dict, float] | None = None
    for station in index.values():
        distance = haversine_m(lng, lat, station["lng"], station["lat"])
        if best is None or distance < best[1]:
            best = (station, distance)
    return best


class SzmcProvider(BaseProvider):
    meta = ProviderMeta(
        code="szmc",
        name="深圳地铁官方",
        domain=ProviderDomain.transit,
        capabilities=frozenset({Capability.route_transit, Capability.metro_time}),
        auth="none",
        coord_system="GCJ02",
        description="官方站点字典 + MinTimeJson，地铁+步行估算；零额度",
        docs_url="https://www.szmc.net/",
        quota=QuotaPolicy(period="day", limit=0),
        priority=5,
    )

    _station_index: dict[str, dict] | None = None
    _station_index_at: float = 0.0
    _payload: dict | None = None
    _payload_at: float = 0.0

    async def _load_payload(self) -> dict:
        now = time.monotonic()
        if (
            type(self)._payload is not None
            and now - type(self)._payload_at < STATION_CACHE_SECONDS
        ):
            return type(self)._payload
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(STATION_URL)
        except httpx.HTTPError as exc:
            raise ProviderUnavailable(
                f"深圳地铁站点字典请求失败：{type(exc).__name__}"
            ) from exc
        if response.status_code >= 400:
            raise ProviderUnavailable(f"深圳地铁站点字典 HTTP {response.status_code}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderUnavailable("深圳地铁站点字典返回非 JSON") from exc
        index = build_station_index(payload)
        if not index:
            raise ProviderUnavailable("深圳地铁站点字典为空")
        type(self)._payload = payload
        type(self)._payload_at = now
        type(self)._station_index = index
        type(self)._station_index_at = now
        return payload

    async def _stations(self) -> dict[str, dict]:
        await self._load_payload()
        return type(self)._station_index or {}

    async def station_catalog(self) -> dict:
        """Return metro lines/stations for the map layer (cached 24h)."""
        payload = await self._load_payload()
        lines = []
        station_count = 0
        for line in payload.get("l") or []:
            points = []
            for station in line.get("st") or []:
                sid = str(station.get("sid") or "")
                name = str(station.get("n") or "")
                value = str(station.get("sl") or "")
                if not sid or not name or "," not in value:
                    continue
                try:
                    lng, lat = (float(item) for item in value.split(",", 1))
                except ValueError:
                    continue
                points.append(
                    {"sid": sid, "name": name, "lng": lng, "lat": lat}
                )
            if not points:
                continue
            station_count += len(points)
            lines.append(
                {
                    "id": str(line.get("ln") or line.get("ls") or ""),
                    "name": str(line.get("kn") or line.get("ln") or "地铁"),
                    "color": str(line.get("cl") or "#2f7d5b"),
                    "stations": points,
                }
            )
        return {"lines": lines, "station_count": station_count}

    async def _min_time(self, departure: str, arrival: str) -> dict:
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.post(
                    MIN_TIME_URL,
                    data={
                        "departureStation": departure,
                        "arriveStation": arrival,
                        "ridingType": "0",
                    },
                )
        except httpx.HTTPError as exc:
            raise ProviderUnavailable(
                f"深圳地铁耗时接口失败：{type(exc).__name__}"
            ) from exc
        if response.status_code >= 400:
            raise ProviderUnavailable(f"深圳地铁耗时接口 HTTP {response.status_code}")
        try:
            data = response.json()
        except ValueError as exc:
            raise ProviderUnavailable("深圳地铁耗时接口返回非 JSON") from exc
        if not data.get("useTime"):
            raise ProviderUnavailable(f"深圳地铁未返回路线：{str(data)[:200]}")
        return data

    async def transit(
        self, origin: str, destination: str, city: str = "0755"
    ) -> dict | None:
        origin_lng, origin_lat = parse_lonlat(origin)
        dest_lng, dest_lat = parse_lonlat(destination)
        index = await self._stations()
        origin_match = nearest_station(index, origin_lng, origin_lat)
        dest_match = nearest_station(index, dest_lng, dest_lat)
        if origin_match is None or dest_match is None:
            return None
        origin_station, origin_walk_m = origin_match
        dest_station, dest_walk_m = dest_match
        if origin_walk_m > MAX_WALK_METERS or dest_walk_m > MAX_WALK_METERS:
            return None
        walk_minutes = (origin_walk_m + dest_walk_m) / WALK_METERS_PER_MINUTE
        if origin_station["sid"] == dest_station["sid"]:
            return {
                "duration_s": int(round(walk_minutes * 60)),
                "distance_m": int(round(origin_walk_m + dest_walk_m)),
                "transfers": 0,
                "provider": "szmc",
                "mode": "metro",
                "walk_min": round(walk_minutes, 1),
                "raw": {
                    "origin_station": origin_station["name"],
                    "destination_station": dest_station["name"],
                },
            }
        data = await self._min_time(origin_station["codes"][0], dest_station["codes"][0])
        use_time = int(data.get("useTime") or 0)
        lines = [
            item
            for item in (data.get("lineList") or [])
            if item.get("line") and item.get("line") != "xx"
        ]
        try:
            transfers = int(data.get("times") or max(0, len(lines) - 1))
        except (TypeError, ValueError):
            transfers = max(0, len(lines) - 1)
        return {
            "duration_s": use_time + int(round(walk_minutes * 60)),
            "distance_m": int(round(origin_walk_m + dest_walk_m)),
            "transfers": transfers,
            "provider": "szmc",
            "mode": "metro",
            "walk_min": round(walk_minutes, 1),
            "raw": {
                "origin_station": origin_station["name"],
                "destination_station": dest_station["name"],
                "metro_seconds": use_time,
                "ticket_price": data.get("ticketPrice") or data.get("adultSZT"),
                "lines": [
                    {
                        "line": item.get("line"),
                        "name": item.get("lineName"),
                        "from": item.get("departureStation"),
                        "to": item.get("arriveStation"),
                    }
                    for item in lines
                ],
            },
        }

    async def test(self) -> ProviderTestResult:
        started = time.monotonic()
        result = await self.transit("114.030298,22.610496", "114.061101,22.534769")
        latency = int((time.monotonic() - started) * 1000)
        if result is None:
            return ProviderTestResult(ok=False, message="未计算到路线", latency_ms=latency)
        raw = result.get("raw") or {}
        message = (
            f"{raw.get('origin_station')} → {raw.get('destination_station')} "
            f"{result['duration_s'] / 60:.0f} 分钟"
        )
        return ProviderTestResult(
            ok=True,
            message=message,
            latency_ms=latency,
            quota_units=1,
        )
