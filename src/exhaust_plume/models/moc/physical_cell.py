"""Boundary-conditioned triangular post-shock cell assembly.

This module is the next seam after the diagnostic shrinking-front field.  It
does not choose a shock or invent an outer boundary.  Instead, it consumes a
branch-checked shock boundary and an independently sampled ambient-pressure
outer boundary, couples them through a triangular ``C+``/``C-`` net, and
requires the remaining perimeter to reproduce the centerline.  That contract
is suitable for a future free-boundary shooter and cannot silently promote the
existing topological fan.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import cos, isfinite, sin, sqrt
from typing import Any, Sequence

from exhaust_plume.models.moc.ambient_boundary import (
  MocAmbientBoundarySample,
  MocAmbientBoundaryStatus,
  MocAmbientPressureBoundaryResult,
  validate_ambient_pressure_boundary,
)
from exhaust_plume.models.moc.chain import (
  MocCellClosureStatus,
  MocChainBoundaryKind,
  MocChainBoundarySample,
  MocChainCell,
  MocChainGeometryFidelity,
)
from exhaust_plume.models.moc.post_shock import MocShockBoundaryFitResult
from exhaust_plume.models.moc.primitives import (
  CharacteristicState,
  CharacteristicPointResult,
  MocPrimitiveStatus,
  interior_characteristic_point,
)
from exhaust_plume.models.moc.topology import MocTopologyResult, validate_moc_mesh
from exhaust_plume.models.moc.zone import MocCharacteristicCell, MocCharacteristicNode

__all__ = (
  'MocPhysicalPostShockFieldStatus',
  'MocPhysicalPostShockFieldResult',
  'assemble_ambient_boundary_post_shock_field',
)


class MocPhysicalPostShockFieldStatus(str, Enum):
  """Structured outcome for a coupled shock/outer/centerline cell."""

  CONVERGED_AMBIENT_CLOSED = 'converged_ambient_closed_field'
  INVALID_INPUT = 'invalid_input'
  SHOCK_FAILURE = 'shock_boundary_failure'
  AMBIENT_BOUNDARY_FAILURE = 'ambient_boundary_failure'
  GEOMETRY_FAILURE = 'geometry_failure'
  INVARIANT_FAILURE = 'invariant_failure'
  AXIS_FAILURE = 'centerline_closure_failure'
  TOPOLOGY_FAILURE = 'topology_failure'
####


@dataclass(frozen=True, slots=True)
class MocPhysicalPostShockFieldResult:
  """A post-shock field accepted against an explicit ambient perimeter."""

  status: MocPhysicalPostShockFieldStatus
  characteristic_layer_count: int
  nodes: tuple[MocCharacteristicNode, ...]
  cells: tuple[MocCharacteristicCell, ...]
  topology: MocTopologyResult
  shock_boundary_points_m: tuple[tuple[float, float], ...]
  ambient_boundary_points_m: tuple[tuple[float, float], ...]
  centerline_boundary_points_m: tuple[tuple[float, float], ...]
  centerline_boundary_states: tuple[CharacteristicState, ...]
  centerline_boundary_total_pressure_Pa: tuple[float, ...]
  ambient_boundary: MocAmbientPressureBoundaryResult
  maximum_geometry_residual_m: float | None
  maximum_absolute_invariant_residual: float | None
  minimum_post_shock_total_pressure_ratio: float | None
  maximum_post_shock_total_pressure_ratio: float | None
  message: str = ''
  characteristic_family_orientation_verified: bool = False

  @property
  def converged(self) -> bool:
    return self.status is MocPhysicalPostShockFieldStatus.CONVERGED_AMBIENT_CLOSED
  ####

  @property
  def physical_closure_verified(self) -> bool:
    return self.converged and self.characteristic_family_orientation_verified
  ####

  @property
  def node_count(self) -> int:
    return len(self.nodes)
  ####

  @property
  def cell_count(self) -> int:
    return len(self.cells)
  ####

  @property
  def pressure_loss_verified(self) -> bool:
    return (
      self.minimum_post_shock_total_pressure_ratio is not None
      and self.maximum_post_shock_total_pressure_ratio is not None
      and self.minimum_post_shock_total_pressure_ratio > 0.0
      and self.maximum_post_shock_total_pressure_ratio < 1.0
    )
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'physical_closure_verified': self.physical_closure_verified,
      'characteristic_family_orientation_verified': (
        self.characteristic_family_orientation_verified
      ),
      'characteristic_layer_count': self.characteristic_layer_count,
      'node_count': self.node_count,
      'cell_count': self.cell_count,
      'topology_forms_closed_zone': self.topology.forms_closed_zone,
      'nonmanifold_edge_count': self.topology.nonmanifold_edge_count,
      'ambient_boundary': self.ambient_boundary.as_report(),
      'maximum_geometry_residual_m': self.maximum_geometry_residual_m,
      'maximum_absolute_invariant_residual': self.maximum_absolute_invariant_residual,
      'minimum_post_shock_total_pressure_ratio': self.minimum_post_shock_total_pressure_ratio,
      'maximum_post_shock_total_pressure_ratio': self.maximum_post_shock_total_pressure_ratio,
      'message': self.message,
    }
  ####

  def as_chain_cell(
    self,
    *,
    start_x_m: float,
    end_x_m: float,
    cell_index: int = 1,
    diagnostics: dict[str, Any] | None = None,
  ) -> MocChainCell:
    """Promote only a fully ambient-closed cell into the resolved chain."""

    if not self.physical_closure_verified:
      raise ValueError(
        'only a converged ambient-closed post-shock field with verified '
        'shock-C+/ambient-C- family orientation can become a chain cell'
      )
    chain_diagnostics: dict[str, Any] = {
      'source': 'ambient-pressure-coupled-post-shock-field',
      'physical_closure_verified': True,
      'characteristic_layer_count': self.characteristic_layer_count,
      'node_count': self.node_count,
      'cell_count': self.cell_count,
      'maximum_geometry_residual_m': self.maximum_geometry_residual_m,
      'maximum_absolute_invariant_residual': self.maximum_absolute_invariant_residual,
      'minimum_post_shock_total_pressure_ratio': self.minimum_post_shock_total_pressure_ratio,
      'maximum_post_shock_total_pressure_ratio': self.maximum_post_shock_total_pressure_ratio,
      'ambient_boundary_maximum_absolute_pressure_residual': (
        self.ambient_boundary.maximum_absolute_pressure_residual
      ),
      'ambient_boundary_maximum_absolute_tangent_residual': (
        self.ambient_boundary.maximum_absolute_tangent_residual
      ),
    }
    if diagnostics is not None:
      reserved = set(chain_diagnostics) & set(diagnostics)
      if reserved:
        raise ValueError(f'diagnostics cannot override reserved closure keys: {sorted(reserved)!r}')
      chain_diagnostics.update(diagnostics)
    return MocChainCell(
      cell_index=cell_index,
      start_x_m=start_x_m,
      end_x_m=end_x_m,
      mesh=self.cells,
      geometry_fidelity=MocChainGeometryFidelity.RESOLVED_PLANAR_MOC,
      physical_closure=MocCellClosureStatus.CLOSED,
      diagnostics=chain_diagnostics,
      continuation_boundary=tuple(
        MocChainBoundarySample(state=state, total_pressure_Pa=pressure)
        for state, pressure in zip(
          self.centerline_boundary_states,
          self.centerline_boundary_total_pressure_Pa,
          strict=True,
        )
      ),
      continuation_boundary_kind=MocChainBoundaryKind.CENTERLINE_TRACE,
    )
  ####


def _empty_ambient_boundary(ambient_pressure_Pa: float) -> MocAmbientPressureBoundaryResult:
  return MocAmbientPressureBoundaryResult(
    status=MocAmbientBoundaryStatus.INVALID_INPUT,
    points_m=(),
    states=(),
    total_pressure_Pa=(),
    static_pressure_Pa=(),
    pressure_residuals=(),
    tangent_residuals=(),
    ambient_pressure_Pa=ambient_pressure_Pa,
    maximum_absolute_pressure_residual=None,
    maximum_absolute_tangent_residual=None,
    message='ambient boundary was not assembled',
  )


def _failure(
  status: MocPhysicalPostShockFieldStatus,
  *,
  ambient_boundary: MocAmbientPressureBoundaryResult,
  characteristic_layer_count: int = 0,
  nodes: Sequence[MocCharacteristicNode] = (),
  cells: Sequence[MocCharacteristicCell] = (),
  topology: MocTopologyResult | None = None,
  shock_points: Sequence[tuple[float, float]] = (),
  ambient_points: Sequence[tuple[float, float]] = (),
  axis_points: Sequence[tuple[float, float]] = (),
  axis_states: Sequence[CharacteristicState] = (),
  axis_pressures: Sequence[float] = (),
  pressure_ratios: Sequence[float] = (),
  maximum_geometry_residual_m: float | None = None,
  maximum_absolute_invariant_residual: float | None = None,
  message: str,
) -> MocPhysicalPostShockFieldResult:
  return MocPhysicalPostShockFieldResult(
    status=status,
    characteristic_layer_count=characteristic_layer_count,
    nodes=tuple(nodes),
    cells=tuple(cells),
    topology=validate_moc_mesh(()) if topology is None else topology,
    shock_boundary_points_m=tuple(shock_points),
    ambient_boundary_points_m=tuple(ambient_points),
    centerline_boundary_points_m=tuple(axis_points),
    centerline_boundary_states=tuple(axis_states),
    centerline_boundary_total_pressure_Pa=tuple(float(value) for value in axis_pressures),
    ambient_boundary=ambient_boundary,
    maximum_geometry_residual_m=maximum_geometry_residual_m,
    maximum_absolute_invariant_residual=maximum_absolute_invariant_residual,
    minimum_post_shock_total_pressure_ratio=min(pressure_ratios, default=None),
    maximum_post_shock_total_pressure_ratio=max(pressure_ratios, default=None),
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


def _shock_endpoint_characteristic_point(
  plus_source: CharacteristicState,
  shock_state: CharacteristicState,
  shock_point: tuple[float, float],
  *,
  position_tolerance_m: float,
  invariant_tolerance: float,
) -> CharacteristicPointResult:
  """Validate a ``C+`` arriving at a known shock endpoint.

  The shock sample is itself the ``C-`` source, so a generic two-ray
  intersection sees a zero-length second ray and correctly rejects it as an
  interior point.  A physical shock boundary needs the one-sided endpoint
  contract instead: compatibility must match the shock state and the plus
  characteristic from the outer boundary must arrive at that point.
  """

  if abs(plus_source.gamma - shock_state.gamma) > invariant_tolerance:
    return CharacteristicPointResult(
      status=MocPrimitiveStatus.INVALID_INPUT,
      state=None,
      point_m=None,
      invariant_residual_plus=None,
      invariant_residual_minus=None,
      geometry_residual=None,
      iterations=0,
      message='ambient and shock endpoint states use different gamma values',
    )
  plus_residual = shock_state.k_plus - plus_source.k_plus
  if abs(plus_residual) > invariant_tolerance:
    return CharacteristicPointResult(
      status=MocPrimitiveStatus.INVARIANT_FAILURE,
      state=shock_state,
      point_m=shock_point,
      invariant_residual_plus=plus_residual,
      invariant_residual_minus=0.0,
      geometry_residual=None,
      iterations=0,
      message='ambient-to-shock endpoint does not preserve the C+ invariant',
    )
  start_angle = plus_source.theta_rad + plus_source.mu_rad
  end_angle = shock_state.theta_rad + shock_state.mu_rad
  direction_angle = 0.5 * (start_angle + end_angle)
  direction = (cos(direction_angle), sin(direction_angle))
  displacement = (
    shock_point[0] - plus_source.x_m,
    shock_point[1] - plus_source.y_m,
  )
  forward_parameter = displacement[0] * direction[0] + displacement[1] * direction[1]
  geometry_residual = abs(
    displacement[0] * direction[1] - displacement[1] * direction[0]
  )
  if forward_parameter <= position_tolerance_m:
    return CharacteristicPointResult(
      status=MocPrimitiveStatus.GEOMETRY_FAILURE,
      state=None,
      point_m=None,
      invariant_residual_plus=plus_residual,
      invariant_residual_minus=0.0,
      geometry_residual=geometry_residual,
      iterations=0,
      message='ambient-to-shock C+ endpoint has no forward margin',
    )
  if geometry_residual > position_tolerance_m:
    return CharacteristicPointResult(
      status=MocPrimitiveStatus.GEOMETRY_FAILURE,
      state=None,
      point_m=None,
      invariant_residual_plus=plus_residual,
      invariant_residual_minus=0.0,
      geometry_residual=geometry_residual,
      iterations=0,
      message='ambient-to-shock C+ endpoint is not on its averaged characteristic',
    )
  return CharacteristicPointResult(
    status=MocPrimitiveStatus.CONVERGED,
    state=shock_state,
    point_m=shock_point,
    invariant_residual_plus=plus_residual,
    invariant_residual_minus=0.0,
    geometry_residual=geometry_residual,
    iterations=0,
    intersection_status='boundary-endpoint',
  )


def assemble_ambient_boundary_post_shock_field(
  shock_fit: MocShockBoundaryFitResult,
  ambient_boundary: Sequence[MocAmbientBoundarySample],
  ambient_pressure_Pa: float,
  *,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  pressure_tolerance: float = 1.0e-8,
  tangent_tolerance: float = 1.0e-8,
) -> MocPhysicalPostShockFieldResult:
  """Assemble a shock/ambient/centerline triangular characteristic field.

  The ambient samples are the physical outer boundary and are ordered from
  the shock attachment toward the downstream axis.  ``C+`` sources are taken
  from that boundary and ``C-`` sources from the downstream shock states.  A
  diagonal intersection must reproduce each shock point; the unlabelled
  closing perimeter must then lie on ``y=0`` with ``theta=0``.  This is a
  coupled boundary acceptance primitive, not an automatic boundary shooter.
  """

  if not isinstance(shock_fit, MocShockBoundaryFitResult):
    ambient_result = _empty_ambient_boundary(float(ambient_pressure_Pa))
    return _failure(
      MocPhysicalPostShockFieldStatus.INVALID_INPUT,
      ambient_boundary=ambient_result,
      message='shock_fit must be a MocShockBoundaryFitResult',
    )
  if not isfinite(float(ambient_pressure_Pa)) or ambient_pressure_Pa <= 0.0:
    raise ValueError('ambient_pressure_Pa must be finite and positive')
  for name, value in (
    ('position_tolerance_m', position_tolerance_m),
    ('invariant_tolerance', invariant_tolerance),
    ('pressure_tolerance', pressure_tolerance),
    ('tangent_tolerance', tangent_tolerance),
  ):
    if not isfinite(float(value)) or value <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
  if not shock_fit.converged:
    ambient_result = _empty_ambient_boundary(float(ambient_pressure_Pa))
    return _failure(
      MocPhysicalPostShockFieldStatus.SHOCK_FAILURE,
      ambient_boundary=ambient_result,
      message=f'shock boundary fit is not converged: {shock_fit.message}',
    )
  samples = tuple(ambient_boundary)
  if any(not isinstance(sample, MocAmbientBoundarySample) for sample in samples):
    ambient_result = _empty_ambient_boundary(float(ambient_pressure_Pa))
    return _failure(
      MocPhysicalPostShockFieldStatus.INVALID_INPUT,
      ambient_boundary=ambient_result,
      message='ambient_boundary must contain MocAmbientBoundarySample values',
    )
  shock_samples = tuple(shock_fit.boundary_states)
  if len(shock_samples) < 3 or len(samples) != len(shock_samples):
    ambient_result = _empty_ambient_boundary(float(ambient_pressure_Pa))
    return _failure(
      MocPhysicalPostShockFieldStatus.INVALID_INPUT,
      ambient_boundary=ambient_result,
      message='shock and ambient boundaries must contain the same three-or-more sample count',
    )
  ambient_result = validate_ambient_pressure_boundary(
    samples,
    ambient_pressure_Pa,
    position_tolerance_m=position_tolerance_m,
    pressure_tolerance=pressure_tolerance,
    tangent_tolerance=tangent_tolerance,
  )
  if not ambient_result.converged:
    return _failure(
      MocPhysicalPostShockFieldStatus.AMBIENT_BOUNDARY_FAILURE,
      ambient_boundary=ambient_result,
      shock_points=tuple(sample.point_m for sample in shock_samples),
      ambient_points=tuple(sample.point_m for sample in samples),
      message=f'ambient boundary is not accepted: {ambient_result.message}',
    )
  shock_points = tuple(sample.point_m for sample in shock_samples)
  ambient_points = tuple(sample.point_m for sample in samples)
  if (
    any(
      abs(shock.point_m[0] - shock.state.x_m) > position_tolerance_m
      or abs(shock.point_m[1] - shock.state.y_m) > position_tolerance_m
      for shock in shock_samples
    )
  ):
    return _failure(
      MocPhysicalPostShockFieldStatus.INVALID_INPUT,
      ambient_boundary=ambient_result,
      shock_points=shock_points,
      ambient_points=ambient_points,
      message='shock boundary state coordinates do not match their fitted points',
    )
  if any(point[1] < -position_tolerance_m for point in shock_points):
    return _failure(
      MocPhysicalPostShockFieldStatus.GEOMETRY_FAILURE,
      ambient_boundary=ambient_result,
      shock_points=shock_points,
      ambient_points=ambient_points,
      message='shock boundary crossed below the symmetry line',
    )
  if any(
    second[0] <= first[0] + position_tolerance_m
    or second[1] > first[1] + position_tolerance_m
    for first, second in zip(shock_points, shock_points[1:])
  ):
    return _failure(
      MocPhysicalPostShockFieldStatus.GEOMETRY_FAILURE,
      ambient_boundary=ambient_result,
      shock_points=shock_points,
      ambient_points=ambient_points,
      message='shock boundary must be strictly downstream and nonincreasing in y',
    )
  if (
    sqrt(
      (shock_points[0][0] - ambient_points[0][0]) ** 2
      + (shock_points[0][1] - ambient_points[0][1]) ** 2
    ) > position_tolerance_m
  ):
    return _failure(
      MocPhysicalPostShockFieldStatus.GEOMETRY_FAILURE,
      ambient_boundary=ambient_result,
      shock_points=shock_points,
      ambient_points=ambient_points,
      message='shock and ambient boundaries must share their attachment point',
    )
  if abs(shock_points[-1][1]) > position_tolerance_m:
    return _failure(
      MocPhysicalPostShockFieldStatus.GEOMETRY_FAILURE,
      ambient_boundary=ambient_result,
      shock_points=shock_points,
      ambient_points=ambient_points,
      message='shock boundary must terminate on the symmetry line',
    )
  if abs(ambient_points[-1][1]) > position_tolerance_m:
    return _failure(
      MocPhysicalPostShockFieldStatus.GEOMETRY_FAILURE,
      ambient_boundary=ambient_result,
      shock_points=shock_points,
      ambient_points=ambient_points,
      message='ambient boundary must terminate on the symmetry line',
    )
  pressure_ratios = tuple(
    sample.downstream_total_pressure_Pa / sample.upstream_total_pressure_Pa
    for sample in shock_samples
  )
  if any(ratio <= 0.0 or ratio >= 1.0 for ratio in pressure_ratios):
    return _failure(
      MocPhysicalPostShockFieldStatus.SHOCK_FAILURE,
      ambient_boundary=ambient_result,
      shock_points=shock_points,
      ambient_points=ambient_points,
      pressure_ratios=pressure_ratios,
      message='shock boundary must carry strict total-pressure loss at every sample',
    )
  ####

  expected_count = len(samples)
  nodes_by_index: dict[tuple[int, int], MocCharacteristicNode] = {}
  for plus_index in range(expected_count):
    plus_source = samples[plus_index].state
    for minus_index in range(plus_index + 1):
      minus_source = shock_samples[minus_index].state
      if plus_index == minus_index:
        if plus_index == 0:
          point_result = CharacteristicPointResult(
            status=MocPrimitiveStatus.CONVERGED,
            state=minus_source,
            point_m=shock_points[0],
            invariant_residual_plus=0.0,
            invariant_residual_minus=0.0,
            geometry_residual=0.0,
            iterations=0,
            intersection_status='shared-boundary-attachment',
          )
          point = shock_points[0]
          state = minus_source
        elif (
          plus_index == expected_count - 1
          and abs(ambient_points[-1][1]) <= position_tolerance_m
          and abs(shock_points[-1][1]) <= position_tolerance_m
        ):
          point_result = CharacteristicPointResult(
            status=MocPrimitiveStatus.CONVERGED,
            state=minus_source,
            point_m=shock_points[plus_index],
            invariant_residual_plus=0.0,
            invariant_residual_minus=0.0,
            geometry_residual=0.0,
            iterations=0,
            intersection_status='shared-centerline-corner',
          )
          point = shock_points[plus_index]
          state = minus_source
        else:
          point_result = _shock_endpoint_characteristic_point(
            plus_source,
            minus_source,
            shock_points[plus_index],
            position_tolerance_m=position_tolerance_m,
            invariant_tolerance=invariant_tolerance,
          )
          if not point_result.converged or point_result.point_m is None or point_result.state is None:
            status = (
              MocPhysicalPostShockFieldStatus.INVARIANT_FAILURE
              if point_result.status.value == 'invariant_failure'
              else MocPhysicalPostShockFieldStatus.GEOMETRY_FAILURE
            )
            return _failure(
              status,
              ambient_boundary=ambient_result,
              characteristic_layer_count=expected_count - 1,
              nodes=tuple(nodes_by_index.values()),
              shock_points=shock_points,
              ambient_points=ambient_points,
              pressure_ratios=pressure_ratios,
              message=f'diagonal shock coupling {plus_index} failed: {point_result.message}',
            )
          point = point_result.point_m
          state = point_result.state
      else:
        point_result = interior_characteristic_point(
          plus_source,
          minus_source,
          position_tolerance_m=position_tolerance_m,
          invariant_tolerance=invariant_tolerance,
        )
        if not point_result.converged or point_result.point_m is None or point_result.state is None:
          status = (
            MocPhysicalPostShockFieldStatus.INVARIANT_FAILURE
            if point_result.status.value == 'invariant_failure'
            else MocPhysicalPostShockFieldStatus.GEOMETRY_FAILURE
          )
          return _failure(
            status,
            ambient_boundary=ambient_result,
            characteristic_layer_count=expected_count - 1,
            nodes=tuple(nodes_by_index.values()),
            shock_points=shock_points,
            ambient_points=ambient_points,
            pressure_ratios=pressure_ratios,
            message=f'characteristic node ({plus_index}, {minus_index}) failed: {point_result.message}',
          )
        point = point_result.point_m
        state = point_result.state
      nodes_by_index[(plus_index, minus_index)] = MocCharacteristicNode(
        centerline_index=plus_index,
        boundary_index=minus_index,
        point_m=(float(point[0]), float(point[1])),
        state=state,
        point_result=point_result,
        total_pressure_Pa=shock_samples[minus_index].downstream_total_pressure_Pa,
      )
  ####

  def node_point(plus_index: int, minus_index: int) -> tuple[float, float]:
    return nodes_by_index[(plus_index, minus_index)].point_m

  def axis_state(plus_index: int, minus_index: int) -> CharacteristicState:
    return nodes_by_index[(plus_index, minus_index)].state

  cells_list: list[MocCharacteristicCell] = []
  try:
    for index in range(expected_count - 1):
      outer_vertices = (
        (
          ambient_points[index],
          ambient_points[index + 1],
          node_point(index + 1, 0),
        )
        if index == 0
        else (
          ambient_points[index],
          ambient_points[index + 1],
          node_point(index + 1, 0),
          node_point(index, 0),
        )
      )
      cells_list.append(
        MocCharacteristicCell(
          cell_index=len(cells_list),
          cell_kind='post-shock-ambient-outer-strip',
          vertices_xr_m=outer_vertices,
          centerline_indices=(index, index + 1),
          boundary_indices=(0,),
        )
      )
    for row in range(1, expected_count - 1):
      for column in range(row):
        cells_list.append(
          MocCharacteristicCell(
            cell_index=len(cells_list),
            cell_kind='post-shock-ambient-interior',
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
    for index in range(expected_count - 1):
      cells_list.append(
        MocCharacteristicCell(
          cell_index=len(cells_list),
          cell_kind='post-shock-ambient-shock-strip',
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
      MocPhysicalPostShockFieldStatus.GEOMETRY_FAILURE,
      ambient_boundary=ambient_result,
      characteristic_layer_count=expected_count - 1,
      nodes=tuple(nodes_by_index.values()),
      cells=tuple(cells_list),
      shock_points=shock_points,
      ambient_points=ambient_points,
      pressure_ratios=pressure_ratios,
      message=f'coupled characteristic cell geometry failed: {error}',
    )
  ####

  cells = tuple(cells_list)
  topology = validate_moc_mesh(cells)
  if not topology.connected or not topology.forms_closed_zone or topology.nonmanifold_edge_count:
    return _failure(
      MocPhysicalPostShockFieldStatus.TOPOLOGY_FAILURE,
      ambient_boundary=ambient_result,
      characteristic_layer_count=expected_count - 1,
      nodes=tuple(nodes_by_index.values()),
      cells=cells,
      topology=topology,
      shock_points=shock_points,
      ambient_points=ambient_points,
      pressure_ratios=pressure_ratios,
      message=f'coupled shock/ambient field topology failed: {topology.message}',
    )
  ####

  axis_points_natural = [shock_points[-1]]
  axis_states_natural = [shock_samples[-1].state]
  axis_pressures_natural = [shock_samples[-1].downstream_total_pressure_Pa]
  axis_points_natural.extend(
    node_point(expected_count - 1, column)
    for column in range(expected_count - 2, -1, -1)
  )
  axis_states_natural.extend(
    axis_state(expected_count - 1, column)
    for column in range(expected_count - 2, -1, -1)
  )
  axis_pressures_natural.extend(
    shock_samples[column].downstream_total_pressure_Pa
    for column in range(expected_count - 2, -1, -1)
  )
  axis_points_natural.append(ambient_points[-1])
  axis_states_natural.append(samples[-1].state)
  axis_pressures_natural.append(samples[-1].total_pressure_Pa)
  natural_axis = (
    tuple(axis_points_natural),
    tuple(axis_states_natural),
    tuple(axis_pressures_natural),
  )
  reversed_axis = (
    tuple(reversed(axis_points_natural)),
    tuple(reversed(axis_states_natural)),
    tuple(reversed(axis_pressures_natural)),
  )
  if all(
    second[0] > first[0] + position_tolerance_m
    for first, second in zip(natural_axis[0], natural_axis[0][1:])
  ):
    axis_points, axis_states, axis_pressures = natural_axis
  elif all(
    second[0] > first[0] + position_tolerance_m
    for first, second in zip(reversed_axis[0], reversed_axis[0][1:])
  ):
    axis_points, axis_states, axis_pressures = reversed_axis
  else:
    axis_points, axis_states, axis_pressures = natural_axis
  if any(
    abs(point[1]) > position_tolerance_m or abs(state.theta_rad) > invariant_tolerance
    for point, state in zip(axis_points, axis_states, strict=True)
  ):
    return _failure(
      MocPhysicalPostShockFieldStatus.AXIS_FAILURE,
      ambient_boundary=ambient_result,
      characteristic_layer_count=expected_count - 1,
      nodes=tuple(nodes_by_index.values()),
      cells=cells,
      topology=topology,
      shock_points=shock_points,
      ambient_points=ambient_points,
      axis_points=axis_points,
      axis_states=axis_states,
      axis_pressures=axis_pressures,
      pressure_ratios=pressure_ratios,
      message='coupled field closing perimeter does not reproduce centerline y=0 and theta=0',
    )
  if any(
    second[0] <= first[0] + position_tolerance_m
    for first, second in zip(axis_points, axis_points[1:])
  ):
    return _failure(
      MocPhysicalPostShockFieldStatus.AXIS_FAILURE,
      ambient_boundary=ambient_result,
      characteristic_layer_count=expected_count - 1,
      nodes=tuple(nodes_by_index.values()),
      cells=cells,
      topology=topology,
      shock_points=shock_points,
      ambient_points=ambient_points,
      axis_points=axis_points,
      axis_states=axis_states,
      axis_pressures=axis_pressures,
      pressure_ratios=pressure_ratios,
      message='coupled field centerline closure is not strictly downstream',
    )
  ####

  edge_counts = _edge_counts(cells, position_tolerance_m)
  if not (
    _path_edges_present(shock_points, edge_counts, position_tolerance_m)
    and _path_edges_present(ambient_points, edge_counts, position_tolerance_m)
    and _path_edges_present(axis_points, edge_counts, position_tolerance_m)
  ):
    return _failure(
      MocPhysicalPostShockFieldStatus.GEOMETRY_FAILURE,
      ambient_boundary=ambient_result,
      characteristic_layer_count=expected_count - 1,
      nodes=tuple(nodes_by_index.values()),
      cells=cells,
      topology=topology,
      shock_points=shock_points,
      ambient_points=ambient_points,
      axis_points=axis_points,
      axis_states=axis_states,
      axis_pressures=axis_pressures,
      pressure_ratios=pressure_ratios,
      message='coupled field is missing an explicit shock, ambient, or centerline perimeter edge',
    )
  maximum_geometry_residual = max(
    (
      abs(node.point_result.geometry_residual)
      for node in nodes_by_index.values()
      if node.point_result.geometry_residual is not None
    ),
    default=None,
  )
  maximum_invariant_residual = max(
    (
      abs(value)
      for node in nodes_by_index.values()
      for value in (
        node.point_result.invariant_residual_plus,
        node.point_result.invariant_residual_minus,
      )
      if value is not None
    ),
    default=None,
  )
  return MocPhysicalPostShockFieldResult(
    status=MocPhysicalPostShockFieldStatus.CONVERGED_AMBIENT_CLOSED,
    characteristic_layer_count=expected_count - 1,
    nodes=tuple(nodes_by_index.values()),
    cells=cells,
    topology=topology,
    shock_boundary_points_m=shock_points,
    ambient_boundary_points_m=ambient_points,
    centerline_boundary_points_m=axis_points,
    centerline_boundary_states=axis_states,
    centerline_boundary_total_pressure_Pa=axis_pressures,
    ambient_boundary=ambient_result,
    maximum_geometry_residual_m=maximum_geometry_residual,
    maximum_absolute_invariant_residual=maximum_invariant_residual,
    minimum_post_shock_total_pressure_ratio=min(pressure_ratios),
    maximum_post_shock_total_pressure_ratio=max(pressure_ratios),
    message=(
      'ambient-pressure outer boundary, fitted shock, and centerline closing '
      'perimeter converged through a coupled triangular characteristic field'
    ),
  )
