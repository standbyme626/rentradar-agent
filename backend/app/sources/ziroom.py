"""Ziroom public list API source (P2/W9).

The list endpoint is public and returns one page of rooms per request.  The
price is exposed as an image plus a digit array (e.g. ``[5, 9, 1, 4]``), so we
rebuild the monthly rent from the digits instead of OCR-ing the PNG.  Request
frequency is intentionally low: the source is disabled until an operator
enables it on the Ops page, and pages sleep between requests.
"""

import asyncio
import io
from typing import Any
from urllib.parse import urlparse

import httpx
from PIL import Image

from app.core.logging import get_logger
from app.sources.base import EmptyPageError, ListingDraft, SourceError

log = get_logger("ziroom")

API_URL = "https://m.ziroom.com/v7/room/list.json"
CITY_CODES = {"sz": "440300", "sh": "310100", "bj": "110000"}
DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SLEEP = 2.0
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148"
    ),
    "Accept": "application/json",
    "Referer": "https://m.ziroom.com/",
}
# Ziroom renders the price digits as a sprite whose glyph order is a random
# permutation per sprite.  The list payload carries glyph indices only.  These
# 64-bit dHash templates were learned from two sprites with known order
# ("1743598026", "8652039147"); unknown sprites are decoded by nearest
# Hamming distance and rejected unless all ten digits are distinct.
GLYPH_TEMPLATES = (
    ("177149e1e1497117", "0"),
    ("7474747570707f78", "1"),
    ("4923061c72497137", "2"),
    ("3771c16e3c717117", "3"),
    ("3032353933263d32", "4"),
    ("3771c96131094343", "5"),
    ("3771c961318d6137", "6"),
    ("0626264d9e183169", "7"),
    ("3771c17133617117", "8"),
    ("13714ef361c97117", "9"),
)
_SPRITE_ORDERS: dict[str, str] = {}


def _hamming(left: str, right: str) -> int:
    try:
        return (int(left, 16) ^ int(right, 16)).bit_count()
    except ValueError:
        return 64


def _glyph_hash(image: Image.Image) -> str:
    gray = image.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
    pixels = list(gray.tobytes())
    bits = 0
    index = 0
    for row in range(8):
        for col in range(8):
            if pixels[row * 9 + col] > pixels[row * 9 + col + 1]:
                bits |= 1 << index
            index += 1
    return f"{bits:016x}"


def sprite_order(image: Image.Image) -> str:
    """Decode a price sprite into its digit order (e.g. ``"1743598026"``)."""
    rgba = image.convert("RGBA")
    rgba = rgba.crop(rgba.getbbox())
    alpha = rgba.split()[3]
    width = rgba.width
    columns = [0] * width
    for x in range(width):
        for y in range(rgba.height):
            if alpha.getpixel((x, y)) > 30:
                columns[x] += 1
    runs: list[tuple[int, int]] = []
    start: int | None = None
    for x, count in enumerate(columns):
        if count and start is None:
            start = x
        if not count and start is not None:
            runs.append((start, x))
            start = None
    if start is not None:
        runs.append((start, width))
    if len(runs) != 10:
        return ""
    labels: list[str] = []
    for left, right in runs:
        glyph = rgba.crop((left, 0, right, rgba.height))
        background = Image.new("L", glyph.size, 255)
        background.paste(glyph.convert("L"), mask=glyph.split()[3])
        digest = _glyph_hash(background)
        best = min(
            GLYPH_TEMPLATES, key=lambda item: _hamming(digest, item[0])
        )
        if _hamming(digest, best[0]) > 3:
            return ""
        labels.append(best[1])
    order = "".join(labels)
    return order if len(set(order)) == 10 else ""


def _sprite_url(room: dict[str, Any]) -> str | None:
    raw = room.get("price")
    if not isinstance(raw, list) or not raw:
        return None
    value = str(raw[0] or "").strip()
    if value.startswith("//"):
        value = f"https:{value}"
    parsed = urlparse(value)
    if parsed.scheme != "https" or not (
        parsed.hostname == "static8.ziroom.com"
        or (parsed.hostname or "").endswith(".ziroom.com")
    ):
        return None
    return value


def _price(room: dict[str, Any], order: str) -> int | None:
    raw = room.get("price")
    if isinstance(raw, (int, float)):
        value = int(raw)
    elif isinstance(raw, list) and len(raw) > 1 and isinstance(raw[1], list):
        try:
            digits = "".join(
                order[int(item)] for item in raw[1] if str(item).isdigit()
            )
        except (IndexError, ValueError):
            return None
        if not digits or len(digits) != len(raw[1]):
            return None
        value = int(digits)
    else:
        return None
    return value if 100 <= value <= 100000 else None


def _layout(room: dict[str, Any]) -> str | None:
    bedroom = room.get("bedroom")
    parlor = room.get("parlor")
    if isinstance(bedroom, int) and bedroom > 0:
        return f"{bedroom}室{parlor}厅" if isinstance(parlor, int) else f"{bedroom}室"
    name = str(room.get("name") or "")
    for marker in ("1居室", "2居室", "3居室", "4居室"):
        if marker in name:
            return marker.replace("居室", "室")
    return None


def _image(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.startswith("//"):
        text = f"https:{text}"
    return text if text.startswith(("http://", "https://")) else None


def parse_room(
    room: dict[str, Any], city_code: str = "sz", *, sprite_order_value: str = ""
) -> ListingDraft | None:
    room_id = str(room.get("id") or room.get("house_id") or "").strip()
    if not room_id:
        return None
    rent = _price(room, sprite_order_value)
    if rent is None:
        return None
    house_id = str(room.get("house_id") or room_id)
    city_id = CITY_CODES.get(city_code, "")
    url = f"https://m.ziroom.com/wap/detail/room?city_code={city_id}&id={room_id}"
    tags = [
        str(item.get("title") or "").strip()
        for item in room.get("tags") or []
        if isinstance(item, dict) and str(item.get("title") or "").strip()
    ]
    if room.get("type_text"):
        tags.insert(0, str(room["type_text"]))
    return ListingDraft(
        source_listing_id=house_id[:64],
        url=url[:512],
        title=" ".join(str(room.get("name") or "").split())[:255],
        community_name=(str(room.get("resblock_name") or "")[:128] or None),
        district=(str(room.get("district_name") or "")[:64] or None),
        layout=_layout(room),
        area=(
            float(room["area"])
            if str(room.get("area") or "").replace(".", "", 1).isdigit()
            else None
        ),
        orientation=(str(room.get("face") or "")[:32] or None),
        floor=(
            f"{room['floor']}/{room['floor_total']}"
            if room.get("floor") and room.get("floor_total")
            else None
        ),
        rent=rent,
        tags=tags[:12],
        image_url=_image(room.get("photo") or room.get("photo_min")),
        agent_type="ziroom",
        raw={
            "ziroom_id": room_id,
            "house_code": house_id,
            "lng": room.get("lng"),
            "lat": room.get("lat"),
            "code": room.get("code"),
            "subway": room.get("subway_station_info"),
        },
    )


class ZiroomFetcher:
    def __init__(self, city_code: str = "sz") -> None:
        self.city_code = city_code
        self.city_id = CITY_CODES.get(city_code)
        if self.city_id is None:
            raise SourceError(f"ziroom has no city_code for {city_code}")
        self._client = httpx.AsyncClient(timeout=30.0, headers=HEADERS)

    async def close(self) -> None:
        await self._client.aclose()

    async def _order(self, url: str) -> str:
        if url in _SPRITE_ORDERS:
            return _SPRITE_ORDERS[url]
        try:
            response = await self._client.get(url)
            image = Image.open(io.BytesIO(response.content))
            order = sprite_order(image)
        except Exception as exc:
            log.warning("ziroom_sprite_failed", url=url[:120], error=str(exc)[:120])
            return ""
        if order:
            _SPRITE_ORDERS[url] = order
        else:
            log.warning("ziroom_sprite_unknown", url=url[:120])
        return order

    async def fetch_page(
        self, page: int = 1, *, limit: int = DEFAULT_PAGE_SIZE
    ) -> list[ListingDraft]:
        try:
            response = await self._client.get(
                API_URL,
                params={"city_code": self.city_id, "page": max(1, page)},
            )
        except httpx.HTTPError as exc:
            raise SourceError(f"ziroom request failed: {type(exc).__name__}") from exc
        if response.status_code >= 400:
            raise SourceError(f"ziroom HTTP {response.status_code}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise SourceError("ziroom returned non-JSON") from exc
        data = payload.get("data") or {}
        rooms = data.get("rooms") or []
        if not rooms:
            raise EmptyPageError(f"ziroom page {page} has no rooms")
        drafts: list[ListingDraft] = []
        for room in rooms[: max(1, limit)]:
            sprite = _sprite_url(room)
            order = await self._order(sprite) if sprite else ""
            if not order:
                continue
            draft = parse_room(room, self.city_code, sprite_order_value=order)
            if draft is not None:
                drafts.append(draft)
        await asyncio.sleep(MAX_PAGE_SLEEP)
        return drafts
