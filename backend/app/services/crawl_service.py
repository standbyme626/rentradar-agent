import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models import (
    City,
    Community,
    Event,
    EventType,
    Listing,
    ListingStatus,
    Run,
    Snapshot,
    Source,
    Task,
)
from app.services import dedupe_service, provider_runtime
from app.services.notify_service import notify_events, send_text
from app.services.score_service import score_listing
from app.services.settings_service import get_admin_settings
from app.sources import beike_api, manual
from app.sources.base import CaptchaRequiredError
from app.sources.beike import build_list_url, parse_list
from app.sources.cdp import CDPPageFetcher

log = get_logger("crawl")


def _raw_hash(raw: dict) -> str:
    payload = json.dumps(raw, ensure_ascii=False, sort_keys=True).encode()
    return hashlib.md5(payload).hexdigest()


async def _get_or_create_community(
    db: AsyncSession,
    city_id: int,
    name: str | None,
    district: str | None,
    lng: float | None = None,
    lat: float | None = None,
) -> Community | None:
    if not name:
        return None
    community = await db.scalar(
        select(Community).where(Community.city_id == city_id, Community.name == name)
    )
    if community:
        if community.lng is None and community.lat is None and lng is not None and lat is not None:
            community.lng = lng
            community.lat = lat
            community.geocode_confidence = 0.9
        return community
    has_coord = lng is not None and lat is not None
    community = Community(
        city_id=city_id,
        name=name,
        district=district,
        lng=lng if has_coord else None,
        lat=lat if has_coord else None,
        coord_system="GCJ02",
        geocode_confidence=0.9 if has_coord else 0.5,
    )
    db.add(community)
    await db.flush()
    return community


def _apply_draft(listing: Listing, draft, community: Community | None) -> None:
    listing.community_id = community.id if community else listing.community_id
    listing.url = draft.url
    listing.title = draft.title
    listing.community_name = draft.community_name
    listing.district = draft.district
    listing.layout = draft.layout
    listing.area = draft.area
    listing.orientation = draft.orientation
    listing.floor = draft.floor
    listing.rent = draft.rent
    listing.tags = draft.tags
    listing.image_url = draft.image_url
    listing.agent_type = draft.agent_type
    listing.raw = draft.raw
    listing.raw_hash = _raw_hash(draft.raw)


async def _ingest_draft(
    db: AsyncSession,
    *,
    city: City,
    source: Source,
    task: Task,
    draft,
    now: datetime,
    baseline: bool,
    stats: dict,
    event_ids: list[int],
    seen_ids: set[int],
    seen_drafts: set[str],
) -> None:
    """Insert or update one listing, with cross-source de-duplication."""
    if draft.source_listing_id in seen_drafts:
        stats["duplicates"] += 1
        return
    seen_drafts.add(draft.source_listing_id)
    community = await _get_or_create_community(
        db,
        city.id,
        draft.community_name,
        draft.district,
        lng=draft.raw.get("lng"),
        lat=draft.raw.get("lat"),
    )
    listing = await db.scalar(
        select(Listing).where(
            Listing.source_id == source.id,
            Listing.source_listing_id == draft.source_listing_id,
        )
    )
    if listing is None:
        duplicate = await dedupe_service.find_duplicate(
            db, city.id, draft, source.id
        )
        if duplicate is not None:
            aliases = list((duplicate.raw or {}).get("cross_source") or [])
            aliases.append(
                {
                    "source": source.code,
                    "source_listing_id": draft.source_listing_id,
                    "url": draft.url,
                }
            )
            duplicate.raw = {**(duplicate.raw or {}), "cross_source": aliases[-10:]}
            duplicate.cluster_id = duplicate.cluster_id or duplicate.id
            duplicate.last_seen_at = now
            if duplicate.community_id is None and community is not None:
                duplicate.community_id = community.id
            stats["cross_source_duplicates"] = (
                int(stats.get("cross_source_duplicates") or 0) + 1
            )
            seen_ids.add(duplicate.id)
            return
        listing = Listing(
            source_id=source.id,
            city_id=city.id,
            community_id=community.id if community else None,
            source_listing_id=draft.source_listing_id,
            url=draft.url,
            title=draft.title,
            community_name=draft.community_name,
            district=draft.district,
            layout=draft.layout,
            area=draft.area,
            orientation=draft.orientation,
            floor=draft.floor,
            rent=draft.rent,
            tags=draft.tags,
            image_url=draft.image_url,
            agent_type=draft.agent_type,
            raw=draft.raw,
            raw_hash=_raw_hash(draft.raw),
            status=ListingStatus.active,
            first_seen_at=now,
            last_seen_at=now,
        )
        db.add(listing)
        await db.flush()
        if draft.rent is not None:
            db.add(Snapshot(listing_id=listing.id, rent=draft.rent, seen_at=now))
        event = Event(
            listing_id=listing.id,
            type=EventType.new,
            payload={"rent": draft.rent, "source": source.code, "baseline": baseline},
            notified=baseline,
        )
        db.add(event)
        await db.flush()
        event_ids.append(event.id)
        stats["new"] += 1
    else:
        old_rent = listing.rent
        was_missing = listing.status in (ListingStatus.gone, ListingStatus.suspect)
        _apply_draft(listing, draft, community)
        listing.last_seen_at = now
        if was_missing:
            listing.status = ListingStatus.active
            listing.miss_count = 0
            event = Event(
                listing_id=listing.id,
                type=EventType.relisted,
                payload={"rent": draft.rent},
            )
            db.add(event)
            await db.flush()
            event_ids.append(event.id)
        if old_rent is not None and draft.rent is not None and old_rent != draft.rent:
            db.add(Snapshot(listing_id=listing.id, rent=draft.rent, seen_at=now))
            event = Event(
                listing_id=listing.id,
                type=EventType.price_drop
                if draft.rent < old_rent
                else EventType.price_up,
                payload={"old": old_rent, "new": draft.rent},
            )
            db.add(event)
            await db.flush()
            event_ids.append(event.id)
            stats["price_changes"] += 1
        stats["updated"] += 1

    scored = await score_listing(db, listing, task.filters or {})
    if scored is None:
        listing.score = None
        listing.score_reasons = {"filter": "未通过硬过滤"}
    else:
        listing.score, listing.score_reasons = scored
        stats["scored"] += 1
    seen_ids.add(listing.id)


async def run_task(
    db: AsyncSession,
    task: Task,
    *,
    pages: int = 1,
    sort: str = "newest",
    district: str = "",
    line: str = "",
    notify: bool = False,
    full_scan: bool = False,
    transport: str = "",
) -> dict:
    city = await db.get(City, task.city_id)
    source = await db.get(Source, task.source_id)
    if city is None or source is None:
        raise ValueError("task city or source missing")
    if source.code not in {"beike", "manual"}:
        raise ValueError(f"source {source.code} is not implemented yet")
    if not source.enabled:
        raise ValueError(f"source {source.code} is disabled")

    filters = task.filters or {}
    transport = (transport or str(filters.get("transport") or "cdp")).lower()
    if transport not in {"cdp", "api"}:
        raise ValueError(f"unsupported transport: {transport}")
    if transport == "api" and district and not line:
        raise ValueError("api transport needs a line; district-only is not supported")
    if source.code == "beike":
        await provider_runtime.ensure_enabled(
            db, "beike_api" if transport == "api" else "beike_cdp"
        )

    run = Run(task_id=task.id, status="running")
    db.add(run)
    await db.commit()
    await db.refresh(run)

    baseline = (
        int(
            await db.scalar(
                select(func.count()).select_from(Listing).where(Listing.source_id == source.id)
            )
            or 0
        )
        == 0
    )
    scope = f"line:{line}" if line else (f"district:{district}" if district else "all")
    stats = {
        "pages": 0,
        "fetched": 0,
        "new": 0,
        "updated": 0,
        "price_changes": 0,
        "scored": 0,
        "baseline": baseline,
        "district": district,
        "line": line,
        "scope": scope,
        "sort": sort,
        "full_scan": full_scan,
        "gone": 0,
        "suspect": 0,
        "duplicates": 0,
        "total": None,
        "transport": transport,
        "cross_source_duplicates": 0,
    }
    event_ids: list[int] = []
    seen_ids: set[int] = set()
    seen_drafts: set[str] = set()
    if source.code == "manual":
        try:
            feed_path = str(filters.get("feed_path") or "").strip()
            if not feed_path:
                raise ValueError("manual source needs filters.feed_path")
            drafts, feed_errors = manual.load_feed(feed_path)
            stats.update(
                {
                    "pages": 1,
                    "scope": f"manual:{Path(feed_path).name}",
                    "feed_rows": len(drafts),
                    "feed_errors": feed_errors[:20],
                    "transport": "manual",
                }
            )
            now = datetime.now(UTC)
            for draft in drafts:
                city_hint = str(draft.raw.get("city") or "").strip().lower()
                if city_hint and city_hint not in {city.code.lower(), city.name.lower()}:
                    stats["feed_skipped_other_city"] = (
                        int(stats.get("feed_skipped_other_city") or 0) + 1
                    )
                    continue
                draft.raw["scope"] = f"manual:{Path(feed_path).name}"
                await _ingest_draft(
                    db,
                    city=city,
                    source=source,
                    task=task,
                    draft=draft,
                    now=now,
                    baseline=baseline,
                    stats=stats,
                    event_ids=event_ids,
                    seen_ids=seen_ids,
                    seen_drafts=seen_drafts,
                )
            await db.commit()
            run = await db.get(Run, run.id)
            run.status = "done"
            run.finished_at = datetime.now(UTC)
            run.stats = stats
            await db.commit()
            notify_result = await notify_events(db, event_ids) if notify else None
            return {"run_id": run.id, **stats, "notify": notify_result}
        except Exception as exc:
            await db.rollback()
            run = await db.get(Run, run.id)
            if run is not None:
                run.status = "failed"
                run.error = str(exc)[:1000]
                run.finished_at = datetime.now(UTC)
                run.stats = stats
            await db.commit()
            raise
    page_size = beike_api.MAX_LIMIT
    if transport == "api":
        page_size = max(1, min(int(filters.get("page_size") or page_size), page_size))
    fetcher = (
        beike_api.BeikeAPIFetcher(city.code) if transport == "api" else CDPPageFetcher()
    )

    try:
        for page in range(1, max(1, pages) + 1):
            if transport == "api":
                if page > beike_api.max_pages(page_size):
                    break
                started = time.monotonic()
                try:
                    drafts, total = await fetcher.fetch_page(
                        page, line=line, sort=sort, limit=page_size
                    )
                except Exception as exc:
                    await provider_runtime.record_external_call(
                        "beike_api",
                        capability="listing_search",
                        status="error",
                        latency_ms=int((time.monotonic() - started) * 1000),
                        units=1,
                        error=f"{type(exc).__name__}: {exc}"[:500],
                    )
                    raise
                await provider_runtime.record_external_call(
                    "beike_api",
                    capability="listing_search",
                    status="ok",
                    latency_ms=int((time.monotonic() - started) * 1000),
                    units=1,
                )
                stats["total"] = total
                url = "app-api"
                if not drafts:
                    log.info("crawl_api_end", page=page, total=total)
                    break
            else:
                url = build_list_url(
                    city.code, page=page, sort=sort, district=district, line=line
                )
                started = time.monotonic()
                try:
                    html = await fetcher.fetch_html(url)
                except Exception as exc:
                    await provider_runtime.record_external_call(
                        "beike_cdp",
                        capability="listing_search",
                        status="error",
                        latency_ms=int((time.monotonic() - started) * 1000),
                        units=1,
                        error=f"{type(exc).__name__}: {exc}"[:500],
                    )
                    raise
                drafts = parse_list(html, city.code)
                await provider_runtime.record_external_call(
                    "beike_cdp",
                    capability="listing_search",
                    status="ok",
                    latency_ms=int((time.monotonic() - started) * 1000),
                    units=1,
                )
            for draft in drafts:
                draft.raw["scope"] = scope
            stats["pages"] += 1
            stats["fetched"] += len(drafts)
            now = datetime.now(UTC)

            for draft in drafts:
                await _ingest_draft(
                    db,
                    city=city,
                    source=source,
                    task=task,
                    draft=draft,
                    now=now,
                    baseline=baseline,
                    stats=stats,
                    event_ids=event_ids,
                    seen_ids=seen_ids,
                    seen_drafts=seen_drafts,
                )

            await db.commit()
            log.info(
                "crawl_page_done",
                page=page,
                url=url,
                fetched=stats["fetched"],
                new=stats["new"],
                updated=stats["updated"],
            )

        if full_scan:
            complete = transport != "api" or (
                stats["total"] is not None and stats["pages"] * page_size >= stats["total"]
            )
            if not complete:
                stats["suspect_skipped"] = True
                log.warning(
                    "full_scan_partial_skip_suspect",
                    pages=stats["pages"],
                    total=stats["total"],
                )
            else:
                active = (
                    (
                        await db.execute(
                            select(Listing).where(
                                Listing.source_id == source.id,
                                Listing.city_id == city.id,
                                Listing.status.in_(
                                    [ListingStatus.active, ListingStatus.relisted]
                                ),
                                # 只判定同一采集范围内房源；旧范围无 scope，跳过以免误标
                                Listing.raw["scope"].astext == scope,
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
                for listing in active:
                    if listing.id in seen_ids:
                        listing.miss_count = 0
                        continue
                    listing.miss_count += 1
                    if listing.miss_count >= 2:
                        listing.status = ListingStatus.suspect
                        event = Event(
                            listing_id=listing.id,
                            type=EventType.suspect,
                            payload={
                                "miss_count": listing.miss_count,
                                "reason": "连续两次全量未出现，待人工核实",
                            },
                        )
                        db.add(event)
                        await db.flush()
                        event_ids.append(event.id)
                        stats["suspect"] += 1
                await db.commit()

        run = await db.get(Run, run.id)
        run.status = "done"
        run.finished_at = datetime.now(UTC)
        run.stats = stats
        await db.commit()

        notify_result = await notify_events(db, event_ids) if notify else None
        return {"run_id": run.id, **stats, "notify": notify_result}
    except Exception as exc:
        await db.rollback()
        run = await db.get(Run, run.id)
        if run is not None:
            run.status = "failed"
            run.error = str(exc)[:1000]
            run.finished_at = datetime.now(UTC)
            run.stats = stats
        if isinstance(exc, CaptchaRequiredError):
            task.enabled = False
            log.error("task_paused_captcha", task_id=task.id)
            try:
                admin_settings = await get_admin_settings(db)
                if admin_settings.get("pauseAlert", True):
                    await send_text(
                        db,
                        f"RentRadar 采集暂停：任务 {task.id} 触发验证码，已自动停用。",
                    )
            except Exception as alert_exc:
                log.warning("pause_alert_failed", error=str(alert_exc)[:200])
        await db.commit()
        log.error("crawl_failed", error=str(exc)[:500])
        raise
    finally:
        await fetcher.close()
