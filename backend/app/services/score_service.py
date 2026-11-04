import math
from datetime import UTC, datetime
from statistics import median

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Listing, ListingStatus, PoiCache
from app.services import (
    commute_service,
    reference_rent_service,
    reputation_service,
)
from app.services.settings_service import destination_key, get_commute_destination


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _hours_since(value: datetime) -> float:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return max(0.0, (datetime.now(UTC) - value).total_seconds() / 3600)


def _passes_filters(listing: Listing, filters: dict) -> tuple[bool, str]:
    rent = listing.rent
    area = float(listing.area) if listing.area is not None else None
    if filters.get("min_rent") is not None and (rent is None or rent < int(filters["min_rent"])):
        return False, "低于租金下限"
    if filters.get("max_rent") is not None and (rent is None or rent > int(filters["max_rent"])):
        return False, "高于租金上限"
    if filters.get("min_area") is not None and (area is None or area < float(filters["min_area"])):
        return False, "面积小于下限"
    if filters.get("max_area") is not None and (area is None or area > float(filters["max_area"])):
        return False, "面积大于上限"
    layout = filters.get("layout")
    if layout and layout not in (listing.layout or ""):
        return False, "户型不符"
    districts = filters.get("districts")
    if districts and listing.district not in districts:
        return False, "区域不符"
    for word in filters.get("exclude_keywords") or []:
        if word and word in (listing.title or ""):
            return False, f"命中排除词：{word}"
    return True, ""


async def score_listing(
    db: AsyncSession, listing: Listing, filters: dict | None = None
) -> tuple[int, dict] | None:
    filters = filters or {}
    passed, reason = _passes_filters(listing, filters)
    if not passed:
        return None

    reasons: dict = {}
    total = 0.0

    # 性价比：同小区同户型活跃房源中位价，样本不足时回落到同区同户型
    price_score = 0.5
    price_reason = "同小区样本不足（估算）"
    price_scope = "同小区"
    rents: list[int] = []
    if listing.community_id and listing.layout and listing.rent:
        rows = (
            (
                await db.execute(
                    select(Listing.rent).where(
                        Listing.community_id == listing.community_id,
                        Listing.layout == listing.layout,
                        Listing.status == ListingStatus.active,
                        Listing.rent.is_not(None),
                    )
                )
            )
            .scalars()
            .all()
        )
        rents = [int(item) for item in rows if item]
    if len(rents) < 3 and listing.district and listing.layout and listing.rent:
        rows = (
            (
                await db.execute(
                    select(Listing.rent).where(
                        Listing.city_id == listing.city_id,
                        Listing.district == listing.district,
                        Listing.layout == listing.layout,
                        Listing.status == ListingStatus.active,
                        Listing.rent.is_not(None),
                    )
                )
            )
            .scalars()
            .all()
        )
        district_rents = [int(item) for item in rows if item]
        if len(district_rents) >= 3:
            rents = district_rents
            price_scope = "同区"
    reference = await reference_rent_service.latest_for_listing(db, listing)
    if reference and listing.rent:
        mid = float(reference["monthly_rent"])
        delta = (mid - listing.rent) / mid
        price_score = _clamp(0.5 + delta / 0.4)
        direction = "低" if delta >= 0 else "高"
        price_reason = (
            f"比参考租金{direction} {abs(delta) * 100:.0f}%"
            f"（¥{mid:.0f}，{reference['reference_month']}，{reference['source']}）"
        )
        reasons["reference_rent"] = reference
    elif len(rents) >= 3 and listing.rent:
        mid = float(median(rents))
        delta = (mid - listing.rent) / mid
        price_score = _clamp(0.5 + delta / 0.4)
        direction = "低" if delta >= 0 else "高"
        price_reason = (
            f"比{price_scope}同户型中位价{direction} {abs(delta) * 100:.0f}%（中位 ¥{mid:.0f}）"
        )
    reasons["price"] = price_reason
    total += 35 * price_score

    # 通勤：小区 → 公司，多时段样本取 p50
    commute_score = 0.5
    commute_reason = "通勤样本缺失（暂按中性 50% 计分）"
    destination = await get_commute_destination(db)
    if listing.community_id and destination:
        key = destination_key(destination)
        stats = (
            await commute_service.community_stats(
                db, listing.community_id, key, destination=destination
            )
            if key
            else None
        )
        if stats is not None:
            minutes = stats["p50_min"]
            if minutes <= 30:
                commute_score = 1.0
            elif minutes >= 60:
                commute_score = 0.0
            else:
                commute_score = (60 - minutes) / 30
            label = "地铁+步行" if stats["mode"] == "metro" else "公共交通"
            commute_reason = f"{label} p50 {minutes:.0f} 分钟"
            if stats.get("p90_min") is not None and stats.get("multi_bucket"):
                commute_reason += f" / p90 {stats['p90_min']:.0f} 分钟"
            commute_reason += f"（{stats['samples']} 个样本/{stats['bucket_count']} 个时段）"
            if stats.get("provider") == "szmc":
                commute_reason += " · 深圳地铁官方"
            if stats.get("static"):
                commute_reason += " · 时刻表估算，无时段波动"
            if destination.get("example"):
                commute_reason += " · 示例目的地址，请修改"
    reasons["commute"] = commute_reason
    total += 25 * commute_score

    tags = set(listing.tags or [])
    condition = 0.3
    condition_notes = []
    if "电梯" in tags:
        condition += 0.3
        condition_notes.append("电梯")
    if "精装" in tags:
        condition += 0.15
        condition_notes.append("精装")
    if listing.orientation in {"南", "东南", "南北"}:
        condition += 0.15
        condition_notes.append(f"{listing.orientation}向")
    if listing.floor == "中楼层":
        condition += 0.1
        condition_notes.append("中楼层")
    elif listing.floor == "高楼层":
        condition += 0.05
        condition_notes.append("高楼层")
    if listing.area and 30 <= float(listing.area) <= 100:
        condition += 0.1
        condition_notes.append(f"{float(listing.area):.0f}㎡")
    if listing.area and float(listing.area) < 25:
        condition = min(condition, 0.15)
        condition_notes.append("面积偏小")
    condition = _clamp(condition)
    reasons["condition"] = " / ".join(condition_notes) if condition_notes else "信息有限（估算）"
    total += 15 * condition

    convenience_score = 0.5
    convenience_reason = "待接入 POI（估算）"
    if listing.community_id:
        cache = await db.get(PoiCache, listing.community_id)
        if cache is not None:
            dining = cache.dining_count or 0
            daily = cache.daily_count or 0
            dining_score = min(1.0, math.log10(dining + 1) / math.log10(200))
            daily_score = min(1.0, math.log10(daily + 1) / math.log10(40))
            convenience_score = 0.7 * dining_score + 0.3 * daily_score
            convenience_reason = f"1km 餐饮 {dining} 家 / 便利店超市菜场 {daily} 家（周边）"
    reasons["convenience"] = convenience_reason
    total += 10 * convenience_score

    reputation_summary = await reputation_service.community_summary(
        db, listing.community_id
    )
    reputation_score, reputation_reason, reputation_status = (
        reputation_service.summarize_for_score(reputation_summary)
    )
    reasons["reputation"] = reputation_reason
    reasons["reputation_status"] = reputation_status
    reasons["reputation_evidence"] = int(
        (reputation_summary or {}).get("count") or 0
    )
    total += 10 * reputation_score

    age_hours = _hours_since(listing.first_seen_at)
    if age_hours <= 6:
        freshness = 1.0
        freshness_text = f"新上架 {age_hours:.0f} 小时"
    elif age_hours <= 24:
        freshness = 0.6
        freshness_text = f"上架 {age_hours:.0f} 小时"
    elif age_hours <= 72:
        freshness = 0.3
        freshness_text = f"上架 {age_hours / 24:.1f} 天"
    else:
        freshness = 0.1
        freshness_text = f"上架 {age_hours / 24:.0f} 天"
    reasons["freshness"] = freshness_text
    total += 5 * freshness

    risk_notes: list[str] = []
    risk_penalty = 0
    if listing.area and float(listing.area) < 25:
        risk_notes.append("面积小于 25㎡")
        risk_penalty += 5
    reasons["risk"] = risk_notes
    reasons["components"] = {
        "price": round(35 * price_score, 1),
        "commute": round(25 * commute_score, 1),
        "condition": round(15 * condition, 1),
        "convenience": round(10 * convenience_score, 1),
        "reputation": round(10 * reputation_score, 1),
        "freshness": round(5 * freshness, 1),
        "risk": -risk_penalty,
    }
    reasons["weights"] = {
        "price": 35,
        "commute": 25,
        "condition": 15,
        "convenience": 10,
        "reputation": 10,
        "freshness": 5,
    }
    total = max(0, min(100, round(total - risk_penalty)))
    return total, reasons
