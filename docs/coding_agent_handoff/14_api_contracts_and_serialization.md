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
