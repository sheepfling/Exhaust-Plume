# Coding-Agent Directive

## Baseline

Start every branch from `main@49d6ffd1839258ce14319e157002005c6d2230e1` or a later reviewed main commit. Do not branch from `feature/initial-work`, `feature/curved-plume-kernel`, or `feature/mvp-product-contracts`.

## Work selection

1. Read `planning/work_plan.yaml`.
2. Select exactly one `ready` packet whose dependencies are complete.
3. Read the matching file in `work_packets/`.
4. Implement only that packet.
5. Report changed files, tests, evidence, compatibility impact, and remaining limitations.

## Required implementation style

- Python 3.10-compatible syntax in the package unless the project raises its floor.
- Fully type-annotated public and computational interfaces.
- Preserve existing TODOs.
- Keep DTO validation at boundaries and numerical arrays in computational modules.
- End each scope with the project’s `####` convention where used.
- Do not add dependencies without packet-level justification.

## Prohibitions

Do not:

- create a third API/product hierarchy;
- create a universal nullable plume result;
- expose `ZoneResult`, `CurvedPlumeStation`, mesh classes, or solver arrays as transport DTOs;
- infer radiance/signature from geometry;
- advertise ray/signature support before gates pass;
- delete a1 imports without tested compatibility;
- tune multiple physical mechanisms against one observable in the provider PR;
- bundle API consolidation, kernel modification, sidecar, and optical physics into one PR.

## Completion evidence

Every PR includes:

- exact base and head commits;
- equations or contract semantics changed;
- unit/frame/time behavior;
- positive and structured-failure tests;
- Ruff, Pyright, pytest, build, installed-wheel evidence;
- compatibility statement;
- applicability and validation-level statement;
- remaining limitations.
