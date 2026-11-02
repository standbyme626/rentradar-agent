import asyncio
import json

from app.geo.coords import cgcs2000_to_gcj02
from app.integrations.maps.tianditu import TiandituProvider, keyword_for_types


def test_keyword_mapping():
    assert keyword_for_types("050000") == "餐饮"
    assert keyword_for_types("050600") == "夜宵"
    assert keyword_for_types("060200|060300|060400") == "便利店"


def test_geocode_converts_cgcs_to_gcj02(monkeypatch):
    provider = TiandituProvider()
    expected = cgcs2000_to_gcj02(114.05483, 22.53345)

    async def fake_get(params):
        assert "keyWord" in json.loads(params["ds"])
        return {
            "msg": "ok",
            "location": {
                "lon": "114.05483",
                "lat": "22.53345",
                "level": "兴趣点",
                "keyWord": "深圳会展中心",
            },
        }

    monkeypatch.setattr(provider, "_get", fake_get)
    result = asyncio.run(provider.geocode("深圳会展中心"))
    assert result is not None
    assert abs(result["lng"] - expected[0]) < 1e-6
    assert abs(result["lat"] - expected[1]) < 1e-6
    assert result["formatted_address"] == "深圳会展中心"


def test_around_count_sends_query_type_3(monkeypatch):
    provider = TiandituProvider()
    captured = {}

    async def fake_request(url, params):
        captured["url"] = url
        captured["post"] = json.loads(params["postStr"])
        return {"count": 695, "status": {"infocode": 1000}}

    monkeypatch.setattr(provider, "_request", fake_request)
    count = asyncio.run(
        provider.around_count("114.05483,22.53345", "050000", radius=1000)
    )
    assert count == 695
    assert captured["post"]["queryType"] == 3
    assert captured["post"]["keyWord"] == "餐饮"
    assert captured["post"]["queryRadius"] == 1000
