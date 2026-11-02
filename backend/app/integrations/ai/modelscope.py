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


class ModelScopeProvider(BaseProvider):
    meta = ProviderMeta(
        code="modelscope_deepseek",
        name="魔搭 DeepSeek V4.1 Flash",
        domain=ProviderDomain.ai,
        capabilities=frozenset({Capability.chat}),
        auth="api_key",
        coord_system="无",
        description=(
            "ModelScope OpenAI 兼容推理；默认 DeepSeek-V4.1-Flash-1017，"
            "免费额度约 2000 次/天，运行时受 aiDailyCap 约束"
        ),
        docs_url="https://www.modelscope.cn/my/myaccesstoken",
        quota=QuotaPolicy(period="day", limit=2000),
        priority=10,
    )

    def __init__(self) -> None:
        self.configured = bool(settings.modelscope_api_key)

    @property
    def base_url(self) -> str:
        return settings.modelscope_base_url.rstrip("/")

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        max_tokens: int = 600,
        temperature: float = 0.2,
        model: str | None = None,
    ) -> dict:
        if not self.configured:
            raise ProviderAuthError("未配置 MODELSCOPE_API_KEY")
        payload = {
            "model": model or settings.modelscope_model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        headers = {
            "Authorization": f"Bearer {settings.modelscope_api_key}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions", headers=headers, json=payload
                )
        except httpx.HTTPError as exc:
            raise ProviderUnavailable(f"魔搭请求失败：{type(exc).__name__}") from exc
        if response.status_code in (401, 403):
            raise ProviderAuthError("魔搭 API Key 无效或未授权")
        if response.status_code == 429:
            raise ProviderRateLimitError("魔搭限流或免费额度不足")
        if response.status_code >= 400:
            raise ProviderUnavailable(
                f"魔搭 HTTP {response.status_code}: {response.text[:200]}"
            )
        try:
            data = response.json()
        except ValueError as exc:
            raise ProviderUnavailable("魔搭返回非 JSON") from exc
        choices = data.get("choices") or []
        if not choices:
            raise ProviderUnavailable("魔搭返回空 choices")
        message = choices[0].get("message") or {}
        usage = data.get("usage") or {}
        return {
            "content": message.get("content") or "",
            "reasoning_content": message.get("reasoning_content") or "",
            "model": data.get("model") or payload["model"],
            "prompt_tokens": int(usage.get("prompt_tokens") or 0),
            "completion_tokens": int(usage.get("completion_tokens") or 0),
            "raw": data,
        }

    async def test(self) -> ProviderTestResult:
        started = time.monotonic()
        if not self.configured:
            return ProviderTestResult(
                ok=False,
                message="未配置 MODELSCOPE_API_KEY",
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
