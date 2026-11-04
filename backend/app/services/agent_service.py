import asyncio
import json
import re
import time
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models import (
    AgentMonitor,
    AgentSession,
    AgentToolCall,
    Job,
    JobStatus,
    Listing,
    ListingStatus,
    Task,
)
from app.services import agent_tools, guardrails, llm_service
from app.services.commute_service import COMMUTE_BUCKETS
from app.services.settings_service import (
    get_admin_settings,
    get_commute_destination,
    set_commute_destination,
)

log = get_logger("agent")

DISTRICTS = {
    "福田区": "福田区",
    "罗湖区": "罗湖区",
    "南山区": "南山区",
    "宝安区": "宝安区",
    "龙华区": "龙华区",
    "龙岗区": "龙岗区",
    "盐田区": "盐田区",
    "光明区": "光明区",
    "坪山区": "坪山区",
    "大鹏新区": "大鹏新区",
    "福田": "福田区",
    "罗湖": "罗湖区",
    "南山": "南山区",
    "宝安": "宝安区",
    "龙华": "龙华区",
    "龙岗": "龙岗区",
    "盐田": "盐田区",
    "光明": "光明区",
    "坪山": "坪山区",
    "大鹏": "大鹏新区",
}
LAYOUTS = (
    (r"(两居|二居|2居|两室|2室)", "2室"),
    (r"(一居|1居|一室|1室)", "1室"),
    (r"(三居|3居|三室|3室)", "3室"),
    (r"(单间|开间)", "1室"),
)


def _extract_budget(text: str) -> int | None:
    patterns = (
        r"预算\s*(?:压到|降到|控制在|改到)?\s*(\d{3,5})",
        r"(\d{3,5})\s*(?:元|块)(?:/月|每月)?",
        r"(?:≤|<=|不超过|以内|以下)\s*(\d{3,5})",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            value = int(match.group(1))
            if 500 <= value <= 50000:
                return value
    for value in re.findall(r"(?<!\d)(\d{4})(?!\d)", text):
        number = int(value)
        if 1000 <= number <= 20000:
            return number
    return None


def _extract_commute(text: str) -> int | None:
    match = re.search(r"(\d{1,3})\s*(?:分钟|分|min)", text)
    if not match:
        return None
    value = int(match.group(1))
    return value if 5 <= value <= 180 else None


def _extract_layout(text: str) -> str | None:
    compact = text.replace(" ", "")
    for pattern, label in LAYOUTS:
        if re.search(pattern, compact):
            return label
    return None


def _extract_district(text: str) -> str | None:
    for key, value in DISTRICTS.items():
        if key in text:
            return value
    return None


def _has_positive(text: str, word: str) -> bool:
    """True when the tag appears without a nearby negation (不要/无/没有)."""
    for match in re.finditer(re.escape(word), text):
        prefix = text[max(0, match.start() - 4) : match.start()]
        if any(item in prefix for item in ("不", "无", "没", "免")):
            continue
        return True
    return False


COMPANY_PATTERNS = (
    re.compile(
        r"(?:公司|上班|工作|单位)(?:位置|地点|地址)?(?:在|位于|是|改为|改成|换到|换成|换去|定在|到)?"
        r"\s*[:：]?\s*([^\s，,。；;、]{2,32})"
    ),
    re.compile(r"(?:通勤|上班)(?:到|去)\s*([^\s，,。；;、]{2,32})"),
)
COMPANY_STOP_WORDS = (
    "预算",
    "通勤",
    "号线",
    "地铁",
    "附近",
    "上班",
    "工作",
    "小区",
    "房子",
)
COMPANY_GENERIC = {
    "公司",
    "单位",
    "工作",
    "上班",
    "地点",
    "位置",
    "地址",
    "公司地址",
    "还是",
    "会展中心",
}


def _extract_company_match(text: str) -> tuple[str, int, int] | None:
    """Return (value, start, end) for an explicit office / commute destination."""
    for pattern in COMPANY_PATTERNS:
        for match in pattern.finditer(text):
            value = match.group(1).strip()
            value = re.sub(r"^(在|到|去|是)", "", value)
            for stop in COMPANY_STOP_WORDS:
                if stop in value:
                    value = value.split(stop, 1)[0]
            value = value.strip("，,。；;、 ")
            if len(value) < 2 or value in COMPANY_GENERIC:
                continue
            return value[:64], match.start(), match.end()
    return None


def _extract_company(text: str) -> str | None:
    match = _extract_company_match(text)
    return match[0] if match else None


def _extract_must(text: str) -> list[str]:
    must = []
    for tag in ("电梯", "近地铁", "精装"):
        if _has_positive(text, tag):
            must.append(tag)
    if _has_positive(text, "南向") or _has_positive(text, "朝南"):
        must.append("南向")
    return must


def parse_conditions(message: str, base: dict | None = None) -> dict:
    base = dict(base or {})
    conditions = {
        "company": base.get("company", "深圳会展中心"),
        "company_explicit": bool(base.get("company_explicit", False)),
        "line": "5号线" if "5号线" in message else base.get("line", "5号线"),
        "budget": base.get("budget"),
        "commute": base.get("commute"),
        "layout": base.get("layout"),
        "district": base.get("district"),
        "must": sorted(set(base.get("must") or [])),
    }
    budget = _extract_budget(message)
    commute = _extract_commute(message)
    layout = _extract_layout(message)
    # A company/office location is not a requested residential district:
    # remove the company phrase before scanning for a district.
    district_text = message
    company_match = _extract_company_match(message)
    if company_match:
        district_text = (
            message[: company_match[1]] + " " + message[company_match[2] :]
        )
    district = _extract_district(district_text)
    if budget is not None:
        conditions["budget"] = budget
    if commute is not None:
        conditions["commute"] = commute
    if layout is not None:
        conditions["layout"] = layout
    if district is not None:
        conditions["district"] = district
    company = company_match[0] if company_match else None
    if company:
        conditions["company"] = company
        conditions["company_explicit"] = True
    elif "会展中心" in message:
        conditions["company"] = "深圳会展中心"
        conditions["company_explicit"] = True
    conditions["must"] = sorted(set(conditions["must"]) | set(_extract_must(message)))
    conditions["isLong"] = (
        conditions["district"] == "龙岗区"
        or bool(conditions.get("budget") and conditions["budget"] <= 3000)
        or bool(conditions.get("commute") and conditions["commute"] >= 60)
    )
    return conditions


def conditions_summary(conditions: dict) -> str:
    parts = []
    if conditions.get("budget"):
        parts.append(f"预算≤{conditions['budget']}")
    if conditions.get("commute"):
        parts.append(f"通勤≤{conditions['commute']}min")
    if conditions.get("layout"):
        parts.append(str(conditions["layout"]))
    if conditions.get("district"):
        parts.append(str(conditions["district"]))
    if conditions.get("must"):
        parts.append("/".join(str(item) for item in conditions["must"]))
    return " · ".join(parts) or "未限定条件"


def _ui_conditions(conditions: dict) -> dict:
    budget = conditions.get("budget")
    commute = conditions.get("commute")
    layout = conditions.get("layout")
    must = conditions.get("must") or []
    return {
        "company": conditions.get("company") or "深圳会展中心",
        "budget": f"{int(budget)} 元/月以内" if budget else "不限",
        "line": conditions.get("line") or "5号线",
        "commute": f"≤ {int(commute)} 分钟" if commute else "不限",
        "layout": layout or "不限",
        "district": conditions.get("district") or "",
        "must": " / ".join(str(item) for item in must) if must else "无硬条件",
        "isLong": bool(conditions.get("isLong")),
    }

async def _query_cards(
    db: AsyncSession,
    conditions: dict,
    *,
    limit: int = 4,
    sort_by_commute: bool = False,
) -> tuple[list[dict], dict]:
    return await agent_tools.search_cards(
        db, conditions, limit=limit, sort_by_commute=sort_by_commute
    )


def _build_plan(
    condition_text: str,
    guard_text: str,
    tool_plan: list[dict],
    final_count: int,
) -> list[dict]:
    steps = [
        {
            "id": "parse",
            "label": "解析需求",
            "desc": condition_text,
            "status": "done",
            "time": "local",
        },
        {
            "id": "guard",
            "label": "输入护栏",
            "desc": guard_text,
            "status": "done",
            "time": "local",
        },
    ]
    for index, item in enumerate(tool_plan):
        steps.append(
            {
                "id": f"tool-{index + 1}",
                "label": item["tool"],
                "desc": item.get("summary") or item.get("reason") or "",
                "status": item.get("status", "done"),
                "time": item.get("time", "local"),
            }
        )
    steps.append(
        {
            "id": "answer",
            "label": "推荐",
            "desc": f"{final_count} 套候选",
            "status": "done",
            "time": "local",
        }
    )
    return steps


def _answer_for(cards: list[dict], conditions: dict) -> str:
    if not cards:
        return (
            f"没有找到同时满足「{conditions_summary(conditions)}」的房源。"
            "建议放宽预算、通勤或户型，或者去掉电梯/精装等硬条件。"
        )
    lines = []
    for card in cards[:3]:
        commute = card.get("commute_min")
        commute_text = f"通勤 {commute} 分钟" if commute is not None else "通勤样本待补"
        lines.append(
            f"{card.get('community_name') or '房源'} · ¥{card.get('rent')} · "
            f"{commute_text} · {card.get('score')} 分"
        )
    return "；".join(lines) + "。"


def _monitor_name(conditions: dict) -> str:
    return f"{conditions.get('line', '5号线')} · {conditions_summary(conditions)}"[:128]


def _session_amap_cap(settings: dict) -> int:
    return max(1, int(settings.get("sessionAmapCap") or 15))


def _merge_llm_conditions(
    rule: dict, intent: dict | None, message: str | None = None
) -> dict:
    if not intent:
        return rule
    merged = dict(rule)
    company_match = _extract_company_match(message) if message is not None else None
    for key in ("budget", "commute", "layout", "district", "company"):
        value = intent.get(key)
        if value is None:
            continue
        if key == "company":
            explicit = bool(company_match) or (
                message is not None and "会展中心" in message
            )
            if message is not None and not (merged.get("company_explicit") or explicit):
                # The LLM sometimes echoes the current destination back as a
                # new company; do not let that silently change the setting.
                continue
            if value != merged.get("company"):
                merged["company_explicit"] = True
        if key == "district" and message is not None:
            # A company address can contain a district name; only accept an
            # LLM district when the user separately stated a residential area.
            stripped = (
                message[: company_match[1]] + " " + message[company_match[2] :]
                if company_match
                else message
            )
            if not merged.get("district") and _extract_district(stripped) is None:
                continue
        merged[key] = value
    if intent.get("must"):
        merged["must"] = sorted(set(merged.get("must") or []) | set(intent["must"]))
    merged["isLong"] = (
        merged.get("district") == "龙岗区"
        or bool(merged.get("budget") and merged.get("budget") <= 3000)
        or bool(merged.get("commute") and merged.get("commute") >= 60)
    )
    return merged


def _session_title(message: str) -> str:
    return " ".join(message.split())[:24] or "找房会话"


async def _use_current_destination(db: AsyncSession, conditions: dict) -> None:
    """Show the persisted destination when the user did not name a company."""
    if conditions.get("company_explicit"):
        return
    current = await get_commute_destination(db)
    address = str((current or {}).get("address") or "").strip()
    if address:
        conditions["company"] = address


async def _sync_commute_destination(db: AsyncSession, conditions: dict) -> dict | None:
    """Persist an explicit office change and refresh commute-based scores."""
    if not conditions.get("company_explicit"):
        return None
    company = str(conditions.get("company") or "").strip()
    if not company:
        return None
    current = await get_commute_destination(db)
    if current and str(current.get("address") or "") == company:
        return None
    try:
        value = await set_commute_destination(db, company, city="深圳")
    except Exception as exc:
        log.warning("commute_destination_update_failed", company=company, error=str(exc)[:200])
        return None
    # Re-score the current top candidates synchronously so the next search
    # does not show reasons computed against the previous destination, then
    # let the worker refresh the full task in the background.
    task = await db.get(Task, 1)
    if task is not None:
        try:
            from app.services.enrich_service import rescore_listings

            ids = (
                await db.execute(
                    select(Listing.id)
                    .where(Listing.status == ListingStatus.active)
                    .order_by(Listing.score.desc().nullslast(), Listing.id.desc())
                    .limit(300)
                )
            ).scalars().all()
            await rescore_listings(db, task, [int(item) for item in ids])
            admin_settings = await get_admin_settings(db)
            batch = max(1, int(admin_settings.get("batchCap") or 10))
            db.add(
                Job(
                    task_id=task.id,
                    type="sampling",
                    payload={
                        "count": batch,
                        "buckets": list(COMMUTE_BUCKETS),
                        "modes": ["公交/地铁"],
                    },
                    status=JobStatus.queued,
                )
            )
            db.add(
                Job(
                    task_id=task.id,
                    type="analysis",
                    payload={"listing_ids": []},
                    status=JobStatus.queued,
                )
            )
            await db.commit()
        except Exception as exc:
            await db.rollback()
            log.warning("commute_rescore_failed", error=str(exc)[:200])
    return value


async def _save_session(
    db: AsyncSession,
    session: AgentSession,
    *,
    stage: str,
    conditions: dict,
    candidates: str,
    plan: list[dict],
    tools: list[list[str]],
    result: str,
    latency_ms: int,
    llm: dict | None = None,
    guardrail_log: list[dict] | None = None,
    status: str = "done",
) -> None:
    session.status = status
    session.stage = stage
    session.conditions = conditions
    session.candidates = candidates
    session.tools_count = len(tools)
    session.amap_count = 0
    session.latency_ms = latency_ms
    session.plan = plan
    session.tools_list = tools
    session.guardrails = guardrail_log or []
    session.result = result
    if llm:
        if llm.get("model"):
            session.model = str(llm["model"])[:128]
        session.prompt_tokens = int(session.prompt_tokens or 0) + int(
            llm.get("prompt_tokens") or 0
        )
        session.completion_tokens = int(session.completion_tokens or 0) + int(
            llm.get("completion_tokens") or 0
        )
        session.cost = float(session.cost or 0) + float(llm.get("cost") or 0)
        session.llm_fallback = bool(llm.get("fallback", True))
    session.updated_at = datetime.now(UTC)
    await db.commit()


def _jsonable(value):
    """Make tool results safe for JSONB (datetimes, decimals, model objects)."""
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (datetime,)):
        return value.isoformat()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    try:
        from decimal import Decimal

        if isinstance(value, Decimal):
            return float(value)
    except ImportError:  # pragma: no cover
        pass
    return str(value)


def _compact_result(result: dict) -> str:
    try:
        text = json.dumps(result, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return "{}"
    return text[:3000]


async def _execute_tools(
    db: AsyncSession,
    session: AgentSession,
    steps: list[dict],
    conditions: dict,
    *,
    user_id: int,
) -> tuple[list[dict], dict, dict, list[list[str]], list[dict], list[dict]]:
    """Execute the validated tool plan and persist one trace row per call."""
    cards: list[dict] = []
    counts = {"total": 0, "filtered": 0, "final": 0}
    results: list[dict] = []
    trace: list[list[str]] = []
    tool_plan: list[dict] = []
    current = dict(conditions)
    trimmed = steps[: guardrails.MAX_TOOL_STEPS]
    for index, step in enumerate(trimmed):
        tool = str(step.get("tool") or "")
        args = dict(step.get("args") or {})
        started = time.monotonic()
        resolved: dict = {}
        status = "ok"
        summary = ""
        result: dict = {}
        error_text: str | None = None
        try:
            result, summary, resolved = await asyncio.wait_for(
                agent_tools.execute(
                    db,
                    tool,
                    args,
                    base_conditions=current,
                    cards=cards,
                    user_id=user_id,
                ),
                timeout=8.0,
            )
        except Exception as exc:
            status = "error"
            error_text = f"{type(exc).__name__}: {exc}"[:300]
            summary = f"{tool} 失败：{type(exc).__name__}"
            result = {"error": error_text}
        latency = int((time.monotonic() - started) * 1000)
        db.add(
            AgentToolCall(
                session_id=session.id,
                step=index + 1,
                tool=tool[:32],
                args=resolved or args,
                status=status,
                latency_ms=latency,
                result_summary=summary[:255],
                result=_jsonable(
                    result if isinstance(result, dict) else {"value": result}
                ),
                error=error_text,
            )
        )
        trace.append(
            [
                tool,
                json.dumps(resolved or args, ensure_ascii=False, default=str)[:300],
                f"{latency}ms",
                summary[:120],
            ]
        )
        tool_plan.append(
            {
                "tool": tool,
                "reason": step.get("reason") or "",
                "status": status,
                "summary": summary[:160],
                "time": f"{latency}ms",
            }
        )
        if status == "ok":
            results.append(
                {
                    "tool": tool,
                    "summary": summary,
                    "data": _compact_result(result),
                }
            )
            if tool == "search_listings":
                cards = list(result.get("cards") or [])
                counts = dict(result.get("counts") or counts)
                current = dict(result.get("conditions") or current)
    await db.commit()
    return cards, counts, current, trace, results, tool_plan


async def stream(
    db: AsyncSession, session_id: str | None, message: str, *, user_id: int
) -> AsyncIterator[dict]:
    started = time.monotonic()
    session: AgentSession | None = None
    guard_log: list[dict] = []
    try:
        inspection = guardrails.inspect_message(message)
        guard_record = {
            "stage": "input",
            "flags": inspection["flags"],
            "pii_hits": inspection["pii_hits"],
            "injections": inspection["injections"],
            "summary": guardrails.summarize(inspection),
        }
        guard_log.append(guard_record)
        masked = inspection["masked"]
        allow_llm = bool(inspection["allow_llm"])
        budget_record: dict = {}
        budget_blocked = ""
        if allow_llm:
            try:
                budget_record = await guardrails.check_llm_budget(db)
            except guardrails.BudgetExceeded as exc:
                allow_llm = False
                budget_blocked = str(exc)
                budget_record = {"blocked": budget_blocked}
        if budget_record:
            guard_log.append({"stage": "budget", **budget_record})

        if session_id:
            session = await db.get(AgentSession, session_id)
        new_session = session is None

        parse_meta = llm_service.merge_meta()
        plan_meta = llm_service.merge_meta()
        answer_meta = llm_service.merge_meta()
        conditions: dict = {}

        if new_session:
            rule = parse_conditions(masked)
            intent = None
            if allow_llm:
                intent, parse_meta = await llm_service.parse_intent(db, masked, {})
            conditions = _merge_llm_conditions(rule, intent, masked)
            session = AgentSession(
                id=f"S-{uuid.uuid4().hex[:8].upper()}",
                user_id=user_id,
                title=_session_title(message),
                prompt=message,
                conditions={},
                status="running",
            )
            db.add(session)
            await db.commit()
            await db.refresh(session)
        else:
            conditions = dict(session.conditions or {})

        yield {"type": "session", "sessionId": session.id, "title": session.title}

        base = dict(session.conditions or {})
        preview = parse_conditions(message, base)
        await _use_current_destination(db, preview)
        preview_update = await _sync_commute_destination(db, preview)
        if preview_update:
            base = preview
            yield {
                "type": "toast",
                "message": (
                    f"公司位置已更新为 {preview_update['address']}，"
                    "正在按新目的地重采通勤"
                ),
            }
        lower = message.lower()
        quick_text: str | None = None
        quick_saved = False
        if not new_session and "对比" in message:
            quick_text = "已经切到对比视图。差异主要在通勤、租金和面积；如果两个人住，优先看两居。"
            yield {"type": "tab", "tab": "compare"}
        elif not new_session and ("图片" in message or "ai" in lower):
            detail_text = (
                "封面级图片管线已接入后台：下载封面、dHash 去重、价格异常与中介话术信号，"
                "两条以上信号才标记可疑。视觉标签已接 OpenCode Go，"
                "但默认关闭；聊天中不主动触发下载。"
            )
            yield {"type": "ai", "text": detail_text}
            quick_text = "封面分析在管理端「图片 / AI」页；本次推荐仍基于价格、通勤和标签。"
        elif not new_session and ("保存" in message or "监控" in message):
            name = _monitor_name(base)
            save_args = {"name": name, "conditions": base}
            resolved: dict = {}
            started_save = time.monotonic()
            try:
                result, summary, resolved = await agent_tools.execute(
                    db,
                    "save_monitor",
                    save_args,
                    base_conditions=base,
                    cards=[],
                    user_id=user_id,
                )
                status = "ok"
            except Exception as exc:
                result = {"error": str(exc)[:200]}
                summary = "保存监控失败"
                status = "error"
                resolved = save_args
            latency = int((time.monotonic() - started_save) * 1000)
            db.add(
                AgentToolCall(
                    session_id=session.id,
                    step=1,
                    tool="save_monitor",
                    args=resolved,
                    status=status,
                    latency_ms=latency,
                    result_summary=summary[:255],
                    result=result,
                    error=None if status == "ok" else result.get("error"),
                )
            )
            await db.commit()
            yield {"type": "toast", "message": f"已保存监控：{name}"}
            quick_text = "已保存为监控条件。新匹配/降价推送在后续接入。"
            plan = _build_plan(
                conditions_summary(base),
                guard_record["summary"],
                [
                    {
                        "tool": "save_monitor",
                        "reason": "用户明确要求保存",
                        "status": status,
                        "summary": summary,
                        "time": f"{latency}ms",
                    }
                ],
                0,
            )
            quick_saved = True
            await _save_session(
                db,
                session,
                stage="监控已保存",
                conditions=base,
                candidates=session.candidates or "",
                plan=plan,
                tools=[["save_monitor", name, f"{latency}ms", summary]],
                result=quick_text,
                latency_ms=int((time.monotonic() - started) * 1000),
                guardrail_log=guard_log,
                status="done",
            )

        if quick_text is not None and not new_session:
            if not quick_saved:
                await _save_session(
                    db,
                    session,
                    stage="对比视图" if "对比" in message else "图片说明",
                    conditions=base,
                    candidates=session.candidates or "",
                    plan=_build_plan(
                        conditions_summary(base),
                        guard_record["summary"],
                        [],
                        0,
                    ),
                    tools=[],
                    result=quick_text,
                    latency_ms=int((time.monotonic() - started) * 1000),
                    guardrail_log=guard_log,
                    status="done",
                )
            yield {"type": "message", "text": quick_text}
            yield {"type": "done"}
            return

        await _use_current_destination(db, conditions)
        destination_update = await _sync_commute_destination(db, conditions)
        if destination_update:
            yield {
                "type": "toast",
                "message": (
                    f"公司位置已更新为 {destination_update['address']}，"
                    "正在按新目的地重采通勤"
                ),
            }
        if new_session:
            steps = None
            if allow_llm and settings.agent_native_tools:
                steps, plan_meta = await llm_service.plan_tools_native(
                    db, masked, conditions
                )
            if allow_llm and not steps:
                json_steps, json_meta = await llm_service.plan_tools(
                    db, masked, conditions
                )
                steps = json_steps
                plan_meta = llm_service.merge_meta(plan_meta, json_meta)
            if not steps:
                steps = agent_tools.rule_plan(masked, conditions)
            cards, counts, conditions, trace, tool_results, tool_plan = (
                await _execute_tools(db, session, steps, conditions, user_id=user_id)
            )
        else:
            rule = parse_conditions(masked, base)
            intent = None
            if allow_llm:
                intent, parse_meta = await llm_service.parse_intent(db, masked, base)
            conditions = _merge_llm_conditions(rule, intent, masked)
            steps = None
            if allow_llm and settings.agent_native_tools:
                steps, plan_meta = await llm_service.plan_tools_native(
                    db, masked, conditions
                )
            if allow_llm and not steps:
                json_steps, json_meta = await llm_service.plan_tools(
                    db, masked, conditions
                )
                steps = json_steps
                plan_meta = llm_service.merge_meta(plan_meta, json_meta)
            if not steps:
                steps = agent_tools.rule_plan(masked, conditions)
            cards, counts, conditions, trace, tool_results, tool_plan = (
                await _execute_tools(db, session, steps, conditions, user_id=user_id)
            )

        if not counts.get("total"):
            cards, counts = await _query_cards(db, conditions)
        plan = _build_plan(
            conditions_summary(conditions),
            guard_record["summary"],
            tool_plan,
            int(counts.get("final") or 0),
        )
        yield {"type": "conditions", "conditions": _ui_conditions(conditions)}
        yield {"type": "plan", "steps": plan}
        yield {
            "type": "budget",
            "amap": 0,
            "cap": _session_amap_cap(await get_admin_settings(db)),
            "ai": {
                "used": budget_record.get("used"),
                "limit": budget_record.get("limit"),
                "blocked": bool(budget_blocked),
            },
        }
        yield {
            "type": "cards",
            "cards": cards,
            "longgang": bool(conditions.get("isLong")),
        }
        llm_answer = None
        if allow_llm:
            llm_answer, answer_meta = await llm_service.answer(
                db, cards, conditions, tool_results=tool_results
            )
        llm_meta = llm_service.merge_meta(parse_meta, plan_meta, answer_meta)
        answer = llm_answer or _answer_for(cards, conditions)
        if inspection["injections"]:
            answer = "检测到疑似指令覆盖/提示词探测，本次只按本地规则处理。" + answer
        if budget_blocked:
            answer = f"{budget_blocked}；本次改用规则版。" + answer
        yield {"type": "message", "text": answer}
        latency = int((time.monotonic() - started) * 1000)
        tools = trace + list(llm_meta.get("calls") or [])
        status = "blocked" if budget_blocked else "done"
        if budget_blocked:
            stage = "预算拦截"
        elif new_session:
            stage = "已推荐" if cards else "无匹配"
        else:
            stage = "已重排" if "通勤" in message or "近" in message else "已更新"
        await _save_session(
            db,
            session,
            stage=stage,
            conditions=conditions,
            candidates=(
                f"{counts['total']} → {counts['filtered']} → {counts['final']}"
            ),
            plan=plan,
            tools=tools,
            result=answer,
            latency_ms=latency,
            llm=llm_meta,
            guardrail_log=guard_log,
            status=status,
        )
        yield {"type": "done"}
    except Exception as exc:
        if session is not None:
            session.status = "failed"
            session.stage = "失败"
            session.result = f"{type(exc).__name__}: {exc}"[:500]
            session.updated_at = datetime.now(UTC)
            await db.commit()
        yield {"type": "error", "message": f"{type(exc).__name__}: {exc}"[:200]}
        yield {"type": "done"}


async def list_chat_sessions(
    db: AsyncSession, user_id: int, limit: int = 30
) -> list[dict]:
    rows = (
        (
            await db.execute(
                select(AgentSession)
                .where(AgentSession.user_id == user_id)
                .order_by(AgentSession.updated_at.desc())
                .limit(max(1, min(limit, 100)))
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": item.id,
            "title": item.title,
            "prompt": item.prompt,
            "updatedAt": item.updated_at,
        }
        for item in rows
    ]


async def list_monitors(db: AsyncSession, user_id: int, limit: int = 50) -> list[dict]:
    rows = (
        (
            await db.execute(
                select(AgentMonitor)
                .where(AgentMonitor.user_id == user_id)
                .order_by(AgentMonitor.created_at.desc())
                .limit(max(1, min(limit, 100)))
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": item.id,
            "name": item.name,
            "conditions": item.conditions or {},
            "createdAt": item.created_at,
            "newMatches": item.new_matches,
        }
        for item in rows
    ]


async def create_monitor(
    db: AsyncSession, name: str, conditions: dict, *, user_id: int
) -> dict:
    monitor = AgentMonitor(
        id=f"M-{uuid.uuid4().hex[:6].upper()}",
        user_id=user_id,
        name=name[:128],
        conditions=conditions,
    )
    db.add(monitor)
    await db.commit()
    await db.refresh(monitor)
    return {
        "id": monitor.id,
        "name": monitor.name,
        "conditions": monitor.conditions or {},
        "createdAt": monitor.created_at,
        "newMatches": monitor.new_matches,
    }


async def delete_monitor(
    db: AsyncSession, monitor_id: str, *, user_id: int, is_admin: bool = False
) -> bool:
    monitor = await db.get(AgentMonitor, monitor_id)
    if monitor is None:
        return False
    if not is_admin and monitor.user_id != user_id:
        return False
    await db.delete(monitor)
    await db.commit()
    return True


async def list_admin_sessions(db: AsyncSession, limit: int = 50) -> list[dict]:
    rows = (
        (
            await db.execute(
                select(AgentSession)
                .order_by(AgentSession.updated_at.desc())
                .limit(max(1, min(limit, 100)))
            )
        )
        .scalars()
        .all()
    )
    session_ids = [item.id for item in rows]
    calls: list[AgentToolCall] = []
    if session_ids:
        calls = list(
            (
                await db.execute(
                    select(AgentToolCall)
                    .where(AgentToolCall.session_id.in_(session_ids))
                    .order_by(AgentToolCall.session_id, AgentToolCall.step)
                )
            )
            .scalars()
            .all()
        )
    grouped: dict[str, list[AgentToolCall]] = {}
    for call in calls:
        grouped.setdefault(call.session_id, []).append(call)
    result = []
    for item in rows:
        plan = [
            [
                step.get("label", ""),
                step.get("desc", ""),
                step.get("status", "pending"),
                step.get("time", ""),
            ]
            for step in (item.plan or [])
            if isinstance(step, dict)
        ]
        result.append(
            {
                "id": item.id,
                "query": item.prompt,
                "stage": item.stage or "—",
                "cand": item.candidates or "—",
                "tools": item.tools_count,
                "amap": item.amap_count,
                "latency": f"{item.latency_ms / 1000:.1f}s" if item.latency_ms else "—",
                "status": item.status,
                "model": item.model or "规则版",
                "promptTokens": item.prompt_tokens,
                "completionTokens": item.completion_tokens,
                "cost": float(item.cost or 0),
                "fallback": item.llm_fallback,
                "plan": plan,
                "toolsList": item.tools_list or [],
                "guardrails": item.guardrails or [],
                "toolCalls": [
                    {
                        "step": call.step,
                        "tool": call.tool,
                        "args": call.args or {},
                        "status": call.status,
                        "latency": f"{call.latency_ms}ms" if call.latency_ms else "—",
                        "summary": call.result_summary,
                        "error": call.error,
                    }
                    for call in grouped.get(item.id, [])
                ],
                "result": item.result or "",
            }
        )
    return result


async def annotate_session(db: AsyncSession, session_id: str, label: str) -> bool:
    session = await db.get(AgentSession, session_id)
    if session is None:
        return False
    session.label = label[:32]
    await db.commit()
    return True
