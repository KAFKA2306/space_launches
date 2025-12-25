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
import markdown
import glob
import os

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
async def get_trades(request: Request, q: str = ""):
    """Get trades table partial (all trades, filtered by query)."""
    analyzer = services.get_analyzer()
    trades = []

    if analyzer:
        df = analyzer.trades_df.copy().sort_values("trade_date", ascending=False)
        df["trade_date"] = df["trade_date"].astype(str)

        # Filter if query provided
        if q:
            df = services.filter_trades(df, q)

        # Convert to records (all trades)
        trades = df.where(pd.notna(df), None).to_dict("records")

    return templates.TemplateResponse(
        "partials/trades.html",
        {"request": request, "trades": trades},
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


@app.get("/api/kpis", response_class=HTMLResponse)
async def get_kpis(request: Request):
    """Get KPIs partial."""
    kpis = services.calculate_kpis()
    return templates.TemplateResponse("partials/kpis.html", {"request": request, "kpis": kpis})


@app.get("/api/chart/{symbol}", response_class=HTMLResponse)
async def get_chart(request: Request, symbol: str, days: int = 90):
    """Get price chart partial for a symbol."""
    import json

    chart_data = services.get_chart_data(symbol, days)
    return templates.TemplateResponse(
        "partials/chart.html",
        {
            "request": request,
            "symbol": symbol,
            "chart_data": json.dumps(chart_data),
            "has_data": len(chart_data) > 0,
        },
    )


# NOTE: /api/realtime-prices removed per design spec.

# Web display is offline-only. Real-time data fetch violates reproducibility.


@app.get("/notes", response_class=HTMLResponse)
async def list_notes(request: Request):
    """List all trade notes."""
    note_dir = Path("docs/tradenote")
    notes = []
    
    # Check if dir exists
    if note_dir.exists():
        # Get all .md files
        files = list(note_dir.glob("*.md"))
        for f in files:
            # Filename format: Code_Name.md or just Code.md
            stem = f.stem # Code_Name
            parts = stem.split('_', 1)
            code = parts[0]
            name = parts[1] if len(parts) > 1 else code
            
            notes.append({"code": code, "name": name})
    
    # Sort by code (numeric if possible, else string)
    try:
        notes.sort(key=lambda x: int(x['code']) if x['code'].isdigit() else x['code'])
    except:
         notes.sort(key=lambda x: x['code'])

    return templates.TemplateResponse(
        "notes_index.html",
        {"request": request, "notes": notes}
    )

async def get_note(request: Request, symbol: str):
    """Render markdown trade note for a symbol."""
    note_dir = Path("docs/tradenote")
    
    # Matching logic: Symbol_*.md
    # We need to find the file that starts with symbol_ or just symbol.md
    # Because of sanitization, it might be slightly different, but usually code is safe.
    # We'll use glob.
    
    # Try exact match first
    candidates = list(note_dir.glob(f"{symbol}_*.md"))
    
    if not candidates:
        return templates.TemplateResponse(
            "note.html", 
            {"request": request, "symbol": symbol, "content": "<p>No trade note found for this symbol.</p>"}
        )
    
    # Pick the first match
    note_path = candidates[0]
    
    try:
        content_md = note_path.read_text(encoding="utf-8")
        content_html = markdown.markdown(content_md, extensions=['tables'])
    except Exception as e:
        content_html = f"<p>Error reading note: {e}</p>"
        
    return templates.TemplateResponse(
        "note.html",
        {"request": request, "symbol": symbol, "content": content_html}
    )

