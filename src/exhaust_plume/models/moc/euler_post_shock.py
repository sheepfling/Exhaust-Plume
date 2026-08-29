"""A local exact-Euler post-shock topology for the planar MOC lane.

This module closes one deliberately bounded piece of the higher-fidelity
solver: a uniform downstream Euler state behind a locally conservative shock
is connected to the centerline by its compatible ``C-`` characteristics.
The result is a finite, state-carrying local field with a closed polygonal
topology, but it is not an ambient/free-boundary plume cell.  The inlet seam
and the final uniform-state fan completion remain explicit so callers cannot
promote this research field into the fast shock-cell provider or a physical
continued cell chain.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field, replace
from enum import Enum
from math import hypot, isfinite
from typing import Any, Sequence

from exhaust_plume.models.moc.chain import (
  MocChainBoundarySample,
  MocChainTerminationDecision,
  MocChainTerminationReason,
)
from exhaust_plume.models.moc.euler_shock_boundary import (
  MocEulerShockBoundaryCurveResult,
  MocEulerShockBoundaryOrientation,
)
from exhaust_plume.models.moc.primitives import (
  CharacteristicFamily,
  CharacteristicPointResult,
  CharacteristicState,
  MocPrimitiveStatus,
  centerline_characteristic_point,
  interior_characteristic_point,
)
from exhaust_plume.models.moc.topology import (
  MocTopologyResult,
  validate_moc_mesh,
)
from exhaust_plume.models.moc.zone import (
  MocCharacteristicCell,
  MocCharacteristicNode,
)

__all__ = (
  'MocEulerPostShockFieldStatus',
  'MocEulerPostShockFieldResult',
  'assemble_euler_post_shock_field',
)


class MocEulerPostShockFieldStatus(str, Enum):
  """Outcome of the local exact-Euler post-shock field assembly."""

  CONVERGED_LOCAL_CLOSED = 'converged_local_closed_post_shock_field'
  INVALID_INPUT = 'invalid_input'
  SHOCK_BOUNDARY_REQUIRED = 'euler_shock_boundary_required'
  NONUNIFORM_DOWNSTREAM_STATE = 'nonuniform_downstream_state'
  INVARIANT_FAILURE = 'post_shock_invariant_failure'
  CENTERLINE_FAILURE = 'post_shock_centerline_failure'
  GEOMETRY_FAILURE = 'post_shock_geometry_failure'
  TOPOLOGY_FAILURE = 'post_shock_topology_failure'


def _empty_topology() -> MocTopologyResult:
  return validate_moc_mesh(())


def _finite_point(value: Sequence[float], name: str) -> tuple[float, float]:
  try:
    point = (float(value[0]), float(value[1]))
  except (IndexError, TypeError, ValueError) as error:
    raise ValueError(f'{name} must contain two numeric coordinates') from error
  if not all(isfinite(component) for component in point):
    raise ValueError(f'{name} must contain finite coordinates')
  return point


def _triangle_interpolation_weights(
  point: tuple[float, float],
  vertices: tuple[tuple[float, float], ...],
  *,
  tolerance_m: float,
) -> tuple[float, ...] | None:
  (ax, ay), (bx, by), (cx, cy) = vertices
  denominator = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
  if abs(denominator) <= max(tolerance_m * tolerance_m, 1.0e-24):
    return None
  px, py = point
  first = ((by - cy) * (px - cx) + (cx - bx) * (py - cy)) / denominator
  second = ((cy - ay) * (px - cx) + (ax - cx) * (py - cy)) / denominator
  third = 1.0 - first - second
  if min(first, second, third) < -1.0e-10:
    return None
  if max(first, second, third) > 1.0 + 1.0e-10:
    return None
  return first, second, third


def _polygon_contains(
  point: tuple[float, float],
  vertices: tuple[tuple[float, float], ...],
  *,
  tolerance_m: float,
) -> bool:
  if len(vertices) == 3:
    return _triangle_interpolation_weights(
      point,
      vertices,
      tolerance_m=tolerance_m,
    ) is not None
  if len(vertices) != 4:
    return False
  return (
    _triangle_interpolation_weights(
      point,
      (vertices[0], vertices[1], vertices[2]),
      tolerance_m=tolerance_m,
    ) is not None
    or _triangle_interpolation_weights(
      point,
      (vertices[0], vertices[2], vertices[3]),
      tolerance_m=tolerance_m,
    ) is not None
  )


def _forward_margin(
  source: CharacteristicState,
  target: CharacteristicState,
  family: CharacteristicFamily,
) -> float | None:
  first_direction = source.direction(family)
  second_direction = target.direction(family)
  averaged = (
    0.5 * (first_direction[0] + second_direction[0]),
    0.5 * (first_direction[1] + second_direction[1]),
  )
  norm = hypot(*averaged)
  if norm <= 0.0 or not isfinite(norm):
    return None
  displacement = (target.x_m - source.x_m, target.y_m - source.y_m)
  return (
    displacement[0] * averaged[0] / norm
    + displacement[1] * averaged[1] / norm
  )


def _maximum_result_value(
  results: Sequence[CharacteristicPointResult],
  attribute: str,
) -> float | None:
  values = [
    abs(float(value))
    for result in results
    if (value := getattr(result, attribute)) is not None
  ]
  return max(values, default=None)


@dataclass(frozen=True, slots=True)
class MocEulerPostShockFieldResult:
  """A locally closed, uniform-state exact-Euler post-shock field.

  The field's polygonal perimeter is closed by an explicit shock-to-axis
  inlet seam and a topology-only terminal fan center.  Those two choices are
  retained in the result and deliberately keep physical ambient closure and
  production chain promotion disabled.
  """

  status: MocEulerPostShockFieldStatus
  shock_boundary: MocEulerShockBoundaryCurveResult | None = None
  nodes: tuple[MocCharacteristicNode, ...] = ()
  cells: tuple[MocCharacteristicCell, ...] = ()
  topology: MocTopologyResult = dataclass_field(default_factory=_empty_topology)
  shock_boundary_points_m: tuple[tuple[float, float], ...] = ()
  shock_boundary_states: tuple[CharacteristicState, ...] = ()
  shock_boundary_total_pressure_Pa: tuple[float, ...] = ()
  centerline_boundary_points_m: tuple[tuple[float, float], ...] = ()
  centerline_boundary_states: tuple[CharacteristicState, ...] = ()
  centerline_boundary_total_pressure_Pa: tuple[float, ...] = ()
  attachment_boundary_points_m: tuple[tuple[float, float], ...] = ()
  uniform_downstream_state: CharacteristicState | None = None
  uniform_downstream_total_pressure_Pa: float | None = None
  maximum_geometry_residual_m: float | None = None
  maximum_absolute_invariant_residual: float | None = None
  minimum_forward_margin_m: float | None = None
  uniform_state_verified: bool = False
  characteristic_geometry_verified: bool = False
  terminal_mesh_completion_synthetic: bool = False
  position_tolerance_m: float = 1.0e-10
  invariant_tolerance: float = 1.0e-10
  state_tolerance: float = 1.0e-10
  pressure_tolerance: float = 1.0e-8
  physical_closure_status: str = 'not-assembled'
  shock_closure_status: str = 'not-assembled'
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocEulerPostShockFieldStatus):
      raise TypeError('status must be a MocEulerPostShockFieldStatus')
    if self.shock_boundary is not None and not isinstance(
      self.shock_boundary,
      MocEulerShockBoundaryCurveResult,
    ):
      raise TypeError(
        'shock_boundary must be a MocEulerShockBoundaryCurveResult or None'
      )
    if not isinstance(self.topology, MocTopologyResult):
      raise TypeError('topology must be a MocTopologyResult')
    for name in ('nodes', 'cells'):
      values = tuple(getattr(self, name))
      expected_type = (
        MocCharacteristicNode if name == 'nodes' else MocCharacteristicCell
      )
      if any(not isinstance(value, expected_type) for value in values):
        raise TypeError(f'{name} must contain {expected_type.__name__} values')
      object.__setattr__(self, name, values)
    point_fields = (
      'shock_boundary_points_m',
      'centerline_boundary_points_m',
      'attachment_boundary_points_m',
    )
    for name in point_fields:
      points = tuple(_finite_point(point, name) for point in getattr(self, name))
      object.__setattr__(self, name, points)
    for name in (
      'shock_boundary_states',
      'centerline_boundary_states',
    ):
      states = tuple(getattr(self, name))
      if any(not isinstance(state, CharacteristicState) for state in states):
        raise TypeError(f'{name} must contain CharacteristicState values')
      object.__setattr__(self, name, states)
    pressure_fields = (
      'shock_boundary_total_pressure_Pa',
      'centerline_boundary_total_pressure_Pa',
    )
    for name in pressure_fields:
      pressures = tuple(float(value) for value in getattr(self, name))
      if any(not isfinite(value) or value <= 0.0 for value in pressures):
        raise ValueError(f'{name} must contain finite positive values')
      object.__setattr__(self, name, pressures)
    if len(self.shock_boundary_points_m) != len(self.shock_boundary_states):
      raise ValueError('shock boundary points and states must have equal lengths')
    if len(self.shock_boundary_points_m) != len(
      self.shock_boundary_total_pressure_Pa
    ):
      raise ValueError(
        'shock boundary points and total pressures must have equal lengths'
      )
    if len(self.centerline_boundary_points_m) != len(
      self.centerline_boundary_states
    ):
      raise ValueError(
        'centerline boundary points and states must have equal lengths'
      )
    if len(self.centerline_boundary_points_m) != len(
      self.centerline_boundary_total_pressure_Pa
    ):
      raise ValueError(
        'centerline boundary points and total pressures must have equal lengths'
      )
    if len(self.attachment_boundary_points_m) not in (0, 2):
      raise ValueError('attachment_boundary_points_m must be empty or contain two points')
    if self.uniform_downstream_state is not None and not isinstance(
      self.uniform_downstream_state,
      CharacteristicState,
    ):
      raise TypeError(
        'uniform_downstream_state must be a CharacteristicState or None'
      )
    if self.uniform_downstream_total_pressure_Pa is not None:
      pressure = float(self.uniform_downstream_total_pressure_Pa)
      if not isfinite(pressure) or pressure <= 0.0:
        raise ValueError(
          'uniform_downstream_total_pressure_Pa must be finite and positive'
        )
      object.__setattr__(self, 'uniform_downstream_total_pressure_Pa', pressure)
    for name in (
      'maximum_geometry_residual_m',
      'maximum_absolute_invariant_residual',
      'minimum_forward_margin_m',
    ):
      value = getattr(self, name)
      if value is None:
        continue
      numeric = float(value)
      if not isfinite(numeric):
        raise ValueError(f'{name} must be finite when supplied')
      if name != 'minimum_forward_margin_m' and numeric < 0.0:
        raise ValueError(f'{name} must be nonnegative when supplied')
      object.__setattr__(self, name, numeric)
    for name in (
      'position_tolerance_m',
      'invariant_tolerance',
      'state_tolerance',
      'pressure_tolerance',
    ):
      value = float(getattr(self, name))
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      object.__setattr__(self, name, value)
    for name in (
      'uniform_state_verified',
      'characteristic_geometry_verified',
      'terminal_mesh_completion_synthetic',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    object.__setattr__(self, 'physical_closure_status', str(self.physical_closure_status))
    object.__setattr__(self, 'shock_closure_status', str(self.shock_closure_status))
    object.__setattr__(self, 'message', str(self.message))

  @property
  def converged(self) -> bool:
    return self.status is MocEulerPostShockFieldStatus.CONVERGED_LOCAL_CLOSED

  @property
  def node_count(self) -> int:
    return len(self.nodes)

  @property
  def cell_count(self) -> int:
    return len(self.cells)

  @property
  def closed_topology_verified(self) -> bool:
    return bool(
      self.cells
      and self.topology.forms_closed_zone
      and self.topology.nonmanifold_edge_count == 0
    )

  @property
  def physical_closure_verified(self) -> bool:
    """This local field never claims ambient/free-boundary closure."""

    return False

  @property
  def chain_promotion_blocked(self) -> bool:
    return True

  @property
  def production_claim_allowed(self) -> bool:
    return False

  @property
  def state_sampling_available(self) -> bool:
    return bool(
      self.converged
      and self.uniform_state_verified
      and self.uniform_downstream_state is not None
      and self.uniform_downstream_total_pressure_Pa is not None
      and self.closed_topology_verified
    )

  @property
  def domain_x_extent_m(self) -> tuple[float, float] | None:
    points = (
      *(point for cell in self.cells for point in cell.vertices_xr_m),
      *self.shock_boundary_points_m,
      *self.centerline_boundary_points_m,
    )
    if not points:
      return None
    values = tuple(float(point[0]) for point in points)
    if not all(isfinite(value) for value in values):
      return None
    return min(values), max(values)

  @property
  def domain_y_extent_m(self) -> tuple[float, float] | None:
    points = (
      *(point for cell in self.cells for point in cell.vertices_xr_m),
      *self.shock_boundary_points_m,
      *self.centerline_boundary_points_m,
    )
    if not points:
      return None
    values = tuple(float(point[1]) for point in points)
    if not all(isfinite(value) for value in values):
      return None
    return min(values), max(values)

  def _contains(
    self,
    point_m: tuple[float, float],
    *,
    position_tolerance_m: float,
  ) -> bool:
    return any(
      _polygon_contains(
        point_m,
        tuple(cell.vertices_xr_m),
        tolerance_m=position_tolerance_m,
      )
      for cell in self.cells
    )

  def state_at(
    self,
    point_m: tuple[float, float],
    *,
    position_tolerance_m: float = 1.0e-10,
  ) -> CharacteristicState | None:
    """Return the uniform state only for points inside the retained mesh."""

    tolerance = float(position_tolerance_m)
    if not isfinite(tolerance) or tolerance <= 0.0:
      raise ValueError('position_tolerance_m must be finite and positive')
    try:
      point = _finite_point(point_m, 'point_m')
    except ValueError:
      return None
    if not self.state_sampling_available or not self._contains(
      point,
      position_tolerance_m=tolerance,
    ):
      return None
    assert self.uniform_downstream_state is not None
    return replace(
      self.uniform_downstream_state,
      x_m=point[0],
      y_m=point[1],
    )

  def total_pressure_at(
    self,
    point_m: tuple[float, float],
    *,
    position_tolerance_m: float = 1.0e-10,
  ) -> float | None:
    """Return the carried constant post-shock total pressure in the mesh."""

    state = self.state_at(
      point_m,
      position_tolerance_m=position_tolerance_m,
    )
    if state is None:
      return None
    return self.uniform_downstream_total_pressure_Pa

  def static_pressure_at(
    self,
    point_m: tuple[float, float],
    *,
    position_tolerance_m: float = 1.0e-10,
  ) -> float | None:
    """Return the isentropic static pressure for an in-domain sample."""

    state = self.state_at(
      point_m,
      position_tolerance_m=position_tolerance_m,
    )
    pressure = self.total_pressure_at(
      point_m,
      position_tolerance_m=position_tolerance_m,
    )
    if state is None or pressure is None:
      return None
    pressure_ratio = (
      1.0 + 0.5 * (state.gamma - 1.0) * state.mach * state.mach
    ) ** (state.gamma / (state.gamma - 1.0))
    return pressure / pressure_ratio

  @property
  def downstream_handoff(self) -> tuple[MocChainBoundarySample, ...]:
    """Return the centerline trace while retaining the local fidelity stop."""

    if not self.state_sampling_available:
      return ()
    return tuple(
      MocChainBoundarySample(state=state, total_pressure_Pa=pressure)
      for state, pressure in zip(
        self.centerline_boundary_states,
        self.centerline_boundary_total_pressure_Pa,
        strict=True,
      )
    )

  def as_chain_termination_decision(self) -> MocChainTerminationDecision:
    """Map the local field result to an explicit non-physical chain stop."""

    if self.converged:
      reason = MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
      message = (
        'local Euler post-shock topology is closed and state-carrying, but '
        'ambient/free-boundary closure is not solved; continued physical '
        'shock-cell promotion remains blocked'
      )
    elif self.status is MocEulerPostShockFieldStatus.INVALID_INPUT:
      reason = MocChainTerminationReason.INVALID_INPUT
      message = self.message
    elif self.status in (
      MocEulerPostShockFieldStatus.SHOCK_BOUNDARY_REQUIRED,
      MocEulerPostShockFieldStatus.NONUNIFORM_DOWNSTREAM_STATE,
    ):
      reason = MocChainTerminationReason.FIDELITY_NOT_ALLOWED
      message = self.message
    elif self.status is MocEulerPostShockFieldStatus.TOPOLOGY_FAILURE:
      reason = MocChainTerminationReason.TOPOLOGY_INVALID
      message = self.message
    else:
      reason = MocChainTerminationReason.STATE_NOT_CARRIED
      message = self.message
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=reason,
      message=message,
      diagnostics={
        'euler_post_shock_field_status': self.status.value,
        'closed_topology_verified': self.closed_topology_verified,
        'uniform_state_verified': self.uniform_state_verified,
        'characteristic_geometry_verified': self.characteristic_geometry_verified,
        'terminal_mesh_completion_synthetic': self.terminal_mesh_completion_synthetic,
        'physical_closure_verified': False,
        'chain_promotion_blocked': True,
        'production_claim_allowed': False,
      },
    )

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'node_count': self.node_count,
      'cell_count': self.cell_count,
      'state_sampling_available': self.state_sampling_available,
      'closed_topology_verified': self.closed_topology_verified,
      'uniform_state_verified': self.uniform_state_verified,
      'characteristic_geometry_verified': self.characteristic_geometry_verified,
      'terminal_mesh_completion_synthetic': self.terminal_mesh_completion_synthetic,
      'domain_x_extent_m': self.domain_x_extent_m,
      'domain_y_extent_m': self.domain_y_extent_m,
      'shock_boundary_sample_count': len(self.shock_boundary_points_m),
      'centerline_boundary_sample_count': len(self.centerline_boundary_points_m),
      'attachment_boundary_points_m': [
        list(point) for point in self.attachment_boundary_points_m
      ],
      'topology_status': self.topology.status.value,
      'topology_connected': self.topology.connected,
      'topology_forms_closed_zone': self.topology.forms_closed_zone,
      'topology_boundary_edge_count': self.topology.boundary_edge_count,
      'topology_nonmanifold_edge_count': self.topology.nonmanifold_edge_count,
      'maximum_geometry_residual_m': self.maximum_geometry_residual_m,
      'maximum_absolute_invariant_residual': self.maximum_absolute_invariant_residual,
      'minimum_forward_margin_m': self.minimum_forward_margin_m,
      'position_tolerance_m': self.position_tolerance_m,
      'invariant_tolerance': self.invariant_tolerance,
      'state_tolerance': self.state_tolerance,
      'pressure_tolerance': self.pressure_tolerance,
      'physical_closure_status': self.physical_closure_status,
      'shock_closure_status': self.shock_closure_status,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'downstream_handoff_sample_count': len(self.downstream_handoff),
      'chain_termination_decision': self.as_chain_termination_decision().as_report(),
      'message': self.message,
    }


def _failure(
  status: MocEulerPostShockFieldStatus,
  *,
  shock_boundary: MocEulerShockBoundaryCurveResult | None,
  shock_points: Sequence[tuple[float, float]] = (),
  shock_states: Sequence[CharacteristicState] = (),
  shock_pressures: Sequence[float] = (),
  centerline_points: Sequence[tuple[float, float]] = (),
  centerline_states: Sequence[CharacteristicState] = (),
  centerline_pressures: Sequence[float] = (),
  nodes: Sequence[MocCharacteristicNode] = (),
  cells: Sequence[MocCharacteristicCell] = (),
  topology: MocTopologyResult | None = None,
  attachment_points: Sequence[tuple[float, float]] = (),
  uniform_state: CharacteristicState | None = None,
  uniform_total_pressure: float | None = None,
  maximum_geometry_residual_m: float | None = None,
  maximum_absolute_invariant_residual: float | None = None,
  minimum_forward_margin_m: float | None = None,
  uniform_state_verified: bool = False,
  characteristic_geometry_verified: bool = False,
  terminal_mesh_completion_synthetic: bool = False,
  message: str,
) -> MocEulerPostShockFieldResult:
  return MocEulerPostShockFieldResult(
    status=status,
    shock_boundary=shock_boundary,
    nodes=tuple(nodes),
    cells=tuple(cells),
    topology=_empty_topology() if topology is None else topology,
    shock_boundary_points_m=tuple(shock_points),
    shock_boundary_states=tuple(shock_states),
    shock_boundary_total_pressure_Pa=tuple(shock_pressures),
    centerline_boundary_points_m=tuple(centerline_points),
    centerline_boundary_states=tuple(centerline_states),
    centerline_boundary_total_pressure_Pa=tuple(centerline_pressures),
    attachment_boundary_points_m=tuple(attachment_points),
    uniform_downstream_state=uniform_state,
    uniform_downstream_total_pressure_Pa=uniform_total_pressure,
    maximum_geometry_residual_m=maximum_geometry_residual_m,
    maximum_absolute_invariant_residual=maximum_absolute_invariant_residual,
    minimum_forward_margin_m=minimum_forward_margin_m,
    uniform_state_verified=uniform_state_verified,
    characteristic_geometry_verified=characteristic_geometry_verified,
    terminal_mesh_completion_synthetic=terminal_mesh_completion_synthetic,
    physical_closure_status='local-topology-only',
    shock_closure_status='shock-retained; ambient-free-boundary-open',
    message=message,
  )


def assemble_euler_post_shock_field(
  shock_boundary: MocEulerShockBoundaryCurveResult,
  *,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  state_tolerance: float = 1.0e-10,
  pressure_tolerance: float = 1.0e-8,
) -> MocEulerPostShockFieldResult:
  """Assemble a local closed topology from a uniform exact-Euler shock.

  The retained shock must descend to ``y=0`` and carry a uniform downstream
  state with zero flow angle.  ``C-`` characteristics from the shock are
  reflected onto the centerline; ``C+`` characteristics launched from that
  centerline build the interior rows.  The final row is closed with a
  topology-only uniform-state fan center, which is intentionally reported as
  synthetic rather than as an invented characteristic intersection.
  """

  if not isinstance(shock_boundary, MocEulerShockBoundaryCurveResult):
    return _failure(
      MocEulerPostShockFieldStatus.INVALID_INPUT,
      shock_boundary=None,
      message='shock_boundary must be a MocEulerShockBoundaryCurveResult',
    )
  try:
    position_tolerance_value = float(position_tolerance_m)
    invariant_tolerance_value = float(invariant_tolerance)
    state_tolerance_value = float(state_tolerance)
    pressure_tolerance_value = float(pressure_tolerance)
  except (TypeError, ValueError):
    return _failure(
      MocEulerPostShockFieldStatus.INVALID_INPUT,
      shock_boundary=shock_boundary,
      message='post-shock field tolerances must be numeric',
    )
  for name, value in (
    ('position_tolerance_m', position_tolerance_value),
    ('invariant_tolerance', invariant_tolerance_value),
    ('state_tolerance', state_tolerance_value),
    ('pressure_tolerance', pressure_tolerance_value),
  ):
    if not isfinite(value) or value <= 0.0:
      raise ValueError(f'{name} must be finite and positive')

  points = tuple(shock_boundary.shock_points_m)
  states = tuple(shock_boundary.downstream_states)
  pressures = tuple(shock_boundary.downstream_total_pressure_Pa)
  if (
    not shock_boundary.converged
    or not shock_boundary.local_euler_verified
    or shock_boundary.orientation
    is not MocEulerShockBoundaryOrientation.MIXED_CHARACTERISTIC_BOUNDARY
  ):
    return _failure(
      MocEulerPostShockFieldStatus.SHOCK_BOUNDARY_REQUIRED,
      shock_boundary=shock_boundary,
      shock_points=points,
      shock_states=states,
      shock_pressures=pressures,
      message=(
        'local post-shock field requires a converged Euler-verified mixed '
        f'characteristic shock boundary: {shock_boundary.message}'
      ),
    )
  if len(points) < 3 or len(states) != len(points) or len(pressures) != len(points):
    return _failure(
      MocEulerPostShockFieldStatus.INVALID_INPUT,
      shock_boundary=shock_boundary,
      shock_points=points,
      shock_states=states,
      shock_pressures=pressures,
      message=(
        'post-shock field requires at least three aligned shock points, '
        'downstream states, and total-pressure samples'
      ),
    )
  for index, (point, state) in enumerate(zip(points, states, strict=True)):
    if hypot(state.x_m - point[0], state.y_m - point[1]) > 10.0 * position_tolerance_value:
      return _failure(
        MocEulerPostShockFieldStatus.GEOMETRY_FAILURE,
        shock_boundary=shock_boundary,
        shock_points=points,
        shock_states=states,
        shock_pressures=pressures,
        message=f'downstream shock state {index} is not located at its shock point',
      )
  for index, (previous, current) in enumerate(
    zip(points[:-1], points[1:], strict=True),
    start=1,
  ):
    if current[0] <= previous[0] + position_tolerance_value:
      return _failure(
        MocEulerPostShockFieldStatus.GEOMETRY_FAILURE,
        shock_boundary=shock_boundary,
        shock_points=points,
        shock_states=states,
        shock_pressures=pressures,
        message=f'shock point {index} is not strictly downstream in x',
      )
    if current[1] > previous[1] + position_tolerance_value:
      return _failure(
        MocEulerPostShockFieldStatus.GEOMETRY_FAILURE,
        shock_boundary=shock_boundary,
        shock_points=points,
        shock_states=states,
        shock_pressures=pressures,
        message='shock points must be nonincreasing in y toward the centerline',
      )
  if points[0][1] <= position_tolerance_value or abs(points[-1][1]) > 10.0 * position_tolerance_value:
    return _failure(
      MocEulerPostShockFieldStatus.GEOMETRY_FAILURE,
      shock_boundary=shock_boundary,
      shock_points=points,
      shock_states=states,
      shock_pressures=pressures,
      message='shock boundary must start above and end on the y=0 centerline',
    )

  reference_state = states[0]
  state_residuals = tuple(
    max(
      abs(state.theta_rad - reference_state.theta_rad),
      abs(state.mach - reference_state.mach),
      abs(state.gamma - reference_state.gamma),
    )
    for state in states
  )
  if max(state_residuals, default=float('inf')) > state_tolerance_value:
    return _failure(
      MocEulerPostShockFieldStatus.NONUNIFORM_DOWNSTREAM_STATE,
      shock_boundary=shock_boundary,
      shock_points=points,
      shock_states=states,
      shock_pressures=pressures,
      uniform_state=reference_state,
      message=(
        'local post-shock topology only supports a uniform downstream state; '
        f'maximum state residual is {max(state_residuals, default=None)}'
      ),
    )
  if abs(reference_state.theta_rad) > state_tolerance_value:
    return _failure(
      MocEulerPostShockFieldStatus.GEOMETRY_FAILURE,
      shock_boundary=shock_boundary,
      shock_points=points,
      shock_states=states,
      shock_pressures=pressures,
      uniform_state=reference_state,
      message='uniform downstream state must be aligned with the centerline',
    )
  if any(not isfinite(value) or value <= 0.0 for value in pressures):
    return _failure(
      MocEulerPostShockFieldStatus.INVARIANT_FAILURE,
      shock_boundary=shock_boundary,
      shock_points=points,
      shock_states=states,
      shock_pressures=pressures,
      uniform_state=reference_state,
      message='downstream shock total pressures must be finite and positive',
    )
  pressure_residuals = tuple(abs(value - pressures[0]) for value in pressures)
  if max(pressure_residuals, default=float('inf')) > pressure_tolerance_value * max(
    1.0,
    abs(pressures[0]),
  ):
    return _failure(
      MocEulerPostShockFieldStatus.INVARIANT_FAILURE,
      shock_boundary=shock_boundary,
      shock_points=points,
      shock_states=states,
      shock_pressures=pressures,
      uniform_state=reference_state,
      uniform_total_pressure=pressures[0],
      message='downstream total pressure is not constant along the local field',
    )

  centerline_results: list[CharacteristicPointResult] = []
  centerline_points: list[tuple[float, float]] = []
  centerline_states: list[CharacteristicState] = []
  for index, state in enumerate(states):
    result = centerline_characteristic_point(
      state,
      CharacteristicFamily.MINUS,
      position_tolerance_m=position_tolerance_value,
      invariant_tolerance=invariant_tolerance_value,
    )
    if not result.converged or result.point_m is None or result.state is None:
      return _failure(
        MocEulerPostShockFieldStatus.CENTERLINE_FAILURE,
        shock_boundary=shock_boundary,
        shock_points=points,
        shock_states=states,
        shock_pressures=pressures,
        centerline_points=centerline_points,
        centerline_states=centerline_states,
        centerline_pressures=pressures[:len(centerline_points)],
        maximum_geometry_residual_m=_maximum_result_value(
          centerline_results,
          'geometry_residual',
        ),
        maximum_absolute_invariant_residual=max(
          (
            max(
              abs(value)
              for value in (
                result.invariant_residual_plus,
                result.invariant_residual_minus,
              )
              if value is not None
            )
            for result in centerline_results
          ),
          default=None,
        ),
        uniform_state=reference_state,
        uniform_total_pressure=pressures[0],
        message=f'centerline characteristic {index} failed: {result.message}',
      )
    centerline_results.append(result)
    centerline_points.append(result.point_m)
    centerline_states.append(result.state)

  for index, (previous, current) in enumerate(
    zip(centerline_points[:-1], centerline_points[1:], strict=True),
    start=1,
  ):
    if current[0] <= previous[0] + position_tolerance_value:
      return _failure(
        MocEulerPostShockFieldStatus.GEOMETRY_FAILURE,
        shock_boundary=shock_boundary,
        shock_points=points,
        shock_states=states,
        shock_pressures=pressures,
        centerline_points=centerline_points,
        centerline_states=centerline_states,
        centerline_pressures=pressures,
        uniform_state=reference_state,
        uniform_total_pressure=pressures[0],
        maximum_geometry_residual_m=_maximum_result_value(
          centerline_results,
          'geometry_residual',
        ),
        message=f'centerline characteristic {index} is not ordered downstream',
      )
  if centerline_points[0][0] <= points[0][0] + position_tolerance_value:
    return _failure(
      MocEulerPostShockFieldStatus.GEOMETRY_FAILURE,
      shock_boundary=shock_boundary,
      shock_points=points,
      shock_states=states,
      shock_pressures=pressures,
      centerline_points=centerline_points,
      centerline_states=centerline_states,
      centerline_pressures=pressures,
      uniform_state=reference_state,
      uniform_total_pressure=pressures[0],
      maximum_geometry_residual_m=_maximum_result_value(
        centerline_results,
        'geometry_residual',
      ),
      message='first centerline characteristic does not advance from the shock',
    )
  if hypot(centerline_points[-1][0] - points[-1][0], centerline_points[-1][1] - points[-1][1]) > 10.0 * position_tolerance_value:
    return _failure(
      MocEulerPostShockFieldStatus.GEOMETRY_FAILURE,
      shock_boundary=shock_boundary,
      shock_points=points,
      shock_states=states,
      shock_pressures=pressures,
      centerline_points=centerline_points,
      centerline_states=centerline_states,
      centerline_pressures=pressures,
      uniform_state=reference_state,
      uniform_total_pressure=pressures[0],
      maximum_geometry_residual_m=_maximum_result_value(
        centerline_results,
        'geometry_residual',
      ),
      message='terminal centerline characteristic does not meet the shock endpoint',
    )

  nodes_by_key: dict[tuple[int, int], MocCharacteristicNode] = {}
  nodes: list[MocCharacteristicNode] = []
  nodes_by_key[0, 0] = MocCharacteristicNode(
    centerline_index=0,
    boundary_index=0,
    point_m=centerline_points[0],
    state=centerline_states[0],
    point_result=centerline_results[0],
    total_pressure_Pa=pressures[0],
  )
  nodes.append(nodes_by_key[0, 0])
  interior_results: list[CharacteristicPointResult] = []
  forward_margins: list[float] = []
  for row in range(1, len(points) - 1):
    for column in range(row):
      result = interior_characteristic_point(
        centerline_states[column],
        states[row],
        position_tolerance_m=position_tolerance_value,
        invariant_tolerance=invariant_tolerance_value,
      )
      if not result.converged or result.point_m is None or result.state is None:
        return _failure(
          MocEulerPostShockFieldStatus.GEOMETRY_FAILURE,
          shock_boundary=shock_boundary,
          shock_points=points,
          shock_states=states,
          shock_pressures=pressures,
          centerline_points=centerline_points,
          centerline_states=centerline_states,
          centerline_pressures=pressures,
          nodes=nodes,
          maximum_geometry_residual_m=max(
            (
              value
              for value in (
                _maximum_result_value(centerline_results, 'geometry_residual'),
                _maximum_result_value(interior_results, 'geometry_residual'),
              )
              if value is not None
            ),
            default=None,
          ),
          uniform_state=reference_state,
          uniform_total_pressure=pressures[0],
          message=(
            f'interior characteristic at row {row}, column {column} failed: '
            f'{result.message}'
          ),
        )
      interior_results.append(result)
      margin_plus = _forward_margin(
        centerline_states[column],
        result.state,
        CharacteristicFamily.PLUS,
      )
      margin_minus = _forward_margin(
        states[row],
        result.state,
        CharacteristicFamily.MINUS,
      )
      if margin_plus is None or margin_minus is None:
        return _failure(
          MocEulerPostShockFieldStatus.GEOMETRY_FAILURE,
          shock_boundary=shock_boundary,
          shock_points=points,
          shock_states=states,
          shock_pressures=pressures,
          centerline_points=centerline_points,
          centerline_states=centerline_states,
          centerline_pressures=pressures,
          nodes=nodes,
          uniform_state=reference_state,
          uniform_total_pressure=pressures[0],
          message='interior characteristic direction is undefined',
        )
      forward_margins.extend((margin_plus, margin_minus))
      node = MocCharacteristicNode(
        centerline_index=column,
        boundary_index=row,
        point_m=result.point_m,
        state=result.state,
        point_result=result,
        total_pressure_Pa=pressures[0],
      )
      nodes_by_key[row, column] = node
      nodes.append(node)
    node = MocCharacteristicNode(
      centerline_index=row,
      boundary_index=row,
      point_m=centerline_points[row],
      state=centerline_states[row],
      point_result=centerline_results[row],
      total_pressure_Pa=pressures[0],
    )
    nodes_by_key[row, row] = node
    nodes.append(node)

  cells: list[MocCharacteristicCell] = []
  try:
    for row in range(1, len(points) - 1):
      cells.append(
        MocCharacteristicCell(
          cell_index=len(cells) + 1,
          cell_kind='shock-characteristic-strip',
          vertices_xr_m=(
            points[row - 1],
            points[row],
            nodes_by_key[row, 0].point_m,
            nodes_by_key[row - 1, 0].point_m,
          ),
          centerline_indices=(row - 1, row),
          boundary_indices=(row - 1, row),
        )
      )
      for column in range(row):
        if column == row - 1:
          vertices = (
            nodes_by_key[row - 1, column].point_m,
            nodes_by_key[row, column].point_m,
            nodes_by_key[row, column + 1].point_m,
          )
        else:
          vertices = (
            nodes_by_key[row - 1, column].point_m,
            nodes_by_key[row, column].point_m,
            nodes_by_key[row, column + 1].point_m,
            nodes_by_key[row - 1, column + 1].point_m,
          )
        cells.append(
          MocCharacteristicCell(
            cell_index=len(cells) + 1,
            cell_kind=(
              'characteristic-compatibility-triangle'
              if len(vertices) == 3
              else 'characteristic-compatibility-cell'
            ),
            vertices_xr_m=vertices,
            centerline_indices=(row - 1, row),
            boundary_indices=(column, row),
          )
        )

    terminal_row = len(points) - 2
    terminal_boundary = [
      points[-2],
      points[-1],
      centerline_points[-2],
      *[
        nodes_by_key[terminal_row, column].point_m
        for column in range(terminal_row - 1, -1, -1)
      ],
    ]
    terminal_center = (
      sum(point[0] for point in terminal_boundary) / len(terminal_boundary),
      sum(point[1] for point in terminal_boundary) / len(terminal_boundary),
    )
    terminal_state = replace(
      reference_state,
      x_m=terminal_center[0],
      y_m=terminal_center[1],
    )
    terminal_result = CharacteristicPointResult(
      status=MocPrimitiveStatus.CONVERGED,
      state=terminal_state,
      point_m=terminal_center,
      invariant_residual_plus=0.0,
      invariant_residual_minus=0.0,
      geometry_residual=0.0,
      iterations=0,
      intersection_status='synthetic-uniform-state-terminal-center',
      message=(
        'terminal center is a topology-only uniform-state sample; it is not '
        'a claimed characteristic intersection'
      ),
    )
    nodes.append(
      MocCharacteristicNode(
        centerline_index=terminal_row,
        boundary_index=terminal_row,
        point_m=terminal_center,
        state=terminal_state,
        point_result=terminal_result,
        total_pressure_Pa=pressures[0],
      )
    )
    for first, second in zip(
      terminal_boundary,
      terminal_boundary[1:] + terminal_boundary[:1],
      strict=True,
    ):
      cells.append(
        MocCharacteristicCell(
          cell_index=len(cells) + 1,
          cell_kind='terminal-uniform-state-topology-fan',
          vertices_xr_m=(terminal_center, first, second),
          centerline_indices=(terminal_row,),
          boundary_indices=(terminal_row,),
        )
      )
  except (TypeError, ValueError) as error:
    topology = validate_moc_mesh(cells)
    return _failure(
      MocEulerPostShockFieldStatus.GEOMETRY_FAILURE,
      shock_boundary=shock_boundary,
      shock_points=points,
      shock_states=states,
      shock_pressures=pressures,
      centerline_points=centerline_points,
      centerline_states=centerline_states,
      centerline_pressures=pressures,
      nodes=nodes,
      cells=cells,
      topology=topology,
      attachment_points=(points[0], centerline_points[0]),
      uniform_state=reference_state,
      uniform_total_pressure=pressures[0],
      message=f'post-shock characteristic cell geometry failed: {error}',
    )

  topology = validate_moc_mesh(cells)
  if not topology.forms_closed_zone or topology.nonmanifold_edge_count:
    return _failure(
      MocEulerPostShockFieldStatus.TOPOLOGY_FAILURE,
      shock_boundary=shock_boundary,
      shock_points=points,
      shock_states=states,
      shock_pressures=pressures,
      centerline_points=centerline_points,
      centerline_states=centerline_states,
      centerline_pressures=pressures,
      nodes=nodes,
      cells=cells,
      topology=topology,
      attachment_points=(points[0], centerline_points[0]),
      uniform_state=reference_state,
      uniform_total_pressure=pressures[0],
      maximum_geometry_residual_m=max(
        (
          value
          for value in (
            _maximum_result_value(centerline_results, 'geometry_residual'),
            _maximum_result_value(interior_results, 'geometry_residual'),
          )
          if value is not None
        ),
        default=None,
      ),
      maximum_absolute_invariant_residual=max(
        (
          abs(value)
          for result in (*centerline_results, *interior_results)
          for value in (
            result.invariant_residual_plus,
            result.invariant_residual_minus,
          )
          if value is not None
        ),
        default=None,
      ),
      minimum_forward_margin_m=min(forward_margins, default=None),
      message=f'post-shock characteristic topology failed: {topology.message}',
    )
  return MocEulerPostShockFieldResult(
    status=MocEulerPostShockFieldStatus.CONVERGED_LOCAL_CLOSED,
    shock_boundary=shock_boundary,
    nodes=tuple(nodes),
    cells=tuple(cells),
    topology=topology,
    shock_boundary_points_m=points,
    shock_boundary_states=states,
    shock_boundary_total_pressure_Pa=pressures,
    centerline_boundary_points_m=tuple(centerline_points),
    centerline_boundary_states=tuple(centerline_states),
    centerline_boundary_total_pressure_Pa=pressures,
    attachment_boundary_points_m=(points[0], centerline_points[0]),
    uniform_downstream_state=reference_state,
    uniform_downstream_total_pressure_Pa=pressures[0],
    maximum_geometry_residual_m=max(
      (
        value
        for value in (
          _maximum_result_value(centerline_results, 'geometry_residual'),
          _maximum_result_value(interior_results, 'geometry_residual'),
        )
        if value is not None
      ),
      default=None,
    ),
    maximum_absolute_invariant_residual=max(
      (
        abs(value)
        for result in (*centerline_results, *interior_results)
        for value in (
          result.invariant_residual_plus,
          result.invariant_residual_minus,
        )
        if value is not None
      ),
      default=None,
    ),
    minimum_forward_margin_m=min(forward_margins, default=None),
    uniform_state_verified=True,
    characteristic_geometry_verified=True,
    terminal_mesh_completion_synthetic=True,
    position_tolerance_m=position_tolerance_value,
    invariant_tolerance=invariant_tolerance_value,
    state_tolerance=state_tolerance_value,
    pressure_tolerance=pressure_tolerance_value,
    physical_closure_status='local-topology-only',
    shock_closure_status='shock-retained; ambient-free-boundary-open',
    message=(
      'uniform exact-Euler post-shock characteristic topology assembled; '
      'ambient/free-boundary closure and continued physical chain promotion '
      'remain intentionally blocked'
    ),
  )
