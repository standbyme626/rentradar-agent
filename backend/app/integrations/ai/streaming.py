"""Helpers for OpenAI-compatible streamed chat completions."""

from typing import Any


def parse_openai_stream_chunk(data: dict[str, Any]) -> str:
    """Return the text delta from one SSE JSON object (empty for metadata)."""
    choices = data.get("choices") or []
    if not choices:
        return ""
    delta = choices[0].get("delta") or {}
    content = delta.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        # Some gateways send content parts; keep text parts only.
        return "".join(
            str(part.get("text") or "")
            for part in content
            if isinstance(part, dict) and part.get("type") in (None, "text")
        )
    return ""


def parse_openai_stream_usage(data: dict[str, Any]) -> tuple[int, int, str]:
    usage = data.get("usage") or {}
    return (
        int(usage.get("prompt_tokens") or 0),
        int(usage.get("completion_tokens") or 0),
        str(data.get("model") or ""),
    )
