import asyncio

import httpx
import pytest

from app.core.config import settings
from app.integrations.ai.opencode_go import OpenCodeGoProvider, _session_id
from app.integrations.base import (
    Capability,
    ProviderAuthError,
    ProviderDomain,
    ProviderRateLimitError,
)
from app.integrations.registry import load_default_providers, registry
from app.services.provider_service import _cap_key


def _provider(monkeypatch) -> OpenCodeGoProvider:
    monkeypatch.setattr(settings, "opencode_go_api_key", "test-key")
    monkeypatch.setattr(settings, "opencode_go_base_url", "https://opencode.test/v1")
    monkeypatch.setattr(settings, "opencode_go_model", "deepseek-v4.1-flash")
    return OpenCodeGoProvider()


def _fake_client(monkeypatch, response: httpx.Response, captured: dict):
    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, *, headers, json):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return response

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)


def test_open_code_go_registered_and_priority():
    load_default_providers()
    provider = registry.get("opencode_go_deepseek")
    assert provider is not None
    assert provider.meta.domain == ProviderDomain.ai
    assert Capability.chat in provider.meta.capabilities
    assert provider.meta.priority < registry.get("modelscope_deepseek").meta.priority
    assert getattr(provider, "supports_tools", False) is True


def test_chat_sends_required_opencode_headers_and_parses_tool_calls(monkeypatch):
    provider = _provider(monkeypatch)
    captured: dict = {}
    response = httpx.Response(
        200,
        json={
            "model": "deepseek-v4.1-flash",
            "choices": [
                {
                    "finish_reason": "tool_calls",
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {
                                    "name": "search_listings",
                                    "arguments": '{"budget": 4000}',
                                },
                            }
                        ],
                    },
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        },
    )
    _fake_client(monkeypatch, response, captured)
    result = asyncio.run(
        provider.chat(
            [{"role": "system", "content": "sys"}, {"role": "user", "content": "hi"}],
            max_tokens=64,
            tools=[{"type": "function", "function": {"name": "x", "parameters": {}}}],
        )
    )
    assert captured["url"] == "https://opencode.test/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert "RentRadar/" in captured["headers"]["User-Agent"]
    assert captured["headers"]["x-opencode-session"].startswith("rentradar-")
    assert captured["json"]["tools"][0]["function"]["name"] == "x"
    assert result["tool_calls"] == [
        {
            "id": "call_1",
            "name": "search_listings",
            "arguments": {"budget": 4000},
            "raw_arguments": '{"budget": 4000}',
        }
    ]
    assert result["prompt_tokens"] == 10


def test_chat_maps_auth_and_rate_limit_errors(monkeypatch):
    provider = _provider(monkeypatch)
    captured: dict = {}
    _fake_client(monkeypatch, httpx.Response(403, text="error code: 1010"), captured)
    with pytest.raises(ProviderAuthError):
        asyncio.run(provider.chat([{"role": "user", "content": "hi"}]))
    _fake_client(monkeypatch, httpx.Response(429, text="limited"), captured)
    with pytest.raises(ProviderRateLimitError):
        asyncio.run(provider.chat([{"role": "user", "content": "hi"}]))


def test_tag_image_parses_strict_json_and_sends_data_url(monkeypatch):
    provider = _provider(monkeypatch)
    captured: dict = {}
    response = httpx.Response(
        200,
        json={
            "model": "deepseek-v4.1-flash",
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"scene":"样板间","tags":['
                            '{"tag":"样板间","confidence":0.7},'
                            '{"tag":"采光好","confidence":0.8}],'
                            '"summary":"精修图"}'
                        )
                    }
                }
            ],
            "usage": {"prompt_tokens": 300, "completion_tokens": 40},
        },
    )
    _fake_client(monkeypatch, response, captured)
    data_url = "data:image/jpeg;base64,AAAA"
    result = asyncio.run(provider.tag_image(data_url))
    assert result["scene"] == "样板间"
    assert result["tags"][0] == {"tag": "样板间", "confidence": 0.7}
    message = captured["json"]["messages"][1]
    assert message["content"][1]["image_url"]["url"] == data_url


def test_chat_requires_key(monkeypatch):
    monkeypatch.setattr(settings, "opencode_go_api_key", "")
    provider = OpenCodeGoProvider()
    with pytest.raises(ProviderAuthError):
        asyncio.run(provider.chat([{"role": "user", "content": "hi"}]))


def test_session_id_is_stable_per_conversation():
    first = _session_id([{"role": "user", "content": "预算 4000"}])
    second = _session_id([{"role": "user", "content": "预算 4000"}])
    other = _session_id([{"role": "user", "content": "预算 5000"}])
    assert first == second
    assert first != other


def test_ai_cap_covers_both_model_providers(monkeypatch):
    load_default_providers()
    assert _cap_key(registry.get("opencode_go_deepseek")) == "aiDailyCap"
    assert _cap_key(registry.get("modelscope_deepseek")) == "aiDailyCap"
    assert _cap_key(registry.get("amap")) == "amapMonthlyCap"
