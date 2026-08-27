"""Independent geometry measurements for the planar-MOC shock-cell lane.

The MOC solver owns characteristic compatibility and physical closure.  This
module owns a separate, deliberately small measurement operator: it extracts
shock-cell geometry and optional shock total-pressure loss from an assembled
field, while preserving topology and fidelity metadata in the result.  It
does not infer a shock from a scalar trace, fill an open boundary, or promote
the measurement to validation evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import cos, fsum, hypot, isfinite, log, sin
from typing import Any, Sequence

from exhaust_plume.models.moc.mixed_regime import (
  MocMixedRegimeClosureResult,
  MocMixedRegimeDownstreamConditionKind,
  MocMixedRegimeDownstreamConditionResult,
  MocMixedRegimeFieldResult,
  MocMixedRegimeFieldSample,
  validate_mixed_regime_boundary,
  validate_mixed_regime_downstream_condition,
)
from exhaust_plume.models.moc.compression import MocNormalShockTerminalResult
from exhaust_plume.models.moc.primitives import CharacteristicState
from exhaust_plume.models.moc.post_shock import MocPostShockBoundaryState
from exhaust_plume.models.moc.shock_chain import MocTerminalShockCellFieldResult
from exhaust_plume.models.moc.topology import MocTopologyResult, validate_moc_mesh

__all__ = (
  'MOC_SHOCK_CELL_CHAIN_OPERATOR_ID',
  'MOC_SHOCK_CELL_GEOMETRY_OPERATOR_ID',
  'MOC_TERMINAL_CLOSURE_OPERATOR_ID',
  'MocTerminalClosureMeasurement',
  'MocTerminalClosureMeasurementStatus',
  'MocTerminalClosureObservation',
  'MocShockCellChainMeasurement',
  'MocShockCellMeasurement',
  'MocShockCellMeasurementStatus',
  'MocShockCellObservation',
  'measure_moc_terminal_closure',
  'measure_moc_shock_cell',
  'measure_moc_shock_cell_chain',
)


MOC_SHOCK_CELL_GEOMETRY_OPERATOR_ID = 'op.moc.shock-cell-geometry'
MOC_SHOCK_CELL_CHAIN_OPERATOR_ID = 'op.moc.shock-cell-chain'
MOC_TERMINAL_CLOSURE_OPERATOR_ID = 'op.moc.terminal-closure'

Point = tuple[float, float]


class MocShockCellMeasurementStatus(str, Enum):
  """Outcome of an independent MOC shock-cell measurement."""

  CONVERGED = 'converged'
  INVALID_INPUT = 'invalid_input'
  GEOMETRY_FAILURE = 'geometry_failure'
  TOPOLOGY_FAILURE = 'topology_failure'
  PRESSURE_FAILURE = 'pressure_failure'
  CHAIN_FAILURE = 'chain_failure'
####


class MocTerminalClosureMeasurementStatus(str, Enum):
  """Outcome of the independent first-cell terminal measurement."""

  CONVERGED = 'converged'
  INVALID_INPUT = 'invalid_input'
  GEOMETRY_FAILURE = 'geometry_failure'
  TOPOLOGY_FAILURE = 'topology_failure'
  PRESSURE_FAILURE = 'pressure_failure'
  SUPERSONIC_FAILURE = 'supersonic_failure'
  MIXED_REGIME_FAILURE = 'mixed_regime_failure'
####


@dataclass(frozen=True, slots=True)
class MocTerminalClosureObservation:
  """Terminal field and optional mixed-regime closure to be measured.

  The observation carries solver output as data only.  The measurement
  operator rechecks the terminal mesh, shock pressure loss, scalar seam,
  mixed-regime mesh, and closure metrics without accepting a solver object's
  convenience properties as proof.
  """

  terminal_field: MocTerminalShockCellFieldResult
  mixed_regime_closure: MocMixedRegimeClosureResult | None = None
####


@dataclass(frozen=True, slots=True)
class MocTerminalClosureMeasurement:
  """Independent acceptance gates for a terminal mixed-regime attachment."""

  status: MocTerminalClosureMeasurementStatus
  operator_id: str
  terminal_field_status: str | None
  mixed_regime_status: str | None
  supersonic_topology: MocTopologyResult
  mixed_regime_topology: MocTopologyResult
  terminal_shock_sample_count: int
  terminal_shock_edge_count: int
  terminal_shock_downstream_sample_count: int
  perimeter_sample_count: int
  supersonic_node_count: int
  supersonic_cell_count: int
  mixed_regime_node_count: int
  mixed_regime_cell_count: int
  terminal_normal_shock_verified: bool
  terminal_shock_geometry_verified: bool
  terminal_pressure_loss_verified: bool
  supersonic_patch_verified: bool
  mixed_regime_request_verified: bool
  mixed_regime_boundary_verified: bool
  mixed_regime_model_verified: bool
  downstream_condition_verified: bool
  physical_closure_verified: bool
  physical_termination_verified: bool
  chain_promotion_blocked: bool
  minimum_terminal_total_pressure_ratio: float | None
  maximum_terminal_total_pressure_ratio: float | None
  maximum_thermodynamic_residual: float | None
  maximum_harmonic_residual: float | None
  maximum_velocity_divergence_residual: float | None
  claim_status: str
  message: str

  @property
  def converged(self) -> bool:
    return self.status is MocTerminalClosureMeasurementStatus.CONVERGED
  ####

  def as_report(self) -> dict[str, Any]:
    """Return a JSON-compatible terminal measurement record."""

    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'terminal_field_status': self.terminal_field_status,
      'mixed_regime_status': self.mixed_regime_status,
      'supersonic_topology': {
        'status': self.supersonic_topology.status.value,
        'connected': self.supersonic_topology.connected,
        'forms_closed_zone': self.supersonic_topology.forms_closed_zone,
        'boundary_edge_count': self.supersonic_topology.boundary_edge_count,
        'boundary_component_count': self.supersonic_topology.boundary_component_count,
        'nonmanifold_edge_count': self.supersonic_topology.nonmanifold_edge_count,
      },
      'mixed_regime_topology': {
        'status': self.mixed_regime_topology.status.value,
        'connected': self.mixed_regime_topology.connected,
        'forms_closed_zone': self.mixed_regime_topology.forms_closed_zone,
        'boundary_edge_count': self.mixed_regime_topology.boundary_edge_count,
        'boundary_component_count': self.mixed_regime_topology.boundary_component_count,
        'nonmanifold_edge_count': self.mixed_regime_topology.nonmanifold_edge_count,
      },
      'counts': {
        'terminal_shock_sample_count': self.terminal_shock_sample_count,
        'terminal_shock_edge_count': self.terminal_shock_edge_count,
        'terminal_shock_downstream_sample_count': self.terminal_shock_downstream_sample_count,
        'perimeter_sample_count': self.perimeter_sample_count,
        'supersonic_node_count': self.supersonic_node_count,
        'supersonic_cell_count': self.supersonic_cell_count,
        'mixed_regime_node_count': self.mixed_regime_node_count,
        'mixed_regime_cell_count': self.mixed_regime_cell_count,
      },
      'checks': {
        'terminal_normal_shock_verified': self.terminal_normal_shock_verified,
        'terminal_shock_geometry_verified': self.terminal_shock_geometry_verified,
        'terminal_pressure_loss_verified': self.terminal_pressure_loss_verified,
        'supersonic_patch_verified': self.supersonic_patch_verified,
        'mixed_regime_request_verified': self.mixed_regime_request_verified,
        'mixed_regime_boundary_verified': self.mixed_regime_boundary_verified,
        'mixed_regime_model_verified': self.mixed_regime_model_verified,
        'downstream_condition_verified': self.downstream_condition_verified,
      },
      'physical_closure_verified': self.physical_closure_verified,
      'physical_termination_verified': self.physical_termination_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'pressure': {
        'minimum_terminal_total_pressure_ratio': self.minimum_terminal_total_pressure_ratio,
        'maximum_terminal_total_pressure_ratio': self.maximum_terminal_total_pressure_ratio,
      },
      'residuals': {
        'maximum_thermodynamic_residual': self.maximum_thermodynamic_residual,
        'maximum_harmonic_residual': self.maximum_harmonic_residual,
        'maximum_velocity_divergence_residual': self.maximum_velocity_divergence_residual,
      },
      'claim_status': self.claim_status,
      'message': self.message,
    }
  ####


@dataclass(frozen=True, slots=True)
class MocShockCellObservation:
  """Raw field boundaries and mesh supplied to the measurement operator.

  The observation intentionally contains no solver status.  A planner mock
  and a solver-generated field therefore go through exactly the same
  extraction and topology checks, while their provenance remains the caller's
  responsibility.
  """

  cell_index: int
  shock_boundary_points_m: tuple[Point, ...]
  centerline_boundary_points_m: tuple[Point, ...]
  cells: tuple[object, ...]
  upstream_total_pressure_Pa: tuple[float, ...] = ()
  downstream_total_pressure_Pa: tuple[float, ...] = ()

  def __post_init__(self) -> None:
    if isinstance(self.cell_index, bool) or not isinstance(self.cell_index, int):
      raise TypeError('cell_index must be an integer')
    if self.cell_index < 1:
      raise ValueError('cell_index must be positive')
    object.__setattr__(
      self,
      'shock_boundary_points_m',
      tuple((float(point[0]), float(point[1])) for point in self.shock_boundary_points_m),
    )
    object.__setattr__(
      self,
      'centerline_boundary_points_m',
      tuple((float(point[0]), float(point[1])) for point in self.centerline_boundary_points_m),
    )
    object.__setattr__(self, 'cells', tuple(self.cells))
    object.__setattr__(
      self,
      'upstream_total_pressure_Pa',
      tuple(float(value) for value in self.upstream_total_pressure_Pa),
    )
    object.__setattr__(
      self,
      'downstream_total_pressure_Pa',
      tuple(float(value) for value in self.downstream_total_pressure_Pa),
    )
  ####


@dataclass(frozen=True, slots=True)
class MocShockCellMeasurement:
  """Geometry and optional shock-loss measurements for one MOC cell."""

  status: MocShockCellMeasurementStatus
  operator_id: str
  cell_index: int
  cell_count: int
  topology: MocTopologyResult
  shock_boundary_point_count: int
  centerline_boundary_point_count: int
  shock_start_m: Point | None
  shock_end_m: Point | None
  centerline_end_m: Point | None
  axial_extent_m: tuple[float, float] | None
  axial_length_m: float | None
  shock_boundary_length_m: float | None
  centerline_boundary_length_m: float | None
  maximum_radius_m: float | None
  mesh_area_m2: float | None
  perimeter_area_m2: float | None
  area_closure_residual_m2: float | None
  pressure_sample_count: int
  minimum_total_pressure_ratio: float | None
  maximum_total_pressure_ratio: float | None
  pressure_loss_verified: bool | None
  claim_status: str
  message: str

  @property
  def converged(self) -> bool:
    return self.status is MocShockCellMeasurementStatus.CONVERGED
  ####

  def as_report(self) -> dict[str, Any]:
    """Return a JSON-compatible measurement record."""

    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'cell_index': self.cell_index,
      'cell_count': self.cell_count,
      'topology': {
        'status': self.topology.status.value,
        'connected': self.topology.connected,
        'forms_closed_zone': self.topology.forms_closed_zone,
        'boundary_edge_count': self.topology.boundary_edge_count,
        'boundary_component_count': self.topology.boundary_component_count,
        'nonmanifold_edge_count': self.topology.nonmanifold_edge_count,
      },
      'boundary_point_counts': {
        'shock': self.shock_boundary_point_count,
        'centerline': self.centerline_boundary_point_count,
      },
      'shock_start_m': self.shock_start_m,
      'shock_end_m': self.shock_end_m,
      'centerline_end_m': self.centerline_end_m,
      'axial_extent_m': self.axial_extent_m,
      'axial_length_m': self.axial_length_m,
      'shock_boundary_length_m': self.shock_boundary_length_m,
      'centerline_boundary_length_m': self.centerline_boundary_length_m,
      'maximum_radius_m': self.maximum_radius_m,
      'mesh_area_m2': self.mesh_area_m2,
      'perimeter_area_m2': self.perimeter_area_m2,
      'area_closure_residual_m2': self.area_closure_residual_m2,
      'pressure': {
        'sample_count': self.pressure_sample_count,
        'minimum_total_pressure_ratio': self.minimum_total_pressure_ratio,
        'maximum_total_pressure_ratio': self.maximum_total_pressure_ratio,
        'pressure_loss_verified': self.pressure_loss_verified,
      },
      'claim_status': self.claim_status,
      'message': self.message,
    }
  ####


@dataclass(frozen=True, slots=True)
class MocShockCellChainMeasurement:
  """Independent measurements for an ordered continued-cell chain."""

  status: MocShockCellMeasurementStatus
  operator_id: str
  cells: tuple[MocShockCellMeasurement, ...]
  axial_extent_m: tuple[float, float] | None
  shock_start_spacing_m: tuple[float, ...]
  total_mesh_area_m2: float | None
  claim_status: str
  message: str

  @property
  def converged(self) -> bool:
    return self.status is MocShockCellMeasurementStatus.CONVERGED
  ####

  def as_report(self) -> dict[str, Any]:
    """Return a JSON-compatible chain measurement record."""

    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'cell_count': len(self.cells),
      'cells': [cell.as_report() for cell in self.cells],
      'axial_extent_m': self.axial_extent_m,
      'shock_start_spacing_m': list(self.shock_start_spacing_m),
      'total_mesh_area_m2': self.total_mesh_area_m2,
      'claim_status': self.claim_status,
      'message': self.message,
    }
  ####


def _empty_topology() -> MocTopologyResult:
  return validate_moc_mesh(())
####


def _failure(
  status: MocShockCellMeasurementStatus,
  *,
  cell_index: int,
  cell_count: int,
  shock_boundary_point_count: int,
  centerline_boundary_point_count: int,
  topology: MocTopologyResult | None = None,
  message: str,
) -> MocShockCellMeasurement:
  return MocShockCellMeasurement(
    status=status,
    operator_id=MOC_SHOCK_CELL_GEOMETRY_OPERATOR_ID,
    cell_index=cell_index,
    cell_count=cell_count,
    topology=_empty_topology() if topology is None else topology,
    shock_boundary_point_count=shock_boundary_point_count,
    centerline_boundary_point_count=centerline_boundary_point_count,
    shock_start_m=None,
    shock_end_m=None,
    centerline_end_m=None,
    axial_extent_m=None,
    axial_length_m=None,
    shock_boundary_length_m=None,
    centerline_boundary_length_m=None,
    maximum_radius_m=None,
    mesh_area_m2=None,
    perimeter_area_m2=None,
    area_closure_residual_m2=None,
    pressure_sample_count=0,
    minimum_total_pressure_ratio=None,
    maximum_total_pressure_ratio=None,
    pressure_loss_verified=None,
    claim_status='not_accepted',
    message=message,
  )
####


def _points(value: Sequence[Sequence[float]], name: str) -> tuple[Point, ...]:
  points: list[Point] = []
  for index, point in enumerate(value):
    try:
      if len(point) != 2:
        raise ValueError
      candidate = (float(point[0]), float(point[1]))
    except (TypeError, ValueError, IndexError) as error:
      raise ValueError(f'{name} point {index} is not a pair of coordinates') from error
    if not all(isfinite(coordinate) for coordinate in candidate):
      raise ValueError(f'{name} point {index} is not finite')
    points.append(candidate)
  if len(points) < 2:
    raise ValueError(f'{name} requires at least two points')
  return tuple(points)
####


def _validate_polyline(
  points: tuple[Point, ...],
  name: str,
  *,
  position_tolerance_m: float,
  require_strict_x: bool,
) -> str | None:
  if any(point[1] < -position_tolerance_m for point in points):
    return f'{name} must remain on or above the symmetry line'
  for first, second in zip(points, points[1:]):
    dx = second[0] - first[0]
    dy = second[1] - first[1]
    if require_strict_x and dx <= position_tolerance_m:
      return f'{name} must be strictly downstream in x'
    if not require_strict_x and dx < -position_tolerance_m:
      return f'{name} must not move upstream in x'
    if dy > position_tolerance_m:
      return f'{name} must be nonincreasing in y'
  return None
####


def _key(point: Point, tolerance_m: float) -> tuple[int, int]:
  return round(point[0] / tolerance_m), round(point[1] / tolerance_m)
####


def _edge_counts(
  cells: tuple[object, ...],
  *,
  vertex_tolerance_m: float,
) -> tuple[
  dict[tuple[tuple[int, int], tuple[int, int]], int],
  dict[tuple[int, int], Point],
]:
  counts: dict[tuple[tuple[int, int], tuple[int, int]], int] = {}
  points: dict[tuple[int, int], Point] = {}
  for cell in cells:
    vertices = tuple(
      (float(point[0]), float(point[1]))
      for point in getattr(cell, 'vertices_xr_m')
    )
    keys = tuple(_key(point, vertex_tolerance_m) for point in vertices)
    for key, point in zip(keys, vertices, strict=True):
      points[key] = point
    for first, second in zip(keys, (*keys[1:], keys[0])):
      edge = (first, second) if first <= second else (second, first)
      counts[edge] = counts.get(edge, 0) + 1
  return counts, points
####


def _cell_vertices(cell: object) -> tuple[Point, ...]:
  raw_vertices = getattr(cell, 'vertices_xr_m', None)
  if raw_vertices is None:
    raise AttributeError('cell does not expose vertices_xr_m')
  vertices: list[Point] = []
  for index, point in enumerate(raw_vertices):
    try:
      if len(point) != 2:
        raise ValueError
      candidate = (float(point[0]), float(point[1]))
    except (TypeError, ValueError, IndexError) as error:
      raise ValueError(f'cell vertex {index} is not a coordinate pair') from error
    if not all(isfinite(coordinate) for coordinate in candidate):
      raise ValueError(f'cell vertex {index} is not finite')
    vertices.append(candidate)
  return tuple(vertices)
####


def _polyline_has_boundary_edges(
  polyline: tuple[Point, ...],
  edge_counts: dict[tuple[tuple[int, int], tuple[int, int]], int],
  *,
  vertex_tolerance_m: float,
) -> bool:
  for first, second in zip(polyline, polyline[1:]):
    first_key = _key(first, vertex_tolerance_m)
    second_key = _key(second, vertex_tolerance_m)
    edge = (
      (first_key, second_key)
      if first_key <= second_key
      else (second_key, first_key)
    )
    if edge_counts.get(edge) != 1:
      return False
  return True
####


def _perimeter_points(
  edge_counts: dict[tuple[tuple[int, int], tuple[int, int]], int],
  vertex_points: dict[tuple[int, int], Point],
) -> tuple[Point, ...] | None:
  boundary_edges = [edge for edge, count in edge_counts.items() if count == 1]
  graph: dict[tuple[int, int], list[tuple[int, int]]] = {}
  for first, second in boundary_edges:
    graph.setdefault(first, []).append(second)
    graph.setdefault(second, []).append(first)
  if not graph or any(len(neighbors) != 2 for neighbors in graph.values()):
    return None
  start = next(iter(graph))
  cycle = [start]
  previous: tuple[int, int] | None = None
  current = start
  while True:
    neighbors = graph[current]
    next_vertex = neighbors[0] if neighbors[0] != previous else neighbors[1]
    if next_vertex == start:
      break
    if next_vertex in cycle or len(cycle) > len(graph):
      return None
    cycle.append(next_vertex)
    previous, current = current, next_vertex
  if len(cycle) != len(graph):
    return None
  return tuple(vertex_points[key] for key in cycle)
####


def _polygon_area(points: Sequence[Point]) -> float:
  return 0.5 * fsum(
    first[0] * second[1] - second[0] * first[1]
    for first, second in zip(points, (*points[1:], points[0]))
  )
####


def _pressure_metrics(
  upstream: tuple[float, ...],
  downstream: tuple[float, ...],
  *,
  expected_count: int,
) -> tuple[int, float | None, float | None, bool | None, str | None]:
  if not upstream and not downstream:
    return 0, None, None, None, None
  if len(upstream) != len(downstream) or len(upstream) != expected_count:
    return (
      0,
      None,
      None,
      False,
      'upstream and downstream pressure samples must both match the shock boundary',
    )
  if any(
      not isfinite(value) or value <= 0.0
      for value in (*upstream, *downstream)
  ):
    return 0, None, None, False, 'total-pressure samples must be finite and positive'
  ratios = tuple(
    downstream_value / upstream_value
    for upstream_value, downstream_value in zip(upstream, downstream, strict=True)
  )
  loss_verified = all(
    downstream_value < upstream_value
    for upstream_value, downstream_value in zip(upstream, downstream, strict=True)
  )
  return (
    len(ratios),
    min(ratios),
    max(ratios),
    loss_verified,
    None if loss_verified else 'every shock sample must reduce total pressure',
  )
####


def measure_moc_shock_cell(
  observation: MocShockCellObservation,
  *,
  position_tolerance_m: float = 1.0e-10,
  axis_tolerance_m: float = 1.0e-10,
  area_tolerance_m2: float = 1.0e-9,
  mesh_vertex_tolerance_m: float = 1.0e-12,
) -> MocShockCellMeasurement:
  """Measure one shock-cell field without inferring missing physical edges."""

  if not isinstance(observation, MocShockCellObservation):
    raise TypeError('observation must be a MocShockCellObservation')
  for name, value in (
    ('position_tolerance_m', position_tolerance_m),
    ('axis_tolerance_m', axis_tolerance_m),
    ('area_tolerance_m2', area_tolerance_m2),
    ('mesh_vertex_tolerance_m', mesh_vertex_tolerance_m),
  ):
    if not isfinite(float(value)) or value <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
  try:
    shock = _points(observation.shock_boundary_points_m, 'shock boundary')
    centerline = _points(
      observation.centerline_boundary_points_m,
      'centerline boundary',
    )
  except ValueError as error:
    return _failure(
      MocShockCellMeasurementStatus.INVALID_INPUT,
      cell_index=observation.cell_index,
      cell_count=len(observation.cells),
      shock_boundary_point_count=len(observation.shock_boundary_points_m),
      centerline_boundary_point_count=len(observation.centerline_boundary_points_m),
      message=str(error),
    )
  shock_error = _validate_polyline(
    shock,
    'shock boundary',
    position_tolerance_m=position_tolerance_m,
    require_strict_x=True,
  )
  centerline_error = _validate_polyline(
    centerline,
    'centerline boundary',
    position_tolerance_m=position_tolerance_m,
    require_strict_x=False,
  )
  if shock_error or centerline_error:
    return _failure(
      MocShockCellMeasurementStatus.GEOMETRY_FAILURE,
      cell_index=observation.cell_index,
      cell_count=len(observation.cells),
      shock_boundary_point_count=len(shock),
      centerline_boundary_point_count=len(centerline),
      message=shock_error or centerline_error or 'boundary geometry is invalid',
    )
  if hypot(
      shock[-1][0] - centerline[0][0],
      shock[-1][1] - centerline[0][1],
  ) > position_tolerance_m:
    return _failure(
      MocShockCellMeasurementStatus.GEOMETRY_FAILURE,
      cell_index=observation.cell_index,
      cell_count=len(observation.cells),
      shock_boundary_point_count=len(shock),
      centerline_boundary_point_count=len(centerline),
      message='shock and centerline boundaries must share their endpoint',
    )
  if abs(centerline[-1][1]) > axis_tolerance_m:
    return _failure(
      MocShockCellMeasurementStatus.GEOMETRY_FAILURE,
      cell_index=observation.cell_index,
      cell_count=len(observation.cells),
      shock_boundary_point_count=len(shock),
      centerline_boundary_point_count=len(centerline),
      message='centerline boundary must terminate on y = 0',
    )
  for cell_index, cell in enumerate(observation.cells):
    try:
      vertices = _cell_vertices(cell)
    except (AttributeError, TypeError, ValueError) as error:
      return _failure(
        MocShockCellMeasurementStatus.INVALID_INPUT,
        cell_index=observation.cell_index,
        cell_count=len(observation.cells),
        shock_boundary_point_count=len(shock),
        centerline_boundary_point_count=len(centerline),
        message=f'cell {cell_index} could not be read: {error}',
      )
    if any(
        len(point) != 2
        or not all(isfinite(float(coordinate)) for coordinate in point)
        or float(point[1]) < -axis_tolerance_m
        for point in vertices
    ):
      return _failure(
        MocShockCellMeasurementStatus.GEOMETRY_FAILURE,
        cell_index=observation.cell_index,
        cell_count=len(observation.cells),
        shock_boundary_point_count=len(shock),
        centerline_boundary_point_count=len(centerline),
        message=f'cell {cell_index} leaves the nonnegative-y measurement half-plane',
      )
  topology = validate_moc_mesh(
    observation.cells,
    vertex_tolerance_m=mesh_vertex_tolerance_m,
  )
  if not topology.connected or not topology.forms_closed_zone or topology.nonmanifold_edge_count:
    return _failure(
      MocShockCellMeasurementStatus.TOPOLOGY_FAILURE,
      cell_index=observation.cell_index,
      cell_count=len(observation.cells),
      shock_boundary_point_count=len(shock),
      centerline_boundary_point_count=len(centerline),
      topology=topology,
      message=f'MOC cell mesh topology is not one bounded connected zone: {topology.message}',
    )
  try:
    edge_counts, vertex_points = _edge_counts(
      observation.cells,
      vertex_tolerance_m=mesh_vertex_tolerance_m,
    )
  except (AttributeError, TypeError, ValueError) as error:
    return _failure(
      MocShockCellMeasurementStatus.INVALID_INPUT,
      cell_index=observation.cell_index,
      cell_count=len(observation.cells),
      shock_boundary_point_count=len(shock),
      centerline_boundary_point_count=len(centerline),
      topology=topology,
      message=f'cell mesh could not be measured: {error}',
    )
  if not _polyline_has_boundary_edges(
      shock,
      edge_counts,
      vertex_tolerance_m=mesh_vertex_tolerance_m,
  ):
    message = 'shock boundary samples are not explicit perimeter edges in the mesh'
    return _failure(
      MocShockCellMeasurementStatus.GEOMETRY_FAILURE,
      cell_index=observation.cell_index,
      cell_count=len(observation.cells),
      shock_boundary_point_count=len(shock),
      centerline_boundary_point_count=len(centerline),
      topology=topology,
      message=message,
    )
  if not _polyline_has_boundary_edges(
      centerline,
      edge_counts,
      vertex_tolerance_m=mesh_vertex_tolerance_m,
  ):
    return _failure(
      MocShockCellMeasurementStatus.GEOMETRY_FAILURE,
      cell_index=observation.cell_index,
      cell_count=len(observation.cells),
      shock_boundary_point_count=len(shock),
      centerline_boundary_point_count=len(centerline),
      topology=topology,
      message='centerline boundary samples are not explicit perimeter edges in the mesh',
    )
  perimeter = _perimeter_points(edge_counts, vertex_points)
  if perimeter is None:
    return _failure(
      MocShockCellMeasurementStatus.GEOMETRY_FAILURE,
      cell_index=observation.cell_index,
      cell_count=len(observation.cells),
      shock_boundary_point_count=len(shock),
      centerline_boundary_point_count=len(centerline),
      topology=topology,
      message='mesh perimeter could not be reconstructed as one cycle',
    )
  mesh_area = fsum(
    abs(_polygon_area(_cell_vertices(cell)))
    for cell in observation.cells
  )
  perimeter_area = abs(_polygon_area(perimeter))
  area_residual = mesh_area - perimeter_area
  scaled_area_tolerance = max(
    area_tolerance_m2,
    area_tolerance_m2 * max(1.0, perimeter_area),
  )
  if abs(area_residual) > scaled_area_tolerance:
    return _failure(
      MocShockCellMeasurementStatus.GEOMETRY_FAILURE,
      cell_index=observation.cell_index,
      cell_count=len(observation.cells),
      shock_boundary_point_count=len(shock),
      centerline_boundary_point_count=len(centerline),
      topology=topology,
      message=(
        'cell-area and perimeter-area measurements disagree beyond tolerance: '
        f'{area_residual}'
      ),
    )
  pressure_count, minimum_ratio, maximum_ratio, pressure_loss_verified, pressure_error = _pressure_metrics(
    observation.upstream_total_pressure_Pa,
    observation.downstream_total_pressure_Pa,
    expected_count=len(shock),
  )
  if pressure_error is not None:
    return MocShockCellMeasurement(
      status=MocShockCellMeasurementStatus.PRESSURE_FAILURE,
      operator_id=MOC_SHOCK_CELL_GEOMETRY_OPERATOR_ID,
      cell_index=observation.cell_index,
      cell_count=len(observation.cells),
      topology=topology,
      shock_boundary_point_count=len(shock),
      centerline_boundary_point_count=len(centerline),
      shock_start_m=shock[0],
      shock_end_m=shock[-1],
      centerline_end_m=centerline[-1],
      axial_extent_m=(
        min(point[0] for point in (*shock, *centerline, *perimeter)),
        max(point[0] for point in (*shock, *centerline, *perimeter)),
      ),
      axial_length_m=max(point[0] for point in (*shock, *centerline, *perimeter))
      - min(point[0] for point in (*shock, *centerline, *perimeter)),
      shock_boundary_length_m=fsum(
        hypot(second[0] - first[0], second[1] - first[1])
        for first, second in zip(shock, shock[1:])
      ),
      centerline_boundary_length_m=fsum(
        hypot(second[0] - first[0], second[1] - first[1])
        for first, second in zip(centerline, centerline[1:])
      ),
      maximum_radius_m=max(point[1] for point in (*shock, *centerline, *perimeter)),
      mesh_area_m2=mesh_area,
      perimeter_area_m2=perimeter_area,
      area_closure_residual_m2=area_residual,
      pressure_sample_count=pressure_count,
      minimum_total_pressure_ratio=minimum_ratio,
      maximum_total_pressure_ratio=maximum_ratio,
      pressure_loss_verified=pressure_loss_verified,
      claim_status='not_accepted',
      message=pressure_error,
    )
  all_points = (*shock, *centerline, *perimeter)
  axial_min = min(point[0] for point in all_points)
  axial_max = max(point[0] for point in all_points)
  return MocShockCellMeasurement(
    status=MocShockCellMeasurementStatus.CONVERGED,
    operator_id=MOC_SHOCK_CELL_GEOMETRY_OPERATOR_ID,
    cell_index=observation.cell_index,
    cell_count=len(observation.cells),
    topology=topology,
    shock_boundary_point_count=len(shock),
    centerline_boundary_point_count=len(centerline),
    shock_start_m=shock[0],
    shock_end_m=shock[-1],
    centerline_end_m=centerline[-1],
    axial_extent_m=(axial_min, axial_max),
    axial_length_m=axial_max - axial_min,
    shock_boundary_length_m=fsum(
      hypot(second[0] - first[0], second[1] - first[1])
      for first, second in zip(shock, shock[1:])
    ),
    centerline_boundary_length_m=fsum(
      hypot(second[0] - first[0], second[1] - first[1])
      for first, second in zip(centerline, centerline[1:])
    ),
    maximum_radius_m=max(point[1] for point in all_points),
    mesh_area_m2=mesh_area,
    perimeter_area_m2=perimeter_area,
    area_closure_residual_m2=area_residual,
    pressure_sample_count=pressure_count,
    minimum_total_pressure_ratio=minimum_ratio,
    maximum_total_pressure_ratio=maximum_ratio,
    pressure_loss_verified=pressure_loss_verified,
    claim_status='not_accepted',
    message=(
      'shock-cell geometry and explicit perimeter topology measured; '
      'external comparison and physical-closure acceptance remain separate gates'
    ),
  )
####


def _terminal_measurement_failure(
  status: MocTerminalClosureMeasurementStatus,
  *,
  terminal_field_status: str | None = None,
  mixed_regime_status: str | None = None,
  supersonic_topology: MocTopologyResult | None = None,
  mixed_regime_topology: MocTopologyResult | None = None,
  terminal_shock_sample_count: int = 0,
  terminal_shock_edge_count: int = 0,
  terminal_shock_downstream_sample_count: int = 0,
  perimeter_sample_count: int = 0,
  supersonic_node_count: int = 0,
  supersonic_cell_count: int = 0,
  mixed_regime_node_count: int = 0,
  mixed_regime_cell_count: int = 0,
  terminal_normal_shock_verified: bool = False,
  terminal_shock_geometry_verified: bool = False,
  terminal_pressure_loss_verified: bool = False,
  supersonic_patch_verified: bool = False,
  mixed_regime_request_verified: bool = False,
  mixed_regime_boundary_verified: bool = False,
  mixed_regime_model_verified: bool = False,
  downstream_condition_verified: bool = False,
  physical_closure_verified: bool = False,
  physical_termination_verified: bool = False,
  minimum_terminal_total_pressure_ratio: float | None = None,
  maximum_terminal_total_pressure_ratio: float | None = None,
  maximum_thermodynamic_residual: float | None = None,
  maximum_harmonic_residual: float | None = None,
  maximum_velocity_divergence_residual: float | None = None,
  message: str,
) -> MocTerminalClosureMeasurement:
  return MocTerminalClosureMeasurement(
    status=status,
    operator_id=MOC_TERMINAL_CLOSURE_OPERATOR_ID,
    terminal_field_status=terminal_field_status,
    mixed_regime_status=mixed_regime_status,
    supersonic_topology=(
      _empty_topology() if supersonic_topology is None else supersonic_topology
    ),
    mixed_regime_topology=(
      _empty_topology()
      if mixed_regime_topology is None
      else mixed_regime_topology
    ),
    terminal_shock_sample_count=terminal_shock_sample_count,
    terminal_shock_edge_count=terminal_shock_edge_count,
    terminal_shock_downstream_sample_count=terminal_shock_downstream_sample_count,
    perimeter_sample_count=perimeter_sample_count,
    supersonic_node_count=supersonic_node_count,
    supersonic_cell_count=supersonic_cell_count,
    mixed_regime_node_count=mixed_regime_node_count,
    mixed_regime_cell_count=mixed_regime_cell_count,
    terminal_normal_shock_verified=terminal_normal_shock_verified,
    terminal_shock_geometry_verified=terminal_shock_geometry_verified,
    terminal_pressure_loss_verified=terminal_pressure_loss_verified,
    supersonic_patch_verified=supersonic_patch_verified,
    mixed_regime_request_verified=mixed_regime_request_verified,
    mixed_regime_boundary_verified=mixed_regime_boundary_verified,
    mixed_regime_model_verified=mixed_regime_model_verified,
    downstream_condition_verified=downstream_condition_verified,
    physical_closure_verified=physical_closure_verified,
    physical_termination_verified=physical_termination_verified,
    chain_promotion_blocked=True,
    minimum_terminal_total_pressure_ratio=minimum_terminal_total_pressure_ratio,
    maximum_terminal_total_pressure_ratio=maximum_terminal_total_pressure_ratio,
    maximum_thermodynamic_residual=maximum_thermodynamic_residual,
    maximum_harmonic_residual=maximum_harmonic_residual,
    maximum_velocity_divergence_residual=maximum_velocity_divergence_residual,
    claim_status='not_accepted',
    message=message,
  )
####


def _state_total_pressure(state: CharacteristicState, static_pressure_Pa: float) -> float:
  factor = 1.0 + 0.5 * (state.gamma - 1.0) * state.mach * state.mach
  return static_pressure_Pa * factor ** (state.gamma / (state.gamma - 1.0))
####


def _scalar_total_pressure(
  mach: float,
  gamma: float,
  static_pressure_Pa: float,
) -> float:
  factor = 1.0 + 0.5 * (gamma - 1.0) * mach * mach
  return static_pressure_Pa * factor ** (gamma / (gamma - 1.0))
####


def _relative_value_residual(actual: float, expected: float) -> float:
  return abs(actual - expected) / max(1.0, abs(actual), abs(expected))
####


def _mixed_field_thermodynamic_residual(
  nodes: Sequence[MocMixedRegimeFieldSample],
) -> float | None:
  if not nodes:
    return None
  residuals: list[float] = []
  for sample in nodes:
    try:
      total_pressure = _scalar_total_pressure(
        sample.mach,
        sample.gamma,
        sample.static_pressure_Pa,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError):
      return None
    residuals.append(
      _relative_value_residual(total_pressure, sample.total_pressure_Pa)
    )
  return max(residuals)
####


def _mixed_field_node_lookup(
  nodes: Sequence[MocMixedRegimeFieldSample],
  *,
  vertex_tolerance_m: float,
) -> dict[tuple[int, int], MocMixedRegimeFieldSample]:
  return {
    _key(sample.point_m, vertex_tolerance_m): sample
    for sample in nodes
  }
####


def _mixed_field_velocity_divergence_residual(
  field: MocMixedRegimeFieldResult,
  *,
  vertex_tolerance_m: float,
) -> float | None:
  if not field.cells:
    return None
  lookup = _mixed_field_node_lookup(
    field.nodes,
    vertex_tolerance_m=vertex_tolerance_m,
  )
  residuals: list[float] = []
  for cell in field.cells:
    try:
      vertices = _cell_vertices(cell)
    except (AttributeError, TypeError, ValueError):
      return None
    if len(vertices) != 3:
      return None
    samples = tuple(
      lookup.get(_key(point, vertex_tolerance_m))
      for point in vertices
    )
    if any(sample is None for sample in samples):
      return None
    first, second, third = samples
    assert first is not None
    assert second is not None
    assert third is not None
    x1, y1 = first.point_m
    x2, y2 = second.point_m
    x3, y3 = third.point_m
    area_twice = (x2 - x1) * (y3 - y1) - (y2 - y1) * (x3 - x1)
    if abs(area_twice) <= 1.0e-20:
      return None
    velocities = tuple(
      (
        sample.mach * cos(sample.flow_angle_rad),
        sample.mach * sin(sample.flow_angle_rad),
      )
      for sample in (first, second, third)
    )
    du_dx = (
      velocities[0][0] * (y2 - y3)
      + velocities[1][0] * (y3 - y1)
      + velocities[2][0] * (y1 - y2)
    ) / area_twice
    dv_dy = (
      velocities[0][1] * (x3 - x2)
      + velocities[1][1] * (x1 - x3)
      + velocities[2][1] * (x2 - x1)
    ) / area_twice
    residuals.append(abs(du_dx + dv_dy))
  return max(residuals)
####


def _mixed_field_harmonic_residual(
  field: MocMixedRegimeFieldResult,
  *,
  position_tolerance_m: float,
) -> float | None:
  """Recompute the residual of the declared reference discretization."""

  boundary = field.boundary
  perimeter = boundary.perimeter_points_m
  samples = boundary.subsonic_samples
  if len(perimeter) < 4 or len(samples) != len(perimeter):
    return None
  unique_points = tuple(perimeter[:-1])
  unique_samples = tuple(samples[:-1])
  sample_count = len(unique_points)
  if sample_count < 3:
    return None
  if field.interior_point_m is None:
    return None
  if field.radial_divisions == 1:
    if len(field.nodes) != sample_count + 1:
      return None
    center = field.nodes[-1]
    if hypot(
        center.point_m[0] - field.interior_point_m[0],
        center.point_m[1] - field.interior_point_m[1],
    ) > position_tolerance_m:
      return None
    means = (
      fsum(sample.mach for sample in unique_samples) / sample_count,
      fsum(sample.flow_angle_rad for sample in unique_samples) / sample_count,
      fsum(sample.static_pressure_Pa for sample in unique_samples) / sample_count,
      fsum(sample.total_pressure_Pa for sample in unique_samples) / sample_count,
    )
    return max(
      abs(actual - expected)
      for actual, expected in zip(
        (
          center.mach,
          center.flow_angle_rad,
          center.static_pressure_Pa,
          center.total_pressure_Pa,
        ),
        means,
        strict=True,
      )
    )
  radial_divisions = field.radial_divisions
  expected_node_count = 1 + radial_divisions * sample_count
  if len(field.nodes) != expected_node_count:
    return None
  for level in range(radial_divisions + 1):
    level_points = (
      (field.interior_point_m,)
      if level == 0
      else tuple(
        (
          field.interior_point_m[0]
          + level / radial_divisions * (point[0] - field.interior_point_m[0]),
          field.interior_point_m[1]
          + level / radial_divisions * (point[1] - field.interior_point_m[1]),
        )
        for point in unique_points
      )
    )
    level_nodes = (
      (field.nodes[0],)
      if level == 0
      else tuple(
        field.nodes[1 + (level - 1) * sample_count + index]
        for index in range(sample_count)
      )
    )
    if any(
        hypot(node.point_m[0] - point[0], node.point_m[1] - point[1])
        > position_tolerance_m
        for node, point in zip(level_nodes, level_points, strict=True)
    ):
      return None
  residuals: list[float] = []
  components = (
    lambda sample: sample.mach,
    lambda sample: sample.flow_angle_rad,
    lambda sample: log(sample.total_pressure_Pa),
    lambda sample: sample.gamma,
  )
  for component in components:
    values = tuple(component(sample) for sample in field.nodes)
    residuals.append(
      abs(sample_count * values[0] - sum(
        values[1 + index] for index in range(sample_count)
      ))
    )
    for level in range(1, radial_divisions):
      for index in range(sample_count):
        row = 1 + (level - 1) * sample_count + index
        inner = 0.0 if level == 1 else values[
          1 + (level - 2) * sample_count + index
        ]
        outer = (
          values[1 + (radial_divisions - 1) * sample_count + index]
          if level + 1 == radial_divisions
          else values[1 + level * sample_count + index]
        )
        left = values[1 + (level - 1) * sample_count + (index - 1) % sample_count]
        right = values[1 + (level - 1) * sample_count + (index + 1) % sample_count]
        center = values[0] if level == 1 else inner
        residuals.append(abs(4.0 * values[row] - center - outer - left - right))
    if radial_divisions == 1:
      break
  return max(residuals, default=None)
####


def _terminal_shock_x_at_y(
  shock_points: Sequence[Point],
  ordinate: float,
  *,
  position_tolerance_m: float,
) -> float | None:
  for first, second in zip(shock_points, shock_points[1:]):
    low = min(first[1], second[1])
    high = max(first[1], second[1])
    if low - position_tolerance_m <= ordinate <= high + position_tolerance_m:
      if abs(second[1] - first[1]) <= position_tolerance_m:
        return 0.5 * (first[0] + second[0])
      fraction = (ordinate - first[1]) / (second[1] - first[1])
      return first[0] + fraction * (second[0] - first[0])
  return None
####


def _terminal_shock_coverage(
  cells: Sequence[object],
  shock_points: Sequence[Point],
  *,
  position_tolerance_m: float,
  mesh_vertex_tolerance_m: float,
) -> tuple[int, bool, float | None]:
  """Measure coverage of a sampled shock over explicit mesh perimeter edges."""

  if len(shock_points) < 2:
    return 0, False, None
  edge_counts: dict[tuple[tuple[int, int], tuple[int, int]], int] = {}
  edge_points: dict[
    tuple[tuple[int, int], tuple[int, int]],
    tuple[Point, Point],
  ] = {}
  for cell in cells:
    vertices = _cell_vertices(cell)
    for first, second in zip(vertices, (*vertices[1:], vertices[0])):
      first_key = _key(first, mesh_vertex_tolerance_m)
      second_key = _key(second, mesh_vertex_tolerance_m)
      edge = (
        (first_key, second_key)
        if first_key <= second_key
        else (second_key, first_key)
      )
      edge_counts[edge] = edge_counts.get(edge, 0) + 1
      edge_points.setdefault(edge, (first, second))
  target_low = min(point[1] for point in shock_points)
  target_high = max(point[1] for point in shock_points)
  covered_edges: list[tuple[float, float]] = []
  residuals: list[float] = []
  for edge, count in edge_counts.items():
    if count != 1:
      continue
    first, second = edge_points[edge]
    low = min(first[1], second[1])
    high = max(first[1], second[1])
    if high < target_low - position_tolerance_m or low > target_high + position_tolerance_m:
      continue
    ordinates = [
      first[1],
      second[1],
      *(
        point[1]
        for point in shock_points
        if low - position_tolerance_m <= point[1] <= high + position_tolerance_m
      ),
    ]
    edge_residual = 0.0
    for ordinate in ordinates:
      if abs(second[1] - first[1]) <= mesh_vertex_tolerance_m:
        edge_x = 0.5 * (first[0] + second[0])
      else:
        fraction = (ordinate - first[1]) / (second[1] - first[1])
        edge_x = first[0] + fraction * (second[0] - first[0])
      shock_x = _terminal_shock_x_at_y(
        shock_points,
        ordinate,
        position_tolerance_m=position_tolerance_m,
      )
      if shock_x is None:
        edge_residual = float('inf')
        break
      edge_residual = max(edge_residual, abs(edge_x - shock_x))
    if edge_residual <= position_tolerance_m:
      covered_edges.append((low, high))
      residuals.append(edge_residual)
  covered_edges.sort()
  merged: list[tuple[float, float]] = []
  for low, high in covered_edges:
    if merged and low <= merged[-1][1] + position_tolerance_m:
      merged[-1] = (merged[-1][0], max(merged[-1][1], high))
    else:
      merged.append((low, high))
  covered = bool(merged) and (
    merged[0][0] <= target_low + position_tolerance_m
    and merged[-1][1] >= target_high - position_tolerance_m
    and all(
      second[0] <= first[1] + position_tolerance_m
      for first, second in zip(merged, merged[1:])
    )
  )
  return len(covered_edges), covered, max(residuals, default=None)
####


def measure_moc_terminal_closure(
  observation: MocTerminalClosureObservation,
  *,
  position_tolerance_m: float = 1.0e-9,
  axis_tolerance_m: float = 1.0e-10,
  state_tolerance: float = 1.0e-10,
  pressure_tolerance: float = 1.0e-8,
  thermodynamic_tolerance: float = 1.0e-8,
  residual_tolerance: float = 1.0e-12,
  mesh_vertex_tolerance_m: float = 1.0e-12,
) -> MocTerminalClosureMeasurement:
  """Measure a terminal field and optional mixed-regime attachment.

  This operator intentionally re-runs geometry, topology, shock pressure-loss,
  scalar seam, reference-field residual, and downstream-condition checks.  It
  never infers a missing perimeter and never turns a passing terminal result
  into a continued supersonic cell.
  """

  if not isinstance(observation, MocTerminalClosureObservation):
    return _terminal_measurement_failure(
      MocTerminalClosureMeasurementStatus.INVALID_INPUT,
      message='observation must be a MocTerminalClosureObservation',
    )
  for name, value in (
    ('position_tolerance_m', position_tolerance_m),
    ('axis_tolerance_m', axis_tolerance_m),
    ('state_tolerance', state_tolerance),
    ('pressure_tolerance', pressure_tolerance),
    ('thermodynamic_tolerance', thermodynamic_tolerance),
    ('residual_tolerance', residual_tolerance),
    ('mesh_vertex_tolerance_m', mesh_vertex_tolerance_m),
  ):
    if not isfinite(float(value)) or float(value) <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
  field = observation.terminal_field
  if not isinstance(field, MocTerminalShockCellFieldResult):
    return _terminal_measurement_failure(
      MocTerminalClosureMeasurementStatus.INVALID_INPUT,
      message='terminal_field must be a MocTerminalShockCellFieldResult',
    )
  terminal_field_status = field.status.value
  closure = observation.mixed_regime_closure
  mixed_regime_status = (
    None
    if closure is None
    else closure.status.value
    if isinstance(closure, MocMixedRegimeClosureResult)
    else 'invalid_input'
  )
  try:
    supersonic_topology = validate_moc_mesh(
      field.cells,
      vertex_tolerance_m=mesh_vertex_tolerance_m,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _terminal_measurement_failure(
      MocTerminalClosureMeasurementStatus.INVALID_INPUT,
      terminal_field_status=terminal_field_status,
      mixed_regime_status=mixed_regime_status,
      message=f'terminal supersonic mesh could not be measured: {error}',
    )
  supersonic_node_count = len(field.nodes)
  supersonic_cell_count = len(field.cells)
  try:
    shock_points = _points(
      field.terminal_shock_boundary_points_m,
      'terminal shock boundary',
    )
  except ValueError as error:
    return _terminal_measurement_failure(
      MocTerminalClosureMeasurementStatus.GEOMETRY_FAILURE,
      terminal_field_status=terminal_field_status,
      mixed_regime_status=mixed_regime_status,
      supersonic_topology=supersonic_topology,
      supersonic_node_count=supersonic_node_count,
      supersonic_cell_count=supersonic_cell_count,
      message=str(error),
    )
  try:
    terminal_shock_edge_count, shock_boundary_edges_verified, _shock_residual = (
      _terminal_shock_coverage(
        field.cells,
        shock_points,
        position_tolerance_m=position_tolerance_m,
        mesh_vertex_tolerance_m=mesh_vertex_tolerance_m,
      )
    )
  except (AttributeError, TypeError, ValueError) as error:
    shock_boundary_edges_verified = False
    terminal_shock_edge_count = 0
    edge_error = str(error)
  else:
    edge_error = ''
  terminal = field.terminal_normal_shock
  terminal_normal_shock_verified = False
  terminal_ratio: float | None = None
  terminal_upstream_total: float | None = None
  if isinstance(terminal, MocNormalShockTerminalResult):
    terminal_values = (
      terminal.shock_point_m,
      terminal.upstream_state,
      terminal.upstream_pressure_Pa,
      terminal.downstream_flow_angle_rad,
      terminal.downstream_mach,
      terminal.downstream_pressure_Pa,
      terminal.upstream_total_pressure_Pa,
      terminal.downstream_total_pressure_Pa,
      terminal.total_pressure_ratio,
    )
    if all(value is not None for value in terminal_values):
      assert terminal.shock_point_m is not None
      assert terminal.upstream_state is not None
      assert terminal.upstream_pressure_Pa is not None
      assert terminal.downstream_flow_angle_rad is not None
      assert terminal.downstream_mach is not None
      assert terminal.downstream_pressure_Pa is not None
      assert terminal.upstream_total_pressure_Pa is not None
      assert terminal.downstream_total_pressure_Pa is not None
      assert terminal.total_pressure_ratio is not None
      terminal_upstream_total = _state_total_pressure(
        terminal.upstream_state,
        terminal.upstream_pressure_Pa,
      )
      terminal_ratio = (
        terminal.downstream_total_pressure_Pa / terminal_upstream_total
      )
      terminal_scalar_values = (
        terminal.shock_point_m[0],
        terminal.shock_point_m[1],
        terminal.upstream_pressure_Pa,
        terminal.downstream_flow_angle_rad,
        terminal.downstream_mach,
        terminal.downstream_pressure_Pa,
        terminal.upstream_total_pressure_Pa,
        terminal.downstream_total_pressure_Pa,
        terminal.total_pressure_ratio,
      )
      terminal_normal_shock_verified = bool(
        terminal.converged
        and terminal.subsonic
        and all(isfinite(float(value)) for value in terminal_scalar_values)
        and terminal.downstream_mach > 0.0
        and terminal.downstream_pressure_Pa > 0.0
        and terminal.upstream_total_pressure_Pa > 0.0
        and terminal.downstream_total_pressure_Pa > 0.0
        and 0.0 < terminal.total_pressure_ratio < 1.0
        and _relative_value_residual(
          terminal_upstream_total,
          terminal.upstream_total_pressure_Pa,
        ) <= pressure_tolerance
        and _relative_value_residual(
          terminal_ratio,
          terminal.total_pressure_ratio,
        ) <= pressure_tolerance
        and hypot(
          terminal.shock_point_m[0] - shock_points[-1][0],
          terminal.shock_point_m[1] - shock_points[-1][1],
        ) <= position_tolerance_m
      )
  upstream_states = field.terminal_shock_upstream_states
  upstream_pressures = field.terminal_shock_upstream_pressure_Pa
  patch = field.terminal_shock_supersonic_downstream_states
  terminal_shock_geometry_verified = bool(
    len(upstream_states) == len(shock_points)
    and len(upstream_pressures) == len(shock_points)
    and len(patch) == len(shock_points) - 1
    and shock_boundary_edges_verified
    and abs(shock_points[-1][1]) <= axis_tolerance_m
    and all(
      isinstance(state, CharacteristicState)
      and hypot(
        state.x_m - point[0],
        state.y_m - point[1],
      ) <= state_tolerance
      for state, point in zip(upstream_states, shock_points, strict=True)
    )
    and all(
      second[0] > first[0] + position_tolerance_m
      and second[1] <= first[1] + position_tolerance_m
      and second[1] >= -axis_tolerance_m
      for first, second in zip(shock_points, shock_points[1:])
    )
  )
  upstream_total_residuals: list[float] = []
  pressure_samples_valid = len(upstream_pressures) == len(shock_points)
  if pressure_samples_valid:
    for state, pressure in zip(upstream_states, upstream_pressures, strict=True):
      if not isinstance(state, CharacteristicState) or not isfinite(float(pressure)) or pressure <= 0.0:
        pressure_samples_valid = False
        break
      upstream_total_residuals.append(
        _state_total_pressure(state, float(pressure))
      )
  patch_types_valid = all(
    isinstance(sample, MocPostShockBoundaryState)
    for sample in patch
  )
  patch_points_valid = bool(patch_types_valid and patch) and all(
    hypot(
      sample.point_m[0] - shock_points[index][0],
      sample.point_m[1] - shock_points[index][1],
    ) <= state_tolerance
    for index, sample in enumerate(patch)
  )
  patch_pressure_loss_verified = bool(
    patch_types_valid
    and pressure_samples_valid
    and patch_points_valid
    and all(
      sample.state.mach > 1.0
      and sample.upstream_total_pressure_Pa > 0.0
      and sample.downstream_total_pressure_Pa > 0.0
      and sample.downstream_total_pressure_Pa < sample.upstream_total_pressure_Pa
      and _relative_value_residual(
        sample.upstream_total_pressure_Pa,
        upstream_total_residuals[index],
      ) <= pressure_tolerance
      for index, sample in enumerate(patch)
    )
  )
  terminal_pressure_loss_verified = bool(
    patch_pressure_loss_verified
    and terminal_normal_shock_verified
    and terminal_ratio is not None
    and terminal_ratio < 1.0
  )
  supersonic_patch_verified = bool(
    patch_pressure_loss_verified
    and len(patch) == len(shock_points) - 1
  )
  ratios = tuple(
    sample.downstream_total_pressure_Pa / sample.upstream_total_pressure_Pa
    for sample in patch
    if isinstance(sample, MocPostShockBoundaryState)
    and sample.upstream_total_pressure_Pa > 0.0
  )
  if terminal_ratio is not None:
    ratios = (*ratios, terminal_ratio)
  minimum_ratio = min(ratios) if ratios else None
  maximum_ratio = max(ratios) if ratios else None
  mixed_regime_topology = _empty_topology()
  perimeter_sample_count = 0
  mixed_regime_node_count = 0
  mixed_regime_cell_count = 0
  mixed_regime_request_verified = False
  mixed_regime_boundary_verified = False
  mixed_regime_model_verified = False
  downstream_condition_verified = False
  maximum_thermodynamic_residual: float | None = None
  maximum_harmonic_residual: float | None = None
  maximum_velocity_divergence_residual: float | None = None
  mixed_messages: list[str] = []
  if closure is None:
    mixed_messages.append(
      'no mixed-regime closure was supplied; the terminal remains an open '
      'physical-closure boundary'
    )
  elif not isinstance(closure, MocMixedRegimeClosureResult):
    mixed_messages.append(
      'mixed_regime_closure must be a MocMixedRegimeClosureResult'
    )
  elif not terminal_normal_shock_verified or not isinstance(
    terminal,
    MocNormalShockTerminalResult,
  ):
    mixed_messages.append(
      'mixed-regime closure cannot be seam-checked without a verified normal shock'
    )
  else:
    try:
      expected_request = field.mixed_regime_perimeter_request()
      mixed_regime_request_verified = closure.request == expected_request
    except (TypeError, ValueError) as error:
      mixed_messages.append(f'mixed-regime terminal request could not be checked: {error}')
    if not mixed_regime_request_verified:
      mixed_messages.append(
        'mixed-regime closure request does not retain the exact terminal seam'
      )
    mixed_field = closure.field
    if not isinstance(mixed_field, MocMixedRegimeFieldResult):
      mixed_messages.append(
        'mixed-regime closure did not provide a MocMixedRegimeFieldResult'
      )
    else:
      mixed_regime_node_count = len(mixed_field.nodes)
      mixed_regime_cell_count = len(mixed_field.cells)
      perimeter_sample_count = len(mixed_field.boundary.perimeter_points_m)
      try:
        mixed_regime_topology = validate_moc_mesh(
          mixed_field.cells,
          vertex_tolerance_m=mesh_vertex_tolerance_m,
        )
      except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
        mixed_messages.append(f'mixed-regime mesh could not be measured: {error}')
      try:
        mixed_cells_geometry_valid = bool(mixed_field.cells) and all(
          len(_cell_vertices(cell)) == 3
          for cell in mixed_field.cells
        )
      except (AttributeError, TypeError, ValueError):
        mixed_cells_geometry_valid = False
      samples_valid = all(
        isinstance(sample, MocMixedRegimeFieldSample)
        and all(isfinite(float(value)) for value in (
          *sample.point_m,
          sample.mach,
          sample.flow_angle_rad,
          sample.static_pressure_Pa,
          sample.total_pressure_Pa,
          sample.gamma,
        ))
        for sample in mixed_field.nodes
      )
      try:
        independent_boundary = validate_mixed_regime_boundary(
          terminal,
          patch,
          supersonic_patch_converged=True,
          subsonic_samples=mixed_field.boundary.subsonic_samples,
          perimeter_points_m=mixed_field.boundary.perimeter_points_m,
          position_tolerance_m=position_tolerance_m,
          state_tolerance=state_tolerance,
          pressure_tolerance=pressure_tolerance,
        )
      except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
        independent_boundary = None
        mixed_messages.append(f'mixed-regime scalar seam could not be measured: {error}')
      if independent_boundary is not None:
        mixed_regime_boundary_verified = independent_boundary.converged
      if not mixed_regime_boundary_verified:
        mixed_messages.append(
          'mixed-regime scalar perimeter did not pass an independent seam check'
        )
      maximum_thermodynamic_residual = _mixed_field_thermodynamic_residual(
        mixed_field.nodes,
      )
      maximum_harmonic_residual = _mixed_field_harmonic_residual(
        mixed_field,
        position_tolerance_m=position_tolerance_m,
      )
      maximum_velocity_divergence_residual = (
        _mixed_field_velocity_divergence_residual(
          mixed_field,
          vertex_tolerance_m=mesh_vertex_tolerance_m,
        )
      )
      mixed_regime_model_verified = bool(
        mixed_field.converged
        and samples_valid
        and mixed_regime_node_count > 0
        and mixed_regime_cell_count > 0
        and mixed_cells_geometry_valid
        and mixed_regime_topology.connected
        and mixed_regime_topology.forms_closed_zone
        and not mixed_regime_topology.nonmanifold_edge_count
        and maximum_thermodynamic_residual is not None
        and maximum_thermodynamic_residual <= thermodynamic_tolerance
        and maximum_harmonic_residual is not None
        and maximum_harmonic_residual <= residual_tolerance
        and maximum_velocity_divergence_residual is not None
        and maximum_velocity_divergence_residual <= residual_tolerance
      )
      if not mixed_regime_model_verified:
        mixed_messages.append(
          'mixed-regime reference mesh or independently recomputed residuals failed'
        )
      condition = mixed_field.downstream_condition
      if (
        independent_boundary is not None
        and isinstance(condition, MocMixedRegimeDownstreamConditionResult)
        and condition.boundary == mixed_field.boundary
        and condition.condition_kind is not None
      ):
        ambient_pressure = None
        if condition.condition_kind in (
          MocMixedRegimeDownstreamConditionKind.PRESSURE_OUTFLOW_SECTION,
          MocMixedRegimeDownstreamConditionKind.AMBIENT_PRESSURE_FREE_BOUNDARY,
        ):
          if (
            closure.perimeter_spec is not None
            and closure.perimeter_spec.condition_kind is condition.condition_kind
            and closure.perimeter_spec.ambient_pressure_Pa is not None
          ):
            ambient_pressure = closure.perimeter_spec.ambient_pressure_Pa
          else:
            mixed_messages.append(
              'independent pressure-condition verification requires the '
              'explicit perimeter ambient pressure'
            )
        if (
          condition.condition_kind is MocMixedRegimeDownstreamConditionKind.SLIP_WALL
          or ambient_pressure is not None
        ):
          independent_condition = validate_mixed_regime_downstream_condition(
            independent_boundary,
            condition.condition_kind,
            ambient_pressure_Pa=ambient_pressure,
            position_tolerance_m=position_tolerance_m,
            tangent_tolerance_rad=1.0e-8,
            pressure_tolerance=pressure_tolerance,
          )
          downstream_condition_verified = bool(
            condition.converged and independent_condition.converged
          )
      if not downstream_condition_verified:
        mixed_messages.append(
          'mixed-regime downstream condition did not pass an independent check'
        )
  physical_closure_verified = bool(
    field.converged
    and supersonic_topology.connected
    and supersonic_topology.forms_closed_zone
    and not supersonic_topology.nonmanifold_edge_count
    and supersonic_node_count > 0
    and supersonic_cell_count > 0
    and terminal_normal_shock_verified
    and terminal_shock_geometry_verified
    and terminal_pressure_loss_verified
    and supersonic_patch_verified
    and mixed_regime_request_verified
    and mixed_regime_boundary_verified
    and mixed_regime_model_verified
    and downstream_condition_verified
  )
  physical_termination_verified = bool(
    physical_closure_verified and terminal_normal_shock_verified
  )
  if not supersonic_topology.connected or not supersonic_topology.forms_closed_zone:
    status = MocTerminalClosureMeasurementStatus.TOPOLOGY_FAILURE
    message = f'terminal supersonic topology failed independent measurement: {supersonic_topology.message}'
  elif not terminal_shock_geometry_verified:
    status = MocTerminalClosureMeasurementStatus.GEOMETRY_FAILURE
    message = (
      'terminal shock geometry did not pass independent measurement'
      + (f': {edge_error}' if edge_error else '')
    )
  elif not terminal_pressure_loss_verified:
    status = MocTerminalClosureMeasurementStatus.PRESSURE_FAILURE
    message = 'terminal shock total-pressure loss did not pass independent measurement'
  elif not terminal_normal_shock_verified or not supersonic_patch_verified:
    status = MocTerminalClosureMeasurementStatus.SUPERSONIC_FAILURE
    message = 'terminal normal-shock or supersonic-patch checks failed independent measurement'
  elif not physical_closure_verified:
    status = MocTerminalClosureMeasurementStatus.MIXED_REGIME_FAILURE
    message = '; '.join(mixed_messages) or 'mixed-regime closure did not pass independent measurement'
  else:
    status = MocTerminalClosureMeasurementStatus.CONVERGED
    message = (
      'terminal supersonic region and supplied mixed-regime closure passed '
      'independent geometry, topology, seam, pressure, and residual checks; '
      'the result remains a terminal stop and is not a production validation claim'
    )
  return _terminal_measurement_failure(
    status,
    terminal_field_status=terminal_field_status,
    mixed_regime_status=mixed_regime_status,
    supersonic_topology=supersonic_topology,
    mixed_regime_topology=mixed_regime_topology,
    terminal_shock_sample_count=len(shock_points),
    terminal_shock_edge_count=terminal_shock_edge_count,
    terminal_shock_downstream_sample_count=len(patch),
    perimeter_sample_count=perimeter_sample_count,
    supersonic_node_count=supersonic_node_count,
    supersonic_cell_count=supersonic_cell_count,
    mixed_regime_node_count=mixed_regime_node_count,
    mixed_regime_cell_count=mixed_regime_cell_count,
    terminal_normal_shock_verified=terminal_normal_shock_verified,
    terminal_shock_geometry_verified=terminal_shock_geometry_verified,
    terminal_pressure_loss_verified=terminal_pressure_loss_verified,
    supersonic_patch_verified=supersonic_patch_verified,
    mixed_regime_request_verified=mixed_regime_request_verified,
    mixed_regime_boundary_verified=mixed_regime_boundary_verified,
    mixed_regime_model_verified=mixed_regime_model_verified,
    downstream_condition_verified=downstream_condition_verified,
    physical_closure_verified=physical_closure_verified,
    physical_termination_verified=physical_termination_verified,
    minimum_terminal_total_pressure_ratio=minimum_ratio,
    maximum_terminal_total_pressure_ratio=maximum_ratio,
    maximum_thermodynamic_residual=maximum_thermodynamic_residual,
    maximum_harmonic_residual=maximum_harmonic_residual,
    maximum_velocity_divergence_residual=maximum_velocity_divergence_residual,
    message=message,
  )
####


def _chain_failure(message: str) -> MocShockCellChainMeasurement:
  return MocShockCellChainMeasurement(
    status=MocShockCellMeasurementStatus.CHAIN_FAILURE,
    operator_id=MOC_SHOCK_CELL_CHAIN_OPERATOR_ID,
    cells=(),
    axial_extent_m=None,
    shock_start_spacing_m=(),
    total_mesh_area_m2=None,
    claim_status='not_accepted',
    message=message,
  )
####


def measure_moc_shock_cell_chain(
  observations: Sequence[MocShockCellObservation],
  *,
  position_tolerance_m: float = 1.0e-10,
  axis_tolerance_m: float = 1.0e-10,
  area_tolerance_m2: float = 1.0e-9,
  mesh_vertex_tolerance_m: float = 1.0e-12,
) -> MocShockCellChainMeasurement:
  """Measure an ordered set of independently assembled MOC shock cells."""

  items = tuple(observations)
  if not items:
    return _chain_failure('at least one shock-cell observation is required')
  if any(not isinstance(item, MocShockCellObservation) for item in items):
    return _chain_failure('chain observations must be MocShockCellObservation values')
  indices = tuple(item.cell_index for item in items)
  if indices != tuple(range(1, len(items) + 1)):
    return _chain_failure('shock-cell observations must have contiguous one-based indices')
  measurements = tuple(
    measure_moc_shock_cell(
      item,
      position_tolerance_m=position_tolerance_m,
      axis_tolerance_m=axis_tolerance_m,
      area_tolerance_m2=area_tolerance_m2,
      mesh_vertex_tolerance_m=mesh_vertex_tolerance_m,
    )
    for item in items
  )
  if any(not measurement.converged for measurement in measurements):
    return MocShockCellChainMeasurement(
      status=MocShockCellMeasurementStatus.CHAIN_FAILURE,
      operator_id=MOC_SHOCK_CELL_CHAIN_OPERATOR_ID,
      cells=measurements,
      axial_extent_m=None,
      shock_start_spacing_m=(),
      total_mesh_area_m2=None,
      claim_status='not_accepted',
      message='one or more cell measurements failed; no chain metric was promoted',
    )
  extents = tuple(measurement.axial_extent_m for measurement in measurements)
  if any(extent is None for extent in extents):
    return _chain_failure('converged cell measurements must expose axial extents')
  resolved_extents = tuple(extent for extent in extents if extent is not None)
  if any(
      right[0] < left[1] - position_tolerance_m
      for left, right in zip(resolved_extents, resolved_extents[1:])
  ):
    return MocShockCellChainMeasurement(
      status=MocShockCellMeasurementStatus.CHAIN_FAILURE,
      operator_id=MOC_SHOCK_CELL_CHAIN_OPERATOR_ID,
      cells=measurements,
      axial_extent_m=None,
      shock_start_spacing_m=(),
      total_mesh_area_m2=None,
      claim_status='not_accepted',
      message='continued shock-cell measurement extents overlap or reverse order',
    )
  shock_starts = tuple(
    measurement.shock_start_m[0]
    for measurement in measurements
    if measurement.shock_start_m is not None
  )
  return MocShockCellChainMeasurement(
    status=MocShockCellMeasurementStatus.CONVERGED,
    operator_id=MOC_SHOCK_CELL_CHAIN_OPERATOR_ID,
    cells=measurements,
    axial_extent_m=(resolved_extents[0][0], resolved_extents[-1][1]),
    shock_start_spacing_m=tuple(
      right - left for left, right in zip(shock_starts, shock_starts[1:])
    ),
    total_mesh_area_m2=fsum(
      measurement.mesh_area_m2
      for measurement in measurements
      if measurement.mesh_area_m2 is not None
    ),
    claim_status='not_accepted',
    message=(
      'continued shock-cell geometry measured with independent per-cell '
      'topology checks; this does not establish physical chain closure'
    ),
  )
####
