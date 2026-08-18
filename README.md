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
- [`api/v1/space-launches/provenance.json`](api/v1/space-launches/provenance.json) — live raw evidenceとreviewed primary evidenceのprovenance

## Source authority

1. SpaceX公式frontendが利用する `content.spacex.com` のlaunch CMS JSON / mission JSON
2. Rocket Lab公式completed/upcoming mission index / mission releases
3. Blue Origin公式mission index / mission releases
4. FAA Part 450 transition / commercial-space licensing statements

SpaceXは公開WebのJS shellをHTML解析せず、公式frontend自身が読む `launches-page-tiles` JSONの `missionStatus / launchDate / launchSite / vehicle / link` を正準化します。booster再利用の詳細は同じ公式CMSのmission JSONへ戻ります。第三者launch aggregatorを正準sourceにしません。

### Live と reviewed を混同しない

SpaceX / Rocket Lab / FAA はGitHub Actionsからlive取得し、raw responseをSHA-256 content-addressed保存します。

Blue Origin公式ページは2026-08-19時点でGitHub-hosted runnerへHTTP 429を返すため、Blue Originの2024+ mission ledgerとNG-1/NG-2 reuse evidenceは `reviewed_primary_url` として明示的に分離しています。公式URL・review日・committed evidence hash・`live_fetch_status` を保持し、live取得済みとは表示しません。Blue Origin側のtransportが将来利用可能になれば、この境界を消さずlive evidenceへ昇格させます。

## Data contract

- `completed` と `planned` は別tableです。延期・予定日を実績へ混ぜません。
- cadenceはcompleted missionの日付だけから計算します。
- first-stage reuse、recovery、landing、loss、reentryはoperator/FAAが明示した場合だけrecord化します。
- launch回数からbooster再利用回数を推定しません。
- FAAがprogram/portfolio authorizationだけを示す場合、存在しないper-flight license IDを作りません。
- operator / vehicle / mission / launch site / date / source identityを保持します。
- `live_fetched_primary` と `reviewed_primary_url` を同じverification stateとして扱いません。
- 一次sourceの構造・markerが変わればfail closedします。

## Reviewed static evidence

- [`data/blue-origin-launches.json`](data/blue-origin-launches.json) — Blue Origin公式mission indexをreviewした2024+ mission ledger。live取得ではないことをmetadataで保持
- [`data/authorization-registry.json`](data/authorization-registry.json) — FAA authorization scope。FAA sourceはlive verification対象
- [`data/reuse-events.json`](data/reuse-events.json) — explicit reuse / recovery event。SpaceX/Rocket Labはlive source、Blue Originはreviewed primary sourceを明示

Derived APIにはsource URL・verification mode・SHA-256 evidenceを付与します。

## Current verified coverage

2026-08-19のPR verificationでは、2024-01-02〜2026-08-15について次を再生成しました。

- completed missions: 468
  - SpaceX: 406
  - Rocket Lab: 45
  - Blue Origin: 17
- US launches: 417
- Rocket Lab planned missions: 14
- FAA authorization records: 5
- explicit reuse/recovery events: 4
- live primary sources: 6
- reviewed primary sources: 3

この数字はREADMEを正本にはせず、[`index.json`](api/v1/space-launches/index.json) のcoverageを正準値とします。

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
