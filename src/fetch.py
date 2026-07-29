"""Pull raw financial data for the bank universe.

Every pull is tagged with `as_of` (the date the data reflects) and cached to
data/raw/{ticker}/{as_of}.json. Stage 1 only ever calls this with
as_of=today (today's live snapshot from Yahoo Finance), but the on-disk
layout and function signature are already keyed by as_of so that a future
Stage 4 backtest can add a second fetcher (e.g. pulling historical filed
financials) that writes into the same cache under past dates without
touching the processed data shape or any downstream code.
"""

import datetime as dt
import json
from pathlib import Path

import yfinance as yf

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

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

    as_of defaults to today. Historical as_of values are not fetchable from
    Yahoo's .info endpoint (it only ever returns "now") - that's the gap
    Stage 4 will need a different data source for. This function's shape
    already accounts for that: callers pass as_of, get back cached-or-fresh
    data, and don't need to know which source served it.
    """
    as_of = as_of or dt.date.today().isoformat()
    path = _cache_path(ticker, as_of)

    if use_cache and path.exists():
        with open(path) as f:
            return json.load(f)

    if as_of != dt.date.today().isoformat():
        raise NotImplementedError(
            f"No historical data source wired up yet for {ticker} as_of={as_of}. "
            "Stage 1 only supports as_of=today (live Yahoo Finance snapshot)."
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
