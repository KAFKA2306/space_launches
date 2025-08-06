#!/usr/bin/env python3

import pandas as pd
import numpy as np
from pathlib import Path
import re
from datetime import datetime
import logging
from ..utils.helpers import standardize_date, clean_numeric
from config import Config


class DataLoader:
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.all_data = []
        
    def _finalize_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        df = df.copy()
        df.loc[:, "trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce")
        df = df.dropna(subset=["trade_date"])
        if not df.empty:
            df = df.sort_values("trade_date").reset_index(drop=True)
        return df

    def detect_file_type(self, filename):
        filename = filename.lower()
        
        if 'tradehistory' in filename:
            if '(jp)' in filename:
                return 'rakuten_jp'
            elif '(us)' in filename:
                return 'rakuten_us'
            elif '(invst)' in filename:
                return 'rakuten_investment'
            elif '(ch)' in filename:
                return 'rakuten_ch'
        elif 'savefile' in filename:
            return 'sbi_domestic'
        elif 'yakujo' in filename:
            return 'sbi_foreign'
        elif 'wise' in filename:
            return 'wise'
        elif 'assetbalance' in filename or 'new_file' in filename:
            return 'portfolio'
        
        return 'unknown'

    def _standardize_columns(self, df, source_file):
        if df.empty:
            return df
            
        df = df.copy()
        df.loc[:, 'trade_date'] = df['trade_date'].apply(standardize_date)
        df.loc[:, 'settlement_date'] = df['settlement_date'].apply(standardize_date)
        
        numeric_columns = ['quantity', 'price', 'settlement_amount']
        for col in numeric_columns:
            if col in df.columns:
                df.loc[:, col] = df[col].apply(clean_numeric)
        
        if 'transaction_type' in df.columns:
            df.loc[:, 'transaction_type'] = df['transaction_type'].apply(
                lambda x: str(x).strip().lower() if pd.notna(x) else 'unknown'
            )
        
        if 'currency' in df.columns:
            df.loc[:, 'currency'] = df['currency'].apply(
                lambda x: str(x).strip().upper() if pd.notna(x) else 'JPY'
            )
        
        df.loc[:, 'data_source'] = source_file
        
        return df

    def load_rakuten_jp_data(self, file_path):
        self.logger.info(f"Loading Rakuten JP data from {file_path}")
        
        try:
            df = pd.read_csv(file_path, encoding='shift_jis')
        except:
            df = pd.read_csv(file_path, encoding='utf-8')
        
        if df.empty:
            return df
        
        df = df.rename(columns=self.config.COLUMN_MAPPINGS.get('rakuten_jp', {}))
        df['currency'] = 'JPY'
        df = self._standardize_columns(df, file_path.name)
        
        self.logger.info(f"Successfully loaded {len(df)} trading records from {file_path.name}")
        return df

    def load_rakuten_us_data(self, file_path):
        self.logger.info(f"Loading Rakuten US data from {file_path}")
        
        try:
            df = pd.read_csv(file_path, encoding='shift_jis')
        except:
            df = pd.read_csv(file_path, encoding='utf-8')
        
        if df.empty:
            return df
        
        df = df.rename(columns=self.config.COLUMN_MAPPINGS.get('rakuten_us', {}))
        df['currency'] = 'USD'
        df = self._standardize_columns(df, file_path.name)
        
        self.logger.info(f"Successfully loaded {len(df)} trading records from {file_path.name}")
        return df

    def load_rakuten_investment_data(self, file_path):
        self.logger.info(f"Loading Rakuten investment data from {file_path}")
        
        try:
            df = pd.read_csv(file_path, encoding='shift_jis')
        except:
            df = pd.read_csv(file_path, encoding='utf-8')
        
        if df.empty:
            return df
        
        df = df.rename(columns=self.config.COLUMN_MAPPINGS.get('rakuten_investment', {}))
        df['currency'] = df.get('currency', 'JPY')
        df['security_code'] = ''
        df = self._standardize_columns(df, file_path.name)
        
        self.logger.info(f"Successfully loaded {len(df)} trading records from {file_path.name}")
        return df

    def load_rakuten_ch_data(self, file_path):
        self.logger.info(f"Loading Rakuten CH data from {file_path}")
        
        try:
            df = pd.read_csv(file_path, encoding='shift_jis')
        except:
            df = pd.read_csv(file_path, encoding='utf-8')
        
        if df.empty:
            return df
        
        df = df.rename(columns=self.config.COLUMN_MAPPINGS.get('rakuten_ch', {}))
        if 'currency' not in df.columns:
            df['currency'] = 'HKD'
        df = self._standardize_columns(df, file_path.name)
        
        self.logger.info(f"Successfully loaded {len(df)} trading records from {file_path.name}")
        return df

    def load_sbi_domestic_data(self, file_path):
        self.logger.info(f"Loading SBI domestic data from {file_path}")
        
        try:
            df = pd.read_csv(file_path, encoding='shift_jis', skiprows=8)
        except:
            try:
                df = pd.read_csv(file_path, encoding='utf-8', skiprows=8)
            except:
                df = pd.read_csv(file_path, encoding='shift_jis')
        
        if df.empty:
            return df
        
        df = df.rename(columns=self.config.COLUMN_MAPPINGS.get('sbi_domestic', {}))
        df['currency'] = 'JPY'
        df = self._standardize_columns(df, file_path.name)
        
        self.logger.info(f"Successfully loaded {len(df)} trading records from {file_path.name}")
        return df

    def load_sbi_foreign_data(self, file_path):
        self.logger.info(f"Loading SBI foreign data from {file_path}")
        
        try:
            df = pd.read_csv(file_path, encoding='shift_jis', skiprows=2)
        except:
            try:
                df = pd.read_csv(file_path, encoding='utf-8', skiprows=2)
            except:
                df = pd.read_csv(file_path, encoding='shift_jis')
        
        if df.empty:
            return df
        
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
        
        if 'security_name' in df.columns:
            df['security_code'] = df['security_name'].str.extract(r'([A-Z]{2,4})')
        else:
            df['security_code'] = ''
            
        df = self._standardize_columns(df, file_path.name)
        
        self.logger.info(f"Successfully loaded {len(df)} trading records from {file_path.name}")
        return df

    def load_wise_data(self, file_path):
        self.logger.info(f"Loading Wise data from {file_path}")
        
        try:
            df = pd.read_csv(file_path, encoding='utf-8')
        except:
            df = pd.read_csv(file_path, encoding='shift_jis')
        
        if df.empty:
            return df
        
        df = self._standardize_columns(df, file_path.name)
        
        self.logger.info(f"Successfully loaded {len(df)} trading records from {file_path.name}")
        return df

    def load_portfolio_data(self, file_path):
        self.logger.info(f"Loading portfolio snapshot from {file_path}")
        
        try:
            if 'assetbalance' in file_path.name.lower():
                return self._parse_assetbalance_file(file_path)
            elif 'new_file' in file_path.name.lower():
                return self._parse_portfolio_listing_file(file_path)
        except Exception as e:
            self.logger.warning(f"Failed to load portfolio data from {file_path}: {e}")
        
        return pd.DataFrame()

    def _parse_assetbalance_file(self, file_path):
        portfolio_data = []
        try:
            with open(file_path, 'r', encoding='shift_jis') as f:
                lines = f.readlines()
                
            in_holdings = False
            for i, line in enumerate(lines):
                if '保有商品' in line:
                    in_holdings = True
                    continue
                if in_holdings and '合計' in line:
                    break
                if in_holdings and len(line.split(',')) >= 10:
                    try:
                        fields = line.strip().split(',')
                        if len(fields) > 5 and fields[1] and fields[1] != '-':
                            portfolio_data.append({
                                'security_code': fields[1],
                                'security_name': fields[2] if len(fields) > 2 else '',
                                'quantity': float(fields[4]) if len(fields) > 4 and fields[4] else 0,
                                'data_source': file_path.name
                            })
                    except:
                        continue
                        
            df = pd.DataFrame(portfolio_data)
            self.logger.info(f"Parsed {len(df)} holdings from assetbalance file")
            return df
        except Exception as e:
            self.logger.warning(f"Error parsing assetbalance file: {e}")
            return pd.DataFrame()

    def _parse_portfolio_listing_file(self, file_path):
        portfolio_data = []
        try:
            with open(file_path, 'r', encoding='shift_jis') as f:
                lines = f.readlines()
                
            for line in lines:
                if len(line.split(',')) >= 8:
                    try:
                        fields = line.strip().split(',')
                        security_info = fields[0].strip()
                        if security_info and any(c.isdigit() for c in security_info):
                            if ' ' in security_info:
                                code, name = security_info.split(' ', 1)
                            else:
                                code, name = security_info, ''
                            
                            portfolio_data.append({
                                'security_code': code,
                                'security_name': name,
                                'quantity': float(fields[2]) if len(fields) > 2 and fields[2] else 0,
                                'data_source': file_path.name
                            })
                    except:
                        continue
                        
            df = pd.DataFrame(portfolio_data)
            self.logger.info(f"Parsed {len(df)} holdings from portfolio listing file")
            return df
        except Exception as e:
            self.logger.warning(f"Error parsing portfolio listing file: {e}")
            return pd.DataFrame()

    def _try_codes_style_processing(self, file_path):
        try:
            encodings = ['shift_jis', 'utf-8']
            skiprows_options = [0, 5]
            
            for encoding in encodings:
                for skiprows in skiprows_options:
                    try:
                        df = pd.read_csv(file_path, encoding=encoding, skiprows=skiprows)
                        if not df.empty and len(df.columns) >= 5:
                            df['data_source'] = file_path.name
                            self.logger.info(f"Successfully read {file_path.name} with encoding={encoding}, skiprows={skiprows}")
                            return df
                    except:
                        continue
                        
            return pd.DataFrame()
        except Exception as e:
            self.logger.error(f"CODES-style processing failed for {file_path}: {e}")
            return pd.DataFrame()

    def load_all_broker_data(self, data_dir):
        self.logger.info(f"Loading data from all brokers in {data_dir} (CODES-enhanced)")
        self.logger.info("Using direct file processing approach inspired by CODES/1concat.py...")
        
        all_trades_data = []
        csv_files = list(Path(data_dir).rglob("*.csv"))
        self.logger.info(f"Found {len(csv_files)} total CSV files")
        
        for csv_file in csv_files:
            try:
                file_type = self.detect_file_type(csv_file.name)
                self.logger.info(f"Detected file type '{file_type}' for {csv_file.name}")
                
                self.logger.info(f"Loading file: {csv_file}")
                
                if file_type == 'rakuten_jp':
                    df = self.load_rakuten_jp_data(csv_file)
                elif file_type == 'rakuten_us':
                    df = self.load_rakuten_us_data(csv_file)
                elif file_type == 'rakuten_investment':
                    df = self.load_rakuten_investment_data(csv_file)
                elif file_type == 'rakuten_ch':
                    df = self.load_rakuten_ch_data(csv_file)
                elif file_type == 'sbi_domestic':
                    df = self.load_sbi_domestic_data(csv_file)
                elif file_type == 'sbi_foreign':
                    df = self.load_sbi_foreign_data(csv_file)
                elif file_type == 'wise':
                    df = self.load_wise_data(csv_file)
                elif file_type == 'portfolio':
                    df = self.load_portfolio_data(csv_file)
                else:
                    self.logger.info(f"Unknown file type for {csv_file.name}, trying CODES-style direct processing")
                    df = self._try_codes_style_processing(csv_file)
                
                if df is not None and not df.empty:
                    all_trades_data.append(df)
                    
            except Exception as e:
                self.logger.error(f"Error loading {csv_file}: {e}")
                continue
        
        if not all_trades_data:
            self.logger.error("No trading data loaded successfully")
            return None
        
        combined_df = pd.concat(all_trades_data, ignore_index=True)
        self.logger.info(f"Combined data: {len(combined_df)} total records")
        
        if combined_df.empty:
            return combined_df
        
        combined_df = combined_df.copy()
        combined_df.loc[:, "trade_date"] = pd.to_datetime(combined_df["trade_date"], errors="coerce")
        combined_df = combined_df.dropna(subset=["trade_date"])
        if not combined_df.empty:
            combined_df = combined_df.sort_values("trade_date").reset_index(drop=True)
        
        return combined_df


def perform_eda_analysis(trades_df, config, logger):
    pass