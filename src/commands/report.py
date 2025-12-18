"""Report command - Generate charts and comprehensive reports."""

import logging
from pathlib import Path

from src.analysis.unified_csv_analyzer import UnifiedCSVAnalyzer
from src.config import Config


def register(subparsers):
    """Register the report command."""
    parser = subparsers.add_parser(
        "report",
        help="[4] レポート出力: Generate charts and comprehensive reports",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(Config.REPORTS_DIR),
        help="Output directory for charts and reports",
    )
    parser.add_argument(
        "--charts-only",
        action="store_true",
        help="Generate only visualization charts",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Generate only summary report (no charts)",
    )
    parser.add_argument("--verbose", action="store_true", help="Verbose logging")
    parser.set_defaults(func=run)


def find_latest_unified_csv():
    """Find the latest unified CSV file."""
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
    """Generate reports and visualizations."""
    log_level = logging.INFO if args.verbose else logging.WARNING
    logging.basicConfig(level=log_level, format="%(asctime)s - %(levelname)s - %(message)s")
    logging.getLogger(__name__)

    # Find unified CSV
    csv_file, fund_mapping_file = find_latest_unified_csv()
    if not csv_file:
        print("❌ No unified CSV files found.")
        print("💡 Run 'task import' first to generate data.")
        return 1

    print(f"📊 Generating reports from: {csv_file.name}")

    try:
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize analyzer
        analyzer = UnifiedCSVAnalyzer(str(csv_file), str(fund_mapping_file) if fund_mapping_file else None)

        if args.summary_only:
            # Summary report only
            print("📝 Generating summary report...")
            report = analyzer.generate_comprehensive_report(str(output_dir))
            _print_summary(report)

        elif args.charts_only:
            # Charts only
            print("📈 Creating visualizations...")
            analyzer.create_advanced_visualizations(str(output_dir))
            print(f"✅ Charts saved to: {output_dir}")

        else:
            # Full reports: summary + charts
            print("📊 Generating comprehensive report...")
            report = analyzer.generate_comprehensive_report(str(output_dir))

            print("📈 Creating visualizations...")
            analyzer.create_advanced_visualizations(str(output_dir))

            _print_summary(report)
            print(f"\n📁 All outputs saved to: {output_dir}")

        print("✅ Report generation complete!")
        return 0

    except Exception as e:
        print(f"❌ Report generation failed: {str(e)}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1


def _print_summary(report: dict):
    """Print a summary of the report to console."""
    print(f"\n{'=' * 50}")
    print("📊 REPORT SUMMARY")
    print(f"{'=' * 50}")

    portfolio = report.get("portfolio_summary", {})
    perf = report.get("performance_metrics", {})

    print(f"  • Holdings: {portfolio.get('total_holdings', 'N/A')}")
    print(f"  • Portfolio Value: ¥{portfolio.get('total_portfolio_value_jpy', 0):,.0f}")
    print(f"  • Total Return: {perf.get('total_return_pct', 0):.2f}%")
    print(f"  • Sharpe Ratio: {perf.get('sharpe_ratio', 0):.2f}")
