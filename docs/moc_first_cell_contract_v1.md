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
- a domain-bounded reflected-zone state/pressure sampler that refuses to
  extrapolate once a candidate shock leaves the solved upstream lattice;
- a typed reflected-zone shock-path coupling probe that records partial
  upstream samples and the first missing characteristic-strip point;
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
- a reflected-zone ambient-closure adapter with independent upstream coverage
  reporting and a chain-promotion method that refuses incomplete coupling;
- a separate boundary-conditioned triangular assembler that accepts a
  branch-checked shock trace plus an independently accepted ambient trace and
  only exposes a resolved chain handoff after the characteristic net closes on
  the centerline. It is an acceptance primitive for the future free-boundary
  shooter, not that shooter itself;
- a separate MOC cell-chain continuation contract that rejects open cells,
  non-bounded meshes, axial gaps, and scaled reduced-order fidelity;
- a typed chain termination decision that distinguishes a physical endpoint
  from a planner/numerical callback stop;
- continued-cell reports that expose the outgoing total-pressure range for
  every carried terminal trace and flag nonincreasing pressure maxima as
  bookkeeping evidence;
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
`terminal-characteristic-trace`, not an axial cut plane. A continued solver
must propagate the trace to its own next shock boundary and record the exact
incoming trace through `incoming_handoff`; the separate chain adapter checks
that the trace was consumed unchanged and that total pressure did not reset
upward before appending the cell. It does not invent a next shock location or
promote the reduced-order shock train. An executable prescribed-boundary
planner mock exercises this contract in the primitive validation report; the
solver-generated chain reference now exercises the same handoff with generated
shock boundaries. Both remain callback-conditioned evidence rather than
physical free-boundary chain evidence.
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
The prescribed field still promotes only the
`TERMINAL_CHARACTERISTIC_TRACE` kind. The separate ambient-closed triangular
assembler promotes its centerline handoff as
`MocChainBoundaryKind.CENTERLINE_TRACE`; a later true axial cut must declare
`MocChainBoundaryKind.AXIAL_SECTION`.
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
   with a solved post-shock boundary condition. The new ambient shooter is the
   bounded research seam for that condition, but the current probes are not a
   production free-boundary first-cell solution: one fails the full perimeter
   gate and the canonical reflected case fails upstream coverage.
2. Demonstrate grid/refinement convergence for the assembled reflected and
   post-shock zones, underexpanded, and mild attached overexpanded reference
   cases.
3. Compare an independent cold-jet case through an explicit measurement
   operator and uncertainty model.
4. Only then route an explicitly versioned MOC provider through the visual
   product contract; downstream shock-train and optical/FPA products remain
   separate lanes.
