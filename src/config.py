"""Configuration management for trade history analysis."""

from pathlib import Path


class Config:
    """Configuration settings for the trade history analyzer."""
    
    # Base directory (project root)
    BASE_DIR = Path(__file__).parent.parent
    
    # Data directories
    DATA_DIR = BASE_DIR / "data"
    RAW_DATA_DIR = DATA_DIR / "raw"
    PROCESSED_DATA_DIR = DATA_DIR / "processed"
    OUTPUT_DIR = DATA_DIR / "output"
    
    # Resources directory (formerly DIC)
    RESOURCES_DIR = BASE_DIR / "resources"
    
    # Create directories if they don't exist
    @classmethod
    def ensure_directories(cls):
        """Ensure all required directories exist."""
        directories = [
            cls.DATA_DIR,
            cls.RAW_DATA_DIR,
            cls.PROCESSED_DATA_DIR,
            cls.OUTPUT_DIR,
            cls.RESOURCES_DIR,
        ]
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    # Market data settings
    FOREX_PAIRS = ['USDJPY=X', 'EURJPY=X']
    MARKET_START_DATE = '2018-01-01'
    
    # File patterns for different brokers
    BROKER_PATTERNS = {
        'rakuten_jp': '*JP*.csv',
        'rakuten_us': '*US*.csv', 
        'rakuten_ch': '*CH*.csv',
        'rakuten_investment': '*INVST*.csv',
        'sbi_domestic': 'SaveFile*.csv',
        'sbi_foreign': 'yakujo*.csv',
        'wise': 'cleaned_wise_data*.csv',
        'portfolio': 'assetbalance*.csv'
    }
    
    # Column mappings for data standardization
    COLUMN_MAPPINGS = {
        'rakuten_jp': {
            '約定日': 'trade_date',
            '受渡日': 'settlement_date',
            '銘柄コード': 'security_code',
            '銘柄名': 'security_name',
            '売買区分': 'transaction_type',
            '数量［株］': 'quantity',
            '単価［円］': 'price',
            '受渡金額［円］': 'settlement_amount',
            '口座区分': 'account_type'
        },
        'rakuten_us': {
            '約定日': 'trade_date',
            '受渡日': 'settlement_date',
            'ティッカー': 'security_code',
            '銘柄名': 'security_name',
            '売買区分': 'transaction_type',
            '数量［株］': 'quantity',
            '単価［USドル］': 'price',
            '受渡金額［円］': 'settlement_amount',
            '口座': 'account_type'
        },
        'rakuten_ch': {
            '約定日': 'trade_date',
            '受渡日': 'settlement_date',
            '銘柄コード': 'security_code',
            '銘柄名': 'security_name',
            '通貨': 'currency',
            '売買区分': 'transaction_type',
            '信用区分': 'margin_type',
            '数量［株］': 'quantity',
            '単価': 'price',
            '約定金額': 'amount',
            '為替レート': 'exchange_rate',
            '受渡金額［円］': 'settlement_amount'
        },
        'rakuten_investment': {
            '約定日': 'trade_date',
            '受渡日': 'settlement_date',
            'ファンド名': 'security_name',
            '取引': 'transaction_type',
            '数量［口］': 'quantity',
            '単価': 'price',
            '受渡金額/(ポイント利用)[円]': 'settlement_amount',
            '決済通貨': 'currency',
            '口座': 'account_type'
        },
        'sbi_domestic': {
            '約定日': 'trade_date',
            '受渡日': 'settlement_date',
            '銘柄コード': 'security_code',
            '銘柄': 'security_name',
            '取引': 'transaction_type',
            '約定数量': 'quantity',
            '約定単価': 'price',
            '受渡金額/決済損益': 'settlement_amount',
            '預り': 'account_type'
        },
        'wise': {
            '完了日': 'trade_date',
            '為替レート': 'exchange_rate',
            '送金元通貨.1': 'from_currency',
            '受取通貨': 'to_currency',
            '送金額（手数料差し引き後）': 'from_amount',
            '受取額（手数料差し引き後）': 'to_amount'
        }
    }
    
    # Transaction type mappings
    TRANSACTION_TYPE_MAPPINGS = {
        'buy': ['buy', '買付', '買', '買い', '再投資', '入庫', '積立', '定期積立'],
        'sell': ['sell', '売付', '売', '売り', '解約', '出庫']
    }
    
    # Currency mappings
    CURRENCY_MAPPINGS = {
        'JPY': ['JPY', '日本円', '円', '¥'],
        'USD': ['USD', '米国ドル', '米ドル', 'USドル', '$'],
        'EUR': ['EUR', 'ユーロ', '€'],
        'HKD': ['HKD', '香港ドル', 'HK$'],
        'CNY': ['CNY', '中国元', '人民元']
    }
    
    # Alternative data sources configuration
    ALTERNATIVE_DATA_SOURCES = {
        'default_sources': ['stooq'],  # STOOQ first for Japanese stocks
        'rate_limit_seconds': 1.5,     # Faster for STOOQ
        'request_timeout': 30,
        'retry_count': 3,
        'max_symbols_per_batch': 50
    }
    
    # JSON export settings
    JSON_EXPORT = {
        'enable_auto_export': True,
        'export_directory': 'json_data',
        'include_metadata': True,
        'pretty_print': True
    }
    
    # API configuration (use environment variables for actual keys)
    API_KEYS = {
        'alpha_vantage_key': None,  # Set via ALPHA_VANTAGE_API_KEY env var
        'polygon_key': None,        # Set via POLYGON_API_KEY env var
        'iex_key': None            # Set via IEX_API_KEY env var
    }
    
    # Historical data settings
    HISTORICAL_DATA = {
        'default_start_date': '2020-01-01',
        'max_days_per_request': 365,
        'enable_caching': True,
        'cache_directory': 'historical_cache'
    }
