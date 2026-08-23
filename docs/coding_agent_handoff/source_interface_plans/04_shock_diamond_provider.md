# Shock-Diamond Provider Plan

## Current solver role

The current analytical solver is a geometry and thermodynamic zone model. It should not initially advertise a validated IR-signature capability.

It naturally provides:

```text
axisymmetric-zone-field
spatial-support
projected-area
```

Potential later capabilities:

```text
directional-spectral-intensity
spectral-ray-transfer
```

only after a separate optical-property/radiative-transfer model is attached.

## Required solver refactor

Split the current public path into two layers:

```text
calculatePlumeZones(... total/nozzle parameters ...)
    -> calcNozzleExitFlowState(...)
    -> calculatePlumeZonesFromExitState(...)
```

The existing `calculatePlumeZones` remains backward-compatible and delegates to the new exit-state entry point.

The provider calls `calculatePlumeZonesFromExitState` directly.

## Provider-specific inputs

### Definition

```text
nozzle radius or equivalent exit geometry
plume-frame convention
```

### Configuration

```text
num_expansion_lines
num_compression_lines
maximum_construction_passes
termination policy
numerical tolerances
```

Prefer `maximum_construction_passes` over `num_plumes` in the new provider API because the current parameter controls repeated construction passes rather than physical plume count/lifetime.

### Operating state

```text
bulk nozzle-exit static pressure
bulk nozzle-exit static temperature
bulk nozzle-exit density
bulk nozzle-exit velocity vector
gamma
uniform ambient pressure
uniform ambient temperature/density/velocity
```

For the current provider, reject states outside its model domain rather than weakening the generic contract.

Examples of provider-domain checks:

- exit Mach must be supersonic;
- exit velocity should be materially axial;
- gamma must be present and > 1;
- input values finite and positive where required;
- unsupported extreme pressure/Mach regimes produce a typed domain error;
- geometry must be finite before spatial/radiometric use.

## Neutral zone-field representation

Do not make current `ZoneResult` the cross-provider interchange type.

Use a provider-neutral axisymmetric zone record:

```text
zone_id
polygon_xr_m
static_pressure_pa
static_temperature_k
static_density_kg_m3
mach
phase
provider_metadata
```

The current solver maps:

```text
corners_ru[:, 0] -> axial x
corners_ru[:, 1] -> radial r
```

Construction diagnostics such as points A-K and the quadratic `plume_fit` remain provider diagnostics, not generic interchange geometry.

## Placeholder geometry

Some current compression subdivisions may contain placeholder NaN polygons.

The provider must not silently expose them as usable spatial geometry.

Recommended policies:

1. omit invalid polygons from `AxisymmetricZoneField` while preserving diagnostic state information; or
2. mark the snapshot spatial capability invalid and raise a typed contract/domain error.

The initial implementation should favor strict rejection for any capability that needs those polygons.

## Termination report

Until a physical end criterion exists:

```text
reason = requested_construction_limit
is_physical = false
```

Later policies may include:

- weak-wave cutoff;
- persistent ambient-equilibrium criterion;
- finite study-domain truncation;
- entrainment/mixing model;
- coupling to a higher-fidelity downstream solver.

## First radiometry adapter

Do not embed spectroscopy in the wave solver. Attach a separate pipeline:

```text
AxisymmetricZoneField
  + ZoneOpticalPropertyModel
        |
        v
AxisymmetricSpectralRayTransfer
        |
        +--> resolved rays
        |
        +--> FarFieldFromRayTransfer
                  |
                  v
       DirectionalSpectralIntensity
```

For a homogeneous segment of path length `ell` and absorption coefficient `kappa_lambda`:

\[
T_\lambda = e^{-\kappa_\lambda \ell}
\]

and for a source function `S_lambda`:

\[
L_{out}
=
T_\lambda L_{in}
+
S_\lambda(1-T_\lambda)
\]

The ray capability should expose the plume contribution and transmittance separately.

## Initial software-fixture optical model

A first `GrayLteOpticalPropertyModel` may be used strictly as an integration fixture:

- gray or simple temperature-dependent opacity;
- no scattering;
- homogeneous zones;
- assumed composition;
- no Doppler treatment;
- no claim of validated exhaust spectroscopy.

This is useful to test the geometry/ray/source interfaces before the chemistry and spectral databases are selected.
