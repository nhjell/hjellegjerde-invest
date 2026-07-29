"""Systematic relative-value backtest scaffold for the residual income model.

Strategy under test
-------------------
At each rebalance date: using only data available on or before that date,
estimate each bank's trailing ROE, payout and cost of equity, mechanically roll
those into a configurable-horizon residual income valuation, rank banks by
mispricing, buy the top-N most undervalued (equal weight), and hold until the
next rebalance. The
benchmark is the equal-weighted universe.

Anti-lookahead contract
------------------------
`generate_point_in_time_assumptions` and the valuation step must only ever see
fundamentals with a report/effective date <= the rebalance date, and prices up
to the rebalance date. The performance metrics below operate purely on realised
forward returns. The data-assembly functions are written against a point-in-time
fundamentals source (not yet wired to a historical feed - see the note in
run_relative_value_backtest); the metrics functions are complete and usable now.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from residual_income_model import value_all_banks
from utils import get_logger

logger = get_logger(__name__)

TRADING_DAYS = 252


def get_rebalance_dates(price_data: pd.DataFrame | pd.Series, frequency: str = "Q") -> pd.DatetimeIndex:
    """Rebalance dates at the given frequency, snapped to the last available
    trading day on or before each period end (so we never trade on a date with
    no price). `frequency`: 'M', 'Q', or 'A' (pandas period aliases).

    price_data is indexed by date (a Series of prices or a DataFrame of them).
    """
    idx = pd.DatetimeIndex(price_data.index).sort_values()
    if len(idx) == 0:
        return pd.DatetimeIndex([])
    alias = {"M": "ME", "Q": "QE", "A": "YE"}.get(frequency.upper(), frequency)
    period_ends = pd.date_range(idx.min(), idx.max(), freq=alias)
    dates = []
    for pe in period_ends:
        on_or_before = idx[idx <= pe]
        if len(on_or_before):
            dates.append(on_or_before[-1])
    return pd.DatetimeIndex(pd.unique(pd.DatetimeIndex(dates)))


def generate_point_in_time_assumptions(
    fundamentals_history: pd.DataFrame,
    as_of: pd.Timestamp,
    forecast_cfg: dict,
    coe_by_ticker: dict,
) -> pd.DataFrame:
    """Build forecast + terminal assumptions from data known at `as_of`.

    fundamentals_history: long DataFrame with at least
        ticker, report_date, roe, payout_ratio, country
    Only rows with report_date <= as_of are used (no lookahead). Each ticker's
    trailing history feeds src/forecast.py's build_assumption_rows - the same
    normalise / trend-tilt / persistence-decay / terminal-spread generator the
    live model uses - so the backtest values banks exactly the way the live
    pipeline does, just with an earlier information set.
    """
    from forecast import build_assumption_rows  # shared with build_inputs.py

    available = fundamentals_history[fundamentals_history["report_date"] <= as_of]
    rows = []
    for ticker, grp in available.groupby("ticker"):
        grp = grp.sort_values("report_date")
        country = grp.iloc[-1]["country"]
        if ticker not in coe_by_ticker:
            continue
        roe_hist = grp["roe"].tolist()
        payout_hist = grp["payout_ratio"].tolist()
        result = build_assumption_rows(
            ticker=ticker, country=country, coe=coe_by_ticker[ticker],
            current_roe=roe_hist[-1] if roe_hist else None,
            current_payout=payout_hist[-1] if payout_hist else None,
            roe_history=roe_hist[:-1], payout_history=payout_hist[:-1],
            forecast_cfg=forecast_cfg,
        )
        if result is None:
            continue
        rows.extend(result[0])
    return pd.DataFrame(rows)


def run_relative_value_backtest(
    price_data: pd.DataFrame,
    fundamentals_history: pd.DataFrame,
    bvps_history: pd.DataFrame,
    forecast_cfg: dict,
    coe_by_ticker: dict,
    top_n: int = 5,
    frequency: str = "Q",
) -> pd.DataFrame:
    """Run the point-in-time relative value backtest.

    price_data: wide DataFrame (index=date, columns=tickers) of adjusted prices.
    bvps_history: long DataFrame (ticker, report_date, bvps, actual_pb) for
        point-in-time book value. At each rebalance we value banks with the RI
        model, rank by mispricing, and hold the top_n equal-weighted vs the
        equal-weighted universe benchmark.

    Returns a per-period DataFrame: rebalance_date, strategy_return,
    benchmark_return, holdings.

    NOTE: this requires a historical point-in-time fundamentals feed supplied
    by the caller. Yahoo Finance's current snapshot endpoint cannot reconstruct
    the information set available on an arbitrary past date. The loop itself
    enforces its no-lookahead date filters.
    """
    rebal_dates = get_rebalance_dates(price_data, frequency)
    records = []
    for i, date in enumerate(rebal_dates[:-1]):
        next_date = rebal_dates[i + 1]
        assumptions = generate_point_in_time_assumptions(
            fundamentals_history, date, forecast_cfg, coe_by_ticker
        )
        bv = bvps_history[bvps_history["report_date"] <= date]
        if assumptions.empty or bv.empty:
            continue
        latest_bv = (bv.sort_values("report_date").groupby("ticker").tail(1)
                     [["ticker", "country", "bvps", "actual_pb"]])
        ranked = value_all_banks(latest_bv, assumptions, horizon=forecast_cfg["horizon_years"])
        if ranked.empty:
            continue

        picks = ranked.head(top_n)["ticker"].tolist()
        universe = ranked["ticker"].tolist()
        fwd = _forward_returns(price_data, date, next_date, universe)
        if not fwd:
            continue
        strat_ret = np.mean([fwd[t] for t in picks if t in fwd]) if any(t in fwd for t in picks) else np.nan
        bench_ret = np.mean(list(fwd.values()))
        records.append({
            "rebalance_date": date, "next_date": next_date,
            "strategy_return": strat_ret, "benchmark_return": bench_ret,
            "excess_return": strat_ret - bench_ret, "holdings": ", ".join(picks),
        })
    return pd.DataFrame(records)


def _forward_returns(price_data, start, end, tickers) -> dict:
    """Simple price return between two dates for each ticker with data at both."""
    out = {}
    for t in tickers:
        if t not in price_data.columns:
            continue
        s = price_data[t].dropna()
        p0 = s[s.index <= start]
        p1 = s[s.index <= end]
        if len(p0) and len(p1):
            out[t] = p1.iloc[-1] / p0.iloc[-1] - 1.0
    return out


def calculate_strategy_returns(backtest_df: pd.DataFrame, return_col: str = "strategy_return") -> pd.Series:
    """Compound per-period returns into a cumulative growth-of-$1 curve."""
    r = backtest_df.set_index("rebalance_date")[return_col].dropna()
    return (1 + r).cumprod()


def calculate_performance_metrics(
    returns: pd.Series,
    benchmark: pd.Series | None = None,
    periods_per_year: int = 4,
    risk_free_rate: float = 0.0,
) -> dict:
    """Standard performance stats from a series of per-period returns.

    returns: per-period simple returns (index = rebalance dates). Reports CAGR,
    annualised volatility, Sharpe, max drawdown, hit rate, average period return,
    and benchmark excess return (annualised) when a benchmark is supplied.
    """
    r = pd.Series(returns).dropna()
    if r.empty:
        return {k: np.nan for k in
                ("cagr", "volatility", "sharpe", "max_drawdown", "hit_rate",
                 "avg_period_return", "n_periods", "benchmark_excess_return")}

    n = len(r)
    growth = (1 + r).prod()
    years = n / periods_per_year
    cagr = growth ** (1 / years) - 1 if years > 0 and growth > 0 else np.nan
    vol = r.std(ddof=1) * np.sqrt(periods_per_year) if n > 1 else np.nan
    rf_per_period = risk_free_rate / periods_per_year
    excess = r - rf_per_period
    sharpe = (excess.mean() / r.std(ddof=1) * np.sqrt(periods_per_year)) if n > 1 and r.std(ddof=1) > 0 else np.nan

    curve = (1 + r).cumprod()
    drawdown = curve / curve.cummax() - 1
    max_dd = drawdown.min()

    metrics = {
        "cagr": cagr,
        "volatility": vol,
        "sharpe": sharpe,
        "max_drawdown": max_dd,
        "hit_rate": (r > 0).mean(),
        "avg_period_return": r.mean(),
        "n_periods": n,
    }

    if benchmark is not None:
        b = pd.Series(benchmark).dropna()
        aligned = pd.concat([r, b], axis=1, join="inner").dropna()
        if not aligned.empty:
            strat_cagr = (1 + aligned.iloc[:, 0]).prod() ** (periods_per_year / len(aligned)) - 1
            bench_cagr = (1 + aligned.iloc[:, 1]).prod() ** (periods_per_year / len(aligned)) - 1
            metrics["benchmark_excess_return"] = strat_cagr - bench_cagr
        else:
            metrics["benchmark_excess_return"] = np.nan
    else:
        metrics["benchmark_excess_return"] = np.nan
    return metrics
