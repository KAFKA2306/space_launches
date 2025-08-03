"""Data loading utilities for different broker formats."""

import pandas as pd
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
        
        # Map investment fund columns
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
        df['data_source'] = f'rakuten_investment_{file_path.name}'
        
        return self._standardize_dataframe(df)
    
    def load_sbi_domestic(self, file_path: Path) -> pd.DataFrame:
        """Load SBI domestic stock data."""
        logger.info(f"Loading SBI domestic data from {file_path}")
        
        df = safe_read_csv(file_path, encoding='shift_jis', skiprows=8)
        
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
        """Load data from all brokers and combine."""
        logger.info(f"Loading data from all brokers in {raw_data_dir}")
        logger.info("Searching recursively in all subdirectories...")
        
        all_dataframes = []
        
        # Load Rakuten data - search recursively in all subdirectories
        for pattern, loader_method in [
            ('**/*JP*.csv', self.load_rakuten_jp),
            ('**/*US*.csv', self.load_rakuten_us), 
            ('**/*INVST*.csv', self.load_rakuten_investment)
        ]:
            files = list(raw_data_dir.glob(pattern))
            logger.info(f"Found {len(files)} files matching pattern '{pattern}'")
            for file_path in files:
                try:
                    logger.info(f"Loading file: {file_path}")
                    df = loader_method(file_path)
                    all_dataframes.append(df)
                    logger.info(f"Successfully loaded {len(df)} records from {file_path.name}")
                except Exception as e:
                    logger.error(f"Error loading {file_path}: {e}")
        
        # Load SBI data - search recursively in all subdirectories  
        for pattern, loader_method in [
            ('**/SaveFile*.csv', self.load_sbi_domestic),
            ('**/yakujo*.csv', self.load_sbi_foreign)
        ]:
            files = list(raw_data_dir.glob(pattern))
            logger.info(f"Found {len(files)} files matching pattern '{pattern}'")
            for file_path in files:
                try:
                    logger.info(f"Loading file: {file_path}")
                    df = loader_method(file_path)
                    all_dataframes.append(df)
                    logger.info(f"Successfully loaded {len(df)} records from {file_path.name}")
                except Exception as e:
                    logger.error(f"Error loading {file_path}: {e}")
        
        # Load Wise data - search recursively in all subdirectories
        wise_files = list(raw_data_dir.glob('**/cleaned_wise_data*.csv'))
        logger.info(f"Found {len(wise_files)} Wise files")
        for file_path in wise_files:
            try:
                logger.info(f"Loading file: {file_path}")
                df = self.load_wise_data(file_path)
                all_dataframes.append(df)
                logger.info(f"Successfully loaded {len(df)} records from {file_path.name}")
            except Exception as e:
                logger.error(f"Error loading {file_path}: {e}")
        
        if not all_dataframes:
            logger.warning("No data files found in any subdirectories")
            logger.info("Please check that your CSV files are placed in data/raw/ or its subdirectories")
            # List all CSV files found for debugging
            all_csv_files = list(raw_data_dir.glob('**/*.csv'))
            if all_csv_files:
                logger.info(f"Found {len(all_csv_files)} total CSV files:")
                for csv_file in all_csv_files:
                    logger.info(f"  - {csv_file}")
            else:
                logger.info("No CSV files found at all")
            return pd.DataFrame(columns=self.standard_columns)
        
        # Combine all dataframes
        combined_df = pd.concat(all_dataframes, ignore_index=True)
        combined_df = combined_df.sort_values('trade_date').reset_index(drop=True)
        
        logger.info(f"Successfully loaded {len(combined_df)} total records from {len(all_dataframes)} files")
        return combined_df