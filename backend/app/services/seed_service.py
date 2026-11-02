from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

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
    User,
    Watchlist,
)


def _reasons(price: str, commute: str, condition: str, convenience: str, reputation: str) -> dict:
    return {
        "price": price,
        "commute": commute,
        "condition": condition,
        "convenience": convenience,
        "reputation": reputation,
        "freshness": "24 小时内新上架",
        "risk": [],
    }


SEED_LISTINGS = [
    {
        "code": "SZ2000000000000000001",
        "title": "整租·居里十舍 2室1厅 68㎡",
        "community": "居里十舍",
        "district": "龙岗区",
        "layout": "2室1厅",
        "area": 68,
        "orientation": "南",
        "floor": "中楼层",
        "rent": 4200,
        "tags": ["近地铁", "电梯", "精装"],
        "score": 88,
        "status": ListingStatus.active,
        "age_hours": 2,
        "reasons": _reasons(
            "比同小区中位价低 9%",
            "公交 32 分钟（p90 41 分钟）",
            "电梯/南向/中楼层",
            "1km 内 42 家餐饮",
            "近 12 个月 3 条噪音讨论，低置信",
        ),
    },
    {
        "code": "SZ2000000000000000002",
        "title": "整租·居里十舍 1室1厅 45㎡",
        "community": "居里十舍",
        "district": "龙岗区",
        "layout": "1室1厅",
        "area": 45,
        "orientation": "东南",
        "floor": "高楼层",
        "rent": 3300,
        "tags": ["近地铁", "电梯"],
        "score": 81,
        "status": ListingStatus.active,
        "age_hours": 26,
        "reasons": _reasons(
            "比同小区中位价低 5%",
            "公交 35 分钟（p90 44 分钟）",
            "电梯/东南向",
            "1km 内 42 家餐饮",
            "暂无高置信口碑",
        ),
    },
    {
        "code": "SZ2000000000000000003",
        "title": "整租·信义假日名城 3室2厅 89㎡",
        "community": "信义假日名城",
        "district": "龙岗区",
        "layout": "3室2厅",
        "area": 89,
        "orientation": "南北",
        "floor": "低楼层",
        "rent": 5600,
        "tags": ["电梯", "带花园"],
        "score": 76,
        "status": ListingStatus.active,
        "age_hours": 3,
        "reasons": _reasons(
            "与同户型中位价持平",
            "公交 41 分钟（p90 55 分钟）",
            "电梯/南北通透/低楼层",
            "1km 内 28 家餐饮",
            "暂无高置信口碑",
        ),
    },
    {
        "code": "SZ2000000000000000004",
        "title": "整租·龙悦居四期 2室1厅 62㎡",
        "community": "龙悦居四期",
        "district": "龙岗区",
        "layout": "2室1厅",
        "area": 62,
        "orientation": "南",
        "floor": "中楼层",
        "rent": 3900,
        "tags": ["近地铁", "电梯", "民水民电"],
        "score": 84,
        "status": ListingStatus.active,
        "age_hours": 30,
        "reasons": _reasons(
            "比同小区中位价低 12%",
            "公交 28 分钟（p90 36 分钟）",
            "电梯/南向",
            "1km 内 35 家餐饮",
            "近 12 个月 1 条漏水讨论，低置信",
        ),
    },
    {
        "code": "SZ2000000000000000005",
        "title": "整租·万科城 2室2厅 75㎡",
        "community": "万科城",
        "district": "龙岗区",
        "layout": "2室2厅",
        "area": 75,
        "orientation": "北",
        "floor": "高楼层",
        "rent": 4800,
        "tags": ["电梯", "公寓"],
        "score": 62,
        "status": ListingStatus.suspect,
        "age_hours": 48,
        "reasons": _reasons(
            "价格低于区间 18%",
            "公交 45 分钟（p90 60 分钟）",
            "电梯/北向",
            "1km 内 20 家餐饮",
            "图片疑似重复，待核实",
        ),
    },
    {
        "code": "SZ2000000000000000006",
        "title": "整租·中海怡翠山庄 3室2厅 96㎡",
        "community": "中海怡翠山庄",
        "district": "龙岗区",
        "layout": "3室2厅",
        "area": 96,
        "orientation": "南",
        "floor": "中楼层",
        "rent": 5200,
        "tags": ["电梯", "小区环境好"],
        "score": 73,
        "status": ListingStatus.active,
        "age_hours": 5,
        "reasons": _reasons(
            "比同户型中位价低 3%",
            "公交 44 分钟（p90 58 分钟）",
            "电梯/南向",
            "1km 内 24 家餐饮",
            "暂无高置信口碑",
        ),
    },
    {
        "code": "SZ2000000000000000007",
        "title": "整租·布吉慢城 1室1厅 40㎡",
        "community": "布吉慢城",
        "district": "龙岗区",
        "layout": "1室1厅",
        "area": 40,
        "orientation": "西",
        "floor": "低楼层",
        "rent": 2900,
        "tags": ["近地铁", "电梯"],
        "score": 69,
        "status": ListingStatus.active,
        "age_hours": 6,
        "reasons": _reasons(
            "与同户型中位价持平",
            "公交 38 分钟（p90 49 分钟）",
            "电梯/西向/低楼层",
            "1km 内 31 家餐饮",
            "暂无高置信口碑",
        ),
    },
    {
        "code": "SZ2000000000000000008",
        "title": "整租·信义假日名城 2室1厅 70㎡",
        "community": "信义假日名城",
        "district": "龙岗区",
        "layout": "2室1厅",
        "area": 70,
        "orientation": "南",
        "floor": "中楼层",
        "rent": 4500,
        "tags": ["电梯"],
        "score": 71,
        "status": ListingStatus.gone,
        "age_hours": 24 * 8,
        "reasons": _reasons(
            "与同户型中位价持平",
            "公交 40 分钟（p90 52 分钟）",
            "电梯/南向",
            "1km 内 28 家餐饮",
            "已下架",
        ),
    },
    {
        "code": "SZ2000000000000000009",
        "title": "整租·龙悦居四期 3室2厅 88㎡",
        "community": "龙悦居四期",
        "district": "龙岗区",
        "layout": "3室2厅",
        "area": 88,
        "orientation": "东南",
        "floor": "高楼层",
        "rent": 5100,
        "tags": ["近地铁", "电梯", "采光好"],
        "score": 79,
        "status": ListingStatus.active,
        "age_hours": 12,
        "reasons": _reasons(
            "比同户型中位价低 6%",
            "公交 30 分钟（p90 39 分钟）",
            "电梯/东南向/高楼层",
            "1km 内 35 家餐饮",
            "暂无高置信口碑",
        ),
    },
    {
        "code": "SZ2000000000000000010",
        "title": "整租·万科城 1室1厅 38㎡",
        "community": "万科城",
        "district": "龙岗区",
        "layout": "1室1厅",
        "area": 38,
        "orientation": "南",
        "floor": "中楼层",
        "rent": 3200,
        "tags": ["电梯", "公寓"],
        "score": 66,
        "status": ListingStatus.active,
        "age_hours": 96,
        "reasons": _reasons(
            "与同户型中位价持平",
            "公交 46 分钟（p90 61 分钟）",
            "电梯/南向",
            "1km 内 20 家餐饮",
            "暂无高置信口碑",
        ),
    },
    {
        "code": "SZ2000000000000000011",
        "title": "整租·居里十舍 2室2厅 80㎡",
        "community": "居里十舍",
        "district": "龙岗区",
        "layout": "2室2厅",
        "area": 80,
        "orientation": "南北",
        "floor": "高楼层",
        "rent": 5000,
        "tags": ["近地铁", "电梯", "精装", "降价"],
        "score": 90,
        "status": ListingStatus.active,
        "age_hours": 1,
        "reasons": _reasons(
            "比同小区中位价低 15%",
            "公交 32 分钟（p90 41 分钟）",
            "电梯/南北通透/高楼层",
            "1km 内 42 家餐饮",
            "近 12 个月 3 条噪音讨论，低置信",
        ),
    },
    {
        "code": "SZ2000000000000000012",
        "title": "整租·中海怡翠山庄 2室1厅 65㎡",
        "community": "中海怡翠山庄",
        "district": "龙岗区",
        "layout": "2室1厅",
        "area": 65,
        "orientation": "南",
        "floor": "中楼层",
        "rent": 4100,
        "tags": ["电梯", "重新上架"],
        "score": 74,
        "status": ListingStatus.relisted,
        "age_hours": 20,
        "reasons": _reasons(
            "比同户型中位价低 4%",
            "公交 44 分钟（p90 58 分钟）",
            "电梯/南向",
            "1km 内 24 家餐饮",
            "暂无高置信口碑",
        ),
    },
]


async def seed(db: AsyncSession) -> dict:
    existing = int(await db.scalar(select(func.count()).select_from(Listing)) or 0)
    if existing:
        return {"skipped": True, "listings": existing}

    now = datetime.now(UTC)
    sz = City(
        code="sz",
        name="深圳",
        domain_template="https://{city}.zu.ke.com",
        center_lng=114.0579,
        center_lat=22.5431,
    )
    sh = City(
        code="sh",
        name="上海",
        domain_template="https://{city}.zu.ke.com",
        center_lng=121.4737,
        center_lat=31.2304,
    )
    beike = Source(
        code="beike",
        name="贝壳租房",
        kind="html",
        rate_limit={"qps": 0.3, "daily": 2000},
    )
    lianjia = Source(
        code="lianjia",
        name="链家租房",
        kind="html",
        rate_limit={"qps": 0.3, "daily": 2000},
    )
    local_user = User(username="local", role="admin")
    db.add_all([sz, sh, beike, lianjia, local_user])
    await db.flush()

    communities = {}
    for name, district, lng, lat in [
        ("居里十舍", "龙岗区", 114.280728, 22.727079),
        ("信义假日名城", "龙岗区", 114.246000, 22.710000),
        ("龙悦居四期", "龙岗区", 114.228000, 22.698000),
        ("万科城", "龙岗区", 114.238000, 22.690000),
        ("中海怡翠山庄", "龙岗区", 114.260000, 22.718000),
        ("布吉慢城", "龙岗区", 114.210000, 22.680000),
    ]:
        community = Community(
            city_id=sz.id,
            name=name,
            district=district,
            lng=lng,
            lat=lat,
            coord_system="GCJ02",
            adcode="440307",
            geocode_confidence=0.9,
        )
        db.add(community)
        communities[name] = community
    await db.flush()

    task_fast = Task(
        name="贝壳-横岗租房快循环",
        city_id=sz.id,
        source_id=beike.id,
        filters={
            "min_rent": 3000,
            "max_rent": 6000,
            "districts": ["龙岗区"],
            "layout": "2室",
        },
        schedule={"fast_minutes": 10, "slow_minutes": 180},
        account_strategy="auto",
        proxy_strategy="direct",
    )
    task_slow = Task(
        name="链家-深圳全量慢循环",
        city_id=sz.id,
        source_id=lianjia.id,
        filters={},
        schedule={"fast_minutes": 60, "slow_minutes": 360},
        account_strategy="auto",
        proxy_strategy="direct",
    )
    db.add_all([task_fast, task_slow])
    await db.flush()

    db.add(
        Run(
            task_id=task_fast.id,
            status="done",
            started_at=now - timedelta(minutes=14),
            finished_at=now - timedelta(minutes=13),
            stats={"fetched": 30, "new": 2, "parse_errors": 0},
        )
    )

    for item in SEED_LISTINGS:
        first_seen = now - timedelta(hours=item["age_hours"])
        listing = Listing(
            source_id=beike.id,
            city_id=sz.id,
            community_id=communities[item["community"]].id,
            source_listing_id=item["code"],
            url=f"https://sz.zu.ke.com/zufang/{item['code']}.html",
            title=item["title"],
            community_name=item["community"],
            district=item["district"],
            layout=item["layout"],
            area=item["area"],
            orientation=item["orientation"],
            floor=item["floor"],
            rent=item["rent"],
            tags=item["tags"],
            agent_type="apartment",
            raw={"seed": True},
            score=item["score"],
            score_reasons=item["reasons"],
            status=item["status"],
            first_seen_at=first_seen,
            last_seen_at=now,
        )
        db.add(listing)
        await db.flush()

        rents = [
            item["rent"] + 300,
            item["rent"] + 200,
            item["rent"] + 100,
            item["rent"],
            item["rent"],
        ]
        if item["code"].endswith("0011"):
            rents = [5600, 5500, 5300, 5000, 5000]
        if item["code"].endswith("0008"):
            rents = [4700, 4600, 4500, 4500, 4500]
        for index, rent in enumerate(rents):
            db.add(
                Snapshot(
                    listing_id=listing.id,
                    rent=rent,
                    seen_at=now - timedelta(days=(len(rents) - index) * 2),
                )
            )

        if item["age_hours"] <= 72:
            db.add(
                Event(
                    listing_id=listing.id,
                    type=EventType.new,
                    payload={"rent": item["rent"], "score": item["score"]},
                    created_at=first_seen,
                )
            )
        if item["code"].endswith(("0001", "0011")):
            db.add(
                Event(
                    listing_id=listing.id,
                    type=EventType.price_drop,
                    payload={"old": rents[-2], "new": item["rent"], "pct": 0.06},
                    created_at=now - timedelta(hours=1),
                )
            )
        if item["status"] == ListingStatus.gone:
            db.add(
                Event(
                    listing_id=listing.id,
                    type=EventType.gone,
                    payload={"reason": "连续两次成功运行未出现"},
                    created_at=now - timedelta(days=1),
                )
            )
        if item["status"] == ListingStatus.suspect:
            db.add(
                Event(
                    listing_id=listing.id,
                    type=EventType.suspect,
                    payload={"signals": ["price_outlier", "image_reuse"]},
                    created_at=now - timedelta(hours=6),
                )
            )

    first_listing = (
        await db.execute(
            select(Listing).where(Listing.source_listing_id == "SZ2000000000000000001")
        )
    ).scalar_one()
    db.add(
        Watchlist(
            user_id=local_user.id,
            listing_id=first_listing.id,
            state="seen",
            note="联系过，等回复",
        )
    )

    await db.commit()
    return {"skipped": False, "listings": len(SEED_LISTINGS), "cities": 2, "sources": 2}
