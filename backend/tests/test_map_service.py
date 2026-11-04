import asyncio
from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException

from app.core.config import settings
from app.services import map_service


def test_validate_tile_rejects_bad_values():
    with pytest.raises(HTTPException):
        map_service.validate_tile("nope", 10, 1, 1)
    with pytest.raises(HTTPException):
        map_service.validate_tile("vec", 2, 0, 0)
    with pytest.raises(HTTPException):
        map_service.validate_tile("vec", 5, 32, 1)
    map_service.validate_tile("vec", 5, 31, 31)


def test_tile_path_is_layer_zoom_xy(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "map_tile_cache_dir", str(tmp_path))
    path = map_service._tile_dir("vec", 12, 3456, 789)
    assert path == tmp_path / "vec" / "12" / "3456" / "789.png"


def test_cached_tile_is_returned_without_provider_call(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "map_tile_cache_dir", str(tmp_path))
    monkeypatch.setattr(settings, "tianditu_api_key", "test-key")
    path = map_service._tile_dir("cva", 10, 100, 200)
    path.parent.mkdir(parents=True)
    path.write_bytes(b"\x89PNG" + b"0" * 100)
    called = False

    async def fake_invoke(*_args, **_kwargs):
        nonlocal called
        called = True
        return {"content": b"new", "content_type": "image/png"}

    monkeypatch.setattr(map_service.provider_runtime, "invoke", fake_invoke)
    content, content_type, state = asyncio.run(
        map_service.get_tile(None, "cva", 10, 100, 200)
    )
    assert state == "hit"
    assert content.startswith(b"\x89PNG")
    assert content_type == "image/png"
    assert called is False


def test_missed_tile_is_fetched_and_cached(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "map_tile_cache_dir", str(tmp_path))
    monkeypatch.setattr(settings, "tianditu_api_key", "test-key")

    async def fake_invoke(*_args, **_kwargs):
        return {"content": b"\x89PNG" + b"1" * 100, "content_type": "image/png"}

    monkeypatch.setattr(map_service.provider_runtime, "invoke", fake_invoke)
    content, _content_type, state = asyncio.run(
        map_service.get_tile(None, "vec", 9, 10, 20)
    )
    assert state == "miss"
    assert content.startswith(b"\x89PNG")
    cached = map_service._tile_dir("vec", 9, 10, 20)
    assert cached.is_file()
    assert cached.read_bytes() == content


def test_get_tile_without_key_is_unavailable(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "map_tile_cache_dir", str(tmp_path))
    monkeypatch.setattr(settings, "tianditu_api_key", "")
    with pytest.raises(HTTPException) as error:
        asyncio.run(map_service.get_tile(None, "vec", 9, 10, 20))
    assert error.value.status_code == 503


def test_mercator_center_is_half_world():
    x, y = map_service._mercator(0, 0)
    assert x == 0.5
    assert abs(y - 0.5) < 1e-9
    x, _y = map_service._mercator(114.0579, 22.5431)
    assert 0.8 < x < 0.83


def test_fresh_cache_respects_ttl(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "map_tile_cache_dir", str(tmp_path))
    monkeypatch.setattr(settings, "map_tile_ttl_days", 30)
    path = tmp_path / "vec.png"
    path.write_bytes(b"x")
    assert map_service._fresh(path) is True
    old = datetime.now().timestamp() - timedelta(days=31).total_seconds()
    import os

    os.utime(path, (old, old))
    assert map_service._fresh(path) is False
