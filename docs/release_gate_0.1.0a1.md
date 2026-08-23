# Release gate: `0.1.0a1`

## Result

`RLS-001` passes against the exact merged baseline `main@49d6ffd`:

```text
49d6ffd1839258ce14319e157002005c6d2230e1
package version: 0.1.0.a1
tag: v0.1.0a1 -> 8b37e48b65321403bb3eb4ed0fdfe949dc9f1506
```

The tag points to the release-version commit that is contained by the merged
`main` baseline. The machine-readable record is
`docs/release_gate_0.1.0a1.json`; artifact and public-asset hashes are in
`docs/release_gate_0.1.0a1.sha256`.

## Evidence

| Gate | Result | Evidence |
| --- | --- | --- |
| Ruff | PASS | `python3 -m ruff check .` |
| Pyright | PASS | `python3 -m pyright` |
| Pytest | PASS | 238 collected, 238 passed locally on Python 3.12.3 |
| CI matrix | PASS | Python 3.10, 3.11, 3.12, and 3.13 in [run 32614071277](https://github.com/sheepfling/Exhaust-Plume/actions/runs/32614071277) |
| Schema regeneration | PASS | Fresh output byte-for-byte matches `schemas/` |
| Fixture regeneration | PASS | Fresh output byte-for-byte matches `fixtures/contracts/` |
| sdist/wheel | PASS | `exhaust_plume-0.1.0a1` artifacts built successfully |
| Installed wheel | PASS | Fresh environment smoke script completed successfully |
| CLI smoke | PASS | All four console scripts return success for `--help` |

## Known warnings

The local test run reports 18 known warnings: 10 deprecation warnings from
legacy compatibility names and 8 runtime warnings from existing projected-area
boundary cases. The installed smoke also emits known numerical diagnostics from
legacy extreme expansion cases; it exits successfully. These are recorded in
the JSON report and are not silently treated as physical validation.

## Reproducibility correction

The deterministic fixture generator emits the default empty
`provenance.metadata` object. The four checked-in public contract fixtures were
updated to include that field. Fresh schema and fixture regeneration now has an
empty diff.

This gate makes no physics, API, provider, radiation, or downstream packet
change. It establishes release evidence and keeps the shipped public assets
aligned with their generators.
