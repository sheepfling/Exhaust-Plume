# HND-002 — Implement explicit matched-source handoff construction

## Metadata

- **Phase:** Conservative composition
- **Target release:** `0.1.0a2`
- **Priority:** P0
- **Dependencies:** `HND-001`
- **Suggested branch:** `work/hnd-002`

## Objective

Provide a reliable source boundary for downstream integral providers before the validated shock-cell endpoint exists.

## Scope

- Construct a canonical `PlumeFluxSection` from an explicit pressure-matched nozzle or user-supplied section.
- Reject pressure mismatch beyond a declared tolerance.
- Preserve gas/species composition and total enthalpy.
- Expose residuals and applicability rather than silently coercing the state.

## Deliverables

- Matched-source builder.
- Reference fixtures for zero-angle and rotated sources.
- Conservation evidence.

## Acceptance criteria

- [ ] Mass, momentum, enthalpy, and species closure satisfy declared tolerances.
- [ ] Rotating the source rotates vectors without changing scalar fluxes.
- [ ] Non-matched inputs fail structurally.

## Required tests and evidence

- [ ] Analytic uniform-flow closure.
- [ ] Pressure-match boundary cases.
- [ ] Rotation invariance.

## Suggested repository paths

- `src/exhaust_plume/api/`
- `src/exhaust_plume/models/nozzle/`
- `tests/fixtures/`

## Non-goals

- No area-averaging across a shock-cell control surface.

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
