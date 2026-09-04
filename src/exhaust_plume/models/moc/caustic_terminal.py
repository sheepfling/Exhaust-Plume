"""Solver-owned simple-wave terminal handoff at a planar-MOC caustic.

The source-strip caustic does not provide a connected upstream field.  This
module adds a deliberately separate research lane: a constant-invariant
simple-wave *trace* is generated from the exact one-sided caustic state, an
attached shock is marched against that trace, and the supersonic prefix is
assembled into an open post-shock zone ending at a typed normal-shock
terminal.

The simple wave is a boundary-condition model, not a reconstructed two-
dimensional pre-shock field.  Its result is therefore useful for solver
development and visualization, but it remains non-promotable until the true
caustic remesh and mixed-regime perimeter are solved.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Callable, Sequence

from exhaust_plume.models.moc.caustic_remesh import MocCausticShockRemeshRequest
from exhaust_plume.models.moc.chain import (
  MocChainBoundarySample,
  MocChainTerminationDecision,
  MocChainTerminationReason,
)
from exhaust_plume.models.moc.compression import MocNormalShockTerminalResult
from exhaust_plume.models.moc.free_boundary import (
  MocFreeBoundaryShockResult,
  MocFreeBoundaryShockStatus,
  solve_marched_attached_shock_field,
)
from exhaust_plume.models.moc.post_shock import (
  MocPostShockCharacteristicZoneResult,
  MocPostShockContinuationResult,
  MocPostShockFirstLayerResult,
  MocShockBoundaryFitResult,
  assemble_post_shock_characteristic_zone,
  assemble_post_shock_first_layer,
  continue_post_shock_characteristics_to_centerline_open,
  fit_attached_shock_boundary,
)
from exhaust_plume.models.moc.primitives import (
  CharacteristicFamily,
  CharacteristicState,
  inverse_prandtl_meyer_angle_rad,
)
from exhaust_plume.util.aero.shock_validity import ShockBranch

__all__ = (
  'MocCausticSimpleWaveTraceStatus',
  'MocCausticSimpleWaveTrace',
  'build_caustic_simple_wave_trace',
  'MocCausticSimpleWaveTerminalStatus',
  'MocCausticSimpleWaveTerminalResult',
  'solve_caustic_simple_wave_terminal_remesh',
)


class MocCausticSimpleWaveTraceStatus(str, Enum):
  """Outcome of constructing the bounded simple-wave trace model."""

  CONVERGED_TRACE = 'converged_solver_owned_simple_wave_trace'
  INVALID_INPUT = 'invalid_input'
####


@dataclass(frozen=True, slots=True)
class MocCausticSimpleWaveTrace:
  """A finite-ordinate, solver-owned constant-invariant upstream trace.

  The trace is bounded in ``y`` between the caustic event and the requested
  centerline ordinate.  It is intentionally independent of ``x`` apart from
  an optional downstream limit: this is an explicit simple-wave boundary
  condition for a shock marcher, not an unbounded 2-D field extrapolator.
  """

  status: MocCausticSimpleWaveTraceStatus
  event_point_m: tuple[float, float] | None
  event_state: CharacteristicState | None
  event_static_pressure_Pa: float | None
  invariant_family: CharacteristicFamily | None
  invariant_value: float | None
  target_centerline_y_m: float | None
  centerline_flow_angle_rad: float | None
  total_pressure_Pa: float | None
  maximum_x_m: float | None = None
  message: str = ''

  def __post_init__(self) -> None:
    if self.event_point_m is not None:
      if len(self.event_point_m) != 2 or not all(
        isfinite(float(value)) for value in self.event_point_m
      ):
        raise ValueError('event_point_m must contain two finite coordinates')
      ####
      object.__setattr__(
        self,
        'event_point_m',
        (float(self.event_point_m[0]), float(self.event_point_m[1])),
      )
    ####
    if self.event_state is not None and not isinstance(
      self.event_state,
      CharacteristicState,
    ):
      raise TypeError('event_state must be a CharacteristicState or None')
    ####
    for name in (
      'event_static_pressure_Pa',
      'invariant_value',
      'target_centerline_y_m',
      'centerline_flow_angle_rad',
      'total_pressure_Pa',
      'maximum_x_m',
    ):
      value = getattr(self, name)
      if value is not None and not isfinite(float(value)):
        raise ValueError(f'{name} must be finite when supplied')
      ####
    ####
    if self.event_static_pressure_Pa is not None and self.event_static_pressure_Pa <= 0.0:
      raise ValueError('event_static_pressure_Pa must be positive')
    ####
    if self.total_pressure_Pa is not None and self.total_pressure_Pa <= 0.0:
      raise ValueError('total_pressure_Pa must be positive')
    ####
    if self.maximum_x_m is not None and self.event_point_m is not None and (
      self.maximum_x_m <= self.event_point_m[0]
    ):
      raise ValueError('maximum_x_m must be downstream of the event point')
    ####
  ####

  @property
  def converged(self) -> bool:
    return self.status is MocCausticSimpleWaveTraceStatus.CONVERGED_TRACE
  ####

  @property
  def physical_closure_verified(self) -> bool:
    return False
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    return True
  ####

  def _fraction(self, y_m: float) -> float | None:
    if not self.converged or self.event_point_m is None or self.target_centerline_y_m is None:
      return None
    ####
    event_y = self.event_point_m[1]
    target_y = self.target_centerline_y_m
    span = event_y - target_y
    if span <= 0.0 or y_m < target_y - 1.0e-10 or y_m > event_y + 1.0e-10:
      return None
    ####
    return max(0.0, min(1.0, (y_m - target_y) / span))
  ####

  def state_at(
    self,
    point_m: tuple[float, float],
    *,
    position_tolerance_m: float = 1.0e-10,
  ) -> CharacteristicState | None:
    """Return the simple-wave state only inside its finite ordinate domain."""

    if not self.converged:
      return None
    ####
    if len(point_m) != 2 or not all(isfinite(float(value)) for value in point_m):
      raise ValueError('point_m must contain two finite coordinates')
    ####
    if not isfinite(float(position_tolerance_m)) or position_tolerance_m <= 0.0:
      raise ValueError('position_tolerance_m must be finite and positive')
    ####
    assert self.event_point_m is not None
    assert self.event_state is not None
    assert self.invariant_family is not None
    assert self.invariant_value is not None
    assert self.target_centerline_y_m is not None
    assert self.centerline_flow_angle_rad is not None
    x_m, y_m = float(point_m[0]), float(point_m[1])
    if x_m < self.event_point_m[0] - position_tolerance_m:
      return None
    ####
    if self.maximum_x_m is not None and x_m > self.maximum_x_m + position_tolerance_m:
      return None
    ####
    fraction = self._fraction(y_m)
    if fraction is None:
      return None
    ####
    if (
      abs(x_m - self.event_point_m[0]) <= position_tolerance_m
      and abs(y_m - self.event_point_m[1]) <= position_tolerance_m
    ):
      return self.event_state
    ####
    theta = self.centerline_flow_angle_rad + (
      self.event_state.theta_rad - self.centerline_flow_angle_rad
    ) * fraction
    if self.invariant_family is CharacteristicFamily.PLUS:
      nu = theta - self.invariant_value
    else:
      nu = self.invariant_value - theta
    ####
    if not isfinite(nu) or nu <= 0.0:
      return None
    ####
    inversion = inverse_prandtl_meyer_angle_rad(nu, self.event_state.gamma)
    if not inversion.converged or inversion.value is None or inversion.value <= 1.0:
      return None
    ####
    return CharacteristicState(
      x_m=x_m,
      y_m=y_m,
      theta_rad=theta,
      mach=inversion.value,
      gamma=self.event_state.gamma,
    )
  ####

  def static_pressure_at(
    self,
    point_m: tuple[float, float],
    *,
    position_tolerance_m: float = 1.0e-10,
  ) -> float | None:
    """Return isentropic pressure carried by the simple-wave trace."""

    state = self.state_at(point_m, position_tolerance_m=position_tolerance_m)
    if state is None or self.total_pressure_Pa is None:
      return None
    ####
    factor = 1.0 + 0.5 * (state.gamma - 1.0) * state.mach * state.mach
    return self.total_pressure_Pa / factor ** (state.gamma / (state.gamma - 1.0))
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'model': 'solver-owned-constant-invariant-simple-wave-trace',
      'event_point_m': self.event_point_m,
      'event_state': None if self.event_state is None else {
        'x_m': self.event_state.x_m,
        'y_m': self.event_state.y_m,
        'theta_rad': self.event_state.theta_rad,
        'mach': self.event_state.mach,
        'gamma': self.event_state.gamma,
      },
      'event_static_pressure_Pa': self.event_static_pressure_Pa,
      'invariant_family': (
        None if self.invariant_family is None else self.invariant_family.value
      ),
      'invariant_value': self.invariant_value,
      'target_centerline_y_m': self.target_centerline_y_m,
      'centerline_flow_angle_rad': self.centerline_flow_angle_rad,
      'total_pressure_Pa': self.total_pressure_Pa,
      'maximum_x_m': self.maximum_x_m,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'message': self.message,
    }
  ####
####


def build_caustic_simple_wave_trace(
  request: MocCausticShockRemeshRequest,
  *,
  upstream_invariant_family: CharacteristicFamily = CharacteristicFamily.MINUS,
  target_centerline_y_m: float = 0.0,
  centerline_flow_angle_rad: float = 0.0,
  total_pressure_Pa: float | None = None,
  maximum_x_m: float | None = None,
) -> MocCausticSimpleWaveTrace:
  """Build an explicit constant-invariant trace from a prepared caustic.

  The event state and static pressure are taken verbatim from the remesh
  request.  No one-sided source-strip sample is averaged and no downstream
  state is used as an upstream continuation.
  """

  if not isinstance(request, MocCausticShockRemeshRequest):
    return MocCausticSimpleWaveTrace(
      status=MocCausticSimpleWaveTraceStatus.INVALID_INPUT,
      event_point_m=None,
      event_state=None,
      event_static_pressure_Pa=None,
      invariant_family=None,
      invariant_value=None,
      target_centerline_y_m=None,
      centerline_flow_angle_rad=None,
      total_pressure_Pa=None,
      maximum_x_m=None,
      message='request must be a MocCausticShockRemeshRequest',
    )
  ####
  if not isinstance(upstream_invariant_family, CharacteristicFamily):
    return MocCausticSimpleWaveTrace(
      status=MocCausticSimpleWaveTraceStatus.INVALID_INPUT,
      event_point_m=request.event_point_m,
      event_state=request.upstream_state,
      event_static_pressure_Pa=request.upstream_static_pressure_Pa,
      invariant_family=None,
      invariant_value=None,
      target_centerline_y_m=None,
      centerline_flow_angle_rad=None,
      total_pressure_Pa=None,
      maximum_x_m=None,
      message='upstream_invariant_family must be a CharacteristicFamily',
    )
  ####
  try:
    target_y = float(target_centerline_y_m)
    target_theta = float(centerline_flow_angle_rad)
  except (TypeError, ValueError):
    return MocCausticSimpleWaveTrace(
      status=MocCausticSimpleWaveTraceStatus.INVALID_INPUT,
      event_point_m=request.event_point_m,
      event_state=request.upstream_state,
      event_static_pressure_Pa=request.upstream_static_pressure_Pa,
      invariant_family=upstream_invariant_family,
      invariant_value=None,
      target_centerline_y_m=None,
      centerline_flow_angle_rad=None,
      total_pressure_Pa=None,
      maximum_x_m=None,
      message='simple-wave target ordinate and centerline angle must be numeric',
    )
  ####
  event = request.event_point_m
  if not isfinite(target_y) or not isfinite(target_theta):
    return MocCausticSimpleWaveTrace(
      status=MocCausticSimpleWaveTraceStatus.INVALID_INPUT,
      event_point_m=event,
      event_state=request.upstream_state,
      event_static_pressure_Pa=request.upstream_static_pressure_Pa,
      invariant_family=upstream_invariant_family,
      invariant_value=None,
      target_centerline_y_m=None,
      centerline_flow_angle_rad=None,
      total_pressure_Pa=None,
      maximum_x_m=None,
      message='simple-wave target ordinate and centerline angle must be finite',
    )
  ####
  if target_y >= event[1]:
    message = 'simple-wave target ordinate must be finite and below the caustic event'
    return MocCausticSimpleWaveTrace(
      status=MocCausticSimpleWaveTraceStatus.INVALID_INPUT,
      event_point_m=event,
      event_state=request.upstream_state,
      event_static_pressure_Pa=request.upstream_static_pressure_Pa,
      invariant_family=upstream_invariant_family,
      invariant_value=None,
      target_centerline_y_m=target_y,
      centerline_flow_angle_rad=target_theta,
      total_pressure_Pa=None,
      maximum_x_m=None,
      message=message,
    )
  ####
  if target_y < -1.0e-10:
    return MocCausticSimpleWaveTrace(
      status=MocCausticSimpleWaveTraceStatus.INVALID_INPUT,
      event_point_m=event,
      event_state=request.upstream_state,
      event_static_pressure_Pa=request.upstream_static_pressure_Pa,
      invariant_family=upstream_invariant_family,
      invariant_value=None,
      target_centerline_y_m=target_y,
      centerline_flow_angle_rad=target_theta,
      total_pressure_Pa=None,
      maximum_x_m=None,
      message='simple-wave target ordinate must remain in the upper half-plane',
    )
  ####
  if maximum_x_m is not None:
    try:
      x_limit = float(maximum_x_m)
    except (TypeError, ValueError):
      x_limit = float('nan')
    ####
    if not isfinite(x_limit) or x_limit <= event[0]:
      return MocCausticSimpleWaveTrace(
        status=MocCausticSimpleWaveTraceStatus.INVALID_INPUT,
        event_point_m=event,
        event_state=request.upstream_state,
        event_static_pressure_Pa=request.upstream_static_pressure_Pa,
        invariant_family=upstream_invariant_family,
        invariant_value=None,
        target_centerline_y_m=target_y,
        centerline_flow_angle_rad=target_theta,
        total_pressure_Pa=None,
        maximum_x_m=x_limit if isfinite(x_limit) else None,
        message='maximum_x_m must be finite and downstream of the caustic event',
      )
    ####
  else:
    x_limit = None
  ####

  upstream = request.upstream_state
  invariant = (
    upstream.k_plus
    if upstream_invariant_family is CharacteristicFamily.PLUS
    else upstream.k_minus
  )
  if upstream_invariant_family is CharacteristicFamily.PLUS:
    target_nu = target_theta - invariant
  else:
    target_nu = invariant - target_theta
  ####
  if not isfinite(target_nu) or target_nu <= 0.0:
    return MocCausticSimpleWaveTrace(
      status=MocCausticSimpleWaveTraceStatus.INVALID_INPUT,
      event_point_m=event,
      event_state=upstream,
      event_static_pressure_Pa=request.upstream_static_pressure_Pa,
      invariant_family=upstream_invariant_family,
      invariant_value=invariant,
      target_centerline_y_m=target_y,
      centerline_flow_angle_rad=target_theta,
      total_pressure_Pa=None,
      maximum_x_m=x_limit,
      message='simple-wave centerline angle leaves the supersonic compatibility domain',
    )
  ####
  if total_pressure_Pa is None:
    factor = 1.0 + 0.5 * (upstream.gamma - 1.0) * upstream.mach * upstream.mach
    total_pressure = request.upstream_static_pressure_Pa * factor ** (
      upstream.gamma / (upstream.gamma - 1.0)
    )
  else:
    total_pressure = float(total_pressure_Pa)
  ####
  if not isfinite(total_pressure) or total_pressure <= 0.0:
    raise ValueError('total_pressure_Pa must be finite and positive')
  ####
  return MocCausticSimpleWaveTrace(
    status=MocCausticSimpleWaveTraceStatus.CONVERGED_TRACE,
    event_point_m=event,
    event_state=upstream,
    event_static_pressure_Pa=request.upstream_static_pressure_Pa,
    invariant_family=upstream_invariant_family,
    invariant_value=invariant,
    target_centerline_y_m=target_y,
    centerline_flow_angle_rad=target_theta,
    total_pressure_Pa=total_pressure,
    maximum_x_m=x_limit,
    message=(
      'constant-invariant upstream simple-wave trace built from the exact '
      'caustic one-sided state; this is a research boundary condition'
    ),
  )
####


class MocCausticSimpleWaveTerminalStatus(str, Enum):
  """Outcome of the simple-wave shock-prefix/open-zone handoff."""

  CONVERGED_OPEN_TERMINAL_FIELD = 'converged_open_simple_wave_terminal_field'
  INVALID_INPUT = 'invalid_input'
  EVENT_SEAM_FAILURE = 'simple_wave_event_seam_failure'
  UPSTREAM_FIELD_FAILURE = 'simple_wave_upstream_field_failure'
  DOWNSTREAM_BOUNDARY_FAILURE = 'simple_wave_downstream_boundary_failure'
  SHOCK_FAILURE = 'simple_wave_shock_failure'
  SHOCK_PREFIX_FAILURE = 'simple_wave_shock_prefix_failure'
  DOWNSTREAM_ZONE_FAILURE = 'simple_wave_downstream_zone_failure'
####


@dataclass(frozen=True, slots=True)
class MocCausticSimpleWaveTerminalResult:
  """Open supersonic field plus a typed normal-shock terminal.

  ``converged`` means that the solver-owned simple-wave trace, attached shock
  prefix, open post-shock characteristic zone, and terminal normal shock all
  passed their local gates.  It never means that the subsonic side or full
  physical cell perimeter is closed.
  """

  status: MocCausticSimpleWaveTerminalStatus
  request: MocCausticShockRemeshRequest | None
  trace: MocCausticSimpleWaveTrace | None
  shock: MocFreeBoundaryShockResult | None
  shock_fit: MocShockBoundaryFitResult | None
  continuation: MocPostShockContinuationResult | None
  first_layer: MocPostShockFirstLayerResult | None
  zone: MocPostShockCharacteristicZoneResult | None
  terminal: MocNormalShockTerminalResult | None
  event_point_m: tuple[float, float] | None
  event_seam_verified: bool
  local_bridge_state_verified: bool
  upstream_coupling_verified: bool
  shock_prefix_verified: bool
  downstream_zone_verified: bool
  terminal_verified: bool
  incoming_handoff_states: tuple[CharacteristicState, ...] = ()
  incoming_handoff_total_pressure_Pa: tuple[float, ...] = ()
  message: str = ''

  def __post_init__(self) -> None:
    if len(self.incoming_handoff_states) != len(self.incoming_handoff_total_pressure_Pa):
      raise ValueError('incoming handoff states and pressures must have equal lengths')
    ####
    if any(not isinstance(state, CharacteristicState) for state in self.incoming_handoff_states):
      raise TypeError('incoming handoff states must be CharacteristicState values')
    ####
    if any(not isfinite(float(value)) or value <= 0.0 for value in self.incoming_handoff_total_pressure_Pa):
      raise ValueError('incoming handoff pressures must be finite and positive')
    ####
    if self.event_point_m is not None:
      if len(self.event_point_m) != 2 or not all(isfinite(float(value)) for value in self.event_point_m):
        raise ValueError('event_point_m must contain two finite coordinates')
      ####
      object.__setattr__(self, 'event_point_m', tuple(float(value) for value in self.event_point_m))
    ####
    for name in (
      'event_seam_verified',
      'local_bridge_state_verified',
      'upstream_coupling_verified',
      'shock_prefix_verified',
      'downstream_zone_verified',
      'terminal_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
  ####

  @property
  def converged(self) -> bool:
    return self.status is MocCausticSimpleWaveTerminalStatus.CONVERGED_OPEN_TERMINAL_FIELD
  ####

  @property
  def physical_terminal_verified(self) -> bool:
    return self.terminal_verified and self.terminal is not None and self.terminal.subsonic
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
  def open_field_available(self) -> bool:
    return self.converged and self.zone is not None and self.zone.converged
  ####

  def as_chain_termination_decision(self) -> MocChainTerminationDecision:
    if self.status is MocCausticSimpleWaveTerminalStatus.INVALID_INPUT:
      reason = MocChainTerminationReason.INVALID_INPUT
    elif self.status is MocCausticSimpleWaveTerminalStatus.UPSTREAM_FIELD_FAILURE:
      reason = MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
    elif self.status is MocCausticSimpleWaveTerminalStatus.EVENT_SEAM_FAILURE:
      reason = MocChainTerminationReason.CHARACTERISTIC_CAUSTIC
    elif self.converged:
      reason = MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
    else:
      reason = MocChainTerminationReason.SOLVER_ERROR
    ####
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=reason,
      message=(
        self.message
        or 'simple-wave terminal handoff is not a promotable physical chain cell'
      ),
      diagnostics={
        'termination_model': 'caustic-simple-wave-open-terminal-field',
        'simple_wave_trace_status': None if self.trace is None else self.trace.status.value,
        'event_point_m': self.event_point_m,
        'event_seam_verified': self.event_seam_verified,
        'local_bridge_state_verified': self.local_bridge_state_verified,
        'upstream_coupling_verified': self.upstream_coupling_verified,
        'shock_prefix_verified': self.shock_prefix_verified,
        'downstream_zone_verified': self.downstream_zone_verified,
        'terminal_verified': self.terminal_verified,
        'physical_terminal_verified': self.physical_terminal_verified,
        'physical_closure_verified': self.physical_closure_verified,
        'chain_promotion_blocked': self.chain_promotion_blocked,
        'shock_sample_count': None if self.shock is None else self.shock.sample_count,
        'zone_cell_count': None if self.zone is None else self.zone.cell_count,
        'incoming_handoff_sample_count': len(self.incoming_handoff_states),
      },
    )
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'event_point_m': self.event_point_m,
      'event_seam_verified': self.event_seam_verified,
      'local_bridge_state_verified': self.local_bridge_state_verified,
      'upstream_coupling_verified': self.upstream_coupling_verified,
      'shock_prefix_verified': self.shock_prefix_verified,
      'downstream_zone_verified': self.downstream_zone_verified,
      'terminal_verified': self.terminal_verified,
      'physical_terminal_verified': self.physical_terminal_verified,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'open_field_available': self.open_field_available,
      'trace': None if self.trace is None else self.trace.as_report(),
      'shock': None if self.shock is None else self.shock.as_report(),
      'shock_fit': None if self.shock_fit is None else {
        'converged': self.shock_fit.converged,
        'sample_count': len(self.shock_fit.boundary_states),
        'maximum_shock_angle_residual_rad': self.shock_fit.maximum_shock_angle_residual_rad,
      },
      'continuation': None if self.continuation is None else {
        'converged': self.continuation.converged,
        'segment_count': len(self.continuation.segments),
        'maximum_geometry_residual_m': self.continuation.maximum_geometry_residual_m,
        'maximum_absolute_invariant_residual': self.continuation.maximum_absolute_invariant_residual,
      },
      'first_layer': None if self.first_layer is None else {
        'converged': self.first_layer.converged,
        'crossing_count': len(self.first_layer.crossings),
        'maximum_geometry_residual_m': self.first_layer.maximum_geometry_residual_m,
        'maximum_absolute_invariant_residual': self.first_layer.maximum_absolute_invariant_residual,
      },
      'zone': None if self.zone is None else self.zone.as_report(),
      'terminal': None if self.terminal is None else self.terminal.as_report(),
      'incoming_handoff_sample_count': len(self.incoming_handoff_states),
      'incoming_handoff_total_pressure_range_Pa': (
        None if not self.incoming_handoff_total_pressure_Pa else (
          min(self.incoming_handoff_total_pressure_Pa),
          max(self.incoming_handoff_total_pressure_Pa),
        )
      ),
      'chain_termination_decision': self.as_chain_termination_decision().as_report(),
      'message': self.message,
    }
  ####
####


def _state_matches(
  actual: CharacteristicState,
  expected: CharacteristicState,
  *,
  position_tolerance_m: float,
  state_tolerance: float,
) -> bool:
  return (
    abs(actual.x_m - expected.x_m) <= position_tolerance_m
    and abs(actual.y_m - expected.y_m) <= position_tolerance_m
    and abs(actual.theta_rad - expected.theta_rad) <= state_tolerance * max(
      1.0, abs(actual.theta_rad), abs(expected.theta_rad)
    )
    and abs(actual.mach - expected.mach) <= state_tolerance * max(
      1.0, abs(actual.mach), abs(expected.mach)
    )
    and abs(actual.gamma - expected.gamma) <= state_tolerance * max(
      1.0, abs(actual.gamma), abs(expected.gamma)
    )
  )
####


def _pressure_matches(actual: float, expected: float, tolerance: float) -> bool:
  return abs(float(actual) - float(expected)) <= tolerance * max(
    1.0, abs(float(actual)), abs(float(expected))
  )
####


def _failure(
  status: MocCausticSimpleWaveTerminalStatus,
  *,
  request: MocCausticShockRemeshRequest | None,
  trace: MocCausticSimpleWaveTrace | None,
  shock: MocFreeBoundaryShockResult | None = None,
  shock_fit: MocShockBoundaryFitResult | None = None,
  continuation: MocPostShockContinuationResult | None = None,
  first_layer: MocPostShockFirstLayerResult | None = None,
  zone: MocPostShockCharacteristicZoneResult | None = None,
  terminal: MocNormalShockTerminalResult | None = None,
  event_seam_verified: bool = False,
  local_bridge_state_verified: bool = False,
  upstream_coupling_verified: bool = False,
  shock_prefix_verified: bool = False,
  downstream_zone_verified: bool = False,
  terminal_verified: bool = False,
  handoff: tuple[MocChainBoundarySample, ...] = (),
  message: str,
) -> MocCausticSimpleWaveTerminalResult:
  return MocCausticSimpleWaveTerminalResult(
    status=status,
    request=request,
    trace=trace,
    shock=shock,
    shock_fit=shock_fit,
    continuation=continuation,
    first_layer=first_layer,
    zone=zone,
    terminal=terminal,
    event_point_m=None if request is None else request.event_point_m,
    event_seam_verified=event_seam_verified,
    local_bridge_state_verified=local_bridge_state_verified,
    upstream_coupling_verified=upstream_coupling_verified,
    shock_prefix_verified=shock_prefix_verified,
    downstream_zone_verified=downstream_zone_verified,
    terminal_verified=terminal_verified,
    incoming_handoff_states=tuple(sample.state for sample in handoff),
    incoming_handoff_total_pressure_Pa=tuple(sample.total_pressure_Pa for sample in handoff),
    message=message,
  )
####


def solve_caustic_simple_wave_terminal_remesh(
  request: MocCausticShockRemeshRequest,
  incoming_handoff: Sequence[MocChainBoundarySample],
  *,
  upstream_invariant_family: CharacteristicFamily = CharacteristicFamily.MINUS,
  target_centerline_y_m: float = 0.0,
  upstream_centerline_flow_angle_rad: float = 0.0,
  downstream_centerline_flow_angle_rad: float = 0.0,
  downstream_flow_angle_at: Callable[[int, tuple[float, float]], float] | None = None,
  maximum_x_m: float | None = None,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  shock_angle_tolerance_rad: float = 0.2,
  maximum_segment_iterations: int = 24,
) -> MocCausticSimpleWaveTerminalResult:
  """Solve the simple-wave shock-prefix/open-zone terminal handoff.

  The default downstream angle is a linear profile from the exact local
  bridge downstream angle to ``downstream_centerline_flow_angle_rad``.  With
  the default zero centerline angle, a zero-turn sample is represented by the
  typed normal-shock terminal rather than fabricated as a subsonic MOC state.
  A caller-supplied angle law remains an explicit research boundary condition.
  """

  if not isinstance(request, MocCausticShockRemeshRequest):
    return _failure(
      MocCausticSimpleWaveTerminalStatus.INVALID_INPUT,
      request=None,
      trace=None,
      message='request must be a MocCausticShockRemeshRequest',
    )
  ####
  try:
    handoff = tuple(incoming_handoff)
  except TypeError:
    return _failure(
      MocCausticSimpleWaveTerminalStatus.INVALID_INPUT,
      request=request,
      trace=None,
      message='incoming_handoff must be an iterable of MocChainBoundarySample values',
    )
  ####
  if len(handoff) < 3 or any(not isinstance(sample, MocChainBoundarySample) for sample in handoff):
    return _failure(
      MocCausticSimpleWaveTerminalStatus.INVALID_INPUT,
      request=request,
      trace=None,
      handoff=handoff,
      message='simple-wave terminal remesh requires at least three typed incoming handoff samples',
    )
  ####
  if not isinstance(branch, ShockBranch):
    return _failure(
      MocCausticSimpleWaveTerminalStatus.INVALID_INPUT,
      request=request,
      trace=None,
      handoff=handoff,
      message='branch must be a ShockBranch',
    )
  ####
  if isinstance(sample_count, bool) or not isinstance(sample_count, int) or sample_count < 5:
    raise ValueError('sample_count must be an integer of at least five')
  ####
  for name, value in (
    ('position_tolerance_m', position_tolerance_m),
    ('invariant_tolerance', invariant_tolerance),
    ('shock_angle_tolerance_rad', shock_angle_tolerance_rad),
  ):
    if not isfinite(float(value)) or float(value) <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
    ####
  ####
  trace = build_caustic_simple_wave_trace(
    request,
    upstream_invariant_family=upstream_invariant_family,
    target_centerline_y_m=target_centerline_y_m,
    centerline_flow_angle_rad=upstream_centerline_flow_angle_rad,
    maximum_x_m=maximum_x_m,
  )
  if not trace.converged:
    return _failure(
      MocCausticSimpleWaveTerminalStatus.INVALID_INPUT,
      request=request,
      trace=trace,
      handoff=handoff,
      message=f'simple-wave upstream trace could not be built: {trace.message}',
    )
  ####

  event = request.event_point_m
  event_state = trace.state_at(event, position_tolerance_m=position_tolerance_m)
  event_pressure = trace.static_pressure_at(event, position_tolerance_m=position_tolerance_m)
  event_seam_verified = bool(
    event_state is not None
    and event_pressure is not None
    and _state_matches(
      event_state,
      request.upstream_state,
      position_tolerance_m=position_tolerance_m,
      state_tolerance=invariant_tolerance,
    )
    and _pressure_matches(
      event_pressure,
      request.upstream_static_pressure_Pa,
      invariant_tolerance,
    )
  )
  if not event_seam_verified:
    return _failure(
      MocCausticSimpleWaveTerminalStatus.EVENT_SEAM_FAILURE,
      request=request,
      trace=trace,
      handoff=handoff,
      message='simple-wave trace does not reproduce the exact prepared caustic event state and pressure',
    )
  ####

  local_downstream = request.local_bridge.downstream_state
  compression = request.local_bridge.compression
  if local_downstream is None or compression is None or compression.downstream_total_pressure_Pa is None:
    return _failure(
      MocCausticSimpleWaveTerminalStatus.EVENT_SEAM_FAILURE,
      request=request,
      trace=trace,
      event_seam_verified=True,
      handoff=handoff,
      message='prepared caustic request has no complete local downstream bridge state',
    )
  ####
  try:
    target_downstream_angle = float(downstream_centerline_flow_angle_rad)
  except (TypeError, ValueError):
    target_downstream_angle = float('nan')
  ####
  if not isfinite(target_downstream_angle):
    return _failure(
      MocCausticSimpleWaveTerminalStatus.INVALID_INPUT,
      request=request,
      trace=trace,
      event_seam_verified=True,
      handoff=handoff,
      message='downstream_centerline_flow_angle_rad must be finite',
    )
  ####

  law_checked = False

  def default_downstream_angle(index: int, point: tuple[float, float]) -> float:
    nonlocal law_checked
    if point[1] < target_centerline_y_m - position_tolerance_m or point[1] > event[1] + position_tolerance_m:
      raise ValueError('downstream angle law was sampled outside the terminal ordinate domain')
    ####
    fraction = max(
      0.0,
      min(1.0, (point[1] - target_centerline_y_m) / (event[1] - target_centerline_y_m)),
    )
    value = target_downstream_angle + (
      local_downstream.theta_rad - target_downstream_angle
    ) * fraction
    if index == 0:
      law_checked = abs(value - local_downstream.theta_rad) <= invariant_tolerance * max(
        1.0, abs(value), abs(local_downstream.theta_rad)
      )
    ####
    return value
  ####

  def supplied_downstream_angle(index: int, point: tuple[float, float]) -> float:
    nonlocal law_checked
    assert downstream_flow_angle_at is not None
    value = float(downstream_flow_angle_at(index, point))
    if not isfinite(value):
      raise ValueError('downstream_flow_angle_at returned a non-finite value')
    ####
    if index == 0:
      law_checked = abs(value - local_downstream.theta_rad) <= invariant_tolerance * max(
        1.0, abs(value), abs(local_downstream.theta_rad)
      )
    ####
    return value
  ####

  angle_law = supplied_downstream_angle if downstream_flow_angle_at is not None else default_downstream_angle
  try:
    angle_at_event = angle_law(0, event)
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocCausticSimpleWaveTerminalStatus.DOWNSTREAM_BOUNDARY_FAILURE,
      request=request,
      trace=trace,
      event_seam_verified=True,
      handoff=handoff,
      message=f'downstream angle law failed at the caustic event: {error}',
    )
  ####
  if not law_checked or abs(angle_at_event - local_downstream.theta_rad) > invariant_tolerance * max(
    1.0, abs(angle_at_event), abs(local_downstream.theta_rad)
  ):
    return _failure(
      MocCausticSimpleWaveTerminalStatus.DOWNSTREAM_BOUNDARY_FAILURE,
      request=request,
      trace=trace,
      event_seam_verified=True,
      handoff=handoff,
      message='downstream angle law does not reproduce the prepared local caustic bridge at the event',
    )
  ####

  try:
    shock = solve_marched_attached_shock_field(
      trace.state_at,
      trace.static_pressure_at,
      event,
      target_centerline_y_m=target_centerline_y_m,
      downstream_flow_angle_at=angle_law,
      incoming_handoff=handoff,
      sample_count=sample_count,
      branch=branch,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      maximum_segment_iterations=maximum_segment_iterations,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocCausticSimpleWaveTerminalStatus.SHOCK_FAILURE,
      request=request,
      trace=trace,
      event_seam_verified=True,
      handoff=handoff,
      message=f'simple-wave shock march raised: {error}',
    )
  ####
  terminal = shock.normal_shock_terminal
  terminal_verified = bool(
    shock.status is MocFreeBoundaryShockStatus.SUBSONIC_TERMINAL_REQUIRED
    and terminal is not None
    and terminal.converged
    and terminal.subsonic
    and terminal.shock_point_m is not None
  )
  if not terminal_verified:
    return _failure(
      MocCausticSimpleWaveTerminalStatus.SHOCK_FAILURE,
      request=request,
      trace=trace,
      shock=shock,
      terminal=terminal,
      event_seam_verified=True,
      handoff=handoff,
      message=f'simple-wave shock did not reach a typed normal-shock terminal: {shock.message}',
    )
  ####
  if len(shock.shock_points_m) < 4:
    return _failure(
      MocCausticSimpleWaveTerminalStatus.SHOCK_PREFIX_FAILURE,
      request=request,
      trace=trace,
      shock=shock,
      terminal=terminal,
      event_seam_verified=True,
      terminal_verified=terminal_verified,
      handoff=handoff,
      message='simple-wave terminal requires at least four retained supersonic shock samples',
    )
  ####

  try:
    shock_fit = fit_attached_shock_boundary(
      shock.upstream_states,
      shock.upstream_pressure_Pa,
      shock.shock_points_m,
      shock.downstream_flow_angles_rad,
      branch=branch,
      position_tolerance_m=position_tolerance_m,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocCausticSimpleWaveTerminalStatus.SHOCK_PREFIX_FAILURE,
      request=request,
      trace=trace,
      shock=shock,
      terminal=terminal,
      event_seam_verified=True,
      terminal_verified=terminal_verified,
      handoff=handoff,
      message=f'simple-wave shock-prefix fit raised: {error}',
    )
  ####
  shock_prefix_verified = bool(
    shock_fit.converged
    and len(shock_fit.boundary_states) == len(shock.shock_points_m)
    and shock_fit.maximum_shock_angle_residual_rad is not None
    and shock_fit.maximum_shock_angle_residual_rad <= shock_angle_tolerance_rad
  )
  if not shock_prefix_verified:
    return _failure(
      MocCausticSimpleWaveTerminalStatus.SHOCK_PREFIX_FAILURE,
      request=request,
      trace=trace,
      shock=shock,
      shock_fit=shock_fit,
      terminal=terminal,
      event_seam_verified=True,
      terminal_verified=terminal_verified,
      handoff=handoff,
      message=f'simple-wave shock prefix did not pass attached-boundary fitting: {shock_fit.message}',
    )
  ####

  first_boundary = shock_fit.boundary_states[0]
  local_bridge_state_verified = bool(
    _state_matches(
      first_boundary.state,
      local_downstream,
      position_tolerance_m=position_tolerance_m,
      state_tolerance=invariant_tolerance,
    )
    and _state_matches(
      shock.upstream_states[0],
      request.upstream_state,
      position_tolerance_m=position_tolerance_m,
      state_tolerance=invariant_tolerance,
    )
    and _pressure_matches(
      shock.upstream_pressure_Pa[0],
      request.upstream_static_pressure_Pa,
      invariant_tolerance,
    )
    and _pressure_matches(
      first_boundary.downstream_total_pressure_Pa,
      compression.downstream_total_pressure_Pa,
      invariant_tolerance,
    )
    and abs(
      (
        first_boundary.state.k_plus
        if request.downstream_invariant_family is CharacteristicFamily.PLUS
        else first_boundary.state.k_minus
      )
      - request.downstream_invariant_target
    ) <= invariant_tolerance * max(1.0, abs(request.downstream_invariant_target))
  )
  if not local_bridge_state_verified:
    return _failure(
      MocCausticSimpleWaveTerminalStatus.EVENT_SEAM_FAILURE,
      request=request,
      trace=trace,
      shock=shock,
      shock_fit=shock_fit,
      terminal=terminal,
      event_seam_verified=True,
      shock_prefix_verified=shock_prefix_verified,
      terminal_verified=terminal_verified,
      handoff=handoff,
      message='simple-wave shock prefix does not reproduce the prepared local caustic shock bridge',
    )
  ####

  try:
    continuation = continue_post_shock_characteristics_to_centerline_open(
      shock_fit.boundary_states,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
      pressure_tolerance=invariant_tolerance,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocCausticSimpleWaveTerminalStatus.DOWNSTREAM_ZONE_FAILURE,
      request=request,
      trace=trace,
      shock=shock,
      shock_fit=shock_fit,
      terminal=terminal,
      event_seam_verified=True,
      local_bridge_state_verified=True,
      shock_prefix_verified=shock_prefix_verified,
      terminal_verified=terminal_verified,
      handoff=handoff,
      message=f'simple-wave open C- continuation raised: {error}',
    )
  ####
  if not continuation.converged:
    return _failure(
      MocCausticSimpleWaveTerminalStatus.DOWNSTREAM_ZONE_FAILURE,
      request=request,
      trace=trace,
      shock=shock,
      shock_fit=shock_fit,
      continuation=continuation,
      terminal=terminal,
      event_seam_verified=True,
      local_bridge_state_verified=True,
      shock_prefix_verified=shock_prefix_verified,
      terminal_verified=terminal_verified,
      handoff=handoff,
      message=f'simple-wave open C- continuation did not converge: {continuation.message}',
    )
  ####
  first_layer = assemble_post_shock_first_layer(
    continuation,
    position_tolerance_m=position_tolerance_m,
    invariant_tolerance=invariant_tolerance,
  )
  if not first_layer.converged:
    return _failure(
      MocCausticSimpleWaveTerminalStatus.DOWNSTREAM_ZONE_FAILURE,
      request=request,
      trace=trace,
      shock=shock,
      shock_fit=shock_fit,
      continuation=continuation,
      first_layer=first_layer,
      terminal=terminal,
      event_seam_verified=True,
      local_bridge_state_verified=True,
      shock_prefix_verified=shock_prefix_verified,
      terminal_verified=terminal_verified,
      handoff=handoff,
      message=f'simple-wave first downstream layer did not converge: {first_layer.message}',
    )
  ####
  zone = assemble_post_shock_characteristic_zone(
    continuation,
    first_layer,
    shock_fit.boundary_states,
    position_tolerance_m=position_tolerance_m,
    invariant_tolerance=invariant_tolerance,
  )
  downstream_zone_verified = zone.converged and zone.state_sampling_available
  if not downstream_zone_verified:
    return _failure(
      MocCausticSimpleWaveTerminalStatus.DOWNSTREAM_ZONE_FAILURE,
      request=request,
      trace=trace,
      shock=shock,
      shock_fit=shock_fit,
      continuation=continuation,
      first_layer=first_layer,
      zone=zone,
      terminal=terminal,
      event_seam_verified=True,
      local_bridge_state_verified=True,
      shock_prefix_verified=shock_prefix_verified,
      terminal_verified=terminal_verified,
      handoff=handoff,
      message=f'simple-wave open post-shock zone did not converge: {zone.message}',
    )
  ####

  upstream_coupling_verified = all(
    (
      (sampled_state := trace.state_at(point, position_tolerance_m=position_tolerance_m)) is not None
      and (sampled_pressure := trace.static_pressure_at(point, position_tolerance_m=position_tolerance_m)) is not None
      and _state_matches(
        sampled_state,
        expected_state,
        position_tolerance_m=position_tolerance_m,
        state_tolerance=invariant_tolerance,
      )
      and _pressure_matches(sampled_pressure, expected_pressure, invariant_tolerance)
    )
    for point, expected_state, expected_pressure in zip(
      shock.shock_points_m,
      shock.upstream_states,
      shock.upstream_pressure_Pa,
      strict=True,
    )
  )
  if not upstream_coupling_verified:
    return _failure(
      MocCausticSimpleWaveTerminalStatus.UPSTREAM_FIELD_FAILURE,
      request=request,
      trace=trace,
      shock=shock,
      shock_fit=shock_fit,
      continuation=continuation,
      first_layer=first_layer,
      zone=zone,
      terminal=terminal,
      event_seam_verified=True,
      local_bridge_state_verified=True,
      shock_prefix_verified=shock_prefix_verified,
      downstream_zone_verified=downstream_zone_verified,
      terminal_verified=terminal_verified,
      handoff=handoff,
      message='simple-wave shock prefix did not retain the solver-owned upstream trace samples',
    )
  ####
  return MocCausticSimpleWaveTerminalResult(
    status=MocCausticSimpleWaveTerminalStatus.CONVERGED_OPEN_TERMINAL_FIELD,
    request=request,
    trace=trace,
    shock=shock,
    shock_fit=shock_fit,
    continuation=continuation,
    first_layer=first_layer,
    zone=zone,
    terminal=terminal,
    event_point_m=event,
    event_seam_verified=True,
    local_bridge_state_verified=True,
    upstream_coupling_verified=True,
    shock_prefix_verified=True,
    downstream_zone_verified=True,
    terminal_verified=True,
    incoming_handoff_states=tuple(sample.state for sample in handoff),
    incoming_handoff_total_pressure_Pa=tuple(sample.total_pressure_Pa for sample in handoff),
    message=(
      'solver-owned simple-wave trace fed a fitted supersonic shock prefix, '
      'an open post-shock characteristic zone, and a typed normal-shock '
      'terminal; mixed-regime closure and chain promotion remain blocked'
    ),
  )
####
