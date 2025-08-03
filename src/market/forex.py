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
    
    def download_forex_data(self, pairs: List[str] = None, 
                          start_date: str = None, 
                          end_date: str = None) -> pd.DataFrame:
        """Download forex data from Yahoo Finance."""
        pairs = pairs or self.config.FOREX_PAIRS
        start_date = start_date or self.config.MARKET_START_DATE
        end_date = end_date or (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        logger.info(f"Downloading forex data for pairs: {pairs}")
        logger.info(f"Date range: {start_date} to {end_date}")
        
        forex_data = pd.DataFrame()
        
        for pair in pairs:
            try:
                logger.info(f"Downloading {pair}")
                data = yf.download(pair, start=start_date, end=end_date)
                
                if data.empty:
                    logger.warning(f"No data available for {pair}")
                    continue
                
                # Clean pair name for column
                clean_pair = pair.replace('=X', '')
                forex_data[clean_pair] = data['Close']
                
                logger.info(f"Downloaded {len(data)} records for {pair}")
                
            except Exception as e:
                logger.error(f"Error downloading {pair}: {e}")
        
        if forex_data.empty:
            logger.error("No forex data was downloaded")
            return pd.DataFrame()
        
        # Ensure timezone-naive datetime index
        if forex_data.index.tz is not None:
            forex_data.index = forex_data.index.tz_localize(None)
        
        logger.info(f"Successfully downloaded forex data: {list(forex_data.columns)}")
        return forex_data
    
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