# Coding-agent program-lead prompt

You are implementing the post-`0.1.0a1` Exhaust-Plume program.

## Baseline

- Repository: `sheepfling/Exhaust-Plume`
- Expected base: `main@49d6ffd1839258ce14319e157002005c6d2230e1`
- Expected package version: `0.1.0.a1`

Before any change, confirm the base SHA. If `main` has moved, stop and produce a resync report rather than applying stale assumptions.

## Authorities

1. `START_HERE.md`
2. `docs/PROGRAM_PLAN.md`
3. `planning/work_plan.yaml`
4. The selected issue file in `issues/`
5. `decisions/ADR-0001-canonical-api.md`, once accepted

## Execution rules

- Implement exactly one ready work packet per PR.
- Create a feature branch; never commit directly to `main`.
- Do not implement downstream packets opportunistically.
- Preserve TODOs unless the selected packet explicitly resolves them.
- Preserve 0.1.0a1 compatibility unless the packet authorizes a migration.
- New public work targets `exhaust_plume.api`.
- Never create a third product or lifecycle hierarchy.
- Keep visual, signature, and ray-transfer products independent.
- Keep solver-private zones, stations, grids, buffers, and meshes private.
- Cross physical regimes only with the canonical `PlumeFluxSection`.
- Report structured failure rather than returning plausible invalid geometry.
- Domain truncation is not physical termination.
- Tabulated signatures are not physical radiation.
- Visual geometry is not an optical medium.

## PR completion evidence

Every PR must include:

- base and head SHAs;
- implemented packet ID;
- equations or contract semantics;
- units and frame conventions;
- compatibility impact;
- success and failure tests;
- numerical/conservation evidence;
- generated-schema/fixture impact;
- Ruff, Pyright, Pytest, build, and installed-wheel results as applicable;
- remaining limitations;
- explicit confirmation that no downstream packet was implemented.

Begin with `RLS-001`.
