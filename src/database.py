"""SQLite access layer."""
import sqlite3
from contextlib import contextmanager

import pandas as pd

from config import DB_PATH, SQL_DIR


@contextmanager
def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """(Re)create all tables, indexes and views from sql/schema.sql."""
    with connect() as conn:
        conn.executescript((SQL_DIR / "schema.sql").read_text())


def load_dataset(suppliers, products, sales):
    with connect() as conn:
        suppliers.to_sql("suppliers", conn, if_exists="append", index=False)
        products.to_sql("products", conn, if_exists="append", index=False)
        sales.to_sql("sales", conn, if_exists="append", index=False)


def read_sales() -> pd.DataFrame:
    with connect() as conn:
        return pd.read_sql(
            "SELECT sale_date, product_id, units_sold, unit_price, promo "
            "FROM sales ORDER BY sale_date, product_id", conn, parse_dates=["sale_date"])


def read_products() -> pd.DataFrame:
    with connect() as conn:
        return pd.read_sql("SELECT * FROM products ORDER BY product_id", conn)


def read_sql(query: str, params=()) -> pd.DataFrame:
    with connect() as conn:
        return pd.read_sql(query, conn, params=params)


def write_table(df: pd.DataFrame, table: str, replace_all: bool = False):
    with connect() as conn:
        if replace_all:
            conn.execute(f"DELETE FROM {table}")
        df.to_sql(table, conn, if_exists="append", index=False)


def run_named_queries() -> dict:
    """Parse sql/analytics.sql ('-- name: x' blocks) and run each query."""
    text = (SQL_DIR / "analytics.sql").read_text()
    results = {}
    with connect() as conn:
        for block in text.split("-- name:")[1:]:
            name, _, query = block.partition("\n")
            results[name.strip()] = pd.read_sql(query.strip().rstrip(";"), conn)
    return results
