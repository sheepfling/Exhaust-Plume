# Conformance and Testing Plan

## Shared provider conformance suite

Every provider should run against a common contract-test suite in addition to provider-specific physics tests.

## Universal snapshot invariants

Test that:

- descriptor capability IDs match the actual capability registry;
- capability major versions are explicit;
- deterministic providers return equivalent values for identical inputs;
- provider inputs are not mutated;
- output arrays are defensively copied or immutable;
- all shapes match the capability specification;
- unsupported capability requests raise `UnsupportedCapabilityError`;
- out-of-domain requests raise typed domain errors;
- termination/validity/provenance metadata is always present where required.

## Directional spectral intensity conformance

Inputs:

- positive strictly increasing wavelength grid;
- finite unit source-to-observer vectors.

Outputs:

- shape `(n_view, n_wavelength)`;
- finite values;
- nonnegative spectral radiant intensity;
- no unrequested wavelength/direction reordering;
- immutable result arrays;
- quality flags for approximations/degraded validity.

Axisymmetric-provider physics invariant:

- rotation about the plume axis should not change the result for equal polar aspect.

Table-provider invariants:

- exact table grid points reproduce stored values;
- interpolation policy is deterministic;
- extrapolation policy is enforced.

## Spectral ray-transfer conformance

Test that:

- source radiance is finite and nonnegative;
- transmittance is finite and in `[0, 1]`;
- a ray that misses the plume returns:

```text
source_radiance = 0
transmittance = 1
```

- homogeneous segments compose correctly;
- maximum-distance bounds are respected;
- ray direction vectors are validated;
- axisymmetric symmetry is preserved;
- orthographic integration converges toward stable far-field intensity as sampling is refined.

## Shock-diamond provider regression tests

The wrapper must preserve existing solver behavior.

Tests should verify:

- provider zones match direct legacy solver results for benchmark cases;
- underexpanded and overexpanded cases remain unchanged;
- pressure equalization remains within current tolerances;
- existing public tests remain unmodified and pass;
- legacy `calculatePlumeZones` remains public;
- `calculatePlumeZonesFromExitState` reproduces the legacy path;
- invalid/placeholder geometry is not silently exposed;
- termination reason is `requested_construction_limit` until a physical cutoff exists.

## External-consumer source conformance

The external-consumer plugin/source adapter should validate:

- callable `evaluate(query)`;
- source/model identity;
- expected model version;
- query non-mutation;
- output shape and units semantics;
- finite/nonnegative intensity;
- exact source ID and provenance;
- no silent extrapolation.

## External-consumer physical point-source fixtures

### Constant source inverse-square test

Given constant `I_lambda` and unity transmission:

```text
R2 = 2 * R1
```

expected irradiance ratio:

\[
E_2/E_1 = 1/4
\]

### Spectral integration test

Use a simple known source and flat throughput/QE so the electron integral has a closed-form or direct numerical reference.

### Pose transform test

Known source rotation + known sensor position should produce the expected source-local view vector.

### Multi-sensor batching test

Two or more sensors observing one source at one epoch should cause one batched source evaluation, not repeated snapshot construction.

### Source swap test

Run the same observation pipeline with:

- constant fixture source;
- table source;
- Exhaust-Plume adapter source.

No sensor code should change.

## Point-source validity tests

If the provider exposes characteristic spatial extent, verify that insufficient range produces a typed rejection or route-to-resolved decision.

## GPU execution conformance

For a monotonic provider:

- decreasing time requests fail immediately;
- invalidated snapshots raise `SnapshotInvalidatedError`;
- session close prevents further evaluation;
- batch limits are enforced;
- preflight detects incompatible consumer scheduling.

## Provenance tests

Ensure a result provenance ID changes when any material source changes, including:

- provider version;
- configuration;
- source definition;
- table asset digest;
- optical-property model;
- interpolation policy;
- radiative-transfer model.
