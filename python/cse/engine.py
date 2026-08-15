"""
Confluence Signal Engine — Python reference implementation.

This mirrors the logic of `pine/confluence_signal_engine.pine` bar-for-bar so the
signal rules can be validated on historical data (Pine cannot be backtested
outside TradingView). If you change one, change the other.

Not investment advice.
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

# ----------------------------------------------------------------------------
# data
# ----------------------------------------------------------------------------
UA = {"User-Agent": "Mozilla/5.0"}


def fetch(symbol: str, rng: str = "10y", interval: str = "1d") -> pd.DataFrame:
    """Yahoo Finance OHLCV. Drops the spurious trailing partial weekly bar."""
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}"
        f"?range={rng}&interval={interval}"
    )
    req = urllib.request.Request(url, headers=UA)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                js = json.loads(r.read())
            break
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2**attempt)

    res = js["chart"]["result"][0]
    q = res["indicators"]["quote"][0]
    df = pd.DataFrame(
        {"open": q["open"], "high": q["high"], "low": q["low"],
         "close": q["close"], "volume": q["volume"]}
    )
    df["dt"] = pd.to_datetime(res["timestamp"], unit="s", utc=True).tz_convert("America/New_York")
    df = df.dropna(subset=["open", "high", "low", "close"]).reset_index(drop=True)
    df = df[df["close"] > 0].reset_index(drop=True)
    if interval == "1wk" and len(df) > 2 and (df["dt"].iloc[-1] - df["dt"].iloc[-2]).days < 5:
        df = df.iloc[:-1].reset_index(drop=True)
    return df


# ----------------------------------------------------------------------------
# indicators (match Pine's ta.* semantics)
# ----------------------------------------------------------------------------
def rma(s: pd.Series, n: int) -> pd.Series:
    """Wilder smoothing — Pine's ta.rma."""
    return s.ewm(alpha=1 / n, adjust=False).mean()


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    d = close.diff()
    return 100 - 100 / (1 + rma(d.clip(lower=0), n) / rma(-d.clip(upper=0), n).replace(0, np.nan))


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    pc = df["close"].shift()
    tr = pd.concat(
        [df["high"] - df["low"], (df["high"] - pc).abs(), (df["low"] - pc).abs()], axis=1
    ).max(axis=1)
    return rma(tr, n)


def dmi(df: pd.DataFrame, n: int = 14) -> tuple[pd.Series, pd.Series, pd.Series]:
    up, dn = df["high"].diff(), -df["low"].diff()
    plus = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), index=df.index)
    minus = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), index=df.index)
    tr = atr(df, n)
    di_p = 100 * rma(plus, n) / tr
    di_m = 100 * rma(minus, n) / tr
    dx = 100 * (di_p - di_m).abs() / (di_p + di_m).replace(0, np.nan)
    return di_p, di_m, rma(dx, n)


def macd(close: pd.Series):
    line = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
    sig = line.ewm(span=9, adjust=False).mean()
    return line, sig, line - sig


def stoch_k(df: pd.DataFrame, n: int = 14, smooth: int = 3) -> pd.Series:
    ll, hh = df["low"].rolling(n).min(), df["high"].rolling(n).max()
    return (100 * (df["close"] - ll) / (hh - ll)).rolling(smooth).mean()


def percentrank(s: pd.Series, n: int) -> pd.Series:
    """Pine's ta.percentrank: % of the last n values strictly below current."""
    return s.rolling(n).apply(lambda w: (w[:-1] < w[-1]).mean() * 100, raw=True)


def obv(df: pd.DataFrame) -> pd.Series:
    return (np.sign(df["close"].diff()).fillna(0) * df["volume"]).cumsum()


def ewma_var(logret: pd.Series, lam: float = 0.94) -> pd.Series:
    """RiskMetrics EWMA conditional variance — the GARCH proxy used for gating."""
    r2 = logret.fillna(0.0) ** 2
    out = np.empty(len(r2))
    out[0] = r2.iloc[0]
    vals = r2.to_numpy()
    for i in range(1, len(r2)):
        out[i] = lam * out[i - 1] + (1 - lam) * vals[i]
    return pd.Series(out, index=logret.index)


def pivots(df: pd.DataFrame, left: int, right: int) -> tuple[pd.Series, pd.Series]:
    """Pine ta.pivothigh/low — value is placed on the CONFIRMATION bar (index+right)."""
    h, l = df["high"].to_numpy(), df["low"].to_numpy()
    n = len(df)
    ph = np.full(n, np.nan)
    pl = np.full(n, np.nan)
    for i in range(left, n - right):
        w_h, w_l = h[i - left:i + right + 1], l[i - left:i + right + 1]
        if h[i] == w_h.max() and (w_h == h[i]).sum() == 1:
            ph[i + right] = h[i]
        if l[i] == w_l.min() and (w_l == l[i]).sum() == 1:
            pl[i + right] = l[i]
    return pd.Series(ph, index=df.index), pd.Series(pl, index=df.index)


# ----------------------------------------------------------------------------
# configuration
# ----------------------------------------------------------------------------
@dataclass
class Config:
    long_thr: float = 45.0
    short_thr: float = 55.0
    min_rr: float = 1.5
    noise_mult: float = 1.0
    hv_suppress: float = 90.0
    cooldown: int = 10
    use_vol_conf: bool = True
    piv_len: int = 5
    rsi_len: int = 14
    adx_len: int = 14
    atr_len: int = 14
    vol_len: int = 20
    db_tol: float = 4.0
    db_min_sep: int = 15
    db_max_sep: int = 90
    retest_tol: float = 1.5
    fb_window: int = 10
    range_len: int = 20
    range_max_w: float = 9.0
    weights: dict = field(default_factory=lambda: {
        "ma": 2.0, "htf": 2.0, "struct": 1.5, "adx": 1.5, "macd": 1.0,
        "rsi": 1.0, "vol": 1.0, "ext": 1.0, "hv": 1.0, "lvl": 1.0,
    })


def _clip(v, lo, hi):
    return max(lo, min(hi, v))


# ----------------------------------------------------------------------------
# feature computation
# ----------------------------------------------------------------------------
def compute_features(df: pd.DataFrame, cfg: Config, htf: pd.DataFrame | None = None) -> pd.DataFrame:
    d = df.copy()
    c = d["close"]
    d["sma20"], d["sma50"], d["sma200"] = c.rolling(20).mean(), c.rolling(50).mean(), c.rolling(200).mean()
    d["atr"] = atr(d, cfg.atr_len)
    d["rsi"] = rsi(c, cfg.rsi_len)
    _, _, d["macdh"] = macd(c)
    d["dip"], d["dim"], d["adx"] = dmi(d, cfg.adx_len)
    d["stochk"] = stoch_k(d)
    d["sd20"] = c.rolling(20).std(ddof=0)
    d["z20"] = (c - d["sma20"]) / d["sd20"].replace(0, np.nan)
    d["obv"] = obv(d)
    d["obv_agree"] = np.sign(d["obv"] - d["obv"].shift(20)) == np.sign(c - c.shift(20))
    d["volavg"] = d["volume"].rolling(cfg.vol_len).mean()
    d["relvol"] = d["volume"] / d["volavg"].replace(0, np.nan)
    d["relvol5"] = d["relvol"].rolling(5).mean()
    d["logret"] = np.log(c / c.shift())
    d["hv20"] = d["logret"].rolling(20).std(ddof=1) * np.sqrt(252) * 100
    d["hv_pct"] = percentrank(d["hv20"], 252)
    ev = ewma_var(d["logret"], 0.94)
    d["ewma_vol_ann"] = np.sqrt(ev.clip(lower=0) * 252) * 100
    d["sigma21"] = np.sqrt(ev.clip(lower=0) * 21)
    d["noise_floor"] = c * d["sigma21"]
    d["ph"], d["pl"] = pivots(d, cfg.piv_len, cfg.piv_len)
    d["rng_hi"] = d["high"].rolling(cfg.range_len).max()
    d["rng_lo"] = d["low"].rolling(cfg.range_len).min()
    d["rng_w"] = (d["rng_hi"] - d["rng_lo"]) / d["rng_lo"] * 100

    # higher timeframe, aligned as-of (previous closed HTF bar -> no lookahead)
    if htf is not None and len(htf) > 55:
        h = htf.copy()
        h["sma50"] = h["close"].rolling(50).mean()
        h = h[["dt", "close", "sma50"]].copy()
        h["dt"] = h["dt"] + pd.Timedelta(seconds=1)  # only usable AFTER the bar closes
        # merge_asof requires identical datetime resolutions on both keys
        tz = "America/New_York"
        left = d.sort_values("dt").copy()
        right = h.sort_values("dt").copy()
        left["dt"] = left["dt"].astype(f"datetime64[ns, {tz}]")
        right["dt"] = right["dt"].astype(f"datetime64[ns, {tz}]")
        d = pd.merge_asof(left, right, on="dt", direction="backward", suffixes=("", "_htf"))
        d["htf_up"] = d["close_htf"] > d["sma50_htf"]
        d["htf_dn"] = d["close_htf"] < d["sma50_htf"]
    else:
        d["htf_up"] = False
        d["htf_dn"] = False
    return d


# ----------------------------------------------------------------------------
# stateful pass: structure, patterns, score, gates, signals
# ----------------------------------------------------------------------------
def run(df: pd.DataFrame, cfg: Config, htf: pd.DataFrame | None = None) -> pd.DataFrame:
    d = compute_features(df, cfg, htf)
    n = len(d)
    w = cfg.weights
    w_tot = sum(w.values())

    ph1 = ph2 = pl1 = pl2 = np.nan
    ph1_bar = pl1_bar = None
    ph_arr: list[float] = []
    pl_arr: list[float] = []
    pl_hist: list[tuple[float, int]] = []   # (low, bar) for pair-wise matching

    db_neck = db_base = np.nan
    db_break = None
    db_retest = db_fail = False
    db_born = -10**6            # bar the pattern was formed on

    last_sig = -10**6
    pos = 0
    entry = stop = tgt = np.nan
    entry_armed = False   # was this trade entered on the double-bottom setup?

    cols = {k: np.full(n, np.nan) for k in
            ("score", "res", "sup", "res_sigma", "sup_sigma", "long_rr", "db_neck", "db_target")}
    flags = {k: np.zeros(n, dtype=bool) for k in
             ("long_sig", "short_sig", "exit_sig", "db_armed", "struct_up", "struct_dn", "high_vol")}
    regime_out = np.array(["" for _ in range(n)], dtype=object)
    block_out = np.array(["" for _ in range(n)], dtype=object)
    pos_out = np.zeros(n, dtype=int)
    stop_out = np.full(n, np.nan)
    tgt_out = np.full(n, np.nan)

    for i in range(n):
        row = d.iloc[i]
        px = row["close"]

        # ---- structure ------------------------------------------------------
        if not np.isnan(row["ph"]):
            ph2, ph1 = ph1, row["ph"]
            ph1_bar = i - cfg.piv_len
            ph_arr.append(row["ph"])
            ph_arr[:] = ph_arr[-40:]
        if not np.isnan(row["pl"]):
            pl2, pl1 = pl1, row["pl"]
            pl1_bar = i - cfg.piv_len
            pl_arr.append(row["pl"])
            pl_arr[:] = pl_arr[-40:]
            pl_hist.append((float(row["pl"]), pl1_bar))
            pl_hist[:] = pl_hist[-12:]

            # ---- double-bottom detection ------------------------------------
            # Compare the new pivot low against the LAST SEVERAL pivot lows, not
            # only the immediately preceding one. A qualifying pair is routinely
            # separated by an intervening pivot (e.g. NVDA 189.80 -> 197.97 ->
            # 190.01), and consecutive-only matching misses those entirely.
            for k in range(len(pl_hist) - 2, max(-1, len(pl_hist) - 8), -1):
                prev_val, prev_bar = pl_hist[k]
                sep = pl1_bar - prev_bar
                if sep > cfg.db_max_sep:
                    break
                if (abs(pl1 - prev_val) / prev_val * 100 <= cfg.db_tol
                        and sep >= cfg.db_min_sep):
                    neck = d["high"].iloc[max(0, prev_bar):pl1_bar + 1].max()
                    base = min(pl1, prev_val)
                    if not np.isnan(neck) and (neck - base) / base * 100 >= 5.0:
                        db_neck, db_base = neck, base
                        db_break, db_retest, db_fail = None, False, False
                        db_born = i
                    break

        s_up = not np.isnan(ph1) and not np.isnan(ph2) and not np.isnan(pl1) and not np.isnan(pl2) \
            and ph1 > ph2 and pl1 > pl2
        s_dn = not np.isnan(ph1) and not np.isnan(ph2) and not np.isnan(pl1) and not np.isnan(pl2) \
            and ph1 < ph2 and pl1 < pl2

        # ---- pattern state machine -----------------------------------------
        # A pattern that never breaks out goes stale; drop it rather than let an
        # old neckline persist indefinitely.
        if not np.isnan(db_neck) and db_break is None and (i - db_born) > cfg.db_max_sep * 2:
            db_neck = db_base = np.nan
        if not np.isnan(db_neck):
            if db_break is None and px > db_neck:
                db_break = i
            elif db_break is not None:
                if row["low"] <= db_neck * (1 + cfg.retest_tol / 100) and i > db_break:
                    db_retest = True
                if px < db_neck and i - db_break <= cfg.fb_window:
                    db_fail = True
                if px < db_neck * 0.98:
                    db_fail = True
        db_armed = db_break is not None and db_retest and not db_fail and px > db_neck
        db_target = db_neck + (db_neck - db_base) if not np.isnan(db_neck) else np.nan

        # ---- adaptive levels -------------------------------------------------
        atrv = row["atr"]
        above = [v for v in ph_arr if v > px]
        below = [v for v in pl_arr if v < px]
        res = min(above) if above else np.nan          # nearest, for display
        sup = max(below) if below else np.nan
        nf = row["noise_floor"]
        res_sig = (res - px) / nf if (not np.isnan(res) and nf and nf > 0) else np.nan
        sup_sig = (px - sup) / nf if (not np.isnan(sup) and nf and nf > 0) else np.nan

        # The TARGET is the nearest resistance that clears the noise floor. Using
        # the merely-nearest level makes the noise gate self-defeating: the closest
        # pivot high sits ~0.2 sigma away by construction, so it can never qualify.
        # With no qualifying level overhead (blue sky), fall back to a volatility
        # target — an absence of overhead supply is itself constructive.
        need = cfg.noise_mult * nf if (nf and nf > 0) else 0.0
        qual = [v for v in above if (v - px) >= need]
        res_target = min(qual) if qual else (px + max(2.5 * atrv, need)
                                             if not np.isnan(atrv) else np.nan)

        # ---- regime ----------------------------------------------------------
        in_range = not np.isnan(row["rng_w"]) and row["rng_w"] <= cfg.range_max_w
        adxv, dip, dim = row["adx"], row["dip"], row["dim"]
        if adxv >= 25 and dip > dim:
            regime = "TREND UP"
        elif adxv >= 25 and dim > dip:
            regime = "TREND DOWN"
        elif adxv < 20 and in_range:
            regime = "RANGE"
        elif adxv < 20:
            regime = "CHOP"
        else:
            regime = "TRANSITION"
        high_vol = not np.isnan(row["hv_pct"]) and row["hv_pct"] >= cfg.hv_suppress

        # ---- confluence score ------------------------------------------------
        if np.isnan(row["sma50"]):
            score = np.nan
        else:
            c_ma = ((1 if px > row["sma20"] else -1)
                    + (1 if row["sma20"] > row["sma50"] else -1)
                    + (0 if np.isnan(row["sma200"]) else (1 if row["sma50"] > row["sma200"] else -1))) / 3
            c_htf = 1.0 if row["htf_up"] else (-1.0 if row["htf_dn"] else 0.0)
            c_struct = 1.0 if s_up else (-1.0 if s_dn else 0.0)
            c_adx = (1.0 if adxv >= 25 else 0.5 if adxv >= 20 else 0.15) * (1 if dip > dim else -1)
            prev_h = d["macdh"].iloc[i - 1] if i else 0.0
            c_macd = (1 if row["macdh"] > 0 else -1) * (
                1.0 if abs(row["macdh"]) > abs(prev_h) else 0.5)
            c_rsi = _clip((row["rsi"] - 50) / 25, -1, 1)
            rv5 = row["relvol5"]
            c_vol = (0.5 if (not np.isnan(rv5) and rv5 >= 1.0) else -0.25) \
                + (0.5 if row["obv_agree"] else -0.5)
            z = row["z20"]
            c_ext = (-np.sign(z) * _clip((abs(z) - 1.5) / 1.5, 0, 1)) if (
                not np.isnan(z) and abs(z) > 1.5) else 0.0
            hvp = row["hv_pct"]
            c_hv = -0.6 if (not np.isnan(hvp) and hvp > 80) else (
                -0.25 if (not np.isnan(hvp) and hvp > 60) else 0.15)
            c_lvl = (0.5 if (not np.isnan(sup_sig) and sup_sig < 0.35) else 0.0) \
                + (-0.5 if (not np.isnan(res_sig) and res_sig < 0.35) else 0.0)
            raw = (c_ma * w["ma"] + c_htf * w["htf"] + c_struct * w["struct"] + c_adx * w["adx"]
                   + c_macd * w["macd"] + c_rsi * w["rsi"] + c_vol * w["vol"] + c_ext * w["ext"]
                   + c_hv * w["hv"] + c_lvl * w["lvl"])
            score = _clip(raw / w_tot * 100, -100, 100)

        # ---- geometry & gates -------------------------------------------------
        # Stop sits below structure but never tighter than 1 ATR: a stop closer
        # than one ATR is noise-triggered and inflates R:R with a fake edge.
        struct_stop = (sup - 0.5 * atrv) if not np.isnan(sup) else px - 2.0 * atrv
        l_stop = min(struct_stop, px - 1.0 * atrv)
        l_tgt = db_target if (db_armed and not np.isnan(db_target)) else res_target
        l_risk = px - l_stop
        l_rew = (l_tgt - px) if not np.isnan(l_tgt) else np.nan
        l_rr = (l_rew / l_risk) if (not np.isnan(l_rew) and l_risk > 0) else np.nan

        g_noise = (not np.isnan(l_tgt)) and (l_tgt - px) >= cfg.noise_mult * nf
        g_rr = (not np.isnan(l_rr)) and l_rr >= cfg.min_rr
        g_score = (not np.isnan(score)) and score >= cfg.long_thr
        g_vol_regime = not high_vol
        g_volume = (not cfg.use_vol_conf) or (
            (not np.isnan(row["relvol"]) and row["relvol"] >= 1.0) or bool(row["obv_agree"]))

        rng_hi, rng_lo = row["rng_hi"], row["rng_lo"]
        prev_c = d["close"].iloc[i - 1] if i else px
        uptrend_ctx = bool(row["htf_up"]) or (not np.isnan(row["sma200"])
                                              and row["sma50"] > row["sma200"])
        # (a) breakout whose retest HELD - the highest-information event measured
        setup_retest = db_armed
        # (b) lower third of an established range
        setup_range_low = (in_range and not np.isnan(rng_lo)
                           and px <= rng_lo + (rng_hi - rng_lo) * 0.30 and px > rng_lo
                           and row["rsi"] < 55)
        # (c) pullback inside an uptrend, turning back up
        setup_pullback = (uptrend_ctx and not np.isnan(row["sma50"]) and px > row["sma50"]
                          and not np.isnan(row["z20"]) and row["z20"] < 0.8
                          and 35 < row["rsi"] < 62 and px > prev_c)
        # (d) reclaim of the 50-period mean from below
        setup_reclaim = (uptrend_ctx and not np.isnan(row["sma50"]) and px > row["sma50"]
                         and prev_c <= d["sma50"].iloc[i - 1] if i else False)
        g_setup = setup_retest or setup_range_low or setup_pullback or setup_reclaim
        cool_ok = (i - last_sig) >= cfg.cooldown

        long_raw = all([g_noise, g_rr, g_score, g_vol_regime, g_volume, g_setup, cool_ok])

        # ---- blocking reason -------------------------------------------------
        if long_raw:
            block = "-"
        elif not g_vol_regime:
            block = "high volatility"
        elif not g_setup:
            block = "no qualifying setup"
        elif not g_score:
            block = "score below threshold"
        elif not g_noise:
            block = "target inside noise floor"
        elif not g_rr:
            block = "R:R too low"
        elif not g_volume:
            block = "volume not confirming"
        else:
            block = "cooldown"

        # ---- position management ---------------------------------------------
        long_sig = long_raw and pos <= 0
        exit_sig = False
        if pos == 1:
            hit_stop = px < stop
            hit_tgt = row["high"] >= tgt
            # db_fail may only close a trade that was ENTERED on that pattern —
            # it is persistent global state, not a property of every trade.
            degraded = (not np.isnan(score) and score < 0) or (db_fail and entry_armed)
            extended = (not np.isnan(row["z20"]) and row["z20"] > 2.0
                        and not np.isnan(row["stochk"]) and row["stochk"] > 90
                        and not np.isnan(row["relvol5"]) and row["relvol5"] < 0.8)
            exit_sig = hit_stop or hit_tgt or degraded or extended

        if long_sig:
            pos, entry, stop, tgt = 1, px, l_stop, l_tgt
            entry_armed = bool(setup_retest)
            last_sig = i
        elif pos == 1 and exit_sig:
            pos, entry, stop, tgt = 0, np.nan, np.nan, np.nan
            entry_armed = False

        cols["score"][i] = score
        cols["res"][i], cols["sup"][i] = res, sup
        cols["res_sigma"][i], cols["sup_sigma"][i] = res_sig, sup_sig
        cols["long_rr"][i] = l_rr
        cols["db_neck"][i], cols["db_target"][i] = db_neck, db_target
        flags["long_sig"][i] = long_sig
        flags["exit_sig"][i] = exit_sig
        flags["db_armed"][i] = db_armed
        flags["struct_up"][i], flags["struct_dn"][i] = s_up, s_dn
        flags["high_vol"][i] = high_vol
        regime_out[i], block_out[i] = regime, block
        pos_out[i], stop_out[i], tgt_out[i] = pos, stop, tgt

    for k, v in cols.items():
        d[k] = v
    for k, v in flags.items():
        d[k] = v
    d["regime"] = regime_out
    d["blocked_by"] = block_out
    d["pos"] = pos_out
    d["stop"] = stop_out
    d["target"] = tgt_out
    return d
