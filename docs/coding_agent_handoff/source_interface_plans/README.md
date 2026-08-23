# Rocket Exhaust Plume Interface Plans

This package consolidates the interface and architecture plans developed for swappable exhaust-plume providers, including low-fidelity analytical shock-diamond models, rotor-washed/curved plumes, tabulated signatures, and future GPU/volumetric solvers.

## Documents

1. `01_architecture_overview.md` — overall architecture and stable design principles.
2. `02_provider_contracts.md` — provider/session/snapshot lifecycle, capabilities, fidelity, execution semantics, and typed provider-specific inputs.
3. `03_radiometry_and_external_consumers.md` — unresolved spectral source contract, resolved ray transfer, source pose, and sensor pipeline.
4. `04_shock_diamond_provider.md` — how the current analytical solver should be wrapped without overclaiming fidelity.
5. `05_signature_tables_and_gpu.md` — precomputed tables, interpolation/provenance, GPU lifecycle, transient constraints, and future renderer interfaces.
6. `06_conformance_and_testing.md` — shared contract tests, invariants, error semantics, and integration tests.
7. `07_implementation_roadmap.md` — coding-agent PR/tranche sequence and acceptance criteria.
8. `08_python_interface_sketches.py` — consolidated typed Python sketches for the proposed interfaces.

## Core decisions

- Generic outputs, provider-specific strongly typed inputs.
- Capability and fidelity are separate concepts.
- Execution constraints are separate from both capability and fidelity.
- External consumers consume a generic radiometric source, not plume geometry or plume internals.
- Far-field unresolved output is spectral radiant intensity, `I_lambda` in W/(sr m).
- Resolved output is emitted/source spectral radiance plus plume transmittance.
- Plume-local coordinates use nozzle-exit center as origin and +X downstream.
- The current shock-diamond solver should initially expose geometry/flow capabilities only.
- Spectroscopy/radiative transfer is attached as a separate capability layer.
- Existing APIs should remain backward-compatible while new provider-oriented entry points are added.
