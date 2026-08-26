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
| `planar-moc-research-v2` | numerical planar characteristic research and future resolved first cell/chain | open fan/reflected lattice, sampled attached-shock fit, solver-generated marched attached-shock reference field, shock-seeded closed post-shock field, ambient-perimeter shooting seam, and a state-carrying chain boundary | requires reflected-field coupling, a converged physical ambient perimeter, production next-cell free-boundary solving, refinement, and independent validation |
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
- Added a reflected-zone shock solver entry point and continued-cell adapter.
  They feed the domain-bounded reflected state/pressure callbacks directly into
  the attached-shock march, independently resample the generated path, and
  reject a next cell when the shock leaves the solved upstream lattice. The
  downstream turn condition remains explicitly caller-supplied.
- Added a reusable triangular source-boundary characteristic-strip solver. It
  reconstructs the axis/free-boundary C+/C- lattice with explicit diagonal
  seam checks and exposes a domain-bounded pressure-aware field for later
  shock fitting.
- Added an explicitly labeled constant-`K+` simple-wave continuation of the
  source strip. The canonical case adds 12 samples, preserves a converged
  231-node/230-cell open topology, and advances a domain-bounded shock probe
  before stopping at the next missing upstream field sample. This is a
  diagnostic continuation law, not physical shock closure.
- Added explicit source-window metadata and a terminal-window continuation
  result. When the full triangular continuation reaches a characteristic
  caustic, a converged terminal patch can be consumed without hiding the
  failed prefix; the full-strip failure remains attached to the report.
- Added a deterministic spatial index to the domain-bounded source-strip
  sampler. Repeated shock samples now reuse node and cell lookup metadata,
  keeping large terminal-window/invariant-shooting experiments practical
  without extrapolating outside the solved characteristic domain.
- Added bracketed constant-invariant downstream shooting. It resolves a local
  attached-compression angle from the domain-bounded upstream strip, marches
  the shock, and accepts a result only when the post-shock characteristic field
  closes. Invalid endpoints and midpoints stop the shoot instead of being
  skipped or extrapolated. The canonical window currently records a
  no-bracket result, so this is a coupling boundary and not a physical closure
  claim.
- Added an invariant-conditioned continued-cell adapter that consumes the
  exact prior terminal trace before a solved field can become a next chain-cell
  result. It raises on unresolved closure and cannot relabel reduced-order
  geometry.
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
- Added a typed chain termination decision. A callback returning `None` remains
  a non-physical numerical stop; only an explicit physical-termination
  decision can set `physical_termination=true`. The planner mock now uses the
  non-physical typed stop so its three-cell result cannot be mistaken for a
  predicted chain endpoint.
- Added continued-chain pressure-lineage reporting. Each state-carrying cell
  now reports its outgoing total-pressure range and the chain report records
  whether those carried maxima are nonincreasing. This is a handoff
  bookkeeping check, not a substitute for a physical shock-loss proof.
- Added an explicit ambient-pressure outer-perimeter gate. It extracts the
  mesh boundary left after removing the shock and centerline edges, requires
  solver-carried state/total-pressure samples on that trace, and checks both
  static-pressure matching and flow tangency. The synthetic shrinking-front
  field now records this gate as a pressure/tangency failure rather than
  allowing a topological perimeter to stand in for a free boundary.
- Added a bounded scalar ambient-pressure closure shoot. It varies an explicit
  linear downstream-turn endpoint, regenerates the attached shock and
  post-shock field at every trial, and shoots the signed mean pressure residual
  on the actual non-shock/non-centerline perimeter. The independent validator
  still gates every pressure and tangent sample, so a scalar pressure root
  cannot be promoted when the perimeter is an internal characteristic.
- Added a reflected-zone ambient-closure adapter and strict chain-promotion
  method. The adapter independently resamples the generated shock path and
  records the first missing reflected-zone sample; only a fully ambient-closed
  result with complete upstream coverage can become a continued MOC chain
  cell.
- Added a typed normal-shock terminal primitive. It reconstructs the
  subsonic Mach number, static-pressure rise, and total-pressure loss without
  fabricating a subsonic `CharacteristicState`; the marched-shock result
  carries that evidence when a zero-turn symmetry endpoint is reached, while
  chain promotion remains blocked until a mixed-regime field is solved.
- Added a separate boundary-conditioned triangular assembler. It couples a
  branch-checked shock trace and an independently accepted ambient trace
  through C+/C- intersections, then requires the remaining perimeter to
  reproduce the centerline before exposing a resolved chain handoff. No
  production free-boundary shooter is wired to it yet.
- Added the correctly oriented shock/ambient strip seam. A shock-sourced C+
  march generates an ambient-pressure, streamline-tangent C- boundary, and
  the independent strip assembler couples those sources into a 45-node/
  44-cell (at nine samples) physical-boundary net. Its downstream terminal
  trace is explicit and chain promotion remains blocked until a centerline
  closure is solved. The trace is also exported as typed chain-boundary
  samples and checked independently as a shock-sourced C+ characteristic;
  its nonzero coarse-grid geometry residual is retained as a rejection
  diagnostic rather than hidden by the open-strip status.
- Added a typed terminal-compression candidate. It consumes the open strip's
  shock-sourced C+ trace, checks the endpoint's ambient static pressure, and
  solves a forward attached compression segment to the centerline. A declared
  mesh-scale trace tolerance is retained separately from the strict trace
  diagnostic. The candidate reports branch and total-pressure-loss evidence,
  but its characteristic patch is unsolved, so physical closure and chain
  promotion remain hard-false.
- Added an independent MOC shock-cell measurement operator. It extracts
  shock/centerline boundaries, axial extent, boundary lengths, radius, mesh
  area, perimeter-area closure, and optional shock total-pressure loss only
  from explicit field geometry. The same operator runs over the solver
  reference and the prescribed three-cell planner mock; its results remain
  diagnostic and `not_accepted` until an external measurement mapping exists.
- Added an explicit strict continuation mode that requires carried upstream
  shock states and total pressure before a field can enter the production
  promotion path. The compatibility mode remains available for prescribed
  research fixtures, but its chain seed records that upstream coupling was
  not verified.
- Added a separate centerline-reflection upstream continuation law. It sends
  the outer boundary's ``C-`` characteristic to the symmetry line, applies
  ``theta=0``, and marches the reflected ``C+`` characteristic to the
  ambient-pressure/tangent boundary at each step. The canonical source
  domain retains the generated samples but currently stops at a forward-ray
  caustic when the old triangular mesh is reassembled; that bounded failure is
  evidence for the required remesh/shock-closure seam, not a promotion.
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
   contract, a solver-generated uniform linear-turn reference, and a
   domain-bounded invariant-shooting boundary are implemented. A separate
   bounded ambient-pressure shoot now drives the actual post-shock outer
   perimeter, but the canonical reflected-zone attempt stops at its first
   missing upstream sample and the synthetic pressure root still fails full
   perimeter tangency, so the physical downstream condition remains open.

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
   count and axial distance as safety limits. A physical endpoint must be
   returned as an explicit `MocChainTerminationDecision`; `None` and safety
   truncation remain non-physical.

The existing reduced-order `solve_shock_train` remains the separate Level B
implementation. It must not be used as this callback.

The validation script's planner mock is only an executable contract fixture:
it supplies the next shock boundary directly so that handoff, pressure-loss,
and fidelity checks can run. Its prescribed boundary advances with each
planned cell, and the report checks the carried total-pressure maxima without
calling that bookkeeping a physical endpoint. A separate generated-chain
reference now runs the same continuation adapter with solver-generated
boundaries, but its upstream field and linear downstream-turn law remain
explicit callbacks. Neither is evidence for production automatic shock
placement, physical termination, or external validation.

The continuation adapter also exposes a strict upstream-coupled mode. It
rejects the prescribed planner seed before callback execution and requires
each generated field to carry the fitted upstream shock state/pressure
samples. The canonical marcher separately reports
`subsonic_terminal_required` when a zero-turn/normal-shock endpoint would need
to leave the supersonic MOC lane.

The constant-`K+` source-strip continuation is a separate upstream-only
diagnostic fixture: it tests how a continued shock probe consumes a growing
characteristic domain, but it must not be promoted into a resolved chain cell
until the shock boundary and post-shock field are solved from the coupled
reflected MOC state/pressure field. A terminal source window is allowed as a
domain-bounded research input only when its omitted prefix and full-strip
status are retained alongside it.

The invariant-conditioned shock solver is the next explicit boundary for this
work: it can reject an unbracketed or domain-limited closure, but it does not
invent a downstream physical law. A converged invariant-conditioned field is
therefore still research evidence until the selected invariant, case domain,
and independent measurements are validated.

The reflected-zone shock solver now closes the upstream callback seam without
claiming a complete first-cell solution. Its independent coverage report is a
required input to the continued-cell adapter; the canonical reflected zone
still ends before the candidate shock can reach the symmetry line, so the
expected result is a bounded `upstream_field_failure` rather than an
extrapolated cell. A future solve must extend or re-mesh the upstream
characteristic domain and replace the caller-supplied downstream turn law.
The new ambient-pressure adapter uses the same domain-bounded callbacks and
adds a strict outer-perimeter pressure/tangency gate; its canonical result is
therefore a bounded field/coupling failure and cannot be promoted into the
continued chain.

The terminal-compression candidate is the next local boundary primitive after
the open shock/ambient strip. It is intentionally weaker than a first-cell
closure: it solves the endpoint-to-centerline compression only. The next
solver must supply the upstream state along that compression and assemble the
compatible characteristic patch between the incoming terminal C+ trace and
the new boundary before a resolved cell can be returned.

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

Use a disjoint case and an explicit measurement operator. The local
`op.moc.shock-cell-geometry` and `op.moc.shock-cell-chain` operators now
provide the geometry/topology extraction layer for solver fields and planner
fixtures, including optional shock total-pressure loss. Keep the current
CJ/UEJ component comparison as supporting, not accepted, evidence until the
external measurement-space mapping, uncertainty/provenance, and closure
domain are complete. The operator must not infer physical shock cells from a
centerline pressure trace or repair an open mesh.

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
  field, but is not yet coupled to a complete reflected MOC upstream
  state/pressure domain or a converged physical downstream boundary
  condition. The new scalar ambient shoot is a bounded research seam; it does
  not change that claim.
- The reflected-zone shock entry point now consumes the assembled lattice
  directly, but the canonical candidate still leaves that domain after its
  boundary start. A terminal source-window continuation makes that boundary
  explicit, but the full continuation still reaches a characteristic caustic
  and the physical upstream extension/continuation solve is still required.
- The trace-extension reference uses a constant terminal boundary trace; it is
  useful for deterministic plumbing and refinement, but it is not the physical
  upstream characteristic strip.
- The shock-seeded field's remaining polygon perimeter is now explicitly
  measurable, but the prescribed fixture fails the ambient-pressure and
  streamline-tangency gate. A coupled solver still has to replace that
  internal-characteristic edge with a solved free boundary before a cell can
  be accepted physically. The new shock-sourced ambient strip demonstrates the
  corrected source-family orientation and carries the physical boundary
  conditions, but its terminal trace still needs an axis/centerline closure.
  The scalar shoot continues to demonstrate the old internal-characteristic
  failure without weakening the gate.
- The canonical marched shock now classifies a zero-turn/normal-shock endpoint
  as `subsonic_terminal_required` and carries a verified typed normal-shock
  terminal diagnostic. That is an explicit supersonic-MOC validity boundary,
  not a reason to force a bracket or relabel the endpoint as a converged
  supersonic cell; a mixed-regime field and perimeter model is still required
  for that case.
- The invariant-conditioned shock shoot currently records a canonical
  no-bracket result; a selected constant downstream invariant is not yet an
  accepted physical free-boundary condition. No production solver yet supplies
  an automatic next-cell shock fit. The state-carrying chain adapters therefore
  require a converged explicit research solve and do not use the reduced-order
  chain.
- The independent shock-cell measurement operators now pass local geometry,
  topology, and supplied shock-loss extraction for the current fixtures, but
  they do not provide external observations, uncertainty, or a provider-bound
  measurement-space mapping. Their successful status must not be read as
  physical MOC closure or validation acceptance.
- The recovered validation archive is not a substitute for the missing
  provider-bound measurement/operator bindings.

These blockers are intentionally represented as structured statuses in code;
they are not reasons to weaken the fidelity boundary.
