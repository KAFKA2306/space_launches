import json

import pandas as pd

from src.data.loaders import DataLoader
from src.market.data_converter import DataConverter
from src.market.forex import ForexDataManager
from src.market.fund_dictionary_builder import FundDictionaryBuilder
from src.market.stocks import StockDataManager


def update_market_data(config, logger):
    logger.info("=== Updating Market Data (Incremental) ===")

    forex_manager = ForexDataManager(config)
    # Save to interim/market
    forex_path = config.MARKET_DATA_DIR / "forex_data.csv"
    forex_data = forex_manager.update_forex_data(forex_path)

    if not forex_data.empty:
        logger.info(f"Forex data updated: {len(forex_data)} records")
    else:
        logger.warning("No forex data available")
        forex_data = None

    return forex_data


def load_and_process_trades(config, logger):
    logger.info("=== Loading Trading Data ===")

    raw_data_dir = config.RAW_DATA_DIR

    if not raw_data_dir.exists():
        logger.error(f"Raw data directory not found: {raw_data_dir}")
        return None

    # Use proper DataLoader
    data_loader = DataLoader(config)

    try:
        # Load all trading data using the proper data loader
        trades_df = data_loader.load_all_broker_data(raw_data_dir)

        if trades_df is None or trades_df.empty:
            logger.error("No trading data found. Please check your CSV files in the data/raw directory.")
            return None

        logger.info(f"Successfully loaded {len(trades_df)} trades from raw data")

    except Exception as e:
        logger.error(f"Error loading trading data: {e}")
        return None

    # Save to interim/trades
    trades_path = config.TRADES_DATA_DIR / "trades.csv"
    trades_df.to_csv(trades_path, index=False)
    logger.info(f"Processed trades saved to {trades_path}")

    return trades_df


def update_stock_prices(trades_df, config, logger, use_alternative_sources=False):
    logger.info("=== Updating Stock Prices (Incremental) ===")

    stock_manager = StockDataManager(config, use_alternative_sources=use_alternative_sources)

    security_codes = stock_manager.extract_security_codes(trades_df)

    if not security_codes:
        logger.warning("No security codes found in trading data")
        return None

    # Save to interim/market
    price_path = config.MARKET_DATA_DIR / "stock_prices.csv"
    price_data = stock_manager.update_stock_prices(price_path, security_codes)

    if not price_data.empty:
        logger.info(f"Stock price data updated: {len(price_data)} records for {len(price_data.columns)} securities")
    else:
        logger.warning("No stock price data available")

    return price_data


def create_unified_csv(config, logger):
    logger.info("=== Creating Unified CSV ===")

    try:
        converter = DataConverter(config)
        # Use dedicated unified directory (data/unified)
        unified_output_dir = config.UNIFIED_DATA_DIR

        # We need to tell converter where to find processed trades (interim/trades)
        unified_csv_path = converter.create_unified_trades_csv(config.TRADES_DATA_DIR, unified_output_dir)

        if unified_csv_path:
            logger.info(f"Unified CSV created successfully: {unified_csv_path}")

            df = pd.read_csv(unified_csv_path)

            logger.info("Unified CSV Summary:")
            logger.info(f"  Total trades: {len(df)}")
            logger.info(f"  Unique securities: {df['security_code'].nunique()}")
            logger.info(f"  Investment funds mapped: {df['ticker_mapped'].sum()}")
            logger.info(f"  Investment funds identified: {df['is_investment_fund'].sum()}")
            logger.info(f"  Total JPY amount: {df['amount_jpy_unified'].sum():,.0f} JPY")

            return unified_csv_path
        else:
            logger.warning("Failed to create unified CSV")
            return None

    except Exception as e:
        logger.error(f"Error creating unified CSV: {e}")
        return None


def build_fund_dictionary(config, logger):
    logger.info("=== Building Comprehensive Fund Dictionary ===")

    try:
        builder = FundDictionaryBuilder(config)
        dict_path = builder.build_and_save_dictionary()

        if dict_path:
            logger.info(f"Fund dictionary built successfully: {dict_path}")

            with open(dict_path, "r", encoding="utf-8") as f:
                fund_dict = json.load(f)

            metadata = fund_dict.get("metadata", {})
            logger.info("Dictionary Summary:")
            logger.info(f"  Total funds: {metadata.get('total_funds', 0)}")
            logger.info(f"  Mapped funds: {metadata.get('mapped_funds', 0)}")
            logger.info(f"  Unmapped funds: {metadata.get('unmapped_funds', 0)}")

            return dict_path
        else:
            logger.warning("Failed to build fund dictionary")
            return None

    except Exception as e:
        logger.error(f"Error building fund dictionary: {e}")
        return None
