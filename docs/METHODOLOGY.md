# Methodology

The rules in `pine/confluence_signal_engine.pine` were not chosen by convention. Each one traces
to a measurement. This documents those measurements, including the ones that argue against the
tool.

Data: Yahoo Finance daily OHLCV, 10–15 years, 22-symbol basket (mega-cap tech, semis, energy,
SPY/QQQ), plus multi-timeframe series (weekly / daily / 4H / 1H / 15m) for the instrument study.

## 1. Return-series character

Variance ratios (Lo–MacKinlay) on 10y daily log returns:

| Symbol | AC(1) | VR(5) | z-stat | Excess kurtosis | Ann. vol |
|---|---|---|---|---|---|
| NVDA | −0.081 | 0.844 | **−6.19** | 6.31 | 48.3% |
| AAPL | −0.056 | 0.933 | −2.67 | 5.09 | 27.4% |
| CL=F | +0.013 | 0.886 | −4.53 | 4.69 | 37.3% |
| USO  | +0.050 | **1.095** | **+3.77** | 3.10 | 34.0% |

- **Autocorrelation is dead everywhere** (no lag exceeds |0.081|). Nothing in the engine relies on
  day-to-day serial dependence.
- **VR < 1 = mean-reverting.** NVDA reverts strongly at weekly horizons. This is why the engine
  *penalises* stretched entries (|Z| > 1.5) rather than treating them as momentum.
- **CL=F and USO have opposite persistence** — front-month crude reverts, the ETF trends, because
  roll carry adds a smooth drift component. They are not interchangeable instruments.
- **All are fat-tailed** (excess kurtosis 3.1–6.3). Gaussian risk models understate tail risk;
  the Monte Carlo work bootstraps actual returns instead.

## 2. Why confluence is mandatory

Multivariate OLS of 21-day forward return on five standardized state features
(Z-score, RSI, signed ADX, Bollinger-width percentile, HV percentile), n ≈ 2,200 per symbol:

| Symbol | R² | 21d point forecast | 90% prediction interval |
|---|---|---|---|
| NVDA | 0.0272 | +3.64% | [−19.1%, +26.4%] |
| AAPL | 0.0340 | +0.77% | [−12.6%, +14.1%] |
| CL=F | 0.0253 | +2.39% | [−22.5%, +27.3%] |
| USO  | 0.0300 | +3.08% | [−16.6%, +22.8%] |

Current technical state explains **~3% of forward variance**. F-tests are "significant" only
because n is large; the effect is economically negligible and every point forecast is dwarfed by
its own error bar. **No single factor may fire a signal.**

A cross-asset detail: the HV-percentile coefficient is **negative for NVDA (t = −6.0)** but
**positive for CL=F (t = +5.9)**. Equity volatility is punished; commodity volatility is
compensated. The engine's volatility penalty is therefore calibrated for equities.

## 3. Why the noise floor is the primary gate

GARCH(1,1) fitted by maximum likelihood:

| Symbol | α+β | Shock half-life | 21-bar 1σ move |
|---|---|---|---|
| NVDA | 0.9212 | 8.4 days | **±13.41%** |
| AAPL | 0.9604 | 17.2 days | ±8.31% |
| CL=F | **0.9800** | **34.3 days** | ±13.99% |

Measured against the distance to each instrument's own key levels:

| Symbol | Structure spans | In σ |
|---|---|---|
| NVDA | 214.39 → 232.28 | **0.60σ** |
| AAPL | 300.00 → 316.29 | **0.64σ** |
| CL=F | 77.78 → 87.07 | **0.81σ** |

**Every key level across three instruments and five timeframes sat inside a single standard
deviation of the 21-day forecast distribution.** A target that close is not a target. Hence
GATE 1: the target must clear `noiseMult` × 21-bar σ, or no signal is issued.

The engine uses **RiskMetrics EWMA (λ = 0.94)** as the live proxy for this, since Pine cannot fit
GARCH per bar. It tracks the same conditional-variance dynamic closely enough for gating.

## 4. Why the retest decides everything

A pattern detector was run over 15 years × 22 symbols, yielding **1,150 double bottoms**:

| Metric | Value |
|---|---|
| P(measured target before failure) | 0.370 |
| **P(false breakout ≤10 bars)** | **0.633** |
| P(retest occurs within 15 bars) | 0.941 |

Conditioning changes the picture completely:

| Condition | n | P(target first) | Median 21d |
|---|---|---|---|
| Retest **held** | 575 | **0.617** | **+3.23%** |
| Retest failed | 575 | 0.122 | −2.67% |
| No false breakout | 422 | **0.692** | **+3.87%** |
| False breakout | 728 | 0.183 | −1.02% |

This is the single strongest conditioning event found anywhere in the study, and it is why the
engine tracks breakout → retest → hold/fail as an explicit state machine rather than signalling
on the breakout bar.

**Symbol-specific caution:** NVDA's own double-bottom history is the worst in the basket
(P(target) = 0.200; 0.300 with a volatility-scaled failure buffer; median 21d **−1.35%**, the only
negative in the group). Higher-volatility names TSLA and AMD scored 0.531 and 0.514, so
volatility does not explain it. Pattern statistics do not transfer uniformly across symbols.

## 5. Why shorts are stricter

2,171 range breakouts:

| Direction | n | P(false breakout ≤5 bars) | Median 21d | P(up 21d) |
|---|---|---|---|---|
| **Down** | 870 | **0.618** | **+2.00%** | **0.603** |
| Up | 1,301 | 0.516 | +1.39% | 0.588 |

**Downside breaks reverse more often than they follow through** — the unconditional median 21-day
return after a *downside* break is positive. Hence the higher short threshold (55 vs 45).

## 6. Why the stop is never tighter than 1 ATR

An order-aware barrier race (first-passage logic, with bootstrapped intraday high/low excursions)
showed that higher nominal R:R comes with proportionally lower win rates:

| Trade | R:R | Breakeven P | Actual P(win) | EV |
|---|---|---|---|---|
| NVDA long, tgt 238.98 | 1.19:1 | 0.458 | 0.433 | −0.10% |
| NVDA long, tgt 232.28 | 0.61:1 | 0.621 | 0.607 | +0.01% |
| NVDA pullback, tight stop | **3.28:1** | 0.233 | **0.180** | **−0.60%** |

The best-looking R:R had the worst expected value. A stop tighter than 1 ATR is triggered by noise
and manufactures a fake edge, so the engine floors it.

Nearly every trade's EV sign flipped depending on the assumed drift. **The apparent edge in
historical data was mostly embedded drift, not pattern recognition.**

## 7. Data defects encountered

Documented because they silently corrupt results:

- **Spurious trailing weekly bar.** Yahoo appends a partial bar duplicating the last daily bar,
  corrupting weekly RSI/MACD/ATR. Handled in `engine.py` — note the guard must test whether the
  bar's **final session** has passed, not the inter-bar gap: bars are stamped at period start, so
  a still-forming weekly bar is a full 7 days after its predecessor and a gap test never sees it.
- **WTI negative price.** CL=F closed at **−$37.63 on 2020-04-20**. Log returns are undefined;
  this produced a `nan` Hurst exponent and inflated kurtosis to 23.26 (4.69 once corrected).
- **Splice artifact.** Deleting a date range to exclude that episode creates a spurious jump
  return. Correct approach: *mask* affected returns, don't delete rows. (`engine.py` originally
  did the wrong thing here despite this warning; it now retains the row and masks the returns.)
- **Duplicated volume.** CL=F occasionally repeats the prior bar's volume as a placeholder.
- **Missing volume.** Null volume bars appear across symbols. A single NaN inside a `cumsum`
  propagates to every subsequent bar, so OBV must zero-fill rather than inherit NaN.

## 8. Known biases in all of the above

- **Basket drift.** Unconditional P(up, 21d) across detected breakouts was **0.594**, not 0.50.
  Subtract ~9 points from any bullish-looking probability here.
- **Survivorship.** All basket symbols are still listed and liquid.
- **Regime.** The 10–15 year window was mostly a bull market.
- **Threshold sensitivity.** The "pattern failure" definition (a close 2% below the neckline) is
  arbitrary and volatility-dependent; a 1×ATR buffer was tested as a robustness check and changed
  individual symbol results materially.
- **Design contamination.** The gates were tuned on the design basket. This is exactly why the
  out-of-sample holdout in the README matters more than the in-sample result.
