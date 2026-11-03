import csv
import io
from datetime import UTC, datetime

from app.services.listing_service import watchlist_csv


def listing_row() -> dict:
    return {
        "id": 7,
        "source_code": "beike",
        "city_code": "sz",
        "source_listing_id": "SZ1",
        "url": "https://sz.zu.ke.com/zufang/SZ1.html",
        "title": "整租·测试花园 2室1厅",
        "community_name": "测试花园",
        "district": "南山区",
        "layout": "2室1厅",
        "area": 68.5,
        "orientation": "南",
        "floor": "中楼层",
        "rent": 4200,
        "tags": ["电梯"],
        "image_url": None,
        "agent_type": "unknown",
        "score": 82,
        "status": "active",
        "first_seen_at": datetime(2026, 11, 1, tzinfo=UTC),
        "last_seen_at": datetime(2026, 11, 2, tzinfo=UTC),
    }


def test_watchlist_csv_contains_checklist_and_export_fields():
    entries = [
        {
            "listing": listing_row(),
            "state": "viewed",
            "note": "周末复看",
            "updated_at": datetime(2026, 11, 3, 10, 0, tzinfo=UTC),
            "inspection": {
                "items": {"soundproofing": True, "leak": False, "elevator": True},
                "note": "电梯正常，临街略吵",
                "photos": ["https://example.com/a.jpg", "https://example.com/b.jpg"],
            },
        }
    ]
    text = watchlist_csv(entries)
    rows = list(csv.reader(io.StringIO(text)))
    assert rows[0][0] == "房源ID"
    assert rows[0][4] == "面积㎡"
    assert rows[1][0] == "7"
    assert rows[1][1] == "测试花园"
    assert rows[1][5] == "4200"
    assert rows[1][7] == "viewed"
    assert "隔音" in rows[1][9]
    assert "电梯" in rows[1][9]
    assert rows[1][10] == "电梯正常，临街略吵"
    assert rows[1][11] == "2"
    assert rows[1][14] == listing_row()["url"]


def test_watchlist_csv_handles_missing_inspection():
    entries = [
        {
            "listing": listing_row(),
            "state": "new",
            "note": None,
            "updated_at": None,
            "inspection": {"items": {}, "note": None, "photos": []},
        }
    ]
    rows = list(csv.reader(io.StringIO(watchlist_csv(entries))))
    assert rows[1][8] == ""
    assert rows[1][9] == ""
    assert rows[1][13] == ""
