from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    City,
    DeliveryProbe,
    Event,
    Listing,
    ListingStatus,
    Snapshot,
    Source,
    Watchlist,
)


def _listing_dict(listing: Listing, source_code: str, city_code: str) -> dict:
    return {
        "id": listing.id,
        "source_code": source_code,
        "city_code": city_code,
        "source_listing_id": listing.source_listing_id,
        "url": listing.url,
        "title": listing.title,
        "community_name": listing.community_name,
        "district": listing.district,
        "layout": listing.layout,
        "area": float(listing.area) if listing.area is not None else None,
        "orientation": listing.orientation,
        "floor": listing.floor,
        "rent": listing.rent,
        "tags": listing.tags or [],
        "image_url": listing.image_url,
        "agent_type": listing.agent_type,
        "score": listing.score,
        "status": listing.status.value,
        "first_seen_at": listing.first_seen_at,
        "last_seen_at": listing.last_seen_at,
    }


async def list_listings(
    db: AsyncSession,
    *,
    q: str | None = None,
    status: str | None = None,
    city: str | None = None,
    min_rent: int | None = None,
    max_rent: int | None = None,
    score_min: int | None = None,
    scored_only: bool = False,
    sort: str = "score_desc",
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int]:
    stmt = (
        select(Listing, Source.code, City.code)
        .join(Source, Listing.source_id == Source.id)
        .join(City, Listing.city_id == City.id)
    )
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Listing.title.ilike(like), Listing.community_name.ilike(like)))
    if status:
        try:
            stmt = stmt.where(Listing.status == ListingStatus(status))
        except ValueError:
            stmt = stmt.where(Listing.status == ListingStatus.active)
    if city:
        stmt = stmt.where(City.code == city)
    if min_rent is not None:
        stmt = stmt.where(Listing.rent >= min_rent)
    if max_rent is not None:
        stmt = stmt.where(Listing.rent <= max_rent)
    if score_min is not None:
        stmt = stmt.where(Listing.score >= score_min)
    if scored_only:
        stmt = stmt.where(Listing.score.is_not(None))

    count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = int(await db.scalar(count_stmt) or 0)

    if sort == "newest":
        order = Listing.first_seen_at.desc()
    elif sort == "rent_asc":
        order = Listing.rent.asc().nullslast()
    elif sort == "rent_desc":
        order = Listing.rent.desc().nullslast()
    else:
        order = Listing.score.desc().nullslast()

    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    rows = (
        await db.execute(
            stmt.order_by(order, Listing.id.desc()).offset((page - 1) * page_size).limit(page_size)
        )
    ).all()
    return [
        _listing_dict(listing, source_code, city_code) for listing, source_code, city_code in rows
    ], total


async def get_listing_detail(
    db: AsyncSession, listing_id: int, user_id: int
) -> dict | None:
    row = (
        await db.execute(
            select(Listing, Source.code, City.code)
            .join(Source, Listing.source_id == Source.id)
            .join(City, Listing.city_id == City.id)
            .where(Listing.id == listing_id)
        )
    ).first()
    if row is None:
        return None
    listing, source_code, city_code = row
    data = _listing_dict(listing, source_code, city_code)

    snapshots = (
        (
            await db.execute(
                select(Snapshot)
                .where(Snapshot.listing_id == listing_id)
                .order_by(Snapshot.seen_at.asc())
            )
        )
        .scalars()
        .all()
    )
    events = (
        (
            await db.execute(
                select(Event)
                .where(Event.listing_id == listing_id)
                .order_by(Event.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    watch_state = await db.scalar(
        select(Watchlist.state).where(
            Watchlist.user_id == user_id, Watchlist.listing_id == listing_id
        )
    )
    probes = []
    if listing.community_id is not None:
        probes = (
            (
                await db.execute(
                    select(DeliveryProbe)
                    .where(DeliveryProbe.community_id == listing.community_id)
                    .order_by(DeliveryProbe.probe_at.desc())
                    .limit(6)
                )
            )
            .scalars()
            .all()
        )

    data.update(
        {
            "score_reasons": listing.score_reasons or {},
            "delivery_probes": [
                {
                    "id": item.id,
                    "platform": item.platform,
                    "probe_at": item.probe_at,
                    "meal_period": item.meal_period,
                    "address_label": item.address_label,
                    "eta_min_low": item.eta_min_low,
                    "eta_min_high": item.eta_min_high,
                    "fee": float(item.fee) if item.fee is not None else None,
                    "merchant_count": item.merchant_count,
                    "confidence": float(item.confidence)
                    if item.confidence is not None
                    else None,
                }
                for item in probes
            ],
            "snapshots": [
                {"rent": item.rent, "seen_at": item.seen_at, "image_hash": item.image_hash}
                for item in snapshots
            ],
            "events": [
                {
                    "id": item.id,
                    "type": item.type.value,
                    "listing_id": item.listing_id,
                    "listing_title": listing.title,
                    "payload": item.payload or {},
                    "notified": item.notified,
                    "created_at": item.created_at,
                }
                for item in events
            ],
            "watch_state": watch_state,
        }
    )
    return data


async def set_watch_state(
    db: AsyncSession,
    listing_id: int,
    user_id: int,
    state: str,
    note: str | None = None,
) -> str:
    entry = await db.get(Watchlist, (user_id, listing_id))
    if entry is None:
        entry = Watchlist(user_id=user_id, listing_id=listing_id, state=state, note=note)
        db.add(entry)
    else:
        entry.state = state
        entry.note = note
    await db.commit()
    return state
