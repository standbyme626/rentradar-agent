from types import SimpleNamespace

from PIL import Image

from app.services import image_service


def _image(color: int, size=(32, 24)) -> Image.Image:
    return Image.new("RGB", size, (color, color, color))


def _pattern(reverse: bool = False) -> Image.Image:
    image = Image.new("L", (32, 24))
    values = []
    for y in range(24):
        for x in range(32):
            values.append((x * 7 + y * 5) % 256)
    if reverse:
        values = list(reversed(values))
    image.putdata(values)
    return image.convert("RGB")


def test_dhash_is_stable_and_discriminates():
    first = image_service.dhash(_pattern())
    second = image_service.dhash(_pattern())
    different = image_service.dhash(_pattern(reverse=True))
    assert first == second
    assert len(first) == 16
    assert image_service.hamming(first, second) == 0
    assert image_service.hamming(first, different) > 0


def test_image_quality_flags_low_resolution_and_darkness():
    quality = image_service.image_quality(_image(10, size=(320, 200)))
    assert quality["width"] == 320
    assert quality["height"] == 200
    assert quality["low_resolution"] is True
    assert quality["very_dark"] is True
    bright = image_service.image_quality(_image(250, size=(800, 600)))
    assert bright["low_resolution"] is False
    assert bright["very_dark"] is False


def test_classify_requires_two_fake_signals():
    duplicate = {
        "code": "duplicate_image",
        "label": "重复封面",
        "severity": "high",
        "confidence": 0.85,
    }
    price = {
        "code": "price_outlier",
        "label": "价格异常",
        "severity": "high",
        "confidence": 0.6,
    }
    low_res = {"code": "low_resolution", "label": "低清", "severity": "low", "confidence": 0.6}
    assert image_service.classify([duplicate]) == ("watch", 0.85)
    verdict, confidence = image_service.classify([duplicate, price])
    assert verdict == "suspicious"
    assert confidence > 0.5
    assert image_service.classify([low_res]) == ("clear", 0.5)


def test_agency_wording_signal_matches_listing_text():
    listing = SimpleNamespace(
        title="整租·XX公寓 1室1厅",
        community_name="XX公寓",
        raw={"desc": "免押金，押一付一，个人直租"},
        id=1,
    )
    signal = image_service._agency_signal(listing)
    assert signal is not None
    assert "公寓" in signal["evidence"]["keywords"]
    clean = SimpleNamespace(title="整租·花园小区 2室1厅", community_name="花园小区", raw={}, id=2)
    assert image_service._agency_signal(clean) is None


def test_price_signal_requires_enough_samples():
    class FakeSession:
        def __init__(self, values):
            self.values = values
            self.calls = 0

        async def execute(self, _stmt):
            self.calls += 1

            class Result:
                def __init__(self, values):
                    self.values = values

                def scalars(self):
                    return self

                def all(self):
                    return self.values

            return Result(self.values)

    listing = SimpleNamespace(
        id=1,
        rent=2000,
        layout="2室",
        community_id=10,
        city_id=1,
        district="福田区",
    )
    import asyncio

    no_match = asyncio.run(
        image_service._price_signal(FakeSession([3000, 3200, 3300, 3400]), listing)
    )
    assert no_match is None
    signal = asyncio.run(
        image_service._price_signal(FakeSession([3200, 3300, 3400, 3500, 3600, 3700]), listing)
    )
    assert signal is not None
    assert signal["code"] == "price_outlier"


def test_cover_url_only_allows_beike_cdn():
    allowed = SimpleNamespace(
        image_url="https://ke-image.ljcdn.com/wanjia/example.jpg"
    )
    blocked = SimpleNamespace(image_url="http://127.0.0.1:8010/api/admin/overview")
    assert image_service._cover_url(allowed) == allowed.image_url
    assert image_service._cover_url(blocked) is None
