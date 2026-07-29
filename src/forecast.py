"""Forecast path generation for ROE and payout (v2, trajectory-aware).

Replaces the v1 straight-line fade (current -> blended terminal over 5 years)
with a method that respects both the short-term trajectory and the long-run
economics of banking:

1. NORMALISE - the starting level is a multi-year average (last
   `history_years` reported fiscal years + the current TTM snapshot), so a
   single distorted year (a payout of 257% on collapsed earnings, one bad ROE
   print) cannot anchor the whole forecast.

2. TRAJECTORY - the recent trend (per-year slope of annual ROEs) tilts the
   year-1 starting point: an improving bank keeps some momentum instead of
   being immediately dragged down, a deteriorating one keeps some slide. The
   tilt is capped (`trend_tilt_cap`) so four noisy data points can never
   launch an extreme path.

3. REVERSION WITH REAL-WORLD PERSISTENCE - from year 2 onward the abnormal
   component of ROE (ROE_t - terminal ROE) decays geometrically:

       ROE_{t+1} = terminal_roe + persistence * (ROE_t - terminal_roe)

   Empirical work on abnormal earnings (e.g. Dechow-Hutton-Sloan) puts annual
   persistence around 0.6-0.8: reversion is fast at first when profitability
   is far from normal and flattens as it approaches - exactly the "short term
   matters, reversion happens eventually" shape. Banks with a stable excess-
   return record get persistence + adjustment (durable franchises revert
   slower); volatile records get - adjustment.

4. HARD REALISTIC LIMIT - every forecast year is clipped to `roe_clip`; no
   trajectory is allowed to extrapolate beyond what real banks sustain.

5. TERMINAL DISCIPLINE - the terminal ROE is not a mechanical blend but an
   economic statement about the franchise:

       terminal_roe = CoE + clip(franchise_weight * (normalised ROE - CoE),
                                 spread_floor, max_durable_spread)

   i.e. only a fraction of the demonstrated excess spread survives forever,
   and never more than `max_durable_spread` - competition erodes the rest. A
   bank earning below its CoE gets floored at `spread_floor` (structural
   weakness, but consolidation/repricing stops the value destruction from
   compounding forever).

Payout keeps the simpler v1 treatment (normalised start, linear fade to a
country-anchored blend): in a residual income model payout only changes how
fast book value compounds, so it is a second-order driver not worth a complex
rule.

Used by both src/build_inputs.py (live valuation) and
src/backtest.py::generate_point_in_time_assumptions (so the backtest values
banks exactly the way the live model does).
"""

from __future__ import annotations

import numpy as np

from utils import get_logger

logger = get_logger(__name__)


def linear_fade(start: float, end: float, horizon: int) -> list[float]:
    """Linear fade from start (year 0) to end (year `horizon`), years 1..horizon."""
    return [start + (end - start) * (t / horizon) for t in range(1, horizon + 1)]


def normalise_level(history: list[float], current: float | None, max_years: int) -> float | None:
    """Average of the last `max_years` observations (history + current TTM).

    NaNs/Nones are dropped. Returns None when there is no usable data at all.
    """
    values = [v for v in list(history) + [current] if v is not None and np.isfinite(v)]
    if not values:
        return None
    return float(np.mean(values[-max_years:]))


def estimate_trend(history: list[float], current: float | None) -> float:
    """Per-year slope of the recent observations (chronological order).

    OLS slope on 3+ points, simple difference on 2, zero otherwise - four
    annual data points are too thin to deserve anything fancier.
    """
    values = [v for v in list(history) + [current] if v is not None and np.isfinite(v)]
    n = len(values)
    if n < 2:
        return 0.0
    if n == 2:
        return float(values[1] - values[0])
    return float(np.polyfit(np.arange(n), values, 1)[0])


def roe_persistence(spread_history: list[float], cfg: dict) -> float:
    """Annual persistence of abnormal ROE, adjusted for track-record stability.

    A bank whose excess return over CoE has been steady (std < 1.5 ROE points)
    behaves like a durable franchise -> reverts slower (persistence + adj).
    A volatile record (std > 3.5 points) -> reverts faster (- adj).
    """
    base = cfg["persistence"]
    adj = cfg["persistence_adjustment"]
    lo, hi = cfg["persistence_bounds"]

    values = [v for v in spread_history if v is not None and np.isfinite(v)]
    if len(values) >= 3:
        std = float(np.std(values, ddof=1))
        if std < 0.015:
            base += adj
        elif std > 0.035:
            base -= adj
    return float(np.clip(base, lo, hi))


def terminal_roe(coe: float, normalised_roe: float, terminal_cfg: dict) -> float:
    """Terminal ROE = CoE + a disciplined, capped durable franchise spread."""
    spread = terminal_cfg["franchise_weight"] * (normalised_roe - coe)
    spread = float(np.clip(spread, terminal_cfg["spread_floor"], terminal_cfg["max_durable_spread"]))
    return coe + spread


def build_roe_path(
    normalised: float,
    trend: float,
    term_roe: float,
    persistence: float,
    cfg: dict,
) -> list[float]:
    """Years 1..horizon of ROE: trend-tilted start, then geometric decay to terminal."""
    horizon = cfg["horizon_years"]
    lo, hi = cfg["roe_clip"]
    tilt = float(np.clip(cfg["trend_tilt_weight"] * trend, -cfg["trend_tilt_cap"], cfg["trend_tilt_cap"]))

    path = []
    roe_t = float(np.clip(normalised + tilt, lo, hi))
    path.append(roe_t)
    for _ in range(2, horizon + 1):
        roe_t = term_roe + persistence * (roe_t - term_roe)
        path.append(float(np.clip(roe_t, lo, hi)))
    return path


def build_assumption_rows(
    ticker: str,
    country: str,
    coe: float,
    current_roe: float | None,
    current_payout: float | None,
    roe_history: list[float],
    payout_history: list[float],
    forecast_cfg: dict,
) -> tuple[list[dict], dict] | None:
    """Build the forecast_year rows ('1'..horizon + 'terminal') for one bank.

    Returns (rows, diagnostics) or None when the bank can't be forecast
    (unknown country). Row schema matches valuation_assumptions.csv:
    ticker, country, forecast_year, roe, payout_ratio, cost_of_equity,
    terminal_growth.
    """
    anchors = forecast_cfg["country_anchors"]
    if country not in anchors:
        logger.warning("No forecast anchors for country %s (%s); skipping", country, ticker)
        return None
    anc = anchors[country]
    horizon = forecast_cfg["horizon_years"]
    hist_years = forecast_cfg["history_years"]

    # --- ROE ---------------------------------------------------------------
    norm_roe = normalise_level(roe_history, current_roe, hist_years)
    if norm_roe is None:
        norm_roe = anc["terminal_roe"]  # fallback: no usable ROE data at all
        trend = 0.0
        n_roe_obs = 0
    else:
        trend = estimate_trend(roe_history, current_roe)
        n_roe_obs = len([v for v in list(roe_history) + [current_roe] if v is not None and np.isfinite(v)])

    spread_history = [
        v - coe for v in list(roe_history) + [current_roe] if v is not None and np.isfinite(v)
    ]
    persistence = roe_persistence(spread_history, forecast_cfg)
    term_roe = terminal_roe(coe, norm_roe, forecast_cfg["terminal"])
    roe_path = build_roe_path(norm_roe, trend, term_roe, persistence, forecast_cfg)

    # --- Payout (second-order driver: normalised start, linear fade) --------
    clipped_payouts = [
        float(np.clip(v, 0.0, 1.0)) for v in payout_history if v is not None and np.isfinite(v)
    ]
    current_payout_clipped = (
        float(np.clip(current_payout, 0.0, 1.0))
        if current_payout is not None and np.isfinite(current_payout) else None
    )
    norm_payout = normalise_level(clipped_payouts, current_payout_clipped, hist_years)
    if norm_payout is None:
        norm_payout = anc["terminal_payout"]
    mr = forecast_cfg["mean_reversion"]
    term_payout = float(
        np.clip(mr * anc["terminal_payout"] + (1 - mr) * norm_payout, *forecast_cfg["payout_clip"])
    )
    payout_path = linear_fade(norm_payout, term_payout, horizon)

    # --- Assemble rows -------------------------------------------------------
    rows = []
    for t in range(1, horizon + 1):
        rows.append(
            {
                "ticker": ticker,
                "country": country,
                "forecast_year": str(t),
                "roe": round(roe_path[t - 1], 6),
                "payout_ratio": round(payout_path[t - 1], 6),
                "cost_of_equity": round(coe, 6),
                "terminal_growth": np.nan,
            }
        )
    rows.append(
        {
            "ticker": ticker,
            "country": country,
            "forecast_year": "terminal",
            "roe": round(term_roe, 6),
            "payout_ratio": round(term_payout, 6),
            "cost_of_equity": round(coe, 6),
            "terminal_growth": anc["terminal_growth"],
        }
    )

    diagnostics = {
        "ticker": ticker,
        "country": country,
        "n_roe_observations": n_roe_obs,
        "normalised_roe": round(norm_roe, 4),
        "trend_per_year": round(trend, 4),
        "year1_roe": round(roe_path[0], 4),
        "persistence": round(persistence, 3),
        "cost_of_equity": round(coe, 4),
        "terminal_roe": round(term_roe, 4),
        "terminal_spread": round(term_roe - coe, 4),
        "normalised_payout": round(norm_payout, 4),
        "terminal_payout": round(term_payout, 4),
    }
    return rows, diagnostics
