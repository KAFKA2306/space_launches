# AGENTS.md

## Repository responsibility

This repository owns primary-source evidence for reusable commercial launch activity. Do not reintroduce the former broker trade-history, portfolio, market-data, dashboard, or IFA-onboarding surfaces.

## Canonical sources

1. SpaceX official completed mission index and mission pages
2. Rocket Lab official completed/upcoming mission index and operator releases
3. Blue Origin official mission index and mission releases
4. FAA commercial-space licensing statements and Part 450 transition evidence
5. Derived views rebuilt from stored raw evidence

## Evidence rules

- Completed and planned missions are separate tables.
- Launch cadence is computed only from completed missions.
- Booster reuse, recovery, landing, loss, or reentry is recorded only when a primary source explicitly states it.
- Do not infer a per-flight FAA license identifier when the source only provides program/portfolio authorization.
- Preserve the operator/vehicle/mission/site/date/source identity and raw SHA-256 provenance.
- Unknown or changed source structure fails closed.
- Delete obsolete duplicate paths instead of adding compatibility fallbacks.

## Required checks

```bash
python -m py_compile space_launches.py test_space_launches.py
python -m unittest -v test_space_launches
```

Production evidence additionally requires the `Space launches evidence` workflow to pass live source verification, coverage audit, and offline deterministic rebuild.
