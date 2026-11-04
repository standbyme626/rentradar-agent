"""Manual JSON/CSV housing feed (P2/W9).

This is the first non-Beike source.  It is opt-in (source ``manual`` starts
disabled) and intended for brand-apartment lists or offline rows an operator
already has.  It never fetches the network, so it is safe to run anywhere.

Accepted JSON: a list of rows, or ``{"items": [...]}``.
Accepted CSV: headers matching the row fields below (snake_case or camelCase).
"""

import csv
import json
from pathlib import Path

from app.sources.base import ListingDraft, SourceError

_FIELDS = {
    "id": ("source_listing_id", "sourceListingId", "id", "code", "house_code"),
    "url": ("url", "link"),
    "title": ("title", "name"),
    "community": ("community_name", "communityName", "community", "resblock_name"),
    "district": ("district", "district_name"),
    "layout": ("layout",),
    "area": ("area", "rent_area"),
    "orientation": ("orientation", "frame_orientation"),
    "floor": ("floor", "floor_level"),
    "rent": ("rent", "rent_price_listing", "monthly_rent", "price"),
    "tags": ("tags",),
    "image": ("image_url", "image", "cover"),
    "city": ("city", "city_code", "cityCode"),
}


def _pick(row: dict, key: str):
    for name in _FIELDS[key]:
        if name in row and row[name] not in (None, ""):
            return row[name]
    return None


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


def _tags(value) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.replace("，", ",").split(",") if item.strip()]
    return []


def parse_row(row: dict, index: int = 0) -> ListingDraft:
    if not isinstance(row, dict):
        raise SourceError(f"第 {index + 1} 行不是对象")
    source_listing_id = str(_pick(row, "id") or "").strip()
    rent = _int(_pick(row, "rent"))
    if not source_listing_id:
        raise SourceError(f"第 {index + 1} 行缺少 id/house_code")
    if rent is None or not (100 <= rent <= 100000):
        raise SourceError(f"第 {index + 1} 行 rent 无效")
    area = _float(_pick(row, "area"))
    if area is not None and not (5 <= area <= 1000):
        raise SourceError(f"第 {index + 1} 行 area 无效")
    return ListingDraft(
        source_listing_id=source_listing_id[:64],
        url=str(_pick(row, "url") or f"manual://{source_listing_id}")[:512],
        title=str(_pick(row, "title") or "")[:255],
        community_name=(str(_pick(row, "community") or "")[:128] or None),
        district=(str(_pick(row, "district") or "")[:64] or None),
        layout=(str(_pick(row, "layout") or "")[:32] or None),
        area=area,
        orientation=(str(_pick(row, "orientation") or "")[:32] or None),
        floor=(str(_pick(row, "floor") or "")[:32] or None),
        rent=rent,
        tags=_tags(_pick(row, "tags")),
        image_url=(str(_pick(row, "image") or "")[:512] or None),
        agent_type="manual",
        raw={"manual": True, "city": _pick(row, "city"), "row_index": index},
    )


def parse_rows(rows: list[dict]) -> tuple[list[ListingDraft], list[str]]:
    drafts: list[ListingDraft] = []
    errors: list[str] = []
    for index, row in enumerate(rows):
        try:
            drafts.append(parse_row(row, index))
        except SourceError as exc:
            errors.append(str(exc))
    return drafts, errors


def load_feed(path: str | Path) -> tuple[list[ListingDraft], list[str]]:
    file = Path(path)
    if not file.is_file():
        raise SourceError(f"feed file not found: {path}")
    suffix = file.suffix.lower()
    try:
        if suffix == ".json":
            payload = json.loads(file.read_text(encoding="utf-8"))
            rows = payload.get("items") if isinstance(payload, dict) else payload
        elif suffix == ".csv":
            with file.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
        else:
            raise SourceError("feed must be .json or .csv")
    except (OSError, ValueError) as exc:
        raise SourceError(f"cannot read feed: {exc}") from exc
    if not isinstance(rows, list):
        raise SourceError("feed must contain a list of rows")
    return parse_rows(rows)
