# API-008C — Establish canonical schema and fixture generation

## Metadata

- **Phase:** API consolidation
- **Target release:** `0.1.0a2`
- **Priority:** P0
- **Dependencies:** `API-008B`
- **Suggested branch:** `work/api-008c`

## Objective

Make one deterministic generator authoritative for v1 schemas and golden fixtures.

## Scope

- Generate all public schemas from the canonical DTOs.
- Migrate valid and invalid fixtures to the canonical generator.
- Preserve shipped wire compatibility unless the ADR explicitly allows a versioned break.
- Record schema IDs, capability IDs, and major versions in one manifest.
- Add a CI check that fails on generated-asset drift.

## Deliverables

- Canonical schema generator.
- Canonical fixture generator.
- Generated-asset manifest with digests.
- CI drift check.

## Acceptance criteria

- [ ] A clean generation run produces no Git diff.
- [ ] Every valid fixture validates against its schema.
- [ ] Every intentionally invalid fixture is rejected for the expected reason.
- [ ] No schema file is generated from the deprecated model hierarchy.

## Required tests and evidence

- [ ] Draft 2020-12 schema validation.
- [ ] Determinism test across two clean generation runs.
- [ ] Backward-compatibility comparison against 0.1.0a1 assets.

## Suggested repository paths

- `scripts/`
- `schemas/`
- `fixtures/contracts/`
- `tests/src/contracts/`

## Non-goals

- No provider implementation changes.
- No physical validation claims.

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
