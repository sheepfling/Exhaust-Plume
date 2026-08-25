# WASH-001 — Define canonical washed-plume provider inputs and session semantics

## Metadata

- **Phase:** Washed plume productization
- **Target release:** `0.1.0a2`
- **Priority:** P0
- **Dependencies:** `API-009`, `HND-001`
- **Suggested branch:** `work/wash-001`

## Objective

Turn the merged curved-plume kernel into a provider-ready, reproducible definition and configuration boundary.

## Scope

- Define source handoff, ambient thermodynamic field, composable velocity fields, entrainment closure, source terms, termination policy, numerical options, and output sampling.
- Separate immutable definition from per-snapshot operating state.
- Declare the first provider steady and local.
- Keep rotor specifics in ambient velocity-field implementations rather than in the plume kernel.

## Deliverables

- Canonical washed-provider definition/configuration DTOs.
- Session/snapshot lifecycle design.
- Input validation and applicability rules.

## Acceptance criteria

- [ ] Every solver input is represented once with units and frame semantics.
- [ ] A prescribed ambient, uniform crossflow, and actuator-disk case can be represented.
- [ ] Unsupported transient or non-pressure-matched states fail before integration.

## Required tests and evidence

- [ ] DTO validation.
- [ ] Serialization determinism.
- [ ] Invalid field-composition and pressure-match tests.

## Suggested repository paths

- `src/exhaust_plume/api/`
- `src/exhaust_plume/models/plume/curved_plume*.py`

## Non-goals

- No provider execution yet.
- No coefficient calibration.

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
