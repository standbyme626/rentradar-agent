from types import SimpleNamespace

import pytest

from app.services.shard_service import (
    crawl_commands,
    fetch_line_total,
    probe_shards,
)
from app.sources.base import CaptchaRequiredError, SourceError


class FakeFetcher:
    def __init__(self, by_condition: dict | None = None, errors: dict | None = None):
        self.by_condition = by_condition or {}
        self.errors = errors or {}
        self.calls: list[dict] = []
        self.resets = 0
        self.closed = False

    def reset_condition(self) -> None:
        self.resets += 1

    async def fetch_page(
        self, page: int, *, line: str = "", sort: str = "newest", limit: int = 30
    ):
        self.calls.append({"page": page, "line": line, "sort": sort, "limit": limit})
        if line in self.errors:
            raise self.errors[line]
        pages = self.by_condition[line]
        codes, total = pages[min(page - 1, len(pages) - 1)]
        return [SimpleNamespace(source_listing_id=code) for code in codes], total

    async def close(self) -> None:
        self.closed = True


def shard(name: str, condition: str) -> dict:
    return {"name": name, "condition": condition, "station_id": 1}


async def test_probe_shards_dedupes_and_summarizes():
    line = {"line_id": 110460696, "line_name": "5号线(环中线)", "line_condition": "li110460696"}
    shards = [shard("赤湾", "a"), shard("荔湾", "b")]
    fetcher = FakeFetcher({"a": [(["x", "y"], 2)], "b": [(["y", "z"], 2)]})

    report = await probe_shards(
        line,
        shards,
        pages=1,
        page_size=30,
        line_total=10,
        interval=(0, 0),
        fetcher_factory=lambda city: fetcher,
    )

    assert report["line"]["condition"] == "li110460696"
    first, second = report["shards"]
    assert (first["unique"], first["overlap"], first["complete"]) == (2, 0, True)
    assert (second["unique"], second["overlap"], second["complete"]) == (1, 1, True)
    assert report["summary"] == {
        "shards": 2,
        "fetched": 4,
        "unique": 3,
        "duplicates": 1,
        "scope_total": 4,
        "line_total": 10,
        "coverage_vs_scope": 0.75,
        "coverage_vs_line": 0.3,
        "complete_shards": 2,
        "failed_shards": 0,
        "pages_probed": 2,
        "expected_pages": 2,
        "page_size": 30,
        "partial": False,
    }
    assert fetcher.resets == 2
    assert fetcher.closed is True


async def test_probe_shards_reports_incomplete_reasons():
    line = {"line_id": 1, "line_name": "5号线", "line_condition": "li1"}
    shards = [shard("A", "a"), shard("B", "b")]
    offset_pages = [([f"b{index}" for index in range(30)], 4000) for _ in range(100)]
    fetcher = FakeFetcher({"a": [(["only-one"], 61)], "b": offset_pages})

    report = await probe_shards(
        line, shards, pages=0, page_size=30, interval=(0, 0), fetcher_factory=lambda city: fetcher
    )

    short, limited = report["shards"]
    assert short["complete"] is False
    assert short["expected_pages"] == 3
    assert short["missing_reason"] == "未抓全（已抓 1/61）"
    assert limited["complete"] is False
    assert limited["pages"] == 100
    assert limited["fetched"] == 3000
    assert limited["missing_reason"] == "超过 offset 上限（最多 3000 条）"
    assert report["summary"]["partial"] is True
    assert report["summary"]["complete_shards"] == 0


async def test_probe_shards_records_errors_and_propagates_captcha():
    line = {"line_id": 1, "line_name": "5号线", "line_condition": "li1"}
    shards = [shard("A", "a"), shard("B", "b")]
    fetcher = FakeFetcher(
        {"a": [(["x"], 1)]},
        errors={"b": SourceError("boom")},
    )
    report = await probe_shards(
        line, shards, pages=1, interval=(0, 0), fetcher_factory=lambda city: fetcher
    )
    assert report["shards"][1]["error"] == "boom"
    assert "请求失败" in report["shards"][1]["missing_reason"]
    assert report["summary"]["failed_shards"] == 1

    captcha = FakeFetcher(errors={"a": CaptchaRequiredError("verify")})
    with pytest.raises(CaptchaRequiredError):
        await probe_shards(
            line,
            [shard("A", "a")],
            pages=1,
            interval=(0, 0),
            fetcher_factory=lambda city: captcha,
        )
    assert captcha.closed is True


async def test_fetch_line_total_reads_single_item():
    fetcher = FakeFetcher({"li110460696": [(["x"], 6336)]})
    total = await fetch_line_total("li110460696", fetcher_factory=lambda city: fetcher)
    assert total == 6336
    assert fetcher.calls[0]["limit"] == 1
    assert fetcher.closed is True


def test_crawl_commands_respect_completeness():
    shards = [shard("A", "a"), shard("B", "b"), shard("C", "c")]
    results = [
        {"condition": "a", "expected_pages": 2, "complete": True, "pages": 2},
        {"condition": "b", "expected_pages": 4, "complete": False, "pages": 1},
    ]
    commands = crawl_commands(shards, task_id=7, page_size=30, results=results)
    assert commands[0]["command"] == (
        "python -m app.cli crawl --task-id 7 --line a --pages 2 --transport api --full-scan"
    )
    assert commands[1]["command"] == (
        "python -m app.cli crawl --task-id 7 --line b --pages 4 --transport api"
    )
    assert commands[2]["command"] == (
        "python -m app.cli crawl --task-id 7 --line c --pages 1 --transport api"
    )
