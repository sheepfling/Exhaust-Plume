# Executive Summary

## Current state

`v0.1.0a1` is not an empty foundation. The release already contains:

- explicit gas, nozzle, throat, ambient, and shock-validity contracts;
- shock-cell analytical and straight visual providers;
- a straight conservative integral continuation kernel;
- a curved/washed conservative kernel with actuator-disk wash, swirl, buoyancy, entrainment, and swept geometry;
- provider/session/snapshot contracts;
- visual, signature, ray-transfer, support, and flux DTOs;
- prescribed visual and table-backed signature products;
- visual/signature/validity CLI workflows.

The release does **not** yet contain a canonical straight-integral provider, a canonical washed-integral provider, a loopback sidecar, a true downstream shock-to-mixing handoff, or physical ray-transfer/radiation.

## Main architectural defect

Two overlapping public hierarchies coexist:

```text
exhaust_plume.api
```

and

```text
exhaust_plume.contracts + exhaust_plume.products + exhaust_plume.providers
```

The supplied decisions select `exhaust_plume.api` as the canonical strict product boundary. The first substantive post-release task is therefore API consolidation—not another solver rewrite.

## Release strategy

### `0.1.0a2` — live washed visual MVP

Ship:

1. exact-main baseline and CI evidence;
2. one canonical API authority plus compatibility adapters;
3. `StraightIntegralPlumeProvider`;
4. one consolidated entrainment implementation and W1 defaults;
5. `WashedIntegralPlumeProvider`;
6. consumer swap from prescribed to live washed physics;
7. loopback sidecar over the canonical schemas.

Do not claim physical signature or ray transfer.

### `0.1.0a3` — regime composition and gray optical MVP

Ship:

- true downstream shock-to-mixing handoff;
- composite provider;
- curved ray intervals;
- verified homogeneous gray transfer;
- optional ray-derived unresolved intensity consistency.

### Later

Calibrate free-jet/crossflow/rotor physics, then add ellipses, walls, plume merger, imported fields, molecular radiation, chemistry, particles, transient flow, and GPU execution.

## First action

Execute `A1-000` from `main@49d6ffd1839258ce14319e157002005c6d2230e1`.
