from app.services.agent_service import conditions_summary, parse_conditions


def test_parse_initial_prompt():
    conditions = parse_conditions(
        "公司在会展中心，预算 4000，想住 5 号线沿线，通勤 40 分钟内，最好有电梯"
    )
    assert conditions["budget"] == 4000
    assert conditions["commute"] == 40
    assert conditions["line"] == "5号线"
    assert conditions["company"] == "深圳会展中心"
    assert "电梯" in conditions["must"]
    assert conditions["isLong"] is False


def test_parse_longgang_prompt():
    conditions = parse_conditions("预算 3000，龙岗方向，接受 60 分钟通勤，两居优先")
    assert conditions["budget"] == 3000
    assert conditions["commute"] == 60
    assert conditions["layout"] == "2室"
    assert conditions["district"] == "龙岗区"
    assert conditions["isLong"] is True


def test_follow_up_merges_base_conditions():
    base = parse_conditions("预算 4500，5 号线，通勤 40 分钟内，最好有电梯")
    conditions = parse_conditions("预算压到 3500，最好两居", base)
    assert conditions["budget"] == 3500
    assert conditions["layout"] == "2室"
    assert conditions["commute"] == 40
    assert "电梯" in conditions["must"]


def test_conditions_summary():
    conditions = parse_conditions("预算 4000，两居，电梯")
    summary = conditions_summary(conditions)
    assert "预算≤4000" in summary
    assert "2室" in summary
    assert "电梯" in summary
