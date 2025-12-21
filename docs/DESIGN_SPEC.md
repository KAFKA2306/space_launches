# TraHist DESIGN_SPEC v1.0（Final / 凍結仕様）

## 0. 本書の位置づけ（最重要）

本書は TraHist プロジェクトにおける **設計の最終決定文書**である。
本書に記載された内容は、以下に優先する。

* README
* Taskfile.yml
* 実装コード上のコメント
* Web UI の挙動説明
* 過去の設計メモ・議論

本書に反する実装・運用・拡張は、**動作していても不具合とみなす**。

---

## 1. ステータスと変更ポリシー

* **Document Name**: TraHist DESIGN_SPEC
* **Version**: v1.0
* **Status**: Final（凍結）
* **Effective Date**: 本文書承認日以降

### 1.1 変更ルール

* v1.x 系列

  * 許可：バグ修正、実装修正、性能改善、ドキュメント補足
  * 禁止：意味変更、責務変更、成功条件変更

* v2.0 以降

  * 新たな設計としてのみ変更を許可
  * v1.0 との後方互換は保証しない

---

## 2. 基本思想（Core Principle）

TraHist の設計思想は、次の一文に集約される。

> **fetch は resources を更新する操作であり、
> 計算は常に resources を読むだけで行われる**

この原則は、例外なく全レイヤに適用される。

---

## 3. システムの目的と非目的

### 3.1 目的

TraHist は以下を目的とする。

* 金融取引データを **再現可能・検証可能** に処理する
* 外部データ依存（市場価格・為替）を **明示的に管理** する
* 計算結果が「いつ・何を根拠に」出たかを説明可能にする

### 3.2 非目的

以下は TraHist v1.0 の目的外とする。

* 最適な投資判断の提示
* リアルタイム価格の常時取得
* 欠損データの推測・補完
* FIFO/LIFO 等の損益計算ルールの最適化
* 投資信託 NAV の自動収集

---

## 4. パイプライン全体像

TraHist は以下の段階的パイプラインで構成される。

```
raw → interim → resources → unified → report / web
```

各段階は **責務が明確に分離** されており、
上流の責務を下流が侵害してはならない。

---

## 5. ディレクトリ責務定義（凍結）

### 5.1 data/raw

* 役割：証券会社等から取得した元CSVの保管
* 特徴：

  * フォーマット不定
  * スキーマ保証なし
* 制約：

  * 計算で直接参照してはならない

---

### 5.2 data/interim

* 役割：正規化済み中間データ
* 実施内容：

  * 文字正規化（NFKC）
  * 数値正規化（float）
  * 日付正規化（YYYY-MM-DD）
* 制約：

  * 通貨換算・評価計算は禁止
  * 市場価格・為替に触れてはならない

---

### 5.3 resources（Single Source of Truth）

* 役割：外部世界（市場・為替・資産定義）の写像
* 例：

  * forex_data.csv
  * charts.csv
  * asset_master.csv（v2.0）
* 制約：

  * **fetch:m のみが更新可能**
  * run / web / report は読み取り専用
  * fallback 扱いは禁止

---

### 5.4 data/unified

* 役割：計算可能な唯一の真実
* 内容：

  * trades_unified.csv
  * pipeline_status.csv
* 制約：

  * run 以外で生成・更新してはならない
  * discovery（latest 探索）禁止

---

## 6. コマンド責務定義（Task / CLI）

### 6.1 fetch:c（Offline）

* 目的：raw → interim
* ネットワーク：禁止
* 実施内容：

  * raw CSV 読込
  * 正規化
  * interim 出力
* 禁止事項：

  * unified 作成
  * resources 更新

---

### 6.2 fetch:m（Network）

* 目的：resources 更新
* ネットワーク：許可（明示 opt-in）
* 実施内容：

  * 為替データ更新
  * 市場価格更新
* 禁止事項：

  * unified 作成
  * interim 以外の data 更新

---

### 6.3 run

* 目的：オフライン計算パイプライン
* ネットワーク：禁止
* 実施内容：

  * fetch:c 相当処理
  * resources 読込
  * unified CSV 作成
  * pipeline_status 出力
* 禁止事項：

  * resources 更新
  * ネットワークアクセス

---

### 6.4 serve / web

* 目的：表示
* 制約：

  * 計算しない
  * fetch しない
  * pipeline_status を確認してから表示

---

## 7. スキーマ責務とスコープ

### 7.1 スキーマ定義の責務

スキーマ定義は以下のみを規定する。

* 列名
* データ型
* 不変条件
* 欠損の許容可否

### 7.2 明示的スコープ外

以下は **スキーマ定義では扱わない**。

* FIFO / LIFO 等の計算ルール
* 為替補完方法
* 投信 NAV の取得頻度
* 市場休日補正
* 企業同一性（ADR / 現地株）

---

## 8. Unified CSV の位置づけ

* unified は **唯一の計算入口**
* すべての集計・表示・レポートは unified を参照する
* raw / interim / resources を直接参照する実装は禁止

---

## 9. Pipeline Status（成功宣言）

### 9.1 目的

* 実行結果の成否を **機械的に判定**
* Web / CLI / CI の共通基準

### 9.2 mode 別成功条件

#### fetch

* stage_raw_loaded = True
* stage_market_updated ∈ {ran, skipped}

#### run

* stage_raw_loaded = True
* stage_resources_read = True
* stage_unified_written = True

---

## 10. 禁止事項（Hard Rules）

以下は **理由を問わず禁止**。

* run 中のネットワークアクセス
* resources を fallback 扱いする実装
* unified を探索（latest 検索）する実装
* 欠損値を暗黙に 0 補完
* Web UI からの暗黙 fetch
* 成功判定を pipeline_status 以外で行うこと

---

## 11. 設計完了条件（達成済）

* fetch / run / serve の責務分離
* resources の Single Source of Truth 化
* unified の固定パス化
* mode 別成功判定
* オフライン再現可能な run

---

## 12. 最終宣言（Freeze）

本 DESIGN_SPEC v1.0 は、
TraHist における設計判断を将来にわたって固定する。

以後の実装・レビュー・議論は、
本設計に反しないことを前提条件とする。

本設計を変更する場合は、
**DESIGN_SPEC v2.0 を新たに策定すること。**