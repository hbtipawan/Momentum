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
def _fetch_one(sym: str, rng: str = "3y"):   # 3y: 12−1 lag + 252d vol need ~504 bars
    ysym = sym if sym.startswith("%5E") else f"{sym}.NS"
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/"
           f"{ysym}?range={rng}&interval=1d")
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=12) as resp:
            d = json.load(resp)
        r = d["chart"]["result"][0]
        s = pd.Series(r["indicators"]["quote"][0]["close"],
                      index=pd.to_datetime(r["timestamp"], unit="s").normalize(),
                      name=sym).dropna()
        return sym, s[~s.index.duplicated(keep="last")]
    except Exception:
        return None


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def fetch_prices(symbols: tuple) -> pd.DataFrame:
    series = {}
    prog = st.progress(0.0, text="Fetching prices…")
    todo = list(symbols) + [BENCH_SYMBOL]
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
        futures = {ex.submit(_fetch_one, s): s for s in todo}
        done = 0
        for fut in concurrent.futures.as_completed(futures):
            res = fut.result()
            if res:
                series[res[0]] = res[1]
            done += 1
            if done % 25 == 0:
                prog.progress(done / len(todo), text=f"Fetching… {done}/{len(todo)}")
    prog.empty()
    return pd.DataFrame(series).sort_index()


# ------------------------------------------------------------------ signals
MIN_PRICE = 20          # user rule: closing price must exceed Rs 20
BREADTH_THRESHOLD = 0.50  # risk-on when >50% of universe above own 200DMA


GAP_PCT = 0.15          # Strategy A: exclude stocks with any daily move >15%
GAP_WINDOW = 90         # ...within the last 90 trading days


def compute_rankings(prices: pd.DataFrame):
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
prices = fetch_prices(tuple(uni["Symbol"].tolist()))
dfA, dfB, regime_on, bi = compute_rankings(prices)

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
    st.markdown(f'<div class="big-red">🔴 REGIME: RISK-OFF — universe breadth '
                f'{bi["breadth"]}% ({bi["n_above"]} of {bi["n_total"]} stocks '
                f'above their own 200DMA, below the 50% threshold). '
                f'RULE: sell ALL positions TODAY (at close or next open) — do '
                f'NOT wait for rebalance day. Re-enter only at the next '
                f'scheduled rebalance once breadth is back above 50%.</div>',
                unsafe_allow_html=True)
st.caption(f"Prices as of {bi['date']} · regime checked DAILY (exit same day "
           f"breadth closes below 50%) · trailing stop {int(STOP_PCT*100)}% "
           f"from post-entry peak, checked daily")

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
               "in the 15y re-validation with the same MAR). "
               "Rebalance every 2nd Monday.")
    d = dfA.copy()
    d["Zone"] = zone_col(d, top_n, buffer)
    cols = ["Rank", "Zone", "Industry", "CMP", "1M %", "3M %", "MaxGap %",
            "Score"]
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
               "and it won all three 5-year eras. RECOMMENDED core, N=10. "
               "Rebalance every 2nd Monday.")
    d = dfB.copy()
    d["Zone"] = zone_col(d, top_n, buffer)
    cols = ["Rank", "Zone", "Industry", "CMP", "6M %", "12−1M %", "Vol %",
            "Score"]
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
st.caption("Data: Yahoo Finance (delayed) · Backtest details in repo README · "
           "Research tool, not investment advice.")
