# Web Interface Documentation

This document describes the web-based user interface for the TraHist application.

## Overview

TraHist includes a lightweight web interface built with FastAPI and htmx, designed to provide a quick and interactive way to view your portfolio and trade history.

## Getting Started

To start the web server, run the following command in your terminal:

```bash
task serve
```

This will start the application at `http://localhost:8000`. Open this URL in your web browser to access the dashboard.

## Dashboard Features

The main dashboard provides several key views:

### 1. Portfolio Summary
At the top of the page, you'll see a high-level summary of your portfolio, including:
- **Total Value (JPY)**: The current total value of your holdings.
- **Unrealized P&L**: Total profit/loss based on current market value vs. cost basis.
- **Realized P&L**: Total profit/loss from closed positions.
- **Return %**: The overall percentage return of your active investments.

### 2. Current Holdings
The "Holdings" table displays your current open positions.
- **Search**: Use the search bar to filter holdings by symbol or name.
- **Sort**: Click the sort options to order the list by Value, Return %, P&L, or Name.
- **Market Price**: For supported assets, current market prices are fetched to provide up-to-date valuations.

### 3. Trade History
The "Trades" section lists your historical transactions.
- **Pagination**: Navigate through your trade history using the "Load More" button or page links.
- **Details**: Shows Date, Symbol, Side (Buy/Sell), Quantity, Price, and Total Value.

## Data Management

### Refreshing Data
The "Refresh Data" button in the header allows you to trigger a backend update. This runs the `task import -- --download` command to:
1. Reload CSV data from the `data/raw` directory.
2. Download the latest market data for your holdings.
3. Re-calculate portfolio statistics.

**Note**: This process may take a few moments. The UI will indicate when the refresh is complete.

## Real-time Data

The application attempts to fetch real-time (or near real-time) prices for your top holdings using `yfinance`.
- This ensures that your portfolio value reflects intraday market movements.
- Prices are updated when the dashboard loads or when you manually refresh.

## Technical Implementation

The web app is built using a modern, lightweight stack:
- **Backend**: Python [FastAPI](https://fastapi.tiangolo.com/)
- **Frontend Interactivity**: [htmx](https://htmx.org/) for dynamic updates without full page reloads.
- **Templating**: [Jinja2](https://jinja.palletsprojects.com/) for server-side rendering.
- **Styling**: Vanilla CSS for substantial simplicity.

The application logic resides in `src/webapp/`.
