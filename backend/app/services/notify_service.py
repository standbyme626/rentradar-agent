import json

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models import Event, EventType, Listing
from app.services.settings_service import get_admin_settings, is_quiet_now

log = get_logger("notify")


async def send_text(db: AsyncSession, text: str) -> dict:
    admin_settings = await get_admin_settings(db)
    if not admin_settings.get("feishu", True):
        return {"ok": False, "skipped": True, "reason": "feishu disabled"}
    if not (settings.feishu_app_id and settings.feishu_app_secret and settings.feishu_receive_id):
        return {"ok": False, "skipped": True, "reason": "feishu credentials missing"}

    async with httpx.AsyncClient(timeout=15.0) as client:
        token_response = await client.post(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": settings.feishu_app_id, "app_secret": settings.feishu_app_secret},
        )
        token_data = token_response.json()
        token = token_data.get("tenant_access_token")
        if not token:
            log.error("feishu_token_failed", code=token_data.get("code"), msg=token_data.get("msg"))
            return {"ok": False, "error": token_data.get("msg"), "code": token_data.get("code")}

        response = await client.post(
            "https://open.feishu.cn/open-apis/im/v1/messages",
            params={"receive_id_type": settings.feishu_receive_id_type},
            headers={"Authorization": f"Bearer {token}"},
            json={
                "receive_id": settings.feishu_receive_id,
                "msg_type": "text",
                "content": json.dumps({"text": text}, ensure_ascii=False),
            },
        )
        data = response.json()
        if data.get("code") != 0:
            log.error("feishu_send_failed", code=data.get("code"), msg=data.get("msg"))
            return {"ok": False, "error": data.get("msg"), "code": data.get("code")}
        return {"ok": True, "message_id": (data.get("data") or {}).get("message_id")}


def _format_event(event: Event, listing: Listing | None) -> str:
    score = f"{listing.score}分" if listing and listing.score is not None else "未评分"
    rent = f"¥{listing.rent}" if listing and listing.rent else "—"
    title = (listing.title if listing else None) or "未知房源"
    return f"- [{event.type.value}] {score} {rent} {title}"


def _qualifies(
    event: Event,
    listing: Listing | None,
    *,
    score_min: int,
    drop_pct: float,
) -> bool:
    if event.type in (EventType.new, EventType.relisted):
        return bool(listing and listing.score is not None and listing.score >= score_min)
    if event.type == EventType.price_drop:
        old = (event.payload or {}).get("old")
        new = (event.payload or {}).get("new")
        if old and new and old > 0:
            return (old - new) / old >= drop_pct / 100
    return False


async def notify_events(
    db: AsyncSession, event_ids: list[int], limit: int | None = None, force: bool = False
) -> dict:
    if not event_ids:
        return {"ok": False, "skipped": True, "reason": "no events"}
    admin_settings = await get_admin_settings(db)
    if not force and is_quiet_now(admin_settings):
        return {"ok": False, "skipped": True, "reason": "silent hours"}

    events = (
        (
            await db.execute(
                select(Event)
                .where(Event.id.in_(event_ids), Event.notified.is_(False))
                .order_by(Event.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    if not events:
        return {"ok": False, "skipped": True, "reason": "all notified"}

    batch_cap = int(admin_settings.get("notifyBatchCap") or limit or 10)
    selected = events[: max(1, batch_cap)]
    listing_ids = [event.listing_id for event in selected if event.listing_id]
    listings = (
        (await db.execute(select(Listing).where(Listing.id.in_(listing_ids)))).scalars().all()
    )
    by_id = {listing.id: listing for listing in listings}
    selected = [
        event
        for event in selected
        if _qualifies(
            event,
            by_id.get(event.listing_id),
            score_min=int(admin_settings.get("notifyScoreMin") or 75),
            drop_pct=float(admin_settings.get("priceDropPct") or 8),
        )
    ]
    if not selected:
        return {"ok": False, "skipped": True, "reason": "no qualifying events"}

    lines = ["RentRadar 即时提醒"]
    for event in selected:
        lines.append(_format_event(event, by_id.get(event.listing_id)))
    result = await send_text(db, "\n".join(lines))
    if result.get("ok"):
        for event in selected:
            event.notified = True
        await db.commit()
    return result
