"""
SENTINEL CONTRACTS  -- the single source of truth for data shapes.

Rule: changing this file needs ALL five teammates to agree.
Every module (generator, detector, RAG, MCP, dashboard) imports from here.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------- Enums ----------
class SensorType(str, Enum):
    VIBRATION = "vibration_mm_s"
    TEMPERATURE = "temperature_c"
    PRESSURE = "pressure_bar"
    CURRENT = "current_a"


class AssetState(str, Enum):
    NORMAL = "normal"
    WATCH = "watch"                 # PREDICTED risk: trend, no threshold breach
    ACTIVE_FAULT = "active_fault"   # CONFIRMED: a threshold is breached now
    RESOLVED = "resolved"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ---------- Sensor data ----------
class SensorReading(BaseModel):
    asset_id: str
    timestamp: datetime
    sensor: SensorType
    value: float


# ---------- Detection output ----------
class SignalEvidence(BaseModel):
    """Math evidence for ONE sensor on ONE asset. Produced by code, never by an LLM."""
    sensor: SensorType
    window_start: datetime
    window_end: datetime
    latest_value: float
    rolling_mean: float
    z_score: float
    slope_per_day: float
    threshold: float
    threshold_breached: bool
    days_to_alarm: float | None = None   # estimate for WATCH signals: days until alarm at current slope


class ScoreComponent(BaseModel):
    factor: str          # e.g. "threshold_breach"
    points: int
    reason: str          # human-readable, shown in the dashboard


class Flag(BaseModel):
    flag_id: str = Field(default_factory=lambda: f"FLG-{uuid4().hex[:8]}")
    asset_id: str
    created_at: datetime = Field(default_factory=_now)
    state: AssetState
    risk: RiskLevel
    risk_score: int
    score_breakdown: list[ScoreComponent]
    signals: list[SignalEvidence]

    @property
    def is_multi_signal(self) -> bool:
        return len(self.signals) >= 2

    @model_validator(mode="after")
    def _enforce_confirmed_vs_predicted(self) -> "Flag":
        breached = any(s.threshold_breached for s in self.signals)
        if self.state in (AssetState.WATCH, AssetState.ACTIVE_FAULT) and not self.signals:
            raise ValueError("A flag in WATCH/ACTIVE_FAULT must carry evidence signals")
        if self.state == AssetState.ACTIVE_FAULT and not breached:
            raise ValueError("ACTIVE_FAULT (confirmed) requires a breached threshold")
        if self.state == AssetState.WATCH and breached:
            raise ValueError("WATCH (predicted) cannot contain a breached threshold")
        if self.risk_score != sum(c.points for c in self.score_breakdown):
            raise ValueError("risk_score must equal the sum of score_breakdown points")
        return self


# ---------- RAG output ----------
class Citation(BaseModel):
    source_id: str       # e.g. "MAN-PUMP-4.2" or "WO-2031"
    section: str | None = None


class Explanation(BaseModel):
    flag_id: str
    status: Literal["explained", "no_evidence"]
    failure_mode: str | None = None
    summary: str
    confidence: Confidence
    citations: list[Citation] = Field(default_factory=list)

    @model_validator(mode="after")
    def _no_claims_without_evidence(self) -> "Explanation":
        if self.status == "explained" and not self.citations:
            raise ValueError("An 'explained' result must cite at least one source")
        if self.status == "no_evidence":
            if self.failure_mode or self.citations:
                raise ValueError("'no_evidence' must not state a failure mode or citations")
            if self.confidence != Confidence.LOW:
                raise ValueError("'no_evidence' must have LOW confidence")
        return self


# ---------- Work order ----------
class PartLine(BaseModel):
    part_id: str
    quantity: int = Field(ge=1)


class WorkOrderDraft(BaseModel):
    flag_id: str
    asset_id: str
    title: str
    fault_kind: Literal["predicted_risk", "confirmed_fault"]
    problem_description: str
    suggested_steps: list[str]
    parts: list[PartLine] = Field(default_factory=list)
    priority: Literal["P1", "P2", "P3", "P4"]
    cited_sources: list[str] = Field(default_factory=list)
    # The agent can ONLY ever create drafts. Enforced here AND in the MCP server.
    status: Literal["draft"] = "draft"


# ---------- Governance ----------
class AuditEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: f"AUD-{uuid4().hex[:10]}")
    timestamp: datetime = Field(default_factory=_now)
    actor: str                                   # "sentinel-agent" or a human username
    actor_type: Literal["agent", "human", "system"]
    action: str                                  # e.g. "tool_call", "model_call", "approve"
    target_type: str                             # "flag", "work_order", ...
    target_id: str
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class CostLogEntry(BaseModel):
    flag_id: str
    timestamp: datetime = Field(default_factory=_now)
    model: str
    route_reason: str    # "low_risk_single_signal", "high_risk", "multi_signal", "fallback"
    input_tokens: int
    output_tokens: int
    est_cost_usd: float
    latency_ms: int | None = None


# ---------- Asset metadata & ground-truth labels (added in Phase 2) ----------
class ThresholdSpec(BaseModel):
    """warn = early-attention level. alarm = CONFIRMED-fault level.
    A signal counts as 'threshold_breached' (see SignalEvidence) only when ALARM is crossed."""
    warn: float
    alarm: float
    direction: Literal["high", "low"] = "high"   # "low" = bad when value falls BELOW the level


class AssetMeta(BaseModel):
    asset_id: str
    name: str
    asset_type: Literal["pump", "motor", "compressor"]
    location: str
    criticality: int = Field(ge=1, le=3)         # 3 = most critical
    installed_date: date
    last_service_date: date
    nominal: dict[SensorType, float]             # healthy average per sensor
    thresholds: dict[SensorType, ThresholdSpec]


class AssetLabel(BaseModel):
    """Answer key used ONLY by evaluation and tests, never by the detector."""
    asset_id: str
    category: Literal["fault", "decoy", "healthy"]
    fault_type: Literal["bearing_wear", "overheating", "pressure_drift", "current_anomaly"] | None = None
    decoy_type: str | None = None
    primary_sensor: SensorType | None = None
    affected_sensors: list[SensorType] = Field(default_factory=list)
    onset_time: datetime | None = None
    warn_cross_time: datetime | None = None       # projected from the noise-free curve
    alarm_cross_time: datetime | None = None      # projected; may fall AFTER the 30-day window
    alarm_crossed_in_window: bool = False
    expected_state_at_end: Literal["normal", "watch", "active_fault"]
    multi_signal: bool = False                    # >=2 sensors clearly show the fault
    has_manual_coverage: bool = True              # False -> system should answer "no evidence"
    decoy_events: list[dict[str, Any]] = Field(default_factory=list)
    data_gaps: list[dict[str, Any]] = Field(default_factory=list)
    split: Literal["dev", "test"]
