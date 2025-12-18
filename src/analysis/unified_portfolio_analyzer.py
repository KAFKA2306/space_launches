#!/usr/bin/env python3

import logging
import re
from collections import defaultdict
from datetime import datetime
from typing import Dict, Optional, Tuple

import pandas as pd

from src.config import Config

logger = logging.getLogger(__name__)


class UnifiedPortfolioAnalyzer:
    """
    統一ポートフォリオ分析クラス

    通貨の違いやティッカー名の違いを吸収し、
    網羅的なポートフォリオ・取引解析を提供
    """

    def __init__(self, config: Config = None):
        self.config = config or Config()
        self.ticker_normalizer = TickerNormalizer()
        self.currency_unifier = CurrencyUnifier()

    def unified_portfolio_analysis(self, trades_df: pd.DataFrame, price_data: Optional[pd.DataFrame] = None) -> Dict:
        """
        統一ポートフォリオ分析メイン処理

        Args:
            trades_df: 取引データ（既にJPY統一済み想定）
            price_data: 価格データ（オプション）

        Returns:
            Dict: 統一分析結果
        """
        logger.info("=== 統一ポートフォリオ分析開始 ===")

        # 1. データ前処理・正規化
        normalized_trades = self._normalize_trades_data(trades_df)

        # 2. 統一ティッカーによる集約分析
        unified_holdings = self._analyze_unified_holdings(normalized_trades, price_data)

        # 3. 通貨別・地域別分析
        currency_analysis = self._analyze_by_currency_region(normalized_trades)

        # 4. セクター・資産クラス別分析
        sector_analysis = self._analyze_by_sector_asset_class(normalized_trades)

        # 5. リスク・リターン分析
        risk_return_analysis = self._analyze_risk_return(normalized_trades, price_data)

        # 6. ポートフォリオ効率性分析
        efficiency_analysis = self._analyze_portfolio_efficiency(normalized_trades)

        # 7. 取引行動分析
        trading_behavior = self._analyze_trading_behavior(normalized_trades)

        return {
            "unified_holdings": unified_holdings,
            "currency_analysis": currency_analysis,
            "sector_analysis": sector_analysis,
            "risk_return": risk_return_analysis,
            "efficiency": efficiency_analysis,
            "trading_behavior": trading_behavior,
            "summary_metrics": self._calculate_summary_metrics(normalized_trades),
        }

    def _normalize_trades_data(self, trades_df: pd.DataFrame) -> pd.DataFrame:
        """取引データの正規化処理"""
        df = trades_df.copy()

        # 1. ティッカー正規化
        df["unified_ticker"] = df["security_code"].apply(self.ticker_normalizer.normalize_ticker)

        # 2. 統一JPY金額使用
        if "amount_jpy_unified" in df.columns:
            df["unified_amount"] = df["amount_jpy_unified"]
        else:
            df["unified_amount"] = df["settlement_amount"]

        # 3. 統一価格使用
        if "price_jpy_unified" in df.columns:
            df["unified_price"] = df["price_jpy_unified"]
        else:
            df["unified_price"] = df["price"]

        # 4. 地域・通貨情報付加
        df["region"] = df["unified_ticker"].apply(self._determine_region)
        df["asset_class"] = df.apply(self._determine_asset_class, axis=1)
        df["sector"] = df["unified_ticker"].apply(self._determine_sector)

        logger.info(f"データ正規化完了: {len(df)}取引, {df['unified_ticker'].nunique()}統一ティッカー")

        return df

    def _analyze_unified_holdings(self, trades_df: pd.DataFrame, price_data: Optional[pd.DataFrame]) -> pd.DataFrame:
        """統一ティッカーによる保有状況分析"""

        holdings = defaultdict(
            lambda: {
                "unified_ticker": "",
                "security_names": set(),
                "total_shares": 0,
                "total_cost_jpy": 0,
                "avg_cost_per_share_jpy": 0,
                "currencies": set(),
                "regions": set(),
                "asset_classes": set(),
                "sectors": set(),
                "accounts": set(),
                "brokers": set(),
                "first_purchase_date": None,
                "last_trade_date": None,
                "buy_transactions": [],
                "sell_transactions": [],
                "realized_pnl_jpy": 0,
                "transaction_count": 0,
            }
        )

        # 取引データを統一ティッカーで集約
        for _, trade in trades_df.iterrows():
            ticker = trade["unified_ticker"]

            # 基本情報更新
            holdings[ticker]["unified_ticker"] = ticker
            holdings[ticker]["security_names"].add(trade["security_name"])
            holdings[ticker]["currencies"].add(trade["currency"])
            holdings[ticker]["regions"].add(trade["region"])
            holdings[ticker]["asset_classes"].add(trade["asset_class"])
            holdings[ticker]["sectors"].add(trade["sector"])
            holdings[ticker]["accounts"].add(trade.get("account_type", ""))
            holdings[ticker]["brokers"].add(self._extract_broker_from_source(trade.get("data_source", "")))
            holdings[ticker]["transaction_count"] += 1

            # 日付情報更新
            trade_date = pd.to_datetime(trade["trade_date"])
            if holdings[ticker]["first_purchase_date"] is None:
                holdings[ticker]["first_purchase_date"] = trade_date
            else:
                holdings[ticker]["first_purchase_date"] = min(holdings[ticker]["first_purchase_date"], trade_date)

            holdings[ticker]["last_trade_date"] = max(holdings[ticker]["last_trade_date"] or trade_date, trade_date)

            # 取引タイプ別処理
            quantity = float(trade["quantity"]) if pd.notna(trade["quantity"]) else 0
            amount_jpy = float(trade["unified_amount"]) if pd.notna(trade["unified_amount"]) else 0

            if trade["transaction_type"] == "buy":
                holdings[ticker]["total_shares"] += quantity
                holdings[ticker]["total_cost_jpy"] += amount_jpy
                holdings[ticker]["buy_transactions"].append(
                    {
                        "date": trade_date,
                        "quantity": quantity,
                        "amount_jpy": amount_jpy,
                        "broker": self._extract_broker_from_source(trade.get("data_source", "")),
                        "account": trade.get("account_type", ""),
                    }
                )

            elif trade["transaction_type"] == "sell":
                holdings[ticker]["total_shares"] -= quantity
                # 簡易FIFO法でのPnL計算
                if holdings[ticker]["total_cost_jpy"] > 0 and holdings[ticker]["total_shares"] > 0:
                    avg_cost = holdings[ticker]["total_cost_jpy"] / (holdings[ticker]["total_shares"] + quantity)
                    cost_of_sold = avg_cost * quantity
                    holdings[ticker]["realized_pnl_jpy"] += amount_jpy - cost_of_sold
                    holdings[ticker]["total_cost_jpy"] -= cost_of_sold

                holdings[ticker]["sell_transactions"].append(
                    {"date": trade_date, "quantity": quantity, "amount_jpy": amount_jpy}
                )

        # DataFrameに変換
        holdings_data = []
        for ticker, data in holdings.items():
            if data["total_shares"] > 0:  # 現在保有中のもののみ
                # 平均取得単価計算
                if data["total_shares"] > 0:
                    data["avg_cost_per_share_jpy"] = data["total_cost_jpy"] / data["total_shares"]

                # 現在価格・評価額取得
                current_price_jpy, current_value_jpy = self._get_current_valuation(
                    ticker, data["total_shares"], price_data
                )

                holdings_data.append(
                    {
                        "unified_ticker": ticker,
                        "security_names": " | ".join(data["security_names"]),
                        "total_shares": data["total_shares"],
                        "avg_cost_per_share_jpy": data["avg_cost_per_share_jpy"],
                        "total_cost_jpy": data["total_cost_jpy"],
                        "current_price_jpy": current_price_jpy,
                        "current_value_jpy": current_value_jpy,
                        "unrealized_pnl_jpy": current_value_jpy - data["total_cost_jpy"],
                        "realized_pnl_jpy": data["realized_pnl_jpy"],
                        "total_pnl_jpy": (current_value_jpy - data["total_cost_jpy"]) + data["realized_pnl_jpy"],
                        "pnl_percentage": ((current_value_jpy - data["total_cost_jpy"]) + data["realized_pnl_jpy"])
                        / data["total_cost_jpy"]
                        * 100
                        if data["total_cost_jpy"] > 0
                        else 0,
                        "currencies": " | ".join(data["currencies"]),
                        "regions": " | ".join(data["regions"]),
                        "asset_classes": " | ".join(data["asset_classes"]),
                        "sectors": " | ".join(data["sectors"]),
                        "accounts": " | ".join(data["accounts"]),
                        "brokers": " | ".join(data["brokers"]),
                        "first_purchase_date": data["first_purchase_date"],
                        "last_trade_date": data["last_trade_date"],
                        "holding_period_days": (datetime.now() - data["first_purchase_date"]).days,
                        "transaction_count": data["transaction_count"],
                        "weight_percentage": 0,  # 後で計算
                    }
                )

        holdings_df = pd.DataFrame(holdings_data)

        # ポートフォリオ構成比計算
        if not holdings_df.empty:
            total_value = holdings_df["current_value_jpy"].sum()
            if total_value > 0:
                holdings_df["weight_percentage"] = holdings_df["current_value_jpy"] / total_value * 100

            holdings_df = holdings_df.sort_values("current_value_jpy", ascending=False)

        logger.info(f"統一保有分析完了: {len(holdings_df)}銘柄")
        return holdings_df

    def _analyze_by_currency_region(self, trades_df: pd.DataFrame) -> Dict:
        """通貨・地域別分析"""

        analysis = {}

        # 通貨別集計
        currency_summary = (
            trades_df.groupby("currency")
            .agg(
                {
                    "unified_amount": ["sum", "count", "mean"],
                    "unified_ticker": "nunique",
                }
            )
            .round(2)
        )
        currency_summary.columns = [
            "total_amount_jpy",
            "transaction_count",
            "avg_amount_jpy",
            "unique_securities",
        ]

        # 地域別集計
        region_summary = (
            trades_df.groupby("region")
            .agg(
                {
                    "unified_amount": ["sum", "count", "mean"],
                    "unified_ticker": "nunique",
                }
            )
            .round(2)
        )
        region_summary.columns = [
            "total_amount_jpy",
            "transaction_count",
            "avg_amount_jpy",
            "unique_securities",
        ]

        # 通貨×地域クロス分析
        currency_region_cross = pd.crosstab(
            trades_df["currency"],
            trades_df["region"],
            values=trades_df["unified_amount"],
            aggfunc="sum",
        ).fillna(0)

        analysis = {
            "by_currency": currency_summary.to_dict("index"),
            "by_region": region_summary.to_dict("index"),
            "currency_region_matrix": currency_region_cross.to_dict("index"),
            "diversification_score": self._calculate_diversification_score(trades_df),
        }

        return analysis

    def _analyze_by_sector_asset_class(self, trades_df: pd.DataFrame) -> Dict:
        """セクター・資産クラス別分析"""

        # 資産クラス別集計
        asset_class_summary = (
            trades_df.groupby("asset_class")
            .agg({"unified_amount": ["sum", "count"], "unified_ticker": "nunique"})
            .round(2)
        )

        # セクター別集計
        sector_summary = (
            trades_df.groupby("sector").agg({"unified_amount": ["sum", "count"], "unified_ticker": "nunique"}).round(2)
        )

        return {
            "by_asset_class": asset_class_summary.to_dict(),
            "by_sector": sector_summary.to_dict(),
            "asset_allocation_balance": self._calculate_asset_allocation_balance(trades_df),
        }

    def _analyze_risk_return(self, trades_df: pd.DataFrame, price_data: Optional[pd.DataFrame]) -> Dict:
        """リスク・リターン分析"""

        # ポートフォリオレベルのリスク・リターン
        portfolio_metrics = self._calculate_portfolio_risk_metrics(trades_df, price_data)

        # 銘柄レベルのリスク・リターン
        security_metrics = self._calculate_security_risk_metrics(trades_df, price_data)

        return {
            "portfolio_level": portfolio_metrics,
            "security_level": security_metrics,
        }

    def _analyze_portfolio_efficiency(self, trades_df: pd.DataFrame) -> Dict:
        """ポートフォリオ効率性分析"""

        return {
            "concentration_risk": self._calculate_concentration_risk(trades_df),
            "rebalancing_frequency": self._analyze_rebalancing_frequency(trades_df),
            "cost_efficiency": self._analyze_cost_efficiency(trades_df),
            "tax_efficiency": self._analyze_tax_efficiency(trades_df),
        }

    def _analyze_trading_behavior(self, trades_df: pd.DataFrame) -> Dict:
        """取引行動分析"""

        return {
            "trading_frequency": self._calculate_trading_frequency(trades_df),
            "market_timing": self._analyze_market_timing_behavior(trades_df),
            "broker_usage": self._analyze_broker_usage_patterns(trades_df),
            "account_utilization": self._analyze_account_utilization(trades_df),
        }

    # ヘルパーメソッド
    def _determine_region(self, ticker: str) -> str:
        """ティッカーから地域を判定"""
        if not ticker or pd.isna(ticker):
            return "Unknown"

        ticker = str(ticker).upper()

        # 日本（4桁数字）
        if re.match(r"^\d{4}$", ticker):
            return "Japan"

        # 米国（英字3-5文字）
        if re.match(r"^[A-Z]{2,5}$", ticker):
            return "US"

        # 香港（4桁で0で始まる）
        if re.match(r"^0\d{3}$", ticker):
            return "Hong Kong"

        # 中国（4桁で6で始まる）
        if re.match(r"^6\d{3}$", ticker):
            return "China"

        return "Other"

    def _determine_asset_class(self, row) -> str:
        """資産クラスを判定"""
        if row.get("is_investment_fund", False):
            return "Investment Fund"

        ticker = str(row.get("unified_ticker", "")).upper()
        security_name = str(row.get("security_name", "")).lower()

        # ETF判定
        if "etf" in security_name or any(etf_keyword in ticker for etf_keyword in ["VTI", "VOO", "QQQ", "SPY"]):
            return "ETF"

        # REIT判定
        if "reit" in security_name or "リート" in security_name:
            return "REIT"

        # 債券判定
        if any(bond_keyword in security_name for bond_keyword in ["債券", "bond", "国債"]):
            return "Bond"

        return "Stock"

    def _determine_sector(self, ticker: str) -> str:
        """セクターを判定（簡易版）"""
        if not ticker:
            return "Unknown"

        # 簡易的なセクターマッピング
        sector_mapping = {
            "AAPL": "Technology",
            "MSFT": "Technology",
            "GOOGL": "Technology",
            "AMZN": "Consumer Discretionary",
            "TSLA": "Consumer Discretionary",
            "NVDA": "Technology",
            "7203": "Consumer Discretionary",  # Toyota
            "6758": "Technology",  # Sony
            "9984": "Technology",  # SoftBank
        }

        return sector_mapping.get(str(ticker).upper(), "Other")

    def _extract_broker_from_source(self, data_source: str) -> str:
        """データソースからブローカーを抽出"""
        if not data_source:
            return "Unknown"

        source_lower = str(data_source).lower()

        if "rakuten" in source_lower or "tradehistory" in source_lower:
            return "Rakuten"
        elif "sbi" in source_lower or "savefile" in source_lower or "yakujo" in source_lower:
            return "SBI"
        elif "wise" in source_lower:
            return "Wise"
        else:
            return "Other"

    def _get_current_valuation(
        self, ticker: str, shares: float, price_data: Optional[pd.DataFrame]
    ) -> Tuple[float, float]:
        """現在の評価額を取得"""
        if price_data is None or price_data.empty:
            return 0.0, 0.0

        # 価格データから最新価格を取得（実装簡易版）
        # 実際の実装では、price_dataの構造に応じて適切に価格を取得
        try:
            if ticker in price_data.columns:
                current_price = price_data[ticker].dropna().iloc[-1] if not price_data[ticker].dropna().empty else 0
            else:
                current_price = 0
        except Exception:
            current_price = 0

        current_value = current_price * shares
        return float(current_price), float(current_value)

    def _calculate_diversification_score(self, trades_df: pd.DataFrame) -> float:
        """分散度スコア計算"""
        # 地域・通貨・資産クラスの分散度を測定
        region_count = trades_df["region"].nunique()
        currency_count = trades_df["currency"].nunique()
        asset_class_count = trades_df["asset_class"].nunique()

        # 簡易分散スコア（0-100）
        max_possible_diversity = 10  # 仮の最大値
        diversity_score = min(
            100,
            (region_count + currency_count + asset_class_count) / max_possible_diversity * 100,
        )

        return round(diversity_score, 2)

    def _calculate_summary_metrics(self, trades_df: pd.DataFrame) -> Dict:
        """サマリーメトリクス計算"""
        return {
            "total_transactions": len(trades_df),
            "unique_securities": trades_df["unified_ticker"].nunique(),
            "total_investment_jpy": trades_df[trades_df["transaction_type"] == "buy"]["unified_amount"].sum(),
            "total_divestment_jpy": trades_df[trades_df["transaction_type"] == "sell"]["unified_amount"].sum(),
            "net_investment_jpy": trades_df[trades_df["transaction_type"] == "buy"]["unified_amount"].sum()
            - trades_df[trades_df["transaction_type"] == "sell"]["unified_amount"].sum(),
            "unique_currencies": trades_df["currency"].nunique(),
            "unique_regions": trades_df["region"].nunique(),
            "unique_asset_classes": trades_df["asset_class"].nunique(),
            "unique_brokers": len(set(trades_df["data_source"].apply(self._extract_broker_from_source))),
            "date_range_days": (trades_df["trade_date"].max() - trades_df["trade_date"].min()).days,
            "diversification_score": self._calculate_diversification_score(trades_df),
        }

    # その他の分析メソッドの実装スタブ（実際の実装では詳細なロジックを追加）
    def _calculate_asset_allocation_balance(self, trades_df: pd.DataFrame) -> Dict:
        return {"balance_score": 75.0}  # placeholder

    def _calculate_portfolio_risk_metrics(self, trades_df: pd.DataFrame, price_data: Optional[pd.DataFrame]) -> Dict:
        return {"volatility": 0.15, "sharpe_ratio": 1.2}  # placeholder

    def _calculate_security_risk_metrics(self, trades_df: pd.DataFrame, price_data: Optional[pd.DataFrame]) -> Dict:
        return {}  # placeholder

    def _calculate_concentration_risk(self, trades_df: pd.DataFrame) -> float:
        return 0.25  # placeholder

    def _analyze_rebalancing_frequency(self, trades_df: pd.DataFrame) -> Dict:
        return {"frequency_score": "Medium"}  # placeholder

    def _analyze_cost_efficiency(self, trades_df: pd.DataFrame) -> Dict:
        return {"cost_ratio": 0.02}  # placeholder

    def _analyze_tax_efficiency(self, trades_df: pd.DataFrame) -> Dict:
        return {"tax_efficiency_score": 80}  # placeholder

    def _calculate_trading_frequency(self, trades_df: pd.DataFrame) -> Dict:
        return {"trades_per_month": 5.2}  # placeholder

    def _analyze_market_timing_behavior(self, trades_df: pd.DataFrame) -> Dict:
        return {"timing_score": "Average"}  # placeholder

    def _analyze_broker_usage_patterns(self, trades_df: pd.DataFrame) -> Dict:
        broker_counts = trades_df["data_source"].apply(self._extract_broker_from_source).value_counts()
        return broker_counts.to_dict()

    def _analyze_account_utilization(self, trades_df: pd.DataFrame) -> Dict:
        account_counts = trades_df["account_type"].value_counts()
        return account_counts.to_dict()


class TickerNormalizer:
    """ティッカー名正規化クラス"""

    def __init__(self):
        # ティッカー統合マッピング
        self.ticker_mappings = {
            # 投資信託 -> 代表ETFへの統合
            "ACWI_FUND": "ACWI",  # 全世界株式系ファンド
            "VWO_FUND": "VWO",  # 新興国株式系ファンド
            "VOO_FUND": "VOO",  # S&P500系ファンド
            # 同一企業の異なる市場上場銘柄統合
            "9984.T": "9984",  # SoftBank Tokyo
            "AAPL": "AAPL",  # Apple
            "GOOGL": "GOOGL",  # Google
            # 地域別同一銘柄統合
            "0700.HK": "700",  # Tencent Hong Kong
            "00700": "700",  # Tencent別表記
        }

    def normalize_ticker(self, ticker: str) -> str:
        """ティッカーの正規化"""
        if not ticker or pd.isna(ticker):
            return "UNKNOWN"

        ticker = str(ticker).strip().upper()

        # 直接マッピングがある場合
        if ticker in self.ticker_mappings:
            return self.ticker_mappings[ticker]

        # 投資信託マッピング判定
        if ticker == "" and hasattr(self, "_security_name"):
            # security_nameから投資信託を判定してティッカー化
            return self._map_fund_name_to_ticker(self._security_name)

        # 市場サフィックス除去
        ticker = re.sub(r"\.(T|HK|SS|SZ)$", "", ticker)

        # ゼロ埋めされた番号を正規化
        if re.match(r"^0+\d+$", ticker):
            ticker = ticker.lstrip("0")

        return ticker

    def _map_fund_name_to_ticker(self, fund_name: str) -> str:
        """投資信託名からティッカーへのマッピング"""
        fund_name_lower = str(fund_name).lower()

        if "emaxis slim 全世界" in fund_name_lower or "sbi・全世界株式" in fund_name_lower:
            return "ACWI"
        elif "新興国株式" in fund_name_lower:
            return "VWO"
        elif "emaxis slim 米国" in fund_name_lower or "s&p500" in fund_name_lower:
            return "VOO"
        elif "全米株式" in fund_name_lower:
            return "VTI"
        else:
            return "FUND_OTHER"


class CurrencyUnifier:
    """通貨統一処理クラス"""

    def __init__(self):
        self.base_currency = "JPY"

        # 通貨統一マッピング
        self.currency_mappings = {
            "JPY": "JPY",
            "円": "JPY",
            "USD": "USD",
            "ドル": "USD",
            "HKD": "HKD",
            "HK$": "HKD",
            "HKドル": "HKD",
            "EUR": "EUR",
            "ユーロ": "EUR",
            "GBP": "GBP",
            "英ポンド": "GBP",
        }

    def normalize_currency(self, currency: str) -> str:
        """通貨名の正規化"""
        if not currency or pd.isna(currency):
            return self.base_currency

        currency = str(currency).strip()
        return self.currency_mappings.get(currency, currency)

    def convert_to_base_currency(self, amount: float, from_currency: str, rate: float = 1.0) -> float:
        """基準通貨への変換"""
        normalized_currency = self.normalize_currency(from_currency)

        if normalized_currency == self.base_currency:
            return amount

        # 為替レート適用
        return amount * rate
