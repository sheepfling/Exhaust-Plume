"""Bounded outgoing-frontier extraction for entropy-characteristic remeshes.

The continued entropy-characteristic remesh solves a curved terminal ``C-``
edge, but its chain handoff intentionally retains only the two endpoint
states.  This module exposes the solved edge as a diagnostic frontier and
audits a candidate downstream path against that frontier.  It never fills a
gap, extrapolates an upstream state, or turns frontier coverage into physical
shock-cell closure.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Any, Sequence

from exhaust_plume.models.moc.chain import MocChainBoundarySample
from exhaust_plume.models.moc.euler_entropy_characteristic_continuation_remesh import (
  MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshResult,
  MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshEdge,
)
from exhaust_plume.models.moc.primitives import CharacteristicFamily

__all__ = (
  'MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFrontierStatus',
  'MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFrontierResult',
  'MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFrontierCoverageStatus',
  'MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFrontierCoverageResult',
  'extract_euler_ambient_first_wedge_entropy_characteristic_remesh_frontier',
  'audit_euler_ambient_first_wedge_entropy_characteristic_remesh_frontier_path',
)


class MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFrontierStatus(
  str,
  Enum,
):
  """Outcome of extracting the solved outgoing remesh frontier."""

  CONVERGED_BOUNDED_FRONTIER = (
    'converged_bounded_entropy_characteristic_c_minus_frontier'
  )
  INVALID_INPUT = 'invalid_input'
  FRONTIER_UNAVAILABLE = (
    'entropy_characteristic_remesh_outgoing_frontier_unavailable'
  )
  GEOMETRY_FAILURE = (
    'entropy_characteristic_remesh_outgoing_frontier_geometry_failure'
  )
####


class MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFrontierCoverageStatus(
  str,
  Enum,
):
  """Outcome of sampling a candidate path against the bounded frontier."""

  CONVERGED_BOUNDED_PATH = (
    'converged_bounded_entropy_characteristic_frontier_path'
  )
  INVALID_INPUT = 'invalid_input'
  FRONTIER_REQUIRED = 'entropy_characteristic_remesh_frontier_required'
  PATH_GEOMETRY_FAILURE = (
    'entropy_characteristic_remesh_frontier_path_geometry_failure'
  )
  FRONTIER_EXTERIOR = (
    'entropy_characteristic_remesh_frontier_exterior_boundary'
  )
  DOMAIN_GAP = 'entropy_characteristic_remesh_frontier_domain_gap'
  SAMPLER_FAILURE = 'entropy_characteristic_remesh_frontier_sampler_failure'
####


def _state_close(
  actual: Any,
  expected: Any,
  *,
  position_tolerance_m: float,
  state_tolerance: float,
) -> bool:
  return bool(
    hasattr(actual, 'x_m')
    and hasattr(expected, 'x_m')
    and abs(actual.x_m - expected.x_m) <= position_tolerance_m
    and abs(actual.y_m - expected.y_m) <= position_tolerance_m
    and abs(actual.theta_rad - expected.theta_rad) <= state_tolerance
    and abs(actual.mach - expected.mach) <= state_tolerance
    and abs(actual.gamma - expected.gamma) <= state_tolerance
  )
####


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFrontierResult:
  """The exact solved outgoing ``C-`` edge of one bounded remesh."""

  status: MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFrontierStatus
  remesh: (
    MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshResult
    | None
  )
  edge: MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshEdge | None
  samples: tuple[MocChainBoundarySample, ...]
  message: str = ''
  position_tolerance_m: float = 1.0e-8
  state_tolerance: float = 1.0e-8

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFrontierStatus,
    ):
      raise TypeError('status must be a remesh frontier status')
    ####
    if self.remesh is not None and not isinstance(
      self.remesh,
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshResult,
    ):
      raise TypeError('remesh must be a typed continuation remesh or None')
    ####
    if self.edge is not None and not isinstance(
      self.edge,
      MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshEdge,
    ):
      raise TypeError('edge must be a typed remesh edge or None')
    ####
    samples = tuple(self.samples)
    if any(not isinstance(sample, MocChainBoundarySample) for sample in samples):
      raise TypeError('samples must contain MocChainBoundarySample values')
    ####
    if self.edge is None and samples:
      raise ValueError('frontier samples require a resolved edge')
    ####
    if self.edge is not None and len(samples) != len(self.edge.states):
      raise ValueError('frontier samples must match the resolved edge states')
    ####
    for name in ('position_tolerance_m', 'state_tolerance'):
      value = float(getattr(self, name))
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      ####
      object.__setattr__(self, name, value)
    ####
    object.__setattr__(self, 'samples', samples)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status is (
      MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFrontierStatus
      .CONVERGED_BOUNDED_FRONTIER
    )
  ####

  @property
  def sample_count(self) -> int:
    return len(self.samples)
  ####

  @property
  def edge_index(self) -> int | None:
    return None if self.edge is None else self.edge.edge_index
  ####

  @property
  def family(self) -> CharacteristicFamily | None:
    return None if self.edge is None else self.edge.family
  ####

  @property
  def physical_closure_verified(self) -> bool:
    return False
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    return True
  ####

  @property
  def production_claim_allowed(self) -> bool:
    return False
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'edge_index': self.edge_index,
      'family': None if self.family is None else self.family.value,
      'sample_count': self.sample_count,
      'points_m': [list(sample.point_m) for sample in self.samples],
      'total_pressure_Pa': [
        sample.total_pressure_Pa for sample in self.samples
      ],
      'edge': None if self.edge is None else self.edge.as_report(),
      'physical_closure_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'message': self.message,
    }
  ####
####


def _frontier_failure(
  status: MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFrontierStatus,
  remesh: (
    MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshResult
    | None
  ),
  message: str,
) -> MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFrontierResult:
  return MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFrontierResult(
    status=status,
    remesh=remesh,
    edge=None,
    samples=(),
    message=message,
  )
####


def extract_euler_ambient_first_wedge_entropy_characteristic_remesh_frontier(
  remesh: MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshResult,
  *,
  position_tolerance_m: float = 1.0e-8,
  state_tolerance: float = 1.0e-8,
) -> MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFrontierResult:
  """Expose the solved terminal ``C-`` edge without changing the handoff.

  The returned samples follow the edge's stored outer-to-centerline order.
  They are diagnostic samples of the remesh itself; they are not a new
  production upstream field.
  """

  if not isinstance(
    remesh,
    MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshResult,
  ):
    return _frontier_failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFrontierStatus
      .INVALID_INPUT,
      None,
      'remesh must be a typed continuation remesh result',
    )
  ####
  try:
    position_tolerance = float(position_tolerance_m)
    resolved_state_tolerance = float(state_tolerance)
  except (TypeError, ValueError):
    return _frontier_failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFrontierStatus
      .INVALID_INPUT,
      remesh,
      'frontier tolerances must be numeric',
    )
  ####
  if not all(
    isfinite(value) and value > 0.0
    for value in (position_tolerance, resolved_state_tolerance)
  ):
    return _frontier_failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFrontierStatus
      .INVALID_INPUT,
      remesh,
      'frontier tolerances must be finite and positive',
    )
  ####
  source = remesh.source_continuation
  if not remesh.local_characteristic_remesh_verified or source is None:
    return _frontier_failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFrontierStatus
      .FRONTIER_UNAVAILABLE,
      remesh,
      'a locally verified remesh and source continuation are required before '
      'the outgoing frontier can be exposed',
    )
  ####
  terminal = source.terminal_centerline_state
  if terminal is None or not source.outer_states:
    return _frontier_failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFrontierStatus
      .FRONTIER_UNAVAILABLE,
      remesh,
      'the source continuation does not retain a terminal centerline and '
      'outer state pair',
    )
  ####
  expected_outer = source.outer_states[-1]
  expected_outer_pressure = source.outer_total_pressure_Pa[-1]
  expected_terminal_pressure = source.terminal_centerline_total_pressure_Pa
  if expected_terminal_pressure is None:
    return _frontier_failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFrontierStatus
      .FRONTIER_UNAVAILABLE,
      remesh,
      'the source continuation does not retain terminal pressure lineage',
    )
  ####
  candidates = tuple(
    edge
    for edge in reversed(remesh.characteristic_edges)
    if edge.family is CharacteristicFamily.MINUS
    and _state_close(
      edge.start_state,
      expected_outer,
      position_tolerance_m=position_tolerance,
      state_tolerance=resolved_state_tolerance,
    )
    and _state_close(
      edge.end_state,
      terminal,
      position_tolerance_m=position_tolerance,
      state_tolerance=resolved_state_tolerance,
    )
  )
  if not candidates:
    return _frontier_failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFrontierStatus
      .FRONTIER_UNAVAILABLE,
      remesh,
      'no solved C- edge connects the final outer state to the terminal '
      'centerline state',
    )
  ####
  edge = candidates[0]
  if (
    abs(edge.start_total_pressure_Pa - expected_outer_pressure)
    > resolved_state_tolerance * max(1.0, abs(expected_outer_pressure))
    or abs(edge.end_total_pressure_Pa - expected_terminal_pressure)
    > resolved_state_tolerance * max(1.0, abs(expected_terminal_pressure))
  ):
    return _frontier_failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFrontierStatus
      .FRONTIER_UNAVAILABLE,
      remesh,
      'the terminal C- edge does not preserve the source pressure lineage',
    )
  ####
  points = edge.points_xr_m
  if any(
    second[0] <= first[0] + position_tolerance
    or second[1] > first[1] + position_tolerance
    for first, second in zip(points, points[1:])
  ):
    return _frontier_failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFrontierStatus
      .GEOMETRY_FAILURE,
      remesh,
      'the solved outgoing C- frontier is not downstream and nonincreasing '
      'toward the centerline',
    )
  ####
  if (
    points[0][1] <= source.target_centerline_y_m + position_tolerance
    or abs(points[-1][1] - source.target_centerline_y_m)
    > position_tolerance
  ):
    return _frontier_failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFrontierStatus
      .GEOMETRY_FAILURE,
      remesh,
      'the solved outgoing C- frontier does not span the declared centerline',
    )
  ####
  if (
    edge.maximum_geometry_residual
    > remesh.characteristic_residual_tolerance
    or edge.maximum_compatibility_residual
    > remesh.characteristic_residual_tolerance
    or edge.maximum_pressure_residual > remesh.pressure_lineage_tolerance
  ):
    return _frontier_failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFrontierStatus
      .GEOMETRY_FAILURE,
      remesh,
      'the terminal C- frontier did not retain its local characteristic or '
      'pressure-lineage residual gates',
    )
  ####
  samples = tuple(
    MocChainBoundarySample(state=state, total_pressure_Pa=pressure)
    for state, pressure in zip(edge.states, edge.total_pressure_Pa, strict=True)
  )
  return MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFrontierResult(
    status=(
      MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFrontierStatus
      .CONVERGED_BOUNDED_FRONTIER
    ),
    remesh=remesh,
    edge=edge,
    samples=samples,
    message=(
      'exact solver-owned outgoing C- frontier exposed as bounded diagnostic '
      'samples; global reflected/free-boundary closure remains separate'
    ),
    position_tolerance_m=position_tolerance,
    state_tolerance=resolved_state_tolerance,
  )
####


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFrontierCoverageResult:
  """An audit of a candidate path against a bounded solved frontier."""

  status: (
    MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFrontierCoverageStatus
  )
  frontier: (
    MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFrontierResult | None
  )
  requested_points_m: tuple[tuple[float, float], ...]
  covered_points_m: tuple[tuple[float, float], ...]
  first_missing_sample_index: int | None
  first_missing_point_m: tuple[float, float] | None
  first_exterior_sample_index: int | None
  first_exterior_point_m: tuple[float, float] | None
  first_exterior_frontier_point_m: tuple[float, float] | None
  first_exterior_signed_offset_m: float | None
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFrontierCoverageStatus,
    ):
      raise TypeError('status must be a frontier coverage status')
    ####
    if self.frontier is not None and not isinstance(
      self.frontier,
      MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFrontierResult,
    ):
      raise TypeError('frontier must be a typed frontier result or None')
    ####
    requested = tuple(
      (float(point[0]), float(point[1])) for point in self.requested_points_m
    )
    covered = tuple(
      (float(point[0]), float(point[1])) for point in self.covered_points_m
    )
    if any(
      not all(isfinite(value) for value in point)
      for point in (*requested, *covered)
    ):
      raise ValueError('frontier coverage points must be finite')
    ####
    object.__setattr__(self, 'requested_points_m', requested)
    object.__setattr__(self, 'covered_points_m', covered)
    for name in (
      'first_missing_sample_index',
      'first_exterior_sample_index',
    ):
      value = getattr(self, name)
      if value is not None and (
        isinstance(value, bool) or not isinstance(value, int) or value < 0
      ):
        raise ValueError(f'{name} must be a nonnegative integer or None')
      ####
    ####
    for name in (
      'first_missing_point_m',
      'first_exterior_point_m',
      'first_exterior_frontier_point_m',
    ):
      point = getattr(self, name)
      if point is None:
        continue
      ####
      resolved = (float(point[0]), float(point[1]))
      if not all(isfinite(value) for value in resolved):
        raise ValueError(f'{name} must contain finite coordinates')
      ####
      object.__setattr__(self, name, resolved)
    ####
    if self.first_exterior_signed_offset_m is not None:
      offset = float(self.first_exterior_signed_offset_m)
      if not isfinite(offset):
        raise ValueError('first_exterior_signed_offset_m must be finite')
      ####
      object.__setattr__(self, 'first_exterior_signed_offset_m', offset)
    ####
    if (
      self.first_missing_sample_index is None
      and self.first_missing_point_m is not None
    ) or (
      self.first_missing_sample_index is not None
      and self.first_missing_point_m is None
    ):
      raise ValueError(
        'first missing sample index and point must be supplied together'
      )
    ####
    if (
      self.first_exterior_sample_index is None
      and any(
        value is not None
        for value in (
          self.first_exterior_point_m,
          self.first_exterior_frontier_point_m,
          self.first_exterior_signed_offset_m,
        )
      )
    ) or (
      self.first_exterior_sample_index is not None
      and self.first_exterior_point_m is None
    ):
      raise ValueError('exterior sample metadata is incomplete')
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status is (
      MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFrontierCoverageStatus
      .CONVERGED_BOUNDED_PATH
    )
  ####

  @property
  def covered_sample_count(self) -> int:
    return len(self.covered_points_m)
  ####

  @property
  def requested_sample_count(self) -> int:
    return len(self.requested_points_m)
  ####

  @property
  def physical_closure_verified(self) -> bool:
    return False
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    return True
  ####

  @property
  def production_claim_allowed(self) -> bool:
    return False
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'requested_sample_count': self.requested_sample_count,
      'covered_sample_count': self.covered_sample_count,
      'requested_points_m': [list(point) for point in self.requested_points_m],
      'covered_points_m': [list(point) for point in self.covered_points_m],
      'first_missing_sample_index': self.first_missing_sample_index,
      'first_missing_point_m': self.first_missing_point_m,
      'first_exterior_sample_index': self.first_exterior_sample_index,
      'first_exterior_point_m': self.first_exterior_point_m,
      'first_exterior_frontier_point_m': self.first_exterior_frontier_point_m,
      'first_exterior_signed_offset_m': self.first_exterior_signed_offset_m,
      'frontier': None if self.frontier is None else self.frontier.as_report(),
      'physical_closure_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'message': self.message,
    }
  ####
####


def _coverage_result(
  status: MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFrontierCoverageStatus,
  frontier: MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFrontierResult
  | None,
  points: tuple[tuple[float, float], ...],
  covered: tuple[tuple[float, float], ...],
  *,
  first_missing_sample_index: int | None = None,
  first_missing_point_m: tuple[float, float] | None = None,
  first_exterior_sample_index: int | None = None,
  first_exterior_point_m: tuple[float, float] | None = None,
  first_exterior_frontier_point_m: tuple[float, float] | None = None,
  first_exterior_signed_offset_m: float | None = None,
  message: str,
) -> MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFrontierCoverageResult:
  return MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFrontierCoverageResult(
    status=status,
    frontier=frontier,
    requested_points_m=points,
    covered_points_m=covered,
    first_missing_sample_index=first_missing_sample_index,
    first_missing_point_m=first_missing_point_m,
    first_exterior_sample_index=first_exterior_sample_index,
    first_exterior_point_m=first_exterior_point_m,
    first_exterior_frontier_point_m=first_exterior_frontier_point_m,
    first_exterior_signed_offset_m=first_exterior_signed_offset_m,
    message=message,
  )
####


def _frontier_point_at_y(
  samples: Sequence[MocChainBoundarySample],
  y_m: float,
  *,
  position_tolerance_m: float,
) -> tuple[float, float] | None:
  for sample in samples:
    if abs(sample.state.y_m - y_m) <= position_tolerance_m:
      return sample.point_m
    ####
  ####
  for first, second in zip(samples, samples[1:]):
    first_y = first.state.y_m
    second_y = second.state.y_m
    if not second_y - position_tolerance_m <= y_m <= first_y + position_tolerance_m:
      continue
    ####
    denominator = first_y - second_y
    if denominator <= 0.0:
      continue
    ####
    fraction = (first_y - y_m) / denominator
    return (
      first.state.x_m + fraction * (second.state.x_m - first.state.x_m),
      float(y_m),
    )
  ####
  return None
####


def audit_euler_ambient_first_wedge_entropy_characteristic_remesh_frontier_path(
  frontier: MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFrontierResult,
  path_points_m: Sequence[tuple[float, float]],
  *,
  position_tolerance_m: float = 1.0e-8,
) -> MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFrontierCoverageResult:
  """Audit a downstream shock candidate against the solved frontier.

  A positive signed offset means the candidate lies on the exterior
  downstream side of the outgoing frontier at the same ordinate.  The
  frontier is never evaluated outside its retained ordinate range.
  """

  try:
    points = tuple((float(point[0]), float(point[1])) for point in path_points_m)
  except (IndexError, TypeError, ValueError):
    points = ()
  ####
  if not points or any(not all(isfinite(value) for value in point) for point in points):
    return _coverage_result(
      MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFrontierCoverageStatus
      .INVALID_INPUT,
      frontier if isinstance(
        frontier,
        MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFrontierResult,
      ) else None,
      points,
      (),
      message='path_points_m must contain at least one finite point',
    )
  ####
  if not isinstance(
    frontier,
    MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFrontierResult,
  ):
    return _coverage_result(
      MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFrontierCoverageStatus
      .INVALID_INPUT,
      None,
      points,
      (),
      message='frontier must be a typed remesh frontier result',
    )
  ####
  try:
    tolerance = float(position_tolerance_m)
  except (TypeError, ValueError):
    tolerance = float('nan')
  ####
  if not isfinite(tolerance) or tolerance <= 0.0:
    return _coverage_result(
      MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFrontierCoverageStatus
      .INVALID_INPUT,
      frontier,
      points,
      (),
      message='position_tolerance_m must be finite and positive',
    )
  ####
  if not frontier.converged or frontier.remesh is None:
    return _coverage_result(
      MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFrontierCoverageStatus
      .FRONTIER_REQUIRED,
      frontier,
      points,
      (),
      message='a converged bounded frontier is required for path coverage',
    )
  ####
  if any(
    second[0] <= first[0] + tolerance
    or second[1] > first[1] + tolerance
    for first, second in zip(points, points[1:])
  ):
    return _coverage_result(
      MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFrontierCoverageStatus
      .PATH_GEOMETRY_FAILURE,
      frontier,
      points,
      (),
      first_missing_sample_index=1,
      first_missing_point_m=points[1],
      message=(
        'candidate path must progress strictly downstream in x and not rise '
        'in y'
      ),
    )
  ####
  covered: list[tuple[float, float]] = []
  for index, point in enumerate(points):
    try:
      state = frontier.remesh.diagnostic_state_at(
        point,
        position_tolerance_m=tolerance,
      )
      pressure = frontier.remesh.diagnostic_static_pressure_at(
        point,
        position_tolerance_m=tolerance,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      return _coverage_result(
        MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFrontierCoverageStatus
        .SAMPLER_FAILURE,
        frontier,
        points,
        tuple(covered),
        first_missing_sample_index=index,
        first_missing_point_m=point,
        message=f'bounded frontier sampler failed at sample {index}: {error}',
      )
    ####
    if state is not None and pressure is not None:
      covered.append(point)
      continue
    ####
    frontier_point = _frontier_point_at_y(
      frontier.samples,
      point[1],
      position_tolerance_m=tolerance,
    )
    signed_offset = (
      None if frontier_point is None else point[0] - frontier_point[0]
    )
    if signed_offset is not None and signed_offset > tolerance:
      return _coverage_result(
        MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFrontierCoverageStatus
        .FRONTIER_EXTERIOR,
        frontier,
        points,
        tuple(covered),
        first_missing_sample_index=index,
        first_missing_point_m=point,
        first_exterior_sample_index=index,
        first_exterior_point_m=point,
        first_exterior_frontier_point_m=frontier_point,
        first_exterior_signed_offset_m=signed_offset,
        message=(
          'candidate path left the bounded remesh on the exterior side of '
          'the solved outgoing C- frontier; no upstream state was extrapolated'
        ),
      )
    ####
    return _coverage_result(
      MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFrontierCoverageStatus
      .DOMAIN_GAP,
      frontier,
      points,
      tuple(covered),
      first_missing_sample_index=index,
      first_missing_point_m=point,
      message=(
        'candidate path is not covered by the bounded remesh and its first '
        'missing point cannot be attributed to the retained frontier'
      ),
    )
  ####
  return _coverage_result(
    MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFrontierCoverageStatus
    .CONVERGED_BOUNDED_PATH,
    frontier,
    points,
    tuple(covered),
    message=(
      'every candidate path sample is covered by the bounded entropy remesh; '
      'global reflected/free-boundary and physical chain closure remain pending'
    ),
  )
####
