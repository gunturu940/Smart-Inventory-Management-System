"""Synthetic retail data: suppliers, products and 2 years of daily sales.

Demand has weekly + yearly seasonality, a per-product trend, holiday spikes,
promotion uplift and Poisson noise - realistic enough for ML to learn from.
"""
import numpy as np
import pandas as pd

from config import HISTORY_DAYS, N_PRODUCTS, RANDOM_SEED

CATEGORY_SPECS = {
    "Grocery":     dict(base=(30, 80), price=(2, 12),    amp=0.05, peak_month=12, weekend=0.18,
                        names=["Basmati Rice 5kg", "Olive Oil 1L", "Whole Wheat Flour", "Green Tea Box", "Peanut Butter"]),
    "Electronics": dict(base=(4, 15),  price=(40, 600),  amp=0.25, peak_month=11, weekend=0.10,
                        names=["Wireless Earbuds", "Smart Watch", "Power Bank 20k", "Bluetooth Speaker", "USB-C Hub"]),
    "Apparel":     dict(base=(8, 25),  price=(15, 120),  amp=0.30, peak_month=12, weekend=0.20,
                        names=["Cotton T-Shirt", "Denim Jeans", "Running Shoes", "Winter Jacket", "Sports Socks"]),
    "Home":        dict(base=(6, 20),  price=(10, 150),  amp=0.10, peak_month=5,  weekend=0.12,
                        names=["LED Bulb Pack", "Cookware Set", "Bed Sheet Set", "Desk Lamp", "Storage Bins"]),
    "Toys":        dict(base=(5, 20),  price=(8, 60),    amp=0.50, peak_month=12, weekend=0.30,
                        names=["Building Blocks", "RC Car", "Puzzle 1000pc", "Board Game"]),
}

SUPPLIERS = [
    (1, "FastTrack Distributors", 3),
    (2, "Metro Wholesale", 5),
    (3, "Prime Source Ltd", 7),
    (4, "Global Imports Co", 10),
    (5, "Overseas Direct", 14),
]


def _holiday_boost(dates: pd.DatetimeIndex, category: str) -> np.ndarray:
    m, d = dates.month.values, dates.day.values
    boost = np.ones(len(dates))
    if category != "Home":
        boost[(m == 11) & (d >= 22)] = 1.5          # Black-Friday window
        boost[(m == 12) & (d >= 10) & (d <= 24)] = 1.3  # Christmas run-up
    return boost


def generate(seed: int = RANDOM_SEED, end_date=None):
    """Return (suppliers_df, products_df, sales_df)."""
    rng = np.random.default_rng(seed)
    end = pd.Timestamp(end_date) if end_date is not None else pd.Timestamp.today().normalize() - pd.Timedelta(days=1)
    dates = pd.date_range(end=end, periods=HISTORY_DAYS, freq="D")

    suppliers = pd.DataFrame(SUPPLIERS, columns=["supplier_id", "name", "lead_time_days"])

    # ---- products ---------------------------------------------------------
    rows, pid = [], 1
    for cat, spec in CATEGORY_SPECS.items():
        for name in spec["names"]:
            if pid > N_PRODUCTS:
                break
            price = round(float(rng.uniform(*spec["price"])), 2)
            sup = suppliers.sample(1, random_state=int(rng.integers(1e6))).iloc[0]
            rows.append(dict(
                product_id=pid, sku=f"SKU-{pid:04d}", name=name, category=cat,
                unit_cost=round(price * rng.uniform(0.50, 0.80), 2), unit_price=price,
                supplier_id=int(sup.supplier_id), lead_time_days=int(sup.lead_time_days),
                order_cost=round(float(rng.uniform(40, 120)), 2),
                holding_cost_rate=round(float(rng.uniform(0.15, 0.30)), 3),
                tmp_base=float(rng.uniform(*spec["base"])), tmp_cat=cat,
                tmp_trend=float(rng.uniform(-0.10, 0.25)),
            ))
            pid += 1
    prod = pd.DataFrame(rows)

    # ---- sales ------------------------------------------------------------
    t = np.arange(len(dates))
    dow, doy = dates.dayofweek.values, dates.dayofyear.values
    sales_rows, recent_mean = [], {}
    for p in prod.itertuples():
        spec = CATEGORY_SPECS[p.tmp_cat]
        peak_doy = pd.Timestamp(2024, spec["peak_month"], 15).dayofyear
        season = 1 + spec["amp"] * np.cos(2 * np.pi * (doy - peak_doy) / 365.25)
        weekend = np.where(dow >= 5, 1 + spec["weekend"], 1.0)
        trend = 1 + p.tmp_trend * t / 365.0
        holiday = _holiday_boost(dates, p.tmp_cat)

        promo, disc, left, cur = np.zeros(len(t), int), np.zeros(len(t)), 0, 0.0
        for i in range(len(t)):
            if left == 0 and rng.random() < 0.015:
                left, cur = int(rng.integers(3, 8)), float(rng.choice([0.10, 0.15, 0.20, 0.30]))
            if left > 0:
                promo[i], disc[i] = 1, cur
                left -= 1

        mean = (p.tmp_base * season * weekend * trend * holiday * (1 + 2.5 * disc)
                * rng.lognormal(0, 0.10, len(t)))
        units = rng.poisson(mean)
        recent_mean[p.product_id] = float(np.mean(units[-30:]))
        sales_rows.append(pd.DataFrame({
            "sale_date": dates.strftime("%Y-%m-%d"), "product_id": p.product_id,
            "units_sold": units, "unit_price": np.round(p.unit_price * (1 - disc), 2), "promo": promo,
        }))
    sales = pd.concat(sales_rows, ignore_index=True)

    # ---- current stock: deliberately mixed (some critical, some overstocked)
    covers = rng.choice([1.5, 3, 5, 8, 12, 20, 35, 60, 90], size=len(prod),
                        p=[0.04, 0.08, 0.10, 0.12, 0.18, 0.20, 0.14, 0.08, 0.06])
    prod["current_stock"] = [int(recent_mean[i] * c) for i, c in zip(prod.product_id, covers)]
    products = prod.drop(columns=[c for c in prod.columns if c.startswith("tmp_")])
    return suppliers, products, sales
