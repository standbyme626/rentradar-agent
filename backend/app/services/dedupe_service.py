"""Cross-source duplicate detection (P2/W9).

The same flat can be listed on Beike and on a brand-apartment/manual feed.
We do not want two scored rows for one unit.  Matching is deliberately
conservative: same city + normalized community + normalized layout + rent
within 3% (+ area within 5% when both sides have it).  A match is recorded as
a cross-source alias on the existing listing instead of inserting a new row.
"""

import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Listing, ListingStatus
from app.sources.base import ListingDraft

RENT_TOLERANCE = 0.03
AREA_TOLERANCE = 0.05
_PUNCT = re.compile(r"[\s\-_·•（）()\[\]【】]+")


def normalize_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    return _PUNCT.sub("", text)


def normalize_layout(value: Any) -> str:
    match = re.search(r"(\d)\s*室\s*(\d)?\s*厅?", str(value or ""))
    if not match:
        return normalize_text(value)[:8]
    rooms, halls = match.group(1), match.group(2)
    return f"{rooms}室{halls}厅" if halls else f"{rooms}室"


def _rent(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _area(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True, slots=True)
class Candidate:
    community_name: str | None
    layout: str | None
    rent: int | None
    area: float | None


def is_cross_source_duplicate(
    existing: Candidate,
    incoming: Candidate,
    *,
    rent_tolerance: float = RENT_TOLERANCE,
    area_tolerance: float = AREA_TOLERANCE,
) -> bool:
    if not normalize_text(existing.community_name) or not normalize_text(
        incoming.community_name
    ):
        return False
    if normalize_text(existing.community_name) != normalize_text(
        incoming.community_name
    ):
        return False
    if not normalize_layout(existing.layout) or (
        normalize_layout(existing.layout) != normalize_layout(incoming.layout)
    ):
        return False
    left, right = _rent(existing.rent), _rent(incoming.rent)
    if not left or not right:
        return False
    if abs(left - right) / max(left, right) > rent_tolerance:
        return False
    left_area, right_area = _area(existing.area), _area(incoming.area)
    if left_area and right_area:
        if abs(left_area - right_area) / max(left_area, right_area) > area_tolerance:
            return False
    return True


async def find_duplicate(
    db: AsyncSession, city_id: int, draft: ListingDraft, source_id: int
) -> Listing | None:
    if not draft.community_name or not draft.rent:
        return None
    candidates = (
        (
            await db.execute(
                select(Listing).where(
                    Listing.city_id == city_id,
                    Listing.source_id != source_id,
                    Listing.community_name == draft.community_name,
                    Listing.status.in_(
                        [ListingStatus.active, ListingStatus.relisted]
                    ),
                )
            )
        )
        .scalars()
        .all()
    )
    incoming = Candidate(
        community_name=draft.community_name,
        layout=draft.layout,
        rent=draft.rent,
        area=draft.area,
    )
    for listing in candidates:
        existing = Candidate(
            community_name=listing.community_name,
            layout=listing.layout,
            rent=listing.rent,
            area=float(listing.area) if listing.area is not None else None,
        )
        if is_cross_source_duplicate(existing, incoming):
            return listing
    return None
