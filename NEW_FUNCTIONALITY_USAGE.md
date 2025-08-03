# New JSON Conversion and Alternative Data Functionality

This document explains how to use the new features added to the trade history analyzer.

## Overview

Two new modules have been added:
1. **Data Converter** (`src/market/data_converter.py`) - Converts trades and portfolio CSV data to JSON format
2. **Alternative Data Fetcher** (`src/market/alternative_data.py`) - Fetches historical price data without using yfinance

## Features

### 1. CSV to JSON Conversion

Convert your processed trades and portfolio data to JSON format for easier integration with other tools.

**Key Functions:**
- `trades_csv_to_json()` - Convert trades CSV to structured JSON
- `portfolio_csv_to_json()` - Convert portfolio CSV to structured JSON  
- `extract_ticker_codes()` - Extract unique ticker symbols from the data
- `convert_latest_data_to_json()` - Process the most recent data files automatically

### 2. Alternative Historical Data Sources

Fetch historical price data using multiple sources as alternatives to yfinance:

**Supported Sources:**
- **STOOQ** (Free) - Supports international markets including Japanese stocks
- **Yahoo Finance Direct** (Free) - Direct API calls to Yahoo without yfinance library
- **Alpha Vantage** (API key required) - Professional data service

**Key Functions:**
- `fetch_historical_data()` - Fetch data for single ticker with fallback sources
- `fetch_multiple_symbols()` - Batch process multiple tickers with rate limiting
- `save_historical_data()` - Save results to CSV files with metadata

## Usage Examples

### Quick Test

Run the included test script to see everything in action:

```bash
python3 test_new_functionality.py
```

This will:
1. Convert your latest trades/portfolio data to JSON
2. Extract ticker codes  
3. Fetch historical data for the first 3 tickers
4. Save everything to the output directory

### Manual Usage

```python
from src.market.data_converter import DataConverter
from src.market.alternative_data import AlternativeDataFetcher
from config import Config

# Initialize
config = Config()
converter = DataConverter(config)
fetcher = AlternativeDataFetcher(config)

# Convert latest data to JSON
result_paths = converter.convert_latest_data_to_json(
    config.PROCESSED_DATA_DIR, 
    config.OUTPUT_DIR / "json_data"
)

# Extract ticker codes
trades_file = config.PROCESSED_DATA_DIR / "trades_20250803_193352.csv"
portfolio_file = config.OUTPUT_DIR / "portfolio_holdings_20250803_193352.csv"

ticker_codes = converter.extract_ticker_codes(
    trades_file_path=trades_file,
    portfolio_file_path=portfolio_file
)

# Fetch historical data
historical_data = fetcher.fetch_multiple_symbols(
    symbols=list(ticker_codes),
    start_date="2024-01-01",
    end_date="2025-08-03",
    sources=['stooq', 'yahoo'],  # Try STOOQ first, then Yahoo
    delay_seconds=2.0  # Rate limiting
)

# Save results
fetcher.save_historical_data(
    historical_data, 
    config.OUTPUT_DIR / "historical_data"
)
```

## Generated Files

### JSON Output Structure

**Trades JSON:**
```json
{
  "metadata": {
    "total_trades": 14,
    "date_range": {"start": "2020-09-18T00:00:00", "end": "2025-02-25T00:00:00"},
    "currencies": ["JPY", "USD", "HKドル"],
    "data_sources": ["rakuten_us_...", "sbi_domestic_..."]
  },
  "trades": [
    {
      "trade_date": "2020-09-18T00:00:00",
      "security_code": "VDE",
      "security_name": "VA ENERGY",
      "transaction_type": "buy",
      "quantity": 2.0,
      "price": 41.31,
      "settlement_amount": 8772.0,
      "currency": "USD"
    }
  ]
}
```

**Ticker Codes JSON:**
```json
{
  "metadata": {
    "total_codes": 7,
    "extracted_at": "2025-08-03T19:43:02.171681"
  },
  "ticker_codes": ["2563", "2621", "2837", "EBIZ", "VDC", "VDE", "XLP"]
}
```

### Historical Data Files

- Individual CSV files per ticker: `{symbol}_historical.csv`
- Combined price data: `combined_historical_prices.csv`
- Metadata file: `historical_data_metadata.json`

## Current Results

From your trading data, the following ticker codes were extracted:
- **Japanese stocks:** 2563, 2621, 2837 (successfully fetched from STOOQ)
- **US ETFs:** EBIZ, VDC, VDE, XLP (can be fetched from Yahoo/STOOQ)

Test results:
- ✅ 100% success rate for Japanese stocks via STOOQ
- ✅ 242 trading days of data per symbol (1 year period)
- ✅ Proper OHLCV data format
- ✅ Automatic rate limiting and error handling

## Integration with Existing Code

The new functionality is designed to work alongside your existing trade analysis pipeline. You can:

1. Use the JSON format for external integrations
2. Replace yfinance calls with the alternative data sources
3. Access Japanese stock data that may not be available through yfinance
4. Implement backup data sources for reliability

## Rate Limiting

The fetcher includes built-in rate limiting:
- 2-second delays between symbols by default
- Configurable delays between API calls
- Retry logic for failed requests
- Multiple fallback sources

## Error Handling

Robust error handling ensures:
- Graceful failures when data sources are unavailable
- Automatic fallback to next data source
- Detailed logging of success/failure rates
- No data loss if some symbols fail

## Next Steps

You can extend this functionality by:
1. Adding more data sources (e.g., Polygon, IEX Cloud)
2. Implementing real-time data feeds
3. Adding cryptocurrency support
4. Creating automated data update schedules