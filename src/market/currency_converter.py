"""Currency conversion utilities for unified JPY pricing."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple

import pandas as pd

logger = logging.getLogger(__name__)


class CurrencyConverter:
    """Convert different currencies to JPY with investment fund special rules."""

    def __init__(self, config=None):
        self.config = config
        self.forex_data = self._load_forex_data()

        # Investment fund price adjustment rules
        self.fund_price_rules = {
            "mutual_fund_10000x": True,  # Japanese mutual funds use 10,000x pricing
            "etf_regular": False,  # ETFs use regular pricing
        }

        # Comprehensive currency aliases
        self.currency_aliases = {
            "JPY": ["JPY", "日本円", "円", "¥", "yen", "japanese yen"],
            "USD": [
                "USD",
                "米国ドル",
                "米ドル",
                "USドル",
                "アメリカドル",
                "$",
                "dollar",
                "us dollar",
            ],
            "EUR": ["EUR", "ユーロ", "欧州ユーロ", "€", "euro", "european euro"],
            "HKD": ["HKD", "香港ドル", "HK$", "hong kong dollar", "hk dollar"],
            "HKドル": [
                "HKD",
                "香港ドル",
                "HK$",
                "hong kong dollar",
                "hk dollar",
            ],  # Special case
            "CNY": ["CNY", "中国元", "人民元", "chinese yuan", "rmb"],
            "GBP": ["GBP", "英ポンド", "英国ポンド", "£", "pound", "british pound"],
            "AUD": ["AUD", "豪ドル", "オーストラリアドル", "australian dollar"],
            "CAD": ["CAD", "カナダドル", "canadian dollar"],
            "CHF": ["CHF", "スイスフラン", "swiss franc"],
            "SGD": ["SGD", "シンガポールドル", "singapore dollar"],
            "KRW": ["KRW", "韓国ウォン", "korean won"],
            "TWD": ["TWD", "台湾ドル", "taiwan dollar", "taiwanese dollar"],
            "THB": ["THB", "タイバーツ", "thai baht"],
            "MYR": ["MYR", "マレーシアリンギット", "malaysian ringgit"],
        }

        # Investment fund name normalization patterns
        self.fund_name_patterns = {
            # Company/Brand normalization
            "sbi": ["ＳＢＩ", "SBI", "エスビーアイ"],
            "rakuten": ["楽天", "Rakuten", "らくてん"],
            "nissay": ["ニッセイ", "Nissay", "日本生命"],
            "daiwa": ["ダイワ", "Daiwa", "大和"],
            "nomura": ["ノムラ", "Nomura", "野村"],
            "mitsubishi": ["三菱", "Mitsubishi", "MUFG"],
            "mizuho": ["みずほ", "Mizuho"],
            "emaxis": ["eMAXIS", "イーマクシス", "emaxis"],
            "ifree": ["iFree", "アイフリー", "ifree"],
            "tracers": ["Tracers", "トレーサーズ"],
            # Index/Asset class normalization
            "sp500": ["S&P500", "SP500", "S&P 500", "ＳＰ５００", "エス&ピー500"],
            "topix": ["TOPIX", "トピックス", "トピックス"],
            "nasdaq": ["NASDAQ", "ナスダック", "NASDAQ100", "ナスダック１００"],
            "msci": ["MSCI", "エムエスシーアイ"],
            # Geographic regions
            "全世界": [
                "全世界",
                "world",
                "global",
                "all country",
                "オール・カントリー",
            ],
            "先進国": ["先進国", "developed", "developed market"],
            "新興国": ["新興国", "emerging", "emerging market"],
            "米国": ["米国", "US", "USA", "america", "アメリカ"],
            "欧州": ["欧州", "europe", "european", "ヨーロッパ"],
            "日本": ["日本", "japan", "japanese", "にほん", "にっぽん"],
            # Asset types
            "株式": ["株式", "stock", "equity", "share"],
            "債券": ["債券", "bond", "treasury", "government bond"],
            "reit": ["REIT", "リート", "不動産投資信託", "不動産"],
            "ゴールド": ["ゴールド", "gold", "金", "precious metal"],
            # Common fund suffixes/types
            "インデックス": ["インデックス", "index", "パッシブ"],
            "ファンド": ["ファンド", "fund"],
            "ETF": ["ETF", "イーティーエフ", "上場投信"],
            # Special terms
            "ヘッジあり": ["ヘッジあり", "hedged", "為替ヘッジあり"],
            "ヘッジなし": ["ヘッジなし", "unhedged", "為替ヘッジなし"],
            "高配当": ["高配当", "high dividend", "dividend"],
            "小型": ["小型", "small cap", "small-cap"],
            "大型": ["大型", "large cap", "large-cap"],
        }

    def _load_forex_data(self) -> pd.DataFrame:
        """Load forex rate data from files."""
        try:
            # Try to load existing forex data
            base_dir = Path(__file__).parent.parent.parent
            forex_file = base_dir / "data" / "processed" / "forex_data.csv"

            if forex_file.exists():
                forex_df = pd.read_csv(forex_file, parse_dates=["Date"])
                forex_df.set_index("Date", inplace=True)
                logger.info(f"Loaded forex data: {len(forex_df)} records")
                return forex_df
            else:
                logger.warning(f"Forex data file not found: {forex_file}")
                return pd.DataFrame()

        except Exception as e:
            logger.error(f"Error loading forex data: {e}")
            return pd.DataFrame()

    def normalize_currency_code(self, currency_input: str) -> str:
        """Normalize currency code using comprehensive aliases."""
        if not currency_input:
            return "JPY"  # Default to JPY

        # Clean and normalize input
        currency_clean = str(currency_input).strip()

        # Direct lookup for exact matches
        for standard_code, aliases in self.currency_aliases.items():
            if currency_clean in aliases:
                # Handle special case for HKドル -> HKD
                if standard_code == "HKドル":
                    return "HKD"
                return standard_code

        # Case-insensitive lookup
        currency_lower = currency_clean.lower()
        for standard_code, aliases in self.currency_aliases.items():
            if any(currency_lower == alias.lower() for alias in aliases):
                if standard_code == "HKドル":
                    return "HKD"
                return standard_code

        # Partial match for complex strings
        for standard_code, aliases in self.currency_aliases.items():
            if any(alias.lower() in currency_lower for alias in aliases if len(alias) > 2):
                if standard_code == "HKドル":
                    return "HKD"
                return standard_code

        logger.warning(f"Unknown currency: {currency_input}, defaulting to JPY")
        return "JPY"

    def normalize_fund_name(self, fund_name: str) -> str:
        """Normalize fund name using comprehensive patterns."""
        if not fund_name:
            return ""

        normalized = fund_name.strip()

        # Apply normalization patterns
        for standard_term, aliases in self.fund_name_patterns.items():
            for alias in aliases:
                # Case-sensitive replacement for Japanese text
                if any(char > "\u3040" for char in alias):  # Contains Japanese characters
                    normalized = normalized.replace(alias, standard_term)
                else:
                    # Case-insensitive for English
                    import re

                    pattern = re.compile(re.escape(alias), re.IGNORECASE)
                    normalized = pattern.sub(standard_term, normalized)

        # Additional cleanup
        normalized = re.sub(r"[（）()【】\[\]＜＞<>]", " ", normalized)
        normalized = re.sub(r"[　\s]+", " ", normalized)
        normalized = normalized.strip()

        return normalized

    def _is_investment_fund(self, security_name: str, security_code: str = "") -> bool:
        """Check if the security is an investment fund (mutual fund)."""
        # Use config fund indicators if available, otherwise use defaults
        fund_indicators = (
            self.config.FUND_INDICATORS
            if self.config and hasattr(self.config, "FUND_INDICATORS")
            else [
                "ファンド",
                "Fund",
                "インデックス",
                "Index",
                "投信",
                "投資信託",
                "eMAXIS",
                "iFree",
                "SBI",
                "ＳＢＩ",
                "楽天",
                "Rakuten",
                "ニッセイ",
                "Nissay",
                "Tracers",
                "ブル",  # Leveraged bull funds
                "ベア",  # Leveraged bear funds
                "レバレッジ",  # Leveraged
                "REIT",  # Real estate funds
                "リート",
                "NZAM",  # Fund brand
                "auAM",  # Fund brand
                "為替ヘッジ",  # Hedged funds
                "Slim",  # eMAXIS Slim series
            ]
        )

        # ETF indicators (these should NOT be treated as 10,000x funds)
        etf_indicators = (
            self.config.ETF_INDICATORS
            if self.config and hasattr(self.config, "ETF_INDICATORS")
            else ["ETF", "SPDR", "Vanguard", "iShares"]
        )

        name_upper = security_name.upper()

        # If it has ETF indicators, it's an ETF (regular pricing)
        if any(indicator.upper() in name_upper for indicator in etf_indicators):
            return False

        # If it has fund indicators, it's likely a mutual fund (10,000x pricing)
        if any(indicator in security_name for indicator in fund_indicators):
            return True

        # If security_code is empty or NaN, it's likely a fund
        if not security_code or (isinstance(security_code, float) and pd.isna(security_code)):
            return True
        if isinstance(security_code, str) and security_code.strip() == "":
            return True

        return False

    def _get_exchange_rate(self, currency: str, trade_date: datetime) -> float:
        """Get exchange rate to JPY for a specific date."""
        # Normalize currency code first
        normalized_currency = self.normalize_currency_code(currency)

        if normalized_currency == "JPY":
            return 1.0

        if self.forex_data.empty:
            # Fallback rates if no forex data available
            fallback_rates = (
                self.config.FALLBACK_FOREX_RATES
                if self.config and hasattr(self.config, "FALLBACK_FOREX_RATES")
                else {"USD": 150.0, "HKD": 19.0, "EUR": 165.0, "CNY": 21.0}
            )
            rate = fallback_rates.get(currency.upper(), 1.0)
            logger.warning(f"Using fallback rate for {currency}: {rate}")
            return rate

        # Map currency to forex column
        forex_columns = {
            "USD": "USDJPY",
            "HKD": "HKDJPY",  # Will need to calculate from USD if not available
            "EUR": "EURJPY",
            "CNY": "CNYJPY",  # Will need to calculate if not available
        }

        forex_col = forex_columns.get(normalized_currency)
        if not forex_col:
            logger.warning(f"Unknown currency: {currency}, using rate 1.0")
            return 1.0

        try:
            # Find closest date
            trade_date_only = trade_date.date() if hasattr(trade_date, "date") else trade_date

            # Get rate for exact date or closest available date
            if forex_col in self.forex_data.columns:
                # Try exact date first
                if trade_date_only in self.forex_data.index.date:
                    rate = self.forex_data.loc[self.forex_data.index.date == trade_date_only, forex_col].iloc[0]
                    if pd.notna(rate):
                        return float(rate)

                # Find nearest date
                nearest_idx = self.forex_data.index.get_indexer([trade_date], method="nearest")[0]
                if nearest_idx >= 0:
                    rate = self.forex_data.iloc[nearest_idx][forex_col]
                    if pd.notna(rate):
                        logger.debug(f"Using nearest rate for {currency} on {trade_date}: {rate}")
                        return float(rate)

            # Fallback to default rates
            fallback_rates = (
                self.config.FALLBACK_FOREX_RATES
                if self.config and hasattr(self.config, "FALLBACK_FOREX_RATES")
                else {"USD": 150.0, "HKD": 19.0, "EUR": 165.0, "CNY": 21.0}
            )
            rate = fallback_rates.get(currency.upper(), 1.0)
            logger.warning(f"Using fallback rate for {currency}: {rate}")
            return rate

        except Exception as e:
            logger.error(f"Error getting exchange rate for {currency}: {e}")
            return 1.0

    def convert_to_jpy_unified_price(self, trade_data: Dict) -> Tuple[float, float, Dict]:
        """
        Convert trade data to unified JPY pricing.

        Returns:
            - price_jpy: Unified price in JPY
            - amount_jpy: Unified transaction amount in JPY
            - conversion_info: Details about the conversion
        """
        try:
            security_name = str(trade_data.get("security_name", "") or "")
            security_code = trade_data.get("security_code", "")
            raw_currency = trade_data.get("currency", "JPY")
            currency = str(raw_currency) if pd.notna(raw_currency) else "JPY"
            price = float(trade_data.get("price", 0) or 0)
            quantity = float(trade_data.get("quantity", 0) or 0)
            # Handle NaN settlement_amount
            raw_settlement = trade_data.get("settlement_amount", 0)
            settlement_amount = float(raw_settlement) if pd.notna(raw_settlement) else 0
            trade_date = trade_data.get("trade_date")

            # Parse trade date
            if isinstance(trade_date, str):
                trade_date = pd.to_datetime(trade_date)

            # Get exchange rate
            exchange_rate = self._get_exchange_rate(currency, trade_date)

            # Check if it's an investment fund
            is_fund = self._is_investment_fund(security_name, security_code)

            # Calculate unified JPY price
            # Normalize currency for comparison
            currency_upper = currency.upper() if isinstance(currency, str) else "JPY"
            is_jpy = currency_upper in ["JPY", "円"]

            if is_jpy:
                price_jpy = price
                if is_fund and price > 100:  # Apply 10,000x rule for Japanese funds
                    price_jpy = price / 10000
                    fund_adjustment = True
                else:
                    fund_adjustment = False
            else:
                # Foreign currency conversion
                price_jpy = price * exchange_rate
                fund_adjustment = False

            # Calculate unified JPY amount
            # Logic: If settlement_amount is already in JPY (large number compared to price*quantity), don't convert
            expected_foreign_amount = price * quantity
            is_settlement_in_foreign = False

            if settlement_amount != 0 and expected_foreign_amount != 0:
                # If settlement is close to price*quantity (within 20%), it's likely foreign currency
                ratio = settlement_amount / expected_foreign_amount
                if 0.8 <= ratio <= 1.2:
                    is_settlement_in_foreign = True

            # Decide conversion
            if settlement_amount == 0 or pd.isna(settlement_amount):
                # Fallback: calculate from price * quantity
                if is_fund and is_jpy:
                    # Japanese investment funds: price is per 10,000 units
                    amount_jpy = (quantity / 10000) * price
                else:
                    amount_jpy = price * quantity * exchange_rate
            elif not is_jpy and is_settlement_in_foreign:
                amount_jpy = settlement_amount * exchange_rate
            else:
                amount_jpy = settlement_amount

            conversion_info = {
                "original_currency": currency,
                "exchange_rate": exchange_rate,
                "is_investment_fund": is_fund,
                "fund_10000x_applied": fund_adjustment,
                "conversion_date": trade_date.strftime("%Y-%m-%d") if trade_date else None,
            }

            logger.debug(f"Conversion: {security_name} {price} {currency} -> {price_jpy:.2f} JPY")

            return price_jpy, amount_jpy, conversion_info

        except Exception as e:
            logger.error(f"Error in currency conversion: {e}")
            return 0.0, 0.0, {"error": str(e)}

    def add_unified_pricing_to_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add unified JPY pricing columns to a trades DataFrame."""
        try:
            logger.info(f"Adding unified JPY pricing to {len(df)} trades")

            # Initialize new columns
            df["price_jpy_unified"] = 0.0
            df["amount_jpy_unified"] = 0.0
            df["conversion_rate"] = 1.0
            df["is_investment_fund"] = False
            df["fund_10000x_applied"] = False

            for idx, row in df.iterrows():
                trade_data = {
                    "security_name": row.get("security_name", ""),
                    "security_code": row.get("security_code", ""),
                    "currency": row.get("currency", "JPY"),
                    "price": row.get("price", 0),
                    "quantity": row.get("quantity", 0),
                    "settlement_amount": row.get("settlement_amount", 0),
                    "trade_date": row.get("trade_date"),
                }

                price_jpy, amount_jpy, conversion_info = self.convert_to_jpy_unified_price(trade_data)

                df.at[idx, "price_jpy_unified"] = price_jpy
                df.at[idx, "amount_jpy_unified"] = amount_jpy
                df.at[idx, "conversion_rate"] = conversion_info.get("exchange_rate", 1.0)
                df.at[idx, "is_investment_fund"] = conversion_info.get("is_investment_fund", False)
                df.at[idx, "fund_10000x_applied"] = conversion_info.get("fund_10000x_applied", False)

            logger.info("Successfully added unified pricing columns")
            return df

        except Exception as e:
            logger.error(f"Error adding unified pricing: {e}")
            return df
