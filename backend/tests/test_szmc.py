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
