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
