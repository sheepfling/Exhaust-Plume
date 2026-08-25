# ADR-0001 — Canonical public API and v1 wire authority

- **Status:** Proposed for `API-008A`
- **Context baseline:** `main@49d6ffd1839258ce14319e157002005c6d2230e1`

## Context

The repository currently contains:

- `exhaust_plume.api`, described as the canonical contract/lifecycle authority;
- `exhaust_plume.contracts`, which contains the typed v1 lifecycle and schema models used by current providers and schema generation;
- `exhaust_plume.products` and `exhaust_plume.providers`, which contain working consumer workflows and providers;
- package-root exports that expose the contracts/providers path rather than the canonical API review-witness lifecycle.

The two lifecycle systems use different method names, capability representations, result types, and construction signatures. Leaving both authoritative will force every future provider to choose or implement both.

## Decision

1. The supported public import namespace for all new provider/product work is `exhaust_plume.api`.
2. The v1 wire shapes already shipped through `contracts/*_v1`, schemas, fixtures, and working providers are the recommended serialization baseline.
3. `exhaust_plume.api` will expose those canonical v1 semantics through re-exports or lossless adapters.
4. Duplicate review-witness DTOs and lifecycle types under `api` that conflict with the shipped v1 shapes will be deprecated after compatibility mapping.
5. `exhaust_plume.contracts`, `products`, and `providers` may remain implementation and compatibility modules during 0.1.x, but they do not define new public semantics.
6. One generator produces all public schemas and fixtures.
7. One conformance harness applies to all providers.
8. A future incompatible change requires a new capability major version, not silent field drift.

## Consequences

Positive:

- Existing 0.1.0a1 assets receive the smallest possible migration.
- Documentation and consumer imports gain one stable namespace.
- Future providers implement one lifecycle.
- Schema and capability drift become testable.

Costs:

- Temporary aliases and adapters are required.
- Some current class names may survive only as deprecated aliases.
- The package root must be curated rather than exporting every implementation class.

## Rejected alternatives

### Keep both systems

Rejected because every provider, schema, error, and consumer would need duplicate semantics.

### Make the current `api` review-witness wire shapes authoritative immediately

Rejected as the default because working providers, generated schemas, and fixtures currently use the other v1 models; switching without a compatibility study risks avoidable wire breakage.

### Make `contracts` the permanent public namespace

Rejected because the repository's own architecture documentation names `exhaust_plume.api` as the public boundary, and an API facade provides a cleaner long-term surface.

## Confirmation required

`API-008A` must validate this decision against actual downstream imports and serialized assets. If evidence shows that the review-witness shapes are already the external dependency, the ADR must be amended before implementation.
