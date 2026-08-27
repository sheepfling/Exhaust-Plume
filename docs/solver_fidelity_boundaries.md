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
| `planar-moc-primitives-v1` | boundary-conditioned field/chain foundation; provider pending | Standalone planar characteristic states, scalar inversions, compatibility residuals, pressure- and turn-prescribed attached compression, sampled attached-shock fit, solver-generated marched attached-shock reference field, reflected centerline-to-free-boundary march, reusable triangular source-boundary strip, assembled open characteristic zone, domain-bounded shock-path coupling probe and reflected-zone shock/chain entry point, shock-seeded closed post-shock C+/C- field, shock-sourced C+/ambient-sourced C- physical-boundary strip, ambient-perimeter validator and bounded scalar closure shoot, total-pressure handoff, state-carrying chain adapter, separate elliptic-isentropic subsonic reference field, and independent shock-cell geometry/topology measurement operators | None yet; future MOC first-cell provider only after complete reflected-field coupling, canonical ambient-perimeter physical closure, refinement, and external validation gates | No public visual, signature, optical, detector, or FPA claim; no axisymmetric or reacting-flow claim; the elliptic reference is not a supersonic MOC chain cell |
| `shock-cell-basic-v1` | active | Fast, steady, straight, low-order shock-cell construction | `plume.visual.sectioned-tube@1`; supporting spatial/engineering handoffs where explicitly advertised | No physical signature, ray transfer, detector image, mixing, chemistry, radiation, or curved/washed flow |
| `shock-cell-reduced-order-v1` | experimental | One resolved first cell plus explicitly calibrated, scaled downstream shock-train continuation | `plume.visual.sectioned-tube@1` through `plume.shock-train-reduced-order` | No resolved downstream MOC claim, spectral signature, ray transfer, detector image, FPA, or unvalidated universal closure |
| `signature-table-mvp-v1` | active | Independent unresolved spectral lookup | `plume.signature.spectral-radiant-intensity@1` | No solved flow, geometry reconstruction, atmosphere, optics, detector, or focal-plane array |
| `washed-integral-v1` | planned | Curved, rotor-washed, or crossflow integral continuation | Visual and engineering products only after a provider and validation gate exist | No automatic spectral or ray-transfer claim |
| `optical-transfer-v1` | active | Straight constant-radius support with exact homogeneous gray transfer | `plume.optical.spectral-ray-transfer@1` | No chemistry, atmosphere, curved transport, detector integration, or focal-plane electronics |
| `focal-plane-array-v1` | validated downstream adapter; no provider | Camera/optics identity, spectral response, exposure, pixel integration, expected noise variance, and deterministic digitization | A future image/detector product | Not a plume solver; requires validated ray transfer and external detector evidence |

The machine-readable copy is
[`solver_fidelity_matrix_v1.json`](solver_fidelity_matrix_v1.json). The matrix
is a governance artifact; it does not create a second product contract.

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
closure remains open. The independent `op.moc.shock-cell-geometry` and
`op.moc.shock-cell-chain` operators now measure explicit shock-cell geometry,
perimeter topology, and supplied shock-loss lineage for the reference and
planner fixtures, but remain `not_accepted` without external observations.
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
At the caustic handoff, a separate remesh-preparation contract now binds the
selected one-sided state, exact crossing point, local invariant-conditioned
shock bridge, and the required future shock-curve/new-family outputs. A ready
request is still a non-physical ``characteristic-caustic`` stop: it supplies
the next solver's exact inputs without treating a local shock state as a
remeshed field or a chain cell.
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
