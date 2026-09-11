"""Independent audit for the two-sided entropy-aware terminal closure."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from exhaust_plume.models.moc.euler_two_sided_terminal_closure import (
  MocEulerTwoSidedTerminalClosureResult,
  MocEulerTwoSidedTerminalClosureStatus,
)
from exhaust_plume.validation.moc_euler_characteristic import (
  measure_moc_euler_ambient_first_wedge_terminal_characteristic_audit,
)
from exhaust_plume.validation.moc_euler_entropy import (
  measure_moc_euler_ambient_first_wedge_entropy_carry,
)
from exhaust_plume.validation.moc_euler_entropy_characteristic_field import (
  measure_moc_euler_ambient_first_wedge_entropy_characteristic_field,
)
from exhaust_plume.validation.moc_euler_two_sided_field_iteration import (
  measure_moc_euler_two_sided_field_iteration,
)

__all__ = (
  'MOC_EULER_TWO_SIDED_TERMINAL_CLOSURE_AUDIT_OPERATOR_ID',
  'MocEulerTwoSidedTerminalClosureAuditStatus',
  'MocEulerTwoSidedTerminalClosureAudit',
  'measure_moc_euler_two_sided_terminal_closure',
)


MOC_EULER_TWO_SIDED_TERMINAL_CLOSURE_AUDIT_OPERATOR_ID = (
  'op.moc.euler-two-sided-terminal-closure-audit'
)


class MocEulerTwoSidedTerminalClosureAuditStatus(str, Enum):
  """Typed outcomes for the terminal-closure audit."""

  CONVERGED_LOCAL_AUDIT = 'converged_two_sided_terminal_closure_audit'
  INVALID_INPUT = 'invalid_input'
  REQUEST_FAILURE = 'two_sided_terminal_closure_audit_request_failure'
  FIELD_ITERATION_FAILURE = 'two_sided_terminal_closure_audit_field_iteration_failure'
  TERMINAL_WEDGE_FAILURE = 'two_sided_terminal_closure_audit_terminal_wedge_failure'
  ENTROPY_CARRY_FAILURE = 'two_sided_terminal_closure_audit_entropy_carry_failure'
  INTERNAL_FIELD_FAILURE = 'two_sided_terminal_closure_audit_internal_field_failure'
  FLAG_FAILURE = 'two_sided_terminal_closure_audit_flag_failure'
####


@dataclass(frozen=True, slots=True)
class MocEulerTwoSidedTerminalClosureAudit:
  """Independent evidence for the local terminal closure sequence."""

  status: MocEulerTwoSidedTerminalClosureAuditStatus
  result_status: str | None
  request_verified: bool
  field_iteration_verified: bool
  terminal_geometry_verified: bool
  entropy_carry_verified: bool
  internal_characteristic_field_verified: bool
  component_audits_verified: bool
  physical_closure_verified: bool
  chain_promotion_blocked: bool
  production_claim_allowed: bool
  message: str = ''
  operator_id: str = MOC_EULER_TWO_SIDED_TERMINAL_CLOSURE_AUDIT_OPERATOR_ID

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocEulerTwoSidedTerminalClosureAuditStatus):
      raise TypeError(
        'status must be a MocEulerTwoSidedTerminalClosureAuditStatus'
      )
    ####
    if self.result_status is not None:
      object.__setattr__(self, 'result_status', str(self.result_status))
    ####
    for name in (
      'request_verified',
      'field_iteration_verified',
      'terminal_geometry_verified',
      'entropy_carry_verified',
      'internal_characteristic_field_verified',
      'component_audits_verified',
      'physical_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if self.physical_closure_verified:
      raise ValueError('terminal closure audit cannot claim physical closure')
    ####
    operator_id = str(self.operator_id)
    if not operator_id:
      raise ValueError('operator_id must be a non-empty string')
    ####
    object.__setattr__(self, 'operator_id', operator_id)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status is MocEulerTwoSidedTerminalClosureAuditStatus.CONVERGED_LOCAL_AUDIT
  ####

  @property
  def local_consistency_verified(self) -> bool:
    return bool(
      self.converged
      and self.request_verified
      and self.field_iteration_verified
      and self.terminal_geometry_verified
      and self.entropy_carry_verified
      and self.internal_characteristic_field_verified
      and self.component_audits_verified
      and not self.physical_closure_verified
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
    )
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'local_consistency_verified': self.local_consistency_verified,
      'result_status': self.result_status,
      'request_verified': self.request_verified,
      'field_iteration_verified': self.field_iteration_verified,
      'terminal_geometry_verified': self.terminal_geometry_verified,
      'entropy_carry_verified': self.entropy_carry_verified,
      'internal_characteristic_field_verified': (
        self.internal_characteristic_field_verified
      ),
      'component_audits_verified': self.component_audits_verified,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'message': self.message,
    }
  ####
####


def _failure(
  status: MocEulerTwoSidedTerminalClosureAuditStatus,
  message: str,
  *,
  result_status: str | None = None,
  request_verified: bool = False,
  field_iteration_verified: bool = False,
  terminal_geometry_verified: bool = False,
  entropy_carry_verified: bool = False,
  internal_characteristic_field_verified: bool = False,
  component_audits_verified: bool = False,
  physical_closure_verified: bool = False,
  chain_promotion_blocked: bool = True,
  production_claim_allowed: bool = False,
) -> MocEulerTwoSidedTerminalClosureAudit:
  return MocEulerTwoSidedTerminalClosureAudit(
    status=status,
    result_status=result_status,
    request_verified=request_verified,
    field_iteration_verified=field_iteration_verified,
    terminal_geometry_verified=terminal_geometry_verified,
    entropy_carry_verified=entropy_carry_verified,
    internal_characteristic_field_verified=internal_characteristic_field_verified,
    component_audits_verified=component_audits_verified,
    physical_closure_verified=physical_closure_verified,
    chain_promotion_blocked=chain_promotion_blocked,
    production_claim_allowed=production_claim_allowed,
    message=message,
  )
####


def measure_moc_euler_two_sided_terminal_closure(
  result: MocEulerTwoSidedTerminalClosureResult,
) -> MocEulerTwoSidedTerminalClosureAudit:
  """Recompute every local component gate in the terminal closure."""

  if not isinstance(result, MocEulerTwoSidedTerminalClosureResult):
    return _failure(
      MocEulerTwoSidedTerminalClosureAuditStatus.INVALID_INPUT,
      'result must be a MocEulerTwoSidedTerminalClosureResult',
    )
  ####
  request = result.request
  request_verified = bool(
    request is not None
    and result.field_iteration is request.field_iteration
  )
  if not request_verified or request is None or result.field_iteration is None:
    return _failure(
      MocEulerTwoSidedTerminalClosureAuditStatus.REQUEST_FAILURE,
      'terminal closure did not retain the exact field-iteration request lineage',
      result_status=result.status.value,
      request_verified=request_verified,
    )
  ####
  iteration_audit = measure_moc_euler_two_sided_field_iteration(
    result.field_iteration
  )
  field_iteration_verified = bool(iteration_audit.local_consistency_verified)
  if not field_iteration_verified:
    return _failure(
      MocEulerTwoSidedTerminalClosureAuditStatus.FIELD_ITERATION_FAILURE,
      'independent two-sided field-iteration audit did not pass',
      result_status=result.status.value,
      request_verified=True,
    )
  ####
  if result.terminal_wedge is None:
    return _failure(
      MocEulerTwoSidedTerminalClosureAuditStatus.TERMINAL_WEDGE_FAILURE,
      'terminal closure did not retain a terminal-wedge result',
      result_status=result.status.value,
      request_verified=True,
      field_iteration_verified=True,
    )
  ####
  terminal_audit = measure_moc_euler_ambient_first_wedge_terminal_characteristic_audit(
    result.terminal_wedge
  )
  terminal_geometry_verified = bool(
    terminal_audit.local_consistency_verified
  )
  if not terminal_geometry_verified:
    return _failure(
      MocEulerTwoSidedTerminalClosureAuditStatus.TERMINAL_WEDGE_FAILURE,
      'independent terminal-wedge audit did not pass',
      result_status=result.status.value,
      request_verified=True,
      field_iteration_verified=True,
    )
  ####
  if result.entropy_carry is None:
    return _failure(
      MocEulerTwoSidedTerminalClosureAuditStatus.ENTROPY_CARRY_FAILURE,
      'terminal closure did not retain an entropy-carry result',
      result_status=result.status.value,
      request_verified=True,
      field_iteration_verified=True,
      terminal_geometry_verified=True,
    )
  ####
  carry_audit = measure_moc_euler_ambient_first_wedge_entropy_carry(
    result.entropy_carry
  )
  entropy_carry_verified = bool(carry_audit.local_consistency_verified)
  if not entropy_carry_verified:
    return _failure(
      MocEulerTwoSidedTerminalClosureAuditStatus.ENTROPY_CARRY_FAILURE,
      'independent entropy-carry audit did not pass',
      result_status=result.status.value,
      request_verified=True,
      field_iteration_verified=True,
      terminal_geometry_verified=True,
    )
  ####
  if result.internal_field is None:
    return _failure(
      MocEulerTwoSidedTerminalClosureAuditStatus.INTERNAL_FIELD_FAILURE,
      'terminal closure did not retain an internal characteristic field',
      result_status=result.status.value,
      request_verified=True,
      field_iteration_verified=True,
      terminal_geometry_verified=True,
      entropy_carry_verified=True,
    )
  ####
  internal_audit = measure_moc_euler_ambient_first_wedge_entropy_characteristic_field(
    result.internal_field
  )
  internal_verified = bool(internal_audit.local_consistency_verified)
  if not internal_verified:
    return _failure(
      MocEulerTwoSidedTerminalClosureAuditStatus.INTERNAL_FIELD_FAILURE,
      'independent internal entropy-characteristic field audit did not pass',
      result_status=result.status.value,
      request_verified=True,
      field_iteration_verified=True,
      terminal_geometry_verified=True,
      entropy_carry_verified=True,
    )
  ####
  component_audits_verified = bool(
    result.terminal_geometry_verified == terminal_geometry_verified
    and result.entropy_carry_verified == entropy_carry_verified
    and result.internal_characteristic_field_verified == internal_verified
  )
  flags_verified = bool(
    result.status is MocEulerTwoSidedTerminalClosureStatus.CONVERGED_INTERNAL_FIELD
    and result.physical_closure_verified is False
    and result.chain_promotion_blocked
    and result.production_claim_allowed is False
  )
  if not component_audits_verified or not flags_verified:
    return _failure(
      MocEulerTwoSidedTerminalClosureAuditStatus.FLAG_FAILURE,
      'terminal closure producer flags did not match independent component evidence',
      result_status=result.status.value,
      request_verified=True,
      field_iteration_verified=True,
      terminal_geometry_verified=terminal_geometry_verified,
      entropy_carry_verified=entropy_carry_verified,
      internal_characteristic_field_verified=internal_verified,
      component_audits_verified=component_audits_verified,
      physical_closure_verified=result.physical_closure_verified,
      chain_promotion_blocked=result.chain_promotion_blocked,
      production_claim_allowed=result.production_claim_allowed,
    )
  ####
  return _failure(
    MocEulerTwoSidedTerminalClosureAuditStatus.CONVERGED_LOCAL_AUDIT,
    'independent terminal-closure audit passed field-iteration, characteristic-wedge, entropy-carry, and internal-field gates; global physical closure remains pending',
    result_status=result.status.value,
    request_verified=True,
    field_iteration_verified=True,
    terminal_geometry_verified=True,
    entropy_carry_verified=True,
    internal_characteristic_field_verified=True,
    component_audits_verified=True,
    physical_closure_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
  )
####
