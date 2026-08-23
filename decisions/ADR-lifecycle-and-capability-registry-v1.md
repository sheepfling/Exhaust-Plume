# ADR — Canonical v1 lifecycle and capability registry

- **Status:** Accepted for `API-008B`
- **Depends on:** `ADR-canonical-api-v1.md`
- **Target release:** `0.1.0a2`

## Decision

The runtime lifecycle for new v1 providers is the typed dispatcher already
implemented in `exhaust_plume.contracts.lifecycle_v1` and re-exported through
`exhaust_plume.api.v1`:

```text
ProductProvider
    → ProductSession
        → ProductSnapshot
            → CapabilitySpec + typed request
                → typed v1 result
```

The common names remain provider, session, and snapshot at the public boundary;
the `Product*` names make it explicit that a snapshot evaluates one requested
product rather than returning a universal plume result. `ImmutableProductSnapshot`
is the canonical dispatcher and retains a mapping of capability identities to
evaluators.

The canonical capability registry is
`exhaust_plume.contracts.capability.CANONICAL_CAPABILITY_REGISTRY`, surfaced as
`exhaust_plume.api.v1.CANONICAL_CAPABILITY_REGISTRY`. It contains the three
primary products plus engineering flux, support, local field, axisymmetric-zone
field, projected-area, and spectral-image supporting identities. The primary
typed request/result mappings are in
`PRIMARY_PRODUCT_CAPABILITY_SPECS`, resolved by
`get_product_capability_spec`.

The old `exhaust_plume.api.lifecycle` UUID/string-request lifecycle and the
camelCase `exhaust_plume.providers.lifecycle` facade remain importable for
0.1.x. `api.compatibility` provides explicit request, session, snapshot, and
error adapters. A review-witness DTO must supply a deliberate result adapter;
the compatibility layer never claims that a geometry witness is a v1 wire
result by structural coincidence.

## Semantics

- `create_snapshot` fixes time, source pose, dynamic state digest, ambient
  state digest, and provider state digest in `SnapshotMetadata`.
- `evaluate` dispatches by typed capability identity and validates request and
  result classes; unsupported capability and unsupported major version are
  distinct typed failures.
- Static providers may create snapshots at arbitrary requested times only when
  their declared provider semantics permit it. Prescribed time-sliced assets
  retain their explicit time policy; the adapter does not invent interpolation.
- Product results retain SI units, named frames, applicability, provenance,
  warnings, and explicit partial-sample status/masks.
- Visual, unresolved signature, ray transfer, and engineering handoff products
  remain independent capability results.

## Compatibility mapping

| Legacy surface | Canonical v1 mapping | Behavior |
| --- | --- | --- |
| `api.ProductRequest(capability_id, schema_version)` | `CapabilityIdentity` + `CapabilitySpec` | Parse and validate major agreement; lookup goes through the canonical registry. |
| `api.PlumeSession.snapshot(SnapshotRequest)` | `ProductSession.create_snapshot(...)` | `CanonicalSessionLegacyAdapter` preserves requested time and binds explicit source/ambient state. |
| `api.PlumeSnapshot.get_product(ProductRequest)` | `ProductSnapshot.evaluate(CapabilitySpec, typed_request)` | `CanonicalSnapshotLegacyAdapter` requires a typed request binding and returns the canonical result object. |
| legacy snapshot as canonical | `LegacySnapshotCanonicalAdapter` | Requires a result adapter for review-witness DTOs; canonical v1 results pass through losslessly. |
| `PlumeApiError` | `ApiError` | Stable error class and structured context are preserved; equivalent error codes are mapped explicitly. |

No provider implementation is ported in API-008B. The adapters are the seam
used by API-009 and PRV-001..003.
