"""Charts + CSV exports."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from config import OUTPUT_DIR
from src import database as db

COLORS = {"CRITICAL": "#d62728", "REORDER": "#ff9f1c", "OK": "#2ca02c", "OVERSTOCK": "#1f77b4"}


def model_comparison(results: dict):
    df = pd.DataFrame(results).T[["wape", "mae", "rmse"]]
    fig, ax = plt.subplots(1, 3, figsize=(12, 3.8))
    for a, col, t in zip(ax, df.columns, ["WAPE % (lower=better)", "MAE", "RMSE"]):
        a.bar(df.index, df[col], color=["#999", "#4c78a8", "#f58518"][: len(df)])
        a.set_title(t); a.tick_params(axis="x", rotation=20)
    fig.suptitle("Model comparison on hold-out period", fontweight="bold")
    fig.tight_layout(); fig.savefig(OUTPUT_DIR / "model_comparison.png", dpi=130); plt.close(fig)


def actual_vs_predicted(test_frame: pd.DataFrame, best: str, n=3):
    top = test_frame.groupby(level="product_id")["target"].sum().nlargest(n).index
    names = db.read_products().set_index("product_id")["name"]
    fig, axes = plt.subplots(n, 1, figsize=(10, 2.8 * n), sharex=True)
    for ax, pid in zip(axes, top):
        d = test_frame.xs(pid, level="product_id")
        ax.plot(d.index, d["target"], label="Actual", color="black", lw=1.4)
        ax.plot(d.index, d[f"pred_{best}"], label=f"{best}", color="#f58518", lw=1.4)
        ax.set_title(names[pid], loc="left", fontsize=10); ax.legend(loc="upper right", fontsize=8)
    fig.suptitle("Hold-out: actual vs predicted daily demand", fontweight="bold")
    fig.tight_layout(); fig.savefig(OUTPUT_DIR / "actual_vs_predicted.png", dpi=130); plt.close(fig)


def forecast_chart(n=4):
    sales = db.read_sales(); fc = db.read_sql("SELECT * FROM demand_forecast", ) 
    fc["forecast_date"] = pd.to_datetime(fc["forecast_date"])
    products = db.read_products().set_index("product_id")
    top = sales.groupby("product_id")["units_sold"].sum().nlargest(n).index
    fig, axes = plt.subplots(2, 2, figsize=(12, 6))
    for ax, pid in zip(axes.ravel(), top):
        h = sales[(sales.product_id == pid)].tail(60)
        f = fc[fc.product_id == pid]
        ax.plot(h.sale_date, h.units_sold, color="#555", label="History")
        ax.plot(f.forecast_date, f.predicted_units, color="#d62728", label="Forecast")
        ax.set_title(products.loc[pid, "name"], fontsize=10); ax.tick_params(axis="x", rotation=30)
    axes[0, 0].legend()
    fig.suptitle("28-day demand forecast", fontweight="bold")
    fig.tight_layout(); fig.savefig(OUTPUT_DIR / "forecast.png", dpi=130); plt.close(fig)


def inventory_dashboard(plan: pd.DataFrame):
    plan = plan.sort_values("days_of_cover")
    fig, ax = plt.subplots(1, 2, figsize=(13, 6), gridspec_kw={"width_ratios": [2.2, 1]})
    ax[0].barh(plan["name"], plan["days_of_cover"].clip(upper=120),
               color=[COLORS[s] for s in plan["status"]])
    ax[0].scatter(plan["lead_time_days"], plan["name"], color="black", marker="|", s=120, label="Supplier lead time")
    ax[0].set_xlabel("Days of cover (capped at 120)"); ax[0].legend(); ax[0].set_title("Stock cover vs lead time")
    counts = plan["status"].value_counts()
    ax[1].bar(counts.index, counts.values, color=[COLORS[s] for s in counts.index])
    ax[1].set_title("Products by status")
    fig.tight_layout(); fig.savefig(OUTPUT_DIR / "inventory_dashboard.png", dpi=130); plt.close(fig)


def export_plan(plan: pd.DataFrame):
    cols = ["sku", "name", "category", "status", "current_stock", "days_of_cover", "lead_time_days",
            "safety_stock", "reorder_point", "eoq", "recommended_qty", "est_order_cost"]
    plan[cols].sort_values(["status", "days_of_cover"]).to_csv(OUTPUT_DIR / "reorder_plan.csv", index=False)
