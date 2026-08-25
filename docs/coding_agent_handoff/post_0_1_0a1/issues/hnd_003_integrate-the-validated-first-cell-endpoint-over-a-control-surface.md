# HND-003 — Integrate the validated first-cell endpoint over a control surface

## Metadata

- **Phase:** Conservative composition
- **Target release:** `0.2.0a1`
- **Priority:** P0
- **Dependencies:** `MOC-007`, `HND-001`
- **Suggested branch:** `work/hnd-003`

## Objective

Create a physically auditable `PlumeFluxSection` at the near-field/downstream boundary.

## Scope

- Define a control surface at a pressure-matched or declared handoff station.
- Integrate mass, vector momentum including pressure thrust, stagnation enthalpy, and species over all intersected MOC regions.
- Carry geometric moments, residuals, uncertainty, and provenance.
- Reject incomplete or non-closing control surfaces.

## Deliverables

- MOC-to-handoff control-surface integrator.
- Closure report for every handoff.
- Reference fixtures.

## Acceptance criteria

- [ ] Integrated fluxes close against upstream invariants within declared tolerance.
- [ ] Pressure mismatch and incomplete coverage are explicit.
- [ ] The result is consumable by straight and washed integral providers without solver-private types.

## Required tests and evidence

- [ ] Uniform-state exact integration.
- [ ] Piecewise-zone manufactured cases.
- [ ] Rotation and refinement invariance.
- [ ] Incomplete-surface failure.

## Suggested repository paths

- `src/exhaust_plume/models/moc/`
- `src/exhaust_plume/api/`
- `tests/src/contracts/`

## Non-goals

- No downstream entrainment.

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
