# Canonical Architecture

## Product lifecycle

```text
provider-specific definition + configuration
                    |
                    v
              PlumeProvider
                    |
              create_session
                    v
              PlumeSession
                    |
                 snapshot
                    v
          immutable PlumeSnapshot
          /          |           \
         v           v            v
 sectioned tube   signature    ray transfer
```

There is no universal result object.

## Canonical authority

### Public v1 product and transport authority

```text
src/exhaust_plume/api/
```

This owns:

- capability identities;
- strict immutable Pydantic DTOs;
- provider/session/snapshot protocols;
- structured API errors;
- result envelopes and deterministic hashes;
- canonical downward adapters;
- generated JSON schemas.

### Computational state

```text
src/exhaust_plume/models/
```

This owns gas, nozzle, shock-cell, straight-integral, curved-integral, thermodynamic, geometry, and numerical state. Computational classes do not cross the transport boundary.

### Compatibility/workflow surface

```text
src/exhaust_plume/contracts/
src/exhaust_plume/products/
src/exhaust_plume/providers/
```

During `0.1.0a2`, these remain supported but are explicitly classified:

- retained provider implementations may live under `providers`;
- legacy product DTOs and workflows are compatibility facades;
- new schema semantics are added only to `api`;
- every retained compatibility result has a tested adapter to/from the canonical DTO where semantically possible.

## Neutral physical handoff

Only a conservative flux section crosses physical-regime providers:

\[
\dot m,
\quad
\boldsymbol{\Pi}=\int_A \rho u_n\mathbf u\,dA + \int_A(p-p_a)\mathbf n\,dA,
\quad
\dot H_0,
\quad
\dot m_k.
\]

Use one public name: `PlumeFluxSection`.

To eliminate current ambiguity:

- public/transport DTO: `exhaust_plume.api.PlumeFluxSection`;
- internal computational state: rename to `FluxSectionState` or `IntegralFluxSectionState`;
- preserve `exhaust_plume.contracts.handoff.PlumeFluxSection` as a deprecated alias/adapter through the alpha migration window.

## Provider composition

```text
NozzleExitState
    |
    +--> ShockCellAnalyticalProvider -- downstream PlumeFluxSection --+
    |                                                               |
    +---------------------------------------------------------------+
                                                                    v
                                                   StraightIntegralPlumeProvider
                                                                    or
                                                    WashedIntegralPlumeProvider
                                                                    |
                                            +-----------------------+----------------+
                                            |                                        |
                                      visual adapter                          optical field
                                            |                                        |
                              sectioned-tube product                       ray transfer
                                                                                   |
                                                                         unresolved signature
```

## Allowed derivations

```text
validated local field -> visual support
validated local optical field -> ray transfer
ray transfer -> spectral image
ray transfer -> unresolved intensity
curved integral state -> conservative flux sections
```

## Prohibited inference

```text
visual geometry -X-> spectral radiance
visual geometry -X-> signature
signature table -X-> geometry
projected area -X-> ray transfer
steady result -X-> transient coherence
```

## W1 washed model boundary

- steady;
- pressure matched;
- non-Boussinesq ideal gas;
- circular top-hat section;
- mass, vector momentum, total energy, and exhaust tracer conservation;
- one-way ambient coupling;
- hover actuator disk with optional torque-derived swirl;
- rotation-minimizing frames;
- visual product only until optical gates pass.
