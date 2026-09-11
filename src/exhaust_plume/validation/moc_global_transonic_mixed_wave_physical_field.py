"""Strict physical-field admission attempt for the mixed-wave seam.

The mixed-wave interface is intentionally an open, local research seam.  This
module makes the next boundary-value attempt explicit: it consumes the exact
interface frontier, invokes the existing entropy-characteristic
ambient/centerline physical-field solver, and independently audits the
retained result.

Even a locally closed field remains below the global reflected-domain closure
and production claims.  No state is extrapolated beyond the bounded source
field, and no approximate angle law is promoted into a global feedback path.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Any

from exhaust_plume.models.moc.euler_entropy_characteristic_free_boundary import (
  MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryResult,
  MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryStatus,
  solve_euler_ambient_first_wedge_entropy_characteristic_free_boundary,
)
from exhaust_plume.util.aero.shock_validity import ShockBranch
from exhaust_plume.validation.moc_euler_entropy_characteristic_free_boundary import (
  MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryAudit,
  MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryAuditStatus,
  measure_moc_euler_ambient_first_wedge_entropy_characteristic_free_boundary,
)
from exhaust_plume.validation.moc_global_transonic_mixed_wave_interface import (
  MocReflectedDomainGlobalTransonicMixedWaveInterfaceResult,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_TRANSONIC_MIXED_WAVE_PHYSICAL_FIELD_OPERATOR_ID',
  'MocReflectedDomainGlobalTransonicMixedWavePhysicalFieldStatus',
  'MocReflectedDomainGlobalTransonicMixedWavePhysicalFieldResult',
  'solve_reflected_domain_global_transonic_mixed_wave_physical_field',
)


MOC_REFLECTED_DOMAIN_GLOBAL_TRANSONIC_MIXED_WAVE_PHYSICAL_FIELD_OPERATOR_ID = (
  'op.moc.reflected-domain.global-transonic-mixed-wave-physical-field'
)
DEFAULT_POSITION_TOLERANCE_M = 1.0e-10
DEFAULT_STATE_TOLERANCE = 1.0e-8
DEFAULT_INVARIANT_TOLERANCE = 1.0e-10
DEFAULT_ATTACHMENT_PRESSURE_TOLERANCE = 1.0e-8
DEFAULT_PRESSURE_TOLERANCE = 1.0e-8
DEFAULT_TANGENT_TOLERANCE = 1.0e-8
DEFAULT_SHOCK_ANGLE_TOLERANCE_RAD = 1.0e-2
DEFAULT_MAXIMUM_SEGMENT_ITERATIONS = 24
DEFAULT_MAXIMUM_BOUNDARY_ITERATIONS = 16
DEFAULT_MAXIMUM_SHOOTING_ITERATIONS = 40


class MocReflectedDomainGlobalTransonicMixedWavePhysicalFieldStatus(
  str,
  Enum,
):
  """Typed outcome of one strict local physical-field attempt."""

  CONVERGED_RESEARCH_PHYSICAL_FIELD = (
    'converged-research-global-transonic-mixed-wave-physical-field'
  )
  INVALID_INPUT = 'invalid_input'
  INTERFACE_REQUIRED = 'global-transonic-mixed-wave-interface-required'
  INTERFACE_FAILURE = 'global-transonic-mixed-wave-interface-failure'
  SOURCE_FIELD_FAILURE = 'global-transonic-mixed-wave-source-field-failure'
  UPSTREAM_FIELD_BOUNDARY = (
    'global-transonic-mixed-wave-upstream-field-boundary'
  )
  SUBSONIC_TERMINAL_REQUIRED = (
    'global-transonic-mixed-wave-subsonic-terminal-required'
  )
  CENTERLINE_BOUNDARY_FAILURE = (
    'global-transonic-mixed-wave-centerline-boundary-failure'
  )
  PHYSICAL_FIELD_FAILURE = 'global-transonic-mixed-wave-physical-field-failure'
  AUDIT_FAILURE = 'global-transonic-mixed-wave-physical-field-audit-failure'


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalTransonicMixedWavePhysicalFieldResult:
  """Retained evidence for the bounded physical-field admission attempt."""

  status: MocReflectedDomainGlobalTransonicMixedWavePhysicalFieldStatus
  interface: MocReflectedDomainGlobalTransonicMixedWaveInterfaceResult | None
  physical_field: (
    MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryResult | None
  ) = None
  audit: MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryAudit | None = None
  outer_flow_angle_bracket: tuple[float, float] | None = None
  sample_count: int | None = None
  position_tolerance_m: float = DEFAULT_POSITION_TOLERANCE_M
  state_tolerance: float = DEFAULT_STATE_TOLERANCE
  invariant_tolerance: float = DEFAULT_INVARIANT_TOLERANCE
  attachment_pressure_tolerance: float = DEFAULT_ATTACHMENT_PRESSURE_TOLERANCE
  pressure_tolerance: float = DEFAULT_PRESSURE_TOLERANCE
  tangent_tolerance: float = DEFAULT_TANGENT_TOLERANCE
  shock_angle_tolerance_rad: float = DEFAULT_SHOCK_ANGLE_TOLERANCE_RAD
  maximum_segment_iterations: int = DEFAULT_MAXIMUM_SEGMENT_ITERATIONS
  maximum_boundary_iterations: int = DEFAULT_MAXIMUM_BOUNDARY_ITERATIONS
  maximum_shooting_iterations: int = DEFAULT_MAXIMUM_SHOOTING_ITERATIONS
  allow_zero_strength_attachment: bool = False
  allow_zero_strength_endpoints: bool = False
  interface_consumed: bool = False
  source_field_consumed: bool = False
  frontier_consumed: bool = False
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
      MocReflectedDomainGlobalTransonicMixedWavePhysicalFieldStatus,
    ):
      raise TypeError('status must be a typed physical-field status')
    ####
    if self.interface is not None and not isinstance(
      self.interface,
      MocReflectedDomainGlobalTransonicMixedWaveInterfaceResult,
    ):
      raise TypeError('interface must be a typed mixed-wave interface or None')
    ####
    if self.physical_field is not None and not isinstance(
      self.physical_field,
      MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryResult,
    ):
      raise TypeError('physical_field must be a typed free-boundary result or None')
    ####
    if self.audit is not None and not isinstance(
      self.audit,
      MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryAudit,
    ):
      raise TypeError('audit must be a typed free-boundary audit or None')
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
    if self.sample_count is not None:
      if (
        isinstance(self.sample_count, bool)
        or not isinstance(self.sample_count, int)
        or self.sample_count < 3
      ):
        raise ValueError('sample_count must be an integer of at least three')
      ####
    ####
    for name in (
      'position_tolerance_m',
      'state_tolerance',
      'invariant_tolerance',
      'attachment_pressure_tolerance',
      'pressure_tolerance',
      'tangent_tolerance',
      'shock_angle_tolerance_rad',
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
      'allow_zero_strength_attachment',
      'allow_zero_strength_endpoints',
      'interface_consumed',
      'source_field_consumed',
      'frontier_consumed',
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
      raise ValueError('physical-field evidence must block chain promotion')
    ####
    if self.global_coupling_verified:
      raise ValueError(
        'a local mixed-wave physical-field attempt cannot claim global coupling'
      )
    ####
    if self.production_claim_allowed:
      raise ValueError('physical-field evidence cannot allow production claims')
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def local_physical_field_verified(self) -> bool:
    """Whether the local reflected field and its independent audit passed."""

    return bool(
      self.status
      is MocReflectedDomainGlobalTransonicMixedWavePhysicalFieldStatus
      .CONVERGED_RESEARCH_PHYSICAL_FIELD
      and self.interface_consumed
      and self.source_field_consumed
      and self.frontier_consumed
      and self.centerline_attempted
      and self.centerline_boundary_verified
      and self.independent_audit_verified
      and self.physical_field is not None
      and self.physical_field.local_consistency_verified
      and self.audit is not None
      and self.audit.converged
      and self.audit.reflected_free_boundary_verified
      and self.chain_promotion_blocked
      and not self.global_coupling_verified
      and not self.production_claim_allowed
    )
  ####

  @property
  def converged(self) -> bool:
    return self.local_physical_field_verified
  ####

  @property
  def physical_closure_verified(self) -> bool:
    """A local field does not close the global reflected-domain problem."""

    return False
  ####

  @property
  def subsonic_terminal_required(self) -> bool:
    """Whether the retained ambient march reached its typed subsonic seam."""

    if self.physical_field is None or self.physical_field.physical_field is None:
      return False
    ####
    attachment = self.physical_field.physical_field.ambient_attachment
    return bool(
      attachment is not None
      and attachment.shock is not None
      and attachment.shock.subsonic_terminal_required
    )
  ####

  @property
  def terminal_model_verified(self) -> bool:
    """Whether the retained subsonic terminal has valid shock scalars."""

    if self.physical_field is None or self.physical_field.physical_field is None:
      return False
    ####
    attachment = self.physical_field.physical_field.ambient_attachment
    return bool(
      attachment is not None
      and attachment.shock is not None
      and attachment.shock.terminal_model_verified
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'model': MOC_REFLECTED_DOMAIN_GLOBAL_TRANSONIC_MIXED_WAVE_PHYSICAL_FIELD_OPERATOR_ID,
      'status': self.status.value,
      'converged': self.converged,
      'local_physical_field_verified': self.local_physical_field_verified,
      'physical_closure_verified': self.physical_closure_verified,
      'interface_consumed': self.interface_consumed,
      'source_field_consumed': self.source_field_consumed,
      'frontier_consumed': self.frontier_consumed,
      'centerline_attempted': self.centerline_attempted,
      'centerline_boundary_verified': self.centerline_boundary_verified,
      'independent_audit_verified': self.independent_audit_verified,
      'global_coupling_verified': self.global_coupling_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'external_validation_required': self.external_validation_required,
      'subsonic_terminal_required': self.subsonic_terminal_required,
      'terminal_model_verified': self.terminal_model_verified,
      'interface_status': (
        None if self.interface is None else self.interface.status.value
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
      'state_tolerance': self.state_tolerance,
      'invariant_tolerance': self.invariant_tolerance,
      'attachment_pressure_tolerance': self.attachment_pressure_tolerance,
      'pressure_tolerance': self.pressure_tolerance,
      'tangent_tolerance': self.tangent_tolerance,
      'shock_angle_tolerance_rad': self.shock_angle_tolerance_rad,
      'maximum_segment_iterations': self.maximum_segment_iterations,
      'maximum_boundary_iterations': self.maximum_boundary_iterations,
      'maximum_shooting_iterations': self.maximum_shooting_iterations,
      'allow_zero_strength_attachment': self.allow_zero_strength_attachment,
      'allow_zero_strength_endpoints': self.allow_zero_strength_endpoints,
      'claim_status': (
        'research-only local physical-field attempt; global feedback, '
        'shock-cell continuation, external validation, and production claims '
        'remain blocked'
      ),
      'message': self.message,
    }
  ####


def _failure(
  status: MocReflectedDomainGlobalTransonicMixedWavePhysicalFieldStatus,
  *,
  interface: MocReflectedDomainGlobalTransonicMixedWaveInterfaceResult | None,
  outer_flow_angle_bracket: tuple[float, float] | None = None,
  sample_count: int | None = None,
  position_tolerance_m: float = DEFAULT_POSITION_TOLERANCE_M,
  state_tolerance: float = DEFAULT_STATE_TOLERANCE,
  invariant_tolerance: float = DEFAULT_INVARIANT_TOLERANCE,
  attachment_pressure_tolerance: float = DEFAULT_ATTACHMENT_PRESSURE_TOLERANCE,
  pressure_tolerance: float = DEFAULT_PRESSURE_TOLERANCE,
  tangent_tolerance: float = DEFAULT_TANGENT_TOLERANCE,
  shock_angle_tolerance_rad: float = DEFAULT_SHOCK_ANGLE_TOLERANCE_RAD,
  maximum_segment_iterations: int = DEFAULT_MAXIMUM_SEGMENT_ITERATIONS,
  maximum_boundary_iterations: int = DEFAULT_MAXIMUM_BOUNDARY_ITERATIONS,
  maximum_shooting_iterations: int = DEFAULT_MAXIMUM_SHOOTING_ITERATIONS,
  allow_zero_strength_attachment: bool = False,
  allow_zero_strength_endpoints: bool = False,
  interface_consumed: bool = False,
  source_field_consumed: bool = False,
  frontier_consumed: bool = False,
  centerline_attempted: bool = False,
  centerline_boundary_verified: bool = False,
  independent_audit_verified: bool = False,
  physical_field: (
    MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryResult | None
  ) = None,
  audit: MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryAudit | None = None,
  message: str,
) -> MocReflectedDomainGlobalTransonicMixedWavePhysicalFieldResult:
  return MocReflectedDomainGlobalTransonicMixedWavePhysicalFieldResult(
    status=status,
    interface=interface,
    physical_field=physical_field,
    audit=audit,
    outer_flow_angle_bracket=outer_flow_angle_bracket,
    sample_count=sample_count,
    position_tolerance_m=position_tolerance_m,
    state_tolerance=state_tolerance,
    invariant_tolerance=invariant_tolerance,
    attachment_pressure_tolerance=attachment_pressure_tolerance,
    pressure_tolerance=pressure_tolerance,
    tangent_tolerance=tangent_tolerance,
    shock_angle_tolerance_rad=shock_angle_tolerance_rad,
    maximum_segment_iterations=maximum_segment_iterations,
    maximum_boundary_iterations=maximum_boundary_iterations,
    maximum_shooting_iterations=maximum_shooting_iterations,
    allow_zero_strength_attachment=allow_zero_strength_attachment,
    allow_zero_strength_endpoints=allow_zero_strength_endpoints,
    interface_consumed=interface_consumed,
    source_field_consumed=source_field_consumed,
    frontier_consumed=frontier_consumed,
    centerline_attempted=centerline_attempted,
    centerline_boundary_verified=centerline_boundary_verified,
    independent_audit_verified=independent_audit_verified,
    message=message,
  )


def _audit_is_typed_and_consistent(
  audit: MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryAudit,
) -> bool:
  """Return whether the independent audit recognized a typed outcome."""

  return audit.status in (
    MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryAuditStatus
    .CONVERGED_LOCAL_BOUNDARY_AUDIT,
    MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryAuditStatus
    .CONVERGED_LOCAL_CLOSED_AUDIT,
    MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryAuditStatus
    .ATTACHMENT_FAILURE,
    MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryAuditStatus
    .REFLECTED_FIELD_FAILURE,
    MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryAuditStatus
    .PATH_COVERAGE_FAILURE,
  )


def _subsonic_terminal_required(
  physical_field: MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryResult,
) -> bool:
  """Return whether the retained ambient march stopped at a subsonic seam."""

  if physical_field.physical_field is None:
    return False
  ####
  attachment = physical_field.physical_field.ambient_attachment
  return bool(
    attachment is not None
    and attachment.shock is not None
    and attachment.shock.subsonic_terminal_required
  )
####


def solve_reflected_domain_global_transonic_mixed_wave_physical_field(
  interface: MocReflectedDomainGlobalTransonicMixedWaveInterfaceResult,
  *,
  outer_flow_angle_bracket: tuple[float, float],
  sample_count: int | None = None,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = DEFAULT_POSITION_TOLERANCE_M,
  state_tolerance: float = DEFAULT_STATE_TOLERANCE,
  invariant_tolerance: float = DEFAULT_INVARIANT_TOLERANCE,
  attachment_pressure_tolerance: float = DEFAULT_ATTACHMENT_PRESSURE_TOLERANCE,
  pressure_tolerance: float = DEFAULT_PRESSURE_TOLERANCE,
  tangent_tolerance: float = DEFAULT_TANGENT_TOLERANCE,
  shock_angle_tolerance_rad: float = DEFAULT_SHOCK_ANGLE_TOLERANCE_RAD,
  maximum_segment_iterations: int = DEFAULT_MAXIMUM_SEGMENT_ITERATIONS,
  maximum_boundary_iterations: int = DEFAULT_MAXIMUM_BOUNDARY_ITERATIONS,
  maximum_shooting_iterations: int = DEFAULT_MAXIMUM_SHOOTING_ITERATIONS,
  allow_zero_strength_attachment: bool = False,
  allow_zero_strength_endpoints: bool = False,
) -> MocReflectedDomainGlobalTransonicMixedWavePhysicalFieldResult:
  """Attempt and audit the bounded local physical-field closure.

  The outer angle bracket is deliberately required from the caller.  It is a
  boundary-value input, not something this wrapper may infer from the
  approximate mixed-wave angle law.  ``sample_count=None`` uses the retained
  interface shock sample count, falling back to the exact interface frontier
  count; it never extrapolates the source field.
  """

  status_type = MocReflectedDomainGlobalTransonicMixedWavePhysicalFieldStatus
  if not isinstance(
    interface,
    MocReflectedDomainGlobalTransonicMixedWaveInterfaceResult,
  ):
    return _failure(
      status_type.INTERFACE_REQUIRED,
      interface=None,
      message='interface must be a typed global mixed-wave interface result',
    )
  ####
  if not interface.local_interface_verified:
    return _failure(
      status_type.INTERFACE_FAILURE,
      interface=interface,
      message=(
        'physical-field admission requires a locally verified mixed-wave '
        'interface; open or tampered interface evidence was not consumed'
      ),
    )
  ####
  source_field = interface.source_field
  if source_field is None or not source_field.local_consistency_verified:
    return _failure(
      status_type.SOURCE_FIELD_FAILURE,
      interface=interface,
      interface_consumed=True,
      message=(
        'physical-field admission requires the locally consistent exact '
        'entropy-characteristic source field retained by the interface'
      ),
    )
  ####
  frontier = tuple(interface.frontier)
  source_frontier = tuple(source_field.continuation_boundary)
  if not frontier or frontier != source_frontier:
    return _failure(
      status_type.SOURCE_FIELD_FAILURE,
      interface=interface,
      interface_consumed=True,
      source_field_consumed=True,
      message=(
        'interface frontier must exactly match the source field continuation '
        'boundary; no frontier remapping or extrapolation is allowed'
      ),
    )
  ####
  ambient_pressure = interface.ambient_pressure_Pa
  if ambient_pressure is None or not isfinite(float(ambient_pressure)) or ambient_pressure <= 0.0:
    return _failure(
      status_type.INVALID_INPUT,
      interface=interface,
      interface_consumed=True,
      source_field_consumed=True,
      frontier_consumed=True,
      message='interface ambient pressure must be finite and positive',
    )
  ####
  try:
    bracket = tuple(float(value) for value in outer_flow_angle_bracket)
  except (TypeError, ValueError):
    return _failure(
      status_type.INVALID_INPUT,
      interface=interface,
      interface_consumed=True,
      source_field_consumed=True,
      frontier_consumed=True,
      message='outer_flow_angle_bracket must contain two numeric values',
    )
  ####
  if (
    len(bracket) != 2
    or not all(isfinite(value) for value in bracket)
    or bracket[0] >= bracket[1]
  ):
    return _failure(
      status_type.INVALID_INPUT,
      interface=interface,
      outer_flow_angle_bracket=bracket,
      interface_consumed=True,
      source_field_consumed=True,
      frontier_consumed=True,
      message='outer_flow_angle_bracket must be finite and strictly ordered',
    )
  ####
  resolved_sample_count = sample_count
  if resolved_sample_count is None:
    if interface.shock is not None:
      resolved_sample_count = len(interface.shock.shock_points_m)
    else:
      resolved_sample_count = len(frontier)
  ####
  if (
    isinstance(resolved_sample_count, bool)
    or not isinstance(resolved_sample_count, int)
    or resolved_sample_count < 3
  ):
    return _failure(
      status_type.INVALID_INPUT,
      interface=interface,
      outer_flow_angle_bracket=bracket,
      sample_count=resolved_sample_count,
      interface_consumed=True,
      source_field_consumed=True,
      frontier_consumed=True,
      message='sample_count must be an integer of at least three',
    )
  ####
  if not isinstance(branch, ShockBranch):
    return _failure(
      status_type.INVALID_INPUT,
      interface=interface,
      outer_flow_angle_bracket=bracket,
      sample_count=resolved_sample_count,
      interface_consumed=True,
      source_field_consumed=True,
      frontier_consumed=True,
      message='branch must be a ShockBranch',
    )
  ####
  numeric_tolerances = (
    position_tolerance_m,
    state_tolerance,
    invariant_tolerance,
    attachment_pressure_tolerance,
    pressure_tolerance,
    tangent_tolerance,
    shock_angle_tolerance_rad,
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
      outer_flow_angle_bracket=bracket,
      sample_count=resolved_sample_count,
      interface_consumed=True,
      source_field_consumed=True,
      frontier_consumed=True,
      message='physical-field tolerances must be finite and positive',
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
        outer_flow_angle_bracket=bracket,
        sample_count=resolved_sample_count,
        interface_consumed=True,
        source_field_consumed=True,
        frontier_consumed=True,
        message=f'{name} must be a positive integer',
      )
  ####
  if not isinstance(allow_zero_strength_attachment, bool) or not isinstance(
    allow_zero_strength_endpoints,
    bool,
  ):
    return _failure(
      status_type.INVALID_INPUT,
      interface=interface,
      outer_flow_angle_bracket=bracket,
      sample_count=resolved_sample_count,
      interface_consumed=True,
      source_field_consumed=True,
      frontier_consumed=True,
      message='zero-strength options must be bool values',
    )
  ####
  try:
    physical_field = solve_euler_ambient_first_wedge_entropy_characteristic_free_boundary(
      source_field,
      frontier,
      frontier[0].point_m,
      float(ambient_pressure),
      bracket[0],
      bracket[1],
      target_centerline_y_m=interface.target_centerline_y_m,
      target_centerline_flow_angle_rad=interface.target_centerline_flow_angle_rad,
      sample_count=resolved_sample_count,
      branch=branch,
      position_tolerance_m=tolerances[0],
      state_tolerance=tolerances[1],
      invariant_tolerance=tolerances[2],
      attachment_pressure_tolerance=tolerances[3],
      pressure_tolerance=tolerances[4],
      tangent_tolerance=tolerances[5],
      shock_angle_tolerance_rad=tolerances[6],
      maximum_segment_iterations=maximum_segment_iterations,
      maximum_boundary_iterations=maximum_boundary_iterations,
      maximum_shooting_iterations=maximum_shooting_iterations,
      allow_zero_strength_attachment=allow_zero_strength_attachment,
      allow_zero_strength_endpoints=allow_zero_strength_endpoints,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      status_type.PHYSICAL_FIELD_FAILURE,
      interface=interface,
      outer_flow_angle_bracket=bracket,
      sample_count=resolved_sample_count,
      position_tolerance_m=tolerances[0],
      state_tolerance=tolerances[1],
      invariant_tolerance=tolerances[2],
      attachment_pressure_tolerance=tolerances[3],
      pressure_tolerance=tolerances[4],
      tangent_tolerance=tolerances[5],
      shock_angle_tolerance_rad=tolerances[6],
      maximum_segment_iterations=maximum_segment_iterations,
      maximum_boundary_iterations=maximum_boundary_iterations,
      maximum_shooting_iterations=maximum_shooting_iterations,
      allow_zero_strength_attachment=allow_zero_strength_attachment,
      allow_zero_strength_endpoints=allow_zero_strength_endpoints,
      interface_consumed=True,
      source_field_consumed=True,
      frontier_consumed=True,
      centerline_attempted=True,
      message=f'physical-field solver raised: {error}',
    )
  ####
  try:
    audit = measure_moc_euler_ambient_first_wedge_entropy_characteristic_free_boundary(
      physical_field,
      position_tolerance_m=tolerances[0],
      state_tolerance=tolerances[1],
      shock_residual_tolerance=tolerances[4],
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      status_type.AUDIT_FAILURE,
      interface=interface,
      outer_flow_angle_bracket=bracket,
      sample_count=resolved_sample_count,
      position_tolerance_m=tolerances[0],
      state_tolerance=tolerances[1],
      invariant_tolerance=tolerances[2],
      attachment_pressure_tolerance=tolerances[3],
      pressure_tolerance=tolerances[4],
      tangent_tolerance=tolerances[5],
      shock_angle_tolerance_rad=tolerances[6],
      maximum_segment_iterations=maximum_segment_iterations,
      maximum_boundary_iterations=maximum_boundary_iterations,
      maximum_shooting_iterations=maximum_shooting_iterations,
      allow_zero_strength_attachment=allow_zero_strength_attachment,
      allow_zero_strength_endpoints=allow_zero_strength_endpoints,
      interface_consumed=True,
      source_field_consumed=True,
      frontier_consumed=True,
      centerline_attempted=True,
      physical_field=physical_field,
      message=f'independent physical-field audit raised: {error}',
    )
  ####
  independent_audit_verified = _audit_is_typed_and_consistent(audit)
  centerline_boundary_verified = bool(
    physical_field.reflected_free_boundary_verified
    and audit.reflected_free_boundary_verified
  )
  common = dict(
    interface=interface,
    outer_flow_angle_bracket=bracket,
    sample_count=resolved_sample_count,
    position_tolerance_m=tolerances[0],
    state_tolerance=tolerances[1],
    invariant_tolerance=tolerances[2],
    attachment_pressure_tolerance=tolerances[3],
    pressure_tolerance=tolerances[4],
    tangent_tolerance=tolerances[5],
    shock_angle_tolerance_rad=tolerances[6],
    maximum_segment_iterations=maximum_segment_iterations,
    maximum_boundary_iterations=maximum_boundary_iterations,
    maximum_shooting_iterations=maximum_shooting_iterations,
    allow_zero_strength_attachment=allow_zero_strength_attachment,
    allow_zero_strength_endpoints=allow_zero_strength_endpoints,
    interface_consumed=True,
    source_field_consumed=True,
    frontier_consumed=True,
    centerline_attempted=True,
    centerline_boundary_verified=centerline_boundary_verified,
    independent_audit_verified=independent_audit_verified,
    physical_field=physical_field,
    audit=audit,
  )
  ####
  if not independent_audit_verified:
    return _failure(
      status_type.AUDIT_FAILURE,
      message=(
        'independent physical-field audit did not recognize a consistent '
        f'typed result: {audit.message}'
      ),
      **common,
    )
  ####
  if physical_field.status is (
    MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryStatus
    .UPSTREAM_FIELD_BOUNDARY
  ):
    status = status_type.UPSTREAM_FIELD_BOUNDARY
  elif physical_field.status is (
    MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryStatus
    .AMBIENT_ATTACHMENT_FAILURE
  ):
    status = (
      status_type.SUBSONIC_TERMINAL_REQUIRED
      if _subsonic_terminal_required(physical_field)
      else status_type.CENTERLINE_BOUNDARY_FAILURE
    )
  elif physical_field.status is (
    MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryStatus
    .REFLECTED_FIELD_FAILURE
  ):
    status = (
      status_type.SUBSONIC_TERMINAL_REQUIRED
      if _subsonic_terminal_required(physical_field)
      else status_type.CENTERLINE_BOUNDARY_FAILURE
    )
  elif (
    physical_field.status
    is MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryStatus
    .CONVERGED_LOCAL_PHYSICAL_FIELD
    and centerline_boundary_verified
    and audit.converged
  ):
    status = status_type.CONVERGED_RESEARCH_PHYSICAL_FIELD
  else:
    status = status_type.PHYSICAL_FIELD_FAILURE
  ####
  return _failure(
    status,
    message=(
      'retained exact mixed-wave frontier was consumed by the equation-level '
      f'physical-field attempt: {physical_field.message}'
    ),
    **common,
  )
