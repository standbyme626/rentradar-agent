"""Bounded conversation memory helpers.

Keep a short recent window for verbatim recall and a compact summary for older
turns. This mirrors the working-memory + summary pattern used by agent memory
systems, without adding a vector database or a second model call.
"""

MAX_RECENT_TURNS = 6
MAX_SUMMARY_CHARS = 1200


def _line(item: dict, limit: int = 90) -> str:
    role = "用户" if item.get("role") == "user" else "助手"
    text = " ".join(str(item.get("text") or "").split())
    return f"{role}: {text[:limit]}" if text else ""


def compact(
    history: list[dict],
    summary: str = "",
    *,
    max_recent: int = MAX_RECENT_TURNS,
    max_summary_chars: int = MAX_SUMMARY_CHARS,
) -> tuple[list[dict], str]:
    """Return (recent_turns, summary); older turns fold into the summary."""
    if len(history) <= max_recent:
        return history, summary
    dropped = history[:-max_recent]
    recent = history[-max_recent:]
    lines = [summary.strip()] if summary.strip() else []
    for item in dropped:
        line = _line(item)
        if line:
            lines.append(line)
    folded = "\n".join(lines)
    if len(folded) > max_summary_chars:
        folded = folded[-max_summary_chars:]
    return recent, folded
