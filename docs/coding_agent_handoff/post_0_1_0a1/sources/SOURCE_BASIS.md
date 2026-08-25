# Source basis

This packet is grounded in the repository state inspected on 2026-08-22 (America/Chicago).

## Repository anchor

- `main` commit: `49d6ffd1839258ce14319e157002005c6d2230e1` — “Merge 0.1.0a1 release into main”
- Package constant: `0.1.0.a1`

## Source-derived findings

1. `docs/first_mvp_release.md` states that the first production-shaped visual slice is implemented and explicitly excludes complete mixing, physical radiation, ray transfer, detached shocks, chemistry, particles, and external validation.
2. `docs/interface_v1_gate_report.json` records a passing interface gate with 164 tests and identifies physical radiation, resolved ray transfer, CPU/GPU acceleration, canonical curved providers, advanced thermochemistry, and external validation as excluded.
3. `docs/mvp_product_alignment.md` names `exhaust_plume.api` as the canonical public boundary while describing products/providers as compatibility surfaces and saying the formal freeze remains outstanding.
4. `src/exhaust_plume/__init__.py` exports the working contracts/providers hierarchy and many solver implementation classes at package root.
5. `src/exhaust_plume/api/lifecycle.py` and `src/exhaust_plume/contracts/lifecycle_v1.py` define materially different provider/session/snapshot protocols.
6. `src/exhaust_plume/models/shock_cells/solve.py` exposes the desired state-based first-cell boundary but delegates non-matched cases to the legacy geometric solver.
7. `src/exhaust_plume/contracts/handoff.py` defines a useful conservative section and currently constructs it from a uniform nozzle exit.
8. `src/exhaust_plume/models/integral/straight.py` implements a top-hat continuation with explicit spatial-domain termination, but it is not yet the calibrated composite plume.
9. Curved-plume documents and source describe a conservative 3-D kernel, ambient velocity composition, actuator-disk wake, buoyancy, developing/crossflow entrainment, and rotation-minimizing swept geometry.
10. At PR-publication resync, PRs #1 and #2 are closed, `feature/*` branches are gone, `main` is protected with the Python 3.10–3.13 checks, and annotated tag `v0.1.0a1` exists. The tag targets release commit `8b37e48b65321403bb3eb4ed0fdfe949dc9f1506`, whose tree matches current `main`.

## Inferences and recommendations

The following are recommendations, not claims directly made by the repository:

- Preserve the shipped contracts v1 wire shapes while making `exhaust_plume.api` the public namespace.
- Sequence the next release as `0.1.0a2` for API consolidation and washed-provider productization.
- Develop MOC privately in parallel but do not merge a public MOC provider before the API freeze.
- Treat the current straight continuation's moving-ambient momentum equation as requiring re-derivation.
- Delay physical optical products until exact ray intervals and gray slab transfer pass independent tests.

## Relevant repository URLs

- Main commit: https://github.com/sheepfling/Exhaust-Plume/commit/49d6ffd1839258ce14319e157002005c6d2230e1
- First MVP release: https://github.com/sheepfling/Exhaust-Plume/blob/main/docs/first_mvp_release.md
- Interface gate: https://github.com/sheepfling/Exhaust-Plume/blob/main/docs/interface_v1_gate_report.json
- MVP alignment: https://github.com/sheepfling/Exhaust-Plume/blob/main/docs/mvp_product_alignment.md
- Interface contracts: https://github.com/sheepfling/Exhaust-Plume/blob/main/docs/interface_contracts_v1.md
- Package root: https://github.com/sheepfling/Exhaust-Plume/blob/main/src/exhaust_plume/__init__.py
- API lifecycle: https://github.com/sheepfling/Exhaust-Plume/blob/main/src/exhaust_plume/api/lifecycle.py
- Contracts lifecycle: https://github.com/sheepfling/Exhaust-Plume/blob/main/src/exhaust_plume/contracts/lifecycle_v1.py
- First-cell boundary: https://github.com/sheepfling/Exhaust-Plume/blob/main/src/exhaust_plume/models/shock_cells/solve.py
- Conservative handoff: https://github.com/sheepfling/Exhaust-Plume/blob/main/src/exhaust_plume/contracts/handoff.py
- Straight integral continuation: https://github.com/sheepfling/Exhaust-Plume/blob/main/src/exhaust_plume/models/integral/straight.py
- Curved model: https://github.com/sheepfling/Exhaust-Plume/blob/main/docs/curved_plume_model.md
- Rotor wake: https://github.com/sheepfling/Exhaust-Plume/blob/main/docs/actuator_disk_wake_model.md
- Curved geometry: https://github.com/sheepfling/Exhaust-Plume/blob/main/docs/curved_plume_geometry.md
