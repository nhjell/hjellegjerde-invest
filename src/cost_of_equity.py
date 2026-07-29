"""Cost of equity via CAPM, with an explicit country risk premium.

    CoE = risk_free_rate + beta * equity_risk_premium + country_risk_premium

The country risk premium is what lets the model *explain* why Thai banks can
rationally trade at a lower Price-to-Book than Australian banks for the same
ROE: a higher required return shrinks the fair P/B. We deliberately keep it as
a separate, visible term rather than burying it inside beta so it can be
audited and stressed.
"""

from __future__ import annotations

import pandas as pd

from utils import get_logger, is_number

logger = get_logger(__name__)


def calculate_cost_of_equity(
    risk_free_rate: float,
    beta: float,
    equity_risk_premium: float,
    country_risk_premium: float = 0.0,
) -> float:
    """CAPM cost of equity with an additive country risk premium.

    All inputs are decimals (0.055 == 5.5%). Raises on non-numeric input so a
    bad assumption fails loudly rather than silently producing NaN downstream.
    """
    for name, val in (
        ("risk_free_rate", risk_free_rate),
        ("beta", beta),
        ("equity_risk_premium", equity_risk_premium),
        ("country_risk_premium", country_risk_premium),
    ):
        if not is_number(val):
            raise ValueError(f"calculate_cost_of_equity: {name}={val!r} is not numeric")
    return risk_free_rate + beta * equity_risk_premium + country_risk_premium


def build_cost_of_equity_inputs(universe: list[dict], capm_cfg: dict) -> pd.DataFrame:
    """Build the per-bank CAPM input table from the universe + config defaults.

    Returns a DataFrame with columns:
        ticker, country, beta, risk_free_rate, equity_risk_premium,
        country_risk_premium, cost_of_equity
    """
    defaults = capm_cfg["country_defaults"]
    beta_overrides = capm_cfg.get("beta_overrides", {})
    flat_cfg = capm_cfg.get("flat_cost_of_equity", {})
    flat_rate = flat_cfg.get("rate") if flat_cfg.get("enabled") else None

    rows = []
    for bank in universe:
        ticker = bank["yahoo_ticker"]
        country = bank["country"]
        if country not in defaults:
            raise KeyError(f"No CAPM defaults for country {country!r} (ticker {ticker})")
        cd = defaults[country]
        beta = beta_overrides.get(ticker, cd["default_beta"])
        capm_coe = calculate_cost_of_equity(
            risk_free_rate=cd["risk_free_rate"],
            beta=beta,
            equity_risk_premium=cd["equity_risk_premium"],
            country_risk_premium=cd["country_risk_premium"],
        )
        rows.append(
            {
                "ticker": ticker,
                "country": country,
                "beta": beta,
                "risk_free_rate": cd["risk_free_rate"],
                "equity_risk_premium": cd["equity_risk_premium"],
                "country_risk_premium": cd["country_risk_premium"],
                # CAPM value kept for reference even when the flat override is on.
                "capm_cost_of_equity": capm_coe,
                "coe_method": "flat" if flat_rate is not None else "capm",
                "cost_of_equity": flat_rate if flat_rate is not None else capm_coe,
            }
        )
    if flat_rate is not None:
        logger.info("Flat cost of equity override ON: every bank at %.2f%%", flat_rate * 100)
    return pd.DataFrame(rows)


def apply_cost_of_equity_table(df: pd.DataFrame) -> pd.DataFrame:
    """(Re)compute cost_of_equity from the component columns of a CoE table.

    Lets a user hand-edit beta / premia in cost_of_equity_inputs.csv and have
    the cost_of_equity column recomputed consistently.
    """
    required = {"risk_free_rate", "beta", "equity_risk_premium"}
    missing = required - set(df.columns)
    if missing:
        raise KeyError(f"apply_cost_of_equity_table missing columns: {sorted(missing)}")
    out = df.copy()
    crp = out["country_risk_premium"] if "country_risk_premium" in out.columns else 0.0
    out["cost_of_equity"] = (
        out["risk_free_rate"] + out["beta"] * out["equity_risk_premium"] + crp
    )
    return out


def compare_country_cost_of_equity(df: pd.DataFrame) -> pd.DataFrame:
    """Summarise average CoE and its components by country (AUS vs THA)."""
    cols = [
        "cost_of_equity",
        "beta",
        "risk_free_rate",
        "equity_risk_premium",
        "country_risk_premium",
    ]
    present = [c for c in cols if c in df.columns]
    summary = df.groupby("country")[present].mean().reset_index()
    summary = summary.rename(columns={c: f"avg_{c}" for c in present})
    return summary
