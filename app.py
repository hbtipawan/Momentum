#!/usr/bin/env python3
"""
app.py — Dual-Strategy Momentum Screener v2 (1,000–25,000 Cr universe)

Two backtest-validated strategies (15-year study 2011–2026, re-validated
Jul 2026 on the current 982-stock band with per-era robustness testing):
  STRATEGY A v2 — Fast Momentum + anti-speculation gap filter:
      score = 0.5×1M + 0.5×3M return; stocks with ANY daily move >15%
      in the last 90 days are EXCLUDED (Clenow/quality-momentum rule).
  STRATEGY B v2 — Vol-Adjusted Dual-Lookback Momentum (core):
      score = 0.5×(6M return ÷ ann. vol) + 0.5×(12−1M return ÷ ann. vol)
      — the NSE-momentum-index / Barroso–Santa-Clara style signal that
      beat plain 12−1 in ALL THREE 5-year eras of the backtest.

Shared rules (unchanged): equal weight · buffer band 1.75×N · 30% trailing
stop · DAILY universe-breadth regime filter (>50% above own 200DMA) ·
rebalance every 2nd Monday.

Universe: Stocks.csv in repo root, or upload in-app (column: Symbol).
"""
import io
import json
import datetime as dt
import urllib.request
import urllib.parse
import concurrent.futures

import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Momentum Screener", layout="wide", page_icon="🏆")

st.markdown("""
<style>
  html, body, [class*="css"] { font-size: 18px !important; }
  h1 { font-size: 32px !important; }
  h2, h3 { font-size: 25px !important; }
  .stTabs [data-baseweb="tab"] { font-size: 19px !important; padding: 10px 18px; }
  thead th { font-size: 17px !important; }
  tbody td { font-size: 17px !important; }
  .big-green { background:#d4f4dd; border:3px solid #1a7a3a; border-radius:10px;
               padding:14px 20px; font-size:24px; font-weight:bold; color:#0a5a2a; }
  .big-red   { background:#ffe0e0; border:3px solid #c00; border-radius:10px;
               padding:14px 20px; font-size:24px; font-weight:bold; color:#900; }
</style>
""", unsafe_allow_html=True)

HEADERS = {"User-Agent": "Mozilla/5.0"}
STOP_PCT = 0.30
BENCH_SYMBOL = "%5ECRSLDX"          # Nifty 500


# ------------------------------------------------------------------ universe
def load_universe(uploaded) -> pd.DataFrame:
    """Priority: in-app upload > Stocks.csv in repo root."""
    if uploaded is not None:
        df = pd.read_csv(uploaded)
    else:
        try:
            df = pd.read_csv("Stocks.csv")
        except FileNotFoundError:
            st.error("No universe found. Add **Stocks.csv** to the repo root "
                     "or upload it in the sidebar. Required column: `Symbol`.")
            st.stop()
    sym_col = next((c for c in df.columns if c.strip().lower() == "symbol"),
                   df.columns[0])
    df = df.rename(columns={sym_col: "Symbol"})
    df["Symbol"] = df["Symbol"].astype(str).str.strip().str.upper()
    df = df[df["Symbol"].str.len() > 0].drop_duplicates("Symbol")
    return df


# ------------------------------------------------------------------ data
# Primary source: Upstox historical-candle API (free, no auth) — better
# coverage than Yahoo, especially recent listings (~150 extra symbols).
# Fallback: Yahoo Finance v8 chart API per symbol.
UPSTOX_MASTER_URL = ("https://assets.upstox.com/market-quote/instruments/"
                     "exchange/NSE.csv.gz")
NIFTY500_UPSTOX_KEY = "NSE_INDEX|Nifty 500"
DATA_DAYS = 3 * 365          # 12−1 lag + 252d vol need ~504 bars


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def load_upstox_keys() -> dict:
    """{tradingsymbol -> instrument_key} for NSE equities (cached daily).
    Returns {} on failure → app runs in pure-Yahoo mode."""
    import gzip
    try:
        req = urllib.request.Request(UPSTOX_MASTER_URL, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
        df = pd.read_csv(io.BytesIO(gzip.decompress(raw)))
        eq = df[(df["exchange"] == "NSE_EQ")
                & (df["instrument_type"] == "EQUITY")]
        return dict(zip(eq["tradingsymbol"].astype(str),
                        eq["instrument_key"].astype(str)))
    except Exception:
        return {}


def _fetch_upstox(sym: str, key: str):
    """Daily closes from Upstox v3 historical-candle (no auth needed)."""
    to = dt.date.today().isoformat()
    frm = (dt.date.today() - dt.timedelta(days=DATA_DAYS)).isoformat()
    url = (f"https://api.upstox.com/v3/historical-candle/"
           f"{urllib.parse.quote(key)}/days/1/{to}/{frm}")
    try:
        req = urllib.request.Request(
            url, headers={"Accept": "application/json", **HEADERS})
        with urllib.request.urlopen(req, timeout=12) as resp:
            d = json.load(resp)
        candles = d["data"]["candles"]            # newest first
        if not candles:
            return None
        idx = (pd.to_datetime([c[0] for c in candles])
               .tz_localize(None).normalize())
        df = pd.DataFrame({"close": [c[4] for c in candles],
                           "high": [c[2] for c in candles],
                           "low": [c[3] for c in candles]}, index=idx)
        df = df.dropna(subset=["close"])
        df = df[~df.index.duplicated(keep="last")].sort_index()
        if not len(df):
            return None
        return df["close"].rename(sym), _downlocks_90(df)
    except Exception:
        return None


def _fetch_yahoo(sym: str, rng: str = "3y"):
    ysym = sym if sym.startswith("%5E") else f"{sym}.NS"
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/"
           f"{ysym}?range={rng}&interval=1d")
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=12) as resp:
            d = json.load(resp)
        r = d["chart"]["result"][0]
        q = r["indicators"]["quote"][0]
        df = pd.DataFrame({"close": q["close"], "high": q["high"],
                           "low": q["low"]},
                          index=pd.to_datetime(r["timestamp"],
                                               unit="s").normalize())
        df = df.dropna(subset=["close"])
        df = df[~df.index.duplicated(keep="last")].sort_index()
        if not len(df):
            return None
        return df["close"].rename(sym), _downlocks_90(df)
    except Exception:
        return None


FULL_HISTORY_BARS = 600      # ~3y of NSE sessions minus holidays
DOWNLOCK_MAX = 1             # exclude stocks with >=2 lower-circuit locks/90d


def _downlocks_90(df: pd.DataFrame) -> int:
    """Count lower-circuit lock days (high==low on a down day) in the last
    90 sessions — the 'can't exit' stocks. 15y evidence: excluding >=2
    down-locks lifted B core CAGR 43.3→45.6% with MaxDD −34.5→−27.3%, and
    A 62.3→71.0% with MaxDD −42.0→−35.9% (RESEARCH_NOTES.md)."""
    t = df.tail(91)
    r = t["close"].pct_change()
    return int(((t["high"] == t["low"]) & (r < -0.005)).sum())


def _fetch_one(sym: str, keys: dict):
    """Upstox first; if its history is incomplete (e.g. instrument-key reset
    after a relisting), also try Yahoo and keep the LONGER series — a short
    series silently drops the stock from the 12-month rankings.
    Returns (sym, series, source) or None."""
    if sym == BENCH_SYMBOL:
        r = _fetch_upstox(sym, NIFTY500_UPSTOX_KEY)
        if r is not None and len(r[0]) > 50:
            return sym, r[0], "upstox", 0
        r = _fetch_yahoo(sym)
        return (sym, r[0], "yahoo", 0) if r is not None else None
    key = keys.get(sym)
    r_up = _fetch_upstox(sym, key) if key else None
    if r_up is not None and len(r_up[0]) >= FULL_HISTORY_BARS:
        return sym, r_up[0], "upstox", r_up[1]
    r_y = _fetch_yahoo(sym)
    n_up = len(r_up[0]) if r_up is not None else 0
    n_y = len(r_y[0]) if r_y is not None else 0
    if n_up == 0 and n_y == 0:
        return None
    return ((sym, r_up[0], "upstox", r_up[1]) if n_up >= n_y
            else (sym, r_y[0], "yahoo", r_y[1]))


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def fetch_prices(symbols: tuple):
    keys = load_upstox_keys()
    series, dlocks = {}, {}
    src_count = {"upstox": 0, "yahoo": 0, "missing": 0}
    prog = st.progress(0.0, text="Fetching prices (Upstox → Yahoo fallback)…")
    todo = list(symbols) + [BENCH_SYMBOL]
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
        futures = {ex.submit(_fetch_one, s, keys): s for s in todo}
        done = 0
        for fut in concurrent.futures.as_completed(futures):
            res = fut.result()
            if res:
                series[res[0]] = res[1]
                src_count[res[2]] += 1
                dlocks[res[0]] = res[3]
            else:
                src_count["missing"] += 1
            done += 1
            if done % 25 == 0:
                prog.progress(done / len(todo), text=f"Fetching… {done}/{len(todo)}")
    prog.empty()
    if not keys:
        st.warning("⚠️ Upstox instrument master unavailable — running on "
                   "Yahoo Finance only this session.")
    return (pd.DataFrame(series).sort_index(), src_count,
            pd.Series(dlocks, dtype=float))


# ------------------------------------------------------------------ signals
MIN_PRICE = 20          # user rule: closing price must exceed Rs 20
BREADTH_THRESHOLD = 0.50  # risk-on when >50% of universe above own 200DMA


GAP_PCT = 0.15          # Strategy A: exclude stocks with any daily move >15%
GAP_WINDOW = 90         # ...within the last 90 trading days


B_MCAP_MIN, B_MCAP_MAX = 1000, 25000     # band applies to Strategy B only


def compute_rankings(prices: pd.DataFrame, mcap: pd.Series = None,
                     downlocks: pd.Series = None):
    """Return (df_A, df_B, regime_on, regime_info) — v2 signals."""
    stocks = prices.drop(columns=[BENCH_SYMBOL], errors="ignore")
    pxs = stocks.ffill(limit=5)
    rr = pxs.pct_change()

    last = pxs.iloc[-1]
    p21 = pxs.shift(21).iloc[-1]
    p63 = pxs.shift(63).iloc[-1]
    p126 = pxs.shift(126).iloc[-1]
    p252 = pxs.shift(252).iloc[-1]

    r1m = (last / p21 - 1) * 100
    r3m = (last / p63 - 1) * 100
    r6m = (last / p126 - 1) * 100
    r12_1 = (p21 / p252 - 1) * 100          # 12M skipping last month

    # annualised realised vol (denominators of the v2 core score)
    vol6 = rr.rolling(126, min_periods=90).std().iloc[-1] * np.sqrt(252)
    vol12 = rr.rolling(252, min_periods=180).std().iloc[-1] * np.sqrt(252)
    # largest single-day move in the gap window (Strategy A exclusion)
    gap_max = rr.abs().rolling(GAP_WINDOW, min_periods=60).max().iloc[-1] * 100

    base = pd.DataFrame({"CMP": last, "1M %": r1m, "3M %": r3m,
                         "6M %": r6m, "12−1M %": r12_1,
                         "Vol %": vol12 * 100, "MaxGap %": gap_max})
    base = base[base["CMP"] > MIN_PRICE]     # price filter (user rule)
    if downlocks is not None:
        base["Locks↓90d"] = downlocks.reindex(base.index).fillna(0).astype(int)
        # circuit filter: a stock that recently locked LOWER circuit has
        # trapped sellers — exclude from BOTH books (validated: raises
        # CAGR AND cuts drawdown; upper-circuit winners stay eligible).
        base = base[base["Locks↓90d"] <= DOWNLOCK_MAX]

    # ---- STRATEGY A v2: fast momentum + anti-speculation gap filter ----
    # 15y re-validation: excluding >15%-day movers cut MaxDD −48.9%→−42.0%
    # and beat the unfiltered signal in 2 of 3 eras (only the 2016–21
    # melt-up favoured no filter). MAR 1.47→1.48.
    dfA = base.dropna(subset=["1M %", "3M %"]).copy()
    dfA = dfA[dfA["MaxGap %"] <= GAP_PCT * 100]
    dfA["Score"] = 0.5 * dfA["1M %"] + 0.5 * dfA["3M %"]
    dfA = dfA.sort_values("Score", ascending=False)
    dfA["Rank"] = range(1, len(dfA) + 1)

    # ---- STRATEGY B v2: vol-adjusted dual-lookback momentum (core) ----
    # score = 0.5×(6M/σ) + 0.5×(12−1/σ), the NSE-momentum-index style.
    # 15y re-validation vs plain 12−1 (N10): CAGR 34.0%→43.3%,
    # MaxDD −36.3%→−34.5%, Sharpe 1.33→1.68 — and it won ALL 3 eras.
    dfB = base.dropna(subset=["6M %", "12−1M %"]).copy()
    dfB = dfB[(dfB["Vol %"] > 0)]
    # Cap band for B ONLY (validated: cap-free diluted the vol-adjusted
    # core, CAGR 43.3%→39.1%; cap-free IMPROVED fast A, 62.3%→64.9% with
    # lower DD — so A ranks the whole list, B stays 1,000–25,000 Cr).
    if mcap is not None:
        mc = mcap.reindex(dfB.index)
        dfB = dfB[mc.between(B_MCAP_MIN, B_MCAP_MAX) | mc.isna()]
    v6 = vol6.reindex(dfB.index) * 100
    dfB["Score"] = (0.5 * dfB["6M %"] / v6.clip(lower=1)
                    + 0.5 * dfB["12−1M %"] / dfB["Vol %"].clip(lower=1))
    dfB = dfB.dropna(subset=["Score"]).sort_values("Score", ascending=False)
    dfB["Rank"] = range(1, len(dfB) + 1)

    # ---- REGIME: universe internal breadth (15y-validated) ----
    # Risk-on when >50% of the universe's stocks close above their own 200DMA.
    # Backtest (2011-2026): MAR 1.33 & Sharpe 1.52 with DAILY exit — cut MaxDD
    # to -29% vs -40% for the Nifty500-200DMA gauge, incl. -19% vs -40% in
    # the 2018-20 smallcap bear.
    dma = stocks.rolling(200, min_periods=150).mean()
    pxf = stocks.ffill(limit=5)
    have = pxf.notna() & dma.notna()
    breadth_series = (((pxf > dma) & have).sum(axis=1)
                      / have.sum(axis=1).clip(lower=1)).tail(5)
    breadth = float(breadth_series.iloc[-1])
    regime_on = breadth > BREADTH_THRESHOLD

    # consecutive days above threshold (for the 2-day-confirm fast re-entry)
    green_run = 0
    for v in breadth_series[::-1]:
        if v > BREADTH_THRESHOLD:
            green_run += 1
        else:
            break

    last_have = have.iloc[-1]
    regime_info = dict(breadth=round(breadth * 100, 1),
                       n_above=int(((pxf.iloc[-1] > dma.iloc[-1]) & last_have).sum()),
                       n_total=int(last_have.sum()),
                       green_run=green_run,
                       history=[round(v * 100, 1) for v in breadth_series],
                       date=str(stocks.dropna(how="all").index[-1].date()))
    return dfA, dfB, regime_on, regime_info


# --------------------------------------------------- risk-off sleeve
# When breadth ≤50% the book goes risk-off. Instead of 0% cash, the
# validated sleeve is: GOLDBEES while gold is above its own 200DMA,
# otherwise a liquid/arbitrage fund. 15y evidence in RESEARCH_NOTES.md:
# B v2 core CAGR 43.3%→59.9% at the SAME MaxDD; won all three eras.
GOLD_SYMBOL = "GOLDBEES"


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def gold_sleeve_status(cache_key: str) -> dict:
    """Gold trend check for the risk-off sleeve. Splices split artifacts
    (|daily move|>50%) that Yahoo leaves unadjusted for Indian ETFs."""
    keys = load_upstox_keys()
    res = _fetch_one(GOLD_SYMBOL, keys)
    if res is None or len(res[1]) < 220:
        return {}
    s = res[1]  # (sym, series, source, downlocks)
    r = s.pct_change()
    r[r.abs() > 0.5] = 0.0
    clean = (1 + r.fillna(0)).cumprod()
    dma = clean.rolling(200, min_periods=150).mean()
    if np.isnan(dma.iloc[-1]):
        return {}
    up = bool(clean.iloc[-1] > dma.iloc[-1])
    dist = (clean.iloc[-1] / dma.iloc[-1] - 1) * 100
    return {"up": up, "dist": round(dist, 1), "price": round(s.iloc[-1], 2),
            "date": str(s.index[-1].date()), "source": res[2]}


# ------------------------------------------------------- YTD tracker
# Simulates each book with the full locked rules (rebalance 1st & 3rd
# Monday, buffer 1.75N, 30% stop, daily breadth regime with 2-day confirm,
# 0.25%/side) from ~6 months BEFORE Jan 1 (warm start, so the book enters
# the year already positioned like a continuously-running system), then
# reports the equity change since Jan 1.
SIM_COST = 0.0025


def _sim_book(pxs, rr, breadth_s, score_frame, gapmax, top_n, gap_filter,
              start, stop_pct=STOP_PCT):
    buffer_n = int(top_n * 1.75)
    dts = pxs.index[pxs.index >= start]
    # rebalance dates: 1st & 3rd Monday each month
    rbs = set()
    for m in pd.period_range(dts[0], dts[-1], freq="M"):
        mondays = pd.date_range(m.to_timestamp(),
                                m.to_timestamp() + pd.offsets.MonthEnd(0),
                                freq="W-MON")
        for k in (0, 2):
            if k < len(mondays):
                nxt = dts[dts >= mondays[k]]
                if len(nxt):
                    rbs.add(nxt[0])
    cash, pos = 1.0, {}
    pending = set()
    risk_on, green = True, 0
    eq, eqd = [], []
    for d in dts:
        row = pxs.loc[d]
        for s in list(pending):
            v = row.get(s, np.nan)
            if s in pos and not np.isnan(v):
                cash += pos[s]["u"] * v * (1 - SIM_COST)
                del pos[s]
                pending.discard(s)
        b = breadth_s.loc[d]
        green = green + 1 if b > BREADTH_THRESHOLD else 0
        if risk_on and b <= BREADTH_THRESHOLD:
            risk_on = False
            for s in list(pos):
                v = row.get(s, np.nan)
                if not np.isnan(v):
                    cash += pos[s]["u"] * v * (1 - SIM_COST)
                    del pos[s]
        reenter = (not risk_on) and green >= 2
        if reenter:
            risk_on = True
        for s, p in pos.items():
            v = row.get(s, np.nan)
            if not np.isnan(v):
                p["pk"] = max(p["pk"], v)
                if v < p["pk"] * (1 - stop_pct):
                    pending.add(s)
        if (d in rbs and risk_on) or reenter:
            sc = score_frame.loc[d].copy()
            sc[row <= MIN_PRICE] = np.nan
            if gap_filter:
                sc[gapmax.loc[d] > GAP_PCT] = np.nan
            ranked = sc.dropna().sort_values(ascending=False)
            rank = pd.Series(np.arange(1, len(ranked) + 1), index=ranked.index)
            for s in list(pos):
                if rank.get(s, 10**9) > buffer_n:
                    v = row.get(s, np.nan)
                    if not np.isnan(v):
                        cash += pos[s]["u"] * v * (1 - SIM_COST)
                        del pos[s]
            vac = top_n - len(pos)
            if vac > 0 and cash > 0:
                per = cash / vac
                for s in [x for x in ranked.index if x not in pos][:vac]:
                    v = row.get(s, np.nan)
                    if np.isnan(v):
                        continue
                    pos[s] = {"u": per * (1 - SIM_COST) / v, "pk": v}
                    cash -= per
        pv = cash + sum(p["u"] * row.get(s, np.nan) for s, p in pos.items()
                        if not np.isnan(row.get(s, np.nan)))
        eq.append(pv)
        eqd.append(d)
    return pd.Series(eq, index=eqd)


@st.cache_data(ttl=6 * 3600, show_spinner="Simulating YTD performance…")
def ytd_tracker(_prices: pd.DataFrame, top_n: int, cache_key: str) -> dict:
    """YTD % and MaxDD for A v2, B v2 and the Nifty 500 benchmark."""
    stocks = _prices.drop(columns=[BENCH_SYMBOL], errors="ignore")
    pxs = stocks.ffill(limit=5)
    rr = pxs.pct_change()
    jan1 = pd.Timestamp(dt.date.today().replace(month=1, day=1))
    warm = jan1 - pd.DateOffset(months=6)

    dma = pxs.rolling(200, min_periods=150).mean()
    have = pxs.notna() & dma.notna()
    breadth_s = ((pxs > dma) & have).sum(axis=1) / have.sum(axis=1).clip(lower=1)

    vol6 = rr.rolling(126, min_periods=90).std() * np.sqrt(252)
    vol12 = rr.rolling(252, min_periods=180).std() * np.sqrt(252)
    gapmax = rr.abs().rolling(GAP_WINDOW, min_periods=60).max()
    scoreA = 0.5 * (pxs / pxs.shift(21) - 1) + 0.5 * (pxs / pxs.shift(63) - 1)
    scoreB = (0.5 * (pxs / pxs.shift(126) - 1) / vol6.clip(lower=0.01)
              + 0.5 * (pxs.shift(21) / pxs.shift(252) - 1)
              / vol12.clip(lower=0.01))

    out = {}
    for name, sf, gf, n in (("A v2", scoreA, True, top_n),
                            ("B v2", scoreB, False, top_n)):
        e = _sim_book(pxs, rr, breadth_s, sf, gapmax, n, gf, warm)
        w = e[e.index >= jan1]
        if len(w) > 2:
            out[name] = ((w.iloc[-1] / w.iloc[0] - 1) * 100,
                         ((w / w.cummax()) - 1).min() * 100)
    if BENCH_SYMBOL in _prices.columns:
        bw = _prices[BENCH_SYMBOL].dropna()
        bw = bw[bw.index >= jan1]
        if len(bw) > 2:
            out["Nifty 500"] = ((bw.iloc[-1] / bw.iloc[0] - 1) * 100,
                                ((bw / bw.cummax()) - 1).min() * 100)
    return out


def zone_col(df, top_n, buffer):
    return np.where(df["Rank"] <= top_n, "🟢 TOP",
           np.where(df["Rank"] <= buffer, "🟡 BUFFER", ""))


def rotation(df, held, top_n, buffer):
    rank_map = df["Rank"].to_dict()
    kept = [s for s in held if rank_map.get(s, 9e9) <= buffer]
    sells = [s for s in held if s not in kept]
    buys = [s for s in df.index if s not in kept][:max(top_n - len(kept), 0)]
    rows = ([{"Symbol": s, "Action": "🔴 SELL",
              "Rank": rank_map.get(s, "out of universe"),
              "Why": f"Rank fell below {buffer} (or left universe)"} for s in sells]
            + [{"Symbol": s, "Action": "🟢 BUY", "Rank": rank_map.get(s),
                "Why": "New entrant filling vacancy"} for s in buys]
            + [{"Symbol": s,
                "Action": "🟡 HOLD (buffer)" if rank_map[s] > top_n else "⚪ HOLD",
                "Rank": rank_map[s], "Why": ""} for s in kept])
    return pd.DataFrame(rows)


def stop_report(prices, portfolio):
    """portfolio: {symbol: entry_date_str}. Peak measured from entry date."""
    rows = []
    for sym, entry in portfolio.items():
        if sym not in prices.columns:
            rows.append({"Symbol": sym, "Status": "⚠️ no data", "CMP": None,
                         "Peak since entry": None, "Stop level": None,
                         "Room to stop %": None})
            continue
        s = prices[sym].dropna()
        seg = s[s.index >= pd.Timestamp(entry)] if entry else s
        if seg.empty:
            seg = s
        peak = float(seg.max())
        cmp_ = float(seg.iloc[-1])
        stop_level = peak * (1 - STOP_PCT)
        room = (cmp_ / stop_level - 1) * 100
        status = "🔴 STOP HIT — SELL" if cmp_ < stop_level else \
                 ("🟠 within 5% of stop" if room < 5 else "🟢 OK")
        rows.append({"Symbol": sym, "Status": status, "CMP": round(cmp_, 1),
                     "Peak since entry": round(peak, 1),
                     "Stop level": round(stop_level, 1),
                     "Room to stop %": round(room, 1)})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ UI
st.title("🏆 Dual-Strategy Momentum Screener v2")
st.caption("Universe: your Stocks.csv (1,000–25,000 Cr band) · "
           "Strategies validated on a 15-year backtest (2011–2026), "
           "v2 signals re-validated Jul 2026 with per-era robustness tests")

with st.sidebar:
    st.header("Universe")
    up = st.file_uploader("Upload Stocks.csv (optional — else repo file is used)",
                          type="csv")
    st.header("Portfolio size")
    top_n = st.select_slider("Stocks per strategy", [5, 10, 15], value=5)
    buffer = int(top_n * 1.75)
    st.caption(f"Buffer band: hold while rank ≤ {buffer}")
    st.divider()
    if st.button("🔃 Force refresh prices"):
        st.cache_data.clear()
        st.rerun()

uni = load_universe(up)
st.sidebar.markdown(f"**{len(uni)} stocks loaded**")
prices, src, downlocks = fetch_prices(tuple(uni["Symbol"].tolist()))
st.sidebar.caption(f"Data: 🟦 Upstox {src['upstox']} · 🟨 Yahoo "
                   f"{src['yahoo']} · ⚫ no data {src['missing']}")
mcap_s = (uni.set_index("Symbol")["MarketCap_Cr"]
          if "MarketCap_Cr" in uni.columns else None)
dfA, dfB, regime_on, bi = compute_rankings(prices, mcap_s, downlocks)

name_map = uni.set_index("Symbol")
for df in (dfA, dfB):
    if "Industry" in name_map.columns:
        df.insert(0, "Industry", [name_map["Industry"].get(s, "") for s in df.index])

# ---- regime banner: universe breadth (daily-exit rule) ----
if regime_on:
    entry_note = ("" if bi["green_run"] >= 3 else
                  (" ⚡ Breadth has now been above 50% for 2 consecutive days "
                   "— if you are in CASH, ENTER TODAY (validated fast "
                   "re-entry rule), don't wait for Monday."
                   if bi["green_run"] == 2 else
                   " ⏳ First day above 50% — wait for one more green close "
                   "before re-entering (2-day confirm)."))
    st.markdown(f'<div class="big-green">🟢 REGIME: RISK-ON — universe breadth '
                f'{bi["breadth"]}% ({bi["n_above"]} of {bi["n_total"]} stocks '
                f'above their own 200DMA, threshold 50%; '
                f'{bi["green_run"]} consecutive green day(s)).'
                f'{entry_note} Check this banner DAILY.</div>',
                unsafe_allow_html=True)
else:
    gs = gold_sleeve_status(cache_key=bi["date"])
    if gs and gs["up"]:
        sleeve_note = (f" 💰 PARK the freed cash in GOLDBEES (gold is "
                       f"{gs['dist']:+.1f}% vs its 200DMA — uptrend intact).")
    elif gs:
        sleeve_note = (f" 🏦 PARK the freed cash in a LIQUID/ARBITRAGE fund "
                       f"(gold is {gs['dist']:+.1f}% vs its 200DMA — "
                       f"downtrend, do NOT hold GOLDBEES).")
    else:
        sleeve_note = " 🏦 PARK the freed cash in a LIQUID/ARBITRAGE fund."
    st.markdown(f'<div class="big-red">🔴 REGIME: RISK-OFF — universe breadth '
                f'{bi["breadth"]}% ({bi["n_above"]} of {bi["n_total"]} stocks '
                f'above their own 200DMA, below the 50% threshold). '
                f'RULE: sell ALL positions TODAY (at close or next open) — do '
                f'NOT wait for rebalance day.{sleeve_note} Re-entry: after 2 '
                f'consecutive daily closes with breadth above 50%, sell the '
                f'sleeve and buy the full book the SAME day (this banner '
                f'counts the green days).</div>',
                unsafe_allow_html=True)
st.caption(f"Prices as of {bi['date']} · regime checked DAILY (exit same day "
           f"breadth closes below 50%) · trailing stop {int(STOP_PCT*100)}% "
           f"from post-entry peak, checked daily")
if regime_on:
    gs = gold_sleeve_status(cache_key=bi["date"])
    if gs:
        st.caption(f"Risk-off sleeve (for when the banner turns RED): gold is "
                   f"{'ABOVE' if gs['up'] else 'BELOW'} its 200DMA "
                   f"({gs['dist']:+.1f}%) → freed cash would go to "
                   f"{'GOLDBEES' if gs['up'] else 'a liquid/arbitrage fund'}.")

# ---- YTD tracker: simulated book performance vs benchmark ----
ytd = ytd_tracker(prices, top_n, cache_key=f"{bi['date']}|{top_n}")
if ytd:
    cols = st.columns(len(ytd))
    for col, (name, (r, dd)) in zip(cols, ytd.items()):
        col.metric(f"{name} — YTD", f"{r:+.1f}%", f"MaxDD {dd:.1f}%",
                   delta_color="off")
    st.caption(f"YTD = locked rules simulated at Top {top_n} from 6 months "
               f"before 1 Jan (warm start), 0.25%/side costs — a discipline "
               f"gauge, not your live P&L. Momentum earns its CAGR in GREEN "
               f"regimes; trailing the index in a red, choppy year with a "
               f"smaller drawdown is the system working, not failing.")

tabA, tabB, tabRot, tabStop, tabManual = st.tabs(
    ["⚡ Strategy A v2 — Fast + Gap Filter",
     "🏛️ Strategy B v2 — Vol-Adjusted Dual Momentum",
     "🔄 Rotation Actions", "🛑 Stop-Loss Tracker", "📖 Manual"])

fmt = {"CMP": "{:.1f}", "1M %": "{:.1f}", "3M %": "{:.1f}", "6M %": "{:.1f}",
       "12−1M %": "{:.1f}", "Vol %": "{:.0f}", "MaxGap %": "{:.1f}",
       "Score": "{:.2f}"}

with tabA:
    st.subheader(f"Strategy A v2 — Fast Momentum + Gap Filter "
                 f"(0.5×1M + 0.5×3M) · Top {top_n}")
    st.caption("Stocks with any daily move >15% in the last 90 days are "
               "auto-excluded (anti-speculation rule — cut MaxDD by ~7 pts "
               "in the 15y re-validation with the same MAR). Ranks the FULL list — "
               "no market-cap band (cap-free tested better for A: 64.9% vs "
               "62.3% CAGR with LOWER drawdown). "
               "Rebalance fortnightly per tranche — see Manual §4 tranching.")
    d = dfA.copy()
    d["Zone"] = zone_col(d, top_n, buffer)
    cols = ["Rank", "Zone", "Industry", "CMP", "1M %", "3M %", "MaxGap %",
            "Locks↓90d", "Score"]
    cols = [c for c in cols if c in d.columns or c in ("Rank", "Zone")]
    cols = [c for c in cols if c in d.columns]
    st.dataframe(d.head(buffer + 10)[cols].style.format(fmt),
                 use_container_width=True, height=650)
    st.download_button("⬇️ Full ranking A (CSV)", d.to_csv().encode(),
                       f"strategyA_{dt.date.today()}.csv")

with tabB:
    st.subheader(f"Strategy B v2 — Vol-Adjusted Dual Momentum "
                 f"(0.5×6M/σ + 0.5×12−1/σ) · Top {top_n}")
    st.caption("The upgraded core: return DIVIDED by realised volatility, "
               "averaged over 6M and 12−1M lookbacks (NSE-momentum-index / "
               "Barroso–Santa-Clara style). 15y re-validation vs plain 12−1: "
               "CAGR 34.0%→43.3%, MaxDD −36.3%→−34.5%, Sharpe 1.33→1.68, "
               "and it won all three 5-year eras. Band-limited to 1,000–25,000 Cr "
               "(cap-free tested WORSE for this signal: 39.1% vs 43.3%). "
               "RECOMMENDED core, N=10. "
               "Rebalance fortnightly per tranche — see Manual §4 tranching.")
    if mcap_s is None:
        st.warning("⚠️ Your CSV has no MarketCap_Cr column — Strategy B is "
                   "running CAP-FREE, which backtested 4 pts worse. Add the "
                   "column (run make_universe.py) to restore the "
                   "1,000–25,000 Cr band.")
    d = dfB.copy()
    d["Zone"] = zone_col(d, top_n, buffer)
    cols = ["Rank", "Zone", "Industry", "CMP", "6M %", "12−1M %", "Vol %",
            "Locks↓90d", "Score"]
    cols = [c for c in cols if c in d.columns or c in ("Rank", "Zone")]
    cols = [c for c in cols if c in d.columns]
    st.dataframe(d.head(buffer + 10)[cols].style.format(fmt),
                 use_container_width=True, height=650)
    st.download_button("⬇️ Full ranking B (CSV)", d.to_csv().encode(),
                       f"strategyB_{dt.date.today()}.csv")

with tabRot:
    st.subheader("Rotation vs your current holdings")
    strat = st.radio("Which strategy book?", ["A — Fast", "B — 12−1"],
                     horizontal=True)
    df_use = dfA if strat.startswith("A") else dfB
    c1, c2 = st.columns(2)
    with c1:
        held_text = st.text_area("Holdings (comma-separated symbols)",
                                 placeholder="HFCL, ANANDRATHI, ...")
    with c2:
        pf_up = st.file_uploader("…or upload portfolio.json", type="json",
                                 key="pf")
    portfolio = {}
    if pf_up:
        portfolio = json.load(pf_up).get("holdings", {})
        if isinstance(portfolio, list):                    # legacy format
            portfolio = {s: None for s in portfolio}
    elif held_text.strip():
        portfolio = {s.strip().upper(): None
                     for s in held_text.split(",") if s.strip()}

    if portfolio:
        if not regime_on:
            st.error("🔴 REGIME IS RISK-OFF → the rule says SELL EVERYTHING "
                     "TODAY, not at the next rebalance. Table below shows "
                     "what rotation WOULD be if you override the regime rule.")
        act = rotation(df_use, list(portfolio), top_n, buffer)
        st.dataframe(act, use_container_width=True)
        today = str(dt.date.today())
        new_pf = {}
        for _, r in act.iterrows():
            if "SELL" in r["Action"]:
                continue
            new_pf[r["Symbol"]] = (today if "BUY" in r["Action"]
                                   else portfolio.get(r["Symbol"]) or today)
        st.download_button("⬇️ Save portfolio.json (re-upload next rebalance)",
                           json.dumps({"holdings": new_pf,
                                       "strategy": strat,
                                       "as_of": bi["date"]}, indent=2).encode(),
                           "portfolio.json")
    else:
        st.info(f"No holdings entered. A fresh start = simply buy the "
                f"Top {top_n} from the strategy tab, equal rupee amounts, "
                f"then download portfolio.json here after entering them above.")

with tabStop:
    st.subheader(f"Trailing stop tracker ({int(STOP_PCT*100)}% from "
                 f"post-entry peak)")
    st.caption("Upload the portfolio.json saved from the Rotation tab — entry "
               "dates in it let the tracker measure each stock's peak "
               "correctly.")
    pf_up2 = st.file_uploader("portfolio.json", type="json", key="pf2")
    manual = st.text_area("…or enter SYMBOL:YYYY-MM-DD per line",
                          placeholder="HFCL:2026-06-02\nANANDRATHI:2026-05-19")
    pf = {}
    if pf_up2:
        pf = json.load(pf_up2).get("holdings", {})
        if isinstance(pf, list):
            pf = {s: None for s in pf}
    elif manual.strip():
        for line in manual.splitlines():
            if ":" in line:
                s, d_ = line.split(":", 1)
                pf[s.strip().upper()] = d_.strip()
            elif line.strip():
                pf[line.strip().upper()] = None
    if pf:
        rep = stop_report(prices, pf)
        st.dataframe(rep, use_container_width=True)
        hits = rep[rep["Status"].str.contains("STOP HIT", na=False)]
        if len(hits):
            st.error(f"🔴 {len(hits)} stop(s) breached — the rule is to sell "
                     f"at the NEXT market open, no exceptions: "
                     f"{', '.join(hits['Symbol'])}")
    else:
        st.info("Nothing to track yet.")

with tabManual:
    st.subheader("📖 How to use & rebalance")
    try:
        st.markdown(open("MANUAL.md").read())
    except FileNotFoundError:
        st.warning("MANUAL.md not found in repo.")

st.divider()
st.caption("Data: Upstox historical API (primary) with Yahoo Finance "
           "fallback · Backtest details in repo README & RESEARCH_NOTES · "
           "Research tool, not investment advice.")
