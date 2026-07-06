"""Single-stage Gordon Growth Model fair P/B: (payout_ratio * ROE) / (r - g).

r and g are read from config/assumptions.yaml - edit that file, not this one.
"""

import math

import pandas as pd


def _growth_rate(roe: float, payout_ratio: float, assumptions: dict) -> float:
    method = assumptions["growth"]["method"]
    if method == "sustainable":
        return roe * (1 - payout_ratio)
    if method == "flat":
        return assumptions["growth"]["flat_growth_rate"]
    raise ValueError(f"Unknown growth method: {method}")


def build_screen_table(records: list[dict], assumptions: dict) -> pd.DataFrame:
    rows = []
    for rec in records:
        roe = rec.get("returnOnEquity")
        payout = rec.get("payoutRatio")
        pb_actual = rec.get("priceToBook")
        div_yield = rec.get("dividendYield")
        country = rec["country"]
        r = assumptions["cost_of_capital"][country]

        fair_pb = float("nan")
        g = float("nan")
        if roe is not None and payout is not None:
            g = _growth_rate(roe, payout, assumptions)
            if r - g > 0:
                fair_pb = (payout * roe) / (r - g)

        rows.append(
            {
                "name": rec["name"],
                "ticker": rec["ticker"],
                "country": country,
                "cost_of_capital": r,
                "roe": roe,
                "dividend_yield_pct": div_yield,
                "payout_ratio": payout,
                "growth_g": g,
                "pb_actual": pb_actual,
                "pb_fair": fair_pb,
                "upside_pct": (fair_pb / pb_actual - 1) * 100
                if pb_actual not in (None, 0) and not math.isnan(fair_pb)
                else float("nan"),
            }
        )

    df = pd.DataFrame(rows).sort_values(["country", "name"]).reset_index(drop=True)
    return df
