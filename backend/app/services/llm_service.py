import json
import re
import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services import provider_runtime

DISTRICTS = {
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
}
LAYOUTS = {"1室", "2室", "3室"}
MUSTS = {"电梯", "近地铁", "精装", "南向"}


def _empty_meta(error: str | None = None) -> dict:
    return {
        "model": "",
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "cost": 0.0,
        "fallback": True,
        "error": error,
        "calls": [],
    }


def _extract_json(text: str) -> dict | None:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        value = json.loads(cleaned)
        return value if isinstance(value, dict) else None
    except ValueError:
        match = re.search(r"\{.*\}", cleaned, re.S)
        if not match:
            return None
        try:
            value = json.loads(match.group(0))
            return value if isinstance(value, dict) else None
        except ValueError:
            return None


def _validate_intent(data: dict) -> dict:
    result: dict[str, Any] = {}
    budget = data.get("budget")
    if isinstance(budget, (int, float)) and 500 <= int(budget) <= 50000:
        result["budget"] = int(budget)
    commute = data.get("commute")
    if isinstance(commute, (int, float)) and 5 <= int(commute) <= 180:
        result["commute"] = int(commute)
    layout = data.get("layout")
    if layout in LAYOUTS:
        result["layout"] = layout
    district = data.get("district")
    if district in DISTRICTS:
        result["district"] = district
    must = data.get("must")
    if isinstance(must, list):
        result["must"] = sorted({str(item) for item in must if str(item) in MUSTS})
    company = data.get("company")
    if isinstance(company, str) and company.strip():
        result["company"] = company.strip()[:64]
    return result


async def parse_intent(
    db: AsyncSession, message: str, base: dict
) -> tuple[dict | None, dict]:
    system = (
        "你是 RentRadar 的租房条件解析器。只输出 JSON，不要 markdown。"
        "字段：budget(整数或null)、commute(整数分钟或null)、"
        'layout("1室"/"2室"/"3室"或null)、'
        'district("福田区"/"罗湖区"/"南山区"/"宝安区"/"龙华区"/"龙岗区"/'
        '"盐田区"/"光明区"/"坪山区"/"大鹏新区"或null)、'
        'must(数组，元素只能是"电梯","近地铁","精装","南向")、'
        'company("深圳会展中心"或null)。'
        "只提取用户明确说出的条件；已有条件作为默认值，新消息可以覆盖。"
    )
    user = f"已有条件：{json.dumps(base, ensure_ascii=False)}\n新消息：{message}"
    started = time.monotonic()
    try:
        result = await provider_runtime.invoke_chat(
            db,
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=1200,
            temperature=0.1,
        )
    except Exception as exc:
        return None, _empty_meta(f"{type(exc).__name__}: {exc}"[:200])
    latency = int((time.monotonic() - started) * 1000)
    data = _extract_json(result["content"])
    meta = {
        "model": result["model"],
        "prompt_tokens": result["prompt_tokens"],
        "completion_tokens": result["completion_tokens"],
        "cost": 0.0,
        "fallback": False,
        "error": None,
        "calls": [
            [
                "llm_parse",
                result["model"],
                f"{latency}ms",
                f"{result['prompt_tokens']}+{result['completion_tokens']} tok",
            ]
        ],
    }
    if data is None:
        meta["fallback"] = True
        meta["error"] = "LLM 返回无法解析的 JSON"
        return None, meta
    intent = _validate_intent(data)
    if not intent:
        meta["fallback"] = True
        meta["error"] = "LLM 未返回有效条件"
        return None, meta
    return intent, meta


async def answer(
    db: AsyncSession, cards: list[dict], conditions: dict
) -> tuple[str | None, dict]:
    compact = [
        {
            "community": card.get("community_name"),
            "district": card.get("district"),
            "layout": card.get("layout"),
            "rent": card.get("rent"),
            "commute_min": card.get("commute_min"),
            "score": card.get("score"),
            "tags": card.get("tags"),
            "price_reason": (card.get("score_reasons") or {}).get("price"),
        }
        for card in cards
    ]
    system = (
        "你是 RentRadar 的租房顾问。基于提供的本地库存卡片写 2–4 句中文推荐，"
        "不得编造卡片外的事实；必须说明本次只查本地库存，详情图/AI 尚未接入。"
        "如果卡片为空，直接建议用户放宽预算/通勤/户型。"
    )
    user = json.dumps(
        {"conditions": conditions, "cards": compact}, ensure_ascii=False
    )
    started = time.monotonic()
    try:
        result = await provider_runtime.invoke_chat(
            db,
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=900,
            temperature=0.3,
        )
    except Exception as exc:
        return None, _empty_meta(f"{type(exc).__name__}: {exc}"[:200])
    latency = int((time.monotonic() - started) * 1000)
    text = str(result["content"]).strip()
    meta = {
        "model": result["model"],
        "prompt_tokens": result["prompt_tokens"],
        "completion_tokens": result["completion_tokens"],
        "cost": 0.0,
        "fallback": not bool(text),
        "error": None if text else "LLM 返回空内容",
        "calls": [
            [
                "llm_answer",
                result["model"],
                f"{latency}ms",
                f"{result['prompt_tokens']}+{result['completion_tokens']} tok",
            ]
        ],
    }
    return (text or None), meta


def merge_meta(*metas: dict) -> dict:
    merged = _empty_meta()
    merged["fallback"] = True
    for meta in metas:
        if not meta:
            continue
        if meta.get("model"):
            merged["model"] = meta["model"]
        merged["prompt_tokens"] += int(meta.get("prompt_tokens") or 0)
        merged["completion_tokens"] += int(meta.get("completion_tokens") or 0)
        merged["cost"] += float(meta.get("cost") or 0)
        merged["calls"].extend(meta.get("calls") or [])
        if meta.get("error"):
            merged["error"] = meta["error"]
        if not meta.get("fallback", True):
            merged["fallback"] = False
    return merged
