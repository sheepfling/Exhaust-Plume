# COMP-001 — Compose near field, shock train, and straight mixing provider

## Metadata

- **Phase:** Downstream straight plume
- **Target release:** `0.2.0a2`
- **Priority:** P1
- **Dependencies:** `CELL-001`, `MIX-002`, `TERM-001`, `API-010`
- **Suggested branch:** `work/comp-001`

## Objective

Provide one straight-plume session that composes validated regimes through neutral handoffs.

## Scope

- Compose MOC first cell, finite shock train, conservative handoff, and integral mixing.
- Expose visual, engineering, support, and diagnostic products.
- Preserve provenance and uncertainty through every regime transition.

## Deliverables

- Composite straight provider.
- End-to-end conservation ledger.
- Consumer fixtures.

## Acceptance criteria

- [ ] No provider-private types cross regime boundaries.
- [ ] Flux closure is reported at every handoff.
- [ ] Provider swapping remains transparent to visual consumers.
- [ ] Termination is physical or explicitly imposed.

## Required tests and evidence

- [ ] Matched, underexpanded, and overexpanded end-to-end cases.
- [ ] Handoff conservation.
- [ ] Provider conformance.

## Suggested repository paths

- `src/exhaust_plume/providers/`
- `src/exhaust_plume/api/`

## Non-goals

- No optical transfer.

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
