"""Sensitivity analysis for the residual income fair P/B.

The headline table is Fair P/B as a function of terminal ROE and terminal cost
of equity - the two assumptions the valuation is most exposed to, because they
drive the perpetuity that usually dominates intrinsic value. Also supported:
terminal cost of equity vs terminal growth, and forecast ROE vs payout.
"""

from __future__ import annotations

import pandas as pd

from residual_income_model import ValuationInputError, value_bank_from_assumptions

# Which assumption column each shift name maps to, and whether it hits the
# terminal row only or every forecast (non-terminal) row.
_SHIFT_SPEC = {
    "roe": ("roe", "forecast"),
    "payout": ("payout_ratio", "forecast"),
    "coe": ("cost_of_equity", "forecast"),
    "terminal_roe": ("roe", "terminal"),
    "terminal_payout": ("payout_ratio", "terminal"),
    "terminal_coe": ("cost_of_equity", "terminal"),
    "terminal_growth": ("terminal_growth", "terminal"),
}


def _apply_shift(assump_ticker: pd.DataFrame, shift_name: str, amount: float) -> pd.DataFrame:
    if shift_name not in _SHIFT_SPEC:
        raise KeyError(f"Unknown sensitivity shift {shift_name!r}; valid: {sorted(_SHIFT_SPEC)}")
    col, scope = _SHIFT_SPEC[shift_name]
    out = assump_ticker.copy()
    is_terminal = out["forecast_year"].astype(str) == "terminal"
    mask = is_terminal if scope == "terminal" else ~is_terminal
    out.loc[mask, col] = out.loc[mask, col] + amount
    return out


def two_way_sensitivity(
    ticker: str,
    assumptions: pd.DataFrame,
    bvps0: float,
    param_x: str,
    x_shifts: list[float],
    param_y: str,
    y_shifts: list[float],
    actual_pb: float | None = None,
    metric: str = "fair_pb",
    horizon: int = 5,
) -> pd.DataFrame:
    """Grid of `metric` (fair_pb or mispricing) over two shifted parameters.

    Rows are indexed by param_y shifts, columns by param_x shifts. Cells that
    violate a validation rule (e.g. terminal CoE <= growth) come back as NaN.
    """
    base = assumptions[assumptions["ticker"] == ticker].copy()
    if base.empty:
        raise ValuationInputError(f"No assumptions rows for ticker {ticker}")

    grid = {}
    for yv in y_shifts:
        row_vals = []
        for xv in x_shifts:
            shifted = _apply_shift(base, param_x, xv)
            shifted = _apply_shift(shifted, param_y, yv)
            full = pd.concat([assumptions[assumptions["ticker"] != ticker], shifted], ignore_index=True)
            try:
                res = value_bank_from_assumptions(
                    ticker, full, bvps0, actual_pb=actual_pb, horizon=horizon
                )
                row_vals.append(res[metric])
            except ValuationInputError:
                row_vals.append(float("nan"))
        grid[round(yv, 4)] = row_vals

    table = pd.DataFrame(grid, index=[round(x, 4) for x in x_shifts]).T
    table.index.name = f"{param_y}_shift"
    table.columns.name = f"{param_x}_shift"
    return table


def terminal_roe_vs_coe(
    ticker: str,
    assumptions: pd.DataFrame,
    bvps0: float,
    roe_shifts: list[float],
    coe_shifts: list[float],
    actual_pb: float | None = None,
    horizon: int = 5,
) -> pd.DataFrame:
    """Headline table: Fair P/B vs terminal ROE (cols) and terminal CoE (rows)."""
    return two_way_sensitivity(
        ticker, assumptions, bvps0,
        param_x="terminal_roe", x_shifts=roe_shifts,
        param_y="terminal_coe", y_shifts=coe_shifts,
        actual_pb=actual_pb, metric="fair_pb", horizon=horizon,
    )
