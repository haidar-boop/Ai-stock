# Short-Side Test — Results

Run against [`SHORT_TEST_PREREGISTRATION.md`](SHORT_TEST_PREREGISTRATION.md), committed before
the test was executed.

Reproduce: `cd python && python wide_test.py collect && python wide_test.py analyze 2000`

---

## Result

**294 symbols · 25 years · 955 short signals across 279 symbols**

| | Engine shorts | Random shorts | Edge |
|---|---|---|---|
| Mean per trade | **−0.711%** | −0.329% | **−0.382 pp** (−2.22 sd) |
| Excl. prior holdout | −0.675% | −0.335% | −0.341 pp (−1.88 sd) |
| **Win rate** | **20.3%** | 39.6% | −19.3 points |

**p = 0.9845** — in 98.45% of random draws, randomly chosen shorts did *better* than the engine's.

### PRE-REGISTERED VERDICT: **B — NO EDGE** (p ≥ 0.05)

The prediction recorded in advance was outcome B. That is what happened.

## It is not merely "no edge" — the point estimate is negative

Both arms lose money on average, exactly as pre-registered (equities drift up, so shorting anything
at random loses ~0.33% per trade). That was expected and is not the finding.

The finding is that **the engine's shorts lose roughly twice as much as random shorts**, and only
**one short signal in five is profitable** versus two in five for random entry.

A symbol-level check confirms this is broad rather than a few blowups:

| | |
|---|---|
| Symbols with ≥3 short signals | 178 |
| Engine short worse than that symbol's own random short | **104 (58%)** |
| Engine short better | 74 (42%) |
| Median per-symbol difference | **−0.610 pp** |
| Sign test, two-sided | p = 0.029 |

**Honesty note on statistics:** the pre-registered test was one-sided — *does the engine beat
random?* It does not. The additional claim that it is *significantly worse* was **not**
pre-registered, so the −2.22 sd and the sign test p = 0.029 are post-hoc observations. They
corroborate each other and point the same way, but they carry less weight than a pre-registered
result and should not be quoted as though they were one.

## Why this might happen — hypothesis, not finding

The engine shorts breakdowns, downtrend rallies and range highs. In a market with persistent
upward drift, those are disproportionately the moments most prone to sharp reversal — capitulation
lows, squeezes, mean reversion after a flush. Random shorts are spread across all conditions and
so avoid selecting for that.

That is a plausible mechanism, **not** a demonstrated one. Testing it would need its own
pre-registration.

## Decision

Per the pre-registration, outcome B means short signals **stay disabled by default**. Their label
changes from *"unvalidated"* to *"measured, and worse than random"* — a materially different and
stronger warning.

They remain available as an explicit opt-in only because removing working code would make the
result harder to reproduce. **There is no defensible reason to trade them.**

## Risk disclosure (required by the pre-registration regardless of outcome)

Shorting carries risks the long side does not, none of which this backtest models:

- **Theoretically unlimited loss** — a short has no floor.
- **Borrow costs and availability** — shares can be recalled, forcing a close at the worst time.
- **Margin calls** — an adverse move can force liquidation before any thesis plays out.
- **Short squeezes** — the exact reversal dynamic the results above are consistent with.

The backtest assumes free, always-available borrow and no margin constraints. Real short results
would be **worse** than the already-poor figures above.
