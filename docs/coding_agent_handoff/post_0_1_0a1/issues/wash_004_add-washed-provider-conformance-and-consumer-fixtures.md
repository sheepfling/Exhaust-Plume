# WASH-004 — Add washed-provider conformance and consumer fixtures

## Metadata

- **Phase:** Washed plume productization
- **Target release:** `0.1.0a2`
- **Priority:** P0
- **Dependencies:** `WASH-003`
- **Suggested branch:** `work/wash-004`

## Objective

Prove that prescribed, straight analytical, and washed providers are interchangeable at the consumer-facing visual boundary.

## Scope

- Register the washed provider in canonical conformance.
- Create quiescent, uniform-crossflow, rotor-downwash, and torque-reversal fixtures.
- Run the existing visual mesh/OBJ workflow against a live washed snapshot.
- Compare prescribed and live fixtures through identical consumer code.

## Deliverables

- Provider fixtures and expected outputs.
- End-to-end consumer smoke program.
- Conformance report.

## Acceptance criteria

- [ ] No consumer branches on provider class.
- [ ] All fixtures serialize deterministically.
- [ ] Torque reversal mirrors lateral displacement as expected.
- [ ] Provider limitations and coefficient provenance are present in every result.

## Required tests and evidence

- [ ] Full canonical conformance.
- [ ] CLI or script end-to-end smoke.
- [ ] Fixture determinism.
- [ ] Zero-crossflow equivalence.

## Suggested repository paths

- `fixtures/providers/`
- `fixtures/products/`
- `tests/conformance/`
- `scripts/`

## Non-goals

- No external calibration claim.
- No network sidecar.

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
