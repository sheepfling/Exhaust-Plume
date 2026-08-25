# TERM-001 — Implement coherent-plume termination and passive-scalar handoff

## Metadata

- **Phase:** Downstream straight plume
- **Target release:** `0.2.0a2`
- **Priority:** P1
- **Dependencies:** `CELL-001`, `MIX-002`
- **Suggested branch:** `work/term-001`

## Objective

Prevent the integral jet from being extended indefinitely after coherent momentum has decayed.

## Scope

- Define persistent criteria for relative velocity, temperature anomaly, species anomaly, curvature/slenderness, and domain limits.
- Distinguish coherent-jet termination from continued passive-cloud transport.
- Create a neutral passive-scalar handoff contract if residual thermal/species anomalies remain.

## Deliverables

- Termination policy and diagnostics.
- Passive-scalar handoff DTO.
- Reference scenarios.

## Acceptance criteria

- [ ] Termination reason is always explicit.
- [ ] Domain limits never masquerade as physical termination.
- [ ] The handoff conserves remaining scalar mass and energy quantities.

## Required tests and evidence

- [ ] Threshold persistence tests.
- [ ] Zero-anomaly and finite-anomaly cases.
- [ ] Domain-truncation distinction.

## Suggested repository paths

- `src/exhaust_plume/models/integral/`
- `src/exhaust_plume/api/`

## Non-goals

- No atmospheric dispersion solver implementation.

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
