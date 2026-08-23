# Unified Plume Architecture: Provider, Products, and Consumer Views

## 1. Purpose

This document is the authoritative architecture seam for all plume models in
Exhaust-Plume. It reconciles the physics roadmap with the swappable-provider
interface plans.

The central rule is:

> A plume provider is defined by what products it can provide, not by whether
> it is "low fidelity", "high fidelity", "straight", or "curved".

There are two primary consumer use cases:

1. **Signature use** — the consumer needs an intrinsic unresolved spectral
   source as a function of time and observer direction. The provider may use
   geometry internally, but geometry need not be exposed.
2. **Spatial/physical use** — the consumer needs geometry, local fields,
   optical-medium state, ray transfer, or other spatially resolved products.

The same provider may serve either or both use cases.

## 2. Orthogonal dimensions

Do not encode these dimensions into one inheritance hierarchy.

### 2.1 Consumer product level

```text
SIGNATURE
  directional spectral radiant intensity
  optional band-integrated intensity

SPATIAL
  support/bounds
  geometry/zones
  local thermodynamic/species fields
  optical medium
  resolved spectral ray transfer
  optional scene radiance
```

### 2.2 Plume morphology

```text
STRAIGHT
CURVED
ROTOR_WASHED
CROSSFLOW_DEFLECTED
MULTI_ENGINE_INTERACTING
GENERAL_3D
```

Morphology describes plume structure; it does not determine fidelity.

### 2.3 Physics fidelity

Examples:

```text
signature table
empirical band model
reduced-order shock-cell model
integral mixing plume
planar analytical field
axisymmetric CFD surrogate
RANS/LES snapshot
coupled CFD + radiation
```

Fidelity is metadata and applicability information, not an API tier.

### 2.4 Radiation fidelity

Examples:

```text
none
gray LTE
band model
correlated-k
line-by-line LTE
non-LTE
particles/scattering
```

### 2.5 Execution behavior

Examples:

```text
random-access CPU
monotonic transient GPU
serialized external service
reentrant table lookup
checkpointed CFD sequence
```

Execution constraints are not physics capabilities.

## 3. Provider lifecycle

The stable lifecycle is:

```text
PlumeProvider[DefinitionT, ConfigurationT, OperatingStateT]
    |
    +-- create_session(definition, configuration)
            |
            v
        PlumeSession
            |
            +-- snapshot(operating_state)
                    |
                    v
                PlumeSnapshot
                    |
                    +-- capability registry
```

Provider inputs remain strongly typed and provider-specific. A curved
rotor-washed provider is allowed to require a spatial ambient-flow service;
a signature-table provider is not required to fabricate a nozzle exit state.

## 4. Product lattice, not product hierarchy

Products form a partial order because some products can be derived from richer
ones, but not vice versa.

```text
local flow / optical medium
           |
           v
resolved spectral ray transfer
           |
           v
spectral radiance image
           |
           v
unresolved directional spectral radiant intensity
```

A provider may implement any product directly.

For example:

- a CFD+radiation provider can derive all downstream products;
- a CFD-derived lookup table may expose only directional intensity;
- a shock-cell provider may expose geometry/flow first, then gain a separate
  radiation adapter later;
- a tabulated signature provider can expose directional intensity without any
  spatial capability.

No consumer may assume that a provider exposing directional intensity also
exposes geometry.

## 5. Two consumer profiles

### 5.1 Signature consumer

Minimal request:

```text
time / snapshot
wavelength grid
source-to-observer unit directions in plume frame
```

Minimal intrinsic result:

\[
J_\lambda(t,\hat{\mathbf s})
\quad [\mathrm{W\,sr^{-1}\,m^{-1}}].
\]

This excludes range, atmosphere, optics, and detector response.

A signature consumer should depend on a very small `DirectionalSpectralSource`
port, not on `PlumeSnapshot` internals.

### 5.2 Spatial/physical consumer

Possible requests include:

```text
conservative spatial support
zone/mesh geometry
local flow state q(t,x)
thermochemical state
particle state
optical coefficients
spectral ray transfer
resolved radiance image
```

A renderer, focal-plane simulator, engineering diagnostic, or coupling model
uses these optional capabilities.

## 6. Geometry visibility rule

Geometry has three statuses:

```text
INTERNAL_ONLY
EXPOSED_APPROXIMATE
EXPOSED_VALIDATED
```

A provider may require detailed geometry internally to compute a signature but
advertise no geometry capability. This is normal and encouraged when the
geometry is an implementation detail or not valid as an interchange product.

The current shock-diamond solver initially has `EXPOSED_APPROXIMATE` geometry
only after invalid/placeholder polygons are removed or rejected.

## 7. Common plume-local frame

Every physical plume instance that exposes spatial or directional products uses
a right-handed plume-local frame:

```text
origin: nozzle exit center or provider-declared source reference
+X: nominal downstream direction at the source
+Y,+Z: complete the right-handed frame
```

For curved plumes, +X is the source/nozzle reference direction, not the local
tangent everywhere downstream.

The direction passed to an unresolved source is always:

```text
source_to_observer_direction_plume
```

and is a finite unit vector.

## 8. Curved plume representation

A curved plume is not a different consumer interface. Its spatial model adds a
centerline and local transported frame.

Let centerline arc length be \(s\), with

\[
\mathbf c(s),\qquad
\mathbf t(s)=\frac{d\mathbf c}{ds}.
\]

A tube-like reduced-order plume may define cross-section radius \(R(s)\) and
cross-sectional fields in a local frame \((\mathbf t,\mathbf n,\mathbf b)\).

The centerline evolves under a provider-specific momentum/environment model,
for example

\[
\frac{d}{ds}(\dot m\,\mathbf u)
=
\mathbf f_{\mathrm{entrainment}}
+\mathbf f_{\mathrm{crossflow}}
+\mathbf f_{\mathrm{buoyancy}}
+\cdots.
\]

Those equations belong to the curved provider. Consumers continue to request
standard spatial or radiometric capabilities.

## 9. Capability IDs

Core capability IDs and major versions should begin with:

```text
spatial-support                 v1
axisymmetric-zone-field         v1
centerline-tube-field           v1
local-flow-state                v1
projected-area                  v1
directional-spectral-intensity  v1
spectral-ray-transfer           v1
optical-medium                  v1
scene-radiance-renderer         v1
uncertainty                     v1
```

A capability version changes only when that capability's semantic contract is
broken. Provider package versions are separate.

## 10. Provider descriptor

The descriptor must keep capability, fidelity, morphology, and execution
separate:

```text
provider_id
provider_version
core_contract_major_version
capability_versions
input_schema_ids

morphology:
  straight | curved | rotor-washed | crossflow | general-3d

fidelity:
  geometry_model
  spatial_dimensionality
  temporal_model
  flow_model
  mixing_model
  thermochemistry_model
  radiation_model
  environmental_coupling
  validation_level

execution:
  time_access
  concurrency
  deterministic
  direction_batching
  checkpointability
  preferred_device
  snapshot_retention
```

There is deliberately no single `LOW/MEDIUM/HIGH` field with semantic meaning.

## 11. Recommended provider families

### ShockCellAnalyticalProvider

Morphology: straight, nominally axisymmetric-looking spatial output from a
planar analytical construction.

Initial capabilities:

```text
spatial-support
axisymmetric-zone-field
projected-area
```

Later adapters may add:

```text
optical-medium
spectral-ray-transfer
directional-spectral-intensity
```

### IntegralStraightPlumeProvider

Morphology: straight.

Capabilities:

```text
spatial-support
local-flow-state
centerline-tube-field
```

May be chained after a shock-cell provider.

### CurvedIntegralPlumeProvider

Morphology: curved/crossflow/rotor-washed.

Provider-specific input includes an ambient spatial flow service.

Capabilities are the same standard spatial capabilities; curvature does not
change consumer APIs.

### SignatureTableProvider

Morphology may be metadata only.

Capabilities:

```text
directional-spectral-intensity
```

No geometry is required.

### ImportedFieldProvider

Wraps CFD/RANS/LES fields.

Capabilities may include local state, optical medium, ray transfer, or derived
signatures depending on the imported asset.

### GpuTransientPlumeProvider

May implement general 3-D fields and radiation with monotonic-time execution
and short-lived snapshots. Semantics remain compatible with the same
capabilities.

## 12. Adapters are first-class

Adapters convert richer products into simpler products without modifying the
underlying provider.

Examples:

```text
AxisymmetricZoneField
  + OpticalPropertyModel
    -> SpectralRayTransfer

SpectralRayTransfer
  -> orthographic integration
    -> DirectionalSpectralIntensity

LocalFlowState
  + Chemistry/Radiation model
    -> OpticalMedium

Legacy calculatePlumeZones(...)
  -> ShockCellAnalyticalProvider snapshot
```

This prevents radiative physics from being hard-coded into the wave solver.

## 13. External-consumer integration boundary

An unresolved tracking/sensor application should own a source port equivalent
to:

```text
evaluate(epoch, wavelength_grid, source_local_directions)
  -> spectral radiant intensity
```

Exhaust-Plume supplies an adapter implementing that port. Exhaust-Plume does
not depend on a particular consumer package.

Observation propagation then applies:

\[
E_\lambda
=
\frac{\tau_\lambda J_\lambda}{R^2},
\]

followed by optics, quantum efficiency, noise, and detection logic.

## 14. Non-negotiable architecture rules

1. Provider-specific inputs; generic capability outputs.
2. Signature and spatial use cases share the provider lifecycle.
3. Straight/curved is morphology metadata, not an interface split.
4. Low/high fidelity is metadata, not an inheritance split.
5. Geometry may be internal-only.
6. Capability absence is explicit; never fabricate unsupported products.
7. Radiation is separable from flow whenever possible.
8. Intrinsic source products exclude sensor range, atmosphere, and detector
   response.
9. Source pose is separate from source emission.
10. Every result retains provider, calibration, validity, and approximation
    provenance.
