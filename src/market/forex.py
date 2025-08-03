"""Forex data downloading and processing."""

import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from pathlib import Path
import logging
from typing import List, Optional

from config import Config


logger = logging.getLogger(__name__)


class ForexDataManager:
    """Manage forex data downloading and processing."""
    
    def __init__(self, config: Config = None):
        self.config = config or Config()
    
    def update_forex_data(self, forex_file_path: Path,
                         pairs: List[str] = None, 
                         retry_count: int = 3,
                         delay_seconds: float = 2.0) -> pd.DataFrame:
        """Update forex data incrementally by fetching only new data."""
        import time
        
        pairs = pairs or self.config.FOREX_PAIRS
        end_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        # Load existing data or determine start date
        existing_data = pd.DataFrame()
        if forex_file_path.exists():
            try:
                existing_data = self.load_forex_data(forex_file_path)
                if not existing_data.empty:
                    # Get last date and start from next day
                    last_date = existing_data.index.max()
                    start_date = (last_date + timedelta(days=1)).strftime('%Y-%m-%d')
                    logger.info(f"Found existing data up to {last_date}. Fetching from {start_date}")
                else:
                    start_date = self.config.MARKET_START_DATE
                    logger.info("Existing file is empty. Starting fresh download")
            except Exception as e:
                logger.warning(f"Error reading existing forex data: {e}. Starting fresh")
                start_date = self.config.MARKET_START_DATE
        else:
            start_date = self.config.MARKET_START_DATE
            logger.info("No existing forex data found. Starting fresh download")
        
        # Check if we need to download anything
        if start_date > end_date:
            logger.info("Forex data is already up to date")
            return existing_data
        
        logger.info(f"Updating forex data for pairs: {pairs}")
        logger.info(f"Date range: {start_date} to {end_date}")
        logger.info(f"Using rate limiting: {delay_seconds}s delay between requests")
        
        new_forex_data = pd.DataFrame()
        successful_downloads = 0
        
        for i, pair in enumerate(pairs):
            if i > 0:
                logger.info(f"Waiting {delay_seconds}s before next request...")
                time.sleep(delay_seconds)
            
            success = False
            for attempt in range(retry_count):
                try:
                    logger.info(f"Downloading {pair} (attempt {attempt + 1}/{retry_count})")
                    data = yf.download(pair, start=start_date, end=end_date, progress=False)
                    
                    if data.empty:
                        logger.warning(f"No new data available for {pair}")
                        # If we have existing data for this pair, mark as success
                        if not existing_data.empty and pair.replace('=X', '') in existing_data.columns:
                            success = True
                        break
                    
                    clean_pair = pair.replace('=X', '')
                    new_forex_data[clean_pair] = data['Close']
                    
                    logger.info(f"✅ Downloaded {len(data)} new records for {pair}")
                    successful_downloads += 1
                    success = True
                    break
                    
                except Exception as e:
                    if "rate limit" in str(e).lower() or "429" in str(e):
                        wait_time = delay_seconds * (2 ** attempt)
                        logger.warning(f"Rate limit hit for {pair}. Waiting {wait_time}s before retry...")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"Error downloading {pair}: {e}")
                        break
            
            if not success:
                logger.error(f"❌ Failed to download {pair} after {retry_count} attempts")
        
        # Merge existing and new data
        if existing_data.empty and new_forex_data.empty:
            logger.warning("No forex data available - continuing with analysis")
            return pd.DataFrame()
        elif existing_data.empty:
            combined_data = new_forex_data
        elif new_forex_data.empty:
            combined_data = existing_data
        else:
            # Ensure timezone-naive datetime index for new data
            if new_forex_data.index.tz is not None:
                new_forex_data.index = new_forex_data.index.tz_localize(None)
            
            # Combine data
            combined_data = pd.concat([existing_data, new_forex_data])
            combined_data = combined_data.sort_index()
            # Remove any duplicate dates
            combined_data = combined_data[~combined_data.index.duplicated(keep='last')]
        
        # Save updated data
        self.save_forex_data(combined_data, forex_file_path)
        
        total_pairs = len(existing_data.columns) if not existing_data.empty else 0
        new_pairs = len(new_forex_data.columns) if not new_forex_data.empty else 0
        logger.info(f"✅ Forex data updated: {len(combined_data)} total records")
        logger.info(f"   Existing pairs: {total_pairs}, New data for: {new_pairs} pairs")
        
        return combined_data
    
    def save_forex_data(self, forex_data: pd.DataFrame, output_path: Path):
        """Save forex data to CSV."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        forex_data.to_csv(output_path)
        logger.info(f"Forex data saved to {output_path}")
    
    def load_forex_data(self, file_path: Path) -> pd.DataFrame:
        """Load forex data from CSV."""
        if not file_path.exists():
            logger.warning(f"Forex data file not found: {file_path}")
            return pd.DataFrame()
        
        forex_data = pd.read_csv(file_path, index_col=0, parse_dates=True)
        
        # Ensure timezone-naive datetime index
        if forex_data.index.tz is not None:
            forex_data.index = forex_data.index.tz_localize(None)
        
        logger.info(f"Loaded forex data with {len(forex_data)} records")
        return forex_data
    
    def merge_forex_with_trades(self, trades_df: pd.DataFrame, 
                               forex_data: pd.DataFrame) -> pd.DataFrame:
        """Merge trade data with forex rates."""
        if forex_data.empty:
            logger.warning("No forex data available for merging")
            return trades_df
        
        # Prepare forex data for merging
        forex_for_merge = forex_data.reset_index()
        forex_for_merge = forex_for_merge.rename(columns={'Date': 'trade_date'})
        
        # Merge with trade data
        merged_df = pd.merge(trades_df, forex_for_merge, on='trade_date', how='left')
        
        logger.info("Merged trade data with forex rates")
        return merged_df
    
    def calculate_jpy_amounts(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate JPY amounts for all trades."""
        df = df.copy()
        
        def convert_to_jpy(row):
            if row['currency'] == 'JPY':
                # For JPY trades, use settlement amount directly
                return row['settlement_amount'] if pd.notna(row['settlement_amount']) else 0
            
            elif row['currency'] == 'USD':
                # For USD trades, convert using USDJPY rate
                if pd.notna(row.get('USDJPY')) and pd.notna(row['price']) and pd.notna(row['quantity']):
                    return row['price'] * row['quantity'] * row['USDJPY']
                else:
                    return row['settlement_amount'] if pd.notna(row['settlement_amount']) else 0
            
            elif row['currency'] == 'EUR':
                # For EUR trades, convert using EURJPY rate
                if pd.notna(row.get('EURJPY')) and pd.notna(row['price']) and pd.notna(row['quantity']):
                    return row['price'] * row['quantity'] * row['EURJPY']
                else:
                    return row['settlement_amount'] if pd.notna(row['settlement_amount']) else 0
            
            else:
                # For other currencies, use settlement amount if available
                return row['settlement_amount'] if pd.notna(row['settlement_amount']) else 0
        
        df['amount_jpy'] = df.apply(convert_to_jpy, axis=1)
        
        logger.info("Calculated JPY amounts for all trades")
        return df