from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.settings_service import (
    DEFAULT_ADMIN_SETTINGS,
    _parse_hhmm,
    is_quiet_now,
)
from app.services.settings_service import time as time_cls


def test_defaults_include_runtime_guards():
    assert DEFAULT_ADMIN_SETTINGS["notifyScoreMin"] == 75
    assert DEFAULT_ADMIN_SETTINGS["priceDropPct"] == 8.0
    assert DEFAULT_ADMIN_SETTINGS["monitorPush"] is True
    assert DEFAULT_ADMIN_SETTINGS["quietStart"] == "23:00"


def test_quiet_window_wraps_midnight():
    settings = {
        **DEFAULT_ADMIN_SETTINGS,
        "quiet": True,
        "quietStart": "23:00",
        "quietEnd": "08:00",
    }
    tz = ZoneInfo("Asia/Shanghai")
    assert is_quiet_now(settings, datetime(2026, 10, 31, 23, 30, tzinfo=tz))
    assert is_quiet_now(settings, datetime(2026, 10, 31, 2, 0, tzinfo=tz))
    assert not is_quiet_now(settings, datetime(2026, 10, 31, 12, 0, tzinfo=tz))
    assert not is_quiet_now(
        {**settings, "quiet": False}, datetime(2026, 10, 31, 23, 30, tzinfo=tz)
    )


def test_quiet_window_same_day():
    settings = {
        **DEFAULT_ADMIN_SETTINGS,
        "quiet": True,
        "quietStart": "01:00",
        "quietEnd": "06:00",
    }
    tz = ZoneInfo("Asia/Shanghai")
    assert is_quiet_now(settings, datetime(2026, 10, 31, 3, 0, tzinfo=tz))
    assert not is_quiet_now(settings, datetime(2026, 10, 31, 7, 0, tzinfo=tz))
    assert _parse_hhmm("25:00", time_cls(0, 0)) == time_cls(0, 0)
