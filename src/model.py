"""Train, compare, persist and use demand-forecasting models."""
from datetime import datetime

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from config import FORECAST_HORIZON, MODEL_PATH, RANDOM_SEED, TEST_DAYS
from src import database as db
from src.features import FEATURES, make_features, to_wide


def _metrics(y, pred) -> dict:
    y, pred = np.asarray(y, float), np.asarray(pred, float)
    return dict(
        mae=float(mean_absolute_error(y, pred)),
        rmse=float(np.sqrt(mean_squared_error(y, pred))),
        wape=float(np.abs(y - pred).sum() / max(y.sum(), 1e-9) * 100),  # % weighted abs. pct error
        r2=float(r2_score(y, pred)),
    )


def _candidates() -> dict:
    return {
        "RandomForest": RandomForestRegressor(
            n_estimators=200, min_samples_leaf=3, n_jobs=-1, random_state=RANDOM_SEED),
        "HistGradientBoosting": HistGradientBoostingRegressor(
            loss="poisson", learning_rate=0.05, max_iter=400, max_leaf_nodes=31,
            l2_regularization=1.0, random_state=RANDOM_SEED),
    }


def train() -> dict:
    sales, products = db.read_sales(), db.read_products()
    units, promo, price = to_wide(sales)
    data = make_features(units, promo, price, products).dropna()

    cutoff = units.index.max() - pd.Timedelta(days=TEST_DAYS)
    is_test = data.index.get_level_values("sale_date") > cutoff
    train_df, test_df = data[~is_test], data[is_test]
    X_tr, y_tr, X_te, y_te = train_df[FEATURES], train_df["target"], test_df[FEATURES], test_df["target"]

    results, preds = {}, {}
    # Baseline: "same day last week" - any ML model must beat this to be worth it
    preds["Naive (lag-7)"] = X_te["lag_7"].values
    for name, mdl in _candidates().items():
        mdl.fit(X_tr, y_tr)
        preds[name] = np.clip(mdl.predict(X_te), 0, None)
    for name, p in preds.items():
        results[name] = _metrics(y_te, p)

    best = min((n for n in results if not n.startswith("Naive")), key=lambda n: results[n]["wape"])

    # Per-product forecast error (std of residuals) -> used for safety stock
    resid = (y_te - preds[best]).groupby(level="product_id").std().fillna(0.0)

    # Refit winner on ALL data for production forecasting
    final = _candidates()[best].fit(data[FEATURES], data["target"])
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": final, "name": best, "features": FEATURES,
                 "residual_std": resid.to_dict(), "trained_at": datetime.now().isoformat()}, MODEL_PATH)

    now = datetime.now().isoformat(timespec="seconds")
    runs = pd.DataFrame([{**m, "model_name": n, "is_selected": int(n == best), "trained_at": now}
                         for n, m in results.items()])
    db.write_table(runs, "model_runs")

    return {"results": results, "best": best, "test_frame": test_df.assign(**{f"pred_{k}": v for k, v in preds.items()})}


def load_bundle() -> dict:
    return joblib.load(MODEL_PATH)


def forecast(horizon: int = FORECAST_HORIZON) -> pd.DataFrame:
    """Recursive multi-step forecast: each day's prediction feeds the next day's lags."""
    bundle = load_bundle()
    model, feats = bundle["model"], bundle["features"]
    sales, products = db.read_sales(), db.read_products()
    units, promo, price = (f.tail(60).copy() for f in to_wide(sales))   # 28d lag + buffer
    list_price = products.set_index("product_id")["unit_price"].reindex(units.columns).values
    last = units.index.max()

    out = []
    for h in range(1, horizon + 1):
        d = last + pd.Timedelta(days=h)
        units.loc[d] = np.nan
        promo.loc[d] = 0            # assume no promotion unless planned
        price.loc[d] = list_price
        row = make_features(units, promo, price, products).xs(d, level="sale_date")
        pred = np.clip(model.predict(row[feats]), 0, None)
        pred = pd.Series(pred, index=row.index).reindex(units.columns)
        units.loc[d] = pred.values
        out.append(pd.DataFrame({"forecast_date": d.strftime("%Y-%m-%d"),
                                 "product_id": pred.index, "predicted_units": pred.values}))

    fc = pd.concat(out, ignore_index=True)
    fc["model_name"] = bundle["name"]
    fc["generated_at"] = datetime.now().isoformat(timespec="seconds")
    db.write_table(fc, "demand_forecast", replace_all=True)
    return fc
