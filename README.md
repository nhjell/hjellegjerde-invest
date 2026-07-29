# Bank Equity Valuation with Residual Income

A transparent Python research pipeline for valuing 19 listed banks across
Australia, Thailand, Norway, Sweden, and Denmark. The project converts
bank-specific forecasts for return on equity (ROE), payout, and cost of equity
into an implied fair price-to-book ratio (P/B), then compares fair P/B with the
market P/B to rank possible under- and overvaluation.

The main workflow is configuration-driven, writes auditable intermediate CSVs,
and produces standalone interactive Plotly charts. It is a research tool—not
investment advice or a production trading system.

## What the repository does

| Stage | Purpose | Main file |
|---|---|---|
| 1. Define | Set the bank universe and model assumptions | `config/*.yaml` |
| 2. Fetch | Cache current Yahoo Finance snapshots and annual fundamentals | `src/fetch.py` |
| 3. Build | Turn raw cache files and configuration into reviewable model inputs | `src/build_inputs.py` |
| 4. Value | Run the residual-income model for every bank | `src/run_valuation.py` |
| 5. Compare | Rank mispricing and run country, scenario, and sensitivity analyses | `src/relative_value.py`, `src/scenarios.py`, `src/sensitivity.py` |
| 6. Review | Inspect generated CSV tables and interactive HTML charts | `data/processed/`, `outputs/` |

The active universe is defined only in
[`config/universe.yaml`](config/universe.yaml):

| Market | Country code | Banks | Yahoo suffix |
|---|---:|---:|---|
| Australia | `AUS` | 8 | `.AX` |
| Thailand | `THA` | 8 | `.BK` |
| Norway | `NOR` | 1 | `.OL` |
| Sweden | `SWE` | 1 | `.ST` |
| Denmark | `DNK` | 1 | `.CO` |
| **Total** |  | **19** |  |

## Why residual income

Deposits and wholesale funding are operating inputs for a bank, so conventional
enterprise-value and free-cash-flow-to-firm approaches do not fit as cleanly as
they do for non-financial companies. This model values equity directly:

```text
EPS_t             = ROE_t × BVPS_(t-1)
Dividends_t       = EPS_t × payout_t
BVPS_t            = BVPS_(t-1) + EPS_t - Dividends_t
Residual income_t = (ROE_t - CoE_t) × BVPS_(t-1)
```

For an explicit horizon of `H` years:

```text
Intrinsic value = BVPS_0 + Σ PV(residual income_t) + PV(terminal value)
Fair P/B        = intrinsic value / BVPS_0
Mispricing      = fair P/B / actual P/B - 1
```

A positive mispricing estimate means modelled fair P/B is above market P/B;
a negative estimate means it is below market P/B. A bank earning exactly its
cost of equity has no residual income and is worth book value under the model.

Terminal value is a growing perpetuity of residual income:

```text
Terminal residual income = (terminal ROE - terminal CoE) × BVPS_H
Terminal value           = terminal residual income / (terminal CoE - g)
```

The implementation rejects terminal assumptions where `terminal CoE <= g`,
because the perpetuity would not be economically or mathematically valid.

## Forecast and cost-of-equity logic

The current explicit forecast horizon is 10 years and is controlled by
`forecast.horizon_years` in
[`config/assumptions.yaml`](config/assumptions.yaml).

ROE forecasts are generated in five steps:

1. Average the latest available annual observations and current snapshot.
2. Apply a capped first-year tilt from the recent ROE trend.
3. Mean-revert abnormal ROE toward a terminal level using a persistence factor.
4. Clip each forecast year to the configured realistic ROE range.
5. Estimate terminal ROE as cost of equity plus a capped fraction of the
   bank's demonstrated excess return.

Cost of equity uses CAPM plus an explicit country risk premium:

```text
CoE = risk-free rate + beta × equity risk premium + country risk premium
```

The generated `data/processed/forecast_diagnostics.csv` records the normalized
ROE, trend, persistence, terminal ROE, and payout choices for each bank.

## Quick start

Python 3.12 or newer is recommended.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

A fresh clone contains configuration and selected example outputs, but raw and
processed data are intentionally Git-ignored. Fetch current data, build the
inputs, and run the valuation:

```bash
python src/fetch.py
python src/build_inputs.py
python src/run_valuation.py
```

`run_valuation.py` automatically runs `build_inputs.py` when required processed
inputs are missing. It does not download market data automatically, so a fresh
clone still needs `fetch.py` first.

To replace today's cached Yahoo Finance data before rebuilding:

```bash
python src/fetch.py --refresh
python src/build_inputs.py
python src/run_valuation.py
```

Useful fetch modes:

| Command | Result |
|---|---|
| `python src/fetch.py` | Fetch or reuse today's snapshot and annual history for all configured banks |
| `python src/fetch.py --refresh` | Redownload and overwrite today's cache |
| `python src/fetch.py --snapshot-only` | Update only point-in-time market/fundamental snapshots |
| `python src/fetch.py --history-only` | Update only annual ROE, payout, and BVPS history |

Yahoo Finance access is required only for the fetch step. Building inputs,
running valuations, tests, and chart generation work from local files.

## Configuration

[`config/assumptions.yaml`](config/assumptions.yaml) is the single source of
truth for model settings.

| Section | Controls |
|---|---|
| `capm.flat_cost_of_equity` | Optional common CoE override for comparison runs |
| `capm.country_defaults` | Risk-free rate, ERP, country premium, and fallback beta |
| `capm.beta_overrides` | Per-bank beta assumptions |
| `forecast` | Horizon, history window, trend tilt, persistence, and sanity clips |
| `forecast.terminal` | Durable franchise spread, cap, and floor |
| `forecast.country_anchors` | Fallback terminal ROE, payout, and growth by country |
| `scenarios` | Additive bull/base/bear shifts |
| `sensitivity` | Terminal ROE, CoE, and growth stress grids |
| `cost_of_capital`, `growth` | Inputs for the older single-stage GGM screen only |

All percentage-like model inputs are decimals: `0.10` means 10%.

After changing the universe or assumptions, rebuild the processed inputs before
running the model:

```bash
python src/build_inputs.py
python src/run_valuation.py
```

Generated CSVs are overwritten by `build_inputs.py`. If you want to preserve a
manual analyst case, copy it elsewhere or encode the change in configuration
before rebuilding.

## Outputs

The main pipeline writes:

| Path | Contents |
|---|---|
| `data/processed/bank_panel.csv` | Joined universe, fundamentals, and CoE inputs |
| `data/processed/valuation_assumptions.csv` | Annual forecast and terminal rows by bank |
| `data/processed/forecast_diagnostics.csv` | Audit trail for generated forecast paths |
| `data/processed/valuation_results.csv` | Intrinsic value, fair P/B, actual P/B, and rank |
| `data/processed/valuation_yearly_detail.csv` | Year-by-year book value and residual income |
| `data/processed/relative_value_table.csv` | Mispricing, z-scores, signal, and rank |
| `data/processed/scenario_results.csv` | Base, bull, and bear fair P/B estimates |
| `data/processed/cost_of_equity_by_country.csv` | Average CoE components by country |
| `outputs/tables/sensitivity_terminal_roe_vs_coe.csv` | Per-bank sensitivity grid |
| `outputs/charts/ri_*.html` | Standalone interactive Plotly charts |

Files already committed under `outputs/` and `logs/` are historical research
artifacts. Their dates and assumptions may differ from a newly generated run;
regenerate the pipeline when you need current, internally consistent results.

## Repository layout

```text
config/
  assumptions.yaml              Model, scenario, and sensitivity settings
  universe.yaml                 Configured bank universe
data/
  raw/                          Local Yahoo Finance JSON cache (ignored)
  processed/                    Generated model inputs/results (ignored)
logs/                           Historical project reports
outputs/
  charts/                       Interactive HTML research charts
  tables/                       Generated and historical result tables
src/
  fetch.py                      Data-cache command and Yahoo Finance adapter
  build_inputs.py               Raw/config to auditable processed inputs
  forecast.py                   ROE and payout forecast generation
  cost_of_equity.py             CAPM and country-risk calculations
  residual_income_model.py      Core valuation engine
  relative_value.py             Ranking, z-scores, and signals
  scenarios.py                  Bull/base/bear cases
  sensitivity.py                Two-variable valuation stresses
  plots.py                      Residual-income charts
  run_valuation.py              Main end-to-end valuation command
  screen.py, model.py           Legacy single-stage GGM screen
  backtest.py                   Point-in-time RI backtest framework
  *_backtest.py                 Exploratory legacy backtests
tests/                          Unit tests for core model components
```

The `notebooks/` directory is currently a placeholder; the maintained workflow
uses the scripts above.

## Testing

```bash
python -m pytest tests -q
```

The tests cover cost of equity, forecast construction, residual-income
valuation, and relative-value ranking.

## Backtesting status

`src/backtest.py` contains a lookahead-aware framework: at each rebalance it
uses only fundamentals reported on or before that date, values the available
banks, holds the top-ranked names, and compares them with an equal-weighted
universe. Performance metrics are implemented.

The missing production input is a reliable historical point-in-time
fundamentals feed. Yahoo Finance's current snapshot endpoint cannot recreate
what the market knew on an arbitrary past date, so the framework should not be
presented as a completed historical validation.

## Important limitations

- Yahoo Finance fields can be missing, delayed, restated, or defined
  inconsistently across markets.
- Betas and macro assumptions are editable research estimates, not live feeds.
- Terminal value can be a large part of intrinsic value; use the scenario and
  sensitivity outputs rather than relying on a single point estimate.
- Currency values are modelled per share within each listing. Do not compare
  intrinsic value per share across currencies; compare dimensionless P/B and
  mispricing measures.
- A model signal is not a recommendation. Capital adequacy, asset quality,
  regulation, liquidity, governance, and market-specific risks require separate
  analysis.

## Legacy tools

`src/screen.py` and `src/model.py` retain the original single-stage Gordon
Growth fair-P/B screen for comparison. The residual-income pipeline in
`src/run_valuation.py` is the primary maintained workflow. The exploratory
backtest scripts are research artifacts and are not substitutes for the
point-in-time framework in `src/backtest.py`.
