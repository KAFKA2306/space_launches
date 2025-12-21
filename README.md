# Trade History Analyzer (TraHist)

証券会社の取引履歴を分析するツール。JPY統合と自動ファンドマッピング機能付き。

## Quick Start

```bash
git clone <repository-url>
cd trahist
uv sync
```

## Usage - User Stories

| ストーリー | コマンド | 説明 |
|-----------|---------|------|
| **[1] データ取込** | `task import -- --download` | 証券会社CSVを読み込み、市場データをダウンロード |
| **[2] ポートフォリオ確認** | `task view` | 現在の保有銘柄とP&Lを表示 |
| **[3] パフォーマンス分析** | `task analyze` | 過去のパフォーマンス指標を分析 |
| **[4] レポート出力** | `task report` | チャートと包括的レポートを生成 |
| **フルパイプライン** | `task pipeline` | 全ステップを順次実行 |
| **Web UI** | `task serve` | ダッシュボードサーバーを起動 (localhost:8000) |
| **クリーン** | `task clean` | 生成データを削除（rawは安全） |

## Maintenance Tools

### Market Data Repair
Missing market data can be repaired using the utility script:
```bash
python scripts/repair_market_data.py
```
This script backfills missing price data for symbols with empty columns or stale data.

## Data Directory Structure

```
data/
├── raw/          # Input: 証券会社CSVをここに配置
├── interim/      # Staging: 市場データ、正規化された取引
├── unified/      # Gold: trades_unified_*.csv (JPY価格付き)
└── reports/      # Output: チャート、JSON分析、CSVレポート
```

## Key Features

- **Fund Mapping**: `eMAXIS Slim 全世界株式` → `ACWI` (Ticker) 自動変換
- **JPY Unification**: `150.5 USD` → `22575 JPY` 日次レートで変換
- **Separation of Concerns**: `import` と `analyze` を完全分離

## Documentation

- [Data Architecture & Formatting Standards](docs/DATA_STANDARDS.md) - Strict guide on data ingestion and schema.
- [Web Interface Documentation](docs/web_interface.md) - Guide to using the web dashboard.

## License

Personal Use Only.