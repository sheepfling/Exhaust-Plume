"""Bounded global-to-coupled downstream continuation for the MOC lane.

The global reflected closure and the constant-gamma coupled Euler field are
separate solver lanes.  This module binds them for one explicit research
candidate and retains the independent coupled-field audit.  The candidate is
not a canonical global closure: the downstream field does not feed its
pressure and characteristic response back into the upstream shock solve, so
``global_coupling_verified`` remains false by construction.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import atan2, isfinite
from typing import Any

from exhaust_plume.models.moc.chain import (
  MocChainTerminationDecision,
  MocChainTerminationReason,
)
from exhaust_plume.models.moc.coupled_euler_free_boundary import (
  MocReflectedDomainCoupledEulerFreeBoundaryRequest,
  MocReflectedDomainCoupledEulerFreeBoundaryResult,
  MocReflectedDomainCoupledEulerFreeBoundaryStatus,
  MocReflectedDomainCoupledEulerInletBoundaryMode,
  build_reflected_domain_coupled_euler_free_boundary_request,
  solve_reflected_domain_coupled_euler_free_boundary,
)
from exhaust_plume.models.moc.global_physical_closure import (
  MocReflectedDomainDownstreamBoundaryResult,
  MocReflectedDomainGlobalPhysicalClosureResult,
  moc_reflected_domain_global_physical_closure_fingerprint,
)
from exhaust_plume.models.moc.field_continuation import (
  MocPhysicalFieldContinuationProfileRequest,
  MocPhysicalFieldContinuationProfileResult,
  build_moc_physical_field_continuation_profile,
)
from exhaust_plume.models.moc.physical_field_shock_front import (
  MocPhysicalFieldShockFrontConditionRequest,
  MocPhysicalFieldShockFrontConditionResult,
  build_moc_physical_field_shock_front_condition,
)
from exhaust_plume.models.moc.reflected_domain_mixed_regime import (
  MocReflectedDomainMixedRegimeBoundaryRequest,
  build_reflected_domain_mixed_regime_boundary_request,
)
from exhaust_plume.models.moc.transonic_interface import (
  MocTransonicShockInterfaceFieldPlacementRequest,
  MocTransonicShockInterfaceFieldPlacementResult,
  build_moc_transonic_shock_interface_profile_from_field_placement,
)

__all__ = (
  'MocReflectedDomainGlobalCoupledDownstreamStatus',
  'MocReflectedDomainGlobalPhysicalFieldHandoff',
  'MocReflectedDomainGlobalCoupledDownstreamBoundaryResponseStatus',
  'MocReflectedDomainGlobalCoupledDownstreamBoundaryResponse',
  'measure_reflected_domain_global_coupled_downstream_boundary_response',
  'MocReflectedDomainGlobalCoupledDownstreamResult',
  'build_reflected_domain_global_solver_owned_physical_field_handoff',
  'solve_reflected_domain_global_coupled_downstream',
)


GLOBAL_COUPLED_DOWNSTREAM_MODEL = (
  'research-global-coupled-euler-downstream-candidate'
)
GLOBAL_COUPLED_DOWNSTREAM_BOUNDARY_RESPONSE_MODEL = (
  'research-global-coupled-downstream-boundary-response-v1'
)


class MocReflectedDomainGlobalCoupledDownstreamStatus(str, Enum):
  """Outcome of one bound global-to-coupled downstream candidate."""

  CONVERGED_LOCAL_COUPLED_FIELD = (
    'converged-local-global-coupled-downstream-field'
  )
  INVALID_INPUT = 'invalid_input'
  UPSTREAM_CLOSURE_FAILURE = 'global-coupled-downstream-upstream-failure'
  MIXED_REGIME_REQUEST_FAILURE = (
    'global-coupled-downstream-mixed-regime-request-failure'
  )
  PHYSICAL_FIELD_HANDOFF_FAILURE = (
    'global-coupled-downstream-physical-field-handoff-failure'
  )
  COUPLED_SOLVER_FAILURE = 'global-coupled-downstream-solver-failure'
  INDEPENDENT_AUDIT_FAILURE = (
    'global-coupled-downstream-independent-audit-failure'
  )
####


class MocReflectedDomainGlobalCoupledDownstreamBoundaryResponseStatus(str, Enum):
  """Outcome of comparing the downstream field with its global neighbor."""

  CONVERGED_LOCAL_OVERLAP = 'converged-local-downstream-boundary-overlap'
  INVALID_INPUT = 'invalid_input'
  UPSTREAM_BOUNDARY_FAILURE = 'downstream-boundary-upstream-reference-failure'
  COUPLED_FIELD_FAILURE = 'downstream-boundary-coupled-field-failure'
  COVERAGE_FAILURE = 'downstream-boundary-overlap-coverage-failure'
  RESIDUAL_FAILURE = 'downstream-boundary-overlap-residual-failure'
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalPhysicalFieldHandoff:
  """Solver-owned exact field handoff prepared for the coupled lane.

  The placement, continuation profile, and neighboring shock-front condition
  are all derived from one retained global physical field.  This object is a
  contract seam only: consuming it does not establish global feedback,
  canonical mixed-regime closure, or a production claim.
  """

  placement: MocTransonicShockInterfaceFieldPlacementResult
  continuation_profile: MocPhysicalFieldContinuationProfileResult
  shock_front_condition: MocPhysicalFieldShockFrontConditionResult

  def __post_init__(self) -> None:
    if not isinstance(
      self.placement,
      MocTransonicShockInterfaceFieldPlacementResult,
    ):
      raise TypeError(
        'placement must be a '
        'MocTransonicShockInterfaceFieldPlacementResult'
      )
    ####
    if not isinstance(
      self.continuation_profile,
      MocPhysicalFieldContinuationProfileResult,
    ):
      raise TypeError(
        'continuation_profile must be a '
        'MocPhysicalFieldContinuationProfileResult'
      )
    ####
    if not isinstance(
      self.shock_front_condition,
      MocPhysicalFieldShockFrontConditionResult,
    ):
      raise TypeError(
        'shock_front_condition must be a '
        'MocPhysicalFieldShockFrontConditionResult'
      )
    ####
  ####

  @property
  def converged(self) -> bool:
    """Whether every derived handoff component passed its own audit."""

    return bool(
      self.placement.converged
      and self.continuation_profile.converged
      and self.shock_front_condition.converged
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'converged': self.converged,
      'placement': self.placement.as_report(),
      'continuation_profile': self.continuation_profile.as_report(),
      'shock_front_condition': self.shock_front_condition.as_report(),
      'claim_status': (
        'research-only-solver-owned-global-physical-field-handoff; '
        'global-feedback, canonical mixed-regime closure, refinement, and '
        'external validation remain open'
      ),
    }
  ####
####


def _interpolate_downstream_boundary(
  boundary: MocReflectedDomainDownstreamBoundaryResult,
  x_m: float,
  *,
  position_tolerance_m: float,
) -> tuple[float, float, float] | None:
  """Sample the retained global boundary without x extrapolation."""

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
  if x_m < points[0][0] - position_tolerance_m or x_m > points[-1][0] + position_tolerance_m:
    return None
  ####
  for index, (first_point, second_point) in enumerate(zip(points, points[1:])):
    if abs(x_m - first_point[0]) <= position_tolerance_m:
      return (
        float(first_point[1]),
        float(states[index].theta_rad),
        float(pressures[index]),
      )
    ####
    if x_m <= second_point[0] + position_tolerance_m:
      span = second_point[0] - first_point[0]
      if span <= position_tolerance_m:
        return None
      ####
      fraction = min(max((x_m - first_point[0]) / span, 0.0), 1.0)
      return (
        float(first_point[1] + fraction * (second_point[1] - first_point[1])),
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


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalCoupledDownstreamBoundaryResponse:
  """Independent overlap response between global and coupled boundaries.

  This result measures the downstream response on the shared retained domain.
  It is deliberately not a global closure: no extrapolation is allowed, and
  the response does not change the upstream solver or promotion gates.
  """

  status: MocReflectedDomainGlobalCoupledDownstreamBoundaryResponseStatus
  upstream_boundary: MocReflectedDomainDownstreamBoundaryResult | None
  coupled_field: MocReflectedDomainCoupledEulerFreeBoundaryResult | None
  matched_x_stations_m: tuple[float, ...] = ()
  upstream_boundary_points_m: tuple[tuple[float, float], ...] = ()
  coupled_boundary_points_m: tuple[tuple[float, float], ...] = ()
  coordinate_residuals_m: tuple[float, ...] = ()
  tangent_residuals_rad: tuple[float, ...] = ()
  pressure_residuals_Pa: tuple[float, ...] = ()
  normal_velocity_residuals_m_s: tuple[float, ...] = ()
  coordinate_tolerance_m: float = 1.0e-3
  tangent_tolerance_rad: float = 5.0e-2
  pressure_tolerance_Pa: float = 2.0e4
  normal_velocity_tolerance_m_s: float = 2.0e2
  overlap_coverage_verified: bool = False
  residuals_verified: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalCoupledDownstreamBoundaryResponseStatus,
    ):
      raise TypeError(
        'status must be a '
        'MocReflectedDomainGlobalCoupledDownstreamBoundaryResponseStatus'
      )
    ####
    if self.upstream_boundary is not None and not isinstance(
      self.upstream_boundary,
      MocReflectedDomainDownstreamBoundaryResult,
    ):
      raise TypeError(
        'upstream_boundary must be a '
        'MocReflectedDomainDownstreamBoundaryResult or None'
      )
    ####
    if self.coupled_field is not None and not isinstance(
      self.coupled_field,
      MocReflectedDomainCoupledEulerFreeBoundaryResult,
    ):
      raise TypeError(
        'coupled_field must be a '
        'MocReflectedDomainCoupledEulerFreeBoundaryResult or None'
      )
    ####
    for name in (
      'matched_x_stations_m',
      'coordinate_residuals_m',
      'tangent_residuals_rad',
      'pressure_residuals_Pa',
      'normal_velocity_residuals_m_s',
    ):
      values = tuple(float(value) for value in getattr(self, name))
      if any(not isfinite(value) or value < 0.0 for value in values):
        raise ValueError(f'{name} must contain finite nonnegative values')
      ####
      object.__setattr__(self, name, values)
    ####
    for name in ('upstream_boundary_points_m', 'coupled_boundary_points_m'):
      points = tuple(
        (float(point[0]), float(point[1])) for point in getattr(self, name)
      )
      if any(not all(isfinite(value) for value in point) for point in points):
        raise ValueError(f'{name} must contain finite points')
      ####
      object.__setattr__(self, name, points)
    ####
    lengths = {
      len(self.matched_x_stations_m),
      len(self.upstream_boundary_points_m),
      len(self.coupled_boundary_points_m),
      len(self.coordinate_residuals_m),
      len(self.tangent_residuals_rad),
      len(self.pressure_residuals_Pa),
      len(self.normal_velocity_residuals_m_s),
    }
    if len(lengths) != 1:
      raise ValueError('downstream boundary response channels must be aligned')
    ####
    for name in (
      'coordinate_tolerance_m',
      'tangent_tolerance_rad',
      'pressure_tolerance_Pa',
      'normal_velocity_tolerance_m_s',
    ):
      value = float(getattr(self, name))
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      ####
      object.__setattr__(self, name, value)
    ####
    for name in ('overlap_coverage_verified', 'residuals_verified'):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def maximum_coordinate_residual_m(self) -> float:
    return max(self.coordinate_residuals_m, default=0.0)
  ####

  @property
  def maximum_tangent_residual_rad(self) -> float:
    return max(self.tangent_residuals_rad, default=0.0)
  ####

  @property
  def maximum_pressure_residual_Pa(self) -> float:
    return max(self.pressure_residuals_Pa, default=0.0)
  ####

  @property
  def maximum_normal_velocity_residual_m_s(self) -> float:
    return max(self.normal_velocity_residuals_m_s, default=0.0)
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalCoupledDownstreamBoundaryResponseStatus
      .CONVERGED_LOCAL_OVERLAP
      and self.overlap_coverage_verified
      and self.residuals_verified
    )
  ####

  @property
  def production_claim_allowed(self) -> bool:
    return False
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'model': GLOBAL_COUPLED_DOWNSTREAM_BOUNDARY_RESPONSE_MODEL,
      'status': self.status.value,
      'converged': self.converged,
      'matched_x_stations_m': self.matched_x_stations_m,
      'upstream_boundary_points_m': self.upstream_boundary_points_m,
      'coupled_boundary_points_m': self.coupled_boundary_points_m,
      'coordinate_residuals_m': self.coordinate_residuals_m,
      'tangent_residuals_rad': self.tangent_residuals_rad,
      'pressure_residuals_Pa': self.pressure_residuals_Pa,
      'normal_velocity_residuals_m_s': self.normal_velocity_residuals_m_s,
      'maximum_coordinate_residual_m': self.maximum_coordinate_residual_m,
      'maximum_tangent_residual_rad': self.maximum_tangent_residual_rad,
      'maximum_pressure_residual_Pa': self.maximum_pressure_residual_Pa,
      'maximum_normal_velocity_residual_m_s': (
        self.maximum_normal_velocity_residual_m_s
      ),
      'coordinate_tolerance_m': self.coordinate_tolerance_m,
      'tangent_tolerance_rad': self.tangent_tolerance_rad,
      'pressure_tolerance_Pa': self.pressure_tolerance_Pa,
      'normal_velocity_tolerance_m_s': self.normal_velocity_tolerance_m_s,
      'overlap_coverage_verified': self.overlap_coverage_verified,
      'residuals_verified': self.residuals_verified,
      'production_claim_allowed': self.production_claim_allowed,
      'claim_status': (
        'research-only-global-coupled-boundary-overlap-response; upstream '
        'feedback, canonical closure, refinement, and external validation remain open'
      ),
      'message': self.message,
    }
  ####
####


def measure_reflected_domain_global_coupled_downstream_boundary_response(
  closure: MocReflectedDomainGlobalPhysicalClosureResult,
  coupled_field: MocReflectedDomainCoupledEulerFreeBoundaryResult,
  *,
  position_tolerance_m: float = 1.0e-9,
  coordinate_tolerance_m: float = 1.0e-3,
  tangent_tolerance_rad: float = 5.0e-2,
  pressure_tolerance_Pa: float = 2.0e4,
  normal_velocity_tolerance_m_s: float = 2.0e2,
) -> MocReflectedDomainGlobalCoupledDownstreamBoundaryResponse:
  """Recompute the shared global/coupled boundary response without extrapolation."""

  def failure(
    status: MocReflectedDomainGlobalCoupledDownstreamBoundaryResponseStatus,
    message: str,
    *,
    upstream: MocReflectedDomainDownstreamBoundaryResult | None = None,
    coupled: MocReflectedDomainCoupledEulerFreeBoundaryResult | None = None,
    coverage: bool = False,
  ) -> MocReflectedDomainGlobalCoupledDownstreamBoundaryResponse:
    return MocReflectedDomainGlobalCoupledDownstreamBoundaryResponse(
      status=status,
      upstream_boundary=upstream,
      coupled_field=coupled,
      coordinate_tolerance_m=coordinate_tolerance_m,
      tangent_tolerance_rad=tangent_tolerance_rad,
      pressure_tolerance_Pa=pressure_tolerance_Pa,
      normal_velocity_tolerance_m_s=normal_velocity_tolerance_m_s,
      overlap_coverage_verified=coverage,
      message=message,
    )
  ####

  if not isinstance(closure, MocReflectedDomainGlobalPhysicalClosureResult):
    return failure(
      MocReflectedDomainGlobalCoupledDownstreamBoundaryResponseStatus.INVALID_INPUT,
      'closure must be a MocReflectedDomainGlobalPhysicalClosureResult',
    )
  ####
  if not isinstance(
    coupled_field,
    MocReflectedDomainCoupledEulerFreeBoundaryResult,
  ):
    return failure(
      MocReflectedDomainGlobalCoupledDownstreamBoundaryResponseStatus.INVALID_INPUT,
      'coupled_field must be a MocReflectedDomainCoupledEulerFreeBoundaryResult',
    )
  ####
  try:
    tolerances = (
      float(position_tolerance_m),
      float(coordinate_tolerance_m),
      float(tangent_tolerance_rad),
      float(pressure_tolerance_Pa),
      float(normal_velocity_tolerance_m_s),
    )
  except (TypeError, ValueError):
    return failure(
      MocReflectedDomainGlobalCoupledDownstreamBoundaryResponseStatus.INVALID_INPUT,
      'downstream boundary response tolerances must be numeric',
    )
  ####
  if any(not isfinite(value) or value <= 0.0 for value in tolerances):
    return failure(
      MocReflectedDomainGlobalCoupledDownstreamBoundaryResponseStatus.INVALID_INPUT,
      'downstream boundary response tolerances must be finite and positive',
    )
  ####
  upstream = closure.downstream_boundary
  if upstream is None or not upstream.samples_available:
    return failure(
      MocReflectedDomainGlobalCoupledDownstreamBoundaryResponseStatus
      .UPSTREAM_BOUNDARY_FAILURE,
      'global closure retained no downstream boundary samples for overlap',
      upstream=upstream,
      coupled=coupled_field,
    )
  ####
  coupled_points = tuple(coupled_field.free_boundary_points_m)
  coupled_pressures = tuple(
    coupled_field.free_boundary_adjacent_static_pressure_Pa
  )
  coupled_normal_velocities = tuple(
    coupled_field.free_boundary_normal_velocity_residuals_m_s
  )
  if not (
    len(coupled_points) >= 2
    and len(coupled_pressures) == len(coupled_points) - 1
    and len(coupled_normal_velocities) == len(coupled_points) - 1
  ):
    return failure(
      MocReflectedDomainGlobalCoupledDownstreamBoundaryResponseStatus
      .COUPLED_FIELD_FAILURE,
      'coupled field retained no aligned free-boundary pressure response',
      upstream=upstream,
      coupled=coupled_field,
    )
  ####
  if any(
    second[0] <= first[0] + tolerances[0]
    for first, second in zip(coupled_points, coupled_points[1:])
  ):
    return failure(
      MocReflectedDomainGlobalCoupledDownstreamBoundaryResponseStatus
      .COUPLED_FIELD_FAILURE,
      'coupled free-boundary stations must be strictly downstream ordered',
      upstream=upstream,
      coupled=coupled_field,
    )
  ####
  matched_x: list[float] = []
  upstream_points: list[tuple[float, float]] = []
  coordinate_residuals: list[float] = []
  tangent_residuals: list[float] = []
  pressure_residuals: list[float] = []
  normal_velocity_residuals: list[float] = []
  for index, point in enumerate(coupled_points):
    reference = _interpolate_downstream_boundary(
      upstream,
      point[0],
      position_tolerance_m=tolerances[0],
    )
    if reference is None:
      return failure(
        MocReflectedDomainGlobalCoupledDownstreamBoundaryResponseStatus
        .COVERAGE_FAILURE,
        'coupled free-boundary station lies outside the retained global '
        'boundary; no extrapolation was attempted',
        upstream=upstream,
        coupled=coupled_field,
        coverage=False,
      )
    ####
    reference_y, reference_theta, reference_pressure = reference
    matched_x.append(float(point[0]))
    upstream_points.append((float(point[0]), reference_y))
    coordinate_residuals.append(abs(float(point[1]) - reference_y))
    if index == 0:
      adjacent_pressure = coupled_pressures[0]
    elif index >= len(coupled_pressures):
      adjacent_pressure = coupled_pressures[-1]
    else:
      adjacent_pressure = 0.5 * (
        coupled_pressures[index - 1] + coupled_pressures[index]
      )
    ####
    pressure_residuals.append(abs(float(adjacent_pressure) - reference_pressure))
    if index == 0:
      coupled_theta = atan2(
        coupled_points[1][1] - coupled_points[0][1],
        coupled_points[1][0] - coupled_points[0][0],
      )
    else:
      coupled_theta = atan2(
        point[1] - coupled_points[index - 1][1],
        point[0] - coupled_points[index - 1][0],
      )
    ####
    tangent_residuals.append(abs(coupled_theta - reference_theta))
    if index < len(coupled_normal_velocities):
      normal_velocity_residuals.append(
        abs(float(coupled_normal_velocities[index]))
      )
    else:
      normal_velocity_residuals.append(
        abs(float(coupled_normal_velocities[-1]))
      )
    ####
  ####
  coupled_boundary_points = tuple(
    (float(point[0]), float(point[1])) for point in coupled_points
  )
  residuals_verified = bool(
    max(coordinate_residuals, default=0.0) <= tolerances[1]
    and max(tangent_residuals, default=0.0) <= tolerances[2]
    and max(pressure_residuals, default=0.0) <= tolerances[3]
    and max(normal_velocity_residuals, default=0.0) <= tolerances[4]
  )
  status = (
    MocReflectedDomainGlobalCoupledDownstreamBoundaryResponseStatus
    .CONVERGED_LOCAL_OVERLAP
    if residuals_verified
    else MocReflectedDomainGlobalCoupledDownstreamBoundaryResponseStatus
    .RESIDUAL_FAILURE
  )
  message = (
    'coupled free-boundary response is covered by the retained global '
    'boundary and all overlap residuals pass'
    if residuals_verified
    else 'coupled free-boundary response is covered, but the retained global '
    'boundary overlap residual exceeds its research tolerance'
  )
  return MocReflectedDomainGlobalCoupledDownstreamBoundaryResponse(
    status=status,
    upstream_boundary=upstream,
    coupled_field=coupled_field,
    matched_x_stations_m=tuple(matched_x),
    upstream_boundary_points_m=tuple(upstream_points),
    coupled_boundary_points_m=coupled_boundary_points,
    coordinate_residuals_m=tuple(coordinate_residuals),
    tangent_residuals_rad=tuple(tangent_residuals),
    pressure_residuals_Pa=tuple(pressure_residuals),
    normal_velocity_residuals_m_s=tuple(normal_velocity_residuals),
    coordinate_tolerance_m=tolerances[1],
    tangent_tolerance_rad=tolerances[2],
    pressure_tolerance_Pa=tolerances[3],
    normal_velocity_tolerance_m_s=tolerances[4],
    overlap_coverage_verified=True,
    residuals_verified=residuals_verified,
    message=message,
  )
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalCoupledDownstreamResult:
  """A research candidate with explicit upstream and downstream lineage."""

  status: MocReflectedDomainGlobalCoupledDownstreamStatus
  closure: MocReflectedDomainGlobalPhysicalClosureResult | None
  mixed_regime_request: MocReflectedDomainMixedRegimeBoundaryRequest | None
  coupled_request: MocReflectedDomainCoupledEulerFreeBoundaryRequest | None
  coupled_field: MocReflectedDomainCoupledEulerFreeBoundaryResult | None
  coupled_field_audit: Any | None
  physical_field_handoff: MocReflectedDomainGlobalPhysicalFieldHandoff | None = None
  downstream_boundary_response: (
    MocReflectedDomainGlobalCoupledDownstreamBoundaryResponse | None
  ) = None
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalCoupledDownstreamStatus,
    ):
      raise TypeError(
        'status must be a MocReflectedDomainGlobalCoupledDownstreamStatus'
      )
    ####
    if self.closure is not None and not isinstance(
      self.closure,
      MocReflectedDomainGlobalPhysicalClosureResult,
    ):
      raise TypeError(
        'closure must be a '
        'MocReflectedDomainGlobalPhysicalClosureResult or None'
      )
    ####
    if self.mixed_regime_request is not None and not isinstance(
      self.mixed_regime_request,
      MocReflectedDomainMixedRegimeBoundaryRequest,
    ):
      raise TypeError(
        'mixed_regime_request must be a '
        'MocReflectedDomainMixedRegimeBoundaryRequest or None'
      )
    ####
    if self.coupled_request is not None and not isinstance(
      self.coupled_request,
      MocReflectedDomainCoupledEulerFreeBoundaryRequest,
    ):
      raise TypeError(
        'coupled_request must be a '
        'MocReflectedDomainCoupledEulerFreeBoundaryRequest or None'
      )
    ####
    if self.coupled_field is not None and not isinstance(
      self.coupled_field,
      MocReflectedDomainCoupledEulerFreeBoundaryResult,
    ):
      raise TypeError(
        'coupled_field must be a '
        'MocReflectedDomainCoupledEulerFreeBoundaryResult or None'
      )
    ####
    if self.physical_field_handoff is not None and not isinstance(
      self.physical_field_handoff,
      MocReflectedDomainGlobalPhysicalFieldHandoff,
    ):
      raise TypeError(
        'physical_field_handoff must be a '
        'MocReflectedDomainGlobalPhysicalFieldHandoff or None'
      )
    ####
    if self.downstream_boundary_response is not None and not isinstance(
      self.downstream_boundary_response,
      MocReflectedDomainGlobalCoupledDownstreamBoundaryResponse,
    ):
      raise TypeError(
        'downstream_boundary_response must be a '
        'MocReflectedDomainGlobalCoupledDownstreamBoundaryResponse or None'
      )
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def source_closure_fingerprint(self) -> str | None:
    if self.closure is None:
      return None
    ####
    return moc_reflected_domain_global_physical_closure_fingerprint(
      self.closure
    )
  ####

  @property
  def closure_lineage_verified(self) -> bool:
    """Whether the candidate retains one exact closure identity end to end."""

    fingerprint = self.source_closure_fingerprint
    return bool(
      fingerprint is not None
      and self.mixed_regime_request is not None
      and self.mixed_regime_request.closure_fingerprint == fingerprint
      and self.coupled_request is not None
      and self.coupled_request.source_closure_fingerprint == fingerprint
      and (
        self.coupled_field is None
        or (
          self.coupled_field.request is self.coupled_request
          and self.coupled_field.request.source_closure_fingerprint == fingerprint
        )
      )
      and (
        self.coupled_field_audit is None
        or getattr(self.coupled_field_audit, 'candidate', None)
        is self.coupled_field
      )
    )
  ####

  @property
  def local_coupled_field_verified(self) -> bool:
    """Whether the downstream candidate and its independent audit both pass."""

    return bool(
      self.coupled_field is not None
      and self.coupled_field_audit is not None
      and self.coupled_field.status
      is MocReflectedDomainCoupledEulerFreeBoundaryStatus
      .CONVERGED_LOCAL_PHYSICAL_CLOSURE
      and self.coupled_field.converged
      and getattr(self.coupled_field_audit, 'converged', False)
      and getattr(self.coupled_field_audit, 'local_consistency_verified', False)
      and self.closure_lineage_verified
    )
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalCoupledDownstreamStatus
      .CONVERGED_LOCAL_COUPLED_FIELD
      and self.local_coupled_field_verified
    )
  ####

  @property
  def global_coupling_verified(self) -> bool:
    """Whether downstream response was iterated back into the global solve."""

    return False
  ####

  @property
  def downstream_boundary_closure_verified(self) -> bool:
    """The candidate never satisfies the canonical downstream gate."""

    return False
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    return True
  ####

  @property
  def production_claim_allowed(self) -> bool:
    return False
  ####

  def as_chain_termination_decision(self) -> MocChainTerminationDecision:
    reason = (
      MocChainTerminationReason.FIDELITY_NOT_ALLOWED
      if self.local_coupled_field_verified
      else MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
    )
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=reason,
      message=self.message,
      diagnostics={
        'termination_model': GLOBAL_COUPLED_DOWNSTREAM_MODEL,
        'status': self.status.value,
        'source_closure_fingerprint': self.source_closure_fingerprint,
        'closure_lineage_verified': self.closure_lineage_verified,
        'local_coupled_field_verified': self.local_coupled_field_verified,
        'global_coupling_verified': self.global_coupling_verified,
        'downstream_boundary_closure_verified': (
          self.downstream_boundary_closure_verified
        ),
        'chain_promotion_blocked': self.chain_promotion_blocked,
        'production_claim_allowed': self.production_claim_allowed,
      },
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'model': GLOBAL_COUPLED_DOWNSTREAM_MODEL,
      'status': self.status.value,
      'converged': self.converged,
      'source_closure_fingerprint': self.source_closure_fingerprint,
      'closure_lineage_verified': self.closure_lineage_verified,
      'local_coupled_field_verified': self.local_coupled_field_verified,
      'global_coupling_verified': self.global_coupling_verified,
      'downstream_boundary_closure_verified': (
        self.downstream_boundary_closure_verified
      ),
      'mixed_regime_request': (
        None
        if self.mixed_regime_request is None
        else self.mixed_regime_request.as_report()
      ),
      'coupled_request': (
        None
        if self.coupled_request is None
        else self.coupled_request.as_report()
      ),
      'coupled_field': (
        None
        if self.coupled_field is None
        else self.coupled_field.as_report()
      ),
      'coupled_field_audit': (
        None
        if self.coupled_field_audit is None
        else self.coupled_field_audit.as_report()
      ),
      'physical_field_handoff': (
        None
        if self.physical_field_handoff is None
        else self.physical_field_handoff.as_report()
      ),
      'downstream_boundary_response': (
        None
        if self.downstream_boundary_response is None
        else self.downstream_boundary_response.as_report()
      ),
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'chain_termination_decision': self.as_chain_termination_decision().as_report(),
      'message': self.message,
    }
  ####
####


def _failure(
  status: MocReflectedDomainGlobalCoupledDownstreamStatus,
  message: str,
  *,
  closure: MocReflectedDomainGlobalPhysicalClosureResult | None = None,
  mixed_regime_request: MocReflectedDomainMixedRegimeBoundaryRequest | None = None,
  coupled_request: MocReflectedDomainCoupledEulerFreeBoundaryRequest | None = None,
  coupled_field: MocReflectedDomainCoupledEulerFreeBoundaryResult | None = None,
  coupled_field_audit: Any | None = None,
  physical_field_handoff: MocReflectedDomainGlobalPhysicalFieldHandoff | None = None,
  downstream_boundary_response: (
    MocReflectedDomainGlobalCoupledDownstreamBoundaryResponse | None
  ) = None,
) -> MocReflectedDomainGlobalCoupledDownstreamResult:
  return MocReflectedDomainGlobalCoupledDownstreamResult(
    status=status,
    closure=closure,
    mixed_regime_request=mixed_regime_request,
    coupled_request=coupled_request,
    coupled_field=coupled_field,
    coupled_field_audit=coupled_field_audit,
    physical_field_handoff=physical_field_handoff,
    downstream_boundary_response=downstream_boundary_response,
    message=message,
  )
####


def build_reflected_domain_global_solver_owned_physical_field_handoff(
  closure: MocReflectedDomainGlobalPhysicalClosureResult,
  *,
  sample_count: int = 10,
  post_shock_fraction: float = 0.25,
) -> MocReflectedDomainGlobalPhysicalFieldHandoff:
  """Derive an exact audited downstream handoff from one global field.

  The placement rule is solver-owned and uses the complete retained field
  span.  The continuation profile is sampled directly from that field, and
  the shock-front condition binds the same field's shock, ambient, and
  centerline paths.  No caller-selected geometry or scalar-normal-shock
  fallback is introduced.
  """

  if not isinstance(
    closure,
    MocReflectedDomainGlobalPhysicalClosureResult,
  ):
    raise TypeError(
      'closure must be a MocReflectedDomainGlobalPhysicalClosureResult'
    )
  ####
  if (
    not closure.converged
    or not closure.physical_closure_verified
    or closure.global_euler is None
    or closure.global_euler.physical_field is None
    or closure.global_euler.physical_field.field is None
  ):
    raise ValueError(
      'solver-owned physical-field handoff requires a locally verified global '
      'closure with a retained exact physical field'
    )
  ####
  field = closure.global_euler.physical_field.field
  placement = build_moc_transonic_shock_interface_profile_from_field_placement(
    MocTransonicShockInterfaceFieldPlacementRequest(
      field=field,
      sample_count=sample_count,
      post_shock_fraction=post_shock_fraction,
      boundary_margin_fraction=0.0,
      profile_id=(
        'global-closure-solver-owned-physical-field-placement-v1'
      ),
      source='global-closure-solver-owned-physical-field-handoff-v1',
    )
  )
  if not placement.converged or not placement.sample_points_m:
    raise ValueError(
      'solver-owned physical-field placement did not pass its independent '
      f'audit: {placement.message}'
    )
  ####
  continuation = build_moc_physical_field_continuation_profile(
    MocPhysicalFieldContinuationProfileRequest(
      field=field,
      sample_points_m=placement.sample_points_m,
      profile_id=(
        'global-closure-solver-owned-physical-field-continuation-v1'
      ),
    )
  )
  if not continuation.converged:
    raise ValueError(
      'solver-owned physical-field continuation did not pass its independent '
      f'audit: {continuation.message}'
    )
  ####
  shock_front_condition = build_moc_physical_field_shock_front_condition(
    MocPhysicalFieldShockFrontConditionRequest(
      continuation_profile=continuation,
      condition_id=(
        'global-closure-solver-owned-physical-field-shock-front-v1'
      ),
    )
  )
  if not shock_front_condition.converged:
    raise ValueError(
      'solver-owned physical-field shock-front condition did not pass its '
      f'independent audit: {shock_front_condition.message}'
    )
  ####
  return MocReflectedDomainGlobalPhysicalFieldHandoff(
    placement=placement,
    continuation_profile=continuation,
    shock_front_condition=shock_front_condition,
  )
####


def solve_reflected_domain_global_coupled_downstream(
  closure: MocReflectedDomainGlobalPhysicalClosureResult,
  *,
  reference_total_temperature_K: float,
  ambient_pressure_Pa: float | None = None,
  downstream_length_m: float = 0.2,
  initial_outlet_height_m: float = 0.05,
  control_section_x_offset_m: float = 0.02,
  control_section_height_m: float = 0.05,
  control_section_sample_count: int = 4,
  axial_station_count: int = 7,
  axial_cell_count: int = 12,
  transverse_cell_count: int = 6,
  max_pseudo_iterations: int = 1200,
  max_shape_iterations: int = 18,
  inlet_boundary_mode: MocReflectedDomainCoupledEulerInletBoundaryMode = (
    MocReflectedDomainCoupledEulerInletBoundaryMode.FULL_STATE_RUSANOV
  ),
  outlet_static_pressure_Pa: float | None = None,
  physical_field_continuation_profile: (
    MocPhysicalFieldContinuationProfileResult | None
  ) = None,
  physical_field_shock_front_condition: (
    MocPhysicalFieldShockFrontConditionResult | None
  ) = None,
) -> MocReflectedDomainGlobalCoupledDownstreamResult:
  """Run one explicitly bound downstream coupled-Euler research candidate."""

  if not isinstance(
    closure,
    MocReflectedDomainGlobalPhysicalClosureResult,
  ):
    return _failure(
      MocReflectedDomainGlobalCoupledDownstreamStatus.INVALID_INPUT,
      'closure must be a MocReflectedDomainGlobalPhysicalClosureResult',
    )
  ####
  if not closure.converged or not closure.physical_closure_verified:
    return _failure(
      MocReflectedDomainGlobalCoupledDownstreamStatus.UPSTREAM_CLOSURE_FAILURE,
      'global coupled downstream solving requires a locally verified global '
      'physical closure',
      closure=closure,
    )
  ####
  try:
    mixed_regime_request = build_reflected_domain_mixed_regime_boundary_request(
      closure,
      ambient_pressure_Pa=ambient_pressure_Pa,
      downstream_length_m=downstream_length_m,
      initial_outlet_height_m=initial_outlet_height_m,
      control_section_x_offset_m=control_section_x_offset_m,
      control_section_height_m=control_section_height_m,
      control_section_sample_count=control_section_sample_count,
      axial_station_count=axial_station_count,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainGlobalCoupledDownstreamStatus
      .MIXED_REGIME_REQUEST_FAILURE,
      f'global coupled downstream mixed-regime request failed: {error}',
      closure=closure,
    )
  ####
  physical_field_handoff: MocReflectedDomainGlobalPhysicalFieldHandoff | None = None
  resolved_continuation_profile = physical_field_continuation_profile
  resolved_shock_front_condition = physical_field_shock_front_condition
  if (
    inlet_boundary_mode
    is MocReflectedDomainCoupledEulerInletBoundaryMode
    .SOLVER_OWNED_PHYSICAL_FIELD_CONTINUATION_PROFILE
    and resolved_continuation_profile is None
    and resolved_shock_front_condition is None
  ):
    try:
      physical_field_handoff = (
        build_reflected_domain_global_solver_owned_physical_field_handoff(
          closure
        )
      )
      resolved_continuation_profile = (
        physical_field_handoff.continuation_profile
      )
      resolved_shock_front_condition = (
        physical_field_handoff.shock_front_condition
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      return _failure(
        MocReflectedDomainGlobalCoupledDownstreamStatus
        .PHYSICAL_FIELD_HANDOFF_FAILURE,
        f'global solver-owned physical-field handoff failed: {error}',
        closure=closure,
        mixed_regime_request=mixed_regime_request,
      )
    ####
  ####
  try:
    coupled_request = build_reflected_domain_coupled_euler_free_boundary_request(
      mixed_regime_request,
      reference_total_temperature_K=reference_total_temperature_K,
      axial_cell_count=axial_cell_count,
      transverse_cell_count=transverse_cell_count,
      max_pseudo_iterations=max_pseudo_iterations,
      max_shape_iterations=max_shape_iterations,
      inlet_boundary_mode=inlet_boundary_mode,
      outlet_static_pressure_Pa=outlet_static_pressure_Pa,
      physical_field_continuation_profile=resolved_continuation_profile,
      physical_field_shock_front_condition=resolved_shock_front_condition,
    )
    coupled_field = solve_reflected_domain_coupled_euler_free_boundary(
      coupled_request
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainGlobalCoupledDownstreamStatus.COUPLED_SOLVER_FAILURE,
      f'global coupled downstream solver raised: {error}',
      closure=closure,
      mixed_regime_request=mixed_regime_request,
      physical_field_handoff=physical_field_handoff,
    )
  ####
  try:
    from exhaust_plume.validation.moc_coupled_euler_free_boundary import (
      measure_reflected_domain_coupled_euler_free_boundary,
    )

    coupled_field_audit = measure_reflected_domain_coupled_euler_free_boundary(
      coupled_field
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainGlobalCoupledDownstreamStatus
      .INDEPENDENT_AUDIT_FAILURE,
      f'global coupled downstream independent audit raised: {error}',
      closure=closure,
      mixed_regime_request=mixed_regime_request,
      coupled_request=coupled_request,
      coupled_field=coupled_field,
      physical_field_handoff=physical_field_handoff,
    )
  ####
  downstream_boundary_response: (
    MocReflectedDomainGlobalCoupledDownstreamBoundaryResponse | None
  ) = None
  try:
    downstream_boundary_response = (
      measure_reflected_domain_global_coupled_downstream_boundary_response(
        closure,
        coupled_field,
      )
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError):
    # The response is an independent research diagnostic.  Preserve the
    # coupled-field status and leave the response unavailable if its operator
    # cannot reconstruct aligned channels; never promote by omission.
    downstream_boundary_response = None
  ####
  if coupled_field.status is (
    MocReflectedDomainCoupledEulerFreeBoundaryStatus
    .CONVERGED_LOCAL_PHYSICAL_CLOSURE
  ) and coupled_field_audit.converged:
    status = (
      MocReflectedDomainGlobalCoupledDownstreamStatus
      .CONVERGED_LOCAL_COUPLED_FIELD
    )
    message = (
      'global closure and downstream coupled-Euler field passed their local '
      'audits; exact solver-owned field handoff was consumed when requested; '
      'global feedback, canonical boundary closure, refinement, external '
      'validation, and downstream overlap residual gates remain open'
    )
  else:
    status = (
      MocReflectedDomainGlobalCoupledDownstreamStatus.COUPLED_SOLVER_FAILURE
    )
    message = (
      'downstream coupled-Euler candidate retained its typed solver/audit '
      f'failure ({coupled_field.status.value}); no global feedback or '
      'lower-fidelity fallback was attempted'
    )
  ####
  return MocReflectedDomainGlobalCoupledDownstreamResult(
    status=status,
    closure=closure,
    mixed_regime_request=mixed_regime_request,
    coupled_request=coupled_request,
    coupled_field=coupled_field,
    coupled_field_audit=coupled_field_audit,
    physical_field_handoff=physical_field_handoff,
    downstream_boundary_response=downstream_boundary_response,
    message=message,
  )
####
