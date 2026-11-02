"""坐标转换：WGS84/CGCS2000 <-> GCJ-02 <-> BD-09，参数顺序均为 (lng, lat)。"""

import math

PI = math.pi
A = 6378245.0
EE = 0.00669342162296594323
X_PI = PI * 3000.0 / 180.0

CRS_ALIASES = {
    "wgs84": "wgs84",
    "cgcs2000": "wgs84",
    "gcj02": "gcj02",
    "bd09": "bd09",
}


def out_of_china(lng: float, lat: float) -> bool:
    return not (72.004 <= lng <= 137.8347 and 0.8293 <= lat <= 55.8271)


def _transform_lat(lng: float, lat: float) -> float:
    ret = -100.0 + 2.0 * lng + 3.0 * lat + 0.2 * lat * lat + 0.1 * lng * lat
    ret += 0.2 * math.sqrt(abs(lng))
    ret += (20.0 * math.sin(6.0 * lng * PI) + 20.0 * math.sin(2.0 * lng * PI)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lat * PI) + 40.0 * math.sin(lat / 3.0 * PI)) * 2.0 / 3.0
    ret += (160.0 * math.sin(lat / 12.0 * PI) + 320 * math.sin(lat * PI / 30.0)) * 2.0 / 3.0
    return ret


def _transform_lng(lng: float, lat: float) -> float:
    ret = 300.0 + lng + 2.0 * lat + 0.1 * lng * lng + 0.1 * lng * lat
    ret += 0.1 * math.sqrt(abs(lng))
    ret += (20.0 * math.sin(6.0 * lng * PI) + 20.0 * math.sin(2.0 * lng * PI)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lng * PI) + 40.0 * math.sin(lng / 3.0 * PI)) * 2.0 / 3.0
    ret += (150.0 * math.sin(lng / 12.0 * PI) + 300.0 * math.sin(lng / 30.0 * PI)) * 2.0 / 3.0
    return ret


def wgs84_to_gcj02(lng: float, lat: float) -> tuple[float, float]:
    if out_of_china(lng, lat):
        return lng, lat
    dlat = _transform_lat(lng - 105.0, lat - 35.0)
    dlng = _transform_lng(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * PI
    magic = math.sin(radlat)
    magic = 1 - EE * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((A * (1 - EE)) / (magic * sqrtmagic) * PI)
    dlng = (dlng * 180.0) / (A / sqrtmagic * math.cos(radlat) * PI)
    return lng + dlng, lat + dlat


def gcj02_to_wgs84(lng: float, lat: float) -> tuple[float, float]:
    if out_of_china(lng, lat):
        return lng, lat
    wgs_lng, wgs_lat = lng, lat
    for _ in range(4):
        gcj_lng, gcj_lat = wgs84_to_gcj02(wgs_lng, wgs_lat)
        wgs_lng += lng - gcj_lng
        wgs_lat += lat - gcj_lat
    return wgs_lng, wgs_lat


def gcj02_to_bd09(lng: float, lat: float) -> tuple[float, float]:
    if out_of_china(lng, lat):
        return lng, lat
    z = math.sqrt(lng * lng + lat * lat) + 0.00002 * math.sin(lat * X_PI)
    theta = math.atan2(lat, lng) + 0.000003 * math.cos(lng * X_PI)
    return z * math.cos(theta) + 0.0065, z * math.sin(theta) + 0.006


def bd09_to_gcj02(lng: float, lat: float) -> tuple[float, float]:
    if out_of_china(lng, lat):
        return lng, lat
    x = lng - 0.0065
    y = lat - 0.006
    z = math.sqrt(x * x + y * y) - 0.00002 * math.sin(y * X_PI)
    theta = math.atan2(y, x) - 0.000003 * math.cos(x * X_PI)
    return z * math.cos(theta), z * math.sin(theta)


def wgs84_to_bd09(lng: float, lat: float) -> tuple[float, float]:
    return gcj02_to_bd09(*wgs84_to_gcj02(lng, lat))


def bd09_to_wgs84(lng: float, lat: float) -> tuple[float, float]:
    return gcj02_to_wgs84(*bd09_to_gcj02(lng, lat))


def cgcs2000_to_gcj02(lng: float, lat: float) -> tuple[float, float]:
    return wgs84_to_gcj02(lng, lat)


def gcj02_to_cgcs2000(lng: float, lat: float) -> tuple[float, float]:
    return gcj02_to_wgs84(lng, lat)


def _normalize(crs: str) -> str:
    key = str(crs).strip().lower().replace("-", "").replace("_", "")
    try:
        return CRS_ALIASES[key]
    except KeyError:
        raise ValueError(f"unsupported coordinate system: {crs}") from None


def convert(lng: float, lat: float, src: str, dst: str) -> tuple[float, float]:
    source = _normalize(src)
    target = _normalize(dst)
    if source == target:
        return lng, lat
    converters = {
        ("wgs84", "gcj02"): wgs84_to_gcj02,
        ("gcj02", "wgs84"): gcj02_to_wgs84,
        ("gcj02", "bd09"): gcj02_to_bd09,
        ("bd09", "gcj02"): bd09_to_gcj02,
        ("wgs84", "bd09"): wgs84_to_bd09,
        ("bd09", "wgs84"): bd09_to_wgs84,
    }
    return converters[(source, target)](lng, lat)
