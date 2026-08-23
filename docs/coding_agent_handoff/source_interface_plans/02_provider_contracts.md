# Provider Contracts

## Generic lifecycle

A plume provider is constructed with provider-specific definition and configuration. It creates a session, and the session produces snapshots from provider-specific operating states.

```text
PlumeProvider
  -> create_session(definition, configuration)
      -> PlumeSession
          -> snapshot(operating_state)
              -> PlumeSnapshot
```

## Provider-specific typed inputs

Do not require a single universal `PlumeOperatingState` for every provider.

Examples:

### Shock-diamond analytical model

```text
Definition:
- nozzle radius/area
- plume-frame convention

Configuration:
- expansion-line count
- compression-line count
- maximum construction passes
- termination policy

Operating state:
- bulk nozzle-exit thermodynamic state
- uniform ambient state
```

### Signature-table provider

```text
Definition:
- table asset / source identity

Configuration:
- interpolation policy
- extrapolation policy
- caching policy

Operating state:
- time, or another table coordinate bundle
```

### Rotor-washed model

```text
Definition:
- nozzle geometry
- source-frame convention

Configuration:
- centerline/tube solver settings
- environmental-coupling settings

Operating state:
- nozzle state
- uniform ambient reference
- external spatial flow-field service
```

### GPU transient solver

```text
Definition:
- domain mesh
- boundary topology

Configuration:
- device/resource settings
- numerical tolerances
- chemistry/radiation options

Operating state:
- boundary fields
- time-dependent forcing
- optional initialization/checkpoint state
```

## Reusable standard input schemas

The library may define reusable schemas that providers can opt into.

### Bulk nozzle-exit state

- static pressure [Pa]
- static temperature [K]
- static density [kg/m³]
- plume-frame velocity vector [m/s]
- ratio of specific heats, when relevant
- species mass fractions, when relevant

### Uniform ambient state

- static pressure [Pa]
- static temperature [K]
- static density [kg/m³]
- plume-frame velocity [m/s]
- composition, optional

### Axisymmetric nozzle profile

- radius grid
- pressure profile
- temperature profile
- density profile
- axial/radial velocity profiles
- species profiles

### Surface boundary field

- boundary coordinates/connectivity
- pressure/temperature/velocity fields
- species/turbulence fields

## Provider descriptor

The descriptor should expose:

```text
provider_id
provider_version
core_contract_major_version
capability_versions
input schema identifiers
execution profile
fidelity description
supported validity domains
```

Capability versions should be independent from the provider package version.

Example:

```text
core                         v1
axisymmetric-zone-field      v1
spatial-support              v1
directional-spectral-source  v1
spectral-ray-transfer        v1
```

## Capability registry

The snapshot should have an explicit capability registry rather than relying only on structural `Protocol` checks.

Example capability IDs:

```text
axisymmetric-zone-field
spatial-support
projected-area
directional-spectral-intensity
spectral-ray-transfer
optical-medium
scene-radiance-renderer
```

Consumers request a capability by ID and major version. Unsupported capability requests raise a typed error.

## Fidelity metadata

Recommended fields:

```text
geometry_model
spatial_dimensionality
temporal_model
flow_model
thermochemistry_model
radiation_model
environmental_coupling
validation_level
```

Avoid a single `LOW/MEDIUM/HIGH` value as the only fidelity description.

## Execution profile

Recommended fields:

```text
time_access:
  random_access | monotonic_forward

concurrency:
  reentrant | session_isolated | serialized

deterministic: bool
supports_direction_batching: bool
maximum_direction_batch_size: int | None
checkpointable: bool
preferred_device: cpu | cuda | external
snapshot_retention:
  independent | until_session_close | until_next_snapshot
```

## Snapshot retention

CPU analytical/table providers should normally return independent immutable snapshots.

GPU providers may return snapshots that are valid only until the next state advance. Such semantics must be explicit and accessing an invalidated snapshot must raise `SnapshotInvalidatedError`.

## Termination status

Every spatial plume result should include structured termination information.

Recommended reasons:

```text
requested_construction_limit
weak_wave_cutoff
ambient_equilibrium
spatial_domain_limit
temporal_domain_limit
provider_failure
```

Recommended report fields:

```text
reason
is_physical
axial_extent_m
pressure_residual_fraction
temperature_residual_fraction
last_active_wave_type
warnings
```

Until a physical plume-end policy is implemented, the current analytical solver should report:

```text
reason = requested_construction_limit
is_physical = false
```

## Error taxonomy

Recommended typed errors:

```text
UnsupportedCapabilityError
CapabilityVersionMismatchError
ProviderConfigurationError
OperatingStateDomainError
SpectralDomainError
AngularDomainError
TemporalDomainError
PointSourceApproximationError
SnapshotInvalidatedError
ContractViolationError
ProviderFailureError
```

Do not silently extrapolate outside a provider's declared validity domain.
