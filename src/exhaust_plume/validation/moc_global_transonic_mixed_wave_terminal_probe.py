"""Bounded terminal-reflection evidence for the global mixed-wave seam.

The global mixed-wave interface deliberately stops at an open shock/ambient
characteristic strip.  This module consumes that open trace with the existing
terminal-reflection and domain-bounded next-shock solvers.  The result is a
typed normal-shock *reference* for the next seam; it is not a subsonic field,
global feedback solve, physical shock-cell fit, or production closure.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite

from exhaust_plume.models.moc.terminal_patch import (
  MocTerminalReflectionPatchResult,
  assemble_terminal_trace_centerline_patch,
)
from exhaust_plume.models.moc.terminal_patch_solver import (
  MocTerminalReflectionPatchShockSolveResult,
  solve_marched_attached_shock_from_terminal_reflection_patch,
)
from exhaust_plume.models.moc.chain import (
  MocChainBoundarySample,
  validate_characteristic_trace,
)
from exhaust_plume.models.moc.primitives import CharacteristicFamily
from exhaust_plume.util.aero.shock_validity import ShockBranch
from exhaust_plume.validation.moc_global_transonic_mixed_wave_interface import (
  MocReflectedDomainGlobalTransonicMixedWaveInterfaceResult,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_TRANSONIC_MIXED_WAVE_TERMINAL_PROBE_OPERATOR_ID',
  'MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeStatus',
  'MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeResult',
  'probe_reflected_domain_global_transonic_mixed_wave_terminal_continuation',
  'MOC_REFLECTED_DOMAIN_GLOBAL_TRANSONIC_MIXED_WAVE_TERMINAL_PROBE_AUDIT_OPERATOR_ID',
  'MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeAuditStatus',
  'MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeAudit',
  'measure_reflected_domain_global_transonic_mixed_wave_terminal_probe',
)


MOC_REFLECTED_DOMAIN_GLOBAL_TRANSONIC_MIXED_WAVE_TERMINAL_PROBE_OPERATOR_ID = (
  'op.moc.reflected-domain.global-transonic-mixed-wave-terminal-probe'
)
MOC_REFLECTED_DOMAIN_GLOBAL_TRANSONIC_MIXED_WAVE_TERMINAL_PROBE_AUDIT_OPERATOR_ID = (
  'op.moc.reflected-domain.global-transonic-mixed-wave-terminal-probe-audit'
)
DEFAULT_TRACE_POSITION_TOLERANCE_M = 1.0e-5
DEFAULT_POSITION_TOLERANCE_M = 1.0e-5
DEFAULT_INVARIANT_TOLERANCE = 1.0e-10
DEFAULT_SHOCK_ANGLE_TOLERANCE_RAD = 2.0e-2
DEFAULT_MAXIMUM_SEGMENT_ITERATIONS = 24


class MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeStatus(str, Enum):
  """Outcome of one bounded terminal-reflection continuation probe."""

  CONVERGED_TERMINAL_REFERENCE = (
    'converged-global-transonic-mixed-wave-terminal-reference'
  )
  CONVERGED_OPEN_SHOCK_REFERENCE = (
    'converged-global-transonic-mixed-wave-open-shock-reference'
  )
  INVALID_INPUT = 'invalid_input'
  INTERFACE_REQUIRED = 'global-transonic-mixed-wave-interface-required'
  REFLECTION_PATCH_FAILURE = (
    'global-transonic-mixed-wave-terminal-reflection-patch-failure'
  )
  SHOCK_PROBE_FAILURE = (
    'global-transonic-mixed-wave-terminal-shock-probe-failure'
  )


class MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeAuditStatus(
  str,
  Enum,
):
  """Outcome of the independent retained-output terminal-probe audit."""

  VERIFIED = 'verified-global-transonic-mixed-wave-terminal-probe'
  INVALID_INPUT = 'invalid_input'
  CANDIDATE_REQUIRED = 'global-transonic-mixed-wave-terminal-probe-required'
  INTERFACE_FAILURE = 'global-transonic-mixed-wave-terminal-probe-interface-failure'
  TRACE_FAILURE = 'global-transonic-mixed-wave-terminal-probe-trace-failure'
  SHOCK_PATH_FAILURE = (
    'global-transonic-mixed-wave-terminal-probe-shock-path-failure'
  )
  TERMINAL_FAILURE = (
    'global-transonic-mixed-wave-terminal-probe-terminal-failure'
  )
  CLAIM_FLAG_FAILURE = (
    'global-transonic-mixed-wave-terminal-probe-claim-flag-failure'
  )


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeResult:
  """Research-only evidence for one reflected terminal trace and next shock."""

  status: MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeStatus
  interface: MocReflectedDomainGlobalTransonicMixedWaveInterfaceResult | None
  reflection_patch: MocTerminalReflectionPatchResult | None = None
  terminal_patch_shock_probe: (
    MocTerminalReflectionPatchShockSolveResult | None
  ) = None
  trace_position_tolerance_m: float = DEFAULT_TRACE_POSITION_TOLERANCE_M
  position_tolerance_m: float = DEFAULT_POSITION_TOLERANCE_M
  invariant_tolerance: float = DEFAULT_INVARIANT_TOLERANCE
  shock_angle_tolerance_rad: float = DEFAULT_SHOCK_ANGLE_TOLERANCE_RAD
  maximum_segment_iterations: int = DEFAULT_MAXIMUM_SEGMENT_ITERATIONS
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeStatus,
    ):
      raise TypeError('status must be a terminal-probe status')
    ####
    if self.interface is not None and not isinstance(
      self.interface,
      MocReflectedDomainGlobalTransonicMixedWaveInterfaceResult,
    ):
      raise TypeError('interface must be a typed mixed-wave interface or None')
    ####
    if self.reflection_patch is not None and not isinstance(
      self.reflection_patch,
      MocTerminalReflectionPatchResult,
    ):
      raise TypeError('reflection_patch must be a typed reflection patch or None')
    ####
    if self.terminal_patch_shock_probe is not None and not isinstance(
      self.terminal_patch_shock_probe,
      MocTerminalReflectionPatchShockSolveResult,
    ):
      raise TypeError(
        'terminal_patch_shock_probe must be a typed shock probe or None'
      )
    ####
    for name in (
      'trace_position_tolerance_m',
      'position_tolerance_m',
      'invariant_tolerance',
      'shock_angle_tolerance_rad',
    ):
      value = float(getattr(self, name))
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      ####
      object.__setattr__(self, name, value)
    ####
    if (
      isinstance(self.maximum_segment_iterations, bool)
      or not isinstance(self.maximum_segment_iterations, int)
      or self.maximum_segment_iterations < 1
    ):
      raise ValueError('maximum_segment_iterations must be a positive integer')
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    """Whether the bounded terminal reference produced usable evidence."""

    return self.status in (
      MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeStatus
      .CONVERGED_TERMINAL_REFERENCE,
      MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeStatus
      .CONVERGED_OPEN_SHOCK_REFERENCE,
    )
  ####

  @property
  def reflection_patch_verified(self) -> bool:
    return bool(
      self.reflection_patch is not None
      and self.reflection_patch.converged
      and self.reflection_patch.outgoing_trace_validation is not None
      and self.reflection_patch.outgoing_trace_validation.converged
    )
  ####

  @property
  def shock_probe_verified(self) -> bool:
    """Whether the shock path stayed inside the retained reflection patch."""

    probe = self.terminal_patch_shock_probe
    return bool(
      probe is not None
      and probe.coupling.converged
      and len(probe.shock.shock_points_m) == probe.coupling.sampled_count
      and len(probe.shock.upstream_pressure_Pa) == probe.coupling.sampled_count
    )
  ####

  @property
  def terminal_reference_verified(self) -> bool:
    """Whether a typed subsonic normal-shock reference was retained."""

    probe = self.terminal_patch_shock_probe
    return bool(
      self.shock_probe_verified
      and probe is not None
      and probe.physical_terminal_verified
    )
  ####

  @property
  def physical_closure_verified(self) -> bool:
    """A normal-shock reference does not close its downstream subsonic field."""

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

  def as_report(self) -> dict[str, object]:
    probe = self.terminal_patch_shock_probe
    terminal = None if probe is None else probe.shock.normal_shock_terminal
    return {
      'model': (
        MOC_REFLECTED_DOMAIN_GLOBAL_TRANSONIC_MIXED_WAVE_TERMINAL_PROBE_OPERATOR_ID
      ),
      'status': self.status.value,
      'converged': self.converged,
      'reflection_patch_verified': self.reflection_patch_verified,
      'shock_probe_verified': self.shock_probe_verified,
      'terminal_reference_verified': self.terminal_reference_verified,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'trace_position_tolerance_m': self.trace_position_tolerance_m,
      'position_tolerance_m': self.position_tolerance_m,
      'invariant_tolerance': self.invariant_tolerance,
      'shock_angle_tolerance_rad': self.shock_angle_tolerance_rad,
      'maximum_segment_iterations': self.maximum_segment_iterations,
      'interface_status': (
        None if self.interface is None else self.interface.status.value
      ),
      'reflection_patch': (
        None
        if self.reflection_patch is None
        else self.reflection_patch.as_report()
      ),
      'terminal_patch_shock_probe': (
        None if probe is None else probe.as_report()
      ),
      'terminal_normal_shock': (
        None if terminal is None else terminal.as_report()
      ),
      'message': self.message,
      'claim_status': (
        'bounded-terminal-normal-shock-reference-only; downstream-subsonic-'
        'field, global-feedback, physical-shock-cell, external-validation, '
        'and-production gates remain open'
      ),
    }
  ####


def _state_residual(
  actual: object,
  expected: object,
) -> float:
  """Return a normalized scalar residual for two retained MOC states."""

  values = (
    abs(float(getattr(actual, 'x_m')) - float(getattr(expected, 'x_m'))),
    abs(float(getattr(actual, 'y_m')) - float(getattr(expected, 'y_m'))),
    abs(float(getattr(actual, 'theta_rad')) - float(getattr(expected, 'theta_rad'))),
    abs(float(getattr(actual, 'mach')) - float(getattr(expected, 'mach'))),
    abs(float(getattr(actual, 'gamma')) - float(getattr(expected, 'gamma'))),
  )
  return max(values)


def _boundary_sample_residual(
  actual: MocChainBoundarySample,
  expected: MocChainBoundarySample,
) -> tuple[float, float]:
  return (
    _state_residual(actual.state, expected.state),
    abs(actual.total_pressure_Pa - expected.total_pressure_Pa),
  )


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeAudit:
  """Independent evidence remeasured from one retained terminal probe."""

  status: MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeAuditStatus
  candidate: MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeResult | None
  operator_id: str = (
    MOC_REFLECTED_DOMAIN_GLOBAL_TRANSONIC_MIXED_WAVE_TERMINAL_PROBE_AUDIT_OPERATOR_ID
  )
  interface_verified: bool = False
  input_trace_verified: bool = False
  output_trace_verified: bool = False
  patch_geometry_verified: bool = False
  shock_path_geometry_verified: bool = False
  shock_state_lineage_verified: bool = False
  shock_pressure_lineage_verified: bool = False
  terminal_reference_verified: bool = False
  claim_flags_verified: bool = False
  maximum_trace_state_residual: float | None = None
  maximum_trace_pressure_residual_Pa: float | None = None
  maximum_shock_state_residual: float | None = None
  maximum_shock_pressure_residual_Pa: float | None = None
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeAuditStatus,
    ):
      raise TypeError('status must be a terminal-probe audit status')
    ####
    if self.candidate is not None and not isinstance(
      self.candidate,
      MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeResult,
    ):
      raise TypeError('candidate must be a typed terminal-probe result or None')
    ####
    operator_id = str(self.operator_id)
    if not operator_id:
      raise ValueError('operator_id must be non-empty')
    ####
    object.__setattr__(self, 'operator_id', operator_id)
    for name in (
      'interface_verified',
      'input_trace_verified',
      'output_trace_verified',
      'patch_geometry_verified',
      'shock_path_geometry_verified',
      'shock_state_lineage_verified',
      'shock_pressure_lineage_verified',
      'terminal_reference_verified',
      'claim_flags_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    for name in (
      'maximum_trace_state_residual',
      'maximum_trace_pressure_residual_Pa',
      'maximum_shock_state_residual',
      'maximum_shock_pressure_residual_Pa',
    ):
      value = getattr(self, name)
      if value is None:
        continue
      ####
      numeric = float(value)
      if not isfinite(numeric) or numeric < 0.0:
        raise ValueError(f'{name} must be finite and nonnegative')
      ####
      object.__setattr__(self, name, numeric)
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeAuditStatus
      .VERIFIED
      and self.interface_verified
      and self.input_trace_verified
      and self.output_trace_verified
      and self.patch_geometry_verified
      and self.shock_path_geometry_verified
      and self.shock_state_lineage_verified
      and self.shock_pressure_lineage_verified
      and self.terminal_reference_verified
      and self.claim_flags_verified
    )
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

  def as_report(self) -> dict[str, object]:
    return {
      'operator_id': self.operator_id,
      'status': self.status.value,
      'converged': self.converged,
      'interface_verified': self.interface_verified,
      'input_trace_verified': self.input_trace_verified,
      'output_trace_verified': self.output_trace_verified,
      'patch_geometry_verified': self.patch_geometry_verified,
      'shock_path_geometry_verified': self.shock_path_geometry_verified,
      'shock_state_lineage_verified': self.shock_state_lineage_verified,
      'shock_pressure_lineage_verified': self.shock_pressure_lineage_verified,
      'terminal_reference_verified': self.terminal_reference_verified,
      'claim_flags_verified': self.claim_flags_verified,
      'maximum_trace_state_residual': self.maximum_trace_state_residual,
      'maximum_trace_pressure_residual_Pa': (
        self.maximum_trace_pressure_residual_Pa
      ),
      'maximum_shock_state_residual': self.maximum_shock_state_residual,
      'maximum_shock_pressure_residual_Pa': (
        self.maximum_shock_pressure_residual_Pa
      ),
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'candidate_status': (
        None if self.candidate is None else self.candidate.status.value
      ),
      'message': self.message,
    }
  ####


def _audit_failure(
  status: MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeAuditStatus,
  *,
  candidate: MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeResult | None,
  message: str,
  **kwargs: object,
) -> MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeAudit:
  return MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeAudit(
    status=status,
    candidate=candidate,
    message=message,
    **kwargs,
  )


def measure_reflected_domain_global_transonic_mixed_wave_terminal_probe(
  candidate: MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeResult,
) -> MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeAudit:
  """Remeasure retained terminal-probe outputs without rerunning the solver."""

  if not isinstance(
    candidate,
    MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeResult,
  ):
    return _audit_failure(
      MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeAuditStatus
      .INVALID_INPUT,
      candidate=None,
      message='candidate must be a typed terminal-probe result',
    )
  ####
  interface = candidate.interface
  patch = candidate.reflection_patch
  probe = candidate.terminal_patch_shock_probe
  if interface is None or patch is None or probe is None:
    return _audit_failure(
      MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeAuditStatus
      .CANDIDATE_REQUIRED,
      candidate=candidate,
      message='candidate must retain interface, reflection patch, and shock probe',
    )
  ####
  interface_verified = bool(
    interface.local_interface_verified
    and interface.chain_promotion_blocked
    and not interface.production_claim_allowed
    and interface.shock_ambient_strip is not None
  )
  if not interface_verified:
    return _audit_failure(
      MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeAuditStatus
      .INTERFACE_FAILURE,
      candidate=candidate,
      interface_verified=False,
      message='retained mixed-wave interface no longer passes its local gates',
    )
  ####
  strip = interface.shock_ambient_strip
  assert strip is not None
  expected_input = strip.terminal_trace_samples
  actual_input = (
    () if patch.input_trace_validation is None
    else patch.input_trace_validation.samples
  )
  trace_state_residuals: list[float] = []
  trace_pressure_residuals: list[float] = []
  if len(actual_input) == len(expected_input):
    for actual, expected in zip(actual_input, expected_input, strict=True):
      state_residual, pressure_residual = _boundary_sample_residual(
        actual,
        expected,
      )
      trace_state_residuals.append(state_residual)
      trace_pressure_residuals.append(pressure_residual)
  ####
  input_trace_verified = bool(
    patch.input_trace_validation is not None
    and patch.input_trace_validation.family is CharacteristicFamily.PLUS
    and patch.input_trace_validation.converged
    and len(actual_input) == len(expected_input)
    and all(
      residual <= candidate.trace_position_tolerance_m
      for residual in trace_state_residuals
    )
    and all(
      residual <= candidate.trace_position_tolerance_m * max(
        1.0,
        expected.total_pressure_Pa,
      )
      for residual, expected in zip(
        trace_pressure_residuals,
        expected_input,
        strict=True,
      )
    )
  )
  ####
  if not input_trace_verified:
    return _audit_failure(
      MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeAuditStatus
      .TRACE_FAILURE,
      candidate=candidate,
      interface_verified=True,
      input_trace_verified=False,
      maximum_trace_state_residual=max(trace_state_residuals, default=None),
      maximum_trace_pressure_residual_Pa=max(
        trace_pressure_residuals,
        default=None,
      ),
      message='retained reflection patch input trace does not match the open strip',
    )
  ####
  output_samples = tuple(
    MocChainBoundarySample(state=state, total_pressure_Pa=pressure)
    for state, pressure in zip(
      patch.outgoing_trace_states,
      patch.outgoing_trace_total_pressure_Pa,
      strict=True,
    )
  )
  output_remeasurement = validate_characteristic_trace(
    output_samples,
    CharacteristicFamily.MINUS,
    position_tolerance_m=candidate.trace_position_tolerance_m,
    forward_position_tolerance_m=candidate.trace_position_tolerance_m,
    invariant_tolerance=candidate.invariant_tolerance,
  ) if len(output_samples) >= 2 else None
  output_trace_verified = bool(
    patch.outgoing_trace_validation is not None
    and patch.outgoing_trace_validation.family is CharacteristicFamily.MINUS
    and patch.outgoing_trace_validation.converged
    and output_remeasurement is not None
    and output_remeasurement.converged
    and output_remeasurement.sample_count == len(patch.outgoing_trace_points_m)
  )
  axis_geometry_verified = bool(
    len(patch.axis_points_m) == len(patch.axis_states)
    and all(
      abs(point[1]) <= candidate.trace_position_tolerance_m
      and abs(state.y_m) <= candidate.trace_position_tolerance_m
      and abs(state.theta_rad) <= candidate.invariant_tolerance
      for point, state in zip(patch.axis_points_m, patch.axis_states, strict=True)
    )
    and all(
      second[0] > first[0] + candidate.trace_position_tolerance_m
      for first, second in zip(patch.axis_points_m, patch.axis_points_m[1:])
    )
  )
  patch_geometry_verified = bool(
    patch.converged
    and patch.topology.connected
    and patch.combined_topology.connected
    and patch.combined_topology.nonmanifold_edge_count == 0
    and axis_geometry_verified
    and output_trace_verified
  )
  if not patch_geometry_verified:
    return _audit_failure(
      MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeAuditStatus
      .TRACE_FAILURE,
      candidate=candidate,
      interface_verified=True,
      input_trace_verified=True,
      output_trace_verified=output_trace_verified,
      patch_geometry_verified=False,
      maximum_trace_state_residual=max(trace_state_residuals, default=None),
      maximum_trace_pressure_residual_Pa=max(
        trace_pressure_residuals,
        default=None,
      ),
      message='retained reflection patch geometry or outgoing trace failed remeasurement',
    )
  ####
  shock_points = tuple(probe.shock.shock_points_m)
  shock_path_geometry_verified = bool(
    probe.coupling.converged
    and len(shock_points) >= 2
    and len(probe.shock.upstream_states) == len(shock_points)
    and len(probe.shock.upstream_pressure_Pa) == len(shock_points)
    and len(probe.coupling.upstream_states) == len(shock_points)
    and all(
      second[0] > first[0] + candidate.position_tolerance_m
      and second[1] <= first[1] + candidate.position_tolerance_m
      for first, second in zip(shock_points, shock_points[1:])
    )
    and all(
      abs(first[0] - second[0]) <= candidate.position_tolerance_m
      and abs(first[1] - second[1]) <= candidate.position_tolerance_m
      for first, second in zip(
        shock_points,
        probe.coupling.shock_points_m,
        strict=True,
      )
    )
  )
  shock_state_residuals: list[float] = []
  shock_pressure_residuals: list[float] = []
  for point, coupling_state, coupling_pressure in zip(
    shock_points,
    probe.coupling.upstream_states,
    probe.coupling.upstream_pressure_Pa,
    strict=False,
  ):
    sampled_state = patch.state_at(
      point,
      position_tolerance_m=candidate.position_tolerance_m,
    )
    sampled_pressure = patch.static_pressure_at(
      point,
      position_tolerance_m=candidate.position_tolerance_m,
    )
    if sampled_state is None or sampled_pressure is None:
      continue
    ####
    shock_state_residuals.append(_state_residual(coupling_state, sampled_state))
    shock_pressure_residuals.append(
      abs(float(coupling_pressure) - float(sampled_pressure))
    )
  ####
  shock_state_lineage_verified = bool(
    shock_path_geometry_verified
    and len(shock_state_residuals) == len(shock_points)
    and all(
      residual <= candidate.position_tolerance_m
      for residual in shock_state_residuals
    )
  )
  shock_pressure_lineage_verified = bool(
    shock_path_geometry_verified
    and len(shock_pressure_residuals) == len(shock_points)
    and all(
      residual <= candidate.position_tolerance_m * max(
        1.0,
        abs(float(pressure)),
      )
      for residual, pressure in zip(
        shock_pressure_residuals,
        probe.coupling.upstream_pressure_Pa,
        strict=True,
      )
    )
  )
  if not shock_state_lineage_verified or not shock_pressure_lineage_verified:
    return _audit_failure(
      MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeAuditStatus
      .SHOCK_PATH_FAILURE,
      candidate=candidate,
      interface_verified=True,
      input_trace_verified=True,
      output_trace_verified=True,
      patch_geometry_verified=True,
      shock_path_geometry_verified=shock_path_geometry_verified,
      shock_state_lineage_verified=shock_state_lineage_verified,
      shock_pressure_lineage_verified=shock_pressure_lineage_verified,
      maximum_trace_state_residual=max(trace_state_residuals, default=None),
      maximum_trace_pressure_residual_Pa=max(
        trace_pressure_residuals,
        default=None,
      ),
      maximum_shock_state_residual=max(shock_state_residuals, default=None),
      maximum_shock_pressure_residual_Pa=max(
        shock_pressure_residuals,
        default=None,
      ),
      message='retained shock path is not fully reproducible inside the patch',
    )
  ####
  terminal = probe.shock.normal_shock_terminal
  strip_end_x = strip.terminal_trace_points_m[-1][0]
  terminal_reference_verified = bool(
    probe.physical_terminal_verified
    and terminal is not None
    and terminal.converged
    and terminal.subsonic
    and terminal.shock_point_m is not None
    and isfinite(float(terminal.shock_point_m[0]))
    and isfinite(float(terminal.shock_point_m[1]))
    and abs(
      float(terminal.shock_point_m[1]) - interface.target_centerline_y_m
    ) <= candidate.position_tolerance_m
    and float(terminal.shock_point_m[0]) > (
      float(strip_end_x) + candidate.position_tolerance_m
    )
  )
  if not terminal_reference_verified:
    return _audit_failure(
      MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeAuditStatus
      .TERMINAL_FAILURE,
      candidate=candidate,
      interface_verified=True,
      input_trace_verified=True,
      output_trace_verified=True,
      patch_geometry_verified=True,
      shock_path_geometry_verified=True,
      shock_state_lineage_verified=True,
      shock_pressure_lineage_verified=True,
      terminal_reference_verified=False,
      maximum_trace_state_residual=max(trace_state_residuals, default=None),
      maximum_trace_pressure_residual_Pa=max(
        trace_pressure_residuals,
        default=None,
      ),
      maximum_shock_state_residual=max(shock_state_residuals, default=None),
      maximum_shock_pressure_residual_Pa=max(
        shock_pressure_residuals,
        default=None,
      ),
      message='retained next-shock result no longer passes the terminal reference gates',
    )
  ####
  claim_flags_verified = bool(
    candidate.physical_closure_verified is False
    and candidate.chain_promotion_blocked
    and candidate.production_claim_allowed is False
    and patch.physical_closure_verified is False
    and patch.chain_promotion_blocked
    and probe.physical_closure_verified is False
    and probe.chain_promotion_blocked
  )
  if not claim_flags_verified:
    return _audit_failure(
      MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeAuditStatus
      .CLAIM_FLAG_FAILURE,
      candidate=candidate,
      interface_verified=True,
      input_trace_verified=True,
      output_trace_verified=True,
      patch_geometry_verified=True,
      shock_path_geometry_verified=True,
      shock_state_lineage_verified=True,
      shock_pressure_lineage_verified=True,
      terminal_reference_verified=True,
      claim_flags_verified=False,
      maximum_trace_state_residual=max(trace_state_residuals, default=None),
      maximum_trace_pressure_residual_Pa=max(
        trace_pressure_residuals,
        default=None,
      ),
      maximum_shock_state_residual=max(shock_state_residuals, default=None),
      maximum_shock_pressure_residual_Pa=max(
        shock_pressure_residuals,
        default=None,
      ),
      message='terminal-probe claim flags were weakened or inconsistent',
    )
  ####
  return MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeAudit(
    status=MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeAuditStatus
    .VERIFIED,
    candidate=candidate,
    interface_verified=True,
    input_trace_verified=True,
    output_trace_verified=True,
    patch_geometry_verified=True,
    shock_path_geometry_verified=True,
    shock_state_lineage_verified=True,
    shock_pressure_lineage_verified=True,
    terminal_reference_verified=True,
    claim_flags_verified=True,
    maximum_trace_state_residual=max(trace_state_residuals, default=None),
    maximum_trace_pressure_residual_Pa=max(
      trace_pressure_residuals,
      default=None,
    ),
    maximum_shock_state_residual=max(shock_state_residuals, default=None),
    maximum_shock_pressure_residual_Pa=max(
      shock_pressure_residuals,
      default=None,
    ),
    message=(
      'independent retained-output audit verified the bounded reflection '
      'patch, in-domain shock sampling, terminal reference, and non-promotion '
      'flags; downstream subsonic physics remains open'
    ),
  )


def _failure(
  status: MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeStatus,
  *,
  interface: MocReflectedDomainGlobalTransonicMixedWaveInterfaceResult | None,
  reflection_patch: MocTerminalReflectionPatchResult | None = None,
  terminal_patch_shock_probe: MocTerminalReflectionPatchShockSolveResult | None = None,
  trace_position_tolerance_m: float = DEFAULT_TRACE_POSITION_TOLERANCE_M,
  position_tolerance_m: float = DEFAULT_POSITION_TOLERANCE_M,
  invariant_tolerance: float = DEFAULT_INVARIANT_TOLERANCE,
  shock_angle_tolerance_rad: float = DEFAULT_SHOCK_ANGLE_TOLERANCE_RAD,
  maximum_segment_iterations: int = DEFAULT_MAXIMUM_SEGMENT_ITERATIONS,
  message: str,
) -> MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeResult:
  return MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeResult(
    status=status,
    interface=interface,
    reflection_patch=reflection_patch,
    terminal_patch_shock_probe=terminal_patch_shock_probe,
    trace_position_tolerance_m=trace_position_tolerance_m,
    position_tolerance_m=position_tolerance_m,
    invariant_tolerance=invariant_tolerance,
    shock_angle_tolerance_rad=shock_angle_tolerance_rad,
    maximum_segment_iterations=maximum_segment_iterations,
    message=message,
  )


def probe_reflected_domain_global_transonic_mixed_wave_terminal_continuation(
  interface: MocReflectedDomainGlobalTransonicMixedWaveInterfaceResult,
  *,
  trace_position_tolerance_m: float = DEFAULT_TRACE_POSITION_TOLERANCE_M,
  position_tolerance_m: float = DEFAULT_POSITION_TOLERANCE_M,
  invariant_tolerance: float = DEFAULT_INVARIANT_TOLERANCE,
  shock_angle_tolerance_rad: float = DEFAULT_SHOCK_ANGLE_TOLERANCE_RAD,
  maximum_segment_iterations: int = DEFAULT_MAXIMUM_SEGMENT_ITERATIONS,
  branch: ShockBranch = ShockBranch.WEAK,
) -> MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeResult:
  """Probe the open mixed-wave terminal without extrapolation or promotion."""

  if not isinstance(
    interface,
    MocReflectedDomainGlobalTransonicMixedWaveInterfaceResult,
  ):
    return _failure(
      MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeStatus.INVALID_INPUT,
      interface=None,
      message='interface must be a typed mixed-wave interface result',
    )
  ####
  try:
    trace_tolerance = float(trace_position_tolerance_m)
    position_tolerance = float(position_tolerance_m)
    resolved_invariant_tolerance = float(invariant_tolerance)
    shock_tolerance = float(shock_angle_tolerance_rad)
  except (TypeError, ValueError):
    return _failure(
      MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeStatus.INVALID_INPUT,
      interface=interface,
      message='terminal-probe tolerances must be numeric',
    )
  ####
  if not all(
    isfinite(value) and value > 0.0
    for value in (
      trace_tolerance,
      position_tolerance,
      resolved_invariant_tolerance,
      shock_tolerance,
    )
  ):
    return _failure(
      MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeStatus.INVALID_INPUT,
      interface=interface,
      trace_position_tolerance_m=trace_tolerance,
      position_tolerance_m=position_tolerance,
      invariant_tolerance=resolved_invariant_tolerance,
      shock_angle_tolerance_rad=shock_tolerance,
      message='terminal-probe tolerances must be finite and positive',
    )
  ####
  if (
    isinstance(maximum_segment_iterations, bool)
    or not isinstance(maximum_segment_iterations, int)
    or maximum_segment_iterations < 1
  ):
    return _failure(
      MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeStatus.INVALID_INPUT,
      interface=interface,
      trace_position_tolerance_m=trace_tolerance,
      position_tolerance_m=position_tolerance,
      invariant_tolerance=resolved_invariant_tolerance,
      shock_angle_tolerance_rad=shock_tolerance,
      message='maximum_segment_iterations must be a positive integer',
    )
  ####
  if not isinstance(branch, ShockBranch):
    return _failure(
      MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeStatus.INVALID_INPUT,
      interface=interface,
      trace_position_tolerance_m=trace_tolerance,
      position_tolerance_m=position_tolerance,
      invariant_tolerance=resolved_invariant_tolerance,
      shock_angle_tolerance_rad=shock_tolerance,
      maximum_segment_iterations=maximum_segment_iterations,
      message='branch must be a ShockBranch',
    )
  ####
  if not interface.local_interface_verified:
    return _failure(
      MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeStatus
      .INTERFACE_REQUIRED,
      interface=interface,
      trace_position_tolerance_m=trace_tolerance,
      position_tolerance_m=position_tolerance,
      invariant_tolerance=resolved_invariant_tolerance,
      shock_angle_tolerance_rad=shock_tolerance,
      maximum_segment_iterations=maximum_segment_iterations,
      message=(
        'terminal continuation requires a locally verified open mixed-wave '
        'interface; no downstream state was inferred'
      ),
    )
  ####
  strip = interface.shock_ambient_strip
  if strip is None:
    return _failure(
      MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeStatus
      .INTERFACE_REQUIRED,
      interface=interface,
      trace_position_tolerance_m=trace_tolerance,
      position_tolerance_m=position_tolerance,
      invariant_tolerance=resolved_invariant_tolerance,
      shock_angle_tolerance_rad=shock_tolerance,
      maximum_segment_iterations=maximum_segment_iterations,
      message='locally verified interface retained no open shock/ambient strip',
    )
  ####
  try:
    reflection_patch = assemble_terminal_trace_centerline_patch(
      strip,
      trace_position_tolerance_m=trace_tolerance,
      trace_forward_tolerance_m=trace_tolerance,
      invariant_tolerance=resolved_invariant_tolerance,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeStatus
      .REFLECTION_PATCH_FAILURE,
      interface=interface,
      trace_position_tolerance_m=trace_tolerance,
      position_tolerance_m=position_tolerance,
      invariant_tolerance=resolved_invariant_tolerance,
      shock_angle_tolerance_rad=shock_tolerance,
      maximum_segment_iterations=maximum_segment_iterations,
      message=f'terminal reflection patch raised: {error}',
    )
  ####
  if not reflection_patch.converged or not reflection_patch.outgoing_trace_points_m:
    return _failure(
      MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeStatus
      .REFLECTION_PATCH_FAILURE,
      interface=interface,
      reflection_patch=reflection_patch,
      trace_position_tolerance_m=trace_tolerance,
      position_tolerance_m=position_tolerance,
      invariant_tolerance=resolved_invariant_tolerance,
      shock_angle_tolerance_rad=shock_tolerance,
      maximum_segment_iterations=maximum_segment_iterations,
      message=(
        'terminal reflection patch did not produce a usable outgoing trace: '
        f'{reflection_patch.message}'
      ),
    )
  ####
  try:
    terminal_patch_shock_probe = (
      solve_marched_attached_shock_from_terminal_reflection_patch(
        reflection_patch,
        reflection_patch.outgoing_trace_points_m[0],
        target_centerline_y_m=interface.target_centerline_y_m,
        downstream_flow_angle_rad=interface.target_centerline_flow_angle_rad,
        incoming_handoff=reflection_patch.outgoing_trace_samples,
        sample_count=len(reflection_patch.outgoing_trace_points_m),
        branch=branch,
        position_tolerance_m=position_tolerance,
        invariant_tolerance=resolved_invariant_tolerance,
        shock_angle_tolerance_rad=shock_tolerance,
        maximum_segment_iterations=maximum_segment_iterations,
      )
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeStatus
      .SHOCK_PROBE_FAILURE,
      interface=interface,
      reflection_patch=reflection_patch,
      trace_position_tolerance_m=trace_tolerance,
      position_tolerance_m=position_tolerance,
      invariant_tolerance=resolved_invariant_tolerance,
      shock_angle_tolerance_rad=shock_tolerance,
      maximum_segment_iterations=maximum_segment_iterations,
      message=f'terminal shock probe raised: {error}',
    )
  ####
  probe_verified = bool(
    terminal_patch_shock_probe.coupling.converged
    and len(terminal_patch_shock_probe.shock.shock_points_m)
    == terminal_patch_shock_probe.coupling.sampled_count
    and len(terminal_patch_shock_probe.shock.upstream_pressure_Pa)
    == terminal_patch_shock_probe.coupling.sampled_count
  )
  if not probe_verified:
    return _failure(
      MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeStatus
      .SHOCK_PROBE_FAILURE,
      interface=interface,
      reflection_patch=reflection_patch,
      terminal_patch_shock_probe=terminal_patch_shock_probe,
      trace_position_tolerance_m=trace_tolerance,
      position_tolerance_m=position_tolerance,
      invariant_tolerance=resolved_invariant_tolerance,
      shock_angle_tolerance_rad=shock_tolerance,
      maximum_segment_iterations=maximum_segment_iterations,
      message=(
        'terminal shock probe did not retain complete in-domain upstream '
        f'coupling: {terminal_patch_shock_probe.message}'
      ),
    )
  ####
  terminal_reference = terminal_patch_shock_probe.physical_terminal_verified
  status = (
    MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeStatus
    .CONVERGED_TERMINAL_REFERENCE
    if terminal_reference
    else MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeStatus
    .CONVERGED_OPEN_SHOCK_REFERENCE
  )
  return MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeResult(
    status=status,
    interface=interface,
    reflection_patch=reflection_patch,
    terminal_patch_shock_probe=terminal_patch_shock_probe,
    trace_position_tolerance_m=trace_tolerance,
    position_tolerance_m=position_tolerance,
    invariant_tolerance=resolved_invariant_tolerance,
    shock_angle_tolerance_rad=shock_tolerance,
    maximum_segment_iterations=maximum_segment_iterations,
    message=(
      'bounded terminal reflection and in-domain next-shock probe converged '
      'as research evidence; the normal-shock terminal still requires an '
      'independent downstream subsonic field and global feedback before '
      'physical closure or chain promotion'
    ),
  )
