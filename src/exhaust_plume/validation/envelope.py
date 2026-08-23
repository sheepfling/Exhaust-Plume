"""Study-validity assessment for the supported simple plume path.

The envelope in this module is a declared numerical/study boundary.  It is
not an external physical validation claim.  A case can be inside the declared
input envelope and still be marked marginal or outside after the low-order
shock-cell execution reports a construction or numerical failure.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable

from pydantic import BaseModel, ConfigDict, Field, model_validator

from exhaust_plume.contracts import ApplicabilityStatus
from exhaust_plume.models.gas.calorically_perfect import CaloricallyPerfectGas
from exhaust_plume.models.nozzle.contracts import AmbientInput
from exhaust_plume.models.nozzle.exit_state import derive_ambient_state
from exhaust_plume.models.nozzle.geometry import NozzleGeometry, ThroatConfiguration, derive_nozzle_exit_from_geometry
from exhaust_plume.models.shock_cells import (
  ExpansionRegime,
  ShockCellSolveConfig,
  SolverStatus,
  TerminationReason,
  solve_shock_cells,
)

__all__ = (
  'DEFAULT_STUDY_VALIDITY_ENVELOPE',
  'NozzleCaseAssessment',
  'NozzleValidityCase',
  'StudyValidityEnvelope',
  'default_nozzle_geometries',
  'default_pressure_sweep',
  'default_validity_cases',
  'evaluate_nozzle_case',
  'evaluate_validity_matrix',
  'write_validity_report_csv',
  'write_validity_report_json',
)


class StudyValidityEnvelope(BaseModel):
  """Declared finite study range for the simple constant-gamma model."""

  model_config = ConfigDict(frozen=True, extra='forbid', allow_inf_nan=False)

  envelope_id: str = Field(default='simple-straight-study-v1', min_length=1)
  min_total_pressure_Pa: float = Field(default=1.0e3, gt=0.0)
  max_total_pressure_Pa: float = Field(default=1.0e8, gt=0.0)
  min_total_temperature_K: float = Field(default=200.0, gt=0.0)
  max_total_temperature_K: float = Field(default=3000.0, gt=0.0)
  min_ambient_pressure_Pa: float = Field(default=1.0, gt=0.0)
  max_ambient_pressure_Pa: float = Field(default=2.0e6, gt=0.0)
  marginal_ambient_pressure_low_Pa: float = Field(default=10.0, gt=0.0)
  marginal_ambient_pressure_high_Pa: float = Field(default=1.0e6, gt=0.0)
  min_exit_mach: float = Field(default=1.1, gt=1.0)
  max_exit_mach: float = Field(default=8.0, gt=1.0)
  marginal_exit_mach_low: float = Field(default=1.25, gt=1.0)
  marginal_exit_mach_high: float = Field(default=6.0, gt=1.0)
  min_area_ratio: float = Field(default=1.02, gt=1.0)
  max_area_ratio: float = Field(default=100.0, gt=1.0)
  marginal_area_ratio_low: float = Field(default=1.2, gt=1.0)
  marginal_area_ratio_high: float = Field(default=50.0, gt=1.0)
  min_exit_to_ambient_pressure_ratio: float = Field(default=1.0e-2, gt=0.0)
  max_exit_to_ambient_pressure_ratio: float = Field(default=1.0e3, gt=0.0)
  marginal_pressure_ratio_low: float = Field(default=0.1, gt=0.0)
  marginal_pressure_ratio_high: float = Field(default=100.0, gt=0.0)
  min_gamma: float = Field(default=1.1, gt=1.0)
  max_gamma: float = Field(default=1.67, gt=1.0)
  marginal_gamma_low: float = Field(default=1.2, gt=1.0)
  marginal_gamma_high: float = Field(default=1.6, gt=1.0)

  @model_validator(mode='after')
  def validate_ordering(self) -> StudyValidityEnvelope:
    pairs = (
      ('total pressure', self.min_total_pressure_Pa, self.max_total_pressure_Pa),
      ('total temperature', self.min_total_temperature_K, self.max_total_temperature_K),
      ('ambient pressure', self.min_ambient_pressure_Pa, self.max_ambient_pressure_Pa),
      ('exit Mach', self.min_exit_mach, self.max_exit_mach),
      ('area ratio', self.min_area_ratio, self.max_area_ratio),
      ('exit-to-ambient pressure ratio', self.min_exit_to_ambient_pressure_ratio, self.max_exit_to_ambient_pressure_ratio),
      ('gamma', self.min_gamma, self.max_gamma),
    )
    if any(lower >= upper for _, lower, upper in pairs):
      raise ValueError('validity envelope lower bounds must be below upper bounds')
    ####
    if not self.min_ambient_pressure_Pa <= self.marginal_ambient_pressure_low_Pa < self.max_ambient_pressure_Pa:
      raise ValueError('marginal ambient pressure low bound must lie inside the ambient pressure range')
    ####
    if not self.min_ambient_pressure_Pa < self.marginal_ambient_pressure_high_Pa <= self.max_ambient_pressure_Pa:
      raise ValueError('marginal ambient pressure high bound must lie inside the ambient pressure range')
    ####
    if not self.min_exit_mach <= self.marginal_exit_mach_low < self.max_exit_mach:
      raise ValueError('marginal Mach low bound must lie inside the Mach range')
    ####
    if not self.min_exit_mach < self.marginal_exit_mach_high <= self.max_exit_mach:
      raise ValueError('marginal Mach high bound must lie inside the Mach range')
    ####
    if not self.min_area_ratio <= self.marginal_area_ratio_low < self.max_area_ratio:
      raise ValueError('marginal area-ratio low bound must lie inside the area-ratio range')
    ####
    if not self.min_area_ratio < self.marginal_area_ratio_high <= self.max_area_ratio:
      raise ValueError('marginal area-ratio high bound must lie inside the area-ratio range')
    ####
    if not self.min_exit_to_ambient_pressure_ratio <= self.marginal_pressure_ratio_low < self.max_exit_to_ambient_pressure_ratio:
      raise ValueError('marginal pressure-ratio low bound must lie inside the pressure-ratio range')
    ####
    if not self.min_exit_to_ambient_pressure_ratio < self.marginal_pressure_ratio_high <= self.max_exit_to_ambient_pressure_ratio:
      raise ValueError('marginal pressure-ratio high bound must lie inside the pressure-ratio range')
    ####
    if not self.min_gamma <= self.marginal_gamma_low < self.max_gamma:
      raise ValueError('marginal gamma low bound must lie inside the gamma range')
    ####
    if not self.min_gamma < self.marginal_gamma_high <= self.max_gamma:
      raise ValueError('marginal gamma high bound must lie inside the gamma range')
    ####
    return self
  ####
####


DEFAULT_STUDY_VALIDITY_ENVELOPE = StudyValidityEnvelope()


class NozzleValidityCase(BaseModel):
  """One reproducible geometry, gas, and ambient operating point."""

  model_config = ConfigDict(frozen=True, extra='forbid', allow_inf_nan=False)

  case_id: str = Field(min_length=1)
  geometry: NozzleGeometry
  total_pressure_Pa: float = Field(gt=0.0)
  total_temperature_K: float = Field(gt=0.0)
  ambient_pressure_Pa: float = Field(gt=0.0)
  ambient_temperature_K: float = Field(gt=0.0)
  gas: CaloricallyPerfectGas
  expansion_characteristics: int = Field(default=2, ge=2)
  compression_characteristics: int = Field(default=1, ge=1)
  max_cells: int = Field(default=1, ge=0)
  pressure_match_rtol: float = Field(default=1.0e-4, gt=0.0)
####


class NozzleCaseAssessment(BaseModel):
  """Serializable assessment with input applicability and execution status."""

  model_config = ConfigDict(frozen=True, extra='forbid', allow_inf_nan=False)

  case_id: str = Field(min_length=1)
  validity_status: ApplicabilityStatus
  reasons: tuple[str, ...] = ()
  geometry_id: str = Field(min_length=1)
  throat_area_m2: float = Field(gt=0.0)
  exit_area_m2: float = Field(gt=0.0)
  area_ratio: float = Field(gt=1.0)
  total_pressure_Pa: float = Field(gt=0.0)
  total_temperature_K: float = Field(gt=0.0)
  ambient_pressure_Pa: float = Field(gt=0.0)
  ambient_temperature_K: float = Field(gt=0.0)
  gamma: float = Field(gt=1.0)
  exit_mach: float | None = Field(default=None, gt=1.0)
  exit_static_pressure_Pa: float | None = Field(default=None, gt=0.0)
  exit_to_ambient_pressure_ratio: float | None = Field(default=None, gt=0.0)
  regime: ExpansionRegime | None = None
  solver_status: SolverStatus | None = None
  termination_reason: TerminationReason | None = None
  zone_count: int = Field(default=0, ge=0)
  error: str | None = None
####


def _range_reasons(
    label: str,
    value: float,
    minimum: float,
    maximum: float,
    marginal_low: float | None = None,
    marginal_high: float | None = None,
) -> tuple[bool, bool, tuple[str, ...]]:
  if value < minimum or value > maximum:
    return True, False, (f'{label}={value:g} is outside [{minimum:g}, {maximum:g}]',)
  ####
  marginal = (
    marginal_low is not None and value <= marginal_low
  ) or (
    marginal_high is not None and value >= marginal_high
  )
  if marginal:
    return False, True, (f'{label}={value:g} is in a declared marginal boundary band',)
  ####
  return False, False, ()
####


def _assess_inputs(
    case: NozzleValidityCase,
    *,
    exit_mach: float,
    exit_pressure_Pa: float,
    envelope: StudyValidityEnvelope,
) -> tuple[ApplicabilityStatus, tuple[str, ...]]:
  pressure_ratio = exit_pressure_Pa / case.ambient_pressure_Pa
  metrics = (
    ('total_pressure_Pa', case.total_pressure_Pa, envelope.min_total_pressure_Pa, envelope.max_total_pressure_Pa, None, None),
    ('total_temperature_K', case.total_temperature_K, envelope.min_total_temperature_K, envelope.max_total_temperature_K, 300.0, 2500.0),
    ('ambient_pressure_Pa', case.ambient_pressure_Pa, envelope.min_ambient_pressure_Pa, envelope.max_ambient_pressure_Pa, envelope.marginal_ambient_pressure_low_Pa, envelope.marginal_ambient_pressure_high_Pa),
    ('exit_mach', exit_mach, envelope.min_exit_mach, envelope.max_exit_mach, envelope.marginal_exit_mach_low, envelope.marginal_exit_mach_high),
    ('area_ratio', case.geometry.area_ratio, envelope.min_area_ratio, envelope.max_area_ratio, envelope.marginal_area_ratio_low, envelope.marginal_area_ratio_high),
    ('exit_to_ambient_pressure_ratio', pressure_ratio, envelope.min_exit_to_ambient_pressure_ratio, envelope.max_exit_to_ambient_pressure_ratio, envelope.marginal_pressure_ratio_low, envelope.marginal_pressure_ratio_high),
    ('gamma', case.gas.gamma, envelope.min_gamma, envelope.max_gamma, envelope.marginal_gamma_low, envelope.marginal_gamma_high),
  )
  outside: list[str] = []
  marginal: list[str] = []
  for label, value, minimum, maximum, marginal_low, marginal_high in metrics:
    is_outside, is_marginal, reasons = _range_reasons(label, value, minimum, maximum, marginal_low, marginal_high)
    if is_outside:
      outside.extend(reasons)
    elif is_marginal:
      marginal.extend(reasons)
    ####
  ####
  if outside:
    return ApplicabilityStatus.OUTSIDE, tuple(outside + marginal)
  ####
  if marginal:
    return ApplicabilityStatus.MARGINAL, tuple(marginal)
  ####
  return ApplicabilityStatus.INSIDE, ()
####


def evaluate_nozzle_case(
    case: NozzleValidityCase,
    *,
    envelope: StudyValidityEnvelope = DEFAULT_STUDY_VALIDITY_ENVELOPE,
) -> NozzleCaseAssessment:
  """Run one case and preserve both applicability and solver outcomes."""

  geometry = case.geometry
  base = {
    'case_id': case.case_id,
    'geometry_id': geometry.geometry_id,
    'throat_area_m2': geometry.throat.area_m2,
    'exit_area_m2': geometry.exit_area_m2,
    'area_ratio': geometry.area_ratio,
    'total_pressure_Pa': case.total_pressure_Pa,
    'total_temperature_K': case.total_temperature_K,
    'ambient_pressure_Pa': case.ambient_pressure_Pa,
    'ambient_temperature_K': case.ambient_temperature_K,
    'gamma': case.gas.gamma,
  }
  try:
    exit_state = derive_nozzle_exit_from_geometry(
        geometry,
        total_pressure_Pa=case.total_pressure_Pa,
        total_temperature_K=case.total_temperature_K,
        gas=case.gas,
    )
    ambient = derive_ambient_state(
        AmbientInput(
            pressure_Pa=case.ambient_pressure_Pa,
            temperature_K=case.ambient_temperature_K,
        ),
        case.gas,
    )
  except (ArithmeticError, ValueError) as caught:
    return NozzleCaseAssessment(
        **base,
        validity_status=ApplicabilityStatus.OUTSIDE,
        reasons=(f'input derivation failed: {caught}',),
        error=str(caught),
    )
  ####

  validity_status, reasons = _assess_inputs(
      case,
      exit_mach=exit_state.mach,
      exit_pressure_Pa=exit_state.static_pressure_Pa,
      envelope=envelope,
  )
  solver_status: SolverStatus | None = None
  regime: ExpansionRegime | None = None
  termination_reason: TerminationReason | None = None
  error: str | None = None
  zone_count = 0
  try:
    solved = solve_shock_cells(ShockCellSolveConfig(
        exit=exit_state,
        ambient=ambient,
        expansion_characteristics=case.expansion_characteristics,
        compression_characteristics=case.compression_characteristics,
        max_cells=case.max_cells,
        pressure_match_rtol=case.pressure_match_rtol,
    ))
    solver_status = solved.status
    regime = solved.regime
    termination_reason = solved.termination_reason
    zone_count = len(solved.zones)
  except (ArithmeticError, ValueError) as caught:
    error = str(caught)
  ####

  final_reasons = list(reasons)
  if error is not None:
    validity_status = ApplicabilityStatus.OUTSIDE
    final_reasons.append(f'low-order solver execution failed: {error}')
  elif solver_status is not None and solver_status in (
      SolverStatus.NUMERICAL_FAILURE,
      SolverStatus.OUTSIDE_MODEL_VALIDITY,
      SolverStatus.INVALID_INPUT,
  ):
    validity_status = ApplicabilityStatus.OUTSIDE
    final_reasons.append(f'low-order solver status is {solver_status.value}')
  elif solver_status is SolverStatus.CONVERGED_AT_BOUNDARY:
    if validity_status is ApplicabilityStatus.INSIDE:
      validity_status = ApplicabilityStatus.MARGINAL
    ####
    final_reasons.append('result is limited by the requested low-order construction boundary')
  ####
  return NozzleCaseAssessment(
      **base,
      validity_status=validity_status,
      reasons=tuple(final_reasons),
      exit_mach=exit_state.mach,
      exit_static_pressure_Pa=exit_state.static_pressure_Pa,
      exit_to_ambient_pressure_ratio=exit_state.static_pressure_Pa / case.ambient_pressure_Pa,
      regime=regime,
      solver_status=solver_status,
      termination_reason=termination_reason,
      zone_count=zone_count,
      error=error,
  )
####


def evaluate_validity_matrix(
    cases: Iterable[NozzleValidityCase],
    *,
    envelope: StudyValidityEnvelope = DEFAULT_STUDY_VALIDITY_ENVELOPE,
) -> tuple[NozzleCaseAssessment, ...]:
  """Evaluate a deterministic matrix and reject duplicate case identifiers."""

  materialized = tuple(cases)
  case_ids = tuple(case.case_id for case in materialized)
  if len(case_ids) != len(set(case_ids)):
    raise ValueError('validity matrix case_id values must be unique')
  ####
  return tuple(evaluate_nozzle_case(case, envelope=envelope) for case in materialized)
####


def default_pressure_sweep() -> tuple[float, ...]:
  """Return atmosphere through finite near-vacuum pressures in Pa."""

  return (101325.0, 1.0e4, 1.0e2, 1.0, 1.0e-2)
####


def default_nozzle_geometries() -> tuple[NozzleGeometry, ...]:
  """Return three circular throat/area-ratio configurations for smoke studies."""

  configurations = (
    ('small-throat-area-ratio-4', 1.0e-3, 4.0),
    ('medium-throat-area-ratio-9', 1.0e-2, 9.0),
    ('large-throat-area-ratio-25', 1.0e-1, 25.0),
  )
  return tuple(
    NozzleGeometry(
        geometry_id=geometry_id,
        throat=ThroatConfiguration(area_m2=throat_area, profile_id=f'{geometry_id}-throat'),
        exit_area_m2=throat_area * area_ratio,
    )
    for geometry_id, throat_area, area_ratio in configurations
  )
####


def default_validity_cases() -> tuple[NozzleValidityCase, ...]:
  """Build a compact throat, gas, temperature, and pressure matrix."""

  gammas = (1.2, 1.4, 1.67)
  total_temperatures = (500.0, 800.0, 1500.0)
  cases: list[NozzleValidityCase] = []
  for geometry_index, (geometry, gamma, total_temperature) in enumerate(
      zip(default_nozzle_geometries(), gammas, total_temperatures, strict=True),
  ):
    gas = CaloricallyPerfectGas.dry_air(gamma=gamma)
    for pressure_index, ambient_pressure in enumerate(default_pressure_sweep()):
      cases.append(NozzleValidityCase(
          case_id=f'geometry-{geometry_index + 1}-pressure-{pressure_index + 1}',
          geometry=geometry,
          total_pressure_Pa=20.0 * 101325.0,
          total_temperature_K=total_temperature,
          ambient_pressure_Pa=ambient_pressure,
          ambient_temperature_K=300.0,
          gas=gas,
      ))
    ####
  ####
  return tuple(cases)
####


def write_validity_report_json(
    results: Iterable[NozzleCaseAssessment],
    path: str | Path,
    *,
    envelope: StudyValidityEnvelope = DEFAULT_STUDY_VALIDITY_ENVELOPE,
) -> Path:
  """Write a canonical machine-readable validity report."""

  output = Path(path)
  output.parent.mkdir(parents=True, exist_ok=True)
  payload = {
    'report_schema': 'plume.study-validity-report@1',
    'envelope': envelope.model_dump(mode='json'),
    'results': [result.model_dump(mode='json') for result in results],
  }
  output.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')
  return output
####


def write_validity_report_csv(results: Iterable[NozzleCaseAssessment], path: str | Path) -> Path:
  """Write one flat row per validity-matrix case."""

  output = Path(path)
  output.parent.mkdir(parents=True, exist_ok=True)
  rows = tuple(results)
  with output.open('w', encoding='utf-8', newline='') as stream:
    writer = csv.writer(stream)
    writer.writerow((
      'case_id',
      'validity_status',
      'geometry_id',
      'throat_area_m2',
      'exit_area_m2',
      'area_ratio',
      'total_pressure_Pa',
      'total_temperature_K',
      'ambient_pressure_Pa',
      'ambient_temperature_K',
      'gamma',
      'exit_mach',
      'exit_static_pressure_Pa',
      'exit_to_ambient_pressure_ratio',
      'regime',
      'solver_status',
      'termination_reason',
      'zone_count',
      'reasons',
      'error',
    ))
    for result in rows:
      writer.writerow((
        result.case_id,
        result.validity_status.value,
        result.geometry_id,
        result.throat_area_m2,
        result.exit_area_m2,
        result.area_ratio,
        result.total_pressure_Pa,
        result.total_temperature_K,
        result.ambient_pressure_Pa,
        result.ambient_temperature_K,
        result.gamma,
        result.exit_mach,
        result.exit_static_pressure_Pa,
        result.exit_to_ambient_pressure_ratio,
        result.regime.value if result.regime is not None else None,
        result.solver_status.value if result.solver_status is not None else None,
        result.termination_reason.value if result.termination_reason is not None else None,
        result.zone_count,
        ' | '.join(result.reasons),
        result.error,
      ))
    ####
  ####
  return output
####
