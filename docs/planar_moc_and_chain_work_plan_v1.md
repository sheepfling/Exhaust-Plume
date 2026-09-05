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
| `planar-moc-research-v2` | numerical planar characteristic research and future resolved first cell/chain | open fan/reflected lattice, sampled attached-shock fit, solver-generated marched attached-shock reference field, shock-seeded closed post-shock field, ambient-perimeter shooting seam, a state-carrying chain boundary, and a bounded multi-row characteristic-remesh/free-boundary probe | requires refinement-stable conservative Euler acceptance, globally coupled reflected-field/free-boundary closure, production next-cell free-boundary solving, and independent validation |
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
- Added a reflected-zone continued-cell ``or_termination`` adapter. It turns
  an incomplete upstream coupling into a typed non-physical
  ``upstream-field-boundary`` chain stop with the sampled count, first missing
  index, and last valid point, so the chain can report the finite-domain seam
  without raising, extrapolating, or inferring plume termination.
- Added a reusable triangular source-boundary characteristic-strip solver. It
  reconstructs the axis/free-boundary C+/C- lattice with explicit diagonal
  seam checks and exposes a domain-bounded pressure-aware field for later
  shock fitting.
- Added an explicitly labeled constant-`K+` simple-wave continuation of the
  source strip. The canonical case adds 12 samples, preserves a converged
  231-node/230-cell open topology, and advances a domain-bounded shock probe
  before stopping at the next missing upstream field sample. This is a
  diagnostic continuation law, not physical shock closure.
- Extended source-strip continuation failures now retain the longest converged
  prefix and probe the first unassembled source row. A requested long
  simple-wave continuation therefore exposes its finite prefix, frontier,
  and caustic/remesh handoff even when the full triangular strip fails; the
  retained prefix remains an open research field and is never relabeled as a
  completed upstream solve.
- Added the solver-owned source-strip-to-chain adapter and planner. A
  converged source strip can feed one bounded next-shock attempt with the
  exact prior post-shock perimeter recorded; a reflected continuation that
  reaches the canonical caustic returns a typed non-physical
  ``CHARACTERISTIC_CAUSTIC`` stop before shock fitting, while a finite strip
  boundary returns ``UPSTREAM_FIELD_BOUNDARY``. The source strip is never
  reused for a later cell and the planner remains research-only.
- Added a fresh-domain source-strip sequence planner. Each continued shock
  cell requests a new bounded upstream continuation, carries the exact prior
  post-shock perimeter into the source-strip shock adapter, and records the
  source-domain reports alongside the cell handoff audit. Reusing either a
  prior continuation result or its strip object is rejected as a typed
  ``UPSTREAM_FIELD_BOUNDARY``; the sequence remains research-only until the
  physical reflected-field and downstream closure are solved.
- Added the corresponding fresh-domain caustic-remesh sequence planner. The
  first post-caustic shock consumes one bounded Cauchy remesh, while every
  later shock requests a distinct remesh from the exact preceding handoff.
  Reusing a remesh or its source strip, returning no remesh, or presenting an
  upstream event becomes a typed upstream-field boundary; the attempt history
  and deterministic remesh fingerprints remain in the planner diagnostics.
  This extends the continued-chain audit without promoting the Cauchy patch,
  the planner mock, or any synthetic outer trace into a physical product cell.
- Added a separately named compressible isentropic potential-flow reference
  for an explicit downstream perimeter. It solves the conservative nonlinear
  subsonic potential equation on a triangular radial mesh, checks uniform
  total-pressure/gamma lineage, single-valued boundary potential,
  mass-conservation and boundary-velocity residuals, and records radial
  refinement. It remains a scalar research model with chain promotion blocked;
  it does not infer the canonical free boundary or create a supersonic MOC
  ``CharacteristicState`` field.
- Added an independent measurement operator for that compressible potential
  reference. It reconstructs the boundary seam, radial layout, potential
  gradients, compressible mass residual, circulation, and subsonic gate from
  the returned field data rather than trusting solver convenience properties.
  The validation report records the operator and its radial-refinement
  results; the measurement remains explicitly non-canonical and
  non-promotable.
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
- Added a field-coupled invariant-conditioned continued-cell solver. It uses
  the exact prior post-shock perimeter plus bounded state/pressure samples,
  inverts an explicitly selected downstream ``C+``/``C-`` invariant through
  the attached-compression relation at every shock sample, and returns either
  a newly assembled state-carrying field or a typed physical/numerical stop.
  The invariant law remains a research boundary; it does not close the
  canonical mixed-regime perimeter or promote the fast/reduced-order lanes.
- Added a reusable invariant-boundary shock marcher and caustic-family chain
  adapter. It solves the local downstream turn from an explicit `C+`/`C-`
  invariant at every generated shock sample, preserves the bounded upstream
  family-band domain, and records the first missing sample as a typed
  `upstream-field-boundary` planner stop. The canonical one-sided caustic
  wedge reaches four valid shock samples before its next shock point exits the
  solved field; no extrapolated state or physical termination is inferred.
- Added a separately labeled reflected-boundary trace-extension reference. It
  can generate a closed shock field from the terminal boundary trace, while
  retaining the upstream characteristic-strip coupling gate.
- Added a closed post-shock field acceptance gate. It requires explicit shock
  and centerline boundary edges, connected finite-cell topology, and converged
  characteristic-node evidence; it does not synthesize missing cells.
- Extended the terminal-shock supersonic composite to retain validated source
  characteristic nodes that remain in the clipped mesh. Newly cut terminal-
  shock vertices remain represented only by the explicit terminal boundary
  state arrays, preserving the mixed-regime fidelity boundary while making
  refinement and visualization reports inspectable.
- Expanded the independent CJ-UEJ MOC component diagnostic to sample the
  verified archive's centerline and off-axis static-pressure and axial-
  velocity profiles using carried total-pressure and declared total-
  temperature assumptions. Coverage and residuals remain supplemental,
  domain-bounded, and explicitly non-accepted.
- Added a shock-seeded C+/C- field assembler. It grows shrinking compatible
  fronts from a fitted shock boundary, carries post-shock total pressure along
  the source lineage, closes the terminal characteristic fan to the symmetry
  line, and rejects zero-area or missing-edge constructions.
- Added a production caustic-family-band shock seam. It consumes the bounded
  band input edge in both canonical orientations, refits the solver-generated
  supersonic shock samples, assembles a 27-cell open post-shock characteristic
  zone, and retains the typed subsonic normal-shock terminal. The zone remains
  a mixed-regime handoff with chain promotion blocked until the subsonic field
  and complete physical perimeter are solved.
- Added a bounded state/pressure sampler to the open post-shock zone. It
  carries node-level total-pressure lineage and axis-side samples, supports
  in-cell supersonic state, total-pressure, and static-pressure probes, and
  returns no extrapolated value outside the assembled cells. This makes the
  open downstream domain usable as a typed solver interface while keeping
  physical closure and chain promotion blocked.
- Extended the caustic-family band with bounded axial/transverse extents and
  an explicit no-extrapolation state-sampling capability report. Shock-coupling
  adapters now require that capability before sampling the restarted field,
  keeping a converged status from standing in for an actual usable domain.
- Added a bounded next-shock coupling adapter for that open zone. It
  independently resamples the generated shock path, preserves the exact
  first missing sample and last valid upstream state, and returns a typed
  upstream-field stop or verified normal-shock terminal rather than appending
  an open-zone cell. Its downstream turn law remains caller-supplied.
- Added a one-step open-zone chain planner wrapper. It records the exact
  carried post-shock perimeter before consuming the bounded zone, promotes
  only a fully covered upstream-coupled next field, and preserves a partial
  shock march as an `UPSTREAM_FIELD_BOUNDARY` stop. The open zone is never
  reused as though it were a resolved chain cell.
- Added a caustic-family-band continued-chain planner seam. It carries the
  exact prior post-shock perimeter into the bounded band shock solve, records
  the solver-generated open zone and terminal diagnostics, and stops with a
  typed ``OPEN_PHYSICAL_CLOSURE`` decision after one attempted next cell. Both
  canonical restart orientations pass this audit; neither is promoted as a
  resolved chain cell.
- Added an executable caustic shock-remesh executor and planner seam. It
  consumes the exact one-sided event state, incoming perimeter, and bounded
  upstream callbacks, verifies the generated shock/new-family field when a
  local invariant law closes, and exposes a combined remesh-seam verdict.
  Even a locally converged remesh remains a one-step research stop until the
  physical first-cell ambient/terminal boundary is solved; no remesh result is
  appended as a chain cell.
- Added the executable remesh and one-step planner probe to the standalone
  MOC validation report. It records the exact incoming perimeter, all local
  remesh seam gates, the solver-backed open-closure stop, and the explicit
  non-production claim ceiling alongside the existing three-cell planner
  mock.
- Added an explicit bounded downstream-field handoff after a converged
  caustic remesh. The handoff exposes the solver-carried field only after the
  event, upstream, shock, and characteristic-field seams pass, and a
  research-only planner can feed that field into the existing re-solved
  continued-cell lane with either an explicit flow-angle or selected
  characteristic-invariant boundary law. The opt-in planners preserve the
  remesh's hard physical-closure/promotion block and carry its report into
  the planner diagnostics; they are not production chain providers.
- Added a strict bridge-fed caustic remesh adapter. It uses the bounded
  old-family/restarted-family bridge at the exact event and every generated
  shock sample, retains the first uncovered point as a typed upstream-field
  boundary, and never falls back to a last state or callback extrapolation.
  The matching planner entry point carries the same audit into the one-step
  chain decision. The callback-owned remesh fixture remains available as a
  separate local solver contract; the bridge-fed path is the explicit
  canonical coupling gate and remains non-promotable when the caustic corridor
  ends.
- Added a weak-branch caustic-origin forward-envelope reachability gate. It
  follows the local zero-turn attached limit through the bounded restarted
  family band, retains the valid prefix and first missing point, and returns a
  typed ``CHARACTERISTIC_CAUSTIC`` remesh stop when the finite band ends before
  the centerline. The canonical two restart orientations both exercise this
  measured boundary; the envelope is a reachability diagnostic, not a shock
  curve or a physical closure claim.
- Added a one-step caustic-origin envelope planner wrapper. It records the
  exact incoming post-shock perimeter before the bounded reachability probe
  and preserves the typed ``CHARACTERISTIC_CAUSTIC`` stop; it cannot append
  the envelope as a continued cell.
- Added caustic-band terminal refinement and independent measurement gates.
  Five, seven, nine, and eleven shock-march samples converge in both
  orientations with open-zone cell counts 5, 14, 27, and 44 and decreasing
  shock-fit tangent residuals. The independent shock-cell measurement
  operator deliberately rejects the open terminal zone because its shock and
  centerline polylines do not share a physical endpoint; this is retained as
  evidence of the missing mixed-regime perimeter, not hidden as acceptance.
- Added the only permitted promotion path from a verified closed post-shock
  field into a `RESOLVED_PLANAR_MOC` chain seed, retaining closure and residual
  diagnostics.
- Added an ambient-closed physical-field continuation adapter and planner.
  A new cell must be returned as a separately assembled ambient-closed field,
  retain the exact prior centerline handoff, and pass the optional upstream
  shock-coupling gate before it can enter the resolved chain. The planner
  records physical-field results separately from the prescribed mock and keeps
  the research-only claim ceiling; no reduced-order or open field can cross
  this seam.
- Hardened physical-field promotion with an immutable evidence audit. A field
  now has to retain a connected bounded mesh, matching shock/ambient/
  centerline boundary paths, centerline state/pressure samples, converged
  characteristic-node residuals, an accepted ambient condition, and strict
  shock total-pressure loss in addition to its solver status. Tampering with
  the declared paths therefore cannot turn a planner fixture into a resolved
  chain cell.
- Added solver-carried downstream shock states and bounded state, static-
  pressure, and total-pressure samplers to the ambient-closed physical field.
  A strict explicit-perimeter next-cell adapter now fits a new attached shock
  using only those samples, records the exact prior centerline handoff, and
  returns typed ``UPSTREAM_FIELD_BOUNDARY`` or ``OPEN_PHYSICAL_CLOSURE`` stops
  instead of extrapolating or fabricating a cell. Automatic reflected-domain
  and ambient free-boundary shooting remain pending.
- Added a bounded first-wedge remesh checkpoint and planner. The solver-owned
  reflected centerline triangle can be subdivided at levels 1, 2, and 3 into
  4, 16, and 64 diagnostic cells using only bounded state/total-pressure
  samples; independent Euler cell residuals decrease across the ladder (about
  0.114, 0.063, and 0.033) but remain above the 1e-2 acceptance gate. The
  planner records the ladder and stops with ``FIDELITY_NOT_ALLOWED`` before
  creating a ``MocChainCell``. This is a measured remesh/state-projection
  seam, not conservative Euler closure, and it does not alter the basic or
  reduced-order providers.
- Added an independent variable-entropy characteristic audit for the
  first-wedge remesh. It evaluates the generalized ``K+``/``K-`` source from
  the carried total-pressure gradient and separately checks that each
  triangular subcell retains two characteristic-aligned edges. The current
  canonical remesh fails that edge-topology gate, making the missing
  entropy-carrying terminal-wedge solve explicit rather than allowing the
  isentropic projection to be promoted.
- Added a solver-owned terminal-wedge characteristic candidate and planner.
  It replaces the old axis vertex with the downstream endpoint of the
  terminal node's reflected ``C-`` characteristic, carries that node's total
  pressure onto the reflected edge, and retains the corrected ``C+``/``C-``
  geometry as a one-cell candidate. The canonical candidate passes topology,
  state/pressure lineage, and characteristic alignment, while the
  independently recomputed variable-entropy and local Euler residual gates
  still fail. The planner records the candidate and terminates with
  ``FIDELITY_NOT_ALLOWED``; it contributes zero physical ``MocChainCell``
  objects and does not modify the existing field or lower-fidelity providers.
- Added a strict ambient-axis-shoot-to-physical-field bridge. A scalar
  attachment-coordinate pressure root is now rechecked against the complete
  ambient-to-axis pressure/tangency perimeter before the shock/ambient/
  centerline field assembler can run. Failed tangency remains a typed
  ``ambient_axis_boundary_failure`` with no field or chain promotion; a
  future passing field will still be research-only until canonical reflected
  coupling and external validation are complete.
- Added typed downstream characteristic-state/total-pressure handoff samples
  and a state-carrying chain adapter. The shock-seeded field labels its
  composite carried edge as a post-shock field perimeter, not a single
  characteristic or an axial section. Every next field must report the exact
  incoming boundary it consumed before its cell can be appended; its newly
  propagated shock boundary is validated separately.
- Added a deterministic prescribed-boundary chain-planner mock to the
  primitive validation report. It exercises three resolved callback cells,
  carries total-pressure loss across the mock steps, and remains explicitly
  non-physical until each continuation cell is coupled to a solved
  free-boundary shock geometry.
- Added a reusable planner wrapper for generic and post-shock chains. It
  records the exact boundary kind, sample count, total-pressure range, and a
  deterministic full state/pressure handoff fingerprint before every callback,
  while retaining a hard non-production claim ceiling for the prescribed-
  boundary mock. Each step now also records the typed callback outcome (field
  solve, cell, termination, no-cell, or solver error) and its status, so a
  multi-cell mock and a physical-stop research path are auditable step by step.
- Extended the independent shock-cell chain measurement with optional raw
  incoming/outgoing typed handoffs. When a chain supplies that metadata, the
  operator now requires exact state/total-pressure equality and matching
  boundary kinds across every adjacent cell. Both the three-cell prescribed
  planner mock and the three-cell solver-generated reference pass this audit;
  a tampered handoff is retained as a chain failure. This validates state
  transport without treating either research fixture as physical plume data.
- Added a terminal-reflection-patch planner wrapper that routes the exact
  outgoing ``C-`` handoff through the generic planner and records the typed
  normal-shock stop. It permits only the patch's one solved domain step;
  later cells require a new upstream field and solver adapter.
- Promoted the prescribed three-cell continuation fixture into the public
  isolated planner module as `MocPrescribedPostShockChainMock` with a
  `plan_prescribed_post_shock_chain_mock` convenience entry point. The
  validation script now only adds observations around that reusable fixture;
  its prescribed shock geometry remains planning evidence and cannot satisfy
  the free-boundary or product-promotion gates.
- Promoted the three-cell solver-generated continuation reference into the
  public isolated planner module as
  `MocSolverGeneratedPostShockChainReference` with a
  `plan_solver_generated_post_shock_chain_reference` convenience entry point.
  Each step now re-solves the attached shock and closed post-shock field
  through the real solver, while the explicit uniform upstream state and
  linear downstream-turn law remain named reference conditions. The fixture
  exercises state/total-pressure handoff and is still research-only; it does
  not stand in for the reflected upstream field or a physical downstream
  boundary.
- Added a separate `MocFieldCoupledPostShockChainReference` and planner entry
  point. Its shock/pressure solve samples only the currently accepted bounded
  post-shock field and replaces that field only after a complete returned
  cell. The canonical seed reaches the typed normal-shock termination before
  a second cell, while a synthetic broad-domain contract fixture proves that
  a re-solved cell can be followed by a typed upstream-field boundary without
  extrapolation. This remains planner/research evidence, not canonical plume
  closure or production-chain validation.
- Hardened the prescribed planner mock so every continued cell passes its
  prescribed curve through the real branch-checked attached-shock fitter. The
  default fixture is a nondegenerate varying-state shock line, the returned
  field retains the fitted maximum shock-angle residual, and incompatible
  geometry fails before characteristic assembly. An optional pressure-loss
  ratio is now an assertion only; it can never fabricate post-shock states.
- Tightened chain-boundary semantics so a carried `CENTERLINE_TRACE` must
  actually lie on `y=0` with `theta=0`; a generic downstream polyline cannot be
  relabeled as an axis handoff.
- Added a solver-owned mixed-regime perimeter request from the terminal shock
  composite. It exposes the terminal scalar state and supersonic post-shock
  samples but supplies no inferred downstream perimeter; the open supersonic
  zone remains an explicit non-perimeter seam.
- Added a typed terminal-boundary graph audit. It independently verifies the
  solver-owned initial-shock, ambient-streamline, centerline, and terminal-
  shock joins, reports their residuals, and accepts an optional downstream
  path only as geometry. It never treats that path as a physical downstream
  condition or mixed-regime field, so chain promotion remains blocked.
- Added a callback-owned mixed-regime closure gate. A returned field must
  retain the exact terminal object and patch sample count and pass its closed
  perimeter/topology/residual checks before the terminal composite can attach
  it or issue a physical stop.
- Added a validated reference attachment test for the terminal mixed-regime
  lane. It solves an explicitly supplied scalar perimeter with the separate
  elliptic/isentrope reference field and verifies the resulting physical
  terminal decision. The perimeter is deliberately a contract fixture; the
  canonical downstream boundary is still not inferred from the open
  supersonic field.
- Promoted that synthetic pressure-outflow terminal fixture into the reusable
  planner namespace as `MocPrescribedMixedRegimeClosureMock`. It now owns an
  explicit closed rectangle, exact terminal-seam scalar samples, and the
  separate elliptic reference solve, while reporting a hard planning-only,
  non-production claim ceiling. It is executable planner evidence for the
  mixed-regime handoff, not a canonical free-boundary perimeter or a
  continued supersonic chain cell.
- Marked every mixed-regime closure result as `chain_promotion_blocked`.
  Condition-qualified reference fields may produce a typed terminal stop, but
  they cannot be reused as a supersonic next-cell seed.
- Added an MOC chain continuation contract. It accepts only connected,
  topologically bounded meshes with explicit physical closure and resolved
  planar-MOC fidelity.
- Added a typed chain termination decision. A callback returning `None` remains
  a non-physical numerical stop; only an explicit physical-termination
  decision can set `physical_termination=true`. The planner mock now uses the
  non-physical typed stop so its three-cell result cannot be mistaken for a
  predicted chain endpoint.
- Added a continued-cell adapter that returns either a generated
  state-carrying cell or an explicit normal-shock termination decision. The
  solver-generated chain probe now demonstrates a one-cell continuation that
  stops physically at the typed subsonic boundary while retaining the missing
  mixed-regime field as a blocker.
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
- Added an ambient-pressure field-coupled continued-cell adapter and planner.
  Each candidate next shock consumes the prior post-shock perimeter exactly,
  re-solves against the currently accepted bounded state/pressure field, and
  replaces that field only after the ambient pressure/tangency, shock-fit,
  upstream-coupling, and handoff gates pass. Bounded-domain, bracket, and
  closure failures become typed non-physical planner stops; the lane remains
  research-only and cannot alter the fast visual or reduced-order providers.
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
- Added a bracketed ambient-attachment closure. It solves the outer shock
  turn from the local post-shock static-pressure/ambient residual, regenerates
  the marched attached shock, and assembles the physical shock/ambient strip
  without caller-supplied attachment angle. The result deliberately retains
  the linear-to-centerline law as a named reference and leaves the terminal
  trace open, so it cannot promote a first cell.
- Added a staged shock-cell transition adapter. It composes the ambient
  attachment, centerline reflection, and domain-bounded next-shock probe,
  carries the reflected outgoing ``C-`` trace as a typed next-shock handoff,
  and converts a verified normal-shock endpoint into an explicit physical
  chain stop. The transition remains non-promotable because its downstream
  condition is still a named centerline-normal-shock reference rather than a
  closed mixed-regime field.
- Added a typed terminal-compression candidate. It consumes the open strip's
  shock-sourced C+ trace, checks the endpoint's ambient static pressure, and
  solves a forward attached compression segment to the centerline. A declared
  mesh-scale trace tolerance is retained separately from the strict trace
  diagnostic. The candidate reports branch and total-pressure-loss evidence,
  but its characteristic patch is unsolved, so physical closure and chain
  promotion remain hard-false.
- Added a terminal-trace centerline reflection patch. It consumes the typed
  shock-sourced C+ trace with the correct downstream orientation, reflects
  each C- characteristic to a theta=0 centerline source, assembles the
  compatible triangular net, and emits a typed outgoing C- trace. The patch
  shares the incoming seam with the shock/ambient strip and validates the
  combined topology; its outgoing front remains open for a physical shock or
  compression boundary and therefore cannot yet be promoted as a chain cell.
- Added a domain-bounded terminal-patch shock probe. It interpolates the
  reflected patch's state, total pressure, and static pressure without
  extrapolation, consumes the outgoing C- handoff, and stops with a typed
  `subsonic_terminal_required` result when the canonical supersonic march
  reaches the centerline normal-shock boundary. The probe verifies upstream
  coverage but remains blocked from physical closure and chain promotion.
- Added a terminal-patch continued-cell adapter. It accepts only a resolved
  current cell whose exact typed handoff is the patch's outgoing C- trace,
  feeds the patch's finite state/pressure field into the next shock march, and
  returns either a fully coupled next-field solve or a typed bounded/normal-
  shock stop. It never appends an open patch or fabricates a subsonic cell;
  the caller-supplied downstream turn remains research-only input.
- Connected the accepted physical field to that continuation seam through a
  bounded terminal-reflection-patch source. The source exposes the exact first
  outgoing C- point, finite state/static-pressure callbacks, explicit spatial
  extents, and no-extrapolation semantics. On the canonical field, the
  generated ambient-attachment bracket does not straddle a next-shock
  solution because the outgoing source starts at ambient pressure, so the
  planner records an ``open-physical-closure`` stop rather than appending a
  false cell. A separate uniform-source probe confirms that the same planner
  maps a verified normal-shock/subsonic arrival to a typed physical
  termination, leaving the unresolved mixed-regime field outside the MOC
  chain.
- Added a first-cell composite assembler. It cancels the shared terminal C+
  seam between the physical shock/ambient strip and the centerline-reflection
  patch, verifies the fitted shock, ambient streamline, centerline, and
  outgoing C- paths are explicit boundary edges, and retains the outgoing
  trace as typed continuation state. Its closed supersonic topology and
  independent geometry measurement are evidence only; physical closure and
  chain promotion remain hard-false.
- The first-cell composite now also exposes a typed ``OPEN_PHYSICAL_CLOSURE``
  chain decision. This lets the planner stop at the explicit unresolved
  boundary without promoting the topology or reporting a generic numerical
  failure.
- Added a physical mixed-regime termination adapter for that probe. Once all
  upstream samples and the normal-shock terminal are verified, it returns an
  explicit `MocChainTerminationDecision` with `physical_termination=true`.
  This stops a supersonic chain without relabeling the unresolved subsonic
  field as a closed MOC cell.
- Added a separate 9/17/33-sample refinement probe for the assembled terminal
  supersonic composite. Each case carries the complete terminal shock edge,
  the matching upstream state/pressure samples, and the same typed
  normal-shock stop; the coarse case retains its declared mesh-scale trace
  tolerance. This is terminal-topology and boundary-coverage evidence only,
  not mixed-regime closure or chain-cell promotion.
- The terminal composite now also carries the independently fitted
  downstream supersonic states along the oblique portion of that shock. The
  subsonic normal-shock endpoint remains a scalar terminal result rather than
  being forced into ``CharacteristicState``; this is a boundary handoff for a
  future mixed-regime solve, not a completed downstream field.
- Added a first-cell-owned terminal closure bridge. It consumes the composite's
  exact outgoing ``C-`` handoff, fits the solver-generated terminal shock, and
  closes the supersonic side of the first cell without importing synthetic
  geometry. Its result is explicitly ``converged_first_cell_supersonic_region``:
  the mixed-regime perimeter remains separate, so physical closure and chain
  promotion stay blocked. The canonical and 9/17/33-sample refinement probes
  now exercise this bridge independently.
- Added an explicit open downstream supersonic patch at that handoff. Each
  oblique post-shock state is continued on a compatible ``C-`` trace to the
  centerline, then the first ``C+``/``C-`` cross-layer and its 119-cell open
  zone are assembled for the canonical 17-sample terminal. The final
  shock-side sample remains above the axis at the typed normal-shock
  interface; this proves a usable downstream patch seam without fabricating a
  subsonic characteristic state, and it remains outside mixed-regime closure
  and chain promotion.
- Added a typed scalar mixed-regime boundary handoff. It validates the open
  supersonic patch, an explicitly closed downstream perimeter, subsonic Mach
  and scalar thermodynamic samples, terminal seam continuity, and
  total-pressure lineage without constructing a subsonic
  ``CharacteristicState``. The canonical report exercises both the missing
  field rejection and a clearly labeled scalar-perimeter contract fixture;
  both retain ``physical_closure_verified=false`` and block chain promotion
  until a real subsonic field/mesh solver replaces the fixture.
- Added a separate downstream-condition validator for that scalar handoff.
  Slip-wall candidates must be flow-tangent on every perimeter segment;
  ambient-pressure free-boundary candidates must also match static pressure.
  The report retains both a deliberately non-tangent rejection and a
  wall-aligned positive contract fixture. A passing condition is still only a
  boundary-condition seam: it remains chain-promotion-blocked and does not
  upgrade the harmonic reference field into a physical plume solve.
  The terminal supersonic field exposes the same check as a convenience
  method, so callers cannot accidentally validate a perimeter against a
  detached shock/patch seam.
- Added a separate solver-backed elliptic subsonic reference field. It accepts
  only a closed scalar perimeter, builds an explicit triangular mesh around an
  interior control point, checks connected topology, isentropic total-pressure
  consistency, harmonic extension, and per-cell velocity-divergence residuals,
  and can attach to a terminal composite as a typed physical termination
  fixture once its downstream condition is also accepted. Its model lineage is
  ``elliptic-isentropic-subsonic-reference``: it is not a supersonic MOC field,
  does not promote a chain cell, and the positive validation case remains a
  synthetic contract fixture until the canonical plume supplies a real
  subsonic perimeter.
- Added a condition-qualified mixed-regime field gate. An elliptic mesh may be
  inspected as ``model_closure_verified`` while remaining physically
  incomplete; terminal attachment and the callback closure adapter now require
  the exact same validated downstream condition. The condition lane includes
  the existing strict slip-wall/free-boundary checks and an explicit
  prescribed-pressure outflow-section condition for pressure-outlet reference
  fixtures, with tangency applicability recorded separately.
- Extended the mixed-regime reference with an explicit radial refinement
  control. ``radial_divisions > 1`` solves a deterministic concentric-ring
  Dirichlet Laplace reference in scalar/log-total-pressure space, checks every
  triangular cell, and records 2/3/4-ring refinement evidence. The result is
  labeled ``elliptic-isentropic-radial-reference`` and remains a declared
  scalar reference model: it does not provide the missing canonical
  subsonic boundary condition, a nonlinear compressible potential solve, or a
  continued supersonic chain handoff.
- Added a typed downstream-perimeter adapter for the reference lane. It binds
  an explicit closed perimeter specification and caller-owned scalar samples
  to the exact terminal/supersonic seam, applies the named downstream
  pressure/tangency condition, and runs the radial reference-field gates in
  one reproducible operation. It rejects changed sample coordinates and never
  repairs missing geometry from the open supersonic zone; accepted results
  remain finite-domain reference/termination fixtures only.
- Exercised the refined reference through the terminal composite's exact seam
  validator at 2/3/4 radial divisions. Each case retains the same normal-shock
  terminal and supersonic patch, produces an explicit physical-stop decision,
  and keeps chain promotion blocked; this is attachment/refinement evidence,
  not canonical mixed-regime acceptance.
- Added a separate solver-owned
  ``solver-owned-quasi-1d-ambient-free-boundary-reference`` planner lane. It
  shoots an effective outlet height from the terminal subsonic total state and
  an explicit ambient-pressure target, generates a finite
  centerline/outlet/free-boundary perimeter, and attaches a scalar radial
  field through the exact terminal-seam closure adapter. Its effective inlet
  height, axial envelope, terminal regularization, and quasi-one-dimensional
  model remain explicit assumptions; the result is a research reference for
  planner/visualization work, not the canonical reflected-MOC free boundary
  and not a next-cell seed.
- Added an explicit scalar downstream control-section seam beside that
  reference. A section carries ordered transverse geometry, subsonic state
  samples, oriented flux, and total-pressure lineage; the validator rejects a
  missing/invalid section without inferring area from the open supersonic
  patch. The section-aware planner may feed the quasi-1D reference only when
  its samples are terminal-equivalent, while a varying section returns a
  typed control-section failure requiring the pending downstream 2-D solve.
  The prescribed mixed-regime mock remains unchanged, and both section paths
  keep physical product claims and supersonic chain promotion blocked.
- Added an independent ``op.moc.mixed-regime-control-section`` measurement.
  It recomputes section placement, transverse geometry, scalar isentropic
  residuals, total-pressure gain, and oriented mass-flux evidence without
  trusting the solver's cached verdict. A passing measurement is still only
  input evidence for the declared reference lane.
- Added an explicit planar downstream handoff adapter for the next fidelity
  boundary. It requires the exact terminal request, an explicit transverse
  control section, and an explicit closed perimeter before invoking a
  callback-owned field solver; returned fields must retain the shock patch,
  perimeter, and named downstream-condition selections. The first-cell
  planner records this handoff without attaching it or issuing a physical
  stop, so even a varying-section callback cannot promote a scalar reference
  mesh into canonical 2-D closure. The returned field now also retains the
  exact consumed control-section object, so a callback cannot satisfy the
  scalar seam while silently ignoring the varying section.
- Added an independent
  ``op.moc.mixed-regime-free-boundary-reference`` measurement. It recomputes
  the scalar height root, generated perimeter geometry, selected pressure and
  tangency condition, radial field layout, and mass-flow residual. It records
  the large two-dimensional velocity-divergence value as a diagnostic rather
  than using it as a gate, making the reference's fidelity boundary explicit.
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
  caustic when the old triangular mesh is reassembled. The continuation now
  reports the disjoint forward frontier intervals and first invalid ray
  explicitly and attempts only the valid local remesh cells; the canonical
  candidate rejects its first self-intersecting patch cell and records the
  bounded crossing point and crossing characteristic edges as a typed
  caustic handoff. It retains the separate valid local patch cell as evidence,
  but reports the combined candidate as disconnected and leaves the bounded
  frontier as a remesh/shock-closure seam, not a promotion; it does not
  fabricate a shock state at the event.
- Added an explicit non-physical chain termination decision for that caustic
  handoff. A continued-cell callback can now stop with the typed
  ``characteristic-caustic`` reason and retain the crossing point, valid
  frontier intervals, failed intervals, and retained local patch count. The
  decision is deliberately not ``physical_termination``; only a future
  new-family or shock solver can resume the chain from this seam.
- The caustic event handoff also retains the solved endpoint states on each
  crossing characteristic edge. The event itself does not interpolate a state
  at the crossing or turn those one-sided samples into a shock; they are input
  evidence for the future entropy/new-family solve.
- Added a bounded caustic shock-formation seed. It reconstructs the two
  one-sided crossing states only along their inferred characteristic family
  (``C-`` in the canonical reflected case), records the flow/static-pressure
  jump, and rejects a seed when the edge geometry or invariant evidence does
  not pass. The seed explicitly has no downstream shock state, entropy jump,
  physical closure, or chain-promotion path.
- Added a local Rankine--Hugoniot candidate probe for that seed. It tests both
  one-sided orientations with the attached-compression solver and records the
  Mach, static-pressure, and total-pressure residuals against the opposite
  edge state. In the canonical case the forward compression is mathematically
  attached but does not match the opposite one-sided state, while the reverse
  orientation has no positive compression turn; the typed result therefore
  rejects both candidates and keeps chain promotion blocked.
- Added an explicit invariant-conditioned local caustic shock bridge. It
  selects one one-sided upstream state and solves an attached compression
  against a caller-supplied downstream characteristic invariant, retaining
  strict total-pressure-loss evidence and a local shock angle. The canonical
  target now produces a local compatibility state without treating the
  opposite one-sided reconstruction as downstream. This remains a local
  shock-state result only: shock-curve fitting, downstream characteristic
  field closure, mixed-regime closure, and chain promotion stay blocked.
- Added a one-sided caustic new-family restart primitive. For each crossing
  edge it reflects the selected C- anchor to the centerline, marches a
  pressure-matched/tangent C+ boundary, and independently checks pressure,
  tangent, geometry, and forward-progress residuals. Both canonical
  orientations produce six finite boundary samples and a connected
  anchor-wedge plus ten-step family band. The old triangular interior assembly is
  retained as an explicit geometry failure, so this is a typed open remesh/
  shock handoff rather than a fabricated shock state or physical chain cell.
  The band has a bounded state/pressure sampler, and a production shock-band
  seam now consumes both canonical orientations from the explicit input edge:
  it refits the supersonic shock samples, assembles a 27-cell open downstream
  characteristic zone, and records the typed subsonic centerline terminal.
  The zone is still an open mixed-regime handoff, so physical first-cell
  closure and chain promotion remain pending.
- Added a strict two-sided caustic upstream bridge. It composes the converged
  old-family strip and restarted-family band only where one selected field
  covers the point, rejects ambiguous overlap, preserves explicit side
  selection, and records gaps without averaging or extrapolation.
- Added ordinary and invariant-conditioned bridge shock/planner adapters.
  Both preserve the exact prior chain handoff and report bounded upstream
  coverage, but remain one-step research diagnostics with physical closure
  and production chain promotion disabled.
- Added an explicit caustic shock-remesh preparation contract. It binds a
  selected one-sided seed edge, its exact event point and static pressure, and
  a caller-selected downstream invariant to the local entropy-admissible
  bridge. The request enumerates the future solver outputs—shock curve,
  carried upstream/downstream states and pressure loss, post-shock field, and
  exact incoming handoff—and exposes a typed ``CHARACTERISTIC_CAUSTIC`` stop
  until those outputs are actually solved. This is solver-boundary and
  planner/validation evidence; it does not create a shock curve or promote a
  chain cell.
- Hardened the caustic restart handoff for continued-chain planning. The
  selected one-sided seed edge is now retained as an exact anchor and an
  anchor wedge is included in the family-band mesh. The band proves that its
  input edge is downstream of that anchor, and restart reports a typed
  band-assembly failure instead of
  claiming an open-boundary restart when the band cannot be built. The
  restart also exposes a non-physical ``characteristic-caustic`` chain stop
  with explicit ``old_family_bridge_verified=false`` and
  ``shock_entropy_closure_verified=false`` diagnostics. This closes the
  state/geometry bookkeeping seam only; it does not close the physical first
  cell or promote a planner/mock cell.
- Added a terminal-to-mixed-regime handoff adapter. The terminal composite and
  caustic-band result now route caller-supplied scalar subsonic perimeter data
  through the mixed-regime validator, while an empty/open perimeter returns a
  typed subsonic-field failure. The terminal composite also exposes an
  explicit non-physical `OPEN_PHYSICAL_CLOSURE` chain decision until a real
  mixed-regime field is attached; no boundary point is inferred from the open
  zone.
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
   upstream-field coupling and external acceptance gates remain open. The
   solver-generated terminal also now assembles the oblique downstream
  supersonic patch through its first cross-layer, but that patch ends at the
  typed normal-shock interface and does not satisfy the mixed-regime closure
  gate. The caustic-band terminal seam now supplies the same open-zone evidence
  from the restarted upstream field at 5/7/9/11 shock samples; the independent
  measurement operator rejects the unresolved endpoint as expected.
  The open zone now retains a bounded supersonic state/pressure sampler for
  downstream solver probes; this interface does not extend the domain or
  change its open-closure status.
  The ambient-strip validation now also carries the final ambient ``C-``
  sample to a geometric centerline candidate and reports the carried static-
  pressure residual. The canonical candidate reaches ``y=0`` but misses
  ambient pressure by about 15 percent, so the result is a solver-owned
  boundary residual—not a physical closure or a chain-promotion input.
  The next bounded global shoot now makes the missing degree of freedom
  explicit: it varies a caller-owned upstream attachment coordinate, solves
  the local ambient attachment at each trial, and bisects the resulting axis
  pressure residual. The canonical uniform field correctly returns a typed
  no-bracket result; a nonuniform research fixture exercises the converged
  scalar path, while both paths remain outside physical closure and chain
  promotion until the appended ambient-to-axis tangency gate and the
  downstream characteristic/mixed-regime field are solved.

### MOC-3 — Re-solved continued cells

Use the state-carrying callback behind
`continue_post_shock_characteristic_chain` as the local MOC solver boundary:

1. take the previous cell's typed carried boundary and total-pressure field;
   for the shock-seeded field this is a composite post-shock perimeter, while
   a separately solved characteristic handoff remains a distinct boundary
   kind;
2. propagate that carried boundary to the next local shock boundary; an axial
   section is a separate boundary kind and must not be inferred from it;
3. solve the next compression/expansion boundary and post-shock field;
4. record the exact incoming boundary in `incoming_handoff`, return a new field
   and cell with `resolved-planar-moc` fidelity, or return a structured
   validity/termination result; the adapter verifies that the consumed
   boundary is unchanged and that upstream total pressure does not reset
   upward;
5. stop on physical model limits, not on an arbitrary count, while retaining
   count and axial distance as safety limits. A physical endpoint must be
   returned as an explicit `MocChainTerminationDecision`; `None` and safety
   truncation remain non-physical.

The existing reduced-order `solve_shock_train` remains the separate Level B
implementation. It must not be used as this callback.

The validation script's planner mock is only an executable contract fixture:
it supplies the next shock curve directly, then runs that curve through the
real branch-checked attached-shock fitter so handoff, pressure-loss, and
fidelity checks exercise a physically meaningful local seam. Its prescribed
boundary advances with each planned cell, and the report checks the carried
total-pressure maxima without calling that bookkeeping a physical endpoint.
A separate generated-chain reference now runs the same continuation adapter
with solver-generated boundaries, but its upstream field and linear
downstream-turn law remain explicit callbacks. Neither is evidence for
production automatic shock placement, physical termination, or external
validation.

The independent planner-trace measurement is applied to both three-cell
traces and to the field-coupled one-cell terminal reference. It reconstructs
the returned chain data and exact handoff fingerprints instead of accepting
the planner's own summary flags. A passing audit verifies orchestration and
fidelity isolation only; it does not turn a prescribed boundary, explicit
turn law, or named terminal model into canonical free-boundary evidence.

The continuation adapter also exposes a strict upstream-coupled mode. It
rejects the prescribed planner seed before callback execution and requires
each generated field to carry the fitted upstream shock state/pressure
samples. The canonical marcher separately reports
`subsonic_terminal_required` when a zero-turn/normal-shock endpoint would need
to leave the supersonic MOC lane. The companion continued-cell adapter can
now return that verified terminal as a physical chain-stop decision, while
the ordinary generated-cell path remains available for nonterminal cells.

The constant-`K+` source-strip continuation is a separate upstream-only
diagnostic fixture: it tests how a continued shock probe consumes a growing
characteristic domain, but it must not be promoted into a resolved chain cell
until the shock boundary and post-shock field are solved from the coupled
reflected MOC state/pressure field. A terminal source window is allowed as a
domain-bounded research input only when its omitted prefix and full-strip
status are retained alongside it.

The source-strip sequence planner now makes the later-cell contract explicit:
the first shock uses the supplied continuation, and every subsequent shock
must receive a distinct continuation result and distinct strip object from
the upstream solver. A missing, nonconverged, caustic, or reused source domain
is a typed non-physical upstream boundary; the prior resolved cell is retained
and no source field is extrapolated or reused as a downstream chain field.
The current validation case exercises the canonical caustic as a one-cell
sequence stop, while the planner contract tests cover successive fresh-domain
callbacks separately from the numerical source/shock solve.

The invariant-conditioned shock solver is now an explicit solver boundary for
this work: it can reject an unbracketed or domain-limited closure, but it does
not invent a downstream physical law. A converged invariant-conditioned field
is therefore still research evidence until the selected invariant, case
domain, and independent measurements are validated.

The field-coupled invariant adapter now applies that same condition to a
continued cell: it consumes the prior field's exact perimeter, samples only
inside that finite field, and re-solves the next attached shock and closed
post-shock characteristic field. A successful cell carries the prior state and
total-pressure handoff; an invariant miss, upstream-domain miss, solver
failure, or verified normal-shock endpoint remains typed. This is a solver
boundary for continued-cell experiments, not a production next-cell shock
placement or a canonical downstream closure.

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
continued chain. The ambient-pressure field planner now repeats that contract
for later cells: only an accepted field replaces the current upstream field,
and every failed attempt leaves the prior cell and handoff unchanged.

The ambient-closed physical-field planner is the stricter continuation lane
for the eventual production solver. Its callback receives the prior closed
cell's centerline trace and must return a newly assembled physical field that
records the exact incoming state/total-pressure samples. The adapter promotes
that field only after the immutable field-evidence audit, ambient perimeter,
characteristic topology, and optional upstream shock-coupling checks pass. The
current tests use a clearly marked manufactured field only to audit the
handoff and multi-cell planner contract; the canonical reflected field still
has not passed the physical closure gate.

The first-cell terminal now has a matching planner/audit wrapper. It can submit
the exact normal-shock scalar seam to the prescribed mixed-regime closure mock
and retain the resulting typed physical-stop decision, while keeping terminal
closure separate from supersonic next-cell promotion. With no downstream
solver, the same wrapper preserves the open-physical-closure decision. The
mock's local closure is useful for planner and report plumbing only; it does
not close the canonical free boundary or authorize a product claim.

The caustic-family-band planner is a separate one-step research path for the
new-family branch. It carries the current cell's exact post-shock perimeter,
solves the next attached shock from the bounded band state/pressure field,
and records the resulting open post-shock zone and normal-shock terminal.
Because the mixed-regime perimeter is still unsolved, the planner returns
``OPEN_PHYSICAL_CLOSURE`` with ``production_claim_allowed=false`` and refuses
to append the open result. A later cell requires a new solved family or a
closed downstream field.

The open post-shock zone now has the same bounded next-shock coupling seam:
it can be queried for a candidate continuation and returns a typed
upstream-field boundary or normal-shock terminal. It remains an open solver
interface, so a successful callback does not by itself authorize chain-cell
promotion.
The matching one-step planner wrapper now records this seam in the same
handoff audit used by the other research planners. A valid-prefix shock march
cannot be misreported as a generic solver failure: the first uncovered sample
is retained and the planner returns a non-physical upstream-field stop. A
later cell requires a newly solved bounded field.

The bracketed ambient-attachment adapter removes one caller-supplied boundary
coordinate: it solves the outer shock turn against the local post-shock
static-pressure/ambient condition before generating the physical shock/ambient
strip. This is a stronger attachment seam than the fixed-angle reference, but
it intentionally leaves the downstream terminal trace open and labels the
linear-to-centerline law as a reference. A centerline reflection, downstream
compression/shock fit, and mixed-regime/perimeter closure are still required
before a first cell or continued chain cell can be accepted.

The staged shock-cell transition now composes those boundaries into one
typed research result. It can carry the reflected outgoing ``C-`` front into
the next-shock coupling probe and, when the supersonic lane reaches the
verified normal-shock terminal, return a physical chain-stop decision. That
stop is narrower than a closed cell: the subsonic downstream field and the
full mixed-regime perimeter remain outside the planar supersonic-MOC lane.

The terminal-reflection-patch continued-cell adapter now makes that handoff
usable by the generic chain seam. It requires a resolved prior cell, a
`terminal-characteristic-trace` boundary, and exact equality between the
prior boundary, the patch's outgoing ``C-`` trace, and the returned field's
`incoming_handoff`. A complete nonterminal field can therefore be returned as
the next local solver result; the canonical case instead reaches the typed
normal-shock stop. The adapter is a solver-backed research seam, not evidence
that the patch's caller-supplied downstream turn is a production boundary
condition.

The first-cell composite assembler now joins the strip and reflection patch
at their shared terminal ``C+`` edge. The union is a single connected mesh
with explicit shock, ambient, centerline, and outgoing ``C-`` boundary paths;
the independent shock-cell measurement operator checks its area and supplied
shock loss. This closes the local supersonic topology while preserving the
separate claim that the reflected upstream field, downstream boundary law,
and external validation still have to pass before the first cell is promoted.

The terminal-compression candidate is the next local boundary primitive after
the open shock/ambient strip. It is intentionally weaker than a first-cell
closure: it solves the endpoint-to-centerline compression only. The next
solver must supply the upstream state along that compression and assemble the
compatible characteristic patch between the incoming terminal C+ trace and
the new boundary before a resolved cell can be returned.

The terminal-trace centerline reflection patch now supplies that compatible
patch as an explicit open transition and carries its outgoing C- front. This
is a real state-carrying continuation seam, not a closed cell: the next
solver must fit the physical compression/shock boundary against that front
and close the remaining perimeter before using the chain promotion adapter.

The terminal-patch shock probe now consumes that outgoing front through a
domain-bounded state/pressure sampler. The canonical march covers all 17
requested upstream samples before stopping at the typed subsonic normal-shock
terminal. That is a mixed-regime boundary decision, not a failed attempt to
hide missing upstream data; a future solver must add the downstream
mixed-regime field and physical perimeter gate before promotion.

When that terminal is verified, the probe can now return a typed physical
chain-stop decision. The decision is deliberately narrower than cell closure:
it records the normal-shock model and downstream scalar state, while the
subsonic field remains outside the supersonic MOC chain.

The transition now also assembles a terminal supersonic composite field by
clipping the validated reflected characteristic patch to the upstream side
of the solver-generated shock and revalidating the union with the physical
shock/ambient strip. This closes the one-perimeter supersonic topology and
preserves inherited characteristic-cell evidence without inventing a
post-shock subsonic ``CharacteristicState``. The field therefore reports
``supersonic_region_closed`` while keeping ``mixed_regime_field_complete``
and ``physical_closure_verified`` false; it is a geometry/topology checkpoint,
not a promoted first cell.
The checkpoint also requires the terminal-shock boundary itself to appear as
a complete one-perimeter mesh edge set and carries the normal-shock endpoint
upstream state/pressure sample. A bounded mesh without that explicit shock
coverage is rejected as geometry failure.

The same seam has 9/17/33-sample refinement evidence. The reflected patch
axis endpoint converges toward the 33-sample result, every resolution covers
its requested upstream shock samples, and every case reaches the same typed
mixed-regime gate. The assembled supersonic terminal composite now has a
separate refinement record: its terminal-shock edge coverage and upstream
state/pressure carry pass at all three resolutions. This establishes numerical
behavior of the open transition and its supersonic-side topology, not
acceptance of a physical first cell.
The terminal probe is branch-aware as well: a strong attached branch that
reaches a subsonic downstream state earlier is retained as a typed scalar
boundary with its shock location and total-pressure loss. It is deliberately
not represented as a ``CharacteristicState`` and cannot be mistaken for the
weak branch's normal-shock termination. The validation artifact records both
paths so branch selection remains a fidelity decision rather than a hidden
solver flag.

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

The marched attached-shock reference, terminal reflection transition, and
the generated five-cell chain now have 9/17/33-sample refinement evidence.
The chain operator independently confirms stable cell count, exact handoff
links, pressure-loss lineage, typed non-physical truncation, and bounded
geometry deltas. This is numerical diagnostic evidence only until the
upstream reflected field and downstream boundary condition are solved
together.

Refinement evidence is diagnostic until the physical closure and external
measurement comparison both pass.

### MOC-5 — Independent validation

Use a disjoint case and an explicit measurement operator. The local
`op.moc.shock-cell-geometry`, `op.moc.shock-cell-chain`, and
`op.moc.shock-cell-chain-refinement` operators now provide the
geometry/topology and numerical-sensitivity extraction layer for solver
fields and planner fixtures, including optional shock total-pressure loss.
Keep the current
CJ/UEJ component comparison as supporting, not accepted, evidence until the
external measurement-space mapping, uncertainty/provenance, and closure
domain are complete. The operator must not infer physical shock cells from a
centerline pressure trace or repair an open mesh.

The `op.moc.terminal-closure` operator now measures the terminal lane
separately from the terminal solver. It rechecks the closed supersonic mesh,
sampled terminal-shock coverage and total-pressure loss, exact mixed-regime
seam, explicit downstream condition, and independently recomputed reference
field residuals. With no mixed-regime closure it reports an open physical
boundary; with the prescribed perimeter fixture it reports a terminal
measurement and physical-stop diagnostic while retaining
`chain_promotion_blocked=true` and `claim_status=not_accepted`. This is
measurement evidence for the fidelity boundary, not canonical plume
validation.

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
- The fresh-domain source-strip sequence planner now enforces the later-cell
  boundary, but it does not invent the next upstream source solve. The
  canonical sequence therefore stops at the same caustic until a coupled
  remesher/new-family solver can supply a distinct bounded field for the next
  shock; the sequence API is continuation plumbing, not automatic chain
  closure.
- The canonical reflected continuation now identifies that caustic as two
  disjoint forward intervals (`0..2` and `8..9`) for the new axis row. Those
  intervals cannot be stitched into one triangular strip. The first local
  polygon crossing is now measured at approximately
  ``(0.6584202, 0.0569707)`` in the canonical case, but that geometric event
  carries no downstream state; a physical remesher/new-family shock solver
  must bridge or explicitly stop the characteristic family before the
  upstream field can feed a production shock fit. The chain layer now records
  this as a non-physical ``characteristic-caustic`` stop, so a numerical
  boundary cannot be mistaken for a physical plume termination.
  The bounded seed now supplies two one-sided ``C-`` states at that crossing;
  the local Rankine--Hugoniot probe rejects both orientations (the forward
  candidate has approximately ``-6.2%`` Mach and ``+32.8%`` static-pressure
  residuals), so a coupled shock/new-family solve is still required. An
  explicit-invariant local bridge can now solve an entropy-admissible state
  for a caller-selected downstream ``K+`` target, but it deliberately does
  not claim a shock curve, downstream field, or physical first-cell closure.
  The new-family restart can now advance either one-sided anchor to a
  pressure-matched/tangent boundary with six finite samples and residuals below
  tolerance, then carry those traces through a connected anchor-wedge plus
  ten-step two-triangle-per-step open band. Its original triangular cross-ray assembly
  still fails at the first non-forward node, and the band has no shock or
  entropy closure; a physically fitted shock must still bridge the caustic
  before upstream coupling is complete. The weak-branch forward-envelope gate
  now measures that finite-band reachability seam explicitly: both canonical
  anchor orientations leave the restarted band before reaching the centerline,
  so it remains a remeshing diagnostic rather than a physical shock result. The
  bounded band shock seam now
  consumes the band samples through a solver-generated open post-shock zone
  and typed subsonic terminal, and the one-step chain planner carries the exact
  prior perimeter into that solve. It still returns a non-physical
  ``OPEN_PHYSICAL_CLOSURE`` stop and does not promote a chain cell.
- The selected seed-to-band anchor is now checked exactly and a family-band
  assembly failure propagates to the parent restart status. The resulting
  chain decision remains a non-physical characteristic-caustic stop until an
  old-family bridge and shock/entropy closure are solved; this is handoff
  bookkeeping, not physical first-cell closure.
- Ambient-pressure closure now reports upstream shock-state coupling as a
  separate gate. The research adapter can retain a locally ambient-closed
  field, but its strict coupled chain adapter refuses promotion until the
  upstream states are carried through the accepted shock path as well.
  The repeated ambient-pressure field planner enforces the same rule between
  cells; the canonical bounded post-shock seed still stops at its finite field
  boundary before a second cell can be accepted.
- The trace-extension reference uses a constant terminal boundary trace; it is
  useful for deterministic plumbing and refinement, but it is not the physical
  upstream characteristic strip.
- The shock-seeded field's remaining polygon perimeter is now explicitly
  measurable, but the prescribed fixture fails the ambient-pressure and
  streamline-tangency gate. A coupled solver still has to replace that
  internal-characteristic edge with a solved free boundary before a cell can
  be accepted physically. The new shock-sourced ambient strip demonstrates the
  corrected source-family orientation and carries the physical boundary
  conditions, and the bracketed attachment seam now solves the outer shock
  turn from ambient pressure. Its terminal trace still needs an
  axis/centerline closure; the linear-to-centerline law used to generate this
  open strip remains a named reference, not a physical first-cell closure.
  The staged transition can now reflect that trace and carry a next-shock
  handoff to a typed normal-shock stop and close the supersonic-side composite
  topology, but this is still termination/topology evidence rather than a
  closed mixed-regime cell.
  The scalar shoot continues to demonstrate the old internal-characteristic
  failure without weakening the gate.
- The ambient-axis physical-field bridge now makes the promotion boundary
  executable: the nonuniform reference reaches an axis-pressure root but is
  rejected before field assembly because its appended ambient-to-axis trace
  fails tangency. The uniform canonical probe stops earlier at the
  attachment-coordinate bracket. A passing boundary would still need the
  immutable physical-field, state-sampling, upstream-coupling, refinement,
  and external-validation gates before it could support continued cells.
- The canonical marched shock now classifies a zero-turn/normal-shock endpoint
  as `subsonic_terminal_required`, carries a verified typed normal-shock
  terminal diagnostic, and can return a physical chain-stop decision after
  full upstream coverage. That is an explicit supersonic-MOC validity
  boundary, not a reason to force a bracket or relabel the endpoint as a
  converged supersonic cell. The new scalar mixed-regime handoff and separate
  elliptic reference field validate the seam, mesh, and residual bookkeeping,
  but the canonical case still lacks a physically solved subsonic perimeter;
  the fixture attachment therefore cannot be used as canonical closure.
- The mixed-regime reference now has a multi-ring mesh/refinement path, but its
  general perimeter adapter still consumes a caller-supplied closed perimeter
  and uses a declared harmonic scalar reference rather than a coupled
  nonlinear subsonic flow solve. A separate solver-owned quasi-1D reference
  can generate a finite ambient envelope for planner/visualization testing,
  but its explicit effective area model is not the canonical plume boundary.
  Both lanes remain contract evidence only; an unqualified field remains
  model-only, and the canonical terminal still has no physical downstream
  perimeter or chain-promotion path.
  The typed downstream-perimeter adapter now makes that caller-owned boundary
  and sample model explicit and reproducible, but it does not change the
  canonical status or promote the reference field into the supersonic chain.
  The first-cell result also accepts an attached closure only through an exact
  request-matching seam before exposing its typed physical stop; this keeps
  terminal attachment auditable without making the mixed-regime result a
  continued supersonic cell.
- The compressible potential reference now supplies a nonlinear conservative
  field solve for an explicit perimeter, but it is still a finite-domain
  scalar reference. It requires uniform isentropic total pressure and a
  single-valued boundary potential, does not solve the free-boundary geometry,
  and does not produce subsonic ``CharacteristicState`` values for chain
  continuation. The canonical terminal therefore remains physically open and
  chain promotion remains blocked until a coupled downstream perimeter and
  compatible MOC/field handoff are solved.
- The solver-owned quasi-1D free-boundary reference now supplies a generated
  finite perimeter and an independently measured scalar radial field. Its
  returned physical-closure flag is local to that declared model; it remains
  ``production_claim_allowed=false`` and ``chain_promotion_blocked=true``.
  The canonical reflected-MOC downstream field still needs a genuine
  coupled free-boundary solve, with the reference's effective inlet height and
  terminal regularization replaced by geometry and flux obtained from the
  upstream solution.
- The control-section adapter now makes that missing geometry/flux input
  explicit. A terminal-equivalent scalar section can drive the bounded
  quasi-1D reference for planner and visualization tests; a state-varying
  section is retained as a typed input failure rather than projected into a
  scalar height. The remaining promotion gate is a canonical reflected-MOC
  downstream section/field solve with independent measurements, after which
  only a separately solved supersonic next-cell handoff may continue the
  shock-cell chain.
- The terminal-boundary graph audit confirms that the canonical terminal's
  four solver-owned supersonic paths join with zero reported residual, while
  no downstream path or physical downstream condition is supplied. A future
  mixed-regime solve must provide that path and its state/flux boundary data;
  the geometry-only audit cannot promote the terminal or continue the chain.
- The invariant-conditioned shock shoot currently records a canonical
  no-bracket result; a selected constant downstream invariant is not yet an
  accepted physical free-boundary condition. The field-coupled invariant
  adapter now supplies a bounded research next-cell shock fit when a caller
  provides that invariant, but no production solver yet supplies automatic
  next-cell shock placement. The state-carrying chain adapters therefore
  require a converged explicit research solve and do not use the reduced-order
  chain.
- A bounded caustic upstream bridge now composes the converged old-family strip
  and one-sided restarted-family band without averaging or extrapolation. It
  accepts unique domain coverage, rejects overlaps unless a caller explicitly
  selects a side, and records the canonical gap as a typed upstream boundary.
  The bridge-backed shock/planner seam carries the exact prior handoff but
  remains a one-step research diagnostic: it does not solve the missing
  caustic remesh, entropy branch, or downstream mixed-regime closure, and it
  cannot promote a chain cell. A candidate attached shock started at the
  terminal old-family boundary now records the first downstream point that
  leaves both one-sided fields; the planner maps that exact point to an
  ``UPSTREAM_FIELD_BOUNDARY`` stop instead of treating the retained one-point
  prefix as a continued cell. This is the required corridor evidence for the
  next physical remesher, not a substitute for one.
- The remesh-preparation contract now packages the exact crossing point,
  selected one-sided state/pressure, local invariant-conditioned bridge, and
  required shock/new-family outputs. A ready request is still a
  non-physical ``characteristic-caustic`` stop; it is an auditable input to a
  future coupled remesher, not evidence that the remesher or a continued cell
  already exists.
- The coupled caustic remesher now executes the bounded shock/new-family solve
  and verifies its event, local bridge, upstream carry, shock curve, and
  downstream-field gates. Its planner records the exact prior perimeter and
  remains one-step/non-physical by policy. The canonical first-cell
  downstream perimeter is still missing, so this remesh result cannot yet
  promote a continued cell.
- The remesh also has a strict bridge-fed entry point. It samples the exact
  old-family/restarted-family seam at the event and along the candidate shock,
  returns the first uncovered point as ``UPSTREAM_FIELD_FAILURE``, and retains
  the independent bridge audit in the result. This makes the canonical
  caustic corridor a real solver input boundary rather than a callback-owned
  assumption; it still does not solve the missing physical downstream
  closure.
- ``MocBoundedUpstreamFieldSource.from_caustic_upstream_bridge`` now exposes
  the converged old-family/restarted-family bridge through the generic
  repeated-cell source contract. The adapter preserves the bridge's one-sided
  selection and domain gaps, reports the union of its finite mesh extents, and
  keeps ``upstream_coupling_verified`` false. It is therefore usable as a
  solver-owned research input, but cannot promote the open caustic band to a
  shock cell or authorize a production claim.
- Added a separate solver-owned centerline-conditioned upstream Cauchy-remesh
  lane. It consumes an explicit centerline ``C+`` trace and outer/pre-shock
  ``C-`` trace, checks the exact selected one-sided caustic state/pressure seam,
  and assembles a bounded characteristic source strip without generating or
  extrapolating the missing outer trace. Its one-step shock-chain adapter
  preserves the first uncovered upstream sample as a typed
  ``UPSTREAM_FIELD_BOUNDARY`` stop; the source field remains open and the
  canonical outer trace, entropy/shock closure, and chain promotion remain
  pending.
- Added a separate solver-owned simple-wave terminal lane. It builds a
  constant-invariant upstream trace from the exact selected caustic state,
  marches an attached shock against an explicit turn profile, fits the
  retained supersonic prefix, assembles its open post-shock characteristic
  zone, and records the typed normal-shock endpoint. The lane reports exact
  event/bridge/pressure gates and never inserts the subsonic endpoint into the
  characteristic network. Its one-step planner records the incoming perimeter
  and returns ``OPEN_PHYSICAL_CLOSURE`` without appending a chain cell; the
  simple-wave trace is a solver boundary condition, not the physical caustic
  remesh or mixed-regime closure still required for promotion.
- Added an independent ``op.moc.caustic-remesh`` measurement operator. It
  re-fits the carried shock boundary, recomputes total-pressure loss, checks
  the returned characteristic mesh/topology and state-carry residuals,
  independently compares the returned incoming handoff to the exact prior
  chain boundary when supplied, and re-samples an optional strict
  old/restarted-family bridge. The canonical
  callback-owned remesh passes only its bounded research gates; the strict
  bridge measurement preserves the first selected-side domain gap. Both
  results remain ``not_accepted`` and chain promotion stays blocked.
- Planner steps now record both sides of each continued-cell handoff: the
  incoming fingerprint, the returned cell/field boundary kind and pressure
  range, and the outgoing fingerprint. Multi-step mock and solver-generated
  references must prove every later callback consumed the exact prior result
  handoff; this is chain bookkeeping evidence, not free-boundary validation.
- The prescribed post-shock planner mock now reports a separate claim-fidelity
  ceiling: its local shock fit and post-shock characteristic field are
  solver-backed, but the shock ordinates and downstream angles remain
  prescribed. Increasing the fixture length therefore exercises arbitrary
  handoff depth without changing ``free_boundary_verified=false`` or allowing
  physical chain promotion. The standalone primitive artifact exercises a
  five-cell instance; the default three-cell fixture remains the compact unit
  test case. The solver-generated reference now exercises the same five-cell
  depth, with its local resolved-planar-MOC geometry ceiling reported
  separately from its explicit-reference/free-boundary boundary.
- Added an independent ``op.moc.chain-planner`` audit for continued-cell
  traces. It reconstructs each cell's topology, sequence position, exact
  state/total-pressure handoff, returned-cell correspondence, typed terminal
  decision, and resolved-planar-MOC fidelity from the planner data. The
  three-cell prescribed mock and solver-generated reference both pass this
  independent trace audit, while the field-coupled one-cell terminal audit
  separately preserves its typed physical-stop result. All remain explicitly
  ``not_accepted`` at the product boundary; the operator does not trust the
  planner's own handoff verdict or promote a chain.
- Hardened the continued post-shock field handoff with a fresh downstream
  domain gate. A returned field must place every reported mesh, shock, and
  carried continuation point strictly after the current cell; a valid old
  field with a new endpoint is now rejected as a solver error rather than
  appended as a fake continued cell. The chain endpoint remains solver
  bookkeeping because an oblique centerline closure can extend beyond the
  requested axial step.
- Extended the independent shock-cell-chain measurement with the matching
  ``fresh_domain_verified`` gate. It reports touching or reused axial domains
  as a chain-measurement failure instead of allowing topology and handoff
  identity alone to stand in for continued-cell geometry.
- The same independent planner audit is now attached to every typed-stop
  continuation probe in the validation report: ambient-pressure field,
  source-strip/fresh-domain, bounded post-shock-zone, terminal reflection,
  caustic remesh/simple-wave, caustic-family-band, invariant, and bridge-fed
  lanes. Each probe must independently reproduce its returned-to-incoming
  handoff, typed termination, and fidelity isolation. This broadens the
  bookkeeping evidence for continued shock-cell chains without turning any
  numerical or open-closure stop into a physical product claim.
- The independent planner audit now also checks each continued cell's axial
  domain freshness against the shared interface. It reports a typed
  ``domain_failure`` for a reused or non-advancing mesh, non-contiguous cell
  interval, or upstream-reused carried boundary, and serializes
  ``domain_freshness_verified`` with the other planner checks. This keeps a
  passing handoff trace from being mistaken for a genuinely re-solved cell.
- The independent shock-cell measurement operators now pass local geometry,
  topology, and supplied shock-loss extraction for the current fixtures, but
  they do not provide external observations, uncertainty, or a provider-bound
  measurement-space mapping. Their successful status must not be read as
  physical MOC closure or validation acceptance.
- The generic state-carrying chain contract now checks the returned cell mesh
  against the shared axial interface before accepting a candidate. Shared
  interface vertices remain legal, but a candidate whose mesh starts
  upstream, or never advances downstream, is rejected. State-carrying
  boundaries receive the matching upstream-domain check. This closes a
  planner-level relabeling hole independently of the stricter post-shock
  field freshness gate; it does not loosen the physical-closure boundary.
  Chain reports now expose each cell's bookkeeping interval alongside the
  measured mesh and carried-boundary axial extents so a continued-cell trace
  can be audited without reconstructing geometry from the solver objects.
- Added a standard bounded report to the shock-seeded post-shock field. It
  exposes mesh axial/transverse extents, shock/centerline/continuation
  boundaries, topology and residual summaries, pressure-loss lineage, and
  incoming-handoff counts. This replaces ad hoc field serialization in
  planner/validation consumers while keeping the field's finite-domain and
  research-only closure boundary explicit.
- Threaded that bounded field report through the solver-generated free-boundary
  result, so a higher-level shock/remesh report carries the same geometry and
  handoff data instead of exposing only `field_status`. This is an inspection
  API improvement; it does not change the solver's closure or promotion gates.
- Tightened the caustic-remesh research handoff so its bounded downstream field
  is exposed only when the returned field has state samples and finite axial
  and transverse extents. A converged status alone can no longer make an
  unsampleable field available to continued-cell probes.
- Retained shock/centerline state and total-pressure samples in the validated
  closed-field result. Its chain adapter now emits a typed centerline handoff
  and requires bounded state-sampling evidence, so a validated field can seed
  continued-cell bookkeeping without dropping the downstream boundary.
- Added bounded reflected-zone capability reporting: the open reflected mesh
  now exposes its finite extents, cell-kind counts, and whether its state and
  pressure samplers are actually usable. Reflected-zone shock and ambient
  closure adapters stop with a typed upstream-field failure when the caller
  provides geometry without total-pressure lineage; they no longer let a
  geometry-only zone reach a pressure callback.
- The reflected-zone report now carries the same explicit promotion flags as
  the other MOC lanes: its topological perimeter can be closed while
  ``physical_closure_verified=false`` and ``chain_promotion_blocked=true``.
  This keeps the planner and validation artifact from interpreting an open
  reflected lattice as a completed shock cell.
- Routed the standalone reflected-zone artifact through that canonical report
  and added a regression for the geometry-only handoff. The canonical case
  still reports a pressure-capable open domain, while the continued shock-cell
  planner remains a five-cell research fixture with exact handoff auditing and
  no production claim.
- Extended the prescribed continued-chain fixture with an explicit optional
  per-cell shock-geometry scale. Scaling the shock ordinates and their sample
  spacing together preserves the local fitted tangent while allowing the
  planner/visualization artifact to show changing cell height across a longer
  chain. The option is intentionally confined to the prescribed-boundary
  diagnostic lane; its fidelity ceiling and promotion block remain unchanged.
- The same fixture now exposes its deterministic scale schedule and resamples
  the full prior typed total-pressure handoff across each prescribed shock
  sample. Continued-cell reports therefore retain pressure variation and
  pressure-loss ordering instead of flattening a handoff to its maximum;
  normalized-index resampling is explicitly a mock policy and is not a
  physical upstream-to-shock mapping.
- The recovered validation archive is not a substitute for the missing
  provider-bound measurement/operator bindings.
- Continued-cell chain reports now expose per-cell transverse extents and a
  structured boundary-geometry/pressure-trace payload. The payload preserves
  incoming handoff, shock, centerline, and (where applicable) ambient paths so
  planner and visualization consumers can inspect expansion and pressure loss
  without reaching into solver internals. These traces are evidence surfaces,
  not an elevation of the chain's fidelity or closure claim.
- Added an independent continued-chain refinement operator. It remeasures
  coarse/medium/fine chain observations, checks stable cell count and
  per-cell spacing, compares axial extent/shock-spacing/mesh-area deltas,
  verifies strict shock total-pressure loss, and audits a planner's typed
  termination across resolutions. The generated 9/17/33-sample five-cell
  reference passes those numerical checks, while the result remains
  ``not_accepted`` research evidence and does not establish physical closure.
- The solver-generated continued-chain reference now carries the complete
  prior total-pressure trace into each local shock solve using an explicit
  normalized shock-height interpolation policy. This removes the old
  max-pressure flattening while keeping the uniform upstream-state and
  reference-turn assumptions visible; reflected-field coupling and canonical
  free-boundary closure remain pending.
- The prescribed planner mock now accepts an explicit per-cell geometry
  schedule for continued cells: axial pitch, shock-start offset, and shock
  height scale can vary independently across a chain. The standalone artifact
  exercises a five-cell expanding schedule, while the mock still routes every
  shock through the branch-checked attached-shock fit and remains capped at
  ``prescribed-boundary-diagnostic`` fidelity.
- Added a solver-owned bounded caustic upstream continuation controller. It
  audits both one-sided new-family restarts, refuses to choose a branch when
  none is selected, and for an explicit branch exposes an exact event
  state/pressure seam through a bounded old-family/restarted-family bridge.
  The bridge is usable for research-only upstream sampling, but shock-curve
  physics, downstream mixed-regime closure, and continued-cell promotion
  remain blocked.
- Tightened the continued caustic-remesh sequence contract so each later
  remesh request must carry the exact prior state/total-pressure handoff it
  was asked to continue. The planner retains the handoff-seam result in its
  attempt audit before checking remesh/source-strip freshness; a missing or
  mismatched provenance record is a typed upstream-field boundary rather than
  an inferred coupling.
- Added the corresponding validation-report probe. It drives a three-cell
  research-only sequence with solver-assembled remesh domains, verifies the
  exact later handoffs independently, and confirms that a reused source strip
  stops at a typed upstream-field boundary without enabling a production claim.
- Added the matching planner seam for that controller. It records the
  two-sided branch audit, the optional selected branch, and the typed
  non-physical caustic termination without appending a chain cell. This keeps
  continuation orchestration auditable while the first physical post-caustic
  shock-cell solve remains a separate gate.
- Added a solver-owned ambient-attachment-to-physical-field path. It keeps the
  legacy scalar axis/corner bridge diagnostic, but closes the canonical
  solver-generated ambient boundary by continuing every ambient ``C-`` source
  to ``y=0`` and adding the terminal axis cells. The canonical nine-sample
  reference is a state-carrying 45-node/53-cell ambient-closed field with all
  immutable physical gates passing. The strict physical-chain adapter consumes
  only the exact physical ambient sample count and records the centerline
  handoff; its canonical next-cell probe stops at the bounded upstream-domain
  edge rather than extrapolating a second shock. Reflected/mixed-regime
  upstream extension, production next-cell solving, refinement, and external
  validation remain open gates.

These blockers are intentionally represented as structured statuses in code;
they are not reasons to weaken the fidelity boundary.

### Continued terminal-patch transition

The accepted centerline-reflected physical field now exposes a solver-owned
open shock/ambient source submesh through
`as_open_shock_ambient_strip()`. This is a projection of the existing field,
not a second cell: it retains the shock-sourced `C+` terminal trace, validates
the retained state/total-pressure lineage, and carries an explicit trace
discretization tolerance. The existing terminal reflection assembler then
builds the centerline patch and hands its outgoing `C-` trace to the marched
attached-shock solver.

`plan_ambient_closed_post_shock_chain_terminal_patch()` records this one-step
research transition. On the canonical nine-sample case it produces a resolved
seed plus a typed `PHYSICAL_TERMINATION` at a converged normal shock, with the
subsonic/mixed-regime field left outside the supersonic chain. The planner
stores the source-strip report, centerline-seam check, reflected-patch report,
downstream shock report, and tolerance settings. It never appends an open
patch or an unresolved mixed-regime cell, and it remains
`UPSTREAM_COUPLED_RESEARCH` with no production claim.

This closes the first real continued-shock transition without claiming a
complete multi-cell plume. Further cells require a physically closed
mixed-regime handoff (or a separately validated reflected-domain solver),
refinement evidence for the trace-to-patch seam, and independent
measurement-space validation. The basic visual solver and reduced-order
shock-train provider remain unchanged.

The terminal transition now retains its solver-owned artifacts as a typed
`MocPhysicalPostShockTerminalPatchTransitionResult`: the projected source
strip, reflected patch, downstream shock solve, clipped supersonic terminal
field, and exact `MocMixedRegimePerimeterRequest`. A companion planner can run
the explicit prescribed mixed-regime mock—or the existing scalar reference or
caller field callback—against that exact request. The result is recorded
beside the one-cell chain and reports local mixed-regime model convergence
separately from canonical physical closure; the downstream field is never
attached as a supersonic cell and `production_claim_allowed` remains false.

The planar downstream lane also includes a separately named affine
control-section projection reference. It consumes a validated scalar section,
fits its tangential and normal velocity profiles, extends those profiles over
an explicitly closed perimeter, and runs the nonlinear compressible
isentropic potential-field solver. The planner records this field beside the
terminal result, including projection residuals and an independent field
measurement, but does not attach it as a supersonic cell. It remains below
canonical reflected-MOC/free-boundary closure and external validation, with
chain promotion blocked.

The physical continuation seam now has a typed explicit next-cell candidate
bundle containing the candidate shock, downstream-angle schedule, paired
ambient boundary samples, and terminal axial extent. A prescribed ambient-
closed chain mock can drive one or more of these candidates through the strict
solver-owned upstream sampler, attached-shock fit, ambient closure, and
centerline state/pressure handoff. The planner replaces its upstream field only
after a complete physical-field solve; missing upstream samples produce the
typed `UPSTREAM_FIELD_BOUNDARY` stop and preserve the last valid prefix. This
is orchestration and boundary-condition evidence at
`prescribed-boundary-diagnostic` fidelity, not a free-boundary solver or a
production provider, and it does not extrapolate the finite accepted field.

The next reference lane is solver-generated rather than candidate-scheduled:
`MocBoundedUpstreamFieldSource` supplies exact state and static-pressure
callbacks over a declared finite domain, and
`MocSolverGeneratedAmbientClosedPostShockChainReference` re-solves each cell
through the attached-shock, ambient-closure, and centerline-reflection path.
The active field is replaced only after a complete accepted physical solve.
Without a new reflected-domain or characteristic-family source, the default
source is the preceding field and the planner stops at its boundary with
`UPSTREAM_FIELD_BOUNDARY`. A uniform callback is only a labeled plumbing
fixture for multi-cell regression; it does not constitute reflected upstream
coupling, free-boundary closure, or a product-ready solver.
The explicit `MocAmbientClosedChainSourceMode.TERMINAL_REFLECTION_PATCH`
variant now derives the bounded next-source projection from the accepted
field's outgoing shock/ambient strip and reflected centerline patch inside the
solver-generated reference. In the canonical case this produces one accepted
continued-cell attempt and then the typed `OPEN_PHYSICAL_CLOSURE` stop; it
does not extrapolate or promote an unresolved next cell. The mode is an
orchestration seam for the pending reflected-domain/mixed-regime solve, not a
new production fidelity tier.
When a source supplies a preferred shock-start point, the planner also checks
that the point is at or downstream of the current cell interface before
sampling it. A stale or backtracking preferred point is an explicit bounded
upstream-field stop, with no callback evaluation; this keeps a valid source
domain from being reused as a prior-cell source or silently backtracked.
The validation artifact now feeds the accepted physical first-cell field into
this same planner through the canonical old-family/restarted-family caustic
bridge. The exact caustic anchor is accepted as a downstream handoff, and the
planner records one bounded research step before stopping at
``OPEN_PHYSICAL_CLOSURE``; the independent planner measurement passes while
``physical_termination`` and production promotion remain false. This proves
the bridge-to-chain interface without treating the unresolved post-caustic
field remesh as a continued physical cell.

The continued terminal-patch planner now also exposes an explicit planar
downstream handoff. It captures the terminal transition once, forwards the
exact ``MocMixedRegimePerimeterRequest`` to a caller-owned planar callback
alongside an explicit control section and closed perimeter specification, and
records the returned seam as adjacent evidence. The callback result is never
attached to the supersonic chain; ``physical_closure_verified`` and
``chain_promotion_blocked`` remain at their research-only values. The terminal
patch's axis/front traces were also checked against the reusable source-strip
contract and intentionally rejected as a new source lattice because their
geometry is degenerate for that handoff. A future continuation must therefore
provide a genuinely remeshed reflected-domain source rather than relabeling
the bounded patch.

The planar reference lane now also has a separately named frozen-profile
variant. It preserves piecewise-linear, non-affine tangential data from an
explicit control section while requiring a constant normal component for the
declared potential extension. Every perimeter query must remain inside the
measured transverse span; out-of-span samples are typed projection failures,
not extrapolated states. The resulting nonlinear field and independent
measurement are useful for higher-resolution planning and visualization, but
the lane remains a scalar research reference with no canonical free-boundary
or continued-chain promotion claim.

The first-cell planner now has an explicit wrapper for this frozen-profile
reference. It retains the exact terminal request, section, perimeter, profile
policy, and independent handoff result as adjacent diagnostics. The wrapper
keeps the terminal's mixed-regime field unattached and preserves the typed
open-physical-closure chain stop.

The continued terminal-patch result now has the matching explicit attachment
seam. A caller may opt into attaching a converged mixed-regime field only
after it retains the exact terminal shock and supersonic patch; the transition
then reports its local physical closure while keeping terminal status,
``chain_promotion_blocked``, and ``production_claim_allowed=false`` intact.
The planner mock and scalar reference remain adjacent by default, so their
local convergence cannot silently become a continued supersonic cell or a
product claim.

The next solver-owned continuation checkpoint is now explicit. A bounded
terminal-reflection patch can be coupled to a new ambient-closed physical
field through an opt-in Mach-wave endpoint contract: an ambient-matched patch
seam may begin at zero shock strength, and the centerline endpoint may also
be a zero-strength Mach wave, while every interior fitted sample must retain
strict total-pressure loss. The ordinary attached-shock path keeps both
exceptions disabled.

The patch-to-field result records two different handoffs. The prior cell's
centerline trace is retained as the next field's ``incoming_handoff``; the
patch's outgoing ``C-`` trace is retained separately as the internal
``patch_handoff`` consumed by the shock solve. This prevents a reflected
source trace from being mistaken for the adjacent-cell seam. The accepted
field must still pass the ambient, centerline, topology, state-sampling, and
upstream-shock-coupling gates.

The new
``MocTerminalReflectionPatchAmbientClosureChainReference`` and
``plan_ambient_closed_post_shock_chain_terminal_reflection_patch_ambient_closure``
planner provide a deterministic continued-chain experiment. On the
canonical bounded fixture it now carries two newly solved planar-MOC fields,
so the chain contains three resolved cells, then returns a configured
``SOLVER_RETURNED_NO_NEXT_CELL`` stop. The continuation endpoint is the
actual next ambient-boundary endpoint and the requested axial coordinate is
only a limit; no interface is fabricated. This is a research planner, not a
production provider. Continuing beyond that prefix still requires the
canonical reflected-domain/remeshing solve, a polarity-aware expansion or
compression treatment, a genuine downstream free-boundary/mixed-regime
closure, refinement evidence, and independent validation data.

Short near-Mach-wave trace segments now use separate forward and geometry
tolerances. This preserves the strict downstream ordering check without
rejecting a geometrically valid characteristic because one endpoint step is
smaller than the mesh-residual tolerance. That tolerance split is diagnostic
infrastructure only and does not relax the physical closure gates.

The continued-chain experiment now has an explicit trace-polarity checkpoint.
`classify_reflected_trace_polarity()` compares each exact outgoing `C-` trace
with the affine endpoint-angle reference and records compression, expansion,
mixed, or neutral interior evidence. When the affine law would request an
expansion, the opt-in research profile
`reflected-trace-referenced-compression-envelope` preserves the exact trace
endpoints and adds a bounded positive interior compression envelope. This is
an honest numerical continuation profile for exercising handoff and solver
stability; it is not a canonical expansion fan, reflected-domain remesh, or
free-boundary solution.

`MocTerminalReflectionPatchAmbientClosureChainReference` now enables that
profile explicitly and carries a three-cell resolved research prefix on the
canonical bounded fixture. The planner records the polarity-aware setting,
compression amplitude, exact handoff links, and actual downstream ambient
endpoints, then stops at the configured `SOLVER_RETURNED_NO_NEXT_CELL`
boundary. The trace projection uses a mesh-scale `1e-3 m` geometry tolerance
and a separate `1e-4 m` forward-order tolerance; this accommodates the
retained characteristic sampling without weakening the shock loss or field
closure gates. The prefix remains below canonical reflected expansion/
remeshing, mixed-regime, refinement, and external validation acceptance, and
it cannot promote or mutate the basic, reduced-order, signature, ray, or FPA
providers.

## Multi-band variable-entropy continuation-chain checkpoint

The variable-entropy characteristic lane now carries a typed source band into
the next downstream solve. A continuation may consume the initial internal
entropy field or the prior continuation result; the planner requires exact
state/total-pressure frontier retention, source-object identity, shared
pressure-gradient lineage, and a fresh downstream axial domain. The
solver-owned reference exercises two accepted bands and ends with an explicit
``SOLVER_RETURNED_NO_NEXT_CELL`` decision.

The independent continuation-chain audit recursively remeasures every band
and verifies the planner's step records, fingerprints, frontiers, source
links, gradient links, and domain ordering. This closes the multi-band
research seam without creating a ``MocChainCell``: physical cell count,
physical closure, and production claim remain hard false, and the lower-
fidelity visualization, signature, ray-transfer, and focal-plane-array
providers remain untouched.

The next physical gates are still the coupled reflected-shock/free-boundary
and two-dimensional Euler closure, independent refinement across additional
cases, indexed owner-provided validation data, and production next-cell
shock fitting. The continuation chain is evidence for those implementations,
not a substitute for them.

## Local entropy-carrying terminal trial checkpoint

`solve_euler_ambient_first_wedge_entropy_carry` is the next solver-owned
terminal seam after the two-cell retile. It keeps the first ambient-source
total pressure on the off-axis node, carries the terminal shock total pressure
along the centerline, and solves the off-axis flow angle/reflected-axis Mach
pair against the generalized variable-entropy source on both terminal
characteristic edges. The reference trial drives those two source residuals
below `1e-8` while retaining the incoming ambient `C-` geometry and exact
pressure lineages; it does not copy the off-axis entropy onto the axis.

`measure_moc_euler_ambient_first_wedge_entropy_carry` independently rebuilds
the incoming and terminal characteristic geometry, pressure lineage, entropy
source residuals, topology, and coarse-cell Euler residual from the returned
raw samples. On the canonical fixture the trial is intentionally an
`euler_ambient_first_wedge_entropy_euler_residual_failure` with a coarse-cell
residual of approximately `0.01598`. The corresponding planner records the
successful entropy-source closure but stops with `FIDELITY_NOT_ALLOWED` and
zero physical chain cells. The next physical gate is characteristic subcell
refinement with internal family closure, followed by coupling that local
field to the reflected free boundary and indexed external observations.

The reflected-domain remesh seam is now implemented as a separate research
lane. `MocReflectedDomainRemeshRequest` preserves the prior outgoing `C-`
front as an exact reflection anchor and requires independently supplied
centerline `C+` and new outer `C-` source data, so a one-characteristic front
cannot be mistaken for a two-dimensional source boundary. The bounded field
validates polarity, ordering, diagonal compatibility, and source-row total-
pressure continuity; its one-step and fresh-domain sequence planners record
the fidelity ceiling and exact incoming-handoff provenance. The validation
report exercises both the accepted remesh and the typed rejection of front
reuse. The bounded source field can now carry explicit, family-specific total
pressure rows, but it still does not compute their shock/free-boundary source
values. Canonical alternating-family/free-boundary remeshing, mixed-regime
closure, refinement, and external validation remain open, and no
product/provider lane consumes this result. An independent
`op.moc.reflected-domain-remesh` measurement now rechecks the raw trace,
polarity, reflection seam, source rows, source-family pressure lineage, mesh
topology, and bounded state sampling. This strengthens the local audit without
changing the result's research-only ceiling: physical closure, canonical
mixed-regime continuation, and external validation are still the next gates.

The same evidence artifact now includes an independent physical-field-chain
audit, `op.moc.ambient-closed-physical-field-chain`. It remeasures each
solver-generated ambient-closed field and verifies the exact centerline
handoff plus fresh downstream ambient interface across the three-field
research prefix. The generic shock-cell measurement explicitly carries the
zero-strength endpoint allowance used by the reflected continuation, without
relaxing interior shock total-pressure loss. This closes the local planner/
field-chain evidence seam only; canonical reflected remeshing,
mixed-regime/free-boundary closure, refinement, and external validation remain
the release gates, and no lower-fidelity provider is changed.

The reflected-remesh lane now also exposes a physical solver bridge through
`plan_reflected_domain_remesh_ambient_closed_chain`. Its source adapter keeps
the remesh bounded and selects the first state on the newly supplied outer
`C-` source curve as the next shock-start preference. The planner requires the
exact prior centerline handoff in every remesh request and rejects reused
remesh/source-strip identities before invoking the ambient-closed physical
field solver. This is a stronger continued-shock-cell orchestration seam than
the source-strip-only sequence, but it is still a research reference: the
outer curve is caller-supplied Cauchy data, source-row pressure data is
explicitly supplied, and canonical reflected free-boundary closure,
refinement, and external validation remain open. The existing basic
visualization, reduced-order, signature, ray, and focal-plane-array providers
remain untouched.

The remesh also supports a variable-total-pressure source contract. Separate
centerline `C+` and outer `C-` pressure rows are validated and carried into
the bounded characteristic cells by `C-` family, preserving a nonuniform
entropy lineage for later shock/ambient coupling. This is transport of
solver-supplied pressure data, not a shock-loss or ambient free-boundary
solve; the remesh remains open and non-promotable until those coupled
conditions are solved and independently validated.

The next boundary step is now executable as a separate solver-owned reference:
`solve_reflected_domain_outer_source_curve` starts from an explicit prior
outer-boundary state, marches each later centerline `C+` source to an
ambient-pressure/streamline-tangent endpoint, and reassembles the resulting
rows through the pressure-aware characteristic strip. Its independent
`op.moc.reflected-domain-outer-source` audit checks the raw rows, pressure
lineage, ambient residuals, topology, and bounded sampling. The generated
curve can be bound into a fresh reflected-remesh request, so a future planner
callback has a real boundary-solving seam rather than only a prescribed outer
trace. The centerline source, prior seed, shock entropy production, downstream
perimeter, and physical chain-cell promotion remain explicit unresolved gates.

## Alternating-family reflected remesh checkpoint

The first solver-owned alternating continuation is now executable as
`solve_reflected_domain_alternating_source`. It consumes the exact outgoing
`C-` front from the terminal reflection patch, verifies that its first
centerline reflection reproduces the prior patch anchor, and then repeats the
local sequence

`outer seed -> C- centerline anchor -> C+ ambient/tangent outer point`.

The result is represented as a connected band of local two-triangle cells.
This is deliberately a separate mesh contract: the older triangular source
strip requires every centerline/outer cross-pair to remain forward, while the
alternating continuation only claims the neighboring `C-`/`C+` seams it
actually solves. It carries explicit total-pressure rows and provides a
bounded state/pressure sampler, but it does not infer shock entropy, solve the
mixed-regime downstream perimeter, or promote a physical shock cell.

The independent `op.moc.reflected-domain-alternating-source` operator
recomputes the incoming trace, polarity, seed, centerline reflections, ambient
boundary points, alternating compatibility seams, topology, and bounded
sampling. The canonical fixture passes this local audit. The remaining gates
are coupling this band to a canonical reflected free-boundary/shock remesher,
mixed-regime closure, refinement, and external observations; all basic,
reduced-order, signature, ray, and focal-plane-array providers remain
unchanged.

## Alternating-source physical-field checkpoint

The bounded alternating source band now feeds the actual ambient/centerline
physical MOC assembler through
`solve_reflected_domain_alternating_physical_field`. The bridge starts at the
ambient-matched source point, records shock entropy for the positive interior
turn envelope, permits only the explicitly declared zero-strength endpoints,
and retains the exact incoming chain handoff. The independent
`op.moc.reflected-domain-alternating-physical-field` audit remeasures the
source, attachment, envelope, shock curve, raw field, sampling, and upstream
coupling rather than trusting solver flags.

`plan_reflected_domain_alternating_source_chain` now carries one resolved
state-bearing research cell and then returns a typed no-next-cell stop so the
finite source band cannot be reused. This closes the local physical-field
bridge but remains non-canonical: the provisional compression envelope,
reflected free-boundary remesher, mixed-regime closure, refinement, and
external validation are still open, and no product/provider lane consumes it.

## External observation comparison checkpoint

The continued-cell validation seam now includes the separate
`op.moc.shock-cell-external-comparison` operator. A caller can register an
external case with explicit calibration or validation role, source/provenance,
axial-transverse metre metadata, and one or more indexed cell observations.
The operator compares only exact overlapping cell indices and reports per-cell
axial length, maximum radius, shock start/end, and centerline-end residuals,
including uncertainty-normalized diagnostics when uncertainties are supplied.
It never fits an axial origin, synthesizes a missing cell, converts units, or
extrapolates beyond the observed range.

`audit_moc_external_validation_splits` separately checks that calibration and
validation case identities are both present and disjoint. A successful split
audit is governance evidence only. The comparison and split audit both remain
`not_accepted`: no external observation archive is currently available in the
workspace, canonical reflected free-boundary/mixed-regime closure is still
open, and neither the planner mock nor any visualization, signature, ray, or
focal-plane-array provider consumes this lane.

## Fresh alternating-source chain sequence checkpoint

The alternating reflected-domain lane now has a multi-cell planner seam:
`plan_reflected_domain_alternating_source_chain_sequence`. The initial bounded
C-/C+ source band is used for the first continued cell, and every later cell
must be supplied by a callback that solves a new source band from the
currently accepted physical field. The source solver can now retain the exact
prior centerline handoff as provenance; the planner rejects a missing or
mismatched handoff before shock solving.

The sequence also fingerprints the state-bearing source rows and rejects a
copied geometry even when a caller wraps it in a new result object. Active
field replacement occurs only after the alternating source, ambient-closed
shock field, upstream coupling, and downstream extent gates pass. A missing
fresh band is a typed `SOLVER_RETURNED_NO_NEXT_CELL` research stop, while
source or physical-field failures retain their specific chain reason.

This is a real continued shock-cell orchestration contract, not a canonical
reflected-plume solution: the local compression envelope, canonical
mixed-regime/free-boundary closure, refinement, and external validation gates
remain open. The planner mock and all lower-fidelity visualization, signature,
ray, and focal-plane-array providers remain unchanged.

## Potential-field no-penetration checkpoint

The explicit compressible-potential reference now measures the finite-element
normal velocity on every selected tangency edge, using the adjacent triangle
gradient and the declared perimeter orientation. A tangent input trace alone
is therefore not allowed to masquerade as a no-penetration field: slip-wall
and ambient free-boundary conditions gate on the independent outer-edge normal
residual, while a prescribed-pressure outflow section keeps its intentionally
different normal-flux contract.

The field result and the independent
`op.moc.mixed-regime-compressible-potential` measurement both carry this
residual. A tangency-conditioned potential solve that cannot satisfy the
finite-element no-penetration check returns a typed residual failure, and a
tampered converged field is rejected by the independent operator. This is a
closure diagnostic and a stricter research gate, not a free-boundary shape
solver: the perimeter is still caller-owned, the quasi-one-dimensional
free-boundary reference remains separate, canonical reflected-domain
coupling/refinement and external observations are still open, and no product
or provider lane consumes the result.

## Terminal audit model-dispatch checkpoint

The independent terminal-closure measurement now dispatches its mixed-regime
model gate from the declared field model. Harmonic and radial reference fields
retain their existing independently recomputed harmonic/divergence checks;
the compressible potential reference is instead remeasured through
`op.moc.mixed-regime-compressible-potential`, including nonlinear mass,
potential circulation, boundary-potential, strict-subsonic, and applicable
finite-element normal-flow residuals. Those model-specific diagnostics are
carried in the terminal report rather than being hidden behind a generic
harmonic residual.

This closes an audit mismatch without changing the physical claim ceiling: the
perimeter is still supplied by the caller, the terminal remains a stop, and
the reflected-domain canonical free-boundary/mixed-regime solver, refinement
evidence, and external observations are still required before any promotion.

## Alternating physical-field chain audit checkpoint

The continued alternating-source lane now has an independent multi-result
audit, `op.moc.reflected-domain-alternating-physical-field-chain`. It remeasures
each source/physical-field result, compares source-geometry fingerprints that
exclude the incoming handoff, verifies exact centerline handoffs, and delegates
raw mesh/domain checks to the physical-field chain operator. A copied source
band is rejected even when wrapped in a new result, and a source band that
produces another field at the original interface is rejected as a non-fresh
domain. The current bounded fixture therefore records the correct research
stop rather than accepting a geometrically repeated cell.

The fresh-band sequence planner now runs this audit over the raw alternating
physical-field results it produced and carries the report in its diagnostics.
This makes the planner mock/sequence output self-describing: a resolved
bookkeeping chain can coexist with an explicit `domain_failure` audit until
the underlying solver has actually remeshed the downstream interface.

This audit does not close the remaining physics: a solver-owned reflected
terminal trace must still produce a valid downstream C− source and a fresh
mixed-regime/free-boundary perimeter before an alternating result can pass the
multi-cell domain gate. Refinement and external observations remain separate
release gates, and no visualization, signature, ray, or focal-plane-array
provider consumes this research lane.

## Terminal planner downstream-audit checkpoint

The continued terminal-patch planner now records independent downstream
evidence beside its solver result. Every retained terminal field and selected
mixed-regime closure is remeasured through
`op.moc.terminal-closure`; the audit verifies the normal-shock seam, terminal
mesh coverage, pressure loss, exact mixed-regime seam, and the declared field
model. The solver-owned quasi-one-dimensional reference additionally carries
the independent `op.moc.mixed-regime-free-boundary-reference` measurement,
which rechecks its outlet-height root, generated perimeter, ambient pressure,
tangency, mass-flow, and scalar-field gates.

The free-boundary solver now retains its exact downstream condition and
perimeter specification on the closure object as well as on the enclosing
result. The generic terminal audit dispatches the free-boundary model without
applying the harmonic reference's velocity-divergence gate; the specialized
free-boundary operator remains the stronger root and geometry check. Explicit
field attachment therefore requires the independent terminal seam audit and,
for the free-boundary reference, its specialized audit too. Both outcomes
remain terminal, non-promotable research evidence: the reflected two-
dimensional free-boundary solve, refinement, and external observations are
still open, and no product/provider lane consumes them.

## Continued-chain terminal orchestration checkpoint

`plan_ambient_closed_post_shock_chain_terminal_reflection_patch_ambient_closure_with_mixed_regime`
now composes the bounded reflected-patch chain with one terminal handoff. It
retains the accepted multi-cell supersonic prefix, captures only the final
field that actually entered that prefix, and invokes the terminal planner from
that field. A prefix that stops before accepting a new physical field does not
fabricate a terminal transition. The mixed-regime result is reported beside
the prefix and is never counted as another shock cell.

The combined planner can exercise the prescribed mixed-regime mock or the
solver-owned scalar free-boundary reference, including the latter's optional
resolution sweep. The mock path is a deterministic orchestration fixture; the
scalar reference can still fail its independent outlet-height or geometry
gates for a continued-cell seam, and that failure remains visible rather than
being converted into a resolved closure. Both modes retain the research-only
claim ceiling, block chain promotion at the mixed-regime boundary, and leave
the fast visualization, signature, ray, and focal-plane-array providers
unchanged. Canonical reflected-domain/free-boundary physics and external
validation remain release gates.

The composite planner also carries independent measurements of the prefix:
the planner-trace audit rechecks cell order, topology, handoff fingerprints,
typed termination, and fidelity isolation, while the physical-field-chain
audit remeasures each retained raw field, shock loss, ambient closure, state
sampling, exact handoff, and fresh downstream domain. These audits are
diagnostics and remain non-promoting; they make a passing continued prefix
distinguishable from a solver flag or a copied geometry.

## Solver-derived reflected-interface attachment checkpoint

The automatic alternating-source chain planner now derives each fresh source
band from the accepted physical field that precedes it. The bounded source
sampler retains the reflected patch as an upstream interface region, while
the newly generated alternating cells remain the preferred samples wherever
their domains overlap. An opt-in outer-seed attachment starts the next shock
at the exact retained outgoing reflection-interface point and passes the
zero-strength trace to the shock marcher; the existing first-new-outer-row
attachment remains the default for one-step callers.

The physical-field result records its attachment mode and numerical sampling
tolerance separately from the looser projected-patch geometry tolerance. The
independent alternating physical-field audit uses that sampling tolerance, so
fresh multi-cell domains are checked against the same state field that the
solver marched. The automatic planner now reports a passing fresh-domain,
handoff, and physical-field-chain audit for the bounded canonical fixture.
This remains a research continuation: the canonical reflected free-boundary
law, mixed-regime downstream closure, refinement evidence, and external
observations are still release gates, and no product/provider lane consumes
the result.

## Alternating physical-field chain refinement checkpoint

The continued shock-cell lane now has a separate numerical-sensitivity
operator, `op.moc.reflected-domain-alternating-physical-field-chain-refinement`.
It accepts independently rerun typed physical-field chains at strictly
increasing shock resolutions and remeasures every chain before comparison.
Resolution metadata must match every retained field's physical shock sample
count; a caller cannot relabel an unchanged run as refinement evidence.

The audit requires stable continued-cell count and geometry shape, fixed
solver controls, fresh source-band geometry, exact handoff metadata, strict
shock pressure loss, and bounded changes in axial extent, shock spacing, mesh
area, and maximum radius. Optional termination metadata is compared when
provided. The case report retains the per-resolution measurements and raw
residuals, so a failed sensitivity check is distinguishable from a solver or
source-domain failure.

A passing refinement measurement is still explicitly research-only: its
`physical_closure_verified` property remains false, chain promotion remains
blocked, and production claims remain disallowed. The canonical reflected
free-boundary/mixed-regime closure and external validation archive are still
open, and the fast visualization, signature, ray, and focal-plane-array
providers remain untouched.

## Standalone continued-chain validation checkpoint

The standalone primitive-validation report now runs the alternating
physical-field refinement probe from the solver-generated ambient-closed seed.
For each of the 17- and 33-sample cases it rebuilds the reflected strip,
centerline patch, alternating source band, and two-cell shock sequence from
fresh carried fields and exact centerline handoffs. The report records the
declared geometry tolerances, per-case measurements, residuals, and every
research-chain gate; a missing or inconsistent refinement result fails the
validation artifact rather than being hidden by the older one-cell probe.

This checkpoint makes the planner mock and continued shock-cell evidence
visible in the same artifact used by the broader primitive gate. It does not
turn numerical repeatability into physical closure: the canonical reflected
free-boundary/mixed-regime coupling, external observations, and product
promotion remain open release gates.

## Standalone external-observation gate checkpoint

The standalone report now carries an explicit external-validation record next
to the solver-generated continued-chain measurement. It invokes the split
governance operator with no bound datasets and reports the result as
`blocked-missing-external-observations`; this status is intentionally outside
the local primitive failure list because it is a known release gate, not a
failed numerical solve.

The external adapter requires indexed shock-cell observations with
`cell_index`, axial-transverse coordinates in metres, feature provenance, and
disjoint calibration/validation case metadata. The current intake evidence is
not bound to that schema. In particular, pressure-position or Mach-disk points
must not be converted into shock-cell geometry without an explicit extraction
and provenance binding. Until a real indexed calibration and validation set is
attached, the comparison is `None`, the split audit is not verified, and no
external or product claim is accepted.

This checkpoint closes the reporting seam only. Canonical reflected-domain
mixed-regime/free-boundary coupling, external indexed observations, and
provider promotion remain open; the fast visualization, signature, ray, and
focal-plane-array lanes are unchanged.

## Integrated control-section flux reference checkpoint

The solver-owned terminal adapter now has an explicit opt-in integrated-flux
path for a distributed subsonic control section. It recomputes an equivalent
terminal-state height from the section's scalar mass-flux proxy, while keeping
the full section, its varying Mach/flow-angle samples, and the flux identity in
the result. The original geometric-measure adapter still rejects a
non-terminal-equivalent section, so a caller must name the lower-fidelity
reduction deliberately.

The first-cell planner exposes this path through
`plan_solver_generated_first_cell_terminal_closure_reference_from_control_section_flux`.
The independent free-boundary measurement rechecks the control section,
stored validation, flux proxy, equivalent height, and flux residual before
accepting the local reference. This is useful for continued-chain and
visualization development, but it remains a quasi-one-dimensional reduction:
the downstream 2-D perimeter/entropy coupling, refinement, and external
indexed observations are still release gates. The terminal remains a stop and
cannot seed another shock cell; no product/provider lane consumes this result.

## Continued-chain control-section handoff checkpoint

The combined continued-chain planner now carries an explicit downstream
control section through the accepted supersonic prefix and into the terminal
mixed-regime handoff. The scalar section path remains the strict default and
requires terminal-equivalent states; the opt-in integrated-flux path records
the distributed section and its flux identity while naming the result as a
quasi-one-dimensional reduction. Refinement reruns use the same selected mode,
so a resolution sweep cannot silently switch the downstream fidelity.

The terminal remains evidence beside the shock-cell prefix: its free-boundary
model is independently audited, the chain promotion gate remains blocked, and
the fast basic visualization/reduced-order providers are unchanged. This
extends the planner mock and continued-cell orchestration seam, but does not
close the canonical reflected 2-D free-boundary/entropy solve or provide the
missing indexed external observations required for promotion.

## Continued-chain planar handoff checkpoint

The continued-prefix orchestration now has a dedicated planar handoff entry
point. It runs the same fresh reflected physical-field prefix audit, passes
the exact terminal request from the last accepted field to the callback, and
retains the callback's control-section/perimeter result beside—not inside—the
supersonic chain. This makes the planner mock, scalar/integrated-flux
references, and explicit planar callback comparable at the same terminal
seam.

The callback remains caller-owned research evidence. A passing local planar
field does not close the canonical reflected free boundary, does not create a
new shock cell, and cannot promote the basic visualization, reduced-order,
signature, ray, or focal-plane-array lanes.

## Next fidelity boundary: trace-referenced continuation

The continued alternating-field lane now exposes an explicit
`use_trace_referenced_profile` switch. With retained outer-seed attachment,
the opt-in path reuses the exact reflected `C-` trace as the downstream turn
profile and independently remeasures that profile from raw samples. The
automatic multi-cell planner leaves this switch off: a locally closed
trace-profile field can still fail the next remesh's terminal-characteristic
gate at the current resolution. That observed failure is retained as a
research boundary rather than hidden by relaxing the chain's geometry checks.

The next implementation target remains the canonical reflected-domain
remesher and mixed-regime/free-boundary solve. Until those gates, refinement,
and indexed external observations pass, all alternating results remain
research-only and isolated from visualization, signature, ray, and
focal-plane-array providers.

## Parameterized 2-D free-boundary reference checkpoint

The mixed-regime seam now has a separately named
`parameterized-2d-compressible-potential-free-boundary-reference`. It takes an
explicit terminal request and scalar control section, represents the
downstream envelope with a parameterized nondecreasing/concave set of height
samples, and iterates those heights against signed finite-element normal-flow
residuals from the nonlinear compressible-potential field. Downstream length,
outlet height, radial resolution, and free-boundary sample count remain
explicit inputs; the single-field reference also requires uniform isentropic
total pressure and gamma across the control section.

The independent
`op.moc.mixed-regime-planar-free-boundary-reference` measurement reconstructs
the perimeter from the reported shape, rechecks the terminal/control-section
and ambient-pressure/tangency seams, and independently measures the retained
field's normal-flow residual. Uniform and nontrivial ambient-pressure cases
are covered by focused tests, including tampered-geometry and tampered-field
rejections.

This is local 2-D potential-flow evidence, not canonical reflected-MOC
closure. It cannot seed another supersonic shock cell, remains blocked from
all production providers, and still requires canonical mixed-regime coupling,
refinement, and indexed external observations before any promotion decision.

## Parameterized planar free-boundary refinement checkpoint

The planar reference now has a separate independent refinement operator,
`op.moc.mixed-regime-planar-free-boundary-refinement`. It consumes fresh
typed reruns at strictly increasing free-boundary resolutions, remeasures each
case with `op.moc.mixed-regime-planar-free-boundary-reference`, and derives
the reported perimeter, node, and cell counts from the retained results. A
caller cannot relabel one run as several resolutions; the exact terminal
request, control section, ambient pressure, downstream dimensions, centerline
sampling, and radial sampling must remain fixed.

The refinement gate compares a normalized 33-point envelope shape, normalized
centerline speed, and finite-element mesh area between adjacent resolutions.
It also requires every independent boundary-normal velocity residual to pass.
The canonical fixture passes the 6/8/10 sample sequence with perimeter counts
11/13/15, node counts 21/25/29, and cell counts 30/36/42. These measurements
are numerical-sensitivity evidence for the parameterized potential reference,
not a claim that the physical reflected-MOC boundary has converged.

The refinement result therefore preserves
`canonical_free_boundary_verified=false`, `chain_promotion_blocked=true`,
and `production_claim_allowed=false`. The next physics gate is still a
solver-owned reflected 2-D free-boundary/entropy coupling with a shared
shock/ambient boundary, followed by refinement and indexed external
observations; neither this operator nor its local field may seed a continued
shock-cell chain or alter the basic visualization, signature, ray, or
focal-plane-array providers.

## Reflected shock-interface entropy handoff checkpoint

The terminal request now exposes a typed
`solver-owned-reflected-shock-interface-entropy-handoff`. It concatenates the
validated oblique-shock patch with the scalar normal-shock endpoint and carries
the sample-wise upstream/downstream total-pressure pair, downstream regime,
flow angle, gamma, and cumulative shock-interface arc length. The handoff
provides bounded pressure/entropy interpolation for the next downstream
solver; it does not invent a subsonic `CharacteristicState`, close a
perimeter, or extrapolate past the measured interface.

The independent `op.moc.mixed-regime-entropy-handoff` operator rebuilds those
samples from the exact terminal request, checks path ordering and terminal
identity, and recomputes strict shock loss and the nondimensional entropy
coordinate. The standalone fixture passes this measurement with all 17
interface samples, while the handoff remains explicitly non-physical and
non-promotable. The next physics task is to advect this pressure/entropy
profile through a solver-owned subsonic field while solving the reflected
ambient free boundary; only that coupled result can feed a continued cell.

## Planner entropy-handoff checkpoint

The first-cell and continued-prefix planners now retain the exact
`MocMixedRegimeEntropyHandoffResult` beside the terminal result. Each planner
run invokes the independent entropy-handoff measurement and exposes its
`mixed_regime_entropy_handoff_verified` gate in both the typed result and the
serialized planner report. This makes the planner mock, scalar reference, and
explicit planar callback comparable at the same terminal seam, including
sample count, pressure-loss metrics, and the terminal index.

The handoff is still an open interface profile: it carries shock-interface
entropy data but does not advect entropy through a subsonic field, infer the
ambient/free boundary, or create another supersonic cell. The continued-chain
planner therefore keeps chain promotion blocked and the production claim
false. The next implementation target remains the solver-owned coupled
subsonic entropy-transport/free-boundary problem, followed by refinement and
indexed external observations.

## Continued-chain pressure-map checkpoint

The prescribed post-shock planner mock now exposes an explicit normalized
pressure-coordinate vector for every prescribed next-shock sample. The
continued-cell callback maps the exact incoming handoff through those
coordinates and reports the mapping alongside the per-cell geometry schedule;
planner and visualization diagnostics can therefore see how pressure lineage
was transferred instead of treating normalized-index resampling as hidden
solver behavior. The standalone five-cell fixture exercises a nonuniform
coordinate schedule and the existing independent shock-cell/planner
measurements remain green.

This is still a deterministic prescribed-boundary mock. The coordinate map is
not a streamline solve, a reflected free-boundary law, or canonical entropy
transport, so the mock remains below the resolved physical-chain and product
claim ceilings. The next physics gate is unchanged: a solver-owned
subsonic entropy-transport/free-boundary solve must replace the fixture policy
before any continued-cell promotion.

## Explicit mixed-regime entropy transport boundary checkpoint

The next downstream seam is now represented by
`MocMixedRegimeEntropyTransportResult`. It accepts a caller-declared source
arc coordinate and streamline identifier for each node of a solved scalar
mixed-regime field. The solver checks exact request/handoff/field identity,
bounded interpolation over the ordered shock-interface pressure profile,
streamline-group completeness, pressure-lineage residuals, and the terminal
normal-shock seam. It never infers a streamline or extrapolates entropy data.

The independent
`op.moc.mixed-regime-entropy-transport-boundary` operator repeats those checks
from the separate typed inputs, including result-metric consistency. The
first-cell planner, continued terminal planner, and continued-prefix planner
can opt into the seam with paired source-coordinate and streamline-id arrays;
their reports expose the transport result and measurement separately from the
supersonic chain.

This checkpoint is deliberately below the release boundary. It is an explicit
solver-owned entropy boundary reference, not a variable-entropy Euler solve,
not a canonical reflected free-boundary solution, and not another shock-cell
seed. All promotion and product flags remain blocked. The next implementation
step is to replace the caller-owned map with a coupled reflected downstream
field that advects entropy while solving the ambient/free boundary, then add
refinement and indexed external observations.

## Solver-owned variable-entropy free-boundary reference checkpoint

The next research seam is now implemented as
`solve_mixed_regime_variable_entropy_free_boundary`. It consumes the typed
terminal shock/entropy handoff and a vertical downstream control section, then
constructs its source pressure/gamma profile internally, transports total
pressure along explicitly labeled streamlines, and iterates the outer height
against the ambient-pressure condition. The returned triangular stream-tube
mesh retains source arc coordinates, streamline IDs, transported pressure,
free-boundary points, and residual histories as auditable solver-owned data.

The result intentionally separates settled downstream checks from the entrance
regularization seam. Settled cells are checked for mapped continuity, entropy
advection, and mass-flow consistency; connector, entrance, and transverse-
momentum residuals remain visible rather than being folded into a single
acceptance number. The independent
`op.moc.mixed-regime-variable-entropy-free-boundary` measurement reconstructs
the source profile and node layout, rechecks the control-section/ambient
condition, topology, and residuals, and verifies the returned fidelity flags.

The standalone validation uses a derived pressure-lineage stress fixture
because the current production-generated handoff contains an outer sample with
total pressure above the terminal value, which violates the scalar no-gain
perimeter required by this reference. The fixture preserves the same terminal
seam and applies a documented pressure-loss patch; it does not mutate the
production handoff or imply external validation coverage.

This checkpoint remains below the canonical boundary: transverse momentum is
not closed, the entrance regularization is not a converged coupled solution,
and the free boundary is not a shock-fitted canonical Euler boundary. Thus
`physical_closure_verified=false`,
`canonical_free_boundary_verified=false`,
`canonical_euler_verified=false`, `chain_promotion_blocked=true`, and
`production_claim_allowed=false` remain mandatory. The next physics gate is a
genuinely coupled reflected 2-D Euler/MOC/free-boundary solve, followed by
refinement and indexed external observations; no basic visualization,
signature, ray, or focal-plane-array provider consumes this lane.

## Geometry-owned first-cell candidate checkpoint

The next supersonic seam is now explicit in
`solve_first_cell_geometry_owned_candidate`. It accepts a finite shock-geometry
seed and a bounded upstream source exposing `state_at` and
`static_pressure_at`; it does not accept a downstream flow-angle callback. At
each shock sample it derives the local attached turn from the shock tangent,
re-solves the Rankine--Hugoniot state, corrects the first segment to the
requested ambient pressure, corrects the final segment to the centerline
target, and assembles the ambient/centerline reflected characteristic field.

The returned candidate retains the original and corrected shock points, the
upstream samples, downstream angles, shock-angle residuals, ambient pressure
and tangent residuals, the iteration history, and the complete physical-field
result. The independent
`op.moc.first-cell-geometry-owned-candidate` measurement recomputes the local
shock tangent/RH residual, strict total-pressure loss, ambient attachment,
field topology, state sampling, and upstream-shock coupling from those typed
outputs. A bounded source miss is a typed upstream-field failure; no last-state
extrapolation is permitted.

This is a research candidate rather than the canonical free-boundary solve.
The seed still supplies the global shock topology, the upstream field is a
bounded fixture or previously solved source, and the coupled 2-D Euler/free-
boundary residual plus external indexed observations remain open. The
candidate and its measurement therefore keep
`canonical_free_boundary_verified=false`,
`canonical_euler_verified=false`, `external_validation_verified=false`,
`chain_promotion_blocked=true`, and `production_claim_allowed=false`. The
standalone primitive report now records this candidate beside the existing
prescribed planner mock and continued physical-chain references without
changing any fast visualization or reduced-order provider.

The next implementation seam is to use the accepted local field as an
explicit research handoff for a deterministic continued-cell audit, then
replace the seeded geometry with a globally remeshed reflected shock and add
sample-count refinement before any chain promotion is reconsidered.

## Bounded first-cell shock-shape correction and planner guard

The first geometry-owned candidate now has a separate residual-driven
correction lane, `solve_first_cell_free_boundary_correction`. It searches a
bounded one-parameter axial homothety of the seeded shock about its attachment
point. Every trial is re-solved through the local Rankine--Hugoniot,
ambient-boundary, and reflected characteristic-field candidate; the carried
ambient-to-axis static-pressure mismatch is retained as the scalar residual.
The solver records the initial, endpoint, and bisection trials and returns
typed `NO_BRACKET`, upstream-field, candidate, and iteration outcomes without
extrapolating a bounded source.

The independent
`op.moc.first-cell-free-boundary-correction` measurement reconstructs the
shape family, recomputes every retained axis residual from the trial field,
checks the selected-trial linkage, and reuses the independent local candidate
measurement only for the selected field. The canonical uniform reference
currently has a same-sign positive residual of about `0.15276` at both shape
bounds, so the correct evidence is an audited `axis_pressure_no_bracket`
boundary, not a fabricated corrected root.

The standalone refinement keeps the same narrow shape bracket, `0.95 <= s <=
1.05`, and repeats fresh solves at 5, 9, and 17 shock samples. All three
resolutions independently reproduce the shape family, selected raw field
audit, and same-sign residual; the appended ambient-to-axis boundary remains
open at every resolution. A wider local bracket can leave the characteristic
domain at the fine resolution, so it is reported as a solver-domain boundary
rather than silently widened or extrapolated.

The reusable `op.moc.first-cell-free-boundary-correction-refinement` operator
now owns that resolution check for the standalone gate. It independently
remeasures each correction, requires the declared sample-count order and
fixed shape bracket, compares the selected residuals, and carries the same
non-promotion flags. A converged refinement measurement therefore means
resolution consistency of an unresolved research boundary, not readiness to
append a continued shock cell.

`plan_first_cell_free_boundary_correction` exposes the correction-owned chain
termination decision through a planner guard. It deliberately invokes no
continued-cell callback and preserves
`chain_promotion_blocked=true`,
`canonical_free_boundary_verified=false`,
`canonical_euler_verified=false`, and
`production_claim_allowed=false`. The existing prescribed planner mock and
continued shock-cell chain remain useful for handoff/topology validation, but
neither may consume this research correction as a production first cell. The
next physics gate is a globally remeshed reflected shock whose residual can
straddle zero, followed by an independently closed post-shock field and
sample-count refinement.

## First-cell research handoff into a continued chain

The geometry-owned first-cell candidate now has an explicit research-chain
planner, `plan_first_cell_geometry_owned_research_chain`. It first reruns the
independent local candidate measurement, then uses the exact retained physical
field as the seed for either the solver-generated terminal-reflection-patch
continuation or the existing prescribed ambient-closed planner mock. Accepted
continued fields are observed and retained beside the candidate rather than
reconstructed from chain geometry.

The standalone primitive report currently exercises the reflected-patch path
with a three-cell prefix: the geometry-owned candidate is cell 1, followed by
two fresh reflected/remeshed physical fields. The configured reference stop
is recorded as `solver-returned-no-next-cell`. The independent
`op.moc.first-cell-geometry-owned-research-chain` operator remeasures the
candidate, planner trace, exact centerline handoffs, cell count, and each
fresh downstream physical-field domain. Its passing result is a
research-chain audit, not canonical free-boundary evidence.

The companion
`op.moc.first-cell-geometry-owned-research-chain-refinement` operator now
repeats that three-cell chain at sample counts 5, 9, and 17. It independently
remeasures both runs at every resolution, verifies identical typed handoff
traces on the repeats, and bounds per-cell axial extent, shock-spacing,
radius, and mesh-area changes across resolution. The standalone gate passes
these checks; the result is numerical stability evidence for the research
lane only, not a physical reflected-plume validation claim.

The higher-fidelity sibling
`plan_first_cell_geometry_owned_alternating_research_chain` now seeds the same
candidate field into the automatic reflected-domain source path. It derives a
fresh alternating `C-`/`C+` source band from each accepted field, retains the
exact incoming centerline handoff, and is independently checked at 5, 9, and
17 shock samples. The bounded default prefix contains the candidate plus two
continued fields and ends with a typed `solver-returned-no-next-cell`
decision. Its explicit compression envelope is a research control, not the
canonical reflected expansion/free-boundary law; canonical mixed-regime
closure, external validation, and product promotion remain closed.

The optional prescribed mock remains a separate mode. It may consume the
same local candidate field only as a bounded handoff fixture; if its explicit
next shock leaves that finite field, the planner returns the typed
`upstream-field-boundary` stop and does not extrapolate. Both modes preserve
`canonical_free_boundary_verified=false`, `canonical_euler_verified=false`,
`chain_promotion_blocked=true`, and `production_claim_allowed=false`. No fast
visualization, signature, ray, or focal-plane-array provider consumes this
research-chain result.

## Solver-owned first-cell endpoint reference

The next local boundary experiment is now explicit in
`solve_reflected_domain_solver_owned_first_cell`. It consumes a generated
alternating source band and varies a local compression amplitude; each trial
generates its shock and post-shock field from that source band, then compares
the raw shock endpoint with the next solver-generated centerline source
state. No caller-supplied shock curve is used, and every trial, including a
failed trial, is retained.

The independent
`op.moc.reflected-domain-solver-owned-first-cell` measurement recomputes the
source-band audit, trial physical fields, endpoint coordinates, scalar
residuals, selected-trial linkage, and fidelity metadata. A reproducible
same-sign amplitude bracket is a successful research audit of the no-bracket
boundary; it is not a physical endpoint closure. The current standalone
fixture records two locally complete trials with a typed
`solver_owned_first_cell_boundary_bracket_failure` result and zero validation
failures.

This reference remains deliberately below the canonical boundary. Its local
compression family is still a research control, the reflected global shock
topology and mixed-regime downstream closure are not solved, and refinement
and external observations are still required. The result therefore keeps
`canonical_free_boundary_verified=false`,
`canonical_euler_verified=false`, `external_validation_verified=false`,
`chain_promotion_blocked=true`, and `production_claim_allowed=false`.
The one-cell `total_cell_count=1` planner edge now stops before attempting a
source projection, while larger prefixes continue to require fresh source
bands, exact centerline handoffs, independent field audits, and explicit
typed termination.

The next physics gate is a globally remeshed reflected shock whose endpoint
residual can straddle zero, followed by a coupled post-shock field with
sample-count refinement and indexed external validation. Until those gates
pass, the fast visualization and reduced-order shock-train lanes remain
unchanged and are not trained or relabeled from this research lane.

## Solver-owned first-cell planner handoff checkpoint

The solver-owned first-cell endpoint shoot is now callable through
`plan_reflected_domain_solver_owned_first_cell_chain`. The planner checks the
exact seed centerline handoff, records the callback step, retains the solver's
typed endpoint result and independently measured audit, and stops with
`OPEN_PHYSICAL_CLOSURE` when the bounded amplitude family has no endpoint
root. A future locally closed root would still stop at
`FIDELITY_NOT_ALLOWED`; this adapter cannot silently promote the local
compression envelope into a continued production shock cell.

The endpoint solver also supports an optional bounded interior amplitude scan.
The scan can discover an adjacent sign-changing pair inside the declared
interval, but it cannot cross an invalid trial or evaluate beyond the caller's
bounds. The standalone evidence uses a three-sample scan and records the
same-sign residual boundary as a successful research audit. This advances the
bracket-search seam without changing the fidelity ceiling or any
visualization, signature, ray, or focal-plane-array provider.

## Euler companion-field and external-review checkpoint

The Euler-consistent shock lane now exposes the companion-conditioned strip's
chain boundary through `MocEulerCompanionFieldResult.as_chain_termination_decision`.
A converged one-layer strip is reported as a typed non-physical
`open-physical-closure` stop, while missing shock/companion data, unsupported
characteristic orientation, topology failure, and pressure/invariant failure
retain distinct chain reasons. This makes the strip available to planner
logic without allowing a topologically bounded diagnostic patch to become a
resolved chain cell.

The external lane now has an explicit
`MocShockCellExternalPromotionPolicy` and
`review_moc_shock_cell_external_promotion` operator. It aligns only exact
`cell_index` observations, requires disjoint calibration and validation case
IDs, and refuses to infer tolerances, coordinates, missing features, or
unobserved cells. A passing review is external evidence only; it leaves chain
and product promotion false. Because the owner-provided indexed archive is
not currently bound to the standalone report, its review remains
`blocked-missing-external-data`.

The next implementation gate remains a solver-owned companion/free-boundary
closure that can supply the missing downstream boundary and entropy transport
from the reflected field. Once that exists, the same chain handoff and
external review contracts can audit a multi-cell sequence without changing
the fast visualization or reduced-order providers.

## Open Euler field-chain planner mock checkpoint

The Euler companion-field lane now exposes a typed downstream handoff made
from its solver-carried interior state and pressure samples. That handoff is
an open frontier, not a physical cell perimeter. A separate
`plan_euler_companion_field_chain` consumes only a converged, state-carrying
open field, requires an exact handoff fingerprint at every continuation, and
retains each fresh field in a typed step trace. It never constructs a
`MocChainCell` and rejects a callback that claims physical termination for
this open lane.

`MocEulerCompanionFieldChainMock` provides a deterministic three-field
translated-strip sequence for planner, visualization, and topology tests.
The mock exercises repeated downstream frontiers and a typed
`solver-returned-no-next-cell` stop, but it is not a physical continuation
law and does not imply solved reflected/free-boundary or entropy closure.
`op.moc.euler-companion-field-chain-audit` independently remeasures every
field, fresh axial domain, exact frontier link, result fingerprint, and
termination. Its passing status means the local sequence contract is stable;
`physical_closure_verified`, `chain_promotion_blocked`, and
`production_claim_allowed` remain false, and the fast/basic visualization,
signature, ray-transfer, and focal-plane-array providers remain untouched.

The separate
`op.moc.euler-companion-field-chain-refinement` measurement now remeasures
the same open sequence at 9, 17, and 33 shock samples. It requires the
declared resolution to match every retained boundary/interior array,
rechecks connected non-manifold-free strip topology, compares corresponding
field endpoints and axial domains, requires non-increasing local conservative
residuals, and repeats the exact handoff and typed-stop checks. The generated
sequence passes with maximum cell residuals decreasing from approximately
`0.00654` to `0.00349` to `0.00180`. This is numerical evidence for the
bounded open-field planner seam only; it does not close the physical
reflected/free-boundary or entropy problem.

The next gate is a solver-owned continuation that replaces the translated
fixture with a globally remeshed reflected field, transports entropy, and
supplies a physically closed downstream/free-boundary perimeter. Only after
that gate, refinement, and indexed external observations pass may the same
handoff machinery be considered for a physical continued shock-cell chain.

## Ambient companion-boundary audit checkpoint

The solver-owned ambient companion reference now has an independent
`op.moc.euler-ambient-companion-boundary-audit` measurement. It reconstructs
the exact shock/sample alignment, ambient static-pressure residuals, carried
`C-` invariant, streamline-like geometry and shock clearance, then verifies
that the solver has kept physical closure false, chain promotion blocked, and
production claims disabled. The standalone artifact requires this audit next
to the independent open-strip Euler audit, so a locally consistent companion
trace cannot silently become a resolved cell.

This remains a bounded research reference. A coupled reflected downstream
field must still transport entropy, solve the ambient/free boundary, and close
the mixed-regime perimeter before any continued shock-cell chain can consume
it. Indexed external observations are also still missing; the promotion
review therefore remains a hard data gate, and the fast/basic visualization
and reduced-order providers remain unchanged.

## Euler companion-field planner and continued-chain boundary checkpoint

The locally audited Euler companion strip is now exposed through the planner
contract by `plan_euler_companion_field_reference`. Its
`MocEulerCompanionFieldPlannerResult` preserves the field's typed
`open-physical-closure` termination, reports the local result as
`upstream-coupled-research`, and keeps production claims and chain promotion
disabled. A converged open strip is therefore visible to planning and
validation without being relabeled as a resolved shock cell.

`plan_euler_companion_field_chain_probe` adds the next seam. It accepts an
already resolved planar-MOC seed, records the exact incoming state/total-
pressure handoff, invokes the boundary adapter once, and returns the typed
open-closure stop. The Euler strip is explicitly not converted into a
`MocChainCell`, and the accepted upstream field is never replaced by the
probe. The existing prescribed multi-cell planner mock remains a separate
deterministic contract for exercising repeated state-carrying cells; it is not
used to increase the Euler lane's fidelity.

The standalone validation report now audits both planner boundaries and their
independent chain-planner measurement. This advances the continued-cell
interface while leaving the physics gate unchanged: global reflected
Euler/free-boundary closure, entropy transport, refinement, and indexed
external observations are still required before a continued Euler chain can
be claimed.

## Explicit companion open-field chain checkpoint

The exact ambient-field lane now has a separately named
`assemble_euler_ambient_shock_field_from_companion` route. It accepts only a
solver-owned, state-carrying companion boundary derived from the same exact
shock object, checks the downstream total-pressure lineage, and assembles an
exact open characteristic strip with a positive shock clearance. The
standard ambient march remains the shared-attachment path; on the reference
fixture its first interior wedge has no positive forward margin and therefore
retains `attachment-geometry-failure`.

`MocEulerAmbientShockFieldChainMock` can now consume the explicit separated
route and carry three fresh open fields through two exact state/pressure
handoffs. `op.moc.euler-ambient-shock-field-audit` independently identifies
the `explicit-separated-companion` boundary, reconstructs its ambient
pressure and `C-` invariant residuals, and verifies the non-promotion flags;
`op.moc.euler-ambient-shock-field-chain-audit` rechecks every translated
field, frontier link, and typed `solver-returned-no-next-cell` stop. This is a
positive continued-chain contract for research visualization and planner
integration, not a physical shock-cell chain: no `MocChainCell` is created,
physical closure remains false, and no fast/basic, signature, ray, or
focal-plane-array provider is changed.

The next higher-fidelity gate is still a globally coupled reflected
Euler/free-boundary solve with entropy transport, attachment-aware first-cell
remeshing, refinement, and indexed external observations. The explicit
companion route is a controlled bridge to that work; it must not be used to
backfill or silently upgrade the lower-fidelity products.

## Local exact post-shock topology and continued-field chain checkpoint

The higher-fidelity Euler lane now exposes
`assemble_euler_post_shock_field`. It takes a locally conservative mixed-
characteristic shock that descends to the centerline and has a uniform
downstream state, reflects the compatible `C-` family to the axis, and builds
the interior characteristic rows. The retained mesh has a closed polygonal
topology and a six-sample centerline state/total-pressure frontier on the
reference case.

The last terminal region is completed with an explicitly labelled uniform-
state topology fan. Its center is retained as a synthetic topology sample,
not as a fabricated characteristic intersection. This makes the local field
useful for geometry and visualization while keeping
`physical_closure_verified=false`, `chain_promotion_blocked=true`, and
`production_claim_allowed=false`: the shared ambient/free-boundary attachment,
entropy transport, and physical shock-cell perimeter are still open.

`MocEulerPostShockFieldChainMock` and
`plan_euler_post_shock_field_chain_mock` now reassemble three translated local
fields on fresh domains, preserve exact centerline handoffs, and stop with a
typed `solver-returned-no-next-cell` decision. The independent
`op.moc.euler.post-shock-field-audit` and
`op.moc.euler.post-shock-field-chain-audit` operators remeasure shock jumps,
characteristic geometry, topology, constant-state Euler residuals, domains,
frontier fingerprints, and fidelity flags. This is a controlled continued
field-chain fixture for research visualization and planner work, not a
production shock-cell solver or a change to the fast/basic, signature,
ray-transfer, or focal-plane-array providers.

The next physical gate is a shared-attachment reflected/free-boundary solver
that replaces the local topology fan with a solved downstream perimeter and
transports nonuniform shock entropy. It must pass refinement and indexed
external observations before this chain can be promoted beyond research use.

## Exact ambient-closed physical-field checkpoint

`assemble_euler_ambient_physical_field` is the next solver-owned lane after
the local post-shock topology. It consumes a locally Euler-verified,
mixed-characteristic shock curve, marches its shock-sourced `C+` data to a
pressure-matched ambient boundary, and reuses the reflected centerline
assembler to retain a bounded field and downstream state/total-pressure
handoff. A shaped nine-sample shock fixture now closes that local boundary
with ordered centerline topology and exact local shock jumps.

This is deliberately a physical-field candidate rather than a production
claim. The independent `op.moc.euler-ambient-physical-field-audit` rechecks
the shock jumps, ambient samples, field topology/state sampling, and
conservative cell residuals. The current fixture reaches the geometric
closure checkpoint but remains stopped at the cell-residual/refinement gate;
its variable downstream entropy lineage is reported explicitly. The result
therefore keeps `chain_promotion_blocked=true` and
`production_claim_allowed=false`, and exposes a typed
`fidelity-not-allowed` chain decision instead of silently making a shock-cell
handoff.

The exact ambient lane does not alter the fast/basic visualization,
signature, ray-transfer, or focal-plane-array providers. Continued shock
cells still require independent conservative-cell refinement, a globally
coupled reflected free-boundary/entropy solve, and indexed external
validation data. The shaped fixture is retained as a reproducible
planner/visualization checkpoint while those gates remain open.

## Exact ambient-field first-wedge refinement checkpoint

The independent
`op.moc.euler-ambient-physical-field-refinement` measurement now compares
the exact ambient-closed candidate at declared 9, 17, and 33 sample
resolutions. It remeasures the field and conservative cell residuals rather
than trusting solver flags, and it separately counts the reflected
`post-shock-ambient-centerline-triangle` cells. The reference residual maxima
are approximately `0.189`, `0.178`, and `0.172`, while the first-wedge count
remains exactly `1, 1, 1`.

That result is a typed
`euler_ambient_physical_field_refinement_first_wedge_failure`, not a release
failure: adding samples to the two physical boundary traces does not refine
the terminal wedge. The next implementation gate is an attachment/terminal
wedge remesh or characteristic subdivision that retains state and entropy
lineage on the new cells. Until that gate passes, the exact field remains
available for visualization and planner diagnostics only; no continued
shock-cell chain or lower-fidelity provider may consume it.

The next terminal-wedge seam is now solver-owned rather than an interpolated
subdivision. It reflects the terminal node's ``C-`` characteristic to the
centerline, carries its total-pressure value onto that edge, and retains the
corrected ``C+``/``C-`` triangle as an auditable candidate. The canonical
candidate passes topology, state/pressure lineage, and characteristic
alignment, while the independently recomputed entropy-source and local Euler
residual gates still fail. Its planner records the candidate, contributes zero
physical chain cells, and stops with ``FIDELITY_NOT_ALLOWED``. The next gate
is a multi-cell entropy-carrying terminal remesh coupled to the complete
ambient/reflected free boundary.

The next local field seam now applies a retile to that corrected triangle and
the immediately adjacent centerline strip. The solver replaces only the two
affected cells and the matching centerline sample, retains the untouched
field cells, and exposes the raw snapshot for visualization and audit. The
retiled mesh is connected with one explicit perimeter and all 53 cell vertex
states/total-pressure samples remain finite on the reference case. Its field
status is intentionally ``invariant_failure`` rather than converged, so the
ordinary field sampler and every continued-chain adapter reject it. The
independent
``op.moc.euler-ambient-first-wedge-characteristic-field-audit`` rechecks the
retiled topology, shock/ambient/centerline paths, raw state/pressure samples,
all cell Euler residuals, the terminal entropy audit, and the non-promotion
barrier. The canonical result remains an expected entropy/Euler boundary with
zero physical chain cells; it is not a production field and does not alter
the basic visualization, signature, ray-transfer, or focal-plane-array
providers.

## Entropy-carrying refinement and chain-planner boundary

The first-wedge entropy-carrying candidate now has a separate diagnostic
subcell ladder. ``refine_euler_ambient_first_wedge_entropy_carry`` projects
``theta``, ``nu``, and ``log(p0)`` over the solver-owned triangle and evaluates
the finite-volume Euler residual for each barycentric subcell. The independent
``op.moc.euler-ambient-first-wedge-entropy-carry-refinement-audit`` rebuilds
the projection, topology, pressure lineage, and residuals from raw samples.

The canonical 1/2/3 ladder has side counts 2/4/8, cell counts 4/16/64, and
maximum residuals about 0.01801/0.01223/0.00703. This establishes useful local
resolution evidence, but it is deliberately not the MOC solution: no internal
characteristic family closure or reflected free-boundary coupling is claimed.

The planner mock records each diagnostic refinement step and stops with
``FIDELITY_NOT_ALLOWED`` and zero physical shock-cell entries. The next
implementation work is to replace the barycentric projection with a
solver-owned ``C+``/``C-`` subcell solve, propagate the reflected outer/front
boundary through the refined mesh, and then repeat full-field conservation,
refinement, and indexed-observation gates. None of this changes the fast
visualization or reduced-order product providers.

## Solver-owned characteristic subcell and continued-chain boundary

The barycentric refinement seam now has a separate higher-fidelity solver
lane: ``solve_euler_ambient_first_wedge_entropy_characteristic_field``. It
builds a deterministic four-triangle first-wedge field from the entropy-carry
source trial, with split shock/ambient source edges, a reflected centerline
node, six typed characteristic edges, and carried log-total-pressure
lineage. The canonical field closes its local family-compatibility and
conservative cell-residual gates, and
``op.moc.euler-ambient-first-wedge-entropy-characteristic-field-audit``
independently reconstructs topology, state samples, pressure lineage,
characteristic residuals, and cell Euler residuals.
It also exposes the exact three-sample ``POST_SHOCK_FIELD_PERIMETER``
frontier in solver-owned order, so a future continued-cell solve can consume
the handoff without reconstructing it from cell order.

The matching planner is intentionally a pre-chain boundary. It records the
six-node/four-cell/six-edge field, then returns a typed
``FIDELITY_NOT_ALLOWED`` decision with zero physical shock-cell entries. The
field is not passed to the generic resolved-chain callback because its
reflected free boundary and external validation are still absent. The
dedicated ``plan_euler_ambient_first_wedge_entropy_characteristic_field_chain``
planner now defines the separate continuation seam. Each callback receives
the exact ``POST_SHOCK_FIELD_PERIMETER`` and may append only a solver-supplied
locally audited field on a fresh downstream domain; open fields are never
converted into ``MocChainCell`` objects. The matching
``MocEulerAmbientFirstWedgeEntropyCharacteristicFieldChainMock`` is an
explicit replay fixture: it defaults to the one-field/no-next-field stop and
does not synthesize translated downstream physics. The independent
``op.moc.euler-ambient-first-wedge-entropy-characteristic-field-chain-audit``
rechecks every retained field, exact handoff fingerprint, fresh-domain link,
and nonphysical termination. This lane is not used to upgrade the
solver-owned field or the fast/reduced-order providers.

The first non-mock continuation attempt is now bounded by
``solve_euler_ambient_first_wedge_entropy_characteristic_shock_coupling``.
It consumes the exact perimeter through the field's finite state and pressure
samplers, invokes the attached-shock marcher, and stops with a typed
``UPSTREAM_FIELD_BOUNDARY`` when the generated path leaves the retained local
field. The corresponding
``plan_euler_ambient_first_wedge_entropy_characteristic_shock_coupling_probe``
records that attempt without fabricating a downstream field, and
``op.moc.euler-ambient-first-wedge-entropy-characteristic-shock-coupling-audit``
independently verifies the retained path coverage, handoff, and status. The
canonical probe therefore demonstrates a real finite-domain coupling seam,
not a completed reflected free boundary or physical shock-cell chain.

The next seam is now explicit as
``solve_euler_ambient_first_wedge_entropy_characteristic_free_boundary``. It
accepts an ambient pressure and outer-angle bracket, consumes the exact
``POST_SHOCK_FIELD_PERIMETER``, and routes only bounded state/static-pressure
samples into the ambient-attachment plus centerline-reflection solver. On the
canonical four-triangle field it records one shock sample and a typed
``UPSTREAM_FIELD_BOUNDARY`` at sample index 1. Its planner/audit pair preserves
zero physical chain cells and an explicit external-validation gate. This is
progress on the coupling contract, not completion of the first physical cell:
the upstream field must still be enlarged or globally remeshed so the shock,
ambient, and reflected characteristic paths can close before continued shock
cell chains are enabled.

Next implementation sequence:

- enlarge or globally remesh the locally closed characteristic subcells so the
  solver-owned reflected outer/front boundary can retain a complete physical
  perimeter;
- preserve that perimeter through the same typed handoff used by continued
  shock-cell planners, with no extrapolation or pressure reset;
- repeat independent Euler audits over a declared resolution ladder and bind
  indexed external observations before any physical chain-cell promotion;
- keep the planner mock and the higher-fidelity lane separately labeled in
  visualization reports so exploratory chain views cannot be mistaken for a
  production solver.

## Bounded continued shock-cell-chain source band

The first solver-owned continuation beyond the finite entropy field is now
implemented as ``solve_euler_ambient_first_wedge_entropy_characteristic_continuation``.
It solves alternating variable-entropy ``C-`` centerline reflections and
``C+`` ambient-boundary segments, transports the retained log-total-pressure
gradient, and emits a bounded seven-cell source band for the canonical
four-cycle fixture. The outgoing perimeter is a typed two-sample ``C-``
handoff, so the next research solver has a concrete frontier rather than a
translated or interpolated mock field.

The associated
``plan_euler_ambient_first_wedge_entropy_characteristic_continuation_probe``
records this source band as one planner attempt and terminates with
``OPEN_PHYSICAL_CLOSURE``. It never creates a synthetic downstream field or
physical ``MocChainCell``. The explicit replay planner mock remains separate
and continues to serve deterministic field-sequence tests.

The independent
``op.moc.euler-ambient-first-wedge-entropy-characteristic-continuation-audit``
recomputes segment geometry, variable-entropy compatibility, pressure
transport, ambient matching, topology, and conservative cell residuals. The
canonical source band passes the local characteristic audit and has finite
Euler residuals, but its maximum residual is approximately ``0.01812``
against the current ``0.01`` gate. The next implementation gate is therefore
conservative refinement of this variable-entropy band, followed by a coupled
Euler shock/free-boundary closure and indexed external validation before any
continued shock-cell chain can be promoted.

## Continuation-band projection refinement checkpoint

The bounded source band now has an independently audited diagnostic resolution
ladder through
``refine_euler_ambient_first_wedge_entropy_characteristic_continuation``.
For side counts ``1, 4, 12, 16``, it produces ``7, 112, 1008, 1792``
projected triangular cells. The independently recomputed maximum conservative
Euler residuals are approximately
``0.01812, 0.01714, 0.00745, 0.00577``. The ladder therefore passes its
finite, structural, pressure-lineage, topology, monotone-reduction, and final
``0.01`` residual gates.

This is resolution evidence, not a newly solved characteristic net: the
subcells are a barycentric projection in ``theta``, ``nu``, and ``log(p0)``.
The planner records the ladder but still stops at ``OPEN_PHYSICAL_CLOSURE``
with zero physical chain cells. The next solver task is an intra-cycle
``C+``/``C-`` characteristic remesh that reproduces this residual trend while
closing the reflected/free-boundary perimeter; only then can the physical
shock-cell chain and external-observation gates be evaluated.

## Solver-owned characteristic-edge remesh checkpoint

The next fidelity seam is now a separate solver-owned remesh:
``remesh_euler_ambient_first_wedge_entropy_characteristic_continuation``.
For each source triangle it solves the two slanted characteristic edges as
short variable-entropy boundary-value traces and caches each shared edge in
one canonical orientation. The bounded implementation supports the
power-of-two interval ladder ``1, 2, 4, 8, 16, 32``, producing
``7, 28, 112, 448, 1792, 7168`` triangular cells and 8 shared characteristic
edge traces on the canonical four-cycle continuation source. For every case
above two intervals, the row layout is indexed in characteristic coordinates:
each interior node joins base points on the same C+ and C- source families.
This avoids treating neighboring nodes from different characteristics as a
single trace as the mesh is refined.

The interior row stencil contains
``(n - 1)(n - 2)/2`` C+/C- intersections per source triangle. The ladder
therefore contains 21, 147, 735, and 3255 intersections at 4, 8, 16, and 32
intervals respectively, retaining the source pressures, transported pressure,
both compatibility residuals, and explicit forward-direction margins. All
six meshes are connected, simply bounded open zones with no non-manifold
edges; the open perimeter is retained as evidence rather than filled by
extrapolated cells.

The two-interval case independently passes the characteristic geometry,
variable-entropy compatibility, pressure-lineage, and topology gates. Its
maximum remesh residuals are approximately ``1.19e-8`` for geometry,
``1.68e-7`` for compatibility, and ``8.9e-16`` for pressure transport under
the bounded ``1e-6`` characteristic and ``1e-8`` pressure tolerances. The
independent
``op.moc.euler-ambient-first-wedge-entropy-characteristic-continuation-remesh-audit``
recomputes those edge equations and the cell flux residuals. The conservative
Euler gate remains separate and fails at approximately ``0.02394`` against
the ``0.01`` threshold, so this is a locally coherent remesh, not an accepted
Euler field.

The four-, eight-, sixteen-, and thirty-two-interval cases independently replay
the interior intersection equations and pass the local characteristic and
pressure-lineage gates. Their independently recomputed maximum conservative
Euler residuals are approximately ``0.01732, 0.01374, 0.01186, 0.00918``.
The thirty-two-interval case therefore passes the bounded ``0.01`` local
conservative-Euler gate. This closes the local remesh acceptance gate for the
canonical source band, but does not by itself establish refinement stability
across reflected cases or authorize a physical chain cell.

The matching
``plan_euler_ambient_first_wedge_entropy_characteristic_continuation_remesh_probe``
now records the one-, two-, four-, eight-, sixteen-, and thirty-two-interval
ladder while preserving
``OPEN_PHYSICAL_CLOSURE``, zero physical chain cells, and the explicit
external-validation requirement. This closes the projection-to-solver-owned
edge-and-local-row seam and the canonical local conservative-Euler gate only.
A globally closed reflected/free-boundary shock, indexed external observations,
and physical shock-cell-chain promotion remain pending; the remesh ladder is
not exported as a downstream field or chain-cell provider.

## Bounded remesh reflected/free-boundary probe checkpoint

The thirty-two-interval remesh now exposes a typed, bounded diagnostic sampler
to a separate reflected/free-boundary closure probe:
``solve_euler_ambient_first_wedge_entropy_characteristic_remesh_free_boundary``.
The probe consumes the exact outgoing ``C-`` handoff and only samples states,
static pressure, and total pressure inside the remesh. If the trial shock
leaves that domain, the result retains the covered prefix and first missing
sample as ``UPSTREAM_REMESH_BOUNDARY``; it does not reuse the last state,
extrapolate the field, or infer a physical endpoint.

On the canonical case, the local remesh is characteristic-consistent and its
independent maximum conservative Euler residual is approximately ``0.00918``,
inside the ``0.01`` acceptance gate. The closure probe nevertheless stops at
shock sample ``1`` with one covered sample and first missing index ``1``. Its
independent audit returns a local boundary audit, confirms the remesh and
handoff bookkeeping, and deliberately reports incomplete shock-path coverage;
global reflected/free-boundary closure, external observations, and physical
chain promotion remain false.

The matching
``plan_euler_ambient_first_wedge_entropy_characteristic_remesh_free_boundary_probe``
records this as one typed attempt with one source field, zero continued fields,
zero physical chain cells, no synthetic downstream field, and an explicit
external-validation requirement. This is the planner boundary for the next
implementation increment: enlarge or replace the bounded upstream field with
a globally coupled, Euler-accepted reflected ``C-`` frontier before a physical
shock-cell chain can be extended.

## Outgoing C− frontier coverage checkpoint

The bounded remesh now exposes its exact terminal outgoing ``C-`` edge through
``extract_euler_ambient_first_wedge_entropy_characteristic_remesh_frontier``.
The edge retains the solver-owned curved coordinates, states, transported
total-pressure lineage, and local characteristic residuals in outer-to-
centerline order. This is a diagnostic frontier view; it does not replace the
two-endpoint continuation handoff or turn the remesh into a production field.

The matching
``audit_euler_ambient_first_wedge_entropy_characteristic_remesh_frontier_path``
checks a candidate shock path only against retained remesh cells and the
outgoing frontier. It reports the first missing point as a bounded-domain gap
or as an exterior crossing with a signed offset, without inserting an
upstream state. On the canonical n=4 diagnostic mesh, the first missing shock
sample is classified as ``FRONTIER_EXTERIOR`` about ``3.59e-3 m`` beyond the
frontier. The independent free-boundary audit recomputes this classification,
and the planner records the frontier status and sample count alongside the
closure attempt.

This closes the observability and handoff-diagnosis seam only. The next true
solver task remains a two-sided/global reflected free-boundary solve (or a
separately justified terminal model) that supplies a valid downstream
condition beyond the outgoing frontier. No continued shock-cell-chain cell is
promoted until that solve, refinement-stable Euler evidence, and indexed
external validation all pass.

## Bounded outgoing-frontier bridge checkpoint

The remesh free-boundary probe now has an explicit opt-in
``use_outgoing_frontier_bridge`` lane. It consumes the dense solver-owned
outgoing ``C-`` frontier, solves one variable-entropy ambient ``C+`` segment
from the frontier's centerline endpoint to a new ambient-boundary endpoint,
and uses the resulting three-vertex triangle as a bounded diagnostic source
for the reflected shock march. The remesh itself is unchanged, and the
bridge sampler refuses points outside the bridge or retained remesh cells.

On the canonical thirty-two-interval case, the bridge passes its local
geometry, compatibility, and pressure-lineage equations. With the explicit
zero-strength Mach-wave endpoint contract and nine shock samples, the shock
march reaches the centerline with all nine upstream samples covered; the
coupled physical field reports an ambient-closed local closure probe. The
independent audit reconstructs the bridge triangle and residual equations,
replays the combined bounded sampler, and returns
``CONVERGED_LOCAL_CLOSED_AUDIT``.

This is a terminal closure diagnostic, not a new physical shock-cell-chain
provider. The planner records the bridge status while retaining zero
continued fields, zero physical chain cells, ``FIDELITY_NOT_ALLOWED``, and the
external-validation requirement. The frontier-only coverage report still
shows the shock crossing the original remesh frontier; that crossing is the
declared reason the bridge exists, not evidence that the remesh was silently
extended. A globally continued multi-cell chain remains pending indexed
validation and refinement-stable physical promotion.

## Reflected centerline seam checkpoint

The physical-field terminal-patch adapter now exposes a typed
``MocCenterlineSeamComparisonResult``. It compares the accepted upstream
centerline trace with the axis produced by reflecting the projected terminal
``C+`` trace, and records sample-count, coordinate, state, and total-pressure
residuals together with the first failing sample. The comparison is evidence
only; it does not relax the exact seam requirement or promote a chain cell.

The n=32 bridge regression reaches the terminal patch and then stops with
``STATE_NOT_CARRIED``: both traces have ten samples, the first mismatch is
sample 2 in position, and the maximum coordinate residual is greater than
``1e-2 m`` while state and pressure residuals remain below their tolerances.
This is the measured global reflected/free-boundary gap: the local bridge is
closed, but its reflected axis is not the same axis that closed the upstream
field. The planner therefore retains one accepted source field, zero
continued cells, and the global reconciliation solve remains the next task.

## Automatic physical-field-to-global-remesh planner checkpoint

``plan_reflected_domain_global_shock_remesh_chain_from_physical_field`` now
connects the accepted physical-field boundary to the global remesh planner in
one explicit path. It derives a finite shock/ambient strip, reflects its
terminal ``C+`` trace into a centerline patch, solves a fresh alternating
``C-``/``C+`` source band, and only then runs the bounded global source-pair /
compression-profile sweep. The strip, patch, source-band handoff, and global
attempt reports remain in the planner diagnostics so the continuation can be
replayed and audited without a caller fabricating a source domain.

The canonical reflected-domain fixture now exercises this automatic path and
reproduces the independently measured no-endpoint-closure result. The planner
retains one seed cell, reports zero continued/physical chain cells, and keeps
``chain_promotion_blocked=true`` and ``production_claim_allowed=false``. A
projection failure is also a typed stop; no stale source band or extrapolated
state is substituted. The next physics task is still the globally coupled
reflected shock/free-boundary construction whose axis, shock geometry,
entropy, and Euler residuals close together, followed by refinement and
indexed external validation.

## Geometry-conditioned Euler shock reconciliation checkpoint

The global remesh planner now retains a second, independent interpretation of
each selected shock geometry through
``fit_euler_consistent_shock_boundary_from_geometry``. It derives the local
downstream turn from the actual retained shock tangent, then re-solves the
attached oblique shock and normalized Rankine--Hugoniot jump. This closes the
question "can this stored geometry carry a locally conservative shock?" without
silently treating the existing global attempt's downstream angles as physical
boundary data.

The canonical two-attempt sweep passes this geometry-conditioned local Euler
reconciliation with a mixed-characteristic orientation. The original
downstream-angle fit remains independently recorded and is not replaced. Each
reconciliation is also sent to the exact ambient physical-field assembler as a
coupling probe. Both canonical attempts stop at ambient attachment because the
reconciled post-shock pressure does not match the source-band ambient pressure;
the reports retain that typed failure rather than adjusting the shock or
ambient boundary after the fact.

This is evidence for a local shock-boundary seam only. It does not close the
reflected axis, the downstream characteristic field, or a continued shock-cell
chain. The planner still retains one seed cell, zero physical chain cells,
``chain_promotion_blocked=true``, and
``production_claim_allowed=false``. The next implementation gate is a global
free-boundary solve that couples the remeshed ``C-`` frontier, shock geometry,
ambient attachment, and reflected centerline in one converged problem. The
bounded local version of that coupling is the next checkpoint; refinement and
indexed external observations remain after it.

## Continuous source-frontier Euler closure checkpoint

The global remesh now has a separate
``solve_reflected_domain_global_euler_shock_boundary`` bridge. It consumes the
selected retained shock geometry and the verified alternating source band,
re-samples every shock point without extrapolation, and projects only the
first and last shock segments onto their exact local Mach-wave tangents. The
downstream endpoint is allowed to be a continuous point on the retained
centerline source edge; it is not forced onto the next discrete axis vertex.
That distinction matters because the discrete vertex can require a positive
interior compression through a zero-strength endpoint, which is not a valid
Euler shock boundary.

The bridge carries an explicit zero-strength endpoint contract, then assembles
the ambient-pressure/reflected-centerline characteristic field. On the
canonical two-attempt sweep it closes a 53-cell local field, passes the
independent shock-jump and conservative-cell audit, and reports endpoint
tangent residuals at machine precision. The planner now records this result
and returns ``FIDELITY_NOT_ALLOWED`` rather than an open-closure stop when the
local field closes. The independently measured source seam, geometry, field,
and fidelity flags are retained in the planner report.

This is a locally closed exact-Euler research field, not a production
continued shock-cell provider. Its canonical reflected-free-boundary audit,
resolution ladder, mixed-regime downstream closure, and indexed external
validation are still separate gates. It contributes zero physical chain
cells, cannot update the basic visualization, signature, ray-transfer, or
focal-plane-array lanes, and remains the explicit handoff for the next
refinement and external-observation work.

## Global exact-Euler resolution audit checkpoint

The local bridge now has an independent resolution operator,
``measure_moc_reflected_domain_global_euler_shock_boundary_refinement``. It
accepts caller-retained exact-Euler fields at declared resolutions, reruns no
solver, and independently remeasures the source seam, endpoint Mach-wave
tangents, shock-boundary audit, and conservative cell residuals. The operator
also requires strictly increasing shock sample counts, non-decreasing field
cell counts, finite residuals, at least one residual reduction, and a
converging continuous source-frontier location.

The direct canonical fixture passes the 5/9/11 ladder with 19/53/76 field
cells and decreasing maximum cell Euler residuals of approximately
``5.84e-4``, ``3.61e-4``, and ``3.01e-4``. The standalone solver-generated
report uses its stable 9/11/13 ladder with 53/76/103 cells; its bounded
five-sample attempt is retained as a typed attempt failure rather than being
omitted or treated as a converged coarse case. This keeps resolution evidence
specific to the source lineage that produced it.

Passing this operator is local numerical refinement evidence only. Its report
sets ``canonical_free_boundary_verified=false``,
``canonical_euler_verified=false``, and
``external_validation_verified=false``; it keeps
``chain_promotion_blocked=true`` and contributes no promoted physical cells.
The missing indexed observation archive remains the next gate before any
physical shock-cell-chain promotion or product-provider change.

## Continued shock-cell planner/mock checkpoint

The continued-cell lane now has two deliberately separate fixtures. The
compact ``MocPrescribedPostShockChainMock`` defaults to three cells for unit
tests; the standalone validation artifact configures the same planner for five
cells so the trace contains a meaningful continued prefix and a terminal
``SOLVER_RETURNED_NO_NEXT_CELL`` boundary. The solver-generated five-cell
reference is a separate research fixture and is not treated as the prescribed
mock.

Every accepted mock or reference step consumes the exact prior post-shock
field perimeter, state samples, pressure samples, and total-pressure handoff.
It then creates a fresh downstream domain and field, which lets the independent
chain and planner operators verify contiguous indices, geometry freshness,
hand-off fingerprints, pressure loss, and the terminal decision. A failed
continuation keeps the accepted prefix and returns a typed boundary; it does
not fill the chain with extrapolated or uniform state.

This planner is a contract and audit fixture, not a production shock-cell
model. Prescribed shock geometry, explicit per-cell schedules, and the
solver-generated reference law remain outside the production path. The current
local exact-Euler field and its resolution ladder likewise remain research
evidence: they do not promote cells or alter the basic visualization,
signature, optical-transfer, or focal-plane-array lanes.

The remaining implementation order is therefore explicit:

1. Bind the owner-provided indexed shock-cell archive and verify its
   provenance, digest, coordinates, and calibration/validation split. The
   missing archive cannot be replaced with synthetic observations.
2. Close a canonical reflected free-boundary/mixed-regime field that couples
   the continued ``C-`` frontier, shock geometry, ambient attachment, reflected
   centerline, entropy, and Euler residuals in one solve.
3. Extend the exact-Euler resolution ladder over additional reflected and mild
   attached/overexpanded cases, with a stable physical terminal criterion.
4. Implement production next-cell shock fitting from the typed state and
   total-pressure frontier without prescribed geometry or template schedules.
5. Run disjoint external comparison and promotion review, then consider only a
   dedicated resolved-planar-MOC provider. No result may flow backward into a
   lower-fidelity product lane.

## Exact-Euler frontier handoff checkpoint

The exact-Euler ambient/centerline bridge now accepts an optional typed
incoming ``MocChainBoundarySample`` frontier. It validates the trace before
solving, passes the frontier into the physical-field assembler, and verifies
that the assembled field retained the same state and total-pressure samples
exactly. The global reflected-shock closure forwards its source-band handoff
through this seam and exposes an independent
``incoming_handoff_verified`` measurement gate.

This closes a real data-lineage gap: the global field can now carry the prior
cell's frontier for a future research continuation instead of merely checking
the handoff before solving. It still does not promote a ``MocChainCell``. The
global result remains below the canonical mixed-regime/free-boundary closure,
indexed validation, and production next-cell fitting gates, and the fast,
basic-visualization, signature, optical-transfer, and focal-plane-array lanes
remain unchanged.

## Global exact-Euler continued-chain research adapter

The locally audited global exact-Euler field can now seed a separate research
chain adapter. The adapter carries the field's exact typed frontier into the
existing terminal-reflection/ambient-closure continuation reference, captures
each newly solved field, and independently remeasures the resulting chain. The
validation fixture exercises three resolved fields and a typed
``SOLVER_RETURNED_NO_NEXT_CELL`` stop, with fresh-domain and handoff-link
checks across the continuation.

This is an explicit fidelity transition: ``global-exact-euler`` is used for
the local seed, while the downstream cells use the terminal-reflection patch
reference. The transition is recorded in diagnostics and cannot authorize a
canonical reflected free-boundary claim, external validation, production
next-cell fitting, or any lower-fidelity product provider.

## Global exact-Euler fresh-source continuation checkpoint

The continued global-Euler lane now has a second, stricter research adapter:
``plan_reflected_domain_global_euler_continued_chain``. It does not hand the
seed to the lower-cost terminal-patch chain reference. For every accepted next
cell it projects only the current field's finite shock/ambient strip, solves a
new centerline reflection patch, solves a new alternating source band, reruns
the bounded global shock remesh, and closes a new exact-Euler ambient/
centerline field. Source-band fingerprints are retained so a reused geometric
front cannot satisfy the freshness gate.

The physical-field chain audit now accepts an explicit intercell bridge. The
bridge records the previous ambient endpoint and the next shock/ambient
attachment, while the planner diagnostics retain the reflected patch and
source-band stages that connect them. This is necessary because the next
global-Euler field begins at a newly solved source interface rather than at the
previous field's ambient endpoint; an axial gap is therefore never silently
treated as a shared interface.

The standalone validation fixture first reconciles an accepted physical seed
field through an independent nine-point attached-shock scalar reference, then
exercises three resolved exact-Euler fields, two independently measured fresh
source/remesh/Euler steps, distinct source fingerprints, verified intercell bridges, and a typed
``SOLVER_RETURNED_NO_NEXT_CELL`` stop. The lane remains planning-only:
canonical reflected free-boundary/mixed-regime closure, indexed external
observations, refinement across additional cases, and production next-cell
fitting are still required. Nothing from this lane flows backward into the
fast/basic visualization, signature, optical-transfer, or focal-plane-array
providers.

## Variable-entropy terminal planner reference checkpoint

The terminal planner now has a fourth, explicitly named downstream mode:
``solver-owned-variable-entropy-reference``. After the continued reflected
prefix reaches its typed normal-shock stop, this mode consumes the exact
shock-interface entropy handoff and builds its own vertical control section.
The section carries the reverse-mapped total-pressure profile and local
isentropic state data into the variable-entropy free-boundary reference; it is
reported beside the supersonic chain and is never appended as another shock
cell.

The scalar mixed-regime pressure-lineage gate remains strict by default. A
distributed total-pressure profile can pass only through an explicit opt-in
used by the variable-entropy solver, and its source mapping is then rechecked
by the independent variable-entropy measurement operator. The canonical
scalar closure, field attachment, chain-promotion, and production-claim gates
remain false for this reference, even when its local mapped mesh converges.

Focused regressions cover the new planner mode, exact seam retention, the
distributed-profile boundary, mode exclusivity, and the no-attachment fidelity
boundary. The remaining gates are a coupled two-dimensional subsonic/Euler
closure, indexed owner-provided validation observations, additional
resolution/case evidence, and production next-cell shock fitting. No output
from this reference changes the basic visualization, signature,
optical-transfer, or focal-plane-array providers.

## Continued-band local reflected-closure chain checkpoint

The next planner seam is
``plan_euler_ambient_first_wedge_entropy_characteristic_continuation_closure_chain``.
For each accepted downstream band it retains the exact source continuation,
solver-owned characteristic remesh, dense outgoing ``C-`` frontier bridge,
and reflected/free-boundary field candidate as one typed result. The reference
planner uses the n=32 remesh gate and the opt-in outgoing ``C+`` bridge; the
explicit ``MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationClosureChainMock``
replays caller-supplied candidates through the same provenance checks without
synthesizing a field.

The integrated two-band fixture produces two independently locally closed
53-cell field candidates and then records a typed
``SOLVER_RETURNED_NO_NEXT_CELL`` stop. The independent
``op.moc.euler-ambient-first-wedge-entropy-characteristic-continuation-closure-chain-audit``
recomputes the continuation, remesh, and free-boundary audits and verifies the
source, incoming-frontier, entropy-gradient, remesh, closure, fresh-domain,
step-record, and termination links. A coarser n=16 case stops at the Euler
residual gate, so the closure bridge cannot bypass conservative acceptance.

These 53-cell fields are local closure candidates in separate solver-owned
coordinate domains, not physical intercell ``MocChainCell`` objects. The
planner and audit therefore report ``local_physical_closure_count=2`` but
``physical_chain_cell_count=0``, keep ``chain_promotion_blocked=true``, and
require global source-frontier reconciliation, refinement across cases, and
indexed external validation before production next-cell shock fitting. No
candidate can update the basic visualization, signature, ray-transfer, or
focal-plane-array providers.

## Global frontier reconciliation checkpoint

The next long-goal slice is now implemented as an explicit solver-owned
reconciliation result. For every accepted continued closure band, the
reconciler re-extracts the exact outgoing ``C-`` remesh frontier, matches it to
the retained continuation endpoints and closure frontier record, and then
checks the adjacent-band seam through the exact compressed handoff. It records
frontier fingerprints, sample counts, endpoint residuals, axial ordering, and
positive downstream band spacing without fabricating a state in the intervening
domain.

The independent validation operator repeats the closure-chain audit and
re-extracts the frontiers before accepting the stored result. The validation
script also runs three real two-band cases with outer-angle half-widths of 1,
2, and 5 microradians at the n=32 local remesh resolution. All three retain
two 33-sample frontiers and one verified seam, providing cross-case stability
evidence for this research lane.

The reconciliation and case ladder remain below physical promotion. They do
not prove dense pointwise inter-band continuity, solve the missing globally
coupled reflected/mixed-regime field, consume indexed owner validation data, or
create ``MocChainCell`` objects. The next work remains physical canonical
closure, additional resolution and reflected/attached cases, external
calibration/validation comparison, and production next-cell shock fitting in a
dedicated resolved-planar-MOC provider. Lower-fidelity visualization,
signature, optical-transfer, and focal-plane-array providers remain isolated.

## Cross-case downstream-gate observability checkpoint

Each fresh global-Euler resolution report now carries the selected downstream
continuation law, its ``downstream_boundary_closure_verified`` gate, the
promotion blockers, and the complete promotion-gate map.  The named
reflected/mild-attached cross-case aggregate preserves those values per case
and per resolution rather than collapsing them into one local-convergence
flag.  The current compression-envelope law is therefore visible in every
case ladder while the solver-owned downstream closure gate remains false.
This is evidence plumbing, not a physical closure result; canonical
reflected/mixed-regime solving and external validation remain required.

## Fresh global-closure refinement-run checkpoint

The global-Euler refinement lane now has an executable run wrapper:
``run_moc_reflected_domain_global_euler_shock_boundary_refinement``. It keeps
one verified source band fixed, invokes the global physical-closure solver once
for every declared shock sample resolution, retains typed closure failures, and
passes only the complete retained ladder to the independent refinement
measurement. The run report carries a deterministic source-band fingerprint,
configuration fingerprint, per-resolution solver status, and the local
physical-closure/fidelity checks needed to distinguish a real resolution run
from a hand-assembled result list.

This improves reproducibility evidence but does not change the physical claim
ceiling. Even a converged fresh ladder remains a bounded local exact-Euler
research result: chain promotion stays blocked, canonical reflected
free-boundary and dense frontier coupling remain open, and indexed external
validation is still required. The next physics work is to replace the current
research downstream turn/perimeter law with a solver-owned globally coupled
reflected/mixed-regime closure, then repeat this runner across reflected and
mild-attached cases before considering production shock-cell fitting.

## Dense source-frontier audit checkpoint

The global exact-Euler measurement now exposes the dense source handoff rather
than reporting only its terminal centerline state. For every retained shock
sample, the independent operator re-extracts the bounded source state, static
pressure, and total pressure and compares them with the upstream evidence
carried by the Euler shock curve. The report records the sample count and the
maximum state, static-pressure, and total-pressure residuals. A tampered
interior pressure sample is therefore rejected as a typed frontier failure,
even when the local shock curve itself still reports convergence.

This closes an observability and provenance gap; it is not a new physical
closure law. The candidate remains a bounded local exact-Euler research field:
canonical reflected/free-boundary, coupled mixed-regime, refinement,
provider-bound validation, chain promotion, and production claims remain
blocked. The next implementation slice is solver-owned downstream boundary
closure, followed by repeated reflected/mild-attached case and resolution
evidence.

## Named reflected/mild-attached case-ladder checkpoint

The global exact-Euler refinement lane now has an explicit cross-case contract:
``MocReflectedDomainGlobalEulerShockBoundaryCrossCase`` names a regime, owns a
solver-generated source band, and declares that case's resolution ladder.
``run_moc_reflected_domain_global_euler_shock_boundary_cross_case_refinement``
executes the existing fresh-ladder runner separately for every named case.
The independent aggregate measurement preserves the per-case ladders rather
than flattening different physical inputs into one residual trend, verifies
the source-band fingerprints and case ordering, and rejects duplicate source
inputs that could masquerade as broader coverage.

The new runner can therefore carry reflected and mild-attached source cases
through the same local exact-Euler audit while retaining an auditable case
identity. The test matrix exercises a reflected source and a distinct
resampled source, and verifies that every run remains fidelity-isolated with
promotion blocked. This is still only local research evidence: the source
bands use the current research downstream law, canonical globally coupled
reflected/mixed-regime closure is not proven, indexed external observations
are absent, and no production shock-cell, Signature, ray-transfer, or
focal-plane-array claim is enabled.

## Higher-fidelity MOC visualization checkpoint

The standardized planar-MOC visualization now carries the solver-owned exact
shock evidence when a retained result exposes it.  The common station bundle
can show shock height, tangent and wave angles, downstream turn, static and
total-pressure loss ratios, and the individual plus maximum
Rankine--Hugoniot residuals.  It also records the global-Euler status,
orientation, closure flags, and entropy diagnostic beside the existing cell
polygons and physical boundary paths.

These channels are interpolated only over the retained shock-domain interval
and are omitted when a displayed station falls outside that interval or when
the source array is incomplete.  The field remains a 2-D research display;
the new observability does not create a resolved radiation medium, promote a
shock cell, or change the canonical/refinement/external-validation gates.

## Downstream-boundary readiness checkpoint

Global physical-closure reports now name the selected downstream continuation
law and carry an explicit ``downstream_boundary_closure_verified`` gate.  The
current bounded compression-envelope law remains research-only and cannot
pass that gate.  This makes the next physics seam precise: implement a typed
solver-owned reflected/mixed-regime downstream boundary, then repeat the
global case and resolution ladders before fitting a production shock-cell
chain.  A local exact-Euler field or a renamed envelope is not sufficient.

The closure now retains that seam as a typed downstream-boundary result.  It
records the solver-carried boundary points, state and pressure samples,
point/segment residual evidence, selected continuation-law identity, and
separate solver-owned, boundary-condition, and mixed-regime-field checks.  The
current compression-envelope result is explicitly tagged research-only, and a
status relabel cannot make its closure flag pass.  This is an auditable solver
handoff contract, not the missing physics itself: the canonical implementation
must still solve the reflected/mixed-regime downstream field and then rerun
the case and resolution ladders before production shock-cell fitting.

The typed handoff is now independently auditable through
``measure_moc_reflected_domain_downstream_boundary``.  That operator
reconstructs the retained coordinate, pressure, ambient-pressure, and tangent
residual channels and rejects altered sample data.  Its successful result is
still explicitly research-only; the coupled mixed-regime field and all
downstream promotion gates remain open work.

The next orchestration seam now binds that verified global closure to the
constant-gamma coupled-Euler request and retains the coupled-field audit under
the same closure fingerprint.  A compatible research case reaches a locally
audited downstream field, while the actual ambient case retains the typed
transonic-frontier failure.  This is intentionally not called global closure:
the downstream response has not yet been iterated back into the upstream shock
solve, so ``global_coupling_verified`` and the downstream closure gate remain
false.  The same orchestrator can carry an independently audited
physical-field continuation and shock-front condition explicitly, so this
research lane does not need to fall back to a scalar inlet when exact field
lineage is available.

The orchestrator now has a solver-owned exact-handoff path as well.  When the
request selects ``SOLVER_OWNED_PHYSICAL_FIELD_CONTINUATION_PROFILE`` without
profiles, it chooses a full-span cross-section from the retained global field,
re-samples the exact continuation, binds the retained shock/ambient/centerline
neighbors, and independently audits the complete handoff before the coupled
solver starts.  Any placement, sampling, or neighboring-condition failure is
typed; no scalar branch or lower-fidelity fallback is attempted.  This closes
the caller-assembly seam only.  The downstream response is still not iterated
back into the upstream shock solve, so ``global_coupling_verified`` remains
false and canonical closure, refinement, physical cell length, and external
validation remain open.

## Typed variable-entropy audit checkpoint

The terminal-patch planner now retains the independent variable-entropy
free-boundary measurement as a typed field beside the solver reference rather
than only serializing it inside a diagnostics mapping.  The planner validates
that the measurement points to the exact reference instance it audited, and
its verification property requires the measurement operator's complete local
gate set.  Reports include the full measurement record for downstream
reviewers and case-ladder tooling.

This is evidence plumbing for `P2.1`, not a canonical closure result.  The
variable-entropy reference still uses a mapped stream-tube model, keeps
``physical_closure_verified=false``, blocks chain promotion, and cannot seed a
production shock cell.  The next physics step remains a coupled reflected
2-D Euler/free-boundary solver with refinement and accepted external
measurement evidence.

## Conservative Euler residual audit checkpoint

The variable-entropy reference now retains a normalized conservative flux
audit over every triangular cell.  It reports separate mass,
streamwise-momentum, transverse-momentum, and energy residual maxima plus
their combined Euler maximum.  ``measure_mixed_regime_variable_entropy_free_boundary``
reconstructs those fluxes independently and rejects altered reported values,
so this checkpoint distinguishes an auditable residual measurement from a
solver claim.

The residuals are evidence of the remaining P2.1 gap, not a closure gate: the
mapped stream-tube field still keeps
``physical_closure_verified=false``, ``canonical_euler_verified=false``, and
chain promotion blocked.  The next implementation step remains a coupled
reflected 2-D Euler/free-boundary solve whose residuals can be reduced and
independently validated across a resolution ladder.

## Variable-entropy resolution-ladder checkpoint

The variable-entropy reference now has a separate independent refinement
operator,
``measure_mixed_regime_variable_entropy_free_boundary_refinement``.  It
remeasures each case from its retained request, entropy handoff, and control
section, requires a strictly increasing resolution sequence and actual mesh
growth, and compares the post-entrance free-boundary segment at normalized
axial locations.  The current 5/7/9-station regression ladder passes with
node/cell counts of 21/27, 29/39, and 37/51; outlet-height deltas are zero and
post-entrance shape deltas remain below ``5e-10 m``.

The two seeded entrance stations remain covered by the single-case audit but
are intentionally excluded from the converged-shape comparison because their
locations are resolution-dependent in this mapped reference.  The ladder
also retains the independently reproduced conservative-Euler maxima
(``1.52``, ``2.60``, and ``3.14`` for the current cases) without requiring
them to decrease; their growth is diagnostic evidence of the unresolved
coupled closure.  This is numerical-sensitivity evidence for a research
reference only: it does not close the canonical downstream field, authorize a
continued chain, or change any product/release gate.

## Global-to-mixed-regime boundary-reference checkpoint

The candidate branch now exposes an explicit solver-owned boundary packet
through ``MocReflectedDomainMixedRegimeBoundaryRequest`` and
``MocReflectedDomainMixedRegimeBoundaryResult``.  The request is derived from
the retained global exact-Euler shock curve: zero-strength endpoint samples
are not treated as entropy-producing patch samples, the remaining strictly
lossy downstream states form the open supersonic patch, and a new scalar
normal-shock terminal is solved at the curve's centerline endpoint.  The
terminal, patch, entropy handoff, and axis-aligned control section are bound
to the exact global closure fingerprint and incoming frontier, so an altered
or reused upstream handoff cannot be substituted silently.

The independent operator
``measure_reflected_domain_mixed_regime_boundary`` rederives the global shock
binding and terminal scalars, then delegates the field-as-data audit to the
existing variable-entropy measurement without invoking its solver.  The
result carries separate geometry, pressure/total-pressure, entropy,
tangency, and control/frontier checks.  It also carries independent mass,
streamwise-momentum, transverse-momentum, energy, and combined-Euler residual
maxima with explicit per-channel coverage and validity masks.  A reported
conservative residual mutation is rejected by the measurement operator.

This is intentionally a solver-bound research reference rather than a
canonical mixed-regime field.  The current physical ambient pressure produces
a typed strict-subsonic pressure-unreachable stop because the retained global
shock interface remains too high in total pressure; a separately declared
reference ambient pressure exercises the mapped variable-entropy field and
its full audit.  Even when that audit passes, ``mixed_regime_field_verified``
and ``physical_closure_verified`` remain false, chain promotion remains
blocked, and no production claim is enabled.  The next physics seam is still
the coupled reflected 2-D Euler/free-boundary solve, followed by repeated
case/resolution evidence.

## Coupled-Euler pressure-budget checkpoint

The coupled finite-volume research result now carries a typed pressure-budget
diagnostic independently rederived from the outer control-section total
pressure.  It reports the isentropic strict-subsonic pressure bounds, the
maximum total pressure compatible with the requested ambient target at the
sonic limit, and the minimum additional total-pressure reduction implied by
that bound.  The actual global case is below the bound and requires about
47.5% additional reduction for the current fixture; the compatible research
fixture is within the range.

This is deliberately non-gating evidence.  A continued two-dimensional
shock/mixing solve can add entropy and change the budget, so the diagnostic
does not replace the canonical reflected free-boundary/Euler closure, refine
the production shock-cell fit, or authorize any product claim.  The next
physics seam is a solver-owned continued supersonic/mixed-regime closure with
its own independent audit and cross-case evidence.

## Retained transonic-transition lineage checkpoint

The coupled constant-gamma research result now retains the scalar
transonic/normal-shock pressure reference that is derived from its actual
outer control-section sample.  The result also retains the independent scalar
audit, and the coupled-field audit verifies the exact control-section binding,
transition request, scalar invariants, and audit values.  A mutation of the
transition evidence therefore fails as a typed transition-audit failure
instead of remaining a disconnected diagnostic.

This closes the evidence-lineage seam only.  The scalar reference still does
not place a shock in the 2-D mesh, transport entropy through the mixed-regime
field, close the free boundary, or create a physical ``MocChainCell``.  The
canonical field, resolution ladder, accepted physical shock lengths, and
external product validation remain required before any production promotion.

## Entropy-inequality evidence checkpoint

The coupled constant-gamma field and its independent audit now distinguish
entropy loss from entropy production.  A shock or numerically resolved
compressive layer may increase the entropy proxy; the local gate rejects only
loss below the inlet entropy envelope and retains the maximum production
fraction for inspection and visualization.  The independent audit recomputes
both values and rejects a tampered report.

This corrects the direction of the research-lane entropy gate but does not
identify a resolved shock, close the free boundary, establish a refinement-
stable physical field, or authorize a chain cell.  The actual global case
still remains an explicit free-boundary failure, and the production,
canonical, and external-validation gates remain open.

## Cell-wise regime-evidence visualization checkpoint

The coupled-Euler visualization now carries a per-cell
``entropy_production_fraction`` field when the solver retains that evidence,
and adds explicit ``subsonic_mask``, ``near_sonic_mask``, and
``supersonic_mask`` channels.  The near-sonic display band is the recorded
``|M-1| <= 0.05`` interval.  The independent coupled-Euler audit recomputes
the entropy map and rejects altered cell values, so the displayed regions are
traceable to the retained conservative field.

This is a diagnostic visualization seam, not a shock detector: entropy excess
may include numerical compression or unresolved mixing, and a near-sonic
mask is not a resolved shock boundary.  The global field remains
non-promotable until a solver-owned mixed-regime closure, stable refinement,
and accepted external measurements exist.

The coupled-Euler refinement runner now carries the maximum entropy-production
fraction at every resolution and requires the independent per-cell map audit
before reporting a locally consistent ladder.  This closes the resolution-
evidence provenance seam for the new visualization channel; it does not
reduce the conservative residuals or promote the research field.

## Characteristic-inlet closure checkpoint

The coupled constant-gamma field now exposes two explicit inlet treatments:
the legacy full-state Rusanov boundary and a subsonic-characteristic boundary
that preserves the outgoing acoustic invariant while retaining caller-owned
total pressure, total temperature, and flow direction.  The latter is
independently re-derived by the coupled-field audit, so its residual evidence
cannot be accepted by accidentally auditing the old full-state flux.

The compatible pressure-seam fixture converges locally with this boundary and
passes the independent audit.  The actual global target has no admissible
subsonic characteristic root; it is therefore retained as a typed inlet
characteristic failure.  The result makes the missing transonic/supersonic
branch or shock-placement solve explicit without turning a boundary failure
into a physical first cell.  Canonical reflected closure, refinement,
accepted physical shock lengths, and external validation remain open.

## Scalar transonic branch-state handoff checkpoint

The scalar transonic reference now accepts caller-owned total temperature and
can emit a typed ``MocTransonicShockState``.  It reconstructs the upstream
supersonic and downstream subsonic state on the normal-shock branch, including
static pressure/temperature, density, sound speed, velocity, total-pressure
ratio, and entropy increase.  Its independent audit rederives all of those
quantities.  The coupled-Euler request binds the state handoff to the exact
reference total temperature, and the planar visualization publishes the
branch-state quantities as traceable research diagnostics.

This closes the thermodynamic handoff needed by a future placed transition;
it does not place the shock, select its orientation or location, continue the
neighboring 2-D characteristic field, close the free boundary, or authorize a
shock-cell length.  The next physics packet remains a solver-owned
transonic/supersonic interface with geometry and cross-case validation.

The independent handoff audit now additionally checks normalized mass,
momentum, and total-energy flux jumps across the reconstructed state.  These
residuals are carried through the coupled-Euler audit and visualization
diagnostics, and tampering with the downstream state invalidates the seam.
This is a conservative scalar checkpoint only; it does not promote the state
into a physical planar shock or continued-cell chain.

## Transonic placement evidence checkpoint

A bounded sensitivity probe of the actual coupled-Euler case varied the
research free-boundary pressure relaxation from `0.05` to `0.5` and allowed
thirty shape iterations.  The pressure residual remained approximately
`133--174 kPa` against the `212.166 kPa` ambient target, and the larger
relaxations exceeded the declared normal-velocity tolerance.  Extending the
shape relaxation envelope reduced the best pressure residual only to about
`115 kPa` while the normal-velocity residual fraction rose to about `0.168`.
The case therefore cannot be closed by shape-iteration tuning alone.  Its
control-section static pressure is approximately `564.587 kPa`, and the
independent scalar transition identifies the required supersonic-to-subsonic
branch.

This is a numerical-boundary diagnosis, not a physical closure result.  It
keeps the actual case as a typed free-boundary failure and identifies the next
solver-owned seam: an internal shock-placement/mixed-regime boundary that
couples the scalar branch state to the two-dimensional field, followed by
independent residual and refinement evidence.  No shock-cell length or product
provider may consume this sensitivity result.

## Caller-owned transonic geometry-binding checkpoint

The scalar branch state now exposes a typed research binding to a caller-owned
shock point and normal.  The binding resolves the normal/tangential velocity
components and carries normalized mass-, momentum-, and energy-flux residuals;
``measure_moc_transonic_shock_geometry`` independently rederives those values
and rejects misaligned or tampered results.

This is an interface seam for the future placement solver, not a placed
two-dimensional shock.  The point and normal are supplied by the caller, no
neighboring characteristic field or entropy transport is solved, and the
result remains barred from ``MocChainCell`` promotion and production claims.
MOC-1 still requires solver-owned placement and mixed-regime closure before
physical shock length, refinement, or external validation can be accepted.

## Scalar post-shock downstream-field checkpoint

The coupled Euler research solver now has an explicit
``scalar-normal-shock-branch`` inlet mode.  It requires the independently
audited scalar shock point/normal, binds the branch downstream state to the
request's gamma, gas constant, total temperature, and ambient target, and
solves the resulting downstream material-streamline field.  The independent
coupled-Euler measurement rederives the branch state, conservative field
residuals, entropy map, pressure boundary, and tangency evidence.

The actual low-ambient fixture now closes this bounded downstream field
locally, while the original control-section-driven solve remains a typed
free-boundary failure.  The new mode does not claim that the upstream field
has reached the branch or that the shock is globally placed; the visual lane
shows only a caller-bound marker and keeps ``MocChainCell`` and production
promotion blocked.  The next MOC-1 work is a solver-owned attachment/transport
of this branch into the upstream two-dimensional characteristic field.

## Solver-owned transonic field-attachment checkpoint

The MOC lane now has a bounded ``MocTransonicShockFieldAttachmentRequest``.
It searches the retained, locally consistent upstream characteristic field for
the deterministic best node match to the audited scalar branch using Mach,
flow angle, gamma, static pressure, and total-pressure lineage.  A matching
node is then bound to the scalar normal-shock geometry, and an independent
measurement operator reselects the node and rederives the geometry audit.

This closes a real field-to-branch evidence seam without pretending that the
field solver has placed a shock: no extrapolation, free-boundary update,
upstream transport, or downstream mixed-regime coupling is performed.  Missing
field sampling and state mismatch are typed failures, and the attachment
remains blocked from ``MocChainCell`` promotion and production claims.  The
next MOC-1 packet is a solver-owned characteristic transport/placement solve
that can connect this local attachment to the reflected frontier and then
re-run conservative closure and refinement evidence.

The standardized planar visualization now accepts this attachment result
directly.  It adapts the retained upstream cells and frontier into the common
renderer-neutral field view, adds separate branch and selected-node markers,
and publishes the node-match and geometry-audit residuals.  The adapter keeps
the marker diagnostic-only and does not invent a shock boundary or turn the
attachment into a production visualization claim.

## Solver-owned bounded characteristic-transport checkpoint

The attached branch can now be advanced through the retained upstream field
along a declared characteristic family.  The transport result retains exact
field samples, total-pressure lineage, characteristic geometry residuals,
variable-entropy compatibility residuals, forward-advance margins, and the
first unavailable point.  It stops at the bounded field boundary without
extrapolation, downstream state invention, or hidden fallback to another
fidelity.

An independent transport measurement re-solves the request, re-samples every
state and pressure value, recomputes all residuals, and verifies the boundary
stop.  This closes a bounded coverage/lineage seam for MOC-1 only.  It does
not choose a global shock position, connect a neighboring reflected field,
close the mixed-regime free boundary, authorize a physical shock-cell length,
or permit chain or production promotion.  The next gate remains solver-owned
shock placement with neighboring-field coupling and conservative mixed-regime
closure, followed by refinement and external validation.

The common planar visualization now accepts this transport result directly.
It renders the retained characteristic trace as a named path and carries the
transport status, termination, sample/segment counts, residual maxima, and
first-unavailable point as diagnostics.  The attachment marker and trace are
kept distinct from a fitted global shock boundary, and the visualization
retains the research-only claim ceiling.

## Solver-owned bounded frontier-placement checkpoint

The next MOC-1 seam now searches the retained transported path for one
in-domain intersection with a typed neighboring frontier.  Placement accepts
only a ``RESOLVED_PLANAR_MOC`` frontier, interpolates the retained state and
log-total-pressure lineages at the intersection, checks state and pressure
seam residuals, and binds the scalar shock geometry to the frontier tangent.
An independent placement operator re-solves the intersection, recomputes the
seams, and re-audits the scalar geometry.

This is deliberately a bounded placement result rather than global reflected
closure.  Prescribed or reduced-order frontiers, ambiguous intersections,
missing intersections, state/pressure mismatches, and failed geometry audits
are typed stops.  Even a verified local placement keeps physical closure,
continued-chain promotion, physical shock-cell length, production Signature /
FPA claims, and external validation disabled until the neighboring field,
mixed-regime boundary, conservative residual, refinement, and validation
gates are complete.

The standardized planar visualization now unwraps the retained field through
the placement request, shows the neighboring frontier and intersection as
separate named paths, and carries the frontier fidelity, segment/fraction,
seam residual, and promotion-block diagnostics.  It does not relabel the
frontier as a global shock boundary or alter any lower-fidelity provider.

## Global/coupled downstream boundary-response checkpoint

The coupled finite-volume result now retains one static-pressure sample for
each axial cell column adjacent to its retained free boundary.  The
global-to-coupled orchestrator uses those solver-owned adjacent-cell values
to reconstruct the boundary-station pressure comparison against the exact
global ambient-neighbor path, and compares both paths only over their shared
x-domain.  The response operator requires ordered stations and rejects a
downstream point outside the retained global path; there is no extrapolation,
clipping, or lower-fidelity replacement.

The resulting research record contains matched points, geometric and tangent
residuals, pressure residuals, normal-velocity residuals, signed correction
offsets, coverage, and the declared tolerances.  The compatible fixture is
covered but remains a typed
overlap residual failure, which makes the unresolved boundary mismatch
visible without changing ``global_coupling_verified`` or the downstream
closure gate.  This is the quantitative input to the next solver-owned
global-frontier feedback iteration; it is not a canonical reflected field,
physical chain cell, or product claim.

## Global/coupled response refinement checkpoint

The downstream response now has a separate fresh mesh-ladder operator.  Every
declared axial/transverse resolution re-solves the coupled field from the
same closure fingerprint, independently remeasures the retained boundary
response, and checks the solver-stored response against that independent
record.  Coordinate, tangent, pressure, and normal-velocity residuals remain
separate channels, and local mesh convergence cannot erase a failed global
overlap.

The compatible research ladder has ordered mesh growth and complete local
coverage at both tested resolutions, but both cases remain a typed overlap
residual failure.  This is refinement evidence for the next solver-owned
feedback iteration; it does not create a global feedback gate, canonical
downstream boundary, physical chain cell, or product claim.

## Solver-owned boundary-pressure consumer checkpoint

The coupled-Euler request now retains an explicitly sourced pressure profile
at the downstream cell-column centers.  One builder samples the exact global
boundary without extrapolation; a second builder converts the signed pressure
offsets from an independently measured global/coupled response into a bounded
relaxed correction for a subsequent coupled solve.  The solver consumes that
profile in both the material-streamline pressure flux and the free-boundary
shape residual, then records consumption and preserves the exact closure
fingerprint.

The new contract rejects cross-closure profiles, missing coverage, invalid
pressure targets, and coordinate mismatch.  The compatible tests show the
handoff is consumed, but the path remains a research seam: it does not
iterate a correction into the upstream global field, close canonical reflected
boundary conditions, fit a physical shock-cell length, or authorize Signature
or FPA production claims.

## Global/coupled pressure-feedback iteration checkpoint

The solver-owned pressure consumer now has a bounded validation runner that
executes fresh downstream coupled solves and independently reconstructs the
global/coupled response after each solve.  It records the input and next
profiles, response lineage, exact cell-center alignment, pressure-update
tolerance, local coupled-field status, and the explicit promotion ceiling.
Station drift is rejected instead of being interpolated or extrapolated.

On the compatible local fixture, the baseline response and second-solve
profile consumption are observable and lineaged, but the consumed second
field does not pass its local solver/audit gate.  The runner therefore retains
a typed solver failure and keeps global feedback, canonical closure, continued
shock-cell claims, Signature/FPA promotion, and external validation blocked.

## Reduced-order shock-train split-audit checkpoint

The reduced-order lane now audits its explicit case-role manifest against the
available case inventory.  Duplicate identities, unknown cases, silently
unassigned inventory members, and missing calibration or validation roles are
reported as typed states.  A verified disjoint manifest is retained as
governance evidence and still carries a ``not_accepted`` claim status.

The current one-case archive remains unassigned and therefore fails the
missing-split state.  This makes the next calibration packet executable when
an owner supplies additional cases, without treating pressure-extrema
spacing, scaled downstream geometry, or synthetic fixtures as physical
shock-cell validation.

## Explicit global/coupled boundary-geometry feedback checkpoint

The downstream feedback runner now carries a pressure profile and a separate
free-boundary geometry profile.  The geometry handoff is sampled from the
retained global boundary at the exact coupled boundary nodes and preserves
the closure fingerprint, station order, source identity, and research-only
claim ceiling.  The coupled solver consumes it only at aligned nodes; it
does not infer geometric displacement from pressure or silently regrid the
profile.

The independent Euler audit rederives the retained boundary ordinates and
marks exact geometry consumption separately from the pressure consumer.  The
initial response fixture correctly failed closed when the response-derived
profile did not match the coupled inlet seam.  The follow-on frame-anchor
slice below makes that seam explicit without translating coordinates.

## Solver-owned ambient-neighbor boundary-profile checkpoint

When exact physical-field continuation is selected without caller-supplied
downstream profiles, the coupled solver now samples the retained
shock-front-condition ambient neighbor directly.  Static pressure is sampled
at coupled cell centers, while the ordinate profile is sampled at coupled
boundary nodes; both require complete source coverage and neither path is
extrapolated.  The resolved profiles and source identifiers remain on the
coupled request, including the lower-ordinate frame, and the global
orchestrator retains that post-resolution request for lineage auditing.

The independent audit re-implements the interpolation and rejects a tampered
source-owned pressure or geometry path with
``PHYSICAL_FIELD_NEIGHBOR_PROFILE_FAILURE``.  Explicit caller-supplied
profiles remain a separate contract.  This closes the exact-field
source-to-boundary accounting seam only; the global feedback fixed point,
canonical mixed-regime closure, refinement, continued-chain promotion,
physical shock-cell fitting, and external validation remain open.

## Exact-field feedback-consumption checkpoint

The downstream feedback runner now distinguishes an exact physical-field
continuation run from the ordinary response-profile path.  When the caller
omits pressure and geometry feedback profiles, the first iteration is accepted
only when the coupled solver materializes both profiles from the retained
ambient-neighbor path, preserves the solver-owned source identifiers and
request object, and passes the independent neighbor-profile audit.  The next
iteration then consumes the explicitly generated profiles at their exact
cell-center and boundary-node stations.

On the compatible exact-field fixture, this closes the local research update
and reports ``CONVERGED_RESEARCH_PRESSURE_UPDATE`` with finite, independently
measured overlap residuals.  It does not set ``global_coupling_verified`` or
the downstream-boundary closure gate, and it cannot authorize continued-chain,
shock-cell, Signature, FPA, or external-validation claims.  The ordinary
response-feedback path remains separately typed and may still fail its local
pressure/tangency gate; it is not silently upgraded by this exact-field seam.

## Solver-owned geometry-frame anchor checkpoint

The geometry profile now retains the lower ordinate of the source coupled
request, and the downstream solver carries that ordinate through the typed
request and independent audit.  A verified global geometry profile determines
the coupled inlet height from its first retained boundary ordinate minus the
source lower ordinate; the solver rebuilds the mixed-regime request at that
height before consuming the aligned profile.  A lower-ordinate mismatch is a
typed input failure.  No implicit frame translation, regridding,
extrapolation, or pressure-only substitution is permitted.

The compatible fixture now passes the geometry consumer and its coordinate
response channel reaches tolerance with an independently audited local field.
The combined pressure/geometry feedback runner also verifies exact lineage,
station alignment, coverage, and consumption, while the second fresh field
in the ordinary response-profile configuration still fails the local
pressure/tangency residual gate.  The exact physical-field continuation
configuration now recognizes its solver-owned first-iteration profiles and
can reach the local research pressure-update result.  This remains a
solver-owned P2.2 seam: global feedback, canonical reflected closure,
continued-chain promotion, physical shock-cell fitting, Signature/FPA
promotion, and external validation stay closed.

## Solver-owned pressure-profile audit checkpoint

The independent coupled-Euler audit now reconstructs the exact pressure target
vector carried by the request.  A supplied solver-owned pressure profile is
used for the independent wall-flux reconstruction and for the
pressure/tangency gate; the scalar ambient pressure is used only when no
profile is present.  This closes a measurement-contract mismatch that had
mistakenly treated a consumed pressure profile as an ambient-boundary field.

With the corrected audit, a full research pressure update can produce a
locally audited field alongside the anchored geometry profile, and the
bounded runner can reach a local pressure fixed point when explicitly given
that update policy.  The exact physical-field continuation path also verifies
its solver-owned first-iteration neighbor profiles before entering the same
bounded runner.  These are local research outcomes only: canonical closure,
continued-chain promotion, physical shock-cell fitting, Signature/FPA
promotion, and external validation remain blocked.

## Downstream pressure-profile compatibility checkpoint

The coupled result now retains a separate typed diagnostic for the full
solver-owned downstream pressure profile.  It evaluates each target against
the outer control-section isentropic subsonic range and reports the target
extrema, below/within/above counts, worst-case compatible total pressure, and
the minimum additional loss fraction.  This catches the case where the
ambient target is compatible but the global feedback profile is not.

The independent audit recomputes the profile record and detects a tampered
record.  The diagnostic is intentionally non-gating: a below-budget profile
is retained as research input for the missing shock/mixing entropy treatment,
while global overlap, physical closure, external validation, and production
claims remain false.  The next implementation seam is the solver-owned
transonic/frontier treatment that can supply that missing physical budget.

## Target-pressure-aware transonic placement checkpoint

The solver-owned transonic placement request now optionally carries a declared
downstream static-pressure target and relative tolerance.  Candidate
cross-sections are evaluated in solver order using their derived normal-shock
profiles; a candidate is accepted only when its sampled profile meets the
target, while an unreachable target returns the typed
`TARGET_PRESSURE_UNREACHABLE` result with the best in-domain candidate and
residual retained for diagnosis.

The independent audit repeats the candidate ordering, field sampling, and
target residual calculation.  This is an executable local pressure-budget
gate, not a claim that the transonic/frontier closure is complete: the
surrounding C-/C+ field, ambient/centerline boundaries, global remesh
feedback, physical shock-cell length, Signature/FPA promotion, and external
validation remain separate work and remain closed.
