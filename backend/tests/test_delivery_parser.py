from app.delivery.meituan import extract_probe


def test_extract_probe_from_accessibility():
    items = [
        {"caption": "地址:吓井二小区, 按钮, 双击重新选择地址"},
        {
            "caption": "一家专做牛肉的店 起送 ¥20 配送 约¥2 1.4km 25-30分钟 4.4 分"
        },
        {"caption": "福记牛肉店 起送 ¥25 配送 约¥1.4 3.1km 30分钟 4.5 分"},
        {"caption": "木屋烧烤 起送 ¥20 免配送费 3.1km 35分钟 4.0 分"},
    ]
    result = extract_probe(items)
    assert result["address_label"] == "吓井二小区"
    assert result["eta_min_low"] == 30
    assert result["eta_min_high"] == 30
    assert result["merchant_count"] == 3
    assert result["fee"] == 1.4
    assert result["confidence"] == 0.9


def test_extract_probe_requires_eta():
    try:
        extract_probe([{"caption": "地址:吓井二小区"}])
    except ValueError as exc:
        assert "no ETA" in str(exc)
    else:
        raise AssertionError("expected ValueError")
