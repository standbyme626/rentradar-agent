from datetime import UTC, datetime
from types import SimpleNamespace

from app.services.admin_service import build_crawl_coverage


def run(condition: str, total: int, pages: int, fetched: int, *, status: str = "done"):
    return SimpleNamespace(
        id=1,
        status=status,
        started_at=datetime(2026, 11, 4, 1, 0, tzinfo=UTC),
        finished_at=datetime(2026, 11, 4, 1, 5, tzinfo=UTC),
        stats={
            "line": condition,
            "total": total,
            "pages": pages,
            "fetched": fetched,
            "duplicates": 3,
            "suspect_skipped": pages * 30 < total,
        },
    )


def test_build_crawl_coverage_reports_shards_and_completeness():
    filters = {
        "shard_conditions": ["a", "b", "c"],
        "shard_labels": ["站一", "站二", "站三"],
        "shard_line": "li110460696",
        "shard_cursor": 2,
        "page_size": 30,
    }
    latest = {"a": run("a", 100, 4, 100), "b": run("b", 100, 2, 60)}
    counts = {"line:a": 100, "line:b": 50}
    payload = build_crawl_coverage(1, "任务 1", filters, latest, counts)

    assert payload["task_id"] == 1
    assert payload["line"] == "li110460696"
    assert payload["shard_cursor"] == 2
    assert len(payload["shards"]) == 3
    first, second, third = payload["shards"]
    assert first["station"] == "站一"
    assert first["listings"] == 100 and first["complete"] is True
    assert second["listings"] == 50 and second["complete"] is False
    assert second["last_run"]["suspect_skipped"] is True
    assert third["last_run"] is None and third["complete"] is False
    assert payload["summary"] == {
        "shards": 3,
        "listings": 150,
        "complete": 1,
        "scanned": 2,
        "last_scan_at": datetime(2026, 11, 4, 1, 0, tzinfo=UTC),
    }


def test_build_crawl_coverage_without_plan():
    payload = build_crawl_coverage(None, None, {}, {}, {})
    assert payload["shards"] == []
    assert payload["summary"]["shards"] == 0
    assert payload["summary"]["last_scan_at"] is None
