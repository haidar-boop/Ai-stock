# Wide Test — Pre-Registration

**Written and committed BEFORE the test was run.** Every threshold below was fixed in advance so
the verdict cannot be chosen after seeing the numbers. That discipline is the only reason any of
this project's earlier findings are trustworthy — the retest gate looked convincing precisely
because nobody had pre-declared what "convincing" meant.

Commit this file, *then* run `python/wide_test.py`.

---

## 1. The question

Every result so far rests on **182 out-of-sample trades**. At the observed variance that test can
only detect an edge larger than roughly **0.5 percentage points per trade**. Anything smaller is
invisible to it — so "no edge found" currently means *"no large edge found"*, not *"no edge"*.

**Question:** on a universe far wider than the one it was designed on, does the engine's entry
selection produce a higher mean return per trade than random entry under identical exit rules?

## 2. Universe

- **~320 US equities across all 11 GICS sectors**, plus a small set of index/sector ETFs.
- **25 years** of daily bars (or the symbol's full history if shorter).
- **The 22 design-basket symbols are excluded outright.** They are contaminated — the rules were
  tuned on them.
- The 14 symbols used in the earlier holdout are **included but tagged**, so the pooled result can
  be reported with and without them. They were never tuned on, but their result has been seen.
- Minimum **1,500 daily bars** to be included; symbols with less history are reported as skipped.

## 3. Method

Identical to `randomization_test.py`, unchanged:

- Engine entries vs. random entries, **same exit rules, same trade counts, same eligibility**.
- Trade geometry from the engine's per-bar `plan_stop` / `plan_target`.
- Symmetric intrabar barriers, adverse-first, gap-aware fills.
- 2,000 randomization iterations (up from 400, since the pooled sample is much larger).

**Primary metric:** `edge = mean(engine trade return) − mean(random trade return)`, in percentage
points per trade, with a p-value from the randomization distribution.

## 4. Success criteria — fixed in advance

| Outcome | Condition | Verdict |
|---|---|---|
| **A. Real edge** | p < 0.01 **and** edge ≥ +0.10 pp/trade | Entry selection carries information |
| **B. No edge** | p ≥ 0.05 | Entry selection is worthless; stop building on it |
| **C. Inconclusive** | 0.01 ≤ p < 0.05, or p < 0.01 with edge < +0.10 pp | Statistically detectable, economically trivial — treat as no edge for practical purposes |

Both conditions must hold for outcome A. A tiny edge that is statistically significant only
because the sample is huge is **not** a tradeable edge, and will be reported as such.

## 5. Secondary breakdowns — EXPLORATORY ONLY

The pooled result above is the **only confirmatory test**. The following are reported for
hypothesis generation and are explicitly **not** evidence on their own, because slicing a null
result enough ways will always produce a "significant" subgroup:

- by **sector** (11 groups)
- by **volatility bucket** (symbol annualised volatility, quartiles)
- by **era** (2000–2008, 2009–2015, 2016–2020, 2021–present)
- by **entry regime** as classified by the engine

Any subgroup that looks promising is a **candidate for a future pre-registered test on fresh
data**, not a finding. Reporting one as a finding would repeat exactly the error that produced the
retest gate.

## 6. Known biases, stated in advance

- **Survivorship.** The universe is built from symbols that exist today. This inflates absolute
  returns for *both* arms. The paired design largely controls it for the *relative* comparison —
  engine and random draw from the identical bars of the identical symbols — but the absolute
  return figures should not be read as achievable.
- **No transaction costs, slippage, or spread.** All figures are gross. At ~1 signal per symbol
  per year this is small, but it is not zero, and it only ever makes results worse.
- **Era.** 2000–2026 contains two major crashes and a long bull market, which is better balance
  than the earlier 10-year window, but it is still one sample of history.
- **Yahoo data defects** as documented in `METHODOLOGY.md` §7.

## 7. What each outcome will change

- **A (real edge):** proceed to the 63-day horizon test, then consider paid data sources.
- **B (no edge):** stop developing the entry logic. The tool is a risk filter, that is all it will
  ever be, and the README will say so without hedging.
- **C (inconclusive):** same practical action as B, but the door stays open for a future test with
  genuinely new information rather than more price-derived indicators.

**I commit to reporting whichever outcome occurs, including B.**
