# Trade History Analyzer (TraHist)

複数の証券会社・通貨・商品名に分かれた取引履歴を、元明細を公開せずに同じ意味へ正規化し、**「今何を持っているか」「いくらで取得したか」「どの資産へ偏っているか」**を再計算可能な形で確認するための portfolio history tool です。

> **現在の中心価値:** broker CSVを一つの表へ変換することではなく、取引履歴から holdings / cost basis / performance / asset allocation を同じ基準で検証できる状態を作ることです。raw broker files は公開artifactやIFA delivery packへ含めません。

## Vision

異なるbrokerの画面やCSVを別々に眺める代わりに、取引履歴を安全に正規化し、**元取引まで遡れる一つのportfolio historyから保有状況を理解できる体験**を作ります。

成功条件は「CSV変換が通った」ことではありません。利用者が、どの取引がどのsymbolへ対応し、どの通貨・為替レートを通り、どのholdings / cost basisへ集計されたかを確認できることです。

## Design philosophy

- **Privacy first** — raw broker filesを公開・delivery artifactへ含めない。
- **Fail closed mapping** — fund名からtickerを推測して別市場の商品へ誤対応させるより、未mappingとして止めることを優先する。
- **FX is evidence, not decoration** — JPY換算では原通貨、取引日、`exchange_rate`をcanonical schemaへ残す。rateは`resources/forex_data.csv`のhistorical dataを使い、利用できない場合にfallback rateを使う現行実装があるため、fallback使用を市場観測値と同一視しない。
- **Offline by default** — broker CSVの変換・canonical化・holdings/metrics計算と、network経由のmarket data更新を分離する。
- **Recomputable outputs** — holdings / cost basis / metricsは正規化済み取引から再計算できる状態を保つ。
- **Anonymous delivery** — IFA向けpackは匿名case IDとnormalized outputsだけから生成する。
- **CI is not economic verification** — test/CI成功は、broker原票の完全性、市場価格の正しさ、投資成果を保証しない。

## Why / 差別化

TraHistの差別化はTaskfile、CSV、DuckDBなど個別技術ではありません。

**brokerごとに意味の違う取引履歴を一つのcanonical meaningへ揃えながら、mapping・currency conversion・例外を追跡し、raw個人明細を外へ出さずにportfolioを理解できること**を中心にします。

特に、便利そうな自動補完よりも誤った金融データを作らないことを優先します。日本の投資信託名を似た米国ETFへ自動mappingすると、価格単位・通貨・市場・商品そのものが別物のまま評価額へ混入し得るため、unsafe cross-market mappingは拒否します。

## User journey

```text
raw broker CSVs
    │  private / local
    ▼
offline normalize
    │  broker, date, symbol, currency, exchange_rate
    ▼
data/unified/trades_unified.csv
    │
    ├─ verify mapping / exceptions / pipeline status
    │
    ├─ holdings / JPY cost basis
    ├─ performance metrics / asset allocation
    └─ anonymous IFA delivery pack

network market refresh は別経路:
task fetch:m → resources/forex_data.csv / market resources
```

`data/unified/trades_unified.csv` がcanonical transaction table、`data/unified/pipeline_status.csv` がpipeline statusです。raw inputとnetwork refreshを同じ処理に見せません。

## Evidence / FX boundary

canonical schemaでは最低限、`trade_date`、`symbol`、`transaction_type`、`amount`、`currency`、`exchange_rate`、`source_file`、`data_source`を区別します。詳細は[`docs/DATA_STANDARDS.md`](docs/DATA_STANDARDS.md)を参照してください。

FX換算の現行境界:

- `currency`は原取引通貨を保持します。
- `exchange_rate`はJPY換算rateです。JPY取引は`1.0`です。
- historical lookupは取引日を基準に`resources/forex_data.csv`を参照し、完全一致がなければ近い日付を使う実装があります。
- forex dataが利用できない場合は設定済みfallback rateを使う経路があります。**fallbackは「その日の検証済み市場rate」ではありません。**
- したがってportfolio valuationを監査するときは、rate・date・currencyだけでなく、そのrateがhistorical resource由来かfallbackかも実行log/入力resourceと合わせて確認します。

現行schemaは`exchange_rate`を保持しますが、各rowへ独立した`fx_source`列を必須化してはいません。source provenanceをrow単位で完全追跡する必要がある用途では、この点を未実装境界として扱います。

## Offline / network boundary

| Task | Network | Role |
|---|---:|---|
| `task fetch:c` | No | raw broker CSVをinterimへ読み込む |
| `task run` | No | `fetch:c` → canonical/metrics計算 |
| `task holdings` | No | current holdings / cost basisを表示 |
| `task metrics` | No | performance / allocationを表示 |
| `task fetch:m` | Yes | forex・market resourcesを更新 |
| `task onboarding:pack -- --case-id case-demo-001` | No | unified outputsから匿名delivery packを生成 |

`task fetch:m`で取得したmarket resourcesが存在することと、offline conversionが正しく完了したことは別の状態です。

## IFA delivery / privacy

`task onboarding:pack` は次の2ファイルだけを入力にします。

```text
data/unified/trades_unified.csv
data/unified/pipeline_status.csv
```

raw broker CSVはpack generatorの入力にも納品物にも含めません。出力は`data/onboarding/<case-id>/`へ生成され、匿名case IDを使います。市場価格が別途検証されていない場合、holdingsは`valuation_status=COST_BASIS_ONLY`として現在価値を推測しません。

詳細な契約は[`docs/business/ifa-onboarding.md`](docs/business/ifa-onboarding.md)を参照してください。

## Performance interpretation boundary

holdings、Sharpe等のperformance metric、asset allocationは**取引履歴を理解するための分析結果**です。売買推奨、将来リターン予測、利益保証ではありません。

CI成功も、入力broker dataの経済的完全性、market dataの正確性、portfolio評価の妥当性を保証しません。結果を利用するときはcanonical trades、mapping、FX、exceptionsを併せて確認します。

## Quick Start

```bash
git clone <repository-url>
cd trahist
uv sync
```

## Usage - Task Commands

| Task | Action |
|------|--------|
| **`task fetch:c`** | **[Offline]** Load raw broker CSVs into interim; no market download |
| **`task fetch:m`** | **[Network]** Update forex and market resources |
| **`task run`** | **[Offline]** fetch:c → compute → status |
| **`task holdings`** | List current portfolio positions and cost/value information available from current resources |
| **`task metrics`** | Show performance stats and asset allocation |
| **`task serve`** | Launch the local web dashboard |
| `task report` | Generate static analysis files |
| `task onboarding:pack -- --case-id case-demo-001` | Build anonymous IFA delivery from offline unified outputs |
| `task format` | Apply Ruff/Prettier fixes; intentionally modifies source files |
| `task lint` | Check Ruff/Prettier formatting without modifying tracked files |
| `task test` | Run pytest regression tests only |
| `task ci` | lint → tests → fixture replay → tracked-file diff audit |
| `task clean` | Clean generated data |

## Data Directory Structure

```text
data/
├── raw/          # private input: broker CSVs
├── interim/      # staging
├── unified/      # canonical: trades_unified.csv, pipeline_status.csv
├── reports/      # generated charts / JSON / CSV reports
└── onboarding/   # anonymous IFA delivery packs; generated, not tracked
```

## Key Features

- **Fund Mapping**: `resources/securitycode2.csv`をmanual source of truthとして扱い、unsafe cross-market mappingをconverter側で拒否します。
- **JPY Unification**: original currencyと`exchange_rate`を保持しながらJPY統合します。
- **Separation of Concerns**: offline canonical conversionとnetwork market refreshを分離します。
- **Holdings / Metrics**: normalized tradesからportfolio positionsと分析値を再計算します。
- **IFA onboarding delivery**: normalized trades、cost-basis holdings、summary、exceptions、pipeline status、manifestを匿名case IDで束ねます。

## Resources Directory

| File | Purpose |
|------|---------|
| `securitycode2.csv` | Manual fund→ticker mappings |
| `fund_dictionary.json` | Generated mapping dictionary / aliases |
| `forex_data.csv` | Historical forex rates used by conversion |
| `charts.csv` | Stock price history |

## Quality and regression contract

`task ci` はGitHub Actionsでも使うclean-checkout gateです。Python/HTMLのlint/format check、pytest、deterministic offline fixture replayを行い、validation中にtracked fileが変わると失敗します。

fixture suiteは日本語数値normalization、invalid-date filtering、stable ordering、同一broker record保持、固定rateによるUSD→JPY conversion、exact fund mapping、unsafe Japanese-fund→US-ETF mapping拒否、匿名IFA onboarding casesを対象とします。market downloadはtestに必須ではありません。

## Documentation

- [Data Architecture & Formatting Standards](docs/DATA_STANDARDS.md)
- [Design Specification](docs/DESIGN_SPEC.md)
- [Web Interface Documentation](docs/web_interface.md)
- [IFA onboarding service boundary](docs/business/ifa-onboarding.md)

## Security / privacy

公開repositoryやdelivery artifactへ、API key、credential、raw broker CSV、氏名・メールアドレス・口座番号などの識別情報を含めないでください。`source_file` / `data_source`を含むcanonical data自体も、公開前に個人情報・契約上の再配布条件を確認します。

## License

Personal Use Only.
