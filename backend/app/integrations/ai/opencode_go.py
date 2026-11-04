import hashlib
import json
import time
from typing import Any

import httpx

from app.core.config import settings
from app.integrations.base import (
    BaseProvider,
    Capability,
    ProviderAuthError,
    ProviderDomain,
    ProviderMeta,
    ProviderRateLimitError,
    ProviderTestResult,
    ProviderUnavailable,
    QuotaPolicy,
)


def _session_id(messages: list[dict[str, Any]]) -> str:
    """Stable per-conversation routing id required by OpenCode Go.

    The gateway asks clients to send one stable ``x-opencode-session`` per
    conversation so it can route and cache prompts.  We derive it from the
    system/user content, which keeps retries of the same request on the same
    session without storing anything extra.
    """
    payload = json.dumps(
        [
            {"role": item.get("role"), "content": item.get("content")}
            for item in messages
            if item.get("role") in {"system", "user"}
        ],
        ensure_ascii=False,
        sort_keys=True,
    ).encode()
    return f"rentradar-{hashlib.sha256(payload).hexdigest()[:40]}"


class OpenCodeGoProvider(BaseProvider):
    """OpenCode Go subscription gateway (OpenAI-compatible chat completions).

    The gateway requires a real client User-Agent and a stable
    ``x-opencode-session`` header; using the generic SDK user agent gets a
    Cloudflare 403 (error 1010).  We send both on every call.
    """

    meta = ProviderMeta(
        code="opencode_go_deepseek",
        name="OpenCode Go · DeepSeek V4.1 Flash",
        domain=ProviderDomain.ai,
        capabilities=frozenset({Capability.chat, Capability.image_tagging}),
        auth="api_key",
        coord_system="无",
        description=(
            "OpenCode Go 订阅网关（OpenAI 兼容 Chat Completions）；默认 "
            "deepseek-v4.1-flash，支持原生 tool_calls；额度由 aiDailyCap 硬约束。"
        ),
        docs_url="https://opencode.ai/v2/docs/console/go/",
        quota=QuotaPolicy(period="day", limit=0),
        priority=5,
    )

    def __init__(self) -> None:
        self.configured = bool(settings.opencode_go_api_key)
        self.supports_tools = True

    @property
    def base_url(self) -> str:
        return settings.opencode_go_base_url.rstrip("/")

    @property
    def model(self) -> str:
        return settings.opencode_go_model

    def _headers(self, messages: list[dict[str, Any]]) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {settings.opencode_go_api_key}",
            "Content-Type": "application/json",
            "User-Agent": (
                f"RentRadar/{settings.version} "
                "(self-hosted; +https://github.com/standbyme626/rentradar-agent)"
            ),
            "x-opencode-session": _session_id(messages),
        }

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        max_tokens: int = 600,
        temperature: float = 0.2,
        model: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict | None = None,
    ) -> dict:
        if not self.configured:
            raise ProviderAuthError("未配置 OPENCODE_GO_API_KEY")
        payload: dict[str, Any] = {
            "model": model or self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice or "auto"
        try:
            async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self._headers(messages),
                    json=payload,
                )
        except httpx.HTTPError as exc:
            raise ProviderUnavailable(
                f"OpenCode Go 请求失败：{type(exc).__name__}"
            ) from exc
        if response.status_code in (401, 403):
            raise ProviderAuthError(
                "OpenCode Go API Key 无效、未订阅，或客户端被网关拒绝"
            )
        if response.status_code == 429:
            raise ProviderRateLimitError("OpenCode Go 限流或订阅额度不足")
        if response.status_code >= 400:
            raise ProviderUnavailable(
                f"OpenCode Go HTTP {response.status_code}: {response.text[:200]}"
            )
        try:
            data = response.json()
        except ValueError as exc:
            raise ProviderUnavailable("OpenCode Go 返回非 JSON") from exc
        choices = data.get("choices") or []
        if not choices:
            raise ProviderUnavailable("OpenCode Go 返回空 choices")
        message = choices[0].get("message") or {}
        usage = data.get("usage") or {}
        tool_calls = []
        for call in message.get("tool_calls") or []:
            function = call.get("function") or {}
            raw_args = function.get("arguments")
            arguments: dict[str, Any] | None
            if isinstance(raw_args, str):
                try:
                    arguments = json.loads(raw_args)
                except ValueError:
                    arguments = None
            elif isinstance(raw_args, dict):
                arguments = raw_args
            else:
                arguments = None
            tool_calls.append(
                {
                    "id": call.get("id") or "",
                    "name": function.get("name") or "",
                    "arguments": arguments,
                    "raw_arguments": raw_args if isinstance(raw_args, str) else "",
                }
            )
        return {
            "content": message.get("content") or "",
            "reasoning_content": message.get("reasoning_content") or "",
            "model": data.get("model") or payload["model"],
            "prompt_tokens": int(usage.get("prompt_tokens") or 0),
            "completion_tokens": int(usage.get("completion_tokens") or 0),
            "tool_calls": tool_calls,
            "finish_reason": choices[0].get("finish_reason"),
            "raw": data,
        }

    async def stream_chat(
        self,
        messages: list[dict[str, Any]],
        *,
        max_tokens: int = 600,
        temperature: float = 0.2,
        model: str | None = None,
    ):
        if not self.configured:
            raise ProviderAuthError("未配置 OPENCODE_GO_API_KEY")
        payload: dict[str, Any] = {
            "model": model or self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        from app.integrations.ai.streaming import (
            parse_openai_stream_chunk,
            parse_openai_stream_usage,
        )

        prompt_tokens = completion_tokens = 0
        response_model = str(payload["model"])
        try:
            async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    headers=self._headers(messages),
                    json=payload,
                ) as response:
                    if response.status_code in (401, 403):
                        raise ProviderAuthError(
                            "OpenCode Go API Key 无效、未订阅，或客户端被网关拒绝"
                        )
                    if response.status_code == 429:
                        raise ProviderRateLimitError(
                            "OpenCode Go 限流或订阅额度不足"
                        )
                    if response.status_code >= 400:
                        body = (await response.aread()).decode(errors="ignore")
                        raise ProviderUnavailable(
                            f"OpenCode Go HTTP {response.status_code}: {body[:200]}"
                        )
                    async for line in response.aiter_lines():
                        line = line.strip()
                        if not line or not line.startswith("data:"):
                            continue
                        raw = line[5:].strip()
                        if raw == "[DONE]":
                            break
                        try:
                            data = json.loads(raw)
                        except ValueError:
                            continue
                        text = parse_openai_stream_chunk(data)
                        p_tokens, c_tokens, chunk_model = parse_openai_stream_usage(data)
                        prompt_tokens = p_tokens or prompt_tokens
                        completion_tokens = c_tokens or completion_tokens
                        response_model = chunk_model or response_model
                        if text:
                            yield {"type": "delta", "text": text}
        except (ProviderAuthError, ProviderRateLimitError, ProviderUnavailable):
            raise
        except httpx.HTTPError as exc:
            raise ProviderUnavailable(
                f"OpenCode Go 流式请求失败：{type(exc).__name__}"
            ) from exc
        yield {
            "type": "done",
            "model": response_model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        }

    async def tag_image(
        self,
        image_url: str,
        *,
        prompt: str | None = None,
        model: str | None = None,
    ) -> dict:
        """Ask the approved model for strict-JSON cover-image tags.

        The caller passes a data URL (downscaled JPEG) so only the cover image
        is sent, never listing text/addresses.
        """
        system = prompt or (
            "你是租房房源封面审核器。只输出 JSON 对象，不要 markdown："
            '{"scene":"实拍|样板间|不确定",'
            '"tags":[{"tag":"实拍|样板间|精装修|采光好|采光差|水渍|霉斑|图文不符",'
            '"confidence":0.0}],"summary":"一句话"}。'
            "只根据图片可见内容判断；不确定就不要编造。"
        )
        messages = [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "请分析这张租房封面。"},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            },
        ]
        result = await self.chat(
            messages, max_tokens=500, temperature=0, model=model
        )
        text = result.get("content") or result.get("reasoning_content") or ""
        data = self._extract_json(text)
        if data is None:
            raise ProviderUnavailable("OpenCode Go 视觉标签返回无法解析")
        tags: list[dict] = []
        for item in data.get("tags") or []:
            if not isinstance(item, dict):
                continue
            tag = str(item.get("tag") or "").strip()
            try:
                confidence = float(item.get("confidence"))
            except (TypeError, ValueError):
                confidence = 0.5
            if tag:
                tags.append(
                    {
                        "tag": tag[:32],
                        "confidence": round(min(1.0, max(0.0, confidence)), 2),
                    }
                )
        return {
            "scene": str(data.get("scene") or "")[:32],
            "tags": tags[:12],
            "summary": str(data.get("summary") or "")[:200],
            "model": result.get("model") or "",
            "prompt_tokens": result.get("prompt_tokens") or 0,
            "completion_tokens": result.get("completion_tokens") or 0,
        }

    @staticmethod
    def _extract_json(text: str) -> dict | None:
        import re

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

    async def test(self) -> ProviderTestResult:
        started = time.monotonic()
        if not self.configured:
            return ProviderTestResult(
                ok=False,
                message="未配置 OPENCODE_GO_API_KEY",
                latency_ms=0,
            )
        result = await self.chat(
            [{"role": "user", "content": "只回复 OK"}],
            max_tokens=256,
            temperature=0,
        )
        latency = int((time.monotonic() - started) * 1000)
        text = result["content"] or result["reasoning_content"]
        return ProviderTestResult(
            ok=bool(text),
            message=f"{result['model']} 可用，返回 {text[:20]}",
            latency_ms=latency,
            quota_units=1,
        )
