"""Stage 1 entry point: fetch -> screen -> table + chart.

Run with:  python src/screen.py
Outputs:
  data/processed/screen_{as_of}.csv   - full table
  outputs/charts/pb_vs_fair_pb_{as_of}.html  - standalone interactive chart
"""

import datetime as dt
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

from config import load_assumptions, load_universe
from fetch import fetch_universe_snapshot
from model import build_screen_table

ROOT = Path(__file__).resolve().parent.parent
COUNTRY_COLORS = {"AUS": "#1f77b4", "THA": "#d62728"}


def build_chart(df, as_of: str) -> go.Figure:
    fig = go.Figure()

    for country, color in COUNTRY_COLORS.items():
        sub = df[df["country"] == country]
        fig.add_trace(
            go.Scatter(
                x=sub["pb_actual"],
                y=sub["pb_fair"],
                mode="markers+text",
                text=sub["ticker"],
                textposition="top center",
                name=country,
                marker=dict(size=12, color=color),
            )
        )

    lo = min(df["pb_actual"].min(skipna=True), df["pb_fair"].min(skipna=True))
    hi = max(df["pb_actual"].max(skipna=True), df["pb_fair"].max(skipna=True))
    fig.add_trace(
        go.Scatter(
            x=[lo, hi],
            y=[lo, hi],
            mode="lines",
            name="fair = actual",
            line=dict(dash="dash", color="gray"),
        )
    )

    fig.update_layout(
        title=f"Actual P/B vs Fair P/B (Gordon Growth) - as of {as_of}",
        xaxis_title="Actual P/B",
        yaxis_title="Fair P/B",
        template="plotly_white",
        width=900,
        height=650,
    )
    return fig


def main():
    as_of = dt.date.today().isoformat()

    banks = load_universe()
    assumptions = load_assumptions()

    universe_table = pd.DataFrame(banks)[["name", "yahoo_ticker", "country"]]
    universe_table = universe_table.sort_values(["country", "name"]).reset_index(drop=True)
    print(f"Bank universe ({len(universe_table)} names)")
    print(universe_table.to_string(index=False))
    print()

    records = fetch_universe_snapshot(banks, as_of=as_of)
    df = build_screen_table(records, assumptions)

    processed_path = ROOT / "data" / "processed" / f"screen_{as_of}.csv"
    processed_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(processed_path, index=False)

    pd.set_option("display.float_format", "{:.3f}".format)
    print(df.to_string(index=False))

    fig = build_chart(df, as_of)
    chart_path = ROOT / "outputs" / "charts" / f"pb_vs_fair_pb_{as_of}.html"
    chart_path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(chart_path)

    print(f"\nSaved table -> {processed_path}")
    print(f"Saved chart -> {chart_path}")


if __name__ == "__main__":
    main()
