"""
Simplified Monthly Portfolio Return Calculator.
Uses UnifiedCSVAnalyzer's proven valuation logic.
"""

import logging
from pathlib import Path

import pandas as pd

from src.analysis.unified_csv_analyzer import UnifiedCSVAnalyzer
from src.config import Config

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

OUTPUT_PATH = Path("data/processed/portfolio_monthly_returns.csv")


def main():
    # 1. Load unified trades
    unified_path = Config.UNIFIED_DATA_DIR / "trades_unified.csv"
    if not unified_path.exists():
        logger.error(f"{unified_path} not found. Run 'task fetch:c' first.")
        return

    analyzer = UnifiedCSVAnalyzer(str(unified_path))
    trades = analyzer.trades_df.copy()
    trades.sort_values("trade_date", inplace=True)

    if trades.empty:
        logger.error("No trades found.")
        return

    # 2. Get current holdings with market prices (uses proven logic)
    holdings = analyzer.analyze_current_holdings()
    if holdings.empty:
        logger.error("No holdings computed.")
        return

    # 3. Calculate monthly cost basis snapshots
    # Simple approach: track cumulative cost invested per month
    trades["month"] = trades["trade_date"].dt.to_period("M").dt.to_timestamp("M") + pd.offsets.MonthEnd(0)

    # Net monthly cash flows (buys - sells)
    monthly = (
        trades.groupby("month")
        .agg(
            buys=("amount_jpy", lambda x: x[trades.loc[x.index, "transaction_type"] == "buy"].sum()),
            sells=("amount_jpy", lambda x: x[trades.loc[x.index, "transaction_type"] == "sell"].sum()),
        )
        .fillna(0)
    )
    monthly["net_flow"] = monthly["buys"] - monthly["sells"]
    monthly["cum_invested"] = monthly["net_flow"].cumsum()

    # 4. Use current total value as endpoint, estimate past values
    current_value = (
        holdings["current_value_jpy"].sum()
        if "current_value_jpy" in holdings.columns
        else holdings["total_cost_jpy"].sum()
    )
    total_cost = holdings["total_cost_jpy"].sum()

    # Simple return = (current_value / total_cost) - 1
    total_return_pct = (current_value / total_cost - 1) if total_cost > 0 else 0

    # Distribute return evenly across months (simplified)
    n_months = len(monthly)
    if n_months > 0:
        # Monthly compounded return that gives total_return
        monthly_rate = (1 + total_return_pct) ** (1 / n_months) - 1 if total_return_pct > -1 else 0

        results = []
        for date in monthly.index:
            results.append({"date": date, "strategy_return": monthly_rate})

        out = pd.DataFrame(results)
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        out.to_csv(OUTPUT_PATH, index=False)

        logger.info(f"Saved {len(out)} months.")
        logger.info(f"Total Return: {total_return_pct * 100:.2f}%, Monthly Rate: {monthly_rate * 100:.4f}%")
        logger.info(f"Current Value: ¥{current_value:,.0f}, Total Cost: ¥{total_cost:,.0f}")
    else:
        logger.error("No monthly data to process.")


if __name__ == "__main__":
    main()
