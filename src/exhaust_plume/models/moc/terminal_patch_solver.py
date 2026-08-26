"""Domain-bounded shock probes driven by a terminal reflection patch.

The terminal reflection patch is an upstream characteristic domain, not a
closed shock cell.  This module lets the existing attached-shock marcher
consume that domain without extrapolating beyond its last solved cell.  The
downstream flow-angle condition remains explicit here; the result is therefore
a coupling probe and cannot promote a chain cell until that physical boundary
condition is replaced by a converged free-boundary solve.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Callable, Sequence

from exhaust_plume.models.moc.chain import (
  MocChainBoundarySample,
  MocChainBoundaryKind,
  MocChainCell,
  MocChainTerminationDecision,
  MocChainTerminationReason,
)
from exhaust_plume.models.moc.free_boundary import (
  MocFreeBoundaryShockResult,
  MocFreeBoundaryShockStatus,
  solve_marched_attached_shock_field,
)
from exhaust_plume.models.moc.terminal_patch import (
  MocTerminalReflectionPatchResult,
)
from exhaust_plume.models.moc.post_shock import MocPostShockChainCellSolve
from exhaust_plume.models.moc.primitives import CharacteristicFamily, CharacteristicState
from exhaust_plume.util.aero.shock_validity import ShockBranch

__all__ = (
  'MocTerminalPatchShockCouplingStatus',
  'MocTerminalPatchShockCouplingResult',
  'MocTerminalReflectionPatchShockSolveResult',
  'sample_terminal_reflection_patch_along_shock_path',
  'solve_marched_attached_shock_from_terminal_reflection_patch',
  'solve_marched_attached_shock_chain_cell_from_terminal_reflection_patch',
  'solve_marched_attached_shock_chain_cell_from_terminal_reflection_patch_or_termination',
)


class MocTerminalPatchShockCouplingStatus(str, Enum):
  """Outcome of sampling a candidate shock inside the reflected patch."""

  CONVERGED = 'converged_terminal_reflection_patch_field'
  INVALID_INPUT = 'invalid_input'
  PATCH_FAILURE = 'terminal_reflection_patch_failure'
  OUTSIDE_DOMAIN = 'outside_terminal_reflection_patch_domain'
  PRESSURE_FAILURE = 'terminal_reflection_patch_pressure_failure'


@dataclass(frozen=True, slots=True)
class MocTerminalPatchShockCouplingResult:
  """Domain-bounded upstream state and pressure samples along a shock path."""

  status: MocTerminalPatchShockCouplingStatus
  shock_points_m: tuple[tuple[float, float], ...]
  upstream_states: tuple[CharacteristicState, ...]
  upstream_pressure_Pa: tuple[float, ...]
  first_missing_sample_index: int | None
  message: str = ''

  @property
  def converged(self) -> bool:
    return self.status is MocTerminalPatchShockCouplingStatus.CONVERGED

  @property
  def sampled_count(self) -> int:
    return len(self.upstream_states)

  @property
  def last_valid_point_m(self) -> tuple[float, float] | None:
    if not self.upstream_states:
      return None
    state = self.upstream_states[-1]
    return state.x_m, state.y_m

  def as_report(self) -> dict[str, object]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'requested_sample_count': len(self.shock_points_m),
      'sampled_count': self.sampled_count,
      'first_missing_sample_index': self.first_missing_sample_index,
      'last_valid_point_m': self.last_valid_point_m,
      'message': self.message,
    }


@dataclass(frozen=True, slots=True)
class MocTerminalReflectionPatchShockSolveResult:
  """A shock march coupled to, but not physically closing, a terminal patch."""

  shock: MocFreeBoundaryShockResult
  coupling: MocTerminalPatchShockCouplingResult
  incoming_handoff: tuple[MocChainBoundarySample, ...]
  downstream_condition_status: str
  message: str = ''
  shock_branch: ShockBranch = ShockBranch.WEAK

  @property
  def converged(self) -> bool:
    return self.shock.converged and self.coupling.converged

  @property
  def upstream_coupling_verified(self) -> bool:
    return (
      self.converged
      and len(self.shock.shock_points_m) == len(self.coupling.upstream_states)
      and len(self.shock.upstream_pressure_Pa) == len(self.coupling.upstream_states)
      and all(
        abs(first.x_m - second.x_m) <= 1.0e-10
        and abs(first.y_m - second.y_m) <= 1.0e-10
        and abs(first.theta_rad - second.theta_rad) <= 1.0e-10
        and abs(first.mach - second.mach) <= 1.0e-10
        for first, second in zip(
          self.shock.upstream_states,
          self.coupling.upstream_states,
          strict=True,
        )
      )
      and all(
        abs(first - second) <= 1.0e-8 * max(1.0, abs(first), abs(second))
        for first, second in zip(
          self.shock.upstream_pressure_Pa,
          self.coupling.upstream_pressure_Pa,
          strict=True,
        )
      )
    )

  @property
  def physical_closure_verified(self) -> bool:
    """The patch and its explicit downstream law are not production closure."""

    return False

  @property
  def chain_promotion_blocked(self) -> bool:
    return True

  @property
  def physical_terminal_verified(self) -> bool:
    """Whether the mixed-regime endpoint is strong enough to stop a chain."""

    return (
      self.coupling.converged
      and self.shock.subsonic_terminal_required
      and self.shock.normal_shock_terminal is not None
      and self.shock.normal_shock_terminal.converged
      and self.coupling.sampled_count == self.shock.sample_count
    )

  def as_physical_termination_decision(self) -> MocChainTerminationDecision:
    """Return a typed chain stop for a verified normal-shock terminal.

    This decision closes the chain's *termination condition*, not the missing
    subsonic field.  It is therefore intentionally independent of
    ``physical_closure_verified`` and never promotes a cell.
    """

    if not self.physical_terminal_verified:
      raise ValueError(
        'a physical mixed-regime termination requires complete upstream '
        'coverage and a converged normal-shock terminal'
      )
    terminal = self.shock.normal_shock_terminal
    assert terminal is not None
    return MocChainTerminationDecision(
      physical_termination=True,
      reason=MocChainTerminationReason.PHYSICAL_TERMINATION,
      message=(
        'supersonic terminal-patch march reached a verified subsonic normal '
        'shock; continued supersonic MOC cells stop at the mixed-regime boundary'
      ),
      diagnostics={
        'termination_model': 'normal-shock-terminal',
        'shock_point_m': terminal.shock_point_m,
        'downstream_mach': terminal.downstream_mach,
        'downstream_pressure_Pa': terminal.downstream_pressure_Pa,
        'total_pressure_ratio': terminal.total_pressure_ratio,
        'upstream_sample_count': self.coupling.sampled_count,
      },
    )

  def as_report(self) -> dict[str, object]:
    termination_decision = (
      self.as_physical_termination_decision().as_report()
      if self.physical_terminal_verified
      else None
    )
    return {
      'status': self.shock.status.value,
      'converged': self.converged,
      'upstream_coupling_verified': self.upstream_coupling_verified,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'shock_branch': self.shock_branch.value,
      'physical_terminal_verified': self.physical_terminal_verified,
      'termination_decision_available': self.physical_terminal_verified,
      'physical_termination_decision': termination_decision,
      'incoming_handoff_sample_count': len(self.incoming_handoff),
      'downstream_condition_status': self.downstream_condition_status,
      'shock': self.shock.as_report(),
      'coupling': self.coupling.as_report(),
      'message': self.message,
    }


def _normalise_points(
  shock_points_m: Sequence[tuple[float, float]],
) -> tuple[tuple[float, float], ...] | None:
  try:
    points = tuple((float(point[0]), float(point[1])) for point in shock_points_m)
  except (IndexError, TypeError, ValueError):
    return None
  if any(not all(isfinite(value) for value in point) for point in points):
    return None
  return points


def sample_terminal_reflection_patch_along_shock_path(
  patch: MocTerminalReflectionPatchResult,
  shock_points_m: Sequence[tuple[float, float]],
  *,
  position_tolerance_m: float = 1.0e-10,
) -> MocTerminalPatchShockCouplingResult:
  """Sample a candidate shock without extrapolating the terminal patch."""

  points = _normalise_points(shock_points_m)
  if points is None or len(points) < 2:
    return MocTerminalPatchShockCouplingResult(
      status=MocTerminalPatchShockCouplingStatus.INVALID_INPUT,
      shock_points_m=() if points is None else points,
      upstream_states=(),
      upstream_pressure_Pa=(),
      first_missing_sample_index=None,
      message='shock path coupling requires at least two finite points',
    )
  if not isfinite(float(position_tolerance_m)) or position_tolerance_m <= 0.0:
    raise ValueError('position_tolerance_m must be finite and positive')
  if not isinstance(patch, MocTerminalReflectionPatchResult):
    return MocTerminalPatchShockCouplingResult(
      status=MocTerminalPatchShockCouplingStatus.INVALID_INPUT,
      shock_points_m=points,
      upstream_states=(),
      upstream_pressure_Pa=(),
      first_missing_sample_index=None,
      message='patch must be a MocTerminalReflectionPatchResult',
    )
  if not patch.converged:
    return MocTerminalPatchShockCouplingResult(
      status=MocTerminalPatchShockCouplingStatus.PATCH_FAILURE,
      shock_points_m=points,
      upstream_states=(),
      upstream_pressure_Pa=(),
      first_missing_sample_index=None,
      message=f'terminal reflection patch is not converged: {patch.message}',
    )
  for index, (previous, current) in enumerate(zip(points, points[1:]), start=1):
    if (
      current[0] <= previous[0] + position_tolerance_m
      or current[1] > previous[1] + position_tolerance_m
    ):
      return MocTerminalPatchShockCouplingResult(
        status=MocTerminalPatchShockCouplingStatus.INVALID_INPUT,
        shock_points_m=points,
        upstream_states=(),
        upstream_pressure_Pa=(),
        first_missing_sample_index=index,
        message='shock path must be strictly downstream in x and nonincreasing in y',
      )

  states = []
  pressures: list[float] = []
  for index, point in enumerate(points):
    state = patch.state_at(point, position_tolerance_m=position_tolerance_m)
    pressure = patch.static_pressure_at(point, position_tolerance_m=position_tolerance_m)
    if state is None:
      return MocTerminalPatchShockCouplingResult(
        status=MocTerminalPatchShockCouplingStatus.OUTSIDE_DOMAIN,
        shock_points_m=points,
        upstream_states=tuple(states),
        upstream_pressure_Pa=tuple(pressures),
        first_missing_sample_index=index,
        message=f'terminal reflection patch has no upstream state at shock sample {index}',
      )
    if pressure is None or not isfinite(float(pressure)) or pressure <= 0.0:
      return MocTerminalPatchShockCouplingResult(
        status=MocTerminalPatchShockCouplingStatus.PRESSURE_FAILURE,
        shock_points_m=points,
        upstream_states=tuple(states),
        upstream_pressure_Pa=tuple(pressures),
        first_missing_sample_index=index,
        message=f'terminal reflection patch has no valid pressure at shock sample {index}',
      )
    states.append(state)
    pressures.append(float(pressure))
  return MocTerminalPatchShockCouplingResult(
    status=MocTerminalPatchShockCouplingStatus.CONVERGED,
    shock_points_m=points,
    upstream_states=tuple(states),
    upstream_pressure_Pa=tuple(pressures),
    first_missing_sample_index=None,
    message='every shock sample lies inside the terminal reflection patch',
  )


def _shock_failure(message: str) -> MocFreeBoundaryShockResult:
  return MocFreeBoundaryShockResult(
    status=MocFreeBoundaryShockStatus.INVALID_INPUT,
    shock_fit=None,
    field=None,
    shock_points_m=(),
    upstream_states=(),
    upstream_pressure_Pa=(),
    downstream_flow_angles_rad=(),
    shock_angle_residuals_rad=(),
    maximum_shock_angle_residual_rad=None,
    endpoint_m=None,
    message=message,
  )


def _partial_coupling(
  shock: MocFreeBoundaryShockResult,
  *,
  message: str,
) -> MocTerminalPatchShockCouplingResult:
  return MocTerminalPatchShockCouplingResult(
    status=(
      MocTerminalPatchShockCouplingStatus.OUTSIDE_DOMAIN
      if shock.status is MocFreeBoundaryShockStatus.UPSTREAM_FIELD_FAILURE
      else MocTerminalPatchShockCouplingStatus.INVALID_INPUT
    ),
    shock_points_m=shock.shock_points_m,
    upstream_states=shock.upstream_states,
    upstream_pressure_Pa=shock.upstream_pressure_Pa,
    first_missing_sample_index=len(shock.shock_points_m),
    message=message,
  )


def solve_marched_attached_shock_from_terminal_reflection_patch(
  patch: MocTerminalReflectionPatchResult,
  start_point_m: tuple[float, float],
  *,
  target_centerline_y_m: float = 0.0,
  downstream_flow_angle_at: Callable[[int, tuple[float, float]], float] | None = None,
  downstream_flow_angle_rad: float | None = None,
  incoming_handoff: Sequence[MocChainBoundarySample] | None = None,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
) -> MocTerminalReflectionPatchShockSolveResult:
  """Try a shock march using only the solved terminal-patch upstream domain.

  The start point must be the outer end of the patch's outgoing C- front.  The
  patch's outgoing trace is carried automatically as the next-cell handoff;
  callers may provide the same tuple explicitly as an identity check.  The
  downstream flow-angle law is intentionally still explicit and is reported as
  such, so even a locally converged shock field cannot be promoted here.
  """

  if not isinstance(branch, ShockBranch):
    raise ValueError('branch must be a ShockBranch')
  if not isinstance(patch, MocTerminalReflectionPatchResult):
    message = 'patch must be a MocTerminalReflectionPatchResult'
    return MocTerminalReflectionPatchShockSolveResult(
      shock=_shock_failure(message),
      coupling=MocTerminalPatchShockCouplingResult(
        status=MocTerminalPatchShockCouplingStatus.INVALID_INPUT,
        shock_points_m=(),
        upstream_states=(),
        upstream_pressure_Pa=(),
        first_missing_sample_index=None,
        message=message,
      ),
      incoming_handoff=(),
      downstream_condition_status='caller-supplied',
      message=message,
      shock_branch=branch,
    )
  if not patch.converged or len(patch.outgoing_trace_points_m) < 3:
    message = f'terminal reflection patch is not usable: {patch.message}'
    return MocTerminalReflectionPatchShockSolveResult(
      shock=_shock_failure(message),
      coupling=MocTerminalPatchShockCouplingResult(
        status=MocTerminalPatchShockCouplingStatus.PATCH_FAILURE,
        shock_points_m=(),
        upstream_states=(),
        upstream_pressure_Pa=(),
        first_missing_sample_index=None,
        message=message,
      ),
      incoming_handoff=(),
      downstream_condition_status='caller-supplied',
      message=message,
      shock_branch=branch,
    )
  try:
    start = (float(start_point_m[0]), float(start_point_m[1]))
  except (IndexError, TypeError, ValueError):
    message = 'start_point_m must contain two finite coordinates'
    return MocTerminalReflectionPatchShockSolveResult(
      shock=_shock_failure(message),
      coupling=MocTerminalPatchShockCouplingResult(
        status=MocTerminalPatchShockCouplingStatus.INVALID_INPUT,
        shock_points_m=(),
        upstream_states=(),
        upstream_pressure_Pa=(),
        first_missing_sample_index=None,
        message=message,
      ),
      incoming_handoff=(),
      downstream_condition_status='caller-supplied',
      message=message,
      shock_branch=branch,
    )
  if not all(isfinite(value) for value in start):
    raise ValueError('start_point_m must contain two finite coordinates')
  expected_start = patch.outgoing_trace_points_m[0]
  if (
    abs(start[0] - expected_start[0]) > position_tolerance_m
    or abs(start[1] - expected_start[1]) > position_tolerance_m
  ):
    raise ValueError('shock start must equal the outer end of the outgoing C- trace')
  expected_handoff = patch.outgoing_trace_samples
  handoff = expected_handoff if incoming_handoff is None else tuple(incoming_handoff)
  if handoff != expected_handoff:
    raise ValueError('incoming_handoff must exactly match the terminal patch outgoing C- trace')
  if (downstream_flow_angle_at is None) == (downstream_flow_angle_rad is None):
    raise ValueError('supply exactly one downstream flow-angle provider')

  shock = solve_marched_attached_shock_field(
    patch.state_at,
    patch.static_pressure_at,
    start,
    target_centerline_y_m=target_centerline_y_m,
    downstream_flow_angle_at=downstream_flow_angle_at,
    downstream_flow_angle_rad=downstream_flow_angle_rad,
    incoming_handoff=handoff,
    sample_count=sample_count,
    branch=branch,
    position_tolerance_m=position_tolerance_m,
    invariant_tolerance=invariant_tolerance,
    shock_angle_tolerance_rad=shock_angle_tolerance_rad,
    maximum_segment_iterations=maximum_segment_iterations,
  )
  coupling = (
    sample_terminal_reflection_patch_along_shock_path(
      patch,
      shock.shock_points_m,
      position_tolerance_m=position_tolerance_m,
    )
    if len(shock.shock_points_m) >= 2
    else _partial_coupling(shock, message=shock.message)
  )
  if shock.converged and coupling.converged:
    message = (
      'attached shock and post-shock field converged with complete terminal '
      'reflection-patch upstream coverage; physical downstream closure remains pending'
    )
  elif not coupling.converged:
    message = coupling.message
  else:
    message = shock.message
  return MocTerminalReflectionPatchShockSolveResult(
    shock=shock,
    coupling=coupling,
    incoming_handoff=handoff,
    downstream_condition_status='caller-supplied',
    message=message,
    shock_branch=branch,
  )


def _validate_terminal_patch_chain_inputs(
  current_cell: MocChainCell,
  next_cell_index: int,
  incoming_handoff: Sequence[MocChainBoundarySample],
  patch: MocTerminalReflectionPatchResult,
  *,
  start_point_m: tuple[float, float],
  end_x_m: float,
  position_tolerance_m: float,
) -> tuple[tuple[MocChainBoundarySample, ...], tuple[float, float]]:
  """Validate the cell-to-patch seam before invoking the shock marcher."""

  if not isinstance(current_cell, MocChainCell):
    raise TypeError('current_cell must be a MocChainCell')
  if (
    isinstance(next_cell_index, bool)
    or not isinstance(next_cell_index, int)
    or next_cell_index != current_cell.cell_index + 1
  ):
    raise ValueError('next_cell_index must immediately follow current_cell.cell_index')
  if not current_cell.resolved:
    raise ValueError(
      'terminal-patch continuation requires a closed resolved planar-MOC current cell'
    )
  if current_cell.continuation_boundary_kind is not MocChainBoundaryKind.TERMINAL_CHARACTERISTIC_TRACE:
    raise ValueError(
      'terminal-patch continuation requires a terminal-characteristic-trace current boundary'
    )
  try:
    handoff = tuple(incoming_handoff)
  except TypeError as error:
    raise ValueError(
      'incoming_handoff must be an iterable of MocChainBoundarySample values'
    ) from error
  if any(not isinstance(sample, MocChainBoundarySample) for sample in handoff):
    raise ValueError('incoming_handoff must contain MocChainBoundarySample values')
  if handoff != current_cell.continuation_boundary:
    raise ValueError('incoming_handoff must exactly match the current cell boundary')
  if len(handoff) < 3:
    raise ValueError('continued terminal-patch shock cells require at least three handoff samples')
  if not isinstance(patch, MocTerminalReflectionPatchResult):
    raise TypeError('patch must be a MocTerminalReflectionPatchResult')
  if not patch.converged or len(patch.outgoing_trace_points_m) < 3:
    raise ValueError(
      f'terminal reflection patch is not usable: {patch.message}'
    )
  if (
    patch.outgoing_trace_validation is None
    or not patch.outgoing_trace_validation.converged
    or patch.outgoing_trace_validation.family is not CharacteristicFamily.MINUS
  ):
    raise ValueError(
      'terminal reflection patch must expose a converged outgoing C- trace'
    )
  if patch.outgoing_trace_samples != handoff:
    raise ValueError(
      'incoming_handoff must exactly match the terminal patch outgoing C- trace'
    )
  if not isfinite(float(end_x_m)) or end_x_m <= current_cell.end_x_m:
    raise ValueError(
      'continued cell end_x_m must be strictly downstream of the current cell'
    )
  if not isfinite(float(position_tolerance_m)) or position_tolerance_m <= 0.0:
    raise ValueError('position_tolerance_m must be finite and positive')
  try:
    start = (float(start_point_m[0]), float(start_point_m[1]))
  except (IndexError, TypeError, ValueError) as error:
    raise ValueError('start_point_m must contain two finite coordinates') from error
  if not all(isfinite(value) for value in start):
    raise ValueError('start_point_m must contain two finite coordinates')
  if start[0] <= current_cell.end_x_m + position_tolerance_m:
    raise ValueError(
      'continued shock start point must be downstream of the current cell'
    )
  return handoff, start


def _solve_terminal_patch_chain_candidate(
  current_cell: MocChainCell,
  next_cell_index: int,
  incoming_handoff: Sequence[MocChainBoundarySample],
  patch: MocTerminalReflectionPatchResult,
  *,
  start_point_m: tuple[float, float],
  end_x_m: float,
  target_centerline_y_m: float,
  downstream_flow_angle_at: Callable[[int, tuple[float, float]], float] | None,
  downstream_flow_angle_rad: float | None,
  sample_count: int,
  branch: ShockBranch,
  position_tolerance_m: float,
  invariant_tolerance: float,
  shock_angle_tolerance_rad: float,
  maximum_segment_iterations: int,
) -> tuple[
  MocTerminalReflectionPatchShockSolveResult,
  tuple[MocChainBoundarySample, ...],
  float,
]:
  """Run a terminal-patch shock solve after validating the chain seam."""

  handoff, start = _validate_terminal_patch_chain_inputs(
    current_cell,
    next_cell_index,
    incoming_handoff,
    patch,
    start_point_m=start_point_m,
    end_x_m=end_x_m,
    position_tolerance_m=position_tolerance_m,
  )
  solved = solve_marched_attached_shock_from_terminal_reflection_patch(
    patch,
    start,
    target_centerline_y_m=target_centerline_y_m,
    downstream_flow_angle_at=downstream_flow_angle_at,
    downstream_flow_angle_rad=downstream_flow_angle_rad,
    incoming_handoff=handoff,
    sample_count=sample_count,
    branch=branch,
    position_tolerance_m=position_tolerance_m,
    invariant_tolerance=invariant_tolerance,
    shock_angle_tolerance_rad=shock_angle_tolerance_rad,
    maximum_segment_iterations=maximum_segment_iterations,
  )
  return solved, handoff, float(end_x_m)


def _as_terminal_patch_chain_cell_solve(
  solved: MocTerminalReflectionPatchShockSolveResult,
  handoff: tuple[MocChainBoundarySample, ...],
  *,
  end_x_m: float,
) -> MocPostShockChainCellSolve:
  """Require a complete upstream-coupled field before returning a cell solve."""

  if solved.physical_terminal_verified:
    raise ValueError(
      'terminal reflection patch reached a physical normal-shock terminal; '
      'use the or_termination adapter instead of appending a cell'
    )
  if not solved.converged or solved.shock.field is None:
    raise ValueError(
      'terminal-patch continued shock cell failed: '
      f'{solved.shock.status.value}: {solved.message}'
    )
  if not solved.upstream_coupling_verified:
    raise ValueError(
      'terminal-patch continued shock cell lacks complete upstream state/pressure coupling'
    )
  field = solved.shock.field
  expected_states = tuple(sample.state for sample in handoff)
  expected_pressures = tuple(sample.total_pressure_Pa for sample in handoff)
  if (
    field.incoming_handoff_states != expected_states
    or field.incoming_handoff_total_pressure_Pa != expected_pressures
  ):
    raise ValueError(
      'terminal-patch continued field did not retain the exact incoming handoff'
    )
  if not field.upstream_shock_coupling_verified:
    raise ValueError(
      'terminal-patch continued field did not retain its fitted upstream shock samples'
    )
  return MocPostShockChainCellSolve(field=field, end_x_m=end_x_m)


def solve_marched_attached_shock_chain_cell_from_terminal_reflection_patch(
  current_cell: MocChainCell,
  next_cell_index: int,
  incoming_handoff: Sequence[MocChainBoundarySample],
  patch: MocTerminalReflectionPatchResult,
  *,
  start_point_m: tuple[float, float],
  end_x_m: float,
  target_centerline_y_m: float = 0.0,
  downstream_flow_angle_at: Callable[[int, tuple[float, float]], float] | None = None,
  downstream_flow_angle_rad: float | None = None,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 2.0e-4,
  invariant_tolerance: float = 1.0e-10,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
) -> MocPostShockChainCellSolve:
  """Generate a continued cell from a solved terminal-reflection patch.

  The patch's outgoing ``C-`` trace is the only upstream input accepted at
  this seam.  The attached-shock marcher samples the patch's finite state and
  pressure domain directly, records the exact handoff in the returned field,
  and refuses to fabricate a cell on an incomplete or mixed-regime result.
  The downstream flow-angle condition remains caller-supplied research input;
  this adapter is therefore not a production provider or closure claim.
  """

  solved, handoff, end_x = _solve_terminal_patch_chain_candidate(
    current_cell,
    next_cell_index,
    incoming_handoff,
    patch,
    start_point_m=start_point_m,
    end_x_m=end_x_m,
    target_centerline_y_m=target_centerline_y_m,
    downstream_flow_angle_at=downstream_flow_angle_at,
    downstream_flow_angle_rad=downstream_flow_angle_rad,
    sample_count=sample_count,
    branch=branch,
    position_tolerance_m=position_tolerance_m,
    invariant_tolerance=invariant_tolerance,
    shock_angle_tolerance_rad=shock_angle_tolerance_rad,
    maximum_segment_iterations=maximum_segment_iterations,
  )
  return _as_terminal_patch_chain_cell_solve(solved, handoff, end_x_m=end_x)


def solve_marched_attached_shock_chain_cell_from_terminal_reflection_patch_or_termination(
  current_cell: MocChainCell,
  next_cell_index: int,
  incoming_handoff: Sequence[MocChainBoundarySample],
  patch: MocTerminalReflectionPatchResult,
  *,
  start_point_m: tuple[float, float],
  end_x_m: float,
  target_centerline_y_m: float = 0.0,
  downstream_flow_angle_at: Callable[[int, tuple[float, float]], float] | None = None,
  downstream_flow_angle_rad: float | None = None,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 2.0e-4,
  invariant_tolerance: float = 1.0e-10,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
) -> MocPostShockChainCellSolve | MocChainTerminationDecision:
  """Generate a terminal-patch cell or return a typed bounded stop.

  A verified normal-shock endpoint is returned as a physical termination.  An
  incomplete patch coupling or failed local field is returned as a
  non-physical solver/domain stop, preserving the finite-domain seam in
  diagnostics.  Neither case appends a synthetic subsonic or open cell.
  """

  solved, handoff, end_x = _solve_terminal_patch_chain_candidate(
    current_cell,
    next_cell_index,
    incoming_handoff,
    patch,
    start_point_m=start_point_m,
    end_x_m=end_x_m,
    target_centerline_y_m=target_centerline_y_m,
    downstream_flow_angle_at=downstream_flow_angle_at,
    downstream_flow_angle_rad=downstream_flow_angle_rad,
    sample_count=sample_count,
    branch=branch,
    position_tolerance_m=position_tolerance_m,
    invariant_tolerance=invariant_tolerance,
    shock_angle_tolerance_rad=shock_angle_tolerance_rad,
    maximum_segment_iterations=maximum_segment_iterations,
  )
  if solved.physical_terminal_verified:
    return solved.as_physical_termination_decision()
  if not solved.converged or solved.shock.field is None:
    reason = (
      MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
      if solved.coupling.status is MocTerminalPatchShockCouplingStatus.OUTSIDE_DOMAIN
      else MocChainTerminationReason.SOLVER_ERROR
    )
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=reason,
      message=(
        'terminal-patch shock path stopped before a complete upstream-coupled '
        'next cell was solved; no physical endpoint was inferred'
      ),
      diagnostics={
        'termination_model': 'terminal-reflection-patch-upstream-field-boundary',
        'coupling_status': solved.coupling.status.value,
        'coupling_sampled_count': solved.coupling.sampled_count,
        'first_missing_sample_index': solved.coupling.first_missing_sample_index,
        'last_valid_point_m': solved.coupling.last_valid_point_m,
        'shock_status': solved.shock.status.value,
        'next_cell_index': next_cell_index,
        'message': solved.message,
      },
    )
  try:
    return _as_terminal_patch_chain_cell_solve(solved, handoff, end_x_m=end_x)
  except ValueError as error:
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=MocChainTerminationReason.STATE_NOT_CARRIED,
      message=(
        'terminal-patch shock field did not satisfy the exact state-carry '
        'handoff contract; no physical endpoint was inferred'
      ),
      diagnostics={
        'termination_model': 'terminal-reflection-patch-state-handoff',
        'next_cell_index': next_cell_index,
        'incoming_handoff_sample_count': len(handoff),
        'end_x_m': end_x,
        'message': str(error),
      },
    )
