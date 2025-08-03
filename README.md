# 取引履歴分析ツール

複数の証券会社から取引履歴を読み込み、ポートフォリオ分析と詳細な可視化を行う包括的なPythonツールです。

## 主な機能

- **複数証券会社対応**: 楽天証券、SBI証券、Wiseのデータを読み込み・標準化
- **ポートフォリオ分析**: 保有銘柄、損益、パフォーマンス指標を計算
- **マーケットデータ統合**: Yahoo Finance/STOOQから為替・株価データをダウンロード
- **包括的な可視化**: ポートフォリオ概要、取引活動、個別銘柄のチャートを生成
- **JSONエクスポート**: 取引データを構造化JSONフォーマットで出力
- **投資信託自動マッピング**: 投資信託名から自動的にティッカーコードを抽出（136種類対応）
- **代替データソース**: STOOQメインで日本株により良いカバレッジを提供

## クイックスタート

### インストール

1. **プロジェクトをクローンまたはダウンロード**
2. **依存関係をインストール**:
   ```bash
   pip install -r requirements.txt
   ```

### データ設定

1. **データディレクトリを作成**（初回実行時に自動作成）:
   ```
   data/
   ├── raw/           # CSVファイルをここに配置
   ├── processed/     # 処理済みデータファイル
   └── output/        # 分析結果とチャート
   ```

2. **取引データファイルを `data/raw/` に配置**（サブディレクトリ対応）:
   - 楽天ファイル: `*JP*.csv`, `*US*.csv`, `*INVST*.csv`, `*CH*.csv`
   - SBIファイル: `SaveFile*.csv`, `yakujo*.csv`
   - Wiseファイル: `cleaned_wise_data*.csv`
   - **サブディレクトリ対応**: `data/raw/RAWDATA/rakuten/` 等の任意のフォルダ構造可能

### 分析実行

**基本的な使用方法**:
```bash
# 完全分析（マーケットデータダウンロード + 分析）
python3 main.py

# STOOQを使用（日本株推奨）
python3 main.py --alternative-data

# JSONエクスポート付き
python3 main.py --export-json

# STOOQとJSONエクスポートの組み合わせ（推奨）
python3 main.py --alternative-data --export-json

# マーケットデータダウンロードをスキップ
python3 main.py --skip-download

# JSONのみエクスポート（分析なし）
python3 main.py --json-only

# チャートのみ作成
python3 main.py --charts-only
```

## 新機能詳細

### JSONエクスポート機能

取引データと銘柄コードを構造化されたJSONフォーマットで出力します。**投資信託の銘柄名から自動的にティッカーコードを抽出**し、STOOQでの履歴データ取得を可能にします。

**投資信託の自動マッピング**:
- "eMAXIS Slim 全世界株式(オール・カントリー)" → `ACWI`
- "ＳＢＩ・新興国株式インデックス・ファンド(雪だるま（新興国株式）)" → `VWO`
- "＜購入・換金手数料なし＞ニッセイ新興国株式インデックスファンド" → `VWO`
- "ＳＢＩ・全世界株式インデックス・ファンド" → `ACWI`

**出力例**:
```json
{
  "metadata": {
    "total_trades": 14,
    "date_range": {"start": "2020-09-18", "end": "2025-02-25"},
    "currencies": ["JPY", "USD", "HKドル"],
    "data_sources": ["rakuten_us_...", "sbi_domestic_..."]
  },
  "trades": [
    {
      "trade_date": "2020-09-29T00:00:00",
      "security_code": "VDE",
      "security_name": "VA ENERGY",
      "transaction_type": "buy",
      "quantity": 2.0,
      "price": 41.31,
      "settlement_amount": 8772.0,
      "currency": "USD"
    }
  ]
}
```

### STOOQデータソース（推奨）

**日本株での高い成功率**:
- `2563`: 1,250件の履歴データ
- `2621`: 1,174件の履歴データ  
- `2837`: 878件の履歴データ

**設定済み**:
- STOOQを主要データソースとして設定
- 1.5秒のレート制限（高速化）
- 自動フォールバック機能

### データソースカバレッジ

| 資産タイプ | STOOQ | Yahoo Direct | Alpha Vantage | 推奨 |
|------------|-------|--------------|---------------|------|
| 日本株（TSE） | ✅ 優秀 | ❌ 限定的 | ✅ 良好 | STOOQ |
| 米国株/ETF | ⚠️ 限定的 | ✅ 良好 | ✅ 優秀 | Yahoo + Alpha Vantage |
| 欧州株 | ✅ 良好 | ✅ 良好 | ✅ 良好 | いずれか |
| アジア市場 | ✅ 良好 | ⚠️ 限定的 | ⚠️ 限定的 | STOOQ |

## プロジェクト構成

```
trahist/
├── main.py                    # メインエントリーポイント
├── config.py                  # 設定ファイル
├── requirements.txt           # 依存関係
├── README.md                  # このファイル
├── data/                      # データディレクトリ
│   ├── raw/                   # 生CSVファイル
│   ├── processed/             # 処理済みデータ
│   └── output/                # 結果とチャート
│       ├── charts/            # 可視化チャート
│       ├── json_data/         # JSONエクスポート
│       └── historical_data/   # 代替データダウンロード
├── src/                       # ソースコード
│   ├── data/                  # データ処理
│   │   └── loaders.py         # データ読み込みユーティリティ
│   ├── market/                # マーケットデータ
│   │   ├── forex.py           # 為替データ管理
│   │   ├── stocks.py          # 株価データ
│   │   ├── data_converter.py  # JSONエクスポート
│   │   └── alternative_data.py # 代替データソース
│   ├── analysis/              # 分析モジュール
│   │   ├── portfolio.py       # ポートフォリオ分析
│   │   └── visualization.py   # チャート生成
│   └── utils/                 # ユーティリティ
│       └── helpers.py         # ヘルパー関数
├── DIC/                       # レガシーデータ（フォールバック）
│   ├── forex_data.csv         # フォールバック為替データ
│   ├── charts.csv             # フォールバック株価
│   └── *.csv                  # その他参照データ
└── CODES/                     # レガシーコード（参考用）
```

## 対応データフォーマット

### 楽天証券
- **日本株**: `*JP*.csv` - 約定日, 銘柄コード, 売買区分等
- **米国株**: `*US*.csv` - 約定日, ティッカー, 売買区分等
- **投資信託**: `*INVST*.csv` - ファンド名, 取引等
- **中国・香港株**: `*CH*.csv` - 約定日, 銘柄コード, 通貨等

### SBI証券
- **国内**: `SaveFile*.csv` ファイル（8行スキップ）
- **外国**: `yakujo*.csv` ファイル（2行スキップ）

### Wise（外貨両替）
- 前処理済みファイル: `cleaned_wise_data*.csv`

## 出力ファイル

### 分析結果
- `portfolio_holdings_TIMESTAMP.csv` - 現在のポートフォリオ保有銘柄
- `security_performance_TIMESTAMP.csv` - 銘柄別パフォーマンス
- `trades_TIMESTAMP.csv` - 処理済み取引データ

### JSONエクスポート
- `trades_YYYYMMDD_HHMMSS.json` - 構造化された取引データ
- `ticker_codes_YYYYMMDD_HHMMSS.json` - 抽出された銘柄コード

### マーケットデータ
- `forex_data.csv` - ダウンロード済み為替レート
- `stock_prices.csv` - ダウンロード済み株価
- `combined_historical_prices.csv` - 代替ソースからの履歴データ
- `historical_data_metadata.json` - データソースメタデータ

### 可視化
- `portfolio_overview.png` - ポートフォリオサマリーチャート
- `trading_activity.png` - 取引パターンと活動
- `performance_summary.png` - パフォーマンス分析
- `securities/` - 個別銘柄チャート

## 設定

`config.py`で以下をカスタマイズ:
- データディレクトリ
- マーケットデータソース（STOOQが主）
- 異なる証券会社のカラムマッピング
- 日付範囲やその他設定

### 代替データソース設定
```python
ALTERNATIVE_DATA_SOURCES = {
    'default_sources': ['stooq'],  # STOOQを最優先
    'rate_limit_seconds': 1.5,     # STOOQは高速
    'request_timeout': 30,
    'retry_count': 3,
    'max_symbols_per_batch': 50
}
```

### JSONエクスポート設定
```python
JSON_EXPORT = {
    'enable_auto_export': True,    # 分析後自動エクスポート
    'export_directory': 'json_data',
    'include_metadata': True,
    'pretty_print': True
}
```

## エラーハンドリング

システムは堅牢なエラーハンドリングを含みます:
- **自動フォールバック**: STOOQが失敗した場合、Yahoo Direct、その後Alpha Vantageを試行
- **レート制限**: リクエスト間に1.5秒の遅延（API制限回避）
- **リトライロジック**: 失敗したリクエストを最大3回再試行
- **グレースフルデグラデーション**: 一部の銘柄が失敗しても分析を続行
- **詳細ログ**: 成功/失敗の完全な追跡

## パフォーマンスのヒント

1. **日本株には `--alternative-data` を使用** - yfinanceより優れたカバレッジ
2. **Alpha Vantage APIキーを設定** - 米国市場に最適（無料枠あり）
3. **クイックエクスポートには `--json-only` を使用** - データのみ必要な場合
4. **設定テストには `--skip-download` を最初に実行** - ダウンロード前の設定確認
5. **レート制限を監視** - 制限に引っかかる場合はconfigでdelay_secondsを増加

## 後方互換性

- 既存の全機能は変更なし
- `--alternative-data`を指定しない限りデフォルトはyfinance
- `--export-json`を使用するか自動エクスポートを有効にしない限りJSONエクスポートはオプション
- 既存のコマンドライン引数は全て従来通り動作

## 外部ツールとの統合

JSONフォーマットにより以下との統合が容易:
- **Webアプリケーション** - 直接JSON消費
- **データ分析ツール** - PandasでJSONを直接読み込み
- **API** - 標準REST APIフォーマット
- **データベース** - NoSQLデータベースへのJSONインポート
- **可視化ツール** - Chart.js、D3.js等

## トラブルシューティング

### よくある問題

**データが見つからない**: 
- CSVファイルが`data/raw/`にあることを確認
- ファイル名が期待されるパターンと一致することを確認

**マーケットデータダウンロードが失敗**:
- インターネット接続を確認
- システムは遅延とリトライでレート制限を自動処理
- 利用可能な場合はDICディレクトリの既存データにフォールバック
- 部分的な失敗は適切に処理され、分析は継続

**Yahoo 401エラー**: 使用量が多いと正常な動作、代替としてAlpha Vantageを使用

**STOOQデータなし**: 一部の銘柄は利用不可、銘柄フォーマットを確認

**レート制限**: configで`rate_limit_seconds`を増加

**エンコーディングエラー**:
- システムは自動でエンコーディングを検出、`config.py`で手動指定も可能

### ヘルプ

詳細なログで実行して詳細な操作を確認:
```bash
python3 main.py --alternative-data --export-json 2>&1 | tee analysis.log
```

特定のエラーメッセージと成功率についてはログを確認してください。

## 環境変数（オプション）

```bash
# 追加データソース用APIキーを設定
export ALPHA_VANTAGE_API_KEY="your_key_here"
export POLYGON_API_KEY="your_key_here"
export IEX_API_KEY="your_key_here"
```

## 要件

- Python 3.8+
- pandas, numpy（データ処理用）
- matplotlib, seaborn（可視化用）
- yfinance（マーケットデータ用）
- requests（代替データソース用）
- chardet（エンコーディング検出用）

## ライセンス

このプロジェクトは個人使用用です。証券会社のデータを使用する際は、各社の利用規約に準拠してください。