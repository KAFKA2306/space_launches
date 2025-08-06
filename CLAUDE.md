# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a comprehensive Japanese trading history analysis tool (`trahist`) that processes trading data from multiple Japanese brokers (Rakuten, SBI, Wise) and provides unified JPY-based portfolio analysis. The tool specializes in handling Japanese investment funds with their unique 10,000x pricing convention and automatically maps fund names to ticker codes.

## Development Commands

### Environment Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Ensure Python 3.8+ is used
python3 --version
```

### Running the Application
```bash
# Main analysis (full pipeline)
python3 main.py

# Create unified CSV with JPY conversion (most commonly used)
python3 main.py --unified-csv

# Use alternative data sources (STOOQ for Japanese stocks)
python3 main.py --alternative-data

# Export data to JSON format
python3 main.py --export-json

# Skip market data download (use existing data)
python3 main.py --skip-download

# Charts only from existing processed data
python3 main.py --charts-only

# JSON export only (fast)
python3 main.py --json-only

# Build comprehensive fund dictionary
python3 main.py --build-fund-dict
```

### Testing and Validation
```bash
# Test with skip download first (validates configuration)
python3 main.py --skip-download

# Run with detailed logging
python3 main.py --unified-csv 2>&1 | tee analysis.log
```

## Code Architecture

### Main Entry Point
- `main.py`: Central orchestrator with argument parsing and pipeline execution
- `config.py`: Configuration management with broker patterns, column mappings, and data source settings

### Core Modules Structure
```
src/
├── data/loaders.py          # Multi-broker CSV data loading and standardization
├── market/
│   ├── forex.py             # Currency conversion and JPY unification
│   ├── stocks.py            # Stock price data management (yfinance + alternatives)
│   ├── alternative_data.py  # STOOQ/Alpha Vantage data sources
│   ├── data_converter.py    # JSON export and unified CSV creation
│   ├── currency_converter.py # Investment fund price conversion (10,000x rule)
│   └── fund_dictionary_builder.py # Investment fund name→ticker mapping
├── analysis/
│   ├── portfolio.py         # Portfolio performance calculations
│   └── visualization.py     # Chart generation and plotting
└── utils/helpers.py         # Utility functions for file handling and data processing
```

### Data Processing Pipeline
1. **Data Loading**: Multi-format CSV parsing with encoding detection (Shift-JIS/UTF-8)
2. **Data Standardization**: Unified column mapping across different brokers
3. **Currency Conversion**: All amounts converted to JPY using historical exchange rates
4. **Investment Fund Processing**: 10,000x price rule application and ticker mapping
5. **Market Data Integration**: Price data from STOOQ (primary) or yfinance (fallback)
6. **Portfolio Analysis**: Holdings calculation, P&L analysis, performance metrics
7. **Visualization**: Chart generation for portfolio overview and individual securities

### Investment Fund Handling
The system includes sophisticated handling of Japanese investment funds:
- **Name Mapping**: 136+ fund names automatically mapped to ticker codes
- **Price Conversion**: 10,000x rule applied (e.g., 15,230 yen → 1.523 yen per unit)
- **Dictionary Building**: Dynamic fund dictionary creation from historical data

### Alternative Data Sources
- **STOOQ**: Primary source for Japanese stocks (high coverage)
- **Yahoo Finance**: Fallback for international securities
- **Alpha Vantage**: Premium data source (requires API key)
- **Rate Limiting**: 1.5-second delays with retry logic

## Important Configuration

### Broker Data Patterns
Configured in `config.py` under `BROKER_PATTERNS`:
- Rakuten: `*JP*.csv`, `*US*.csv`, `*INVST*.csv`, `*CH*.csv`
- SBI: `SaveFile*.csv`, `yakujo*.csv`  
- Wise: `cleaned_wise_data*.csv`

### Data Directories
```
data/
├── raw/           # Input CSV files (auto-discovered recursively)
├── processed/     # Standardized data files
└── output/        # Analysis results, charts, unified CSVs, JSON exports
```

### Environment Variables (Optional)
```bash
export ALPHA_VANTAGE_API_KEY="your_key_here"
export POLYGON_API_KEY="your_key_here"
export IEX_API_KEY="your_key_here"
```

## Key Features to Understand

### Unified CSV Output
The `--unified-csv` command creates standardized CSV files with:
- JPY-unified pricing across all currencies
- Investment fund ticker mapping
- Standardized column structure for cross-analysis

### Multi-Currency Support
Supports JPY, USD, EUR, HKD, CNY, GBP with automatic conversion to JPY using historical rates.

### Error Handling
- Graceful degradation when data sources fail
- Automatic fallback between data providers
- Detailed logging for troubleshooting

### Performance Considerations
- Uses pandas for efficient data processing
- Implements rate limiting for API calls
- Supports incremental data updates
- Batch processing for large datasets

## Common Development Tasks

### Adding New Broker Support
1. Add file pattern to `config.py` `BROKER_PATTERNS`
2. Add column mapping to `config.py` `COLUMN_MAPPINGS`
3. Implement loader method in `src/data/loaders.py`

### Extending Investment Fund Mapping
Update the fund dictionary in `DIC/securitycode2.csv` or use `--build-fund-dict` to generate from historical data.

### Adding New Data Sources
Extend `src/market/alternative_data.py` with new provider implementations following the existing pattern.

## Important Implementation Notes

### Missing Functions
- `perform_eda_analysis()` called at main.py:394 is not implemented - this function needs to be created or the call should be removed/handled gracefully
- `process_csv_direct()` and `clean_trades_data()` functions called at main.py:66 and main.py:79 are not implemented in the current codebase

### Known Issues
- The main.py file references functions that don't exist in the current implementation, suggesting this is an incomplete migration from a CODES-style approach
- The DataLoader class in src/data/loaders.py provides the proper implementation for data loading, but main.py doesn't use it consistently