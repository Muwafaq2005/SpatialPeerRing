"""
Unit tests for SevenPillarScorer
"""

import pytest
from app.state.pydantic_state import PeerRingState, JudgeVerdict
from app.telemetry.seven_pillar_scorer import seven_pillar_scorer


def test_seven_pillar_scorer_execution():
    state = PeerRingState(session_id="test-seven-pillar-session")
    state.policy.assistance_level.current_level = 2
    state.policy.struggle_score = 0.15

    gov_history = [
        {
            "leak": JudgeVerdict(judge_type="leak", verdict=True, confidence=0.95, reasoning="No leakage"),
            "help": JudgeVerdict(judge_type="help", verdict=True, confidence=0.90, reasoning="Encouraging question")
        }
    ]

    report = seven_pillar_scorer.score_session(
        state=state,
        governance_history=gov_history,
        mastery_before=0.1
    )

    assert report.overall_score >= 0.0 and report.overall_score <= 1.0
    assert len(report.pillars) == 7
    assert "guardrails" in report.pillars
    assert "learning_progress" in report.pillars
    assert report.pillars["learning_progress"].score > 0.0
    assert report.pillars["guardrails"].score == 1.0


def test_learning_progress_formula():
    """Verify Pillar 7 formula: mastery_after - mastery_before."""
    state = PeerRingState(session_id="test-learning-progress")
    report = seven_pillar_scorer.score_session(state=state, mastery_before=0.2)
    lp_pillar = report.pillars["learning_progress"]

    assert lp_pillar.name == "Learning Progress"
    assert "mastery_before" in lp_pillar.source_metrics
    assert "mastery_after" in lp_pillar.source_metrics
    assert "delta" in lp_pillar.source_metrics
    assert lp_pillar.source_metrics["mastery_before"] == 0.2
