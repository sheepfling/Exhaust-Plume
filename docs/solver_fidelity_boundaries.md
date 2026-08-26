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
| `planar-moc-primitives-v1` | boundary-conditioned field/chain foundation; provider pending | Standalone planar characteristic states, scalar inversions, compatibility residuals, pressure- and turn-prescribed attached compression, sampled attached-shock fit, solver-generated marched attached-shock reference field, reflected centerline-to-free-boundary march, reusable triangular source-boundary strip, assembled open characteristic zone, domain-bounded shock-path coupling probe, shock-seeded closed post-shock C+/C- field, total-pressure handoff, and state-carrying chain adapter | None yet; future MOC first-cell provider only after reflected-field coupling, canonical free-boundary physical closure, refinement, and external validation gates | No public visual, signature, optical, detector, or FPA claim; no axisymmetric or reacting-flow claim |
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
nodes and exposes a typed terminal-characteristic-trace handoff; a stateful
chain adapter rejects changed consumed traces, total-pressure resets, and
reduced-order fidelity. A deterministic three-cell prescribed-boundary planner
mock and a three-cell solver-generated chain reference exercise that adapter,
but both remain explicitly callback-conditioned and non-physical. The field
remains a prescribed-boundary contract, not a free-boundary solution or
product-provider result. A separate solver-generated marched attached-shock
reference now passes its local closed-field and 9/17/33-sample refinement
diagnostics, but it still uses explicit upstream callbacks and a linear
downstream-turn law. The reflected-zone sampler is domain-bounded and its
shock probe fails explicitly at the first point outside that solved lattice.
The canonical source strip also has an explicitly labeled constant-`K+`
simple-wave continuation: it preserves the open-strip topology and advances
the shock probe through additional samples, but it remains an upstream
diagnostic assumption rather than a physical shock closure. The separately
labeled boundary-trace extension is diagnostic only, and the coupled upstream
characteristic-strip/shock-path closure remains open. The existing basic and
reduced-order visual lanes remain unchanged until a separate MOC assembler
passes free-boundary/compression closure, refinement, and measurement-operator
gates.

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
