import asyncio
import logging

import pandas as pd
import yfinance as yf

from src.analysis.unified_csv_analyzer import UnifiedCSVAnalyzer
from src.config import Config

logger = logging.getLogger(__name__)

# Caching for analyzer
_analyzer_cache = {"instance": None, "last_load": 0}


def get_analyzer():
    """Get analyzer instance with caching."""
    global _analyzer_cache
    csv_path = Config.UNIFIED_DATA_DIR / "trades_unified.csv"
    fund_mapping = Config.BASE_DIR / "resources" / "fund_dictionary.json"

    if not csv_path.exists():
        return None

    mtime = csv_path.stat().st_mtime
    if _analyzer_cache["instance"] and _analyzer_cache["last_load"] >= mtime:
        return _analyzer_cache["instance"]

    logger.info("Reloading UnifiedCSVAnalyzer")
    analyzer = UnifiedCSVAnalyzer(str(csv_path), str(fund_mapping) if fund_mapping.exists() else None)
    _analyzer_cache = {"instance": analyzer, "last_load": mtime}
    return analyzer


def calculate_summary(holdings: pd.DataFrame) -> dict:
    """Calculate portfolio summary metrics."""
    if holdings.empty:
        return {}

    val_col = "current_value_jpy" if "current_value_jpy" in holdings.columns else "total_cost_jpy"
    # Ensure numeric and fill
    total_val_series = (
        pd.to_numeric(holdings[val_col], errors="coerce").fillna(holdings["total_cost_jpy"])
        if "current_value_jpy" in holdings.columns
        else holdings[val_col]
    )
    total_value = total_val_series.sum()

    realized_pnl = holdings["realized_pnl_jpy"].sum()
    total_cost = holdings["total_cost_jpy"].sum()

    # Unrealized P&L
    unrealized_pnl = (total_value - total_cost) if "current_value_jpy" in holdings.columns else 0

    # Avoid division by zero
    total_invested = total_value - unrealized_pnl
    pnl_pct = (unrealized_pnl / total_invested * 100) if total_invested > 0 else 0

    return {
        "total_holdings": len(holdings),
        "total_value": total_value,
        "total_realized_pnl": realized_pnl,
        "total_unrealized_pnl": unrealized_pnl,
        "pnl_pct": pnl_pct,
    }


def filter_and_sort_holdings(df: pd.DataFrame, q: str, sort: str) -> pd.DataFrame:
    """Filter and sort holdings DataFrame."""
    if q:
        # Vectorized string search
        q = q.lower()
        mask = df["symbol"].astype(str).str.lower().str.contains(q, na=False) | df["security_name"].astype(
            str
        ).str.lower().str.contains(q, na=False)
        df = df[mask]

    # Sort logic map
    sort_map = {
        "value": ("current_value_jpy" if "current_value_jpy" in df.columns else "total_cost_jpy"),
        "percent": "unrealized_pnl_pct",
        "pnl": "unrealized_pnl_jpy",
        "name": "symbol",
    }
    col = sort_map.get(sort, sort_map["value"])

    if col in df.columns:
        df = df.sort_values(col, ascending=(sort == "name"))

    return df


def filter_trades(df: pd.DataFrame, q: str) -> pd.DataFrame:
    """Filter trades DataFrame."""
    if q:
        # Vectorized string search
        q = q.lower()
        # Search in security_code (ticker), security_name, and original_security_code
        mask = (
            df["security_code"].astype(str).str.lower().str.contains(q, na=False)
            | df["security_name"].astype(str).str.lower().str.contains(q, na=False)
            | df["original_security_code"].astype(str).str.lower().str.contains(q, na=False)
        )
        df = df[mask]

    return df


async def fetch_realtime_prices(holdings: pd.DataFrame) -> dict:
    """Fetch real-time prices for key holdings."""
    if holdings.empty:
        return {"error": "No holdings"}

    # Filter symbols: exclude funds (is_fund==True), exclude USDJPY, exclude digit-only (unless needed, but usually .T)
    # The main.py logic had `~holdings["is_fund"]`
    df_stocks = holdings[~holdings["is_fund"]]
    symbols = df_stocks["symbol"].head(20).tolist()

    # Cleaning
    valid_symbols = [s for s in symbols if not s.startswith("USDJPY") and not s.isdigit()][:10]

    def fetch():
        try:
            if not valid_symbols:
                return {}

            tickers = yf.Tickers(" ".join(valid_symbols))
            prices = {}
            for sym in valid_symbols:
                info = tickers.tickers[sym].fast_info
                # Use getattr for safety, yfinance fast_info behavior varies
                last = getattr(info, "last_price", None)
                prev = getattr(info, "previous_close", None)
                if last:
                    prices[sym] = {
                        "price": round(last, 2),
                        "change": round(last - prev, 2) if prev else None,
                        "change_pct": round((last - prev) / prev * 100, 2) if prev else None,
                    }
                else:
                    prices[sym] = {"price": None}
            return prices
        except Exception as e:
            return {"error": str(e)}

    loop = asyncio.get_event_loop()
    prices = await loop.run_in_executor(None, fetch)
    return {"prices": prices, "symbols": valid_symbols}


def calculate_kpis() -> dict:
    """Calculate portfolio KPIs from monthly returns and FF5 results."""
    from pathlib import Path

    import numpy as np

    kpis = {"performance": {}, "ff5": {}, "available": False}

    # Load monthly returns
    returns_path = Path("data/processed/portfolio_monthly_returns.csv")
    if returns_path.exists():
        try:
            df = pd.read_csv(returns_path)
            if "strategy_return" in df.columns and len(df) > 1:
                r = df["strategy_return"].dropna()

                # Sharpe: (mean_excess / std) * sqrt(12)
                # Assuming ~0.3% monthly risk-free rate (~3.6% annual)
                rf_monthly = 0.003
                excess = r - rf_monthly
                kpis["performance"]["sharpe"] = (
                    round((excess.mean() / excess.std()) * np.sqrt(12), 2) if excess.std() > 0 else 0
                )

                # MaxDD: from wealth curve (1 + r).cumprod()
                wealth = (1 + r).cumprod()
                peak = wealth.cummax()
                drawdown = (wealth - peak) / peak
                kpis["performance"]["max_drawdown"] = round(drawdown.min() * 100, 2)

                # Total return: compounded
                kpis["performance"]["total_return"] = round((wealth.iloc[-1] - 1) * 100, 2)
                kpis["performance"]["months"] = len(r)
                kpis["available"] = True
        except Exception as e:
            logger.warning(f"Failed to load returns: {e}")

    # Load FF5 results
    ff5_path = Path("ff5_report.csv")
    if ff5_path.exists():
        try:
            df = pd.read_csv(ff5_path)
            factors = ["Alpha", "MKT", "SMB", "HML", "RMW", "CMA"]
            for factor in factors:
                row = df[df["Factor"] == factor]
                if not row.empty:
                    kpis["ff5"][factor.lower()] = {
                        "coef": round(float(row["Coef"].iloc[0]) * 100, 2),
                        "t": round(float(row["t"].iloc[0]), 2),
                    }
            if df["R2"].notna().any():
                kpis["ff5"]["r2"] = round(float(df["R2"].iloc[0]) * 100, 2)
            kpis["available"] = True
        except Exception as e:
            logger.warning(f"Failed to load FF5: {e}")

    return kpis


# Caching for chart data
_chart_data_cache = {"data": None, "last_load": 0}


def get_chart_data(symbol: str, days: int = 90) -> list[dict]:
    """Get historical price data for a symbol from charts.csv.

    Args:
        symbol: Stock ticker (e.g., 'NVDA', '9984.T')
        days: Number of days of history to return (default 90)

    Returns:
        List of {date, price} dictionaries, sorted by date ascending
    """
    global _chart_data_cache

    charts_path = Config.BASE_DIR / "resources" / "charts.csv"
    if not charts_path.exists():
        return []

    # Check cache
    mtime = charts_path.stat().st_mtime
    if _chart_data_cache["data"] is None or _chart_data_cache["last_load"] < mtime:
        logger.info("Loading charts.csv for chart data")
        try:
            _chart_data_cache["data"] = pd.read_csv(charts_path)
            _chart_data_cache["last_load"] = mtime
        except Exception as e:
            logger.warning(f"Failed to load charts.csv: {e}")
            return []

    df = _chart_data_cache["data"]

    # Check if symbol exists in columns, try .T suffix for Japanese stocks
    lookup_symbol = symbol
    if symbol not in df.columns:
        # Try with .T suffix for numeric Japanese tickers
        if symbol.isdigit() and f"{symbol}.T" in df.columns:
            lookup_symbol = f"{symbol}.T"
        else:
            return []

    # Extract date and price columns
    chart_df = df[["Date", lookup_symbol]].copy()
    chart_df = chart_df.dropna(subset=[lookup_symbol])

    # Get last N days
    if len(chart_df) > days:
        chart_df = chart_df.tail(days)

    # Convert to list of dicts
    result = []
    for _, row in chart_df.iterrows():
        try:
            price = float(row[lookup_symbol])
            result.append({"date": str(row["Date"]), "price": round(price, 2)})
        except (ValueError, TypeError):
            continue

    return result
