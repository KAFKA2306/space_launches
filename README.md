# Space Launches — reusable launch primary evidence

[![Space launches evidence](https://github.com/KAFKA2306/space_launches/actions/workflows/space-launches-evidence.yml/badge.svg)](https://github.com/KAFKA2306/space_launches/actions/workflows/space-launches-evidence.yml)
[![Deploy Pages](https://github.com/KAFKA2306/space_launches/actions/workflows/pages.yml/badge.svg)](https://github.com/KAFKA2306/space_launches/actions/workflows/pages.yml)

SpaceX / Blue Origin / Rocket Lab のlaunch・reuse evidenceをoperator公式mission履歴とFAA一次情報から再生成可能な形で追跡します。

## Public dashboard

- Daily entry point: https://kafka2306.github.io/space_launches/
- latest **completed** mission
- completed launch count over the latest 7 / 30 days and year-to-date
- latest explicitly evidenced reuse / recovery event
- future missions shown only as a separate **verified schedule window** at the precision stated by the source
- every public fact links back to canonical data or primary evidence

Pagesは`api/v1/space-launches/`をread-onlyで投影します。`planned`、authorization、completed mission、reuse eventを同じ状態として扱いません。

## Canonical outputs

- [`api/v1/space-launches/index.json`](api/v1/space-launches/index.json) — current coverage / rules / source limitations
- [`api/v1/space-launches/launches.json`](api/v1/space-launches/launches.json) — completed missions
- [`api/v1/space-launches/planned.json`](api/v1/space-launches/planned.json) — planned/upcoming missions, separate from completed
- [`api/v1/space-launches/reuse-events.json`](api/v1/space-launches/reuse-events.json) — explicit booster reflight/recovery/loss/landing events
- [`api/v1/space-launches/monthly-cadence.json`](api/v1/space-launches/monthly-cadence.json) — cadence derived only from completed missions
- [`api/v1/space-launches/authorizations.json`](api/v1/space-launches/authorizations.json) — FAA authorization/program scope
- [`api/v1/space-launches/provenance.json`](api/v1/space-launches/provenance.json) — evidence provenance and verification mode

`index.json` is the authority for current counts and dates; README does not duplicate a hand-maintained coverage snapshot.

## Source authority

1. SpaceX official `content.spacex.com` launch CMS / mission JSON
2. Rocket Lab official completed/upcoming mission index and mission releases
3. Blue Origin official mission index / mission releases
4. FAA commercial-space licensing statements

Third-party launch aggregators are not canonical sources.

### Live and reviewed evidence remain separate

SpaceX / Rocket Lab / FAA sources are fetched live in GitHub Actions and stored with SHA-256 provenance.

Blue Origin official pages have returned HTTP 429 to GitHub-hosted runners. Blue Origin mission/reuse evidence is therefore explicitly represented as `reviewed_primary_url`, with official URL, review date and committed evidence hash. It is never labeled as live-fetched evidence.

## Data contract

- `completed` and `planned` are separate tables
- launch cadence uses completed mission dates only
- a future schedule is displayed only at the date precision stated by the source; no exact date is invented
- first-stage reuse / recovery / landing / loss is recorded only when explicitly stated by an operator or regulator
- launch count is not used to infer booster reuse count
- FAA program authorization is not presented as mission completion or an invented per-flight license
- operator / vehicle / mission / launch site / date / source identity are retained
- `live_fetched_primary` and `reviewed_primary_url` remain distinct verification states
- source schema drift or missing required markers fails closed

## Rebuild and verification

No external Python package is required for the canonical collector.

```bash
python -m py_compile space_launches.py test_space_launches.py
python -m unittest -v test_space_launches test_sanitize_external_evidence
python space_launches.py
```

Offline deterministic rebuild:

```bash
python space_launches.py --offline \
  --data-root data/space-launches \
  --api-dir build/rebuilt-space-launches
```

- `Space launches evidence` performs live source collection, provenance/coverage audit and byte-for-byte offline rebuild verification.
- `Deploy Pages` validates the public dashboard contract on pull requests and, on main, deploys canonical JSON with `deployment.json`, then verifies the exact deployed commit.

## Scope

This repository owns launch cadence, vehicle/operator evidence, FAA authorization scope and explicit reuse/recovery evidence for the Reusable Rockets theme. Stock prices, portfolio decisions and broker history are outside this repository.
