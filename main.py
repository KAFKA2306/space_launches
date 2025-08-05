#!/usr/bin/env python3
"""
Trade History Analyzer - Main Entry Point

A comprehensive tool for analyzing trading history from multiple brokers,
calculating portfolio performance, and generating insights.
"""

import argparse
import logging
from pathlib import Path
import sys

# Add src to path for imports
sys.path.append(str(Path(__file__).parent / 'src'))

from config import Config
from src.utils.helpers import setup_logging, get_timestamp
from src.data.loaders import DataLoader
from src.market.forex import ForexDataManager
from src.market.stocks import StockDataManager
from src.market.data_converter import DataConverter
from src.market.alternative_data import AlternativeDataFetcher
from src.analysis.portfolio import PortfolioAnalyzer
from src.analysis.visualization import TradeVisualizer


def setup_environment():
    """Set up the environment and configuration."""
    config = Config()
    config.ensure_directories()
    logger = setup_logging()
    return config, logger


def update_market_data(config, logger):
    """Update forex and stock price data incrementally."""
    logger.info("=== Updating Market Data (Incremental) ===")
    
    # Update forex data
    forex_manager = ForexDataManager(config)
    forex_path = config.PROCESSED_DATA_DIR / "forex_data.csv"
    forex_data = forex_manager.update_forex_data(forex_path)
    
    if not forex_data.empty:
        logger.info(f"Forex data updated: {len(forex_data)} records")
    else:
        logger.warning("No forex data available")
        forex_data = None
    
    return forex_data


def load_and_process_trades(config, logger):
    """Load and process trading data from all sources."""
    logger.info("=== Loading Trading Data ===")
    
    # Load trade data
    loader = DataLoader(config)
    trades_df = loader.load_all_broker_data(config.RAW_DATA_DIR)
    
    if trades_df.empty:
        logger.error("No trading data found. Please place your CSV files in the data/raw directory.")
        return None
    
    # Save processed trades
    trades_path = config.PROCESSED_DATA_DIR / f"trades_{get_timestamp()}.csv"
    trades_df.to_csv(trades_path, index=False)
    logger.info(f"Processed trades saved to {trades_path}")
    
    return trades_df


def update_stock_prices(trades_df, config, logger, use_alternative_sources=False):
    """Update stock price data for traded securities incrementally."""
    logger.info("=== Updating Stock Prices (Incremental) ===")
    
    stock_manager = StockDataManager(config, use_alternative_sources=use_alternative_sources)
    
    # Extract security codes
    security_codes = stock_manager.extract_security_codes(trades_df)
    
    if not security_codes:
        logger.warning("No security codes found in trading data")
        return None
    
    # Update price data incrementally
    price_path = config.PROCESSED_DATA_DIR / "stock_prices.csv"
    price_data = stock_manager.update_stock_prices(price_path, security_codes)
    
    if not price_data.empty:
        logger.info(f"Stock price data updated: {len(price_data)} records for {len(price_data.columns)} securities")
    else:
        logger.warning("No stock price data available")
    
    return price_data


def export_to_json(config, logger):
    """Export processed data to JSON format."""
    logger.info("=== Exporting Data to JSON ===")
    
    converter = DataConverter(config)
    
    try:
        # Export latest processed data to JSON
        json_output_dir = config.OUTPUT_DIR / config.JSON_EXPORT['export_directory']
        result_paths = converter.convert_latest_data_to_json(
            config.PROCESSED_DATA_DIR,
            json_output_dir
        )
        
        if result_paths:
            logger.info("JSON export successful. Created files:")
            for file_type, path in result_paths.items():
                logger.info(f"  {file_type}: {path}")
            return result_paths
        else:
            logger.warning("No JSON files were created")
            return {}
            
    except Exception as e:
        logger.error(f"Error during JSON export: {e}")
        return {}


def create_unified_csv(config, logger):
    """Create unified CSV with JPY pricing and investment fund mappings."""
    logger.info("=== Creating Unified CSV ===")
    
    try:
        converter = DataConverter(config)
        unified_output_dir = config.OUTPUT_DIR / 'unified_csv'
        
        unified_csv_path = converter.create_unified_trades_csv(
            config.PROCESSED_DATA_DIR,
            unified_output_dir
        )
        
        if unified_csv_path:
            logger.info(f"Unified CSV created successfully: {unified_csv_path}")
            
            # Display summary statistics
            import pandas as pd
            df = pd.read_csv(unified_csv_path)
            
            logger.info(f"Unified CSV Summary:")
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


def analyze_portfolio(trades_df, price_data, forex_data, config, logger):
    """Perform portfolio analysis."""
    logger.info("=== Analyzing Portfolio ===")
    
    # Merge with forex data if available
    if forex_data is not None:
        forex_manager = ForexDataManager(config)
        trades_df = forex_manager.merge_forex_with_trades(trades_df, forex_data)
        trades_df = forex_manager.calculate_jpy_amounts(trades_df)
    
    # Analyze portfolio
    analyzer = PortfolioAnalyzer(config)
    
    # Current holdings
    safe_price_data = price_data if price_data is not None and not price_data.empty else pd.DataFrame()
    holdings_df = analyzer.analyze_holdings(trades_df, safe_price_data)
    if not holdings_df.empty:
        holdings_path = config.OUTPUT_DIR / f"portfolio_holdings_{get_timestamp()}.csv"
        holdings_df.to_csv(holdings_path, index=False)
        logger.info(f"Portfolio holdings saved to {holdings_path}")
    
    # Portfolio summary
    summary = analyzer.calculate_portfolio_summary(holdings_df)
    
    # Trading activity
    activity = analyzer.analyze_trading_activity(trades_df)
    
    # Security performance
    performance_df = analyzer.calculate_security_performance(trades_df, safe_price_data)
    if not performance_df.empty:
        performance_path = config.OUTPUT_DIR / f"security_performance_{get_timestamp()}.csv"
        performance_df.to_csv(performance_path, index=False)
        logger.info(f"Security performance saved to {performance_path}")
    
    return holdings_df, summary, activity, performance_df


def create_visualizations(trades_df, holdings_df, summary, activity, 
                         performance_df, price_data, config, logger):
    """Create visualizations and charts."""
    logger.info("=== Creating Visualizations ===")
    
    visualizer = TradeVisualizer(config)
    charts_dir = config.OUTPUT_DIR / "charts"
    charts_dir.mkdir(exist_ok=True)
    
    # Portfolio overview
    if not holdings_df.empty and summary:
        portfolio_chart = charts_dir / "portfolio_overview.png"
        visualizer.plot_portfolio_overview(holdings_df, summary, portfolio_chart)
    
    # Trading activity
    if not trades_df.empty and activity:
        activity_chart = charts_dir / "trading_activity.png"
        visualizer.plot_trading_activity(trades_df, activity, activity_chart)
    
    # Performance summary
    if not performance_df.empty:
        performance_chart = charts_dir / "performance_summary.png"
        visualizer.plot_performance_summary(performance_df, performance_chart)
    
    # Individual security charts
    if price_data is not None and not price_data.empty:
        security_charts_dir = charts_dir / "securities"
        visualizer.create_all_security_charts(trades_df, price_data, security_charts_dir)
    
    logger.info(f"Visualizations saved to {charts_dir}")


def print_summary(summary, activity, logger):
    """Print summary to console."""
    print("\n" + "="*60)
    print("PORTFOLIO SUMMARY")
    print("="*60)
    
    if summary:
        print(f"Total Portfolio Value: ¥{summary['total_value']:,.0f}")
        print(f"Total Cost: ¥{summary['total_cost']:,.0f}")
        print(f"Total P&L: ¥{summary['total_pnl']:,.0f} ({summary['total_pnl_percentage']:.2f}%)")
        print(f"Realized P&L: ¥{summary['realized_pnl']:,.0f}")
        print(f"Unrealized P&L: ¥{summary['unrealized_pnl']:,.0f}")
        print(f"Number of Holdings: {summary['number_of_holdings']}")
    
    print("\n" + "="*60)
    print("TRADING ACTIVITY")
    print("="*60)
    
    if activity:
        print(f"Total Trades: {activity['total_trades']}")
        print(f"Buy Trades: {activity['buy_trades']}")
        print(f"Sell Trades: {activity['sell_trades']}")
        print(f"Total Amount Traded: ¥{activity['total_amount_traded']:,.0f}")
        print(f"Average Trade Amount: ¥{activity['avg_trade_amount']:,.0f}")
        print(f"Trading Period: {activity['date_range']['days']} days")
    
    print("\n" + "="*60)


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Analyze trading history and portfolio performance"
    )
    parser.add_argument(
        "--skip-download", 
        action="store_true", 
        help="Skip downloading market data and use existing files"
    )
    parser.add_argument(
        "--charts-only", 
        action="store_true", 
        help="Only create charts from existing processed data"
    )
    parser.add_argument(
        "--export-json",
        action="store_true",
        help="Export processed data to JSON format"
    )
    parser.add_argument(
        "--alternative-data",
        action="store_true", 
        help="Use alternative data sources (STOOQ, Yahoo Direct) instead of yfinance"
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Only export data to JSON format without full analysis"
    )
    parser.add_argument(
        "--unified-csv",
        action="store_true",
        help="Create unified CSV with JPY pricing and investment fund mappings"
    )
    
    args = parser.parse_args()
    
    # Setup
    config, logger = setup_environment()
    logger.info("Starting Trade History Analysis")
    
    try:
        if args.json_only:
            # Only export to JSON without full analysis
            logger.info("Exporting data to JSON only")
            export_to_json(config, logger)
            logger.info("JSON export completed!")
            
        elif args.unified_csv:
            # Only create unified CSV with JPY pricing and fund mappings
            logger.info("Creating unified CSV only")
            create_unified_csv(config, logger)
            logger.info("Unified CSV creation completed!")
            
        elif args.charts_only:
            # Load existing data and create charts only
            logger.info("Creating charts from existing data")
            
            # Load processed data
            trades_files = list(config.PROCESSED_DATA_DIR.glob("trades_*.csv"))
            if not trades_files:
                logger.error("No processed trade data found")
                return
            
            latest_trades_file = max(trades_files, key=lambda x: x.stat().st_mtime)
            trades_df = pd.read_csv(latest_trades_file, parse_dates=['trade_date'])
            logger.info(f"Loaded trades from {latest_trades_file}")
            
            # Load price data
            price_path = config.PROCESSED_DATA_DIR / "stock_prices.csv"
            price_data = None
            if price_path.exists():
                price_data = pd.read_csv(price_path, index_col=0, parse_dates=True)
                logger.info(f"Loaded price data from {price_path}")
            
            # Create minimal analysis for charts
            analyzer = PortfolioAnalyzer(config)
            holdings_df = analyzer.analyze_holdings(trades_df, price_data or pd.DataFrame())
            summary = analyzer.calculate_portfolio_summary(holdings_df)
            activity = analyzer.analyze_trading_activity(trades_df)
            performance_df = analyzer.calculate_security_performance(trades_df, price_data or pd.DataFrame())
            
            # Create visualizations
            create_visualizations(trades_df, holdings_df, summary, activity, 
                                performance_df, price_data, config, logger)
            
        else:
            # Full analysis pipeline
            forex_data = None
            if not args.skip_download:
                forex_data = update_market_data(config, logger)
            
            # Load and process trades
            trades_df = load_and_process_trades(config, logger)
            if trades_df is None:
                return
            
            # Update stock prices
            price_data = None
            if not args.skip_download:
                price_data = update_stock_prices(trades_df, config, logger, 
                                               use_alternative_sources=args.alternative_data)
            
            # Analyze portfolio
            holdings_df, summary, activity, performance_df = analyze_portfolio(
                trades_df, price_data, forex_data, config, logger
            )
            
            # Create visualizations
            create_visualizations(trades_df, holdings_df, summary, activity, 
                                performance_df, price_data, config, logger)
            
            # Export to JSON if requested
            if args.export_json or config.JSON_EXPORT['enable_auto_export']:
                export_to_json(config, logger)
            
            # Create unified CSV if requested  
            if args.unified_csv or args.export_json:
                create_unified_csv(config, logger)
            
            # Print summary
            print_summary(summary, activity, logger)
        
        logger.info("Analysis completed successfully!")
        print(f"\nResults saved to: {config.OUTPUT_DIR}")
        
    except Exception as e:
        logger.error(f"Error during analysis: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    import pandas as pd
    main()