"""FastAPI + htmx Web Application for Trade History Analysis."""

import asyncio
import subprocess
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from src.config import Config
from src.webapp import services

app = FastAPI(title="TraHist", description="Trade History Analyzer")

# Templates
templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page."""
    analyzer = services.get_analyzer()
    summary = services.calculate_summary(analyzer.analyze_current_holdings()) if analyzer else {}
    return templates.TemplateResponse("index.html", {"request": request, "summary": summary})


@app.get("/api/summary", response_class=HTMLResponse)
async def get_summary(request: Request):
    """Get portfolio summary partial."""
    analyzer = services.get_analyzer()
    summary = services.calculate_summary(analyzer.analyze_current_holdings()) if analyzer else {}
    return templates.TemplateResponse("partials/summary.html", {"request": request, "summary": summary})


@app.get("/api/holdings", response_class=HTMLResponse)
async def get_holdings(request: Request, q: str = "", sort: str = "value"):
    """Get holdings table partial."""
    analyzer = services.get_analyzer()
    holdings = []

    if analyzer:
        df = analyzer.analyze_current_holdings()
        if not df.empty:
            df = services.filter_and_sort_holdings(df, q, sort)
            holdings = df.head(50).to_dict("records")

    return templates.TemplateResponse("partials/holdings.html", {"request": request, "holdings": holdings})


@app.get("/api/trades", response_class=HTMLResponse)
async def get_trades(request: Request, page: int = 1, limit: int = 20):
    """Get trades table partial with pagination."""
    analyzer = services.get_analyzer()
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
    """
    Trigger data refresh (offline conversion only).
    Per design spec: Refresh = fetch:c re-execution (no network).
    """
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: subprocess.run(["task", "fetch:c"], capture_output=True, text=True, cwd=Config.BASE_DIR),
    )
    success = result.returncode == 0
    response = templates.TemplateResponse(
        "partials/refresh_result.html",
        {"request": request, "success": success, "message": "Data refreshed!" if success else "Refresh failed"},
    )
    if success:
        response.headers["HX-Trigger"] = "dataRefreshed"
    return response


@app.post("/api/refresh-market", response_class=HTMLResponse)
async def refresh_market_data(request: Request):
    """
    Trigger market data update (requires network).
    Per design spec: Market data fetch is explicit opt-in only.
    """
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: subprocess.run(["task", "fetch:m"], capture_output=True, text=True, cwd=Config.BASE_DIR),
    )
    success = result.returncode == 0
    response = templates.TemplateResponse(
        "partials/refresh_result.html",
        {
            "request": request,
            "success": success,
            "message": "Market data updated!" if success else "Market update failed",
        },
    )
    if success:
        response.headers["HX-Trigger"] = "dataRefreshed"
    return response


# NOTE: /api/realtime-prices removed per design spec.
# Web display is offline-only. Real-time data fetch violates reproducibility.
# Use 'task fetch:m' explicitly to update resources with latest market data.
