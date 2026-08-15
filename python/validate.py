"""
Validate the Confluence Signal Engine's rules on historical data.

Pine cannot be backtested outside TradingView, so this runs the mirrored Python
implementation and reports, honestly:

  * how often the engine actually signals (it should be rare),
  * what happened after each signal vs. the symbol's own baseline drift,
  * whether the volatility noise-floor gate does any real filtering work.

A result of "no edge" is a valid and reportable outcome.

Usage:  python validate.py [SYM ...]
"""
from __future__ import annotations

import sys
import time

import numpy as np
import pandas as pd

from cse.engine import Config, fetch, run

DEFAULT = ["NVDA", "AAPL", "CL=F", "USO", "MSFT", "AMZN", "GOOGL", "META",
           "TSLA", "AMD", "SPY", "QQQ", "XOM", "CVX"]
HORIZONS = (5, 10, 21)


def trades_from(d: pd.DataFrame) -> pd.DataFrame:
    """Reconstruct closed trades from the engine's position state."""
    rows = []
    open_i = None
    for i in range(len(d)):
        if d["long_sig"].iloc[i]:
            open_i = i
        elif open_i is not None and d["pos"].iloc[i] == 0 and d["pos"].iloc[i - 1] == 1:
            e, x = d["close"].iloc[open_i], d["close"].iloc[i]
            rows.append(dict(
                entry_i=open_i, exit_i=i, bars=i - open_i,
                entry=e, exit=x, ret=(x / e - 1) * 100,
                rr_planned=d["long_rr"].iloc[open_i],
                regime=d["regime"].iloc[open_i],
                armed=bool(d["db_armed"].iloc[open_i]),
            ))
            open_i = None
    return pd.DataFrame(rows)


def baseline(d: pd.DataFrame, h: int) -> tuple[float, float]:
    c = d["close"].to_numpy()
    a, b = c[:-h], c[h:]
    ok = np.isfinite(a) & np.isfinite(b) & (a > 0) & (b > 0)
    f = b[ok] / a[ok] - 1
    if f.size == 0:
        return float("nan"), float("nan")
    return float((f > 0).mean()), float(np.median(f) * 100)


def main(syms: list[str]) -> None:
    cfg = Config()
    all_tr, all_sig, summary = [], [], []

    for s in syms:
        try:
            d1 = fetch(s, "10y", "1d")
            wk = fetch(s, "10y", "1wk")
        except Exception as exc:  # network / symbol problems shouldn't abort the run
            print(f"  !! {s}: fetch failed ({exc})")
            continue
        if len(d1) < 300:
            print(f"  !! {s}: insufficient history")
            continue

        d = run(d1, cfg, htf=wk)
        n_bars = int(d["score"].notna().sum())
        sig_i = np.where(d["long_sig"].to_numpy())[0]
        rate = len(sig_i) / max(n_bars, 1) * 100

        # forward returns from every signal bar, vs baseline
        c = d["close"].to_numpy()
        fwd = {}
        for h in HORIZONS:
            ok = sig_i[sig_i < len(c) - h]
            r = (c[ok + h] / c[ok] - 1) * 100 if len(ok) else np.array([])
            b_p, b_m = baseline(d, h)
            fwd[h] = dict(n=len(r),
                          p_up=float((r > 0).mean()) if len(r) else np.nan,
                          med=float(np.median(r)) if len(r) else np.nan,
                          base_p=b_p, base_med=b_m)
            for v in r:
                all_sig.append(dict(sym=s, h=h, ret=v))

        tr = trades_from(d)
        if len(tr):
            tr["sym"] = s
            all_tr.append(tr)

        blocked = d.loc[d["score"].notna(), "blocked_by"].value_counts(normalize=True) * 100
        summary.append(dict(
            sym=s, bars=n_bars, signals=len(sig_i), rate=rate,
            trades=len(tr),
            win=float((tr["ret"] > 0).mean() * 100) if len(tr) else np.nan,
            med=float(tr["ret"].median()) if len(tr) else np.nan,
            mean=float(tr["ret"].mean()) if len(tr) else np.nan,
            bars_held=float(tr["bars"].median()) if len(tr) else np.nan,
            noise_block=float(blocked.get("target inside noise floor", 0.0)),
        ))

        print(f"\n=== {s} ===  bars={n_bars}  signals={len(sig_i)} ({rate:.2f}% of bars)  "
              f"trades={len(tr)}")
        for h in HORIZONS:
            f = fwd[h]
            if f["n"]:
                edge = f["p_up"] - f["base_p"]
                print(f"   H={h:2d}: n={f['n']:3d}  P(up)={f['p_up']:.3f} vs base {f['base_p']:.3f} "
                      f"({edge:+.3f})   med={f['med']:+.2f}% vs base {f['base_med']:+.2f}%")
        if len(tr):
            print(f"   trades: win={float((tr['ret'] > 0).mean()) * 100:.1f}%  "
                  f"med={tr['ret'].median():+.2f}%  mean={tr['ret'].mean():+.2f}%  "
                  f"median hold={tr['bars'].median():.0f} bars")
        print("   top blocking reasons: " + ", ".join(
            f"{k} {v:.0f}%" for k, v in blocked.head(4).items()))
        time.sleep(0.3)

    print("\n" + "=" * 100)
    print("AGGREGATE")
    print("=" * 100)
    S = pd.DataFrame(summary)
    if not S.empty:
        print(S.to_string(index=False, float_format=lambda x: f"{x:.2f}"))
        print(f"\n  mean signal rate: {S['rate'].mean():.2f}% of bars "
              f"(~1 signal per {100 / max(S['rate'].mean(), 1e-9):.0f} bars)")
        print(f"  bars blocked by the NOISE FLOOR gate: {S['noise_block'].mean():.1f}% "
              f"(this is the gate doing its job)")
    if all_tr:
        T = pd.concat(all_tr, ignore_index=True)
        print(f"\n  ALL TRADES: n={len(T)}  win={float((T['ret'] > 0).mean()) * 100:.1f}%  "
              f"med={T['ret'].median():+.2f}%  mean={T['ret'].mean():+.2f}%  "
              f"median hold={T['bars'].median():.0f} bars")
        pos, neg = T.loc[T["ret"] > 0, "ret"], T.loc[T["ret"] <= 0, "ret"]
        if len(neg) and neg.sum() != 0:
            print(f"  profit factor={abs(pos.sum() / neg.sum()):.2f}  "
                  f"avg win={pos.mean():+.2f}%  avg loss={neg.mean():+.2f}%")
        print("\n  by regime at entry:")
        print(T.groupby("regime")["ret"].agg(["count", "median", "mean"]).to_string(
            float_format=lambda x: f"{x:.2f}"))
        print("\n  double-bottom retest-held signals vs other setups:")
        print(T.groupby("armed")["ret"].agg(["count", "median", "mean"]).to_string(
            float_format=lambda x: f"{x:.2f}"))
    if all_sig:
        A = pd.DataFrame(all_sig)
        print("\n  pooled forward returns from signal bars:")
        print(A.groupby("h")["ret"].agg(
            n="count", p_up=lambda x: (x > 0).mean(), median="median", mean="mean"
        ).to_string(float_format=lambda x: f"{x:.3f}"))


if __name__ == "__main__":
    main(sys.argv[1:] or DEFAULT)
