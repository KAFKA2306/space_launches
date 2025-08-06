"""Data conversion utilities for converting CSV data to JSON and extracting ticker codes."""

import pandas as pd
import json
from pathlib import Path
from typing import Dict, List, Set, Optional
import logging
from datetime import datetime
import re
from .currency_converter import CurrencyConverter

logger = logging.getLogger(__name__)


class DataConverter:
    """Convert CSV data to JSON and extract ticker information."""
    
    def __init__(self, config=None):
        self.config = config
        self.comprehensive_fund_dict = self._load_comprehensive_fund_dictionary()
        self.security_mapping = self._load_security_mapping()  # Keep as fallback
        self.currency_converter = CurrencyConverter(config)
        self.fund_mappings = {}  # Track successful fund mappings
    
    def _load_security_mapping(self) -> Dict[str, str]:
        """Load security name to ticker code mapping from DIC/securitycode2.csv."""
        mapping = {}
        try:
            # Load the security mapping file
            base_dir = Path(__file__).parent.parent.parent
            mapping_file = base_dir / "DIC" / "securitycode2.csv"
            
            if mapping_file.exists():
                df = pd.read_csv(mapping_file)
                for _, row in df.iterrows():
                    security_name = str(row['security_name']).strip()
                    security_code = str(row['security_code']).strip()
                    
                    # Clean up security_code - remove commas and handle special cases
                    if security_code and security_code != 'nan':
                        # Remove leading commas and clean up
                        security_code = security_code.lstrip('，,').strip()
                        
                        # Skip if still empty or invalid after cleaning
                        if security_code and security_code != 'nan' and len(security_code) > 0:
                            mapping[security_name] = security_code
                
                logger.info(f"Loaded {len(mapping)} security name mappings")
                
                # Debug: show some sample mappings
                sample_items = list(mapping.items())[:5]
                logger.debug(f"Sample mappings: {sample_items}")
                
            else:
                logger.warning(f"Security mapping file not found: {mapping_file}")
                
        except Exception as e:
            logger.error(f"Error loading security mapping: {e}")
            
        return mapping
    
    def _load_comprehensive_fund_dictionary(self) -> Dict:
        """Load comprehensive fund dictionary from JSON file."""
        try:
            base_dir = Path(__file__).parent.parent.parent
            dict_file = base_dir / "DIC" / "comprehensive_fund_dictionary.json"
            
            if dict_file.exists():
                with open(dict_file, 'r', encoding='utf-8') as f:
                    fund_dict = json.load(f)
                
                funds_count = len(fund_dict.get('funds', {}))
                mapped_count = fund_dict.get('metadata', {}).get('mapped_funds', 0)
                logger.info(f"Loaded comprehensive fund dictionary: {funds_count} funds, {mapped_count} mapped")
                return fund_dict
            else:
                logger.warning(f"Comprehensive fund dictionary not found: {dict_file}")
                logger.info("Run: from src.market.fund_dictionary_builder import FundDictionaryBuilder; FundDictionaryBuilder().build_and_save_dictionary()")
                return {"funds": {}}
                
        except Exception as e:
            logger.error(f"Error loading comprehensive fund dictionary: {e}")
            return {"funds": {}}
    
    def _find_ticker_for_fund(self, security_name: str) -> Optional[str]:
        """Find ticker code for investment fund using comprehensive dictionary."""
        if not security_name:
            return None
            
        security_name = security_name.strip()
        
        # Search in comprehensive fund dictionary first
        ticker = self._search_comprehensive_dictionary(security_name)
        if ticker:
            logger.debug(f"Found ticker in comprehensive dictionary: '{security_name}' -> '{ticker}'")
            return ticker
        
        # Fallback to old security mapping method
        ticker = self._search_legacy_mapping(security_name)
        if ticker:
            logger.debug(f"Found ticker in legacy mapping: '{security_name}' -> '{ticker}'")
            return ticker
        
        logger.debug(f"No ticker found for fund: {security_name}")
        return None
    
    def _search_comprehensive_dictionary(self, security_name: str) -> Optional[str]:
        """Search for ticker in comprehensive fund dictionary."""
        funds = self.comprehensive_fund_dict.get('funds', {})
        
        # Direct name match
        if security_name in funds:
            fund_info = funds[security_name]
            return fund_info.get('ticker') if fund_info.get('ticker') else None
        
        # Search through aliases using regex patterns
        for fund_name, fund_info in funds.items():
            ticker = fund_info.get('ticker')
            if not ticker:
                continue
                
            aliases = fund_info.get('aliases', [])
            
            # Check aliases with regex matching
            if self._matches_any_alias(security_name, aliases):
                logger.info(f"Matched fund '{security_name}' to ticker '{ticker}' via comprehensive dictionary")
                return ticker
        
        return None
    
    def _matches_any_alias(self, target_name: str, aliases: List[str]) -> bool:
        """Check if target name matches any alias using regex patterns."""
        target_normalized = self._normalize_for_matching(target_name)
        
        for alias in aliases:
            if not alias:
                continue
                
            alias_normalized = self._normalize_for_matching(alias)
            
            # Exact match
            if target_normalized == alias_normalized:
                return True
            
            # Partial match for longer names
            if len(target_normalized) > 10 and len(alias_normalized) > 10:
                if target_normalized in alias_normalized or alias_normalized in target_normalized:
                    return True
            
            # Regex pattern matching for flexible matching
            if self._regex_pattern_match(target_normalized, alias_normalized):
                return True
        
        return False
    
    def _normalize_for_matching(self, name: str) -> str:
        """Normalize name for matching purposes."""
        if not name:
            return ""
        
        # Convert to lowercase and remove special characters
        normalized = name.lower()
        normalized = re.sub(r'[（）()＜＞<>【】\[\]・･\s]+', ' ', normalized)
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        return normalized
    
    def _regex_pattern_match(self, name1: str, name2: str) -> bool:
        """Advanced regex-based pattern matching."""
        # Extract key terms (3+ characters)
        terms1 = set(re.findall(r'\w{3,}', name1))
        terms2 = set(re.findall(r'\w{3,}', name2))
        
        # Remove common stop words
        stop_words = {
            'ファンド', 'fund', 'インデックス', 'index', 'etf', '投信',
            '株式', 'equity', 'bond', '債券', 'の', 'and', 'or'
        }
        
        terms1 = terms1 - stop_words
        terms2 = terms2 - stop_words
        
        if not terms1 or not terms2:
            return False
        
        # Calculate overlap ratio
        overlap = len(terms1 & terms2)
        min_terms = min(len(terms1), len(terms2))
        
        return min_terms > 0 and overlap / min_terms >= 0.7
    
    def _search_legacy_mapping(self, security_name: str) -> Optional[str]:
        """Search using legacy security mapping as fallback."""
        # Direct match first
        if security_name in self.security_mapping:
            return self.security_mapping[security_name]
        
        # Fuzzy matching for investment funds
        for mapped_name, ticker in self.security_mapping.items():
            if self._names_match(security_name, mapped_name):
                logger.info(f"Legacy match: '{security_name}' to ticker '{ticker}' via '{mapped_name}'")
                return ticker
        
        return None
    
    def _names_match(self, name1: str, name2: str) -> bool:
        """Check if two fund names are similar enough to be considered a match."""
        # Remove common variations and normalize
        def normalize_name(name):
            # Remove special characters and normalize spaces
            name = re.sub(r'[（）()＜＞<>【】\[\]・･]', ' ', name)
            name = re.sub(r'[　\s]+', ' ', name).strip()
            # Remove common fund suffixes/prefixes
            name = re.sub(r'(ファンド|Fund|インデックス|Index|ETF|投信)$', '', name)
            return name.lower()
        
        norm1 = normalize_name(name1)
        norm2 = normalize_name(name2)
        
        # Check for exact match after normalization
        if norm1 == norm2:
            return True
        
        # Asset class validation - prevent mismatches between different asset classes
        asset_classes = {
            'reit': ['reit', 'リート', 'j-reit', 'jreit', '不動産'],
            'gold': ['gold', 'ゴールド', '金'],
            'bond': ['bond', '債券', 'treasury', '国債'],
            'europe': ['europe', '欧州', 'european'],
            'topix': ['topix', 'トピックス'],
            'sp500': ['s&p500', 'sp500', 's&p', 'sp'],
            'nasdaq': ['nasdaq', 'ナスダック'],
            'emerging': ['emerging', '新興国'],
            'developed': ['developed', '先進国']
        }
        
        def get_asset_class(name):
            name_lower = name.lower()
            for asset_class, keywords in asset_classes.items():
                if any(keyword in name_lower for keyword in keywords):
                    return asset_class
            return None
        
        class1 = get_asset_class(norm1)
        class2 = get_asset_class(norm2)
        
        # If both have clear asset classes and they differ, don't match
        if class1 and class2 and class1 != class2:
            logger.debug(f"Asset class mismatch prevented: '{name1}' ({class1}) vs '{name2}' ({class2})")
            return False
        
        # Check if one name contains the other (for partial matches)
        if len(norm1) > 10 and len(norm2) > 10:
            if norm1 in norm2 or norm2 in norm1:
                return True
        
        # Check for key keyword matches
        keywords1 = set(norm1.split())
        keywords2 = set(norm2.split())
        
        # Remove common stop words
        stop_words = {'の', 'and', 'or', '・', '株式', '債券', '投資', '投信', 'fund', 'index', 'etf'}
        keywords1 = keywords1 - stop_words
        keywords2 = keywords2 - stop_words
        
        if len(keywords1) >= 2 and len(keywords2) >= 2:
            # If majority of keywords match (increased threshold for better precision)
            common_keywords = keywords1 & keywords2
            match_ratio = len(common_keywords) / min(len(keywords1), len(keywords2))
            return match_ratio >= 0.7  # Increased from 0.6 to 0.7 for better precision
        
        return False
        
    def trades_csv_to_json(self, trades_file_path: Path) -> Dict:
        """Convert trades CSV file to JSON format."""
        try:
            logger.info(f"Converting trades CSV to JSON: {trades_file_path}")
            
            if not trades_file_path.exists():
                raise FileNotFoundError(f"Trades file not found: {trades_file_path}")
            
            # Read CSV with proper date parsing
            df = pd.read_csv(trades_file_path, parse_dates=['trade_date', 'settlement_date'])
            
            # Convert to JSON-serializable format
            json_data = {
                "metadata": {
                    "file_path": str(trades_file_path),
                    "total_trades": len(df),
                    "date_range": {
                        "start": df['trade_date'].min().isoformat() if not df.empty else None,
                        "end": df['trade_date'].max().isoformat() if not df.empty else None
                    },
                    "currencies": df['currency'].unique().tolist() if not df.empty else [],
                    "data_sources": df['data_source'].unique().tolist() if not df.empty else [],
                    "converted_at": datetime.now().isoformat()
                },
                "trades": []
            }
            
            # Convert each trade to dictionary with unified pricing
            for _, row in df.iterrows():
                security_code = row['security_code'] if pd.notna(row['security_code']) else ""
                security_name = row['security_name'] if pd.notna(row['security_name']) else ""
                original_security_code = security_code  # Keep original for mapping tracking
                
                # If no security code but name exists, try to find ticker for investment funds
                if (pd.isna(security_code) or not str(security_code).strip()) and security_name:
                    ticker = self._find_ticker_for_fund(security_name)
                    if ticker:
                        security_code = ticker
                        self.fund_mappings[security_name] = ticker  # Track mapping
                        logger.info(f"Mapped fund '{security_name}' to ticker '{ticker}'")
                
                # Prepare trade data for currency conversion
                trade_data = {
                    'security_name': security_name,
                    'security_code': security_code,
                    'currency': row['currency'] if pd.notna(row['currency']) else 'JPY',
                    'price': float(row['price']) if pd.notna(row['price']) else 0.0,
                    'quantity': float(row['quantity']) if pd.notna(row['quantity']) else 0.0,
                    'settlement_amount': float(row['settlement_amount']) if pd.notna(row['settlement_amount']) else 0.0,
                    'trade_date': row['trade_date'] if pd.notna(row['trade_date']) else None
                }
                
                # Get unified JPY pricing
                price_jpy, amount_jpy, conversion_info = self.currency_converter.convert_to_jpy_unified_price(trade_data)
                
                trade = {
                    "trade_date": row['trade_date'].isoformat() if pd.notna(row['trade_date']) else None,
                    "settlement_date": row['settlement_date'].isoformat() if pd.notna(row['settlement_date']) else None,
                    "security_code": security_code,
                    "security_code_original": original_security_code,  # Keep original for reference
                    "security_name": security_name,
                    "transaction_type": row['transaction_type'] if pd.notna(row['transaction_type']) else "",
                    "quantity": float(row['quantity']) if pd.notna(row['quantity']) else 0.0,
                    "price": float(row['price']) if pd.notna(row['price']) else 0.0,
                    "price_jpy_unified": round(price_jpy, 4),  # Unified JPY price
                    "settlement_amount": float(row['settlement_amount']) if pd.notna(row['settlement_amount']) else 0.0,
                    "amount_jpy_unified": round(amount_jpy, 2),  # Unified JPY amount
                    "currency": self.currency_converter.normalize_currency_code(row['currency'] if pd.notna(row['currency']) else 'JPY'),
                    "account_type": row['account_type'] if pd.notna(row['account_type']) else "",
                    "data_source": row['data_source'] if pd.notna(row['data_source']) else "",
                    "conversion_info": conversion_info  # Include conversion details
                }
                json_data["trades"].append(trade)
            
            logger.info(f"Successfully converted {len(json_data['trades'])} trades to JSON")
            return json_data
            
        except Exception as e:
            logger.error(f"Error converting trades CSV to JSON: {e}")
            raise
    
    def portfolio_csv_to_json(self, portfolio_file_path: Path) -> Dict:
        """Convert portfolio CSV file to JSON format."""
        try:
            logger.info(f"Converting portfolio CSV to JSON: {portfolio_file_path}")
            
            if not portfolio_file_path.exists():
                raise FileNotFoundError(f"Portfolio file not found: {portfolio_file_path}")
            
            # Read CSV
            df = pd.read_csv(portfolio_file_path)
            
            # Calculate summary statistics
            total_cost = df['total_cost'].sum() if 'total_cost' in df.columns else 0
            total_value = df['current_value'].sum() if 'current_value' in df.columns else 0
            total_pnl = df['total_pnl'].sum() if 'total_pnl' in df.columns else 0
            
            # Convert to JSON-serializable format
            json_data = {
                "metadata": {
                    "file_path": str(portfolio_file_path),
                    "total_holdings": len(df),
                    "summary": {
                        "total_cost": float(total_cost),
                        "total_current_value": float(total_value),
                        "total_pnl": float(total_pnl),
                        "pnl_percentage": float(total_pnl / total_cost * 100) if total_cost != 0 else 0
                    },
                    "converted_at": datetime.now().isoformat()
                },
                "holdings": []
            }
            
            # Convert each holding to dictionary
            for _, row in df.iterrows():
                security_code = row['security_code'] if pd.notna(row['security_code']) else ""
                
                # If no security code but we can get security name from somewhere, try to find ticker
                # Note: portfolio CSV might not have security_name column, so this is optional
                if not security_code and 'security_name' in df.columns:
                    security_name = row['security_name'] if pd.notna(row['security_name']) else ""
                    if security_name:
                        ticker = self._find_ticker_for_fund(security_name)
                        if ticker:
                            security_code = ticker
                            logger.debug(f"Mapped portfolio fund '{security_name}' to ticker '{ticker}'")
                
                holding = {
                    "security_code": security_code,
                    "shares": float(row['shares']) if pd.notna(row['shares']) else 0.0,
                    "avg_cost_per_share": float(row['avg_cost_per_share']) if pd.notna(row['avg_cost_per_share']) else 0.0,
                    "total_cost": float(row['total_cost']) if pd.notna(row['total_cost']) else 0.0,
                    "current_price": float(row['current_price']) if pd.notna(row['current_price']) else 0.0,
                    "current_value": float(row['current_value']) if pd.notna(row['current_value']) else 0.0,
                    "unrealized_pnl": float(row['unrealized_pnl']) if pd.notna(row['unrealized_pnl']) else 0.0,
                    "realized_pnl": float(row['realized_pnl']) if pd.notna(row['realized_pnl']) else 0.0,
                    "total_pnl": float(row['total_pnl']) if pd.notna(row['total_pnl']) else 0.0,
                    "pnl_percentage": float(row['pnl_percentage']) if pd.notna(row['pnl_percentage']) else 0.0
                }
                json_data["holdings"].append(holding)
            
            logger.info(f"Successfully converted {len(json_data['holdings'])} holdings to JSON")
            return json_data
            
        except Exception as e:
            logger.error(f"Error converting portfolio CSV to JSON: {e}")
            raise
    
    def extract_ticker_codes(self, trades_json: Dict = None, portfolio_json: Dict = None, 
                            trades_file_path: Path = None, portfolio_file_path: Path = None) -> Set[str]:
        """Extract unique ticker codes from trades and portfolio data."""
        ticker_codes = set()
        fund_mappings = {}  # Track fund name to ticker mappings found
        
        try:
            # If file paths provided, convert to JSON first
            if trades_file_path and trades_file_path.exists():
                trades_json = self.trades_csv_to_json(trades_file_path)
            
            if portfolio_file_path and portfolio_file_path.exists():
                portfolio_json = self.portfolio_csv_to_json(portfolio_file_path)
            
            # Extract from trades data
            if trades_json and "trades" in trades_json:
                for trade in trades_json["trades"]:
                    code = trade.get("security_code", "").strip()
                    security_name = trade.get("security_name", "").strip()
                    
                    if code:  # If security code exists, use it
                        ticker_codes.add(code)
                    elif security_name:  # If no code but name exists, try to find ticker
                        ticker = self._find_ticker_for_fund(security_name)
                        if ticker:
                            ticker_codes.add(ticker)
                            fund_mappings[security_name] = ticker
            
            # Extract from portfolio data
            if portfolio_json and "holdings" in portfolio_json:
                for holding in portfolio_json["holdings"]:
                    code = holding.get("security_code", "").strip()
                    if code:  # Only add non-empty codes
                        ticker_codes.add(code)
            
            # Log fund mappings found
            if fund_mappings:
                logger.info(f"Found {len(fund_mappings)} investment fund mappings:")
                for fund_name, ticker in fund_mappings.items():
                    logger.info(f"  '{fund_name}' -> {ticker}")
            
            logger.info(f"Extracted {len(ticker_codes)} unique ticker codes: {sorted(ticker_codes)}")
            return ticker_codes
            
        except Exception as e:
            logger.error(f"Error extracting ticker codes: {e}")
            return set()
    
    def save_json_to_file(self, json_data: Dict, output_path: Path) -> None:
        """Save JSON data to file."""
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"JSON data saved to {output_path}")
            
        except Exception as e:
            logger.error(f"Error saving JSON to file: {e}")
            raise
    
    def convert_latest_data_to_json(self, processed_data_dir: Path, output_dir: Path) -> Dict[str, Path]:
        """Convert the latest trades and portfolio CSV files to JSON."""
        result_paths = {}
        
        try:
            # Find latest trades file
            trades_files = list(processed_data_dir.glob("trades_*.csv"))
            if trades_files:
                latest_trades_file = max(trades_files, key=lambda x: x.stat().st_mtime)
                trades_json = self.trades_csv_to_json(latest_trades_file)
                
                # Save trades JSON
                trades_json_path = output_dir / f"trades_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                self.save_json_to_file(trades_json, trades_json_path)
                result_paths['trades'] = trades_json_path
            
            # Find latest portfolio file
            portfolio_files = list(processed_data_dir.glob("portfolio_holdings_*.csv"))
            if portfolio_files:
                latest_portfolio_file = max(portfolio_files, key=lambda x: x.stat().st_mtime)
                portfolio_json = self.portfolio_csv_to_json(latest_portfolio_file)
                
                # Save portfolio JSON
                portfolio_json_path = output_dir / f"portfolio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                self.save_json_to_file(portfolio_json, portfolio_json_path)
                result_paths['portfolio'] = portfolio_json_path
            
            # Extract and save ticker codes
            if 'trades' in result_paths or 'portfolio' in result_paths:
                trades_json = None
                portfolio_json = None
                
                if 'trades' in result_paths:
                    with open(result_paths['trades'], 'r', encoding='utf-8') as f:
                        trades_json = json.load(f)
                
                if 'portfolio' in result_paths:
                    with open(result_paths['portfolio'], 'r', encoding='utf-8') as f:
                        portfolio_json = json.load(f)
                
                ticker_codes = self.extract_ticker_codes(trades_json, portfolio_json)
                
                # Save ticker codes as JSON
                ticker_data = {
                    "metadata": {
                        "extracted_from": list(result_paths.keys()),
                        "total_codes": len(ticker_codes),
                        "extracted_at": datetime.now().isoformat()
                    },
                    "ticker_codes": sorted(list(ticker_codes))
                }
                
                tickers_json_path = output_dir / f"ticker_codes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                self.save_json_to_file(ticker_data, tickers_json_path)
                result_paths['tickers'] = tickers_json_path
            
            logger.info(f"Successfully converted data to JSON. Files created: {list(result_paths.keys())}")
            return result_paths
            
        except Exception as e:
            logger.error(f"Error converting latest data to JSON: {e}")
            raise
    
    def save_fund_mapping_table(self, output_dir: Path) -> Path:
        """Save investment fund name to ticker mapping table as CSV."""
        try:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Create mapping table
            mapping_data = []
            for fund_name, ticker in self.fund_mappings.items():
                # Normalize fund name for better matching
                normalized_name = self.currency_converter.normalize_fund_name(fund_name)
                
                # Get asset classification
                is_fund = self.currency_converter._is_investment_fund(fund_name, ticker)
                
                mapping_data.append({
                    'original_fund_name': fund_name,
                    'normalized_fund_name': normalized_name,
                    'ticker_code': ticker,
                    'is_investment_fund': is_fund,
                    'mapping_source': 'DIC/securitycode2.csv',
                    'mapped_at': datetime.now().isoformat()
                })
            
            if mapping_data:
                df = pd.DataFrame(mapping_data)
                
                # Sort by ticker code for easier reading
                df = df.sort_values('ticker_code')
                
                # Save to CSV
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                csv_path = output_dir / f"fund_ticker_mapping_{timestamp}.csv"
                df.to_csv(csv_path, index=False, encoding='utf-8')
                
                logger.info(f"Saved {len(mapping_data)} fund mappings to {csv_path}")
                return csv_path
            else:
                logger.warning("No fund mappings found to save")
                return None
                
        except Exception as e:
            logger.error(f"Error saving fund mapping table: {e}")
            return None
    
    def create_unified_trades_csv(self, processed_data_dir: Path, output_dir: Path) -> Path:
        """Create a unified trades CSV with JPY pricing and fund mappings."""
        try:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Find latest trades file
            trades_files = list(processed_data_dir.glob("trades_*.csv"))
            if not trades_files:
                logger.warning("No trades files found")
                return None
                
            latest_trades_file = max(trades_files, key=lambda x: x.stat().st_mtime)
            logger.info(f"Processing trades file: {latest_trades_file}")
            
            # Read and process trades
            df = pd.read_csv(latest_trades_file, parse_dates=['trade_date', 'settlement_date'])
            
            # Add unified pricing columns
            df = self.currency_converter.add_unified_pricing_to_dataframe(df)
            
            # Add fund mapping information
            df['ticker_mapped'] = False
            df['original_security_code'] = df['security_code'].copy()
            
            for idx, row in df.iterrows():
                security_name = str(row.get('security_name', ''))
                security_code = row.get('security_code', '')
                
                # Try to map investment fund names to ticker codes
                # Check for empty, NaN, or blank security codes
                if pd.isna(security_code) or not str(security_code).strip():
                    ticker = self._find_ticker_for_fund(security_name)
                    if ticker:
                        df.at[idx, 'security_code'] = ticker
                        df.at[idx, 'ticker_mapped'] = True
                        self.fund_mappings[security_name] = ticker
                        logger.info(f"Mapped investment fund '{security_name}' -> '{ticker}'")
            
            # Reorder columns for better readability
            column_order = [
                'trade_date', 'settlement_date', 'security_code', 'original_security_code',
                'security_name', 'transaction_type', 'quantity', 
                'price', 'price_jpy_unified', 'settlement_amount', 'amount_jpy_unified',
                'currency', 'conversion_rate', 'is_investment_fund', 'fund_10000x_applied',
                'ticker_mapped', 'account_type', 'data_source'
            ]
            
            # Keep only existing columns
            available_columns = [col for col in column_order if col in df.columns]
            remaining_columns = [col for col in df.columns if col not in available_columns]
            final_columns = available_columns + remaining_columns
            
            df = df[final_columns]
            
            # Save unified CSV
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            unified_csv_path = output_dir / f"trades_unified_{timestamp}.csv"
            df.to_csv(unified_csv_path, index=False, encoding='utf-8')
            
            logger.info(f"Created unified trades CSV with {len(df)} trades: {unified_csv_path}")
            
            # Also save the fund mapping table
            self.save_fund_mapping_table(output_dir)
            
            return unified_csv_path
            
        except Exception as e:
            logger.error(f"Error creating unified trades CSV: {e}")
            return None