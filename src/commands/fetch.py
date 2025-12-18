
import sys
from src.config import Config
from src.utils.helpers import setup_logging
from src.fetch.pipeline import (
    update_market_data,
    load_and_process_trades,
    update_stock_prices,
    create_unified_csv,
    build_fund_dictionary
)

def register(subparsers):
    parser = subparsers.add_parser("fetch", help="Fetch and Ingest Data (Market Data + Raw Trades)")
    parser.add_argument(
        "--download",
        action="store_true",
        help="Download latest market data (forex and stock prices)",
    )
    parser.add_argument(
        "--alternative-data",
        action="store_true",
        help="Use alternative data sources (STOOQ, Yahoo Direct) instead of yfinance",
    )
    parser.add_argument(
        "--build-fund-dict",
        action="store_true",
        help="Build comprehensive fund dictionary from historical data",
    )
    parser.add_argument(
        "--skip-unified",
        action="store_true",
        help="Skip creating unified CSV after fetching",
    )
    parser.set_defaults(func=run)

def setup_environment():
    config = Config()
    config.ensure_directories()
    logger = setup_logging()
    return config, logger

def run(args):
    config, logger = setup_environment()
    logger.info("Starting Data Fetch/Ingest Process")

    try:
        if args.build_fund_dict:
            build_fund_dictionary(config, logger)

        # 1. Market Data (Global)
        if args.download:
            update_market_data(config, logger)
        
        # 2. Ingest Trades (Local Raw -> Processed)
        trades_df = load_and_process_trades(config, logger)
        
        if trades_df is None:
            logger.error("Failed to load trades. Aborting.")
            return 1

        # 3. Market Data (Specific to Trades)
        if args.download:
            update_stock_prices(
                trades_df,
                config,
                logger,
                use_alternative_sources=args.alternative_data,
            )
            
        # 3.5 Build Fund Dictionary (from the just-processed trades)
        build_fund_dictionary(config, logger)
        
        # 4. Create Unified CSV (Transformation)
        if not args.skip_unified:
            create_unified_csv(config, logger)

        logger.info("Fetch/Ingest completed successfully!")
        return 0

    except Exception as e:
        logger.error(f"Error during fetch: {e}", exc_info=True)
        return 1
