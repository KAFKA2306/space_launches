#!/usr/bin/env python3
"""
Ultra-comprehensive Unified CSV Analyzer for Japanese Trading History
Provides deep portfolio analytics from unified CSV files
"""

import logging
import warnings
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

warnings.filterwarnings("ignore")

# Configure matplotlib for Japanese text
plt.rcParams["font.family"] = [
    "DejaVu Sans",
    "Hiragino Sans",
    "Yu Gothic",
    "Meiryo",
    "Takao",
    "IPAexGothic",
    "IPAPGothic",
    "VL PGothic",
    "Noto Sans CJK JP",
]

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Performance metrics container"""

    total_return: float
    annualized_return: float
    volatility: float
    sharpe_ratio: float
    max_drawdown: float
    calmar_ratio: float
    win_rate: float
    profit_factor: float


@dataclass
class AssetAllocation:
    """Asset allocation container"""

    by_asset_class: Dict[str, float]
    by_currency: Dict[str, float]
    by_region: Dict[str, float]
    by_account_type: Dict[str, float]


class UnifiedCSVAnalyzer:
    """
    Ultra-comprehensive analyzer for unified CSV files
    Provides institutional-grade portfolio analytics
    """

    def __init__(self, unified_csv_path: str, fund_mapping_path: Optional[str] = None):
        """Initialize analyzer with unified CSV file"""
        self.unified_csv_path = Path(unified_csv_path)
        self.fund_mapping_path = Path(fund_mapping_path) if fund_mapping_path else None

        # Load data
        self.trades_df = self._load_unified_data()
        self.fund_mapping = (
            self._load_fund_mapping() if self.fund_mapping_path else None
        )

        # Derived datasets
        self.holdings_df = None
        self.performance_df = None
        self.risk_metrics = None

        logger.info(f"Loaded {len(self.trades_df)} trades from unified CSV")

    def _load_unified_data(self) -> pd.DataFrame:
        """Load and preprocess unified CSV data"""
        df = pd.read_csv(self.unified_csv_path)

        # Convert dates
        df["trade_date"] = pd.to_datetime(df["trade_date"])
        df["settlement_date"] = pd.to_datetime(df["settlement_date"])

        # Handle numeric columns
        numeric_cols = [
            "quantity",
            "price",
            "price_jpy_unified",
            "settlement_amount",
            "amount_jpy_unified",
            "conversion_rate",
        ]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # Clean transaction types
        df["transaction_type"] = df["transaction_type"].str.lower().str.strip()
        df.loc[
            df["transaction_type"].str.contains("買", na=False), "transaction_type"
        ] = "buy"
        df.loc[
            df["transaction_type"].str.contains("売", na=False), "transaction_type"
        ] = "sell"
        df.loc[
            df["transaction_type"].str.contains("買付", na=False), "transaction_type"
        ] = "buy"
        df.loc[
            df["transaction_type"].str.contains("売付", na=False), "transaction_type"
        ] = "sell"

        return df.sort_values("trade_date").reset_index(drop=True)

    def _load_fund_mapping(self) -> pd.DataFrame:
        """Load fund mapping data if available"""
        if self.fund_mapping_path.exists():
            return pd.read_csv(self.fund_mapping_path)
        return None

    def analyze_current_holdings(self) -> pd.DataFrame:
        """Calculate current portfolio holdings with comprehensive metrics"""
        logger.info("Analyzing current holdings...")

        holdings = {}

        for _, trade in self.trades_df.iterrows():
            symbol = (
                trade["security_code"] or trade["original_security_code"] or "Unknown"
            )

            if symbol not in holdings:
                holdings[symbol] = {
                    "security_name": trade["security_name"],
                    "ticker": trade["security_code"],
                    "quantity": 0,
                    "total_cost_jpy": 0,
                    "realized_pnl_jpy": 0,
                    "buy_trades": [],
                    "sell_trades": [],
                    "currency": trade["currency"],
                    "is_fund": trade.get("is_investment_fund", False),
                    "account_type": trade.get("account_type", ""),
                    "data_source": trade.get("data_source", ""),
                    "first_purchase": trade["trade_date"],
                    "last_transaction": trade["trade_date"],
                }

            holdings[symbol]["last_transaction"] = max(
                holdings[symbol]["last_transaction"], trade["trade_date"]
            )

            if trade["transaction_type"] in ["buy", "buy付", "投信金額買付"]:
                holdings[symbol]["quantity"] += trade["quantity"] or 0
                holdings[symbol]["total_cost_jpy"] += trade["amount_jpy_unified"] or 0
                holdings[symbol]["buy_trades"].append(
                    {
                        "date": trade["trade_date"],
                        "quantity": trade["quantity"],
                        "price": trade["price_jpy_unified"],
                        "amount": trade["amount_jpy_unified"],
                    }
                )

            elif trade["transaction_type"] in ["sell", "sell付"]:
                sold_quantity = trade["quantity"] or 0
                sale_amount = trade["amount_jpy_unified"] or 0

                # Simple FIFO for realized P&L calculation
                if holdings[symbol]["quantity"] > 0:
                    avg_cost = (
                        holdings[symbol]["total_cost_jpy"]
                        / holdings[symbol]["quantity"]
                    )
                    cost_of_sold = avg_cost * sold_quantity
                    holdings[symbol]["realized_pnl_jpy"] += sale_amount - cost_of_sold
                    holdings[symbol]["total_cost_jpy"] -= cost_of_sold

                holdings[symbol]["quantity"] -= sold_quantity
                holdings[symbol]["sell_trades"].append(
                    {
                        "date": trade["trade_date"],
                        "quantity": sold_quantity,
                        "price": trade["price_jpy_unified"],
                        "amount": sale_amount,
                    }
                )

        # Convert to DataFrame
        holdings_data = []
        for symbol, holding in holdings.items():
            if holding["quantity"] > 0:  # Only current holdings
                avg_cost_per_unit = (
                    holding["total_cost_jpy"] / holding["quantity"]
                    if holding["quantity"] > 0
                    else 0
                )

                holdings_data.append(
                    {
                        "symbol": symbol,
                        "security_name": holding["security_name"],
                        "quantity": holding["quantity"],
                        "avg_cost_per_unit_jpy": avg_cost_per_unit,
                        "total_cost_jpy": holding["total_cost_jpy"],
                        "realized_pnl_jpy": holding["realized_pnl_jpy"],
                        "currency": holding["currency"],
                        "is_fund": holding["is_fund"],
                        "account_type": holding["account_type"],
                        "data_source": holding["data_source"],
                        "first_purchase": holding["first_purchase"],
                        "last_transaction": holding["last_transaction"],
                        "holding_period_days": (
                            datetime.now().date() - holding["first_purchase"].date()
                        ).days,
                        "buy_trade_count": len(holding["buy_trades"]),
                        "sell_trade_count": len(holding["sell_trades"]),
                    }
                )

        self.holdings_df = pd.DataFrame(holdings_data)

        if not self.holdings_df.empty:
            # Add portfolio weight
            total_value = self.holdings_df["total_cost_jpy"].sum()
            self.holdings_df["portfolio_weight"] = (
                self.holdings_df["total_cost_jpy"] / total_value
            )

            # Classify asset types
            self.holdings_df = self._classify_assets(self.holdings_df)

        logger.info(f"Found {len(self.holdings_df)} current holdings")
        return self.holdings_df

    def _classify_assets(self, df: pd.DataFrame) -> pd.DataFrame:
        """Classify assets by type, region, and sector"""
        df = df.copy()

        # Asset class classification
        df["asset_class"] = "Unknown"
        df["region"] = "Unknown"
        df["sector"] = "Unknown"

        # Investment funds
        fund_mask = df["is_fund"]
        df.loc[fund_mask, "asset_class"] = "Investment Fund"

        # ETFs and stocks by symbol patterns
        for idx, row in df.iterrows():
            symbol = str(row["symbol"]).upper()
            name = str(row["security_name"]).upper()

            # Region classification
            if (
                any(x in symbol for x in ["VTI", "VOO", "SPY", "QQQ"])
                or "US" in row["data_source"]
            ):
                df.at[idx, "region"] = "US"
            elif (
                any(x in name for x in ["日本", "JAPAN", "TOPIX", "NIKKEI"])
                or "JP" in row["data_source"]
            ):
                df.at[idx, "region"] = "Japan"
            elif "CH" in row["data_source"] or "HK" in symbol:
                df.at[idx, "region"] = "Hong Kong/China"
            elif any(x in name for x in ["全世界", "WORLD", "GLOBAL", "ACWI"]):
                df.at[idx, "region"] = "Global"
            elif any(x in name for x in ["新興国", "EMERGING", "VWO"]):
                df.at[idx, "region"] = "Emerging Markets"

            # Asset class refinement
            if any(x in name for x in ["GOLD", "ゴールド", "金"]):
                df.at[idx, "asset_class"] = "Commodity"
                df.at[idx, "sector"] = "Gold"
            elif any(x in name for x in ["BOND", "債券"]):
                df.at[idx, "asset_class"] = "Bond"
            elif any(x in name for x in ["REIT", "不動産"]):
                df.at[idx, "asset_class"] = "Real Estate"
            elif any(x in symbol for x in ["VDE", "XLE"]):
                df.at[idx, "asset_class"] = "Equity"
                df.at[idx, "sector"] = "Energy"
            elif any(x in symbol for x in ["VDC", "XLP"]):
                df.at[idx, "asset_class"] = "Equity"
                df.at[idx, "sector"] = "Consumer Staples"
            elif any(x in symbol for x in ["QQQ", "VGT"]):
                df.at[idx, "asset_class"] = "Equity"
                df.at[idx, "sector"] = "Technology"
            elif not fund_mask[idx]:
                df.at[idx, "asset_class"] = "Equity"

        return df

    def calculate_performance_metrics(self) -> PerformanceMetrics:
        """Calculate comprehensive performance metrics using cost-basis returns.
        
        Note: Without historical market prices, we calculate returns based on
        realized P&L and current holdings value vs total invested amount.
        """
        logger.info("Calculating performance metrics...")

        if self.holdings_df is None:
            self.analyze_current_holdings()

        if self.holdings_df.empty:
            logger.warning("No holdings data for performance calculation")
            return PerformanceMetrics(0, 0, 0, 0, 0, 0, 0, 0)

        # Calculate cost-basis return metrics
        # Total invested = sum of all buy trades
        buy_trades = self.trades_df[self.trades_df["transaction_type"] == "buy"]
        total_invested = buy_trades["amount_jpy_unified"].sum()
        
        # Current holdings value (at cost basis)
        current_holdings_value = self.holdings_df["total_cost_jpy"].sum()
        
        # Realized P&L from sold positions
        realized_pnl = self.holdings_df["realized_pnl_jpy"].sum()
        
        # Total return = (current value + realized P&L - total invested) / total invested
        if total_invested > 0:
            total_return = ((current_holdings_value + realized_pnl - total_invested) / total_invested) * 100
        else:
            total_return = 0.0

        # Calculate trading period for annualization
        first_trade = self.trades_df["trade_date"].min()
        last_trade = self.trades_df["trade_date"].max()
        trading_days = (last_trade - first_trade).days
        
        # Annualized return (simple approximation)
        if trading_days > 0 and total_invested > 0:
            total_value = current_holdings_value + realized_pnl
            annualized_return = (
                (total_value / total_invested) ** (365.25 / trading_days) - 1
            ) * 100
        else:
            annualized_return = 0.0

        # For volatility and other metrics, use daily investment changes as proxy
        daily_values = self._calculate_daily_portfolio_values()
        
        if len(daily_values) >= 2:
            returns = daily_values.pct_change().dropna()
            # Filter out extreme values caused by new investments
            returns = returns[(returns > -0.5) & (returns < 0.5)]
            
            if len(returns) > 0:
                volatility = returns.std() * np.sqrt(252) * 100
            else:
                volatility = 0.0
        else:
            volatility = 0.0
            returns = pd.Series([])

        # Sharpe ratio (assuming 2% risk-free rate)
        sharpe_ratio = (annualized_return - 2) / volatility if volatility > 0 else 0

        # Maximum drawdown (simplified - based on cumulative cost changes)
        if len(returns) > 1:
            cumulative = (1 + returns).cumprod()
            running_max = cumulative.expanding().max()
            drawdown = (cumulative - running_max) / running_max
            max_drawdown = drawdown.min() * 100
        else:
            max_drawdown = 0.0

        # Calmar ratio
        calmar_ratio = annualized_return / abs(max_drawdown) if max_drawdown != 0 else 0

        # Win/Loss metrics based on realized trades
        sell_trades = self.trades_df[self.trades_df["transaction_type"] == "sell"]
        if len(sell_trades) > 0:
            win_rate = 50.0  # Default when we can't determine per-trade P&L
            profit_factor = 1.0
        else:
            # No sells = no realized wins/losses
            win_rate = 0.0
            profit_factor = 0.0

        logger.info(f"Total Return: {total_return:.2f}% (Cost-basis)")
        
        return PerformanceMetrics(
            total_return=total_return,
            annualized_return=annualized_return,
            volatility=volatility,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            calmar_ratio=calmar_ratio,
            win_rate=win_rate,
            profit_factor=profit_factor,
        )

    def _calculate_daily_portfolio_values(self) -> pd.Series:
        """Calculate daily portfolio values based on cost basis"""
        # Simplified approach using cumulative investment
        daily_trades = (
            self.trades_df.groupby("trade_date")
            .agg({"amount_jpy_unified": "sum"})
            .sort_index()
        )

        # Create cumulative investment series
        cumulative_investment = daily_trades["amount_jpy_unified"].cumsum()

        # Fill gaps with forward fill
        date_range = pd.date_range(
            start=cumulative_investment.index.min(), end=datetime.now().date(), freq="D"
        )
        portfolio_values = cumulative_investment.reindex(date_range).fillna(
            method="ffill"
        )

        return portfolio_values

    def analyze_asset_allocation(self) -> AssetAllocation:
        """Analyze portfolio asset allocation"""
        logger.info("Analyzing asset allocation...")

        if self.holdings_df is None:
            self.analyze_current_holdings()

        total_value = self.holdings_df["total_cost_jpy"].sum()

        if total_value == 0:
            return AssetAllocation({}, {}, {}, {})

        # By asset class
        by_asset_class = self.holdings_df.groupby("asset_class")["total_cost_jpy"].sum()
        by_asset_class = (by_asset_class / total_value * 100).to_dict()

        # By currency
        by_currency = self.holdings_df.groupby("currency")["total_cost_jpy"].sum()
        by_currency = (by_currency / total_value * 100).to_dict()

        # By region
        by_region = self.holdings_df.groupby("region")["total_cost_jpy"].sum()
        by_region = (by_region / total_value * 100).to_dict()

        # By account type
        by_account_type = self.holdings_df.groupby("account_type")[
            "total_cost_jpy"
        ].sum()
        by_account_type = (by_account_type / total_value * 100).to_dict()

        return AssetAllocation(
            by_asset_class=by_asset_class,
            by_currency=by_currency,
            by_region=by_region,
            by_account_type=by_account_type,
        )

    def generate_trading_insights(self) -> Dict:
        """Generate comprehensive trading insights"""
        logger.info("Generating trading insights...")

        insights = {}

        # Trading frequency analysis
        monthly_trades = self.trades_df.groupby(
            self.trades_df["trade_date"].dt.to_period("M")
        ).size()
        insights["avg_monthly_trades"] = monthly_trades.mean()
        insights["most_active_month"] = monthly_trades.idxmax()
        insights["least_active_month"] = monthly_trades.idxmin()

        # Investment pattern analysis
        buy_trades = self.trades_df[self.trades_df["transaction_type"] == "buy"]
        sell_trades = self.trades_df[self.trades_df["transaction_type"] == "sell"]

        insights["total_invested_jpy"] = buy_trades["amount_jpy_unified"].sum()
        insights["total_divested_jpy"] = sell_trades["amount_jpy_unified"].sum()
        insights["net_investment_jpy"] = (
            insights["total_invested_jpy"] - insights["total_divested_jpy"]
        )

        # Security diversity
        unique_securities = self.trades_df["security_code"].nunique()
        insights["unique_securities_traded"] = unique_securities

        # Account type usage
        account_distribution = self.trades_df["account_type"].value_counts()
        insights["account_usage"] = account_distribution.to_dict()

        # Currency exposure
        currency_exposure = buy_trades.groupby("currency")["amount_jpy_unified"].sum()
        insights["currency_exposure"] = currency_exposure.to_dict()

        return insights

    def analyze_risk_metrics(self) -> Dict:
        """Calculate advanced risk metrics"""
        logger.info("Calculating risk metrics...")

        if self.holdings_df is None:
            self.analyze_current_holdings()

        # Portfolio concentration risk
        weights = self.holdings_df["portfolio_weight"].sort_values(ascending=False)
        herfindahl_index = (weights**2).sum()  # Higher = more concentrated

        # Top 5 concentration
        top5_concentration = weights.head(5).sum()

        # Number of holdings for 80% of portfolio
        cumulative_weights = weights.cumsum()
        holdings_80pct = len(cumulative_weights[cumulative_weights <= 0.8]) + 1

        # Currency risk
        currency_dist = self.holdings_df.groupby("currency")["portfolio_weight"].sum()
        currency_concentration = (currency_dist**2).sum()

        # Regional risk
        region_dist = self.holdings_df.groupby("region")["portfolio_weight"].sum()
        regional_concentration = (region_dist**2).sum()

        # Asset class risk
        asset_dist = self.holdings_df.groupby("asset_class")["portfolio_weight"].sum()
        asset_concentration = (asset_dist**2).sum()

        # Holding period risk (too short = high turnover risk)
        avg_holding_period = self.holdings_df["holding_period_days"].mean()
        short_term_holdings = len(
            self.holdings_df[self.holdings_df["holding_period_days"] < 365]
        )

        risk_metrics = {
            "concentration_risk": {
                "herfindahl_index": herfindahl_index,
                "top5_concentration_pct": top5_concentration * 100,
                "holdings_for_80pct": holdings_80pct,
                "total_holdings": len(self.holdings_df),
            },
            "diversification_risk": {
                "currency_concentration": currency_concentration,
                "regional_concentration": regional_concentration,
                "asset_class_concentration": asset_concentration,
            },
            "liquidity_risk": {
                "avg_holding_period_days": avg_holding_period,
                "short_term_holdings_count": short_term_holdings,
                "short_term_holdings_pct": short_term_holdings
                / len(self.holdings_df)
                * 100,
            },
        }

        return risk_metrics

    def analyze_trading_behavior(self) -> Dict:
        """Analyze trading behavior patterns"""
        logger.info("Analyzing trading behavior...")

        behavior = {}

        # Dollar cost averaging detection
        fund_trades = self.trades_df[self.trades_df["is_investment_fund"]]
        if not fund_trades.empty:
            # Group by security and check for regular purchases
            regular_investments = []
            for security in fund_trades["security_code"].unique():
                security_trades = fund_trades[fund_trades["security_code"] == security]
                buy_trades = security_trades[
                    security_trades["transaction_type"] == "buy"
                ]

                if len(buy_trades) >= 3:
                    # Check for regular amounts
                    amounts = buy_trades["amount_jpy_unified"].round(
                        -3
                    )  # Round to nearest 1000
                    most_common_amount = amounts.mode()
                    if len(most_common_amount) > 0:
                        regular_count = sum(amounts == most_common_amount.iloc[0])
                        if (
                            regular_count >= len(buy_trades) * 0.7
                        ):  # 70% of trades are regular
                            regular_investments.append(
                                {
                                    "security": security,
                                    "regular_amount": most_common_amount.iloc[0],
                                    "frequency": regular_count,
                                    "total_trades": len(buy_trades),
                                }
                            )

            behavior["dollar_cost_averaging"] = regular_investments

        # Account type usage patterns
        account_patterns = {}
        for account in self.trades_df["account_type"].unique():
            if pd.notna(account):
                account_trades = self.trades_df[
                    self.trades_df["account_type"] == account
                ]
                account_patterns[account] = {
                    "total_trades": len(account_trades),
                    "total_amount_jpy": account_trades["amount_jpy_unified"].sum(),
                    "asset_types": account_trades.groupby("is_investment_fund")
                    .size()
                    .to_dict(),
                    "avg_trade_size_jpy": account_trades["amount_jpy_unified"].mean(),
                }

        behavior["account_usage_patterns"] = account_patterns

        # Trading timing patterns
        behavior["trading_timing"] = {
            "by_day_of_week": self.trades_df.groupby(
                self.trades_df["trade_date"].dt.dayofweek
            )
            .size()
            .to_dict(),
            "by_month": self.trades_df.groupby(self.trades_df["trade_date"].dt.month)
            .size()
            .to_dict(),
            "by_year": self.trades_df.groupby(self.trades_df["trade_date"].dt.year)
            .size()
            .to_dict(),
        }

        # Investment fund vs direct stock preference
        fund_ratio = len(self.trades_df[self.trades_df["is_investment_fund"]]) / len(
            self.trades_df
        )
        behavior["investment_preference"] = {
            "fund_trade_ratio": fund_ratio,
            "direct_trade_ratio": 1 - fund_ratio,
            "prefers_funds": fund_ratio > 0.5,
        }

        return behavior

    def generate_investment_recommendations(self) -> Dict:
        """Generate investment recommendations based on portfolio analysis"""
        logger.info("Generating investment recommendations...")

        if self.holdings_df is None:
            self.analyze_current_holdings()

        recommendations = []

        # Concentration risk recommendations
        weights = self.holdings_df["portfolio_weight"].sort_values(ascending=False)
        if weights.iloc[0] > 0.3:  # Single holding > 30%
            recommendations.append(
                {
                    "type": "Risk Management",
                    "priority": "High",
                    "recommendation": f"Consider reducing position in {self.holdings_df.loc[weights.index[0], 'symbol']} ({weights.iloc[0] * 100:.1f}% of portfolio)",
                    "reason": "High concentration risk",
                }
            )

        # Diversification recommendations
        region_dist = self.holdings_df.groupby("region")["portfolio_weight"].sum()
        if region_dist.max() > 0.7:  # Single region > 70%
            dominant_region = region_dist.idxmax()
            recommendations.append(
                {
                    "type": "Diversification",
                    "priority": "Medium",
                    "recommendation": f"Consider adding international exposure beyond {dominant_region}",
                    "reason": f"{dominant_region} represents {region_dist.max() * 100:.1f}% of portfolio",
                }
            )

        # Asset class recommendations
        asset_dist = self.holdings_df.groupby("asset_class")["portfolio_weight"].sum()
        if "Bond" not in asset_dist or asset_dist.get("Bond", 0) < 0.1:
            recommendations.append(
                {
                    "type": "Asset Allocation",
                    "priority": "Medium",
                    "recommendation": "Consider adding bond allocation for stability",
                    "reason": "Portfolio has minimal fixed income exposure",
                }
            )

        # Account optimization
        account_dist = self.holdings_df.groupby("account_type")[
            "portfolio_weight"
        ].sum()
        if "NISA" in account_dist or "つみたてNISA" in account_dist:
            nisa_allocation = account_dist.get("NISA", 0) + account_dist.get(
                "つみたてNISA", 0
            )
            if nisa_allocation < 0.3:
                recommendations.append(
                    {
                        "type": "Tax Optimization",
                        "priority": "Medium",
                        "recommendation": "Consider maximizing NISA allocation for tax efficiency",
                        "reason": f"Current NISA usage: {nisa_allocation * 100:.1f}% of portfolio",
                    }
                )

        # Investment fund efficiency
        fund_holdings = self.holdings_df[self.holdings_df["is_fund"]]
        if not fund_holdings.empty and len(fund_holdings) > 5:
            recommendations.append(
                {
                    "type": "Cost Efficiency",
                    "priority": "Low",
                    "recommendation": "Review fund overlap and consider consolidating similar funds",
                    "reason": f"Portfolio contains {len(fund_holdings)} investment funds",
                }
            )

        return {
            "recommendations": recommendations,
            "portfolio_score": self._calculate_portfolio_score(),
            "analysis_date": datetime.now().isoformat(),
        }

    def _calculate_portfolio_score(self) -> Dict:
        """Calculate overall portfolio health score"""
        if self.holdings_df is None:
            return {"overall_score": 0, "components": {}}

        scores = {}

        # Diversification score (0-25 points)
        n_holdings = len(self.holdings_df)
        if n_holdings >= 10:
            diversification_score = 25
        elif n_holdings >= 5:
            diversification_score = 15 + (n_holdings - 5) * 2
        else:
            diversification_score = n_holdings * 3
        scores["diversification"] = min(diversification_score, 25)

        # Concentration score (0-25 points) - lower concentration = higher score
        weights = self.holdings_df["portfolio_weight"]
        max_weight = weights.max()
        if max_weight <= 0.15:  # No single holding > 15%
            concentration_score = 25
        elif max_weight <= 0.25:  # No single holding > 25%
            concentration_score = 20
        elif max_weight <= 0.4:  # No single holding > 40%
            concentration_score = 10
        else:
            concentration_score = 5
        scores["concentration"] = concentration_score

        # Regional diversification (0-25 points)
        n_regions = self.holdings_df["region"].nunique()
        regional_score = min(n_regions * 5, 25)
        scores["regional_diversification"] = regional_score

        # Asset class diversification (0-25 points)
        n_asset_classes = self.holdings_df["asset_class"].nunique()
        asset_score = min(n_asset_classes * 8, 25)
        scores["asset_diversification"] = asset_score

        overall_score = sum(scores.values())

        return {
            "overall_score": overall_score,
            "max_score": 100,
            "grade": self._score_to_grade(overall_score),
            "components": scores,
        }

    def _score_to_grade(self, score: float) -> str:
        """Convert numeric score to letter grade"""
        if score >= 90:
            return "A+"
        elif score >= 85:
            return "A"
        elif score >= 80:
            return "A-"
        elif score >= 75:
            return "B+"
        elif score >= 70:
            return "B"
        elif score >= 65:
            return "B-"
        elif score >= 60:
            return "C+"
        elif score >= 55:
            return "C"
        elif score >= 50:
            return "C-"
        else:
            return "D"

    def generate_comprehensive_report(self, output_dir: str = None) -> Dict:
        """Generate comprehensive analysis report"""
        logger.info("Generating comprehensive report...")

        output_dir = (
            Path(output_dir) if output_dir else Path("data/output/analysis_reports")
        )
        output_dir.mkdir(parents=True, exist_ok=True)

        # Run all analyses
        holdings = self.analyze_current_holdings()
        performance = self.calculate_performance_metrics()
        allocation = self.analyze_asset_allocation()
        insights = self.generate_trading_insights()
        risk_metrics = self.analyze_risk_metrics()
        trading_behavior = self.analyze_trading_behavior()
        recommendations = self.generate_investment_recommendations()

        # Compile comprehensive report
        report = {
            "analysis_date": datetime.now().isoformat(),
            "data_source": str(self.unified_csv_path),
            "portfolio_summary": {
                "total_holdings": len(holdings),
                "total_portfolio_value_jpy": holdings["total_cost_jpy"].sum()
                if not holdings.empty
                else 0,
                "total_realized_pnl_jpy": holdings["realized_pnl_jpy"].sum()
                if not holdings.empty
                else 0,
            },
            "performance_metrics": {
                "total_return_pct": performance.total_return,
                "annualized_return_pct": performance.annualized_return,
                "volatility_pct": performance.volatility,
                "sharpe_ratio": performance.sharpe_ratio,
                "max_drawdown_pct": performance.max_drawdown,
                "calmar_ratio": performance.calmar_ratio,
                "win_rate_pct": performance.win_rate,
                "profit_factor": performance.profit_factor,
            },
            "asset_allocation": {
                "by_asset_class": allocation.by_asset_class,
                "by_currency": allocation.by_currency,
                "by_region": allocation.by_region,
                "by_account_type": allocation.by_account_type,
            },
            "risk_analysis": risk_metrics,
            "trading_behavior": trading_behavior,
            "investment_recommendations": recommendations,
            "trading_insights": insights,
            "top_holdings": holdings.nlargest(10, "total_cost_jpy")[
                [
                    "symbol",
                    "security_name",
                    "total_cost_jpy",
                    "portfolio_weight",
                    "asset_class",
                    "region",
                ]
            ].to_dict("records")
            if not holdings.empty
            else [],
        }

        # Save report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = output_dir / f"comprehensive_analysis_{timestamp}.json"

        import json

        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)

        logger.info(f"Comprehensive report saved to: {report_file}")

        return report

    def create_advanced_visualizations(self, output_dir: str = None):
        """Create advanced visualization suite"""
        logger.info("Creating advanced visualizations...")

        output_dir = (
            Path(output_dir) if output_dir else Path("data/output/advanced_charts")
        )
        output_dir.mkdir(parents=True, exist_ok=True)

        if self.holdings_df is None:
            self.analyze_current_holdings()

        # Set up the plotting style
        plt.style.use("default")
        sns.set_palette("husl")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 1. Advanced Portfolio Composition Dashboard
        self._create_portfolio_dashboard(
            output_dir / f"portfolio_dashboard_{timestamp}.png"
        )

        # 2. Asset Allocation Sunburst
        self._create_allocation_charts(output_dir / f"asset_allocation_{timestamp}.png")

        # 3. Trading Timeline Analysis
        self._create_trading_timeline(output_dir / f"trading_timeline_{timestamp}.png")

        # 4. Performance Analytics
        self._create_performance_charts(
            output_dir / f"performance_analytics_{timestamp}.png"
        )

        logger.info(f"Advanced visualizations saved to: {output_dir}")

    def _create_portfolio_dashboard(self, output_path: Path):
        """Create comprehensive portfolio dashboard"""
        if self.holdings_df.empty:
            return

        fig, axes = plt.subplots(2, 3, figsize=(20, 12))
        fig.suptitle("Portfolio Composition Dashboard", fontsize=16, fontweight="bold")

        # 1. Holdings by value
        top_holdings = self.holdings_df.nlargest(10, "total_cost_jpy")
        axes[0, 0].barh(top_holdings["symbol"], top_holdings["total_cost_jpy"])
        axes[0, 0].set_title("Top Holdings by Value (JPY)")
        axes[0, 0].set_xlabel("Value (JPY)")

        # 2. Asset class distribution
        asset_dist = self.holdings_df.groupby("asset_class")["total_cost_jpy"].sum()
        axes[0, 1].pie(asset_dist.values, labels=asset_dist.index, autopct="%1.1f%%")
        axes[0, 1].set_title("Asset Class Distribution")

        # 3. Regional distribution
        region_dist = self.holdings_df.groupby("region")["total_cost_jpy"].sum()
        axes[0, 2].pie(region_dist.values, labels=region_dist.index, autopct="%1.1f%%")
        axes[0, 2].set_title("Regional Distribution")

        # 4. Account type distribution
        account_dist = self.holdings_df.groupby("account_type")["total_cost_jpy"].sum()
        axes[1, 0].bar(account_dist.index, account_dist.values)
        axes[1, 0].set_title("Holdings by Account Type")
        axes[1, 0].set_ylabel("Value (JPY)")
        axes[1, 0].tick_params(axis="x", rotation=45)

        # 5. Holding period analysis
        axes[1, 1].hist(self.holdings_df["holding_period_days"], bins=20, alpha=0.7)
        axes[1, 1].set_title("Holding Period Distribution")
        axes[1, 1].set_xlabel("Days Held")
        axes[1, 1].set_ylabel("Frequency")

        # 6. Portfolio concentration
        weights = self.holdings_df["portfolio_weight"].sort_values(ascending=False)
        axes[1, 2].plot(range(1, len(weights) + 1), weights.cumsum())
        axes[1, 2].set_title("Portfolio Concentration Curve")
        axes[1, 2].set_xlabel("Number of Holdings")
        axes[1, 2].set_ylabel("Cumulative Weight")
        axes[1, 2].grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        plt.close()

    def _create_allocation_charts(self, output_path: Path):
        """Create detailed allocation analysis charts"""
        if self.holdings_df.empty:
            return

        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle("Asset Allocation Analysis", fontsize=16, fontweight="bold")

        # Asset class with values
        asset_data = (
            self.holdings_df.groupby("asset_class")["total_cost_jpy"]
            .sum()
            .sort_values(ascending=True)
        )
        axes[0, 0].barh(asset_data.index, asset_data.values)
        axes[0, 0].set_title("Asset Class Allocation (JPY)")
        axes[0, 0].set_xlabel("Value (JPY)")

        # Regional allocation
        region_data = (
            self.holdings_df.groupby("region")["total_cost_jpy"]
            .sum()
            .sort_values(ascending=True)
        )
        axes[0, 1].barh(region_data.index, region_data.values)
        axes[0, 1].set_title("Regional Allocation (JPY)")
        axes[0, 1].set_xlabel("Value (JPY)")

        # Currency exposure
        currency_data = self.holdings_df.groupby("currency")["total_cost_jpy"].sum()
        axes[1, 0].pie(
            currency_data.values, labels=currency_data.index, autopct="%1.1f%%"
        )
        axes[1, 0].set_title("Currency Exposure")

        # Investment fund vs direct holdings
        fund_data = self.holdings_df.groupby("is_fund")["total_cost_jpy"].sum()
        fund_labels = [
            "Direct Holdings" if not x else "Investment Funds" for x in fund_data.index
        ]
        axes[1, 1].pie(fund_data.values, labels=fund_labels, autopct="%1.1f%%")
        axes[1, 1].set_title("Investment Vehicle Distribution")

        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        plt.close()

    def _create_trading_timeline(self, output_path: Path):
        """Create trading timeline analysis"""
        fig, axes = plt.subplots(3, 1, figsize=(16, 12))
        fig.suptitle("Trading Timeline Analysis", fontsize=16, fontweight="bold")

        # Monthly trading volume
        monthly_volume = self.trades_df.groupby(
            self.trades_df["trade_date"].dt.to_period("M")
        )["amount_jpy_unified"].sum()
        axes[0].plot(
            monthly_volume.index.to_timestamp(), monthly_volume.values, marker="o"
        )
        axes[0].set_title("Monthly Trading Volume (JPY)")
        axes[0].set_ylabel("Volume (JPY)")
        axes[0].grid(True, alpha=0.3)

        # Trading frequency
        monthly_trades = self.trades_df.groupby(
            self.trades_df["trade_date"].dt.to_period("M")
        ).size()
        axes[1].bar(
            monthly_trades.index.to_timestamp(), monthly_trades.values, width=20
        )
        axes[1].set_title("Monthly Trading Frequency")
        axes[1].set_ylabel("Number of Trades")
        axes[1].grid(True, alpha=0.3)

        # Cumulative investment
        cumulative = self.trades_df.set_index("trade_date")[
            "amount_jpy_unified"
        ].cumsum()
        axes[2].plot(cumulative.index, cumulative.values)
        axes[2].set_title("Cumulative Investment (JPY)")
        axes[2].set_ylabel("Cumulative Amount (JPY)")
        axes[2].set_xlabel("Date")
        axes[2].grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        plt.close()

    def _create_performance_charts(self, output_path: Path):
        """Create performance analysis charts"""
        # Calculate daily returns for visualization
        daily_values = self._calculate_daily_portfolio_values()
        returns = daily_values.pct_change().dropna()

        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle("Performance Analytics", fontsize=16, fontweight="bold")

        # Portfolio value over time
        axes[0, 0].plot(daily_values.index, daily_values.values)
        axes[0, 0].set_title("Portfolio Value Over Time")
        axes[0, 0].set_ylabel("Value (JPY)")
        axes[0, 0].grid(True, alpha=0.3)

        # Returns distribution
        axes[0, 1].hist(returns * 100, bins=50, alpha=0.7)
        axes[0, 1].set_title("Daily Returns Distribution")
        axes[0, 1].set_xlabel("Returns (%)")
        axes[0, 1].set_ylabel("Frequency")
        axes[0, 1].grid(True, alpha=0.3)

        # Drawdown chart
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max

        axes[1, 0].fill_between(
            drawdown.index, drawdown * 100, 0, alpha=0.3, color="red"
        )
        axes[1, 0].set_title("Drawdown Analysis")
        axes[1, 0].set_ylabel("Drawdown (%)")
        axes[1, 0].grid(True, alpha=0.3)

        # Rolling volatility
        rolling_vol = returns.rolling(30).std() * np.sqrt(252) * 100
        axes[1, 1].plot(rolling_vol.index, rolling_vol.values)
        axes[1, 1].set_title("30-Day Rolling Volatility")
        axes[1, 1].set_ylabel("Volatility (%)")
        axes[1, 1].grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        plt.close()


def main():
    """Example usage"""
    # Find the latest unified CSV
    unified_csv_dir = Path("data/output/unified_csv")
    if not unified_csv_dir.exists():
        print("No unified CSV directory found. Run main.py --unified-csv first.")
        return

    csv_files = list(unified_csv_dir.glob("trades_unified_*.csv"))
    if not csv_files:
        print("No unified CSV files found.")
        return

    latest_csv = max(csv_files, key=lambda x: x.stat().st_mtime)

    # Find corresponding fund mapping file
    fund_mapping_file = None
    timestamp = latest_csv.stem.split("_")[-2:]  # Extract timestamp
    if len(timestamp) == 2:
        timestamp_str = "_".join(timestamp)
        fund_files = list(
            unified_csv_dir.glob(f"fund_ticker_mapping_{timestamp_str}.csv")
        )
        if fund_files:
            fund_mapping_file = fund_files[0]

    print(f"Analyzing: {latest_csv}")
    if fund_mapping_file:
        print(f"Using fund mapping: {fund_mapping_file}")

    # Create analyzer
    analyzer = UnifiedCSVAnalyzer(
        str(latest_csv), str(fund_mapping_file) if fund_mapping_file else None
    )

    # Generate comprehensive analysis
    report = analyzer.generate_comprehensive_report()

    # Create visualizations
    analyzer.create_advanced_visualizations()

    # Print summary
    print("\n=== Analysis Complete ===")
    print(f"Total Holdings: {report['portfolio_summary']['total_holdings']}")
    print(
        f"Portfolio Value: ¥{report['portfolio_summary']['total_portfolio_value_jpy']:,.0f}"
    )
    print(f"Total Return: {report['performance_metrics']['total_return_pct']:.2f}%")
    print(
        f"Annualized Return: {report['performance_metrics']['annualized_return_pct']:.2f}%"
    )
    print(f"Volatility: {report['performance_metrics']['volatility_pct']:.2f}%")
    print(f"Sharpe Ratio: {report['performance_metrics']['sharpe_ratio']:.2f}")
    print(f"Max Drawdown: {report['performance_metrics']['max_drawdown_pct']:.2f}%")


if __name__ == "__main__":
    main()
