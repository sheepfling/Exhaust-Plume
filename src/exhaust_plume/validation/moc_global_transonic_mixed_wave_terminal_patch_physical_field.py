"""Terminal-patch physical-field evidence for the mixed-wave seam.

The open mixed-wave interface cannot close its subsonic terminal by treating
the terminal point as another supersonic shock sample.  The bounded terminal
reflection patch provides the correct finite upstream domain for the next
ambient/centerline field.  This module consumes that patch with the existing
physical-field solver and then runs an independent conservative audit.

The result intentionally has a lower claim ceiling than a canonical global
reflected-domain solve.  A locally closed field is useful research evidence,
but the global feedback, cross-case refinement, external validation, and
production-provider gates remain explicit.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Any

from exhaust_plume.models.moc.coupled import (
  MocTerminalReflectionPatchPhysicalFieldResult,
  solve_marched_attached_shock_with_ambient_centerline_physical_field_from_terminal_reflection_patch,
)
from exhaust_plume.util.aero.shock_validity import ShockBranch
from exhaust_plume.validation.moc_euler import (
  MocPhysicalFieldEulerAudit,
  measure_moc_physical_field_euler_audit,
)
from exhaust_plume.validation.moc_global_transonic_mixed_wave_interface import (
  MocReflectedDomainGlobalTransonicMixedWaveInterfaceResult,
)
from exhaust_plume.validation.moc_global_transonic_mixed_wave_terminal_probe import (
  MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeResult,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_TRANSONIC_MIXED_WAVE_TERMINAL_PATCH_PHYSICAL_FIELD_OPERATOR_ID',
  'MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchPhysicalFieldStatus',
  'MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchPhysicalFieldResult',
  'solve_reflected_domain_global_transonic_mixed_wave_terminal_patch_physical_field',
)


MOC_REFLECTED_DOMAIN_GLOBAL_TRANSONIC_MIXED_WAVE_TERMINAL_PATCH_PHYSICAL_FIELD_OPERATOR_ID = (
  'op.moc.reflected-domain.global-transonic-mixed-wave-terminal-patch-physical-field'
)
DEFAULT_POSITION_TOLERANCE_M = 1.0e-9
DEFAULT_INVARIANT_TOLERANCE = 1.0e-10
DEFAULT_ATTACHMENT_PRESSURE_TOLERANCE = 1.0e-8
DEFAULT_PRESSURE_TOLERANCE = 1.0e-8
DEFAULT_TANGENT_TOLERANCE = 1.0e-8
DEFAULT_SHOCK_ANGLE_TOLERANCE_RAD = 1.0e-2
DEFAULT_MAXIMUM_SEGMENT_ITERATIONS = 24
DEFAULT_MAXIMUM_BOUNDARY_ITERATIONS = 16
DEFAULT_MAXIMUM_SHOOTING_ITERATIONS = 40
DEFAULT_EULER_SHOCK_RESIDUAL_TOLERANCE = 1.0e-2
DEFAULT_EULER_CELL_RESIDUAL_TOLERANCE = 1.0e-2


class MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchPhysicalFieldStatus(
  str,
  Enum,
):
  """Typed outcome of one bounded terminal-patch field attempt."""

  CONVERGED_RESEARCH_TERMINAL_PATCH_PHYSICAL_FIELD = (
    'converged-research-global-transonic-mixed-wave-terminal-patch-physical-field'
  )
  INVALID_INPUT = 'invalid_input'
  INTERFACE_REQUIRED = 'global-transonic-mixed-wave-interface-required'
  INTERFACE_FAILURE = 'global-transonic-mixed-wave-interface-failure'
  TERMINAL_PROBE_REQUIRED = (
    'global-transonic-mixed-wave-terminal-probe-required'
  )
  TERMINAL_PATCH_FAILURE = (
    'global-transonic-mixed-wave-terminal-patch-field-failure'
  )
  PHYSICAL_FIELD_FAILURE = (
    'global-transonic-mixed-wave-terminal-patch-physical-field-failure'
  )
  AUDIT_FAILURE = (
    'global-transonic-mixed-wave-terminal-patch-physical-field-audit-failure'
  )
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchPhysicalFieldResult:
  """Research-only terminal-patch field evidence with hard claim gates."""

  status: MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchPhysicalFieldStatus
  interface: MocReflectedDomainGlobalTransonicMixedWaveInterfaceResult | None
  terminal_probe: MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeResult | None
  physical_field: MocTerminalReflectionPatchPhysicalFieldResult | None = None
  audit: MocPhysicalFieldEulerAudit | None = None
  outer_flow_angle_bracket: tuple[float, float] | None = None
  sample_count: int | None = None
  position_tolerance_m: float = DEFAULT_POSITION_TOLERANCE_M
  invariant_tolerance: float = DEFAULT_INVARIANT_TOLERANCE
  attachment_pressure_tolerance: float = DEFAULT_ATTACHMENT_PRESSURE_TOLERANCE
  pressure_tolerance: float = DEFAULT_PRESSURE_TOLERANCE
  tangent_tolerance: float = DEFAULT_TANGENT_TOLERANCE
  shock_angle_tolerance_rad: float = DEFAULT_SHOCK_ANGLE_TOLERANCE_RAD
  maximum_segment_iterations: int = DEFAULT_MAXIMUM_SEGMENT_ITERATIONS
  maximum_boundary_iterations: int = DEFAULT_MAXIMUM_BOUNDARY_ITERATIONS
  maximum_shooting_iterations: int = DEFAULT_MAXIMUM_SHOOTING_ITERATIONS
  euler_shock_residual_tolerance: float = (
    DEFAULT_EULER_SHOCK_RESIDUAL_TOLERANCE
  )
  euler_cell_residual_tolerance: float = (
    DEFAULT_EULER_CELL_RESIDUAL_TOLERANCE
  )
  interface_consumed: bool = False
  source_field_consumed: bool = False
  frontier_consumed: bool = False
  terminal_probe_consumed: bool = False
  centerline_attempted: bool = False
  centerline_boundary_verified: bool = False
  independent_audit_verified: bool = False
  global_coupling_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  external_validation_required: bool = True
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchPhysicalFieldStatus,
    ):
      raise TypeError('status must be a terminal-patch physical-field status')
    ####
    if self.interface is not None and not isinstance(
      self.interface,
      MocReflectedDomainGlobalTransonicMixedWaveInterfaceResult,
    ):
      raise TypeError('interface must be a typed mixed-wave interface or None')
    ####
    if self.terminal_probe is not None and not isinstance(
      self.terminal_probe,
      MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeResult,
    ):
      raise TypeError('terminal_probe must be a typed terminal probe or None')
    ####
    if self.physical_field is not None and not isinstance(
      self.physical_field,
      MocTerminalReflectionPatchPhysicalFieldResult,
    ):
      raise TypeError(
        'physical_field must be a terminal-patch physical-field result or None'
      )
    ####
    if self.audit is not None and not isinstance(
      self.audit,
      MocPhysicalFieldEulerAudit,
    ):
      raise TypeError('audit must be a MocPhysicalFieldEulerAudit or None')
    ####
    if self.outer_flow_angle_bracket is not None:
      bracket = tuple(float(value) for value in self.outer_flow_angle_bracket)
      if len(bracket) != 2 or not all(isfinite(value) for value in bracket):
        raise ValueError(
          'outer_flow_angle_bracket must contain two finite values'
        )
      ####
      object.__setattr__(self, 'outer_flow_angle_bracket', bracket)
    ####
    if self.sample_count is not None and (
      isinstance(self.sample_count, bool)
      or not isinstance(self.sample_count, int)
      or self.sample_count < 3
    ):
      raise ValueError('sample_count must be an integer of at least three')
    ####
    for name in (
      'position_tolerance_m',
      'invariant_tolerance',
      'attachment_pressure_tolerance',
      'pressure_tolerance',
      'tangent_tolerance',
      'shock_angle_tolerance_rad',
      'euler_shock_residual_tolerance',
      'euler_cell_residual_tolerance',
    ):
      value = float(getattr(self, name))
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      ####
      object.__setattr__(self, name, value)
    ####
    for name in (
      'maximum_segment_iterations',
      'maximum_boundary_iterations',
      'maximum_shooting_iterations',
    ):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f'{name} must be a positive integer')
      ####
    ####
    for name in (
      'interface_consumed',
      'source_field_consumed',
      'frontier_consumed',
      'terminal_probe_consumed',
      'centerline_attempted',
      'centerline_boundary_verified',
      'independent_audit_verified',
      'global_coupling_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
      'external_validation_required',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if not self.chain_promotion_blocked:
      raise ValueError(
        'global terminal-patch evidence must block chain promotion'
      )
    ####
    if self.global_coupling_verified:
      raise ValueError(
        'terminal-patch evidence cannot claim global coupling'
      )
    ####
    if self.production_claim_allowed:
      raise ValueError(
        'terminal-patch evidence cannot allow production claims'
      )
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def terminal_reference_verified(self) -> bool:
    """Whether the consumed probe retained a typed subsonic terminal."""

    return bool(
      self.terminal_probe is not None
      and self.terminal_probe.terminal_reference_verified
    )
  ####

  @property
  def local_physical_field_verified(self) -> bool:
    """Whether the local patch field and independent audit both passed."""

    return bool(
      self.status
      is MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchPhysicalFieldStatus
      .CONVERGED_RESEARCH_TERMINAL_PATCH_PHYSICAL_FIELD
      and self.interface_consumed
      and self.source_field_consumed
      and self.frontier_consumed
      and self.terminal_probe_consumed
      and self.centerline_attempted
      and self.centerline_boundary_verified
      and self.independent_audit_verified
      and self.physical_field is not None
      and self.physical_field.physical_closure_verified
      and self.physical_field.state_sampling_available
      and self.physical_field.upstream_coupling_verified
      and self.audit is not None
      and self.audit.converged
      and self.chain_promotion_blocked
      and not self.global_coupling_verified
      and not self.production_claim_allowed
    )
  ####

  @property
  def converged(self) -> bool:
    """Whether this research-layer field admission passed all local gates."""

    return self.local_physical_field_verified
  ####

  @property
  def physical_closure_verified(self) -> bool:
    """Global reflected-domain closure remains intentionally unverified."""

    return False
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'model': (
        MOC_REFLECTED_DOMAIN_GLOBAL_TRANSONIC_MIXED_WAVE_TERMINAL_PATCH_PHYSICAL_FIELD_OPERATOR_ID
      ),
      'status': self.status.value,
      'converged': self.converged,
      'local_physical_field_verified': self.local_physical_field_verified,
      'physical_closure_verified': self.physical_closure_verified,
      'interface_consumed': self.interface_consumed,
      'source_field_consumed': self.source_field_consumed,
      'frontier_consumed': self.frontier_consumed,
      'terminal_probe_consumed': self.terminal_probe_consumed,
      'terminal_reference_verified': self.terminal_reference_verified,
      'centerline_attempted': self.centerline_attempted,
      'centerline_boundary_verified': self.centerline_boundary_verified,
      'independent_audit_verified': self.independent_audit_verified,
      'global_coupling_verified': self.global_coupling_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'external_validation_required': self.external_validation_required,
      'interface_status': (
        None if self.interface is None else self.interface.status.value
      ),
      'terminal_probe_status': (
        None
        if self.terminal_probe is None
        else self.terminal_probe.status.value
      ),
      'physical_field': (
        None
        if self.physical_field is None
        else self.physical_field.as_report()
      ),
      'audit': None if self.audit is None else self.audit.as_report(),
      'outer_flow_angle_bracket': self.outer_flow_angle_bracket,
      'sample_count': self.sample_count,
      'position_tolerance_m': self.position_tolerance_m,
      'invariant_tolerance': self.invariant_tolerance,
      'attachment_pressure_tolerance': self.attachment_pressure_tolerance,
      'pressure_tolerance': self.pressure_tolerance,
      'tangent_tolerance': self.tangent_tolerance,
      'shock_angle_tolerance_rad': self.shock_angle_tolerance_rad,
      'maximum_segment_iterations': self.maximum_segment_iterations,
      'maximum_boundary_iterations': self.maximum_boundary_iterations,
      'maximum_shooting_iterations': self.maximum_shooting_iterations,
      'euler_shock_residual_tolerance': self.euler_shock_residual_tolerance,
      'euler_cell_residual_tolerance': self.euler_cell_residual_tolerance,
      'claim_status': (
        'research-only terminal-patch physical-field attempt; global feedback, '
        'cross-case refinement, external validation, and production claims '
        'remain blocked'
      ),
      'message': self.message,
    }
  ####
####


def _failure(
  status: MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchPhysicalFieldStatus,
  *,
  interface: MocReflectedDomainGlobalTransonicMixedWaveInterfaceResult | None,
  terminal_probe: MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeResult | None,
  message: str,
  **kwargs: object,
) -> MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchPhysicalFieldResult:
  return MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchPhysicalFieldResult(
    status=status,
    interface=interface,
    terminal_probe=terminal_probe,
    message=message,
    **kwargs,
  )
####


def solve_reflected_domain_global_transonic_mixed_wave_terminal_patch_physical_field(
  interface: MocReflectedDomainGlobalTransonicMixedWaveInterfaceResult,
  terminal_probe: MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeResult,
  *,
  outer_flow_angle_bracket: tuple[float, float],
  sample_count: int | None = None,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = DEFAULT_POSITION_TOLERANCE_M,
  invariant_tolerance: float = DEFAULT_INVARIANT_TOLERANCE,
  attachment_pressure_tolerance: float = DEFAULT_ATTACHMENT_PRESSURE_TOLERANCE,
  pressure_tolerance: float = DEFAULT_PRESSURE_TOLERANCE,
  tangent_tolerance: float = DEFAULT_TANGENT_TOLERANCE,
  shock_angle_tolerance_rad: float = DEFAULT_SHOCK_ANGLE_TOLERANCE_RAD,
  maximum_segment_iterations: int = DEFAULT_MAXIMUM_SEGMENT_ITERATIONS,
  maximum_boundary_iterations: int = DEFAULT_MAXIMUM_BOUNDARY_ITERATIONS,
  maximum_shooting_iterations: int = DEFAULT_MAXIMUM_SHOOTING_ITERATIONS,
  euler_shock_residual_tolerance: float = (
    DEFAULT_EULER_SHOCK_RESIDUAL_TOLERANCE
  ),
  euler_cell_residual_tolerance: float = (
    DEFAULT_EULER_CELL_RESIDUAL_TOLERANCE
  ),
  allow_zero_strength_attachment: bool = True,
) -> MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchPhysicalFieldResult:
  """Consume a verified terminal patch and attempt a local closed field.

  The outer angle bracket is caller-owned.  In the mixed-wave terminal case it
  must straddle the ambient-matched, zero-strength attachment carried by the
  patch; this function never infers or widens that bracket.  The returned
  result can expose a locally closed field even when the independent Euler
  audit rejects it, but it cannot claim global closure or production status.
  """

  status_type = (
    MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchPhysicalFieldStatus
  )
  if not isinstance(
    interface,
    MocReflectedDomainGlobalTransonicMixedWaveInterfaceResult,
  ):
    return _failure(
      status_type.INTERFACE_REQUIRED,
      interface=None,
      terminal_probe=(
        terminal_probe
        if isinstance(
          terminal_probe,
          MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeResult,
        )
        else None
      ),
      message='interface must be a typed mixed-wave interface result',
    )
  ####
  if not interface.local_interface_verified:
    return _failure(
      status_type.INTERFACE_FAILURE,
      interface=interface,
      terminal_probe=(
        terminal_probe
        if isinstance(
          terminal_probe,
          MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeResult,
        )
        else None
      ),
      interface_consumed=True,
      message=(
        'terminal-patch field admission requires a locally verified open '
        'mixed-wave interface'
      ),
    )
  ####
  if not isinstance(
    terminal_probe,
    MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeResult,
  ):
    return _failure(
      status_type.TERMINAL_PROBE_REQUIRED,
      interface=interface,
      terminal_probe=None,
      interface_consumed=True,
      source_field_consumed=True,
      frontier_consumed=True,
      message='terminal_probe must be a typed terminal-probe result',
    )
  ####
  if terminal_probe.interface is not interface:
    return _failure(
      status_type.TERMINAL_PROBE_REQUIRED,
      interface=interface,
      terminal_probe=terminal_probe,
      interface_consumed=True,
      source_field_consumed=True,
      frontier_consumed=True,
      message=(
        'terminal_probe must retain the exact interface object supplied to '
        'the terminal-patch field admission'
      ),
    )
  ####
  if not (
    terminal_probe.converged
    and terminal_probe.reflection_patch_verified
    and terminal_probe.terminal_reference_verified
    and terminal_probe.reflection_patch is not None
  ):
    return _failure(
      status_type.TERMINAL_PROBE_REQUIRED,
      interface=interface,
      terminal_probe=terminal_probe,
      interface_consumed=True,
      source_field_consumed=True,
      frontier_consumed=True,
      terminal_probe_consumed=True,
      message=(
        'terminal_probe must retain a converged reflection patch and typed '
        'subsonic terminal before field admission'
      ),
    )
  ####
  ambient_pressure = interface.ambient_pressure_Pa
  if ambient_pressure is None or not isfinite(float(ambient_pressure)) or ambient_pressure <= 0.0:
    return _failure(
      status_type.INVALID_INPUT,
      interface=interface,
      terminal_probe=terminal_probe,
      interface_consumed=True,
      source_field_consumed=True,
      frontier_consumed=True,
      terminal_probe_consumed=True,
      message='interface ambient pressure must be finite and positive',
    )
  ####
  try:
    bracket = tuple(float(value) for value in outer_flow_angle_bracket)
  except (TypeError, ValueError):
    bracket = ()
  ####
  if len(bracket) != 2 or not all(isfinite(value) for value in bracket) or bracket[0] >= bracket[1]:
    return _failure(
      status_type.INVALID_INPUT,
      interface=interface,
      terminal_probe=terminal_probe,
      outer_flow_angle_bracket=bracket,
      interface_consumed=True,
      source_field_consumed=True,
      frontier_consumed=True,
      terminal_probe_consumed=True,
      message='outer_flow_angle_bracket must be finite and strictly ordered',
    )
  ####
  if not isinstance(branch, ShockBranch):
    return _failure(
      status_type.INVALID_INPUT,
      interface=interface,
      terminal_probe=terminal_probe,
      outer_flow_angle_bracket=bracket,
      interface_consumed=True,
      source_field_consumed=True,
      frontier_consumed=True,
      terminal_probe_consumed=True,
      message='branch must be a ShockBranch',
    )
  ####
  numeric_tolerances = (
    position_tolerance_m,
    invariant_tolerance,
    attachment_pressure_tolerance,
    pressure_tolerance,
    tangent_tolerance,
    shock_angle_tolerance_rad,
    euler_shock_residual_tolerance,
    euler_cell_residual_tolerance,
  )
  try:
    tolerances = tuple(float(value) for value in numeric_tolerances)
  except (TypeError, ValueError):
    tolerances = ()
  ####
  if len(tolerances) != len(numeric_tolerances) or not all(
    isfinite(value) and value > 0.0 for value in tolerances
  ):
    return _failure(
      status_type.INVALID_INPUT,
      interface=interface,
      terminal_probe=terminal_probe,
      outer_flow_angle_bracket=bracket,
      interface_consumed=True,
      source_field_consumed=True,
      frontier_consumed=True,
      terminal_probe_consumed=True,
      message='field and audit tolerances must be finite and positive',
    )
  ####
  for name, value in (
    ('maximum_segment_iterations', maximum_segment_iterations),
    ('maximum_boundary_iterations', maximum_boundary_iterations),
    ('maximum_shooting_iterations', maximum_shooting_iterations),
  ):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
      return _failure(
        status_type.INVALID_INPUT,
        interface=interface,
        terminal_probe=terminal_probe,
        outer_flow_angle_bracket=bracket,
        interface_consumed=True,
        source_field_consumed=True,
        frontier_consumed=True,
        terminal_probe_consumed=True,
        message=f'{name} must be a positive integer',
      )
  ####
  if not isinstance(allow_zero_strength_attachment, bool):
    return _failure(
      status_type.INVALID_INPUT,
      interface=interface,
      terminal_probe=terminal_probe,
      outer_flow_angle_bracket=bracket,
      interface_consumed=True,
      source_field_consumed=True,
      frontier_consumed=True,
      terminal_probe_consumed=True,
      message='allow_zero_strength_attachment must be a bool',
    )
  ####
  patch = terminal_probe.reflection_patch
  assert patch is not None
  if len(patch.outgoing_trace_points_m) < 3:
    return _failure(
      status_type.TERMINAL_PATCH_FAILURE,
      interface=interface,
      terminal_probe=terminal_probe,
      outer_flow_angle_bracket=bracket,
      interface_consumed=True,
      source_field_consumed=True,
      frontier_consumed=True,
      terminal_probe_consumed=True,
      message='terminal reflection patch must retain at least three outgoing points',
    )
  ####
  resolved_sample_count = sample_count
  if resolved_sample_count is None:
    if interface.shock is not None:
      resolved_sample_count = len(interface.shock.shock_points_m)
    else:
      resolved_sample_count = len(patch.outgoing_trace_points_m) - 1
  ####
  if (
    isinstance(resolved_sample_count, bool)
    or not isinstance(resolved_sample_count, int)
    or resolved_sample_count < 3
  ):
    return _failure(
      status_type.INVALID_INPUT,
      interface=interface,
      terminal_probe=terminal_probe,
      outer_flow_angle_bracket=bracket,
      sample_count=resolved_sample_count,
      interface_consumed=True,
      source_field_consumed=True,
      frontier_consumed=True,
      terminal_probe_consumed=True,
      message='sample_count must be an integer of at least three',
    )
  ####
  start_point = patch.outgoing_trace_points_m[0]
  start_state = patch.state_at(
    start_point,
    position_tolerance_m=tolerances[0],
  )
  if start_state is None:
    return _failure(
      status_type.TERMINAL_PATCH_FAILURE,
      interface=interface,
      terminal_probe=terminal_probe,
      outer_flow_angle_bracket=bracket,
      sample_count=resolved_sample_count,
      interface_consumed=True,
      source_field_consumed=True,
      frontier_consumed=True,
      terminal_probe_consumed=True,
      message='terminal reflection patch cannot sample its outgoing start state',
    )
  ####
  start_y = float(start_point[1])
  target_y = float(interface.target_centerline_y_m)
  target_angle = float(interface.target_centerline_flow_angle_rad)
  if start_y <= target_y + tolerances[0]:
    return _failure(
      status_type.TERMINAL_PATCH_FAILURE,
      interface=interface,
      terminal_probe=terminal_probe,
      outer_flow_angle_bracket=bracket,
      sample_count=resolved_sample_count,
      interface_consumed=True,
      source_field_consumed=True,
      frontier_consumed=True,
      terminal_probe_consumed=True,
      message='terminal reflection patch start must lie above the centerline',
    )
  ####

  def reflected_downstream_angle_at(
    _index: int,
    point_m: tuple[float, float],
  ) -> float:
    upstream_state = patch.state_at(
      point_m,
      position_tolerance_m=tolerances[0],
    )
    if upstream_state is None:
      raise ValueError(
        f'terminal reflection patch has no state at requested point {point_m}'
      )
    fraction = (float(point_m[1]) - target_y) / (start_y - target_y)
    fraction = max(0.0, min(1.0, fraction))
    positive_reference = (
      target_angle
      + (start_state.theta_rad - target_angle) * fraction
    )
    # The retained shock curve descends at theta_upstream - beta.  Mirror the
    # old positive-turn reference around the local upstream direction so the
    # attached solver receives the physically matching negative signed turn;
    # the opt-in downstream solver then uses its magnitude for compression.
    return 2.0 * upstream_state.theta_rad - positive_reference
  ####

  common = dict(
    interface=interface,
    terminal_probe=terminal_probe,
    outer_flow_angle_bracket=bracket,
    sample_count=resolved_sample_count,
    position_tolerance_m=tolerances[0],
    invariant_tolerance=tolerances[1],
    attachment_pressure_tolerance=tolerances[2],
    pressure_tolerance=tolerances[3],
    tangent_tolerance=tolerances[4],
    shock_angle_tolerance_rad=tolerances[5],
    maximum_segment_iterations=maximum_segment_iterations,
    maximum_boundary_iterations=maximum_boundary_iterations,
    maximum_shooting_iterations=maximum_shooting_iterations,
    euler_shock_residual_tolerance=tolerances[6],
    euler_cell_residual_tolerance=tolerances[7],
    interface_consumed=True,
    source_field_consumed=True,
    frontier_consumed=True,
    terminal_probe_consumed=True,
    centerline_attempted=True,
  )
  ####
  try:
    physical_field = (
      solve_marched_attached_shock_with_ambient_centerline_physical_field_from_terminal_reflection_patch(
        patch,
        float(ambient_pressure),
        bracket[0],
        bracket[1],
        start_point_m=patch.outgoing_trace_points_m[0],
        target_centerline_y_m=interface.target_centerline_y_m,
        target_centerline_flow_angle_rad=interface.target_centerline_flow_angle_rad,
        incoming_handoff=patch.outgoing_trace_samples,
        patch_handoff=patch.outgoing_trace_samples,
        sample_count=resolved_sample_count,
        branch=branch,
        position_tolerance_m=tolerances[0],
        invariant_tolerance=tolerances[1],
        attachment_pressure_tolerance=tolerances[2],
        pressure_tolerance=tolerances[3],
        tangent_tolerance=tolerances[4],
        shock_angle_tolerance_rad=tolerances[5],
        maximum_segment_iterations=maximum_segment_iterations,
        maximum_boundary_iterations=maximum_boundary_iterations,
        maximum_shooting_iterations=maximum_shooting_iterations,
        allow_zero_strength_attachment=allow_zero_strength_attachment,
        allow_negative_turn=True,
        downstream_flow_angle_at=reflected_downstream_angle_at,
        continuation_law='reflected-negative-turn',
      )
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      status_type.TERMINAL_PATCH_FAILURE,
      message=f'terminal-patch physical-field solver raised: {error}',
      **common,
    )
  ####
  field = physical_field.field
  centerline_boundary_verified = bool(
    physical_field.physical_closure_verified
    and field is not None
    and field.physical_closure_verified
  )
  if not centerline_boundary_verified or field is None:
    return _failure(
      status_type.PHYSICAL_FIELD_FAILURE,
      physical_field=physical_field,
      centerline_boundary_verified=centerline_boundary_verified,
      message=(
        'terminal reflection patch did not produce a state-carrying '
        f'ambient-closed physical field: {physical_field.message}'
      ),
      **common,
    )
  ####
  try:
    audit = measure_moc_physical_field_euler_audit(
      field,
      shock_residual_tolerance=tolerances[6],
      cell_residual_tolerance=tolerances[7],
      position_tolerance_m=tolerances[0],
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      status_type.AUDIT_FAILURE,
      physical_field=physical_field,
      centerline_boundary_verified=True,
      message=f'independent terminal-patch Euler audit raised: {error}',
      **common,
    )
  ####
  independent_audit_verified = bool(audit.converged)
  if not independent_audit_verified:
    return _failure(
      status_type.AUDIT_FAILURE,
      physical_field=physical_field,
      audit=audit,
      centerline_boundary_verified=True,
      independent_audit_verified=False,
      message=(
        'terminal-patch field closed geometrically, but its independent '
        f'conservative audit did not pass: {audit.message}'
      ),
      **common,
    )
  ####
  return _failure(
    status_type.CONVERGED_RESEARCH_TERMINAL_PATCH_PHYSICAL_FIELD,
    physical_field=physical_field,
    audit=audit,
    centerline_boundary_verified=True,
    independent_audit_verified=True,
    message=(
      'terminal reflection patch produced a locally closed state-carrying '
      'physical field and the independent conservative audit passed; global '
      'feedback, external validation, and production claims remain pending'
    ),
    **common,
  )
####
