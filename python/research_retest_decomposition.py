"""
Decompose the 'retest held' finding.

The engine's headline design principle cites: retest held -> target reached
61.7%, retest failed -> 12.2%. That statistic was computed as

    rt      = any bar's LOW came within 1.5% ABOVE the neckline, in 15 bars
    rt_held = rt AND price never CLOSED 2% below the neckline in those 15 bars

Questions:
  A. How much of the discrimination comes from `rt` versus the no-fail clause?
  B. `rt` fires almost immediately after a breakout (a breakout bar closes just
     above the neckline, so the next bar's low is nearly always within 1.5% of
     it). Is `rt` doing any work at all?
  C. The no-fail clause conditions on 15 bars of FUTURE behaviour, which the
     live engine cannot know when it arms. What is the causal version worth?
"""
import json, time, urllib.parse, urllib.request
import numpy as np, pandas as pd

BASKET = ["NVDA", "AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA", "AMD", "INTC", "QCOM",
          "AVGO", "CRM", "ORCL", "CSCO", "TXN", "MU", "SPY", "QQQ", "XLE", "USO", "CVX", "XOM"]


def fetch(sym, rng="15y"):
    u = (f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}"
         f"?range={rng}&interval=1d")
    r = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
    for a in range(4):
        try:
            js = json.loads(urllib.request.urlopen(r, timeout=30).read()); break
        except Exception:
            if a == 3: return None
            time.sleep(2 ** a)
    try:
        res = js["chart"]["result"][0]; q = res["indicators"]["quote"][0]
        d = pd.DataFrame({"open": q["open"], "high": q["high"], "low": q["low"],
                          "close": q["close"]}).dropna().reset_index(drop=True)
        return d[d.close > 0].reset_index(drop=True)
    except Exception:
        return None


def swing_lows(df, k=5):
    l = df.low.values
    return [i for i in range(k, len(df) - k) if l[i] == min(l[i - k:i + k + 1])]


def patterns(df, tol=.04, mins=15, maxs=90, mind=.05, wait=60):
    lows = swing_lows(df); h, l, c = df.high.values, df.low.values, df.close.values
    out, used = [], set()
    for a in range(len(lows)):
        for b in range(a + 1, len(lows)):
            i, j = lows[a], lows[b]
            if j - i < mins: continue
            if j - i > maxs: break
            if abs(l[j] - l[i]) / l[i] > tol: continue
            neck = h[i:j + 1].max(); base = min(l[i], l[j])
            if (neck - base) / base < mind: continue
            bo = next((t for t in range(j + 1, min(j + 1 + wait, len(df))) if c[t] > neck), None)
            if bo is None or any(abs(bo - u) < 10 for u in used): continue
            used.add(bo)
            out.append((bo, neck, base)); break
    return out


rows = []
for s in BASKET:
    d = fetch(s)
    if d is None or len(d) < 400: continue
    h, l, c = d.high.values, d.low.values, d.close.values
    for bo, neck, base in patterns(d):
        end = min(bo + 126, len(d))
        if end - bo < 20: continue
        tgt = neck + (neck - base)
        w = range(bo + 1, min(bo + 16, len(d)))
        # --- the two clauses of the published statistic -----------------------
        rt = any(l[t] <= neck * 1.015 for t in w)
        nofail = not any(c[t] < neck * 0.98 for t in w)
        rt_held = rt and nofail
        # first bar at which rt becomes true (is it doing any work?)
        rt_lag = next((t - bo for t in w if l[t] <= neck * 1.015), np.nan)
        # --- a STRICT retest: excursion away, then a genuine return -----------
        strict = False
        strict_lag = np.nan
        peak = c[bo]
        for t in w:
            peak = max(peak, h[t])
            moved_away = peak >= neck * 1.015          # actually left the level
            came_back = l[t] <= neck * 1.005           # returned to touch it
            reclosed = c[t] > neck                     # and held above
            if moved_away and came_back and reclosed and (t - bo) >= 3:
                strict, strict_lag = True, t - bo
                break
        # --- CAUSAL arming: no future window, first bar rt is true and no fail yet
        causal_arm = np.nan
        for t in w:
            if c[t] < neck * 0.98:
                break
            if l[t] <= neck * 1.015:
                causal_arm = t - bo
                break
        # --- outcome ----------------------------------------------------------
        hit = fail = None
        for t in range(bo + 1, end):
            if hit is None and h[t] >= tgt: hit = t
            if fail is None and c[t] < neck * 0.98: fail = t
            if hit or fail: break
        target_first = bool(hit and (not fail or hit < fail))
        rows.append(dict(sym=s, rt=rt, nofail=nofail, rt_held=rt_held, strict=strict,
                         rt_lag=rt_lag, strict_lag=strict_lag,
                         causal_armed=not np.isnan(causal_arm), causal_lag=causal_arm,
                         target_first=target_first,
                         ret21=(c[min(bo + 21, len(c) - 1)] / c[bo] - 1) * 100))
    time.sleep(.2)

D = pd.DataFrame(rows)
print(f"patterns: {len(D)} across {D.sym.nunique()} symbols\n")

print("A. Does the `rt` clause do any work on its own?")
print(f"   P(rt fires at all)          = {D.rt.mean():.3f}   <- fires on nearly every pattern")
print(f"   median bars until rt fires  = {D.rt_lag.median():.0f}")
print(f"   rt fires within 1 bar       = {(D.rt_lag <= 1).mean():.3f}")
for k, g in D.groupby("rt"):
    print(f"   rt={str(k):5s} n={len(g):4d}  P(target first)={g.target_first.mean():.3f}")

print("\nB. Decomposition — which clause carries the discrimination?")
for name, col in [("rt only", "rt"), ("nofail only", "nofail"), ("rt_held (published)", "rt_held"),
                  ("STRICT retest", "strict")]:
    a = D[D[col]]; b = D[~D[col]]
    if len(a) and len(b):
        print(f"   {name:20s} true: n={len(a):4d} P={a.target_first.mean():.3f} | "
              f"false: n={len(b):4d} P={b.target_first.mean():.3f} | "
              f"spread={a.target_first.mean()-b.target_first.mean():+.3f}")

print("\nC. Is the published split just survivorship?")
sub = D[D.rt]
for k, g in sub.groupby("nofail"):
    print(f"   among rt=True, nofail={str(k):5s}: n={len(g):4d} P(target first)={g.target_first.mean():.3f}")
print("   -> if nofail alone reproduces the split, 'retest' is not the mechanism")

print("\nD. Strict retest vs loose, and how often each is available")
print(f"   P(strict retest occurs)     = {D.strict.mean():.3f}")
print(f"   median bars until strict    = {D.strict_lag.median():.1f}")
print(f"   P(causal arming happens)    = {D.causal_armed.mean():.3f}")
print(f"   median bars until causal    = {D.causal_lag.median():.1f}")
for k, g in D.groupby("strict"):
    print(f"   strict={str(k):5s} n={len(g):4d} P(target first)={g.target_first.mean():.3f} "
          f"med21d={g.ret21.median():+.2f}%")
