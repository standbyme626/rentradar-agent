"""Input guardrails for the conversational agent.

The agent is deliberately small: it can only call read-only local tools and the
configured chat provider.  These helpers are the first line of defence before a
user message reaches an external model or the tool planner:

* mask obvious PII (phone / email / ID card) before any LLM call;
* detect prompt-injection / instruction-override attempts and keep the turn on
  the deterministic rule path instead of sending it to the model;
* enforce the daily AI budget and per-turn tool/step limits before spending.
"""

import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.services import provider_runtime
from app.services.settings_service import get_admin_settings

MAX_TOOL_STEPS = 4
MAX_TOOL_CALLS = 6
LLM_CALLS_PER_TURN = 2  # intent parse + answer

_PII_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"), "手机号"),
    (re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)"), "身份证号"),
    (
        re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
        "邮箱",
    ),
)

_INJECTION_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"(?:忽略|无视|忘记|跳过).{0,10}(?:之前|以上|前面|所有|系统).{0,8}"
            r"(?:指令|指示|规则|设定|要求)"
        ),
        "忽略既有指令",
    ),
    (
        re.compile(
            r"(?:ignore|disregard|forget).{0,20}(?:previous|above|all|system).{0,20}"
            r"(?:instructions?|prompts?|rules?)",
            re.IGNORECASE,
        ),
        "instruction override",
    ),
    (
        re.compile(
            r"(?:system|developer|hidden)\s*(?:prompt|message)", re.IGNORECASE
        ),
        "探测系统提示词",
    ),
    (
        re.compile(r"(?:输出|打印|泄露|告诉我|显示).{0,8}(?:提示词|prompt|系统消息)"),
        "索取提示词",
    ),
    (
        re.compile(
            r"(?:你现在是|扮演|进入).{0,10}(?:DAN|开发者模式|越狱模式|无限制模式)",
            re.IGNORECASE,
        ),
        "角色越狱",
    ),
    (
        re.compile(r"(?:jailbreak|越狱模式|开发者模式|绕过(?:安全|限制))", re.IGNORECASE),
        "越狱关键词",
    ),
    (
        re.compile(r"(?:rm\s+-rf|drop\s+table|delete\s+from|truncate\s+table)", re.IGNORECASE),
        "危险指令",
    ),
)


class BudgetExceeded(Exception):
    """Raised before an LLM call when the daily AI budget is exhausted."""


class ToolLimitExceeded(Exception):
    """Raised when a plan exceeds the per-turn tool budget."""


def mask_pii(text: str) -> tuple[str, int]:
    """Replace obvious personal identifiers; returns (masked_text, hits)."""
    masked = text
    hits = 0
    for pattern, label in _PII_PATTERNS:
        masked, count = pattern.subn(f"[{label}]", masked)
        hits += count
    return masked, hits


def detect_injection(text: str) -> list[str]:
    labels: list[str] = []
    for pattern, label in _INJECTION_PATTERNS:
        if pattern.search(text or ""):
            labels.append(label)
    return labels


def inspect_message(text: str) -> dict:
    """Return a serialisable guardrail record for one user message."""
    masked, pii_hits = mask_pii(text)
    injections = detect_injection(text)
    flags: list[str] = []
    if pii_hits:
        flags.append("pii_masked")
    if injections:
        flags.append("prompt_injection_blocked")
    return {
        "masked": masked,
        "changed": masked != text,
        "pii_hits": pii_hits,
        "injections": injections,
        "flags": flags,
        "allow_llm": not injections,
    }


def summarize(record: dict) -> str:
    parts = []
    if record.get("pii_hits"):
        parts.append(f"脱敏 {record['pii_hits']} 处个人信息")
    if record.get("injections"):
        parts.append("拦截注入：" + "、".join(record["injections"]))
    return "；".join(parts) or "输入检查通过"


async def check_llm_budget(
    db: AsyncSession, *, calls: int = LLM_CALLS_PER_TURN
) -> dict:
    """Fail fast when the configured daily AI quota cannot cover this turn."""
    await get_admin_settings(db)
    used, limit = await provider_runtime.quota_snapshot(
        db, "modelscope_deepseek", cap_key="aiDailyCap"
    )
    remaining = None if limit is None else max(0, limit - used)
    if remaining is not None and remaining < calls:
        raise BudgetExceeded(
            f"AI 日额度不足：已用 {used}/{limit}，本轮需要 {calls} 次"
        )
    return {"used": used, "limit": limit, "remaining": remaining, "calls": calls}


def validate_plan_limits(steps: list[dict]) -> None:
    if len(steps) > MAX_TOOL_STEPS:
        raise ToolLimitExceeded(f"工具步骤 {len(steps)} 超过上限 {MAX_TOOL_STEPS}")
    if sum(1 for step in steps if step.get("tool")) > MAX_TOOL_CALLS:
        raise ToolLimitExceeded(f"工具调用超过上限 {MAX_TOOL_CALLS}")
