import csv
import io

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    City,
    DeliveryProbe,
    Event,
    Inspection,
    Listing,
    ListingImageAnalysis,
    ListingStatus,
    Snapshot,
    Source,
    Watchlist,
)
from app.services import commute_service, reputation_service
from app.services.settings_service import destination_key, get_commute_destination

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


def _inspection_dict(record: Inspection | None) -> dict:
    items = {key: False for key in CHECKLIST_KEYS}
    if record is None:
        return {"items": items, "note": None, "photos": [], "updated_at": None}
    data = record.data or {}
    items.update({key: bool(value) for key, value in (data.get("items") or {}).items()})
    return {
        "items": items,
        "note": data.get("note"),
        "photos": data.get("photos") or [],
        "updated_at": record.updated_at,
    }


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
    watch = await db.get(Watchlist, (user_id, listing_id))
    inspection = await db.get(Inspection, (listing_id, user_id))
    destination = await get_commute_destination(db)
    key = destination_key(destination)
    commute = None
    if listing.community_id is not None and key is not None:
        commute = await commute_service.community_stats(
            db, listing.community_id, key, destination=destination
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

    analysis = await db.get(ListingImageAnalysis, listing_id)
    reputation = await reputation_service.listing_reputation(
        db, listing.community_id
    )
    data.update(
        {
            "score_reasons": listing.score_reasons or {},
            "image_analysis": (
                {
                    "verdict": analysis.verdict,
                    "confidence": float(analysis.confidence)
                    if analysis.confidence is not None
                    else None,
                    "signals": analysis.signals or [],
                    "quality": analysis.quality or {},
                    "needs_vision": analysis.needs_vision,
                    "analyzed_at": analysis.analyzed_at,
                }
                if analysis is not None
                else None
            ),
            "reputation": reputation,
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
            "watch_state": watch.state if watch is not None else None,
            "watch_note": watch.note if watch is not None else None,
            "watch_updated_at": watch.updated_at if watch is not None else None,
            "inspection": _inspection_dict(inspection),
            "commute_stats": commute,
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


async def watchlist_entries(db: AsyncSession, user_id: int) -> list[dict]:
    rows = (
        await db.execute(
            select(Watchlist, Listing, Source.code, City.code)
            .join(Listing, Watchlist.listing_id == Listing.id)
            .join(Source, Listing.source_id == Source.id)
            .join(City, Listing.city_id == City.id)
            .where(Watchlist.user_id == user_id)
            .order_by(Watchlist.updated_at.desc(), Watchlist.listing_id.desc())
        )
    ).all()
    inspection_rows = (
        (
            await db.execute(
                select(Inspection).where(Inspection.user_id == user_id)
            )
        )
        .scalars()
        .all()
    )
    inspections = {item.listing_id: item for item in inspection_rows}
    result = []
    for entry, listing, source_code, city_code in rows:
        item = _listing_dict(listing, source_code, city_code)
        result.append(
            {
                "listing": item,
                "state": entry.state,
                "note": entry.note,
                "updated_at": entry.updated_at,
                "inspection": _inspection_dict(inspections.get(listing.id)),
            }
        )
    return result


def watchlist_csv(entries: list[dict]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "房源ID",
            "小区",
            "区域",
            "户型",
            "面积㎡",
            "月租",
            "评分",
            "状态",
            "备注",
            "检查通过项",
            "检查备注",
            "照片数",
            "上架时间",
            "更新时间",
            "链接",
        ]
    )
    labels = {
        "soundproofing": "隔音",
        "leak": "漏水",
        "water": "水电",
        "power": "供电",
        "network": "网络",
        "delivery": "外卖",
        "property": "物业",
        "elevator": "电梯",
    }
    for item in entries:
        listing = item["listing"]
        inspection = item["inspection"] or {}
        passed = [
            labels.get(key, key)
            for key, value in (inspection.get("items") or {}).items()
            if value
        ]
        writer.writerow(
            [
                listing["id"],
                listing.get("community_name") or "",
                listing.get("district") or "",
                listing.get("layout") or "",
                listing.get("area") if listing.get("area") is not None else "",
                listing.get("rent") if listing.get("rent") is not None else "",
                listing.get("score") if listing.get("score") is not None else "",
                item["state"],
                item.get("note") or "",
                " / ".join(passed),
                inspection.get("note") or "",
                len(inspection.get("photos") or []),
                listing.get("first_seen_at").isoformat() if listing.get("first_seen_at") else "",
                item["updated_at"].isoformat() if item.get("updated_at") else "",
                listing.get("url") or "",
            ]
        )
    return buffer.getvalue()
