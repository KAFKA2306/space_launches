import pandas as pd

from src.analysis.portfolio import PortfolioAnalyzer
from src.analysis.visualization import TradeVisualizer
from src.config import Config
from src.utils.helpers import get_timestamp, setup_logging


def register(subparsers, command_name: str = "view"):
    """Register the view (portfolio) command."""
    parser = subparsers.add_parser(command_name, help="[2] ポートフォリオ確認: View current holdings and P&L")
    parser.set_defaults(func=run)


def setup_environment():
    config = Config()
    config.ensure_directories()
    logger = setup_logging()
    return config, logger


def find_latest_processed_data(config, logger):
    """Find the latest processed trades and price data."""
    # Look in TRADES_DATA_DIR (interim/trades)
    trades_dir = config.TRADES_DATA_DIR
    if not trades_dir.exists():
        logger.error(f"Trades directory not found: {trades_dir}. Please run 'task fetch' first.")
        return None, None

    trades_files = list(trades_dir.glob("trades_*.csv"))
    if not trades_files:
        logger.error(f"No processed trade data found in {trades_dir}. Please run 'task fetch' first.")
        return None, None

    # Simple max by mtime
    latest_trades_file = max(trades_files, key=lambda x: x.stat().st_mtime)
    logger.info(f"Using latest trades file: {latest_trades_file.name}")

    trades_df = pd.read_csv(latest_trades_file, parse_dates=["trade_date"])

    # Load prices from MARKET_DATA_DIR (interim/market)
    price_path = config.MARKET_DATA_DIR / "stock_prices.csv"
    price_data = None
    if price_path.exists():
        price_data = pd.read_csv(price_path, index_col=0, parse_dates=True)
        logger.info(f"Loaded price data from {price_path.name}")
    else:
        logger.warning(f"No stock price data found at {price_path}.")

    return trades_df, price_data


def analyze_portfolio(trades_df, price_data, config, logger):
    logger.info("=== Analyzing Portfolio ===")

    # Ensure trade_date is datetime
    trades_df = trades_df.copy()
    trades_df["trade_date"] = pd.to_datetime(trades_df["trade_date"], errors="coerce")
    trades_df = trades_df.dropna(subset=["trade_date"])

    from src.market.forex import ForexDataManager

    forex_manager = ForexDataManager(config)

    # We load forex data from file since we are not downloading it in memory
    # Load from interim/market
    forex_path = config.MARKET_DATA_DIR / "forex_data.csv"
    if forex_path.exists():
        try:
            # Use the manager's method to load consistently
            forex_data = forex_manager.load_forex_data(forex_path)
            trades_df = forex_manager.merge_forex_with_trades(trades_df, forex_data)
            trades_df = forex_manager.calculate_jpy_amounts(trades_df)
        except Exception as e:
            logger.warning(f"Failed to apply forex data: {e}")
            # Continue without forex conversion if it fails
    else:
        logger.warning(f"Forex data file not found at {forex_path}. Foreign amounts wont be converted.")

    analyzer = PortfolioAnalyzer(config)

    safe_price_data = price_data if price_data is not None and not price_data.empty else pd.DataFrame()

    analysis_dir = config.REPORTS_DIR / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)

    holdings_df = analyzer.analyze_holdings(trades_df, safe_price_data)
    if not holdings_df.empty:
        holdings_path = analysis_dir / f"portfolio_holdings_{get_timestamp()}.csv"
        holdings_df.to_csv(holdings_path, index=False)
        logger.info(f"Portfolio holdings saved to {holdings_path}")

    summary = analyzer.calculate_portfolio_summary(holdings_df)
    activity = analyzer.analyze_trading_activity(trades_df)
    performance_df = analyzer.calculate_security_performance(trades_df, safe_price_data)

    if not performance_df.empty:
        performance_path = analysis_dir / f"security_performance_{get_timestamp()}.csv"
        performance_df.to_csv(performance_path, index=False)
        logger.info(f"Security performance saved to {performance_path}")

    return holdings_df, summary, activity, performance_df


def create_visualizations(
    trades_df,
    holdings_df,
    summary,
    activity,
    performance_df,
    price_data,
    config,
    logger,
):
    logger.info("=== Creating Visualizations ===")

    visualizer = TradeVisualizer(config)
    charts_dir = config.REPORTS_DIR / "charts"
    charts_dir.mkdir(exist_ok=True)

    if not holdings_df.empty and summary:
        portfolio_chart = charts_dir / "portfolio_overview.png"
        visualizer.plot_portfolio_overview(holdings_df, summary, portfolio_chart)

    if not trades_df.empty and activity:
        activity_chart = charts_dir / "trading_activity.png"
        visualizer.plot_trading_activity(trades_df, activity, activity_chart)

    if not performance_df.empty:
        performance_chart = charts_dir / "performance_summary.png"
        visualizer.plot_performance_summary(performance_df, performance_chart)

    if price_data is not None and not price_data.empty:
        security_charts_dir = charts_dir / "securities"
        visualizer.create_all_security_charts(trades_df, price_data, security_charts_dir)

    logger.info(f"Visualizations saved to {charts_dir}")


def print_summary(summary, activity):
    print("\n" + "=" * 60)
    print("PORTFOLIO SUMMARY")
    print("=" * 60)

    if summary:
        print(f"Total Portfolio Value: ¥{summary['total_value']:,.0f}")
        print(f"Total Cost: ¥{summary['total_cost']:,.0f}")
        print(f"Total P&L: ¥{summary['total_pnl']:,.0f} ({summary['total_pnl_percentage']:.2f}%)")
        print(f"Realized P&L: ¥{summary['realized_pnl']:,.0f}")
        print(f"Unrealized P&L: ¥{summary['unrealized_pnl']:,.0f}")
        print(f"Number of Holdings: {summary['number_of_holdings']}")

    print("\n" + "=" * 60)
    print("TRADING ACTIVITY")
    print("=" * 60)

    if activity:
        print(f"Total Trades: {activity['total_trades']}")
        print(f"Buy Trades: {activity['buy_trades']}")
        print(f"Sell Trades: {activity['sell_trades']}")
        print(f"Total Amount Traded: ¥{activity['total_amount_traded']:,.0f}")
        print(f"Average Trade Amount: ¥{activity['avg_trade_amount']:,.0f}")
        print(f"Trading Period: {activity['date_range']['days']} days")

    print("\n" + "=" * 60)


def run(args):
    config, logger = setup_environment()
    logger.info("Starting Trade History Analysis")

    try:
        trades_df, price_data = find_latest_processed_data(config, logger)

        if trades_df is None:
            return 1

        holdings_df, summary, activity, performance_df = analyze_portfolio(trades_df, price_data, config, logger)

        create_visualizations(
            trades_df,
            holdings_df,
            summary,
            activity,
            performance_df,
            price_data,
            config,
            logger,
        )

        print_summary(summary, activity)

        logger.info("Analysis completed successfully!")
        print(f"\nResults saved to: {config.REPORTS_DIR}")
        return 0

    except Exception as e:
        logger.error(f"Error during analysis: {e}", exc_info=True)
        return 1
