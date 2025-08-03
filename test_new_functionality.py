#!/usr/bin/env python3
"""
Test script for the new JSON conversion and alternative data fetching functionality.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent / 'src'))

from config import Config
from src.market.data_converter import DataConverter
from src.market.alternative_data import AlternativeDataFetcher
from src.utils.helpers import setup_logging
import json

def main():
    """Test the new functionality."""
    # Setup
    config = Config()
    logger = setup_logging()
    logger.info("Testing new JSON conversion and alternative data functionality")
    
    # Initialize converters
    converter = DataConverter(config)
    data_fetcher = AlternativeDataFetcher(config)
    
    try:
        # Step 1: Convert latest trades and portfolio data to JSON
        logger.info("=== Step 1: Converting CSV data to JSON ===")
        
        processed_data_dir = config.PROCESSED_DATA_DIR
        output_dir = config.OUTPUT_DIR / "json_data"
        
        result_paths = converter.convert_latest_data_to_json(processed_data_dir, output_dir)
        
        if result_paths:
            logger.info(f"JSON conversion successful. Created files:")
            for file_type, path in result_paths.items():
                logger.info(f"  {file_type}: {path}")
        else:
            logger.error("No JSON files were created")
            return
        
        # Step 2: Load and display ticker codes
        logger.info("=== Step 2: Extracting Ticker Codes ===")
        
        if 'tickers' in result_paths:
            with open(result_paths['tickers'], 'r', encoding='utf-8') as f:
                ticker_data = json.load(f)
            
            ticker_codes = ticker_data['ticker_codes']
            logger.info(f"Found {len(ticker_codes)} ticker codes: {ticker_codes}")
        else:
            logger.error("No ticker codes file found")
            return
        
        # Step 3: Test historical data fetching (limit to first few for testing)
        logger.info("=== Step 3: Testing Historical Data Fetching ===")
        
        # Limit to first 3 ticker codes for testing to avoid rate limits
        test_symbols = ticker_codes[:3]
        logger.info(f"Testing with symbols: {test_symbols}")
        
        # Set date range (last 1 year for testing)
        from datetime import datetime, timedelta
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)
        
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')
        
        logger.info(f"Fetching data from {start_date_str} to {end_date_str}")
        
        # Fetch historical data
        historical_data = data_fetcher.fetch_multiple_symbols(
            symbols=test_symbols,
            start_date=start_date_str,
            end_date=end_date_str,
            sources=['stooq', 'yahoo'],  # Skip alpha_vantage for now (no API key)
            delay_seconds=2.0,
            max_symbols=3  # Limit for testing
        )
        
        # Step 4: Save historical data
        if historical_data:
            logger.info("=== Step 4: Saving Historical Data ===")
            
            historical_output_dir = config.OUTPUT_DIR / "historical_data"
            metadata_path = data_fetcher.save_historical_data(historical_data, historical_output_dir)
            
            logger.info(f"Historical data saved. Metadata: {metadata_path}")
            
            # Display summary
            logger.info("=== Summary ===")
            logger.info(f"Successfully fetched data for {len(historical_data)} symbols:")
            for symbol, df in historical_data.items():
                if not df.empty:
                    logger.info(f"  {symbol}: {len(df)} records from {df.index.min()} to {df.index.max()}")
        else:
            logger.warning("No historical data was successfully fetched")
        
        # Step 5: Display sample JSON data
        logger.info("=== Step 5: Sample JSON Data ===")
        
        if 'trades' in result_paths:
            with open(result_paths['trades'], 'r', encoding='utf-8') as f:
                trades_json = json.load(f)
            
            logger.info(f"Trades JSON sample:")
            logger.info(f"  Total trades: {trades_json['metadata']['total_trades']}")
            logger.info(f"  Date range: {trades_json['metadata']['date_range']}")
            logger.info(f"  Currencies: {trades_json['metadata']['currencies']}")
            
            if trades_json['trades']:
                sample_trade = trades_json['trades'][0]
                logger.info(f"  Sample trade: {sample_trade['security_code']} - {sample_trade['security_name']}")
        
        if 'portfolio' in result_paths:
            with open(result_paths['portfolio'], 'r', encoding='utf-8') as f:
                portfolio_json = json.load(f)
            
            logger.info(f"Portfolio JSON sample:")
            logger.info(f"  Total holdings: {portfolio_json['metadata']['total_holdings']}")
            logger.info(f"  Total cost: ¥{portfolio_json['metadata']['summary']['total_cost']:,.0f}")
            logger.info(f"  Total P&L: ¥{portfolio_json['metadata']['summary']['total_pnl']:,.0f}")
        
        logger.info("=== Test completed successfully! ===")
        
    except Exception as e:
        logger.error(f"Error during testing: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    main()