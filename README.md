# Smart Inventory Management & Stock Demand Prediction System

Python + SQL (SQLite) + Machine Learning. Forecasts per-product demand, then converts the
forecast into **safety stock, reorder points, EOQ and purchase recommendations**.

## Quick start
```bash
pip install -r requirements.txt
python main.py all        # init -> train -> forecast -> plan -> analytics -> report
```
Individual steps: `python main.py init | train | forecast | plan | analytics | report`

## Architecture
```
sales history (SQL) -> feature engineering -> ML model -> 28-day forecast (SQL)
                                                  |
 products / suppliers (SQL) ----------------------+--> inventory policy -> reorder_plan (SQL) -> CSV + charts
```

| Path | Purpose |
|---|---|
| `sql/schema.sql` | Tables, FKs, constraints, indexes, `v_daily_revenue` view |
| `sql/analytics.sql` | 8 named BI queries (CTEs, window functions: ABC analysis, MoM growth, stockout risk...) |
| `src/data_generator.py` | Synthetic data: weekly/yearly seasonality, trend, holidays, promotions, Poisson noise |
| `src/features.py` | Lags (1/7/14/28), rolling mean/std, calendar, promo/discount, product/category |
| `src/model.py` | Baseline vs RandomForest vs HistGradientBoosting, time-based split, recursive forecasting |
| `src/inventory.py` | Safety stock, reorder point, EOQ, status classification, order quantities |
| `src/report.py` | Charts + `reorder_plan.csv` |
| `tests/` | Unit tests for the inventory formulas and data validity |

## Key design decisions
- **No data leakage**: all lag/rolling features are shifted by 1 day; validation is the *last 60 days* (time-based, not random).
- **Baseline first**: a "same day last week" model is the benchmark ML must beat (WAPE 25.9% -> 16.9%).
- **Recursive forecasting**: day *t+1* uses predicted day *t* as a lag, through one shared feature function for training and inference.
- **Uncertainty-aware stock**: safety stock uses each product's own hold-out forecast error.

## Inventory formulas
- Safety stock = `z * sigma_d * sqrt(L)` (z = 1.65, ~95% service level)
- Reorder point = forecast demand over lead time + safety stock
- EOQ = `sqrt(2 * D * S / H)`
- Status: `CRITICAL` (stock <= lead-time demand) / `REORDER` (<= ROP) / `OVERSTOCK` / `OK`
- Order qty = `ROP + EOQ - current_stock`

## Using your own data
Replace the `generate()` call in `cmd_init` with a loader that fills `suppliers`, `products`
and `sales` (columns in `sql/schema.sql`). Everything downstream works unchanged.

## Ideas for extension
Streamlit dashboard, promo/price scenario simulation, quantile models for prediction intervals,
multi-warehouse support, scheduled retraining (cron/Airflow).

## Dashboard (web app)
```bash
pip install streamlit
python main.py all          # once, to build the database + model
streamlit run app.py        # opens http://localhost:8501
```
Pages: Overview, Reorder Plan (filter + CSV download), Demand Forecast (per product), Model Performance, SQL Analytics.
