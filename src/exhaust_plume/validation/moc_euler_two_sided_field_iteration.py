"""Independent audit for the two-sided exact-Euler field iteration.

The solver-side iteration retains a useful research field even when its
entropy/total-pressure lineage is not yet admissible for a continued chain.
This audit replays the retained handoff sequence, independently audits each
physical field, validates each open terminal trace, and checks the fixed-point
flags.  It deliberately keeps the research fixed point separate from
canonical free-boundary closure and production promotion.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import hypot, isfinite
from typing import Any

from exhaust_plume.models.moc.chain import MocChainBoundarySample
from exhaust_plume.models.moc.euler_two_sided_field_iteration import (
  MocEulerTwoSidedFieldIterationResult,
  MocEulerTwoSidedFieldIterationStatus,
)
from exhaust_plume.validation.moc_euler import (
  measure_moc_euler_ambient_physical_field,
  measure_moc_euler_companion_field,
)
from exhaust_plume.validation.moc_euler_variable_entropy_lineage import (
  measure_moc_euler_variable_entropy_lineage,
)

__all__ = (
  'MOC_EULER_TWO_SIDED_FIELD_ITERATION_AUDIT_OPERATOR_ID',
  'MocEulerTwoSidedFieldIterationAuditStatus',
  'MocEulerTwoSidedFieldIterationAudit',
  'measure_moc_euler_two_sided_field_iteration',
)


MOC_EULER_TWO_SIDED_FIELD_ITERATION_AUDIT_OPERATOR_ID = (
  'op.moc.euler-two-sided-field-iteration-audit'
)


class MocEulerTwoSidedFieldIterationAuditStatus(str, Enum):
  """Typed outcomes for the independent two-sided iteration audit."""

  CONVERGED_LOCAL_AUDIT = 'converged_two_sided_field_iteration_audit'
  INVALID_INPUT = 'invalid_input'
  REQUEST_FAILURE = 'two_sided_iteration_audit_request_failure'
  COMPANION_FIELD_FAILURE = 'two_sided_iteration_audit_companion_field_failure'
  RECORD_FAILURE = 'two_sided_iteration_audit_record_failure'
  PHYSICAL_FIELD_FAILURE = 'two_sided_iteration_audit_physical_field_failure'
  SOURCE_STRIP_FAILURE = 'two_sided_iteration_audit_source_strip_failure'
  RESIDUAL_FAILURE = 'two_sided_iteration_audit_residual_failure'
  ENTROPY_LINEAGE_FAILURE = 'two_sided_iteration_audit_entropy_lineage_failure'
  FLAG_FAILURE = 'two_sided_iteration_audit_flag_failure'
  ITERATION_LIMIT = 'two_sided_iteration_audit_iteration_limit'
####


@dataclass(frozen=True, slots=True)
class MocEulerTwoSidedFieldIterationAudit:
  """Independent evidence for one bounded two-sided field iteration."""

  status: MocEulerTwoSidedFieldIterationAuditStatus
  result_status: str | None
  iteration_count: int
  request_verified: bool
  companion_field_verified: bool
  record_lineage_verified: bool
  physical_field_local_gates_verified: bool
  source_strip_verified: bool
  handoff_residuals_verified: bool
  fixed_point_verified: bool
  field_iteration_verified: bool
  entropy_lineage_verified: bool
  canonical_free_boundary_verified: bool
  canonical_euler_verified: bool
  chain_promotion_blocked: bool
  production_claim_allowed: bool
  maximum_coordinate_residual_m: float | None = None
  maximum_state_residual: float | None = None
  maximum_pressure_residual_Pa: float | None = None
  message: str = ''
  operator_id: str = MOC_EULER_TWO_SIDED_FIELD_ITERATION_AUDIT_OPERATOR_ID

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocEulerTwoSidedFieldIterationAuditStatus):
      raise TypeError(
        'status must be a MocEulerTwoSidedFieldIterationAuditStatus'
      )
    ####
    if self.result_status is not None:
      object.__setattr__(self, 'result_status', str(self.result_status))
    ####
    if (
      isinstance(self.iteration_count, bool)
      or not isinstance(self.iteration_count, int)
      or self.iteration_count < 0
    ):
      raise ValueError('iteration_count must be a nonnegative integer')
    ####
    for name in (
      'request_verified',
      'companion_field_verified',
      'record_lineage_verified',
      'physical_field_local_gates_verified',
      'source_strip_verified',
      'handoff_residuals_verified',
      'fixed_point_verified',
      'field_iteration_verified',
      'entropy_lineage_verified',
      'canonical_free_boundary_verified',
      'canonical_euler_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    for name in (
      'maximum_coordinate_residual_m',
      'maximum_state_residual',
      'maximum_pressure_residual_Pa',
    ):
      value = getattr(self, name)
      if value is None:
        continue
      ####
      numeric = float(value)
      if not isfinite(numeric) or numeric < 0.0:
        raise ValueError(f'{name} must be finite and nonnegative when supplied')
      ####
      object.__setattr__(self, name, numeric)
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
    return self.status is MocEulerTwoSidedFieldIterationAuditStatus.CONVERGED_LOCAL_AUDIT
  ####

  @property
  def local_consistency_verified(self) -> bool:
    """Whether the research iteration passed its local source-lineage gates.

    The variable-entropy audit is required for local consistency, but local
    consistency still does not imply canonical free-boundary closure or
    production promotion.
    """

    return bool(
      self.converged
      and self.request_verified
      and self.companion_field_verified
      and self.record_lineage_verified
      and self.physical_field_local_gates_verified
      and self.source_strip_verified
      and self.handoff_residuals_verified
      and self.fixed_point_verified
      and self.field_iteration_verified
      and self.entropy_lineage_verified
      and not self.canonical_free_boundary_verified
      and not self.canonical_euler_verified
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
      'iteration_count': self.iteration_count,
      'request_verified': self.request_verified,
      'companion_field_verified': self.companion_field_verified,
      'record_lineage_verified': self.record_lineage_verified,
      'physical_field_local_gates_verified': self.physical_field_local_gates_verified,
      'source_strip_verified': self.source_strip_verified,
      'handoff_residuals_verified': self.handoff_residuals_verified,
      'fixed_point_verified': self.fixed_point_verified,
      'field_iteration_verified': self.field_iteration_verified,
      'entropy_lineage_verified': self.entropy_lineage_verified,
      'canonical_free_boundary_verified': self.canonical_free_boundary_verified,
      'canonical_euler_verified': self.canonical_euler_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'maximum_coordinate_residual_m': self.maximum_coordinate_residual_m,
      'maximum_state_residual': self.maximum_state_residual,
      'maximum_pressure_residual_Pa': self.maximum_pressure_residual_Pa,
      'message': self.message,
    }
  ####
####


def _residuals(
  incoming: tuple[MocChainBoundarySample, ...],
  outgoing: tuple[MocChainBoundarySample, ...],
) -> tuple[float | None, float | None, float | None]:
  pair_count = min(len(incoming), len(outgoing))
  if pair_count == 0:
    return None, None, None
  ####
  maximum_coordinate = max(
    (
      hypot(
        outgoing[index].state.x_m - incoming[index].state.x_m,
        outgoing[index].state.y_m - incoming[index].state.y_m,
      )
      for index in range(pair_count)
    ),
    default=None,
  )
  maximum_state = max(
    (
      max(
        abs(outgoing[index].state.theta_rad - incoming[index].state.theta_rad),
        abs(outgoing[index].state.mach - incoming[index].state.mach),
        abs(outgoing[index].state.gamma - incoming[index].state.gamma),
      )
      for index in range(pair_count)
    ),
    default=None,
  )
  maximum_pressure = max(
    (
      abs(
        outgoing[index].total_pressure_Pa
        - incoming[index].total_pressure_Pa
      )
      for index in range(pair_count)
    ),
    default=None,
  )
  return maximum_coordinate, maximum_state, maximum_pressure
####


def _close(actual: float | None, expected: float | None) -> bool:
  if actual is None or expected is None:
    return actual is None and expected is None
  ####
  scale = max(1.0, abs(float(actual)), abs(float(expected)))
  return abs(float(actual) - float(expected)) <= 1.0e-9 * scale
####


def _fixed_point(
  incoming: tuple[MocChainBoundarySample, ...],
  outgoing: tuple[MocChainBoundarySample, ...],
  request: Any,
) -> bool:
  if len(incoming) != len(outgoing) or not outgoing:
    return False
  ####
  coordinate, state, pressure = _residuals(incoming, outgoing)
  return bool(
    coordinate is not None
    and state is not None
    and pressure is not None
    and coordinate <= request.handoff_position_tolerance_m
    and state <= request.handoff_state_tolerance
    and pressure <= request.handoff_pressure_tolerance_Pa
  )
####


def _failure(
  status: MocEulerTwoSidedFieldIterationAuditStatus,
  message: str,
  *,
  result_status: str | None = None,
  iteration_count: int = 0,
  request_verified: bool = False,
  companion_field_verified: bool = False,
  record_lineage_verified: bool = False,
  physical_field_local_gates_verified: bool = False,
  source_strip_verified: bool = False,
  handoff_residuals_verified: bool = False,
  fixed_point_verified: bool = False,
  field_iteration_verified: bool = False,
  entropy_lineage_verified: bool = False,
  canonical_free_boundary_verified: bool = False,
  canonical_euler_verified: bool = False,
  chain_promotion_blocked: bool = True,
  production_claim_allowed: bool = False,
  maximum_coordinate_residual_m: float | None = None,
  maximum_state_residual: float | None = None,
  maximum_pressure_residual_Pa: float | None = None,
) -> MocEulerTwoSidedFieldIterationAudit:
  return MocEulerTwoSidedFieldIterationAudit(
    status=status,
    result_status=result_status,
    iteration_count=iteration_count,
    request_verified=request_verified,
    companion_field_verified=companion_field_verified,
    record_lineage_verified=record_lineage_verified,
    physical_field_local_gates_verified=physical_field_local_gates_verified,
    source_strip_verified=source_strip_verified,
    handoff_residuals_verified=handoff_residuals_verified,
    fixed_point_verified=fixed_point_verified,
    field_iteration_verified=field_iteration_verified,
    entropy_lineage_verified=entropy_lineage_verified,
    canonical_free_boundary_verified=canonical_free_boundary_verified,
    canonical_euler_verified=canonical_euler_verified,
    chain_promotion_blocked=chain_promotion_blocked,
    production_claim_allowed=production_claim_allowed,
    maximum_coordinate_residual_m=maximum_coordinate_residual_m,
    maximum_state_residual=maximum_state_residual,
    maximum_pressure_residual_Pa=maximum_pressure_residual_Pa,
    message=message,
  )
####


def measure_moc_euler_two_sided_field_iteration(
  result: MocEulerTwoSidedFieldIterationResult,
) -> MocEulerTwoSidedFieldIterationAudit:
  """Recompute two-sided iteration lineage and local fixed-point evidence."""

  if not isinstance(result, MocEulerTwoSidedFieldIterationResult):
    return _failure(
      MocEulerTwoSidedFieldIterationAuditStatus.INVALID_INPUT,
      'result must be a MocEulerTwoSidedFieldIterationResult',
    )
  ####
  request = result.request
  initial_companion = result.initial_companion_field
  request_verified = bool(
    request is not None
    and result.shock_boundary is request.shock_boundary
    and initial_companion is request.companion_field
  )
  if not request_verified or request is None or initial_companion is None:
    return _failure(
      MocEulerTwoSidedFieldIterationAuditStatus.REQUEST_FAILURE,
      'result did not retain the exact two-sided iteration request lineage',
      result_status=result.status.value,
      request_verified=request_verified,
    )
  ####
  try:
    companion_audit = measure_moc_euler_companion_field(initial_companion)
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocEulerTwoSidedFieldIterationAuditStatus.COMPANION_FIELD_FAILURE,
      f'independent companion-field audit raised: {error}',
      result_status=result.status.value,
      request_verified=True,
    )
  ####
  companion_field_verified = bool(
    companion_audit.local_euler_consistency_verified
    and initial_companion.shock_boundary is request.shock_boundary
    and not initial_companion.physical_closure_verified
    and initial_companion.chain_promotion_blocked
    and not initial_companion.production_claim_allowed
  )
  if not companion_field_verified:
    return _failure(
      MocEulerTwoSidedFieldIterationAuditStatus.COMPANION_FIELD_FAILURE,
      'independent open companion-field audit did not verify the required '
      'two-sided research handoff',
      result_status=result.status.value,
      request_verified=True,
      companion_field_verified=False,
    )
  ####
  records = tuple(result.records)
  if not records:
    return _failure(
      MocEulerTwoSidedFieldIterationAuditStatus.RECORD_FAILURE,
      'two-sided iteration retained no audit records',
      result_status=result.status.value,
      iteration_count=0,
      request_verified=True,
      companion_field_verified=True,
    )
  ####
  incoming = initial_companion.downstream_handoff
  record_lineage_verified = True
  physical_field_local_gates_verified = True
  source_strip_verified = True
  handoff_residuals_verified = True
  entropy_lineage_verified = True
  fixed_point_seen = False
  maximum_coordinate_residual: float | None = None
  maximum_state_residual: float | None = None
  maximum_pressure_residual: float | None = None
  for expected_index, record in enumerate(records):
    if (
      record.iteration_index != expected_index
      or record.incoming_handoff_sample_count != len(incoming)
    ):
      record_lineage_verified = False
      break
    ####
    physical = record.physical_field
    source_strip = record.source_strip
    if physical is None:
      physical_field_local_gates_verified = False
      break
    ####
    try:
      physical_audit = measure_moc_euler_ambient_physical_field(physical)
    except (ArithmeticError, FloatingPointError, TypeError, ValueError):
      physical_field_local_gates_verified = False
      break
    ####
    field_local = bool(
      physical_audit.shock_jump_verified
      and physical_audit.cell_euler_residuals_verified
      and physical_audit.physical_field_verified
      and physical_audit.physical_closure_verified
      and physical_audit.chain_promotion_blocked
      and not physical_audit.production_claim_allowed
    )
    physical_field_local_gates_verified = (
      physical_field_local_gates_verified and field_local
    )
    if not field_local:
      break
    ####
    try:
      entropy_audit = measure_moc_euler_variable_entropy_lineage(physical)
    except (ArithmeticError, FloatingPointError, TypeError, ValueError):
      entropy_lineage_verified = False
      break
    ####
    entropy_lineage_verified = (
      entropy_lineage_verified
      and entropy_audit.variable_entropy_lineage_verified
    )
    if not entropy_lineage_verified:
      break
    ####
    if source_strip is None:
      source_strip_verified = False
      break
    ####
    outgoing = source_strip.terminal_trace_samples
    trace_verified = bool(
      source_strip.converged
      and source_strip.chain_promotion_blocked
      and not source_strip.physical_closure_verified
      and source_strip.terminal_trace_validation.converged
      and len(outgoing) == record.outgoing_handoff_sample_count
    )
    source_strip_verified = source_strip_verified and trace_verified
    if not trace_verified:
      break
    ####
    coordinate_residual, state_residual, pressure_residual = _residuals(
      incoming,
      outgoing,
    )
    maximum_coordinate_residual = max(
      value
      for value in (maximum_coordinate_residual, coordinate_residual)
      if value is not None
    ) if maximum_coordinate_residual is not None or coordinate_residual is not None else None
    maximum_state_residual = max(
      value
      for value in (maximum_state_residual, state_residual)
      if value is not None
    ) if maximum_state_residual is not None or state_residual is not None else None
    maximum_pressure_residual = max(
      value
      for value in (maximum_pressure_residual, pressure_residual)
      if value is not None
    ) if maximum_pressure_residual is not None or pressure_residual is not None else None
    residuals_match = bool(
      _close(record.maximum_coordinate_residual_m, coordinate_residual)
      and _close(record.maximum_state_residual, state_residual)
      and _close(record.maximum_pressure_residual_Pa, pressure_residual)
    )
    fixed_point_expected = _fixed_point(incoming, outgoing, request)
    residuals_match = residuals_match and (
      record.fixed_point_converged == fixed_point_expected
    )
    handoff_residuals_verified = handoff_residuals_verified and residuals_match
    if not residuals_match:
      break
    ####
    if fixed_point_expected:
      fixed_point_seen = True
      if expected_index != len(records) - 1:
        record_lineage_verified = False
        break
    ####
    incoming = outgoing
  ####
  if records:
    record_lineage_verified = bool(
      record_lineage_verified
      and result.final_physical_field is records[-1].physical_field
      and result.final_source_strip is records[-1].source_strip
    )
  ####
  fixed_point_verified = bool(
    fixed_point_seen
    and result.fixed_point_converged
    and result.final_source_strip is not None
  )
  expected_field_iteration_verified = bool(
    fixed_point_verified
    and request_verified
    and companion_field_verified
    and record_lineage_verified
    and physical_field_local_gates_verified
    and source_strip_verified
    and handoff_residuals_verified
    and result.status is MocEulerTwoSidedFieldIterationStatus.CONVERGED_FIXED_POINT
  )
  flags_verified = bool(
    result.field_iteration_verified == expected_field_iteration_verified
    and not result.canonical_free_boundary_verified
    and not result.canonical_euler_verified
    and result.chain_promotion_blocked
    and not result.production_claim_allowed
  )
  if not handoff_residuals_verified:
    status = MocEulerTwoSidedFieldIterationAuditStatus.RESIDUAL_FAILURE
    message = 'retained two-sided handoff residuals or fixed-point flags did not remeasure independently'
  elif not record_lineage_verified:
    status = MocEulerTwoSidedFieldIterationAuditStatus.RECORD_FAILURE
    message = 'retained two-sided iteration records did not preserve exact sequential lineage'
  elif not physical_field_local_gates_verified:
    status = MocEulerTwoSidedFieldIterationAuditStatus.PHYSICAL_FIELD_FAILURE
    message = 'one or more retained physical fields failed independent local gates'
  elif not entropy_lineage_verified:
    status = MocEulerTwoSidedFieldIterationAuditStatus.ENTROPY_LINEAGE_FAILURE
    message = (
      'one or more retained physical fields failed the independent variable-'
      'entropy source-lineage audit'
    )
  elif not source_strip_verified:
    status = MocEulerTwoSidedFieldIterationAuditStatus.SOURCE_STRIP_FAILURE
    message = 'one or more retained open terminal traces failed independent validation'
  elif not flags_verified:
    status = MocEulerTwoSidedFieldIterationAuditStatus.FLAG_FAILURE
    message = 'two-sided iteration promotion or canonical-closure flags were weakened'
  elif not fixed_point_seen:
    status = MocEulerTwoSidedFieldIterationAuditStatus.ITERATION_LIMIT
    message = 'two-sided iteration records are locally auditable but did not reach a fixed point'
  else:
    status = MocEulerTwoSidedFieldIterationAuditStatus.CONVERGED_LOCAL_AUDIT
    message = (
      'independent two-sided field-iteration audit passed companion-field, '
      'physical-field, variable-entropy lineage, terminal-trace, residual, '
      'and fixed-point gates; canonical production closure remains pending'
    )
  ####
  return _failure(
    status,
    message,
    result_status=result.status.value,
    iteration_count=len(records),
    request_verified=request_verified,
    companion_field_verified=companion_field_verified,
    record_lineage_verified=record_lineage_verified,
    physical_field_local_gates_verified=physical_field_local_gates_verified,
    source_strip_verified=source_strip_verified,
    handoff_residuals_verified=handoff_residuals_verified,
    fixed_point_verified=fixed_point_verified,
    field_iteration_verified=expected_field_iteration_verified,
    entropy_lineage_verified=entropy_lineage_verified,
    canonical_free_boundary_verified=result.canonical_free_boundary_verified,
    canonical_euler_verified=result.canonical_euler_verified,
    chain_promotion_blocked=result.chain_promotion_blocked,
    production_claim_allowed=result.production_claim_allowed,
    maximum_coordinate_residual_m=maximum_coordinate_residual,
    maximum_state_residual=maximum_state_residual,
    maximum_pressure_residual_Pa=maximum_pressure_residual,
  )
####
