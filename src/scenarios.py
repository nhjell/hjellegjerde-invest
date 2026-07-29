"""Scenario analysis: base / bull / bear cases via additive assumption shifts.

Each scenario shifts ROE and cost of equity across all forecast years (and the
terminal year), plus a shift to terminal growth. The residual income model is
then re-run under each shifted assumption set. Shifts are additive in decimal
space (e.g. roe_shift: 0.01 adds one percentage point to every ROE).
"""

from __future__ import annotations

import pandas as pd

from residual_income_model import value_all_banks
from utils import get_logger

logger = get_logger(__name__)


def apply_scenario_shifts(assumptions: pd.DataFrame, scenario_cfg: dict) -> pd.DataFrame:
    """Return a copy of the assumptions table with a scenario's shifts applied.

    roe_shift and coe_shift apply to every row (all forecast years + terminal).
    terminal_growth_shift applies only where terminal_growth is defined
    (the terminal row).
    """
    out = assumptions.copy()
    out["roe"] = out["roe"] + scenario_cfg.get("roe_shift", 0.0)
    out["cost_of_equity"] = out["cost_of_equity"] + scenario_cfg.get("coe_shift", 0.0)
    if "terminal_growth" in out.columns:
        mask = out["terminal_growth"].notna()
        out.loc[mask, "terminal_growth"] = (
            out.loc[mask, "terminal_growth"] + scenario_cfg.get("terminal_growth_shift", 0.0)
        )
    return out


def run_scenario_analysis(
    fundamentals: pd.DataFrame,
    assumptions: pd.DataFrame,
    scenarios_cfg: dict,
    horizon: int = 5,
) -> pd.DataFrame:
    """Value every bank under each scenario.

    Returns a long DataFrame with columns:
        ticker, country, scenario, intrinsic_value_per_share, fair_pb,
        actual_pb, mispricing
    """
    frames = []
    for scenario_name, cfg in scenarios_cfg.items():
        shifted = apply_scenario_shifts(assumptions, cfg)
        summary = value_all_banks(fundamentals, shifted, horizon=horizon)
        if summary.empty:
            logger.warning("Scenario %s produced no valuations", scenario_name)
            continue
        summary = summary.copy()
        summary.insert(2, "scenario", scenario_name)
        frames.append(
            summary[
                ["ticker", "country", "scenario", "intrinsic_value_per_share",
                 "fair_pb", "actual_pb", "mispricing"]
            ]
        )

    if not frames:
        return pd.DataFrame(
            columns=["ticker", "country", "scenario", "intrinsic_value_per_share",
                     "fair_pb", "actual_pb", "mispricing"]
        )
    out = pd.concat(frames, ignore_index=True)
    return out.sort_values(["ticker", "scenario"]).reset_index(drop=True)
