#!/usr/bin/env python3
"""
Unified CSV Analyzer for Japanese Trading History
Provides portfolio analytics from unified CSV files
"""

import logging
import warnings
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.analysis.models import AssetAllocation, PerformanceMetrics
from src.analysis.report_generator import ReportGenerator
from src.config import Config
from src.market.stocks import StockDataManager

warnings.filterwarnings("ignore")
logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)
plt.rcParams["font.family"] = Config.get("font_family")

logger = logging.getLogger(__name__)


class UnifiedCSVAnalyzer:
    """Analyzer for unified CSV files providing portfolio analytics."""

    def __init__(self, unified_csv_path: str, fund_mapping_path: Optional[str] = None):
        """Initialize analyzer with unified CSV file."""
        self.unified_csv_path = Path(unified_csv_path)
        self.fund_mapping_path = Path(fund_mapping_path) if fund_mapping_path else None

        self.trades_df = self._load_unified_data()
        self.fund_mapping = self._load_fund_mapping() if self.fund_mapping_path else None
        self.holdings_df = None
        self.performance_df = None
        self.risk_metrics = None
        self.stock_manager = StockDataManager()
        self._report_generator = None

        logger.info(f"Loaded {len(self.trades_df)} trades from unified CSV")

    @property
    def report_generator(self):
        """Lazy-load report generator."""
        if self._report_generator is None:
            self._report_generator = ReportGenerator(self)
        return self._report_generator

    def _load_unified_data(self) -> pd.DataFrame:
        """Load and preprocess unified CSV data."""
        df = pd.read_csv(self.unified_csv_path)
        df["trade_date"] = pd.to_datetime(df["trade_date"])
        df["settlement_date"] = pd.to_datetime(df["settlement_date"])

        for col in Config.get("unified_numeric_columns"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        df["transaction_type"] = df["transaction_type"].str.lower().str.strip()
        df.loc[df["transaction_type"].str.contains("買", na=False), "transaction_type"] = "buy"
        df.loc[df["transaction_type"].str.contains("売", na=False), "transaction_type"] = "sell"
        df.loc[df["transaction_type"].str.contains("買付", na=False), "transaction_type"] = "buy"
        df.loc[df["transaction_type"].str.contains("売付", na=False), "transaction_type"] = "sell"

        return df.sort_values("trade_date").reset_index(drop=True)

    def _load_fund_mapping(self) -> pd.DataFrame:
        """Load fund mapping data if available."""
        if self.fund_mapping_path.exists():
            return pd.read_csv(self.fund_mapping_path)
        return None

    def _force_scalar(self, val):
        """Recursively reduce pandas/numpy objects to scalar."""
        if val is None:
            return np.nan

        for _ in range(10):
            if isinstance(val, (pd.Series, pd.DataFrame)):
                if val.empty:
                    return np.nan
                val = val.iloc[0]
            elif isinstance(val, np.ndarray):
                if val.size == 0:
                    return np.nan
                val = val.item() if val.ndim == 0 else val[0]
            elif isinstance(val, list):
                if not val:
                    return np.nan
                val = val[0]
            else:
                break

        if hasattr(val, "item"):
            try:
                return val.item()
            except (ValueError, AttributeError):
                pass
        return val

    def analyze_current_holdings(self) -> pd.DataFrame:
        """Calculate current portfolio holdings with comprehensive metrics."""
        logger.info("Analyzing current holdings...")
        holdings = {}

        for _, trade in self.trades_df.iterrows():
            # Use security_name as the unique key to prevent merging different funds
            # that happen to be mapped to the same reference ticker (e.g., 1343.T)
            security_name = trade["security_name"] or "Unknown"
            ticker = trade["security_code"] or trade["original_security_code"] or ""

            if security_name not in holdings:
                holdings[security_name] = {
                    "security_name": security_name,
                    "ticker": ticker,  # Keep ticker for price lookups
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

            holdings[security_name]["last_transaction"] = max(
                holdings[security_name]["last_transaction"], trade["trade_date"]
            )
            if trade.get("is_investment_fund", False):
                holdings[security_name]["is_fund"] = True

            if trade["transaction_type"] in ["buy", "buy付", "投信金額買付"]:
                holdings[security_name]["quantity"] += trade["quantity"] or 0
                holdings[security_name]["total_cost_jpy"] += trade["amount_jpy"] or 0
                holdings[security_name]["buy_trades"].append(
                    {
                        "date": trade["trade_date"],
                        "quantity": trade["quantity"],
                        "price": trade["market_price"],
                        "amount": trade["amount_jpy"],
                    }
                )
            elif trade["transaction_type"] in ["sell", "sell付"]:
                sold_qty = trade["quantity"] or 0
                sale_amt = trade["amount_jpy"] or 0
                if holdings[security_name]["quantity"] > 0:
                    avg_cost = holdings[security_name]["total_cost_jpy"] / holdings[security_name]["quantity"]
                    cost_of_sold = avg_cost * sold_qty
                    holdings[security_name]["realized_pnl_jpy"] += sale_amt - cost_of_sold
                    holdings[security_name]["total_cost_jpy"] -= cost_of_sold
                holdings[security_name]["quantity"] -= sold_qty
                holdings[security_name]["sell_trades"].append(
                    {
                        "date": trade["trade_date"],
                        "quantity": sold_qty,
                        "price": trade["market_price"],
                        "amount": sale_amt,
                    }
                )

        holdings_data = []
        for name, h in holdings.items():
            if h["quantity"] > 0:
                avg_cost = h["total_cost_jpy"] / h["quantity"] if h["quantity"] > 0 else 0
                # Use ticker as symbol for display if available, otherwise use truncated name
                ticker_val = h["ticker"]
                if pd.notna(ticker_val) and str(ticker_val).strip():
                    display_symbol = str(ticker_val).strip()
                else:
                    # Use first 12 chars of security name as fallback symbol
                    display_symbol = name[:12] if name else "Unknown"
                    ticker_val = ""  # Ensure it's an empty string, not NaN
                holdings_data.append(
                    {
                        "symbol": display_symbol,
                        "ticker": ticker_val,  # Keep separate ticker for price lookups
                        "security_name": h["security_name"],
                        "quantity": h["quantity"],
                        "avg_cost_per_unit_jpy": avg_cost,
                        "total_cost_jpy": h["total_cost_jpy"],
                        "realized_pnl_jpy": h["realized_pnl_jpy"],
                        "currency": h["currency"],
                        "is_fund": h["is_fund"],
                        "account_type": h["account_type"],
                        "data_source": h["data_source"],
                        "first_purchase": h["first_purchase"],
                        "last_transaction": h["last_transaction"],
                        "holding_period_days": (datetime.now().date() - h["first_purchase"].date()).days,
                        "buy_trade_count": len(h["buy_trades"]),
                        "sell_trade_count": len(h["sell_trades"]),
                    }
                )

        self.holdings_df = pd.DataFrame(holdings_data)

        if not self.holdings_df.empty:
            self._apply_market_prices()
            value_col = "current_value_jpy" if "current_value_jpy" in self.holdings_df.columns else "total_cost_jpy"
            if value_col == "current_value_jpy":
                # Ensure numeric type before filling
                self.holdings_df[value_col] = pd.to_numeric(self.holdings_df[value_col], errors="coerce")

                # Fill missing current values with cost basis (safe fallback)
                self.holdings_df[value_col] = self.holdings_df[value_col].fillna(self.holdings_df["total_cost_jpy"])

                # Recalculate P&L based on valid/filled current values
                self.holdings_df["unrealized_pnl_jpy"] = (
                    self.holdings_df[value_col] - self.holdings_df["total_cost_jpy"]
                )

                # Calculate P&L % safely handles division by zero
                cost_series = self.holdings_df["total_cost_jpy"]
                valid_cost = cost_series != 0
                self.holdings_df.loc[valid_cost, "unrealized_pnl_pct"] = (
                    self.holdings_df.loc[valid_cost, "unrealized_pnl_jpy"] / cost_series.loc[valid_cost] * 100
                )
                self.holdings_df.loc[~valid_cost, "unrealized_pnl_pct"] = 0.0

            total_value = self.holdings_df[value_col].sum()
            self.holdings_df["portfolio_weight"] = self.holdings_df[value_col] / total_value
            self.holdings_df = self._classify_assets(self.holdings_df)

        logger.info(f"Found {len(self.holdings_df)} current holdings")
        return self.holdings_df

    def _apply_market_prices(self):
        """Apply latest market prices to holdings."""
        from src.market.fund_nav_estimator import FundNavEstimator

        try:
            # Try charts.csv first (primary source), then fall back to stock_prices.csv
            price_file = Config.MARKET_DATA_DIR / "charts.csv"
            if not price_file.exists():
                price_file = Config.MARKET_DATA_DIR / "stock_prices.csv"
            price_data = self.stock_manager.load_stock_prices(price_file)
            latest_prices = self.stock_manager.get_latest_prices(price_data)
        except Exception as e:
            logger.error(f"Failed to load market prices: {e}")
            return

        if latest_prices.empty or self.holdings_df is None or self.holdings_df.empty:
            return

        if isinstance(latest_prices, pd.DataFrame):
            latest_prices = latest_prices.iloc[-1]
        if latest_prices.index.duplicated().any():
            latest_prices = latest_prices[~latest_prices.index.duplicated(keep="first")]

        # Initialize FundNavEstimator for investment trusts
        try:
            nav_estimator = FundNavEstimator()
        except Exception as e:
            logger.warning(f"Failed to initialize FundNavEstimator: {e}")
            nav_estimator = None

        # Initialize columns
        self.holdings_df["current_price"] = np.nan
        self.holdings_df["current_value_jpy"] = np.nan
        self.holdings_df["unrealized_pnl_jpy"] = np.nan
        self.holdings_df["unrealized_pnl_pct"] = np.nan
        self.holdings_df["price_type"] = "cost_basis"
        self.holdings_df["mapped_ticker"] = ""
        self.holdings_df["mapping_confidence"] = "none"

        usdjpy = self._force_scalar(latest_prices.get("USDJPY=X")) or 150.0

        for idx, row in self.holdings_df.iterrows():
            ticker = row.get("ticker", "") or row["symbol"]
            symbol = row["symbol"]
            security_name = row.get("security_name", "")
            is_fund = row.get("is_fund", False)
            currency = row.get("currency", "JPY")
            quantity = self._force_scalar(row["quantity"])
            cost = row["total_cost_jpy"]

            try:
                # Check if this is an investment fund that should use NAV estimation
                use_nav_estimation = (
                    nav_estimator is not None
                    and is_fund
                    and nav_estimator.is_investment_fund(security_name, ticker, is_fund)
                )

                if use_nav_estimation:
                    # Use scale factor-based NAV estimation for investment trusts
                    result = nav_estimator.estimate_fund_value(self.trades_df, security_name, quantity, currency)

                    self.holdings_df.at[idx, "mapped_ticker"] = result["mapped_ticker"] or ""
                    self.holdings_df.at[idx, "mapping_confidence"] = result["mapping_confidence"]

                    if result["current_value"] is not None:
                        current_value = result["current_value"]
                        self.holdings_df.at[idx, "current_value_jpy"] = current_value
                        self.holdings_df.at[idx, "price_type"] = "estimated_nav_index_linked"

                        pnl = current_value - cost
                        self.holdings_df.at[idx, "unrealized_pnl_jpy"] = pnl
                        self.holdings_df.at[idx, "unrealized_pnl_pct"] = (pnl / cost * 100) if cost > 0 else 0
                        continue  # Skip direct price lookup

                # Direct price lookup for ETFs/stocks (or fallback for funds)
                price = None
                
                # Build symbol variants based on currency to avoid cross-exchange mismatches
                # Example: 2837 in HKD should use 2837.HK, not 2837.T (different securities!)
                symbol_variants = [ticker, symbol]
                
                if currency in ["HKD", "HKドル"]:
                    # HKD securities: prefer .HK suffix
                    if ticker and str(ticker).isdigit():
                        symbol_variants.append(f"{ticker}.HK")
                elif currency in ["USD", "ＵＳドル", "米国ドル"]:
                    # USD securities: no suffix typically needed (yfinance uses plain tickers)
                    pass
                else:
                    # JPY or other: try .T suffix for Japanese securities
                    if ticker:
                        symbol_variants.append(str(ticker).replace(".JP", ".T"))
                        symbol_variants.append(str(ticker).replace(".JP", ""))
                    if ticker and str(ticker).isdigit():
                        symbol_variants.append(f"{ticker}.T")

                for variant in symbol_variants:
                    if variant:
                        price = self._force_scalar(latest_prices.get(variant))
                        if pd.notna(price):
                            break

                if pd.notna(price):
                    self.holdings_df.at[idx, "current_price"] = price
                    self.holdings_df.at[idx, "price_type"] = "market_price"

                    # Calculate current value
                    qty_for_calc = quantity
                    # For Japanese investment funds with 10k unit rule (when using direct price)
                    if is_fund and quantity > 1000:
                        qty_for_calc = quantity / 10000

                    if currency in ["JPY", "円"] or str(symbol).endswith((".JP", ".T")) or str(symbol).isdigit():
                        current_value = qty_for_calc * price
                    elif currency in ["USD", "ＵＳドル", "米国ドル"]:
                        current_value = qty_for_calc * price * usdjpy
                    elif currency in ["HKD", "HKドル"]:
                        current_value = qty_for_calc * price * 20.0
                    else:
                        current_value = cost

                    self.holdings_df.at[idx, "current_value_jpy"] = current_value
                    pnl = current_value - cost
                    self.holdings_df.at[idx, "unrealized_pnl_jpy"] = pnl
                    self.holdings_df.at[idx, "unrealized_pnl_pct"] = (pnl / cost * 100) if cost > 0 else 0

            except Exception as e:
                logger.exception(f"Error pricing {symbol}: {e}")

    def _classify_assets(self, df: pd.DataFrame) -> pd.DataFrame:
        """Classify assets by type, region, and sector."""
        df = df.copy()
        df["asset_class"] = "Unknown"
        df["region"] = "Unknown"
        df["sector"] = "Unknown"

        fund_mask = df["is_fund"]
        df.loc[fund_mask, "asset_class"] = "Investment Fund"

        region_keywords = {
            "US": (["VTI", "VOO", "SPY", "QQQ"], "symbol"),
            "Japan": (["日本", "JAPAN", "TOPIX", "NIKKEI"], "name"),
            "Global": (["全世界", "WORLD", "GLOBAL", "ACWI"], "name"),
            "Emerging Markets": (["新興国", "EMERGING", "VWO"], "name"),
        }

        for idx, row in df.iterrows():
            symbol = str(row["symbol"]).upper()
            name = str(row["security_name"]).upper()

            for region, (keywords, field) in region_keywords.items():
                check = symbol if field == "symbol" else name
                if any(k in check for k in keywords):
                    df.at[idx, "region"] = region
                    break

            if any(x in name for x in ["GOLD", "ゴールド", "金"]):
                df.at[idx, "asset_class"] = "Commodity"
            elif any(x in name for x in ["BOND", "債券"]):
                df.at[idx, "asset_class"] = "Bond"
            elif any(x in name for x in ["REIT", "不動産"]):
                df.at[idx, "asset_class"] = "Real Estate"
            elif not fund_mask[idx]:
                df.at[idx, "asset_class"] = "Equity"

        return df

    def calculate_performance_metrics(self) -> PerformanceMetrics:
        """Calculate performance metrics using cost-basis returns."""
        if self.holdings_df is None:
            self.analyze_current_holdings()
        if self.holdings_df.empty:
            return PerformanceMetrics(0, 0, 0, 0, 0, 0, 0, 0)

        buy_trades = self.trades_df[self.trades_df["transaction_type"] == "buy"]
        total_invested = buy_trades["amount_jpy"].sum()
        current_value = self.holdings_df["total_cost_jpy"].sum()
        realized_pnl = self.holdings_df["realized_pnl_jpy"].sum()

        total_return = (
            ((current_value + realized_pnl - total_invested) / total_invested * 100) if total_invested > 0 else 0
        )

        first_trade = self.trades_df["trade_date"].min()
        last_trade = self.trades_df["trade_date"].max()
        days = (last_trade - first_trade).days

        if days > 0 and total_invested > 0:
            annualized = (((current_value + realized_pnl) / total_invested) ** (365.25 / days) - 1) * 100
        else:
            annualized = 0

        daily = self._calculate_daily_portfolio_values()
        if len(daily) >= 2:
            rets = daily.pct_change().dropna()
            rets = rets[(rets > -0.5) & (rets < 0.5)]
            volatility = rets.std() * np.sqrt(252) * 100 if len(rets) > 0 else 0

            if len(rets) > 1:
                cum = (1 + rets).cumprod()
                dd = (cum - cum.expanding().max()) / cum.expanding().max()
                max_dd = dd.min() * 100
            else:
                max_dd = 0
        else:
            volatility, max_dd = 0, 0

        sharpe = (annualized - 2) / volatility if volatility > 0 else 0
        calmar = annualized / abs(max_dd) if max_dd != 0 else 0

        return PerformanceMetrics(total_return, annualized, volatility, sharpe, max_dd, calmar, 50.0, 1.0)

    def _calculate_daily_portfolio_values(self) -> pd.Series:
        """Calculate daily portfolio values based on cost basis."""
        daily = self.trades_df.groupby("trade_date").agg({"amount_jpy": "sum"}).sort_index()
        cum = daily["amount_jpy"].cumsum()
        dates = pd.date_range(start=cum.index.min(), end=datetime.now().date(), freq="D")
        return cum.reindex(dates).ffill()

    def analyze_asset_allocation(self) -> AssetAllocation:
        """Analyze portfolio asset allocation."""
        if self.holdings_df is None:
            self.analyze_current_holdings()
        total = self.holdings_df["total_cost_jpy"].sum()
        if total == 0:
            return AssetAllocation({}, {}, {}, {})

        def pct_by(col):
            return (self.holdings_df.groupby(col)["total_cost_jpy"].sum() / total * 100).to_dict()

        return AssetAllocation(pct_by("asset_class"), pct_by("currency"), pct_by("region"), pct_by("account_type"))

    def generate_trading_insights(self) -> Dict:
        """Generate trading insights."""
        monthly = self.trades_df.groupby(self.trades_df["trade_date"].dt.to_period("M")).size()
        buy = self.trades_df[self.trades_df["transaction_type"] == "buy"]
        sell = self.trades_df[self.trades_df["transaction_type"] == "sell"]

        return {
            "avg_monthly_trades": monthly.mean(),
            "total_invested_jpy": buy["amount_jpy"].sum(),
            "total_divested_jpy": sell["amount_jpy"].sum(),
            "unique_securities_traded": self.trades_df["security_code"].nunique(),
            "account_usage": self.trades_df["account_type"].value_counts().to_dict(),
        }

    def analyze_risk_metrics(self) -> Dict:
        """Calculate risk metrics."""
        if self.holdings_df is None:
            self.analyze_current_holdings()

        weights = self.holdings_df["portfolio_weight"].sort_values(ascending=False)
        cum_weights = weights.cumsum()

        return {
            "concentration_risk": {
                "herfindahl_index": (weights**2).sum(),
                "top5_concentration_pct": weights.head(5).sum() * 100,
                "holdings_for_80pct": len(cum_weights[cum_weights <= 0.8]) + 1,
            },
            "diversification_risk": {
                "currency_concentration": (self.holdings_df.groupby("currency")["portfolio_weight"].sum() ** 2).sum(),
                "regional_concentration": (self.holdings_df.groupby("region")["portfolio_weight"].sum() ** 2).sum(),
            },
        }

    def analyze_trading_behavior(self) -> Dict:
        """Analyze trading behavior patterns."""
        return {
            "trading_timing": {
                "by_day_of_week": self.trades_df.groupby(self.trades_df["trade_date"].dt.dayofweek).size().to_dict(),
                "by_year": self.trades_df.groupby(self.trades_df["trade_date"].dt.year).size().to_dict(),
            },
            "investment_preference": {
                "fund_trade_ratio": len(self.trades_df[self.trades_df["is_investment_fund"]]) / len(self.trades_df),
            },
        }

    def generate_investment_recommendations(self) -> Dict:
        """Generate investment recommendations."""
        if self.holdings_df is None:
            self.analyze_current_holdings()

        recommendations = []
        weights = self.holdings_df["portfolio_weight"].sort_values(ascending=False)

        if weights.iloc[0] > 0.3:
            recommendations.append(
                {
                    "type": "Risk Management",
                    "priority": "High",
                    "recommendation": f"Consider reducing position in {self.holdings_df.loc[weights.index[0], 'symbol']}",
                }
            )

        score = min(len(self.holdings_df) * 3, 25) + (25 if weights.max() <= 0.15 else 10)
        return {
            "recommendations": recommendations,
            "portfolio_score": {"overall_score": score, "grade": "A" if score >= 80 else "B" if score >= 60 else "C"},
        }

    def generate_comprehensive_report(self, output_dir: str = None) -> Dict:
        """Generate comprehensive analysis report."""
        return self.report_generator.generate_comprehensive_report(output_dir)

    def create_advanced_visualizations(self, output_dir: str = None):
        """Create advanced visualization suite."""
        return self.report_generator.create_advanced_visualizations(output_dir)


def main():
    """Example usage."""
    csv_dir = Path("data/output/unified_csv")
    if not csv_dir.exists():
        print("No unified CSV directory found.")
        return

    csv_files = list(csv_dir.glob("trades_unified_*.csv"))
    if not csv_files:
        print("No unified CSV files found.")
        return

    latest = max(csv_files, key=lambda x: x.stat().st_mtime)
    print(f"Analyzing: {latest}")

    analyzer = UnifiedCSVAnalyzer(str(latest))
    report = analyzer.generate_comprehensive_report()
    analyzer.create_advanced_visualizations()

    print(f"\nTotal Holdings: {report['portfolio_summary']['total_holdings']}")
    print(f"Portfolio Value: ¥{report['portfolio_summary']['total_portfolio_value_jpy']:,.0f}")


if __name__ == "__main__":
    main()
