import asyncio

from app.services import llm_service, provider_runtime


def test_plan_tools_native_uses_validated_tool_calls(monkeypatch):
    captured = {}

    async def fake_invoke(db, messages, **kwargs):
        captured.update(kwargs)
        return {
            "model": "deepseek-v4.1-flash",
            "prompt_tokens": 12,
            "completion_tokens": 8,
            "tool_calls": [
                {
                    "id": "call_1",
                    "name": "search_listings",
                    "arguments": {"budget": 4000, "layout": "2室"},
                }
            ],
        }

    monkeypatch.setattr(provider_runtime, "invoke_chat", fake_invoke)
    steps, meta = asyncio.run(llm_service.plan_tools_native(None, "预算4000", {}))
    assert captured["tools"]
    assert captured["tool_choice"] == "auto"
    assert steps == [
        {
            "tool": "search_listings",
            "args": {"budget": 4000, "layout": "2室"},
            "reason": "模型原生工具调用",
        }
    ]
    assert meta["fallback"] is False
    assert meta["model"] == "deepseek-v4.1-flash"


def test_plan_tools_native_falls_back_without_tool_calls(monkeypatch):
    async def fake_invoke(db, messages, **kwargs):
        return {
            "model": "deepseek-v4.1-flash",
            "prompt_tokens": 1,
            "completion_tokens": 1,
            "tool_calls": [],
        }

    monkeypatch.setattr(provider_runtime, "invoke_chat", fake_invoke)
    steps, meta = asyncio.run(llm_service.plan_tools_native(None, "预算4000", {}))
    assert steps is None
    assert meta["fallback"] is True
    assert "未选择工具" in meta["error"]


def test_plan_tools_native_rejects_invalid_first_step(monkeypatch):
    async def fake_invoke(db, messages, **kwargs):
        return {
            "model": "m",
            "prompt_tokens": 1,
            "completion_tokens": 1,
            "tool_calls": [
                {"id": "1", "name": "get_listing", "arguments": {"listing_id": 1}}
            ],
        }

    monkeypatch.setattr(provider_runtime, "invoke_chat", fake_invoke)
    steps, meta = asyncio.run(llm_service.plan_tools_native(None, "详情", {}))
    assert steps is None
    assert meta["fallback"] is True
