"""Two ways to use the detector:
   python -m detection.run --asset P-102 --now 2026-10-25T00:00        # print one Flag as JSON
   python -m detection.run --report                                    # replay all DEV assets, compare with dev labels
"""
import argparse, json, sys
from pathlib import Path
import pandas as pd
from contracts.models import AssetLabel, AssetMeta
from detection.engine import AssetMemory, DetectionEngine

ROOT = Path(__file__).resolve().parent.parent


def load(data_dir: Path):
    sensors = pd.read_parquet(data_dir / "sensors.parquet")
    ids = set(sensors.asset_id)
    metas = [AssetMeta(**m) for m in json.load(open(ROOT / "data" / "assets.json")) if m["asset_id"] in ids]
    return sensors, metas


def report(data_dir: Path):
    sensors, metas = load(data_dir)
    labels = {l["asset_id"]: AssetLabel(**l) for l in json.load(open(data_dir / "labels.json"))}
    evs = DetectionEngine(sensors, metas).replay()
    print(f'{"asset":6}{"truth":22}{"expected":13}{"final":13}{"1st watch":12}{"1st active":12}{"alarm(label)":14}{"lead d":7}{"false ticks"}')
    for aid in sorted(labels):
        L, mine = labels[aid], [e for e in evs if e.asset_id == aid]
        flagged = [e for e in mine if e.state.value in ("watch", "active_fault")]
        fw = next((e.now for e in mine if e.state.value == "watch"), None)
        fa = next((e.now for e in mine if e.state.value == "active_fault"), None)
        first = flagged[0].now if flagged else None
        lead = f"{(L.alarm_cross_time - first.to_pydatetime()).total_seconds() / 86400:.1f}" if (first is not None and L.alarm_cross_time) else "-"
        false_ticks = len(flagged) if L.category != "fault" else "-"
        truth = L.fault_type or (L.decoy_type or "healthy")
        fmt = lambda t: str(t)[5:16] if t is not None else "-"
        print(f'{aid:6}{truth:22}{L.expected_state_at_end:13}{mine[-1].state.value:13}{fmt(fw):12}{fmt(fa):12}'
              f'{fmt(L.alarm_cross_time):14}{lead:7}{false_ticks}')


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(ROOT / "data" / "dev"))
    ap.add_argument("--asset"); ap.add_argument("--now"); ap.add_argument("--report", action="store_true")
    ap.add_argument("--i-accept-peeking", action="store_true")
    a = ap.parse_args()
    if "heldout" in a.data and not a.i_accept_peeking:
        sys.exit("Refusing to touch the held-out set while building. (Phase 10 only.)")
    d = Path(a.data)
    if a.report:
        report(d)
    elif a.asset and a.now:
        sensors, metas = load(d)
        eng = DetectionEngine(sensors, metas)
        now, mem, ev = pd.Timestamp(a.now, tz="UTC"), None, None
        for t in [t for t in eng.ticks(6) if t <= now]:          # replay so hysteresis memory is correct
            ev, mem = eng.evaluate(a.asset, t, mem)
        print("state:", ev.state.value, "| notes:", ev.notes)
        if ev.flag:
            print(ev.flag.model_dump_json(indent=2))
