from pathlib import Path
from datetime import datetime
from collections import defaultdict
import pandas as pd
import logging

from src.analysis.unified_csv_analyzer import UnifiedCSVAnalyzer
from src.config import Config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

OUTPUT_PATH = Path("data/processed/portfolio_monthly_returns.csv")

def main():
    # 1. Load Data
    unified_path = Config.UNIFIED_DATA_DIR / "trades_unified.csv"
    if not unified_path.exists():
        logger.error(f"{unified_path} not found.")
        return

    analyzer = UnifiedCSVAnalyzer(str(unified_path))
    trades = analyzer.trades_df
    stock_manager = analyzer.stock_manager
    
    price_path = Config.MARKET_DATA_DIR / "charts.csv"
    if not price_path.exists(): price_path = Config.MARKET_DATA_DIR / "stock_prices.csv"
    
    logger.info(f"Loading prices from {price_path}...")
    price_data = stock_manager.load_stock_prices(price_path)
    if price_data.empty: return

    # 2. Filter & Prep
    available_tickers = set(price_data.columns)
    
    def is_trackable(row):
        code = row.get("security_code") or row.get("original_security_code")
        if not code: return False
        try:
            return stock_manager.process_security_code(str(code)) in available_tickers
        except: return False

    trades = trades[trades.apply(is_trackable, axis=1)].copy()
    if trades.empty: return

    meta = trades.groupby("security_code").first()[["currency", "is_investment_fund"]]
    trades.sort_values("trade_date", inplace=True)
    
    # 3. Calculate Returns (Incremental)
    start_date = trades["trade_date"].min()
    dates = pd.date_range(start=start_date, end=datetime.today(), freq="ME")
    
    holdings = defaultdict(float)
    prev_value = 0.0
    results = []
    
    for i, date in enumerate(dates):
        # Identify trades in this period (prev_date < t <= date)
        prev_date = dates[i-1] if i > 0 else pd.Timestamp.min
        period_mask = (trades["trade_date"] > prev_date) & (trades["trade_date"] <= date)
        period_tx = trades[period_mask]
        
        flow = 0.0
        for _, t in period_tx.iterrows():
            amt = t["amount_jpy"]
            code = t["security_code"]
            qty = t["quantity"]
            
            if t["transaction_type"] == "buy":
                holdings[code] += qty
                flow += amt
            elif t["transaction_type"] == "sell":
                holdings[code] -= qty
                flow -= amt
        
        # Valuation
        current_value = 0.0
        for code, qty in holdings.items():
            if qty <= 1e-4: continue
            
            price = stock_manager.get_price_on_date(price_data, date, str(code))
            if pd.isna(price): continue
            
            # Simple FX & Scaling
            usdjpy = stock_manager.get_price_on_date(price_data, date, "USDJPY=X") or 150.0
            cur = meta.loc[code]["currency"] if code in meta.index else "JPY"
            is_fund = meta.loc[code]["is_investment_fund"] if code in meta.index else False
            
            qty_calc = qty / 10000 if (is_fund and qty > 1000) else qty
            
            if cur in ["USD", "ＵＳドル"]: val = qty_calc * price * usdjpy
            elif cur in ["HKD", "HKドル"]: val = qty_calc * price * 20.0
            else: val = qty_calc * price
            
            current_value += val
            
        # Return Calculation (Simple Dietz)
        denom = prev_value + (flow / 2)
        ret = (current_value - prev_value - flow) / denom if (prev_value > 0 and denom > 0) else 0.0
        
        if abs(ret) > 2.0: # Winsorize
            logger.warning(f"Clipping return {ret:.2f} at {date.date()}")
            ret = 0.0
            
        results.append({"date": date, "strategy_return": ret})
        prev_value = current_value

    # 4. Save
    out = pd.DataFrame(results)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUTPUT_PATH, index=False)
    logger.info(f"Saved {len(out)} months. Mean Return: {out['strategy_return'].mean():.4f}")

if __name__ == "__main__":
    main()
