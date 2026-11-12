"""Mini exercise 1: detect a slow drift hidden in noise using rolling z-score + slope."""
import numpy as np, pandas as pd

rng = np.random.default_rng(42)
hours = 24 * 30
t = pd.date_range("2026-01-01", periods=hours, freq="h")
daily_cycle = 0.3 * np.sin(2 * np.pi * np.arange(hours) / 24)
noise = rng.normal(0, 0.15, hours)
drift = np.where(np.arange(hours) > 24 * 18, (np.arange(hours) - 24 * 18) * 0.004, 0)  # starts day 18
vib = pd.Series(2.0 + daily_cycle + noise + drift, index=t)

baseline = vib.iloc[: 24 * 10]                       # first 10 days = "healthy"
mu, sd = baseline.mean(), baseline.std()
z = (vib.rolling(24).mean() - mu) / sd               # daily-mean z-score vs baseline


def slope_per_day(s: pd.Series) -> float:
    x = np.arange(len(s)) / 24
    return np.polyfit(x, s.values, 1)[0]


slope = vib.rolling(24 * 3).apply(slope_per_day, raw=False)
flag = (z > 3) & (slope > 0.05)
print("First flagged at:", flag.idxmax() if flag.any() else None, "| drift began:", t[24 * 18])
# TODO for you: add a one-hour spike decoy. Does your rule wrongly flag it? Fix it with persistence.
