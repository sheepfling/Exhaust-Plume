# API-009 — Build the reusable canonical provider conformance harness

## Metadata

- **Phase:** API consolidation
- **Target release:** `0.1.0a2`
- **Priority:** P0
- **Dependencies:** `API-008C`
- **Suggested branch:** `work/api-009`

## Objective

Create one harness that tests lifecycle and product semantics for every provider.

## Scope

- Check descriptor/capability/result agreement.
- Check session closure, snapshot immutability, time policy, frame identity, and deterministic serialization.
- Check structured unsupported-capability and unsupported-version failures.
- Add product-specific checks for visual, signature, ray-transfer, and engineering handoff results.
- Permit provider-specific applicability limits without weakening common semantics.

## Deliverables

- Reusable pytest conformance library.
- Fake providers for visual-only, signature-only, and failure cases.
- Provider registration table used by CI.

## Acceptance criteria

- [ ] A new provider can opt into the harness with a small fixture and no harness edits.
- [ ] Every currently supported provider is either registered or explicitly waived with a reason.
- [ ] Partial-batch and valid-miss semantics are tested where applicable.

## Required tests and evidence

- [ ] Provider lifecycle matrix.
- [ ] Determinism and immutable-snapshot tests.
- [ ] Capability/version negotiation tests.
- [ ] Structured failure tests.

## Suggested repository paths

- `tests/conformance/`
- `src/exhaust_plume/api/`

## Non-goals

- No provider-specific physics assertion in the common harness.
- No network transport.

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
