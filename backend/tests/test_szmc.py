from app.integrations.transit.szmc import (
    build_station_index,
    haversine_m,
    nearest_station,
    parse_lonlat,
)


def sample_payload():
    return {
        "l": [
            {
                "st": [
                    {
                        "sid": "station-a",
                        "n": "深圳北",
                        "sl": "114.030298,22.610496",
                        "poiid": "0410",
                    },
                    {
                        "sid": "station-a",
                        "n": "深圳北",
                        "sl": "114.030298,22.610496",
                        "poiid": "0521",
                    },
                    {
                        "sid": "station-b",
                        "n": "会展中心",
                        "sl": "114.061101,22.534769",
                        "poiid": "0403",
                    },
                ]
            }
        ]
    }


def test_station_index_groups_codes():
    index = build_station_index(sample_payload())
    assert index["station-a"]["codes"] == ["0410", "0521"]
    assert index["station-b"]["name"] == "会展中心"


def test_nearest_station():
    index = build_station_index(sample_payload())
    station, distance = nearest_station(index, 114.0303, 22.6105)
    assert station["sid"] == "station-a"
    assert distance < 10


def test_haversine_and_parse_lonlat():
    assert parse_lonlat("114.1,22.5") == (114.1, 22.5)
    assert haversine_m(0, 0, 0, 0) == 0
    assert 1000 < haversine_m(114.030298, 22.610496, 114.061101, 22.534769) < 10000


def test_station_catalog_shape(monkeypatch):
    import asyncio

    from app.integrations.transit.szmc import SzmcProvider

    provider = SzmcProvider()
    payload = {
        "l": [
            {
                "ln": "5",
                "kn": "地铁5号线(环中线)",
                "cl": "914696",
                "st": [
                    {"sid": "1", "n": "前海湾", "sl": "113.893,22.573"},
                    {"sid": "2", "n": "桂湾", "sl": "113.901,22.567"},
                ],
            }
        ]
    }

    async def fake_load():
        return payload

    monkeypatch.setattr(provider, "_load_payload", fake_load)
    data = asyncio.run(provider.station_catalog())
    assert data["station_count"] == 2
    assert data["lines"][0]["name"] == "地铁5号线(环中线)"
    assert data["lines"][0]["color"] == "914696"
    assert data["lines"][0]["stations"][1]["name"] == "桂湾"
