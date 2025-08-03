"""Portfolio analysis and performance calculations."""

import pandas as pd
import numpy as np
from collections import defaultdict
from datetime import datetime
import logging
from typing import Dict, List, Tuple

from config import Config


logger = logging.getLogger(__name__)


class PortfolioAnalyzer:
    """Analyze portfolio performance and holdings."""
    
    def __init__(self, config: Config = None):
        self.config = config or Config()
    
    def analyze_holdings(self, trades_df: pd.DataFrame, 
                        price_data: pd.DataFrame) -> pd.DataFrame:
        """Analyze current portfolio holdings."""
        logger.info("Analyzing portfolio holdings")
        
        holdings = defaultdict(lambda: {
            'total_shares': 0,
            'total_cost': 0,
            'buy_transactions': [],
            'sell_transactions': [],
            'realized_pnl': 0
        })
        
        # Process all trades
        for _, trade in trades_df.iterrows():
            security_code = trade['security_code']
            transaction_type = trade['transaction_type']
            quantity = trade['quantity'] if pd.notna(trade['quantity']) else 0
            amount_jpy = trade['settlement_amount'] if pd.notna(trade['settlement_amount']) else 0
            
            if transaction_type == 'buy':
                holdings[security_code]['total_shares'] += quantity
                holdings[security_code]['total_cost'] += amount_jpy
                holdings[security_code]['buy_transactions'].append({
                    'date': trade['trade_date'],
                    'quantity': quantity,
                    'amount': amount_jpy
                })
            
            elif transaction_type == 'sell':
                holdings[security_code]['total_shares'] -= quantity
                holdings[security_code]['sell_transactions'].append({
                    'date': trade['trade_date'],
                    'quantity': quantity,
                    'amount': amount_jpy
                })
                
                # Calculate realized P&L (simplified - FIFO method)
                if holdings[security_code]['total_cost'] > 0:
                    avg_cost_per_share = holdings[security_code]['total_cost'] / (holdings[security_code]['total_shares'] + quantity)
                    cost_of_sold_shares = avg_cost_per_share * quantity
                    holdings[security_code]['realized_pnl'] += amount_jpy - cost_of_sold_shares
                    holdings[security_code]['total_cost'] -= cost_of_sold_shares
        
        # Create holdings dataframe
        holdings_data = []
        latest_prices = self._get_latest_prices(price_data)
        
        for security_code, holding in holdings.items():
            if holding['total_shares'] > 0:  # Only include current holdings
                current_price = latest_prices.get(security_code, 0)
                current_value = holding['total_shares'] * current_price
                
                avg_cost_per_share = (holding['total_cost'] / holding['total_shares'] 
                                    if holding['total_shares'] > 0 else 0)
                
                unrealized_pnl = current_value - holding['total_cost']
                total_pnl = holding['realized_pnl'] + unrealized_pnl
                
                holdings_data.append({
                    'security_code': security_code,
                    'shares': holding['total_shares'],
                    'avg_cost_per_share': avg_cost_per_share,
                    'total_cost': holding['total_cost'],
                    'current_price': current_price,
                    'current_value': current_value,
                    'unrealized_pnl': unrealized_pnl,
                    'realized_pnl': holding['realized_pnl'],
                    'total_pnl': total_pnl,
                    'pnl_percentage': (total_pnl / holding['total_cost'] * 100 
                                     if holding['total_cost'] > 0 else 0)
                })
        
        holdings_df = pd.DataFrame(holdings_data)
        
        if not holdings_df.empty:
            holdings_df = holdings_df.sort_values('current_value', ascending=False)
            logger.info(f"Analyzed {len(holdings_df)} current holdings")
        else:
            logger.info("No current holdings found")
        
        return holdings_df
    
    def calculate_portfolio_summary(self, holdings_df: pd.DataFrame) -> Dict:
        """Calculate portfolio summary statistics."""
        if holdings_df.empty:
            return {
                'total_value': 0,
                'total_cost': 0,
                'total_pnl': 0,
                'total_pnl_percentage': 0,
                'realized_pnl': 0,
                'unrealized_pnl': 0,
                'number_of_holdings': 0
            }
        
        summary = {
            'total_value': holdings_df['current_value'].sum(),
            'total_cost': holdings_df['total_cost'].sum(),
            'total_pnl': holdings_df['total_pnl'].sum(),
            'realized_pnl': holdings_df['realized_pnl'].sum(),
            'unrealized_pnl': holdings_df['unrealized_pnl'].sum(),
            'number_of_holdings': len(holdings_df)
        }
        
        summary['total_pnl_percentage'] = (
            summary['total_pnl'] / summary['total_cost'] * 100 
            if summary['total_cost'] > 0 else 0
        )
        
        logger.info(f"Portfolio summary: {summary}")
        return summary
    
    def analyze_trading_activity(self, trades_df: pd.DataFrame) -> Dict:
        """Analyze trading activity patterns."""
        logger.info("Analyzing trading activity")
        
        if trades_df.empty:
            return {}
        
        # Basic statistics
        total_trades = len(trades_df)
        buy_trades = len(trades_df[trades_df['transaction_type'] == 'buy'])
        sell_trades = len(trades_df[trades_df['transaction_type'] == 'sell'])
        
        # Date range
        date_range = {
            'start_date': trades_df['trade_date'].min(),
            'end_date': trades_df['trade_date'].max(),
            'days': (trades_df['trade_date'].max() - trades_df['trade_date'].min()).days
        }
        
        # Monthly activity
        trades_df['month'] = trades_df['trade_date'].dt.to_period('M')
        monthly_activity = trades_df.groupby('month').size()
        
        # Security activity
        security_activity = trades_df['security_code'].value_counts()
        
        # Amount analysis
        total_amount_traded = trades_df['settlement_amount'].sum()
        avg_trade_amount = trades_df['settlement_amount'].mean()
        
        activity_summary = {
            'total_trades': total_trades,
            'buy_trades': buy_trades,
            'sell_trades': sell_trades,
            'date_range': date_range,
            'total_amount_traded': total_amount_traded,
            'avg_trade_amount': avg_trade_amount,
            'most_traded_securities': security_activity.head(10).to_dict(),
            'avg_trades_per_month': monthly_activity.mean(),
            'monthly_activity': monthly_activity.to_dict()
        }
        
        logger.info(f"Trading activity summary: {activity_summary}")
        return activity_summary
    
    def calculate_security_performance(self, trades_df: pd.DataFrame, 
                                     price_data: pd.DataFrame) -> pd.DataFrame:
        """Calculate performance for each security traded."""
        logger.info("Calculating security performance")
        
        security_performance = []
        
        for security_code in trades_df['security_code'].unique():
            if pd.isna(security_code):
                continue
            
            security_trades = trades_df[trades_df['security_code'] == security_code]
            
            total_bought = security_trades[security_trades['transaction_type'] == 'buy']['settlement_amount'].sum()
            total_sold = security_trades[security_trades['transaction_type'] == 'sell']['settlement_amount'].sum()
            
            shares_bought = security_trades[security_trades['transaction_type'] == 'buy']['quantity'].sum()
            shares_sold = security_trades[security_trades['transaction_type'] == 'sell']['quantity'].sum()
            
            current_shares = shares_bought - shares_sold
            
            # Get current price
            current_price = self._get_current_price(price_data, security_code)
            current_value = current_shares * current_price if current_price else 0
            
            # Calculate P&L
            realized_pnl = total_sold - (total_bought * shares_sold / shares_bought if shares_bought > 0 else 0)
            unrealized_pnl = current_value - (total_bought * current_shares / shares_bought if shares_bought > 0 else 0)
            total_pnl = realized_pnl + unrealized_pnl
            
            security_performance.append({
                'security_code': security_code,
                'trades_count': len(security_trades),
                'total_bought': total_bought,
                'total_sold': total_sold,
                'current_shares': current_shares,
                'current_value': current_value,
                'realized_pnl': realized_pnl,
                'unrealized_pnl': unrealized_pnl,
                'total_pnl': total_pnl,
                'first_trade_date': security_trades['trade_date'].min(),
                'last_trade_date': security_trades['trade_date'].max()
            })
        
        performance_df = pd.DataFrame(security_performance)
        
        if not performance_df.empty:
            performance_df = performance_df.sort_values('total_pnl', ascending=False)
        
        logger.info(f"Calculated performance for {len(performance_df)} securities")
        return performance_df
    
    def _get_latest_prices(self, price_data: pd.DataFrame) -> Dict[str, float]:
        """Get latest prices for all securities."""
        if price_data is None or price_data.empty:
            logger.warning("No price data available for latest prices")
            return {}
        
        try:
            latest_prices = price_data.iloc[-1].to_dict()
            return {k: v for k, v in latest_prices.items() if pd.notna(v)}
        except Exception as e:
            logger.error(f"Error getting latest prices: {e}")
            return {}
    
    def _get_current_price(self, price_data: pd.DataFrame, security_code: str) -> float:
        """Get current price for a specific security."""
        if price_data is None or price_data.empty or security_code not in price_data.columns:
            return 0
        
        try:
            latest_price = price_data[security_code].iloc[-1]
            return latest_price if pd.notna(latest_price) else 0
        except Exception as e:
            logger.warning(f"Error getting price for {security_code}: {e}")
            return 0