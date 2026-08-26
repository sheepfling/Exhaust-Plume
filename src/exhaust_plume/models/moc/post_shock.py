"""Prescribed-boundary post-shock characteristic continuation primitives.

The first-cell shock fit is intentionally still outside this module.  The
caller must provide downstream states sampled along an ordered shock
boundary.  This module only verifies the physically useful next operation:
the inward ``C-`` characteristics from those post-shock states reach the
symmetry line as forward, compatible states with a declared total-pressure
loss.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import atan2, isfinite, pi
from typing import Any, Sequence

from exhaust_plume.models.moc.primitives import (
  CharacteristicFamily,
  CharacteristicPointResult,
  CharacteristicState,
  MocPrimitiveStatus,
  centerline_characteristic_point,
  interior_characteristic_point,
)
from exhaust_plume.models.moc.compression import solve_attached_compression_to_turn
from exhaust_plume.models.moc.chain import (
  MocCellClosureStatus,
  MocChainCell,
  MocChainGeometryFidelity,
)
from exhaust_plume.models.moc.topology import MocTopologyResult, validate_moc_mesh
from exhaust_plume.models.moc.zone import (
  MocCharacteristicCell,
  MocCharacteristicNode,
)
from exhaust_plume.util.aero.shock_validity import ShockBranch

__all__ = (
  'MocPostShockBoundaryState',
  'MocPostShockCharacteristicSegment',
  'MocPostShockContinuationResult',
  'MocPostShockContinuationStatus',
  'MocPostShockCrossCharacteristic',
  'MocPostShockFirstLayerResult',
  'MocPostShockFirstLayerStatus',
  'MocPostShockCharacteristicZoneResult',
  'MocPostShockZoneStatus',
  'MocPostShockClosedFieldResult',
  'MocPostShockClosureStatus',
  'MocShockBoundaryFitResult',
  'MocShockBoundaryFitStatus',
  'assemble_post_shock_first_layer',
  'assemble_post_shock_characteristic_zone',
  'continue_post_shock_characteristics_to_centerline',
  'fit_attached_shock_boundary',
  'validate_closed_post_shock_field',
)


class MocPostShockContinuationStatus(str, Enum):
  """Structured outcome for prescribed post-shock continuation."""

  CONVERGED_PRESCRIBED_BOUNDARY = 'converged_prescribed_boundary'
  INVALID_INPUT = 'invalid_input'
  GEOMETRY_FAILURE = 'geometry_failure'
  INVARIANT_FAILURE = 'invariant_failure'
####


class MocPostShockFirstLayerStatus(str, Enum):
  """Outcome for the first downstream cross-characteristic layer."""

  CONVERGED_FIRST_LAYER = 'converged_first_downstream_layer'
  INVALID_INPUT = 'invalid_input'
  GEOMETRY_FAILURE = 'geometry_failure'
  INVARIANT_FAILURE = 'invariant_failure'
####


class MocPostShockZoneStatus(str, Enum):
  """Outcome for a post-shock characteristic zone assembly."""

  CONVERGED_OPEN = 'converged_open'
  INVALID_INPUT = 'invalid_input'
  GEOMETRY_FAILURE = 'geometry_failure'
  TOPOLOGY_FAILURE = 'topology_failure'
  INVARIANT_FAILURE = 'invariant_failure'
####


class MocPostShockClosureStatus(str, Enum):
  """Outcome for the physical closed-field acceptance gate."""

  CONVERGED_CLOSED = 'converged_closed'
  INVALID_INPUT = 'invalid_input'
  SHOCK_FIT_REQUIRED = 'shock_fit_required'
  GEOMETRY_FAILURE = 'geometry_failure'
  TOPOLOGY_FAILURE = 'topology_failure'
  INVARIANT_FAILURE = 'invariant_failure'
####


class MocShockBoundaryFitStatus(str, Enum):
  """Outcome for a sampled attached-shock boundary fit."""

  CONVERGED_FITTED = 'converged_fitted'
  INVALID_INPUT = 'invalid_input'
  OUTSIDE_DOMAIN = 'outside_domain'
  GEOMETRY_FAILURE = 'geometry_failure'
  INVARIANT_FAILURE = 'invariant_failure'
####


@dataclass(frozen=True, slots=True)
class MocPostShockBoundaryState:
  """One downstream state sampled on an ordered shock boundary.

  Boundary points are supplied from the outer shock attachment toward the
  centerline intersection.  The state is downstream of the shock; the two
  total pressures make the irreversible pressure loss explicit instead of
  silently carrying the upstream stagnation pressure into the continuation.
  """

  point_m: tuple[float, float]
  state: CharacteristicState
  upstream_total_pressure_Pa: float
  downstream_total_pressure_Pa: float

  def __post_init__(self) -> None:
    if len(self.point_m) != 2 or not all(isfinite(float(value)) for value in self.point_m):
      raise ValueError('post-shock boundary point must contain two finite coordinates')
    if not isinstance(self.state, CharacteristicState):
      raise TypeError('post-shock boundary state must be a CharacteristicState')
    for name, value in (
      ('upstream_total_pressure_Pa', self.upstream_total_pressure_Pa),
      ('downstream_total_pressure_Pa', self.downstream_total_pressure_Pa),
    ):
      if not isfinite(float(value)) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
  ####


@dataclass(frozen=True, slots=True)
class MocPostShockCharacteristicSegment:
  """One downstream ``C-`` characteristic from shock to centerline."""

  index: int
  shock_point_m: tuple[float, float]
  centerline_point_m: tuple[float, float]
  shock_state: CharacteristicState
  centerline_state: CharacteristicState
  point_result: CharacteristicPointResult

  @property
  def geometry_residual_m(self) -> float | None:
    return self.point_result.geometry_residual

  @property
  def invariant_residual(self) -> float | None:
    return self.point_result.invariant_residual_minus
####


@dataclass(frozen=True, slots=True)
class MocPostShockContinuationResult:
  """Result of continuing a prescribed downstream shock boundary.

  A converged result is a boundary-conditioned characteristic trace, not a
  fitted shock or a complete first-cell mesh.  The distinction is carried in
  the status name and message so this primitive cannot be mistaken for
  physical closure of the reflected plume lattice.
  """

  status: MocPostShockContinuationStatus
  segments: tuple[MocPostShockCharacteristicSegment, ...]
  centerline_states: tuple[CharacteristicState, ...]
  maximum_geometry_residual_m: float | None
  maximum_absolute_invariant_residual: float | None
  message: str = ''

  @property
  def converged(self) -> bool:
    return self.status is MocPostShockContinuationStatus.CONVERGED_PRESCRIBED_BOUNDARY
####


@dataclass(frozen=True, slots=True)
class MocPostShockCrossCharacteristic:
  """One first-layer intersection of an axis ``C+`` and shock ``C-``."""

  index: int
  axis_source_state: CharacteristicState
  shock_source_state: CharacteristicState
  point_result: CharacteristicPointResult

  @property
  def point_m(self) -> tuple[float, float] | None:
    return self.point_result.point_m
  ####


@dataclass(frozen=True, slots=True)
class MocPostShockFirstLayerResult:
  """First post-shock cross-characteristic layer, without closure promotion.

  This is the next numerical layer after the prescribed ``C-`` traces.  It
  supplies the geometry needed to begin a downstream characteristic field,
  but it intentionally does not claim a complete shock-adjacent cell mesh or
  a physical first-cell closure.
  """

  status: MocPostShockFirstLayerStatus
  crossings: tuple[MocPostShockCrossCharacteristic, ...]
  maximum_geometry_residual_m: float | None
  maximum_absolute_invariant_residual: float | None
  minimum_forward_margin_m: float | None
  message: str = ''

  @property
  def converged(self) -> bool:
    return self.status is MocPostShockFirstLayerStatus.CONVERGED_FIRST_LAYER
  ####


@dataclass(frozen=True, slots=True)
class MocPostShockCharacteristicZoneResult:
  """A downstream characteristic zone grown from the first cross layer.

  The zone is a real compatible characteristic mesh, but its front boundary
  is the first computed cross-characteristic layer rather than a fitted shock.
  Consequently ``CONVERGED_OPEN`` is numerical assembly evidence only; it is
  not a physical first-cell or post-shock closure claim.
  """

  status: MocPostShockZoneStatus
  characteristic_count: int
  nodes: tuple[MocCharacteristicNode, ...]
  cells: tuple[MocCharacteristicCell, ...]
  topology: MocTopologyResult
  maximum_geometry_residual_m: float | None
  maximum_absolute_invariant_residual: float | None
  minimum_forward_margin_m: float | None
  upstream_total_pressure_range_Pa: tuple[float, float] | None
  downstream_total_pressure_range_Pa: tuple[float, float] | None
  minimum_post_shock_total_pressure_ratio: float | None
  maximum_post_shock_total_pressure_ratio: float | None
  physical_closure_status: str
  shock_closure_status: str
  message: str = ''

  @property
  def converged(self) -> bool:
    return self.status is MocPostShockZoneStatus.CONVERGED_OPEN
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


@dataclass(frozen=True, slots=True)
class MocPostShockClosedFieldResult:
  """Acceptance result for a complete, shock-bounded post-shock field.

  The closed-field gate deliberately accepts the candidate nodes and cells
  from a solver rather than synthesizing them from the open first-layer
  assembler.  A valid polygon perimeter is necessary but not sufficient:
  every supplied characteristic node must carry converged compatibility
  evidence, and the fitted shock and centerline sample edges must be present
  as explicit physical boundary edges of the candidate field.
  """

  status: MocPostShockClosureStatus
  nodes: tuple[MocCharacteristicNode, ...]
  cells: tuple[MocCharacteristicCell, ...]
  topology: MocTopologyResult
  shock_boundary_points_m: tuple[tuple[float, float], ...]
  axis_boundary_points_m: tuple[tuple[float, float], ...]
  maximum_geometry_residual_m: float | None
  maximum_absolute_invariant_residual: float | None
  maximum_shock_angle_residual_rad: float | None
  minimum_post_shock_total_pressure_ratio: float | None
  maximum_post_shock_total_pressure_ratio: float | None
  message: str = ''

  @property
  def converged(self) -> bool:
    return self.status is MocPostShockClosureStatus.CONVERGED_CLOSED
  ####

  @property
  def physical_closure_verified(self) -> bool:
    return self.converged
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

  def as_chain_cell(
    self,
    *,
    start_x_m: float,
    end_x_m: float,
    cell_index: int = 1,
    diagnostics: dict[str, Any] | None = None,
  ) -> MocChainCell:
    """Promote verified field evidence into a resolved-MOC chain seed.

    An open or failed field can never be promoted through this adapter.
    """

    if not self.converged:
      raise ValueError(
        'only a converged closed post-shock field can become a chain cell'
      )
    chain_diagnostics: dict[str, Any] = {
      'source': 'validated-closed-post-shock-field',
      'physical_closure_verified': True,
      'node_count': self.node_count,
      'cell_count': self.cell_count,
      'maximum_geometry_residual_m': self.maximum_geometry_residual_m,
      'maximum_absolute_invariant_residual': self.maximum_absolute_invariant_residual,
      'maximum_shock_angle_residual_rad': self.maximum_shock_angle_residual_rad,
      'minimum_post_shock_total_pressure_ratio': self.minimum_post_shock_total_pressure_ratio,
      'maximum_post_shock_total_pressure_ratio': self.maximum_post_shock_total_pressure_ratio,
    }
    if diagnostics is not None:
      chain_diagnostics.update(diagnostics)
    return MocChainCell(
      cell_index=cell_index,
      start_x_m=start_x_m,
      end_x_m=end_x_m,
      mesh=self.cells,
      geometry_fidelity=MocChainGeometryFidelity.RESOLVED_PLANAR_MOC,
      physical_closure=MocCellClosureStatus.CLOSED,
      diagnostics=chain_diagnostics,
    )
  ####


@dataclass(frozen=True, slots=True)
class MocShockBoundaryFitResult:
  """A sampled, branch-checked attached shock and its downstream states."""

  status: MocShockBoundaryFitStatus
  boundary_states: tuple[MocPostShockBoundaryState, ...]
  shock_angle_residuals_rad: tuple[float, ...]
  maximum_shock_angle_residual_rad: float | None
  message: str = ''

  @property
  def converged(self) -> bool:
    return self.status is MocShockBoundaryFitStatus.CONVERGED_FITTED
  ####


def _shock_fit_failure(
    status: MocShockBoundaryFitStatus,
    *,
    boundary_states: tuple[MocPostShockBoundaryState, ...] = (),
    residuals: tuple[float, ...] = (),
    message: str,
) -> MocShockBoundaryFitResult:
  return MocShockBoundaryFitResult(
    status=status,
    boundary_states=boundary_states,
    shock_angle_residuals_rad=residuals,
    maximum_shock_angle_residual_rad=max(
      (abs(value) for value in residuals),
      default=None,
    ),
    message=message,
  )


def _wrapped_angle_difference(first: float, second: float) -> float:
  difference = float(first) - float(second)
  while difference > pi:
    difference -= 2.0 * pi
  while difference < -pi:
    difference += 2.0 * pi
  return difference


def fit_attached_shock_boundary(
    upstream_states: Sequence[CharacteristicState],
    upstream_pressure_Pa: Sequence[float],
    shock_points_m: Sequence[tuple[float, float]],
    downstream_flow_angles_rad: Sequence[float],
    *,
    branch: ShockBranch = ShockBranch.WEAK,
    position_tolerance_m: float = 1.0e-10,
    shock_angle_tolerance_rad: float = 1.0e-8,
) -> MocShockBoundaryFitResult:
  """Fit downstream attached states to an explicitly sampled shock curve.

  The geometry is supplied, never invented: each upstream state must be
  located on its corresponding shock sample, and the local tangent must agree
  with the attached oblique-shock angle returned for the requested downstream
  turn.  This is the deterministic boundary contract needed by the post-shock
  field assembler; it is not an automatic free-boundary shock finder.
  """

  samples = tuple(upstream_states)
  pressures = tuple(upstream_pressure_Pa)
  points = tuple(shock_points_m)
  target_angles = tuple(downstream_flow_angles_rad)
  if len(samples) < 2:
    return _shock_fit_failure(
      MocShockBoundaryFitStatus.INVALID_INPUT,
      message='shock boundary fit requires at least two samples',
    )
  if not (len(samples) == len(pressures) == len(points) == len(target_angles)):
    return _shock_fit_failure(
      MocShockBoundaryFitStatus.INVALID_INPUT,
      message='upstream states, pressures, points, and target angles must have equal lengths',
    )
  if not isinstance(branch, ShockBranch):
    return _shock_fit_failure(
      MocShockBoundaryFitStatus.INVALID_INPUT,
      message='branch must be a ShockBranch',
    )
  for name, value in (
    ('position_tolerance_m', position_tolerance_m),
    ('shock_angle_tolerance_rad', shock_angle_tolerance_rad),
  ):
    if not isfinite(float(value)) or value <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
  if not all(isinstance(state, CharacteristicState) for state in samples):
    return _shock_fit_failure(
      MocShockBoundaryFitStatus.INVALID_INPUT,
      message='upstream_states must contain CharacteristicState values',
    )
  gamma = samples[0].gamma
  previous_point: tuple[float, float] | None = None
  for index, (state, pressure, point, target_angle) in enumerate(
      zip(samples, pressures, points, target_angles, strict=True)
  ):
    if abs(state.gamma - gamma) > shock_angle_tolerance_rad:
      return _shock_fit_failure(
        MocShockBoundaryFitStatus.INVALID_INPUT,
        message=f'shock sample {index} uses a different gamma',
      )
    if len(point) != 2 or not all(isfinite(float(value)) for value in point):
      return _shock_fit_failure(
        MocShockBoundaryFitStatus.INVALID_INPUT,
        message=f'shock sample {index} has a non-finite point',
      )
    if abs(state.x_m - point[0]) > position_tolerance_m or abs(state.y_m - point[1]) > position_tolerance_m:
      return _shock_fit_failure(
        MocShockBoundaryFitStatus.INVALID_INPUT,
        message=f'upstream state {index} does not lie on its shock sample',
      )
    if not isfinite(float(pressure)) or pressure <= 0.0:
      return _shock_fit_failure(
        MocShockBoundaryFitStatus.INVALID_INPUT,
        message=f'upstream pressure {index} must be finite and positive',
      )
    if not isfinite(float(target_angle)):
      return _shock_fit_failure(
        MocShockBoundaryFitStatus.INVALID_INPUT,
        message=f'downstream flow angle {index} must be finite',
      )
    if previous_point is not None:
      dx = float(point[0]) - previous_point[0]
      dy = float(point[1]) - previous_point[1]
      if dx <= position_tolerance_m or dy > position_tolerance_m:
        return _shock_fit_failure(
          MocShockBoundaryFitStatus.INVALID_INPUT,
          message=(
            'shock samples must be strictly downstream in x and nonincreasing '
            'in y'
          ),
        )
    previous_point = (float(point[0]), float(point[1]))
  ####

  fitted: list[MocPostShockBoundaryState] = []
  angle_residuals: list[float] = []
  for index, (state, pressure, point, target_angle) in enumerate(
      zip(samples, pressures, points, target_angles, strict=True)
  ):
    target_turn = float(target_angle) - state.theta_rad
    if target_turn <= 0.0:
      return _shock_fit_failure(
        MocShockBoundaryFitStatus.OUTSIDE_DOMAIN,
        boundary_states=tuple(fitted),
        residuals=tuple(angle_residuals),
        message=f'shock sample {index} does not require a positive compression turn',
      )
    compression = solve_attached_compression_to_turn(
      upstream_mach=state.mach,
      gamma=state.gamma,
      upstream_pressure_Pa=float(pressure),
      target_turn_rad=target_turn,
      branch=branch,
    )
    if (
      not compression.converged
      or compression.beta_rad is None
      or compression.downstream_mach is None
      or compression.upstream_total_pressure_Pa is None
      or compression.downstream_total_pressure_Pa is None
    ):
      status = (
        MocShockBoundaryFitStatus.INVARIANT_FAILURE
        if compression.status is MocPrimitiveStatus.INVARIANT_FAILURE
        else MocShockBoundaryFitStatus.OUTSIDE_DOMAIN
      )
      return _shock_fit_failure(
        status,
        boundary_states=tuple(fitted),
        residuals=tuple(angle_residuals),
        message=f'shock sample {index} failed attached compression: {compression.message}',
      )
    if index == 0:
      tangent_dx = points[1][0] - points[0][0]
      tangent_dy = points[1][1] - points[0][1]
    elif index == len(points) - 1:
      tangent_dx = points[-1][0] - points[-2][0]
      tangent_dy = points[-1][1] - points[-2][1]
    else:
      tangent_dx = points[index + 1][0] - points[index - 1][0]
      tangent_dy = points[index + 1][1] - points[index - 1][1]
    tangent_angle = atan2(tangent_dy, tangent_dx)
    shock_angle = state.theta_rad - compression.beta_rad
    angle_residual = _wrapped_angle_difference(tangent_angle, shock_angle)
    angle_residuals.append(angle_residual)
    if abs(angle_residual) > shock_angle_tolerance_rad:
      return _shock_fit_failure(
        MocShockBoundaryFitStatus.GEOMETRY_FAILURE,
        boundary_states=tuple(fitted),
        residuals=tuple(angle_residuals),
        message=(
          f'shock sample {index} tangent disagrees with attached shock angle '
          f'by {angle_residual}'
        ),
      )
    fitted.append(
      MocPostShockBoundaryState(
        point_m=(float(point[0]), float(point[1])),
        state=CharacteristicState(
          x_m=float(point[0]),
          y_m=float(point[1]),
          theta_rad=float(target_angle),
          mach=float(compression.downstream_mach),
          gamma=state.gamma,
        ),
        upstream_total_pressure_Pa=float(compression.upstream_total_pressure_Pa),
        downstream_total_pressure_Pa=float(compression.downstream_total_pressure_Pa),
      )
    )
  ####

  return MocShockBoundaryFitResult(
    status=MocShockBoundaryFitStatus.CONVERGED_FITTED,
    boundary_states=tuple(fitted),
    shock_angle_residuals_rad=tuple(angle_residuals),
    maximum_shock_angle_residual_rad=max(
      (abs(value) for value in angle_residuals),
      default=None,
    ),
  )
####


def _closed_field_failure(
  status: MocPostShockClosureStatus,
  *,
  nodes: tuple[MocCharacteristicNode, ...] = (),
  cells: tuple[MocCharacteristicCell, ...] = (),
  topology: MocTopologyResult | None = None,
  shock_boundary_points: tuple[tuple[float, float], ...] = (),
  axis_boundary_points: tuple[tuple[float, float], ...] = (),
  maximum_geometry_residual_m: float | None = None,
  maximum_absolute_invariant_residual: float | None = None,
  maximum_shock_angle_residual_rad: float | None = None,
  pressure_ratios: tuple[float, ...] = (),
  message: str,
) -> MocPostShockClosedFieldResult:
  return MocPostShockClosedFieldResult(
    status=status,
    nodes=nodes,
    cells=cells,
    topology=validate_moc_mesh(()) if topology is None else topology,
    shock_boundary_points_m=shock_boundary_points,
    axis_boundary_points_m=axis_boundary_points,
    maximum_geometry_residual_m=maximum_geometry_residual_m,
    maximum_absolute_invariant_residual=maximum_absolute_invariant_residual,
    maximum_shock_angle_residual_rad=maximum_shock_angle_residual_rad,
    minimum_post_shock_total_pressure_ratio=min(pressure_ratios, default=None),
    maximum_post_shock_total_pressure_ratio=max(pressure_ratios, default=None),
    message=message,
  )


def _mesh_edge_counts(
  cells: Sequence[MocCharacteristicCell],
  *,
  position_tolerance_m: float,
) -> dict[tuple[tuple[int, int], tuple[int, int]], int]:
  edge_counts: dict[tuple[tuple[int, int], tuple[int, int]], int] = {}
  for cell in cells:
    keys = tuple(
      (
        round(float(point[0]) / position_tolerance_m),
        round(float(point[1]) / position_tolerance_m),
      )
      for point in cell.vertices_xr_m
    )
    for first, second in zip(keys, (*keys[1:], keys[0])):
      edge = (first, second) if first <= second else (second, first)
      edge_counts[edge] = edge_counts.get(edge, 0) + 1
  return edge_counts


def _mesh_edge_key(
  first: tuple[float, float],
  second: tuple[float, float],
  *,
  position_tolerance_m: float,
) -> tuple[tuple[int, int], tuple[int, int]]:
  first_key = (
    round(float(first[0]) / position_tolerance_m),
    round(float(first[1]) / position_tolerance_m),
  )
  second_key = (
    round(float(second[0]) / position_tolerance_m),
    round(float(second[1]) / position_tolerance_m),
  )
  return (first_key, second_key) if first_key <= second_key else (second_key, first_key)


def validate_closed_post_shock_field(
  continuation: MocPostShockContinuationResult,
  shock_fit: MocShockBoundaryFitResult,
  nodes: Sequence[MocCharacteristicNode],
  cells: Sequence[MocCharacteristicCell],
  *,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  shock_angle_tolerance_rad: float = 1.0e-8,
) -> MocPostShockClosedFieldResult:
  """Validate a solver-supplied closed post-shock characteristic field.

  ``assemble_post_shock_characteristic_zone`` intentionally stops at an
  interior first-layer front.  This gate is the promotion boundary for a
  later full solver: it will only return ``CONVERGED_CLOSED`` when candidate
  cells explicitly contain the sampled shock and centerline boundary edges,
  form one connected finite mesh, and carry converged characteristic-node
  evidence.  It never fills missing cells or relabels the open assembler.
  """

  if not isinstance(continuation, MocPostShockContinuationResult):
    return _closed_field_failure(
      MocPostShockClosureStatus.INVALID_INPUT,
      message='continuation must be a MocPostShockContinuationResult',
    )
  if not isinstance(shock_fit, MocShockBoundaryFitResult):
    return _closed_field_failure(
      MocPostShockClosureStatus.INVALID_INPUT,
      message='shock_fit must be a MocShockBoundaryFitResult',
    )
  if not isfinite(float(position_tolerance_m)) or position_tolerance_m <= 0.0:
    raise ValueError('position_tolerance_m must be finite and positive')
  if not isfinite(float(invariant_tolerance)) or invariant_tolerance <= 0.0:
    raise ValueError('invariant_tolerance must be finite and positive')
  if not isfinite(float(shock_angle_tolerance_rad)) or shock_angle_tolerance_rad <= 0.0:
    raise ValueError('shock_angle_tolerance_rad must be finite and positive')
  if not continuation.converged:
    return _closed_field_failure(
      MocPostShockClosureStatus.INVALID_INPUT,
      message=f'continuation is not converged: {continuation.message}',
    )
  if not shock_fit.converged:
    return _closed_field_failure(
      MocPostShockClosureStatus.SHOCK_FIT_REQUIRED,
      message=f'closed post-shock validation requires a converged shock fit: {shock_fit.message}',
    )
  if len(shock_fit.boundary_states) != len(continuation.segments):
    return _closed_field_failure(
      MocPostShockClosureStatus.INVALID_INPUT,
      message='shock-fit samples must match post-shock continuation segments',
    )
  if len(shock_fit.boundary_states) < 2:
    return _closed_field_failure(
      MocPostShockClosureStatus.INVALID_INPUT,
      message='closed post-shock validation requires at least two shock samples',
    )
  ####

  shock_states = shock_fit.boundary_states
  shock_points = tuple(sample.point_m for sample in shock_states)
  axis_points = tuple(segment.centerline_point_m for segment in continuation.segments)
  pressure_ratios = tuple(
    sample.downstream_total_pressure_Pa / sample.upstream_total_pressure_Pa
    for sample in shock_states
  )
  maximum_angle_residual = shock_fit.maximum_shock_angle_residual_rad
  if (
    maximum_angle_residual is None
    or maximum_angle_residual > shock_angle_tolerance_rad
  ):
    return _closed_field_failure(
      MocPostShockClosureStatus.GEOMETRY_FAILURE,
      shock_boundary_points=shock_points,
      axis_boundary_points=axis_points,
      maximum_shock_angle_residual_rad=maximum_angle_residual,
      pressure_ratios=pressure_ratios,
      message='shock-fit tangent residual exceeds the closed-field tolerance',
    )
  if any(ratio <= 0.0 or ratio >= 1.0 for ratio in pressure_ratios):
    return _closed_field_failure(
      MocPostShockClosureStatus.INVARIANT_FAILURE,
      shock_boundary_points=shock_points,
      axis_boundary_points=axis_points,
      maximum_shock_angle_residual_rad=maximum_angle_residual,
      pressure_ratios=pressure_ratios,
      message='closed post-shock field requires strict positive total-pressure loss at every shock sample',
    )
  ####

  for index, (sample, segment) in enumerate(zip(shock_states, continuation.segments, strict=True)):
    if (
      abs(sample.point_m[0] - segment.shock_point_m[0]) > position_tolerance_m
      or abs(sample.point_m[1] - segment.shock_point_m[1]) > position_tolerance_m
      or abs(sample.state.x_m - segment.shock_state.x_m) > position_tolerance_m
      or abs(sample.state.y_m - segment.shock_state.y_m) > position_tolerance_m
      or abs(sample.state.theta_rad - segment.shock_state.theta_rad) > invariant_tolerance
      or abs(sample.state.mach - segment.shock_state.mach) > invariant_tolerance
      or abs(sample.state.gamma - segment.shock_state.gamma) > invariant_tolerance
    ):
      return _closed_field_failure(
        MocPostShockClosureStatus.GEOMETRY_FAILURE,
        shock_boundary_points=shock_points,
        axis_boundary_points=axis_points,
        maximum_shock_angle_residual_rad=maximum_angle_residual,
        pressure_ratios=pressure_ratios,
        message=f'shock-fit sample {index} does not match its continuation segment',
      )
  if any(abs(point[1]) > position_tolerance_m for point in axis_points):
    return _closed_field_failure(
      MocPostShockClosureStatus.GEOMETRY_FAILURE,
      shock_boundary_points=shock_points,
      axis_boundary_points=axis_points,
      maximum_shock_angle_residual_rad=maximum_angle_residual,
      pressure_ratios=pressure_ratios,
      message='continuation centerline samples must lie on the symmetry line',
    )
  if any(
    ((right[0] - left[0]) ** 2 + (right[1] - left[1]) ** 2) ** 0.5
    <= position_tolerance_m
    for left, right in zip(axis_points, axis_points[1:])
  ):
    return _closed_field_failure(
      MocPostShockClosureStatus.GEOMETRY_FAILURE,
      shock_boundary_points=shock_points,
      axis_boundary_points=axis_points,
      maximum_shock_angle_residual_rad=maximum_angle_residual,
      pressure_ratios=pressure_ratios,
      message='centerline boundary samples must be distinct',
    )
  ####

  node_values = tuple(nodes)
  cell_values = tuple(cells)
  if not node_values:
    return _closed_field_failure(
      MocPostShockClosureStatus.INVALID_INPUT,
      shock_boundary_points=shock_points,
      axis_boundary_points=axis_points,
      maximum_shock_angle_residual_rad=maximum_angle_residual,
      pressure_ratios=pressure_ratios,
      message='closed post-shock validation requires characteristic nodes',
    )
  if not all(isinstance(node, MocCharacteristicNode) for node in node_values):
    return _closed_field_failure(
      MocPostShockClosureStatus.INVALID_INPUT,
      shock_boundary_points=shock_points,
      axis_boundary_points=axis_points,
      maximum_shock_angle_residual_rad=maximum_angle_residual,
      pressure_ratios=pressure_ratios,
      message='nodes must contain MocCharacteristicNode values',
    )
  if not cell_values or not all(isinstance(cell, MocCharacteristicCell) for cell in cell_values):
    return _closed_field_failure(
      MocPostShockClosureStatus.INVALID_INPUT,
      nodes=node_values,
      shock_boundary_points=shock_points,
      axis_boundary_points=axis_points,
      maximum_shock_angle_residual_rad=maximum_angle_residual,
      pressure_ratios=pressure_ratios,
      message='cells must contain at least one MocCharacteristicCell value',
    )
  ####

  maximum_geometry_residual = max(
    (
      abs(node.point_result.geometry_residual)
      for node in node_values
      if node.point_result.geometry_residual is not None
    ),
    default=None,
  )
  maximum_invariant_residual = max(
    (
      abs(value)
      for node in node_values
      for value in (
        node.point_result.invariant_residual_plus,
        node.point_result.invariant_residual_minus,
      )
      if value is not None
    ),
    default=None,
  )
  node_keys: set[tuple[int, int]] = set()
  for index, node in enumerate(node_values):
    point_result = node.point_result
    if not point_result.converged or point_result.point_m is None or point_result.state is None:
      return _closed_field_failure(
        MocPostShockClosureStatus.INVARIANT_FAILURE,
        nodes=node_values,
        cells=cell_values,
        shock_boundary_points=shock_points,
        axis_boundary_points=axis_points,
        maximum_geometry_residual_m=maximum_geometry_residual,
        maximum_absolute_invariant_residual=maximum_invariant_residual,
        maximum_shock_angle_residual_rad=maximum_angle_residual,
        pressure_ratios=pressure_ratios,
        message=f'characteristic node {index} does not carry converged compatibility evidence',
      )
    if (
      abs(node.point_m[0] - point_result.point_m[0]) > position_tolerance_m
      or abs(node.point_m[1] - point_result.point_m[1]) > position_tolerance_m
      or abs(node.state.x_m - node.point_m[0]) > position_tolerance_m
      or abs(node.state.y_m - node.point_m[1]) > position_tolerance_m
    ):
      return _closed_field_failure(
        MocPostShockClosureStatus.GEOMETRY_FAILURE,
        nodes=node_values,
        cells=cell_values,
        shock_boundary_points=shock_points,
        axis_boundary_points=axis_points,
        maximum_geometry_residual_m=maximum_geometry_residual,
        maximum_absolute_invariant_residual=maximum_invariant_residual,
        maximum_shock_angle_residual_rad=maximum_angle_residual,
        pressure_ratios=pressure_ratios,
        message=f'characteristic node {index} has inconsistent coordinates',
      )
    if any(
      value is not None and abs(value) > invariant_tolerance
      for value in (
        point_result.invariant_residual_plus,
        point_result.invariant_residual_minus,
      )
    ):
      return _closed_field_failure(
        MocPostShockClosureStatus.INVARIANT_FAILURE,
        nodes=node_values,
        cells=cell_values,
        shock_boundary_points=shock_points,
        axis_boundary_points=axis_points,
        maximum_geometry_residual_m=maximum_geometry_residual,
        maximum_absolute_invariant_residual=maximum_invariant_residual,
        maximum_shock_angle_residual_rad=maximum_angle_residual,
        pressure_ratios=pressure_ratios,
        message=f'characteristic node {index} exceeds invariant tolerance',
      )
    node_keys.add(
      (
        round(node.point_m[0] / position_tolerance_m),
        round(node.point_m[1] / position_tolerance_m),
      )
    )
  ####

  topology = validate_moc_mesh(cell_values)
  if not topology.connected or not topology.forms_closed_zone or topology.nonmanifold_edge_count:
    return _closed_field_failure(
      MocPostShockClosureStatus.TOPOLOGY_FAILURE,
      nodes=node_values,
      cells=cell_values,
      topology=topology,
      shock_boundary_points=shock_points,
      axis_boundary_points=axis_points,
      maximum_geometry_residual_m=maximum_geometry_residual,
      maximum_absolute_invariant_residual=maximum_invariant_residual,
      maximum_shock_angle_residual_rad=maximum_angle_residual,
      pressure_ratios=pressure_ratios,
      message=f'closed post-shock candidate topology failed: {topology.message}',
    )
  edge_counts = _mesh_edge_counts(
    cell_values,
    position_tolerance_m=position_tolerance_m,
  )
  cell_vertex_keys = {
    (
      round(float(point[0]) / position_tolerance_m),
      round(float(point[1]) / position_tolerance_m),
    )
    for cell in cell_values
    for point in cell.vertices_xr_m
  }
  if not node_keys <= cell_vertex_keys:
    return _closed_field_failure(
      MocPostShockClosureStatus.GEOMETRY_FAILURE,
      nodes=node_values,
      cells=cell_values,
      topology=topology,
      shock_boundary_points=shock_points,
      axis_boundary_points=axis_points,
      maximum_geometry_residual_m=maximum_geometry_residual,
      maximum_absolute_invariant_residual=maximum_invariant_residual,
      maximum_shock_angle_residual_rad=maximum_angle_residual,
      pressure_ratios=pressure_ratios,
      message='every characteristic node must be represented by a candidate cell vertex',
    )
  ####

  missing_shock_edges = [
    index
    for index, (first, second) in enumerate(zip(shock_points, shock_points[1:]))
    if _mesh_edge_key(first, second, position_tolerance_m=position_tolerance_m) not in edge_counts
    or edge_counts[_mesh_edge_key(first, second, position_tolerance_m=position_tolerance_m)] != 1
  ]
  if missing_shock_edges:
    return _closed_field_failure(
      MocPostShockClosureStatus.GEOMETRY_FAILURE,
      nodes=node_values,
      cells=cell_values,
      topology=topology,
      shock_boundary_points=shock_points,
      axis_boundary_points=axis_points,
      maximum_geometry_residual_m=maximum_geometry_residual,
      maximum_absolute_invariant_residual=maximum_invariant_residual,
      maximum_shock_angle_residual_rad=maximum_angle_residual,
      pressure_ratios=pressure_ratios,
      message=f'candidate field is missing explicit shock boundary edge(s): {missing_shock_edges}',
    )
  missing_axis_edges = [
    index
    for index, (first, second) in enumerate(zip(axis_points, axis_points[1:]))
    if _mesh_edge_key(first, second, position_tolerance_m=position_tolerance_m) not in edge_counts
    or edge_counts[_mesh_edge_key(first, second, position_tolerance_m=position_tolerance_m)] != 1
  ]
  if missing_axis_edges:
    return _closed_field_failure(
      MocPostShockClosureStatus.GEOMETRY_FAILURE,
      nodes=node_values,
      cells=cell_values,
      topology=topology,
      shock_boundary_points=shock_points,
      axis_boundary_points=axis_points,
      maximum_geometry_residual_m=maximum_geometry_residual,
      maximum_absolute_invariant_residual=maximum_invariant_residual,
      maximum_shock_angle_residual_rad=maximum_angle_residual,
      pressure_ratios=pressure_ratios,
      message=f'candidate field is missing explicit centerline boundary edge(s): {missing_axis_edges}',
    )
  return _closed_field_failure(
    MocPostShockClosureStatus.CONVERGED_CLOSED,
    nodes=node_values,
    cells=cell_values,
    topology=topology,
    shock_boundary_points=shock_points,
    axis_boundary_points=axis_points,
    maximum_geometry_residual_m=maximum_geometry_residual,
    maximum_absolute_invariant_residual=maximum_invariant_residual,
    maximum_shock_angle_residual_rad=maximum_angle_residual,
    pressure_ratios=pressure_ratios,
    message=(
      'closed post-shock characteristic field verified with explicit shock '
      'and centerline boundary edges'
    ),
  )
####


def _first_layer_failure(
    status: MocPostShockFirstLayerStatus,
    *,
    crossings: tuple[MocPostShockCrossCharacteristic, ...] = (),
    message: str,
) -> MocPostShockFirstLayerResult:
  return MocPostShockFirstLayerResult(
    status=status,
    crossings=crossings,
    maximum_geometry_residual_m=max(
      (
        abs(crossing.point_result.geometry_residual)
        for crossing in crossings
        if crossing.point_result.geometry_residual is not None
      ),
      default=None,
    ),
    maximum_absolute_invariant_residual=max(
      (
        max(
          abs(value)
          for value in (
            crossing.point_result.invariant_residual_plus,
            crossing.point_result.invariant_residual_minus,
          )
          if value is not None
        )
        for crossing in crossings
        if crossing.point_result.invariant_residual_plus is not None
        or crossing.point_result.invariant_residual_minus is not None
      ),
      default=None,
    ),
    minimum_forward_margin_m=min(
      (
        crossing.point_result.point_m[0] - max(
          crossing.axis_source_state.x_m,
          crossing.shock_source_state.x_m,
        )
        for crossing in crossings
        if crossing.point_result.point_m is not None
      ),
      default=None,
    ),
    message=message,
  )


def _post_shock_zone_result(
    status: MocPostShockZoneStatus,
    *,
    characteristic_count: int,
    nodes: tuple[MocCharacteristicNode, ...] = (),
    cells: tuple[MocCharacteristicCell, ...] = (),
    topology: MocTopologyResult | None = None,
    crossings: tuple[MocPostShockCrossCharacteristic, ...] = (),
    pressure_ranges: tuple[tuple[float, float], tuple[float, float]] | None = None,
    pressure_ratios: tuple[float, ...] = (),
    message: str,
) -> MocPostShockCharacteristicZoneResult:
  point_results = [node.point_result for node in nodes]
  point_results.extend(crossing.point_result for crossing in crossings)
  upstream_range: tuple[float, float] | None = None
  downstream_range: tuple[float, float] | None = None
  minimum_ratio: float | None = None
  maximum_ratio: float | None = None
  if pressure_ranges is not None:
    upstream_range, downstream_range = pressure_ranges
    if pressure_ratios:
      minimum_ratio = min(pressure_ratios)
      maximum_ratio = max(pressure_ratios)
  return MocPostShockCharacteristicZoneResult(
    status=status,
    characteristic_count=characteristic_count,
    nodes=nodes,
    cells=cells,
    topology=validate_moc_mesh(()) if topology is None else topology,
    maximum_geometry_residual_m=max(
      (
        abs(point_result.geometry_residual)
        for point_result in point_results
        if point_result.geometry_residual is not None
      ),
      default=None,
    ),
    maximum_absolute_invariant_residual=max(
      (
        max(
          abs(value)
          for value in (
            point_result.invariant_residual_plus,
            point_result.invariant_residual_minus,
          )
          if value is not None
        )
        for point_result in point_results
        if point_result.invariant_residual_plus is not None
        or point_result.invariant_residual_minus is not None
      ),
      default=None,
    ),
    minimum_forward_margin_m=min(
      (
        crossing.point_result.point_m[0] - max(
          crossing.axis_source_state.x_m,
          crossing.shock_source_state.x_m,
        )
        for crossing in crossings
        if crossing.point_result.point_m is not None
      ),
      default=None,
    ),
    upstream_total_pressure_range_Pa=upstream_range,
    downstream_total_pressure_range_Pa=downstream_range,
    minimum_post_shock_total_pressure_ratio=minimum_ratio,
    maximum_post_shock_total_pressure_ratio=maximum_ratio,
    physical_closure_status='open',
    shock_closure_status='prescribed-boundary-first-layer',
    message=message,
  )


def assemble_post_shock_characteristic_zone(
    continuation: MocPostShockContinuationResult,
    first_layer: MocPostShockFirstLayerResult,
    boundary_states: Sequence[MocPostShockBoundaryState],
    *,
    position_tolerance_m: float = 1.0e-10,
    invariant_tolerance: float = 1.0e-10,
) -> MocPostShockCharacteristicZoneResult:
  """Assemble a compatible post-shock zone from the first cross layer.

  The input samples are an ordered shock-side downstream boundary.  The
  routine uses the next centerline source and current shock source for the
  diagonal of a triangular characteristic lattice, then assembles axis,
  interior, and first-layer strips.  This produces a connected numerical
  zone and retains total-pressure-loss bookkeeping, but the first-layer front
  is not a fitted physical shock and therefore the returned physical closure
  remains open.
  """

  if not isinstance(continuation, MocPostShockContinuationResult):
    return _post_shock_zone_result(
      MocPostShockZoneStatus.INVALID_INPUT,
      characteristic_count=0,
      message='continuation must be a MocPostShockContinuationResult',
    )
  if not isinstance(first_layer, MocPostShockFirstLayerResult):
    return _post_shock_zone_result(
      MocPostShockZoneStatus.INVALID_INPUT,
      characteristic_count=0,
      message='first_layer must be a MocPostShockFirstLayerResult',
    )
  if not isfinite(float(position_tolerance_m)) or position_tolerance_m <= 0.0:
    raise ValueError('position_tolerance_m must be finite and positive')
  if not isfinite(float(invariant_tolerance)) or invariant_tolerance <= 0.0:
    raise ValueError('invariant_tolerance must be finite and positive')
  if not continuation.converged or not first_layer.converged:
    return _post_shock_zone_result(
      MocPostShockZoneStatus.INVALID_INPUT,
      characteristic_count=0,
      message='post-shock zone requires converged prescribed traces and first layer',
    )
  samples = tuple(boundary_states)
  if len(samples) != len(continuation.segments):
    return _post_shock_zone_result(
      MocPostShockZoneStatus.INVALID_INPUT,
      characteristic_count=0,
      message='boundary sample count must match post-shock continuation segments',
    )
  if len(first_layer.crossings) != len(samples) - 1 or len(samples) < 4:
    return _post_shock_zone_result(
      MocPostShockZoneStatus.INVALID_INPUT,
      characteristic_count=max(0, len(first_layer.crossings) - 1),
      message='post-shock zone requires at least four ordered boundary samples',
    )
  if not all(isinstance(sample, MocPostShockBoundaryState) for sample in samples):
    return _post_shock_zone_result(
      MocPostShockZoneStatus.INVALID_INPUT,
      characteristic_count=0,
      message='boundary_states must contain MocPostShockBoundaryState values',
    )
  ####

  for index, (sample, segment) in enumerate(zip(samples, continuation.segments, strict=True)):
    if (
      abs(sample.point_m[0] - segment.shock_point_m[0]) > position_tolerance_m
      or abs(sample.point_m[1] - segment.shock_point_m[1]) > position_tolerance_m
      or abs(sample.state.x_m - segment.shock_state.x_m) > position_tolerance_m
      or abs(sample.state.y_m - segment.shock_state.y_m) > position_tolerance_m
    ):
      return _post_shock_zone_result(
        MocPostShockZoneStatus.INVALID_INPUT,
        characteristic_count=0,
        message=f'boundary sample {index} does not match its continuation segment',
      )
  upstream_values = tuple(sample.upstream_total_pressure_Pa for sample in samples)
  downstream_values = tuple(sample.downstream_total_pressure_Pa for sample in samples)
  pressure_ranges = (
    (min(upstream_values), max(upstream_values)),
    (min(downstream_values), max(downstream_values)),
  )
  pressure_ratios = tuple(
    downstream / upstream
    for upstream, downstream in zip(upstream_values, downstream_values, strict=True)
  )
  ####

  axis_sources = tuple(segment.centerline_state for segment in continuation.segments[1:])
  shock_sources = tuple(segment.shock_state for segment in continuation.segments[:-1])
  diagonal_points_optional = tuple(crossing.point_m for crossing in first_layer.crossings)
  if any(point is None for point in diagonal_points_optional):
    return _post_shock_zone_result(
      MocPostShockZoneStatus.INVALID_INPUT,
      characteristic_count=max(0, len(axis_sources) - 1),
      crossings=first_layer.crossings,
      pressure_ranges=pressure_ranges,
      pressure_ratios=pressure_ratios,
      message='first-layer crossings must all expose finite points',
    )
  diagonal_points = tuple(
    point for point in diagonal_points_optional if point is not None
  )
  expected_count = len(axis_sources)
  nodes_by_index: dict[tuple[int, int], MocCharacteristicNode] = {}
  for centerline_index in range(expected_count):
    axis_source = axis_sources[centerline_index]
    if abs(axis_source.y_m) > position_tolerance_m or abs(axis_source.theta_rad) > invariant_tolerance:
      return _post_shock_zone_result(
        MocPostShockZoneStatus.INVALID_INPUT,
        characteristic_count=max(0, expected_count - 1),
        pressure_ranges=pressure_ranges,
        pressure_ratios=pressure_ratios,
        message=f'axis source {centerline_index} must satisfy y=0 and theta=0',
      )
    for boundary_index in range(centerline_index + 1):
      point_result = interior_characteristic_point(
        axis_source,
        shock_sources[boundary_index],
        position_tolerance_m=position_tolerance_m,
        invariant_tolerance=invariant_tolerance,
      )
      if not point_result.converged or point_result.state is None or point_result.point_m is None:
        status = (
          MocPostShockZoneStatus.INVARIANT_FAILURE
          if point_result.status is MocPrimitiveStatus.INVARIANT_FAILURE
          else MocPostShockZoneStatus.GEOMETRY_FAILURE
        )
        return _post_shock_zone_result(
          status,
          characteristic_count=max(0, expected_count - 1),
          nodes=tuple(nodes_by_index.values()),
          crossings=first_layer.crossings,
          pressure_ranges=pressure_ranges,
          pressure_ratios=pressure_ratios,
          message=(
            f'post-shock characteristic node ({centerline_index}, '
            f'{boundary_index}) failed: {point_result.message}'
          ),
        )
      point_result_point = point_result.point_m
      if point_result_point is None:
        raise RuntimeError('converged characteristic point did not expose a point')
      point = point_result_point
      if centerline_index == boundary_index:
        diagonal_point = diagonal_points[boundary_index]
        discrepancy = (
          (point[0] - diagonal_point[0]) ** 2
          + (point[1] - diagonal_point[1]) ** 2
        ) ** 0.5
        if discrepancy > position_tolerance_m:
          return _post_shock_zone_result(
            MocPostShockZoneStatus.GEOMETRY_FAILURE,
            characteristic_count=max(0, expected_count - 1),
            nodes=tuple(nodes_by_index.values()),
            crossings=first_layer.crossings,
            pressure_ranges=pressure_ranges,
            pressure_ratios=pressure_ratios,
            message=(
              f'post-shock diagonal node {boundary_index} does not reproduce '
              f'the first-layer point; residual={discrepancy}'
            ),
          )
        point = diagonal_point
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
    state = axis_sources[index]
    return state.x_m, 0.0

  cells_list: list[MocCharacteristicCell] = []
  try:
    for index in range(expected_count - 1):
      cells_list.append(
        MocCharacteristicCell(
          cell_index=len(cells_list),
          cell_kind='post-shock-axis-strip',
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
            cell_kind='post-shock-interior',
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
          cell_kind='post-shock-first-layer-strip',
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
    return _post_shock_zone_result(
      MocPostShockZoneStatus.GEOMETRY_FAILURE,
      characteristic_count=max(0, expected_count - 1),
      nodes=nodes,
      crossings=first_layer.crossings,
      pressure_ranges=pressure_ranges,
      pressure_ratios=pressure_ratios,
      message=f'post-shock characteristic cell geometry failed: {error}',
    )
  ####

  cells = tuple(cells_list)
  topology = validate_moc_mesh(cells)
  if not topology.connected or not topology.forms_closed_zone or topology.nonmanifold_edge_count:
    return _post_shock_zone_result(
      MocPostShockZoneStatus.TOPOLOGY_FAILURE,
      characteristic_count=max(0, expected_count - 1),
      nodes=nodes,
      cells=cells,
      topology=topology,
      crossings=first_layer.crossings,
      pressure_ranges=pressure_ranges,
      pressure_ratios=pressure_ratios,
      message=f'post-shock characteristic topology failed: {topology.message}',
    )
  return _post_shock_zone_result(
    MocPostShockZoneStatus.CONVERGED_OPEN,
    characteristic_count=expected_count - 1,
    nodes=nodes,
    cells=cells,
    topology=topology,
    crossings=first_layer.crossings,
    pressure_ranges=pressure_ranges,
    pressure_ratios=pressure_ratios,
    message=(
      'post-shock characteristic zone assembled through the first downstream '
      'layer; fitted shock closure and physical first-cell closure remain pending'
    ),
  )
####


def assemble_post_shock_first_layer(
    continuation: MocPostShockContinuationResult,
    *,
    position_tolerance_m: float = 1.0e-10,
    invariant_tolerance: float = 1.0e-10,
) -> MocPostShockFirstLayerResult:
  """Build the first downstream cross-characteristic layer.

  For adjacent prescribed shock samples ``S_i`` and centerline endpoints
  ``A_i``, the next forward layer uses the compatible intersection of ``C+``
  from ``A_{i+1}`` and ``C-`` from ``S_i``.  All points must be forward and
  invariant-compatible.  The resulting layer is a diagnostic building block;
  shock fitting, finite-cell topology, and total-pressure assignment remain
  explicit subsequent gates.
  """

  if not isinstance(continuation, MocPostShockContinuationResult):
    return _first_layer_failure(
      MocPostShockFirstLayerStatus.INVALID_INPUT,
      message='continuation must be a MocPostShockContinuationResult',
    )
  if not isfinite(float(position_tolerance_m)) or position_tolerance_m <= 0.0:
    raise ValueError('position_tolerance_m must be finite and positive')
  if not isfinite(float(invariant_tolerance)) or invariant_tolerance <= 0.0:
    raise ValueError('invariant_tolerance must be finite and positive')
  if not continuation.converged:
    return _first_layer_failure(
      MocPostShockFirstLayerStatus.INVALID_INPUT,
      message=(
        'post-shock first layer requires converged prescribed-boundary '
        f'traces: {continuation.message}'
      ),
    )
  if len(continuation.segments) < 2:
    return _first_layer_failure(
      MocPostShockFirstLayerStatus.INVALID_INPUT,
      message='post-shock first layer requires at least two continuation segments',
    )
  ####

  crossings: list[MocPostShockCrossCharacteristic] = []
  for index in range(len(continuation.segments) - 1):
    current = continuation.segments[index]
    next_segment = continuation.segments[index + 1]
    point_result = interior_characteristic_point(
      next_segment.centerline_state,
      current.shock_state,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
    )
    crossing = MocPostShockCrossCharacteristic(
      index=index,
      axis_source_state=next_segment.centerline_state,
      shock_source_state=current.shock_state,
      point_result=point_result,
    )
    crossings.append(crossing)
    if not point_result.converged or point_result.point_m is None or point_result.state is None:
      status = (
        MocPostShockFirstLayerStatus.INVARIANT_FAILURE
        if point_result.status is MocPrimitiveStatus.INVARIANT_FAILURE
        else MocPostShockFirstLayerStatus.GEOMETRY_FAILURE
      )
      return _first_layer_failure(
        status,
        crossings=tuple(crossings),
        message=f'post-shock cross-characteristic {index} failed: {point_result.message}',
      )
    if point_result.point_m[1] < -position_tolerance_m:
      return _first_layer_failure(
        MocPostShockFirstLayerStatus.GEOMETRY_FAILURE,
        crossings=tuple(crossings),
        message=f'post-shock cross-characteristic {index} crossed below the symmetry line',
      )
    if point_result.point_m[0] <= max(
        next_segment.centerline_state.x_m,
        current.shock_state.x_m,
    ) + position_tolerance_m:
      return _first_layer_failure(
        MocPostShockFirstLayerStatus.GEOMETRY_FAILURE,
        crossings=tuple(crossings),
        message=f'post-shock cross-characteristic {index} has no forward margin',
      )
  ####

  return _first_layer_failure(
    MocPostShockFirstLayerStatus.CONVERGED_FIRST_LAYER,
    crossings=tuple(crossings),
    message=(
      'first downstream post-shock cross-characteristic layer converged; '
      'shock fitting, finite-cell topology, and physical closure remain pending'
    ),
  )
####


def _failure(
    status: MocPostShockContinuationStatus,
    *,
    segments: tuple[MocPostShockCharacteristicSegment, ...] = (),
    centerline_states: tuple[CharacteristicState, ...] = (),
    message: str,
) -> MocPostShockContinuationResult:
  return MocPostShockContinuationResult(
    status=status,
    segments=segments,
    centerline_states=centerline_states,
    maximum_geometry_residual_m=max(
      (abs(segment.geometry_residual_m) for segment in segments if segment.geometry_residual_m is not None),
      default=None,
    ),
    maximum_absolute_invariant_residual=max(
      (abs(segment.invariant_residual) for segment in segments if segment.invariant_residual is not None),
      default=None,
    ),
    message=message,
  )
####


def continue_post_shock_characteristics_to_centerline(
    boundary_states: Sequence[MocPostShockBoundaryState],
    *,
    position_tolerance_m: float = 1.0e-10,
    invariant_tolerance: float = 1.0e-10,
    pressure_tolerance: float = 1.0e-10,
    centerline_angle_tolerance_rad: float = 1.0e-10,
) -> MocPostShockContinuationResult:
  """Continue sampled post-shock states to the symmetry line.

  The sequence must run from the outer shock attachment toward a final
  centerline point.  Every ``C-`` trace is solved independently with exact
  centerline ``theta = 0`` compatibility.  The routine does not interpolate
  missing shock states, fit a shock, or assemble the ``C+`` interior field.
  """

  if len(boundary_states) < 2:
    return _failure(
      MocPostShockContinuationStatus.INVALID_INPUT,
      message='post-shock continuation requires at least two sampled shock states',
    )
  for name, value in (
    ('position_tolerance_m', position_tolerance_m),
    ('invariant_tolerance', invariant_tolerance),
    ('pressure_tolerance', pressure_tolerance),
    ('centerline_angle_tolerance_rad', centerline_angle_tolerance_rad),
  ):
    if not isfinite(float(value)) or value <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
  ####
  samples = tuple(boundary_states)
  if not all(isinstance(sample, MocPostShockBoundaryState) for sample in samples):
    return _failure(
      MocPostShockContinuationStatus.INVALID_INPUT,
      message='post-shock continuation inputs must be MocPostShockBoundaryState values',
    )
  gamma = samples[0].state.gamma
  previous_point: tuple[float, float] | None = None
  for index, sample in enumerate(samples):
    point = sample.point_m
    state = sample.state
    if abs(state.gamma - gamma) > invariant_tolerance:
      return _failure(
        MocPostShockContinuationStatus.INVALID_INPUT,
        message=f'post-shock sample {index} uses a different gamma',
      )
    if abs(state.x_m - point[0]) > position_tolerance_m or abs(state.y_m - point[1]) > position_tolerance_m:
      return _failure(
        MocPostShockContinuationStatus.INVALID_INPUT,
        message=f'post-shock sample {index} state and point coordinates disagree',
      )
    if sample.downstream_total_pressure_Pa >= sample.upstream_total_pressure_Pa * (1.0 - pressure_tolerance):
      return _failure(
        MocPostShockContinuationStatus.INVALID_INPUT,
        message=f'post-shock sample {index} does not record a strict total-pressure loss',
      )
    if point[1] < -position_tolerance_m:
      return _failure(
        MocPostShockContinuationStatus.INVALID_INPUT,
        message=f'post-shock sample {index} lies below the symmetry line',
      )
    if previous_point is not None:
      separation = ((point[0] - previous_point[0]) ** 2 + (point[1] - previous_point[1]) ** 2) ** 0.5
      if separation <= position_tolerance_m:
        return _failure(
          MocPostShockContinuationStatus.INVALID_INPUT,
          message=f'post-shock samples {index - 1} and {index} are coincident',
        )
    previous_point = point
  ####
  terminal = samples[-1]
  if abs(terminal.point_m[1]) > position_tolerance_m:
    return _failure(
      MocPostShockContinuationStatus.INVALID_INPUT,
      message='the final post-shock boundary sample must lie on the symmetry line',
    )
  if abs(terminal.state.theta_rad) > centerline_angle_tolerance_rad:
    return _failure(
      MocPostShockContinuationStatus.INVALID_INPUT,
      message='the final post-shock boundary state must satisfy centerline theta = 0',
    )
  ####
  segments: list[MocPostShockCharacteristicSegment] = []
  centerline_states: list[CharacteristicState] = []
  for index, sample in enumerate(samples):
    point_result = centerline_characteristic_point(
      sample.state,
      CharacteristicFamily.MINUS,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
    )
    if not point_result.converged or point_result.state is None or point_result.point_m is None:
      status = (
        MocPostShockContinuationStatus.INVARIANT_FAILURE
        if point_result.status is MocPrimitiveStatus.INVARIANT_FAILURE
        else MocPostShockContinuationStatus.GEOMETRY_FAILURE
      )
      return _failure(
        status,
        segments=tuple(segments),
        centerline_states=tuple(centerline_states),
        message=f'post-shock C- characteristic {index} failed: {point_result.message}',
      )
    centerline_point = point_result.point_m
    if abs(centerline_point[1]) > position_tolerance_m:
      return _failure(
        MocPostShockContinuationStatus.GEOMETRY_FAILURE,
        segments=tuple(segments),
        centerline_states=tuple(centerline_states),
        message=f'post-shock C- characteristic {index} did not reach y=0',
      )
    if index < len(samples) - 1 and centerline_point[0] <= sample.point_m[0] + position_tolerance_m:
      return _failure(
        MocPostShockContinuationStatus.GEOMETRY_FAILURE,
        segments=tuple(segments),
        centerline_states=tuple(centerline_states),
        message=f'post-shock C- characteristic {index} has no forward centerline endpoint',
      )
    centerline_states.append(point_result.state)
    segments.append(MocPostShockCharacteristicSegment(
      index=index,
      shock_point_m=sample.point_m,
      centerline_point_m=centerline_point,
      shock_state=sample.state,
      centerline_state=point_result.state,
      point_result=point_result,
    ))
  ####
  return MocPostShockContinuationResult(
    status=MocPostShockContinuationStatus.CONVERGED_PRESCRIBED_BOUNDARY,
    segments=tuple(segments),
    centerline_states=tuple(centerline_states),
    maximum_geometry_residual_m=max(
      (abs(segment.geometry_residual_m) for segment in segments if segment.geometry_residual_m is not None),
      default=None,
    ),
    maximum_absolute_invariant_residual=max(
      (abs(segment.invariant_residual) for segment in segments if segment.invariant_residual is not None),
      default=None,
    ),
    message=(
      'prescribed downstream shock-boundary C- traces reached the symmetry line; '
      'shock fitting and the downstream C+ interior field remain unassembled'
    ),
  )
####
