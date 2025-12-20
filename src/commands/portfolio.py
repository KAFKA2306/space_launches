import pandas as pd
from src.analysis.unified_csv_analyzer import UnifiedCSVAnalyzer
from src.config import Config
from src.utils.helpers import setup_logging

def register(subparsers, command_name: str = "view"):
    """Register the view (portfolio) command."""
    parser = subparsers.add_parser(command_name, help="[2] ポートフォリオ確認: View current holdings and P&L")
    parser.set_defaults(func=run)

def run(args):
    logger = setup_logging()
    # Path resolution
    csv_path = Config.UNIFIED_DATA_DIR / "trades_unified.csv"
    fund_mapping = Config.UNIFIED_DATA_DIR / "fund_ticker_mapping.csv"

    if not csv_path.exists():
        logger.error(f"Unified data not found at {csv_path}. Run 'task import' first.")
        return 1

    # Use the specific UnifiedCSVAnalyzer which handles all data loading and logic
    analyzer = UnifiedCSVAnalyzer(str(csv_path), str(fund_mapping) if fund_mapping.exists() else None)

    # Logic to check if data exists
    if analyzer.trades_df.empty:
        logger.error("No unified data. Run 'task import' first.")
        return 1

    logger.info("Analyzing current portfolio state...")
    analyzer.analyze_current_holdings()
    
    holdings = analyzer.holdings_df
    
    if holdings.empty:
        print("No current holdings found.")
        return 0

    # Calculate Summary
    if "current_value_jpy" in holdings.columns:
        total_value = holdings["current_value_jpy"].fillna(0).sum()
        total_cost = holdings["total_cost_jpy"].sum()
        total_pnl = total_value - total_cost
        total_pnl_pct = (total_pnl / total_cost * 100) if total_cost else 0
    else:
        logger.warning("Market data missing ('current_value_jpy'), showing simple cost basis.")
        total_value = 0
        total_cost = holdings["total_cost_jpy"].sum()
        total_pnl = 0
        total_pnl_pct = 0

    print("\n" + "=" * 60)
    print("PORTFOLIO SUMMARY")
    print("=" * 60)
    if "current_value_jpy" in holdings.columns:
        print(f"Total Value:      ¥{total_value:,.0f}")
        print(f"Total Cost:       ¥{total_cost:,.0f}")
        print(f"Unrealized P&L:   ¥{total_pnl:,.0f} ({total_pnl_pct:+.2f}%)")
    else:
        print(f"Total Cost:       ¥{total_cost:,.0f}")
        print("Total Value:      (Market data unavailable)")
        print("Unrealized P&L:   (Market data unavailable)")
    print("\n" + "=" * 60)
    print("HOLDINGS")
    print("=" * 60)
    
    # formatting for print
    cols = ["symbol", "security_name", "quantity", "average_cost_jpy", "current_value_jpy", "unrealized_pnl_jpy", "unrealized_pnl_pct", "portfolio_weight"]
    # Ensure cols exist
    existing_cols = [c for c in cols if c in holdings.columns]
    
    display_df = holdings[existing_cols].copy()
    
    if "current_value_jpy" in display_df.columns:
        display_df["current_value_jpy"] = display_df["current_value_jpy"].map(lambda x: f"¥{x:,.0f}" if pd.notna(x) else "-")
    if "quantity" in display_df.columns:
        display_df["quantity"] = display_df["quantity"].map(lambda x: f"{x:,.0f}")
    if "unrealized_pnl_jpy" in display_df.columns:
        display_df["unrealized_pnl_jpy"] = display_df["unrealized_pnl_jpy"].map(lambda x: f"¥{x:,.0f}" if pd.notna(x) else "-")
    if "portfolio_weight" in display_df.columns:
        display_df["portfolio_weight"] = display_df["portfolio_weight"].map(lambda x: f"{x*100:.1f}%" if pd.notna(x) else "-")
        
    print(display_df.to_string(index=False))
    
    return 0
