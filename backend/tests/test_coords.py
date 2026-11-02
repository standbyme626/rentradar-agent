import pytest

from app.geo import coords

BEIJING_WGS84 = (116.404, 39.915)
BEIJING_GCJ02 = (116.41024449916938, 39.91640428150164)
SHENZHEN_GCJ02 = (114.059352, 22.532423)


def test_wgs84_to_gcj02_known_beijing():
    lng, lat = coords.wgs84_to_gcj02(*BEIJING_WGS84)
    assert lng == pytest.approx(BEIJING_GCJ02[0], abs=1e-9)
    assert lat == pytest.approx(BEIJING_GCJ02[1], abs=1e-9)


def test_gcj02_wgs84_round_trip():
    wgs_lng, wgs_lat = coords.gcj02_to_wgs84(*SHENZHEN_GCJ02)
    back_lng, back_lat = coords.wgs84_to_gcj02(wgs_lng, wgs_lat)
    assert back_lng == pytest.approx(SHENZHEN_GCJ02[0], abs=1e-6)
    assert back_lat == pytest.approx(SHENZHEN_GCJ02[1], abs=1e-6)


def test_bd09_round_trip():
    bd_lng, bd_lat = coords.gcj02_to_bd09(*SHENZHEN_GCJ02)
    back_lng, back_lat = coords.bd09_to_gcj02(bd_lng, bd_lat)
    assert back_lng == pytest.approx(SHENZHEN_GCJ02[0], abs=1e-6)
    assert back_lat == pytest.approx(SHENZHEN_GCJ02[1], abs=1e-6)


def test_out_of_china_is_unchanged():
    assert coords.wgs84_to_gcj02(139.6917, 35.6895) == (139.6917, 35.6895)
    assert coords.gcj02_to_bd09(139.6917, 35.6895) == (139.6917, 35.6895)


def test_cgcs2000_is_treated_as_wgs84():
    assert coords.cgcs2000_to_gcj02(*BEIJING_WGS84) == coords.wgs84_to_gcj02(
        *BEIJING_WGS84
    )
    assert coords.gcj02_to_cgcs2000(*BEIJING_GCJ02) == coords.gcj02_to_wgs84(
        *BEIJING_GCJ02
    )


def test_convert_dispatch():
    assert coords.convert(*SHENZHEN_GCJ02, "gcj02", "wgs84") == coords.gcj02_to_wgs84(
        *SHENZHEN_GCJ02
    )
    assert coords.convert(*SHENZHEN_GCJ02, "wgs84", "cgcs2000") == SHENZHEN_GCJ02
    with pytest.raises(ValueError):
        coords.convert(*SHENZHEN_GCJ02, "gcj02", "unknown")
