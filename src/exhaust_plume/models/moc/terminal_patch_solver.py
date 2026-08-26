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

from exhaust_plume.models.moc.chain import MocChainBoundarySample
from exhaust_plume.models.moc.free_boundary import (
  MocFreeBoundaryShockResult,
  MocFreeBoundaryShockStatus,
  solve_marched_attached_shock_field,
)
from exhaust_plume.models.moc.terminal_patch import (
  MocTerminalReflectionPatchResult,
)
from exhaust_plume.models.moc.primitives import CharacteristicState

__all__ = (
  'MocTerminalPatchShockCouplingStatus',
  'MocTerminalPatchShockCouplingResult',
  'MocTerminalReflectionPatchShockSolveResult',
  'sample_terminal_reflection_patch_along_shock_path',
  'solve_marched_attached_shock_from_terminal_reflection_patch',
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

  def as_report(self) -> dict[str, object]:
    return {
      'status': self.shock.status.value,
      'converged': self.converged,
      'upstream_coupling_verified': self.upstream_coupling_verified,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
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
  )
