# FF5 Alpha Verification Module

Offline Fama-French 5-Factor analysis for strategy alpha verification.

## Architecture

```
src/analysis/ff5/
├── core.py       # All logic: Loading, Strategy, OLS
├── main.py       # CLI entry point
├── test_ff5.py   # Unit tests
└── README.md     # This file
```

**Network Isolation**: This module does NOT make network calls.
All data must be pre-fetched via `task fetch:m`.

## Quick Start

```bash
# 1. Fetch data (network)
task fetch:m

# 2. Run analysis (offline)
task analyze:ff5 -- --strategy-csv resources/sample_strategy.csv
```

## Input Requirements

### Strategy CSV
| Column | Type | Required |
|--------|------|----------|
| `date` | YYYY-MM-DD | Yes |
| `strategy_return` | Decimal (0.05 = 5%) | Yes (without --use-earnings) |

### FF5 Factors CSV (auto-downloaded)
Location: `data/raw/ff5_factors.csv`
| Column | Description |
|--------|-------------|
| `date` | Month-end |
| `mkt_rf`, `smb`, `hml`, `rmw`, `cma` | Factor returns (decimal) |
| `rf` | Risk-free rate (decimal) |

## CLI Options

```
--strategy-csv PATH   Required. Path to monthly returns.
--ff5-path PATH       FF5 factors CSV (default: data/raw/ff5_factors.csv)
--output PATH         Output report (default: ff5_report.csv)
--use-earnings        Filter returns by earnings events
```

## Output

Console:
```
        Coef       t
Alpha  0.007   1.38
MKT    1.000   8.35
...
R2: 0.95, N: 60
```

File: `ff5_report.csv` with columns `Factor, Coef, t, SE, R2`.

## Regression Model

```
(Rp - Rf) = α + β1(MKT-RF) + β2(SMB) + β3(HML) + β4(RMW) + β5(CMA) + ε
```

- **α (Alpha)**: Unexplained excess return.
- **t-stat**: Homoskedastic OLS (no Newey-West).

## Validation

Uses strict input validation:
- Rejects % units (values > 1.0)
- Requires exact column names
- Checks MonthEnd frequency
- Provides actionable error messages

Run tests:
```bash
python3 src/analysis/ff5/test_ff5.py
```

## Integration with fetch:m

`task fetch:m` downloads:
1. `ff5_factors.csv` from Ken French Library
2. `earnings_dates.csv` from yfinance (optional)

**Exit codes**:
- `0`: Success (or partial success with FF5 OK)
- `1`: Hard failure (FF5 missing or trades failed)
