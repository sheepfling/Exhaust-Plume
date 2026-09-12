"""Replay the physical shock frontier at every global-feedback closure.

The terminal feedback consumer proves that one frontier step and one terminal
global/downstream recheck share a source closure. This module closes the next
accounting gap: every fresh next_closure retained by the outer feedback loop
must have its own physical shock-frontier handoff. The result remains
research-only until a solver-owned joint global fixed point is implemented.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from exhaust_plume.models.moc.global_physical_closure import (
  MocReflectedDomainGlobalPhysicalClosureResult,
  moc_reflected_domain_global_physical_closure_fingerprint,
)
from exhaust_plume.validation.moc_global_coupled_boundary_condition_feedback import (
  MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRun,
)
from exhaust_plume.validation.moc_global_mixed_regime_global_fixed_point_consumer import (
  MocReflectedDomainGlobalMixedRegimeGlobalFixedPointConsumerAudit,
  MocReflectedDomainGlobalMixedRegimeGlobalFixedPointConsumerRequest,
  MocReflectedDomainGlobalMixedRegimeGlobalFixedPointConsumerResult,
  audit_reflected_domain_global_mixed_regime_global_fixed_point,
  consume_reflected_domain_global_mixed_regime_global_fixed_point,
)
from exhaust_plume.validation.moc_global_mixed_regime_shock_frontier_refinement import (
  MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementStep,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_JOINT_FIXED_POINT_REFINEMENT_OPERATOR_ID',
  'MocReflectedDomainGlobalMixedRegimeJointFixedPointRefinementStatus',
  'MocReflectedDomainGlobalMixedRegimeJointFixedPointRefinementRequest',
  'MocReflectedDomainGlobalMixedRegimeJointFixedPointRefinementResult',
  'MocReflectedDomainGlobalMixedRegimeJointFixedPointRefinementAuditStatus',
  'MocReflectedDomainGlobalMixedRegimeJointFixedPointRefinementAudit',
  'consume_reflected_domain_global_mixed_regime_joint_fixed_point',
  'audit_reflected_domain_global_mixed_regime_joint_fixed_point',
)


MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_JOINT_FIXED_POINT_REFINEMENT_OPERATOR_ID = (
  'op.moc.reflected-domain.global-mixed-regime-joint-fixed-point-refinement-v1'
)


class MocReflectedDomainGlobalMixedRegimeJointFixedPointRefinementStatus(
  str,
  Enum,
):
  """Typed outcomes of the per-closure joint recheck."""

  COMPLETED_RESEARCH_JOINT_RECHECK_WITH_OPEN_CLOSURE = (
    'completed-research-joint-fixed-point-recheck-with-open-closure'
  )
  INVALID_INPUT = 'invalid_input'
  GLOBAL_FEEDBACK_REQUIRED = 'joint-fixed-point-refinement-feedback-required'
  FRONTIER_STEP_COUNT_FAILURE = (
    'joint-fixed-point-refinement-frontier-step-count-failure'
  )
  SOURCE_LINEAGE_FAILURE = (
    'joint-fixed-point-refinement-source-lineage-failure'
  )
  FRONTIER_STEP_FAILURE = 'joint-fixed-point-refinement-frontier-step-failure'
  TERMINAL_FIXED_POINT_FAILURE = (
    'joint-fixed-point-refinement-terminal-fixed-point-failure'
  )
  FIDELITY_FAILURE = 'joint-fixed-point-refinement-fidelity-failure'
  AUDIT_REQUIRED = 'joint-fixed-point-refinement-audit-required'
####


class MocReflectedDomainGlobalMixedRegimeJointFixedPointRefinementAuditStatus(
  str,
  Enum,
):
  """Typed outcomes of the independent joint recheck replay."""

  VERIFIED_RESEARCH_JOINT_RECHECK = (
    'verified-research-joint-fixed-point-recheck'
  )
  INVALID_INPUT = 'invalid_input'
  REPLAY_FAILURE = 'joint-fixed-point-refinement-audit-replay-failure'
  LINEAGE_FAILURE = 'joint-fixed-point-refinement-audit-lineage-failure'
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeJointFixedPointRefinementRequest:
  """Exact feedback run plus one frontier step per retained closure."""

  global_feedback: MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRun
  shock_frontier_steps: tuple[
    MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementStep,
    ...,
  ]
  require_terminal_global_fixed_point: bool = True
  require_terminal_global_downstream_recheck: bool = True
  source: str = (
    'research-global-mixed-regime-joint-fixed-point-refinement-v1'
  )

  def __post_init__(self) -> None:
    if not isinstance(
      self.global_feedback,
      MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRun,
    ):
      raise TypeError('global_feedback must be a typed feedback run')
    ####
    steps = tuple(self.shock_frontier_steps)
    if any(
      not isinstance(
        step,
        MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementStep,
      )
      for step in steps
    ):
      raise TypeError('shock_frontier_steps must contain typed frontier steps')
    ####
    if not steps:
      raise ValueError('shock_frontier_steps must contain at least one step')
    ####
    for name in (
      'require_terminal_global_fixed_point',
      'require_terminal_global_downstream_recheck',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    source = str(self.source)
    if not source:
      raise ValueError('source must be non-empty')
    ####
    object.__setattr__(self, 'shock_frontier_steps', steps)
    object.__setattr__(self, 'source', source)
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': (
        MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_JOINT_FIXED_POINT_REFINEMENT_OPERATOR_ID
      ),
      'source': self.source,
      'require_terminal_global_fixed_point': (
        self.require_terminal_global_fixed_point
      ),
      'require_terminal_global_downstream_recheck': (
        self.require_terminal_global_downstream_recheck
      ),
      'global_feedback': self.global_feedback.as_report(),
      'shock_frontier_steps': tuple(
        step.as_report() for step in self.shock_frontier_steps
      ),
      'research_only': True,
      'production_claim_allowed': False,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeJointFixedPointRefinementResult:
  """Per-closure frontier recheck with global promotion explicitly closed."""

  status: MocReflectedDomainGlobalMixedRegimeJointFixedPointRefinementStatus
  request: MocReflectedDomainGlobalMixedRegimeJointFixedPointRefinementRequest | None
  source_closure: MocReflectedDomainGlobalPhysicalClosureResult | None = None
  source_closure_fingerprint: str | None = None
  global_feedback_consumed: bool = False
  terminal_global_fixed_point_verified: bool = False
  terminal_global_downstream_recheck_verified: bool = False
  frontier_step_count_verified: bool = False
  frontier_feedback_lineage_verified: bool = False
  frontier_steps_consumed: bool = False
  frontier_steps_locally_verified: bool = False
  global_fixed_point_consumer: (
    MocReflectedDomainGlobalMixedRegimeGlobalFixedPointConsumerResult | None
  ) = None
  global_fixed_point_consumer_audit: (
    MocReflectedDomainGlobalMixedRegimeGlobalFixedPointConsumerAudit | None
  ) = None
  joint_recheck_verified: bool = False
  global_coupling_verified: bool = False
  canonical_free_boundary_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalMixedRegimeJointFixedPointRefinementStatus,
    ):
      raise TypeError('status must be a typed joint fixed-point status')
    ####
    if self.request is not None and not isinstance(
      self.request,
      MocReflectedDomainGlobalMixedRegimeJointFixedPointRefinementRequest,
    ):
      raise TypeError('request must be a typed joint fixed-point request')
    ####
    if self.source_closure is not None and not isinstance(
      self.source_closure,
      MocReflectedDomainGlobalPhysicalClosureResult,
    ):
      raise TypeError('source_closure must be a typed physical closure or None')
    ####
    if self.global_fixed_point_consumer is not None and not isinstance(
      self.global_fixed_point_consumer,
      MocReflectedDomainGlobalMixedRegimeGlobalFixedPointConsumerResult,
    ):
      raise TypeError('global_fixed_point_consumer must be a typed result')
    ####
    if self.global_fixed_point_consumer_audit is not None and not isinstance(
      self.global_fixed_point_consumer_audit,
      MocReflectedDomainGlobalMixedRegimeGlobalFixedPointConsumerAudit,
    ):
      raise TypeError('global_fixed_point_consumer_audit must be a typed audit')
    ####
    for name in (
      'global_feedback_consumed',
      'terminal_global_fixed_point_verified',
      'terminal_global_downstream_recheck_verified',
      'frontier_step_count_verified',
      'frontier_feedback_lineage_verified',
      'frontier_steps_consumed',
      'frontier_steps_locally_verified',
      'joint_recheck_verified',
      'global_coupling_verified',
      'canonical_free_boundary_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if self.global_coupling_verified or self.canonical_free_boundary_verified:
      raise ValueError('joint recheck cannot claim canonical global closure')
    ####
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError('joint recheck must remain promotion-blocked')
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalMixedRegimeJointFixedPointRefinementStatus
      .COMPLETED_RESEARCH_JOINT_RECHECK_WITH_OPEN_CLOSURE
      and self.global_feedback_consumed
      and self.terminal_global_fixed_point_verified
      and self.terminal_global_downstream_recheck_verified
      and self.frontier_step_count_verified
      and self.frontier_feedback_lineage_verified
      and self.frontier_steps_consumed
      and self.frontier_steps_locally_verified
      and self.joint_recheck_verified
      and self.chain_promotion_blocked
      and not self.global_coupling_verified
      and not self.production_claim_allowed
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': (
        MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_JOINT_FIXED_POINT_REFINEMENT_OPERATOR_ID
      ),
      'status': self.status.value,
      'converged': self.converged,
      'source_closure_fingerprint': self.source_closure_fingerprint,
      'global_feedback_consumed': self.global_feedback_consumed,
      'terminal_global_fixed_point_verified': (
        self.terminal_global_fixed_point_verified
      ),
      'terminal_global_downstream_recheck_verified': (
        self.terminal_global_downstream_recheck_verified
      ),
      'frontier_step_count_verified': self.frontier_step_count_verified,
      'frontier_feedback_lineage_verified': (
        self.frontier_feedback_lineage_verified
      ),
      'frontier_steps_consumed': self.frontier_steps_consumed,
      'frontier_steps_locally_verified': self.frontier_steps_locally_verified,
      'joint_recheck_verified': self.joint_recheck_verified,
      'global_coupling_verified': False,
      'canonical_free_boundary_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'global_fixed_point_consumer': (
        None
        if self.global_fixed_point_consumer is None
        else self.global_fixed_point_consumer.as_report()
      ),
      'global_fixed_point_consumer_audit': (
        None
        if self.global_fixed_point_consumer_audit is None
        else self.global_fixed_point_consumer_audit.as_report()
      ),
      'source_closure': (
        None if self.source_closure is None else self.source_closure.as_report()
      ),
      'request': None if self.request is None else self.request.as_report(),
      'claim_status': (
        'research-only per-closure shock-frontier recheck against global '
        'feedback states; the actual joint global fixed point, external '
        'validation, and production promotion remain open'
      ),
      'message': self.message,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeJointFixedPointRefinementAudit:
  """Independent replay of closure alignment and terminal composition."""

  status: MocReflectedDomainGlobalMixedRegimeJointFixedPointRefinementAuditStatus
  candidate: MocReflectedDomainGlobalMixedRegimeJointFixedPointRefinementResult | None
  feedback_lineage_replayed: bool = False
  frontier_step_count_replayed: bool = False
  frontier_closure_lineage_replayed: bool = False
  frontier_steps_replayed: bool = False
  terminal_replayed: bool = False
  global_fixed_point_consumer_audit_verified: bool = False
  independent_joint_recheck_verified: bool = False
  global_coupling_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalMixedRegimeJointFixedPointRefinementAuditStatus,
    ):
      raise TypeError('status must be a typed joint-recheck audit status')
    ####
    if self.candidate is not None and not isinstance(
      self.candidate,
      MocReflectedDomainGlobalMixedRegimeJointFixedPointRefinementResult,
    ):
      raise TypeError('candidate must be a typed joint-recheck result or None')
    ####
    for name in (
      'feedback_lineage_replayed',
      'frontier_step_count_replayed',
      'frontier_closure_lineage_replayed',
      'frontier_steps_replayed',
      'terminal_replayed',
      'global_fixed_point_consumer_audit_verified',
      'independent_joint_recheck_verified',
      'global_coupling_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if self.global_coupling_verified or not self.chain_promotion_blocked:
      raise ValueError('joint-recheck audit must remain promotion-blocked')
    ####
    if self.production_claim_allowed:
      raise ValueError('joint-recheck audit cannot allow production claims')
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalMixedRegimeJointFixedPointRefinementAuditStatus
      .VERIFIED_RESEARCH_JOINT_RECHECK
      and self.independent_joint_recheck_verified
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': (
        MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_JOINT_FIXED_POINT_REFINEMENT_OPERATOR_ID
      ),
      'audit_status': self.status.value,
      'converged': self.converged,
      'feedback_lineage_replayed': self.feedback_lineage_replayed,
      'frontier_step_count_replayed': self.frontier_step_count_replayed,
      'frontier_closure_lineage_replayed': (
        self.frontier_closure_lineage_replayed
      ),
      'frontier_steps_replayed': self.frontier_steps_replayed,
      'terminal_replayed': self.terminal_replayed,
      'global_fixed_point_consumer_audit_verified': (
        self.global_fixed_point_consumer_audit_verified
      ),
      'independent_joint_recheck_verified': (
        self.independent_joint_recheck_verified
      ),
      'global_coupling_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'candidate': (
        None if self.candidate is None else self.candidate.as_report()
      ),
      'message': self.message,
    }
  ####
####


def _failure(
  status: MocReflectedDomainGlobalMixedRegimeJointFixedPointRefinementStatus,
  message: str,
  *,
  request: MocReflectedDomainGlobalMixedRegimeJointFixedPointRefinementRequest | None = None,
  **values: Any,
) -> MocReflectedDomainGlobalMixedRegimeJointFixedPointRefinementResult:
  return MocReflectedDomainGlobalMixedRegimeJointFixedPointRefinementResult(
    status=status,
    request=request,
    message=message,
    **values,
  )
####


def _expected_closures(
  feedback: MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRun,
) -> tuple[MocReflectedDomainGlobalPhysicalClosureResult, ...]:
  return (
    feedback.source_closure,
    *tuple(
      iteration.next_closure
      for iteration in feedback.iterations
      if iteration.next_closure is not None
    ),
  )
####


def consume_reflected_domain_global_mixed_regime_joint_fixed_point(
  request: MocReflectedDomainGlobalMixedRegimeJointFixedPointRefinementRequest,
) -> MocReflectedDomainGlobalMixedRegimeJointFixedPointRefinementResult:
  """Consume one physical frontier step for every feedback closure."""

  status_type = (
    MocReflectedDomainGlobalMixedRegimeJointFixedPointRefinementStatus
  )
  if not isinstance(
    request,
    MocReflectedDomainGlobalMixedRegimeJointFixedPointRefinementRequest,
  ):
    return _failure(
      status_type.INVALID_INPUT,
      'request must be a typed joint fixed-point refinement request',
    )
  ####
  feedback = request.global_feedback
  source_closure = feedback.source_closure
  source_fingerprint = moc_reflected_domain_global_physical_closure_fingerprint(
    source_closure
  )
  if not feedback.research_feedback_completed:
    return _failure(
      status_type.GLOBAL_FEEDBACK_REQUIRED,
      'joint recheck requires completed research global feedback',
      request=request,
      source_closure=source_closure,
      source_closure_fingerprint=source_fingerprint,
      global_feedback_consumed=False,
    )
  ####
  terminal_fixed_point_verified = bool(
    feedback.terminal_global_fixed_point_verified
    and feedback.terminal_fixed_point_audit is not None
    and feedback.terminal_fixed_point_audit.terminal_global_fixed_point_verified
  )
  terminal_recheck_verified = bool(
    feedback.terminal_global_downstream_recheck_verified
    and feedback.terminal_fixed_point_audit is not None
    and feedback.terminal_fixed_point_audit
    .terminal_global_downstream_recheck_verified
  )
  if (
    request.require_terminal_global_fixed_point
    and not terminal_fixed_point_verified
  ) or (
    request.require_terminal_global_downstream_recheck
    and not terminal_recheck_verified
  ):
    return _failure(
      status_type.TERMINAL_FIXED_POINT_FAILURE,
      'joint recheck requires a verified terminal global solve and downstream '
      'response recheck',
      request=request,
      source_closure=source_closure,
      source_closure_fingerprint=source_fingerprint,
      global_feedback_consumed=True,
      terminal_global_fixed_point_verified=terminal_fixed_point_verified,
      terminal_global_downstream_recheck_verified=terminal_recheck_verified,
    )
  ####
  expected = _expected_closures(feedback)
  steps = request.shock_frontier_steps
  if len(steps) != len(expected):
    return _failure(
      status_type.FRONTIER_STEP_COUNT_FAILURE,
      'joint recheck requires exactly one frontier step for the feedback '
      f'source closure and each fresh next closure; expected {len(expected)}, '
      f'received {len(steps)}',
      request=request,
      source_closure=source_closure,
      source_closure_fingerprint=source_fingerprint,
      global_feedback_consumed=True,
      terminal_global_fixed_point_verified=terminal_fixed_point_verified,
      terminal_global_downstream_recheck_verified=terminal_recheck_verified,
      frontier_step_count_verified=False,
    )
  ####
  lineage = all(
    step.closure is closure
    and step.source_lineage_verified
    and step.fidelity_isolation_verified
    for step, closure in zip(steps, expected, strict=True)
  )
  if not lineage:
    return _failure(
      status_type.SOURCE_LINEAGE_FAILURE,
      'one or more frontier steps did not retain the exact feedback closure '
      'identity or promotion-blocked local lineage',
      request=request,
      source_closure=source_closure,
      source_closure_fingerprint=source_fingerprint,
      global_feedback_consumed=True,
      terminal_global_fixed_point_verified=terminal_fixed_point_verified,
      terminal_global_downstream_recheck_verified=terminal_recheck_verified,
      frontier_step_count_verified=True,
      frontier_feedback_lineage_verified=False,
    )
  ####
  if not all(step.locally_verified for step in steps):
    return _failure(
      status_type.FRONTIER_STEP_FAILURE,
      'one or more feedback closures lacked a locally verified physical '
      'shock-frontier handoff',
      request=request,
      source_closure=source_closure,
      source_closure_fingerprint=source_fingerprint,
      global_feedback_consumed=True,
      terminal_global_fixed_point_verified=terminal_fixed_point_verified,
      terminal_global_downstream_recheck_verified=terminal_recheck_verified,
      frontier_step_count_verified=True,
      frontier_feedback_lineage_verified=True,
      frontier_steps_consumed=True,
      frontier_steps_locally_verified=False,
    )
  ####
  first_consumer = consume_reflected_domain_global_mixed_regime_global_fixed_point(
    MocReflectedDomainGlobalMixedRegimeGlobalFixedPointConsumerRequest(
      shock_frontier_step=steps[0],
      global_feedback=feedback,
      require_terminal_global_fixed_point=(
        request.require_terminal_global_fixed_point
      ),
      require_terminal_global_downstream_recheck=(
        request.require_terminal_global_downstream_recheck
      ),
    )
  )
  if not first_consumer.converged:
    return _failure(
      status_type.FRONTIER_STEP_FAILURE,
      'the source frontier and terminal feedback composition did not pass: '
      f'{first_consumer.message}',
      request=request,
      source_closure=source_closure,
      source_closure_fingerprint=source_fingerprint,
      global_feedback_consumed=True,
      terminal_global_fixed_point_verified=terminal_fixed_point_verified,
      terminal_global_downstream_recheck_verified=terminal_recheck_verified,
      frontier_step_count_verified=True,
      frontier_feedback_lineage_verified=True,
      frontier_steps_consumed=True,
      frontier_steps_locally_verified=True,
      global_fixed_point_consumer=first_consumer,
    )
  ####
  first_audit = audit_reflected_domain_global_mixed_regime_global_fixed_point(
    first_consumer
  )
  if not first_audit.converged:
    return _failure(
      status_type.AUDIT_REQUIRED,
      'the source frontier/terminal-feedback composition did not replay',
      request=request,
      source_closure=source_closure,
      source_closure_fingerprint=source_fingerprint,
      global_feedback_consumed=True,
      terminal_global_fixed_point_verified=terminal_fixed_point_verified,
      terminal_global_downstream_recheck_verified=terminal_recheck_verified,
      frontier_step_count_verified=True,
      frontier_feedback_lineage_verified=True,
      frontier_steps_consumed=True,
      frontier_steps_locally_verified=True,
      global_fixed_point_consumer=first_consumer,
      global_fixed_point_consumer_audit=first_audit,
    )
  ####
  return MocReflectedDomainGlobalMixedRegimeJointFixedPointRefinementResult(
    status=(
      status_type.COMPLETED_RESEARCH_JOINT_RECHECK_WITH_OPEN_CLOSURE
    ),
    request=request,
    source_closure=source_closure,
    source_closure_fingerprint=source_fingerprint,
    global_feedback_consumed=True,
    terminal_global_fixed_point_verified=terminal_fixed_point_verified,
    terminal_global_downstream_recheck_verified=terminal_recheck_verified,
    frontier_step_count_verified=True,
    frontier_feedback_lineage_verified=True,
    frontier_steps_consumed=True,
    frontier_steps_locally_verified=True,
    global_fixed_point_consumer=first_consumer,
    global_fixed_point_consumer_audit=first_audit,
    joint_recheck_verified=True,
    global_coupling_verified=False,
    canonical_free_boundary_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    message=(
      'the physical shock-frontier chain was independently retained at every '
      'fresh global-feedback closure and the terminal global/downstream '
      'research recheck passed; the actual joint canonical fixed point remains '
      'open'
    ),
  )
####


def audit_reflected_domain_global_mixed_regime_joint_fixed_point(
  result: MocReflectedDomainGlobalMixedRegimeJointFixedPointRefinementResult,
) -> MocReflectedDomainGlobalMixedRegimeJointFixedPointRefinementAudit:
  """Replay exact feedback closure alignment and the source composition."""

  audit_status = (
    MocReflectedDomainGlobalMixedRegimeJointFixedPointRefinementAuditStatus
  )
  if not isinstance(
    result,
    MocReflectedDomainGlobalMixedRegimeJointFixedPointRefinementResult,
  ):
    return MocReflectedDomainGlobalMixedRegimeJointFixedPointRefinementAudit(
      status=audit_status.INVALID_INPUT,
      candidate=None,
      message='result must be a typed joint fixed-point refinement result',
    )
  ####
  request = result.request
  if request is None:
    return MocReflectedDomainGlobalMixedRegimeJointFixedPointRefinementAudit(
      status=audit_status.REPLAY_FAILURE,
      candidate=result,
      message='joint recheck replay requires the exact retained request',
    )
  ####
  try:
    replay = consume_reflected_domain_global_mixed_regime_joint_fixed_point(
      request
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return MocReflectedDomainGlobalMixedRegimeJointFixedPointRefinementAudit(
      status=audit_status.REPLAY_FAILURE,
      candidate=result,
      message=f'independent joint recheck replay raised: {error}',
    )
  ####
  expected = _expected_closures(request.global_feedback)
  steps = request.shock_frontier_steps
  feedback_lineage = bool(
    replay.request is request
    and replay.source_closure is result.source_closure
    and replay.source_closure_fingerprint == result.source_closure_fingerprint
    and replay.global_feedback_consumed == result.global_feedback_consumed
  )
  count_replayed = bool(
    len(steps) == len(expected)
    and replay.frontier_step_count_verified
    == result.frontier_step_count_verified
  )
  closure_lineage = bool(
    len(steps) == len(expected)
    and all(
      step.closure is closure
      for step, closure in zip(steps, expected, strict=True)
    )
    and replay.frontier_feedback_lineage_verified
    == result.frontier_feedback_lineage_verified
  )
  steps_replayed = bool(
    all(step.locally_verified for step in steps)
    and replay.frontier_steps_locally_verified
    == result.frontier_steps_locally_verified
    and replay.frontier_steps_consumed == result.frontier_steps_consumed
  )
  terminal_replayed = bool(
    replay.terminal_global_fixed_point_verified
    == result.terminal_global_fixed_point_verified
    and replay.terminal_global_downstream_recheck_verified
    == result.terminal_global_downstream_recheck_verified
  )
  consumer_audit = bool(
    replay.global_fixed_point_consumer_audit is not None
    and replay.global_fixed_point_consumer_audit.converged
    and replay.joint_recheck_verified == result.joint_recheck_verified
  )
  independent = bool(
    replay.status is result.status
    and feedback_lineage
    and count_replayed
    and closure_lineage
    and steps_replayed
    and terminal_replayed
    and consumer_audit
    and replay.converged
    and not replay.global_coupling_verified
    and replay.chain_promotion_blocked
    and not replay.production_claim_allowed
  )
  return MocReflectedDomainGlobalMixedRegimeJointFixedPointRefinementAudit(
    status=(
      audit_status.VERIFIED_RESEARCH_JOINT_RECHECK
      if independent
      else audit_status.LINEAGE_FAILURE
    ),
    candidate=result,
    feedback_lineage_replayed=feedback_lineage,
    frontier_step_count_replayed=count_replayed,
    frontier_closure_lineage_replayed=closure_lineage,
    frontier_steps_replayed=steps_replayed,
    terminal_replayed=terminal_replayed,
    global_fixed_point_consumer_audit_verified=consumer_audit,
    independent_joint_recheck_verified=independent,
    global_coupling_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    message=(
      'independent replay reproduced the exact frontier step for every '
      'feedback closure and the terminal composition'
      if independent
      else 'independent replay did not reproduce the exact joint recheck'
    ),
  )
####
