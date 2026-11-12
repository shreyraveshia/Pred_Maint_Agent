# Fault Catalogue (generator + detector must both follow this)
Sampling: 1 reading/hour/sensor, 30 days. Thresholds below are ILLUSTRATIVE (documented assumption, not real standards).

| Fault | Asset types | Signature | Warn / Alarm threshold | Duration of ramp |
|---|---|---|---|---|
| Bearing wear | pump, motor | vibration ramps ~2.0 -> 7+ mm/s; temperature +3..5 C | vib 4.5 / 7.1 mm/s | 12-18 days |
| Overheating (blocked cooler) | compressor, motor | temperature ramps ~65 -> 95 C; current +5..10% | temp 80 / 90 C | 8-14 days |
| Pressure drift (seal leak) | pump, compressor | pressure drifts ~6.0 -> 4.2 bar | 5.0 / 4.5 bar (low side) | 10-16 days |
| (optional) Current anomaly | motor | current creeps +20% at constant load | 1.15x / 1.25x baseline | 8-12 days |

## Decoys (must NOT be flagged)
- Start-up spike: 1-3 hour jump, then back to baseline.
- Load change: step change in current/temp that is stable afterward and explained by load.
- Single-sample sensor glitch: one outlier value.

## Ground-truth labels (labels.json) per asset
asset_id, fault_type or null, is_decoy, onset_time, warn_cross_time, alarm_cross_time, split ("dev"|"test")

## Coverage gap on purpose
One fault type (e.g. current anomaly) has NO manual page, so we can test the "no evidence" path.
