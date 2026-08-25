# Start here

> **PR publication resync:** see [`docs/PR_CREATION_RESYNC.md`](docs/PR_CREATION_RESYNC.md) for current tag, branch-protection, PR, and branch state.
## Repository anchor

Work from a clean checkout of:

```text
sheepfling/Exhaust-Plume
main@49d6ffd1839258ce14319e157002005c6d2230e1
package version 0.1.0.a1
```

Confirm that `main` has not moved before beginning. If it has moved, record the new SHA and rerun `RLS-001`; do not silently apply this packet to an unknown baseline.

## Opening sequence

1. `RLS-001` — run and record the final `main` release gate.
2. `RLS-002` — verify the existing alpha tag and repository hygiene, then advance development after release evidence is accepted.
3. `API-008A` — approve one canonical API authority.
4. `API-008B` and `API-008C` — consolidate lifecycle and schemas.
5. `API-009` — establish canonical conformance.
6. Port the three existing providers (`PRV-001` through `PRV-003`).
7. Freeze v1 (`API-010`).
8. Productize the washed kernel (`HND-001` through `WASH-005`).
9. Develop the validated MOC first cell in its private lane (`MOC-001` onward).

## Program rules

- One issue packet per PR.
- The default branch must not be used for direct development commits.
- Preserve 0.1.0a1 compatibility until a packet explicitly changes it.
- New public work targets `exhaust_plume.api`; do not add a third contract hierarchy.
- The visual, signature, and ray-transfer products remain independent.
- Provider-private zones, stations, grids, and meshes never become interchange DTOs.
- `PlumeFluxSection` is the only physical regime-to-regime handoff.
- No later fidelity layer may conceal a failed contract, conservation, topology, convergence, or validation gate.
- Domain truncation is never labeled physical termination.
- Tabulated signature data is not physical radiation.
- Visual geometry is not an optical medium.
