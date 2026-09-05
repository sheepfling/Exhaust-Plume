"""Explicit shock-front and neighboring-boundary condition for continuation.

An exact physical post-shock field retains more than a downstream cross-section:
it also carries the fitted shock front, the ambient-pressure boundary, and the
centerline reflection path.  This module binds those three paths to one exact
continuation profile so a downstream finite-volume study cannot reinterpret an
internal profile as an ambient free boundary.  It is a research handoff, not a
canonical closure or production claim.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Any

from exhaust_plume.models.moc.field_continuation import (
  MocPhysicalFieldContinuationProfile,
  MocPhysicalFieldContinuationProfileResult,
)
from exhaust_plume.models.moc.physical_cell import (
  MocPhysicalPostShockFieldResult,
)
from exhaust_plume.models.moc.primitives import CharacteristicState
from exhaust_plume.models.moc.transonic_interface import (
  MocTransonicShockInterfaceSample,
)

__all__ = (
  'MocPhysicalFieldShockFrontConditionStatus',
  'MocPhysicalFieldShockFrontConditionRequest',
  'MocPhysicalFieldShockFrontConditionResult',
  'build_moc_physical_field_shock_front_condition',
)


PHYSICAL_FIELD_SHOCK_FRONT_CONDITION_MODEL = (
  'research-physical-field-shock-front-condition-v1'
)


class MocPhysicalFieldShockFrontConditionStatus(str, Enum):
  """Outcome of binding an exact field's front and neighboring paths."""

  CONVERGED_SHOCK_FRONT_CONDITION = (
    'converged-physical-field-shock-front-condition'
  )
  INVALID_INPUT = 'invalid_input'
  CONTINUATION_FAILURE = 'physical-field-shock-front-continuation-failure'
  FIELD_CLOSURE_FAILURE = 'physical-field-shock-front-field-closure-failure'
  SHOCK_FRONT_FAILURE = 'physical-field-shock-front-geometry-failure'
  AMBIENT_NEIGHBOR_FAILURE = 'physical-field-shock-front-ambient-neighbor-failure'
  CENTERLINE_NEIGHBOR_FAILURE = (
    'physical-field-shock-front-centerline-neighbor-failure'
  )
  COUPLED_INLET_FAILURE = 'physical-field-shock-front-coupled-inlet-failure'
  INDEPENDENT_AUDIT_FAILURE = (
    'physical-field-shock-front-independent-audit-failure'
  )
####


def _finite_point(point: object) -> tuple[float, float]:
  try:
    values = (float(point[0]), float(point[1]))  # type: ignore[index]
  except (IndexError, TypeError, ValueError) as error:
    raise ValueError('shock-front points must contain two coordinates') from error
  ####
  if not all(isfinite(value) for value in values):
    raise ValueError('shock-front points must be finite')
  ####
  return values
####


def _points(points: object) -> tuple[tuple[float, float], ...]:
  try:
    return tuple(_finite_point(point) for point in points)  # type: ignore[union-attr]
  except TypeError as error:
    raise ValueError('boundary point sequences must be iterable') from error
  ####
####


@dataclass(frozen=True, slots=True)
class MocPhysicalFieldShockFrontConditionRequest:
  """Request to bind a field-bound continuation to its physical neighbors."""

  continuation_profile: MocPhysicalFieldContinuationProfileResult
  condition_id: str = 'solver-owned-physical-field-shock-front-condition-v1'
  position_tolerance_m: float = 1.0e-9
  state_tolerance: float = 1.0e-6
  pressure_tolerance: float = 1.0e-8

  def __post_init__(self) -> None:
    if not isinstance(
      self.continuation_profile,
      MocPhysicalFieldContinuationProfileResult,
    ):
      raise TypeError(
        'continuation_profile must be a '
        'MocPhysicalFieldContinuationProfileResult'
      )
    ####
    for name in (
      'position_tolerance_m',
      'state_tolerance',
      'pressure_tolerance',
    ):
      value = float(getattr(self, name))
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      ####
      object.__setattr__(self, name, value)
    ####
    condition_id = str(self.condition_id)
    if not condition_id:
      raise ValueError('condition_id must not be empty')
    ####
    object.__setattr__(self, 'condition_id', condition_id)
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'model': PHYSICAL_FIELD_SHOCK_FRONT_CONDITION_MODEL,
      'condition_id': self.condition_id,
      'position_tolerance_m': self.position_tolerance_m,
      'state_tolerance': self.state_tolerance,
      'pressure_tolerance': self.pressure_tolerance,
      'continuation_profile': self.continuation_profile.as_report(),
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocPhysicalFieldShockFrontConditionResult:
  """Exact front/neighbor context bound to one continuation profile."""

  status: MocPhysicalFieldShockFrontConditionStatus
  request: MocPhysicalFieldShockFrontConditionRequest
  field: MocPhysicalPostShockFieldResult | None = None
  continuation_profile: MocPhysicalFieldContinuationProfileResult | None = None
  shock_front_points_m: tuple[tuple[float, float], ...] = ()
  ambient_neighbor_points_m: tuple[tuple[float, float], ...] = ()
  centerline_neighbor_points_m: tuple[tuple[float, float], ...] = ()
  coupled_inlet_profile: MocPhysicalFieldContinuationProfile | None = None
  shock_front_verified: bool = False
  ambient_neighbor_verified: bool = False
  centerline_neighbor_verified: bool = False
  continuation_section_verified: bool = False
  coupled_inlet_profile_verified: bool = False
  independent_measurement: Any | None = None
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocPhysicalFieldShockFrontConditionStatus,
    ):
      raise TypeError(
        'status must be a MocPhysicalFieldShockFrontConditionStatus'
      )
    ####
    if not isinstance(
      self.request,
      MocPhysicalFieldShockFrontConditionRequest,
    ):
      raise TypeError(
        'request must be a MocPhysicalFieldShockFrontConditionRequest'
      )
    ####
    if self.field is not None and not isinstance(
      self.field,
      MocPhysicalPostShockFieldResult,
    ):
      raise TypeError(
        'field must be a MocPhysicalPostShockFieldResult or None'
      )
    ####
    if self.continuation_profile is not None and not isinstance(
      self.continuation_profile,
      MocPhysicalFieldContinuationProfileResult,
    ):
      raise TypeError(
        'continuation_profile must be a '
        'MocPhysicalFieldContinuationProfileResult or None'
      )
    ####
    if self.coupled_inlet_profile is not None and not isinstance(
      self.coupled_inlet_profile,
      MocPhysicalFieldContinuationProfile,
    ):
      raise TypeError(
        'coupled_inlet_profile must be a '
        'MocPhysicalFieldContinuationProfile or None'
      )
    ####
    for name in (
      'shock_front_points_m',
      'ambient_neighbor_points_m',
      'centerline_neighbor_points_m',
    ):
      object.__setattr__(self, name, _points(getattr(self, name)))
    ####
    for name in (
      'shock_front_verified',
      'ambient_neighbor_verified',
      'centerline_neighbor_verified',
      'continuation_section_verified',
      'coupled_inlet_profile_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    """Whether the front and both neighboring paths passed independent audit."""

    audit = self.independent_measurement
    return bool(
      self.status
      is MocPhysicalFieldShockFrontConditionStatus
      .CONVERGED_SHOCK_FRONT_CONDITION
      and self.field is not None
      and self.continuation_profile is not None
      and self.coupled_inlet_profile is not None
      and self.shock_front_verified
      and self.ambient_neighbor_verified
      and self.centerline_neighbor_verified
      and self.continuation_section_verified
      and self.coupled_inlet_profile_verified
      and audit is not None
      and bool(getattr(audit, 'converged', False))
    )
  ####

  @property
  def physical_closure_verified(self) -> bool:
    """A bound neighboring condition does not close the downstream FV field."""

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

  def as_report(self) -> dict[str, Any]:
    audit = self.independent_measurement
    return {
      'status': self.status.value,
      'model': PHYSICAL_FIELD_SHOCK_FRONT_CONDITION_MODEL,
      'condition_id': self.request.condition_id,
      'converged': self.converged,
      'field_status': None if self.field is None else self.field.status.value,
      'continuation_profile': (
        None
        if self.continuation_profile is None
        else self.continuation_profile.as_report()
      ),
      'shock_front_points_m': [list(point) for point in self.shock_front_points_m],
      'ambient_neighbor_points_m': [
        list(point) for point in self.ambient_neighbor_points_m
      ],
      'centerline_neighbor_points_m': [
        list(point) for point in self.centerline_neighbor_points_m
      ],
      'coupled_inlet_profile': (
        None
        if self.coupled_inlet_profile is None
        else self.coupled_inlet_profile.as_report()
      ),
      'shock_front_verified': self.shock_front_verified,
      'ambient_neighbor_verified': self.ambient_neighbor_verified,
      'centerline_neighbor_verified': self.centerline_neighbor_verified,
      'continuation_section_verified': self.continuation_section_verified,
      'coupled_inlet_profile_verified': self.coupled_inlet_profile_verified,
      'independent_measurement': (
        None
        if audit is None or not hasattr(audit, 'as_report')
        else audit.as_report()
      ),
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'claim_status': (
        'research-only-explicit-shock-front-and-neighboring-boundary-condition; '
        'downstream coupled closure, refinement, and external validation remain open'
      ),
      'request': self.request.as_report(),
      'message': self.message,
    }
  ####
####


def _failure(
  status: MocPhysicalFieldShockFrontConditionStatus,
  request: MocPhysicalFieldShockFrontConditionRequest,
  *,
  field: MocPhysicalPostShockFieldResult | None = None,
  continuation_profile: MocPhysicalFieldContinuationProfileResult | None = None,
  shock_front_points_m: tuple[tuple[float, float], ...] = (),
  ambient_neighbor_points_m: tuple[tuple[float, float], ...] = (),
  centerline_neighbor_points_m: tuple[tuple[float, float], ...] = (),
  coupled_inlet_profile: MocPhysicalFieldContinuationProfile | None = None,
  shock_front_verified: bool = False,
  ambient_neighbor_verified: bool = False,
  centerline_neighbor_verified: bool = False,
  continuation_section_verified: bool = False,
  coupled_inlet_profile_verified: bool = False,
  independent_measurement: Any | None = None,
  message: str,
) -> MocPhysicalFieldShockFrontConditionResult:
  return MocPhysicalFieldShockFrontConditionResult(
    status=status,
    request=request,
    field=field,
    continuation_profile=continuation_profile,
    shock_front_points_m=shock_front_points_m,
    ambient_neighbor_points_m=ambient_neighbor_points_m,
    centerline_neighbor_points_m=centerline_neighbor_points_m,
    coupled_inlet_profile=coupled_inlet_profile,
    shock_front_verified=shock_front_verified,
    ambient_neighbor_verified=ambient_neighbor_verified,
    centerline_neighbor_verified=centerline_neighbor_verified,
    continuation_section_verified=continuation_section_verified,
    coupled_inlet_profile_verified=coupled_inlet_profile_verified,
    independent_measurement=independent_measurement,
    message=message,
  )
####


def _path_is_ordered(
  points: tuple[tuple[float, float], ...],
  *,
  position_tolerance_m: float,
  centerline: bool = False,
) -> bool:
  if len(points) < 2:
    return False
  ####
  if centerline and any(abs(point[1]) > position_tolerance_m for point in points):
    return False
  ####
  return all(
    second[0] > first[0] + position_tolerance_m
    for first, second in zip(points, points[1:])
  )
####


def _state_path_matches(
  points: tuple[tuple[float, float], ...],
  states: tuple[CharacteristicState, ...],
  pressures: tuple[float, ...],
  *,
  position_tolerance_m: float,
) -> bool:
  return bool(
    len(points) == len(states) == len(pressures)
    and all(
      abs(state.x_m - point[0]) <= position_tolerance_m
      and abs(state.y_m - point[1]) <= position_tolerance_m
      and isfinite(float(pressure))
      and pressure > 0.0
      for point, state, pressure in zip(points, states, pressures, strict=True)
    )
  )
####


def _continuation_section_matches(
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
  ####
  if continuation.field is not field:
    return False
  ####
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
    ####
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
    ####
  ####
  return True
####


def _static_pressure(
  state: CharacteristicState,
  total_pressure_Pa: float,
) -> float:
  factor = 1.0 + 0.5 * (state.gamma - 1.0) * state.mach**2
  return float(total_pressure_Pa) / factor ** (
    state.gamma / (state.gamma - 1.0)
  )
####


def _interpolate_boundary_sample(
  points: tuple[tuple[float, float], ...],
  states: tuple[CharacteristicState, ...],
  pressures: tuple[float, ...],
  x_m: float,
  *,
  position_tolerance_m: float,
) -> MocTransonicShockInterfaceSample | None:
  """Interpolate one retained boundary path without x extrapolation."""

  if len(points) != len(states) or len(points) != len(pressures) or len(points) < 2:
    return None
  ####
  if x_m < points[0][0] - position_tolerance_m:
    return None
  ####
  if x_m > points[-1][0] + position_tolerance_m:
    return None
  ####
  for index, (first_point, second_point) in enumerate(zip(points, points[1:])):
    first_state = states[index]
    second_state = states[index + 1]
    first_pressure = float(pressures[index])
    second_pressure = float(pressures[index + 1])
    if abs(x_m - first_point[0]) <= position_tolerance_m:
      return MocTransonicShockInterfaceSample(
        point_m=(x_m, first_point[1]),
        mach=first_state.mach,
        flow_angle_rad=first_state.theta_rad,
        static_pressure_Pa=_static_pressure(first_state, first_pressure),
        total_pressure_Pa=first_pressure,
        gamma=first_state.gamma,
      )
    ####
    if x_m <= second_point[0] + position_tolerance_m:
      span = second_point[0] - first_point[0]
      if span <= position_tolerance_m:
        return None
      ####
      fraction = min(max((x_m - first_point[0]) / span, 0.0), 1.0)
      point = (
        x_m,
        first_point[1] + fraction * (second_point[1] - first_point[1]),
      )
      state = CharacteristicState(
        x_m=x_m,
        y_m=point[1],
        theta_rad=first_state.theta_rad
        + fraction * (second_state.theta_rad - first_state.theta_rad),
        mach=first_state.mach
        + fraction * (second_state.mach - first_state.mach),
        gamma=first_state.gamma
        + fraction * (second_state.gamma - first_state.gamma),
      )
      total_pressure = first_pressure + fraction * (
        second_pressure - first_pressure
      )
      return MocTransonicShockInterfaceSample(
        point_m=point,
        mach=state.mach,
        flow_angle_rad=state.theta_rad,
        static_pressure_Pa=_static_pressure(state, total_pressure),
        total_pressure_Pa=total_pressure,
        gamma=state.gamma,
      )
    ####
  ####
  if abs(x_m - points[-1][0]) <= position_tolerance_m:
    state = states[-1]
    total_pressure = float(pressures[-1])
    return MocTransonicShockInterfaceSample(
      point_m=(x_m, points[-1][1]),
      mach=state.mach,
      flow_angle_rad=state.theta_rad,
      static_pressure_Pa=_static_pressure(state, total_pressure),
      total_pressure_Pa=total_pressure,
      gamma=state.gamma,
    )
  ####
  return None
####


def _derive_coupled_inlet_profile(
  field: MocPhysicalPostShockFieldResult,
  continuation: MocPhysicalFieldContinuationProfileResult,
  request: MocPhysicalFieldShockFrontConditionRequest,
) -> MocPhysicalFieldContinuationProfile | None:
  """Complete an interior section from the retained physical boundaries.

  The section is deliberately assembled only when the requested continuation
  x lies inside both retained boundary paths.  Boundary samples are
  interpolated along the source path; they are never extrapolated or reset to
  ambient thermodynamic values.
  """

  profile = continuation.profile
  if profile is None:
    return None
  ####
  x_m = profile.cross_section_x_m
  ambient = _interpolate_boundary_sample(
    tuple(field.ambient_boundary.points_m),
    tuple(field.ambient_boundary.states),
    tuple(field.ambient_boundary.total_pressure_Pa),
    x_m,
    position_tolerance_m=request.position_tolerance_m,
  )
  centerline = _interpolate_boundary_sample(
    tuple(field.centerline_boundary_points_m),
    tuple(field.centerline_boundary_states),
    tuple(field.centerline_boundary_total_pressure_Pa),
    x_m,
    position_tolerance_m=request.position_tolerance_m,
  )
  if ambient is None or centerline is None:
    return None
  ####
  ordered = sorted(
    [(0, sample) for sample in profile.samples]
    + [(1, centerline), (1, ambient)],
    key=lambda item: (item[1].point_m[1], item[0]),
  )
  unique: list[tuple[int, MocTransonicShockInterfaceSample]] = []
  for priority, sample in ordered:
    if unique and abs(sample.point_m[1] - unique[-1][1].point_m[1]) <= (
      request.position_tolerance_m
    ):
      if priority >= unique[-1][0]:
        unique[-1] = (priority, sample)
      ####
      continue
    ####
    unique.append((priority, sample))
  ####
  if len(unique) < 2:
    return None
  ####
  try:
    return MocPhysicalFieldContinuationProfile(
      samples=tuple(sample for _priority, sample in unique),
      profile_id=f'{request.condition_id}-coupled-inlet-v1',
      position_tolerance_m=request.position_tolerance_m,
      state_tolerance=request.state_tolerance,
      pressure_tolerance=request.pressure_tolerance,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError):
    return None
  ####
####


def build_moc_physical_field_shock_front_condition(
  request: MocPhysicalFieldShockFrontConditionRequest,
) -> MocPhysicalFieldShockFrontConditionResult:
  """Bind the exact field front and neighboring paths to a continuation."""

  if not isinstance(
    request,
    MocPhysicalFieldShockFrontConditionRequest,
  ):
    raise TypeError(
      'request must be a MocPhysicalFieldShockFrontConditionRequest'
    )
  ####
  continuation = request.continuation_profile
  field = continuation.field
  if not continuation.converged or field is None or continuation.profile is None:
    return _failure(
      MocPhysicalFieldShockFrontConditionStatus.CONTINUATION_FAILURE,
      request,
      field=field,
      continuation_profile=continuation,
      message=(
        'shock-front condition requires a converged exact continuation with '
        'its source field retained'
      ),
    )
  ####
  if not (
    field.converged
    and field.physical_closure_verified
    and field.state_sampling_available
  ):
    return _failure(
      MocPhysicalFieldShockFrontConditionStatus.FIELD_CLOSURE_FAILURE,
      request,
      field=field,
      continuation_profile=continuation,
      message=(
        'shock-front condition requires a converged, physically closed field '
        'with complete state sampling'
      ),
    )
  ####

  shock_points = tuple(field.shock_boundary_points_m)
  ambient_points = tuple(field.ambient_boundary_points_m)
  centerline_points = tuple(field.centerline_boundary_points_m)
  shock_verified = bool(
    len(shock_points) >= 3
    and _path_is_ordered(
      shock_points,
      position_tolerance_m=request.position_tolerance_m,
    )
    and field.upstream_shock_coupling_verified
    and field.pressure_loss_verified
    and _state_path_matches(
      shock_points,
      field.upstream_shock_boundary_states,
      field.upstream_shock_boundary_total_pressure_Pa,
      position_tolerance_m=request.position_tolerance_m,
    )
    and _state_path_matches(
      shock_points,
      field.post_shock_boundary_states,
      field.post_shock_boundary_total_pressure_Pa,
      position_tolerance_m=request.position_tolerance_m,
    )
  )
  if not shock_verified:
    return _failure(
      MocPhysicalFieldShockFrontConditionStatus.SHOCK_FRONT_FAILURE,
      request,
      field=field,
      continuation_profile=continuation,
      shock_front_points_m=shock_points,
      ambient_neighbor_points_m=ambient_points,
      centerline_neighbor_points_m=centerline_points,
      message=(
        'source field did not retain a complete ordered, locally coupled '
        'shock front'
      ),
    )
  ####

  ambient = field.ambient_boundary
  ambient_verified = bool(
    ambient.converged
    and ambient.physical_closure_verified
    and _path_is_ordered(
      ambient_points,
      position_tolerance_m=request.position_tolerance_m,
    )
    and len(ambient_points) == len(ambient.states)
    and len(ambient_points) == len(ambient.total_pressure_Pa)
    and _state_path_matches(
      ambient_points,
      tuple(ambient.states),
      tuple(ambient.total_pressure_Pa),
      position_tolerance_m=request.position_tolerance_m,
    )
  )
  if not ambient_verified:
    return _failure(
      MocPhysicalFieldShockFrontConditionStatus.AMBIENT_NEIGHBOR_FAILURE,
      request,
      field=field,
      continuation_profile=continuation,
      shock_front_points_m=shock_points,
      ambient_neighbor_points_m=ambient_points,
      centerline_neighbor_points_m=centerline_points,
      shock_front_verified=True,
      message=(
        'source field did not retain a complete ambient-pressure neighboring '
        'boundary'
      ),
    )
  ####

  centerline_verified = bool(
    _path_is_ordered(
      centerline_points,
      position_tolerance_m=request.position_tolerance_m,
      centerline=True,
    )
    and _state_path_matches(
      centerline_points,
      tuple(field.centerline_boundary_states),
      tuple(field.centerline_boundary_total_pressure_Pa),
      position_tolerance_m=request.position_tolerance_m,
    )
  )
  if not centerline_verified:
    return _failure(
      MocPhysicalFieldShockFrontConditionStatus.CENTERLINE_NEIGHBOR_FAILURE,
      request,
      field=field,
      continuation_profile=continuation,
      shock_front_points_m=shock_points,
      ambient_neighbor_points_m=ambient_points,
      centerline_neighbor_points_m=centerline_points,
      shock_front_verified=True,
      ambient_neighbor_verified=True,
      message=(
        'source field did not retain a complete ordered centerline neighboring '
        'boundary'
      ),
    )
  ####

  continuation_verified = _continuation_section_matches(
    continuation,
    field,
    position_tolerance_m=request.position_tolerance_m,
    state_tolerance=request.state_tolerance,
    pressure_tolerance=request.pressure_tolerance,
  )
  if not continuation_verified:
    return _failure(
      MocPhysicalFieldShockFrontConditionStatus.CONTINUATION_FAILURE,
      request,
      field=field,
      continuation_profile=continuation,
      shock_front_points_m=shock_points,
      ambient_neighbor_points_m=ambient_points,
      centerline_neighbor_points_m=centerline_points,
      shock_front_verified=True,
      ambient_neighbor_verified=True,
      centerline_neighbor_verified=True,
      message=(
        'continuation samples do not reproduce the exact retained source '
        'field at their section'
      ),
    )
  ####

  coupled_inlet_profile = _derive_coupled_inlet_profile(
    field,
    continuation,
    request,
  )
  if coupled_inlet_profile is None:
    return _failure(
      MocPhysicalFieldShockFrontConditionStatus.COUPLED_INLET_FAILURE,
      request,
      field=field,
      continuation_profile=continuation,
      shock_front_points_m=shock_points,
      ambient_neighbor_points_m=ambient_points,
      centerline_neighbor_points_m=centerline_points,
      shock_front_verified=True,
      ambient_neighbor_verified=True,
      centerline_neighbor_verified=True,
      continuation_section_verified=True,
      message=(
        'retained centerline and ambient boundary paths could not complete '
        'the continuation section without extrapolation'
      ),
    )
  ####

  provisional = MocPhysicalFieldShockFrontConditionResult(
    status=(
      MocPhysicalFieldShockFrontConditionStatus
      .CONVERGED_SHOCK_FRONT_CONDITION
    ),
    request=request,
    field=field,
    continuation_profile=continuation,
    shock_front_points_m=shock_points,
    ambient_neighbor_points_m=ambient_points,
    centerline_neighbor_points_m=centerline_points,
    coupled_inlet_profile=coupled_inlet_profile,
    shock_front_verified=True,
    ambient_neighbor_verified=True,
    centerline_neighbor_verified=True,
    continuation_section_verified=True,
    coupled_inlet_profile_verified=True,
    message=(
      'exact shock front, ambient/free-boundary neighbor, centerline neighbor, '
      'and continuation section are retained; downstream coupled closure remains open'
    ),
  )
  try:
    from exhaust_plume.validation.moc_physical_field_shock_front import (
      measure_moc_physical_field_shock_front_condition,
    )

    audit = measure_moc_physical_field_shock_front_condition(provisional)
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocPhysicalFieldShockFrontConditionStatus.INDEPENDENT_AUDIT_FAILURE,
      request,
      field=field,
      continuation_profile=continuation,
      shock_front_points_m=shock_points,
      ambient_neighbor_points_m=ambient_points,
      centerline_neighbor_points_m=centerline_points,
      coupled_inlet_profile=coupled_inlet_profile,
      shock_front_verified=True,
      ambient_neighbor_verified=True,
      centerline_neighbor_verified=True,
      continuation_section_verified=True,
      coupled_inlet_profile_verified=True,
      message=f'independent shock-front condition audit raised: {error}',
    )
  ####
  if not audit.converged:
    return _failure(
      MocPhysicalFieldShockFrontConditionStatus.INDEPENDENT_AUDIT_FAILURE,
      request,
      field=field,
      continuation_profile=continuation,
      shock_front_points_m=shock_points,
      ambient_neighbor_points_m=ambient_points,
      centerline_neighbor_points_m=centerline_points,
      coupled_inlet_profile=coupled_inlet_profile,
      shock_front_verified=True,
      ambient_neighbor_verified=True,
      centerline_neighbor_verified=True,
      continuation_section_verified=True,
      coupled_inlet_profile_verified=True,
      independent_measurement=audit,
      message=f'shock-front condition failed independent audit: {audit.message}',
    )
  ####
  return MocPhysicalFieldShockFrontConditionResult(
    status=(
      MocPhysicalFieldShockFrontConditionStatus
      .CONVERGED_SHOCK_FRONT_CONDITION
    ),
    request=request,
    field=field,
    continuation_profile=continuation,
    shock_front_points_m=shock_points,
    ambient_neighbor_points_m=ambient_points,
    centerline_neighbor_points_m=centerline_points,
    coupled_inlet_profile=coupled_inlet_profile,
    shock_front_verified=True,
    ambient_neighbor_verified=True,
    centerline_neighbor_verified=True,
    continuation_section_verified=True,
    coupled_inlet_profile_verified=True,
    independent_measurement=audit,
    message=(
      'exact shock front, neighboring boundary paths, and continuation '
      'section passed independent audit; downstream coupled closure remains open'
    ),
  )
####
