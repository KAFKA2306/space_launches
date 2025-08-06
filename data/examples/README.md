# Example CSV Data for Testing

This directory contains comprehensive example CSV files demonstrating all supported broker formats and data types. Use these files to test the system functionality without real trading data.

## 📁 File Structure

```
examples/
├── README.md                                          # This file
├── example_tradehistory(JP)_20241201.csv             # Rakuten Japan stocks
├── example_tradehistory(US)_20241201.csv             # Rakuten US stocks  
├── example_tradehistory(INVST)_20241201.csv          # Rakuten investment funds
├── example_tradehistory(CH)_20241201.csv             # Rakuten China/Hong Kong
├── example_SaveFile_000001_000142.csv                # SBI domestic trades
├── example_yakujo_foreign_20241201.csv               # SBI foreign trades
├── example_cleaned_wise_data_20241201.csv            # Wise currency exchange
├── example_assetbalance(all)_20241201_120000.csv     # Portfolio snapshot
└── example_New_file.csv                              # Portfolio listing
```

## 🎯 How to Use

### Option 1: Copy to Raw Data Directory
```bash
# Copy all example files to your raw data directory
cp /home/kafka/finance/trahist/data/examples/*.csv /home/kafka/finance/trahist/data/raw/

# Run analysis
python3 main.py --unified-csv --export-json
```

### Option 2: Test Specific Broker Data
```bash
# Test only Rakuten data
cp /home/kafka/finance/trahist/data/examples/example_tradehistory*.csv /home/kafka/finance/trahist/data/raw/

# Test only SBI data  
cp /home/kafka/finance/trahist/data/examples/example_SaveFile*.csv /home/kafka/finance/trahist/data/raw/
cp /home/kafka/finance/trahist/data/examples/example_yakujo*.csv /home/kafka/finance/trahist/data/raw/
```

### Option 3: Test Investment Fund Mapping
```bash
# Copy fund-heavy files
cp /home/kafka/finance/trahist/data/examples/example_tradehistory\(INVST\)*.csv /home/kafka/finance/trahist/data/raw/
cp /home/kafka/finance/trahist/data/examples/example_SaveFile*.csv /home/kafka/finance/trahist/data/raw/

# Test fund mapping
python3 main.py --build-fund-dict
python3 main.py --unified-csv
```

## 📊 Example Data Content

### Japanese Stocks (Rakuten JP)
- **Toyota (7203)**: 100 shares, traditional automotive
- **Sony (6758)**: 50 shares, technology conglomerate  
- **SoftBank Group (9984)**: Venture capital, sell transaction
- **Shin-Etsu Chemical (4063)**: Chemical industry
- **Japan Tobacco (2914)**: Tobacco/pharmaceutical 
- **Keyence (6861)**: Industrial automation equipment

### US Stocks (Rakuten US)
- **AAPL**: Apple Inc, technology leader
- **MSFT**: Microsoft Corp, cloud services
- **GOOGL**: Alphabet/Google, search and advertising
- **TSLA**: Tesla Inc, electric vehicles (sell transaction)
- **NVDA**: NVIDIA Corp, AI/graphics processing
- **AMZN**: Amazon.com, e-commerce and cloud

### Investment Funds (Rakuten INVST + SBI)
- **eMAXIS Slim 全世界株式(オール・カントリー)** → ACWI
- **ＳＢＩ・新興国株式インデックス・ファンド(雪だるま)** → VWO  
- **＜購入・換金手数料なし＞ニッセイ新興国株式インデックスファンド** → VWO
- **楽天・全米株式インデックス・ファンド** → VOO
- **ニッセイ外国株式インデックスファンド** → FTSE Developed Markets
- **eMAXIS Slim 米国株式(S&P500)** → SPY
- **Tracers S&P500トップ10インデックス** → NOBL

### Hong Kong/China Stocks (Rakuten CH)
- **2800**: Tracker Fund of Hong Kong
- **2837**: Global X Hang Seng Tech ETF  
- **0700**: Tencent Holdings
- **9988**: Alibaba Group (sell transaction)
- **1211**: BYD Company (electric vehicles)

### SBI Foreign Stocks
- **VTI**: Vanguard Total Stock Market
- **VOO**: Vanguard S&P 500
- **QQQ**: Invesco QQQ (NASDAQ)
- **SCHD**: Schwab US Dividend Equity
- **SPYD**: SPDR S&P 500 High Dividend (sell transaction)

### Currency Exchange (Wise)
- **USD to JPY**: Multiple transactions at different rates
- **EUR to JPY**: European currency conversions  
- **HKD to JPY**: Hong Kong dollar large transaction

### Portfolio Data
- **Current Holdings**: Mix of stocks and funds
- **Account Types**: 特定 (Taxable), NISA, つみたてNISA
- **P&L Information**: Realized and unrealized gains/losses
- **Multi-Currency**: JPY, USD, HKD positions

## 🎯 Expected Results

When you run the analysis with this example data, you should see:

### Fund Mappings
```
✅ eMAXIS Slim 全世界株式(オール・カントリー) → ACWI
✅ ＳＢＩ・新興国株式インデックス・ファンド(雪だるま) → VWO
✅ ニッセイ新興国株式インデックスファンド → VWO
✅ 楽天・全米株式インデックス・ファンド → VOO
```

### Unified CSV Output
- **Total Trades**: ~25-30 transactions
- **Currencies**: JPY, USD, HKD, EUR
- **Investment Funds**: 6-8 funds with ticker mappings
- **Security Codes**: Properly populated for all securities
- **JPY Amounts**: All converted to unified JPY pricing

### JSON Export
- Structured trade data with fund mappings
- Ticker code extraction (15-20 unique codes)
- Conversion metadata and currency information

## 💡 Testing Scenarios

### 1. Basic Functionality Test
```bash
# Clean start
rm -rf data/raw/*.csv
cp data/examples/example_tradehistory\(JP\)*.csv data/raw/
python3 main.py --unified-csv
```

### 2. Multi-Broker Integration Test  
```bash
# Full broker coverage
cp data/examples/*.csv data/raw/
python3 main.py --unified-csv --export-json --charts-only
```

### 3. Investment Fund Mapping Test
```bash
# Fund-focused test
rm -rf data/raw/*.csv
cp data/examples/example_tradehistory\(INVST\)*.csv data/raw/
cp data/examples/example_SaveFile*.csv data/raw/
python3 main.py --build-fund-dict
python3 main.py --unified-csv
```

### 4. Performance Test with Skip Download
```bash
# Fast test without market data download
cp data/examples/*.csv data/raw/
python3 main.py --skip-download --unified-csv --export-json
```

## 🔍 Data Validation

The example data includes:
- ✅ **Realistic Prices**: Based on actual market ranges
- ✅ **Proper Japanese Text**: Authentic fund and company names
- ✅ **Date Consistency**: Proper trade/settlement date relationships  
- ✅ **Account Types**: Real Japanese account classifications
- ✅ **Currency Rates**: Reasonable exchange rate ranges
- ✅ **Edge Cases**: Sell transactions, different currencies, mixed data sources

## 📝 Notes

- **Encoding**: All files use UTF-8 encoding for compatibility
- **Headers**: SBI files include realistic header structures to test skiprows functionality
- **Investment Funds**: Include both exact matches and alias variations for mapping tests
- **Portfolio Data**: Demonstrates both assetbalance and New_file formats
- **Currencies**: Multiple currency combinations to test conversion logic
- **Account Types**: Japanese account classifications (特定, NISA, つみたてNISA)

This example data provides comprehensive coverage for testing all aspects of the Japanese trading history analysis system.