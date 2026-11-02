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
    ProviderTestResult,
    ProviderUnavailable,
    QuotaPolicy,
)


class DidiMcpProvider(BaseProvider):
    meta = ProviderMeta(
        code="didi_mcp",
        name="滴滴 MCP",
        domain=ProviderDomain.maps,
        capabilities=frozenset(
            {
                Capability.poi_search,
                Capability.reverse_geocode,
                Capability.route_driving,
                Capability.route_transit,
                Capability.taxi_estimate,
            }
        ),
        auth="mcp",
        coord_system="GCJ02",
        description="MCP JSON-RPC；默认沙箱，只做搜索/路线/估价，不提供下单方法",
        docs_url="https://mcp.didichuxing.com/api",
        quota=QuotaPolicy(period="month", limit=0),
        priority=15,
    )

    def __init__(self) -> None:
        self.configured = bool(settings.didi_mcp_key)
        self._client: httpx.AsyncClient | None = None
        self._session_id: str | None = None
        self._initialized = False

    @property
    def endpoint(self) -> str:
        base = settings.didi_mcp_url.rstrip("/")
        return f"{base}?key={settings.didi_mcp_key}"

    @property
    def sandbox(self) -> bool:
        return "sandbox" in settings.didi_mcp_url

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self._session_id:
            headers["mcp-session-id"] = self._session_id
        return headers

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=45.0)
        return self._client

    @staticmethod
    def _parse(response: httpx.Response) -> dict | None:
        if "text/event-stream" in response.headers.get("content-type", ""):
            for line in response.text.splitlines():
                if not line.startswith("data:"):
                    continue
                raw = line[5:].strip()
                if not raw or raw == "[DONE]":
                    continue
                try:
                    return json.loads(raw)
                except ValueError:
                    continue
            return None
        try:
            return response.json()
        except ValueError:
            return None

    async def _post(self, payload: dict) -> dict:
        client = await self._get_client()
        response = await client.post(self.endpoint, json=payload, headers=self._headers())
        if response.status_code >= 400:
            raise ProviderUnavailable(f"滴滴 MCP HTTP {response.status_code}")
        data = self._parse(response)
        if not isinstance(data, dict):
            raise ProviderUnavailable("滴滴 MCP 返回非 JSON")
        if "error" in data:
            error = data["error"]
            message = error.get("message") if isinstance(error, dict) else str(error)
            raise ProviderUnavailable(f"滴滴 MCP 错误：{str(message)[:200]}")
        session = response.headers.get("mcp-session-id")
        if session:
            self._session_id = session
        return data

    async def _initialize(self) -> None:
        if self._initialized:
            return
        if not self.configured:
            raise ProviderAuthError("未配置 DIDI_MCP_KEY")
        data = await self._post(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "rentradar", "version": "0.1"},
                },
            }
        )
        if "result" not in data:
            raise ProviderUnavailable("滴滴 MCP 初始化失败")
        if self._session_id:
            await self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})
        self._initialized = True

    async def list_tools(self) -> list[dict]:
        await self._initialize()
        data = await self._post({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        result = data.get("result") or {}
        return result.get("tools") or []

    async def _call(self, name: str, arguments: dict[str, Any]) -> Any:
        await self._initialize()
        data = await self._post(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            }
        )
        result = data.get("result") or {}
        texts = [
            item.get("text", "")
            for item in result.get("content") or []
            if isinstance(item, dict) and item.get("type") == "text"
        ]
        text = "\n".join(texts).strip()
        if not text:
            return result
        try:
            return json.loads(text)
        except ValueError:
            return {"text": text}

    async def test(self) -> ProviderTestResult:
        started = time.monotonic()
        tools = await self.list_tools()
        latency = int((time.monotonic() - started) * 1000)
        mode = "沙箱" if self.sandbox else "生产"
        return ProviderTestResult(
            ok=True,
            message=f"{mode} MCP 可用，{len(tools)} 个工具",
            latency_ms=latency,
        )

    async def search_place(self, keywords: str, city: str = "深圳") -> Any:
        return await self._call("maps_textsearch", {"keywords": keywords, "city": city})

    async def regeocode(self, lng: float, lat: float) -> Any:
        return await self._call("maps_regeocode", {"location": f"{lng},{lat}"})

    async def drive_route(self, origin: str, destination: str) -> Any:
        return await self._call(
            "maps_direction_driving",
            {"origin": origin, "destination": destination, "need_geo": False},
        )

    async def transit_route(
        self, origin: str, destination: str, city: str = "深圳"
    ) -> Any:
        return await self._call(
            "maps_direction_transit",
            {"origin": origin, "destination": destination, "city": city},
        )

    async def taxi_estimate(
        self,
        from_lng: float,
        from_lat: float,
        from_name: str,
        to_lng: float,
        to_lat: float,
        to_name: str,
    ) -> Any:
        return await self._call(
            "taxi_estimate",
            {
                "from_lng": str(from_lng),
                "from_lat": str(from_lat),
                "from_name": from_name,
                "to_lng": str(to_lng),
                "to_lat": str(to_lat),
                "to_name": to_name,
            },
        )

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
