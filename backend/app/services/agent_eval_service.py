"""Deterministic agent evaluation (P1/W4).

The golden set covers intent parsing, tool selection, argument schema and
grounded answers, plus guardrail probes.  It deliberately runs the rule
planner, not the external model, so it is free, repeatable and can be used as
a regression gate before enabling live LLM planning for users.
"""

import json
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import (
    AgentEvalRun,
    AgentSession,
    AgentToolCall,
    ProviderCall,
    ProviderUsage,
)
from app.services import agent_tools, guardrails
from app.services.agent_service import _answer_for, parse_conditions
from app.services.settings_service import get_admin_settings

DATASET_PATH = Path(__file__).resolve().parents[1] / "data" / "agent_eval.json"
INTENT_KEYS = ("budget", "commute", "layout", "district", "must", "company")


def load_dataset() -> dict:
    return json.loads(DATASET_PATH.read_text(encoding="utf-8"))


def _compare_intent(actual: dict, expected: dict) -> tuple[bool, dict]:
    details: dict[str, dict] = {}
    ok = True
    for key in INTENT_KEYS:
        if key not in expected:
            continue
        want = expected[key]
        got = actual.get(key)
        if key == "must":
            got = sorted(got or [])
            want = sorted(want or [])
        elif key == "company" and got is None:
            got = "深圳会展中心"
        match = got == want
        ok = ok and match
        details[key] = {"expected": want, "actual": got, "ok": match}
    return ok, details


def _validate_steps(steps: list[dict]) -> tuple[bool, str | None]:
    try:
        for step in steps:
            probe = dict(step.get("args") or {})
            if probe.get("listing_id") in {"$top", "$top3", "$top_ids"}:
                probe["listing_id"] = 1
            if probe.get("listing_ids") in {"$top3", "$top_ids"}:
                probe["listing_ids"] = [1, 2]
            agent_tools.validate_call(str(step["tool"]), probe)
    except agent_tools.ToolArgumentError as exc:
        return False, str(exc)[:200]
    return True, None


def _search_args(steps: list[dict]) -> dict:
    for step in steps:
        if step.get("tool") == "search_listings":
            return dict(step.get("args") or {})
    return {}


def _grounded_answer() -> tuple[bool, str]:
    cards = [
        {
            "community_name": "测一花园",
            "rent": 4000,
            "score": 80,
            "commute_min": 30,
        },
        {
            "community_name": "测二新村",
            "rent": 4500,
            "score": 72,
            "commute_min": 42,
        },
    ]
    answer = _answer_for(cards, {"budget": 4500, "commute": 45})
    ok = all(text in answer for text in ("测一花园", "¥4000", "80 分", "测二新村"))
    return ok, answer[:200]


def run_case(case: dict) -> dict:
    message = str(case.get("message") or "")
    expect = dict(case.get("expect") or {})
    result = {
        "id": case.get("id"),
        "kind": case.get("kind", "query"),
        "message": message,
        "passed": False,
        "details": {},
    }
    if case.get("kind") == "guardrail":
        probe = guardrails.inspect_message(message)
        blocked_ok = (not probe["allow_llm"]) == bool(expect.get("blocked"))
        pii_ok = (probe["pii_hits"] > 0) == bool(expect.get("pii"))
        result["details"] = {
            "blocked": {"expected": expect.get("blocked"), "actual": not probe["allow_llm"]},
            "pii": {"expected": expect.get("pii"), "actual": probe["pii_hits"] > 0},
            "injections": probe["injections"],
        }
        result["passed"] = blocked_ok and pii_ok
        return result

    parsed = parse_conditions(message)
    intent_ok, intent_details = _compare_intent(parsed, dict(expect.get("intent") or {}))
    steps = agent_tools.rule_plan(message, parsed)
    tools = [step["tool"] for step in steps]
    tools_ok = tools == list(expect.get("tools") or [])
    schema_ok, schema_error = _validate_steps(steps)
    args = _search_args(steps)
    args_ok = True
    for key, want in (expect.get("intent") or {}).items():
        if key not in {"budget", "commute", "layout", "district", "must"}:
            continue
        got = args.get(key)
        if key == "must":
            got = sorted(got or [])
            want = sorted(want or [])
        if got != want:
            args_ok = False
            break
    grounding_ok, grounding_text = _grounded_answer()
    result["details"] = {
        "intent": intent_details,
        "tools": {"expected": expect.get("tools"), "actual": tools, "ok": tools_ok},
        "args_ok": args_ok,
        "schema": {"ok": schema_ok, "error": schema_error},
        "grounding": {"ok": grounding_ok, "answer": grounding_text},
    }
    result["passed"] = bool(intent_ok and tools_ok and schema_ok and args_ok and grounding_ok)
    result["_metrics"] = {
        "intent": intent_ok,
        "tools": tools_ok,
        "args": args_ok,
        "schema": schema_ok,
        "grounding": grounding_ok,
    }
    return result


def evaluate() -> dict:
    dataset = load_dataset()
    started = time.monotonic()
    results = []
    for case in dataset.get("cases") or []:
        try:
            results.append(run_case(case))
        except Exception as exc:  # one broken case must not hide the rest
            results.append(
                {
                    "id": case.get("id"),
                    "kind": case.get("kind", "query"),
                    "message": case.get("message"),
                    "passed": False,
                    "details": {"error": f"{type(exc).__name__}: {exc}"},
                }
            )
    query = [item for item in results if item["kind"] == "query"]
    guards = [item for item in results if item["kind"] == "guardrail"]

    def rate(items: list[dict], key: str) -> float | None:
        values = [bool(item.get("_metrics", {}).get(key)) for item in items]
        if not values:
            return None
        return round(sum(values) / len(values), 3)

    field_total = 0
    field_ok = 0
    for item in query:
        for detail in (item["details"].get("intent") or {}).values():
            field_total += 1
            field_ok += 1 if detail.get("ok") else 0
    metrics = {
        "intent_case_accuracy": round(
            sum(1 for item in query if item.get("_metrics", {}).get("intent"))
            / max(1, len(query)),
            3,
        ),
        "intent_field_accuracy": round(field_ok / max(1, field_total), 3),
        "tool_accuracy": rate(query, "tools"),
        "arg_accuracy": rate(query, "args"),
        "schema_valid_rate": rate(query, "schema"),
        "grounding_rate": rate(query, "grounding"),
        "guardrail_accuracy": round(
            sum(1 for item in guards if item["passed"]) / max(1, len(guards)), 3
        ),
        "overall_pass_rate": round(
            sum(1 for item in results if item["passed"]) / max(1, len(results)), 3
        ),
        "query_cases": len(query),
        "guardrail_cases": len(guards),
    }
    public_results = []
    for item in results:
        data = {key: value for key, value in item.items() if not key.startswith("_")}
        public_results.append(data)
    return {
        "version": dataset.get("version", "unknown"),
        "mode": "rules",
        "total": len(results),
        "passed": sum(1 for item in results if item["passed"]),
        "metrics": metrics,
        "cases": public_results,
        "duration_ms": int((time.monotonic() - started) * 1000),
    }


async def run_and_store(db: AsyncSession, *, mode: str = "rules") -> dict:
    if mode != "rules":
        raise ValueError("当前只支持 rules 基线评测（不调用外部模型）")
    result = evaluate()
    record = AgentEvalRun(
        dataset_version=result["version"],
        mode=result["mode"],
        total=result["total"],
        passed=result["passed"],
        metrics=result["metrics"],
        cases=result["cases"],
        duration_ms=result["duration_ms"],
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return {
        "id": record.id,
        "version": record.dataset_version,
        "mode": record.mode,
        "total": record.total,
        "passed": record.passed,
        "metrics": record.metrics or {},
        "cases": record.cases or [],
        "duration_ms": record.duration_ms,
        "created_at": record.created_at,
    }


async def latest(db: AsyncSession) -> dict:
    record = (
        await db.execute(select(AgentEvalRun).order_by(AgentEvalRun.id.desc()).limit(1))
    ).scalar_one_or_none()
    history = (
        (
            await db.execute(
                select(AgentEvalRun).order_by(AgentEvalRun.id.desc()).limit(10)
            )
        )
        .scalars()
        .all()
    )
    dataset = load_dataset()
    return {
        "dataset_version": dataset.get("version"),
        "dataset_cases": len(dataset.get("cases") or []),
        "latest": (
            {
                "id": record.id,
                "version": record.dataset_version,
                "mode": record.mode,
                "total": record.total,
                "passed": record.passed,
                "metrics": record.metrics or {},
                "cases": record.cases or [],
                "duration_ms": record.duration_ms,
                "created_at": record.created_at,
            }
            if record
            else None
        ),
        "history": [
            {
                "id": item.id,
                "version": item.dataset_version,
                "mode": item.mode,
                "passed": item.passed,
                "total": item.total,
                "metrics": item.metrics or {},
                "created_at": item.created_at,
            }
            for item in history
        ],
    }


async def cost_summary(db: AsyncSession, days: int = 7) -> dict:
    days = max(1, min(int(days), 90))
    since = datetime.now(UTC) - timedelta(days=days)
    sessions = (
        (
            await db.execute(
                select(AgentSession)
                .where(AgentSession.created_at >= since)
                .order_by(AgentSession.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    statuses: dict[str, int] = {}
    fallbacks = 0
    injection_blocks = 0
    pii_masked = 0
    for session in sessions:
        statuses[session.status] = statuses.get(session.status, 0) + 1
        if session.llm_fallback:
            fallbacks += 1
        for item in session.guardrails or []:
            if not isinstance(item, dict):
                continue
            flags = item.get("flags") or []
            if "prompt_injection_blocked" in flags:
                injection_blocks += 1
            if "pii_masked" in flags:
                pii_masked += 1
    session_ids = [item.id for item in sessions]
    tool_stats = {"calls": 0, "errors": 0, "avg_latency_ms": 0, "success_rate": None}
    if session_ids:
        rows = (
            await db.execute(
                select(AgentToolCall).where(
                    AgentToolCall.session_id.in_(session_ids)
                )
            )
        ).scalars().all()
        tool_stats["calls"] = len(rows)
        tool_stats["errors"] = sum(1 for item in rows if item.status != "ok")
        if rows:
            tool_stats["avg_latency_ms"] = int(
                sum(item.latency_ms for item in rows) / len(rows)
            )
            tool_stats["success_rate"] = round(
                (len(rows) - tool_stats["errors"]) / len(rows), 3
            )
    period = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d")
    usage = await db.get(ProviderUsage, ("modelscope_deepseek", period))
    calls = (
        await db.execute(
            select(ProviderCall).where(
                ProviderCall.provider == "modelscope_deepseek",
                ProviderCall.created_at >= since,
            )
        )
    ).scalars().all()
    admin = await get_admin_settings(db)
    provider_used = int(usage.used if usage else 0)
    provider_limit = int(admin.get("aiDailyCap") or 0)
    return {
        "days": days,
        "sessions": {
            "total": len(sessions),
            "done": statuses.get("done", 0),
            "blocked": statuses.get("blocked", 0),
            "failed": statuses.get("failed", 0),
            "running": statuses.get("running", 0),
            "fallback": fallbacks,
            "fallback_rate": round(fallbacks / max(1, len(sessions)), 3),
            "prompt_tokens": sum(int(item.prompt_tokens or 0) for item in sessions),
            "completion_tokens": sum(
                int(item.completion_tokens or 0) for item in sessions
            ),
            "cost": round(sum(float(item.cost or 0) for item in sessions), 6),
            "avg_latency_ms": int(
                sum(item.latency_ms for item in sessions) / max(1, len(sessions))
            ),
        },
        "tools": tool_stats,
        "guardrails": {
            "injection_blocks": injection_blocks,
            "pii_masked": pii_masked,
            "quota_blocked": statuses.get("blocked", 0),
        },
        "provider": {
            "code": "modelscope_deepseek",
            "model": settings.modelscope_model,
            "used": provider_used,
            "limit": provider_limit,
            "remaining": max(0, provider_limit - provider_used) if provider_limit else None,
            "calls": len(calls),
            "errors": sum(1 for item in calls if item.status != "ok"),
            "avg_latency_ms": int(
                sum(item.latency_ms or 0 for item in calls) / max(1, len(calls))
            ),
        },
        "daily": _daily_series(sessions),
        "total_sessions": int(
            await db.scalar(select(func.count()).select_from(AgentSession)) or 0
        ),
    }


def _daily_series(sessions: list[AgentSession]) -> list[dict]:
    grouped: dict[str, dict] = {}
    for item in sessions:
        created = item.created_at
        if created is None:
            continue
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        key = created.astimezone(ZoneInfo("Asia/Shanghai")).strftime("%m-%d")
        bucket = grouped.setdefault(
            key, {"date": key, "sessions": 0, "tokens": 0, "blocked": 0}
        )
        bucket["sessions"] += 1
        bucket["tokens"] += int(item.prompt_tokens or 0) + int(
            item.completion_tokens or 0
        )
        if item.status == "blocked":
            bucket["blocked"] += 1
    return [grouped[key] for key in sorted(grouped)][-14:]


async def recent_failures(db: AsyncSession, limit: int = 10) -> list[dict]:
    rows = (
        (
            await db.execute(
                select(AgentEvalRun)
                .order_by(AgentEvalRun.id.desc())
                .limit(max(1, min(limit, 30)))
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": item.id,
            "version": item.dataset_version,
            "passed": item.passed,
            "total": item.total,
            "created_at": item.created_at,
        }
        for item in rows
    ]
