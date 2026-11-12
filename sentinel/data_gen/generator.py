"""Synthetic sensor generator: baseline + daily cycle + AR(1) noise + planted faults + decoys.
Deterministic: same seed -> byte-identical data. Each asset has its own RNG stream, so adding or
removing an asset never changes the others."""
from __future__ import annotations
import zlib
from datetime import timedelta
import numpy as np
import pandas as pd
from contracts.models import (AssetLabel, AssetMeta, SensorType as S, ThresholdSpec)
from data_gen import config as C


def _rng(seed: int, asset_id: str) -> np.random.Generator:
    return np.random.default_rng([seed, zlib.crc32(asset_id.encode())])   # crc32 is stable; hash() is not


def _ar1(rng, n: int, sd: float, phi: float = 0.5) -> np.ndarray:
    """Slightly auto-correlated noise (real sensors do not jump independently each hour)."""
    e = rng.normal(0, sd * np.sqrt(1 - phi ** 2), n)
    x = np.empty(n); x[0] = rng.normal(0, sd)
    for i in range(1, n):
        x[i] = phi * x[i - 1] + e[i]
    return x


def _clean(nominal: dict, spec: C.AssetSpec, sensor: S, t_days: np.ndarray) -> np.ndarray:
    """Noise-free curve: nominal level + planted fault ramp. Used for data AND for label timing."""
    y = np.full_like(t_days, nominal[sensor], dtype=float)
    f = spec.fault
    if f and sensor in f.effects:
        mag = f.effects[sensor] * (nominal[sensor] if sensor == S.CURRENT else 1.0)
        p = np.clip((t_days - f.onset_day) / f.ramp_days, 0, 1)
        y = y + mag * p ** C.RAMP_EXPONENT
    return y


def _cross_time(meta, spec, sensor, level):
    t = np.arange(C.PROJECTION_DAYS * 24) / 24
    y = _clean(meta.nominal, spec, sensor, t)
    hit = np.where(y >= level)[0] if meta.thresholds[sensor].direction == "high" else np.where(y <= level)[0]
    return C.START + timedelta(hours=int(hit[0])) if len(hit) else None


def _hi(day: float, hour: float = 0) -> int:
    return int(day * 24 + hour)


def _ts(i: int):
    return (C.START + timedelta(hours=i)).isoformat()


def _apply_decoy(spec, series: dict):
    """Harmless events the detector must NOT flag. Returns (events, gaps)."""
    events, gaps = [], []
    k = spec.decoy
    if k == "startup_spike":          # 2-hour jumps on start-up; vibration briefly exceeds WARN
        for day in (5, 13, 21):
            i = _hi(day, 6)
            for j, (dv, dt) in enumerate([(3.0, 4.0), (1.5, 2.0)]):
                series[S.VIBRATION][i + j] += dv; series[S.TEMPERATURE][i + j] += dt
            events.append({"start": _ts(i), "end": _ts(i + 2), "sensors": ["vibration_mm_s", "temperature_c"],
                           "description": "start-up spike, back to normal within 2 hours"})
    elif k == "sensor_glitch":        # single-sample garbage readings (even beyond ALARM)
        i = _hi(12, 14); series[S.VIBRATION][i] = 14.0
        events.append({"start": _ts(i), "end": _ts(i + 1), "sensors": ["vibration_mm_s"],
                       "description": "single-sample vibration glitch (14.0)"})
        i = _hi(20, 3); series[S.PRESSURE][i] = 0.0
        events.append({"start": _ts(i), "end": _ts(i + 1), "sensors": ["pressure_bar"],
                       "description": "single-sample pressure dropout (0.0)"})
    elif k == "load_change":          # stable step after a production change
        i0 = _hi(15, 12)
        for i in range(i0, C.N):
            w = min(1.0, (i - i0) / 2)
            series[S.CURRENT][i] *= 1 + 0.12 * w; series[S.TEMPERATURE][i] += 4.0 * w
        events.append({"start": _ts(i0), "end": _ts(C.N - 1), "sensors": ["current_a", "temperature_c"],
                       "description": "production load change: current +12%, temp +4C, then stable"})
    elif k == "spike_and_gap":        # 2-hour temperature spike above WARN + 6-hour data outage
        i = _hi(18, 10)
        series[S.TEMPERATURE][i] += 13.0; series[S.TEMPERATURE][i + 1] += 8.0
        events.append({"start": _ts(i), "end": _ts(i + 2), "sensors": ["temperature_c"],
                       "description": "2-hour temperature spike, then normal"})
        g0 = _hi(9, 0)
        gaps.append({"start": _ts(g0), "end": _ts(g0 + 6), "sensors": "all", "description": "6-hour data outage",
                     "_idx": (g0, g0 + 6)})
    return events, gaps


def generate_asset(spec: C.AssetSpec, seed: int):
    rng = _rng(seed, spec.asset_id)
    sensors = C.SENSORS_BY_TYPE[spec.asset_type]
    nominal = {s: C.BASELINES[spec.asset_type][s] * rng.uniform(0.97, 1.03) for s in sensors}
    phase = rng.uniform(0, 2 * np.pi)
    thr = {}
    for s in sensors:
        if s == S.CURRENT:
            thr[s] = ThresholdSpec(warn=round(nominal[s] * 1.15, 2), alarm=round(nominal[s] * 1.25, 2))
        else:
            w, a, d = C.THRESHOLDS[s]; thr[s] = ThresholdSpec(warn=w, alarm=a, direction=d)
    meta = AssetMeta(
        asset_id=spec.asset_id, name=spec.name, asset_type=spec.asset_type, location=spec.location,
        criticality=spec.criticality,
        installed_date=(C.START - timedelta(days=int(spec.installed_years_ago * 365))).date(),
        last_service_date=(C.START - timedelta(days=spec.service_days_ago)).date(),
        nominal={s: round(v, 3) for s, v in nominal.items()}, thresholds=thr)

    t_days = np.arange(C.N) / 24
    series = {}
    for s in sensors:
        scale = nominal[s] if s == S.CURRENT else 1.0
        series[s] = (_clean(nominal, spec, s, t_days)
                     + C.CYCLE_AMP[s] * scale * np.sin(2 * np.pi * t_days + phase)
                     + _ar1(rng, C.N, C.NOISE_SD[s] * scale))
    series[S.VIBRATION] = np.maximum(series[S.VIBRATION], 0.05)
    events, gaps = _apply_decoy(spec, series)

    keep = np.ones(C.N, dtype=bool)
    for g in gaps:
        keep[g["_idx"][0]:g["_idx"][1]] = False
    ts = pd.date_range(C.START, periods=C.N, freq="h")
    df = pd.concat([pd.DataFrame({"asset_id": spec.asset_id, "timestamp": ts[keep],
                                  "sensor": s.value, "value": series[s][keep]}) for s in sensors],
                   ignore_index=True)
    for g in gaps: g.pop("_idx")

    # ---- ground-truth label ----
    split = "test" if spec.asset_id in C.TEST_ASSETS else "dev"
    if spec.fault:
        f = spec.fault
        th = meta.thresholds[f.primary]
        alarm_t = _cross_time(meta, spec, f.primary, th.alarm)
        in_window = alarm_t is not None and alarm_t < C.START + timedelta(days=C.DAYS)
        label = AssetLabel(
            asset_id=spec.asset_id, category="fault", fault_type=f.type, primary_sensor=f.primary,
            affected_sensors=list(f.effects.keys()), onset_time=C.START + timedelta(days=f.onset_day),
            warn_cross_time=_cross_time(meta, spec, f.primary, th.warn), alarm_cross_time=alarm_t,
            alarm_crossed_in_window=in_window,
            expected_state_at_end="active_fault" if in_window else "watch",
            multi_signal=f.multi_signal, has_manual_coverage=f.has_manual_coverage, split=split)
    else:
        label = AssetLabel(asset_id=spec.asset_id, category="decoy" if spec.decoy else "healthy",
                           decoy_type=spec.decoy, expected_state_at_end="normal",
                           decoy_events=events, data_gaps=gaps, split=split)
    return meta, df, label


def generate_fleet(seed: int = C.SEED, only: list[str] | None = None):
    metas, frames, labels = [], [], []
    for spec in C.ASSETS:
        if only and spec.asset_id not in only:
            continue
        m, d, l = generate_asset(spec, seed)
        metas.append(m); frames.append(d); labels.append(l)
    return metas, pd.concat(frames, ignore_index=True), labels
