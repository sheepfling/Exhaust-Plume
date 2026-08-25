# Current state at `main@49d6ffd1839258ce14319e157002005c6d2230e1`

## Source-derived status

| Area | Status | Interpretation |
|---|---|---|
| First visual MVP | Landed | Straight analytical visual provider, prescribed provider, fixtures, and local visual workflow exist. |
| Signature MVP | Landed as lookup | Directional wavelength-resolved table provider exists; it is not spectroscopy or transfer. |
| Ray-transfer product | Contract only | No physical ray-transfer provider exists. |
| Explicit gas/nozzle state | Landed | New explicit gas, nozzle, ambient, area–Mach, and exit-state paths exist. |
| Shock validity | Landed foundation | Weak/strong branch, maximum attached turn, and pressure-target helpers exist. |
| First-cell solver | Partial | Public state-based boundary exists, but it still delegates to the legacy geometric solver. |
| Conservative handoff | Partial | `PlumeFluxSection` exists; current construction is primarily from a uniform nozzle exit. |
| Straight integral continuation | Prototype | Top-hat entrainment continuation exists, with explicit domain termination; calibration remains. |
| Curved/washed kernel | Substantially landed | Conservative centerline solver, ambient fields, rotor wake, buoyancy, entrainment, and swept geometry exist. |
| Canonical washed provider | Missing | The kernel is not yet fully exposed through the declared canonical API lifecycle. |
| Public API | Conflicted | `exhaust_plume.api` is declared canonical, while package-root real providers and schemas use the parallel contracts/products/providers hierarchy. |
| Validated MOC first cell | Missing | Characteristic mesh, free boundary, convergence, and external validation remain. |
| Finite shock train | Missing | No physical cell-count/decay/termination model. |
| Physical radiation | Missing | No gray or molecular source/transfer provider. |
| External physical validation | Missing | Current validity matrix is an applicability study, not CFD/experimental validation. |

## Critical interpretation

The project is beyond the initial MVP-construction stage. The remaining critical path is:

```text
release integrity
→ canonical API and schema authority
→ live washed provider
→ validated MOC first cell
→ conservative shock-to-mixing handoff
→ finite shock train and calibrated mixing
→ exact rays and physical radiation
```

## Repository hygiene

The release merge remains on `main`. At PR-publication resync, annotated tag `v0.1.0a1` exists, PRs #1 and #2 are closed, `feature/*` branches are gone, and `main` is protected with the Python 3.10–3.13 required checks. `RLS-001` still owns final commit-specific release-gate evidence; `RLS-002` now verifies the existing release/hygiene state and advances development only after that evidence is accepted.
