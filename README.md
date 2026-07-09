# 🏆 Dual-Strategy Momentum Screener **v2** (1,000–25,000 Cr)

Streamlit app implementing two momentum rotation strategies. v1 was
validated on a 15-year backtest (Jul 2011 – Jul 2026); **v2 upgrades the
two ranking signals** after a fresh re-validation (Jul 2026, 982-stock
band, per-era robustness testing, cost-sensitivity checks). All risk rules
are unchanged.

| Strategy | Signal | 15y CAGR | MaxDD | Sharpe | MAR | Character |
|---|---|---|---|---|---|---|
| **A v2 — Fast + Gap Filter** | 0.5×1M + 0.5×3M return, excluding stocks with any >15% daily move in 90d | 62.3% | −42.0% | 1.89 | 1.48 | CAGR champ, less era-dependent than v1 |
| **B v2 — Vol-Adjusted Dual Momentum** ⭐ | 0.5×(6M÷σ) + 0.5×(12−1M÷σ) | 43.3% | −34.5% | **1.68** | **1.26** | Won **all 3 eras** — recommended core |

v1 comparison (same engine, same data): A 71.9%/−48.9%/MAR 1.47 ·
B 34.0%/−36.3%/Sharpe 1.33. The v2 core added **+9.3 pts CAGR with LOWER
drawdown**; A v2 traded 9 pts of (era-concentrated) CAGR for 7 pts less
drawdown and consistency across eras.

Shared rules (unchanged): Top-N equal weight (A=5, B=10) · buffer band
1.75×N · **30% trailing stop** from post-entry peak · **daily
universe-breadth regime filter** (>50% of stocks above own 200DMA; same-day
exit, 2-day-confirm re-entry) · rebalance **every 2nd Monday**.

⚠️ Backtest carries survivorship bias (today's constituents traded
historically). Realistic live expectations: A ≈ 30–40% CAGR, B ≈ 25–32%,
with −35 to −45% drawdowns. Cost-stress: at double costs (0.5%/side) the
core still backtested at 40.7% CAGR. Not investment advice.

## Deploy (5 minutes)
1. Fork/clone this repo to your GitHub (files at root: `app.py`,
   `requirements.txt`, `Stocks.csv`, `MANUAL.md`).
2. [share.streamlit.io](https://share.streamlit.io) → New app → select repo →
   main file `app.py` → Deploy.

## Data sources
- **Primary: Upstox historical-candle API** (free, no auth, no API key) —
  better coverage than Yahoo, including ~150 recent listings Yahoo misses.
- **Fallback: Yahoo Finance** per symbol. If Upstox returns a truncated
  history (instrument-key resets after relistings), the app fetches both
  and keeps the longer series so no stock silently drops out of the
  12-month rankings. The sidebar shows the per-source counts each session.

## Universe (`Stocks.csv`)
- Required column: `Symbol` (NSE symbols, no `.NS` suffix).
- Optional: `Company Name`, `Industry`, `MarketCap_Cr`.
- Refresh monthly: `python make_universe.py` (needs `pip install yfinance`),
  commit the new file — **or** upload a CSV in the app sidebar (upload
  overrides the repo file).

## App tabs
- **Strategy A v2 / Strategy B v2** — live rankings, Top-N green, buffer
  amber; A shows each stock's `MaxGap %`, B shows `Vol %` and the
  vol-adjusted `Score`
- **Rotation Actions** — paste holdings or upload `portfolio.json` → exact
  BUY / SELL / HOLD list with buffer-band logic; saves entry dates
- **Stop-Loss Tracker** — daily 30% trailing-stop check per holding
- **Manual** — full operating manual (also in `MANUAL.md`)

## How to operate
Read **MANUAL.md**. Short version: every 1st & 3rd Monday — check the regime
banner, open Rotation Actions, execute the table, save `portfolio.json`.
Daily (2 min): check the banner and the Stop tab. Never override the rules.

## Research provenance
- v1: (1) replication of the ValuePickr smallcap momentum thread,
  (2) 243-config sweep on Nifty 500 with look-ahead-bias audit,
  (3) 192-config × 15-year sweep on the 1,000–25,000 Cr band.
- **v2 (Jul 2026)**: literature-driven upgrade study — Barroso &
  Santa-Clara (JFE 2015) volatility management, Clenow *Stocks on the
  Move* gap exclusion + vol-adjusted ranking, NSE momentum-index
  normalised-score methodology, Gray & Vogel *Quantitative Momentum*
  quality screens — each tested on the exact live rules, adopted only
  where the improvement held across all/most 5-year sub-eras AND survived
  doubled transaction costs. Rejected candidates and full evidence tables
  in `RESEARCH_NOTES.md`.
