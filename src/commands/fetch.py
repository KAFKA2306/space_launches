from src.config import Config
from src.fetch.pipeline import (
    build_fund_dictionary,
    load_and_process_trades,
    update_market_data,
    update_stock_prices,
)
from src.fetch.status import PipelineStatus, write_pipeline_status
from src.utils.helpers import setup_logging


def register(subparsers, command_name: str = "import"):
    """Register the import (data fetch) command."""
    parser = subparsers.add_parser(
        command_name,
        help="[1] データ取込: Import broker CSVs + optionally download market data",
    )
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
    # Note: --skip-unified removed. Per design spec, fetch doesn't create unified CSV.
    # Unified CSV creation is the responsibility of the 'run' command.
    parser.set_defaults(func=run)


def setup_environment():
    config = Config()
    config.ensure_directories()
    logger = setup_logging()
    return config, logger


def run(args):
    config, logger = setup_environment()
    logger.info("Starting Data Fetch/Ingest Process")

    # Initialize pipeline status tracker with mode='fetch'
    status = PipelineStatus(mode="fetch")

    try:
        if args.build_fund_dict:
            build_fund_dictionary(config, logger)

        # 1. Market Data (Global) - only if explicitly requested
        if args.download:
            try:
                update_market_data(config, logger)
                status.stage_market_updated = "ran"
            except Exception as e:
                logger.error(f"Market data update failed: {e}")
                status.stage_market_updated = "failed"
                status.errors_count += 1
        else:
            status.stage_market_updated = "skipped"

        # 2. Ingest Trades (Local Raw -> Processed)
        trades_df = load_and_process_trades(config, logger)

        if trades_df is None:
            logger.error("Failed to load trades. Aborting.")
            status.errors_count += 1
            status.mark_complete()
            write_pipeline_status(status)
            return 1

        status.stage_raw_loaded = True

        # 3. Market Data (Specific to Trades) - only if download requested
        if args.download and status.stage_market_updated == "ran":
            try:
                update_stock_prices(
                    trades_df,
                    config,
                    logger,
                    use_alternative_sources=args.alternative_data,
                )
            except Exception as e:
                logger.error(f"Stock price update failed: {e}")
                status.stage_market_updated = "failed"
                status.errors_count += 1

        # 3.5 Build Fund Dictionary (from the just-processed trades)
        build_fund_dictionary(config, logger)

        # Per design spec: fetch does NOT create unified CSV
        # Unified CSV creation is the responsibility of the 'run' command
        # Set unified_written to False since fetch doesn't handle this

        # Mark pipeline complete and write status
        status.mark_complete()
        status_file = write_pipeline_status(status)

        if status.is_success():
            logger.info("Fetch/Ingest completed successfully!")
            logger.info(f"Pipeline status written to: {status_file}")
            return 0
        else:
            logger.warning(f"Fetch completed with {status.errors_count} errors")
            return 1

    except Exception as e:
        logger.error(f"Error during fetch: {e}", exc_info=True)
        status.errors_count += 1
        status.mark_complete()
        write_pipeline_status(status)
        return 1
