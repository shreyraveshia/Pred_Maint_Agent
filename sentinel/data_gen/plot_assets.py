"""Visual sanity check:  python -m data_gen.plot_assets            (dev assets only)
Draws every sensor with warn/alarm lines, 24h rolling mean, and shaded fault/decoy windows."""
import argparse, json
from pathlib import Path
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from contracts.models import AssetLabel, AssetMeta

ROOT = Path(__file__).resolve().parent.parent


def plot_asset(df, meta: AssetMeta, label: AssetLabel, out: Path):
    sensors = list(meta.thresholds.keys())
    fig, axes = plt.subplots(len(sensors), 1, figsize=(11, 2.3 * len(sensors)), sharex=True)
    for ax, s in zip(axes, sensors):
        d = df[(df.asset_id == meta.asset_id) & (df.sensor == s.value)].set_index("timestamp")["value"]
        ax.plot(d.index, d.values, lw=0.6, alpha=0.5, label="hourly")
        ax.plot(d.index, d.rolling(24, min_periods=6).mean(), lw=1.6, label="24h mean")
        th = meta.thresholds[s]
        ax.axhline(th.warn, ls="--", c="orange", lw=1); ax.axhline(th.alarm, ls="--", c="red", lw=1)
        if label.onset_time and s in label.affected_sensors:
            ax.axvspan(label.onset_time, d.index[-1], color="red", alpha=0.07)
        for e in label.decoy_events:
            if s.value in e["sensors"]:
                ax.axvspan(pd.Timestamp(e["start"]), pd.Timestamp(e["end"]) + pd.Timedelta(hours=1), color="green", alpha=0.3)
        ax.set_ylabel(s.value, fontsize=8)
    title = f"{meta.asset_id} {meta.name} | {label.category.upper()} {label.fault_type or label.decoy_type or ''} | expected end state: {label.expected_state_at_end}"
    axes[0].set_title(title, fontsize=10); axes[0].legend(fontsize=7, loc="upper left")
    fig.tight_layout(); out.parent.mkdir(parents=True, exist_ok=True); fig.savefig(out, dpi=90); plt.close(fig)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--split", default="dev", choices=["dev", "heldout", "tiny"])
    a = ap.parse_args()
    if a.split == "heldout":
        print("WARNING: you are looking at the held-out test set. Do not tune anything based on it.")
    folder = ROOT / "data" / a.split
    df = pd.read_parquet(folder / "sensors.parquet")
    metas = {m["asset_id"]: AssetMeta(**m) for m in json.load(open(folder / "assets.json" if a.split == "tiny" else ROOT / "data" / "assets.json"))}
    for l in json.load(open(folder / "labels.json")):
        lab = AssetLabel(**l); plot_asset(df, metas[lab.asset_id], lab, ROOT / "docs" / "plots" / a.split / f"{lab.asset_id}.png")
    print("plots written to docs/plots/", a.split)
