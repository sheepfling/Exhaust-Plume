"""Assembly of the reflected planar characteristic zone.

This module assembles the compatible characteristic network between the
centerline and the pressure-matched free boundary.  It intentionally stops at
that open physical boundary: no compression state, shock endpoint, or
downstream total-pressure continuation is inferred here.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite, sqrt

import numpy as np

from exhaust_plume.geometry.contracts import GeometryStatus
from exhaust_plume.geometry.polygons import validate_polygon
from exhaust_plume.models.moc.boundary import MocReflectedBoundaryResult
from exhaust_plume.models.moc.fan import MocExpansionFanResult
from exhaust_plume.models.moc.primitives import (
  CharacteristicPointResult,
  CharacteristicState,
  interior_characteristic_point,
)
from exhaust_plume.models.moc.topology import MocTopologyResult, validate_moc_mesh

__all__ = (
  'MocCharacteristicCell',
  'MocCharacteristicNode',
  'MocZoneAssemblyStatus',
  'MocReflectedCharacteristicZoneResult',
  'assemble_reflected_characteristic_zone',
)


class MocZoneAssemblyStatus(str, Enum):
  """Outcome of assembling a reflected characteristic network."""

  CONVERGED_OPEN = 'converged_open'
  INVALID_INPUT = 'invalid_input'
  GEOMETRY_FAILURE = 'geometry_failure'
  TOPOLOGY_FAILURE = 'topology_failure'
####


@dataclass(frozen=True, slots=True)
class MocCharacteristicNode:
  """One compatible intersection in the reflected characteristic lattice."""

  centerline_index: int
  boundary_index: int
  point_m: tuple[float, float]
  state: CharacteristicState
  point_result: CharacteristicPointResult
####


@dataclass(frozen=True, slots=True)
class MocCharacteristicCell:
  """A validated triangular or quadrilateral characteristic cell."""

  cell_index: int
  cell_kind: str
  vertices_xr_m: tuple[tuple[float, float], ...]
  centerline_indices: tuple[int, ...]
  boundary_indices: tuple[int, ...]
  geometry_status: GeometryStatus = GeometryStatus.VALID

  def __post_init__(self) -> None:
    if len(self.vertices_xr_m) not in (3, 4):
      raise ValueError('characteristic cells must be triangular or quadrilateral')
    validation = validate_polygon(np.asarray(self.vertices_xr_m, dtype=float))
    if not validation.is_valid:
      raise ValueError(f'characteristic cell polygon is invalid: {validation.status.value}')
    object.__setattr__(self, 'geometry_status', GeometryStatus.VALID)
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedCharacteristicZoneResult:
  """An assembled but physically open reflected characteristic zone.

  ``status`` reports numerical assembly of the characteristic network.  A
  ``CONVERGED_OPEN`` result is deliberately not a closed shock cell: the
  perimeter is topologically connected, while compression/shock closure and
  downstream total-pressure bookkeeping remain explicit pending gates.
  """

  status: MocZoneAssemblyStatus
  characteristic_count: int
  nodes: tuple[MocCharacteristicNode, ...]
  cells: tuple[MocCharacteristicCell, ...]
  topology: MocTopologyResult
  coverage_area_m2: float | None
  coverage_area_residual_m2: float | None
  physical_closure_status: str
  shock_closure_status: str
  message: str = ''

  @property
  def converged(self) -> bool:
    return self.status is MocZoneAssemblyStatus.CONVERGED_OPEN
  ####

  @property
  def node_count(self) -> int:
    return len(self.nodes)
  ####

  @property
  def cell_count(self) -> int:
    return len(self.cells)
  ####
####


def _empty_topology() -> MocTopologyResult:
  return validate_moc_mesh(())
####


def _failure(
  *,
  status: MocZoneAssemblyStatus,
  characteristic_count: int,
  nodes: tuple[MocCharacteristicNode, ...] = (),
  cells: tuple[MocCharacteristicCell, ...] = (),
  topology: MocTopologyResult | None = None,
  coverage_area_m2: float | None = None,
  coverage_area_residual_m2: float | None = None,
  message: str,
) -> MocReflectedCharacteristicZoneResult:
  return MocReflectedCharacteristicZoneResult(
    status=status,
    characteristic_count=characteristic_count,
    nodes=nodes,
    cells=cells,
    topology=_empty_topology() if topology is None else topology,
    coverage_area_m2=coverage_area_m2,
    coverage_area_residual_m2=coverage_area_residual_m2,
    physical_closure_status='not_assembled',
    shock_closure_status='not_assembled',
    message=message,
  )
####


def _signed_area(vertices: tuple[tuple[float, float], ...]) -> float:
  return 0.5 * sum(
    vertices[index][0] * vertices[(index + 1) % len(vertices)][1]
    - vertices[(index + 1) % len(vertices)][0] * vertices[index][1]
    for index in range(len(vertices))
  )
####


def _coverage_area(
  cells: tuple[MocCharacteristicCell, ...],
  *,
  vertex_tolerance_m: float,
) -> tuple[float, float] | None:
  """Return ``(perimeter_area, cell_area_residual)`` for one cell zone."""

  if not cells:
    return None
  signed_areas = [_signed_area(cell.vertices_xr_m) for cell in cells]
  if not all(isfinite(value) for value in signed_areas):
    return None
  if any(value == 0.0 for value in signed_areas) or (
    min(signed_areas) < 0.0 < max(signed_areas)
  ):
    return None
  edge_counts: dict[tuple[tuple[int, int], tuple[int, int]], int] = {}
  vertex_points: dict[tuple[int, int], tuple[float, float]] = {}
  for cell in cells:
    keys = []
    for point in cell.vertices_xr_m:
      key = round(point[0] / vertex_tolerance_m), round(point[1] / vertex_tolerance_m)
      keys.append(key)
      vertex_points[key] = point
    for first, second in zip(keys, (*keys[1:], keys[0])):
      edge = (first, second) if first <= second else (second, first)
      edge_counts[edge] = edge_counts.get(edge, 0) + 1
  boundary_edges = [edge for edge, count in edge_counts.items() if count == 1]
  if not boundary_edges:
    return None
  boundary_graph: dict[tuple[int, int], list[tuple[int, int]]] = {}
  for first, second in boundary_edges:
    boundary_graph.setdefault(first, []).append(second)
    boundary_graph.setdefault(second, []).append(first)
  if not all(len(neighbors) == 2 for neighbors in boundary_graph.values()):
    return None
  start = next(iter(boundary_graph))
  cycle = [start]
  previous: tuple[int, int] | None = None
  current = start
  while True:
    neighbors = boundary_graph[current]
    next_vertex = neighbors[0] if neighbors[0] != previous else neighbors[1]
    if next_vertex == start:
      break
    if next_vertex in cycle:
      return None
    cycle.append(next_vertex)
    previous, current = current, next_vertex
    if len(cycle) > len(boundary_graph):
      return None
  if len(cycle) != len(boundary_graph):
    return None
  perimeter_vertices = tuple(vertex_points[key] for key in cycle)
  perimeter_area = abs(_signed_area(perimeter_vertices))
  cell_area = sum(abs(value) for value in signed_areas)
  return perimeter_area, cell_area - perimeter_area
####


def assemble_reflected_characteristic_zone(
  fan: MocExpansionFanResult,
  reflected_boundary: MocReflectedBoundaryResult,
  *,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
) -> MocReflectedCharacteristicZoneResult:
  """Assemble the reflected centerline/free-boundary characteristic lattice.

  The lattice has three explicit parts: an axis strip, interior
  characteristic quadrilaterals, and a triangular strip terminating on the
  pressure-matched free boundary.  Boundary diagonal nodes are required to
  reproduce the supplied free-boundary points; this prevents a source-angle
  or marching-angle inconsistency from being hidden by topology alone.

  The returned mesh is an open physical solver lane.  Its ``forms_closed_zone``
  topology flag means that the finite cells have one connected polygonal
  perimeter; it does not mean that a shock or downstream physical closure has
  been solved.
  """

  if not isfinite(position_tolerance_m) or position_tolerance_m <= 0.0:
    raise ValueError('position_tolerance_m must be finite and positive')
  if not isfinite(invariant_tolerance) or invariant_tolerance <= 0.0:
    raise ValueError('invariant_tolerance must be finite and positive')
  if not fan.converged:
    return _failure(
      status=MocZoneAssemblyStatus.INVALID_INPUT,
      characteristic_count=0,
      message=f'lip fan is not converged: {fan.message}',
    )
  if not reflected_boundary.converged:
    return _failure(
      status=MocZoneAssemblyStatus.INVALID_INPUT,
      characteristic_count=0,
      message=f'reflected free boundary is not converged: {reflected_boundary.message}',
    )
  ####
  centerline_states = reflected_boundary.centerline_states
  boundary_states = reflected_boundary.boundary_states
  if len(centerline_states) < 3:
    return _failure(
      status=MocZoneAssemblyStatus.INVALID_INPUT,
      characteristic_count=0,
      message='reflected characteristic assembly requires at least two intervals',
    )
  expected_count = len(centerline_states)
  if (
    len(fan.states) != expected_count
    or len(fan.lip_states) != expected_count
    or len(fan.centerline_points_m) != expected_count
    or len(boundary_states) != expected_count
    or len(reflected_boundary.boundary_points_m) != expected_count
  ):
    return _failure(
      status=MocZoneAssemblyStatus.INVALID_INPUT,
      characteristic_count=max(0, expected_count - 1),
      message='fan, centerline, and reflected-boundary arrays have inconsistent lengths',
    )
  characteristic_count = expected_count - 1
  ####
  nodes_by_index: dict[tuple[int, int], MocCharacteristicNode] = {}
  for centerline_index in range(expected_count):
    for boundary_index in range(centerline_index + 1):
      point_result = interior_characteristic_point(
        centerline_states[centerline_index],
        boundary_states[boundary_index],
        position_tolerance_m=position_tolerance_m,
        invariant_tolerance=invariant_tolerance,
      )
      if not point_result.converged or point_result.state is None or point_result.point_m is None:
        nodes = tuple(nodes_by_index.values())
        return _failure(
          status=MocZoneAssemblyStatus.GEOMETRY_FAILURE,
          characteristic_count=characteristic_count,
          nodes=nodes,
          message=(
            f'characteristic node ({centerline_index}, {boundary_index}) failed: '
            f'{point_result.message}'
          ),
        )
      point = point_result.point_m
      if centerline_index == boundary_index:
        boundary_point = reflected_boundary.boundary_points_m[boundary_index]
        discrepancy = sqrt(
          (point[0] - boundary_point[0]) ** 2
          + (point[1] - boundary_point[1]) ** 2
        )
        if discrepancy > position_tolerance_m:
          nodes = tuple(nodes_by_index.values())
          return _failure(
            status=MocZoneAssemblyStatus.GEOMETRY_FAILURE,
            characteristic_count=characteristic_count,
            nodes=nodes,
            message=(
              f'boundary diagonal node ({centerline_index}, {boundary_index}) '
              f'does not reproduce the supplied boundary point; residual={discrepancy}'
            ),
          )
        point = (float(boundary_point[0]), float(boundary_point[1]))
      nodes_by_index[(centerline_index, boundary_index)] = MocCharacteristicNode(
        centerline_index=centerline_index,
        boundary_index=boundary_index,
        point_m=(float(point[0]), float(point[1])),
        state=point_result.state,
        point_result=point_result,
      )
  ####
  nodes = tuple(nodes_by_index.values())

  def node_point(centerline_index: int, boundary_index: int) -> tuple[float, float]:
    return nodes_by_index[(centerline_index, boundary_index)].point_m

  def axis_point(index: int) -> tuple[float, float]:
    state = centerline_states[index]
    if not isfinite(state.x_m) or not isfinite(state.y_m):
      raise ValueError(f'centerline state {index} has a non-finite coordinate')
    if abs(state.y_m) > position_tolerance_m:
      raise ValueError(f'centerline state {index} is not on the symmetry line')
    return state.x_m, 0.0

  cells_list: list[MocCharacteristicCell] = []
  try:
    for index in range(characteristic_count):
      cells_list.append(
        MocCharacteristicCell(
          cell_index=len(cells_list),
          cell_kind='axis-strip',
          vertices_xr_m=(
            axis_point(index),
            axis_point(index + 1),
            node_point(index + 1, 0),
            node_point(index, 0),
          ),
          centerline_indices=(index, index + 1),
          boundary_indices=(0,),
        )
      )
    for row in range(1, expected_count - 1):
      for column in range(row):
        cells_list.append(
          MocCharacteristicCell(
            cell_index=len(cells_list),
            cell_kind='interior',
            vertices_xr_m=(
              node_point(row, column),
              node_point(row + 1, column),
              node_point(row + 1, column + 1),
              node_point(row, column + 1),
            ),
            centerline_indices=(row, row + 1),
            boundary_indices=(column, column + 1),
          )
        )
    for index in range(characteristic_count):
      cells_list.append(
        MocCharacteristicCell(
          cell_index=len(cells_list),
          cell_kind='free-boundary-strip',
          vertices_xr_m=(
            node_point(index, index),
            node_point(index + 1, index),
            node_point(index + 1, index + 1),
          ),
          centerline_indices=(index + 1,),
          boundary_indices=(index, index + 1),
        )
      )
  except (KeyError, ValueError) as error:
    return _failure(
      status=MocZoneAssemblyStatus.GEOMETRY_FAILURE,
      characteristic_count=characteristic_count,
      nodes=nodes,
      cells=tuple(cells_list),
      message=f'characteristic cell geometry failed: {error}',
    )
  ####
  cells = tuple(cells_list)
  topology = validate_moc_mesh(cells)
  if not topology.forms_closed_zone or topology.nonmanifold_edge_count:
    return _failure(
      status=MocZoneAssemblyStatus.TOPOLOGY_FAILURE,
      characteristic_count=characteristic_count,
      nodes=nodes,
      cells=cells,
      topology=topology,
      message=f'characteristic zone topology failed: {topology.message}',
    )
  coverage = _coverage_area(cells, vertex_tolerance_m=1.0e-12)
  if coverage is None:
    return _failure(
      status=MocZoneAssemblyStatus.TOPOLOGY_FAILURE,
      characteristic_count=characteristic_count,
      nodes=nodes,
      cells=cells,
      topology=topology,
      message='characteristic zone coverage area could not be validated',
    )
  coverage_area_m2, coverage_area_residual_m2 = coverage
  if abs(coverage_area_residual_m2) > max(1.0e-12, 1.0e-9 * coverage_area_m2):
    return _failure(
      status=MocZoneAssemblyStatus.TOPOLOGY_FAILURE,
      characteristic_count=characteristic_count,
      nodes=nodes,
      cells=cells,
      topology=topology,
      coverage_area_m2=coverage_area_m2,
      coverage_area_residual_m2=coverage_area_residual_m2,
      message=(
        'characteristic zone cell-area coverage residual exceeded tolerance: '
        f'{coverage_area_residual_m2}'
      ),
    )
  return MocReflectedCharacteristicZoneResult(
    status=MocZoneAssemblyStatus.CONVERGED_OPEN,
    characteristic_count=characteristic_count,
    nodes=nodes,
    cells=cells,
    topology=topology,
    coverage_area_m2=coverage_area_m2,
    coverage_area_residual_m2=coverage_area_residual_m2,
    physical_closure_status='open',
    shock_closure_status='not_assembled',
  )
####
