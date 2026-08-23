# API-008A compatibility and deprecation matrix

The matrix keeps the `0.1.0a1` consumers working while giving new code one
public import authority. “Retain” means the import remains supported in 0.1.x;
“adapt” means the object may be converted at a provider/product boundary;
“deprecate” means no new use and a warning/removal plan is recorded, not that
the symbol is deleted in this packet.

| Import surface | Examples | 0.1.x disposition | New code | Follow-up |
| --- | --- | --- | --- | --- |
| `exhaust_plume.api.v1` | `VisualSectionedTubeRequest`, `SpectralSignatureResult`, `ProviderDescriptor`, `PUBLIC_CONTRACT_MODELS` | retain as canonical facade | use | API-010 freezes the v1 surface |
| `exhaust_plume.contracts` common/v1 modules | `Pose`, `ResultMetadata`, `VisualSectionedTubeResult`, `SpectralSignatureResult`, `SpectralRayTransferRequest` | retain as wire authority and compatibility import | prefer `api.v1` aliases | deprecation guidance after v1 freeze; no field drift |
| `exhaust_plume.api.contracts` | `Pose3`, `ResultEnvelope`, `SectionedTubePayload`, spectral payloads | retain compatibility DTOs | do not extend | adapt/deprecate during API-008B/008C and API-010 |
| `exhaust_plume.api.lifecycle` | `PlumeProvider`, `PlumeSession`, `PlumeSnapshot`, `ProductRequest` | retain review-witness lifecycle | do not add a parallel lifecycle | API-008B selects the ABI; API-009 adds conformance |
| `exhaust_plume.api.prescribed` | `PrescribedSectionedTubeProvider` | retain the old envelope as a compatibility shell | delegates lifecycle/evaluation to `providers.PrescribedVisualProvider` | remove no earlier than 0.2.0 |
| `exhaust_plume.products._base` | `ContractModel`, product metadata, product DTOs | retain implementation compatibility | no new wire DTOs | PRV-001..003 adapt outputs |
| `exhaust_plume.products` workflows | mesh, plotting, CSV/JSON helpers | retain | use as consumer adapters | keep visual/signature/ray products independent |
| `exhaust_plume.providers.lifecycle` | `ProviderDescriptor`, `createSession`, `resolveCapability` | retain existing provider ABI | no new providers before API-009 | conformance/migration in API-009/PRV packets |
| `exhaust_plume.providers.*` | prescribed, straight, signature-table, shock-cell providers | retain and test | use through current compatibility path until ported | PRV-001..003 |
| `exhaust_plume` root | physics helpers and convenience contract/provider imports | retain; no deletion | new product examples move to `api.v1` | API-010 curates without breaking 0.1.x |

## Removal rules

No compatibility import is removed by API-008A. A future deprecation must name
the replacement import, preserve the old wire fields for the announced window,
and add an import test plus a migration note. A field rename or capability
meaning change requires a new major capability identity and schema fixture; a
Python alias alone is not a wire migration.
