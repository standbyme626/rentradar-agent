from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.services import reputation_service


def _mention(
    *,
    severity="medium",
    confidence=0.8,
    source="douban",
    issue="noise",
    status="verified",
    age_days=10,
    expires_days=200,
):
    now = datetime.now(UTC)
    return SimpleNamespace(
        match_status=status,
        severity=severity,
        confidence=confidence,
        source=source,
        issue_type=issue,
        published_at=now - timedelta(days=age_days),
        created_at=now - timedelta(days=age_days),
        expires_at=now + timedelta(days=expires_days),
    )


def test_no_verified_mentions_keeps_neutral_and_says_insufficient():
    summary = reputation_service.summarize_mentions(
        [_mention(status="uncertain", confidence=0.9)]
    )
    assert summary["status"] == "insufficient"
    assert summary["count"] == 0
    assert summary["uncertain"] == 1
    assert summary["score"] == 0.5
    assert "数据不足" in summary["label"]


def test_more_severe_evidence_lowers_score():
    one = reputation_service.summarize_mentions([_mention(severity="medium")])
    many = reputation_service.summarize_mentions(
        [
            _mention(severity="high", source="12345"),
            _mention(severity="high", source="douban"),
            _mention(severity="high", source="xiaohongshu"),
        ]
    )
    assert one["status"] in {"low", "watch"}
    assert many["score"] < one["score"]
    assert many["risk"] == "high"
    assert many["count"] == 3
    assert len(many["sources"]) == 3
    assert many["top_issue"] == "noise"


def test_expired_and_rejected_mentions_do_not_count():
    summary = reputation_service.summarize_mentions(
        [
            _mention(expires_days=-1),
            _mention(status="rejected"),
        ]
    )
    assert summary["count"] == 0
    assert summary["status"] == "insufficient"


def test_old_evidence_decays():
    recent = reputation_service.decay_weight(_mention(age_days=0))
    old = reputation_service.decay_weight(_mention(age_days=360))
    assert recent > old * 3


def test_summarize_for_score_shapes_reason():
    score, reason, status = reputation_service.summarize_for_score(
        {
            "status": "high",
            "score": 0.3,
            "label": "口碑风险高",
            "count": 2,
            "sources": ["douban", "12345"],
        }
    )
    assert score == 0.3
    assert status == "high"
    assert "2 条证据" in reason
    assert "douban" in reason
    neutral, neutral_reason, neutral_status = reputation_service.summarize_for_score(None)
    assert neutral == 0.5
    assert neutral_status == "insufficient"
    assert "数据不足" in neutral_reason
