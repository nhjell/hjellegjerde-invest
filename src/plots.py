"""Charts for the residual income pipeline.

Uses plotly to stay consistent with the existing Stage 1 charts (standalone,
interactive HTML that opens in any browser). Every function returns the figure
and, if given a filename, also writes it to outputs/charts/.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from utils import CHARTS_DIR

COUNTRY_COLORS = {
    "AUS": "#1f77b4",  # blue
    "THA": "#d62728",  # red
    "NOR": "#2ca02c",  # green
    "SWE": "#9467bd",  # purple
    "DNK": "#e8a838",  # amber
}
FALLBACK_COLOR = "#7f7f7f"  # any country not listed above still plots, in grey


def _countries(df: pd.DataFrame) -> list[str]:
    """Countries actually present in the data, known ones first."""
    present = [c for c in df["country"].dropna().unique()]
    return sorted(present, key=lambda c: (c not in COUNTRY_COLORS, c))


def _save(fig: go.Figure, filename: str | None) -> go.Figure:
    if filename:
        path = Path(CHARTS_DIR) / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.write_html(path)
    return fig


def plot_actual_vs_fair_pb(df: pd.DataFrame, filename: str | None = "ri_actual_vs_fair_pb.html") -> go.Figure:
    """Scatter of actual P/B (x) vs residual-income fair P/B (y), with parity line."""
    fig = go.Figure()
    for country in _countries(df):
        sub = df[df["country"] == country]
        fig.add_trace(go.Scatter(
            x=sub["actual_pb"], y=sub["fair_pb"], mode="markers+text",
            text=sub["ticker"], textposition="top center", name=country,
            marker=dict(size=12, color=COUNTRY_COLORS.get(country, FALLBACK_COLOR)),
        ))
    valid = df.dropna(subset=["actual_pb", "fair_pb"])
    if not valid.empty:
        lo = min(valid["actual_pb"].min(), valid["fair_pb"].min())
        hi = max(valid["actual_pb"].max(), valid["fair_pb"].max())
        fig.add_trace(go.Scatter(x=[lo, hi], y=[lo, hi], mode="lines",
                                 name="fair = actual", line=dict(dash="dash", color="gray")))
    fig.update_layout(
        title="Residual income fair P/B vs actual P/B (above line = undervalued)",
        xaxis_title="Actual P/B", yaxis_title="Fair P/B (residual income)",
        template="plotly_white", width=900, height=650,
    )
    return _save(fig, filename)


def plot_mispricing_ranking(df: pd.DataFrame, filename: str | None = "ri_mispricing_ranking.html") -> go.Figure:
    """Horizontal bar chart of mispricing per bank, sorted cheap (top) to expensive."""
    d = df.dropna(subset=["mispricing"]).sort_values("mispricing")
    colors = [COUNTRY_COLORS.get(c, "#888") for c in d["country"]]
    fig = go.Figure(go.Bar(
        x=d["mispricing"] * 100, y=d["ticker"], orientation="h",
        marker_color=colors,
        text=[f"{v:+.0%}" for v in d["mispricing"]], textposition="outside",
    ))
    fig.add_vline(x=0, line_color="gray", line_width=1)
    fig.update_layout(
        title="Mispricing by bank (fair P/B / actual P/B - 1). Positive = undervalued",
        xaxis_title="Mispricing (%)", yaxis_title="",
        template="plotly_white", width=900, height=700,
    )
    return _save(fig, filename)


def plot_country_cost_of_equity(coe_summary: pd.DataFrame, filename: str | None = "ri_country_cost_of_equity.html") -> go.Figure:
    """Bar chart of average cost of equity by country (from compare_country_cost_of_equity)."""
    col = "avg_cost_of_equity" if "avg_cost_of_equity" in coe_summary.columns else "cost_of_equity"
    fig = go.Figure(go.Bar(
        x=coe_summary["country"], y=coe_summary[col] * 100,
        marker_color=[COUNTRY_COLORS.get(c, "#888") for c in coe_summary["country"]],
        text=[f"{v:.1%}" for v in coe_summary[col]], textposition="outside",
    ))
    fig.update_layout(
        title="Average CAPM cost of equity by country",
        xaxis_title="", yaxis_title="Cost of equity (%)",
        template="plotly_white", width=600, height=500,
    )
    return _save(fig, filename)


def plot_roe_vs_pb(df: pd.DataFrame, roe_col: str = "roe", filename: str | None = "ri_roe_vs_pb.html") -> go.Figure:
    """Scatter of ROE (x) vs actual P/B (y): are higher-ROE banks priced richer?"""
    fig = go.Figure()
    for country in _countries(df):
        sub = df[df["country"] == country]
        fig.add_trace(go.Scatter(
            x=sub[roe_col], y=sub["actual_pb"], mode="markers+text",
            text=sub["ticker"], textposition="top center", name=country,
            marker=dict(size=12, color=COUNTRY_COLORS.get(country, FALLBACK_COLOR)),
        ))
    fig.update_layout(
        title="ROE vs actual P/B",
        xaxis_title="ROE", xaxis_tickformat=".0%",
        yaxis_title="Actual P/B", template="plotly_white", width=900, height=650,
    )
    return _save(fig, filename)


def plot_sensitivity_heatmap(
    table: pd.DataFrame, title: str, filename: str | None = None
) -> go.Figure:
    """Heatmap of a two-way sensitivity grid (rows/cols are assumption shifts)."""
    fig = go.Figure(go.Heatmap(
        z=table.values,
        x=[f"{c:+.3f}" for c in table.columns],
        y=[f"{r:+.3f}" for r in table.index],
        colorscale="RdYlGn",
        colorbar=dict(title="Fair P/B"),
        text=[[f"{v:.2f}" if pd.notna(v) else "" for v in row] for row in table.values],
        texttemplate="%{text}",
    ))
    fig.update_layout(
        title=title,
        xaxis_title=table.columns.name, yaxis_title=table.index.name,
        template="plotly_white", width=800, height=550,
    )
    return _save(fig, filename)


def plot_forecast_paths(
    assumptions: pd.DataFrame,
    coe_table: pd.DataFrame | None = None,
    filename: str | None = "ri_forecast_paths.html",
    terminal_extension_years: int = 3,
) -> go.Figure:
    """Two stacked panels: each bank's forecast ROE path (top) and payout path
    (bottom), years 1..horizon, with the terminal level drawn as a dashed
    flat extension so you can see where each path levels off.

    `assumptions` is the valuation_assumptions table (forecast_year '1'..'H'
    + 'terminal' rows per ticker). Click a ticker in the legend to isolate it.
    """
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08,
        subplot_titles=("Forecast ROE path (dashed = terminal level, held forever)",
                        "Forecast payout ratio path"),
    )

    is_term = assumptions["forecast_year"].astype(str) == "terminal"
    horizon = int(assumptions.loc[~is_term, "forecast_year"].astype(int).max())
    term_x = [horizon, horizon + terminal_extension_years]

    for i, (ticker, grp) in enumerate(assumptions.groupby("ticker")):
        country = grp["country"].iloc[0]
        color = COUNTRY_COLORS.get(country, FALLBACK_COLOR)
        fc = grp[grp["forecast_year"].astype(str) != "terminal"].copy()
        fc["forecast_year"] = fc["forecast_year"].astype(int)
        fc = fc.sort_values("forecast_year")
        term = grp[grp["forecast_year"].astype(str) == "terminal"].iloc[0]

        for row, col_name in ((1, "roe"), (2, "payout_ratio")):
            fig.add_trace(go.Scatter(
                x=fc["forecast_year"], y=fc[col_name], mode="lines+markers",
                name=ticker, legendgroup=ticker, showlegend=(row == 1),
                line=dict(color=color, width=1.8), marker=dict(size=5),
                hovertemplate=f"{ticker} yr %{{x}}: %{{y:.1%}}<extra></extra>",
            ), row=row, col=1)
            fig.add_trace(go.Scatter(
                x=term_x, y=[term[col_name]] * 2, mode="lines",
                name=ticker, legendgroup=ticker, showlegend=False,
                line=dict(color=color, width=1.4, dash="dot"),
                hovertemplate=f"{ticker} terminal: %{{y:.1%}}<extra></extra>",
            ), row=row, col=1)

    fig.update_yaxes(tickformat=".0%", row=1, col=1, title_text="ROE")
    fig.update_yaxes(tickformat=".0%", row=2, col=1, title_text="Payout ratio")
    fig.update_xaxes(title_text="Forecast year", row=2, col=1, dtick=1)
    fig.update_layout(
        title="Forecast assumption paths per bank (colour = country) - click legend to isolate",
        template="plotly_white", width=1000, height=850,
        legend=dict(font=dict(size=9)),
    )
    return _save(fig, filename)


def plot_scenario_ranges(scenarios_df: pd.DataFrame, filename: str | None = "ri_scenario_fair_pb.html") -> go.Figure:
    """Per-bank base fair P/B with bull/bear whiskers, sorted by base."""
    wide = scenarios_df.pivot_table(index="ticker", columns="scenario", values="fair_pb")
    for col in ("base", "bull", "bear"):
        if col not in wide.columns:
            wide[col] = pd.NA
    wide = wide.dropna(subset=["base"]).sort_values("base")

    # Current market P/B per bank (one value per ticker) from the same table.
    actual = scenarios_df.groupby("ticker")["actual_pb"].first()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=wide["base"], y=wide.index, mode="markers", name="fair P/B (base)",
        marker=dict(size=10, color="#333"),
        error_x=dict(
            type="data", symmetric=False,
            array=(wide["bull"] - wide["base"]).clip(lower=0),
            arrayminus=(wide["base"] - wide["bear"]).clip(lower=0),
        ),
    ))
    fig.add_trace(go.Scatter(
        x=actual.reindex(wide.index), y=wide.index, mode="markers",
        name="current P/B (market)",
        marker=dict(size=11, color="#d62728", symbol="x"),
    ))
    fig.update_layout(
        title="Fair P/B by scenario (whiskers = bear..bull) vs current market P/B",
        xaxis_title="P/B", yaxis_title="",
        template="plotly_white", width=900, height=700,
    )
    return _save(fig, filename)
