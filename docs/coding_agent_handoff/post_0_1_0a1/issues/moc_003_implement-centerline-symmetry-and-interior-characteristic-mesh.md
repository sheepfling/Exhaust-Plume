# MOC-003 — Implement centerline symmetry and interior characteristic mesh

## Metadata

- **Phase:** Validated near field
- **Target release:** `0.2.0a1`
- **Priority:** P0
- **Dependencies:** `MOC-002`
- **Suggested branch:** `work/moc-003`

## Objective

Construct the validated interior characteristic field and centerline boundary.

## Scope

- Implement C+ and C- intersections with forward-parameter checks.
- Implement centerline zero-turn symmetry.
- Track topology, conditioning, residuals, and monotonically advancing axial coordinates.

## Deliverables

- Characteristic mesh types and solver.
- Centerline boundary implementation.
- Topology diagnostics.

## Acceptance criteria

- [ ] All accepted intersections are forward and finite.
- [ ] Centerline radial velocity/turning condition is satisfied.
- [ ] Mesh connectivity is deterministic and non-self-intersecting.

## Required tests and evidence

- [ ] Manufactured characteristic nets.
- [ ] Symmetry cases.
- [ ] Near-parallel characteristic failure cases.

## Suggested repository paths

- `src/exhaust_plume/models/moc/`
- `src/exhaust_plume/geometry/`

## Non-goals

- No free boundary.
- No overexpanded shock boundary.

## Completion report

The PR description must include:

- Exact base SHA and head SHA.
- Contract or equation changes.
- Units, frames, and lifecycle semantics.
- Compatibility impact.
- Success and structured-failure evidence.
- Ruff, Pyright, Pytest, build, and installed-wheel results.
- Remaining limitations.
- Confirmation that no downstream packet was implemented opportunistically.
