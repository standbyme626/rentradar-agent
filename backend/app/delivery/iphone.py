import asyncio
import json
import subprocess
from pathlib import Path

from app.core.config import settings


class IPhoneError(Exception):
    pass


async def _run(cmd: list[str], timeout: float = 60.0) -> subprocess.CompletedProcess:
    return await asyncio.to_thread(
        subprocess.run,
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


class LocationSession:
    """保持 DVT 虚拟定位会话；退出时终止并清除模拟位置。"""

    def __init__(self, lng: float, lat: float) -> None:
        self.lng = lng
        self.lat = lat
        self.proc: asyncio.subprocess.Process | None = None

    async def __aenter__(self):
        self.proc = await asyncio.create_subprocess_exec(
            settings.pymd3_bin,
            "developer",
            "dvt",
            "simulate-location",
            "set",
            f"{self.lat:.6f}",
            f"{self.lng:.6f}",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        await asyncio.sleep(6)
        if self.proc.returncode is not None:
            output = b""
            if self.proc.stdout is not None:
                output = await self.proc.stdout.read()
            raise IPhoneError(f"location session exited: {output.decode(errors='ignore')[:300]}")
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self.proc is not None and self.proc.returncode is None:
            self.proc.terminate()
            try:
                await asyncio.wait_for(self.proc.wait(), timeout=5)
            except TimeoutError:
                self.proc.kill()
        await _run(
            [settings.pymd3_bin, "developer", "dvt", "simulate-location", "clear"],
            timeout=30,
        )


class IPhoneClient:
    def __init__(self) -> None:
        self.pymd3 = settings.pymd3_bin
        self.ipctl = settings.ipctl_bin

    async def tap(self, x: int, y: int) -> None:
        result = await _run([self.ipctl, "tap", str(x), str(y)], timeout=15)
        if result.returncode != 0:
            raise IPhoneError(f"tap failed: {(result.stdout + result.stderr)[:200]}")
        await asyncio.sleep(0.3)

    async def launch_meituan(self) -> None:
        await _run(
            [self.pymd3, "developer", "dvt", "pkill", "imeituan"],
            timeout=30,
        )
        await asyncio.sleep(2)
        # 回到桌面第一页，再左滑到第二页（美团在第二页左下角）
        for _ in range(2):
            await _run([self.ipctl, "home"], timeout=15)
            await asyncio.sleep(1)
        await _run(
            [
                self.ipctl,
                "drag",
                "52000",
                "32000",
                "8000",
                "32000",
                "--steps",
                "20",
                "--duration",
                "0.3",
            ],
            timeout=15,
        )
        await asyncio.sleep(2)
        await self.tap(7456, 47800)
        await asyncio.sleep(10)

    async def open_delivery(self) -> None:
        await self.tap(7864, 10894)
        await asyncio.sleep(7)

    async def refresh_delivery(self) -> None:
        await self.tap(7864, 61450)
        await asyncio.sleep(6)

    async def ensure_delivery_home(self) -> list[dict]:
        items = await self.accessibility()
        for _ in range(2):
            captions = [item.get("caption", "") for item in items]
            if any("起送" in caption and "分钟" in caption for caption in captions):
                return items
            if any("回首页" in caption for caption in captions):
                await self.tap(32738, 61450)
                await asyncio.sleep(6)
                items = await self.accessibility()
                continue
            if any("选择收货地址" in caption for caption in captions):
                await self.tap(4600, 5328)
                await asyncio.sleep(2)
            await self.open_delivery()
            items = await self.accessibility()
        captions = [item.get("caption", "") for item in items]
        raise IPhoneError(f"delivery page not ready: {captions[:8]}")

    async def accessibility(self) -> list[dict]:
        last_error = ""
        for _ in range(2):
            try:
                result = await _run(
                    [self.pymd3, "developer", "accessibility", "list-items"], timeout=35
                )
            except subprocess.TimeoutExpired:
                last_error = "timeout"
                await asyncio.sleep(2)
                continue
            if result.returncode != 0:
                last_error = (result.stdout + result.stderr)[:300]
                await asyncio.sleep(2)
                continue
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError:
                last_error = f"invalid JSON: {result.stdout[:200]}"
                await asyncio.sleep(2)
        raise IPhoneError(f"accessibility failed: {last_error}")

    async def screenshot(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        result = await _run([self.ipctl, "shot", str(path)], timeout=40)
        if result.returncode != 0 or not path.exists():
            raise IPhoneError(f"screenshot failed: {(result.stdout + result.stderr)[:200]}")
