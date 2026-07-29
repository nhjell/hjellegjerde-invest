"""Unit tests for the CAPM cost of equity module."""

import pandas as pd
import pytest

from cost_of_equity import (
    apply_cost_of_equity_table,
    build_cost_of_equity_inputs,
    calculate_cost_of_equity,
    compare_country_cost_of_equity,
)


def test_capm_formula():
    # 0.04 + 1.0 * 0.05 + 0.0 = 0.09
    assert calculate_cost_of_equity(0.04, 1.0, 0.05) == pytest.approx(0.09)


def test_country_risk_premium_is_added():
    base = calculate_cost_of_equity(0.04, 1.0, 0.05, country_risk_premium=0.0)
    with_crp = calculate_cost_of_equity(0.04, 1.0, 0.05, country_risk_premium=0.03)
    assert with_crp == pytest.approx(base + 0.03)


def test_beta_scales_only_the_erp():
    low = calculate_cost_of_equity(0.04, 0.5, 0.06)
    high = calculate_cost_of_equity(0.04, 1.5, 0.06)
    assert high - low == pytest.approx((1.5 - 0.5) * 0.06)


def test_non_numeric_input_raises():
    with pytest.raises(ValueError):
        calculate_cost_of_equity(0.04, None, 0.05)


def test_build_and_country_comparison():
    universe = [
        {"yahoo_ticker": "A.AX", "country": "AUS", "name": "A"},
        {"yahoo_ticker": "B.BK", "country": "THA", "name": "B"},
    ]
    capm_cfg = {
        "country_defaults": {
            "AUS": {"risk_free_rate": 0.043, "equity_risk_premium": 0.055,
                    "country_risk_premium": 0.0, "default_beta": 1.0},
            "THA": {"risk_free_rate": 0.025, "equity_risk_premium": 0.070,
                    "country_risk_premium": 0.030, "default_beta": 0.95},
        },
        "beta_overrides": {"A.AX": 1.1},
    }
    df = build_cost_of_equity_inputs(universe, capm_cfg)
    # Override applied for A.AX
    assert df.loc[df.ticker == "A.AX", "beta"].iloc[0] == 1.1
    # Thailand should have a higher cost of equity here (the whole point).
    aus = df.loc[df.ticker == "A.AX", "cost_of_equity"].iloc[0]
    tha = df.loc[df.ticker == "B.BK", "cost_of_equity"].iloc[0]
    assert tha > aus

    summary = compare_country_cost_of_equity(df)
    assert set(summary["country"]) == {"AUS", "THA"}


def test_flat_cost_of_equity_override():
    universe = [
        {"yahoo_ticker": "A.AX", "country": "AUS", "name": "A"},
        {"yahoo_ticker": "B.BK", "country": "THA", "name": "B"},
    ]
    capm_cfg = {
        "flat_cost_of_equity": {"enabled": True, "rate": 0.10},
        "country_defaults": {
            "AUS": {"risk_free_rate": 0.043, "equity_risk_premium": 0.055,
                    "country_risk_premium": 0.0, "default_beta": 1.0},
            "THA": {"risk_free_rate": 0.025, "equity_risk_premium": 0.070,
                    "country_risk_premium": 0.030, "default_beta": 0.95},
        },
    }
    df = build_cost_of_equity_inputs(universe, capm_cfg)
    assert (df["cost_of_equity"] == 0.10).all()
    assert (df["coe_method"] == "flat").all()
    # CAPM reference values still computed and different from the flat rate
    assert df["capm_cost_of_equity"].nunique() == 2

    capm_cfg["flat_cost_of_equity"]["enabled"] = False
    df2 = build_cost_of_equity_inputs(universe, capm_cfg)
    assert (df2["cost_of_equity"] == df2["capm_cost_of_equity"]).all()
    assert (df2["coe_method"] == "capm").all()


def test_apply_cost_of_equity_table_recomputes():
    df = pd.DataFrame([{"ticker": "A", "risk_free_rate": 0.04, "beta": 1.0,
                        "equity_risk_premium": 0.05, "country_risk_premium": 0.02,
                        "cost_of_equity": 999.0}])
    out = apply_cost_of_equity_table(df)
    assert out.loc[0, "cost_of_equity"] == pytest.approx(0.11)
