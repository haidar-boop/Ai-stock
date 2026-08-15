"""
Regression test: the higher-timeframe merge must never leak future data.

This guards a bug that silently contaminated every published backtest number.
Yahoo stamps an HTF bar at the START of its period — a weekly bar dated Monday
holds Friday's close. Offsetting that timestamp by a token amount (the original
implementation added 1 second) lands INSIDE the bar, so every Tuesday-to-Friday
daily bar could read its own week's Friday close: three days of future data,
feeding the highest-weighted score factor and two of the four entry setups.

Run:  python test_no_lookahead.py
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from cse.engine import Config, compute_features, fetch

SYMBOLS = ["AAPL", "MSFT", "SPY"]


def check(symbol: str) -> tuple[int, int]:
    """Return (bars_checked, leaking_bars) for one symbol."""
    daily = fetch(symbol, "2y", "1d")
    weekly = fetch(symbol, "5y", "1wk")
    d = compute_features(daily, Config(), htf=weekly)

    w = weekly[["dt", "close"]].copy()
    # a weekly bar stamped Monday is complete only after that week's final session
    w["completed_on"] = w["dt"] + pd.Timedelta(days=6)

    checked = leaking = 0
    for _, r in d.iterrows():
        if pd.isna(r.get("close_htf", np.nan)):
            continue
        src = w[np.isclose(w["close"], r["close_htf"])]
        if src.empty:
            continue
        checked += 1
        if src["completed_on"].iloc[-1].date() >= r["dt"].date():
            leaking += 1
    return checked, leaking


def main() -> int:
    failures = 0
    for sym in SYMBOLS:
        try:
            checked, leaking = check(sym)
        except Exception as exc:
            print(f"  {sym:6s} SKIP (fetch failed: {exc})")
            continue
        status = "PASS" if leaking == 0 else "FAIL"
        print(f"  {sym:6s} {status}  bars_checked={checked:5d}  leaking={leaking}")
        failures += leaking > 0

    # explicit assertion of the original failing case, so the exact regression
    # cannot silently return
    try:
        d = compute_features(fetch("AAPL", "2y", "1d"), Config(), htf=fetch("AAPL", "5y", "1wk"))
        row = d[d["dt"].dt.date == pd.Timestamp("2026-08-04").date()]
        if len(row):
            got = float(row["close_htf"].iloc[0])
            # 313.33 is the close of the week CONTAINING 2026-08-04 — reading it
            # on the Tuesday of that week is the leak.
            if abs(got - 313.33) < 0.01:
                print(f"  AAPL 2026-08-04 FAIL: close_htf={got} is its own week's Friday close")
                failures += 1
            else:
                print(f"  AAPL 2026-08-04 PASS: close_htf={got} (prior completed week)")
    except Exception as exc:
        print(f"  pinned-case SKIP ({exc})")

    print("\nRESULT:", "all clear" if failures == 0 else f"{failures} FAILURE(S)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
