"""Chart: current actual P/B vs each bank's average ROE over its last 3 reported fiscal years.

Purpose: a quick eyeball check of whether the market is pricing banks roughly
in line with their recent profitability (ROE), independent of the Gordon
Growth fair-value model - high-ROE banks earning a premium P/B is expected;
this just shows whether that premium looks proportionate across the universe.

Uses the most recent Stage 1 screen CSV for actual P/B, and pulls ~4y annual
financials per bank (yfinance) to compute the trailing-3yr average ROE.

Run with: python pb_vs_avg_roe_chart.py
"""

import glob
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

from config import load_universe
from valuation_signal_backtest import ROOT, bank_year_observations


def latest_screen_csv() -> Path:
    candidates = sorted(glob.glob(str(ROOT / "data" / "processed" / "screen_*.csv")))
    if not candidates:
        raise FileNotFoundError("No screen_*.csv found - run screen.py first.")
    return Path(candidates[-1])


def main():
    screen_path = latest_screen_csv()
    screen = pd.read_csv(screen_path)
    print(f"Using current P/B from {screen_path.name}")

    banks = load_universe()
    rows = []
    print("Pulling ~4y annual financials per bank to compute trailing 3yr average ROE...")
    for bank in banks:
        ticker = bank["yahoo_ticker"]
        hist = bank_year_observations(ticker)
        if hist.empty:
            print(f"  {ticker}: no usable annual data, skipping")
            continue

        last3 = hist.sort_values("fiscal_year_end").tail(3)
        avg_roe = last3["roe"].mean()

        pb_row = screen[screen["ticker"] == ticker]
        if pb_row.empty:
            continue
        pb_actual = pb_row.iloc[0]["pb_actual"]

        rows.append(
            {
                "name": bank["name"],
                "ticker": ticker,
                "country": bank["country"],
                "avg_roe_3yr": avg_roe,
                "n_years_used": len(last3),
                "pb_actual": pb_actual,
            }
        )

    df = pd.DataFrame(rows).sort_values(["country", "name"]).reset_index(drop=True)
    print(df.to_string(index=False))

    out_csv = ROOT / "data" / "processed" / "pb_vs_avg_roe.csv"
    df.to_csv(out_csv, index=False)
    print(f"\nSaved -> {out_csv}")

    fig = go.Figure()
    colors = {"AUS": "#1f77b4", "THA": "#d62728"}
    for country, color in colors.items():
        sub = df[df["country"] == country]
        fig.add_trace(
            go.Scatter(
                x=sub["avg_roe_3yr"], y=sub["pb_actual"], mode="markers+text",
                text=sub["ticker"], textposition="top center", name=country,
                marker=dict(size=12, color=color),
            )
        )

    fig.update_layout(
        title="Actual P/B vs Trailing 3yr Average ROE",
        xaxis_title="Average ROE, last 3 reported fiscal years",
        xaxis_tickformat=".0%",
        yaxis_title="Actual P/B (current)",
        template="plotly_white",
        width=900,
        height=650,
    )
    chart_path = ROOT / "outputs" / "charts" / "pb_vs_avg_roe.html"
    fig.write_html(chart_path)
    print(f"Saved chart -> {chart_path}")


if __name__ == "__main__":
    main()
