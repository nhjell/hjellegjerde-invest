"""Exploratory backtest: annual-rebalance cheap-half vs expensive-half portfolio,
using one shared reshuffle date per year and actual daily price paths.

This is not the point-in-time residual-income backtest. It is a quick,
small-sample exploration of whether sorting banks by the legacy GGM valuation
gap and rebalancing annually produces a return spread, using real daily prices
instead of point-to-point annual returns.

Rebalance rule: on 1 Jan each year, value every bank using the most recently
reported fiscal year's ROE/payout (i.e. last year's annual report - the one
that would actually be available by New Year's Day), split the country's
banks into a cheap half and an expensive half by that valuation gap, hold
both halves through daily price moves until the next 1 Jan, then re-split
and carry the compounded value forward. This is a single, explicit rule
applied uniformly to both countries, and it avoids the previous version's
inconsistency of "buying" each bank on its own fiscal year end (Jun/Aug/Sep
for AUS, Dec for THA) - now everyone transacts on the same calendar date.

Look-ahead caveat: real annual reports are published weeks to months after
the fiscal year end, not instantly - using "most recent fiscal year end
before 1 Jan" is a simplification that's slightly optimistic (e.g. a Dec
fiscal year end technically isn't fully reported until Feb-Apr the
following year for some banks). Treat this as a clean, documented
approximation, not a claim of zero look-ahead bias.

Run with: python portfolio_rebalance_backtest.py
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf
from scipy import stats

from config import load_assumptions, load_universe
from valuation_signal_backtest import ROOT, fair_pb


def fetch_ticker_data(ticker: str):
    """Return (fundamentals_df, daily_price_series) for one ticker."""
    t = yf.Ticker(ticker)
    fin, bs, cf = t.financials, t.balance_sheet, t.cashflow
    prices = t.history(period="6y", interval="1d")["Close"]

    if fin.empty or bs.empty or prices.empty:
        return pd.DataFrame(), pd.Series(dtype=float)

    rows = []
    for date in fin.columns:
        try:
            net_income = fin.loc["Net Income", date]
            equity = bs.loc["Stockholders Equity", date]
            shares = bs.loc["Ordinary Shares Number", date]
            div_paid = abs(cf.loc["Cash Dividends Paid", date]) if "Cash Dividends Paid" in cf.index else np.nan
        except KeyError:
            continue
        if pd.isna(net_income) or pd.isna(equity) or pd.isna(shares) or shares == 0 or net_income == 0:
            continue
        rows.append(
            {
                "fiscal_year_end": date,
                "roe": net_income / equity,
                "payout": div_paid / net_income if not pd.isna(div_paid) else np.nan,
                "bvps": equity / shares,
                "shares": shares,
            }
        )
    return pd.DataFrame(rows), prices


def nearest_trading_day_on_or_after(price_series: pd.Series, target_naive_date: pd.Timestamp):
    tz = price_series.index.tz
    target = target_naive_date.tz_localize(tz) if tz is not None else target_naive_date
    candidates = price_series.index[price_series.index >= target]
    return candidates[0] if len(candidates) > 0 else None


def latest_fundamentals_as_of(fundamentals: pd.DataFrame, reshuffle_date: pd.Timestamp):
    prior = fundamentals[fundamentals["fiscal_year_end"] < reshuffle_date]
    if prior.empty:
        return None
    return prior.sort_values("fiscal_year_end").iloc[-1]


def main():
    assumptions = load_assumptions()
    banks = load_universe()

    print("Pulling fundamentals + daily prices per bank...")
    bank_data = {}
    for bank in banks:
        fundamentals, prices = fetch_ticker_data(bank["yahoo_ticker"])
        if fundamentals.empty or prices.empty:
            print(f"  {bank['yahoo_ticker']}: no usable data, skipping")
            continue
        bank_data[bank["yahoo_ticker"]] = {**bank, "fundamentals": fundamentals, "prices": prices}

    all_fy_ends = pd.concat([d["fundamentals"]["fiscal_year_end"] for d in bank_data.values()])
    years = range(all_fy_ends.dt.year.min() + 1, pd.Timestamp.today().year + 1)
    reshuffle_targets = [pd.Timestamp(year=y, month=1, day=1) for y in years]

    period_rows = []
    curves = {}  # (country, half) -> list of daily Series, one per period, already scaled to chain

    for country in ["AUS", "THA"]:
        tickers = [tk for tk, d in bank_data.items() if d["country"] == country]

        # Resolve each target date to an actual per-ticker trading day, keep the target's own
        # representative date (using the first ticker's calendar) for chart annotations.
        resolved_dates = []
        for target in reshuffle_targets:
            any_day = None
            for tk in tickers:
                day = nearest_trading_day_on_or_after(bank_data[tk]["prices"], target)
                if day is not None:
                    any_day = day
                    break
            resolved_dates.append((target, any_day))

        running_value = {"cheap": 1.0, "expensive": 1.0, "index": 1.0}
        cheap_series_parts, expensive_series_parts, index_series_parts = [], [], []
        marker_dates = []

        for i, (target, _) in enumerate(resolved_dates):
            next_target = reshuffle_targets[i + 1] if i + 1 < len(reshuffle_targets) else None

            end_day = None
            if next_target is not None:
                for tk in tickers:
                    day = nearest_trading_day_on_or_after(bank_data[tk]["prices"], next_target)
                    if day is not None:
                        end_day = day
                        break

            # Market-cap-weighted "hold everything" index: weight = shares outstanding (as of
            # the last reported fiscal year) x price at the reshuffle date, re-weighted every
            # year alongside the cheap/expensive rebalance so weights track each bank's actual
            # relative size over time rather than staying fixed at day one.
            market_caps = {}
            for tk in tickers:
                fdata = bank_data[tk]
                asof = latest_fundamentals_as_of(fdata["fundamentals"], target)
                start_day = nearest_trading_day_on_or_after(fdata["prices"], target)
                if asof is None or start_day is None or pd.isna(asof["shares"]):
                    continue
                price_at_start = fdata["prices"].loc[start_day]
                market_caps[tk] = {
                    "weight_basis": asof["shares"] * price_at_start,
                    "start_day": start_day,
                }

            if market_caps:
                total_cap = sum(v["weight_basis"] for v in market_caps.values())
                normalized = []
                weights = []
                for tk, v in market_caps.items():
                    series = bank_data[tk]["prices"]
                    window = series.loc[v["start_day"]:end_day] if end_day is not None else series.loc[v["start_day"]:]
                    normalized.append(window / window.iloc[0])
                    weights.append(v["weight_basis"] / total_cap)
                panel = pd.concat(normalized, axis=1, join="inner")
                index_curve = panel.mul(weights, axis=1).sum(axis=1)
                scaled_index = index_curve * running_value["index"]
                index_series_parts.append(scaled_index)
                running_value["index"] = scaled_index.iloc[-1]

            gaps = {}
            for tk in tickers:
                fdata = bank_data[tk]
                asof = latest_fundamentals_as_of(fdata["fundamentals"], target)
                start_day = nearest_trading_day_on_or_after(fdata["prices"], target)
                if asof is None or start_day is None:
                    continue
                price_at_start = fdata["prices"].loc[start_day]
                actual_pb = price_at_start / asof["bvps"]
                fair = fair_pb(asof["roe"], asof["payout"], assumptions["cost_of_capital"][country])
                if pd.isna(fair):
                    continue
                gaps[tk] = {"gap": actual_pb - fair, "start_day": start_day}

            if len(gaps) < 4:
                continue

            gap_series = pd.Series({tk: v["gap"] for tk, v in gaps.items()})
            median_gap = gap_series.median()
            cheap_tickers = gap_series[gap_series <= median_gap].index.tolist()
            expensive_tickers = gap_series[gap_series > median_gap].index.tolist()

            for label, half_tickers in [("cheap", cheap_tickers), ("expensive", expensive_tickers)]:
                normalized = []
                for tk in half_tickers:
                    start_day = gaps[tk]["start_day"]
                    series = bank_data[tk]["prices"]
                    window = series.loc[start_day:end_day] if end_day is not None else series.loc[start_day:]
                    normalized.append(window / window.iloc[0])
                panel = pd.concat(normalized, axis=1, join="inner")
                half_index = panel.mean(axis=1)  # equal-weighted daily index, starts at 1.0

                scaled = half_index * running_value[label]
                if label == "cheap":
                    cheap_series_parts.append(scaled)
                else:
                    expensive_series_parts.append(scaled)
                running_value[label] = scaled.iloc[-1]

            marker_dates.append(gaps[cheap_tickers[0]]["start_day"] if cheap_tickers else None)

            period_return_cheap = cheap_series_parts[-1].iloc[-1] / cheap_series_parts[-1].iloc[0] - 1
            period_return_expensive = expensive_series_parts[-1].iloc[-1] / expensive_series_parts[-1].iloc[0] - 1
            period_rows.append(
                {
                    "country": country,
                    "rebalance_year": target.year,
                    "n_banks": len(gaps),
                    "cheap_names": ", ".join(cheap_tickers),
                    "expensive_names": ", ".join(expensive_tickers),
                    "cheap_return": period_return_cheap,
                    "expensive_return": period_return_expensive,
                }
            )

        curves[(country, "cheap")] = pd.concat(cheap_series_parts) if cheap_series_parts else pd.Series(dtype=float)
        curves[(country, "expensive")] = (
            pd.concat(expensive_series_parts) if expensive_series_parts else pd.Series(dtype=float)
        )
        curves[(country, "index")] = pd.concat(index_series_parts) if index_series_parts else pd.Series(dtype=float)
        curves[(country, "reshuffle_dates")] = [d for d in marker_dates if d is not None]

    port = pd.DataFrame(period_rows)
    port["spread"] = port["cheap_return"] - port["expensive_return"]

    print("\n--- annual rebalance (1 Jan each year, prior fiscal year's data): cheap half vs expensive half ---")
    print(
        port[["country", "rebalance_year", "n_banks", "cheap_return", "expensive_return", "spread"]]
        .to_string(index=False, float_format="%.3f")
    )

    out_path = ROOT / "data" / "processed" / "portfolio_rebalance_returns.csv"
    port.to_csv(out_path, index=False)
    print(f"\nSaved -> {out_path}")

    print("\n--- summary per country ---")
    fig = go.Figure()
    colors = {"AUS": "#1f77b4", "THA": "#d62728"}
    for country, color in colors.items():
        sub = port[port["country"] == country]
        if sub.empty:
            continue

        n_years = len(sub)
        cheap_curve = curves[(country, "cheap")]
        expensive_curve = curves[(country, "expensive")]
        index_curve = curves[(country, "index")]
        cheap_total = cheap_curve.iloc[-1] - 1
        expensive_total = expensive_curve.iloc[-1] - 1
        index_total = index_curve.iloc[-1] - 1 if not index_curve.empty else float("nan")
        win_rate = (sub["spread"] > 0).mean() * 100
        t_stat, p_value = (np.nan, np.nan)
        if n_years >= 3:
            t_stat, p_value = stats.ttest_1samp(sub["spread"], 0)

        print(
            f"{country}: {n_years} rebalance years | cheap total return={cheap_total:.1%} "
            f"| expensive total return={expensive_total:.1%} | market-cap-weighted index total return="
            f"{index_total:.1%} | cheap beat expensive in {win_rate:.0f}% of years | "
            f"spread t-test p-value={p_value:.3f}"
        )

        fig.add_trace(go.Scatter(x=cheap_curve.index, y=cheap_curve.values, mode="lines",
                                  name=f"{country} cheap half", line=dict(color=color, width=2)))
        fig.add_trace(go.Scatter(x=expensive_curve.index, y=expensive_curve.values, mode="lines",
                                  name=f"{country} expensive half", line=dict(color=color, dash="dot", width=2)))
        if not index_curve.empty:
            fig.add_trace(go.Scatter(x=index_curve.index, y=index_curve.values, mode="lines",
                                      name=f"{country} market-cap-weighted index (hold all)",
                                      line=dict(color=color, dash="longdash", width=3)))

        for d in curves[(country, "reshuffle_dates")]:
            fig.add_vline(x=d, line_width=1, line_dash="dash", line_color=color, opacity=0.4)
            fig.add_annotation(x=d, y=1.02, yref="paper", showarrow=False, text=f"{country} reshuffle",
                                textangle=-90, font=dict(size=9, color=color), xanchor="left")

    fig.add_hline(y=1.0, line_color="gray", line_width=1)
    fig.update_layout(
        title="Daily growth of $1: cheap half vs expensive half vs market-cap-weighted index "
              "(reshuffle = 1 Jan each year)",
        xaxis_title="Date",
        yaxis_title="Cumulative growth of $1",
        template="plotly_white",
        width=1000,
        height=650,
        margin=dict(t=100),
    )
    chart_path = ROOT / "outputs" / "charts" / "portfolio_cheap_vs_expensive_growth.html"
    fig.write_html(chart_path)
    print(f"\nSaved chart -> {chart_path}")
    print("Dashed vertical lines mark each reshuffle date (1 Jan, valued off the prior fiscal year's report).")
    print("Caveat: only ~3 rebalance years and ~4 names per half - directional read, not proof.")


if __name__ == "__main__":
    main()
