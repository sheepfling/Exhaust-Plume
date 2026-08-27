# Planar MOC first-cell contract v1

This document freezes the numerical boundary for the next solver fidelity
lane. It is intentionally separate from the compatibility-backed
`shock-cell-basic-v1` provider. The basic provider remains engineering-
approximate visual geometry until a later validated MOC provider is accepted.

## Scope of this tranche

The implementation in `exhaust_plume.models.moc` currently provides:

- radians-based Prandtl–Meyer evaluation and a bracketed inverse;
- the finite asymptotic-angle domain check;
- Mach angle and planar `K+ = theta - nu`, `K- = theta + nu` invariants;
- compatible interior characteristic points from one `C+` and one `C-` ray;
- centerline compatibility with an exact `theta = 0` boundary state;
- an open, triangular underexpanded expansion-fan mesh from the nozzle lip to
  averaged-characteristic compatibility axis intersections, with direct
  lip-ray intersections retained as a separate geometry diagnostic;
- an attached-compression pressure inversion with weak/strong branch status
  and a supersonic-downstream check;
- a turn-prescribed attached-compression state solve with weak/strong branch
  status, downstream supersonic-state reconstruction, and explicit detached
  turn rejection;
- a mild-overexpanded lip-shock branch with an explicit first centerline
  intersection and rejection of unsupported pressure ratios;
- a local ambient-pressure tangent segment with explicit finite extent,
  pressure residual, and tangent residual;
- a reflected `C+` march from centerline-compatible states to a sequence of
  ambient-pressure boundary points with per-point geometry and residual
  diagnostics;
- an assembled reflected characteristic lattice with axis-strip, interior,
  and free-boundary cells plus connected one-perimeter topology diagnostics;
- a boundary-side attached shock-to-centerline segment candidate with explicit
  turn, branch, positioned downstream characteristic state, and
  forward-endpoint diagnostics;
- a prescribed-boundary post-shock continuation primitive that marches
  downstream `C-` characteristics from sampled shock states to the symmetry
  line while checking forward geometry, invariant residuals, and total-
  pressure loss;
- a first downstream post-shock cross-characteristic layer from the continued
  centerline states and sampled shock states, with forward-margin and
  compatibility diagnostics while physical closure remains pending;
- a sampled, branch-checked attached-shock fit that returns downstream states
  and total-pressure loss at every shock sample;
- a solver-generated marched attached-shock boundary and full post-shock
  characteristic field, including a uniform linear-turn reference case and
  explicit upstream-state/pressure callbacks;
- a continued-cell adapter that passes a typed terminal-trace handoff into a
  new solver-generated shock field before returning a chain-cell solve result;
- a bounded state, static-pressure, and total-pressure sampler on a converged
  post-shock field. It interpolates only inside solver-carried characteristic
  cells and exposes the shock-boundary state/pressure samples needed for the
  next-cell upstream handoff;
- a field-coupled continued-cell adapter and planner that consume those
  bounded samples, preserve the exact prior perimeter, and return either a
  complete next field or a typed normal-shock/field-boundary stop. The planner
  remains a research lane with explicit caller-supplied downstream turning;
- a domain-bounded reflected-zone state/pressure sampler that refuses to
  extrapolate once a candidate shock leaves the solved upstream lattice;
- a typed reflected-zone shock-path coupling probe that records partial
  upstream samples and the first missing characteristic-strip point;
- a reflected-zone continued-cell ``or_termination`` adapter that returns a
  typed non-physical ``upstream-field-boundary`` stop with those coupling
  diagnostics instead of extrapolating or turning a finite-domain miss into a
  physical endpoint;
- a one-sided caustic new-family restart that reflects each selected C- edge
  to the centerline and marches an ambient-pressure/tangent C+ boundary with
  explicit pressure, tangent, geometry, and forward-progress residuals. It
  records the old triangular interior assembly separately when the first
  cross-ray is not forward, then assembles a connected two-triangle-per-step
  open family band from the valid centerline/boundary traces. The band remains
  an open remesh/shock seam and cannot promote a chain cell; its state and
  pressure samplers are domain-bounded and refuse to extrapolate beyond the
  new band. A production shock-band seam consumes the explicit input edge in
  both canonical orientations, refits the supersonic shock samples, assembles
  a 27-cell open post-shock characteristic zone, and records the typed
  subsonic centerline terminal. The zone remains an open mixed-regime handoff
  until a subsonic field and complete physical perimeter are solved;
- the caustic restart retains the selected one-sided seed point/state as the
  family-band anchor and verifies that the new band's input edge is strictly
  downstream of it. A successful handoff exposes a typed non-physical
  ``characteristic-caustic`` chain decision; a failed band assembly propagates
  as a restart failure. Neither result bridges the old family, fits a shock,
  or promotes an open band into a chain cell;
- the caustic-band terminal seam's refinement probe reaches the same typed
  terminal at 5, 7, 9, and 11 shock samples in both canonical orientations,
  with open-zone cell counts 5, 14, 27, and 44 and decreasing tangent-fit
  residuals. The independent shock-cell measurement operator intentionally
  rejects this open zone until the shock and centerline boundaries share a
  physical endpoint;
- a reusable triangular source-boundary characteristic-strip assembler and
  domain-bounded state/pressure sampler that reproduces the reflected-zone
  compatibility grid;
- an explicitly open constant-`K+` simple-wave continuation of that source
  strip, with deterministic boundary-progress and extended-strip topology
  diagnostics;
- an explicitly labeled reflected-boundary trace-extension reference that
  generates a closed shock field without claiming a solved upstream strip;
- a shock-seeded shrinking-front C+/C- characteristic-field assembler with
  explicit shock/centerline edges, total-pressure lineage, forward margins,
  invariant diagnostics, and a typed downstream handoff boundary;
- a closed post-shock field acceptance gate that requires solver-supplied
  converged nodes, explicit shock and centerline boundary edges, connected
  topology, and strict pressure loss before producing a chain seed;
- an explicit ambient-pressure outer-perimeter gate that removes the shock
  and centerline edges from a candidate mesh, reconstructs the remaining
  solver-carried state trace, and checks both static-pressure matching and
  flow/boundary tangency;
- a bounded scalar ambient-pressure closure shoot that regenerates the
  attached shock/field for each outer-turn trial and uses the perimeter gate
  as the final acceptance condition;
- an explicit upstream-coupling gate on ambient closure results. The research
  adapter may retain a boundary-conditioned ambient-closed field, while the
  strict ``as_coupled_chain_cell`` adapter requires both the ambient perimeter
  gate and carried upstream shock states before a resolved chain handoff is
  possible;
- a reflected-zone ambient-closure adapter with independent upstream coverage
  reporting and a chain-promotion method that refuses incomplete coupling;
- a separate boundary-conditioned triangular assembler that accepts a
  branch-checked shock trace plus an independently accepted ambient trace and
  only exposes a resolved chain handoff after the characteristic net closes on
  the centerline. It is an acceptance primitive for the future free-boundary
  shooter, not that shooter itself;
- a correctly oriented shock/ambient strip assembler in which shock-sourced
  ``C+`` characteristics and ambient-sourced ``C-`` characteristics form a
  connected physical-boundary net, plus a shock-to-ambient boundary marcher
  that enforces the incoming ``K+`` law, ambient pressure, and streamline
  tangency. The result carries an explicit downstream terminal trace and is
  not chain-promotable until a centerline closure is solved;
- a bracketed ambient-attachment closure that solves the outer shock turn from
  the local post-shock static-pressure/ambient residual before regenerating
  that physical shock/ambient strip. It removes the fixed attachment angle from
  the caller, but retains a named linear-to-centerline reference law and an
  open terminal trace, so it is not a closed first-cell or chain-promotion
  result;
- a staged shock-cell transition adapter that composes ambient attachment,
  centerline reflection, and the domain-bounded next-shock probe. It carries
  the reflected outgoing ``C-`` trace as a typed next-shock handoff and can
  return a physical chain-stop decision for a verified normal-shock terminal,
  while keeping cell promotion blocked until a mixed-regime field is solved;
- a typed terminal-compression candidate that validates that downstream
  shock-sourced ``C+`` trace, checks its ambient endpoint pressure, and solves
  a forward attached compression segment to the centerline. It remains a
  local boundary primitive only: the characteristic patch on its downstream
  side is unsolved, so physical closure and chain promotion are hard-false;
- a terminal-trace centerline-reflection patch that consumes the shock-sourced
  ``C+`` trace with downstream ``C-`` characteristics, assembles a connected
  compatible net, and emits a typed outgoing ``C-`` front. The incoming seam
  is checked against the shock/ambient strip, while the outgoing front stays
  open until a physical compression/shock boundary is fitted;
- a domain-bounded terminal-patch shock probe that interpolates the reflected
  state and pressure field, carries the outgoing ``C-`` handoff into the
  attached-shock marcher, and returns a typed subsonic/normal-shock terminal
  when the supersonic lane reaches its mixed-regime boundary. It verifies
  upstream coverage but remains ineligible for physical closure or promotion;
- a terminal-patch continued-cell adapter that requires a resolved prior cell
  and exact outgoing ``C-`` handoff, feeds the finite patch state/pressure
  domain into the next shock solve, and returns either a coupled field solve or
  a typed bounded/normal-shock stop without fabricating an open or subsonic
  cell. Its downstream turn law remains explicitly research-only;
- a first-cell composite assembler that joins the shock/ambient strip and
  centerline-reflection patch at their shared terminal ``C+`` seam, checks
  explicit shock/ambient/centerline/outgoing-``C-`` perimeter paths, and
  exposes an independently measurable closed supersonic topology while
  keeping physical closure and chain promotion blocked;
- a typed ``OPEN_PHYSICAL_CLOSURE`` chain decision from that composite, so a
  planner can stop at the unresolved downstream boundary without treating it
  as a physical endpoint or an unstructured solver error;
- a physical mixed-regime termination adapter for the terminal-patch probe.
  After complete upstream coverage and a converged normal-shock terminal, it
  returns an explicit physical chain-stop decision while keeping the
  unresolved subsonic field out of the supersonic cell-promotion path;
- a terminal-shock composite-field assembler that clips the validated
  shock/ambient strip and reflected characteristic patch to the upstream side
  of the solver-generated normal shock. It exposes a connected, one-perimeter
  supersonic-region topology gate and inherited characteristic-cell evidence,
  retaining the validated source characteristic nodes that remain vertices of
  the clipped mesh for refinement and visualization diagnostics,
  requires explicit coverage of the complete terminal-shock boundary and its
  endpoint upstream state/pressure sample,
  while reporting ``mixed_regime_field_complete`` and
  ``physical_closure_verified`` as hard-false until the downstream subsonic
  field is solved;
- a first-cell terminal-closure bridge that consumes the composite's exact
  outgoing ``C-`` handoff, fits the solver-generated terminal shock, and
  returns a typed closed-supersonic-region result. It does not infer a
  downstream perimeter: the mixed-regime field remains a separate gate and
  chain promotion remains blocked;
- a solver-owned mixed-regime perimeter request that carries the terminal
  scalar state and exact supersonic post-shock seam while supplying no guessed
  downstream geometry. The open supersonic zone is explicitly rejected as a
  substitute for that perimeter;
- a callback-owned mixed-regime closure gate that requires the returned field
  to retain the exact terminal object, patch sample count, closed perimeter,
  topology, and residual acceptance before attachment. A missing or mismatched
  callback result remains a typed failure;
- a separate MOC cell-chain continuation contract that rejects open cells,
  non-bounded meshes, axial gaps, and scaled reduced-order fidelity;
- a typed chain termination decision that distinguishes a physical endpoint
  from a planner/numerical callback stop;
- a caustic-aware source-frontier probe that reports disjoint forward
  characteristic intervals and the first invalid ray without stitching them
  into a false connected upstream strip; its local remesh attempt retains
  only valid candidate cells and reports the first self-intersecting patch
  together with its bounded crossing point as a non-promotable shock/new-family
  handoff;
- continued-cell reports that expose the outgoing total-pressure range for
  every carried terminal trace and flag nonincreasing pressure maxima as
  bookkeeping evidence;
- a reusable chain-planner wrapper that records the exact incoming boundary
  before each continuation callback, including a deterministic fingerprint of
  every carried state and total-pressure sample. Its prescribed-boundary
  planner mode is an executable mock with a hard
  ``production_claim_allowed=false`` ceiling;
- a terminal-reflection-patch planner wrapper that audits one exact outgoing
  ``C-`` handoff and its typed normal-shock stop through the generic chain
  planner. It stops after that finite patch domain; later cells require a new
  upstream field and solver adapter;
- a solver-generated field-coupled planner checkpoint that samples the prior
  closed post-shock lattice for the next shock, reaches a typed normal-shock
  terminal without extrapolation, and records the planner as
  ``upstream-coupled-research`` with ``production_claim_allowed=false``;
- a caustic-family-band planner checkpoint that carries the exact prior
  post-shock perimeter into a solver-generated open next-shock field in both
  restart orientations, then returns a typed ``OPEN_PHYSICAL_CLOSURE`` stop
  without appending that open result as a chain cell;
- an executable caustic shock-remesh planner seam that consumes the exact
  event state, incoming perimeter, and bounded upstream callbacks, verifies a
  solver-generated local shock/new-family field when the invariant law closes,
  and still returns a one-step non-physical stop while physical first-cell
  closure remains pending;
- a separate mixed-regime reference-field attachment gate for the terminal
  first-cell closure. A validated explicit scalar perimeter can be solved by
  the ``elliptic-isentropic-subsonic-reference`` model and attached only when
  the exact terminal and supersonic patch are retained; this can produce a
  typed physical termination fixture, but the canonical plume perimeter is
  still not inferred from the open supersonic zone;
- a typed downstream-perimeter adapter for that reference lane. It accepts an
  explicitly closed perimeter specification plus a caller-owned scalar sample
  provider, validates the exact terminal/supersonic seam and named downstream
  condition, and then runs the elliptic reference-field gate. It never fills
  missing samples or geometry from the open supersonic zone. Its accepted
  result is a reproducible finite-domain reference/termination fixture, not a
  canonical free-boundary perimeter or a new supersonic chain cell;
- mesh connectivity diagnostics that distinguish a topologically bounded
  polygon from an unresolved physical boundary;
- a shared averaged-characteristic fan/reflected interface whose combined
  cells pass connected one-perimeter topology checks;
- structured scalar, invariant, and forward-ray geometry residuals.

The fan mesh is intentionally open: it does not close the compression side,
solve a free-boundary/shock endpoint, or claim a physical Mach-disk location.
The turn-prescribed compression primitive is state-side evidence only: it
does not select a shock location, assemble a reflected characteristic, or
close the first-cell topology.
The reflected-boundary march and characteristic-zone assembler now assemble
the centerline, interior, and pressure-matched boundary network. The result is
still physically open until a compression/shock endpoint and post-shock
characteristic continuation are solved. The current shock-to-centerline
operation reconstructs a positioned downstream supersonic state and its
total-pressure loss, but it remains only a boundary-side candidate; it does
not prove that downstream characteristics or total-pressure bookkeeping close
across the full plume cell. The prescribed-boundary continuation primitive now
proves individual downstream `C-` traces when a sampled post-shock boundary is
supplied. The sampled shock-fit primitive verifies an explicitly supplied
attached-shock curve and carries sample-wise total-pressure loss, but it is
still a boundary contract rather than a free-boundary finder. The
solver-generated marcher now constructs an attached-shock curve from local
theta-beta-Mach compression solutions and assembles the same closed-field
gate around it. Its uniform linear-turn case is a deterministic
higher-fidelity reference fixture; the production gate still requires
coupling the marcher to the reflected MOC upstream state/pressure field and
solving the downstream boundary condition rather than prescribing that turn
law. The first downstream cross-characteristic layer is an explicit partial
sub-gate, not a physical closure claim. The closed-field gate refuses to synthesize missing
cells: it promotes only a solver-supplied field whose shock and centerline
edges are explicit and whose characteristic nodes carry converged
compatibility evidence. Only that verified result can be adapted into a
resolved planar-MOC chain seed. The shock-seeded assembler supplies a
boundary-conditioned full characteristic fan and exposes its terminal path as
typed state/total-pressure handoff samples. That path is explicitly a
`post-shock-field-perimeter`: it is an ordered composite edge made of multiple
characteristic segments, not one invariant-preserving characteristic and not
an axial cut plane. A continued solver must propagate the perimeter to its own
next shock boundary and record the exact incoming boundary through
`incoming_handoff`; the separate chain adapter checks that the boundary was
consumed unchanged and that total pressure did not reset upward before
appending the cell. It does not invent a next shock location or promote the
reduced-order shock train. The reusable
`MocPrescribedPostShockChainMock` and its planner convenience entry point
exercise this contract in the primitive validation report; the solver-generated
chain reference now runs through the same planner wrapper and records each
generated handoff step with strict upstream-coupling mode enabled. Both remain
callback-conditioned evidence rather than physical free-boundary chain
evidence.
The terminal-reflection-patch planner uses the same audit path for the
solver-backed one-step handoff. It records the patch boundary kind and exact
sample count before the adapter runs, and a second step cannot reuse the
terminal patch outside its solved domain. Its typed normal-shock result is a
physical chain stop, not a promoted subsonic cell.
The completed post-shock field now also exposes bounded state, static-pressure,
and total-pressure sampling at its cell vertices and shock boundary. The
field-coupled continued-cell adapter feeds those samples into the marched
next-shock solver, verifies the exact prior perimeter handoff, and returns a
typed field-boundary or normal-shock stop without extrapolation. The reusable
``plan_post_shock_field_chain`` wrapper updates its upstream field only after
a complete next field is returned. Its canonical reference reaches a typed
normal-shock stop after one seed cell, while its downstream turn condition and
production validation remain explicitly pending.
The caustic-family-band continuation is isolated as a separate one-step
planner path: it carries the exact prior perimeter into the bounded restarted
family, solves the next shock and open supersonic zone, and records the typed
normal-shock terminal. Both canonical orientations end with
``OPEN_PHYSICAL_CLOSURE``; the unresolved mixed-regime perimeter prevents
chain-cell promotion and any later-cell reuse of that band.
The constant-`K+` source-strip continuation is another upstream-only diagnostic
fixture: in the canonical case it preserves an open 231-node/230-cell strip
and advances the domain-bounded shock probe before stopping at the next
missing field sample. A longer continuation can expose a terminal source
window after the full triangular lattice reaches a characteristic caustic; the
window carries its source offset and the full-strip failure as explicit
metadata. A separate bracketed constant-invariant shock shoot now consumes
that domain-bounded window and either returns a closed field or a structured
no-bracket/domain failure. It is not a physical shock closure or a production
next-cell solver until the invariant law and its validation domain are
accepted.
The mesh topology intentionally remains reported as `OPEN`: its boundary edges
are the physical shock/centerline perimeter. `physical_closure_status` and the
field status carry the separate evidence that this prescribed-boundary fan is
closed for numerical promotion, but that is not an ambient free-boundary
acceptance. `validate_post_shock_ambient_boundary` is the additional external
condition gate; the current prescribed fixture fails it because its remaining
perimeter is an internal characteristic with pressure and tangency residuals.
The ambient-pressure shooter now uses that same extracted perimeter as a
scalar pressure coordinate, but it retains the full vector pressure/tangency
gate. The synthetic pressure-root probe therefore returns a bounded
`ambient_boundary_failure`, and the canonical reflected-zone probe returns a
bounded upstream-domain failure rather than manufacturing a first cell.
Ambient closure reports expose `upstream_coupling_verified` separately;
passing the perimeter shoot alone is not enough for strict chain promotion.
The reflected-zone adapter uses the strict coupled promotion method, so a
boundary-conditioned or domain-incomplete result remains a research artifact
even if its local downstream field is numerically closed.
When a marched shock reaches a zero-turn symmetry endpoint, the solver also
records a `MocNormalShockTerminalResult` with the normal-shock static and
total-pressure jump. Its downstream Mach remains scalar rather than entering
the supersonic `CharacteristicState` type; this is terminal evidence only,
not mixed-regime closure or chain-cell promotion.
The prescribed field still promotes only the
`POST_SHOCK_FIELD_PERIMETER` kind for its composite downstream edge. A
separately solved single characteristic remains
`TERMINAL_CHARACTERISTIC_TRACE`. The separate ambient-closed triangular
assembler promotes its centerline handoff as
`MocChainBoundaryKind.CENTERLINE_TRACE`; a later true axial cut must declare
`MocChainBoundaryKind.AXIAL_SECTION`.
The shock/ambient strip intentionally has no promotion adapter: its
`terminal-characteristic-trace` is a real unresolved downstream boundary, not
an inferred centerline or axial section.
The bracketed ambient-attachment result has the same boundary: its
`outer_downstream_flow_angle_rad` is solved from a local ambient-pressure
attachment bracket, while `downstream_condition_status` remains
`linear-centerline-reference`. This records a physical open boundary net, not
the missing centerline reflection, next-shock fit, or mixed-regime perimeter
closure required for a first cell.
The staged transition consumes that open trace and exposes the reflected
outgoing ``C-`` front to the next-shock probe. A verified normal-shock terminal
can therefore stop the supersonic chain explicitly, but it does not set
``physical_closure_verified``: the subsonic downstream field and mixed-regime
perimeter are not represented by the current planar supersonic-MOC cell.
The strip exposes that trace as typed `MocChainBoundarySample` values and
reports independent `C+` characteristic-trace evidence (family invariant,
forward margin, and discrete geometry residual). A finite trace report is not
the same as closure: the current coarse strip retains its nonzero
characteristic-line discretization residual and remains ineligible for chain
promotion until a converged downstream boundary-value solve accepts it.
The terminal-compression candidate can use a separately declared mesh-scale
trace tolerance for this coarse polyline, but that tolerance is reported with
the candidate and does not change the strict strip diagnostic. Even when the
local attached segment reaches the centerline and carries a valid shock
total-pressure loss, the candidate is not a cell and cannot enter the
continued chain until a downstream C+/C- characteristic patch is assembled.
The terminal-trace centerline-reflection patch is that compatible patch seam:
it preserves the incoming trace, checks the combined mesh topology, and
returns an outgoing C- trace. It remains an open transition rather than a
closed physical cell until that outgoing front is replaced or coupled to a
solver-generated compression/shock boundary.
The terminal-patch shock probe consumes the outgoing front through a
domain-bounded interpolated state/pressure field. In the canonical reference
it covers the requested shock samples and returns the typed subsonic normal-
shock terminal; this is a mixed-regime boundary decision, not a closed
supersonic first-cell result. Its downstream field and physical perimeter
remain pending. The 9/17/33-sample terminal-patch refinement probe reaches
the same typed terminal at every resolution and shows a converging centerline
endpoint; that validates the open transition's numerical behavior only.
The continued-cell adapter consumes the same outgoing front only after a
resolved prior cell and exact `terminal-characteristic-trace` handoff are
present. It verifies that the patch's finite upstream state/pressure domain
is the field actually used by the next shock march and returns a
`MocPostShockChainCellSolve` only for a complete nonterminal field. The
canonical zero-turn case returns the existing typed normal-shock termination
instead, so no open patch or subsonic state is promoted.
The first-cell composite assembler then joins the strip and patch over the
same terminal trace. Its union has one connected, topologically bounded
supersonic mesh with explicit shock, ambient, centerline, and outgoing-trace
edges, and the independent geometry operator measures the union without
inferring any edge. This is a materially closed local topology, but its
production physical-closure flag remains false until the reflected upstream
field and downstream boundary condition are accepted.
When complete upstream coverage is present, the same result can provide a
physical chain-stop decision for that mixed-regime terminal. This decision
does not set ``physical_closure_verified`` and cannot promote a cell; it only
prevents the chain from misreporting a verified normal shock as a numerical
truncation.
The composite itself exposes the analogous open-closure decision before a
terminal shock is fitted. Its decision preserves the continuation trace and
reports the missing reflected-field/downstream-closure gates without inventing
an endpoint.
The continued-cell free-boundary adapter now exposes the same distinction to
the generic chain: a resolved next field is appended, while a verified
normal-shock terminal returns a physical stop without appending a subsonic
MOC cell.
The terminal-shock composite-field assembler now closes the supersonic side
of that same terminal by clipping the reflected characteristic cells against
the solver-generated shock path and rechecking the combined mesh. Its
``supersonic_region_closed`` and ``characteristic_field_evidence_verified``
flags describe topology and inherited source-cell evidence only; they do not
claim a solved downstream state. ``mixed_regime_field_complete`` remains
false, so the composite region is still a terminal research artifact rather
than a chain-promotable first cell.
The validation report separately refines this composite at 9/17/33 samples;
each case carries the complete terminal-shock edge and matching upstream
state/pressure samples to approximately ``1e-9 m`` geometry residual. The
coarse case retains its declared mesh-scale trace tolerance. This is
supersonic-side topology evidence only and does not relax the mixed-regime
closure gate.
The composite also carries independently fitted downstream supersonic states
along the oblique portion of the terminal shock. The subsonic normal-shock
endpoint remains a scalar terminal result rather than being forced into
``CharacteristicState``; this is a handoff for a future mixed-regime solve,
not a completed downstream field. Those oblique states now feed an explicitly
open downstream patch: compatible ``C-`` traces reach the centerline, the
first ``C+``/``C-`` cross-layer is checked, and the resulting open zone is
retained as diagnostic mesh evidence. The canonical 17-sample case produces
16 centerline traces and a 119-cell open zone. Its final shock-side sample
still terminates at the normal-shock interface above the axis, so the patch
does not claim a subsonic state, mixed-regime closure, or chain promotion.
The terminal probe also records branch-specific mixed-regime seams. A strong
attached branch can reach ``M2 < 1`` before the weak branch reaches its scalar
normal-shock endpoint; that result carries scalar Rankine--Hugoniot data and
its shock point but no downstream ``CharacteristicState``. The branch is
reported separately from the outer attachment branch, and neither the typed
strong boundary nor the open supersonic patch relaxes the mixed-regime field
or chain-promotion gate.
The separate ``mixed_regime`` contract now accepts only scalar subsonic
samples on an explicitly closed downstream perimeter. It checks the open
supersonic patch first, then checks terminal Mach/angle/pressure continuity,
downstream geometry, and total-pressure lineage. A passing result is named a
``converged_subsonic_boundary_handoff`` rather than a field: it has no
subsonic characteristic states or mesh, so ``mixed_regime_field_complete``
and ``physical_closure_verified`` remain false and chain promotion remains
blocked. The validation artifact includes a missing-field rejection and a
non-physical scalar-perimeter contract fixture to keep this boundary
executable without pretending that the fixture is a solved plume region.
The separate ``solve_mixed_regime_subsonic_field`` lane now consumes that
closed scalar contract only as a declared boundary. Its first reference model,
``elliptic-isentropic-subsonic-reference``, builds a connected four-cell fan
around an interior point and gates completion on isentropic total-pressure,
harmonic-extension, and per-cell velocity-divergence residuals. It exposes a
typed terminal attachment/termination report, but deliberately remains outside
the supersonic ``CharacteristicState`` and chain-cell promotion contracts. The
validation artifact's passing square perimeter and terminal attachment are
contract fixtures; the canonical terminal remains unclosed until a physical
downstream perimeter is generated by the plume solver.
The terminal composite and caustic-band terminal seam now expose this same
handoff directly: callers can submit scalar perimeter samples to the mixed-
regime validator, and an empty/open perimeter returns a typed
``subsonic_field_failure``. A terminal composite without an attached mixed-
regime field also returns a non-physical ``OPEN_PHYSICAL_CLOSURE`` chain stop,
so the planner can preserve the boundary without promoting the open zone.
The boundary-conditioned triangular assembler now uses the same physical
orientation—shock-sourced ``C+`` and ambient-sourced ``C-``—and records
per-node compatibility evidence before its centerline closure gate. It accepts
an explicit downstream axis corner when the ambient trace has one more sample
than the shock trace, but it still refuses chain promotion unless the complete
centerline perimeter and orientation evidence pass. The canonical marched
ambient trace currently reaches the explicit centerline-closure failure at
this seam; the terminal composite/terminal-shock path remains the accepted
route for the separately solved mixed-regime gate.
The executable caustic remesh seam consumes the prepared event through a
bounded attached-shock/new-family solve and preserves the exact incoming
perimeter in its planner report. Its result is deliberately hard-false for
physical closure and chain promotion until a physical first-cell boundary is
attached, even when all local remesh and downstream-field checks converge.
No public provider is wired to these primitives yet. The module does not claim
axisymmetric, reacting, viscous, or experimentally validated plume physics.

## External source review

The NASA-CR-169257 underexpanded-jet study is useful as a topology warning,
not as a bound validation fixture for this repository. It covers Mach 1.4 and
2.1 convergent-nozzle jets and describes the higher-pressure case as having
intercepting compression waves connected by a normal shock or Riemann-wave
region. That behavior is consistent with keeping shock coalescence and
post-shock continuation as explicit implementation gates rather than closing
the current open lattice with a single geometric segment. The report is source
context only here; no digitized NASA flowfield or independent MOC solution is
accepted as a provider-bound reference in this branch.

Source: [NASA NTRS record 19820022412](https://ntrs.nasa.gov/citations/19820022412)
and its public report [NASA-CR-169257 PDF](https://ntrs.nasa.gov/api/citations/19820022412/downloads/19820022412.pdf).

## State and units

The independent plane is `(x, y)` in metres, with `+x` downstream and
`theta` measured counter-clockwise from `+x`. Mach, `gamma`, `nu`, and `mu`
are dimensionless or radians as named. Every state is supersonic (`M > 1`);
the sonic limit is represented only by scalar inversion at `M = 1`.

For a state `(theta, nu)`, the invariants are

```text
K+ = theta - nu
K- = theta + nu
```

An interior point formed from an incoming `C+` state `A` and `C-` state `B`
uses

```text
theta_P = (K+_A + K-_B) / 2
nu_P    = (K-_B - K+_A) / 2
```

The state is solved before geometry. Characteristic directions use the
average of the source and target angles, and intersections are required to be
forward on both parameterized rays. A finite least-squares or backward point
is never reported as a converged MOC point.

## Failure and acceptance semantics

`ScalarRootResult` and `CharacteristicPointResult` preserve status, residual,
iteration count, and bracket/intersection diagnostics. The following are
distinct:

- `outside_domain`: the requested Prandtl–Meyer state is not finite or would
  require an asymptotic Mach number;
- `geometry_failure`: characteristic rays are parallel, ill-conditioned, or
  intersect behind a source;
- `invariant_failure`: the geometry exists but compatibility residuals exceed
  tolerance;
- `max_iterations`: a declared numerical limit was reached.

The current tests establish dense forward/inverse round trips, near-sonic and
high-Mach conditioning, pressure-ratio inversion, invariant closure, and
forward centerline/interior geometry. They are primitive evidence only; they
do not authorize replacing the basic provider or accepting a product claim.

## Next gates before provider integration

1. Extend the reflected MOC upstream state/pressure field far enough to cover
   the generated shock path, then replace both the uniform reference
   linear-turn law and the diagnostic constant-`K+` continuation assumption
   with a solved post-shock boundary condition. The new bracketed ambient
   attachment shooter is the bounded research seam for the outer shock turn,
   but its current open-strip result still uses a named linear-centerline
   reference and is not a production free-boundary first-cell solution: the
   remaining terminal closure and canonical reflected upstream coverage are
   still open.
2. Demonstrate grid/refinement convergence for the assembled reflected and
   post-shock zones, underexpanded, and mild attached overexpanded reference
   cases.
3. Compare an independent cold-jet case through an explicit measurement
   operator and uncertainty model.
4. Only then route an explicitly versioned MOC provider through the visual
   product contract; downstream shock-train and optical/FPA products remain
   separate lanes.
