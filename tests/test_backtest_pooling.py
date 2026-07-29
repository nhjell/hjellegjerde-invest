"""Regression tests for the point-in-time backtest helpers.

The bug these guard against: `value_region_at_date` refuses to value a market
with fewer than MIN_BANKS_PER_DATE names, which is right for a standalone
regional book but silently dropped every single-bank country (Norway, Sweden,
Denmark) from the pooled *global* ranking.
"""

import pandas as pd
import pytest

from backtest_flat_coe import MIN_BANKS_PER_DATE, PUBLICATION_LAG_DAYS, value_region_at_date

FORECAST_CFG = {
    "horizon_years": 10,
    "history_years": 4,
    "trend_tilt_weight": 0.5,
    "trend_tilt_cap": 0.02,
    "persistence": 0.80,
    "persistence_adjustment": 0.10,
    "persistence_bounds": [0.60, 0.92],
    "payout_clip": [0.30, 0.90],
    "roe_clip": [0.04, 0.18],
    "terminal": {"franchise_weight": 0.75, "max_durable_spread": 0.05, "spread_floor": -0.04},
    "mean_reversion": 0.60,
    "country_anchors": {
        "NOR": {"terminal_roe": 0.12, "terminal_payout": 0.65, "terminal_growth": 0.035},
    },
}

AS_OF = pd.Timestamp("2026-06-30")


def _one_bank_country():
    """Fundamentals + prices for a single-bank market with 3 effective reports."""
    rows = []
    for year, roe in ((2022, 0.134), (2023, 0.147), (2024, 0.162)):
        fye = pd.Timestamp(f"{year}-12-31")
        rows.append({
            "ticker": "SOLO.OL", "country": "NOR", "fiscal_year_end": fye,
            "effective_date": fye + pd.Timedelta(days=PUBLICATION_LAG_DAYS),
            "roe": roe, "payout_ratio": 0.50, "bvps": 100.0 + year - 2022,
        })
    fundamentals = pd.DataFrame(rows)
    prices = {"SOLO.OL": pd.Series(
        150.0, index=pd.date_range("2022-01-01", AS_OF, freq="B")
    )}
    return fundamentals, prices


def test_single_bank_country_dropped_by_default_guard():
    """Default behaviour (regional book): too thin to rank -> empty."""
    fundamentals, prices = _one_bank_country()
    out = value_region_at_date(AS_OF, "NOR", fundamentals, prices, FORECAST_CFG)
    assert out.empty
    assert MIN_BANKS_PER_DATE > 1  # the guard is what makes this empty


def test_single_bank_country_valued_when_pooling():
    """min_banks=1 (global pooling): the bank must be valued, not dropped."""
    fundamentals, prices = _one_bank_country()
    out = value_region_at_date(AS_OF, "NOR", fundamentals, prices, FORECAST_CFG, min_banks=1)
    assert len(out) == 1
    assert out.iloc[0]["ticker"] == "SOLO.OL"
    assert out.iloc[0]["fair_pb"] > 0
    assert pd.notna(out.iloc[0]["mispricing"])


def test_publication_lag_excludes_unreported_year():
    """A fiscal year whose report is not yet 'published' must be invisible."""
    fundamentals, prices = _one_bank_country()
    # As of just before the 2024 report becomes effective, only 2 reports exist.
    just_before = fundamentals["effective_date"].max() - pd.Timedelta(days=1)
    visible = fundamentals[fundamentals["effective_date"] <= just_before]
    assert len(visible) == 2
    out = value_region_at_date(just_before, "NOR", fundamentals, prices, FORECAST_CFG, min_banks=1)
    assert len(out) == 1  # still valued, just on a smaller information set
