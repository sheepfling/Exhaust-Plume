"""Independent refinement evidence for solver-generated shock-cell fits.

The frontier-only production fitter produces a useful research candidate, but
one fit at one retained resolution is not a physical cell-length result.  This
module audits a caller-produced resolution ladder without changing the fit,
replacing the solver-owned shock path, or binding external evidence that is
not present.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from math import isfinite
from typing import Any, Sequence

from exhaust_plume.models.moc.chain import MocChainBoundarySample
from exhaust_plume.models.moc.chain import MocChainContinuationPolicy
from exhaust_plume.models.moc.global_physical_closure import (
  MocProductionShockCellFitResult,
  MocReflectedDomainGlobalPhysicalClosureResult,
  moc_reflected_domain_global_physical_closure_fingerprint,
  fit_reflected_domain_production_shock_cell,
  solve_reflected_domain_global_physical_closure,
)
from exhaust_plume.models.moc.reflected_domain import (
  MocReflectedDomainAlternatingSourceResult,
  MocReflectedDomainGlobalEulerShockBoundaryResult,
)
from exhaust_plume.models.moc.planner import (
  MocChainPlannerResult,
  MocGlobalEulerContinuedChainReference,
  plan_reflected_domain_global_euler_continued_chain,
)
from exhaust_plume.validation.moc_measurements import (
  MocShockCellMeasurement,
  measure_moc_production_shock_cell_fit,
)
from exhaust_plume.validation.moc_reflected_domain_refinement import (
  run_moc_reflected_domain_global_euler_shock_boundary_refinement,
)

__all__ = (
  'MOC_PRODUCTION_SHOCK_CELL_FIT_REFINEMENT_OPERATOR_ID',
  'MocProductionShockCellFitRefinementStatus',
  'MocProductionShockCellFitRefinementCase',
  'MocProductionShockCellFitRefinementMeasurement',
  'measure_moc_production_shock_cell_fit_refinement',
  'MOC_PRODUCTION_SHOCK_CELL_FIT_REFINEMENT_RUN_OPERATOR_ID',
  'MocProductionShockCellFitRefinementRun',
  'run_moc_production_shock_cell_fit_refinement',
  'MOC_PRODUCTION_SHOCK_CELL_CONTINUED_CHAIN_RUN_OPERATOR_ID',
  'MocProductionShockCellContinuedChainStatus',
  'MocProductionShockCellContinuedChainRun',
  'run_moc_production_shock_cell_continued_chain',
)


MOC_PRODUCTION_SHOCK_CELL_FIT_REFINEMENT_OPERATOR_ID = (
  'op.moc.reflected-domain.production-shock-cell-fit-refinement'
)
MOC_PRODUCTION_SHOCK_CELL_FIT_REFINEMENT_RUN_OPERATOR_ID = (
  'op.moc.reflected-domain.production-shock-cell-fit-refinement-run'
)
MOC_PRODUCTION_SHOCK_CELL_CONTINUED_CHAIN_RUN_OPERATOR_ID = (
  'op.moc.reflected-domain.production-shock-cell-continued-chain-run'
)


class MocProductionShockCellFitRefinementStatus(str, Enum):
  """Outcome of the independent shock-cell fit resolution audit."""

  CONVERGED_LOCAL_FIT_REFINEMENT = (
    'converged_local_production_shock_cell_fit_refinement'
  )
  INVALID_INPUT = 'invalid_input'
  RESOLUTION_FAILURE = 'production_shock_cell_refinement_resolution_failure'
  SOURCE_FAILURE = 'production_shock_cell_refinement_source_failure'
  FIT_FAILURE = 'production_shock_cell_refinement_fit_failure'
  MEASUREMENT_FAILURE = 'production_shock_cell_refinement_measurement_failure'
  PLACEMENT_FAILURE = 'production_shock_cell_refinement_placement_failure'
  LENGTH_STABILITY_FAILURE = (
    'production_shock_cell_refinement_length_stability_failure'
  )
####


@dataclass(frozen=True, slots=True)
class MocProductionShockCellFitRefinementCase:
  """One solver-generated fit retained at a declared shock resolution."""

  resolution: int
  fit: MocProductionShockCellFitResult

  def __post_init__(self) -> None:
    if (
      isinstance(self.resolution, bool)
      or not isinstance(self.resolution, int)
      or self.resolution < 1
    ):
      raise ValueError('resolution must be a positive integer')
    ####
    if not isinstance(self.fit, MocProductionShockCellFitResult):
      raise TypeError(
        'fit must be a MocProductionShockCellFitResult'
      )
    ####
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'resolution': self.resolution,
      'fit_status': self.fit.status.value,
      'local_fit_verified': self.fit.local_fit_verified,
      'closure_fingerprint': (
        None
        if self.fit.closure is None
        else moc_reflected_domain_global_physical_closure_fingerprint(
          self.fit.closure
        )
      ),
      'fitted_shock_sample_count': len(self.fit.fitted_shock_points_m),
      'start_x_m': self.fit.start_x_m,
      'end_x_m': self.fit.end_x_m,
      'cell_index': self.fit.cell_index,
    }
  ####
####


def _source_fingerprint(source_band: Any) -> str:
  """Fingerprint the immutable upstream source carried by a closure."""

  report = source_band.as_report()
  return _payload_fingerprint(report)
####


def _payload_fingerprint(payload: Any) -> str:
  """Return a deterministic fingerprint for a configuration payload."""

  serialized = json.dumps(
    payload,
    sort_keys=True,
    separators=(',', ':'),
    ensure_ascii=True,
    default=str,
  )
  return sha256(serialized.encode('utf-8')).hexdigest()
####


def _boundary_sample_payload(sample: MocChainBoundarySample) -> dict[str, Any]:
  """Return a deterministic JSON payload for one carried boundary sample."""

  state = sample.state
  return {
    'state': {
      'x_m': state.x_m,
      'y_m': state.y_m,
      'theta_rad': state.theta_rad,
      'mach': state.mach,
      'gamma': state.gamma,
    },
    'total_pressure_Pa': sample.total_pressure_Pa,
  }
####


@dataclass(frozen=True, slots=True)
class MocProductionShockCellFitRefinementMeasurement:
  """Independent evidence for a fit ladder below physical acceptance.

  The ladder verifies that each fit is locally closed, source-bound, measured
  against its own retained field, and placed over the same axial interval.  It
  reports resolution-to-resolution length variation, but deliberately does
  not mark any length as an accepted physical observation.
  """

  status: MocProductionShockCellFitRefinementStatus
  cases: tuple[MocProductionShockCellFitRefinementCase, ...] = ()
  measurements: tuple[MocShockCellMeasurement, ...] = ()
  resolutions: tuple[int, ...] = ()
  closure_fingerprints: tuple[str, ...] = ()
  source_band_fingerprints: tuple[str, ...] = ()
  shock_sample_counts: tuple[int, ...] = ()
  axial_lengths_m: tuple[float | None, ...] = ()
  axial_length_deltas_m: tuple[float | None, ...] = ()
  resolution_order_verified: bool = False
  case_fits_verified: bool = False
  source_binding_verified: bool = False
  closure_resolution_identity_verified: bool = False
  placement_verified: bool = False
  measurements_verified: bool = False
  shock_sample_growth_verified: bool = False
  lengths_finite_verified: bool = False
  length_resolution_sequence_verified: bool = False
  physical_closure_verified: bool = False
  fidelity_isolation_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  external_validation_required: bool = True
  length_tolerance_m: float = 1.0e-6
  position_tolerance_m: float = 1.0e-8
  claim_status: str = (
    'independent-production-shock-cell-fit-refinement; not-accepted'
  )
  message: str = ''
  operator_id: str = MOC_PRODUCTION_SHOCK_CELL_FIT_REFINEMENT_OPERATOR_ID

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocProductionShockCellFitRefinementStatus,
    ):
      raise TypeError(
        'status must be a MocProductionShockCellFitRefinementStatus'
      )
    ####
    cases = tuple(self.cases)
    measurements = tuple(self.measurements)
    if len(cases) != len(measurements):
      raise ValueError('cases and measurements must have equal lengths')
    ####
    if any(
      not isinstance(case, MocProductionShockCellFitRefinementCase)
      for case in cases
    ):
      raise TypeError(
        'cases must contain MocProductionShockCellFitRefinementCase values'
      )
    ####
    if any(
      not isinstance(measurement, MocShockCellMeasurement)
      for measurement in measurements
    ):
      raise TypeError(
        'measurements must contain MocShockCellMeasurement values'
      )
    ####
    object.__setattr__(self, 'cases', cases)
    object.__setattr__(self, 'measurements', measurements)

    derived_resolutions = tuple(case.resolution for case in cases)
    if self.resolutions and tuple(self.resolutions) != derived_resolutions:
      raise ValueError('resolutions must match the supplied cases')
    ####
    object.__setattr__(self, 'resolutions', derived_resolutions)

    for name in (
      'closure_fingerprints',
      'source_band_fingerprints',
    ):
      values = tuple(str(value) for value in getattr(self, name))
      if len(values) != len(cases):
        raise ValueError(f'{name} must match the case count')
      ####
      if any(not value for value in values):
        raise ValueError(f'{name} must contain non-empty strings')
      ####
      object.__setattr__(self, name, values)
    ####

    shock_counts = tuple(self.shock_sample_counts)
    if len(shock_counts) != len(cases):
      raise ValueError('shock_sample_counts must match the case count')
    ####
    if any(
      isinstance(value, bool) or not isinstance(value, int) or value < 0
      for value in shock_counts
    ):
      raise ValueError('shock_sample_counts must contain nonnegative integers')
    ####
    object.__setattr__(self, 'shock_sample_counts', shock_counts)

    lengths = tuple(self.axial_lengths_m)
    if len(lengths) != len(cases):
      raise ValueError('axial_lengths_m must match the case count')
    ####
    for value in lengths:
      if value is not None:
        normalized = float(value)
        if not isfinite(normalized) or normalized < 0.0:
          raise ValueError(
            'axial_lengths_m must contain finite nonnegative values or None'
          )
        ####
      ####
    ####
    object.__setattr__(self, 'axial_lengths_m', lengths)

    deltas = tuple(self.axial_length_deltas_m)
    if len(deltas) != max(0, len(cases) - 1):
      raise ValueError(
        'axial_length_deltas_m must contain one value between each pair of cases'
      )
    ####
    for value in deltas:
      if value is not None:
        normalized = float(value)
        if not isfinite(normalized) or normalized < 0.0:
          raise ValueError(
            'axial_length_deltas_m must contain finite nonnegative values or None'
          )
        ####
      ####
    ####
    object.__setattr__(self, 'axial_length_deltas_m', deltas)

    for name in (
      'resolution_order_verified',
      'case_fits_verified',
      'source_binding_verified',
      'closure_resolution_identity_verified',
      'placement_verified',
      'measurements_verified',
      'shock_sample_growth_verified',
      'lengths_finite_verified',
      'length_resolution_sequence_verified',
      'physical_closure_verified',
      'fidelity_isolation_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
      'external_validation_required',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if not self.chain_promotion_blocked:
      raise ValueError('shock-cell fit refinement must retain promotion block')
    ####
    if self.production_claim_allowed:
      raise ValueError(
        'shock-cell fit refinement cannot claim production validity'
      )
    ####
    if not self.external_validation_required:
      raise ValueError(
        'shock-cell fit refinement must retain the external-validation gate'
      )
    ####
    for name in ('length_tolerance_m', 'position_tolerance_m'):
      value = float(getattr(self, name))
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      ####
      object.__setattr__(self, name, value)
    ####
    operator_id = str(self.operator_id)
    if not operator_id:
      raise ValueError('operator_id must be a non-empty string')
    ####
    object.__setattr__(self, 'operator_id', operator_id)
    claim_status = str(self.claim_status)
    if not claim_status:
      raise ValueError('claim_status must be a non-empty string')
    ####
    object.__setattr__(self, 'claim_status', claim_status)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status is (
      MocProductionShockCellFitRefinementStatus
      .CONVERGED_LOCAL_FIT_REFINEMENT
    )
  ####

  @property
  def local_consistency_verified(self) -> bool:
    """Whether the fit ladder passes local evidence gates only."""

    return bool(
      self.converged
      and len(self.cases) >= 2
      and self.resolution_order_verified
      and self.case_fits_verified
      and self.source_binding_verified
      and self.closure_resolution_identity_verified
      and self.placement_verified
      and self.measurements_verified
      and self.shock_sample_growth_verified
      and self.lengths_finite_verified
      and self.length_resolution_sequence_verified
      and self.physical_closure_verified
      and self.fidelity_isolation_verified
      and self.external_validation_required
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'local_consistency_verified': self.local_consistency_verified,
      'resolutions': list(self.resolutions),
      'closure_fingerprints': list(self.closure_fingerprints),
      'source_band_fingerprints': list(self.source_band_fingerprints),
      'shock_sample_counts': list(self.shock_sample_counts),
      'axial_lengths_m': list(self.axial_lengths_m),
      'axial_length_deltas_m': list(self.axial_length_deltas_m),
      'cases': [
        {
          'resolution': case.resolution,
          'fit_status': case.fit.status.value,
          'local_fit_verified': case.fit.local_fit_verified,
          'closure_fingerprint': (
            None
            if case.fit.closure is None
            else moc_reflected_domain_global_physical_closure_fingerprint(
              case.fit.closure
            )
          ),
        }
        for case in self.cases
      ],
      'measurements': [measurement.as_report() for measurement in self.measurements],
      'checks': {
        'resolution_order_verified': self.resolution_order_verified,
        'case_fits_verified': self.case_fits_verified,
        'source_binding_verified': self.source_binding_verified,
        'closure_resolution_identity_verified': (
          self.closure_resolution_identity_verified
        ),
        'placement_verified': self.placement_verified,
        'measurements_verified': self.measurements_verified,
        'shock_sample_growth_verified': self.shock_sample_growth_verified,
        'lengths_finite_verified': self.lengths_finite_verified,
        'length_resolution_sequence_verified': (
          self.length_resolution_sequence_verified
        ),
        'physical_closure_verified': self.physical_closure_verified,
        'fidelity_isolation_verified': self.fidelity_isolation_verified,
        'external_validation_required': self.external_validation_required,
        'chain_promotion_blocked': self.chain_promotion_blocked,
        'production_claim_allowed': self.production_claim_allowed,
      },
      'physical_length_accepted': False,
      'external_validation_verified': False,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'length_tolerance_m': self.length_tolerance_m,
      'position_tolerance_m': self.position_tolerance_m,
      'claim_status': self.claim_status,
      'message': self.message,
    }
  ####
####


def _failure(
  status: MocProductionShockCellFitRefinementStatus,
  message: str,
  *,
  cases: Sequence[MocProductionShockCellFitRefinementCase] = (),
  measurements: Sequence[MocShockCellMeasurement] = (),
  length_tolerance_m: float = 1.0e-6,
  position_tolerance_m: float = 1.0e-8,
) -> MocProductionShockCellFitRefinementMeasurement:
  case_values = tuple(cases)
  measurement_values = tuple(measurements)
  if len(case_values) != len(measurement_values):
    paired_count = min(len(case_values), len(measurement_values))
    case_values = case_values[:paired_count]
    measurement_values = measurement_values[:paired_count]
  ####
  lengths = tuple(
    measurement.axial_length_m for measurement in measurement_values
  )
  deltas = tuple(
    None
    if lengths[index] is None or lengths[index + 1] is None
    else abs(float(lengths[index + 1]) - float(lengths[index]))
    for index in range(len(lengths) - 1)
  )
  return MocProductionShockCellFitRefinementMeasurement(
    status=status,
    cases=case_values,
    measurements=measurement_values,
    closure_fingerprints=tuple(
      'unavailable'
      if case.fit.closure is None
      else moc_reflected_domain_global_physical_closure_fingerprint(
        case.fit.closure
      )
      for case in case_values
    ),
    source_band_fingerprints=tuple(
      'unavailable'
      if case.fit.closure is None or case.fit.closure.source_band is None
      else _source_fingerprint(case.fit.closure.source_band)
      for case in case_values
    ),
    shock_sample_counts=tuple(
      len(case.fit.fitted_shock_points_m) for case in case_values
    ),
    axial_lengths_m=tuple(
      measurement.axial_length_m for measurement in measurement_values
    ),
    axial_length_deltas_m=deltas,
    length_tolerance_m=length_tolerance_m,
    position_tolerance_m=position_tolerance_m,
    message=message,
  )
####


def measure_moc_production_shock_cell_fit_refinement(
  cases: Sequence[MocProductionShockCellFitRefinementCase],
  *,
  position_tolerance_m: float = 1.0e-8,
  length_tolerance_m: float = 1.0e-6,
  measurement_position_tolerance_m: float = 1.0e-10,
  measurement_axis_tolerance_m: float = 1.0e-10,
  measurement_area_tolerance_m2: float = 1.0e-9,
  measurement_mesh_vertex_tolerance_m: float = 1.0e-12,
) -> MocProductionShockCellFitRefinementMeasurement:
  """Audit independently produced shock-cell fits at increasing resolutions.

  A passing sequence proves only local solver/measurement consistency.  It
  does not compare against an observation and cannot authorize a production
  chain cell.
  """

  try:
    position_tolerance = float(position_tolerance_m)
    length_tolerance = float(length_tolerance_m)
    measurement_position_tolerance = float(measurement_position_tolerance_m)
    measurement_axis_tolerance = float(measurement_axis_tolerance_m)
    measurement_area_tolerance = float(measurement_area_tolerance_m2)
    measurement_mesh_vertex_tolerance = float(
      measurement_mesh_vertex_tolerance_m
    )
  except (TypeError, ValueError):
    return _failure(
      MocProductionShockCellFitRefinementStatus.INVALID_INPUT,
      'shock-cell fit refinement tolerances must be numeric',
    )
  ####
  if not all(
    isfinite(value) and value > 0.0
    for value in (
      position_tolerance,
      length_tolerance,
      measurement_position_tolerance,
      measurement_axis_tolerance,
      measurement_area_tolerance,
      measurement_mesh_vertex_tolerance,
    )
  ):
    return _failure(
      MocProductionShockCellFitRefinementStatus.INVALID_INPUT,
      'shock-cell fit refinement tolerances must be finite and positive',
    )
  ####
  try:
    case_values = tuple(cases)
  except TypeError:
    return _failure(
      MocProductionShockCellFitRefinementStatus.INVALID_INPUT,
      'cases must be an iterable of shock-cell fit refinement cases',
      length_tolerance_m=length_tolerance,
      position_tolerance_m=position_tolerance,
    )
  ####
  if len(case_values) < 2:
    return _failure(
      MocProductionShockCellFitRefinementStatus.RESOLUTION_FAILURE,
      'shock-cell fit refinement requires at least two cases',
      length_tolerance_m=length_tolerance,
      position_tolerance_m=position_tolerance,
    )
  ####
  if any(
    not isinstance(case, MocProductionShockCellFitRefinementCase)
    for case in case_values
  ):
    return _failure(
      MocProductionShockCellFitRefinementStatus.INVALID_INPUT,
      'cases must contain MocProductionShockCellFitRefinementCase values',
      length_tolerance_m=length_tolerance,
      position_tolerance_m=position_tolerance,
    )
  ####

  resolutions = tuple(case.resolution for case in case_values)
  resolution_order_verified = all(
    right > left for left, right in zip(resolutions, resolutions[1:])
  )
  if not resolution_order_verified:
    return _failure(
      MocProductionShockCellFitRefinementStatus.RESOLUTION_FAILURE,
      'shock-cell fit refinement requires strictly increasing resolutions',
      length_tolerance_m=length_tolerance,
      position_tolerance_m=position_tolerance,
    )
  ####

  fits = tuple(case.fit for case in case_values)
  case_fits_verified = all(fit.local_fit_verified for fit in fits)
  if not case_fits_verified:
    return _failure(
      MocProductionShockCellFitRefinementStatus.FIT_FAILURE,
      'every shock-cell fit must pass its local frontier/field/Euler gates',
      cases=case_values,
      measurements=tuple(
        measure_moc_production_shock_cell_fit(
          fit,
          position_tolerance_m=measurement_position_tolerance,
          axis_tolerance_m=measurement_axis_tolerance,
          area_tolerance_m2=measurement_area_tolerance,
          mesh_vertex_tolerance_m=measurement_mesh_vertex_tolerance,
        )
        for fit in fits
      ),
      length_tolerance_m=length_tolerance,
      position_tolerance_m=position_tolerance,
    )
  ####

  closures = tuple(fit.closure for fit in fits)
  if any(closure is None for closure in closures):
    return _failure(
      MocProductionShockCellFitRefinementStatus.SOURCE_FAILURE,
      'every local shock-cell fit must retain its exact global closure',
      cases=case_values,
      measurements=tuple(
        measure_moc_production_shock_cell_fit(
          fit,
          position_tolerance_m=measurement_position_tolerance,
          axis_tolerance_m=measurement_axis_tolerance,
          area_tolerance_m2=measurement_area_tolerance,
          mesh_vertex_tolerance_m=measurement_mesh_vertex_tolerance,
        )
        for fit in fits
      ),
      length_tolerance_m=length_tolerance,
      position_tolerance_m=position_tolerance,
    )
  ####
  resolved_closures = tuple(closure for closure in closures if closure is not None)
  source_fingerprints = tuple(
    '' if closure.source_band is None else _source_fingerprint(closure.source_band)
    for closure in resolved_closures
  )
  source_binding_verified = bool(
    source_fingerprints
    and all(source_fingerprint == source_fingerprints[0]
            for source_fingerprint in source_fingerprints)
  )
  if not source_binding_verified:
    return _failure(
      MocProductionShockCellFitRefinementStatus.SOURCE_FAILURE,
      'fit ladder cases must use one immutable upstream source band',
      cases=case_values,
      measurements=tuple(
        measure_moc_production_shock_cell_fit(
          fit,
          position_tolerance_m=measurement_position_tolerance,
          axis_tolerance_m=measurement_axis_tolerance,
          area_tolerance_m2=measurement_area_tolerance,
          mesh_vertex_tolerance_m=measurement_mesh_vertex_tolerance,
        )
        for fit in fits
      ),
      length_tolerance_m=length_tolerance,
      position_tolerance_m=position_tolerance,
    )
  ####

  closure_fingerprints = tuple(
    moc_reflected_domain_global_physical_closure_fingerprint(closure)
    for closure in resolved_closures
  )
  closure_resolution_identity_verified = (
    len(set(closure_fingerprints)) == len(closure_fingerprints)
  )
  placement_verified = bool(
    all(fit.start_x_m is not None and fit.end_x_m is not None for fit in fits)
    and all(fit.cell_index == fits[0].cell_index for fit in fits)
    and all(
      abs(float(fit.start_x_m) - float(fits[0].start_x_m))
      <= position_tolerance
      and abs(float(fit.end_x_m) - float(fits[0].end_x_m))
      <= position_tolerance
      for fit in fits
    )
  )
  if not placement_verified:
    return _failure(
      MocProductionShockCellFitRefinementStatus.PLACEMENT_FAILURE,
      'fit ladder cases must retain one common solver-owned axial interval and cell index',
      cases=case_values,
      measurements=tuple(
        measure_moc_production_shock_cell_fit(
          fit,
          position_tolerance_m=measurement_position_tolerance,
          axis_tolerance_m=measurement_axis_tolerance,
          area_tolerance_m2=measurement_area_tolerance,
          mesh_vertex_tolerance_m=measurement_mesh_vertex_tolerance,
        )
        for fit in fits
      ),
      length_tolerance_m=length_tolerance,
      position_tolerance_m=position_tolerance,
    )
  ####

  measurements = tuple(
    measure_moc_production_shock_cell_fit(
      fit,
      position_tolerance_m=measurement_position_tolerance,
      axis_tolerance_m=measurement_axis_tolerance,
      area_tolerance_m2=measurement_area_tolerance,
      mesh_vertex_tolerance_m=measurement_mesh_vertex_tolerance,
    )
    for fit in fits
  )
  measurements_verified = all(measurement.converged for measurement in measurements)
  if not measurements_verified:
    return _failure(
      MocProductionShockCellFitRefinementStatus.MEASUREMENT_FAILURE,
      'at least one solver-owned shock-cell fit failed independent measurement',
      cases=case_values,
      measurements=measurements,
      length_tolerance_m=length_tolerance,
      position_tolerance_m=position_tolerance,
    )
  ####

  shock_sample_counts = tuple(
    len(fit.fitted_shock_points_m) for fit in fits
  )
  shock_sample_growth_verified = all(
    right > left
    for left, right in zip(shock_sample_counts, shock_sample_counts[1:])
  )
  lengths = tuple(measurement.axial_length_m for measurement in measurements)
  lengths_finite_verified = bool(
    all(
      value is not None and isfinite(float(value)) and float(value) > 0.0
      for value in lengths
    )
  )
  deltas = tuple(
    None
    if lengths[index] is None or lengths[index + 1] is None
    else abs(float(lengths[index + 1]) - float(lengths[index]))
    for index in range(len(lengths) - 1)
  )
  length_resolution_sequence_verified = bool(
    lengths_finite_verified
    and all(delta is not None and isfinite(float(delta)) for delta in deltas)
    and all(
      float(deltas[index]) <= float(deltas[index - 1]) + length_tolerance
      for index in range(1, len(deltas))
    )
  )
  physical_closure_verified = all(
    closure.physical_closure_verified for closure in resolved_closures
  )
  fidelity_isolation_verified = all(
    fit.chain_promotion_blocked and not fit.production_claim_allowed
    for fit in fits
  )
  common = dict(
    cases=case_values,
    measurements=measurements,
    closure_fingerprints=closure_fingerprints,
    source_band_fingerprints=source_fingerprints,
    shock_sample_counts=shock_sample_counts,
    axial_lengths_m=lengths,
    axial_length_deltas_m=deltas,
    resolution_order_verified=resolution_order_verified,
    case_fits_verified=case_fits_verified,
    source_binding_verified=source_binding_verified,
    closure_resolution_identity_verified=closure_resolution_identity_verified,
    placement_verified=placement_verified,
    measurements_verified=measurements_verified,
    shock_sample_growth_verified=shock_sample_growth_verified,
    lengths_finite_verified=lengths_finite_verified,
    length_resolution_sequence_verified=length_resolution_sequence_verified,
    physical_closure_verified=physical_closure_verified,
    fidelity_isolation_verified=fidelity_isolation_verified,
    length_tolerance_m=length_tolerance,
    position_tolerance_m=position_tolerance,
  )
  if not closure_resolution_identity_verified:
    status = MocProductionShockCellFitRefinementStatus.SOURCE_FAILURE
    message = (
      'fit ladder reused an identical closure fingerprint at multiple '
      'declared resolutions'
    )
  elif not shock_sample_growth_verified:
    status = MocProductionShockCellFitRefinementStatus.RESOLUTION_FAILURE
    message = 'solver-owned fitted shock sample count did not increase with resolution'
  elif not length_resolution_sequence_verified:
    status = MocProductionShockCellFitRefinementStatus.LENGTH_STABILITY_FAILURE
    message = (
      'solver-owned fit lengths were finite but did not form a non-increasing '
      'resolution-difference sequence'
    )
  elif not physical_closure_verified:
    status = MocProductionShockCellFitRefinementStatus.FIT_FAILURE
    message = 'one or more fit closures did not pass the local physical-closure gate'
  elif not fidelity_isolation_verified:
    status = MocProductionShockCellFitRefinementStatus.FIT_FAILURE
    message = 'fit ladder weakened its research-only promotion boundary'
  else:
    status = MocProductionShockCellFitRefinementStatus.CONVERGED_LOCAL_FIT_REFINEMENT
    message = (
      'solver-generated shock-cell fits passed independent geometry and '
      'resolution evidence; physical length acceptance and external comparison '
      'remain separate gates'
    )
  ####
  return MocProductionShockCellFitRefinementMeasurement(
    status=status,
    claim_status=(
      'independent-production-shock-cell-fit-refinement; '
      'local-research-only; physical-length-not-accepted'
    ),
    message=message,
    **common,
  )
####


@dataclass(frozen=True, slots=True)
class MocProductionShockCellFitRefinementRun:
  """Fresh global-closure execution followed by fit-ladder evidence."""

  source_band: MocReflectedDomainAlternatingSourceResult
  requested_resolutions: tuple[int, ...]
  closures: tuple[MocReflectedDomainGlobalPhysicalClosureResult, ...]
  cases: tuple[MocProductionShockCellFitRefinementCase, ...]
  measurement: MocProductionShockCellFitRefinementMeasurement
  source_band_fingerprint: str
  configuration: tuple[tuple[str, Any], ...]
  configuration_fingerprint: str
  start_x_m: float
  end_x_m: float | None
  fresh_solver_invocation_verified: bool
  local_physical_closure_verified: bool
  fidelity_isolation_verified: bool
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.source_band,
      MocReflectedDomainAlternatingSourceResult,
    ):
      raise TypeError(
        'source_band must be a MocReflectedDomainAlternatingSourceResult'
      )
    ####
    resolutions = tuple(self.requested_resolutions)
    if not resolutions:
      raise ValueError('requested_resolutions must not be empty')
    ####
    if any(
      isinstance(resolution, bool)
      or not isinstance(resolution, int)
      or resolution < 1
      for resolution in resolutions
    ):
      raise ValueError('requested_resolutions must contain positive integers')
    ####
    closures = tuple(self.closures)
    if len(closures) != len(resolutions):
      raise ValueError('closures must match requested_resolutions')
    ####
    if any(
      not isinstance(closure, MocReflectedDomainGlobalPhysicalClosureResult)
      for closure in closures
    ):
      raise TypeError(
        'closures must contain MocReflectedDomainGlobalPhysicalClosureResult values'
      )
    ####
    cases = tuple(self.cases)
    if any(
      not isinstance(case, MocProductionShockCellFitRefinementCase)
      for case in cases
    ):
      raise TypeError(
        'cases must contain MocProductionShockCellFitRefinementCase values'
      )
    ####
    if not isinstance(
      self.measurement,
      MocProductionShockCellFitRefinementMeasurement,
    ):
      raise TypeError(
        'measurement must be a MocProductionShockCellFitRefinementMeasurement'
      )
    ####
    if self.measurement.cases and self.measurement.cases != cases:
      raise ValueError('measurement cases must match retained fit cases')
    ####
    object.__setattr__(self, 'requested_resolutions', resolutions)
    object.__setattr__(self, 'closures', closures)
    object.__setattr__(self, 'cases', cases)
    start = float(self.start_x_m)
    if not isfinite(start):
      raise ValueError('start_x_m must be finite')
    ####
    object.__setattr__(self, 'start_x_m', start)
    if self.end_x_m is not None:
      end = float(self.end_x_m)
      if not isfinite(end) or end <= start:
        raise ValueError('end_x_m must be finite and greater than start_x_m')
      ####
      object.__setattr__(self, 'end_x_m', end)
    ####
    for name in ('source_band_fingerprint', 'configuration_fingerprint'):
      value = str(getattr(self, name))
      if not value:
        raise ValueError(f'{name} must be non-empty')
      ####
      object.__setattr__(self, name, value)
    ####
    configuration = tuple(self.configuration)
    if any(
      not isinstance(item, tuple)
      or len(item) != 2
      or not isinstance(item[0], str)
      for item in configuration
    ):
      raise ValueError('configuration must contain (name, value) pairs')
    ####
    object.__setattr__(self, 'configuration', configuration)
    for name in (
      'fresh_solver_invocation_verified',
      'local_physical_closure_verified',
      'fidelity_isolation_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.measurement.converged
  ####

  @property
  def local_consistency_verified(self) -> bool:
    return bool(
      self.measurement.local_consistency_verified
      and self.fresh_solver_invocation_verified
      and self.local_physical_closure_verified
      and self.fidelity_isolation_verified
    )
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    return all(case.fit.chain_promotion_blocked for case in self.cases)
  ####

  @property
  def production_claim_allowed(self) -> bool:
    return False
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.measurement.status.value,
      'operator_id': MOC_PRODUCTION_SHOCK_CELL_FIT_REFINEMENT_RUN_OPERATOR_ID,
      'converged': self.converged,
      'local_consistency_verified': self.local_consistency_verified,
      'source_band_fingerprint': self.source_band_fingerprint,
      'configuration': dict(self.configuration),
      'configuration_fingerprint': self.configuration_fingerprint,
      'requested_resolutions': list(self.requested_resolutions),
      'start_x_m': self.start_x_m,
      'end_x_m': self.end_x_m,
      'closures': [
        {
          'resolution': resolution,
          'status': closure.status.value,
          'converged': closure.converged,
          'physical_closure_verified': closure.physical_closure_verified,
          'global_euler_retained': closure.global_euler is not None,
          'downstream_boundary_model': closure.downstream_boundary_model,
          'downstream_boundary_closure_verified': (
            closure.downstream_boundary_closure_verified
          ),
          'production_claim_allowed': closure.production_claim_allowed,
        }
        for resolution, closure in zip(
          self.requested_resolutions,
          self.closures,
          strict=True,
        )
      ],
      'cases': [case.as_report() for case in self.measurement.cases],
      'measurement': self.measurement.as_report(),
      'checks': {
        'fresh_solver_invocation_verified': (
          self.fresh_solver_invocation_verified
        ),
        'local_physical_closure_verified': (
          self.local_physical_closure_verified
        ),
        'fidelity_isolation_verified': self.fidelity_isolation_verified,
        'chain_promotion_blocked': self.chain_promotion_blocked,
        'production_claim_allowed': self.production_claim_allowed,
      },
      'external_validation_verified': False,
      'physical_length_accepted': False,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'claim_status': (
        'fresh-production-shock-cell-fit-refinement; '
        'local-research-only; physical-length-not-accepted'
      ),
      'message': self.message,
    }
  ####
####


def run_moc_production_shock_cell_fit_refinement(
  source_band: MocReflectedDomainAlternatingSourceResult,
  resolutions: Sequence[int],
  *,
  start_x_m: float,
  end_x_m: float | None = None,
  end_margin_m: float = 0.05,
  cell_index: int = 1,
  incoming_handoff: Sequence[MocChainBoundarySample] | None = None,
  length_tolerance_m: float = 1.0e-6,
  position_tolerance_m: float = 1.0e-8,
  measurement_position_tolerance_m: float = 1.0e-10,
  measurement_axis_tolerance_m: float = 1.0e-10,
  measurement_area_tolerance_m2: float = 1.0e-9,
  measurement_mesh_vertex_tolerance_m: float = 1.0e-12,
  **solver_options: Any,
) -> MocProductionShockCellFitRefinementRun:
  """Freshly solve and audit a solver-generated shock-cell fit ladder.

  The existing global-Euler refinement runner owns the closure resolution
  ladder.  This runner consumes only its retained physically verified fields,
  fits the same solver-owned axial interval at every resolution, and then
  invokes the independent fit-refinement measurement.  It never falls back to
  a caller-supplied shock path or promotes the resulting length.
  """

  if not isinstance(source_band, MocReflectedDomainAlternatingSourceResult):
    raise TypeError(
      'source_band must be a MocReflectedDomainAlternatingSourceResult'
    )
  ####
  try:
    requested_resolutions = tuple(resolutions)
  except TypeError as error:
    raise ValueError(
      'resolutions must be an iterable of positive integers'
    ) from error
  ####
  if not requested_resolutions:
    raise ValueError('resolutions must not be empty')
  ####
  if any(
    isinstance(resolution, bool)
    or not isinstance(resolution, int)
    or resolution < 1
    for resolution in requested_resolutions
  ):
    raise ValueError('resolutions must contain positive integers')
  ####
  start = float(start_x_m)
  margin = float(end_margin_m)
  if not isfinite(start):
    raise ValueError('start_x_m must be finite')
  ####
  if not isfinite(margin) or margin < 0.0:
    raise ValueError('end_margin_m must be finite and nonnegative')
  ####
  if isinstance(cell_index, bool) or not isinstance(cell_index, int) or cell_index < 1:
    raise ValueError('cell_index must be a positive integer')
  ####
  resolved_handoff = None if incoming_handoff is None else tuple(incoming_handoff)
  if resolved_handoff is not None and any(
    not isinstance(sample, MocChainBoundarySample)
    for sample in resolved_handoff
  ):
    raise TypeError('incoming_handoff must contain MocChainBoundarySample values')
  ####
  source_fingerprint = _source_fingerprint(source_band)
  configuration_payload: dict[str, Any] = {
    'operator_id': MOC_PRODUCTION_SHOCK_CELL_FIT_REFINEMENT_RUN_OPERATOR_ID,
    'source_band_fingerprint': source_fingerprint,
    'requested_resolutions': list(requested_resolutions),
    'start_x_m': start,
    'end_x_m': None if end_x_m is None else float(end_x_m),
    'end_margin_m': margin,
    'cell_index': cell_index,
    'incoming_handoff': (
      None
      if resolved_handoff is None
      else [_boundary_sample_payload(sample) for sample in resolved_handoff]
    ),
    'length_tolerance_m': length_tolerance_m,
    'position_tolerance_m': position_tolerance_m,
    'measurement_position_tolerance_m': measurement_position_tolerance_m,
    'measurement_axis_tolerance_m': measurement_axis_tolerance_m,
    'measurement_area_tolerance_m2': measurement_area_tolerance_m2,
    'measurement_mesh_vertex_tolerance_m': measurement_mesh_vertex_tolerance_m,
    'solver_options': solver_options,
  }
  configuration = tuple(
    (name, configuration_payload[name])
    for name in sorted(configuration_payload)
  )
  configuration_fingerprint = _payload_fingerprint(configuration_payload)

  global_run = run_moc_reflected_domain_global_euler_shock_boundary_refinement(
    source_band,
    requested_resolutions,
    incoming_handoff=resolved_handoff,
    **solver_options,
  )
  closures = tuple(global_run.closures)
  local_physical_closure_verified = bool(
    closures and all(closure.physical_closure_verified for closure in closures)
  )
  missing_resolutions = tuple(
    resolution
    for resolution, closure in zip(requested_resolutions, closures, strict=True)
    if closure.global_euler is None
    or closure.global_euler.physical_field is None
    or closure.global_euler.physical_field.field is None
  )
  if missing_resolutions:
    measurement = MocProductionShockCellFitRefinementMeasurement(
      status=MocProductionShockCellFitRefinementStatus.FIT_FAILURE,
      message=(
        'fresh global closure retained no physical field for fit resolution(s) '
        f'{missing_resolutions}; no lower-fidelity fit was attempted'
      ),
    )
    return MocProductionShockCellFitRefinementRun(
      source_band=source_band,
      requested_resolutions=requested_resolutions,
      closures=closures,
      cases=(),
      measurement=measurement,
      source_band_fingerprint=source_fingerprint,
      configuration=configuration,
      configuration_fingerprint=configuration_fingerprint,
      start_x_m=start,
      end_x_m=None if end_x_m is None else float(end_x_m),
      fresh_solver_invocation_verified=(
        global_run.fresh_solver_invocation_verified
      ),
      local_physical_closure_verified=local_physical_closure_verified,
      fidelity_isolation_verified=bool(
        closures
        and all(
          closure.chain_promotion_blocked
          and not closure.production_claim_allowed
          for closure in closures
        )
      ),
      message=measurement.message,
    )
  ####

  fields = tuple(
    closure.global_euler.physical_field.field
    for closure in closures
    if closure.global_euler is not None
    and closure.global_euler.physical_field is not None
    and closure.global_euler.physical_field.field is not None
  )
  resolved_end = (
    max(field.ambient_boundary_points_m[-1][0] for field in fields) + margin
    if end_x_m is None
    else float(end_x_m)
  )
  if not isfinite(resolved_end) or resolved_end <= start:
    raise ValueError('resolved end_x_m must be finite and greater than start_x_m')
  ####
  cases = tuple(
    MocProductionShockCellFitRefinementCase(
      resolution=resolution,
      fit=fit_reflected_domain_production_shock_cell(
        closure,
        start_x_m=start,
        end_x_m=resolved_end,
        cell_index=cell_index,
        incoming_frontier=closure.incoming_handoff,
        position_tolerance_m=position_tolerance_m,
      ),
    )
    for resolution, closure in zip(requested_resolutions, closures, strict=True)
  )
  measurement = measure_moc_production_shock_cell_fit_refinement(
    cases,
    position_tolerance_m=position_tolerance_m,
    length_tolerance_m=length_tolerance_m,
    measurement_position_tolerance_m=measurement_position_tolerance_m,
    measurement_axis_tolerance_m=measurement_axis_tolerance_m,
    measurement_area_tolerance_m2=measurement_area_tolerance_m2,
    measurement_mesh_vertex_tolerance_m=measurement_mesh_vertex_tolerance_m,
  )
  fidelity_isolation_verified = bool(
    cases
    and all(
      case.fit.chain_promotion_blocked
      and not case.fit.production_claim_allowed
      for case in cases
    )
  )
  return MocProductionShockCellFitRefinementRun(
    source_band=source_band,
    requested_resolutions=requested_resolutions,
    closures=closures,
    cases=cases,
    measurement=measurement,
    source_band_fingerprint=source_fingerprint,
    configuration=configuration,
    configuration_fingerprint=configuration_fingerprint,
    start_x_m=start,
    end_x_m=resolved_end,
    fresh_solver_invocation_verified=global_run.fresh_solver_invocation_verified,
    local_physical_closure_verified=local_physical_closure_verified,
    fidelity_isolation_verified=fidelity_isolation_verified,
    message=(
      'fresh global-closure fit ladder executed and independently measured; '
      'physical length acceptance and external validation remain pending'
    ),
  )
####


class MocProductionShockCellContinuedChainStatus(str, Enum):
  """Outcome of a fresh exact-Euler continued-chain evidence run."""

  CONVERGED_LOCAL_CONTINUED_CHAIN = (
    'converged_local_production_shock_cell_continued_chain'
  )
  INVALID_INPUT = 'invalid_input'
  SEED_FAILURE = 'production_shock_cell_continued_chain_seed_failure'
  CHAIN_FAILURE = 'production_shock_cell_continued_chain_solver_failure'
  MEASUREMENT_FAILURE = (
    'production_shock_cell_continued_chain_measurement_failure'
  )
####


def _continued_chain_policy_report(
  policy: MocChainContinuationPolicy,
) -> dict[str, Any]:
  """Serialize the state-carry policy without losing its fidelity boundary."""

  return {
    'max_cells': policy.max_cells,
    'max_axial_distance_m': policy.max_axial_distance_m,
    'position_tolerance_m': policy.position_tolerance_m,
    'allowed_fidelities': [
      getattr(fidelity, 'value', str(fidelity))
      for fidelity in policy.allowed_fidelities
    ],
    'require_state_carry': policy.require_state_carry,
    'state_tolerance': policy.state_tolerance,
  }
####


@dataclass(frozen=True, slots=True)
class MocProductionShockCellContinuedChainRun:
  """Typed evidence for fresh solver-owned continued shock-cell fields.

  The runner exposes the existing fresh-source global-Euler chain planner
  through the production validation surface.  A converged result is local
  research evidence only: canonical reflected/free-boundary closure,
  accepted physical lengths, external comparison, and production promotion
  remain separate gates.
  """

  source_band: MocReflectedDomainAlternatingSourceResult
  seed_closure: MocReflectedDomainGlobalPhysicalClosureResult | None
  seed_global_euler: MocReflectedDomainGlobalEulerShockBoundaryResult | None
  planner: MocChainPlannerResult | None
  reference: MocGlobalEulerContinuedChainReference
  policy: MocChainContinuationPolicy
  status: MocProductionShockCellContinuedChainStatus
  source_band_fingerprint: str
  configuration: tuple[tuple[str, Any], ...]
  configuration_fingerprint: str
  start_x_m: float
  end_x_m: float
  fresh_solver_invocation_verified: bool
  seed_measurement_verified: bool
  continued_chain_measurement_verified: bool
  intercell_bridge_verified: bool
  fidelity_isolation_verified: bool
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.source_band,
      MocReflectedDomainAlternatingSourceResult,
    ):
      raise TypeError(
        'source_band must be a MocReflectedDomainAlternatingSourceResult'
      )
    ####
    for name, expected_type in (
      (
        'seed_closure',
        MocReflectedDomainGlobalPhysicalClosureResult,
      ),
      ('seed_global_euler', MocReflectedDomainGlobalEulerShockBoundaryResult),
      ('planner', MocChainPlannerResult),
    ):
      value = getattr(self, name)
      if value is not None and not isinstance(value, expected_type):
        raise TypeError(f'{name} must be a {expected_type.__name__} or None')
      ####
    ####
    if (
      self.seed_closure is not None
      and self.seed_global_euler is not None
      and self.seed_closure.global_euler is not self.seed_global_euler
    ):
      raise ValueError(
        'seed_global_euler must be the exact global-Euler result retained by '
        'seed_closure'
      )
    ####
    if self.planner is not None and self.seed_global_euler is None:
      raise ValueError('planner requires a retained seed_global_euler result')
    ####
    if not isinstance(self.reference, MocGlobalEulerContinuedChainReference):
      raise TypeError(
        'reference must be a MocGlobalEulerContinuedChainReference'
      )
    ####
    if not isinstance(self.policy, MocChainContinuationPolicy):
      raise TypeError('policy must be a MocChainContinuationPolicy')
    ####
    if not isinstance(
      self.status,
      MocProductionShockCellContinuedChainStatus,
    ):
      raise TypeError(
        'status must be a MocProductionShockCellContinuedChainStatus'
      )
    ####
    expected_source_fingerprint = _source_fingerprint(self.source_band)
    if self.source_band_fingerprint != expected_source_fingerprint:
      raise ValueError('source_band_fingerprint does not match source_band')
    ####
    configuration = tuple(self.configuration)
    if any(
      not isinstance(item, tuple)
      or len(item) != 2
      or not isinstance(item[0], str)
      for item in configuration
    ):
      raise ValueError('configuration must contain (name, value) pairs')
    ####
    object.__setattr__(self, 'configuration', configuration)
    configuration_fingerprint = str(self.configuration_fingerprint)
    if not configuration_fingerprint:
      raise ValueError('configuration_fingerprint must be non-empty')
    ####
    object.__setattr__(self, 'configuration_fingerprint', configuration_fingerprint)
    start = float(self.start_x_m)
    end = float(self.end_x_m)
    if not isfinite(start) or not isfinite(end) or end <= start:
      raise ValueError('continued-chain axial bounds must be finite and ordered')
    ####
    object.__setattr__(self, 'start_x_m', start)
    object.__setattr__(self, 'end_x_m', end)
    for name in (
      'fresh_solver_invocation_verified',
      'seed_measurement_verified',
      'continued_chain_measurement_verified',
      'intercell_bridge_verified',
      'fidelity_isolation_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def resolved(self) -> bool:
    return self.status is (
      MocProductionShockCellContinuedChainStatus
      .CONVERGED_LOCAL_CONTINUED_CHAIN
    )
  ####

  @property
  def research_physical_cell_count(self) -> int:
    if self.planner is None:
      return 0
    ####
    value = self.planner.diagnostics.get(
      'global_euler_continued_chain_research_physical_cell_count',
      max(0, self.planner.chain.cell_count - 1),
    )
    try:
      return max(0, int(value))
    except (TypeError, ValueError):
      return 0
    ####
  ####

  @property
  def local_consistency_verified(self) -> bool:
    return bool(
      self.resolved
      and self.seed_closure is not None
      and self.seed_closure.physical_closure_verified
      and self.seed_global_euler is not None
      and self.planner is not None
      and self.planner.resolved
      and self.planner.handoff_links_verified is True
      and self.fresh_solver_invocation_verified
      and self.seed_measurement_verified
      and self.continued_chain_measurement_verified
      and self.intercell_bridge_verified
      and self.fidelity_isolation_verified
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
    )
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    return True
  ####

  @property
  def production_claim_allowed(self) -> bool:
    return False
  ####

  def as_report(self) -> dict[str, Any]:
    diagnostics = (
      {} if self.planner is None else dict(self.planner.diagnostics)
    )
    return {
      'status': self.status.value,
      'operator_id': MOC_PRODUCTION_SHOCK_CELL_CONTINUED_CHAIN_RUN_OPERATOR_ID,
      'resolved': self.resolved,
      'local_consistency_verified': self.local_consistency_verified,
      'source_band_fingerprint': self.source_band_fingerprint,
      'configuration': dict(self.configuration),
      'configuration_fingerprint': self.configuration_fingerprint,
      'start_x_m': self.start_x_m,
      'end_x_m': self.end_x_m,
      'research_physical_cell_count': self.research_physical_cell_count,
      'reference': self.reference.as_report(),
      'policy': _continued_chain_policy_report(self.policy),
      'seed_closure': (
        None if self.seed_closure is None else self.seed_closure.as_report()
      ),
      'seed_global_euler': (
        None
        if self.seed_global_euler is None
        else self.seed_global_euler.as_report()
      ),
      'planner': None if self.planner is None else self.planner.as_report(),
      'planner_diagnostics': diagnostics,
      'checks': {
        'fresh_solver_invocation_verified': (
          self.fresh_solver_invocation_verified
        ),
        'seed_measurement_verified': self.seed_measurement_verified,
        'continued_chain_measurement_verified': (
          self.continued_chain_measurement_verified
        ),
        'intercell_bridge_verified': self.intercell_bridge_verified,
        'fidelity_isolation_verified': self.fidelity_isolation_verified,
        'chain_promotion_blocked': self.chain_promotion_blocked,
        'production_claim_allowed': self.production_claim_allowed,
      },
      'canonical_free_boundary_verified': False,
      'canonical_euler_verified': False,
      'physical_length_accepted': False,
      'external_validation_verified': False,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'claim_status': (
        'fresh-global-euler-continued-chain; local-research-only; '
        'physical-length-not-accepted'
      ),
      'message': self.message,
    }
  ####
####


def run_moc_production_shock_cell_continued_chain(
  source_band: MocReflectedDomainAlternatingSourceResult,
  *,
  start_x_m: float,
  end_x_m: float,
  reference: MocGlobalEulerContinuedChainReference | None = None,
  policy: MocChainContinuationPolicy | None = None,
  incoming_handoff: Sequence[MocChainBoundarySample] | None = None,
) -> MocProductionShockCellContinuedChainRun:
  """Freshly seed and audit a solver-owned continued shock-cell chain.

  The seed is re-solved from the immutable source band using the exact global
  physical-closure path.  Each later cell is rebuilt by the existing fresh
  source-band/global-Euler planner, which preserves explicit intercell bridge
  evidence and never falls back to a lower-fidelity chain.  The result is
  intentionally below canonical and production promotion.
  """

  if not isinstance(source_band, MocReflectedDomainAlternatingSourceResult):
    raise TypeError(
      'source_band must be a MocReflectedDomainAlternatingSourceResult'
    )
  ####
  resolved_reference = (
    MocGlobalEulerContinuedChainReference()
    if reference is None else reference
  )
  if not isinstance(
    resolved_reference,
    MocGlobalEulerContinuedChainReference,
  ):
    raise TypeError(
      'reference must be a MocGlobalEulerContinuedChainReference or None'
    )
  ####
  if resolved_reference.total_cell_count < 2:
    raise ValueError(
      'continued-chain evidence requires at least one cell beyond the seed'
    )
  ####
  resolved_policy = (
    MocChainContinuationPolicy(
      max_cells=resolved_reference.total_cell_count,
      require_state_carry=True,
    )
    if policy is None else policy
  )
  if not isinstance(resolved_policy, MocChainContinuationPolicy):
    raise TypeError('policy must be a MocChainContinuationPolicy or None')
  ####
  start = float(start_x_m)
  end = float(end_x_m)
  if not isfinite(start) or not isfinite(end) or end <= start:
    raise ValueError('start_x_m and end_x_m must be finite and ordered')
  ####
  resolved_handoff = (
    tuple(source_band.incoming_handoff)
    if incoming_handoff is None else tuple(incoming_handoff)
  )
  if any(
    not isinstance(sample, MocChainBoundarySample)
    for sample in resolved_handoff
  ):
    raise TypeError('incoming_handoff must contain MocChainBoundarySample values')
  ####
  if resolved_handoff != source_band.incoming_handoff:
    raise ValueError(
      'incoming_handoff must exactly match the source-band handoff'
    )
  ####
  source_fingerprint = _source_fingerprint(source_band)
  configuration_payload: dict[str, Any] = {
    'operator_id': MOC_PRODUCTION_SHOCK_CELL_CONTINUED_CHAIN_RUN_OPERATOR_ID,
    'source_band_fingerprint': source_fingerprint,
    'start_x_m': start,
    'end_x_m': end,
    'incoming_handoff': [
      _boundary_sample_payload(sample) for sample in resolved_handoff
    ],
    'reference': resolved_reference.as_report(),
    'policy': _continued_chain_policy_report(resolved_policy),
  }
  configuration = tuple(
    (name, configuration_payload[name])
    for name in sorted(configuration_payload)
  )
  configuration_fingerprint = _payload_fingerprint(configuration_payload)

  def build_run(
    *,
    status: MocProductionShockCellContinuedChainStatus,
    seed_closure: MocReflectedDomainGlobalPhysicalClosureResult | None,
    seed_global_euler: MocReflectedDomainGlobalEulerShockBoundaryResult | None,
    planner: MocChainPlannerResult | None,
    fresh_solver_invocation_verified: bool,
    seed_measurement_verified: bool,
    continued_chain_measurement_verified: bool,
    intercell_bridge_verified: bool,
    fidelity_isolation_verified: bool,
    message: str,
  ) -> MocProductionShockCellContinuedChainRun:
    return MocProductionShockCellContinuedChainRun(
      source_band=source_band,
      seed_closure=seed_closure,
      seed_global_euler=seed_global_euler,
      planner=planner,
      reference=resolved_reference,
      policy=resolved_policy,
      status=status,
      source_band_fingerprint=source_fingerprint,
      configuration=configuration,
      configuration_fingerprint=configuration_fingerprint,
      start_x_m=start,
      end_x_m=end,
      fresh_solver_invocation_verified=fresh_solver_invocation_verified,
      seed_measurement_verified=seed_measurement_verified,
      continued_chain_measurement_verified=continued_chain_measurement_verified,
      intercell_bridge_verified=intercell_bridge_verified,
      fidelity_isolation_verified=fidelity_isolation_verified,
      message=message,
    )
  ####

  try:
    seed_closure = solve_reflected_domain_global_physical_closure(
      source_band,
      outer_source_indices=resolved_reference.outer_source_indices,
      target_centerline_indices=resolved_reference.target_centerline_indices,
      compression_amplitude_lower_rad=(
        resolved_reference.compression_amplitude_lower_rad
      ),
      compression_amplitude_upper_rad=(
        resolved_reference.compression_amplitude_upper_rad
      ),
      compression_envelope_skews=resolved_reference.compression_envelope_skews,
      closure_tolerance_m=resolved_reference.closure_tolerance_m,
      incoming_handoff=resolved_handoff,
      sample_count=resolved_reference.sample_count,
      branch=resolved_reference.branch,
      position_tolerance_m=resolved_reference.position_tolerance_m,
      invariant_tolerance=resolved_reference.invariant_tolerance,
      attachment_pressure_tolerance=(
        resolved_reference.attachment_pressure_tolerance
      ),
      pressure_tolerance=resolved_reference.pressure_tolerance,
      tangent_tolerance=resolved_reference.tangent_tolerance,
      shock_angle_tolerance_rad=resolved_reference.shock_angle_tolerance_rad,
      euler_reconciliation_shock_angle_tolerance_rad=(
        resolved_reference.euler_reconciliation_shock_angle_tolerance_rad
      ),
      euler_reconciliation_residual_tolerance=(
        resolved_reference.euler_reconciliation_residual_tolerance
      ),
      maximum_segment_iterations=resolved_reference.maximum_segment_iterations,
      maximum_boundary_iterations=resolved_reference.maximum_boundary_iterations,
      maximum_shooting_iterations=resolved_reference.maximum_shooting_iterations,
      maximum_bracket_scan_samples=resolved_reference.maximum_bracket_scan_samples,
      maximum_attempts=resolved_reference.maximum_attempts,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return build_run(
      status=MocProductionShockCellContinuedChainStatus.SEED_FAILURE,
      seed_closure=None,
      seed_global_euler=None,
      planner=None,
      fresh_solver_invocation_verified=True,
      seed_measurement_verified=False,
      continued_chain_measurement_verified=False,
      intercell_bridge_verified=False,
      fidelity_isolation_verified=True,
      message=f'fresh continued-chain seed solve raised: {error}',
    )
  ####

  seed_global_euler = seed_closure.global_euler
  if (
    not seed_closure.physical_closure_verified
    or seed_global_euler is None
    or seed_global_euler.physical_field is None
    or seed_global_euler.physical_field.field is None
  ):
    return build_run(
      status=MocProductionShockCellContinuedChainStatus.SEED_FAILURE,
      seed_closure=seed_closure,
      seed_global_euler=seed_global_euler,
      planner=None,
      fresh_solver_invocation_verified=True,
      seed_measurement_verified=False,
      continued_chain_measurement_verified=False,
      intercell_bridge_verified=False,
      fidelity_isolation_verified=bool(
        seed_closure.chain_promotion_blocked
        and not seed_closure.production_claim_allowed
      ),
      message=(
        'fresh continued-chain seed retained no locally verified global '
        f'physical field: {seed_closure.message}'
      ),
    )
  ####

  try:
    planner = plan_reflected_domain_global_euler_continued_chain(
      seed_global_euler,
      start_x_m=start,
      end_x_m=end,
      reference=resolved_reference,
      policy=resolved_policy,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return build_run(
      status=MocProductionShockCellContinuedChainStatus.CHAIN_FAILURE,
      seed_closure=seed_closure,
      seed_global_euler=seed_global_euler,
      planner=None,
      fresh_solver_invocation_verified=True,
      seed_measurement_verified=True,
      continued_chain_measurement_verified=False,
      intercell_bridge_verified=False,
      fidelity_isolation_verified=True,
      message=f'fresh continued-chain planner raised: {error}',
    )
  ####

  diagnostics = dict(planner.diagnostics)
  seed_measurement = diagnostics.get(
    'global_euler_continued_chain_source_measurement'
  )
  seed_checks = (
    {} if not isinstance(seed_measurement, dict)
    else seed_measurement.get('checks', {})
  )
  seed_measurement_verified = bool(
    isinstance(seed_measurement, dict)
    and seed_measurement.get('status') == 'converged'
    and isinstance(seed_checks, dict)
    and seed_checks.get('incoming_handoff_verified') is True
    and seed_checks.get('physical_closure_verified') is True
    and seed_checks.get('chain_promotion_blocked') is True
    and seed_checks.get('production_claim_allowed') is False
  )
  chain_measurement = diagnostics.get(
    'global_euler_continued_chain_independent_measurement'
  )
  planner_measurement = diagnostics.get(
    'global_euler_continued_chain_planner_measurement'
  )
  continued_chain_measurement_verified = bool(
    diagnostics.get('global_euler_continued_chain_audit_accepted') is True
    and isinstance(chain_measurement, dict)
    and chain_measurement.get('status') == 'converged'
    and isinstance(planner_measurement, dict)
    and planner_measurement.get('status') == 'converged'
  )
  intercell_bridge_report = (
    {} if not isinstance(chain_measurement, dict)
    else chain_measurement.get('intercell_bridges', {})
  )
  intercell_bridge_verified = bool(
    isinstance(intercell_bridge_report, dict)
    and int(intercell_bridge_report.get('count', 0)) > 0
    and intercell_bridge_report.get('verified') is True
  )
  field_reports = diagnostics.get(
    'global_euler_continued_chain_global_euler_fields',
    (),
  )
  fidelity_isolation_verified = bool(
    planner.production_claim_allowed is False
    and diagnostics.get('chain_promotion_blocked') is True
    and diagnostics.get('production_claim_allowed') is False
    and all(
      isinstance(report, dict)
      and report.get('chain_promotion_blocked') is True
      and report.get('production_claim_allowed') is False
      for report in field_reports
    )
  )
  if not planner.resolved:
    status = MocProductionShockCellContinuedChainStatus.CHAIN_FAILURE
    message = (
      'fresh continued-chain planner returned an unresolved chain; '
      'no physical endpoint or lower-fidelity fallback was inferred'
    )
  elif not (
    seed_measurement_verified
    and continued_chain_measurement_verified
    and intercell_bridge_verified
  ):
    status = MocProductionShockCellContinuedChainStatus.MEASUREMENT_FAILURE
    message = (
      'fresh continued-chain fields were retained, but the independent '
      'chain/bridge measurement did not pass all local gates'
    )
  elif not fidelity_isolation_verified:
    status = MocProductionShockCellContinuedChainStatus.MEASUREMENT_FAILURE
    message = 'continued-chain evidence weakened its research-only promotion boundary'
  else:
    status = MocProductionShockCellContinuedChainStatus.CONVERGED_LOCAL_CONTINUED_CHAIN
    message = (
      'fresh global-Euler continued-chain fields passed independent handoff, '
      'fresh-domain, and intercell-bridge audits; physical length acceptance '
      'and external comparison remain separate gates'
    )
  ####
  return build_run(
    status=status,
    seed_closure=seed_closure,
    seed_global_euler=seed_global_euler,
    planner=planner,
    fresh_solver_invocation_verified=True,
    seed_measurement_verified=seed_measurement_verified,
    continued_chain_measurement_verified=continued_chain_measurement_verified,
    intercell_bridge_verified=intercell_bridge_verified,
    fidelity_isolation_verified=fidelity_isolation_verified,
    message=message,
  )
####
