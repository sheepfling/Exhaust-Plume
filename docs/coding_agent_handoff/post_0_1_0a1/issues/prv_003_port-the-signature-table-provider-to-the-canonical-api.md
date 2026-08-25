# PRV-003 — Port the signature-table provider to the canonical API

## Metadata

- **Phase:** Canonical providers
- **Target release:** `0.1.0a2`
- **Priority:** P0
- **Dependencies:** `API-009`
- **Suggested branch:** `work/prv-003`

## Objective

Retain the useful tabulated signature product while making its non-physical lookup nature explicit in the canonical API.

## Scope

- Port wavelength, direction-cosine, optional time, operating-point, interpolation, and extrapolation policies.
- Preserve source-only radiant-intensity semantics.
- Preserve asset digests, domains, provenance, and tabulated radiation claim.
- Reject unsupported nodes and out-of-domain requests consistently.

## Deliverables

- Canonical signature-table provider.
- Compatibility adapter for current workflow and CLI.
- Conformance registration and fixture migration.

## Acceptance criteria

- [ ] All existing interpolation modes retain expected behavior.
- [ ] Exact-only remains exact-only even when extrapolation is requested.
- [ ] The provider never claims physical spectroscopy, atmosphere, optics, or detector effects.

## Required tests and evidence

- [ ] Wavelength, angle, time, and operating-point matrix.
- [ ] Extrapolation rejection and marginal-result tests.
- [ ] Asset hash and deterministic output tests.

## Suggested repository paths

- `src/exhaust_plume/providers/signature_table.py`
- `src/exhaust_plume/products/workflow_signature.py`
- `fixtures/products/`

## Non-goals

- No physical radiation model.
- No ray-transfer capability.

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
