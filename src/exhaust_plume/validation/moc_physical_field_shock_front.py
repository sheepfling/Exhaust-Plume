"""Independent audit for the exact physical-field shock-front condition."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import hypot, isfinite
from typing import Any

from exhaust_plume.models.moc.field_continuation import (
  MocPhysicalFieldContinuationProfileResult,
)
from exhaust_plume.models.moc.physical_cell import (
  MocPhysicalPostShockFieldResult,
)
from exhaust_plume.models.moc.physical_field_shock_front import (
  MocPhysicalFieldShockFrontConditionResult,
  MocPhysicalFieldShockFrontConditionStatus,
)
from exhaust_plume.models.moc.primitives import CharacteristicState
from exhaust_plume.validation.moc_field_continuation import (
  measure_moc_physical_field_continuation_profile,
)

__all__ = (
  'MOC_PHYSICAL_FIELD_SHOCK_FRONT_CONDITION_OPERATOR_ID',
  'MocPhysicalFieldShockFrontConditionAuditStatus',
  'MocPhysicalFieldShockFrontConditionAudit',
  'measure_moc_physical_field_shock_front_condition',
)


MOC_PHYSICAL_FIELD_SHOCK_FRONT_CONDITION_OPERATOR_ID = (
  'op.moc.physical-field.shock-front-condition-audit'
)


class MocPhysicalFieldShockFrontConditionAuditStatus(str, Enum):
  """Outcome of remeasuring the front and neighboring paths."""

  VERIFIED = 'verified-physical-field-shock-front-condition-audit'
  RESULT_FAILURE = 'physical-field-shock-front-condition-result-failure'


@dataclass(frozen=True, slots=True)
class MocPhysicalFieldShockFrontConditionAudit:
  """Independent evidence for the explicit front/neighboring condition."""

  status: MocPhysicalFieldShockFrontConditionAuditStatus
  condition: MocPhysicalFieldShockFrontConditionResult | None
  rederived: bool
  continuation_verified: bool
  field_lineage_verified: bool
  shock_front_verified: bool
  ambient_neighbor_verified: bool
  centerline_neighbor_verified: bool
  continuation_section_verified: bool
  maximum_point_residual_m: float | None = None
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocPhysicalFieldShockFrontConditionAuditStatus,
    ):
      raise TypeError(
        'status must be a MocPhysicalFieldShockFrontConditionAuditStatus'
      )
    if self.condition is not None and not isinstance(
      self.condition,
      MocPhysicalFieldShockFrontConditionResult,
    ):
      raise TypeError(
        'condition must be a MocPhysicalFieldShockFrontConditionResult or None'
      )
    for name in (
      'rederived',
      'continuation_verified',
      'field_lineage_verified',
      'shock_front_verified',
      'ambient_neighbor_verified',
      'centerline_neighbor_verified',
      'continuation_section_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    if self.maximum_point_residual_m is not None:
      value = float(self.maximum_point_residual_m)
      if not isfinite(value) or value < 0.0:
        raise ValueError('maximum_point_residual_m must be finite and nonnegative')
      object.__setattr__(self, 'maximum_point_residual_m', value)
    object.__setattr__(self, 'message', str(self.message))

  @property
  def converged(self) -> bool:
    return self.status is MocPhysicalFieldShockFrontConditionAuditStatus.VERIFIED

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': MOC_PHYSICAL_FIELD_SHOCK_FRONT_CONDITION_OPERATOR_ID,
      'status': self.status.value,
      'converged': self.converged,
      'rederived': self.rederived,
      'continuation_verified': self.continuation_verified,
      'field_lineage_verified': self.field_lineage_verified,
      'shock_front_verified': self.shock_front_verified,
      'ambient_neighbor_verified': self.ambient_neighbor_verified,
      'centerline_neighbor_verified': self.centerline_neighbor_verified,
      'continuation_section_verified': self.continuation_section_verified,
      'maximum_point_residual_m': self.maximum_point_residual_m,
      'physical_closure_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'message': self.message,
    }


def _failure(
  condition: MocPhysicalFieldShockFrontConditionResult | None,
  message: str,
  *,
  continuation_verified: bool = False,
  field_lineage_verified: bool = False,
  shock_front_verified: bool = False,
  ambient_neighbor_verified: bool = False,
  centerline_neighbor_verified: bool = False,
  continuation_section_verified: bool = False,
  maximum_point_residual_m: float | None = None,
) -> MocPhysicalFieldShockFrontConditionAudit:
  return MocPhysicalFieldShockFrontConditionAudit(
    status=MocPhysicalFieldShockFrontConditionAuditStatus.RESULT_FAILURE,
    condition=condition,
    rederived=False,
    continuation_verified=continuation_verified,
    field_lineage_verified=field_lineage_verified,
    shock_front_verified=shock_front_verified,
    ambient_neighbor_verified=ambient_neighbor_verified,
    centerline_neighbor_verified=centerline_neighbor_verified,
    continuation_section_verified=continuation_section_verified,
    maximum_point_residual_m=maximum_point_residual_m,
    message=message,
  )


def _point_residual(
  first: tuple[float, float],
  second: tuple[float, float],
) -> float:
  return hypot(first[0] - second[0], first[1] - second[1])


def _maximum_point_residual(
  reported: tuple[tuple[float, float], ...],
  expected: tuple[tuple[float, float], ...],
) -> float | None:
  if len(reported) != len(expected):
    return None
  return max(
    (_point_residual(first, second) for first, second in zip(reported, expected)),
    default=0.0,
  )


def _ordered_path(
  points: tuple[tuple[float, float], ...],
  tolerance_m: float,
  *,
  centerline: bool = False,
) -> bool:
  return bool(
    len(points) >= 2
    and (not centerline or all(abs(point[1]) <= tolerance_m for point in points))
    and all(
      second[0] > first[0] + tolerance_m
      for first, second in zip(points, points[1:])
    )
  )


def _state_path_verified(
  points: tuple[tuple[float, float], ...],
  states: tuple[Any, ...],
  pressures: tuple[float, ...],
  tolerance_m: float,
) -> bool:
  return bool(
    len(points) == len(states) == len(pressures)
    and all(
      isinstance(state, CharacteristicState)
      and abs(state.x_m - point[0]) <= tolerance_m
      and abs(state.y_m - point[1]) <= tolerance_m
      and isfinite(float(pressure))
      and pressure > 0.0
      for point, state, pressure in zip(points, states, pressures, strict=True)
    )
  )


def _continuation_section_verified(
  continuation: MocPhysicalFieldContinuationProfileResult,
  field: MocPhysicalPostShockFieldResult,
  *,
  position_tolerance_m: float,
  state_tolerance: float,
  pressure_tolerance: float,
) -> bool:
  profile = continuation.profile
  if not continuation.converged or profile is None:
    return False
  if continuation.field is not field:
    return False
  for sample in profile.samples:
    state = field.state_at(
      sample.point_m,
      position_tolerance_m=position_tolerance_m,
    )
    total_pressure = field.total_pressure_at(
      sample.point_m,
      position_tolerance_m=position_tolerance_m,
    )
    static_pressure = field.static_pressure_at(
      sample.point_m,
      position_tolerance_m=position_tolerance_m,
    )
    if state is None or total_pressure is None or static_pressure is None:
      return False
    pressure_scale = max(abs(sample.static_pressure_Pa), abs(static_pressure), 1.0)
    if (
      abs(state.mach - sample.mach) > state_tolerance
      or abs(state.theta_rad - sample.flow_angle_rad) > state_tolerance
      or abs(total_pressure - sample.total_pressure_Pa)
      > pressure_tolerance * max(abs(sample.total_pressure_Pa), 1.0)
      or abs(static_pressure - sample.static_pressure_Pa)
      > pressure_tolerance * pressure_scale
    ):
      return False
  return True


def measure_moc_physical_field_shock_front_condition(
  candidate: MocPhysicalFieldShockFrontConditionResult,
) -> MocPhysicalFieldShockFrontConditionAudit:
  """Rebuild the source front, neighboring paths, and section handoff."""

  if not isinstance(
    candidate,
    MocPhysicalFieldShockFrontConditionResult,
  ):
    return _failure(
      None,
      'candidate must be a MocPhysicalFieldShockFrontConditionResult',
    )
  request = candidate.request
  field = candidate.field
  continuation = candidate.continuation_profile
  expected_continuation = request.continuation_profile
  if not isinstance(continuation, MocPhysicalFieldContinuationProfileResult):
    return _failure(candidate, 'condition retained no continuation profile')
  if continuation != expected_continuation:
    return _failure(
      candidate,
      'condition continuation does not reproduce the request lineage',
    )
  if not isinstance(field, MocPhysicalPostShockFieldResult):
    return _failure(candidate, 'condition retained no physical source field')
  if field is not continuation.field or not field.state_sampling_available:
    return _failure(
      candidate,
      'condition field does not reproduce the continuation source or sampler',
      field_lineage_verified=False,
    )
  continuation_audit = measure_moc_physical_field_continuation_profile(
    continuation
  )
  continuation_verified = continuation_audit.converged
  field_lineage_verified = bool(
    continuation_verified
    and field.converged
    and field.physical_closure_verified
    and field.state_sampling_available
  )
  if not field_lineage_verified:
    return _failure(
      candidate,
      'independent continuation or source-field lineage audit failed',
      continuation_verified=continuation_verified,
      field_lineage_verified=False,
    )

  tolerance_m = request.position_tolerance_m
  shock_points = tuple(field.shock_boundary_points_m)
  ambient_points = tuple(field.ambient_boundary_points_m)
  centerline_points = tuple(field.centerline_boundary_points_m)
  front_residual = _maximum_point_residual(
    candidate.shock_front_points_m,
    shock_points,
  )
  ambient_residual = _maximum_point_residual(
    candidate.ambient_neighbor_points_m,
    ambient_points,
  )
  centerline_residual = _maximum_point_residual(
    candidate.centerline_neighbor_points_m,
    centerline_points,
  )
  maximum_point_residual = max(
    (value for value in (front_residual, ambient_residual, centerline_residual) if value is not None),
    default=None,
  )
  shock_front_verified = bool(
    front_residual is not None
    and front_residual <= tolerance_m
    and len(shock_points) >= 3
    and _ordered_path(shock_points, tolerance_m)
    and field.upstream_shock_coupling_verified
    and field.pressure_loss_verified
    and _state_path_verified(
      shock_points,
      field.upstream_shock_boundary_states,
      field.upstream_shock_boundary_total_pressure_Pa,
      tolerance_m,
    )
    and _state_path_verified(
      shock_points,
      field.post_shock_boundary_states,
      field.post_shock_boundary_total_pressure_Pa,
      tolerance_m,
    )
  )
  ambient = field.ambient_boundary
  ambient_neighbor_verified = bool(
    ambient_residual is not None
    and ambient_residual <= tolerance_m
    and ambient.converged
    and ambient.physical_closure_verified
    and _ordered_path(ambient_points, tolerance_m)
    and _state_path_verified(
      ambient_points,
      tuple(ambient.states),
      tuple(ambient.total_pressure_Pa),
      tolerance_m,
    )
  )
  centerline_neighbor_verified = bool(
    centerline_residual is not None
    and centerline_residual <= tolerance_m
    and _ordered_path(centerline_points, tolerance_m, centerline=True)
    and _state_path_verified(
      centerline_points,
      tuple(field.centerline_boundary_states),
      tuple(field.centerline_boundary_total_pressure_Pa),
      tolerance_m,
    )
  )
  continuation_section_verified = _continuation_section_verified(
    continuation,
    field,
    position_tolerance_m=tolerance_m,
    state_tolerance=request.state_tolerance,
    pressure_tolerance=request.pressure_tolerance,
  )
  verified = bool(
    candidate.status
    is MocPhysicalFieldShockFrontConditionStatus
    .CONVERGED_SHOCK_FRONT_CONDITION
    and candidate.shock_front_verified
    and candidate.ambient_neighbor_verified
    and candidate.centerline_neighbor_verified
    and candidate.continuation_section_verified
    and shock_front_verified
    and ambient_neighbor_verified
    and centerline_neighbor_verified
    and continuation_section_verified
  )
  return MocPhysicalFieldShockFrontConditionAudit(
    status=(
      MocPhysicalFieldShockFrontConditionAuditStatus.VERIFIED
      if verified
      else MocPhysicalFieldShockFrontConditionAuditStatus.RESULT_FAILURE
    ),
    condition=candidate,
    rederived=True,
    continuation_verified=continuation_verified,
    field_lineage_verified=field_lineage_verified,
    shock_front_verified=shock_front_verified,
    ambient_neighbor_verified=ambient_neighbor_verified,
    centerline_neighbor_verified=centerline_neighbor_verified,
    continuation_section_verified=continuation_section_verified,
    maximum_point_residual_m=maximum_point_residual,
    message=(
      'exact shock front, ambient/free-boundary neighbor, centerline neighbor, '
      'and continuation section reproduced independently'
      if verified
      else 'one or more exact front/neighboring-condition checks failed'
    ),
  )
