# MOC-004 — Implement the underexpanded ambient-pressure free boundary

## Metadata

- **Phase:** Validated near field
- **Target release:** `0.2.0a1`
- **Priority:** P0
- **Dependencies:** `MOC-003`
- **Suggested branch:** `work/moc-004`

## Objective

Solve the mild-underexpanded first-cell boundary without the current quadratic geometry hack.

## Scope

- Impose ambient static pressure on the free boundary.
- Advance boundary points using characteristic compatibility and tangent-flow conditions.
- Close the first-cell topology at the centerline or compression system defined by the mathematical contract.

## Deliverables

- Underexpanded MOC first-cell solver.
- Boundary residual and topology report.
- Resolution-study fixtures.

## Acceptance criteria

- [ ] Boundary pressure residual meets tolerance.
- [ ] All zones are finite, simple, and correctly oriented.
- [ ] Refinement produces convergent cell length and maximum radius.

## Required tests and evidence

- [ ] Mild pressure-ratio sweep.
- [ ] Grid refinement.
- [ ] Correlation comparison.
- [ ] Failure outside applicability.

## Suggested repository paths

- `src/exhaust_plume/models/moc/`
- `tests/fixtures/physics/`

## Non-goals

- No detached Mach disk.
- No viscous mixing.

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
