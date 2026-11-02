from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models import Inspection, User
from app.schemas import (
    InspectionOut,
    InspectionUpdate,
    ListingDetail,
    ListingPage,
    StateUpdate,
)
from app.services import listing_service

router = APIRouter(
    prefix="/api/listings", tags=["listings"], dependencies=[Depends(get_current_user)]
)

CHECKLIST_KEYS = [
    "soundproofing",
    "leak",
    "water",
    "power",
    "network",
    "delivery",
    "property",
    "elevator",
]


@router.get("", response_model=ListingPage)
async def list_listings(
    q: str | None = None,
    status: str | None = None,
    city: str | None = None,
    min_rent: int | None = Query(default=None, ge=0),
    max_rent: int | None = Query(default=None, ge=0),
    score_min: int | None = Query(default=None, ge=0, le=100),
    scored_only: bool = False,
    sort: str = Query(default="score_desc", pattern="^(score_desc|newest|rent_asc|rent_desc)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> ListingPage:
    items, total = await listing_service.list_listings(
        db,
        q=q,
        status=status,
        city=city,
        min_rent=min_rent,
        max_rent=max_rent,
        score_min=score_min,
        scored_only=scored_only,
        sort=sort,
        page=page,
        page_size=page_size,
    )
    return ListingPage(items=items, total=total, page=page, page_size=page_size)


@router.get("/{listing_id}", response_model=ListingDetail)
async def get_listing(
    listing_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ListingDetail:
    detail = await listing_service.get_listing_detail(db, listing_id, user.id)
    if detail is None:
        raise HTTPException(status_code=404, detail="listing not found")
    return ListingDetail(**detail)


@router.patch("/{listing_id}/state")
async def update_state(
    listing_id: int,
    payload: StateUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    detail = await listing_service.get_listing_detail(db, listing_id, user.id)
    if detail is None:
        raise HTTPException(status_code=404, detail="listing not found")
    state = await listing_service.set_watch_state(
        db, listing_id, user.id, payload.state, payload.note
    )
    return {"ok": True, "state": state}


@router.get("/{listing_id}/inspection", response_model=InspectionOut)
async def get_inspection(
    listing_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InspectionOut:
    detail = await listing_service.get_listing_detail(db, listing_id, user.id)
    if detail is None:
        raise HTTPException(status_code=404, detail="listing not found")
    record = await db.get(Inspection, (listing_id, user.id))
    if record is None:
        return InspectionOut(items={key: False for key in CHECKLIST_KEYS})
    items = {key: False for key in CHECKLIST_KEYS}
    items.update({key: bool(value) for key, value in (record.data or {}).get("items", {}).items()})
    return InspectionOut(
        items=items,
        note=(record.data or {}).get("note"),
        photos=(record.data or {}).get("photos") or [],
        updated_at=record.updated_at,
    )


@router.put("/{listing_id}/inspection", response_model=InspectionOut)
async def put_inspection(
    listing_id: int,
    payload: InspectionUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InspectionOut:
    detail = await listing_service.get_listing_detail(db, listing_id, user.id)
    if detail is None:
        raise HTTPException(status_code=404, detail="listing not found")
    record = await db.get(Inspection, (listing_id, user.id))
    data = {
        "items": {key: bool(payload.items.get(key)) for key in CHECKLIST_KEYS},
        "note": payload.note,
        "photos": payload.photos,
    }
    if record is None:
        record = Inspection(listing_id=listing_id, user_id=user.id, data=data)
        db.add(record)
    else:
        record.data = data
    await db.commit()
    await db.refresh(record)
    return InspectionOut(**data, updated_at=record.updated_at)
