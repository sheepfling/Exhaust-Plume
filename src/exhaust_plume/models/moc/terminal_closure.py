"""Typed terminal-compression candidates for an open planar-MOC strip.

The shock/ambient characteristic strip ends on a downstream ``C+`` trace.
The next physical boundary in a continued shock-cell solve may be an attached
compression segment from that trace to the symmetry line, but that segment is
not the complete next MOC cell.  This module solves and validates only that
local boundary primitive.  It deliberately does not triangulate the open
trace, invent an upstream state along the compression, or promote the result
into the resolved chain.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite

from exhaust_plume.models.moc.ambient_shock_strip import (
  MocAmbientShockStripResult,
  MocAmbientShockStripStatus,
)
from exhaust_plume.models.moc.chain import (
  MocCharacteristicTraceResult,
  validate_characteristic_trace,
)
from exhaust_plume.models.moc.compression import (
  MocShockToCenterlineResult,
  solve_attached_shock_to_centerline,
)
from exhaust_plume.models.moc.primitives import (
  CharacteristicFamily,
  CharacteristicState,
)
from exhaust_plume.util.aero.shock_validity import ShockBranch

__all__ = (
  'MocTerminalCompressionStatus',
  'MocTerminalCompressionClosureResult',
  'solve_terminal_compression_candidate',
)


class MocTerminalCompressionStatus(str, Enum):
  """Outcome of a terminal compression-boundary candidate solve."""

  CONVERGED_LOCAL_COMPRESSION_CANDIDATE = (
    'converged_local_compression_candidate'
  )
  INVALID_INPUT = 'invalid_input'
  STRIP_FAILURE = 'open_strip_failure'
  TRACE_FAILURE = 'terminal_trace_failure'
  PRESSURE_FAILURE = 'terminal_pressure_failure'
  COMPRESSION_FAILURE = 'terminal_compression_failure'
####


@dataclass(frozen=True, slots=True)
class MocTerminalCompressionClosureResult:
  """A validated local compression segment at an open strip's endpoint.

  ``converged`` means only that the terminal trace and attached compression
  segment passed their local gates.  ``physical_closure_verified`` is always
  false: the characteristic patch between the incoming trace and the new
  compression boundary has not been solved here.
  """

  status: MocTerminalCompressionStatus
  strip_status: MocAmbientShockStripStatus | None
  terminal_trace_validation: MocCharacteristicTraceResult | None
  upstream_terminal_state: CharacteristicState | None
  upstream_terminal_pressure_Pa: float | None
  upstream_terminal_static_pressure_Pa: float | None
  terminal_static_pressure_residual: float | None
  ambient_pressure_Pa: float | None
  target_centerline_y_m: float | None
  compression: MocShockToCenterlineResult | None
  message: str = ''

  @property
  def converged(self) -> bool:
    return self.status is MocTerminalCompressionStatus.CONVERGED_LOCAL_COMPRESSION_CANDIDATE
  ####

  @property
  def physical_closure_verified(self) -> bool:
    """Whether this result can stand in for a complete first-cell solve."""

    return False
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    """Keep a local boundary primitive out of the resolved chain."""

    return True
  ####

  @property
  def accepted_for_chain(self) -> bool:
    """The explicit promotion gate, always false for this local primitive."""

    return False
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'accepted_for_chain': self.accepted_for_chain,
      'strip_status': None if self.strip_status is None else self.strip_status.value,
      'terminal_trace_validation': (
        None
        if self.terminal_trace_validation is None
        else self.terminal_trace_validation.as_report()
      ),
      'upstream_terminal_state': (
        None
        if self.upstream_terminal_state is None
        else {
          'x_m': self.upstream_terminal_state.x_m,
          'y_m': self.upstream_terminal_state.y_m,
          'theta_rad': self.upstream_terminal_state.theta_rad,
          'mach': self.upstream_terminal_state.mach,
          'gamma': self.upstream_terminal_state.gamma,
        }
      ),
      'upstream_terminal_pressure_Pa': self.upstream_terminal_pressure_Pa,
      'upstream_terminal_static_pressure_Pa': self.upstream_terminal_static_pressure_Pa,
      'terminal_static_pressure_residual': self.terminal_static_pressure_residual,
      'ambient_pressure_Pa': self.ambient_pressure_Pa,
      'target_centerline_y_m': self.target_centerline_y_m,
      'compression': None if self.compression is None else {
        'status': self.compression.status.value,
        'converged': self.compression.converged,
        'shock_start_m': self.compression.shock_start_m,
        'shock_end_m': self.compression.shock_end_m,
        'shock_angle_rad': self.compression.shock_angle_rad,
        'geometry_residual_m': self.compression.geometry_residual_m,
        'downstream_mach': self.compression.downstream_mach,
        'downstream_pressure_Pa': self.compression.downstream_pressure_Pa,
        'downstream_total_pressure_Pa': self.compression.downstream_total_pressure_Pa,
        'total_pressure_ratio': self.compression.total_pressure_ratio,
        'message': self.compression.message,
      },
      'message': self.message,
    }
  ####
####


def _failure(
  status: MocTerminalCompressionStatus,
  *,
  strip_status: MocAmbientShockStripStatus | None,
  trace_validation: MocCharacteristicTraceResult | None = None,
  upstream_state: CharacteristicState | None = None,
  upstream_pressure: float | None = None,
  upstream_static_pressure: float | None = None,
  pressure_residual: float | None = None,
  ambient_pressure: float | None = None,
  target_y: float | None = None,
  compression: MocShockToCenterlineResult | None = None,
  message: str,
) -> MocTerminalCompressionClosureResult:
  return MocTerminalCompressionClosureResult(
    status=status,
    strip_status=strip_status,
    terminal_trace_validation=trace_validation,
    upstream_terminal_state=upstream_state,
    upstream_terminal_pressure_Pa=upstream_pressure,
    upstream_terminal_static_pressure_Pa=upstream_static_pressure,
    terminal_static_pressure_residual=pressure_residual,
    ambient_pressure_Pa=ambient_pressure,
    target_centerline_y_m=target_y,
    compression=compression,
    message=message,
  )
####


def _static_pressure_from_total(
  state: CharacteristicState,
  total_pressure_Pa: float,
) -> float:
  return float(total_pressure_Pa) / (
    1.0 + 0.5 * (state.gamma - 1.0) * state.mach**2
  ) ** (state.gamma / (state.gamma - 1.0))
####


def solve_terminal_compression_candidate(
  strip: MocAmbientShockStripResult,
  *,
  ambient_pressure_Pa: float,
  target_centerline_y_m: float = 0.0,
  branch: ShockBranch = ShockBranch.WEAK,
  trace_position_tolerance_m: float = 1.0e-10,
  trace_invariant_tolerance: float = 1.0e-10,
  pressure_tolerance: float = 1.0e-8,
) -> MocTerminalCompressionClosureResult:
  """Solve the local compression segment after an open shock/ambient strip.

  The final sample of the strip's typed ``C+`` terminal trace supplies the
  upstream state and total pressure.  The local static pressure must agree
  with the requested ambient pressure, and a weak/strong attached shock must
  reach the requested centerline with a forward endpoint.  The resulting
  segment is evidence for a future cell closure solver, not that solver.

  ``trace_position_tolerance_m`` is explicit because a coarse diagonal trace
  is a polyline approximation to a characteristic.  The default remains the
  strict primitive tolerance; a validation harness may choose a declared
  mesh-scale tolerance while retaining the strict result in its report.
  """

  if not isinstance(strip, MocAmbientShockStripResult):
    return _failure(
      MocTerminalCompressionStatus.INVALID_INPUT,
      strip_status=None,
      message='strip must be a MocAmbientShockStripResult',
    )
  ####
  try:
    ambient_pressure = float(ambient_pressure_Pa)
    target_y = float(target_centerline_y_m)
  except (TypeError, ValueError):
    return _failure(
      MocTerminalCompressionStatus.INVALID_INPUT,
      strip_status=strip.status,
      message='ambient pressure and target centerline ordinate must be numeric',
    )
  ####
  if not isfinite(ambient_pressure) or ambient_pressure <= 0.0:
    return _failure(
      MocTerminalCompressionStatus.INVALID_INPUT,
      strip_status=strip.status,
      ambient_pressure=ambient_pressure,
      target_y=target_y,
      message='ambient_pressure_Pa must be finite and positive',
    )
  ####
  if not isfinite(target_y):
    return _failure(
      MocTerminalCompressionStatus.INVALID_INPUT,
      strip_status=strip.status,
      ambient_pressure=ambient_pressure,
      target_y=target_y,
      message='target_centerline_y_m must be finite',
    )
  ####
  if not isinstance(branch, ShockBranch):
    return _failure(
      MocTerminalCompressionStatus.INVALID_INPUT,
      strip_status=strip.status,
      ambient_pressure=ambient_pressure,
      target_y=target_y,
      message='branch must be a ShockBranch',
    )
  ####
  for name, value in (
    ('trace_position_tolerance_m', trace_position_tolerance_m),
    ('trace_invariant_tolerance', trace_invariant_tolerance),
    ('pressure_tolerance', pressure_tolerance),
  ):
    if not isfinite(float(value)) or value <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
    ####
  ####
  if (
    strip.status is not MocAmbientShockStripStatus.CONVERGED_OPEN
    or not strip.topology.connected
    or not strip.topology.forms_closed_zone
    or strip.topology.nonmanifold_edge_count
  ):
    return _failure(
      MocTerminalCompressionStatus.STRIP_FAILURE,
      strip_status=strip.status,
      ambient_pressure=ambient_pressure,
      target_y=target_y,
      message=(
        'terminal compression requires a converged connected open strip; '
        f'received {strip.status.value} with topology {strip.topology.message}'
      ),
    )
  ####

  trace_validation = validate_characteristic_trace(
    strip.terminal_trace_samples,
    CharacteristicFamily.PLUS,
    position_tolerance_m=trace_position_tolerance_m,
    invariant_tolerance=trace_invariant_tolerance,
  )
  if not trace_validation.converged:
    return _failure(
      MocTerminalCompressionStatus.TRACE_FAILURE,
      strip_status=strip.status,
      trace_validation=trace_validation,
      ambient_pressure=ambient_pressure,
      target_y=target_y,
      message=(
        'terminal compression requires a validated shock-sourced C+ trace: '
        f'{trace_validation.message}'
      ),
    )
  ####

  terminal_sample = trace_validation.samples[-1]
  terminal_state = terminal_sample.state
  terminal_pressure = terminal_sample.total_pressure_Pa
  terminal_static_pressure = _static_pressure_from_total(
    terminal_state,
    terminal_pressure,
  )
  pressure_residual = (
    terminal_static_pressure - ambient_pressure
  ) / ambient_pressure
  if abs(pressure_residual) > pressure_tolerance:
    return _failure(
      MocTerminalCompressionStatus.PRESSURE_FAILURE,
      strip_status=strip.status,
      trace_validation=trace_validation,
      upstream_state=terminal_state,
      upstream_pressure=terminal_pressure,
      upstream_static_pressure=terminal_static_pressure,
      pressure_residual=pressure_residual,
      ambient_pressure=ambient_pressure,
      target_y=target_y,
      message=(
        'terminal trace endpoint does not reproduce ambient static pressure: '
        f'residual={pressure_residual}'
      ),
    )
  ####

  try:
    compression = solve_attached_shock_to_centerline(
      terminal_state,
      upstream_pressure_Pa=terminal_static_pressure,
      target_centerline_y_m=target_y,
      target_centerline_flow_angle_rad=0.0,
      branch=branch,
    )
  except (ArithmeticError, FloatingPointError, ValueError) as error:
    return _failure(
      MocTerminalCompressionStatus.COMPRESSION_FAILURE,
      strip_status=strip.status,
      trace_validation=trace_validation,
      upstream_state=terminal_state,
      upstream_pressure=terminal_pressure,
      upstream_static_pressure=terminal_static_pressure,
      pressure_residual=pressure_residual,
      ambient_pressure=ambient_pressure,
      target_y=target_y,
      message=f'terminal compression solve failed: {error}',
    )
  ####
  if not compression.converged:
    return _failure(
      MocTerminalCompressionStatus.COMPRESSION_FAILURE,
      strip_status=strip.status,
      trace_validation=trace_validation,
      upstream_state=terminal_state,
      upstream_pressure=terminal_pressure,
      upstream_static_pressure=terminal_static_pressure,
      pressure_residual=pressure_residual,
      ambient_pressure=ambient_pressure,
      target_y=target_y,
      compression=compression,
      message=(
        'terminal C+ trace passed, but its attached compression candidate '
        f'did not converge: {compression.message}'
      ),
    )
  ####
  return MocTerminalCompressionClosureResult(
    status=MocTerminalCompressionStatus.CONVERGED_LOCAL_COMPRESSION_CANDIDATE,
    strip_status=strip.status,
    terminal_trace_validation=trace_validation,
    upstream_terminal_state=terminal_state,
    upstream_terminal_pressure_Pa=terminal_pressure,
    upstream_terminal_static_pressure_Pa=terminal_static_pressure,
    terminal_static_pressure_residual=pressure_residual,
    ambient_pressure_Pa=ambient_pressure,
    target_centerline_y_m=target_y,
    compression=compression,
    message=(
      'validated local attached compression candidate reaches the centerline; '
      'the downstream characteristic patch and chain-cell closure remain pending'
    ),
  )
####
