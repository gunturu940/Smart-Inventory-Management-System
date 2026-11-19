"""Smart Inventory Management & Demand Prediction - CLI.

    python main.py all          # full pipeline
    python main.py init|train|forecast|plan|analytics|report
"""
import argparse

import pandas as pd

from config import OUTPUT_DIR
from src import data_generator, database as db, inventory, model, report

pd.set_option("display.width", 160, "display.max_columns", 20)
_state = {}


def cmd_init():
    print("[1/6] Generating data & loading SQLite ...")
    db.init_db()
    db.load_dataset(*data_generator.generate())
    n = db.read_sql("SELECT COUNT(*) AS n FROM sales").n[0]
    print(f"      {n:,} sales rows loaded")


def cmd_train():
    print("[2/6] Training demand models ...")
    out = model.train(); _state.update(out)
    print(pd.DataFrame(out["results"]).T.round(2).to_string())
    print(f"      Selected model: {out['best']}")


def cmd_forecast():
    print("[3/6] Forecasting next 28 days ...")
    fc = model.forecast()
    print(f"      {len(fc):,} product-day forecasts saved")


def cmd_plan():
    print("[4/6] Building replenishment plan ...")
    plan = inventory.build_plan(); _state["plan"] = plan
    print(plan["status"].value_counts().to_string())
    urgent = plan[plan.status.isin(["CRITICAL", "REORDER"])].sort_values("days_of_cover")
    print("\nOrders to place now:")
    print(urgent[["sku", "name", "status", "current_stock", "days_of_cover", "lead_time_days",
                  "recommended_qty", "est_order_cost"]].to_string(index=False))


def cmd_analytics():
    print("[5/6] SQL analytics")
    for name, df in db.run_named_queries().items():
        print(f"\n--- {name} ---"); print(df.to_string(index=False))


def cmd_report():
    print("[6/6] Writing charts to outputs/ ...")
    OUTPUT_DIR.mkdir(exist_ok=True)
    if "results" in _state:
        report.model_comparison(_state["results"])
        report.actual_vs_predicted(_state["test_frame"], _state["best"])
    report.forecast_chart()
    plan = _state.get("plan")
    if plan is None:
        plan = inventory.build_plan()
    report.inventory_dashboard(plan); report.export_plan(plan)
    print("      done")


COMMANDS = dict(init=cmd_init, train=cmd_train, forecast=cmd_forecast, plan=cmd_plan,
                analytics=cmd_analytics, report=cmd_report)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("command", choices=[*COMMANDS, "all"])
    cmd = ap.parse_args().command
    for fn in (COMMANDS.values() if cmd == "all" else [COMMANDS[cmd]]):
        fn()
