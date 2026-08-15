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
| In-sample | Tech / energy (the design basket) | 136 | **+1.720 pp/trade** (+3.62 sd) | **0.003** | Entry adds signal |
| **Out-of-sample** | **14 names never used to design the rules** | **148** | **+0.206 pp/trade** (+0.66 sd) | **0.257** | **No demonstrable edge** |

**The in-sample edge did not survive out-of-sample.** The rules were tuned on the design basket,
so the p = 0.003 is optimistically biased. The out-of-sample edge points the same direction but is
not statistically distinguishable from luck. The honest reading is:

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
mean/trade   +2.681%  +0.961%      +0.578%  +0.372%
win rate       50.0%    56.0%        37.2%    49.7%   <-- engine wins LESS often, both times
```

**The engine wins less often than random entry and wins bigger when it wins.** That pattern is
consistent across both baskets: it selects for larger-magnitude moves, not for a higher hit rate.
Median hold is ~10 bars. If you cannot sit through a sub-50% win rate, this tool will feel broken
while behaving exactly as designed — and note the median trade is *negative* in both baskets; the
mean is carried by a minority of large winners.

Reproduce any of this yourself:

```bash
cd python
pip install -r requirements.txt
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

## Known limitations

- **No demonstrated out-of-sample entry edge.** See above. Use it as a discipline framework —
  it enforces volatility-aware targets, R:R minimums, structural stops, and regime awareness —
  rather than as a source of alpha.
- **Small samples.** 136 in-sample and 148 out-of-sample trades. Both are too small for strong
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
