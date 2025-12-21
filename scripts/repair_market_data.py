#!/usr/bin/env python3
"""
Market Data Repair Script
Backfills missing price data for symbols that have empty columns or stale data.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parents[1]))

import pandas as pd
import yfinance as yf
import logging
from datetime import datetime, timedelta
from src.config import Config
from src.market.stocks import StockDataManager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def repair_market_data():
    logger.info("=== Starting Market Data Repair ===")
    
    # Initialize
    price_file = Config.MARKET_DATA_DIR / "stock_prices.csv"
    if not price_file.exists():
        logger.error(f"Price file not found: {price_file}")
        return

    # Load existing data
    df = pd.read_csv(price_file, index_col=0, parse_dates=True)
    logger.info(f"Loaded {len(df)} rows, {len(df.columns)} columns")
    
    # Identify candidates for repair
    candidates = []
    
    # 1. Empty columns (all NaN)
    empty_cols = [col for col in df.columns if df[col].dropna().empty]
    logger.info(f"Found {len(empty_cols)} empty columns: {empty_cols}")
    candidates.extend(empty_cols)
    
    # 2. Stale columns (last valid date > 5 days ago)
    # Use timezone-naive comparisons
    if df.index.tz is not None:
        last_idx = df.index.max().tz_convert(None)
    else:
        last_idx = df.index.max()
        
    threshold_date = datetime.now() - timedelta(days=5)
    
    stale_cols = []
    for col in df.columns:
        if col in empty_cols: continue
        
        valid_idx = df[col].dropna().index
        if valid_idx.empty: continue
            
        last_valid = valid_idx.max()
        # Ensure timezone naive
        if hasattr(last_valid, 'tzinfo') and last_valid.tzinfo:
             last_valid = last_valid.tz_convert(None)
             
        if last_valid < threshold_date:
            stale_cols.append(col)
            
    logger.info(f"Found {len(stale_cols)} stale columns: {stale_cols}")
    candidates.extend(stale_cols)
    
    candidates = sorted(list(set(candidates)))
    if not candidates:
        logger.info("No candidates for repair found. Everything looks good!")
        return

    logger.info(f"Attempting to repair {len(candidates)} symbols...")
    
    # Batch download
    batch_size = 20
    import time
    
    repaired_data = pd.DataFrame()
    
    for i in range(0, len(candidates), batch_size):
        batch = candidates[i:i+batch_size]
        logger.info(f"Downloading batch {i//batch_size + 1}: {batch}")
        
        try:
            # Handle special symbols for yfinance
            yf_batch = []
            for sym in batch:
                 if sym.isdigit(): yf_batch.append(f"{sym}.T")
                 elif sym.endswith(".JP"): yf_batch.append(f"{sym.replace('.JP', '.T')}")
                 else: yf_batch.append(sym)
            
            # Use period instead of dates for safety
            data = yf.download(yf_batch, period="1mo", group_by='column', progress=False, ignore_tz=True)
            
            if not data.empty:
                logger.info(f"Data columns: {data.columns}")
                
                batch_data = pd.DataFrame()
                
                # Check column structure
                if isinstance(data.columns, pd.MultiIndex):
                    # MultiIndex: (PriceType, Ticker)
                    # We need to extract the best price for EACH ticker
                    
                    # Levels might be (Price, Ticker) or (Ticker, Price) depending on yfinance version/args
                    # Based on logs: names=['Price', 'Ticker']
                    
                    # Get unique tickers from the index
                    # data.columns.levels[1] contains tickers if names=['Price', 'Ticker']
                    tickers = data.columns.get_level_values('Ticker').unique()
                    
                    for ticker in tickers:
                        try:
                            # Try Adj Close first, then Close
                            if ('Adj Close', ticker) in data.columns:
                                col_data = data[('Adj Close', ticker)]
                            elif ('Close', ticker) in data.columns:
                                col_data = data[('Close', ticker)]
                            else:
                                continue
                                
                            batch_data[ticker] = col_data
                        except Exception as e:
                            logger.warning(f"Error extracting data for {ticker}: {e}")

                else:
                    # Single index (likely just one symbol in result)
                    if "Adj Close" in data.columns:
                        batch_data = pd.DataFrame({batch[0]: data["Adj Close"]})
                    elif "Close" in data.columns:
                        batch_data = pd.DataFrame({batch[0]: data["Close"]})

                if not batch_data.empty:
                     # Clean column names (remove .T)
                    batch_data.columns = [c.replace('.T', '') for c in batch_data.columns]
                    
                    if repaired_data.empty:
                        repaired_data = batch_data
                    else:
                        repaired_data = pd.concat([repaired_data, batch_data], axis=1)
                    
                    logger.info(f"Successfully processed batch, got columns: {batch_data.columns.tolist()}")

            time.sleep(2) # be nice to API
            
        except Exception as e:
            logger.error(f"Error downloading batch: {e}")

    # Merge repaired data
    if not repaired_data.empty:
        logger.info(f"Downloaded fresh data for {len(repaired_data.columns)} symbols")
        
        # Merge logic: update existing df with new values
        if repaired_data.index.tz is not None:
            repaired_data.index = repaired_data.index.tz_localize(None)
            
        combined = df.combine_first(repaired_data)
        df = combined # Update current df reference

    # Also merge from resources/charts.csv if available
    charts_file = Config.RESOURCES_DIR / "charts.csv"
    if charts_file.exists():
        logger.info(f"Merging fallback data from {charts_file}")
        try:
            fallback = pd.read_csv(charts_file, index_col=0, parse_dates=True)
            if fallback.index.tz is not None:
                fallback.index = fallback.index.tz_localize(None)
            
            # Only merge columns that are empty or missing in current df
            # Or simplified: use combine_first again (df takes precedence)
            # checking which columns are actually missing
            missing_cols = [c for c in fallback.columns if c not in df.columns or df[c].dropna().empty]
            
            if missing_cols:
                logger.info(f"Found {len(missing_cols)} symbols to restore from fallback: {missing_cols}")
                fallback_subset = fallback[missing_cols]
                df = df.combine_first(fallback_subset)
        except Exception as e:
            logger.error(f"Error merging fallback data: {e}")

    # Save final result
    df.sort_index(inplace=True)
    df.to_csv(price_file)
    logger.info(f"Successfully saved merged data to {price_file}")

if __name__ == "__main__":
    repair_market_data()
