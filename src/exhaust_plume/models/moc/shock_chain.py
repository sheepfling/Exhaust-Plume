"""Staged shock-cell transitions for the isolated planar-MOC lane.

This module composes the research primitives that form one physical
shock-cell transition: ambient-matched shock attachment, the physical
shock/ambient characteristic strip, centerline reflection, and a
domain-bounded next-shock probe.  It intentionally does not manufacture a
closed cell.  A transition can expose a typed next-shock handoff or a
verified normal-shock chain stop, while unresolved downstream closure remains
outside the resolved-cell provider contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Callable, Sequence

from exhaust_plume.models.moc.ambient_shock_strip import MocAmbientShockStripResult
from exhaust_plume.models.moc.chain import (
  MocChainBoundarySample,
  MocChainTerminationDecision,
)
from exhaust_plume.models.moc.compression import MocNormalShockTerminalResult
from exhaust_plume.models.moc.coupled import (
  MocAmbientAttachmentResult,
  MocAmbientAttachmentStatus,
  solve_marched_attached_shock_with_ambient_attachment_closure,
)
from exhaust_plume.models.moc.primitives import CharacteristicState
from exhaust_plume.models.moc.terminal_patch import (
  MocTerminalReflectionPatchResult,
  assemble_terminal_trace_centerline_patch,
)
from exhaust_plume.models.moc.terminal_patch_solver import (
  MocTerminalReflectionPatchShockSolveResult,
  solve_marched_attached_shock_from_terminal_reflection_patch,
)
from exhaust_plume.models.moc.topology import MocTopologyResult, validate_moc_mesh
from exhaust_plume.models.moc.zone import MocCharacteristicCell
from exhaust_plume.util.aero.shock_validity import ShockBranch

__all__ = (
  'MocTerminalShockCellFieldStatus',
  'MocTerminalShockCellFieldResult',
  'assemble_terminal_shock_cell_field',
  'MocShockCellTransitionStatus',
  'MocShockCellTransitionResult',
  'solve_marched_ambient_attachment_shock_cell_transition',
)


class MocTerminalShockCellFieldStatus(str, Enum):
  """Outcome for clipping a valid reflected field to a terminal shock."""

  CONVERGED_CLOSED_SUPERSONIC_REGION = 'converged_closed_supersonic_terminal_region'
  INVALID_INPUT = 'invalid_input'
  STRIP_FAILURE = 'strip_failure'
  PATCH_FAILURE = 'reflection_patch_failure'
  SHOCK_FAILURE = 'terminal_shock_failure'
  GEOMETRY_FAILURE = 'terminal_shock_geometry_failure'
  TOPOLOGY_FAILURE = 'terminal_shock_topology_failure'
####


@dataclass(frozen=True, slots=True)
class MocTerminalShockCellFieldResult:
  """A closed supersonic region cut out by a verified terminal shock.

  The field is assembled from already validated shock/ambient-strip and
  centerline-reflection cells, then clipped by the solver-generated upstream
  side of the terminal shock.  This closes the first-cell *supersonic
  topology* without fabricating subsonic characteristic states.  The
  downstream normal-shock region therefore remains a separate mixed-regime
  gate and the result cannot become a resolved supersonic chain cell.
  """

  status: MocTerminalShockCellFieldStatus
  cells: tuple[MocCharacteristicCell, ...]
  topology: MocTopologyResult
  initial_shock_boundary_points_m: tuple[tuple[float, float], ...]
  ambient_boundary_points_m: tuple[tuple[float, float], ...]
  centerline_boundary_points_m: tuple[tuple[float, float], ...]
  terminal_shock_boundary_points_m: tuple[tuple[float, float], ...]
  terminal_shock_upstream_states: tuple[CharacteristicState, ...]
  terminal_shock_upstream_pressure_Pa: tuple[float, ...]
  terminal_normal_shock: MocNormalShockTerminalResult | None
  source_strip_cell_count: int
  source_patch_cell_count: int
  clipped_patch_cell_count: int
  message: str = ''

  @property
  def converged(self) -> bool:
    return self.status is MocTerminalShockCellFieldStatus.CONVERGED_CLOSED_SUPERSONIC_REGION
  ####

  @property
  def supersonic_region_closed(self) -> bool:
    return self.converged and self.topology.forms_closed_zone
  ####

  @property
  def characteristic_field_evidence_verified(self) -> bool:
    """Whether the closed region inherits only validated characteristic cells."""

    return self.supersonic_region_closed and bool(self.cells)
  ####

  @property
  def mixed_regime_field_complete(self) -> bool:
    """The subsonic side of the terminal normal shock is not represented."""

    return False
  ####

  @property
  def physical_closure_verified(self) -> bool:
    """Full physical closure waits for the mixed-regime downstream field."""

    return False
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    return True
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'supersonic_region_closed': self.supersonic_region_closed,
      'characteristic_field_evidence_verified': self.characteristic_field_evidence_verified,
      'mixed_regime_field_complete': self.mixed_regime_field_complete,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'node_count': None,
      'cell_count': len(self.cells),
      'topology_status': self.topology.status.value,
      'topology_connected': self.topology.connected,
      'topology_forms_closed_zone': self.topology.forms_closed_zone,
      'topology_boundary_edge_count': self.topology.boundary_edge_count,
      'topology_boundary_component_count': self.topology.boundary_component_count,
      'topology_nonmanifold_edge_count': self.topology.nonmanifold_edge_count,
      'initial_shock_boundary_sample_count': len(self.initial_shock_boundary_points_m),
      'ambient_boundary_sample_count': len(self.ambient_boundary_points_m),
      'centerline_boundary_sample_count': len(self.centerline_boundary_points_m),
      'terminal_shock_boundary_sample_count': len(self.terminal_shock_boundary_points_m),
      'terminal_shock_upstream_sample_count': len(self.terminal_shock_upstream_states),
      'source_strip_cell_count': self.source_strip_cell_count,
      'source_patch_cell_count': self.source_patch_cell_count,
      'clipped_patch_cell_count': self.clipped_patch_cell_count,
      'terminal_normal_shock': (
        None
        if self.terminal_normal_shock is None
        else self.terminal_normal_shock.as_report()
      ),
      'message': self.message,
    }
####


def _empty_terminal_topology() -> MocTopologyResult:
  return validate_moc_mesh(())
####


def _terminal_field_failure(
  status: MocTerminalShockCellFieldStatus,
  *,
  cells: Sequence[MocCharacteristicCell] = (),
  topology: MocTopologyResult | None = None,
  initial_shock_points: Sequence[tuple[float, float]] = (),
  ambient_points: Sequence[tuple[float, float]] = (),
  centerline_points: Sequence[tuple[float, float]] = (),
  terminal_shock_points: Sequence[tuple[float, float]] = (),
  upstream_states: Sequence[CharacteristicState] = (),
  upstream_pressures: Sequence[float] = (),
  terminal_normal_shock: MocNormalShockTerminalResult | None = None,
  source_strip_cell_count: int = 0,
  source_patch_cell_count: int = 0,
  clipped_patch_cell_count: int = 0,
  message: str,
) -> MocTerminalShockCellFieldResult:
  return MocTerminalShockCellFieldResult(
    status=status,
    cells=tuple(cells),
    topology=_empty_terminal_topology() if topology is None else topology,
    initial_shock_boundary_points_m=tuple(initial_shock_points),
    ambient_boundary_points_m=tuple(ambient_points),
    centerline_boundary_points_m=tuple(centerline_points),
    terminal_shock_boundary_points_m=tuple(terminal_shock_points),
    terminal_shock_upstream_states=tuple(upstream_states),
    terminal_shock_upstream_pressure_Pa=tuple(float(value) for value in upstream_pressures),
    terminal_normal_shock=terminal_normal_shock,
    source_strip_cell_count=source_strip_cell_count,
    source_patch_cell_count=source_patch_cell_count,
    clipped_patch_cell_count=clipped_patch_cell_count,
    message=message,
  )
####


def _clean_clipped_polygon(
  points: Sequence[tuple[float, float]],
) -> tuple[tuple[float, float], ...]:
  cleaned: list[tuple[float, float]] = []
  for point in points:
    canonical = (round(float(point[0]), 12), round(float(point[1]), 12))
    if not cleaned or canonical != cleaned[-1]:
      cleaned.append(canonical)
  if len(cleaned) > 1 and cleaned[0] == cleaned[-1]:
    cleaned.pop()
  return tuple(cleaned)
####


def _terminal_shock_x_at_y(
  shock_points: Sequence[tuple[float, float]],
  y_value: float,
  *,
  tolerance_m: float,
) -> float | None:
  if not shock_points:
    return None
  if y_value >= shock_points[0][1] - tolerance_m:
    return shock_points[0][0]
  if y_value <= shock_points[-1][1] + tolerance_m:
    return shock_points[-1][0]
  for first, second in zip(shock_points, shock_points[1:], strict=True):
    lower = min(first[1], second[1])
    upper = max(first[1], second[1])
    if lower - tolerance_m <= y_value <= upper + tolerance_m:
      if abs(second[1] - first[1]) <= tolerance_m:
        return 0.5 * (first[0] + second[0])
      fraction = (y_value - first[1]) / (second[1] - first[1])
      return first[0] + fraction * (second[0] - first[0])
  return None
####


def _terminal_shock_signed_distance(
  point: tuple[float, float],
  shock_points: Sequence[tuple[float, float]],
  *,
  tolerance_m: float,
) -> float:
  shock_x = _terminal_shock_x_at_y(
    shock_points,
    point[1],
    tolerance_m=tolerance_m,
  )
  if shock_x is None:
    raise ValueError('point lies outside the terminal shock ordinate range')
  return point[0] - shock_x
####


def _terminal_shock_boundary_intersection(
  first: tuple[float, float],
  second: tuple[float, float],
  shock_points: Sequence[tuple[float, float]],
  *,
  tolerance_m: float,
) -> tuple[float, float]:
  first_value = _terminal_shock_signed_distance(
    first,
    shock_points,
    tolerance_m=tolerance_m,
  )
  second_value = _terminal_shock_signed_distance(
    second,
    shock_points,
    tolerance_m=tolerance_m,
  )
  if abs(first_value) <= tolerance_m:
    return first
  if abs(second_value) <= tolerance_m:
    return second
  left = 0.0
  right = 1.0
  left_value = first_value
  for _ in range(64):
    midpoint = 0.5 * (left + right)
    point = (
      first[0] + midpoint * (second[0] - first[0]),
      first[1] + midpoint * (second[1] - first[1]),
    )
    midpoint_value = _terminal_shock_signed_distance(
      point,
      shock_points,
      tolerance_m=tolerance_m,
    )
    if abs(midpoint_value) <= tolerance_m:
      return point
    if left_value * midpoint_value <= 0.0:
      right = midpoint
    else:
      left = midpoint
      left_value = midpoint_value
  midpoint = 0.5 * (left + right)
  return (
    first[0] + midpoint * (second[0] - first[0]),
    first[1] + midpoint * (second[1] - first[1]),
  )
####


def _clip_polygon_to_terminal_shock_upstream_side(
  vertices: Sequence[tuple[float, float]],
  shock_points: Sequence[tuple[float, float]],
  *,
  tolerance_m: float,
) -> tuple[tuple[float, float], ...]:
  """Keep the side containing the first shock/ambient strip.

  The terminal shock is monotone in ``y``.  Its piecewise-linear ``x(y)``
  graph lets us clip each already-valid characteristic polygon without
  extrapolating any state.  The result is a sub-polygon of a validated source
  cell; newly exposed vertices are only geometric cut vertices on the shock.
  """

  if not vertices:
    return ()
  output: list[tuple[float, float]] = []
  previous = vertices[-1]
  previous_value = _terminal_shock_signed_distance(
    previous,
    shock_points,
    tolerance_m=tolerance_m,
  )
  previous_inside = previous_value <= tolerance_m
  for current in vertices:
    current_value = _terminal_shock_signed_distance(
      current,
      shock_points,
      tolerance_m=tolerance_m,
    )
    current_inside = current_value <= tolerance_m
    if current_inside:
      if not previous_inside:
        output.append(
          _terminal_shock_boundary_intersection(
            previous,
            current,
            shock_points,
            tolerance_m=tolerance_m,
          )
        )
      output.append(current)
    elif previous_inside:
      output.append(
        _terminal_shock_boundary_intersection(
          previous,
          current,
          shock_points,
          tolerance_m=tolerance_m,
        )
      )
    previous = current
    previous_value = current_value
    previous_inside = current_inside
  return _clean_clipped_polygon(output)
####


def _polygon_signed_area(
  vertices: Sequence[tuple[float, float]],
) -> float:
  return 0.5 * sum(
    first[0] * second[1] - second[0] * first[1]
    for first, second in zip(vertices, (*vertices[1:], vertices[0]))
  )
####


def _triangulate_clipped_polygon(
  vertices: tuple[tuple[float, float], ...],
) -> tuple[tuple[tuple[float, float], ...], ...]:
  if len(vertices) <= 4:
    return (vertices,)
  return tuple(
    (vertices[0], vertices[index], vertices[index + 1])
    for index in range(1, len(vertices) - 1)
  )
####


def assemble_terminal_shock_cell_field(
  strip: MocAmbientShockStripResult,
  reflection_patch: MocTerminalReflectionPatchResult,
  downstream_shock: MocTerminalReflectionPatchShockSolveResult,
  *,
  target_centerline_y_m: float = 0.0,
  position_tolerance_m: float = 1.0e-9,
  mesh_vertex_tolerance_m: float = 1.0e-9,
) -> MocTerminalShockCellFieldResult:
  """Close the composite supersonic topology at a normal-shock terminal.

  The strip and reflected patch are already validated characteristic meshes.
  This routine removes the patch portion on the downstream side of the
  generated terminal shock and validates the union with the physical strip.
  It does not invent a subsonic ``CharacteristicState`` after the normal
  shock, so the returned topology is a terminal supersonic region rather than
  a promotion-ready mixed-regime cell.
  """

  if not isinstance(strip, MocAmbientShockStripResult):
    return _terminal_field_failure(
      MocTerminalShockCellFieldStatus.INVALID_INPUT,
      message='strip must be a MocAmbientShockStripResult',
    )
  if not isinstance(reflection_patch, MocTerminalReflectionPatchResult):
    return _terminal_field_failure(
      MocTerminalShockCellFieldStatus.INVALID_INPUT,
      message='reflection_patch must be a MocTerminalReflectionPatchResult',
    )
  if not isinstance(downstream_shock, MocTerminalReflectionPatchShockSolveResult):
    return _terminal_field_failure(
      MocTerminalShockCellFieldStatus.INVALID_INPUT,
      message='downstream_shock must be a MocTerminalReflectionPatchShockSolveResult',
    )
  for name, value in (
    ('target_centerline_y_m', target_centerline_y_m),
    ('position_tolerance_m', position_tolerance_m),
    ('mesh_vertex_tolerance_m', mesh_vertex_tolerance_m),
  ):
    if not isfinite(float(value)):
      raise ValueError(f'{name} must be finite')
  if position_tolerance_m <= 0.0 or mesh_vertex_tolerance_m <= 0.0:
    raise ValueError('terminal shock tolerances must be positive')
  if not strip.converged:
    return _terminal_field_failure(
      MocTerminalShockCellFieldStatus.STRIP_FAILURE,
      message=f'shock/ambient strip is not converged: {strip.message}',
    )
  if not reflection_patch.converged:
    return _terminal_field_failure(
      MocTerminalShockCellFieldStatus.PATCH_FAILURE,
      source_strip_cell_count=strip.cell_count,
      message=f'centerline reflection patch is not converged: {reflection_patch.message}',
    )
  if (
    not downstream_shock.physical_terminal_verified
    or downstream_shock.shock.normal_shock_terminal is None
  ):
    return _terminal_field_failure(
      MocTerminalShockCellFieldStatus.SHOCK_FAILURE,
      source_strip_cell_count=strip.cell_count,
      source_patch_cell_count=reflection_patch.cell_count,
      message=(
        'terminal field requires complete upstream coverage and a verified '
        'normal-shock terminal'
      ),
    )

  terminal = downstream_shock.shock.normal_shock_terminal
  shock_samples = tuple(downstream_shock.shock.shock_points_m)
  upstream_states = tuple(downstream_shock.shock.upstream_states)
  upstream_pressures = tuple(downstream_shock.shock.upstream_pressure_Pa)
  if (
    len(shock_samples) < 2
    or len(shock_samples) != len(upstream_states)
    or len(shock_samples) != len(upstream_pressures)
    or not downstream_shock.coupling.converged
    or downstream_shock.coupling.sampled_count != len(shock_samples)
  ):
    return _terminal_field_failure(
      MocTerminalShockCellFieldStatus.SHOCK_FAILURE,
      source_strip_cell_count=strip.cell_count,
      source_patch_cell_count=reflection_patch.cell_count,
      terminal_normal_shock=terminal,
      upstream_states=upstream_states,
      upstream_pressures=upstream_pressures,
      message='terminal shock does not carry a complete domain-bounded upstream path',
    )
  terminal_point = terminal.shock_point_m
  if terminal_point is None or not all(isfinite(float(value)) for value in terminal_point):
    return _terminal_field_failure(
      MocTerminalShockCellFieldStatus.GEOMETRY_FAILURE,
      source_strip_cell_count=strip.cell_count,
      source_patch_cell_count=reflection_patch.cell_count,
      terminal_normal_shock=terminal,
      upstream_states=upstream_states,
      upstream_pressures=upstream_pressures,
      message='normal-shock terminal does not expose a finite shock point',
    )
  terminal_shock_points = (*shock_samples, terminal_point)
  expected_start = reflection_patch.outgoing_trace_points_m[0]
  if (
    abs(shock_samples[0][0] - expected_start[0]) > position_tolerance_m
    or abs(shock_samples[0][1] - expected_start[1]) > position_tolerance_m
  ):
    return _terminal_field_failure(
      MocTerminalShockCellFieldStatus.GEOMETRY_FAILURE,
      source_strip_cell_count=strip.cell_count,
      source_patch_cell_count=reflection_patch.cell_count,
      terminal_shock_points=terminal_shock_points,
      terminal_normal_shock=terminal,
      upstream_states=upstream_states,
      upstream_pressures=upstream_pressures,
      message='terminal shock does not start at the reflected outgoing trace',
    )
  if abs(terminal_point[1] - float(target_centerline_y_m)) > position_tolerance_m:
    return _terminal_field_failure(
      MocTerminalShockCellFieldStatus.GEOMETRY_FAILURE,
      source_strip_cell_count=strip.cell_count,
      source_patch_cell_count=reflection_patch.cell_count,
      terminal_shock_points=terminal_shock_points,
      terminal_normal_shock=terminal,
      upstream_states=upstream_states,
      upstream_pressures=upstream_pressures,
      message='normal-shock terminal does not lie on the requested centerline',
    )
  if any(
    second[0] <= first[0] + position_tolerance_m
    or second[1] > first[1] + position_tolerance_m
    or second[1] < float(target_centerline_y_m) - position_tolerance_m
    for first, second in zip(terminal_shock_points, terminal_shock_points[1:])
  ):
    return _terminal_field_failure(
      MocTerminalShockCellFieldStatus.GEOMETRY_FAILURE,
      source_strip_cell_count=strip.cell_count,
      source_patch_cell_count=reflection_patch.cell_count,
      terminal_shock_points=terminal_shock_points,
      terminal_normal_shock=terminal,
      upstream_states=upstream_states,
      upstream_pressures=upstream_pressures,
      message='terminal shock path is not strictly downstream and centerline-bounded',
    )
  if reflection_patch.axis_points_m and (
    terminal_point[0] < reflection_patch.axis_points_m[0][0] - position_tolerance_m
    or terminal_point[0] > reflection_patch.axis_points_m[-1][0] + position_tolerance_m
  ):
    return _terminal_field_failure(
      MocTerminalShockCellFieldStatus.GEOMETRY_FAILURE,
      source_strip_cell_count=strip.cell_count,
      source_patch_cell_count=reflection_patch.cell_count,
      terminal_shock_points=terminal_shock_points,
      terminal_normal_shock=terminal,
      upstream_states=upstream_states,
      upstream_pressures=upstream_pressures,
      message='normal-shock terminal lies outside the reflected centerline interval',
    )

  input_trace = reflection_patch.input_trace_validation
  if input_trace is None or not input_trace.converged:
    return _terminal_field_failure(
      MocTerminalShockCellFieldStatus.PATCH_FAILURE,
      source_strip_cell_count=strip.cell_count,
      source_patch_cell_count=reflection_patch.cell_count,
      terminal_shock_points=terminal_shock_points,
      terminal_normal_shock=terminal,
      upstream_states=upstream_states,
      upstream_pressures=upstream_pressures,
      message='reflection patch does not expose a converged input trace',
    )
  if len(input_trace.samples) != len(strip.terminal_trace_points_m) or any(
    abs(sample.state.x_m - point[0]) > position_tolerance_m
    or abs(sample.state.y_m - point[1]) > position_tolerance_m
    for sample, point in zip(input_trace.samples, strip.terminal_trace_points_m, strict=True)
  ):
    return _terminal_field_failure(
      MocTerminalShockCellFieldStatus.GEOMETRY_FAILURE,
      source_strip_cell_count=strip.cell_count,
      source_patch_cell_count=reflection_patch.cell_count,
      terminal_shock_points=terminal_shock_points,
      terminal_normal_shock=terminal,
      upstream_states=upstream_states,
      upstream_pressures=upstream_pressures,
      message='reflection patch input trace does not match the strip terminal trace',
    )

  cells: list[MocCharacteristicCell] = []
  try:
    for source in strip.cells:
      cells.append(MocCharacteristicCell(
        cell_index=len(cells),
        cell_kind=f'terminal-composite-strip-{source.cell_kind}',
        vertices_xr_m=tuple(source.vertices_xr_m),
        centerline_indices=source.centerline_indices,
        boundary_indices=source.boundary_indices,
      ))
    clipped_count = 0
    for source in reflection_patch.cells:
      clipped = _clip_polygon_to_terminal_shock_upstream_side(
        source.vertices_xr_m,
        terminal_shock_points,
        tolerance_m=position_tolerance_m,
      )
      if len(clipped) < 3 or abs(_polygon_signed_area(clipped)) <= position_tolerance_m**2:
        continue
      for polygon in _triangulate_clipped_polygon(clipped):
        if len(polygon) not in (3, 4) or abs(_polygon_signed_area(polygon)) <= position_tolerance_m**2:
          continue
        cells.append(MocCharacteristicCell(
          cell_index=len(cells),
          cell_kind=f'terminal-composite-patch-{source.cell_kind}',
          vertices_xr_m=polygon,
          centerline_indices=source.centerline_indices,
          boundary_indices=source.boundary_indices,
        ))
        clipped_count += 1
  except (TypeError, ValueError) as error:
    return _terminal_field_failure(
      MocTerminalShockCellFieldStatus.GEOMETRY_FAILURE,
      cells=cells,
      source_strip_cell_count=strip.cell_count,
      source_patch_cell_count=reflection_patch.cell_count,
      clipped_patch_cell_count=0,
      terminal_shock_points=terminal_shock_points,
      terminal_normal_shock=terminal,
      upstream_states=upstream_states,
      upstream_pressures=upstream_pressures,
      message=f'terminal shock cell clipping produced invalid geometry: {error}',
    )
  if not cells:
    return _terminal_field_failure(
      MocTerminalShockCellFieldStatus.GEOMETRY_FAILURE,
      source_strip_cell_count=strip.cell_count,
      source_patch_cell_count=reflection_patch.cell_count,
      terminal_shock_points=terminal_shock_points,
      terminal_normal_shock=terminal,
      upstream_states=upstream_states,
      upstream_pressures=upstream_pressures,
      message='terminal shock clipping produced no characteristic cells',
    )
  topology = validate_moc_mesh(
    cells,
    vertex_tolerance_m=mesh_vertex_tolerance_m,
  )
  if not topology.connected or not topology.forms_closed_zone or topology.nonmanifold_edge_count:
    return _terminal_field_failure(
      MocTerminalShockCellFieldStatus.TOPOLOGY_FAILURE,
      cells=cells,
      topology=topology,
      source_strip_cell_count=strip.cell_count,
      source_patch_cell_count=reflection_patch.cell_count,
      clipped_patch_cell_count=clipped_count,
      terminal_shock_points=terminal_shock_points,
      terminal_normal_shock=terminal,
      upstream_states=upstream_states,
      upstream_pressures=upstream_pressures,
      message=f'terminal composite topology failed: {topology.message}',
    )
  centerline_points = tuple(
    point for point in reflection_patch.axis_points_m
    if point[0] <= terminal_point[0] + position_tolerance_m
  )
  if not centerline_points or abs(centerline_points[-1][0] - terminal_point[0]) > position_tolerance_m:
    centerline_points = (*centerline_points, terminal_point)
  return MocTerminalShockCellFieldResult(
    status=MocTerminalShockCellFieldStatus.CONVERGED_CLOSED_SUPERSONIC_REGION,
    cells=tuple(cells),
    topology=topology,
    initial_shock_boundary_points_m=strip.shock_boundary_points_m,
    ambient_boundary_points_m=strip.ambient_boundary_points_m,
    centerline_boundary_points_m=centerline_points,
    terminal_shock_boundary_points_m=terminal_shock_points,
    terminal_shock_upstream_states=upstream_states,
    terminal_shock_upstream_pressure_Pa=upstream_pressures,
    terminal_normal_shock=terminal,
    source_strip_cell_count=strip.cell_count,
    source_patch_cell_count=reflection_patch.cell_count,
    clipped_patch_cell_count=clipped_count,
    message=(
      'shock/ambient strip and reflected characteristic patch were clipped '
      'to a closed supersonic region at the verified normal shock; subsonic '
      'downstream field remains outside the planar MOC lane'
    ),
  )
####


class MocShockCellTransitionStatus(str, Enum):
  """Structured outcomes for a staged shock-cell transition."""

  CONVERGED_OPEN_TRANSITION = 'converged_open_shock_cell_transition'
  PHYSICALLY_TERMINATED = 'physically_terminated_at_normal_shock'
  INVALID_INPUT = 'invalid_input'
  ATTACHMENT_FAILURE = 'attachment_failure'
  REFLECTION_FAILURE = 'centerline_reflection_failure'
  DOWNSTREAM_SHOCK_FAILURE = 'downstream_shock_failure'
####


@dataclass(frozen=True, slots=True)
class MocShockCellTransitionResult:
  """A typed open transition between adjacent planar-MOC shock regions.

  ``CONVERGED_OPEN_TRANSITION`` means that the attachment, physical
  shock/ambient strip, centerline reflection, and next-shock coupling all
  passed their local gates.  ``PHYSICALLY_TERMINATED`` means that the same
  transition reached a verified subsonic normal-shock terminal.  Neither
  result is a closed first-cell or a chain-cell promotion result: the
  downstream law used by the next-shock probe is retained as a named
  centerline-normal-shock reference.
  """

  status: MocShockCellTransitionStatus
  attachment: MocAmbientAttachmentResult
  reflection_patch: MocTerminalReflectionPatchResult | None
  downstream_shock: MocTerminalReflectionPatchShockSolveResult | None
  terminal_field: MocTerminalShockCellFieldResult | None
  downstream_condition_status: str
  message: str = ''

  @property
  def converged(self) -> bool:
    return self.status in (
      MocShockCellTransitionStatus.CONVERGED_OPEN_TRANSITION,
      MocShockCellTransitionStatus.PHYSICALLY_TERMINATED,
    )
  ####

  @property
  def physical_termination(self) -> bool:
    return self.status is MocShockCellTransitionStatus.PHYSICALLY_TERMINATED
  ####

  @property
  def physical_closure_verified(self) -> bool:
    """The staged transition never promotes an open field into a cell."""

    return False
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    return True
  ####

  @property
  def next_shock_handoff(self) -> tuple[MocChainBoundarySample, ...]:
    """Return the reflected outgoing trace for a possible next shock."""

    if self.reflection_patch is None:
      return ()
    return self.reflection_patch.outgoing_trace_samples
  ####

  def as_physical_termination_decision(self) -> MocChainTerminationDecision:
    """Return the verified normal-shock stop when this transition has one."""

    if not self.physical_termination or self.downstream_shock is None:
      raise ValueError(
        'a physical shock-cell termination requires a verified downstream '
        'normal-shock terminal'
      )
    return self.downstream_shock.as_physical_termination_decision()
  ####

  def as_report(self) -> dict[str, object]:
    termination = (
      self.as_physical_termination_decision().as_report()
      if self.physical_termination
      else None
    )
    return {
      'status': self.status.value,
      'converged': self.converged,
      'physical_termination': self.physical_termination,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'downstream_condition_status': self.downstream_condition_status,
      'next_shock_handoff_kind': 'terminal-characteristic-trace',
      'next_shock_handoff_sample_count': len(self.next_shock_handoff),
      'termination_decision_available': termination is not None,
      'physical_termination_decision': termination,
      'attachment': self.attachment.as_report(),
      'reflection_patch': (
        None
        if self.reflection_patch is None
        else self.reflection_patch.as_report()
      ),
      'downstream_shock': (
        None
        if self.downstream_shock is None
        else self.downstream_shock.as_report()
      ),
      'terminal_field': (
        None
        if self.terminal_field is None
        else self.terminal_field.as_report()
      ),
      'message': self.message,
    }
####


def _invalid_attachment(message: str) -> MocAmbientAttachmentResult:
  return MocAmbientAttachmentResult(
    status=MocAmbientAttachmentStatus.INVALID_INPUT,
    shock=None,
    ambient_march=None,
    strip=None,
    ambient_pressure_Pa=None,
    outer_downstream_flow_angle_rad=None,
    outer_flow_angle_bracket=None,
    attachment_pressure_residual=None,
    shooting_iterations=0,
    message=message,
  )
####


def solve_marched_ambient_attachment_shock_cell_transition(
  upstream_state_at: Callable[[tuple[float, float]], CharacteristicState | None],
  upstream_pressure_at: Callable[[tuple[float, float]], float | None],
  start_point_m: tuple[float, float],
  ambient_pressure_Pa: float,
  outer_downstream_flow_angle_lower_rad: float,
  outer_downstream_flow_angle_upper_rad: float,
  *,
  target_centerline_y_m: float = 0.0,
  incoming_handoff: Sequence[MocChainBoundarySample] | None = None,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  downstream_flow_angle_rad: float = 0.0,
  trace_position_tolerance_m: float = 2.0e-4,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  attachment_pressure_tolerance: float = 1.0e-8,
  pressure_tolerance: float = 1.0e-8,
  tangent_tolerance: float = 1.0e-8,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
  maximum_boundary_iterations: int = 16,
  maximum_shooting_iterations: int = 40,
) -> MocShockCellTransitionResult:
  """Build one staged shock-cell transition and retain its open boundary.

  The outer shock turn is solved against ambient pressure first.  The
  resulting physical shock/ambient strip is reflected to the centerline, and
  its outgoing ``C-`` trace is passed to the domain-bounded next-shock probe.
  A zero downstream angle is a declared normal-shock reference condition; it
  is not silently treated as a universal downstream closure.
  """

  try:
    downstream_angle = float(downstream_flow_angle_rad)
    trace_tolerance = float(trace_position_tolerance_m)
  except (TypeError, ValueError):
    attachment = _invalid_attachment(
      'downstream flow angle and trace tolerance must be numeric',
    )
    return MocShockCellTransitionResult(
      status=MocShockCellTransitionStatus.INVALID_INPUT,
      attachment=attachment,
      reflection_patch=None,
      downstream_shock=None,
      terminal_field=None,
      downstream_condition_status='centerline-normal-shock-reference',
      message=attachment.message,
    )
  if not isfinite(downstream_angle) or not isfinite(trace_tolerance) or trace_tolerance <= 0.0:
    attachment = _invalid_attachment(
      'downstream flow angle must be finite and trace tolerance must be positive',
    )
    return MocShockCellTransitionResult(
      status=MocShockCellTransitionStatus.INVALID_INPUT,
      attachment=attachment,
      reflection_patch=None,
      downstream_shock=None,
      terminal_field=None,
      downstream_condition_status='centerline-normal-shock-reference',
      message=attachment.message,
    )

  try:
    attachment = solve_marched_attached_shock_with_ambient_attachment_closure(
      upstream_state_at,
      upstream_pressure_at,
      start_point_m,
      ambient_pressure_Pa,
      outer_downstream_flow_angle_lower_rad,
      outer_downstream_flow_angle_upper_rad,
      target_centerline_y_m=target_centerline_y_m,
      incoming_handoff=incoming_handoff,
      sample_count=sample_count,
      branch=branch,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
      attachment_pressure_tolerance=attachment_pressure_tolerance,
      pressure_tolerance=pressure_tolerance,
      tangent_tolerance=tangent_tolerance,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      maximum_segment_iterations=maximum_segment_iterations,
      maximum_boundary_iterations=maximum_boundary_iterations,
      maximum_shooting_iterations=maximum_shooting_iterations,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    attachment = _invalid_attachment(f'ambient attachment raised: {error}')
  if not attachment.converged or attachment.strip is None:
    return MocShockCellTransitionResult(
      status=MocShockCellTransitionStatus.ATTACHMENT_FAILURE,
      attachment=attachment,
      reflection_patch=None,
      downstream_shock=None,
      terminal_field=None,
      downstream_condition_status='centerline-normal-shock-reference',
      message=f'ambient attachment did not converge: {attachment.message}',
    )

  try:
    reflection_patch = assemble_terminal_trace_centerline_patch(
      attachment.strip,
      trace_position_tolerance_m=trace_tolerance,
      invariant_tolerance=invariant_tolerance,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return MocShockCellTransitionResult(
      status=MocShockCellTransitionStatus.REFLECTION_FAILURE,
      attachment=attachment,
      reflection_patch=None,
      downstream_shock=None,
      terminal_field=None,
      downstream_condition_status='centerline-normal-shock-reference',
      message=f'centerline reflection patch raised: {error}',
    )
  if not reflection_patch.converged or not reflection_patch.outgoing_trace_points_m:
    return MocShockCellTransitionResult(
      status=MocShockCellTransitionStatus.REFLECTION_FAILURE,
      attachment=attachment,
      reflection_patch=reflection_patch,
      downstream_shock=None,
      terminal_field=None,
      downstream_condition_status='centerline-normal-shock-reference',
      message=f'centerline reflection patch did not converge: {reflection_patch.message}',
    )

  try:
    downstream_shock = solve_marched_attached_shock_from_terminal_reflection_patch(
      reflection_patch,
      reflection_patch.outgoing_trace_points_m[0],
      target_centerline_y_m=target_centerline_y_m,
      downstream_flow_angle_rad=downstream_angle,
      incoming_handoff=reflection_patch.outgoing_trace_samples,
      sample_count=sample_count,
      position_tolerance_m=trace_tolerance,
      invariant_tolerance=invariant_tolerance,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      maximum_segment_iterations=maximum_segment_iterations,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return MocShockCellTransitionResult(
      status=MocShockCellTransitionStatus.DOWNSTREAM_SHOCK_FAILURE,
      attachment=attachment,
      reflection_patch=reflection_patch,
      downstream_shock=None,
      terminal_field=None,
      downstream_condition_status='centerline-normal-shock-reference',
      message=f'downstream shock probe raised: {error}',
    )

  terminal_field = None
  if downstream_shock.physical_terminal_verified:
    terminal_field = assemble_terminal_shock_cell_field(
      attachment.strip,
      reflection_patch,
      downstream_shock,
      target_centerline_y_m=target_centerline_y_m,
      position_tolerance_m=trace_tolerance,
      mesh_vertex_tolerance_m=max(position_tolerance_m, 1.0e-9),
    )
    if terminal_field.converged:
      status = MocShockCellTransitionStatus.PHYSICALLY_TERMINATED
      message = (
        'ambient attachment, centerline reflection, and next-shock coupling '
        'reached a verified normal-shock terminal and closed the supersonic '
        'composite topology; no mixed-regime cell was promoted'
      )
    else:
      status = MocShockCellTransitionStatus.DOWNSTREAM_SHOCK_FAILURE
      message = f'terminal supersonic topology did not close: {terminal_field.message}'
  elif downstream_shock.converged:
    status = MocShockCellTransitionStatus.CONVERGED_OPEN_TRANSITION
    message = (
      'ambient attachment, centerline reflection, and next-shock coupling '
      'converged as an open transition; downstream cell closure remains pending'
    )
  else:
    status = MocShockCellTransitionStatus.DOWNSTREAM_SHOCK_FAILURE
    message = f'downstream shock probe did not converge: {downstream_shock.message}'
  return MocShockCellTransitionResult(
    status=status,
    attachment=attachment,
    reflection_patch=reflection_patch,
    downstream_shock=downstream_shock,
    terminal_field=terminal_field,
    downstream_condition_status='centerline-normal-shock-reference',
    message=message,
  )
####
