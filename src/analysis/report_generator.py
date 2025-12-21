"""Report generation and visualization for portfolio analysis."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict

import matplotlib.pyplot as plt
import numpy as np

from src.config import Config

logger = logging.getLogger(__name__)

# Configure matplotlib
plt.rcParams["font.family"] = Config.get("font_family")


class ReportGenerator:
    """Generates reports and visualizations from analysis data."""

    def __init__(self, analyzer):
        """Initialize with reference to analyzer for data access."""
        self.analyzer = analyzer

    def generate_comprehensive_report(self, output_dir: str = None) -> Dict:
        """Generate comprehensive analysis report."""
        logger.info("Generating comprehensive report...")

        output_dir = Path(output_dir) if output_dir else Path("data/output/analysis_reports")
        output_dir.mkdir(parents=True, exist_ok=True)

        a = self.analyzer
        holdings = a.analyze_current_holdings()
        performance = a.calculate_performance_metrics()
        allocation = a.analyze_asset_allocation()
        insights = a.generate_trading_insights()
        risk_metrics = a.analyze_risk_metrics()
        trading_behavior = a.analyze_trading_behavior()
        recommendations = a.generate_investment_recommendations()

        report = {
            "analysis_date": datetime.now().isoformat(),
            "data_source": str(a.unified_csv_path),
            "portfolio_summary": {
                "total_holdings": len(holdings),
                "total_portfolio_value_jpy": holdings["total_cost_jpy"].sum() if not holdings.empty else 0,
                "total_realized_pnl_jpy": holdings["realized_pnl_jpy"].sum() if not holdings.empty else 0,
            },
            "performance_metrics": {
                "total_return_pct": performance.total_return,
                "annualized_return_pct": performance.annualized_return,
                "volatility_pct": performance.volatility,
                "sharpe_ratio": performance.sharpe_ratio,
                "max_drawdown_pct": performance.max_drawdown,
                "calmar_ratio": performance.calmar_ratio,
                "win_rate_pct": performance.win_rate,
                "profit_factor": performance.profit_factor,
            },
            "asset_allocation": {
                "by_asset_class": allocation.by_asset_class,
                "by_currency": allocation.by_currency,
                "by_region": allocation.by_region,
                "by_account_type": allocation.by_account_type,
            },
            "risk_analysis": risk_metrics,
            "trading_behavior": trading_behavior,
            "investment_recommendations": recommendations,
            "trading_insights": insights,
            "top_holdings": holdings.nlargest(10, "total_cost_jpy")[
                ["symbol", "security_name", "total_cost_jpy", "portfolio_weight", "asset_class", "region"]
            ].to_dict("records")
            if not holdings.empty
            else [],
        }

        report_file = output_dir / "comprehensive_analysis.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)

        logger.info(f"Comprehensive report saved to: {report_file}")
        return report

    def create_advanced_visualizations(self, output_dir: str = None):
        """Create advanced visualization suite."""
        logger.info("Creating advanced visualizations...")
        output_dir = Path(output_dir) if output_dir else Path("data/output/advanced_charts")
        output_dir.mkdir(parents=True, exist_ok=True)

        a = self.analyzer
        if a.holdings_df is None:
            a.analyze_current_holdings()

        plt.style.use("seaborn-v0_8-whitegrid")
        viz_cfg = Config.get("visualization", {})
        dpi = viz_cfg.get("dpi", 300)

        self._create_dashboard(output_dir, dpi)
        self._create_allocation_chart(output_dir, dpi)
        self._create_timeline_chart(output_dir, dpi)
        self._create_performance_chart(output_dir, dpi)

        logger.info(f"Visualizations saved to: {output_dir}")

    def _create_dashboard(self, output_dir: Path, dpi: int):
        """Create portfolio dashboard (6-panel)."""
        df = self.analyzer.holdings_df
        if df.empty:
            return

        fig, axes = plt.subplots(2, 3, figsize=(20, 12))
        fig.suptitle("Portfolio Dashboard", fontsize=16, fontweight="bold")

        top = df.nlargest(10, "total_cost_jpy")
        axes[0, 0].barh(top["symbol"].astype(str), top["total_cost_jpy"])
        axes[0, 0].set_title("Top Holdings")

        for col, ax, title in [("asset_class", axes[0, 1], "Asset Class"), ("region", axes[0, 2], "Region")]:
            data = df.groupby(col)["total_cost_jpy"].sum()
            ax.pie(data.values, labels=data.index, autopct="%1.1f%%")
            ax.set_title(title)

        acct = df.groupby("account_type")["total_cost_jpy"].sum()
        axes[1, 0].bar(acct.index, acct.values)
        axes[1, 0].tick_params(axis="x", rotation=45)
        axes[1, 0].set_title("By Account")

        axes[1, 1].hist(df["holding_period_days"], bins=20, alpha=0.7)
        axes[1, 1].set_title("Holding Period")

        wts = df["portfolio_weight"].sort_values(ascending=False)
        axes[1, 2].plot(range(1, len(wts) + 1), wts.cumsum())
        axes[1, 2].set_title("Concentration")
        axes[1, 2].grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig(output_dir / "portfolio_dashboard.png", dpi=dpi, bbox_inches="tight")
        plt.close()

    def _create_allocation_chart(self, output_dir: Path, dpi: int):
        """Create asset allocation chart (4-panel)."""
        df = self.analyzer.holdings_df
        if df.empty:
            return

        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle("Asset Allocation", fontsize=16, fontweight="bold")

        for col, ax, title in [("asset_class", axes[0, 0], "Asset Class"), ("region", axes[0, 1], "Region")]:
            data = df.groupby(col)["total_cost_jpy"].sum().sort_values()
            ax.barh(data.index, data.values)
            ax.set_title(title)

        curr = df.groupby("currency")["total_cost_jpy"].sum()
        axes[1, 0].pie(curr.values, labels=curr.index, autopct="%1.1f%%")
        axes[1, 0].set_title("Currency")

        fund = df.groupby("is_fund")["total_cost_jpy"].sum()
        axes[1, 1].pie(fund.values, labels=["Direct" if not x else "Funds" for x in fund.index], autopct="%1.1f%%")
        axes[1, 1].set_title("Vehicle")

        plt.tight_layout()
        plt.savefig(output_dir / "asset_allocation.png", dpi=dpi, bbox_inches="tight")
        plt.close()

    def _create_timeline_chart(self, output_dir: Path, dpi: int):
        """Create trading timeline chart (3-panel)."""
        trades = self.analyzer.trades_df

        fig, axes = plt.subplots(3, 1, figsize=(16, 12))
        fig.suptitle("Trading Timeline", fontsize=16, fontweight="bold")

        monthly = trades.groupby(trades["trade_date"].dt.to_period("M"))

        vol = monthly["amount_jpy"].sum()
        axes[0].plot(vol.index.to_timestamp(), vol.values, marker="o")
        axes[0].set_title("Monthly Volume")
        axes[0].grid(True, alpha=0.3)

        cnt = monthly.size()
        axes[1].bar(cnt.index.to_timestamp(), cnt.values, width=20)
        axes[1].set_title("Trade Count")
        axes[1].grid(True, alpha=0.3)

        cum = trades.set_index("trade_date")["amount_jpy"].cumsum()
        axes[2].plot(cum.index, cum.values)
        axes[2].set_title("Cumulative")
        axes[2].grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig(output_dir / "trading_timeline.png", dpi=dpi, bbox_inches="tight")
        plt.close()

    def _create_performance_chart(self, output_dir: Path, dpi: int):
        """Create performance chart (4-panel)."""
        daily = self.analyzer._calculate_daily_portfolio_values()
        rets = daily.pct_change().dropna()

        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle("Performance", fontsize=16, fontweight="bold")

        axes[0, 0].plot(daily.index, daily.values)
        axes[0, 0].set_title("Portfolio Value")
        axes[0, 0].grid(True, alpha=0.3)

        axes[0, 1].hist(rets * 100, bins=50, alpha=0.7)
        axes[0, 1].set_title("Returns Distribution")
        axes[0, 1].grid(True, alpha=0.3)

        cumret = (1 + rets).cumprod()
        dd = (cumret - cumret.expanding().max()) / cumret.expanding().max()
        axes[1, 0].fill_between(dd.index, dd * 100, 0, alpha=0.3, color="red")
        axes[1, 0].set_title("Drawdown")
        axes[1, 0].grid(True, alpha=0.3)

        vol = rets.rolling(30).std() * np.sqrt(252) * 100
        axes[1, 1].plot(vol.index, vol.values)
        axes[1, 1].set_title("30D Volatility")
        axes[1, 1].grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig(output_dir / "performance_analytics.png", dpi=dpi, bbox_inches="tight")
        plt.close()
