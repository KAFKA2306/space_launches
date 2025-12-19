"""Simplified visualization utilities for trade analysis."""

import logging
from pathlib import Path
from typing import Dict

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from src.config import Config

logger = logging.getLogger(__name__)
logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)

# Modern style setup
plt.style.use("seaborn-v0_8-whitegrid")
sns.set_palette("husl")


class TradeVisualizer:
    """Create visualizations for trade analysis."""

    def __init__(self, config: Config = None):
        viz_cfg = Config.get("visualization", {})
        self.dpi = viz_cfg.get("dpi", 300)
        self.colors = viz_cfg.get("colors", {"positive": "green", "negative": "red"})
        self.alpha = viz_cfg.get("alpha", {"grid": 0.3, "bar": 0.7, "scatter": 0.6})
        self.fig_size = tuple(viz_cfg.get("figure_size_large", [16, 12]))
        self.top_n = viz_cfg.get("top_n_display", 10)

    def _format_jpy(self, ax, axis="y"):
        """Format axis with JPY abbreviations (M=million, K=thousand)."""
        from matplotlib.ticker import FuncFormatter

        fmt = FuncFormatter(lambda x, _: f"¥{x / 1e6:.1f}M" if x >= 1e6 else f"¥{x / 1e3:.0f}K")
        (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(fmt)

    def _safe_pie(self, ax, data: pd.Series, title: str):
        """Safe pie chart with fallback for empty data."""
        if data.empty or data.sum() == 0:
            ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
        else:
            ax.pie(data.values, labels=data.index, autopct="%1.1f%%", startangle=90)
        ax.set_title(title)

    def _color_by_sign(self, values) -> list:
        """Return green/red colors based on positive/negative values."""
        return [self.colors["positive"] if v > 0 else self.colors["negative"] for v in values]

    def plot_portfolio_overview(self, holdings_df: pd.DataFrame, summary: Dict, output_path: Path):
        """Create portfolio overview charts (4-panel)."""
        df = holdings_df.dropna(subset=["security_code"]).copy()
        # Use total_cost as fallback when current_value is missing or 0
        if "current_value" not in df.columns:
            df["current_value"] = df.get("total_cost", 0)
        df["current_value"] = df["current_value"].fillna(df.get("total_cost", 0))
        df.loc[df["current_value"] == 0, "current_value"] = df.loc[df["current_value"] == 0, "total_cost"]
        df = df[df["current_value"] > 0]
        if df.empty:
            logger.warning("No valid holdings data")
            return

        fig, axes = plt.subplots(2, 2, figsize=self.fig_size)
        fig.suptitle("Portfolio Overview", fontsize=16, fontweight="bold")

        # 1. Holdings pie
        top = df.nlargest(self.top_n, "current_value")
        self._safe_pie(axes[0, 0], top.set_index("security_code")["current_value"], "Top Holdings by Value")

        # 2. P&L bar
        if "total_pnl" in df.columns:
            pnl_data = df.nlargest(self.top_n, "total_pnl").dropna(subset=["total_pnl"])
            if not pnl_data.empty:
                axes[0, 1].bar(
                    pnl_data["security_code"], pnl_data["total_pnl"], color=self._color_by_sign(pnl_data["total_pnl"])
                )
                axes[0, 1].axhline(0, color="black", alpha=self.alpha["grid"])
                axes[0, 1].tick_params(axis="x", rotation=45)
                self._format_jpy(axes[0, 1])
        axes[0, 1].set_title("Top P&L by Security")

        # 3. Cost vs Value scatter
        if "total_cost" in df.columns:
            valid = df.dropna(subset=["total_cost", "current_value"])
            if not valid.empty and valid["total_cost"].max() > 0:
                axes[1, 0].scatter(valid["total_cost"], valid["current_value"], alpha=self.alpha["scatter"])
                max_val = max(valid["total_cost"].max(), valid["current_value"].max())
                axes[1, 0].plot([0, max_val], [0, max_val], "r--", alpha=0.5, label="Break-even")
                axes[1, 0].legend()
                self._format_jpy(axes[1, 0], "x")
                self._format_jpy(axes[1, 0], "y")
        axes[1, 0].set_title("Cost vs Current Value")
        axes[1, 0].set_xlabel("Total Cost")
        axes[1, 0].set_ylabel("Current Value")

        # 4. Summary text
        axes[1, 1].axis("off")
        if summary:
            text = f"""Portfolio Summary:
            
Total Value: ¥{summary.get("total_value", 0):,.0f}
Total Cost: ¥{summary.get("total_cost", 0):,.0f}
Total P&L: ¥{summary.get("total_pnl", 0):,.0f}
P&L %: {summary.get("total_pnl_percentage", 0):.2f}%

Realized P&L: ¥{summary.get("realized_pnl", 0):,.0f}
Unrealized P&L: ¥{summary.get("unrealized_pnl", 0):,.0f}

Holdings: {summary.get("number_of_holdings", 0)}"""
            axes[1, 1].text(
                0.1, 0.9, text, transform=axes[1, 1].transAxes, fontsize=12, va="top", fontfamily="monospace"
            )

        plt.tight_layout()
        plt.savefig(output_path, dpi=self.dpi, bbox_inches="tight")
        plt.close()
        logger.info(f"Portfolio overview saved to {output_path}")

    def plot_trading_activity(self, trades_df: pd.DataFrame, activity_summary: Dict, output_path: Path):
        """Create trading activity charts (4-panel)."""
        if trades_df.empty:
            logger.warning("No trading data")
            return

        df = trades_df.copy()
        df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce")
        df = df.dropna(subset=["trade_date"])
        amount_col = "amount_jpy" if "amount_jpy" in df.columns else "settlement_amount"

        fig, axes = plt.subplots(2, 2, figsize=self.fig_size)
        fig.suptitle("Trading Activity Analysis", fontsize=16, fontweight="bold")

        # 1. Monthly volume
        df["month"] = df["trade_date"].dt.to_period("M")
        monthly = df.groupby("month")[amount_col].sum()
        monthly.plot(kind="bar", ax=axes[0, 0])
        axes[0, 0].set_title("Monthly Trading Volume")
        axes[0, 0].tick_params(axis="x", rotation=45)
        self._format_jpy(axes[0, 0])

        # 2. Buy vs Sell pie
        self._safe_pie(axes[0, 1], df["transaction_type"].value_counts(), "Buy vs Sell")

        # 3. Most traded
        if "most_traded_securities" in activity_summary:
            top = pd.Series(activity_summary["most_traded_securities"]).head(self.top_n)
            top.plot(kind="barh", ax=axes[1, 0])
        axes[1, 0].set_title("Most Traded Securities")

        # 4. Amount distribution
        axes[1, 1].hist(df[amount_col].dropna(), bins=30, alpha=self.alpha["bar"], edgecolor="black")
        mean_val = df[amount_col].mean()
        axes[1, 1].axvline(mean_val, color="red", linestyle="--", label=f"Mean: ¥{mean_val:,.0f}")
        axes[1, 1].set_title("Trade Amount Distribution")
        axes[1, 1].legend()

        plt.tight_layout()
        plt.savefig(output_path, dpi=self.dpi, bbox_inches="tight")
        plt.close()
        logger.info(f"Trading activity saved to {output_path}")

    def plot_security_chart(
        self, security_code: str, trades_df: pd.DataFrame, price_data: pd.DataFrame, output_path: Path
    ):
        """Create individual security chart with price and trades."""
        sec_trades = trades_df[trades_df["security_code"] == security_code]
        if sec_trades.empty:
            logger.warning(f"No trades for {security_code}")
            return

        # Find price column
        price_col = next((c for c in price_data.columns if c == security_code or c.rstrip(".T") == security_code), None)
        if not price_col:
            logger.warning(f"No price data for {security_code}")
            return

        prices = price_data[price_col].dropna()
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), gridspec_kw={"height_ratios": [3, 1]})

        # Price line
        ax1.plot(prices.index, prices.values, "b-", alpha=0.8)
        ax1.set_title(f"{security_code} - Price & Trades", fontweight="bold")
        ax1.set_ylabel("Price")
        ax1.grid(True, alpha=self.alpha["grid"])

        # Trade markers
        for _, t in sec_trades.iterrows():
            color = self.colors["positive"] if t["transaction_type"] == "buy" else self.colors["negative"]
            marker = "^" if t["transaction_type"] == "buy" else "v"
            trade_date = t["trade_date"]

            if trade_date in prices.index:
                price_at = prices.loc[trade_date]
            else:
                prior = prices.index[prices.index <= trade_date]
                price_at = prices.loc[prior[-1]] if len(prior) else None

            if price_at is not None:
                ax1.scatter(
                    trade_date, price_at, c=color, marker=marker, s=100, alpha=0.8, edgecolors="black", linewidth=0.5
                )
                ax1.axvline(trade_date, color=color, alpha=self.alpha["grid"], linestyle="--")

        ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        ax1.xaxis.set_major_locator(mdates.MonthLocator(interval=3))

        # Volume bars
        amount_col = "amount_jpy" if "amount_jpy" in sec_trades.columns else "settlement_amount"
        colors = self._color_by_sign([1 if t == "buy" else -1 for t in sec_trades["transaction_type"]])
        ax2.bar(sec_trades["trade_date"], sec_trades[amount_col], color=colors, alpha=self.alpha["bar"], width=10)
        ax2.set_ylabel("Trade Amount")
        ax2.grid(True, alpha=self.alpha["grid"])
        ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))

        # Legend
        from matplotlib.lines import Line2D

        legend = [
            Line2D(
                [0], [0], marker="^", color="w", markerfacecolor=self.colors["positive"], markersize=10, label="Buy"
            ),
            Line2D(
                [0], [0], marker="v", color="w", markerfacecolor=self.colors["negative"], markersize=10, label="Sell"
            ),
        ]
        ax1.legend(handles=legend, loc="upper left")

        plt.tight_layout()
        plt.savefig(output_path, dpi=self.dpi, bbox_inches="tight")
        plt.close()
        logger.info(f"Security chart for {security_code} saved")

    def create_all_security_charts(
        self, trades_df: pd.DataFrame, price_data: pd.DataFrame, output_dir: Path, limit: int = 20
    ):
        """Create charts for top traded securities."""
        output_dir.mkdir(parents=True, exist_ok=True)
        top_securities = trades_df["security_code"].value_counts().head(limit).index

        for sec in top_securities:
            if pd.notna(sec):
                self.plot_security_chart(sec, trades_df, price_data, output_dir / f"{sec}_chart.png")

        logger.info(f"Created {len(top_securities)} security charts")

    def plot_performance_summary(self, performance_df: pd.DataFrame, output_path: Path):
        """Create performance summary charts (4-panel)."""
        if performance_df.empty:
            logger.warning("No performance data")
            return

        fig, axes = plt.subplots(2, 2, figsize=self.fig_size)
        fig.suptitle("Security Performance Analysis", fontsize=16, fontweight="bold")

        # 1. Top P&L
        top = performance_df.head(self.top_n)
        axes[0, 0].barh(top["security_code"], top["total_pnl"], color=self._color_by_sign(top["total_pnl"]))
        axes[0, 0].axvline(0, color="black", alpha=self.alpha["grid"])
        axes[0, 0].set_title("Top 10 by P&L")
        self._format_jpy(axes[0, 0], "x")

        # 2. Realized vs Unrealized
        axes[0, 1].scatter(
            performance_df["realized_pnl"], performance_df["unrealized_pnl"], alpha=self.alpha["scatter"]
        )
        axes[0, 1].axhline(0, color="black", linestyle="--", alpha=self.alpha["grid"])
        axes[0, 1].axvline(0, color="black", linestyle="--", alpha=self.alpha["grid"])
        axes[0, 1].set_title("Realized vs Unrealized P&L")
        self._format_jpy(axes[0, 1], "x")
        self._format_jpy(axes[0, 1], "y")

        # 3. Trade count distribution
        axes[1, 0].hist(performance_df["trades_count"], bins=20, alpha=self.alpha["bar"], edgecolor="black")
        axes[1, 0].set_title("Trading Frequency")

        # 4. Current holdings value
        current = performance_df[performance_df["current_shares"] > 0]
        if not current.empty:
            axes[1, 1].hist(current["current_value"], bins=20, alpha=self.alpha["bar"], edgecolor="black")
            self._format_jpy(axes[1, 1], "x")
        else:
            axes[1, 1].text(0.5, 0.5, "No current holdings", ha="center", va="center", transform=axes[1, 1].transAxes)
        axes[1, 1].set_title("Holdings Value Distribution")

        plt.tight_layout()
        plt.savefig(output_path, dpi=self.dpi, bbox_inches="tight")
        plt.close()
        logger.info(f"Performance summary saved to {output_path}")
