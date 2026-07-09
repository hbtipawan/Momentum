# 🔬 RESEARCH_NOTES — v2 Upgrade Study (Jul 2026)

Honest record of what was tested, what was adopted, and what was
**rejected**. Keep this file in the repo so future "improvement ideas" can
be checked against evidence before touching the locked rules.

## Method

- **Data**: Yahoo Finance daily closes, Jul 2010 – Jul 2026, for the 982
  symbols in the current Stocks.csv 1,000–25,000 Cr band that have >1y of
  history (232 recent listings unfetchable — invisible to any backtest).
- **Engine**: exact live rules — rebalance 1st & 3rd Monday, Top-N equal
  weight, buffer 1.75×N, 30% trailing stop (exit next close), universe
  breadth regime (>50% above own 200DMA, same-day exit at close, 2-day
  confirm re-entry), CMP > ₹20, cash earns 0%, **0.25% costs per side**.
- **Test window**: Jul 2011 – Jul 2026 (1y warm-up for 252d signals).
- **Bias**: survivorship (current constituents). Inflates ALL absolute
  CAGRs equally → only **relative** comparisons and era-consistency were
  used for adoption decisions. Absolute numbers are NOT live expectations.
- **Adoption bar**: a change is adopted only if it (a) improves CAGR or
  MAR over the full period, (b) wins in at least 2 of 3 five-year eras,
  and (c) survives doubled costs (0.5%/side).

## Full results (Jul 2011 – Jul 2026, 0.25%/side)

| Variant | CAGR | MaxDD | Sharpe | MAR |
|---|---|---|---|---|
| A v1 baseline (0.5×1M+3M, N5) | 71.9% | −48.9% | 1.99 | 1.47 |
| **A v2 = A + gap filter (N5)** ✅ | 62.3% | −42.0% | 1.89 | **1.48** |
| A + vol-adjusted score (N5) | 64.2% | −47.9% | 1.91 | 1.34 |
| A + vol-adj + gap (N5) | 47.9% | −40.7% | 1.54 | 1.17 |
| A v1 at N10 | 56.0% | −41.6% | 1.90 | 1.34 |
| A + gap at N10 | 43.4% | −37.9% | 1.64 | 1.15 |
| B v1 baseline (12−1, N10) | 34.0% | −36.3% | 1.33 | 0.94 |
| B + gap filter (N10) | 32.5% | −36.7% | 1.36 | 0.89 |
| B vol-adjusted 12−1 only (N10) | 35.2% | −34.8% | 1.42 | 1.01 |
| **B v2 = dual-lookback vol-adj (N10)** ✅ | **43.3%** | **−34.5%** | **1.68** | **1.26** |
| B v2 at N5 | 44.9% | −37.6% | 1.51 | 1.19 |
| B v2 + gap filter (N10) | 37.4% | −30.9% | 1.59 | 1.21 |
| B v2 + 25% vol-target (N10) | 37.2% | −32.4% | 1.49 | 1.15 |
| B vol-adj, 25% stop (N10) | 34.9% | −35.9% | 1.42 | 0.97 |
| B vol-adj, 20% stop (N10) | 35.2% | −35.5% | 1.45 | 0.99 |

## Era robustness (CAGR / MaxDD per 5-year era)

| Variant | 2011–16 | 2016–21 | 2021–26 |
|---|---|---|---|
| A v1 | 15.8% / −39.8% | 145.2% / −36.1% | 77.6% / −48.9% |
| **A v2 (gap)** | **28.8% / −20.2%** | 80.0% / −28.3% | **83.9% / −42.0%** |
| B v1 (12−1) | 26.5% / −26.7% | 42.9% / −24.7% | 33.4% / −36.3% |
| **B v2 (dual vol-adj)** | **27.5% / −29.7%** | **43.0% / −27.6%** | **61.1% / −34.5%** |
| B v2 + gap | 31.0% / −26.0% | 18.8% / −26.1% | 66.0% / −30.9% |

## Adopted

1. **Strategy B v2 — vol-adjusted dual-lookback momentum**
   `score = 0.5×(6M return ÷ ann.σ₁₂₆) + 0.5×(12−1M return ÷ ann.σ₂₅₂)`
   (NSE-momentum-index normalised score; Clenow; Barroso–Santa-Clara
   risk-scaling logic applied at the ranking level).
   Evidence: +9.3 pts CAGR with lower MaxDD and Sharpe 1.33→1.68; **won
   all three eras**; at double costs still 40.7% CAGR; yearly table shows
   it beat plain 12−1 in 10 of 15 calendar years, including 2025
   (+13.6% vs −4.2%).

2. **Strategy A v2 — anti-speculation gap filter**
   Exclude any stock whose largest single-day move in the last 90 trading
   days exceeds 15% (Clenow's exclusion; the "quality momentum /
   frog-in-the-pan" idea).
   Evidence: MaxDD −48.9%→−42.0% at equal MAR; won eras 1 and 3 outright
   (2011–16 CAGR 15.8%→28.8% with DD −39.8%→−20.2%); the only era it lost
   was the 2016–21 smallcap melt-up, i.e. v1's full-period CAGR advantage
   was concentrated in a single regime. Survives double costs (56.8%).

## Rejected (do NOT re-add without new evidence)

- **Gap filter on Strategy B** — lowered CAGR in every configuration
  (34.0→32.5 on v1; 43.3→37.4 on v2). B's 12-month lookback already
  avoids most gap-driven speculation; the filter only removes CAGR.
  (The B v2+gap variant is the max-defence option — −30.9% MaxDD — noted
  here in case a lower-risk phase of life ever wants it.)
- **Vol-adjusted score on Strategy A** — 1M/3M returns divided by vol
  underperformed the plain fast signal with the gap filter (47.9% vs
  62.3% CAGR when combined). Short-lookback momentum needs the raw
  aggression; the gap filter alone removes the toxic tail.
- **Tighter trailing stops (20%, 25%)** — <1 pt CAGR change, ≤0.8 pt DD
  change. 30% stays; the regime filter, not the stop, is the drawdown
  engine.
- **Portfolio volatility targeting (25% target, deleverage-only)** —
  the Barroso–Santa-Clara portfolio-level scaler cost ~6 pts CAGR on the
  v2 core for ~2 pts of DD. The vol adjustment is more efficient inside
  the ranking than on top of the equity curve, because the breadth regime
  filter already does the de-risking that vol-targeting duplicates.

## Known limitations (unchanged from v1)

- Survivorship bias: absolute CAGRs are inflated; use the README's
  "realistic live" band for planning.
- Stop/regime exits modelled at closes (live = next open); costs modelled
  flat 0.25%/side — microcap impact can exceed this in stress.
- 2026 YTD is negative for both books; no signal wins every year.
- The single biggest live-performance risk remains operator discretion
  (skipping ranks, delaying regime exits, overriding stops) — no signal
  change fixes that.
