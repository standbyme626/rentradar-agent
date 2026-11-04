import json
import time
from typing import Any

import httpx

from app.core.config import settings
from app.geo.coords import cgcs2000_to_gcj02, gcj02_to_cgcs2000
from app.integrations.base import (
    BaseProvider,
    Capability,
    ProviderAuthError,
    ProviderDomain,
    ProviderMeta,
    ProviderTestResult,
    ProviderUnavailable,
    QuotaPolicy,
)

GEOCODER_URL = "http://api.tianditu.gov.cn/geocoder"
SEARCH_URL = "http://api.tianditu.gov.cn/v2/search"
TILE_URL = "https://t{s}.tianditu.gov.cn/{layer}_w/wmts"
TILE_LAYERS = {"vec", "img", "ter", "cva", "cia", "cta"}


def keyword_for_types(types: str) -> str:
    if "050600" in types:
        return "夜宵"
    if types.startswith("060"):
        return "便利店"
    return "餐饮"


class TiandituProvider(BaseProvider):
    meta = ProviderMeta(
        code="tianditu",
        name="天地图",
        domain=ProviderDomain.maps,
        capabilities=frozenset(
            {
                Capability.geocode,
                Capability.poi_search,
                Capability.reverse_geocode,
                Capability.map_tile,
            }
        ),
        auth="api_key",
        coord_system="CGCS2000",
        description="CGCS2000 坐标系；地理编码/POI 可用；服务端请求固定走 10943 白名单出口",
        docs_url="http://lbs.tianditu.gov.cn/",
        quota=QuotaPolicy(period="day", limit=10000),
        proxy=settings.tianditu_proxy or None,
        priority=20,
    )

    def __init__(self) -> None:
        self.configured = bool(settings.tianditu_api_key)

    async def _request(self, url: str, params: dict[str, Any]) -> dict:
        if not self.configured:
            raise ProviderAuthError("未配置 TIANDITU_API_KEY")
        query = {**params, "tk": settings.tianditu_api_key}
        try:
            async with httpx.AsyncClient(
                timeout=20.0,
                follow_redirects=True,
                proxy=settings.tianditu_proxy or None,
            ) as client:
                response = await client.get(url, params=query)
        except httpx.HTTPError as exc:
            raise ProviderUnavailable(f"天地图请求失败：{type(exc).__name__}") from exc
        if response.status_code in (401, 403):
            raise ProviderAuthError("天地图拒绝访问：IP 白名单不匹配，请确认使用 10943")
        if response.status_code >= 400:
            raise ProviderUnavailable(f"天地图 HTTP {response.status_code}")
        try:
            data = response.json()
        except ValueError as exc:
            raise ProviderUnavailable("天地图返回非 JSON") from exc
        status = data.get("status")
        if isinstance(status, dict):
            if int(status.get("infocode") or 0) != 1000:
                raise ProviderUnavailable(f"天地图错误：{status.get('cndesc') or status}")
        elif str(data.get("msg")) != "ok":
            raise ProviderUnavailable(f"天地图错误：{data.get('msg')}")
        return data

    async def _get(self, params: dict[str, Any]) -> dict:
        return await self._request(GEOCODER_URL, params)

    @staticmethod
    def _location(data: dict) -> tuple[float, float] | None:
        location = data.get("location")
        if not isinstance(location, dict):
            return None
        try:
            lng = float(location["lon"])
            lat = float(location["lat"])
        except (KeyError, TypeError, ValueError):
            return None
        return cgcs2000_to_gcj02(lng, lat)

    async def geocode(self, address: str, city: str = "深圳") -> dict | None:
        keyword = address if city in address else f"{address} {city}".strip()
        data = await self._get(
            {"ds": json.dumps({"keyWord": keyword}, ensure_ascii=False)}
        )
        coords = self._location(data)
        if coords is None:
            return None
        location = data.get("location") or {}
        return {
            "lng": coords[0],
            "lat": coords[1],
            "level": location.get("level"),
            "adcode": None,
            "formatted_address": address,
        }

    async def search_poi(
        self, keywords: str, city: str = "深圳", types: str = "120000"
    ) -> dict | None:
        result = await self.geocode(keywords, city)
        if result is None:
            return None
        return {
            "name": keywords,
            "address": result["formatted_address"],
            "lng": result["lng"],
            "lat": result["lat"],
            "adcode": result.get("adcode"),
        }

    async def around_count(self, location: str, types: str, radius: int = 1000) -> int:
        try:
            lng, lat = (float(item) for item in location.split(",", 1))
        except ValueError as exc:
            raise ProviderUnavailable(f"天地图坐标格式错误：{location}") from exc
        cgcs_lng, cgcs_lat = gcj02_to_cgcs2000(lng, lat)
        post_str = {
            "keyWord": keyword_for_types(types),
            "queryRadius": max(1, int(radius)),
            "queryType": 3,
            "pointLonlat": f"{cgcs_lng},{cgcs_lat}",
            "start": 0,
            "count": 1,
        }
        data = await self._request(
            SEARCH_URL,
            {"postStr": json.dumps(post_str, ensure_ascii=False), "type": "query"},
        )
        try:
            return int(data.get("count") or 0)
        except (TypeError, ValueError):
            return 0

    async def reverse_geocode(self, lng: float, lat: float) -> dict:
        payload = json.dumps({"lon": lng, "lat": lat, "ver": 1})
        data = await self._get({"postStr": payload, "type": "geocode"})
        result = data.get("result")
        if isinstance(result, dict):
            return result
        return {"raw": result}

    async def reverse_geocode_gcj02(self, lng: float, lat: float) -> dict:
        cgcs_lng, cgcs_lat = gcj02_to_cgcs2000(lng, lat)
        return await self.reverse_geocode(cgcs_lng, cgcs_lat)

    async def fetch_tile(self, layer: str, z: int, x: int, y: int) -> dict:
        if layer not in TILE_LAYERS:
            raise ProviderUnavailable(f"不支持的天地图图层：{layer}")
        if not self.configured:
            raise ProviderAuthError("未配置 TIANDITU_API_KEY")
        subdomain = (int(x) + int(y)) % 8
        params = {
            "SERVICE": "WMTS",
            "REQUEST": "GetTile",
            "VERSION": "1.0.0",
            "LAYER": layer,
            "STYLE": "default",
            "TILEMATRIXSET": "w",
            "FORMAT": "tiles",
            "TILECOL": str(int(x)),
            "TILEROW": str(int(y)),
            "TILEMATRIX": str(int(z)),
            "tk": settings.tianditu_api_key,
        }
        try:
            async with httpx.AsyncClient(
                timeout=20.0,
                follow_redirects=True,
                proxy=settings.tianditu_proxy or None,
            ) as client:
                response = await client.get(
                    TILE_URL.format(s=subdomain, layer=layer), params=params
                )
        except httpx.HTTPError as exc:
            raise ProviderUnavailable(f"天地图瓦片请求失败：{type(exc).__name__}") from exc
        if response.status_code in (401, 403):
            raise ProviderAuthError("天地图拒绝瓦片请求：Key/IP 白名单不匹配")
        if response.status_code >= 400:
            raise ProviderUnavailable(f"天地图瓦片 HTTP {response.status_code}")
        content_type = (response.headers.get("content-type") or "").split(";")[0]
        if not content_type.startswith("image/"):
            raise ProviderUnavailable(f"天地图瓦片返回非图片：{content_type or 'unknown'}")
        if len(response.content) < 64:
            raise ProviderUnavailable("天地图瓦片为空")
        return {"content": response.content, "content_type": content_type}

    async def test(self) -> ProviderTestResult:
        started = time.monotonic()
        result = await self.geocode("深圳会展中心")
        latency = int((time.monotonic() - started) * 1000)
        if result is None:
            return ProviderTestResult(ok=False, message="地理编码无结果", latency_ms=latency)
        return ProviderTestResult(
            ok=True,
            message=(
                f"地理编码成功：{result['formatted_address']} "
                f"({result['lng']:.5f},{result['lat']:.5f})"
            ),
            latency_ms=latency,
            quota_units=1,
        )
