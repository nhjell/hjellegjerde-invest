"""Global (all-country) point-in-time backtest of the residual-income
mispricing signal at a flat 10% cost of equity, measured in USD.

Relationship to backtest_flat_coe.py
------------------------------------
Same strategy engine, one pooled book instead of separate regional books:
this module reuses ``build_fundamentals_history``, ``load_prices``,
``value_region_at_date`` (called per country, then pooled),
``forward_return`` and the metric helpers from ``backtest_flat_coe``. The
differences are deliberate and limited to:

  * ALL countries in the universe are ranked together in a single global
    ranking (AUS, THA, NOR, SWE, DNK), rather than region by region.
  * Prices are converted to USD at daily FX rates, so the book is what a
    USD-based investor would actually have experienced. FX moves are part of
    the return, and the S&P 500 comparison is apples-to-apples.
  * Two benchmarks are reported: the equal-weighted bank universe (the fair
    "did the ranking add anything?" test) and the S&P 500 (market context).

Strategy definition
-------------------
At each quarterly rebalance date t:

  1. Information set: annual fundamentals whose fiscal year end is at least
     PUBLICATION_LAG_DAYS (90) before t; prices up to t. No lookahead.
  2. Valuation: flat FLAT_COE = 0.10 for every bank at every date (risk
     differences deliberately neutralised), forecasts from the same
     trajectory-aware generator as the live model, restricted to that date's
     history. Fair P/B vs actual P/B -> mispricing.
     NOTE: fair P/B, actual P/B and mispricing are all currency-free ratios
     computed in each bank's own currency, so pooling them across markets is
     legitimate; USD conversion applies only to the realised returns.
  3. Portfolio: long the ceil(n/3) most undervalued banks globally, equal
     weighted, held to t+1. Diagnostics: cheap half, expensive half.
  4. Benchmarks: equal-weight all n banks (USD), and the S&P 500 (SPY_TICKER).

Known caveats (stated, not hidden)
----------------------------------
* ~15 quarters of usable history (yfinance exposes ~4 annual statements per
  bank), so every statistic is a small-sample sanity check, not validation.
* Adjusted prices make returns total returns (correct) but slightly
  understate historical P/B levels; affects valuation levels more than
  cross-sectional ranking. Same open issue as the regional backtest.
* A global ranking at a flat CoE will systematically favour low-P/B markets
  (Thailand) because country risk is switched off by construction. That is
  the intended experiment, not an oversight - compare with the regional run
  in backtest_flat_coe.py to see the difference.
* FX series are Yahoo pairs quoted as USD per unit of local currency where
  available; conversion is applied to price levels before returns.

Outputs
-------
  data/processed/backtest_global_periods.csv    per-quarter leg returns
  data/processed/backtest_global_holdings.csv   global picks each quarter
  data/processed/backtest_global_positions.csv  EVERY bank x quarter: rank,
                                                mispricing, held?, action,
                                                entry/exit price, return
  data/processed/backtest_global_trades.csv     BUY/SELL blotter (one row per
                                                transaction, with the reason)
  data/processed/backtest_global_daily.csv      daily growth per leg
  outputs/charts/backtest_global.html           daily chart, strategy in bold
  logs/backtest_global_{today}.md               written results log

Run with:  cd src && python backtest_global.py
"""

from __future__ import annotations

import datetime as dt
import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf
from scipy import stats

from backtest import calculate_performance_metrics, get_rebalance_dates
from backtest_flat_coe import (
    FLAT_COE,
    MIN_BANKS_PER_DATE,
    PERIODS_PER_YEAR,
    PRICE_HISTORY_PERIOD,
    PUBLICATION_LAG_DAYS,
    REBALANCE_FREQ,
    build_fundamentals_history,
    forward_return,
    load_prices,
    value_region_at_date,
)
from config import load_assumptions, load_universe
from utils import CHARTS_DIR, LOGS_DIR, PROCESSED_DIR, RAW_DIR, ensure_dirs, get_logger, save_csv

logger = get_logger(__name__)

SPY_TICKER = "^GSPC"          # S&P 500 index, USD
BENCH_LABEL = "S&P 500"

# Yahoo FX pairs giving USD per 1 unit of local currency.
FX_PAIRS = {
    "AUD": "AUDUSD=X",
    "THB": "THBUSD=X",
    "NOK": "NOKUSD=X",
    "SEK": "SEKUSD=X",
    "DKK": "DKKUSD=X",
}
COUNTRY_CURRENCY = {"AUS": "AUD", "THA": "THB", "NOR": "NOK", "SWE": "SEK", "DNK": "DKK"}

FX_CACHE_DIR = RAW_DIR / "fx"

LEGS = ("top_third", "cheap_half", "exp_half", "benchmark")
LEG_STYLE = {  # leg -> (label, width, dash, opacity)
    "top_third": ("STRATEGY (global top-third long)", 4.0, "solid", 1.0),
    "benchmark": ("benchmark (equal-weight all banks)", 1.8, "longdash", 0.6),
    "cheap_half": ("cheap half", 1.2, "dash", 0.4),
    "exp_half": ("expensive half", 1.2, "dot", 0.4),
}


def load_fx(currency: str, as_of: str) -> pd.Series:
    """Daily USD per 1 unit of `currency`, cached. USD itself is a flat 1.0."""
    if currency == "USD":
        return pd.Series(dtype=float)
    pair = FX_PAIRS[currency]
    path = FX_CACHE_DIR / f"{pair}_{as_of}.csv"
    if path.exists():
        return pd.read_csv(path, index_col=0, parse_dates=True).iloc[:, 0]
    s = yf.Ticker(pair).history(period=PRICE_HISTORY_PERIOD, interval="1d")["Close"]
    s.index = pd.DatetimeIndex(s.index).tz_localize(None)
    path.parent.mkdir(parents=True, exist_ok=True)
    s.to_csv(path)
    return s


def to_usd(prices_local: pd.Series, fx: pd.Series) -> pd.Series:
    """Convert a local-currency price series to USD on a daily basis.

    FX is forward-filled onto the price calendar (holidays differ by market),
    so every trading day gets the most recent available rate.
    """
    if fx.empty:
        return prices_local
    aligned = fx.reindex(prices_local.index.union(fx.index)).ffill().reindex(prices_local.index)
    return (prices_local * aligned).dropna()


def load_index(ticker: str, as_of: str) -> pd.Series:
    """Daily closes for a market index (already USD), cached like prices."""
    return load_prices(ticker, as_of)


def run_global(
    fundamentals: pd.DataFrame,
    prices_local: dict[str, pd.Series],
    prices_usd: dict[str, pd.Series],
    countries: dict[str, str],
    forecast_cfg: dict,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, pd.Series]]:
    """Quarterly loop over one pooled global universe.

    Valuation uses each bank's LOCAL-currency price and book value (so P/B is
    a clean, currency-free ratio); realised returns use the USD series.
    """
    usd_panel = pd.DataFrame(prices_usd).sort_index()
    all_dates = get_rebalance_dates(usd_panel, REBALANCE_FREQ)
    first_ok = fundamentals.groupby("ticker")["effective_date"].min().sort_values()
    start_date = first_ok.iloc[MIN_BANKS_PER_DATE - 1]
    dates = all_dates[all_dates >= start_date]

    period_rows, holding_rows = [], []
    position_rows, trade_rows = [], []   # audit trail: what was held, what traded
    prev_holdings: set[str] = set()
    running = {leg: 1.0 for leg in LEGS}
    curve_parts: dict[str, list[pd.Series]] = {leg: [] for leg in LEGS}

    for i in range(len(dates) - 1):
        date, nxt = dates[i], dates[i + 1]

        # Value every country's banks (in local currency), then pool the
        # resulting currency-free mispricings into one global ranking.
        # min_banks=1: single-bank countries (Norway, Sweden, Denmark) must NOT
        # be dropped here - the "enough names to rank" test belongs on the
        # pooled universe below, not on each country in isolation.
        frames = []
        for country in sorted(set(countries.values())):
            ranked_c = value_region_at_date(
                date, country, fundamentals, prices_local, forecast_cfg, min_banks=1
            )
            if not ranked_c.empty:
                frames.append(ranked_c)
        if not frames:
            continue
        ranked = pd.concat(frames, ignore_index=True)
        ranked = ranked.dropna(subset=["mispricing"]).sort_values("mispricing", ascending=False)
        ranked = ranked[ranked["ticker"].isin(usd_panel.columns)]
        n = len(ranked)
        if n < MIN_BANKS_PER_DATE:
            continue

        n_top = math.ceil(n / 3)
        n_half = n // 2
        members = {
            "top_third": ranked.head(n_top)["ticker"].tolist(),
            "cheap_half": ranked.head(n_half)["ticker"].tolist(),
            "exp_half": ranked.tail(n_half)["ticker"].tolist(),
            "benchmark": ranked["ticker"].tolist(),
        }

        rets = {t: forward_return(prices_usd[t], date, nxt) for t in members["benchmark"]}
        legs = {leg: float(np.nanmean([rets[t] for t in mem])) for leg, mem in members.items()}

        window = usd_panel.loc[(usd_panel.index >= date) & (usd_panel.index <= nxt)]
        for leg, mem in members.items():
            cols = [t for t in mem if t in window.columns]
            sub = window[cols].ffill().dropna(how="any")
            if sub.empty:
                continue
            daily = (sub / sub.iloc[0]).mean(axis=1) * running[leg]
            running[leg] = float(daily.iloc[-1])
            curve_parts[leg].append(daily if not curve_parts[leg] else daily.iloc[1:])

        picks = members["top_third"]

        # ---- Audit trail: per-bank positions and the BUY/SELL blotter --------
        # A name is BOUGHT when it enters the long book, HELD while it stays,
        # and SOLD at the rebalance date it drops out. Every bank in the
        # ranking gets a row each quarter (held or not) so the log doubles as
        # a record of *why* something was or wasn't owned.
        held_now = set(picks)
        weight = 1.0 / len(picks) if picks else 0.0
        for _, r in ranked.iterrows():
            tk = r["ticker"]
            in_book = tk in held_now
            was_held = tk in prev_holdings
            action = ("BUY" if not was_held else "HOLD") if in_book else ("SELL" if was_held else "")
            entry = price_at(prices_usd[tk], date) if tk in prices_usd else float("nan")
            exit_px = price_at(prices_usd[tk], nxt) if tk in prices_usd else float("nan")
            position_rows.append(
                {
                    "rebalance_date": date.date(), "next_date": nxt.date(),
                    "ticker": tk, "country": countries.get(tk),
                    "rank": int(r["rank"]) if pd.notna(r.get("rank")) else None,
                    "fair_pb": round(float(r["fair_pb"]), 3),
                    "actual_pb": round(float(r["actual_pb"]), 3),
                    "mispricing": round(float(r["mispricing"]), 4),
                    "in_strategy": in_book,
                    "action": action,
                    "weight": round(weight, 4) if in_book else 0.0,
                    "price_usd_entry": round(entry, 4),
                    "price_usd_exit": round(exit_px, 4),
                    "period_return": round(rets[tk], 4) if pd.notna(rets.get(tk)) else None,
                }
            )
            if action in ("BUY", "SELL"):
                trade_rows.append(
                    {
                        "date": date.date(), "action": action, "ticker": tk,
                        "country": countries.get(tk),
                        "price_usd": round(entry, 4),
                        "mispricing_at_trade": round(float(r["mispricing"]), 4),
                        "rank_at_trade": int(r["rank"]) if pd.notna(r.get("rank")) else None,
                        "reason": "entered global top third" if action == "BUY"
                                  else "dropped out of global top third",
                    }
                )
        # Names held last quarter that fell out of the ranking entirely
        # (e.g. no longer valuable) must still be sold, not silently dropped.
        for tk in sorted(prev_holdings - set(ranked["ticker"])):
            trade_rows.append(
                {
                    "date": date.date(), "action": "SELL", "ticker": tk,
                    "country": countries.get(tk),
                    "price_usd": round(price_at(prices_usd[tk], date), 4) if tk in prices_usd else None,
                    "mispricing_at_trade": None, "rank_at_trade": None,
                    "reason": "no longer valued (left the ranking)",
                }
            )
        prev_holdings = held_now

        period_rows.append(
            {
                "rebalance_date": date, "next_date": nxt, "n_banks": n,
                **legs,
                "spread": legs["cheap_half"] - legs["exp_half"],
                "top_third_excess": legs["top_third"] - legs["benchmark"],
                "n_countries_in_top": len({countries[t] for t in picks if t in countries}),
            }
        )
        holding_rows.append(
            {
                "rebalance_date": date,
                "top_third": ", ".join(picks),
                "countries": ", ".join(sorted({countries[t] for t in picks if t in countries})),
                "expensive_half": ", ".join(members["exp_half"]),
            }
        )

    # Positions still open at the end of the backtest are marked as such rather
    # than given a fabricated closing trade.
    if period_rows:
        final_date = period_rows[-1]["next_date"]
        for tk in sorted(prev_holdings):
            trade_rows.append(
                {
                    "date": final_date.date(), "action": "STILL HELD", "ticker": tk,
                    "country": countries.get(tk),
                    "price_usd": round(price_at(prices_usd[tk], final_date), 4) if tk in prices_usd else None,
                    "mispricing_at_trade": None, "rank_at_trade": None,
                    "reason": "open position at end of backtest",
                }
            )

    curves = {leg: pd.concat(parts) for leg, parts in curve_parts.items() if parts}
    return (
        pd.DataFrame(period_rows), pd.DataFrame(holding_rows), curves,
        pd.DataFrame(position_rows), pd.DataFrame(trade_rows),
    )


def price_at(px: pd.Series, when: pd.Timestamp) -> float:
    """Last available price on or before `when` (NaN if the series starts later)."""
    s = px[px.index <= when]
    return float(s.iloc[-1]) if len(s) else float("nan")


def index_curve(index_prices: pd.Series, start: pd.Timestamp, end: pd.Timestamp) -> pd.Series:
    """Growth-of-1 for a buy-and-hold index over the same window."""
    s = index_prices[(index_prices.index >= start) & (index_prices.index <= end)].dropna()
    if s.empty:
        return pd.Series(dtype=float)
    return s / s.iloc[0]


def index_period_returns(index_prices: pd.Series, periods: pd.DataFrame) -> pd.Series:
    """Index return over each strategy holding period (for like-for-like stats)."""
    vals = [
        forward_return(index_prices, r["rebalance_date"], r["next_date"])
        for _, r in periods.iterrows()
    ]
    return pd.Series(vals, index=periods["rebalance_date"])


def plot_curves(curves: dict[str, pd.Series], spx: pd.Series) -> None:
    """Daily USD growth curves; the strategy is bold, everything else recedes."""
    fig = go.Figure()
    color = "#1f77b4"
    for leg, (label, width, dash, opacity) in LEG_STYLE.items():
        c = curves.get(leg)
        if c is None or c.empty:
            continue
        fig.add_trace(go.Scatter(
            x=c.index, y=c.values, mode="lines", name=label,
            line=dict(color=color, dash=dash, width=width), opacity=opacity,
            hovertemplate=f"{label}<br>%{{x|%d %b %Y}}: %{{y:.3f}}<extra></extra>",
        ))
    if not spx.empty:
        fig.add_trace(go.Scatter(
            x=spx.index, y=spx.values, mode="lines", name=BENCH_LABEL,
            line=dict(color="#2ca02c", dash="longdash", width=1.8), opacity=0.75,
            hovertemplate=f"{BENCH_LABEL}<br>%{{x|%d %b %Y}}: %{{y:.3f}}<extra></extra>",
        ))
    fig.add_hline(y=1.0, line_color="gray", line_width=1)
    fig.update_layout(
        title="Global flat-CoE backtest (USD, daily): growth of $1. "
              "Bold = the strategy; green = S&P 500",
        xaxis_title="Date", yaxis_title="Cumulative growth of $1 (USD)",
        template="plotly_white", width=1050, height=650,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    )
    fig.write_html(CHARTS_DIR / "backtest_global.html")


def write_log(periods: pd.DataFrame, holdings: pd.DataFrame, stats: dict,
              spx_metrics: dict, today: str,
              positions: pd.DataFrame | None = None,
              trades: pd.DataFrame | None = None) -> str:
    lines = [
        f"# Global flat-CoE residual income backtest (USD) — {today}",
        "",
        "**Question tested:** ranking ALL banks in the universe together (Australia,",
        "Thailand, Norway, Sweden, Denmark) by residual-income mispricing at an",
        "identical 10% cost of equity, does the global top-third long book beat an",
        "equal-weighted holding of every bank — and how does it compare with the",
        f"{BENCH_LABEL}? All returns in USD, so currency moves are included.",
        "",
        "**Method:** quarterly rebalance, 90-day publication lag on annual reports,",
        "equal-weighted legs, point-in-time forecasts from the same trajectory-aware",
        "engine as the live model. Valuation ratios are computed in local currency",
        "(P/B is currency-free); only realised returns are USD-converted. Full",
        "contract in the module docstring of `src/backtest_global.py`.",
        "",
        f"## Results ({stats['n_periods']} quarterly periods, "
        f"{periods['rebalance_date'].min().date()} → {periods['next_date'].max().date()})",
        "",
        "| Leg | CAGR | Vol (ann.) | Sharpe | Max DD | Hit rate |",
        "|---|---|---|---|---|---|",
    ]
    for leg in LEGS:
        m = stats[leg]
        lines.append(
            f"| {LEG_STYLE[leg][0]} | {m['cagr']:.1%} | {m['volatility']:.1%} | "
            f"{m['sharpe']:.2f} | {m['max_drawdown']:.1%} | {m['hit_rate']:.0%} |"
        )
    lines.append(
        f"| {BENCH_LABEL} | {spx_metrics['cagr']:.1%} | {spx_metrics['volatility']:.1%} | "
        f"{spx_metrics['sharpe']:.2f} | {spx_metrics['max_drawdown']:.1%} | "
        f"{spx_metrics['hit_rate']:.0%} |"
    )
    lines += [
        "",
        f"- Strategy vs equal-weight bank benchmark: {stats['top_third_hit_rate_vs_bench']:.0%} "
        f"of quarters ahead, mean excess {periods['top_third_excess'].mean():+.2%}/quarter",
        f"- Cheap−expensive half-spread: mean {stats['spread_mean_q']:+.2%}/quarter, "
        f"hit rate {stats['spread_hit_rate']:.0%}, t = {stats['spread_t']:.2f}, "
        f"p = {stats['spread_p']:.3f}",
        f"- Average countries represented in the long book: "
        f"{periods['n_countries_in_top'].mean():.1f} of 5",
        "",
        "## Honest read",
        "",
        f"With {stats['n_periods']} quarters, none of these p-values settle anything. Two",
        "structural points matter more than the headline numbers. First, switching",
        "country risk off (flat 10% CoE) mechanically tilts a *global* ranking toward",
        "the cheapest-looking market, so the long book is concentrated by construction",
        "— check the countries column below before reading the result as stock",
        "selection. Second, the equal-weight bank benchmark is the honest comparison;",
        f"the {BENCH_LABEL} line answers a different question (banks vs US equities)",
        "and is included for context only.",
        "",
        "## Holdings by quarter",
        "",
        holdings.to_markdown(index=False),
    ]
    if trades is not None and not trades.empty:
        n_buy = (trades["action"] == "BUY").sum()
        n_sell = (trades["action"] == "SELL").sum()
        n_open = (trades["action"] == "STILL HELD").sum()
        lines += [
            "",
            "## Buy / sell blotter",
            "",
            f"{n_buy} buys, {n_sell} sells, {n_open} positions still open at the end. "
            f"A name is bought when it enters the global top third, held while it stays, "
            f"and sold at the rebalance date it drops out. "
            f"Machine-readable: `data/processed/backtest_global_trades.csv`.",
            "",
            trades.to_markdown(index=False),
        ]
    if positions is not None and not positions.empty:
        lines += [
            "",
            "## Position log (every bank, every quarter)",
            "",
            "One row per bank per quarter — whether it was owned, its rank and",
            "mispricing at that date, entry/exit price in USD, and the realised",
            "return. This is the full audit trail for why anything was or was not",
            "held. Machine-readable: `data/processed/backtest_global_positions.csv`.",
            "",
            "Held positions only (the full table including unheld names is in the CSV):",
            "",
            positions[positions["in_strategy"]].to_markdown(index=False),
        ]
    path = LOGS_DIR / f"backtest_global_{today}.md"
    path.write_text("\n".join(lines))
    return str(path)


def global_stats(periods: pd.DataFrame) -> dict:
    out = {"n_periods": len(periods)}
    for leg in LEGS:
        out[leg] = calculate_performance_metrics(
            periods.set_index("rebalance_date")[leg], periods_per_year=PERIODS_PER_YEAR
        )
    spread = periods["spread"].dropna()
    t_stat, p_val = (np.nan, np.nan)
    if len(spread) >= 3:
        t_stat, p_val = stats.ttest_1samp(spread, 0.0)
    out["spread_mean_q"] = spread.mean()
    out["spread_hit_rate"] = (spread > 0).mean()
    out["spread_t"], out["spread_p"] = t_stat, p_val
    out["top_third_hit_rate_vs_bench"] = (periods["top_third_excess"].dropna() > 0).mean()
    return out


def main() -> None:
    ensure_dirs()
    today = dt.date.today().isoformat()
    forecast_cfg = load_assumptions()["forecast"]
    banks = load_universe()
    countries = {b["yahoo_ticker"]: b["country"] for b in banks}

    logger.info("Building point-in-time fundamentals for %d banks (all countries)...", len(banks))
    fundamentals = build_fundamentals_history(banks, today)

    logger.info("Loading prices and FX, converting to USD...")
    fx_cache = {}
    prices_local, prices_usd = {}, {}
    for b in banks:
        tk, country = b["yahoo_ticker"], b["country"]
        s = load_prices(tk, today)
        if s.empty:
            continue
        prices_local[tk] = s
        ccy = COUNTRY_CURRENCY.get(country)
        if ccy not in fx_cache:
            fx_cache[ccy] = load_fx(ccy, today)
        usd = to_usd(s, fx_cache[ccy])
        if not usd.empty:
            prices_usd[tk] = usd
    logger.info("Usable banks: %d local, %d USD-converted", len(prices_local), len(prices_usd))

    periods, holdings, curves, positions, trades = run_global(
        fundamentals, prices_local, prices_usd, countries, forecast_cfg
    )
    if periods.empty:
        logger.error("No tradeable periods - aborting")
        return

    spx_prices = load_index(SPY_TICKER, today)
    strat_curve = curves["top_third"]
    spx = index_curve(spx_prices, strat_curve.index.min(), strat_curve.index.max())
    spx_metrics = calculate_performance_metrics(
        index_period_returns(spx_prices, periods), periods_per_year=PERIODS_PER_YEAR
    )

    stats_all = global_stats(periods)
    save_csv(periods, PROCESSED_DIR / "backtest_global_periods.csv")
    save_csv(holdings, PROCESSED_DIR / "backtest_global_holdings.csv")
    save_csv(positions, PROCESSED_DIR / "backtest_global_positions.csv")
    save_csv(trades, PROCESSED_DIR / "backtest_global_trades.csv")
    daily_rows = []
    for leg, s in curves.items():
        df = s.rename("growth").to_frame()
        df.insert(0, "leg", leg)
        daily_rows.append(df.reset_index(names="date"))
    if not spx.empty:
        df = spx.rename("growth").to_frame()
        df.insert(0, "leg", "sp500")
        daily_rows.append(df.reset_index(names="date"))
    save_csv(pd.concat(daily_rows, ignore_index=True), PROCESSED_DIR / "backtest_global_daily.csv")

    plot_curves(curves, spx)
    log_path = write_log(periods, holdings, stats_all, spx_metrics, today,
                         positions=positions, trades=trades)

    pd.set_option("display.float_format", "{:.3f}".format)
    print("\n=== Global per-period returns (USD) ===")
    print(periods[["rebalance_date", "n_banks", "top_third", "cheap_half",
                   "exp_half", "benchmark", "spread"]].to_string(index=False))
    print(f"\n=== Global summary ({stats_all['n_periods']} quarters, USD) ===")
    for leg in LEGS:
        m = stats_all[leg]
        print(f"  {LEG_STYLE[leg][0]:36} CAGR {m['cagr']:7.1%}  Sharpe {m['sharpe']:5.2f}  "
              f"maxDD {m['max_drawdown']:7.1%}")
    print(f"  {BENCH_LABEL:36} CAGR {spx_metrics['cagr']:7.1%}  "
          f"Sharpe {spx_metrics['sharpe']:5.2f}  maxDD {spx_metrics['max_drawdown']:7.1%}")
    print(f"\n  strategy ahead of EW banks in {stats_all['top_third_hit_rate_vs_bench']:.0%} of quarters")
    print(f"  half-spread {stats_all['spread_mean_q']:+.2%}/q  p={stats_all['spread_p']:.3f}")

    print("\n=== Buy / sell blotter ===")
    print(trades.to_string(index=False))
    print(f"\n  {(trades['action'] == 'BUY').sum()} buys, "
          f"{(trades['action'] == 'SELL').sum()} sells, "
          f"{(trades['action'] == 'STILL HELD').sum()} still open")

    print(f"\nLog       -> {log_path}")
    print(f"Chart     -> {CHARTS_DIR / 'backtest_global.html'}")
    print(f"Positions -> {PROCESSED_DIR / 'backtest_global_positions.csv'}")
    print(f"Trades    -> {PROCESSED_DIR / 'backtest_global_trades.csv'}")


if __name__ == "__main__":
    main()
