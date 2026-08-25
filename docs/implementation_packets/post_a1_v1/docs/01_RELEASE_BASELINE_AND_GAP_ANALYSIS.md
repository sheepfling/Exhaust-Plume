# Release Baseline and Gap Analysis

## Canonical release identity

| Item | Value |
|---|---|
| Repository | `sheepfling/Exhaust-Plume` |
| Canonical branch | `main` |
| Main commit | `49d6ffd1839258ce14319e157002005c6d2230e1` |
| Release tag | `v0.1.0a1` |
| Tag commit | `8b37e48b65321403bb3eb4ed0fdfe949dc9f1506` |
| Python version constant | `0.1.0.a1` |
| Normalized distribution version | `0.1.0a1` |
| Main versus tag | one merge commit ahead; no file-level differences |

## Evidence limitation

No workflow run was returned for main@49d6ffd by the connected GitHub query; rerun and record exact-main CI.

Earlier PR matrices were green, but release acceptance requires exact-main evidence rather than inference from superseded branch heads.

## Milestone reconciliation

| Milestone | Scope | Release status | Evidence/gap |
|---|---|---|---|
| M0 | Architecture and repository baseline | `partial` | Baseline and architecture docs exist but still describe the older a0/86195b state. |
| M1 | Provider contract foundation | `partial` | Provider/session/snapshot contracts exist, but two overlapping public contract hierarchies remain. |
| M2 | Corrected physics foundation and exit-state boundary | `substantially_complete` | Explicit gas/nozzle models, shock feasibility, geometry validity, and compatibility paths are present. |
| M3 | ShockCellAnalyticalProvider | `implemented` | Provider, support, zone-field, projected-area, and conservative exit handoff exist. |
| M4 | Validated first shock cell | `partial` | First-cell interfaces and analytical regressions exist; independent external validation and full MOC evidence remain. |
| M5 | Finite coherent shock train | `not_started` | Construction count remains a safety/request control; no calibrated physical shock-train termination. |
| M6 | Conservative provider handoff | `partial` | PlumeFluxSection exists, but duplicate representations and true downstream shock-to-mixing handoff remain. |
| M7 | Straight integral mixing provider | `kernel_only` | Straight continuation kernel exists; canonical provider and product adapters do not. |
| M8 | Gray radiative transfer | `contract_only` | Ray-transfer DTOs exist; physical ray intervals and transfer solver do not. |
| M9 | Far-field signature and consumer integration | `partial` | Table-backed signature and workflow exist; ray-derived signature consistency does not. |
| M10 | Direct SignatureTableProvider | `implemented` | Lookup-backed provider, interpolation policies, provenance, and CLI workflow exist. |
| M11 | Molecular spectral radiation | `not_started` | No spectroscopy/opacity or molecular transfer provider is claimed. |
| M12 | Curved or washed integral provider | `kernel_only` | Curved solver, ambient fields, rotor wake, entrainment, buoyancy, and geometry exist; canonical provider is missing. |
| M13 | Thermochemistry and particles | `not_started` | Active plume path remains calorically perfect/frozen. |
| M14 | Imported-field provider | `not_started` | No standard imported RANS/LES/CFD provider. |
| M15 | GPU transient or general-3D provider | `not_started` | No accelerated/transient implementation. |

## Retired opening-wave assumptions

The older handoffs instructed the agent to build M0/M1 and begin corrected physics from the minimal `feature/initial-work` baseline. That sequence is now obsolete because those changes have been incorporated into `main`.

Retire these instructions:

- do not branch from `feature/initial-work`;
- do not merge the old curved/product branches as new work;
- do not reimplement provider/session/snapshot contracts from scratch;
- do not create another result hierarchy;
- do not treat the curved kernel as unmerged work.

## Current high-value gaps

1. Baseline docs and CI evidence are stale.
2. Public contract authority is duplicated.
3. Two entrainment implementations share the same public name.
4. Straight and washed kernels are not canonical providers.
5. The shock handoff is still effectively an exit-section handoff.
6. Sidecar transport is absent.
7. Ray transfer remains a contract without physics.
8. Calibration and external validation remain future work.
