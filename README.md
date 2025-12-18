# Trade History Analyzer

Multiple broker trade history analysis tool with JPY unification and automated fund mapping.

## Quick Start

### Setup

```bash
git clone <repository-url>
cd trahist
uv sync
```

### Usage

Use `task` to run specific workflows. The workflow is split into **Fetching** (data processing) and **Running** (analysis).

| Task | Command | Description |
| :--- | :--- | :--- |
| **1. Fetch Data** | `task fetch -- --download` | Reads `data/raw`, downloads market data, and builds `data/interim` & `data/unified`. |
| **2. Run Analysis** | `task run` | Reads `data/unified`, generates reports in `data/reports`. |
| **Clean** | `task clean` | Destructively cleans all generated data (keeps `data/raw` safe). |

## Data Directory Structure (Clean Architecture)

- **`data/raw/`**: Place your broker CSVs here.
- **`data/interim/`**: Internal processing artifacts (market data, normalized trades).
- **`data/unified/`**: The "Gold" dataset. `trades_unified_*.csv` contains all your trades with JPY prices.
- **`data/reports/`**: Final outputs. Charts, JSON analysis, and performance CSVs.

## Key Features

- **Fund Mapping**: Automatically converts `eMAXIS Slim 全世界株式` -> `ACWI` (Ticker).
- **JPY Unification**: Converts `150.5 USD` -> `22575 JPY` using historical daily rates.
- **Separation of Concerns**: `fetch` logic is completely isolated from `analysis`, ensuring safety and reproducibility.

## License
Personal Use Only.