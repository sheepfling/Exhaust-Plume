# Live resync report: main / v0.1.0a1

## Repository state

Live `main` is commit `49d6ffd1839258ce14319e157002005c6d2230e1`, whose message is `Merge 0.1.0a1 release into main`. The release-prep commit `8b37e48b65321403bb3eb4ed0fdfe949dc9f1506` and live `main` resolve to the same tree SHA, `bfd587778b15da8e9b10213d7e680e48b5ae6e1e`.

Therefore the release tree and live default branch are source-identical at this resync point.

## Material already landed

The repository now contains:

- common provider/session/snapshot lifecycle and typed capability discovery;
- versioned visual, unresolved spectral signature, and resolved ray-transfer DTO contracts;
- conformance, provenance, applicability, execution, error, handoff, and schema infrastructure;
- prescribed/static providers and current-solver adapters;
- `plume.visual.sectioned-tube@1` product path;
- straight analytical and straight visual providers;
- table-backed directional spectral signature provider and signature workflow/CLI;
- ray-transfer public contract surface (still interface-only physically);
- corrected gas/nozzle contracts, exit-state derivation, shock validity, geometry/intersection primitives, shock-cell solve boundary, and validity matrix;
- straight integral model code;
- a substantial curved-plume kernel covering ambient forcing, buoyancy, entrainment, closures, exact/reference relations, geometry, state, and solver modules;
- validation-envelope infrastructure and command-line validation;
- product documentation, interface gate reports, and release-boundary documentation.

## Release boundary that remains important

The first visual release explicitly states that it is physically informed but not externally validated. The product guide similarly states that:

- signature values are supplied lookup values, not physical spectroscopy;
- resolved ray/FPA transfer remains contract-only;
- curved or rotor-washed providers are excluded from the released product surface;
- thermochemistry, particles, advanced shock topology, physical radiation, detector models, and acceleration remain outside the MVP.

These statements define the next work; they should not be silently weakened.

## Revised milestone position

| Old milestone | Resynced state |
| --- | --- |
| M0 architecture/repo baseline | DONE |
| M1 provider contracts | MATERIALLY DONE |
| M2 corrected foundation | LARGELY DONE; continue edge/fidelity work |
| M3 analytical spatial provider | DONE at low-order MVP level |
| M4 externally validated first shock cell | NOT DONE |
| M5 coherent finite shock train / physical termination | NOT DONE |
| M6 conservative provider handoff | PARTIAL / integration gate missing |
| M7 straight integral mixing | KERNEL PRESENT; provider composition + validation incomplete |
| M8 gray physical radiative transfer | NOT DONE |
| M9 ray-derived unresolved signature | NOT DONE |
| M10 direct signature table | SUBSTANTIALLY DONE |
| M11 molecular spectral radiation | NOT DONE |
| M12 curved/washed integral provider | KERNEL SUBSTANTIAL; product/provider/validation integration incomplete |
| M13 thermochemistry + particles | NOT DONE on active path |
| M14 imported CFD/field provider | NOT DONE |
| M15 GPU/transient/general 3-D | NOT DONE |

## Architectural correction to the old handoff

The coding agent should not repeat BASE-001/API-001 work simply because those issue names exist in older planning bundles. Instead, establish the pinned release SHA, run the current quality gate, and then begin the validation tranche.

The most important immediate architectural addition is a typed experiment/measurement-operator layer:

`experimental observation -> benchmark definition -> provider product/supporting field -> measurement operator -> predicted observable -> metric/uncertainty -> scoped validation claim`

Experimental CSVs remain observations. They do not become VIS/SIG/RAY response DTOs.
