# Short-Side Test — Pre-Registration

**Written and committed BEFORE the test was run**, same discipline as the long-side wide test.

---

## 1. The question

Does the engine's **short** entry selection produce a better mean return per short trade than
**randomly chosen short entries** under identical exit rules?

The long side was settled by the wide test: no edge, over 10,213 trades. The short logic was never
implemented in Python and has therefore never been measured at all. It exists in the Pine file and
is disabled by default for exactly that reason.

## 2. The comparison must be short-vs-random-short

This is the critical design point. Equities drift upward: random *long* entries returned
**+0.343% per trade** in the wide test, so a random *short* over the same bars starts at roughly
**−0.34% per trade** before any skill is applied.

Comparing engine shorts against zero, or against random longs, would therefore be meaningless — it
would just re-measure market drift. **The random arm shorts the same eligible bars of the same
symbols**, so the drift headwind applies identically to both arms and cancels out of the
comparison.

A negative absolute return for the engine's shorts is expected and is **not** evidence of failure.
The question is only whether the engine's shorts are better than random shorts.

## 3. Universe and method

- Identical universe to the long wide test: **294 symbols, 25 years, all 11 GICS sectors**, design
  basket excluded, prior holdout tagged.
- Short entry outcome: `(entry − exit) / entry × 100`.
- Exit rules are the exact mirror of the long side: symmetric intrabar barriers, **stop takes
  precedence** when both are touched in one bar, gap-aware fills, 60-bar time stop.
- Short signal threshold is `-55` versus the long side's `+45` — deliberately stricter, because
  downside range breaks failed 61.8% of the time in the earlier pattern study.
- 2,000 randomization iterations.

**Expected sample: ~1,000 short signals** (measured at ~0.11 shorts per long on a 10-symbol probe).
That is ~10× smaller than the long test, so the smallest detectable edge will be roughly
**0.3 pp/trade** rather than 0.1. This is stated in advance; the achieved figure will be reported.

## 4. Success criteria — fixed in advance

| Outcome | Condition | Verdict |
|---|---|---|
| **A. Real edge** | p < 0.01 **and** edge ≥ +0.10 pp/trade | Short selection carries information |
| **B. No edge** | p ≥ 0.05 | Short selection is worthless |
| **C. Inconclusive** | 0.01 ≤ p < 0.05, or p < 0.01 with edge < +0.10 pp | Not tradeable |

## 5. Prediction, recorded in advance

**I expect outcome B.** Stated so it cannot be claimed after the fact:

1. The long side, built on the same machinery, has no edge across 10,213 trades.
2. Downside breaks failed 61.8% of the time in the pattern study — the raw material is worse.
3. The short side was never validated during development, so it has had none of the
   bug-finding scrutiny the long side received.

If the result contradicts this prediction, that is a genuinely interesting finding and will be
treated as a candidate for further testing — **not** as a green light to trade.

## 6. Additional risk disclosure required regardless of outcome

Whatever the test shows, the shipped tool must state plainly that shorting carries risks the long
side does not: **theoretically unlimited loss**, borrow costs and availability, margin calls, and
short-squeeze dynamics. A backtest models none of these. Even outcome A would not make an
unhedged short signal safe to follow mechanically.

## 7. Default setting

Short signals stay **disabled by default** unless outcome A is achieved. If outcome B or C, they
remain available as an explicit opt-in, labelled as measured-and-found-worthless rather than
merely untested.

**I commit to reporting whichever outcome occurs.**
