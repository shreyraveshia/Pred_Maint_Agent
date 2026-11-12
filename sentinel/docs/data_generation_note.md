# Data Generation Note (deliverable)

**What:** 18 fictional assets (7 pumps, 6 motors, 5 compressors), 30 days, hourly readings of vibration (mm/s),
temperature (C), pressure (bar; pumps and compressors only) and current (A). 47,496 rows, long format
(`asset_id, timestamp, sensor, value`) matching `SensorReading` in `contracts/models.py`.

**How each signal is built:** `nominal level (per-asset +/-3%) + daily sine cycle + AR(1) noise (phi=0.5)`.

**Planted faults (8):** a smooth ramp `magnitude * progress^1.4` starting at an onset day. Types: bearing wear (3),
overheating (2), pressure drift (2), current anomaly (1). 4 cross the ALARM level inside the window (active/confirmed);
3-4 are still below alarm at day 30 (early warning/predicted). Crossing times are computed from the noise-free curve,
even when they fall after day 30 (projection), so lead time can be measured.

**Decoys (4 assets):** start-up spikes (raw values exceed WARN briefly), single-sample sensor glitches (one value
beyond ALARM), a stable load change (+12% current), a 2-hour temperature spike plus a 6-hour data outage.
Healthy assets (6) contain only noise and the daily cycle.

**Threshold convention:** `warn` = attention level; `alarm` = confirmed-fault level. `SignalEvidence.threshold_breached`
means ALARM crossed (persistently, not by a single glitch). Current thresholds are 1.15x / 1.25x each asset's nominal.
All thresholds are illustrative assumptions, not real standards.

**Reproducibility:** `python -m data_gen.generate --seed 42` regenerates identical data (checked by tests and by the
fingerprint in `data/manifest.json`). Each asset has its own RNG stream.

**Splits:** 4 of 18 assets (22%) are held out in `data/heldout/`: P-103 (early warning), C-302 (active, multi-signal),
M-205 (load-change decoy), C-305 (healthy). Nobody tunes on these until Phase 10.

**Known limitation:** with 18 assets the held-out set has only 2 faulty assets, so precision/recall there is coarse.
Mitigation for the evaluation report: also run the frozen system on freshly generated fleets with other seeds, and
state clearly that these are synthetic, not real-plant, results.
