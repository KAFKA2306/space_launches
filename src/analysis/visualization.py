"""Visualization utilities for trade analysis."""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
from pathlib import Path
import logging
from typing import Dict, List, Optional

from config import Config


logger = logging.getLogger(__name__)

# Set style
plt.style.use('default')
sns.set_palette("husl")


class TradeVisualizer:
    """Create visualizations for trade analysis."""
    
    def __init__(self, config: Config = None):
        self.config = config or Config()
        self.figure_size = (12, 8)
        self.dpi = 300
    
    def plot_portfolio_overview(self, holdings_df: pd.DataFrame, 
                              summary: Dict, output_path: Path):
        """Create portfolio overview charts."""
        if holdings_df.empty:
            logger.warning("No holdings data to plot")
            return
        
        # Clean the data first
        holdings_df = holdings_df.copy()
        holdings_df = holdings_df.dropna(subset=['current_value', 'security_code'])
        holdings_df = holdings_df[holdings_df['current_value'] > 0]
        
        if holdings_df.empty:
            logger.warning("No valid holdings data after cleaning")
            return
        
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle('Portfolio Overview', fontsize=16, fontweight='bold')
        
        # 1. Holdings by value (pie chart)
        top_holdings = holdings_df.nlargest(10, 'current_value')
        # Ensure no NaN values in pie chart data
        valid_holdings = top_holdings.dropna(subset=['current_value', 'security_code'])
        if not valid_holdings.empty:
            ax1.pie(valid_holdings['current_value'], labels=valid_holdings['security_code'], 
                    autopct='%1.1f%%', startangle=90)
            ax1.set_title('Top 10 Holdings by Value')
        else:
            ax1.text(0.5, 0.5, 'No valid holdings data', ha='center', va='center', transform=ax1.transAxes)
            ax1.set_title('Top 10 Holdings by Value')
        
        # 2. P&L by security (bar chart)
        if 'total_pnl' in holdings_df.columns:
            top_pnl = holdings_df.nlargest(10, 'total_pnl').dropna(subset=['total_pnl', 'security_code'])
            if not top_pnl.empty:
                colors = ['green' if x > 0 else 'red' for x in top_pnl['total_pnl']]
                ax2.bar(range(len(top_pnl)), top_pnl['total_pnl'], color=colors)
                ax2.set_title('Top 10 P&L by Security')
                ax2.set_xticks(range(len(top_pnl)))
                ax2.set_xticklabels(top_pnl['security_code'], rotation=45)
                ax2.axhline(y=0, color='black', linestyle='-', alpha=0.3)
            else:
                ax2.text(0.5, 0.5, 'No P&L data available', ha='center', va='center', transform=ax2.transAxes)
                ax2.set_title('Top 10 P&L by Security')
        else:
            ax2.text(0.5, 0.5, 'P&L column not found', ha='center', va='center', transform=ax2.transAxes)
            ax2.set_title('Top 10 P&L by Security')
        
        # 3. Cost vs Current Value
        if 'total_cost' in holdings_df.columns:
            cost_value_data = holdings_df.dropna(subset=['total_cost', 'current_value'])
            if not cost_value_data.empty and cost_value_data['total_cost'].max() > 0:
                ax3.scatter(cost_value_data['total_cost'], cost_value_data['current_value'], alpha=0.6)
                max_cost = cost_value_data['total_cost'].max()
                ax3.plot([0, max_cost], [0, max_cost], 'r--', alpha=0.5, label='Break-even line')
                ax3.set_xlabel('Total Cost (JPY)')
                ax3.set_ylabel('Current Value (JPY)')
                ax3.set_title('Cost vs Current Value')
                ax3.legend()
            else:
                ax3.text(0.5, 0.5, 'No cost data available', ha='center', va='center', transform=ax3.transAxes)
                ax3.set_title('Cost vs Current Value')
        else:
            ax3.text(0.5, 0.5, 'Cost column not found', ha='center', va='center', transform=ax3.transAxes)
            ax3.set_title('Cost vs Current Value')
        
        # 4. Summary statistics
        ax4.axis('off')
        if summary and isinstance(summary, dict):
            try:
                summary_text = f"""
        Portfolio Summary:
        
        Total Value: ¥{summary.get('total_value', 0):,.0f}
        Total Cost: ¥{summary.get('total_cost', 0):,.0f}
        Total P&L: ¥{summary.get('total_pnl', 0):,.0f}
        P&L %: {summary.get('total_pnl_percentage', 0):.2f}%
        
        Realized P&L: ¥{summary.get('realized_pnl', 0):,.0f}
        Unrealized P&L: ¥{summary.get('unrealized_pnl', 0):,.0f}
        
        Number of Holdings: {summary.get('number_of_holdings', 0)}
        """
                ax4.text(0.1, 0.9, summary_text, transform=ax4.transAxes, fontsize=12,
                        verticalalignment='top', fontfamily='monospace')
            except Exception as e:
                logger.warning(f"Error formatting summary: {e}")
                ax4.text(0.5, 0.5, 'Summary data unavailable', ha='center', va='center', 
                        transform=ax4.transAxes)
        else:
            ax4.text(0.5, 0.5, 'No summary data', ha='center', va='center', transform=ax4.transAxes)
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=self.dpi, bbox_inches='tight')
        plt.close()
        
        logger.info(f"Portfolio overview saved to {output_path}")
    
    def plot_trading_activity(self, trades_df: pd.DataFrame, 
                             activity_summary: Dict, output_path: Path):
        """Create trading activity charts."""
        if trades_df.empty:
            logger.warning("No trading data to plot")
            return
        
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle('Trading Activity Analysis', fontsize=16, fontweight='bold')
        
        # Determine which amount column to use
        amount_column = 'amount_jpy' if 'amount_jpy' in trades_df.columns else 'settlement_amount'
        
        # 1. Monthly trading volume
        trades_df['month'] = trades_df['trade_date'].dt.to_period('M')
        monthly_volume = trades_df.groupby('month')[amount_column].sum()
        monthly_volume.plot(kind='bar', ax=ax1)
        ax1.set_title('Monthly Trading Volume')
        ax1.set_xlabel('Month')
        ax1.set_ylabel('Amount (JPY)')
        ax1.tick_params(axis='x', rotation=45)
        
        # 2. Buy vs Sell distribution
        transaction_counts = trades_df['transaction_type'].value_counts()
        ax2.pie(transaction_counts.values, labels=transaction_counts.index, 
                autopct='%1.1f%%', startangle=90)
        ax2.set_title('Buy vs Sell Distribution')
        
        # 3. Most traded securities
        if 'most_traded_securities' in activity_summary:
            top_securities = pd.Series(activity_summary['most_traded_securities']).head(10)
            top_securities.plot(kind='barh', ax=ax3)
            ax3.set_title('Most Traded Securities (by count)')
            ax3.set_xlabel('Number of Trades')
        
        # 4. Trade amount distribution
        ax4.hist(trades_df[amount_column].dropna(), bins=30, alpha=0.7, edgecolor='black')
        ax4.set_title('Trade Amount Distribution')
        ax4.set_xlabel('Amount (JPY)')
        ax4.set_ylabel('Frequency')
        ax4.axvline(trades_df[amount_column].mean(), color='red', linestyle='--', 
                   label=f'Mean: ¥{trades_df[amount_column].mean():,.0f}')
        ax4.legend()
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=self.dpi, bbox_inches='tight')
        plt.close()
        
        logger.info(f"Trading activity chart saved to {output_path}")
    
    def plot_security_chart(self, security_code: str, trades_df: pd.DataFrame, 
                           price_data: pd.DataFrame, output_path: Path):
        """Create individual security chart with price and trades."""
        security_trades = trades_df[trades_df['security_code'] == security_code]
        
        if security_trades.empty:
            logger.warning(f"No trades found for {security_code}")
            return
        
        # Check if we have price data
        price_column = None
        for col in price_data.columns:
            if col == security_code or col.rstrip('.T') == security_code:
                price_column = col
                break
        
        if price_column is None:
            logger.warning(f"No price data found for {security_code}")
            return
        
        price_series = price_data[price_column].dropna()
        
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=self.figure_size, 
                                      gridspec_kw={'height_ratios': [3, 1]})
        
        # Plot price
        ax1.plot(price_series.index, price_series.values, 'b-', linewidth=1, alpha=0.8)
        ax1.set_title(f'{security_code} - Price and Trading Activity', fontweight='bold')
        ax1.set_ylabel('Price')
        ax1.grid(True, alpha=0.3)
        
        # Plot trades
        for _, trade in security_trades.iterrows():
            color = 'green' if trade['transaction_type'] == 'buy' else 'red'
            marker = '^' if trade['transaction_type'] == 'buy' else 'v'
            
            # Plot trade marker
            trade_date = trade['trade_date']
            if trade_date in price_series.index:
                price_at_trade = price_series.loc[trade_date]
            else:
                # Find nearest date
                nearest_dates = price_series.index[price_series.index <= trade_date]
                if len(nearest_dates) > 0:
                    price_at_trade = price_series.loc[nearest_dates[-1]]
                else:
                    continue
            
            ax1.scatter(trade_date, price_at_trade, c=color, marker=marker, 
                       s=100, alpha=0.8, edgecolors='black', linewidth=0.5)
            
            # Add vertical line
            ax1.axvline(x=trade_date, color=color, alpha=0.3, linestyle='--')
        
        # Format x-axis
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax1.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        
        # Volume/amount plot
        trade_dates = security_trades['trade_date']
        amount_column = 'amount_jpy' if 'amount_jpy' in security_trades.columns else 'settlement_amount'
        trade_amounts = security_trades[amount_column]
        colors = ['green' if t == 'buy' else 'red' for t in security_trades['transaction_type']]
        
        ax2.bar(trade_dates, trade_amounts, color=colors, alpha=0.7, width=10)
        ax2.set_ylabel('Trade Amount (JPY)')
        ax2.set_xlabel('Date')
        ax2.grid(True, alpha=0.3)
        
        # Format x-axis for volume plot
        ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        
        # Add legend
        from matplotlib.lines import Line2D
        legend_elements = [
            Line2D([0], [0], marker='^', color='w', markerfacecolor='green', 
                   markersize=10, label='Buy'),
            Line2D([0], [0], marker='v', color='w', markerfacecolor='red', 
                   markersize=10, label='Sell')
        ]
        ax1.legend(handles=legend_elements, loc='upper left')
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=self.dpi, bbox_inches='tight')
        plt.close()
        
        logger.info(f"Security chart for {security_code} saved to {output_path}")
    
    def create_all_security_charts(self, trades_df: pd.DataFrame, 
                                  price_data: pd.DataFrame, 
                                  output_dir: Path, limit: int = 20):
        """Create charts for all securities (limited to most traded)."""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Get most traded securities
        security_counts = trades_df['security_code'].value_counts()
        top_securities = security_counts.head(limit).index
        
        logger.info(f"Creating charts for top {len(top_securities)} securities")
        
        for security_code in top_securities:
            if pd.isna(security_code):
                continue
            
            output_path = output_dir / f"{security_code}_chart.png"
            self.plot_security_chart(security_code, trades_df, price_data, output_path)
        
        logger.info(f"Created {len(top_securities)} security charts in {output_dir}")
    
    def plot_performance_summary(self, performance_df: pd.DataFrame, output_path: Path):
        """Create performance summary charts."""
        if performance_df.empty:
            logger.warning("No performance data to plot")
            return
        
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle('Security Performance Analysis', fontsize=16, fontweight='bold')
        
        # 1. Top performers by total P&L
        top_performers = performance_df.head(10)
        colors = ['green' if x > 0 else 'red' for x in top_performers['total_pnl']]
        ax1.barh(range(len(top_performers)), top_performers['total_pnl'], color=colors)
        ax1.set_title('Top 10 Securities by Total P&L')
        ax1.set_yticks(range(len(top_performers)))
        ax1.set_yticklabels(top_performers['security_code'])
        ax1.axvline(x=0, color='black', linestyle='-', alpha=0.3)
        
        # 2. Realized vs Unrealized P&L
        ax2.scatter(performance_df['realized_pnl'], performance_df['unrealized_pnl'], alpha=0.6)
        ax2.set_xlabel('Realized P&L (JPY)')
        ax2.set_ylabel('Unrealized P&L (JPY)')
        ax2.set_title('Realized vs Unrealized P&L')
        ax2.axhline(y=0, color='black', linestyle='--', alpha=0.3)
        ax2.axvline(x=0, color='black', linestyle='--', alpha=0.3)
        
        # 3. Trading frequency
        ax3.hist(performance_df['trades_count'], bins=20, alpha=0.7, edgecolor='black')
        ax3.set_title('Trading Frequency Distribution')
        ax3.set_xlabel('Number of Trades per Security')
        ax3.set_ylabel('Frequency')
        
        # 4. Current value distribution
        current_holdings = performance_df[performance_df['current_shares'] > 0]
        if not current_holdings.empty:
            ax4.hist(current_holdings['current_value'], bins=20, alpha=0.7, edgecolor='black')
            ax4.set_title('Current Holdings Value Distribution')
            ax4.set_xlabel('Current Value (JPY)')
            ax4.set_ylabel('Frequency')
        else:
            ax4.text(0.5, 0.5, 'No current holdings', ha='center', va='center', 
                    transform=ax4.transAxes, fontsize=14)
            ax4.set_title('Current Holdings Value Distribution')
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=self.dpi, bbox_inches='tight')
        plt.close()
        
        logger.info(f"Performance summary saved to {output_path}")