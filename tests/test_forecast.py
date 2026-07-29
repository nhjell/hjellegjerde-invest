"""Unit tests for the v2 trajectory-aware forecast generator."""

import numpy as np
import pytest

from forecast import (
    build_assumption_rows,
    build_roe_path,
    estimate_trend,
    normalise_level,
    roe_persistence,
    terminal_roe,
)

CFG = {
    "horizon_years": 10,
    "history_years": 4,
    "trend_tilt_weight": 0.5,
    "trend_tilt_cap": 0.02,
    "persistence": 0.75,
    "persistence_adjustment": 0.10,
    "persistence_bounds": [0.55, 0.90],
    "payout_clip": [0.30, 0.90],
    "roe_clip": [0.04, 0.18],
    "terminal": {"franchise_weight": 0.5, "max_durable_spread": 0.02, "spread_floor": -0.01},
    "mean_reversion": 0.60,
    "country_anchors": {
        "AUS": {"terminal_roe": 0.11, "terminal_payout": 0.75, "terminal_growth": 0.035},
    },
}


def test_normalise_averages_last_years():
    # 5 obs, max_years=4 -> average of the last 4 only
    assert normalise_level([0.10, 0.20, 0.20, 0.20], 0.20, 4) == pytest.approx(0.20)
    # One distorted year is diluted, not anchoring
    assert normalise_level([0.10, 0.10, 0.10], 0.02, 4) == pytest.approx(0.08)


def test_normalise_handles_missing():
    assert normalise_level([], None, 4) is None
    assert normalise_level([np.nan], 0.10, 4) == pytest.approx(0.10)


def test_trend_positive_for_improver():
    assert estimate_trend([0.08, 0.09, 0.10], 0.11) == pytest.approx(0.01)
    assert estimate_trend([0.12, 0.11, 0.10], 0.09) == pytest.approx(-0.01)
    assert estimate_trend([], 0.10) == 0.0


def test_improving_bank_keeps_momentum_in_year1():
    """The core fix: an improver's year 1 sits ABOVE its normalised level."""
    norm, trend = 0.095, 0.008
    path = build_roe_path(norm, trend, term_roe=0.10, persistence=0.85, cfg=CFG)
    assert path[0] == pytest.approx(norm + 0.5 * 0.008)
    assert path[0] > norm


def test_trend_tilt_is_capped():
    path = build_roe_path(0.10, trend=0.10, term_roe=0.10, persistence=0.85, cfg=CFG)
    assert path[0] == pytest.approx(0.10 + CFG["trend_tilt_cap"])  # not 0.10 + 0.05


def test_persistence_decay_shape():
    """Abnormal ROE shrinks by the persistence factor each year after year 1."""
    term, p = 0.10, 0.75
    path = build_roe_path(0.16, trend=0.0, term_roe=term, persistence=p, cfg=CFG)
    for t in range(1, len(path)):
        expected = term + p * (path[t - 1] - term)
        assert path[t] == pytest.approx(expected)
    # ...and by year 10 the path has nearly converged to terminal
    assert abs(path[-1] - term) < 0.005


def test_hard_roe_clip_applied_every_year():
    path = build_roe_path(0.30, trend=0.05, term_roe=0.12, persistence=0.9, cfg=CFG)
    assert all(CFG["roe_clip"][0] <= v <= CFG["roe_clip"][1] for v in path)
    assert path[0] == CFG["roe_clip"][1]


def test_persistence_rewards_stability():
    stable = [0.030, 0.031, 0.029, 0.030]        # steady excess spread
    volatile = [0.06, -0.02, 0.05, -0.03]        # erratic spread
    assert roe_persistence(stable, CFG) == pytest.approx(0.85)
    assert roe_persistence(volatile, CFG) == pytest.approx(0.65)
    assert roe_persistence([0.02, 0.025], CFG) == pytest.approx(0.75)  # too few obs -> base


def test_terminal_spread_capped_and_floored():
    tcfg = CFG["terminal"]
    # Star franchise: huge demonstrated spread -> capped at +2%
    assert terminal_roe(0.10, 0.16, tcfg) == pytest.approx(0.12)
    # Weak bank: below its CoE -> floored at -1%
    assert terminal_roe(0.10, 0.04, tcfg) == pytest.approx(0.09)
    # Modest franchise: half its demonstrated spread survives
    assert terminal_roe(0.10, 0.13, tcfg) == pytest.approx(0.10 + 0.5 * 0.03)


def test_build_assumption_rows_schema():
    result = build_assumption_rows(
        ticker="X.AX", country="AUS", coe=0.10,
        current_roe=0.12, current_payout=0.70,
        roe_history=[0.11, 0.115, 0.118], payout_history=[0.68, 0.72, 0.71],
        forecast_cfg=CFG,
    )
    assert result is not None
    rows, diag = result
    years = [r["forecast_year"] for r in rows]
    assert years == [str(t) for t in range(1, 11)] + ["terminal"]
    term = rows[-1]
    assert term["terminal_growth"] == pytest.approx(0.035)
    assert diag["n_roe_observations"] == 4
    # terminal ROE follows the spread rule, not the country anchor
    assert term["roe"] == pytest.approx(terminal_roe(0.10, diag["normalised_roe"], CFG["terminal"]), abs=1e-4)


def test_unknown_country_returns_none():
    assert build_assumption_rows(
        "Y.BK", "XXX", 0.12, 0.10, 0.5, [], [], CFG
    ) is None


def test_payout_distortion_neutralised():
    """A 257%-payout year (BOQ-style) can't drag the path outside sanity."""
    result = build_assumption_rows(
        ticker="B.AX", country="AUS", coe=0.106,
        current_roe=0.016, current_payout=2.57,
        roe_history=[0.059, 0.061, 0.020], payout_history=[0.39, 0.57, 1.80],
        forecast_cfg=CFG,
    )
    rows, diag = result
    assert 0.0 <= diag["normalised_payout"] <= 1.0
    assert all(CFG["payout_clip"][0] <= rows[-1]["payout_ratio"] <= CFG["payout_clip"][1] for _ in [0])
