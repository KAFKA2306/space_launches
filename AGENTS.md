# Space Launches Agent Contract

`AGENTS.md` is the only repository-wide agent instruction source. Tool-specific instruction files must not duplicate it.

## Data ownership

This repository owns primary-source evidence for commercial launch activity and reuse. Market/forecast comparison belongs elsewhere.

Use official operator mission records and FAA evidence where applicable. Preserve operator, vehicle, mission, site, date, source identity, and raw provenance required by the current schema.

Completed and planned missions are separate. Compute cadence only from completed missions. Record recovery, landing, loss, reentry, or reuse only when primary evidence states it. Do not infer future launch outcomes or per-flight license identifiers from broader authorization.

## Execution

- Prefer current user instruction, current primary evidence, and current code/tests over historical prose.
- Proceed with read-only and reversible work without unnecessary confirmation.
- Reuse one canonical workline and one collector/data path per outcome.
- Delete duplicate paths rather than adding compatibility fallbacks.
- Fail closed when source identity or structure is unknown.

## Verification

Use the smallest relevant checks first:

```bash
python -m py_compile space_launches.py test_space_launches.py
python -m unittest -v test_space_launches
```

Broaden to live source acquisition or public release checks only when the requested outcome requires them.

Merge proves repository correctness for the reviewed revision. Release requires the merged revision and the actual live/published data or surface to be verified separately.

## Completion

Re-read before writes, read back after writes, and stop when the requested evidence or release state is directly verified. Unchecked layers remain `UNVERIFIED`.
