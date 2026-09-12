"""Compose the physical shock frontier with terminal global feedback evidence.

The existing boundary-condition feedback operator can perform a fresh global
re-solve and a downstream recheck, but it does not consume the separate
supersonic shock-frontier characteristic chain.  This module is the typed
composition boundary between those two research lanes.  It requires exact
source lineage and independent replay of both lanes while keeping canonical
global closure and production promotion closed.
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
from exhaust_plume.validation.moc_global_mixed_regime_canonical_consumer import (
  MocReflectedDomainGlobalMixedRegimeCanonicalConsumerAudit,
  MocReflectedDomainGlobalMixedRegimeCanonicalConsumerRequest,
  MocReflectedDomainGlobalMixedRegimeCanonicalConsumerResult,
  audit_reflected_domain_global_mixed_regime_canonical_source,
  consume_reflected_domain_global_mixed_regime_canonical_source,
)
from exhaust_plume.validation.moc_global_mixed_regime_shock_frontier_refinement import (
  MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementStep,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_GLOBAL_FIXED_POINT_CONSUMER_OPERATOR_ID',
  'MocReflectedDomainGlobalMixedRegimeGlobalFixedPointConsumerStatus',
  'MocReflectedDomainGlobalMixedRegimeGlobalFixedPointConsumerRequest',
  'MocReflectedDomainGlobalMixedRegimeGlobalFixedPointConsumerResult',
  'MocReflectedDomainGlobalMixedRegimeGlobalFixedPointConsumerAuditStatus',
  'MocReflectedDomainGlobalMixedRegimeGlobalFixedPointConsumerAudit',
  'consume_reflected_domain_global_mixed_regime_global_fixed_point',
  'audit_reflected_domain_global_mixed_regime_global_fixed_point',
)


MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_GLOBAL_FIXED_POINT_CONSUMER_OPERATOR_ID = (
  'op.moc.reflected-domain.global-mixed-regime-global-fixed-point-consumer-v1'
)


class MocReflectedDomainGlobalMixedRegimeGlobalFixedPointConsumerStatus(
  str,
  Enum,
):
  """Typed outcomes of the two-lane research composition boundary."""

  COMPLETED_RESEARCH_CONSUMPTION_WITH_OPEN_GLOBAL_CLOSURE = (
    'completed-research-global-fixed-point-consumption-with-open-global-closure'
  )
  INVALID_INPUT = 'invalid_input'
  SHOCK_FRONTIER_REQUIRED = (
    'global-fixed-point-consumer-shock-frontier-required'
  )
  GLOBAL_FEEDBACK_REQUIRED = 'global-fixed-point-consumer-global-feedback-required'
  GLOBAL_FEEDBACK_FAILURE = 'global-fixed-point-consumer-global-feedback-failure'
  TERMINAL_FIXED_POINT_FAILURE = (
    'global-fixed-point-consumer-terminal-fixed-point-failure'
  )
  SOURCE_LINEAGE_FAILURE = 'global-fixed-point-consumer-source-lineage-failure'
  CANONICAL_CONSUMER_FAILURE = (
    'global-fixed-point-consumer-canonical-consumer-failure'
  )
  AUDIT_REQUIRED = 'global-fixed-point-consumer-audit-required'
  FIDELITY_FAILURE = 'global-fixed-point-consumer-fidelity-failure'
####


class MocReflectedDomainGlobalMixedRegimeGlobalFixedPointConsumerAuditStatus(
  str,
  Enum,
):
  """Typed outcomes of the independent composition replay."""

  VERIFIED_RESEARCH_COMPOSITION = 'verified-research-global-fixed-point-composition'
  INVALID_INPUT = 'invalid_input'
  REPLAY_FAILURE = 'global-fixed-point-consumer-audit-replay-failure'
  LINEAGE_FAILURE = 'global-fixed-point-consumer-audit-lineage-failure'
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeGlobalFixedPointConsumerRequest:
  """Exact shock-frontier and terminal-feedback inputs."""

  shock_frontier_step: MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementStep
  global_feedback: MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRun | None = None
  require_terminal_global_fixed_point: bool = True
  require_terminal_global_downstream_recheck: bool = True
  source: str = (
    'research-global-mixed-regime-global-fixed-point-consumer-v1'
  )

  def __post_init__(self) -> None:
    if not isinstance(
      self.shock_frontier_step,
      MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementStep,
    ):
      raise TypeError('shock_frontier_step must be a typed frontier step')
    ####
    if self.global_feedback is not None and not isinstance(
      self.global_feedback,
      MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRun,
    ):
      raise TypeError('global_feedback must be a typed feedback run or None')
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
    object.__setattr__(self, 'source', source)
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': (
        MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_GLOBAL_FIXED_POINT_CONSUMER_OPERATOR_ID
      ),
      'source': self.source,
      'require_terminal_global_fixed_point': (
        self.require_terminal_global_fixed_point
      ),
      'require_terminal_global_downstream_recheck': (
        self.require_terminal_global_downstream_recheck
      ),
      'shock_frontier_step': self.shock_frontier_step.as_report(),
      'global_feedback': (
        None if self.global_feedback is None else self.global_feedback.as_report()
      ),
      'research_only': True,
      'production_claim_allowed': False,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeGlobalFixedPointConsumerResult:
  """Research composition with canonical global closure explicitly open."""

  status: MocReflectedDomainGlobalMixedRegimeGlobalFixedPointConsumerStatus
  request: MocReflectedDomainGlobalMixedRegimeGlobalFixedPointConsumerRequest | None
  source_closure: MocReflectedDomainGlobalPhysicalClosureResult | None = None
  source_closure_fingerprint: str | None = None
  shock_frontier_consumed: bool = False
  shock_frontier_lineage_verified: bool = False
  terminal_feedback_consumed: bool = False
  terminal_global_fixed_point_verified: bool = False
  terminal_global_downstream_recheck_verified: bool = False
  canonical_consumer: MocReflectedDomainGlobalMixedRegimeCanonicalConsumerResult | None = None
  canonical_consumer_audit: MocReflectedDomainGlobalMixedRegimeCanonicalConsumerAudit | None = None
  canonical_research_consumption_verified: bool = False
  global_coupling_verified: bool = False
  canonical_free_boundary_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalMixedRegimeGlobalFixedPointConsumerStatus,
    ):
      raise TypeError('status must be a typed global fixed-point status')
    ####
    if self.request is not None and not isinstance(
      self.request,
      MocReflectedDomainGlobalMixedRegimeGlobalFixedPointConsumerRequest,
    ):
      raise TypeError('request must be a typed global fixed-point request')
    ####
    if self.source_closure is not None and not isinstance(
      self.source_closure,
      MocReflectedDomainGlobalPhysicalClosureResult,
    ):
      raise TypeError('source_closure must be a typed physical closure or None')
    ####
    if self.canonical_consumer is not None and not isinstance(
      self.canonical_consumer,
      MocReflectedDomainGlobalMixedRegimeCanonicalConsumerResult,
    ):
      raise TypeError('canonical_consumer must be a typed result or None')
    ####
    if self.canonical_consumer_audit is not None and not isinstance(
      self.canonical_consumer_audit,
      MocReflectedDomainGlobalMixedRegimeCanonicalConsumerAudit,
    ):
      raise TypeError('canonical_consumer_audit must be a typed audit or None')
    ####
    for name in (
      'shock_frontier_consumed',
      'shock_frontier_lineage_verified',
      'terminal_feedback_consumed',
      'terminal_global_fixed_point_verified',
      'terminal_global_downstream_recheck_verified',
      'canonical_research_consumption_verified',
      'global_coupling_verified',
      'canonical_free_boundary_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if self.source_closure_fingerprint is not None and not isinstance(
      self.source_closure_fingerprint,
      str,
    ):
      raise TypeError('source_closure_fingerprint must be a string or None')
    ####
    if self.global_coupling_verified or self.canonical_free_boundary_verified:
      raise ValueError('research composition cannot claim global closure')
    ####
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError('research composition must remain promotion-blocked')
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalMixedRegimeGlobalFixedPointConsumerStatus
      .COMPLETED_RESEARCH_CONSUMPTION_WITH_OPEN_GLOBAL_CLOSURE
      and self.shock_frontier_consumed
      and self.shock_frontier_lineage_verified
      and self.terminal_feedback_consumed
      and (
        self.request is None
        or not self.request.require_terminal_global_fixed_point
        or self.terminal_global_fixed_point_verified
      )
      and (
        self.request is None
        or not self.request.require_terminal_global_downstream_recheck
        or self.terminal_global_downstream_recheck_verified
      )
      and self.canonical_research_consumption_verified
      and self.chain_promotion_blocked
      and not self.global_coupling_verified
      and not self.production_claim_allowed
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': (
        MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_GLOBAL_FIXED_POINT_CONSUMER_OPERATOR_ID
      ),
      'status': self.status.value,
      'converged': self.converged,
      'source_closure_fingerprint': self.source_closure_fingerprint,
      'shock_frontier_consumed': self.shock_frontier_consumed,
      'shock_frontier_lineage_verified': self.shock_frontier_lineage_verified,
      'terminal_feedback_consumed': self.terminal_feedback_consumed,
      'terminal_global_fixed_point_verified': (
        self.terminal_global_fixed_point_verified
      ),
      'terminal_global_downstream_recheck_verified': (
        self.terminal_global_downstream_recheck_verified
      ),
      'canonical_research_consumption_verified': (
        self.canonical_research_consumption_verified
      ),
      'canonical_free_boundary_verified': False,
      'global_coupling_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'canonical_consumer': (
        None
        if self.canonical_consumer is None
        else self.canonical_consumer.as_report()
      ),
      'canonical_consumer_audit': (
        None
        if self.canonical_consumer_audit is None
        else self.canonical_consumer_audit.as_report()
      ),
      'source_closure': (
        None if self.source_closure is None else self.source_closure.as_report()
      ),
      'request': None if self.request is None else self.request.as_report(),
      'claim_status': (
        'research-only composition of the physical shock frontier and a '
        'terminal global/downstream feedback recheck; canonical global '
        'closure, external validation, and production promotion remain open'
      ),
      'message': self.message,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeGlobalFixedPointConsumerAudit:
  """Independent replay of the exact two-lane composition."""

  status: MocReflectedDomainGlobalMixedRegimeGlobalFixedPointConsumerAuditStatus
  candidate: MocReflectedDomainGlobalMixedRegimeGlobalFixedPointConsumerResult | None
  shock_frontier_lineage_replayed: bool = False
  terminal_feedback_lineage_replayed: bool = False
  terminal_fixed_point_replayed: bool = False
  canonical_consumer_audit_verified: bool = False
  independent_composition_verified: bool = False
  global_coupling_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalMixedRegimeGlobalFixedPointConsumerAuditStatus,
    ):
      raise TypeError('status must be a typed composition audit status')
    ####
    if self.candidate is not None and not isinstance(
      self.candidate,
      MocReflectedDomainGlobalMixedRegimeGlobalFixedPointConsumerResult,
    ):
      raise TypeError('candidate must be a typed composition result or None')
    ####
    for name in (
      'shock_frontier_lineage_replayed',
      'terminal_feedback_lineage_replayed',
      'terminal_fixed_point_replayed',
      'canonical_consumer_audit_verified',
      'independent_composition_verified',
      'global_coupling_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if self.global_coupling_verified or not self.chain_promotion_blocked:
      raise ValueError('composition audit must remain promotion-blocked')
    ####
    if self.production_claim_allowed:
      raise ValueError('composition audit cannot allow production claims')
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalMixedRegimeGlobalFixedPointConsumerAuditStatus
      .VERIFIED_RESEARCH_COMPOSITION
      and self.independent_composition_verified
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': (
        MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_GLOBAL_FIXED_POINT_CONSUMER_OPERATOR_ID
      ),
      'audit_status': self.status.value,
      'converged': self.converged,
      'shock_frontier_lineage_replayed': (
        self.shock_frontier_lineage_replayed
      ),
      'terminal_feedback_lineage_replayed': (
        self.terminal_feedback_lineage_replayed
      ),
      'terminal_fixed_point_replayed': self.terminal_fixed_point_replayed,
      'canonical_consumer_audit_verified': (
        self.canonical_consumer_audit_verified
      ),
      'independent_composition_verified': (
        self.independent_composition_verified
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
  status: MocReflectedDomainGlobalMixedRegimeGlobalFixedPointConsumerStatus,
  message: str,
  *,
  request: MocReflectedDomainGlobalMixedRegimeGlobalFixedPointConsumerRequest | None = None,
  **values: Any,
) -> MocReflectedDomainGlobalMixedRegimeGlobalFixedPointConsumerResult:
  return MocReflectedDomainGlobalMixedRegimeGlobalFixedPointConsumerResult(
    status=status,
    request=request,
    message=message,
    **values,
  )
####


def consume_reflected_domain_global_mixed_regime_global_fixed_point(
  request: MocReflectedDomainGlobalMixedRegimeGlobalFixedPointConsumerRequest,
) -> MocReflectedDomainGlobalMixedRegimeGlobalFixedPointConsumerResult:
  """Consume both research lanes without claiming the canonical fixed point."""

  status_type = MocReflectedDomainGlobalMixedRegimeGlobalFixedPointConsumerStatus
  if not isinstance(
    request,
    MocReflectedDomainGlobalMixedRegimeGlobalFixedPointConsumerRequest,
  ):
    return _failure(
      status_type.INVALID_INPUT,
      'request must be a typed global fixed-point consumer request',
    )
  ####
  frontier = request.shock_frontier_step
  closure = frontier.closure
  fingerprint = moc_reflected_domain_global_physical_closure_fingerprint(
    closure
  )
  if not frontier.locally_verified:
    return _failure(
      status_type.SHOCK_FRONTIER_REQUIRED,
      'global fixed-point consumption requires a locally verified physical '
      'shock-frontier handoff and independent replay chain',
      request=request,
      source_closure=closure,
      source_closure_fingerprint=fingerprint,
      shock_frontier_consumed=False,
      shock_frontier_lineage_verified=False,
    )
  ####
  feedback = request.global_feedback
  if feedback is None:
    return _failure(
      status_type.GLOBAL_FEEDBACK_REQUIRED,
      'global fixed-point consumption requires the exact terminal global '
      'feedback run and downstream recheck',
      request=request,
      source_closure=closure,
      source_closure_fingerprint=fingerprint,
      shock_frontier_consumed=True,
      shock_frontier_lineage_verified=True,
    )
  ####
  feedback_lineage = bool(
    feedback.source_closure is closure
    and moc_reflected_domain_global_physical_closure_fingerprint(
      feedback.source_closure
    )
    == fingerprint
    and feedback.chain_promotion_blocked
    and not feedback.production_claim_allowed
    and not feedback.global_coupling_verified
    and not feedback.downstream_boundary_closure_verified
  )
  if not feedback_lineage:
    return _failure(
      status_type.SOURCE_LINEAGE_FAILURE,
      'terminal global feedback did not retain the exact physical source '
      'closure or its promotion-blocked fidelity flags',
      request=request,
      source_closure=closure,
      source_closure_fingerprint=fingerprint,
      shock_frontier_consumed=True,
      shock_frontier_lineage_verified=True,
      terminal_feedback_consumed=False,
    )
  ####
  if not feedback.research_feedback_completed:
    return _failure(
      status_type.GLOBAL_FEEDBACK_FAILURE,
      'terminal global feedback did not complete its declared research contract',
      request=request,
      source_closure=closure,
      source_closure_fingerprint=fingerprint,
      shock_frontier_consumed=True,
      shock_frontier_lineage_verified=True,
      terminal_feedback_consumed=True,
    )
  ####
  terminal_audit = feedback.terminal_fixed_point_audit
  terminal_fixed_point_verified = bool(
    feedback.terminal_global_fixed_point_verified
    and terminal_audit is not None
    and terminal_audit.terminal_global_fixed_point_verified
    and terminal_audit.terminal_global_resolve_verified
  )
  downstream_recheck_verified = bool(
    feedback.terminal_global_downstream_recheck_verified
    and terminal_audit is not None
    and terminal_audit.terminal_global_downstream_recheck_verified
  )
  if (
    request.require_terminal_global_fixed_point
    and not terminal_fixed_point_verified
  ):
    return _failure(
      status_type.TERMINAL_FIXED_POINT_FAILURE,
      'the feedback run did not retain a verified terminal global re-solve',
      request=request,
      source_closure=closure,
      source_closure_fingerprint=fingerprint,
      shock_frontier_consumed=True,
      shock_frontier_lineage_verified=True,
      terminal_feedback_consumed=True,
      terminal_global_fixed_point_verified=terminal_fixed_point_verified,
      terminal_global_downstream_recheck_verified=downstream_recheck_verified,
    )
  ####
  if (
    request.require_terminal_global_downstream_recheck
    and not downstream_recheck_verified
  ):
    return _failure(
      status_type.TERMINAL_FIXED_POINT_FAILURE,
      'the feedback run did not retain a verified downstream response recheck '
      'after the terminal global re-solve',
      request=request,
      source_closure=closure,
      source_closure_fingerprint=fingerprint,
      shock_frontier_consumed=True,
      shock_frontier_lineage_verified=True,
      terminal_feedback_consumed=True,
      terminal_global_fixed_point_verified=terminal_fixed_point_verified,
      terminal_global_downstream_recheck_verified=downstream_recheck_verified,
    )
  ####
  canonical_request = MocReflectedDomainGlobalMixedRegimeCanonicalConsumerRequest(
    characteristic_compatibility=frontier.compatibility,
    upstream_state_equation=frontier.state_equation,
    global_feedback=feedback,
    require_global_feedback=True,
    require_terminal_global_downstream_recheck=(
      request.require_terminal_global_downstream_recheck
    ),
    normal_closure=frontier.normal_closure,
    normal_closure_audit=frontier.normal_closure_audit,
    require_normal_closure=True,
    source=(
      'research-global-mixed-regime-shock-frontier-global-fixed-point-'
      'consumer-v1'
    ),
  )
  canonical = consume_reflected_domain_global_mixed_regime_canonical_source(
    canonical_request
  )
  if not canonical.converged:
    return _failure(
      status_type.CANONICAL_CONSUMER_FAILURE,
      'the exact shock-frontier chain and terminal feedback did not pass the '
      f'canonical research-consumer boundary: {canonical.message}',
      request=request,
      source_closure=closure,
      source_closure_fingerprint=fingerprint,
      shock_frontier_consumed=True,
      shock_frontier_lineage_verified=True,
      terminal_feedback_consumed=True,
      terminal_global_fixed_point_verified=terminal_fixed_point_verified,
      terminal_global_downstream_recheck_verified=downstream_recheck_verified,
      canonical_consumer=canonical,
    )
  ####
  canonical_audit = audit_reflected_domain_global_mixed_regime_canonical_source(
    canonical
  )
  if not canonical_audit.converged:
    return _failure(
      status_type.AUDIT_REQUIRED,
      'the canonical research-consumer boundary did not independently replay',
      request=request,
      source_closure=closure,
      source_closure_fingerprint=fingerprint,
      shock_frontier_consumed=True,
      shock_frontier_lineage_verified=True,
      terminal_feedback_consumed=True,
      terminal_global_fixed_point_verified=terminal_fixed_point_verified,
      terminal_global_downstream_recheck_verified=downstream_recheck_verified,
      canonical_consumer=canonical,
      canonical_consumer_audit=canonical_audit,
    )
  ####
  return MocReflectedDomainGlobalMixedRegimeGlobalFixedPointConsumerResult(
    status=(
      status_type.COMPLETED_RESEARCH_CONSUMPTION_WITH_OPEN_GLOBAL_CLOSURE
    ),
    request=request,
    source_closure=closure,
    source_closure_fingerprint=fingerprint,
    shock_frontier_consumed=True,
    shock_frontier_lineage_verified=True,
    terminal_feedback_consumed=True,
    terminal_global_fixed_point_verified=terminal_fixed_point_verified,
    terminal_global_downstream_recheck_verified=downstream_recheck_verified,
    canonical_consumer=canonical,
    canonical_consumer_audit=canonical_audit,
    canonical_research_consumption_verified=True,
    global_coupling_verified=False,
    canonical_free_boundary_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    message=(
      'the physical shock-frontier chain and terminal global/downstream '
      'research feedback were consumed and independently replayed; the '
      'canonical global fixed point and production claim remain open'
    ),
  )
####


def audit_reflected_domain_global_mixed_regime_global_fixed_point(
  result: MocReflectedDomainGlobalMixedRegimeGlobalFixedPointConsumerResult,
) -> MocReflectedDomainGlobalMixedRegimeGlobalFixedPointConsumerAudit:
  """Replay the exact frontier, feedback, and canonical-consumer composition."""

  audit_status = (
    MocReflectedDomainGlobalMixedRegimeGlobalFixedPointConsumerAuditStatus
  )
  if not isinstance(
    result,
    MocReflectedDomainGlobalMixedRegimeGlobalFixedPointConsumerResult,
  ):
    return MocReflectedDomainGlobalMixedRegimeGlobalFixedPointConsumerAudit(
      status=audit_status.INVALID_INPUT,
      candidate=None,
      message='result must be a typed global fixed-point consumer result',
    )
  ####
  request = result.request
  if request is None:
    return MocReflectedDomainGlobalMixedRegimeGlobalFixedPointConsumerAudit(
      status=audit_status.REPLAY_FAILURE,
      candidate=result,
      message='composition replay requires the exact retained request',
    )
  ####
  try:
    replay = consume_reflected_domain_global_mixed_regime_global_fixed_point(
      request
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return MocReflectedDomainGlobalMixedRegimeGlobalFixedPointConsumerAudit(
      status=audit_status.REPLAY_FAILURE,
      candidate=result,
      message=f'independent composition replay raised: {error}',
    )
  ####
  frontier_lineage = bool(
    replay.request is request
    and replay.source_closure is result.source_closure
    and replay.source_closure_fingerprint == result.source_closure_fingerprint
    and replay.shock_frontier_consumed == result.shock_frontier_consumed
    and replay.shock_frontier_lineage_verified
    == result.shock_frontier_lineage_verified
  )
  feedback_lineage = bool(
    request.global_feedback is not None
    and replay.terminal_feedback_consumed == result.terminal_feedback_consumed
    and replay.terminal_global_fixed_point_verified
    == result.terminal_global_fixed_point_verified
    and replay.terminal_global_downstream_recheck_verified
    == result.terminal_global_downstream_recheck_verified
  )
  terminal_replayed = bool(
    request.global_feedback is not None
    and request.global_feedback.terminal_fixed_point_audit is not None
    and (
      not request.require_terminal_global_fixed_point
      or (
        request.global_feedback.terminal_fixed_point_audit
        .terminal_global_fixed_point_verified
        == result.terminal_global_fixed_point_verified
      )
    )
    and (
      not request.require_terminal_global_downstream_recheck
      or (
        request.global_feedback.terminal_fixed_point_audit
        .terminal_global_downstream_recheck_verified
        == result.terminal_global_downstream_recheck_verified
      )
    )
  )
  canonical_audit_verified = bool(
    replay.canonical_consumer_audit is not None
    and replay.canonical_consumer_audit.converged
    and replay.canonical_research_consumption_verified
    == result.canonical_research_consumption_verified
  )
  independent = bool(
    replay.status is result.status
    and frontier_lineage
    and feedback_lineage
    and terminal_replayed
    and canonical_audit_verified
    and replay.converged
    and not replay.global_coupling_verified
    and replay.chain_promotion_blocked
    and not replay.production_claim_allowed
  )
  return MocReflectedDomainGlobalMixedRegimeGlobalFixedPointConsumerAudit(
    status=(
      audit_status.VERIFIED_RESEARCH_COMPOSITION
      if independent
      else audit_status.LINEAGE_FAILURE
    ),
    candidate=result,
    shock_frontier_lineage_replayed=frontier_lineage,
    terminal_feedback_lineage_replayed=feedback_lineage,
    terminal_fixed_point_replayed=terminal_replayed,
    canonical_consumer_audit_verified=canonical_audit_verified,
    independent_composition_verified=independent,
    global_coupling_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    message=(
      'independent replay reproduced the exact physical shock-frontier and '
      'terminal global/downstream research composition'
      if independent
      else 'independent replay did not reproduce the exact research composition'
    ),
  )
####
