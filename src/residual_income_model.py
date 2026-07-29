"""5-year residual income (excess return) valuation for banks.

Why residual income and not DCF/FCFF for banks
-----------------------------------------------
For a bank, debt (deposits, wholesale funding) is raw material, not just
financing, so enterprise value / free-cash-flow-to-firm frameworks don't apply
cleanly. Instead we value the *equity* directly off book value and the excess
return the bank earns on that book value:

    Residual Income_t = (ROE_t - CostOfEquity_t) * BVPS_{t-1}

A bank that earns exactly its cost of equity is worth exactly its book value
(fair P/B = 1). Value is created only when ROE > CoE. The intrinsic value per
share is today's book value plus the present value of all future excess returns:

    IV_0 = BVPS_0 + sum_{t=1..5} PV(RI_t) + PV(Terminal Value)
    Fair P/B = IV_0 / BVPS_0

This module is bank-by-bank and country-aware: every bank carries its own ROE,
payout, and cost-of-equity path, so no two banks are forced to share
assumptions.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from utils import get_logger, is_number

logger = get_logger(__name__)


class ValuationInputError(ValueError):
    """Raised when residual income inputs are structurally invalid."""


def validate_residual_income_inputs(
    bvps0: float,
    roe: list[float],
    payout: list[float],
    coe: list[float],
    terminal_roe: float,
    terminal_payout: float,
    terminal_coe: float,
    terminal_growth: float,
    horizon: int = 5,
) -> None:
    """Validate structure and financial admissibility of the inputs.

    Rules enforced:
      * BVPS_0 must be a positive number (book value per share > 0).
      * ROE, payout, cost of equity and growth must all be numeric.
      * The three forecast paths must each have `horizon` entries.
      * Terminal cost of equity must exceed terminal growth, else the terminal
        value formula RI / (CoE - g) blows up or goes negative nonsensically.
    Negative residual income is allowed (a bank can destroy value).
    """
    if not is_number(bvps0):
        raise ValuationInputError(f"BVPS_0={bvps0!r} is not numeric")
    if bvps0 <= 0:
        raise ValuationInputError(f"BVPS_0 must be positive, got {bvps0}")

    for label, path in (("roe", roe), ("payout", payout), ("coe", coe)):
        if len(path) != horizon:
            raise ValuationInputError(
                f"{label} path has {len(path)} entries, expected horizon={horizon}"
            )
        for i, v in enumerate(path, start=1):
            if not is_number(v):
                raise ValuationInputError(f"{label}[year {i}]={v!r} is not numeric")

    for name, v in (
        ("terminal_roe", terminal_roe),
        ("terminal_payout", terminal_payout),
        ("terminal_coe", terminal_coe),
        ("terminal_growth", terminal_growth),
    ):
        if not is_number(v):
            raise ValuationInputError(f"{name}={v!r} is not numeric")

    if terminal_coe <= terminal_growth:
        raise ValuationInputError(
            f"terminal_coe ({terminal_coe}) must be > terminal_growth "
            f"({terminal_growth}); otherwise the terminal value diverges."
        )


def project_residual_income_valuation(
    bvps0: float,
    roe: list[float],
    payout: list[float],
    coe: list[float],
    terminal_roe: float,
    terminal_payout: float,
    terminal_coe: float,
    terminal_growth: float,
    actual_pb: float | None = None,
    horizon: int = 5,
) -> dict:
    """Run the full residual income projection for a single bank.

    Returns a dict with:
        yearly: DataFrame (one row per forecast year) with bvps_begin, roe,
                eps, dps, retained_earnings, bvps_end, cost_of_equity,
                residual_income, discount_factor, pv_residual_income
        terminal_value, pv_terminal_value, sum_pv_residual_income
        intrinsic_value_per_share, fair_pb, actual_pb, mispricing
    """
    validate_residual_income_inputs(
        bvps0, roe, payout, coe, terminal_roe, terminal_payout,
        terminal_coe, terminal_growth, horizon=horizon,
    )

    rows = []
    bvps_prev = bvps0
    cumulative_discount = 1.0
    for t in range(1, horizon + 1):
        roe_t = roe[t - 1]
        payout_t = payout[t - 1]
        coe_t = coe[t - 1]

        eps_t = roe_t * bvps_prev
        dps_t = eps_t * payout_t
        retained_t = eps_t - dps_t
        bvps_end = bvps_prev + retained_t
        # Residual income = excess return over the cost of equity, on opening book.
        ri_t = (roe_t - coe_t) * bvps_prev

        # Cumulative (period-by-period) discount factor, so a changing CoE path
        # compounds correctly rather than assuming a single flat rate.
        cumulative_discount *= (1.0 + coe_t)
        pv_ri_t = ri_t / cumulative_discount

        rows.append(
            {
                "year": t,
                "bvps_begin": bvps_prev,
                "roe": roe_t,
                "eps": eps_t,
                "payout_ratio": payout_t,
                "dps": dps_t,
                "retained_earnings": retained_t,
                "bvps_end": bvps_end,
                "cost_of_equity": coe_t,
                "residual_income": ri_t,
                "discount_factor": cumulative_discount,
                "pv_residual_income": pv_ri_t,
            }
        )
        bvps_prev = bvps_end

    yearly = pd.DataFrame(rows)
    bvps_terminal_base = bvps_prev  # BVPS at end of year `horizon`
    sum_pv_ri = yearly["pv_residual_income"].sum()

    # Terminal residual income grows at terminal_growth forever; value it as a
    # growing perpetuity discounted back over the forecast horizon.
    terminal_ri = (terminal_roe - terminal_coe) * bvps_terminal_base
    terminal_value = terminal_ri / (terminal_coe - terminal_growth)
    pv_terminal_value = terminal_value / cumulative_discount

    intrinsic_value = bvps0 + sum_pv_ri + pv_terminal_value
    fair_pb = intrinsic_value / bvps0

    mispricing = np.nan
    if actual_pb is not None and is_number(actual_pb) and actual_pb != 0:
        mispricing = fair_pb / actual_pb - 1.0

    return {
        "yearly": yearly,
        "bvps0": bvps0,
        "bvps_terminal": bvps_terminal_base,
        "sum_pv_residual_income": sum_pv_ri,
        "terminal_residual_income": terminal_ri,
        "terminal_value": terminal_value,
        "pv_terminal_value": pv_terminal_value,
        "intrinsic_value_per_share": intrinsic_value,
        "fair_pb": fair_pb,
        "actual_pb": actual_pb if actual_pb is not None else np.nan,
        "terminal_payout": terminal_payout,
        "mispricing": mispricing,
    }


def _paths_from_assumptions(assump: pd.DataFrame, horizon: int) -> tuple:
    """Extract (roe[], payout[], coe[], terminal dict) for one ticker's rows.

    `assump` is the subset of valuation_assumptions for a single ticker,
    containing forecast_year rows '1'..'horizon' plus a 'terminal' row.
    """
    forecast = assump[assump["forecast_year"].astype(str) != "terminal"].copy()
    forecast["forecast_year"] = forecast["forecast_year"].astype(int)
    forecast = forecast.sort_values("forecast_year")

    years = forecast["forecast_year"].tolist()
    if years != list(range(1, horizon + 1)):
        raise ValuationInputError(
            f"Expected forecast years 1..{horizon}, got {years}"
        )

    roe = forecast["roe"].tolist()
    payout = forecast["payout_ratio"].tolist()
    coe = forecast["cost_of_equity"].tolist()

    term_rows = assump[assump["forecast_year"].astype(str) == "terminal"]
    if term_rows.empty:
        raise ValuationInputError("No 'terminal' forecast_year row found")
    term = term_rows.iloc[0]
    terminal = {
        "terminal_roe": float(term["roe"]),
        "terminal_payout": float(term["payout_ratio"]),
        "terminal_coe": float(term["cost_of_equity"]),
        "terminal_growth": float(term["terminal_growth"]),
    }
    return roe, payout, coe, terminal


def value_bank_from_assumptions(
    ticker: str,
    assumptions: pd.DataFrame,
    bvps0: float,
    actual_pb: float | None = None,
    horizon: int = 5,
) -> dict:
    """Value one bank given its rows from the valuation_assumptions table."""
    assump = assumptions[assumptions["ticker"] == ticker]
    if assump.empty:
        raise ValuationInputError(f"No assumptions rows for ticker {ticker}")
    roe, payout, coe, terminal = _paths_from_assumptions(assump, horizon)
    result = project_residual_income_valuation(
        bvps0=bvps0, roe=roe, payout=payout, coe=coe,
        actual_pb=actual_pb, horizon=horizon, **terminal,
    )
    result["ticker"] = ticker
    return result


def value_all_banks(
    fundamentals: pd.DataFrame,
    assumptions: pd.DataFrame,
    horizon: int = 5,
    return_yearly: bool = False,
):
    """Value every bank present in both `fundamentals` and `assumptions`.

    `fundamentals` must have columns: ticker, country, bvps, actual_pb.
    Returns a summary DataFrame (one row per bank), ranked by mispricing
    (most undervalued first). If return_yearly is True, also returns a long
    DataFrame with the per-year projection for every bank.
    """
    summary_rows = []
    yearly_frames = []

    for _, f in fundamentals.iterrows():
        ticker = f["ticker"]
        bvps0 = f.get("bvps")
        actual_pb = f.get("actual_pb")
        if not is_number(bvps0) or bvps0 <= 0:
            logger.warning("Skipping %s: non-positive/missing BVPS (%s)", ticker, bvps0)
            continue
        if ticker not in set(assumptions["ticker"]):
            logger.warning("Skipping %s: no valuation assumptions", ticker)
            continue
        try:
            res = value_bank_from_assumptions(
                ticker, assumptions, bvps0,
                actual_pb=actual_pb if is_number(actual_pb) else None,
                horizon=horizon,
            )
        except ValuationInputError as e:
            logger.warning("Skipping %s: %s", ticker, e)
            continue

        summary_rows.append(
            {
                "ticker": ticker,
                "country": f.get("country"),
                "bvps0": res["bvps0"],
                "intrinsic_value_per_share": res["intrinsic_value_per_share"],
                "fair_pb": res["fair_pb"],
                "actual_pb": res["actual_pb"],
                "mispricing": res["mispricing"],
                "sum_pv_residual_income": res["sum_pv_residual_income"],
                "pv_terminal_value": res["pv_terminal_value"],
            }
        )
        if return_yearly:
            y = res["yearly"].copy()
            y.insert(0, "ticker", ticker)
            yearly_frames.append(y)

    summary = pd.DataFrame(summary_rows)
    if not summary.empty:
        summary = summary.sort_values("mispricing", ascending=False).reset_index(drop=True)
        summary["rank"] = np.arange(1, len(summary) + 1)

    if return_yearly:
        yearly = pd.concat(yearly_frames, ignore_index=True) if yearly_frames else pd.DataFrame()
        return summary, yearly
    return summary
