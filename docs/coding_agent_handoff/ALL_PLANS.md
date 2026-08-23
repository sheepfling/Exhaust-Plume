# Exhaust-Plume Coding-Agent Handoff — Version 4

This combined edition concatenates the authoritative numbered planning documents.
The repository-ready directory also contains machine-readable registries, prompts,
source interface plans, checksums, and the handoff manifest.



---

<!-- BEGIN 00_unified_plume_architecture.md -->

# Unified Plume Architecture: Provider, Products, and Consumer Views

## 1. Purpose

This document is the authoritative architecture seam for all plume models in
Exhaust-Plume. It reconciles the physics roadmap with the swappable-provider
interface plans.

The central rule is:

> A plume provider is defined by what products it can provide, not by whether
> it is "low fidelity", "high fidelity", "straight", or "curved".

There are two primary consumer use cases:

1. **Signature use** — the consumer needs an intrinsic unresolved spectral
   source as a function of time and observer direction. The provider may use
   geometry internally, but geometry need not be exposed.
2. **Spatial/physical use** — the consumer needs geometry, local fields,
   optical-medium state, ray transfer, or other spatially resolved products.

The same provider may serve either or both use cases.

## 2. Orthogonal dimensions

Do not encode these dimensions into one inheritance hierarchy.

### 2.1 Consumer product level

```text
SIGNATURE
  directional spectral radiant intensity
  optional band-integrated intensity

SPATIAL
  support/bounds
  geometry/zones
  local thermodynamic/species fields
  optical medium
  resolved spectral ray transfer
  optional scene radiance
```

### 2.2 Plume morphology

```text
STRAIGHT
CURVED
ROTOR_WASHED
CROSSFLOW_DEFLECTED
MULTI_ENGINE_INTERACTING
GENERAL_3D
```

Morphology describes plume structure; it does not determine fidelity.

### 2.3 Physics fidelity

Examples:

```text
signature table
empirical band model
reduced-order shock-cell model
integral mixing plume
planar analytical field
axisymmetric CFD surrogate
RANS/LES snapshot
coupled CFD + radiation
```

Fidelity is metadata and applicability information, not an API tier.

### 2.4 Radiation fidelity

Examples:

```text
none
gray LTE
band model
correlated-k
line-by-line LTE
non-LTE
particles/scattering
```

### 2.5 Execution behavior

Examples:

```text
random-access CPU
monotonic transient GPU
serialized external service
reentrant table lookup
checkpointed CFD sequence
```

Execution constraints are not physics capabilities.

## 3. Provider lifecycle

The stable lifecycle is:

```text
PlumeProvider[DefinitionT, ConfigurationT, OperatingStateT]
    |
    +-- create_session(definition, configuration)
            |
            v
        PlumeSession
            |
            +-- snapshot(operating_state)
                    |
                    v
                PlumeSnapshot
                    |
                    +-- capability registry
```

Provider inputs remain strongly typed and provider-specific. A curved
rotor-washed provider is allowed to require a spatial ambient-flow service;
a signature-table provider is not required to fabricate a nozzle exit state.

## 4. Product lattice, not product hierarchy

Products form a partial order because some products can be derived from richer
ones, but not vice versa.

```text
local flow / optical medium
           |
           v
resolved spectral ray transfer
           |
           v
spectral radiance image
           |
           v
unresolved directional spectral radiant intensity
```

A provider may implement any product directly.

For example:

- a CFD+radiation provider can derive all downstream products;
- a CFD-derived lookup table may expose only directional intensity;
- a shock-cell provider may expose geometry/flow first, then gain a separate
  radiation adapter later;
- a tabulated signature provider can expose directional intensity without any
  spatial capability.

No consumer may assume that a provider exposing directional intensity also
exposes geometry.

## 5. Two consumer profiles

### 5.1 Signature consumer

Minimal request:

```text
time / snapshot
wavelength grid
source-to-observer unit directions in plume frame
```

Minimal intrinsic result:

\[
J_\lambda(t,\hat{\mathbf s})
\quad [\mathrm{W\,sr^{-1}\,m^{-1}}].
\]

This excludes range, atmosphere, optics, and detector response.

A signature consumer should depend on a very small `DirectionalSpectralSource`
port, not on `PlumeSnapshot` internals.

### 5.2 Spatial/physical consumer

Possible requests include:

```text
conservative spatial support
zone/mesh geometry
local flow state q(t,x)
thermochemical state
particle state
optical coefficients
spectral ray transfer
resolved radiance image
```

A renderer, focal-plane simulator, engineering diagnostic, or coupling model
uses these optional capabilities.

## 6. Geometry visibility rule

Geometry has three statuses:

```text
INTERNAL_ONLY
EXPOSED_APPROXIMATE
EXPOSED_VALIDATED
```

A provider may require detailed geometry internally to compute a signature but
advertise no geometry capability. This is normal and encouraged when the
geometry is an implementation detail or not valid as an interchange product.

The current shock-diamond solver initially has `EXPOSED_APPROXIMATE` geometry
only after invalid/placeholder polygons are removed or rejected.

## 7. Common plume-local frame

Every physical plume instance that exposes spatial or directional products uses
a right-handed plume-local frame:

```text
origin: nozzle exit center or provider-declared source reference
+X: nominal downstream direction at the source
+Y,+Z: complete the right-handed frame
```

For curved plumes, +X is the source/nozzle reference direction, not the local
tangent everywhere downstream.

The direction passed to an unresolved source is always:

```text
source_to_observer_direction_plume
```

and is a finite unit vector.

## 8. Curved plume representation

A curved plume is not a different consumer interface. Its spatial model adds a
centerline and local transported frame.

Let centerline arc length be \(s\), with

\[
\mathbf c(s),\qquad
\mathbf t(s)=\frac{d\mathbf c}{ds}.
\]

A tube-like reduced-order plume may define cross-section radius \(R(s)\) and
cross-sectional fields in a local frame \((\mathbf t,\mathbf n,\mathbf b)\).

The centerline evolves under a provider-specific momentum/environment model,
for example

\[
\frac{d}{ds}(\dot m\,\mathbf u)
=
\mathbf f_{\mathrm{entrainment}}
+\mathbf f_{\mathrm{crossflow}}
+\mathbf f_{\mathrm{buoyancy}}
+\cdots.
\]

Those equations belong to the curved provider. Consumers continue to request
standard spatial or radiometric capabilities.

## 9. Capability IDs

Core capability IDs and major versions should begin with:

```text
spatial-support                 v1
axisymmetric-zone-field         v1
centerline-tube-field           v1
local-flow-state                v1
projected-area                  v1
directional-spectral-intensity  v1
spectral-ray-transfer           v1
optical-medium                  v1
scene-radiance-renderer         v1
uncertainty                     v1
```

A capability version changes only when that capability's semantic contract is
broken. Provider package versions are separate.

## 10. Provider descriptor

The descriptor must keep capability, fidelity, morphology, and execution
separate:

```text
provider_id
provider_version
core_contract_major_version
capability_versions
input_schema_ids

morphology:
  straight | curved | rotor-washed | crossflow | general-3d

fidelity:
  geometry_model
  spatial_dimensionality
  temporal_model
  flow_model
  mixing_model
  thermochemistry_model
  radiation_model
  environmental_coupling
  validation_level

execution:
  time_access
  concurrency
  deterministic
  direction_batching
  checkpointability
  preferred_device
  snapshot_retention
```

There is deliberately no single `LOW/MEDIUM/HIGH` field with semantic meaning.

## 11. Recommended provider families

### ShockCellAnalyticalProvider

Morphology: straight, nominally axisymmetric-looking spatial output from a
planar analytical construction.

Initial capabilities:

```text
spatial-support
axisymmetric-zone-field
projected-area
```

Later adapters may add:

```text
optical-medium
spectral-ray-transfer
directional-spectral-intensity
```

### IntegralStraightPlumeProvider

Morphology: straight.

Capabilities:

```text
spatial-support
local-flow-state
centerline-tube-field
```

May be chained after a shock-cell provider.

### CurvedIntegralPlumeProvider

Morphology: curved/crossflow/rotor-washed.

Provider-specific input includes an ambient spatial flow service.

Capabilities are the same standard spatial capabilities; curvature does not
change consumer APIs.

### SignatureTableProvider

Morphology may be metadata only.

Capabilities:

```text
directional-spectral-intensity
```

No geometry is required.

### ImportedFieldProvider

Wraps CFD/RANS/LES fields.

Capabilities may include local state, optical medium, ray transfer, or derived
signatures depending on the imported asset.

### GpuTransientPlumeProvider

May implement general 3-D fields and radiation with monotonic-time execution
and short-lived snapshots. Semantics remain compatible with the same
capabilities.

## 12. Adapters are first-class

Adapters convert richer products into simpler products without modifying the
underlying provider.

Examples:

```text
AxisymmetricZoneField
  + OpticalPropertyModel
    -> SpectralRayTransfer

SpectralRayTransfer
  -> orthographic integration
    -> DirectionalSpectralIntensity

LocalFlowState
  + Chemistry/Radiation model
    -> OpticalMedium

Legacy calculatePlumeZones(...)
  -> ShockCellAnalyticalProvider snapshot
```

This prevents radiative physics from being hard-coded into the wave solver.

## 13. External-consumer integration boundary

An unresolved tracking/sensor application should own a source port equivalent
to:

```text
evaluate(epoch, wavelength_grid, source_local_directions)
  -> spectral radiant intensity
```

Exhaust-Plume supplies an adapter implementing that port. Exhaust-Plume does
not depend on a particular consumer package.

Observation propagation then applies:

\[
E_\lambda
=
\frac{\tau_\lambda J_\lambda}{R^2},
\]

followed by optics, quantum efficiency, noise, and detection logic.

## 14. Non-negotiable architecture rules

1. Provider-specific inputs; generic capability outputs.
2. Signature and spatial use cases share the provider lifecycle.
3. Straight/curved is morphology metadata, not an interface split.
4. Low/high fidelity is metadata, not an inheritance split.
5. Geometry may be internal-only.
6. Capability absence is explicit; never fabricate unsupported products.
7. Radiation is separable from flow whenever possible.
8. Intrinsic source products exclude sensor range, atmosphere, and detector
   response.
9. Source pose is separate from source emission.
10. Every result retains provider, calibration, validity, and approximation
    provenance.

<!-- END 00_unified_plume_architecture.md -->


---

<!-- BEGIN 01_model_contract_and_architecture.md -->

# Model Contract and Architecture

## 1. Objective

Create a staged plume package that can answer four separate questions:

1. What is the nozzle-exit state?
2. What organized shock-cell structure exists in the near field?
3. How does the plume mix and evolve after coherent shock cells disappear?
4. What spectral radiance reaches a sensor from a selected view angle and
   range?

These questions must remain separate in the architecture because they have
different equations, validity limits, and termination conditions.

## 2. Model pipeline

```text
NozzleBoundaryState
        ↓
ShockCellSolver
        ↓
ShockTrainResult
        ↓
IntegralMixingSolver
        ↓
AxisymmetricPlumeField
        ↓
RadiativeTransferSolver
        ↓
SpectralRadianceResult
        ↓
Atmosphere + Sensor
        ↓
SensorSignatureResult
```

## 3. Initial validated model level

The first validated level shall assume:

- Steady flow.
- One circular nozzle.
- A known, uniform, supersonic exit state.
- Quiescent ambient gas.
- Calorically perfect exhaust with constant \(\gamma\).
- Explicit exhaust molecular weight or specific gas constant.
- Frozen composition.
- Planar near-field characteristics, clearly labeled as planar.
- Reduced-order axisymmetric mixing continuation.
- Local thermodynamic equilibrium for radiation.
- Molecular absorption and emission without scattering.

Not included at this level:

- Internal nozzle boundary-layer separation.
- Mach-disk topology.
- RANS/LES turbulence.
- Vehicle base flow.
- Flight coflow.
- Chemical afterburning.
- Soot or condensed particles.
- Non-LTE radiation.
- Rarefied flow.

Out-of-scope conditions must return structured validity flags, not plausible
but unsupported geometry.

## 4. Coordinates and units

### 4.1 Flow coordinates

Near-field planar solver:

```text
x: downstream axial coordinate [m]
y: radial-like transverse coordinate [m]
theta: flow angle from +x [rad]
mu: Mach angle [rad]
```

Axisymmetric field:

```text
x: downstream axial coordinate [m]
r: cylindrical radius [m]
phi: azimuth [rad]
```

### 4.2 Units

```text
pressure            Pa
temperature         K
density             kg / m^3
velocity            m / s
specific enthalpy   J / kg
molecular weight    kg / mol
wavelength          m internally
wavenumber          1 / m internally
spectral radiance   W / (m^2 sr m)
radiant intensity   W / (sr m)
spectral irradiance W / (m^2 m)
angles              rad
```

User-facing micrometers and inverse centimeters require explicit conversion.

## 5. Foundational thermodynamics

### 5.1 Mixture molecular weight

For species mass fractions \(Y_s\) and molecular weights \(W_s\),

\[
\boxed{
\overline W
=
\left(
\sum_s \frac{Y_s}{W_s}
\right)^{-1}
}
\]

and

\[
\boxed{
R = \frac{R_u}{\overline W}.
}
\]

### 5.2 Ideal gas, sound speed, and velocity

\[
\boxed{p=\rho R T}
\]

\[
\boxed{a=\sqrt{\gamma R T}}
\]

\[
\boxed{u=M a}
\]

### 5.3 Stagnation relations

For constant \(\gamma\),

\[
\boxed{
\frac{T_0}{T}
=
1+\frac{\gamma-1}{2}M^2
}
\]

\[
\boxed{
\frac{p_0}{p}
=
\left(
1+\frac{\gamma-1}{2}M^2
\right)^{\gamma/(\gamma-1)}
}
\]

\[
\boxed{
\frac{\rho_0}{\rho}
=
\left(
1+\frac{\gamma-1}{2}M^2
\right)^{1/(\gamma-1)}
}
\]

For a calorically perfect gas,

\[
c_p=\frac{\gamma R}{\gamma-1},
\qquad
h=c_pT,
\]

\[
\boxed{
h_0=h+\frac{u^2}{2}=c_pT_0.
}
\]

Do not use \(p_0/\rho_0=RT_0\) as total enthalpy or total energy.

### 5.4 Area-Mach relation

\[
\boxed{
\frac{A}{A^*}
=
\frac{1}{M}
\left[
\frac{2}{\gamma+1}
\left(
1+\frac{\gamma-1}{2}M^2
\right)
\right]^{\frac{\gamma+1}{2(\gamma-1)}}.
}
\]

For \(A/A^*>1\), the API must require an explicit subsonic or supersonic branch.

### 5.5 Mass flow

\[
\boxed{
\frac{\dot m}{A}
=
p_0
\sqrt{\frac{\gamma}{RT_0}}
M
\left(
1+\frac{\gamma-1}{2}M^2
\right)^{-\frac{\gamma+1}{2(\gamma-1)}}.
}
\]

At \(M=1\),

\[
\boxed{
A^*
=
\frac{\dot m}{p_0}
\sqrt{\frac{RT_0}{\gamma}}
\left(
\frac{\gamma+1}{2}
\right)^{\frac{\gamma+1}{2(\gamma-1)}}.
}
\]

## 6. Regime classification

Define

\[
r_p=\frac{p_e-p_a}{p_a}.
\]

Given a configured or uncertainty-derived tolerance \(\epsilon_p\),

\[
\boxed{
\begin{cases}
r_p>\epsilon_p & \text{UNDEREXPANDED},\\
r_p<-\epsilon_p & \text{OVEREXPANDED},\\
|r_p|\le\epsilon_p & \text{MATCHED}.
\end{cases}
}
\]

Matched flow returns zero shock cells and
`termination_reason = NO_PRESSURE_MISMATCH`.

## 7. Public data contracts

Use frozen Pydantic v2 models for configuration and frozen dataclasses or
Pydantic models for public results. Numerical arrays must be typed as
`numpy.typing.NDArray[np.float64]`.

### 7.1 GasProperties

Required fields:

```text
gamma
specific_gas_constant_JpkgK
molecular_weight_kgpmol
species_mass_fractions
model_kind
```

Invariants:

```text
gamma > 1
R > 0
W > 0
sum(Y_s) == 1 within tolerance
all(Y_s >= 0)
```

At the first model level, require consistency:

\[
R \approx R_u/\overline W.
\]

### 7.2 NozzleExitState

```text
static_pressure_Pa
static_temperature_K
mach
density_kgpm3
axial_velocity_mps
flow_angle_rad
radius_m
mass_flow_rate_kgps
total_pressure_Pa
total_temperature_K
gas
species_mass_fractions
source_kind
```

`source_kind` examples:

```text
DIRECT_UNIFORM_EXIT
DERIVED_ISENTROPIC
CEA_FROZEN
CEA_EQUILIBRIUM
PROFILED_EXIT
```

### 7.3 AmbientState

```text
pressure_Pa
temperature_K
density_kgpm3
velocity_xyz_mps
species_mass_fractions
geopotential_altitude_m | None
```

Altitude is metadata after the ambient state is calculated.

### 7.4 SolverConfiguration

```text
pressure_match_relative_tolerance
root_relative_tolerance
root_absolute_tolerance
geometry_relative_tolerance
max_iterations
max_cells
max_axial_distance_m
model_level
```

### 7.5 TerminationPolicy

```text
minimum_core_diameter_ratio
maximum_pressure_oscillation_ratio
maximum_mean_pressure_residual
minimum_core_mach_excess
persistence_cells
max_cells
max_axial_distance_m
```

### 7.6 SolverStatus

Required enum values:

```text
SUCCESS
NO_PRESSURE_MISMATCH
INVALID_INPUT
NOZZLE_SEPARATION_NOT_MODELED
DETACHED_SHOCK_REQUIRED
MACH_DISK_REQUIRED
GEOMETRY_INTERSECTION_FAILED
ROOT_SOLVE_FAILED
MODEL_VALIDITY_EXCEEDED
PHYSICAL_TERMINATION
DOMAIN_LIMIT
MAX_CELL_LIMIT
NUMERICAL_FAILURE
```

### 7.7 Diagnostics

Every solver result must include:

```text
status
validity_flags
model_level
iteration_counts
residuals
condition_numbers
termination_reason
was_domain_truncated
calibration_id | None
warnings
```

A warning is not a substitute for a failed status.

## 8. Proposed module layout

```text
src/exhaust_plume/
  models/
    gas/
      contracts.py
      calorically_perfect.py
      mixtures.py

    nozzle/
      contracts.py
      area_mach.py
      exit_state.py

    shock_cells/
      contracts.py
      regime.py
      prandtl_meyer.py
      normal_shock.py
      oblique_shock.py
      geometry.py
      planar_characteristics.py
      free_boundary.py
      first_cell.py
      train.py
      termination.py
      correlations.py

    mixing/
      contracts.py
      entrainment.py
      integral_plume.py
      profiles.py

    radiation/
      contracts.py
      planck.py
      ray_geometry.py
      gray_gas.py
      spectroscopy.py
      radiative_transfer.py
      atmosphere.py
      sensor.py

    chemistry/
      contracts.py
      frozen.py
      cea_boundary.py
      finite_rate.py
      particles.py

    validation/
      analytic_cases.py
      regression_cases.py
      experimental_cases.py
```

Existing public imports should be preserved through compatibility wrappers while
the new architecture is introduced.

## 9. Dependency policy

Target Python:

```text
Python 3.12+
```

Preferred dependencies:

```text
numpy
scipy
pydantic >= 2
pytest
ruff
pyright
```

Optional dependencies:

```text
matplotlib      visualization only
hapi            cross-section generation tools
cantera         finite-rate chemistry
```

Do not make HAPI or Cantera hard dependencies of the base gas-dynamics package.

## 10. Invariants enforced throughout

1. All public scalar inputs are finite.
2. All pressures, temperatures, densities, radii, molecular weights, and gas
   constants are positive.
3. Supersonic routines require \(M>1\).
4. Weak shocks reduce stagnation pressure and preserve stagnation temperature
   under the calorically perfect adiabatic assumption.
5. Expansion fans preserve stagnation pressure and temperature.
6. Ray intersections must be forward on every originating ray.
7. Closed polygons are finite, non-self-intersecting, and have nonzero area.
8. Species mass fractions are normalized and nonnegative.
9. Physical termination is never inferred from hitting a numerical limit.
10. Model validity flags propagate into radiation and sensor results.

<!-- END 01_model_contract_and_architecture.md -->


---

<!-- BEGIN 02_foundation_corrections_plan.md -->

# Foundation Corrections Implementation Plan

## 1. Purpose

Correct known defects in the existing branch before adding new geometry,
mixing, radiation, or chemistry. This phase is complete only when every item
below has a focused regression test and the full quality gate passes.

## 2. Files in scope

Primary:

```text
src/exhaust_plume/models/plume/motor_parameters.py
src/exhaust_plume/models/plume/plume_solve.py
src/exhaust_plume/util/aero/flow_state.py
src/exhaust_plume/util/aero/oblique_shock.py
src/exhaust_plume/util/aero/normal_shock.py
src/exhaust_plume/util/aero/isentropic_flow.py
tests/src/models/plume/test_motor_parameters.py
tests/src/models/plume/test_plume_solver.py
tests/src/util/aero/
```

New modules may be introduced under `models/gas`, `models/nozzle`, and
`models/shock_cells`, but existing APIs must retain compatibility wrappers.

## 3. FND-001: Correct choked throat area

### Existing defect

The existing exponent in the throat-area equation is twice the correct value.

### Correct equation

\[
A^*
=
\frac{\dot m}{p_0}
\sqrt{\frac{RT_0}{\gamma}}
\left(
\frac{\gamma+1}{2}
\right)^{\frac{\gamma+1}{2(\gamma-1)}}.
\]

### Implementation

Replace the exponent:

```python
(gamma + 1.0) / (gamma - 1.0)
```

with:

```python
(gamma + 1.0) / (2.0 * (gamma - 1.0))
```

Refactor the mass-flow function into a forward helper:

```python
calc_mass_flow_rate(...)
```

and verify that throat-area and mass-flow calculations invert one another.

### Tests

- Parameterized values of \(\gamma\), \(R\), \(T_0\), \(p_0\), and \(A^*\).
- Compare against the closed-form forward relation.
- Verify monotonicity:
  - larger \(A^*\) gives larger \(\dot m\);
  - larger \(p_0\) gives larger \(\dot m\);
  - larger \(T_0\) gives lower \(\dot m\) for fixed \(A^*\).

## 4. FND-002: Honor gas molecular weight everywhere

### Existing defect

The active nozzle state and one `EngineParameters` density path use dry-air
molecular weight even when another molecular weight is supplied.

### Correct equations

\[
R=\frac{R_u}{W},
\qquad
\rho=\frac{p}{RT}.
\]

### Implementation

Add one explicit gas input to every state-construction path:

```text
specific_gas_constant_JpkgK
```

or:

```text
molecular_weight_kgpmol
```

Prefer a `GasProperties` contract carrying both with consistency validation.

Remove dry-air imports from generic plume/nozzle calculations. Keep dry air
only as an explicit default in atmosphere-specific code or compatibility
wrappers.

### Tests

For identical \(p,T,\gamma,M\), compare two gases:

\[
\frac{\rho_1}{\rho_2}=\frac{R_2}{R_1}.
\]

Verify:

- density changes with molecular weight;
- speed of sound changes with \(R\);
- Mach remains unchanged when explicitly supplied;
- velocity changes as \(M\sqrt{\gamma RT}\).

## 5. FND-003: Correct total-energy naming

### Existing defect

The current property named `specific_total_energy_Jpkg` returns:

\[
\frac{p_0}{\rho_0}=RT_0.
\]

This is neither total enthalpy nor total specific energy.

### Implementation

Add:

```text
specific_gas_work_Jpkg = p / rho
specific_total_enthalpy_Jpkg = cp * T0
specific_total_energy_Jpkg = cv * T + u^2 / 2
```

Use precise names. Deprecate the old property with a compatibility warning if
it is public.

For constant \(\gamma\),

\[
c_p=\frac{\gamma R}{\gamma-1},
\qquad
c_v=\frac{R}{\gamma-1}.
\]

### Tests

Verify:

\[
h_0=h+\frac{u^2}{2}
\]

and, for the calorically perfect model,

\[
h_0=c_pT_0.
\]

## 6. FND-004: Correct weak-shock zero-turn behavior

### Existing defect

The current oblique-shock implementation forces \(\beta=90^\circ\) for
\(\theta=0\) on both branches.

### Correct limits

Weak branch:

\[
\boxed{
\lim_{\theta\to0}\beta=\mu=\sin^{-1}(1/M)
}
\]

Strong branch:

\[
\boxed{
\lim_{\theta\to0}\beta=\pi/2.
}
\]

### Implementation

Separate branch handling explicitly. Avoid exact equality as the only trigger;
use a small-angle limit that remains numerically stable.

Prefer solving the \(\theta\)-\(\beta\)-\(M\) residual with a bounded root
solver over relying only on the closed cubic expression:

\[
f(\beta)
=
\tan\theta
-
2\cot\beta
\frac{M^2\sin^2\beta-1}
{M^2(\gamma+\cos2\beta)+2}.
\]

Weak root bracket:

\[
\beta\in(\mu,\beta_{\max}).
\]

Strong root bracket:

\[
\beta\in(\beta_{\max},\pi/2).
\]

Use `scipy.optimize.brentq` or `root_scalar(..., method="brentq")`.

### Tests

- \(\theta=0\) weak branch equals Mach angle.
- \(\theta=0\) strong branch equals \(\pi/2\).
- Small positive turns converge continuously.
- Weak angle is less than strong angle.
- Returned residual is below configured tolerance.

## 7. FND-005: Detect detached shocks

### Correct criterion

An attached solution exists only when:

\[
\theta\le
\theta_{\max}(M,\gamma)
=
\max_{\mu<\beta<\pi/2}\theta(M,\beta,\gamma).
\]

### Implementation

Add:

```text
calc_max_attached_turn(...)
solve_oblique_shock_angle(...)
```

Return `DETACHED_SHOCK_REQUIRED` when the requested turn exceeds the maximum.

Do not log an error and return a nominal state.

### Tests

- A turn slightly below \(\theta_{\max}\) succeeds.
- A turn slightly above \(\theta_{\max}\) fails structurally.
- The failure contains \(M,\gamma,\theta,\theta_{\max}\).

## 8. FND-006: Add matched-flow regime

### Existing defect

The current `p_e <= p_a` branch treats exact pressure matching as
overexpansion and then requires at least one constructed pass.

### Correct classifier

\[
r_p=\frac{p_e-p_a}{p_a}.
\]

\[
|r_p|\le\epsilon_p
\Rightarrow
\text{MATCHED}.
\]

### Implementation

Add a regime enum:

```text
UNDEREXPANDED
MATCHED
OVEREXPANDED
```

For matched flow:

```text
zones = [nozzle_exit_zone]
cells = []
status = NO_PRESSURE_MISMATCH
```

Permit `max_cells = 0`.

### Tests

Use values derived directly from a target exit-pressure ratio:

```text
p_e / p_a = 0.90
p_e / p_a = 1.00
p_e / p_a = 1.10
```

Do not identify regimes through arbitrary total-pressure values.

## 9. FND-007: Correct precursor line geometry

### Existing defect

The precursor centerline intersection currently uses a degree-valued angle
inside `cos` and uses the wrong geometric relation.

### Correct geometry

For radial drop \(R\) and shock angle \(\beta\) measured from the axis,

\[
\boxed{
\Delta x=\frac{R}{\tan\beta}.
}
\]

### Implementation

Use internal radians:

```python
delta_x_m = radius_m / np.tan(shock_angle_rad)
```

Validate:

```text
delta_x_m > 0
finite(delta_x_m)
shock_angle_rad in (0, pi/2)
```

### Tests

- Hand-calculated line intersections for several angles.
- Exact \(45^\circ\) case gives \(\Delta x=R\).
- Geometry rejects near-zero or non-forward angles.

## 10. FND-008: Replace unvalidated line intersections

### Existing defect

A pseudoinverse produces a least-squares point even for parallel or backward
rays.

### Correct ray model

\[
\mathbf x_i(s_i)=\mathbf o_i+s_i\mathbf d_i,
\qquad
s_i\ge0.
\]

Solve:

\[
\mathbf o_1+s_1\mathbf d_1
=
\mathbf o_2+s_2\mathbf d_2.
\]

### Result contract

```text
RayIntersection2D
  point_xy_m
  parameter_1
  parameter_2
  residual_m
  condition_number
  status
```

Accept only if:

\[
s_1\ge-\epsilon_s,\qquad
s_2\ge-\epsilon_s,
\]

\[
\lVert
\mathbf o_1+s_1\mathbf d_1-
\mathbf o_2-s_2\mathbf d_2
\rVert
\le\epsilon_x.
\]

### Tests

- Exact perpendicular intersection.
- Skew numerical case with small residual.
- Parallel rays.
- Nearly parallel ill-conditioned rays.
- Intersection behind one origin.
- Scale invariance under direction-vector normalization.

## 11. FND-009: Remove public `NaN` polygons

### Existing defect

Some intermediate compression states use `NaN` placeholder coordinates.

### Implementation

Separate state transitions from closed regions:

```text
FlowTransition
CharacteristicSegment
ShockSegment
ClosedZone
```

Only `ClosedZone` has a polygon and can be revolved or ray traced.

For compatibility, existing `ZoneResult` may temporarily wrap either:

```text
coordinates: ZoneCoordinates | None
```

but public geometry consumers must require a closed zone.

### Tests

- Every `ClosedZone` has finite coordinates.
- Polygon area is positive.
- No self-intersection.
- Unclosed transitions cannot enter mesh or radiation code.

## 12. FND-010: Rename repeated “plumes”

### Existing defect

`num_plumes` and `plume_index` describe repeated shock-cell construction passes,
not separate physical plumes.

### Migration

```text
num_plumes → max_cells
plume_index → cell_index
```

Maintain deprecated aliases for one release cycle.

### Tests

- Old keyword produces a deprecation warning.
- Supplying both old and new keywords raises a clear error.
- Serialized output uses new names.

## 13. FND-011: Harden scalar validation

Require:

```text
finite values
gamma > 1
mach > 1 for supersonic routines
pressure > 0
temperature > 0
density > 0
radius > 0
molecular weight > 0
specific gas constant > 0
integer counts are not bool
```

Every invalid state must fail before numerical work starts.

## 14. FND-012: Correct the current regime tests

The current nominal values:

\[
p_0=69\ \mathrm{atm},
\quad
M_e=4.13,
\quad
\gamma=1.33
\]

give:

\[
\frac{p_0}{p_e}=220.454330636,
\]

\[
p_e=0.312989996\ \mathrm{atm}
\]

and, for \(T_0=2000\ \mathrm K\),

\[
T_e=524.330440\ \mathrm K.
\]

At sea-level ambient pressure, this is overexpanded. Rename or replace any test
that calls it underexpanded.

At the branch's 10 km standard-atmosphere state,

\[
p_a\approx26436.27\ \mathrm{Pa},
\]

so the same exit state is mildly underexpanded.

## 15. Required quality gate

Run:

```bash
python -m pytest
python -m ruff check .
python -m pyright
python -m build
```

Phase 0 is complete only when:

- all existing tests pass or are deliberately migrated;
- all new defect tests pass;
- no ignored `NaN` or runtime warning is required in the corrected paths;
- no solver logs an error and returns a nominal success result;
- compatibility deprecations are documented.

<!-- END 02_foundation_corrections_plan.md -->


---

<!-- BEGIN 03_validated_first_cell_plan.md -->

# Validated First Shock-Cell Plan

## 1. Purpose

Replace the current point-and-parabola construction with a planar,
method-of-characteristics-style first-cell solver whose equations,
compatibility conditions, free boundary, and failure modes are explicit.

This phase does not claim an axisymmetric solution. Its purpose is to establish
a physically interpretable and numerically convergent first shock cell that can
be compared against theory, experiment, and later higher-fidelity models.

## 2. Scope

Supported:

- Uniform circular-nozzle exit represented by a planar half-domain.
- Constant-\(\gamma\), calorically perfect gas.
- Mild underexpansion.
- Mild overexpansion with an attached weak-shock solution and a validated
  uniform exit state.
- Quiescent ambient pressure.
- One coherent cell.
- Closed, finite zones suitable for later revolution and ray tracing.

Explicitly unsupported in this phase:

- Detached shocks.
- Mach disks or Mach reflection.
- Internal nozzle separation.
- Flight coflow.
- Turbulent mixing within the cell.
- Reacting flow.
- Axisymmetric characteristic source terms.

Unsupported cases return structured status.

## 3. Governing equations

## 3.1 Mach angle

\[
\boxed{
\mu(M)=\sin^{-1}\left(\frac{1}{M}\right).
}
\]

## 3.2 Prandtl-Meyer function

\[
\boxed{
\nu(M)
=
\sqrt{\frac{\gamma+1}{\gamma-1}}
\tan^{-1}
\sqrt{
\frac{\gamma-1}{\gamma+1}(M^2-1)
}
-
\tan^{-1}\sqrt{M^2-1}.
}
\]

The expansion turn is:

\[
\boxed{
\Delta\theta=\nu(M_2)-\nu(M_1).
}
\]

The inverse \(M=\nu^{-1}(\nu,\gamma)\) shall use a bounded scalar root solve on
the supersonic branch.

## 3.3 Planar characteristic slopes

Define:

\[
C^+:
\quad
\frac{dy}{dx}=\tan(\theta+\mu),
\]

\[
C^-:
\quad
\frac{dy}{dx}=\tan(\theta-\mu).
\]

For steady, planar, irrotational, isentropic flow:

\[
\boxed{
K_{C^+}=\theta-\nu=\text{constant along }C^+,
}
\]

\[
\boxed{
K_{C^-}=\theta+\nu=\text{constant along }C^-.
}
\]

At the intersection of a \(C^+\) line carrying \(K_{C^+}\) and a \(C^-\) line
carrying \(K_{C^-}\),

\[
\boxed{
\theta
=
\frac{K_{C^+}+K_{C^-}}{2},
}
\]

\[
\boxed{
\nu
=
\frac{K_{C^-}-K_{C^+}}{2}.
}
\]

Then invert \(\nu\) to recover \(M\).

## 3.4 Characteristic intersection geometry

For an incoming characteristic from point \(A\) with angle
\(\psi_A=\theta_A+\mu_A\), and one from point \(B\) with angle
\(\psi_B=\theta_B-\mu_B\),

\[
y-y_A=\tan\psi_A(x-x_A),
\]

\[
y-y_B=\tan\psi_B(x-x_B).
\]

Solve this as a forward ray intersection and report both ray parameters,
condition number, and residual.

For increased accuracy, use averaged endpoint slopes during grid marching:

\[
\psi_{A\to P}
=
\frac{
(\theta_A+\mu_A)+(\theta_P+\mu_P)
}{2},
\]

\[
\psi_{B\to P}
=
\frac{
(\theta_B-\mu_B)+(\theta_P-\mu_P)
}{2}.
\]

The point solve then becomes a small nonlinear iteration because the endpoint
state and geometry are coupled. Use fixed-point iteration or a bounded
two-variable root solve with residual diagnostics.

## 3.5 Centerline condition

At \(y=0\),

\[
\boxed{\theta=0.}
\]

For a characteristic reaching the centerline, combine its invariant with
\(\theta=0\) to calculate the reflected state.

No line should be reflected through a matrix operation alone; the state
compatibility condition must also be applied.

## 3.6 Free-boundary conditions

The plume boundary is a streamline:

\[
\boxed{
\frac{dy_b}{dx}=\tan\theta_b.
}
\]

For a quiescent ambient and neglected surface tension,

\[
\boxed{p_b=p_a.}
\]

At constant stagnation pressure on an isentropic boundary segment,

\[
\boxed{
M_b
=
\sqrt{
\frac{2}{\gamma-1}
\left[
\left(\frac{p_0}{p_a}\right)^{(\gamma-1)/\gamma}
-1
\right]
}.
}
\]

The boundary state must satisfy both the pressure condition and the incoming
characteristic invariant. The boundary point is then found from the incoming
characteristic and a tangent segment whose slope is the local flow angle.

The free boundary must not be replaced by an unconstrained polynomial fit.

## 3.7 Oblique shock equations

For upstream \(M_1\), shock angle \(\beta\), and turn \(\theta\),

\[
\tan\theta
=
2\cot\beta
\frac{
M_1^2\sin^2\beta-1
}{
M_1^2(\gamma+\cos2\beta)+2
}.
\]

Set:

\[
M_{n1}=M_1\sin\beta.
\]

Then:

\[
\frac{p_2}{p_1}
=
1+\frac{2\gamma}{\gamma+1}(M_{n1}^2-1),
\]

\[
\frac{\rho_2}{\rho_1}
=
\frac{(\gamma+1)M_{n1}^2}
{2+(\gamma-1)M_{n1}^2},
\]

\[
\frac{T_2}{T_1}
=
\frac{p_2/p_1}{\rho_2/\rho_1},
\]

\[
M_{n2}^2
=
\frac{
1+\frac{\gamma-1}{2}M_{n1}^2
}{
\gamma M_{n1}^2-\frac{\gamma-1}{2}
},
\]

\[
M_2=\frac{M_{n2}}{\sin(\beta-\theta)}.
\]

The total-pressure ratio is:

\[
\boxed{
\frac{p_{02}}{p_{01}}
=
\left[
\frac{(\gamma+1)M_{n1}^2}
{(\gamma-1)M_{n1}^2+2}
\right]^{\gamma/(\gamma-1)}
\left[
\frac{\gamma+1}
{2\gamma M_{n1}^2-(\gamma-1)}
\right]^{1/(\gamma-1)}.
}
\]

## 4. First-cell data structures

### 4.1 CharacteristicPoint

```text
x_m
y_m
mach
flow_angle_rad
mach_angle_rad
prandtl_meyer_rad
static_pressure_Pa
static_temperature_K
density_kgpm3
total_pressure_Pa
total_temperature_K
source_kind
```

### 4.2 CharacteristicSegment

```text
kind: C_PLUS | C_MINUS
start_point
end_point
invariant_value_rad
intersection_diagnostics
```

### 4.3 ShockSegment

```text
start_point
end_point
upstream_state
downstream_state
shock_angle_rad
turn_angle_rad
total_pressure_ratio
status
```

### 4.4 FreeBoundaryPoint

```text
point
flow_state
boundary_tangent_rad
pressure_residual
characteristic_residual
```

### 4.5 ClosedZone

```text
vertices_xy_m
flow_state
zone_kind
cell_index
area_m2
```

### 4.6 FirstCellResult

```text
regime
characteristic_points
characteristic_segments
shock_segments
free_boundary
closed_zones
cell_start_x_m
cell_end_x_m
cell_length_m
maximum_radius_m
centerline_pressure_extrema_Pa
status
diagnostics
```

## 5. Underexpanded first-cell algorithm

1. Validate the exit state and classify the regime.
2. If matched, return zero cells.
3. Calculate the ambient-pressure boundary Mach \(M_b\).
4. Calculate the total lip expansion:
   \[
   \Delta\theta_{\mathrm{lip}}
   =
   \nu(M_b)-\nu(M_e).
   \]
5. Discretize the expansion fan into \(N\) characteristic states. Use equal
   increments in \(\nu\), not arbitrary equal geometry angles:
   \[
   \nu_i
   =
   \nu_e
   +
   \frac{i}{N}
   (\nu_b-\nu_e).
   \]
6. March the characteristics from the lip to the centerline using forward
   intersection solves and centerline compatibility.
7. Reflect the wave system using characteristic invariants and the
   \(\theta=0\) centerline condition.
8. Solve the free-boundary state and point at every boundary intersection using:
   - incoming characteristic invariant;
   - \(p=p_a\);
   - boundary tangent equal to local flow direction.
9. Where compression requires a discontinuity, solve an attached weak shock.
10. Reject the case if the requested turn exceeds the attached-shock maximum.
11. Build closed zones from ordered, finite vertices.
12. Calculate geometry and conservation diagnostics.
13. Repeat for increasing \(N\) during convergence testing.

## 6. Mild overexpanded first-cell algorithm

The external model may proceed only when the caller certifies a valid uniform
exit state.

1. Calculate the weak-shock solution required to raise pressure toward ambient.
2. Check the maximum attached turn.
3. Construct the lip shock as a forward ray.
4. Apply centerline symmetry at its reflection.
5. Continue with characteristic/free-boundary compatibility.
6. If the required compression is detached, return
   `DETACHED_SHOCK_REQUIRED`.
7. If the pressure ratio or topology indicates a Mach disk, return
   `MACH_DISK_REQUIRED`.
8. If nozzle separation is plausible but no validated exit profile is supplied,
   return `NOZZLE_SEPARATION_NOT_MODELED`.

This phase does not attempt to synthesize a separated nozzle exit.

## 7. First-cell correlation check

Define the fully expanded Mach:

\[
\boxed{
M_j
=
\sqrt{
\frac{2}{\gamma-1}
\left[
\left(\frac{p_0}{p_a}\right)^{(\gamma-1)/\gamma}
-1
\right]
}.
}
\]

Define the area-Mach function:

\[
\mathcal A(M)
=
\frac{1}{M}
\left[
\frac{2}{\gamma+1}
\left(
1+\frac{\gamma-1}{2}M^2
\right)
\right]^{\frac{\gamma+1}{2(\gamma-1)}}.
\]

Then:

\[
\frac{A_j}{A_e}
=
\frac{\mathcal A(M_j)}{\mathcal A(M_e)},
\]

\[
D_j
=
D_e
\sqrt{
\frac{\mathcal A(M_j)}{\mathcal A(M_e)}
}.
\]

Use the classical nearly adapted circular-jet spacing only as a correlation
check:

\[
\boxed{
L_{s,\mathrm{corr}}
=
1.306D_j\sqrt{M_j^2-1}.
}
\]

Report:

\[
\epsilon_L
=
\frac{
L_{s,\mathrm{solver}}
-
L_{s,\mathrm{corr}}
}{
L_{s,\mathrm{corr}}
}.
\]

Do not force the computed geometry to equal the correlation.

For the branch's illustrative 10 km defaults:

\[
M_j\approx4.25733,
\qquad
D_j\approx2.13332\ \mathrm m,
\]

\[
L_{s,\mathrm{corr}}\approx11.5296\ \mathrm m.
\]

This is a regression anchor, not an experimental truth target.

## 8. Numerical strategy

Use:

```text
scipy.optimize.brentq       bounded scalar inversions
scipy.optimize.root_scalar  equivalent bounded roots
numpy.linalg.solve          well-conditioned 2x2 intersections
numpy.linalg.cond           intersection diagnostics
```

Do not use unconstrained root finding where physical brackets exist.

Every iterative calculation returns:

```text
converged
iterations
final_residual
bracket
status
```

## 9. Verification tests

### State-level

- \(\nu^{-1}(\nu(M))=M\).
- Characteristic invariants remain constant.
- Boundary pressure equals ambient.
- Centerline angle equals zero.
- Expansions preserve \(p_0,T_0\).
- Shocks preserve \(T_0\) and reduce \(p_0\).

### Geometry-level

- Every accepted ray parameter is forward.
- Every closed-zone vertex is finite.
- Every polygon area is positive.
- No polygon self-intersects.
- Adjacent zones share common interfaces within tolerance.
- Free-boundary slope matches local \(\theta\).

### Convergence-level

For fan resolutions \(N,2N,4N\), track:

```text
cell length
maximum radius
centerline pressure extrema
free-boundary pressure residual
```

Require asymptotic reduction in changes before declaring grid convergence.

## 10. Acceptance gate

Phase 1 is complete only when:

1. Matched flow returns zero cells.
2. A mild underexpanded case produces one finite, closed cell.
3. A mild attached overexpanded case produces one finite, closed cell.
4. Detached cases fail structurally.
5. The free-boundary pressure residual meets tolerance.
6. Centerline symmetry meets tolerance.
7. Conservation and total-pressure-loss checks pass.
8. Results converge with fan resolution.
9. Near-adapted first-cell scale is reasonably consistent with the correlation
   and any selected experimental benchmark.
10. The result is labeled `PLANAR_MOC`, not axisymmetric.

<!-- END 03_validated_first_cell_plan.md -->


---

<!-- BEGIN 04_shock_train_and_termination_plan.md -->

# Finite Shock Train and Termination Plan

## 1. Purpose

Predict a finite sequence of coherent shock cells rather than asking the user
how many “plumes” to construct.

This phase introduces reduced-order closures for shear-layer growth and
shock-amplitude decay. These closures must be calibrated and must remain
separate from governing gas-dynamic equations.

## 2. Distinct endpoints

The implementation must report separate distances:

```text
shock_train_end_x_m
supersonic_core_end_x_m
thermal_plume_end_x_m
ir_domain_end_x_m
```

They are not interchangeable.

### Shock-train end

Coherent pressure oscillations are no longer resolvable.

### Supersonic-core end

The remaining coherent core is no longer supersonic.

### Thermal-plume end

Temperature and velocity disturbances have mixed toward ambient.

### IR-domain end

Further plume slices contribute negligibly to a selected spectral band and
viewing condition.

## 3. Inputs

```text
FirstCellResult
NozzleExitState
AmbientState
TerminationPolicy
ShockTrainCalibration
max_cells
max_axial_distance_m
```

## 4. Calibration contract

`ShockTrainCalibration` shall contain:

```text
calibration_id
source_description
applicable_mach_range
applicable_pressure_ratio_range
applicable_temperature_ratio_range
mixing_layer_growth_rate
pressure_amplitude_decay_coefficient
cell_spacing_coefficient
finite_shear_layer_spacing_correction
parameter_covariance | None
```

No empirical value may exist only as a module-level number without provenance.

## 5. Reduced-order coherent-core model

## 5.1 Inward mixing-layer growth

Let the inward shear-layer thickness be:

\[
\boxed{
\delta_i(x)=\delta_{i,0}+S_i x.
}
\]

Here \(S_i\) is a closure.

The coherent-core diameter is:

\[
\boxed{
D_c(x)
=
\max\left[D_j-2\delta_i(x),0\right].
}
\]

The geometric core endpoint is:

\[
\boxed{
x_{c,\mathrm{geom}}
=
\frac{D_j-2\delta_{i,0}}{2S_i}
}
\]

when \(S_i>0\).

## 5.2 Local fully expanded state

At the beginning of cell \(n\), use the local core stagnation pressure
\(p_{0,n}\) and ambient pressure:

\[
\boxed{
M_{j,n}
=
\sqrt{
\frac{2}{\gamma-1}
\left[
\left(\frac{p_{0,n}}{p_a}\right)^{(\gamma-1)/\gamma}
-1
\right]
}.
}
\]

If the term inside the square root is nonpositive or
\(M_{j,n}\le1+\epsilon_M\), the coherent supersonic cell system terminates.

## 5.3 Local cell spacing

Use:

\[
\boxed{
L_n
=
C_\lambda
D_c(x_n)
\sqrt{M_{j,n}^2-1}
\,
\Phi_\delta(x_n).
}
\]

Where:

- \(C_\lambda\) begins near the classical circular-jet value \(1.306\).
- \(\Phi_\delta\) is a calibrated finite-shear-layer correction.
- Neither is a universal constant.

A minimal first correction may use:

\[
\Phi_\delta
=
\max
\left[
1-C_\delta\frac{\delta_i}{D_j},
\Phi_{\min}
\right].
\]

The cell boundaries are:

\[
\boxed{
x_{n+1}=x_n+L_n.
}
\]

## 5.4 Pressure oscillation amplitude

Measure the first cell:

\[
A_{p,0}
=
\frac{
p_{\max,0}-p_{\min,0}
}{
2p_a
}.
\]

Use the decay closure:

\[
\boxed{
\frac{dA_p}{dx}
=
-\frac{C_d}{D_c(x)}A_p.
}
\]

The exact integrated form is:

\[
\boxed{
A_p(x)
=
A_{p,0}
\exp
\left[
-C_d
\int_0^x\frac{d\xi}{D_c(\xi)}
\right].
}
\]

For cell stepping, use:

\[
A_{p,n+1}
=
A_{p,n}
\exp
\left[
-C_d
\frac{L_n}
{D_{c,\mathrm{mid},n}}
\right].
\]

## 5.5 Mean pressure residual

For each cell:

\[
\boxed{
r_{\overline p,n}
=
\frac{\overline p_n-p_a}{p_a}.
}
\]

Track both mean mismatch and oscillation amplitude. One zero crossing of
\(p-p_a\) is not termination.

## 5.6 Total-pressure loss

The local core stagnation pressure must account for every modeled shock:

\[
\boxed{
p_{0,n+1}
=
p_{0,n}
\prod_{k\in\text{shocks of cell }n}
\left(
\frac{p_{0,2}}{p_{0,1}}
\right)_k.
}
\]

Do not apply an isentropic total-pressure reconstruction across a shock without
explicitly accounting for entropy loss.

## 6. Cell geometry options

Implement an interface:

```text
ShockCellGeometryModel
  solve_cell(...)
```

### Level A: Resolved first cell

The first cell uses the validated characteristic/free-boundary solver.

### Level B: Reduced-order downstream cells

The initial implementation may scale a nondimensional first-cell template:

\[
\hat x=\frac{x-x_n}{L_n},
\qquad
\hat r=\frac{r}{D_c(x_n)}.
\]

Pressure and wave strength are scaled using \(A_{p,n}\), while thermodynamic
states are recomputed from the local core state.

Every Level B result must carry:

```text
geometry_fidelity = SCALED_REDUCED_ORDER
```

It must not be labeled as a newly solved MOC cell.

### Level C: Re-solved downstream cells

A later implementation may call the first-cell solver for each updated local
state and effective diameter:

```text
geometry_fidelity = RECOMPUTED_PLANAR_MOC
```

## 7. Termination policy

Define:

\[
d_n=\frac{D_c(x_n)}{D_j}.
\]

Terminate physically if any criterion persists as configured.

### Core diameter

\[
\boxed{
d_n\le\epsilon_D.
}
\]

### Core Mach

\[
\boxed{
M_{c,n}\le1+\epsilon_M.
}
\]

### Pressure oscillation

\[
\boxed{
A_{p,n}\le\epsilon_{\mathrm{osc}}
}
\]

for `persistence_cells` consecutive cells.

### Mean pressure plus oscillation

\[
\boxed{
|r_{\overline p,n}|
\le\epsilon_{\mathrm{mean}}
\quad\land\quad
A_{p,n}\le\epsilon_{\mathrm{osc}}.
}
\]

### Model topology

Terminate the current model with a validity status when:

```text
MACH_DISK_REQUIRED
DETACHED_SHOCK_REQUIRED
NOZZLE_SEPARATION_NOT_MODELED
MODEL_VALIDITY_EXCEEDED
```

### Safety limits

```text
x >= max_axial_distance_m  → DOMAIN_LIMIT
n >= max_cells             → MAX_CELL_LIMIT
```

Safety limits are not physical equilibration.

## 8. Iteration algorithm

```text
1. Initialize from FirstCellResult.
2. Record first-cell metrics.
3. Evaluate termination after the completed first cell.
4. Update mixing-layer thickness and coherent-core diameter.
5. Update local total pressure from shock losses.
6. Calculate local fully expanded Mach.
7. Calculate local cell spacing.
8. Calculate pressure-amplitude decay.
9. Generate the next reduced-order or re-solved cell.
10. Record cell metrics and diagnostics.
11. Apply persistence logic.
12. Stop on the first physical, validity, or safety condition.
```

The output cell count is:

\[
\boxed{
N_{\mathrm{cells}}
=
\min\{n:\text{termination policy is satisfied}\}.
}
\]

## 9. Result contracts

### ShockCellMetrics

```text
cell_index
start_x_m
end_x_m
length_m
effective_core_diameter_m
core_mach
mean_pressure_Pa
maximum_pressure_Pa
minimum_pressure_Pa
pressure_oscillation_ratio
mean_pressure_residual
inlet_total_pressure_Pa
outlet_total_pressure_Pa
geometry_fidelity
```

### ShockTrainResult

```text
cells
cell_count
shock_train_end_x_m
supersonic_core_end_x_m
termination_reason
termination_metrics
was_domain_truncated
calibration_id
uncertainty | None
status
diagnostics
```

## 10. Uncertainty propagation

If the calibration supplies a covariance matrix, support Monte Carlo or local
linear propagation for:

```text
cell_count
shock_train_end_x_m
first_cell_length_m
last_pressure_amplitude
```

At minimum, expose sensitivity sweeps for \(S_i\), \(C_d\), and \(C_\lambda\).

A single deterministic value without calibration provenance is not sufficient
for a scientific result.

## 11. Verification tests

1. \(S_i\to0\) prevents geometric core shrinkage.
2. Larger \(S_i\) shortens the coherent-core length.
3. \(C_d\to0\) prevents pressure-amplitude decay.
4. Larger \(C_d\) decreases cell count.
5. \(p_e/p_a\to1\) produces zero or vanishingly weak cells.
6. Each shock decreases \(p_0\).
7. Cell spacing remains positive and finite.
8. Persistence logic does not stop on one isolated weak cell.
9. `DOMAIN_LIMIT` and `MAX_CELL_LIMIT` remain distinguishable from physical
   termination.
10. Reduced-order cells carry the correct fidelity label.

## 12. Validation gate

Calibrate on one dataset and validate against another.

Required comparison quantities:

```text
first-cell length / fully expanded diameter
subsequent mean cell spacing
centerline pressure maxima and minima
pressure-amplitude decay
Mach-disk location if used only as an out-of-scope classifier
potential-core length
```

Do not tune and validate against the same cases without an explicit split.

## 13. Acceptance gate

Phase 2 is complete when:

- cell count is an output, not a required physical input;
- every termination has a reason and metrics;
- physical and safety termination are distinct;
- calibration parameters have provenance;
- sensitivity tests behave monotonically;
- at least one calibration/validation split is documented;
- no downstream cell is mislabeled as resolved MOC when it is template-scaled.

<!-- END 04_shock_train_and_termination_plan.md -->


---

<!-- BEGIN 05_integral_mixing_plume_plan.md -->

# Integral Downstream Mixing-Plume Plan

## 1. Purpose

Continue the plume after coherent shock cells disappear. This model supplies
the downstream velocity, temperature, radius, density, and species fields
needed for thermal and infrared calculations.

The first implementation is a steady, axisymmetric, pressure-matched,
top-hat integral plume. A Gaussian-profile refinement follows only after the
top-hat conservation equations pass verification.

## 2. Entry condition

Start at:

```text
x0 = shock_train_end_x_m
```

Use an area-averaged state derived from the final coherent-core and shear-layer
state.

Required inputs:

```text
mass_flow_rate_kgps
axial_momentum_flux_N
total_enthalpy_flow_W
species_mass_flow_rates_kgps
ambient_state
initial_radius_m
entrainment_calibration
```

## 3. State vector

Use conserved or balance-friendly variables:

\[
\mathbf q
=
\begin{bmatrix}
\dot m\\
\Pi\\
\dot H_0\\
\dot m_1\\
\vdots\\
\dot m_{N_s}
\end{bmatrix}.
\]

Where:

\[
\dot m=\rho uA,
\]

\[
\Pi=\dot m u+(p-p_a)A,
\]

\[
\dot H_0=\dot m h_0,
\]

\[
\dot m_s=\dot mY_s.
\]

This formulation reduces drift in mass, momentum, enthalpy, and species.

## 4. Baseline assumptions

For the first implementation:

\[
p(x)=p_a.
\]

Therefore:

\[
\Pi=\dot m u.
\]

No body forces:

\[
\frac{d\Pi}{dx}=0.
\]

Frozen, nonreacting chemistry:

\[
\dot\omega_s=0.
\]

No radiative feedback on the flow:

\[
\dot Q'_{\mathrm{rad}}=0.
\]

These assumptions can be relaxed later without changing the state contract.

## 5. Entrainment closure

Let \(R(x)\) be the top-hat plume radius. Use:

\[
\boxed{
\frac{d\dot m}{dx}
=
2\pi R
\rho_a
E
|u-u_a|.
}
\]

\(E\) is a calibrated entrainment coefficient.

For quiescent ambient:

\[
u_a=0.
\]

The entrained stream carries ambient momentum, enthalpy, and species.

## 6. Momentum equation

General pressure-aware form:

\[
\boxed{
\frac{d}{dx}
\left[
\dot m u+(p-p_a)A
\right]
=
F'_x.
}
\]

For the baseline pressure-matched, force-free model:

\[
\boxed{
\frac{d\Pi}{dx}=0.
}
\]

Therefore:

\[
\boxed{
u=\frac{\Pi}{\dot m}.
}
\]

As mass is entrained, velocity decays.

## 7. Total-enthalpy equation

\[
\boxed{
\frac{d\dot H_0}{dx}
=
h_{0a}\frac{d\dot m}{dx}
+
\dot Q'_{\mathrm{chem}}
-
\dot Q'_{\mathrm{rad}}
+
\dot W'_{\mathrm{ext}}.
}
\]

Baseline:

\[
\boxed{
\frac{d\dot H_0}{dx}
=
h_{0a}\frac{d\dot m}{dx}.
}
\]

Recover:

\[
h_0=\frac{\dot H_0}{\dot m}.
\]

Then:

\[
\boxed{
h=h_0-\frac{u^2}{2}.
}
\]

For a calorically perfect mixture:

\[
\boxed{
T=\frac{h}{c_p(\mathbf Y)}.
}
\]

## 8. Species equations

For species \(s\):

\[
\boxed{
\frac{d(\dot mY_s)}{dx}
=
Y_{s,a}\frac{d\dot m}{dx}
+
\dot\omega_sA.
}
\]

Baseline frozen mixing:

\[
\boxed{
\frac{d\dot m_s}{dx}
=
Y_{s,a}\frac{d\dot m}{dx}.
}
\]

Recover:

\[
\boxed{
Y_s=\frac{\dot m_s}{\dot m}.
}
\]

After every step, verify:

\[
Y_s\ge0,
\qquad
\sum_sY_s=1
\]

within tolerance.

## 9. Thermodynamic closure and radius

Calculate mixture molecular weight:

\[
\overline W
=
\left(
\sum_s\frac{Y_s}{W_s}
\right)^{-1},
\]

\[
R=\frac{R_u}{\overline W}.
\]

At \(p=p_a\),

\[
\boxed{
\rho=\frac{p_a}{RT}.
}
\]

The cross-sectional area is:

\[
\boxed{
A=\frac{\dot m}{\rho u}.
}
\]

For a circular plume:

\[
\boxed{
R_{\mathrm{plume}}=\sqrt{\frac{A}{\pi}}.
}
\]

## 10. ODE system

The baseline derivatives are:

\[
\frac{d\dot m}{dx}
=
2\pi R_{\mathrm{plume}}
\rho_a
E
|u-u_a|,
\]

\[
\frac{d\Pi}{dx}=0,
\]

\[
\frac{d\dot H_0}{dx}
=
h_{0a}\frac{d\dot m}{dx},
\]

\[
\frac{d\dot m_s}{dx}
=
Y_{s,a}\frac{d\dot m}{dx}.
\]

At every right-hand-side evaluation:

1. Recover \(u=\Pi/\dot m\).
2. Recover \(Y_s=\dot m_s/\dot m\).
3. Calculate \(h_0=\dot H_0/\dot m\).
4. Calculate \(h=h_0-u^2/2\).
5. Invert \(h(T,\mathbf Y)\) for \(T\).
6. Calculate \(R(\mathbf Y)\) and \(\rho=p_a/(RT)\).
7. Calculate \(A=\dot m/(\rho u)\).
8. Calculate plume radius and entrainment.

Use `scipy.integrate.solve_ivp` with event functions and dense output.

## 11. Termination events

### Velocity equilibrium

\[
\boxed{
\frac{|u-u_a|}
{\max(|u_0-u_a|,u_{\mathrm{scale}})}
\le\epsilon_u.
}
\]

### Temperature equilibrium

\[
\boxed{
\frac{|T-T_a|}{T_a}
\le\epsilon_T.
}
\]

### Composition equilibrium

\[
\boxed{
\frac12
\sum_s
|Y_s-Y_{s,a}|
\le\epsilon_Y.
}
\]

### Persistence

Require all selected equilibrium criteria for a minimum axial persistence
length:

\[
\Delta x_{\mathrm{persist}}
\ge
L_{\mathrm{persist}}.
\]

### Domain limit

\[
x\ge x_{\max}
\Rightarrow
\text{DOMAIN_LIMIT}.
\]

## 12. Axisymmetric field reconstruction

The top-hat field is:

\[
\phi(x,r)
=
\begin{cases}
\phi_c(x), & r\le R(x),\\
\phi_a, & r>R(x).
\end{cases}
\]

This is sufficient for the first gray-gas ray tracer but creates a sharp
boundary.

The next refinement uses a Gaussian profile:

\[
\boxed{
\phi(x,r)
=
\phi_a+
[\phi_c(x)-\phi_a]
\exp
\left[
-\left(\frac{r}{b_\phi(x)}\right)^2
\right].
}
\]

Profile widths must be selected so that integrated mass, momentum, enthalpy,
and species match the integral state. Do not choose widths independently of
the conserved fluxes.

## 13. Data contracts

### IntegralPlumeState

```text
x_m
mass_flow_rate_kgps
momentum_flux_N
total_enthalpy_flow_W
species_mass_flow_rates_kgps
velocity_mps
temperature_K
pressure_Pa
density_kgpm3
radius_m
species_mass_fractions
```

### IntegralPlumeResult

```text
states
termination_reason
termination_x_m
conservation_residuals
calibration_id
status
diagnostics
```

### AxisymmetricPlumeField

```text
axial_grid_m
radial_grid_m
temperature_K
pressure_Pa
density_kgpm3
axial_velocity_mps
species_mole_fractions
validity_mask
source_model
```

## 14. Numerical safeguards

Reject or stop when:

```text
mass flow <= 0
velocity <= 0 before expected equilibrium
temperature <= 0
enthalpy inversion fails
radius is nonfinite
species normalization fails
ODE step creates nonphysical state
```

All event and failure states must include the last valid state.

## 15. Verification tests

### Analytic limiting cases

1. \(E=0\):
   - \(\dot m\) constant;
   - \(u\) constant;
   - \(T\) constant;
   - species constant.

2. Ambient identical to plume:
   - no meaningful disturbance;
   - immediate equilibrium status.

3. Frozen entrainment:
   - total species mass-flow derivative equals ambient species in entrained
     mass.

### Conservation

Track:

\[
r_m
=
\dot m(x)
-
\dot m_0
-
\int_{x_0}^x
\frac{d\dot m}{d\xi}d\xi,
\]

\[
r_\Pi=\Pi(x)-\Pi_0,
\]

\[
r_H
=
\dot H_0(x)
-
\dot H_{0,0}
-
\int_{x_0}^x
h_{0a}
\frac{d\dot m}{d\xi}
d\xi.
\]

Require normalized residuals below configured tolerances.

### Monotonic behavior

For hot, fast exhaust in quiescent ambient:

```text
mass flow increases
velocity decreases
temperature approaches ambient
plume radius grows
exhaust-species fractions decrease
ambient-species fractions increase
```

Do not hard-code monotonic temperature when chemistry is later enabled.

## 16. Acceptance gate

Phase 3 is complete when:

- mass, momentum, enthalpy, and species balances close;
- event termination is distinct from domain truncation;
- the top-hat field produces finite ray intersections;
- the field approaches ambient under nonreacting mixing;
- the result preserves model and calibration provenance;
- Gaussian reconstruction, if added, preserves the integral fluxes.

<!-- END 05_integral_mixing_plume_plan.md -->


---

<!-- BEGIN 06_spectral_ir_plan.md -->

# Spectral Infrared Signature Plan

## 1. Purpose

Calculate plume spectral radiance as a function of:

```text
wavelength or wavenumber
viewing angle
image-plane location
sensor range
atmospheric path
sensor spectral response
```

The radiation model must operate on a volumetric temperature, pressure,
composition, velocity, and particle field. Projected area alone is not a
sufficient gas-plume radiation model.

## 2. Implementation stages

### IR-0: Planck and units

Implement Planck radiance, spectral-coordinate conversion, and unit tests.

### IR-1: Gray-gas analytic solver

Implement constant absorption in slabs and axisymmetric fields. Validate the
radiative-transfer equation before adding spectroscopy.

### IR-2: Piecewise axisymmetric ray tracer

Intersect rays with plume zones or gridded fields and solve ordered segment
transport.

### IR-3: Tabulated molecular cross sections

Use precomputed species cross sections on a \(T,p\) grid.

### IR-4: Line-by-line benchmark path

Use HITEMP/HAPI-derived line data for narrow spectral windows and reference
tests.

### IR-5: Atmospheric propagation and sensor response

Apply path transmittance, path radiance, range dilution, optics, and detector
band response.

### IR-6: Particles and scattering

Add only after the molecular no-scattering solver passes validation.

## 3. Spectral-coordinate contract

Do not mix wavelength and wavenumber arrays implicitly.

```text
SpectralCoordinateKind
  WAVELENGTH_M
  WAVENUMBER_PER_M
```

Every spectral result must carry:

```text
coordinate_kind
coordinate_values
spectral_density_unit
```

If converting spectral density, use the Jacobian. For example:

\[
I_\lambda\,d\lambda
=
I_{\tilde\nu}\,d\tilde\nu,
\qquad
\tilde\nu=\frac1\lambda.
\]

Therefore:

\[
\boxed{
I_{\tilde\nu}
=
I_\lambda
\left|
\frac{d\lambda}{d\tilde\nu}
\right|
=
I_\lambda\lambda^2.
}
\]

The implementation must test integral preservation under conversion.

## 4. Planck spectral radiance

In wavelength coordinates:

\[
\boxed{
B_\lambda(T)
=
\frac{2hc^2}{\lambda^5}
\left[
\exp\left(
\frac{hc}{\lambda k_BT}
\right)-1
\right]^{-1}.
}
\]

Units:

\[
\mathrm{W\,m^{-2}\,sr^{-1}\,m^{-1}}.
\]

Use stable numerical forms:

```text
expm1 for the denominator
large-exponent guard
positive wavelength and temperature validation
```

## 5. Axisymmetric viewing geometry

Let the plume axis be \(x\). Let \(\alpha\) be the angle from the plume axis to
the line of sight.

Line-of-sight unit vector:

\[
\hat{\mathbf d}
=
\begin{bmatrix}
\cos\alpha\\
\sin\alpha\\
0
\end{bmatrix}.
\]

Image-plane basis:

\[
\hat{\mathbf e}_u
=
\begin{bmatrix}
-\sin\alpha\\
\cos\alpha\\
0
\end{bmatrix},
\qquad
\hat{\mathbf e}_v
=
\begin{bmatrix}
0\\
0\\
1
\end{bmatrix}.
\]

A ray through image coordinate \((u,v)\) is:

\[
\boxed{
\mathbf r(s)
=
u\hat{\mathbf e}_u
+
v\hat{\mathbf e}_v
+
s\hat{\mathbf d}.
}
\]

Its axial position is:

\[
\boxed{
x(s)
=
-u\sin\alpha+s\cos\alpha.
}
\]

Its cylindrical radius is:

\[
\boxed{
r(s)
=
\sqrt{
\left(u\cos\alpha+s\sin\alpha\right)^2+v^2
}.
}
\]

This mapping samples any axisymmetric field \(\phi(x,r)\) along the ray.

## 6. Ray-domain construction

For a gridded field:

1. Determine the ray interval intersecting the field bounding box.
2. Find crossings of axial and radial cell boundaries.
3. Sort all crossing parameters \(s\).
4. Form nonoverlapping ordered segments.
5. Sample or volume-average each segment.
6. March from background toward the sensor.

For revolved polygon zones:

1. Represent each 2D \((x,r)\) polygon as an axisymmetric volume.
2. Solve ray-volume intersections.
3. Produce ordered path-length segments.
4. Reject overlapping volume ownership unless a documented priority exists.

Every segment shall contain:

```text
s_start_m
s_end_m
path_length_m
cell_id
temperature_K
pressure_Pa
species_mole_fractions
velocity_xyz_mps
absorption_coefficient_spectrum_per_m
```

## 7. Radiative-transfer equation

For local thermodynamic equilibrium, absorption/emission, and no scattering:

\[
\boxed{
\frac{dI_\lambda}{ds}
=
-\alpha_\lambda I_\lambda
+
\alpha_\lambda B_\lambda(T).
}
\]

Define optical depth:

\[
\boxed{
d\tau_\lambda=\alpha_\lambda ds.
}
\]

For a uniform segment \(i\),

\[
\Delta\tau_{\lambda,i}
=
\alpha_{\lambda,i}\Delta s_i.
\]

The exact segment update is:

\[
\boxed{
I_{\lambda,i+1}
=
I_{\lambda,i}
e^{-\Delta\tau_{\lambda,i}}
+
B_\lambda(T_i)
\left(
1-e^{-\Delta\tau_{\lambda,i}}
\right).
}
\]

Use a stable implementation for small optical depth:

```text
one_minus_transmittance = -expm1(-tau)
```

Then:

```text
I_out = I_in * exp(-tau) + B * one_minus_transmittance
```

## 8. Boundary and background radiance

The initial radiance may represent:

```text
cold space
sky
terrain
vehicle/nozzle surface
user-supplied image background
```

Use:

```text
BackgroundRadianceModel
```

with explicit spectral units.

A plume ray that intersects an opaque vehicle surface terminates at that
surface and uses the surface-emission/reflection boundary condition.

## 9. Gray-gas model

For constant gray absorption \(\alpha_g\),

\[
\alpha_\lambda=\alpha_g.
\]

This model is intentionally unphysical spectrally but is ideal for validating:

- ray lengths;
- segment ordering;
- optical-depth integration;
- angular behavior;
- image integration.

## 10. Molecular absorption

Use wavenumber or wavelength consistently. In a wavenumber implementation:

\[
\boxed{
\alpha_{\tilde\nu}
=
\sum_s
n_s
\sigma_s(\tilde\nu,T,p,\mathbf X).
}
\]

For species mole fraction \(X_s\),

\[
\boxed{
n_s=X_s\frac{p}{k_BT}.
}
\]

Line-by-line form:

\[
\boxed{
\sigma_s(\tilde\nu,T,p)
=
\sum_{\ell\in s}
S_{s\ell}(T)
f_{s\ell}(\tilde\nu;T,p).
}
\]

Where:

- \(S_{s\ell}\) is line intensity;
- \(f_{s\ell}\) is a normalized line profile;
- the first implementation uses a Voigt profile;
- pressure and Doppler broadening are included;
- line mixing and continuum terms are deferred unless a selected band requires
  them.

## 11. Cross-section generation architecture

Do not evaluate every spectroscopic line inside every ray segment.

Use an offline or cached table:

\[
\sigma_s(\tilde\nu,T_i,p_j).
\]

Recommended workflow:

```text
1. Select species and spectral windows.
2. Generate reference cross sections from HITEMP/HAPI.
3. Store versioned tables with source metadata.
4. Interpolate in log-pressure and temperature.
5. Multiply by local species number density during ray tracing.
```

Cross-section artifact metadata:

```text
species
isotopologue_policy
spectral_grid
temperature_grid
pressure_grid
line_database_version
line_shape_model
wing_cutoff
partition_function_source
generation_code_version
```

## 12. Velocity and Doppler shift

For line-of-sight velocity:

\[
\boxed{
v_{\mathrm{LOS}}
=
\mathbf u\cdot\hat{\mathbf d}.
}
\]

At first order:

\[
\frac{\Delta\tilde\nu}{\tilde\nu_0}
\approx
-\frac{v_{\mathrm{LOS}}}{c}.
\]

Doppler shifting can be deferred for broadband sensor results but should remain
in the data contract for high-resolution spectra.

## 13. Image and angular outputs

### Spectral radiance image

\[
\boxed{
I_\lambda(u,v;\alpha)
}
\]

with units:

\[
\mathrm{W\,m^{-2}\,sr^{-1}\,m^{-1}}.
\]

### Spectral radiant intensity

Integrate over projected source area:

\[
\boxed{
J_\lambda(\alpha)
=
\int_{A_\perp}
I_\lambda(u,v;\alpha)\,du\,dv.
}
\]

Units:

\[
\mathrm{W\,sr^{-1}\,m^{-1}}.
\]

### Far-field spectral irradiance

At range \(R\):

\[
\boxed{
E_{\lambda,\mathrm{source}}
=
\frac{J_\lambda}{R^2}.
}
\]

### Atmospheric propagation

\[
\boxed{
E_{\lambda,\mathrm{sensor}}
=
\tau_{\lambda,\mathrm{atm}}(R)
\frac{J_\lambda}{R^2}
+
E_{\lambda,\mathrm{path}}.
}
\]

### Sensor-band signal

For normalized or calibrated detector response \(R_b(\lambda)\),

\[
\boxed{
S_b
=
\int
R_b(\lambda)
E_{\lambda,\mathrm{sensor}}
\,d\lambda.
}
\]

The sensor model must state whether \(S_b\) is radiometric power, photoelectron
rate, digital counts, or a normalized response.

## 14. Aspect-angle physics

Viewing angle enters through:

- ray path lengths;
- hot-core/cool-shear-layer ordering;
- self-absorption;
- vehicle/nozzle occlusion;
- finite field of view;
- non-axisymmetric structure;
- atmospheric path;
- line-of-sight velocity.

Important verification result:

> For a fully visible, optically thin, axisymmetric volume with isotropic
> emission, integrated unresolved emission should be nearly angle independent.

Strong angle dependence in that limit indicates a geometry or integration
error. Projected area and chord length should compensate in the volume
integral.

## 15. IR-domain termination

Shock-cell termination is not radiation termination.

For axial slice \(k\), compute its incremental band radiant intensity:

\[
\Delta J_{b,k}.
\]

Define:

\[
\boxed{
r_{\mathrm{IR},k}
=
\frac{
|\Delta J_{b,k}|
}{
\max\left(
\sum_{i\le k}|\Delta J_{b,i}|,
J_{\mathrm{floor}}
\right)
}.
}
\]

Terminate the radiation domain when:

\[
r_{\mathrm{IR},k}<\epsilon_{\mathrm{IR}}
\]

for a configured number of consecutive slices and for all required view
angles/bands.

Report:

```text
ir_domain_end_x_m
ir_termination_band
ir_termination_angles
incremental_contribution_ratios
```

## 16. Data contracts

### SpectralGrid

```text
coordinate_kind
values
units
spacing_kind
```

### RaySegment

```text
ray_id
segment_index
s_start_m
s_end_m
path_length_m
cell_id
thermodynamic_state
composition
velocity_xyz_mps
```

### RadianceImage

```text
view_angle_rad
u_grid_m
v_grid_m
spectral_grid
radiance
background_model_id
```

### AngularSignature

```text
view_angles_rad
spectral_grid
spectral_radiant_intensity
band_radiant_intensity
```

### SensorSignature

```text
range_m
view_angles_rad
atmospheric_path_id
sensor_response_id
spectral_irradiance
band_signal
```

## 17. Performance plan

- Vectorize spectral calculations over rays or segments where memory permits.
- Cache Planck radiance by unique \(T\) grid.
- Cache cross-section interpolation by quantized \(T,p\).
- Chunk spectral grids to bound memory.
- Use NumPy first.
- Add Numba, JAX, or compiled kernels only after profiling and numerical
  equivalence tests.
- Preserve a slow, transparent reference implementation.

## 18. Verification matrix

### Planck

- Wien peak shifts correctly with temperature.
- Stefan-Boltzmann integral agrees after appropriate angular integration.
- Spectral-coordinate conversion preserves integrated radiance.

### Homogeneous slab

For background \(I_0\), constant \(T,\alpha,L\):

\[
I_{\mathrm{out}}
=
I_0e^{-\alpha L}
+
B(T)(1-e^{-\alpha L}).
\]

The numerical solver must match this exactly within floating-point tolerance.

### Limiting behavior

- \(\alpha L=0\): output equals background.
- \(\alpha L\ll1\): excess radiance is linear in \(\alpha L\).
- \(\alpha L\gg1\): output approaches \(B(T)\).

### Layer ordering

A hot layer behind a cold absorbing layer must differ from the reverse order.

### Ray geometry

- Analytic chord through a cylinder.
- Analytic chord through a sphere test object.
- Tangent ray has zero path length within tolerance.
- Rotational symmetry across image azimuth.

### Angular integral

Optically thin integrated radiant intensity is nearly angle independent for a
fully visible axisymmetric test field.

### Spectroscopy

- Cached cross section reproduces the reference generator at grid nodes.
- Interpolation error is bounded at withheld \(T,p\) points.
- Mixture optical depth equals the sum of species optical depths.

## 19. Validation gate

Validation should progress from:

```text
analytic slab
synthetic axisymmetric field
heated nonreacting plume with measured T and p
measured spectral or band images
rocket-relevant plume
```

Do not use a complex rocket image as the first radiation debugging case.

## 20. Acceptance gate

Phase 4/5 is complete only when:

- analytic slab and ray-geometry cases pass;
- spectral units are unambiguous;
- segment order is correct;
- optically thin angular behavior is correct;
- cross-section tables are versioned and reproducible;
- atmospheric and sensor effects are separable from intrinsic plume radiance;
- IR-domain termination is separate from shock-train termination;
- a slow reference implementation remains available.

<!-- END 06_spectral_ir_plan.md -->


---

<!-- BEGIN 07_thermochemistry_and_particles_plan.md -->

# Thermochemistry and Particle-Radiation Plan

## 1. Purpose

Replace the constant-\(\gamma\), dry-air-like approximation with staged
rocket-exhaust composition, thermodynamics, reactions, and particles.

This work begins only after gas dynamics, mixing, and molecular radiative
transfer pass their own verification gates.

## 2. Fidelity stages

### CHEM-0: Explicit frozen mixture

- User-supplied species.
- Explicit molecular weights.
- Constant or tabulated \(c_p(T)\).
- No reactions.

### CHEM-1: CEA boundary-state import

- Chamber/nozzle composition from an external CEA run.
- Frozen or equilibrium nozzle expansion metadata.
- No CEA invocation in the base solver.

### CHEM-2: Thermally perfect frozen flow

- \(h(T,\mathbf Y)\), \(c_p(T,\mathbf Y)\), \(R(\mathbf Y)\).
- Variable \(\gamma(T,\mathbf Y)\).
- Frozen species through shocks and expansions.

### CHEM-3: Equilibrium mixing model

- Equilibrium composition at selected \(p,h,\) and elemental abundance.
- Useful as a limiting model.

### CHEM-4: Finite-rate afterburning

- Reaction kinetics.
- Ambient oxygen entrainment.
- Chemical heat release.
- Species-dependent transport.

### CHEM-5: Soot and condensed particles

- Particle mass and size distributions.
- Particle temperature.
- Absorption, emission, and scattering.

## 3. Composition conversions

For mole fractions \(X_s\), mass fractions \(Y_s\), and molecular weights
\(W_s\):

\[
\boxed{
\overline W
=
\sum_sX_sW_s
=
\left(
\sum_s\frac{Y_s}{W_s}
\right)^{-1}.
}
\]

Convert mole to mass fraction:

\[
\boxed{
Y_s=\frac{X_sW_s}{\overline W}.
}
\]

Convert mass to mole fraction:

\[
\boxed{
X_s=\frac{Y_s/W_s}
{\sum_jY_j/W_j}.
}
\]

Mixture gas constant:

\[
\boxed{
R=\frac{R_u}{\overline W}.
}
\]

All conversions require normalization and nonnegative composition.

## 4. Thermally perfect mixture

For species enthalpy \(h_s(T)\):

\[
\boxed{
h(T,\mathbf Y)=\sum_sY_sh_s(T).
}
\]

Mixture heat capacity:

\[
\boxed{
c_p(T,\mathbf Y)
=
\sum_sY_sc_{p,s}(T).
}
\]

Then:

\[
\boxed{
c_v=c_p-R,
\qquad
\gamma=\frac{c_p}{c_v}.
}
\]

For a variable-\(c_p\) state, temperature is recovered by solving:

\[
h(T,\mathbf Y)-h_{\mathrm{target}}=0.
\]

Use a bounded scalar root solver with a documented valid temperature range.

## 5. Frozen expansions and shocks

Frozen means:

\[
\boxed{
\frac{DY_s}{Dt}=0.
}
\]

The simple constant-\(\gamma\) formulas are no longer exact when \(c_p\) varies
strongly. The thermally perfect extension should conserve:

### Expansion

\[
h_0=h+\frac{u^2}{2}
\]

and entropy for an isentropic expansion:

\[
s_2=s_1.
\]

### Adiabatic shock

Mass:

\[
\boxed{
\rho_1u_{n1}=\rho_2u_{n2}.
}
\]

Normal momentum:

\[
\boxed{
p_1+\rho_1u_{n1}^2
=
p_2+\rho_2u_{n2}^2.
}
\]

Total enthalpy:

\[
\boxed{
h_1+\frac{u_1^2}{2}
=
h_2+\frac{u_2^2}{2}.
}
\]

Tangential velocity is unchanged for an inviscid oblique shock.

Implement the variable-property shock as a nonlinear conservation solve after
the constant-\(\gamma\) model is stable.

## 6. CEA boundary-state adapter

Treat CEA as a boundary-condition generator.

### Input metadata

```text
propellant names
oxidizer/fuel ratio
chamber pressure
chamber temperature or enthalpy assumptions
nozzle area ratio
equilibrium/frozen expansion option
CEA version
thermodynamic database version
```

### Imported outputs

```text
exit pressure
exit temperature
exit Mach
exit velocity
mass flow or characteristic velocity data
species mole fractions
species mass fractions
molecular weight
cp
gamma
enthalpy
entropy
```

### Adapter requirements

- Parse versioned machine-readable output.
- Preserve all original CEA metadata.
- Validate mass-fraction and elemental closure.
- Convert units explicitly.
- Store the raw CEA result as provenance.
- Do not silently collapse trace species required by the selected spectral
  windows.

## 7. Chemical equilibrium

At fixed temperature and pressure, equilibrium minimizes Gibbs free energy:

\[
\boxed{
\min_{\{n_s\ge0\}}
G
=
\sum_sn_s\mu_s.
}
\]

Subject to elemental conservation:

\[
\boxed{
\sum_sa_{ks}n_s=b_k
\quad
\text{for each element }k.
}
\]

For ideal-gas species:

\[
\boxed{
\mu_s
=
\mu_s^\circ(T)
+
R_uT
\ln
\left(
\frac{X_sp}{p^\circ}
\right).
}
\]

In an adiabatic mixing problem, temperature must also satisfy the total
enthalpy constraint.

The project should initially use a trusted equilibrium library rather than
implementing a new Gibbs minimizer.

## 8. Finite-rate chemistry

Species equation:

\[
\boxed{
\frac{\partial(\rho Y_s)}{\partial t}
+
\nabla\cdot(\rho\mathbf uY_s)
=
\nabla\cdot(\rho D_s\nabla Y_s)
+
\dot\omega_s.
}
\]

For reaction \(r\):

\[
\sum_s\nu'_{sr}\mathcal S_s
\rightleftharpoons
\sum_s\nu''_{sr}\mathcal S_s.
\]

Forward Arrhenius rate:

\[
\boxed{
k_{f,r}
=
A_rT^{b_r}
\exp
\left(
-\frac{E_{a,r}}{R_uT}
\right).
}
\]

Progress rate:

\[
\boxed{
q_r
=
k_{f,r}
\prod_jC_j^{\nu'_{jr}}
-
k_{r,r}
\prod_jC_j^{\nu''_{jr}}.
}
\]

Species source:

\[
\boxed{
\dot\omega_s
=
W_s
\sum_r
(\nu''_{sr}-\nu'_{sr})q_r.
}
\]

Chemical heat release:

\[
\boxed{
\dot q_{\mathrm{chem}}
=
-\sum_sh_s(T)\dot\omega_s.
}
\]

Use Cantera or an equivalent validated kinetics library. Do not hand-code a
reaction mechanism inside the plume solver.

## 9. Frozen/equilibrium/finite-rate classifier

Define flow time:

\[
\boxed{
\tau_{\mathrm{flow}}=\frac{L}{u}.
}
\]

Define a selected chemical time \(\tau_{\mathrm{chem}}\). Then:

\[
\boxed{
Da=\frac{\tau_{\mathrm{flow}}}{\tau_{\mathrm{chem}}}.
}
\]

Interpretation:

```text
Da << 1  approximately frozen
Da >> 1  approximately equilibrium-limited
Da ~ 1   finite-rate model needed
```

This is a diagnostic, not an automatic guarantee.

## 10. Coupling finite-rate chemistry to the integral plume

Extend the species equation:

\[
\boxed{
\frac{d(\dot mY_s)}{dx}
=
Y_{s,a}\frac{d\dot m}{dx}
+
\dot\omega_sA.
}
\]

Here \(\dot\omega_s\) is the standard volumetric species mass-production rate
with units \(\mathrm{kg\,m^{-3}\,s^{-1}}\). Multiplication by cross-sectional
area gives the required source per unit axial length. Do not divide by velocity
unless the chemistry interface instead supplies a material derivative such as
\(dY_s/dt\); that alternative convention must have a different typed contract.

Extend total enthalpy consistently. If species sensible and formation
enthalpies are included in \(h(T,\mathbf Y)\), chemical energy should not be
double-counted as an additional arbitrary heat source. Choose one consistent
energy formulation and document it.

## 11. Particle state

For particle class \(k\):

```text
material
diameter_m
number_density_per_m3
mass_fraction
temperature_K
velocity_mps
complex_refractive_index_model
```

### Particle momentum

A reduced model may use drag relaxation:

\[
m_p\frac{du_p}{dt}
=
\frac12
C_D\rho_gA_p
|u_g-u_p|(u_g-u_p).
\]

### Particle energy

\[
\boxed{
m_pc_{p,p}\frac{dT_p}{dt}
=
h_cA_p(T_g-T_p)
-
\epsilon_p\sigma A_p
(T_p^4-T_{\mathrm{rad}}^4)
+
\dot q_{p,\mathrm{chem}}.
}
\]

Particle temperature need not equal gas temperature.

## 12. Particle optical properties

For particle size distribution \(N(d_p)\):

\[
\boxed{
\alpha_{\lambda,\mathrm{part}}
=
\int
N(d_p)
C_{\mathrm{abs}}(\lambda,d_p,m_\lambda)
\,dd_p.
}
\]

Scattering coefficient:

\[
\boxed{
\sigma_{\lambda,\mathrm{sca}}
=
\int
N(d_p)
C_{\mathrm{sca}}(\lambda,d_p,m_\lambda)
\,dd_p.
}
\]

Extinction:

\[
\boxed{
\beta_{\lambda,\mathrm{ext}}
=
\alpha_{\lambda,\mathrm{part}}
+
\sigma_{\lambda,\mathrm{sca}}.
}
\]

The no-scattering molecular RTE is no longer sufficient once particle
scattering matters. Add the scattering source only in a separate solver level.

## 13. Data contracts

### SpeciesDefinition

```text
name
molecular_weight_kgpmol
elemental_composition
thermo_model_id
spectroscopy_id | None
```

### MixtureState

```text
temperature_K
pressure_Pa
density_kgpm3
species_mass_fractions
species_mole_fractions
molecular_weight_kgpmol
specific_gas_constant_JpkgK
cp_JpkgK
gamma
specific_enthalpy_Jpkg
specific_entropy_JpkgK
```

### ChemistryModelMetadata

```text
kind
mechanism_name
mechanism_version
thermo_database_version
transport_model
valid_temperature_range_K
valid_pressure_range_Pa
```

### ParticlePopulation

```text
classes
total_mass_fraction
total_number_density
optical_model_id
```

## 14. Verification tests

### Composition

- \(X\to Y\to X\) round trip.
- \(Y\to X\to Y\) round trip.
- mixture molecular weight agrees by both forms.
- mass and mole fractions normalize.

### Thermodynamics

- \(dh/dT=c_p\) numerically.
- enthalpy inversion returns the original temperature.
- \(c_p-c_v=R\).
- \(\gamma=c_p/c_v\).

### Frozen shock/expansion

- species unchanged.
- mass, momentum, and total enthalpy conserved.
- entropy increases across shocks.
- entropy remains constant through isentropic expansion.

### Equilibrium

- elemental abundances conserved.
- Gibbs energy does not increase from the initial feasible composition.
- reference CEA/Cantera equilibrium cases are reproduced.

### Finite rate

- elemental source sums are zero:
  \[
  \sum_s\frac{a_{ks}}{W_s}\dot\omega_s=0.
  \]
- species remain nonnegative.
- total mass source sums to zero.
- disabling rates recovers frozen behavior.

### Particles

- zero particle concentration recovers molecular radiation.
- optically thin extinction is linear in number density.
- particle energy converges to gas temperature when convection dominates.
- radiation-dominated cooling follows the expected sign.

## 15. Validation strategy

Use a hierarchy:

```text
library reference thermodynamics
CEA nozzle cases
Cantera homogeneous reactor cases
nonreacting heated plume
reacting laboratory jet
propellant-specific plume
particle-bearing plume
```

Do not calibrate particle emissivity to compensate for an incorrect gas
temperature or composition field.

## 16. Acceptance gate

Thermochemistry is accepted only when:

- all composition and elemental balances close;
- CEA provenance is preserved;
- frozen and equilibrium limits reproduce references;
- finite-rate energy is not double-counted;
- radiation uses species number density from the same mixture state;
- particle and gas temperatures remain separate where required;
- every mechanism and optical model has a version and validity range.

<!-- END 07_thermochemistry_and_particles_plan.md -->


---

<!-- BEGIN 08_validation_and_test_matrix.md -->

# Validation and Test Matrix

## 1. Purpose

Define what must be tested, what constitutes verification versus validation,
and which numerical values serve as branch regression anchors.

A test passing does not imply the model is valid outside the test's assumptions.

## 2. Evidence hierarchy

### Level V0: Input and unit verification

Checks types, units, ranges, and conversions.

### Level V1: Algebraic unit tests

Checks one equation in isolation against analytic values.

### Level V2: Conservation verification

Checks mass, momentum, energy, entropy, and species balances.

### Level V3: Numerical solution verification

Checks convergence, residuals, conditioning, and discretization sensitivity.

### Level V4: Model validation

Compares calculated observables to independent experiment or trusted
higher-fidelity calculation.

### Level V5: Uncertainty characterization

Propagates input, calibration, and numerical uncertainty into final outputs.

No phase may claim V4 validation when it only has V1-V3 tests.

## 3. Common normalized residuals

Pressure:

\[
r_p=\frac{p_{\mathrm{calc}}-p_{\mathrm{ref}}}
{\max(|p_{\mathrm{ref}}|,p_{\mathrm{floor}})}.
\]

Temperature:

\[
r_T=\frac{T_{\mathrm{calc}}-T_{\mathrm{ref}}}
{\max(|T_{\mathrm{ref}}|,T_{\mathrm{floor}})}.
\]

Mass flux across a shock:

\[
r_m
=
\frac{
\rho_1u_{n1}-\rho_2u_{n2}
}{
\max(
|\rho_1u_{n1}|,
|\rho_2u_{n2}|,
m_{\mathrm{floor}}
)
}.
\]

Normal momentum:

\[
r_\Pi
=
\frac{
p_1+\rho_1u_{n1}^2
-
p_2-\rho_2u_{n2}^2
}{
\max(
|p_1+\rho_1u_{n1}^2|,
|p_2+\rho_2u_{n2}^2|
)
}.
\]

Total enthalpy:

\[
r_h
=
\frac{
h_{01}-h_{02}
}{
\max(|h_{01}|,|h_{02}|,h_{\mathrm{floor}})
}.
\]

Geometry intersection:

\[
r_x
=
\frac{
\left\|
\mathbf o_1+s_1\mathbf d_1
-
\mathbf o_2-s_2\mathbf d_2
\right\|
}{
D_e
}.
\]

## 4. Foundation test cases

| ID | Test | Inputs | Expected |
|---|---|---|---|
| GAS-001 | Ideal-gas density | chosen \(p,T,R\) | \(\rho=p/(RT)\) |
| GAS-002 | Mixture molecular weight | binary mixture | both formulas agree |
| GAS-003 | Sound speed | chosen \(T,R,\gamma\) | \(a=\sqrt{\gamma RT}\) |
| ISO-001 | Static/total round trip | grid of \(M,\gamma\) | original state recovered |
| NOZ-001 | Area-Mach inversion | \(A/A^*,\gamma\) | selected branch recovered |
| NOZ-002 | Choked mass-flow inversion | \(A^*,p_0,T_0,R,\gamma\) | forward/inverse agree |
| REG-001 | Overexpanded classifier | \(p_e/p_a=0.90\) | OVEREXPANDED |
| REG-002 | Matched classifier | \(p_e/p_a=1.00\) | MATCHED, zero cells |
| REG-003 | Underexpanded classifier | \(p_e/p_a=1.10\) | UNDEREXPANDED |
| GEO-001 | Perpendicular ray intersection | analytic rays | exact point, positive parameters |
| GEO-002 | Parallel rays | parallel directions | structured failure |
| GEO-003 | Backward intersection | lines cross behind origin | structured failure |

## 5. Normal-shock benchmark

Use:

\[
M_1=2.0,
\qquad
\gamma=1.4.
\]

Expected:

\[
\boxed{
\frac{p_2}{p_1}=4.5
}
\]

\[
\boxed{
\frac{\rho_2}{\rho_1}=2.6666666667
}
\]

\[
\boxed{
\frac{T_2}{T_1}=1.6875
}
\]

\[
\boxed{
M_2=0.5773502692
}
\]

\[
\boxed{
\frac{p_{02}}{p_{01}}\approx0.7208738615.
}
\]

Verify mass, momentum, total enthalpy, and entropy sign.

## 6. Oblique-shock benchmark

Use:

\[
M_1=2.0,
\qquad
\gamma=1.4,
\qquad
\theta=10^\circ.
\]

Weak solution:

\[
\boxed{
\beta_{\mathrm{weak}}
\approx39.313931845^\circ
}
\]

Strong solution:

\[
\boxed{
\beta_{\mathrm{strong}}
\approx83.700080376^\circ.
}
\]

For the weak solution:

\[
M_{n1}\approx1.267138036,
\]

\[
\frac{p_2}{p_1}\approx1.706578604,
\]

\[
\frac{\rho_2}{\rho_1}\approx1.458425613,
\]

\[
\frac{T_2}{T_1}\approx1.170151284,
\]

\[
M_2\approx1.640522229,
\]

\[
\frac{p_{02}}{p_{01}}\approx0.984644023.
\]

Also verify:

\[
\theta\to0
\Rightarrow
\beta_{\mathrm{weak}}\to\sin^{-1}(1/M).
\]

## 7. Current-branch regression anchor

Use:

\[
M_e=4.13,
\qquad
\gamma=1.33,
\qquad
p_0=69\ \mathrm{atm},
\qquad
T_0=2000\ \mathrm K.
\]

Expected isentropic exit values:

\[
1+\frac{\gamma-1}{2}M_e^2
=
3.8143885,
\]

\[
\frac{p_0}{p_e}
=
220.454330636,
\]

\[
p_e
=
0.312989996\ \mathrm{atm},
\]

\[
T_e
=
524.330440\ \mathrm K.
\]

Consequences:

```text
at sea level: overexpanded
at branch 10 km atmosphere (~26436.27 Pa): mildly underexpanded
```

Any test named “underexpanded” at sea level with this total state is mislabeled.

## 8. Prandtl-Meyer tests

| ID | Test | Expected |
|---|---|---|
| PM-001 | \(\nu(M)\) monotonic for \(M>1\) | strictly increasing |
| PM-002 | inverse round trip | \(M\) recovered |
| PM-003 | turn sign | expansion increases \(M\), lowers \(p,T,\rho\) |
| PM-004 | stagnation invariance | \(p_0,T_0\) constant |
| PM-005 | infinite-Mach bound | requested \(\nu\) above limit fails |

## 9. First-cell solution verification

### MOC-001: Matched flow

Expected:

```text
zero cells
NO_PRESSURE_MISMATCH
no shock or expansion segments
```

### MOC-002: Mild underexpansion

Use a target exit-pressure ratio such as:

\[
p_e/p_a=1.10.
\]

Check:

```text
finite characteristic network
boundary pressure equals ambient
centerline theta equals zero
closed positive-area zones
no backward intersections
```

### MOC-003: Mild overexpansion

Use:

\[
p_e/p_a=0.90
\]

and a validated uniform exit state. Check attached weak shock and conservation.

### MOC-004: Detached case

Select \(M,\theta\) above \(\theta_{\max}\). Expected:

```text
DETACHED_SHOCK_REQUIRED
no nominal success geometry
```

### MOC-005: Fan-resolution convergence

Run:

```text
N
2N
4N
```

Track:

```text
cell length
maximum radius
centerline pressure extrema
boundary pressure residual
```

Require decreasing changes.

## 10. First-cell scale correlation

For the branch 10 km illustrative state:

\[
p_a\approx26436.2673\ \mathrm{Pa}.
\]

Expected fully expanded values:

\[
M_j\approx4.257327980,
\]

\[
A_j/A_e\approx1.137766918,
\]

\[
D_j\approx2.133323152\ \mathrm m
\]

for \(D_e=2\ \mathrm m\).

Classical spacing anchor:

\[
L_{s,\mathrm{corr}}
\approx11.52956984\ \mathrm m.
\]

The solver is not required to equal the correlation, but the normalized
difference must be reported and investigated.

## 11. Shock-train tests

| ID | Change | Expected response |
|---|---|---|
| TRN-001 | \(S_i=0\) | no geometric core shrinkage |
| TRN-002 | increase \(S_i\) | shorter core and fewer cells |
| TRN-003 | \(C_d=0\) | no amplitude decay from closure |
| TRN-004 | increase \(C_d\) | fewer coherent cells |
| TRN-005 | increase `max_cells` only | physical result unchanged unless previously truncated |
| TRN-006 | hit `max_cells` | MAX_CELL_LIMIT, truncated |
| TRN-007 | hit axial domain | DOMAIN_LIMIT, truncated |
| TRN-008 | weak amplitude for one cell | no stop unless persistence satisfied |
| TRN-009 | \(p_e/p_a\to1\) | zero or vanishing shock train |

## 12. Integral-plume tests

### MIX-001: Zero entrainment

Set \(E=0\). Expected constant:

```text
mass flow
velocity
temperature
radius
species
```

### MIX-002: Frozen entrainment

Verify:

\[
\frac{d(\dot mY_s)}{dx}
=
Y_{s,a}\frac{d\dot m}{dx}.
\]

### MIX-003: Momentum conservation

For pressure-matched, force-free flow:

\[
\Pi(x)=\Pi_0.
\]

### MIX-004: Enthalpy balance

\[
\dot H_0(x)
=
\dot H_{0,0}
+
\int h_{0a}\,d\dot m.
\]

### MIX-005: Equilibrium event

Verify velocity, temperature, and composition tolerances plus persistence.

## 13. Radiation analytic tests

### RAD-001: Homogeneous slab

\[
I_{\mathrm{out}}
=
I_0e^{-\alpha L}
+
B(T)(1-e^{-\alpha L}).
\]

Require direct agreement.

### RAD-002: Zero opacity

\[
\alpha=0
\Rightarrow
I_{\mathrm{out}}=I_0.
\]

### RAD-003: Optically thin

For \(\tau\ll1\):

\[
I_{\mathrm{out}}-I_0
\approx
[B(T)-I_0]\tau.
\]

### RAD-004: Optically thick

\[
\tau\gg1
\Rightarrow
I_{\mathrm{out}}\to B(T).
\]

### RAD-005: Layer ordering

Hot-behind-cold differs from cold-behind-hot.

### RAD-006: Cylinder chord

For cylinder radius \(R\) and impact parameter \(b\):

\[
L=2\sqrt{R^2-b^2}.
\]

### RAD-007: Optically thin angular invariance

Integrated radiant intensity of a fully visible axisymmetric test volume is
nearly independent of angle.

### RAD-008: Spectral-coordinate conversion

Integrated radiance is preserved between wavelength and wavenumber
representations.

## 14. Spectroscopy tests

| ID | Test | Expected |
|---|---|---|
| SPC-001 | cross-section table at grid node | matches generator |
| SPC-002 | withheld \(T,p\) interpolation | bounded error |
| SPC-003 | mixture opacity | species sum |
| SPC-004 | column-density scaling | linear optical depth |
| SPC-005 | table metadata | version and line-shape reproducible |
| SPC-006 | narrow-window line-by-line case | agrees with HAPI reference |

## 15. Chemistry tests

| ID | Test | Expected |
|---|---|---|
| CHM-001 | \(X\leftrightarrow Y\) round trip | original composition |
| CHM-002 | elemental closure | conserved |
| CHM-003 | enthalpy inversion | original \(T\) |
| CHM-004 | frozen shock | unchanged species |
| CHM-005 | equilibrium reference | matches CEA/Cantera |
| CHM-006 | disabled kinetics | frozen behavior |
| CHM-007 | finite-rate element sources | sum to zero |
| CHM-008 | no particles | molecular radiation recovered |

## 16. External validation families

Use independent cases with archived raw inputs and processed comparison data.

### Flow structure

- Underexpanded supersonic round-jet schlieren or PLIF cases.
- Cases reporting exit Mach, pressure ratio, geometry, and centerline pressure.
- Separate calibration and validation subsets.

### First-cell and Mach-disk geometry

- Datasets reporting cell wavelength, maximum jet diameter, Mach-disk
  location, and Mach-disk diameter.
- Mach-disk data may initially validate an out-of-scope classifier rather than
  the attached-cell solver.

### Infrared plume

- Axisymmetric heated-plume cases with measured temperature/pressure fields and
  infrared images.
- Use these before a reacting rocket plume.

### Thermochemistry

- Published CEA example problems.
- Cantera equilibrium and homogeneous-reactor references.
- Propellant-specific data only after generic verification.

## 17. Regression artifact policy

Store regression values with:

```text
case_id
input schema version
solver version
model level
calibration id
expected values
tolerances
source provenance
```

Do not update expected values merely because an implementation changed.
Document the physical or mathematical reason.

## 18. Quality commands

```bash
python -m pytest
python -m pytest --maxfail=1 -q
python -m ruff check .
python -m pyright
python -m build
```

Recommended later additions:

```text
coverage report
property-based tests
benchmark timing
wheel-installed smoke tests
```

## 19. Phase-exit rule

A phase exits only when:

1. Its analytic verification cases pass.
2. Its conservation residuals pass.
3. Its discretization sensitivity is documented.
4. Its validity range is encoded.
5. Its failure states are tested.
6. Its calibration and validation data are distinct where empirical closures
   exist.

<!-- END 08_validation_and_test_matrix.md -->


---

<!-- BEGIN 09_issue_backlog.md -->

# Dependency-Ordered Issue Backlog

## 1. Use

Each item below is intended to become one focused issue and usually one pull
request. Do not combine unrelated physics, architecture, and formatting work.

Priority:

```text
P0 blocking correctness
P1 required model capability
P2 calibration or performance
P3 later fidelity
```

## 2. Phase 0 — Foundation corrections

## FND-001 — Introduce gas and nozzle contracts

**Priority:** P0  
**Depends on:** none

### Scope

Create:

```text
models/gas/contracts.py
models/nozzle/contracts.py
```

Implement frozen, validated contracts for:

```text
GasProperties
NozzleExitState
AmbientState
```

### Done when

- SI units and radians are documented.
- Gas constant and molecular weight consistency is checked.
- Species mass fractions normalize.
- Existing public APIs can construct the new contracts through wrappers.
- Tests cover invalid and valid data.

---

## FND-002 — Correct choked mass-flow and throat-area equations

**Priority:** P0  
**Depends on:** FND-001

### Scope

Correct:

\[
A^*
=
\frac{\dot m}{p_0}
\sqrt{\frac{RT_0}{\gamma}}
\left(
\frac{\gamma+1}{2}
\right)^{\frac{\gamma+1}{2(\gamma-1)}}.
\]

Add a forward mass-flow helper and inversion tests.

### Files

```text
models/plume/motor_parameters.py
models/nozzle/area_mach.py
tests/
```

### Done when

- Forward and inverse functions agree.
- The exponent regression test fails on the old implementation and passes on
  the new implementation.
- Public compatibility is preserved.

---

## FND-003 — Remove hidden dry-air assumptions

**Priority:** P0  
**Depends on:** FND-001

### Scope

Route explicit gas properties through all generic nozzle/plume calculations.

### Done when

- No generic plume path imports dry-air molecular weight.
- Density, sound speed, and velocity change consistently with gas molecular
  weight.
- Atmosphere code may still use explicit dry-air properties.

---

## FND-004 — Correct energy and enthalpy properties

**Priority:** P0  
**Depends on:** FND-001, FND-003

### Scope

Add precise properties:

```text
specific_gas_work_Jpkg
specific_static_enthalpy_Jpkg
specific_total_enthalpy_Jpkg
specific_total_energy_Jpkg
```

Deprecate ambiguous behavior.

### Done when

\[
h_0=h+u^2/2=c_pT_0
\]

passes across the test grid.

---

## FND-005 — Replace oblique-shock angle special cases

**Priority:** P0  
**Depends on:** none

### Scope

Implement bounded weak/strong branch roots for the
\(\theta\)-\(\beta\)-\(M\) equation.

### Done when

- Weak zero-turn limit equals Mach angle.
- Strong zero-turn limit equals \(\pi/2\).
- Residual and root bracket are reported.
- Existing closed-form routine may remain only as a checked optimization or
  reference.

---

## FND-006 — Add maximum attached-turn detection

**Priority:** P0  
**Depends on:** FND-005

### Scope

Calculate \(\theta_{\max}(M,\gamma)\) and return
`DETACHED_SHOCK_REQUIRED` when exceeded.

### Done when

- Below-limit case succeeds.
- Above-limit case fails structurally.
- No nominal state is returned after failure.

---

## FND-007 — Add explicit expansion-regime classification

**Priority:** P0  
**Depends on:** FND-001

### Scope

Add:

```text
UNDEREXPANDED
MATCHED
OVEREXPANDED
```

using:

\[
r_p=(p_e-p_a)/p_a.
\]

### Done when

- \(p_e/p_a=1\) returns zero cells.
- Tolerance is configurable.
- `max_cells=0` is valid.
- Tests use target exit-pressure ratios.

---

## FND-008 — Add forward ray-intersection result

**Priority:** P0  
**Depends on:** none

### Scope

Replace point-only pseudoinverse intersections with a diagnostic ray result.

### Done when

- Forward parameters, residual, and condition number are returned.
- Parallel, ill-conditioned, and backward cases fail explicitly.
- Geometry callers migrate to the new API.

---

## FND-009 — Correct overexpanded precursor intersection

**Priority:** P0  
**Depends on:** FND-005, FND-008

### Scope

Use:

\[
\Delta x=R/\tan\beta
\]

with radians and forward-ray validation.

### Done when

- \(45^\circ\) analytic case passes.
- Current degree/cosine behavior is covered by a regression test.

---

## FND-010 — Separate transitions from closed zones

**Priority:** P0  
**Depends on:** FND-008

### Scope

Introduce:

```text
FlowTransition
CharacteristicSegment
ShockSegment
ClosedZone
```

### Done when

- Public closed zones contain no `NaN`.
- Unclosed transitions cannot be meshed or ray traced.
- Existing consumers have a documented migration.

---

## FND-011 — Rename repeated plume passes to cells

**Priority:** P1  
**Depends on:** FND-007

### Scope

Migrate:

```text
num_plumes → max_cells
plume_index → cell_index
```

### Done when

- Deprecated aliases work with warnings.
- Supplying both forms fails clearly.
- New serialization uses cell terminology.

---

## FND-012 — Correct and expand branch regression tests

**Priority:** P0  
**Depends on:** FND-002 through FND-011 as applicable

### Scope

Add numeric anchors from `08_validation_and_test_matrix.md`.

### Done when

- The old sea-level “underexpanded” labeling is removed.
- Normal and oblique shock reference values pass.
- Matched/over/under regimes are separately tested.

---

## FND-013 — Establish Python 3.12 quality baseline

**Priority:** P1  
**Depends on:** all Phase 0 code tasks

### Scope

Update project configuration and CI for:

```text
Python 3.12+
pytest
ruff
pyright
build
```

### Done when

All quality commands pass in a clean environment and installed-wheel smoke
tests remain green.

## 3. Phase 1 — Validated first cell

## MOC-001 — Implement robust Prandtl-Meyer inverse

**Priority:** P1  
**Depends on:** Phase 0 gate

### Done when

- Monotonic bracketed inverse passes round-trip tests.
- Infinite-Mach angle limit is checked.
- Root diagnostics are exposed.

---

## MOC-002 — Add characteristic point and segment contracts

**Priority:** P1  
**Depends on:** MOC-001, FND-008

### Done when

- \(C^+\) and \(C^-\) invariants are explicit.
- Radians and SI units are enforced.
- Segments carry intersection diagnostics.

---

## MOC-003 — Implement planar characteristic interior point

**Priority:** P1  
**Depends on:** MOC-002

### Scope

Solve state compatibility and averaged-slope geometry at a \(C^+/C^-\)
intersection.

### Done when

- Invariants are conserved.
- Iteration converges on analytic/synthetic cases.
- Ill-conditioned geometry fails structurally.

---

## MOC-004 — Implement centerline compatibility

**Priority:** P1  
**Depends on:** MOC-003

### Scope

Apply \(\theta=0\) and incoming characteristic invariant.

### Done when

- Centerline angle residual passes.
- State reflection is physical, not only geometric.

---

## MOC-005 — Implement ambient-pressure free boundary

**Priority:** P1  
**Depends on:** MOC-003

### Scope

Solve:

```text
incoming characteristic invariant
p = p_ambient
boundary tangent = flow angle
```

### Done when

- Pressure and tangent residuals pass.
- No fitted parabola is required for the solved boundary.

---

## MOC-006 — Assemble mild underexpanded first cell

**Priority:** P1  
**Depends on:** MOC-004, MOC-005

### Done when

- One closed cell is produced.
- All zones are finite.
- Expansion and shock conservation checks pass.

---

## MOC-007 — Assemble mild attached overexpanded first cell

**Priority:** P1  
**Depends on:** MOC-005, FND-006, FND-009

### Done when

- Certified uniform exit required.
- Attached case succeeds.
- Detached and separation-risk cases fail with explicit status.

---

## MOC-008 — Add closed-zone topology validation

**Priority:** P1  
**Depends on:** MOC-006

### Done when

- Polygon area and orientation checked.
- Self-intersections rejected.
- Shared interfaces match within tolerance.

---

## MOC-009 — Add fan-resolution convergence study

**Priority:** P1  
**Depends on:** MOC-006, MOC-007

### Done when

Results for \(N,2N,4N\) report convergence of cell length, radius, pressure
extrema, and boundary residual.

---

## MOC-010 — Add fully expanded jet and spacing correlation

**Priority:** P1  
**Depends on:** FND-002, MOC-006

### Done when

- \(M_j,D_j,L_{s,\mathrm{corr}}\) are reported.
- Correlation mismatch is diagnostic, not forced.

## 4. Phase 2 — Finite shock train

## TRN-001 — Add shock-train calibration contract

**Priority:** P1  
**Depends on:** Phase 1 gate

### Done when

Every closure has provenance and applicability ranges.

---

## TRN-002 — Implement coherent-core diameter model

**Priority:** P1  
**Depends on:** TRN-001

### Scope

\[
D_c(x)=\max[D_j-2(\delta_{i,0}+S_ix),0].
\]

### Done when

Sensitivity to \(S_i\) is monotonic and tested.

---

## TRN-003 — Implement pressure-amplitude decay

**Priority:** P1  
**Depends on:** TRN-001, TRN-002

### Scope

\[
dA_p/dx=-C_dA_p/D_c.
\]

### Done when

Zero and positive decay limits pass.

---

## TRN-004 — Implement local cell-spacing continuation

**Priority:** P1  
**Depends on:** TRN-002, TRN-003

### Scope

\[
L_n=C_\lambda D_c\sqrt{M_{j,n}^2-1}\Phi_\delta.
\]

### Done when

Spacing is positive, finite, and carries calibration metadata.

---

## TRN-005 — Implement reduced-order downstream cell geometry

**Priority:** P1  
**Depends on:** TRN-004

### Done when

Scaled cells are labeled `SCALED_REDUCED_ORDER` and are not mislabeled as MOC.

---

## TRN-006 — Implement physical and safety termination

**Priority:** P1  
**Depends on:** TRN-003, TRN-004

### Done when

Core diameter, Mach, oscillation, persistence, topology, domain, and cell limits
are separate reasons.

---

## TRN-007 — Add shock-train result and diagnostics

**Priority:** P1  
**Depends on:** TRN-005, TRN-006

### Done when

Cell count is an output and termination metrics are serialized.

---

## TRN-008 — Add calibration sensitivity and uncertainty

**Priority:** P2  
**Depends on:** TRN-007

### Done when

At least deterministic sweeps of \(S_i,C_d,C_\lambda\) are available.

---

## TRN-009 — Calibrate and validate against separate datasets

**Priority:** P1  
**Depends on:** TRN-007

### Done when

Calibration cases and validation cases are explicitly disjoint.

## 5. Phase 3 — Integral mixing plume

## MIX-001 — Add conserved integral-state contracts

**Priority:** P1  
**Depends on:** Phase 2 gate

### Done when

Mass flow, momentum flux, total-enthalpy flow, and species mass flows are
represented directly.

---

## MIX-002 — Implement top-hat entrainment ODE

**Priority:** P1  
**Depends on:** MIX-001

### Done when

`solve_ivp` integration passes zero-entrainment and conservation tests.

---

## MIX-003 — Implement thermodynamic state recovery

**Priority:** P1  
**Depends on:** MIX-002

### Done when

Temperature, density, area, radius, and composition are recovered at every
valid state.

---

## MIX-004 — Implement mixing termination events

**Priority:** P1  
**Depends on:** MIX-002, MIX-003

### Done when

Velocity, temperature, composition, persistence, and domain termination are
distinct.

---

## MIX-005 — Reconstruct top-hat axisymmetric field

**Priority:** P1  
**Depends on:** MIX-003

### Done when

The field is finite and directly consumable by the gray-gas ray tracer.

---

## MIX-006 — Add flux-preserving Gaussian profiles

**Priority:** P2  
**Depends on:** MIX-005

### Done when

Integrated mass, momentum, enthalpy, and species match the integral state.

## 6. Phase 4 — Gray-gas radiation

## RAD-001 — Implement spectral units and Planck function

**Priority:** P1  
**Depends on:** Phase 3 gate

### Done when

Wavelength/wavenumber conversion preserves integrated radiance.

---

## RAD-002 — Implement axisymmetric ray geometry

**Priority:** P1  
**Depends on:** RAD-001, MIX-005

### Done when

Cylinder/sphere chord tests and rotational symmetry pass.

---

## RAD-003 — Implement exact gray-gas segment transport

**Priority:** P1  
**Depends on:** RAD-002

### Done when

Homogeneous slab and optical-depth limits pass.

---

## RAD-004 — Implement spectral image and area integration

**Priority:** P1  
**Depends on:** RAD-003

### Done when

Radiance images and radiant intensity have explicit units.

---

## RAD-005 — Implement angular signature sweep

**Priority:** P1  
**Depends on:** RAD-004

### Done when

Optically thin integrated orientation invariance passes.

---

## RAD-006 — Implement IR-domain termination

**Priority:** P1  
**Depends on:** RAD-004

### Done when

Incremental band contribution controls the radiation-domain end independently
of shock-cell termination.

## 7. Phase 5 — Molecular spectra, atmosphere, and sensor

## SPC-001 — Build reproducible cross-section generator

**Priority:** P1  
**Depends on:** RAD-003

### Done when

HITEMP/HAPI inputs and all metadata are versioned.

---

## SPC-002 — Implement cross-section table storage and interpolation

**Priority:** P1  
**Depends on:** SPC-001

### Done when

Grid-node and withheld-point errors pass.

---

## SPC-003 — Implement mixture absorption

**Priority:** P1  
**Depends on:** SPC-002

### Done when

\[
\alpha=\sum_sn_s\sigma_s
\]

passes mixture and column-density tests.

---

## SPC-004 — Integrate molecular transport into images

**Priority:** P1  
**Depends on:** SPC-003, RAD-004

### Done when

Narrow-window line-by-line benchmark agrees with reference.

---

## SPC-005 — Add atmospheric path model interface

**Priority:** P1  
**Depends on:** SPC-004

### Done when

Source radiance, path transmission, and path radiance remain separable.

---

## SPC-006 — Add detector response model

**Priority:** P1  
**Depends on:** SPC-005

### Done when

Output units identify power, photon rate, counts, or normalized response.

---

## SPC-007 — Validate against heated-plume IR data

**Priority:** P1  
**Depends on:** SPC-004

### Done when

Image and band metrics are compared with independent measurements.

## 8. Phase 6 — Thermochemistry and particles

## CHEM-001 — Add species and mixture contracts

**Priority:** P1  
**Depends on:** Phase 0 gas contracts

### Done when

Mass/mole conversion and elemental composition tests pass.

---

## CHEM-002 — Add CEA boundary-state adapter

**Priority:** P1  
**Depends on:** CHEM-001

### Done when

Raw provenance, units, composition, and elemental closure are preserved.

---

## CHEM-003 — Add thermally perfect mixture properties

**Priority:** P1  
**Depends on:** CHEM-001

### Done when

\(h(T)\), \(c_p(T)\), \(\gamma(T)\), and enthalpy inversion pass.

---

## CHEM-004 — Add frozen variable-property expansion/shock solve

**Priority:** P2  
**Depends on:** CHEM-003, Phase 1

### Done when

Mass, momentum, total enthalpy, entropy, and frozen composition checks pass.

---

## CHEM-005 — Add equilibrium reference path

**Priority:** P2  
**Depends on:** CHEM-003

### Done when

Trusted CEA/Cantera cases are reproduced.

---

## CHEM-006 — Add finite-rate integral afterburning

**Priority:** P2  
**Depends on:** MIX-002, CHEM-003

### Done when

Elemental and energy balances pass and disabling rates recovers frozen mixing.

---

## CHEM-007 — Add particle population and thermal model

**Priority:** P3  
**Depends on:** CHEM-006

### Done when

Particle/gas temperatures and drag/energy relaxation are explicit.

---

## CHEM-008 — Add particle absorption and scattering

**Priority:** P3  
**Depends on:** CHEM-007, SPC-004

### Done when

Zero-particle limit recovers molecular radiation and optical-property metadata
is versioned.

## 9. Phase 7 — Higher-fidelity flow

Create separate planning issues before implementation for:

```text
axisymmetric Euler/RANS continuation
Mach-disk topology
internal nozzle separation
flight coflow
vehicle/base flow
multiple engines
crossflow and curved plumes
non-LTE radiation
rarefied flow
```

These are not hidden extensions of the reduced-order solver.

<!-- END 09_issue_backlog.md -->


---

<!-- BEGIN 10_coding_agent_execution_protocol.md -->

# Coding-Agent Execution Protocol

## 1. Mission

Implement the handoff plans in dependency order while preserving mathematical
traceability, public compatibility where practical, and strict verification
gates.

Do not optimize for the largest possible code change. Optimize for the smallest
reviewable change that proves one physical or architectural claim.

## 2. Branch policy

Starting branch:

```text
feature/initial-work
```

Recommended phase branches:

```text
feature/foundation-corrections
feature/validated-first-cell
feature/finite-shock-train
feature/integral-mixing-plume
feature/gray-radiative-transfer
feature/spectral-radiation
feature/thermochemistry
```

Within a phase, use issue branches when possible:

```text
task/FND-002-correct-choked-mass-flow
task/FND-005-oblique-shock-roots
```

Do not commit directly to the source branch.

## 3. Required reading before code changes

Read:

```text
README.md
01_model_contract_and_architecture.md
the plan for the active phase
08_validation_and_test_matrix.md
09_issue_backlog.md
this execution protocol
```

Then inspect the current branch versions of all files named by the issue.

If the branch differs materially from the documented source blobs, report the
difference before applying the plan.

## 4. Scope rules

1. Implement only the active issue.
2. Do not bundle unrelated renames, formatting, dependency upgrades, or
   architecture moves.
3. Preserve existing TODOs unless the issue explicitly resolves them.
4. When resolving a TODO, mention it in the completion report.
5. Do not delete working public APIs without a compatibility path or explicit
   migration approval.
6. Do not hide a failed physical solve behind a warning and nominal result.
7. Do not add empirical constants without provenance and applicability fields.
8. Do not call a planar result axisymmetric.
9. Do not claim model validation from unit tests alone.
10. Do not silently change units or angle conventions.

## 5. Python standards

Target:

```text
Python 3.12+
```

Required style:

- Full type annotations on public and private functions.
- `from __future__ import annotations`.
- `numpy.typing.NDArray` for array contracts.
- Pydantic v2 for validated configuration and interchange models.
- NumPy/SciPy for numerical algorithms.
- Pytest for tests.
- Ruff and Pyright clean.
- Concise, durable docstrings focused on contract and assumptions.
- Preserve TODO comments.
- End every newly written or materially modified scope with a standalone
  `####` marker, following the project-owner convention.
- Do not bulk-reformat untouched legacy scopes solely to change existing scope
  markers.

Avoid:

- `Any` where a durable type can be expressed.
- Bare dictionaries as public result contracts.
- Global mutable configuration.
- Hidden unit conversion.
- Catch-all exception handling around numerical failure.
- Unbounded nonlinear root solves when a physical bracket exists.

## 6. Numerical standards

### Root solving

- Prefer bounded scalar solvers.
- Report bracket, iterations, residual, and convergence.
- Validate the physical branch after solving.
- Do not accept a root outside its admissible interval.

### Geometry

- Normalize direction vectors or document scale.
- Return ray parameters.
- Check forward direction.
- Report condition number and residual.
- Reject degenerate geometry.

### ODE integration

- Use state variables tied to conserved fluxes.
- Use event functions for physical termination.
- Retain the last valid state on failure.
- Report solver tolerances and step statistics.

### Arrays

- Validate shape, dtype, finiteness, and monotonic grids.
- Make immutable public arrays read-only.
- Avoid implicit broadcasting in public contracts when dimensions can be
  ambiguous.

## 7. Equation traceability

Every new physics function must include:

```text
equation
assumptions
input units
output units
valid domain
failure behavior
```

A code comment or docstring should refer to the corresponding handoff section
or a stable primary reference.

For a correlation or closure, also include:

```text
calibration source
applicability range
coefficient uncertainty
```

## 8. Test-first expectation

For a known defect:

1. Add a test that fails on the current branch.
2. Confirm the failure represents the documented defect.
3. Implement the smallest correction.
4. Run focused tests.
5. Run the full phase quality gate.

For new capability:

1. Add analytic verification cases.
2. Implement the reference or simplest transparent solver.
3. Add failure and limit cases.
4. Add convergence tests.
5. Only then add performance optimizations.

## 9. Quality commands

Before every completed issue:

```bash
python -m pytest <focused tests>
python -m ruff check <changed paths>
python -m pyright
```

Before every phase PR:

```bash
python -m pytest
python -m ruff check .
python -m pyright
python -m build
```

Run the installed-wheel smoke test if package structure or exports changed.

## 10. Commit policy

Use small commits with a clear prefix:

```text
fix(FND-002): correct choked throat-area exponent
test(FND-002): add mass-flow inversion benchmarks
refactor(FND-003): route explicit gas properties
feat(MOC-005): solve ambient-pressure free boundary
docs(TRN-006): document termination result contract
```

A commit should not mix behavior, broad formatting, and unrelated tests.

## 11. Completion report format

Every issue completion report must contain:

### Summary

What changed and why.

### Equations or contracts implemented

List exact equations, branch choices, units, and assumptions.

### Files changed

List paths and purpose.

### Tests added

List test IDs from the validation matrix where possible.

### Commands run

Include exact commands and pass/fail status.

### Numerical evidence

Provide residuals, reference values, or convergence evidence.

### Compatibility

Describe deprecations, wrappers, or schema changes.

### Remaining limitations

State what the implementation still does not model.

### Follow-on issue

Name the next dependency-ready issue.

## 12. Failure protocol

When implementation reveals that the plan is inconsistent with the branch:

1. Stop the affected physical change.
2. Preserve any independent tests or diagnostics that are still valid.
3. Report:
   - branch evidence;
   - violated assumption;
   - smallest plan amendment;
   - affected dependent issues.
4. Do not invent a workaround that weakens physics or hides failure.

## 13. Dependency changes

A new dependency requires:

```text
reason
runtime or optional classification
minimum version
license review note
fallback behavior
CI update
```

SciPy and Pydantic are expected additions. HAPI and Cantera should remain
optional.

## 14. Data and fixture policy

Every external fixture includes:

```text
source
retrieval date
license or usage note
raw/processed distinction
processing script
checksum
units
case metadata
```

Do not manually transcribe large reference datasets without a reproducible
processing script.

## 15. Performance policy

1. Preserve a transparent reference implementation.
2. Profile before optimizing.
3. Add equivalence tests before a faster kernel.
4. Report time and memory for benchmark sizes.
5. Do not sacrifice deterministic results or diagnostics for speed without a
   documented option.

## 16. Documentation policy

Update the relevant handoff/model document when:

- assumptions change;
- a correlation is calibrated;
- a public contract changes;
- a validity boundary is discovered;
- a planned phase is intentionally deferred.

Do not allow code behavior and the mathematical model note to diverge.

## 17. Definition of done

An issue is done only when:

- requested behavior is implemented;
- analytic or regression tests pass;
- failure behavior is tested;
- typing and linting pass;
- assumptions and units are documented;
- no unrelated changes are included;
- completion report is produced.

A phase is done only when its acceptance gate in the phase plan passes.

<!-- END 10_coding_agent_execution_protocol.md -->


---

<!-- BEGIN 11_coding_agent_kickoff_prompt.md -->

# Coding-Agent Kickoff Prompt

Use the following prompt to begin Phase 0.

---

You are implementing the foundation-corrections phase for the public repository
`sheepfling/Exhaust-Plume`, starting from branch
`feature/initial-work`.

Read these handoff files before editing code:

```text
docs/coding_agent_handoff/README.md
docs/coding_agent_handoff/01_model_contract_and_architecture.md
docs/coding_agent_handoff/02_foundation_corrections_plan.md
docs/coding_agent_handoff/08_validation_and_test_matrix.md
docs/coding_agent_handoff/09_issue_backlog.md
docs/coding_agent_handoff/10_coding_agent_execution_protocol.md
```

The reviewed source snapshot used these key blobs:

```text
plume_solve.py:
25768f15afafa5863f5cb30a0aaee0d8a04aaf8d

motor_parameters.py:
ad3a436ef5c971c64a0291e136dfa0cba7eb020e

oblique_shock.py:
8d98ccd5820052832ff8e210f7e5931574a893a3
```

First compare the current branch to that snapshot. If the affected code has
changed materially, document the differences and adapt only where the
mathematical intent remains valid.

Create or use:

```text
feature/foundation-corrections
```

Execute Phase 0 in dependency order. Start with the smallest reviewable group:

```text
FND-001  gas and nozzle contracts
FND-002  choked mass-flow/throat-area correction
FND-003  explicit gas properties and removal of hidden dry-air assumptions
FND-004  energy/enthalpy naming correction
```

Do not begin first-cell MOC, shock-train termination, radiation, or chemistry
work during this group.

Required mathematical corrections include:

\[
A^*
=
\frac{\dot m}{p_0}
\sqrt{\frac{RT_0}{\gamma}}
\left(
\frac{\gamma+1}{2}
\right)^{\frac{\gamma+1}{2(\gamma-1)}},
\]

\[
R=R_u/W,
\qquad
\rho=p/(RT),
\]

\[
h_0=h+u^2/2=c_pT_0.
\]

Requirements:

- Python 3.12+.
- Full type annotations.
- Pydantic v2 for validated contracts.
- NumPy/SciPy where numerical work is required.
- Pytest, Ruff, and Pyright clean.
- Preserve existing TODOs.
- End every newly written or materially modified scope with `####`.
- Do not bulk-reformat untouched code.
- Add a failing regression test before fixing each known defect.
- Keep public compatibility wrappers where practical.
- Never log an error and return a nominal success state.
- Use SI units and radians internally.

At the end of this issue group, produce a completion report with:

```text
summary
equations/contracts implemented
files changed
tests added
commands run
numerical evidence
compatibility impact
remaining limitations
next dependency-ready issue
```

Run at minimum:

```bash
python -m pytest <focused tests>
python -m pytest
python -m ruff check .
python -m pyright
python -m build
```

Do not proceed to the next issue group until this group passes the full quality
gate.

---

<!-- END 11_coding_agent_kickoff_prompt.md -->


---

<!-- BEGIN 12_reference_sources.md -->

# Reference Sources and Provenance Plan

## 1. Purpose

Identify the primary references and validation-data families that should
support equations, correlations, test fixtures, and calibration. This file is
a source map, not permission to copy data without checking usage terms.

Every imported fixture must record:

```text
source title
authors or issuing organization
publication/report identifier
publication year
retrieval date
raw file checksum
units
processing script
license or usage note
```

## 2. Compressible-flow equations

### Primary textbook

John D. Anderson, *Modern Compressible Flow: With Historical Perspective*,
third edition.

Use for:

```text
isentropic relations
Prandtl-Meyer flow
normal shocks
oblique shocks
theta-beta-M relation
method-of-characteristics foundations
```

Equation implementation must still be checked independently and tested against
analytic values.

### NASA Glenn educational equations

Use the NASA Glenn compressible-flow and rocket-thrust equation pages as a
secondary check for:

```text
area-Mach relation
choked mass flow
nozzle thrust terms
```

Do not use an educational page as the only validation source.

## 3. Shock-cell spacing and topology

Use the classical Prandtl/Pack near-adapted circular-jet shock-cell literature
for the baseline relation:

\[
L_s\approx1.306D_j\sqrt{M_j^2-1}.
\]

Use later finite-shear-layer analyses for spacing corrections and shock
amplitude behavior.

Rules:

- Treat the relation as a correlation/check, not a governing law.
- Record Mach, pressure ratio, temperature ratio, diameter convention, and
  boundary-layer/shear-layer assumptions.
- Do not extrapolate a near-adapted relation into Mach-disk regimes.

## 4. Flow-structure validation data

### NASA NTRS 20080024224

Underexpanded supersonic round-jet planar-laser-induced-fluorescence data,
including an exit Mach near 2.6 and a range of exit-to-ambient pressure ratios.

Use for:

```text
shock-cell topology
first-cell length
cell spacing
plume boundary
qualitative/quantitative image comparison
```

Verify exact case metadata from the report before creating fixtures.

### NASA NTRS 20060004779

Fluorescence-imaging measurements of underexpanded sonic jets over a broad
pressure-ratio range, with comparisons including shock wavelength and
Mach-disk geometry.

Use initially for:

```text
Mach-disk-required classifier
cell wavelength trends
maximum jet diameter trends
```

Do not claim Mach-disk prediction until that topology is implemented.

### NASA NTRS 19840007357

Historical shock-capturing/turbulent jet-mixing plume-solver work that includes
strongly underexpanded behavior and downstream mixing.

Use for:

```text
architecture comparison
Mach-disk and post-disk model requirements
mixing-continuation expectations
```

## 5. Infrared validation

### NASA NTRS 19960015541

Axisymmetric heated-plume work combining measured temperature/pressure or
constituent fields with infrared imaging and a ray-tracing/band-radiation
comparison.

Use for the first experimental radiation validation because it separates plume
field uncertainty from complex reacting rocket chemistry better than an
operational rocket image.

Comparison metrics should include:

```text
pixel radiance
centerline and radial image profiles
integrated band radiant intensity
view-angle dependence if available
```

## 6. Spectroscopic data

### HITRAN

Use for line definitions, units, pressure broadening, partition functions, and
reference lower-temperature spectroscopy where applicable.

### HITEMP

Use high-temperature line lists for selected combustion species and wavelength
windows.

### HAPI

Use as a reproducible reference generator for:

```text
line-by-line cross sections
transmittance
radiance
temperature/pressure interpolation fixtures
```

Store the database version, isotopologue policy, line shape, wing cutoff, and
partition-function source with every generated table.

## 7. Equilibrium chemistry

### NASA CEA

Primary source:

```text
NASA RP-1311, Parts I and II
Computer Program for Calculation of Complex Chemical Equilibrium Compositions
and Applications
```

Use for:

```text
equilibrium composition
frozen/equilibrium nozzle expansion
thermodynamic properties
theoretical rocket performance
reference shock/equilibrium cases
```

Store raw CEA inputs and outputs. Do not retain only a manually copied result
table.

## 8. Finite-rate chemistry and transport

### Cantera

Use official Cantera documentation and versioned mechanisms for:

```text
species thermodynamics
reaction kinetics
equilibrium checks
transport properties
homogeneous-reactor verification
```

The mechanism file, Cantera version, phase name, and transport model are part
of the result provenance.

## 9. Atmosphere and sensor propagation

The intrinsic plume radiation result must remain independent of atmospheric
and sensor models.

For later atmospheric propagation, select a versioned, validated model capable
of returning:

```text
spectral path transmittance
path radiance
observer/source geometry
atmospheric profile
```

For every sensor, store:

```text
spectral response
aperture
optical throughput
integration time
detector conversion model
range
field of view
```

## 10. Source-ingestion checklist

Before adding any external fixture:

- [ ] Verify the report identifier and exact case.
- [ ] Preserve the raw source file.
- [ ] Record checksum and retrieval date.
- [ ] Confirm units and coordinate conventions.
- [ ] Write a deterministic processing script.
- [ ] Keep raw and processed data separate.
- [ ] Document excluded or digitized quantities.
- [ ] Record uncertainty bars when supplied.
- [ ] Separate calibration cases from validation cases.
- [ ] Add a README beside the fixture.

## 11. Citation rule for code and docs

Use stable report numbers, DOIs, book editions, and database versions in
docstrings and model notes. Avoid source comments that point only to an
unversioned web page.

A correlation implementation must cite the precise source used for its
coefficient and validity range.

<!-- END 12_reference_sources.md -->


---

<!-- BEGIN 13_architecture_decision_records.md -->

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

<!-- END 13_architecture_decision_records.md -->


---

<!-- BEGIN 14_api_contracts_and_serialization.md -->

# Public API Contracts and Serialization Specification

## 1. Purpose

This document defines the target Python API, configuration models, numerical
result types, enum values, serialization format, and schema-version rules. It
prevents the coding agent from inventing incompatible contracts independently
for each phase.

The API is intentionally layered:

```text
validated immutable configuration
        ↓
numerical solver functions
        ↓
immutable numerical result objects
        ↓
explicit serialization adapters
```

Pydantic models are recommended for user-authored configuration and schema
validation. Frozen dataclasses or lightweight immutable classes are recommended
for high-volume numerical result objects. NumPy arrays shall not be placed
inside Pydantic models that are repeatedly instantiated in inner loops.

## 2. Package namespaces

Target public namespaces:

```text
exhaust_plume.gas
exhaust_plume.nozzle
exhaust_plume.shock_cells
exhaust_plume.mixing
exhaust_plume.radiation
exhaust_plume.chemistry
exhaust_plume.validation
exhaust_plume.compat
```

Internal implementation modules may remain under `models/` during migration,
but public imports should converge on the namespaces above.

## 3. Stable enum values

Enum serialization values are lowercase strings and shall not depend on Python
auto-numbering.

### 3.1 ExpansionRegime

```text
matched
underexpanded
overexpanded
invalid_exit_state
```

### 3.2 SolverStatus

```text
converged
converged_at_boundary
invalid_input
outside_model_validity
no_bracket
max_iterations
ill_conditioned
nonfinite_result
partial_result
```

### 3.3 TerminationReason

```text
no_pressure_mismatch
pressure_oscillation_decayed
mean_pressure_equilibrated
mixing_layer_reached_axis
core_became_subsonic
velocity_equilibrated
temperature_equilibrated
composition_equilibrated
ir_contribution_negligible
mach_disk_required
detached_shock_required
nozzle_separation_not_modeled
domain_limit
max_cell_limit
max_step_limit
numerical_failure
```

### 3.4 ShockBranch

```text
weak
strong
detached_required
not_applicable
```

### 3.5 GeometryStatus

```text
valid
open_transition
no_forward_intersection
ill_conditioned
self_intersecting
zero_area
invalid_winding
outside_domain
```

### 3.6 ModelLevel

```text
ideal_first_cell
reduced_shock_train
integral_frozen_plume
gray_radiation
molecular_radiation
equilibrium_chemistry
finite_rate_chemistry
particle_radiation
axisymmetric_cfd
```

## 4. Common scalar and metadata contracts

### 4.1 NumericalTolerances

Recommended frozen Pydantic model:

```python
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class NumericalTolerances(BaseModel):
  model_config = ConfigDict(frozen=True, extra='forbid')

  state_rtol: float = Field(default=1.0e-9, gt=0.0)
  state_atol: float = Field(default=1.0e-12, gt=0.0)
  residual_rtol: float = Field(default=1.0e-9, gt=0.0)
  residual_atol: float = Field(default=1.0e-12, gt=0.0)
  angle_atol_rad: float = Field(default=1.0e-10, gt=0.0)
  geometry_atol_m: float = Field(default=1.0e-10, gt=0.0)
  condition_number_max: float = Field(default=1.0e12, gt=1.0)
  max_iterations: int = Field(default=200, ge=1)
####
```

The numerical defaults are starting values, not universal claims. Each solver
may expose a narrower specialized tolerance model while preserving this common
base vocabulary.

### 4.2 Provenance

```python
class Provenance(BaseModel):
  model_config = ConfigDict(frozen=True, extra='forbid')

  code_version: str
  input_schema_version: str
  model_level: ModelLevel
  calibration_id: str | None = None
  calibration_version: str | None = None
  spectroscopy_database: str | None = None
  spectroscopy_version: str | None = None
  random_seed: int | None = None
####
```

### 4.3 Diagnostic

```python
@dataclass(frozen=True, slots=True)
class Diagnostic:
  code: str
  message: str
  severity: Literal['info', 'warning', 'error']
  value: float | None = None
  units: str | None = None
####
```

Messages are for humans. Stable `code` values are for tests and downstream
programs.

## 5. Gas and composition configuration

### 5.1 CaloricallyPerfectGasConfig

```python
class CaloricallyPerfectGasConfig(BaseModel):
  model_config = ConfigDict(frozen=True, extra='forbid')

  gamma: float = Field(gt=1.0)
  molar_mass_kg_per_mol: float = Field(gt=0.0)
####
```

Derived property:

\[
R=R_u/\overline W.
\]

The public configuration must not contain an implicit dry-air default for a
rocket plume. A convenience constructor named `dry_air()` may exist, but the
chosen gas must remain explicit in serialized input.

### 5.2 FrozenMixtureConfig

```python
class SpeciesFraction(BaseModel):
  model_config = ConfigDict(frozen=True, extra='forbid')

  species: str
  mass_fraction: float = Field(ge=0.0, le=1.0)
####


class FrozenMixtureConfig(BaseModel):
  model_config = ConfigDict(frozen=True, extra='forbid')

  species: tuple[SpeciesFraction, ...]
  normalization_tolerance: float = Field(default=1.0e-10, gt=0.0)
####
```

The validator shall reject duplicate species and mass-fraction sums outside
tolerance rather than silently normalizing by default. An explicit
`normalized()` constructor may be offered for interactive use.

## 6. Nozzle and ambient input contracts

### 6.1 NozzleExitConfig

```python
class NozzleExitConfig(BaseModel):
  model_config = ConfigDict(frozen=True, extra='forbid')

  mach: float = Field(gt=1.0)
  total_pressure_Pa: float = Field(gt=0.0)
  total_temperature_K: float = Field(gt=0.0)
  exit_radius_m: float = Field(gt=0.0)
  flow_angle_rad: float = 0.0
  mass_flow_rate_kg_per_s: float | None = Field(default=None, gt=0.0)
  exit_profile_id: str | None = None
  nozzle_solution_validated: bool = False
####
```

`mass_flow_rate_kg_per_s` may be omitted when it is not needed by the first-cell
solver, but it becomes required before integral mixing is solved.

### 6.2 AmbientConfig

```python
class AmbientConfig(BaseModel):
  model_config = ConfigDict(frozen=True, extra='forbid')

  static_pressure_Pa: float = Field(gt=0.0)
  static_temperature_K: float = Field(gt=0.0)
  velocity_x_m_per_s: float = 0.0
  velocity_y_m_per_s: float = 0.0
  composition: FrozenMixtureConfig | None = None
  geopotential_altitude_m: float | None = None
####
```

Altitude is metadata or an upstream atmosphere-model input; the core solver
uses the resolved ambient state.

## 7. Phase configuration contracts

### 7.1 FirstCellConfig

```python
class FirstCellConfig(BaseModel):
  model_config = ConfigDict(frozen=True, extra='forbid')

  expansion_characteristics: int = Field(default=16, ge=2)
  compression_characteristics: int = Field(default=8, ge=1)
  pressure_match_rtol: float = Field(default=1.0e-4, gt=0.0)
  permit_strong_shock_branch: bool = False
  permit_legacy_parabola_fallback: bool = False
  tolerances: NumericalTolerances = NumericalTolerances()
####
```

### 7.2 ShockTrainCalibrationConfig

```python
class ShockTrainCalibrationConfig(BaseModel):
  model_config = ConfigDict(frozen=True, extra='forbid')

  calibration_id: str
  version: str
  coherent_core_spreading_rate: float = Field(gt=0.0)
  cell_spacing_coefficient: float = Field(default=1.306, gt=0.0)
  pressure_decay_coefficient: float = Field(gt=0.0)
  initial_shear_layer_thickness_ratio: float = Field(ge=0.0)
  covariance: tuple[tuple[float, ...], ...] | None = None
  source_citations: tuple[str, ...]
  applicability_notes: str
####
```

### 7.3 ShockTrainConfig

```python
class ShockTrainConfig(BaseModel):
  model_config = ConfigDict(frozen=True, extra='forbid')

  max_cells: int = Field(default=20, ge=0)
  max_axial_distance_m: float = Field(gt=0.0)
  pressure_oscillation_cutoff: float = Field(gt=0.0)
  mean_pressure_cutoff: float = Field(gt=0.0)
  coherent_core_diameter_cutoff_ratio: float = Field(gt=0.0)
  core_mach_cutoff: float = Field(default=1.01, gt=1.0)
  persistence_cells: int = Field(default=2, ge=1)
  calibration: ShockTrainCalibrationConfig
####
```

### 7.4 IntegralPlumeConfig

```python
class IntegralPlumeConfig(BaseModel):
  model_config = ConfigDict(frozen=True, extra='forbid')

  max_axial_distance_m: float = Field(gt=0.0)
  entrainment_coefficient: float = Field(gt=0.0)
  profile_model: Literal['top_hat', 'gaussian'] = 'top_hat'
  velocity_equilibrium_rtol: float = Field(gt=0.0)
  temperature_equilibrium_rtol: float = Field(gt=0.0)
  composition_equilibrium_atol: float = Field(gt=0.0)
  persistence_distance_m: float = Field(gt=0.0)
  ode_method: Literal['RK45', 'DOP853', 'Radau', 'BDF'] = 'DOP853'
  tolerances: NumericalTolerances = NumericalTolerances()
####
```

### 7.5 RadiationConfig

```python
class SpectralGridConfig(BaseModel):
  model_config = ConfigDict(frozen=True, extra='forbid')

  coordinate: Literal['wavenumber_cm-1', 'wavelength_um']
  start: float = Field(gt=0.0)
  stop: float = Field(gt=0.0)
  points: int = Field(ge=2)
####


class RadiationConfig(BaseModel):
  model_config = ConfigDict(frozen=True, extra='forbid')

  spectral_grid: SpectralGridConfig
  view_angles_rad: tuple[float, ...]
  image_width_pixels: int = Field(ge=1)
  image_height_pixels: int = Field(ge=1)
  model: Literal['gray', 'tabulated_cross_section', 'line_by_line']
  background_temperature_K: float = Field(gt=0.0)
  include_atmospheric_path: bool = False
  sensor_response_id: str | None = None
  ir_slice_cutoff: float = Field(default=1.0e-5, gt=0.0)
  ir_persistence_slices: int = Field(default=3, ge=1)
####
```

## 8. Top-level simulation configuration

```python
class PlumeSimulationConfig(BaseModel):
  model_config = ConfigDict(frozen=True, extra='forbid')

  schema_version: Literal['2.0'] = '2.0'
  gas: CaloricallyPerfectGasConfig | FrozenMixtureConfig
  nozzle_exit: NozzleExitConfig
  ambient: AmbientConfig
  first_cell: FirstCellConfig
  shock_train: ShockTrainConfig | None = None
  integral_plume: IntegralPlumeConfig | None = None
  radiation: RadiationConfig | None = None
####
```

Validation rules shall enforce phase dependencies. For example, radiation may
consume a first-cell-only field for tests, but production angular signatures
that claim the full plume require an integral-plume continuation or an explicit
finite-domain truncation acknowledgement.

## 9. Numerical result contracts

### 9.1 FlowState

```python
@dataclass(frozen=True, slots=True)
class FlowState:
  mach: float
  static_pressure_Pa: float
  static_temperature_K: float
  static_density_kg_per_m3: float
  velocity_x_m_per_s: float
  velocity_y_m_per_s: float
  gamma: float
  specific_gas_constant_J_per_kg_K: float
####
```

Derived properties include total pressure, total temperature, speed of sound,
and stagnation enthalpy. Derived values should not be duplicated in serialized
state unless a snapshot format explicitly requests them.

### 9.2 Geometry primitives

```python
@dataclass(frozen=True, slots=True)
class Point2D:
  x_m: float
  r_m: float
####


@dataclass(frozen=True, slots=True)
class RayIntersectionResult:
  status: GeometryStatus
  point: Point2D | None
  parameter_1_m: float | None
  parameter_2_m: float | None
  residual_m: float
  condition_number: float
####
```

### 9.3 Characteristic and shock records

```python
@dataclass(frozen=True, slots=True)
class CharacteristicPoint:
  point: Point2D
  flow: FlowState
  flow_angle_rad: float
  mach_angle_rad: float
  prandtl_meyer_angle_rad: float
  k_plus_rad: float
  k_minus_rad: float
####


@dataclass(frozen=True, slots=True)
class ShockSegment:
  start: Point2D
  end: Point2D
  branch: ShockBranch
  shock_angle_rad: float
  turn_angle_rad: float
  upstream: FlowState
  downstream: FlowState
####
```

### 9.4 ClosedZone

```python
@dataclass(frozen=True, slots=True)
class ClosedZone:
  zone_id: str
  cell_index: int
  vertices_xr_m: NDArray[np.float64]
  flow: FlowState
  composition_mass_fractions: NDArray[np.float64] | None
  geometry_status: GeometryStatus
####
```

Array shape is `(N, 2)`. Successful closed zones require finite values and
`geometry_status == VALID`.

### 9.5 SolverDiagnostics

```python
@dataclass(frozen=True, slots=True)
class SolverDiagnostics:
  status: SolverStatus
  iterations: int
  absolute_residual: float
  relative_residual: float
  diagnostics: tuple[Diagnostic, ...]
####
```

### 9.6 FirstCellResult

```python
@dataclass(frozen=True, slots=True)
class FirstCellResult:
  regime: ExpansionRegime
  zones: tuple[ClosedZone, ...]
  characteristics: tuple[CharacteristicPoint, ...]
  shocks: tuple[ShockSegment, ...]
  x_start_m: float
  x_end_m: float
  predicted_reference_length_m: float | None
  diagnostics: SolverDiagnostics
  provenance: Provenance
####
```

### 9.7 ShockCell and ShockTrainResult

```python
@dataclass(frozen=True, slots=True)
class ShockCell:
  cell_index: int
  x_start_m: float
  x_end_m: float
  coherent_core_diameter_start_m: float
  coherent_core_diameter_end_m: float
  pressure_oscillation_amplitude: float
  mean_pressure_residual: float
  core_mach: float
  zones: tuple[ClosedZone, ...]
####


@dataclass(frozen=True, slots=True)
class ShockTrainResult:
  cells: tuple[ShockCell, ...]
  shock_train_end_x_m: float
  supersonic_core_end_x_m: float
  termination_reason: TerminationReason
  termination_is_physical: bool
  diagnostics: SolverDiagnostics
  provenance: Provenance
####
```

### 9.8 Integral plume result

```python
@dataclass(frozen=True, slots=True)
class IntegralPlumeSample:
  x_m: float
  radius_m: float
  mass_flow_rate_kg_per_s: float
  axial_velocity_m_per_s: float
  static_pressure_Pa: float
  static_temperature_K: float
  static_density_kg_per_m3: float
  species_mass_fractions: NDArray[np.float64]
####


@dataclass(frozen=True, slots=True)
class IntegralPlumeResult:
  samples: tuple[IntegralPlumeSample, ...]
  thermal_plume_end_x_m: float
  termination_reason: TerminationReason
  termination_is_physical: bool
  diagnostics: SolverDiagnostics
  provenance: Provenance
####
```

### 9.9 Radiation result

```python
@dataclass(frozen=True, slots=True)
class SpectralRadianceImage:
  view_angle_rad: float
  spectral_coordinate: NDArray[np.float64]
  radiance_W_per_m2_sr_per_spectral_unit: NDArray[np.float64]
  image_u_m: NDArray[np.float64]
  image_v_m: NDArray[np.float64]
####


@dataclass(frozen=True, slots=True)
class AngularSignature:
  view_angles_rad: NDArray[np.float64]
  spectral_coordinate: NDArray[np.float64]
  radiant_intensity_W_per_sr_per_spectral_unit: NDArray[np.float64]
  ir_domain_end_x_m: NDArray[np.float64]
  provenance: Provenance
####
```

The radiance image shape must be documented and validated, for example
`(spectral, v, u)`. The angular-signature intensity shape is `(angle,
spectral)`.

## 10. Public solver functions

Target signatures:

```python
def calculate_nozzle_exit_state(
    config: NozzleExitConfig,
    gas: CaloricallyPerfectGasConfig,
) -> FlowState:
  ...
####


def classify_expansion_regime(
    exit_state: FlowState,
    ambient: AmbientConfig,
    *,
    pressure_rtol: float,
) -> ExpansionRegime:
  ...
####


def solve_first_shock_cell(
    exit_state: FlowState,
    ambient: AmbientConfig,
    config: FirstCellConfig,
) -> FirstCellResult:
  ...
####


def solve_shock_train(
    first_cell: FirstCellResult,
    ambient: AmbientConfig,
    config: ShockTrainConfig,
) -> ShockTrainResult:
  ...
####


def solve_integral_plume(
    entry_state: IntegralPlumeSample,
    ambient: AmbientConfig,
    config: IntegralPlumeConfig,
) -> IntegralPlumeResult:
  ...
####


def solve_angular_signature(
    field: AxisymmetricPlumeField,
    config: RadiationConfig,
) -> AngularSignature:
  ...
####


def solve_plume(config: PlumeSimulationConfig) -> PlumeResult:
  ...
####
```

Lower-level functions should remain independently callable for verification.
The orchestration function must not obscure per-phase statuses.

## 11. Top-level PlumeResult

```python
@dataclass(frozen=True, slots=True)
class PlumeResult:
  nozzle_exit: FlowState
  regime: ExpansionRegime
  first_cell: FirstCellResult | None
  shock_train: ShockTrainResult | None
  integral_plume: IntegralPlumeResult | None
  angular_signature: AngularSignature | None
  overall_status: SolverStatus
  diagnostics: tuple[Diagnostic, ...]
  provenance: Provenance
####
```

A downstream phase may be absent because it was not requested, because an
upstream validity gate blocked it, or because the solve failed. These cases
must be distinguishable by status and diagnostics.

## 12. Serialization contract

### 12.1 Schema version

All serialized top-level inputs and results include:

```json
{
  "schema_version": "2.0"
}
```

A schema version is not the package version. Backward-compatible field
additions may preserve the major schema version. Renames, unit changes, shape
changes, and enum-value changes require a schema migration.

### 12.2 Units

Serialized field names carry units where practical:

```text
static_pressure_Pa
static_temperature_K
x_m
view_angle_rad
```

Do not serialize a bare field named `pressure`, `temperature`, `angle`, or
`length` in a public schema.

### 12.3 Arrays

JSON and YAML use nested lists plus explicit shape metadata for large or
ambiguous arrays:

```json
{
  "shape": [128, 64, 64],
  "axis_order": ["spectral", "v", "u"],
  "values": []
}
```

Large production arrays should use a separate NPZ, NetCDF, HDF5, or Zarr
artifact referenced by URI and checksum rather than enormous inline JSON.
The first implementation may use compressed NPZ, but the file format must be
abstracted behind an artifact writer.

### 12.4 Nonfinite values

Successful serialized results may not contain `NaN`, `Infinity`, or
`-Infinity`. Failed optional values are represented by `null` and a structured
status.

### 12.5 Example input

```yaml
schema_version: "2.0"
gas:
  gamma: 1.33
  molar_mass_kg_per_mol: 0.022
nozzle_exit:
  mach: 4.13
  total_pressure_Pa: 6991425.0
  total_temperature_K: 2000.0
  exit_radius_m: 1.0
  flow_angle_rad: 0.0
  mass_flow_rate_kg_per_s: 250.0
  nozzle_solution_validated: true
ambient:
  static_pressure_Pa: 26436.0
  static_temperature_K: 223.15
  velocity_x_m_per_s: 0.0
  velocity_y_m_per_s: 0.0
first_cell:
  expansion_characteristics: 16
  compression_characteristics: 8
  pressure_match_rtol: 1.0e-4
shock_train:
  max_cells: 20
  max_axial_distance_m: 300.0
  pressure_oscillation_cutoff: 0.01
  mean_pressure_cutoff: 0.01
  coherent_core_diameter_cutoff_ratio: 0.02
  core_mach_cutoff: 1.01
  persistence_cells: 2
  calibration:
    calibration_id: example-not-for-production
    version: "0"
    coherent_core_spreading_rate: 0.05
    cell_spacing_coefficient: 1.306
    pressure_decay_coefficient: 0.25
    initial_shear_layer_thickness_ratio: 0.01
    source_citations: []
    applicability_notes: illustrative placeholder; calibration required
```

The example coefficient values are placeholders and must not become hidden
production defaults.

## 13. Compatibility wrapper contract

The legacy entry point

```python
calculatePlumeZones(...)
```

shall remain available during the deprecation interval. The wrapper shall:

```text
1. Emit one targeted deprecation warning per call site.
2. Construct explicit gas and nozzle configuration.
3. Map num_plumes to max_cells as a safety request, not a physical count.
4. Request the legacy-compatible geometry level.
5. Convert radians back to degrees in legacy fields.
6. Return a compatibility details mapping that includes the new structured
   status and termination reason.
```

It must not claim physical termination when it merely generated the requested
number of cells.

## 14. Exceptions versus result statuses

Raise exceptions for:

```text
programmer errors
schema validation failures
impossible array shapes
unknown enum values
missing required dependencies explicitly requested by configuration
```

Return structured unsuccessful results for:

```text
no physical root
out-of-validity topology
detached shock
no forward intersection
iteration limit
physical or domain termination
```

This preserves inspectable diagnostics for research workflows.

## 15. Acceptance gate

This contract is complete when:

- configuration models reject unknown fields and invalid units/ranges;
- every enum has stable string serialization;
- public numerical results are immutable and fully typed;
- successful results contain no nonfinite values;
- array axis order and units are explicit;
- schema version `2.0` round-trips through JSON/YAML adapters;
- legacy wrappers preserve existing import paths during migration;
- all top-level functions expose structured diagnostics;
- serialization fixtures are covered by regression tests;
- API documentation is generated from the implemented contracts.

<!-- END 14_api_contracts_and_serialization.md -->


---

<!-- BEGIN 15_plume_provider_interface.md -->

# Generic Plume Provider Interface — Unified Version

The authoritative merged interface architecture is now split across:

- [`00_unified_plume_architecture.md`](00_unified_plume_architecture.md)
- [`28_consumer_profiles_and_query_contracts.md`](28_consumer_profiles_and_query_contracts.md)
- [`29_provider_taxonomy_and_composition.md`](29_provider_taxonomy_and_composition.md)
- [`30_provider_contracts_v1.md`](30_provider_contracts_v1.md)
- [`31_unified_conformance_and_testing.md`](31_unified_conformance_and_testing.md)
- [`32_merged_implementation_roadmap.md`](32_merged_implementation_roadmap.md)

## Stable summary

The shock-cell solver is one provider, not the universal plume API.

There are two primary consumer views:

```text
SIGNATURE VIEW
  -> directional spectral radiant intensity

SPATIAL / PHYSICAL VIEW
  -> support, geometry, fields, optical medium, or ray transfer
```

A provider may support either or both. Geometry may be used internally without
being exposed.

The following are orthogonal metadata, not interface hierarchies:

```text
morphology: straight / curved / rotor-washed / general-3d
flow fidelity: empirical / analytical / integral / CFD
radiation fidelity: none / gray / band / line-by-line / non-LTE
execution: CPU / GPU / external, random-access / monotonic, etc.
```

The stable lifecycle is:

```text
provider-specific definition/configuration
  -> PlumeSession
      -> snapshot(provider-specific operating state)
          -> PlumeSnapshot
              -> explicit capability registry
```

The unresolved intrinsic source quantity is

\[
J_\lambda(t,\hat{\mathbf d})
\quad [\mathrm{W\,sr^{-1}\,m^{-1}}],
\]

while resolved ray transfer is

\[
L_{\lambda,out}
=L_{\lambda,source}+T_\lambda L_{\lambda,background}.
\]

A rich spatial/ray provider may derive the unresolved source by

\[
J_\lambda(\hat{\mathbf d})
=\int_{A_\perp}L_{\lambda,source}\,dA_\perp,
\]

but the inverse is not possible in general. A signature-table provider is
therefore a valid high-fidelity provenance provider even though it has no
spatial capability.

For provider chaining, use a conservative neutral cross-section/flux handoff
rather than legacy zone types. Curved providers use the same consumer
capabilities and add provider-specific centerline/environment physics.

<!-- END 15_plume_provider_interface.md -->


---

<!-- BEGIN 16_equation_traceability_matrix.md -->

# Equation Traceability Matrix

## 1. Purpose

Every implemented equation shall have a stable project identifier linking:

```text
mathematical statement
classification
assumptions and validity domain
primary source
implementation symbol
verification test
validation evidence
```

Code docstrings, tests, result diagnostics, and calibration artifacts should
refer to these IDs. This prevents an algebraically similar but semantically
different equation from being substituted without review.

Machine-readable entries are in [`equation_registry.yaml`](equation_registry.yaml).

## 2. Classification

```text
GOVERNING   conservation law or thermodynamic relation under stated assumptions
DERIVED     algebraic consequence of governing equations
CORRELATION reduced-order relation with a documented applicability domain
CLOSURE     unresolved-physics relation containing calibrated parameters
NUMERICAL   numerical representation or acceptance criterion
```

A correlation or closure is never relabeled as a governing equation.

## 3. Source identifiers

| ID | Source family |
|---|---|
| SRC-COMP-001 | Anderson, *Modern Compressible Flow*, 3rd edition |
| SRC-NASA-GRC-001 | NASA Glenn compressible-flow and rocket mass-flow equations |
| SRC-SHOCKCELL-001 | Classical Prandtl/Pack circular shock-cell spacing literature |
| SRC-SHOCKCELL-002 | Finite shear-layer and shock-cell decay literature |
| SRC-NASA-JET-001 | NASA underexpanded-jet flow-structure validation data |
| SRC-RTE-001 | Standard non-scattering LTE radiative-transfer equation |
| SRC-HITRAN-001 | HITRAN definitions and units |
| SRC-HITEMP-001 | HITEMP high-temperature line lists |
| SRC-HAPI-001 | HAPI reference absorption/transmittance/radiance calculations |
| SRC-NASA-IR-001 | NASA heated-plume IR field/image validation data |
| SRC-NASA-CEA-001 | NASA Chemical Equilibrium with Applications |
| SRC-CANTERA-001 | Cantera thermodynamics, kinetics, and transport |

The full provenance, access, and fixture-ingestion requirements are in
[`12_reference_sources.md`](12_reference_sources.md).

## 4. Gas and nozzle equations

| Equation ID | Name | Class | Implementation target | Verification tests | Validity |
|---|---|---|---|---|---|
| GAS-001 | Mixture molecular weight | DERIVED | `models/gas/mixtures.py::molecular_weight_from_mass_fractions` | `GAS-001-A/B/C` | Ideal-gas mixture; known species molecular weights |
| GAS-002 | Mixture specific gas constant | DERIVED | `models/gas/mixtures.py::specific_gas_constant` | `GAS-002-A/B` | \(R=R_u/\bar W\) |
| GAS-003 | Ideal-gas equation | GOVERNING | `models/gas/calorically_perfect.py::density_from_pressure_temperature` | `GAS-003-A/B` | Thermodynamic ideal gas |
| GAS-004 | Calorically perfect sound speed | DERIVED | `models/gas/calorically_perfect.py::speed_of_sound` | `GAS-004-A/B` | Constant \(\gamma\), equilibrium acoustic mode |
| ISO-001 | Stagnation/static temperature ratio | DERIVED | `models/gas/calorically_perfect.py` | `ISO-001-A/B/C` | Steady adiabatic calorically perfect flow |
| ISO-002 | Stagnation/static pressure ratio | DERIVED | same | `ISO-002-A/B/C` | Isentropic path |
| ISO-003 | Stagnation/static density ratio | DERIVED | same | `ISO-003-A/B/C` | Isentropic path |
| NOZ-001 | Area-Mach relation | DERIVED | `models/nozzle/area_mach.py::area_ratio` | `NOZ-001-A/B/C/D` | Quasi-1D, isentropic, calorically perfect |
| NOZ-002 | Compressible mass-flow function | DERIVED | `models/nozzle/mass_flow.py::mass_flux` | `NOZ-002-A/B/C` | Uniform section, same assumptions as NOZ-001 |
| NOZ-003 | Choked throat area | DERIVED | `models/nozzle/mass_flow.py::choked_area` | `NOZ-003-A/B/C` | Choked \(M=1\) throat |
| REG-001 | Exit pressure residual | NUMERICAL | `models/shock_cells/regime.py::classify_regime` | `REG-001-A/B/C/D` | Positive ambient pressure; explicit tolerance |

### GAS-001

\[
\boxed{
\bar W
=
\left(\sum_s\frac{Y_s}{W_s}\right)^{-1}
}
\]

### GAS-002 and GAS-003

\[
\boxed{R=\frac{R_u}{\bar W}},
\qquad
\boxed{p=\rho RT}.
\]

### NOZ-001

\[
\boxed{
\frac{A}{A^*}
=
\frac1M
\left[
\frac{2}{\gamma+1}
\left(1+\frac{\gamma-1}{2}M^2\right)
\right]^{\frac{\gamma+1}{2(\gamma-1)}}
}
\]

### NOZ-003

\[
\boxed{
A^*
=
\frac{\dot m}{p_0}
\sqrt{\frac{RT_0}{\gamma}}
\left(\frac{\gamma+1}{2}\right)^{\frac{\gamma+1}{2(\gamma-1)}}
}
\]

Primary sources: `SRC-COMP-001`, `SRC-NASA-GRC-001`.

## 5. Expansion, characteristics, and shocks

| Equation ID | Name | Class | Implementation target | Verification tests | Validity |
|---|---|---|---|---|---|
| PM-001 | Mach angle | DERIVED | `shock_cells/prandtl_meyer.py::mach_angle` | `PM-001-A/B` | \(M\ge1\) |
| PM-002 | Prandtl-Meyer function | DERIVED | `shock_cells/prandtl_meyer.py::prandtl_meyer` | `PM-002-A/B/C` | 2D/axisymmetric local simple wave, calorically perfect |
| PM-003 | Expansion turn | DERIVED | `shock_cells/prandtl_meyer.py::expansion_turn` | `PM-003-A/B` | Isentropic supersonic expansion |
| MOC-001 | Characteristic slopes | GOVERNING/DERIVED | `shock_cells/planar_characteristics.py` | `MOC-001-A/B/C` | Steady planar supersonic irrotational flow |
| MOC-002 | Planar compatibility invariants | GOVERNING/DERIVED | same | `MOC-002-A/B/C` | Same as MOC-001 |
| MOC-003 | Centerline symmetry | BOUNDARY | `shock_cells/first_cell.py` | `MOC-003-A/B` | Symmetric planar jet |
| MOC-004 | Free-boundary pressure | BOUNDARY | `shock_cells/free_boundary.py` | `MOC-004-A/B/C` | Quiescent constant-pressure ambient first model |
| MOC-005 | Free-boundary streamline slope | BOUNDARY | same | `MOC-005-A/B` | Inviscid material boundary |
| SHK-001 | Theta-beta-M relation | DERIVED | `shock_cells/oblique_shock.py::turn_from_wave_angle` | `SHK-001-A/B/C` | Attached planar oblique shock |
| SHK-002 | Upstream normal Mach | DERIVED | same | `SHK-002-A` | Oblique shock |
| SHK-003 | Static pressure ratio | DERIVED | `shock_cells/normal_shock.py` | `SHK-003-A/B` | Calorically perfect normal component |
| SHK-004 | Static density ratio | DERIVED | same | `SHK-004-A/B` | Same |
| SHK-005 | Downstream Mach | DERIVED | `shock_cells/oblique_shock.py` | `SHK-005-A/B` | Attached shock with \(\beta>\theta\) |
| SHK-006 | Stagnation pressure loss | DERIVED | `shock_cells/normal_shock.py::total_pressure_ratio` | `SHK-006-A/B/C` | Adiabatic calorically perfect shock |
| SHK-007 | Maximum attached turn | NUMERICAL | `shock_cells/oblique_shock.py::maximum_attached_turn` | `SHK-007-A/B/C` | \(M>1\), chosen \(\gamma\) |

### PM-002

\[
\boxed{
\nu(M)
=
\sqrt{\frac{\gamma+1}{\gamma-1}}
\tan^{-1}\sqrt{\frac{\gamma-1}{\gamma+1}(M^2-1)}
-
\tan^{-1}\sqrt{M^2-1}
}
\]

### MOC-001 and MOC-002

\[
\boxed{\frac{dy}{dx}=\tan(\theta\pm\mu)},
\]

\[
\boxed{\theta-\nu=\mathrm{const}\text{ on }C^+},
\qquad
\boxed{\theta+\nu=\mathrm{const}\text{ on }C^-}.
\]

The sign convention must be tested against the chosen coordinate orientation;
code shall not rely on a copied sign without a geometric test.

### SHK-001

\[
\boxed{
\tan\theta
=
2\cot\beta
\frac{M_1^2\sin^2\beta-1}
{M_1^2(\gamma+\cos2\beta)+2}
}
\]

Primary source: `SRC-COMP-001`.

## 6. Geometry and topology

| Equation ID | Name | Class | Implementation target | Verification tests | Validity |
|---|---|---|---|---|---|
| GEO-001 | Forward ray intersection | NUMERICAL | `shock_cells/geometry.py::intersect_rays_2d` | `GEO-001-A..F` | Nondegenerate 2D rays |
| GEO-002 | Polygon signed area | NUMERICAL | `shock_cells/geometry.py::signed_polygon_area` | `GEO-002-A/B/C` | Ordered finite polygon |
| GEO-003 | Polygon self-intersection | NUMERICAL | `shock_cells/geometry.py::validate_simple_polygon` | `GEO-003-A/B/C` | Closed 2D polygon |
| GEO-004 | Precursor centerline intersection | DERIVED | `shock_cells/first_cell.py` | `GEO-004-A/B` | Straight shock line; \(0<\beta<\pi/2\) |

### GEO-001

\[
\mathbf o_1+s_1\mathbf d_1
=
\mathbf o_2+s_2\mathbf d_2,
\qquad
s_1,s_2\ge0.
\]

Acceptance requires bounded residual and condition number.

### GEO-004

\[
\boxed{\Delta x=\frac{R}{\tan\beta}}.
\]

## 7. Shock-cell scale and termination

| Equation ID | Name | Class | Implementation target | Verification tests | Validity |
|---|---|---|---|---|---|
| CELL-001 | Fully expanded jet Mach | DERIVED | `shock_cells/correlations.py::fully_expanded_mach` | `CELL-001-A/B` | Isentropic equivalent state at \(p_a\) |
| CELL-002 | Fully expanded diameter | DERIVED | same | `CELL-002-A/B` | Equal mass flow and total state, circular sections |
| CELL-003 | Classical first-cell spacing | CORRELATION | `shock_cells/correlations.py::prandtl_cell_spacing` | `CELL-003-A/B/C` | Nearly adapted uniform circular jet |
| TRN-001 | Inward mixing-layer growth | CLOSURE | `shock_cells/train.py` | `TRN-001-A/B/C` | Calibrated reduced-order train |
| TRN-002 | Coherent-core diameter | DERIVED/CLOSURE | same | `TRN-002-A/B` | Top-hat core and two-sided inward layer |
| TRN-003 | Pressure-amplitude decay | CLOSURE | same | `TRN-003-A/B/C` | Calibrated positive decay coefficient |
| TRN-004 | Local cell spacing | CORRELATION/CLOSURE | same | `TRN-004-A/B/C` | Within calibration applicability |
| TRN-005 | Persistent termination | NUMERICAL | `shock_cells/termination.py` | `TRN-005-A..E` | Ordered completed-cell metrics |

### CELL-003

\[
\boxed{
L_{s,0}=1.306D_j\sqrt{M_j^2-1}
}
\]

Source: `SRC-SHOCKCELL-001`. Correlation mismatch is diagnostic; it is not
forced into MOC geometry.

### TRN-001 through TRN-003

\[
\delta_i(x)=\delta_{i,0}+S_ix,
\]

\[
D_c(x)=\max[D_j-2\delta_i(x),0],
\]

\[
\boxed{
\frac{dA_p}{dx}=-\frac{C_d}{D_c(x)}A_p
}.
\]

Parameters \(S_i\) and \(C_d\) require a calibration artifact.

## 8. Integral mixing plume

| Equation ID | Name | Class | Implementation target | Verification tests | Validity |
|---|---|---|---|---|---|
| MIX-001 | Entrainment mass rate | CLOSURE | `mixing/entrainment.py` | `MIX-001-A/B/C` | Axisymmetric top-hat integral plume |
| MIX-002 | Axial momentum flux | GOVERNING | `mixing/integral_plume.py` | `MIX-002-A/B/C` | Steady integral control volume |
| MIX-003 | Total enthalpy-flow balance | GOVERNING | same | `MIX-003-A/B/C` | Defined source/sink terms |
| MIX-004 | Species mass-flow balance | GOVERNING | same | `MIX-004-A/B/C` | Frozen or explicit reaction source |
| MIX-005 | Cross-section area recovery | DERIVED | same | `MIX-005-A/B` | Positive \(\rho,u,\dot m\) |

### MIX-001

\[
\boxed{
\frac{d\dot m}{dx}
=
2\pi R\rho_aE|u-u_a|
}
\]

The entrainment coefficient \(E\) is a closure with provenance.

### MIX-002 through MIX-004

\[
\frac{d}{dx}\left[\dot m u+(p-p_a)A\right]=0,
\]

\[
\frac{d}{dx}(\dot m h_0)
=
h_{0a}\frac{d\dot m}{dx}
+\dot Q'_{\mathrm{chem}}-\dot Q'_{\mathrm{rad}},
\]

\[
\frac{d}{dx}(\dot mY_s)
=
Y_{s,a}\frac{d\dot m}{dx}+\dot\omega_sA.
\]

## 9. Radiation

| Equation ID | Name | Class | Implementation target | Verification tests | Validity |
|---|---|---|---|---|---|
| RAD-001 | Planck radiance in wavenumber | GOVERNING/DERIVED | `radiation/planck.py` | `RAD-001-A/B/C/D` | Thermal equilibrium radiation |
| RAD-002 | Non-scattering LTE RTE | GOVERNING | `radiation/radiative_transfer.py` | `RAD-002-A/B` | LTE, absorption/emission, no scattering |
| RAD-003 | Exact uniform-segment transport | DERIVED | same | `RAD-003-A..E` | Constant properties over segment |
| RAD-004 | Mixture absorption coefficient | DERIVED | `radiation/spectroscopy.py` | `RAD-004-A/B/C` | Independent species line absorption |
| RAD-005 | Species number density | DERIVED | same | `RAD-005-A/B` | Ideal gas |
| RAD-006 | Image-to-radiant-intensity integral | DEFINITION | `radiation/radiative_transfer.py` | `RAD-006-A/B/C` | Complete projected source image |
| RAD-007 | Vacuum inverse-square irradiance | DEFINITION/DERIVED | `radiation/sensor.py` | `RAD-007-A/B` | Far field, unresolved source |
| RAD-008 | Spectral-density Jacobian | DERIVED | `radiation/contracts.py` | `RAD-008-A/B/C` | Monotonic wavelength/wavenumber transform |
| RAD-009 | IR-domain contribution cutoff | NUMERICAL | `radiation/radiative_transfer.py` | `RAD-009-A/B/C` | Ordered axial contribution slices |

### RAD-001

For \(\tilde\nu=1/\lambda\) in \(\mathrm{m^{-1}}\),

\[
\boxed{
B_{\tilde\nu}(T)
=
\frac{2hc^2\tilde\nu^3}
{\exp(hc\tilde\nu/k_BT)-1}
}
\]

with spectral density per \(\mathrm{m^{-1}}\).

### RAD-002 and RAD-003

\[
\boxed{
\frac{dI_{\tilde\nu}}{ds}
=-\alpha_{\tilde\nu}I_{\tilde\nu}
+\alpha_{\tilde\nu}B_{\tilde\nu}(T)
}
\]

\[
\boxed{
I_{i+1}
=I_i e^{-\Delta\tau_i}
+B_i(1-e^{-\Delta\tau_i}),
\qquad
\Delta\tau_i=\alpha_i\Delta s_i
}
\]

### RAD-004 and RAD-005

\[
\alpha_{\tilde\nu}
=
\sum_s n_s\sigma_s(\tilde\nu,T,p),
\qquad
n_s=X_s\frac{p}{k_BT}.
\]

Sources: `SRC-HITRAN-001`, `SRC-HITEMP-001`, `SRC-HAPI-001`.

## 10. Thermochemistry and particles

| Equation ID | Name | Class | Implementation target | Verification tests | Validity |
|---|---|---|---|---|---|
| CHEM-001 | Mass/mole fraction conversion | DERIVED | `chemistry/contracts.py` | `CHEM-001-A/B/C` | Defined species molecular weights |
| CHEM-002 | Gibbs minimization equilibrium | GOVERNING/DEFINITION | external CEA/validated adapter | `CHEM-002-A/B/C` | Equilibrium at selected constraints |
| CHEM-003 | Finite-rate species source | GOVERNING/MODEL | `chemistry/finite_rate.py` | `CHEM-003-A/B/C` | Selected mechanism and rate laws |
| CHEM-004 | Chemical energy source | DERIVED | same | `CHEM-004-A/B` | Consistent species enthalpies |
| PART-001 | Particle energy balance | GOVERNING/CLOSURE | `chemistry/particles.py` | `PART-001-A/B/C` | Lumped particle temperature |
| PART-002 | Particle spectral extinction | MODEL | `radiation/particles.py` | `PART-002-A/B/C` | Chosen optical model and size distribution |

### CHEM-002

\[
\min_{n_s\ge0}\sum_s n_s\mu_s
\quad\text{subject to}\quad
\sum_s a_{ks}n_s=b_k.
\]

### CHEM-003

\[
\dot\omega_s
=W_s\sum_r(\nu''_{sr}-\nu'_{sr})q_r.
\]

Sources: `SRC-NASA-CEA-001`, `SRC-CANTERA-001`.

## 11. Traceability rules for code

Every implementation function for a registered equation shall include:

```text
Equation IDs
assumptions
input/output units
branch or root selection
failure modes
primary source ID
```

Example docstring fragment:

```python
def calc_choked_area(...) -> float:
  """Calculate sonic throat area.

  Equations:
    NOZ-002, NOZ-003.
  Assumptions:
    Quasi-one-dimensional, isentropic, calorically perfect ideal gas.
  Units:
    SI.
  Sources:
    SRC-COMP-001, SRC-NASA-GRC-001.
  """
  ...
####
```

Tests shall include the equation ID in the test docstring or parameter-case ID.

## 12. Change-control rule

Changing a registered equation requires all of:

1. Update the equation registry.
2. Add or supersede an ADR when semantics change.
3. Update source provenance.
4. Update analytic verification cases.
5. Re-run dependent conservation and validation cases.
6. Record expected regression changes.
7. Increment the affected model or calibration version.

A numerical refactor that preserves the equation may retain the same equation
ID but must demonstrate equivalence within tolerance.

<!-- END 16_equation_traceability_matrix.md -->


---

<!-- BEGIN 17_numerical_algorithms_and_pseudocode.md -->

# Numerical Algorithms and Pseudocode Specification

## 1. Purpose

This document turns the governing equations in the architecture and physics
plans into deterministic numerical procedures. It is normative for root
bracketing, geometry, characteristic marching, shock-cell iteration, mixing
integration, and line-of-sight radiative transfer.

The coding agent shall not replace a bracketed or bounded algorithm with an
unbounded Newton iteration merely because the latter is shorter. Every solver
must return structured convergence information rather than logging an error and
continuing with an approximate state.

## 2. Common numerical contract

Every numerical operation shall return a result containing at least:

```text
status
value
converged
iterations
residual_absolute
residual_relative
bracket_or_domain
warnings
```

Recommended generic status values are:

```text
CONVERGED
CONVERGED_AT_BOUNDARY
INVALID_INPUT
NO_BRACKET
OUTSIDE_PHYSICAL_DOMAIN
ILL_CONDITIONED
MAX_ITERATIONS
NONFINITE_RESULT
DETACHED_SHOCK_REQUIRED
NO_FORWARD_INTERSECTION
```

### 2.1 Residual normalization

For a scalar equation

\[
f(x)=0,
\]

define

\[
r_{\mathrm{abs}}=|f(x)|,
\]

and

\[
r_{\mathrm{rel}}
=
\frac{|f(x)|}{\max(s_f,\epsilon_f)},
\]

where \(s_f\) is a problem-specific scale. A solution is accepted only when
both the state increment and the normalized residual satisfy configured
criteria.

### 2.2 Tolerance hierarchy

Use separate tolerances for:

```text
state_rtol
state_atol
angle_atol_rad
geometry_atol_m
residual_rtol
residual_atol
condition_number_max
max_iterations
```

Do not use one global tolerance for pressure, angle, position, and spectral
radiance.

### 2.3 Finite-value rule

Inputs and outputs must be finite unless the public contract explicitly allows
an infinite asymptotic limit. Intermediate `NaN` values may be used privately
to detect a failed operation, but they must not appear in a successful public
result.

## 3. Scalar root-solving policy

Use `scipy.optimize.brentq` or an equivalent safeguarded bracketed method when
a continuous scalar residual has a known sign-changing interval.

Algorithm:

```text
1. Validate finite lower and upper bounds with lower < upper.
2. Evaluate f(lower) and f(upper).
3. Accept an endpoint only when its residual passes the configured test.
4. If the endpoint residuals do not bracket a sign change, return NO_BRACKET.
5. Run the bounded solver.
6. Re-evaluate the physical-domain constraints at the returned root.
7. Return root, residuals, iterations, and the final bracket.
```

Unbracketed Newton or secant methods may be used only as local accelerators
inside a safeguarded outer method and must never be the sole convergence path
for public physics solvers.

## 4. Supersonic area--Mach inversion

Define

\[
\mathcal A(M;\gamma)
=
\frac{1}{M}
\left[
\frac{2}{\gamma+1}
\left(1+\frac{\gamma-1}{2}M^2\right)
\right]^{\frac{\gamma+1}{2(\gamma-1)}}.
\]

For a requested ratio \(A/A^*\ge 1\), solve

\[
f(M)=\mathcal A(M;\gamma)-\frac{A}{A^*}=0.
\]

### 4.1 Subsonic branch

Use

\[
M\in(M_{\min},1),
\]

with a small positive \(M_{\min}\). The branch is monotone over this interval.

### 4.2 Supersonic branch

Use

\[
M\in(1,M_{\max}).
\]

Find \(M_{\max}\) by geometric expansion:

```text
M_high = 2
while A(M_high) < requested_ratio:
    M_high *= 2
    fail when M_high exceeds configured physical or numerical limit
```

The public API must require the branch explicitly. It must never infer a branch
from a starting guess.

### 4.3 Exact sonic ratio

When

\[
\left|A/A^*-1\right|\le\epsilon_A,
\]

return \(M=1\) with `CONVERGED_AT_BOUNDARY`.

## 5. Prandtl--Meyer inversion

For \(M\ge1\), define

\[
\nu(M)
=
\sqrt{\frac{\gamma+1}{\gamma-1}}
\tan^{-1}
\sqrt{\frac{\gamma-1}{\gamma+1}(M^2-1)}
-
\tan^{-1}\sqrt{M^2-1}.
\]

The maximum angle is

\[
\nu_{\max}
=
\frac{\pi}{2}
\left(
\sqrt{\frac{\gamma+1}{\gamma-1}}-1
\right).
\]

Given \(\nu_t\):

```text
1. Reject nu_t < 0 or nu_t > nu_max plus tolerance.
2. Return M = 1 when nu_t is approximately zero.
3. Set M_low = 1 + epsilon_M.
4. Expand M_high geometrically until nu(M_high) >= nu_t.
5. Solve nu(M) - nu_t = 0 with a bracketed method.
6. Verify M >= 1 and the angle residual.
```

The implementation shall expose the residual in radians even if a compatibility
wrapper accepts degrees.

## 6. Theta--beta--Mach solution

Define

\[
g(\beta;M,\gamma)
=
\tan^{-1}
\left[
2\cot\beta
\frac{M^2\sin^2\beta-1}
{M^2(\gamma+\cos2\beta)+2}
\right].
\]

The physical interval is

\[
\mu<\beta<\frac{\pi}{2},
\qquad
\mu=\sin^{-1}(1/M).
\]

### 6.1 Maximum attached turn

Calculate

\[
\theta_{\max}
=
\max_{\beta\in(\mu,\pi/2)}g(\beta).
\]

Use a bounded scalar maximization of \(-g\), preceded by a coarse deterministic
scan to establish a stable bounded interval around the maximum. Return both
\(\theta_{\max}\) and \(\beta_{\mathrm{peak}}\).

### 6.2 Weak and strong roots

For requested \(\theta\):

```text
if theta < 0:
    return INVALID_INPUT
if theta approximately 0:
    weak beta = Mach angle
    strong beta = pi / 2
if theta > theta_max plus tolerance:
    return DETACHED_SHOCK_REQUIRED
weak root bracket  = [mu + eps, beta_peak]
strong root bracket = [beta_peak, pi / 2 - eps]
solve g(beta) - theta = 0 on the requested branch
```

This explicitly fixes the current behavior in which both zero-turn branches
are forced to a normal shock.

## 7. Shock to a target static pressure

For an upstream state and desired pressure ratio

\[
R_p=\frac{p_2}{p_1}\ge1,
\]

the normal-shock pressure equation gives

\[
M_{n1}^2
=
1+
(R_p-1)\frac{\gamma+1}{2\gamma}.
\]

Therefore

\[
\beta
=
\sin^{-1}\left(\frac{M_{n1}}{M_1}\right).
\]

This direct construction is preferred over a nested pressure-angle bisection.
The algorithm is:

```text
1. Reject target pressure below upstream pressure.
2. Compute the maximum normal-shock pressure ratio at beta = pi / 2.
3. Reject a target above that limit.
4. Compute Mn1 from the requested pressure ratio.
5. Compute beta = asin(Mn1 / M1).
6. Compute theta from the theta--beta--Mach equation.
7. Compute beta_peak and theta_max.
8. If beta > beta_peak plus tolerance, classify the state as strong branch.
9. If only weak attached shocks are permitted, reject a strong-branch target.
10. Build the downstream state and verify the pressure residual and total-
    pressure loss.
```

The result must record `WEAK`, `STRONG`, or `DETACHED_REQUIRED` explicitly.

## 8. Two-dimensional forward-ray intersection

Represent each ray as

\[
\mathbf x_i(s_i)=\mathbf o_i+s_i\mathbf d_i,
\qquad s_i\ge0.
\]

Solve

\[
\begin{bmatrix}
 d_{1x} & -d_{2x}\\
 d_{1y} & -d_{2y}
\end{bmatrix}
\begin{bmatrix}s_1\\s_2\end{bmatrix}
=
\mathbf o_2-\mathbf o_1.
\]

### 8.1 Conditioning

Let the matrix be \(A\). Reject when

\[
\kappa_2(A)>\kappa_{\max}
\]

or when the determinant magnitude is below a scale-aware threshold.

The default successful path shall use a direct 2-by-2 solve, not a
pseudoinverse. A least-squares result may be returned only as a failed
diagnostic.

### 8.2 Forward constraint

Accept only when

\[
s_1\ge-\epsilon_s,
\qquad
s_2\ge-\epsilon_s.
\]

Clamp a parameter to zero only when it lies within tolerance of zero.

### 8.3 Residual

Report

\[
r_x
=
\left\|
\mathbf o_1+s_1\mathbf d_1
-
\mathbf o_2-s_2\mathbf d_2
\right\|_2.
\]

The result contract shall include the point, both ray parameters, determinant,
condition number, and residual.

## 9. Legacy line--parabola intersection

The fitted parabola is temporary compatibility behavior. While it remains:

```text
1. Parameterize the line as a ray, not as a global y = mx + b line.
2. Substitute x(s), y(s) into the polynomial.
3. Solve the resulting scalar polynomial for s.
4. Discard complex roots above tolerance.
5. Discard s < -epsilon_s.
6. Select the smallest forward s, not the smallest positive global x.
7. Return all candidate roots in diagnostics.
```

This prevents a valid-looking intersection on the wrong branch or behind the
origin.

## 10. Planar characteristic interior point

Suppose point \(A\) emits a \(C^+\) characteristic and point \(B\) emits a
\(C^-\) characteristic.

The invariants are

\[
K_+=\theta_A-\nu_A,
\qquad
K_-=\theta_B+\nu_B.
\]

The intersection state is

\[
\theta_P=\frac{K_++K_-}{2},
\qquad
\nu_P=\frac{K_--K_+}{2}.
\]

Invert \(\nu_P\) to obtain \(M_P\) and

\[
\mu_P=\sin^{-1}(1/M_P).
\]

Use averaged endpoint slopes:

\[
\psi_+
=
\frac{(\theta_A+\mu_A)+(\theta_P+\mu_P)}{2},
\]

\[
\psi_-
=
\frac{(\theta_B-\mu_B)+(\theta_P-\mu_P)}{2}.
\]

Then intersect the two forward rays.

Pseudocode:

```text
compute K_plus and K_minus
compute theta_P and nu_P
invert nu_P to M_P
compute mu_P
initialize point from source-state slopes
repeat:
    compute averaged characteristic directions
    intersect forward rays
    compare position update with geometry tolerance
until converged or max iterations
verify state invariants and intersection residual
```

Because the state is fixed by compatibility for a planar calorically perfect
flow, only the geometry normally requires fixed-point iteration.

## 11. Centerline characteristic point

At the centerline,

\[
y=0,
\qquad
\theta=0.
\]

For a \(C^+\) line with invariant \(K_+=\theta-\nu\),

\[
\nu_c=-K_+.
\]

For a \(C^-\) line with invariant \(K_-=\theta+\nu\),

\[
\nu_c=K_-.
\]

Algorithm:

```text
1. Apply the appropriate compatibility invariant.
2. Set theta_c = 0 exactly.
3. Invert nu_c to M_c.
4. Use the averaged incoming characteristic angle.
5. Intersect the characteristic with y = 0 as a forward ray.
6. Verify x_c is downstream and the invariant residual passes.
```

A geometric reflection matrix alone is not a centerline state solution.

## 12. Ambient-pressure free-boundary point

The free boundary satisfies

\[
p_b=p_a,
\qquad
\frac{dy_b}{dx}=\tan\theta_b.
\]

For a calorically perfect isentropic boundary with known stagnation pressure,
calculate \(M_b\) from \(p_0/p_a\), then \(\nu_b\).

For an incoming \(C^+\) characteristic carrying \(K_+\),

\[
\theta_b=K_++\nu_b.
\]

For an incoming \(C^-\) characteristic carrying \(K_-\),

\[
\theta_b=K_--\nu_b.
\]

Given the previous boundary point \(B_0\), solve the intersection of:

- the incoming characteristic ray from interior point \(A\); and
- the boundary tangent ray from \(B_0\).

Use averaged slopes between the old and new endpoint states and iterate until
both position and pressure/compatibility residuals converge.

## 13. First-cell assembly

The first-cell implementation shall be decomposed into pure operations:

```text
classify regime
construct exit state
construct initial lip wave or fan
march characteristic points to centerline
apply centerline compatibility
march reflected characteristics to free boundary
apply free-boundary compatibility
construct compression or shock closure
validate closed-zone topology
compute diagnostics and correlation comparison
```

### 13.1 Underexpanded case

```text
1. Compute the ambient-pressure boundary Mach and required PM turn.
2. Discretize the expansion into N characteristic states.
3. March the initial fan to the centerline.
4. Reflect through compatibility, not coordinate reflection alone.
5. March to the ambient-pressure free boundary.
6. Construct the recompression system.
7. Close the cell only when all boundaries intersect forward and all zones
   have positive area.
```

### 13.2 Mild attached overexpanded case

```text
1. Solve the lip shock needed to raise pressure toward ambient.
2. Reject when the required shock is detached or on a disallowed strong branch.
3. Intersect the shock with the centerline using delta_x = R / tan(beta).
4. Apply centerline shock/compatibility conditions.
5. Continue with the characteristic/free-boundary solve.
6. Reject when nozzle separation invalidates the supplied uniform exit state.
```

## 14. Closed-zone topology validation

For every closed polygon:

```text
finite coordinates
at least three distinct vertices
nonzero signed area
consistent winding
no nonadjacent edge intersection
no edge with length below tolerance
all vertices within the configured domain
```

The signed area is

\[
A
=
\frac12
\sum_i
(x_i y_{i+1}-x_{i+1}y_i).
\]

A successful zone collection must use one consistent winding convention.

## 15. Shock-train iteration

Pseudocode:

```text
cells = [validated_first_cell]
metrics = metrics(first_cell)
state = first_cell.exit_state
x = first_cell.x_end

while True:
    reason = evaluate_physical_termination(metrics, state, x)
    if reason is not None:
        return physical result

    reason = evaluate_safety_limits(cell_count, x)
    if reason is not None:
        return truncated result

    core = update_coherent_core(state, x, calibration)
    spacing = calculate_local_spacing(core, calibration)
    amplitude = integrate_amplitude_decay(metrics.amplitude, spacing)
    next_state = propagate_mean_state_and_total_pressure_loss(state)
    next_cell = construct_reduced_or_resolved_cell(...)

    validate next_cell and diagnostics
    append next_cell
    update x, state, metrics
```

The physical termination test must run before generating the next cell. The
safety-limit result must remain distinguishable from a physical endpoint.

## 16. Integral mixing-plume integration

The state vector should use conservative or positivity-preserving variables,
for example

\[
\mathbf q
=
\left[
\dot m,
\mathcal M,
\mathcal H,
\dot mY_1,\ldots,\dot mY_{N_s-1}
\right],
\]

where

\[
\mathcal M=\dot m u+(p-p_a)A,
\qquad
\mathcal H=\dot m h_0.
\]

At each ODE evaluation:

```text
1. Recover species fractions and final dependent species.
2. Recover thermodynamic state from mass, momentum, and enthalpy invariants.
3. Reject negative density, temperature, area, or species fractions outside
   configured projection tolerance.
4. Evaluate entrainment and optional chemistry/radiation source terms.
5. Return derivatives and event functions.
```

Use `scipy.integrate.solve_ivp` with explicit event functions for velocity,
temperature, composition, and domain termination. Record the solver method,
tolerances, rejected steps, and event that ended the integration.

## 17. Axisymmetric ray-segment construction

For each image-plane ray:

```text
1. Intersect the ray with the plume domain bounding volume.
2. Find every crossing with axial/radial cell boundaries.
3. Sort unique path parameters s.
4. Form intervals between adjacent crossings.
5. Sample the midpoint of each interval to identify the owning field cell.
6. Drop zero-length or outside-domain intervals.
7. Return ordered back-to-front segments with path length and local state.
```

Analytic cylinder and conical-frustum intersections should be used where
possible. General polygon-of-revolution intersections require deterministic
root finding and duplicate-root merging.

## 18. Radiative-transfer marching

For each spectral coordinate and ordered segment,

\[
I_{i+1}
=
I_i e^{-\Delta\tau_i}
+B_i\left(1-e^{-\Delta\tau_i}\right).
\]

Numerically stable implementation:

```text
transmittance = exp(-tau)
source_weight = -expm1(-tau)
I = I * transmittance + B * source_weight
```

Use `expm1` so the optically thin limit does not lose precision.

Vectorize over spectral coordinates. Chunk over rays or wavelengths when the
full array would exceed the configured memory budget.

## 19. Spectral cross-section interpolation

Cross-section tables use axes such as

```text
species
wavenumber
log_temperature or temperature
log_pressure or pressure
broadener composition id
```

Interpolation requirements:

```text
no extrapolation without an explicit policy
nonnegative interpolated cross sections
metadata-preserving unit conversion
bounded interpolation error checked against direct reference calculations
cache key includes database version, isotopologue policy, line profile,
wing cutoff, grid, T, p, and broadener definition
```

Interpolation should usually operate on the logarithm of positive cross
sections with a documented floor, followed by nonnegative reconstruction.

## 20. Determinism and reproducibility

All algorithms must be deterministic for fixed inputs unless uncertainty
sampling is explicitly enabled. Monte Carlo paths shall accept and record a
random seed.

A result artifact shall record:

```text
code version
input schema version
model level
solver tolerances
calibration id
spectroscopy database version
random seed when applicable
```

## 21. Acceptance gate

This numerical specification is implemented when:

- every public root solve is bracketed or bounded;
- physical-domain failures are structured statuses;
- the weak/strong shock branches are explicit;
- all geometry intersections enforce forward-ray constraints;
- MOC state compatibility and geometry residuals are separately reported;
- shock-train physical termination is distinct from safety truncation;
- mixing ODE events are explicit and tested;
- RTE marching uses the exact segment solution and stable thin-limit math;
- deterministic regression tests reproduce identical results for identical
  inputs;
- `pytest`, `ruff`, `pyright`, and package build checks pass.

<!-- END 17_numerical_algorithms_and_pseudocode.md -->


---

<!-- BEGIN 18_scientific_data_and_calibration_plan.md -->

# Calibration, Uncertainty, and Scientific-Data Plan

## 1. Purpose

The reduced-order model contains closures that cannot be determined from the
Euler equations alone. This document prevents those closures from becoming
anonymous constants tuned against the same cases later presented as validation.

The goals are:

- trace every coefficient to data and code;
- separate calibration from validation;
- preserve measurement and model uncertainty;
- detect unidentifiable parameters;
- make every fitted result reproducible;
- propagate uncertainty into cell count, plume length, and IR signature.

## 2. Quantities that require calibration or external data

### 2.1 Shock-train closures

Candidate parameters include:

```text
inward shear-layer spreading rate                 S_i
cell-spacing correction relative to baseline      C_lambda
pressure-oscillation decay coefficient             C_d
mean-pressure relaxation coefficient               C_pbar
total-pressure loss continuation coefficient       C_p0
core-Mach continuation parameters                  model-specific
Mach-disk topology threshold or classifier         model-specific
```

The classical first-cell coefficient is a correlation benchmark. Any modified
coefficient used downstream must be treated as calibrated.

### 2.2 Integral-plume closures

```text
entrainment coefficient                            E
profile-shape parameters                           beta_u, beta_T, beta_Y
ambient coflow correction                          model-specific
compressibility correction                         model-specific
turbulent Schmidt/Prandtl surrogates                model-specific
```

### 2.3 Radiation closures or external tables

```text
gray absorption coefficient                        calibration-only test model
cross-section interpolation floor                  numerical metadata
narrow-band or correlated-k parameters             table provenance
atmospheric transmission model                     external source
sensor spectral response                           manufacturer/user source
```

### 2.4 Chemistry and particles

```text
reaction mechanism and version
mixing/chemistry coupling approximation
particle size distribution
particle complex refractive index
particle emissivity/absorption/scattering model
nucleation, growth, oxidation, and breakup closures
```

## 3. Scientific data record

Every imported dataset receives an immutable manifest.

```yaml
dataset_id: nasa_example_campaign_case_set_v1
kind: flow_structure
source:
  title: "..."
  organization: "..."
  persistent_identifier: "..."
  access_date: "YYYY-MM-DD"
  license_or_use_note: "..."
files:
  - path: raw/source_file.ext
    sha256: "..."
coordinate_system: axial_radial
units:
  x: m
  pressure: Pa
operating_conditions:
  nozzle_exit_mach: "column or scalar"
  pressure_ratio_definition: "explicit definition"
measurement_uncertainty:
  pressure_relative: "value or unknown"
processing:
  script: tools/validation/ingest_example.py
  commit: "git sha"
  output_sha256: "..."
allowed_uses:
  calibration: true
  validation: false
notes: "..."
```

Unknown measurement uncertainty must be recorded as unknown, not silently set
to zero.

## 4. Data directory layout

Recommended repository layout:

```text
validation_data/
  manifests/
    <dataset_id>.yaml
  analytic/
    small generated fixtures
  processed/
    small versioned CSV/NPZ fixtures
  large_data_manifest/
    content hashes and retrieval instructions

tools/
  validation/
    ingest_<dataset>.py
    calibrate_shock_train.py
    validate_shock_train.py
    calibrate_integral_plume.py
    validate_radiation.py
```

Do not place large source datasets in the package wheel. Small processed
fixtures may be checked into the repository when licensing permits.

## 5. Operating-condition identity

Every case must define pressure ratios unambiguously. Distinguish at least:

```text
nozzle pressure ratio              p_0 / p_a
exit pressure ratio                p_e / p_a
fully expanded pressure condition  p_j = p_a
```

Also record:

```text
M_e
D_e or equivalent diameter
gamma or mixture model
T_e / T_a
rho_e / rho_a
ambient Mach/coflow velocity
boundary-layer or shear-layer thickness when available
nozzle geometry and exit profile source
```

A case lacking the quantities required by a closure may still be used for
qualitative comparison but not parameter fitting.

## 6. Calibration/validation split

Split by independent physical cases, not by randomly dividing points from the
same trace.

Preferred hierarchy:

1. Hold out complete operating conditions.
2. Hold out complete test campaigns or facilities.
3. Hold out a pressure-ratio range.
4. Only when data are scarce, hold out complete repeated runs.

Never fit coefficients to a centerline-pressure trace and claim validation
against other points on that same trace.

Dataset manifests must state one of:

```text
CALIBRATION
VALIDATION
QUALITATIVE_ONLY
```

A change in role requires a new calibration record.

## 7. Calibration parameter contract

```python
class CalibrationParameter(BaseModel):
    name: str
    transform: ParameterTransform
    lower_bound: float
    upper_bound: float
    initial_value: float
    units: str
    description: str
    ####
```

Positive parameters should normally be fitted in log space:

\[
z=\ln c,
\qquad c=e^z.
\]

Bounded fractions may use a logistic transformation. Do not let the optimizer
explore physically impossible values and then clip the result.

## 8. Observable definitions

Calibrate against directly interpretable observables rather than internal
state variables that were not measured.

### 8.1 Flow structure

```text
first-cell length / D_j
subsequent cell boundaries / D_j
maximum plume radius / D_j
centerline pressure extrema / p_a
pressure-oscillation amplitude
Mach-disk location and diameter, when topology applies
supersonic-core length / D_j
```

### 8.2 Mixing plume

```text
centerline velocity / exit velocity
centerline temperature ratio
plume half-width / D_j
species mole or mass fraction
mass-flow growth
```

### 8.3 Radiation

```text
spectral radiance at calibrated pixels
band-integrated radiant intensity
image radial/axial profiles
angular signature
spectral line or band ratios
```

Comparisons must preserve the measurement instrument's spatial, spectral, and
temporal response where known.

## 9. Normalized residuals

For scalar observation \(y_i\) with measurement standard uncertainty
\(\sigma_{m,i}\) and numerical uncertainty \(\sigma_{n,i}\), use

\[
r_i
=
\frac{y_i^{model}-y_i^{obs}}
{\sqrt{\sigma_{m,i}^2+\sigma_{n,i}^2+\sigma_{floor,i}^2}}.
\]

The floor represents documented unresolved discrepancy or prevents one
nominally zero uncertainty from dominating. It must be reported and subjected
to sensitivity analysis.

Weighted least-squares objective:

\[
J(\boldsymbol\theta)
=
\frac12
\sum_i w_i r_i^2.
\]

Weights are chosen before inspecting validation performance and are recorded in
the calibration artifact.

For a full covariance matrix \(\mathbf\Sigma\), use

\[
J
=
\frac12
\mathbf e^T\mathbf\Sigma^{-1}\mathbf e.
\]

Do not assume independent pixels or spectral bins when the measurement system
creates strong correlations.

## 10. Calibration stages

Calibrate in dependency order.

### Stage C0 — First-cell scale only

Fit or verify no free parameters if the first cell is governed by the selected
MOC model. Compare against the classical spacing correlation and held-out data.
Do not use downstream decay parameters here.

### Stage C1 — Shock-train spacing and decay

Fit:

```text
S_i
C_lambda adjustment, if required
C_d
optional mean-pressure relaxation
```

Use cell boundaries and centerline pressure amplitudes. Hold out complete
operating conditions.

### Stage C2 — Integral mixing

Fit entrainment and profile parameters using velocity, temperature, width, and
species measurements downstream of the coherent core. Do not re-fit shock-cell
parameters unless a joint model is explicitly justified.

### Stage C3 — Radiation transport

Do not tune molecular line strengths. Validate spectroscopy against source
tools. Calibration may cover instrument response, uncertain background, or a
reduced gray/narrow-band surrogate, with clear separation from fundamental
spectroscopic data.

### Stage C4 — Chemistry and particles

Calibrate only closure quantities not defined by the selected kinetic
mechanism or optical-property source. Hold out propellant conditions or test
campaigns where possible.

## 11. Optimizer policy

Start with deterministic bounded optimization:

```text
scipy.optimize.least_squares
loss = linear for well-characterized Gaussian residuals
robust loss only when justified and documented
```

Run multiple initial points within the admissible parameter domain. Report:

```text
initial points
successful/failed solves
final objective
active bounds
Jacobian condition metrics
parameter correlation
```

A single optimizer result without start-point sensitivity is insufficient.

## 12. Identifiability and sensitivity

Calculate local scaled sensitivity:

\[
S_{ij}
=
\frac{\partial \ln y_i}{\partial \ln \theta_j}
\]

for positive quantities, or an appropriately scaled finite-difference analogue.

Inspect the singular values of the weighted Jacobian. Parameters with nearly
collinear effects should be:

- fixed from independent evidence;
- combined into a lower-dimensional parameter;
- assigned broader uncertainty;
- or removed from the current model.

Do not report precise estimates for unidentifiable coefficients.

## 13. Numerical uncertainty

Before calibration, establish discretization uncertainty for each observable.
Use at least three refinements and estimate an error bound or convergence band.

Examples:

```text
MOC characteristic count
ODE tolerance and output step
ray/image grid
spectral grid and cross-section table resolution
```

Calibration must not fit coefficients to compensate for unresolved numerical
error.

## 14. Parameter uncertainty

At minimum, estimate covariance from the calibrated Jacobian when assumptions
are defensible:

\[
\operatorname{Cov}(\hat\theta)
\approx
s^2
(\mathbf J^T\mathbf W\mathbf J)^{-1}.
\]

For nonlinear or bounded cases, prefer profile likelihood, bootstrap across
independent cases, or Bayesian sampling.

The selected method and assumptions are part of the calibration artifact.

## 15. Forward uncertainty propagation

For uncertain inputs and calibration parameters \(\mathbf z\), propagate to
outputs \(g(\mathbf z)\) using one of:

```text
linear covariance propagation for small uncertainties
Latin hypercube or Sobol sampling
Monte Carlo sampling
polynomial/surrogate model after direct-solver verification
```

Required output summaries:

```text
median or nominal value
5th and 95th percentiles, or configured interval
probability of each termination reason
cell-count distribution
shock-train endpoint distribution
IR band-signal distribution versus angle
```

Cell count and termination reason are discrete; do not summarize them only by a
mean.

## 16. Model discrepancy

Measurement uncertainty, parameter uncertainty, and model discrepancy are
different quantities.

Use validation residuals to characterize discrepancy over the documented
applicability domain. Do not hide systematic error by inflating measurement
uncertainty.

A result should distinguish:

```text
input uncertainty
calibration parameter uncertainty
numerical uncertainty
observed validation discrepancy
unmodeled-physics validity flags
```

## 17. Calibration artifact

Each fitted model produces a content-addressed artifact:

```yaml
calibration_id: shock_train_round_jet_v1
model_kind: reduced_shock_train
code_commit: "..."
configuration_schema_version: "1.0"
parameter_values:
  inward_spreading_rate: "..."
  pressure_decay_coefficient: "..."
parameter_covariance_file: covariance.npy
calibration_datasets:
  - dataset_a
validation_datasets:
  - dataset_b
objective_definition: objective.yaml
optimizer:
  method: scipy_least_squares
  settings: {}
fit_metrics: {}
validation_metrics: {}
applicability:
  exit_mach: [lower, upper]
  pressure_ratio: [lower, upper]
  temperature_ratio: [lower, upper]
files:
  covariance.npy: "sha256"
  objective.yaml: "sha256"
```

The identifier should change whenever data, code, objective, or fitted values
change.

## 18. Applicability checks

Before using a calibration, compare the requested case to its applicability
bounds. Return:

```text
INSIDE_CALIBRATION_DOMAIN
NEAR_DOMAIN_BOUNDARY
OUTSIDE_CALIBRATION_DOMAIN
```

Outside-domain use requires an explicit caller override and produces a validity
flag in all downstream results.

## 19. Reproducibility commands

Every calibration directory contains exact commands, for example:

```bash
python -m tools.validation.ingest_example --manifest validation_data/manifests/example.yaml
python -m tools.validation.calibrate_shock_train --config calibration/shock_train_v1.yaml
python -m tools.validation.validate_shock_train --calibration calibration/shock_train_v1/result.yaml
```

The command records:

```text
Python version
package version and git commit
dependency lock or environment export
platform
random seed
input hashes
output hashes
```

## 20. Acceptance gate

- [ ] Every closure parameter has units, bounds, and physical meaning.
- [ ] Calibration and validation cases are disjoint.
- [ ] Dataset files are hashed and sourced.
- [ ] Pressure-ratio definitions are explicit.
- [ ] Numerical convergence is established before fitting.
- [ ] Multiple optimizer starts are reported.
- [ ] Identifiability is assessed.
- [ ] Parameter uncertainty is reported.
- [ ] Forward uncertainty reaches cell count, endpoints, and IR outputs.
- [ ] Applicability bounds are machine-checkable.
- [ ] The calibration is reproducible without network access during tests.

<!-- END 18_scientific_data_and_calibration_plan.md -->


---

<!-- BEGIN 19_uncertainty_and_sensitivity_methods.md -->

# Calibration, Uncertainty, and Sensitivity Plan

## 1. Purpose

The shock-train decay, turbulent entrainment, reduced-order radial profiles,
and some particle models require empirical closure coefficients. This document
defines how those coefficients are estimated, versioned, validated, and
propagated into reported uncertainty.

A value copied from a paper or adjusted until a plot looks plausible is not a
production calibration unless its source, units, applicability, objective
function, uncertainty, and validation evidence are recorded.

## 2. Uncertainty categories

Keep the following categories separate.

### 2.1 Numerical uncertainty

Caused by finite characteristic count, grid spacing, ODE tolerances, spectral
resolution, ray count, interpolation, and iterative convergence.

### 2.2 Parametric uncertainty

Caused by uncertain measured or supplied inputs such as:

```text
exit pressure
exit temperature
mass flow
exit diameter
ambient state
species fractions
sensor range and angle
```

### 2.3 Closure uncertainty

Caused by empirical parameters such as:

```text
coherent-core spreading rate
pressure-amplitude decay coefficient
cell-spacing correction
entrainment coefficient
radial-profile width
particle size-distribution parameters
```

### 2.4 Model-form uncertainty

Caused by omitted physics or approximations such as:

```text
planar instead of axisymmetric characteristics
uniform instead of profiled nozzle exit
frozen instead of reacting chemistry
gray instead of spectral radiation
neglected particles
quiescent instead of moving ambient
```

Model-form uncertainty shall not be disguised as a narrow parameter confidence
interval.

### 2.5 Measurement uncertainty

Comes from experimental instruments, image extraction, calibration, spatial
registration, and reported confidence intervals.

## 3. Calibration parameter registry

Every calibratable parameter shall have a registry entry:

```text
parameter_id
symbol
units
model module
physical interpretation
allowed range
transformation used during optimization
nominal value
prior or regularization
source data ids
applicability range
covariance group
version introduced
```

### 3.1 Initial shock-train parameters

Recommended registry entries:

| ID | Symbol | Meaning |
|---|---:|---|
| `shock.core_spreading_rate` | \(S_i\) | Inward coherent-core shear-layer growth per axial distance. |
| `shock.spacing_coefficient` | \(C_\lambda\) | Local cell-spacing coefficient. |
| `shock.pressure_decay` | \(C_d\) | Pressure-oscillation amplitude decay coefficient. |
| `shock.initial_shear_ratio` | \(\delta_0/D_j\) | Initial shear-layer thickness ratio. |
| `shock.total_pressure_loss_scale` | \(C_{p0}\) | Optional reduced-order correction to cell-averaged loss. |

### 3.2 Initial integral-plume parameters

| ID | Symbol | Meaning |
|---|---:|---|
| `mixing.entrainment` | \(E\) | Ambient entrainment coefficient. |
| `mixing.velocity_shape` | \(C_u\) | Radial velocity-profile shape or width. |
| `mixing.temperature_shape` | \(C_T\) | Radial temperature-profile shape or width. |
| `mixing.species_shape` | \(C_Y\) | Radial mixture-fraction profile shape or width. |

Molecular spectroscopic line strengths shall not be treated as free plume-fit
parameters. Database uncertainty may be propagated, but arbitrary opacity
multipliers require explicit justification and shall be labeled model
corrections.

## 4. Calibration data contract

Each observation record shall include:

```text
case_id
source_id
facility and configuration
independent variables
measured quantity
measurement location or image coordinates
value
units
standard uncertainty or covariance
processing method
calibration_or_validation split
quality flags
license and redistribution status
```

Examples of observables include:

```text
first-cell length
cell-center positions
Mach-disk location and diameter
centerline pressure maxima and minima
supersonic-core length
plume half-width
centerline velocity and temperature
spectral radiance pixels
band-integrated radiant intensity
```

Raw source data and derived features must be stored separately. Derived feature
scripts shall be reproducible.

## 5. Nondimensionalization

Fit dimensionless observables wherever practical:

\[
\frac{x}{D_j},
\qquad
\frac{r}{D_j},
\qquad
\frac{p-p_a}{p_a},
\qquad
\frac{u-u_a}{u_j-u_a},
\qquad
\frac{T-T_a}{T_j-T_a}.
\]

This improves conditioning and makes applicability across nozzle sizes more
transparent.

## 6. Calibration and validation split

Calibration cases and validation cases must be disjoint by configuration, not
merely by individual image pixels from the same run.

Recommended split hierarchy:

```text
hold out complete operating conditions
hold out complete nozzle geometries when enough data exist
hold out complete facilities when multiple facilities exist
```

The split and its random seed, when randomized, are part of calibration
provenance.

Data may be assigned to:

```text
calibration
validation
exploratory_only
excluded_with_reason
```

A dataset used to tune a coefficient cannot later be described as independent
validation.

## 7. Residual definitions

For observation \(y_i\), prediction \(m_i(\boldsymbol\theta)\), and standard
uncertainty \(\sigma_i\), define

\[
r_i
=
\frac{m_i(\boldsymbol\theta)-y_i}{\sigma_i}.
\]

For correlated observations with covariance \(\Sigma_y\), use

\[
\mathbf r
=
L^{-1}
\left[
\mathbf m(\boldsymbol\theta)-\mathbf y
\right],
\]

where

\[
LL^T=\Sigma_y.
\]

Do not treat every pixel in an image as statistically independent when the
instrument point-spread function or processing creates correlation.

## 8. Objective function

A default deterministic objective is

\[
\boxed{
J(\boldsymbol\theta)
=
\sum_i
w_i\rho(r_i)
+
\lambda R(\boldsymbol\theta).
}
\]

Here:

- \(w_i\) balances observable families or cases;
- \(\rho\) is a robust loss, such as Huber loss;
- \(R\) is a prior or regularization term;
- \(\lambda\) controls regularization.

Huber loss is

\[
\rho_\delta(r)
=
\begin{cases}
\frac12r^2,& |r|\le\delta,\\
\delta\left(|r|-\frac12\delta\right),& |r|>\delta.
\end{cases}
\]

Weights and robust-loss thresholds must be recorded, not hidden inside a fit
script.

## 9. Parameter transformations and bounds

Positive coefficients should be optimized in log space:

\[
\eta_j=\ln\theta_j.
\]

Bounded fractions may use a logit transformation. Physical bounds remain
explicit and are verified after inverse transformation.

The optimizer must not explore negative spreading rates, negative opacities,
or invalid species fractions.

## 10. Optimization strategy

Recommended sequence:

```text
1. Evaluate nominal parameters on all calibration cases.
2. Run one-at-a-time sensitivity scans.
3. Remove or fix parameters that are unidentifiable from available data.
4. Use bounded multistart least squares for the reduced parameter set.
5. Inspect residual structure by case and observable family.
6. Compute local covariance or posterior samples.
7. Freeze the candidate calibration.
8. Evaluate the untouched validation set once.
```

For expensive models, a surrogate may be used, but its approximation error must
be included and checked against direct solver evaluations.

## 11. Sensitivity analysis

### 11.1 Local dimensionless sensitivity

For output \(y_i\) and parameter \(\theta_j\), define

\[
\boxed{
S_{ij}
=
\frac{\theta_j}{s_i}
\frac{\partial y_i}{\partial\theta_j},
}
\]

where \(s_i\) is an output scale, usually \(|y_i|\) or a documented reference
scale.

Use central finite differences with step-size convergence checks unless an
analytic or automatic derivative is available.

### 11.2 Global sensitivity

For nonlinear multi-parameter models, use Latin hypercube or Sobol sampling to
estimate variance-based sensitivity. The sampling design and seed are saved as
artifacts.

### 11.3 Identifiability

Let \(J_\theta\) be the residual Jacobian. Inspect singular values of

\[
J_\theta^TJ_\theta.
\]

Strongly collinear or near-null parameter combinations are not separately
identifiable. Fix, combine, or regularize them rather than reporting artificial
precision.

## 12. Parameter covariance

For a locally linear least-squares solution,

\[
\Sigma_\theta
\approx
s^2
\left(J_\theta^TWJ_\theta\right)^{-1},
\]

where \(s^2\) is an appropriate residual variance estimate. Use a pseudoinverse
only for diagnostics; a rank-deficient covariance indicates unidentifiable
parameters and must be reported.

A production calibration stores the full covariance matrix and parameter order,
not only one standard deviation per parameter.

## 13. Uncertainty propagation

### 13.1 Linearized propagation

For output vector \(\mathbf y=f(\mathbf z)\), input/parameter covariance
\(\Sigma_z\), and Jacobian \(G=\partial f/\partial\mathbf z\),

\[
\boxed{
\Sigma_y
\approx
G\Sigma_zG^T.
}
\]

This is appropriate only near a smooth operating point with approximately
linear response.

### 13.2 Monte Carlo propagation

```text
1. Sample physical inputs from their distributions.
2. Sample calibration parameters jointly from their covariance or posterior.
3. Preserve physical constraints and correlations.
4. Run the complete requested model level.
5. Record failed/out-of-validity samples separately.
6. Report quantiles and failure probability.
```

The random seed and sample count are part of provenance.

### 13.3 Numerical uncertainty combination

Numerical convergence error shall be estimated separately by refinement. It may
be combined with parametric uncertainty only after the numerical estimate is
shown to be sufficiently small or is explicitly represented.

## 14. Model discrepancy

When validation residuals show systematic structure, do not immediately widen
parameter priors until the model appears to fit. Record a model-discrepancy term
or validity limitation.

Examples:

```text
cell-spacing bias increasing with pressure ratio
consistent plume-width bias under flight coflow
spectral residual concentrated in particle-continuum regions
view-angle bias caused by vehicle occlusion omission
```

The discrepancy should inform the next fidelity phase.

## 15. Validation metrics

Report multiple metrics rather than a single aggregate score:

\[
\mathrm{RMSE}
=
\sqrt{\frac1N\sum_i(m_i-y_i)^2},
\]

\[
\mathrm{NRMSE}
=
\frac{\mathrm{RMSE}}{y_{\max}-y_{\min}},
\]

\[
\mathrm{bias}
=
\frac1N\sum_i(m_i-y_i),
\]

and uncertainty-weighted chi-square where appropriate:

\[
\chi^2
=
\mathbf r^T\mathbf r.
\]

For images and spectra also report:

```text
integrated radiant-intensity error
peak-location error
spectral-angle error
spatial registration error
band-integrated error
```

## 16. Calibration artifact layout

Recommended repository structure:

```text
calibrations/
  shock_train/
    <calibration_id>/
      calibration.yaml
      covariance.npy
      source_cases.yaml
      split.yaml
      fit_metrics.json
      validation_metrics.json
      residuals.parquet
      plots/
      README.md
  integral_mixing/
  particles/
```

Large or restricted source data should remain outside the package and be
referenced by checksum and acquisition instructions.

## 17. Calibration YAML requirements

```yaml
schema_version: "1.0"
calibration_id: shock-train-example
calibration_version: "1"
model_level: reduced_shock_train
parameters:
  shock.core_spreading_rate:
    value: 0.05
    units: dimensionless
    standard_uncertainty: 0.01
  shock.spacing_coefficient:
    value: 1.306
    units: dimensionless
    standard_uncertainty: 0.05
covariance_file: covariance.npy
calibration_cases: []
validation_cases: []
applicability:
  mach_range: [1.2, 4.5]
  nozzle_pressure_ratio_range: [1.0, 25.0]
  geometry: circular_axisymmetric
  ambient_flow: quiescent
limitations: >-
  Example only. Replace with a documented fit before production use.
```

Illustrative values must be labeled as such and may not become silent defaults.

## 18. Runtime applicability checks

Before applying a calibration, compare current nondimensional inputs with its
applicability metadata. Return warnings or `OUTSIDE_MODEL_VALIDITY` for
extrapolation beyond configured limits.

Applicability variables may include:

```text
exit Mach
fully expanded Mach
nozzle pressure ratio
temperature ratio
density ratio
Reynolds number
exit boundary-layer thickness ratio
ambient Mach
propellant or gas family
```

## 19. Calibration release gate

A calibration may be marked `validated` only when:

- source data and extraction scripts are reproducible;
- calibration and validation cases are disjoint;
- objective, weights, bounds, and transformations are recorded;
- parameter identifiability has been assessed;
- covariance or posterior samples are stored;
- validation metrics are reported by case and observable;
- applicability ranges and model-form limits are explicit;
- the artifact has an immutable ID, version, and checksums;
- regression tests load the calibration and reproduce reference predictions.

## 20. Acceptance gate

The uncertainty framework is complete when:

- every empirical coefficient is registered and versioned;
- numerical, parametric, closure, model-form, and measurement uncertainties are
  distinguishable;
- calibration data are not reused as independent validation;
- local sensitivity and identifiability reports are generated;
- covariance-aware or posterior-aware sampling is supported;
- outputs can include intervals or quantiles plus failed-sample fractions;
- calibration applicability is checked at runtime;
- deterministic and uncertainty-enabled results both preserve provenance;
- no illustrative coefficient is presented as a validated default.

<!-- END 19_uncertainty_and_sensitivity_methods.md -->


---

<!-- BEGIN 20_phase_0_patch_blueprint.md -->

# Phase 0 File-by-File Patch Blueprint

## 1. Purpose

This document tells the coding agent exactly how to turn the foundation plan
into a reviewable sequence of patches without beginning first-cell MOC,
shock-train, radiation, or chemistry work.

The branch snapshot reviewed by this handoff exposes the package primarily
through:

```text
src/exhaust_plume/__init__.py
src/exhaust_plume/models/plume/__init__.py
```

The installed-wheel smoke test imports `calculatePlumeZones` from the top-level
package and calls the legacy signature. Preserve that path while introducing
the new API.

## 2. Phase 0 target tree

Create:

```text
src/exhaust_plume/models/gas/
  __init__.py
  contracts.py
  calorically_perfect.py

src/exhaust_plume/models/nozzle/
  __init__.py
  contracts.py
  area_mach.py
  exit_state.py

src/exhaust_plume/models/shock_cells/
  __init__.py
  contracts.py
  regime.py
  geometry.py
  oblique_shock.py

src/exhaust_plume/compat/
  __init__.py
  plume_v0.py

src/exhaust_plume/exceptions.py
src/exhaust_plume/warnings.py
```

Do not move every existing aerodynamic helper in the first patch. Introduce
new modules, route corrected behavior through them, and leave thin legacy
re-exports until downstream tests have migrated.

## 3. Commit sequence

Each numbered group should be independently reviewable and leave the repository
passing focused tests. Squashing may occur only after review if project policy
requires it.

## Commit 0 — Capture the baseline

### Work

- Record the branch HEAD and reviewed file SHAs in the PR description.
- Run the complete current quality suite.
- Add no physics changes.
- Create a short regression note containing current expected failures or
  warnings, if any.

### Commands

```bash
python -m pytest
python -m ruff check .
python -m pyright
python -m build
```

### Stop condition

If the current branch is already failing, distinguish pre-existing failures
from work introduced by Phase 0 before continuing.

## Commit 1 — Introduce errors, warnings, and validated gas contracts

### New files

```text
src/exhaust_plume/exceptions.py
src/exhaust_plume/warnings.py
src/exhaust_plume/models/gas/contracts.py
src/exhaust_plume/models/gas/calorically_perfect.py
```

### Required types

```text
GasModelKind
GasPropertiesConfig
GasProperties
InvalidStateError
LegacyApiWarning
LegacyDryAirAssumptionWarning
```

### Required equations

\[
R=R_u/W,
\qquad
p=\rho RT,
\qquad
a=\sqrt{\gamma RT}.
\]

### Tests

Create:

```text
tests/src/models/gas/test_contracts.py
tests/src/models/gas/test_calorically_perfect.py
```

Test consistency of `R` and `W`, composition normalization, density, sound
speed, and invalid values.

### Compatibility

Do not change current exports yet.

## Commit 2 — Correct mass flow and throat area

### New or modified files

```text
src/exhaust_plume/models/nozzle/area_mach.py
src/exhaust_plume/models/plume/motor_parameters.py
```

### Required functions

```text
calc_mass_flow_parameter
calc_mass_flow_rate
calc_choked_throat_area
calc_area_mach_ratio
solve_mach_from_area_ratio
```

Use snake-case names for new APIs. Existing camel-style functions remain as
wrappers.

### Required equation

\[
A^*
=
\frac{\dot m}{p_0}
\sqrt{\frac{RT_0}{\gamma}}
\left(\frac{\gamma+1}{2}\right)^{
(\gamma+1)/(2(\gamma-1))
}.
\]

### Tests

- Forward/inverse mass-flow round trip.
- Subsonic and supersonic area-Mach roots are distinguished.
- The existing incorrect exponent fails the new regression fixture.
- Array and scalar behavior are either both supported and tested or explicitly
  separated.

## Commit 3 — Add the corrected nozzle-exit state path

### New files

```text
src/exhaust_plume/models/nozzle/contracts.py
src/exhaust_plume/models/nozzle/exit_state.py
```

### Required functions

```text
derive_uniform_nozzle_exit
validate_mass_flow_consistency
```

### Work

- Accept an explicit gas model.
- Derive static state from total state and Mach.
- Derive velocity and mass flow.
- Cross-check supplied mass flow if present.
- Retain total-state round-trip residuals.

### Tests

- Static/total round trip.
- Density and velocity change correctly with molecular weight.
- Mass flow equals \(\rho uA\).
- Inconsistent supplied mass flow returns a failed validation or structured
  diagnostic according to the contract.

## Commit 4 — Correct energy and enthalpy semantics

### Modified files

```text
src/exhaust_plume/util/aero/flow_state.py
src/exhaust_plume/models/gas/calorically_perfect.py
run/plot code that uses specific_total_energy_Jpkg
```

### Work

Add precise properties:

```text
specific_gas_work_Jpkg
specific_static_internal_energy_Jpkg
specific_static_enthalpy_Jpkg
specific_total_energy_Jpkg
specific_total_enthalpy_Jpkg
```

For a calorically perfect gas:

\[
e=c_vT,
\qquad
h=c_pT,
\qquad
E=e+u^2/2,
\qquad
h_0=h+u^2/2.
\]

The old property behavior is preserved only through a deprecation alias whose
warning states that it historically returned \(RT_0\).

### Tests

- Enthalpy identity.
- Total-energy identity.
- Deprecated property warning.
- Plots and tables use the intended physical quantity and correct label.

## Commit 5 — Replace oblique-shock angle logic

### New or modified files

```text
src/exhaust_plume/models/shock_cells/oblique_shock.py
src/exhaust_plume/util/aero/oblique_shock.py
```

### Required functions

```text
theta_from_beta
calc_max_attached_turn
solve_oblique_shock_angle
solve_oblique_shock_to_pressure
```

### Work

- Use radians internally.
- Use analytic zero-turn limits.
- Use bounded scalar optimization/root solving.
- Return diagnostics and explicit detached-shock status.
- Replace nested log-and-continue behavior in pressure equalization.

### Tests

- Weak and strong zero-turn limits.
- Continuity for small turn angles.
- Residual checks.
- Below/above maximum-turn boundary.
- Pressure-target direct solution and unattainable target.

## Commit 6 — Add regime classification and matched-flow result

### New or modified files

```text
src/exhaust_plume/models/shock_cells/regime.py
src/exhaust_plume/models/shock_cells/contracts.py
src/exhaust_plume/models/plume/plume_solve.py
```

### Work

- Add `ExpansionRegime`.
- Calculate \(r_p=(p_e-p_a)/p_a\).
- Permit `max_cells=0`.
- Return no cells for matched flow.
- Correct current test names and values.

### Tests

Construct total pressure from target ratios:

```text
p_e / p_a = 0.90
p_e / p_a = 1.00
p_e / p_a = 1.10
```

Do not use ambiguous arbitrary total pressures as regime labels.

## Commit 7 — Add robust ray geometry and correct the precursor

### New or modified files

```text
src/exhaust_plume/models/shock_cells/geometry.py
src/exhaust_plume/models/plume/plume_solve.py
```

### Work

- Add `Ray2D` and `RayIntersection2D`.
- Reject parallel, ill-conditioned, backward, or high-residual intersections.
- Replace the precursor distance with \(R/\tan\beta\).
- Convert every internal geometry angle to radians.

### Tests

- Perpendicular, oblique, parallel, nearly parallel, and backward cases.
- Scale invariance under normalized directions.
- Exact 45-degree precursor case.
- Regression for the degree/radian defect.

## Commit 8 — Separate transitions from closed zones

### New or modified files

```text
src/exhaust_plume/models/shock_cells/contracts.py
src/exhaust_plume/models/plume/plume_solve.py
src/exhaust_plume/models/plume/visualization.py
```

### Work

- Introduce `FlowTransition`, `CharacteristicSegment`, `ShockSegment`, and
  `ClosedZone`.
- Prevent `NaN` placeholder geometry from entering public closed-zone results.
- Make visualization skip or reject non-closed transitions by type rather than
  by checking finiteness.

### Tests

- Polygon finiteness, area, orientation, and self-intersection.
- Transition objects cannot be passed to closed-zone consumers.
- Legacy `ZoneResult` wrapper remains usable.

## Commit 9 — Add compatibility adapters and migrate exports

### New or modified files

```text
src/exhaust_plume/compat/plume_v0.py
src/exhaust_plume/__init__.py
src/exhaust_plume/models/plume/__init__.py
```

### Work

- Preserve all current top-level export names.
- Add new canonical exports.
- Map `num_plumes` to `max_cells`.
- Emit typed deprecation warnings.
- Reject simultaneous old/new keyword specification.
- Preserve legacy dry-air behavior only in the old wrapper and mark it in
  diagnostics.

### Installed-wheel smoke test

Update `tests/installed_smoke.py` to exercise:

1. The legacy `calculatePlumeZones` call.
2. One new validated gas/nozzle call.
3. The matched-flow zero-cell path.
4. Import without optional plotting, spectroscopy, or chemistry packages.

## Commit 10 — Raise the quality baseline

### Modified files

```text
pyproject.toml
pyrightconfig.json
CI workflow files
```

### Work

- Require Python 3.12+.
- Add Pydantic v2 and SciPy if the Phase 0 implementation uses them in the base
  package.
- Move Pyright to Python 3.12.
- Expand type-checking coverage deliberately rather than flipping the complete
  legacy tree to strict in one unreviewable change.
- Add or update build-wheel smoke tests.

### Pyright rollout

Recommended:

```text
new modules: strict
legacy modules: basic until touched
```

Use per-file configuration or separate include groups if required. Every
materially modified function must be fully typed.

## 4. Legacy wrapper behavior

## 4.1 `calcNozzleExitFlowState`

Legacy call:

```python
calcNozzleExitFlowState(
    mach=...,
    total_temperature=...,
    total_pressure=...,
    gamma=...,
)
```

Behavior during compatibility period:

- Construct explicit dry-air `GasProperties`.
- Emit `LegacyDryAirAssumptionWarning` once per call site under normal warning
  filtering.
- Delegate to `derive_uniform_nozzle_exit`.
- Return a legacy-compatible `FlowState` view.

New callers must supply a gas contract.

## 4.2 `calculatePlumeZones`

Legacy behavior:

- Preserve positional and keyword parameters.
- Treat `num_plumes` as deprecated `max_cells`.
- Return the current tuple shape until the compatibility boundary.
- Include new diagnostics in the existing details mapping under a namespaced
  key rather than changing existing keys unexpectedly.

New behavior:

```python
solve_shock_cells(config: ShockCellSolveConfig) -> ShockCellSolveResult
```

## 5. Test file map

Create or expand:

```text
tests/src/models/gas/test_contracts.py
tests/src/models/gas/test_calorically_perfect.py
tests/src/models/nozzle/test_area_mach.py
tests/src/models/nozzle/test_exit_state.py
tests/src/models/shock_cells/test_regime.py
tests/src/models/shock_cells/test_oblique_shock.py
tests/src/models/shock_cells/test_geometry.py
tests/src/models/shock_cells/test_contracts.py
tests/src/compat/test_plume_v0.py
tests/installed_smoke.py
```

Tests should prefer `pytest` parameterization and `numpy.testing` over
`unittest.TestCase` for new modules.

## 6. Pull-request evidence table

The completion report must contain:

| Defect or contract | Failing test before fix | Correct equation or invariant | Final test |
|---|---|---|---|
| Choked exponent | test ID | throat-area equation | test ID |
| Hidden dry air | test ID | \(R=R_u/W\) | test ID |
| Energy naming | test ID | \(h_0=h+u^2/2\) | test ID |
| Weak zero turn | test ID | \(\beta_w=\mu\) | test ID |
| Detached shock | test ID | \(\theta\le\theta_{max}\) | test ID |
| Matched flow | test ID | \(|r_p|\le\epsilon_p\) | test ID |
| Precursor geometry | test ID | \(\Delta x=R/\tan\beta\) | test ID |
| Ray validity | test ID | forward parameters/residual | test ID |
| Closed zones | test ID | finite positive polygon | test ID |
| Legacy API | test ID | adapter mapping | test ID |

## 7. Phase 0 stop rules

Stop and report rather than expanding scope when:

- A correction requires a full first-cell free-boundary redesign.
- The branch has materially changed beyond the reviewed source and the planned
  adapter no longer maps cleanly.
- A legacy consumer requires undocumented behavior that conflicts with the
  corrected equations.
- A proposed root solver cannot produce a bounded residual and validity status.
- Optional chemistry or spectroscopy code is required to pass a base gas-
  dynamics test.

## 8. Phase 0 final gate

- [ ] Every known defect has a focused regression.
- [ ] Full tests pass.
- [ ] Ruff passes.
- [ ] Pyright passes at the documented coverage level.
- [ ] Wheel builds and installs in a clean environment.
- [ ] Legacy and new smoke calls pass.
- [ ] No public closed zone contains `NaN`.
- [ ] No generic gas path imports dry-air constants.
- [ ] No numerical failure logs an error and returns success.
- [ ] No Phase 1 MOC implementation was added prematurely.

<!-- END 20_phase_0_patch_blueprint.md -->


---

<!-- BEGIN 21_phase_0_foundation_task_packets.md -->

# Phase 0 Foundation-Corrections Task Packets

## 1. Purpose

This document converts `FND-*` backlog items into a sequence of small,
reviewable pull requests. The coding agent should complete one packet at a time,
run the complete quality gate, and provide the completion report defined in the
execution protocol.

Phase 0 changes mathematical foundations and API contracts. No MOC rewrite,
shock-train decay model, integral plume, or radiation feature belongs in this
phase.

## 2. Phase 0 branch and baseline

Primary integration branch:

```text
feature/foundation-corrections
```

Recommended short-lived branches:

```text
agent/fnd-a-contracts
agent/fnd-b-nozzle-equations
agent/fnd-c-shock-validity
agent/fnd-d-geometry
agent/fnd-e-regime-compat
agent/fnd-f-quality-gate
```

Before Packet FND-A:

```bash
python -m pip install -e '.[test,quality]'
python -m pytest
python -m ruff check .
python -m pyright
python -m build
```

Record current pass/fail status and do not misattribute pre-existing failures to
a later packet.

## 3. Packet FND-A — Explicit gas and nozzle contracts

### Maps to

```text
FND-001
FND-003 contract portion
FND-013 partial
```

### Goal

Introduce typed, immutable gas/nozzle input contracts and one canonical source
for the specific gas constant without changing the plume geometry yet.

### Required reading

```text
01_model_contract_and_architecture.md
02_foundation_corrections_plan.md sections on gas and nozzle state
14_api_contracts_and_serialization.md sections 3 through 8
```

### Expected files

```text
src/exhaust_plume/models/gas/__init__.py
src/exhaust_plume/models/gas/contracts.py
src/exhaust_plume/models/gas/calorically_perfect.py
src/exhaust_plume/models/nozzle/__init__.py
src/exhaust_plume/models/nozzle/contracts.py
src/exhaust_plume/models/nozzle/exit_state.py
tests/src/models/gas/test_calorically_perfect.py
tests/src/models/nozzle/test_exit_state.py
```

The exact package path may be adjusted to repository conventions, but gas and
nozzle contracts must not remain embedded in `plume_solve.py`.

### Required implementation

- `CaloricallyPerfectGas` or equivalent immutable contract.
- Explicit `gamma` and `molar_mass_kg_per_mol`.
- Derived

  \[
  R=R_u/\overline W.
  \]

- `NozzleExitInput` and `NozzleExitState` contracts.
- Static state derived from total state using the canonical gas.
- Fully typed public methods and NumPy types where arrays are accepted.
- No hidden dry-air default in new APIs.

### Compatibility

The old `calcNozzleExitFlowState` remains callable and delegates to the new
implementation using an explicitly documented dry-air compatibility value.
It emits a diagnostic or deprecation warning only if doing so does not break
existing tests unexpectedly; warning rollout may be deferred to Packet FND-E.

### Tests

```text
specific gas constant matches R_u / molar mass
changing molar mass changes density consistently
static-to-total round trip
velocity equals M sqrt(gamma R T)
invalid gamma, molar mass, pressure, temperature, and Mach are rejected
new public objects are immutable
legacy wrapper reproduces the new dry-air compatibility calculation
```

### Non-goals

```text
variable cp(T)
species chemistry
CEA integration
shock geometry
renaming num_plumes
```

### Done when

- all new and old tests pass;
- no active new gas API imports `MOLAR_MASS_DRY_AIR_kg` internally;
- package-root export changes are documented;
- `ruff` and `pyright` pass for added modules.

## 4. Packet FND-B — Correct nozzle equations and energy naming

### Maps to

```text
FND-002
FND-004
FND-003 remaining implementation
```

### Goal

Correct the choked mass-flow equation, establish branch-explicit area--Mach
inversion, and remove misleading energy terminology.

### Expected files

```text
src/exhaust_plume/models/plume/motor_parameters.py
src/exhaust_plume/models/nozzle/area_mach.py
src/exhaust_plume/util/aero/flow_state.py
tests/src/models/plume/test_motor_parameters.py
tests/src/models/nozzle/test_area_mach.py
tests/src/util/aero/test_flow_state.py
```

### Required equations

\[
A^*
=
\frac{\dot m}{p_0}
\sqrt{\frac{RT_0}{\gamma}}
\left(\frac{\gamma+1}{2}\right)^{\frac{\gamma+1}{2(\gamma-1)}}.
\]

\[
\frac{A}{A^*}
=
\frac1M
\left[
\frac{2}{\gamma+1}
\left(1+\frac{\gamma-1}{2}M^2\right)
\right]^{\frac{\gamma+1}{2(\gamma-1)}}.
\]

\[
h_0=c_pT_0,
\qquad
c_p=\frac{\gamma R}{\gamma-1}.
\]

### Required implementation

- Correct the missing factor of \(1/2\) in the throat-area exponent.
- Implement an explicit `MachBranch` enum or literal for area--Mach inversion.
- Use a bracketed scalar solver according to Document 13.
- Rename or replace `specific_total_energy_Jpkg`.
- Preserve the legacy property as a deprecated alias only if required.
- Correct density property names such as `kgps`/`kpgs` to unit-accurate names,
  retaining aliases where necessary.

### Tests

```text
sonic A/A* = 1
known subsonic and supersonic area--Mach values
area -> Mach -> area round trip on both branches
choked mass flow reconstructed from calculated throat area
molar-mass sensitivity
stagnation enthalpy equals cp T0
legacy energy alias warning and documented numerical meaning
```

### Numerical anchors

Tests should compute reference values independently from the production
function or use high-precision constants checked into the test with the
supporting equation in a comment.

### Non-goals

```text
changing plume geometry
introducing variable gamma
adding shock-train termination
```

### Done when

- the corrected equation is documented in source and mathematical notes;
- no test preserves the incorrect exponent as desired behavior;
- both area--Mach branches have deterministic bracket tests;
- compatibility aliases are covered by migration tests.

## 5. Packet FND-C — Oblique-shock branches and validity

### Maps to

```text
FND-005
FND-006
```

### Goal

Make weak/strong branch behavior explicit, implement the correct zero-turn
limits, and reject detached or unattainable target-pressure shocks.

### Expected files

```text
src/exhaust_plume/util/aero/oblique_shock.py
src/exhaust_plume/util/aero/shock_validity.py
tests/src/util/aero/test_oblique_shock.py
tests/src/util/aero/test_shock_validity.py
```

### Required implementation

- Internal radians.
- `ShockBranch` with stable values.
- `calculate_max_attached_turn(M, gamma)`.
- Branch-specific `solve_shock_angle`.
- Exact limits:

  \[
  \beta_{weak}(0)=\sin^{-1}(1/M),
  \qquad
  \beta_{strong}(0)=\pi/2.
  \]

- Direct target-pressure construction through \(M_{n1}\) and \(\beta\).
- Maximum normal-shock pressure-ratio check.
- Structured `DETACHED_SHOCK_REQUIRED` and strong-branch statuses.
- Verification of downstream state, total-temperature conservation, and
  stagnation-pressure loss.

### Tests

```text
weak zero-turn limit at several Mach numbers
strong zero-turn limit
weak and strong roots satisfy theta-beta-M residual
maximum-turn point is a local maximum
request above theta_max returns detached status
pressure target below upstream is rejected
pressure target above normal-shock limit is rejected
direct target-pressure solution reaches requested pressure
weak-only policy rejects a strong-branch target
```

### Non-goals

```text
Mach-disk geometry
nozzle separation
full first-cell construction
```

### Done when

- no public weak-shock path returns 90 degrees for zero turn;
- all non-solutions are structured and tested;
- old callers receive a compatible exception or result mapping;
- branch selection is explicit in code and serialization.

## 6. Packet FND-D — Robust geometry primitives and precursor fix

### Maps to

```text
FND-008
FND-009
FND-010 geometry portion
```

### Goal

Replace unchecked point-only intersections with forward-ray results and fix the
overexpanded precursor centerline geometry.

### Expected files

```text
src/exhaust_plume/geometry/__init__.py
src/exhaust_plume/geometry/contracts.py
src/exhaust_plume/geometry/intersections.py
src/exhaust_plume/geometry/polygons.py
src/exhaust_plume/models/plume/plume_solve.py
tests/src/geometry/test_intersections.py
tests/src/geometry/test_polygons.py
tests/src/models/plume/test_overexpanded_precursor.py
```

### Required implementation

- `Ray2D` and `RayIntersectionResult`.
- Direct 2-by-2 solve with determinant, condition number, parameters, residual,
  and status.
- Forward-parameter checks.
- Legacy point-only wrapper where needed.
- Parameterized ray--parabola intersection for temporary compatibility.
- Precursor centerline relation:

  \[
  \Delta x=R/\tan\beta.
  \]

- Radian-only trigonometry inside geometry.
- Polygon signed area and self-intersection validation.

### Tests

```text
orthogonal forward rays
intersection at one origin
parallel rays
near-parallel ill-conditioned rays
intersection behind first ray
intersection behind second ray
scale invariance across meter magnitudes
parabola root selection by forward parameter
precursor analytic triangle geometry
polygon area, winding, duplicate vertex, and self-intersection
```

### Non-goals

```text
removing every legacy parabola use
full MOC free boundary
3D mesh generation rewrite
```

### Done when

- successful intersections report positive/near-zero forward parameters;
- no successful result relies on a pseudoinverse least-squares point;
- precursor coordinates satisfy the analytic angle relation;
- geometry failures cannot be mistaken for finite valid polygons.

## 7. Packet FND-E — Regime classification, result separation, and compatibility

### Maps to

```text
FND-007
FND-010 remaining
FND-011
FND-012 partial
```

### Goal

Add explicit matched/underexpanded/overexpanded classification, separate open
transitions from closed zones, and migrate repeated `plume` terminology to
`cell` terminology.

### Expected files

```text
src/exhaust_plume/models/shock_cells/contracts.py
src/exhaust_plume/models/shock_cells/regime.py
src/exhaust_plume/compat/legacy_plume.py
src/exhaust_plume/models/plume/plume_solve.py
src/exhaust_plume/models/plume/run_plume_solve.py
tests/src/models/shock_cells/test_regime.py
tests/src/compat/test_legacy_plume.py
tests/src/models/plume/test_plume_solver.py
```

### Required implementation

- `ExpansionRegime` enum.
- Dimensionless pressure residual.
- Configurable matched-flow tolerance.
- Matched flow returns zero shock cells.
- `max_cells` safety ceiling in the new API.
- `cell_index` in new result contracts.
- Separate `FlowTransition`, `CharacteristicSegment`, `ShockSegment`, and
  `ClosedZone` types, or the minimum additive subset required to ensure public
  successful closed zones contain no placeholder `NaN` polygons.
- Legacy wrappers for `num_plumes` and `plume_index`.
- Structured termination and validity metadata in `details` compatibility view.

### Regime-controlled test cases

Construct test total pressure from target \(p_e/p_a\), rather than naming a
case from guessed total-pressure values:

```text
0.90 mildly overexpanded
1.00 matched
1.10 mildly underexpanded
2.00 strongly underexpanded validity case
```

### Tests

```text
classification around both tolerance boundaries
matched flow zero-cell behavior
max_cells = 0 safety behavior
legacy num_plumes mapping
new cell_index and old plume_index alias
no successful ClosedZone contains NaN
regression test names match their actual regimes
```

### Non-goals

```text
predicting physical cell count
MOC free-boundary replacement
calibrated shock decay
```

### Done when

- the new API never calls one shock cell a plume;
- matched flow creates no artificial wave system;
- compatibility semantics are explicit;
- current misnamed underexpanded test is corrected or replaced.

## 8. Packet FND-F — Documentation, quality, and Phase 0 gate

### Maps to

```text
FND-012 remaining
FND-013
Phase 0 gate
```

### Goal

Complete the source documentation, migration evidence, equation regressions,
quality configuration, and package validation required before Phase 1.

### Expected files

```text
README.md
docs/mathematical_model.tex
docs/coding_agent_handoff implementation status
pyproject.toml
pyrightconfig.json
.github/workflows/*
tests/installed_smoke.py
tests/src/validation/test_phase_0_gate.py
```

### Required implementation

- Update mathematical documentation with corrected equations and model limits.
- Add API and CLI migration examples.
- Move project baseline to Python 3.12 if approved by repository policy.
- Add or verify Pydantic, SciPy, pytest, Ruff, Pyright, and build dependencies.
- Ensure all new source is in Pyright scope.
- Add wheel-install smoke tests for new public imports.
- Create a machine-readable Phase 0 gate report.

### Required commands

```bash
python -m pytest
python -m ruff check .
python -m pyright
python -m build
```

Also install the built wheel into a clean virtual environment and run the public
API and CLI smoke tests outside the source checkout.

### Phase 0 evidence table

The completion report shall include numerical evidence for:

```text
choked throat equation
area--Mach inversion both branches
molar-mass density effect
stagnation enthalpy
weak and strong zero-turn shock limits
maximum attached turn and detached detection
target-pressure shock
matched-flow zero-cell behavior
forward-ray intersection
corrected precursor geometry
closed-zone finite topology
```

### Done when

- every Phase 0 manifest gate passes;
- the wheel smoke test passes;
- known legacy behavior changes are documented;
- no Phase 1 code is present;
- the coding-agent completion report identifies remaining model-form limits.

## 9. Packet dependency graph

```text
FND-A contracts
   ↓
FND-B nozzle equations and energy
   ↓
FND-C shock validity ─────┐
                         ├─→ FND-E regime/contracts
FND-D geometry ──────────┘
   ↓
FND-F quality gate
```

FND-C and FND-D may proceed in parallel after FND-A/B if they touch separate
files, but they must be integrated before FND-E.

## 10. Phase 0 stop conditions

Stop and request review when:

```text
a public compatibility choice is not covered by Document 15
a required equation conflicts with an existing documented convention
a source test relies on the known incorrect equation
the corrected behavior causes broad unexplained regression beyond the known
change set
a new dependency or schema change is needed beyond the approved plan
a requested shock state is outside the attached-shock model
```

Do not bypass a stop condition with a warning and approximate continuation.

<!-- END 21_phase_0_foundation_task_packets.md -->


---

<!-- BEGIN 22_phase_1_first_cell_task_packets.md -->

# Phase 1 Validated First-Cell Task Packets

## 1. Purpose

This document converts the validated first-cell plan into reviewable pull
requests. Phase 1 begins only after the complete Phase 0 gate passes.

The Phase 1 deliverable is one verified planar first shock cell for:

```text
matched flow
mild underexpansion
mild attached overexpansion with a validated exit state
```

Strong underexpansion requiring a Mach disk, detached shocks, and internal
nozzle separation remain structured out-of-validity results.

## 2. Entry gate

Required evidence before work starts:

```text
correct gas/nozzle contracts
correct choked equation
branch-safe area--Mach and PM inverses
weak/strong shock limits
maximum attached-turn detection
forward-ray intersections
explicit regime classification
matched-flow zero-cell behavior
no public NaN closed zones
all Phase 0 quality commands pass
```

Primary branch:

```text
feature/validated-first-cell
```

## 3. Packet MOC-A — Characteristic primitives and PM inverse hardening

### Maps to

```text
MOC-001
MOC-002
```

### Goal

Create immutable characteristic contracts and a high-confidence radians-based
Prandtl--Meyer inverse suitable for grid marching.

### Expected files

```text
src/exhaust_plume/models/shock_cells/characteristics.py
src/exhaust_plume/models/shock_cells/contracts.py
src/exhaust_plume/util/aero/prandtl_meyer.py
tests/src/models/shock_cells/test_characteristic_contracts.py
tests/src/util/aero/test_prandtl_meyer.py
```

### Required implementation

- `CharacteristicFamily` with stable `c_plus` and `c_minus` values.
- `CharacteristicPoint` containing point, \(M\), \(\theta\), \(\mu\), \(\nu\),
  \(K_+\), and \(K_-\).
- `CharacteristicSegment` containing family, endpoints, state provenance, and
  residuals.
- PM inverse using the algorithm in Document 13.
- Exact domain handling at \(M=1\) and \(\nu=0\).
- Explicit maximum PM angle.

### Tests

```text
nu(M) monotonic for M > 1
M -> nu -> M round trip across representative Mach values
nu = 0 returns M = 1
nu near maximum has bounded behavior
out-of-range nu is rejected
K invariants match theta and nu
contracts are immutable and finite
```

### Done when

- no characteristic code uses degree-valued internal fields;
- PM inversion has residual and bracket diagnostics;
- characteristic serialization has stable family names.

## 4. Packet MOC-B — Interior and centerline point solvers

### Maps to

```text
MOC-003
MOC-004
```

### Goal

Implement planar compatibility and averaged-slope geometry for interior and
centerline characteristic points.

### Expected files

```text
src/exhaust_plume/models/shock_cells/planar_characteristics.py
tests/src/models/shock_cells/test_planar_interior_point.py
tests/src/models/shock_cells/test_planar_centerline_point.py
```

### Governing equations

\[
K_+=\theta-\nu,
\qquad
K_-=\theta+\nu.
\]

At a \(C^+/C^-\) intersection:

\[
\theta_P=\frac{K_++K_-}{2},
\qquad
\nu_P=\frac{K_--K_+}{2}.
\]

At the centerline:

\[
y=0,
\qquad
\theta=0.
\]

### Required implementation

- Pure `solve_interior_characteristic_point` function.
- Pure `solve_centerline_characteristic_point` function.
- Averaged endpoint slope iteration.
- Forward-intersection enforcement.
- Separate state-compatibility and geometry residuals.
- Structured no-intersection and ill-conditioning statuses.

### Tests

```text
synthetic invariant intersection with analytic state
symmetric sources produce centerline-consistent point
swapping source order preserves the physical point when families are swapped
averaged-slope refinement reduces geometry residual
parallel characteristic failure
backward intersection failure
centerline theta exactly zero
invariant residual below tolerance
```

### Done when

- compatibility is not implemented as coordinate reflection alone;
- returned point is downstream of both source rays;
- tests separate state and geometry convergence.

## 5. Packet MOC-C — Ambient-pressure free-boundary solver

### Maps to

```text
MOC-005
```

### Goal

Replace the unconstrained polynomial plume boundary with a boundary point solver
that satisfies pressure and streamline conditions.

### Expected files

```text
src/exhaust_plume/models/shock_cells/free_boundary.py
tests/src/models/shock_cells/test_free_boundary.py
```

### Governing conditions

\[
p_b=p_a,
\qquad
\frac{dr_b}{dx}=\tan\theta_b.
\]

The boundary state also satisfies the incoming characteristic invariant.

### Required implementation

- Calculate boundary Mach from \(p_0/p_a\) for the isentropic segment.
- Recover boundary \(\theta\) from the incoming invariant.
- Intersect the incoming characteristic and prior-boundary tangent as forward
  rays.
- Iterate averaged slopes.
- Return pressure, compatibility, tangent, and geometry residuals.
- Preserve the old parabola only as an opt-in diagnostic comparison, not the
  successful default path.

### Tests

```text
boundary pressure equals ambient
boundary tangent equals flow angle
incoming invariant preserved
forward geometry
matched boundary state degenerates cleanly
nonphysical boundary Mach is rejected
legacy parabola comparison does not affect returned solution
```

### Done when

- successful first-cell code can construct a boundary without polynomial fit;
- every boundary point contains residual diagnostics;
- no hidden global ambient pressure is used.

## 6. Packet MOC-D — Mild underexpanded first-cell assembly

### Maps to

```text
MOC-006
MOC-008 partial
```

### Goal

Assemble a complete closed first cell for a mildly underexpanded circular jet
using the planar characteristic and free-boundary primitives.

### Expected files

```text
src/exhaust_plume/models/shock_cells/first_cell.py
src/exhaust_plume/models/shock_cells/underexpanded.py
tests/src/models/shock_cells/test_underexpanded_first_cell.py
```

### Required algorithm

```text
1. Compute exit pressure mismatch.
2. Compute ambient-pressure boundary Mach and total PM turn.
3. Discretize the expansion fan.
4. March characteristics to the centerline.
5. Apply centerline compatibility.
6. March reflected characteristics to the free boundary.
7. Construct the recompression/shock closure using Phase 0 shock validity.
8. Produce closed zones only after topology validation.
9. Report first-cell length and all residuals.
```

### Required input cases

Use target static pressure ratios, for example:

```text
p_e / p_a = 1.02
p_e / p_a = 1.10
p_e / p_a = 1.50
```

The strongest case is accepted only if it remains within the implemented
attached topology.

### Tests

```text
correct UNDEREXPANDED classification
positive downstream cell length
ambient-pressure free boundary
centerline theta = 0
closed polygons finite, positive area, and non-self-intersecting
expansion states preserve stagnation pressure and temperature
compression shocks reduce stagnation pressure
result independent of source object mutation
```

### Done when

- one complete mild-underexpanded first cell is returned without legacy
  parabola fallback;
- all successful zones pass topology checks;
- failure cases return structured partial diagnostics.

## 7. Packet MOC-E — Mild attached overexpanded first-cell assembly

### Maps to

```text
MOC-007
MOC-008 remaining
```

### Goal

Assemble the external first-cell topology for a mildly overexpanded jet when the
uniform exit state is explicitly declared valid.

### Expected files

```text
src/exhaust_plume/models/shock_cells/overexpanded.py
tests/src/models/shock_cells/test_overexpanded_first_cell.py
```

### Required algorithm

```text
1. Require nozzle_solution_validated = true or a validated exit profile id.
2. Solve the lip shock needed for pressure adjustment.
3. Reject detached or disallowed strong-branch requirements.
4. Intersect the shock with the centerline using R / tan(beta).
5. Apply downstream shock state and centerline compatibility.
6. Continue the characteristic/free-boundary construction.
7. Validate closed-zone topology and residuals.
```

### Input cases

```text
p_e / p_a = 0.98
p_e / p_a = 0.90
one case requiring detached shock
one case blocked because nozzle exit was not validated
```

### Tests

```text
correct OVEREXPANDED classification
shock pressure ratio reaches the target within tolerance
precursor geometry matches beta
weak branch used for mild case
detached case returns DETACHED_SHOCK_REQUIRED
unvalidated strongly overexpanded exit returns NOZZLE_SEPARATION_NOT_MODELED
closed-zone topology passes for successful mild cases
```

### Done when

- the solver distinguishes external attached flow from nozzle-separation
  uncertainty;
- no strong or detached case is forced through the mild topology.

## 8. Packet MOC-F — First-cell correlation, convergence, and gate

### Maps to

```text
MOC-009
MOC-010
Phase 1 gate
```

### Goal

Add equivalent fully expanded jet properties, first-cell scale correlation,
resolution convergence, external benchmark fixtures, and release evidence.

### Expected files

```text
src/exhaust_plume/models/shock_cells/fully_expanded.py
src/exhaust_plume/models/shock_cells/correlations.py
tests/src/models/shock_cells/test_fully_expanded.py
tests/src/models/shock_cells/test_first_cell_convergence.py
tests/src/validation/test_first_cell_reference_cases.py
docs/validation/first_cell_phase_1_report.md
```

### Required equations

\[
M_j
=
\sqrt{
\frac{2}{\gamma-1}
\left[
\left(\frac{p_0}{p_a}\right)^{(\gamma-1)/\gamma}-1
\right]
}.
\]

\[
\frac{A_j}{A_e}
=
\frac{\mathcal A(M_j)}{\mathcal A(M_e)},
\qquad
D_j=D_e\sqrt{A_j/A_e}.
\]

\[
L_{s,0}=1.306D_j\sqrt{M_j^2-1}.
\]

The correlation is a comparison metric, not a value imposed on the solved
geometry.

### Convergence study

Run at least three characteristic resolutions with an approximately constant
refinement ratio. Track:

```text
first-cell length
maximum radius
boundary pressure residual
centerline location
integrated zone area
maximum invariant residual
```

Estimate observed order where the data are in the asymptotic range. Do not
claim order from nonmonotonic coarse data.

### Validation fixtures

Add repository fixtures from approved primary sources for at least one
moderate-Mach circular jet. Store source, extraction method, units, and
uncertainty. Keep calibration and validation roles explicit even though Phase 1
has no fitted decay coefficients.

### Tests

```text
fully expanded state preserves total conditions
D_j and L_s are positive and dimensionally scaled
correlation scales linearly with D_e
matched flow reference returns no first-cell correlation claim
first-cell metrics converge with fan refinement
solver residuals decrease or meet tolerance under refinement
external reference error is reported, not hidden by loose assertion
```

### Phase 1 report

The report must include:

```text
implemented equations
model assumptions
underexpanded and overexpanded cases
convergence tables
correlation comparison
external-data comparison
validity failures
timing and memory measurements
known model-form uncertainty
```

### Done when

- all Phase 1 manifest gates pass;
- one underexpanded and one mild attached overexpanded cell converge;
- matched flow returns zero cells;
- detached and unvalidated separation cases are explicit;
- the free boundary meets pressure and tangent residuals;
- first-cell geometry has a documented convergence study;
- the implementation remains clearly labeled planar.

## 9. Packet dependency graph

```text
MOC-A contracts and PM inverse
   ↓
MOC-B interior/centerline
   ↓
MOC-C free boundary
   ├───────────────┐
   ↓               ↓
MOC-D underexpanded  MOC-E overexpanded
   └───────┬───────┘
           ↓
MOC-F convergence and validation gate
```

MOC-D and MOC-E may proceed in parallel after MOC-C if their shared assembly
interfaces are stable.

## 10. Phase 1 stop conditions

Stop and request review when:

```text
a first-cell case requires a Mach disk
a shock requires a detached or unapproved strong branch
a uniform overexpanded exit is not validated
the free-boundary solve has no forward intersection
zone topology changes under small tolerance perturbations
fan refinement does not approach a stable solution
correlation mismatch is large and unexplained
the implementation begins adding downstream empirical decay or mixing
```

A stopped case is valuable validation evidence. It must not be converted into a
nominal successful cell by adding geometry hacks.

<!-- END 22_phase_1_first_cell_task_packets.md -->


---

<!-- BEGIN 23_agent_prompts_and_gate_checklists.md -->

# Coding-Agent Prompts and Phase-Gate Checklists

## 1. Purpose

This document indexes ready-to-paste prompts for each implementation phase and
provides the reviewer checklist that must be completed before advancing.

## 2. Prompt index

1. [`prompts/01_phase_0b_foundation_completion.md`](prompts/01_phase_0b_foundation_completion.md)
2. [`prompts/02_phase_1_validated_first_cell.md`](prompts/02_phase_1_validated_first_cell.md)
3. [`prompts/03_phase_2_finite_shock_train.md`](prompts/03_phase_2_finite_shock_train.md)
4. [`prompts/04_phase_3_integral_mixing.md`](prompts/04_phase_3_integral_mixing.md)
5. [`prompts/05_phase_4_gray_radiation.md`](prompts/05_phase_4_gray_radiation.md)
6. [`prompts/06_phase_5_spectral_radiation.md`](prompts/06_phase_5_spectral_radiation.md)
7. [`prompts/07_phase_6_thermochemistry.md`](prompts/07_phase_6_thermochemistry.md)

The existing [`11_coding_agent_kickoff_prompt.md`](11_coding_agent_kickoff_prompt.md)
starts the first Phase 0 issue group.

## 3. How to use a prompt

1. Start from the branch/commit that passed the previous phase gate.
2. Paste one phase prompt to the coding agent.
3. Require the agent to select only the first dependency-ready issue group.
4. Review the completion report and diff.
5. Run the gate independently.
6. Continue with the next issue group using the same prompt and updated context.
7. Begin the next phase only after every checklist item is evidenced.

A prompt grants no permission to skip tests or combine unrelated issues.

## 4. Universal reviewer checklist

- [ ] The change implements only the stated issue group.
- [ ] Governing equations, correlations, and closures are labeled correctly.
- [ ] New or changed functions are fully typed.
- [ ] New/materially changed scopes end with `####`.
- [ ] Existing TODOs are preserved or explicitly resolved.
- [ ] Failure returns structured status or typed exception.
- [ ] SI units and radians are used internally.
- [ ] Focused tests demonstrate the defect or contract.
- [ ] Full tests, Ruff, Pyright, and build pass.
- [ ] Installed-wheel behavior is checked when exports/dependencies change.
- [ ] Numerical evidence includes residuals and convergence, not only plots.
- [ ] Compatibility impact is documented.
- [ ] Remaining validity limits are explicit.

## 5. Phase 0 gate

- [ ] Choked mass-flow equation corrected.
- [ ] Gas molecular weight honored everywhere in generic paths.
- [ ] Energy and enthalpy names are physically correct.
- [ ] Weak/strong zero-turn limits pass.
- [ ] Maximum attached-turn gate passes.
- [ ] Matched flow returns zero cells.
- [ ] Forward-ray geometry rejects invalid intersections.
- [ ] Precursor geometry uses radians and `R/tan(beta)`.
- [ ] No public closed-zone `NaN` geometry remains.
- [ ] Legacy exports and wheel smoke pass.
- [ ] Python 3.12/type-checking target is truthful.

## 6. Phase 1 gate

- [ ] PM inverse is bounded and verified.
- [ ] Characteristic sign convention is documented and tested.
- [ ] Interior compatibility residuals pass.
- [ ] Centerline `theta=0` residual passes.
- [ ] Free-boundary `p=p_a` residual passes.
- [ ] Underexpanded first cell closes.
- [ ] Supported overexpanded first cell closes or rejects by validity policy.
- [ ] Detached/Mach-disk topology is explicit.
- [ ] Closed-zone topology validation passes.
- [ ] Three-level refinement study shows convergence.

## 7. Phase 2 gate

- [ ] Cell count is an output.
- [ ] Closure coefficients have calibration artifacts.
- [ ] Calibration/validation datasets are disjoint.
- [ ] Core diameter and pressure amplitude evolve consistently.
- [ ] Physical and safety termination are distinct.
- [ ] Applicability bounds are enforced.
- [ ] Sensitivity and identifiability are reported.
- [ ] Uncertainty reaches cell count and endpoint.

## 8. Phase 3 gate

- [ ] Mass balance passes.
- [ ] Momentum balance passes.
- [ ] Total-enthalpy balance passes.
- [ ] Frozen species/element balances pass.
- [ ] Primitive recovery preserves positivity.
- [ ] Physical events and domain truncation are distinct.
- [ ] Field reconstruction preserves integral fluxes.

## 9. Phase 4 gate

- [ ] Planck implementation and units pass.
- [ ] Homogeneous slab matches exact solution.
- [ ] Thin/thick limits pass.
- [ ] Layer ordering passes.
- [ ] Ray geometry matches analytic references.
- [ ] Image and angular integrals converge.
- [ ] Optically thin angle-invariance test passes.
- [ ] IR-domain endpoint is separate.

## 10. Phase 5 gate

- [ ] Spectroscopic tables are content-addressed.
- [ ] Reference cross sections pass.
- [ ] Interpolation error is bounded.
- [ ] Mixture number density and opacity pass.
- [ ] Spectral coordinate conversion passes.
- [ ] Atmosphere, range, and sensor stages are separable.
- [ ] Heated-plume validation and uncertainty are documented.
- [ ] Optional dependencies do not break base import.

## 11. Phase 6 gate

- [ ] Species and elemental balances pass.
- [ ] CEA adapter is reproducible and offline-testable.
- [ ] Thermally perfect property inversion passes.
- [ ] Frozen variable-property waves conserve the right quantities.
- [ ] Equilibrium reference states pass.
- [ ] Finite-rate chemistry is energy consistent.
- [ ] Particle zero limit recovers molecular result.
- [ ] Particle optical data have provenance and applicability.

## 12. Escalation

Use the risk register and create a new ADR proposal when an implementation
choice changes public schema, base dependencies, scientific topology, or a phase
gate. The coding agent must not bury such decisions in a completion report.

<!-- END 23_agent_prompts_and_gate_checklists.md -->


---

<!-- BEGIN 24_end_to_end_acceptance_scenarios.md -->

# End-to-End Acceptance Scenarios

## 1. Purpose

These scenarios connect the individual phase tests into user-visible model
behavior. They define expected status, invariants, and result structure without
requiring every numerical value to be frozen prematurely.

Each scenario should eventually have:

```text
YAML input fixture
expected-status YAML
small scalar regression JSON
optional NPZ reference arrays
human-readable report or plot generated outside unit tests
```

## 2. Scenario E2E-001 — Matched uniform exit

### Purpose

Verify that the solver does not manufacture shock cells when exit and ambient
pressures match.

### Inputs

Construct total pressure from a selected \(M_e\), \(\gamma\), and
\(p_e=p_a\):

\[
p_0
=
p_a
\left(1+\frac{\gamma-1}{2}M_e^2\right)^{\gamma/(\gamma-1)}.
\]

Use explicit gas properties and a positive exit radius.

### Expected

```text
regime = MATCHED
status = NO_PRESSURE_MISMATCH
cells = empty
shock_train_end_x_m = 0 or null by schema decision
termination_reason = NO_PRESSURE_MISMATCH
was_domain_truncated = false
```

### Invariants

- Exit state round trips to supplied total state.
- No shock total-pressure loss exists.
- `max_cells=0` is accepted.
- Legacy wrapper returns a valid compatibility result without fake cells.

## 3. Scenario E2E-002 — Mild underexpanded first cell

### Purpose

Exercise a clean attached expansion/reflection/compression first-cell path.

### Inputs

Choose target

\[
\frac{p_e}{p_a}=1.10
\]

with moderate supersonic Mach and constant \(\gamma\). Derive \(p_0\) from the
exit ratio rather than selecting an arbitrary total pressure.

### Expected

```text
regime = UNDEREXPANDED
first-cell status = SUCCESS
one or more closed zones
all intersections forward
free-boundary pressure residual below tolerance
centerline angle residual below tolerance
```

### Invariants

- Expansion preserves total pressure and total temperature.
- Compression shock decreases total pressure.
- Closed zones are finite, non-self-intersecting, and positive area.
- First-cell length converges with characteristic refinement.
- Classical circular-jet spacing is reported as a comparison, not forced.

## 4. Scenario E2E-003 — Mild overexpanded exit with validated attached state

### Purpose

Exercise the external attached-shock path without implicitly claiming that
internal nozzle separation is absent.

### Inputs

Choose

\[
\frac{p_e}{p_a}=0.90
\]

and mark the uniform exit state as externally validated or explicitly accepted
for the reduced model.

### Expected

```text
regime = OVEREXPANDED
status = SUCCESS or documented attached-overexpanded status
precursor shock attached
centerline intersection downstream
```

### Invariants

- Precursor distance follows \(R/\tan\beta\).
- Shock pressure rise reaches the target within tolerance.
- Weak-branch shock angle is below the maximum-turn shock angle.
- Total pressure decreases across the shock.

### Negative companion

Run the same pressure ratio without the required validated-exit assumption when
the configured nozzle-separation gate considers it outside scope. Expected:

```text
status = NOZZLE_SEPARATION_NOT_MODELED
no fabricated external cell geometry
```

## 5. Scenario E2E-004 — Strong underexpansion outside attached-cell topology

### Purpose

Verify structured refusal rather than a plausible but invalid weak-shock train.

### Inputs

Select a pressure mismatch known by the model classifier to require a Mach-disk
or detached-shock topology.

### Expected

```text
status = MACH_DISK_REQUIRED or DETACHED_SHOCK_REQUIRED
validity flag identifies active limit
no downstream reduced cells generated as SUCCESS
```

### Invariants

- Maximum attached-turn or pressure-rise test explains the failure.
- Diagnostics retain requested and attainable limits.
- Radiation is blocked unless the caller explicitly supplies another flow
  field.

## 6. Scenario E2E-005 — Finite reduced shock train

### Purpose

Verify that cell count is predicted by termination policy and closure state,
not copied from a user request.

### Inputs

Use a valid first cell plus one calibration artifact. Set `max_cells` and
`max_axial_distance_m` above the expected physical endpoint.

### Expected

```text
cells_completed > 0
termination_reason is physical
was_domain_truncated = false
pressure amplitude decays
coherent-core diameter does not increase under the baseline closure
```

### Sensitivity companions

- Increase inward spreading rate: fewer cells or shorter core.
- Increase pressure-decay coefficient: earlier oscillation termination.
- Reduce safety domain below the physical endpoint: `DOMAIN_LIMIT` and
  `was_domain_truncated=true`.

No test should assert that a universal fixed cell count is correct.

## 7. Scenario E2E-006 — Integral frozen mixing plume

### Purpose

Verify conservative handoff from shock cells to a downstream mixing solution.

### Inputs

Initialize from the final coherent-core cross section with frozen exhaust and
ambient species.

### Expected

```text
mass flow grows through entrainment
velocity approaches ambient
thermal excess approaches ambient
species approach ambient composition
termination_reason = AMBIENT_EQUILIBRIUM or DOMAIN_LIMIT
```

### Invariants

- Integrated mass increase equals entrained mass.
- Momentum-flux residual remains below tolerance.
- Total-enthalpy flux includes ambient entrainment.
- Every species remains nonnegative and normalized.
- Element totals are conserved in the nonreacting model.

## 8. Scenario E2E-007 — Gray homogeneous slab

### Purpose

Establish the exact radiative-transfer baseline independent of plume geometry.

### Inputs

Uniform \(T\), gray \(\alpha\), path length \(L\), and background radiance
\(I_0\).

### Exact result

\[
I_L
=
I_0e^{-\alpha L}
+B_\lambda(T)(1-e^{-\alpha L}).
\]

### Expected

- Numerical result matches analytic result over optically thin and thick ranges.
- Zero opacity returns the background.
- Large optical depth approaches Planck radiance.
- Small optical depth is linear to first order.

## 9. Scenario E2E-008 — Axisymmetric gray cylinder by angle

### Purpose

Verify ray geometry and integrated angular behavior.

### Inputs

A finite isothermal cylinder with constant absorption.

### Geometry reference

For a side-on ray at transverse impact parameter \(b\), the radial chord through
an infinite cylinder is

\[
L(b)=2\sqrt{R^2-b^2}.
\]

For the finite cylinder and general angle, use an independent analytic or
high-resolution geometric reference.

### Expected

- Per-ray path lengths converge to the reference.
- Image symmetry holds.
- Optically thin, fully visible integrated volume emission is approximately
  angle invariant.
- Optical thickness introduces physically explainable angle dependence.

## 10. Scenario E2E-009 — Two-layer self-absorption

### Purpose

Verify path ordering.

### Inputs

A hot emitting layer and a cooler absorbing layer with the same spectral band.

### Expected

```text
hot behind cool != cool behind hot
```

The code must reproduce the analytic two-segment recurrence exactly. Sorting
segments by zone ID instead of line-of-sight distance must fail the test.

## 11. Scenario E2E-010 — Frozen molecular plume spectrum

### Purpose

Connect a prescribed plume field to tabulated molecular cross sections.

### Inputs

- Frozen H2O/CO2/CO mixture or a propellant-appropriate explicit mixture.
- Small spectral window with a checked reference table.
- Axisymmetric temperature/pressure field.
- Several aspect angles.

### Expected

- Mixture opacity equals the number-density-weighted species sum.
- Cross-section interpolation stays inside table bounds.
- Spectral features move only when Doppler support is explicitly enabled.
- Band-integrated signal converges with spectral and image refinement.
- Result records table hashes and species set.

## 12. Scenario E2E-011 — Atmosphere and sensor separation

### Purpose

Verify that intrinsic plume intensity, atmospheric propagation, and detector
response remain distinct stages.

### Expected processing

```text
intrinsic spectral radiant intensity
    → atmospheric transmittance and path radiance
    → range dilution
    → sensor spectral response
```

### Invariants

- Changing range does not alter intrinsic plume intensity.
- Changing sensor response does not alter atmospheric transmission.
- Turning atmosphere off recovers inverse-square propagation.
- Band units are documented and dimensionally consistent.

## 13. Scenario E2E-012 — Upstream validity propagation

### Purpose

Prevent radiation from concealing invalid flow physics.

### Inputs

Use a flow result with `MACH_DISK_REQUIRED` or an out-of-calibration-domain
flag.

### Expected

- Default orchestration does not produce a nominally valid signature.
- An explicit expert override may render a supplied approximate field, but the
  radiation result carries all upstream validity flags.
- Serialized output identifies the override and model discrepancy risk.

## 14. Scenario fixture structure

```text
tests/scenarios/
  e2e_001_matched/
    input.yaml
    expected.yaml
  e2e_002_mild_underexpanded/
    input.yaml
    expected.yaml
  ...
```

`expected.yaml` should contain statuses, tolerances, and invariants—not large
opaque arrays.

Example:

```yaml
scenario_id: e2e_001_matched
expected:
  regime: matched
  status: no_pressure_mismatch
  cell_count: 0
checks:
  total_pressure_relative_residual_max: 1.0e-10
  total_temperature_relative_residual_max: 1.0e-10
```

## 15. Regression policy

Freeze exact scalar values only when they represent:

- analytic equations;
- stable contractual behavior;
- or a reviewed scientific reference fixture.

For iterative model outputs, prefer tolerance bands, conservation residuals,
convergence trends, and topology/status checks over bitwise equality.

## 16. End-to-end gate

- [ ] Matched flow yields zero cells.
- [ ] Mild underexpansion closes one validated cell.
- [ ] Mild overexpansion handles or rejects nozzle validity explicitly.
- [ ] Strong mismatch returns a topology status.
- [ ] Shock train terminates physically when the domain permits.
- [ ] Integral plume conserves fluxes.
- [ ] Gray RTE matches exact slabs.
- [ ] Ray geometry matches analytic chords.
- [ ] Layer ordering changes self-absorption correctly.
- [ ] Molecular spectra record table provenance.
- [ ] Atmosphere and sensor stages remain separable.
- [ ] Upstream validity flags propagate through every result.

<!-- END 24_end_to_end_acceptance_scenarios.md -->


---

<!-- BEGIN 25_migration_release_and_compatibility_plan.md -->

# Migration, Release, and Compatibility Plan

## 1. Purpose

The current package has a small public API and an installed-wheel smoke test.
This plan introduces corrected contracts without forcing an immediate breaking
rewrite of every existing caller.

The migration must preserve two truths simultaneously:

1. Old calls remain runnable for a documented compatibility interval.
2. New scientific results never hide legacy dry-air assumptions, naming errors,
   or user-selected cell count behind the corrected API.

## 2. Current public surface

The reviewed branch exports these names from `exhaust_plume`:

```text
MODULE_NAME
VERSION
__version__
EngineParameters
ExpansionFanState
FlowState
ObliqueShockState
ZoneCoordinates
ZoneResult
ZoneType
calcNozzleExitFlowState
calculatePlumeZones
```

The migration should keep these importable while adding the new canonical API.

## 3. Compatibility phases

## Phase C0 — Additive foundation

- Add new modules and canonical APIs.
- Preserve current exports unchanged.
- Add tests for both surfaces.
- Correct internal equations where behavior was objectively defective.
- Emit no deprecation warning for imports alone.

## Phase C1 — Runtime deprecation

- Legacy function calls emit typed warnings.
- Warning text identifies the replacement and hidden assumptions.
- Serialized new results use only new names.
- Documentation examples prefer the new API.

## Phase C2 — Legacy adapter isolation

- Move old behavior entirely under `exhaust_plume.compat`.
- Top-level exports re-export those adapters.
- Internal production modules do not import compatibility modules.
- CI runs a dedicated legacy suite.

## Phase C3 — Removal decision

Before 1.0, the project may remove legacy APIs only after:

```text
at least one documented release boundary
migration guide published
known first-party consumers migrated
legacy usage measured or explicitly accepted
```

If 1.0 is approaching, freeze the final compatibility decision in a separate
ADR.

## 4. Function migration

## 4.1 Nozzle exit

Legacy:

```python
calcNozzleExitFlowState(
    mach,
    total_temperature,
    total_pressure,
    gamma,
)
```

Canonical:

```python
derive_uniform_nozzle_exit(
    config: IsentropicNozzleExitConfig,
) -> NozzleExitState
```

Legacy adapter behavior:

```text
construct explicit dry-air gas model
emit LegacyDryAirAssumptionWarning
call canonical implementation
return legacy FlowState view
record source_kind = LEGACY_DRY_AIR_ADAPTER
```

Do not silently alter the legacy density result before the warning/adaptation
path exists; otherwise existing regressions become difficult to interpret.

## 4.2 Plume-zone solve

Legacy:

```python
calculatePlumeZones(
    nozzle_mach,
    nozzle_total_temperature,
    nozzle_total_pressure,
    nozzle_radius,
    atmospheric_pressure,
    gamma,
    num_expansion_lines,
    num_compression_lines,
    num_plumes,
)
```

Canonical:

```python
solve_shock_cells(
    config: ShockCellSolveConfig,
) -> ShockCellSolveResult
```

Mapping:

| Legacy parameter | Canonical field | Notes |
|---|---|---|
| `nozzle_mach` | `exit.mach` | same physical quantity |
| `nozzle_total_temperature` | `exit.total_temperature_K` | units made explicit |
| `nozzle_total_pressure` | `exit.total_pressure_Pa` | units made explicit |
| `nozzle_radius` | `exit.radius_m` | same physical quantity |
| `atmospheric_pressure` | `ambient.pressure_Pa` | ambient temperature/composition supplied by adapter |
| `gamma` | `exit.gas.gamma` | legacy gas remains explicit dry air |
| `num_expansion_lines` | `num_expansion_characteristics` | resolution control |
| `num_compression_lines` | legacy construction option | no direct long-term physical contract |
| `num_plumes` | `max_cells` | deprecated semantic rename |

The wrapper returns the current tuple shape during compatibility. New
diagnostics may be added under:

```text
details['solver_diagnostics_v1']
```

without deleting `points` or `plume_fit` until the compatibility boundary.

## 5. Type and field migration

## 5.1 FlowState

Legacy fields:

```text
mach
static_pressure
static_temperature
static_density
gamma
```

Canonical fields:

```text
mach
static_pressure_Pa
static_temperature_K
density_kgpm3
flow_angle_rad
gas
```

Legacy property aliases remain read-only and emit no warning for simple scalar
access during the first compatibility stage. Construction through legacy field
names is deprecated sooner than property access.

## 5.2 ZoneResult

Legacy `ZoneResult` combines state, transition metadata, and geometry. The
canonical model separates:

```text
FlowTransition
CharacteristicSegment
ShockSegment
ClosedZone
```

Adapter rules:

- A canonical `ClosedZone` maps directly to a geometry-bearing legacy result.
- A transition without closed geometry maps to a legacy object with
  `coordinates=None`, not a fabricated `NaN` polygon, after the public type is
  made optional.
- Consumers requiring geometry must use an explicit closed-zone predicate.

## 5.3 Enum migration

Map legacy `ZoneType` values to canonical transition kinds:

| Legacy | Canonical |
|---|---|
| `Isentropic` | `ISENTROPIC` or state-only zone classification |
| `ExpansionFan` | `PRANDTL_MEYER_EXPANSION` |
| `ObliqueShock` | `OBLIQUE_SHOCK` |

Do not infer global regime from a local zone type.

## 6. CLI migration

Current CLI options remain accepted while aliases are added:

```text
--num-plumes          deprecated alias of --max-cells
--num-expansion-lines deprecated alias of --num-expansion-characteristics
```

New required or recommended options:

```text
--molecular-weight-kgpmol
--specific-gas-constant-jpkgk
--pressure-match-relative-tolerance
--max-axial-distance-m
--model-level
--calibration-id
```

Legacy CLI defaults that imply dry air must print a concise warning to stderr
and include the assumption in output diagnostics.

`--help` should group options by:

```text
nozzle exit
ambient
gas model
shock-cell numerics
termination
output/plotting
```

## 7. Package dependency migration

Current core dependencies are small. Add dependencies only when used by base
runtime paths.

### Core candidates

```text
numpy
scipy
pydantic >= 2
pyyaml
```

### Extras

```toml
plot = ["matplotlib"]
quality = ["pyright", "ruff"]
test = ["pytest", "build", "matplotlib"]
spectroscopy = ["hapi-package-name-as-verified"]
chemistry = ["cantera"]
all = ["...union of optional runtime extras..."]
```

Verify the actual distribution name before adding an HAPI dependency. Large
HITEMP datasets are data artifacts, not wheel dependencies.

## 8. Python and type-checking migration

The target is Python 3.12+ and fully typed new code.

Recommended sequence:

1. Change package metadata and CI matrix.
2. Change `pyrightconfig.json` to Python 3.12.
3. Enable strict checking on new packages.
4. Keep basic checking on untouched legacy modules.
5. Move a legacy module to strict when materially modified.
6. Include tests in type checking only after fixtures and test helpers have a
   manageable annotation policy.

Do not claim project-wide strict typing while most legacy files remain outside
the checked set.

## 9. Serialization migration

Legacy tuple/dictionary return values are not a durable archive format.
Introduce:

```text
schema_version
package_version
model_level
calibration_id
units
array artifact references
```

Migration rules:

- Readers accept older schema versions through explicit migration functions.
- Writers emit only the newest schema.
- Field renames are recorded in a migration table.
- Large arrays are referenced by content hash.
- Pickle is not an interchange format.

## 10. Test migration

Maintain three distinct suites:

```text
canonical API tests
legacy compatibility tests
installed-wheel smoke tests
```

The installed smoke test must verify:

- Package metadata and resources.
- Optional plotting is not installed by the core wheel.
- Legacy top-level import and call.
- Canonical gas/nozzle call.
- Canonical matched-flow zero-cell result.
- CLI `--help` from outside the checkout.

When a warning is expected, assert its exact class and important message
content rather than globally suppressing it.

## 11. Versioning and changelog

Every release note should separate:

```text
correctness fixes
new canonical APIs
deprecations
scientific model changes
calibration/data changes
known validity limits
```

A corrected governing equation is not merely an internal refactor; it belongs
under correctness and may change numerical outputs.

Calibration-only changes must identify the calibration artifact and should not
be hidden inside an unrelated patch release without documentation.

## 12. Rollback strategy

Every migration PR should be reversible without deleting scientific fixtures.

- Keep adapters isolated.
- Avoid irreversible data-format changes without a reader migration.
- Tag or record the last branch commit before each phase gate.
- Retain baseline numerical outputs for diagnosing changes, even when those
  outputs were physically wrong; label them as legacy regressions.

Rollback must not restore a known equation defect as the canonical path. It may
restore compatibility behavior behind a warning while the corrected path is
repaired.

## 13. Compatibility completion checklist

- [ ] Current top-level imports remain available during the declared interval.
- [ ] New APIs require explicit gas properties.
- [ ] Old dry-air behavior is visible through typed warnings and metadata.
- [ ] `num_plumes` maps to `max_cells` with conflict detection.
- [ ] Legacy tuple shape remains tested until removal.
- [ ] New result schemas are versioned.
- [ ] CLI aliases and warnings are tested.
- [ ] Core wheel imports without optional dependencies.
- [ ] Installed smoke covers legacy and canonical calls.
- [ ] Changelog distinguishes equations, APIs, and calibration changes.

<!-- END 25_migration_release_and_compatibility_plan.md -->


---

<!-- BEGIN 26_risk_register_and_open_decisions.md -->

# Risk Register and Open Decisions

## 1. Purpose

This register prevents unresolved scientific and software choices from being
silently decided inside implementation patches. Each risk has a mitigation and
a phase gate. Each open decision has a current default so work can continue
without repeated clarification.

Risk scale:

```text
likelihood: LOW / MEDIUM / HIGH
impact:     LOW / MEDIUM / HIGH / CRITICAL
```

## 2. Scientific-model risks

| ID | Risk | Likelihood | Impact | Trigger or evidence | Mitigation | Gate |
|---|---|---:|---:|---|---|---|
| PHY-001 | Planar MOC is interpreted as axisymmetric physics after revolution | High | High | Results labeled axisymmetric without geometric source terms | Label model planar; keep rendering separate; later axisymmetric validation | Phase 1 |
| PHY-002 | Strong underexpansion is forced into weak attached cells | High | Critical | Requested turn/pressure exceeds attached solution | Maximum-turn and pressure-rise gates; `MACH_DISK_REQUIRED` | Phase 0/1 |
| PHY-003 | Strong overexpansion ignores internal nozzle separation | Medium | Critical | Uniform exit assumed at large adverse pressure ratio | Require validated exit source or return scope status | Phase 1 |
| PHY-004 | Shock-cell termination is tuned to a desired visual count | High | High | `max_cells` controls reported cell count | Physical decay/core criteria; calibration/validation split | Phase 2 |
| PHY-005 | Thermal/IR plume is truncated at shock-train end | High | High | Radiation domain equals last coherent cell | Integral mixing continuation and separate IR criterion | Phase 3/4 |
| PHY-006 | Constant gamma is used outside valid temperature/composition range | High | High | High-temperature or changing mixture cases | Explicit model level and thermally perfect phase | Phase 6 |
| PHY-007 | Molecular-only radiation misses particles/continuum | Medium | High | Sooting or aluminized propellant case | Validity flag; particle phase; propellant-specific model | Phase 6 |
| PHY-008 | LTE radiation is invalid at low density/high altitude | Medium | High | Collisional timescales too long or known non-LTE bands | Applicability gate and future non-LTE design | Phase 5/7 |
| PHY-009 | Ambient coflow materially changes cells but is omitted | High for flight | High | Nonzero flight Mach | Restrict initial calibration to quiescent ambient; explicit ambient velocity | Phase 2/7 |
| PHY-010 | Chemistry-afterburning changes temperature beyond frozen model | Medium | High | Fuel-rich exhaust entrains oxygen | Frozen validity flag; finite-rate continuation | Phase 6 |

## 3. Numerical risks

| ID | Risk | Likelihood | Impact | Trigger | Mitigation | Gate |
|---|---|---:|---:|---|---|---|
| NUM-001 | Closed-form oblique-shock formula loses branch continuity | Medium | High | Small turn or near maximum turn | Bracketed residual solve and analytic limits | Phase 0 |
| NUM-002 | Pseudoinverse accepts nonphysical intersections | High | High | Parallel/backward lines produce finite point | Parameterized rays, conditioning, residual checks | Phase 0 |
| NUM-003 | MOC geometry depends strongly on fan resolution | High | High | Cell metrics fail convergence | Predictor-corrector and refinement study | Phase 1 |
| NUM-004 | Reduced train ODE hides discontinuous topology | Medium | High | Mach disk or core collapse inside a cell | Event detection and topology status | Phase 2 |
| NUM-005 | Integral state recovery becomes nonphysical | Medium | High | Negative temperature/radius/species | Conservative variables, bounded recovery, terminate on invalid state | Phase 3 |
| NUM-006 | RTE loses precision for tiny optical depth | High | Medium | `1-exp(-tau)` cancellation | `expm1` exact segment update | Phase 4 |
| NUM-007 | Spectral interpolation creates negative opacity | Medium | High | Sparse tables or extrapolation | Nonnegative interpolation, bounds checks, validation | Phase 5 |
| NUM-008 | Performance optimization changes scientific result | Medium | High | Chunking/GPU path diverges | Reference CPU path and cross-backend tolerances | Phase 5+ |

## 4. Data and calibration risks

| ID | Risk | Likelihood | Impact | Trigger | Mitigation | Gate |
|---|---|---:|---:|---|---|---|
| DAT-001 | Calibration and validation reuse the same trace | High | Critical | Random point split within one case | Split by complete operating condition/campaign | Phase 2 |
| DAT-002 | Pressure-ratio definition is ambiguous | High | High | NPR and exit ratio used interchangeably | Manifest field with explicit numerator/denominator | All validation |
| DAT-003 | Remote dataset changes or disappears | Medium | High | Test downloads mutable URL | Content-addressed immutable fixtures | Before CI validation |
| DAT-004 | Measurement uncertainty is omitted | High | High | Residuals treat observations as exact | Record known/unknown uncertainty separately | Calibration |
| DAT-005 | Coefficients are unidentifiable | Medium | High | Correlated Jacobian columns | Sensitivity/SVD, fix or combine parameters | Phase 2/3 |
| DAT-006 | Spectroscopic table provenance is lost | Medium | Critical | Output cannot identify line list/version | Table manifest and hashes in every result | Phase 5 |
| DAT-007 | Propellant-specific chemistry data are unavailable | Medium | High | No mechanism or species set | Keep generic frozen interface; do not fabricate composition | Phase 6 |

## 5. Software and project risks

| ID | Risk | Likelihood | Impact | Trigger | Mitigation | Gate |
|---|---|---:|---:|---|---|---|
| SW-001 | Foundation PR becomes a full rewrite | High | High | MOC/radiation code appears in Phase 0 | File-by-file blueprint and stop rules | Phase 0 |
| SW-002 | Compatibility wrappers contaminate new internals | Medium | High | New modules import `compat` | One-way dependency rule; architecture test | Phase 0 |
| SW-003 | Pydantic/NumPy result serialization is ad hoc | Medium | High | Raw `model_dump` of arrays | Explicit schema adapter and array artifacts | Phase 0/1 |
| SW-004 | Optional dependencies break base import | Medium | High | HAPI/Cantera imported at module top level | Extras, lazy adapters, installed smoke | Every release |
| SW-005 | Pyright target is claimed but not enforced | High | Medium | New files absent from strict include | CI strict include for new modules | Phase 0 |
| SW-006 | Large reference data enter the wheel | Medium | High | Package size increases unexpectedly | Manifest-only large data and wheel audit | Phase 5 |
| SW-007 | Legacy warning noise makes tests unusable | Medium | Medium | Warning emitted at import or every property access | Warn on legacy construction/call, not import | Phase 0 |
| SW-008 | Generated plots become regression truth | Medium | Medium | Image comparison replaces physical metrics | Scalar/conservation tests first; plots diagnostic | All phases |

## 6. Open decisions with working defaults

## DEC-001 — First-cell geometry fidelity

### Question

Should the first implementation remain planar MOC or immediately implement
axisymmetric MOC/finite volume?

### Working default

Implement and validate planar MOC first. Label it accurately and keep a future
axisymmetric solver behind the same result interfaces.

### Decision due

Before Phase 7 design.

## DEC-002 — Overexpanded external-cell scope

### Question

What overexpanded pressure-ratio range may use a supplied uniform exit state?

### Working default

Do not hard-code a universal threshold. Require exit-source metadata and a
validation/calibration applicability record. Return
`NOZZLE_SEPARATION_NOT_MODELED` when the active policy cannot justify the
state.

### Decision due

Before Phase 1 validation cases are finalized.

## DEC-003 — Mach-disk classifier

### Question

Should the reduced solver use an empirical pressure-ratio threshold, attached-
shock feasibility, or both?

### Working default

Use local attached-shock feasibility as a mandatory physics gate. Treat any
empirical Mach-disk criterion as a separately sourced correlation with
applicability metadata.

### Decision due

During Phase 1/2 validation design.

## DEC-004 — Pydantic result envelopes versus dataclass-only API

### Question

Should all public results be Pydantic models?

### Working default

Use Pydantic for boundary/configuration and serialized envelopes; frozen
slotted dataclasses for computational states. Provide explicit conversion.

### Decision due

Phase 0 API review.

## DEC-005 — SciPy as a core dependency

### Question

Should bounded roots and ODE integration rely on SciPy in the base install?

### Working default

Yes, if the project accepts the dependency. Do not maintain duplicate fragile
root/ODE implementations solely to avoid SciPy. If base-size constraints
object, define a separate numerics backend ADR before coding alternatives.

### Decision due

Before Phase 0 dependency commit.

## DEC-006 — Result artifact format

### Question

NPZ, HDF5, or Zarr for large arrays?

### Working default

Use NPZ for small deterministic test fixtures and define a storage interface
before committing to production HDF5/Zarr. JSON/YAML holds metadata only.

### Decision due

Before Phase 4 result persistence.

## DEC-007 — Spectral coordinate

### Question

Should internal spectroscopy use wavelength or wavenumber?

### Working default

Use wavenumber for line-list/cross-section generation and one explicitly tested
conversion layer to wavelength outputs. Never mix density-per-wavelength and
density-per-wavenumber without the Jacobian.

### Decision due

Phase 5 schema freeze.

## DEC-008 — Atmosphere propagation implementation

### Question

Build an internal model, use MODTRAN-like external tooling, or accept user-
supplied transmission/path radiance?

### Working default

Define an interface first and support user-supplied tabulated transmission and
path radiance. Select an external implementation in a later ADR.

### Decision due

Phase 5.

## DEC-009 — Sensor output scope

### Question

Radiometric band signal only, or focal-plane counts/noise as well?

### Working default

Phase 5 ends at spectral/band irradiance and a generic detector response
integral. Detailed focal-plane electronics and detection probability are a
separate consumer layer.

### Decision due

After Phase 5 validation.

## DEC-010 — Chemistry boundary source

### Question

Invoke CEA directly at runtime or import generated boundary states?

### Working default

Start with reproducible offline CEA result ingestion. Runtime coupling is
optional later and must not be required for gas-dynamics unit tests.

### Decision due

Phase 6.

## DEC-011 — Multiple nozzles

### Question

When should plume-plume interaction be modeled?

### Working default

Not before one-nozzle flow and radiation pass validation. Preserve `nozzle_id`
space in future schemas but do not add interaction physics early.

### Decision due

Phase 7 design.

## 7. Escalation rule

The coding agent should stop the current issue and record an ADR proposal when:

- an open decision materially changes public schema;
- a proposed shortcut would weaken a phase gate;
- a new dependency changes base-package installation;
- a validation dataset conflicts with the assumed model topology;
- or a scientific correlation is needed without a source or applicability
  range.

It should not resolve these by silently selecting the easiest implementation.

## 8. Risk review cadence

Review this register:

```text
at the start of each phase
when a validity status is added
when a calibration artifact changes
before any public release
when a downstream result contradicts upstream validation
```

Closed risks remain in the history with the commit, test, or validation artifact
that closed them.

<!-- END 26_risk_register_and_open_decisions.md -->


---

<!-- BEGIN 27_release_gates_and_definition_of_done.md -->

# Release Gates and Definition of Done

## 1. Purpose

This document defines what evidence is required before a phase, branch, or
release may be called complete. Passing unit tests alone is insufficient for a
scientific codebase; each phase needs equation verification, numerical
convergence evidence, validity behavior, documentation, and reproducible
artifacts.

## 2. Evidence classes

Every phase report shall classify evidence as:

```text
E0 source review
E1 algebraic/unit verification
E2 conservation verification
E3 numerical convergence verification
E4 correlation or external-data validation
E5 uncertainty and applicability evidence
E6 packaging and consumer integration evidence
```

No external-data agreement should compensate for failed algebra or
conservation.

## 3. Common continuous-integration matrix

Minimum supported CI after the Python baseline migration:

```text
Python 3.12: full tests, Ruff, Pyright, build, installed-wheel smoke
Python 3.13: full or compatibility test lane when dependencies support it
Linux: required
Windows or macOS: at least one portability lane before stable release
```

Optional dependencies use separate lanes:

```text
plot
spectroscopy
chemistry
all-extras integration
```

The core installation shall remain usable without spectroscopy or chemistry
extras.

## 4. Common quality commands

```bash
python -m pytest
python -m ruff check .
python -m pyright
python -m build
```

Additional release checks:

```text
install built wheel in a fresh environment
run import smoke test outside repository
run CLI --help and one minimal solve
validate JSON/YAML schemas
verify handoff/validation artifact checksums
```

## 5. Test expectations

### 5.1 Critical physics paths

Every equation branch and every structured failure branch must be exercised.
Coverage percentage is secondary to branch inventory, but critical equation
modules should have no known untested branch.

### 5.2 Regression tests

A regression fixture must record:

```text
case id
input schema version
model level
expected output and tolerance
reason the value is trusted
source equation or validation reference
whether value is a legacy anchor or corrected-physics anchor
```

### 5.3 Property tests

Where practical, use randomized/property tests for invariants:

```text
positive thermodynamic state
round-trip transformations
monotonic PM function
shock total-pressure loss
forward intersection symmetry
species sum and elemental conservation
nonnegative opacity
RTE limiting behavior
```

Random tests use fixed seeds in CI.

## 6. Numerical convergence requirements

A numerical solver is not phase-complete until a refinement study exists for
its dominant discretization.

### 6.1 Characteristic solver

Refine characteristic count and track:

```text
first-cell length
maximum radius
boundary pressure residual
centerline state
zone area
invariant residual
```

### 6.2 ODE mixing solver

Refine ODE tolerances and output sampling independently. Verify conserved
fluxes and event location stability.

### 6.3 Ray tracer

Refine image resolution, axial/radial field resolution, and intersection
thresholds separately.

### 6.4 Spectral solver

Refine spectral grid, cross-section interpolation grid, and line-wing cutoff or
band model settings.

### 6.5 Acceptance pattern

For output \(Q_h\) at refinement scale \(h\), report

\[
\Delta_h=|Q_h-Q_{h/r}|.
\]

Where asymptotic behavior is observed, estimate order

\[
p
\approx
\frac{\ln\left(|Q_h-Q_{h/r}|/|Q_{h/r}-Q_{h/r^2}|\right)
}{\ln r}.
\]

A nonmonotonic sequence must be reported and investigated; it is not evidence
of convergence merely because the finest two values look close.

## 7. Performance regression policy

Performance is measured only on validated benchmark cases. Record:

```text
wall time
peak resident memory
problem dimensions
hardware and software environment
backend
```

A PR that slows a benchmark materially must explain the tradeoff. Initial
policy: investigate regressions greater than 20% in median runtime or memory,
but do not reject a correctness fix solely to preserve a flawed fast path.

Benchmark thresholds become release gates only after stable baseline hardware
or normalized CI benchmarks are established.

## 8. Documentation gate

Every completed phase updates:

```text
public API documentation
governing equations and assumptions
validity limits
input/output units
example configuration
failure/status interpretation
validation report
migration notes when public behavior changes
```

Code comments should cite equation identifiers or source documents, not repeat
long derivations.

## 9. Artifact reproducibility gate

Every validation or calibration result includes:

```text
input file
code commit or version
schema version
calibration id/version
source data ids and checksums
solver tolerances
random seed if applicable
commands to reproduce
machine-readable metrics
plots as derived artifacts
```

A plot without its generating data and command is not sufficient evidence.

# Phase gates

## 10. Phase 0 — Foundation corrections

### Entry

- Current branch baseline recorded.
- Existing public API inventory generated.

### Required evidence

```text
correct throat-area equation
area--Mach branch inversion
explicit gas molecular weight
stagnation enthalpy semantics
weak/strong zero-turn limits
maximum attached-turn detection
target-pressure shock validity
forward ray intersection
corrected precursor geometry
matched-flow classification
legacy migration behavior
```

### Exit

- All Phase 0 tests and quality commands pass.
- No successful public closed zone contains nonfinite coordinates.
- Corrected behavior changes have migration notes.
- Wheel and CLI smoke tests pass.
- Phase 0 report is committed.

## 11. Phase 1 — Validated first cell

### Entry

Complete Phase 0 gate.

### Required evidence

```text
PM inverse verification
interior characteristic compatibility
centerline compatibility
ambient-pressure free boundary
mild underexpanded cell
mild attached overexpanded cell
detached/separation validity failures
closed-zone topology
fan-resolution convergence
first-cell correlation comparison
at least one external reference family
```

### Exit

- Matched flow returns zero cells.
- Underexpanded and mild overexpanded reference cases converge.
- Boundary pressure and tangent residuals pass.
- Centerline \(\theta=0\) residual passes.
- No case requiring a Mach disk is mislabeled successful.
- Phase 1 validation report is committed.

## 12. Phase 2 — Finite shock train

### Entry

Complete Phase 1 gate and approved calibration schema.

### Required evidence

```text
coherent-core shrinkage closure
pressure-amplitude decay closure
local cell spacing
physical termination
safety truncation
calibration provenance
sensitivity and identifiability
calibration/validation split
```

### Exit

- Cell count is an output.
- Physical and safety endpoints are distinguishable.
- Calibration applicability is checked at runtime.
- Uncertainty or sensitivity is reported.
- No illustrative calibration is a production default.

## 13. Phase 3 — Integral mixing plume

### Entry

Complete Phase 2 gate and a defined shock-train exit-state mapping.

### Required evidence

```text
mass balance
axial momentum balance
total enthalpy balance
frozen species balance
entrainment closure
state recovery
ODE convergence
equilibrium persistence events
axisymmetric field reconstruction
```

### Exit

- Conservative flux residuals pass.
- Zero-entrainment limit is verified.
- The field approaches ambient in enabled equilibrium cases.
- Physical and domain termination remain separate.
- Phase 3 report includes closure applicability.

## 14. Phase 4 — Gray radiative transfer

### Entry

A finite axisymmetric plume field or analytic test geometry is available.

### Required evidence

```text
Planck function and units
homogeneous slab analytic solution
zero-opacity limit
optically thin limit
optically thick limit
layer ordering
analytic chord lengths
ray-segment ordering
orientation-integral check
IR-domain termination
```

### Exit

- Exact segment RTE matches analytic cases.
- Ray geometry converges.
- Successful images contain finite nonnegative radiance.
- IR endpoint is not conflated with flow endpoint.

## 15. Phase 5 — Molecular spectral radiation

### Entry

Complete Phase 4 gate and approved spectroscopy-data policy.

### Required evidence

```text
cross-section generation reference
units and spectral-coordinate Jacobians
T/p interpolation error
mixture opacity
cache provenance
spectral convergence
atmosphere/sensor separation
heated-plume validation
```

### Exit

- Cross sections reproduce direct reference calculations within tolerance.
- Spectral/band outputs converge.
- Database/version metadata is preserved.
- At least one measured or authoritative plume-radiation case is compared.

## 16. Phase 6 — Thermochemistry and particles

### Entry

Complete Phase 3 and Phase 5 gates.

### Required evidence

```text
composition conversion
mixture thermodynamics
enthalpy inversion
CEA import provenance
frozen and equilibrium limits
elemental conservation
finite-rate energy coupling
particle zero limit
particle optical-table provenance
```

### Exit

- Species mass fractions and elements balance.
- Energy release matches species enthalpy change.
- Frozen chemistry recovers Phase 5 behavior.
- Particle-off behavior recovers the molecular model.
- Chemistry and particle optional dependencies are isolated.

## 17. Phase 7 design gate

Before axisymmetric CFD or flight effects begin, approve a separate design that
selects:

```text
axisymmetric MOC, internal finite volume, or external CFD coupling
turbulence closure
Mach-disk topology handling
nozzle-profile interface
chemistry coupling
GPU strategy
validation datasets
```

Phase 7 must not emerge accidentally as scattered patches to the reduced-order
solver.

# Release definitions

## 18. Research preview release

May contain provisional calibrations and limited model levels. Must clearly
state:

```text
not validated for certification or operational prediction
supported regimes
known missing physics
example versus validated calibration status
```

## 19. Beta release

Requires:

- all gates for advertised model levels;
- stable schema major version;
- migration guide;
- external validation report;
- uncertainty/applicability metadata;
- packaged examples and installed-wheel tests.

## 20. Stable release

Requires:

- no known critical correctness defect in advertised regimes;
- at least one independent validation family per advertised high-level output;
- documented public API support policy;
- calibration/data provenance and licensing review;
- reproducible release artifacts;
- changelog and migration notes.

## 21. Definition of done for an issue

An issue is done only when:

```text
scope implemented
non-goals remain untouched
equations/contracts traceable
tests cover success and failure paths
numerical residuals reported
public compatibility addressed
docs updated
quality commands pass
completion report supplied
follow-on limitations identified
```

## 22. Definition of done for a pull request

A PR is done only when:

- linked issues are complete;
- review comments are resolved;
- no hidden coefficient, unit, or validity assumption was introduced;
- changes are small enough to review coherently;
- CI and local quality evidence agree;
- generated artifacts are reproducible;
- the merge target remains in a releasable state.

## 23. No-go conditions

Do not release an advertised capability when:

```text
a known wrong equation remains on the active path
a root failure is logged but returned as success
matched flow creates shock cells
detached/Mach-disk cases are forced through attached topology
successful geometry contains NaNs or self intersections
calibration and validation data overlap without disclosure
spectral units or coordinate Jacobians are ambiguous
chemistry violates elemental or energy conservation
large model-form limitations are hidden from output metadata
```

## 24. Final phase-report template

```text
Phase and version
Scope completed
Equations/contracts implemented
Source and calibration provenance
Verification matrix
Convergence evidence
Validation evidence
Uncertainty/sensitivity
Performance
Public API/schema changes
Known limits and no-go regimes
Reproduction commands
Release recommendation: GO / GO WITH LIMITATIONS / NO-GO
```

<!-- END 27_release_gates_and_definition_of_done.md -->


---

<!-- BEGIN 28_consumer_profiles_and_query_contracts.md -->

# Consumer Profiles and Query Contracts

## 1. Why consumer profiles exist

Consumer profiles are convenience descriptions of common capability bundles.
They are not base classes and do not constrain provider implementations.

## 2. Signature profile

Required capability:

```text
directional-spectral-intensity v1
```

Optional capabilities:

```text
spatial-support v1
uncertainty v1
```

### Query

```python
@dataclass(frozen=True)
class DirectionalSpectralIntensityQuery:
  wavelength_m: NDArray[np.float64]       # (n_lambda,)
  source_to_observer_direction_plume: NDArray[np.float64]  # (n_view, 3)
####
```

Snapshot time is already bound to the `PlumeSnapshot`. If a stateless source
is preferred, time may be an explicit query coordinate, but the semantic
product remains the same.

### Result

```python
@dataclass(frozen=True)
class DirectionalSpectralIntensityResult:
  wavelength_m: NDArray[np.float64]
  source_to_observer_direction_plume: NDArray[np.float64]
  spectral_radiant_intensity_w_sr_m: NDArray[np.float64]  # (n_view, n_lambda)
  quality_flags: tuple[str, ...]
  provenance_id: str
####
```

### Physics quantity

\[
J_\lambda(\hat{\mathbf s})
=\int_{A_\perp}L_{\lambda,\mathrm{source}}(u,v,\hat{\mathbf s})\,du\,dv.
\]

A direct table provider may supply \(J_\lambda\) without evaluating the
integral at runtime.

## 3. Spatial engineering profile

Minimum useful capability:

```text
spatial-support v1
```

Typical additional capabilities:

```text
axisymmetric-zone-field v1
centerline-tube-field v1
local-flow-state v1
projected-area v1
```

Spatial support is intentionally weaker than a mesh. It answers where the
plume may contribute without claiming a unique plume surface.

### Conservative spatial support

```python
@dataclass(frozen=True)
class SpatialSupport:
  plume_frame_aabb_min_m: tuple[float, float, float]
  plume_frame_aabb_max_m: tuple[float, float, float]
  characteristic_extent_m: float
  support_definition: str
  is_conservative: bool
####
```

## 4. Resolved radiometry profile

Required capability:

```text
spectral-ray-transfer v1
```

Query:

```text
observer_origin_plume_m        (n_ray,3)
observer_to_scene_direction    (n_ray,3)
maximum_distance_m             (n_ray,)
wavelength_m                   (n_lambda,)
```

Result:

```text
source_spectral_radiance       (n_ray,n_lambda)
background_transmittance       (n_ray,n_lambda)
```

with transfer semantics

\[
L_{\lambda,\mathrm{out}}
=
L_{\lambda,\mathrm{source}}
+
T_\lambda L_{\lambda,\mathrm{background}}.
\]

Returning source radiance and transmittance separately is mandatory because a
plume can attenuate vehicle, terrain, sky, or Earth radiance behind it.

## 5. Physical-field coupling profile

Required capability:

```text
local-flow-state v1
```

or a provider-specific structured field capability such as
`axisymmetric-zone-field` or `centerline-tube-field`.

Canonical local state, when available:

\[
\mathbf q=
(\rho,p,T,\mathbf u,\mathbf Y,\text{particles}).
\]

Not every provider must supply every component. The capability schema must
state required/optional fields and quality flags.

## 6. Point-source validity

A signature product does not guarantee that the source is unresolved at an
arbitrary observer range.

Providers should expose at least one of:

```text
minimum_valid_observer_range_m
characteristic_extent_m
angular_validity_model
```

A consumer may evaluate

\[
\chi=\frac{R}{D_\mathrm{source}}.
\]

If its own point-source criterion fails, it should reject the approximation or
request resolved ray transfer when available.

## 7. Consumer selection algorithm

A consumer should:

1. declare the semantic product it needs;
2. inspect the provider descriptor;
3. request the capability and compatible major version;
4. validate wavelength/time/angular/spatial applicability;
5. batch queries according to the execution profile;
6. preserve returned provenance and quality flags.

It must not select a provider by testing whether it is named `LowFidelity` or
`CurvedPlume`.

<!-- END 28_consumer_profiles_and_query_contracts.md -->


---

<!-- BEGIN 29_provider_taxonomy_and_composition.md -->

# Provider Taxonomy and Composition

## 1. Taxonomy purpose

This taxonomy gives planning language for provider families without turning
those labels into incompatible public interfaces.

## 2. Four independent descriptors

### Morphology

```text
straight
curved
rotor-washed
crossflow-deflected
multi-source/general-3d
```

### Flow fidelity

```text
none/signature-only
empirical
reduced-order analytical
integral conservation model
imported field/surrogate
Euler/RANS/LES
```

### Radiation fidelity

```text
none
gray LTE
band/correlated-k
line-by-line LTE
non-LTE
particle/scattering coupled
```

### Time model

```text
steady
quasi-steady sequence
transient
stochastic/ensemble
```

These four descriptors plus validation/applicability metadata are sufficient
for selection and provenance. Do not collapse them into one ordinal fidelity.

## 3. Provider composition patterns

### Pattern A — Direct signature

```text
SignatureTableProvider
   -> directional-spectral-intensity
```

No geometry is exposed or required.

### Pattern B — Analytical flow + radiation adapters

```text
ShockCellAnalyticalProvider
   -> axisymmetric-zone-field
       + OpticalPropertyModel
         -> spectral-ray-transfer
             -> FarFieldFromRays
                 -> directional-spectral-intensity
```

### Pattern C — Near field + downstream continuation

```text
ShockCellAnalyticalProvider
   -> handoff state at shock-train termination
       -> IntegralStraightPlumeProvider
           -> CompositeSpatialPlume
```

The composite snapshot can expose a single spatial support and local-state
view while retaining segment provenance.

### Pattern D — Straight to curved environmental continuation

```text
Nozzle/near-field provider
   -> handoff flux state
       + AmbientFlowField
         -> CurvedIntegralPlumeProvider
```

The curved provider owns deflection and wash physics. The downstream consumer
still sees standard spatial/radiometric capabilities.

### Pattern E — High-fidelity field, low-bandwidth product

```text
CFD/LES offline run
   -> radiative postprocessing
       -> directional signature table
           -> SignatureTableProvider
```

This is a high-fidelity provenance product with a signature-only capability.
It demonstrates why capability is not fidelity.

## 4. Handoff state between providers

Provider chaining should use a neutral conservative handoff state rather than
passing one provider's internal zone type.

Recommended first contract:

```python
@dataclass(frozen=True)
class PlumeFluxSection:
  center_plume_m: tuple[float, float, float]
  normal_plume: tuple[float, float, float]
  area_m2: float
  mass_flow_kg_s: float
  momentum_flux_plume_n: tuple[float, float, float]
  total_enthalpy_flux_w: float
  species_mass_flow_kg_s: tuple[tuple[str, float], ...]
  pressure_pa: float
  characteristic_radius_m: float
  provider_metadata: Mapping[str, object]
####
```

The defining invariants are conservation quantities, not a particular
cross-sectional shape.

For a uniform section:

\[
\dot m=\rho u_n A,
\]

\[
\mathbf \Pi
=\dot m\,\mathbf u+(p-p_a)A\mathbf n,
\]

\[
\dot H_0=\dot m h_0.
\]

A richer provider may additionally expose profile moments or full fields.

## 5. Composite provider

A `CompositePlumeProvider` may orchestrate multiple provider segments while
presenting one snapshot.

Responsibilities:

- create each segment with explicit handoff contracts;
- combine spatial support conservatively;
- route spatial queries to the appropriate segment;
- compose ray transfer in front-to-back order;
- sum unresolved independent source intensity only when occlusion/attenuation
  assumptions allow it;
- preserve per-segment provenance.

It must not erase validity boundaries between segments.

## 6. Curved plume geometric contract

For reduced-order curved plumes, use centerline arc length \(s\):

\[
\mathbf c(s),\quad
\mathbf t(s)=\frac{d\mathbf c}{ds},\quad
A(s),\quad
R(s).
\]

A local query point may be parameterized by

\[
\mathbf x=\mathbf c(s)+\eta\mathbf n(s)+\zeta\mathbf b(s).
\]

The transported frame should use a numerically stable convention such as a
parallel-transport frame; Frenet frames are unsuitable at vanishing curvature.

Curvature is therefore a property of one spatial capability implementation,
not a new top-level plume interface.

<!-- END 29_provider_taxonomy_and_composition.md -->


---

<!-- BEGIN 30_provider_contracts_v1.md -->

# Provider Contracts v1

## 1. Stable lifecycle contracts

```python
DefinitionT = TypeVar('DefinitionT')
ConfigurationT = TypeVar('ConfigurationT')
OperatingStateT = TypeVar('OperatingStateT')


class PlumeProvider(Protocol[DefinitionT, ConfigurationT, OperatingStateT]):
  @property
  def descriptor(self) -> PlumeProviderDescriptor:
    ...
  ####

  def create_session(
      self,
      definition: DefinitionT,
      configuration: ConfigurationT,
  ) -> PlumeSession[OperatingStateT]:
    ...
  ####
####


class PlumeSession(Protocol[OperatingStateT]):
  def snapshot(self, operating_state: OperatingStateT) -> PlumeSnapshot:
    ...
  ####

  def close(self) -> None:
    ...
  ####
####
```

## 2. Snapshot capability lookup

Use explicit capability IDs plus typed capability objects.

```python
class PlumeSnapshot:
  descriptor: PlumeProviderDescriptor
  termination: TerminationReport | None
  provenance: PlumeProvenance

  def get_capability(
      self,
      capability_id: CapabilityId,
      major_version: int,
  ) -> PlumeCapability:
    ...
  ####
####
```

Unsupported capability requests raise `UnsupportedCapabilityError`. A major
version mismatch raises `CapabilityVersionMismatchError`.

## 3. Descriptor

```python
@dataclass(frozen=True)
class PlumeProviderDescriptor:
  provider_id: str
  provider_version: str
  core_contract_major_version: int
  capability_versions: Mapping[CapabilityId, int]
  definition_schema_id: str
  configuration_schema_id: str
  operating_state_schema_id: str
  morphology: PlumeMorphology
  fidelity: ProviderFidelity
  execution: ProviderExecutionProfile
  applicability: ProviderApplicability
####
```

## 4. Fidelity metadata

```python
@dataclass(frozen=True)
class ProviderFidelity:
  geometry_model: str
  spatial_dimensionality: str
  temporal_model: str
  flow_model: str
  mixing_model: str
  thermochemistry_model: str
  radiation_model: str
  environmental_coupling: str
  validation_level: str
####
```

## 5. Execution profile

```python
@dataclass(frozen=True)
class ProviderExecutionProfile:
  time_access: TimeAccessMode
  concurrency: ConcurrencyMode
  deterministic: bool
  supports_direction_batching: bool
  maximum_direction_batch_size: int | None
  checkpointable: bool
  preferred_device: str
  snapshot_retention: SnapshotRetention
####
```

A GPU session may declare `MONOTONIC_FORWARD` and
`UNTIL_NEXT_SNAPSHOT`; a table or analytical provider will normally declare
`RANDOM_ACCESS` and `INDEPENDENT`.

## 6. Applicability

Applicability must be queryable before expensive execution when practical.

Possible bounds:

```text
time
Mach
pressure ratio
altitude/ambient pressure
wavelength
view direction/angular region
observer distance for unresolved approximation
spatial domain
supported propellant/species family
```

No silent extrapolation is allowed.

## 7. Termination

Spatial providers report structured termination separately from snapshot
validity.

Recommended reasons:

```text
NO_PRESSURE_MISMATCH
WEAK_WAVE_CUTOFF
PRESSURE_OSCILLATION_DECAYED
MIXING_LAYER_REACHED_AXIS
CORE_BECAME_SUBSONIC
AMBIENT_EQUILIBRIUM
MACH_DISK_REQUIRED
NOZZLE_SEPARATION_NOT_MODELED
SPATIAL_DOMAIN_LIMIT
TEMPORAL_DOMAIN_LIMIT
REQUESTED_CONSTRUCTION_LIMIT
PROVIDER_FAILURE
```

The report contains `is_physical` so safety/domain truncation is never confused
with a predicted plume endpoint.

## 8. Error taxonomy

```text
UnsupportedCapabilityError
CapabilityVersionMismatchError
ProviderConfigurationError
OperatingStateDomainError
SpectralDomainError
AngularDomainError
TemporalDomainError
SpatialDomainError
ContractViolationError
SnapshotInvalidatedError
ProviderClosedError
```

Physical out-of-model conditions should normally be structured domain/status
results rather than generic numerical exceptions.

<!-- END 30_provider_contracts_v1.md -->


---

<!-- BEGIN 31_unified_conformance_and_testing.md -->

# Unified Provider Conformance and Testing

## 1. Test layers

Every provider has four independent test layers:

```text
contract conformance
provider-specific physics verification
cross-provider semantic equivalence
consumer integration
```

## 2. Universal snapshot invariants

Verify:

- descriptor capability registry equals actual capability objects;
- capability major versions are explicit;
- definition/configuration/operating-state inputs are not mutated;
- immutable or defensively copied result arrays;
- finite values unless the capability explicitly permits masks;
- provenance is present;
- applicability and quality flags are preserved;
- unsupported capabilities fail explicitly;
- deterministic providers reproduce identical results;
- snapshot retention rules are enforced.

## 3. Signature capability conformance

For `directional-spectral-intensity v1`:

Input requirements:

```text
wavelengths finite, positive, strictly increasing
view directions finite unit vectors
```

Output requirements:

```text
shape = (n_view,n_lambda)
finite
nonnegative
same requested ordering
correct units W/(sr m)
```

Axisymmetric invariant:

\[
J_\lambda(\hat{\mathbf s}_1)
=J_\lambda(\hat{\mathbf s}_2)
\]

whenever both directions have the same dot product with the plume axis.

## 4. Ray-transfer conformance

A miss must return exactly:

```text
source radiance = 0
background transmittance = 1
```

For consecutive homogeneous segments:

\[
L_{out}=S_2(1-T_2)+T_2\left[S_1(1-T_1)+T_1L_{bg}\right].
\]

The capability result must reproduce this composition.

## 5. Rich-to-simple equivalence

For a provider exposing both ray transfer and directional intensity, compare
native unresolved intensity against orthographic integration of ray source
radiance:

\[
J_\lambda(\hat{\mathbf s})
=\int L_{\lambda,source}\,dA_\perp.
\]

The comparison tolerance is provider/fidelity-specific and must be documented.

## 6. Signature table tests

- exact grid points reproduce stored data;
- interpolation is deterministic;
- extrapolation defaults to rejection;
- table asset digest participates in provenance;
- angular coordinate conventions are unit tested;
- table periodicity/symmetry assumptions are explicit.

## 7. Shock-cell provider tests

In addition to the physics verification suite:

- provider output matches direct solver output for legacy benchmark states;
- current geometry never leaks placeholder NaN polygons;
- current construction-limit termination is marked nonphysical;
- `maximum_construction_passes` maps deterministically to legacy `num_plumes`;
- provider capability absence prevents premature IR claims.

## 8. Curved provider tests

- zero crossflow reduces to the straight-provider baseline within tolerance;
- rigid rotation/translation of environmental inputs produces the equivalent
  transformed plume;
- transported frame remains continuous through zero-curvature regions;
- spatial support conservatively encloses the centerline/tube field;
- source/ray results remain in the canonical plume frame;
- curvature does not change signature/ray API semantics.

## 9. Cross-fidelity semantic tests

When multiple providers represent the same canonical condition, compare only
products they both claim.

Examples:

```text
shock analytical vs CFD surrogate:
  first-cell length
  spatial support
  selected pressure diagnostics

ray-derived signature vs signature table:
  J_lambda(direction)

straight integral vs curved provider at zero external flow:
  centerline
  radius
  integral fluxes
```

These tests verify semantic interoperability, not numerical identity between
different fidelity models.

## 10. Consumer swap test

One consumer pipeline must be exercised without code changes against at least:

```text
constant fixture source
signature-table source
analytical plume + ray adapter source
```

A spatial consumer should similarly be able to swap straight analytical and
curved reduced-order providers when both implement the requested capability.

<!-- END 31_unified_conformance_and_testing.md -->


---

<!-- BEGIN 32_merged_implementation_roadmap.md -->

# Merged Implementation Roadmap

## Guiding sequence

The interface seam should be introduced early, while expensive radiation and
curved-plume physics remain later. The provider contract is additive and must
not destabilize Phase 0 physics corrections.

## PR I0 — Provider contract foundation

Add:

```text
src/exhaust_plume/contracts/
  capability.py
  descriptor.py
  errors.py
  execution.py
  provenance.py
  snapshot.py
  spatial.py
  radiometry.py

src/exhaust_plume/providers/
  __init__.py
```

No new physics. No new required dependency beyond already approved project
foundation choices.

Acceptance:

- provider/session/snapshot lifecycle;
- capability registry and major versions;
- morphology/fidelity/execution separated;
- fake provider conformance tests;
- existing public solver API unchanged.

## PR I1 — Corrected exit-state boundary

This merges interface PR work with Phase 0 foundation work.

Refactor:

```text
legacy calculatePlumeZones(total conditions,...)
  -> corrected nozzle exit state
  -> calculatePlumeZonesFromExitState(...)
```

The new boundary uses explicit gas properties and corrected mass-flow/nozzle
relations from the foundation plan.

Acceptance:

- old API remains available;
- no duplicated core solve;
- corrected foundation numerical fixtures pass;
- exit-state route is the provider entry point.

## PR I2 — ShockCellAnalyticalProvider

Initial capabilities:

```text
spatial-support
axisymmetric-zone-field
projected-area
```

No spectral capability yet.

Acceptance:

- provider/direct-solver regression equivalence;
- validity domain explicit;
- structured termination;
- invalid geometry rejected;
- neutral zones, not legacy `ZoneResult`, cross the provider boundary.

## Physics Phase 1 — validated first cell

Continue the existing `MOC-A` through `MOC-F` work packets. Provider semantics
remain unchanged; the internal implementation improves.

On completion, provider fidelity metadata and validation evidence are updated.

## Physics Phase 2 — finite shock train

Add physical termination and calibrated decay. `maximum_construction_passes`
remains a safety bound only.

## PR I3 — Conservative provider handoff section

Implement `PlumeFluxSection` to permit near-field -> downstream provider
composition without leaking provider internals.

## Physics Phase 3 — straight integral mixing provider

Implement as a separate provider or continuation segment with standard spatial
capabilities.

## PR I4 — Ray-transfer infrastructure

Add optical-property and axisymmetric ray-transfer adapters. Validate gray LTE
first.

Capabilities:

```text
spectral-ray-transfer
```

## PR I5 — FarFieldFromRays adapter

Derive:

```text
directional-spectral-intensity
```

from ray transfer through orthographic integration.

This creates the first provider path supporting both major consumer profiles.

## PR I6 — SignatureTableProvider

Implement direct unresolved source lookup with explicit interpolation,
extrapolation, asset digest, and validity metadata.

This is the canonical proof that a signature consumer does not require exposed
geometry.

## Physics Phase 5 — molecular spectral model

Add HITEMP/HAPI-backed cross-section generation and validated spectral
postprocessing behind optical-property interfaces.

## PR I7 — Consumer radiometric adapter

Implement a package-neutral source adapter that consumes
`directional-spectral-intensity`. A downstream application can wrap it without
an Exhaust-Plume dependency on that consumer.

## Physics Phase C1 — curved integral plume

Before implementation, approve a dedicated curved-plume physics document that
defines:

- ambient flow-field contract;
- centerline momentum equations;
- entrainment closure in crossflow;
- parallel-transport local frame;
- shock-containing near-field handoff;
- validity regime under rotor wash/crossflow.

Then implement `CurvedIntegralPlumeProvider` using the same standard spatial and
radiometric capability interfaces.

## Physics Phase 6 — thermochemistry and particles

Proceed under the existing chemistry/particle plans. The provider capability
surface remains stable while fidelity metadata changes.

## PR I8 — Imported field provider

Support CFD/RANS/LES data with local-flow and spatial capabilities. Optical
adapters may operate on imported fields.

## PR I9 — GPU transient provider

Only after execution-profile conformance is implemented:

- monotonic time declared;
- snapshot lifetime enforced;
- direction/ray batching supported;
- checkpointability explicit;
- semantic host results match capability contracts.

## Required cross-cutting rule

Every physics phase may improve an existing provider or add a new provider,
but it may not alter consumer semantics simply because fidelity increased or
the plume became curved.

<!-- END 32_merged_implementation_roadmap.md -->


---

<!-- BEGIN 33_coding_agent_interface_kickoff_prompt.md -->

# Coding-Agent Prompt: Unified Provider Interface Foundation

Implement only the provider-interface foundation described by:

```text
00_unified_plume_architecture.md
28_consumer_profiles_and_query_contracts.md
29_provider_taxonomy_and_composition.md
30_provider_contracts_v1.md
31_unified_conformance_and_testing.md
32_merged_implementation_roadmap.md
10_coding_agent_execution_protocol.md
25_migration_release_and_compatibility_plan.md
```

## Scope

Create the additive provider/session/snapshot/capability contracts and a fake
provider conformance suite. Do not implement new plume physics, spectroscopy,
external-consumer integration, or curved-plume dynamics in this PR.

## Required design

- provider-specific strongly typed Definition/Configuration/OperatingState;
- generic capability-bearing snapshots;
- explicit capability IDs and major versions;
- separate morphology, fidelity, applicability, and execution metadata;
- two semantic product paths supported by contracts:
  - unresolved directional spectral intensity;
  - spatial/resolved products;
- geometry must remain optional;
- capability absence must raise a typed error;
- snapshot lifetime semantics must be representable;
- existing solver API must remain unchanged.

## Coding requirements

- Python 3.12+ project target where the migration plan allows it;
- complete type annotations;
- NumPy typing for numerical arrays;
- frozen public contracts;
- preserve existing TODOs;
- end every scope with `####` according to project convention;
- pytest, ruff, and pyright coverage;
- concise durable documentation only.

## Tests

At minimum add fake providers demonstrating:

1. a signature-only table-like provider with no geometry;
2. a spatial-only analytical-like provider with no radiation;
3. a provider exposing both ray transfer and directional intensity;
4. explicit unsupported capability failure;
5. capability version mismatch failure;
6. independent versus invalidatable snapshot semantics;
7. provider descriptor separation of morphology/fidelity/execution.

## Completion report

Report:

```text
files changed
contracts introduced
compatibility impact
tests added
pytest result
ruff result
pyright result
remaining non-goals
```

Do not proceed to physics refactoring in the same PR.

<!-- END 33_coding_agent_interface_kickoff_prompt.md -->


---

<!-- BEGIN 34_comprehensive_work_plan.md -->

# Comprehensive Work Plan

## 1. Purpose

This document is the master execution plan for evolving `sheepfling/Exhaust-Plume`
from the current idealized shock-cell study into a family of swappable plume
providers that serve two primary consumer profiles:

1. **Signature consumers** need intrinsic unresolved spectral radiant intensity
   as a function of time, wavelength, and source-to-observer direction. They do
   not require exposed geometry.
2. **Spatial/physical consumers** need plume support, geometry, local state,
   optical-medium properties, resolved ray transfer, or other spatial products.

The project must support straight, curved, rotor-washed, imported, and future
high-fidelity plumes through the same provider lifecycle. Morphology and
fidelity are metadata and applicability constraints; they are not separate API
families.

This plan consolidates the physics roadmap, provider-interface roadmap,
validation strategy, migration strategy, and coding-agent task packets into one
dependency-ordered program. It is authoritative for execution order. The
specialized documents remain authoritative for their detailed equations,
algorithms, contracts, and test fixtures.

## 2. Target outcome

The target package provides a stable plume-provider framework and several
interchangeable implementations:

```text
PlumeProvider
  -> PlumeSession
      -> PlumeSnapshot
          -> optional, versioned capabilities
```

The initial provider family is:

```text
SignatureTableProvider
    direct unresolved signature; no geometry required

ShockCellAnalyticalProvider
    corrected near-field shock-containing plume

IntegralStraightPlumeProvider
    downstream entraining and mixing continuation

CurvedIntegralPlumeProvider
    curved/crossflow/rotor-washed continuation

ImportedFieldProvider
    CFD/RANS/LES field adapter

GpuTransientPlumeProvider
    future transient general-3D provider
```

The richer physics path is compositional:

```text
corrected nozzle exit state
    -> analytical shock-containing near field
        -> conservative PlumeFluxSection handoff
            -> straight or curved mixing continuation
                -> optical-property adapter
                    -> resolved spectral ray transfer
                        -> far-field directional spectral intensity
```

A signature-only provider may bypass every spatial stage and implement
`directional-spectral-intensity` directly.

## 3. Non-negotiable program rules

1. **Provider-specific inputs, generic capability outputs.** A provider may
   require specialized inputs, but consumer-visible products follow stable,
   versioned capability contracts.
2. **No API split by morphology or fidelity.** Straight, curved, washed,
   analytical, tabulated, and CFD plumes use the same lifecycle.
3. **Geometry is optional.** A provider may use geometry internally while
   exposing only a signature.
4. **One physical plume may contain multiple model segments.** Shock cells and
   the downstream mixed plume are not separate consumer-level plume types.
5. **One plume contains multiple shock cells.** Repeated construction passes
   are not separate plumes.
6. **SI units internally; radians internally.** Degree conversion occurs only
   at CLI, display, or explicitly legacy boundaries.
7. **No hidden dry-air assumptions for rocket exhaust.** Gas properties are
   explicit.
8. **No silent extrapolation, fallback, or fabricated capability.** Domain
   violations and unsupported products are explicit.
9. **Physical termination and safety truncation are distinct.** Every spatial
   result reports a structured termination reason and whether it is physical.
10. **Radiation remains separable from flow.** Flow providers expose neutral
    fields or optical-medium products; radiation adapters derive signatures.
11. **Atmosphere, range, optics, and detector response are not intrinsic plume
    emission.** They are downstream observation layers.
12. **Every correlation and closure has provenance, applicability, calibration
    identity, and uncertainty metadata.**
13. **Every phase is gated.** Later fidelity cannot compensate for an earlier
    failed conservation, geometry, convergence, or contract gate.
14. **Public numerical contracts are immutable and fully typed.** Python 3.12+
    is the target baseline; scopes follow the repository's `####` convention.

## 4. Consumer products and capabilities

### 4.1 Signature profile

The smallest consumer port evaluates intrinsic spectral radiant intensity:

\[
J_\lambda(t,\hat{\mathbf s})
\quad [\mathrm{W\,sr^{-1}\,m^{-1}}].
\]

The input direction is a finite unit vector from source to observer in the
plume-local frame. The result excludes range loss, atmosphere, optics, detector
response, and sensor noise.

Required capability:

```text
directional-spectral-intensity v1
```

Optional simplified products may include band-integrated intensity, but the
spectral quantity remains the canonical interchange product.

### 4.2 Spatial/physical profile

A spatial consumer may request any supported subset of:

```text
spatial-support v1
axisymmetric-zone-field v1
centerline-tube-field v1
local-flow-state v1
optical-medium v1
spectral-ray-transfer v1
projected-area v1
scene-radiance-renderer v1
uncertainty v1
```

Capability absence is normal. A table provider is not defective because it has
no geometry, and an early shock-cell provider is not defective because it has
no spectral capability.

### 4.3 Capability derivation lattice

Richer products can often derive simpler products:

```text
local flow / species / particles
    + optical-property model
        -> optical medium
            -> spectral ray transfer
                -> spectral radiance image
                    -> directional spectral radiant intensity
```

The reverse derivations are generally impossible. Therefore the architecture
uses a product lattice, not a fidelity inheritance hierarchy.

## 5. Physical segmentation of plume models

The architecture distinguishes two physical regions while keeping one provider
surface.

### 5.1 Shock-containing near field

This region begins at the nozzle exit and contains expansion fans, compression
waves, shocks, possible shock cells, and a coherent supersonic core. The first
implementation is a corrected planar analytical/MOC study model presented as
an approximate axisymmetric field only where documented.

Primary provider:

```text
ShockCellAnalyticalProvider
```

Initial products:

```text
spatial-support
axisymmetric-zone-field
projected-area
termination and validity diagnostics
```

### 5.2 Entraining downstream plume

This region begins at a conservative cross-section handoff and continues mass,
momentum, total enthalpy, species, radius, and centerline evolution. It may be
straight or curved by ambient flow, rotor wash, buoyancy, or other forcing.

Primary providers:

```text
IntegralStraightPlumeProvider
CurvedIntegralPlumeProvider
```

Primary products:

```text
spatial-support
centerline-tube-field
local-flow-state
termination and validity diagnostics
```

### 5.3 Conservative handoff

Provider composition uses a neutral `PlumeFluxSection`, not legacy internal
zone objects. At a handoff plane with normal \(\mathbf n\):

\[
\dot m = \int_A \rho\,\mathbf u\!\cdot\!\mathbf n\,dA,
\]

\[
\mathbf\Pi = \int_A
\left[\rho\mathbf u(\mathbf u\!\cdot\!\mathbf n)+p\mathbf n\right]dA,
\]

\[
\dot H_0 = \int_A \rho h_0(\mathbf u\!\cdot\!\mathbf n)\,dA,
\]

\[
\dot m_s = \int_A \rho Y_s(\mathbf u\!\cdot\!\mathbf n)\,dA.
\]

The handoff also records area, centroid, local frame, average pressure,
applicability, uncertainty, and provenance. Downstream providers reconstruct a
state from these conserved quantities without depending on how the upstream
provider represented geometry.

## 6. Provider capability matrix

| Provider | Direct signature | Spatial support | Neutral field | Ray transfer | Typical morphology | Initial status |
| --- | --- | --- | --- | --- | --- | --- |
| `SignatureTableProvider` | Yes | No | No | No | Metadata only | Early parallel proof |
| `ShockCellAnalyticalProvider` | Via adapter later | Yes | Axisymmetric zones | Via adapter later | Straight | Critical physics path |
| `IntegralStraightPlumeProvider` | Via adapter later | Yes | Centerline tube/local state | Via adapter later | Straight | After conservative handoff |
| `CurvedIntegralPlumeProvider` | Via adapter later | Yes | Centerline tube/local state | Via adapter later | Curved/washed/crossflow | After straight integral model |
| `ImportedFieldProvider` | Optional | Yes | Local field | Optional | General | Later adapter path |
| `GpuTransientPlumeProvider` | Optional | Yes | General 3-D field | Optional | General 3-D | Final execution path |

## 7. Stable provider contracts

The provider-contract foundation must stabilize the following concepts before
physics providers depend on it:

```text
PlumeProvider[DefinitionT, ConfigurationT, OperatingStateT]
PlumeSession[OperatingStateT]
PlumeSnapshot
PlumeProviderDescriptor
ProviderFidelity
ProviderExecutionProfile
ProviderApplicability
PlumeProvenance
TerminationReport
CapabilityId + major version
```

The snapshot is a capability registry. Unsupported requests raise typed
contract errors. Physical out-of-model states normally return structured
validity/termination results rather than arbitrary numerical exceptions.

Execution behavior is explicit. A random-access table provider and a
monotonic-time GPU provider may implement the same capability semantics while
having different snapshot lifetime, batching, concurrency, and checkpointing
constraints.

## 8. Master workstreams

The program is organized into eleven workstreams. Milestones below combine
workstreams into reviewable pull requests.

### W0 — Governance, source baseline, and decisions

Maintain the reviewed branch/blob baseline, architecture decisions, equation
registry, risk register, calibration identity, and release gates. Re-audit a
source file before applying a packet when its blob SHA changes.

### W1 — Provider contracts and consumer semantics

Implement lifecycle contracts, capabilities, descriptors, applicability,
execution behavior, provenance, conformance tests, and package-neutral consumer
ports.

### W2 — Corrected gas, nozzle, shock, and geometry foundation

Correct the choked mass-flow equation, explicit gas-property flow, total-energy
naming, weak/strong shock branches, attached-shock validity, expansion-regime
classification, line/ray intersections, precursor geometry, and result types.

### W3 — Validated shock-cell physics

Implement robust Prandtl–Meyer inversion, planar characteristics, centerline
compatibility, ambient-pressure free boundary, mild underexpanded and attached
overexpanded first cells, topology checks, correlation comparison, and
convergence studies.

### W4 — Finite shock train and physical termination

Add calibrated coherent-core shrinkage, pressure-amplitude decay, local cell
spacing, downstream reduced-order cells, total-pressure loss, physical
termination, safety truncation, diagnostics, sensitivity, and validation.

### W5 — Straight and curved mixing continuations

Implement conservative handoff, straight integral entrainment, state recovery,
field reconstruction, then curved-centerline dynamics and local transported
frames under crossflow/rotor-wash forcing.

### W6 — Radiative transfer and far-field signatures

Implement Planck radiation, axisymmetric ray geometry, gray LTE transfer,
spectral images, angular integration, far-field signature adapters, molecular
cross sections, atmosphere interfaces, and detector-response layers.

### W7 — Direct signature and consumer adapters

Implement a direct table provider and a package-neutral unresolved-source
adapter. This proves that geometry is optional and enables early consumer
integration independently of the full physics path.

### W8 — Thermochemistry and particles

Add frozen/equilibrium mixture contracts, CEA boundary-state import,
thermally-perfect properties, finite-rate afterburning, particle populations,
particle thermal lag, and particle optical effects.

### W9 — Imported and accelerated providers

Add imported CFD/RANS/LES fields, then transient GPU/general-3D execution after
execution-profile conformance is proven.

### W10 — Verification, validation, calibration, uncertainty, and release

Maintain analytic verification, property tests, convergence tests, provider
conformance, external validation, calibration/validation separation,
uncertainty propagation, performance baselines, documentation, wheel smoke,
and release evidence.

## 9. Master dependency graph

The critical physics and product path is:

```text
M0 architecture and baseline
  -> M1 provider contract foundation
      -> M2 corrected foundation and exit-state boundary
          -> M3 analytical provider wrapper
              -> M4 validated first cell
                  -> M5 finite shock train
                      -> M6 conservative handoff
                          -> M7 straight mixing provider
                              -> M8 gray ray transfer
                                  -> M9 far-field signature adapter
                                      -> M11 molecular spectra
                                          -> M13 thermochemistry/particles
```

Parallel lanes are allowed only where semantics are already stable:

```text
M1 -> M10 SignatureTableProvider -> M9-compatible consumer source port
M1 -> imported-field contract design
M6/M7 -> M12 curved-plume design and provider
M8 -> atmosphere/sensor interface design
M1 + execution conformance -> M15 GPU transient provider design
W10 validation/data work runs beside every milestone
```

No parallel lane may redefine a capability already used by another lane.

## 10. Milestone M0 — Architecture and repository baseline

### Objective

Freeze the execution boundary before code changes: two consumer profiles,
capability lattice, provider lifecycle, physical segmentation, neutral handoff,
units, error semantics, compatibility policy, and model-level terminology.

### Required work

- Confirm the reviewed branch and source SHAs.
- Approve capability IDs and major versions.
- Approve the plume-local frame and source-to-observer direction convention.
- Approve geometry visibility states: `INTERNAL_ONLY`,
  `EXPOSED_APPROXIMATE`, and `EXPOSED_VALIDATED`.
- Resolve architecture decisions that block Phase 0, especially public
  configuration/result representation and dependency policy.
- Record accepted decisions in the ADR document and machine-readable plan.

### Deliverables

```text
approved ADR set
provider capability registry v1
updated handoff manifest and work plan
source-baseline record
open-decision list with owners and decision gates
```

### Exit gate

- No unresolved decision blocks provider contracts or foundation corrections.
- Consumer semantics are independent of plume morphology and fidelity.
- Existing public APIs have an additive migration strategy.

### Explicit non-goals

No new plume physics and no consumer-specific dependency.

## 11. Milestone M1 — Provider contract foundation (`PR I0`)

### Objective

Introduce the provider/session/snapshot seam without changing existing plume
physics or breaking the legacy solver API.

### Dependencies

`M0` complete.

### Work

Create:

```text
src/exhaust_plume/contracts/
  capability.py
  descriptor.py
  errors.py
  execution.py
  provenance.py
  snapshot.py
  spatial.py
  radiometry.py

src/exhaust_plume/providers/
  __init__.py
```

Implement:

- stable `CapabilityId` and major-version lookup;
- provider/session/snapshot protocols;
- immutable descriptors;
- fidelity, morphology, and execution metadata as separate structures;
- applicability query structures;
- structured termination and provenance;
- typed unsupported/version/domain errors;
- fake-provider fixtures and universal conformance tests.

### Deliverables

```text
core provider contracts v1
capability registry v1
fake direct-signature provider for tests
fake spatial provider for tests
provider conformance test harness
contract API documentation
```

### Acceptance

- Existing `calculatePlumeZones` behavior remains unchanged.
- A fake provider can create a session, produce a snapshot, and serve a typed
  capability.
- Unsupported capabilities and version mismatches produce the specified errors.
- Morphology, fidelity, and execution behavior are not collapsed into one
  ranking or inheritance branch.
- Snapshot lifetime and session closure are tested.
- `pytest`, `ruff`, `pyright`, build, and installed-wheel smoke pass.

### No-go conditions

- Provider contracts import the existing plume solver.
- A capability fabricates unavailable geometry or radiation.
- Provider inputs are forced into one universal nozzle-centric schema.

## 12. Milestone M2 — Corrected foundation and exit-state boundary (`FND-A` through `FND-F`, `PR I1`)

### Objective

Correct the thermodynamic, nozzle, shock, geometry, regime, result, and quality
foundation, then establish an explicit nozzle-exit-state boundary for all
physics providers.

### Dependencies

`M1` may be merged first or developed in a nonconflicting parallel branch. The
foundation gate must pass before `M3` uses the contracts.

### Work packets

#### FND-A — Explicit gas and nozzle contracts

- Add frozen gas/nozzle input models with explicit molecular weight or specific
  gas constant.
- Make units explicit in field names.
- Establish immutable configuration/result conventions.
- Remove hidden assumptions from new core paths while preserving a documented
  legacy wrapper.

#### FND-B — Correct nozzle equations and energy naming

Correct the choked throat relation:

\[
A^*=
\frac{\dot m}{p_0}
\sqrt{\frac{RT_0}{\gamma}}
\left(\frac{\gamma+1}{2}\right)^{\frac{\gamma+1}{2(\gamma-1)}}.
\]

- Verify area–Mach and mass-flow inversion.
- Replace misleading `specific_total_energy_Jpkg` semantics with explicit
  thermodynamic properties such as total enthalpy.
- Use the supplied gas model in density, sound speed, velocity, and mass flux.

#### FND-C — Oblique-shock branches and validity

- Correct the weak zero-turn limit to the Mach angle.
- Keep the strong zero-turn limit at \(90^\circ\).
- Implement maximum attached-turn detection.
- Return structured `DETACHED_SHOCK_REQUIRED` or equivalent validity status.
- Ensure total pressure decreases and total temperature is conserved across an
  adiabatic calorically-perfect shock.

#### FND-D — Geometry primitives and precursor correction

- Replace point-only pseudoinverse intersections with conditioned line/ray
  results containing parameters, residual, and status.
- Require forward ray parameters for physical intersections.
- Correct the overexpanded precursor centerline distance:

\[
\Delta x=\frac{R}{\tan\beta}.
\]

- Eliminate public placeholder `NaN` polygons by separating transitions,
  characteristic segments, shock segments, and closed zones.

#### FND-E — Regime, result separation, and compatibility

Use a pressure residual:

\[
r_p=\frac{p_e-p_a}{p_a}
\]

with explicit underexpanded, overexpanded, and matched ranges.

- Matched flow returns zero shock cells and `NO_PRESSURE_MISMATCH`.
- Rename repeated plume passes to cells or construction passes.
- Add new result/status structures and a legacy adapter.
- Construct regime-controlled tests from target \(p_e/p_a\), not misleading
  total-pressure labels.

#### FND-F — Quality and gate

- Python 3.12 target.
- Fully typed public and critical numerical paths.
- `pytest`, `ruff`, `pyright`, build, and installed-wheel smoke.
- Updated equations, units, migration, and limitation documentation.

### New boundary

```text
legacy calculatePlumeZones(total conditions, ...)
  -> corrected NozzleExitState
      -> calculatePlumeZonesFromExitState(...)
```

The exit-state route becomes the provider entry point. There is one core solve,
not duplicated legacy and provider implementations.

### Deliverables

```text
GasProperties / FrozenGasModel contracts
NozzleExitState contract
corrected nozzle and shock utilities
robust geometry primitives
regime classifier
neutral transition/closed-zone results
legacy compatibility wrapper
Phase 0 evidence report
```

### Acceptance

- Standard mass-flow fixtures pass.
- Molecular weight changes density, sound speed, velocity, and mass flux
  consistently.
- Isentropic round trips close within tolerance.
- Normal/oblique shock conservation residuals pass.
- Weak-branch zero-turn behavior is correct.
- Detached/unattainable shocks are explicit.
- Matched expansion yields no shock-cell construction.
- Every accepted physical intersection lies on the originating forward rays.
- No public closed zone contains nonfinite placeholder geometry.
- Legacy behavior is either preserved or intentionally corrected with a
  documented migration test.

### Explicit non-goals

No new MOC first-cell solver, no shock-train calibration, no radiation, no
chemistry, and no curved plume.

## 13. Milestone M3 — `ShockCellAnalyticalProvider` wrapper (`PR I2`)

### Objective

Expose the corrected analytical solver through neutral provider capabilities
without making legacy `ZoneResult` the permanent interchange format.

### Dependencies

`M1` and `M2` complete.

### Initial capabilities

```text
spatial-support v1
axisymmetric-zone-field v1
projected-area v1
```

### Work

- Add provider-specific definition, configuration, and operating-state models.
- Map corrected solver inputs to a session and snapshot.
- Convert internal transitions/zones to neutral field products.
- Expose structured applicability, termination, approximation, and provenance.
- Declare geometry `EXPOSED_APPROXIMATE` until Phase 1 validation passes.
- Add provider/direct-solver numerical-equivalence tests.

### Deliverables

```text
ShockCellAnalyticalProvider
provider-specific schemas
neutral zone-field capability
legacy adapter sharing the same core implementation
provider conformance tests
```

### Acceptance

- Direct solver and provider snapshot agree for common fixtures.
- Invalid geometry is rejected rather than exported.
- No spectral capability is advertised.
- A signature consumer cannot accidentally depend on shock-cell geometry.
- Provider descriptor states planar analytical origin and validation level.

## 14. Milestone M4 — Validated first shock cell (`MOC-A` through `MOC-F`)

### Objective

Replace heuristic first-cell construction with a verified planar
method-of-characteristics/free-boundary solution for documented mild regimes.

### Dependencies

`M3` complete and Phase 0 gate closed.

### Work packets

#### MOC-A — Characteristic primitives and Prandtl–Meyer inverse

- Harden bracketed inversion of \(\nu(M)\).
- Add characteristic state/segment contracts.
- Verify monotonicity and limiting behavior.

#### MOC-B — Interior and centerline point solvers

For planar isentropic irrotational flow:

\[
K^+=\theta-\nu(M),
\qquad
K^-=\theta+\nu(M),
\]

constant on the appropriate characteristic families, with slopes

\[
\frac{dy}{dx}=\tan(\theta\pm\mu).
\]

At the centerline:

\[
\theta=0.
\]

Implement compatibility and conditioned downstream intersections.

#### MOC-C — Ambient-pressure free boundary

Enforce:

\[
p_b=p_a,
\qquad
\frac{dy_b}{dx}=\tan\theta_b.
\]

Replace the fitted parabola as the authoritative boundary. Preserve the old fit
only as a diagnostic comparison if useful.

#### MOC-D — Mild underexpanded first-cell assembly

- Construct lip expansion, interior characteristics, centerline reflection,
  free-boundary closure, and compression structure.
- Verify closed-zone topology and finite state.

#### MOC-E — Mild attached overexpanded first-cell assembly

- Support only the documented attached external-shock regime.
- Reject cases requiring nozzle separation or detached/Mach-disk topology.

#### MOC-F — Correlation, convergence, and validation gate

Calculate the equivalent fully expanded jet and compare the first cell with the
classical circular-jet scale:

\[
L_{s,0}\approx1.306D_j\sqrt{M_j^2-1}.
\]

Perform fan-resolution, tolerance, and geometry-convergence studies. Compare
against at least one independent experimental or CFD reference family.

### Deliverables

```text
planar characteristic solver
centerline solver
ambient-pressure free-boundary solver
validated mild underexpanded first cell
validated mild attached overexpanded first cell
closed-zone topology validator
convergence and validation report
updated provider fidelity metadata
```

### Acceptance

- Characteristic compatibility residuals satisfy tolerance.
- Centerline flow angle closes to zero.
- Free-boundary pressure satisfies ambient tolerance.
- Every segment intersection is forward and conditioned.
- Polygon/zone topology is closed, finite, and consistently oriented.
- Results converge under characteristic refinement.
- First-cell scale is physically plausible relative to correlation and
  reference data; differences are explained, not tuned away silently.
- Out-of-scope strong regimes return structured validity status.
- `ShockCellAnalyticalProvider` capability semantics do not change when the
  internal first-cell implementation improves.

## 15. Milestone M5 — Finite coherent shock train (`TRN-001` through `TRN-009`)

### Objective

Predict a finite sequence of coherent shock cells with physical termination and
calibrated uncertainty instead of accepting a supposedly physical cell count.

### Dependencies

`M4` complete.

### Work

- Add a versioned shock-train calibration contract.
- Implement inward shear-layer growth and coherent-core diameter:

\[
\delta_i(x)=\delta_{i,0}+S_i x,
\qquad
D_c(x)=\max[D_j-2\delta_i(x),0].
\]

- Implement pressure-oscillation decay:

\[
\frac{dA_p}{dx}=-\frac{C_d}{D_c(x)}A_p.
\]

- Implement local cell-spacing continuation:

\[
L_s(x)=C_\lambda D_c(x)\sqrt{M_c(x)^2-1}.
\]

- Propagate total-pressure loss and reduced-order downstream cell geometry.
- Add physical criteria:

```text
pressure oscillation decayed
mixing layer reached axis
core became subsonic
mean pressure and oscillation near ambient
```

- Add safety criteria:

```text
maximum cells
maximum axial domain
numerical failure
unsupported topology
```

- Report whether termination is physical or imposed.
- Calibrate and validate on separate datasets.
- Propagate parameter sensitivity and uncertainty to cell count and endpoint.

### Deliverables

```text
ShockTrainCalibration
ShockCellMetrics
ShockTrainResult
TerminationPolicy
TerminationReport
calibration artifact and independent validation report
uncertainty summary
```

### Acceptance

- Cell count tends to zero as pressure mismatch tends to zero.
- Greater mixing or decay reduces coherent length in the expected direction.
- Physical termination and truncation are never conflated.
- Calibration and validation datasets are disjoint and provenance-recorded.
- Predicted first-cell properties remain governed by Phase 1, not overridden by
  downstream calibration.
- Shock-train result includes final residuals, last core Mach/diameter, last
  oscillation amplitude, and applicability.

## 16. Milestone M6 — Conservative provider handoff (`PR I3`)

### Objective

Create the neutral seam from a near-field provider to any downstream plume
continuation.

### Dependencies

`M5` complete for the production handoff; contract prototyping may begin after
`M3`.

### Work

- Implement `PlumeFluxSection` and species/particle extensions.
- Integrate conserved fluxes over analytical zones.
- Record local frame, section geometry, covariance/uncertainty, and provenance.
- Implement closure checks comparing upstream integrated fluxes with the
  serialized handoff and downstream reconstructed initial state.
- Define handoff selection by physical endpoint or requested axial section.

### Deliverables

```text
PlumeFluxSection v1
ShockCellToFluxSection adapter
conservation residual report
serialization fixtures
cross-provider composition tests
```

### Acceptance

- Mass, axial/vector momentum, total enthalpy, and species fluxes close within
  documented tolerance.
- The handoff does not expose legacy analytical-zone types.
- A fake downstream provider can initialize solely from the neutral section.
- Uncertainty and calibration provenance survive the handoff.

## 17. Milestone M7 — Straight integral mixing provider (`MIX-001` through `MIX-006`)

### Objective

Continue the plume beyond coherent shock cells using an entraining integral
model and reconstruct a neutral spatial field.

### Dependencies

`M6` complete.

### Governing structure

Mass entrainment closure:

\[
\frac{d\dot m}{dx}
=2\pi R\rho_a E|u-u_a|.
\]

Momentum, total enthalpy, and species balances:

\[
\frac{d}{dx}\left[\dot m u+(p-p_a)A\right]=0,
\]

\[
\frac{d}{dx}(\dot m h_0)
=h_{0a}\frac{d\dot m}{dx}
+\dot Q'_{\mathrm{chem}}-\dot Q'_{\mathrm{rad}},
\]

\[
\frac{d}{dx}(\dot mY_s)
=Y_{s,a}\frac{d\dot m}{dx}+\dot\omega_sA.
\]

The first implementation is frozen and nonreacting:

\[
\dot\omega_s=0,
\qquad
\dot Q'_{\mathrm{chem}}=0.
\]

### Work

- Add conserved integral-state contracts.
- Implement top-hat ODE integration and thermodynamic state recovery.
- Add ambient-equilibrium/domain events.
- Reconstruct a top-hat axisymmetric field.
- Add a flux-preserving Gaussian profile option.
- Expose `spatial-support`, `centerline-tube-field`, and `local-flow-state`.
- Implement as `IntegralStraightPlumeProvider` or a composable continuation
  session.

### Deliverables

```text
IntegralStraightPlumeProvider
integral state ODE
state recovery
termination events
axisymmetric top-hat and Gaussian field reconstructions
cross-provider handoff tests
```

### Acceptance

- Integrated mass increase equals ambient entrainment.
- Momentum and total-enthalpy residuals satisfy tolerance.
- Frozen species and elemental totals are conserved.
- Reconstructed profiles preserve the intended integral fluxes.
- Field approaches ambient conditions in a physically consistent direction.
- Termination is structured and distinct from the shock-train endpoint.

## 18. Milestone M8 — Gray radiative transfer (`RAD-001` through `RAD-006`, `PR I4`)

### Objective

Create a verified resolved ray-transfer path over neutral plume fields before
adding molecular spectroscopy.

### Dependencies

`M7` for the complete downstream field. Infrastructure may be unit-developed
against analytic synthetic fields earlier.

### Work

- Implement spectral coordinate/unit contracts and Planck radiance.
- Implement axisymmetric ray geometry in the plume-local frame.
- Intersect and order ray segments through zone and tube fields.
- Implement exact LTE, no-scattering segment transfer:

\[
I_{\lambda,i+1}
=I_{\lambda,i}e^{-\Delta\tau_{\lambda,i}}
+B_\lambda(T_i)\left(1-e^{-\Delta\tau_{\lambda,i}}\right).
\]

- Use numerically stable `expm1` formulations for small optical depth.
- Produce spectral radiance images and area integration.
- Sweep observer direction.
- Add a separate IR-domain termination criterion based on incremental band
  contribution.
- Expose `spectral-ray-transfer v1` through adapters.

### Deliverables

```text
Planck and spectral-unit utilities
axisymmetric ray marcher
GrayOpticalPropertyModel
gray spectral-ray-transfer adapter
radiance image result
angular sweep result
IR-domain termination report
analytic verification report
```

### Acceptance

- Homogeneous slab matches the analytic solution.
- Zero opacity returns background radiance.
- Optically thin radiance is linear in concentration/path length.
- Optically thick radiance approaches Planck radiance.
- Hot/cold layer order produces the correct self-absorption difference.
- Cylinder/tube chord lengths match analytic geometry.
- Complete-image optically thin integrated emission is nearly orientation
  invariant where expected.
- Ray, pixel, and axial-domain refinement converge.

## 19. Milestone M9 — Far-field signature and consumer integration (`PR I5`, `PR I7`)

### Objective

Derive the canonical signature product from resolved rays and provide a
package-neutral adapter for unresolved consumers.

### Dependencies

`M8` for the physics-backed path. The consumer port may be specified and tested
with a fake provider after `M1`.

### Work

Integrate radiance over the orthographic image plane:

\[
J_\lambda(\hat{\mathbf s})
=\int_{A_\perp}I_\lambda(u,v;\hat{\mathbf s})\,du\,dv.
\]

- Implement `FarFieldFromRays` adapter.
- Implement direction and wavelength batching.
- Add unresolved-distance applicability checks using source support and
  requested observer range where the consumer layer needs them.
- Implement a package-neutral `DirectionalSpectralSource` adapter.
- Keep atmosphere and sensor response outside the intrinsic source result.
- Add rich-to-simple equivalence tests.

### Deliverables

```text
FarFieldFromRays adapter
directional-spectral-intensity capability
consumer-facing source port adapter
batch evaluation support
resolved-to-unresolved equivalence report
```

### Acceptance

- Direction vectors are validated and normalized according to contract.
- Spectral units and wavelength-grid identity are preserved.
- Orthographic integration converges under image refinement.
- The adapter result matches direct integration fixtures.
- The consumer adapter depends only on the small signature port, not provider
  internals or geometry.

## 20. Milestone M10 — Direct `SignatureTableProvider` (`PR I6`)

### Objective

Prove the signature-only use case independently of the spatial physics path and
support fast lookup/surrogate products.

### Dependencies

`M1` complete. This milestone can proceed in parallel with `M2` through `M8`.

### Work

- Define table asset schema for time/operating state, direction, wavelength,
  values, units, frame, provenance, calibration, uncertainty, and validity.
- Implement explicit interpolation and no-silent-extrapolation behavior.
- Support direction batching and random-access snapshots.
- Expose only `directional-spectral-intensity` unless an asset genuinely
  includes another standard capability.
- Add asset digest and reproducibility metadata.

### Deliverables

```text
SignatureTableProvider
versioned table asset schema
table ingestion and validation
interpolation/extrapolation policy
signature-provider conformance tests
```

### Acceptance

- Table nodes reproduce exactly.
- Interpolation behavior is deterministic and documented.
- Out-of-domain time, angle, wavelength, or operating state is explicit.
- The provider exposes no fake geometry.
- A signature consumer can swap between the table provider and
  `FarFieldFromRays` without changing query semantics.

## 21. Milestone M11 — Molecular spectral radiation (`SPC-001` through `SPC-007`)

### Objective

Replace gray opacity with validated high-temperature molecular absorption and
emission while preserving the same ray-transfer and signature capabilities.

### Dependencies

`M8` and `M9` complete. Frozen composition must be available from provider
fields or prescribed inputs.

### Work

- Build an offline reproducible HITEMP/HITRAN/HAPI cross-section generator.
- Store per-species cross sections on a versioned \((T,p,\tilde\nu)\) grid.
- Record database/version/source digests and line-shape assumptions.
- Implement bounded interpolation with no silent extrapolation.
- Form mixture absorption:

\[
\alpha_{\tilde\nu}=\sum_s n_s\sigma_s(\tilde\nu,T,p).
\]

- Integrate molecular optical properties into images and directional
  signatures.
- Add atmosphere propagation interface and detector-response model as separate
  downstream layers.
- Validate against standalone spectral fixtures and heated-plume image/spectral
  data.

### Deliverables

```text
cross-section generator
versioned spectral assets
molecular optical-property model
molecular images and signatures
atmosphere interface
detector response interface
spectral validation report
```

### Acceptance

- Cross sections reproduce generator reference cases.
- Number-density, cross-section, optical-depth, and radiance units are closed.
- Interpolation and spectral-grid refinement converge.
- Gray limit or prescribed-opacity compatibility is retained.
- Atmosphere and detector layers cannot be confused with intrinsic plume
  emission.
- External validation residuals and known discrepancies are documented.

## 22. Milestone M12 — Curved/washed integral provider

### Objective

Add a curved downstream plume that serves the same spatial and radiometric
capabilities as the straight provider.

### Dependencies

`M6` and `M7` complete. The dedicated curved-plume physics design must be
approved before implementation.

### Design gate

Approve equations and contracts for:

- ambient flow-field sampling;
- centerline arc-length parameterization;
- vector momentum evolution;
- crossflow/rotor-wash entrainment closure;
- buoyancy or body-force terms where applicable;
- parallel-transport local frame;
- radius and cross-sectional profile evolution;
- source/near-field handoff and validity regime;
- self-intersection and excessive-curvature handling.

### Geometric representation

\[
\mathbf c(s),
\qquad
\mathbf t(s)=\frac{d\mathbf c}{ds},
\qquad
R(s),
\]

with a transported normal/binormal frame and local cross-sectional fields.
A representative vector balance is

\[
\frac{d}{ds}(\dot m\mathbf u)
=\mathbf f_{\mathrm{entrainment}}
+\mathbf f_{\mathrm{crossflow}}
+\mathbf f_{\mathrm{buoyancy}}
+\cdots.
\]

### Work

- Implement ambient-flow service contract.
- Generalize integral state from scalar axial momentum to vector momentum.
- Implement centerline integration and parallel-transport frame.
- Reconstruct `centerline-tube-field` and `local-flow-state` in 3-D.
- Reuse optical-medium and ray-transfer adapters where applicable.
- Add straight-limit equivalence, rigid-transform invariance, and curvature
  conformance tests.

### Deliverables

```text
approved curved-plume physics specification
CurvedIntegralPlumeProvider
ambient-flow service contract
centerline and transported-frame solver
curved tube-field capability
curved ray-intersection support
validation/applicability report
```

### Acceptance

- Zero crossflow/forcing converges to the straight provider within tolerance.
- Global rigid transforms do not change intrinsic plume results.
- Centerline arc length and frame remain continuous without Frenet-frame flips.
- Conserved fluxes close along the curved path according to modeled forces and
  entrainment.
- Spatial and signature consumers require no API changes.
- Applicability under rotor wash/crossflow is explicit and calibration-backed.

## 23. Milestone M13 — Thermochemistry and particles (`CHEM-001` through `CHEM-008`)

### Objective

Increase thermodynamic and radiative fidelity without changing consumer
capability semantics.

### Dependencies

`M7` and `M11` complete. Frozen molecular radiation is validated first.

### Work

- Add species/mixture contracts and elemental inventories.
- Add CEA boundary-state adapter with frozen/equilibrium provenance.
- Add thermally-perfect \(h(T,\mathbf Y)\), \(c_p(T,\mathbf Y)\),
  \(R(\mathbf Y)\), and \(\gamma(T,\mathbf Y)\).
- Add frozen variable-property expansion/shock reference paths.
- Add equilibrium reference calculations.
- Add finite-rate integral afterburning:

\[
\frac{d}{dx}(\dot mY_s)
=Y_{s,a}\frac{d\dot m}{dx}+\dot\omega_sA,
\]

with chemical enthalpy coupling.
- Add particle population, particle temperature lag, absorption/emission, and
  later scattering.

### Deliverables

```text
mixture/species contracts
CEA boundary adapter
thermally-perfect property model
finite-rate chemistry adapter
particle population and thermal model
particle optical-property model
chemistry/particle validation report
```

### Acceptance

- Species fractions sum to one and elemental abundances close.
- Frozen/equilibrium reference limits reproduce source calculations.
- Reaction enthalpy and total-energy accounting close.
- Disabling reaction rates recovers frozen behavior.
- Particle-free and zero-loading limits recover the molecular model.
- Provider capability versions remain unchanged unless semantics, not fidelity,
  break.

## 24. Milestone M14 — Imported field provider (`PR I8`)

### Objective

Allow CFD/RANS/LES or other field assets to participate in the same provider
and radiation ecosystem.

### Dependencies

`M1` and stable spatial contracts. Molecular/optical adapters may be attached
when field content permits.

### Work

- Define imported-field asset schema, coordinates, units, time identity,
  interpolation, topology, species, particles, and provenance.
- Implement local-flow and spatial-support capabilities.
- Add optical-medium/ray adapters when sufficient state is present.
- Add conservative section extraction for provider chaining.
- Add transformation and interpolation conformance tests.

### Acceptance

- No hidden unit or coordinate conversion.
- Asset digest and source solver metadata are retained.
- Interpolation is deterministic and domain-bounded.
- Equivalent neutral fields produce equivalent downstream radiometric products
  within tolerance.

## 25. Milestone M15 — GPU transient/general-3D provider (`PR I9`)

### Objective

Add high-throughput or transient providers only after execution-profile
semantics are proven.

### Dependencies

`M1`, conformance harness, and at least one stable semantic implementation of
each capability being accelerated.

### Work

- Declare monotonic/random time access, snapshot lifetime, concurrency,
  batching, checkpointability, preferred device, and host/device result rules.
- Implement direction/ray batching.
- Enforce snapshot invalidation behavior.
- Compare semantic host results against CPU/reference capability fixtures.
- Add resource failure and checkpoint recovery tests.

### Acceptance

- Execution differences do not alter physical quantity semantics.
- Snapshot lifetime violations are detected.
- Batched and scalar evaluations agree.
- Determinism/reproducibility status is explicit.
- GPU-specific assets do not leak into consumer contracts.

## 26. Cross-cutting validation program

Every milestone includes five evidence classes.

### 26.1 Analytic verification

Examples:

- isentropic round trips;
- choked mass flow;
- area–Mach inversion;
- normal/oblique shock conservation;
- Mach-angle and zero-turn limits;
- characteristic compatibility;
- homogeneous radiative slab;
- analytic cylinder/tube chords;
- optically thin and thick limits.

### 26.2 Property and metamorphic tests

Examples:

- SI scaling and unit identity;
- rigid-transform invariance;
- direction normalization;
- straight-limit equivalence for curved providers;
- richer-product to simpler-product equivalence;
- scalar versus batched evaluation;
- zero-loading/zero-reaction limit recovery;
- monotonic response to calibrated mixing/decay coefficients where physically
  expected.

### 26.3 Numerical convergence

Each discretized solver records the sequence of resolutions/tolerances and the
observed convergence of load-bearing quantities:

```text
MOC: cell length, boundary residual, zone extrema
ODE: endpoint, conserved fluxes, state profiles
ray tracer: pixel/ray/segment refinement
spectral model: wavelength and T-p table refinement
curved plume: arc-length and frame integration refinement
```

A single-resolution match is not sufficient evidence.

### 26.4 Provider conformance

Universal tests cover:

- lifecycle and closure;
- capability lookup and versioning;
- applicability and no-silent-extrapolation;
- provenance and termination retention;
- units and frames;
- batching semantics;
- cross-provider swap tests for signature and spatial consumers.

### 26.5 External validation

Calibration and validation datasets are separate. Every fixture records:

```text
source and citation
raw-data digest
transformation script/version
operating-condition identity
measurement uncertainty
calibration/validation role
model applicability
```

Validation reports distinguish governing-equation defects, closure error,
measurement uncertainty, and model discrepancy.

## 27. Scientific data, calibration, and uncertainty

### 27.1 Correlation and closure governance

Every non-governing relation is registered with:

```text
equation/closure ID
parameter names and units
bounds and transformations
source provenance
calibration dataset
validation dataset
applicability region
parameter covariance or uncertainty
model-discrepancy statement
```

No “default” coefficient may appear without a calibration identity.

### 27.2 Calibration objective

Use uncertainty-scaled residuals:

\[
r_i(\boldsymbol\theta)
=\frac{m_i(\boldsymbol\theta)-y_i}{\sigma_i},
\]

with robust objectives where justified. Record optimizer, bounds, priors if
used, Jacobian/SVD identifiability, covariance approximation, and held-out
validation performance.

### 27.3 Uncertainty propagation

At minimum propagate uncertain gas/nozzle inputs and calibrated closure
parameters to:

```text
first-cell length
cell count
shock-train endpoint
mixing endpoint
selected field values
spectral/angular intensity
band-integrated intensity
```

Provider results expose uncertainty only when supported by the registered
`uncertainty` capability; otherwise they state that uncertainty is unavailable.

## 28. Compatibility and migration

### 28.1 Additive migration

The initial provider framework and corrected solver are additive. Existing
public functions remain available as wrappers while new contracts stabilize.

### 28.2 Single implementation path

Legacy and provider APIs call the same corrected core. Duplicated physics paths
are prohibited.

### 28.3 Deprecation sequence

1. Introduce new exit-state and provider APIs.
2. Add compatibility tests and migration documentation.
3. Emit deprecation warnings only after an equivalent replacement is stable.
4. Retain serialized schema versioning and conversion tools.
5. Remove legacy APIs only in a planned breaking release.

### 28.4 Schema policy

- Stable enums serialize as strings.
- Arrays use documented artifact storage rather than enormous inline JSON.
- Every result contains schema version, provider identity, calibration identity,
  validity, termination, and provenance.
- Capability major versions change only when consumer-visible semantics break.

## 29. Coding-agent execution protocol

Each coding-agent assignment is one reviewable packet or PR.

### Before implementation

The agent must:

1. Read this master plan and the packet-specific documents.
2. Re-audit target source files when SHAs differ from the handoff baseline.
3. State the packet, files, equations, compatibility behavior, and non-goals.
4. Add or update failing tests before or with implementation.
5. Avoid unrelated formatting or refactoring.

### During implementation

- Preserve TODOs unless the task explicitly resolves them.
- Use Python 3.12+, full type annotations, NumPy typing, Pydantic v2 where
  configured, SciPy bracketed solvers where approved, pytest, ruff, and pyright.
- End scopes according to the repository `####` convention.
- Raise typed programmer/configuration errors; return structured physical domain
  results where specified.
- Record residuals and convergence diagnostics rather than logging and
  continuing with a questionable state.
- Do not add network-dependent tests.

### Completion report

Every PR report includes:

```text
packet and issue IDs
files changed
equations implemented or corrected
public API/schema changes
compatibility behavior
tests and commands run
numerical fixtures and residuals
convergence evidence where applicable
known limitations and out-of-scope regimes
updated documentation/registry entries
```

## 30. Release gates

### Gate R0 — Contract preview

Requires `M0` and `M1`:

- provider lifecycle and conformance stable;
- no physics behavior change;
- fake signature and spatial providers pass.

### Gate R1 — Corrected analytical foundation

Requires `M2` and `M3`:

- foundation equations/conservation pass;
- explicit gas/exit state;
- provider/direct equivalence;
- approximate geometry clearly labeled.

### Gate R2 — Validated analytical near field

Requires `M4` and `M5`:

- first-cell convergence/validation;
- finite shock train;
- physical termination and calibrated uncertainty.

### Gate R3 — Complete reduced-order spatial plume

Requires `M6` and `M7`:

- conservative handoff;
- straight entrainment/mixing field;
- mass, momentum, enthalpy, and species closure.

### Gate R4 — Gray resolved and unresolved radiometry

Requires `M8` and `M9`:

- analytic ray-transfer verification;
- directional spectral source from spatial fields;
- consumer swap tests.

### Gate R5 — Direct signature ecosystem

Requires `M10`:

- table provider;
- signature-only consumer proven without geometry.

### Gate R6 — Molecular signature beta

Requires `M11`:

- reproducible spectral assets;
- molecular images/signatures;
- independent spectral/plume validation;
- atmosphere/sensor layers separated.

### Gate R7 — Curved plume beta

Requires `M12`:

- approved curved physics;
- straight-limit and rigid-transform conformance;
- curved spatial and radiometric products through unchanged capabilities.

### Gate R8 — Advanced thermochemistry/particles research release

Requires `M13`:

- elemental and energy closure;
- frozen/equilibrium/finite-rate validation;
- molecular and particle limit recovery.

### Gate R9 — High-fidelity provider ecosystem

Requires `M14` and optionally `M15`:

- imported/general field conformance;
- execution-profile conformance for accelerated providers.

## 31. Critical risks and controls

| Risk | Consequence | Control and decision gate |
| --- | --- | --- |
| Provider abstraction overfits shock cells | Curved/CFD providers become awkward | Keep provider-specific inputs and capability-based outputs; fake-provider conformance at M1 |
| Planar geometry presented as axisymmetric physics | Misleading spatial validity | Explicit geometry/flow metadata; Phase 1 convergence and validation before `EXPOSED_VALIDATED` |
| Strong underexpansion or Mach disk forced through attached shocks | Invalid topology | Attached-shock/Mach-disk classifier and structured out-of-scope status |
| Overexpanded nozzle separation ignored | Invalid exit state | Require validated exit state or return separation-not-modeled validity |
| Cell count tuned without mixing physics | Nonphysical endpoint | Physical termination closures, separate calibration/validation, uncertainty |
| Curved provider merely bends a straight field | Broken momentum and transport | Dedicated vector integral equations and straight-limit validation |
| Radiation multiplied by projected area | Incorrect gas-plume signature | Volumetric RTE with analytic limiting tests |
| Spectral database/runtime coupling is unreproducible | Unrepeatable signatures | Offline versioned cross-section assets with digests |
| Atmosphere/sensor folded into source signature | Consumer lock-in and wrong units | Separate intrinsic source, propagation, and detector layers |
| Legacy and provider paths diverge | Contradictory results | One corrected core and regression equivalence tests |
| GPU execution leaks into semantics | Consumer-specific behavior | Explicit execution profile and semantic reference tests |
| Too many simultaneous coding-agent changes | Unreviewable failures | One packet/PR at a time and phase gates |

## 32. Parallel execution lanes

After `M1`, the work can be organized into four controlled lanes.

### Lane A — Critical physical model

```text
M2 -> M3 -> M4 -> M5 -> M6 -> M7 -> M8 -> M9 -> M11 -> M13
```

### Lane B — Direct signature product

```text
M1 -> M10 -> consumer integration tests
```

This lane proves the minimal signature profile early.

### Lane C — Curved and imported providers

```text
M6/M7 -> M12
M1 + spatial contracts -> M14
```

Shared field and handoff contracts must be stable before implementation.

### Lane D — Validation, data, and governance

Runs throughout:

```text
reference data ingestion
analytic fixture maintenance
calibration/validation split
uncertainty work
provider conformance
performance baselines
release evidence
```

Lane D is never deferred to the end.

## 33. Immediate execution queue

The next coding-agent queue is:

```text
1. M0 architecture review and open-decision closure
2. M1 / PR I0 provider contract foundation
3. M2 / FND-A explicit gas and nozzle contracts
4. M2 / FND-B corrected nozzle equations and energy naming
5. M2 / FND-C shock branches and validity
6. M2 / FND-D geometry primitives and precursor correction
7. M2 / FND-E regime/results/compatibility
8. M2 / FND-F quality gate
9. M3 / PR I2 ShockCellAnalyticalProvider wrapper
10. M4 / MOC-A through MOC-F
```

`M10 SignatureTableProvider` may begin after `M1` in a separate branch because
it does not depend on corrected shock-cell physics.

## 34. Definition of program completion

The comprehensive program is complete when:

- signature and spatial consumers can swap providers without API changes;
- direct table, analytical straight, straight mixing, curved mixing, and
  imported-field providers pass shared conformance;
- the analytical near field is corrected, convergent, and validated within an
  explicit applicability domain;
- shock-cell and mixed-plume endpoints are physically distinguished;
- provider chaining preserves conserved fluxes and provenance;
- gray and molecular radiative transfer pass analytic and external validation;
- intrinsic source, atmospheric propagation, and detector response remain
  separate;
- thermochemistry and particles preserve elemental and energy closure where
  enabled;
- physical fidelity, morphology, radiation fidelity, validation, execution,
  and uncertainty are separately declared;
- no provider silently fabricates unsupported products or extrapolates outside
  its applicability;
- every release gate has reproducible evidence and installed-artifact tests.

## 35. Document ownership map

This master plan controls sequence and scope. Use the following documents for
implementation detail:

| Subject | Authoritative document |
| --- | --- |
| Unified provider/consumer architecture | `00_unified_plume_architecture.md` |
| Model assumptions and equations | `01_model_contract_and_architecture.md` |
| Foundation corrections | `02_foundation_corrections_plan.md` |
| First-cell MOC | `03_validated_first_cell_plan.md` |
| Shock train and termination | `04_shock_train_and_termination_plan.md` |
| Integral mixing | `05_integral_mixing_plume_plan.md` |
| Radiation | `06_spectral_ir_plan.md` |
| Chemistry and particles | `07_thermochemistry_and_particles_plan.md` |
| Verification and validation | `08_validation_and_test_matrix.md` |
| Issue definitions | `09_issue_backlog.md` |
| Agent behavior | `10_coding_agent_execution_protocol.md` |
| Source provenance | `12_reference_sources.md` |
| Settled decisions | `13_architecture_decision_records.md` |
| API and serialization | `14_api_contracts_and_serialization.md` |
| Provider interface | `15_plume_provider_interface.md` and `30_provider_contracts_v1.md` |
| Equation ownership | `16_equation_traceability_matrix.md` and `equation_registry.yaml` |
| Algorithms | `17_numerical_algorithms_and_pseudocode.md` |
| Calibration/data | `18_scientific_data_and_calibration_plan.md` |
| Uncertainty | `19_uncertainty_and_sensitivity_methods.md` |
| Phase 0/1 packets | `20_phase_0_patch_blueprint.md`, `21_phase_0_foundation_task_packets.md`, `22_phase_1_first_cell_task_packets.md` |
| Agent prompts/gates | `23_agent_prompts_and_gate_checklists.md`, `27_release_gates_and_definition_of_done.md` |
| Consumer queries and provider taxonomy | `28_consumer_profiles_and_query_contracts.md`, `29_provider_taxonomy_and_composition.md` |
| Cross-provider testing | `31_unified_conformance_and_testing.md` |
| Machine-readable master plan | `work_plan.yaml` |

<!-- END 34_comprehensive_work_plan.md -->


---

<!-- BEGIN 35_first_execution_wave.md -->

# First Execution Wave: Coding-Agent Work Plan

## 1. Purpose

This document expands the immediate queue in
`34_comprehensive_work_plan.md` into a branch- and PR-level execution plan.
It covers the work needed to reach:

```text
M0  reproducible baseline
M1  provider contract foundation
M2  corrected physics foundation and exit-state boundary
M3  ShockCellAnalyticalProvider
M10 SignatureTableProvider, in an independent parallel lane
```

No method-of-characteristics replacement, finite shock-train calibration,
integral mixing implementation, curved-plume dynamics, or production radiation
physics belongs in this execution wave.

## 2. Wave completion state

At the end of this wave:

- signature and spatial consumers are represented by stable capability
  contracts;
- fake providers prove that geometry is optional;
- generic plume physics no longer hides dry-air properties;
- nozzle mass-flow, energy/enthalpy, oblique-shock limits, regime
  classification, and precursor geometry are corrected;
- successful public closed zones contain no placeholder nonfinite geometry;
- legacy total-condition and new exit-state APIs share one corrected core;
- the corrected analytical solver is exposed through neutral spatial
  capabilities;
- a direct signature-table provider serves the signature use case without any
  geometry dependency;
- Phase 1 MOC work can begin without reopening provider or foundation
  semantics.

## 3. Dependency and merge sequence

```text
M0 baseline
   |
   +---------------------------+
   |                           |
   v                           v
M1 / I0 provider contracts   M2 / FND-A gas/nozzle contracts
   |                           |
   v                           v
I0 conformance              FND-B nozzle/enthalpy corrections
                               |
                         +-----+-----+
                         |           |
                         v           v
                      FND-C        FND-D
                      shocks       geometry
                         |           |
                         +-----+-----+
                               v
                             FND-E
                    regime/results/migration
                               |
                               v
                             FND-F
                       foundation gate
                               |
                               v
                              I1
                    exit-state core boundary
                               |
                    +----------+----------+
                    |                     |
                    v                     v
                 M3 / I2              M10 / I6
        analytical spatial provider   signature table
```

`M10 / I6` may begin after M1 and merge independently of M2/M3 because it has
no dependency on analytical shock-cell physics.

## 4. M0 — Architecture and repository baseline

### Branch

```text
chore/plume-baseline-inventory
```

### Required work

- Record repository commit, package version, source branch, and reviewed file
  SHAs.
- Run and record:

```bash
python -m pytest
python -m ruff check .
python -m pyright
python -m build
```

- Install the built wheel in a fresh environment and run imports and CLI help
  outside the repository.
- Inventory public functions, classes, enums, CLI options, return structures,
  and documented unit conventions.
- Capture current representative numerical outputs without labeling them as
  physically correct merely because they are reproducible.
- Classify fixtures as:

```text
legacy_anchor
corrected_anchor
untrusted_visual_anchor
```

- Review the open decisions in Document 26 and confirm that none blocks M1 or
  M2.

### Deliverables

```text
docs/baseline/current_api_inventory.md
docs/baseline/current_quality_results.md
tests/fixtures/legacy_baseline/
```

### Gate

No behavior changes. A clean checkout can reproduce the baseline evidence.

## 5. M1 / I0 — Provider contract foundation

### Branch

```text
feature/provider-contract-foundation
```

### Required reading

```text
00_unified_plume_architecture.md
28_consumer_profiles_and_query_contracts.md
29_provider_taxonomy_and_composition.md
30_provider_contracts_v1.md
31_unified_conformance_and_testing.md
33_coding_agent_interface_kickoff_prompt.md
```

### Expected package structure

```text
src/exhaust_plume/contracts/
  capability.py
  descriptor.py
  errors.py
  execution.py
  provenance.py
  radiometry.py
  snapshot.py
  spatial.py

src/exhaust_plume/providers/
  __init__.py
```

### Required contracts

- `PlumeProvider`.
- `PlumeSession`.
- `PlumeSnapshot`.
- `CapabilityId` and explicit major versions.
- `PlumeProviderDescriptor`.
- `ProviderFidelity`.
- `ProviderExecutionProfile`.
- `ProviderApplicability`.
- `PlumeProvenance`.
- Typed provider, lifecycle, domain, and capability errors.
- Canonical plume-local frame and source-to-observer direction semantics.

### Fake providers

1. Signature-only provider with no geometry.
2. Spatial-only provider with no radiation.
3. Ray-transfer provider that also exposes native directional intensity.
4. Provider with snapshot invalidation semantics.

### Conformance tests

- Capability registry equals actual capability objects.
- Unsupported capability and major-version mismatch fail explicitly.
- Definition/configuration/state inputs are not mutated.
- Public arrays are immutable or defensively copied.
- Deterministic providers repeat exactly.
- Signature wavelength and direction validation.
- Axisymmetric directional symmetry.
- Ray miss returns zero source radiance and unit transmittance.
- Rich-to-simple integration equivalence for the fixture provider.
- Provenance, applicability, and snapshot retention are preserved.

### Non-goals

- No adaptation of `calculatePlumeZones`.
- No new plume physics.
- No external-consumer dependency.
- No spectroscopy or curved-plume equations.

### Gate

All provider conformance tests pass and the current solver API remains
unchanged.

## 6. M2 / FND-A — Explicit gas and nozzle contracts

### Branch

```text
feature/gas-nozzle-contracts
```

### Required reading

```text
01_model_contract_and_architecture.md
02_foundation_corrections_plan.md
14_api_contracts_and_serialization.md
16_equation_traceability_matrix.md
20_phase_0_patch_blueprint.md
21_phase_0_foundation_task_packets.md
```

### Expected files

```text
src/exhaust_plume/models/gas/contracts.py
src/exhaust_plume/models/nozzle/contracts.py
src/exhaust_plume/models/nozzle/exit_state.py
```

### Required contracts

- `GasProperties` or equivalent frozen gas model.
- `NozzleExitState`.
- `AmbientState`.
- Explicit SI-unit field names.
- Internal radians.
- Molecular-weight / specific-gas-constant consistency.
- Optional normalized frozen species fractions.

### Tests

- Positive finite validation.
- Molecular weight and gas constant consistency.
- Species normalization, duplicate rejection, and immutable state.
- Serialization round trip where the contract is serializable.

### Non-goals

No changes to shock or plume geometry.

## 7. M2 / FND-B — Correct nozzle equations and energy semantics

### Branch

```text
fix/nozzle-foundation-equations
```

### Depends on

FND-A.

### Required equation

\[
A^*=
\frac{\dot m}{p_0}
\sqrt{\frac{RT_0}{\gamma}}
\left(\frac{\gamma+1}{2}\right)^{
\frac{\gamma+1}{2(\gamma-1)}
}.
\]

### Work

- Add a forward choked mass-flow helper.
- Correct throat-area inversion.
- Verify area--Mach branch inversion.
- Route explicit gas properties through generic nozzle/plume calculations.
- Add precise static and total enthalpy properties.
- Deprecate ambiguous historical energy naming.
- Verify:

\[
h_0=h+\frac{u^2}{2}=c_pT_0.
\]

### Tests

- Forward/inverse choked mass flow.
- Supersonic area--Mach inversion.
- Molecular-weight sensitivity of density, sound speed, velocity, and mass
  flux.
- Isentropic static/total round trips.
- Total-enthalpy identity.
- Explicit deprecation behavior.

## 8. M2 / FND-C — Oblique-shock branches and validity

### Branch

```text
fix/oblique-shock-validity
```

### Depends on

FND-B. May be developed in parallel with FND-D after shared contracts merge.

### Work

- Implement bounded weak and strong roots of the
  \(\theta\)-\(\beta\)-\(M\) relation.
- Enforce:

\[
\lim_{\theta\rightarrow0}\beta_{weak}
=\sin^{-1}(1/M),
\qquad
\lim_{\theta\rightarrow0}\beta_{strong}=\pi/2.
\]

- Compute maximum attached turn.
- Return `DETACHED_SHOCK_REQUIRED` or equivalent structured validity.
- Add target-pressure feasibility checks.
- Report root residual and bracket diagnostics.

### Tests

- Weak and strong zero-turn limits.
- Branch ordering and residual across a grid.
- Below/above maximum-turn behavior.
- Shock mass/momentum/energy conservation.
- Total-pressure loss and total-temperature conservation.

## 9. M2 / FND-D — Geometry primitives and precursor correction

### Branch

```text
fix/plume-geometry-primitives
```

### Depends on

FND-B. May be developed in parallel with FND-C.

### Work

- Replace point-only pseudoinverse intersection with a diagnostic result:

```text
point
parameter_1
parameter_2
condition_number
residual
status
```

- Require forward ray parameters for physical intersections.
- Reject parallel, near-parallel, backward, and high-residual cases.
- Correct the overexpanded precursor centerline distance:

\[
\Delta x=\frac{R}{\tan\beta}.
\]

- Use radians internally.
- Separate flow transitions, characteristic segments, shock segments, and
  closed zones.

### Tests

- Exact orthogonal intersection.
- Parallel and ill-conditioned rejection.
- Backward intersection rejection.
- Analytic forty-five-degree precursor case.
- Regression against the degree/cosine defect.
- Closed-zone finiteness and topology checks.

## 10. M2 / FND-E — Regime, results, terminology, and compatibility

### Branch

```text
feature/corrected-plume-results
```

### Depends on

FND-C and FND-D.

### Work

- Add explicit `UNDEREXPANDED`, `MATCHED`, and `OVEREXPANDED` regimes.
- Classify with:

\[
r_p=\frac{p_e-p_a}{p_a}
\]

  and a documented tolerance.
- Matched flow returns zero cells and `NO_PRESSURE_MISMATCH`.
- Rename repeated plume passes to cells or construction passes in new APIs.
- Retain legacy `num_plumes` only through a documented wrapper.
- Prevent invalid/open geometry from appearing as a successful `ClosedZone`.
- Add structured validity and termination reports.
- Replace misleading tests with cases built from target \(p_e/p_a\).

### Gate

The corrected result model is additive, migration behavior is explicit, and no
second legacy physics implementation exists.

## 11. M2 / FND-F — Foundation quality gate

### Branch

```text
chore/foundation-phase-gate
```

### Work

- Update equations, units, limitations, and migration documentation.
- Update equation registry and ADRs.
- Run full quality and installed-artifact checks.
- Confirm no successful public closed zone contains nonfinite coordinates.
- Record Phase 0 evidence under the classes in Document 27.

### Gate

Every Phase 0 criterion in Document 27 passes before I1 or M3 merges.

## 12. M2 / I1 — Corrected exit-state core boundary

### Branch

```text
refactor/exit-state-core-boundary
```

### Depends on

M1 contracts and FND-F gate.

### Required architecture

```text
legacy calculatePlumeZones(total conditions, ...)
  -> corrected NozzleExitState
      -> calculatePlumeZonesFromExitState(...)
          -> optional legacy result adapter
```

### Tests

- Equivalent legacy/new inputs reach the same corrected core result.
- Explicit gas properties propagate through every state.
- No duplicated shock or geometry solve exists.
- Provider definition/state can bind directly to the exit-state path.

## 13. M3 / I2 — `ShockCellAnalyticalProvider`

### Branch

```text
feature/shock-cell-analytical-provider
```

### Depends on

M1 and M2 complete.

### Initial capabilities

```text
spatial-support v1
axisymmetric-zone-field v1
projected-area v1
```

### Work

- Convert corrected solver output into neutral provider products.
- Do not expose legacy `ZoneResult` through generic capabilities.
- Preserve planar-flow provenance and geometry quality status.
- Expose applicability, validity, and termination separately.
- Advertise no spectral capability yet.

### Tests

- Provider/direct-solver numerical equivalence.
- Conservative spatial support.
- Invalid geometry is rejected rather than exported.
- Legacy construction limits are marked nonphysical.
- Capability absence fails explicitly.

## 14. M10 / I6 — `SignatureTableProvider`

### Branch

```text
feature/signature-table-provider
```

### Depends on

M1 only. This branch may proceed independently of M2 and M3.

### Work

- Define a versioned signature-table asset schema.
- Implement wavelength, direction, and optional time interpolation.
- Reject extrapolation by default.
- Include asset digest, coordinate convention, interpolation policy, and
  validity in provenance.
- Expose only `directional-spectral-intensity` unless an asset explicitly
  contains another standard capability.

### Tests

- Exact grid-point reproduction.
- Deterministic interpolation.
- Direction convention and symmetry.
- Extrapolation rejection.
- Asset-digest provenance.
- Same consumer code works against constant and table providers.

## 15. Conflict ownership

| Area | Owner packet | Other packets must not change |
|---|---|---|
| Provider lifecycle and capability semantics | I0 | physics equations |
| Gas/nozzle contracts | FND-A | provider capability semantics |
| Mass flow and enthalpy | FND-B | shock geometry |
| Oblique-shock solver | FND-C | line-intersection implementation |
| Geometry primitives | FND-D | shock thermodynamic equations |
| Regime/results/migration | FND-E | duplicate core equations |
| Quality/evidence | FND-F | unreviewed physics behavior |
| Exit-state boundary | I1 | provider-specific physics duplication |
| Analytical adapter | I2 | legacy behavior except via shared wrapper |
| Signature table | I6 | geometry assumptions |

A shared-contract change requires an ADR amendment and explicit review before
parallel branches rebase.

## 16. Wave-wide quality gate

Run:

```bash
python -m pytest
python -m ruff check .
python -m pyright
python -m build
```

Then:

- install the built wheel in a fresh environment;
- import and run CLI help outside the repository;
- execute one matched-flow solve;
- run the provider conformance suite;
- validate serialized schemas;
- compare legacy and exit-state paths;
- verify public array immutability;
- update ADR, equation, migration, manifest, and changelog records.

## 17. Stop condition

Do not begin `MOC-A` through `MOC-F` until M0, M1, M2, and M3 have passed their
gates. `SignatureTableProvider` may merge after M1 because it does not rely on
analytical plume physics.

<!-- END 35_first_execution_wave.md -->


---

<!-- BEGIN 36_coding_agent_program_lead_prompt.md -->

# Coding-Agent Prompt: Program Lead and Next-Packet Executor

You are working in `sheepfling/Exhaust-Plume` against the branch and source
snapshot recorded in this handoff.

Read, in order:

```text
README.md
34_comprehensive_work_plan.md
35_first_execution_wave.md
00_unified_plume_architecture.md
10_coding_agent_execution_protocol.md
27_release_gates_and_definition_of_done.md
work_plan.yaml
execution_graph.yaml
```

Then inspect the repository and determine the first incomplete work packet or
PR whose listed dependencies and gate evidence are complete.

## Operating rule

Implement exactly one packet or PR. Do not implement the complete program in
one branch. Do not begin a downstream task merely because the current task is
small.

## Required preflight

1. Confirm repository branch and current commit.
2. Compare reviewed file SHAs with the handoff snapshot when the task touches
   those files.
3. Run and record relevant baseline tests before modification.
4. Read every detailed plan or task packet referenced by the selected work ID.
5. State the selected milestone/work ID, dependencies, expected files,
   equations/contracts, non-goals, and acceptance tests before editing.

## Architecture constraints

- Use the provider/session/snapshot lifecycle.
- Consumers depend on semantic capabilities, not provider implementations.
- Geometry remains optional.
- Morphology, fidelity, radiation model, and execution behavior remain
  orthogonal metadata.
- Intrinsic source signatures exclude range, atmosphere, optics, and detector
  response.
- Provider chaining uses neutral conserved handoffs or standard fields.
- Do not expose provider-private zone or mesh types through generic contracts.
- Do not silently extrapolate, silently fall back, or confuse truncation with
  physical termination.

## Coding constraints

- Python 3.12+.
- Complete type annotations.
- `numpy.typing.NDArray` for numerical arrays.
- Frozen or immutable public contracts.
- Pytest, Ruff, Pyright, and build checks.
- Preserve existing TODOs unless the selected work packet explicitly resolves
  them.
- End every Python scope with `####` according to project convention.
- No network access in tests.
- Heavy spectroscopy, chemistry, or accelerator dependencies remain optional.

## Scientific constraints

- Identify every implemented relation as a governing equation, correlation, or
  closure.
- Use SI units and radians internally.
- Add algebraic/unit verification before calibration.
- Add conservation verification where applicable.
- Add convergence evidence for every numerical solver.
- Keep calibration and validation cases disjoint.
- Carry applicability, provenance, quality, and termination metadata into
  results.

## Required completion report

Return:

```text
selected milestone/work ID and title
dependency and gate evidence
files changed
contracts/equations implemented
behavior and failure semantics
compatibility impact
tests added
numerical or conservation evidence
pytest result
ruff result
pyright result
build and wheel-smoke result
documentation/registry updates
remaining limitations
next eligible work IDs, without starting them
```

If a dependency or architecture decision is genuinely unresolved, stop and
report the exact blocking decision. Do not invent a local workaround that
changes shared consumer semantics.

<!-- END 36_coding_agent_program_lead_prompt.md -->
