# Post-`0.1.0a1` program plan

## Program objective

Transform the merged alpha into a trustworthy product platform while advancing the simplest straight plume from a compatibility-backed low-order construction to a converged and externally assessed MOC first-cell model.

The program preserves three independent products:

```text
plume.visual.sectioned-tube@1
plume.signature.spectral-radiant-intensity@1
plume.optical.spectral-ray-transfer@1
```

and one physical provider-composition boundary:

```text
plume.engineering.flux-section@1
```

## Recommended architecture decision

Use `exhaust_plume.api` as the public namespace.

To minimize breakage, preserve the 0.1.0a1 `contracts/*_v1` wire shapes that already back schemas, fixtures, and real providers. Make `exhaust_plume.api` re-export or adapt those canonical wire types, then deprecate the duplicate review-witness DTOs and lifecycle rather than keeping two equal authorities.

This is a recommendation derived from the current repository state. `API-008A` must confirm it against the real consumer inventory before implementation.

## Release train

### `0.1.0a1` — reproducible baseline

Completion:

- `RLS-001`
- `RLS-002`

Exit gate:

- Tag, source, wheel, schemas, fixtures, and gate report identify the same commit and version.
- `main` is protected.
- Stale PRs and fully merged branches no longer imply unmerged work.

### `0.1.0a2` — one API and a live washed provider

Completion:

- `API-008A` through `API-010`
- `HND-001`, `HND-002`
- `WASH-001` through `WASH-005`

Exit gate:

- One public lifecycle and schema authority.
- Prescribed, straight analytical, signature-table, and washed providers pass the same conformance system.
- Visual consumers swap providers without provider-specific code.
- Washed outputs carry conservation and applicability evidence.
- Coefficients remain clearly uncalibrated where that is true.

### `0.2.0a1` — validated near field

Completion:

- `MOC-001` through `MOC-007`
- `HND-003`

Exit gate:

- Underexpanded and attached-overexpanded first-cell solutions converge with refinement.
- External comparison evidence and uncertainty are recorded.
- The canonical provider uses the MOC core without changing its product contract.
- The MOC endpoint closes a conservative control-surface handoff.

### `0.2.0a2` — coherent straight plume

Completion:

- `CELL-001`
- `MIX-001`
- `MIX-002`
- `TERM-001`
- `COMP-001`

Exit gate:

- Cell count and coherent termination are model outputs.
- Straight mixing is calibrated and validated separately.
- Physical termination and domain truncation are distinct.
- Near-field, shock-train, and mixing regimes compose only through neutral handoffs.

### `0.3.0a1` — first physical optical slice

Completion:

- `RAY-001`
- `RAD-001` through `RAD-003`
- `SIG-002`
- `OPT-VAL-001`

Exit gate:

- Exact geometry and slab transfer references pass.
- Source radiance and background transmittance remain separate.
- Ray-derived unresolved intensity converges with quadrature.
- The release makes no molecular, atmospheric, optical-train, or detector claim.

## Controlled parallelism

After `RLS-001`:

- API consolidation may proceed.
- MOC research and private numerical primitives may proceed.
- No new public MOC provider merges before `API-010`.
- Washed provider work waits for the canonical handoff and conformance contracts.
- Optical geometry waits for the canonical API and a live curved-provider fixture.

## Non-negotiable gates

1. **Release gate:** no tag without commit-specific evidence.
2. **API gate:** no additional public provider before one authority is selected.
3. **Conservation gate:** no regime handoff without mass, momentum, enthalpy, and species closure.
4. **Topology gate:** no accepted MOC solution with backward, non-finite, or self-intersecting geometry.
5. **Convergence gate:** no validated first-cell claim based only on one grid.
6. **Calibration gate:** no coefficient is called validated when it was merely selected.
7. **Radiometry gate:** no spectrum is inferred from visual geometry.
8. **Termination gate:** no requested spatial limit is called a physical plume endpoint.

## Definition of program success

The program is successful when a consumer can select prescribed, straight analytical, composed straight, or washed providers through one lifecycle; obtain independent visual, engineering, signature, or ray-transfer products as supported; trace every product to a model, applicability domain, and validation level; and upgrade provider fidelity without changing consumer-side product semantics.
