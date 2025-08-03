"""Stock price data downloading and processing."""

import pandas as pd
import yfinance as yf
from datetime import datetime
from pathlib import Path
import logging
from typing import Set

from config import Config


logger = logging.getLogger(__name__)


class StockDataManager:
    """Manage stock price data downloading and processing."""
    
    def __init__(self, config: Config = None):
        self.config = config or Config()
    
    def process_security_code(self, code: str) -> str:
        """Process and standardize security codes for Yahoo Finance."""
        if pd.isna(code) or code == '':
            return None
        
        code = str(code).strip().upper()
        
        # Handle Japanese stocks
        if code.isdigit():
            return f"{code}.T"
        elif code.endswith('.JP'):
            return f"{code[:-3]}.T"
        elif code.endswith('.US'):
            return code[:-3]
        else:
            return code
    
    def extract_security_codes(self, trades_df: pd.DataFrame) -> Set[str]:
        """Extract unique security codes from trade data."""
        codes = trades_df['security_code'].apply(self.process_security_code)
        codes = codes.dropna().unique()
        
        logger.info(f"Extracted {len(codes)} unique security codes")
        return set(codes)
    
    def download_stock_prices(self, security_codes: Set[str], 
                            start_date: str = None, 
                            end_date: str = None) -> pd.DataFrame:
        """Download stock price data from Yahoo Finance."""
        start_date = start_date or self.config.MARKET_START_DATE
        end_date = end_date or datetime.now().strftime('%Y-%m-%d')
        
        logger.info(f"Downloading stock prices for {len(security_codes)} securities")
        logger.info(f"Date range: {start_date} to {end_date}")
        
        if not security_codes:
            logger.warning("No security codes provided")
            return pd.DataFrame()
        
        codes_list = list(security_codes)
        
        try:
            # Download all at once for efficiency
            data = yf.download(
                codes_list, 
                start=start_date, 
                end=end_date, 
                group_by='column',
                ignore_tz=True
            )
            
            if data.empty:
                logger.warning("No stock price data downloaded")
                return pd.DataFrame()
            
            # Extract adjusted close prices
            if 'Adj Close' in data.columns:
                adj_close_data = data['Adj Close'].copy()
            else:
                # Fallback to Close if Adj Close not available
                adj_close_data = data['Close'].copy() if 'Close' in data.columns else data
            
            # Clean column names (remove .T suffix for display)
            if hasattr(adj_close_data, 'columns'):
                adj_close_data.columns = [col.rstrip('.T') for col in adj_close_data.columns]
            
            # Remove columns with all NaN values
            adj_close_data = adj_close_data.dropna(axis=1, how='all')
            
            logger.info(f"Downloaded prices for {len(adj_close_data.columns)} securities")
            return adj_close_data
            
        except Exception as e:
            logger.error(f"Error downloading stock prices: {e}")
            return pd.DataFrame()
    
    def save_stock_prices(self, price_data: pd.DataFrame, output_path: Path):
        """Save stock price data to CSV."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        price_data.to_csv(output_path)
        logger.info(f"Stock price data saved to {output_path}")
    
    def load_stock_prices(self, file_path: Path) -> pd.DataFrame:
        """Load stock price data from CSV."""
        if not file_path.exists():
            logger.warning(f"Stock price data file not found: {file_path}")
            return pd.DataFrame()
        
        price_data = pd.read_csv(file_path, index_col=0, parse_dates=True)
        logger.info(f"Loaded stock price data with {len(price_data)} records")
        return price_data
    
    def get_latest_prices(self, price_data: pd.DataFrame) -> pd.Series:
        """Get latest prices for all securities."""
        if price_data.empty:
            return pd.Series()
        
        latest_prices = price_data.iloc[-1]
        return latest_prices.dropna()
    
    def calculate_returns(self, price_data: pd.DataFrame, period: int = 1) -> pd.DataFrame:
        """Calculate returns for given period."""
        if price_data.empty:
            return pd.DataFrame()
        
        returns = price_data.pct_change(periods=period)
        return returns
    
    def get_price_on_date(self, price_data: pd.DataFrame, date: pd.Timestamp, 
                         security_code: str) -> float:
        """Get price for a specific security on a specific date."""
        if price_data.empty or security_code not in price_data.columns:
            return None
        
        # Find the closest date
        try:
            if date in price_data.index:
                price = price_data.loc[date, security_code]
            else:
                # Find nearest date
                nearest_date = price_data.index[price_data.index <= date]
                if len(nearest_date) > 0:
                    price = price_data.loc[nearest_date[-1], security_code]
                else:
                    price = None
            
            return price if pd.notna(price) else None
            
        except Exception as e:
            logger.warning(f"Error getting price for {security_code} on {date}: {e}")
            return None