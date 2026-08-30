"""Bounded shock coupling for the entropy-characteristic field lane.

The solver-owned entropy field exposes a finite state/pressure sampler and an
exact diagnostic perimeter.  This module uses those callbacks for one real
attached-shock march.  It deliberately stops when the generated path leaves
the finite field; no extrapolated upstream state, pressure reset, or physical
``MocChainCell`` is created here.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import hypot, isfinite
from typing import Any, Sequence

from exhaust_plume.models.moc.chain import (
  MocChainBoundarySample,
  MocChainTerminationDecision,
  MocChainTerminationReason,
)
from exhaust_plume.models.moc.euler_entropy_characteristic_field import (
  MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult,
)
from exhaust_plume.models.moc.free_boundary import (
  MocFreeBoundaryShockResult,
  MocFreeBoundaryShockStatus,
  solve_marched_attached_shock_field,
)
from exhaust_plume.models.moc.primitives import CharacteristicState
from exhaust_plume.util.aero.shock_validity import ShockBranch

__all__ = (
  'MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingStatus',
  'MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingResult',
  'solve_euler_ambient_first_wedge_entropy_characteristic_shock_coupling',
)


class MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingStatus(str, Enum):
  """Outcome of a bounded next-shock coupling attempt."""

  CONVERGED_BOUNDED_ATTEMPT = (
    'converged_bounded_entropy_characteristic_shock_coupling_attempt'
  )
  INVALID_INPUT = 'invalid_input'
  FIELD_REQUIRED = 'entropy_characteristic_field_required'
  HANDOFF_FAILURE = 'entropy_characteristic_handoff_failure'
  UPSTREAM_FIELD_BOUNDARY = 'entropy_characteristic_upstream_field_boundary'
  SHOCK_SOLVER_FAILURE = 'entropy_characteristic_shock_solver_failure'


def _finite_point(
  point_m: Sequence[float],
  *,
  label: str,
) -> tuple[float, float] | None:
  try:
    point = (float(point_m[0]), float(point_m[1]))
  except (IndexError, TypeError, ValueError):
    return None
  if not all(isfinite(value) for value in point):
    return None
  return point


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


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingResult:
  """A bounded shock attempt against one entropy-characteristic field.

  ``converged`` means that the attached-shock marcher completed while every
  upstream sample remained inside the supplied field.  It does not mean that
  the reflected/free boundary or a physical shock-cell perimeter is closed.
  """

  status: MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingStatus
  field: MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult | None
  shock: MocFreeBoundaryShockResult | None
  incoming_handoff: tuple[MocChainBoundarySample, ...]
  covered_sample_count: int
  first_missing_sample_index: int | None
  maximum_state_residual: float | None
  maximum_pressure_residual: float | None
  position_tolerance_m: float
  state_tolerance: float
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingStatus,
    ):
      raise TypeError(
        'status must be a '
        'MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingStatus'
      )
    if self.field is not None and not isinstance(
      self.field,
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult,
    ):
      raise TypeError(
        'field must be a '
        'MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult or None'
      )
    if self.shock is not None and not isinstance(
      self.shock,
      MocFreeBoundaryShockResult,
    ):
      raise TypeError('shock must be a MocFreeBoundaryShockResult or None')
    handoff = tuple(self.incoming_handoff)
    if any(not isinstance(sample, MocChainBoundarySample) for sample in handoff):
      raise TypeError(
        'incoming_handoff must contain MocChainBoundarySample values'
      )
    object.__setattr__(self, 'incoming_handoff', handoff)
    if (
      isinstance(self.covered_sample_count, bool)
      or not isinstance(self.covered_sample_count, int)
      or self.covered_sample_count < 0
    ):
      raise ValueError('covered_sample_count must be a nonnegative integer')
    if self.first_missing_sample_index is not None and (
      isinstance(self.first_missing_sample_index, bool)
      or not isinstance(self.first_missing_sample_index, int)
      or self.first_missing_sample_index < 0
    ):
      raise ValueError(
        'first_missing_sample_index must be a nonnegative integer or None'
      )
    for name in ('maximum_state_residual', 'maximum_pressure_residual'):
      value = getattr(self, name)
      if value is None:
        continue
      numeric = float(value)
      if not isfinite(numeric) or numeric < 0.0:
        raise ValueError(f'{name} must be finite and nonnegative when supplied')
      object.__setattr__(self, name, numeric)
    for name in ('position_tolerance_m', 'state_tolerance'):
      value = float(getattr(self, name))
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      object.__setattr__(self, name, value)
    object.__setattr__(self, 'message', str(self.message))

  @property
  def path_coverage_verified(self) -> bool:
    """Whether every retained shock sample has bounded upstream data."""

    return bool(
      self.shock is not None
      and self.shock.converged
      and self.covered_sample_count == self.shock.sample_count
      and self.first_missing_sample_index is None
    )

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      is MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingStatus
      .CONVERGED_BOUNDED_ATTEMPT
      and self.path_coverage_verified
    )

  @property
  def physical_closure_verified(self) -> bool:
    """The bounded probe does not solve the reflected/free boundary."""

    return False

  @property
  def chain_promotion_blocked(self) -> bool:
    return True

  @property
  def production_claim_allowed(self) -> bool:
    return False

  def as_chain_termination_decision(self) -> MocChainTerminationDecision:
    """Map the attempt to a non-physical continuation decision."""

    if self.status is (
      MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingStatus
      .INVALID_INPUT
    ):
      reason = MocChainTerminationReason.INVALID_INPUT
    elif self.status is (
      MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingStatus
      .UPSTREAM_FIELD_BOUNDARY
    ):
      reason = MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
    elif self.status is (
      MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingStatus
      .SHOCK_SOLVER_FAILURE
    ):
      reason = MocChainTerminationReason.SOLVER_ERROR
    elif self.status is (
      MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingStatus
      .HANDOFF_FAILURE
    ):
      reason = MocChainTerminationReason.STATE_NOT_CARRIED
    else:
      reason = MocChainTerminationReason.FIDELITY_NOT_ALLOWED
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=reason,
      message=self.message,
      diagnostics={
        'coupling_status': self.status.value,
        'covered_sample_count': self.covered_sample_count,
        'first_missing_sample_index': self.first_missing_sample_index,
        'path_coverage_verified': self.path_coverage_verified,
        'incoming_handoff_sample_count': len(self.incoming_handoff),
        'physical_closure_verified': False,
        'chain_promotion_blocked': True,
        'production_claim_allowed': False,
        'required_next_gate': (
          'reflected-free-boundary-coupling-and-independent-euler-validation-'
          'before-continued-shock-cell-chain'
        ),
      },
    )

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'path_coverage_verified': self.path_coverage_verified,
      'covered_sample_count': self.covered_sample_count,
      'first_missing_sample_index': self.first_missing_sample_index,
      'maximum_state_residual': self.maximum_state_residual,
      'maximum_pressure_residual': self.maximum_pressure_residual,
      'incoming_handoff_sample_count': len(self.incoming_handoff),
      'shock': None if self.shock is None else self.shock.as_report(),
      'physical_closure_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'position_tolerance_m': self.position_tolerance_m,
      'state_tolerance': self.state_tolerance,
      'chain_termination_decision': (
        self.as_chain_termination_decision().as_report()
      ),
      'message': self.message,
    }


def _failure(
  status: MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingStatus,
  field: MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult | None,
  *,
  incoming_handoff: Sequence[MocChainBoundarySample] = (),
  position_tolerance_m: float = 1.0e-10,
  state_tolerance: float = 1.0e-8,
  message: str,
) -> MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingResult:
  return MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingResult(
    status=status,
    field=field,
    shock=None,
    incoming_handoff=tuple(incoming_handoff),
    covered_sample_count=0,
    first_missing_sample_index=None,
    maximum_state_residual=None,
    maximum_pressure_residual=None,
    position_tolerance_m=position_tolerance_m,
    state_tolerance=state_tolerance,
    message=message,
  )


def solve_euler_ambient_first_wedge_entropy_characteristic_shock_coupling(
  field: MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult,
  incoming_handoff: Sequence[MocChainBoundarySample],
  start_point_m: tuple[float, float],
  *,
  target_centerline_y_m: float = 0.0,
  downstream_flow_angle_at: Any | None = None,
  downstream_flow_angle_rad: float | None = None,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-10,
  state_tolerance: float = 1.0e-8,
  invariant_tolerance: float = 1.0e-10,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
) -> MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingResult:
  """Attempt one attached shock using only a bounded entropy field.

  The first shock point must be the first point of the solver-owned
  continuation perimeter.  The exact perimeter is carried separately as a
  handoff and is never treated as an axial section or as a shock curve.
  """

  if not isinstance(
    field,
    MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult,
  ):
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingStatus
      .INVALID_INPUT,
      None,
      message='field must be a MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult',
    )
  try:
    handoff = tuple(incoming_handoff)
  except TypeError:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingStatus
      .INVALID_INPUT,
      field,
      message='incoming_handoff must be an iterable of MocChainBoundarySample values',
    )
  if any(not isinstance(sample, MocChainBoundarySample) for sample in handoff):
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingStatus
      .INVALID_INPUT,
      field,
      message='incoming_handoff must contain MocChainBoundarySample values',
    )
  if not field.state_sampling_available:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingStatus
      .FIELD_REQUIRED,
      field,
      incoming_handoff=handoff,
      message=(
        'entropy-characteristic shock coupling requires a locally consistent '
        'field with a bounded state sampler'
      ),
    )
  if handoff != field.continuation_boundary:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingStatus
      .HANDOFF_FAILURE,
      field,
      incoming_handoff=handoff,
      message=(
        'incoming_handoff must exactly match the field continuation perimeter'
      ),
    )
  if not handoff:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingStatus
      .HANDOFF_FAILURE,
      field,
      incoming_handoff=handoff,
      message='field continuation perimeter is empty',
    )
  point = _finite_point(start_point_m, label='start_point_m')
  if point is None:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingStatus
      .INVALID_INPUT,
      field,
      incoming_handoff=handoff,
      message='start_point_m must contain two finite coordinates',
    )
  if not isfinite(float(target_centerline_y_m)):
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingStatus
      .INVALID_INPUT,
      field,
      incoming_handoff=handoff,
      message='target_centerline_y_m must be finite',
    )
  if hypot(point[0] - handoff[0].state.x_m, point[1] - handoff[0].state.y_m) > (
    float(position_tolerance_m)
  ):
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingStatus
      .HANDOFF_FAILURE,
      field,
      incoming_handoff=handoff,
      message=(
        'start_point_m must coincide with the first solver-owned continuation '
        'perimeter sample'
      ),
    )
  try:
    position_tolerance = float(position_tolerance_m)
    state_tolerance_value = float(state_tolerance)
  except (TypeError, ValueError):
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingStatus
      .INVALID_INPUT,
      field,
      incoming_handoff=handoff,
      message='shock coupling tolerances must be numeric',
    )
  if (
    not isfinite(position_tolerance)
    or position_tolerance <= 0.0
    or not isfinite(state_tolerance_value)
    or state_tolerance_value <= 0.0
  ):
    raise ValueError('shock coupling tolerances must be finite and positive')
  if (downstream_flow_angle_at is None) == (downstream_flow_angle_rad is None):
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingStatus
      .INVALID_INPUT,
      field,
      incoming_handoff=handoff,
      position_tolerance_m=position_tolerance,
      state_tolerance=state_tolerance_value,
      message='supply exactly one downstream flow-angle provider',
    )
  if not isinstance(branch, ShockBranch):
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingStatus
      .INVALID_INPUT,
      field,
      incoming_handoff=handoff,
      position_tolerance_m=position_tolerance,
      state_tolerance=state_tolerance_value,
      message='branch must be a ShockBranch',
    )

  start_state = field.state_at(
    point,
    position_tolerance_m=position_tolerance,
  )
  start_pressure = field.static_pressure_at(
    point,
    position_tolerance_m=position_tolerance,
  )
  if start_state is None or start_pressure is None:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingStatus
      .UPSTREAM_FIELD_BOUNDARY,
      field,
      incoming_handoff=handoff,
      position_tolerance_m=position_tolerance,
      state_tolerance=state_tolerance_value,
      message=(
        'shock start point is outside the bounded entropy-characteristic '
        'field; no upstream extrapolation was used'
      ),
    )

  try:
    shock = solve_marched_attached_shock_field(
      field.state_at,
      field.static_pressure_at,
      point,
      target_centerline_y_m=float(target_centerline_y_m),
      downstream_flow_angle_at=downstream_flow_angle_at,
      downstream_flow_angle_rad=downstream_flow_angle_rad,
      incoming_handoff=handoff,
      sample_count=sample_count,
      branch=branch,
      position_tolerance_m=position_tolerance,
      invariant_tolerance=invariant_tolerance,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      maximum_segment_iterations=maximum_segment_iterations,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingStatus
      .SHOCK_SOLVER_FAILURE,
      field,
      incoming_handoff=handoff,
      position_tolerance_m=position_tolerance,
      state_tolerance=state_tolerance_value,
      message=f'bounded entropy-characteristic shock coupling raised: {error}',
    )

  state_residuals: list[float] = []
  pressure_residuals: list[float] = []
  covered_count = 0
  first_missing: int | None = None
  for index, (point_value, upstream_state, upstream_pressure) in enumerate(
    zip(
      shock.shock_points_m,
      shock.upstream_states,
      shock.upstream_pressure_Pa,
      strict=True,
    )
  ):
    sampled_state = field.state_at(
      point_value,
      position_tolerance_m=position_tolerance,
    )
    sampled_pressure = field.static_pressure_at(
      point_value,
      position_tolerance_m=position_tolerance,
    )
    if sampled_state is None or sampled_pressure is None:
      first_missing = index
      break
    state_residuals.append(
      max(
        abs(sampled_state.x_m - upstream_state.x_m),
        abs(sampled_state.y_m - upstream_state.y_m),
        abs(sampled_state.theta_rad - upstream_state.theta_rad),
        abs(sampled_state.mach - upstream_state.mach),
        abs(sampled_state.gamma - upstream_state.gamma),
      )
    )
    pressure_residuals.append(abs(sampled_pressure - upstream_pressure))
    if not _state_matches(
      sampled_state,
      upstream_state,
      position_tolerance_m=position_tolerance,
      state_tolerance=state_tolerance_value,
    ):
      first_missing = index
      break
    if abs(sampled_pressure - upstream_pressure) > state_tolerance_value * max(
      1.0,
      abs(sampled_pressure),
      abs(upstream_pressure),
    ):
      first_missing = index
      break
    covered_count += 1

  maximum_state_residual = max(state_residuals, default=None)
  maximum_pressure_residual = max(pressure_residuals, default=None)
  if shock.status is MocFreeBoundaryShockStatus.UPSTREAM_FIELD_FAILURE:
    if first_missing is None:
      first_missing = shock.failed_sample_index
    status = (
      MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingStatus
      .UPSTREAM_FIELD_BOUNDARY
    )
    message = (
      'attached-shock march reached the finite entropy-characteristic field '
      'boundary; no upstream extrapolation was used'
    )
  elif not shock.converged:
    status = (
      MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingStatus
      .SHOCK_SOLVER_FAILURE
    )
    message = f'bounded attached-shock solve did not converge: {shock.message}'
  elif first_missing is not None:
    status = (
      MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingStatus
      .UPSTREAM_FIELD_BOUNDARY
    )
    message = (
      'independent shock-path sampling found a point outside or inconsistent '
      'with the bounded entropy-characteristic field'
    )
  else:
    status = (
      MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingStatus
      .CONVERGED_BOUNDED_ATTEMPT
    )
    message = (
      'attached shock remained inside the bounded entropy-characteristic '
      'field; reflected/free-boundary closure is still open'
    )
  return MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingResult(
    status=status,
    field=field,
    shock=shock,
    incoming_handoff=handoff,
    covered_sample_count=covered_count,
    first_missing_sample_index=first_missing,
    maximum_state_residual=maximum_state_residual,
    maximum_pressure_residual=maximum_pressure_residual,
    position_tolerance_m=position_tolerance,
    state_tolerance=state_tolerance_value,
    message=message,
  )
