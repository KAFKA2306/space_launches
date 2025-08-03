# Raw Data Directory

Place your trading history CSV files here.

## Supported File Patterns

### Rakuten Securities
- `*JP*.csv` - Japanese stock trades
- `*US*.csv` - US stock trades  
- `*INVST*.csv` - Investment fund trades

### SBI Securities
- `SaveFile*.csv` - Domestic trades
- `yakujo*.csv` - Foreign trades

### Wise
- `cleaned_wise_data*.csv` - Currency exchange data

## File Encoding
The system automatically detects file encodings (Shift-JIS, UTF-8, etc.).

## Example Files
Your files might look like:
- `tradehistory(JP)_20240919.csv`
- `tradehistory(US)_20240919.csv`
- `SaveFile_000001_000122.csv`
- `cleaned_wise_data_20240921.csv`