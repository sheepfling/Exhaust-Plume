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
| `planar-moc-research-v2` | numerical planar characteristic research and future resolved first cell/chain | open fan/reflected lattice, sampled attached-shock fit, solver-generated marched attached-shock reference field, shock-seeded closed post-shock field, and a state-carrying chain boundary | requires reflected-field coupling, production next-cell free-boundary solving, refinement, and independent validation |
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
- Added a solver-generated attached-shock marcher and full post-shock field
  reference. It solves a local attached compression at each boundary sample,
  integrates the shock tangent to the centerline, and records refinement and
  topology evidence without changing the lower-fidelity providers.
- Added a generated continued-cell adapter. It records the prior terminal
  characteristic trace as `incoming_handoff` while a new shock boundary and
  closed field are generated from explicit upstream callbacks.
- Added a domain-bounded reflected-zone sampler for compatible state and
  static-pressure callbacks. A shock probe now fails explicitly when it leaves
  the solved reflected lattice instead of silently extrapolating upstream flow.
- Added a typed reflected-zone shock-path coupling probe. It records the exact
  first missing upstream sample and the last valid state/pressure pair, making
  the future characteristic-strip seam executable without treating a domain
  miss as physical closure.
- Added a separately labeled reflected-boundary trace-extension reference. It
  can generate a closed shock field from the terminal boundary trace, while
  retaining the upstream characteristic-strip coupling gate.
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
  and a state-carrying chain adapter. The field labels that handoff as a
  terminal characteristic trace, not an axial section. Every next field must
  report the exact incoming trace it consumed before its cell can be appended;
  its newly propagated shock boundary is validated separately.
- Added a deterministic prescribed-boundary chain-planner mock to the
  primitive validation report. It exercises three resolved callback cells,
  carries total-pressure loss across the mock steps, and remains explicitly
  non-physical until each continuation cell is coupled to a solved
  free-boundary shock geometry.
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
   contract and a solver-generated uniform linear-turn reference are
   implemented; coupling the marcher to the reflected upstream field and a
   solved downstream boundary condition remains open.

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
   boundary-conditioned assembler now passes this local gate on both a varied
   prescribed fixture and the solver-generated uniform reference; reflected
   upstream-field coupling and external acceptance gates remain open.

### MOC-3 — Re-solved continued cells

Use the state-carrying callback behind
`continue_post_shock_characteristic_chain` as the local MOC solver boundary:

1. take the previous cell's terminal characteristic trace and total-pressure
   field;
2. propagate that trace to the next local shock boundary; an axial section is
   a separate boundary kind and must not be inferred from the trace;
3. solve the next compression/expansion boundary and post-shock field;
4. record the exact incoming trace in `incoming_handoff`, return a new field
   and cell with `resolved-planar-moc` fidelity, or return a structured
   validity/termination result; the adapter verifies that the consumed trace
   is unchanged and that upstream total pressure does not reset upward;
5. stop on physical model limits, not on an arbitrary count, while retaining
   count and axial distance as safety limits.

The existing reduced-order `solve_shock_train` remains the separate Level B
implementation. It must not be used as this callback.

The validation script's planner mock is only an executable contract fixture:
it supplies the next shock boundary directly so that handoff, pressure-loss,
and fidelity checks can run. A separate generated-chain reference now runs the
same continuation adapter with solver-generated boundaries, but its upstream
field and linear downstream-turn law remain explicit callbacks. Neither is
evidence for production automatic shock placement, physical termination, or
external validation.

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

The marched attached-shock reference now has 9/17/33-sample refinement
evidence. This is numerical diagnostic evidence only until the upstream
reflected field and downstream boundary condition are solved together.

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

- The solver-generated marcher currently uses a uniform upstream state and
  explicit linear downstream-turn law. It closes a higher-fidelity reference
  field, but is not yet coupled to the reflected MOC upstream state/pressure
  field or a solved downstream boundary condition.
- The reflected-zone sampler currently exposes only the assembled lattice. The
  candidate shock leaves that domain after its boundary start, so a physical
  upstream extension/continuation solve is still required.
- The trace-extension reference uses a constant terminal boundary trace; it is
  useful for deterministic plumbing and refinement, but it is not the physical
  upstream characteristic strip.
- No production solver yet supplies an automatic next-cell shock fit. The
  state-carrying chain adapter therefore requires an explicit re-solved field
  callback and does not use the reduced-order chain.
- The recovered validation archive is not a substitute for the missing
  provider-bound measurement/operator bindings.

These blockers are intentionally represented as structured statuses in code;
they are not reasons to weaken the fidelity boundary.
