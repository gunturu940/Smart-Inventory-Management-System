"""Inventory policy: safety stock, reorder point, EOQ and replenishment plan."""
from datetime import datetime

import numpy as np
import pandas as pd

from config import OVERSTOCK_EOQ_MULTIPLE, SERVICE_LEVEL_Z
from src import database as db
from src.model import load_bundle


def safety_stock(sigma_daily: float, lead_time: int, z: float = SERVICE_LEVEL_Z) -> float:
    """z * sigma_d * sqrt(L)"""
    return z * sigma_daily * np.sqrt(lead_time)


def eoq(annual_demand: float, order_cost: float, unit_holding_cost: float) -> float:
    """Economic Order Quantity = sqrt(2DS / H)"""
    if annual_demand <= 0 or unit_holding_cost <= 0:
        return 0.0
    return float(np.sqrt(2 * annual_demand * order_cost / unit_holding_cost))


def classify(stock, lead_demand, rop, eoq_qty) -> str:
    if stock <= lead_demand:
        return "CRITICAL"      # will stock out before a new order can arrive
    if stock <= rop:
        return "REORDER"       # below reorder point, order now
    if stock > rop + OVERSTOCK_EOQ_MULTIPLE * eoq_qty:
        return "OVERSTOCK"
    return "OK"


def build_plan() -> pd.DataFrame:
    products = db.read_products()
    fc = db.read_sql("SELECT forecast_date, product_id, predicted_units FROM demand_forecast ORDER BY forecast_date")
    sigma = load_bundle()["residual_std"]
    fc["day_idx"] = fc.groupby("product_id").cumcount() + 1   # 1 = tomorrow

    rows = []
    for p in products.itertuples():
        f = fc[fc.product_id == p.product_id]
        avg_daily = f.predicted_units.mean()
        lead_demand = f[f.day_idx <= p.lead_time_days].predicted_units.sum()
        ss = safety_stock(sigma.get(p.product_id, avg_daily ** 0.5), p.lead_time_days)
        rop = lead_demand + ss
        q = eoq(avg_daily * 365, p.order_cost, p.unit_cost * p.holding_cost_rate)
        status = classify(p.current_stock, lead_demand, rop, q)
        qty = int(np.ceil(max(rop + q - p.current_stock, 0))) if status in ("CRITICAL", "REORDER") else 0
        rows.append(dict(
            product_id=p.product_id, current_stock=p.current_stock,
            avg_daily_demand=round(avg_daily, 2), lead_time_demand=round(lead_demand, 1),
            safety_stock=round(ss, 1), reorder_point=round(rop, 1), eoq=round(q, 1),
            days_of_cover=round(p.current_stock / avg_daily, 1) if avg_daily > 0 else 999.0,
            status=status, recommended_qty=qty, est_order_cost=round(qty * p.unit_cost + (p.order_cost if qty else 0), 2),
            generated_at=datetime.now().isoformat(timespec="seconds")))
    plan = pd.DataFrame(rows)
    db.write_table(plan, "reorder_plan", replace_all=True)
    return plan.merge(products[["product_id", "sku", "name", "category", "lead_time_days"]], on="product_id")
