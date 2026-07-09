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
- **Regime filter (universe breadth, checked DAILY)**: the app measures what
  fraction of YOUR universe's stocks close above their own 200-day moving
  average. Risk-on requires **more than 50%**. If the banner turns **🔴 RED**
  → **sell everything the SAME day** (at close or next morning's open) — do
  NOT wait for rebalance day. **Re-entry (2-day confirm rule)**: once breadth
  has closed above 50% for **2 consecutive days**, re-enter the full book the
  same day — don't wait for Monday. (15-year backtest: this fast re-entry
  added ~1% CAGR AND cut MaxDD from −34% to −31% vs waiting for rebalance
  day; 3- and 5-day confirms tested worse.) Do not cherry-pick.
  *Why breadth instead of a Nifty index?* Your universe is equal-weight and
  small/midcap-heavy; a cap-weighted index can stay green while the median
  stock is already in a bear market. In the 15-year backtest the breadth
  gauge with same-day exit cut the worst drawdown to −29% (vs −40% for the
  Nifty-500 gauge) and held it to −19% through the 2018–20 smallcap bear,
  with Sharpe 1.52. It flips ~7×/year and keeps you invested only ~55% of
  the time — long cash spells are normal, not a bug.
- **Never leverage. Never average down. A stopped-out stock may only
  re-enter at a future rebalance if it ranks Top N again.**

---

## 4. Rebalance routine — every 2nd Monday (15 minutes)

Do this on the **1st and 3rd Monday of each month**, after 9:30am IST:

1. Open the app. Note the **regime banner** first.
   - 🔴 RED → you should already be in cash (the daily rule below); if
     anything is still held, sell it now. Skip steps 2–5.
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

### Daily (2 minutes — NOT optional)
Open the app once a day, after 3pm IST or in the evening:
1. **Regime banner**: if it turned 🔴 RED today → sell ALL positions at the
   close or tomorrow's open. This same-day exit is what earns the drawdown
   protection — waiting for rebalance day gave up 2–7% extra drawdown in
   the backtest.
2. **Stop-Loss Tracker** tab, upload portfolio.json. Any row with
   **🔴 STOP HIT — SELL** → sell at the next open.
Between rebalances, freed cash sits idle — do not redeploy it early.

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
Sell everything the same day (close or next open). The backtest showed
same-day exit beats waiting for rebalance day. Re-entry uses the 2-day
confirm: the second consecutive close with breadth above 50%, buy the
full book that day. The app banner counts the green days for you.

**Q: The banner flips GREEN then RED within a few days — whipsaw?**
Yes, it happens (~7 flips/year historically). Take the small costs; they
are the insurance premium that kept the worst drawdown at −29% over 15
years. Never second-guess the banner.

**Q: Can I skip a stock I don't like and take rank 6 instead?**
No. The moment discretion enters, the backtest no longer describes your
system.
