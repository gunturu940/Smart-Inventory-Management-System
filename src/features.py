"""Feature engineering shared by training AND recursive forecasting.

Everything is computed from wide (date x product) frames so the exact same
code path builds the training matrix and the features for future days.
"""
import numpy as np
import pandas as pd

CATEGORY_CODES = {"Grocery": 0, "Electronics": 1, "Apparel": 2, "Home": 3, "Toys": 4}

FEATURES = [
    "lag_1", "lag_7", "lag_14", "lag_28",
    "roll_mean_7", "roll_mean_28", "roll_std_7",
    "promo", "discount",
    "dow", "month", "day", "is_weekend", "doy_sin", "doy_cos", "holiday_season",
    "product_id", "category_code",
]


def to_wide(sales: pd.DataFrame):
    piv = lambda col: sales.pivot(index="sale_date", columns="product_id", values=col).sort_index()
    return piv("units_sold"), piv("promo"), piv("unit_price")


def make_features(units, promo, price, products) -> pd.DataFrame:
    """Return long frame indexed by (sale_date, product_id) with FEATURES (+ target)."""
    shifted = units.shift(1)  # never let a row see its own day's sales
    list_price = products.set_index("product_id")["unit_price"].reindex(units.columns)

    parts = {
        "lag_1": units.shift(1), "lag_7": units.shift(7),
        "lag_14": units.shift(14), "lag_28": units.shift(28),
        "roll_mean_7": shifted.rolling(7).mean(),
        "roll_mean_28": shifted.rolling(28).mean(),
        "roll_std_7": shifted.rolling(7).std(),
        "promo": promo,
        "discount": 1 - price.div(list_price, axis=1),
        "target": units,
    }
    long = pd.concat({k: v.stack() for k, v in parts.items()}, axis=1)
    long.index.names = ["sale_date", "product_id"]

    dates = long.index.get_level_values("sale_date")
    pids = long.index.get_level_values("product_id")
    long["dow"] = dates.dayofweek
    long["month"] = dates.month
    long["day"] = dates.day
    long["is_weekend"] = (dates.dayofweek >= 5).astype(int)
    long["doy_sin"] = np.sin(2 * np.pi * dates.dayofyear / 365.25)
    long["doy_cos"] = np.cos(2 * np.pi * dates.dayofyear / 365.25)
    long["holiday_season"] = (((dates.month == 11) & (dates.day >= 22)) |
                              ((dates.month == 12) & (dates.day >= 10) & (dates.day <= 24))).astype(int)
    long["product_id"] = pids
    cat = products.set_index("product_id")["category"].map(CATEGORY_CODES)
    long["category_code"] = pids.map(cat).values
    return long
