# Trade History Analyzer (TraHist)

証券会社の取引履歴を分析するツール。JPY統合と自動ファンドマッピング機能付き。

## Quick Start

```bash
git clone <repository-url>
cd trahist
uv sync
```

## Usage - Task Commands

| Task | Action |
|------|--------|
| **`task fetch:c`** | **[Offline]** Convert raw broker CSVs to unified format |
| **`task fetch:m`** | **[Network]** Download latest market data from Yahoo Finance |
| **`task run`** | **Full Pipeline**: fetch:c → compute → status confirmation |
| **`task holdings`** | List current portfolio positions and value |
| **`task metrics`** | Show performance stats and asset allocation |
| **`task serve`** | Launch the web dashboard |
| `task report` | Generate static analysis files |
| `task clean` | Clean generated data |

### Design Principles

- **Offline by Default**: `task fetch:c` and `task run` never access the network
- **Explicit Network**: `task fetch:m` is the only command that downloads data
- **Pipeline Status**: Every run writes `data/unified/pipeline_status.csv`
- **Single Source of Truth**: `data/unified/trades_unified.csv` is the authoritative data

## Data Directory Structure

```
data/
├── raw/          # Input: 証券会社CSVをここに配置
├── interim/      # Staging: 市場データ、正規化された取引
├── unified/      # Gold: trades_unified.csv, pipeline_status.csv
└── reports/      # Output: チャート、JSON分析、CSVレポート
```

## Key Features

- **Fund Mapping**: `eMAXIS Slim 全世界株式` → `ACWI` (Ticker) 自動変換
- **JPY Unification**: `150.5 USD` → `22575 JPY` 日次レートで変換
- **Separation of Concerns**: `fetch` と `metrics` を完全分離

## Documentation

- [Data Architecture & Formatting Standards](docs/DATA_STANDARDS.md)
- [Design Specification](docs/DESIGN_SPEC.md) - Authoritative design reference
- [Web Interface Documentation](docs/web_interface.md)

## License

Personal Use Only.