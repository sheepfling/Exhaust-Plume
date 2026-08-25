# MOC-002 — Implement inverse Prandtl–Meyer and characteristic primitives

## Metadata

- **Phase:** Validated near field
- **Target release:** `0.2.0a1`
- **Priority:** P0
- **Dependencies:** `MOC-001`
- **Suggested branch:** `work/moc-002`

## Objective

Build robust numerical primitives for the MOC grid.

## Scope

- Implement forward and inverse Prandtl–Meyer functions with physical bracketing.
- Implement Mach angle, characteristic invariants, interior-point compatibility, and residual reporting.
- Handle near-sonic and high-Mach conditioning explicitly.

## Deliverables

- Typed numerical primitives.
- Iteration diagnostics.
- Analytical reference tests.

## Acceptance criteria

- [ ] Forward/inverse round trips meet tolerance across the declared range.
- [ ] Nonphysical inputs fail structurally.
- [ ] Interior compatibility residuals close.

## Required tests and evidence

- [ ] Dense Mach/gamma sweep.
- [ ] Near-endpoint conditioning cases.
- [ ] Independent equation fixtures.

## Suggested repository paths

- `src/exhaust_plume/models/moc/`
- `tests/src/models/moc/`

## Non-goals

- No plume boundary construction.

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
