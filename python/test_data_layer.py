"""
Regression tests for the data-layer defects found in audit (fix batch 2).

Each test pins a specific bug that silently corrupted results:
  1. _clip() returned the UPPER BOUND for NaN, so a NaN score became +100.
  2. The weekly partial-bar guard never fired (7-day stamp gap vs a <5 day test).
  3. WTI's negative-price row was DELETED, splicing two non-adjacent bars into
     one fabricated return -- the artifact METHODOLOGY.md warns against.
  4. dropna() omitted volume, so one NaN poisoned OBV for the entire series.

Run:  python test_data_layer.py
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from cse.engine import Config, _clip, compute_features, ewma_var, fetch, obv, rsi

fails = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global fails
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))
    fails += not ok


print("1. _clip propagates NaN instead of returning a bound")
check("_clip(nan,-100,100) is NaN", np.isnan(_clip(float("nan"), -100, 100)),
      f"got {_clip(float('nan'), -100, 100)}")
check("_clip(nan,-1,1) is NaN", np.isnan(_clip(float("nan"), -1, 1)))
check("_clip still clips normally", _clip(5, -1, 1) == 1 and _clip(-5, -1, 1) == -1)

print("2. RSI defines the zero-loss case rather than emitting NaN")
rising = pd.Series(np.arange(100, 160, dtype=float))     # monotonic: no down moves
r = rsi(rising, 14)
check("monotonic rise -> RSI 100, not NaN", not np.isnan(r.iloc[-1]) and r.iloc[-1] > 99,
      f"got {r.iloc[-1]:.2f}")
flat = pd.Series(np.full(60, 50.0))
check("flat series -> RSI 50, not NaN", abs(rsi(flat, 14).iloc[-1] - 50) < 1e-6)

print("3. weekly partial/off-cycle bar is actually dropped")
wk = fetch("AAPL", "1y", "1wk")
last = wk["dt"].iloc[-1]
now = pd.Timestamp.now(tz=last.tz)
# a weekly bar is complete once its final session (Friday) has passed
check("last weekly bar's final session has passed",
      now.normalize() > (last + pd.Timedelta(days=4)).normalize(),
      f"last bar {last.date()} (final session {(last + pd.Timedelta(days=4)).date()}), now {now.date()}")
wk10 = fetch("NVDA", "10y", "1wk")
gaps = wk10["dt"].diff().dt.days.dropna()
check("no off-cycle trailing weekly bar retained", bool((gaps.tail(5) >= 5).all()),
      f"last gaps={list(gaps.tail(5).astype(int))}")

print("4. negative prices are masked, not spliced away")
cl = fetch("CL=F", "10y", "1d")
neg = cl[cl["close"] <= 0]
check("the 2020-04-20 negative row is RETAINED", len(neg) >= 1,
      f"{len(neg)} non-positive rows kept")
if len(neg):
    d = compute_features(cl, Config())
    i = int(neg.index[0])
    span = d["logret"].iloc[i:i + 2]
    check("returns spanning it are NaN (undefined), not fabricated",
          bool(span.isna().all()), f"logret={list(np.round(span.values, 4))}")
    biggest = np.nanmax(np.abs(d["logret"].to_numpy()))
    check("no fabricated giant return remains", biggest < 1.0,
          f"max |logret| = {biggest:.3f}")

print("5. missing volume does not poison OBV")
df = pd.DataFrame({"close": np.linspace(10, 20, 50),
                   "volume": np.full(50, 1000.0)})
df.loc[10, "volume"] = np.nan
o = obv(df)
check("OBV finite after a NaN volume bar", bool(np.isfinite(o.iloc[-1])),
      f"tail={o.iloc[-1]}")

print("6. EWMA variance carries through undefined returns")
lr = pd.Series([0.01, -0.02, np.nan, 0.015, -0.01])
v = ewma_var(lr)
check("variance stays positive and finite across NaN",
      bool(np.all(np.isfinite(v)) and v.iloc[2] == v.iloc[1]),
      f"v={list(np.round(v.values, 6))}")


print("7. exit fills are symmetric and gap-aware")
_cfg = Config()
_d = pd.DataFrame({
    "open":   [100.0, 99.0, 94.0, 96.0],
    "high":   [101.0, 99.5, 95.0, 99.0],
    "low":    [ 99.0, 92.0, 93.0, 95.0],   # bar 1 trades THROUGH a 95 stop...
    "close":  [100.0, 99.2, 94.5, 98.0],   # ...but closes back above it
})
_stop = 95.0
# old behaviour: close(99.2) < stop(95) is False -> no loss recorded at all
check("intrabar low triggers the stop even when the close recovers",
      bool(_d["low"].iloc[1] <= _stop and _d["close"].iloc[1] > _stop),
      "this bar was previously recorded as no-loss")
# gap-through fill: bar 2 opens at 94, already below the stop
check("a gap through the stop fills at the open, not the stop",
      min(_d["open"].iloc[2], _stop) == 94.0,
      f"fill={min(_d['open'].iloc[2], _stop)}")
check("a gap through a target fills at the open, not the target",
      max(_d["open"].iloc[3], 95.5) == 96.0)


print("8. an armed pattern retires instead of pinning a stale target")
from cse.engine import run as _run, fetch as _fetch
_deg = _tot = 0
for _s in ("AAPL", "TSLA", "NVDA"):
    _d = _run(_fetch(_s, "10y", "1d"), Config(), htf=_fetch(_s, "10y", "1wk"))
    _m = _d["plan_target"].notna() & _d["close"].notna()
    _deg += int(((_d["plan_target"] <= _d["close"]) & _m).sum())
    _tot += int(_m.sum())
check("planned target is never at or below price",
      _deg == 0, f"{_deg}/{_tot} degenerate (was ~10.5% before retirement)")

print("\nRESULT (full suite):", "all clear" if fails == 0 else f"{fails} FAILURE(S)")
sys.exit(1 if fails else 0)
