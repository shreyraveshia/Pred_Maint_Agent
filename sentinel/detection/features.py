"""Pure statistics. No decisions here: just numbers computed from data up to `now`."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd
from detection.config import DetectionConfig

_H = pd.Timedelta(hours=1)


@dataclass(frozen=True)
class SensorFeatures:
    latest: float
    mean24: float
    z: float                  # signed: positive = above this machine's own baseline
    slope_per_day: float      # signed, units per day, from a straight-line fit over 72 h
    base_mu: float
    base_sd: float
    coverage: float           # share of expected readings present in the last 24 h
    block_means: tuple        # 24h means: newest first: last 24h, the 24h before, ...
    recent: tuple             # the last `persist_hours` hourly readings
    window_start: pd.Timestamp
    window_end: pd.Timestamp


def _slice(s: pd.Series, lo_excl: pd.Timestamp, hi_incl: pd.Timestamp) -> pd.Series:
    i = s.index.searchsorted(lo_excl, side="right")
    j = s.index.searchsorted(hi_incl, side="right")
    return s.iloc[i:j]


def _mean(s: pd.Series) -> float:
    return float(s.mean()) if len(s) else float("nan")


def compute_features(s: pd.Series, now: pd.Timestamp, cfg: DetectionConfig) -> SensorFeatures | None:
    """Returns None while the machine is still 'learning' (baseline + 72 h not yet available) or has no data."""
    if s.empty:
        return None
    start = s.index[0]
    base_end = start + pd.Timedelta(days=cfg.baseline_days)
    if now < base_end + cfg.slope_hours * _H:
        return None
    base = s.iloc[: s.index.searchsorted(base_end, side="left")]
    mu = float(base.mean())
    sd = max(float(base.std(ddof=1)), cfg.min_sd)

    w24 = _slice(s, now - cfg.window_hours * _H, now)
    if w24.empty:
        return None
    w72 = _slice(s, now - cfg.slope_hours * _H, now)
    slope = 0.0
    if len(w72) >= 12:
        x = (w72.index - w72.index[0]).total_seconds().to_numpy() / 86400.0
        slope = float(np.polyfit(x, w72.to_numpy(), 1)[0])
    blocks = tuple(_mean(_slice(s, now - (k + 1) * 24 * _H, now - k * 24 * _H)) for k in range(cfg.steady_blocks))
    recent = tuple(float(v) for v in _slice(s, now - cfg.persist_hours * _H, now).to_numpy())
    return SensorFeatures(latest=float(w24.iloc[-1]), mean24=float(w24.mean()), z=(float(w24.mean()) - mu) / sd,
                          slope_per_day=slope, base_mu=mu, base_sd=sd, coverage=len(w24) / cfg.window_hours,
                          block_means=blocks, recent=recent,
                          window_start=now - cfg.window_hours * _H, window_end=now)
