# 🏆 Dual-Strategy Momentum Screener (1,000–25,000 Cr)

Streamlit app implementing two momentum rotation strategies validated on a
**15-year backtest (Jul 2011 – Jul 2026, 419-stock universe, 192-config
parameter sweep, bias-corrected)**.

| Strategy | Signal | 15y CAGR | MaxDD | Sharpe | Character |
|---|---|---|---|---|---|
| **A — Fast** | 0.5×1M + 0.5×3M return | 52.3% | −41.5% | 1.12 | CAGR champ, lumpy |
| **B — 12−1** ⭐ | 12M return, skip last month | 42.7% | −36.4% | **1.36** | Most robust — recommended core |

Shared rules: Top-N equal weight (default 5) · buffer band 1.75×N ·
**30% trailing stop** from post-entry peak · **200DMA regime filter** on
Nifty 500 (cash when below) · rebalance **every 2nd Monday**.

⚠️ Backtest carries survivorship bias (today's constituents traded
historically). Realistic live expectations: A ≈ 30–40% CAGR, B ≈ 25–32%,
with −35 to −45% drawdowns. Not investment advice.

## Deploy (5 minutes)
1. Fork/clone this repo to your GitHub (files at root: `app.py`,
   `requirements.txt`, `Stocks.csv`, `MANUAL.md`).
2. [share.streamlit.io](https://share.streamlit.io) → New app → select repo →
   main file `app.py` → Deploy.

## Universe (`Stocks.csv`)
- Required column: `Symbol` (NSE symbols, no `.NS` suffix).
- Optional: `Company Name`, `Industry`, `MarketCap_Cr`.
- Included file: 419 stocks currently in the 1,000–25,000 Cr band.
- Refresh monthly: `python make_universe.py` (needs `pip install yfinance`),
  commit the new file — **or** upload a CSV in the app sidebar (upload
  overrides the repo file).

## App tabs
- **Strategy A / Strategy B** — live rankings, Top-N green, buffer amber
- **Rotation Actions** — paste holdings or upload `portfolio.json` → exact
  BUY / SELL / HOLD list with buffer-band logic; saves entry dates
- **Stop-Loss Tracker** — daily 30% trailing-stop check per holding, with
  distance-to-stop and breach alerts
- **Manual** — full operating manual (also in `MANUAL.md`)

## How to operate
Read **MANUAL.md**. Short version: every 1st & 3rd Monday — check the regime
banner, open Rotation Actions, execute the table, save `portfolio.json`.
Daily (2 min): check the Stop tab. Never override the rules.

## Research provenance
Built from a 3-stage study: (1) replication of the ValuePickr smallcap
momentum thread, (2) 243-config sweep on Nifty 500 with a look-ahead-bias
audit, (3) 192-config × 15-year sweep on the 1,000–25,000 Cr band with
sub-period robustness testing. Strategy B's 12−1 signal matches the academic
momentum standard (Jegadeesh–Titman 1993).
