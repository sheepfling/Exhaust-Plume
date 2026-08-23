# Generic interface contracts v1

This repository exposes three separate consumer products behind one provider,
session, and immutable-snapshot lifecycle. The product contracts are
transport-neutral and use SI quantities with explicit coordinate-frame IDs.

## Product identities

| Capability | Product | Primary output |
| --- | --- | --- |
| `plume.visual.sectioned-tube@1` | visual sectioned-tube geometry | oriented sections, radii, optional feature channels, and visual bounds |
| `plume.signature.spectral-radiant-intensity@1` | unresolved spectral intensity | `J_lambda` in `W sr^-1 m^-1` over directions and wavelengths |
| `plume.optical.spectral-ray-transfer@1` | resolved spectral ray transfer | source radiance and background transmittance over rays and wavelengths |

These are independent products. A result never combines them into one nullable
omnibus response, and support for one product does not imply support for either
of the others.

## Lifecycle

```text
provider definition + configuration
              |
              v
           provider
              |
              v
           session
              |
              v
       immutable snapshot
              |
              v
       capability evaluation
```

Provider construction is provider-specific. A session owns reusable setup. A
snapshot fixes source state, ambient state, provider state, and time. Results
reference the snapshot metadata and include request/configuration digests,
claims, applicability, provenance, and warnings.

## Contract rules

- Public arrays have fixed semantic shapes and are validated before evaluation.
- Directions are finite unit vectors; wavelengths are positive and strictly
  increasing; ray intervals satisfy `0 <= t_min < t_max`.
- Visual arc lengths are strictly increasing, section quaternions are unit
  length, and feature channels have one value per section.
- A valid ray miss is distinct from a failed ray: a miss has zero source
  radiance, unit transmittance, and a true validity row.
- Partial batches are opt-in. Failed samples use neutral placeholders plus an
  explicit non-OK status and all-false validity row.
- Visual geometry claims never imply radiometric correctness or conservative
  engineering support.
- Spectral v1 is wavelength-resolved; detector bands, atmosphere, optics,
  exposure, noise, and digitization remain downstream concerns.
- Provider-private zones, meshes, grids, buffers, and solver structures do not
  cross the public boundary.

## Current implementation boundary

The common DTOs, schemas, fixtures, lifecycle dispatcher, deterministic
prescribed visual provider, straight parametric visual provider, first
straight analytical visual provider, neutral table-backed spectral lookup
provider, and local MVP workflows are implemented. The visual workflow can
mesh/export straight sectioned-tube results and adapt the current simple
straight solver envelope. The analytical provider uses the named
`solve_first_cell_from_exit_state` boundary and the same immutable snapshot
contract as the prescribed provider. The signature workflow can load
canonical JSON assets, evaluate requests, export long-form CSV, and render
basic spectral/angular views. The older straight analytical plume provider
remains available through its compatibility contract.

## MVP boundary

The two MVP commands are intentionally local and reproducible:

- `exhaust-plume-visualize` consumes a straight visual JSON asset and emits
  result JSON, triangle-mesh JSON, OBJ, and an optional PNG preview.
- `exhaust-plume-signature` consumes a signature table asset plus a request and
  emits result JSON, long-form CSV, and optional spectrum/angular/heatmap PNGs.
- `StraightAnalyticalPlumeProviderV0` consumes explicit nozzle-exit and ambient
  states and emits only visual sectioned-tube geometry. It supports matched,
  mild underexpanded, and mild attached-overexpanded first-cell cases, with
  structured refusal for strong/detached or numerically failed cases.

The signature asset is an unresolved, axisymmetric direction-cosine lookup. It
does not provide a physical spectroscopy model. The visual mesh is a display
representation of sectioned geometry; it does not make a conservative or
radiometrically valid claim by itself. Both products retain frame IDs,
applicability, claims, uncertainty where supplied, and provenance in their
public results.

The table-backed signature provider uses the `tabulated` radiation claim and
may bind requests to an explicit operating-point identifier. Asset-declared
linear, log-linear, nearest, and exact-only policies are explicit per supported
axis; `log-linear` requires positive bracketing values and extrapolation rejects
by default. Optional source and ambient pressure
metadata are retained as operating-point coverage metadata and are not treated
as a solved pressure axis. Result provenance includes the loaded file SHA-256,
coordinate convention, interpolation policies, extrapolation policy, and
lookup validity domains.

Static tables are valid for arbitrary snapshot times. Time-sliced tables use
the declared time policy and require the `prescribed_transient` time claim;
time, angle, wavelength, and operating-point mismatches are explicit typed
applicability errors.

The active nozzle path has a separate `NozzleGeometry` contract for circular
equivalent-area throat and exit sections. It derives the supersonic exit Mach
from `A_e/A*` and checks the choked-throat mass-flow invariant. The
`StudyValidityEnvelope` and its matrix report expose the supported finite study
range and distinguish input applicability from low-order solver failure or
construction truncation.

No physical spectral/radiation provider or resolved ray-transfer provider is
claimed by this tranche. CPU/GPU acceleration, curved or rotor-washed
providers, advanced radiation, FPA raycasting, thermochemistry, finite-rate
chemistry, and detached-shock or nozzle-separation topology remain outside the
implementation scope.
