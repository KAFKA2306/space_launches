# 取引履歴分析ツール (Trade History Analyzer)

複数の証券会社から取引履歴を読み込み、**JPY統一価格で**ポートフォリオ分析と詳細な可視化を行う包括的なPythonツールです。投資信託の自動マッピングと通貨統一機能により、**日本株・外国株・投資信託を一元管理**できます。

## 📥 クイックスタート

### セットアップ
```bash
# クローンと依存関係インストール
git clone <repository-url>
cd trahist
pip install -r requirements.txt

# Taskランナーのインストール (オプションだが推奨)
# https://taskfile.dev/installation/
```

### 実行コマンド (Taskfile推奨)
本プロジェクトは `Taskfile` を使用して簡単に実行できます。

| タスク | コマンド | 説明 |
| :--- | :--- | :--- |
| **標準分析** | `task run` | データの読み込み、基本分析、チャート作成を実行します。 |
| **詳細分析** | `task analyze` | 統一CSVを用いたより深いポートフォリオ分析を行います。 |
| **ヘルプ** | `task --list` | 利用可能なタスク一覧を表示します。 |

#### オプション引数の渡し方
`--` の後に引数を指定します。
```bash
# マーケットデータをダウンロードして実行
task run -- --download

# 統一CSVのみ作成
task run -- --unified-csv

# 詳細分析で保有銘柄のみ表示
task analyze -- --holdings-only
```

---

## 🌟 主な機能

1.  **マルチブローカー対応**: 楽天証券、SBI証券、Wiseのデータを自動判別・読み込み。
2.  **投資信託自動マッピング**: 
    - `eMAXIS Slim 全世界株式` → `ACWI`
    - `楽天・全米株式` → `VOO`
    - **10,000倍価格ルール**（基準価額）を自動補正。
3.  **JPY統一価格評価**: 全外貨資産（USD, HKD等）を履歴為替レートを用いてJPY換算。
4.  **高度なポートフォリオ分析**: `task analyze` による機関投資家レベルのレポート作成。
5.  **データ可視化**: 資産配分円グラフ、パフォーマンストレンド、個別銘柄チャート。
6.  **STOOQデータ連携**: 日本株の正確な履歴データ取得（yfinanceのフォールバック）。

---

## 📁 データの準備

`data/raw/` ディレクトリに各証券会社のCSVファイルを配置してください（サブフォルダ可）。

| 証券会社 | ファイル名パターン | 内容 |
| :--- | :--- | :--- |
| **楽天証券** | `*JP*.csv` | 日本株取引 |
| | `*US*.csv` | 米国株取引 |
| | `*INVST*.csv` | 投資信託取引 |
| | `*CH*.csv` | 中国/香港株取引 |
| **SBI証券** | `SaveFile*.csv` | 国内取引全般 |
| | `yakujo*.csv` | 外国株取引 |
| **Wise** | `cleaned_wise_data*.csv` | 外貨両替履歴 |

---

## 🔍 詳細分析機能 (Unified Analyzer)

`task analyze` (内部実行: `src.analysis.cli`) は、作成された統一CSVを用いてより深い分析を提供します。

### 機能と出力
- **包括的レポート**: `data/output/unified_analysis/*.json`
    - ポートフォリオスコア（A〜D評価）
    - リスク分析（集中投資リスク、流動性リスク）
    - ドルコスト平均法（DCA）の検出
- **アドバンスドチャート**: `data/output/unified_analysis/*.png`
    - 資産アロケーション（地域別、資産クラス別）
    - パフォーマンス分析（シャープレシオ、ドローダウン）

---

## 🏗️ システムアーキテクチャ

### クリーンアーキテクチャ (Clean Architecture)
本プロジェクトは、保守性と拡張性を高めるために以下のディレクトリ構造を採用しています。

```
.
├── Taskfile.yml             # タスクランナー設定
├── README.md                # 本ドキュメント
├── src/                     # ソースコード (全ロジック)
│   ├── main.py              # アプリケーションエントリーポイント
│   ├── config.py            # 設定管理
│   ├── analysis/            # 分析ロジック & CLI
│   ├── data/                # データローダー
│   ├── market/              # 市場データ処理 & マッピング
│   └── utils/               # ユーティリティ
├── resources/               # (旧 DIC) 静的リソース・辞書データ
├── legacy/                  # (旧 CODES) 旧バージョンコード (参照用)
└── data/                    # データ入出力ディレクトリ
    ├── raw/                 # [入力] CSVファイル配置場所
    ├── processed/           # [中間] 標準化されたデータ
    └── output/              # [出力] チャート、レポート、統一CSV
```

### データ処理フロー
```mermaid
graph TD
    RawCSV[CSVファイル群] --> DataLoader
    DataLoader --> Standardizer[標準化処理]
    Standardizer --> CurrencyConv[通貨統一 (JPY)]
    Standardizer --> FundMapper[投資信託マッピング]
    
    FundMapper --> UnifiedData[統一取引データ]
    
    UnifiedData --> PortfolioCalc[ポートフォリオ計算]
    UnifiedData --> Exporter[CSV/JSON出力]
    
    PortfolioCalc --> Metrics[パフォーマンス指標]
    PortfolioCalc --> Visualizer[チャート生成]
    
    MarketData[Stooq/YFinance] --> PortfolioCalc
```

---

## 💻 開発者ガイド

### 環境変数の設定 (オプション)
より高品質なデータのためにAPIキーを設定可能です。
```bash
export ALPHA_VANTAGE_API_KEY="your_key"
```

### 新しい証券会社の追加
1.  `src/config.py` の `BROKER_PATTERNS` にファイル名パターンを追加。
2.  `src/config.py` の `COLUMN_MAPPINGS` にカラム対応定義を追加。
3.  必要に応じて `src/data/loaders.py` に `process_newbroker_data` 関数を実装。

### 投資信託マッピングの拡張
`resources/securitycode2.csv` が辞書ファイルです。または `src/market/fund_dictionary_builder.py` のロジックを確認してください。

---

## 🗒️ 改善履歴と設計ノート (Historical Notes)

### 資産クラス分類ロジックの改善 (Future Design)
現在の `src/analysis/unified_csv_analyzer.py` はハードコードされた分類を含んでいますが、将来的には以下のようなロジックへの移行が計画されています。
- **判定フロー**: Tier 1 (ティッカー) → Tier 2 (名称キーワード) → Tier 3 (データソース/地域)
- **例**: `GLD` (ETF) や `純金ファンド` (投信) は、Vehicleに関わらず **Asset Class: Commodity / Detail: Gold** として統一的に扱うべきです。

### CODESディレクトリからの移行
旧 `CODES/` ディレクトリは `legacy/` に移動されました。これらは `src/` 配下のモダンなオブジェクト指向/モジュール設計に統合されています。

---

## ライセンス
Personal Use Only. 各証券会社のデータ利用規約に従ってください。