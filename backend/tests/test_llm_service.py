from app.services import llm_service
from app.services.agent_service import _merge_llm_conditions, parse_conditions


def test_extract_json_with_fence():
    data = llm_service._extract_json('```json\n{"budget": 4000, "must": ["电梯"]}\n```')
    assert data == {"budget": 4000, "must": ["电梯"]}


def test_validate_intent_filters_invalid_values():
    parsed = llm_service._validate_intent(
        {
            "budget": 3500,
            "commute": 200,
            "layout": "两居",
            "district": "龙岗区",
            "must": ["电梯", "豪宅"],
            "company": "深圳会展中心",
        }
    )
    assert parsed["budget"] == 3500
    assert "commute" not in parsed
    assert "layout" not in parsed
    assert parsed["district"] == "龙岗区"
    assert parsed["must"] == ["电梯"]


def test_merge_meta_sums_tokens():
    merged = llm_service.merge_meta(
        {
            "model": "deepseek-ai/DeepSeek-V4.1-Flash-1017",
            "prompt_tokens": 100,
            "completion_tokens": 20,
            "cost": 0.0,
            "fallback": False,
            "error": None,
            "calls": [["llm_parse", "m", "1ms", "100+20"]],
        },
        {
            "model": "",
            "prompt_tokens": 50,
            "completion_tokens": 10,
            "cost": 0.0,
            "fallback": True,
            "error": "answer fallback",
            "calls": [],
        },
    )
    assert merged["model"] == "deepseek-ai/DeepSeek-V4.1-Flash-1017"
    assert merged["prompt_tokens"] == 150
    assert merged["completion_tokens"] == 30
    assert merged["fallback"] is False
    assert merged["error"] == "answer fallback"


def test_merge_llm_conditions():
    rule = parse_conditions("预算 4500，5 号线，通勤 40 分钟内，最好有电梯")
    merged = _merge_llm_conditions(
        rule,
        {"budget": 3500, "layout": "2室", "must": ["电梯"], "district": None},
    )
    # Deterministic explicit budget wins over an LLM rewrite.
    assert merged["budget"] == 4500
    assert merged["layout"] == "2室"
    assert merged["commute"] == 40
    assert "电梯" in merged["must"]
    assert merged["isLong"] is False


def test_merge_ignores_hallucinated_company_and_district():
    rule = parse_conditions("预算 4500，5 号线，通勤 40 分钟内")
    merged = _merge_llm_conditions(
        rule,
        {"company": "南山科技园", "district": "南山区"},
        "预算 4500，5 号线，通勤 40 分钟内",
    )
    assert merged["company"] == "深圳会展中心"
    assert merged["company_explicit"] is False
    assert merged["district"] is None


def test_merge_keeps_explicit_company():
    rule = parse_conditions("公司换到南山科技园，预算 4000")
    merged = _merge_llm_conditions(
        rule,
        {"company": "南山科技园", "district": "南山区"},
        "公司换到南山科技园，预算 4000",
    )
    assert merged["company"] == "南山科技园"
    assert merged["company_explicit"] is True
    assert merged["district"] is None


def test_history_block_keeps_recent_turns():
    from app.services.llm_service import _history_block

    block = _history_block(
        [
            {"role": "user", "text": "预算 4000，5 号线"},
            {"role": "assistant", "text": "找到 6 套"},
        ]
    )
    assert "用户: 预算 4000，5 号线" in block
    assert "助手: 找到 6 套" in block
    assert _history_block([]) == ""


def test_compact_history_folds_older_turns():
    from app.services.memory_service import compact

    history = [{"role": "user", "text": f"第{i}轮"} for i in range(1, 9)]
    recent, summary = compact(history)
    assert len(recent) == 6
    assert "第1轮" in summary
    assert "第2轮" in summary
    assert "第8轮" not in summary
