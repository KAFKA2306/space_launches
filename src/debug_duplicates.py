import pandas as pd
from src.config import Config
import sys
import os

sys.path.append(os.getcwd())

price_file = Config.MARKET_DATA_DIR / "stock_prices.csv"
try:
    df = pd.read_csv(price_file, index_col=0, parse_dates=True)
    duplicates = df.columns[df.columns.duplicated()].tolist()
    if duplicates:
        print(f"FAILED: Found duplicate columns: {duplicates}")
    else:
        print("SUCCESS: No duplicate columns found")
        
    # Check USDJPY explicitly
    if "USDJPY=X" in df.columns:
        val = df["USDJPY=X"]
        print(f"USDJPY=X shape: {val.shape}")
        if len(val.shape) > 1:
            print("USDJPY=X is duplicated!")

except Exception as e:
    print(f"Error: {e}")
