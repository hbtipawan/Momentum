# 📖 MANUAL — Dual-Strategy Momentum Screener

Large-print operating manual. Follow it mechanically — the backtest edge only
exists if the rules are executed without discretion.

---

## 1. One-time setup

1. **GitHub**: create a repo, put these files in the root: `app.py`,
   `requirements.txt`, `Stocks.csv`, `MANUAL.md`, `README.md`.
2. **Streamlit Cloud**: go to share.streamlit.io → *New app* → pick your repo
   → main file `app.py` → Deploy. Done in ~2 minutes.
3. **Stocks.csv**: one column named `Symbol` is mandatory (NSE symbols, no
   `.NS`). Extra columns (Company Name, Industry, MarketCap_Cr) are optional
   and shown when present. The included file has 419 stocks in the
   1,000–25,000 Cr band. You can also upload a fresh CSV inside the app —
   the upload always overrides the repo file.

---

## 2. The two strategies — pick ONE per book

| | **Strategy A — Fast** | **Strategy B — 12−1 (recommended core)** |
|---|---|---|
| Signal | avg of 1-month and 3-month return | 12-month return, skipping the last month |
| 15y backtest | 52.3% CAGR, −41.5% MaxDD | 42.7% CAGR, −36.4% MaxDD, Sharpe 1.36 |
| Character | Highest CAGR, violent swings, era-dependent | Most consistent across 3 market eras |
| Realistic live | ~30–40% CAGR | ~25–32% CAGR |

Do **not** blend the two books' signals; run them as separate portfolios if
you run both.

---

## 3. The rules (locked)

- **Positions**: Top N equal-weight (default 5; the sidebar lets you pick
  5/10/15 — the 15-year study found 10 the consistency sweet spot for B).
- **Buffer band**: a stock you already hold is kept while its rank stays
  within **1.75 × N** (e.g. Top 5 → keep while rank ≤ 8). This cuts churn.
- **Trailing stop**: **30% below the highest close since YOUR entry**,
  checked daily. If breached → sell at the next open. No exceptions,
  no "waiting for a bounce".
- **Regime filter**: if the banner is **🔴 RED** (Nifty 500 below its 200DMA)
  → sell everything at the rebalance and stay in cash. Re-enter fully when
  the banner turns 🟢 GREEN. Do not cherry-pick.
- **Never leverage. Never average down. A stopped-out stock may only
  re-enter at a future rebalance if it ranks Top N again.**

---

## 4. Rebalance routine — every 2nd Monday (15 minutes)

Do this on the **1st and 3rd Monday of each month**, after 9:30am IST:

1. Open the app. Note the **regime banner** first.
   - 🔴 RED → sell all, download portfolio.json, done. Skip steps 2–5.
2. Open your strategy tab (A or B). The ranking is live.
3. Go to **Rotation Actions** → upload last time's `portfolio.json`
   (or paste your holdings).
4. Execute exactly what the table says:
   - 🔴 SELL rows first (market/limit orders near the open),
   - then 🟢 BUY rows, equal rupee amounts
     (total capital ÷ N per stock).
5. **Download the new portfolio.json** and store it (Drive/email to
   yourself). This file carries your entry dates — the stop tracker
   needs it.

### Daily (2 minutes, optional but recommended)
Open the **Stop-Loss Tracker** tab, upload portfolio.json. If any row says
**🔴 STOP HIT — SELL**, sell that stock at the next open. Between
rebalances the freed cash just sits idle — do not redeploy it early.

---

## 5. Refreshing the universe (monthly, 5 minutes)

Market caps drift. Once a month, regenerate `Stocks.csv` so the band stays
1,000–25,000 Cr:

- Easiest: run `python make_universe.py` from the repo (fetches NSE
  Midcap 150 + Smallcap 250 + Microcap 250 lists, pulls current market caps
  from Yahoo, writes a fresh Stocks.csv) and push it to GitHub, **or**
- upload the fresh CSV directly in the app sidebar.

A stock leaving the band is NOT a sell signal by itself — it exits your
book only via rank decay or stop, at a normal rebalance.

---

## 6. What to expect (read this twice)

From the 15-year backtest (survivorship-bias-adjusted expectations):

- **Drawdowns of −25% to −40% arrive roughly every 3 years** and last
  6–18 months. This is a feature of momentum, not a malfunction.
- There will be **whole years of negative returns while the index is
  positive** (2025 was −17% for Strategy B vs +7% for the Nifty 500).
- The edge shows up over 3+ year horizons. **Write down a minimum 3-year
  commitment before the first trade.** The most common way this system
  fails is the operator quitting in month 9 of a drawdown — the backtest
  edge survived every drawdown; abandoning mid-drawdown locks the loss in.
- Costs matter in microcaps: use limit orders, avoid market orders in
  stocks below ~3,000 Cr, and never place orders in the first 5 minutes.

---

## 7. FAQ

**Q: The app shows different ranks than yesterday — did it break?**
No. Ranks move daily with prices. Only the 2nd-Monday snapshot matters.

**Q: A holding fell to rank 9 (Top 5 book). Sell?**
No — buffer band keeps it while rank ≤ 8… rank 9 is outside → it becomes a
🔴 SELL at the next rebalance. The Rotation tab handles this automatically.

**Q: Stop hit mid-week but it's not rebalance day?**
Sell anyway, next open. Stops are daily; rotation is fortnightly.

**Q: Regime turned RED mid-week?**
The regime rule is checked only on rebalance Mondays. Your 30% stops
protect you between rebalances.

**Q: Can I skip a stock I don't like and take rank 6 instead?**
No. The moment discretion enters, the backtest no longer describes your
system.
