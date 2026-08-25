# HND-001 — Freeze the canonical PlumeFluxSection handoff

## Metadata

- **Phase:** Conservative composition
- **Target release:** `0.1.0a2`
- **Priority:** P0
- **Dependencies:** `API-008B`
- **Suggested branch:** `work/hnd-001`

## Objective

Define one neutral conservative section contract suitable for straight and curved downstream providers.

## Scope

- Unify the current API and dataclass handoff representations.
- Require area, center, unit normal, mass flow, vector momentum including pressure thrust, stagnation-enthalpy flow, species mass flows, static pressure, ambient pressure, pressure residual, cross-section moments, provenance, applicability, and uncertainty.
- Define frame and sign conventions.
- Define pressure-matched and non-pressure-matched applicability behavior.

## Deliverables

- Canonical handoff DTO and schema.
- Legacy handoff adapters.
- Conservation and validation helpers.

## Acceptance criteria

- [ ] Mass and species flows are finite and nonnegative.
- [ ] Momentum sign/frame semantics are unambiguous.
- [ ] The pressure-thrust contribution is preserved.
- [ ] Species mass flows reconcile with total mass flow within tolerance.
- [ ] Round-trip adapters lose no canonical field.

## Required tests and evidence

- [ ] Validation-property tests.
- [ ] Nozzle-exit construction closure.
- [ ] Frame rotation tests.
- [ ] Schema and fixture tests.

## Suggested repository paths

- `src/exhaust_plume/api/`
- `src/exhaust_plume/contracts/handoff.py`
- `tests/src/contracts/`

## Non-goals

- No shock-cell endpoint integration yet.
- No entrainment model.

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
