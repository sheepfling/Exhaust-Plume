# API-008B — Unify capability identities, lifecycle, and result envelopes

## Metadata

- **Phase:** API consolidation
- **Target release:** `0.1.0a2`
- **Priority:** P0
- **Dependencies:** `API-008A`
- **Suggested branch:** `work/api-008b`

## Objective

Implement the approved API decision so there is one runtime lifecycle and one meaning for each capability and result envelope.

## Scope

- Provide a canonical capability registry for visual, signature, ray transfer, support, and engineering handoff products.
- Unify provider/session/snapshot names and method semantics.
- Unify unsupported-capability, unsupported-version, invalid-request, closed-session, and sample-failure behavior.
- Ensure one class identity or lossless adapter exists for every retained public DTO.
- Prohibit new features from depending on the losing hierarchy directly.

## Deliverables

- Canonical lifecycle protocols and capability registry.
- Compatibility adapters for the losing lifecycle.
- Migration tests proving existing assets and workflows still function.

## Acceptance criteria

- [ ] No duplicate capability registry remains authoritative.
- [ ] One canonical snapshot can evaluate all currently supported product types.
- [ ] Existing callers receive equivalent serialized results or a documented deprecation warning.
- [ ] Adapter round trips are lossless for all v1 fields.

## Required tests and evidence

- [ ] Protocol/runtime conformance tests.
- [ ] Old-to-new and new-to-old adapter round trips.
- [ ] Typed error equivalence tests.
- [ ] Static-time and prescribed-transient lifecycle tests.

## Suggested repository paths

- `src/exhaust_plume/api/`
- `src/exhaust_plume/contracts/`
- `tests/src/api/`
- `tests/src/contracts/`

## Non-goals

- No new physics.
- No new product capability.
- No schema freeze until `API-008C`.

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
