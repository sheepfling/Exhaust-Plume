# API Consolidation and Compatibility Plan

## Problem

The release contains two overlapping models of the same public concepts. Leaving both authoritative would make provider selection, transport schemas, and consumer interoperability ambiguous.

## Decision

`exhaust_plume.api` is canonical for v1 serialized products and lifecycle semantics.

## Migration stages

### Stage 1 — classify and test

Create a matrix for every class in `api`, `contracts`, `products`, and `providers`:

```text
canonical DTO
canonical lifecycle
provider implementation
computational state
compatibility facade
workflow helper
retire after alpha window
```

No behavior changes occur in this commit.

### Stage 2 — adapters

Add explicit adapters for:

- legacy visual products to canonical `SectionedTubeResult`;
- signature table results to canonical `SpectralRadiantIntensityResult`;
- legacy ray DTOs to canonical `SpectralRayTransferResult` when semantics match;
- computational flux state to canonical `PlumeFluxSection`;
- canonical requests into retained provider implementations.

Adapters must reject semantic mismatch instead of filling fields with guesses.

### Stage 3 — root exports

- Export canonical capability identities and DTOs from the package root.
- Retain a1 imports under their original modules.
- Add documented deprecation notices only where a tested replacement exists.
- Avoid ambiguous same-name root exports; use explicit compatibility aliases where necessary.

### Stage 4 — schemas and conformance

- Generate JSON schemas from canonical models only.
- Add a reusable conformance harness for visual-only, signature-only, ray-only, and multi-capability providers.
- Require all new providers to pass it.

## Compatibility promise for the alpha line

- Existing `v0.1.0a1` imports remain importable through at least `v0.1.0a2`.
- No field is silently reinterpreted.
- Deprecated aliases emit at most one warning per process and remain test-covered.
- Serialized v1 capability IDs and units do not change during consolidation.
