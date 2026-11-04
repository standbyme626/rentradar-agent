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


def test_parse_explicit_company_changes_destination_condition():
    conditions = parse_conditions("公司换到南山科技园，预算 4000，通勤 40 分钟")
    assert conditions["company"] == "南山科技园"
    assert conditions["company_explicit"] is True
    assert conditions["budget"] == 4000


def test_parse_company_variants():
    assert parse_conditions("上班地点在福田CBD，预算 5000")["company"] == "福田CBD"
    assert (
        parse_conditions("公司位置：深圳湾科技生态园")["company"]
        == "深圳湾科技生态园"
    )
    assert parse_conditions("公司在会展中心")["company"] == "深圳会展中心"


def test_default_company_is_not_treated_as_an_explicit_change():
    conditions = parse_conditions("预算 4000，5 号线，通勤 40 分钟")
    assert conditions["company"] == "深圳会展中心"
    assert conditions["company_explicit"] is False


def test_company_location_does_not_become_residential_district():
    conditions = parse_conditions("公司换到南山科技园，预算 4000，5 号线，通勤 40 分钟")
    assert conditions["company"] == "南山科技园"
    assert conditions["district"] is None


def test_company_and_explicit_residential_district_are_separate():
    conditions = parse_conditions("公司在南山科技园，想住龙岗，预算 4000")
    assert conditions["company"] == "南山科技园"
    assert conditions["district"] == "龙岗区"


def test_long_commute_marks_long_search():
    conditions = parse_conditions("预算 4500，5 号线，接受 60 分钟通勤")
    assert conditions["isLong"] is True


def test_dependent_tool_args_need_concrete_ids():
    from app.services.agent_service import _has_concrete_tool_args

    assert _has_concrete_tool_args({"listing_id": 12}) is True
    assert _has_concrete_tool_args({"listing_ids": [1, 2]}) is True
    assert _has_concrete_tool_args({"listing_id": "$top"}) is False
    assert _has_concrete_tool_args({"listing_ids": []}) is False


def test_condition_reset_words():
    base = parse_conditions("预算 4000，5 号线，通勤 50 分钟，想要两居，电梯")
    cleared = parse_conditions("预算不限，先不看通勤，户型不限，不要电梯", base)
    assert cleared["budget"] is None
    assert cleared["commute"] is None
    assert cleared["layout"] is None
    assert "电梯" not in cleared["must"]
