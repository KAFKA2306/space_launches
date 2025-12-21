#!/usr/bin/env python3
"""
Market Data Repair Script
Backfills missing price data for symbols that have empty columns or stale data.
"""

import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parents[1]))

import pandas as pd

from src.config import Config
from src.market.stocks import StockDataManager

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def repair_market_data():
    logger.info("=== Starting Market Data Repair ===")

    price_file = Config.MARKET_DATA_DIR / "stock_prices.csv"
    if not price_file.exists():
        logger.error(f"Price file not found: {price_file}")
        return

    # Load existing data
    df = pd.read_csv(price_file, index_col=0, parse_dates=True)
    logger.info(f"Loaded {len(df)} rows, {len(df.columns)} columns")

    # Identify candidates
    candidates = set()

    # 1. Empty columns
    empty_cols = [col for col in df.columns if df[col].dropna().empty]
    logger.info(f"Found {len(empty_cols)} empty columns")
    candidates.update(empty_cols)

    # 2. Stale columns (> 5 days old)
    threshold_date = datetime.now() - timedelta(days=5)
    stale_cols = []

    for col in df.columns:
        if col in empty_cols:
            continue
        valid_idx = df[col].dropna().index
        if valid_idx.empty:
            continue

        last_valid = valid_idx.max()
        if hasattr(last_valid, "tzinfo") and last_valid.tzinfo:
            last_valid = last_valid.tz_convert(None)

        if last_valid < threshold_date:
            stale_cols.append(col)

    logger.info(f"Found {len(stale_cols)} stale columns")
    candidates.update(stale_cols)

    if not candidates:
        logger.info("No candidates for repair found.")
        return

    logger.info(f"Attempting to repair {len(candidates)} symbols...")

    # Use StockDataManager for heavy lifting
    manager = StockDataManager()

    # We can use update_stock_prices but force it to look at these specific candidates
    # However, update_stock_prices operates on file paths and sets of codes.
    # It handles incremental updates nicely.

    # Let's trust the manager to do the right thing for these codes
    repaired_df = manager.update_stock_prices(
        prices_file_path=price_file,
        security_codes=candidates,
        batch_size=20,
        retry_count=2,
        use_fallback=True,  # Allow checking charts.csv
    )

    if not repaired_df.empty:
        logger.info("Repair complete.")
    else:
        logger.warning("Repair yielded no data (or purely fallback).")


if __name__ == "__main__":
    repair_market_data()
