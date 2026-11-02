import asyncio
import time
from collections import defaultdict

from fastapi import Request

from app.core.config import settings

_failures: dict[str, list[float]] = defaultdict(list)
_lock = asyncio.Lock()


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    return request.client.host if request.client else "unknown"


def _prune(key: str, now: float) -> list[float]:
    window = max(1, settings.login_window_minutes) * 60
    values = [item for item in _failures.get(key, []) if now - item < window]
    if values:
        _failures[key] = values
    else:
        _failures.pop(key, None)
    return values


async def login_blocked(key: str) -> bool:
    async with _lock:
        return len(_prune(key, time.time())) >= max(1, settings.login_max_failures)


async def record_login_failure(key: str) -> None:
    async with _lock:
        now = time.time()
        values = _prune(key, now)
        values.append(now)
        _failures[key] = values


async def clear_login_failures(key: str) -> None:
    async with _lock:
        _failures.pop(key, None)
