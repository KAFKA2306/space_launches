"""Configuration management for trade history analysis."""

import json
from pathlib import Path


class Config:
    """Configuration settings for the trade history analyzer.

    All configuration values are loaded from resources/config.json.
    Use Config.get(key) to access configuration values.
    """

    # Base directory (project root)
    BASE_DIR = Path(__file__).parent.parent

    # Data directories
    DATA_DIR = BASE_DIR / "data"
    RAW_DATA_DIR = DATA_DIR / "raw"
    INTERIM_DIR = DATA_DIR / "interim"
    MARKET_DATA_DIR = INTERIM_DIR / "market"
    TRADES_DATA_DIR = INTERIM_DIR / "trades"
    UNIFIED_DATA_DIR = DATA_DIR / "unified"
    REPORTS_DIR = DATA_DIR / "reports"
    RESOURCES_DIR = BASE_DIR / "resources"

    # Load external config from resources
    _config_data = None

    @classmethod
    def _load_config(cls):
        """Load configuration from resources/config.json."""
        if cls._config_data is None:
            config_path = cls.BASE_DIR / "resources" / "config.json"
            with open(config_path, "r", encoding="utf-8") as f:
                cls._config_data = json.load(f)
        return cls._config_data

    @classmethod
    def get(cls, key, default=None):
        """Get a configuration value by key."""
        return cls._load_config().get(key, default)

    @classmethod
    def ensure_directories(cls):
        """Ensure all required directories exist."""
        directories = [
            cls.DATA_DIR,
            cls.RAW_DATA_DIR,
            cls.INTERIM_DIR,
            cls.MARKET_DATA_DIR,
            cls.TRADES_DATA_DIR,
            cls.UNIFIED_DATA_DIR,
            cls.REPORTS_DIR,
            cls.RESOURCES_DIR,
        ]
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

    # Properties that load from JSON config
    @property
    def FOREX_PAIRS(self):
        return self.get("forex_pairs")

    @property
    def MARKET_START_DATE(self):
        return self.get("market_start_date")

    @property
    def DEFAULT_ENCODING(self):
        return self.get("default_encoding")

    @property
    def FALLBACK_ENCODINGS(self):
        return self.get("fallback_encodings")

    @property
    def DATE_FORMATS(self):
        return self.get("date_formats")

    @property
    def NUMERIC_COLUMNS(self):
        return self.get("numeric_columns")

    @property
    def OHLCV_COLUMNS(self):
        return self.get("ohlcv_columns")

    @property
    def DATA_SOURCES(self):
        return self.get("data_sources")

    @property
    def FOREX_COLUMN_NAMES(self):
        return self.get("forex_column_names")

    @property
    def POSSIBLE_DATE_COLUMNS(self):
        return self.get("possible_date_columns")

    @property
    def FALLBACK_FOREX_RATES(self):
        return self.get("fallback_forex_rates")

    @property
    def FUND_INDICATORS(self):
        return self.get("fund_indicators")

    @property
    def ETF_INDICATORS(self):
        return self.get("etf_indicators")

    @property
    def ETF_KEYWORDS(self):
        return self.get("etf_keywords")

    @property
    def SECTOR_MAPPINGS(self):
        return self.get("sector_mappings")

    @property
    def SECTOR_MAPPING(self):
        return self.get("sector_mappings")

    @property
    def FONT_FAMILY(self):
        return self.get("font_family")

    @property
    def UNIFIED_NUMERIC_COLUMNS(self):
        return self.get("unified_numeric_columns")

    @property
    def VISUALIZATION(self):
        return self.get("visualization")

    @property
    def ANALYSIS_THRESHOLDS(self):
        return self.get("analysis_thresholds")

    @property
    def RISK_FREE_RATE(self):
        return self.get("risk_free_rate")

    @property
    def SBI_DOMESTIC_SKIP_ROWS(self):
        return self.get("sbi_domestic_skip_rows")

    @property
    def SBI_FOREIGN_SKIP_ROWS(self):
        return self.get("sbi_foreign_skip_rows")

    @property
    def TICKER_REGEX(self):
        return self.get("ticker_regex")

    @property
    def CURRENCY_NORMALIZATION(self):
        return self.get("currency_normalization")

    @property
    def BROKER_KEYWORDS(self):
        return self.get("broker_keywords")

    @property
    def PORTFOLIO_ANALYSIS(self):
        return self.get("portfolio_analysis")

    @property
    def REGION_KEYWORDS(self):
        return self.get("region_keywords")

    @property
    def ASSET_CLASS_KEYWORDS(self):
        return self.get("asset_class_keywords")

    # Column mappings for data standardization (kept inline as they're structural)
    COLUMN_MAPPINGS = {
        "rakuten_jp": {
            "約定日": "trade_date",
            "受渡日": "settlement_date",
            "銘柄コード": "security_code",
            "銘柄名": "security_name",
            "売買区分": "transaction_type",
            "数量［株］": "quantity",
            "単価［円］": "price",
            "受渡金額［円］": "settlement_amount",
            "口座区分": "account_type",
        },
        "rakuten_us": {
            "約定日": "trade_date",
            "受渡日": "settlement_date",
            "ティッカー": "security_code",
            "銘柄名": "security_name",
            "売買区分": "transaction_type",
            "数量［株］": "quantity",
            "単価［USドル］": "price",
            "受渡金額［円］": "settlement_amount",
            "口座": "account_type",
        },
        "rakuten_ch": {
            "約定日": "trade_date",
            "受渡日": "settlement_date",
            "銘柄コード": "security_code",
            "銘柄名": "security_name",
            "通貨": "currency",
            "売買区分": "transaction_type",
            "取引区分": "transaction_type",
            "信用区分": "margin_type",
            "数量［株］": "quantity",
            "単価": "price",
            "約定金額": "amount",
            "為替レート": "exchange_rate",
            "受渡金額［円］": "settlement_amount",
        },
        "rakuten_investment": {
            "約定日": "trade_date",
            "受渡日": "settlement_date",
            "ファンド名": "security_name",
            "取引": "transaction_type",
            "数量［口］": "quantity",
            "単価": "price",
            "受渡金額/(ポイント利用)[円]": "settlement_amount",
            "決済通貨": "currency",
            "口座": "account_type",
        },
        "sbi_domestic": {
            "約定日": "trade_date",
            "受渡日": "settlement_date",
            "銘柄コード": "security_code",
            "銘柄": "security_name",
            "取引": "transaction_type",
            "約定数量": "quantity",
            "約定単価": "price",
            "受渡金額/決済損益": "settlement_amount",
            "預り": "account_type",
        },
        "wise": {
            "完了日": "trade_date",
            "為替レート": "exchange_rate",
            "送金元通貨.1": "from_currency",
            "受取通貨": "to_currency",
            "送金額（手数料差し引き後）": "from_amount",
            "受取額（手数料差し引き後）": "to_amount",
        },
    }

    # Transaction type mappings (kept inline as they're structural)
    TRANSACTION_TYPE_MAPPINGS = {
        "buy": ["buy", "買付", "買", "買い", "再投資", "入庫", "積立", "定期積立"],
        "sell": ["sell", "売付", "売", "売り", "解約", "出庫"],
    }

    # Currency mappings (kept inline as they're structural)
    CURRENCY_MAPPINGS = {
        "JPY": ["JPY", "日本円", "円", "¥"],
        "USD": ["USD", "米国ドル", "米ドル", "USドル", "$"],
        "EUR": ["EUR", "ユーロ", "€"],
        "HKD": ["HKD", "香港ドル", "HK$"],
        "CNY": ["CNY", "中国元", "人民元"],
    }

    # Ticker mappings (kept inline as they're structural)
    TICKER_MAPPINGS = {
        "ACWI_FUND": "ACWI",
        "VWO_FUND": "VWO",
        "VOO_FUND": "VOO",
        "9984.T": "9984",
        "AAPL": "AAPL",
        "GOOGL": "GOOGL",
        "0700.HK": "700",
        "00700": "700",
    }

    # Fund name mappings (kept inline as they're structural)
    FUND_NAME_MAPPINGS = {
        "ACWI": ["emaxis slim 全世界", "sbi・全世界株式", "オール・カントリー"],
        "VWO": ["新興国株式"],
        "VOO": ["emaxis slim 米国", "s&p500", "s&p 500"],
        "VTI": ["全米株式", "楽天・全米株式"],
    }
