from src.config import Config
from src.data.fetch.pipeline import (
    build_fund_dictionary,
    load_and_process_trades,
    update_market_data,
    update_stock_prices,
)
from src.data.fetch.status import PipelineStatus, write_pipeline_status
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

    status = PipelineStatus(mode="fetch")
    ff5_ok = False

    try:
        if args.build_fund_dict:
            build_fund_dictionary(config, logger)

        # 1. Market Data (Global)
        if args.download:
            try:
                update_market_data(config, logger)
                status.stage_market_updated = "ran"
            except Exception as e:
                logger.error(f"Forex/Global market update failed: {e}")
                status.stage_market_updated = "failed"
                status.errors_count += 1

            # FF5 Factors (Critical)
            try:
                from datetime import datetime

                from src.data.fetch.ff5_client import FF5Client

                FF5Client("data/raw").download_ff5_factors(datetime(2010, 1, 1), datetime.today())
                ff5_ok = True
            except Exception as e:
                logger.error(f"FF5 download failed: {e}")
                status.errors_count += 1
        else:
            status.stage_market_updated = "skipped"

        # 2. Ingest Trades
        trades_df = load_and_process_trades(config, logger)
        if trades_df is None:
            logger.error("Failed to load trades. HARD_FAIL.")
            status.errors_count += 1
            status.mark_complete()
            write_pipeline_status(status)
            return 1
        status.stage_raw_loaded = True

        # 3. Market Data (Specific) - Both are non-critical
        if args.download:
            try:
                update_stock_prices(trades_df, config, logger, use_alternative_sources=args.alternative_data)
            except Exception as e:
                logger.warning(f"Stock prices partially failed: {e}")
                status.errors_count += 1

            try:
                from src.data.fetch.earnings_client import EarningsClient

                tickers = [t for t in trades_df["symbol"].unique() if isinstance(t, str) and (t.isalnum() or "." in t)]
                EarningsClient("data/raw").fetch_earnings_dates(tickers)
            except Exception as e:
                logger.warning(f"Earnings fetch failed: {e}")
                status.errors_count += 1

        # 3.5 Build Fund Dictionary
        build_fund_dictionary(config, logger)

        # Finalize
        status.mark_complete()
        write_pipeline_status(status)

        # Success Definition:
        # - HARD_FAIL: trades failed to load
        # - PARTIAL_SUCCESS: FF5 OK but prices/earnings had issues
        # - FULL_SUCCESS: No errors
        if status.errors_count == 0:
            logger.info("Fetch completed successfully (FULL_SUCCESS).")
            return 0
        elif ff5_ok:
            logger.warning(f"Fetch completed with {status.errors_count} non-critical errors (PARTIAL_SUCCESS).")
            return 0  # CI/automation should continue
        else:
            logger.error("Fetch failed: FF5 critical data missing (HARD_FAIL).")
            return 1

    except Exception as e:
        logger.error(f"Critical error during fetch: {e}", exc_info=True)
        status.errors_count += 1
        status.mark_complete()
        write_pipeline_status(status)
        return 1
