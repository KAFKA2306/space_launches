import pandas as pd

from src.analysis.unified_csv_analyzer import UnifiedCSVAnalyzer
from src.config import Config
from src.utils.helpers import setup_logging


def _format_currency(value, decimals=0):
    """Format value as JPY currency."""
    if pd.notna(value):
        return f"¥{value:,.{decimals}f}"
    return "-"


def _format_percent(value, multiplier=100):
    """Format value as percentage."""
    if pd.notna(value):
        return f"{value * multiplier:.1f}%"
    return "-"


def _format_column(df, col, formatter):
    """Apply formatter to column if it exists."""
    if col in df.columns:
        df[col] = df[col].map(formatter)


def register(subparsers, command_name: str = "view"):
    """Register the view (portfolio) command."""
    parser = subparsers.add_parser(command_name, help="[2] ポートフォリオ確認: View current holdings and P&L")
    parser.add_argument(
        "--sort",
        choices=["value", "percent", "pnl"],
        default="value",
        help="Sort order (default: value)",
    )
    parser.set_defaults(func=run)


def run(args):
    logger = setup_logging()
    csv_path = Config.UNIFIED_DATA_DIR / "trades_unified.csv"
    fund_mapping = Config.UNIFIED_DATA_DIR / "fund_ticker_mapping.csv"

    if not csv_path.exists():
        logger.error(f"Unified data not found at {csv_path}. Run 'task import' first.")
        return 1

    analyzer = UnifiedCSVAnalyzer(str(csv_path), str(fund_mapping) if fund_mapping.exists() else None)

    if analyzer.trades_df.empty:
        logger.error("No unified data. Run 'task import' first.")
        return 1

    logger.info("Analyzing current portfolio state...")
    analyzer.analyze_current_holdings()
    holdings = analyzer.holdings_df

    if holdings.empty:
        print("No current holdings found.")
        return 0

    # Calculate and display summary (consolidated logic)
    has_market_data = "current_value_jpy" in holdings.columns
    total_cost = holdings["total_cost_jpy"].sum()

    if has_market_data:
        total_value = holdings["current_value_jpy"].sum()
        total_pnl = total_value - total_cost
        total_pnl_pct = (total_pnl / total_cost * 100) if total_cost else 0
    else:
        logger.warning("Market data missing ('current_value_jpy'), showing simple cost basis.")
        total_value = total_cost
        total_pnl = 0
        total_pnl_pct = 0

    print("\n" + "=" * 60)
    print("PORTFOLIO SUMMARY")
    print("=" * 60)
    if has_market_data:
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

    # Format display columns using helpers
    cols = [
        "symbol",
        "currency",
        "security_name",
        "quantity",
        "current_price",
        "average_cost_jpy",
        "current_value_jpy",
        "unrealized_pnl_jpy",
        "unrealized_pnl_pct",
        "portfolio_weight",
    ]
    existing_cols = [c for c in cols if c in holdings.columns]
    
    # Sort options
    sort_key = "current_value_jpy"
    if args.sort == "percent" and "unrealized_pnl_pct" in holdings.columns:
        sort_key = "unrealized_pnl_pct"
    elif args.sort == "pnl" and "unrealized_pnl_jpy" in holdings.columns:
        sort_key = "unrealized_pnl_jpy"
        
    if sort_key in holdings.columns:
        holdings = holdings.sort_values(sort_key, ascending=False)
        
    display_df = holdings[existing_cols].copy()

    # Format without hardcoded Yen sign for raw price (it's in local currency)
    _format_column(display_df, "current_price", lambda x: f"{x:,.2f}" if pd.notna(x) else "-")
    
    # Keep Yen for JPY fields
    _format_column(display_df, "current_value_jpy", _format_currency)
    _format_column(display_df, "quantity", lambda x: f"{x:,.0f}")
    _format_column(display_df, "unrealized_pnl_jpy", _format_currency)
    _format_column(display_df, "portfolio_weight", _format_percent)

    print(display_df.to_string(index=False))
    return 0
