"""Forex data downloading and processing."""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

import pandas as pd
import yfinance as yf

from src.config import Config

logger = logging.getLogger(__name__)


class ForexDataManager:
    """Manage forex data downloading and processing."""

    def __init__(self, config: Config = None):
        self.config = config or Config()

    def update_forex_data(
        self,
        forex_file_path: Path,
        pairs: List[str] = None,
        retry_count: int = 3,
        delay_seconds: float = 2.0,
        use_fallback: bool = True,
    ) -> pd.DataFrame:
        """Update forex data incrementally by fetching only new data."""
        import time

        pairs = pairs or self.config.FOREX_PAIRS
        # Fetch up to today to ensure we get yesterday's close (yfinance end is exclusive, but for daily data it usually means 'up to')
        # Actually yfinance end date is exclusive, so using tomorrow's date or just now() is safer to get 'today' if market closed, or yesterday.
        # Standardize on 'Today' string which yfinance handles well as 'up to now'.
        end_date = datetime.now().strftime("%Y-%m-%d")

        # Load existing data or determine start date
        existing_data = pd.DataFrame()
        if forex_file_path.exists():
            try:
                existing_data = self.load_forex_data(forex_file_path)
                if not existing_data.empty:
                    # Get last date and start from next day
                    last_date = existing_data.index.max()
                    start_date = (last_date + timedelta(days=1)).strftime("%Y-%m-%d")
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

        new_forex_data = pd.DataFrame()

        # Batch download all pairs
        success = False
        for attempt in range(retry_count):
            try:
                logger.info(f"Downloading all pairs (attempt {attempt + 1}/{retry_count})")
                data = yf.download(pairs, start=start_date, end=end_date, group_by="column", progress=False)

                if data.empty:
                    logger.warning("No new data returned from yfinance")
                    break

                # Extract Close prices
                if len(pairs) == 1:
                    # Single pair case
                    clean_pair = pairs[0].replace("=X", "")
                    new_forex_data[clean_pair] = data["Close"]
                else:
                    # Multiple pairs case
                    # Handle MultiIndex columns if group_by='column'
                    # data columns level 0 = Ticker, level 1 = OHLCV
                    # Or depending on yfinance version, might be different.
                    # Generally 'Close' is needed.

                    # Safer approach with recent yfinance:
                    # data['Close'] contains columns for each ticker
                    try:
                        closes = data["Close"]
                        # Clean column names
                        closes.columns = [col.replace("=X", "") for col in closes.columns]
                        new_forex_data = closes
                    except KeyError:
                        # Fallback if structure is different
                        logger.warning("Could not find 'Close' prices in downloaded data")
                        logger.debug(f"Columns: {data.columns}")

                if not new_forex_data.empty:
                    logger.info(f"✅ Downloaded {len(new_forex_data)} new records")
                    success = True
                    break

            except Exception as e:
                logger.error(f"Error downloading forex batch: {e}")
                if attempt < retry_count - 1:
                    time.sleep(delay_seconds)

        if not success and new_forex_data.empty:
            logger.warning("Failed to download new forex data")

        # Merge existing and new data
        if existing_data.empty and new_forex_data.empty:
            # Try fallback to DIC directory if no data available
            if use_fallback:
                logger.info("No forex data downloaded. Trying fallback to DIC directory...")
                fallback_data = self._load_fallback_forex_data()
                if not fallback_data.empty:
                    # Save fallback data to processed location for future use
                    self.save_forex_data(fallback_data, forex_file_path)
                    logger.info("✅ Using fallback forex data from DIC directory")
                    return fallback_data

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
            combined_data = combined_data[~combined_data.index.duplicated(keep="last")]

        # Save updated data
        self.save_forex_data(combined_data, forex_file_path)

        total_pairs = len(existing_data.columns) if not existing_data.empty else 0
        new_pairs = len(new_forex_data.columns) if not new_forex_data.empty else 0
        logger.info(f"✅ Forex data updated: {len(combined_data)} total records")
        logger.info(f"   Existing pairs: {total_pairs}, New data for: {new_pairs} pairs")

        return combined_data

    def _load_fallback_forex_data(self) -> pd.DataFrame:
        """Load forex data from DIC directory as fallback."""
        try:
            # Try to load from DIC directory (legacy location)
            # Try to load from resources directory (legacy location)
            dic_forex_path = self.config.RESOURCES_DIR / "forex_data.csv"

            if dic_forex_path.exists():
                logger.info(f"Loading fallback forex data from {dic_forex_path}")
                fallback_data = pd.read_csv(dic_forex_path, index_col=0, parse_dates=True)

                # Clean up timezone information if present
                if fallback_data.index.tz is not None:
                    fallback_data.index = fallback_data.index.tz_localize(None)

                logger.info(f"Loaded {len(fallback_data)} records from fallback forex data")
                logger.info(f"Available pairs: {list(fallback_data.columns)}")
                logger.info(f"Date range: {fallback_data.index.min()} to {fallback_data.index.max()}")

                return fallback_data
            else:
                logger.warning(f"Fallback forex file not found: {dic_forex_path}")
                return pd.DataFrame()

        except Exception as e:
            logger.error(f"Error loading fallback forex data: {e}")
            return pd.DataFrame()

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

    def merge_forex_with_trades(self, trades_df: pd.DataFrame, forex_data: pd.DataFrame) -> pd.DataFrame:
        """Merge trade data with forex rates."""
        if forex_data.empty:
            logger.warning("No forex data available for merging")
            return trades_df

        try:
            logger.info("Starting forex data merge process")

            # Prepare forex data for merging
            forex_for_merge = forex_data.reset_index()
            logger.info(f"Forex data shape after reset_index: {forex_for_merge.shape}")
            logger.info(f"Forex data columns: {list(forex_for_merge.columns)}")

            # Flexible column name handling for different data sources
            date_column = None
            possible_date_columns = ["Date", "date", "index", "trade_date", "DATE"]
            logger.info(f"Looking for date column among: {possible_date_columns}")

            for col in possible_date_columns:
                if col in forex_for_merge.columns:
                    date_column = col
                    logger.info(f"Found date column: '{date_column}'")
                    break

            if date_column is None:
                # If no recognizable date column, use the first column
                if len(forex_for_merge.columns) > 0:
                    date_column = forex_for_merge.columns[0]
                    logger.warning(f"No standard date column found. Using first column: '{date_column}'")
                    logger.info(f"First few values in '{date_column}': {forex_for_merge[date_column].head()}")
                else:
                    logger.error("No columns found in forex data")
                    return trades_df

            # Rename the date column to 'trade_date' for merging
            if date_column != "trade_date":
                forex_for_merge = forex_for_merge.rename(columns={date_column: "trade_date"})
                logger.info(f"Renamed forex date column '{date_column}' to 'trade_date'")

            # Ensure trade_date is datetime type
            logger.info(f"Converting '{date_column}' to datetime...")
            logger.info(f"Sample values before conversion: {forex_for_merge['trade_date'].head()}")
            forex_for_merge["trade_date"] = pd.to_datetime(forex_for_merge["trade_date"], errors="coerce")

            # Remove any rows where date conversion failed
            before_count = len(forex_for_merge)
            forex_for_merge = forex_for_merge.dropna(subset=["trade_date"])
            after_count = len(forex_for_merge)

            if before_count != after_count:
                logger.warning(f"Dropped {before_count - after_count} rows with invalid dates")

            if forex_for_merge.empty:
                logger.error("No valid forex data remaining after date processing")
                return trades_df

            logger.info(
                f"Forex data date range: {forex_for_merge['trade_date'].min()} to {forex_for_merge['trade_date'].max()}"
            )

            # Ensure trades_df also has proper trade_date
            if "trade_date" not in trades_df.columns:
                logger.error("trades_df missing 'trade_date' column")
                logger.info(f"Available columns in trades_df: {list(trades_df.columns)}")
                return trades_df

            logger.info(f"Trades data date range: {trades_df['trade_date'].min()} to {trades_df['trade_date'].max()}")
            logger.info(f"Merging {len(trades_df)} trades with {len(forex_for_merge)} forex records")

            # Merge with trade data
            merged_df = pd.merge(trades_df, forex_for_merge, on="trade_date", how="left")

            # Log merge results
            forex_matches = merged_df["USDJPY"].notna().sum() if "USDJPY" in merged_df.columns else 0
            logger.info(f"Merged trade data with forex rates: {forex_matches}/{len(merged_df)} trades have forex data")

            return merged_df

        except Exception as e:
            logger.error(f"Error merging forex data with trades: {e}")
            logger.info("Continuing without forex data")
            return trades_df

    def calculate_jpy_amounts(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate JPY amounts for all trades."""
        logger.info("Starting JPY amount calculation")
        df = df.copy()

        # Log currency distribution
        currency_counts = df["currency"].value_counts()
        logger.info(f"Currency distribution: {currency_counts.to_dict()}")

        # Check forex data availability
        forex_columns = ["USDJPY", "EURJPY"]
        available_forex = [col for col in forex_columns if col in df.columns]
        logger.info(f"Available forex columns: {available_forex}")

        if available_forex:
            for col in available_forex:
                non_null_count = df[col].notna().sum()
                logger.info(f"{col} data available for {non_null_count}/{len(df)} trades")

        def convert_to_jpy(row):
            if row["currency"] == "JPY":
                # For JPY trades, use settlement amount directly
                amount = row["settlement_amount"] if pd.notna(row["settlement_amount"]) else 0
                return amount

            elif row["currency"] == "USD":
                # For USD trades, convert using USDJPY rate
                if pd.notna(row.get("USDJPY")) and pd.notna(row["price"]) and pd.notna(row["quantity"]):
                    amount = row["price"] * row["quantity"] * row["USDJPY"]
                    return amount
                else:
                    amount = row["settlement_amount"] if pd.notna(row["settlement_amount"]) else 0
                    return amount

            elif row["currency"] == "EUR":
                # For EUR trades, convert using EURJPY rate
                if pd.notna(row.get("EURJPY")) and pd.notna(row["price"]) and pd.notna(row["quantity"]):
                    amount = row["price"] * row["quantity"] * row["EURJPY"]
                    return amount
                else:
                    amount = row["settlement_amount"] if pd.notna(row["settlement_amount"]) else 0
                    return amount

            else:
                # For other currencies, use settlement amount if available
                amount = row["settlement_amount"] if pd.notna(row["settlement_amount"]) else 0
                return amount

        df["amount_jpy"] = df.apply(convert_to_jpy, axis=1)

        # Log calculation results
        total_amount = df["amount_jpy"].sum()
        valid_amounts = df["amount_jpy"].notna().sum()
        logger.info(f"Calculated JPY amounts: {valid_amounts}/{len(df)} trades")
        logger.info(f"Total JPY amount: ¥{total_amount:,.0f}")

        # Log per-currency statistics
        for currency in df["currency"].unique():
            if pd.notna(currency):
                currency_df = df[df["currency"] == currency]
                currency_total = currency_df["amount_jpy"].sum()
                logger.info(f"{currency} trades: {len(currency_df)} trades, ¥{currency_total:,.0f} total")

        return df
