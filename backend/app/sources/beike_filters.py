"""Beike/Lianjia mobile filter config: subway line and station shard conditions.

The mobile filter config endpoint is the source of truth for line/station ids
(see ``docs/API-SOURCES.md``). A station's ``pinyin`` field is already a valid
list ``condition`` prefix, e.g. ``li110460696s100021264`` for 赤湾 on line 5,
so a single line can be split into per-station shards that stay below the
3000-item ``offset`` ceiling of the App list API.
"""

import re

import httpx

from app.sources.base import SourceError
from app.sources.beike_api import CITY_IDS, HEADERS

FILTER_URL = "https://m.lianjia.com/chuzu/aj/config/filter"
LINE_LABEL_RE = re.compile(r"[（(][^）)]*[）)]")


def _line_label(name: str) -> str:
    """Drop a trailing parenthetical, e.g. ``5号线(环中线)`` -> ``5号线``."""
    return LINE_LABEL_RE.sub("", name).strip()


def _float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_filter_payload(payload: dict) -> dict:
    status = payload.get("status")
    if status not in (0, "0"):
        raise SourceError(f"beike filter config error: {payload.get('msg') or status}")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise SourceError("beike filter config returned no data")
    return data


async def fetch_filter_config(
    city_code: str = "sz",
    *,
    timeout: float = 20.0,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict:
    city_id = CITY_IDS.get(city_code)
    if city_id is None:
        raise SourceError(f"beike filter config has no city_id for {city_code}")
    async with httpx.AsyncClient(
        timeout=timeout, headers=HEADERS, transport=transport, follow_redirects=True
    ) as client:
        try:
            response = await client.get(FILTER_URL, params={"city_id": city_id})
        except httpx.HTTPError as exc:
            raise SourceError(
                f"beike filter config request failed: {type(exc).__name__}"
            ) from exc
    if response.status_code >= 400:
        raise SourceError(f"beike filter config http {response.status_code}")
    try:
        payload = response.json()
    except ValueError as exc:
        raise SourceError("beike filter config returned invalid JSON") from exc
    return parse_filter_payload(payload)


def find_line(config: dict, query: str) -> dict:
    """Resolve a line by id, pinyin condition, or readable name (``5号线``)."""
    options = (config.get("li") or {}).get("options") or []
    needle = str(query).strip().strip("/")
    if not needle:
        raise SourceError("subway line query is empty")
    needles = [needle]
    if needle.isdigit():
        # "5" is the readable form of "5号线"; a long numeric id stays an id.
        needles.append(f"{needle}号线")
    exact: list[dict] = []
    fuzzy: list[dict] = []
    for line in options:
        line_id = str(line.get("id") or "")
        pinyin = str(line.get("pinyin") or "").strip("/")
        label = _line_label(str(line.get("name") or ""))
        if any(item in {line_id, pinyin, label} for item in needles):
            exact.append(line)
        elif any(
            item in label or item in str(line.get("name") or "") for item in needles
        ):
            fuzzy.append(line)
    matches = exact or fuzzy
    if not matches:
        raise SourceError(f"unknown subway line: {query}")
    if len(matches) > 1:
        names = ", ".join(_line_label(str(item.get("name"))) for item in matches[:6])
        raise SourceError(f"ambiguous subway line {query!r}: {names}")
    return matches[0]


def build_line_shards(config: dict, query: str) -> dict:
    """Return the line plus one shard per station, in config order.

    Each shard carries the station-level ``condition`` prefix. The caller appends
    the sort suffix (``/rco11``) through the regular crawl path, so the planned
    values can be passed to ``python -m app.cli crawl --line`` directly.
    """
    line = find_line(config, query)
    line_id = line.get("id")
    line_name = str(line.get("name") or "")
    line_condition = str(line.get("pinyin") or "").strip().strip("/")
    if not line_id or not line_condition:
        raise SourceError(f"subway line {query!r} has no usable condition")

    shards: list[dict] = []
    for station in line.get("children") or []:
        station_id = station.get("id")
        condition = str(station.get("pinyin") or "").strip().strip("/")
        if not station_id or not condition:
            # The "不限" option uses id 0 and an empty condition.
            continue
        shards.append(
            {
                "station_id": station_id,
                "name": str(station.get("name") or "").strip(),
                "condition": condition,
                "lat": _float(station.get("latitude")),
                "lng": _float(station.get("longitude")),
                "is_transfer": bool(station.get("is_transfer")),
            }
        )
    if not shards:
        raise SourceError(f"subway line {query!r} has no station conditions")
    return {
        "line_id": line_id,
        "line_name": line_name,
        "line_condition": line_condition,
        "shards": shards,
    }
