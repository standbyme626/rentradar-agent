import asyncio
import random
import re
import time

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.sources.base import CaptchaRequiredError, EmptyPageError, ListingDraft, SourceError

log = get_logger("beike_api")
PROXY_COOLDOWN_SECONDS = 300

API_URL = "https://app.api.ke.com/Rentplat/v2/house/list"
CITY_IDS = {"sz": "440300"}
SORT_CONDITIONS = {"newest": "rco11"}
MAX_OFFSET = 2999
MAX_LIMIT = 30
IMAGE_SIZE_RE = re.compile(r"\.\d+x\d+\.jpg$")

# 贝壳楼层编码：1 高、2 中、3 低（用 CDP 抓到的同一房源交叉校验过）
FLOOR_LEVELS = {
    "200500000001": "高楼层",
    "200500000002": "中楼层",
    "200500000003": "低楼层",
}
TAG_ALIASES = {
    "has_elevator": "电梯",
    "decoration": "精装",
    "is_subway_house": "近地铁",
    "deposit_1_pay_1": "押一付一",
    "no_agency_fee": "免中介费",
    "raise_pet": "可养宠物",
    "first_rent": "首次出租",
    "is_key": "钥匙房",
}
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148"
    ),
    "Accept": "application/json",
    "Referer": "https://m.ke.com/",
}
CAPTCHA_MARKERS = ("验证", "captcha", "访问异常", "antibot")


def parse_proxies(value: str | list[str] | None) -> list[str]:
    """Parse a comma-separated proxy list, preserving order and de-duplicating."""
    if value is None:
        return []
    items = value if isinstance(value, list) else str(value).split(",")
    result: list[str] = []
    for item in items:
        text = str(item).strip()
        if text and text not in result:
            result.append(text)
    return result


def build_condition(line: str = "", sort: str = "newest") -> str:
    parts = [line.strip("/")] if line else []
    sort_condition = SORT_CONDITIONS.get(sort)
    if sort_condition:
        parts.append(sort_condition)
    return "/".join(parts)


def max_pages(limit: int = MAX_LIMIT) -> int:
    limit = max(1, min(limit, MAX_LIMIT))
    return MAX_OFFSET // limit + 1


def build_api_params(
    city_code: str,
    page: int,
    *,
    limit: int = MAX_LIMIT,
    condition: str = "",
    feed_query_id: str = "",
) -> dict:
    city_id = CITY_IDS.get(city_code)
    if city_id is None:
        raise SourceError(f"beike app api has no city_id for {city_code}")
    limit = max(1, min(limit, MAX_LIMIT))
    offset = (max(1, page) - 1) * limit
    if offset > MAX_OFFSET:
        raise SourceError(f"beike app api offset {offset} exceeds {MAX_OFFSET}")
    return {
        "city_id": city_id,
        "condition": condition,
        "offset": offset,
        "limit": limit,
        "scene": "list",
        "from": "default_list",
        "page_uicode": "matrix_homepage",
        "feed_query_id": feed_query_id,
    }


def _parse_coord(value) -> tuple[float | None, float | None]:
    if not value:
        return None, None
    if isinstance(value, str):
        parts = value.split(",")
    elif isinstance(value, (list, tuple)):
        parts = value
    else:
        return None, None
    if len(parts) < 2:
        return None, None
    try:
        lat, lng = float(parts[0]), float(parts[1])
    except (TypeError, ValueError):
        return None, None
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return None, None
    return lat, lng


def _float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _image_url(house: dict) -> str | None:
    url = str(house.get("list_picture") or "").strip()
    if not url:
        raw = str(house.get("list_picture_raw") or "").strip()
        if raw.startswith("/"):
            url = f"https://image1.ljcdn.com{raw}"
        else:
            url = raw
    if not url.startswith("http"):
        return None
    return IMAGE_SIZE_RE.sub(".800x600.jpg", url)


def _normalized_tags(house: dict) -> list[str]:
    tags: list[str] = []
    for tag in house.get("house_tags") or []:
        if not isinstance(tag, dict):
            continue
        value = TAG_ALIASES.get(tag.get("key")) or str(tag.get("name") or "").strip()
        if value and value not in tags:
            tags.append(value)
    return tags


def parse_house(house: dict, city_code: str = "sz") -> ListingDraft | None:
    code = str(house.get("house_code") or "").strip()
    if not code:
        return None
    pc_url = str(house.get("pc_url") or "").strip()
    m_url = str(house.get("m_url") or "").strip()
    url = pc_url or m_url or f"https://{city_code}.zu.ke.com/zufang/{code}.html"
    title = " ".join(str(house.get("house_title") or house.get("app_house_title") or "").split())
    layout = str(house.get("layout") or "").strip() or None
    lat, lng = _parse_coord(house.get("geolatitudelongitude"))
    latest_price_change = house.get("latest_price_change")
    agent_type = (
        "apartment"
        if house.get("apartment_type")
        or "/apartment/" in pc_url
        or title.startswith("独栋·")
        else "unknown"
    )
    return ListingDraft(
        source_listing_id=code,
        url=url,
        title=title,
        community_name=str(house.get("resblock_name") or "").strip() or None,
        district=str(house.get("district_name") or "").strip() or None,
        layout=layout,
        area=_float(house.get("rent_area")),
        orientation=str(house.get("frame_orientation") or "").strip() or None,
        floor=FLOOR_LEVELS.get(str(house.get("floor_level"))),
        rent=_int(house.get("rent_price_listing") or house.get("rent_price")),
        tags=_normalized_tags(house),
        image_url=_image_url(house),
        agent_type=agent_type,
        raw={
            "source": "api_v2",
            "resblock_id": house.get("resblock_id"),
            "bizcircle_name": house.get("bizcircle_name"),
            "subway_distance": house.get("subway_distance"),
            "rent_type": house.get("rent_type"),
            "house_status": house.get("house_status"),
            "app_plat_ctime": house.get("app_plat_ctime"),
            "available_rent_time": house.get("availableRentTime"),
            "latest_price_change": latest_price_change,
            "floor_level": house.get("floor_level"),
            "floor_total": house.get("floor_total"),
            "house_tags_str": house.get("house_tags_str"),
            "app_source_brand_name": house.get("app_source_brand_name"),
            "desc": house.get("desc"),
            "sub_desc": house.get("sub_desc"),
            "pc_url": pc_url or None,
            "m_url": m_url or None,
            "lat": lat,
            "lng": lng,
        },
    )


def parse_list_payload(payload: dict, city_code: str = "sz") -> tuple[list[ListingDraft], int]:
    status = payload.get("status")
    if status not in (0, "0", None):
        message = str(payload.get("msg") or "")
        if any(marker in message.lower() for marker in CAPTCHA_MARKERS):
            raise CaptchaRequiredError(f"beike app api verification: {message}")
        raise SourceError(f"beike app api error: {message or status}")
    data = payload.get("data")
    if not isinstance(data, dict) or "list" not in data:
        raise EmptyPageError("beike app api returned no data.list")
    items = data.get("list") or []
    drafts = [draft for item in items if (draft := parse_house(item, city_code)) is not None]
    total = _int(data.get("total")) or 0
    return drafts, total


class BeikeAPIFetcher:
    def __init__(
        self,
        city_code: str = "sz",
        *,
        timeout: float = 20.0,
        retries: int = 2,
        page_interval: tuple[float, float] = (1.5, 3.0),
        transport: httpx.AsyncBaseTransport | None = None,
        proxies: str | list[str] | None = None,
    ) -> None:
        self.city_code = city_code
        self.retries = retries
        self.page_interval = page_interval
        self._last_fetch = 0.0
        self._feed_query_id = ""
        self._cooldown: dict[int, float] = {}
        if transport is not None:
            self._clients = [
                httpx.AsyncClient(
                    timeout=timeout,
                    headers=HEADERS,
                    transport=transport,
                    follow_redirects=True,
                )
            ]
        else:
            configured = parse_proxies(proxies) if proxies is not None else parse_proxies(
                settings.beike_proxies
            )
            self._clients = []
            for index, proxy in enumerate(configured):
                try:
                    self._clients.append(
                        httpx.AsyncClient(
                            timeout=timeout,
                            headers=HEADERS,
                            proxy=proxy,
                            follow_redirects=True,
                        )
                    )
                except Exception as exc:
                    log.warning(
                        "beike_proxy_invalid",
                        index=index,
                        error=f"{type(exc).__name__}: {exc}"[:160],
                    )
            if not self._clients:
                self._clients = [
                    httpx.AsyncClient(
                        timeout=timeout, headers=HEADERS, follow_redirects=True
                    )
                ]
        self._cursor = 0

    async def close(self) -> None:
        for client in self._clients:
            await client.aclose()

    def reset_condition(self) -> None:
        """Forget the page cursor before switching to another list condition."""
        self._feed_query_id = ""

    async def _pace(self) -> None:
        if not self._last_fetch:
            return
        wait = random.uniform(*self.page_interval) - (time.monotonic() - self._last_fetch)
        if wait > 0:
            await asyncio.sleep(wait)

    def _pick_client(self) -> tuple[int, httpx.AsyncClient]:
        now = time.monotonic()
        count = len(self._clients)
        for _ in range(count):
            index = self._cursor % count
            self._cursor += 1
            until = self._cooldown.get(index, 0)
            if until <= now:
                return index, self._clients[index]
        wait = min(self._cooldown.values()) - now if self._cooldown else 0
        raise SourceError(f"beike proxy pool cooling ({max(0, wait):.0f}s)")

    def _cool(self, index: int) -> None:
        self._cooldown[index] = time.monotonic() + PROXY_COOLDOWN_SECONDS
        log.warning("beike_proxy_cooling", index=index)

    async def _get(self, params: dict) -> dict:
        last_error: object = None
        attempts = max(self.retries + 1, len(self._clients) * 2)
        for attempt in range(attempts):
            try:
                index, client = self._pick_client()
            except SourceError as exc:
                last_error = exc
                break
            try:
                response = await client.get(API_URL, params=params)
            except httpx.HTTPError as exc:
                last_error = exc
                self._cool(index)
            else:
                if response.status_code in (403, 412):
                    if len(self._clients) == 1:
                        raise CaptchaRequiredError(
                            f"beike app api http {response.status_code}; "
                            "use CDP after manual verification"
                        )
                    self._cool(index)
                    last_error = SourceError(
                        f"beike app api http {response.status_code} via proxy {index}"
                    )
                    continue
                if response.status_code == 429 or response.status_code >= 500:
                    self._cool(index)
                    last_error = SourceError(
                        f"beike app api http {response.status_code} via proxy {index}"
                    )
                elif response.status_code >= 400:
                    raise SourceError(f"beike app api http {response.status_code}")
                else:
                    text = response.text
                    if not text.lstrip().startswith("{"):
                        if any(marker in text.lower() for marker in CAPTCHA_MARKERS):
                            raise CaptchaRequiredError(
                                "beike app api returned a verification page"
                            )
                        raise SourceError(
                            f"beike app api returned non-JSON: {text[:120].strip()!r}"
                        )
                    try:
                        return response.json()
                    except ValueError as exc:
                        raise SourceError("beike app api returned invalid JSON") from exc
            if attempt < attempts - 1:
                await asyncio.sleep(2 * (attempt + 1) + random.random())
        if isinstance(last_error, SourceError) and "cooling" in str(last_error):
            raise last_error
        raise SourceError(f"beike app api request failed: {last_error}")

    async def fetch_page(
        self,
        page: int,
        *,
        line: str = "",
        sort: str = "newest",
        limit: int = MAX_LIMIT,
    ) -> tuple[list[ListingDraft], int]:
        condition = build_condition(line=line, sort=sort)
        params = build_api_params(
            self.city_code,
            page,
            limit=limit,
            condition=condition,
            feed_query_id=self._feed_query_id,
        )
        await self._pace()
        payload = await self._get(params)
        self._last_fetch = time.monotonic()
        data = payload.get("data") or {}
        feed_query_id = str(data.get("feed_query_id") or "")
        if feed_query_id:
            self._feed_query_id = feed_query_id
        return parse_list_payload(payload, self.city_code)
