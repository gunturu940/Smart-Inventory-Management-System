"""Central configuration for the Smart Inventory Management system."""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "inventory.db"
MODEL_PATH = BASE_DIR / "models" / "demand_model.joblib"
OUTPUT_DIR = BASE_DIR / "outputs"
SQL_DIR = BASE_DIR / "sql"

# Synthetic data
N_PRODUCTS = 24
HISTORY_DAYS = 730
RANDOM_SEED = 42

# Modelling
FORECAST_HORIZON = 28      # days ahead to forecast (must be >= max lead time)
TEST_DAYS = 60             # hold-out window for time-based validation

# Inventory policy
SERVICE_LEVEL_Z = 1.65     # z-score for ~95% cycle service level
OVERSTOCK_EOQ_MULTIPLE = 2 # stock > ROP + k*EOQ  => overstock
