"""Data loading utilities for different broker formats."""

import pandas as pd
import numpy as np
import re
from pathlib import Path
import glob
import logging
from typing import List, Dict, Optional

from ..utils.helpers import safe_read_csv, standardize_date, clean_numeric, ensure_columns
from config import Config


logger = logging.getLogger(__name__)


class DataLoader:
    """Load and standardize data from different brokers."""
    
    def __init__(self, config: Config = None):
        self.config = config or Config()
        self.standard_columns = [
            'trade_date', 'settlement_date', 'security_code', 'security_name',
            'transaction_type', 'quantity', 'price', 'settlement_amount',
            'currency', 'account_type', 'data_source'
        ]
    
    def load_rakuten_jp(self, file_path: Path) -> pd.DataFrame:
        """Load Rakuten Japan stock data."""
        logger.info(f"Loading Rakuten JP data from {file_path}")
        
        df = safe_read_csv(file_path, encoding='shift_jis')
        mapping = self.config.COLUMN_MAPPINGS['rakuten_jp']
        
        df = df.rename(columns=mapping)
        df['currency'] = 'JPY'
        df['data_source'] = f'rakuten_jp_{file_path.name}'
        
        return self._standardize_dataframe(df)
    
    def load_rakuten_us(self, file_path: Path) -> pd.DataFrame:
        """Load Rakuten US stock data."""
        logger.info(f"Loading Rakuten US data from {file_path}")
        
        df = safe_read_csv(file_path, encoding='shift_jis')
        mapping = self.config.COLUMN_MAPPINGS['rakuten_us']
        
        df = df.rename(columns=mapping)
        df['currency'] = 'USD'
        df['data_source'] = f'rakuten_us_{file_path.name}'
        
        return self._standardize_dataframe(df)
    
    def load_rakuten_investment(self, file_path: Path) -> pd.DataFrame:
        """Load Rakuten investment fund data."""
        logger.info(f"Loading Rakuten investment data from {file_path}")
        
        df = safe_read_csv(file_path, encoding='shift_jis')
        mapping = self.config.COLUMN_MAPPINGS['rakuten_investment']
        
        df = df.rename(columns=mapping)
        df['security_code'] = ''
        df['currency'] = df.get('currency', 'JPY')
        df['data_source'] = f'rakuten_investment_{file_path.name}'
        
        return self._standardize_dataframe(df)
    
    def load_rakuten_ch(self, file_path: Path) -> pd.DataFrame:
        """Load Rakuten China/Hong Kong stock data."""
        logger.info(f"Loading Rakuten CH data from {file_path}")
        
        df = safe_read_csv(file_path, encoding='shift_jis')
        mapping = self.config.COLUMN_MAPPINGS['rakuten_ch']
        
        df = df.rename(columns=mapping)
        # Set default currency if not present
        if 'currency' not in df.columns:
            df['currency'] = 'HKD'
        df['data_source'] = f'rakuten_ch_{file_path.name}'
        
        return self._standardize_dataframe(df)
    
    def load_sbi_domestic(self, file_path: Path) -> pd.DataFrame:
        """Load SBI domestic stock data."""
        logger.info(f"Loading SBI domestic data from {file_path}")
        
        df = safe_read_csv(file_path, encoding='shift_jis', skiprows=8)
        mapping = self.config.COLUMN_MAPPINGS['sbi_domestic']
        
        df = df.rename(columns=mapping)
        df['currency'] = 'JPY'
        df['data_source'] = f'sbi_domestic_{file_path.name}'
        
        return self._standardize_dataframe(df)
    
    def load_sbi_foreign(self, file_path: Path) -> pd.DataFrame:
        """Load SBI foreign stock data."""
        logger.info(f"Loading SBI foreign data from {file_path}")
        
        df = safe_read_csv(file_path, encoding='shift_jis', skiprows=2)
        
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
        
        # Extract security code from security name
        df['security_code'] = df['security_name'].str.extract(r'(\w+) / ')
        df['data_source'] = f'sbi_foreign_{file_path.name}'
        
        return self._standardize_dataframe(df)
    
    def load_wise_data(self, file_path: Path) -> pd.DataFrame:
        """Load Wise forex data."""
        logger.info(f"Loading Wise data from {file_path}")
        
        df = safe_read_csv(file_path)
        
        # Wise data is already processed, just standardize
        df['data_source'] = f'wise_{file_path.name}'
        
        return self._standardize_dataframe(df)
    
    def load_portfolio_data(self, file_path: Path) -> pd.DataFrame:
        """Load portfolio/asset balance data as portfolio snapshots."""
        logger.info(f"Loading portfolio snapshot from {file_path}")
        
        try:
            # Parse based on filename pattern
            if 'assetbalance' in file_path.name.lower():
                return self._parse_assetbalance_file(file_path)
            elif 'new_file' in file_path.name.lower():
                return self._parse_portfolio_listing_file(file_path)
            else:
                logger.warning(f"Unknown portfolio file format: {file_path.name}")
                return pd.DataFrame()
                
        except Exception as e:
            logger.warning(f"Failed to load portfolio data from {file_path}: {e}")
            return pd.DataFrame()
    
    def _parse_assetbalance_file(self, file_path: Path) -> pd.DataFrame:
        """Parse assetbalance CSV file format."""
        import csv
        portfolio_data = []
        in_holdings_section = False
        
        with open(file_path, 'r', encoding='shift_jis') as file:
            reader = csv.reader(file)
            for i, fields in enumerate(reader):
                if not fields:
                    continue
                
                # Look for holdings section header
                line_content = ''.join(fields)
                
                if '保有商品詳細' in line_content or '保有商品明細' in line_content:
                    in_holdings_section = True
                    logger.debug(f"Holdings section detected at row {i}")
                    continue
                
                # Skip column header row
                if in_holdings_section and '銘柄コード・ティッカー' in line_content:
                    continue
                
                # Look for end of holdings section
                if in_holdings_section and ('参考相場レート' in line_content or '合計' in fields[0]):
                    break
                
                # Parse holdings data if we're in the right section
                if in_holdings_section and len(fields) >= 18:
                    try:
                        market = fields[0] if fields[0] else ''
                        security_code = fields[1] if fields[1] and fields[1] != '-' else ''
                        security_name = fields[2] if len(fields) > 2 else ''
                        
                        # Skip summary rows and header rows
                        if not security_code or security_code in ['銘柄コード・ティッカー', '-'] or '合計' in security_name:
                            continue
                        
                        # Skip non-security entries (like cash balances)
                        if any(keyword in security_name for keyword in ['円', 'ドル', '現金', '合計']):
                            continue
                        
                        account_type = fields[3] if len(fields) > 3 else ''
                        quantity = self._safe_numeric(fields[4]) if len(fields) > 4 else 0
                        unit = fields[5] if len(fields) > 5 else ''
                        avg_price = self._safe_numeric(fields[6]) if len(fields) > 6 else 0
                        avg_price_currency = fields[7] if len(fields) > 7 else ''
                        current_price = self._safe_numeric(fields[8]) if len(fields) > 8 else 0
                        current_price_currency = fields[9] if len(fields) > 9 else ''
                        current_value_local = self._safe_numeric(fields[14]) if len(fields) > 14 else 0
                        pnl_amount = self._safe_numeric(fields[16]) if len(fields) > 16 else 0
                        pnl_percent = self._safe_numeric(fields[17]) if len(fields) > 17 else 0
                        
                        if security_code and quantity > 0:
                            portfolio_data.append({
                                'security_code': security_code,
                                'security_name': security_name,
                                'market': market,
                                'account_type': account_type,
                                'quantity': quantity,
                                'unit': unit,
                                'avg_price': avg_price,
                                'avg_price_currency': avg_price_currency,
                                'current_price': current_price,
                                'current_price_currency': current_price_currency,
                                'current_value': current_value_local,
                                'pnl_amount': pnl_amount,
                                'pnl_percent': pnl_percent,
                                'data_source': f'portfolio_{file_path.name}',
                                'file_type': 'portfolio_holdings',
                                'snapshot_date': self._extract_date_from_filename(file_path.name)
                            })
                    except Exception as e:
                        logger.debug(f"Error parsing assetbalance line {i}: {e}")
                        continue
        
        df = pd.DataFrame(portfolio_data)
        logger.info(f"Parsed {len(df)} holdings from assetbalance file")
        return df
    
    def _parse_portfolio_listing_file(self, file_path: Path) -> pd.DataFrame:
        """Parse portfolio listing CSV file format."""
        import csv
        portfolio_data = []
        current_section = "unknown"
        
        with open(file_path, 'r', encoding='shift_jis') as file:
            reader = csv.reader(file)
            for i, fields in enumerate(reader):
                if not fields or len(fields) < 2:
                    continue
                
                # Detect section headers
                if any(keyword in fields[0] for keyword in ['ポートフォリオ', '普通', 'NISA', '投資信託']):
                    current_section = fields[0]
                    continue
                
                # Skip header rows
                if '銘柄コード' in fields[0] or '合計' in fields[0] or '評価額' in fields[0]:
                    continue
                
                # Look for holdings data (security code + name pattern)
                if len(fields) >= 8:
                    security_info = fields[0].strip()
                    
                    # Check if this looks like a security holding
                    if (any(char.isdigit() for char in security_info) and 
                        not security_info.startswith('--') and
                        security_info not in ['', '-'] and
                        '合計' not in security_info and
                        'ファンド名' not in security_info):
                        
                        try:
                            # Extract security code and name
                            if ' ' in security_info:
                                parts = security_info.split(' ', 1)
                                security_code = parts[0]
                                security_name = parts[1] if len(parts) > 1 else ''
                            else:
                                security_code = security_info
                                security_name = ''
                            
                            trade_date = fields[1] if len(fields) > 1 and fields[1] != '----/--/--' else None
                            quantity = self._safe_numeric(fields[2]) if len(fields) > 2 else 0
                            avg_price = self._safe_numeric(fields[3]) if len(fields) > 3 else 0
                            current_price = self._safe_numeric(fields[4]) if len(fields) > 4 else 0
                            pnl_amount = self._safe_numeric(fields[5]) if len(fields) > 5 else 0
                            pnl_percent = self._safe_numeric(fields[6]) if len(fields) > 6 else 0
                            current_value = self._safe_numeric(fields[9]) if len(fields) > 9 else 0
                            
                            # Only include if we have meaningful data
                            if security_code and (quantity > 0 or current_value > 0):
                                portfolio_data.append({
                                    'security_code': security_code,
                                    'security_name': security_name,
                                    'account_type': current_section,
                                    'quantity': quantity,
                                    'avg_price': avg_price,
                                    'current_price': current_price,
                                    'current_value': current_value,
                                    'pnl_amount': pnl_amount,
                                    'pnl_percent': pnl_percent,
                                    'trade_date': trade_date,
                                    'data_source': f'portfolio_{file_path.name}',
                                    'file_type': 'portfolio_holdings',
                                    'snapshot_date': self._extract_date_from_filename(file_path.name)
                                })
                        except Exception as e:
                            logger.debug(f"Error parsing New_file line {i}: {e}")
                            continue
        
        df = pd.DataFrame(portfolio_data)
        logger.info(f"Parsed {len(df)} holdings from portfolio listing file")
        return df
    
    def _safe_numeric(self, value: str) -> float:
        """Safely convert string to numeric value."""
        if not value or value in ['-', '--', '']:
            return 0
        
        # Remove common formatting
        value = str(value).replace(',', '').replace('+', '').replace('¥', '').replace('円', '')
        
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0
    
    def _extract_date_from_filename(self, filename: str) -> str:
        """Extract date from filename."""
        import re
        date_match = re.search(r'(\d{8})', filename)
        if date_match:
            date_str = date_match.group(1)
            return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        return ""
    
    def detect_file_type(self, file_path: Path) -> str:
        """Detect the file type based on filename patterns."""
        filename = file_path.name.lower()
        
        # Trading history patterns
        if 'jp' in filename and 'tradehistory' in filename:
            return 'rakuten_jp'
        elif 'us' in filename and 'tradehistory' in filename:
            return 'rakuten_us'
        elif 'ch' in filename and 'tradehistory' in filename:
            return 'rakuten_ch'
        elif 'invst' in filename and 'tradehistory' in filename:
            return 'rakuten_investment'
        elif 'savefile' in filename:
            return 'sbi_domestic'
        elif 'yakujo' in filename:
            return 'sbi_foreign'
        elif 'wise' in filename:
            return 'wise'
        elif 'assetbalance' in filename or 'new_file' in filename:
            return 'portfolio'
        else:
            return 'unknown'
    
    def _standardize_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Standardize dataframe format."""
        # Ensure all required columns exist
        df = ensure_columns(df, self.standard_columns)
        
        # Standardize dates
        df['trade_date'] = df['trade_date'].apply(standardize_date)
        df['settlement_date'] = df['settlement_date'].apply(standardize_date)
        
        # Clean numeric columns
        numeric_columns = ['quantity', 'price', 'settlement_amount']
        for col in numeric_columns:
            df[col] = df[col].apply(clean_numeric)
        
        # Standardize transaction types
        df['transaction_type'] = df['transaction_type'].apply(
            lambda x: self._standardize_transaction_type(x)
        )
        
        # Standardize currency
        df['currency'] = df['currency'].apply(
            lambda x: self._standardize_currency(x)
        )
        
        return df
    
    def _standardize_transaction_type(self, transaction_type):
        """Standardize transaction type."""
        if pd.isna(transaction_type):
            return 'unknown'
        
        original_type = str(transaction_type).lower().strip()
        
        for standard_type, variations in self.config.TRANSACTION_TYPE_MAPPINGS.items():
            if any(variation in original_type for variation in variations):
                return standard_type
        
        return original_type
    
    def _standardize_currency(self, currency):
        """Standardize currency."""
        if pd.isna(currency):
            return 'Unknown'
        
        original_currency = str(currency).strip()
        
        for standard_currency, variations in self.config.CURRENCY_MAPPINGS.items():
            if original_currency in variations:
                return standard_currency
        
        return original_currency
    
    def load_all_broker_data(self, raw_data_dir: Path) -> pd.DataFrame:
        """Load data from all brokers using CODES-enhanced approach for better performance."""
        logger.info(f"Loading data from all brokers in {raw_data_dir} (CODES-enhanced)")
        logger.info("Using direct file processing approach inspired by CODES/1concat.py...")
        
        all_dataframes = []
        portfolio_dataframes = []
        
        # Get all CSV files recursively
        all_csv_files = list(raw_data_dir.glob('**/*.csv'))
        logger.info(f"Found {len(all_csv_files)} total CSV files")
        
        # Mapping of file types to loader methods
        loader_methods = {
            'rakuten_jp': self.load_rakuten_jp,
            'rakuten_us': self.load_rakuten_us,
            'rakuten_ch': self.load_rakuten_ch,
            'rakuten_investment': self.load_rakuten_investment,
            'sbi_domestic': self.load_sbi_domestic,
            'sbi_foreign': self.load_sbi_foreign,
            'wise': self.load_wise_data,
            'portfolio': self.load_portfolio_data
        }
        
        # Process each file with CODES-style direct approach
        for file_path in all_csv_files:
            # Skip Zone.Identifier files
            if file_path.name.endswith(':Zone.Identifier'):
                continue
                
            file_type = self.detect_file_type(file_path)
            logger.info(f"Detected file type '{file_type}' for {file_path.name}")
            
            # Use CODES-style direct processing for better error handling
            if file_type == 'unknown':
                logger.info(f"Unknown file type for {file_path.name}, trying CODES-style direct processing")
                try:
                    df = self._process_unknown_file_codes_style(file_path)
                    if df is not None and not df.empty:
                        all_dataframes.append(df)
                        logger.info(f"Successfully loaded {len(df)} records using CODES approach")
                    else:
                        logger.warning(f"Failed to process {file_path.name} with CODES approach")
                except Exception as e:
                    logger.error(f"CODES-style processing failed for {file_path.name}: {e}")
                continue
            
            if file_type not in loader_methods:
                logger.warning(f"No loader method for file type '{file_type}', skipping")
                continue
            
            try:
                logger.info(f"Loading file: {file_path}")
                df = loader_methods[file_type](file_path)
                
                if file_type == 'portfolio':
                    portfolio_dataframes.append(df)
                    logger.info(f"Successfully loaded {len(df)} portfolio records from {file_path.name}")
                else:
                    all_dataframes.append(df)
                    logger.info(f"Successfully loaded {len(df)} trading records from {file_path.name}")
                    
            except Exception as e:
                logger.error(f"Error loading {file_path}: {e}")
                # Try CODES-style fallback
                try:
                    logger.info(f"Attempting CODES-style fallback for {file_path.name}")
                    df = self._process_unknown_file_codes_style(file_path)
                    if df is not None and not df.empty:
                        all_dataframes.append(df)
                        logger.info(f"Successfully loaded {len(df)} records using CODES fallback")
                except Exception as fallback_error:
                    logger.error(f"CODES-style fallback also failed: {fallback_error}")
        
        # Handle trading data
        if not all_dataframes:
            logger.warning("No trading data files found")
            trading_df = pd.DataFrame(columns=self.standard_columns)
        else:
            # Combine all trading dataframes
            trading_df = pd.concat(all_dataframes, ignore_index=True)
            trading_df = trading_df.sort_values('trade_date').reset_index(drop=True)
            logger.info(f"Successfully loaded {len(trading_df)} total trading records from {len(all_dataframes)} files")
        
        # Handle portfolio data separately 
        if portfolio_dataframes:
            portfolio_df = pd.concat(portfolio_dataframes, ignore_index=True)
            # Save portfolio data separately
            portfolio_path = self.config.PROCESSED_DATA_DIR / f"portfolio_data_{self._get_timestamp()}.csv"
            portfolio_df.to_csv(portfolio_path, index=False)
            logger.info(f"Portfolio data saved to {portfolio_path}")
        
        # Log detailed statistics for trading data
        if not trading_df.empty:
            logger.info(f"Combined trading data columns: {list(trading_df.columns)}")
            logger.info(f"Trading data date range: {trading_df['trade_date'].min()} to {trading_df['trade_date'].max()}")
            
            # Log data source distribution
            if 'data_source' in trading_df.columns:
                source_counts = trading_df['data_source'].value_counts()
                logger.info(f"Records per data source: {source_counts.to_dict()}")
            
            # Log transaction type distribution
            if 'transaction_type' in trading_df.columns:
                transaction_counts = trading_df['transaction_type'].value_counts()
                logger.info(f"Transaction types: {transaction_counts.to_dict()}")
            
            # Log currency distribution
            if 'currency' in trading_df.columns:
                currency_counts = trading_df['currency'].value_counts()
                logger.info(f"Currencies: {currency_counts.to_dict()}")
            
            # Log sample of the data
            logger.info("Sample of loaded trading data:")
            logger.info(f"\n{trading_df[['trade_date', 'security_name', 'transaction_type', 'quantity', 'currency']].head()}")
        
        return trading_df
    
    def _process_unknown_file_codes_style(self, file_path: Path) -> pd.DataFrame:
        """Process unknown file type using CODES-style approach"""
        file_name = file_path.name.lower()
        
        try:
            # Try different encodings and skip rows like CODES approach
            encodings_to_try = ['shift_jis', 'utf-8', 'cp932']
            skip_rows_options = [0, 1, 2, 5, 8]
            
            for encoding in encodings_to_try:
                for skip_rows in skip_rows_options:
                    try:
                        df = pd.read_csv(file_path, encoding=encoding, skiprows=skip_rows)
                        
                        # Check if this looks like trading data
                        if self._looks_like_trading_data(df):
                            logger.info(f"Successfully read {file_path.name} with encoding={encoding}, skiprows={skip_rows}")
                            
                            # Apply CODES-style column standardization
                            df = self._standardize_unknown_columns(df, file_path)
                            return df
                            
                    except Exception:
                        continue
            
            logger.warning(f"Could not process {file_path.name} with any encoding/skip combination")
            return None
            
        except Exception as e:
            logger.error(f"Error in CODES-style processing of {file_path.name}: {e}")
            return None
    
    def _looks_like_trading_data(self, df: pd.DataFrame) -> bool:
        """Check if DataFrame looks like trading data"""
        if df.empty or len(df.columns) < 5:
            return False
        
        # Look for common trading data patterns
        column_text = ' '.join(df.columns.astype(str).str.lower())
        trading_indicators = [
            '約定', '受渡', '銘柄', '数量', '単価', '金額', 'trade', 'date', 'security', 
            'quantity', 'price', 'amount', 'ticker', 'symbol'
        ]
        
        return any(indicator in column_text for indicator in trading_indicators)
    
    def _standardize_unknown_columns(self, df: pd.DataFrame, file_path: Path) -> pd.DataFrame:
        """Standardize columns for unknown file format using CODES approach"""
        # Create mapping based on common patterns
        column_mapping = {}
        
        for col in df.columns:
            col_lower = str(col).lower()
            
            # Date mappings
            if any(pattern in col_lower for pattern in ['約定日', 'trade_date', '取引日']):
                column_mapping[col] = 'trade_date'
            elif any(pattern in col_lower for pattern in ['受渡日', 'settlement_date', '決済日']):
                column_mapping[col] = 'settlement_date'
            
            # Security mappings
            elif any(pattern in col_lower for pattern in ['銘柄コード', 'security_code', 'ticker', 'ティッカー']):
                column_mapping[col] = 'security_code'
            elif any(pattern in col_lower for pattern in ['銘柄名', 'security_name', 'ファンド名']):
                column_mapping[col] = 'security_name'
            
            # Transaction mappings
            elif any(pattern in col_lower for pattern in ['取引', 'transaction', '売買']):
                column_mapping[col] = 'transaction_type'
            
            # Quantity and price mappings
            elif any(pattern in col_lower for pattern in ['数量', 'quantity', '株', '口']):
                column_mapping[col] = 'quantity'
            elif any(pattern in col_lower for pattern in ['単価', 'price', '価格']):
                column_mapping[col] = 'price'
            elif any(pattern in col_lower for pattern in ['受渡金額', 'settlement_amount', '金額']):
                column_mapping[col] = 'settlement_amount'
            
            # Currency and account mappings
            elif any(pattern in col_lower for pattern in ['通貨', 'currency']):
                column_mapping[col] = 'currency'
            elif any(pattern in col_lower for pattern in ['口座', 'account', '預り']):
                column_mapping[col] = 'account_type'
        
        # Apply mapping
        df = df.rename(columns=column_mapping)
        
        # Add missing columns with defaults
        df['data_source'] = file_path.name
        
        # Ensure standard columns exist
        for col in self.standard_columns:
            if col not in df.columns:
                df[col] = None
        
        # Apply CODES-style data cleaning
        df = self._apply_codes_style_cleaning(df)
        
        return df[self.standard_columns]
    
    def _apply_codes_style_cleaning(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply CODES-style data cleaning"""
        # Clean numeric columns like CODES/2clean.py
        def clean_numeric_codes_style(x):
            if pd.isna(x) or x == '-':
                return np.nan
            if isinstance(x, str):
                x = re.sub(r'[,円]', '', str(x))
                match = re.search(r'-?\d+(\.\d+)?', x)
                if match:
                    return float(match.group())
            try:
                return float(x)
            except (ValueError, TypeError):
                return np.nan
        
        # Apply to numeric columns
        numeric_columns = ['quantity', 'price', 'settlement_amount']
        for col in numeric_columns:
            if col in df.columns:
                df[col] = df[col].apply(clean_numeric_codes_style)
        
        # Standardize transaction types like CODES
        def standardize_transaction_type_codes(transaction_type):
            if pd.isna(transaction_type):
                return 'unknown'
            
            original_type = str(transaction_type)
            lower_type = original_type.lower()
            
            if any(word in lower_type for word in ['買', 'buy', '買付', '再投資','入庫']):
                return 'buy'
            elif any(word in lower_type for word in ['売', 'sell', '解約']):
                return 'sell'
            else:
                return original_type
        
        if 'transaction_type' in df.columns:
            df['transaction_type'] = df['transaction_type'].apply(standardize_transaction_type_codes)
        
        return df
    
    def _get_timestamp(self) -> str:
        """Get current timestamp for file naming."""
        from datetime import datetime
        return datetime.now().strftime("%Y%m%d_%H%M%S")