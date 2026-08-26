# Planar MOC and continued shock-cell-chain work plan v1

This is the long-running plan for the higher-fidelity planar method-of-
characteristics (MOC) lane and its eventual continued cell chain. It is
separate from the fast visualization solver and from the calibrated
reduced-order shock-train provider.

## Product and fidelity boundary

| Lane | Intended use | Current status | Promotion rule |
| --- | --- | --- | --- |
| `shock-cell-basic-v1` | fast, easy visual exploration | frozen compatibility-backed visual lane | do not change while MOC work proceeds |
| `shock-train-reduced-order-v1` | bounded engineering-approximate continued chain | implemented with one resolved compatibility first cell plus scaled downstream cells | remains explicitly `scaled-reduced-order` |
| `planar-moc-research-v2` | numerical planar characteristic research and future resolved first cell/chain | open fan/reflected lattice, sampled attached-shock fit, shock-seeded closed post-shock field, and a state-carrying chain boundary | requires a canonical free-boundary solver, refinement, and independent validation |
| signature, ray, and focal-plane-array lanes | downstream measurement products | separate contracts and providers | consume only an accepted upstream field/operator |

The MOC lane must never import a reduced-order cell and relabel it as a
resolved MOC cell. Conversely, the fast visual lane remains useful and does
not wait on this research closure.

## Completed in this tranche

- Added a post-shock first downstream cross-characteristic layer. It checks
  forward geometry and both compatibility invariants while retaining the
  result as explicitly partial.
- Added a sampled attached-shock boundary fit with branch checks, local tangent
  residuals, downstream-state reconstruction, and sample-wise total-pressure
  loss.
- Added a closed post-shock field acceptance gate. It requires explicit shock
  and centerline boundary edges, connected finite-cell topology, and converged
  characteristic-node evidence; it does not synthesize missing cells.
- Added a shock-seeded C+/C- field assembler. It grows shrinking compatible
  fronts from a fitted shock boundary, carries post-shock total pressure along
  the source lineage, closes the terminal characteristic fan to the symmetry
  line, and rejects zero-area or missing-edge constructions.
- Added the only permitted promotion path from a verified closed post-shock
  field into a `RESOLVED_PLANAR_MOC` chain seed, retaining closure and residual
  diagnostics.
- Added typed downstream characteristic-state/total-pressure handoff samples
  and a state-carrying chain adapter. Every next field must report the exact
  incoming handoff before its cell can be appended.
- Added an MOC chain continuation contract. It accepts only connected,
  topologically bounded meshes with explicit physical closure and resolved
  planar-MOC fidelity.
- Added axial-boundary, cell-index, domain-limit, and callback termination
  checks.
- Added a hard fidelity boundary: scaled reduced-order candidates are
  rejected by the MOC chain and belong in the shock-train lane.
- Added tests for open-seed blocking, topology/axial checks, solver
  termination, and reduced-order rejection.

## Execution sequence

### MOC-1 — Fit the first physical compression boundary

1. Define the upstream boundary samples and the shock parameterization in one
   coordinate convention.
2. Solve the attached or detached branch decision at each sample; reject a
   candidate when the requested turn, shock branch, or downstream Mach is
   outside the planar lane.
3. Carry upstream and downstream total pressure at every shock sample.
4. Fit the shock endpoint and require monotone, forward shock geometry.
5. Keep a failed fit as a structured result; do not close the mesh with a
   geometric line merely because its endpoints are finite. The sampled fit
   contract is implemented; the canonical free-boundary solver remains open.

### MOC-2 — Assemble the complete post-shock field

1. Retain the existing shock-to-centerline `C-` traces.
2. Extend the first cross-characteristic layer into a complete downstream
   `C+`/`C-` characteristic network.
3. Build finite cells adjacent to the shock and axis, with one explicit
   physical perimeter and no non-manifold edges.
4. Check invariant residuals, forward-ray margins, cell-area coverage, and
   total-pressure loss across the shock.
5. Promote `physical_closure` only when all of those checks pass. A
   topologically bounded open lattice is not sufficient. The shock-seeded
   boundary-conditioned assembler now passes this local gate on a varied
   prescribed fixture; the free-boundary shock fit and external acceptance
   gates remain open.

### MOC-3 — Re-solved continued cells

Use the state-carrying callback behind
`continue_post_shock_characteristic_chain` as the local MOC solver boundary:

1. take the previous cell's downstream boundary states and total-pressure
   field;
2. construct the next local characteristic problem from those states;
3. solve its compression/expansion boundary and post-shock field;
4. return a new field and cell with `resolved-planar-moc` fidelity, or a
   structured validity/termination result; the adapter verifies that all
   upstream characteristic states and total pressures equal the prior
   handoff;
5. stop on physical model limits, not on an arbitrary count, while retaining
   count and axial distance as safety limits.

The existing reduced-order `solve_shock_train` remains the separate Level B
implementation. It must not be used as this callback.

The verified post-shock result exposes the only seed-promotion adapter for this
lane. An open zone, prescribed-boundary diagnostic, or scaled reduced-order
cell cannot use that adapter. The continued-cell callback remains an explicit
solver boundary: it does not invent a shock location when a next free-boundary
fit has not been supplied.

### MOC-4 — Refinement and numerical acceptance

For underexpanded and mild attached overexpanded cases, run at least three
characteristic resolutions and record:

- first-cell endpoint and physical length;
- shock endpoint and post-shock field residuals;
- cell-area coverage residual;
- maximum invariant residual and minimum forward margin;
- downstream cell spacing and chain termination sensitivity.

Refinement evidence is diagnostic until the physical closure and external
measurement comparison both pass.

### MOC-5 — Independent validation

Use a disjoint case and an explicit measurement operator. Keep the current
CJ/UEJ component comparison as supporting, not accepted, evidence until the
measurement-space mapping and closure domain are complete. Record uncertainty
and source provenance with the result.

### MOC-6 — Product integration

Only after MOC-1 through MOC-5 pass:

- add a versioned MOC provider capability;
- expose MOC-derived geometry to the standard visualization API;
- compare MOC and basic visual outputs side by side with fidelity labels;
- route signature/ray/FPA products through MOC only when their own upstream
  and measurement gates pass.

## Definition of done for this long goal

- first-cell shock fitting and post-shock `C+`/`C-` field are physically
  closed, not merely topologically bounded, for a canonical free-boundary
  solver;
- continued cells are re-solved planar MOC cells with shared boundaries and
  explicit total-pressure bookkeeping;
- reduced-order cells remain marked and isolated;
- physical termination and numerical truncation remain distinct;
- refinement and disjoint validation reports are reproducible;
- no basic visual, signature, ray, or FPA provider changes occur before the
  appropriate provider-bound validation gate.

## Current blockers

- The current full-field pass uses a varied prescribed shock boundary to
  exercise the characteristic assembler. The sampled fit remains a supplied
  boundary contract, not an accepted free-boundary shock finder.
- No production solver yet supplies a canonical free-boundary field or
  automatic next-cell shock fit. The state-carrying chain adapter therefore
  requires an explicit re-solved field callback and does not use the
  reduced-order chain.
- The recovered validation archive is not a substitute for the missing
  provider-bound measurement/operator bindings.

These blockers are intentionally represented as structured statuses in code;
they are not reasons to weaken the fidelity boundary.
