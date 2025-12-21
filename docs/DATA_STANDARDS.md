# Data Formatting Standards

This document serves as the strict specification for data ingestion and formatting within the `trahist` system. All raw data processing **must** adhere to these standards to ensure data integrity across the pipeline.

## 1. Unified Schema (`trades_unified.csv`)

The goal of the data ingestion pipeline (`src/data/loaders.py`) is to produce a single, normalized CSV file with the following strict schema:

| Column | Type | Description | Mandatory? |
|--------|------|-------------|------------|
| `trade_date` | `datetime64[ns]` | Transaction date (YYYY-MM-DD HH:MM:SS) | **Yes** |
| `symbol` | `string` | Ticker or standardized code (e.g., `AAPL`, `1489.JP`) | **Yes** |
| `transaction_type` | `category` | Normalized type: `buy`, `sell`, `dividend`, `deposit`, `withdrawal` | **Yes** |
| `quantity` | `float64` | Number of shares/units. Must be positive. | **Yes** (0 for dividends) |
| `price` | `float64` | Price per unit in original currency. | No (can be impl. from amount) |
| `amount` | `float64` | Total transaction value in original currency. | **Yes** |
| `currency` | `string` | ISO 4217 Currency Code (`JPY`, `USD`). | **Yes** |
| `exchange_rate` | `float64` | Exchange rate to JPY at time of trade (1.0 for JPY trades). | **Yes** |
| `fee` | `float64` | Transaction fees in original currency. | No (default 0.0) |
| `tax` | `float64` | Tax withheld in original currency. | No (default 0.0) |
| `security_name` | `string` | Original security name from broker (e.g., "eMAXIS Slim..."). | No |
| `account_type` | `string` | Account category (`specific`, `nisa`, `general`). | No |
| `source_file` | `string` | Filename of the raw data source. | **Yes** |
| `data_source` | `string` | Broker identifier (`rakuten`, `sbi`, `monex`, `wise`, `binance`). | **Yes** |

## 2. Broker-Specific Handling

### A. Rakuten Securities
*   **File Detection**: Filenames containing `rakuten` or specific headers.
*   **Normalization**:
    *   `trade_date`: Parsed from `約定日` (Contract Date).
    *   `symbol`: Extracted from `銘柄コード`. Formatted as `xxxx.JP` for domestic stocks.
    *   `transaction_type`: Mapped from `取引種別` (e.g., "現物買" -> `buy`).

### B. SBI Securities
*   **File Detection**: Filenames containing `sbi` or specific column `国内/海外`.
*   **Normalization**:
    *   **Investment Trusts**: Quantity is usually in units. Price is often missing or implicit.
        *   **Rule**: `Price = Settlement Amount / (Quantity / 10000)` if price missing.
    *   **Foreign Stocks**: Handled via `foreign_stocks` logic.
    *   **CSV Encoding**: Often `Shift-JIS`. Loader must handle decoding errors strictly.

### C. Monex Securities
*   **File Detection**: `monex` in filename or headers matching `受渡日`, `銘柄コード`.
*   **Exclusions**:
    *   **Strict Filter**: Rows with `security_name` containing "MRF" or `security_code`="995" are **discarded** (Cash equivalents, not trades).
*   **Type Safety**: `security_code` is explicitly cast to String to prevents float conversion (e.g., "995.0").

### D. Wise (TransferWise)
*   **File Detection**: `wise` or `balance_statement`.
*   **Stock vs. Cash**:
    *   Detects "Stock Activity" files vs standard Balance Statements.
    *   Maps "Added" -> `buy`, "Used" -> `sell` (context dependent).

### E. Binance
*   **File Detection**: `.zip` files containing `xlsx` or `binance` in name.
*   **Process**:
    *   Extracts XLSX from ZIP.
    *   Handles **Password Protection**: Skips/Logs error if password required.
    *   Maps `Coin` to `symbol`.

## 3. Strict Data Cleaning Rules

### Date Formatting
*   All dates MUST be converted to `YYYY-MM-DD`.
*   Time component is preserved if available, otherwise defaults to `00:00:00`.
*   **Timezone**: All internal processing assumes explicit awareness or UTC normalization where applicable.

### Numeric Parsing
*   **Unicode Normalization**: All inputs are normalized using **NFKC** form to handle Zenkaku (Full-width) numbers and punctuation (e.g., `１２３，０００` → `123,000`) before parsing.
*   **Commas**: All commas (`,`) in numeric fields (Price, Amount, Quantity) MUST be removed before float conversion.
*   **NaN Handling**:
    *   Missing `price`: Derived from `amount / quantity` if possible.
    *   Missing `amount`: Derived from `price * quantity` if possible.
    *   Remaining NaNs in critical fields (`amount`, `quantity`) trigger a **Warning** or Filter (depending on strictness config).

### Fund Unit Normalization (The "10k Rule")
*   Japanese Investment Trusts are typically quoted in "10,000 units".
*   **Calculation Logic**:
    *   If `is_investment_fund` is TRUE:
        *   `Market Value = (Quantity / 10000) * Current_Price`
        *   `Cost Basis` is calculated similarly if `settlement_amount` missing.

## 4. Derived Columns & Validation

Data loading includes a derivation step (`CurrencyConverter`):
*   **`amount_jpy_unified`**: The strict JPY value of transaction.
    *   If `currency` == JPY: `amount`
    *   If `currency` != JPY: `amount * exchange_rate` (Using historical rate lookup if `exchange_rate` missing).

ANY changes to `loaders.py` must be verified against this document to ensure strict regression testing.
