# Space Launches

[![Space launches evidence](https://github.com/KAFKA2306/trahist/actions/workflows/space-launches-evidence.yml/badge.svg)](https://github.com/KAFKA2306/trahist/actions/workflows/space-launches-evidence.yml)

**SpaceX / Blue Origin / Rocket Lab の再利用可能ロケット運用を、operator公式mission履歴とFAA一次情報から再生成可能な形で追跡する。**

このrepositoryは旧Trade History Analyzerではありません。broker CSV、portfolio、market-data、dashboard、IFA onboardingの旧surfaceは正準責務から削除します。

## Canonical outputs

- [`api/v1/space-launches/index.json`](api/v1/space-launches/index.json) — coverage / contract
- [`api/v1/space-launches/launches.json`](api/v1/space-launches/launches.json) — 2024年以降のcompleted mission
- [`api/v1/space-launches/planned.json`](api/v1/space-launches/planned.json) — planned/upcoming。completedと混ぜない
- [`api/v1/space-launches/authorizations.json`](api/v1/space-launches/authorizations.json) — FAA authorization/program scope
- [`api/v1/space-launches/reuse-events.json`](api/v1/space-launches/reuse-events.json) — booster reflight/recovery/loss/landingを一次情報が明示したeventだけ保持
- [`api/v1/space-launches/monthly-cadence.json`](api/v1/space-launches/monthly-cadence.json) — completed missionだけから導出した月次cadence
- [`api/v1/space-launches/provenance.json`](api/v1/space-launches/provenance.json) — raw source URL / SHA-256 / retrieval evidence

## Source authority

1. SpaceX公式completed mission index / mission pages
2. Rocket Lab公式completed/upcoming mission index / mission releases
3. Blue Origin公式mission index / mission releases
4. FAA Part 450 transition / commercial-space licensing statements

第三者launch aggregatorを正準sourceにしません。

## Data contract

- `completed` と `planned` は別tableです。延期・予定日を実績へ混ぜません。
- cadenceはcompleted missionの日付だけから計算します。
- first-stage reuse、recovery、landing、loss、reentryはoperator/FAAが明示した場合だけrecord化します。
- launch回数からbooster再利用回数を推定しません。
- FAAがprogram/portfolio authorizationだけを示す場合、存在しないper-flight license IDを作りません。
- operator / vehicle / mission / launch site / date / source identityを保持します。
- 一次sourceの構造・markerが変わればfail closedします。

## Reviewed static evidence

- [`data/blue-origin-launches.json`](data/blue-origin-launches.json) — Blue Origin mission indexからreviewした2024+ mission ledger
- [`data/authorization-registry.json`](data/authorization-registry.json) — FAA authorization scope
- [`data/reuse-events.json`](data/reuse-events.json) — explicit reuse / recovery event

これらのrecordはlive source evidenceへ再結合され、source URL・SHA-256はderived API側へ付与されます。

## Rebuild

依存packageは不要です。Python標準ライブラリだけで実行します。

```bash
python -m py_compile space_launches.py test_space_launches.py
python -m unittest -v test_space_launches
python space_launches.py
```

保存済みraw evidenceだけから再生成:

```bash
python space_launches.py --offline \
  --data-root data/space-launches \
  --api-dir build/rebuilt-space-launches
```

GitHub Actionsではlive一次source取得 → provenance/coverage audit → offline rebuild → byte diffを行います。main/schedule実行時だけ`data/space-launches/`と`api/v1/space-launches/`をcommitします。

## Scope

ARK Big Ideas 2026 `Reusable Rockets` の検証に必要な、launch cadence・vehicle/operator・FAA authorization・明示的reuse/recovery evidenceを担当します。宇宙企業の株価、売買判断、broker履歴は別責務です。
