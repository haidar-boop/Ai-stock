# Wide Test — Results

Run against the criteria fixed in [`WIDE_TEST_PREREGISTRATION.md`](WIDE_TEST_PREREGISTRATION.md),
which was committed before the test was executed (commit `dcac998`).

Reproduce: `cd python && python wide_test.py collect && python wide_test.py analyze 2000`

---

## Scale

| | Earlier holdout | **This test** |
|---|---|---|
| Symbols | 14 | **294** |
| History | 10 years | **25 years** |
| Trades | 182 | **10,213** |
| Smallest detectable edge (~2sd) | ~0.5 pp/trade | **0.099 pp/trade** |

The test is roughly **5× more sensitive** than anything run before. An edge that was previously
invisible would now show up.

## Primary result — confirmatory

| Sample | n | Engine | Random | Edge | p |
|---|---|---|---|---|---|
| All symbols | 10,213 | +0.391% | +0.343% | **+0.048 pp** (+0.97sd) | **0.1675** |
| Excluding prior holdout | 9,677 | +0.411% | +0.348% | **+0.063 pp** (+1.19sd) | **0.1230** |

### PRE-REGISTERED VERDICT: **B — NO EDGE** (p ≥ 0.05)

95% confidence interval on the edge: roughly **−0.05 to +0.15 pp/trade** — it contains zero.

The point estimate is mildly positive and has been positive in most runs, but it is not
distinguishable from chance, and **it is far too small to matter even if real**. At ~1 signal per
symbol per year, +0.05 pp per trade is nothing. Transaction costs, which are excluded here, would
consume it several times over.

**This is the outcome the pre-registration committed to reporting.** The earlier "no edge" results
could be dismissed as an underpowered test. This one cannot: with 10,213 trades we can now rule
out any edge larger than about 0.1 pp/trade, and none is there.

## A structural fact that is now solid

| | Engine | Random |
|---|---|---|
| Win rate | **32.5%** | 44.2% |
| Mean per trade | +0.391% | +0.343% |

Across 10,213 trades the engine **wins 11.7 points less often than random entry** and arrives at
the same mean through rarer, larger wins. At this sample size that is no longer noise — it is a
real, reproducible property of the exit rules (tight structural stops, distant noise-clearing
targets), not of the entry logic.

Practical consequence: **two thirds of signals lose money.** Anyone trading this needs to sit
through long losing streaks for an expectancy that is, on unseen symbols, indistinguishable from
random.

## Secondary breakdowns — EXPLORATORY, NOT EVIDENCE

Declared exploratory in advance. **20 subgroup tests were run.** At p < 0.05 roughly one false
positive is expected by chance alone; the Bonferroni-corrected threshold is **p < 0.0025**.

### By sector

| Sector | n | Edge | p |
|---|---|---|---|
| **RealEstate** | 761 | **+0.407 pp** (+2.38sd) | **0.0100** |
| Communication | 372 | +0.363 pp | 0.1175 |
| Energy | 478 | +0.165 pp | 0.2650 |
| Discretionary | 944 | +0.131 pp | 0.2225 |
| Healthcare | 1,107 | +0.087 pp | 0.2900 |
| Industrials | 1,160 | +0.086 pp | 0.2475 |
| Financials | 1,231 | +0.080 pp | 0.2800 |
| Utilities | 835 | +0.022 pp | 0.4325 |
| ETF | 755 | −0.014 pp | 0.5525 |
| Materials | 681 | −0.101 pp | 0.7075 |
| Staples | 890 | −0.173 pp | 0.9350 |
| **Technology** | 999 | **−0.215 pp** | 0.8600 |

Real Estate is the standout — and it **does not survive multiple-comparison correction**
(0.0100 > 0.0025). Note also that Technology, the sector family the rules were *designed* on, is
the second-worst performer. That is a useful corrective to any story about where this works.

### By symbol volatility

| Bucket | n | Edge | p |
|---|---|---|---|
| Q1 vol <26% | 2,944 | −0.039 pp | 0.7600 |
| Q2 26–32% | 2,515 | +0.079 pp | 0.2000 |
| Q3 32–39% | 2,435 | +0.082 pp | 0.2325 |
| Q4 vol >39% | 2,319 | +0.121 pp | 0.1750 |

Monotonic and in the direction the earlier holdout hinted at (worse on low-beta defensives, better
on high-volatility names). **No bucket is individually significant**, but the ordering is at least
consistent rather than random-looking. Weakest possible form of encouragement.

### By era

| Era | n | Edge | p |
|---|---|---|---|
| **2000–2008** | 2,352 | **+0.290 pp** (+2.66sd) | **0.0025** |
| 2009–2015 | 3,404 | −0.079 pp | 0.8325 |
| 2016–2020 | 2,260 | −0.030 pp | 0.6000 |
| 2021–2026 | 2,197 | +0.066 pp | 0.2750 |

The 2000–2008 window sits exactly *at* the Bonferroni threshold — the single most interesting
number in the run, and still not enough to call a finding out of 20 tests. It covers the dot-com
unwind and the 2008 crisis, so a plausible mechanism exists (volatility gating and structural
stops helping most when volatility is extreme and trends are violent). **That is a hypothesis, not
a result.** Testing it properly requires a fresh pre-registration and data this run has not
already seen.

## What this changes

Per the pre-registration, outcome B means: **stop developing the entry logic.**

- No further tuning of entry rules on price-derived indicators. Six rounds of fixes plus this test
  is sufficient evidence that there is nothing to find there.
- The 63-day horizon test is **not** worth running as an entry-improvement exercise. It was
  conditional on outcome A.
- Paid data sources are not justified by anything measured here.
- The tool's honest description is a **risk filter**: it enforces volatility-aware targets, R:R
  minimums, structural stops and regime awareness, and refuses ~99.7% of bars. That part is
  deterministic arithmetic and works as specified. The entry timing is not an edge and should not
  be presented as one.

The one live question worth a future test is the **high-volatility / crisis-era pattern**, and
only under fresh pre-registration.
