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


def get_analyzer():
    """Get analyzer instance with current data."""
    csv_path = Config.UNIFIED_DATA_DIR / "trades_unified.csv"
    fund_mapping = Config.UNIFIED_DATA_DIR / "fund_ticker_mapping.csv"
    if csv_path.exists():
        return UnifiedCSVAnalyzer(str(csv_path), str(fund_mapping) if fund_mapping.exists() else None)
    return None


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page."""
    analyzer = get_analyzer()
    summary = {}

    if analyzer:
        holdings = analyzer.analyze_current_holdings()
        if not holdings.empty:
            summary = {
                "total_holdings": len(holdings),
                "total_value": holdings["total_cost_jpy"].sum(),
                "total_realized_pnl": holdings["realized_pnl_jpy"].sum(),
            }

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "summary": summary,
        },
    )


@app.get("/api/summary", response_class=HTMLResponse)
async def get_summary(request: Request):
    """Get portfolio summary partial."""
    analyzer = get_analyzer()
    summary = {}

    if analyzer:
        holdings = analyzer.analyze_current_holdings()
        if not holdings.empty:
            # Determine which value column to use
            val_col = "current_value_jpy" if "current_value_jpy" in holdings.columns else "total_cost_jpy"
            total_value = holdings[val_col].fillna(holdings["total_cost_jpy"]).sum()

            realized_pnl = holdings["realized_pnl_jpy"].sum()

            # Calculate unrealized P&L if available
            if "unrealized_pnl_jpy" in holdings.columns:
                unrealized_pnl = holdings["unrealized_pnl_jpy"].fillna(0).sum()
            else:
                unrealized_pnl = 0

            summary = {
                "total_holdings": len(holdings),
                "total_value": total_value,
                "total_realized_pnl": realized_pnl,
                "total_unrealized_pnl": unrealized_pnl,
                "pnl_pct": (unrealized_pnl / (total_value - unrealized_pnl) * 100)
                if (total_value - unrealized_pnl) > 0
                else 0,
            }

    return templates.TemplateResponse(
        "partials/summary.html",
        {
            "request": request,
            "summary": summary,
        },
    )


@app.get("/api/holdings", response_class=HTMLResponse)
async def get_holdings(request: Request, q: str = "", sort: str = "value"):
    """Get holdings table partial."""
    analyzer = get_analyzer()
    holdings = []

    if analyzer:
        df = analyzer.analyze_current_holdings()
        if not df.empty:
            # Filter
            if q:
                mask = df["symbol"].astype(str).str.contains(q, case=False, na=False) | df["security_name"].astype(
                    str
                ).str.contains(q, case=False, na=False)
                df = df[mask]

            # Sort
            if sort == "value":
                df = df.sort_values("total_cost_jpy", ascending=False)
            elif sort == "pnl":
                df = df.sort_values("realized_pnl_jpy", ascending=False)
            elif sort == "name":
                df = df.sort_values("symbol")

            holdings = df.head(50).to_dict("records")

    return templates.TemplateResponse(
        "partials/holdings.html",
        {
            "request": request,
            "holdings": holdings,
        },
    )


@app.get("/api/trades", response_class=HTMLResponse)
async def get_trades(request: Request, page: int = 1, limit: int = 20):
    """Get trades table partial with pagination."""
    analyzer = get_analyzer()
    trades = []
    has_more = False

    if analyzer:
        df = analyzer.trades_df.copy()
        df = df.sort_values("trade_date", ascending=False)

        # Convert datetime to string for template
        df["trade_date"] = df["trade_date"].astype(str)

        start = (page - 1) * limit
        end = start + limit

        page_df = df.iloc[start:end]
        # Replace NaN with None for cleaner template handling
        page_df = page_df.where(page_df.notna(), None)
        trades = page_df.to_dict("records")
        has_more = end < len(df)

    return templates.TemplateResponse(
        "partials/trades.html",
        {
            "request": request,
            "trades": trades,
            "page": page,
            "has_more": has_more,
        },
    )


@app.post("/api/refresh", response_class=HTMLResponse)
async def refresh_data(request: Request):
    """Trigger data refresh."""
    import subprocess

    result = subprocess.run(["task", "import"], capture_output=True, text=True, cwd=Config.BASE_DIR)
    success = result.returncode == 0

    return templates.TemplateResponse(
        "partials/refresh_result.html",
        {
            "request": request,
            "success": success,
            "message": "Data refreshed!" if success else "Refresh failed",
        },
    )
