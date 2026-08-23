# First visual MVP release boundary

This release is the first production-shaped vertical slice from the execution
handoff. It has one renderer-neutral product:
`plume.visual.sectioned-tube@1`.

The analytical path is explicitly bounded to a steady, straight, axisymmetric,
uniform-exit, calorically-perfect, inviscid near-field construction. It derives
the exit state from explicit gas/nozzle/ambient inputs, classifies the exit
pressure against ambient pressure, solves at most the configured first
construction cell, and adapts finite x/r geometry to oriented sectioned-tube
sections. Matched flow has no finite shock-cell endpoint, so the consumer must
request a positive axial display extent and receives a constant-radius tube
over that domain.

The prescribed and analytical providers share the same provider/session/
immutable-snapshot lifecycle, result DTO, sampling, channel validation,
applicability metadata, provenance, deterministic serialization, and visual-only
capability advertisement. A reusable conformance harness checks those common
invariants and confirms that signature and ray-transfer capabilities are not
served by the visual-only providers.

The physics fixtures generate cases from desired static exit-pressure ratios:
matched (`pe/pa = 1.00`), mild underexpanded (`1.20`), mild overexpanded
(`0.85`), and a strong overexpanded case beyond the attached low-order domain.
Legacy total-pressure examples remain regression-only anchors. For the
reference case `Me = 4.13`, `gamma = 1.33`, the matched total-to-ambient ratio
is approximately `220.45`; treating legacy 69-atm or 50-atm values as
stagnation pressures therefore produces overexpanded, not underexpanded,
states.

## Verification boundary

The release includes unit, contract, conformance, geometry, provider, regression,
CLI, schema, build, and installed-wheel checks. The claims are physically
informed but not externally validated: no CFD or experimental comparison is
included. Low-order construction truncation is reported as marginal, and
detached shocks, nozzle separation, complete mixing, chemistry, particles,
physical radiation, signature prediction, ray transfer/FPA raycasting,
rareified/atomistic flow, and CPU/GPU acceleration remain out of scope.

The legacy public solver and CLI remain available. New consumers should use the
explicit gas, nozzle, ambient, state-based first-cell boundary and the versioned
visual product rather than infer physical meaning from legacy pressure labels.
