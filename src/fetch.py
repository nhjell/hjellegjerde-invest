"""Fetch and cache Yahoo Finance data for the configured bank universe.

Run ``python src/fetch.py`` to populate today's snapshot and annual-history
cache, or add ``--refresh`` to replace today's cached files. Every snapshot is
tagged with ``as_of`` and stored under ``data/raw/{ticker}/{as_of}.json``.

Yahoo's ``.info`` endpoint only represents the current information set. The
date-keyed cache is useful for reproducibility, but it is not a historical
point-in-time fundamentals source.
"""

import argparse
import datetime as dt
import json
from pathlib import Path

import yfinance as yf

from config import load_universe
from utils import get_logger

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
logger = get_logger(__name__)

# The .info fields we need to compute ROE, dividend yield, payout ratio, P/B.
FIELDS = [
    "shortName",
    "priceToBook",
    "returnOnEquity",
    "dividendYield",
    "payoutRatio",
    "trailingEps",
    "bookValue",
    "currentPrice",
    "currency",
]


def _cache_path(ticker: str, as_of: str) -> Path:
    return RAW_DIR / ticker / f"{as_of}.json"


def fetch_snapshot(ticker: str, as_of: str | None = None, use_cache: bool = True) -> dict:
    """Fetch (or load from cache) the raw data for one ticker as of a given date.

    ``as_of`` defaults to today. Historical values are not fetchable from
    Yahoo's ``.info`` endpoint because it only returns the current snapshot.
    A point-in-time backtest therefore needs a different fundamentals source.
    Callers still receive the same cached-or-fresh record shape.
    """
    as_of = as_of or dt.date.today().isoformat()
    path = _cache_path(ticker, as_of)

    if use_cache and path.exists():
        with open(path) as f:
            return json.load(f)

    if as_of != dt.date.today().isoformat():
        raise NotImplementedError(
            f"No historical data source wired up yet for {ticker} as_of={as_of}. "
            "Yahoo Finance snapshots only support as_of=today."
        )

    info = yf.Ticker(ticker).info
    record = {k: info.get(k) for k in FIELDS}
    record["ticker"] = ticker
    record["as_of"] = as_of

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(record, f, indent=2)

    return record


def fetch_universe_snapshot(banks: list[dict], as_of: str | None = None, use_cache: bool = True) -> list[dict]:
    """Fetch snapshots for every bank in the universe, merging in name/country."""
    records = []
    for bank in banks:
        raw = fetch_snapshot(bank["yahoo_ticker"], as_of=as_of, use_cache=use_cache)
        records.append({**raw, "name": bank["name"], "country": bank["country"]})
    return records


# --- Annual fundamentals history (for forecast normalisation & trend) -------
# Cached separately from the snapshot cache: data/raw/history/{ticker}_{as_of}.json
# (the snapshot loader globs data/raw/{ticker}/*.json, so history must not land there).
HISTORY_DIR = RAW_DIR / "history"


def fetch_annual_history(ticker: str, as_of: str | None = None, use_cache: bool = True) -> list[dict]:
    """Fetch (or load from cache) per-fiscal-year ROE / payout / BVPS for one ticker.

    Uses yfinance annual statements (~4 years is all the free endpoint exposes).
    Each row: {fiscal_year_end, roe, payout_ratio, bvps}. Rows are chronological
    (oldest first). ROE is net income / year-end equity, payout is cash
    dividends paid / net income - the same definitions the exploratory
    backtests used.
    """
    as_of = as_of or dt.date.today().isoformat()
    path = HISTORY_DIR / f"{ticker}_{as_of}.json"

    if use_cache and path.exists():
        with open(path) as f:
            return json.load(f)

    t = yf.Ticker(ticker)
    fin, bs, cf = t.financials, t.balance_sheet, t.cashflow
    rows = []
    if not fin.empty and not bs.empty:
        for date in fin.columns:
            try:
                net_income = fin.loc["Net Income", date]
                equity = bs.loc["Stockholders Equity", date]
                shares = bs.loc["Ordinary Shares Number", date]
                div_paid = (
                    abs(cf.loc["Cash Dividends Paid", date])
                    if "Cash Dividends Paid" in cf.index else None
                )
            except KeyError:
                continue
            import pandas as pd
            if pd.isna(net_income) or pd.isna(equity) or pd.isna(shares) or shares == 0 or net_income == 0:
                continue
            rows.append(
                {
                    "fiscal_year_end": str(pd.Timestamp(date).date()),
                    "roe": float(net_income / equity),
                    "payout_ratio": float(div_paid / net_income) if div_paid is not None and not pd.isna(div_paid) else None,
                    "bvps": float(equity / shares),
                }
            )
    rows.sort(key=lambda r: r["fiscal_year_end"])

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(rows, f, indent=2)
    return rows


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Cache current Yahoo Finance data for config/universe.yaml."
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="redownload and overwrite today's cached data",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--snapshot-only",
        action="store_true",
        help="fetch market/fundamental snapshots but not annual history",
    )
    mode.add_argument(
        "--history-only",
        action="store_true",
        help="fetch annual history but not current snapshots",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    banks = load_universe()
    use_cache = not args.refresh
    failures = []

    for bank in banks:
        ticker = bank["yahoo_ticker"]
        try:
            if not args.history_only:
                fetch_snapshot(ticker, use_cache=use_cache)
            if not args.snapshot_only:
                fetch_annual_history(ticker, use_cache=use_cache)
            logger.info("Cached %s", ticker)
        except Exception as exc:
            failures.append(ticker)
            logger.error("Failed to fetch %s: %s", ticker, exc)

    completed = len(banks) - len(failures)
    print(f"\nCached data for {completed}/{len(banks)} banks in {RAW_DIR}")
    if failures:
        print(f"Failed tickers: {', '.join(failures)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
