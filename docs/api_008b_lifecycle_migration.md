# API-008B lifecycle migration record

## Canonical authority

New provider code imports the canonical lifecycle and product specs from
`exhaust_plume.api.v1`. The object identities are aliases to the existing
`contracts` implementation, so the wire result classes, schema registry, and
fixture models do not fork. This migration record is now the decision record,
not an open choice between lifecycle variants.

| Concern | Canonical v1 | Retained compatibility surface |
| --- | --- | --- |
| Capability identity | `CapabilityIdentity(name, major)` and `CANONICAL_CAPABILITY_REGISTRY` | API string IDs and product-local `CapabilityId` wrappers |
| Product negotiation | `CapabilitySpec[RequestT, ResultT]` | `ProductRequest(capability_id, schema_version)` |
| Provider | `ProductProvider.create_session(...)` | `api.PlumeProvider`, `providers.compatibility.PlumeProvider` |
| Session | `ProductSession.create_snapshot(...)` | `api.PlumeSession.snapshot(...)`, `createSession(...)` |
| Snapshot | `ProductSnapshot.evaluate(...)` | `api.PlumeSnapshot.get_product(...)`, `resolveCapability(...)` |
| Result | exact `contracts/*_v1` class | review-witness DTO or product wrapper only after an explicit adapter |
| Failure | typed `contracts.errors` / `ApiError` | `PlumeApiError`, provider-specific exceptions mapped by `api.compatibility` |

## Negotiation and failure behavior

`get_product_capability_spec` distinguishes an unknown product from a known
product requested at an unsupported major. Legacy requests are accepted only
when the major in `capability_id` agrees with the schema-version major. Error
adapters preserve provider and snapshot identifiers when they are UUID-shaped;
the original session identifier is retained in canonical error details.

The common dispatcher checks:

- capability is advertised;
- major version matches;
- request is an instance of the declared request model;
- result is an instance of the declared result model.

This prevents a provider from returning a plausible object under the wrong
product identity. A valid ray miss and a failed ray remain distinct through the
existing v1 result status and mask rules.

## Static, prescribed, and analytical behavior

The existing prescribed visual provider, straight visual provider, straight
analytical provider, and table-backed signature provider are exercised through
the canonical `ProductSession.create_snapshot` and
`ProductSnapshot.evaluate` methods. Static geometry may be evaluated at
requested snapshot times while retaining the same deterministic product
content hash. The table-backed signature provider continues to enforce its
declared steady or prescribed-transient time model through its existing
applicability checks. The bounded `ShockCellVisualProvider` follows the same
visual lifecycle and advertises only the visual product; its old spatial-zone
provider remains a compatibility implementation. This migration does not add
time interpolation or a physical radiation claim.

## Deliberate limit

The old review-witness visual/spectral DTOs do not have identical wire fields
to the shipped v1 models. The compatibility adapters therefore require an
explicit result adapter; they do not perform a lossy, implicit field
conversion. Provider-specific lossless mappings and generated
schema/fixture-drift checks remain bounded follow-on work.
