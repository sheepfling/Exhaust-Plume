# API-009 canonical provider conformance

The reusable pytest harness is in `tests/conformance/`. Provider-specific
construction is limited to `ProviderFixture` registrations; lifecycle and
product assertions are shared by every registered provider.

The common checks cover:

- descriptor capability identity and snapshot support agreement;
- session metadata, requested snapshot time, closure, and immutable metadata;
- deterministic serialization from repeated and fresh sessions;
- canonical product/result type, capability, frame, provenance, and shape;
- unsupported capability and unsupported-major-version errors;
- signature partial-batch validity masks and ray hit/miss semantics; and
- neutral `PlumeFluxSection` handoff fields without solver-specific physics assertions.

## Registration status

| Provider symbol | Status |
| --- | --- |
| `PrescribedVisualProvider` | registered visual product fixture |
| `StraightVisualProvider` | registered visual product fixture |
| `StraightAnalyticalProvider` / `StraightAnalyticalPlumeProviderV0` | registered visual product fixture |
| `SignatureTableProvider` | registered signature product fixture |
| `ShockCellVisualProvider` | registered visual product fixture |
| `StaticPlumeProvider` | compatibility-only fixture; not a production provider |
| `ShockCellAnalyticalProvider` | compatibility-only spatial-zone provider; use `ShockCellVisualProvider` |

The failure fixture intentionally advertises a visual capability while
returning a snapshot without that evaluator. The harness rejects it at the
descriptor/snapshot boundary, preserving the distinction between a provider
claim and an actually executable product.

No network transport, GPU/CPU acceleration, FPA raycasting, or provider-
specific physics assertion is part of this gate.
