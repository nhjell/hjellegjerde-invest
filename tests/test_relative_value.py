"""Unit tests for the relative value / mispricing module."""

import numpy as np
import pandas as pd
import pytest

from relative_value import (
    build_relative_value_table,
    calculate_mispricing,
    calculate_pb_zscores,
    rank_banks_by_mispricing,
)


def test_mispricing_formula():
    # fair 1.2 vs actual 1.0 -> +20% undervalued
    assert calculate_mispricing(1.2, 1.0) == pytest.approx(0.2)
    # fair 0.8 vs actual 1.0 -> -20% overvalued
    assert calculate_mispricing(0.8, 1.0) == pytest.approx(-0.2)


def test_mispricing_handles_bad_actual():
    assert np.isnan(calculate_mispricing(1.2, 0))
    assert np.isnan(calculate_mispricing(1.2, None))


def test_ranking_order_is_most_undervalued_first():
    df = pd.DataFrame({"ticker": ["A", "B", "C"], "mispricing": [-0.1, 0.3, 0.05]})
    ranked = rank_banks_by_mispricing(df)
    assert list(ranked["ticker"]) == ["B", "C", "A"]
    assert list(ranked["rank"]) == [1, 2, 3]


def test_zscore_global_and_grouped():
    df = pd.DataFrame({
        "ticker": ["A", "B", "C", "D"],
        "country": ["AUS", "AUS", "THA", "THA"],
        "mispricing": [0.1, -0.1, 0.2, -0.2],
    })
    g = calculate_pb_zscores(df, "mispricing", group_col=None, out_col="z")
    assert g["z"].mean() == pytest.approx(0.0, abs=1e-9)
    grouped = calculate_pb_zscores(df, "mispricing", group_col="country", out_col="zc")
    # Within each 2-bank country the z-scores are symmetric around the mean;
    # with sample std (ddof=1) two points give +/- 1/sqrt(2) = 0.7071.
    z_aus = grouped.loc[grouped.country == "AUS", "zc"]
    assert z_aus.abs().tolist() == pytest.approx([2 ** -0.5, 2 ** -0.5])
    assert z_aus.sum() == pytest.approx(0.0, abs=1e-9)


def test_build_relative_value_table():
    df = pd.DataFrame({
        "ticker": ["A", "B", "C"],
        "country": ["AUS", "AUS", "THA"],
        "fair_pb": [1.2, 0.8, 1.0],
        "actual_pb": [1.0, 1.0, 1.0],
    })
    rv = build_relative_value_table(df)
    assert {"mispricing", "mispricing_z_global", "mispricing_z_country", "signal", "rank"} <= set(rv.columns)
    assert rv.iloc[0]["ticker"] == "A"  # most undervalued
    assert rv.loc[rv.ticker == "A", "signal"].iloc[0] == "undervalued"
    assert rv.loc[rv.ticker == "B", "signal"].iloc[0] == "overvalued"
