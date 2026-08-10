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
| `task onboarding:pack -- --case-id case-demo-001` | Build an anonymous IFA delivery pack from offline unified outputs |
| `task format` | Apply Ruff/Prettier fixes; intentionally modifies source files |
| `task lint` | Check Ruff/Prettier formatting without modifying tracked files |
| `task test` | Run pytest regression tests only; does not format or rewrite files |
| `task ci` | Run lint → tests → fixture pipeline regeneration → `git diff --exit-code` tracked-file audit |
| `task clean` | Clean generated data |

### Design Principles

- **Offline by Default**: `task fetch:c` and `task run` never access the network
- **Explicit Network**: `task fetch:m` is the only command that downloads data
- **Pipeline Status**: Every run writes `data/unified/pipeline_status.csv`
- **Single Source of Truth**: `data/unified/trades_unified.csv` is the authoritative data
- **Non-destructive CI**: `task lint`, `task test`, and `task ci` must not rewrite tracked files. Apply intentional fixes only with `task format`.
- **Privacy-minimal delivery**: the IFA onboarding pack consumes normalized outputs only, never bundles raw broker files, and uses anonymous case IDs.

### Quality and regression contract

`task ci` is the clean-checkout gate used by GitHub Actions. It checks Python lint/format state, HTML formatting, runs the existing FF5 tests plus deterministic offline regression fixtures, then fails if any tracked file changed during validation.

The fixture suite covers Japanese numeric normalization, invalid-date filtering and stable ordering, preservation of identical broker records, deterministic USD→JPY conversion with a fixed exchange rate, exact fund mapping, rejection of unsafe Japanese-fund→US-ETF mapping, and three anonymous IFA onboarding-pack cases. Market downloads are not required for these tests.

When a formatting check fails, run `task format`, review the resulting diff, and commit the intentional change. CI itself never applies `--fix` or `--write`.

## Data Directory Structure

```
data/
├── raw/          # Input: 証券会社CSVをここに配置
├── interim/      # Staging: 市場データ、正規化された取引
├── unified/      # Gold: trades_unified.csv, pipeline_status.csv
├── reports/      # Output: チャート、JSON分析、CSVレポート
└── onboarding/   # Output: anonymous IFA delivery packs (generated, not tracked)
```

## Key Features

- **Fund Mapping**: fund names are mapped through `resources/securitycode2.csv` and the generated fund dictionary, with unsafe cross-market mappings rejected by the converter
- **JPY Unification**: foreign-currency prices and amounts are converted to JPY using stored historical FX data
- **Separation of Concerns**: `fetch` と `metrics` を完全分離
- **Offline-First**: `task run` はネットワーク不要、`task fetch:m` のみダウンロード
- **IFA onboarding delivery**: normalized trades, holdings cost basis, static summary, exceptions, pipeline status, and a machine-readable manifest share one anonymous case ID. See [IFA onboarding service boundary](docs/business/ifa-onboarding.md).

## Resources Directory

| File | Purpose |
|------|---------|
| `securitycode2.csv` | Manual fund→ticker mappings (source of truth) |
| `fund_dictionary.json` | Auto-generated dictionary with aliases |
| `forex_data.csv` | Historical forex rates (USD/JPY, EUR/JPY) |
| `charts.csv` | Stock price history |

## Documentation

- [Data Architecture & Formatting Standards](docs/DATA_STANDARDS.md)
- [Design Specification](docs/DESIGN_SPEC.md) - Authoritative design reference
- [Web Interface Documentation](docs/web_interface.md)
- [IFA onboarding service boundary](docs/business/ifa-onboarding.md)

## License

Personal Use Only.
