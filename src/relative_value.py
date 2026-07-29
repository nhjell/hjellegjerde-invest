"""Relative value: turn fair vs actual P/B into rankable mispricing signals.

Mispricing is expressed two ways:
  * raw mispricing = fair_pb / actual_pb - 1  (positive => undervalued)
  * z-score of mispricing within a group (country) and globally, so a bank is
    judged cheap/expensive relative to its peers rather than in absolute terms.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def calculate_mispricing(fair_pb: float, actual_pb: float) -> float:
    """Fractional mispricing: >0 undervalued (fair above market), <0 overvalued."""
    if actual_pb in (None, 0) or pd.isna(actual_pb) or pd.isna(fair_pb):
        return np.nan
    return fair_pb / actual_pb - 1.0


def rank_banks_by_mispricing(df: pd.DataFrame, mispricing_col: str = "mispricing") -> pd.DataFrame:
    """Return df sorted most-undervalued first, with an integer `rank` column."""
    out = df.copy()
    out = out.sort_values(mispricing_col, ascending=False, na_position="last").reset_index(drop=True)
    out["rank"] = np.arange(1, len(out) + 1)
    return out


def calculate_pb_zscores(
    df: pd.DataFrame,
    value_col: str = "mispricing",
    group_col: str | None = None,
    out_col: str | None = None,
) -> pd.DataFrame:
    """Add a z-score of `value_col`, globally or within `group_col` (e.g. country).

    Uses sample std; a group with <2 valid points gets NaN z-scores (a z-score
    is meaningless without dispersion), rather than a divide-by-zero.
    """
    out = df.copy()
    out_col = out_col or (f"{value_col}_z" if group_col is None else f"{value_col}_z_{group_col}")

    def _z(s: pd.Series) -> pd.Series:
        valid = s.dropna()
        if len(valid) < 2 or valid.std(ddof=1) == 0:
            return pd.Series(np.nan, index=s.index)
        return (s - valid.mean()) / valid.std(ddof=1)

    if group_col is None:
        out[out_col] = _z(out[value_col])
    else:
        out[out_col] = out.groupby(group_col)[value_col].transform(_z)
    return out


def build_relative_value_table(df: pd.DataFrame) -> pd.DataFrame:
    """Assemble the audit-ready relative value table.

    Expects at least: ticker, country, fair_pb, actual_pb, mispricing.
    Adds global and within-country z-scores, a cheap/expensive label, and ranks.
    """
    out = df.copy()
    if "mispricing" not in out.columns and {"fair_pb", "actual_pb"} <= set(out.columns):
        out["mispricing"] = out.apply(
            lambda r: calculate_mispricing(r["fair_pb"], r["actual_pb"]), axis=1
        )

    out = calculate_pb_zscores(out, "mispricing", group_col=None, out_col="mispricing_z_global")
    if "country" in out.columns:
        out = calculate_pb_zscores(out, "mispricing", group_col="country", out_col="mispricing_z_country")

    out["signal"] = np.where(
        out["mispricing"].isna(), "n/a",
        np.where(out["mispricing"] > 0, "undervalued", "overvalued"),
    )
    out = rank_banks_by_mispricing(out)
    if "country" in out.columns:
        out["rank_in_country"] = (
            out.groupby("country")["mispricing"]
            .rank(ascending=False, method="min")
            .astype("Int64")
        )
    return out
