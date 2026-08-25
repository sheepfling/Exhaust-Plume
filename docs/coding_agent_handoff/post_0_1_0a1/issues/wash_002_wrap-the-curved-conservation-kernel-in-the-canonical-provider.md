# WASH-002 — Wrap the curved conservation kernel in the canonical provider

## Metadata

- **Phase:** Washed plume productization
- **Target release:** `0.1.0a2`
- **Priority:** P0
- **Dependencies:** `WASH-001`, `HND-002`
- **Suggested branch:** `work/wash-002`

## Objective

Implement `WashedIntegralPlumeProvider` around the existing conservative arc-length solver.

## Scope

- Create provider, session, immutable snapshot, and solver-result ownership semantics.
- Use canonical `PlumeFluxSection` as the source boundary.
- Preserve mass, vector momentum, total-energy/enthalpy, and source-origin tracer invariants.
- Propagate termination, curvature, slenderness, solver status, and warnings.

## Deliverables

- Canonical washed provider/session/snapshot.
- Internal adapter from handoff to `CurvedPlumeSource`.
- Provider-level diagnostics.

## Acceptance criteria

- [ ] Zero crossflow reproduces the straight integral limit within tolerance.
- [ ] Uniform crossflow matches the existing analytical regression.
- [ ] Rotation of source and ambient rotates the solution.
- [ ] Solver failures become structured provider failures.

## Required tests and evidence

- [ ] Free-jet exact solution.
- [ ] Orthogonal-crossflow exact solution.
- [ ] Source-term composition and buoyancy regressions.
- [ ] Lifecycle and closure tests.

## Suggested repository paths

- `src/exhaust_plume/providers/`
- `src/exhaust_plume/models/plume/`
- `tests/src/providers/`

## Non-goals

- No claim that empirical coefficients are calibrated.
- No optical capability.

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
