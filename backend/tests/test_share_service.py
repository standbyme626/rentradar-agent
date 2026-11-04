from datetime import UTC, datetime

from app.services import share_service


def test_issue_and_hash_token():
    raw, digest, prefix = share_service.issue_token()
    assert raw.startswith(share_service.TOKEN_PREFIX)
    assert len(digest) == 64
    assert prefix.startswith(share_service.TOKEN_PREFIX)
    assert share_service.hash_token(raw) == digest
    assert share_service.hash_token("other") != digest


def test_aggregate_dashboard_has_no_listing_fields():
    payload = share_service.aggregate_dashboard(
        active=100,
        scored=80,
        communities=20,
        districts=[("龙岗区", 60, 4200, 78.5), ("福田区", 40, 6100, 82.0)],
        price_bands={"<=3000": 5, "3000-5000": 60, "5000-8000": 30, ">8000": 5},
        line5={"summary": {"shards": 37, "listings": 1500, "complete": 10, "scanned": 12}},
        generated_at=datetime(2026, 11, 4, tzinfo=UTC),
    )
    assert payload["totals"]["active_listings"] == 100
    assert payload["totals"]["scored_ratio"] == 0.8
    assert payload["districts"][0]["name"] == "龙岗区"
    assert payload["price_bands"]["3000-5000"] == 60
    assert payload["line5"]["complete"] == 10
    assert "title" not in payload["districts"][0]
    text = str(payload["districts"]) + str(payload["totals"])
    for forbidden in ("title", "image_url", "phone", "address", "contact"):
        assert forbidden not in text
