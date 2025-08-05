#!/usr/bin/env python3
"""
Trade History Analyzer - CODES Enhanced Version

A comprehensive tool for analyzing trading history from multiple brokers,
with destructive improvements inspired by the CODES legacy system.
"""

import argparse
import logging
import pandas as pd
import numpy as np
import re
import yfinance as yf
from pathlib import Path
import sys
from datetime import datetime, timedelta
import os
from concurrent.futures import ProcessPoolExecutor
from tqdm import tqdm
import matplotlib.pyplot as plt
import seaborn as sns

# Add src to path for imports
sys.path.append(str(Path(__file__).parent / 'src'))

from config import Config
from src.utils.helpers import setup_logging, get_timestamp


def process_csv_direct(file_path, logger):
    """Process CSV file directly based on filename patterns like CODES/1concat.py with enhanced error handling"""
    file_name = file_path.name
    
    # Try multiple encodings like CODES approach
    encodings_to_try = ['shift_jis', 'utf-8', 'cp932', 'iso-2022-jp']
    
    for encoding in encodings_to_try:
        try:
            logger.debug(f"Trying encoding {encoding} for {file_name}")
            
            if 'INVST' in file_name or 'invst' in file_name.lower():
                df = pd.read_csv(file_path, encoding=encoding)
                df = df.rename(columns={
                    '約定日': 'trade_date',
                    '受渡日': 'settlement_date',
                    'ファンド名': 'security_name',
                    '取引': 'transaction_type',
                    '数量［口］': 'quantity',
                    '単価': 'price',
                    '受渡金額/(ポイント利用)[円]': 'settlement_amount',
                    '決済通貨': 'currency',
                    '口座': 'account_type'
                })
                df['security_code'] = ''
                break  # Success, exit encoding loop
            elif 'JP' in file_name or any(x in file_name.lower() for x in ['japan', 'jp', '日本']):
                df = pd.read_csv(file_path, encoding=encoding)
            df = df.rename(columns={
                '約定日': 'trade_date',
                '受渡日': 'settlement_date',
                '銘柄コード': 'security_code',
                '銘柄名': 'security_name',
                '売買区分': 'transaction_type',
                '数量［株］': 'quantity',
                '単価［円］': 'price',
                '受渡金額［円］': 'settlement_amount',
                '口座区分': 'account_type'
            })
            df['currency'] = 'JPY'
            elif 'US' in file_name or any(x in file_name.lower() for x in ['usa', 'america', 'us']):
                df = pd.read_csv(file_path, encoding=encoding)
            df = df.rename(columns={
                '約定日': 'trade_date',
                '受渡日': 'settlement_date',
                'ティッカー': 'security_code',
                '銘柄名': 'security_name',
                '売買区分': 'transaction_type',
                '数量［株］': 'quantity',
                '単価［USドル］': 'price',
                '受渡金額［円］': 'settlement_amount',
                '口座': 'account_type'
            })
            df['currency'] = 'USD'
            elif 'SaveFile' in file_name:
                df = pd.read_csv(file_path, encoding=encoding, skiprows=8)
            df = df.rename(columns={
                '約定日': 'trade_date',
                '受渡日': 'settlement_date',
                '銘柄コード': 'security_code',
                '銘柄': 'security_name',
                '取引': 'transaction_type',
                '約定数量': 'quantity',
                '約定単価': 'price',
                '受渡金額/決済損益': 'settlement_amount',
                '預り': 'account_type'
            })
            df['currency'] = 'JPY'
            elif 'yakujo' in file_name.lower():
                df = pd.read_csv(file_path, encoding=encoding, skiprows=2)
            df = df.rename(columns={
                '国内約定日': 'trade_date',
                '国内受渡日': 'settlement_date',
                '銘柄名': 'security_name',
                '取引': 'transaction_type',
                '約定数量': 'quantity',
                '約定単価': 'price',
                '受渡金額': 'settlement_amount',
                '通貨': 'currency',
                '預り区分': 'account_type'
            })
            df['security_code'] = df['security_name'].str.extract(r'(\w+) / ')
            elif 'CH' in file_name or 'ch' in file_name.lower():
                # Handle China/Hong Kong files
                df = pd.read_csv(file_path, encoding=encoding)
                df = df.rename(columns={
                    '約定日': 'trade_date',
                    '受渡日': 'settlement_date',
                    'ティッカー': 'security_code',
                    '銘柄名': 'security_name',
                    '売買区分': 'transaction_type',
                    '数量［株］': 'quantity',
                    '単価［香港ドル］': 'price',
                    '受渡金額［円］': 'settlement_amount',
                    '口座': 'account_type'
                })
                df['currency'] = 'HKD'
                break
            elif 'assetbalance' in file_name.lower() or 'new_file' in file_name.lower():
                # Skip portfolio files in trade processing
                logger.info(f"Skipping portfolio file: {file_name}")
                return None
            else:
                # Try generic CSV loading
                logger.debug(f"Unknown file format: {file_name}, attempting generic load with {encoding}")
                df = pd.read_csv(file_path, encoding=encoding)
                
                # Try to map columns automatically
                df = auto_map_columns(df, file_path)
                if df is not None:
                    break
                
        except (UnicodeDecodeError, pd.errors.EmptyDataError) as e:
            logger.debug(f"Encoding {encoding} failed for {file_name}: {e}")
            continue
        except Exception as e:
            logger.warning(f"Unexpected error with encoding {encoding} for {file_name}: {e}")
            continue
    
    # If we get here, all encodings failed
    if 'df' not in locals():
        logger.error(f"Failed to read {file_name} with any encoding")
        return None
            
    df['data_source'] = file_name
    
    # Ensure required columns exist
    columns_to_select = ['trade_date', 'settlement_date', 'security_code', 'security_name', 
                         'transaction_type', 'quantity', 'price', 'settlement_amount', 
                         'currency', 'account_type', 'data_source']
    
    for col in columns_to_select:
        if col not in df.columns:
            df[col] = None
    
    logger.info(f"Successfully processed {file_name} with {len(df)} records")
    return df[columns_to_select]


def auto_map_columns(df, file_path):
    """Automatically map columns for unknown file formats"""
    if df.empty:
        return None
        
    column_mapping = {}
    
    for col in df.columns:
        col_lower = str(col).lower()
        
        # Date mappings
        if any(pattern in col_lower for pattern in ['約定日', 'trade_date', '取引日', 'date']):
            column_mapping[col] = 'trade_date'
        elif any(pattern in col_lower for pattern in ['受渡日', 'settlement_date', '決済日']):
            column_mapping[col] = 'settlement_date'
        
        # Security mappings
        elif any(pattern in col_lower for pattern in ['銘柄コード', 'security_code', 'ticker', 'ティッカー']):
            column_mapping[col] = 'security_code'
        elif any(pattern in col_lower for pattern in ['銘柄名', 'security_name', 'ファンド名', 'name']):
            column_mapping[col] = 'security_name'
        
        # Transaction mappings
        elif any(pattern in col_lower for pattern in ['取引', 'transaction', '売買']):
            column_mapping[col] = 'transaction_type'
        
        # Quantity and price mappings
        elif any(pattern in col_lower for pattern in ['数量', 'quantity', '株', '口']):
            column_mapping[col] = 'quantity'
        elif any(pattern in col_lower for pattern in ['単価', 'price', '価格']):
            column_mapping[col] = 'price'
        elif any(pattern in col_lower for pattern in ['受渡金額', 'settlement_amount', '金額', 'amount']):
            column_mapping[col] = 'settlement_amount'
        
        # Currency and account mappings
        elif any(pattern in col_lower for pattern in ['通貨', 'currency']):
            column_mapping[col] = 'currency'
        elif any(pattern in col_lower for pattern in ['口座', 'account', '預り']):
            column_mapping[col] = 'account_type'
    
    if not column_mapping:
        return None
        
    # Apply mapping
    df = df.rename(columns=column_mapping)
    
    return df


def clean_trades_data(df, logger):
    """Clean trades data using CODES/2clean.py approach with enhanced error handling"""
    logger.info("Cleaning trades data using CODES approach with enhanced error handling...")
    
    # Add row count tracking for debugging
    original_count = len(df)
    logger.info(f"Starting with {original_count} raw trades")
    
    # Standardize dates like CODES/2clean.py
    def parse_dates(date_series):
        return pd.to_datetime(date_series, errors='coerce')
    
    df['trade_date'] = parse_dates(df['trade_date'])
    df['settlement_date'] = parse_dates(df['settlement_date'])
    
    # Clean numeric columns like CODES/2clean.py with enhanced error handling
    def clean_numeric(x):
        if pd.isna(x) or x == '-' or x == '' or x is None:
            return np.nan
        if isinstance(x, str):
            # Remove more Japanese and special characters
            x = re.sub(r'[,円，、\s+]', '', x)
            # Handle negative values in parentheses (Japanese accounting style)
            if x.startswith('(') and x.endswith(')'):
                x = '-' + x[1:-1]
            match = re.search(r'-?\d+(\.\d+)?', x)
            if match:
                try:
                    return float(match.group())
                except (ValueError, OverflowError):
                    return np.nan
        try:
            return float(x)
        except (ValueError, TypeError, OverflowError):
            return np.nan
    
    numeric_columns = ['quantity', 'price', 'settlement_amount']
    for col in numeric_columns:
        if col in df.columns:
            try:
                df[col] = df[col].apply(clean_numeric)
                cleaned_count = df[col].notna().sum()
                logger.debug(f"Cleaned {col}: {cleaned_count}/{len(df)} valid values")
            except Exception as e:
                logger.warning(f"Error cleaning numeric column {col}: {e}")
                df[col] = np.nan
    
    # Standardize currency like CODES
    currency_mapping = {
        'JPY': 'JPY', '日本円': 'JPY', '円': 'JPY',
        'USD': 'USD', '米国ドル': 'USD', '米ドル': 'USD'
    }
    df['currency'] = df['currency'].map(currency_mapping).fillna('Unknown')
    
    # Standardize transaction types like CODES with more patterns
    def standardize_transaction_type(transaction_type):
        if pd.isna(transaction_type) or transaction_type == '' or transaction_type is None:
            return 'unknown'
        
        original_type = str(transaction_type).strip()
        lower_type = original_type.lower()
        
        # Buy patterns (expanded)
        buy_patterns = ['買', 'buy', '買付', '再投資', '入庫', '購入', 'purchase', 'acquire']
        if any(word in lower_type for word in buy_patterns):
            return 'buy'
        
        # Sell patterns (expanded) 
        sell_patterns = ['売', 'sell', '解約', '売却', '売付', 'dispose', 'redemption']
        if any(word in lower_type for word in sell_patterns):
            return 'sell'
        
        # Other transaction types
        if any(word in lower_type for word in ['配当', 'dividend']):
            return 'dividend'
        elif any(word in lower_type for word in ['分割', 'split']):
            return 'split'
        
        return original_type
    
    df['transaction_type'] = df['transaction_type'].apply(standardize_transaction_type)
    
    # Sort by trade date like CODES, with error handling
    try:
        df = df.sort_values('trade_date')
    except Exception as e:
        logger.warning(f"Error sorting by trade_date: {e}, skipping sort")
    
    # Filter out completely empty rows
    df = df.dropna(how='all')
    
    final_count = len(df)
    logger.info(f"Cleaned {final_count} trades using CODES approach (reduced from {original_count})")
    
    # Log data quality metrics
    if final_count > 0:
        valid_dates = df['trade_date'].notna().sum()
        valid_amounts = df['settlement_amount'].notna().sum() 
        logger.info(f"Data quality: {valid_dates}/{final_count} valid dates, {valid_amounts}/{final_count} valid amounts")
    
    return df


def download_forex_data_direct(config, logger):
    """Download forex data directly like CODES/0fx.py"""
    try:
        # Currency pairs like CODES/0fx.py
        pairs = ['USDJPY=X', 'EURJPY=X']
        start_date = '2018-01-01'
        end_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        # Create DataFrame like CODES approach
        df = pd.DataFrame()
        
        for pair in pairs:
            try:
                data = yf.download(pair, start=start_date, end=end_date)
                if not data.empty:
                    # Handle timezone like CODES
                    if not data.index.tz:
                        data.index = data.index.tz_localize('UTC')
                    df[pair] = data['Close']
                    logger.info(f"Downloaded {pair}: {len(data)} records")
            except Exception as e:
                logger.warning(f"Error downloading {pair}: {e}")
        
        if not df.empty:
            # Clean column names like CODES
            df.columns = [col.replace('=X', '') for col in df.columns]
            logger.info(f"Total forex data points: {len(df)}")
        
        return df
        
    except Exception as e:
        logger.error(f"Error in direct forex download: {e}")
        return None


def perform_eda_analysis(trades_df, config, logger):
    """Perform comprehensive EDA like CODES/3eda.py"""
    logger.info("=== Performing EDA Analysis (CODES-style) ===")
    
    try:        
        # Create EDA output directory
        eda_dir = config.OUTPUT_DIR / "eda_analysis"
        eda_dir.mkdir(exist_ok=True)
        
        # Basic statistics like CODES/3eda.py
        logger.info("Dataset information:")
        logger.info(f"Total trades: {len(trades_df)}")
        logger.info(f"Date range: {trades_df['trade_date'].min()} to {trades_df['trade_date'].max()}")
        
        # Save summary statistics
        summary_stats = trades_df.describe()
        summary_stats.to_csv(eda_dir / 'summary_statistics.csv')
        
        # Missing values analysis
        missing_values = trades_df.isnull().sum()
        missing_values.to_csv(eda_dir / 'missing_values.csv')
        
        # Transaction type distribution
        plt.figure(figsize=(10, 6))
        trades_df['transaction_type'].value_counts().plot(kind='bar')
        plt.title('Distribution of Transaction Types')
        plt.tight_layout()
        plt.savefig(eda_dir / 'transaction_types_distribution.png')
        plt.close()
        
        # Currency distribution
        plt.figure(figsize=(8, 8))
        trades_df['currency'].value_counts().plot(kind='pie', autopct='%1.1f%%')
        plt.title('Distribution of Currencies')
        plt.tight_layout()
        plt.savefig(eda_dir / 'currency_distribution.png')
        plt.close()
        
        # Monthly trading activity
        trades_df['month'] = trades_df['trade_date'].dt.to_period('M')
        monthly_counts = trades_df.groupby('month').size()
        
        plt.figure(figsize=(12, 6))
        monthly_counts.plot(kind='bar')
        plt.title('Monthly Transaction Counts')
        plt.xlabel('Month')
        plt.ylabel('Transaction Count')
        plt.tight_layout()
        plt.savefig(eda_dir / 'monthly_transaction_counts.png')
        plt.close()
        
        # Calculate total investment amount like CODES
        total_investment = trades_df['settlement_amount'].sum()
        logger.info(f"Total Investment Amount: {total_investment:,.0f}")
        
        # Save total investment amount
        with open(eda_dir / 'total_investment_amount.txt', 'w') as f:
            f.write(f"Total Investment Amount: {total_investment:,.0f}")
        
        logger.info(f"EDA analysis completed. Results saved to {eda_dir}")
        return eda_dir
        
    except Exception as e:
        logger.error(f"Error in EDA analysis: {e}")
        return None


def generate_security_chart_codes_style(args):
    """Generate individual security chart using CODES/4chart.py approach"""
    trades_df, price_data, security_code, output_folder = args
    
    try:
        # Filter trades for this security
        security_trades = trades_df[trades_df['security_code'] == security_code]
        
        # Get price data for this security
        adj_close = price_data.get(security_code)
        
        if adj_close is None or adj_close.empty:
            return
        
        # Create chart like CODES/4chart.py
        fig, ax1 = plt.subplots(figsize=(14, 8))
        ax1.grid(True, linestyle='--', alpha=0.7)
        ax1.plot(adj_close.index, adj_close.values, color='tab:blue', label='Adjusted Close', linewidth=2)
        ax1.set_xlabel('Date', fontsize=12)
        ax1.set_ylabel('Adjusted Close Price', color='tab:blue', fontsize=12)
        
        ax2 = ax1.twinx()
        ax2.set_ylabel('Trade Amount (JPY)', color='tab:orange', fontsize=12)
        
        # Plot trades with size proportional to amount
        if not security_trades.empty:
            max_amount = security_trades['settlement_amount'].max()
            for _, trade in security_trades.iterrows():
                color = 'g' if trade['transaction_type'].lower() == 'buy' else 'r'
                marker = '^' if trade['transaction_type'].lower() == 'buy' else 'v'
                size = 50 * (trade['settlement_amount'] / max_amount) + 20 if max_amount > 0 else 50
                ax2.scatter(trade['trade_date'], trade['settlement_amount'], 
                           c=color, marker=marker, s=size, alpha=0.7, zorder=5)
                ax1.axvline(x=trade['trade_date'], color='gray', alpha=0.3, linestyle='--', zorder=1)
        
        plt.title(f'Price and Trades for {security_code}', fontsize=16)
        fig.autofmt_xdate()
        
        # Add legend
        ax2.scatter([], [], c='g', marker='^', s=100, alpha=0.7, label='Buy Trade')
        ax2.scatter([], [], c='r', marker='v', s=100, alpha=0.7, label='Sell Trade')
        ax1.legend(loc='upper left', fontsize=10).get_frame().set_alpha(0.7)
        
        plt.tight_layout()
        output_file = output_folder / f'{security_code}.png'
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()
        
    except Exception as e:
        print(f"Error generating chart for {security_code}: {e}")


def load_and_process_trades_codes_style(config, logger):
    """Load and process trading data using CODES-style direct processing"""
    logger.info("=== Loading Trading Data (CODES-style) ===")
    
    # Direct file processing approach inspired by CODES/1concat.py
    all_data = []
    raw_data_dir = config.RAW_DATA_DIR
    
    if not raw_data_dir.exists():
        logger.error(f"Raw data directory not found: {raw_data_dir}")
        return None
    
    # Process files directly like CODES/1concat.py
    for file_path in raw_data_dir.rglob("*.csv"):
        logger.info(f"Processing {file_path}...")
        try:
            df = process_csv_direct(file_path, logger)
            if df is not None:
                all_data.append(df)
        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")
            continue
    
    if not all_data:
        logger.error("No trading data found. Please place your CSV files in the data/raw directory.")
        return None
    
    # Combine all data like CODES approach
    trades_df = pd.concat(all_data, ignore_index=True)
    
    # Clean and standardize data like CODES/2clean.py
    trades_df = clean_trades_data(trades_df, logger)
    
    # Save processed trades
    trades_path = config.PROCESSED_DATA_DIR / f"trades_{get_timestamp()}.csv"
    trades_df.to_csv(trades_path, index=False)
    logger.info(f"Processed trades saved to {trades_path}")
    
    return trades_df


def update_market_data_codes_style(config, logger):
    """Update forex and stock price data using CODES/0fx.py approach"""
    logger.info("=== Updating Market Data (CODES-style Direct Download) ===")
    
    # Direct forex download like CODES/0fx.py
    forex_data = download_forex_data_direct(config, logger)
    
    if forex_data is not None and not forex_data.empty:
        logger.info(f"Forex data updated: {len(forex_data)} records")
        # Save like CODES approach
        forex_path = config.PROCESSED_DATA_DIR / "forex_data.csv"
        forex_data.to_csv(forex_path)
        logger.info(f"Forex data saved to {forex_path}")
    else:
        logger.warning("No forex data available")
        forex_data = None
    
    return forex_data


def create_charts_codes_style(trades_df, price_data, config, logger):
    """Create charts using CODES/4chart.py multi-processing approach"""
    logger.info("=== Creating Charts (CODES-style Multi-processing) ===")
    
    charts_dir = config.OUTPUT_DIR / "charts"
    charts_dir.mkdir(exist_ok=True)
    
    if price_data is not None and not price_data.empty and not trades_df.empty:
        # Get unique security codes from trades
        security_codes = trades_df['security_code'].dropna().unique()
        
        logger.info(f"Generating {len(security_codes)} individual charts using CODES approach...")
        
        # Use multi-processing like CODES/4chart.py
        with ProcessPoolExecutor() as executor:
            args_list = [(trades_df, price_data, code, charts_dir) for code in security_codes]
            list(tqdm(executor.map(generate_security_chart_codes_style, args_list), 
                     total=len(security_codes), desc="Generating charts"))
    
    logger.info(f"Charts saved to {charts_dir}")


def setup_environment():
    """Set up the environment and configuration"""
    config = Config()
    config.ensure_directories()
    logger = setup_logging()
    return config, logger


def print_summary_codes_style(trades_df, logger):
    """Print summary using CODES-style approach"""
    print("\n" + "="*60)
    print("TRADE HISTORY SUMMARY (CODES Enhanced)")
    print("="*60)
    
    if not trades_df.empty:
        total_trades = len(trades_df)
        total_amount = trades_df['settlement_amount'].sum()
        buy_trades = len(trades_df[trades_df['transaction_type'] == 'buy'])
        sell_trades = len(trades_df[trades_df['transaction_type'] == 'sell'])
        unique_securities = trades_df['security_code'].nunique()
        
        print(f"Total Trades: {total_trades}")
        print(f"Buy Trades: {buy_trades}")
        print(f"Sell Trades: {sell_trades}")
        print(f"Total Amount: ¥{total_amount:,.0f}")
        print(f"Unique Securities: {unique_securities}")
        print(f"Date Range: {trades_df['trade_date'].min().date()} to {trades_df['trade_date'].max().date()}")
    
    print("="*60)


def main():
    """Main function with CODES-style enhancements"""
    parser = argparse.ArgumentParser(
        description="Analyze trading history with CODES-style enhancements"
    )
    parser.add_argument(
        "--skip-download", 
        action="store_true", 
        help="Skip downloading market data and use existing files"
    )
    parser.add_argument(
        "--codes-pipeline",
        action="store_true",
        help="Use full CODES-style processing pipeline"
    )
    
    args = parser.parse_args()
    
    # Setup
    config, logger = setup_environment()
    logger.info("Starting Trade History Analysis (CODES Enhanced)")
    
    try:
        # CODES-style processing pipeline
        if args.codes_pipeline:
            logger.info("Running full CODES-style pipeline...")
            
            # Step 1: Download forex data (like CODES/0fx.py)
            if not args.skip_download:
                forex_data = update_market_data_codes_style(config, logger)
            
            # Step 2: Process and concatenate CSV files (like CODES/1concat.py + 2clean.py)
            trades_df = load_and_process_trades_codes_style(config, logger)
            if trades_df is None:
                return
            
            # Step 3: Perform EDA (like CODES/3eda.py)
            perform_eda_analysis(trades_df, config, logger)
            
            # Step 4: Generate charts (like CODES/4chart.py)
            # For now, we'll skip price data integration for simplicity
            # create_charts_codes_style(trades_df, None, config, logger)
            
            # Print summary
            print_summary_codes_style(trades_df, logger)
            
        else:
            # Use existing main.py logic but with CODES enhancements
            from src.data.loaders import DataLoader
            loader = DataLoader(config)
            trades_df = loader.load_all_broker_data(config.RAW_DATA_DIR)
            
            if not trades_df.empty:
                # Add some CODES-style cleaning
                trades_df = clean_trades_data(trades_df, logger)
                perform_eda_analysis(trades_df, config, logger)
                print_summary_codes_style(trades_df, logger)
        
        logger.info("Analysis completed successfully!")
        print(f"\nResults saved to: {config.OUTPUT_DIR}")
        
    except Exception as e:
        logger.error(f"Error during analysis: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()