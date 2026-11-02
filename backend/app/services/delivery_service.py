from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.delivery.iphone import IPhoneClient, IPhoneError, LocationSession
from app.delivery.meituan import extract_probe
from app.models import Community, DeliveryProbe, Listing

log = get_logger("delivery")
PROBE_DIR = Path("/home/kkk/Project/rentradar/data/probes")


def meal_period(now: datetime | None = None) -> str:
    local = (now or datetime.now(ZoneInfo("Asia/Shanghai"))).astimezone(ZoneInfo("Asia/Shanghai"))
    hour = local.hour
    if 11 <= hour < 14:
        return "lunch"
    if 17 <= hour <= 20:
        return "dinner"
    if hour >= 21 or hour < 2:
        return "late_night"
    return "other"


async def probe_community(
    db: AsyncSession,
    community_id: int,
    platform: str = "meituan",
    navigate: bool = True,
) -> dict:
    community = await db.get(Community, community_id)
    if community is None:
        raise ValueError(f"community {community_id} not found")
    if community.lng is None or community.lat is None:
        raise ValueError(f"community {community_id} has no coordinates")
    if platform != "meituan":
        raise ValueError(f"platform {platform} not implemented")

    client = IPhoneClient()
    now = datetime.now(UTC)
    shot_path = PROBE_DIR / f"{community_id}_{now:%Y%m%d_%H%M%S}.png"
    async with LocationSession(float(community.lng), float(community.lat)):
        if navigate:
            await client.launch_meituan()
            items = await client.ensure_delivery_home()
        else:
            await client.refresh_delivery()
            items = await client.accessibility()
            captions = [item.get("caption", "") for item in items]
            if not any("起送" in caption and "分钟" in caption for caption in captions):
                raise IPhoneError("Meituan is not on the delivery home; leave it there and retry")
        await client.screenshot(shot_path)
        data = extract_probe(items)

    probe = DeliveryProbe(
        community_id=community.id,
        platform=platform,
        probe_at=now,
        meal_period=meal_period(),
        address_label=data["address_label"],
        eta_min_low=data["eta_min_low"],
        eta_min_high=data["eta_min_high"],
        fee=data["fee"],
        merchant_count=data["merchant_count"],
        raw_text=data["raw_text"],
        screenshot_paths=[str(shot_path)],
        confidence=data["confidence"],
        device_id=settings.probe_device_id,
    )
    db.add(probe)
    await db.commit()
    await db.refresh(probe)
    log.info(
        "delivery_probe_saved",
        probe_id=probe.id,
        community=community.name,
        eta=(probe.eta_min_low, probe.eta_min_high),
        fee=float(probe.fee) if probe.fee is not None else None,
    )
    return {
        "id": probe.id,
        "community": community.name,
        "platform": platform,
        "meal_period": probe.meal_period,
        "address": probe.address_label,
        "eta": [probe.eta_min_low, probe.eta_min_high],
        "fee": float(probe.fee) if probe.fee is not None else None,
        "merchant_count": probe.merchant_count,
        "confidence": float(probe.confidence) if probe.confidence is not None else None,
        "screenshot": str(shot_path),
    }


async def probe_for_listing(db: AsyncSession, listing_id: int) -> dict:
    listing = await db.get(Listing, listing_id)
    if listing is None or listing.community_id is None:
        raise ValueError(f"listing {listing_id} has no community")
    return await probe_community(db, listing.community_id)


async def recent_probes(db: AsyncSession, community_id: int, limit: int = 6) -> list[dict]:
    from sqlalchemy import select

    rows = (
        (
            await db.execute(
                select(DeliveryProbe)
                .where(DeliveryProbe.community_id == community_id)
                .order_by(DeliveryProbe.probe_at.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": row.id,
            "platform": row.platform,
            "probe_at": row.probe_at,
            "meal_period": row.meal_period,
            "address_label": row.address_label,
            "eta_min_low": row.eta_min_low,
            "eta_min_high": row.eta_min_high,
            "fee": float(row.fee) if row.fee is not None else None,
            "merchant_count": row.merchant_count,
            "confidence": float(row.confidence) if row.confidence is not None else None,
        }
        for row in rows
    ]
