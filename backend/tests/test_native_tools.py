import pytest

from app.services import agent_tools


def test_native_schemas_exclude_write_tool_and_allow_placeholders():
    schemas = agent_tools.native_tool_schemas()
    names = {item["function"]["name"] for item in schemas}
    assert names == set(agent_tools.planner_tools())
    assert "save_monitor" not in names
    get_listing = next(
        item for item in schemas if item["function"]["name"] == "get_listing"
    )
    prop = get_listing["function"]["parameters"]["properties"]["listing_id"]
    assert "anyOf" in prop
    assert "$top" in prop["anyOf"][1]["enum"]


def test_normalize_native_calls_builds_plan_and_resolves_placeholders():
    steps = agent_tools.normalize_native_calls(
        [
            {
                "name": "search_listings",
                "arguments": {"budget": 4000, "layout": "2室"},
            },
            {"name": "get_listing", "arguments": {"listing_id": "$top"}},
        ]
    )
    assert steps[0]["tool"] == "search_listings"
    assert steps[1]["args"]["listing_id"] == "$top"


def test_normalize_native_calls_rejects_bad_first_step_or_write_tool():
    with pytest.raises(agent_tools.ToolArgumentError):
        agent_tools.normalize_native_calls(
            [{"name": "get_listing", "arguments": {"listing_id": 1}}]
        )
    with pytest.raises(agent_tools.ToolArgumentError):
        agent_tools.normalize_native_calls(
            [{"name": "save_monitor", "arguments": {"name": "x"}}]
        )
    with pytest.raises(agent_tools.ToolArgumentError):
        agent_tools.normalize_native_calls(
            [{"name": "search_listings", "arguments": None}]
        )
