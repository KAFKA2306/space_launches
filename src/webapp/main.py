"""FastAPI + htmx Web Application for Trade History Analysis."""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from src.analysis.unified_csv_analyzer import UnifiedCSVAnalyzer
from src.config import Config

app = FastAPI(title="TraHist", description="Trade History Analyzer")

# Templates
templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


import asyncio
import subprocess
import pandas as pd
import yfinance as yf

# ... (Previous imports) ...

# ... (Templates init) ...

# Caching
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

    analyzer = UnifiedCSVAnalyzer(str(csv_path), str(fund_mapping) if fund_mapping.exists() else None)
    _analyzer_cache = {"instance": analyzer, "last_load": mtime}
    return analyzer


def _calculate_summary(holdings):
    """Calculate portfolio summary metrics."""
    if holdings.empty:
        return {}

    val_col = "current_value_jpy" if "current_value_jpy" in holdings.columns else "total_cost_jpy"
    # Ensure numeric and fill
    total_val_series = pd.to_numeric(holdings[val_col], errors='coerce').fillna(holdings["total_cost_jpy"]) if "current_value_jpy" in holdings.columns else holdings[val_col]
    total_value = total_val_series.sum()
    
    realized_pnl = holdings["realized_pnl_jpy"].sum()
    total_cost = holdings["total_cost_jpy"].sum()
    
    # Unrealized P&L
    unrealized_pnl = (total_value - total_cost) if "current_value_jpy" in holdings.columns else 0

    return {
        "total_holdings": len(holdings),
        "total_value": total_value,
        "total_realized_pnl": realized_pnl,
        "total_unrealized_pnl": unrealized_pnl,
        "pnl_pct": (unrealized_pnl / (total_value - unrealized_pnl) * 100) if (total_value - unrealized_pnl) > 0 else 0,
    }


def _filter_and_sort(df, q, sort):
    """Filter and sort holdings DataFrame."""
    if q:
        # Vectorized string search
        q = q.lower()
        mask = df["symbol"].astype(str).str.lower().str.contains(q, na=False) | \
               df["security_name"].astype(str).str.lower().str.contains(q, na=False)
        df = df[mask]

    # Sort logic map
    sort_map = {
        "value": ("current_value_jpy" if "current_value_jpy" in df.columns else "total_cost_jpy"),
        "percent": "unrealized_pnl_pct",
        "pnl": "unrealized_pnl_jpy",
        "name": "symbol"
    }
    col = sort_map.get(sort, sort_map["value"])
    
    if col in df.columns:
        df = df.sort_values(col, ascending=(sort == "name"))
        
    return df


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page."""
    analyzer = get_analyzer()
    summary = _calculate_summary(analyzer.analyze_current_holdings()) if analyzer else {}
    return templates.TemplateResponse("index.html", {"request": request, "summary": summary})


@app.get("/api/summary", response_class=HTMLResponse)
async def get_summary(request: Request):
    """Get portfolio summary partial."""
    analyzer = get_analyzer()
    summary = _calculate_summary(analyzer.analyze_current_holdings()) if analyzer else {}
    return templates.TemplateResponse("partials/summary.html", {"request": request, "summary": summary})


@app.get("/api/holdings", response_class=HTMLResponse)
async def get_holdings(request: Request, q: str = "", sort: str = "value"):
    """Get holdings table partial."""
    analyzer = get_analyzer()
    holdings = []

    if analyzer:
        df = analyzer.analyze_current_holdings()
        if not df.empty:
            df = _filter_and_sort(df, q, sort)
            holdings = df.head(50).to_dict("records")

    return templates.TemplateResponse("partials/holdings.html", {"request": request, "holdings": holdings})


@app.get("/api/trades", response_class=HTMLResponse)
async def get_trades(request: Request, page: int = 1, limit: int = 20):
    """Get trades table partial with pagination."""
    analyzer = get_analyzer()
    trades = []
    has_more = False

    if analyzer:
        df = analyzer.trades_df.copy().sort_values("trade_date", ascending=False)
        df["trade_date"] = df["trade_date"].astype(str)
        
        start = (page - 1) * limit
        page_df = df.iloc[start : start + limit].where(pd.notna(df), None)
        trades = page_df.to_dict("records")
        has_more = (start + limit) < len(df)

    return templates.TemplateResponse(
        "partials/trades.html",
        {"request": request, "trades": trades, "page": page, "has_more": has_more},
    )


@app.post("/api/refresh", response_class=HTMLResponse)
async def refresh_data(request: Request):
    """Trigger data refresh."""
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: subprocess.run(
            ["task", "import", "--", "--download"], capture_output=True, text=True, cwd=Config.BASE_DIR
        ),
    )
    success = result.returncode == 0
    response = templates.TemplateResponse(
        "partials/refresh_result.html",
        {"request": request, "success": success, "message": "Data refreshed!" if success else "Refresh failed"},
    )
    if success:
        response.headers["HX-Trigger"] = "dataRefreshed"
    return response


@app.get("/api/realtime-prices")
async def get_realtime_prices():
    """Fetch real-time prices for key holdings."""
    analyzer = get_analyzer()
    if not analyzer: return {"error": "No data"}

    holdings = analyzer.analyze_current_holdings()
    if holdings.empty: return {"error": "No holdings"}

    # Filter symbols
    symbols = holdings[~holdings["is_fund"]]["symbol"].head(20).tolist()
    valid_symbols = [s for s in symbols if not s.startswith("USDJPY") and not s.isdigit()][:10]

    def fetch():
        try:
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
                         "change_pct": round((last - prev) / prev * 100, 2) if prev else None
                     }
                else:
                     prices[sym] = {"price": None}
            return prices
        except Exception as e:
            return {"error": str(e)}

    loop = asyncio.get_event_loop()
    prices = await loop.run_in_executor(None, fetch)
    return {"prices": prices, "symbols": valid_symbols}
