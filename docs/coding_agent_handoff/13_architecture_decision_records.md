# Architecture Decision Records

## 1. Purpose

This document records decisions that the coding agent shall treat as settled
unless a new ADR explicitly supersedes them. The intent is to prevent each
implementation phase from reopening the same model-boundary, API, units, and
validation questions.

Each record contains:

```text
status
context
decision
consequences
revisit trigger
```

The default status is `ACCEPTED`.

## ADR-001 — Separate source physics from observation physics

**Status:** ACCEPTED

### Context

The current package constructs flow zones and projected areas in one focused
plume package. Future consumers may need local flow fields, geometry, spectral
radiance images, unresolved far-field signatures, or only a precomputed
signature table.

### Decision

Use the staged pipeline:

```text
nozzle/exit state
  -> shock-cell source model
  -> downstream mixing field
  -> radiative-transfer source signature
  -> atmosphere/path model
  -> sensor model
```

The output of one stage is an explicit immutable contract consumed by the next.
Atmospheric propagation and detector response shall not be embedded in the
intrinsic plume-source solver.

### Consequences

- Flow verification is possible without radiation.
- Radiation verification is possible with analytic fields.
- A provider may supply a precomputed signature without exposing a flow field.
- Source radiant intensity remains reusable for many ranges and sensors.

### Revisit trigger

Only if a validated coupled radiation-hydrodynamics model demonstrates that
one-way stage coupling is insufficient for the intended operating regime.

## ADR-002 — Validate planar gas dynamics before axisymmetric CFD

**Status:** ACCEPTED

### Context

The branch currently uses planar characteristic geometry and revolves it for
visualization. Revolving a planar result does not introduce the cylindrical
source terms of an axisymmetric flow solution.

### Decision

The first corrected near-field solver shall be labeled and validated as a
**planar reduced-order shock-cell model**. Axisymmetric revolution may be used
to create a first radiation volume, but the result metadata shall state that
the gas dynamics are planar-derived.

A true axisymmetric Euler/RANS/LES continuation is a separate provider and a
later design phase.

### Consequences

- The current code can be improved incrementally.
- Model claims remain honest.
- Planar and axisymmetric providers can be compared through the same public
  provider interface.

### Revisit trigger

When Phase 7 begins or when validation shows that planar error exceeds the
allocated model-form uncertainty for the intended use.

## ADR-003 — Shock-cell count is an output

**Status:** ACCEPTED

### Context

`num_plumes` currently determines how many repeated construction passes are
created. A physical plume contains one shock-cell train whose coherent cell
count depends on pressure mismatch, mixing, coflow, and topology.

### Decision

Rename the safety control to `max_cells`. The solver computes:

```text
cells_completed
shock_train_end_x_m
termination_reason
was_domain_truncated
```

A requested fixed cell count may exist only as an explicit diagnostic mode
named `FORCED_CELL_COUNT`, never as the default physical behavior.

### Consequences

- Physical and numerical termination are distinguishable.
- Sensitivity to mixing and pressure-decay closures becomes testable.
- Existing callers require a compatibility alias for one deprecation cycle.

### Revisit trigger

None. This is a semantic correction rather than a fidelity choice.

## ADR-004 — Gas properties and composition are explicit

**Status:** ACCEPTED

### Context

The active exit-state calculation and one engine-density path use dry-air
molecular weight even when another gas is requested.

### Decision

Every state capable of producing density, speed of sound, velocity, mass flux,
or opacity shall carry an explicit gas model. At minimum:

```text
gamma
specific_gas_constant_JpkgK
molecular_weight_kgpmol
species_mass_fractions
```

No rocket-exhaust path may import a dry-air constant implicitly.

### Consequences

- Gas-state and radiation calculations share a consistent number density.
- Ambient air remains an explicit gas composition rather than a hidden default.
- Existing convenience constructors may offer `GasProperties.dry_air()` only
  when callers deliberately select it.

### Revisit trigger

When the calorically perfect model is superseded by thermally perfect or
finite-rate thermochemistry; the explicit gas contract remains.

## ADR-005 — SI units and radians are canonical internally

**Status:** ACCEPTED

### Decision

All public numerical state contracts use SI units. All internal angles are
radians. Degree-valued compatibility properties and CLI inputs may exist, but
must include `_deg` in their names and convert at the boundary.

### Consequences

- Trigonometric units errors become less likely.
- Source code and serialized schemas are unambiguous.
- Existing degree-valued public objects require compatibility wrappers.

### Revisit trigger

None.

## ADR-006 — Invalid input raises; physical non-solutions return status

**Status:** ACCEPTED

### Context

The existing solver sometimes logs a numerical failure and returns a nominal
state. Callers cannot reliably distinguish a valid result from a failed solve.

### Decision

Use the following split:

- Invalid scalar data, inconsistent dimensions, or violated construction
  invariants raise `ValueError` or Pydantic validation errors before solving.
- A valid physical request outside a provider's capability returns a structured
  status such as `DETACHED_SHOCK_REQUIRED`, `MACH_DISK_REQUIRED`, or
  `NOZZLE_SEPARATION_NOT_MODELED`.
- Unexpected numerical failure returns `NUMERICAL_FAILURE` with residuals and
  iteration diagnostics; it never masquerades as success.

### Consequences

- Batch studies can continue across out-of-scope physical cases.
- Programming errors remain loud.
- Tests can assert exact failure semantics.

### Revisit trigger

If a higher-level orchestration layer standardizes a different result/error
contract across all providers.

## ADR-007 — State transitions and closed geometry are separate types

**Status:** ACCEPTED

### Context

Some current `ZoneResult` values carry `NaN` placeholder polygons because a
flow transition is known before a region has been geometrically closed.

### Decision

Represent these concepts separately:

```text
FlowTransition
CharacteristicSegment
ShockSegment
ClosedZone
```

Only `ClosedZone` may be meshed, revolved, projected, or ray traced. Public
closed zones contain finite, ordered, non-self-intersecting polygons.

### Consequences

- Radiation cannot accidentally ingest placeholder geometry.
- The MOC network can exist independently of a chosen zone tessellation.
- Compatibility `ZoneResult` may temporarily expose `coordinates | None`.

### Revisit trigger

None.

## ADR-008 — Use bracketed numerical methods for scalar roots

**Status:** ACCEPTED

### Context

The model contains bounded scalar inversions: area-Mach, inverse
Prandtl-Meyer, weak/strong oblique-shock angle, pressure equalization, and
enthalpy inversion.

### Decision

Use `scipy.optimize.root_scalar` with a documented bracket and the Brent method
for one-dimensional roots. Use bounded scalar minimization when locating
maximum attached turn. Do not use unconstrained Newton iteration as the only
path for physically bounded scalar problems.

Every root result records:

```text
bracket
iterations
function_calls
residual
converged
```

### Consequences

- Failure is reproducible and bounded.
- Branch selection is explicit.
- SciPy becomes a base numerical dependency after Phase 0.

### Revisit trigger

If dependency constraints forbid SciPy, in which case an equivalent in-package
Brent implementation requires its own verification plan.

## ADR-009 — Canonical internal spectral coordinate is wavenumber per meter

**Status:** ACCEPTED

### Context

Spectroscopy databases conventionally use wavenumber in inverse centimeters,
while sensor bands are often described in wavelength. Implicit mixing of
spectral-density coordinates produces Jacobian errors.

### Decision

The canonical internal radiation grid is:

```text
spectral_coordinate = WAVENUMBER_PER_M
```

HITRAN/HITEMP adapters convert from inverse centimeters at ingestion. Sensor
and display adapters may expose wavelength in meters or micrometers. Every
spectral-density conversion applies and tests the Jacobian:

\[
I_\lambda\,d\lambda=I_{\tilde\nu}\,d\tilde\nu,
\qquad
\tilde\nu=\frac{1}{\lambda}.
\]

### Consequences

- Spectroscopic tables have one canonical coordinate.
- Public results retain coordinate and density-unit metadata.
- Wavelength conversion is never a simple relabeling of the horizontal axis.

### Revisit trigger

Only if an upstream/downstream ecosystem requires a different canonical
coordinate; conversion requirements remain.

## ADR-010 — Optional high-fidelity dependencies stay out of the base install

**Status:** ACCEPTED

### Decision

The base package may require:

```text
numpy
scipy
pydantic >= 2
pyyaml
```

Optional extras contain:

```text
plot       -> matplotlib
spectra    -> hapi tooling or project cross-section generator dependencies
chemistry  -> cantera
```

CEA is treated initially as an external/offline boundary-state generator.

### Consequences

- Gas-dynamics users do not install chemistry or spectroscopy stacks.
- Optional-provider imports must fail with actionable messages.
- Cross-section products and CEA outputs are versioned data artifacts.

### Revisit trigger

When packaging or licensing constraints require a separate distribution.

## ADR-011 — Preserve the alpha API through an explicit compatibility layer

**Status:** ACCEPTED

### Context

Version `0.1.0.a0` exports `EngineParameters`, flow-state types,
`calcNozzleExitFlowState`, and `calculatePlumeZones` from the package root.

### Decision

Introduce the new request/result API without silently changing old return
types. Existing root imports remain wrappers during the documented alpha
migration window. Deprecated arguments emit `DeprecationWarning` with a clear
replacement.

Do not preserve mathematically incorrect behavior merely for compatibility.
Corrected values are documented as intentional numerical changes.

### Consequences

- Existing exploratory scripts continue to run long enough to migrate.
- New code uses explicit immutable request/result objects.
- A compatibility removal milestone is planned rather than indefinite.

### Revisit trigger

At the first stable `1.0` API review.

## ADR-012 — Calibration is a versioned model artifact

**Status:** ACCEPTED

### Decision

Every empirical closure set carries:

```text
calibration_id
parameter_values
parameter_covariance or intervals
source_datasets
excluded_datasets
objective_definition
applicability_bounds
software_commit
created_at
```

A result using default placeholder coefficients must be labeled
`UNCALIBRATED`.

### Consequences

- Reproducibility and uncertainty propagation are possible.
- Calibration and validation cases can be kept disjoint.
- Constants do not enter code without provenance.

### Revisit trigger

None.

## ADR-013 — Providers advertise capabilities instead of implementing stubs

**Status:** ACCEPTED

### Context

Future providers include the reduced-order straight shock-cell plume, curved
or rotor-washed plumes, imported CFD, GPU solvers, and precomputed spectral
signature tables. Not all can expose the same intermediate products.

### Decision

Use capability negotiation. A provider declares support for products such as:

```text
LOCAL_FLOW_STATE
GEOMETRY
RADIANCE_IMAGE
SPECTRAL_RADIANT_INTENSITY
BAND_SIGNATURE
TIME_DEPENDENCE
NON_AXISYMMETRIC_FIELD
UNCERTAINTY
```

Unsupported capabilities are absent, not implemented as plausible-looking
empty or zero results.

### Consequences

- Low- and high-fidelity providers share one orchestration interface.
- Consumers request only the products they require.
- A signature-only provider remains valid.

### Revisit trigger

If capability combinations become complex enough to justify separate service
interfaces; the semantic products remain unchanged.

## ADR-014 — Verification precedes validation

**Status:** ACCEPTED

### Decision

Every phase follows:

```text
units/input verification
  -> algebraic verification
  -> conservation verification
  -> numerical convergence verification
  -> experimental or high-fidelity validation
  -> uncertainty characterization
```

Experimental agreement cannot waive failed conservation or convergence tests.

### Consequences

- Model-form error is separated from implementation error.
- Regression fixtures carry evidence level metadata.
- Phase gates remain objective.

### Revisit trigger

None.
