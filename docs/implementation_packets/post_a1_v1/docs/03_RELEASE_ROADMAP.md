# Release Roadmap

## Dependency-ordered queue

| Packet | Priority | Title | Target | Depends on |
|---|---:|---|---|---|
| `A1-000` | P0 | Post-release baseline, CI evidence, and repository hygiene | 0.1.0a2 | — |
| `A1-010` | P0 | API-008 authority review, compatibility inventory, and freeze record | 0.1.0a2 | A1-000 |
| `A1-011` | P0 | Canonical API adapters, schema authority, root exports, and deprecations | 0.1.0a2 | A1-010 |
| `A1-020` | P0 | StraightIntegralPlumeProvider over the landed continuation kernel | 0.1.0a2 | A1-011 |
| `A1-030` | P0 | Consolidate curved-plume entrainment and freeze W1 defaults | 0.1.0a2 | A1-011 |
| `A1-040` | P0 | WashedIntegralPlumeProvider and canonical visual/flux adapters | 0.1.0a2 | A1-020, A1-030 |
| `A1-050` | P0 | Live visual consumer swap and golden physics fixture | 0.1.0a2 | A1-040 |
| `A1-060` | P1 | Loopback HTTP/1.1 sidecar for canonical schemas | 0.1.0a2 | A1-011, A1-050 |
| `A1-070` | P1 | Downstream shock-cell flux-section extraction and transition diagnostics | 0.1.0a3 | A1-020 |
| `A1-071` | P1 | ShockToWashedCompositeProvider and provenance chain | 0.1.0a3 | A1-040, A1-070 |
| `A1-080` | P1 | Exact/convergent ray intervals through straight and curved support | 0.1.0a3 | A1-040 |
| `A1-081` | P1 | Homogeneous gray ray-transfer provider and advertisement gate | 0.1.0a3 | A1-080 |
| `A1-090` | P2 | Calibration data registry, objective functions, and free-jet calibration | post-a3 | A1-040 |
| `A1-091` | P2 | Uniform-crossflow, rotor-wake, and helicopter held-out validation | post-a3 | A1-090 |

## `0.1.0a2` release gate

The release is ready only when:

- exact-main CI passes on Python 3.10–3.13;
- baseline docs describe the actual release;
- API-008 is recorded and one canonical API hierarchy is implemented;
- a1 imports remain compatibility-tested;
- straight integral provider passes exact regressions;
- washed provider passes zero-wash, conservation, rigid-transform, frame, and swirl-mirroring gates;
- the visual consumer swaps providers without special-case logic;
- the loopback sidecar round-trips canonical visual products;
- no washed provider advertises signature or ray transfer.

## `0.1.0a3` release gate

- downstream shock-cell conservative section and transition diagnostics;
- composite shock-to-mixing provider;
- curved support ray intervals;
- homogeneous gray transfer verification;
- separate source radiance and background transmittance;
- ray capability advertised only after all analytical/refinement gates.

## Parallel work

Documentation/CI hygiene precedes API-008. After A1-011 merges, straight-provider and entrainment-consolidation packets may run in parallel. Washed provider waits for both. After the washed provider, downstream shock handoff and ray-interval work may run in parallel.
