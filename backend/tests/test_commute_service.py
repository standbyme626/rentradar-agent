from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.services.commute_service import (
    percentile,
    summarize,
    with_destination,
)


def sample(
    duration_s: int,
    *,
    bucket: str | None = "08:00",
    provider: str = "szmc",
    minutes_ago: int = 0,
    mode: str = "metro",
    direction: str = "community_to_destination",
):
    return SimpleNamespace(
        duration_s=duration_s,
        depart_bucket=bucket,
        provider=provider,
        mode=mode,
        direction=direction,
        transfers=1,
        walk_min=5.0,
        raw={"walk_min": 5.0},
        fetched_at=datetime.now(UTC) - timedelta(minutes=minutes_ago),
    )


def test_percentile_interpolates():
    assert percentile([], 0.5) is None
    assert percentile([30], 0.9) == 30
    assert percentile([10, 20, 30], 0.5) == 20
    assert percentile([10, 20, 30], 0.9) == 28
    assert percentile([10, 20, 30, 40], 0.5) == 25


def test_summarize_p50_p90_and_buckets():
    rows = [
        sample(1800, bucket="07:30"),
        sample(1800, bucket="08:00"),
        sample(2400, bucket="08:30"),
    ]
    stats = summarize(rows)
    assert stats is not None
    assert stats["samples"] == 3
    assert stats["buckets"] == ["07:30", "08:00", "08:30"]
    assert stats["bucket_count"] == 3
    assert stats["multi_bucket"] is True
    assert stats["p50_min"] == 30.0
    assert stats["p90_min"] == 38.0
    assert stats["static"] is False
    assert stats["provider"] == "szmc"
    assert stats["mode"] == "metro"


def test_summarize_prefers_szmc_and_flags_static():
    rows = [
        sample(9999, bucket=None, provider="amap"),
        sample(1800, bucket="07:30"),
        sample(1800, bucket="08:00"),
        sample(1800, bucket="08:30"),
    ]
    stats = summarize(rows)
    assert stats["samples"] == 3
    assert stats["provider"] == "szmc"
    assert stats["static"] is True
    assert stats["p50_min"] == 30.0
    assert stats["p90_min"] == 30.0


def test_summarize_empty_and_destination_labels():
    assert summarize([]) is None
    stats = summarize([sample(1800)])
    enriched = with_destination(stats, {"address": "深圳会展中心", "example": True})
    assert enriched["destination"] == "深圳会展中心"
    assert enriched["example"] is True
    assert enriched["direction_label"] == "小区→公司"
