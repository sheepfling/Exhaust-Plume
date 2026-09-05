"""Bounded solver-owned transonic placement against a resolved frontier.

The transonic attachment and characteristic transport seams establish a
bounded upstream path, but neither chooses where that path meets a neighboring
field.  This module performs that next geometric operation using only a typed
resolved-planar-MOC frontier.  It searches for an in-domain segment
intersection, interpolates the two retained state/pressure lineages at that
intersection, and binds the scalar shock state to the neighboring-frontier
tangent.

The result is a placement evidence seam, not global reflected closure.  It
does not solve the ambient/free boundary, centerline reflection, mixed-regime
Euler field, or a physical shock-cell length.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import atan2, exp, hypot, isfinite, log, pi, sin, cos
from typing import Any

from exhaust_plume.models.moc.chain import (
  MocChainBoundaryKind,
  MocChainBoundarySample,
  MocChainGeometryFidelity,
  MocChainTerminationDecision,
  MocChainTerminationReason,
)
from exhaust_plume.models.moc.primitives import CharacteristicState
from exhaust_plume.models.moc.transonic_attachment import (
  MocTransonicShockFieldAttachmentResult,
)
from exhaust_plume.models.moc.transonic_transition import (
  MocTransonicShockGeometryAudit,
  MocTransonicShockGeometryRequest,
  MocTransonicShockGeometryResult,
  measure_moc_transonic_shock_geometry,
  solve_moc_transonic_shock_geometry,
)
from exhaust_plume.models.moc.euler_entropy_characteristic_transport import (
  MocTransonicCharacteristicTransportResult,
)

__all__ = (
  'MocTransonicPlacementStatus',
  'MocTransonicPlacementRequest',
  'MocTransonicPlacementResult',
  'solve_moc_transonic_placement',
)


class MocTransonicPlacementStatus(str, Enum):
  """Outcome of one bounded transonic/frontier placement attempt."""

  CONVERGED_BOUNDED_PLACEMENT = 'converged-bounded-transonic-placement'
  INVALID_INPUT = 'invalid_input'
  TRANSPORT_REQUIRED = 'transonic-placement-transport-required'
  FRONTIER_REQUIRED = 'transonic-placement-frontier-required'
  FRONTIER_FIDELITY_FAILURE = 'transonic-placement-frontier-fidelity-failure'
  FRONTIER_GEOMETRY_FAILURE = 'transonic-placement-frontier-geometry-failure'
  FRONTIER_NOT_REACHED = 'transonic-placement-frontier-not-reached'
  INTERSECTION_AMBIGUOUS = 'transonic-placement-intersection-ambiguous'
  STATE_SEAM_FAILURE = 'transonic-placement-state-seam-failure'
  PRESSURE_SEAM_FAILURE = 'transonic-placement-pressure-seam-failure'
  SHOCK_GEOMETRY_FAILURE = 'transonic-placement-shock-geometry-failure'
####


def _finite(name: str, value: object) -> float:
  try:
    numeric = float(value)
  except (TypeError, ValueError) as error:
    raise ValueError(f'{name} must be numeric') from error
  ####
  if not isfinite(numeric):
    raise ValueError(f'{name} must be finite')
  ####
  return numeric
####


def _cross(first: tuple[float, float], second: tuple[float, float]) -> float:
  return first[0] * second[1] - first[1] * second[0]
####


def _wrapped_angle_residual(first: float, second: float) -> float:
  return abs(atan2(sin(first - second), cos(first - second)))
####


def _intersect_segments(
  first_start: tuple[float, float],
  first_end: tuple[float, float],
  second_start: tuple[float, float],
  second_end: tuple[float, float],
  *,
  position_tolerance_m: float,
) -> tuple[float, float, tuple[float, float]] | None:
  first_direction = (
    first_end[0] - first_start[0],
    first_end[1] - first_start[1],
  )
  second_direction = (
    second_end[0] - second_start[0],
    second_end[1] - second_start[1],
  )
  first_length = hypot(*first_direction)
  second_length = hypot(*second_direction)
  if first_length <= position_tolerance_m or second_length <= position_tolerance_m:
    return None
  ####
  denominator = _cross(first_direction, second_direction)
  scale = max(first_length * second_length, 1.0)
  if abs(denominator) <= position_tolerance_m / scale:
    return None
  ####
  between = (
    second_start[0] - first_start[0],
    second_start[1] - first_start[1],
  )
  first_fraction = _cross(between, second_direction) / denominator
  second_fraction = _cross(between, first_direction) / denominator
  fraction_tolerance = position_tolerance_m / max(first_length, second_length, 1.0)
  if not (
    -fraction_tolerance <= first_fraction <= 1.0 + fraction_tolerance
    and -fraction_tolerance <= second_fraction <= 1.0 + fraction_tolerance
  ):
    return None
  ####
  first_fraction = min(1.0, max(0.0, first_fraction))
  second_fraction = min(1.0, max(0.0, second_fraction))
  point = (
    first_start[0] + first_fraction * first_direction[0],
    first_start[1] + first_fraction * first_direction[1],
  )
  return first_fraction, second_fraction, point
####


def _interpolate_state(
  first: CharacteristicState,
  second: CharacteristicState,
  fraction: float,
  point: tuple[float, float],
) -> CharacteristicState:
  return CharacteristicState(
    x_m=point[0],
    y_m=point[1],
    theta_rad=first.theta_rad + fraction * (second.theta_rad - first.theta_rad),
    mach=first.mach + fraction * (second.mach - first.mach),
    gamma=first.gamma + fraction * (second.gamma - first.gamma),
  )
####


def _interpolate_log_pressure(
  first: float,
  second: float,
  fraction: float,
) -> float:
  return exp((1.0 - fraction) * log(first) + fraction * log(second))
####


@dataclass(frozen=True, slots=True)
class MocTransonicPlacementRequest:
  """Inputs for bounded intersection of a transported path and frontier."""

  transport: MocTransonicCharacteristicTransportResult
  target_frontier: tuple[MocChainBoundarySample, ...]
  frontier_kind: MocChainBoundaryKind
  frontier_fidelity: MocChainGeometryFidelity
  frontier_source: str
  position_tolerance_m: float = 1.0e-9
  state_tolerance: float = 1.0e-6
  pressure_tolerance: float = 1.0e-8
  normal_alignment_tolerance_rad: float = 1.0e-2
  flux_tolerance: float = 1.0e-8

  def __post_init__(self) -> None:
    if not isinstance(
      self.transport,
      MocTransonicCharacteristicTransportResult,
    ):
      raise TypeError(
        'transport must be a MocTransonicCharacteristicTransportResult'
      )
    ####
    frontier = tuple(self.target_frontier)
    if any(not isinstance(sample, MocChainBoundarySample) for sample in frontier):
      raise TypeError(
        'target_frontier must contain MocChainBoundarySample values'
      )
    ####
    if len(frontier) < 2:
      raise ValueError('target_frontier must contain at least two samples')
    ####
    if not isinstance(self.frontier_kind, MocChainBoundaryKind):
      raise TypeError('frontier_kind must be a MocChainBoundaryKind')
    ####
    if self.frontier_kind not in (
      MocChainBoundaryKind.TERMINAL_CHARACTERISTIC_TRACE,
      MocChainBoundaryKind.POST_SHOCK_FIELD_PERIMETER,
    ):
      raise ValueError(
        'frontier_kind must identify a characteristic trace or post-shock '
        'field perimeter'
      )
    ####
    if not isinstance(self.frontier_fidelity, MocChainGeometryFidelity):
      raise TypeError('frontier_fidelity must be a MocChainGeometryFidelity')
    ####
    source = str(self.frontier_source)
    if not source:
      raise ValueError('frontier_source must be non-empty')
    ####
    for name in (
      'position_tolerance_m',
      'state_tolerance',
      'pressure_tolerance',
      'normal_alignment_tolerance_rad',
      'flux_tolerance',
    ):
      value = _finite(name, getattr(self, name))
      if value <= 0.0:
        raise ValueError(f'{name} must be positive')
      ####
      object.__setattr__(self, name, value)
    ####
    object.__setattr__(self, 'target_frontier', frontier)
    object.__setattr__(self, 'frontier_source', source)
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'transport_status': self.transport.status.value,
      'transport_verified': self.transport.bounded_transport_verified,
      'frontier_kind': self.frontier_kind.value,
      'frontier_fidelity': self.frontier_fidelity.value,
      'frontier_source': self.frontier_source,
      'frontier_sample_count': len(self.target_frontier),
      'position_tolerance_m': self.position_tolerance_m,
      'state_tolerance': self.state_tolerance,
      'pressure_tolerance': self.pressure_tolerance,
      'normal_alignment_tolerance_rad': self.normal_alignment_tolerance_rad,
      'flux_tolerance': self.flux_tolerance,
      'model': 'research-solver-owned-transonic-frontier-placement-v1',
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocTransonicPlacementResult:
  """Bounded placement evidence with explicit global-closure stops."""

  status: MocTransonicPlacementStatus
  request: MocTransonicPlacementRequest
  transport_segment_index: int | None = None
  frontier_segment_index: int | None = None
  transport_fraction: float | None = None
  frontier_fraction: float | None = None
  intersection_point_m: tuple[float, float] | None = None
  transport_state: CharacteristicState | None = None
  frontier_state: CharacteristicState | None = None
  transport_total_pressure_Pa: float | None = None
  frontier_total_pressure_Pa: float | None = None
  state_seam_residual: float | None = None
  pressure_seam_residual: float | None = None
  frontier_tangent_angle_rad: float | None = None
  shock_normal_angle_rad: float | None = None
  shock_geometry: MocTransonicShockGeometryResult | None = None
  shock_geometry_audit: MocTransonicShockGeometryAudit | None = None
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocTransonicPlacementStatus):
      raise TypeError('status must be a MocTransonicPlacementStatus')
    ####
    if not isinstance(self.request, MocTransonicPlacementRequest):
      raise TypeError('request must be a MocTransonicPlacementRequest')
    ####
    for name in ('transport_segment_index', 'frontier_segment_index'):
      value = getattr(self, name)
      if value is not None and (
        isinstance(value, bool) or not isinstance(value, int) or value < 0
      ):
        raise ValueError(f'{name} must be a nonnegative integer or None')
      ####
    ####
    for name in ('transport_fraction', 'frontier_fraction'):
      value = getattr(self, name)
      if value is not None:
        numeric = _finite(name, value)
        if not 0.0 <= numeric <= 1.0:
          raise ValueError(f'{name} must be in the [0, 1] interval')
        ####
        object.__setattr__(self, name, numeric)
      ####
    ####
    if self.intersection_point_m is not None:
      point = tuple(
        _finite(f'intersection_point_m[{index}]', value)
        for index, value in enumerate(self.intersection_point_m)
      )
      if len(point) != 2:
        raise ValueError('intersection_point_m must contain two coordinates')
      ####
      object.__setattr__(self, 'intersection_point_m', point)
    ####
    for name in ('transport_state', 'frontier_state'):
      value = getattr(self, name)
      if value is not None and not isinstance(value, CharacteristicState):
        raise TypeError(f'{name} must be a CharacteristicState or None')
      ####
    ####
    for name in (
      'transport_total_pressure_Pa',
      'frontier_total_pressure_Pa',
    ):
      value = getattr(self, name)
      if value is not None:
        numeric = _finite(name, value)
        if numeric <= 0.0:
          raise ValueError(f'{name} must be positive when supplied')
        ####
        object.__setattr__(self, name, numeric)
      ####
    ####
    for name in ('state_seam_residual', 'pressure_seam_residual'):
      value = getattr(self, name)
      if value is not None:
        numeric = _finite(name, value)
        if numeric < 0.0:
          raise ValueError(f'{name} must be nonnegative when supplied')
        ####
        object.__setattr__(self, name, numeric)
      ####
    ####
    for name in ('frontier_tangent_angle_rad', 'shock_normal_angle_rad'):
      value = getattr(self, name)
      if value is not None:
        object.__setattr__(self, name, _finite(name, value))
      ####
    ####
    if (self.shock_geometry is None) != (self.shock_geometry_audit is None):
      raise ValueError(
        'shock_geometry and shock_geometry_audit must be supplied together'
      )
    ####
    if self.shock_geometry is not None and not isinstance(
      self.shock_geometry,
      MocTransonicShockGeometryResult,
    ):
      raise TypeError('shock_geometry must be a typed geometry result or None')
    ####
    if self.shock_geometry_audit is not None and not isinstance(
      self.shock_geometry_audit,
      MocTransonicShockGeometryAudit,
    ):
      raise TypeError('shock_geometry_audit must be a typed audit or None')
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def placement_verified(self) -> bool:
    return bool(
      self.status is MocTransonicPlacementStatus.CONVERGED_BOUNDED_PLACEMENT
      and self.request.frontier_fidelity
      is MocChainGeometryFidelity.RESOLVED_PLANAR_MOC
      and self.request.transport.bounded_transport_verified
      and self.state_seam_residual is not None
      and self.state_seam_residual <= self.request.state_tolerance
      and self.pressure_seam_residual is not None
      and self.pressure_seam_residual <= self.request.pressure_tolerance
      and self.shock_geometry is not None
      and self.shock_geometry.geometry_verified
      and self.shock_geometry_audit is not None
      and self.shock_geometry_audit.geometry_binding_verified
    )
  ####

  @property
  def physical_closure_verified(self) -> bool:
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
      MocChainTerminationReason.INVALID_INPUT
      if self.status is MocTransonicPlacementStatus.INVALID_INPUT
      else MocChainTerminationReason.FIDELITY_NOT_ALLOWED
      if self.placement_verified
      else MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
    )
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=reason,
      message=self.message,
      diagnostics={
        'placement_status': self.status.value,
        'placement_verified': self.placement_verified,
        'frontier_kind': self.request.frontier_kind.value,
        'frontier_fidelity': self.request.frontier_fidelity.value,
        'physical_closure_verified': False,
        'chain_promotion_blocked': True,
        'production_claim_allowed': False,
        'required_next_gate': (
          'globally-coupled-reflected-mixed-regime-closure-and-independent-'
          'refinement-before-physical-shock-cell-promotion'
        ),
      },
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'placement_verified': self.placement_verified,
      'physical_closure_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'transport_segment_index': self.transport_segment_index,
      'frontier_segment_index': self.frontier_segment_index,
      'transport_fraction': self.transport_fraction,
      'frontier_fraction': self.frontier_fraction,
      'intersection_point_m': (
        None
        if self.intersection_point_m is None
        else list(self.intersection_point_m)
      ),
      'transport_state': (
        None
        if self.transport_state is None
        else {
          'x_m': self.transport_state.x_m,
          'y_m': self.transport_state.y_m,
          'theta_rad': self.transport_state.theta_rad,
          'mach': self.transport_state.mach,
          'gamma': self.transport_state.gamma,
        }
      ),
      'frontier_state': (
        None
        if self.frontier_state is None
        else {
          'x_m': self.frontier_state.x_m,
          'y_m': self.frontier_state.y_m,
          'theta_rad': self.frontier_state.theta_rad,
          'mach': self.frontier_state.mach,
          'gamma': self.frontier_state.gamma,
        }
      ),
      'transport_total_pressure_Pa': self.transport_total_pressure_Pa,
      'frontier_total_pressure_Pa': self.frontier_total_pressure_Pa,
      'state_seam_residual': self.state_seam_residual,
      'pressure_seam_residual': self.pressure_seam_residual,
      'frontier_tangent_angle_rad': self.frontier_tangent_angle_rad,
      'shock_normal_angle_rad': self.shock_normal_angle_rad,
      'shock_geometry': (
        None
        if self.shock_geometry is None
        else self.shock_geometry.as_report()
      ),
      'shock_geometry_audit': (
        None
        if self.shock_geometry_audit is None
        else self.shock_geometry_audit.as_report()
      ),
      'request': self.request.as_report(),
      'chain_termination_decision': self.as_chain_termination_decision().as_report(),
      'claim_status': (
        'research-only-bounded-transonic-placement; global reflected closure, '
        'physical shock-cell length, external validation, and production '
        'promotion remain open'
      ),
      'message': self.message,
    }
  ####
####


def _failure(
  status: MocTransonicPlacementStatus,
  request: MocTransonicPlacementRequest,
  *,
  transport_segment_index: int | None = None,
  frontier_segment_index: int | None = None,
  transport_fraction: float | None = None,
  frontier_fraction: float | None = None,
  intersection_point_m: tuple[float, float] | None = None,
  transport_state: CharacteristicState | None = None,
  frontier_state: CharacteristicState | None = None,
  transport_total_pressure_Pa: float | None = None,
  frontier_total_pressure_Pa: float | None = None,
  state_seam_residual: float | None = None,
  pressure_seam_residual: float | None = None,
  frontier_tangent_angle_rad: float | None = None,
  shock_normal_angle_rad: float | None = None,
  shock_geometry: MocTransonicShockGeometryResult | None = None,
  shock_geometry_audit: MocTransonicShockGeometryAudit | None = None,
  message: str,
) -> MocTransonicPlacementResult:
  return MocTransonicPlacementResult(
    status=status,
    request=request,
    transport_segment_index=transport_segment_index,
    frontier_segment_index=frontier_segment_index,
    transport_fraction=transport_fraction,
    frontier_fraction=frontier_fraction,
    intersection_point_m=intersection_point_m,
    transport_state=transport_state,
    frontier_state=frontier_state,
    transport_total_pressure_Pa=transport_total_pressure_Pa,
    frontier_total_pressure_Pa=frontier_total_pressure_Pa,
    state_seam_residual=state_seam_residual,
    pressure_seam_residual=pressure_seam_residual,
    frontier_tangent_angle_rad=frontier_tangent_angle_rad,
    shock_normal_angle_rad=shock_normal_angle_rad,
    shock_geometry=shock_geometry,
    shock_geometry_audit=shock_geometry_audit,
    message=message,
  )
####


def solve_moc_transonic_placement(
  request: MocTransonicPlacementRequest,
) -> MocTransonicPlacementResult:
  """Search for one bounded transport/frontier intersection and audit it."""

  if not isinstance(request, MocTransonicPlacementRequest):
    raise TypeError('request must be a MocTransonicPlacementRequest')
  ####
  transport = request.transport
  if not transport.bounded_transport_verified:
    return _failure(
      MocTransonicPlacementStatus.TRANSPORT_REQUIRED,
      request,
      message=(
        'placement requires bounded characteristic transport with at least '
        'one verified field-boundary segment'
      ),
    )
  ####
  if request.frontier_fidelity is not MocChainGeometryFidelity.RESOLVED_PLANAR_MOC:
    return _failure(
      MocTransonicPlacementStatus.FRONTIER_FIDELITY_FAILURE,
      request,
      message=(
        'placement requires a resolved-planar-MOC neighboring frontier; '
        'prescribed and reduced-order boundaries cannot satisfy placement'
      ),
    )
  ####
  transport_points = tuple(sample.point_m for sample in transport.samples)
  frontier_points = tuple(sample.point_m for sample in request.target_frontier)
  if any(
    hypot(second[0] - first[0], second[1] - first[1])
    <= request.position_tolerance_m
    for first, second in zip(frontier_points, frontier_points[1:])
  ):
    return _failure(
      MocTransonicPlacementStatus.FRONTIER_GEOMETRY_FAILURE,
      request,
      message=(
        'resolved neighboring frontier contains a degenerate segment and '
        'cannot provide a placement tangent'
      ),
    )
  ####
  candidates: list[tuple[int, int, float, float, tuple[float, float]]] = []
  for transport_index, (first, second) in enumerate(
    zip(transport_points, transport_points[1:]),
  ):
    for frontier_index, (frontier_first, frontier_second) in enumerate(
      zip(frontier_points, frontier_points[1:]),
    ):
      intersection = _intersect_segments(
        first,
        second,
        frontier_first,
        frontier_second,
        position_tolerance_m=request.position_tolerance_m,
      )
      if intersection is not None:
        transport_fraction, frontier_fraction, point = intersection
        candidates.append(
          (
            transport_index,
            frontier_index,
            transport_fraction,
            frontier_fraction,
            point,
          )
        )
      ####
    ####
  ####
  unique_candidates: list[tuple[int, int, float, float, tuple[float, float]]] = []
  for candidate in candidates:
    if not any(
      hypot(
        candidate[4][0] - previous[4][0],
        candidate[4][1] - previous[4][1],
      )
      <= request.position_tolerance_m
      for previous in unique_candidates
    ):
      unique_candidates.append(candidate)
    ####
  ####
  candidates = unique_candidates
  if not candidates:
    return _failure(
      MocTransonicPlacementStatus.FRONTIER_NOT_REACHED,
      request,
      message=(
        'transport reached only its retained bounded domain and did not '
        'intersect the supplied resolved neighboring frontier'
      ),
    )
  ####
  if len(candidates) > 1:
    return _failure(
      MocTransonicPlacementStatus.INTERSECTION_AMBIGUOUS,
      request,
      message=(
        'transport and neighboring frontier have multiple in-domain '
        'intersections; placement requires one ordered shock interface'
      ),
    )
  ####
  (
    transport_index,
    frontier_index,
    transport_fraction,
    frontier_fraction,
    point,
  ) = candidates[0]
  transport_start = transport.samples[transport_index]
  transport_end = transport.samples[transport_index + 1]
  frontier_start = request.target_frontier[frontier_index]
  frontier_end = request.target_frontier[frontier_index + 1]
  transport_state = _interpolate_state(
    transport_start.state,
    transport_end.state,
    transport_fraction,
    point,
  )
  frontier_state = _interpolate_state(
    frontier_start.state,
    frontier_end.state,
    frontier_fraction,
    point,
  )
  transport_pressure = _interpolate_log_pressure(
    transport_start.total_pressure_Pa,
    transport_end.total_pressure_Pa,
    transport_fraction,
  )
  frontier_pressure = _interpolate_log_pressure(
    frontier_start.total_pressure_Pa,
    frontier_end.total_pressure_Pa,
    frontier_fraction,
  )
  state_residual = max(
    abs(transport_state.theta_rad - frontier_state.theta_rad),
    abs(transport_state.mach - frontier_state.mach),
    abs(transport_state.gamma - frontier_state.gamma),
  )
  pressure_residual = abs(log(transport_pressure / frontier_pressure))
  common = {
    'transport_segment_index': transport_index,
    'frontier_segment_index': frontier_index,
    'transport_fraction': transport_fraction,
    'frontier_fraction': frontier_fraction,
    'intersection_point_m': point,
    'transport_state': transport_state,
    'frontier_state': frontier_state,
    'transport_total_pressure_Pa': transport_pressure,
    'frontier_total_pressure_Pa': frontier_pressure,
    'state_seam_residual': state_residual,
    'pressure_seam_residual': pressure_residual,
  }
  if state_residual > request.state_tolerance:
    return _failure(
      MocTransonicPlacementStatus.STATE_SEAM_FAILURE,
      request,
      **common,
      message='transport and neighboring-frontier state lineages disagree at the intersection',
    )
  ####
  if pressure_residual > request.pressure_tolerance:
    return _failure(
      MocTransonicPlacementStatus.PRESSURE_SEAM_FAILURE,
      request,
      **common,
      message='transport and neighboring-frontier total-pressure lineages disagree at the intersection',
    )
  ####
  frontier_delta = (
    frontier_end.point_m[0] - frontier_start.point_m[0],
    frontier_end.point_m[1] - frontier_start.point_m[1],
  )
  tangent = atan2(frontier_delta[1], frontier_delta[0])
  base_normal = tangent + 0.5 * pi
  attachment: MocTransonicShockFieldAttachmentResult = transport.request.attachment
  attachment_geometry = attachment.geometry
  if attachment_geometry is None:
    return _failure(
      MocTransonicPlacementStatus.SHOCK_GEOMETRY_FAILURE,
      request,
      **common,
      frontier_tangent_angle_rad=tangent,
      message='verified attachment retained no scalar shock geometry for placement',
    )
  ####
  reference_normal = attachment_geometry.shock_normal_angle_rad
  normal_candidates = (base_normal, base_normal + pi)
  normal = min(
    normal_candidates,
    key=lambda candidate: _wrapped_angle_residual(candidate, reference_normal),
  )
  geometry_request = MocTransonicShockGeometryRequest(
    shock_state=attachment_geometry.request.shock_state,
    shock_point_m=point,
    shock_normal_angle_rad=normal,
    normal_alignment_tolerance_rad=request.normal_alignment_tolerance_rad,
    flux_tolerance=request.flux_tolerance,
  )
  geometry = solve_moc_transonic_shock_geometry(geometry_request)
  geometry_audit = measure_moc_transonic_shock_geometry(geometry)
  if not geometry.geometry_verified or not geometry_audit.converged:
    return _failure(
      MocTransonicPlacementStatus.SHOCK_GEOMETRY_FAILURE,
      request,
      **common,
      frontier_tangent_angle_rad=tangent,
      shock_normal_angle_rad=normal,
      shock_geometry=geometry,
      shock_geometry_audit=geometry_audit,
      message='placed scalar shock geometry failed its independent binding audit',
    )
  ####
  return _failure(
    MocTransonicPlacementStatus.CONVERGED_BOUNDED_PLACEMENT,
    request,
    **common,
    frontier_tangent_angle_rad=tangent,
    shock_normal_angle_rad=normal,
    shock_geometry=geometry,
    shock_geometry_audit=geometry_audit,
    message=(
      'bounded transport intersected the resolved neighboring frontier and '
      'the local scalar shock geometry was independently audited; global '
      'reflected closure remains open'
    ),
  )
####
