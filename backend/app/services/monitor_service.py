import re
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models import (
    AgentMonitor,
    AgentMonitorMatch,
    Event,
    EventType,
    Listing,
    ListingStatus,
)
from app.services import commute_service
from app.services.notify_service import send_text
from app.services.settings_service import (
    destination_key,
    get_admin_settings,
    get_commute_destination,
    is_quiet_now,
)

log = get_logger("monitor")


def normalize_conditions(raw: dict | None) -> dict:
    raw = raw or {}

    def _number(value) -> int | None:
        if isinstance(value, (int, float)):
            return int(value)
        match = re.search(r"\d+", str(value or ""))
        return int(match.group(0)) if match else None

    raw_must = raw.get("must")
    if isinstance(raw_must, str):
        raw_must = re.split(r"[/,，、]", raw_must)
    if not isinstance(raw_must, list):
        raw_must = []
    known = ("电梯", "近地铁", "精装", "南向")
    must = [
        tag
        for tag in known
        if any(tag in str(item) for item in raw_must)
    ]
    layout = raw.get("layout")
    if layout in ("", "不限", None):
        layout = None
    elif layout:
        text = str(layout)
        if "两居" in text or "二居" in text or "2室" in text:
            layout = "2室"
        elif "三居" in text or "3室" in text:
            layout = "3室"
        elif "一居" in text or "1室" in text:
            layout = "1室"
        else:
            layout = None
    district = raw.get("district")
    if district in ("", "不限", None):
        district = None
    return {
        "budget": _number(raw.get("budget")),
        "commute": _number(raw.get("commute")),
        "layout": str(layout) if layout else None,
        "district": str(district) if district else None,
        "must": [str(item) for item in must],
        "line": raw.get("line"),
    }


def matches_conditions(
    listing: Listing,
    conditions: dict,
    commute_minutes: int | None = None,
) -> bool:
    budget = conditions.get("budget")
    if budget and (listing.rent is None or listing.rent > int(budget)):
        return False
    layout = conditions.get("layout")
    if layout and layout not in (listing.layout or ""):
        return False
    district = conditions.get("district")
    if district and listing.district != district:
        return False
    tags = set(listing.tags or [])
    for tag in conditions.get("must") or []:
        if tag == "南向":
            if "南" not in (listing.orientation or ""):
                return False
        elif tag not in tags:
            return False
    commute = conditions.get("commute")
    if commute:
        if commute_minutes is None or commute_minutes > int(commute):
            return False
    return True


async def _latest_commute(db: AsyncSession) -> dict[int, int]:
    destination = await get_commute_destination(db)
    key = destination_key(destination)
    if key is None:
        return {}
    stats = await commute_service.bulk_stats(db, key, destination=destination)
    if not stats:
        nearest = await commute_service.nearest_destination_key(db, key)
        if nearest is not None:
            stats = await commute_service.bulk_stats(
                db, nearest, destination=destination
            )
    return {
        community_id: round(item["p50_min"])
        for community_id, item in stats.items()
        if item.get("p50_min") is not None
    }


def _price_drop_ok(event: Event, threshold: float) -> bool:
    old = (event.payload or {}).get("old")
    new = (event.payload or {}).get("new")
    if not old or not new or old <= 0:
        return False
    return (old - new) / old >= threshold / 100


async def _scan_monitor(
    db: AsyncSession,
    monitor: AgentMonitor,
    *,
    commute: dict[int, int],
    price_drop_pct: float,
) -> int:
    conditions = normalize_conditions(monitor.conditions)
    since = monitor.last_checked_at or monitor.created_at
    if since.tzinfo is None:
        since = since.replace(tzinfo=UTC)
    rows = (
        await db.execute(
            select(Event, Listing)
            .join(Listing, Event.listing_id == Listing.id)
            .where(
                Event.created_at > since,
                Event.type.in_(
                    [EventType.new, EventType.relisted, EventType.price_drop]
                ),
                Listing.status == ListingStatus.active,
            )
            .order_by(Event.created_at.asc())
        )
    ).all()
    inserted = 0
    for event, listing in rows:
        if event.type == EventType.price_drop and not _price_drop_ok(
            event, price_drop_pct
        ):
            continue
        duration = commute.get(listing.community_id) if listing.community_id else None
        minutes = round(duration / 60) if duration else None
        if not matches_conditions(listing, conditions, minutes):
            continue
        match_key = f"{event.type.value}:{event.id}"
        result = await db.execute(
            pg_insert(AgentMonitorMatch)
            .values(
                monitor_id=monitor.id,
                listing_id=listing.id,
                event_id=event.id,
                match_key=match_key,
                type=event.type.value,
                score=listing.score,
                rent=listing.rent,
                title=(listing.title or listing.community_name or "")[:255] or None,
            )
            .on_conflict_do_nothing(
                index_elements=[AgentMonitorMatch.monitor_id, AgentMonitorMatch.match_key]
            )
        )
        inserted += int(result.rowcount or 0)
    monitor.last_checked_at = datetime.now(UTC)
    return inserted


async def _refresh_counts(db: AsyncSession) -> None:
    counts = (
        await db.execute(
            select(
                AgentMonitorMatch.monitor_id,
                func.count().label("pending"),
            )
            .where(AgentMonitorMatch.notified_at.is_(None))
            .group_by(AgentMonitorMatch.monitor_id)
        )
    ).all()
    pending = {monitor_id: int(count) for monitor_id, count in counts}
    monitors = (await db.execute(select(AgentMonitor))).scalars().all()
    for monitor in monitors:
        monitor.new_matches = pending.get(monitor.id, 0)


async def push_pending(db: AsyncSession) -> dict:
    admin_settings = await get_admin_settings(db)
    if not admin_settings.get("monitorPush", True):
        return {"ok": False, "skipped": True, "reason": "monitor push disabled"}
    if is_quiet_now(admin_settings):
        return {"ok": False, "skipped": True, "reason": "silent hours"}
    batch_cap = max(1, int(admin_settings.get("notifyBatchCap") or 10))
    rows = (
        await db.execute(
            select(AgentMonitorMatch, AgentMonitor)
            .join(AgentMonitor, AgentMonitorMatch.monitor_id == AgentMonitor.id)
            .where(
                AgentMonitorMatch.notified_at.is_(None),
                AgentMonitor.enabled.is_(True),
            )
            .order_by(AgentMonitorMatch.created_at.asc())
            .limit(batch_cap)
        )
    ).all()
    if not rows:
        return {"ok": False, "skipped": True, "reason": "no pending matches"}

    groups: dict[str, list[AgentMonitorMatch]] = {}
    names: dict[str, str] = {}
    for match, monitor in rows:
        groups.setdefault(monitor.id, []).append(match)
        names[monitor.id] = monitor.name

    sent: list[AgentMonitorMatch] = []
    for monitor_id, matches in groups.items():
        lines = [f"RentRadar 监控命中 · {names[monitor_id]}"]
        for match in matches:
            label = {
                "new": "新上架",
                "relisted": "重新上架",
                "price_drop": "降价",
            }.get(match.type, match.type)
            score = f"{match.score}分" if match.score is not None else "未评分"
            rent = f"¥{match.rent}" if match.rent else "—"
            lines.append(f"- {label} | {score} {rent} {match.title or ''}".strip())
        result = await send_text(db, "\n".join(lines))
        if not result.get("ok"):
            log.warning(
                "monitor_push_failed",
                monitor_id=monitor_id,
                reason=result.get("reason") or result.get("error"),
            )
            continue
        now = datetime.now(UTC)
        for match in matches:
            match.notified_at = now
            sent.append(match)
        monitor = await db.get(AgentMonitor, monitor_id)
        if monitor is not None:
            monitor.last_notified_at = now
    await db.flush()
    await _refresh_counts(db)
    await db.commit()
    return {"ok": True, "sent": len(sent)}


async def process_monitors(db: AsyncSession) -> dict:
    admin_settings = await get_admin_settings(db)
    if not admin_settings.get("monitorPush", True):
        return {"ok": False, "skipped": True, "reason": "monitor push disabled"}
    monitors = (
        (
            await db.execute(
                select(AgentMonitor)
                .where(AgentMonitor.enabled.is_(True))
                .order_by(AgentMonitor.created_at)
            )
        )
        .scalars()
        .all()
    )
    if not monitors:
        return {"ok": True, "monitors": 0, "matches": 0, "push": None}
    commute = await _latest_commute(db)
    price_drop_pct = float(admin_settings.get("priceDropPct") or 8)
    inserted = 0
    for monitor in monitors:
        inserted += await _scan_monitor(
            db, monitor, commute=commute, price_drop_pct=price_drop_pct
        )
    await _refresh_counts(db)
    await db.commit()
    pushed = await push_pending(db)
    return {"ok": True, "monitors": len(monitors), "matches": inserted, "push": pushed}
