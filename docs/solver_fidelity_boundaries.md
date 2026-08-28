# Solver fidelity boundaries

Status: active architecture decision for the post-`0.1.0a1` completion line.

The three products remain independent contracts. Fidelity is a property of a
provider and its model lineage, not a new product API and not one scalar score.
The same visual, signature, or ray-transfer contract may eventually be served
by more than one provider, but each provider must declare its own physics,
applicability, validation evidence, and complexity ceiling.

## Boundary matrix

| Lane | Status | Current role | Allowed primary product | Explicit non-claims |
| --- | --- | --- | --- | --- |
| `planar-moc-primitives-v1` | boundary-conditioned field/chain foundation; provider pending | Standalone planar characteristic states, scalar inversions, compatibility residuals, pressure- and turn-prescribed attached compression, sampled attached-shock fit, solver-generated marched attached-shock reference field, reflected centerline-to-free-boundary march, reusable triangular source-boundary strip, assembled open characteristic zone, domain-bounded shock-path coupling probe and reflected-zone shock/chain entry point, shock-seeded closed post-shock C+/C- field, shock-sourced C+/ambient-sourced C- physical-boundary strip, ambient-perimeter validator and bounded scalar closure shoot, ambient-axis closure residual and attachment-coordinate global shoot, total-pressure handoff, state-carrying chain adapter, separate elliptic-isentropic subsonic reference field, and independent shock-cell geometry/topology measurement operators | None yet; future MOC first-cell provider only after complete reflected-field coupling, canonical ambient-perimeter physical closure, refinement, and external validation gates | No public visual, signature, optical, detector, or FPA claim; no axisymmetric or reacting-flow claim; the elliptic reference is not a supersonic MOC chain cell |
| `shock-cell-basic-v1` | active | Fast, steady, straight, low-order shock-cell construction | `plume.visual.sectioned-tube@1`; supporting spatial/engineering handoffs where explicitly advertised | No physical signature, ray transfer, detector image, mixing, chemistry, radiation, or curved/washed flow |
| `shock-cell-reduced-order-v1` | experimental | One resolved first cell plus explicitly calibrated, scaled downstream shock-train continuation | `plume.visual.sectioned-tube@1` through `plume.shock-train-reduced-order` | No resolved downstream MOC claim, spectral signature, ray transfer, detector image, FPA, or unvalidated universal closure |
| `signature-table-mvp-v1` | active | Independent unresolved spectral lookup | `plume.signature.spectral-radiant-intensity@1` | No solved flow, geometry reconstruction, atmosphere, optics, detector, or focal-plane array |
| `washed-integral-v1` | planned | Curved, rotor-washed, or crossflow integral continuation | Visual and engineering products only after a provider and validation gate exist | No automatic spectral or ray-transfer claim |
| `optical-transfer-v1` | active | Straight constant-radius support with exact homogeneous gray transfer | `plume.optical.spectral-ray-transfer@1` | No chemistry, atmosphere, curved transport, detector integration, or focal-plane electronics |
| `focal-plane-array-v1` | validated downstream adapter; no provider | Camera/optics identity, spectral response, exposure, pixel integration, expected noise variance, and deterministic digitization | A future image/detector product | Not a plume solver; requires validated ray transfer and external detector evidence |

The machine-readable copy is
[`solver_fidelity_matrix_v1.json`](solver_fidelity_matrix_v1.json). The matrix
is a governance artifact; it does not create a second product contract.

The ambient-axis shooting seam has an additional promotion gate: a scalar
attachment-coordinate pressure root is not a physical field. The retained
ambient-to-axis point/state/total-pressure samples must first pass the full
pressure and streamline-tangency validator, and only then may the coupled
shock/ambient/centerline assembler attempt a state-carrying field. The bridge
remains research-only and cannot change the basic visual, signature, ray, or
focal-plane-array providers.

The terminal mixed-regime lane also has a separate solver-owned
``solver-owned-quasi-1d-ambient-free-boundary-reference``. It shoots a finite
outlet height from the terminal subsonic total state and an explicit ambient
pressure, then generates a scalar radial field with a typed physical-condition
result. Its effective inlet height and downstream envelope are explicit model
assumptions, so even a passing result is planner/visualization research
evidence only: ``production_claim_allowed=false`` and
``chain_promotion_blocked=true`` remain mandatory. The canonical reflected-MOC
free boundary still requires a coupled downstream geometry/flux solve and
external validation. An independent
``op.moc.mixed-regime-free-boundary-reference`` measurement rechecks that
reference and reports its large embedded 2-D divergence diagnostic without
using it as a full-flow acceptance gate.
The separate
``op.moc.mixed-regime-free-boundary-refinement`` operator remeasures solver
outputs at declared 5/7/9 free-boundary resolutions, requires one exact seam
and fixed reference parameters, and records outlet-height sensitivity. The
canonical generated case is locally stable (perimeter counts 8/10/12), but
the rising 2-D divergence diagnostic is retained as evidence of the
quasi-1-D model limitation; this sequence cannot promote a reflected-MOC
cell or close the canonical downstream boundary.

The reference lane also accepts an explicit
``MocMixedRegimeControlSection`` handoff. This is a transverse, scalar,
flux-bearing input—not a ``CharacteristicState`` boundary. The section-aware
planner uses its measured section length as the quasi-1-D effective inlet only
when every sample is terminal-equivalent; a varying section returns a typed
control-section failure and must wait for the canonical downstream 2-D solver.
The existing prescribed mixed-regime planner mock remains a synthetic fixture,
and both the mock and section-aware reference retain
``physical_closure_verified``/product claims at their declared research-only
ceiling and keep ``chain_promotion_blocked=true``.
The independent ``op.moc.mixed-regime-control-section`` operator remeasures
the section geometry, placement, scalar state, pressure lineage, and oriented
flux separately; its convergence is input evidence only, not external plume
validation.

The downstream planar handoff is now an explicit callback seam through
``run_mixed_regime_planar_field_solver``. It requires the exact terminal
request, the control section, and a closed ``MocMixedRegimeDownstreamPerimeterSpec``
as separate inputs, then checks that the returned field retains the exact
shock patch, perimeter geometry, and downstream-condition selections. A
varying section may pass this seam, but the result remains
``physical_closure_verified=false``, ``canonical_free_boundary_verified=false``,
and ``chain_promotion_blocked=true``. The first-cell planner stores the result
as evidence and leaves the terminal's open-closure decision unchanged; this
is the boundary for a future genuine planar mixed-regime solver, not a relabel
for the scalar reference. The field result must also retain the exact
control-section object it consumed; a callback that returns a valid scalar
field while ignoring that section is rejected as a seam failure.

## Planar MOC foundation

The first high-fidelity tranche is isolated in
[`moc_first_cell_contract_v1.md`](moc_first_cell_contract_v1.md) and
[`validation/moc_primitive_validation_v1.json`](validation/moc_primitive_validation_v1.json).
Its 15 Mach/gamma round trips, interior and centerline compatibility fixtures,
8-cell open underexpanded fan, pressure- and turn-prescribed attached
compression, sampled attached-shock fit, reflected centerline-to-free-boundary
march, 44-cell connected open reflected characteristic zone, boundary-side
shock-to-centerline candidate, post-shock first layer, a shock-seeded
boundary-conditioned full C+/C- field, mild-overexpanded lip-compression
branch, local ambient-pressure tangent residual, and mesh topology checks pass
with finite residuals. The full-field fixture carries total pressure into its
nodes and exposes a typed post-shock-field-perimeter handoff; a stateful chain
adapter rejects changed consumed boundaries, total-pressure resets, and
reduced-order fidelity. A deterministic three-cell prescribed-boundary planner
mock and a three-cell solver-generated chain reference exercise that adapter,
but both remain explicitly callback-conditioned and non-physical. The field
remains a prescribed-boundary contract, not a free-boundary solution or
product-provider result. A separate solver-generated marched attached-shock
reference now passes its local closed-field and 9/17/33-sample refinement
diagnostics, but it still uses explicit upstream callbacks and a linear
downstream-turn law. The reflected-zone sampler is domain-bounded and its
shock probe fails explicitly at the first point outside that solved lattice.
The reflected-zone shock entry point now uses the solved lattice's state and
pressure samplers directly and independently reports upstream coverage. In the
canonical case it stops at the first missing sample, so the new continued-cell
adapter cannot promote an outside-domain candidate. Its downstream flow-angle
condition is still caller-supplied and the result is not a production physical
first-cell solve. A bounded ambient-pressure closure shoot now regenerates the
shock/field for an explicit outer-turn bracket and validates the actual
non-shock/non-centerline perimeter; a scalar pressure root is still rejected
when the full pressure/tangency vector fails. The reflected-zone ambient
adapter carries the same independent coverage result, so the canonical attempt
remains a bounded failure and cannot become a chain cell. The planar MOC lane
now also has a correctly oriented shock-sourced ``C+`` /
ambient-sourced ``C-`` physical-boundary assembly. Its marcher enforces
ambient pressure and streamline tangency and retains the downstream terminal
characteristic trace; it does not infer an axis closure or create a provider or
chain seed.
The staged shock-cell transition composes this attachment/strip with the
centerline reflection and domain-bounded next-shock probe. It carries the
reflected outgoing trace and can return a verified normal-shock chain stop,
but it remains an open, non-promotable research transition because the
downstream condition is a named centerline-normal-shock reference and the
subsonic mixed-regime field is not solved.
Its terminal-field checkpoint can now close the validated supersonic side of
the transition at that shock and verify one-perimeter mesh topology. That
checkpoint preserves the fidelity boundary: it records inherited
characteristic-cell evidence only, leaves the downstream subsonic field
unsolved, and therefore cannot set physical closure or promote a chain cell.
The checkpoint rejects a mesh unless the complete solver-generated shock edge
is present and the terminal upstream state/pressure sample is carried with it.
The accepted physical field can now be projected into a bounded
``bounded-terminal-reflection-patch`` upstream source with the exact outgoing
``C-`` start point and no-extrapolation callbacks. The canonical generated
ambient-attachment attempt reaches an explicit ``open-physical-closure``
boundary because its outgoing source begins at ambient pressure and the
configured compression bracket does not straddle a next-shock solution; this
is recorded as a failed continuation, not as a resolved cell. An independent
bounded uniform-source case exercises the other legal outcome: a verified
subsonic normal shock becomes a typed physical termination while the
mixed-regime downstream field remains outside the supersonic MOC chain.
When a bounded source supplies a preferred shock-start point, the planner
requires that point to be at or downstream of the current cell interface;
stale upstream starts are rejected without callback sampling or backtracking.
The standalone validation report also routes the accepted physical first-cell
field through the canonical old-family/restarted-family caustic bridge and the
generic continued-chain planner. The exact caustic anchor is accepted as a
downstream handoff, then the bounded research lane stops at
``open-physical-closure`` after one cell; its independent planner measurement
passes, but physical termination and production promotion remain false until
the post-caustic remesher and downstream closure exist.
The first-cell-owned terminal closure bridge now consumes the composite's exact
outgoing ``C-`` handoff, fits that terminal shock, and closes only the
supersonic side. It reports ``converged_first_cell_supersonic_region`` while
the mixed-regime perimeter is absent; ``physical_closure_verified`` and chain
promotion therefore remain false, even when the terminal shock itself is
verified.
The oblique portion of that edge also carries independently fitted downstream
supersonic states; the centerline normal-shock endpoint remains scalar because
the subsonic state is outside the ``CharacteristicState`` contract. This is a
mixed-regime handoff seam only, not a closed downstream field. The oblique
states now also feed an explicitly open downstream C− continuation, first
cross-layer, and compatible zone; the canonical 17-sample case reaches the
centerline with 16 traces and assembles 119 open-zone cells. That evidence
closes the supersonic patch seam only. The final shock-side endpoint remains
the typed normal-shock interface, so mixed-regime closure and chain promotion
remain blocked. The separate scalar mixed-regime boundary contract now
validates that seam plus an explicitly closed downstream perimeter and
total-pressure lineage without creating subsonic MOC states. Its passing
status is only ``converged_subsonic_boundary_handoff``: the result remains
``physical_closure_verified=false`` and cannot promote a chain cell until a
real subsonic field/mesh solver supplies the missing field evidence.
That missing-field lane now has a separate solver-backed reference model,
``elliptic-isentropic-subsonic-reference``. It builds a connected mesh from a
closed scalar perimeter and an interior control point, then requires
thermodynamic, harmonic-extension, and velocity-divergence residual gates.
This is a model-specific closure/termination result, not a conversion of
subsonic states into ``CharacteristicState`` and not permission to promote a
continued MOC cell. The passing perimeter and terminal attachment in the
validation artifact are synthetic contract fixtures; the canonical plume still
needs its own physical downstream perimeter.
The reference lane also exposes a typed downstream-perimeter adapter that
binds explicit closed geometry and caller-owned scalar samples to the exact
terminal seam before applying the named downstream condition and radial
reference-field gates. This improves reproducibility for finite-domain
planner fixtures without inferring the canonical perimeter or promoting the
reference model to a production MOC provider.
An independent ``op.moc.mixed-regime-compressible-potential`` measurement
operator now rechecks that reference from its returned mesh and potential
samples. It independently verifies the scalar boundary seam, radial layout,
circulation, compressible mass residual, boundary-potential velocity, and
strict-subsonic limit across the reported refinement levels. A passing
measurement is evidence for the explicitly bounded scalar reference only;
``physical_closure_verified`` remains false and chain promotion remains
blocked.
The terminal probe now keeps the shock branch explicit as well. The weak
branch may reach the scalar normal-shock endpoint; a strong attached branch
that becomes subsonic earlier is retained as a typed scalar boundary with its
position, turn, Mach, pressure, and total-pressure loss. It is never coerced
into a ``CharacteristicState`` and is not treated as a normal-shock terminal
or a chain-promotable cell. The independent ``terminal_branch`` control makes
that fidelity choice visible in staged-transition reports.
It also has an explicitly labeled constant-`K+`
simple-wave continuation: it preserves the open-strip topology and advances
the shock probe through additional samples, but it remains an upstream
diagnostic assumption rather than a physical shock closure. The separately
labeled boundary-trace extension is diagnostic only. A terminal source-window
continuation now records a valid local patch separately from a full-strip
caustic, and a bracketed constant-invariant downstream shoot consumes that
patch without extrapolation. The canonical shoot currently returns a
no-bracket diagnostic, so the coupled upstream characteristic-strip/shock-path
closure remains open. The independent `op.moc.shock-cell-geometry`,
`op.moc.shock-cell-chain`, and `op.moc.shock-cell-chain-refinement` operators
now measure explicit shock-cell geometry,
perimeter topology, supplied shock-loss lineage, and exact adjacent
state/total-pressure handoff identity for the reference and planner fixtures,
while the separate `op.moc.chain-planner` operator independently audits the
continued-cell step sequence, returned-to-incoming fingerprints, the exact
state/total-pressure handoff retained by each returned field, typed
termination, and fidelity isolation without using the planner's own handoff
verdict as evidence across the prescribed mock, generated reference, and
field-coupled terminal traces and the typed-stop continuation probes. These
operators remain `not_accepted` without external observations or a physical
free-boundary closure.
At the detected source-strip caustic, a separate one-sided new-family restart
now reflects either selected C- anchor to the centerline and advances six
ambient-pressure/tangent C+ boundary samples with finite residuals, then
assembles a connected anchor-wedge plus ten-step two-triangle-per-step open
family band. Its
legacy triangular interior assembly remains an explicit non-forward geometry
failure, and the band has no shock or entropy closure, so it cannot promote a
continued cell. Its domain-bounded state/pressure sampler now feeds a
production shock-band seam in both canonical orientations. The seam refits
the supersonic shock samples, assembles a 27-cell open post-shock
characteristic zone, and records a typed subsonic centerline terminal. The
downstream zone is still an open mixed-regime handoff; physical closure and
chain promotion remain blocked until a subsonic field and complete perimeter
are solved.
The open zone now also exposes a bounded next-shock coupling adapter: it
independently resamples each generated shock point and returns an explicit
upstream-field boundary or verified normal-shock terminal. This is a solver
interface only and does not promote the open zone or replace the missing
mixed-regime perimeter.
Its one-step planner wrapper records the exact incoming post-shock perimeter
and preserves a valid-prefix miss as a non-physical ``upstream-field-boundary``
stop; the finite open zone is not reused as a resolved cell for later steps.
At the caustic handoff, a separate remesh-preparation contract now binds the
selected one-sided state, exact crossing point, local invariant-conditioned
shock bridge, and the required future shock-curve/new-family outputs. A ready
request is still a non-physical ``characteristic-caustic`` stop: it supplies
the next solver's exact inputs without treating a local shock state as a
remeshed field or a chain cell.
The executable ``solve_caustic_shock_remesh`` seam now consumes that request,
the exact incoming perimeter, and bounded upstream state/pressure callbacks.
It validates the event seam, solves a marched attached shock, and verifies the
solver-carried downstream characteristic field when the local invariant law
supports it. Even a converged result remains a research-only remesh report:
the physical first-cell ambient/terminal closure gate is hard-false, so the
corresponding ``plan_caustic_shock_remesh_chain`` wrapper records one exact
planner step and returns a typed non-physical stop rather than appending a
chain cell. Event, upstream-field, and shock-solve failures retain their
specific typed termination reasons.
When all remesh seams do pass, ``as_bounded_downstream_field`` exposes the
finite solver-carried field as an explicit research input for a later shock
solve. ``plan_caustic_remesh_downstream_field_chain`` and its invariant-law
counterpart require an explicit research opt-in, preserve the remesh's
physical-closure/promotion block in their diagnostics, and use the same
replace-only-after-complete-field-coupled handoff rule as the ordinary field
planner. These are continuation experiments, not production promotions of
the unresolved caustic seam.
The strict ``solve_caustic_shock_remesh_from_upstream_bridge`` entry point
uses the bounded old-family/restarted-family bridge at the exact event and
along the generated shock path. A gap or ambiguous branch is retained as an
explicit event/upstream failure with an independent bridge audit; no last
state or callback extrapolation can satisfy the remesh contract.
``plan_caustic_shock_remesh_chain_from_upstream_bridge`` routes the planner
through that same strict entry point and carries its bridge audit into the
typed one-step chain stop.
The converged post-shock field now exposes bounded state, static-pressure, and
total-pressure samplers backed by its solver-carried cell vertices and shock
boundary. A separate field-coupled continued-cell adapter and planner uses
those samples as the next shock's upstream field, preserves the exact prior
perimeter handoff, and reports either a complete next field or a typed
normal-shock/field-boundary stop. The canonical reference reaches the typed
normal-shock stop without extrapolation; its downstream turn law remains
caller-supplied and its planner is explicitly research-only, so this closes
the upstream sampling seam without creating a production continued-cell
provider.
The ambient-closed physical-field result now retains its downstream shock
states and total-pressure samples as well as its ambient and centerline
perimeters. Its bounded state/pressure samplers are available only when every
assembled cell vertex resolves to solver-carried data. A separate explicit-
perimeter next-cell adapter fits the candidate shock from that bounded field,
records the exact centerline handoff, and returns typed upstream-domain or
open-closure stops. It is a continuation foundation; the reflected-domain and
automatic ambient free-boundary shooter are still required before canonical
provider promotion.
The solver-owned ambient-centerline physical-field path now supplies the
canonical reflected closure for the generated ambient boundary: each ambient
``C-`` source is continued to the symmetry line and the terminal axis cells
are assembled explicitly. The legacy scalar axis/corner path remains a
diagnostic reference. The canonical nine-sample reflected field passes its
closure, state-sampling, and upstream-shock-coupling gates, while its physical
next-cell probe stops at the bounded upstream domain with
``UPSTREAM_FIELD_BOUNDARY`` rather than extrapolating. This does not authorize
the production provider; mixed-regime/reflected upstream extension,
next-cell free-boundary solving, refinement, and external validation remain
required.
The caustic-family-band branch has the same hard ceiling through a separate
one-step planner. It carries the exact prior post-shock perimeter into both
canonical restarted-family orientations, solves a bounded next shock and open
supersonic zone, and stops with ``OPEN_PHYSICAL_CLOSURE`` at the unresolved
mixed-regime perimeter. Its planner is ``upstream-coupled-research`` only and
never appends that open result as a resolved chain cell.
The seam's refinement probe reaches the same typed terminal at 5, 7, 9, and
11 shock samples in both orientations, with open-zone cell counts 5, 14, 27,
and 44 and decreasing shock-fit tangent residuals. The independent
shock-cell measurement operator rejects the open zone at the missing physical
endpoint, preserving the mixed-regime boundary as an explicit validation
failure rather than treating topology alone as cell acceptance.
The strict chain mode rejects a prescribed seed that lacks carried upstream
shock states, and the marcher reports `subsonic_terminal_required` while
carrying a typed normal-shock terminal diagnostic when an endpoint leaves the
supersonic MOC validity lane. The existing
basic and reduced-order visual lanes remain unchanged until a separate MOC
assembler passes free-boundary/compression closure, refinement, and external
measurement gates.
The generic resolved-chain contract also checks every returned candidate's
mesh against the shared axial interface. A shared-interface vertex is
allowed, but an upstream-reused mesh or a mesh with no downstream progress is
rejected; when state carry is required, the carried boundary receives the
same lower-domain check. This keeps planner bookkeeping from turning an old
field into a new cell under a fresh endpoint. Chain reports also expose the
bookkeeping interval and measured mesh/boundary axial extents for each cell,
making that freshness evidence visible in serialized planner output.
The independent `op.moc.chain-planner` measurement applies the same domain
freshness rule to planner traces and emits `domain_failure` plus
`domain_freshness_verified=false` when a returned cell reuses or fails to
advance beyond its shared interface. A passing handoff audit therefore does
not, by itself, certify that the downstream field was re-solved. The
prescribed post-shock planner mock now reports
`claim_fidelity_ceiling=prescribed-boundary-diagnostic` and the separate
`boundary_provenance` and `local_field_assembly` values: longer mock chains
exercise exact handoff bookkeeping, but they retain
`free_boundary_verified=false` and
`physical_chain_promotion_allowed=false`.
The standalone primitive artifact exercises a five-cell instance of that
fixture; the default three-cell unit fixture remains available for compact
tests.
Shock-seeded post-shock fields now expose a bounded `as_report()` contract
with mesh extents, explicit boundary paths, topology/residual summaries,
pressure-loss lineage, and incoming-handoff counts. The report is intended
for planner and visualization inspection; it does not convert the finite
shock-seeded field into canonical reflected-plume closure.
Solver-generated free-boundary shock reports now carry that field report under
`field`, preserving the same bounded inspection contract through the
higher-level shock/remesh handoff.
The caustic-remesh adapter applies the corresponding state-sampling and
finite-extent gate before exposing a bounded downstream field to
research-only continuation.
The generic validated closed-field result now retains its shock/centerline
state and total-pressure samples and emits a `CENTERLINE_TRACE` handoff when
it is used as a chain seed; status-only mesh validation is not enough for
continuation.
The separate solver-owned simple-wave terminal lane now makes one explicit
constant-invariant upstream trace from the exact caustic request, marches a
shock against a linear downstream turn profile, and retains the valid
supersonic prefix plus open post-shock characteristic zone when the axis
requires a normal-shock terminal. Its bounded ordinate/optional downstream-x
domain and event/bridge/pressure gates are independently reported; the
subsonic terminal is never coerced into a characteristic state. The matching
`plan_caustic_simple_wave_terminal_chain` wrapper records the exact prior
perimeter and returns an `OPEN_PHYSICAL_CLOSURE` one-step research stop. This
is solver-owned continuation evidence, not a physical caustic remesh, mixed-
regime perimeter, or production chain cell. The caustic upstream continuation
controller now owns the preceding branch-selection seam: it audits both
one-sided family restarts, returns `BRANCH_SELECTION_REQUIRED` without a
bridge when no branch is selected, and for an explicit anchor edge verifies
the event point, state, pressure, and total-pressure lineage before exposing
an x-split bounded bridge. This makes the continuation usable as a solver
interface for later shock-cell work while keeping the unresolved shock curve,
mixed-regime closure, and chain promotion explicitly blocked. The planner
wrapper records that branch audit and the typed non-physical caustic stop; it
does not append the bounded bridge as a chain cell or change the basic/reduced
provider lanes. A separate centerline-conditioned upstream Cauchy remesher
now consumes explicit centerline `C+` and outer/pre-shock `C-` traces,
verifies their exact event state/pressure seam, and exposes a bounded source
strip to one shock-chain attempt. The outer trace is caller-supplied coupled-
remesher data, not an inferred or extrapolated boundary; the resulting
upstream-field stop, open physical closure, and promotion block remain
explicit. Its sequence planner now permits multiple continued cells only when
each cell receives a distinct remesh from the preceding handoff. Remesh and
source-strip fingerprints, provider failures, upstream events, and typed
domain stops are retained in the planner audit; reuse is rejected and no
upstream Cauchy patch is promoted as a physical chain cell.
For later remeshes, the returned request must also echo the exact incoming
state/total-pressure handoff supplied to the provider. A remesh that omits or
changes that provenance is stopped before source-strip reuse is considered;
standalone Cauchy requests may leave the optional provenance empty.
The standalone validation report exercises this contract through a three-cell
research sequence: the first two domains are distinct and handoff-annotated,
while the third attempt reuses the source strip and is typed as an upstream
field boundary. This verifies orchestration and fidelity isolation only.

## What is done for the basic solver

The initial shock-cell solver is complete for its declared job when:

- it solves the steady, straight, axisymmetric, calorically-perfect,
  inviscid near-field problem inside its declared study envelope;
- its finite construction limit and matched-flow display extent are explicit;
  a construction boundary is never presented as a physical plume endpoint;
- its public provider advertises visual geometry only. Supporting spatial or
  flux capabilities may be added only as individually named capabilities with
  their own contracts;
- failed, strong/detached, or out-of-envelope cases are rejected or marked
  with structured applicability/termination evidence;
- results are deterministic and carry provider, configuration, model-lineage,
  and applicability evidence; and
- regression, validity-envelope, conformance, and performance checks pass at
  the frozen configuration ceiling.

“Done” means useful and bounded, not physically complete. Viscous mixing,
curved or washed flow, finite-rate chemistry, radiation, and detector
modeling belong to later lanes.

## Reduced-order shock-train boundary

`shock-cell-reduced-order-v1` is a separate experimental lane. It consumes the
resolved first-cell result, then advances downstream cells with an explicit
calibration object carrying applicability ranges and closure provenance. The
downstream geometry is labeled `SCALED_REDUCED_ORDER`; it is not silently
promoted to resolved characteristic/MOC geometry. Physical termination checks
are kept separate from `max_cells` and axial-domain safety truncation.

The canonical provider is visual-only and requires a caller-supplied
calibration. The recovered CJ-UEJ archive supplies component context and
provenance, but it does not provide the disjoint calibration/validation split
needed to accept the closure. The current evidence is recorded in
[`shock_train_component_validation_v1.json`](validation/shock_train_component_validation_v1.json)
and remains `not_accepted`.

## Signature boundary

Fast shock-cell geometry can be useful context for a future signature
approximation, but geometry and display channels are not a spectral source
model. The current signature product is therefore served by an independent
table-backed provider and must not be silently populated from shock-cell
output.

If a future approximation combines them, it must be a named adapter/profile
with explicit emissivity, spectral-law, and integration assumptions. It needs
its own validation evidence and lineage; it does not promote
`shock-cell-basic-v1` or alter the meaning of the existing signature-table
provider.

## Focal-plane boundary

The basic solver is not an FPA solver. It may be used in an investigation as a
geometry-only prefilter or candidate-support estimate, provided that result is
labeled as such. A focal-plane result requires, at minimum, resolved ray
transfer, camera/optics geometry, detector spectral response, exposure or time
integration, pixel integration, and an explicit noise/digitization policy.
Until those contracts and validation gates exist, no provider may advertise an
FPA capability.

The current `optical-transfer-v1` provider is intentionally narrower than that
future product: it resolves exact homogeneous gray transfer through a straight
constant-radius support. The downstream boundary operators now preserve an
explicit camera/optics mapping identity and deterministic ADC policy, but their
synthetic checks do not validate the external BSUV2, EMAP, or ALSI sensor-space
gates, do not create a measured image, and do not advertise an FPA provider.

## Fidelity isolation rules

1. A higher-fidelity model is a new provider/profile and a new lineage. It is
   not a growing set of flags on the basic solver.
2. High-fidelity results may be compared with the basic solver over an overlap
   domain. Comparison, calibration studies, and residual reports must not
   mutate the frozen basic configuration automatically.
3. A change that expands morphology, mixing, thermochemistry, radiation,
   temporal behavior, or product claims requires a new profile and a review of
   its applicability and validation evidence.
4. Product derivations must preserve explicit parent lineage and claims. A
   visual result never becomes a signature or FPA result merely because a
   consumer asks for more fields.
5. Performance is part of the basic solver contract. If a proposed improvement
   makes the fast lane materially slower or more stateful, it belongs in a
   separate lane even when it agrees with the same equations in a small test.

## Reflected physical-field continuation boundary

The higher-fidelity planar lane now has a concrete one-transition path after
the accepted first field. The field can expose its open shock/ambient source
submesh, carry the terminal `C+` trace into the centerline reflection patch,
and provide the reflected `C-` front to the next attached-shock marcher.
The source projection and centerline seam are independently reported, with a
declared mesh-discretization tolerance.

The canonical transition ends at a verified normal-shock/subsonic boundary.
That is a valid typed physical stop for the supersonic chain, not acceptance
of the downstream mixed-regime field. The planner retains only the resolved
seed, blocks cell promotion at that boundary, and remains research-only
because its downstream turn condition and external validation are not yet
canonical. Further shock cells require a separately solved mixed-regime or
reflected-domain continuation. No basic, reduced-order, signature, or FPA
provider is changed by this lane.

# Continued terminal-patch planner handoff

The transition also exposes a typed downstream request and a planner-only
adapter for the prescribed mixed-regime mock and scalar reference. Those
results prove request identity and local seam bookkeeping only; they remain
beside the terminal chain, are not attached as canonical closure, and cannot
raise the product fidelity ceiling.

The downstream handoff now also has a reproducible research reference that
projects an explicit scalar control section into an explicit perimeter and
solves the nonlinear compressible isentropic potential field. Its affine
profile assumption, projection residual, perimeter condition, field residuals,
and independent measurement are all reported. This is useful for planner and
visualization work, but it is not a canonical reflected-MOC free-boundary
solve, does not infer geometry, and cannot seed a continued shock-cell chain.

The physical chain lane additionally exposes an explicit next-cell candidate
contract and a planner mock for repeated candidates. Each candidate carries
its own shock geometry, downstream angles, ambient samples, and axial extent;
the mock delegates to the strict ambient-closed physical-field continuation
solver and advances only after a complete field is accepted. The bounded
upstream sampler therefore returns a typed boundary stop instead of inventing
or extrapolating states. This remains a prescribed-boundary diagnostic fixture
with no canonical free-boundary, product-provider, or external-validation
claim.

The solver-generated reference lane adds the same boundary discipline to a
repeated-cell planner. `MocBoundedUpstreamFieldSource` requires bounded,
non-extrapolating state and static-pressure callbacks, while
`MocSolverGeneratedAmbientClosedPostShockChainReference` advances only after
the existing attached-shock/ambient/centerline physical field is completely
accepted. The default source wraps the preceding finite field and therefore
ends with `UPSTREAM_FIELD_BOUNDARY`; a uniform source callback is a named
multi-cell plumbing fixture, not reflected upstream coupling. This lane stays
research-only until a reflected/free-boundary remesher, mixed-regime handoff,
refinement evidence, and independent external validation are available.
The caustic bridge can now be adapted into the same bounded source contract;
its callbacks retain one-sided branch selection and return no state across a
bridge gap. This makes the new-family corridor consumable by the generic
planner for diagnostics, while its unresolved caustic/shock and downstream
closure gates continue to block cell promotion.
