import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import numpy as np
from src.inventory import classify, eoq, safety_stock
from src.data_generator import generate


def test_eoq_formula():
    assert abs(eoq(1000, 50, 2) - np.sqrt(2 * 1000 * 50 / 2)) < 1e-9
    assert eoq(0, 50, 2) == 0


def test_safety_stock_grows_with_lead_time():
    assert safety_stock(5, 16) > safety_stock(5, 4)
    assert abs(safety_stock(5, 4, z=1.65) - 1.65 * 5 * 2) < 1e-9


def test_classification():
    assert classify(stock=10, lead_demand=20, rop=30, eoq_qty=50) == "CRITICAL"
    assert classify(stock=25, lead_demand=20, rop=30, eoq_qty=50) == "REORDER"
    assert classify(stock=60, lead_demand=20, rop=30, eoq_qty=50) == "OK"
    assert classify(stock=500, lead_demand=20, rop=30, eoq_qty=50) == "OVERSTOCK"


def test_generated_data_is_valid():
    sup, prod, sales = generate(seed=1, end_date="2025-12-31")
    assert len(prod) == 24 and (sales.units_sold >= 0).all()
    assert sales.groupby(["sale_date", "product_id"]).size().max() == 1
    assert set(prod.supplier_id) <= set(sup.supplier_id)
