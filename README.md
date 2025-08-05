# 取引履歴分析ツール

複数の証券会社から取引履歴を読み込み、**JPY統一価格で**ポートフォリオ分析と詳細な可視化を行う包括的なPythonツールです。投資信託の自動マッピングと通貨統一機能により、**日本株・外国株・投資信託を一元管理**できます。

## 主な機能

- **複数証券会社対応**: 楽天証券、SBI証券、Wiseのデータを読み込み・標準化
- **JPY統一価格算出**: 全取引をJPY基準で統一比較（為替レート自動適用）
- **投資信託10,000倍ルール対応**: 日本の投資信託価格表記を自動調整
- **投資信託自動マッピング**: 投資信託名から自動的にティッカーコードを抽出（136種類対応）
- **統一CSV出力**: 日本株・外国株・投資信託を統一項目でCSV出力
- **包括的な可視化**: ポートフォリオ概要、取引活動、個別銘柄のチャートを生成
- **JSONエクスポート**: 取引データを構造化JSONフォーマットで出力
- **代替データソース**: STOOQメインで日本株により良いカバレッジを提供

## 💡 このツールを使う理由

### 問題
- 複数証券会社のデータがバラバラで統合が困難
- 投資信託名が複雑で銘柄コードが不明
- USD・JPY・HKドルなど通貨がバラバラで比較困難
- 投資信託の価格表記（10,000倍）が株式と異なる

### 解決
- **一つのツールで全証券会社のデータを統一処理**
- **投資信託名を自動でティッカーコードに変換**
- **全取引をJPY統一価格で比較可能**
- **統一CSVで Excel やデータ分析ツールでも活用可能**

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

**推奨使用方法**:
```bash
# 🎯 最も重要：統一CSV作成（JPY価格統一 + 投資信託マッピング）
python3 main.py --unified-csv

# 🚀 完全分析（統一CSV + JSON + チャート + STOOQデータ）
python3 main.py --alternative-data --export-json

# 基本分析（従来のyfinanceベース）
python3 main.py
```

**その他のオプション**:
```bash
# JSONのみエクスポート（分析なし、高速）
python3 main.py --json-only

# マーケットデータダウンロードをスキップ（既存データ使用）
python3 main.py --skip-download

# チャートのみ作成（既存データからグラフ生成）
python3 main.py --charts-only

# STOOQを使用（日本株で高精度、yfinanceより安定）
python3 main.py --alternative-data
```

## 🆕 新機能詳細

### 1. 統一CSV機能（最重要）

**全取引を統一項目でCSV出力**し、ExcelやPythonで簡単に分析できます。

**出力される統一CSV**:
- `trades_unified_YYYYMMDD_HHMMSS.csv` - **統一価格付き取引データ**
- `fund_ticker_mapping_YYYYMMDD_HHMMSS.csv` - **投資信託→ティッカー対応表**

**統一CSV項目**:
```csv
trade_date,settlement_date,security_code,original_security_code,security_name,
transaction_type,quantity,price,price_jpy_unified,settlement_amount,
amount_jpy_unified,currency,conversion_rate,is_investment_fund,
fund_10000x_applied,ticker_mapped,account_type,data_source
```

**実際の変換例**:
```csv
2020-09-29,2020-10-01,VDE,,VA ENERGY,buy,2.0,41.31,6196.5,8772.0,1315800.0,USD,150.0,False,False,False,特定,rakuten_us_...
2020-09-18,2020-09-25,VWO,,ＳＢＩ・新興国株式インデックス・ファンド,buy,494.0,1.012,1.012,5001.0,5001.0,JPY,1.0,True,True,True,特定,rakuten_investment_...
```

### 2. 投資信託自動マッピング

**136種類の投資信託名を自動でティッカーコードに変換**します。

**マッピング例**:
- `eMAXIS Slim 全世界株式(オール・カントリー)` → **ACWI**
- `ＳＢＩ・新興国株式インデックス・ファンド(雪だるま（新興国株式）)` → **VWO**  
- `＜購入・換金手数料なし＞ニッセイ新興国株式インデックスファンド` → **VWO**
- `楽天・全米株式インデックス・ファンド（楽天・バンガード・ファンド（全米株式））` → **VOO**
- `Tracers S&P500トップ10インデックス(米国株式)` → **NOBL**

### 3. JPY統一価格算出

**全ての取引を統一JPY価格で比較**できます。

**変換ルール**:
- **外貨取引**: 取引日の為替レートを自動適用
- **投資信託**: 10,000倍ルールを自動適用（例：10,120円 → 1.012円）
- **日本株・ETF**: そのまま使用

**通貨対応**:
- JPY（日本円）、USD（米ドル）、HKD（香港ドル）、EUR（ユーロ）
- CNY（中国元）、GBP（英ポンド）、その他15種類の通貨エイリアス

### 4. JSONエクスポート機能

**構造化されたJSONフォーマット**で取引データを出力し、API連携やWeb開発で活用できます。

**出力例**:
```json
{
  "metadata": {
    "total_trades": 14,
    "date_range": {"start": "2020-09-18", "end": "2025-02-25"},
    "currencies": ["JPY", "USD", "HKドル"]
  },
  "trades": [
    {
      "trade_date": "2020-09-29T00:00:00",
      "security_code": "VDE",
      "security_name": "VA ENERGY",
      "price_jpy_unified": 6196.5,
      "amount_jpy_unified": 1315800.0,
      "conversion_info": {
        "exchange_rate": 150.0,
        "is_investment_fund": false
      }
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

## 📁 対応データフォーマット

このツールは以下の証券会社・サービスのCSVファイルに対応しています。

### 楽天証券
1. **日本株取引**: `rakuten_jp_tradehistory(JP)_YYYYMMDD.csv`
   - 必要列: 約定日, 銘柄コード, 銘柄名, 売買区分, 数量［株］, 単価［円］, 受渡金額［円］
   - 例: `7203`,`トヨタ自動車`,`買付`,`100`,`2500.0`,`250000`

2. **米国株取引**: `rakuten_us_tradehistory(US)_YYYYMMDD.csv`
   - 必要列: 約定日, ティッカー, 銘柄名, 売買区分, 数量［株］, 単価［USドル］, 受渡金額［円］
   - 例: `AAPL`,`APPLE INC`,`買付`,`10`,`150.0`,`165000`

3. **投資信託取引**: `rakuten_investment_tradehistory(INVST)_YYYYMMDD.csv`
   - 必要列: 約定日, ファンド名, 取引, 数量［口］, 単価, 受渡金額, 口座
   - 例: `eMAXIS Slim 全世界株式`,`買付`,`1000`,`15230`,`15230`

4. **中国・香港株取引**: `rakuten_ch_tradehistory(CH)_YYYYMMDD.csv`
   - 必要列: 約定日, 銘柄コード, 銘柄名, 通貨, 売買区分, 数量, 単価, 約定金額
   - 例: `2837`,`グローバルX ハンセン・テック ETF`,`HKドル`,`買付`,`600`,`7.1`

### SBI証券
1. **国内取引**: `SaveFile_XXXXXX_XXXXXX.csv`
   - ヘッダー8行をスキップ
   - 必要列: 約定日, 銘柄コード, 銘柄, 取引, 約定数量, 約定単価, 受渡金額
   - 例: `ＳＢＢ・全世界株式インデックス・ファンド`,`買付`,`50000`,`18803`,`120000`

2. **外国株取引**: `yakujo_XXXXXX.csv`
   - ヘッダー2行をスキップ  
   - 必要列: 約定日, 銘柄コード, 取引, 数量, 単価, 受渡金額

### Wise（外貨両替サービス）
- **両替履歴**: `cleaned_wise_data_YYYYMMDD.csv`
- 必要列: 完了日, 為替レート, 送金元通貨, 受取通貨, 送金額, 受取額
- 例: `2023-01-15`,`150.5`,`USD`,`JPY`,`1000`,`150500`

### ポートフォリオデータ（オプション）
- **資産残高**: `assetbalance_YYYYMMDD.csv`
- 現在の保有銘柄と残高情報

## 📊 データ使用方法の詳細

### ステップ1: データ準備
```
data/raw/
├── rakuten_jp_tradehistory(JP)_20250805.csv     # 楽天日本株
├── rakuten_us_tradehistory(US)_20250805.csv     # 楽天米国株  
├── rakuten_investment_tradehistory(INVST)_20250805.csv  # 楽天投資信託
├── rakuten_ch_tradehistory(CH)_20250805.csv     # 楽天中国・香港株
├── sbi_domestic_SaveFile_000001_000141.csv      # SBI国内
└── cleaned_wise_data_20250805.csv               # Wise外貨両替
```

### ステップ2: 実行
```bash
# 統一CSV作成（推奨）
python3 main.py --unified-csv
```

### ステップ3: 出力確認
```
data/output/
├── unified_csv/
│   ├── trades_unified_20250805_143022.csv       # 🎯 統一取引データ
│   └── fund_ticker_mapping_20250805_143022.csv  # 投資信託マッピング表
├── json_data/
│   ├── trades_20250805_143022.json              # JSON取引データ
│   └── ticker_codes_20250805_143022.json        # ティッカー一覧
└── charts/
    ├── trading_activity.png                     # 取引活動チャート
    └── performance_summary.png                  # パフォーマンス概要
```

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

## 📈 活用例

### Excel・スプレッドシートでの分析
```bash
# 統一CSVを作成
python3 main.py --unified-csv

# data/output/unified_csv/trades_unified_*.csv をExcelで開く
# → JPY統一価格で全取引を比較・分析可能
```

### Pythonでの詳細分析
```python
import pandas as pd

# 統一CSVを読み込み
df = pd.read_csv('data/output/unified_csv/trades_unified_20250805_143022.csv')

# JPY統一価格での分析
total_investment = df['amount_jpy_unified'].sum()
by_currency = df.groupby('currency')['amount_jpy_unified'].sum()
fund_investments = df[df['is_investment_fund'] == True]['amount_jpy_unified'].sum()

print(f"総投資額: {total_investment:,.0f} JPY")
print(f"投資信託投資額: {fund_investments:,.0f} JPY")
```

### データ可視化・ダッシュボード構築
```python
# 投資信託マッピング表の活用
mapping_df = pd.read_csv('data/output/unified_csv/fund_ticker_mapping_*.csv')
print("投資信託→ティッカーコード対応表:")
print(mapping_df[['original_fund_name', 'ticker_code']])
```

## 🔧 技術仕様

### 動作環境
- **Python**: 3.8以上
- **OS**: Windows, macOS, Linux
- **メモリ**: 最低1GB（大量データの場合は2GB以上推奨）

### 依存ライブラリ
```txt
pandas>=2.0.0              # データ処理
numpy>=1.24.0              # 数値計算
matplotlib>=3.6.0          # グラフ作成
seaborn>=0.12.0            # 統計可視化
yfinance>=0.2.0            # 従来の株価データ
pandas-datareader>=0.10.0  # STOOQ連携
python-dateutil>=2.8.0     # 日付処理
chardet>=5.0.0             # エンコーディング検出
openpyxl>=3.1.0            # Excel対応（オプション）
```

### データ処理能力
- **取引件数**: 10,000件以上の取引履歴に対応
- **証券会社**: 5社以上の同時処理
- **投資信託**: 136種類の自動マッピング
- **通貨**: 15種類の通貨・エイリアス対応

## ⚠️ 注意事項・制限事項

### データ取り扱い
- **個人データ**: 証券会社のデータは機密情報です。適切に管理してください
- **利用規約**: 各証券会社の利用規約に準拠してデータを使用してください
- **バックアップ**: 重要なデータは必ずバックアップを取ってください

### 技術的制限
- **為替レート**: インターネット接続が必要（オフラインの場合はフォールバック値を使用）
- **投資信託マッピング**: 新しいファンドは手動でDIC/securitycode2.csvに追加が必要
- **エンコーディング**: 日本語CSVファイルはShift-JISまたはUTF-8に対応

### API制限
- **STOOQ**: 無料サービスのため、大量リクエスト時は遅延あり
- **Yahoo Finance**: レート制限があるため、大量の銘柄処理時は時間がかかる場合あり

## 🆘 トラブルシューティング

### よくある問題と解決方法

**❌ エラー: `ModuleNotFoundError: No module named 'pandas_datareader'`**
```bash
# 解決方法
pip install pandas-datareader python-dateutil
```

**❌ エラー: `KeyError: 'Column not found: amount_jpy'`**
```bash
# 解決方法: 為替データが不足している場合
python3 main.py --skip-download  # 既存データで実行
```

**❌ 投資信託がマッピングされない**
```bash
# 確認方法
python3 main.py --unified-csv
# data/output/unified_csv/fund_ticker_mapping_*.csv でマッピング結果を確認
```

**❌ STOOQからデータが取得できない**
```bash
# フォールバック: 従来のyfinanceを使用
python3 main.py  # --alternative-dataオプションを外す
```

## 📞 サポート・フィードバック

### ログの確認方法
```bash
# 詳細ログ付きで実行
python3 main.py --unified-csv 2>&1 | tee analysis.log

# ログファイルを確認
cat analysis.log | grep ERROR
```

### よくある質問（FAQ）

**Q: 新しい証券会社のCSVに対応してもらえますか？**
A: `config.py`の`BROKER_PATTERNS`と`COLUMN_MAPPINGS`を追加することで対応可能です。

**Q: 投資信託の価格が正しく変換されません**
A: `src/market/currency_converter.py`の`_is_investment_fund()`メソッドで判定ロジックを確認してください。

**Q: 統一CSVをExcelで開いた時に文字化けします**
A: ExcelでCSVを開く際は「データ」→「外部データの取り込み」→「CSV」→「UTF-8」を選択してください。

## ライセンス

このプロジェクトは個人使用用です。証券会社のデータを使用する際は、各社の利用規約に準拠してください。