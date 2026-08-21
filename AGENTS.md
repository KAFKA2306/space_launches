# AGENTS.md

## Repository responsibility

This repository owns primary-source evidence for reusable commercial launch activity. Do not reintroduce the former broker trade-history, portfolio, market-data, dashboard, or IFA-onboarding surfaces.

## Canonical sources

1. SpaceX official completed mission index and mission pages
2. Rocket Lab official completed/upcoming mission index and operator releases
3. Blue Origin official mission index and mission releases
4. FAA commercial-space licensing statements and Part 450 transition evidence
5. Derived views rebuilt from stored raw evidence

## Autonomous execution

1. Re-read current `main`, README, open Issues/PRs, canonical launch/reuse evidence, workflows/tests and public outputs before choosing work.
2. Continue one existing canonical workline for the same operational outcome before creating another collector, dataset, branch or Issue.
3. Prefer newly verified completed/reentry/reuse events, identity/status corrections, deterministic cadence/reuse views, public usability, then simplification that removes recurring work.
4. Require primary event evidence and stable identity before counting a mission, recovery or reuse occurrence.
5. Run the smallest relevant checks and verify the exact reviewed revision before merge.
6. Stop at the fixed point. Do not fill schedule gaps or future launch outcomes by inference, and do not churn a blocked source if external state has not changed.

Cross-repository ARK/market forecast comparison belongs in `investor2`; do not duplicate forecast authority here. Do not execute trades, transfers or account actions.

## Evidence rules

- Completed and planned missions are separate tables.
- Launch cadence is computed only from completed missions.
- Booster reuse, recovery, landing, loss, or reentry is recorded only when a primary source explicitly states it.
- Do not infer a per-flight FAA license identifier when the source only provides program/portfolio authorization.
- Preserve the operator/vehicle/mission/site/date/source identity and raw SHA-256 provenance.
- Unknown or changed source structure fails closed.
- Delete obsolete duplicate paths instead of adding compatibility fallbacks.

## Merge and release are separate

### PR merge conditions

A PR may merge when the deterministic repository-local launch/reuse contract is correct on the exact head revision: identity/status/provenance semantics hold, focused tests pass, offline/generated views are reproducible where affected, and no unresolved review or correctness blocker remains.

A future mission outcome, live operator/FAA fetch after merge, production publication, or public endpoint availability is **not** a merge condition unless the PR specifically changes the release/live-acquisition mechanism and that mechanism must be validated before merge.

### Product/data release conditions

Release is a separate post-merge decision. Treat launch/reuse evidence as released only after the merged `main` revision is read back and the release requirements in scope are actually executed, including live primary-source verification when required, published/generated artifacts, public surface if any, deployment identity, and rollback/rebuild path.

A merged PR does not prove a mission occurred or production data were released. A release/live-source blocker may block release without invalidating a correctly merged repository change. Report merge and release independently.

## Required checks

```bash
python -m py_compile space_launches.py test_space_launches.py
python -m unittest -v test_space_launches
```

These checks are merge evidence. The `Space launches evidence` workflow or equivalent live source/coverage run is release evidence when live production acquisition is in scope. A layer that did not run is not PASS.

## Completion report

Report verified launch/reuse evidence Before -> After, primary/raw evidence and canonical artifact, Issue/PR/commit/check evidence, then report `merged` and `released` separately with direct evidence for each. Include duplicate/manual work removed and the remaining verified blocker.