from collections import Counter
from datetime import datetime
from statistics import mean, median
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    City,
    Community,
    CommuteSample,
    DeliveryProbe,
    Job,
    JobStatus,
    Listing,
    ListingStatus,
    PoiCache,
    ProviderUsage,
    Run,
    Source,
    Task,
)
from app.services import agent_service, listing_service, task_service
from app.services.settings_service import (
    destination_key,
    get_commute_destination,
)
from app.services.settings_service import (
    get_admin_settings as runtime_get_admin_settings,
)
from app.services.settings_service import (
    update_admin_settings as runtime_update_admin_settings,
)

LINE5_SCOPE = "line:li110460696"


def _period() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m")


async def _latest_commute(db: AsyncSession) -> tuple[dict[int, int], Counter[int]]:
    destination = await get_commute_destination(db)
    key = destination_key(destination)
    stmt = select(
        CommuteSample.community_id, CommuteSample.duration_s, CommuteSample.fetched_at
    ).order_by(CommuteSample.community_id, CommuteSample.fetched_at.desc())
    if key:
        stmt = stmt.where(CommuteSample.destination_key == key)
    rows = (await db.execute(stmt)).all()
    latest: dict[int, int] = {}
    counts: Counter[int] = Counter()
    for community_id, duration_s, _ in rows:
        counts[community_id] += 1
        latest.setdefault(community_id, duration_s)
    return latest, counts


async def _community_rows(db: AsyncSession) -> list[dict]:
    counts = (
        select(Listing.community_id, func.count().label("listings"))
        .where(Listing.status == ListingStatus.active)
        .group_by(Listing.community_id)
        .subquery()
    )
    rows = (
        await db.execute(
            select(Community, counts.c.listings, PoiCache)
            .outerjoin(counts, Community.id == counts.c.community_id)
            .outerjoin(PoiCache, PoiCache.community_id == Community.id)
            .order_by(Community.id)
        )
    ).all()
    latest, samples = await _latest_commute(db)
    result = []
    for community, listing_count, poi in rows:
        result.append(
            {
                "id": community.id,
                "name": community.name,
                "district": community.district,
                "lng": float(community.lng) if community.lng is not None else None,
                "lat": float(community.lat) if community.lat is not None else None,
                "listings": int(listing_count or 0),
                "dining_count": poi.dining_count if poi else None,
                "daily_count": poi.daily_count if poi else None,
                "nightlife_count": poi.nightlife_count if poi else None,
                "commute_min": round(latest[community.id] / 60) if community.id in latest else None,
                "samples": samples.get(community.id, 0),
            }
        )
    return result


async def get_stats(db: AsyncSession, communities: list[dict] | None = None) -> dict:
    communities = communities if communities is not None else await _community_rows(db)
    scores = [
        int(item)
        for item in (
            await db.execute(select(Listing.score).where(Listing.score.is_not(None)))
        ).scalars()
    ]
    active_communities = (
        await db.execute(
            select(Listing.community_id).where(Listing.status == ListingStatus.active)
        )
    ).scalars().all()
    scored_communities = (
        await db.execute(select(Listing.community_id).where(Listing.score.is_not(None)))
    ).scalars().all()
    geo_ids = {item["id"] for item in communities if item["lng"] is not None}
    _, sample_counts = await _latest_commute(db)
    sample_ids = set(sample_counts)
    scored_geo = sum(1 for cid in scored_communities if cid in geo_ids)
    scored_commute = sum(1 for cid in scored_communities if cid in sample_ids)
    listings_no_geo = sum(
        1 for cid in active_communities if cid is None or cid not in geo_ids
    )
    listings_no_commute = sum(
        1 for cid in active_communities if cid is None or cid not in sample_ids
    )
    no_commute_but_geo = sum(
        1 for cid in active_communities if cid in geo_ids and cid not in sample_ids
    )
    usage = await db.get(ProviderUsage, ("amap", _period()))
    return {
        "listings": int(await db.scalar(select(func.count()).select_from(Listing)) or 0),
        "line5": int(
            await db.scalar(
                select(func.count())
                .select_from(Listing)
                .where(Listing.raw["scope"].astext == LINE5_SCOPE)
            )
            or 0
        ),
        "scored": len(scores),
        "ge75": sum(1 for score in scores if score >= 75),
        "scored_geo": scored_geo,
        "scored_commute": scored_commute,
        "avg_score": round(mean(scores), 1) if scores else 0,
        "median_score": round(median(scores), 1) if scores else 0,
        "max_score": max(scores) if scores else 0,
        "communities": len(communities),
        "geocoded": len(geo_ids),
        "commute_samples": int(
            await db.scalar(select(func.count()).select_from(CommuteSample)) or 0
        ),
        "commute_communities": int(
            await db.scalar(
                select(func.count(func.distinct(CommuteSample.community_id)))
            )
            or 0
        ),
        "poi_cache": sum(1 for item in communities if item["dining_count"] is not None),
        "probes": int(await db.scalar(select(func.count()).select_from(DeliveryProbe)) or 0),
        "listings_no_geo": listings_no_geo,
        "listings_no_commute": listings_no_commute,
        "poi_capped": sum(
            1 for item in communities if (item["dining_count"] or 0) >= 600
        ),
        "no_commute_but_geo": no_commute_but_geo,
        "amap_used": usage.used if usage else 0,
        "amap_limit": usage.limit_value if usage and usage.limit_value else 5000,
    }


async def list_runs(db: AsyncSession, limit: int = 20) -> list[dict]:
    runs = (
        (
            await db.execute(
                select(Run).order_by(Run.started_at.desc()).limit(max(1, min(limit, 100)))
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": run.id,
            "status": run.status,
            "stats": run.stats or {},
            "error": run.error,
            "started_at": run.started_at,
            "finished_at": run.finished_at,
        }
        for run in runs
    ]


async def overview(db: AsyncSession) -> dict:
    communities = await _community_rows(db)
    stats = await get_stats(db, communities)
    scored_geo = stats["scored_geo"]
    scored_commute = stats["scored_commute"]
    no_geo = stats["communities"] - stats["geocoded"]
    quality = [
        {
            "label": "缺坐标",
            "desc": f"{no_geo} 个小区 · {stats['listings_no_geo']} 套房受影响",
            "tone": "coral",
            "badge": "高优先",
        },
        {
            "label": "POI 封顶",
            "desc": f"{stats['poi_capped']} 个小区餐饮 count ≥ 600，密度区分度不足",
            "tone": "amber",
            "badge": "中",
        },
        {
            "label": "详情图",
            "desc": "列表只有封面；详情图/AI 尚未接入",
            "tone": "coral",
            "badge": "未接入",
        },
        {
            "label": "外卖样本",
            "desc": f"{stats['probes']} 条实测；仍缺午餐/晚餐",
            "tone": "amber",
            "badge": "部分",
        },
        {
            "label": "价格快照",
            "desc": f"{stats['listings']} 套在库，快照持续积累",
            "tone": "green",
            "badge": "正常",
        },
    ]
    return {
        "stats": stats,
        "funnel": [
            {"value": stats["line5"], "label": "5 号线"},
            {
                "value": stats["scored"],
                "label": "已评分",
                "drop": f"-{max(0, stats['line5'] - stats['scored'])} 硬过滤",
            },
            {
                "value": scored_geo,
                "label": "有坐标",
                "drop": f"-{stats['listings_no_geo']} 缺坐标",
            },
            {"value": scored_commute, "label": "有通勤"},
            {"value": 0, "label": "有图片/AI", "drop": "未接入"},
        ],
        "quality": quality,
        "runs": await list_runs(db, 10),
        "nextSteps": [
            {
                "title": "图片/AI：详情图 + pHash + Qwen-VL",
                "desc": "只对候选运行，不占高德额度；先做 Top 5，假房源需多信号交叉。",
            },
            {
                "title": "真实 Agent 工具运行时",
                "desc": "在规则版之上接 LLM 规划、工具白名单、trace/eval/cost/guardrail。",
            },
            {
                "title": "Top 10 候选跑 p50/p90",
                "desc": "4 时段 × 工作日；用深圳地铁官方接口替代部分高德调用。",
            },
            {
                "title": "地铁 / 开放数据",
                "desc": "深圳地铁 MinTimeJson、住建局参考租金；鉴权/额度/监控运行时已接入。",
            },
        ],
    }


async def candidates(db: AsyncSession, limit: int = 200) -> list[dict]:
    latest, samples = await _latest_commute(db)
    rows = (
        await db.execute(
            select(Listing, Source.code, City.code, Community, PoiCache)
            .join(Source, Listing.source_id == Source.id)
            .join(City, Listing.city_id == City.id)
            .outerjoin(Community, Listing.community_id == Community.id)
            .outerjoin(PoiCache, PoiCache.community_id == Community.id)
            .where(Listing.status == ListingStatus.active, Listing.score.is_not(None))
            .order_by(Listing.score.desc().nullslast(), Listing.id.desc())
            .limit(max(1, min(limit, 500)))
        )
    ).all()
    result = []
    for listing, source_code, city_code, community, poi in rows:
        item = listing_service._listing_dict(listing, source_code, city_code)
        item["score_reasons"] = listing.score_reasons or {}
        has_geo = bool(
            community
            and community.lng is not None
            and community.lat is not None
        )
        item["has_geo"] = has_geo
        item["has_commute"] = listing.community_id in latest
        item["commute_min"] = (
            round(latest[listing.community_id] / 60)
            if listing.community_id in latest
            else None
        )
        item["samples"] = samples.get(listing.community_id, 0) if listing.community_id else 0
        item["dining_count"] = poi.dining_count if poi else None
        item["daily_count"] = poi.daily_count if poi else None
        item["nightlife_count"] = poi.nightlife_count if poi else None
        result.append(item)
    return result


async def coverage(db: AsyncSession) -> dict:
    communities = await _community_rows(db)
    stats = await get_stats(db, communities)
    priority = sorted(
        [item for item in communities if item["lng"] is None],
        key=lambda item: item["listings"],
        reverse=True,
    )[:5]
    return {"stats": stats, "communities": communities, "priority": priority}


async def quality(db: AsyncSession) -> dict:
    communities = await _community_rows(db)
    stats = await get_stats(db, communities)
    geo_priority = sorted(
        [item for item in communities if item["lng"] is None],
        key=lambda item: item["listings"],
        reverse=True,
    )[:10]
    poi_capped = sorted(
        [item for item in communities if (item["dining_count"] or 0) >= 600],
        key=lambda item: item["dining_count"] or 0,
        reverse=True,
    )[:10]
    return {
        "stats": stats,
        "geoPriority": geo_priority,
        "poiCapped": poi_capped,
    }


async def agent_sessions(db: AsyncSession) -> list[dict]:
    return await agent_service.list_admin_sessions(db)


async def get_admin_settings(db: AsyncSession) -> dict:
    return await runtime_get_admin_settings(db)


async def update_admin_settings(db: AsyncSession, payload: dict) -> dict:
    return await runtime_update_admin_settings(db, payload)


async def _task_for_job(db: AsyncSession) -> Task | None:
    task = await db.scalar(
        select(Task).where(Task.enabled.is_(True)).order_by(Task.id).limit(1)
    )
    if task is not None:
        return task
    return await db.scalar(select(Task).order_by(Task.id).limit(1))


def _job_out(job: Job, calls: int | None) -> dict:
    return {
        "id": f"J-{job.id}",
        "type": job.type,
        "status": job.status.value if hasattr(job.status, "value") else str(job.status),
        "calls": calls,
        "createdAt": job.created_at.isoformat(),
    }


async def enqueue_analysis(db: AsyncSession, listing_ids: list[int]) -> dict | None:
    task = await _task_for_job(db)
    if task is None:
        return None
    job = Job(
        task_id=task.id,
        type="analysis",
        payload={"listing_ids": listing_ids},
        status=JobStatus.queued,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return _job_out(job, len(listing_ids) or None)


async def enqueue_sampling(
    db: AsyncSession, *, origin: str, count: int, buckets: list[str], modes: list[str]
) -> dict | None:
    task = await _task_for_job(db)
    if task is None:
        return None
    settings = await get_admin_settings(db)
    count = max(1, min(count, int(settings.get("batchCap") or 10)))
    job = Job(
        task_id=task.id,
        type="sampling",
        payload={
            "origin": origin,
            "count": count,
            "buckets": buckets,
            "modes": modes,
        },
        status=JobStatus.queued,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    calls = max(1, count) * max(1, len(buckets)) * max(1, len(modes))
    return _job_out(job, calls)


async def enqueue_geocode(db: AsyncSession, community_ids: list[int]) -> dict | None:
    task = await _task_for_job(db)
    if task is None:
        return None
    settings = await get_admin_settings(db)
    community_ids = community_ids[: max(1, int(settings.get("batchCap") or 10))]
    job = Job(
        task_id=task.id,
        type="geocode",
        payload={"community_ids": community_ids},
        status=JobStatus.queued,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return _job_out(job, len(community_ids) * 5 or None)


async def run_task_now(db: AsyncSession, task_id: int) -> int | None:
    return await task_service.run_task_now(db, task_id)


async def list_tasks(db: AsyncSession) -> list[dict]:
    return await task_service.list_tasks(db)
