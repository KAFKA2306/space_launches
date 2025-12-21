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
    fund_mapping = Config.UNIFIED_DATA_DIR / "fund_ticker_mapping.csv"

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
