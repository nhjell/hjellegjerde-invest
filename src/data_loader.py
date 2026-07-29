"""Load the processed input CSVs and assemble the clean modelling panel.

This is the read side of the pipeline. src/build_inputs.py writes the CSVs from
the cached raw snapshots + config; this module reads them back, standardises
tickers/dates, and merges them into a single panel the valuation model consumes.
It never downloads: if a processed file is missing it tells you to run
build_inputs.py rather than silently reaching for the network.
"""

from __future__ import annotations

import glob
import json

import pandas as pd

from utils import PROCESSED_DIR, RAW_DIR, get_logger, load_csv

logger = get_logger(__name__)

_FILES = {
    "universe": "bank_universe.csv",
    "fundamentals": "bank_fundamentals.csv",
    "assumptions": "valuation_assumptions.csv",
    "cost_of_equity": "cost_of_equity_inputs.csv",
    "panel": "bank_panel.csv",
}


def inputs_exist() -> bool:
    return all((PROCESSED_DIR / name).exists() for name in _FILES.values())


def _standardise(df: pd.DataFrame) -> pd.DataFrame:
    """Uppercase/strip tickers and parse any `date` column to datetime."""
    out = df.copy()
    if "ticker" in out.columns:
        out["ticker"] = out["ticker"].astype(str).str.strip().str.upper()
    if "date" in out.columns:
        out["date"] = pd.to_datetime(out["date"], errors="coerce")
    return out


def load_universe() -> pd.DataFrame:
    return _standardise(load_csv(PROCESSED_DIR / _FILES["universe"]))


def load_fundamentals() -> pd.DataFrame:
    return _standardise(load_csv(PROCESSED_DIR / _FILES["fundamentals"]))


def load_valuation_assumptions() -> pd.DataFrame:
    # forecast_year stays as string so 'terminal' and '1'..'5' coexist.
    df = load_csv(PROCESSED_DIR / _FILES["assumptions"], dtype={"forecast_year": str})
    return _standardise(df)


def load_cost_of_equity_inputs() -> pd.DataFrame:
    return _standardise(load_csv(PROCESSED_DIR / _FILES["cost_of_equity"]))


def load_raw_snapshots() -> pd.DataFrame:
    """Load every cached raw JSON snapshot (all dates) as a long DataFrame.

    Useful for point-in-time work later; the main pipeline uses the processed
    fundamentals table instead.
    """
    rows = []
    for path in sorted(glob.glob(str(RAW_DIR / "*" / "*.json"))):
        with open(path) as f:
            rows.append(json.load(f))
    df = pd.DataFrame(rows)
    return _standardise(df)


def build_model_panel(
    fundamentals: pd.DataFrame | None = None,
    cost_of_equity: pd.DataFrame | None = None,
    universe: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Merge fundamentals + cost of equity + universe into one row per bank.

    Loads any argument left as None from disk. The result carries everything the
    residual income model needs: ticker, country, bvps, actual_pb, beta, CoE.
    """
    fundamentals = load_fundamentals() if fundamentals is None else _standardise(fundamentals)
    cost_of_equity = load_cost_of_equity_inputs() if cost_of_equity is None else _standardise(cost_of_equity)
    universe = load_universe() if universe is None else _standardise(universe)

    panel = universe.merge(
        fundamentals.drop(columns=["country"], errors="ignore"), on="ticker", how="left"
    )
    panel = panel.merge(
        cost_of_equity.drop(columns=["country"], errors="ignore"),
        on="ticker", how="left", suffixes=("", "_coe"),
    )
    missing_bvps = panel["bvps"].isna().sum() if "bvps" in panel.columns else len(panel)
    if missing_bvps:
        logger.warning("%d banks missing BVPS in the panel", int(missing_bvps))
    return panel


def load_all() -> dict:
    """Convenience: load every processed table into a dict."""
    return {
        "universe": load_universe(),
        "fundamentals": load_fundamentals(),
        "assumptions": load_valuation_assumptions(),
        "cost_of_equity": load_cost_of_equity_inputs(),
        "panel": build_model_panel(),
    }
