"""Composite first-cell topology for the planar MOC research lane.

The shock/ambient strip and the terminal centerline-reflection patch are each
open transitions.  They share the strip's terminal shock-sourced ``C+`` edge,
so their union can be checked as one finite supersonic cell: the fitted shock,
ambient streamline, centerline, and the outgoing ``C-`` trace are its boundary
paths.  This module records that physical-boundary composite without claiming
that the caller-supplied downstream law or the reflected upstream field is a
production closure.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Sequence

from exhaust_plume.models.moc.ambient_shock_strip import (
  MocAmbientShockStripResult,
  MocAmbientShockStripStatus,
)
from exhaust_plume.models.moc.ambient_boundary import MocAmbientPressureBoundaryResult
from exhaust_plume.models.moc.post_shock import MocShockBoundaryFitResult
from exhaust_plume.models.moc.terminal_patch import (
  MocTerminalReflectionPatchResult,
  MocTerminalReflectionPatchStatus,
)
from exhaust_plume.models.moc.chain import MocChainBoundarySample
from exhaust_plume.models.moc.primitives import CharacteristicState
from exhaust_plume.models.moc.topology import MocTopologyResult, validate_moc_mesh
from exhaust_plume.models.moc.zone import MocCharacteristicCell, MocCharacteristicNode

__all__ = (
  'MocFirstCellCompositeStatus',
  'MocFirstCellCompositeResult',
  'assemble_first_cell_composite',
)


class MocFirstCellCompositeStatus(str, Enum):
  """Outcome of joining the physical strip and reflection patch."""

  CONVERGED_CLOSED_SUPERSONIC_COMPOSITE = 'converged_closed_supersonic_composite'
  INVALID_INPUT = 'invalid_input'
  SHOCK_FAILURE = 'shock_boundary_failure'
  STRIP_FAILURE = 'shock_ambient_strip_failure'
  PATCH_FAILURE = 'terminal_reflection_patch_failure'
  SEAM_FAILURE = 'shared_terminal_seam_failure'
  TOPOLOGY_FAILURE = 'topology_failure'
  BOUNDARY_FAILURE = 'physical_boundary_path_failure'
####


@dataclass(frozen=True, slots=True)
class MocFirstCellCompositeResult:
  """A closed supersonic first-cell composite with a carried downstream edge.

  ``topology_closed`` and ``physical_boundary_conditions_verified`` describe
  the assembled shock/ambient/axis boundary network.  ``physical_closure`` is
  intentionally separate and remains false until the reflected upstream field
  and downstream boundary law are accepted for production use.
  """

  status: MocFirstCellCompositeStatus
  shock_fit: MocShockBoundaryFitResult | None
  strip: MocAmbientShockStripResult | None
  patch: MocTerminalReflectionPatchResult | None
  nodes: tuple[MocCharacteristicNode, ...]
  cells: tuple[MocCharacteristicCell, ...]
  topology: MocTopologyResult
  shock_boundary_points_m: tuple[tuple[float, float], ...]
  ambient_boundary_points_m: tuple[tuple[float, float], ...]
  centerline_boundary_points_m: tuple[tuple[float, float], ...]
  continuation_boundary_points_m: tuple[tuple[float, float], ...]
  continuation_boundary_states: tuple[CharacteristicState, ...]
  continuation_boundary_total_pressure_Pa: tuple[float, ...]
  ambient_boundary: MocAmbientPressureBoundaryResult | None
  maximum_geometry_residual_m: float | None
  maximum_absolute_invariant_residual: float | None
  minimum_post_shock_total_pressure_ratio: float | None
  maximum_post_shock_total_pressure_ratio: float | None
  shared_terminal_seam_verified: bool
  physical_boundary_conditions_verified: bool
  message: str = ''

  def __post_init__(self) -> None:
    if len(self.continuation_boundary_states) != len(
      self.continuation_boundary_total_pressure_Pa
    ):
      raise ValueError(
        'continuation boundary states and total-pressure samples must have equal lengths'
      )
    if any(
      not isfinite(float(value)) or value <= 0.0
      for value in self.continuation_boundary_total_pressure_Pa
    ):
      raise ValueError(
        'continuation boundary total-pressure samples must be finite and positive'
      )
  ####

  @property
  def converged(self) -> bool:
    return self.status is MocFirstCellCompositeStatus.CONVERGED_CLOSED_SUPERSONIC_COMPOSITE
  ####

  @property
  def topology_closed(self) -> bool:
    return (
      self.converged
      and self.topology.connected
      and self.topology.forms_closed_zone
      and self.topology.nonmanifold_edge_count == 0
    )
  ####

  @property
  def physical_closure_verified(self) -> bool:
    """Keep production closure distinct from the closed supersonic composite."""

    return False
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    return True
  ####

  @property
  def upstream_shock_coupling_verified(self) -> bool:
    """Whether the fitted shock retained a complete upstream state/pressure edge."""

    if self.shock_fit is None or not self.shock_fit.converged:
      return False
    boundary_count = len(self.shock_fit.boundary_states)
    if (
      len(self.shock_fit.upstream_states) != boundary_count
      or len(self.shock_fit.upstream_total_pressure_Pa) != boundary_count
    ):
      return False
    return all(
      abs(state.x_m - sample.point_m[0]) <= 1.0e-10
      and abs(state.y_m - sample.point_m[1]) <= 1.0e-10
      and abs(pressure - sample.upstream_total_pressure_Pa)
      <= 1.0e-8 * max(1.0, abs(pressure), abs(sample.upstream_total_pressure_Pa))
      for state, pressure, sample in zip(
        self.shock_fit.upstream_states,
        self.shock_fit.upstream_total_pressure_Pa,
        self.shock_fit.boundary_states,
        strict=True,
      )
    )
  ####

  @property
  def continuation_boundary(self) -> tuple[MocChainBoundarySample, ...]:
    return tuple(
      MocChainBoundarySample(state=state, total_pressure_Pa=pressure)
      for state, pressure in zip(
        self.continuation_boundary_states,
        self.continuation_boundary_total_pressure_Pa,
        strict=True,
      )
    )
  ####

  @property
  def node_count(self) -> int:
    return len(self.nodes)
  ####

  @property
  def cell_count(self) -> int:
    return len(self.cells)
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'topology_closed': self.topology_closed,
      'physical_boundary_conditions_verified': self.physical_boundary_conditions_verified,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'upstream_shock_coupling_verified': self.upstream_shock_coupling_verified,
      'shared_terminal_seam_verified': self.shared_terminal_seam_verified,
      'node_count': self.node_count,
      'cell_count': self.cell_count,
      'topology_status': self.topology.status.value,
      'topology_connected': self.topology.connected,
      'topology_forms_closed_zone': self.topology.forms_closed_zone,
      'topology_boundary_edge_count': self.topology.boundary_edge_count,
      'topology_nonmanifold_edge_count': self.topology.nonmanifold_edge_count,
      'shock_boundary_sample_count': len(self.shock_boundary_points_m),
      'ambient_boundary_sample_count': len(self.ambient_boundary_points_m),
      'centerline_boundary_sample_count': len(self.centerline_boundary_points_m),
      'continuation_boundary_sample_count': len(self.continuation_boundary_points_m),
      'continuation_boundary_kind': 'terminal-characteristic-trace',
      'ambient_boundary': (
        None if self.ambient_boundary is None else self.ambient_boundary.as_report()
      ),
      'maximum_geometry_residual_m': self.maximum_geometry_residual_m,
      'maximum_absolute_invariant_residual': self.maximum_absolute_invariant_residual,
      'minimum_post_shock_total_pressure_ratio': self.minimum_post_shock_total_pressure_ratio,
      'maximum_post_shock_total_pressure_ratio': self.maximum_post_shock_total_pressure_ratio,
      'message': self.message,
    }
  ####


def _empty_topology() -> MocTopologyResult:
  return validate_moc_mesh(())


def _failure(
  status: MocFirstCellCompositeStatus,
  *,
  shock_fit: MocShockBoundaryFitResult | None = None,
  strip: MocAmbientShockStripResult | None = None,
  patch: MocTerminalReflectionPatchResult | None = None,
  nodes: Sequence[MocCharacteristicNode] = (),
  cells: Sequence[MocCharacteristicCell] = (),
  topology: MocTopologyResult | None = None,
  shock_points: Sequence[tuple[float, float]] = (),
  ambient_points: Sequence[tuple[float, float]] = (),
  centerline_points: Sequence[tuple[float, float]] = (),
  continuation_points: Sequence[tuple[float, float]] = (),
  continuation_states: Sequence[CharacteristicState] = (),
  continuation_pressures: Sequence[float] = (),
  ambient_boundary: MocAmbientPressureBoundaryResult | None = None,
  maximum_geometry_residual_m: float | None = None,
  maximum_absolute_invariant_residual: float | None = None,
  pressure_ratios: Sequence[float] = (),
  shared_terminal_seam_verified: bool = False,
  physical_boundary_conditions_verified: bool = False,
  message: str,
) -> MocFirstCellCompositeResult:
  return MocFirstCellCompositeResult(
    status=status,
    shock_fit=shock_fit,
    strip=strip,
    patch=patch,
    nodes=tuple(nodes),
    cells=tuple(cells),
    topology=_empty_topology() if topology is None else topology,
    shock_boundary_points_m=tuple(shock_points),
    ambient_boundary_points_m=tuple(ambient_points),
    centerline_boundary_points_m=tuple(centerline_points),
    continuation_boundary_points_m=tuple(continuation_points),
    continuation_boundary_states=tuple(continuation_states),
    continuation_boundary_total_pressure_Pa=tuple(
      float(value) for value in continuation_pressures
    ),
    ambient_boundary=ambient_boundary,
    maximum_geometry_residual_m=maximum_geometry_residual_m,
    maximum_absolute_invariant_residual=maximum_absolute_invariant_residual,
    minimum_post_shock_total_pressure_ratio=min(pressure_ratios, default=None),
    maximum_post_shock_total_pressure_ratio=max(pressure_ratios, default=None),
    shared_terminal_seam_verified=shared_terminal_seam_verified,
    physical_boundary_conditions_verified=physical_boundary_conditions_verified,
    message=message,
  )


def _point_key(
  point: tuple[float, float],
  position_tolerance_m: float,
) -> tuple[int, int]:
  return round(point[0] / position_tolerance_m), round(point[1] / position_tolerance_m)


def _edge_key(
  first: tuple[float, float],
  second: tuple[float, float],
  position_tolerance_m: float,
) -> tuple[tuple[int, int], tuple[int, int]]:
  first_key = _point_key(first, position_tolerance_m)
  second_key = _point_key(second, position_tolerance_m)
  return (first_key, second_key) if first_key <= second_key else (second_key, first_key)


def _edge_counts(
  cells: Sequence[MocCharacteristicCell],
  position_tolerance_m: float,
) -> dict[tuple[tuple[int, int], tuple[int, int]], int]:
  counts: dict[tuple[tuple[int, int], tuple[int, int]], int] = {}
  for cell in cells:
    vertices = tuple(cell.vertices_xr_m)
    for first, second in zip(vertices, (*vertices[1:], vertices[0])):
      edge = _edge_key(first, second, position_tolerance_m)
      counts[edge] = counts.get(edge, 0) + 1
  return counts


def _path_edges_present(
  points: Sequence[tuple[float, float]],
  edge_counts: dict[tuple[tuple[int, int], tuple[int, int]], int],
  position_tolerance_m: float,
) -> bool:
  return all(
    edge_counts.get(_edge_key(first, second, position_tolerance_m), 0) == 1
    for first, second in zip(points, points[1:])
  )


def _same_point(
  first: tuple[float, float],
  second: tuple[float, float],
  position_tolerance_m: float,
) -> bool:
  return (
    abs(first[0] - second[0]) <= position_tolerance_m
    and abs(first[1] - second[1]) <= position_tolerance_m
  )


def _unique_nodes(
  nodes: Sequence[MocCharacteristicNode],
  position_tolerance_m: float,
) -> tuple[MocCharacteristicNode, ...]:
  by_point: dict[tuple[int, int], MocCharacteristicNode] = {}
  for node in nodes:
    by_point.setdefault(_point_key(node.point_m, position_tolerance_m), node)
  return tuple(by_point.values())


def assemble_first_cell_composite(
  shock_fit: MocShockBoundaryFitResult,
  strip: MocAmbientShockStripResult,
  patch: MocTerminalReflectionPatchResult,
  *,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
) -> MocFirstCellCompositeResult:
  """Join a shock/ambient strip and reflection patch into one cell topology.

  The shared terminal trace is cancelled only when its points and typed
  state/pressure samples are identical in both objects.  The returned union
  retains the outgoing patch trace as a downstream chain interface; it does
  not infer a shock, ambient, or subsonic boundary that was not supplied.
  """

  if not isinstance(shock_fit, MocShockBoundaryFitResult):
    return _failure(
      MocFirstCellCompositeStatus.INVALID_INPUT,
      message='shock_fit must be a MocShockBoundaryFitResult',
    )
  if not isinstance(strip, MocAmbientShockStripResult):
    return _failure(
      MocFirstCellCompositeStatus.INVALID_INPUT,
      shock_fit=shock_fit,
      message='strip must be a MocAmbientShockStripResult',
    )
  if not isinstance(patch, MocTerminalReflectionPatchResult):
    return _failure(
      MocFirstCellCompositeStatus.INVALID_INPUT,
      shock_fit=shock_fit,
      strip=strip,
      message='patch must be a MocTerminalReflectionPatchResult',
    )
  for name, value in (
    ('position_tolerance_m', position_tolerance_m),
    ('invariant_tolerance', invariant_tolerance),
  ):
    if not isfinite(float(value)) or value <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
  shock_points = tuple(sample.point_m for sample in shock_fit.boundary_states)
  ambient_points = tuple(strip.ambient_boundary_points_m)
  if not shock_fit.converged:
    return _failure(
      MocFirstCellCompositeStatus.SHOCK_FAILURE,
      shock_fit=shock_fit,
      strip=strip,
      patch=patch,
      shock_points=shock_points,
      ambient_points=ambient_points,
      message=f'shock fit is not converged: {shock_fit.message}',
    )
  if (
    strip.status is not MocAmbientShockStripStatus.CONVERGED_OPEN
    or not strip.converged
  ):
    return _failure(
      MocFirstCellCompositeStatus.STRIP_FAILURE,
      shock_fit=shock_fit,
      strip=strip,
      patch=patch,
      shock_points=shock_points,
      ambient_points=ambient_points,
      ambient_boundary=strip.ambient_boundary,
      message=f'shock/ambient strip is not converged: {strip.message}',
    )
  if (
    patch.status is not MocTerminalReflectionPatchStatus.CONVERGED_OPEN
    or not patch.converged
  ):
    return _failure(
      MocFirstCellCompositeStatus.PATCH_FAILURE,
      shock_fit=shock_fit,
      strip=strip,
      patch=patch,
      shock_points=shock_points,
      ambient_points=ambient_points,
      ambient_boundary=strip.ambient_boundary,
      message=f'terminal reflection patch is not converged: {patch.message}',
    )
  if len(shock_points) < 3 or len(shock_points) != len(strip.shock_boundary_points_m):
    return _failure(
      MocFirstCellCompositeStatus.INVALID_INPUT,
      shock_fit=shock_fit,
      strip=strip,
      patch=patch,
      shock_points=shock_points,
      ambient_points=ambient_points,
      ambient_boundary=strip.ambient_boundary,
      message='shock fit and strip must expose the same three-or-more shock points',
    )
  if any(
    not _same_point(first, second, position_tolerance_m)
    for first, second in zip(shock_points, strip.shock_boundary_points_m, strict=True)
  ):
    return _failure(
      MocFirstCellCompositeStatus.SEAM_FAILURE,
      shock_fit=shock_fit,
      strip=strip,
      patch=patch,
      shock_points=shock_points,
      ambient_points=ambient_points,
      ambient_boundary=strip.ambient_boundary,
      message='shock fit and strip shock boundary points do not agree',
    )
  if patch.input_trace_validation is None:
    return _failure(
      MocFirstCellCompositeStatus.SEAM_FAILURE,
      shock_fit=shock_fit,
      strip=strip,
      patch=patch,
      shock_points=shock_points,
      ambient_points=ambient_points,
      ambient_boundary=strip.ambient_boundary,
      message='terminal reflection patch has no input trace validation',
    )
  strip_trace = strip.terminal_trace_samples
  patch_trace = patch.input_trace_validation.samples
  if patch_trace != strip_trace:
    return _failure(
      MocFirstCellCompositeStatus.SEAM_FAILURE,
      shock_fit=shock_fit,
      strip=strip,
      patch=patch,
      shock_points=shock_points,
      ambient_points=ambient_points,
      ambient_boundary=strip.ambient_boundary,
      message='strip terminal C+ trace and patch input trace are not identical',
    )
  if len(patch.outgoing_trace_points_m) < 3:
    return _failure(
      MocFirstCellCompositeStatus.INVALID_INPUT,
      shock_fit=shock_fit,
      strip=strip,
      patch=patch,
      shock_points=shock_points,
      ambient_points=ambient_points,
      ambient_boundary=strip.ambient_boundary,
      message='terminal reflection patch requires at least three outgoing samples',
    )
  cells = tuple((*strip.cells, *patch.cells))
  topology = validate_moc_mesh(cells)
  if not topology.connected or not topology.forms_closed_zone or topology.nonmanifold_edge_count:
    return _failure(
      MocFirstCellCompositeStatus.TOPOLOGY_FAILURE,
      shock_fit=shock_fit,
      strip=strip,
      patch=patch,
      nodes=_unique_nodes((*strip.nodes, *patch.nodes), position_tolerance_m),
      cells=cells,
      topology=topology,
      shock_points=shock_points,
      ambient_points=ambient_points,
      ambient_boundary=strip.ambient_boundary,
      message=f'first-cell strip/patch union topology failed: {topology.message}',
    )
  centerline_points = tuple(patch.axis_points_m)
  continuation_points = tuple(patch.outgoing_trace_points_m)
  edge_counts = _edge_counts(cells, position_tolerance_m)
  if not (
    _path_edges_present(shock_points, edge_counts, position_tolerance_m)
    and _path_edges_present(ambient_points, edge_counts, position_tolerance_m)
    and _path_edges_present(centerline_points, edge_counts, position_tolerance_m)
    and _path_edges_present(continuation_points, edge_counts, position_tolerance_m)
  ):
    return _failure(
      MocFirstCellCompositeStatus.BOUNDARY_FAILURE,
      shock_fit=shock_fit,
      strip=strip,
      patch=patch,
      nodes=_unique_nodes((*strip.nodes, *patch.nodes), position_tolerance_m),
      cells=cells,
      topology=topology,
      shock_points=shock_points,
      ambient_points=ambient_points,
      centerline_points=centerline_points,
      continuation_points=continuation_points,
      continuation_states=patch.outgoing_trace_states,
      continuation_pressures=patch.outgoing_trace_total_pressure_Pa,
      ambient_boundary=strip.ambient_boundary,
      message='first-cell union is missing an explicit physical or continuation boundary path',
    )
  if not (
    shock_points
    and ambient_points
    and centerline_points
    and continuation_points
    and _same_point(shock_points[0], ambient_points[0], position_tolerance_m)
    and _same_point(shock_points[-1], centerline_points[0], position_tolerance_m)
    and _same_point(ambient_points[-1], continuation_points[0], position_tolerance_m)
    and _same_point(centerline_points[-1], continuation_points[-1], position_tolerance_m)
  ):
    return _failure(
      MocFirstCellCompositeStatus.SEAM_FAILURE,
      shock_fit=shock_fit,
      strip=strip,
      patch=patch,
      nodes=_unique_nodes((*strip.nodes, *patch.nodes), position_tolerance_m),
      cells=cells,
      topology=topology,
      shock_points=shock_points,
      ambient_points=ambient_points,
      centerline_points=centerline_points,
      continuation_points=continuation_points,
      continuation_states=patch.outgoing_trace_states,
      continuation_pressures=patch.outgoing_trace_total_pressure_Pa,
      ambient_boundary=strip.ambient_boundary,
      message='first-cell boundary paths do not meet at the shared strip/patch corners',
    )
  if any(
    abs(point[1]) > position_tolerance_m or abs(state.theta_rad) > invariant_tolerance
    for point, state in zip(patch.axis_points_m, patch.axis_states, strict=True)
  ):
    return _failure(
      MocFirstCellCompositeStatus.BOUNDARY_FAILURE,
      shock_fit=shock_fit,
      strip=strip,
      patch=patch,
      nodes=_unique_nodes((*strip.nodes, *patch.nodes), position_tolerance_m),
      cells=cells,
      topology=topology,
      shock_points=shock_points,
      ambient_points=ambient_points,
      centerline_points=centerline_points,
      continuation_points=continuation_points,
      continuation_states=patch.outgoing_trace_states,
      continuation_pressures=patch.outgoing_trace_total_pressure_Pa,
      ambient_boundary=strip.ambient_boundary,
      message='first-cell centerline boundary does not satisfy y=0 and theta=0',
    )
  pressure_ratios = tuple(
    sample.downstream_total_pressure_Pa / sample.upstream_total_pressure_Pa
    for sample in shock_fit.boundary_states
  )
  if any(ratio <= 0.0 or ratio >= 1.0 for ratio in pressure_ratios):
    return _failure(
      MocFirstCellCompositeStatus.SHOCK_FAILURE,
      shock_fit=shock_fit,
      strip=strip,
      patch=patch,
      nodes=_unique_nodes((*strip.nodes, *patch.nodes), position_tolerance_m),
      cells=cells,
      topology=topology,
      shock_points=shock_points,
      ambient_points=ambient_points,
      centerline_points=centerline_points,
      continuation_points=continuation_points,
      continuation_states=patch.outgoing_trace_states,
      continuation_pressures=patch.outgoing_trace_total_pressure_Pa,
      ambient_boundary=strip.ambient_boundary,
      pressure_ratios=pressure_ratios,
      message='first-cell shock boundary must carry strict total-pressure loss',
    )
  nodes = _unique_nodes((*strip.nodes, *patch.nodes), position_tolerance_m)
  maximum_geometry = max(
    (
      abs(node.point_result.geometry_residual)
      for node in nodes
      if node.point_result.geometry_residual is not None
    ),
    default=None,
  )
  maximum_invariant = max(
    (
      abs(value)
      for node in nodes
      for value in (
        node.point_result.invariant_residual_plus,
        node.point_result.invariant_residual_minus,
      )
      if value is not None
    ),
    default=None,
  )
  return MocFirstCellCompositeResult(
    status=MocFirstCellCompositeStatus.CONVERGED_CLOSED_SUPERSONIC_COMPOSITE,
    shock_fit=shock_fit,
    strip=strip,
    patch=patch,
    nodes=nodes,
    cells=cells,
    topology=topology,
    shock_boundary_points_m=shock_points,
    ambient_boundary_points_m=ambient_points,
    centerline_boundary_points_m=centerline_points,
    continuation_boundary_points_m=continuation_points,
    continuation_boundary_states=patch.outgoing_trace_states,
    continuation_boundary_total_pressure_Pa=patch.outgoing_trace_total_pressure_Pa,
    ambient_boundary=strip.ambient_boundary,
    maximum_geometry_residual_m=maximum_geometry,
    maximum_absolute_invariant_residual=maximum_invariant,
    minimum_post_shock_total_pressure_ratio=min(pressure_ratios),
    maximum_post_shock_total_pressure_ratio=max(pressure_ratios),
    shared_terminal_seam_verified=True,
    physical_boundary_conditions_verified=(
      strip.ambient_boundary.converged
      and patch.outgoing_trace_validation is not None
      and patch.outgoing_trace_validation.converged
    ),
    message=(
      'shock/ambient strip and centerline-reflection patch form a closed '
      'supersonic first-cell composite; outgoing C- trace remains a '
      'research continuation boundary'
    ),
  )
