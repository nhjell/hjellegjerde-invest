"""End-to-end residual income valuation pipeline (main entry point).

    python src/run_valuation.py

Steps:
  1. Ensure processed inputs exist (build them from the cache + config if not).
  2. Value every bank over the configured residual-income forecast horizon.
  3. Build the relative value table (mispricing, z-scores, ranks).
  4. Compare cost of equity across countries.
  5. Run base / bull / bear scenario analysis.
  6. Run the headline terminal-ROE vs terminal-CoE sensitivity for each bank.
  7. Write all results to data/processed/ and outputs/, and render charts.
"""

from __future__ import annotations

import build_inputs
import data_loader
import plots
from config import load_assumptions
from cost_of_equity import compare_country_cost_of_equity
from relative_value import build_relative_value_table
from residual_income_model import value_all_banks
from scenarios import run_scenario_analysis
from sensitivity import terminal_roe_vs_coe
from utils import PROCESSED_DIR, TABLES_DIR, ensure_dirs, get_logger, save_csv

logger = get_logger(__name__)


def main() -> None:
    ensure_dirs()
    assumptions_cfg = load_assumptions()
    horizon = assumptions_cfg["forecast"]["horizon_years"]

    if not data_loader.inputs_exist():
        logger.info("Processed inputs missing - building them from cache + config...")
        build_inputs.main()

    panel = data_loader.build_model_panel()
    val_assumptions = data_loader.load_valuation_assumptions()
    coe_inputs = data_loader.load_cost_of_equity_inputs()

    # --- 2. Core valuation ------------------------------------------------
    summary, yearly = value_all_banks(panel, val_assumptions, horizon=horizon, return_yearly=True)
    save_csv(summary, PROCESSED_DIR / "valuation_results.csv")
    save_csv(yearly, PROCESSED_DIR / "valuation_yearly_detail.csv")
    logger.info("Valued %d banks", len(summary))

    # --- 3. Relative value ------------------------------------------------
    rv = build_relative_value_table(summary)
    save_csv(rv, PROCESSED_DIR / "relative_value_table.csv")

    # --- 4. Cost of equity comparison ------------------------------------
    coe_summary = compare_country_cost_of_equity(coe_inputs)
    save_csv(coe_summary, PROCESSED_DIR / "cost_of_equity_by_country.csv")

    # --- 5. Scenario analysis --------------------------------------------
    scen = run_scenario_analysis(panel, val_assumptions, assumptions_cfg["scenarios"], horizon=horizon)
    save_csv(scen, PROCESSED_DIR / "scenario_results.csv")

    # --- 6. Sensitivity (headline grid per bank) -------------------------
    sens_cfg = assumptions_cfg["sensitivity"]
    bvps_by_ticker = dict(zip(panel["ticker"], panel["bvps"]))
    pb_by_ticker = dict(zip(panel["ticker"], panel["actual_pb"]))
    sens_frames = []
    for ticker in summary["ticker"]:
        try:
            grid = terminal_roe_vs_coe(
                ticker, val_assumptions, bvps_by_ticker[ticker],
                roe_shifts=sens_cfg["terminal_roe_shifts"],
                coe_shifts=sens_cfg["terminal_coe_shifts"],
                actual_pb=pb_by_ticker.get(ticker), horizon=horizon,
            )
        except Exception as e:  # keep going; a single bad bank shouldn't stop the run
            logger.warning("Sensitivity failed for %s: %s", ticker, e)
            continue
        long = grid.reset_index().melt(id_vars=grid.index.name, var_name="terminal_roe_shift", value_name="fair_pb")
        long.insert(0, "ticker", ticker)
        sens_frames.append(long)
    if sens_frames:
        import pandas as pd
        sens_all = pd.concat(sens_frames, ignore_index=True)
        save_csv(sens_all, TABLES_DIR / "sensitivity_terminal_roe_vs_coe.csv")

    # --- 7. Charts --------------------------------------------------------
    plots.plot_actual_vs_fair_pb(rv)
    plots.plot_mispricing_ranking(rv)
    plots.plot_country_cost_of_equity(coe_summary)
    plots.plot_roe_vs_pb(panel)
    plots.plot_scenario_ranges(scen)
    plots.plot_forecast_paths(val_assumptions)
    # Heatmap for the largest bank as an illustrative example.
    top_ticker = summary.iloc[0]["ticker"]
    try:
        grid = terminal_roe_vs_coe(
            top_ticker, val_assumptions, bvps_by_ticker[top_ticker],
            roe_shifts=sens_cfg["terminal_roe_shifts"],
            coe_shifts=sens_cfg["terminal_coe_shifts"], horizon=horizon,
        )
        plots.plot_sensitivity_heatmap(
            grid, title=f"Fair P/B sensitivity - {top_ticker} (terminal ROE vs CoE shifts)",
            filename="ri_sensitivity_heatmap.html",
        )
    except Exception as e:
        logger.warning("Heatmap failed for %s: %s", top_ticker, e)

    # --- Console summary --------------------------------------------------
    import pandas as pd
    pd.set_option("display.float_format", "{:.3f}".format)
    cols = ["rank", "ticker", "country", "fair_pb", "actual_pb", "mispricing", "signal"]
    print("\n=== Residual income relative value (most undervalued first) ===")
    print(rv[cols].to_string(index=False))
    print("\n=== Average cost of equity by country ===")
    print(coe_summary.to_string(index=False))
    print(f"\nResults written to {PROCESSED_DIR} and charts to outputs/charts/")


if __name__ == "__main__":
    main()
