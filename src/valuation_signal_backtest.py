"""Exploratory backtest: does the fair-P/B valuation gap predict forward returns?

This is not the point-in-time residual-income backtest. It is a quick,
small-sample exploration of the legacy GGM screen's required-return assumption.

Question: is the fair-P/B signal (actual P/B minus model fair P/B) actually
informative about forward returns, or is the "everything looks overvalued"
result purely an artifact of r being set too high?

Method (deliberately simple):
  1. Pull ~4 years of annual financials per bank from yfinance (that's all
     the free annual history it exposes) to get ROE, payout ratio and book
     value per share at each historical fiscal year end.
  2. Compute fair P/B at each fiscal year end using that year's own
     ROE/payout, for a *sweep* of r values (not just the config's r).
  3. Pull the actual price at that fiscal year end and ~1yr later to get
     the "valuation gap" (actual P/B - fair P/B) and the forward return.
  4. Correlate valuation gap vs forward return, per r. If the model has any
     signal, more-overvalued names should show up with lower forward
     returns (negative correlation) - and the sweep tells you which r
     maximizes that relationship instead of guessing.

Sample size is small (16 banks x ~3 usable year-pairs = ~48 obs max), so
treat this as directional, not conclusive. Run with: python valuation_signal_backtest.py
"""

import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf
from scipy import stats

from config import load_universe

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent

R_GRID = {
    "AUS": np.arange(0.06, 0.125, 0.005),
    "THA": np.arange(0.08, 0.155, 0.005),
}


def bank_year_observations(ticker: str) -> pd.DataFrame:
    """Build one row per fiscal year end with ROE, payout, book value/share, price."""
    t = yf.Ticker(ticker)
    fin = t.financials
    bs = t.balance_sheet
    cf = t.cashflow
    hist = t.history(period="6y", interval="1d")

    if fin.empty or bs.empty or hist.empty:
        return pd.DataFrame()

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

        roe = net_income / equity
        payout = div_paid / net_income if not pd.isna(div_paid) else np.nan
        bvps = equity / shares

        price_row = hist.index[hist.index <= date.tz_localize(hist.index.tz)]
        if len(price_row) == 0:
            continue
        price_t = hist.loc[price_row[-1], "Close"]

        fwd_date = date + pd.Timedelta(days=365)
        fwd_candidates = hist.index[hist.index >= fwd_date.tz_localize(hist.index.tz)]
        fwd_price = hist.loc[fwd_candidates[0], "Close"] if len(fwd_candidates) > 0 else np.nan

        rows.append(
            {
                "ticker": ticker,
                "fiscal_year_end": date,
                "roe": roe,
                "payout": payout,
                "bvps": bvps,
                "price": price_t,
                "actual_pb": price_t / bvps,
                "fwd_price": fwd_price,
                "fwd_return": (fwd_price / price_t - 1) if not pd.isna(fwd_price) else np.nan,
            }
        )

    return pd.DataFrame(rows)


def fair_pb(roe, payout, r):
    if pd.isna(roe) or pd.isna(payout) or payout < 0:
        return np.nan
    g = roe * (1 - payout)
    if r - g <= 0:
        return np.nan
    return (payout * roe) / (r - g)


def main():
    banks = load_universe()

    all_obs = []
    print("Pulling ~4y annual financials per bank (this hits yfinance once per ticker)...")
    for bank in banks:
        df = bank_year_observations(bank["yahoo_ticker"])
        if df.empty:
            print(f"  {bank['yahoo_ticker']}: no usable annual data, skipping")
            continue
        df["country"] = bank["country"]
        df["name"] = bank["name"]
        all_obs.append(df)

    obs = pd.concat(all_obs, ignore_index=True)
    obs = obs.dropna(subset=["fwd_return"])
    print(f"\nUsable bank-year observations (have a forward return): {len(obs)}")
    print(obs[["name", "fiscal_year_end", "roe", "payout", "actual_pb", "fwd_return"]].to_string(index=False))

    print("\n--- r sweep: correlation between valuation gap (actual P/B - fair P/B) and forward return ---")
    print("(negative correlation = signal works: 'overvalued' names went on to underperform)\n")

    results = []
    for country, r_values in R_GRID.items():
        sub = obs[obs["country"] == country]
        if sub.empty:
            continue
        for r in r_values:
            fair = sub.apply(lambda row: fair_pb(row["roe"], row["payout"], r), axis=1)
            gap = sub["actual_pb"] - fair
            valid = gap.notna() & sub["fwd_return"].notna()
            if valid.sum() < 4:
                continue
            corr = np.corrcoef(gap[valid], sub["fwd_return"][valid])[0, 1]
            pct_overvalued = (gap[valid] > 0).mean() * 100
            results.append(
                {"country": country, "r": round(r, 3), "n": int(valid.sum()),
                 "corr_gap_vs_fwd_return": round(corr, 3), "pct_overvalued": round(pct_overvalued, 1)}
            )

    results_df = pd.DataFrame(results)
    print(results_df.to_string(index=False))

    print("\n--- best r per country (most negative correlation = strongest signal) ---")
    best_r = {}
    for country in R_GRID:
        sub = results_df[results_df["country"] == country]
        if sub.empty:
            continue
        best = sub.loc[sub["corr_gap_vs_fwd_return"].idxmin()]
        best_r[country] = best["r"]
        print(f"{country}: r={best['r']} gives corr={best['corr_gap_vs_fwd_return']} "
              f"(n={int(best['n'])}, {best['pct_overvalued']}% flagged overvalued at that r)")

    obs["r_used"] = obs["country"].map(best_r)
    obs["fair_pb_at_best_r"] = obs.apply(lambda row: fair_pb(row["roe"], row["payout"], row["r_used"]), axis=1)
    obs["valuation_gap"] = obs["actual_pb"] - obs["fair_pb_at_best_r"]
    obs["flagged_overvalued"] = obs["valuation_gap"] > 0
    obs["outcome_matches_flag"] = (obs["flagged_overvalued"] & (obs["fwd_return"] < 0)) | (
        ~obs["flagged_overvalued"] & (obs["fwd_return"] > 0)
    )

    out_cols = [
        "country", "name", "ticker", "fiscal_year_end", "roe", "payout",
        "actual_pb", "r_used", "fair_pb_at_best_r", "valuation_gap",
        "flagged_overvalued", "fwd_return", "outcome_matches_flag",
    ]
    out_path = ROOT / "data" / "processed" / "bank_year_valuation_observations.csv"
    obs[out_cols].sort_values(["country", "name", "fiscal_year_end"]).to_csv(out_path, index=False)
    print(f"\nSaved per-observation detail -> {out_path}")
    print("Open it in Excel/Numbers, sort by outcome_matches_flag=False to see where the model got it backwards.")

    print("\n--- does the signal hold up statistically? (OLS: fwd_return ~ valuation_gap) ---")
    fig = go.Figure()
    colors = {"AUS": "#1f77b4", "THA": "#d62728"}
    for country, color in colors.items():
        sub = obs[obs["country"] == country].dropna(subset=["valuation_gap", "fwd_return"])
        if len(sub) < 4:
            continue

        slope, intercept, r_value, p_value, std_err = stats.linregress(sub["valuation_gap"], sub["fwd_return"])
        r_squared = r_value ** 2
        sig_note = "significant at 5%" if p_value < 0.05 else "not significant at 5%"
        print(
            f"{country}: n={len(sub)}  slope={slope:.3f}  R^2={r_squared:.3f}  "
            f"p-value={p_value:.3f}  ({sig_note})"
        )

        fig.add_trace(
            go.Scatter(
                x=sub["valuation_gap"], y=sub["fwd_return"], mode="markers",
                name=f"{country} observations",
                text=sub["name"] + " " + sub["fiscal_year_end"].dt.year.astype(str),
                hoverinfo="text+x+y",
                marker=dict(size=9, color=color),
            )
        )

        x_line = np.linspace(sub["valuation_gap"].min(), sub["valuation_gap"].max(), 50)
        y_line = slope * x_line + intercept
        fig.add_trace(
            go.Scatter(
                x=x_line, y=y_line, mode="lines",
                name=f"{country} trend (R²={r_squared:.2f}, p={p_value:.2f})",
                line=dict(color=color, dash="dash"),
            )
        )

    fig.add_hline(y=0, line_color="gray", line_width=1)
    fig.add_vline(x=0, line_color="gray", line_width=1)
    fig.update_layout(
        title="Valuation gap (actual P/B - fair P/B) vs forward 1yr return",
        xaxis_title="Valuation gap (positive = model says overvalued)",
        yaxis_title="Forward 1yr return",
        template="plotly_white",
        width=900,
        height=650,
    )
    chart_path = ROOT / "outputs" / "charts" / "valuation_gap_vs_forward_return.html"
    fig.write_html(chart_path)
    print(f"\nSaved chart -> {chart_path}")
    print("Bottom-left and top-right quadrants = signal working (overvalued->fell, undervalued->rose).")
    print("Bottom-right and top-left quadrants = signal wrong for that observation.")
    print("With n~20-25 per country, p-values this small a sample size are rarely below 0.05 - treat as directional.")


if __name__ == "__main__":
    main()
