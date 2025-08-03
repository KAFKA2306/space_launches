"""Data conversion utilities for converting CSV data to JSON and extracting ticker codes."""

import pandas as pd
import json
from pathlib import Path
from typing import Dict, List, Set, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class DataConverter:
    """Convert CSV data to JSON and extract ticker information."""
    
    def __init__(self, config=None):
        self.config = config
        
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
            
            # Convert each trade to dictionary
            for _, row in df.iterrows():
                trade = {
                    "trade_date": row['trade_date'].isoformat() if pd.notna(row['trade_date']) else None,
                    "settlement_date": row['settlement_date'].isoformat() if pd.notna(row['settlement_date']) else None,
                    "security_code": row['security_code'] if pd.notna(row['security_code']) else "",
                    "security_name": row['security_name'] if pd.notna(row['security_name']) else "",
                    "transaction_type": row['transaction_type'] if pd.notna(row['transaction_type']) else "",
                    "quantity": float(row['quantity']) if pd.notna(row['quantity']) else 0.0,
                    "price": float(row['price']) if pd.notna(row['price']) else 0.0,
                    "settlement_amount": float(row['settlement_amount']) if pd.notna(row['settlement_amount']) else 0.0,
                    "currency": row['currency'] if pd.notna(row['currency']) else "",
                    "account_type": row['account_type'] if pd.notna(row['account_type']) else "",
                    "data_source": row['data_source'] if pd.notna(row['data_source']) else ""
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
                holding = {
                    "security_code": row['security_code'] if pd.notna(row['security_code']) else "",
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
                    if code:  # Only add non-empty codes
                        ticker_codes.add(code)
            
            # Extract from portfolio data
            if portfolio_json and "holdings" in portfolio_json:
                for holding in portfolio_json["holdings"]:
                    code = holding.get("security_code", "").strip()
                    if code:  # Only add non-empty codes
                        ticker_codes.add(code)
            
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