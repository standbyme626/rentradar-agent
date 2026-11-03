import json
from pathlib import Path

import httpx
import pytest

from app.sources.base import SourceError
from app.sources.beike_filters import (
    build_line_shards,
    fetch_filter_config,
    find_line,
    parse_filter_payload,
)

FIXTURE = Path(__file__).parent / "fixtures" / "beike_filter_sz.json"


def load_payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def load_config() -> dict:
    return parse_filter_payload(load_payload())


def test_find_line_by_name_number_id_and_pinyin():
    config = load_config()
    for query in ("5号线", "5", "5号线(环中线)", "li110460696", "110460696"):
        assert find_line(config, query)["id"] == 110460696


def test_find_line_prefers_exact_name_over_substring():
    config = load_config()
    # "5号线" must not resolve to "15号线" even though it is a substring.
    assert find_line(config, "5号线")["name"] == "5号线(环中线)"
    assert find_line(config, "15号线")["id"] == 111111


def test_find_line_rejects_unknown_and_ambiguous():
    config = load_config()
    with pytest.raises(SourceError, match="unknown subway line"):
        find_line(config, "99号线")
    with pytest.raises(SourceError, match="ambiguous subway line"):
        find_line(config, "号线")


def test_build_line_shards_skips_unlimited_and_keeps_order():
    plan = build_line_shards(load_config(), "5号线")
    assert plan["line_id"] == 110460696
    assert plan["line_condition"] == "li110460696"
    assert [item["name"] for item in plan["shards"]] == ["赤湾", "荔湾", "铁路公园"]

    first = plan["shards"][0]
    assert first["condition"] == "li110460696s100021264"
    assert first["station_id"] == 100021264
    assert first["lat"] == pytest.approx(22.485483)
    assert first["lng"] == pytest.approx(113.904203)
    assert first["is_transfer"] is True


def test_build_line_shards_requires_station_conditions():
    config = {
        "li": {
            "options": [
                {
                    "name": "X号线",
                    "id": 1,
                    "pinyin": "li1/",
                    "children": [{"id": 0, "name": "不限", "pinyin": "/"}],
                }
            ]
        }
    }
    with pytest.raises(SourceError, match="no station conditions"):
        build_line_shards(config, "X号线")


def test_parse_filter_payload_errors():
    with pytest.raises(SourceError, match="no data"):
        parse_filter_payload({"status": 0, "data": []})
    with pytest.raises(SourceError, match="error"):
        parse_filter_payload({"status": 1, "msg": "boom"})


async def test_fetch_filter_config_uses_city_id():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json=load_payload())

    config = await fetch_filter_config("sz", transport=httpx.MockTransport(handler))
    assert seen["params"]["city_id"] == "440300"
    assert find_line(config, "5号线")["id"] == 110460696


async def test_fetch_filter_config_errors():
    with pytest.raises(SourceError, match="no city_id"):
        await fetch_filter_config("unknown")

    def http_error(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    with pytest.raises(SourceError, match="http 500"):
        await fetch_filter_config("sz", transport=httpx.MockTransport(http_error))
