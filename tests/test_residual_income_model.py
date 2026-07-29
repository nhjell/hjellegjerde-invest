"""Unit tests for the residual income valuation model."""

import numpy as np
import pandas as pd
import pytest

from residual_income_model import (
    ValuationInputError,
    project_residual_income_valuation,
    validate_residual_income_inputs,
    value_all_banks,
    value_bank_from_assumptions,
)


def _flat_inputs(roe=0.12, coe=0.10, payout=0.6, bvps0=10.0, horizon=5):
    return dict(
        bvps0=bvps0,
        roe=[roe] * horizon,
        payout=[payout] * horizon,
        coe=[coe] * horizon,
        terminal_roe=roe,
        terminal_payout=payout,
        terminal_coe=coe,
        terminal_growth=0.02,
    )


def test_bvps_rolls_forward_correctly():
    res = project_residual_income_valuation(**_flat_inputs(roe=0.12, payout=0.5, bvps0=10.0))
    y = res["yearly"]
    # Year 1: EPS = 0.12 * 10 = 1.2, retained = 1.2 * (1-0.5) = 0.6, BVPS_end = 10.6
    assert y.loc[0, "eps"] == pytest.approx(1.2)
    assert y.loc[0, "retained_earnings"] == pytest.approx(0.6)
    assert y.loc[0, "bvps_end"] == pytest.approx(10.6)
    # Year 2 opens where year 1 closed.
    assert y.loc[1, "bvps_begin"] == pytest.approx(10.6)
    assert y.loc[1, "eps"] == pytest.approx(0.12 * 10.6)


def test_residual_income_is_excess_return_on_opening_book():
    res = project_residual_income_valuation(**_flat_inputs(roe=0.12, coe=0.10, bvps0=10.0))
    # RI_1 = (0.12 - 0.10) * 10 = 0.2
    assert res["yearly"].loc[0, "residual_income"] == pytest.approx(0.2)


def test_fair_pb_equals_one_when_roe_equals_coe():
    # A bank earning exactly its cost of equity is worth book value: fair P/B = 1.
    res = project_residual_income_valuation(**_flat_inputs(roe=0.10, coe=0.10))
    assert res["fair_pb"] == pytest.approx(1.0, abs=1e-9)
    assert res["intrinsic_value_per_share"] == pytest.approx(res["bvps0"], abs=1e-9)


def test_fair_pb_above_one_when_roe_exceeds_coe():
    res = project_residual_income_valuation(**_flat_inputs(roe=0.15, coe=0.10))
    assert res["fair_pb"] > 1.0


def test_fair_pb_below_one_when_roe_below_coe():
    res = project_residual_income_valuation(**_flat_inputs(roe=0.06, coe=0.10))
    assert res["fair_pb"] < 1.0


def test_mispricing_sign():
    res = project_residual_income_valuation(actual_pb=1.0, **_flat_inputs(roe=0.15, coe=0.10))
    # fair > 1 and actual = 1 -> undervalued -> positive mispricing
    assert res["mispricing"] > 0


def test_negative_residual_income_allowed():
    inp = _flat_inputs(roe=0.02, coe=0.10)  # ROE below CoE -> negative RI, but valid
    res = project_residual_income_valuation(**inp)
    assert (res["yearly"]["residual_income"] < 0).all()
    assert res["fair_pb"] < 1.0


def test_terminal_coe_must_exceed_growth():
    inp = _flat_inputs()
    inp["terminal_coe"] = 0.03
    inp["terminal_growth"] = 0.05
    with pytest.raises(ValuationInputError):
        validate_residual_income_inputs(**inp)


def test_bvps_must_be_positive():
    inp = _flat_inputs(bvps0=-5.0)
    with pytest.raises(ValuationInputError):
        validate_residual_income_inputs(**inp)


def test_non_numeric_roe_rejected():
    inp = _flat_inputs()
    inp["roe"] = [0.12, 0.12, None, 0.12, 0.12]
    with pytest.raises(ValuationInputError):
        validate_residual_income_inputs(**inp)


def test_closed_form_matches_flat_perpetuity():
    """With flat ROE/CoE/payout, fair P/B must match the Gordon-style closed form.

    For constant ROE and CoE with book growing at g = ROE*(1-payout), residual
    income grows at g, so IV = B0 + (ROE-CoE)*B0/(CoE-g) and
    fair P/B = 1 + (ROE-CoE)/(CoE-g).
    """
    roe, coe, payout = 0.14, 0.10, 0.5
    g = roe * (1 - payout)
    # Make the terminal growth equal the internal growth so the whole path is a
    # single growing perpetuity; use a long horizon so truncation error is tiny.
    inp = dict(bvps0=10.0, roe=[roe] * 5, payout=[payout] * 5, coe=[coe] * 5,
               terminal_roe=roe, terminal_payout=payout, terminal_coe=coe,
               terminal_growth=g)
    res = project_residual_income_valuation(**inp)
    expected_fair_pb = 1 + (roe - coe) / (coe - g)
    assert res["fair_pb"] == pytest.approx(expected_fair_pb, rel=1e-6)


def test_value_bank_from_assumptions_and_value_all_banks():
    assumptions = pd.DataFrame(
        [
            {"ticker": "X", "forecast_year": str(t), "roe": 0.12, "payout_ratio": 0.5,
             "cost_of_equity": 0.10, "terminal_growth": np.nan}
            for t in range(1, 6)
        ]
        + [{"ticker": "X", "forecast_year": "terminal", "roe": 0.12, "payout_ratio": 0.5,
            "cost_of_equity": 0.10, "terminal_growth": 0.02}]
    )
    res = value_bank_from_assumptions("X", assumptions, bvps0=10.0, actual_pb=1.0)
    assert res["fair_pb"] > 1.0

    fundamentals = pd.DataFrame([{"ticker": "X", "country": "AUS", "bvps": 10.0, "actual_pb": 1.0}])
    summary = value_all_banks(fundamentals, assumptions)
    assert list(summary["ticker"]) == ["X"]
    assert summary.loc[0, "rank"] == 1
