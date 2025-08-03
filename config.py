"""Configuration management for trade history analysis."""

from pathlib import Path


class Config:
    """Configuration settings for the trade history analyzer."""
    
    # Base directory
    BASE_DIR = Path(__file__).parent
    
    # Data directories
    DATA_DIR = BASE_DIR / "data"
    RAW_DATA_DIR = DATA_DIR / "raw"
    PROCESSED_DATA_DIR = DATA_DIR / "processed"
    OUTPUT_DIR = DATA_DIR / "output"
    
    # Create directories if they don't exist
    @classmethod
    def ensure_directories(cls):
        """Ensure all required directories exist."""
        directories = [
            cls.DATA_DIR,
            cls.RAW_DATA_DIR,
            cls.PROCESSED_DATA_DIR,
            cls.OUTPUT_DIR,
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
        'rakuten_investment': '*INVST*.csv',
        'sbi_domestic': 'SaveFile*.csv',
        'sbi_foreign': 'yakujo*.csv',
        'wise': 'cleaned_wise_data*.csv'
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
        'buy': ['buy', '買付', '買', '買い', '再投資', '入庫'],
        'sell': ['sell', '売付', '売', '売り', '解約']
    }
    
    # Currency mappings
    CURRENCY_MAPPINGS = {
        'JPY': ['JPY', '日本円', '円'],
        'USD': ['USD', '米国ドル', '米ドル'],
        'EUR': ['EUR', 'ユーロ']
    }