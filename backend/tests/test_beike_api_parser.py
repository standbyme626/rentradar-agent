import json
from pathlib import Path

import httpx
import pytest

from app.sources import beike_api
from app.sources.base import CaptchaRequiredError, EmptyPageError, SourceError

FIXTURE = Path(__file__).parent / "fixtures" / "beike_api_sz.json"


def load_payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_parse_list_payload():
    drafts, total = beike_api.parse_list_payload(load_payload())
    assert total == 6688
    assert len(drafts) == 3

    first = drafts[0]
    assert first.source_listing_id == "SZ2223778397576757248"
    assert first.title == "整租·恒立心海湾花园 4室2厅"
    assert first.community_name == "恒立心海湾花园"
    assert first.district == "南山区"
    assert first.layout == "4室2厅2卫"
    assert first.area == 149.0
    assert first.rent == 12000
    assert first.orientation == "南"
    assert first.floor == "中楼层"
    assert first.raw["lat"] == pytest.approx(22.507795620093905)
    assert first.raw["lng"] == pytest.approx(113.90227876915979)
    assert first.raw["latest_price_change"]["changePrice"] == 388
    assert {"电梯", "精装", "近地铁"} <= set(first.tags)
    assert "有电梯" not in first.tags
    assert first.image_url and first.image_url.endswith(".800x600.jpg")
    assert first.url == "https://sz.zu.ke.com/zufang/SZ2223778397576757248.html"
    assert first.agent_type == "unknown"


def test_parse_apartment_and_floor_mapping():
    drafts, _ = beike_api.parse_list_payload(load_payload())
    apartment = drafts[1]
    assert apartment.source_listing_id == "1010009"
    assert apartment.agent_type == "apartment"
    assert apartment.floor is None
    assert apartment.raw["pc_url"].startswith("https://sz.zu.ke.com/apartment/")

    third = drafts[2]
    assert third.floor == "高楼层"


def test_build_params_condition_and_offset_cap():
    condition = beike_api.build_condition("li110460696", "newest")
    assert condition == "li110460696/rco11"
    params = beike_api.build_api_params("sz", 2, limit=30, condition=condition)
    assert params["city_id"] == "440300"
    assert params["offset"] == 30
    assert params["limit"] == 30
    assert params["condition"] == "li110460696/rco11"
    assert params["feed_query_id"] == ""
    assert beike_api.max_pages(30) == 100
    with pytest.raises(SourceError):
        beike_api.build_api_params("sz", 101)
    with pytest.raises(SourceError):
        beike_api.build_api_params("unknown", 1)


def test_parse_payload_errors():
    with pytest.raises(EmptyPageError):
        beike_api.parse_list_payload({"status": 0, "data": {}})
    with pytest.raises(CaptchaRequiredError):
        beike_api.parse_list_payload({"status": 1, "msg": "请完成安全验证"})
    with pytest.raises(SourceError):
        beike_api.parse_list_payload({"status": 1, "msg": "boom"})


async def test_fetcher_uses_app_api_params():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json=load_payload())

    fetcher = beike_api.BeikeAPIFetcher(transport=httpx.MockTransport(handler))
    try:
        drafts, total = await fetcher.fetch_page(1, line="li110460696", sort="newest")
    finally:
        await fetcher.close()

    assert total == 6688
    assert len(drafts) == 3
    assert seen["params"]["condition"] == "li110460696/rco11"
    assert seen["params"]["offset"] == "0"
    assert seen["params"]["city_id"] == "440300"


async def test_fetcher_passes_feed_query_id_between_pages():
    payload = load_payload()
    payload["data"]["feed_query_id"] = "feed-1"
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(dict(request.url.params))
        return httpx.Response(200, json=payload)

    fetcher = beike_api.BeikeAPIFetcher(
        transport=httpx.MockTransport(handler), page_interval=(0, 0)
    )
    try:
        await fetcher.fetch_page(1, line="li110460696")
        await fetcher.fetch_page(2, line="li110460696")
    finally:
        await fetcher.close()

    assert seen[0]["feed_query_id"] == ""
    assert seen[1]["feed_query_id"] == "feed-1"
    assert seen[1]["offset"] == "30"


async def test_fetcher_raises_captcha_on_403():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="verify")

    fetcher = beike_api.BeikeAPIFetcher(transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(CaptchaRequiredError):
            await fetcher.fetch_page(1, line="li110460696")
    finally:
        await fetcher.close()
