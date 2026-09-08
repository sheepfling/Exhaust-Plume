"""Solver-owned global pressure-boundary consumption evidence.

The target-guided resolver measures a downstream packet against a family of
global candidates.  This module is the next, narrower seam: it passes the
packet's pressure profile into the exact global ambient march, while the
marching solver still owns the boundary ordinates and tangents.  The result
is a fresh research closure, not a fixed-point proof or a production cell.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from math import isfinite
from typing import Any

from exhaust_plume.models.moc.global_frontier_reconciliation import (
  MocReflectedDomainGlobalFrontierReconciliationRequest,
  moc_reflected_domain_global_frontier_proposal_fingerprint,
)
from exhaust_plume.models.moc.global_physical_closure import (
  MocReflectedDomainGlobalPhysicalClosureResult,
  moc_reflected_domain_global_physical_closure_fingerprint,
  solve_reflected_domain_global_physical_closure,
)
from exhaust_plume.models.moc.physical_field_euler_reconciliation import (
  MocPhysicalFieldEulerBoundaryPressureTarget,
)
from exhaust_plume.models.moc.reflected_domain import ShockBranch

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_FRONTIER_BOUNDARY_CONDITION_OPERATOR_ID',
  'MocReflectedDomainGlobalFrontierBoundaryConditionStatus',
  'MocReflectedDomainGlobalFrontierBoundaryConditionResult',
  'run_reflected_domain_global_frontier_boundary_conditioned_resolve',
)


MOC_REFLECTED_DOMAIN_GLOBAL_FRONTIER_BOUNDARY_CONDITION_OPERATOR_ID = (
  'op.moc.reflected-domain.global-frontier-boundary-condition'
)


class MocReflectedDomainGlobalFrontierBoundaryConditionStatus(str, Enum):
  """Outcome of one pressure-conditioned global re-solve."""

  CONVERGED_RESEARCH_BOUNDARY_CONDITION = (
    'converged-research-global-frontier-boundary-condition'
  )
  INVALID_INPUT = 'invalid_input'
  SOURCE_CLOSURE_FAILURE = 'global-frontier-boundary-source-failure'
  TARGET_COVERAGE_FAILURE = 'global-frontier-boundary-target-coverage-failure'
  GLOBAL_SOLVE_FAILURE = 'global-frontier-boundary-global-solve-failure'
  TARGET_CONSUMPTION_FAILURE = (
    'global-frontier-boundary-target-consumption-failure'
  )
  TARGET_MISMATCH = 'global-frontier-boundary-target-mismatch'
  FIDELITY_FAILURE = 'global-frontier-boundary-fidelity-failure'
####


def _configuration_fingerprint(configuration: Mapping[str, Any]) -> str:
  serialized = json.dumps(
    dict(configuration),
    sort_keys=True,
    separators=(',', ':'),
    ensure_ascii=True,
    default=str,
  )
  return sha256(serialized.encode('utf-8')).hexdigest()
####


def _sample_boundary_at_x(
  closure: MocReflectedDomainGlobalPhysicalClosureResult,
  x_m: float,
  *,
  position_tolerance_m: float,
) -> tuple[float, float, float] | None:
  boundary = closure.downstream_boundary
  if boundary is None or not boundary.samples_available:
    return None
  ####
  points = boundary.boundary_points_m
  states = boundary.boundary_states
  pressures = boundary.boundary_static_pressure_Pa
  if not (len(points) == len(states) == len(pressures) >= 2):
    return None
  ####
  if any(
    second[0] <= first[0] + position_tolerance_m
    for first, second in zip(points, points[1:])
  ):
    return None
  ####
  if (
    x_m < points[0][0] - position_tolerance_m
    or x_m > points[-1][0] + position_tolerance_m
  ):
    return None
  ####
  for index, (first, second) in enumerate(zip(points, points[1:])):
    if abs(x_m - first[0]) <= position_tolerance_m:
      return (
        float(first[1]),
        float(states[index].theta_rad),
        float(pressures[index]),
      )
    ####
    if x_m <= second[0] + position_tolerance_m:
      span = second[0] - first[0]
      if span <= position_tolerance_m:
        return None
      ####
      fraction = min(max((x_m - first[0]) / span, 0.0), 1.0)
      return (
        float(first[1] + fraction * (second[1] - first[1])),
        float(
          states[index].theta_rad
          + fraction * (states[index + 1].theta_rad - states[index].theta_rad)
        ),
        float(
          pressures[index]
          + fraction * (pressures[index + 1] - pressures[index])
        ),
      )
    ####
  ####
  if abs(x_m - points[-1][0]) <= position_tolerance_m:
    return (
      float(points[-1][1]),
      float(states[-1].theta_rad),
      float(pressures[-1]),
    )
  ####
  return None
####


def _measure_target(
  closure: MocReflectedDomainGlobalPhysicalClosureResult,
  request: MocReflectedDomainGlobalFrontierReconciliationRequest,
  *,
  position_tolerance_m: float,
  tangent_tolerance_rad: float,
  pressure_tolerance_fraction: float,
) -> tuple[
  tuple[float, ...],
  tuple[float, ...],
  tuple[float, ...],
  bool,
  bool,
  bool,
  str,
]:
  coordinate_residuals: list[float] = []
  tangent_residuals: list[float] = []
  pressure_residuals: list[float] = []
  for x_m, point, tangent, pressure in zip(
    request.target_x_stations_m,
    request.target_boundary_points_m,
    request.target_tangent_rad,
    request.target_static_pressure_Pa,
    strict=True,
  ):
    sample = _sample_boundary_at_x(
      closure,
      x_m,
      position_tolerance_m=position_tolerance_m,
    )
    if sample is None:
      return (), (), (), False, False, False, (
        'target station lies outside the conditioned solver boundary; '
        'no extrapolation was attempted'
      )
    ####
    boundary_y, boundary_tangent, boundary_pressure = sample
    coordinate_residuals.append(abs(boundary_y - point[1]))
    tangent_residuals.append(abs(boundary_tangent - tangent))
    pressure_residuals.append(abs(boundary_pressure - pressure))
  ####
  residuals = (*coordinate_residuals, *tangent_residuals, *pressure_residuals)
  finite = bool(residuals) and all(isfinite(value) for value in residuals)
  match = bool(
    finite
    and max(coordinate_residuals, default=float('inf')) <= position_tolerance_m
    and max(tangent_residuals, default=float('inf')) <= tangent_tolerance_rad
    and all(
      residual / max(abs(pressure), 1.0) <= pressure_tolerance_fraction
      for residual, pressure in zip(
        pressure_residuals,
        request.target_static_pressure_Pa,
        strict=True,
      )
    )
  )
  return (
    tuple(coordinate_residuals),
    tuple(tangent_residuals),
    tuple(pressure_residuals),
    True,
    finite,
    match,
    (
      'conditioned global boundary covered the exact target and met bounded '
      'research tolerances'
      if match
      else 'conditioned global boundary covered the target but exceeded a '
      'bounded research tolerance'
    ),
  )
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalFrontierBoundaryConditionResult:
  """Research evidence for one pressure-conditioned global field."""

  status: MocReflectedDomainGlobalFrontierBoundaryConditionStatus
  request: MocReflectedDomainGlobalFrontierReconciliationRequest
  source_closure: MocReflectedDomainGlobalPhysicalClosureResult
  target: MocPhysicalFieldEulerBoundaryPressureTarget | None
  conditioned_closure: MocReflectedDomainGlobalPhysicalClosureResult | None
  coordinate_residuals_m: tuple[float, ...] = ()
  tangent_residuals_rad: tuple[float, ...] = ()
  pressure_residuals_Pa: tuple[float, ...] = ()
  target_lineage_verified: bool = False
  target_coverage_verified: bool = False
  target_boundary_condition_consumed: bool = False
  solver_owned_geometry_verified: bool = False
  target_match_verified: bool = False
  fidelity_isolation_verified: bool = False
  global_coupling_verified: bool = False
  downstream_boundary_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  configuration: dict[str, Any] | None = None
  configuration_fingerprint: str = ''
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalFrontierBoundaryConditionStatus,
    ):
      raise TypeError(
        'status must be a '
        'MocReflectedDomainGlobalFrontierBoundaryConditionStatus'
      )
    ####
    if not isinstance(
      self.request,
      MocReflectedDomainGlobalFrontierReconciliationRequest,
    ):
      raise TypeError(
        'request must be a '
        'MocReflectedDomainGlobalFrontierReconciliationRequest'
      )
    ####
    if not isinstance(
      self.source_closure,
      MocReflectedDomainGlobalPhysicalClosureResult,
    ):
      raise TypeError(
        'source_closure must be a '
        'MocReflectedDomainGlobalPhysicalClosureResult'
      )
    ####
    if self.target is not None and not isinstance(
      self.target,
      MocPhysicalFieldEulerBoundaryPressureTarget,
    ):
      raise TypeError(
        'target must be a MocPhysicalFieldEulerBoundaryPressureTarget or None'
      )
    ####
    if self.conditioned_closure is not None and not isinstance(
      self.conditioned_closure,
      MocReflectedDomainGlobalPhysicalClosureResult,
    ):
      raise TypeError(
        'conditioned_closure must be a '
        'MocReflectedDomainGlobalPhysicalClosureResult or None'
      )
    ####
    for name in (
      'coordinate_residuals_m',
      'tangent_residuals_rad',
      'pressure_residuals_Pa',
    ):
      values = tuple(float(value) for value in getattr(self, name))
      if any(not isfinite(value) or value < 0.0 for value in values):
        raise ValueError(f'{name} must contain finite nonnegative values')
      ####
      object.__setattr__(self, name, values)
    ####
    if len({
      len(self.coordinate_residuals_m),
      len(self.tangent_residuals_rad),
      len(self.pressure_residuals_Pa),
    }) != 1:
      raise ValueError('target residual channels must have equal lengths')
    ####
    for name in (
      'target_lineage_verified',
      'target_coverage_verified',
      'target_boundary_condition_consumed',
      'solver_owned_geometry_verified',
      'target_match_verified',
      'fidelity_isolation_verified',
      'global_coupling_verified',
      'downstream_boundary_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if self.global_coupling_verified or self.downstream_boundary_closure_verified:
      raise ValueError(
        'boundary-conditioned research results cannot claim canonical closure'
      )
    ####
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError(
        'boundary-conditioned research results must remain blocked from production'
      )
    ####
    object.__setattr__(self, 'configuration', dict(self.configuration or {}))
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged_research_resolve(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalFrontierBoundaryConditionStatus
      .CONVERGED_RESEARCH_BOUNDARY_CONDITION
      and self.target_lineage_verified
      and self.target_coverage_verified
      and self.target_boundary_condition_consumed
      and self.solver_owned_geometry_verified
      and self.target_match_verified
      and self.fidelity_isolation_verified
      and self.conditioned_closure is not None
      and self.conditioned_closure.physical_closure_verified
    )
  ####

  @property
  def target_residual_magnitude(self) -> float:
    return max(
      max(self.coordinate_residuals_m, default=float('inf')),
      max(self.tangent_residuals_rad, default=float('inf')),
      max(self.pressure_residuals_Pa, default=float('inf')),
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': MOC_REFLECTED_DOMAIN_GLOBAL_FRONTIER_BOUNDARY_CONDITION_OPERATOR_ID,
      'status': self.status.value,
      'converged_research_resolve': self.converged_research_resolve,
      'target_lineage_verified': self.target_lineage_verified,
      'target_coverage_verified': self.target_coverage_verified,
      'target_boundary_condition_consumed': self.target_boundary_condition_consumed,
      'solver_owned_geometry_verified': self.solver_owned_geometry_verified,
      'target_match_verified': self.target_match_verified,
      'target_residual_magnitude': self.target_residual_magnitude,
      'coordinate_residuals_m': self.coordinate_residuals_m,
      'tangent_residuals_rad': self.tangent_residuals_rad,
      'pressure_residuals_Pa': self.pressure_residuals_Pa,
      'global_coupling_verified': self.global_coupling_verified,
      'downstream_boundary_closure_verified': (
        self.downstream_boundary_closure_verified
      ),
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'source_closure_fingerprint': (
        moc_reflected_domain_global_physical_closure_fingerprint(
          self.source_closure
        )
      ),
      'conditioned_closure_fingerprint': (
        None
        if self.conditioned_closure is None
        else moc_reflected_domain_global_physical_closure_fingerprint(
          self.conditioned_closure
        )
      ),
      'source_proposal_fingerprint': (
        moc_reflected_domain_global_frontier_proposal_fingerprint(
          self.request.proposal
        )
      ),
      'configuration': self.configuration,
      'configuration_fingerprint': self.configuration_fingerprint,
      'target': None if self.target is None else self.target.as_report(),
      'conditioned_closure': (
        None
        if self.conditioned_closure is None
        else self.conditioned_closure.as_report()
      ),
      'claim_status': (
        'research-only-global-pressure-boundary-condition; pressure was '
        'consumed by the exact ambient march while geometry remained solver '
        'owned, but fixed-point coupling, refinement, validation, and '
        'production gates remain open'
      ),
      'message': self.message,
    }
  ####
####


def _result(
  status: MocReflectedDomainGlobalFrontierBoundaryConditionStatus,
  request: MocReflectedDomainGlobalFrontierReconciliationRequest,
  source_closure: MocReflectedDomainGlobalPhysicalClosureResult,
  target: MocPhysicalFieldEulerBoundaryPressureTarget | None,
  conditioned_closure: MocReflectedDomainGlobalPhysicalClosureResult | None,
  configuration: Mapping[str, Any],
  message: str,
  **kwargs: Any,
) -> MocReflectedDomainGlobalFrontierBoundaryConditionResult:
  return MocReflectedDomainGlobalFrontierBoundaryConditionResult(
    status=status,
    request=request,
    source_closure=source_closure,
    target=target,
    conditioned_closure=conditioned_closure,
    configuration=dict(configuration),
    configuration_fingerprint=_configuration_fingerprint(configuration),
    message=message,
    **kwargs,
  )
####


def run_reflected_domain_global_frontier_boundary_conditioned_resolve(
  request: MocReflectedDomainGlobalFrontierReconciliationRequest,
  source_closure: MocReflectedDomainGlobalPhysicalClosureResult,
  *,
  position_tolerance_m: float = 5.0e-3,
  tangent_tolerance_rad: float = 5.0e-3,
  pressure_tolerance_fraction: float = 0.02,
  shock_angle_tolerance_rad: float = 0.02,
  maximum_boundary_iterations: int = 16,
  sample_count: int | None = None,
) -> MocReflectedDomainGlobalFrontierBoundaryConditionResult:
  """Consume one exact frontier pressure packet in a fresh global solve."""

  if not isinstance(
    request,
    MocReflectedDomainGlobalFrontierReconciliationRequest,
  ):
    raise TypeError(
      'request must be a '
      'MocReflectedDomainGlobalFrontierReconciliationRequest'
    )
  ####
  if not isinstance(
    source_closure,
    MocReflectedDomainGlobalPhysicalClosureResult,
  ):
    raise TypeError(
      'source_closure must be a MocReflectedDomainGlobalPhysicalClosureResult'
    )
  ####
  try:
    position_tolerance = float(position_tolerance_m)
    tangent_tolerance = float(tangent_tolerance_rad)
    pressure_tolerance = float(pressure_tolerance_fraction)
    shock_tolerance = float(shock_angle_tolerance_rad)
  except (TypeError, ValueError) as error:
    raise ValueError('boundary-condition tolerances must be numeric') from error
  ####
  if not all(
    isfinite(value) and value > 0.0
    for value in (
      position_tolerance,
      tangent_tolerance,
      pressure_tolerance,
      shock_tolerance,
    )
  ):
    raise ValueError('boundary-condition tolerances must be finite and positive')
  ####
  if (
    isinstance(maximum_boundary_iterations, bool)
    or not isinstance(maximum_boundary_iterations, int)
    or maximum_boundary_iterations < 1
  ):
    raise ValueError('maximum_boundary_iterations must be a positive integer')
  ####
  if sample_count is not None and (
    isinstance(sample_count, bool)
    or not isinstance(sample_count, int)
    or sample_count < 3
  ):
    raise ValueError('sample_count must be an integer >= 3 when supplied')
  ####
  source_fingerprint = moc_reflected_domain_global_physical_closure_fingerprint(
    source_closure
  )
  configuration: dict[str, Any] = {
    'source_closure_fingerprint': source_fingerprint,
    'source_proposal_fingerprint': (
      moc_reflected_domain_global_frontier_proposal_fingerprint(request.proposal)
    ),
    'position_tolerance_m': position_tolerance,
    'tangent_tolerance_rad': tangent_tolerance,
    'pressure_tolerance_fraction': pressure_tolerance,
    'shock_angle_tolerance_rad': shock_tolerance,
    'maximum_boundary_iterations': maximum_boundary_iterations,
    'geometry_policy': 'solver-owned-global-march-no-target-geometry-injection-v1',
  }
  if not request.lineage_verified or request.source_closure_fingerprint != source_fingerprint:
    return _result(
      MocReflectedDomainGlobalFrontierBoundaryConditionStatus.INVALID_INPUT,
      request,
      source_closure,
      None,
      None,
      configuration,
      'frontier request does not retain the exact source closure lineage',
    )
  ####
  if not source_closure.converged or not source_closure.physical_closure_verified:
    return _result(
      MocReflectedDomainGlobalFrontierBoundaryConditionStatus.SOURCE_CLOSURE_FAILURE,
      request,
      source_closure,
      None,
      None,
      configuration,
      'boundary-conditioned resolve requires a locally verified source closure',
    )
  ####
  target = MocPhysicalFieldEulerBoundaryPressureTarget(
    x_stations_m=request.target_x_stations_m,
    static_pressure_Pa=request.target_static_pressure_Pa,
    boundary_points_m=request.target_boundary_points_m,
    tangent_rad=request.target_tangent_rad,
    source_id=(
      'global-frontier-boundary-condition:'
      f'{configuration["source_proposal_fingerprint"]}'
    ),
    source_closure_fingerprint=source_fingerprint,
    source_proposal_fingerprint=configuration['source_proposal_fingerprint'],
  )
  remesh = source_closure.global_remesh
  selected_attempt = None if remesh is None else remesh.selected_attempt
  source_band = source_closure.source_band
  if remesh is None or selected_attempt is None or source_band is None:
    return _result(
      MocReflectedDomainGlobalFrontierBoundaryConditionStatus.SOURCE_CLOSURE_FAILURE,
      request,
      source_closure,
      target,
      None,
      configuration,
      'source closure retained no selected remesh attempt or source band',
    )
  ####
  bracket = selected_attempt.first_cell_result.compression_amplitude_bracket
  selected_field = selected_attempt.first_cell_result.selected_physical_field
  if (
    bracket is None
    or len(bracket) != 2
    or selected_field is None
    or selected_field.field is None
  ):
    return _result(
      MocReflectedDomainGlobalFrontierBoundaryConditionStatus.SOURCE_CLOSURE_FAILURE,
      request,
      source_closure,
      target,
      None,
      configuration,
      'source closure retained no solver-owned amplitude bracket or field',
    )
  ####
  resolved_sample_count = len(selected_field.field.shock_boundary_points_m)
  if sample_count is not None:
    resolved_sample_count = sample_count
  ####
  if resolved_sample_count < 3:
    return _result(
      MocReflectedDomainGlobalFrontierBoundaryConditionStatus.SOURCE_CLOSURE_FAILURE,
      request,
      source_closure,
      target,
      None,
      configuration,
      'source closure retained too few shock samples for a fresh solve',
    )
  ####
  shock_points = tuple(selected_field.field.shock_boundary_points_m)
  target_min_x = request.target_x_stations_m[0]
  target_max_x = request.target_x_stations_m[-1]
  shock_min_x = min(point[0] for point in shock_points)
  shock_max_x = max(point[0] for point in shock_points)
  if (
    target_min_x > shock_min_x + position_tolerance
    or target_max_x < shock_max_x - position_tolerance
  ):
    return _result(
      MocReflectedDomainGlobalFrontierBoundaryConditionStatus
      .TARGET_COVERAGE_FAILURE,
      request,
      source_closure,
      target,
      None,
      configuration,
      'partial frontier pressure target does not cover the solver-owned shock '
      'station interval; a joint geometry/state boundary solve is required '
      'and no extrapolation was attempted',
      target_lineage_verified=True,
    )
  ####
  try:
    conditioned = solve_reflected_domain_global_physical_closure(
      source_band,
      outer_source_indices=remesh.outer_source_indices,
      target_centerline_indices=remesh.target_centerline_indices,
      compression_amplitude_lower_rad=float(bracket[0]),
      compression_amplitude_upper_rad=float(bracket[1]),
      compression_envelope_skews=(
        float(selected_attempt.compression_envelope_skew),
      ),
      incoming_handoff=source_band.incoming_handoff,
      ambient_pressure_target=target,
      sample_count=resolved_sample_count,
      branch=ShockBranch.WEAK,
      shock_angle_tolerance_rad=shock_tolerance,
      maximum_boundary_iterations=maximum_boundary_iterations,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _result(
      MocReflectedDomainGlobalFrontierBoundaryConditionStatus.GLOBAL_SOLVE_FAILURE,
      request,
      source_closure,
      target,
      None,
      configuration,
      f'conditioned global solve raised: {error}',
    )
  ####
  if not conditioned.converged or not conditioned.physical_closure_verified:
    return _result(
      MocReflectedDomainGlobalFrontierBoundaryConditionStatus.GLOBAL_SOLVE_FAILURE,
      request,
      source_closure,
      target,
      conditioned,
      configuration,
      f'conditioned global solve did not pass local closure gates: {conditioned.message}',
    )
  ####
  field_result = conditioned.global_euler
  physical_field = None if field_result is None else field_result.physical_field
  march = None if physical_field is None else physical_field.ambient_march
  target_consumed = bool(
    march is not None
    and march.ambient_pressure_target_consumed
    and march.ambient_pressure_target_source == target.source_id
    and len(march.ambient_boundary.ambient_pressure_profile_Pa)
    == len(march.boundary_samples)
  )
  geometry_solver_owned = bool(
    target_consumed
    and march is not None
    and not march.ambient_pressure_target_geometry_consumed
  )
  (
    coordinate_residuals,
    tangent_residuals,
    pressure_residuals,
    coverage_verified,
    residuals_finite,
    match_verified,
    measurement_message,
  ) = _measure_target(
    conditioned,
    request,
    position_tolerance_m=position_tolerance,
    tangent_tolerance_rad=tangent_tolerance,
    pressure_tolerance_fraction=pressure_tolerance,
  )
  fidelity_isolation = bool(
    target_consumed
    and geometry_solver_owned
    and residuals_finite
    and not conditioned.production_claim_allowed
    and not conditioned.downstream_boundary_closure_verified
  )
  if not target_consumed:
    status = (
      MocReflectedDomainGlobalFrontierBoundaryConditionStatus
      .TARGET_CONSUMPTION_FAILURE
    )
    message = (
      'global solve completed locally but did not retain proof that the '
      'pressure profile reached the exact ambient march'
    )
  elif not coverage_verified or not residuals_finite:
    status = (
      MocReflectedDomainGlobalFrontierBoundaryConditionStatus
      .TARGET_COVERAGE_FAILURE
    )
    message = measurement_message
  elif not match_verified:
    status = MocReflectedDomainGlobalFrontierBoundaryConditionStatus.TARGET_MISMATCH
    message = measurement_message
  elif not fidelity_isolation:
    status = (
      MocReflectedDomainGlobalFrontierBoundaryConditionStatus.FIDELITY_FAILURE
    )
    message = 'conditioned solve did not preserve the research-only promotion gates'
  else:
    status = (
      MocReflectedDomainGlobalFrontierBoundaryConditionStatus
      .CONVERGED_RESEARCH_BOUNDARY_CONDITION
    )
    message = (
      'downstream pressure was consumed by a fresh exact global ambient '
      'march; the ambient geometry remained solver-owned and canonical '
      'fixed-point closure remains open'
    )
  ####
  return _result(
    status,
    request,
    source_closure,
    target,
    conditioned,
    configuration,
    message,
    coordinate_residuals_m=coordinate_residuals,
    tangent_residuals_rad=tangent_residuals,
    pressure_residuals_Pa=pressure_residuals,
    target_lineage_verified=True,
    target_coverage_verified=coverage_verified,
    target_boundary_condition_consumed=target_consumed,
    solver_owned_geometry_verified=geometry_solver_owned,
    target_match_verified=match_verified,
    fidelity_isolation_verified=fidelity_isolation,
  )
####
