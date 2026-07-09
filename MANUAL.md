# 📖 MANUAL — Dual-Strategy Momentum Screener **v2**

Large-print operating manual. Follow it mechanically — the backtest edge only
exists if the rules are executed without discretion.

**What changed in v2 (Jul 2026 research upgrade):** the two ranking signals
were upgraded after a fresh 15-year re-validation (2011–2026, 982-stock
1,000–25,000 Cr band, per-era robustness testing, 0.25%/side costs).
Everything else — stops, regime filter, buffer band, rebalance routine —
is UNCHANGED and stays locked. Full evidence in `RESEARCH_NOTES.md`.

---

## 1. One-time setup

1. **GitHub**: create a repo, put these files in the root: `app.py`,
   `requirements.txt`, `Stocks.csv`, `MANUAL.md`, `README.md`.
2. **Streamlit Cloud**: go to share.streamlit.io → *New app* → pick your repo
   → main file `app.py` → Deploy. Done in ~2 minutes.
3. **Stocks.csv**: one column named `Symbol` is mandatory (NSE symbols, no
   `.NS`). Extra columns (Company Name, Industry, MarketCap_Cr) are optional
   and shown when present. You can also upload a fresh CSV inside the app —
   the upload always overrides the repo file.

---

## 2. The two strategies — pick ONE per book

| | **Strategy A v2 — Fast + Gap Filter** | **Strategy B v2 — Vol-Adjusted Dual Momentum (recommended core)** |
|---|---|---|
| Signal | avg of 1-month and 3-month return; **stocks with any daily move >15% in the last 90 days are excluded** | **0.5×(6M return ÷ ann. volatility) + 0.5×(12−1M return ÷ ann. volatility)** |
| Default N | 5 | 10 |
| 15y re-validation | 62.3% CAGR, −42.0% MaxDD, MAR 1.48 | 43.3% CAGR, −34.5% MaxDD, Sharpe 1.68, MAR 1.26 |
| vs old signal | old A: 71.9% CAGR but −48.9% DD and only 15.8% CAGR in 2011–16; v2 won 2 of 3 eras with 7 pts less drawdown | old 12−1: 34.0% CAGR, −36.3% DD, Sharpe 1.33; **v2 won ALL THREE eras** |
| Character | Highest CAGR, violent swings, less era-dependent than before | Most consistent; turned 2025 from −4.2% (old) to +13.6% (v2) |
| Realistic live | ~30–40% CAGR | ~25–32% CAGR |

⚠️ The backtest CAGRs above carry survivorship bias (today's constituents
traded historically) — treat the "Realistic live" row as the honest
expectation. The RELATIVE edge of v2 over v1 is the validated result.

Do **not** blend the two books' signals; run them as separate portfolios if
you run both. The app applies the gap filter (A) and the vol adjustment (B)
automatically — you never compute anything by hand.

---

## 3. The rules (locked)

- **Positions**: Top N equal-weight (default A=5, B=10; the sidebar lets you
  pick 5/10/15 — 10 remains the consistency sweet spot for the core book).
- **Buffer band**: a stock you already hold is kept while its rank stays
  within **1.75 × N** (e.g. Top 10 → keep while rank ≤ 17). This cuts churn.
- **Trailing stop**: **30% below the highest close since YOUR entry**,
  checked daily. If breached → sell at the next open. No exceptions,
  no "waiting for a bounce". (Re-tested in v2: 20% and 25% stops changed
  CAGR by <1 pt — 30% stays.)
- **Regime filter (universe breadth, checked DAILY)**: the app measures what
  fraction of YOUR universe's stocks close above their own 200-day moving
  average. Risk-on requires **more than 50%**. If the banner turns **🔴 RED**
  → **sell everything the SAME day** (at close or next morning's open) — do
  NOT wait for rebalance day. **Re-entry (2-day confirm rule)**: once breadth
  has closed above 50% for **2 consecutive days**, re-enter the full book the
  same day — don't wait for Monday. Long cash spells are normal, not a bug
  (the book sat ~100% cash through most of 2019 — that flat year IS the
  drawdown protection working).
- **Risk-off sleeve (what the cash does while the banner is RED)**: the
  freed capital does NOT sit idle. The rule, shown live on the banner:
  - if GOLDBEES is ABOVE its own 200DMA → park 100% of it in **GOLDBEES**;
  - if GOLDBEES is BELOW its 200DMA → park it in a **liquid/arbitrage
    fund** instead. Never hold gold against its own downtrend.
  When the 2-day-confirm re-entry fires, sell the sleeve and buy the full
  equity book the same day. 15y evidence (RESEARCH_NOTES.md): this sleeve
  lifted the core book's CAGR from 43.3% to 59.9% at the SAME worst
  drawdown, and it won all three 5-year eras — gold tends to rally in
  exactly the risk-off windows when breadth fails, and the 200DMA check
  keeps you out of gold's own bear phases (e.g. 2013–15).
- **Never leverage. Never average down. A stopped-out stock may only
  re-enter at a future rebalance if it ranks Top N again.**

---

## 4. Rebalance routine — Mondays, tranched (8–15 minutes)

**Why Monday at all?** Tested: all five weekdays, both books, era-by-era.
No weekday has a robust edge — Friday looked +7 pts better for Strategy A
but won only 7 of 15 years and the edge INVERTED under a one-week phase
shift, i.e. timing luck. The "Monday crowding" fear shows no measurable
tax at this fortnightly frequency. What DOES matter is phase: 1st&3rd vs
2nd&4th Mondays differed by ±4 pts CAGR — also pure luck.

**The fix is TRANCHING (recommended): split capital into two half-books.**
- **Tranche 1**: rebalance on the **1st and 3rd Monday** of each month.
- **Tranche 2**: rebalance on the **2nd and 4th Monday**.
Each tranche runs the full rules on half the capital with its own
`portfolio.json`. Every Monday you touch exactly one tranche. 15y
evidence (B v2 core): CAGR 43.3%→45.7%, MaxDD −34.5%→−31.3%, MAR
1.26→1.46, better in all three eras — not by predicting the lucky phase,
but by averaging the luck away. If you prefer operational simplicity,
running a single book on 1st & 3rd Mondays remains valid — you are just
accepting a ±4 pt luck band around the expected result.

On your tranche's Monday, after 9:30am IST:

1. Open the app. Note the **regime banner** first.
   - 🔴 RED → you should already be in cash (the daily rule below); if
     anything is still held, sell it now. Skip steps 2–5.
2. Open your strategy tab (A or B). The ranking is live.
3. Go to **Rotation Actions** → upload THIS TRANCHE's last
   `portfolio.json` (or paste its holdings). Keep the two tranche files
   separate — name them e.g. `portfolio_T1.json` / `portfolio_T2.json`.
4. Execute exactly what the table says:
   - 🔴 SELL rows first (market/limit orders near the open),
   - then 🟢 BUY rows, equal rupee amounts
     (total capital ÷ N per stock).
5. **Download the new portfolio.json** and store it (Drive/email to
   yourself). This file carries your entry dates — the stop tracker
   needs it.

### The YTD strip (under the regime banner)
Three tiles show the simulated year-to-date result of **A v2**, **B v2**
(both at your sidebar's Top-N) and the **Nifty 500**, with each one's
worst drawdown this year. It is a *discipline gauge*, not your live P&L:
it assumes perfect rule-following at 0.25%/side. Two rules for reading it:
(1) if the books trail the index in a RED/choppy year but with smaller
drawdowns, the system is WORKING — do not tinker; (2) never judge the
strategy on this strip — the edge is measured in 3-year windows, not
calendar half-years.

### Daily (2 minutes — NOT optional)
Open the app once a day, after 3pm IST or in the evening:
1. **Regime banner**: if it turned 🔴 RED today → sell ALL positions at the
   close or tomorrow's open. This same-day exit is what earns the drawdown
   protection.
2. **Stop-Loss Tracker** tab, upload portfolio.json. Any row with
   **🔴 STOP HIT — SELL** → sell at the next open.
Between rebalances, freed cash sits idle — do not redeploy it early.

---

## 5. Refreshing the universe (monthly, 5 minutes)

Market caps drift. Once a month, regenerate `Stocks.csv`:

- Easiest: run `python make_universe.py` from the repo and push it to
  GitHub, **or**
- upload the fresh CSV directly in the app sidebar.

A stock leaving the band is NOT a sell signal by itself — it exits your
book only via rank decay or stop, at a normal rebalance.

---

## 6. What to expect (read this twice)

From the 15-year re-validation (survivorship-bias-adjusted expectations):

- **Drawdowns of −25% to −40% arrive roughly every 3 years** and last
  6–18 months. This is a feature of momentum, not a malfunction. The v2
  core's worst year was 2022 (−18.5%); the old signal's was −24.4%.
- There will be **flat or negative stretches while the index is positive** —
  including whole years spent mostly in cash (2019). The v2 core turned the
  old signal's 2025 loss (−4.2%) into +13.6%, but 2026 YTD is negative for
  both. No signal wins every year.
- The edge shows up over 3+ year horizons. **Write down a minimum 3-year
  commitment before the first trade.** The most common way this system
  fails is the operator quitting in month 9 of a drawdown.
- Costs matter in microcaps: use limit orders, avoid market orders in
  stocks below ~3,000 Cr, and never place orders in the first 5 minutes.
  (v2 signals were stress-tested at double costs — 0.5% per side — and the
  core still delivered 40.7% CAGR in-backtest, so realistic slippage does
  not kill the edge.)

---

## 7. FAQ

**Q: Where does the price data come from?**
Upstox's free historical API first (no login needed), Yahoo Finance as
fallback — and whichever has the LONGER history wins per stock. The
sidebar shows how many symbols came from each source. If the Upstox
instrument master is unreachable, the app warns you and runs pure-Yahoo
for that session.

**Q: The app shows different ranks than yesterday — did it break?**
No. Ranks move daily with prices. Only the 2nd-Monday snapshot matters.

**Q: Why did a huge recent winner not appear in Strategy A?**
Check its `MaxGap %` — if it had any single day move above 15% in the last
90 days, the anti-speculation filter excludes it by design. Those
gap-driven names are where the old signal's worst drawdowns lived.

**Q: Why does Strategy B rank a 150% stock above a 300% stock?**
Because the 300% stock was twice as volatile. The v2 score is return ÷
volatility — smooth risers beat erratic rockets. This single change is
what won all three eras.

**Q: A holding fell outside the buffer band. Sell?**
Yes — at the next rebalance. The Rotation tab handles this automatically.

**Q: Stop hit mid-week but it's not rebalance day?**
Sell anyway, next open. Stops are daily; rotation is fortnightly.

**Q: Regime turned RED mid-week?**
Sell everything the same day (close or next open). Re-entry uses the 2-day
confirm: the second consecutive close with breadth above 50%, buy the
full book that day. The app banner counts the green days for you.

**Q: The banner flips GREEN then RED within a few days — whipsaw?**
Yes, it happens (~7 flips/year historically). Take the small costs; they
are the insurance premium on the worst drawdowns. Never second-guess the
banner.

**Q: Can I skip a stock I don't like and take rank 6 instead?**
No. The moment discretion enters, the backtest no longer describes your
system.

**Q: Shouldn't I rebalance on Friday to front-run the Monday crowd?**
Tested — no. Friday's apparent edge on Strategy A was concentrated in a
few lucky years and flipped negative when the weeks were phase-shifted.
No weekday is robustly better. Tranche across two Monday phases instead;
that's the only timing change the evidence supports.

**Q: Why gold and not just a liquid fund when RED?**
Both were backtested. Liquid-only added ~4 pts CAGR over idle cash;
gold-with-trend-check added ~17 pts at the same drawdown, because equity
risk-off and gold rallies overlap (2011, 2016, 2020, 2022, 2025–26). The
trend check matters: holding gold ALWAYS during RED was worse in 2011–16
(gold's own bear) — the 200DMA switch is what makes it robust. Note gold
ETF taxation differs from equity; check the current rules with your CA.

**Q: What about volatility targeting / tighter stops / gap filter on B?**
All tested in the Jul 2026 study and REJECTED — see `RESEARCH_NOTES.md`
for the numbers. Do not add them by hand.
