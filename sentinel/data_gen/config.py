"""All knobs of the synthetic factory live here. Change a number here, regenerate, done."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from contracts.models import SensorType as S

SEED = 42
START = datetime(2026, 10, 1, tzinfo=timezone.utc)
DAYS = 30
N = DAYS * 24                 # hourly readings
PROJECTION_DAYS = 60          # how far we extend the clean curve to project threshold crossings
RAMP_EXPONENT = 1.4           # >1 = degradation accelerates (more realistic than a straight line)

SENSORS_BY_TYPE = {
    "pump":       [S.VIBRATION, S.TEMPERATURE, S.PRESSURE, S.CURRENT],
    "motor":      [S.VIBRATION, S.TEMPERATURE, S.CURRENT],          # motors have no pressure sensor
    "compressor": [S.VIBRATION, S.TEMPERATURE, S.PRESSURE, S.CURRENT],
}
BASELINES = {   # healthy average values (units: mm/s, C, bar, A)
    "pump":       {S.VIBRATION: 2.0, S.TEMPERATURE: 55.0, S.PRESSURE: 6.0, S.CURRENT: 12.0},
    "motor":      {S.VIBRATION: 1.8, S.TEMPERATURE: 62.0, S.CURRENT: 25.0},
    "compressor": {S.VIBRATION: 2.6, S.TEMPERATURE: 70.0, S.PRESSURE: 6.5, S.CURRENT: 40.0},
}
# Noise std-dev and daily-cycle amplitude. For CURRENT these are FRACTIONS of nominal.
NOISE_SD  = {S.VIBRATION: 0.12, S.TEMPERATURE: 0.6, S.PRESSURE: 0.05, S.CURRENT: 0.012}
CYCLE_AMP = {S.VIBRATION: 0.08, S.TEMPERATURE: 1.5, S.PRESSURE: 0.04, S.CURRENT: 0.02}
# (warn, alarm, direction). CURRENT uses 1.15x / 1.25x of each asset's nominal (see generator).
THRESHOLDS = {S.VIBRATION: (4.5, 7.1, "high"), S.TEMPERATURE: (80.0, 90.0, "high"),
              S.PRESSURE: (5.0, 4.5, "low")}


@dataclass
class Fault:
    type: str                         # bearing_wear | overheating | pressure_drift | current_anomaly
    primary: S                        # the sensor the label/thresholds are judged on
    onset_day: float
    ramp_days: float
    effects: dict                     # sensor -> total change at full ramp (CURRENT: fraction of nominal)
    multi_signal: bool = False
    has_manual_coverage: bool = True


@dataclass
class AssetSpec:
    asset_id: str
    asset_type: str
    name: str
    location: str
    criticality: int
    service_days_ago: int
    installed_years_ago: float
    fault: Fault | None = None
    decoy: str | None = None          # startup_spike | sensor_glitch | load_change | spike_and_gap


ASSETS: list[AssetSpec] = [
    # ---------------- Pumps ----------------
    AssetSpec("P-101", "pump", "Feed Pump 101", "Unit A", 3, 120, 6),                                   # healthy
    AssetSpec("P-102", "pump", "Feed Pump 102", "Unit A", 3, 200, 6, fault=Fault(                       # ACTIVE bearing wear
        "bearing_wear", S.VIBRATION, 8, 15, {S.VIBRATION: 5.6, S.TEMPERATURE: 2.0})),
    AssetSpec("P-103", "pump", "Transfer Pump 103", "Unit B", 2, 150, 4, fault=Fault(                   # EARLY WARNING bearing wear
        "bearing_wear", S.VIBRATION, 22, 16, {S.VIBRATION: 5.6, S.TEMPERATURE: 2.0})),
    AssetSpec("P-104", "pump", "Booster Pump 104", "Unit B", 3, 320, 8, fault=Fault(                    # ACTIVE pressure drift (seal), service overdue
        "pressure_drift", S.PRESSURE, 6, 18, {S.PRESSURE: -2.0})),
    AssetSpec("P-105", "pump", "Cooling Pump 105", "Utilities", 1, 60, 3, decoy="startup_spike"),       # decoy
    AssetSpec("P-106", "pump", "Spare Pump 106", "Utilities", 1, 90, 3),                                # healthy
    AssetSpec("P-107", "pump", "Dosing Pump 107", "Unit C", 2, 45, 2, decoy="sensor_glitch"),           # decoy
    # ---------------- Motors ----------------
    AssetSpec("M-201", "motor", "Drive Motor 201", "Unit A", 3, 100, 6),                                # healthy
    AssetSpec("M-202", "motor", "Drive Motor 202", "Unit A", 3, 250, 6, fault=Fault(                    # ACTIVE bearing wear, multi-signal
        "bearing_wear", S.VIBRATION, 10, 14, {S.VIBRATION: 5.8, S.TEMPERATURE: 6.0}, multi_signal=True)),
    AssetSpec("M-203", "motor", "Fan Motor 203", "Unit C", 2, 140, 5, fault=Fault(                      # EARLY WARNING overheating, multi-signal
        "overheating", S.TEMPERATURE, 21, 14, {S.TEMPERATURE: 30.0, S.CURRENT: 0.10}, multi_signal=True)),
    AssetSpec("M-204", "motor", "Mixer Motor 204", "Unit C", 2, 210, 5, fault=Fault(                    # ACTIVE current anomaly: NO MANUAL COVERAGE
        "current_anomaly", S.CURRENT, 10, 10, {S.CURRENT: 0.30, S.TEMPERATURE: 4.0},
        has_manual_coverage=False)),
    AssetSpec("M-205", "motor", "Conveyor Motor 205", "Unit B", 1, 70, 4, decoy="load_change"),         # decoy
    AssetSpec("M-206", "motor", "Spare Motor 206", "Utilities", 1, 30, 2),                              # healthy
    # ---------------- Compressors ----------------
    AssetSpec("C-301", "compressor", "Air Compressor 301", "Utilities", 3, 80, 7),                      # healthy
    AssetSpec("C-302", "compressor", "Air Compressor 302", "Utilities", 3, 230, 7, fault=Fault(         # ACTIVE overheating, multi-signal
        "overheating", S.TEMPERATURE, 12, 12, {S.TEMPERATURE: 28.0, S.CURRENT: 0.10}, multi_signal=True)),
    AssetSpec("C-303", "compressor", "Process Compressor 303", "Unit B", 2, 170, 5, fault=Fault(        # EARLY WARNING pressure drift
        "pressure_drift", S.PRESSURE, 20, 18, {S.PRESSURE: -2.3})),
    AssetSpec("C-304", "compressor", "Process Compressor 304", "Unit C", 2, 50, 3, decoy="spike_and_gap"),  # decoy + data gap
    AssetSpec("C-305", "compressor", "Backup Compressor 305", "Utilities", 1, 40, 2),                   # healthy
]

# Held-out 20% (4 of 18 assets), chosen to cover: early warning, active fault, decoy, healthy.
# DO NOT TUNE ON THESE. Evaluation (Phase 10) only.
TEST_ASSETS = ["P-103", "C-302", "M-205", "C-305"]
TINY_ASSETS = ["P-101", "P-102", "P-105"]     # healthy, active fault, decoy
