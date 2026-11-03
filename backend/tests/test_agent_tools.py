import pytest

from app.services import agent_tools
from app.services.agent_service import parse_conditions


def test_tool_registry_is_small_and_read_only_by_default():
    names = agent_tools.allowed_tools()
    assert names == [
        "search_listings",
        "get_listing",
        "compare_listings",
        "commute_lookup",
        "price_history",
        "save_monitor",
    ]
    assert agent_tools.WRITE_TOOLS == {"save_monitor"}
    assert "save_monitor" not in agent_tools.planner_tools()


def test_validate_search_args_rejects_invalid_ranges():
    with pytest.raises(agent_tools.ToolArgumentError):
        agent_tools.validate_call("search_listings", {"budget": 100})
    with pytest.raises(agent_tools.ToolArgumentError):
        agent_tools.validate_call("search_listings", {"district": "不存在区"})
    with pytest.raises(agent_tools.ToolArgumentError):
        agent_tools.validate_call("search_listings", {"unknown": 1})
    with pytest.raises(agent_tools.ToolArgumentError):
        agent_tools.validate_call("get_listing", {})


def test_normalize_plan_requires_search_first_and_known_tools():
    plan = agent_tools.normalize_plan(
        {
            "steps": [
                {"tool": "search_listings", "args": {"budget": 4000}},
                {"tool": "price_history", "args": {"listing_id": "$top"}},
            ]
        }
    )
    assert [step["tool"] for step in plan] == ["search_listings", "price_history"]
    assert plan[1]["args"]["listing_id"] == "$top"
    with pytest.raises(agent_tools.ToolArgumentError):
        agent_tools.normalize_plan(
            {"steps": [{"tool": "price_history", "args": {"listing_id": 1}}]}
        )
    with pytest.raises(agent_tools.ToolArgumentError):
        agent_tools.normalize_plan(
            {"steps": [{"tool": "search_listings"}, {"tool": "save_monitor"}]}
        )


def test_rule_plan_selects_followup_tool_by_intent():
    conditions = parse_conditions("预算 4000，通勤 30 分钟")
    tools = [item["tool"] for item in agent_tools.rule_plan("预算 4000，通勤多久", conditions)]
    assert tools == ["search_listings", "commute_lookup"]
    tools = [item["tool"] for item in agent_tools.rule_plan("预算 4000，对比一下", conditions)]
    assert tools == ["search_listings", "compare_listings"]
    tools = [item["tool"] for item in agent_tools.rule_plan("预算 4000，看看价格", conditions)]
    assert tools == ["search_listings", "price_history"]
    tools = [item["tool"] for item in agent_tools.rule_plan("预算 4000，看看详情", conditions)]
    assert tools == ["search_listings", "get_listing"]


def test_placeholder_resolution_uses_top_cards():
    cards = [{"id": 7}, {"id": 9}, {"id": 11}]
    assert agent_tools.resolve_args({"listing_id": "$top"}, cards) == {"listing_id": 7}
    assert agent_tools.resolve_args({"listing_ids": "$top3"}, cards) == {
        "listing_ids": [7, 9, 11]
    }
    assert agent_tools.resolve_args({"listing_id": "$top"}, []) == {}
