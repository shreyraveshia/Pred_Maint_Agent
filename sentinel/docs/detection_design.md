# Detection Engine Design (Phase 3) - no LLM anywhere in this module

Pipeline per machine, per tick ("now"): features -> per-sensor judgement -> asset state machine -> risk score -> Flag.
Code: `detection/features.py`, `rules.py`, `risk.py`, `engine.py`, `config.py` (all tunables), `run.py` (CLI).

## Per-sensor rules
| Rule | Definition | Why |
|---|---|---|
| Baseline | mean/std of the machine's first 5 days | each machine judged against itself |
| z-score | (24h mean - baseline mean) / baseline std | "is it unusual?" |
| Slope | straight-line fit over 72 h, units per day | "is it heading somewhere?" |
| TREND | z >= 3 in the bad direction AND slope >= 0.75 sd/day AND 3 consecutive daily-block increases each >= 0.75 sd | rejects spikes, glitches and steps |
| BREACHED (confirmed) | last 6 hourly readings (>=5 present) all beyond ALARM; sticky while 24h mean stays beyond alarm | one reading can never confirm a fault; no flicker |
| Bad direction | high for vibration/temperature/current, low for pressure | from `ThresholdSpec.direction` |

## Asset state machine
- ACTIVE_FAULT (confirmed) = any sensor BREACHED.
- WATCH (predicted) = any sensor TREND, or held after a problem: for 24 h after the last trend, or while a 24h mean is beyond WARN.
- RESOLVED -> NORMAL = no trend, below warn, grace period over.
- Insufficient data (<70% of last 24h) = state is held, note `insufficient_data_or_learning`.
- Flag validators in `contracts/` guarantee WATCH never contains a breach and ACTIVE_FAULT always does.

## Risk score (points; every point has a written reason in `score_breakdown`)
trend +2 | alarm breach +3 (or warn exceeded +1) | criticality 3:+2, 2:+1, 1:0 | service overdue (>180 d) +1 | 2+ abnormal sensors +1.
Bands: High >= 6, Medium 3-5, Low <= 2. Also `days_to_alarm` for WATCH signals = (alarm - 24h mean) / slope.

## Decisions worth knowing / known limitations
1. Baseline assumes the first 5 days are healthy (true for all assets here; a real system would re-learn baselines).
2. A one-off level shift ABOVE warn but with no trend is not flagged from NORMAL (only trends start a Watch). Possible extension.
3. Stricter steadiness (3 increases) cost 0.2-1.0 day of lead time versus the first version; accepted to reject steps.
4. Tuned on the 14 dev assets only. The dev set has no load-change decoy (it exists only in the sealed set), so that
   behaviour is verified by hand-built tests (`tests/test_detection.py`), not by looking at held-out data.
5. Ticks are every 6 simulated hours; evaluation (Phase 10) measures lead time against `labels.json`.
