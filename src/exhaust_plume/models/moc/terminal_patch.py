"""Centerline-reflected continuation from an open shock/ambient trace.

The correctly oriented shock/ambient strip ends on a shock-sourced ``C+``
trace.  This module consumes that trace as the ``C-`` source boundary of the
next compatible patch, reflects each source characteristic to the centerline,
and assembles the triangular net between the incoming trace and centerline.

The patch is deliberately open at its downstream front.  Its value is the
typed outgoing trace and the combined topology check: a future shock-fitting
solver can consume that front without treating an arbitrary line or a
reduced-order cell as a resolved boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite

from exhaust_plume.models.moc.ambient_shock_strip import (
  MocAmbientShockStripResult,
  MocAmbientShockStripStatus,
)
from exhaust_plume.models.moc.chain import (
  MocChainBoundarySample,
  MocCharacteristicTraceResult,
  validate_characteristic_trace,
)
from exhaust_plume.models.moc.primitives import (
  CharacteristicFamily,
  CharacteristicPointResult,
  CharacteristicState,
  MocPrimitiveStatus,
  centerline_characteristic_point,
  interior_characteristic_point,
  inverse_prandtl_meyer_angle_rad,
)
from exhaust_plume.models.moc.topology import MocTopologyResult, validate_moc_mesh
from exhaust_plume.models.moc.zone import MocCharacteristicCell, MocCharacteristicNode

__all__ = (
  'MocTerminalReflectionPatchStatus',
  'MocTerminalReflectionPatchResult',
  'assemble_terminal_trace_centerline_patch',
)


class MocTerminalReflectionPatchStatus(str, Enum):
  """Outcome of reflecting an open terminal trace to the centerline."""

  CONVERGED_OPEN = 'converged_open_terminal_reflection_patch'
  INVALID_INPUT = 'invalid_input'
  STRIP_FAILURE = 'open_strip_failure'
  AXIS_FAILURE = 'centerline_reflection_failure'
  GEOMETRY_FAILURE = 'geometry_failure'
  INVARIANT_FAILURE = 'invariant_failure'
  TRACE_FAILURE = 'outgoing_trace_failure'
  TOPOLOGY_FAILURE = 'topology_failure'


@dataclass(frozen=True, slots=True)
class MocTerminalReflectionPatchResult:
  """An open compatible patch generated from a terminal ``C+`` trace."""

  status: MocTerminalReflectionPatchStatus
  source_strip_status: MocAmbientShockStripStatus | None
  nodes: tuple[MocCharacteristicNode, ...]
  cells: tuple[MocCharacteristicCell, ...]
  topology: MocTopologyResult
  combined_topology: MocTopologyResult
  input_trace_validation: MocCharacteristicTraceResult | None
  outgoing_trace_validation: MocCharacteristicTraceResult | None
  axis_points_m: tuple[tuple[float, float], ...]
  axis_states: tuple[CharacteristicState, ...]
  axis_total_pressure_Pa: tuple[float, ...]
  outgoing_trace_points_m: tuple[tuple[float, float], ...]
  outgoing_trace_states: tuple[CharacteristicState, ...]
  outgoing_trace_total_pressure_Pa: tuple[float, ...]
  maximum_geometry_residual_m: float | None
  maximum_absolute_invariant_residual: float | None
  minimum_forward_margin_m: float | None
  message: str = ''

  @property
  def converged(self) -> bool:
    return self.status is MocTerminalReflectionPatchStatus.CONVERGED_OPEN

  @property
  def physical_closure_verified(self) -> bool:
    """The outgoing characteristic front still needs a physical boundary."""

    return False

  @property
  def chain_promotion_blocked(self) -> bool:
    """An open transition cannot become a resolved shock-cell by itself."""

    return True

  @property
  def node_count(self) -> int:
    return len(self.nodes)

  @property
  def cell_count(self) -> int:
    return len(self.cells)

  @property
  def outgoing_trace_samples(self) -> tuple[MocChainBoundarySample, ...]:
    return tuple(
      MocChainBoundarySample(state=state, total_pressure_Pa=pressure)
      for state, pressure in zip(
        self.outgoing_trace_states,
        self.outgoing_trace_total_pressure_Pa,
        strict=True,
      )
    )

  def state_at(
    self,
    point_m: tuple[float, float],
    *,
    position_tolerance_m: float = 1.0e-10,
  ) -> CharacteristicState | None:
    """Interpolate a state inside the reflected patch without extrapolation."""

    sample = self._sample_at(point_m, position_tolerance_m=position_tolerance_m)
    return None if sample is None else sample[0]

  def total_pressure_at(
    self,
    point_m: tuple[float, float],
    *,
    position_tolerance_m: float = 1.0e-10,
  ) -> float | None:
    """Return the carried total pressure at a point inside the patch."""

    sample = self._sample_at(point_m, position_tolerance_m=position_tolerance_m)
    return None if sample is None else sample[1]

  def static_pressure_at(
    self,
    point_m: tuple[float, float],
    *,
    position_tolerance_m: float = 1.0e-10,
  ) -> float | None:
    """Return the isentropic static pressure at a sampled patch state."""

    sample = self._sample_at(point_m, position_tolerance_m=position_tolerance_m)
    if sample is None:
      return None
    state, total_pressure = sample
    pressure_ratio = (
      1.0 + 0.5 * (state.gamma - 1.0) * state.mach * state.mach
    ) ** (state.gamma / (state.gamma - 1.0))
    return total_pressure / pressure_ratio

  def _sample_at(
    self,
    point_m: tuple[float, float],
    *,
    position_tolerance_m: float,
  ) -> tuple[CharacteristicState, float] | None:
    if len(point_m) != 2 or not all(isfinite(float(value)) for value in point_m):
      raise ValueError('point_m must contain two finite coordinates')
    if not isfinite(float(position_tolerance_m)) or position_tolerance_m <= 0.0:
      raise ValueError('position_tolerance_m must be finite and positive')
    point = (float(point_m[0]), float(point_m[1]))
    node_by_key = {
      (node.centerline_index, node.boundary_index): node
      for node in self.nodes
    }
    for node in self.nodes:
      if (
        abs(node.point_m[0] - point[0]) <= position_tolerance_m
        and abs(node.point_m[1] - point[1]) <= position_tolerance_m
      ):
        if node.total_pressure_Pa is None:
          return None
        return (
          CharacteristicState(
            x_m=point[0],
            y_m=point[1],
            theta_rad=node.state.theta_rad,
            mach=node.state.mach,
            gamma=node.state.gamma,
          ),
          float(node.total_pressure_Pa),
        )
    for cell in self.cells:
      samples = _terminal_cell_samples(cell, node_by_key)
      if samples is None:
        continue
      vertices, states, pressures = samples
      weights = _polygon_interpolation_weights(
        point,
        vertices,
        tolerance_m=position_tolerance_m,
      )
      if weights is None:
        continue
      theta = sum(
        weight * state.theta_rad
        for weight, state in zip(weights, states, strict=True)
      )
      nu = sum(
        weight * state.nu_rad
        for weight, state in zip(weights, states, strict=True)
      )
      inverse = inverse_prandtl_meyer_angle_rad(nu, states[0].gamma)
      if not inverse.converged or inverse.value is None:
        return None
      return (
        CharacteristicState(
          x_m=point[0],
          y_m=point[1],
          theta_rad=theta,
          mach=inverse.value,
          gamma=states[0].gamma,
        ),
        sum(weight * pressure for weight, pressure in zip(weights, pressures, strict=True)),
      )
    return None

  def as_report(self) -> dict[str, object]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'source_strip_status': (
        None if self.source_strip_status is None else self.source_strip_status.value
      ),
      'node_count': self.node_count,
      'cell_count': self.cell_count,
      'topology_status': self.topology.status.value,
      'topology_connected': self.topology.connected,
      'topology_forms_closed_zone': self.topology.forms_closed_zone,
      'topology_boundary_edge_count': self.topology.boundary_edge_count,
      'topology_nonmanifold_edge_count': self.topology.nonmanifold_edge_count,
      'combined_topology_status': self.combined_topology.status.value,
      'combined_topology_connected': self.combined_topology.connected,
      'combined_topology_forms_closed_zone': self.combined_topology.forms_closed_zone,
      'combined_topology_boundary_edge_count': self.combined_topology.boundary_edge_count,
      'combined_topology_nonmanifold_edge_count': self.combined_topology.nonmanifold_edge_count,
      'input_trace_family': CharacteristicFamily.PLUS.value,
      'input_trace_validation': (
        None
        if self.input_trace_validation is None
        else self.input_trace_validation.as_report()
      ),
      'outgoing_trace_family': CharacteristicFamily.MINUS.value,
      'outgoing_trace_kind': 'terminal-characteristic-trace',
      'outgoing_trace_sample_count': len(self.outgoing_trace_points_m),
      'outgoing_trace_validation': (
        None
        if self.outgoing_trace_validation is None
        else self.outgoing_trace_validation.as_report()
      ),
      'axis_sample_count': len(self.axis_points_m),
      'axis_start_m': self.axis_points_m[0] if self.axis_points_m else None,
      'axis_end_m': self.axis_points_m[-1] if self.axis_points_m else None,
      'maximum_geometry_residual_m': self.maximum_geometry_residual_m,
      'maximum_absolute_invariant_residual': self.maximum_absolute_invariant_residual,
      'minimum_forward_margin_m': self.minimum_forward_margin_m,
      'message': self.message,
    }


def _empty_topology() -> MocTopologyResult:
  return validate_moc_mesh(())


def _failure(
  status: MocTerminalReflectionPatchStatus,
  *,
  source_strip_status: MocAmbientShockStripStatus | None,
  nodes: tuple[MocCharacteristicNode, ...] = (),
  cells: tuple[MocCharacteristicCell, ...] = (),
  topology: MocTopologyResult | None = None,
  combined_topology: MocTopologyResult | None = None,
  input_trace_validation: MocCharacteristicTraceResult | None = None,
  outgoing_trace_validation: MocCharacteristicTraceResult | None = None,
  axis_points: tuple[tuple[float, float], ...] = (),
  axis_states: tuple[CharacteristicState, ...] = (),
  axis_pressures: tuple[float, ...] = (),
  outgoing_points: tuple[tuple[float, float], ...] = (),
  outgoing_states: tuple[CharacteristicState, ...] = (),
  outgoing_pressures: tuple[float, ...] = (),
  maximum_geometry_residual_m: float | None = None,
  maximum_absolute_invariant_residual: float | None = None,
  minimum_forward_margin_m: float | None = None,
  message: str,
) -> MocTerminalReflectionPatchResult:
  return MocTerminalReflectionPatchResult(
    status=status,
    source_strip_status=source_strip_status,
    nodes=nodes,
    cells=cells,
    topology=_empty_topology() if topology is None else topology,
    combined_topology=(
      _empty_topology() if combined_topology is None else combined_topology
    ),
    input_trace_validation=input_trace_validation,
    outgoing_trace_validation=outgoing_trace_validation,
    axis_points_m=axis_points,
    axis_states=axis_states,
    axis_total_pressure_Pa=axis_pressures,
    outgoing_trace_points_m=outgoing_points,
    outgoing_trace_states=outgoing_states,
    outgoing_trace_total_pressure_Pa=outgoing_pressures,
    maximum_geometry_residual_m=maximum_geometry_residual_m,
    maximum_absolute_invariant_residual=maximum_absolute_invariant_residual,
    minimum_forward_margin_m=minimum_forward_margin_m,
    message=message,
  )


def _residual_maxima(
  nodes: tuple[MocCharacteristicNode, ...],
) -> tuple[float | None, float | None]:
  return (
    max(
      (
        abs(node.point_result.geometry_residual)
        for node in nodes
        if node.point_result.geometry_residual is not None
      ),
      default=None,
    ),
    max(
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
    ),
  )


def _terminal_cell_samples(
  cell: MocCharacteristicCell,
  node_by_key: dict[tuple[int, int], MocCharacteristicNode],
) -> tuple[
  tuple[tuple[float, float], ...],
  tuple[CharacteristicState, ...],
  tuple[float, ...],
] | None:
  """Return ordered state and pressure samples for one patch cell."""

  if cell.cell_kind == 'terminal-reflection-interior':
    if len(cell.centerline_indices) != 2 or len(cell.boundary_indices) != 2:
      return None
    first_axis, second_axis = cell.centerline_indices
    first_boundary, second_boundary = cell.boundary_indices
    keys = (
      (first_axis, first_boundary),
      (first_axis, second_boundary),
      (second_axis, second_boundary),
      (second_axis, first_boundary),
    )
  elif cell.cell_kind == 'terminal-reflection-axis-strip':
    if len(cell.centerline_indices) != 2:
      return None
    first_row, second_row = cell.centerline_indices
    keys = (
      (first_row, first_row),
      (first_row, second_row),
      (second_row, second_row),
    )
  else:
    return None
  nodes = tuple(node_by_key.get(key) for key in keys)
  if any(node is None or node.total_pressure_Pa is None for node in nodes):
    return None
  resolved = tuple(node for node in nodes if node is not None)
  return (
    tuple(cell.vertices_xr_m),
    tuple(node.state for node in resolved),
    tuple(float(node.total_pressure_Pa) for node in resolved if node.total_pressure_Pa is not None),
  )


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
  if min(first, second, third) < -1.0e-10 or max(first, second, third) > 1.0 + 1.0e-10:
    return None
  return first, second, third


def _polygon_interpolation_weights(
  point: tuple[float, float],
  vertices: tuple[tuple[float, float], ...],
  *,
  tolerance_m: float,
) -> tuple[float, ...] | None:
  if len(vertices) == 3:
    return _triangle_interpolation_weights(point, vertices, tolerance_m=tolerance_m)
  first = _triangle_interpolation_weights(
    point,
    (vertices[0], vertices[1], vertices[2]),
    tolerance_m=tolerance_m,
  )
  if first is not None:
    return first[0], first[1], first[2], 0.0
  second = _triangle_interpolation_weights(
    point,
    (vertices[0], vertices[2], vertices[3]),
    tolerance_m=tolerance_m,
  )
  if second is not None:
    return second[0], 0.0, second[1], second[2]
  return None


def assemble_terminal_trace_centerline_patch(
  strip: MocAmbientShockStripResult,
  *,
  trace_position_tolerance_m: float | None = None,
  invariant_tolerance: float = 1.0e-10,
) -> MocTerminalReflectionPatchResult:
  """Reflect an open shock/ambient ``C+`` trace into a centerline patch.

  The incoming trace is used as the ``C-`` source boundary for this patch.
  Each source state is first sent to the centerline with a ``C-``
  characteristic, producing the ``C+`` source state on the axis.  Compatible
  intersections are then assembled with the axis source indexed before the
  trace source.  The final row is retained as an outgoing ``C-`` trace.

  The returned mesh is a connected open transition.  Its incoming trace is
  shared with the supplied strip and its outgoing front is a new typed
  boundary; neither a shock nor a physical termination is invented here.
  When the position tolerance is omitted, the trace tolerance recorded by
  the source strip is reused; standard strips retain their strict default,
  while projected physical fields retain their declared mesh tolerance.
  """

  if not isinstance(strip, MocAmbientShockStripResult):
    return _failure(
      MocTerminalReflectionPatchStatus.INVALID_INPUT,
      source_strip_status=None,
      message='strip must be a MocAmbientShockStripResult',
    )
  if trace_position_tolerance_m is None:
    trace_position_tolerance_m = strip.terminal_trace_position_tolerance_m
  for name, value in (
    ('trace_position_tolerance_m', trace_position_tolerance_m),
    ('invariant_tolerance', invariant_tolerance),
  ):
    if not isfinite(float(value)) or value <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
  if (
    strip.status is not MocAmbientShockStripStatus.CONVERGED_OPEN
    or not strip.topology.connected
    or not strip.topology.forms_closed_zone
    or strip.topology.nonmanifold_edge_count
  ):
    return _failure(
      MocTerminalReflectionPatchStatus.STRIP_FAILURE,
      source_strip_status=strip.status,
      message=(
        'terminal reflection requires a converged connected open strip; '
        f'received {strip.status.value}: {strip.topology.message}'
      ),
    )

  input_trace = validate_characteristic_trace(
    strip.terminal_trace_samples,
    CharacteristicFamily.PLUS,
    position_tolerance_m=trace_position_tolerance_m,
    invariant_tolerance=invariant_tolerance,
  )
  if not input_trace.converged:
    return _failure(
      MocTerminalReflectionPatchStatus.TRACE_FAILURE,
      source_strip_status=strip.status,
      input_trace_validation=input_trace,
      message=f'incoming terminal C+ trace failed: {input_trace.message}',
    )
  trace = input_trace.samples
  if len(trace) < 3:
    return _failure(
      MocTerminalReflectionPatchStatus.INVALID_INPUT,
      source_strip_status=strip.status,
      input_trace_validation=input_trace,
      message='terminal reflection requires at least three trace samples',
    )

  axis_results: list[CharacteristicPointResult] = []
  axis_states: list[CharacteristicState] = []
  axis_points: list[tuple[float, float]] = []
  axis_pressures: list[float] = []
  for index, sample in enumerate(trace):
    result = centerline_characteristic_point(
      sample.state,
      CharacteristicFamily.MINUS,
      position_tolerance_m=trace_position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
    )
    if not result.converged or result.state is None or result.point_m is None:
      status = (
        MocTerminalReflectionPatchStatus.INVARIANT_FAILURE
        if result.status is MocPrimitiveStatus.INVARIANT_FAILURE
        else MocTerminalReflectionPatchStatus.AXIS_FAILURE
      )
      return _failure(
        status,
        source_strip_status=strip.status,
        input_trace_validation=input_trace,
        axis_points=tuple(axis_points),
        axis_states=tuple(axis_states),
        axis_pressures=tuple(axis_pressures),
        message=f'terminal trace sample {index} did not reach the centerline: {result.message}',
      )
    if abs(result.point_m[1]) > trace_position_tolerance_m or abs(result.state.theta_rad) > invariant_tolerance:
      return _failure(
        MocTerminalReflectionPatchStatus.AXIS_FAILURE,
        source_strip_status=strip.status,
        input_trace_validation=input_trace,
        axis_points=tuple(axis_points),
        axis_states=tuple(axis_states),
        axis_pressures=tuple(axis_pressures),
        message=f'centerline reflection sample {index} does not satisfy y=0 and theta=0',
      )
    if axis_points and result.point_m[0] <= axis_points[-1][0] + trace_position_tolerance_m:
      return _failure(
        MocTerminalReflectionPatchStatus.GEOMETRY_FAILURE,
        source_strip_status=strip.status,
        input_trace_validation=input_trace,
        axis_points=tuple(axis_points),
        axis_states=tuple(axis_states),
        axis_pressures=tuple(axis_pressures),
        message=f'centerline reflection sample {index} is not strictly downstream',
      )
    axis_results.append(result)
    axis_states.append(result.state)
    axis_points.append(result.point_m)
    axis_pressures.append(sample.total_pressure_Pa)

  node_by_index: dict[tuple[int, int], MocCharacteristicNode] = {}
  for trace_index, trace_sample in enumerate(trace):
    for axis_index in range(trace_index + 1):
      if trace_index == axis_index:
        point_result = axis_results[trace_index]
        point = axis_points[trace_index]
        state = axis_states[trace_index]
      else:
        point_result = interior_characteristic_point(
          axis_states[axis_index],
          trace_sample.state,
          position_tolerance_m=trace_position_tolerance_m,
          invariant_tolerance=invariant_tolerance,
        )
        if not point_result.converged or point_result.state is None or point_result.point_m is None:
          status = (
            MocTerminalReflectionPatchStatus.INVARIANT_FAILURE
            if point_result.status is MocPrimitiveStatus.INVARIANT_FAILURE
            else MocTerminalReflectionPatchStatus.GEOMETRY_FAILURE
          )
          nodes = tuple(node_by_index.values())
          maximum_geometry, maximum_invariant = _residual_maxima(nodes)
          return _failure(
            status,
            source_strip_status=strip.status,
            nodes=nodes,
            input_trace_validation=input_trace,
            axis_points=tuple(axis_points),
            axis_states=tuple(axis_states),
            axis_pressures=tuple(axis_pressures),
            maximum_geometry_residual_m=maximum_geometry,
            maximum_absolute_invariant_residual=maximum_invariant,
            message=(
              f'terminal reflection node ({trace_index}, {axis_index}) failed: '
              f'{point_result.message}'
            ),
          )
        if axis_index == 0:
          point = trace_sample.point_m
          state = trace_sample.state
        else:
          point = point_result.point_m
          state = point_result.state
      node_by_index[(trace_index, axis_index)] = MocCharacteristicNode(
        centerline_index=axis_index,
        boundary_index=trace_index,
        point_m=(float(point[0]), float(point[1])),
        state=state,
        point_result=point_result,
        total_pressure_Pa=trace_sample.total_pressure_Pa,
      )

  def node_point(trace_index: int, axis_index: int) -> tuple[float, float]:
    return node_by_index[(trace_index, axis_index)].point_m

  cells_list: list[MocCharacteristicCell] = []
  try:
    for row in range(len(trace) - 1):
      for column in range(row):
        cells_list.append(
          MocCharacteristicCell(
            cell_index=len(cells_list),
            cell_kind='terminal-reflection-interior',
            vertices_xr_m=(
              node_point(row, column),
              node_point(row + 1, column),
              node_point(row + 1, column + 1),
              node_point(row, column + 1),
            ),
            centerline_indices=(column, column + 1),
            boundary_indices=(row, row + 1),
          )
        )
      cells_list.append(
        MocCharacteristicCell(
          cell_index=len(cells_list),
          cell_kind='terminal-reflection-axis-strip',
          vertices_xr_m=(
            node_point(row, row),
            node_point(row + 1, row),
            node_point(row + 1, row + 1),
          ),
          centerline_indices=(row, row + 1),
          boundary_indices=(row + 1,),
        )
      )
  except ValueError as error:
    nodes = tuple(node_by_index.values())
    maximum_geometry, maximum_invariant = _residual_maxima(nodes)
    return _failure(
      MocTerminalReflectionPatchStatus.GEOMETRY_FAILURE,
      source_strip_status=strip.status,
      nodes=nodes,
      cells=tuple(cells_list),
      input_trace_validation=input_trace,
      axis_points=tuple(axis_points),
      axis_states=tuple(axis_states),
      axis_pressures=tuple(axis_pressures),
      maximum_geometry_residual_m=maximum_geometry,
      maximum_absolute_invariant_residual=maximum_invariant,
      message=f'terminal reflection cell geometry failed: {error}',
    )

  nodes = tuple(node_by_index.values())
  cells = tuple(cells_list)
  topology = validate_moc_mesh(cells)
  combined_topology = validate_moc_mesh((*strip.cells, *cells))
  if (
    not topology.connected
    or not topology.forms_closed_zone
    or topology.nonmanifold_edge_count
    or not combined_topology.connected
    or not combined_topology.forms_closed_zone
    or combined_topology.nonmanifold_edge_count
  ):
    maximum_geometry, maximum_invariant = _residual_maxima(nodes)
    return _failure(
      MocTerminalReflectionPatchStatus.TOPOLOGY_FAILURE,
      source_strip_status=strip.status,
      nodes=nodes,
      cells=cells,
      topology=topology,
      combined_topology=combined_topology,
      input_trace_validation=input_trace,
      axis_points=tuple(axis_points),
      axis_states=tuple(axis_states),
      axis_pressures=tuple(axis_pressures),
      maximum_geometry_residual_m=maximum_geometry,
      maximum_absolute_invariant_residual=maximum_invariant,
      message=(
        'terminal reflection topology failed: '
        f'patch={topology.message}; combined={combined_topology.message}'
      ),
    )

  outgoing_nodes = tuple(
    node_by_index[(len(trace) - 1, axis_index)]
    for axis_index in range(len(trace))
  )
  outgoing_points = tuple(node.point_m for node in outgoing_nodes)
  outgoing_states = tuple(node.state for node in outgoing_nodes)
  outgoing_pressures = (trace[-1].total_pressure_Pa,) * len(outgoing_nodes)
  outgoing_trace = validate_characteristic_trace(
    tuple(
      MocChainBoundarySample(state=state, total_pressure_Pa=pressure)
      for state, pressure in zip(outgoing_states, outgoing_pressures, strict=True)
    ),
    CharacteristicFamily.MINUS,
    position_tolerance_m=trace_position_tolerance_m,
    invariant_tolerance=invariant_tolerance,
  )
  maximum_geometry, maximum_invariant = _residual_maxima(nodes)
  minimum_forward = min(
    (
      node.point_m[0]
      - max(
        axis_states[node.centerline_index].x_m,
        trace[node.boundary_index].state.x_m,
      )
      for node in nodes
      if node.centerline_index not in (0, node.boundary_index)
    ),
    default=None,
  )
  if not outgoing_trace.converged:
    return _failure(
      MocTerminalReflectionPatchStatus.TRACE_FAILURE,
      source_strip_status=strip.status,
      nodes=nodes,
      cells=cells,
      topology=topology,
      combined_topology=combined_topology,
      input_trace_validation=input_trace,
      outgoing_trace_validation=outgoing_trace,
      axis_points=tuple(axis_points),
      axis_states=tuple(axis_states),
      axis_pressures=tuple(axis_pressures),
      outgoing_points=outgoing_points,
      outgoing_states=outgoing_states,
      outgoing_pressures=outgoing_pressures,
      maximum_geometry_residual_m=maximum_geometry,
      maximum_absolute_invariant_residual=maximum_invariant,
      minimum_forward_margin_m=minimum_forward,
      message=f'outgoing reflected C- trace failed: {outgoing_trace.message}',
    )
  return MocTerminalReflectionPatchResult(
    status=MocTerminalReflectionPatchStatus.CONVERGED_OPEN,
    source_strip_status=strip.status,
    nodes=nodes,
    cells=cells,
    topology=topology,
    combined_topology=combined_topology,
    input_trace_validation=input_trace,
    outgoing_trace_validation=outgoing_trace,
    axis_points_m=tuple(axis_points),
    axis_states=tuple(axis_states),
    axis_total_pressure_Pa=tuple(axis_pressures),
    outgoing_trace_points_m=outgoing_points,
    outgoing_trace_states=outgoing_states,
    outgoing_trace_total_pressure_Pa=outgoing_pressures,
    maximum_geometry_residual_m=maximum_geometry,
    maximum_absolute_invariant_residual=maximum_invariant,
    minimum_forward_margin_m=minimum_forward,
    message=(
      'terminal shock-sourced C+ trace reflected to a centerline-compatible '
      'patch; outgoing C- characteristic front remains open for the next '
      'shock/boundary solve'
    ),
  )
