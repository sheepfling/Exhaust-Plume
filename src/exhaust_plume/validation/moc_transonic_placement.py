"""Independent measurement for bounded transonic/frontier placement."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import exp, hypot, isclose, isfinite, log
from typing import Any

from exhaust_plume.models.moc.chain import MocChainGeometryFidelity
from exhaust_plume.models.moc.primitives import CharacteristicState
from exhaust_plume.models.moc.transonic_placement import (
  MocTransonicPlacementRequest,
  MocTransonicPlacementResult,
  MocTransonicPlacementStatus,
  solve_moc_transonic_placement,
)
from exhaust_plume.models.moc.transonic_transition import (
  MocTransonicShockGeometryAudit,
  measure_moc_transonic_shock_geometry,
)

__all__ = (
  'MocTransonicPlacementAuditStatus',
  'MocTransonicPlacementAudit',
  'measure_moc_transonic_placement',
)


class MocTransonicPlacementAuditStatus(str, Enum):
  """Independent audit outcome for bounded transonic placement."""

  VERIFIED = 'verified-transonic-placement-audit'
  RESULT_FAILURE = 'transonic-placement-result-failure'
####


@dataclass(frozen=True, slots=True)
class MocTransonicPlacementAudit:
  """Re-derived frontier intersection, seam, and geometry evidence."""

  status: MocTransonicPlacementAuditStatus
  result_status: MocTransonicPlacementStatus
  rederived: bool
  frontier_fidelity_verified: bool
  frontier_geometry_verified: bool
  intersection_verified: bool
  state_seam_verified: bool
  pressure_seam_verified: bool
  shock_geometry_verified: bool
  state_seam_residual: float | None
  pressure_seam_residual: float | None
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocTransonicPlacementAuditStatus):
      raise TypeError('status must be a MocTransonicPlacementAuditStatus')
    ####
    if not isinstance(self.result_status, MocTransonicPlacementStatus):
      raise TypeError('result_status must be a MocTransonicPlacementStatus')
    ####
    for name in (
      'rederived',
      'frontier_fidelity_verified',
      'frontier_geometry_verified',
      'intersection_verified',
      'state_seam_verified',
      'pressure_seam_verified',
      'shock_geometry_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    for name in ('state_seam_residual', 'pressure_seam_residual'):
      value = getattr(self, name)
      if value is None:
        continue
      ####
      numeric = float(value)
      if not isfinite(numeric) or numeric < 0.0:
        raise ValueError(f'{name} must be finite and nonnegative when supplied')
      ####
      object.__setattr__(self, name, numeric)
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status is MocTransonicPlacementAuditStatus.VERIFIED
  ####

  @property
  def physical_closure_verified(self) -> bool:
    return False
  ####

  @property
  def production_claim_allowed(self) -> bool:
    return False
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'result_status': self.result_status.value,
      'converged': self.converged,
      'rederived': self.rederived,
      'frontier_fidelity_verified': self.frontier_fidelity_verified,
      'frontier_geometry_verified': self.frontier_geometry_verified,
      'intersection_verified': self.intersection_verified,
      'state_seam_verified': self.state_seam_verified,
      'pressure_seam_verified': self.pressure_seam_verified,
      'shock_geometry_verified': self.shock_geometry_verified,
      'state_seam_residual': self.state_seam_residual,
      'pressure_seam_residual': self.pressure_seam_residual,
      'physical_closure_verified': False,
      'production_claim_allowed': False,
      'claim_status': (
        'research-only-bounded-placement-audit; global reflected closure, '
        'physical shock-cell length, and production promotion remain open'
      ),
      'message': self.message,
    }
  ####
####


def _close(actual: float | None, expected: float | None) -> bool:
  if actual is None or expected is None:
    return actual is expected
  ####
  return bool(isclose(float(actual), float(expected), rel_tol=3.0e-6, abs_tol=1.0e-10))
####


def _point_close(
  actual: tuple[float, float] | None,
  expected: tuple[float, float] | None,
) -> bool:
  if actual is None or expected is None:
    return actual is expected
  ####
  return bool(_close(actual[0], expected[0]) and _close(actual[1], expected[1]))
####


def _state_close(actual: CharacteristicState | None, expected: CharacteristicState | None) -> bool:
  if actual is None or expected is None:
    return actual is expected
  ####
  return bool(
    _close(actual.x_m, expected.x_m)
    and _close(actual.y_m, expected.y_m)
    and _close(actual.theta_rad, expected.theta_rad)
    and _close(actual.mach, expected.mach)
    and _close(actual.gamma, expected.gamma)
  )
####


def _intersection_matches(
  result: MocTransonicPlacementResult,
  expected: MocTransonicPlacementResult,
) -> bool:
  return bool(
    result.transport_segment_index == expected.transport_segment_index
    and result.frontier_segment_index == expected.frontier_segment_index
    and _close(result.transport_fraction, expected.transport_fraction)
    and _close(result.frontier_fraction, expected.frontier_fraction)
    and _point_close(result.intersection_point_m, expected.intersection_point_m)
  )
####


def _frontier_geometry_verified(request: MocTransonicPlacementRequest) -> bool:
  points = tuple(sample.point_m for sample in request.target_frontier)
  return bool(
    len(points) >= 2
    and all(
      hypot(second[0] - first[0], second[1] - first[1])
      > request.position_tolerance_m
      for first, second in zip(points, points[1:])
    )
  )
####


def _independent_seam_residuals(
  result: MocTransonicPlacementResult,
) -> tuple[float | None, float | None]:
  request = result.request
  if (
    result.transport_segment_index is None
    or result.frontier_segment_index is None
    or result.transport_fraction is None
    or result.frontier_fraction is None
    or result.intersection_point_m is None
  ):
    return None, None
  ####
  transport = request.transport.samples
  frontier = request.target_frontier
  transport_start = transport[result.transport_segment_index]
  transport_end = transport[result.transport_segment_index + 1]
  frontier_start = frontier[result.frontier_segment_index]
  frontier_end = frontier[result.frontier_segment_index + 1]
  point = result.intersection_point_m
  transport_state = CharacteristicState(
    x_m=point[0],
    y_m=point[1],
    theta_rad=transport_start.state.theta_rad + result.transport_fraction * (
      transport_end.state.theta_rad - transport_start.state.theta_rad
    ),
    mach=transport_start.state.mach + result.transport_fraction * (
      transport_end.state.mach - transport_start.state.mach
    ),
    gamma=transport_start.state.gamma + result.transport_fraction * (
      transport_end.state.gamma - transport_start.state.gamma
    ),
  )
  frontier_state = CharacteristicState(
    x_m=point[0],
    y_m=point[1],
    theta_rad=frontier_start.state.theta_rad + result.frontier_fraction * (
      frontier_end.state.theta_rad - frontier_start.state.theta_rad
    ),
    mach=frontier_start.state.mach + result.frontier_fraction * (
      frontier_end.state.mach - frontier_start.state.mach
    ),
    gamma=frontier_start.state.gamma + result.frontier_fraction * (
      frontier_end.state.gamma - frontier_start.state.gamma
    ),
  )
  state_residual = max(
    abs(transport_state.theta_rad - frontier_state.theta_rad),
    abs(transport_state.mach - frontier_state.mach),
    abs(transport_state.gamma - frontier_state.gamma),
  )
  transport_pressure = exp(
    (1.0 - result.transport_fraction) * log(transport_start.total_pressure_Pa)
    + result.transport_fraction * log(transport_end.total_pressure_Pa)
  )
  frontier_pressure = exp(
    (1.0 - result.frontier_fraction) * log(frontier_start.total_pressure_Pa)
    + result.frontier_fraction * log(frontier_end.total_pressure_Pa)
  )
  return state_residual, abs(log(transport_pressure / frontier_pressure))
####


def measure_moc_transonic_placement(
  result: MocTransonicPlacementResult,
) -> MocTransonicPlacementAudit:
  """Re-solve and independently remeasure one placement result."""

  if not isinstance(result, MocTransonicPlacementResult):
    raise TypeError('result must be a MocTransonicPlacementResult')
  ####
  expected = solve_moc_transonic_placement(result.request)
  rederived = bool(
    result.status is expected.status
    and _intersection_matches(result, expected)
    and _point_close(result.intersection_point_m, expected.intersection_point_m)
    and _state_close(result.transport_state, expected.transport_state)
    and _state_close(result.frontier_state, expected.frontier_state)
    and _close(
      result.transport_total_pressure_Pa,
      expected.transport_total_pressure_Pa,
    )
    and _close(
      result.frontier_total_pressure_Pa,
      expected.frontier_total_pressure_Pa,
    )
    and _close(result.state_seam_residual, expected.state_seam_residual)
    and _close(result.pressure_seam_residual, expected.pressure_seam_residual)
    and _close(
      result.frontier_tangent_angle_rad,
      expected.frontier_tangent_angle_rad,
    )
    and _close(result.shock_normal_angle_rad, expected.shock_normal_angle_rad)
  )
  frontier_fidelity_verified = (
    result.request.frontier_fidelity is MocChainGeometryFidelity.RESOLVED_PLANAR_MOC
  )
  frontier_geometry_verified = _frontier_geometry_verified(result.request)
  intersection_verified = bool(
    rederived
    and expected.intersection_point_m is not None
    and expected.transport_segment_index is not None
  )
  independent_state, independent_pressure = _independent_seam_residuals(result)
  state_seam_verified = bool(
    independent_state is not None
    and _close(result.state_seam_residual, independent_state)
    and independent_state <= result.request.state_tolerance
  )
  pressure_seam_verified = bool(
    independent_pressure is not None
    and _close(result.pressure_seam_residual, independent_pressure)
    and independent_pressure <= result.request.pressure_tolerance
  )
  shock_geometry_verified = False
  if result.shock_geometry is not None and result.shock_geometry_audit is not None:
    geometry_audit: MocTransonicShockGeometryAudit = (
      measure_moc_transonic_shock_geometry(result.shock_geometry)
    )
    shock_geometry_verified = bool(
      geometry_audit.converged
      and result.shock_geometry_audit.geometry_binding_verified
      and geometry_audit.geometry_binding_verified
    )
  ####
  verified = bool(
    expected.status is MocTransonicPlacementStatus.CONVERGED_BOUNDED_PLACEMENT
    and result.placement_verified
    and rederived
    and frontier_fidelity_verified
    and frontier_geometry_verified
    and intersection_verified
    and state_seam_verified
    and pressure_seam_verified
    and shock_geometry_verified
  )
  return MocTransonicPlacementAudit(
    status=(
      MocTransonicPlacementAuditStatus.VERIFIED
      if verified
      else MocTransonicPlacementAuditStatus.RESULT_FAILURE
    ),
    result_status=result.status,
    rederived=rederived,
    frontier_fidelity_verified=frontier_fidelity_verified,
    frontier_geometry_verified=frontier_geometry_verified,
    intersection_verified=intersection_verified,
    state_seam_verified=state_seam_verified,
    pressure_seam_verified=pressure_seam_verified,
    shock_geometry_verified=shock_geometry_verified,
    state_seam_residual=independent_state,
    pressure_seam_residual=independent_pressure,
    message=(
      'bounded placement, frontier fidelity, seam residuals, and scalar shock '
      'geometry were independently remeasured'
      if verified
      else 'reported bounded placement does not match independent remeasurement'
    ),
  )
####
