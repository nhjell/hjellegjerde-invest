"""Point-in-time backtest of the residual-income mispricing signal at a flat
10% cost of equity, run separately for Australia and Thailand.

Strategy definition
-------------------
At each quarterly rebalance date t, independently within each region:

  1. Information set: annual fundamentals (ROE, payout, BVPS) whose fiscal year
     end is at least `PUBLICATION_LAG_DAYS` (90) before t - i.e. we only use a
     report once it would plausibly have been published. Prices up to t.
  2. Forecast: the SAME generator the live model uses
     (``forecast.build_assumption_rows``: normalised multi-year start, capped
     trend tilt, geometric persistence decay, disciplined terminal spread),
     fed only the point-in-time history. Cost of equity is a constant
     ``FLAT_COE = 0.10`` for every bank at every date, so the signal is pure
     profitability-vs-price with risk differences deliberately neutralised.
  3. Valuation: configurable-horizon residual income model
     (``residual_income_model.value_all_banks``) -> fair P/B per bank.
     Actual P/B = price(t) / latest point-in-time BVPS.
     Mispricing = fair P/B / actual P/B - 1.
  4. Portfolios (equal-weighted, held until t+1):
        top_third   - the ceil(n/3) most undervalued names   (headline long book)
        cheap_half  - the n/2 most undervalued               (signal diagnostic)
        exp_half    - the n/2 least undervalued
        benchmark   - all n names
     The half-spread (cheap_half - exp_half) is the cleanest read on whether
     the ranking contains information, because common market moves cancel.

Anti-lookahead contract
-----------------------
* Fundamentals enter the information set only at fiscal_year_end + 90 days.
* The forecast generator sees only history dated on or before t.
* Returns are measured strictly forward, from the last price <= t to the last
  price <= t+1.

Known measurement caveats (stated, not hidden)
----------------------------------------------
* Prices are Yahoo auto-adjusted closes, so period returns are TOTAL returns
  (dividends reinvested) - correct for performance. The same adjusted price is
  used in the P/B snapshot, which slightly understates historical P/B for
  older dates (dividends paid after that date deflate the adjusted price).
  This biases valuation *levels*, not the within-region ranking much, but it
  is the same open issue flagged in the Stage 1 exploratory backtests.
* Only ~4 annual statements per bank are available from the data source, so
  the tradeable window is roughly late-2022 onward: ~15 quarterly periods.
  Treat every statistic here as a small-sample sanity check, not proof.
* Regions are run separately, each in its own currency (AUD / THB), so there
  is no FX mixing anywhere.

Outputs
-------
  data/processed/backtest_flat_coe_periods.csv   per-period returns per region
  data/processed/backtest_flat_coe_holdings.csv  what was held when
  outputs/charts/backtest_flat_coe.html          cumulative growth curves
  logs/backtest_flat_coe_{today}.md              full written results log

Run with:  cd src && python backtest_flat_coe.py
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
from config import load_assumptions, load_universe
from fetch import fetch_annual_history
from forecast import build_assumption_rows
from residual_income_model import value_all_banks
from utils import CHARTS_DIR, LOGS_DIR, PROCESSED_DIR, RAW_DIR, ensure_dirs, get_logger, save_csv

logger = get_logger(__name__)

# --- Parameters (the deliberate choices, all in one place) -------------------
FLAT_COE = 0.10                # constant cost of equity, every bank, every date
PUBLICATION_LAG_DAYS = 90      # fiscal year end -> usable in the information set
REBALANCE_FREQ = "Q"           # quarterly
REGIONS = ("AUS", "THA")       # run as fully separate books (separate currency)
MIN_BANKS_PER_DATE = 4         # need at least this many valued names to trade
PRICE_HISTORY_PERIOD = "6y"    # max daily history pulled per ticker
PERIODS_PER_YEAR = 4           # for annualisation (quarterly)

PRICE_CACHE_DIR = RAW_DIR / "prices"


# --- Data assembly -----------------------------------------------------------
def load_prices(ticker: str, as_of: str) -> pd.Series:
    """Daily adjusted close for one ticker, cached to data/raw/prices/.

    Adjusted closes make period returns total returns (dividends reinvested).
    Cache is keyed by fetch date so re-runs on the same day are offline.
    """
    path = PRICE_CACHE_DIR / f"{ticker}_{as_of}.csv"
    if path.exists():
        s = pd.read_csv(path, index_col=0, parse_dates=True).iloc[:, 0]
        return s
    s = yf.Ticker(ticker).history(period=PRICE_HISTORY_PERIOD, interval="1d")["Close"]
    s.index = pd.DatetimeIndex(s.index).tz_localize(None)  # naive dates throughout
    path.parent.mkdir(parents=True, exist_ok=True)
    s.to_csv(path)
    return s


def build_fundamentals_history(banks: list[dict], as_of: str) -> pd.DataFrame:
    """Long point-in-time fundamentals table with the publication lag applied.

    One row per (ticker, fiscal year): roe, payout_ratio, bvps,
    fiscal_year_end, and effective_date = fiscal_year_end + 90 days, which is
    the first rebalance date allowed to see this row.
    """
    rows = []
    for b in banks:
        for h in fetch_annual_history(b["yahoo_ticker"], as_of=as_of):
            fye = pd.Timestamp(h["fiscal_year_end"])
            rows.append(
                {
                    "ticker": b["yahoo_ticker"],
                    "country": b["country"],
                    "fiscal_year_end": fye,
                    "effective_date": fye + pd.Timedelta(days=PUBLICATION_LAG_DAYS),
                    "roe": h["roe"],
                    "payout_ratio": h["payout_ratio"],
                    "bvps": h["bvps"],
                }
            )
    return pd.DataFrame(rows)


# --- Point-in-time valuation --------------------------------------------------
def value_region_at_date(
    date: pd.Timestamp,
    region: str,
    fundamentals: pd.DataFrame,
    prices: dict[str, pd.Series],
    forecast_cfg: dict,
    min_banks: int | None = None,
) -> pd.DataFrame:
    """Fair P/B, actual P/B and mispricing for every bank in `region` using
    only information effective on or before `date`.

    Returns an empty frame when fewer than `min_banks` names can be valued
    (default MIN_BANKS_PER_DATE, i.e. don't trade a region too thin to rank).
    Callers that pool several countries into one global ranking should pass
    min_banks=1 so single-bank countries are not dropped here, and enforce the
    minimum on the pooled universe instead.
    """
    min_banks = MIN_BANKS_PER_DATE if min_banks is None else min_banks
    known = fundamentals[
        (fundamentals["country"] == region) & (fundamentals["effective_date"] <= date)
    ].sort_values("fiscal_year_end")

    assumption_rows, panel_rows = [], []
    for ticker, grp in known.groupby("ticker"):
        roe_hist = grp["roe"].tolist()
        payout_hist = grp["payout_ratio"].tolist()
        latest = grp.iloc[-1]

        px = prices.get(ticker)
        if px is None or px[px.index <= date].empty:
            continue
        price_t = px[px.index <= date].iloc[-1]
        if not np.isfinite(latest["bvps"]) or latest["bvps"] <= 0:
            continue

        result = build_assumption_rows(
            ticker=ticker, country=region, coe=FLAT_COE,
            current_roe=roe_hist[-1], current_payout=payout_hist[-1],
            roe_history=roe_hist[:-1], payout_history=payout_hist[:-1],
            forecast_cfg=forecast_cfg,
        )
        if result is None:
            continue
        assumption_rows.extend(result[0])
        panel_rows.append(
            {
                "ticker": ticker,
                "country": region,
                "bvps": latest["bvps"],
                "actual_pb": price_t / latest["bvps"],
            }
        )

    if len(panel_rows) < min_banks:
        return pd.DataFrame()
    ranked = value_all_banks(
        pd.DataFrame(panel_rows), pd.DataFrame(assumption_rows),
        horizon=forecast_cfg["horizon_years"],
    )
    return ranked


# --- Portfolio mechanics --------------------------------------------------------
def forward_return(px: pd.Series, start: pd.Timestamp, end: pd.Timestamp) -> float:
    """Total return from last price <= start to last price <= end."""
    p0 = px[px.index <= start]
    p1 = px[px.index <= end]
    if p0.empty or p1.empty:
        return np.nan
    return p1.iloc[-1] / p0.iloc[-1] - 1.0


def run_region(
    region: str,
    fundamentals: pd.DataFrame,
    prices: dict[str, pd.Series],
    forecast_cfg: dict,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Quarterly loop for one region.

    Returns (period_table, holdings_table, daily_curves) where daily_curves
    maps each leg name to a daily growth-of-1 Series built by holding the
    leg's names through actual daily prices between rebalances and chaining
    the compounded value across periods.
    """
    tickers = sorted(fundamentals.loc[fundamentals["country"] == region, "ticker"].unique())
    price_panel = pd.DataFrame({t: prices[t] for t in tickers if t in prices}).sort_index()
    all_dates = get_rebalance_dates(price_panel, REBALANCE_FREQ)
    # First tradeable date = first quarter end with enough effective reports.
    first_ok = fundamentals[fundamentals["country"] == region].groupby("ticker")["effective_date"].min()
    start_date = first_ok.sort_values().iloc[MIN_BANKS_PER_DATE - 1]
    dates = all_dates[all_dates >= start_date]

    LEGS = ("top_third", "cheap_half", "exp_half", "benchmark")
    period_rows, holding_rows = [], []
    running = {leg: 1.0 for leg in LEGS}
    curve_parts: dict[str, list[pd.Series]] = {leg: [] for leg in LEGS}

    for i in range(len(dates) - 1):
        date, nxt = dates[i], dates[i + 1]
        ranked = value_region_at_date(date, region, fundamentals, prices, forecast_cfg)
        if ranked.empty:
            continue

        n = len(ranked)
        n_top = math.ceil(n / 3)
        n_half = n // 2
        members = {
            "top_third": ranked.head(n_top)["ticker"].tolist(),
            "cheap_half": ranked.head(n_half)["ticker"].tolist(),
            "exp_half": ranked.tail(n_half)["ticker"].tolist(),
            "benchmark": ranked["ticker"].tolist(),
        }

        rets = {t: forward_return(prices[t], date, nxt) for t in members["benchmark"]}
        legs = {leg: np.nanmean([rets[t] for t in mem]) for leg, mem in members.items()}

        # Daily equal-weighted growth path for each leg over this holding
        # period, scaled to chain onto the previous periods' compounded value.
        window = price_panel.loc[(price_panel.index >= date) & (price_panel.index <= nxt)]
        for leg, mem in members.items():
            cols = [t for t in mem if t in window.columns]
            sub = window[cols].ffill().dropna(how="any")
            if sub.empty:
                continue
            daily = (sub / sub.iloc[0]).mean(axis=1) * running[leg]
            running[leg] = float(daily.iloc[-1])
            # drop the first point on all but the first period to avoid duplicates
            curve_parts[leg].append(daily if not curve_parts[leg] else daily.iloc[1:])

        period_rows.append(
            {
                "region": region, "rebalance_date": date, "next_date": nxt, "n_banks": n,
                **legs,
                "spread": legs["cheap_half"] - legs["exp_half"],
                "top_third_excess": legs["top_third"] - legs["benchmark"],
            }
        )
        holding_rows.append(
            {
                "region": region, "rebalance_date": date,
                "top_third": ", ".join(members["top_third"]),
                "cheap_half": ", ".join(members["cheap_half"]),
                "expensive_half": ", ".join(members["exp_half"]),
            }
        )

    daily_curves = {leg: pd.concat(parts) for leg, parts in curve_parts.items() if parts}
    return pd.DataFrame(period_rows), pd.DataFrame(holding_rows), daily_curves


# --- Reporting -----------------------------------------------------------------
def region_stats(periods: pd.DataFrame) -> dict:
    """Headline statistics for one region's period table."""
    out = {"n_periods": len(periods)}
    for leg in ("top_third", "cheap_half", "exp_half", "benchmark"):
        m = calculate_performance_metrics(
            periods.set_index("rebalance_date")[leg], periods_per_year=PERIODS_PER_YEAR
        )
        out[leg] = m
    spread = periods["spread"].dropna()
    t_stat, p_val = (np.nan, np.nan)
    if len(spread) >= 3:
        t_stat, p_val = stats.ttest_1samp(spread, 0.0)
    out["spread_mean_q"] = spread.mean()
    out["spread_hit_rate"] = (spread > 0).mean()
    out["spread_t"] = t_stat
    out["spread_p"] = p_val
    excess = periods["top_third_excess"].dropna()
    out["top_third_hit_rate_vs_bench"] = (excess > 0).mean()
    return out


def write_log(all_periods: pd.DataFrame, all_holdings: pd.DataFrame, stats_by_region: dict, today: str) -> str:
    """Write the quant-readable markdown results log to logs/."""
    lines = [
        f"# Flat-CoE residual income backtest — {today}",
        "",
        "**Question tested:** if every bank is valued with an identical 10% cost of",
        "equity (risk differences deliberately neutralised), does ranking banks by",
        "residual-income mispricing — using the same trajectory-aware forecast engine",
        "as the live model, restricted to point-in-time information — predict",
        "subsequent quarterly returns within Australia and within Thailand?",
        "",
        "**Method:** see the module docstring of `src/backtest_flat_coe.py` for the",
        "full contract. Quarterly rebalance; 90-day publication lag on annual",
        "reports; equal-weighted legs; each region runs in its own currency.",
        "Portfolios: top-third long (headline), cheap-half vs expensive-half spread",
        "(diagnostic), equal-weight regional benchmark.",
        "",
    ]
    for region, s in stats_by_region.items():
        sub = all_periods[all_periods["region"] == region]
        lines += [
            f"## {region} ({s['n_periods']} quarterly periods, "
            f"{sub['rebalance_date'].min().date()} → {sub['next_date'].max().date()})",
            "",
            "| Leg | CAGR | Vol (ann.) | Sharpe | Max DD | Hit rate |",
            "|---|---|---|---|---|---|",
        ]
        for leg in ("top_third", "cheap_half", "exp_half", "benchmark"):
            m = s[leg]
            lines.append(
                f"| {leg} | {m['cagr']:.1%} | {m['volatility']:.1%} | "
                f"{m['sharpe']:.2f} | {m['max_drawdown']:.1%} | {m['hit_rate']:.0%} |"
            )
        lines += [
            "",
            f"- Cheap−expensive half-spread: mean {s['spread_mean_q']:+.2%}/quarter, "
            f"hit rate {s['spread_hit_rate']:.0%}, t = {s['spread_t']:.2f}, p = {s['spread_p']:.3f}",
            f"- Top-third beat its regional benchmark in {s['top_third_hit_rate_vs_bench']:.0%} of quarters",
            "",
        ]
    lines += [
        "## Honest read",
        "",
        f"With only ~{int(all_periods.groupby('region').size().max())} quarters per region, no p-value here deserves",
        "much weight in either direction. The half-spread hit rate and its sign are",
        "the most informative numbers; treat them as a directional sanity check on",
        "the signal, not as evidence the strategy 'works'. Known measurement bias:",
        "adjusted prices slightly understate historical P/B levels (see module",
        "docstring) — it affects levels far more than within-region rankings.",
        "",
        "## Holdings by quarter",
        "",
        all_holdings.to_markdown(index=False),
    ]
    path = LOGS_DIR / f"backtest_flat_coe_{today}.md"
    path.write_text("\n".join(lines))
    return str(path)


def plot_curves(daily_by_region: dict[str, dict[str, pd.Series]]) -> None:
    """Daily cumulative growth-of-1 curves per region.

    The STRATEGY (top-third long book) is drawn bold and fully opaque; the
    diagnostic legs (cheap/expensive halves, benchmark) are thin, dashed and
    faded so the strategy reads unmistakably as the headline line.
    """
    fig = go.Figure()
    colors = {"AUS": "#1f77b4", "THA": "#d62728"}
    styling = {  # leg -> (label, width, dash, opacity)
        "top_third": ("STRATEGY (top-third long)", 4.0, "solid", 1.0),
        "benchmark": ("benchmark (equal-weight)", 1.6, "longdash", 0.55),
        "cheap_half": ("cheap half", 1.2, "dash", 0.40),
        "exp_half": ("expensive half", 1.2, "dot", 0.40),
    }
    for region, curves in daily_by_region.items():
        color = colors.get(region, "#888")
        for leg, (label, width, dash, opacity) in styling.items():
            curve = curves.get(leg)
            if curve is None or curve.empty:
                continue
            fig.add_trace(go.Scatter(
                x=curve.index, y=curve.values, mode="lines",
                name=f"{region} — {label}",
                line=dict(color=color, dash=dash, width=width),
                opacity=opacity,
                hovertemplate=f"{region} {label}<br>%{{x|%d %b %Y}}: %{{y:.3f}}<extra></extra>",
            ))
    fig.add_hline(y=1.0, line_color="gray", line_width=1)
    fig.update_layout(
        title="Flat-CoE backtest, daily view: growth of 1 unit of local currency "
              "(quarterly rebalance, 90-day report lag). Bold = the strategy.",
        xaxis_title="Date", yaxis_title="Cumulative growth of 1",
        template="plotly_white", width=1050, height=650,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    )
    fig.write_html(CHARTS_DIR / "backtest_flat_coe.html")


def main() -> None:
    ensure_dirs()
    today = dt.date.today().isoformat()
    forecast_cfg = load_assumptions()["forecast"]
    banks = [b for b in load_universe() if b["country"] in REGIONS]

    logger.info("Loading fundamentals history (%d banks, %dd publication lag)...",
                len(banks), PUBLICATION_LAG_DAYS)
    fundamentals = build_fundamentals_history(banks, today)
    usable = fundamentals["ticker"].nunique()
    logger.info("Fundamentals: %d banks with at least one annual report", usable)

    logger.info("Loading daily prices (cached)...")
    prices = {}
    for b in banks:
        s = load_prices(b["yahoo_ticker"], today)
        if not s.empty:
            prices[b["yahoo_ticker"]] = s

    all_periods, all_holdings, stats_by_region = [], [], {}
    daily_by_region: dict[str, dict[str, pd.Series]] = {}
    for region in REGIONS:
        periods, holdings, daily_curves = run_region(region, fundamentals, prices, forecast_cfg)
        if periods.empty:
            logger.warning("%s: no tradeable periods", region)
            continue
        all_periods.append(periods)
        all_holdings.append(holdings)
        daily_by_region[region] = daily_curves
        stats_by_region[region] = region_stats(periods)

    periods_df = pd.concat(all_periods, ignore_index=True)
    holdings_df = pd.concat(all_holdings, ignore_index=True)
    save_csv(periods_df, PROCESSED_DIR / "backtest_flat_coe_periods.csv")
    save_csv(holdings_df, PROCESSED_DIR / "backtest_flat_coe_holdings.csv")
    # Daily strategy curve as CSV too, for audit / further analysis.
    daily_rows = []
    for region, curves in daily_by_region.items():
        for leg, s in curves.items():
            df = s.rename("growth").to_frame()
            df.insert(0, "region", region)
            df.insert(1, "leg", leg)
            daily_rows.append(df.reset_index(names="date"))
    if daily_rows:
        save_csv(pd.concat(daily_rows, ignore_index=True), PROCESSED_DIR / "backtest_flat_coe_daily.csv")
    plot_curves(daily_by_region)
    log_path = write_log(periods_df, holdings_df, stats_by_region, today)

    pd.set_option("display.float_format", "{:.3f}".format)
    print("\n=== Per-period table ===")
    print(periods_df[["region", "rebalance_date", "n_banks", "top_third",
                      "cheap_half", "exp_half", "benchmark", "spread"]].to_string(index=False))
    for region, s in stats_by_region.items():
        print(f"\n=== {region} ===  ({s['n_periods']} quarters)")
        print(f"  top_third : CAGR {s['top_third']['cagr']:.1%}  Sharpe {s['top_third']['sharpe']:.2f}")
        print(f"  benchmark : CAGR {s['benchmark']['cagr']:.1%}  Sharpe {s['benchmark']['sharpe']:.2f}")
        print(f"  spread    : {s['spread_mean_q']:+.2%}/q  hit {s['spread_hit_rate']:.0%}  "
              f"t={s['spread_t']:.2f}  p={s['spread_p']:.3f}")
    print(f"\nLog     -> {log_path}")
    print(f"Chart   -> {CHARTS_DIR / 'backtest_flat_coe.html'}")


if __name__ == "__main__":
    main()
