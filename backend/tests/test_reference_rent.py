from types import SimpleNamespace

from app.services.reference_rent_service import normalize_layout, pick_latest


def ref(month: str, confidence: float):
    return SimpleNamespace(reference_month=month, confidence=confidence)


def test_normalize_layout():
    assert normalize_layout("2室1厅") == "2室"
    assert normalize_layout("整租·3室2厅") == "3室"
    assert normalize_layout("开间") == "开间"
    assert normalize_layout(None) == ""


def test_pick_latest_prefers_month_then_confidence():
    rows = [ref("2026-09", 0.9), ref("2026-10", 0.6), ref("2026-10", 0.8)]
    assert pick_latest(rows).confidence == 0.8
    assert pick_latest([]) is None
