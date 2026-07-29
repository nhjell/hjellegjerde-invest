# Australian and Thai Bank Equity Valuation using Residual Income and Price-to-Book Modelling

A Python framework that values 16 Australian (ASX) and Thai (SET) banks through
**book value and residual income** rather than conventional free cash flow, and
converts the result into an **implied fair Price-to-Book (P/B) ratio** that is
compared against the actual market P/B to flag relative mispricing.

The universe is 8 Australian banks (CBA, WBC, NAB, ANZ, MQG, BOQ, BEN, JDO) and
8 Thai banks (BBL, KBANK, SCB, KTB, TTB, BAY, KKP, TISCO), defined in
[`config/universe.yaml`](config/universe.yaml).

---

## Why this model

**Why P/B for banks.** A bank's assets and liabilities are marked close to fair
value and its earnings are generated *on* its book of equity, so book value is a
meaningful anchor and P/B is the natural comparable — far more so than P/E or
EV/EBITDA.

**Why residual income, not DCF.** For a bank, debt (deposits and wholesale
funding) is raw material used to make loans, not just financing. Enterprise
value / free-cash-flow-to-firm frameworks — which treat debt as a financing
claim to be netted off — do not apply cleanly. Residual income values the
**equity directly** off book value plus the *excess* return the bank earns above
its cost of equity.

**Why GGM is only a shortcut.** A single-stage Gordon Growth Model (the original
Stage 1 screen, still available via `src/screen.py`) collapses the entire future
into one ROE, one payout and one growth rate. The residual income model lets ROE,
payout and cost of equity vary year by year and mean-revert to a long-run
terminal state — a more defensible picture of a bank whose profitability is
currently above or below its sustainable level.

**Why Australia and Thailand differ.** Cost of equity is built from CAPM plus an
explicit **country risk premium**. Thailand carries an added premium for FX,
political, liquidity and macro risk, which raises its required return and, for
the same ROE, *lowers* its fair P/B. This is how the model explains — rather than
just observes — why Thai banks can rationally trade below Australian banks.

---

## The model

For each bank, over a 10-year explicit forecast horizon:

```
EPS_t              = ROE_t * BVPS_{t-1}
Dividends_t        = EPS_t * payout_t
Retained_t         = EPS_t - Dividends_t
BVPS_t             = BVPS_{t-1} + Retained_t
Residual_Income_t  = (ROE_t - CostOfEquity_t) * BVPS_{t-1}
PV(RI_t)           = RI_t / prod_{k=1..t}(1 + CostOfEquity_k)
```

Terminal value (a growing perpetuity of residual income beyond the horizon H):

```
Terminal_RI   = (Terminal_ROE - Terminal_CoE) * BVPS_H
Terminal_Val  = Terminal_RI / (Terminal_CoE - Terminal_Growth)
PV(Terminal)  = Terminal_Val / prod_{k=1..H}(1 + CostOfEquity_k)
```

Intrinsic value, fair P/B and mispricing:

```
Intrinsic_Value_Per_Share = BVPS_0 + sum_{t=1..H} PV(RI_t) + PV(Terminal)
Fair_PB                   = Intrinsic_Value_Per_Share / BVPS_0
Mispricing                = Fair_PB / Actual_PB - 1
```

A positive mispricing means the model's fair P/B sits above the market's P/B →
**undervalued**; negative → **overvalued**. A bank earning exactly its cost of
equity is worth book value (fair P/B = 1); value is created only when ROE > CoE.

**ROE forecasting (v2, trajectory-aware — see `src/forecast.py`):** the starting
level is a *normalised* multi-year average (last ~4 fiscal years + current TTM),
so one distorted year can't anchor the forecast. The recent trend tilts year 1
(an improving bank keeps some momentum, capped at ±2 ROE points), then the
abnormal component of ROE decays geometrically toward terminal at an empirical
persistence rate (~0.75/yr, higher for stable franchises, lower for volatile
ones), with every year hard-clipped to a realistic band. The terminal ROE is
disciplined economically: `terminal_ROE = CoE + clip(0.5 × demonstrated spread,
−1%, +2%)` — only half of a bank's demonstrated excess return survives forever,
and never more than 2% over the cost of equity. Per-bank inputs and the exact
normalisation/trend/persistence used are audited in
`data/processed/forecast_diagnostics.csv`.

**Cost of equity (CAPM with country risk):**

```
CoE = risk_free_rate + beta * equity_risk_premium + country_risk_premium
```

All inputs live in [`config/assumptions.yaml`](config/assumptions.yaml) and are
materialised into auditable CSVs under `data/processed/`.

---

## Project layout

```
config/
  universe.yaml            # the 16 banks
  assumptions.yaml         # CAPM, forecast anchors, scenarios, sensitivity grids
data/
  raw/                     # cached yfinance snapshots (JSON, keyed by ticker/date)
  processed/               # generated input + result CSVs
src/
  config.py                # load YAML config
  utils.py                 # paths, logging, CSV I/O, numeric cleaning
  fetch.py                 # yfinance snapshot + annual-history fetch -> data/raw cache
  build_inputs.py          # cache + config  -> data/processed input CSVs
  data_loader.py           # read processed CSVs, merge into modelling panel
  cost_of_equity.py        # CAPM cost of equity + country comparison
  forecast.py              # trajectory-aware ROE/payout path generation (v2)
  residual_income_model.py # the multi-year residual income valuation
  relative_value.py        # mispricing, ranking, z-scores
  scenarios.py             # base / bull / bear scenario analysis
  sensitivity.py           # 2-way sensitivity grids (terminal ROE vs CoE, ...)
  plots.py                 # plotly charts
  backtest.py              # lookahead-safe backtest scaffold + performance metrics
  run_valuation.py         # <-- main pipeline entry point
  screen.py, model.py, *_backtest.py, pb_vs_avg_roe_chart.py   # Stage 1 (legacy GGM)
outputs/
  charts/                  # standalone interactive HTML charts
  tables/                  # sensitivity tables
tests/                     # pytest unit tests
```

---

## Usage

Install dependencies (a virtualenv at `.venv` is assumed):

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run the full residual income pipeline:

```bash
python src/build_inputs.py     # generate data/processed input CSVs from cache + config
python src/run_valuation.py    # value all banks, run scenarios/sensitivity, write charts
```

`run_valuation.py` will call `build_inputs.py` automatically if the processed
inputs are missing, so the second command alone is enough on a fresh checkout
that already has the raw cache.

**Outputs** (written by `run_valuation.py`):

| File | Contents |
|------|----------|
| `data/processed/valuation_results.csv` | Fair P/B, actual P/B, mispricing, rank per bank |
| `data/processed/valuation_yearly_detail.csv` | Year-by-year BVPS/EPS/DPS/RI/PV per bank |
| `data/processed/relative_value_table.csv` | Mispricing + global/country z-scores + signal |
| `data/processed/scenario_results.csv` | Fair P/B under base / bull / bear |
| `data/processed/cost_of_equity_by_country.csv` | Average CoE and components by country |
| `outputs/tables/sensitivity_terminal_roe_vs_coe.csv` | Fair P/B sensitivity grid per bank |
| `outputs/charts/ri_*.html` | Interactive charts (open in any browser) |

Refresh live data (overwrites today's raw snapshots, then rebuild):

```bash
python src/fetch.py 2>/dev/null || true   # (fetch is invoked via screen.py in Stage 1)
python src/build_inputs.py
```

Notebooks in `notebooks/` can import the modules by adding `src/` to the path:

```python
import sys; sys.path.insert(0, "src")
import data_loader, residual_income_model
```

Run the tests:

```bash
python -m pytest tests/ -q
```

---

## Assumptions and data still required

- **Betas are illustrative placeholders** in `config/assumptions.yaml` — replace
  `beta_overrides` with regression betas estimated against a local market index.
- **Macro inputs** (risk-free rates, equity risk premia, country risk premium)
  are static config values; wire them to live market data for production use.
- **Forecasts are mechanical** — normalised multi-year starting levels, a capped
  trend tilt, then persistence-based decay toward a disciplined terminal (see
  `src/forecast.py`). The generated `data/processed/valuation_assumptions.csv`
  is still meant to be hand-edited per bank where you have an analyst view, and
  `forecast_diagnostics.csv` shows exactly what the generator chose and why.
- **Point-in-time history**: `yfinance` only exposes ~4 years of annual
  financials, which caps how far back the backtest can reach.

## Next steps for backtesting

`src/backtest.py` contains a lookahead-safe scaffold. The strategy: at each
quarterly rebalance, value banks using only data available on that date, rank by
mispricing, hold the top-N most undervalued equal-weighted, and benchmark against
the equal-weighted universe. Performance metrics (CAGR, volatility, Sharpe, max
drawdown, hit rate, benchmark excess) are implemented. The remaining work is to
supply a **historical point-in-time fundamentals feed** — `src/fetch.py` is
already keyed by `as_of` date for exactly this purpose — so that
`generate_point_in_time_assumptions` can be driven off real reported history
without lookahead bias.
