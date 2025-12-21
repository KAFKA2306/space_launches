"""Stock price data downloading and processing."""

import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Set

import pandas as pd
import yfinance as yf

from src.config import Config

from .alternative_data import AlternativeDataFetcher

logger = logging.getLogger(__name__)


class StockDataManager:
    """Manage stock price data downloading and processing."""

    def __init__(self, config: Config = None, use_alternative_sources: bool = False):
        self.config = config or Config()
        self.use_alternative_sources = use_alternative_sources
        self.alternative_fetcher = AlternativeDataFetcher(config) if use_alternative_sources else None

        # Set up API keys from environment variables
        if self.alternative_fetcher:
            self.alternative_fetcher.alpha_vantage_key = os.getenv("ALPHA_VANTAGE_API_KEY")

    def process_security_code(self, code: str) -> str:
        """Process and standardize security codes for Yahoo Finance."""
        if pd.isna(code) or code == "":
            return None

        code = str(code).strip().upper()

        # Handle Japanese stocks
        # Handle Japanese stocks
        # Pure digits (old format) or 3 digits + 1 letter (new format since 2024)
        if code.isdigit() or (len(code) == 4 and code[:3].isdigit() and code[3].isalpha()):
            return f"{code}.T"
        elif code.endswith(".JP"):
            return f"{code[:-3]}.T"
        elif code.endswith(".US"):
            return code[:-3]
        else:
            return code

    def extract_security_codes(self, trades_df: pd.DataFrame) -> Set[str]:
        """Extract unique security codes from trade data, including mapped fund tickers."""
        codes = set()

        # Extract from security_code column
        if "security_code" in trades_df.columns:
            security_codes = trades_df["security_code"].apply(self.process_security_code)
            codes.update(security_codes.dropna().unique())

        # Also extract from ticker column (mapped funds)
        if "ticker" in trades_df.columns:
            ticker_codes = trades_df["ticker"].dropna().unique()
            for ticker in ticker_codes:
                processed = self.process_security_code(ticker)
                if processed:
                    codes.add(processed)

        # Add common ETFs that might be mapped from fund names
        # These are commonly held ETFs that should always be downloaded
        common_etfs = [
            "VTI",
            "VOO",
            "VWO",
            "VEA",
            "VIG",
            "VYM",
            "VXUS",  # Vanguard
            "SPY",
            "QQQ",
            "IWM",
            "EFA",
            "EEM",
            "AGG",
            "BND",  # iShares/SPDR
            "ACWI",
            "ICLN",
            "SOXX",
            "NOBL",
            "GLD",
            "GLDM",  # Other ETFs
            "USDJPY=X",
            "EURJPY=X",  # Forex
        ]
        codes.update(common_etfs)

        logger.info(f"Extracted {len(codes)} unique security codes (including mapped tickers and common ETFs)")
        return codes

    def update_stock_prices_alternative(
        self,
        prices_file_path: Path,
        security_codes: Set[str],
        sources: Optional[list] = None,
    ) -> pd.DataFrame:
        """Update stock prices using alternative data sources (not yfinance)."""
        if not self.alternative_fetcher:
            logger.warning("Alternative data fetcher not initialized. Using yfinance fallback.")
            return self.update_stock_prices(prices_file_path, security_codes)

        if not security_codes:
            logger.warning("No security codes provided")
            return pd.DataFrame()

        logger.info(f"Updating stock prices using alternative sources for {len(security_codes)} securities")

        # Load existing data or determine start date
        existing_data = pd.DataFrame()
        start_date = self.config.HISTORICAL_DATA["default_start_date"]

        if prices_file_path.exists():
            try:
                existing_data = self.load_stock_prices(prices_file_path)
                if not existing_data.empty:
                    last_date = existing_data.index.max()
                    start_date = (last_date + timedelta(days=1)).strftime("%Y-%m-%d")
                    logger.info(f"Found existing data up to {last_date}. Fetching from {start_date}")
                else:
                    logger.info("Existing file is empty. Starting fresh download")
            except Exception as e:
                logger.warning(f"Error reading existing data: {e}. Starting fresh")
        else:
            logger.info("No existing data found. Starting fresh download")

        # Check if we need to download
        end_date = datetime.now().strftime("%Y-%m-%d")
        if start_date > end_date:
            logger.info("Stock price data is already up to date")
            return existing_data

        # Use alternative data fetcher
        sources = sources or self.config.ALTERNATIVE_DATA_SOURCES["default_sources"]
        delay_seconds = self.config.ALTERNATIVE_DATA_SOURCES["rate_limit_seconds"]
        max_symbols = self.config.ALTERNATIVE_DATA_SOURCES["max_symbols_per_batch"]

        # Process security codes for alternative sources
        processed_codes = []
        for code in security_codes:
            if pd.isna(code) or code == "":
                continue
            # For alternative sources, we might need different processing
            processed_code = str(code).strip()
            if processed_code.endswith(".T"):
                processed_code = processed_code[:-2]  # Remove .T for alternative sources
            processed_codes.append(processed_code)

        # Fetch historical data
        historical_data = self.alternative_fetcher.fetch_multiple_symbols(
            symbols=processed_codes,
            start_date=start_date,
            end_date=end_date,
            sources=sources,
            delay_seconds=delay_seconds,
            max_symbols=max_symbols,
        )

        # Convert to price DataFrame (close prices only)
        new_price_data = pd.DataFrame()
        if historical_data:
            for symbol, df in historical_data.items():
                if not df.empty and "Close" in df.columns:
                    new_price_data[symbol] = df["Close"]

        # Merge with existing data
        if existing_data.empty and new_price_data.empty:
            logger.warning("No stock price data available")
            return pd.DataFrame()
        elif existing_data.empty:
            combined_data = new_price_data
        elif new_price_data.empty:
            combined_data = existing_data
        else:
            # Merge existing and new data
            all_columns = set(existing_data.columns) | set(new_price_data.columns)
            existing_data = existing_data.reindex(columns=all_columns)
            new_price_data = new_price_data.reindex(columns=all_columns)

            combined_data = pd.concat([existing_data, new_price_data])
            combined_data = combined_data.sort_index()
            combined_data = combined_data[~combined_data.index.duplicated(keep="last")]

        # Save updated data
        self.save_stock_prices(combined_data, prices_file_path)

        logger.info(f"✅ Stock price data updated using alternative sources: {len(combined_data)} records")
        logger.info(f"   Securities: {len(combined_data.columns) if not combined_data.empty else 0}")

        return combined_data

    def update_stock_prices(
        self,
        prices_file_path: Path,
        security_codes: Set[str],
        batch_size: int = 20,
        delay_seconds: float = 3.0,
        retry_count: int = 2,
        use_fallback: bool = True,
    ) -> pd.DataFrame:
        """Update stock price data incrementally by fetching only new data."""
        # Route to alternative sources if configured
        if self.use_alternative_sources:
            logger.info("Using alternative data sources instead of yfinance")
            return self.update_stock_prices_alternative(prices_file_path, security_codes)

        import time

        end_date = datetime.now().strftime("%Y-%m-%d")

        if not security_codes:
            logger.warning("No security codes provided")
            return pd.DataFrame()

        # Load existing data or determine start date
        existing_data = pd.DataFrame()
        new_symbols = set()
        incremental_start_date = self.config.MARKET_START_DATE

        if prices_file_path.exists():
            try:
                existing_data = self.load_stock_prices(prices_file_path)
                if not existing_data.empty:
                    last_date = existing_data.index.max()
                    incremental_start_date = (last_date + timedelta(days=1)).strftime("%Y-%m-%d")

                    # Find NEW symbols that need full historical data
                    existing_symbols = set(existing_data.columns)
                    new_symbols = security_codes - existing_symbols
                    # existing_to_update = security_codes & existing_symbols

                    if new_symbols:
                        logger.info(f"Found {len(new_symbols)} NEW symbols to download full history for")
                        logger.info(f"New symbols: {list(new_symbols)[:10]}{'...' if len(new_symbols) > 10 else ''}")

                    logger.info(
                        f"Found existing price data up to {last_date}. Fetching incremental from {incremental_start_date}"
                    )
                else:
                    incremental_start_date = self.config.MARKET_START_DATE
                    logger.info("Existing price file is empty. Starting fresh download")
            except Exception as e:
                logger.warning(f"Error reading existing price data: {e}. Starting fresh")
                incremental_start_date = self.config.MARKET_START_DATE
        else:
            logger.info("No existing price data found. Starting fresh download")

        logger.info(f"Updating stock prices for {len(security_codes)} securities")
        logger.info(f"Using batches of {batch_size} with {delay_seconds}s delays")

        new_price_data = pd.DataFrame()
        successful_downloads = 0

        def download_batch(batch, start, end, batch_label):
            """Helper to download a batch of symbols."""
            nonlocal successful_downloads

            for attempt in range(retry_count):
                try:
                    logger.info(f"Downloading {batch_label} (attempt {attempt + 1}/{retry_count})")

                    if len(batch) == 1:
                        data = yf.download(batch[0], start=start, end=end, progress=False)
                        if not data.empty:
                            batch_data = pd.DataFrame(
                                {batch[0]: data["Adj Close"] if "Adj Close" in data.columns else data["Close"]}
                            )
                        else:
                            batch_data = pd.DataFrame()
                    else:
                        data = yf.download(
                            batch,
                            start=start,
                            end=end,
                            group_by="column",
                            progress=False,
                            ignore_tz=True,
                        )

                        if data.empty:
                            batch_data = pd.DataFrame()
                        else:
                            if "Adj Close" in data.columns:
                                batch_data = data["Adj Close"].copy()
                            elif "Close" in data.columns:
                                batch_data = data["Close"].copy()
                            else:
                                batch_data = data

                    if not batch_data.empty:
                        if hasattr(batch_data, "columns"):
                            batch_data.columns = [col.rstrip(".T") for col in batch_data.columns]
                        batch_data = batch_data.dropna(axis=1, how="all")
                        successful_downloads += len(batch_data.columns) if hasattr(batch_data, "columns") else 1
                        logger.info(
                            f"✅ Downloaded {len(batch_data.columns) if hasattr(batch_data, 'columns') else 1} securities"
                        )
                        return batch_data
                    else:
                        logger.warning("No new data returned for batch")
                        return pd.DataFrame()

                except Exception as e:
                    if "rate limit" in str(e).lower() or "429" in str(e):
                        wait_time = delay_seconds * (2**attempt)
                        logger.warning(f"Rate limit hit. Waiting {wait_time}s before retry...")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"Error downloading batch: {e}")
                        break

            logger.error(f"❌ Failed to download {batch_label} after {retry_count} attempts")
            return pd.DataFrame()

        # Download full history for NEW symbols
        if new_symbols:
            new_symbols_list = list(new_symbols)
            historical_start = self.config.MARKET_START_DATE
            logger.info(f"Downloading full history for {len(new_symbols)} NEW symbols from {historical_start}")

            for i in range(0, len(new_symbols_list), batch_size):
                batch = new_symbols_list[i : i + batch_size]
                batch_num = (i // batch_size) + 1
                total_batches = (len(new_symbols_list) + batch_size - 1) // batch_size

                if i > 0:
                    logger.info(f"Waiting {delay_seconds}s before next batch...")
                    time.sleep(delay_seconds)

                batch_data = download_batch(batch, historical_start, end_date, f"NEW batch {batch_num}/{total_batches}")
                if not batch_data.empty:
                    if new_price_data.empty:
                        new_price_data = batch_data
                    else:
                        new_price_data = pd.concat([new_price_data, batch_data], axis=1)

        # Download incremental updates for EXISTING symbols (if date range is valid)
        if incremental_start_date <= end_date:
            existing_symbols = security_codes - new_symbols
            if existing_symbols:
                existing_list = list(existing_symbols)
                logger.info(
                    f"Downloading incremental updates for {len(existing_symbols)} existing symbols from {incremental_start_date}"
                )

                for i in range(0, len(existing_list), batch_size):
                    batch = existing_list[i : i + batch_size]
                    batch_num = (i // batch_size) + 1
                    total_batches = (len(existing_list) + batch_size - 1) // batch_size

                    if new_price_data.empty and i == 0:
                        pass  # First batch, no delay needed
                    else:
                        logger.info(f"Waiting {delay_seconds}s before next batch...")
                        time.sleep(delay_seconds)

                    batch_data = download_batch(
                        batch, incremental_start_date, end_date, f"INCREMENTAL batch {batch_num}/{total_batches}"
                    )
                    if not batch_data.empty:
                        if new_price_data.empty:
                            new_price_data = batch_data
                        else:
                            new_price_data = pd.concat([new_price_data, batch_data], axis=1)
        else:
            logger.info("Stock price data is already up to date for existing symbols")

        # Merge existing and new data
        if existing_data.empty and new_price_data.empty:
            # Try fallback to DIC directory if no data available
            if use_fallback:
                logger.info("No stock price data downloaded. Trying fallback to DIC directory...")
                fallback_data = self._load_fallback_stock_data(security_codes)
                if not fallback_data.empty:
                    # Save fallback data to processed location for future use
                    self.save_stock_prices(fallback_data, prices_file_path)
                    logger.info("✅ Using fallback stock price data from DIC directory")
                    return fallback_data

            logger.warning("No stock price data available - continuing with analysis")
            return pd.DataFrame()
        elif existing_data.empty:
            combined_data = new_price_data
        elif new_price_data.empty:
            combined_data = existing_data
        else:
            # Ensure all securities are included
            all_columns = set(existing_data.columns) | set(new_price_data.columns)

            # Reindex both dataframes to have all columns
            existing_data = existing_data.reindex(columns=all_columns)
            new_price_data = new_price_data.reindex(columns=all_columns)

            # Combine data
            combined_data = pd.concat([existing_data, new_price_data])
            combined_data = combined_data.sort_index()
            # Remove any duplicate dates
            combined_data = combined_data[~combined_data.index.duplicated(keep="last")]

        # Save updated data
        self.save_stock_prices(combined_data, prices_file_path)

        existing_securities = len(existing_data.columns) if not existing_data.empty else 0
        new_securities = len(new_price_data.columns) if not new_price_data.empty else 0
        logger.info(f"✅ Stock price data updated: {len(combined_data)} total records")
        logger.info(f"   Existing securities: {existing_securities}, Updated: {new_securities}")

        return combined_data

    def _load_fallback_stock_data(self, security_codes: Set[str]) -> pd.DataFrame:
        """Load stock price data from DIC directory as fallback."""
        try:
            # Try to load from DIC directory (legacy location)
            dic_charts_path = self.config.RESOURCES_DIR / "charts.csv"

            if dic_charts_path.exists():
                logger.info(f"Loading fallback stock data from {dic_charts_path}")
                fallback_data = pd.read_csv(dic_charts_path, index_col=0, parse_dates=True)

                # Clean up timezone information if present
                if fallback_data.index.tz is not None:
                    fallback_data.index = fallback_data.index.tz_localize(None)

                # Filter to only include securities we're looking for
                available_securities = set(fallback_data.columns)
                requested_securities = set()

                # Map security codes to available columns
                for code in security_codes:
                    # Try different variations of the security code
                    variations = [
                        code,  # Original code
                        code.rstrip(".T"),  # Remove .T suffix
                        f"{code}.T",  # Add .T suffix
                        code.replace(".T", ""),  # Replace .T
                    ]

                    for variation in variations:
                        if variation in available_securities:
                            requested_securities.add(variation)
                            break

                if requested_securities:
                    # Select only the securities we found
                    filtered_data = fallback_data[list(requested_securities)]

                    # Clean column names to remove .T suffix for consistency
                    filtered_data.columns = [col.rstrip(".T") for col in filtered_data.columns]

                    logger.info(
                        f"Loaded {len(filtered_data)} records for {len(filtered_data.columns)} securities from fallback data"
                    )
                    logger.info(f"Available securities: {list(filtered_data.columns)}")
                    logger.info(f"Date range: {filtered_data.index.min()} to {filtered_data.index.max()}")

                    return filtered_data
                else:
                    logger.warning("No matching securities found in fallback data")
                    logger.info(f"Requested: {list(security_codes)[:10]}{'...' if len(security_codes) > 10 else ''}")
                    logger.info(
                        f"Available: {list(available_securities)[:10]}{'...' if len(available_securities) > 10 else ''}"
                    )
                    return pd.DataFrame()
            else:
                logger.warning(f"Fallback stock data file not found: {dic_charts_path}")
                return pd.DataFrame()

        except Exception as e:
            logger.error(f"Error loading fallback stock data: {e}")
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

        # Use ffill to get the last valid observation for each column
        # This handles cases where different markets have different trading days
        latest_prices = price_data.ffill().iloc[-1]
        return latest_prices.dropna()

    def calculate_returns(self, price_data: pd.DataFrame, period: int = 1) -> pd.DataFrame:
        """Calculate returns for given period."""
        if price_data.empty:
            return pd.DataFrame()

        returns = price_data.pct_change(periods=period)
        return returns

    def get_price_on_date(self, price_data: pd.DataFrame, date: pd.Timestamp, security_code: str) -> float:
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
