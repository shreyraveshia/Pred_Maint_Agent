from datetime import datetime, timezone
import pytest
from pydantic import ValidationError
from contracts.models import *

T = datetime(2026, 1, 10, tzinfo=timezone.utc)


def sig(breached: bool) -> SignalEvidence:
    return SignalEvidence(sensor=SensorType.VIBRATION, window_start=T, window_end=T,
                          latest_value=5.0, rolling_mean=4.0, z_score=3.1,
                          slope_per_day=0.3, threshold=4.5, threshold_breached=breached)


def comps():
    return [ScoreComponent(factor="trend", points=2, reason="rising"),
            ScoreComponent(factor="criticality", points=1, reason="medium")]


def test_watch_without_breach_is_valid():
    f = Flag(asset_id="P-101", state=AssetState.WATCH, risk=RiskLevel.MEDIUM,
             risk_score=3, score_breakdown=comps(), signals=[sig(False)])
    assert not f.is_multi_signal


def test_active_fault_requires_breach():
    with pytest.raises(ValidationError):
        Flag(asset_id="P-101", state=AssetState.ACTIVE_FAULT, risk=RiskLevel.HIGH,
             risk_score=3, score_breakdown=comps(), signals=[sig(False)])


def test_watch_cannot_contain_breach():
    with pytest.raises(ValidationError):
        Flag(asset_id="P-101", state=AssetState.WATCH, risk=RiskLevel.MEDIUM,
             risk_score=3, score_breakdown=comps(), signals=[sig(True)])


def test_score_must_match_breakdown():
    with pytest.raises(ValidationError):
        Flag(asset_id="P-101", state=AssetState.WATCH, risk=RiskLevel.MEDIUM,
             risk_score=99, score_breakdown=comps(), signals=[sig(False)])


def test_explained_needs_citation():
    with pytest.raises(ValidationError):
        Explanation(flag_id="F", status="explained", failure_mode="bearing wear",
                    summary="x", confidence=Confidence.HIGH, citations=[])


def test_no_evidence_cannot_claim_failure_mode():
    with pytest.raises(ValidationError):
        Explanation(flag_id="F", status="no_evidence", failure_mode="bearing wear",
                    summary="x", confidence=Confidence.LOW)


def test_no_evidence_valid():
    e = Explanation(flag_id="F", status="no_evidence",
                    summary="No reliable evidence found.", confidence=Confidence.LOW)
    assert e.citations == []


def test_work_order_status_is_always_draft():
    with pytest.raises(ValidationError):
        WorkOrderDraft(flag_id="F", asset_id="A", title="t", fault_kind="predicted_risk",
                       problem_description="d", suggested_steps=["s"], priority="P2",
                       status="approved")
