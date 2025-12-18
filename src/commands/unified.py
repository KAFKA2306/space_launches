import logging
from pathlib import Path

from src.analysis.unified_csv_analyzer import UnifiedCSVAnalyzer
from src.config import Config


def register(subparsers, command_name: str = "analyze"):
    """Register the analyze (unified analysis) command."""
    parser = subparsers.add_parser(command_name, help="[3] パフォーマンス分析: Analyze historical performance metrics")
    parser.add_argument(
        "--csv-file",
        type=str,
        help="Path to unified CSV file (default: latest in data/unified/)",
    )

    parser.add_argument(
        "--fund-mapping",
        type=str,
        help="Path to fund mapping file (auto-detected by default)",
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(Config.REPORTS_DIR / "unified_analysis"),
        help="Output directory for reports and charts",
    )

    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Generate report only, skip visualizations",
    )

    parser.add_argument("--charts-only", action="store_true", help="Generate charts only, skip report")

    parser.add_argument("--holdings-only", action="store_true", help="Analyze holdings only (fastest)")

    parser.add_argument("--verbose", action="store_true", help="Verbose logging")
    parser.set_defaults(func=run)


def find_latest_unified_csv(csv_dir: Path = None):
    """Find the latest unified CSV file"""
    if csv_dir is None:
        csv_dir = Config.UNIFIED_DATA_DIR

    if not csv_dir.exists():
        return None, None

    csv_files = list(csv_dir.glob("trades_unified_*.csv"))
    if not csv_files:
        return None, None

    latest_csv = max(csv_files, key=lambda x: x.stat().st_mtime)

    # Find corresponding fund mapping file
    fund_mapping_file = None
    timestamp = latest_csv.stem.split("_")[-2:]
    if len(timestamp) == 2:
        timestamp_str = "_".join(timestamp)
        fund_files = list(csv_dir.glob(f"fund_ticker_mapping_{timestamp_str}.csv"))
        if fund_files:
            fund_mapping_file = fund_files[0]

    return latest_csv, fund_mapping_file


def run(args):
    # Setup logging
    log_level = logging.INFO if args.verbose else logging.WARNING
    logging.basicConfig(level=log_level, format="%(asctime)s - %(levelname)s - %(message)s")
    logging.getLogger(__name__)

    # Find CSV file
    if args.csv_file:
        csv_file = Path(args.csv_file)
        fund_mapping_file = Path(args.fund_mapping) if args.fund_mapping else None
    else:
        csv_file, fund_mapping_file = find_latest_unified_csv()
        if not csv_file:
            print("❌ No unified CSV files found.")
            print("💡 Run 'task fetch' first.")
            return 1

    if not csv_file.exists():
        print(f"❌ CSV file not found: {csv_file}")
        return 1

    print(f"🔍 Analyzing: {csv_file.name}")
    if fund_mapping_file:
        print(f"📊 Using fund mapping: {fund_mapping_file.name}")

    try:
        # Initialize analyzer
        analyzer = UnifiedCSVAnalyzer(str(csv_file), str(fund_mapping_file) if fund_mapping_file else None)

        # Create output directory
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        if args.holdings_only:
            # Quick holdings analysis
            print("📈 Analyzing current holdings...")
            holdings = analyzer.analyze_current_holdings()

            if not holdings.empty:
                print("\n=== Holdings Summary ===")
                print(f"Total Holdings: {len(holdings)}")
                print(f"Portfolio Value: ¥{holdings['total_cost_jpy'].sum():,.0f}")
                print(f"Total Realized P&L: ¥{holdings['realized_pnl_jpy'].sum():,.0f}")

                # Top 5 holdings
                print("\n=== Top 5 Holdings ===")
                top5 = holdings.nlargest(5, "total_cost_jpy")
                for _, holding in top5.iterrows():
                    weight_pct = holding["portfolio_weight"] * 100
                    print(f"{holding['symbol']}: ¥{holding['total_cost_jpy']:,.0f} ({weight_pct:.1f}%)")
            else:
                print("No current holdings found.")

        elif args.report_only:
            # Generate report only
            print("📊 Generating comprehensive report...")
            report = analyzer.generate_comprehensive_report(str(output_dir))
            print(f"✅ Report saved to: {output_dir}")

        elif args.charts_only:
            # Generate charts only
            print("📈 Creating advanced visualizations...")
            analyzer.create_advanced_visualizations(str(output_dir))
            print(f"✅ Charts saved to: {output_dir}")

        else:
            # Full analysis
            print("🚀 Running comprehensive analysis...")

            # Generate report
            print("📊 Generating report...")
            report = analyzer.generate_comprehensive_report(str(output_dir))

            # Generate visualizations
            print("📈 Creating visualizations...")
            analyzer.create_advanced_visualizations(str(output_dir))

            # Print summary
            print(f"\n{'=' * 50}")
            print("🎯 ANALYSIS COMPLETE")
            print(f"{'=' * 50}")

            portfolio_summary = report["portfolio_summary"]
            performance = report["performance_metrics"]

            print("📊 Portfolio Overview:")
            print(f"  • Total Holdings: {portfolio_summary['total_holdings']}")
            print(f"  • Portfolio Value: ¥{portfolio_summary['total_portfolio_value_jpy']:,.0f}")
            print(f"  • Total Realized P&L: ¥{portfolio_summary['total_realized_pnl_jpy']:,.0f}")

            print("\n📈 Performance Metrics:")
            print(f"  • Total Return: {performance['total_return_pct']:.2f}%")
            print(f"  • Annualized Return: {performance['annualized_return_pct']:.2f}%")
            print(f"  • Volatility: {performance['volatility_pct']:.2f}%")
            print(f"  • Sharpe Ratio: {performance['sharpe_ratio']:.2f}")
            print(f"  • Max Drawdown: {performance['max_drawdown_pct']:.2f}%")

            # Asset allocation
            if report["asset_allocation"]["by_asset_class"]:
                print("\n🏷️  Asset Allocation:")
                for asset_class, pct in sorted(
                    report["asset_allocation"]["by_asset_class"].items(),
                    key=lambda x: x[1],
                    reverse=True,
                ):
                    print(f"  • {asset_class}: {pct:.1f}%")

            # Top holdings
            if report["top_holdings"]:
                print("\n🔝 Top Holdings:")
                for i, holding in enumerate(report["top_holdings"][:5], 1):
                    print(
                        f"  {i}. {holding['symbol']} - ¥{holding['total_cost_jpy']:,.0f} ({holding['portfolio_weight'] * 100:.1f}%)"
                    )

            print(f"\n📁 Output Directory: {output_dir}")
            print("✅ Analysis complete!")

        return 0

    except Exception as e:
        print(f"❌ Analysis failed: {str(e)}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1
