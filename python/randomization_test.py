"""
Randomization test: does the ENTRY signal add anything?

A profitable-looking backtest can come entirely from (a) the basket's upward
drift and (b) an asymmetric exit rule that cuts losses and lets winners run.
Neither requires the entry signal to carry information.

This holds the exit logic and trade count fixed, replaces engine entries with
RANDOM entries, and asks whether the real signals beat the random ones.

If the engine's entries land inside the random distribution, the entry rules
add nothing and should be described that way.

Usage:  python randomization_test.py [ITERATIONS]
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from cse.engine import Config, fetch, run

SYMS = ["NVDA", "AAPL", "CL=F", "USO", "MSFT", "AMZN", "GOOGL", "META",
        "TSLA", "AMD", "SPY", "QQQ", "XOM", "CVX"]


def simulate(d: pd.DataFrame, entries: list[int], cfg: Config) -> list[float]:
    """Apply the engine's exit rules to an arbitrary set of entry bars."""
    c = d["close"].to_numpy()
    hi = d["high"].to_numpy()
    atrv = d["atr"].to_numpy()
    sup = d["sup"].to_numpy()
    tgt_a = d["target"].to_numpy()
    score = d["score"].to_numpy()
    z = d["z20"].to_numpy()
    sk = d["stochk"].to_numpy()
    rv = d["relvol5"].to_numpy()
    n = len(d)
    out = []
    for e in entries:
        if e >= n - 2 or np.isnan(atrv[e]) or np.isnan(c[e]):
            continue
        px = c[e]
        struct_stop = (sup[e] - 0.5 * atrv[e]) if not np.isnan(sup[e]) else px - 2.0 * atrv[e]
        stop = min(struct_stop, px - 1.0 * atrv[e])
        tgt = tgt_a[e] if not np.isnan(tgt_a[e]) else px + 2.5 * atrv[e]
        exit_px = c[min(e + 60, n - 1)]           # time stop, matches median holds
        for j in range(e + 1, min(e + 61, n)):
            degraded = (not np.isnan(score[j])) and score[j] < 0
            extended = (not np.isnan(z[j]) and z[j] > 2.0
                        and not np.isnan(sk[j]) and sk[j] > 90
                        and not np.isnan(rv[j]) and rv[j] < 0.8)
            if c[j] < stop or hi[j] >= tgt or degraded or extended:
                exit_px = c[j]
                break
        out.append((exit_px / px - 1) * 100)
    return out


def main(iters: int = 500) -> None:
    cfg = Config()
    rng = np.random.default_rng(42)
    real_all: list[float] = []
    rand_means = np.zeros(iters)
    rand_wins = np.zeros(iters)
    per_sym = []

    frames = {}
    for s in SYMS:
        try:
            frames[s] = run(fetch(s, "10y", "1d"), cfg, htf=fetch(s, "10y", "1wk"))
        except Exception as exc:
            print(f"  !! {s}: {exc}")
    print(f"loaded {len(frames)} symbols\n")

    # real signals
    counts = {}
    for s, d in frames.items():
        e = list(np.where(d["long_sig"].to_numpy())[0])
        counts[s] = len(e)
        r = simulate(d, e, cfg)
        real_all += r
        if r:
            per_sym.append(dict(sym=s, n=len(r), mean=np.mean(r), median=np.median(r),
                                win=(np.array(r) > 0).mean() * 100))

    real_mean = float(np.mean(real_all))
    real_win = float((np.array(real_all) > 0).mean() * 100)
    real_med = float(np.median(real_all))

    # random entries, same count per symbol, restricted to bars the engine could
    # have evaluated (features present)
    for it in range(iters):
        pool: list[float] = []
        for s, d in frames.items():
            valid = np.where(d["score"].notna().to_numpy())[0]
            valid = valid[valid < len(d) - 61]
            if len(valid) == 0 or counts[s] == 0:
                continue
            e = rng.choice(valid, size=min(counts[s], len(valid)), replace=False)
            pool += simulate(d, list(e), cfg)
        rand_means[it] = np.mean(pool) if pool else np.nan
        rand_wins[it] = (np.array(pool) > 0).mean() * 100 if pool else np.nan

    rm = rand_means[np.isfinite(rand_means)]
    rw = rand_wins[np.isfinite(rand_wins)]
    p_mean = float((rm >= real_mean).mean())
    p_win = float((rw >= real_win).mean())

    print("=" * 78)
    print("RANDOMIZATION TEST — engine entries vs random entries, identical exits")
    print("=" * 78)
    print(pd.DataFrame(per_sym).to_string(index=False, float_format=lambda x: f"{x:.2f}"))
    print(f"\n  REAL   trades={len(real_all)}  mean={real_mean:+.3f}%  "
          f"median={real_med:+.3f}%  win={real_win:.1f}%")
    print(f"  RANDOM ({len(rm)} iterations, same trade count & exit rules)")
    print(f"         mean  : avg={rm.mean():+.3f}%  sd={rm.std():.3f}  "
          f"5-95pct=[{np.percentile(rm,5):+.3f}, {np.percentile(rm,95):+.3f}]")
    print(f"         win%  : avg={rw.mean():.1f}%  sd={rw.std():.2f}  "
          f"5-95pct=[{np.percentile(rw,5):.1f}, {np.percentile(rw,95):.1f}]")
    print(f"\n  p-value (random mean >= engine mean) = {p_mean:.3f}")
    print(f"  p-value (random win%  >= engine win%) = {p_win:.3f}")
    edge = real_mean - rm.mean()
    print(f"\n  EDGE over random entry: {edge:+.3f} percentage points per trade "
          f"({edge / rm.std():+.2f} sd)")
    verdict = ("ENTRY ADDS SIGNAL (p<0.05)" if p_mean < 0.05
               else "WEAK / SUGGESTIVE (0.05<=p<0.20)" if p_mean < 0.20
               else "NO DEMONSTRABLE ENTRY EDGE (p>=0.20)")
    print(f"  VERDICT: {verdict}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 500)
