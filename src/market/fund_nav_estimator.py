"""
Fund NAV Estimator - Calculate investment fund current values using scale factor.

The scale factor (S_f) is calculated from historical trades:
    S_f = Σ[P_f × Q_f] / Σ[I_i × FX × Q_f]

Where:
    P_f = Fund purchase price (NAV at trade time)
    Q_f = Quantity purchased
    I_i = Index/ETF price at trade time
    FX = Forex rate at trade time

Current NAV is then estimated as:
    current_nav = S_f × I_i(T) × FX(T)
"""

import json
import logging
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd

from src.config import Config

logger = logging.getLogger(__name__)


class FundNavEstimator:
    """Estimate investment fund NAV using scale factor from index prices."""

    # Keywords that indicate investment funds
    FUND_INDICATORS = [
        "ファンド",
        "インデックス",
        "オープン",
        "投信",
        "eMAXIS",
        "iFree",
        "Tracers",
        "ニッセイ",
        "ＳＢＩ",
        "SBI",
        "楽天",
        "雪だるま",
        "Slim",
        "NISA",
    ]

    def __init__(
        self,
        charts_path: Optional[Path] = None,
        forex_path: Optional[Path] = None,
        fund_dict_path: Optional[Path] = None,
    ):
        """Initialize with data file paths."""
        self.charts_path = charts_path or Config.MARKET_DATA_DIR / "charts.csv"
        self.forex_path = forex_path or Config.MARKET_DATA_DIR / "forex_data.csv"
        self.fund_dict_path = fund_dict_path or Config.RESOURCES_DIR / "fund_dictionary.json"

        self.charts_df = self._load_charts()
        self.forex_df = self._load_forex()
        self.fund_dict = self._load_fund_dictionary()

        logger.info(f"FundNavEstimator initialized with {len(self.fund_dict.get('funds', {}))} fund mappings")

    def _load_charts(self) -> pd.DataFrame:
        """Load charts.csv with Date index."""
        if not self.charts_path.exists():
            logger.warning(f"Charts file not found: {self.charts_path}")
            return pd.DataFrame()

        df = pd.read_csv(self.charts_path)
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"])
            df = df.set_index("Date").sort_index()
        return df

    def _load_forex(self) -> pd.DataFrame:
        """Load forex_data.csv with Date index."""
        if not self.forex_path.exists():
            logger.warning(f"Forex file not found: {self.forex_path}")
            return pd.DataFrame()

        df = pd.read_csv(self.forex_path)
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"])
            df = df.set_index("Date").sort_index()
        return df

    def _load_fund_dictionary(self) -> dict:
        """Load fund_dictionary.json."""
        if not self.fund_dict_path.exists():
            logger.warning(f"Fund dictionary not found: {self.fund_dict_path}")
            return {"funds": {}}

        with open(self.fund_dict_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def is_investment_fund(
        self, security_name: str, security_code: str = "", is_fund_flag: bool = False
    ) -> bool:
        """
        Determine if a security is an investment fund eligible for NAV estimation.

        Returns True if:
        - Dictionary has entry with type="fund" (or missing type, defaulting to fund)
        - Not in dictionary, but matches fund keywords (fallback)

        Returns False if:
        - Dictionary has entry with type="stock" or "etf"
        - Not in dictionary and no keywords match
        """
        # 1. Check Dictionary First (The "Truth")
        funds = self.fund_dict.get("funds", {})
        
        # Check exact name
        if security_name in funds:
            ftype = funds[security_name].get("type", "fund")
            return ftype == "fund"
        
        # Check aliases
        for fund_name, entry in funds.items():
            if security_name in entry.get("aliases", []):
                ftype = entry.get("type", "fund")
                return ftype == "fund"

        # 2. Fallback to heuristics if not in dictionary
        # If explicitly flagged as fund by source, trust it unless we know better
        if is_fund_flag:
            return True

        # Heuristic checks
        if not security_code or pd.isna(security_code) or str(security_code).strip() == "":
            # Missing code usually implies fund (unless it's a manual entry error)
            return True

        name_upper = str(security_name).upper()
        
        # Exclude specific patterns that might match keywords but are definitely not funds
        # (Though dictionary registration is the preferred way to handle these)
        
        for indicator in self.FUND_INDICATORS:
            if indicator.upper() in name_upper or indicator in security_name:
                return True

        return False

    def get_fund_mapping(self, security_name: str) -> Tuple[Optional[str], str]:
        """
        Get mapped ticker and confidence for a fund.

        Returns:
            (mapped_ticker, confidence) where confidence is "high", "medium", "low", or "none"
        """
        funds = self.fund_dict.get("funds", {})

        # Exact match
        if security_name in funds:
            entry = funds[security_name]
            return entry.get("ticker"), entry.get("confidence", "medium")

        # Alias matching
        for fund_name, entry in funds.items():
            aliases = entry.get("aliases", [])
            if security_name in aliases:
                return entry.get("ticker"), entry.get("confidence", "medium")

        return None, "none"

    def _get_index_price_on_date(self, date: pd.Timestamp, ticker: str) -> Optional[float]:
        """Get index price on a specific date, with forward-fill for missing."""
        if self.charts_df.empty or ticker not in self.charts_df.columns:
            return None

        # Try exact date
        if date in self.charts_df.index:
            price = self.charts_df.loc[date, ticker]
            if pd.notna(price):
                return float(price)

        # Try to find nearest previous date
        mask = self.charts_df.index <= date
        if mask.any():
            valid_dates = self.charts_df.index[mask]
            for prev_date in reversed(valid_dates):
                price = self.charts_df.loc[prev_date, ticker]
                if pd.notna(price):
                    return float(price)

        return None

    def _get_forex_on_date(self, date: pd.Timestamp, currency: str) -> float:
        """Get forex rate on a specific date. Returns 1.0 for JPY."""
        if currency in ["JPY", "円", "日本円"]:
            return 1.0

        if self.forex_df.empty:
            return self._get_fallback_forex(currency)

        # Determine forex column name
        forex_col = None
        if currency in ["USD", "米ドル", "ＵＳドル", "米国ドル"]:
            forex_col = "USDJPY" if "USDJPY" in self.forex_df.columns else "USDJPY=X"
        elif currency in ["EUR", "ユーロ"]:
            forex_col = "EURJPY" if "EURJPY" in self.forex_df.columns else None
        elif currency in ["HKD", "HKドル", "香港ドル"]:
            forex_col = "HKDJPY" if "HKDJPY" in self.forex_df.columns else None

        if forex_col is None or forex_col not in self.forex_df.columns:
            return self._get_fallback_forex(currency)

        # Try exact date
        if date in self.forex_df.index:
            rate = self.forex_df.loc[date, forex_col]
            if pd.notna(rate):
                return float(rate)

        # Try nearest previous date
        mask = self.forex_df.index <= date
        if mask.any():
            valid_dates = self.forex_df.index[mask]
            for prev_date in reversed(valid_dates):
                rate = self.forex_df.loc[prev_date, forex_col]
                if pd.notna(rate):
                    return float(rate)

        return self._get_fallback_forex(currency)

    def _get_fallback_forex(self, currency: str) -> float:
        """Fallback forex rates when data is unavailable."""
        fallbacks = {
            "USD": 150.0,
            "米ドル": 150.0,
            "ＵＳドル": 150.0,
            "米国ドル": 150.0,
            "EUR": 160.0,
            "ユーロ": 160.0,
            "HKD": 19.0,
            "HKドル": 19.0,
            "香港ドル": 19.0,
        }
        return fallbacks.get(currency, 1.0)

    def calculate_scale_factor(
        self, trades_df: pd.DataFrame, security_name: str, mapped_ticker: str, currency: str = "JPY"
    ) -> Optional[float]:
        """
        Calculate scale factor S_f for a fund.

        S_f = Σ[P_f × Q_f] / Σ[I_i × FX × Q_f]

        Args:
            trades_df: DataFrame with all trades
            security_name: Fund name to calculate for
            mapped_ticker: Reference index/ETF ticker
            currency: Currency for forex conversion

        Returns:
            Scale factor or None if insufficient data
        """
        if self.charts_df.empty or mapped_ticker not in self.charts_df.columns:
            logger.debug(f"No chart data for {mapped_ticker}")
            return None

        # Filter buy trades for this fund
        fund_trades = trades_df[
            (trades_df["security_name"] == security_name)
            & (trades_df["transaction_type"].isin(["buy", "buy付", "投信金額買付"]))
        ].copy()

        if fund_trades.empty:
            return None

        numerator = 0.0  # Σ[P_f × Q_f]
        denominator = 0.0  # Σ[I_i × FX × Q_f]
        valid_trades = 0

        for _, trade in fund_trades.iterrows():
            trade_date = pd.Timestamp(trade["trade_date"])
            quantity = trade.get("quantity", 0) or 0
            # Fund price (NAV) - use market_price or calculate from amount/quantity
            fund_price = trade.get("market_price", 0) or 0
            if fund_price == 0 and quantity > 0:
                amount = trade.get("amount_jpy", 0) or trade.get("settlement_amount", 0) or 0
                if amount > 0:
                    fund_price = amount / quantity

            if quantity <= 0 or fund_price <= 0:
                continue

            # Get index price on trade date
            index_price = self._get_index_price_on_date(trade_date, mapped_ticker)
            if index_price is None or index_price <= 0:
                continue

            # Get forex rate on trade date
            fx_rate = self._get_forex_on_date(trade_date, currency)

            # Accumulate
            numerator += fund_price * quantity
            denominator += index_price * fx_rate * quantity
            valid_trades += 1

        if valid_trades == 0 or denominator == 0:
            logger.debug(f"No valid trades for scale calculation: {security_name}")
            return None

        scale_factor = numerator / denominator
        logger.debug(f"Scale factor for {security_name}: {scale_factor:.6f} ({valid_trades} trades)")
        return scale_factor

    def get_latest_index_price(self, ticker: str) -> Optional[float]:
        """Get the latest available price for a ticker from charts.csv."""
        if self.charts_df.empty or ticker not in self.charts_df.columns:
            return None

        # Get last non-NaN value
        series = self.charts_df[ticker].dropna()
        if series.empty:
            return None

        return float(series.iloc[-1])

    def get_latest_forex(self, currency: str) -> float:
        """Get the latest forex rate."""
        if currency in ["JPY", "円", "日本円"]:
            return 1.0

        if self.forex_df.empty:
            return self._get_fallback_forex(currency)

        forex_col = None
        if currency in ["USD", "米ドル", "ＵＳドル", "米国ドル"]:
            forex_col = "USDJPY" if "USDJPY" in self.forex_df.columns else "USDJPY=X"

        if forex_col and forex_col in self.forex_df.columns:
            series = self.forex_df[forex_col].dropna()
            if not series.empty:
                return float(series.iloc[-1])

        return self._get_fallback_forex(currency)

    def estimate_current_nav(self, scale_factor: float, mapped_ticker: str, currency: str = "JPY") -> Optional[float]:
        """
        Estimate current NAV for a fund.

        current_nav = S_f × I_i(T) × FX(T)

        Args:
            scale_factor: Pre-calculated scale factor
            mapped_ticker: Reference index/ETF ticker
            currency: Currency for forex conversion

        Returns:
            Estimated current NAV or None
        """
        if scale_factor is None:
            return None

        latest_index = self.get_latest_index_price(mapped_ticker)
        if latest_index is None:
            return None

        latest_fx = self.get_latest_forex(currency)

        current_nav = scale_factor * latest_index * latest_fx
        return current_nav

    def estimate_fund_value(
        self, trades_df: pd.DataFrame, security_name: str, quantity: float, currency: str = "JPY"
    ) -> dict:
        """
        Estimate current value for an investment fund.

        Returns dict with:
            - mapped_ticker
            - mapping_confidence
            - scale_factor
            - current_nav
            - current_value
            - price_type
        """
        result = {
            "mapped_ticker": None,
            "mapping_confidence": "none",
            "scale_factor": None,
            "current_nav": None,
            "current_value": None,
            "price_type": None,
        }

        # Get mapping
        mapped_ticker, confidence = self.get_fund_mapping(security_name)
        result["mapped_ticker"] = mapped_ticker
        result["mapping_confidence"] = confidence

        if mapped_ticker is None:
            return result

        # Calculate scale factor
        scale_factor = self.calculate_scale_factor(trades_df, security_name, mapped_ticker, currency)
        result["scale_factor"] = scale_factor

        if scale_factor is None:
            return result

        # Estimate current NAV
        current_nav = self.estimate_current_nav(scale_factor, mapped_ticker, currency)
        result["current_nav"] = current_nav

        if current_nav is None:
            return result

        # Calculate current value
        result["current_value"] = quantity * current_nav
        result["price_type"] = "estimated_nav_index_linked"

        return result
