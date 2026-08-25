# API-010 — Hold the formal v1 API freeze gate

## Metadata

- **Phase:** API consolidation
- **Target release:** `0.1.0a2`
- **Priority:** P0
- **Dependencies:** `PRV-004`
- **Suggested branch:** `work/api-010`

## Objective

Formally freeze the first public lifecycle and wire contracts after real providers and compatibility paths pass review.

## Scope

- Review consumer workflows, wire schemas, frame conventions, time semantics, error behavior, and partial-result rules.
- Review visual, signature, ray-transfer, and engineering-handoff boundaries independently.
- Record accepted major versions and compatibility promises.
- Block merge of new public capabilities until the gate is accepted.

## Deliverables

- `docs/api_v1_freeze_report.md`.
- `docs/api_v1_freeze_report.json`.
- Frozen capability/schema manifest.

## Acceptance criteria

- [ ] One lifecycle and schema authority is documented and tested.
- [ ] All canonical providers pass conformance.
- [ ] Compatibility impact is reviewed.
- [ ] Open decisions are either resolved or explicitly deferred without affecting v1 meaning.

## Required tests and evidence

- [ ] Schema diff review.
- [ ] Consumer smoke tests.
- [ ] Provider conformance summary.
- [ ] Installed-wheel import inventory.

## Suggested repository paths

- `docs/`
- `schemas/`
- `fixtures/`
- `tests/conformance/`

## Non-goals

- No new physics.
- No opportunistic v2 fields.

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
