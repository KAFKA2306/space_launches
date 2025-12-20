import pandas as pd
from src.config import Config
from src.market.stocks import StockDataManager
import sys
import os

# Modify sys path to include current dir
sys.path.append(os.getcwd())

# Load prices
price_file = Config.MARKET_DATA_DIR / "stock_prices.csv"
print(f"Loading prices from {price_file}")
try:
    df = pd.read_csv(price_file, index_col=0, parse_dates=True)
    print(f"Shape: {df.shape}")
    
    if "MSTR" in df.columns:
        print(f"MSTR last 5:\n{df['MSTR'].tail()}")
        
        # Test get_latest_prices logic
        latest = df.ffill().iloc[-1]
        print(f"MSTR latest (ffill): {latest.get('MSTR')}")
    else:
        print("MSTR not in columns")
except Exception as e:
    print(f"Error loading prices: {e}")

# Load trades
trades_file = Config.UNIFIED_DATA_DIR / "trades_unified.csv"
print(f"Loading trades from {trades_file}")
try:
    trades = pd.read_csv(trades_file)
    mstr_trade = trades[trades["security_code"] == "MSTR"]
    if not mstr_trade.empty:
        print("MSTR Trade Sample:")
        print(mstr_trade.iloc[0][["security_code", "is_investment_fund", "transaction_type", "quantity", "amount_jpy_unified"]])
    else:
        print("MSTR not found in trades")
except Exception as e:
    print(f"Error loading trades: {e}")
