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
| `shock-cell-basic-v1` | active | Fast, steady, straight, low-order shock-cell construction | `plume.visual.sectioned-tube@1`; supporting spatial/engineering handoffs where explicitly advertised | No physical signature, ray transfer, detector image, mixing, chemistry, radiation, or curved/washed flow |
| `signature-table-mvp-v1` | active | Independent unresolved spectral lookup | `plume.signature.spectral-radiant-intensity@1` | No solved flow, geometry reconstruction, atmosphere, optics, detector, or focal-plane array |
| `washed-integral-v1` | planned | Curved, rotor-washed, or crossflow integral continuation | Visual and engineering products only after a provider and validation gate exist | No automatic spectral or ray-transfer claim |
| `optical-transfer-v1` | planned | Local thermochemical/optical field and resolved transport | `plume.optical.spectral-ray-transfer@1` | No detector integration or focal-plane electronics |
| `focal-plane-array-v1` | planned downstream adapter | Camera geometry, spectral response, exposure, pixel integration, noise, and digitization | A future image/detector product | Not a plume solver; requires validated ray transfer as an input |

The machine-readable copy is
[`solver_fidelity_matrix_v1.json`](solver_fidelity_matrix_v1.json). The matrix
is a governance artifact; it does not create a second product contract.

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

