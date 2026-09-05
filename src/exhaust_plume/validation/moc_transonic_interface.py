"""Independent audit for the bounded transonic shock-interface handoff."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import hypot, isclose, log
from typing import Any

from exhaust_plume.models.moc.primitives import CharacteristicState
from exhaust_plume.models.moc.transonic_interface import (
  MocTransonicShockInterfaceSample,
  MocTransonicShockInterfaceResult,
  MocTransonicShockInterfaceStatus,
)
from exhaust_plume.models.moc.transonic_placement import (
  MocTransonicPlacementStatus,
)
from exhaust_plume.models.moc.transonic_transition import (
  MocTransonicShockGeometryAudit,
  measure_moc_transonic_shock_geometry,
)
from exhaust_plume.validation.moc_transonic_placement import (
  measure_moc_transonic_placement,
)

__all__ = (
  'MocTransonicShockInterfaceAuditStatus',
  'MocTransonicShockInterfaceAudit',
  'measure_moc_transonic_shock_interface',
)


class MocTransonicShockInterfaceAuditStatus(str, Enum):
  """Independent audit outcome for one local interface handoff."""

  VERIFIED = 'verified-transonic-shock-interface-audit'
  RESULT_FAILURE = 'transonic-shock-interface-result-failure'
####


@dataclass(frozen=True, slots=True)
class MocTransonicShockInterfaceAudit:
  """Re-derived placement, geometry, and state-handoff evidence."""

  status: MocTransonicShockInterfaceAuditStatus
  result_status: MocTransonicShockInterfaceStatus
  rederived: bool
  placement_verified: bool
  geometry_verified: bool
  upstream_state_verified: bool
  frontier_state_verified: bool
  upstream_pressure_verified: bool
  frontier_pressure_verified: bool
  downstream_state_verified: bool
  upstream_state_residual: float | None
  frontier_state_residual: float | None
  upstream_pressure_residual: float | None
  frontier_pressure_residual: float | None
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocTransonicShockInterfaceAuditStatus):
      raise TypeError(
        'status must be a MocTransonicShockInterfaceAuditStatus'
      )
    ####
    if not isinstance(self.result_status, MocTransonicShockInterfaceStatus):
      raise TypeError(
        'result_status must be a MocTransonicShockInterfaceStatus'
      )
    ####
    for name in (
      'rederived',
      'placement_verified',
      'geometry_verified',
      'upstream_state_verified',
      'frontier_state_verified',
      'upstream_pressure_verified',
      'frontier_pressure_verified',
      'downstream_state_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    for name in (
      'upstream_state_residual',
      'frontier_state_residual',
      'upstream_pressure_residual',
      'frontier_pressure_residual',
    ):
      value = getattr(self, name)
      if value is None:
        continue
      ####
      numeric = float(value)
      if numeric < 0.0:
        raise ValueError(f'{name} must be nonnegative when supplied')
      ####
      object.__setattr__(self, name, numeric)
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status is MocTransonicShockInterfaceAuditStatus.VERIFIED
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
      'placement_verified': self.placement_verified,
      'geometry_verified': self.geometry_verified,
      'upstream_state_verified': self.upstream_state_verified,
      'frontier_state_verified': self.frontier_state_verified,
      'upstream_pressure_verified': self.upstream_pressure_verified,
      'frontier_pressure_verified': self.frontier_pressure_verified,
      'downstream_state_verified': self.downstream_state_verified,
      'upstream_state_residual': self.upstream_state_residual,
      'frontier_state_residual': self.frontier_state_residual,
      'upstream_pressure_residual': self.upstream_pressure_residual,
      'frontier_pressure_residual': self.frontier_pressure_residual,
      'physical_closure_verified': False,
      'production_claim_allowed': False,
      'claim_status': (
        'research-only-transonic-interface-audit; mixed-regime closure, '
        'physical shock-cell length, and external validation remain open'
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


def _state_close(
  actual: CharacteristicState | None,
  expected: CharacteristicState | None,
) -> bool:
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


def _sample_close(
  actual: MocTransonicShockInterfaceSample | None,
  expected: MocTransonicShockInterfaceSample | None,
) -> bool:
  if actual is None or expected is None:
    return actual is expected
  ####
  return bool(
    _close(actual.point_m[0], expected.point_m[0])
    and _close(actual.point_m[1], expected.point_m[1])
    and _close(actual.mach, expected.mach)
    and _close(actual.flow_angle_rad, expected.flow_angle_rad)
    and _close(actual.static_pressure_Pa, expected.static_pressure_Pa)
    and _close(actual.total_pressure_Pa, expected.total_pressure_Pa)
    and _close(actual.gamma, expected.gamma)
  )
####


def _state_residual(
  actual: CharacteristicState | None,
  expected: CharacteristicState | None,
) -> float | None:
  if actual is None or expected is None:
    return None
  ####
  return max(
    abs(actual.x_m - expected.x_m),
    abs(actual.y_m - expected.y_m),
    abs(actual.theta_rad - expected.theta_rad),
    abs(actual.mach - expected.mach),
    abs(actual.gamma - expected.gamma),
  )
####


def _pressure_residual(actual: float | None, expected: float | None) -> float | None:
  if actual is None or expected is None:
    return None
  ####
  if actual <= 0.0 or expected <= 0.0:
    return None
  ####
  return abs(log(float(actual) / float(expected)))
####


def measure_moc_transonic_shock_interface(
  result: MocTransonicShockInterfaceResult,
) -> MocTransonicShockInterfaceAudit:
  """Re-derive the placement-bound interface without trusting its fields."""

  if not isinstance(result, MocTransonicShockInterfaceResult):
    raise TypeError('result must be a MocTransonicShockInterfaceResult')
  ####
  placement = result.request.placement
  placement_audit = measure_moc_transonic_placement(placement)
  placement_verified = bool(
    placement_audit.converged
    and placement.status is MocTransonicPlacementStatus
    .CONVERGED_BOUNDED_PLACEMENT
    and placement.placement_verified
  )
  geometry = result.shock_geometry
  geometry_audit = result.shock_geometry_audit
  point = placement.intersection_point_m
  shock_state = None if geometry is None else geometry.request.shock_state
  expected_upstream = None
  expected_upstream_sample = None
  expected_downstream_sample = None
  if shock_state is not None and point is not None:
    expected_upstream = CharacteristicState(
      x_m=point[0],
      y_m=point[1],
      theta_rad=shock_state.upstream_flow_angle_rad,
      mach=shock_state.upstream_mach,
      gamma=shock_state.gamma,
    )
    expected_upstream_sample = MocTransonicShockInterfaceSample(
      point_m=point,
      mach=shock_state.upstream_mach,
      flow_angle_rad=shock_state.upstream_flow_angle_rad,
      static_pressure_Pa=shock_state.upstream_static_pressure_Pa,
      total_pressure_Pa=shock_state.upstream_total_pressure_Pa,
      gamma=shock_state.gamma,
    )
    expected_downstream_sample = MocTransonicShockInterfaceSample(
      point_m=point,
      mach=shock_state.downstream_mach,
      flow_angle_rad=shock_state.upstream_flow_angle_rad,
      static_pressure_Pa=shock_state.downstream_static_pressure_Pa,
      total_pressure_Pa=shock_state.downstream_total_pressure_Pa,
      gamma=shock_state.gamma,
    )
  ####
  upstream_state_residual = _state_residual(
    placement.transport_state,
    expected_upstream,
  )
  frontier_state_residual = _state_residual(
    placement.frontier_state,
    expected_upstream,
  )
  upstream_pressure_residual = _pressure_residual(
    placement.transport_total_pressure_Pa,
    None if shock_state is None else shock_state.upstream_total_pressure_Pa,
  )
  frontier_pressure_residual = _pressure_residual(
    placement.frontier_total_pressure_Pa,
    None if shock_state is None else shock_state.upstream_total_pressure_Pa,
  )
  upstream_state_verified = bool(
    expected_upstream is not None
    and _state_close(placement.transport_state, expected_upstream)
  )
  frontier_state_verified = bool(
    expected_upstream is not None
    and _state_close(placement.frontier_state, expected_upstream)
  )
  upstream_pressure_verified = bool(
    upstream_pressure_residual is not None
    and upstream_pressure_residual <= result.request.pressure_tolerance
  )
  frontier_pressure_verified = bool(
    frontier_pressure_residual is not None
    and frontier_pressure_residual <= result.request.pressure_tolerance
  )
  geometry_rederived = False
  if geometry is not None and geometry_audit is not None:
    independent_geometry_audit: MocTransonicShockGeometryAudit = (
      measure_moc_transonic_shock_geometry(geometry)
    )
    geometry_rederived = bool(
      independent_geometry_audit.converged
      and geometry_audit.converged
      and geometry_audit.geometry_binding_verified
      and independent_geometry_audit.geometry_binding_verified
      and point is not None
      and hypot(
        geometry.shock_point_m[0] - point[0],
        geometry.shock_point_m[1] - point[1],
      ) <= result.request.position_tolerance_m
    )
  ####
  downstream_state_verified = bool(
    shock_state is not None
    and result.downstream_sample is not None
    and _sample_close(result.downstream_sample, expected_downstream_sample)
    and shock_state.upstream_supersonic
    and shock_state.downstream_subsonic
    and 0.0 < shock_state.total_pressure_ratio < 1.0
  )
  rederived = bool(
    result.upstream_sample is not None
    and _sample_close(result.upstream_sample, expected_upstream_sample)
    and result.status is MocTransonicShockInterfaceStatus
    .CONVERGED_BOUNDED_INTERFACE
  )
  verified = bool(
    placement_verified
    and geometry_rederived
    and upstream_state_verified
    and frontier_state_verified
    and upstream_pressure_verified
    and frontier_pressure_verified
    and downstream_state_verified
    and rederived
  )
  return MocTransonicShockInterfaceAudit(
    status=(
      MocTransonicShockInterfaceAuditStatus.VERIFIED
      if verified
      else MocTransonicShockInterfaceAuditStatus.RESULT_FAILURE
    ),
    result_status=result.status,
    rederived=rederived,
    placement_verified=placement_verified,
    geometry_verified=geometry_rederived,
    upstream_state_verified=upstream_state_verified,
    frontier_state_verified=frontier_state_verified,
    upstream_pressure_verified=upstream_pressure_verified,
    frontier_pressure_verified=frontier_pressure_verified,
    downstream_state_verified=downstream_state_verified,
    upstream_state_residual=upstream_state_residual,
    frontier_state_residual=frontier_state_residual,
    upstream_pressure_residual=upstream_pressure_residual,
    frontier_pressure_residual=frontier_pressure_residual,
    message=(
      'placement, scalar geometry, upstream/frontier lineage, and downstream '
      'state were independently rederived'
      if verified
      else 'reported shock-interface handoff does not match independent remeasurement'
    ),
  )
####
