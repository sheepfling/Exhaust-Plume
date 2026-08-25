# API-008A — Approve one canonical API and wire-contract authority

## Metadata

- **Phase:** API consolidation
- **Target release:** `0.1.0a2`
- **Priority:** P0
- **Dependencies:** `RLS-001`
- **Suggested branch:** `work/api-008a`

## Objective

Resolve the current dual lifecycle and dual DTO hierarchy before adding more public providers.

## Scope

- Inventory every public symbol in `exhaust_plume.api`, `exhaust_plume.contracts`, `exhaust_plume.products`, `exhaust_plume.providers`, and package-root exports.
- Compare lifecycle methods, capability identity, result envelope, errors, schemas, fixtures, and provider implementations.
- Adopt `exhaust_plume.api` as the public import namespace.
- Recommended implementation decision: retain the already shipped `contracts/*_v1` wire shapes as the v1 serialization authority, then re-export or adapt them through `exhaust_plume.api`.
- Define a deprecation window for duplicate review-witness models and compatibility facades.

## Deliverables

- `decisions/ADR-canonical-api-v1.md`.
- Symbol and wire-field crosswalk between the two current systems.
- Compatibility and deprecation matrix.

## Acceptance criteria

- [ ] Exactly one namespace is named as the public semantic authority.
- [ ] Exactly one set of models generates v1 schemas.
- [ ] Every currently shipped import has a documented retain, alias, adapt, deprecate, or remove disposition.
- [ ] The decision is reviewed against the existing visual and signature workflows.

## Required tests and evidence

- [ ] Import inventory test.
- [ ] Serialized golden-fixture comparison.
- [ ] Consumer examples exercised through the proposed public namespace.

## Suggested repository paths

- `src/exhaust_plume/api/`
- `src/exhaust_plume/contracts/`
- `src/exhaust_plume/products/`
- `src/exhaust_plume/providers/`
- `src/exhaust_plume/__init__.py`

## Non-goals

- No provider port in the same PR.
- No wire-field rename without an explicit migration rule.
- No deletion of compatibility imports.

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
