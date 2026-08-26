"""Reusable source-boundary characteristic strips for the planar MOC lane.

The reflected fan is one instance of a triangular source strip: compatible
``C+`` states are supplied on an axis boundary, compatible ``C-`` states are
supplied on an outer boundary, and the diagonal intersections must reproduce
that outer boundary.  This module keeps that numerical construction separate
from the fan/reflected-boundary orchestration so a later continued-cell solver
can reuse the same field contract without importing a reduced-order cell.

The returned strip is an open upstream field.  It is not a shock closure and
does not infer a downstream boundary or physical termination.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Sequence

from exhaust_plume.models.moc.primitives import (
  CharacteristicFamily,
  CharacteristicState,
  interior_characteristic_point,
  inverse_prandtl_meyer_angle_rad,
)
from exhaust_plume.models.moc.boundary import solve_ambient_pressure_free_boundary_point
from exhaust_plume.models.moc.topology import MocTopologyResult, validate_moc_mesh
from exhaust_plume.models.moc.zone import MocCharacteristicCell, MocCharacteristicNode

__all__ = (
  'MocSourceStripStatus',
  'MocSourceStripContinuationStatus',
  'MocSourceCharacteristicStripResult',
  'MocSourceStripContinuationResult',
  'assemble_source_characteristic_strip',
  'extend_source_characteristic_strip_constant_k_plus',
)


class MocSourceStripStatus(str, Enum):
  """Structured outcome for a source-boundary characteristic strip."""

  CONVERGED_OPEN = 'converged_open_source_strip'
  INVALID_INPUT = 'invalid_input'
  GEOMETRY_FAILURE = 'geometry_failure'
  TOPOLOGY_FAILURE = 'topology_failure'
####


class MocSourceStripContinuationStatus(str, Enum):
  """Outcome for a simple-wave source-strip continuation."""

  CONVERGED_EXTENDED = 'converged_constant_k_plus_extension'
  INVALID_INPUT = 'invalid_input'
  BOUNDARY_FAILURE = 'boundary_continuation_failure'
  STRIP_FAILURE = 'strip_assembly_failure'
####


@dataclass(frozen=True, slots=True)
class MocSourceCharacteristicStripResult:
  """A domain-bounded triangular source-boundary MOC field."""

  status: MocSourceStripStatus
  plus_source_states: tuple[CharacteristicState, ...]
  minus_source_states: tuple[CharacteristicState, ...]
  nodes: tuple[MocCharacteristicNode, ...]
  cells: tuple[MocCharacteristicCell, ...]
  topology: MocTopologyResult
  total_pressure_Pa: float
  maximum_geometry_residual_m: float | None
  maximum_absolute_invariant_residual: float | None
  message: str = ''

  def __post_init__(self) -> None:
    if not isfinite(float(self.total_pressure_Pa)) or self.total_pressure_Pa <= 0.0:
      raise ValueError('total_pressure_Pa must be finite and positive')
  ####

  @property
  def converged(self) -> bool:
    return self.status is MocSourceStripStatus.CONVERGED_OPEN
  ####

  @property
  def node_count(self) -> int:
    return len(self.nodes)
  ####

  @property
  def cell_count(self) -> int:
    return len(self.cells)
  ####

  def state_at(
    self,
    point_m: tuple[float, float],
    *,
    position_tolerance_m: float = 1.0e-10,
  ) -> CharacteristicState | None:
    """Interpolate a state inside the strip, returning ``None`` outside it."""

    point = _finite_point(point_m, 'point_m')
    if not isfinite(float(position_tolerance_m)) or position_tolerance_m <= 0.0:
      raise ValueError('position_tolerance_m must be finite and positive')
    for state in (*self.plus_source_states, *self.minus_source_states):
      if _distance(point, (state.x_m, state.y_m)) <= position_tolerance_m:
        return CharacteristicState(
          x_m=point[0],
          y_m=point[1],
          theta_rad=state.theta_rad,
          mach=state.mach,
          gamma=state.gamma,
        )
    node_by_key = {
      (node.centerline_index, node.boundary_index): node
      for node in self.nodes
    }
    for cell in self.cells:
      samples = _cell_samples(self, cell, node_by_key)
      if samples is None:
        continue
      vertices, states = samples
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
      return CharacteristicState(
        x_m=point[0],
        y_m=point[1],
        theta_rad=theta,
        mach=inverse.value,
        gamma=states[0].gamma,
      )
    return None
  ####

  def static_pressure_at(
    self,
    point_m: tuple[float, float],
    *,
    position_tolerance_m: float = 1.0e-10,
  ) -> float | None:
    """Return the isentropic static pressure for a sampled strip state."""

    state = self.state_at(point_m, position_tolerance_m=position_tolerance_m)
    if state is None:
      return None
    pressure_ratio = (
      1.0 + 0.5 * (state.gamma - 1.0) * state.mach * state.mach
    ) ** (state.gamma / (state.gamma - 1.0))
    return self.total_pressure_Pa / pressure_ratio
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'plus_source_count': len(self.plus_source_states),
      'minus_source_count': len(self.minus_source_states),
      'node_count': self.node_count,
      'cell_count': self.cell_count,
      'topology_forms_closed_zone': self.topology.forms_closed_zone,
      'nonmanifold_edge_count': self.topology.nonmanifold_edge_count,
      'maximum_geometry_residual_m': self.maximum_geometry_residual_m,
      'maximum_absolute_invariant_residual': self.maximum_absolute_invariant_residual,
      'total_pressure_Pa': self.total_pressure_Pa,
      'message': self.message,
    }
####


@dataclass(frozen=True, slots=True)
class MocSourceStripContinuationResult:
  """An open source strip extended with an explicit constant-``K+`` law."""

  status: MocSourceStripContinuationStatus
  strip: MocSourceCharacteristicStripResult | None
  plus_source_states: tuple[CharacteristicState, ...]
  minus_source_states: tuple[CharacteristicState, ...]
  added_sample_count: int
  axis_step_m: float
  continuation_k_plus: float | None
  message: str = ''

  @property
  def converged(self) -> bool:
    return self.status is MocSourceStripContinuationStatus.CONVERGED_EXTENDED
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'added_sample_count': self.added_sample_count,
      'axis_step_m': self.axis_step_m,
      'continuation_k_plus': self.continuation_k_plus,
      'strip': None if self.strip is None else self.strip.as_report(),
      'message': self.message,
    }
####


def _empty_topology() -> MocTopologyResult:
  return validate_moc_mesh(())


def _finite_point(point_m: tuple[float, float], name: str) -> tuple[float, float]:
  if len(point_m) != 2 or not all(isfinite(float(value)) for value in point_m):
    raise ValueError(f'{name} must contain two finite coordinates')
  return float(point_m[0]), float(point_m[1])


def _distance(first: tuple[float, float], second: tuple[float, float]) -> float:
  return ((first[0] - second[0]) ** 2 + (first[1] - second[1]) ** 2) ** 0.5


def _failure(
  status: MocSourceStripStatus,
  plus_sources: tuple[CharacteristicState, ...],
  minus_sources: tuple[CharacteristicState, ...],
  *,
  nodes: Sequence[MocCharacteristicNode] = (),
  cells: Sequence[MocCharacteristicCell] = (),
  topology: MocTopologyResult | None = None,
  maximum_geometry_residual_m: float | None = None,
  maximum_absolute_invariant_residual: float | None = None,
  total_pressure_Pa: float,
  message: str,
) -> MocSourceCharacteristicStripResult:
  return MocSourceCharacteristicStripResult(
    status=status,
    plus_source_states=plus_sources,
    minus_source_states=minus_sources,
    nodes=tuple(nodes),
    cells=tuple(cells),
    topology=_empty_topology() if topology is None else topology,
    total_pressure_Pa=total_pressure_Pa,
    maximum_geometry_residual_m=maximum_geometry_residual_m,
    maximum_absolute_invariant_residual=maximum_absolute_invariant_residual,
    message=message,
  )


def assemble_source_characteristic_strip(
  plus_source_states: Sequence[CharacteristicState],
  minus_source_states: Sequence[CharacteristicState],
  total_pressure_Pa: float,
  *,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
) -> MocSourceCharacteristicStripResult:
  """Assemble a triangular strip from axis and outer source states.

  The source arrays must have the same length and at least three states.  The
  plus sources are required to lie on the symmetry line.  For each diagonal
  pair ``(i, i)``, the compatible C+/C- intersection must reproduce the
  corresponding minus-source point; this is the seam that prevents a source
  line from being silently replaced by a merely topological diagonal.
  """

  plus = tuple(plus_source_states)
  minus = tuple(minus_source_states)
  try:
    pressure = float(total_pressure_Pa)
  except (TypeError, ValueError):
    pressure = float('nan')
  if not isfinite(pressure) or pressure <= 0.0:
    return _failure(
      MocSourceStripStatus.INVALID_INPUT,
      plus,
      minus,
      total_pressure_Pa=1.0,
      message='total_pressure_Pa must be finite and positive',
    )
  if len(plus) != len(minus) or len(plus) < 3:
    return _failure(
      MocSourceStripStatus.INVALID_INPUT,
      plus,
      minus,
      total_pressure_Pa=pressure,
      message='source strips require equal arrays with at least three states',
    )
  if any(not isinstance(state, CharacteristicState) for state in (*plus, *minus)):
    return _failure(
      MocSourceStripStatus.INVALID_INPUT,
      plus,
      minus,
      total_pressure_Pa=pressure,
      message='source arrays must contain CharacteristicState values',
    )
  if not isfinite(float(position_tolerance_m)) or position_tolerance_m <= 0.0:
    raise ValueError('position_tolerance_m must be finite and positive')
  if not isfinite(float(invariant_tolerance)) or invariant_tolerance <= 0.0:
    raise ValueError('invariant_tolerance must be finite and positive')
  gamma = plus[0].gamma
  if any(abs(state.gamma - gamma) > invariant_tolerance for state in (*plus, *minus)):
    return _failure(
      MocSourceStripStatus.INVALID_INPUT,
      plus,
      minus,
      total_pressure_Pa=pressure,
      message='source arrays must use one common gamma',
    )
  if any(abs(state.y_m) > position_tolerance_m for state in plus):
    return _failure(
      MocSourceStripStatus.INVALID_INPUT,
      plus,
      minus,
      total_pressure_Pa=pressure,
      message='plus source states must lie on the symmetry line',
    )
  ####

  nodes_by_index: dict[tuple[int, int], MocCharacteristicNode] = {}
  for centerline_index in range(len(plus)):
    for boundary_index in range(centerline_index + 1):
      point_result = interior_characteristic_point(
        plus[centerline_index],
        minus[boundary_index],
        position_tolerance_m=position_tolerance_m,
        invariant_tolerance=invariant_tolerance,
      )
      if not point_result.converged or point_result.state is None or point_result.point_m is None:
        return _failure(
          MocSourceStripStatus.GEOMETRY_FAILURE,
          plus,
          minus,
          nodes=tuple(nodes_by_index.values()),
          total_pressure_Pa=pressure,
          message=(
            f'characteristic node ({centerline_index}, {boundary_index}) failed: '
            f'{point_result.message}'
          ),
        )
      point = point_result.point_m
      if centerline_index == boundary_index:
        expected = minus[boundary_index]
        discrepancy = _distance(point, (expected.x_m, expected.y_m))
        if discrepancy > position_tolerance_m:
          return _failure(
            MocSourceStripStatus.GEOMETRY_FAILURE,
            plus,
            minus,
            nodes=tuple(nodes_by_index.values()),
            total_pressure_Pa=pressure,
            maximum_geometry_residual_m=discrepancy,
            message=(
              f'diagonal source node ({centerline_index}, {boundary_index}) '
              f'does not reproduce its minus source point; residual={discrepancy}'
            ),
          )
        point = (expected.x_m, expected.y_m)
      nodes_by_index[(centerline_index, boundary_index)] = MocCharacteristicNode(
        centerline_index=centerline_index,
        boundary_index=boundary_index,
        point_m=(float(point[0]), float(point[1])),
        state=point_result.state,
        point_result=point_result,
        total_pressure_Pa=pressure,
      )
  ####

  nodes = tuple(nodes_by_index.values())

  def node_point(centerline_index: int, boundary_index: int) -> tuple[float, float]:
    return nodes_by_index[(centerline_index, boundary_index)].point_m

  cells_list: list[MocCharacteristicCell] = []
  try:
    for index in range(len(plus) - 1):
      cells_list.append(
        MocCharacteristicCell(
          cell_index=len(cells_list),
          cell_kind='source-axis-strip',
          vertices_xr_m=(
            (plus[index].x_m, plus[index].y_m),
            (plus[index + 1].x_m, plus[index + 1].y_m),
            node_point(index + 1, 0),
            node_point(index, 0),
          ),
          centerline_indices=(index, index + 1),
          boundary_indices=(0,),
        )
      )
    for row in range(1, len(plus) - 1):
      for column in range(row):
        cells_list.append(
          MocCharacteristicCell(
            cell_index=len(cells_list),
            cell_kind='source-interior',
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
    for index in range(len(plus) - 1):
      cells_list.append(
        MocCharacteristicCell(
          cell_index=len(cells_list),
          cell_kind='source-boundary-strip',
          vertices_xr_m=(
            node_point(index, index),
            node_point(index + 1, index),
            (minus[index + 1].x_m, minus[index + 1].y_m),
          ),
          centerline_indices=(index + 1,),
          boundary_indices=(index, index + 1),
        )
      )
  except (KeyError, ValueError) as error:
    return _failure(
      MocSourceStripStatus.GEOMETRY_FAILURE,
      plus,
      minus,
      nodes=nodes,
      cells=cells_list,
      total_pressure_Pa=pressure,
      message=f'source characteristic cell geometry failed: {error}',
    )
  ####

  cells = tuple(cells_list)
  topology = validate_moc_mesh(cells)
  if not topology.forms_closed_zone or topology.nonmanifold_edge_count:
    return _failure(
      MocSourceStripStatus.TOPOLOGY_FAILURE,
      plus,
      minus,
      nodes=nodes,
      cells=cells,
      topology=topology,
      total_pressure_Pa=pressure,
      message=f'source characteristic strip topology failed: {topology.message}',
    )
  ####
  maximum_geometry_residual = max(
    (
      abs(node.point_result.geometry_residual)
      for node in nodes
      if node.point_result.geometry_residual is not None
    ),
    default=None,
  )
  maximum_invariant_residual = max(
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
  return MocSourceCharacteristicStripResult(
    status=MocSourceStripStatus.CONVERGED_OPEN,
    plus_source_states=plus,
    minus_source_states=minus,
    nodes=nodes,
    cells=cells,
    topology=topology,
    total_pressure_Pa=pressure,
    maximum_geometry_residual_m=maximum_geometry_residual,
    maximum_absolute_invariant_residual=maximum_invariant_residual,
    message=(
      'triangular source-boundary characteristic strip converged; '
      'shock and downstream closure remain separate'
    ),
  )
####


def extend_source_characteristic_strip_constant_k_plus(
  plus_source_states: Sequence[CharacteristicState],
  minus_source_states: Sequence[CharacteristicState],
  total_pressure_Pa: float,
  ambient_pressure_Pa: float,
  additional_sample_count: int,
  axis_step_m: float,
  *,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  pressure_tolerance: float = 1.0e-10,
  maximum_iterations: int = 16,
) -> MocSourceStripContinuationResult:
  """Extend an open source strip with a constant-``K+`` simple-wave law.

  The terminal outer-boundary ``K+`` invariant is held fixed.  New axis
  source states use ``theta = 0`` and the corresponding Prandtl--Meyer angle;
  each new outer-boundary state is then obtained from the ambient-pressure
  free-boundary primitive.  This is a deterministic upstream continuation
  suitable for investigating a continued shock-cell chain, but it is not a
  replacement for solving the physical shock/free-boundary closure.
  """

  plus = tuple(plus_source_states)
  minus = tuple(minus_source_states)
  try:
    total_pressure = float(total_pressure_Pa)
    ambient_pressure = float(ambient_pressure_Pa)
  except (TypeError, ValueError):
    return MocSourceStripContinuationResult(
      status=MocSourceStripContinuationStatus.INVALID_INPUT,
      strip=None,
      plus_source_states=plus,
      minus_source_states=minus,
      added_sample_count=0,
      axis_step_m=float('nan'),
      continuation_k_plus=None,
      message='pressures must be finite numeric values',
    )
  if (
    not isfinite(total_pressure)
    or total_pressure <= 0.0
    or not isfinite(ambient_pressure)
    or ambient_pressure <= 0.0
    or total_pressure <= ambient_pressure
  ):
    return MocSourceStripContinuationResult(
      status=MocSourceStripContinuationStatus.INVALID_INPUT,
      strip=None,
      plus_source_states=plus,
      minus_source_states=minus,
      added_sample_count=0,
      axis_step_m=float('nan'),
      continuation_k_plus=None,
      message='total pressure must exceed a finite positive ambient pressure',
    )
  if (
    isinstance(additional_sample_count, bool)
    or not isinstance(additional_sample_count, int)
    or additional_sample_count < 1
  ):
    try:
      reported_axis_step = float(axis_step_m)
    except (TypeError, ValueError):
      reported_axis_step = float('nan')
    return MocSourceStripContinuationResult(
      status=MocSourceStripContinuationStatus.INVALID_INPUT,
      strip=None,
      plus_source_states=plus,
      minus_source_states=minus,
      added_sample_count=0,
      axis_step_m=reported_axis_step,
      continuation_k_plus=None,
      message='additional_sample_count must be a positive integer',
    )
  try:
    axis_step = float(axis_step_m)
  except (TypeError, ValueError):
    axis_step = float('nan')
  if not isfinite(axis_step) or axis_step <= 0.0:
    return MocSourceStripContinuationResult(
      status=MocSourceStripContinuationStatus.INVALID_INPUT,
      strip=None,
      plus_source_states=plus,
      minus_source_states=minus,
      added_sample_count=0,
      axis_step_m=axis_step,
      continuation_k_plus=None,
      message='axis_step_m must be finite and positive',
    )
  if not isfinite(float(pressure_tolerance)) or pressure_tolerance <= 0.0:
    raise ValueError('pressure_tolerance must be finite and positive')
  if (
    isinstance(maximum_iterations, bool)
    or not isinstance(maximum_iterations, int)
    or maximum_iterations < 1
  ):
    raise ValueError('maximum_iterations must be a positive integer')

  initial_strip = assemble_source_characteristic_strip(
    plus,
    minus,
    total_pressure,
    position_tolerance_m=position_tolerance_m,
    invariant_tolerance=invariant_tolerance,
  )
  if not initial_strip.converged:
    return MocSourceStripContinuationResult(
      status=MocSourceStripContinuationStatus.STRIP_FAILURE,
      strip=initial_strip,
      plus_source_states=plus,
      minus_source_states=minus,
      added_sample_count=0,
      axis_step_m=axis_step,
      continuation_k_plus=None,
      message=f'initial source strip is not converged: {initial_strip.message}',
    )

  continuation_k_plus = minus[-1].k_plus
  target_nu = -continuation_k_plus
  if target_nu <= 0.0:
    return MocSourceStripContinuationResult(
      status=MocSourceStripContinuationStatus.BOUNDARY_FAILURE,
      strip=initial_strip,
      plus_source_states=plus,
      minus_source_states=minus,
      added_sample_count=0,
      axis_step_m=axis_step,
      continuation_k_plus=continuation_k_plus,
      message='constant-K+ continuation requires a strictly positive axis Prandtl-Meyer angle',
    )
  axis_inverse = inverse_prandtl_meyer_angle_rad(target_nu, plus[-1].gamma)
  if not axis_inverse.converged or axis_inverse.value is None:
    return MocSourceStripContinuationResult(
      status=MocSourceStripContinuationStatus.BOUNDARY_FAILURE,
      strip=initial_strip,
      plus_source_states=plus,
      minus_source_states=minus,
      added_sample_count=0,
      axis_step_m=axis_step,
      continuation_k_plus=continuation_k_plus,
      message=(
        'constant-K+ continuation cannot construct a supersonic axis state: '
        f'{axis_inverse.message}'
      ),
    )

  extended_plus = list(plus)
  extended_minus = list(minus)
  for _ in range(additional_sample_count):
    previous_plus = extended_plus[-1]
    previous_minus = extended_minus[-1]
    incoming = CharacteristicState(
      x_m=previous_plus.x_m + axis_step,
      y_m=0.0,
      theta_rad=0.0,
      mach=axis_inverse.value,
      gamma=previous_plus.gamma,
    )
    boundary_result = solve_ambient_pressure_free_boundary_point(
      incoming,
      previous_minus,
      CharacteristicFamily.PLUS,
      total_pressure_Pa=total_pressure,
      ambient_pressure_Pa=ambient_pressure,
      position_tolerance_m=position_tolerance_m,
      pressure_tolerance=pressure_tolerance,
      maximum_iterations=maximum_iterations,
    )
    if (
      not boundary_result.converged
      or boundary_result.state is None
      or boundary_result.point_m is None
    ):
      return MocSourceStripContinuationResult(
        status=MocSourceStripContinuationStatus.BOUNDARY_FAILURE,
        strip=initial_strip,
        plus_source_states=tuple(extended_plus),
        minus_source_states=tuple(extended_minus),
        added_sample_count=len(extended_minus) - len(minus),
        axis_step_m=axis_step,
        continuation_k_plus=continuation_k_plus,
        message=(
          'constant-K+ ambient boundary continuation failed after '
          f'{len(extended_minus) - len(minus)} added samples: '
          f'{boundary_result.message}'
        ),
      )
    if boundary_result.state.x_m <= previous_minus.x_m + position_tolerance_m:
      return MocSourceStripContinuationResult(
        status=MocSourceStripContinuationStatus.BOUNDARY_FAILURE,
        strip=initial_strip,
        plus_source_states=tuple(extended_plus),
        minus_source_states=tuple(extended_minus),
        added_sample_count=len(extended_minus) - len(minus),
        axis_step_m=axis_step,
        continuation_k_plus=continuation_k_plus,
        message='constant-K+ ambient boundary continuation stopped without downstream progress',
      )
    extended_plus.append(incoming)
    extended_minus.append(boundary_result.state)

  extended_strip = assemble_source_characteristic_strip(
    extended_plus,
    extended_minus,
    total_pressure,
    position_tolerance_m=position_tolerance_m,
    invariant_tolerance=invariant_tolerance,
  )
  if not extended_strip.converged:
    return MocSourceStripContinuationResult(
      status=MocSourceStripContinuationStatus.STRIP_FAILURE,
      strip=extended_strip,
      plus_source_states=tuple(extended_plus),
      minus_source_states=tuple(extended_minus),
      added_sample_count=len(extended_minus) - len(minus),
      axis_step_m=axis_step,
      continuation_k_plus=continuation_k_plus,
      message=(
        'constant-K+ source continuation reached its requested samples, but '
        f'the extended strip failed: {extended_strip.message}'
      ),
    )
  return MocSourceStripContinuationResult(
    status=MocSourceStripContinuationStatus.CONVERGED_EXTENDED,
    strip=extended_strip,
    plus_source_states=tuple(extended_plus),
    minus_source_states=tuple(extended_minus),
    added_sample_count=len(extended_minus) - len(minus),
    axis_step_m=axis_step,
    continuation_k_plus=continuation_k_plus,
    message=(
      'constant-K+ simple-wave source continuation converged as an open '
      'upstream strip; physical shock fitting and downstream closure remain pending'
    ),
  )
####


def _cell_samples(
  strip: MocSourceCharacteristicStripResult,
  cell: MocCharacteristicCell,
  node_by_key: dict[tuple[int, int], MocCharacteristicNode],
) -> tuple[tuple[tuple[float, float], ...], tuple[CharacteristicState, ...]] | None:
  def node_sample(key: tuple[int, int]) -> tuple[tuple[float, float], CharacteristicState] | None:
    node = node_by_key.get(key)
    return None if node is None else (node.point_m, node.state)

  if cell.cell_kind == 'source-axis-strip':
    first, second = cell.centerline_indices
    samples = (
      ((strip.plus_source_states[first].x_m, strip.plus_source_states[first].y_m), strip.plus_source_states[first]),
      ((strip.plus_source_states[second].x_m, strip.plus_source_states[second].y_m), strip.plus_source_states[second]),
      node_sample((second, 0)),
      node_sample((first, 0)),
    )
  elif cell.cell_kind == 'source-interior':
    row, next_row = cell.centerline_indices
    column, next_column = cell.boundary_indices
    samples = (
      node_sample((row, column)),
      node_sample((next_row, column)),
      node_sample((next_row, next_column)),
      node_sample((row, next_column)),
    )
  elif cell.cell_kind == 'source-boundary-strip':
    first, second = cell.boundary_indices
    samples = (
      node_sample((first, first)),
      node_sample((second, first)),
      ((strip.minus_source_states[second].x_m, strip.minus_source_states[second].y_m), strip.minus_source_states[second]),
    )
  else:
    return None
  if any(sample is None for sample in samples):
    return None
  resolved = tuple(sample for sample in samples if sample is not None)
  return tuple(cell.vertices_xr_m), tuple(sample[1] for sample in resolved)


def _triangle_weights(
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
    return _triangle_weights(point, vertices, tolerance_m=tolerance_m)
  first = _triangle_weights(
    point,
    (vertices[0], vertices[1], vertices[2]),
    tolerance_m=tolerance_m,
  )
  if first is not None:
    return first[0], first[1], first[2], 0.0
  second = _triangle_weights(
    point,
    (vertices[0], vertices[2], vertices[3]),
    tolerance_m=tolerance_m,
  )
  if second is not None:
    return second[0], 0.0, second[1], second[2]
  return None
####
