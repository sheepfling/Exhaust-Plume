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

from exhaust_plume.models.moc.global_physical_closure import (
  MocProductionShockCellFitResult,
  moc_reflected_domain_global_physical_closure_fingerprint,
)
from exhaust_plume.validation.moc_measurements import (
  MocShockCellMeasurement,
  measure_moc_production_shock_cell_fit,
)

__all__ = (
  'MOC_PRODUCTION_SHOCK_CELL_FIT_REFINEMENT_OPERATOR_ID',
  'MocProductionShockCellFitRefinementStatus',
  'MocProductionShockCellFitRefinementCase',
  'MocProductionShockCellFitRefinementMeasurement',
  'measure_moc_production_shock_cell_fit_refinement',
)


MOC_PRODUCTION_SHOCK_CELL_FIT_REFINEMENT_OPERATOR_ID = (
  'op.moc.reflected-domain.production-shock-cell-fit-refinement'
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
####


def _source_fingerprint(source_band: Any) -> str:
  """Fingerprint the immutable upstream source carried by a closure."""

  report = source_band.as_report()
  serialized = json.dumps(
    report,
    sort_keys=True,
    separators=(',', ':'),
    ensure_ascii=True,
    default=str,
  )
  return sha256(serialized.encode('utf-8')).hexdigest()
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
