"""Connectivity and boundary checks for isolated planar MOC meshes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Sequence

import numpy as np

from exhaust_plume.geometry.polygons import validate_polygon

__all__ = (
  'MocTopologyResult',
  'MocTopologyStatus',
  'validate_moc_mesh',
)


class MocTopologyStatus(str, Enum):
  """Topological outcome for a finite collection of planar cells."""

  CLOSED = 'closed'
  OPEN = 'open'
  DISCONNECTED = 'disconnected'
  NONMANIFOLD = 'nonmanifold'
  INVALID_INPUT = 'invalid_input'
####


@dataclass(frozen=True, slots=True)
class MocTopologyResult:
  """Mesh connectivity, boundary, and non-manifold edge diagnostics."""

  status: MocTopologyStatus
  cell_count: int
  edge_count: int
  boundary_edge_count: int
  boundary_component_count: int
  boundary_is_closed_cycle: bool
  nonmanifold_edge_count: int
  connected: bool
  message: str = ''

  @property
  def is_closed(self) -> bool:
    return self.status is MocTopologyStatus.CLOSED

  @property
  def forms_closed_zone(self) -> bool:
    """Return whether the cells form one simply bounded planar zone."""

    return (
      self.connected
      and self.nonmanifold_edge_count == 0
      and self.boundary_component_count == 1
      and self.boundary_is_closed_cycle
    )
####


def _vertex_key(point: Sequence[float], tolerance_m: float) -> tuple[int, int]:
  x, y = (float(value) for value in point)
  return round(x / tolerance_m), round(y / tolerance_m)
####


def validate_moc_mesh(
  cells: Sequence[object],
  *,
  vertex_tolerance_m: float = 1.0e-12,
) -> MocTopologyResult:
  """Validate cell connectivity without inventing missing boundary cells.

  An ``OPEN`` result is valid evidence for a partial characteristic mesh.  It
  becomes ``CLOSED`` only when every edge belongs to exactly one or two cells,
  the cells form one connected component, and no edge is left on the boundary.
  """

  if not isfinite(vertex_tolerance_m) or vertex_tolerance_m <= 0.0:
    raise ValueError('vertex_tolerance_m must be finite and positive')
  if not cells:
    return MocTopologyResult(
      status=MocTopologyStatus.INVALID_INPUT,
      cell_count=0,
      edge_count=0,
      boundary_edge_count=0,
      boundary_component_count=0,
      boundary_is_closed_cycle=False,
      nonmanifold_edge_count=0,
      connected=False,
      message='MOC mesh must contain at least one cell',
    )
  ####
  edge_owners: dict[tuple[tuple[int, int], tuple[int, int]], list[int]] = {}
  polygon_keys: set[tuple[tuple[int, int], ...]] = set()
  for cell_index, cell in enumerate(cells):
    vertices = getattr(cell, 'vertices_xr_m', None)
    if vertices is None:
      return MocTopologyResult(
        status=MocTopologyStatus.INVALID_INPUT,
        cell_count=len(cells),
        edge_count=0,
        boundary_edge_count=0,
        boundary_component_count=0,
        boundary_is_closed_cycle=False,
        nonmanifold_edge_count=0,
        connected=False,
        message=f'cell {cell_index} does not expose vertices_xr_m',
      )
    points = np.asarray(vertices, dtype=float)
    if points.ndim != 2 or points.shape[1] != 2 or not np.isfinite(points).all():
      return MocTopologyResult(
        status=MocTopologyStatus.INVALID_INPUT,
        cell_count=len(cells),
        edge_count=0,
        boundary_edge_count=0,
        boundary_component_count=0,
        boundary_is_closed_cycle=False,
        nonmanifold_edge_count=0,
        connected=False,
        message=f'cell {cell_index} has non-finite or malformed vertices',
      )
    polygon = validate_polygon(points, tolerance=vertex_tolerance_m)
    if not polygon.is_valid:
      return MocTopologyResult(
        status=MocTopologyStatus.INVALID_INPUT,
        cell_count=len(cells),
        edge_count=0,
        boundary_edge_count=0,
        boundary_component_count=0,
        boundary_is_closed_cycle=False,
        nonmanifold_edge_count=0,
        connected=False,
        message=f'cell {cell_index} is not a valid simple polygon: {polygon.status.value}',
      )
    keys = tuple(_vertex_key(point, vertex_tolerance_m) for point in points)
    canonical_polygon = tuple(sorted(keys))
    if canonical_polygon in polygon_keys:
      return MocTopologyResult(
        status=MocTopologyStatus.INVALID_INPUT,
        cell_count=len(cells),
        edge_count=0,
        boundary_edge_count=0,
        boundary_component_count=0,
        boundary_is_closed_cycle=False,
        nonmanifold_edge_count=0,
        connected=False,
        message=f'cell {cell_index} duplicates another cell',
      )
    polygon_keys.add(canonical_polygon)
    for first, second in zip(keys, (*keys[1:], keys[0])):
      edge: tuple[tuple[int, int], tuple[int, int]] = (
        (first, second) if first <= second else (second, first)
      )
      edge_owners.setdefault(edge, []).append(cell_index)
  ####
  nonmanifold_edges = [owners for owners in edge_owners.values() if len(owners) > 2]
  if nonmanifold_edges:
    return MocTopologyResult(
      status=MocTopologyStatus.NONMANIFOLD,
      cell_count=len(cells),
      edge_count=len(edge_owners),
      boundary_edge_count=sum(len(owners) == 1 for owners in edge_owners.values()),
      boundary_component_count=0,
      boundary_is_closed_cycle=False,
      nonmanifold_edge_count=len(nonmanifold_edges),
      connected=False,
      message='one or more edges belong to more than two cells',
    )
  ####
  adjacency: dict[int, set[int]] = {index: set() for index in range(len(cells))}
  for owners in edge_owners.values():
    if len(owners) == 2:
      first, second = owners
      adjacency[first].add(second)
      adjacency[second].add(first)
  visited = {0}
  frontier = [0]
  while frontier:
    current = frontier.pop()
    for neighbor in adjacency[current]:
      if neighbor not in visited:
        visited.add(neighbor)
        frontier.append(neighbor)
  connected = len(visited) == len(cells)
  boundary_edges = [edge for edge, owners in edge_owners.items() if len(owners) == 1]
  boundary_edge_count = len(boundary_edges)
  boundary_graph: dict[tuple[int, int], set[tuple[int, int]]] = {}
  for first, second in boundary_edges:
    boundary_graph.setdefault(first, set()).add(second)
    boundary_graph.setdefault(second, set()).add(first)
  boundary_is_closed_cycle = bool(boundary_graph) and all(
    len(neighbors) == 2 for neighbors in boundary_graph.values()
  )
  boundary_component_count = 0
  boundary_visited: set[tuple[int, int]] = set()
  for start in boundary_graph:
    if start in boundary_visited:
      continue
    boundary_component_count += 1
    boundary_frontier = [start]
    boundary_visited.add(start)
    while boundary_frontier:
      current = boundary_frontier.pop()
      for neighbor in boundary_graph[current]:
        if neighbor not in boundary_visited:
          boundary_visited.add(neighbor)
          boundary_frontier.append(neighbor)
  if not connected:
    status = MocTopologyStatus.DISCONNECTED
    message = 'MOC cells do not form one connected component'
  elif boundary_edge_count:
    status = MocTopologyStatus.OPEN
    message = (
      'MOC mesh has an explicit physical boundary; its polygonal perimeter is '
      'topologically closed but its physical closure remains unresolved'
      if boundary_is_closed_cycle and boundary_component_count == 1
      else 'MOC mesh has an explicit boundary that is not one closed perimeter'
    )
  else:
    status = MocTopologyStatus.CLOSED
    message = ''
  return MocTopologyResult(
    status=status,
    cell_count=len(cells),
    edge_count=len(edge_owners),
    boundary_edge_count=boundary_edge_count,
    boundary_component_count=boundary_component_count,
    boundary_is_closed_cycle=boundary_is_closed_cycle,
    nonmanifold_edge_count=0,
    connected=connected,
    message=message,
  )
####
