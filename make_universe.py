#!/usr/bin/env python3
"""
make_universe.py — Regenerate Stocks.csv (all NSE index stocks ≥1,000 Cr, NO upper cap)

Strategy A ranks the full list (cap-free validated better for fast momentum);
the app applies the 1,000–25,000 Cr band to Strategy B internally using the
MarketCap_Cr column — so keep that column in the CSV.

Run monthly, then commit the new Stocks.csv to GitHub:
    pip install yfinance pandas
    python make_universe.py
    git add Stocks.csv && git commit -m "universe refresh" && git push

Sources:
  - NSE archives: Nifty Midcap 150 + Smallcap 250 + Microcap 250 lists
  - Yahoo Finance: current market cap per stock
"""
import csv
import io
import sys
import urllib.request
import concurrent.futures

import yfinance as yf

HEADERS = {"User-Agent": "Mozilla/5.0"}
MCAP_MIN_CR = 1000
MCAP_MAX_CR = None          # no upper cap — B's band is applied in-app
INDEX_FILES = [
    "ind_nifty100list.csv",
    "ind_niftymidcap150list.csv",
    "ind_niftysmallcap250list.csv",
    "ind_niftymicrocap250_list.csv",
]


def fetch_index_lists():
    symbols = {}
    for f in INDEX_FILES:
        url = f"https://archives.nseindia.com/content/indices/{f}"
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=20) as resp:
            text = resp.read().decode()
        for r in csv.DictReader(io.StringIO(text)):
            symbols[r["Symbol"]] = {
                "name": r["Company Name"],
                "industry": r["Industry"],
            }
    return symbols


def get_mcap_cr(sym):
    try:
        mc = yf.Ticker(f"{sym}.NS").fast_info["marketCap"]
        return sym, round(mc / 1e7)          # rupees -> crore
    except Exception:
        return sym, None


def main():
    symbols = fetch_index_lists()
    print(f"Index lists fetched: {len(symbols)} unique symbols", file=sys.stderr)

    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
        for i, (sym, mc) in enumerate(ex.map(get_mcap_cr, symbols)):
            symbols[sym]["mcap_cr"] = mc
            if (i + 1) % 100 == 0:
                print(f"  market caps {i+1}/{len(symbols)}", file=sys.stderr)

    rows = sorted(
        (s, v["name"], v["industry"], v["mcap_cr"])
        for s, v in symbols.items()
        if v.get("mcap_cr") and v["mcap_cr"] >= MCAP_MIN_CR
        and (MCAP_MAX_CR is None or v["mcap_cr"] <= MCAP_MAX_CR)
    )
    with open("Stocks.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Symbol", "Company Name", "Industry", "MarketCap_Cr"])
        w.writerows(rows)
    print(f"Stocks.csv written: {len(rows)} stocks (>= {MCAP_MIN_CR} Cr, no upper cap)")


if __name__ == "__main__":
    main()
