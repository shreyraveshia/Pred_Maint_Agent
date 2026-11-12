"""CLI:  python -m data_gen.generate [--seed 42] [--tiny]
Writes dev data to data/dev/, held-out TEST data to data/heldout/ (do not open it while building)."""
import argparse, json
from pathlib import Path
import pandas as pd
from data_gen import config as C
from data_gen.generator import generate_fleet

ROOT = Path(__file__).resolve().parent.parent


def _write(folder: Path, df, labels):
    folder.mkdir(parents=True, exist_ok=True)
    df.to_parquet(folder / "sensors.parquet", index=False)
    (folder / "labels.json").write_text(json.dumps([l.model_dump(mode="json") for l in labels], indent=2))


def generate_all(seed: int = C.SEED, out_root: Path = ROOT / "data", tiny: bool = False) -> dict:
    out_root = Path(out_root)
    if tiny:
        metas, df, labels = generate_fleet(seed, only=C.TINY_ASSETS)
        _write(out_root / "tiny", df, labels)
        (out_root / "tiny" / "assets.json").write_text(json.dumps([m.model_dump(mode="json") for m in metas], indent=2))
        return {"tiny_assets": len(metas), "rows": len(df)}
    metas, df, labels = generate_fleet(seed)
    test_ids = {l.asset_id for l in labels if l.split == "test"}
    mask = df.asset_id.isin(test_ids)
    _write(out_root / "dev", df[~mask], [l for l in labels if l.split == "dev"])
    _write(out_root / "heldout", df[mask], [l for l in labels if l.split == "test"])
    (out_root / "assets.json").write_text(json.dumps([m.model_dump(mode="json") for m in metas], indent=2))
    fingerprint = format(int(pd.util.hash_pandas_object(df, index=False).sum()) & (2**64 - 1), "x")
    manifest = {"seed": seed, "assets": len(metas), "rows_total": len(df), "rows_dev": int((~mask).sum()),
                "rows_test": int(mask.sum()), "test_assets": sorted(test_ids), "fingerprint": fingerprint}
    (out_root / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=C.SEED)
    ap.add_argument("--tiny", action="store_true")
    a = ap.parse_args()
    print(json.dumps(generate_all(a.seed, tiny=a.tiny), indent=2))
