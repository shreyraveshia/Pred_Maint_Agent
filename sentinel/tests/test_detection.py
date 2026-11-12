"""Detector tests: hand-built traps (no generator needed) + dev-set integration. Held-out assets are NEVER used here."""
from datetime import date, datetime, timedelta, timezone
import numpy as np, pandas as pd, pytest
from contracts.models import AssetMeta, AssetState as St, RiskLevel, SensorType as S, ThresholdSpec
from data_gen.generator import generate_fleet
from detection.config import DetectionConfig
from detection.engine import DetectionEngine

START = datetime(2026, 10, 1, tzinfo=timezone.utc)
N = 720


def meta(sensor=S.VIBRATION, nominal=2.0, warn=4.5, alarm=7.1, direction="high", crit=3, service_days_ago=100):
    return AssetMeta(asset_id="T-1", name="Test", asset_type="pump", location="X", criticality=crit,
                     installed_date=date(2020, 1, 1), last_service_date=(START - timedelta(days=service_days_ago)).date(),
                     nominal={sensor: nominal}, thresholds={sensor: ThresholdSpec(warn=warn, alarm=alarm, direction=direction)})


def healthy(nominal=2.0, sd=0.13, seed=1):
    rng = np.random.default_rng(seed)
    t = np.arange(N) / 24
    return nominal + 0.08 * np.sin(2 * np.pi * t) + rng.normal(0, sd, N)


def run(values, m=None, sensor=S.VIBRATION, drop=None):
    m = m or meta(sensor=sensor)
    ts = pd.date_range(START, periods=N, freq="h")
    df = pd.DataFrame({"asset_id": "T-1", "timestamp": ts, "sensor": sensor.value, "value": values})
    if drop is not None:
        df = df.drop(df.index[drop])
    return DetectionEngine(df, [m]).replay(step_hours=6), m


def states(evs):
    return [e.state for e in evs]


def ramp(total, onset=8, ramp_days=15, base=None):
    t = np.arange(N) / 24
    p = np.clip((t - onset) / ramp_days, 0, 1)
    return (base if base is not None else healthy()) + total * p ** 1.4


# ---------------- traps ----------------
def test_flat_noise_is_normal():
    evs, _ = run(healthy())
    assert set(states(evs)) == {St.NORMAL}


def test_ramp_gives_watch_then_active_never_active_early():
    v = ramp(5.6)
    evs, _ = run(v)
    seq = states(evs)
    assert St.WATCH in seq and seq[-1] == St.ACTIVE_FAULT
    first_watch = seq.index(St.WATCH); first_active = seq.index(St.ACTIVE_FAULT)
    assert first_watch < first_active
    clean = 2.0 + 5.6 * np.clip((np.arange(N) / 24 - 8) / 15, 0, 1) ** 1.4
    cross_hour = int(np.argmax(clean >= 7.1))
    assert evs[first_active].now >= pd.Timestamp(START) + pd.Timedelta(hours=cross_hour)   # confirmed only after truly crossing


def test_single_sample_glitch_ignored_even_beyond_alarm():
    v = healthy(); v[300] = 14.0
    evs, _ = run(v)
    assert set(states(evs)) == {St.NORMAL}


def test_two_hour_spike_above_warn_ignored():
    v = healthy(); v[300] += 3.0; v[301] += 1.5
    evs, _ = run(v)
    assert set(states(evs)) == {St.NORMAL}


def test_stable_load_change_step_ignored():
    m = meta(sensor=S.CURRENT, nominal=25.0, warn=28.75, alarm=31.25)
    v = healthy(nominal=25.0, sd=0.3)
    v[360:] += 3.0                                           # +12% step that stays flat
    evs, _ = run(v, m=m, sensor=S.CURRENT)
    assert set(states(evs)) == {St.NORMAL}


def test_falling_pressure_uses_low_direction():
    m = meta(sensor=S.PRESSURE, nominal=6.0, warn=5.0, alarm=4.5, direction="low")
    t = np.arange(N) / 24
    v = healthy(nominal=6.0, sd=0.05) - 2.0 * np.clip((t - 6) / 18, 0, 1) ** 1.4
    evs, _ = run(v, m=m, sensor=S.PRESSURE)
    seq = states(evs)
    assert St.WATCH in seq and seq[-1] == St.ACTIVE_FAULT


def test_rising_pressure_is_not_a_fault_for_low_direction():
    m = meta(sensor=S.PRESSURE, nominal=6.0, warn=5.0, alarm=4.5, direction="low")
    t = np.arange(N) / 24
    v = healthy(nominal=6.0, sd=0.05) + 1.0 * np.clip((t - 6) / 18, 0, 1)
    evs, _ = run(v, m=m, sensor=S.PRESSURE)
    assert set(states(evs)) == {St.NORMAL}


def test_missing_data_holds_state_and_says_so():
    v = ramp(5.6)
    evs, _ = run(v, drop=list(range(N - 70, N - 52)))        # an 18 h outage in the middle of a confirmed fault
    held = [i for i, e in enumerate(evs) if e.notes == ["insufficient_data_or_learning"]]
    assert held, "the outage should trigger at least one 'insufficient data' tick"
    assert all(evs[i].state == evs[i - 1].state == St.ACTIVE_FAULT for i in held)
    assert evs[-1].state == St.ACTIVE_FAULT


def test_resolved_after_repair_then_normal():
    v = healthy(seed=3)
    t = np.arange(N) / 24
    fault = 5.6 * np.clip((t - 4.5) / 8, 0, 1) ** 1.4 * (t < 18)       # fault ramps up, then a 'repair' on day 18
    evs, _ = run(v + fault)
    seq = states(evs)
    assert St.ACTIVE_FAULT in seq and St.RESOLVED in seq and seq[-1] == St.NORMAL
    assert seq.index(St.RESOLVED) > seq.index(St.ACTIVE_FAULT)


def test_no_flicker_once_confirmed():
    evs, _ = run(ramp(5.6))
    seq = states(evs)
    i = seq.index(St.ACTIVE_FAULT)
    assert all(s == St.ACTIVE_FAULT for s in seq[i:])


def test_deterministic_same_input_same_output():
    a, _ = run(ramp(5.6)); b, _ = run(ramp(5.6))
    assert [e.flag.model_dump() if e.flag else None for e in a] == [e.flag.model_dump() if e.flag else None for e in b]


def test_step_not_aligned_to_day_blocks_still_ignored():
    m = meta(sensor=S.CURRENT, nominal=25.0, warn=28.75, alarm=31.25)
    for hour in (360, 366, 372, 378):                        # different alignments against the 24h blocks
        v = healthy(nominal=25.0, sd=0.3, seed=hour); v[hour:] += 3.0
        evs, _ = run(v, m=m, sensor=S.CURRENT)
        assert set(states(evs)) == {St.NORMAL}, hour


def test_plateau_below_warn_ends_watch():
    v = healthy(seed=5); t = np.arange(N) / 24
    v = v + 1.8 * np.clip((t - 8) / 4, 0, 1)                 # rises to ~3.8 mm/s (< warn 4.5) then stays flat
    evs, _ = run(v)
    seq = states(evs)
    assert St.WATCH in seq and seq[-1] == St.NORMAL


def test_plateau_above_warn_stays_watch_not_active():
    v = healthy(seed=6); t = np.arange(N) / 24
    v = v + 3.5 * np.clip((t - 8) / 4, 0, 1)                 # rises to ~5.5 mm/s (> warn, < alarm) then stays flat
    evs, _ = run(v)
    assert evs[-1].state == St.WATCH and St.ACTIVE_FAULT not in states(evs)


# ---------------- risk score ----------------
def flag_at_end(m, v, sensor=S.VIBRATION):
    evs, _ = run(v, m=m, sensor=sensor)
    return evs[-1].flag


def test_score_is_sum_of_breakdown_and_bands():
    evs, _ = run(ramp(5.6), m=meta(crit=3, service_days_ago=200))
    f = next(e.flag for e in evs if e.state == St.ACTIVE_FAULT)          # the moment it first turns confirmed
    assert f.state == St.ACTIVE_FAULT and f.risk_score == sum(c.points for c in f.score_breakdown)
    assert {c.factor for c in f.score_breakdown} >= {"trend", "threshold_breach", "criticality", "service_overdue"}
    assert f.risk == RiskLevel.HIGH


def test_criticality_and_service_change_the_score():
    hi = flag_at_end(meta(crit=3, service_days_ago=250), ramp(5.6))
    lo = flag_at_end(meta(crit=1, service_days_ago=10), ramp(5.6))
    assert hi.risk_score > lo.risk_score
    assert "criticality" not in {c.factor for c in lo.score_breakdown}


def test_watch_flag_never_breached_and_has_days_to_alarm():
    evs, _ = run(ramp(5.6, onset=22, ramp_days=16))           # late onset: still below alarm at the end
    f = evs[-1].flag
    assert f is not None and f.state == St.WATCH
    assert not any(s.threshold_breached for s in f.signals)
    assert f.signals[0].days_to_alarm is not None and f.signals[0].days_to_alarm > 0


# ---------------- dev-set integration (14 dev assets only) ----------------
@pytest.fixture(scope="module")
def dev_run():
    metas, df, labels = generate_fleet(42)
    dev = {l.asset_id: l for l in labels if l.split == "dev"}
    df = df[df.asset_id.isin(dev)]
    evs = DetectionEngine(df, [m for m in metas if m.asset_id in dev]).replay()
    return dev, evs


def test_dev_final_states_match_labels(dev_run):
    dev, evs = dev_run
    for aid, L in dev.items():
        final = [e for e in evs if e.asset_id == aid][-1]
        assert final.state.value == L.expected_state_at_end, aid


def test_dev_no_false_flags_on_healthy_or_decoy(dev_run):
    dev, evs = dev_run
    bad = [(e.asset_id, str(e.now)) for e in evs if dev[e.asset_id].category != "fault" and e.state in (St.WATCH, St.ACTIVE_FAULT)]
    assert bad == []


def test_dev_faults_warned_before_alarm(dev_run):
    dev, evs = dev_run
    for aid, L in dev.items():
        if L.category != "fault":
            continue
        first = next(e.now for e in evs if e.asset_id == aid and e.state in (St.WATCH, St.ACTIVE_FAULT))
        assert first.to_pydatetime() < L.alarm_cross_time, aid


def test_dev_never_confirms_before_alarm_crossed(dev_run):
    dev, evs = dev_run
    for e in evs:
        if e.state == St.ACTIVE_FAULT:
            assert e.now.to_pydatetime() >= dev[e.asset_id].alarm_cross_time - timedelta(hours=1), e.asset_id


def test_m204_confirmed_even_though_manuals_have_no_coverage(dev_run):
    _, evs = dev_run
    assert [e for e in evs if e.asset_id == "M-204"][-1].state == St.ACTIVE_FAULT
