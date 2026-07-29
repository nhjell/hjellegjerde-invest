"""Materialise the auditable input CSVs under data/processed/ from the cached
raw snapshots (data/raw/) and the assumptions in config/assumptions.yaml.

Run once (or whenever you refresh the raw cache / edit config):

    python src/build_inputs.py

Produces:
    data/processed/bank_universe.csv
    data/processed/bank_fundamentals.csv        (from cached yfinance snapshots)
    data/processed/cost_of_equity_inputs.csv    (CAPM inputs + CoE per bank)
    data/processed/valuation_assumptions.csv    (forecast + terminal rows)
    data/processed/bank_panel.csv               (merged view)

It deliberately reads the *cached* JSON snapshots rather than re-downloading, so
it is offline and reproducible. Delete a ticker's cache and rerun src/fetch.py
to refresh. The generated CSVs are meant to be hand-editable: tweak a bank's
forecast in valuation_assumptions.csv and re-run the model without touching code.
"""

from __future__ import annotations

import glob
import json

import numpy as np
import pandas as pd

from config import load_assumptions, load_universe
from cost_of_equity import build_cost_of_equity_inputs
from forecast import build_assumption_rows
from utils import PROCESSED_DIR, RAW_DIR, ensure_dirs, get_logger, save_csv, to_float

logger = get_logger(__name__)

HISTORY_DIR = RAW_DIR / "history"


def _latest_snapshot(ticker: str) -> dict | None:
    """Most recent cached raw JSON snapshot for a ticker, or None if absent."""
    files = sorted(glob.glob(str(RAW_DIR / ticker / "*.json")))
    if not files:
        return None
    with open(files[-1]) as f:
        return json.load(f)


def build_bank_universe(universe: list[dict]) -> pd.DataFrame:
    rows = [
        {"ticker": b["yahoo_ticker"], "name": b["name"], "country": b["country"]}
        for b in universe
    ]
    return pd.DataFrame(rows)


def build_bank_fundamentals(universe: list[dict], coe_table: pd.DataFrame) -> pd.DataFrame:
    """Assemble the fundamentals panel from cached snapshots.

    Note on the raw feed: yfinance returns returnOnEquity/payoutRatio as
    decimals but dividendYield already as a *percent* (e.g. 3.0 == 3.0%), so we
    divide it by 100 to store a decimal consistently. EPS and BVPS are per share.
    """
    beta_by_ticker = dict(zip(coe_table["ticker"], coe_table["beta"]))
    rows = []
    for b in universe:
        ticker = b["yahoo_ticker"]
        snap = _latest_snapshot(ticker)
        if snap is None:
            logger.warning("No cached snapshot for %s - run src/fetch.py", ticker)
            continue
        eps = to_float(snap.get("trailingEps"))
        payout = to_float(snap.get("payoutRatio"))
        div_yield_pct = to_float(snap.get("dividendYield"))
        rows.append(
            {
                "ticker": ticker,
                "date": snap.get("as_of"),
                "price": to_float(snap.get("currentPrice")),
                "bvps": to_float(snap.get("bookValue")),
                "actual_pb": to_float(snap.get("priceToBook")),
                "roe": to_float(snap.get("returnOnEquity")),
                "payout_ratio": payout,
                "dividend_yield": div_yield_pct / 100.0 if not np.isnan(div_yield_pct) else np.nan,
                "eps": eps,
                "dps": eps * payout if not (np.isnan(eps) or np.isnan(payout)) else np.nan,
                "beta": beta_by_ticker.get(ticker, np.nan),
                "currency": snap.get("currency"),
                "country": b["country"],
            }
        )
    return pd.DataFrame(rows)


def load_annual_history(ticker: str) -> list[dict]:
    """Latest cached annual-history JSON for a ticker (chronological rows).

    Empty list when nothing is cached - run src/fetch.py's
    fetch_annual_history to populate. build_inputs deliberately stays offline.
    """
    files = sorted(glob.glob(str(HISTORY_DIR / f"{ticker}_*.json")))
    if not files:
        return []
    with open(files[-1]) as f:
        return json.load(f)


def build_valuation_assumptions(
    fundamentals: pd.DataFrame,
    coe_table: pd.DataFrame,
    forecast_cfg: dict,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Generate forecast + terminal assumption rows for every bank (v2 method).

    Delegates the path logic to src/forecast.py: normalised multi-year starting
    levels, trend-tilted year 1, geometric persistence decay of abnormal ROE,
    hard clips, and a disciplined terminal spread over the cost of equity.
    Returns (assumption_rows, diagnostics) - the diagnostics table shows, per
    bank, exactly which normalised level / trend / persistence / terminal
    spread the generator used, for auditability.
    """
    coe_by_ticker = dict(zip(coe_table["ticker"], coe_table["cost_of_equity"]))
    rows, diags = [], []

    for _, f in fundamentals.iterrows():
        ticker = f["ticker"]
        coe = coe_by_ticker.get(ticker)
        if coe is None:
            logger.warning("No cost of equity for %s; skipping assumptions", ticker)
            continue

        history = load_annual_history(ticker)
        if not history:
            logger.warning("%s: no cached annual history - forecasting from the snapshot alone", ticker)

        result = build_assumption_rows(
            ticker=ticker,
            country=f["country"],
            coe=coe,
            current_roe=None if pd.isna(f["roe"]) else float(f["roe"]),
            current_payout=None if pd.isna(f["payout_ratio"]) else float(f["payout_ratio"]),
            roe_history=[h["roe"] for h in history],
            payout_history=[h["payout_ratio"] for h in history],
            forecast_cfg=forecast_cfg,
        )
        if result is None:
            continue
        bank_rows, diag = result
        rows.extend(bank_rows)
        diags.append(diag)

    return pd.DataFrame(rows), pd.DataFrame(diags)


def build_panel(universe_df, fundamentals, coe_table) -> pd.DataFrame:
    """Wide merged view: universe + fundamentals + cost of equity, one row/bank."""
    panel = universe_df.merge(
        fundamentals.drop(columns=["country"], errors="ignore"), on="ticker", how="left"
    )
    panel = panel.merge(
        coe_table.drop(columns=["country"], errors="ignore"), on="ticker", how="left"
    )
    return panel


def main() -> None:
    ensure_dirs()
    universe = load_universe()
    assumptions = load_assumptions()

    universe_df = build_bank_universe(universe)
    coe_table = build_cost_of_equity_inputs(universe, assumptions["capm"])
    fundamentals = build_bank_fundamentals(universe, coe_table)
    val_assumptions, forecast_diags = build_valuation_assumptions(
        fundamentals, coe_table, assumptions["forecast"]
    )
    panel = build_panel(universe_df, fundamentals, coe_table)

    # Consolidated annual history (audit trail for the normalisation/trend step).
    hist_rows = []
    for b in universe:
        for h in load_annual_history(b["yahoo_ticker"]):
            hist_rows.append({"ticker": b["yahoo_ticker"], "country": b["country"], **h})
    history_df = pd.DataFrame(hist_rows)

    outputs = {
        "bank_universe.csv": universe_df,
        "cost_of_equity_inputs.csv": coe_table,
        "bank_fundamentals.csv": fundamentals,
        "bank_fundamentals_history.csv": history_df,
        "valuation_assumptions.csv": val_assumptions,
        "forecast_diagnostics.csv": forecast_diags,
        "bank_panel.csv": panel,
    }
    for name, df in outputs.items():
        path = save_csv(df, PROCESSED_DIR / name)
        logger.info("Wrote %s (%d rows)", path.name, len(df))

    print(f"\nBuilt {len(outputs)} input files in {PROCESSED_DIR}")
    print(f"  banks in universe : {len(universe_df)}")
    print(f"  fundamentals rows : {len(fundamentals)}")
    print(f"  assumption rows   : {len(val_assumptions)}")


if __name__ == "__main__":
    main()
