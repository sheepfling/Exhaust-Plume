# Architecture Overview

## Goal

Support multiple interchangeable exhaust-plume implementations while allowing different consumers to request only the information they need.

Expected provider families include:

- current straight shock-diamond analytical model;
- curved or rotor-washed analytical model;
- empirical or precomputed spectral signature tables;
- axisymmetric CFD-derived surrogates;
- transient 3-D GPU solvers;
- future volumetric radiative-transfer renderers.

The design should support both unresolved far-field consumers and image/focal-plane consumers that need spatially resolved plume structure.

## Fundamental split

The architecture has two primary layers:

```text
provider-specific definition / configuration / operating state
                           |
                           v
                     PlumeSession
                           |
                     snapshot(state)
                           |
                           v
                     PlumeSnapshot
          _________________|____________________
         |                 |                    |
         v                 v                    v
      geometry       unresolved source     resolved transfer
      / fields          capabilities         capabilities
         |                 |                    |
         |                 +---------+----------+
         |                           |
         v                           v
 engineering/analysis         sensor adapters/renderers
                                   |
                                   v
                         external consumers / FPA
```

## Design rule: capability is not fidelity

Capabilities describe what a provider can return.

Examples:

- axisymmetric zone field;
- conservative bounds;
- projected area;
- directional spectral radiant intensity;
- spectral ray transfer;
- optical-medium fields;
- full scene-radiance renderer.

Fidelity describes how the result was calculated.

Examples:

- inviscid analytical wave model;
- integral mixing model;
- RANS/LES surrogate;
- gray-body radiation;
- band model;
- correlated-k;
- line-by-line;
- steady/quasi-steady/transient;
- axisymmetric versus 3-D.

A high-fidelity CFD product might be distributed only as a far-field table. A simple analytical model might support resolved image formation. Therefore there must not be a `LowFidelity -> MediumFidelity -> HighFidelity` interface hierarchy.

## Design rule: execution behavior is also separate

A provider also has runtime properties that are not physics fidelity:

- random-access versus monotonic time;
- reentrant versus serialized access;
- deterministic versus seeded stochastic behavior;
- batch-size limits;
- checkpointability;
- snapshot lifetime;
- CPU/GPU/external-service execution.

These belong in an execution profile.

## Three contracts

### 1. Provider construction contract

Strongly typed, provider-specific inputs:

```text
PlumeProvider[DefinitionT, ConfigurationT, OperatingStateT]
```

The generic lifecycle is stable, but the physical inputs are not forced into one giant universal object.

### 2. Plume result contract

A generic capability-bearing snapshot:

```text
PlumeSnapshot
├── AxisymmetricZoneField
├── SpatialSupport
├── ProjectedArea
├── DirectionalSpectralIntensity
├── SpectralRayTransfer
└── OpticalMedium
```

This is the primary plume interoperability seam.

### 3. Consumer radiometric source contract

An external consumer owns a small source interface:

```text
epoch + source-local observer direction + wavelengths
    -> spectral radiant intensity
```

An Exhaust-Plume integration adapter implements that interface. The consumer
never needs to know about nozzle Mach number, shock cells, rotor wash, or CFD
meshes.

## Coordinate convention

All plume-core geometry should use a plume-local right-handed frame:

- origin: nozzle-exit center;
- `+X`: nominal downstream exhaust direction;
- `+Y`, `+Z`: complete the right-handed basis.

Core APIs should use direction vectors rather than azimuth/elevation. Angles can be convenience adapters.

## Stable radiometric quantities

For unresolved far-field use:

\[
I_\lambda(t, \hat{s})
\quad [\mathrm{W}/(\mathrm{sr}\,\mathrm{m})]
\]

For resolved ray transfer:

\[
L_{\lambda,\mathrm{out}}
= L_{\lambda,\mathrm{source}} + T_\lambda L_{\lambda,\mathrm{background}}
\]

with source spectral radiance in W/(m² sr m) and transmittance dimensionless.

## Why geometry stays optional

A plume does not have a unique physical surface. An isosurface is model- and threshold-dependent, and a table-based source may have no geometry at all.

Therefore the first geometric capability should be conservative spatial support/bounds, not a required mesh.

Meshes, zone fields, and optical-medium fields should remain optional capabilities.
