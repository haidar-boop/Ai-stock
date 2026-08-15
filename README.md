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
| In-sample | Tech / energy (the design basket) | 173 | **+1.929 pp/trade** (+3.81 sd) | **<0.003** | Entry adds signal |
| **Out-of-sample** | **14 names never used to design the rules** | **182** | **−0.074 pp/trade** (−0.24 sd) | **0.597** | **Slightly worse than random** |

> Regenerated after six rounds of correctness fixes (see *Corrections*). The out-of-sample figure
> after each round: **+0.206 → +0.014 → +0.245 → +0.069 → −0.057 → −0.074 pp/trade**. It has
> crossed zero and sits **slightly below random entry**. Every reading is inside noise and the
> swing between them exceeds the quantity being measured, so the defensible summary is simply:
> **on symbols the rules were not built on, this engine's entry timing is worth nothing.** Six
> rounds of fixing — including deleting the design's own headline principle — did not change it.

**The in-sample edge did not survive out-of-sample.** The rules were tuned on the design basket,
so the in-sample p-value is optimistically biased. Out-of-sample the engine now returns **less
than random entry** (+0.240% vs +0.296% per trade). The honest reading is:

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
mean/trade   +2.738%  +1.189%      +0.240%  +0.296%   <-- OOS: BELOW random
win rate       45.2%    49.9%        29.8%    43.6%   <-- engine wins LESS often, both times
```

**The engine wins less often than random entry in both baskets** — by 4.7 and 13.8 points. It is
a low-hit-rate, large-win profile, and the trade ledger shows exactly that:

| Exit reason | n | Median | Mean |
|---|---|---|---|
| target | 52 | **+10.27%** | +11.21% |
| stop | 69 | −2.44% | −3.33% |
| degraded (score collapsed) | 28 | −1.21% | −0.61% |
| extended (stretched, volume fading) | 7 | +3.53% | +3.63% |

**The median trade is negative in both baskets** — 44% of trades stop out and the mean is carried
entirely by the 33% that reach target. In the design basket that arithmetic comes out positive; on
unseen symbols it does not. If you cannot sit through a sub-50% hit rate, this tool will feel
broken while working as designed.

Reproduce any of this yourself:

```bash
cd python
pip install -r requirements.txt
python test_no_lookahead.py        # regression guard: HTF must not leak future data
python test_data_layer.py          # regression guard: data-handling correctness
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

**3. The retest finding did not survive scrutiny — and the gate built on it was removed.**
Earlier versions withheld breakout signals until "the retest held", citing 61.7% vs 12.2%
target-reach rates. Decomposing that statistic (n = 1,150, reproduce with
`python/research_retest_decomposition.py`) showed it does not mean what it appeared to:

| Clause | Fires | P(target) when true | when false | Spread |
|---|---|---|---|---|
| retest clause alone | **94.1%** of patterns | 0.336 | 0.897 | **−0.561** |
| "never closed 2% below neckline in 15 bars" | 55.9% | 0.647 | 0.018 | **+0.629** |
| published combination | 50.0% | 0.617 | 0.122 | +0.496 |
| a *stricter*, genuine retest | 51.6% | 0.304 | 0.440 | **−0.136** |

Three problems. The retest clause **fires on 94% of patterns with a median lag of one bar** — a
breakout closes just above the neckline, so the next bar's low is almost always within 1.5% of it.
On its own it is **negatively** associated with success. And the entire discrimination came from
the no-fail clause, which is close to a **restatement of the outcome being predicted**: "target
first" is *defined* as reaching target before a 2% neckline break, so conditioning on "no 2% break
in 15 bars" is largely circular. A stricter, genuine retest (move away, return, re-close above)
tested *worse* than no filter at all.

→ *The retest gate was removed.* Pattern state is still displayed, but not traded on. What
remains is the causal validity condition: the breakout has not broken down as of this bar.

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
6. **A qualifying setup** — un-failed breakout, range low, uptrend pullback, or mean reclaim
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
python/test_no_lookahead.py          regression guard: no HTF future data
python/test_data_layer.py            regression guard: data-handling correctness
python/lint_pine.py                  static checks for the Pine file (it cannot be compiled here)
python/research_retest_decomposition.py  evidence that retracted the retest gate
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

**2026-08-15 — data-layer defects (fixed).** Five correctness bugs in data handling, guarded by
`python/test_data_layer.py`:

- `_clip()` returned the **upper bound** for NaN input (`min(1, nan)` is `1` in Python), so a NaN
  confluence score became **+100** and cleared the long threshold unconditionally. NaN now
  propagates, and RSI's zero-average-loss case is defined (100) rather than left NaN.
- The weekly partial-bar guard **never fired**: Yahoo stamps bars at period start, so the
  still-forming bar sits a full 7 days after its predecessor and a `< 5` day gap test cannot see
  it. Now tested against the bar's **final session** (Friday), which also avoids discarding a
  completed week over the weekend. The off-cycle-duplicate case is still caught separately.
- CL=F's negative-price row (**−$37.63, 2020-04-20**) was **deleted**, splicing two non-adjacent
  bars into one fabricated return — the exact artifact `docs/METHODOLOGY.md` warns against. The
  row is now retained and the affected *returns* are masked as undefined. Max |log return| in the
  series dropped to 0.320.
- A single missing volume poisoned **OBV for the entire remaining series** via `cumsum`, and
  blanked 39 bars of relative volume. Volume is now coerced and zero-filled for OBV, with
  tolerant `min_periods` on the rolling averages.
- Pine divergence: `relVol` defaulted to `1.0` when the volume average was unusable, which
  **passed** the volume gate, while Python's NaN blocked it. Pine now uses `na` and can only pass
  that gate via OBV agreement — the conservative reading, matching Python.

EWMA variance also now carries forward across undefined returns instead of injecting a zero
return, which would have understated volatility and *loosened* the noise-floor gate precisely
where data is least trustworthy.

**2026-08-15 — asymmetric backtest fills (fixed).** Targets filled on the intrabar high while
stops only triggered on the **close**, so a bar could trade clean through the stop, recover, and
record no loss. Both barriers are now tested against intrabar extremes; when both are touched in
one bar the **stop takes precedence** (OHLC cannot resolve the order, so the adverse case is
assumed); and fills use the barrier price, or the **open** when the bar gapped past it.

Worth recording that this bug ran in **both** directions, and the net was the opposite of what I
predicted. Stops were too lenient (overstating returns), but targets triggered on the high and
then settled at the bar's *close*, systematically **understating wins**. Fixing both lowered the
win rate (49.3% → 45.9% in-sample) and *raised* the mean (+2.529% → +2.616%), because winners are
now booked at the target instead of wherever the bar happened to close.

Concrete example, AAPL 2026-07-31: the bar opened 304.81, low 300.00, closed 308.91. It gapped
straight through the stop, but `close < stop` was false, so the old code recorded **no loss at
all**. It now fills at the open.

**2026-08-15 — randomization-test bias (fixed).** The test used to validate everything else was
itself tilted toward the engine, in two ways:

- **Unequal horizons.** Real entries were only skipped within 2 bars of the series end, so late
  signals ran on truncated windows, while every random entry was guaranteed the full 60 bars. In
  an upward-drifting basket that depressed the real mean relative to random. Both paths now share
  one eligibility rule (`MIN_TAIL = 61`).
- **Inherited targets.** Random entries read the `target` column, which is only populated *while a
  trade is live* — so a random entry landing on an in-position bar (6.3% of AAPL's pool) inherited
  another trade's target, priced off a different entry. The engine now publishes `plan_stop` /
  `plan_target` on **every** bar, and both real and random entries use that same per-bar geometry.

Correcting the instrument **reduced** the measured edge, which is the expected direction: random
entries had been handicapped. The random baseline rose from +0.878% to +1.118% per trade
in-sample, and the out-of-sample edge fell from +0.245 pp back to **+0.069 pp**. This is why the
measuring tool was fixed before any further behavioural change.

**2026-08-15 — stale armed patterns (fixed).** `db_armed` never expired. `price > neckline` stays
true after any rally and the failure test needs a 2% break, so once armed the flag latched on
permanently and pinned the trade target to a measured move price had long since passed. The
planned target sat **at or below price on ~10.5% of bars — 19.1% on TSLA**, making reward negative
and failing every gate from then on: the engine could brick itself for the rest of a series.

Patterns now retire when the target is reached, when they fail, or after `db_max_hold` (126) bars,
and an armed pattern may only supply the target while that target is still *ahead* of price.
Degenerate targets went from **10.5% to 0.00%** across 7,542 bars, and signal counts rose (155
in-sample, 168 out-of-sample) because the engine is no longer locking itself out.

**2026-08-15 — the retest gate was removed (design principle retracted).** The gate was not just
badly implemented, the finding behind it did not hold. See *What it does → 3* above for the
decomposition: the retest clause fires on 94.1% of patterns at a median lag of one bar, is
negatively associated with success on its own (0.336 vs 0.897), and the published 61.7%/12.2%
split came entirely from a clause that restates the outcome being predicted. A stricter, genuine
retest tested worse still. The gate is gone; pattern state is displayed, not traded on.

I did **not** replace it with a new rule mined from the same data — that is how the original
overfitting happened. Removing it raised the in-sample edge to +1.929 pp/trade and left the
out-of-sample figure unchanged at ≈ zero.

**2026-08-15 — Pine parity (fixed).** The indicator's short side and exit reporting had drifted
from the long side:

- **`ta.*` inside conditionals.** The neckline used `ta.highest()` / `ta.lowest()` inside `if`/`for`
  blocks. Pine's `ta.*` functions must execute on *every* bar to maintain internal state; called
  conditionally they silently return wrong values. Both are now explicit `high[k]` / `low[k]`
  scans, which are safe anywhere.
- **Short target/stop.** The short path used the merely-*nearest* support as its target — the same
  self-defeating choice fixed on the long side, which sits ~0.2σ from price by construction and so
  could never clear the noise gate. The SELL path was effectively dead code. It now uses a
  noise-clearing target and the matching 1-ATR stop floor.
- **Double-top detector.** Now uses the same pair-wise pivot matching as the double bottom
  (consecutive-only matching missed any pattern with an intervening pivot) and the same staleness
  expiry.
- **Reversals emitted no exit.** A BUY firing while a short was open overwrote the position
  silently — no EXIT marker, no exit alert. An alert user saw a BUY with no preceding close.
- **EXIT marker fired one bar late**, because it read `exitLong[1]` *after* `posState` had already
  been reset. Both marker and alert are now un-lagged.

**Short signals are now OFF by default.** The Python mirror implements no short side, so the short
path has never been scored against random entry — every published figure here is long-only. Turning
shorts on is opting into an unvalidated signal.

`python/lint_pine.py` statically checks the error classes above (plus comma-chained declarations,
use-before-declaration, bracket balance), since Pine only compiles inside TradingView.

**Open issues.** None outstanding from the audit. The remaining known risk is that
**the Pine file has still never been compiled** — see *Known limitations*.

## Known limitations

- **No out-of-sample entry edge — the current estimate is slightly negative.** See above. Use it
  as a discipline framework (it enforces volatility-aware targets, R:R minimums, structural stops
  and regime awareness), not as a source of alpha.
- **Small samples.** 173 in-sample and 182 out-of-sample trades. Both are too small for strong
  conclusions in either direction.
- **Backtests exclude commissions, slippage, and spread**, which would reduce every result.
- **Bull-market window.** The 10-year study period was mostly a bull market; random entries alone
  returned +0.96%/trade. Bearish regimes are under-represented.
- **Pivot lag.** Structure confirms `pivLen` bars late by construction. This is inherent to pivot
  detection, not a bug, but it means levels appear after the fact.
- **Not compiled in CI.** The Pine file is hand-reviewed and passes `python/lint_pine.py`, but
  Pine only compiles inside TradingView, so it has never been run. This is the largest unretired
  risk in the repository. Report any compile error and it will be fixed.
- **The short path is unvalidated** and disabled by default. All published figures are long-only.
- Yahoo Finance data has known defects (spurious partial weekly bars, occasional duplicated
  volume, missing volume, and WTI's negative 2020-04-20 print). All of these are now handled in
  `engine.py` and pinned by `python/test_data_layer.py`; see `docs/METHODOLOGY.md` for detail.
