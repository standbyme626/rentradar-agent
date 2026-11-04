"""Read-only tool registry for the conversational agent.

Every tool has a small, explicit argument model and returns a compact payload
plus a one-line summary that is safe to show in the admin trace.  The planner
(LLM strict-JSON plan or deterministic rules) can only invoke the names listed
here; ``save_monitor`` is the single write tool and is reserved for the
deterministic "save this search" path.
"""

import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AgentMonitor,
    City,
    Listing,
    ListingStatus,
    PoiCache,
    Snapshot,
    Source,
)
from app.services import commute_service, listing_service
from app.services.settings_service import (
    destination_key,
    get_commute_destination,
)

DISTRICTS = (
    "福田区",
    "罗湖区",
    "南山区",
    "宝安区",
    "龙华区",
    "龙岗区",
    "盐田区",
    "光明区",
    "坪山区",
    "大鹏新区",
)
LAYOUTS = ("1室", "2室", "3室")
MUSTS = ("电梯", "近地铁", "精装", "南向")
WRITE_TOOLS = {"save_monitor"}


class ToolArgumentError(ValueError):
    pass


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SearchArgs(_StrictModel):
    budget: int | None = Field(default=None, ge=500, le=50000)
    commute: int | None = Field(default=None, ge=5, le=180)
    layout: Literal["1室", "2室", "3室"] | None = None
    district: str | None = None
    must: list[str] = Field(default_factory=list, max_length=4)
    limit: int = Field(default=6, ge=1, le=10)
    sort_by_commute: bool = False

    @model_validator(mode="after")
    def _check_enums(self) -> "SearchArgs":
        if self.district is not None and self.district not in DISTRICTS:
            raise ValueError(f"不支持的区域：{self.district}")
        self.must = [item for item in self.must if item in MUSTS]
        if self.layout is not None and self.layout not in LAYOUTS:
            raise ValueError(f"不支持的户型：{self.layout}")
        return self


class ListingArgs(_StrictModel):
    listing_id: int = Field(ge=1)


class CompareArgs(_StrictModel):
    listing_ids: list[int] = Field(min_length=2, max_length=4)


class CommuteArgs(_StrictModel):
    listing_id: int | None = Field(default=None, ge=1)
    community_id: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _one_target(self) -> "CommuteArgs":
        if (self.listing_id is None) == (self.community_id is None):
            raise ValueError("listing_id 与 community_id 二选一")
        return self


class PriceArgs(_StrictModel):
    listing_id: int = Field(ge=1)
    points: int = Field(default=20, ge=1, le=50)


class MonitorArgs(_StrictModel):
    name: str = Field(min_length=1, max_length=128)
    conditions: dict = Field(default_factory=dict)


TOOL_SPECS: tuple[dict[str, Any], ...] = (
    {
        "name": "search_listings",
        "description": "按预算/通勤/户型/区域/硬条件检索本地已评分房源，返回最多 10 套候选。",
        "read_only": True,
        "args_model": SearchArgs,
        "args": {
            "budget": "int 500-50000，可空",
            "commute": "int 5-180 分钟，可空",
            "layout": "1室|2室|3室，可空",
            "district": "深圳行政区，可空",
            "must": "电梯|近地铁|精装|南向 的子集",
            "limit": "1-10，默认 6",
            "sort_by_commute": "bool，默认 false",
        },
    },
    {
        "name": "get_listing",
        "description": "读取一套房源的详情：评分拆解、价格快照、通勤 p50/p90、口碑证据。",
        "read_only": True,
        "args_model": ListingArgs,
        "args": {"listing_id": "int，可用 $top 指代本次搜索第一套"},
    },
    {
        "name": "compare_listings",
        "description": "横向对比 2-4 套房源的价格、面积、通勤和评分。",
        "read_only": True,
        "args_model": CompareArgs,
        "args": {"listing_ids": "2-4 个 int，可用 $top3 指代前三套"},
    },
    {
        "name": "commute_lookup",
        "description": "查询小区的真实通勤样本（p50/p90、时段数、方向）。",
        "read_only": True,
        "args_model": CommuteArgs,
        "args": {"listing_id": "int 或 $top", "community_id": "int，二者选一"},
    },
    {
        "name": "price_history",
        "description": "查询房源价格快照与涨跌。",
        "read_only": True,
        "args_model": PriceArgs,
        "args": {"listing_id": "int 或 $top", "points": "1-50，默认 20"},
    },
    {
        "name": "save_monitor",
        "description": "把当前条件保存为监控；只允许用户在明确说“保存/监控”时使用。",
        "read_only": False,
        "args_model": MonitorArgs,
        "args": {"name": "str", "conditions": "当前筛选条件对象"},
    },
)


def _spec(name: str) -> dict[str, Any] | None:
    return next((item for item in TOOL_SPECS if item["name"] == name), None)


def allowed_tools() -> list[str]:
    return [item["name"] for item in TOOL_SPECS]


def planner_tools() -> list[str]:
    return [item["name"] for item in TOOL_SPECS if item["name"] not in WRITE_TOOLS]


def prompt_catalog() -> str:
    lines = []
    for item in TOOL_SPECS:
        if item["name"] in WRITE_TOOLS:
            continue
        args = "；".join(f"{key}: {value}" for key, value in item["args"].items())
        lines.append(f"- {item['name']}：{item['description']} 参数：{args}")
    return "\n".join(lines)


def native_tool_schemas() -> list[dict[str, Any]]:
    """OpenAI-compatible function schemas for native tool_calls planning."""
    schemas: list[dict[str, Any]] = []
    for item in TOOL_SPECS:
        if item["name"] in WRITE_TOOLS:
            continue
        schema = item["args_model"].model_json_schema()
        properties = schema.get("properties") or {}
        for key in ("listing_id", "listing_ids"):
            prop = properties.get(key)
            if not prop:
                continue
            properties[key] = {
                "anyOf": [
                    prop,
                    {
                        "type": "string",
                        "enum": ["$top", "$top3", "$top_ids"],
                    },
                ],
                "description": (
                    str(prop.get("description") or "")
                    + " 可引用本次搜索结果：$top/$top3/$top_ids"
                ).strip(),
            }
        schemas.append(
            {
                "type": "function",
                "function": {
                    "name": item["name"],
                    "description": item["description"],
                    "parameters": schema,
                },
            }
        )
    return schemas


def normalize_native_calls(calls: list[dict[str, Any]]) -> list[dict]:
    """Validate native tool_calls into the same step format as JSON plans."""
    steps: list[dict] = []
    for call in calls[:8]:
        name = str(call.get("name") or "").strip()
        if name not in planner_tools():
            raise ToolArgumentError(f"规划包含不允许的工具：{name}")
        args = call.get("arguments")
        if not isinstance(args, dict):
            raise ToolArgumentError(f"{name} 的 tool_calls 参数不是 JSON 对象")
        _validate_plan_args(name, args)
        steps.append(
            {
                "tool": name,
                "args": _resolve_static_args(args),
                "reason": "模型原生工具调用",
            }
        )
    if not steps:
        raise ToolArgumentError("模型没有选择工具")
    if steps[0]["tool"] != "search_listings":
        raise ToolArgumentError("规划第一步必须是 search_listings")
    return steps


def validate_call(name: str, args: dict | None) -> dict:
    spec = _spec(name)
    if spec is None:
        raise ToolArgumentError(f"未知工具：{name}")
    try:
        model = spec["args_model"].model_validate(args or {})
    except ValidationError as exc:
        errors = "; ".join(
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exc.errors()
        )
        raise ToolArgumentError(f"{name} 参数错误：{errors}") from exc
    return model.model_dump(exclude_none=True)


def normalize_plan(payload: Any) -> list[dict]:
    """Validate a strict-JSON planner payload into executable steps."""
    if not isinstance(payload, dict):
        raise ToolArgumentError("规划结果必须是 JSON 对象")
    raw_steps = payload.get("steps")
    if not isinstance(raw_steps, list) or not raw_steps:
        raise ToolArgumentError("规划结果缺少 steps")
    steps: list[dict] = []
    for raw in raw_steps[:8]:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("tool") or "").strip()
        if name not in planner_tools():
            raise ToolArgumentError(f"规划包含不允许的工具：{name}")
        args = raw.get("args")
        if not isinstance(args, dict):
            args = {}
        _validate_plan_args(name, args)
        steps.append(
            {
                "tool": name,
                "args": _resolve_static_args(args),
                "reason": str(raw.get("reason") or "")[:160],
            }
        )
    if not steps:
        raise ToolArgumentError("规划结果没有可用步骤")
    if steps[0]["tool"] != "search_listings":
        raise ToolArgumentError("规划第一步必须是 search_listings")
    return steps


def _validate_plan_args(name: str, args: dict) -> None:
    probe: dict[str, Any] = {}
    for key, value in args.items():
        if value == "$top":
            probe[key] = 1
        elif value == "$top3":
            probe[key] = [1, 2]
        elif value == "$top_ids":
            probe[key] = [1, 2]
        elif (
            isinstance(value, list)
            and value
            and all(item in {"$top3", "$top_ids", "$top"} for item in value)
        ):
            probe[key] = [1, 2]
        else:
            probe[key] = value
    validate_call(name, probe)


def _resolve_static_args(args: dict) -> dict:
    """Keep placeholder strings for deferred resolution, validate the rest."""
    placeholders = {"$top", "$top3", "$top_ids"}
    resolved: dict[str, Any] = {}
    for key, value in args.items():
        if isinstance(value, str) and value in placeholders:
            resolved[key] = value
        elif isinstance(value, list) and value and all(
            isinstance(item, str) and item in placeholders for item in value
        ):
            resolved[key] = value[0]
        else:
            resolved[key] = value
    return resolved


def rule_plan(message: str, conditions: dict) -> list[dict]:
    """Deterministic fallback planner used when the LLM is unavailable."""
    args: dict[str, Any] = {
        "limit": 6,
        "must": list(conditions.get("must") or []),
    }
    for key in ("budget", "commute", "layout", "district"):
        if conditions.get(key) is not None:
            args[key] = conditions[key]
    sort_by_commute = any(word in message for word in ("通勤", "近一点", "近", "地铁"))
    if sort_by_commute:
        args["sort_by_commute"] = True
    steps: list[dict] = [
        {"tool": "search_listings", "args": args, "reason": "按条件检索本地候选"}
    ]
    if any(word in message for word in ("对比", "比较")):
        steps.append(
            {
                "tool": "compare_listings",
                "args": {"listing_ids": "$top3"},
                "reason": "用户要求对比",
            }
        )
    elif any(word in message for word in ("价格", "降价", "走势", "涨幅", "历史")):
        steps.append(
            {
                "tool": "price_history",
                "args": {"listing_id": "$top"},
                "reason": "用户关心价格变化",
            }
        )
    elif any(word in message for word in ("通勤", "多久", "分钟", "地铁")):
        steps.append(
            {
                "tool": "commute_lookup",
                "args": {"listing_id": "$top"},
                "reason": "用户关心通勤",
            }
        )
    elif any(word in message for word in ("详情", "评分", "为什么", "看看")):
        steps.append(
            {
                "tool": "get_listing",
                "args": {"listing_id": "$top"},
                "reason": "用户要看详情",
            }
        )
    return steps


def _placeholder_values(value: Any, cards: list[dict]) -> Any:
    if value == "$top":
        return cards[0]["id"] if cards else None
    if value == "$top3":
        return [item["id"] for item in cards[:3]]
    if value == "$top_ids":
        return [item["id"] for item in cards]
    return value


def resolve_args(args: dict, cards: list[dict]) -> dict:
    resolved = {key: _placeholder_values(value, cards) for key, value in args.items()}
    return {key: value for key, value in resolved.items() if value is not None}


async def _latest_commute(db: AsyncSession) -> dict[int, dict]:
    destination = await get_commute_destination(db)
    key = destination_key(destination)
    if key is None:
        return {}
    return await commute_service.bulk_stats(db, key, destination=destination)


async def search_cards(
    db: AsyncSession, conditions: dict, *, limit: int = 6, sort_by_commute: bool = False
) -> tuple[list[dict], dict]:
    """Shared local search used by both the agent and the search tool."""
    total = int(
        await db.scalar(
            select(func.count())
            .select_from(Listing)
            .where(Listing.status == ListingStatus.active, Listing.score.is_not(None))
        )
        or 0
    )
    stmt = (
        select(Listing, Source.code, City.code, PoiCache)
        .join(Source, Listing.source_id == Source.id)
        .join(City, Listing.city_id == City.id)
        .outerjoin(PoiCache, PoiCache.community_id == Listing.community_id)
        .where(Listing.status == ListingStatus.active, Listing.score.is_not(None))
    )
    if conditions.get("budget"):
        stmt = stmt.where(Listing.rent <= int(conditions["budget"]))
    if conditions.get("layout"):
        stmt = stmt.where(Listing.layout.ilike(f"%{conditions['layout']}%"))
    if conditions.get("district"):
        stmt = stmt.where(Listing.district == conditions["district"])
    must = set(conditions.get("must") or [])
    for tag in must - {"南向"}:
        stmt = stmt.where(Listing.tags.contains([tag]))
    if "南向" in must:
        stmt = stmt.where(Listing.orientation.ilike("%南%"))
    stmt = stmt.order_by(Listing.score.desc().nullslast(), Listing.id.desc()).limit(100)
    rows = (await db.execute(stmt)).all()
    commute = await _latest_commute(db)
    max_commute = conditions.get("commute")
    cards = []
    for listing, source_code, city_code, poi in rows:
        stats = commute.get(listing.community_id)
        minutes = round(stats["p50_min"]) if stats else None
        if max_commute is not None and (minutes is None or minutes > int(max_commute)):
            continue
        item = listing_service._listing_dict(listing, source_code, city_code)
        item["community_id"] = listing.community_id
        item["score_reasons"] = listing.score_reasons or {}
        item["commute_min"] = minutes
        item["commute_p50"] = stats["p50_min"] if stats else None
        item["commute_p90"] = stats["p90_min"] if stats else None
        item["commute_buckets"] = stats["bucket_count"] if stats else 0
        item["commute_static"] = stats["static"] if stats else None
        item["samples"] = stats["samples"] if stats else 0
        item["dining_count"] = poi.dining_count if poi else None
        item["daily_count"] = poi.daily_count if poi else None
        item["nightlife_count"] = poi.nightlife_count if poi else None
        cards.append(item)
    if sort_by_commute:
        cards.sort(
            key=lambda item: item["commute_min"]
            if item["commute_min"] is not None
            else 999
        )
    counts = {
        "total": total,
        "filtered": len(rows),
        "final": min(len(cards), limit),
    }
    return cards[:limit], counts


async def _resolve_listing(db: AsyncSession, listing_id: int) -> Listing | None:
    return await db.get(Listing, int(listing_id))


async def _tool_search(db: AsyncSession, args: dict, base: dict) -> tuple[dict, str]:
    conditions = dict(base)
    for key in ("budget", "commute", "layout", "district"):
        if args.get(key) is not None:
            conditions[key] = args[key]
    if args.get("must") is not None:
        conditions["must"] = args["must"]
    cards, counts = await search_cards(
        db,
        conditions,
        limit=int(args.get("limit") or 6),
        sort_by_commute=bool(args.get("sort_by_commute")),
    )
    summary = f"{len(cards)} 套候选（硬过滤后 {counts['filtered']} 套）"
    return {"cards": cards, "counts": counts, "conditions": conditions}, summary


async def _tool_listing(db: AsyncSession, args: dict, _base: dict) -> tuple[dict, str]:
    detail = await listing_service.get_listing_detail(db, int(args["listing_id"]), 0)
    if detail is None:
        return {"error": "listing not found"}, "房源不存在"
    compact = {
        "id": detail["id"],
        "title": detail.get("title"),
        "community_name": detail.get("community_name"),
        "district": detail.get("district"),
        "layout": detail.get("layout"),
        "area": detail.get("area"),
        "rent": detail.get("rent"),
        "score": detail.get("score"),
        "score_reasons": detail.get("score_reasons") or {},
        "commute_stats": detail.get("commute_stats"),
        "snapshots": (detail.get("snapshots") or [])[-12:],
        "reputation": detail.get("reputation"),
        "image_analysis": detail.get("image_analysis"),
    }
    summary = (
        f"{compact.get('community_name') or compact.get('title')} "
        f"¥{compact.get('rent')} · {compact.get('score')} 分"
    )
    return compact, summary


async def _tool_compare(db: AsyncSession, args: dict, _base: dict) -> tuple[dict, str]:
    items = []
    for listing_id in args["listing_ids"]:
        detail = await listing_service.get_listing_detail(db, int(listing_id), 0)
        if detail is None:
            continue
        items.append(
            {
                "id": detail["id"],
                "community_name": detail.get("community_name"),
                "layout": detail.get("layout"),
                "area": detail.get("area"),
                "rent": detail.get("rent"),
                "score": detail.get("score"),
                "commute_p50": (detail.get("commute_stats") or {}).get("p50_min"),
                "commute_p90": (detail.get("commute_stats") or {}).get("p90_min"),
                "score_reasons": detail.get("score_reasons") or {},
            }
        )
    return {"items": items}, f"对比 {len(items)} 套房源"


async def _tool_commute(db: AsyncSession, args: dict, _base: dict) -> tuple[dict, str]:
    community_id = args.get("community_id")
    if community_id is None and args.get("listing_id") is not None:
        listing = await _resolve_listing(db, int(args["listing_id"]))
        if listing is None:
            return {"error": "listing not found"}, "房源不存在"
        community_id = listing.community_id
    if community_id is None:
        return {"error": "no community"}, "该房源没有小区坐标"
    destination = await get_commute_destination(db)
    key = destination_key(destination)
    if key is None:
        return {"error": "no destination"}, "未配置通勤目的地"
    stats = await commute_service.community_stats(
        db, int(community_id), key, destination=destination
    )
    if stats is None:
        return {"community_id": community_id, "stats": None}, "暂无通勤样本"
    summary = f"通勤 p50 {stats['p50_min']} 分钟 / p90 {stats['p90_min']} 分钟"
    return {"community_id": community_id, "stats": stats}, summary


async def _tool_price(db: AsyncSession, args: dict, _base: dict) -> tuple[dict, str]:
    listing = await _resolve_listing(db, int(args["listing_id"]))
    if listing is None:
        return {"error": "listing not found"}, "房源不存在"
    snapshots = (
        (
            await db.execute(
                select(Snapshot)
                .where(Snapshot.listing_id == listing.id)
                .order_by(Snapshot.seen_at.desc())
                .limit(int(args.get("points") or 20))
            )
        )
        .scalars()
        .all()
    )
    points = [
        {"rent": item.rent, "seen_at": item.seen_at.isoformat()}
        for item in reversed(snapshots)
    ]
    if not points:
        return {"listing_id": listing.id, "points": []}, "暂无价格快照"
    rents = [int(item["rent"]) for item in points]
    change = None
    if len(rents) >= 2 and rents[0]:
        change = round((rents[-1] - rents[0]) / rents[0] * 100, 1)
    return {
        "listing_id": listing.id,
        "points": points,
        "low": min(rents),
        "high": max(rents),
        "latest": rents[-1],
        "change_pct": change,
    }, f"{len(points)} 个价格点 · 最新 ¥{rents[-1]}"


async def _tool_save_monitor(db: AsyncSession, args: dict, base: dict, *, user_id: int):
    conditions = {**base, **(args.get("conditions") or {})}
    monitor = AgentMonitor(
        id=f"M-{uuid.uuid4().hex[:6].upper()}",
        user_id=user_id,
        name=str(args["name"])[:128],
        conditions=conditions,
    )
    db.add(monitor)
    await db.commit()
    await db.refresh(monitor)
    return {"id": monitor.id, "name": monitor.name}, f"监控已保存：{monitor.name}"


async def execute(
    db: AsyncSession,
    tool: str,
    args: dict,
    *,
    base_conditions: dict,
    cards: list[dict],
    user_id: int,
) -> tuple[dict, str, dict]:
    """Execute one validated tool call; returns (result, summary, resolved_args)."""
    spec = _spec(tool)
    if spec is None:
        raise ToolArgumentError(f"未知工具：{tool}")
    resolved = resolve_args(args, cards)
    call_args = validate_call(tool, resolved)
    if tool == "search_listings":
        result, summary = await _tool_search(db, call_args, base_conditions)
    elif tool == "get_listing":
        result, summary = await _tool_listing(db, call_args, base_conditions)
    elif tool == "compare_listings":
        result, summary = await _tool_compare(db, call_args, base_conditions)
    elif tool == "commute_lookup":
        result, summary = await _tool_commute(db, call_args, base_conditions)
    elif tool == "price_history":
        result, summary = await _tool_price(db, call_args, base_conditions)
    elif tool == "save_monitor":
        result, summary = await _tool_save_monitor(
            db, call_args, base_conditions, user_id=user_id
        )
    else:  # pragma: no cover - guarded by validate_call
        raise ToolArgumentError(f"工具未实现：{tool}")
    return result, summary, call_args
