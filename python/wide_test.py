"""
Wide test: does the engine's entry selection beat random entry across a broad
universe and a long history?

Pre-registered in docs/WIDE_TEST_PREREGISTRATION.md BEFORE this was run. The
success criteria there are fixed; do not edit them to match the output.

Design note — why this is fast enough to run at all:
    The randomization test needs thousands of resamples of random entry bars.
    Rather than re-simulate each draw, this precomputes the outcome of entering
    at EVERY eligible bar once per symbol. A random draw then becomes an array
    lookup. The exit rules are a bar-for-bar copy of randomization_test.simulate().

Usage:
    python wide_test.py collect [START] [END]   # cache per-symbol outcomes
    python wide_test.py analyze                 # pooled test + breakdowns
"""
from __future__ import annotations

import os
import sys
import time

import numpy as np
import pandas as pd

from cse.engine import Config, fetch, run

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_wide_cache")
HORIZON = 60
MIN_TAIL = HORIZON + 1
MIN_BARS = 1500

# Symbols the rules were TUNED on. Excluded outright — they are contaminated.
DESIGN_BASKET = {
    "NVDA", "AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA", "AMD", "INTC", "QCOM",
    "AVGO", "CRM", "ORCL", "CSCO", "TXN", "MU", "SPY", "QQQ", "XLE", "USO", "CVX", "XOM",
}
# Used once as a holdout. Never tuned on, but the result has been seen — tagged
# so the pooled figure can be reported with and without them.
PRIOR_HOLDOUT = {
    "JPM", "JNJ", "PG", "WMT", "KO", "DIS", "BA", "CAT", "GE", "PFE", "VZ", "MRK", "HD", "MCD",
}

UNIVERSE: dict[str, str] = {}


def _add(sector: str, syms: str) -> None:
    for s in syms.split():
        if s not in DESIGN_BASKET:
            UNIVERSE[s] = sector


_add("Technology", """ADBE ACN IBM NOW INTU AMAT LRCX KLAC ADI NXPI MCHP SNPS CDNS ANET
     FTNT PANW HPQ DELL STX WDC GLW KEYS TER SWKS MPWR ON ZBRA PTC TYL EPAM JNPR NTAP AKAM CTSH""")
_add("Financials", """JPM BAC WFC C GS MS SCHW BLK SPGI CME ICE AXP COF USB PNC TFC BK STT
     AIG MET PRU ALL TRV PGR CB AON MMC AJG DFS SYF FITB KEY RF CFG HBAN NTRS""")
_add("Healthcare", """JNJ PFE MRK UNH ABBV LLY TMO ABT DHR BMY AMGN GILD CVS CI ELV HUM ISRG
     SYK BSX MDT ZBH BDX BAX EW REGN VRTX BIIB IQV A DGX LH HOLX RMD STE""")
_add("Staples", """PG KO WMT PEP COST MDLZ CL KMB GIS K HSY STZ KHC SYY ADM TSN CHD CLX MKC
     DG DLTR KR EL MO PM""")
_add("Discretionary", """HD MCD NKE SBUX LOW TJX TGT BKNG MAR HLT YUM CMG ORLY AZO ROST EBAY
     F GM LVS WYNN MGM RCL CCL DHI LEN NVR WHR APTV BBY GPC""")
_add("Industrials", """BA CAT GE HON UPS UNP RTX LMT NOC GD MMM DE EMR ETN ITW PH CMI PCAR
     CSX NSC FDX WM RSG ROK DOV IR SWK TT JCI LHX EFX VRSK URI""")
_add("Energy", """COP EOG SLB PSX VLO MPC OXY HAL BKR DVN FANG HES KMI WMB OKE TRGP APA MRO""")
_add("Materials", """LIN APD SHW ECL DD DOW PPG NEM FCX NUE STLD VMC MLM ALB IFF CE EMN PKG IP AVY""")
_add("Utilities", """NEE DUK SO D AEP EXC SRE XEL ED WEC ES PEG AEE DTE PPL CMS CNP ATO NI LNT""")
_add("RealEstate", """AMT PLD CCI EQIX PSA SPG O WELL DLR AVB EQR VTR ESS MAA UDR BXP ARE HST REG KIM""")
_add("Communication", """VZ T TMUS CMCSA CHTR NFLX EA TTWO OMC IPG LYV WBD PARA FOXA NWSA DIS""")
_add("ETF", """DIA IWM MDY EFA EEM XLF XLV XLP XLY XLI XLB XLU XLRE XLK IYR GLD SLV TLT HYG""")


def outcomes_all_bars(d: pd.DataFrame) -> np.ndarray:
    """Return, for every bar, the trade result of entering there — or NaN if the
    bar is not eligible. Mirrors randomization_test.simulate() exactly."""
    c = d["close"].to_numpy(float)
    hi = d["high"].to_numpy(float)
    lo = d["low"].to_numpy(float)
    op = d["open"].to_numpy(float)
    atrv = d["atr"].to_numpy(float)
    p_stop = d["plan_stop"].to_numpy(float)
    p_tgt = d["plan_target"].to_numpy(float)
    score = d["score"].to_numpy(float)
    z = d["z20"].to_numpy(float)
    sk = d["stochk"].to_numpy(float)
    rv = d["relvol5"].to_numpy(float)
    n = len(d)
    out = np.full(n, np.nan)

    for e in range(max(0, n - MIN_TAIL)):
        if not np.isfinite(atrv[e]) or not np.isfinite(c[e]) or c[e] <= 0:
            continue
        px = c[e]
        stop = p_stop[e] if np.isfinite(p_stop[e]) else px - atrv[e]
        tgt = p_tgt[e]
        if not np.isfinite(tgt) or tgt <= px:
            tgt = px + 2.5 * atrv[e]
        if stop >= px:
            stop = px - atrv[e]
        exit_px = c[min(e + HORIZON, n - 1)]
        for j in range(e + 1, min(e + HORIZON + 1, n)):
            if lo[j] <= stop:
                exit_px = min(op[j], stop)
                break
            if hi[j] >= tgt:
                exit_px = max(op[j], tgt)
                break
            degraded = np.isfinite(score[j]) and score[j] < 0
            extended = (np.isfinite(z[j]) and z[j] > 2.0
                        and np.isfinite(sk[j]) and sk[j] > 90
                        and np.isfinite(rv[j]) and rv[j] < 0.8)
            if degraded or extended:
                exit_px = c[j]
                break
        out[e] = (exit_px / px - 1) * 100
    return out


def collect(start: int = 0, end: int | None = None) -> None:
    os.makedirs(CACHE, exist_ok=True)
    cfg = Config()
    syms = sorted(UNIVERSE)[start:end]
    print(f"collect: {len(syms)} symbols (universe {len(UNIVERSE)}), cache={CACHE}", flush=True)
    ok = skip = fail = 0
    for i, s in enumerate(syms, 1):
        path = os.path.join(CACHE, f"{s.replace('/', '_')}.npz")
        if os.path.exists(path):
            skip += 1
            continue
        try:
            d1 = fetch(s, "25y", "1d")
            if len(d1) < MIN_BARS:
                print(f"  [{i}/{len(syms)}] {s}: only {len(d1)} bars — skipped", flush=True)
                np.savez_compressed(path, insufficient=True)
                skip += 1
                continue
            wk = fetch(s, "25y", "1wk")
            d = run(d1, cfg, htf=wk)
            out = outcomes_all_bars(d)
            sig = d["long_sig"].to_numpy(bool)
            lr = np.log(d["close"] / d["close"].shift()).replace([np.inf, -np.inf], np.nan)
            annvol = float(lr.std(ddof=1) * np.sqrt(252) * 100)
            years = d["dt"].dt.year.to_numpy()
            np.savez_compressed(
                path, outcome=out.astype(np.float32), signal=sig, year=years.astype(np.int16),
                sector=UNIVERSE[s], annvol=annvol, bars=len(d1),
                prior_holdout=bool(s in PRIOR_HOLDOUT), insufficient=False,
            )
            ok += 1
            if i % 20 == 0 or i == len(syms):
                print(f"  [{i}/{len(syms)}] ok={ok} skip={skip} fail={fail} "
                      f"(last {s}: {len(d1)} bars, {int(sig.sum())} signals)", flush=True)
        except Exception as exc:
            fail += 1
            print(f"  [{i}/{len(syms)}] {s}: FAILED {type(exc).__name__}: {exc}", flush=True)
        time.sleep(0.1)
    print(f"collect done: ok={ok} skipped={skip} failed={fail}", flush=True)


def _load() -> list[dict]:
    rows = []
    for f in sorted(os.listdir(CACHE)):
        if not f.endswith(".npz"):
            continue
        z = np.load(os.path.join(CACHE, f), allow_pickle=False)
        if "insufficient" in z and bool(z["insufficient"]):
            continue
        rows.append(dict(
            sym=f[:-4], outcome=z["outcome"].astype(float), signal=z["signal"],
            year=z["year"], sector=str(z["sector"]), annvol=float(z["annvol"]),
            prior_holdout=bool(z["prior_holdout"]),
        ))
    return rows


def _randtest(data: list[dict], iters: int = 2000, seed: int = 7) -> dict:
    """Engine entries vs random entries drawn from the same eligible bars."""
    rng = np.random.default_rng(seed)
    real, pools, counts = [], [], []
    for r in data:
        elig = np.isfinite(r["outcome"])
        s = r["signal"] & elig
        k = int(s.sum())
        if k == 0:
            continue
        real.append(r["outcome"][s])
        pools.append(r["outcome"][elig])
        counts.append(k)
    if not real:
        return {}
    real = np.concatenate(real)
    rm = np.empty(iters)
    rw = np.empty(iters)
    for it in range(iters):
        draw = [rng.choice(p, size=min(k, p.size), replace=False)
                for p, k in zip(pools, counts)]
        pooled = np.concatenate(draw)
        rm[it] = pooled.mean()
        rw[it] = (pooled > 0).mean() * 100
    edge = real.mean() - rm.mean()
    return dict(n=real.size, symbols=len(counts),
                real_mean=real.mean(), real_med=float(np.median(real)),
                real_win=(real > 0).mean() * 100,
                rand_mean=rm.mean(), rand_sd=rm.std(), rand_win=rw.mean(),
                p=float((rm >= real.mean()).mean()), edge=edge,
                sd_units=edge / rm.std() if rm.std() else np.nan)


def _line(tag: str, r: dict) -> str:
    if not r:
        return f"  {tag:24s} (no signals)"
    return (f"  {tag:24s} n={r['n']:6d} sym={r['symbols']:3d}  "
            f"engine={r['real_mean']:+6.3f}%  random={r['rand_mean']:+6.3f}%  "
            f"edge={r['edge']:+6.3f}pp ({r['sd_units']:+5.2f}sd)  p={r['p']:.4f}")


def analyze(iters: int = 2000) -> None:
    data = _load()
    if not data:
        print("no cache — run `python wide_test.py collect` first")
        return
    tot_sig = sum(int((d["signal"] & np.isfinite(d["outcome"])).sum()) for d in data)
    print("=" * 104)
    print(f"WIDE TEST — {len(data)} symbols, {tot_sig} engine signals")
    print("Pre-registered in docs/WIDE_TEST_PREREGISTRATION.md")
    print("=" * 104)

    print("\n### PRIMARY (confirmatory) ###")
    main = _randtest(data, iters)
    print(_line("ALL SYMBOLS", main))
    clean = _randtest([d for d in data if not d["prior_holdout"]], iters)
    print(_line("excl. prior holdout", clean))

    if main:
        p, e = main["p"], main["edge"]
        if p < 0.01 and e >= 0.10:
            verdict = "A — REAL EDGE (p<0.01 and edge>=+0.10pp)"
        elif p >= 0.05:
            verdict = "B — NO EDGE (p>=0.05)"
        else:
            verdict = "C — INCONCLUSIVE / economically trivial"
        print(f"\n  PRE-REGISTERED VERDICT: {verdict}")
        print(f"  engine win rate {main['real_win']:.1f}%  vs random {main['rand_win']:.1f}%")
        print(f"  smallest edge this test could detect (~2sd): {2*main['rand_sd']:.3f} pp/trade")

    print("\n### SECONDARY — EXPLORATORY ONLY, not evidence ###")
    print("\n-- by sector --")
    for sec in sorted({d["sector"] for d in data}):
        print(_line(sec, _randtest([d for d in data if d["sector"] == sec], 400)))

    print("\n-- by symbol annualised volatility (quartiles) --")
    vols = np.array([d["annvol"] for d in data])
    qs = np.percentile(vols, [25, 50, 75])
    for lbl, sel in [
        (f"Q1 vol <{qs[0]:.0f}%", lambda v: v < qs[0]),
        (f"Q2 {qs[0]:.0f}-{qs[1]:.0f}%", lambda v: qs[0] <= v < qs[1]),
        (f"Q3 {qs[1]:.0f}-{qs[2]:.0f}%", lambda v: qs[1] <= v < qs[2]),
        (f"Q4 vol >{qs[2]:.0f}%", lambda v: v >= qs[2]),
    ]:
        print(_line(lbl, _randtest([d for d in data if sel(d["annvol"])], 400)))

    print("\n-- by era (entry year) --")
    for lbl, lo_y, hi_y in [("2000-2008", 2000, 2008), ("2009-2015", 2009, 2015),
                            ("2016-2020", 2016, 2020), ("2021-2026", 2021, 2026)]:
        sub = []
        for d in data:
            m = (d["year"] >= lo_y) & (d["year"] <= hi_y)
            if m.sum() < 50:
                continue
            o = d["outcome"].copy()
            o[~m] = np.nan
            sub.append({**d, "outcome": o})
        print(_line(lbl, _randtest(sub, 400)))

    print("\nReminder: subgroup results are hypothesis candidates for a future")
    print("pre-registered test on fresh data, NOT findings.")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "collect"
    if cmd == "collect":
        a = int(sys.argv[2]) if len(sys.argv) > 2 else 0
        b = int(sys.argv[3]) if len(sys.argv) > 3 else None
        collect(a, b)
    else:
        analyze(int(sys.argv[2]) if len(sys.argv) > 2 else 2000)
