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
field while ignoring that section is rejected as a seam failure. The
continued-prefix counterpart,
``plan_ambient_closed_post_shock_chain_terminal_reflection_patch_ambient_closure_with_planar_handoff``,
repeats the same prefix audit and passes the exact terminal request from the
last accepted physical field into that callback. Its planar result remains
beside the supersonic chain, with ``physical_closure_verified=false`` and
``chain_promotion_blocked=true``; it is not a new chain cell or a provider
promotion path.

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

The continued terminal-patch planner now has the same explicit planar callback
seam: it forwards the exact terminal request, caller-owned control section,
and closed perimeter specification after the one-step reflected transition.
The returned ``MocMixedRegimePlanarSolveResult`` retains the exact request in
its report and is recorded beside—not attached to—the supersonic chain. This
is a verified handoff only; canonical physical closure and chain promotion
remain blocked. The bounded terminal patch was checked against the reusable
source-characteristic-strip contract and is intentionally not promoted as a
new source lattice because its axis/front geometry is degenerate there.

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
multi-cell plumbing fixture, not reflected upstream coupling. An explicit
`MocAmbientClosedChainSourceMode.TERMINAL_REFLECTION_PATCH` option can now
derive the bounded next-source projection from the accepted field's outgoing
shock/ambient strip and reflected centerline patch without a manually wired
callback. On the canonical case it reaches the same typed
`OPEN_PHYSICAL_CLOSURE` boundary after the accepted prefix; it does not
extrapolate or promote a next cell. This lane stays research-only until a
reflected/free-boundary remesher, mixed-regime handoff, refinement evidence,
and independent external validation are available.
The caustic bridge can now be adapted into the same bounded source contract;
its callbacks retain one-sided branch selection and return no state across a
bridge gap. This makes the new-family corridor consumable by the generic
planner for diagnostics, while its unresolved caustic/shock and downstream
closure gates continue to block cell promotion.

The planar reference lane also exposes a separately named frozen-profile
variant. It retains piecewise-linear, non-affine tangential data from an
explicit control section, requires a constant normal component for its
potential extension, and refuses perimeter points outside the measured
transverse span. This is a higher-resolution scalar research lane for planner
and visualization work; it remains below canonical reflected-MOC free-boundary
closure and cannot promote a continued shock cell.

The first-cell planner exposes this variant through a named wrapper so its
non-affine profile evidence can be compared with the affine reference without
merging their model assumptions. The wrapper records the exact terminal seam
and leaves the scalar field beside the supersonic chain; it does not alter the
chain termination or promotion gates.

The continued terminal-patch result exposes the matching attachment boundary
for an explicitly selected downstream field. Attachment requires exact
terminal and supersonic-patch identity and a locally physically closed field;
even a successful attachment remains a terminal result with chain promotion
blocked and no production claim. The default planner mock/reference path does
not attach, preserving the distinction between seam evidence and canonical
downstream closure.

The current downstream continuation checkpoint is the named
``terminal-reflection-patch-ambient-closure`` research lane. It consumes a
bounded reflected patch, permits an explicit ambient-matched Mach-wave start
and centerline endpoint, and requires strict shock total-pressure loss at
interior samples. The default attached-shock solver remains strict; the
zero-strength exception is never a global relaxation.

The lane keeps the chain contract and the internal source contract separate:
the prior cell's centerline trace is the next field's ``incoming_handoff``,
while the reflected patch's outgoing characteristic trace is its separate
``patch_handoff``. Only a complete ambient-closed field with state sampling,
retained upstream shock data, and exact handoff identity may cross into the
resolved planar-MOC chain. The
``MocTerminalReflectionPatchAmbientClosureChainReference`` planner is
research-only and, on the canonical bounded fixture, produces a three-cell
resolved prefix followed by an explicit configured solver stop. Its endpoint
is taken from the next field's actual ambient boundary rather than from a
caller-supplied fabricated interface.

This does not close the canonical reflected plume. Further cells need a
reflected-domain/remeshing method that handles the alternating compression /
expansion character of the chain, a coupled downstream free-boundary and
mixed-regime field, refinement and conservation evidence, and external
validation observations. The basic visual, reduced-order, signature, ray,
and focal-plane-array providers remain unchanged and cannot consume this
research result by implication.

## Trace-polarity continuation checkpoint

The research lane now classifies every reflected outgoing `C-` trace against
the declared affine endpoint-angle reference. The result distinguishes
compression-compatible, expansion-required, mixed-polarity, and neutral
interior turns and retains the sample-level evidence. This makes the
alternating character of later shock-cell attempts visible rather than hiding
it behind a failed scalar turn law.

For an opt-in continued-chain experiment, the named
`reflected-trace-referenced-compression-envelope` profile uses the exact
source trace as its endpoint baseline and adds a bounded positive
`4*s*(1-s)` interior compression envelope. It is useful for deterministic
handoff and stability testing, but it does not solve the canonical expansion
fan or reflected-domain remeshing problem. Its report therefore sets
`canonical_expansion_remesh_solved=false` and `production_claim_allowed=false`.

The corresponding planner carries a three-cell resolved research prefix on
the bounded fixture, verifies exact handoff links, uses actual ambient-boundary
endpoints, and stops at an explicit configured solver boundary. This evidence
does not change the fidelity tier or authorize promotion into any basic,
reduced-order, signature, ray, or focal-plane-array provider. Canonical
reflected-domain closure, mixed-regime continuation, refinement, and external
validation remain required.

## Reflected-domain remesh checkpoint

The next continuation seam is now explicit rather than implicit. A
`MocReflectedDomainRemeshRequest` treats the prior terminal-patch outgoing
`C-` front as one exact reflection/alternating-family anchor. It requires a
new centerline `C+` source row and a distinct outer `C-` source curve; reusing
the single prior characteristic as the whole outer boundary is rejected as a
degenerate domain. The solver validates the reflection endpoint, family
polarity, source ordering, diagonal compatibility, and scalar total-pressure
handoff before exposing a bounded source field. Optional centerline and outer
source pressure rows now preserve a caller-supplied nonuniform pressure
lineage through that bounded field; they do not infer shock entropy.

`plan_reflected_domain_remesh_shock_chain` adapts that field for one
research-only shock attempt. Its sequence counterpart requires a fresh
remesh/source field for each later cell and an exact echo of the preceding
chain handoff. Both planners retain `physical_closure_verified=false` and
`production_claim_allowed=false`. The scalar source strip does not solve
nonuniform entropy transport, the canonical free boundary, the mixed-regime
downstream field, or the physical shock-cell closure; those remain the next
gates. The basic visual, reduced-order, signature, ray, and focal-plane-array
providers remain untouched.
The independent `op.moc.reflected-domain-remesh` measurement operator
rechecks the raw incoming trace, polarity, reflection seam, source rows,
pressure lineage, topology, and bounded state sampling. It also preserves the
typed rejection of reusing the prior single `C-` front. A passing measurement
is bounded remesh evidence only and keeps physical closure, chain promotion,
and production claims false.

## Physical field-chain audit checkpoint

The continued terminal-patch lane now has a separate
`op.moc.ambient-closed-physical-field-chain` measurement operator. It audits
the solver-returned fields as raw data: explicit shock, ambient, and
centerline perimeter paths; remeasured ambient pressure/tangency; retained
node states and pressures; characteristic residuals; shock total-pressure
loss; and mesh topology. Adjacent fields must preserve the exact centerline
state/total-pressure handoff and begin at the preceding field's ambient
interface. Explicit zero-strength shock endpoints are accepted only when the
field declares the endpoint allowance; interior samples remain strict.

The standalone evidence report exercises the planner reference and the
independent field audit together: three locally closed research fields and
two exact handoff links pass with fresh downstream domains. The audit remains
non-promoting evidence. Canonical alternating-family reflected remeshing,
mixed-regime/free-boundary closure, refinement, and external validation are
still open, and the basic/reduced, signature, ray, and focal-plane-array
providers remain untouched.

## Reflected-remesh to physical-field chain checkpoint

The reflected-domain lane now has an explicit bridge into the real
ambient-closed physical-field solver. `MocBoundedUpstreamFieldSource` can expose
one converged Cauchy remesh through bounded state and static-pressure callbacks;
the adapter uses the newly supplied outer source curve as the preferred shock
start and returns no extrapolated state outside the remesh domain.

`plan_reflected_domain_remesh_ambient_closed_chain` consumes a seed physical
field, an initial remesh, and a remesh callback for later cells. Before each
physical solve it requires an exact incoming centerline handoff, a fresh
remesh object, and a fresh source-strip fingerprint. Accepted remeshes are then
passed to the ambient-pressure/centerline-reflection field solver, not the
source-strip-only shock adapter. The planner records each remesh and solver
attempt, but remains research-only: the outer curve is explicit Cauchy data,
the remesh requires explicit source-row pressure data, canonical free-boundary
closure is false, and product providers are unchanged.

The remesh now has a bounded variable-entropy transport path. Optional
centerline and outer source total-pressure rows are retained at source samples
and carried to each interior node by its `C-` family; the bounded sampler
interpolates those values alongside the compatible state, and independent
measurement rechecks the rows and samples. This closes pressure lineage inside
an explicit Cauchy patch, but it does not compute shock entropy loss, infer the
outer ambient curve, or authorize a canonical continued cell.

The outer-source boundary now has a separate solver-owned reference seam.
`solve_reflected_domain_outer_source_curve` uses an explicit prior outer seed,
marches the later centerline `C+` states to ambient-pressure/tangent endpoints,
and reassembles the generated rows as a bounded pressure-aware source field.
`op.moc.reflected-domain-outer-source` independently rechecks those rows,
ambient residuals, topology, and source sampling. The result can be bound into
a fresh reflected-remesh request, but it remains a source-domain result: the
centerline source, entropy production across shocks, downstream perimeter,
canonical free-boundary closure, and product promotion are still blocked.

The next local continuation checkpoint is now implemented separately as
`solve_reflected_domain_alternating_source`. It starts with the exact first
state of the outgoing reflected `C-` front, independently verifies its `C-`
reflection against the prior patch's centerline anchor, and marches repeated
`C-` centerline / ambient-pressure `C+` outer-point pairs. Its two-triangle
band contract records only the neighboring characteristic seams actually
solved; it does not reuse the old front as a full source curve or claim every
cross-pair in the triangular source-strip lattice.

The independent `op.moc.reflected-domain-alternating-source` measurement
recomputes the trace, polarity, seed, characteristic steps, ambient pressure
and tangency, alternating seams, topology, and bounded state sampling. The
canonical bounded fixture passes this audit. The lane remains research-only:
shock entropy production, canonical reflected free-boundary/mixed-regime
closure, refinement, external observations, and chain promotion are still
open, and the lower-fidelity visualization, reduced-order, signature, ray,
and focal-plane-array providers remain untouched.

## Alternating-source physical-field checkpoint

`solve_reflected_domain_alternating_physical_field` couples the finite
alternating Cauchy band to the existing ambient-closed physical MOC field.
Its attachment point is an explicit ambient-matched zero-strength seam; its
interior shock turns use a positive, solver-owned local compression envelope;
and its final centerline endpoint may be zero-strength only under the explicit
endpoint allowance. The bridge retains fitted shock loss, field sampling, and
the exact incoming state/total-pressure handoff. The independent
`op.moc.reflected-domain-alternating-physical-field` measurement repeats those
checks from raw outputs.

`plan_reflected_domain_alternating_source_chain` accepts that result for one
state-carrying research cell and then emits a typed no-next-cell decision,
never reusing the bounded source band. This is a validated local seam, not a
production provider: the local envelope must still be replaced by a canonical
reflected free-boundary/mixed-regime closure and compared against refinement
and external observations. Basic/visual, reduced-order, signature, ray, and
focal-plane-array providers remain isolated.

## Trace-profile continuation boundary checkpoint

The alternating physical-field solver now exposes the exact reflected-trace
compression profile as a separate `use_trace_referenced_profile` option. When
selected together with outer-seed attachment, the downstream turn callback is
recomputed from the retained outgoing `C-` trace rather than from the local
alternating-band state. The independent field measurement reconstructs that
profile from raw trace samples and checks the same endpoint and interior law.

This option is deliberately not the default for the automatic multi-cell
planner. A profile can close an individual sampled field while its terminal
trace is not usable for the next remesh at that resolution; the default chain
therefore retains the prior local-envelope behavior and its existing fresh
domain/typed-stop gates. The profile mode remains a bounded research
experiment, with canonical reflected remeshing, mixed-regime/free-boundary
coupling, refinement, external observations, and product promotion still
blocked.

## Global reflected-shock remesh checkpoint

`solve_reflected_domain_global_shock_remesh` is the next bounded solver-owned
step for continued shock-cell work. It sweeps explicit outer-source /
centerline-target pairs and a finite set of compression-profile shape values
across the entire sampled shock path. Each attempt reruns the complete
solver-owned first-cell shoot; a failed attempt is retained as a typed result,
and no bracket or state is bridged across an invalid field. The result exposes
the selected residual, all attempt reports, and the separate statuses
`NO_ENDPOINT_CLOSURE` and `ATTEMPT_FAILURE` so an incomplete sweep cannot be
mistaken for a global closure.

`op.moc.reflected-domain-global-shock-remesh` independently remeasures the
source band, every first-cell trial, source/profile lineage, selected-attempt
identity, and endpoint residual. A complete no-root sweep is accepted as
research evidence only. Even a locally aligned endpoint keeps
`physical_closure_verified=false`, `canonical_free_boundary_verified=false`,
`canonical_euler_verified=false`, `chain_promotion_blocked=true`, and
`production_claim_allowed=false` because the reflected shock remains a
prescribed profile family rather than a coupled free-boundary/Euler solution.

`plan_reflected_domain_global_shock_remesh_chain` carries the exact seed
centerline state/total-pressure handoff into this sweep and preserves the
solver's typed stop. It returns a one-cell research prefix with an
`open-physical-closure` stop for the current no-root fixture; it does not
fabricate or promote a continued cell. The fast/basic visualization and
reduced-order lanes, signature lane, ray-transfer lane, and focal-plane-array
lane remain isolated from this research result.

## Local normalized Euler audit checkpoint

`op.moc.physical-field-euler-audit` is an independent diagnostic for a closed
state-carrying post-shock field. It reconstructs normalized calorically-perfect-
gas primitives from the retained Mach, flow angle, gamma, and total-pressure
samples, then reports Rankine--Hugoniot mass/momentum/energy jumps on the
fitted shock and a conservative finite-volume flux residual for every retained
characteristic cell. The cell samples are exposed through a bounded read-only
field method; no state is interpolated outside the assembled mesh.

The audit is intentionally below the promotion ceiling. It independently
reports finite local cell evidence even when the shock jump fails, and it
never changes the solver's closure flags or authorizes a chain handoff. On the
current reflected-domain reference, the cell residuals are finite (about
`5.2e-3` maximum at the fixture resolution), while the stored shock tangent
and thermodynamic jump disagree (about `1.6e-2` on the global-remesh fixture;
the uniform reference is larger). This is a concrete reason to keep the
global compression envelope out of the canonical Euler lane rather than
loosening the validation threshold.

The global-remesh planner records one Euler-audit report per retained attempt
and requires this audit to be passed before any future promotion review. The
current planner therefore remains a one-cell research prefix with
`global_reflected_shock_remesh_euler_audit_accepted=false`,
`canonical_euler_verified=false`, `chain_promotion_blocked=true`, and
`production_claim_allowed=false`. The next physics gate is a new reflected
shock/free-boundary construction whose stored shock geometry, downstream
state, characteristic orientation, and Euler residuals close together.

## Locally Euler-consistent shock-segment checkpoint

`solve_euler_consistent_attached_shock_segment` is the first isolated physics
primitive for that next construction. It accepts a supersonic upstream state,
an upstream total-pressure scale, and a downstream angle that turns toward a
descending shock. It uses the attached compression solver for the weak/strong
branch, positions the segment from its actual tangent, reconstructs the
downstream state at the target ordinate, and checks normalized
Rankine--Hugoniot mass, momentum, and energy jumps.

The primitive's `converged_local_euler_shock` status means only that one shock
segment closes locally. It deliberately leaves physical/canonical closure
false and chain promotion blocked. The older attached-shock reference keeps
its compatibility behavior unchanged; its opposite-sign turn convention is
rejected by this lane as `noncompressive_turn` rather than silently repaired.
The next implementation gate is an orientation-aware post-shock
characteristic field on this shock Cauchy curve, followed by reflected
free-boundary coupling and indexed external validation.

## Parameterized planar free-boundary research boundary

The current higher-fidelity downstream experiment is isolated under the exact
model name `parameterized-2d-compressible-potential-free-boundary-reference`.
It solves a nonlinear compressible potential field on an explicit radial mesh
while iterating a discrete concave free-boundary envelope until the selected
boundary-normal velocity residual closes. Its terminal request, scalar
control section, perimeter, ambient pressure, and local field are all retained
as typed evidence.

The matching independent measurement operator rebuilds the expected
terminal/centerline/envelope perimeter, reruns the scalar seam and physical
condition validators, and compares the reported normal residual against an
independent finite-element reconstruction. A passing measurement verifies
only this bounded research model. Uniform control-section total pressure and
gamma, explicit downstream length/outlet height, and the axis-aligned current
parameterization are intentional fidelity boundaries.

The result keeps `canonical_free_boundary_verified=false`,
`chain_promotion_blocked=true`, and `production_claim_allowed=false`.
Canonical reflected-MOC/free-boundary coupling, numerical refinement, and
indexed external observations remain release gates; the fast visualization,
signature, ray, and focal-plane-array providers do not consume this lane.

The planar reference has a separate refinement audit,
``op.moc.mixed-regime-planar-free-boundary-refinement``. It requires fresh
reruns at strictly increasing free-boundary sample counts and independently
remeasures every returned field through the planar reference operator. The
audit derives resolution and mesh metadata from the typed results, fixes the
terminal request/control-section seam and solver configuration, and compares
the normalized envelope shape, centerline speed, mesh area, and boundary-
normal velocity residuals. The canonical 6/8/10 rerun passes locally with
perimeter counts 11/13/15, node counts 21/25/29, and cell counts 30/36/42.

This is a numerical-sensitivity gate for the explicitly parameterized
compressible-potential reference. It does not establish canonical reflected
MOC closure: the refinement measurement keeps
``canonical_free_boundary_verified=false``, ``chain_promotion_blocked=true``,
and ``production_claim_allowed=false``. A genuine reflected 2-D
shock/ambient/free-boundary entropy solve, followed by refinement and indexed
external observations, is still required before any product or continued-cell
promotion.

## Reflected shock-interface entropy handoff

The terminal mixed-regime request now has a solver-owned
`MocMixedRegimeEntropyHandoffResult`. It retains the exact ordered oblique
shock patch and scalar normal-shock endpoint as an open interface profile. At
each sample it carries downstream Mach/flow angle/gamma, upstream and
downstream total pressure, the local total-pressure ratio, and
``log(p0_up/p0_down)`` as the fixed-total-temperature nondimensional entropy
production coordinate. Cumulative arc length is retained so a future
downstream solver can interpolate only inside the solved shock interface.

`build_mixed_regime_entropy_handoff` rejects missing terminal data, invalid
regime transitions, zero-length interface segments, and any total-pressure
gain. The convenience methods on the terminal field and transition expose the
same artifact without changing their terminal-stop semantics. The handoff is
an entropy input contract, not entropy advection: it has
`physical_closure_verified=false`, `canonical_free_boundary_verified=false`,
`chain_promotion_blocked=true`, and `production_claim_allowed=false`.

The independent `op.moc.mixed-regime-entropy-handoff` measurement reconstructs
the expected patch-plus-terminal samples from the request, remeasures arc
length and pressure loss, and rejects changed sample data or stale summary
metrics. This local gate passes in the standalone report. A coupled
subsonic entropy-transport/free-boundary solve, numerical refinement, and
indexed external observations remain required before any continued shock-cell
chain or product provider can consume the result.

The first-cell, continued-prefix, scalar-reference, and planar-handoff
planners now retain and independently measure this same entropy seam. Their
reports expose the handoff and a separate
`mixed_regime_entropy_handoff_verified` gate, while preserving
`chain_promotion_blocked=true` and `production_claim_allowed=false`. This is
planner observability only; it does not change the fidelity boundary or
authorize downstream field closure.

The prescribed continued-cell planner mock also now makes its pressure
lineage map explicit. A normalized coordinate is retained for each
prescribed next-shock sample, the exact incoming boundary is interpolated only
through that declared map, and the schedule is serialized for independent
planner/visualization diagnostics. The standalone five-cell mock uses a
nonuniform schedule to exercise this path. It remains a fixture mapping—not a
streamline correspondence or entropy/free-boundary solve—and therefore does
not change the mock's prescribed-boundary fidelity ceiling or authorize chain
promotion.

## Explicit mixed-regime entropy transport boundary

The mixed-regime research lane now has a typed
`MocMixedRegimeEntropyTransportResult`. It binds an explicit source arc-length
and streamline identifier to every node in an already closed scalar field,
then compares the field's total pressure with the pressure profile carried by
the shock-interface handoff. Each streamline group must contain at least two
nodes with one declared source coordinate, and interpolation is bounded to the
solved interface; source extrapolation and implicit terminal-pressure resets
are rejected.

The independent
`op.moc.mixed-regime-entropy-transport-boundary` measurement receives the
request, handoff, field, and transport result separately. It rebuilds the
pressure interpolation locally, checks the exact terminal/patch field seam,
recomputes pressure and entropy-coordinate residuals, and checks the reported
flags and metrics. The standalone fixture and both planner paths pass this
measurement with a terminal-source map.

This is a solver-owned Cauchy/streamline boundary reference, not an Euler
entropy-advection solve. The result remains
`physical_closure_verified=false`,
`canonical_free_boundary_verified=false`, `chain_promotion_blocked=true`, and
`production_claim_allowed=false`. The first-cell, continued terminal, and
continued-prefix planner reports expose the opt-in transport result and its
independent measurement, but do not attach it as a new supersonic cell or feed
it to the visualization, signature, ray, or focal-plane-array providers. The
next physics gate is a coupled reflected shock/ambient/free-boundary solve
whose entropy transport is solved rather than assigned by a caller-owned map.

## Solver-owned variable-entropy/free-boundary research reference

The next higher-fidelity lane is
`moc.mixed-regime-variable-entropy-free-boundary`. It takes the typed
shock-interface entropy handoff and a vertical downstream control section,
derives its own reverse source pressure/gamma profile, and solves a structured
triangular stream-tube reference with an iterated outer height. Streamline IDs,
source arc coordinates, transported total pressure, free-boundary samples,
and residual histories are retained in the typed result instead of being
hidden in a caller-owned map.

Its acceptance surface is deliberately split. Settled cells must satisfy the
mapped continuity, entropy-advection, and mass-flow checks, while connector and
entrance regularization residuals remain reported separately. Transverse
momentum is measured for every cell and is expected to remain nonzero until a
coupled transverse solve exists. The independent
`op.moc.mixed-regime-variable-entropy-free-boundary` operator rebuilds the
source profile, topology, boundary condition, pressure transport, and all
reported metrics from the typed inputs.

The standalone stress case uses a derived pressure-loss lineage because the
current production handoff's outer sample can exceed the terminal total
pressure; a scalar no-gain perimeter cannot accept that input. This derived
case is explicitly labeled and does not rewrite the production handoff or
count as external validation.

This remains a research reference only. It does not close the entrance seam,
transverse Euler momentum, shock fitting, or canonical reflected free-boundary
coupling, so its physical/canonical flags remain false and chain promotion
remains blocked. The basic visual, signature, ray, and focal-plane-array
providers are unchanged and cannot consume its cells. The next gate is a
solver-owned coupled 2-D Euler/MOC/free-boundary implementation with
refinement and indexed external observations.

## Geometry-owned first-cell candidate

`solve_first_cell_geometry_owned_candidate` is the higher-fidelity local
first-cell seam beside the planner mock. Its upstream input is a bounded
state/pressure source and its shock input is a finite geometry seed. The
candidate derives the downstream turn from each shock tangent and the attached
theta-beta-Mach/Rankine--Hugoniot relation; callers cannot supply a hidden
downstream-angle law. The first shock segment is corrected against ambient
static pressure and the terminal segment is corrected against the centerline
target before the solver-owned ambient march and centerline-reflected physical
field are assembled.

The candidate's local closure gate is intentionally narrower than a canonical
claim. It can report a converged finite shock/ambient/centerline field with
state sampling and fitted upstream shock data, while the global reflected
free-boundary topology, coupled 2-D Euler residual, and indexed external
validation remain unsolved. Its independent measurement operator
`op.moc.first-cell-geometry-owned-candidate` rechecks the retained geometry,
local RH residuals, pressure loss, ambient boundary, topology, state sampling,
and upstream coupling. A bounded source returning no state or pressure is a
typed upstream-field stop; source extrapolation is out of contract.

Accordingly the candidate and measurement retain
`canonical_free_boundary_verified=false`,
`canonical_euler_verified=false`, `external_validation_verified=false`,
`chain_promotion_blocked=true`, and `production_claim_allowed=false`. The
candidate is reported alongside the existing prescribed-boundary planner mock
and continued shock-cell references for research comparison only. No basic
visualization, signature, ray, or focal-plane-array provider consumes it. The
next gate is a globally remeshed reflected shock/free-boundary solve with
refinement and indexed external observations, after which a separate chain
promotion review can be performed.

## Bounded shock-shape correction and continued-chain guard

`solve_first_cell_free_boundary_correction` is a bounded research correction
around the geometry-owned candidate. Its single shape parameter scales the
downstream shock abscissae about the attachment point while retaining the
sample ordinates and centerline target. Each trial invokes the local
solver-owned candidate and carries the final ambient-boundary `C-` trace to
the centerline. The resulting relative static-pressure mismatch is the
declared scalar residual. Endpoint and bisection trials are retained, and a
bounded upstream-source miss remains a typed boundary failure.

The independent
`op.moc.first-cell-free-boundary-correction` operator rebuilds the axial shape
family and axis residuals from retained trial data, then independently
measures the selected candidate field. On the uniform reference, the lower
and upper shape bounds both retain a positive residual of approximately
`0.15276`; the solver therefore reports `axis_pressure_no_bracket`. This is a
successful audit of an unresolved boundary, not physical free-boundary
closure.

The standalone refinement fixes the same narrow shape bracket, `0.95 <= s <=
1.05`, and reruns fresh corrections at 5, 9, and 17 shock samples. Each
resolution passes the raw field audit and retains the same positive residual;
the ambient-to-axis boundary is still open. The earlier wider local family
can leave the fine-resolution characteristic domain, so it is not widened by
fallback or extrapolation.

The reusable
`op.moc.first-cell-free-boundary-correction-refinement` operator now owns the
resolution audit used by the standalone gate. It independently remeasures
each correction, requires the declared sample-count order and fixed shape
bracket, compares selected residuals, and preserves the non-promotion flags.
Its converged status means that an unresolved research boundary is stable
across the declared cases; it does not authorize a continued shock-cell
handoff.

`plan_first_cell_free_boundary_correction` is a planner guard that forwards
the correction-owned `open-physical-closure` decision without creating a
continued-cell handoff. The correction, planner guard, and measurement must
keep `canonical_free_boundary_verified=false`,
`canonical_euler_verified=false`, `chain_promotion_blocked=true`, and
`production_claim_allowed=false`. Existing prescribed planner mocks and
continued shock-cell chains may validate exact handoffs and topology, but
cannot promote this local correction. Promotion requires a globally remeshed
shock, an independently closed post-shock characteristic field, and
resolution/refinement evidence.

## Geometry-owned first-cell research-chain handoff

`plan_first_cell_geometry_owned_research_chain` is the explicit boundary
between the local geometry-owned first-cell candidate and a continued
shock-cell experiment. It requires the independent first-cell measurement
before invoking a continuation. The default path feeds the exact candidate
physical field into the solver-generated terminal-reflection-patch remesher;
an optional `MocPrescribedAmbientClosedPostShockChainMock` exercises the same
handoff with caller-supplied next-shock and ambient boundaries.

The handoff retains the candidate field and every accepted downstream field.
`op.moc.first-cell-geometry-owned-research-chain` independently checks the
candidate, planner step trace, first-field identity, exact centerline state /
total-pressure handoffs, fresh downstream domains, and local physical closure.
The current standalone case passes with two continued cells and an explicit
configured reference stop. A mock candidate that leaves the bounded field
returns `upstream-field-boundary`; no state or pressure is extrapolated.

The separate
`op.moc.first-cell-geometry-owned-research-chain-refinement` measurement
repeats the three-cell prefix at sample counts 5, 9, and 17. It independently
checks per-resolution candidate/chain/field evidence, exact repeat handoff
fingerprints, typed termination consistency, and bounded changes in per-cell
axial extent, shock spacing, radius, and mesh area. This makes deterministic
continuation and resolution sensitivity visible without promoting the chain.

The higher-fidelity sibling
`plan_first_cell_geometry_owned_alternating_research_chain` seeds the same
candidate field into the automatic reflected-domain source path. It derives a
fresh alternating `C-`/`C+` source band from each accepted field, retains the
exact incoming centerline handoff, and is independently checked at 5, 9, and
17 shock samples. The bounded default prefix contains the candidate plus two
continued fields and ends with a typed `solver-returned-no-next-cell`
decision. Its explicit compression envelope is a research control, not the
canonical reflected expansion/free-boundary law; canonical mixed-regime
closure, external validation, and product promotion remain false.

This handoff is useful for research visualization and chain-topology work only.
The candidate seed, reflected-patch continuation, and prescribed mock all
retain `canonical_free_boundary_verified=false`,
`canonical_euler_verified=false`, `chain_promotion_blocked=true`, and
`production_claim_allowed=false`. No product/provider lane is allowed to
consume the result until the globally coupled reflected free-boundary solve,
refinement, and indexed external observations are closed.
