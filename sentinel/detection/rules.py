"""Turns numbers into judgements: per sensor (trend? breached?) and per asset (the state machine)."""
from __future__ import annotations
from dataclasses import dataclass
import pandas as pd
from contracts.models import AssetState, SensorType, ThresholdSpec
from detection.config import DetectionConfig
from detection.features import SensorFeatures


@dataclass(frozen=True)
class SensorJudgement:
    sensor: SensorType
    f: SensorFeatures | None
    ok_data: bool
    trend: bool = False
    breached: bool = False
    warn_exceeded: bool = False
    elevated: bool = False
    dz: float = 0.0
    days_to_alarm: float | None = None


def judge_sensor(sensor: SensorType, f: SensorFeatures | None, th: ThresholdSpec,
                 cfg: DetectionConfig, was_breached: bool) -> SensorJudgement:
    if f is None or f.coverage < cfg.min_coverage:
        return SensorJudgement(sensor, f, ok_data=False)
    d = 1.0 if th.direction == "high" else -1.0          # +1: bad when HIGH, -1: bad when LOW
    sd = f.base_sd
    beyond = (lambda v, lim: v >= lim) if d > 0 else (lambda v, lim: v <= lim)

    dz = d * f.z
    bm = f.block_means
    steady = all(d * (bm[i] - bm[i + 1]) >= cfg.step_min_sd * sd for i in range(len(bm) - 1))   # NaN -> False
    trend = dz >= cfg.z_min and d * f.slope_per_day >= cfg.slope_min_sd_per_day * sd and steady

    persistent = len(f.recent) >= cfg.persist_min_points and all(beyond(v, th.alarm) for v in f.recent)
    breached = persistent or (was_breached and beyond(f.mean24, th.alarm))   # hysteresis once confirmed

    days = None
    if trend and not breached and d * f.slope_per_day > 0:
        remaining = (th.alarm - f.mean24) if d > 0 else (f.mean24 - th.alarm)
        days = round(max(remaining, 0.0) / (d * f.slope_per_day), 1)
    return SensorJudgement(sensor, f, True, trend, breached, beyond(f.mean24, th.warn), dz >= cfg.exit_z, dz, days)


def decide_state(js: list[SensorJudgement], prev: AssetState, now, last_trend, cfg: DetectionConfig):
    """The state machine. Returns (new_state, evidence sensors, data_ok, new_last_trend)."""
    ok = [j for j in js if j.ok_data]
    if not ok:
        return prev, [], False, last_trend                       # no usable data: hold the previous state
    trending = any(j.trend for j in ok)
    if trending:
        last_trend = now
    in_grace = last_trend is not None and (now - last_trend) <= pd.Timedelta(hours=cfg.trend_grace_hours)
    held = prev in (AssetState.WATCH, AssetState.ACTIVE_FAULT) and (in_grace or any(j.warn_exceeded for j in ok))
    if any(j.breached for j in ok):
        state = AssetState.ACTIVE_FAULT                          # CONFIRMED
    elif trending or held:
        state = AssetState.WATCH                                 # PREDICTED / still at risk
    elif prev in (AssetState.WATCH, AssetState.ACTIVE_FAULT):
        state = AssetState.RESOLVED                              # back to normal after a problem
    else:
        state = AssetState.NORMAL
    evidence = [j for j in ok if j.breached or j.trend]
    if state == AssetState.WATCH and not evidence:
        evidence = [j for j in ok if j.elevated] or [max(ok, key=lambda j: j.dz)]
    return state, evidence, True, last_trend
