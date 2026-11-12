"""Transparent risk score: every point has a written reason."""
from __future__ import annotations
import pandas as pd
from contracts.models import AssetMeta, RiskLevel, ScoreComponent
from detection.config import CRITICALITY_POINTS, DetectionConfig
from detection.rules import SensorJudgement


def score_flag(meta: AssetMeta, now: pd.Timestamp, evidence: list[SensorJudgement], cfg: DetectionConfig):
    comps: list[ScoreComponent] = []
    breached = [j for j in evidence if j.breached]
    trending = [j for j in evidence if j.trend]
    if trending:
        j = trending[0]
        comps.append(ScoreComponent(factor="trend", points=cfg.pts_trend,
                                    reason=f"{j.sensor.value} trending {j.f.slope_per_day:+.3g} per day"))
    if breached:
        comps.append(ScoreComponent(factor="threshold_breach", points=cfg.pts_breach,
                                    reason=f"{breached[0].sensor.value} beyond alarm level for {cfg.persist_hours} h"))
    elif any(j.warn_exceeded for j in evidence):
        comps.append(ScoreComponent(factor="warn_level", points=cfg.pts_warn,
                                    reason="24h mean beyond the warning level (alarm not yet reached)"))
    cp = CRITICALITY_POINTS.get(meta.criticality, 0)
    if cp:
        comps.append(ScoreComponent(factor="criticality", points=cp, reason=f"asset criticality {meta.criticality} of 3"))
    days = (now.date() - meta.last_service_date).days
    if days > cfg.service_interval_days:
        comps.append(ScoreComponent(factor="service_overdue", points=cfg.pts_overdue,
                                    reason=f"{days} days since last service (interval {cfg.service_interval_days})"))
    if len(evidence) >= 2:
        comps.append(ScoreComponent(factor="multi_signal", points=cfg.pts_multi,
                                    reason=f"{len(evidence)} sensors abnormal together"))
    total = sum(c.points for c in comps)
    level = RiskLevel.HIGH if total >= cfg.high_min else RiskLevel.MEDIUM if total >= cfg.medium_min else RiskLevel.LOW
    return total, comps, level
