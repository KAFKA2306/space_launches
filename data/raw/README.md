# Raw Data Directory

Place your trading history CSV files here. **Subdirectories are fully supported!**

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

## Directory Structure Examples

You can organize files in any subdirectory structure:

```
data/raw/
├── tradehistory(JP)_20250214.csv           # Direct placement
├── RAWDATA/                                # Subdirectory (legacy structure)
│   ├── rakuten/
│   │   ├── tradehistory(JP)_20250214.csv
│   │   └── tradehistory(US)_20250214.csv
│   └── sbi/
│       └── SaveFile_000001_000122.csv
└── wise/
    └── cleaned_wise_data_20240921.csv
```

**✅ All structures above work perfectly!** The system recursively searches all subdirectories.

## File Encoding
The system automatically detects file encodings (Shift-JIS, UTF-8, etc.).

## Example Files
Your files might look like:
- `tradehistory(JP)_20240919.csv`
- `tradehistory(US)_20240919.csv`
- `SaveFile_000001_000122.csv`
- `cleaned_wise_data_20240921.csv`