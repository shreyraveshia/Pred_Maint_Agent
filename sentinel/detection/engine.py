"""Orchestrates features -> rules -> risk -> Flag. Never sees labels. Never calls an LLM."""
from __future__ import annotations
from dataclasses import dataclass, field
import pandas as pd
from contracts.models import AssetMeta, AssetState, Flag, SensorType, SignalEvidence
from detection.config import DetectionConfig
from detection.features import compute_features
from detection.risk import score_flag
from detection.rules import decide_state, judge_sensor


@dataclass(frozen=True)
class AssetMemory:
    state: AssetState = AssetState.NORMAL
    breached: frozenset = frozenset()
    last_key: tuple | None = None
    last_trend: pd.Timestamp | None = None


@dataclass
class AssetEval:
    asset_id: str
    now: pd.Timestamp
    state: AssetState
    flag: Flag | None
    notes: list[str] = field(default_factory=list)
    changed: bool = False          # state or risk level differs from the previous evaluation


class DetectionEngine:
    def __init__(self, sensors: pd.DataFrame, assets: list[AssetMeta], cfg: DetectionConfig | None = None):
        self.cfg = cfg or DetectionConfig()
        self.assets = {a.asset_id: a for a in assets}
        self.series: dict[tuple[str, SensorType], pd.Series] = {}
        for (aid, sensor), g in sensors.groupby(["asset_id", "sensor"]):
            self.series[(aid, SensorType(sensor))] = g.set_index("timestamp")["value"].sort_index()
        self.start = sensors["timestamp"].min()
        self.end = sensors["timestamp"].max()

    def evaluate(self, asset_id: str, now: pd.Timestamp, mem: AssetMemory | None = None) -> tuple[AssetEval, AssetMemory]:
        mem = mem or AssetMemory()
        meta = self.assets[asset_id]
        js = []
        for sensor, th in meta.thresholds.items():
            s = self.series.get((asset_id, sensor))
            f = compute_features(s, now, self.cfg) if s is not None else None
            js.append(judge_sensor(sensor, f, th, self.cfg, was_breached=sensor in mem.breached))
        state, evidence, ok, last_trend = decide_state(js, mem.state, now, mem.last_trend, self.cfg)
        if not ok:
            ev = AssetEval(asset_id, now, state, None, ["insufficient_data_or_learning"])
            return ev, mem
        flag = None
        key = (state, None)
        if state in (AssetState.WATCH, AssetState.ACTIVE_FAULT):
            score, comps, level = score_flag(meta, now, evidence, self.cfg)
            sigs = [SignalEvidence(sensor=j.sensor, window_start=j.f.window_start.to_pydatetime(),
                                   window_end=j.f.window_end.to_pydatetime(), latest_value=round(j.f.latest, 3),
                                   rolling_mean=round(j.f.mean24, 3), z_score=round(j.f.z, 2),
                                   slope_per_day=round(j.f.slope_per_day, 4), threshold=meta.thresholds[j.sensor].alarm,
                                   threshold_breached=j.breached, days_to_alarm=j.days_to_alarm) for j in evidence]
            flag = Flag(flag_id=f"FLG-{asset_id}-{now:%Y%m%d%H}", asset_id=asset_id, created_at=now.to_pydatetime(),
                        state=state, risk=level, risk_score=score, score_breakdown=comps, signals=sigs)
            key = (state, level)
        new_mem = AssetMemory(state=state, breached=frozenset(j.sensor for j in js if j.ok_data and j.breached),
                              last_key=key, last_trend=last_trend)
        return AssetEval(asset_id, now, state, flag, [], changed=key != mem.last_key), new_mem

    def ticks(self, step_hours: int = 6) -> list[pd.Timestamp]:
        first = self.start + pd.Timedelta(days=self.cfg.baseline_days, hours=self.cfg.slope_hours)
        t = list(pd.date_range(first, self.end, freq=f"{step_hours}h"))
        if not t or t[-1] != self.end:
            t.append(self.end)
        return t

    def replay(self, step_hours: int = 6, asset_ids: list[str] | None = None) -> list[AssetEval]:
        """Walk through time. At each tick the engine sees only data up to that tick."""
        out, ids = [], asset_ids or sorted({a for a, _ in self.series})
        mems = {a: AssetMemory() for a in ids}
        for now in self.ticks(step_hours):
            for a in ids:
                ev, mems[a] = self.evaluate(a, now, mems[a])
                out.append(ev)
        return out
