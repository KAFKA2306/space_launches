# Space Launches Agent Contract

`AGENTS.md` is the repository-wide agent instruction source. Tool-specific instruction files must not duplicate it.

## Data contract

This repository owns primary-source evidence for commercial launch activity and reuse. Market/forecast comparison belongs elsewhere.

Use official operator mission records and FAA evidence where applicable. Preserve operator, vehicle, mission, site, date, source identity, and raw provenance required by the current schema.

Completed and planned missions are separate. Compute cadence only from completed missions. Record recovery, landing, loss, reentry, or reuse only when primary evidence states it. Do not infer future launch outcomes or per-flight license identifiers from broader authorization. Fail closed when source identity or structure is unknown.

## Verification

Use the repository checks for changed source/data behavior:

```bash
python -m py_compile space_launches.py test_space_launches.py
python -m unittest -v test_space_launches
```

Live source acquisition and public release are separate claims. Verify them directly only when they are part of the requested outcome.

## Outcome-first task interpretation (Altitude / Depth / Range / Speed)

- **Altitude:** Interpret a task as a verifiable user outcome, not only the named intermediate step. Infer the smallest justified acceptance criteria from the request and current repository state; do not silently expand scope or override explicit instructions.
- **Depth:** Use primary/current evidence and real domain tools and methods. Verify the actual postcondition independently of agent self-report, preferably on the exact changed revision or target runtime.
- **Range:** Combine code, data, tests, runtime/UI, and domain expertise when that materially improves the outcome, while respecting canonical owners and avoiding duplicate systems.
- **Speed:** Complete authorized read-only and reversible work through implementation, focused checks, and read-back without unnecessary approval loops. Bound retries and stop at the proven outcome.
- These principles never bypass repository-specific security, privacy, permission, publication, spending, destructive-action, or release boundaries. State verified results and any remaining `UNVERIFIED` layers.
