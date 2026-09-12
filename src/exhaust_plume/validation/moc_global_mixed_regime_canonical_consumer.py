"""Research-only composition gate for the canonical mixed-regime source.

This module is the P3.43 boundary between the already audited research
operators and the future canonical moving characteristic/free-boundary solve.
It consumes the exact incoming-family compatibility evidence, the exact
conservative/entropy state equation, and a solver-owned global-feedback result
as separate contracts.  It independently replays the first two inputs and
requires their source lineage to agree.

The current global-feedback operator intentionally remains below canonical
closure.  Therefore a successful result from this module means that the
research evidence was composed without crossing a fidelity boundary; it does
not mean that normal closure, a global fixed point, or production promotion
has been achieved.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from exhaust_plume.models.moc.global_mixed_regime_upstream_characteristic_compatibility import (
  MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityResult,
  audit_reflected_domain_global_mixed_regime_upstream_characteristic_compatibility,
)
from exhaust_plume.models.moc.global_mixed_regime_upstream_state_equation import (
  MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationResult,
  audit_reflected_domain_global_mixed_regime_upstream_state_equation,
)
from exhaust_plume.models.moc.global_physical_closure import (
  MocReflectedDomainGlobalPhysicalClosureResult,
  moc_reflected_domain_global_physical_closure_fingerprint,
)
from exhaust_plume.models.moc.global_mixed_regime_normal_closure import (
  MocReflectedDomainGlobalMixedRegimeNormalClosureAudit,
  MocReflectedDomainGlobalMixedRegimeNormalClosureResult,
  audit_reflected_domain_global_mixed_regime_normal_closure,
)
from exhaust_plume.validation.moc_global_coupled_boundary_condition_feedback import (
  MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRun,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_CANONICAL_CONSUMER_OPERATOR_ID',
  'MocReflectedDomainGlobalMixedRegimeCanonicalConsumerStatus',
  'MocReflectedDomainGlobalMixedRegimeCanonicalConsumerRequest',
  'MocReflectedDomainGlobalMixedRegimeCanonicalConsumerResult',
  'MocReflectedDomainGlobalMixedRegimeCanonicalConsumerAuditStatus',
  'MocReflectedDomainGlobalMixedRegimeCanonicalConsumerAudit',
  'consume_reflected_domain_global_mixed_regime_canonical_source',
  'audit_reflected_domain_global_mixed_regime_canonical_source',
)


MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_CANONICAL_CONSUMER_OPERATOR_ID = (
  'op.moc.reflected-domain.global-mixed-regime-canonical-consumer-gate-v1'
)


class MocReflectedDomainGlobalMixedRegimeCanonicalConsumerStatus(str, Enum):
  """Typed outcomes of the research-to-canonical composition boundary."""

  COMPLETED_RESEARCH_CANONICAL_CONSUMPTION_WITH_OPEN_CLOSURE = (
    'completed-research-canonical-consumption-with-open-closure'
  )
  COMPLETED_RESEARCH_CANONICAL_CONSUMPTION_WITH_OPEN_GLOBAL_CLOSURE = (
    'completed-research-canonical-consumption-with-open-global-closure'
  )
  INVALID_INPUT = 'invalid_input'
  CHARACTERISTIC_COMPATIBILITY_REQUIRED = (
    'canonical-consumer-characteristic-compatibility-required'
  )
  UPSTREAM_STATE_EQUATION_REQUIRED = (
    'canonical-consumer-upstream-state-equation-required'
  )
  SOURCE_LINEAGE_FAILURE = 'canonical-consumer-source-lineage-failure'
  AUDIT_REQUIRED = 'canonical-consumer-independent-audit-required'
  GLOBAL_FEEDBACK_REQUIRED = 'canonical-consumer-global-feedback-required'
  GLOBAL_FEEDBACK_FAILURE = 'canonical-consumer-global-feedback-failure'
  NORMAL_CLOSURE_REQUIRED = 'canonical-consumer-normal-closure-required'
####


class MocReflectedDomainGlobalMixedRegimeCanonicalConsumerAuditStatus(
  str,
  Enum,
):
  """Typed outcomes of the composed evidence audit."""

  VERIFIED_RESEARCH_CANONICAL_CONSUMPTION = (
    'verified-research-canonical-consumption'
  )
  INVALID_INPUT = 'invalid_input'
  REPLAY_FAILURE = 'canonical-consumer-audit-replay-failure'
  LINEAGE_FAILURE = 'canonical-consumer-audit-lineage-failure'
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeCanonicalConsumerRequest:
  """Exact lower-lane inputs required by the canonical source boundary."""

  characteristic_compatibility: (
    MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityResult
  )
  upstream_state_equation: (
    MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationResult
  )
  global_feedback: MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRun | None = None
  require_global_feedback: bool = True
  require_terminal_global_downstream_recheck: bool = True
  normal_closure: MocReflectedDomainGlobalMixedRegimeNormalClosureResult | None = None
  normal_closure_audit: MocReflectedDomainGlobalMixedRegimeNormalClosureAudit | None = None
  require_normal_closure: bool = False
  source: str = (
    'research-global-mixed-regime-canonical-consumer-gate-v1'
  )

  def __post_init__(self) -> None:
    if not isinstance(
      self.characteristic_compatibility,
      MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityResult,
    ):
      raise TypeError('characteristic_compatibility must be a typed result')
    ####
    if not isinstance(
      self.upstream_state_equation,
      MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationResult,
    ):
      raise TypeError('upstream_state_equation must be a typed result')
    ####
    if self.global_feedback is not None and not isinstance(
      self.global_feedback,
      MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRun,
    ):
      raise TypeError('global_feedback must be a typed feedback result or None')
    ####
    if self.normal_closure is not None and not isinstance(
      self.normal_closure,
      MocReflectedDomainGlobalMixedRegimeNormalClosureResult,
    ):
      raise TypeError('normal_closure must be a typed result or None')
    ####
    if self.normal_closure_audit is not None and not isinstance(
      self.normal_closure_audit,
      MocReflectedDomainGlobalMixedRegimeNormalClosureAudit,
    ):
      raise TypeError('normal_closure_audit must be a typed audit or None')
    ####
    for name in (
      'require_global_feedback',
      'require_terminal_global_downstream_recheck',
      'require_normal_closure',
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
      'operator_id': MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_CANONICAL_CONSUMER_OPERATOR_ID,
      'source': self.source,
      'require_global_feedback': self.require_global_feedback,
      'require_terminal_global_downstream_recheck': (
        self.require_terminal_global_downstream_recheck
      ),
      'characteristic_compatibility': self.characteristic_compatibility.as_report(),
      'upstream_state_equation': self.upstream_state_equation.as_report(),
      'global_feedback': (
        None if self.global_feedback is None else self.global_feedback.as_report()
      ),
      'normal_closure': (
        None if self.normal_closure is None else self.normal_closure.as_report()
      ),
      'normal_closure_audit': (
        None
        if self.normal_closure_audit is None
        else self.normal_closure_audit.as_report()
      ),
      'require_normal_closure': self.require_normal_closure,
      'research_only': True,
      'production_claim_allowed': False,
    }
  ####
####


def _chain_state_equation(
  compatibility: (
    MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityResult
  ),
) -> MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationResult | None:
  request = compatibility.request
  if request is None or request.equation_request is None:
    return None
  ####
  interface_request = request.equation_request.transonic_interface.request
  if interface_request is None:
    return None
  ####
  frame_request = interface_request.characteristic_frame.request
  if frame_request is None:
    return None
  ####
  return frame_request.upstream_state_equation
####


def _source_closure(
  equation: MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationResult,
) -> MocReflectedDomainGlobalPhysicalClosureResult | None:
  if equation.source_closure is not None:
    return equation.source_closure
  ####
  if equation.request is not None:
    return equation.request.closure
  ####
  return None
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeCanonicalConsumerResult:
  """Composed research evidence with canonical promotion explicitly closed."""

  status: MocReflectedDomainGlobalMixedRegimeCanonicalConsumerStatus
  request: MocReflectedDomainGlobalMixedRegimeCanonicalConsumerRequest | None
  source_closure: MocReflectedDomainGlobalPhysicalClosureResult | None = None
  source_closure_fingerprint: str | None = None
  characteristic_compatibility_consumed: bool = False
  characteristic_compatibility_audit_verified: bool = False
  upstream_state_equation_consumed: bool = False
  upstream_state_equation_audit_verified: bool = False
  global_feedback_consumed: bool = False
  global_feedback_lineage_verified: bool = False
  research_consumption_verified: bool = False
  normal_closure_required: bool = True
  normal_closure_consumed: bool = False
  normal_closure_audit_verified: bool = False
  normal_closure_verified: bool = False
  canonical_free_boundary_verified: bool = False
  global_coupling_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  global_feedback: MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRun | None = None
  normal_closure: MocReflectedDomainGlobalMixedRegimeNormalClosureResult | None = None
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalMixedRegimeCanonicalConsumerStatus,
    ):
      raise TypeError('status must be a typed canonical-consumer status')
    ####
    if self.request is not None and not isinstance(
      self.request,
      MocReflectedDomainGlobalMixedRegimeCanonicalConsumerRequest,
    ):
      raise TypeError('request must be a typed canonical-consumer request')
    ####
    if self.source_closure is not None and not isinstance(
      self.source_closure,
      MocReflectedDomainGlobalPhysicalClosureResult,
    ):
      raise TypeError('source_closure must be a typed physical closure or None')
    ####
    if self.global_feedback is not None and not isinstance(
      self.global_feedback,
      MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRun,
    ):
      raise TypeError('global_feedback must be a typed feedback result or None')
    ####
    if self.normal_closure is not None and not isinstance(
      self.normal_closure,
      MocReflectedDomainGlobalMixedRegimeNormalClosureResult,
    ):
      raise TypeError('normal_closure must be a typed normal-closure result or None')
    ####
    for name in (
      'characteristic_compatibility_consumed',
      'characteristic_compatibility_audit_verified',
      'upstream_state_equation_consumed',
      'upstream_state_equation_audit_verified',
      'global_feedback_consumed',
      'global_feedback_lineage_verified',
      'research_consumption_verified',
      'normal_closure_required',
      'normal_closure_consumed',
      'normal_closure_audit_verified',
      'normal_closure_verified',
      'canonical_free_boundary_verified',
      'global_coupling_verified',
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
    if (
      self.canonical_free_boundary_verified
      or self.global_coupling_verified
    ):
      raise ValueError(
        'research canonical-consumer evidence cannot claim canonical/global closure'
      )
    ####
    if self.normal_closure_verified and (
      self.normal_closure is None
      or not self.normal_closure_consumed
      or not self.normal_closure_audit_verified
    ):
      raise ValueError(
        'normal_closure_verified requires an independently audited normal closure'
      )
    ####
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError('canonical-consumer evidence must remain promotion-blocked')
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    """Whether all supplied research evidence was consumed and replayed."""

    return bool(
      self.status
      in {
        MocReflectedDomainGlobalMixedRegimeCanonicalConsumerStatus
        .COMPLETED_RESEARCH_CANONICAL_CONSUMPTION_WITH_OPEN_CLOSURE,
        MocReflectedDomainGlobalMixedRegimeCanonicalConsumerStatus
        .COMPLETED_RESEARCH_CANONICAL_CONSUMPTION_WITH_OPEN_GLOBAL_CLOSURE,
      }
      and self.research_consumption_verified
      and self.normal_closure_required
      and (
        not self.request
        or not self.request.require_normal_closure
        or self.normal_closure_verified
      )
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_CANONICAL_CONSUMER_OPERATOR_ID,
      'status': self.status.value,
      'converged': self.converged,
      'source_closure_fingerprint': self.source_closure_fingerprint,
      'characteristic_compatibility_consumed': (
        self.characteristic_compatibility_consumed
      ),
      'characteristic_compatibility_audit_verified': (
        self.characteristic_compatibility_audit_verified
      ),
      'upstream_state_equation_consumed': self.upstream_state_equation_consumed,
      'upstream_state_equation_audit_verified': (
        self.upstream_state_equation_audit_verified
      ),
      'global_feedback_consumed': self.global_feedback_consumed,
      'global_feedback_lineage_verified': self.global_feedback_lineage_verified,
      'research_consumption_verified': self.research_consumption_verified,
      'normal_closure_required': self.normal_closure_required,
      'normal_closure_consumed': self.normal_closure_consumed,
      'normal_closure_audit_verified': self.normal_closure_audit_verified,
      'normal_closure_verified': self.normal_closure_verified,
      'canonical_free_boundary_verified': False,
      'global_coupling_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'source_closure': (
        None if self.source_closure is None else self.source_closure.as_report()
      ),
      'global_feedback': (
        None if self.global_feedback is None else self.global_feedback.as_report()
      ),
      'normal_closure': (
        None if self.normal_closure is None else self.normal_closure.as_report()
      ),
      'request': None if self.request is None else self.request.as_report(),
      'claim_status': (
        'research-only composed source evidence; the normal/free-boundary '
        'closure and global fixed point remain open'
      ),
      'message': self.message,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeCanonicalConsumerAudit:
  """Independent lower-lane replay and lineage audit."""

  status: MocReflectedDomainGlobalMixedRegimeCanonicalConsumerAuditStatus
  candidate: MocReflectedDomainGlobalMixedRegimeCanonicalConsumerResult | None
  compatibility_audit_verified: bool = False
  state_equation_audit_verified: bool = False
  source_lineage_replayed: bool = False
  global_feedback_lineage_replayed: bool = False
  normal_closure_lineage_replayed: bool = False
  normal_closure_audit_verified: bool = False
  independent_research_consumption_verified: bool = False
  canonical_free_boundary_verified: bool = False
  global_coupling_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalMixedRegimeCanonicalConsumerAuditStatus,
    ):
      raise TypeError('status must be a typed canonical-consumer audit status')
    ####
    if self.candidate is not None and not isinstance(
      self.candidate,
      MocReflectedDomainGlobalMixedRegimeCanonicalConsumerResult,
    ):
      raise TypeError('candidate must be a typed canonical-consumer result')
    ####
    for name in (
      'compatibility_audit_verified',
      'state_equation_audit_verified',
      'source_lineage_replayed',
      'global_feedback_lineage_replayed',
      'normal_closure_lineage_replayed',
      'normal_closure_audit_verified',
      'independent_research_consumption_verified',
      'canonical_free_boundary_verified',
      'global_coupling_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if self.canonical_free_boundary_verified or self.global_coupling_verified:
      raise ValueError('canonical-consumer audit cannot claim global closure')
    ####
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError('canonical-consumer audit must remain promotion-blocked')
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalMixedRegimeCanonicalConsumerAuditStatus
      .VERIFIED_RESEARCH_CANONICAL_CONSUMPTION
      and self.independent_research_consumption_verified
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_CANONICAL_CONSUMER_OPERATOR_ID,
      'audit_status': self.status.value,
      'converged': self.converged,
      'compatibility_audit_verified': self.compatibility_audit_verified,
      'state_equation_audit_verified': self.state_equation_audit_verified,
      'source_lineage_replayed': self.source_lineage_replayed,
      'global_feedback_lineage_replayed': self.global_feedback_lineage_replayed,
      'normal_closure_lineage_replayed': self.normal_closure_lineage_replayed,
      'normal_closure_audit_verified': self.normal_closure_audit_verified,
      'independent_research_consumption_verified': (
        self.independent_research_consumption_verified
      ),
      'canonical_free_boundary_verified': False,
      'global_coupling_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'candidate': None if self.candidate is None else self.candidate.as_report(),
      'message': self.message,
    }
  ####
####


def _failure(
  status: MocReflectedDomainGlobalMixedRegimeCanonicalConsumerStatus,
  message: str,
  *,
  request: MocReflectedDomainGlobalMixedRegimeCanonicalConsumerRequest | None = None,
  **values: Any,
) -> MocReflectedDomainGlobalMixedRegimeCanonicalConsumerResult:
  return MocReflectedDomainGlobalMixedRegimeCanonicalConsumerResult(
    status=status,
    request=request,
    message=message,
    **values,
  )
####


def consume_reflected_domain_global_mixed_regime_canonical_source(
  request: MocReflectedDomainGlobalMixedRegimeCanonicalConsumerRequest,
) -> MocReflectedDomainGlobalMixedRegimeCanonicalConsumerResult:
  """Compose exact research evidence without claiming canonical closure."""

  status_type = MocReflectedDomainGlobalMixedRegimeCanonicalConsumerStatus
  if not isinstance(
    request,
    MocReflectedDomainGlobalMixedRegimeCanonicalConsumerRequest,
  ):
    return _failure(
      status_type.INVALID_INPUT,
      'request must be a typed canonical-consumer request',
    )
  ####
  compatibility = request.characteristic_compatibility
  equation = request.upstream_state_equation
  chained_equation = _chain_state_equation(compatibility)
  if chained_equation is None:
    return _failure(
      status_type.CHARACTERISTIC_COMPATIBILITY_REQUIRED,
      'characteristic compatibility did not retain a complete interface/frame '
      'lineage to an upstream state equation',
      request=request,
    )
  ####
  if chained_equation is not equation:
    return _failure(
      status_type.SOURCE_LINEAGE_FAILURE,
      'the supplied state equation is not the exact equation retained by the '
      'characteristic compatibility request',
      request=request,
    )
  ####
  closure = _source_closure(equation)
  if closure is None or equation.request is None:
    return _failure(
      status_type.UPSTREAM_STATE_EQUATION_REQUIRED,
      'canonical consumption requires the exact state-equation request and '
      'source closure',
      request=request,
    )
  ####
  if not compatibility.converged or not compatibility.characteristic_compatibility_consumed:
    return _failure(
      status_type.CHARACTERISTIC_COMPATIBILITY_REQUIRED,
      'canonical consumption requires a converged incoming-family '
      'compatibility result; subsonic samples are not promoted',
      request=request,
      source_closure=closure,
      source_closure_fingerprint=moc_reflected_domain_global_physical_closure_fingerprint(
        closure
      ),
    )
  ####
  if not equation.converged or not equation.research_state_equation_consumed:
    return _failure(
      status_type.UPSTREAM_STATE_EQUATION_REQUIRED,
      'canonical consumption requires the exact conservative/entropy state '
      'equation to be consumed and locally converged',
      request=request,
      source_closure=closure,
      source_closure_fingerprint=moc_reflected_domain_global_physical_closure_fingerprint(
        closure
      ),
      characteristic_compatibility_consumed=True,
    )
  ####
  if not closure.converged or not closure.physical_closure_verified:
    return _failure(
      status_type.SOURCE_LINEAGE_FAILURE,
      'canonical consumption requires a locally verified physical source '
      'closure',
      request=request,
      source_closure=closure,
    )
  ####
  compatibility_audit = (
    audit_reflected_domain_global_mixed_regime_upstream_characteristic_compatibility(
      compatibility
    )
  )
  state_equation_audit = audit_reflected_domain_global_mixed_regime_upstream_state_equation(
    equation
  )
  if not compatibility_audit.converged or not state_equation_audit.converged:
    return _failure(
      status_type.AUDIT_REQUIRED,
      'canonical consumption requires independent replay of both the '
      'incoming-family compatibility and conservative/entropy state equation',
      request=request,
      source_closure=closure,
      source_closure_fingerprint=moc_reflected_domain_global_physical_closure_fingerprint(
        closure
      ),
      characteristic_compatibility_consumed=True,
      characteristic_compatibility_audit_verified=compatibility_audit.converged,
      upstream_state_equation_consumed=True,
      upstream_state_equation_audit_verified=state_equation_audit.converged,
    )
  ####
  feedback = request.global_feedback
  if request.require_global_feedback and feedback is None:
    return _failure(
      status_type.GLOBAL_FEEDBACK_REQUIRED,
      'canonical consumption requires a solver-owned global feedback result '
      'after exact characteristic/state-equation admission',
      request=request,
      source_closure=closure,
      source_closure_fingerprint=moc_reflected_domain_global_physical_closure_fingerprint(
        closure
      ),
      characteristic_compatibility_consumed=True,
      characteristic_compatibility_audit_verified=True,
      upstream_state_equation_consumed=True,
      upstream_state_equation_audit_verified=True,
    )
  ####
  feedback_lineage_verified = False
  if feedback is not None:
    feedback_lineage_verified = bool(
      moc_reflected_domain_global_physical_closure_fingerprint(
        feedback.source_closure
      )
      == moc_reflected_domain_global_physical_closure_fingerprint(closure)
      and feedback.chain_promotion_blocked
      and not feedback.production_claim_allowed
    )
    if not feedback_lineage_verified:
      return _failure(
        status_type.SOURCE_LINEAGE_FAILURE,
        'global feedback source closure or fidelity flags do not match the '
        'exact upstream source',
        request=request,
        source_closure=closure,
        source_closure_fingerprint=moc_reflected_domain_global_physical_closure_fingerprint(
          closure
        ),
        characteristic_compatibility_consumed=True,
        characteristic_compatibility_audit_verified=True,
        upstream_state_equation_consumed=True,
        upstream_state_equation_audit_verified=True,
        global_feedback=feedback,
      )
    ####
    if not feedback.research_feedback_completed:
      return _failure(
        status_type.GLOBAL_FEEDBACK_FAILURE,
        'global feedback did not complete its declared research contract',
        request=request,
        source_closure=closure,
        source_closure_fingerprint=moc_reflected_domain_global_physical_closure_fingerprint(
          closure
        ),
        characteristic_compatibility_consumed=True,
        characteristic_compatibility_audit_verified=True,
        upstream_state_equation_consumed=True,
        upstream_state_equation_audit_verified=True,
        global_feedback_consumed=True,
        global_feedback_lineage_verified=True,
        global_feedback=feedback,
      )
    ####
    if (
      request.require_terminal_global_downstream_recheck
      and not feedback.terminal_global_downstream_recheck_required
    ):
      return _failure(
        status_type.GLOBAL_FEEDBACK_FAILURE,
        'canonical consumption requires the global-downstream recheck mode '
        'to be explicitly requested by the feedback run',
        request=request,
        source_closure=closure,
        source_closure_fingerprint=moc_reflected_domain_global_physical_closure_fingerprint(
          closure
        ),
        characteristic_compatibility_consumed=True,
        characteristic_compatibility_audit_verified=True,
        upstream_state_equation_consumed=True,
        upstream_state_equation_audit_verified=True,
        global_feedback_consumed=True,
        global_feedback_lineage_verified=True,
        global_feedback=feedback,
      )
    ####
  ####
  if feedback is None and not request.require_global_feedback:
    return _failure(
      status_type.GLOBAL_FEEDBACK_REQUIRED,
      'this composition contract does not permit canonical consumption without '
      'a retained global-feedback result',
      request=request,
    )
  ####
  normal_closure = request.normal_closure
  normal_closure_audit = request.normal_closure_audit
  normal_closure_consumed = False
  normal_closure_audit_verified = False
  normal_closure_verified = False
  if normal_closure is None:
    if request.require_normal_closure:
      return _failure(
        status_type.NORMAL_CLOSURE_REQUIRED,
        'canonical consumption requires an independently audited local normal '
        'closure when require_normal_closure is enabled',
        request=request,
        source_closure=closure,
        source_closure_fingerprint=(
          moc_reflected_domain_global_physical_closure_fingerprint(closure)
        ),
        characteristic_compatibility_consumed=True,
        characteristic_compatibility_audit_verified=True,
        upstream_state_equation_consumed=True,
        upstream_state_equation_audit_verified=True,
        global_feedback_consumed=feedback is not None,
        global_feedback_lineage_verified=feedback_lineage_verified,
        global_feedback=feedback,
      )
    ####
  else:
    if not normal_closure.converged:
      return _failure(
        status_type.NORMAL_CLOSURE_REQUIRED,
        'supplied normal closure did not converge its two-sided component and '
        'entropy gates',
        request=request,
        source_closure=closure,
        source_closure_fingerprint=(
          moc_reflected_domain_global_physical_closure_fingerprint(closure)
        ),
        characteristic_compatibility_consumed=True,
        characteristic_compatibility_audit_verified=True,
        upstream_state_equation_consumed=True,
        upstream_state_equation_audit_verified=True,
        global_feedback_consumed=feedback is not None,
        global_feedback_lineage_verified=feedback_lineage_verified,
        global_feedback=feedback,
        normal_closure=normal_closure,
      )
    ####
    if normal_closure_audit is None or not normal_closure_audit.converged:
      return _failure(
        status_type.AUDIT_REQUIRED,
        'canonical consumption requires an independent normal-closure replay '
        'when normal-closure evidence is supplied',
        request=request,
        source_closure=closure,
        source_closure_fingerprint=(
          moc_reflected_domain_global_physical_closure_fingerprint(closure)
        ),
        characteristic_compatibility_consumed=True,
        characteristic_compatibility_audit_verified=True,
        upstream_state_equation_consumed=True,
        upstream_state_equation_audit_verified=True,
        global_feedback_consumed=feedback is not None,
        global_feedback_lineage_verified=feedback_lineage_verified,
        global_feedback=feedback,
        normal_closure=normal_closure,
        normal_closure_consumed=True,
      )
    ####
    normal_request = normal_closure.request
    normal_lineage = bool(
      normal_request is not None
      and normal_request.characteristic_compatibility is compatibility
      and normal_request.characteristic_compatibility_audit is not None
      and normal_request.characteristic_compatibility_audit.candidate
      is compatibility
      and normal_closure_audit.candidate is normal_closure
    )
    if not normal_lineage:
      return _failure(
        status_type.SOURCE_LINEAGE_FAILURE,
        'normal closure must retain the exact characteristic compatibility '
        'chain supplied to the canonical consumer',
        request=request,
        source_closure=closure,
        source_closure_fingerprint=(
          moc_reflected_domain_global_physical_closure_fingerprint(closure)
        ),
        characteristic_compatibility_consumed=True,
        characteristic_compatibility_audit_verified=True,
        upstream_state_equation_consumed=True,
        upstream_state_equation_audit_verified=True,
        global_feedback_consumed=feedback is not None,
        global_feedback_lineage_verified=feedback_lineage_verified,
        global_feedback=feedback,
        normal_closure=normal_closure,
        normal_closure_consumed=True,
        normal_closure_audit_verified=normal_closure_audit.converged,
      )
    ####
    normal_closure_consumed = True
    normal_closure_audit_verified = True
    normal_closure_verified = True
  ####
  final_status = (
    status_type.COMPLETED_RESEARCH_CANONICAL_CONSUMPTION_WITH_OPEN_GLOBAL_CLOSURE
    if normal_closure_verified
    else status_type.COMPLETED_RESEARCH_CANONICAL_CONSUMPTION_WITH_OPEN_CLOSURE
  )
  return MocReflectedDomainGlobalMixedRegimeCanonicalConsumerResult(
    status=final_status,
    request=request,
    source_closure=closure,
    source_closure_fingerprint=moc_reflected_domain_global_physical_closure_fingerprint(
      closure
    ),
    characteristic_compatibility_consumed=True,
    characteristic_compatibility_audit_verified=True,
    upstream_state_equation_consumed=True,
    upstream_state_equation_audit_verified=True,
    global_feedback_consumed=feedback is not None,
    global_feedback_lineage_verified=feedback_lineage_verified,
    research_consumption_verified=True,
    normal_closure_required=True,
    normal_closure_consumed=normal_closure_consumed,
    normal_closure_audit_verified=normal_closure_audit_verified,
    normal_closure_verified=normal_closure_verified,
    canonical_free_boundary_verified=False,
    global_coupling_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    global_feedback=feedback,
    normal_closure=normal_closure,
    message=(
      'exact incoming-family compatibility, conservative/entropy state '
      'equation, and audited global-feedback evidence were composed; '
      + (
        'the independently audited local normal closure is consumed; the '
        'canonical global fixed point remains open'
        if normal_closure_verified
        else 'normal closure and the canonical global fixed point remain open'
      )
    ),
  )
####


def audit_reflected_domain_global_mixed_regime_canonical_source(
  result: MocReflectedDomainGlobalMixedRegimeCanonicalConsumerResult,
) -> MocReflectedDomainGlobalMixedRegimeCanonicalConsumerAudit:
  """Replay the lower research contracts and exact source lineage."""

  audit_status = MocReflectedDomainGlobalMixedRegimeCanonicalConsumerAuditStatus
  if not isinstance(
    result,
    MocReflectedDomainGlobalMixedRegimeCanonicalConsumerResult,
  ):
    return MocReflectedDomainGlobalMixedRegimeCanonicalConsumerAudit(
      status=audit_status.INVALID_INPUT,
      candidate=None,
      message='result must be a typed canonical-consumer result',
    )
  ####
  request = result.request
  if request is None:
    return MocReflectedDomainGlobalMixedRegimeCanonicalConsumerAudit(
      status=audit_status.REPLAY_FAILURE,
      candidate=result,
      message='canonical-consumer audit requires the exact request',
    )
  ####
  compatibility_audit = (
    audit_reflected_domain_global_mixed_regime_upstream_characteristic_compatibility(
      request.characteristic_compatibility
    )
  )
  state_equation_audit = audit_reflected_domain_global_mixed_regime_upstream_state_equation(
    request.upstream_state_equation
  )
  compatibility_verified = compatibility_audit.converged
  state_equation_verified = state_equation_audit.converged
  source = _source_closure(request.upstream_state_equation)
  source_lineage = bool(
    source is not None
    and result.source_closure is source
    and result.source_closure_fingerprint
    == moc_reflected_domain_global_physical_closure_fingerprint(source)
  )
  feedback_lineage = bool(
    request.global_feedback is result.global_feedback
    and (
      request.global_feedback is None
      or result.global_feedback_lineage_verified
    )
  )
  normal_closure_lineage = bool(
    request.normal_closure is result.normal_closure
    and (
      request.normal_closure is None
      or (
        result.normal_closure_consumed
        and request.normal_closure_audit is not None
        and request.normal_closure_audit.candidate is request.normal_closure
        and request.normal_closure_audit.converged
      )
    )
  )
  normal_closure_audit_verified = False
  if result.normal_closure is None:
    normal_closure_audit_verified = not result.normal_closure_verified
  else:
    replay_normal_closure_audit = (
      audit_reflected_domain_global_mixed_regime_normal_closure(
        result.normal_closure
      )
    )
    normal_closure_audit_verified = bool(
      replay_normal_closure_audit.converged
      and result.normal_closure_audit_verified
      and result.normal_closure_verified
    )
  ####
  independent = bool(
    result.converged
    and compatibility_verified
    and state_equation_verified
    and source_lineage
    and feedback_lineage
    and normal_closure_lineage
    and normal_closure_audit_verified
    and result.characteristic_compatibility_consumed
    and result.upstream_state_equation_consumed
    and result.global_feedback_consumed
  )
  return MocReflectedDomainGlobalMixedRegimeCanonicalConsumerAudit(
    status=(
      audit_status.VERIFIED_RESEARCH_CANONICAL_CONSUMPTION
      if independent
      else audit_status.LINEAGE_FAILURE
    ),
    candidate=result,
    compatibility_audit_verified=compatibility_verified,
    state_equation_audit_verified=state_equation_verified,
    source_lineage_replayed=source_lineage,
    global_feedback_lineage_replayed=feedback_lineage,
    normal_closure_lineage_replayed=normal_closure_lineage,
    normal_closure_audit_verified=normal_closure_audit_verified,
    independent_research_consumption_verified=independent,
    canonical_free_boundary_verified=False,
    global_coupling_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    message=(
      'independent lower-lane replays and exact source lineage reproduced the '
      'composed research consumption boundary'
      if independent
      else 'one or more lower-lane replays or source-lineage checks failed'
    ),
  )
####
