import logging
from pathlib import Path

import pandas as pd

from src.analysis.unified_csv_analyzer import UnifiedCSVAnalyzer
from src.config import Config
from src.fetch.pipeline import create_unified_csv
from src.fetch.status import PipelineStatus, write_pipeline_status
from src.utils.helpers import setup_logging


def register(subparsers, command_name: str = "analyze"):
    """Register the analyze (unified analysis) command."""
    parser = subparsers.add_parser(command_name, help="[3] パフォーマンス分析: Analyze historical performance metrics")
    parser.add_argument(
        "--csv-file",
        type=str,
        help="Path to unified CSV file (default: data/unified/trades_unified.csv)",
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

    parser.add_argument(
        "--compute",
        action="store_true",
        help="Compute holdings and write pipeline status (used by 'task run')",
    )

    parser.add_argument("--verbose", action="store_true", help="Verbose logging")
    parser.set_defaults(func=run)


def get_unified_csv_path() -> tuple[Path | None, Path | None]:
    """
    Get the fixed path to unified CSV file.
    Per design spec: No 'find_latest_xxx' patterns allowed.
    Returns (csv_path, fund_mapping_path) or (None, None) if not found.
    """
    csv_file = Config.UNIFIED_DATA_DIR / "trades_unified.csv"
    fund_file = Config.UNIFIED_DATA_DIR / "fund_ticker_mapping.csv"

    if csv_file.exists():
        return csv_file, fund_file if fund_file.exists() else None
    return None, None


def run(args):
    # Setup logging
    log_level = logging.INFO if args.verbose else logging.WARNING
    logging.basicConfig(level=log_level, format="%(asctime)s - %(levelname)s - %(message)s")

    config = Config()

    # --compute mode: Create unified CSV from raw + resources, write pipeline status
    if args.compute:
        logger = setup_logging()
        logger.info("=== Starting Compute Pipeline ===")
        status = PipelineStatus(mode="run")

        try:
            # 1. Load raw trades (interim should already exist from fetch:c)
            trades_path = config.TRADES_DATA_DIR / "trades.csv"
            if not trades_path.exists():
                logger.error(f"Trades not found: {trades_path}")
                logger.error("Run 'task fetch:c' first to load raw data into interim")
                status.errors_count += 1
                status.mark_complete()
                write_pipeline_status(status)
                return 1

            status.stage_raw_loaded = True
            logger.info(f"✅ Raw trades loaded from: {trades_path}")

            # 2. Check resources exist (forex, charts)
            forex_path = config.RESOURCES_DIR / "forex_data.csv"
            charts_path = config.RESOURCES_DIR / "charts.csv"
            resources_ok = forex_path.exists() and charts_path.exists()
            if resources_ok:
                status.stage_resources_read = True
                logger.info("✅ Resources available (forex + charts)")
            else:
                logger.warning("⚠ Some resources missing - unified will have gaps")

            # 3. Create unified CSV
            unified_path = create_unified_csv(config, logger)
            if unified_path:
                status.stage_unified_written = True
                try:
                    df = pd.read_csv(unified_path)
                    status.unified_rows = len(df)
                    status.unified_schema_ok = True
                    logger.info(f"✅ Unified CSV created: {unified_path}")
                except Exception:
                    pass
            else:
                status.errors_count += 1

            # 4. Write pipeline status
            status.mark_complete()
            status_file = write_pipeline_status(status)
            logger.info(f"✅ Pipeline status written: {status_file}")

            if status.is_success():
                print("✅ Compute pipeline completed successfully!")
                return 0
            else:
                print(f"⚠ Compute completed with {status.errors_count} errors")
                return 1

        except Exception as e:
            logger.error(f"Compute pipeline failed: {e}", exc_info=True)
            status.errors_count += 1
            status.mark_complete()
            write_pipeline_status(status)
            return 1

    # Find CSV file using fixed path (not find_latest pattern)
    if args.csv_file:
        csv_file = Path(args.csv_file)
        fund_mapping_file = Path(args.fund_mapping) if args.fund_mapping else None
    else:
        csv_file, fund_mapping_file = get_unified_csv_path()
        if not csv_file:
            print("❌ Unified CSV not found: data/unified/trades_unified.csv")
            print("💡 Run 'task run' first to generate the unified CSV.")
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
            # Full analysis (Text Only for 'metrics' command)
            print("🚀 Calculating performance metrics...")

            # Generate report data (but don't save unless explicit)
            # Note: We pass None as output_dir to prevent saving?
            # Actually generate_comprehensive_report saves if output_dir is passed.
            # But the args.output_dir has a default.
            # We will use report_generator directly or just skip the saving parts if possible.
            # UnifiedCSVAnalyzer.generate_comprehensive_report passes output_dir.
            # If we want to strictly avoid saving, we should ideally not pass output_dir or modify the analyzer.
            # However, for now, let's just generate the report to get the DICT, but we know it might save json/csvs.
            # The plan said "metrics: Show performance stats (text only). Stop generating files."
            # UnifiedCSVAnalyzer.generate_comprehensive_report calls self.report_generator.generate_comprehensive_report(output_dir)
            # which definitely saves things.
            #
            # WORKAROUND: We will manually call the analysis methods and print the summary,
            # avoiding generate_comprehensive_report() which saves files.

            # 1. Analyze holdings (fills self.holdings_df)
            analyzer.analyze_current_holdings()

            # 2. Performance Metrics
            perf_metrics = analyzer.calculate_performance_metrics()

            # 3. Asset Allocation
            allocation = analyzer.analyze_asset_allocation()

            # 4. Top Holdings
            top_holdings = []
            if analyzer.holdings_df is not None and not analyzer.holdings_df.empty:
                top_sorted = analyzer.holdings_df.sort_values("portfolio_weight", ascending=False).head(10)
                top_holdings = top_sorted.to_dict("records")

            # 5. Portfolio Summary Stats
            total_value = analyzer.holdings_df["current_value_jpy"].sum() if not analyzer.holdings_df.empty else 0
            total_realized = analyzer.holdings_df["realized_pnl_jpy"].sum() if not analyzer.holdings_df.empty else 0

            # Construct report dict for printing logic below
            report = {
                "portfolio_summary": {
                    "total_holdings": len(analyzer.holdings_df) if analyzer.holdings_df is not None else 0,
                    "total_portfolio_value_jpy": total_value,
                    "total_realized_pnl_jpy": total_realized,
                },
                "performance_metrics": {
                    "total_return_pct": perf_metrics.total_return,
                    "annualized_return_pct": perf_metrics.annualized_return,
                    "volatility_pct": perf_metrics.volatility,
                    "sharpe_ratio": perf_metrics.sharpe_ratio,
                    "max_drawdown_pct": perf_metrics.max_drawdown,
                },
                "asset_allocation": {"by_asset_class": allocation.by_asset_class},
                "top_holdings": top_holdings,
            }
            # Skip visualization creation
            # analyzer.create_advanced_visualizations(str(output_dir))

            # Print summary
            print(f"\n{'=' * 50}")
            print("🎯 METRICS SUMMARY")
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
