"""Contracts for the fidelity-isolated reduced-order coherent shock train."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import isfinite
from types import MappingProxyType
from typing import Any, Mapping

from exhaust_plume.contracts.termination import TerminationReason, TerminationReport
from exhaust_plume.models.shock_cells.contracts import ClosedZone

__all__ = (
  'SHOCK_TRAIN_CALIBRATION_PARAMETER_NAMES',
  'CalibrationValidationSplitStatus',
  'GeometryFidelity',
  'ShockCellMetrics',
  'ShockTrainCalibrationValidationSplit',
  'ShockTrainCalibration',
  'ShockTrainCell',
  'ShockTrainResult',
  'ShockTrainStatus',
  'ShockTrainTerminationPolicy',
)


SHOCK_TRAIN_CALIBRATION_PARAMETER_NAMES = (
  'mixing_layer_growth_rate',
  'pressure_amplitude_decay_coefficient',
  'cell_spacing_coefficient',
  'finite_shear_layer_spacing_correction',
  'total_pressure_loss_coefficient',
  'mean_pressure_relaxation_coefficient',
)


class GeometryFidelity(str, Enum):
  """Geometry provenance for one train cell."""

  RESOLVED_FIRST_CELL = 'resolved-first-cell'
  SCALED_REDUCED_ORDER = 'scaled-reduced-order'
####


class CalibrationValidationSplitStatus(str, Enum):
  """Acceptance state for an empirical closure case split."""

  READY = 'disjoint-ready'
  BLOCKED_INSUFFICIENT_CASES = 'blocked-insufficient-disjoint-cases'
####


def _case_id_tuple(name: str, values: tuple[str, ...]) -> tuple[str, ...]:
  normalized = tuple(values)
  if any(not isinstance(value, str) or not value for value in normalized):
    raise ValueError(f'{name} must contain nonempty strings')
  ####
  if len(normalized) != len(set(normalized)):
    raise ValueError(f'{name} must not contain duplicate case IDs')
  ####
  return normalized
####


@dataclass(frozen=True, slots=True)
class ShockTrainCalibrationValidationSplit:
  """Explicit case-role assignment for empirical shock-train closure.

  ``unassigned_case_ids`` keeps recovered or candidate cases visible without
  allowing them to silently serve as both calibration and validation data.
  A split is ready only when both assigned sets are nonempty and disjoint.
  """

  calibration_case_ids: tuple[str, ...] = ()
  validation_case_ids: tuple[str, ...] = ()
  unassigned_case_ids: tuple[str, ...] = ()

  def __post_init__(self) -> None:
    calibration = _case_id_tuple('calibration_case_ids', self.calibration_case_ids)
    validation = _case_id_tuple('validation_case_ids', self.validation_case_ids)
    unassigned = _case_id_tuple('unassigned_case_ids', self.unassigned_case_ids)
    if set(calibration) & set(validation):
      raise ValueError('calibration_case_ids and validation_case_ids must be disjoint')
    ####
    if (set(calibration) | set(validation)) & set(unassigned):
      raise ValueError('unassigned_case_ids must not overlap assigned case IDs')
    ####
    object.__setattr__(self, 'calibration_case_ids', calibration)
    object.__setattr__(self, 'validation_case_ids', validation)
    object.__setattr__(self, 'unassigned_case_ids', unassigned)
  ####

  @property
  def status(self) -> CalibrationValidationSplitStatus:
    if self.calibration_case_ids and self.validation_case_ids:
      return CalibrationValidationSplitStatus.READY
    ####
    return CalibrationValidationSplitStatus.BLOCKED_INSUFFICIENT_CASES
  ####

  @property
  def accepted(self) -> bool:
    return self.status is CalibrationValidationSplitStatus.READY
  ####

  def as_report(self, *, reason: str | None = None) -> dict[str, Any]:
    report: dict[str, Any] = {
      'status': self.status.value,
      'accepted': self.accepted,
      'calibration_cases': len(self.calibration_case_ids),
      'validation_cases': len(self.validation_case_ids),
      'unassigned_cases': len(self.unassigned_case_ids),
      'calibration_case_ids': list(self.calibration_case_ids),
      'validation_case_ids': list(self.validation_case_ids),
      'unassigned_case_ids': list(self.unassigned_case_ids),
    }
    if reason is not None:
      report['reason'] = reason
    ####
    return report
  ####
####


class ShockTrainStatus(str, Enum):
  """Overall status of a shock-train solve."""

  CONVERGED = 'converged'
  PHYSICALLY_TERMINATED = 'physically-terminated'
  TRUNCATED = 'truncated'
  MODEL_VALIDITY_EXCEEDED = 'model-validity-exceeded'
  INVALID_INPUT = 'invalid-input'
  NUMERICAL_FAILURE = 'numerical-failure'
####


def _finite_nonnegative(name: str, value: float) -> float:
  value = float(value)
  if not isfinite(value) or value < 0.0:
    raise ValueError(f'{name} must be finite and nonnegative')
  ####
  return value
####


def _finite_positive(name: str, value: float) -> float:
  value = float(value)
  if not isfinite(value) or value <= 0.0:
    raise ValueError(f'{name} must be finite and positive')
  ####
  return value
####


def _finite_value(name: str, value: float) -> float:
  value = float(value)
  if not isfinite(value):
    raise ValueError(f'{name} must be finite')
  ####
  return value
####


def _range(name: str, value: tuple[float, float]) -> tuple[float, float]:
  if len(value) != 2:
    raise ValueError(f'{name} must contain exactly two values')
  ####
  lower = _finite_nonnegative(f'{name}[0]', value[0])
  upper = _finite_positive(f'{name}[1]', value[1])
  if lower > upper:
    raise ValueError(f'{name} lower bound must not exceed upper bound')
  ####
  return (lower, upper)
####


@dataclass(frozen=True, slots=True)
class ShockTrainCalibration:
  """Provenance-bearing reduced-order closure parameters.

  The parameters are not universal gas-dynamic constants.  A caller must
  provide a calibration identity and source description before a train can be
  solved, keeping an engineering closure from being mistaken for the basic
  first-cell equations.
  """

  calibration_id: str
  source_description: str
  applicable_mach_range: tuple[float, float]
  applicable_pressure_ratio_range: tuple[float, float]
  applicable_temperature_ratio_range: tuple[float, float]
  mixing_layer_growth_rate: float
  pressure_amplitude_decay_coefficient: float
  cell_spacing_coefficient: float
  finite_shear_layer_spacing_correction: float
  total_pressure_loss_coefficient: float
  mean_pressure_relaxation_coefficient: float
  initial_shear_layer_thickness_m: float = 0.0
  minimum_shear_layer_spacing_correction: float = 0.25
  parameter_covariance: tuple[tuple[float, ...], ...] | None = None
  covariance_parameter_names: tuple[str, ...] | None = None

  def __post_init__(self) -> None:
    if not self.calibration_id or not self.source_description:
      raise ValueError('calibration_id and source_description must not be empty')
    ####
    object.__setattr__(self, 'applicable_mach_range', _range('applicable_mach_range', self.applicable_mach_range))
    object.__setattr__(self, 'applicable_pressure_ratio_range', _range('applicable_pressure_ratio_range', self.applicable_pressure_ratio_range))
    object.__setattr__(self, 'applicable_temperature_ratio_range', _range('applicable_temperature_ratio_range', self.applicable_temperature_ratio_range))
    object.__setattr__(self, 'mixing_layer_growth_rate', _finite_nonnegative('mixing_layer_growth_rate', self.mixing_layer_growth_rate))
    object.__setattr__(self, 'pressure_amplitude_decay_coefficient', _finite_nonnegative('pressure_amplitude_decay_coefficient', self.pressure_amplitude_decay_coefficient))
    object.__setattr__(self, 'cell_spacing_coefficient', _finite_positive('cell_spacing_coefficient', self.cell_spacing_coefficient))
    object.__setattr__(self, 'finite_shear_layer_spacing_correction', _finite_nonnegative('finite_shear_layer_spacing_correction', self.finite_shear_layer_spacing_correction))
    object.__setattr__(self, 'total_pressure_loss_coefficient', _finite_nonnegative('total_pressure_loss_coefficient', self.total_pressure_loss_coefficient))
    object.__setattr__(self, 'mean_pressure_relaxation_coefficient', _finite_nonnegative('mean_pressure_relaxation_coefficient', self.mean_pressure_relaxation_coefficient))
    object.__setattr__(self, 'initial_shear_layer_thickness_m', _finite_nonnegative('initial_shear_layer_thickness_m', self.initial_shear_layer_thickness_m))
    minimum_correction = _finite_positive(
      'minimum_shear_layer_spacing_correction',
      self.minimum_shear_layer_spacing_correction,
    )
    if minimum_correction > 1.0:
      raise ValueError('minimum_shear_layer_spacing_correction must not exceed one')
    ####
    object.__setattr__(self, 'minimum_shear_layer_spacing_correction', minimum_correction)
    if self.parameter_covariance is not None:
      rows = tuple(
        tuple(_finite_value('parameter_covariance', value) for value in row)
        for row in self.parameter_covariance
      )
      if not rows or any(len(row) != len(rows) for row in rows):
        raise ValueError('parameter_covariance must be a nonempty square matrix')
      ####
      if any(
          abs(rows[row][column] - rows[column][row]) > 1.0e-12
          for row in range(len(rows))
          for column in range(len(rows))
      ):
        raise ValueError('parameter_covariance must be symmetric')
      ####
      object.__setattr__(self, 'parameter_covariance', rows)
      if self.covariance_parameter_names is None:
        raise ValueError(
          'covariance_parameter_names are required when parameter_covariance is supplied'
        )
      ####
      names = tuple(self.covariance_parameter_names)
      if not names or any(not isinstance(name, str) or not name for name in names):
        raise ValueError(
          'covariance_parameter_names must contain nonempty strings'
        )
      ####
      if len(names) != len(rows) or len(set(names)) != len(names):
        raise ValueError(
          'covariance_parameter_names must match the covariance dimension without duplicates'
        )
      ####
      unknown = sorted(set(names) - set(SHOCK_TRAIN_CALIBRATION_PARAMETER_NAMES))
      if unknown:
        raise ValueError(f'unknown shock-train covariance parameters: {unknown!r}')
      ####
      object.__setattr__(self, 'covariance_parameter_names', names)
    elif self.covariance_parameter_names is not None:
      raise ValueError(
        'covariance_parameter_names require a parameter_covariance matrix'
      )
    ####
  ####
####


@dataclass(frozen=True, slots=True)
class ShockTrainTerminationPolicy:
  """Physical criteria and separate numerical safety limits."""

  epsilon_diameter_fraction: float = 1.0e-3
  epsilon_mach: float = 1.0e-3
  epsilon_oscillation: float = 1.0e-2
  epsilon_mean_pressure: float = 1.0e-2
  persistence_cells: int = 2
  max_cells: int = 64
  max_axial_distance_m: float | None = None

  def __post_init__(self) -> None:
    for name in (
        'epsilon_diameter_fraction',
        'epsilon_mach',
        'epsilon_oscillation',
        'epsilon_mean_pressure',
    ):
      object.__setattr__(self, name, _finite_positive(name, getattr(self, name)))
    ####
    if isinstance(self.persistence_cells, bool) or self.persistence_cells < 1:
      raise ValueError('persistence_cells must be a positive integer')
    ####
    if isinstance(self.max_cells, bool) or self.max_cells < 1:
      raise ValueError('max_cells must be a positive integer')
    ####
    if self.max_axial_distance_m is not None:
      object.__setattr__(self, 'max_axial_distance_m', _finite_positive('max_axial_distance_m', self.max_axial_distance_m))
    ####
  ####
####


@dataclass(frozen=True, slots=True)
class ShockCellMetrics:
  """Diagnostics for one resolved or reduced-order train cell."""

  cell_index: int
  start_x_m: float
  end_x_m: float
  length_m: float
  effective_core_diameter_m: float
  core_mach: float
  mean_pressure_Pa: float
  maximum_pressure_Pa: float
  minimum_pressure_Pa: float
  pressure_oscillation_ratio: float
  mean_pressure_residual: float
  inlet_total_pressure_Pa: float
  outlet_total_pressure_Pa: float
  geometry_fidelity: GeometryFidelity

  def __post_init__(self) -> None:
    if isinstance(self.cell_index, bool) or self.cell_index < 1:
      raise ValueError('cell_index must be a positive integer')
    ####
    for name in (
        'start_x_m',
        'end_x_m',
        'length_m',
        'effective_core_diameter_m',
        'core_mach',
        'mean_pressure_Pa',
        'maximum_pressure_Pa',
        'minimum_pressure_Pa',
        'pressure_oscillation_ratio',
        'mean_pressure_residual',
        'inlet_total_pressure_Pa',
        'outlet_total_pressure_Pa',
    ):
      if not isfinite(float(getattr(self, name))):
        raise ValueError(f'{name} must be finite')
      ####
    ####
    if self.start_x_m < 0.0 or self.end_x_m < self.start_x_m:
      raise ValueError('cell axial bounds must be ordered and nonnegative')
    ####
    if self.length_m <= 0.0 or abs((self.end_x_m - self.start_x_m) - self.length_m) > max(1.0e-12, self.length_m * 1.0e-9):
      raise ValueError('length_m must match the ordered axial bounds')
    ####
    if self.effective_core_diameter_m < 0.0 or self.core_mach < 0.0:
      raise ValueError('core diameter and Mach must be nonnegative')
    ####
    if self.minimum_pressure_Pa <= 0.0 or self.maximum_pressure_Pa < self.minimum_pressure_Pa:
      raise ValueError('pressure extrema must be positive and ordered')
    ####
    if self.pressure_oscillation_ratio < 0.0:
      raise ValueError('pressure_oscillation_ratio must be nonnegative')
    ####
    if self.inlet_total_pressure_Pa <= 0.0 or self.outlet_total_pressure_Pa <= 0.0:
      raise ValueError('total pressures must be positive')
    ####
    if self.outlet_total_pressure_Pa > self.inlet_total_pressure_Pa * (1.0 + 1.0e-9):
      raise ValueError('a train cell may not increase total pressure')
    ####
  ####
####


@dataclass(frozen=True, slots=True)
class ShockTrainCell:
  """One train cell and its optional adapted geometry."""

  metrics: ShockCellMetrics
  zones: tuple[ClosedZone, ...] = ()
####


@dataclass(frozen=True, slots=True)
class ShockTrainResult:
  """Finite coherent train with physical/safety termination metadata."""

  cells: tuple[ShockTrainCell, ...]
  shock_train_end_x_m: float | None
  supersonic_core_end_x_m: float | None
  thermal_plume_end_x_m: float | None
  termination: TerminationReport
  status: ShockTrainStatus
  was_domain_truncated: bool
  calibration_id: str
  uncertainty: Mapping[str, Any] = field(default_factory=dict)
  diagnostics: Mapping[str, Any] = field(default_factory=dict)

  def __post_init__(self) -> None:
    cells = tuple(self.cells)
    object.__setattr__(self, 'cells', cells)
    if not self.calibration_id:
      raise ValueError('calibration_id must not be empty')
    ####
    for name in ('shock_train_end_x_m', 'supersonic_core_end_x_m', 'thermal_plume_end_x_m'):
      value = getattr(self, name)
      if value is not None and (not isfinite(float(value)) or float(value) < 0.0):
        raise ValueError(f'{name} must be finite and nonnegative when supplied')
      ####
    ####
    object.__setattr__(self, 'uncertainty', MappingProxyType(dict(self.uncertainty)))
    object.__setattr__(self, 'diagnostics', MappingProxyType(dict(self.diagnostics)))
    if self.was_domain_truncated and self.termination.is_physical:
      raise ValueError('domain truncation and physical termination cannot both be true')
    ####
  ####

  @property
  def cell_count(self) -> int:
    return len(self.cells)
  ####

  @property
  def termination_reason(self) -> TerminationReason:
    return self.termination.reason
  ####
####
