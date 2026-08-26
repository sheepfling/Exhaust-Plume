"""Boundary-conditioned shock closure for the isolated planar MOC lane.

The source-strip and marched-shock primitives deliberately keep their
boundary conditions explicit.  This module adds one narrow research solver:
it shoots a constant downstream characteristic invariant until the generated
shock reaches a requested centerline flow angle.  The upstream state and
pressure still come only from a converged, domain-bounded source strip, and a
candidate is promoted only when the existing attached-shock fit and closed
post-shock characteristic-field gates both pass.

Constant-invariant shooting is an executable coupling boundary, not a claim
that one invariant is the universal physical closure for every plume regime.
Callers must provide a bracket and retain the result's fidelity label when
using it in a planner or continued-cell experiment.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Sequence

from exhaust_plume.models.moc.chain import MocChainBoundarySample, MocChainCell
from exhaust_plume.models.moc.compression import solve_attached_compression_to_turn
from exhaust_plume.models.moc.free_boundary import (
  MocFreeBoundaryShockResult,
  solve_marched_attached_shock_from_source_strip,
)
from exhaust_plume.models.moc.post_shock import MocPostShockChainCellSolve
from exhaust_plume.models.moc.primitives import (
  CharacteristicState,
  prandtl_meyer_angle_rad,
)
from exhaust_plume.models.moc.source_strip import MocSourceCharacteristicStripResult
from exhaust_plume.util.aero.shock_validity import ShockBranch

__all__ = (
  'MocInvariantClosureFamily',
  'MocInvariantClosureStatus',
  'MocInvariantClosureResult',
  'solve_marched_attached_shock_with_constant_invariant_closure',
  'solve_marched_attached_shock_chain_cell_with_constant_invariant_closure',
)


class MocInvariantClosureFamily(str, Enum):
  """The downstream characteristic invariant held during shooting."""

  K_PLUS = 'K+'
  K_MINUS = 'K-'
####


class MocInvariantClosureStatus(str, Enum):
  """Structured outcomes for invariant-conditioned shock closure."""

  CONVERGED_CLOSED = 'converged_invariant_conditioned_field'
  INVALID_INPUT = 'invalid_input'
  BOUNDARY_CONDITION_FAILURE = 'boundary_condition_failure'
  SHOOTING_FAILURE = 'shooting_failure'
  FIELD_FAILURE = 'field_failure'
####


@dataclass(frozen=True, slots=True)
class MocInvariantClosureResult:
  """A bracketed invariant shoot and its optional closed shock field."""

  status: MocInvariantClosureStatus
  invariant_family: MocInvariantClosureFamily
  shock: MocFreeBoundaryShockResult | None
  invariant_target: float | None
  invariant_bracket: tuple[float, float] | None
  closure_residual_rad: float | None
  shooting_iterations: int
  source_window_start_index: int | None
  message: str = ''

  @property
  def converged(self) -> bool:
    return self.status is MocInvariantClosureStatus.CONVERGED_CLOSED
  ####

  @property
  def physical_closure_verified(self) -> bool:
    return self.converged and self.shock is not None and self.shock.physical_closure_verified
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'physical_closure_verified': self.physical_closure_verified,
      'invariant_family': self.invariant_family.value,
      'invariant_target': self.invariant_target,
      'invariant_bracket': self.invariant_bracket,
      'closure_residual_rad': self.closure_residual_rad,
      'shooting_iterations': self.shooting_iterations,
      'source_window_start_index': self.source_window_start_index,
      'shock': None if self.shock is None else self.shock.as_report(),
      'message': self.message,
    }
####


@dataclass(frozen=True, slots=True)
class _InvariantEvaluation:
  angle_rad: float | None
  residual: float | None
  message: str
####


def _failure(
  status: MocInvariantClosureStatus,
  family: MocInvariantClosureFamily,
  *,
  shock: MocFreeBoundaryShockResult | None = None,
  invariant_target: float | None = None,
  invariant_bracket: tuple[float, float] | None = None,
  closure_residual_rad: float | None = None,
  shooting_iterations: int = 0,
  source_window_start_index: int | None = None,
  message: str,
) -> MocInvariantClosureResult:
  return MocInvariantClosureResult(
    status=status,
    invariant_family=family,
    shock=shock,
    invariant_target=invariant_target,
    invariant_bracket=invariant_bracket,
    closure_residual_rad=closure_residual_rad,
    shooting_iterations=shooting_iterations,
    source_window_start_index=source_window_start_index,
    message=message,
  )
####


def _invariant_value(
  family: MocInvariantClosureFamily,
  theta_rad: float,
  downstream_mach: float,
  gamma: float,
) -> float:
  nu = prandtl_meyer_angle_rad(downstream_mach, gamma)
  return theta_rad - nu if family is MocInvariantClosureFamily.K_PLUS else theta_rad + nu
####


def _solve_downstream_angle(
  state: CharacteristicState,
  pressure_Pa: float,
  family: MocInvariantClosureFamily,
  invariant_target: float,
  *,
  branch: ShockBranch,
  maximum_downstream_angle_rad: float,
  invariant_tolerance: float,
  maximum_scan_samples: int,
) -> _InvariantEvaluation:
  """Solve one local downstream angle on the selected attached branch."""

  lower = state.theta_rad + max(1.0e-8, invariant_tolerance)
  upper = float(maximum_downstream_angle_rad)
  if upper <= lower:
    return _InvariantEvaluation(
      angle_rad=None,
      residual=None,
      message='downstream invariant search interval is empty for the local state',
    )

  def evaluate(angle_rad: float) -> tuple[float | None, str] | None:
    try:
      compression = solve_attached_compression_to_turn(
        upstream_mach=state.mach,
        gamma=state.gamma,
        upstream_pressure_Pa=pressure_Pa,
        target_turn_rad=angle_rad - state.theta_rad,
        branch=branch,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      return None, f'local attached-compression inversion failed: {error}'
    if not compression.converged or compression.downstream_mach is None:
      return None, f'local attached-compression inversion failed: {compression.message}'
    value = _invariant_value(
      family,
      angle_rad,
      compression.downstream_mach,
      state.gamma,
    )
    return value - invariant_target, ''

  try:
    lower_value = evaluate(lower)
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _InvariantEvaluation(None, None, f'local invariant evaluation failed: {error}')
  if lower_value is None or lower_value[0] is None:
    return _InvariantEvaluation(
      None,
      None,
      'local invariant evaluation returned no result at the lower angle',
    )
  previous_angle = lower
  previous_residual = lower_value[0]
  if abs(previous_residual) <= invariant_tolerance:
    return _InvariantEvaluation(previous_angle, previous_residual, '')

  for index in range(1, maximum_scan_samples + 1):
    angle = lower + (upper - lower) * index / maximum_scan_samples
    current = evaluate(angle)
    if current is None or current[0] is None:
      if index == 1:
        continue
      break
    current_residual = current[0]
    if abs(current_residual) <= invariant_tolerance:
      return _InvariantEvaluation(angle, current_residual, '')
    if previous_residual * current_residual < 0.0:
      bracket_lower = previous_angle
      bracket_upper = angle
      bracket_residual = previous_residual
      for _ in range(80):
        midpoint = 0.5 * (bracket_lower + bracket_upper)
        midpoint_result = evaluate(midpoint)
        if midpoint_result is None or midpoint_result[0] is None:
          return _InvariantEvaluation(
            None,
            None,
            'local invariant bisection left the attached-compression branch',
          )
        midpoint_residual = midpoint_result[0]
        if abs(midpoint_residual) <= invariant_tolerance:
          return _InvariantEvaluation(midpoint, midpoint_residual, '')
        if bracket_residual * midpoint_residual <= 0.0:
          bracket_upper = midpoint
        else:
          bracket_lower = midpoint
          bracket_residual = midpoint_residual
      return _InvariantEvaluation(
        0.5 * (bracket_lower + bracket_upper),
        midpoint_residual,
        'local invariant bisection did not meet its residual tolerance',
      )
    previous_angle = angle
    previous_residual = current_residual
  return _InvariantEvaluation(
    None,
    None,
    'the requested downstream invariant was not reached on the attached branch',
  )
####


def _run_invariant_target(
  upstream_strip: MocSourceCharacteristicStripResult,
  start_point_m: tuple[float, float],
  family: MocInvariantClosureFamily,
  invariant_target: float,
  *,
  target_centerline_y_m: float,
  target_centerline_flow_angle_rad: float,
  incoming_handoff: Sequence[MocChainBoundarySample] | None,
  sample_count: int,
  branch: ShockBranch,
  position_tolerance_m: float,
  invariant_tolerance: float,
  shock_angle_tolerance_rad: float,
  maximum_segment_iterations: int,
  maximum_downstream_angle_rad: float,
  maximum_invariant_scan_samples: int,
) -> tuple[float | None, MocFreeBoundaryShockResult, str | None]:
  boundary_errors: list[str] = []

  def downstream_angle_at(index: int, point_m: tuple[float, float]) -> float:
    state = upstream_strip.state_at(
      point_m,
      position_tolerance_m=position_tolerance_m,
    )
    pressure = upstream_strip.static_pressure_at(
      point_m,
      position_tolerance_m=position_tolerance_m,
    )
    if state is None or pressure is None:
      message = f'upstream source strip has no state/pressure at shock sample {index}'
      boundary_errors.append(message)
      return float('nan')
    evaluation = _solve_downstream_angle(
      state,
      pressure,
      family,
      invariant_target,
      branch=branch,
      maximum_downstream_angle_rad=maximum_downstream_angle_rad,
      invariant_tolerance=invariant_tolerance,
      maximum_scan_samples=maximum_invariant_scan_samples,
    )
    if evaluation.angle_rad is None:
      boundary_errors.append(
        f'downstream invariant boundary failed at shock sample {index}: '
        f'{evaluation.message}'
      )
      return float('nan')
    return evaluation.angle_rad

  shock = solve_marched_attached_shock_from_source_strip(
    upstream_strip,
    start_point_m,
    target_centerline_y_m=target_centerline_y_m,
    downstream_flow_angle_at=downstream_angle_at,
    incoming_handoff=incoming_handoff,
    sample_count=sample_count,
    branch=branch,
    position_tolerance_m=position_tolerance_m,
    invariant_tolerance=invariant_tolerance,
    shock_angle_tolerance_rad=shock_angle_tolerance_rad,
    maximum_segment_iterations=maximum_segment_iterations,
  )
  if shock.sample_count != sample_count:
    return (
      None,
      shock,
      boundary_errors[-1]
      if boundary_errors
      else f'invariant-conditioned shock stopped at {shock.sample_count}/{sample_count} samples',
    )
  if shock.shock_fit is None or not shock.shock_fit.converged:
    return (
      None,
      shock,
      boundary_errors[-1]
      if boundary_errors
      else f'invariant-conditioned shock fit did not converge: {shock.message}',
    )
  if len(shock.downstream_flow_angles_rad) != sample_count:
    return None, shock, 'invariant-conditioned shock returned an incomplete downstream angle trace'
  terminal_angle = shock.downstream_flow_angles_rad[-1]
  residual = float(terminal_angle) - float(target_centerline_flow_angle_rad)
  if not isfinite(residual):
    return None, shock, 'invariant-conditioned shock produced a non-finite centerline closure residual'
  return residual, shock, None
####


def solve_marched_attached_shock_with_constant_invariant_closure(
  upstream_strip: MocSourceCharacteristicStripResult,
  start_point_m: tuple[float, float],
  invariant_family: MocInvariantClosureFamily,
  invariant_target_lower: float,
  invariant_target_upper: float,
  *,
  target_centerline_y_m: float = 0.0,
  target_centerline_flow_angle_rad: float = 0.0,
  incoming_handoff: Sequence[MocChainBoundarySample] | None = None,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-9,
  invariant_tolerance: float = 1.0e-9,
  closure_tolerance_rad: float = 1.0e-9,
  shock_angle_tolerance_rad: float = 1.0e-1,
  maximum_segment_iterations: int = 24,
  maximum_shooting_iterations: int = 40,
  maximum_downstream_angle_rad: float = 0.9,
  maximum_invariant_scan_samples: int = 64,
) -> MocInvariantClosureResult:
  """Shoot a constant downstream invariant to a centerline flow-angle target.

  Both bracket endpoints must produce a complete, attached shock sample set;
  a missing source-strip state or an unattached local compression invalidates
  the bracket.  The solver never skips an invalid midpoint or extrapolates the
  upstream field.  A returned converged result therefore includes both the
  scalar closure residual and the existing closed post-shock field gate.
  """

  family = (
    invariant_family
    if isinstance(invariant_family, MocInvariantClosureFamily)
    else MocInvariantClosureFamily.K_PLUS
  )
  if not isinstance(upstream_strip, MocSourceCharacteristicStripResult):
    return _failure(
      MocInvariantClosureStatus.INVALID_INPUT,
      family,
      message='upstream_strip must be a MocSourceCharacteristicStripResult',
    )
  if not isinstance(invariant_family, MocInvariantClosureFamily):
    return _failure(
      MocInvariantClosureStatus.INVALID_INPUT,
      MocInvariantClosureFamily.K_PLUS,
      message='invariant_family must be a MocInvariantClosureFamily',
    )
  if not upstream_strip.converged:
    return _failure(
      MocInvariantClosureStatus.INVALID_INPUT,
      family,
      source_window_start_index=upstream_strip.source_window_start_index,
      message=f'upstream source strip is not converged: {upstream_strip.message}',
    )
  try:
    start = (float(start_point_m[0]), float(start_point_m[1]))
    target_y = float(target_centerline_y_m)
    target_angle = float(target_centerline_flow_angle_rad)
    lower_target = float(invariant_target_lower)
    upper_target = float(invariant_target_upper)
  except (IndexError, TypeError, ValueError):
    return _failure(
      MocInvariantClosureStatus.INVALID_INPUT,
      family,
      source_window_start_index=upstream_strip.source_window_start_index,
      message='shock closure coordinates, target angle, and invariant bracket must be numeric',
    )
  if not all(isfinite(value) for value in (*start, target_y, target_angle, lower_target, upper_target)):
    return _failure(
      MocInvariantClosureStatus.INVALID_INPUT,
      family,
      source_window_start_index=upstream_strip.source_window_start_index,
      message='shock closure inputs must be finite',
    )
  if target_y >= start[1]:
    return _failure(
      MocInvariantClosureStatus.INVALID_INPUT,
      family,
      source_window_start_index=upstream_strip.source_window_start_index,
      message='target centerline ordinate must be below the shock start',
    )
  if lower_target >= upper_target:
    return _failure(
      MocInvariantClosureStatus.INVALID_INPUT,
      family,
      source_window_start_index=upstream_strip.source_window_start_index,
      message='invariant bracket lower target must be below upper target',
    )
  if not isinstance(branch, ShockBranch):
    return _failure(
      MocInvariantClosureStatus.INVALID_INPUT,
      family,
      source_window_start_index=upstream_strip.source_window_start_index,
      message='branch must be a ShockBranch',
    )
  if isinstance(sample_count, bool) or not isinstance(sample_count, int) or sample_count < 3:
    raise ValueError('sample_count must be an integer of at least three')
  if isinstance(maximum_shooting_iterations, bool) or not isinstance(maximum_shooting_iterations, int) or maximum_shooting_iterations < 1:
    raise ValueError('maximum_shooting_iterations must be a positive integer')
  if isinstance(maximum_segment_iterations, bool) or not isinstance(maximum_segment_iterations, int) or maximum_segment_iterations < 1:
    raise ValueError('maximum_segment_iterations must be a positive integer')
  if isinstance(maximum_invariant_scan_samples, bool) or not isinstance(maximum_invariant_scan_samples, int) or maximum_invariant_scan_samples < 4:
    raise ValueError('maximum_invariant_scan_samples must be an integer of at least four')
  for name, value in (
    ('position_tolerance_m', position_tolerance_m),
    ('invariant_tolerance', invariant_tolerance),
    ('closure_tolerance_rad', closure_tolerance_rad),
    ('shock_angle_tolerance_rad', shock_angle_tolerance_rad),
    ('maximum_downstream_angle_rad', maximum_downstream_angle_rad),
  ):
    if not isfinite(float(value)) or value <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
  if maximum_downstream_angle_rad <= target_angle:
    raise ValueError('maximum_downstream_angle_rad must exceed the target flow angle')
  ####

  bracket = (lower_target, upper_target)
  lower_residual, lower_shock, lower_error = _run_invariant_target(
    upstream_strip,
    start,
    invariant_family,
    lower_target,
    target_centerline_y_m=target_y,
    target_centerline_flow_angle_rad=target_angle,
    incoming_handoff=incoming_handoff,
    sample_count=sample_count,
    branch=branch,
    position_tolerance_m=position_tolerance_m,
    invariant_tolerance=invariant_tolerance,
    shock_angle_tolerance_rad=shock_angle_tolerance_rad,
    maximum_segment_iterations=maximum_segment_iterations,
    maximum_downstream_angle_rad=maximum_downstream_angle_rad,
    maximum_invariant_scan_samples=maximum_invariant_scan_samples,
  )
  upper_residual, upper_shock, upper_error = _run_invariant_target(
    upstream_strip,
    start,
    invariant_family,
    upper_target,
    target_centerline_y_m=target_y,
    target_centerline_flow_angle_rad=target_angle,
    incoming_handoff=incoming_handoff,
    sample_count=sample_count,
    branch=branch,
    position_tolerance_m=position_tolerance_m,
    invariant_tolerance=invariant_tolerance,
    shock_angle_tolerance_rad=shock_angle_tolerance_rad,
    maximum_segment_iterations=maximum_segment_iterations,
    maximum_downstream_angle_rad=maximum_downstream_angle_rad,
    maximum_invariant_scan_samples=maximum_invariant_scan_samples,
  )
  if lower_residual is None or upper_residual is None:
    return _failure(
      MocInvariantClosureStatus.BOUNDARY_CONDITION_FAILURE,
      invariant_family,
      shock=upper_shock if upper_residual is None else lower_shock,
      invariant_bracket=bracket,
      source_window_start_index=upstream_strip.source_window_start_index,
      message=(
        'invariant shooting requires both bracket endpoints to reach the '
        'centerline with a complete attached-shock fit; '
        f'lower={lower_error or "valid"}; upper={upper_error or "valid"}'
      ),
    )

  def accept(
    residual: float,
    shock: MocFreeBoundaryShockResult,
    target: float,
    iterations: int,
  ) -> MocInvariantClosureResult | None:
    if abs(residual) > closure_tolerance_rad:
      return None
    if shock.converged and shock.field is not None and shock.field.converged:
      return _failure(
        MocInvariantClosureStatus.CONVERGED_CLOSED,
        invariant_family,
        shock=shock,
        invariant_target=target,
        invariant_bracket=bracket,
        closure_residual_rad=residual,
        shooting_iterations=iterations,
        source_window_start_index=upstream_strip.source_window_start_index,
        message=(
          'constant downstream invariant shooting converged with a closed '
          'attached-shock and post-shock characteristic field; this remains '
          'a boundary-conditioned research result'
        ),
      )
    return _failure(
      MocInvariantClosureStatus.FIELD_FAILURE,
      invariant_family,
      shock=shock,
      invariant_target=target,
      invariant_bracket=bracket,
      closure_residual_rad=residual,
      shooting_iterations=iterations,
      source_window_start_index=upstream_strip.source_window_start_index,
      message=(
        'invariant shooting reached the centerline angle target, but the '
        f'generated shock field did not close: {shock.message}'
      ),
    )

  endpoint = accept(lower_residual, lower_shock, lower_target, 0)
  if endpoint is not None:
    return endpoint
  endpoint = accept(upper_residual, upper_shock, upper_target, 0)
  if endpoint is not None:
    return endpoint
  if lower_residual * upper_residual > 0.0:
    return _failure(
      MocInvariantClosureStatus.SHOOTING_FAILURE,
      invariant_family,
      shock=upper_shock,
      invariant_bracket=bracket,
      closure_residual_rad=upper_residual,
      source_window_start_index=upstream_strip.source_window_start_index,
      message=(
        'invariant bracket does not straddle the requested centerline flow-angle '
        f'closure: lower residual={lower_residual}, upper residual={upper_residual}'
      ),
    )

  current_lower = lower_target
  current_upper = upper_target
  current_lower_residual = lower_residual
  last_shock = upper_shock
  last_residual = upper_residual
  for iteration in range(1, maximum_shooting_iterations + 1):
    midpoint = 0.5 * (current_lower + current_upper)
    midpoint_residual, midpoint_shock, midpoint_error = _run_invariant_target(
      upstream_strip,
      start,
      invariant_family,
      midpoint,
      target_centerline_y_m=target_y,
      target_centerline_flow_angle_rad=target_angle,
      incoming_handoff=incoming_handoff,
      sample_count=sample_count,
      branch=branch,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      maximum_segment_iterations=maximum_segment_iterations,
      maximum_downstream_angle_rad=maximum_downstream_angle_rad,
      maximum_invariant_scan_samples=maximum_invariant_scan_samples,
    )
    if midpoint_residual is None:
      return _failure(
        MocInvariantClosureStatus.SHOOTING_FAILURE,
        invariant_family,
        shock=midpoint_shock,
        invariant_target=midpoint,
        invariant_bracket=(current_lower, current_upper),
        source_window_start_index=upstream_strip.source_window_start_index,
        message=(
          'invariant shooting encountered an invalid midpoint and stopped '
          'without extrapolating the upstream field: '
          f'{midpoint_error or midpoint_shock.message}'
        ),
      )
    last_shock = midpoint_shock
    last_residual = midpoint_residual
    endpoint = accept(midpoint_residual, midpoint_shock, midpoint, iteration)
    if endpoint is not None:
      return endpoint
    if current_lower_residual * midpoint_residual <= 0.0:
      current_upper = midpoint
    else:
      current_lower = midpoint
      current_lower_residual = midpoint_residual
  ####
  return _failure(
    MocInvariantClosureStatus.SHOOTING_FAILURE,
    invariant_family,
    shock=last_shock,
    invariant_target=0.5 * (current_lower + current_upper),
    invariant_bracket=(current_lower, current_upper),
    closure_residual_rad=last_residual,
    shooting_iterations=maximum_shooting_iterations,
    source_window_start_index=upstream_strip.source_window_start_index,
    message=(
      'invariant shooting reached its iteration limit before satisfying the '
      f'centerline closure tolerance; residual={last_residual}'
    ),
  )
####


def solve_marched_attached_shock_chain_cell_with_constant_invariant_closure(
  current_cell: MocChainCell,
  next_cell_index: int,
  incoming_handoff: Sequence[MocChainBoundarySample],
  upstream_strip: MocSourceCharacteristicStripResult,
  start_point_m: tuple[float, float],
  end_x_m: float,
  invariant_family: MocInvariantClosureFamily,
  invariant_target_lower: float,
  invariant_target_upper: float,
  *,
  target_centerline_y_m: float = 0.0,
  target_centerline_flow_angle_rad: float = 0.0,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-9,
  invariant_tolerance: float = 1.0e-9,
  closure_tolerance_rad: float = 1.0e-9,
  shock_angle_tolerance_rad: float = 1.0e-1,
  maximum_segment_iterations: int = 24,
  maximum_shooting_iterations: int = 40,
  maximum_downstream_angle_rad: float = 0.9,
  maximum_invariant_scan_samples: int = 64,
) -> MocPostShockChainCellSolve:
  """Adapt an invariant-conditioned field into one typed chain-cell solve.

  The prior cell's terminal trace is checked byte-for-byte at this boundary
  and passed to the field assembler as ``incoming_handoff``.  This helper does
  not infer the next shock location from an axial section and does not accept a
  reduced-order candidate; an unresolved invariant shoot raises instead of
  returning a relabeled cell.
  """

  if not isinstance(current_cell, MocChainCell):
    raise TypeError('current_cell must be a MocChainCell')
  if (
    isinstance(next_cell_index, bool)
    or not isinstance(next_cell_index, int)
    or next_cell_index != current_cell.cell_index + 1
  ):
    raise ValueError('next_cell_index must immediately follow current_cell.cell_index')
  handoff = tuple(incoming_handoff)
  if handoff != current_cell.continuation_boundary:
    raise ValueError('incoming_handoff must exactly match the current cell boundary')
  if len(handoff) < 3:
    raise ValueError('continued invariant-conditioned cells require at least three handoff samples')
  try:
    start = (float(start_point_m[0]), float(start_point_m[1]))
    end_x = float(end_x_m)
  except (IndexError, TypeError, ValueError) as error:
    raise ValueError('continued invariant-conditioned cell geometry must be numeric') from error
  if not all(isfinite(value) for value in (*start, end_x)):
    raise ValueError('continued invariant-conditioned cell geometry must be finite')
  if start[0] <= current_cell.end_x_m + position_tolerance_m:
    raise ValueError('continued invariant-conditioned shock must start downstream of the current cell')
  if end_x <= current_cell.end_x_m:
    raise ValueError('continued invariant-conditioned cell end_x_m must be downstream of the current cell')

  result = solve_marched_attached_shock_with_constant_invariant_closure(
    upstream_strip,
    start,
    invariant_family,
    invariant_target_lower,
    invariant_target_upper,
    target_centerline_y_m=target_centerline_y_m,
    target_centerline_flow_angle_rad=target_centerline_flow_angle_rad,
    incoming_handoff=handoff,
    sample_count=sample_count,
    branch=branch,
    position_tolerance_m=position_tolerance_m,
    invariant_tolerance=invariant_tolerance,
    closure_tolerance_rad=closure_tolerance_rad,
    shock_angle_tolerance_rad=shock_angle_tolerance_rad,
    maximum_segment_iterations=maximum_segment_iterations,
    maximum_shooting_iterations=maximum_shooting_iterations,
    maximum_downstream_angle_rad=maximum_downstream_angle_rad,
    maximum_invariant_scan_samples=maximum_invariant_scan_samples,
  )
  if not result.converged or result.shock is None or result.shock.field is None:
    raise ValueError(
      'continued invariant-conditioned shock cell did not converge: '
      f'{result.status.value}: {result.message}'
    )
  field = result.shock.field
  expected_states = tuple(sample.state for sample in handoff)
  expected_pressures = tuple(sample.total_pressure_Pa for sample in handoff)
  if (
    field.incoming_handoff_states != expected_states
    or field.incoming_handoff_total_pressure_Pa != expected_pressures
  ):
    raise ValueError(
      'continued invariant-conditioned field did not retain the exact incoming handoff'
    )
  return MocPostShockChainCellSolve(field=field, end_x_m=end_x)
####
