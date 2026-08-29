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
