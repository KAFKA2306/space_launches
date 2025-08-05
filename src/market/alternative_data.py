"""Alternative data sources for historical price data (not using yfinance)."""

import pandas as pd
import pandas_datareader as pdr
import requests
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import json
from dateutil.relativedelta import relativedelta

logger = logging.getLogger(__name__)


class AlternativeDataFetcher:
    """Fetch historical price data from alternative sources (not yfinance)."""
    
    def __init__(self, config=None):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # API keys (should be set via environment variables in production)
        self.alpha_vantage_key = None  # Set via environment or config
        
    def fetch_from_stooq(self, symbol: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """
        Fetch historical data from STOOQ using pandas-datareader (more stable).
        Supports international markets including Japanese stocks.
        """
        try:
            logger.info(f"Fetching {symbol} from STOOQ via pandas-datareader")
            
            # Convert symbol for STOOQ format
            stooq_symbol = self._convert_to_stooq_format(symbol)
            
            # Set default date range if not provided
            if not end_date:
                end_date = datetime.now().date()
            else:
                end_date = pd.to_datetime(end_date).date()
                
            if not start_date:
                # Default to 2 years of data
                start_date = end_date - relativedelta(years=2)
            else:
                start_date = pd.to_datetime(start_date).date()
            
            logger.debug(f"STOOQ symbol: {stooq_symbol}, period: {start_date} to {end_date}")
            
            # Use pandas-datareader with STOOQ source
            df = pdr.DataReader(stooq_symbol, 'stooq', start=start_date, end=end_date)
            
            if df.empty or len(df) == 0:
                logger.warning(f"No data returned from STOOQ for {symbol}")
                return pd.DataFrame()
            
            # STOOQ returns data with newest date first, so sort to ascending order
            df = df.sort_index()
            
            # Ensure we have required columns
            required_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                logger.warning(f"Missing columns from STOOQ data for {symbol}: {missing_columns}")
                # Fill missing columns with NaN
                for col in missing_columns:
                    df[col] = pd.NA
            logger.info(f"✅ STOOQ: Retrieved {len(df)} records for {symbol}")
            return df
            
        except Exception as e:
            logger.error(f"❌ STOOQ error for {symbol}: {e}")
            return pd.DataFrame()
    
    def fetch_from_alpha_vantage(self, symbol: str, start_date: str = None) -> pd.DataFrame:
        """
        Fetch historical data from Alpha Vantage API.
        Requires API key (free tier available).
        """
        if not self.alpha_vantage_key:
            logger.warning("Alpha Vantage API key not configured, skipping")
            return pd.DataFrame()
        
        try:
            logger.info(f"Fetching {symbol} from Alpha Vantage")
            
            # Alpha Vantage API endpoint
            url = "https://www.alphavantage.co/query"
            params = {
                'function': 'TIME_SERIES_DAILY',
                'symbol': symbol,
                'apikey': self.alpha_vantage_key,
                'outputsize': 'full',  # Get full historical data
                'datatype': 'json'
            }
            
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # Check for API errors
            if "Error Message" in data:
                logger.error(f"Alpha Vantage error: {data['Error Message']}")
                return pd.DataFrame()
            
            if "Note" in data:
                logger.warning(f"Alpha Vantage note: {data['Note']}")
                return pd.DataFrame()
            
            # Extract time series data
            time_series_key = "Time Series (Daily)"
            if time_series_key not in data:
                logger.error(f"No time series data found for {symbol}")
                return pd.DataFrame()
            
            time_series = data[time_series_key]
            
            # Convert to DataFrame
            df = pd.DataFrame.from_dict(time_series, orient='index')
            df.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
            df.index = pd.to_datetime(df.index)
            df = df.sort_index()
            
            # Convert to numeric
            for col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Filter by start date if provided
            if start_date:
                start_dt = pd.to_datetime(start_date)
                df = df[df.index >= start_dt]
            
            logger.info(f"✅ Alpha Vantage: Retrieved {len(df)} records for {symbol}")
            return df
            
        except Exception as e:
            logger.error(f"❌ Alpha Vantage error for {symbol}: {e}")
            return pd.DataFrame()
    
    def fetch_from_yahoo_direct(self, symbol: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """
        Fetch data directly from Yahoo Finance (without yfinance library).
        Uses Yahoo's download API directly.
        """
        try:
            logger.info(f"Fetching {symbol} from Yahoo Finance (direct)")
            
            # Convert dates to timestamps
            start_ts = int(pd.to_datetime(start_date or '2020-01-01').timestamp())
            end_ts = int(pd.to_datetime(end_date or datetime.now()).timestamp())
            
            # Yahoo Finance download URL
            url = f"https://query1.finance.yahoo.com/v7/finance/download/{symbol}"
            params = {
                'period1': start_ts,
                'period2': end_ts,
                'interval': '1d',
                'events': 'history',
                'includeAdjustedClose': 'true'
            }
            
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            # Parse CSV response
            from io import StringIO
            df = pd.read_csv(StringIO(response.text))
            
            if df.empty:
                logger.warning(f"No data returned from Yahoo for {symbol}")
                return pd.DataFrame()
            
            # Set date as index
            df['Date'] = pd.to_datetime(df['Date'])
            df = df.set_index('Date')
            df = df.sort_index()
            
            # Remove any null rows
            df = df.dropna()
            
            logger.info(f"✅ Yahoo Direct: Retrieved {len(df)} records for {symbol}")
            return df
            
        except Exception as e:
            logger.error(f"❌ Yahoo Direct error for {symbol}: {e}")
            return pd.DataFrame()
    
    def _convert_to_stooq_format(self, symbol: str) -> str:
        """Convert ticker symbol to STOOQ format."""
        # Japanese stocks: add .JP suffix if numeric
        if symbol.isdigit():
            return f"{symbol}.jp"
        
        # US stocks: keep as is
        if symbol.replace('.', '').replace('-', '').isalpha():
            return symbol.lower()
        
        # Default: return as is but lowercase
        return symbol.lower()
    
    def fetch_historical_data(self, symbol: str, start_date: str = None, end_date: str = None,
                             sources: List[str] = None, delay_seconds: float = 1.0) -> pd.DataFrame:
        """
        Fetch historical data using multiple sources as fallbacks.
        
        Args:
            symbol: Stock ticker symbol
            start_date: Start date (YYYY-MM-DD format)
            end_date: End date (YYYY-MM-DD format)  
            sources: List of sources to try ['stooq', 'yahoo', 'alpha_vantage']
            delay_seconds: Delay between API calls
        
        Returns:
            DataFrame with historical price data
        """
        if sources is None:
            sources = ['stooq', 'yahoo', 'alpha_vantage']
        
        logger.info(f"Fetching historical data for {symbol} using sources: {sources}")
        
        for i, source in enumerate(sources):
            if i > 0:
                logger.info(f"Waiting {delay_seconds}s before next source...")
                time.sleep(delay_seconds)
            
            try:
                if source == 'stooq':
                    df = self.fetch_from_stooq(symbol, start_date, end_date)
                elif source == 'yahoo':
                    df = self.fetch_from_yahoo_direct(symbol, start_date, end_date)
                elif source == 'alpha_vantage':
                    df = self.fetch_from_alpha_vantage(symbol, start_date)
                else:
                    logger.warning(f"Unknown source: {source}")
                    continue
                
                if not df.empty and len(df) > 0:
                    logger.info(f"✅ Successfully fetched {len(df)} records for {symbol} from {source}")
                    return df
                else:
                    logger.warning(f"No data from {source} for {symbol}, trying next source...")
                    
            except Exception as e:
                logger.error(f"Error fetching from {source} for {symbol}: {e}")
                continue
        
        logger.error(f"❌ Failed to fetch data for {symbol} from all sources")
        return pd.DataFrame()
    
    def fetch_multiple_symbols(self, symbols: List[str], start_date: str = None, end_date: str = None,
                              sources: List[str] = None, delay_seconds: float = 2.0,
                              max_symbols: int = None) -> Dict[str, pd.DataFrame]:
        """
        Fetch historical data for multiple symbols.
        
        Args:
            symbols: List of ticker symbols
            start_date: Start date (YYYY-MM-DD format)
            end_date: End date (YYYY-MM-DD format)
            sources: List of sources to try for each symbol
            delay_seconds: Delay between symbol requests
            max_symbols: Maximum number of symbols to process (for testing)
        
        Returns:
            Dictionary mapping symbol -> DataFrame
        """
        if max_symbols:
            symbols = symbols[:max_symbols]
        
        # Use config rate limit if available
        if not delay_seconds and self.config:
            delay_seconds = self.config.ALTERNATIVE_DATA_SOURCES.get('rate_limit_seconds', 1.5)
        
        logger.info(f"Fetching historical data for {len(symbols)} symbols (pandas-datareader enhanced)")
        logger.info(f"Symbols: {symbols}")
        
        results = {}
        successful_fetches = 0
        
        for i, symbol in enumerate(symbols):
            if i > 0:
                logger.info(f"Waiting {delay_seconds}s before next symbol...")
                time.sleep(delay_seconds)
            
            logger.info(f"Processing symbol {i+1}/{len(symbols)}: {symbol}")
            
            df = self.fetch_historical_data(symbol, start_date, end_date, sources, 0.5)
            
            if not df.empty:
                results[symbol] = df
                successful_fetches += 1
                logger.info(f"✅ Success ({successful_fetches}/{len(symbols)}): {symbol}")
            else:
                logger.warning(f"❌ Failed ({successful_fetches}/{len(symbols)}): {symbol}")
        
        logger.info(f"Completed fetching: {successful_fetches}/{len(symbols)} symbols successful")
        return results
    
    def save_historical_data(self, data_dict: Dict[str, pd.DataFrame], output_dir: Path) -> Path:
        """Save historical data to CSV files and create a combined dataset."""
        try:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Create individual CSV files for each symbol
            individual_files = {}
            for symbol, df in data_dict.items():
                if not df.empty:
                    file_path = output_dir / f"{symbol}_historical.csv"
                    df.to_csv(file_path)
                    individual_files[symbol] = str(file_path)
                    logger.info(f"Saved {symbol} data to {file_path}")
            
            # Create combined dataset (close prices only)
            if data_dict:
                combined_df = pd.DataFrame()
                for symbol, df in data_dict.items():
                    if not df.empty and 'Close' in df.columns:
                        combined_df[symbol] = df['Close']
                
                if not combined_df.empty:
                    combined_path = output_dir / "combined_historical_prices.csv"
                    combined_df.to_csv(combined_path)
                    logger.info(f"Saved combined price data to {combined_path}")
                    
                    # Create metadata file
                    metadata = {
                        "created_at": datetime.now().isoformat(),
                        "symbols_count": len(data_dict),
                        "successful_symbols": len([s for s, df in data_dict.items() if not df.empty]),
                        "date_range": {
                            "start": combined_df.index.min().isoformat() if not combined_df.empty else None,
                            "end": combined_df.index.max().isoformat() if not combined_df.empty else None
                        },
                        "individual_files": individual_files,
                        "combined_file": str(combined_path)
                    }
                    
                    metadata_path = output_dir / "historical_data_metadata.json"
                    with open(metadata_path, 'w') as f:
                        json.dump(metadata, f, indent=2)
                    
                    logger.info(f"Historical data processing complete. Metadata saved to {metadata_path}")
                    return metadata_path
            
            return output_dir
            
        except Exception as e:
            logger.error(f"Error saving historical data: {e}")
            raise