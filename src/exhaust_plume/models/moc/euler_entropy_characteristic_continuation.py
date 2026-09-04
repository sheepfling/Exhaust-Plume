"""Variable-entropy continuation of the solver-owned planar MOC frontier.

The entropy-characteristic first-wedge field ends on a curved ``C-``
perimeter.  The older reflected-domain primitive assumes a constant
characteristic invariant and therefore cannot consume that perimeter without
silently discarding its entropy gradient.  This module supplies the narrow
next seam: a bounded alternating ``C-``/``C+`` source band that transports the
declared log-total-pressure gradient and solves its geometry locally.

The source band is research evidence only.  It has a bounded state sampler,
but it does not solve a downstream shock or authorize a physical shock-cell
chain.  Conservative Euler residuals are retained as an independent gate and
are deliberately not folded into the characteristic-geometry result.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import cos, exp, hypot, isfinite, log, sin, sqrt, tan
from typing import Any, Sequence

from scipy.optimize import least_squares

from exhaust_plume.models.moc.boundary import (
  solve_ambient_pressure_free_boundary_point,
)
from exhaust_plume.models.moc.chain import (
  MocChainBoundaryKind,
  MocChainBoundarySample,
  MocChainTerminationDecision,
  MocChainTerminationReason,
)
from exhaust_plume.models.moc.euler_entropy_carry import _cell_euler_residual
from exhaust_plume.models.moc.euler_entropy_characteristic_field import (
  MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult,
)
from exhaust_plume.models.moc.euler_first_wedge_remesh import (
  MocEulerAmbientFirstWedgeCellSample,
)
from exhaust_plume.models.moc.primitives import (
  CharacteristicFamily,
  CharacteristicState,
  inverse_prandtl_meyer_angle_rad,
)
from exhaust_plume.models.moc.topology import MocTopologyResult, validate_moc_mesh
from exhaust_plume.models.moc.zone import MocCharacteristicCell

__all__ = (
  'MocEulerAmbientFirstWedgeEntropyCharacteristicSegmentStatus',
  'MocEulerAmbientFirstWedgeEntropyCharacteristicSegmentResult',
  'MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationStatus',
  'MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationResult',
  'solve_euler_ambient_first_wedge_entropy_characteristic_continuation',
)


class MocEulerAmbientFirstWedgeEntropyCharacteristicSegmentStatus(str, Enum):
  """Outcome of one variable-entropy characteristic segment solve."""

  CONVERGED = 'converged_variable_entropy_characteristic_segment'
  INVALID_INPUT = 'invalid_input'
  SOLVER_FAILURE = 'variable_entropy_characteristic_segment_solver_failure'
  GEOMETRY_FAILURE = 'variable_entropy_characteristic_segment_geometry_failure'
  COMPATIBILITY_FAILURE = (
    'variable_entropy_characteristic_segment_compatibility_failure'
  )
  PRESSURE_FAILURE = 'variable_entropy_characteristic_segment_pressure_failure'
####


class MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationStatus(str, Enum):
  """Outcome of a bounded alternating entropy-characteristic continuation."""

  CONVERGED_BOUNDED_CONTINUATION = (
    'converged_bounded_entropy_characteristic_continuation'
  )
  INVALID_INPUT = 'invalid_input'
  FIELD_REQUIRED = 'entropy_characteristic_field_required'
  HANDOFF_FAILURE = 'entropy_characteristic_continuation_handoff_failure'
  REFLECTION_FAILURE = 'entropy_characteristic_centerline_reflection_failure'
  AMBIENT_BOUNDARY_FAILURE = (
    'entropy_characteristic_ambient_boundary_continuation_failure'
  )
  TOPOLOGY_FAILURE = 'entropy_characteristic_continuation_topology_failure'
  PRESSURE_LINEAGE_FAILURE = (
    'entropy_characteristic_continuation_pressure_lineage_failure'
  )
  EULER_RESIDUAL_FAILURE = (
    'entropy_characteristic_continuation_euler_residual_failure'
  )
####


def _finite_point(point: Sequence[float]) -> tuple[float, float] | None:
  try:
    value = (float(point[0]), float(point[1]))
  except (IndexError, TypeError, ValueError):
    return None
  ####
  return value if all(isfinite(component) for component in value) else None
####


def _state_matches(
  actual: CharacteristicState,
  expected: CharacteristicState,
  *,
  position_tolerance_m: float,
  state_tolerance: float,
) -> bool:
  return bool(
    abs(actual.x_m - expected.x_m) <= position_tolerance_m
    and abs(actual.y_m - expected.y_m) <= position_tolerance_m
    and abs(actual.theta_rad - expected.theta_rad)
    <= state_tolerance * max(1.0, abs(actual.theta_rad), abs(expected.theta_rad))
    and abs(actual.mach - expected.mach)
    <= state_tolerance * max(1.0, abs(actual.mach), abs(expected.mach))
    and abs(actual.gamma - expected.gamma)
    <= state_tolerance * max(1.0, abs(actual.gamma), abs(expected.gamma))
  )
####


def _transport_total_pressure(
  start: CharacteristicState,
  start_total_pressure_Pa: float,
  point: tuple[float, float],
  gradient: tuple[float, float],
) -> float:
  return float(start_total_pressure_Pa) * exp(
    gradient[0] * (point[0] - start.x_m)
    + gradient[1] * (point[1] - start.y_m)
  )
####


def _compatibility_source(
  start: CharacteristicState,
  end: CharacteristicState,
  gradient: tuple[float, float],
) -> float:
  length = hypot(end.x_m - start.x_m, end.y_m - start.y_m)
  average_theta = 0.5 * (start.theta_rad + end.theta_rad)
  normal_gradient = (
    gradient[0] * -sin(average_theta)
    + gradient[1] * cos(average_theta)
  )
  average_mach = 0.5 * (start.mach + end.mach)
  average_gamma = 0.5 * (start.gamma + end.gamma)
  return (
    -sqrt(max(average_mach * average_mach - 1.0, 0.0))
    / (average_gamma * average_mach**3)
    * normal_gradient
    * length
  )
####


def _characteristic_geometry_residual(
  start: CharacteristicState,
  end: CharacteristicState,
  family: CharacteristicFamily,
) -> float:
  displacement = (end.x_m - start.x_m, end.y_m - start.y_m)
  length = hypot(*displacement)
  start_direction = start.direction(family)
  end_direction = end.direction(family)
  average_direction = (
    0.5 * (start_direction[0] + end_direction[0]),
    0.5 * (start_direction[1] + end_direction[1]),
  )
  average_length = hypot(*average_direction)
  if length <= 0.0 or average_length <= 0.0:
    return float('inf')
  ####
  return (
    displacement[0] * average_direction[1]
    - displacement[1] * average_direction[0]
  ) / (length * average_length)
####


def _boundary_geometry_residual(
  previous: CharacteristicState,
  current: CharacteristicState,
) -> float:
  displacement = (current.x_m - previous.x_m, current.y_m - previous.y_m)
  length = hypot(*displacement)
  if length <= 0.0:
    return float('inf')
  ####
  angle = 0.5 * (previous.theta_rad + current.theta_rad)
  return (
    displacement[0] * sin(angle)
    - displacement[1] * cos(angle)
  ) / length
####


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeEntropyCharacteristicSegmentResult:
  """Auditable result for one variable-entropy characteristic segment."""

  status: MocEulerAmbientFirstWedgeEntropyCharacteristicSegmentStatus
  family: CharacteristicFamily
  start_state: CharacteristicState | None
  end_state: CharacteristicState | None
  start_total_pressure_Pa: float | None
  end_total_pressure_Pa: float | None
  geometry_residual: float | None
  compatibility_residual: float | None
  pressure_residual: float | None
  solver_iterations: int
  solver_success: bool
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocEulerAmbientFirstWedgeEntropyCharacteristicSegmentStatus,
    ):
      raise TypeError('status must be a segment status')
    ####
    if not isinstance(self.family, CharacteristicFamily):
      raise TypeError('family must be a CharacteristicFamily')
    ####
    for name in ('start_state', 'end_state'):
      value = getattr(self, name)
      if value is not None and not isinstance(value, CharacteristicState):
        raise TypeError(f'{name} must be a CharacteristicState or None')
      ####
    ####
    for name in ('start_total_pressure_Pa', 'end_total_pressure_Pa'):
      value = getattr(self, name)
      if value is None:
        continue
      ####
      numeric = float(value)
      if not isfinite(numeric) or numeric <= 0.0:
        raise ValueError(f'{name} must be finite and positive when supplied')
      ####
      object.__setattr__(self, name, numeric)
    ####
    for name in (
      'geometry_residual',
      'compatibility_residual',
      'pressure_residual',
    ):
      value = getattr(self, name)
      if value is None:
        continue
      ####
      numeric = float(value)
      if not isfinite(numeric) or numeric < 0.0:
        raise ValueError(f'{name} must be finite and nonnegative when supplied')
      ####
      object.__setattr__(self, name, numeric)
    ####
    if (
      isinstance(self.solver_iterations, bool)
      or not isinstance(self.solver_iterations, int)
      or self.solver_iterations < 0
    ):
      raise ValueError('solver_iterations must be a nonnegative integer')
    ####
    if not isinstance(self.solver_success, bool):
      raise TypeError('solver_success must be a bool')
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status is (
      MocEulerAmbientFirstWedgeEntropyCharacteristicSegmentStatus.CONVERGED
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'family': self.family.value,
      'start_point_m': (
        None
        if self.start_state is None
        else [self.start_state.x_m, self.start_state.y_m]
      ),
      'end_point_m': (
        None
        if self.end_state is None
        else [self.end_state.x_m, self.end_state.y_m]
      ),
      'start_total_pressure_Pa': self.start_total_pressure_Pa,
      'end_total_pressure_Pa': self.end_total_pressure_Pa,
      'geometry_residual': self.geometry_residual,
      'compatibility_residual': self.compatibility_residual,
      'pressure_residual': self.pressure_residual,
      'solver_iterations': self.solver_iterations,
      'solver_success': self.solver_success,
      'message': self.message,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationResult:
  """A bounded alternating source band below physical shock-cell promotion."""

  status: MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationStatus
  source_field: (
    MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult
    | MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationResult
    | None
  )
  incoming_handoff: tuple[MocChainBoundarySample, ...]
  source_pressure_gradient: tuple[float, float] | None
  centerline_states: tuple[CharacteristicState, ...]
  outer_states: tuple[CharacteristicState, ...]
  terminal_centerline_state: CharacteristicState | None
  centerline_total_pressure_Pa: tuple[float, ...]
  outer_total_pressure_Pa: tuple[float, ...]
  terminal_centerline_total_pressure_Pa: float | None
  centerline_segments: tuple[
    MocEulerAmbientFirstWedgeEntropyCharacteristicSegmentResult, ...
  ]
  outer_segments: tuple[
    MocEulerAmbientFirstWedgeEntropyCharacteristicSegmentResult, ...
  ]
  terminal_segment: MocEulerAmbientFirstWedgeEntropyCharacteristicSegmentResult | None
  cells: tuple[MocCharacteristicCell, ...]
  cell_samples: tuple[MocEulerAmbientFirstWedgeCellSample, ...]
  topology: MocTopologyResult
  cell_euler_residuals: tuple[float, ...]
  maximum_cell_euler_residual: float | None
  maximum_geometry_residual: float | None
  maximum_compatibility_residual: float | None
  maximum_pressure_residual: float | None
  reflection_anchor_verified: bool
  alternating_seams_verified: bool
  pressure_lineage_verified: bool
  cell_euler_residuals_finite: bool
  cell_euler_residuals_verified: bool
  physical_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  external_validation_required: bool = True
  ambient_pressure_Pa: float | None = None
  cycle_count: int = 0
  target_centerline_y_m: float = 0.0
  target_centerline_flow_angle_rad: float = 0.0
  position_tolerance_m: float = 1.0e-8
  characteristic_residual_tolerance: float = 1.0e-8
  pressure_lineage_tolerance: float = 1.0e-8
  cell_residual_tolerance: float = 1.0e-2
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationStatus,
    ):
      raise TypeError('status must be a continuation status')
    ####
    if self.source_field is not None and not isinstance(
      self.source_field,
      (
        MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult,
        MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationResult,
      ),
    ):
      raise TypeError(
        'source_field must be an entropy field, a prior entropy continuation, '
        'or None'
      )
    ####
    handoff = tuple(self.incoming_handoff)
    if any(not isinstance(sample, MocChainBoundarySample) for sample in handoff):
      raise TypeError('incoming_handoff must contain chain boundary samples')
    ####
    object.__setattr__(self, 'incoming_handoff', handoff)
    if self.source_pressure_gradient is not None:
      gradient = tuple(float(value) for value in self.source_pressure_gradient)
      if len(gradient) != 2 or not all(isfinite(value) for value in gradient):
        raise ValueError('source_pressure_gradient must contain finite values')
      ####
      object.__setattr__(self, 'source_pressure_gradient', gradient)
    ####
    for name in (
      'centerline_states',
      'outer_states',
    ):
      values = tuple(getattr(self, name))
      if any(not isinstance(state, CharacteristicState) for state in values):
        raise TypeError(f'{name} must contain CharacteristicState values')
      ####
      object.__setattr__(self, name, values)
    ####
    if self.terminal_centerline_state is not None and not isinstance(
      self.terminal_centerline_state,
      CharacteristicState,
    ):
      raise TypeError('terminal_centerline_state must be a CharacteristicState or None')
    ####
    for name in (
      'centerline_total_pressure_Pa',
      'outer_total_pressure_Pa',
    ):
      values = tuple(float(value) for value in getattr(self, name))
      if any(not isfinite(value) or value <= 0.0 for value in values):
        raise ValueError(f'{name} must contain finite positive values')
      ####
      object.__setattr__(self, name, values)
    ####
    if self.terminal_centerline_total_pressure_Pa is not None:
      terminal_pressure = float(self.terminal_centerline_total_pressure_Pa)
      if not isfinite(terminal_pressure) or terminal_pressure <= 0.0:
        raise ValueError(
          'terminal_centerline_total_pressure_Pa must be finite and positive'
        )
      ####
      object.__setattr__(self, 'terminal_centerline_total_pressure_Pa', terminal_pressure)
    ####
    for name in ('centerline_segments', 'outer_segments'):
      values = tuple(getattr(self, name))
      if any(
        not isinstance(
          segment,
          MocEulerAmbientFirstWedgeEntropyCharacteristicSegmentResult,
        )
        for segment in values
      ):
        raise TypeError(f'{name} must contain typed segment results')
      ####
      object.__setattr__(self, name, values)
    ####
    if self.terminal_segment is not None and not isinstance(
      self.terminal_segment,
      MocEulerAmbientFirstWedgeEntropyCharacteristicSegmentResult,
    ):
      raise TypeError('terminal_segment must be a typed segment result or None')
    ####
    cells = tuple(self.cells)
    samples = tuple(self.cell_samples)
    if any(not isinstance(cell, MocCharacteristicCell) for cell in cells):
      raise TypeError('cells must contain MocCharacteristicCell values')
    ####
    if any(
      not isinstance(sample, MocEulerAmbientFirstWedgeCellSample)
      for sample in samples
    ):
      raise TypeError('cell_samples must contain typed cell samples')
    ####
    if len(cells) != len(samples):
      raise ValueError('cells and cell_samples must have equal lengths')
    ####
    if not isinstance(self.topology, MocTopologyResult):
      raise TypeError('topology must be a MocTopologyResult')
    ####
    object.__setattr__(self, 'cells', cells)
    object.__setattr__(self, 'cell_samples', samples)
    residuals = tuple(float(value) for value in self.cell_euler_residuals)
    if any(not isfinite(value) or value < 0.0 for value in residuals):
      raise ValueError('cell_euler_residuals must be finite and nonnegative')
    ####
    if len(residuals) != len(samples):
      raise ValueError('cell_euler_residuals must match cell_samples')
    ####
    object.__setattr__(self, 'cell_euler_residuals', residuals)
    if self.maximum_cell_euler_residual is not None:
      maximum_residual = float(self.maximum_cell_euler_residual)
      if not isfinite(maximum_residual) or maximum_residual < 0.0:
        raise ValueError(
          'maximum_cell_euler_residual must be finite and nonnegative when supplied'
        )
      ####
      object.__setattr__(
        self,
        'maximum_cell_euler_residual',
        maximum_residual,
      )
    ####
    for name in (
      'maximum_geometry_residual',
      'maximum_compatibility_residual',
      'maximum_pressure_residual',
    ):
      value = getattr(self, name)
      if value is None:
        continue
      ####
      numeric = float(value)
      if not isfinite(numeric) or numeric < 0.0:
        raise ValueError(f'{name} must be finite and nonnegative when supplied')
      ####
      object.__setattr__(self, name, numeric)
    ####
    for name in (
      'reflection_anchor_verified',
      'alternating_seams_verified',
      'pressure_lineage_verified',
      'cell_euler_residuals_finite',
      'cell_euler_residuals_verified',
      'physical_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
      'external_validation_required',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if self.physical_closure_verified:
      raise ValueError('entropy continuation cannot claim physical closure')
    ####
    if not self.chain_promotion_blocked:
      raise ValueError('entropy continuation must remain blocked from promotion')
    ####
    if self.production_claim_allowed:
      raise ValueError('entropy continuation cannot claim production validity')
    ####
    if self.ambient_pressure_Pa is not None:
      ambient_pressure = float(self.ambient_pressure_Pa)
      if not isfinite(ambient_pressure) or ambient_pressure <= 0.0:
        raise ValueError(
          'ambient_pressure_Pa must be finite and positive when supplied'
        )
      ####
      object.__setattr__(self, 'ambient_pressure_Pa', ambient_pressure)
    ####
    for name in (
      'cycle_count',
    ):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer')
      ####
    ####
    for name in (
      'target_centerline_y_m',
      'target_centerline_flow_angle_rad',
    ):
      value = float(getattr(self, name))
      if not isfinite(value):
        raise ValueError(f'{name} must be finite')
      ####
      object.__setattr__(self, name, value)
    ####
    for name in (
      'position_tolerance_m',
      'characteristic_residual_tolerance',
      'pressure_lineage_tolerance',
      'cell_residual_tolerance',
    ):
      value = float(getattr(self, name))
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      ####
      object.__setattr__(self, name, value)
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status is (
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationStatus
      .CONVERGED_BOUNDED_CONTINUATION
    )
  ####

  @property
  def continuation_boundary_kind(self) -> MocChainBoundaryKind:
    return MocChainBoundaryKind.POST_SHOCK_FIELD_PERIMETER
  ####

  @property
  def continuation_boundary(self) -> tuple[MocChainBoundarySample, ...]:
    """Return the final solved ``C-`` front, ordered outer to centerline."""

    if not self.converged or self.outer_states == () or self.terminal_centerline_state is None:
      return ()
    ####
    if self.terminal_centerline_total_pressure_Pa is None:
      return ()
    ####
    return (
      MocChainBoundarySample(
        state=self.outer_states[-1],
        total_pressure_Pa=self.outer_total_pressure_Pa[-1],
      ),
      MocChainBoundarySample(
        state=self.terminal_centerline_state,
        total_pressure_Pa=self.terminal_centerline_total_pressure_Pa,
      ),
    )
  ####

  @property
  def continuation_boundary_verified(self) -> bool:
    boundary = self.continuation_boundary
    return bool(
      len(boundary) == 2
      and boundary[1].state.x_m > boundary[0].state.x_m + self.position_tolerance_m
      and boundary[1].state.y_m < boundary[0].state.y_m - self.position_tolerance_m
      and boundary[0].state.y_m > self.target_centerline_y_m
      and abs(boundary[1].state.y_m - self.target_centerline_y_m)
      <= self.position_tolerance_m
    )
  ####

  @property
  def local_consistency_verified(self) -> bool:
    return bool(
      self.converged
      and self.source_field is not None
      and self.source_field.local_consistency_verified
      and self.incoming_handoff == self.source_field.continuation_boundary
      and self.reflection_anchor_verified
      and self.alternating_seams_verified
      and self.pressure_lineage_verified
      and self.topology.connected
      and self.topology.forms_closed_zone
      and self.topology.nonmanifold_edge_count == 0
      and self.continuation_boundary_verified
      and self.cell_euler_residuals_finite
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
    )
  ####

  @property
  def state_sampling_available(self) -> bool:
    """Whether bounded research samples can be read without extrapolation."""

    return bool(self.local_consistency_verified and self.cells and self.cell_samples)
  ####

  @property
  def physical_chain_cell_count(self) -> int:
    return 0
  ####

  def _weights_at(
    self,
    point_m: Sequence[float],
    *,
    position_tolerance_m: float,
  ) -> tuple[tuple[float, float, float], MocEulerAmbientFirstWedgeCellSample] | None:
    point = _finite_point(point_m)
    if point is None:
      return None
    ####
    tolerance = float(position_tolerance_m)
    if not isfinite(tolerance) or tolerance <= 0.0:
      raise ValueError('position_tolerance_m must be finite and positive')
    ####
    for sample in self.cell_samples:
      weights = _triangle_weights(point, sample.vertices_xr_m, tolerance)
      if weights is not None:
        return weights, sample
      ####
    ####
    return None
  ####

  def state_at(
    self,
    point_m: Sequence[float],
    *,
    position_tolerance_m: float = 1.0e-8,
  ) -> CharacteristicState | None:
    sampled = self._weights_at(
      point_m,
      position_tolerance_m=position_tolerance_m,
    )
    if sampled is None:
      return None
    ####
    weights, sample = sampled
    point = _finite_point(point_m)
    if point is None:
      return None
    ####
    theta = sum(
      weight * state.theta_rad
      for weight, state in zip(weights, sample.states, strict=True)
    )
    nu = sum(
      weight * state.nu_rad
      for weight, state in zip(weights, sample.states, strict=True)
    )
    inverse = inverse_prandtl_meyer_angle_rad(nu, sample.states[0].gamma)
    if not inverse.converged or inverse.value is None:
      return None
    ####
    return CharacteristicState(
      x_m=point[0],
      y_m=point[1],
      theta_rad=theta,
      mach=inverse.value,
      gamma=sample.states[0].gamma,
    )
  ####

  def total_pressure_at(
    self,
    point_m: Sequence[float],
    *,
    position_tolerance_m: float = 1.0e-8,
  ) -> float | None:
    sampled = self._weights_at(
      point_m,
      position_tolerance_m=position_tolerance_m,
    )
    if sampled is None:
      return None
    ####
    weights, sample = sampled
    return exp(
      sum(
        weight * log(pressure)
        for weight, pressure in zip(weights, sample.total_pressure_Pa, strict=True)
      )
    )
  ####

  def static_pressure_at(
    self,
    point_m: Sequence[float],
    *,
    position_tolerance_m: float = 1.0e-8,
  ) -> float | None:
    state = self.state_at(point_m, position_tolerance_m=position_tolerance_m)
    total_pressure = self.total_pressure_at(
      point_m,
      position_tolerance_m=position_tolerance_m,
    )
    if state is None or total_pressure is None:
      return None
    ####
    return total_pressure / (
      1.0 + 0.5 * (state.gamma - 1.0) * state.mach * state.mach
    ) ** (state.gamma / (state.gamma - 1.0))
  ####

  def as_chain_termination_decision(self) -> MocChainTerminationDecision:
    if self.status is (
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationStatus
      .INVALID_INPUT
    ):
      reason = MocChainTerminationReason.INVALID_INPUT
    elif self.status in (
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationStatus
      .FIELD_REQUIRED,
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationStatus
      .HANDOFF_FAILURE,
    ):
      reason = MocChainTerminationReason.STATE_NOT_CARRIED
    elif self.status in (
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationStatus
      .REFLECTION_FAILURE,
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationStatus
      .AMBIENT_BOUNDARY_FAILURE,
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationStatus
      .TOPOLOGY_FAILURE,
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationStatus
      .PRESSURE_LINEAGE_FAILURE,
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationStatus
      .EULER_RESIDUAL_FAILURE,
    ):
      reason = MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
    else:
      reason = MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
    ####
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=reason,
      message=self.message,
      diagnostics={
        'continuation_status': self.status.value,
        'cycle_count': self.cycle_count,
        'centerline_sample_count': len(self.centerline_states),
        'outer_sample_count': len(self.outer_states),
        'continuation_boundary_kind': self.continuation_boundary_kind.value,
        'continuation_boundary_sample_count': len(self.continuation_boundary),
        'continuation_boundary_verified': self.continuation_boundary_verified,
        'state_sampling_available': self.state_sampling_available,
        'cell_count': len(self.cells),
        'cell_euler_residuals_verified': self.cell_euler_residuals_verified,
        'physical_closure_verified': False,
        'chain_promotion_blocked': True,
        'production_claim_allowed': False,
        'external_validation_required': True,
        'ambient_pressure_Pa': self.ambient_pressure_Pa,
        'synthetic_downstream_field_created': False,
        'required_next_gate': (
          'conservative-euler-shock-boundary-closure-and-external-validation-'
          'before-continued-shock-cell-chain'
        ),
      },
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'local_consistency_verified': self.local_consistency_verified,
      'state_sampling_available': self.state_sampling_available,
      'continuation_boundary_kind': self.continuation_boundary_kind.value,
      'continuation_boundary_verified': self.continuation_boundary_verified,
      'continuation_boundary': [
        {
          'point_m': [sample.state.x_m, sample.state.y_m],
          'mach': sample.state.mach,
          'flow_angle_rad': sample.state.theta_rad,
          'total_pressure_Pa': sample.total_pressure_Pa,
        }
        for sample in self.continuation_boundary
      ],
      'cycle_count': self.cycle_count,
      'centerline_states': [
        {
          'point_m': [state.x_m, state.y_m],
          'mach': state.mach,
          'flow_angle_rad': state.theta_rad,
          'total_pressure_Pa': pressure,
        }
        for state, pressure in zip(
          self.centerline_states,
          self.centerline_total_pressure_Pa,
          strict=True,
        )
      ],
      'outer_states': [
        {
          'point_m': [state.x_m, state.y_m],
          'mach': state.mach,
          'flow_angle_rad': state.theta_rad,
          'total_pressure_Pa': pressure,
        }
        for state, pressure in zip(
          self.outer_states,
          self.outer_total_pressure_Pa,
          strict=True,
        )
      ],
      'terminal_centerline_state': (
        None
        if self.terminal_centerline_state is None
        else {
          'point_m': [
            self.terminal_centerline_state.x_m,
            self.terminal_centerline_state.y_m,
          ],
          'mach': self.terminal_centerline_state.mach,
          'flow_angle_rad': self.terminal_centerline_state.theta_rad,
          'total_pressure_Pa': self.terminal_centerline_total_pressure_Pa,
        }
      ),
      'source_pressure_gradient': self.source_pressure_gradient,
      'centerline_segments': [
        segment.as_report() for segment in self.centerline_segments
      ],
      'outer_segments': [segment.as_report() for segment in self.outer_segments],
      'terminal_segment': (
        None if self.terminal_segment is None else self.terminal_segment.as_report()
      ),
      'cell_count': len(self.cells),
      'cell_euler_residuals': list(self.cell_euler_residuals),
      'maximum_cell_euler_residual': self.maximum_cell_euler_residual,
      'maximum_geometry_residual': self.maximum_geometry_residual,
      'maximum_compatibility_residual': self.maximum_compatibility_residual,
      'maximum_pressure_residual': self.maximum_pressure_residual,
      'reflection_anchor_verified': self.reflection_anchor_verified,
      'alternating_seams_verified': self.alternating_seams_verified,
      'pressure_lineage_verified': self.pressure_lineage_verified,
      'cell_euler_residuals_finite': self.cell_euler_residuals_finite,
      'cell_euler_residuals_verified': self.cell_euler_residuals_verified,
      'topology': {
        'status': self.topology.status.value,
        'connected': self.topology.connected,
        'forms_closed_zone': self.topology.forms_closed_zone,
        'boundary_edge_count': self.topology.boundary_edge_count,
        'nonmanifold_edge_count': self.topology.nonmanifold_edge_count,
      },
      'physical_closure_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'external_validation_required': True,
      'ambient_pressure_Pa': self.ambient_pressure_Pa,
      'incoming_handoff_sample_count': len(self.incoming_handoff),
      'source_field_status': (
        None if self.source_field is None else self.source_field.status.value
      ),
      'chain_termination_decision': self.as_chain_termination_decision().as_report(),
      'message': self.message,
    }
  ####
####


def _triangle_weights(
  point: tuple[float, float],
  vertices: Sequence[tuple[float, float]],
  tolerance_m: float,
) -> tuple[float, float, float] | None:
  if len(vertices) != 3:
    return None
  ####
  (ax, ay), (bx, by), (cx, cy) = vertices
  denominator = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
  if not isfinite(denominator) or abs(denominator) <= max(
    tolerance_m * tolerance_m,
    1.0e-24,
  ):
    return None
  ####
  px, py = point
  first = ((by - cy) * (px - cx) + (cx - bx) * (py - cy)) / denominator
  second = ((cy - ay) * (px - cx) + (ax - cx) * (py - cy)) / denominator
  third = 1.0 - first - second
  if min(first, second, third) < -1.0e-10:
    return None
  ####
  if max(first, second, third) > 1.0 + 1.0e-10:
    return None
  ####
  return first, second, third
####


def _segment_failure(
  family: CharacteristicFamily,
  status: MocEulerAmbientFirstWedgeEntropyCharacteristicSegmentStatus,
  message: str,
  *,
  start_state: CharacteristicState | None = None,
  end_state: CharacteristicState | None = None,
  start_total_pressure_Pa: float | None = None,
  end_total_pressure_Pa: float | None = None,
  geometry_residual: float | None = None,
  compatibility_residual: float | None = None,
  pressure_residual: float | None = None,
  solver_iterations: int = 0,
  solver_success: bool = False,
) -> MocEulerAmbientFirstWedgeEntropyCharacteristicSegmentResult:
  return MocEulerAmbientFirstWedgeEntropyCharacteristicSegmentResult(
    status=status,
    family=family,
    start_state=start_state,
    end_state=end_state,
    start_total_pressure_Pa=start_total_pressure_Pa,
    end_total_pressure_Pa=end_total_pressure_Pa,
    geometry_residual=geometry_residual,
    compatibility_residual=compatibility_residual,
    pressure_residual=pressure_residual,
    solver_iterations=solver_iterations,
    solver_success=solver_success,
    message=message,
  )
####


def _solve_centerline_segment(
  start: CharacteristicState,
  start_total_pressure_Pa: float,
  gradient: tuple[float, float],
  target_y_m: float,
  target_theta_rad: float,
  *,
  position_tolerance_m: float,
  characteristic_residual_tolerance: float,
  maximum_iterations: int,
  expected_end: MocChainBoundarySample | None = None,
) -> MocEulerAmbientFirstWedgeEntropyCharacteristicSegmentResult:
  family = CharacteristicFamily.MINUS
  if target_y_m >= start.y_m - position_tolerance_m:
    return _segment_failure(
      family,
      MocEulerAmbientFirstWedgeEntropyCharacteristicSegmentStatus.INVALID_INPUT,
      'centerline target must be below the characteristic start',
      start_state=start,
      start_total_pressure_Pa=start_total_pressure_Pa,
    )
  ####
  initial_mach = max(1.05, start.mach)
  initial_angle = start.theta_rad - start.mu_rad
  tangent = tan(initial_angle)
  if abs(tangent) > 1.0e-8:
    initial_x = start.x_m + (target_y_m - start.y_m) / tangent
  else:
    initial_x = start.x_m + abs(start.y_m - target_y_m)
  ####
  initial_x = max(start.x_m + 10.0 * position_tolerance_m, initial_x)

  def residual(vector: Sequence[float]) -> tuple[float, float]:
    endpoint = CharacteristicState(
      x_m=float(vector[0]),
      y_m=target_y_m,
      theta_rad=target_theta_rad,
      mach=float(vector[1]),
      gamma=start.gamma,
    )
    return (
      _characteristic_geometry_residual(start, endpoint, family),
      endpoint.k_minus - start.k_minus - _compatibility_source(
        start,
        endpoint,
        gradient,
      ),
    )
  ####

  try:
    solved = least_squares(
      residual,
      (initial_x, initial_mach),
      bounds=(
        (start.x_m + position_tolerance_m, 1.0001),
        (start.x_m + 100.0, 32.0),
      ),
      max_nfev=max(32, maximum_iterations * 20),
      xtol=1.0e-13,
      ftol=1.0e-13,
      gtol=1.0e-13,
      x_scale='jac',
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _segment_failure(
      family,
      MocEulerAmbientFirstWedgeEntropyCharacteristicSegmentStatus.SOLVER_FAILURE,
      f'centerline variable-entropy solve failed: {error}',
      start_state=start,
      start_total_pressure_Pa=start_total_pressure_Pa,
    )
  ####
  try:
    endpoint = CharacteristicState(
      x_m=float(solved.x[0]),
      y_m=target_y_m,
      theta_rad=target_theta_rad,
      mach=float(solved.x[1]),
      gamma=start.gamma,
    )
    geometry = abs(_characteristic_geometry_residual(start, endpoint, family))
    compatibility = abs(
      endpoint.k_minus - start.k_minus - _compatibility_source(
        start,
        endpoint,
        gradient,
      )
    )
    end_pressure = _transport_total_pressure(
      start,
      start_total_pressure_Pa,
      (endpoint.x_m, endpoint.y_m),
      gradient,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _segment_failure(
      family,
      MocEulerAmbientFirstWedgeEntropyCharacteristicSegmentStatus.SOLVER_FAILURE,
      f'centerline endpoint reconstruction failed: {error}',
      start_state=start,
      start_total_pressure_Pa=start_total_pressure_Pa,
      solver_iterations=int(getattr(solved, 'nfev', 0)),
      solver_success=bool(getattr(solved, 'success', False)),
    )
  ####
  pressure_residual = 0.0
  if expected_end is not None:
    pressure_residual = abs(
      log(end_pressure / expected_end.total_pressure_Pa)
    )
    state_residual = max(
      abs(endpoint.x_m - expected_end.state.x_m),
      abs(endpoint.y_m - expected_end.state.y_m),
      abs(endpoint.theta_rad - expected_end.state.theta_rad),
      abs(endpoint.mach - expected_end.state.mach),
      abs(endpoint.gamma - expected_end.state.gamma),
    )
    pressure_residual = max(pressure_residual, state_residual)
  ####
  if not bool(getattr(solved, 'success', False)):
    status = MocEulerAmbientFirstWedgeEntropyCharacteristicSegmentStatus.SOLVER_FAILURE
    message = 'centerline variable-entropy solve did not converge'
  elif geometry > characteristic_residual_tolerance:
    status = MocEulerAmbientFirstWedgeEntropyCharacteristicSegmentStatus.GEOMETRY_FAILURE
    message = 'centerline characteristic geometry residual exceeded tolerance'
  elif compatibility > characteristic_residual_tolerance:
    status = MocEulerAmbientFirstWedgeEntropyCharacteristicSegmentStatus.COMPATIBILITY_FAILURE
    message = 'centerline variable-entropy compatibility residual exceeded tolerance'
  elif expected_end is not None and (
    not _state_matches(
      endpoint,
      expected_end.state,
      position_tolerance_m=position_tolerance_m,
      state_tolerance=characteristic_residual_tolerance,
    )
    or pressure_residual > characteristic_residual_tolerance
  ):
    status = MocEulerAmbientFirstWedgeEntropyCharacteristicSegmentStatus.PRESSURE_FAILURE
    message = 'centerline solve did not reproduce the exact incoming axis anchor'
  else:
    status = MocEulerAmbientFirstWedgeEntropyCharacteristicSegmentStatus.CONVERGED
    message = ''
  ####
  return _segment_failure(
    family,
    status,
    message,
    start_state=start,
    end_state=endpoint,
    start_total_pressure_Pa=start_total_pressure_Pa,
    end_total_pressure_Pa=end_pressure,
    geometry_residual=geometry,
    compatibility_residual=compatibility,
    pressure_residual=pressure_residual,
    solver_iterations=int(getattr(solved, 'nfev', 0)),
    solver_success=bool(getattr(solved, 'success', False)),
  )
####


def _solve_ambient_segment(
  start: CharacteristicState,
  start_total_pressure_Pa: float,
  previous_boundary: CharacteristicState,
  gradient: tuple[float, float],
  ambient_pressure_Pa: float,
  target_centerline_y_m: float,
  *,
  position_tolerance_m: float,
  characteristic_residual_tolerance: float,
  maximum_iterations: int,
) -> MocEulerAmbientFirstWedgeEntropyCharacteristicSegmentResult:
  family = CharacteristicFamily.PLUS
  try:
    reference = solve_ambient_pressure_free_boundary_point(
      start,
      previous_boundary,
      family,
      total_pressure_Pa=start_total_pressure_Pa,
      ambient_pressure_Pa=ambient_pressure_Pa,
      position_tolerance_m=position_tolerance_m,
      pressure_tolerance=characteristic_residual_tolerance,
      maximum_iterations=max(8, maximum_iterations),
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError):
    reference = None
  ####
  if reference is not None and reference.point_m is not None and reference.state is not None:
    initial = (
      reference.point_m[0],
      reference.point_m[1],
      reference.state.theta_rad,
      reference.state.mach,
    )
  else:
    initial = (
      max(start.x_m, previous_boundary.x_m) + max(0.1, start.y_m),
      max(target_centerline_y_m + 10.0 * position_tolerance_m, previous_boundary.y_m),
      0.5 * (start.theta_rad + previous_boundary.theta_rad),
      max(1.05, start.mach),
    )
  ####

  def residual(vector: Sequence[float]) -> tuple[float, float, float, float]:
    endpoint = CharacteristicState(
      x_m=float(vector[0]),
      y_m=float(vector[1]),
      theta_rad=float(vector[2]),
      mach=float(vector[3]),
      gamma=start.gamma,
    )
    geometry = _characteristic_geometry_residual(start, endpoint, family)
    compatibility = (
      endpoint.k_plus - start.k_plus - _compatibility_source(
        start,
        endpoint,
        gradient,
      )
    )
    total_pressure = _transport_total_pressure(
      start,
      start_total_pressure_Pa,
      (endpoint.x_m, endpoint.y_m),
      gradient,
    )
    static_pressure = total_pressure / (
      1.0 + 0.5 * (endpoint.gamma - 1.0) * endpoint.mach * endpoint.mach
    ) ** (endpoint.gamma / (endpoint.gamma - 1.0))
    pressure = log(static_pressure / ambient_pressure_Pa)
    boundary = _boundary_geometry_residual(previous_boundary, endpoint)
    return geometry, compatibility, pressure, boundary
  ####

  try:
    solved = least_squares(
      residual,
      initial,
      bounds=(
        (
          max(start.x_m, previous_boundary.x_m) + position_tolerance_m,
          target_centerline_y_m + position_tolerance_m,
          -2.5,
          1.0001,
        ),
        (
          start.x_m + 100.0,
          max(previous_boundary.y_m * 4.0, previous_boundary.y_m + 1.0),
          2.5,
          32.0,
        ),
      ),
      max_nfev=max(48, maximum_iterations * 24),
      xtol=1.0e-13,
      ftol=1.0e-13,
      gtol=1.0e-13,
      x_scale='jac',
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _segment_failure(
      family,
      MocEulerAmbientFirstWedgeEntropyCharacteristicSegmentStatus.SOLVER_FAILURE,
      f'ambient variable-entropy solve failed: {error}',
      start_state=start,
      start_total_pressure_Pa=start_total_pressure_Pa,
    )
  ####
  try:
    endpoint = CharacteristicState(
      x_m=float(solved.x[0]),
      y_m=float(solved.x[1]),
      theta_rad=float(solved.x[2]),
      mach=float(solved.x[3]),
      gamma=start.gamma,
    )
    geometry, compatibility, pressure, boundary = residual(solved.x)
    geometry = abs(geometry)
    compatibility = abs(compatibility)
    pressure = abs(pressure)
    boundary = abs(boundary)
    end_pressure = _transport_total_pressure(
      start,
      start_total_pressure_Pa,
      (endpoint.x_m, endpoint.y_m),
      gradient,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _segment_failure(
      family,
      MocEulerAmbientFirstWedgeEntropyCharacteristicSegmentStatus.SOLVER_FAILURE,
      f'ambient endpoint reconstruction failed: {error}',
      start_state=start,
      start_total_pressure_Pa=start_total_pressure_Pa,
      solver_iterations=int(getattr(solved, 'nfev', 0)),
      solver_success=bool(getattr(solved, 'success', False)),
    )
  ####
  if not bool(getattr(solved, 'success', False)):
    status = MocEulerAmbientFirstWedgeEntropyCharacteristicSegmentStatus.SOLVER_FAILURE
    message = 'ambient variable-entropy solve did not converge'
  elif geometry > characteristic_residual_tolerance or boundary > characteristic_residual_tolerance:
    status = MocEulerAmbientFirstWedgeEntropyCharacteristicSegmentStatus.GEOMETRY_FAILURE
    message = 'ambient characteristic or boundary tangent residual exceeded tolerance'
  elif compatibility > characteristic_residual_tolerance:
    status = MocEulerAmbientFirstWedgeEntropyCharacteristicSegmentStatus.COMPATIBILITY_FAILURE
    message = 'ambient variable-entropy compatibility residual exceeded tolerance'
  elif pressure > characteristic_residual_tolerance:
    status = MocEulerAmbientFirstWedgeEntropyCharacteristicSegmentStatus.PRESSURE_FAILURE
    message = 'ambient pressure residual exceeded tolerance'
  else:
    status = MocEulerAmbientFirstWedgeEntropyCharacteristicSegmentStatus.CONVERGED
    message = ''
  ####
  return _segment_failure(
    family,
    status,
    message,
    start_state=start,
    end_state=endpoint,
    start_total_pressure_Pa=start_total_pressure_Pa,
    end_total_pressure_Pa=end_pressure,
    geometry_residual=max(geometry, boundary),
    compatibility_residual=compatibility,
    pressure_residual=pressure,
    solver_iterations=int(getattr(solved, 'nfev', 0)),
    solver_success=bool(getattr(solved, 'success', False)),
  )
####


def _failure(
  status: MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationStatus,
  source_field: (
    MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult
    | MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationResult
    | None
  ),
  *,
  incoming_handoff: Sequence[MocChainBoundarySample] = (),
  source_pressure_gradient: tuple[float, float] | None = None,
  centerline_states: Sequence[CharacteristicState] = (),
  outer_states: Sequence[CharacteristicState] = (),
  terminal_centerline_state: CharacteristicState | None = None,
  centerline_total_pressure_Pa: Sequence[float] = (),
  outer_total_pressure_Pa: Sequence[float] = (),
  terminal_centerline_total_pressure_Pa: float | None = None,
  centerline_segments: Sequence[MocEulerAmbientFirstWedgeEntropyCharacteristicSegmentResult] = (),
  outer_segments: Sequence[MocEulerAmbientFirstWedgeEntropyCharacteristicSegmentResult] = (),
  terminal_segment: MocEulerAmbientFirstWedgeEntropyCharacteristicSegmentResult | None = None,
  cells: Sequence[MocCharacteristicCell] = (),
  cell_samples: Sequence[MocEulerAmbientFirstWedgeCellSample] = (),
  topology: MocTopologyResult | None = None,
  cell_euler_residuals: Sequence[float] = (),
  maximum_cell_euler_residual: float | None = None,
  maximum_geometry_residual: float | None = None,
  maximum_compatibility_residual: float | None = None,
  maximum_pressure_residual: float | None = None,
  reflection_anchor_verified: bool = False,
  alternating_seams_verified: bool = False,
  pressure_lineage_verified: bool = False,
  cell_euler_residuals_finite: bool = False,
  cell_euler_residuals_verified: bool = False,
  ambient_pressure_Pa: float | None = None,
  cycle_count: int = 0,
  target_centerline_y_m: float = 0.0,
  target_centerline_flow_angle_rad: float = 0.0,
  position_tolerance_m: float = 1.0e-8,
  characteristic_residual_tolerance: float = 1.0e-8,
  pressure_lineage_tolerance: float = 1.0e-8,
  cell_residual_tolerance: float = 1.0e-2,
  message: str,
) -> MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationResult:
  return MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationResult(
    status=status,
    source_field=source_field,
    incoming_handoff=tuple(incoming_handoff),
    source_pressure_gradient=source_pressure_gradient,
    centerline_states=tuple(centerline_states),
    outer_states=tuple(outer_states),
    terminal_centerline_state=terminal_centerline_state,
    centerline_total_pressure_Pa=tuple(centerline_total_pressure_Pa),
    outer_total_pressure_Pa=tuple(outer_total_pressure_Pa),
    terminal_centerline_total_pressure_Pa=terminal_centerline_total_pressure_Pa,
    centerline_segments=tuple(centerline_segments),
    outer_segments=tuple(outer_segments),
    terminal_segment=terminal_segment,
    cells=tuple(cells),
    cell_samples=tuple(cell_samples),
    topology=validate_moc_mesh(()) if topology is None else topology,
    cell_euler_residuals=tuple(cell_euler_residuals),
    maximum_cell_euler_residual=maximum_cell_euler_residual,
    maximum_geometry_residual=maximum_geometry_residual,
    maximum_compatibility_residual=maximum_compatibility_residual,
    maximum_pressure_residual=maximum_pressure_residual,
    reflection_anchor_verified=reflection_anchor_verified,
    alternating_seams_verified=alternating_seams_verified,
    pressure_lineage_verified=pressure_lineage_verified,
    cell_euler_residuals_finite=cell_euler_residuals_finite,
    cell_euler_residuals_verified=cell_euler_residuals_verified,
    ambient_pressure_Pa=ambient_pressure_Pa,
    cycle_count=cycle_count,
    target_centerline_y_m=target_centerline_y_m,
    target_centerline_flow_angle_rad=target_centerline_flow_angle_rad,
    position_tolerance_m=position_tolerance_m,
    characteristic_residual_tolerance=characteristic_residual_tolerance,
    pressure_lineage_tolerance=pressure_lineage_tolerance,
    cell_residual_tolerance=cell_residual_tolerance,
    message=message,
  )
####


def solve_euler_ambient_first_wedge_entropy_characteristic_continuation(
  field: (
    MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult
    | MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationResult
  ),
  incoming_handoff: Sequence[MocChainBoundarySample],
  ambient_pressure_Pa: float,
  *,
  cycle_count: int = 4,
  target_centerline_y_m: float = 0.0,
  target_centerline_flow_angle_rad: float = 0.0,
  position_tolerance_m: float = 1.0e-8,
  characteristic_residual_tolerance: float = 1.0e-8,
  pressure_lineage_tolerance: float = 1.0e-8,
  cell_residual_tolerance: float = 1.0e-2,
  maximum_iterations: int = 48,
) -> MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationResult:
  """Extend a variable-entropy ``C-`` front into a bounded source band.

  ``cycle_count`` is the number of new ambient-side rows.  The final
  centerline reflection is solved once more so the returned perimeter is an
  explicit, solved ``C-`` edge that a later continuation can consume.  The
  generated source band carries no shock jump; its conservative Euler gate
  therefore remains independent and promotion stays disabled.
  """

  if not isinstance(
    field,
    (
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult,
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationResult,
    ),
  ):
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationStatus.INVALID_INPUT,
      None,
      message=(
        'field must be an entropy-characteristic field or prior continuation '
        'result'
      ),
    )
  ####
  try:
    handoff = tuple(incoming_handoff)
  except TypeError:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationStatus.INVALID_INPUT,
      field,
      message='incoming_handoff must be iterable',
    )
  ####
  if any(not isinstance(sample, MocChainBoundarySample) for sample in handoff):
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationStatus.INVALID_INPUT,
      field,
      incoming_handoff=handoff,
      message='incoming_handoff must contain MocChainBoundarySample values',
    )
  ####
  if not field.local_consistency_verified or not field.state_sampling_available:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationStatus.FIELD_REQUIRED,
      field,
      incoming_handoff=handoff,
      message=(
        'continuation requires a locally consistent bounded entropy field or '
        'prior continuation'
      ),
    )
  ####
  if handoff != field.continuation_boundary or len(handoff) < 2:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationStatus.HANDOFF_FAILURE,
      field,
      incoming_handoff=handoff,
      message=(
        'incoming_handoff must exactly match the solver-owned source perimeter'
      ),
    )
  ####
  try:
    ambient_pressure = float(ambient_pressure_Pa)
    target_y = float(target_centerline_y_m)
    target_theta = float(target_centerline_flow_angle_rad)
    position_tolerance = float(position_tolerance_m)
    characteristic_tolerance = float(characteristic_residual_tolerance)
    pressure_tolerance = float(pressure_lineage_tolerance)
    cell_tolerance = float(cell_residual_tolerance)
  except (TypeError, ValueError):
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationStatus.INVALID_INPUT,
      field,
      incoming_handoff=handoff,
      message='continuation inputs must be numeric',
    )
  ####
  if not all(
    isfinite(value)
    for value in (
      ambient_pressure,
      target_y,
      target_theta,
      position_tolerance,
      characteristic_tolerance,
      pressure_tolerance,
      cell_tolerance,
    )
  ) or ambient_pressure <= 0.0 or any(
    value <= 0.0
    for value in (
      position_tolerance,
      characteristic_tolerance,
      pressure_tolerance,
      cell_tolerance,
    )
  ):
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationStatus.INVALID_INPUT,
      field,
      incoming_handoff=handoff,
      message='continuation inputs must be finite and ambient pressure positive',
    )
  ####
  if (
    isinstance(cycle_count, bool)
    or not isinstance(cycle_count, int)
    or cycle_count < 1
  ):
    raise ValueError('cycle_count must be a positive integer')
  ####
  if (
    isinstance(maximum_iterations, bool)
    or not isinstance(maximum_iterations, int)
    or maximum_iterations < 1
  ):
    raise ValueError('maximum_iterations must be a positive integer')
  ####
  if target_y >= handoff[0].state.y_m - position_tolerance:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationStatus.INVALID_INPUT,
      field,
      incoming_handoff=handoff,
      source_pressure_gradient=field.source_pressure_gradient,
      cycle_count=cycle_count,
      target_centerline_y_m=target_y,
      target_centerline_flow_angle_rad=target_theta,
      position_tolerance_m=position_tolerance,
      characteristic_residual_tolerance=characteristic_tolerance,
      pressure_lineage_tolerance=pressure_tolerance,
      cell_residual_tolerance=cell_tolerance,
      message='target centerline must be below the first incoming outer sample',
    )
  ####
  gradient = field.source_pressure_gradient
  if (
    gradient is None
    or len(gradient) != 2
    or not all(isfinite(value) for value in gradient)
  ):
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationStatus.PRESSURE_LINEAGE_FAILURE,
      field,
      incoming_handoff=handoff,
      cycle_count=cycle_count,
      target_centerline_y_m=target_y,
      target_centerline_flow_angle_rad=target_theta,
      position_tolerance_m=position_tolerance,
      characteristic_residual_tolerance=characteristic_tolerance,
      pressure_lineage_tolerance=pressure_tolerance,
      cell_residual_tolerance=cell_tolerance,
      message='source field does not retain a finite variable-entropy gradient',
    )
  ####

  centerline_states: list[CharacteristicState] = []
  outer_states: list[CharacteristicState] = []
  centerline_pressures: list[float] = []
  outer_pressures: list[float] = []
  centerline_segments: list[
    MocEulerAmbientFirstWedgeEntropyCharacteristicSegmentResult
  ] = []
  outer_segments: list[
    MocEulerAmbientFirstWedgeEntropyCharacteristicSegmentResult
  ] = []
  previous_outer = handoff[0].state
  previous_outer_pressure = handoff[0].total_pressure_Pa
  reflection_anchor_verified = False
  maximum_geometry: float | None = None
  maximum_compatibility: float | None = None
  maximum_pressure: float | None = None

  for index in range(cycle_count):
    expected_axis = handoff[-1] if index == 0 else None
    centerline_segment = _solve_centerline_segment(
      previous_outer,
      previous_outer_pressure,
      gradient,
      target_y,
      target_theta,
      position_tolerance_m=position_tolerance,
      characteristic_residual_tolerance=characteristic_tolerance,
      maximum_iterations=maximum_iterations,
      expected_end=expected_axis,
    )
    centerline_segments.append(centerline_segment)
    maximum_geometry = max(
      maximum_geometry or 0.0,
      centerline_segment.geometry_residual or 0.0,
    )
    maximum_compatibility = max(
      maximum_compatibility or 0.0,
      centerline_segment.compatibility_residual or 0.0,
    )
    maximum_pressure = max(
      maximum_pressure or 0.0,
      centerline_segment.pressure_residual or 0.0,
    )
    if not centerline_segment.converged or centerline_segment.end_state is None:
      status = (
        MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationStatus
        .REFLECTION_FAILURE
      )
      return _failure(
        status,
        field,
        incoming_handoff=handoff,
        source_pressure_gradient=gradient,
        centerline_states=centerline_states,
        outer_states=outer_states,
        centerline_total_pressure_Pa=centerline_pressures,
        outer_total_pressure_Pa=outer_pressures,
        centerline_segments=centerline_segments,
        outer_segments=outer_segments,
        maximum_geometry_residual=maximum_geometry,
        maximum_compatibility_residual=maximum_compatibility,
        maximum_pressure_residual=maximum_pressure,
        reflection_anchor_verified=reflection_anchor_verified,
        cycle_count=cycle_count,
        target_centerline_y_m=target_y,
        target_centerline_flow_angle_rad=target_theta,
        position_tolerance_m=position_tolerance,
        characteristic_residual_tolerance=characteristic_tolerance,
        pressure_lineage_tolerance=pressure_tolerance,
        cell_residual_tolerance=cell_tolerance,
        message=f'centerline reflection {index} failed: {centerline_segment.message}',
      )
    ####
    axis_state = centerline_segment.end_state
    axis_pressure = centerline_segment.end_total_pressure_Pa
    assert axis_pressure is not None
    if index == 0:
      reflection_anchor_verified = bool(
        expected_axis is not None
        and _state_matches(
          axis_state,
          expected_axis.state,
          position_tolerance_m=position_tolerance,
          state_tolerance=characteristic_tolerance,
        )
        and abs(log(axis_pressure / expected_axis.total_pressure_Pa))
        <= pressure_tolerance
      )
      if not reflection_anchor_verified:
        return _failure(
          MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationStatus.PRESSURE_LINEAGE_FAILURE,
          field,
          incoming_handoff=handoff,
          source_pressure_gradient=gradient,
          centerline_states=(axis_state,),
          centerline_total_pressure_Pa=(axis_pressure,),
          centerline_segments=centerline_segments,
          maximum_geometry_residual=maximum_geometry,
          maximum_compatibility_residual=maximum_compatibility,
          maximum_pressure_residual=maximum_pressure,
          cycle_count=cycle_count,
          target_centerline_y_m=target_y,
          target_centerline_flow_angle_rad=target_theta,
          position_tolerance_m=position_tolerance,
          characteristic_residual_tolerance=characteristic_tolerance,
          pressure_lineage_tolerance=pressure_tolerance,
          cell_residual_tolerance=cell_tolerance,
          message='variable-entropy reflection did not reproduce the exact incoming axis anchor',
        )
      ####
    ####
    centerline_states.append(axis_state)
    centerline_pressures.append(axis_pressure)

    outer_segment = _solve_ambient_segment(
      axis_state,
      axis_pressure,
      previous_outer,
      gradient,
      ambient_pressure,
      target_y,
      position_tolerance_m=position_tolerance,
      characteristic_residual_tolerance=characteristic_tolerance,
      maximum_iterations=maximum_iterations,
    )
    outer_segments.append(outer_segment)
    maximum_geometry = max(
      maximum_geometry or 0.0,
      outer_segment.geometry_residual or 0.0,
    )
    maximum_compatibility = max(
      maximum_compatibility or 0.0,
      outer_segment.compatibility_residual or 0.0,
    )
    maximum_pressure = max(
      maximum_pressure or 0.0,
      outer_segment.pressure_residual or 0.0,
    )
    if not outer_segment.converged or outer_segment.end_state is None:
      return _failure(
        MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationStatus.AMBIENT_BOUNDARY_FAILURE,
        field,
        incoming_handoff=handoff,
        source_pressure_gradient=gradient,
        centerline_states=centerline_states,
        outer_states=outer_states,
        centerline_total_pressure_Pa=centerline_pressures,
        outer_total_pressure_Pa=outer_pressures,
        centerline_segments=centerline_segments,
        outer_segments=outer_segments,
        maximum_geometry_residual=maximum_geometry,
        maximum_compatibility_residual=maximum_compatibility,
        maximum_pressure_residual=maximum_pressure,
        reflection_anchor_verified=reflection_anchor_verified,
        cycle_count=cycle_count,
        target_centerline_y_m=target_y,
        target_centerline_flow_angle_rad=target_theta,
        position_tolerance_m=position_tolerance,
        characteristic_residual_tolerance=characteristic_tolerance,
        pressure_lineage_tolerance=pressure_tolerance,
        cell_residual_tolerance=cell_tolerance,
        message=f'ambient boundary continuation {index} failed: {outer_segment.message}',
      )
    ####
    outer_state = outer_segment.end_state
    outer_pressure = outer_segment.end_total_pressure_Pa
    assert outer_pressure is not None
    outer_states.append(outer_state)
    outer_pressures.append(outer_pressure)
    previous_outer = outer_state
    previous_outer_pressure = outer_pressure
  ####

  terminal_segment = _solve_centerline_segment(
    outer_states[-1],
    outer_pressures[-1],
    gradient,
    target_y,
    target_theta,
    position_tolerance_m=position_tolerance,
    characteristic_residual_tolerance=characteristic_tolerance,
    maximum_iterations=maximum_iterations,
  )
  maximum_geometry = max(
    maximum_geometry or 0.0,
    terminal_segment.geometry_residual or 0.0,
  )
  maximum_compatibility = max(
    maximum_compatibility or 0.0,
    terminal_segment.compatibility_residual or 0.0,
  )
  maximum_pressure = max(
    maximum_pressure or 0.0,
    terminal_segment.pressure_residual or 0.0,
  )
  if not terminal_segment.converged or terminal_segment.end_state is None:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationStatus.REFLECTION_FAILURE,
      field,
      incoming_handoff=handoff,
      source_pressure_gradient=gradient,
      centerline_states=centerline_states,
      outer_states=outer_states,
      centerline_total_pressure_Pa=centerline_pressures,
      outer_total_pressure_Pa=outer_pressures,
      centerline_segments=centerline_segments,
      outer_segments=outer_segments,
      terminal_segment=terminal_segment,
      maximum_geometry_residual=maximum_geometry,
      maximum_compatibility_residual=maximum_compatibility,
      maximum_pressure_residual=maximum_pressure,
      reflection_anchor_verified=reflection_anchor_verified,
      cycle_count=cycle_count,
      target_centerline_y_m=target_y,
      target_centerline_flow_angle_rad=target_theta,
      position_tolerance_m=position_tolerance,
      characteristic_residual_tolerance=characteristic_tolerance,
      pressure_lineage_tolerance=pressure_tolerance,
      cell_residual_tolerance=cell_tolerance,
      message=f'terminal centerline reflection failed: {terminal_segment.message}',
    )
  ####
  terminal_axis = terminal_segment.end_state
  terminal_axis_pressure = terminal_segment.end_total_pressure_Pa
  assert terminal_axis_pressure is not None

  cells: list[MocCharacteristicCell] = []
  samples: list[MocEulerAmbientFirstWedgeCellSample] = []
  try:
    for index in range(cycle_count - 1):
      first_vertices = (
        (centerline_states[index].x_m, centerline_states[index].y_m),
        (centerline_states[index + 1].x_m, centerline_states[index + 1].y_m),
        (outer_states[index].x_m, outer_states[index].y_m),
      )
      first_states = (
        centerline_states[index],
        centerline_states[index + 1],
        outer_states[index],
      )
      first_pressures = (
        centerline_pressures[index],
        centerline_pressures[index + 1],
        outer_pressures[index],
      )
      cells.append(
        MocCharacteristicCell(
          cell_index=len(cells),
          cell_kind='entropy-alternating-axis-step',
          vertices_xr_m=first_vertices,
          centerline_indices=(),
          boundary_indices=(),
        )
      )
      samples.append(
        MocEulerAmbientFirstWedgeCellSample(
          vertices_xr_m=first_vertices,
          states=first_states,
          total_pressure_Pa=first_pressures,
        )
      )
      second_vertices = (
        (centerline_states[index + 1].x_m, centerline_states[index + 1].y_m),
        (outer_states[index + 1].x_m, outer_states[index + 1].y_m),
        (outer_states[index].x_m, outer_states[index].y_m),
      )
      second_states = (
        centerline_states[index + 1],
        outer_states[index + 1],
        outer_states[index],
      )
      second_pressures = (
        centerline_pressures[index + 1],
        outer_pressures[index + 1],
        outer_pressures[index],
      )
      cells.append(
        MocCharacteristicCell(
          cell_index=len(cells),
          cell_kind='entropy-alternating-boundary-step',
          vertices_xr_m=second_vertices,
          centerline_indices=(),
          boundary_indices=(),
        )
      )
      samples.append(
        MocEulerAmbientFirstWedgeCellSample(
          vertices_xr_m=second_vertices,
          states=second_states,
          total_pressure_Pa=second_pressures,
        )
      )
    ####
    terminal_vertices = (
      (centerline_states[-1].x_m, centerline_states[-1].y_m),
      (terminal_axis.x_m, terminal_axis.y_m),
      (outer_states[-1].x_m, outer_states[-1].y_m),
    )
    terminal_states = (centerline_states[-1], terminal_axis, outer_states[-1])
    terminal_pressures = (
      centerline_pressures[-1],
      terminal_axis_pressure,
      outer_pressures[-1],
    )
    cells.append(
      MocCharacteristicCell(
        cell_index=len(cells),
        cell_kind='entropy-alternating-terminal-axis-step',
        vertices_xr_m=terminal_vertices,
        centerline_indices=(),
        boundary_indices=(),
      )
    )
    samples.append(
      MocEulerAmbientFirstWedgeCellSample(
        vertices_xr_m=terminal_vertices,
        states=terminal_states,
        total_pressure_Pa=terminal_pressures,
      )
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationStatus.TOPOLOGY_FAILURE,
      field,
      incoming_handoff=handoff,
      source_pressure_gradient=gradient,
      centerline_states=centerline_states,
      outer_states=outer_states,
      terminal_centerline_state=terminal_axis,
      centerline_total_pressure_Pa=centerline_pressures,
      outer_total_pressure_Pa=outer_pressures,
      terminal_centerline_total_pressure_Pa=terminal_axis_pressure,
      centerline_segments=centerline_segments,
      outer_segments=outer_segments,
      terminal_segment=terminal_segment,
      cells=cells,
      cell_samples=samples,
      maximum_geometry_residual=maximum_geometry,
      maximum_compatibility_residual=maximum_compatibility,
      maximum_pressure_residual=maximum_pressure,
      reflection_anchor_verified=reflection_anchor_verified,
      cycle_count=cycle_count,
      target_centerline_y_m=target_y,
      target_centerline_flow_angle_rad=target_theta,
      position_tolerance_m=position_tolerance,
      characteristic_residual_tolerance=characteristic_tolerance,
      pressure_lineage_tolerance=pressure_tolerance,
      cell_residual_tolerance=cell_tolerance,
      message=f'continuation cell assembly failed: {error}',
    )
  ####
  topology = validate_moc_mesh(cells)
  if not topology.connected or not topology.forms_closed_zone or topology.nonmanifold_edge_count:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationStatus.TOPOLOGY_FAILURE,
      field,
      incoming_handoff=handoff,
      source_pressure_gradient=gradient,
      centerline_states=centerline_states,
      outer_states=outer_states,
      terminal_centerline_state=terminal_axis,
      centerline_total_pressure_Pa=centerline_pressures,
      outer_total_pressure_Pa=outer_pressures,
      terminal_centerline_total_pressure_Pa=terminal_axis_pressure,
      centerline_segments=centerline_segments,
      outer_segments=outer_segments,
      terminal_segment=terminal_segment,
      cells=cells,
      cell_samples=samples,
      topology=topology,
      maximum_geometry_residual=maximum_geometry,
      maximum_compatibility_residual=maximum_compatibility,
      maximum_pressure_residual=maximum_pressure,
      reflection_anchor_verified=reflection_anchor_verified,
      cycle_count=cycle_count,
      target_centerline_y_m=target_y,
      target_centerline_flow_angle_rad=target_theta,
      position_tolerance_m=position_tolerance,
      characteristic_residual_tolerance=characteristic_tolerance,
      pressure_lineage_tolerance=pressure_tolerance,
      cell_residual_tolerance=cell_tolerance,
      message=f'continuation topology failed: {topology.message}',
    )
  ####

  cell_residuals: list[float] = []
  try:
    cell_residuals = [
      _cell_euler_residual(sample.vertices_xr_m, sample.states, sample.total_pressure_Pa)
      for sample in samples
    ]
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationStatus.EULER_RESIDUAL_FAILURE,
      field,
      incoming_handoff=handoff,
      source_pressure_gradient=gradient,
      centerline_states=centerline_states,
      outer_states=outer_states,
      terminal_centerline_state=terminal_axis,
      centerline_total_pressure_Pa=centerline_pressures,
      outer_total_pressure_Pa=outer_pressures,
      terminal_centerline_total_pressure_Pa=terminal_axis_pressure,
      centerline_segments=centerline_segments,
      outer_segments=outer_segments,
      terminal_segment=terminal_segment,
      cells=cells,
      cell_samples=samples,
      topology=topology,
      maximum_geometry_residual=maximum_geometry,
      maximum_compatibility_residual=maximum_compatibility,
      maximum_pressure_residual=maximum_pressure,
      reflection_anchor_verified=reflection_anchor_verified,
      cycle_count=cycle_count,
      target_centerline_y_m=target_y,
      target_centerline_flow_angle_rad=target_theta,
      position_tolerance_m=position_tolerance,
      characteristic_residual_tolerance=characteristic_tolerance,
      pressure_lineage_tolerance=pressure_tolerance,
      cell_residual_tolerance=cell_tolerance,
      message=f'continuation Euler residual evaluation failed: {error}',
    )
  ####
  residuals_finite = bool(cell_residuals and all(isfinite(value) for value in cell_residuals))
  maximum_cell_residual = max(cell_residuals, default=None)
  residuals_verified = bool(
    residuals_finite
    and maximum_cell_residual is not None
    and maximum_cell_residual <= cell_tolerance
  )
  alternating_verified = bool(
    all(segment.converged for segment in centerline_segments)
    and all(segment.converged for segment in outer_segments)
    and terminal_segment.converged
    and all(
      current.x_m > previous.x_m + position_tolerance
      for previous, current in zip(centerline_states, centerline_states[1:])
    )
    and all(
      current.x_m > previous.x_m + position_tolerance
      for previous, current in zip(outer_states, outer_states[1:])
    )
  )
  pressure_verified = bool(
    all(
      segment.pressure_residual is not None
      and segment.pressure_residual <= pressure_tolerance
      for segment in (*centerline_segments, *outer_segments, terminal_segment)
    )
    and all(pressure > ambient_pressure for pressure in outer_pressures)
  )
  status = (
    MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationStatus
    .CONVERGED_BOUNDED_CONTINUATION
    if alternating_verified and pressure_verified
    else MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationStatus
    .PRESSURE_LINEAGE_FAILURE
  )
  message = (
    'variable-entropy alternating source band converged with an explicit '
    'outgoing C- front; conservative Euler shock-cell closure remains pending'
    if status
    is MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationStatus
    .CONVERGED_BOUNDED_CONTINUATION
    else 'variable-entropy continuation did not satisfy its seam or pressure-lineage gates'
  )
  return _failure(
    status,
    field,
    incoming_handoff=handoff,
    source_pressure_gradient=gradient,
    centerline_states=centerline_states,
    outer_states=outer_states,
    terminal_centerline_state=terminal_axis,
    centerline_total_pressure_Pa=centerline_pressures,
    outer_total_pressure_Pa=outer_pressures,
    terminal_centerline_total_pressure_Pa=terminal_axis_pressure,
    centerline_segments=centerline_segments,
    outer_segments=outer_segments,
    terminal_segment=terminal_segment,
    cells=cells,
    cell_samples=samples,
    topology=topology,
    cell_euler_residuals=cell_residuals,
    maximum_cell_euler_residual=maximum_cell_residual,
    maximum_geometry_residual=maximum_geometry,
    maximum_compatibility_residual=maximum_compatibility,
    maximum_pressure_residual=maximum_pressure,
    reflection_anchor_verified=reflection_anchor_verified,
    alternating_seams_verified=alternating_verified,
    pressure_lineage_verified=pressure_verified,
    cell_euler_residuals_finite=residuals_finite,
    cell_euler_residuals_verified=residuals_verified,
    ambient_pressure_Pa=ambient_pressure,
    cycle_count=cycle_count,
    target_centerline_y_m=target_y,
    target_centerline_flow_angle_rad=target_theta,
    position_tolerance_m=position_tolerance,
    characteristic_residual_tolerance=characteristic_tolerance,
    pressure_lineage_tolerance=pressure_tolerance,
    cell_residual_tolerance=cell_tolerance,
    message=message,
  )
####
