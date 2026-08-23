# Signature Tables and GPU Providers

## Signature-table provider

A precomputed table is a first-class plume/source provider, not merely a file format.

It may be generated from:

- the analytical plume model;
- CFD;
- GPU radiative transfer;
- measurements;
- another authoritative simulation.

At runtime it can directly implement directional spectral intensity without exposing geometry.

## Recommended table semantics

Dimensions:

```text
time
view
wavelength
```

Coordinates:

```text
time_s(time)
view_direction_plume(view, xyz)
wavelength_m(wavelength)
```

Variable:

```text
spectral_radiant_intensity_w_sr_m(time, view, wavelength)
```

Metadata:

```text
contract_version
provider_id
provider_version
source_definition_hash
asset_sha256
frame_convention
fidelity_description
validity_domain
interpolation_policy
extrapolation_policy
creation_provenance
```

Use one `view` dimension with a 3-vector coordinate instead of mandatory azimuth/elevation axes.

## Interpolation policy

Interpolation must be explicit and versioned.

Recommended policies:

```text
time: nearest | linear | provider-specific
wavelength: linear | log-linear | exact-only
view: nearest | spherical interpolation | provider-specific
```

Extrapolation should default to `reject`.

A table provider must never silently clamp or extrapolate unless the configured policy explicitly allows it and the result carries a quality flag.

## Provenance and caching

Every cached or baked signature should be traceable to:

```text
source model/provider ID
provider version
contract version
input/definition hash
configuration hash
asset digest
optical-property model version
radiative-transfer model version
creation timestamp
```

Cache identity should be content-addressed where possible.

## GPU transient provider

The same lifecycle supports a GPU implementation:

```text
provider.create_session(...)
    -> allocate device state

session.snapshot(state_0)
    -> initialize/advance

session.snapshot(state_1)
    -> advance monotonically

snapshot capability query
    -> batched radiance/ray evaluation

session.close()
    -> release resources
```

Execution metadata might declare:

```text
time_access = monotonic_forward
concurrency = serialized
snapshot_retention = until_next_snapshot
preferred_device = cuda
supports_direction_batching = true
```

## Version-1 transport boundary

For interoperability, version 1 should define semantic results as ordinary host arrays. Device-native arrays, DLPack, CUDA streams, asynchronous futures, and external-service handles can be later execution extensions.

The physical contract should not depend on a GPU array type.

## Preflight compatibility

Consumers should verify execution compatibility before starting a run.

Example invalid pairing:

```text
provider requires monotonic-forward time
+
consumer plans out-of-order event replay
=
configuration/preflight error
```

This should not fail halfway through a simulation.

## Scene-radiance renderer capability

The simple ray-transfer contract assumes each ray can be represented as:

\[
L_{out} = L_{source} + T L_{background}
\]

For general multiple scattering or globally coupled radiation, that may be insufficient because one ray depends on illumination from many other directions.

A future provider should then advertise a stronger capability such as:

```text
scene-radiance-renderer
```

rather than pretending to satisfy the simpler independent-ray contract.

## Rotor-wash environmental field

Curved/rotor-washed plumes should receive environmental coupling as an optional service, not by adding helicopter-specific fields to every operating-state type.

Example service:

```text
AmbientFlowField.sample(time, positions)
 -> velocity
 -> pressure
 -> temperature
 -> density
```

A straight shock-diamond provider can ignore it. A curved analytical provider can sample it. A GPU provider can use it as a boundary/forcing field.
