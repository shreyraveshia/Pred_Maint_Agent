"""Every tunable number of the detector, in one place. Tune on DEV data only."""
from dataclasses import dataclass


@dataclass(frozen=True)
class DetectionConfig:
    # --- statistics windows ---
    baseline_days: int = 5          # first N days define each machine's own "normal"
    window_hours: int = 24          # rolling mean window
    slope_hours: int = 72           # trend slope window
    # --- trend rule (all three must hold) ---
    z_min: float = 3.0              # |z| of the 24h mean vs baseline
    slope_min_sd_per_day: float = 0.75   # slope in baseline-std-devs per day, in the BAD direction
    step_min_sd: float = 0.75       # each daily-block change must be >= this many baseline sds
    steady_blocks: int = 4          # 4 daily blocks = 3 consecutive increases (a one-off step gives at most 2)
    trend_grace_hours: int = 24     # WATCH is held this long after the last trend (stops flicker), then needs warn-level
    # --- confirmed (alarm) rule ---
    persist_hours: int = 6          # last N hourly readings must all be beyond alarm
    persist_min_points: int = 5     # ...and at least this many readings must exist
    # --- data quality / hysteresis ---
    min_coverage: float = 0.70      # need >=70% of expected readings in the last 24h
    exit_z: float = 2.0             # sensors with |z| above this count as 'elevated' evidence
    min_sd: float = 1e-3
    # --- risk score points (transparent) ---
    pts_trend: int = 2
    pts_breach: int = 3
    pts_warn: int = 1
    pts_multi: int = 1
    pts_overdue: int = 1
    service_interval_days: int = 180
    high_min: int = 6
    medium_min: int = 3


CRITICALITY_POINTS = {1: 0, 2: 1, 3: 2}
