"""Data queries for the dashboard (no Streamlit imports, so it is testable)."""
import pandas as pd
from src import database as db


def plan() -> pd.DataFrame:
    return db.read_sql("""
        SELECT p.sku, p.name, p.category, r.status, r.current_stock, r.days_of_cover,
               p.lead_time_days, r.avg_daily_demand, r.safety_stock, r.reorder_point,
               r.eoq, r.recommended_qty, r.est_order_cost, p.product_id
        FROM reorder_plan r JOIN products p USING (product_id)
        ORDER BY CASE r.status WHEN 'CRITICAL' THEN 0 WHEN 'REORDER' THEN 1
                               WHEN 'OK' THEN 2 ELSE 3 END, r.days_of_cover""")


def products() -> pd.DataFrame:
    return db.read_sql("SELECT product_id, sku, name, category FROM products ORDER BY name")


def history_and_forecast(product_id: int, days: int = 90) -> pd.DataFrame:
    hist = db.read_sql(
        "SELECT sale_date AS date, units_sold AS Actual FROM sales WHERE product_id = ? "
        "ORDER BY sale_date DESC LIMIT ?", (product_id, days))
    fc = db.read_sql(
        "SELECT forecast_date AS date, predicted_units AS Forecast FROM demand_forecast "
        "WHERE product_id = ? ORDER BY forecast_date", (product_id,))
    df = pd.concat([hist.sort_values("date"), fc], ignore_index=True)
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date")


def daily_revenue(days: int = 180) -> pd.DataFrame:
    df = db.read_sql("SELECT sale_date, revenue FROM v_daily_revenue ORDER BY sale_date DESC LIMIT ?", (days,))
    df["sale_date"] = pd.to_datetime(df["sale_date"])
    return df.sort_values("sale_date").set_index("sale_date")


def model_runs() -> pd.DataFrame:
    return db.read_sql("""SELECT model_name, ROUND(wape,2) AS wape_pct, ROUND(mae,2) AS mae,
                          ROUND(rmse,2) AS rmse, ROUND(r2,3) AS r2, is_selected
                          FROM model_runs WHERE trained_at = (SELECT MAX(trained_at) FROM model_runs)
                          ORDER BY wape""")


def last_updated() -> str:
    df = db.read_sql("SELECT MAX(generated_at) AS t FROM reorder_plan")
    return str(df["t"].iloc[0]).replace("T", " ")
