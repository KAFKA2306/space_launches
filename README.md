# Trade History Analyzer

A comprehensive Python tool for analyzing trading history from multiple brokers, calculating portfolio performance, and generating detailed insights and visualizations.

## Features

- **Multi-Broker Support**: Load and standardize data from Rakuten Securities, SBI Securities, and Wise
- **Portfolio Analysis**: Calculate holdings, P&L, and performance metrics
- **Market Data Integration**: Download forex and stock prices from Yahoo Finance
- **Comprehensive Visualizations**: Generate charts for portfolio overview, trading activity, and individual securities
- **Clean Architecture**: Modular design with clear separation of concerns

## Quick Start

### Installation

1. **Clone or download the project**
2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

### Setup Data

1. **Create data directories** (done automatically on first run):
   ```
   data/
   ├── raw/           # Place your CSV files here
   ├── processed/     # Processed data files
   └── output/        # Analysis results and charts
   ```

2. **Place your trading data files** in `data/raw/` (supports subdirectories):
   - Rakuten files: `*JP*.csv`, `*US*.csv`, `*INVST*.csv`
   - SBI files: `SaveFile*.csv`, `yakujo*.csv`
   - Wise files: `cleaned_wise_data*.csv`
   - **Subdirectories supported**: Files can be in any subfolder structure like `data/raw/RAWDATA/rakuten/`

### Run Analysis

**Full analysis** (downloads market data and analyzes everything):
```bash
python main.py
```

**Skip market data download** (uses existing data):
```bash
python main.py --skip-download
```

**Create charts only** (from existing processed data):
```bash
python main.py --charts-only
```

## Project Structure

```
trahist/
├── main.py                    # Main entry point
├── config.py                  # Configuration settings
├── requirements.txt           # Dependencies
├── README.md                  # This file
├── data/                      # Data directories
│   ├── raw/                   # Raw CSV files
│   ├── processed/             # Processed data
│   └── output/                # Results and charts
├── src/                       # Source code
│   ├── data/                  # Data processing
│   │   └── loaders.py         # Data loading utilities
│   ├── market/                # Market data
│   │   ├── forex.py           # Forex data management
│   │   └── stocks.py          # Stock price data
│   ├── analysis/              # Analysis modules
│   │   ├── portfolio.py       # Portfolio analysis
│   │   └── visualization.py   # Chart generation
│   └── utils/                 # Utilities
│       └── helpers.py         # Helper functions
└── CODES/                     # Legacy code (for reference)
```

## Supported Data Formats

### Rakuten Securities
- **Japanese Stocks**: `*JP*.csv` files with columns like 約定日, 銘柄コード, 売買区分, etc.
- **US Stocks**: `*US*.csv` files with columns like 約定日, ティッカー, 売買区分, etc.
- **Investment Funds**: `*INVST*.csv` files with ファンド名, 取引, etc.

### SBI Securities
- **Domestic**: `SaveFile*.csv` files (skip 8 rows)
- **Foreign**: `yakujo*.csv` files (skip 2 rows)

### Wise (Currency Exchange)
- Pre-processed files: `cleaned_wise_data*.csv`

## Output Files

### Analysis Results
- `portfolio_holdings_TIMESTAMP.csv` - Current portfolio holdings
- `security_performance_TIMESTAMP.csv` - Performance by security
- `trades_TIMESTAMP.csv` - Processed trade data

### Market Data
- `forex_data.csv` - Downloaded forex rates
- `stock_prices.csv` - Downloaded stock prices

### Visualizations
- `portfolio_overview.png` - Portfolio summary charts
- `trading_activity.png` - Trading patterns and activity
- `performance_summary.png` - Performance analysis
- `securities/` - Individual security charts

## Key Features Explained

### Data Loading and Standardization
- **Recursive file search**: Finds CSV files in any subdirectory under `data/raw/`
- Automatically detects file encodings (handles Shift-JIS, UTF-8, etc.)
- Standardizes column names across different broker formats
- Cleans and converts numeric data
- Normalizes dates and transaction types

### Portfolio Analysis
- **Current Holdings**: Shares owned, cost basis, current value
- **P&L Calculation**: Realized and unrealized gains/losses
- **Performance Metrics**: Returns by security and overall portfolio
- **Trading Activity**: Patterns and frequency analysis

### Market Data Integration
- Downloads forex rates (USDJPY, EURJPY) from Yahoo Finance
- Fetches stock prices for all traded securities
- Converts all amounts to JPY for consistent analysis

### Visualizations
- **Portfolio Overview**: Holdings distribution, P&L by security
- **Trading Activity**: Monthly volumes, buy/sell patterns
- **Security Charts**: Price movements with trade markers
- **Performance Analysis**: Returns and trading frequency

## Configuration

Edit `config.py` to customize:
- Data directories
- Market data sources
- Column mappings for different brokers
- Date ranges and other settings

## Error Handling

The system includes robust error handling:
- Graceful handling of missing files or data
- Automatic encoding detection
- Detailed logging of all operations
- Continues processing even if some securities fail

## Logging

All operations are logged with timestamps. Check console output for:
- Data loading progress
- Market data download status
- Analysis results
- Error messages and warnings

## Tips for Best Results

1. **File Organization**: Keep data files organized in the `data/raw/` directory
2. **Regular Updates**: Run analysis periodically to get updated market data
3. **Data Quality**: Ensure CSV files are properly formatted and complete
4. **Performance**: Use `--skip-download` for faster re-analysis of existing data

## Troubleshooting

### Common Issues

**No data found**: 
- Check that CSV files are in `data/raw/`
- Verify file naming matches expected patterns

**Market data download fails**:
- Check internet connection
- Yahoo Finance may have rate limits - try again later

**Encoding errors**:
- System automatically detects encodings, but you can manually specify in `config.py`

**Memory issues with large datasets**:
- Consider processing data in smaller chunks
- Close other applications to free memory

## Advanced Usage

### Custom Data Sources
Extend the `DataLoader` class in `src/data/loaders.py` to support additional broker formats.

### Custom Analysis
Add new analysis functions to `src/analysis/portfolio.py` or create new modules.

### Custom Visualizations
Extend the `TradeVisualizer` class in `src/analysis/visualization.py`.

## Requirements

- Python 3.8+
- pandas, numpy for data processing
- matplotlib, seaborn for visualization
- yfinance for market data
- chardet for encoding detection

## License

This project is for personal use. Ensure compliance with your broker's terms of service when using their data.