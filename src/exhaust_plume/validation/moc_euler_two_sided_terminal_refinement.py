"""Independent audit for the two-sided terminal continuation ladder."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Sequence

from exhaust_plume.models.moc.euler_two_sided_terminal_refinement import (
  MocEulerTwoSidedTerminalRefinementResult,
  MocEulerTwoSidedTerminalRefinementStatus,
)
from exhaust_plume.validation.moc_euler_entropy_characteristic_continuation import (
  MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationAudit,
  measure_moc_euler_ambient_first_wedge_entropy_characteristic_continuation,
)
from exhaust_plume.validation.moc_euler_two_sided_terminal_closure import (
  measure_moc_euler_two_sided_terminal_closure,
)

__all__ = (
  'MOC_EULER_TWO_SIDED_TERMINAL_REFINEMENT_AUDIT_OPERATOR_ID',
  'MocEulerTwoSidedTerminalRefinementAuditStatus',
  'MocEulerTwoSidedTerminalRefinementAudit',
  'measure_moc_euler_two_sided_terminal_refinement',
)


MOC_EULER_TWO_SIDED_TERMINAL_REFINEMENT_AUDIT_OPERATOR_ID = (
  'op.moc.euler-two-sided-terminal-refinement-audit'
)


class MocEulerTwoSidedTerminalRefinementAuditStatus(str, Enum):
  """Typed outcomes for the independent ladder audit."""

  CONVERGED_LOCAL_AUDIT = 'converged_two_sided_terminal_refinement_audit'
  INVALID_INPUT = 'invalid_input'
  REQUEST_FAILURE = 'two_sided_terminal_refinement_audit_request_failure'
  TERMINAL_CLOSURE_FAILURE = 'two_sided_terminal_refinement_audit_closure_failure'
  CONTINUATION_FAILURE = 'two_sided_terminal_refinement_audit_continuation_failure'
  LEVEL_FAILURE = 'two_sided_terminal_refinement_audit_level_failure'
  RESIDUAL_FAILURE = 'two_sided_terminal_refinement_audit_residual_failure'
  FLAG_FAILURE = 'two_sided_terminal_refinement_audit_flag_failure'


@dataclass(frozen=True, slots=True)
class MocEulerTwoSidedTerminalRefinementAudit:
  """Recomputed ladder evidence and its separate refinement claim gate."""

  status: MocEulerTwoSidedTerminalRefinementAuditStatus
  result_status: str | None
  request_verified: bool
  terminal_closure_verified: bool
  continuation_audits: tuple[
    MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationAudit, ...
  ]
  continuation_audits_verified: bool
  cycle_order_verified: bool
  cell_counts: tuple[int, ...]
  maximum_cell_euler_residuals: tuple[float, ...]
  cell_growth_verified: bool
  residuals_finite: bool
  residuals_verified: bool
  residual_nonincreasing_verified: bool
  residual_reduction_verified: bool
  refinement_convergence_verified: bool
  physical_closure_verified: bool
  chain_promotion_blocked: bool
  production_claim_allowed: bool
  fidelity_flags_verified: bool
  message: str = ''
  operator_id: str = MOC_EULER_TWO_SIDED_TERMINAL_REFINEMENT_AUDIT_OPERATOR_ID

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocEulerTwoSidedTerminalRefinementAuditStatus):
      raise TypeError('status must be a terminal refinement audit status')
    ####
    if self.result_status is not None:
      object.__setattr__(self, 'result_status', str(self.result_status))
    ####
    audits = tuple(self.continuation_audits)
    if any(
      not isinstance(
        audit,
        MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationAudit,
      )
      for audit in audits
    ):
      raise TypeError('continuation_audits must contain typed audits')
    ####
    cells = tuple(self.cell_counts)
    residuals = tuple(float(value) for value in self.maximum_cell_euler_residuals)
    if len(cells) != len(residuals) or len(cells) != len(audits):
      raise ValueError('ladder audit summaries must have equal lengths')
    ####
    if any(
      isinstance(value, bool) or not isinstance(value, int) or value < 0
      for value in cells
    ):
      raise ValueError('cell_counts must contain nonnegative integers')
    ####
    if any(not isfinite(value) or value < 0.0 for value in residuals):
      raise ValueError('maximum residuals must be finite and nonnegative')
    ####
    object.__setattr__(self, 'continuation_audits', audits)
    object.__setattr__(self, 'cell_counts', cells)
    object.__setattr__(self, 'maximum_cell_euler_residuals', residuals)
    for name in (
      'request_verified',
      'terminal_closure_verified',
      'continuation_audits_verified',
      'cycle_order_verified',
      'cell_growth_verified',
      'residuals_finite',
      'residuals_verified',
      'residual_nonincreasing_verified',
      'residual_reduction_verified',
      'refinement_convergence_verified',
      'physical_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
      'fidelity_flags_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    ####
    if self.physical_closure_verified:
      raise ValueError('terminal refinement audit cannot claim physical closure')
    ####
    if not self.chain_promotion_blocked:
      raise ValueError('terminal refinement audit must retain promotion blocked')
    ####
    if self.production_claim_allowed:
      raise ValueError('terminal refinement audit cannot claim production validity')
    ####
    object.__setattr__(self, 'operator_id', str(self.operator_id))
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status is MocEulerTwoSidedTerminalRefinementAuditStatus.CONVERGED_LOCAL_AUDIT
  ####

  @property
  def local_consistency_verified(self) -> bool:
    return bool(
      self.converged
      and self.request_verified
      and self.terminal_closure_verified
      and self.continuation_audits_verified
      and self.cycle_order_verified
      and self.cell_growth_verified
      and self.residuals_finite
      and self.residuals_verified
      and self.residual_nonincreasing_verified
      and self.fidelity_flags_verified
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
      'terminal_closure_verified': self.terminal_closure_verified,
      'continuation_audits_verified': self.continuation_audits_verified,
      'cycle_order_verified': self.cycle_order_verified,
      'cell_counts': list(self.cell_counts),
      'maximum_cell_euler_residuals': list(self.maximum_cell_euler_residuals),
      'cell_growth_verified': self.cell_growth_verified,
      'residuals_finite': self.residuals_finite,
      'residuals_verified': self.residuals_verified,
      'residual_nonincreasing_verified': self.residual_nonincreasing_verified,
      'residual_reduction_verified': self.residual_reduction_verified,
      'refinement_convergence_verified': self.refinement_convergence_verified,
      'physical_closure_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'fidelity_flags_verified': self.fidelity_flags_verified,
      'continuation_audits': [audit.as_report() for audit in self.continuation_audits],
      'message': self.message,
    }
  ####
####


def _failure(
  status: MocEulerTwoSidedTerminalRefinementAuditStatus,
  message: str,
  *,
  result_status: str | None = None,
  request_verified: bool = False,
  terminal_closure_verified: bool = False,
  continuation_audits: Sequence[
    MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationAudit
  ] = (),
  continuation_audits_verified: bool = False,
  cycle_order_verified: bool = False,
  cell_counts: Sequence[int] = (),
  residuals: Sequence[float] = (),
  cell_growth_verified: bool = False,
  residuals_finite: bool = False,
  residuals_verified: bool = False,
  residual_nonincreasing_verified: bool = False,
  residual_reduction_verified: bool = False,
  refinement_convergence_verified: bool = False,
  physical_closure_verified: bool = False,
  chain_promotion_blocked: bool = True,
  production_claim_allowed: bool = False,
  fidelity_flags_verified: bool = False,
) -> MocEulerTwoSidedTerminalRefinementAudit:
  return MocEulerTwoSidedTerminalRefinementAudit(
    status=status,
    result_status=result_status,
    request_verified=request_verified,
    terminal_closure_verified=terminal_closure_verified,
    continuation_audits=tuple(continuation_audits),
    continuation_audits_verified=continuation_audits_verified,
    cycle_order_verified=cycle_order_verified,
    cell_counts=tuple(cell_counts),
    maximum_cell_euler_residuals=tuple(residuals),
    cell_growth_verified=cell_growth_verified,
    residuals_finite=residuals_finite,
    residuals_verified=residuals_verified,
    residual_nonincreasing_verified=residual_nonincreasing_verified,
    residual_reduction_verified=residual_reduction_verified,
    refinement_convergence_verified=refinement_convergence_verified,
    physical_closure_verified=physical_closure_verified,
    chain_promotion_blocked=chain_promotion_blocked,
    production_claim_allowed=production_claim_allowed,
    fidelity_flags_verified=fidelity_flags_verified,
    message=message,
  )
####


def measure_moc_euler_two_sided_terminal_refinement(
  result: MocEulerTwoSidedTerminalRefinementResult,
) -> MocEulerTwoSidedTerminalRefinementAudit:
  """Recompute terminal closure, continuation, topology, and trends."""

  if not isinstance(result, MocEulerTwoSidedTerminalRefinementResult):
    return _failure(
      MocEulerTwoSidedTerminalRefinementAuditStatus.INVALID_INPUT,
      'result must be a MocEulerTwoSidedTerminalRefinementResult',
    )
  ####
  request = result.request
  request_verified = bool(
    request is not None
    and result.terminal_closure is request.terminal_closure
  )
  if not request_verified or request is None or result.terminal_closure is None:
    return _failure(
      MocEulerTwoSidedTerminalRefinementAuditStatus.REQUEST_FAILURE,
      'terminal refinement did not retain exact request and closure lineage',
      result_status=result.status.value,
      request_verified=request_verified,
    )
  ####
  closure_audit = measure_moc_euler_two_sided_terminal_closure(
    result.terminal_closure
  )
  terminal_verified = bool(closure_audit.local_consistency_verified)
  if not terminal_verified:
    return _failure(
      MocEulerTwoSidedTerminalRefinementAuditStatus.TERMINAL_CLOSURE_FAILURE,
      'independent terminal-closure audit did not pass',
      result_status=result.status.value,
      request_verified=True,
    )
  ####
  if tuple(result.cycle_counts) != tuple(request.cycle_counts):
    return _failure(
      MocEulerTwoSidedTerminalRefinementAuditStatus.LEVEL_FAILURE,
      'result cycle counts do not match the declared refinement request',
      result_status=result.status.value,
      request_verified=True,
      terminal_closure_verified=True,
    )
  ####
  continuation_audits: list[
    MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationAudit
  ] = []
  for cycle_count, continuation in zip(
    request.cycle_counts,
    result.continuations,
    strict=True,
  ):
    if continuation.cycle_count != cycle_count:
      return _failure(
        MocEulerTwoSidedTerminalRefinementAuditStatus.LEVEL_FAILURE,
        'continuation cycle count does not match its declared ladder level',
        result_status=result.status.value,
        request_verified=True,
        terminal_closure_verified=True,
        continuation_audits=continuation_audits,
      )
    ####
    try:
      audit = measure_moc_euler_ambient_first_wedge_entropy_characteristic_continuation(
        continuation,
        characteristic_residual_tolerance=request.characteristic_residual_tolerance,
        pressure_lineage_tolerance=request.pressure_lineage_tolerance,
        cell_residual_tolerance=request.cell_residual_tolerance,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      return _failure(
        MocEulerTwoSidedTerminalRefinementAuditStatus.CONTINUATION_FAILURE,
        f'independent continuation audit raised: {error}',
        result_status=result.status.value,
        request_verified=True,
        terminal_closure_verified=True,
        continuation_audits=continuation_audits,
      )
    ####
    continuation_audits.append(audit)
  ####
  continuation_verified = bool(
    len(continuation_audits) == len(request.cycle_counts)
    and all(audit.local_consistency_verified for audit in continuation_audits)
  )
  cell_counts = tuple(len(continuation.cells) for continuation in result.continuations)
  residuals = tuple(
    continuation.maximum_cell_euler_residual or 0.0
    for continuation in result.continuations
  )
  cycle_order = bool(
    all(right > left for left, right in zip(request.cycle_counts, request.cycle_counts[1:]))
  )
  cell_growth = bool(
    all(right > left for left, right in zip(cell_counts, cell_counts[1:]))
  )
  residuals_finite = bool(
    residuals and all(isfinite(value) and value >= 0.0 for value in residuals)
  )
  residuals_verified = bool(
    residuals_finite
    and all(
      audit.cell_euler_residuals_verified
      and value <= request.cell_residual_tolerance
      for audit, value in zip(continuation_audits, residuals, strict=True)
    )
  )
  residual_nonincreasing = bool(
    all(
      right <= left + request.refinement_tolerance * max(1.0, abs(left))
      for left, right in zip(residuals, residuals[1:])
    )
  )
  residual_reduction = bool(len(residuals) >= 2 and residuals[-1] < residuals[0])
  refinement_convergence = bool(
    continuation_verified
    and cycle_order
    and cell_growth
    and residuals_finite
    and residuals_verified
    and residual_nonincreasing
    and residual_reduction
  )
  flags_verified = bool(
    result.status is MocEulerTwoSidedTerminalRefinementStatus.CONVERGED_LOCAL_LADDER
    and not result.physical_closure_verified
    and result.chain_promotion_blocked
    and not result.production_claim_allowed
    and result.structural_ladder_verified == continuation_verified
    and result.cell_growth_verified == cell_growth
    and result.residuals_finite == residuals_finite
    and result.residuals_verified == residuals_verified
    and result.residual_nonincreasing_verified == residual_nonincreasing
    and result.residual_reduction_verified == residual_reduction
    and result.refinement_convergence_verified == refinement_convergence
  )
  if not continuation_verified:
    status = MocEulerTwoSidedTerminalRefinementAuditStatus.CONTINUATION_FAILURE
    message = 'one or more terminal continuation levels failed independent gates'
  elif not cycle_order or not cell_growth:
    status = MocEulerTwoSidedTerminalRefinementAuditStatus.LEVEL_FAILURE
    message = 'terminal continuation levels did not show declared topology growth'
  elif not residuals_finite or not residuals_verified or not residual_nonincreasing:
    status = MocEulerTwoSidedTerminalRefinementAuditStatus.RESIDUAL_FAILURE
    message = 'terminal continuation residual evidence failed the ladder gate'
  elif not flags_verified:
    status = MocEulerTwoSidedTerminalRefinementAuditStatus.FLAG_FAILURE
    message = 'terminal refinement producer flags did not match independent evidence'
  else:
    status = MocEulerTwoSidedTerminalRefinementAuditStatus.CONVERGED_LOCAL_AUDIT
    message = (
      'independent terminal continuation audit passed local topology and '
      'non-increasing residual gates; strict residual reduction remains '
      'required for refinement convergence'
      if not residual_reduction
      else 'independent terminal continuation audit passed local refinement gates; '
      'canonical closure and physical shock-cell promotion remain pending'
    )
  ####
  return _failure(
    status,
    message,
    result_status=result.status.value,
    request_verified=True,
    terminal_closure_verified=True,
    continuation_audits=continuation_audits,
    continuation_audits_verified=continuation_verified,
    cycle_order_verified=cycle_order,
    cell_counts=cell_counts,
    residuals=residuals,
    cell_growth_verified=cell_growth,
    residuals_finite=residuals_finite,
    residuals_verified=residuals_verified,
    residual_nonincreasing_verified=residual_nonincreasing,
    residual_reduction_verified=residual_reduction,
    refinement_convergence_verified=refinement_convergence,
    physical_closure_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    fidelity_flags_verified=flags_verified,
  )
####
