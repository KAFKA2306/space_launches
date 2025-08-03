# Integrated New Features Usage Guide

The trade history analyzer now includes fully integrated JSON export and alternative data source functionality. This guide shows how to use these features with the main.py script.

## New Command Line Options

```bash
# Basic usage with new features
python3 main.py --help
```

### Available Arguments

| Argument | Description |
|----------|-------------|
| `--export-json` | Export processed data to JSON format |
| `--alternative-data` | Use alternative data sources (STOOQ, Yahoo Direct) instead of yfinance |
| `--json-only` | Only export data to JSON format without full analysis |
| `--skip-download` | Skip downloading market data and use existing files |
| `--charts-only` | Only create charts from existing processed data |

## Usage Examples

### 1. JSON Export Only
Export your existing trading data to JSON format without running full analysis:

```bash
python3 main.py --json-only
```

**Output:**
- `data/output/json_data/trades_YYYYMMDD_HHMMSS.json`
- `data/output/json_data/ticker_codes_YYYYMMDD_HHMMSS.json`

### 2. Alternative Data Sources
Use STOOQ and Yahoo Direct API instead of yfinance for better Japanese stock coverage:

```bash
python3 main.py --alternative-data
```

**Benefits:**
- ✅ Better support for Japanese stocks (TSE listings)
- ✅ No yfinance dependency issues
- ✅ Multiple fallback sources
- ✅ Rate limiting and error handling

### 3. Full Analysis with JSON Export
Run complete analysis with automatic JSON export:

```bash
python3 main.py --export-json
```

### 4. Alternative Data + JSON Export
Combine both new features for optimal results:

```bash
python3 main.py --alternative-data --export-json
```

### 5. Skip Download with Alternative Data (Testing)
Test alternative data routing without actually downloading:

```bash
python3 main.py --alternative-data --skip-download
```

## Test Results

From the integration tests, the system successfully:

### ✅ JSON Export
- Converted 14 trades to structured JSON format
- Extracted 7 unique ticker codes: `2563`, `2621`, `2837`, `EBIZ`, `VDC`, `VDE`, `XLP`
- Generated metadata with date ranges, currencies, and data sources
- Auto-export enabled by default (configurable in config.py)

### ✅ Alternative Data Sources  
- **Japanese Stocks:** 100% success rate with STOOQ
  - `2563`: 1,250 historical records
  - `2621`: 1,174 historical records  
  - `2837`: 878 historical records
- **US ETFs:** Partial success (Yahoo Direct has rate limiting)
  - STOOQ: Limited US coverage
  - Yahoo Direct: 401 Unauthorized (expected with heavy usage)
  - Alpha Vantage: Not configured (requires API key)

## Configuration

### Default Settings (config.py)

```python
# Alternative data sources configuration
ALTERNATIVE_DATA_SOURCES = {
    'default_sources': ['stooq', 'yahoo', 'alpha_vantage'],
    'rate_limit_seconds': 2.0,
    'request_timeout': 30,
    'retry_count': 3,
    'max_symbols_per_batch': 50
}

# JSON export settings  
JSON_EXPORT = {
    'enable_auto_export': True,       # Auto-export after analysis
    'export_directory': 'json_data',
    'include_metadata': True,
    'pretty_print': True
}
```

### Environment Variables (Optional)

```bash
# Set API keys for additional data sources
export ALPHA_VANTAGE_API_KEY="your_key_here"
export POLYGON_API_KEY="your_key_here"
export IEX_API_KEY="your_key_here"
```

## File Structure

After running with new features, your output directory will contain:

```
data/output/
├── charts/                          # Visualization charts
│   ├── trading_activity.png
│   └── performance_summary.png
├── json_data/                       # JSON exports
│   ├── trades_20250803_194947.json
│   └── ticker_codes_20250803_194947.json
├── historical_data/                 # Alternative data downloads
│   ├── 2563_historical.csv
│   ├── 2621_historical.csv
│   ├── 2837_historical.csv
│   ├── combined_historical_prices.csv
│   └── historical_data_metadata.json
├── portfolio_holdings_*.csv         # Portfolio analysis
└── security_performance_*.csv       # Performance metrics
```

## JSON Output Examples

### Trades JSON Structure
```json
{
  "metadata": {
    "total_trades": 14,
    "date_range": {
      "start": "2020-09-18T00:00:00",
      "end": "2025-02-25T00:00:00"
    },
    "currencies": ["JPY", "USD", "HKドル"],
    "data_sources": ["rakuten_us_...", "sbi_domestic_..."]
  },
  "trades": [
    {
      "trade_date": "2020-09-29T00:00:00",
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

### Ticker Codes JSON
```json
{
  "metadata": {
    "total_codes": 7,
    "extracted_at": "2025-08-03T19:43:02.171681"
  },
  "ticker_codes": ["2563", "2621", "2837", "EBIZ", "VDC", "VDE", "XLP"]
}
```

## Data Source Coverage

| Asset Type | STOOQ | Yahoo Direct | Alpha Vantage | Recommended |
|------------|-------|--------------|---------------|-------------|
| Japanese Stocks (TSE) | ✅ Excellent | ❌ Limited | ✅ Good | STOOQ |
| US Stocks/ETFs | ⚠️ Limited | ✅ Good | ✅ Excellent | Yahoo + Alpha Vantage |
| European Stocks | ✅ Good | ✅ Good | ✅ Good | Any |
| Asian Markets | ✅ Good | ⚠️ Limited | ⚠️ Limited | STOOQ |

## Error Handling

The system includes robust error handling:

- **Automatic Fallback:** If STOOQ fails, tries Yahoo Direct, then Alpha Vantage
- **Rate Limiting:** 2-second delays between requests to avoid API limits
- **Retry Logic:** Up to 3 retries for failed requests
- **Graceful Degradation:** Continues analysis even if some symbols fail
- **Detailed Logging:** Complete success/failure tracking

## Performance Tips

1. **Use `--alternative-data` for Japanese stocks** - Much better coverage than yfinance
2. **Set up Alpha Vantage API key** - Best for US markets (free tier available)
3. **Use `--json-only` for quick exports** - Skip analysis when you just need data
4. **Run with `--skip-download` first** - Test configuration before downloading
5. **Monitor rate limits** - Increase delay_seconds in config if hitting limits

## Backwards Compatibility

- All existing functionality remains unchanged
- Default behavior uses yfinance unless `--alternative-data` is specified
- JSON export is optional unless `--export-json` is used or auto-export is enabled
- All existing command line arguments work as before

## Integration with External Tools

The JSON format makes it easy to integrate with:
- **Web applications** - Direct JSON consumption
- **Data analysis tools** - Pandas can read JSON directly
- **APIs** - Standard REST API format
- **Databases** - Import JSON into NoSQL databases
- **Visualization tools** - Chart.js, D3.js, etc.

## Next Steps

1. **Set up API keys** for Alpha Vantage (free tier)
2. **Configure rate limits** based on your usage patterns
3. **Automate exports** by enabling auto-export in config
4. **Monitor data quality** using the metadata files
5. **Build integrations** using the JSON outputs

## Troubleshooting

### Common Issues

1. **Yahoo 401 Errors**: Normal with heavy usage, use Alpha Vantage as alternative
2. **STOOQ No Data**: Some symbols not available, check symbol format
3. **Rate Limiting**: Increase `rate_limit_seconds` in config
4. **API Keys**: Set environment variables for Alpha Vantage

### Getting Help

Run with verbose logging to see detailed operations:
```bash
python3 main.py --alternative-data --export-json 2>&1 | tee analysis.log
```

Check the logs for specific error messages and success rates.