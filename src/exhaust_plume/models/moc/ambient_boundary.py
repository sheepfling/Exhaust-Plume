"""Ambient-pressure perimeter contracts for the planar MOC lane.

The shock-seeded characteristic assembler can produce a connected polygon
whose unlabelled perimeter is still an internal characteristic.  This module
keeps the external free-boundary condition explicit: the perimeter must be
represented by state samples whose static pressure matches the ambient value
and whose flow direction is tangent to the sampled boundary.

These are acceptance and extraction primitives, not a shock-placement solver.
They are deliberately independent of the basic visual and reduced-order
shock-cell providers.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from math import atan2, cos, isfinite, sin
from typing import TYPE_CHECKING, Sequence

from exhaust_plume.models.moc.primitives import CharacteristicState

if TYPE_CHECKING:
  from exhaust_plume.models.moc.post_shock import (
    MocPostShockCharacteristicFieldResult,
    MocShockBoundaryFitResult,
  )
####

__all__ = (
  'MocAmbientBoundarySample',
  'MocAmbientBoundaryStatus',
  'MocAmbientPressureBoundaryResult',
  'validate_ambient_pressure_boundary',
  'validate_post_shock_ambient_boundary',
)


class MocAmbientBoundaryStatus(str, Enum):
  """Structured outcome for an ambient-pressure perimeter check."""

  CONVERGED = 'converged_ambient_pressure_boundary'
  INVALID_INPUT = 'invalid_input'
  TOPOLOGY_FAILURE = 'topology_failure'
  STATE_FAILURE = 'state_failure'
  GEOMETRY_FAILURE = 'geometry_failure'
  PRESSURE_FAILURE = 'pressure_failure'
  TANGENT_FAILURE = 'tangent_failure'
####


@dataclass(frozen=True, slots=True)
class MocAmbientBoundarySample:
  """One ordered state sample on the external free boundary."""

  point_m: tuple[float, float]
  state: CharacteristicState
  total_pressure_Pa: float

  def __post_init__(self) -> None:
    if len(self.point_m) != 2 or not all(isfinite(float(value)) for value in self.point_m):
      raise ValueError('ambient boundary point must contain two finite coordinates')
    ####
    if not isinstance(self.state, CharacteristicState):
      raise TypeError('ambient boundary state must be a CharacteristicState')
    ####
    if not isfinite(float(self.total_pressure_Pa)) or self.total_pressure_Pa <= 0.0:
      raise ValueError('ambient boundary total pressure must be finite and positive')
    ####
  ####
####


@dataclass(frozen=True, slots=True)
class MocAmbientPressureBoundaryResult:
  """Validation result for a sampled ambient-pressure free boundary."""

  status: MocAmbientBoundaryStatus
  points_m: tuple[tuple[float, float], ...]
  states: tuple[CharacteristicState, ...]
  total_pressure_Pa: tuple[float, ...]
  static_pressure_Pa: tuple[float, ...]
  pressure_residuals: tuple[float, ...]
  tangent_residuals: tuple[float, ...]
  ambient_pressure_Pa: float | None
  maximum_absolute_pressure_residual: float | None
  maximum_absolute_tangent_residual: float | None
  message: str = ''

  @property
  def converged(self) -> bool:
    return self.status is MocAmbientBoundaryStatus.CONVERGED
  ####

  @property
  def physical_closure_verified(self) -> bool:
    """Whether both external boundary conditions passed."""

    return self.converged
  ####

  @property
  def sample_count(self) -> int:
    return len(self.points_m)
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'physical_closure_verified': self.physical_closure_verified,
      'sample_count': self.sample_count,
      'ambient_pressure_Pa': self.ambient_pressure_Pa,
      'maximum_absolute_pressure_residual': self.maximum_absolute_pressure_residual,
      'maximum_absolute_tangent_residual': self.maximum_absolute_tangent_residual,
      'message': self.message,
    }
  ####
####


def _failure(
  status: MocAmbientBoundaryStatus,
  *,
  samples: Sequence[MocAmbientBoundarySample] = (),
  ambient_pressure_Pa: float | None = None,
  message: str,
) -> MocAmbientPressureBoundaryResult:
  resolved = tuple(samples)
  return MocAmbientPressureBoundaryResult(
    status=status,
    points_m=tuple(sample.point_m for sample in resolved),
    states=tuple(sample.state for sample in resolved),
    total_pressure_Pa=tuple(float(sample.total_pressure_Pa) for sample in resolved),
    static_pressure_Pa=(),
    pressure_residuals=(),
    tangent_residuals=(),
    ambient_pressure_Pa=ambient_pressure_Pa,
    maximum_absolute_pressure_residual=None,
    maximum_absolute_tangent_residual=None,
    message=message,
  )
####


def validate_ambient_pressure_boundary(
  samples: Sequence[MocAmbientBoundarySample],
  ambient_pressure_Pa: float,
  *,
  position_tolerance_m: float = 1.0e-10,
  pressure_tolerance: float = 1.0e-8,
  tangent_tolerance: float = 1.0e-8,
) -> MocAmbientPressureBoundaryResult:
  """Validate pressure and streamline tangency on an ordered boundary.

  The boundary is ordered downstream.  Each sample supplies the total
  pressure carried on its incoming characteristic lineage; the isentropic
  static pressure is reconstructed from that value and the local Mach number.
  No pressure or state is interpolated, reset, or extrapolated here.
  """

  if not isfinite(float(ambient_pressure_Pa)) or ambient_pressure_Pa <= 0.0:
    raise ValueError('ambient_pressure_Pa must be finite and positive')
  ####
  for name, value in (
    ('position_tolerance_m', position_tolerance_m),
    ('pressure_tolerance', pressure_tolerance),
    ('tangent_tolerance', tangent_tolerance),
  ):
    if not isfinite(float(value)) or value <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
    ####
  ####
  resolved = tuple(samples)
  if len(resolved) < 2:
    return _failure(
      MocAmbientBoundaryStatus.INVALID_INPUT,
      samples=resolved,
      ambient_pressure_Pa=float(ambient_pressure_Pa),
      message='ambient-pressure boundary requires at least two ordered samples',
    )
  ####
  if any(not isinstance(sample, MocAmbientBoundarySample) for sample in resolved):
    return _failure(
      MocAmbientBoundaryStatus.INVALID_INPUT,
      ambient_pressure_Pa=float(ambient_pressure_Pa),
      message='ambient-pressure boundary samples have an invalid type',
    )
  ####
  gamma = resolved[0].state.gamma
  for index, sample in enumerate(resolved):
    if abs(sample.state.gamma - gamma) > pressure_tolerance:
      return _failure(
        MocAmbientBoundaryStatus.INVALID_INPUT,
        samples=resolved[:index],
        ambient_pressure_Pa=float(ambient_pressure_Pa),
        message=f'ambient boundary sample {index} uses a different gamma',
      )
    ####
    if (
      abs(sample.state.x_m - sample.point_m[0]) > position_tolerance_m
      or abs(sample.state.y_m - sample.point_m[1]) > position_tolerance_m
    ):
      return _failure(
        MocAmbientBoundaryStatus.STATE_FAILURE,
        samples=resolved[:index],
        ambient_pressure_Pa=float(ambient_pressure_Pa),
        message=f'ambient boundary state {index} does not lie on its sample point',
      )
    ####
    if sample.point_m[1] < -position_tolerance_m:
      return _failure(
        MocAmbientBoundaryStatus.GEOMETRY_FAILURE,
        samples=resolved[:index],
        ambient_pressure_Pa=float(ambient_pressure_Pa),
        message=f'ambient boundary sample {index} crossed below the symmetry line',
      )
    ####
    if index:
      previous = resolved[index - 1].point_m
      if sample.point_m[0] <= previous[0] + position_tolerance_m:
        return _failure(
          MocAmbientBoundaryStatus.GEOMETRY_FAILURE,
          samples=resolved[:index],
          ambient_pressure_Pa=float(ambient_pressure_Pa),
          message=(
            f'ambient boundary sample {index} is not strictly downstream '
            'in x'
          ),
        )
      ####
    ####
  ####

  static_pressures: list[float] = []
  pressure_residuals: list[float] = []
  for sample in resolved:
    state = sample.state
    pressure_ratio = (
      1.0 + 0.5 * (state.gamma - 1.0) * state.mach * state.mach
    ) ** (state.gamma / (state.gamma - 1.0))
    pressure = float(sample.total_pressure_Pa) / pressure_ratio
    residual = (pressure - float(ambient_pressure_Pa)) / float(ambient_pressure_Pa)
    static_pressures.append(pressure)
    pressure_residuals.append(residual)
  ####
  maximum_pressure_residual = max((abs(value) for value in pressure_residuals), default=None)
  tangent_residuals: list[float] = []
  tangent_direction_cosines: list[float] = []
  for first, second in zip(resolved, resolved[1:]):
    segment_angle = atan2(
      second.point_m[1] - first.point_m[1],
      second.point_m[0] - first.point_m[0],
    )
    flow_angle = 0.5 * (first.state.theta_rad + second.state.theta_rad)
    tangent_residuals.append(sin(segment_angle - flow_angle))
    tangent_direction_cosines.append(cos(segment_angle - flow_angle))
  ####
  maximum_tangent_residual = max((abs(value) for value in tangent_residuals), default=None)
  if maximum_pressure_residual is None or maximum_pressure_residual > pressure_tolerance:
    return MocAmbientPressureBoundaryResult(
      status=MocAmbientBoundaryStatus.PRESSURE_FAILURE,
      points_m=tuple(sample.point_m for sample in resolved),
      states=tuple(sample.state for sample in resolved),
      total_pressure_Pa=tuple(float(sample.total_pressure_Pa) for sample in resolved),
      static_pressure_Pa=tuple(static_pressures),
      pressure_residuals=tuple(pressure_residuals),
      tangent_residuals=tuple(tangent_residuals),
      ambient_pressure_Pa=float(ambient_pressure_Pa),
      maximum_absolute_pressure_residual=maximum_pressure_residual,
      maximum_absolute_tangent_residual=maximum_tangent_residual,
      message='ambient-pressure boundary static-pressure residual exceeded tolerance',
    )
  ####

  status = (
    MocAmbientBoundaryStatus.CONVERGED
    if (
      maximum_tangent_residual is not None
      and maximum_tangent_residual <= tangent_tolerance
      and all(value > 0.0 for value in tangent_direction_cosines)
    )
    else MocAmbientBoundaryStatus.TANGENT_FAILURE
  )
  return MocAmbientPressureBoundaryResult(
    status=status,
    points_m=tuple(sample.point_m for sample in resolved),
    states=tuple(sample.state for sample in resolved),
    total_pressure_Pa=tuple(float(sample.total_pressure_Pa) for sample in resolved),
    static_pressure_Pa=tuple(static_pressures),
    pressure_residuals=tuple(pressure_residuals),
    tangent_residuals=tuple(tangent_residuals),
    ambient_pressure_Pa=float(ambient_pressure_Pa),
    maximum_absolute_pressure_residual=maximum_pressure_residual,
    maximum_absolute_tangent_residual=maximum_tangent_residual,
    message=(
      ''
      if status is MocAmbientBoundaryStatus.CONVERGED
      else 'ambient-pressure boundary streamline-tangent residual exceeded tolerance'
    ),
  )
####


def _point_key(point: tuple[float, float], position_tolerance_m: float) -> tuple[int, int]:
  return (
    round(float(point[0]) / position_tolerance_m),
    round(float(point[1]) / position_tolerance_m),
  )
####


def _edge_key(
  first: tuple[float, float],
  second: tuple[float, float],
  position_tolerance_m: float,
) -> tuple[tuple[int, int], tuple[int, int]]:
  first_key = _point_key(first, position_tolerance_m)
  second_key = _point_key(second, position_tolerance_m)
  return (first_key, second_key) if first_key <= second_key else (second_key, first_key)
####


def _outer_boundary_path(
  field: MocPostShockCharacteristicFieldResult,
  *,
  position_tolerance_m: float,
) -> tuple[tuple[float, float], ...] | None:
  """Extract the perimeter left after removing shock and axis edges."""

  edge_counts: dict[tuple[tuple[int, int], tuple[int, int]], int] = {}
  point_by_key: dict[tuple[int, int], tuple[float, float]] = {}
  for cell in field.cells:
    vertices = tuple(cell.vertices_xr_m)
    for point in vertices:
      point_by_key[_point_key(point, position_tolerance_m)] = point
    ####
    for first, second in zip(vertices, (*vertices[1:], vertices[0])):
      key = _edge_key(first, second, position_tolerance_m)
      edge_counts[key] = edge_counts.get(key, 0) + 1
    ####
  ####
  boundary_edges = {edge for edge, count in edge_counts.items() if count == 1}
  if not field.shock_boundary_points_m or len(field.centerline_boundary_points_m) != 2:
    return None
  ####
  shock_points = tuple(field.shock_boundary_points_m)
  axis_points = tuple(field.centerline_boundary_points_m)
  shock_edges = {
    _edge_key(first, second, position_tolerance_m)
    for first, second in zip(shock_points, shock_points[1:])
  }
  axis_edge = _edge_key(axis_points[0], axis_points[1], position_tolerance_m)
  if any(edge not in boundary_edges for edge in (*shock_edges, axis_edge)):
    return None
  ####
  outer_edges = boundary_edges - shock_edges - {axis_edge}
  start_key = _point_key(shock_points[0], position_tolerance_m)
  end_key = _point_key(axis_points[1], position_tolerance_m)
  if not outer_edges or start_key not in point_by_key or end_key not in point_by_key:
    return None
  ####
  adjacency: dict[tuple[int, int], set[tuple[int, int]]] = defaultdict(set)
  for first, second in outer_edges:
    adjacency[first].add(second)
    adjacency[second].add(first)
  ####
  if len(adjacency[start_key]) != 1 or len(adjacency[end_key]) != 1:
    return None
  ####
  if any(
    key not in (start_key, end_key) and len(neighbours) != 2
    for key, neighbours in adjacency.items()
  ):
    return None
  ####
  path_keys = [start_key]
  previous: tuple[int, int] | None = None
  current = start_key
  while current != end_key:
    choices = [key for key in adjacency[current] if key != previous]
    if len(choices) != 1:
      return None
    ####
    previous, current = current, choices[0]
    path_keys.append(current)
    if len(path_keys) > len(adjacency) + 1:
      return None
    ####
  ####
  if len(path_keys) < 2 or len(path_keys) != len(adjacency):
    return None
  ####
  return tuple(point_by_key[key] for key in path_keys)
####


def validate_post_shock_ambient_boundary(
  field: MocPostShockCharacteristicFieldResult,
  shock_fit: MocShockBoundaryFitResult,
  ambient_pressure_Pa: float,
  *,
  position_tolerance_m: float = 1.0e-10,
  pressure_tolerance: float = 1.0e-8,
  tangent_tolerance: float = 1.0e-8,
) -> MocAmbientPressureBoundaryResult:
  """Validate the actual non-shock/non-axis perimeter of a field.

  ``assemble_post_shock_characteristic_field`` supplies a topologically
  closed characteristic fan, but does not solve an ambient free boundary.
  This adapter removes the explicit shock and centerline edges from the mesh,
  reconstructs the remaining perimeter from solver-carried states, and then
  applies :func:`validate_ambient_pressure_boundary`.
  """

  if not isfinite(float(ambient_pressure_Pa)) or ambient_pressure_Pa <= 0.0:
    raise ValueError('ambient_pressure_Pa must be finite and positive')
  ####
  if not isfinite(float(position_tolerance_m)) or position_tolerance_m <= 0.0:
    raise ValueError('position_tolerance_m must be finite and positive')
  ####
  if field is None or shock_fit is None:
    return _failure(
      MocAmbientBoundaryStatus.INVALID_INPUT,
      ambient_pressure_Pa=float(ambient_pressure_Pa),
      message='field and shock_fit are required',
    )
  ####
  from exhaust_plume.models.moc.post_shock import (
    MocPostShockCharacteristicFieldResult,
    MocShockBoundaryFitResult,
  )
  if not isinstance(field, MocPostShockCharacteristicFieldResult):
    return _failure(
      MocAmbientBoundaryStatus.INVALID_INPUT,
      ambient_pressure_Pa=float(ambient_pressure_Pa),
      message='field must be a MocPostShockCharacteristicFieldResult',
    )
  ####
  if not isinstance(shock_fit, MocShockBoundaryFitResult):
    return _failure(
      MocAmbientBoundaryStatus.INVALID_INPUT,
      ambient_pressure_Pa=float(ambient_pressure_Pa),
      message='shock_fit must be a MocShockBoundaryFitResult',
    )
  ####
  if not field.converged:
    return _failure(
      MocAmbientBoundaryStatus.INVALID_INPUT,
      ambient_pressure_Pa=float(ambient_pressure_Pa),
      message=f'post-shock field is not converged: {field.message}',
    )
  ####
  if not shock_fit.converged:
    return _failure(
      MocAmbientBoundaryStatus.INVALID_INPUT,
      ambient_pressure_Pa=float(ambient_pressure_Pa),
      message=f'shock fit is not converged: {shock_fit.message}',
    )
  ####
  path = _outer_boundary_path(field, position_tolerance_m=position_tolerance_m)
  if path is None:
    return _failure(
      MocAmbientBoundaryStatus.TOPOLOGY_FAILURE,
      ambient_pressure_Pa=float(ambient_pressure_Pa),
      message=(
        'post-shock field does not expose one connected outer perimeter after '
        'removing its explicit shock and centerline edges'
      ),
    )
  ####
  state_by_key: dict[tuple[int, int], MocAmbientBoundarySample] = {}
  for sample in shock_fit.boundary_states:
    state_by_key[_point_key(sample.point_m, position_tolerance_m)] = MocAmbientBoundarySample(
      point_m=sample.point_m,
      state=sample.state,
      total_pressure_Pa=sample.downstream_total_pressure_Pa,
    )
  ####
  for node in field.nodes:
    if node.total_pressure_Pa is None:
      continue
    ####
    state_by_key[_point_key(node.point_m, position_tolerance_m)] = MocAmbientBoundarySample(
      point_m=node.point_m,
      state=node.state,
      total_pressure_Pa=node.total_pressure_Pa,
    )
  ####
  if field.terminal_centerline_state is not None:
    endpoint_key = _point_key(path[-1], position_tolerance_m)
    if endpoint_key not in state_by_key:
      return _failure(
        MocAmbientBoundaryStatus.STATE_FAILURE,
        ambient_pressure_Pa=float(ambient_pressure_Pa),
        message='outer perimeter endpoint has no carried terminal total-pressure state',
      )
    ####
  ####
  samples: list[MocAmbientBoundarySample] = []
  for index, point in enumerate(path):
    sample = state_by_key.get(_point_key(point, position_tolerance_m))
    if sample is None:
      return _failure(
        MocAmbientBoundaryStatus.STATE_FAILURE,
        samples=samples,
        ambient_pressure_Pa=float(ambient_pressure_Pa),
        message=f'outer perimeter sample {index} has no solver-carried state',
      )
    ####
    samples.append(sample)
  ####
  result = validate_ambient_pressure_boundary(
    samples,
    ambient_pressure_Pa,
    position_tolerance_m=position_tolerance_m,
    pressure_tolerance=pressure_tolerance,
    tangent_tolerance=tangent_tolerance,
  )
  if result.converged:
    return result
  ####
  return MocAmbientPressureBoundaryResult(
    status=result.status,
    points_m=result.points_m,
    states=result.states,
    total_pressure_Pa=result.total_pressure_Pa,
    static_pressure_Pa=result.static_pressure_Pa,
    pressure_residuals=result.pressure_residuals,
    tangent_residuals=result.tangent_residuals,
    ambient_pressure_Pa=result.ambient_pressure_Pa,
    maximum_absolute_pressure_residual=result.maximum_absolute_pressure_residual,
    maximum_absolute_tangent_residual=result.maximum_absolute_tangent_residual,
    message=(
      f'post-shock outer perimeter validation failed: {result.message}'
    ),
  )
####
