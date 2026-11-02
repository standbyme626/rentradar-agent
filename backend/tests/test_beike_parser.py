from pathlib import Path

from app.sources.beike import build_list_url, parse_list

FIXTURE = Path(__file__).parent / "fixtures" / "beike_list_sz.html"


def test_parse_list_fixture():
    html = FIXTURE.read_text(encoding="utf-8")
    drafts = parse_list(html)
    assert len(drafts) == 30
    first = drafts[0]
    assert first.source_listing_id
    assert first.title.startswith("整租·")
    assert first.community_name
    assert first.district
    assert first.layout
    assert first.area and first.area > 0
    assert first.rent and first.rent > 0
    assert first.url.startswith("https://sz.zu.ke.com/zufang/")
    assert first.agent_type in {"apartment", "unknown"}


def test_parse_apartment_card_without_community_links():
    html = FIXTURE.read_text(encoding="utf-8")
    drafts = parse_list(html)
    apartment = next(item for item in drafts if item.source_listing_id == "1026172")
    assert apartment.community_name == "有巢公寓"
    assert apartment.agent_type == "apartment"
    assert apartment.url.startswith("https://sz.zu.ke.com/apartment/")


def test_build_list_url():
    assert build_list_url("sz") == "https://sz.zu.ke.com/zufang/"
    assert build_list_url("sz", page=2) == "https://sz.zu.ke.com/zufang/pg2/"
    assert build_list_url("sz", sort="newest") == "https://sz.zu.ke.com/zufang/rco11/"
    assert build_list_url("sz", page=2, sort="newest") == "https://sz.zu.ke.com/zufang/rco11/pg2/"
    assert build_list_url("sz", district="longgangqu") == "https://sz.zu.ke.com/zufang/longgangqu/"
    assert (
        build_list_url("sz", page=2, sort="newest", line="li110460696")
        == "https://sz.zu.ke.com/ditiezufang/li110460696/rco11/pg2/"
    )
    assert (
        build_list_url("sz", district="longgangqu", line="li110460696")
        == "https://sz.zu.ke.com/ditiezufang/li110460696/"
    )
