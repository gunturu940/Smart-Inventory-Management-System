PRAGMA foreign_keys = ON;

DROP VIEW  IF EXISTS v_daily_revenue;
DROP TABLE IF EXISTS reorder_plan;
DROP TABLE IF EXISTS demand_forecast;
DROP TABLE IF EXISTS model_runs;
DROP TABLE IF EXISTS sales;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS suppliers;

CREATE TABLE suppliers (
    supplier_id     INTEGER PRIMARY KEY,
    name            TEXT NOT NULL,
    lead_time_days  INTEGER NOT NULL CHECK (lead_time_days > 0)
);

CREATE TABLE products (
    product_id          INTEGER PRIMARY KEY,
    sku                 TEXT NOT NULL UNIQUE,
    name                TEXT NOT NULL,
    category            TEXT NOT NULL,
    unit_cost           REAL NOT NULL CHECK (unit_cost > 0),
    unit_price          REAL NOT NULL CHECK (unit_price > 0),
    supplier_id         INTEGER NOT NULL REFERENCES suppliers(supplier_id),
    lead_time_days      INTEGER NOT NULL CHECK (lead_time_days > 0),
    current_stock       INTEGER NOT NULL CHECK (current_stock >= 0),
    order_cost          REAL NOT NULL,          -- fixed cost per purchase order
    holding_cost_rate   REAL NOT NULL           -- annual holding cost as fraction of unit cost
);

CREATE TABLE sales (
    sale_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_date   TEXT    NOT NULL,               -- ISO date YYYY-MM-DD
    product_id  INTEGER NOT NULL REFERENCES products(product_id),
    units_sold  INTEGER NOT NULL CHECK (units_sold >= 0),
    unit_price  REAL    NOT NULL,
    promo       INTEGER NOT NULL DEFAULT 0,
    UNIQUE (sale_date, product_id)
);
CREATE INDEX idx_sales_product_date ON sales (product_id, sale_date);
CREATE INDEX idx_sales_date ON sales (sale_date);

CREATE TABLE model_runs (
    run_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    model_name  TEXT NOT NULL,
    mae         REAL, rmse REAL, wape REAL, r2 REAL,
    is_selected INTEGER NOT NULL DEFAULT 0,
    trained_at  TEXT NOT NULL
);

CREATE TABLE demand_forecast (
    forecast_date    TEXT NOT NULL,
    product_id       INTEGER NOT NULL REFERENCES products(product_id),
    predicted_units  REAL NOT NULL,
    model_name       TEXT NOT NULL,
    generated_at     TEXT NOT NULL,
    PRIMARY KEY (forecast_date, product_id)
);

CREATE TABLE reorder_plan (
    product_id        INTEGER PRIMARY KEY REFERENCES products(product_id),
    current_stock     INTEGER,
    avg_daily_demand  REAL,
    lead_time_demand  REAL,
    safety_stock      REAL,
    reorder_point     REAL,
    eoq               REAL,
    days_of_cover     REAL,
    status            TEXT,
    recommended_qty   INTEGER,
    est_order_cost    REAL,
    generated_at      TEXT
);

CREATE VIEW v_daily_revenue AS
SELECT s.sale_date,
       SUM(s.units_sold * s.unit_price)                    AS revenue,
       SUM(s.units_sold * (s.unit_price - p.unit_cost))    AS gross_profit,
       SUM(s.units_sold)                                   AS units
FROM sales s JOIN products p USING (product_id)
GROUP BY s.sale_date;
