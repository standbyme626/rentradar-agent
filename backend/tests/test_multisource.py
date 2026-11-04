import json

import pytest

from app.services.dedupe_service import (
    Candidate,
    is_cross_source_duplicate,
    normalize_layout,
    normalize_text,
)
from app.sources import manual
from app.sources.base import SourceError


def candidate(**overrides):
    data = {
        "community_name": "信义假日名城",
        "layout": "2室1厅",
        "rent": 4500,
        "area": 70,
    }
    data.update(overrides)
    return Candidate(**data)


def test_normalize_helpers():
    assert normalize_layout("2室1厅") == "2室1厅"
    assert normalize_layout("3 室 2 厅") == "3室2厅"
    assert normalize_text(" 信义 · 假日名城 ") == "信义假日名城"


def test_cross_source_duplicate_requires_same_community_layout_and_rent():
    assert is_cross_source_duplicate(candidate(), candidate())
    assert is_cross_source_duplicate(candidate(rent=4600), candidate(rent=4500))
    assert not is_cross_source_duplicate(candidate(rent=5000), candidate(rent=4500))
    assert not is_cross_source_duplicate(candidate(community_name="其他小区"), candidate())
    assert not is_cross_source_duplicate(
        candidate(layout="2室2厅"), candidate(rent=4500, layout="2室1厅")
    )
    assert not is_cross_source_duplicate(candidate(area=90), candidate(area=60))


def test_manual_parse_json_and_csv(tmp_path):
    json_path = tmp_path / "feed.json"
    json_path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "id": "MANUAL-1",
                        "communityName": "品牌公寓 A",
                        "district": "南山区",
                        "layout": "1室1厅",
                        "area": 35,
                        "rent": 4800,
                        "tags": ["电梯", "精装"],
                        "city": "sz",
                    },
                    {"id": "bad", "rent": "not-a-number"},
                ]
            }
        ),
        encoding="utf-8",
    )
    drafts, errors = manual.load_feed(json_path)
    assert len(drafts) == 1
    assert drafts[0].source_listing_id == "MANUAL-1"
    assert drafts[0].rent == 4800
    assert drafts[0].tags == ["电梯", "精装"]
    assert drafts[0].raw["city"] == "sz"
    assert len(errors) == 1

    csv_path = tmp_path / "feed.csv"
    csv_path.write_text(
        "id,url,community_name,layout,area,rent\nM-2,https://example.com/2,小区B,1室1厅,40,3900\n",
        encoding="utf-8",
    )
    drafts, errors = manual.load_feed(csv_path)
    assert not errors
    assert drafts[0].community_name == "小区B"
    assert drafts[0].rent == 3900


def test_manual_feed_errors(tmp_path):
    with pytest.raises(SourceError):
        manual.load_feed(tmp_path / "missing.json")
    bad = tmp_path / "bad.txt"
    bad.write_text("x", encoding="utf-8")
    with pytest.raises(SourceError):
        manual.load_feed(bad)
