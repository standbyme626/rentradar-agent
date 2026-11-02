from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Event, EventType, Listing
from app.services.notify_service import send_text
from app.services.settings_service import get_admin_settings


def _format(event: Event, listing: Listing | None) -> str:
    score = f"{listing.score}分" if listing and listing.score is not None else "未评分"
    rent = f"¥{listing.rent}" if listing and listing.rent else "—"
    title = (listing.title if listing else None) or "未知房源"
    label = "新上架" if event.type == EventType.new else "降价"
    return f"- {label} | {score} {rent} {title}"


async def send_digest(db: AsyncSession, dry_run: bool = False) -> dict:
    admin_settings = await get_admin_settings(db)
    if not admin_settings.get("digest", True):
        return {"ok": False, "skipped": True, "reason": "digest disabled"}
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(UTC)
    rows = (
        await db.execute(
            select(Event, Listing)
            .join(Listing, Event.listing_id == Listing.id, isouter=True)
            .where(
                Event.type.in_([EventType.new, EventType.price_drop]),
                Event.created_at >= day_start,
                Event.notified.is_(False),
            )
            .order_by(Listing.score.desc().nullslast(), Event.created_at.desc())
            .limit(10)
        )
    ).all()
    if not rows:
        return {"ok": False, "skipped": True, "reason": "no events today"}

    lines = [
        f"RentRadar 09:00 日报 · {now:%m-%d}",
        f"今日新增/降价 {len(rows)} 条（Top {len(rows)}）",
    ]
    for event, listing in rows:
        lines.append(_format(event, listing))
    text = "\n".join(lines)
    if dry_run:
        return {"ok": False, "dry_run": True, "count": len(rows), "text": text}
    result = await send_text(db, text)
    if result.get("ok"):
        for event, _ in rows:
            event.notified = True
        await db.commit()
    return result
