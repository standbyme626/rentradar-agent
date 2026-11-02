from types import SimpleNamespace

from app.services.monitor_service import matches_conditions, normalize_conditions


def listing(**overrides):
    data = {
        "rent": 4000,
        "layout": "2室1厅",
        "district": "龙岗区",
        "tags": ["电梯", "精装"],
        "orientation": "南",
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_normalize_ui_conditions():
    normalized = normalize_conditions(
        {
            "budget": "4000 元/月以内",
            "commute": "≤ 40 分钟",
            "layout": "2室",
            "district": "龙岗区",
            "must": "电梯 / 精装",
            "line": "5号线",
        }
    )
    assert normalized["budget"] == 4000
    assert normalized["commute"] == 40
    assert normalized["layout"] == "2室"
    assert normalized["district"] == "龙岗区"
    assert normalized["must"] == ["电梯", "精装"]


def test_normalize_unlimited_values():
    normalized = normalize_conditions(
        {"budget": "不限", "commute": "不限", "layout": "不限", "must": "无硬条件"}
    )
    assert normalized["budget"] is None
    assert normalized["commute"] is None
    assert normalized["layout"] is None
    assert normalized["must"] == []


def test_matches_budget_layout_district_and_must():
    conditions = normalize_conditions(
        {
            "budget": "4000",
            "layout": "2室",
            "district": "龙岗区",
            "must": "电梯 / 精装 / 南向",
            "commute": "40",
        }
    )
    assert matches_conditions(listing(), conditions, commute_minutes=35)
    assert not matches_conditions(listing(rent=4500), conditions, commute_minutes=35)
    assert not matches_conditions(listing(layout="1室"), conditions, commute_minutes=35)
    assert not matches_conditions(listing(district="福田区"), conditions, commute_minutes=35)
    assert not matches_conditions(listing(tags=["电梯"]), conditions, commute_minutes=35)
    assert not matches_conditions(listing(orientation="北"), conditions, commute_minutes=35)
    assert not matches_conditions(listing(), conditions, commute_minutes=45)
    assert not matches_conditions(listing(), conditions, commute_minutes=None)


def test_normalize_rough_ui_conditions():
    normalized = normalize_conditions(
        {
            "budget": "3500–4500 元/月",
            "commute": "≤ 40 分钟",
            "layout": "1–2 居室",
            "must": "电梯（待详情核实）",
        }
    )
    assert normalized["budget"] == 3500
    assert normalized["layout"] is None
    assert normalized["must"] == ["电梯"]

    normalized = normalize_conditions({"layout": "两居优先"})
    assert normalized["layout"] == "2室"
