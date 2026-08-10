# IFA向け取引履歴オンボーディングパック

TraHistの既存offline pipelineで正規化済みの取引データを、匿名case ID単位の引継ぎ資料へ変換するサービスPoCです。コードやraw broker CSVの再配布を商品にしません。

## 対象

- 新規顧客の複数証券会社取引を初回面談前後に整理するIFA・FP・小規模資産管理チーム
- 顧客本人が正当に取得し、処理のために提供した取引履歴を入力とする運用

## 入力境界

`task onboarding:pack -- --case-id case-demo-001` は、既存offline pipelineが生成した次の2ファイルだけを読みます。

- `data/unified/trades_unified.csv`
- `data/unified/pipeline_status.csv`

raw CSVは読み込み対象でも納品対象でもありません。`trades_unified.csv`のschemaが必要列を満たさない場合、pack生成はfail closedします。broker固有CSVの対応可否は既存ingestion側の責務であり、未対応形式をこのpack generatorが推測変換することはありません。

## 納品物

`data/onboarding/<case-id>/` に次を生成します。

- `trades_unified.csv`: 正規化取引。入力側の`data_source`文字列は納品時に除去し、stable hashの`source_ref`へ置換します。
- `holdings.csv`: buy/sellから再構成した数量とJPY cost basis。市場価格は推測せず、`valuation_status=COST_BASIS_ONLY`とします。
- `portfolio_summary.html`: 件数、保有数、cost basis、例外件数だけを表示する静的summary。
- `exceptions.csv`: 欠損値、非数値、負値、既知在庫を超えるsell、保有数量を変えないtransaction typeを明示します。
- `pipeline_status.csv`: upstream pipeline statusを同じcase IDで引き継ぎます。
- `manifest.json`: schema version、case ID、入力境界、raw非同梱、件数、制約を機械可読で記録します。

既存case directoryは上書きしません。

## case ID / 個人情報

case IDは`case-`から始まる小文字英数字・ハイフンだけの匿名slugです。氏名、メールアドレス、口座番号をファイル名に要求しません。raw側の元ファイル名は納品CSVへそのまま出さず、`source_ref`へ変換します。

## 評価境界

この成果物はデータ整理・例外確認用です。売買推奨、銘柄推奨、将来リターン予測は含めません。市場価格が別途検証されていない場合、現在価値をcost basisから推測しません。

sellが既知在庫を超えるなど、入力履歴だけでは再構成できない状態は成功値へ丸めず`exceptions.csv`へ残します。配当等の保有数量を変えない取引もsilent dropせず、正規化取引には保持したうえで例外台帳へ処理状態を残します。

## PoC境界

無料デモではrepository内の匿名fixtureを使います。有償PoCでは、1事業者につき最大3匿名caseの処理、成果物生成、例外レビューを最小納品範囲とします。現行READMEの`Personal Use Only`を変更せず、需要検証段階ではコードを顧客へ再配布しません。

実顧客、商談、デモ、有償転換、継続希望は観測証拠が得られた場合だけ`data/ifa-onboarding-kpis.json`へ記録します。未実施の営業成果をサンプル値で埋めません。
