# Implementation Roadmap

## Tranche / PR 1 — Provider contract foundation

Add to Exhaust-Plume:

```text
src/exhaust_plume/contracts/
    capability.py
    descriptor.py
    errors.py
    execution.py
    provenance.py
    snapshot.py

src/exhaust_plume/providers/
    __init__.py
```

Acceptance criteria:

- Python 3.10 compatible with current package constraints;
- no new required dependency;
- typed provider/session/snapshot lifecycle;
- explicit capability IDs and major versions;
- execution profile separated from fidelity;
- shared fake-provider conformance tests;
- existing public API unchanged.

## Tranche / PR 2 — Exit-state solver boundary

Refactor:

```text
calculatePlumeZones(...)
    -> calcNozzleExitFlowState(...)
    -> calculatePlumeZonesFromExitState(...)
```

Acceptance criteria:

- old API delegates to the new function;
- benchmark numerical results remain equivalent;
- no duplicated plume-construction code;
- current `num_plumes` remains supported;
- new provider API uses `maximum_construction_passes` terminology.

## Tranche / PR 3 — Shock-diamond provider

Add:

```text
src/exhaust_plume/providers/shock_diamond.py
```

Initial capabilities:

```text
axisymmetric-zone-field
spatial-support
projected-area
```

Acceptance criteria:

- explicit provider validity domain;
- structured termination report;
- neutral axial/radial zone conversion;
- no unsupported radiometric claims;
- provider/direct-solver regression equivalence;
- invalid geometry never leaks into spatial capabilities.

## Tranche / PR 4 — External-consumer source port

Add to the external-consumer integration layer:

```text
src/consumer_adapter/contracts/radiometry.py
src/consumer_adapter/source/protocol.py
src/consumer_adapter/source/conformance.py
src/consumer_adapter/source/constant.py
src/consumer_adapter/factories/radiometric_source.py
src/consumer_adapter/sensor/point_source_radiometry.py
```

Keep current Alpha-2 proxy behavior intact. Add a new physical-source path/schema rather than silently changing existing semantics.

Acceptance criteria:

- constant source inverse-square test passes;
- source pose is explicit;
- plugin source cannot mutate its query;
- invalid plugin results are rejected;
- one source call can batch multiple observers;
- final detection record remains downstream.

## Tranche / PR 5 — Signature-table provider/source

Implement a neutral table source/provider.

Acceptance criteria:

- exact grid points reproduce stored values;
- interpolation is explicitly configured;
- extrapolation defaults to reject;
- asset SHA-256 is part of provenance;
- table source can replace constant source with no sensor-code changes.

## Tranche / PR 6 — Axisymmetric ray-transfer infrastructure

Add:

```text
src/exhaust_plume/radiometry/
    optical_properties.py
    axisymmetric_ray_transfer.py
    far_field_from_rays.py
```

Acceptance criteria:

- empty-ray identity;
- homogeneous-segment analytical tests;
- axisymmetric rotational-symmetry tests;
- ray-grid convergence test;
- same snapshot can produce both resolved and far-field products.

## Tranche / PR 7 — Software-fixture optical model

Add a clearly labeled approximate optical-property model for interface validation only.

Acceptance criteria:

- no claim of validated exhaust spectroscopy;
- deterministic results;
- configurable opacity/source function;
- end-to-end plume -> ray -> far-field -> consumer-adapter test.

## Tranche / PR 8 — Physically grounded spectral model

Research/choose:

- species representation;
- LTE versus non-LTE assumptions;
- spectroscopic database;
- line-by-line versus band model;
- pressure/temperature broadening treatment;
- validated comparison cases;
- soot/particles if relevant.

Then implement as a separate optical-property/radiation layer.

## Tranche / PR 9 — Rotor-washed provider

Add `AmbientFlowField` dependency and curved centerline/tube geometry without changing the consumer source interface.

Acceptance criteria:

- straight and curved providers share consumer interfaces;
- spatially varying flow field remains provider-specific input;
- source/ray outputs continue to use plume-local coordinates.

## Tranche / PR 10 — GPU provider

Implement transient/GPU provider with explicit execution semantics.

Acceptance criteria:

- monotonic-time constraints declared and preflighted;
- snapshot retention declared;
- batch queries supported;
- host semantic result compatibility maintained;
- device-native optimization can be added without changing physical interfaces.

## Stable decisions for coding agents

1. Generic outputs; provider-specific strongly typed inputs.
2. The external consumer owns the generic radiometric source port.
3. Exhaust-Plume integrates through adapters and has no consumer-package dependency.
4. Source pose is independent of source emission.
5. Plume-local origin is nozzle-exit center; +X is downstream.
6. Far-field source product is spectral radiant intensity.
7. Resolved transfer product is plume-emitted radiance plus transmittance.
8. Capability, fidelity, and execution behavior are separate descriptors.
9. Current shock-diamond provider begins as geometry/thermodynamics only.
10. Existing APIs remain backward-compatible during migration.
11. Interpolation/extrapolation policies are explicit and provenance-bearing.
12. No silent domain extrapolation.
