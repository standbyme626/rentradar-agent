import asyncio
import json
import random
import time
from urllib.parse import quote, urlparse

import httpx
import websockets

from app.core.config import settings
from app.sources.base import CaptchaRequiredError, LoginRequiredError, SourceError

CAPTCHA_MARKERS = (
    "人机验证",
    "安全验证",
    "请完成验证",
    "验证码",
    "访问异常",
    "滑块验证",
    "captcha",
    "verify",
    "antibot",
)


class CDPError(SourceError):
    pass


def _page_key(url: str) -> tuple[str, str]:
    parsed = urlparse(url)
    return parsed.netloc, (parsed.path.rstrip("/") or "/")


def _looks_like_captcha(url: str, text: str) -> bool:
    haystack = f"{url}\n{text}".lower()
    return any(marker in haystack for marker in CAPTCHA_MARKERS)


class CDPPageFetcher:
    """Fetch pages in one reused Chrome tab, paced like a person.

    A fresh tab per page is a strong bot signal (and triggered a captcha).
    Reuse an existing tab on the same host when possible; only close tabs we
    created ourselves.
    """

    def __init__(
        self,
        base_url: str | None = None,
        *,
        timeout: float = 40.0,
        wait_selector: str = "[data-house_code]",
        page_interval: tuple[float, float] = (6.0, 12.0),
    ) -> None:
        self.base_url = (base_url or settings.cdp_url).rstrip("/")
        self.timeout = timeout
        self.wait_selector = wait_selector
        self.page_interval = page_interval
        self._msg_id = 0
        self._target_id: str | None = None
        self._own_tab = False
        self._ws = None
        self._connected = False
        self._last_fetch = 0.0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    async def close(self) -> None:
        self._connected = False
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None
        if self._target_id and self._own_tab:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    await client.get(f"{self.base_url}/json/close/{self._target_id}")
            except Exception:
                pass
        self._target_id = None
        self._own_tab = False

    async def _find_existing_target(self, url: str) -> dict | None:
        host = urlparse(url).netloc
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.base_url}/json/list")
                response.raise_for_status()
                targets = response.json()
        except Exception:
            return None
        for target in targets:
            if target.get("type") != "page":
                continue
            if urlparse(str(target.get("url") or "")).netloc == host:
                return target
        return None

    async def _ensure_tab(self, url: str) -> None:
        if self._connected and self._ws is not None:
            return
        target = await self._find_existing_target(url)
        if target is None:
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    response = await client.put(f"{self.base_url}/json/new?{quote(url, safe='')}")
                    response.raise_for_status()
                    target = response.json()
            except Exception as exc:
                raise CDPError(
                    f"cannot open CDP tab at {self.base_url}: {exc}. "
                    "check the boss-cdp-tunnel service and Windows Chrome"
                ) from exc
            self._own_tab = True
        self._target_id = target["id"]
        try:
            self._ws = await websockets.connect(
                target["webSocketDebuggerUrl"],
                open_timeout=10,
                max_size=64 * 1024 * 1024,
            )
        except Exception as exc:
            raise CDPError(f"CDP websocket failed: {exc}") from exc
        self._connected = True
        await self._call(self._ws, "Page.enable")
        await self._call(self._ws, "Runtime.enable")

    async def _pace(self) -> None:
        if self._last_fetch:
            wait = random.uniform(*self.page_interval) - (time.monotonic() - self._last_fetch)
            if wait > 0:
                await asyncio.sleep(wait)
        else:
            await asyncio.sleep(random.uniform(0.8, 2.0))

    async def fetch_html(self, url: str) -> str:
        await self._ensure_tab(url)
        await self._pace()
        try:
            await self._call(self._ws, "Page.navigate", {"url": url})
            html = await self._wait_for_content(url)
            self._last_fetch = time.monotonic()
            return html
        except (LoginRequiredError, CaptchaRequiredError, CDPError):
            raise
        except Exception as exc:
            raise CDPError(f"CDP navigation failed: {exc}") from exc

    async def _call(self, ws, method: str, params: dict | None = None) -> dict:
        self._msg_id += 1
        message_id = self._msg_id
        await ws.send(json.dumps({"id": message_id, "method": method, "params": params or {}}))
        while True:
            raw = await asyncio.wait_for(ws.recv(), timeout=20.0)
            message = json.loads(raw)
            if message.get("id") != message_id:
                continue
            if "error" in message:
                raise CDPError(f"CDP {method} failed: {message['error']}")
            return message.get("result", {})

    async def _evaluate(self, ws, expression: str):
        result = await self._call(
            ws,
            "Runtime.evaluate",
            {"expression": expression, "returnByValue": True},
        )
        return (result.get("result") or {}).get("value")

    async def _wait_for_content(self, expected_url: str) -> str:
        deadline = time.monotonic() + self.timeout
        expected_key = _page_key(expected_url)
        selector = json.dumps(self.wait_selector)
        expression = (
            "JSON.stringify({url:location.href,ready:document.readyState,"
            f"count:document.querySelectorAll({selector}).length,"
            "text:(document.body?document.body.innerText.slice(0,400):'')})"
        )
        state: dict = {}
        while time.monotonic() < deadline:
            raw = await self._evaluate(self._ws, expression)
            try:
                state = json.loads(raw or "{}")
            except json.JSONDecodeError:
                state = {}
            current_url = str(state.get("url") or "")
            text = str(state.get("text") or "")
            if "clogin" in current_url or "passport" in current_url or "/login" in current_url:
                raise LoginRequiredError(
                    f"login required for {current_url}; "
                    "log in inside the controlled Chrome profile"
                )
            if _looks_like_captcha(current_url, text):
                raise CaptchaRequiredError(
                    f"verification required at {current_url}; solve it manually in Chrome"
                )
            if (
                state.get("ready") in ("interactive", "complete")
                and int(state.get("count") or 0) > 0
                and _page_key(current_url) == expected_key
            ):
                break
            await asyncio.sleep(1.0)
        else:
            text_preview = str(state.get("text"))[:120]
            raise CDPError(
                f"timed out waiting for {self.wait_selector}: "
                f"{state.get('url')} count={state.get('count')} text={text_preview}"
            )

        html = await self._evaluate(self._ws, "document.documentElement.outerHTML")
        if not isinstance(html, str) or len(html) < 5000:
            raise CDPError("page HTML is suspiciously small")
        return html
