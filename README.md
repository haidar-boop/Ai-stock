# Confluence Signal Engine (CSE)

A TradingView chart overlay that issues conservative buy / sell / exit signals, plus the
Python research code it was derived from and validated against.

**Not investment advice.** This is probabilistic tooling. Read
[the validation results](#validation--read-this-before-using-it) before trusting a signal.

---

## Validation — read this before using it

The engine was built from a quantitative study (10–15 years of daily data, 22-symbol basket)
and then tested against random entries using identical exit rules. Both results are reported,
including the one that undercuts the tool:

| Test | Basket | Trades | Edge vs random entry | p-value | Verdict |
|---|---|---|---|---|---|
| In-sample | Tech / energy (the design basket) | 134 | **+1.642 pp/trade** (+3.40 sd) | **<0.003** | Entry adds signal |
| **Out-of-sample** | **14 names never used to design the rules** | **144** | **+0.014 pp/trade** (+0.04 sd) | **0.460** | **No edge whatsoever** |

> These figures were regenerated after fixing a higher-timeframe **lookahead bug** that
> contaminated all previously published numbers (see *Corrections* below). The in-sample figure
> barely moved; the out-of-sample edge collapsed from +0.206 pp to **+0.014 pp — 0.04 standard
> deviations, indistinguishable from random entry.**

**The in-sample edge did not survive out-of-sample.** The rules were tuned on the design basket,
so the in-sample p-value is optimistically biased. Out-of-sample the edge is **not merely
insignificant, it is ~zero**. The honest reading is:

- There is **no proven entry-timing alpha** on symbols the rules were not built on.
- The holdout was mostly low-beta defensives (JNJ, PG, KO, VZ…), while the design basket was
  high-volatility momentum names. The engine's trend/structure bias may simply be unsuited to
  defensives — a plausible explanation, but *not* a demonstrated one. Treat it as untested there.
- I deliberately did **not** retune against the holdout. Doing so would have destroyed its value
  as an honest test.

One more result worth internalising:

```
                 in-sample            out-of-sample
              engine   random       engine   random
mean/trade   +2.529%  +0.887%      +0.221%  +0.207%   <-- OOS: identical to random
win rate       49.3%    55.3%        34.7%    48.3%   <-- engine wins LESS often, both times
```

**The engine wins less often than random entry in both baskets.** In-sample it compensates with
larger wins. Out-of-sample it does not: the mean matches random almost exactly (+0.221% vs
+0.207%) while the win rate is 13.6 points *worse*. The median trade is **negative in both
baskets** — any positive mean is carried by a small minority of large winners.

Reproduce any of this yourself:

```bash
cd python
pip install -r requirements.txt
python test_no_lookahead.py        # regression guard: HTF must not leak future data
python validate.py                 # per-symbol signal stats vs baseline
python randomization_test.py 400   # in-sample: engine vs random entries
python holdout_test.py 300         # out-of-sample holdout
```

---

## What it does

Most indicators fire constantly. This one is built to stay quiet, because the research behind it
found that most chart-level "signals" are indistinguishable from noise.

Three findings drove the design:

**1. Levels sit inside the noise.** Across the study, typical chart levels — necklines, range
boundaries, fib retracements — sat only **0.6–0.8σ** of the 21-bar forecast distribution away
from price. At that distance they carry little information.
→ *The engine refuses to signal unless the target clears a volatility noise floor.* This is the
primary gate, and it blocks roughly **8% of all bars** on its own.

**2. Single indicators predict ~nothing.** Classic indicator states predicted 21-day forward
returns within ±2 points of their own unconditional baseline. A five-factor regression explained
**~3% of forward variance**, with 90% prediction intervals 12–35× wider than the point forecast.
→ *No single indicator can trigger a signal. Confluence across ten weighted factors is required.*

**3. The retest is where the information is.** After a breakout, whether the retest held was by
far the strongest conditioning event measured (n = 1,150 patterns):

| Condition | Target reached |
|---|---|
| Retest **held** | **61.7%** |
| Retest failed | 12.2% |
| No false breakout | 69.2% |
| False breakout occurred | 18.3% |

→ *Breakout signals are withheld until the retest resolves.*

## Signal frequency

**~0.3% of bars — roughly one signal per 300 bars, or about one per year per symbol.**
"NO SIGNAL" is the normal state. The dashboard always names the gate that is blocking, so you
can see *why* it is quiet rather than guessing.

## Installation (TradingView)

1. Open TradingView → **Pine Editor**
2. Paste the contents of [`pine/confluence_signal_engine.pine`](pine/confluence_signal_engine.pine)
3. **Save**, then **Add to chart**

Works on any symbol and any timeframe. Designed and tested on **daily** bars; on intraday charts
the higher-timeframe reference switches automatically (15m and below → 4H, above → D).

## Reading the overlay

| Element | Meaning |
|---|---|
| Green / red lines | Nearest adaptive support / resistance (from confirmed pivots) |
| Purple band | **Noise floor** — targets inside this band are rejected as un-tradeable |
| Yellow line | Active pattern neckline |
| Red background | High-volatility suppression (no signals) |
| BUY / SELL labels | All gates cleared |
| Orange × | Exit fired |

The dashboard shows regime, confluence score, structure, HTF trend, momentum, volume,
volatility, 21-bar σ, level distances **in σ units**, R:R, pattern state, and the blocking gate.

## The gates

A signal requires **all** of these:

1. **Noise floor** — target ≥ `noiseMult` × 21-bar σ away *(primary gate)*
2. **Reward:risk** ≥ 1.5, with the stop never tighter than 1 ATR
3. **Confluence score** ≥ threshold (45 long / 55 short — shorts are stricter because downside
   range breaks failed 61.8% of the time in testing)
4. **Volatility regime** — suppressed above the 90th HV percentile
5. **Volume confirmation** — relative volume ≥ 1.0 or OBV agreeing
6. **A qualifying setup** — breakout-with-held-retest, range low, uptrend pullback, or mean reclaim
7. **Cooldown** since the last signal

## Tuning

| Want | Change |
|---|---|
| Fewer, higher-conviction signals | Raise score threshold; raise noise floor to 1.5–2.0 |
| More signals | Lower noise floor to 0.5; lower score threshold |
| Trend-following bias | Raise min R:R, raise score threshold |
| Mean-reversion bias | Lower score threshold, reduce range-width limit |

## Repository layout

```
pine/confluence_signal_engine.pine   the TradingView indicator (the deliverable)
python/cse/engine.py                 bar-for-bar Python mirror of the Pine logic
python/validate.py                   signal stats vs per-symbol baselines
python/randomization_test.py         engine entries vs random entries
python/holdout_test.py               out-of-sample check on unseen symbols
docs/METHODOLOGY.md                  the research the rules came from
```

`engine.py` mirrors the Pine logic bar-for-bar so the rules can be backtested (Pine cannot be
tested outside TradingView). **If you change one, change the other.**

## Corrections

**2026-08-15 — higher-timeframe lookahead (fixed).** Yahoo stamps an HTF bar at the *start* of its
period, so a weekly bar dated Monday carries Friday's close. The original merge offset that
timestamp by 1 second, which lands *inside* the bar: every Tuesday-to-Friday daily bar could read
its own week's Friday close — up to three days of future data. It fed `c_htf` (weight 2.0,
tied-highest) and `uptrend_ctx`, which gates two of the four entry setups.

Fixed by mapping each HTF bar to its **successor's timestamp**, so a bar becomes available only
once complete — matching Pine's `request.security(..., close[1], lookahead_off)`, which was
already correct. `python/test_no_lookahead.py` guards the regression, including the exact
failing case. All validation numbers above were regenerated.

**Open issues.** An audit found further defects that are *not yet fixed* and that still affect the
numbers above. Do not treat the current figures as final:

1. Backtest fills are asymmetric — targets fill on the intrabar high, stops only on the close,
   which inflates returns.
2. The retest gate (`low <= neckline * 1.015`) is satisfied ~73% of the time within one bar of the
   breakout, so the engine largely signals on the breakout itself. **The headline design
   principle is not meaningfully implemented.**
3. An armed double-bottom never expires, so after a rally past a stale target the engine can stop
   signalling permanently.
4. `_clip()` returns the upper bound for NaN input, so a NaN score becomes 100 (maximum bullish).
5. The weekly partial-bar guard never fires (7-day stamp gap vs a `< 5` day test).
6. CL=F's negative-price row is deleted rather than masked — the exact splice artifact
   `docs/METHODOLOGY.md` warns against.
7. The randomization test gives real and random entries different maximum holding windows, and
   random entries can inherit an open position's target — both bias the comparison toward the
   engine.
8. Pine only: the short path's target/stop lack the long side's noise-clearing and 1-ATR fixes,
   position reversals emit no exit, the double-top detector lacks the double-bottom's pair-wise
   matching and staleness expiry, and the EXIT marker fires one bar late.

## Known limitations

- **No demonstrated out-of-sample entry edge.** See above. Use it as a discipline framework —
  it enforces volatility-aware targets, R:R minimums, structural stops, and regime awareness —
  rather than as a source of alpha.
- **Small samples.** 134 in-sample and 144 out-of-sample trades. Both are too small for strong
  conclusions in either direction.
- **Backtests exclude commissions, slippage, and spread**, which would reduce every result.
- **Bull-market window.** The 10-year study period was mostly a bull market; random entries alone
  returned +0.96%/trade. Bearish regimes are under-represented.
- **Pivot lag.** Structure confirms `pivLen` bars late by construction. This is inherent to pivot
  detection, not a bug, but it means levels appear after the fact.
- **Not compiled in CI.** The Pine file was written and hand-reviewed but not compiled — Pine only
  compiles inside TradingView. Report any compile error and it will be fixed.
- Yahoo Finance data has known defects (spurious partial weekly bars, occasional duplicated
  volume, and WTI's negative 2020-04-20 print). `engine.py` handles the first; see
  `docs/METHODOLOGY.md` for the rest.
