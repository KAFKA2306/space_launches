
# LEGACY README - OLD VERSION

⚠️ **This is the old README for reference only. Please use the new system described in README.md**

## New System

The project has been completely rebuilt with a modern architecture. Use:

```bash
python3 main.py
```

For the new, improved trade history analyzer.

---

# Original README (Legacy)

## 概要
このプロジェクトは、異なる取引履歴のCSVファイルを統合し、データをクリーンアップし、EDA（探索的データ分析）を行うための一連のスクリプトを提供します。最終的には、取引履歴データを分析し、視覚化することを目的としています。

## ディレクトリ構成
```
TRADEHISTORY/
├── CODES/               # ⚠️ LEGACY CODE - Use new main.py instead
│   ├── 0fx.py               # 為替データをダウンロードするスクリプト
│   ├── 1concat.py           # CSVファイルを統合するスクリプト
│   ├── 2clean.py            # データをクリーンアップするスクリプト
│   ├── 3eda.py              # EDAを実施するスクリプト
├── DIC/                 # ⚠️ LEGACY DATA DIRECTORY
│   ├── forex_data.csv       # ダウンロードした為替データ
│   ├── securitycode.csv      # 銘柄コードデータ
├── RAWDATA/             # ⚠️ LEGACY - Use data/raw/ instead
│   ├── rakuten/             # 楽天の取引データ
│   ├── sbi/                 # SBI証券の取引データ
```

## 必要なライブラリ
```bash
pip install pandas numpy matplotlib seaborn yfinance chardet
```

## 使用方法

⚠️ **DEPRECATED - Use the new system:**

```bash
python3 main.py
```

### Legacy Usage (for reference only)

### 1. 為替データのダウンロード
`0fx.py`を実行して、指定した通貨ペアの為替データをダウンロードします。
```bash
python CODES/0fx.py
```

### 2. CSVファイルの統合
`1concat.py`を実行して、複数の取引履歴CSVファイルを統合します。
```bash
python CODES/1concat.py
```

### 3. データのクリーンアップ
`2clean.py`を実行して、統合されたデータをクリーンアップします。
```bash
python CODES/2clean.py
```

### 4. EDAの実施
`3eda.py`を実行して、クリーンアップされたデータに対して探索的データ分析を行います。
```bash
python CODES/3eda.py
```


## 出力ファイル
- 統合された取引履歴データは、`integrated_trade_history_YYYYMMDD.csv`として保存されます。
- クリーンアップされたデータは、`trade_history3.csv`として保存されます。
- EDAの結果や視覚化は、`EDA_results`フォルダに保存されます。

## 注意事項
- 各スクリプトは、適切なフォルダパスを指定する必要があります。特に、`RAWDATA`フォルダ内に取引データが存在することを確認してください。
