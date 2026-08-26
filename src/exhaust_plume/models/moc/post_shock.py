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
from math import isfinite
from typing import Sequence

from exhaust_plume.models.moc.primitives import (
  CharacteristicFamily,
  CharacteristicPointResult,
  CharacteristicState,
  MocPrimitiveStatus,
  centerline_characteristic_point,
  interior_characteristic_point,
)

__all__ = (
  'MocPostShockBoundaryState',
  'MocPostShockCharacteristicSegment',
  'MocPostShockContinuationResult',
  'MocPostShockContinuationStatus',
  'MocPostShockCrossCharacteristic',
  'MocPostShockFirstLayerResult',
  'MocPostShockFirstLayerStatus',
  'assemble_post_shock_first_layer',
  'continue_post_shock_characteristics_to_centerline',
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
