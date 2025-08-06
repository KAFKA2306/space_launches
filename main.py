#!/usr/bin/env python3

import argparse
import logging
from pathlib import Path
import sys
import pandas as pd
import numpy as np
import re
from datetime import datetime, timedelta
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from tqdm import tqdm

sys.path.append(str(Path(__file__).parent / 'src'))

from config import Config
from src.utils.helpers import setup_logging, get_timestamp
from src.data.loaders import DataLoader, perform_eda_analysis
from src.market.forex import ForexDataManager
from src.market.stocks import StockDataManager
from src.market.data_converter import DataConverter
from src.market.alternative_data import AlternativeDataFetcher
from src.analysis.portfolio import PortfolioAnalyzer
from src.analysis.visualization import TradeVisualizer


def setup_environment():
    config = Config()
    config.ensure_directories()
    logger = setup_logging()
    return config, logger


def update_market_data(config, logger):
    logger.info("=== Updating Market Data (Incremental) ===")
    
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
    logger.info("=== Loading Trading Data (CODES-style) ===")
    
    import pandas as pd
    
    all_data = []
    raw_data_dir = config.RAW_DATA_DIR
    
    if not raw_data_dir.exists():
        logger.error(f"Raw data directory not found: {raw_data_dir}")
        return None
    
    # Use proper DataLoader instead of undefined functions
    from src.data.loaders import DataLoader
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
    
    trades_path = config.PROCESSED_DATA_DIR / f"trades_{get_timestamp()}.csv"
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
    
    price_path = config.PROCESSED_DATA_DIR / "stock_prices.csv"
    price_data = stock_manager.update_stock_prices(price_path, security_codes)
    
    if not price_data.empty:
        logger.info(f"Stock price data updated: {len(price_data)} records for {len(price_data.columns)} securities")
    else:
        logger.warning("No stock price data available")
    
    return price_data


def export_to_json(config, logger):
    logger.info("=== Exporting Data to JSON ===")
    
    converter = DataConverter(config)
    
    try:
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


def build_fund_dictionary(config, logger):
    logger.info("=== Building Comprehensive Fund Dictionary ===")
    
    try:
        from src.market.fund_dictionary_builder import FundDictionaryBuilder
        import json
        
        builder = FundDictionaryBuilder(config)
        dict_path = builder.build_and_save_dictionary()
        
        if dict_path:
            logger.info(f"Fund dictionary built successfully: {dict_path}")
            
            with open(dict_path, 'r', encoding='utf-8') as f:
                fund_dict = json.load(f)
            
            metadata = fund_dict.get('metadata', {})
            logger.info(f"Dictionary Summary:")
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


def analyze_portfolio(trades_df, price_data, forex_data, config, logger):
    logger.info("=== Analyzing Portfolio ===")
    
    # Ensure trade_date is datetime
    trades_df = trades_df.copy()
    trades_df.loc[:, 'trade_date'] = pd.to_datetime(trades_df['trade_date'], errors='coerce')
    trades_df = trades_df.dropna(subset=['trade_date'])
    
    if forex_data is not None:
        forex_manager = ForexDataManager(config)
        trades_df = forex_manager.merge_forex_with_trades(trades_df, forex_data)
        trades_df = forex_manager.calculate_jpy_amounts(trades_df)
    
    analyzer = PortfolioAnalyzer(config)
    
    safe_price_data = price_data if price_data is not None and not price_data.empty else pd.DataFrame()
    holdings_df = analyzer.analyze_holdings(trades_df, safe_price_data)
    if not holdings_df.empty:
        holdings_path = config.OUTPUT_DIR / f"portfolio_holdings_{get_timestamp()}.csv"
        holdings_df.to_csv(holdings_path, index=False)
        logger.info(f"Portfolio holdings saved to {holdings_path}")
    
    summary = analyzer.calculate_portfolio_summary(holdings_df)
    
    activity = analyzer.analyze_trading_activity(trades_df)
    
    performance_df = analyzer.calculate_security_performance(trades_df, safe_price_data)
    if not performance_df.empty:
        performance_path = config.OUTPUT_DIR / f"security_performance_{get_timestamp()}.csv"
        performance_df.to_csv(performance_path, index=False)
        logger.info(f"Security performance saved to {performance_path}")
    
    return holdings_df, summary, activity, performance_df


def create_visualizations(trades_df, holdings_df, summary, activity, 
                         performance_df, price_data, config, logger):
    logger.info("=== Creating Visualizations ===")
    
    visualizer = TradeVisualizer(config)
    charts_dir = config.OUTPUT_DIR / "charts"
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


def print_summary(summary, activity, logger):
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
    parser = argparse.ArgumentParser(
        description="Analyze trading history and portfolio performance (uses existing data by default)"
    )
    parser.add_argument(
        "--download", 
        action="store_true", 
        help="Download latest market data (forex and stock prices)"
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
    parser.add_argument(
        "--build-fund-dict",
        action="store_true",
        help="Build comprehensive fund dictionary from historical data"
    )
    
    args = parser.parse_args()
    
    config, logger = setup_environment()
    logger.info("Starting Trade History Analysis")
    
    try:
        if args.json_only:
            logger.info("Exporting data to JSON only")
            export_to_json(config, logger)
            logger.info("JSON export completed!")
            
        elif args.build_fund_dict:
            logger.info("Building comprehensive fund dictionary")
            build_fund_dictionary(config, logger)
            logger.info("Fund dictionary building completed!")
            
        elif args.unified_csv:
            logger.info("Creating unified CSV only")
            create_unified_csv(config, logger)
            logger.info("Unified CSV creation completed!")
            
        elif args.charts_only:
            logger.info("Creating charts from existing data")
            
            trades_files = list(config.PROCESSED_DATA_DIR.glob("trades_*.csv"))
            if not trades_files:
                logger.error("No processed trade data found")
                return
            
            latest_trades_file = max(trades_files, key=lambda x: x.stat().st_mtime)
            trades_df = pd.read_csv(latest_trades_file, parse_dates=['trade_date'])
            logger.info(f"Loaded trades from {latest_trades_file}")
            
            price_path = config.PROCESSED_DATA_DIR / "stock_prices.csv"
            price_data = None
            if price_path.exists():
                price_data = pd.read_csv(price_path, index_col=0, parse_dates=True)
                logger.info(f"Loaded price data from {price_path}")
            
            analyzer = PortfolioAnalyzer(config)
            safe_price_data = price_data if price_data is not None and not price_data.empty else pd.DataFrame()
            holdings_df = analyzer.analyze_holdings(trades_df, safe_price_data)
            summary = analyzer.calculate_portfolio_summary(holdings_df)
            activity = analyzer.analyze_trading_activity(trades_df)
            performance_df = analyzer.calculate_security_performance(trades_df, safe_price_data)
            
            create_visualizations(trades_df, holdings_df, summary, activity, 
                                performance_df, price_data, config, logger)
            
        else:
            # デフォルト：既存データで解析、--downloadが指定された時のみダウンロード
            if args.download:
                logger.info("=== Market Data Download Mode ===")
            else:
                logger.info("=== Analysis Mode (using existing data) ===")
                
            forex_data = None
            if args.download:
                forex_data = update_market_data(config, logger)
            else:
                logger.info("Skipping market data download - using existing data")
            
            trades_df = load_and_process_trades(config, logger)
            if trades_df is None:
                return
            
            price_data = None
            if args.download:
                price_data = update_stock_prices(trades_df, config, logger, 
                                               use_alternative_sources=args.alternative_data)
            else:
                # 既存の株価データを読み込む
                stock_price_path = config.PROCESSED_DATA_DIR / "stock_prices.csv"
                if stock_price_path.exists():
                    price_data = pd.read_csv(stock_price_path, index_col=0, parse_dates=True)
                    logger.info(f"Loaded existing stock price data: {len(price_data)} records")
                else:
                    logger.info("No existing stock price data found - continuing without price data")
            
            holdings_df, summary, activity, performance_df = analyze_portfolio(
                trades_df, price_data, forex_data, config, logger
            )
            
            perform_eda_analysis(trades_df, config, logger)
            
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