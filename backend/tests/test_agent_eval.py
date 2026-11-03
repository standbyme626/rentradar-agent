from app.services import agent_eval_service


def test_golden_dataset_has_enough_cases():
    dataset = agent_eval_service.load_dataset()
    cases = dataset["cases"]
    assert len(cases) >= 50
    ids = [case["id"] for case in cases]
    assert len(ids) == len(set(ids))
    assert sum(1 for case in cases if case["kind"] == "guardrail") >= 10


def test_rule_baseline_passes_and_reports_metrics():
    result = agent_eval_service.evaluate()
    metrics = result["metrics"]
    assert result["total"] == len(agent_eval_service.load_dataset()["cases"])
    assert metrics["intent_field_accuracy"] == 1.0
    assert metrics["tool_accuracy"] == 1.0
    assert metrics["schema_valid_rate"] == 1.0
    assert metrics["grounding_rate"] == 1.0
    assert metrics["guardrail_accuracy"] == 1.0
    assert result["passed"] == result["total"]


def test_broken_case_is_reported_not_fatal(monkeypatch):
    real_run = agent_eval_service.run_case

    def fake_run(case):
        if case["id"] == "q01":
            raise RuntimeError("boom")
        return real_run(case)

    monkeypatch.setattr(agent_eval_service, "run_case", fake_run)
    result = agent_eval_service.evaluate()
    broken = next(item for item in result["cases"] if item["id"] == "q01")
    assert broken["passed"] is False
    assert "boom" in broken["details"]["error"]
    assert result["passed"] < result["total"]


def test_grounded_answer_uses_real_card_values():
    ok, answer = agent_eval_service._grounded_answer()
    assert ok
    assert "¥4000" in answer
    assert "80 分" in answer
