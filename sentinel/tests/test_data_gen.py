import json
import numpy as np, pandas as pd, pytest
from data_gen import config as C
from data_gen.generate import generate_all
from data_gen.generator import generate_fleet
from contracts.models import AssetLabel, AssetMeta, SensorType as S


@pytest.fixture(scope="module")
def fleet():
    return generate_fleet(seed=42)


def last_day_mean(df, asset, sensor):
    d = df[(df.asset_id == asset) & (df.sensor == sensor.value)].sort_values("timestamp")
    return d.value.tail(24).mean()


def test_deterministic_same_seed():
    _, a, _ = generate_fleet(42); _, b, _ = generate_fleet(42)
    pd.testing.assert_frame_equal(a, b)


def test_different_seed_differs():
    _, a, _ = generate_fleet(42); _, b, _ = generate_fleet(7)
    assert not a.value.equals(b.value)


def test_adding_asset_does_not_change_others():
    _, full, _ = generate_fleet(42)
    _, sub, _ = generate_fleet(42, only=["P-102"])
    pd.testing.assert_frame_equal(full[full.asset_id == "P-102"].reset_index(drop=True), sub.reset_index(drop=True))


def test_fleet_size_and_duration(fleet):
    metas, df, labels = fleet
    assert 15 <= len(metas) <= 20 and len(labels) == len(metas)
    span = df.timestamp.max() - df.timestamp.min()
    assert span.days == 29  # 30 days of hourly data


def test_labels_cover_every_asset_once(fleet):
    metas, _, labels = fleet
    assert sorted(m.asset_id for m in metas) == sorted(l.asset_id for l in labels)


def test_test_split_is_about_20_percent_and_representative(fleet):
    _, _, labels = fleet
    test = [l for l in labels if l.split == "test"]
    assert abs(len(test) / len(labels) - 0.2) <= 0.05
    cats = {l.category for l in test}
    assert cats == {"fault", "decoy", "healthy"}
    states = {l.expected_state_at_end for l in test}
    assert {"watch", "active_fault"} <= states           # both demo fault cases present


def test_demo_cases_exist_in_dev(fleet):
    _, _, labels = fleet
    dev = [l for l in labels if l.split == "dev"]
    assert any(l.expected_state_at_end == "watch" for l in dev)
    assert any(l.expected_state_at_end == "active_fault" for l in dev)
    assert any(l.category == "decoy" for l in dev)


def test_exactly_one_fault_has_no_manual_coverage(fleet):
    _, _, labels = fleet
    assert [l.asset_id for l in labels if l.category == "fault" and not l.has_manual_coverage] == ["M-204"]


def test_active_faults_cross_alarm_and_watch_do_not(fleet):
    metas, df, labels = fleet
    meta = {m.asset_id: m for m in metas}
    for l in labels:
        if l.category != "fault":
            continue
        th = meta[l.asset_id].thresholds[l.primary_sensor]
        v = last_day_mean(df, l.asset_id, l.primary_sensor)
        crossed = v >= th.alarm if th.direction == "high" else v <= th.alarm
        assert crossed == (l.expected_state_at_end == "active_fault"), l.asset_id


def test_healthy_and_decoy_daily_means_never_reach_warn(fleet):
    metas, df, labels = fleet
    meta = {m.asset_id: m for m in metas}
    for l in labels:
        if l.category == "fault":
            continue
        for s, th in meta[l.asset_id].thresholds.items():
            d = df[(df.asset_id == l.asset_id) & (df.sensor == s.value)].set_index("timestamp").value.rolling("24h").mean()
            bad = (d >= th.warn).any() if th.direction == "high" else (d <= th.warn).any()
            assert not bad, f"{l.asset_id} {s.value} daily mean reached warn"


def test_decoys_really_are_adversarial(fleet):
    """Raw hourly values DO cross thresholds (that is the trap) but only briefly."""
    metas, df, _ = fleet
    meta = {m.asset_id: m for m in metas}
    v = df[(df.asset_id == "P-105") & (df.sensor == "vibration_mm_s")].value
    assert (v > meta["P-105"].thresholds[S.VIBRATION].warn).sum() >= 3
    g = df[(df.asset_id == "P-107") & (df.sensor == "vibration_mm_s")].value
    assert (g > meta["P-107"].thresholds[S.VIBRATION].alarm).sum() == 1   # single-sample glitch


def test_data_gap_present(fleet):
    _, df, _ = fleet
    c = df[(df.asset_id == "C-304") & (df.sensor == "temperature_c")]
    assert len(c) == C.N - 6


def test_heldout_files_are_physically_separate(tmp_path):
    generate_all(42, tmp_path)
    dev = pd.read_parquet(tmp_path / "dev" / "sensors.parquet")
    held = pd.read_parquet(tmp_path / "heldout" / "sensors.parquet")
    assert set(dev.asset_id).isdisjoint(set(held.asset_id))
    assert set(held.asset_id) == set(C.TEST_ASSETS)
    assert all(AssetLabel(**l).split == "test" for l in json.load(open(tmp_path / "heldout" / "labels.json")))
    assert all(AssetMeta(**m) for m in json.load(open(tmp_path / "assets.json")))
