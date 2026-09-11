"""Bounded global/downstream frontier feedback iterations.

The downstream coupled lane already exposes an independently measured
frontier response, and the target-guided global lane can fresh-solve a finite
candidate family against that response.  This module composes those two
operators into one repeatable outer iteration:

``global closure -> downstream response -> exact frontier proposal -> fresh
global candidate closure``.

The result is intentionally a research evidence object.  It proves that the
exact target was carried through a fresh global re-solve, but it does not
claim that the canonical mixed-regime/free-boundary equations have reached a
fixed point, that refinement is stable, or that a shock-cell chain is ready
for production.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from math import isfinite
from typing import Any

from exhaust_plume.models.moc.global_frontier_reconciliation import (
  MocReflectedDomainGlobalFrontierReconciliationRequest,
  build_reflected_domain_global_frontier_reconciliation_request,
  moc_reflected_domain_global_frontier_proposal_fingerprint,
)
from exhaust_plume.models.moc.global_coupled_downstream import (
  MocReflectedDomainGlobalCoupledDownstreamUpstreamFeedbackProposal,
)
from exhaust_plume.models.moc.global_physical_closure import (
  MocReflectedDomainGlobalPhysicalClosureResult,
  moc_reflected_domain_global_physical_closure_fingerprint,
)
from exhaust_plume.validation.moc_global_coupled_downstream_feedback import (
  MocReflectedDomainGlobalCoupledDownstreamFeedbackRun,
  run_reflected_domain_global_coupled_downstream_feedback,
)
from exhaust_plume.validation.moc_global_frontier_target_resolve import (
  MocReflectedDomainGlobalFrontierTargetResolveResult,
  run_reflected_domain_global_frontier_target_guided_resolve,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_FRONTIER_FEEDBACK_OPERATOR_ID',
  'MocReflectedDomainGlobalCoupledFrontierFeedbackStatus',
  'MocReflectedDomainGlobalCoupledFrontierFeedbackIteration',
  'MocReflectedDomainGlobalCoupledFrontierFeedbackRun',
  'MocReflectedDomainGlobalCoupledFrontierFeedbackAuditStatus',
  'MocReflectedDomainGlobalCoupledFrontierFeedbackAudit',
  'audit_reflected_domain_global_coupled_frontier_feedback',
  'run_reflected_domain_global_coupled_frontier_feedback',
)


MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_FRONTIER_FEEDBACK_OPERATOR_ID = (
  'op.moc.reflected-domain.global-coupled-frontier-feedback'
)


class MocReflectedDomainGlobalCoupledFrontierFeedbackStatus(str, Enum):
  """Outcome of the bounded global/downstream frontier feedback runner."""

  COMPLETED_RESEARCH_GLOBAL_FRONTIER_FEEDBACK = (
    'completed-research-global-frontier-feedback'
  )
  INVALID_INPUT = 'invalid_input'
  DOWNSTREAM_FEEDBACK_FAILURE = 'global-frontier-downstream-feedback-failure'
  FRONTIER_REQUEST_FAILURE = 'global-frontier-request-failure'
  TARGET_RESOLVE_FAILURE = 'global-frontier-target-resolve-failure'
  FIDELITY_FAILURE = 'global-frontier-fidelity-isolation-failure'
  ITERATION_LIMIT = 'global-frontier-feedback-iteration-limit'
####


class MocReflectedDomainGlobalCoupledFrontierFeedbackAuditStatus(str, Enum):
  """Outcome of independently rechecking a retained frontier feedback run."""

  AUDITED_RESEARCH_EVIDENCE = (
    'audited-research-global-coupled-frontier-feedback'
  )
  INVALID_INPUT = 'invalid_input'
  ITERATION_LINEAGE_FAILURE = (
    'global-frontier-feedback-audit-iteration-lineage-failure'
  )
  DOWNSTREAM_LINEAGE_FAILURE = (
    'global-frontier-feedback-audit-downstream-lineage-failure'
  )
  TARGET_REQUEST_FAILURE = (
    'global-frontier-feedback-audit-target-request-failure'
  )
  TARGET_RESOLVE_FAILURE = (
    'global-frontier-feedback-audit-target-resolve-failure'
  )
  TARGET_MATCH_FAILURE = (
    'global-frontier-feedback-audit-target-match-failure'
  )
  AGGREGATE_FLAG_FAILURE = (
    'global-frontier-feedback-audit-aggregate-flag-failure'
  )
  PROMOTION_FLAG_FAILURE = (
    'global-frontier-feedback-audit-promotion-flag-failure'
  )


def _options(
  value: Mapping[str, Any] | None,
  name: str,
  *,
  reserved: tuple[str, ...],
) -> dict[str, Any]:
  if value is None:
    return {}
  ####
  if not isinstance(value, Mapping):
    raise TypeError(f'{name} must be a mapping when supplied')
  ####
  resolved = dict(value)
  collisions = tuple(key for key in reserved if key in resolved)
  if collisions:
    raise ValueError(
      f'{name} cannot override positional controls: {", ".join(collisions)}'
    )
  ####
  return resolved
####


def _configuration_fingerprint(configuration: Mapping[str, Any]) -> str:
  serialized = json.dumps(
    dict(configuration),
    sort_keys=True,
    separators=(',', ':'),
    ensure_ascii=True,
    default=str,
  )
  return sha256(serialized.encode('utf-8')).hexdigest()
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalCoupledFrontierFeedbackIteration:
  """One downstream-response and fresh-global-resolve feedback step."""

  iteration_index: int
  source_closure: MocReflectedDomainGlobalPhysicalClosureResult
  downstream_feedback: MocReflectedDomainGlobalCoupledDownstreamFeedbackRun | None
  proposal: (
    MocReflectedDomainGlobalCoupledDownstreamUpstreamFeedbackProposal | None
  )
  frontier_request: MocReflectedDomainGlobalFrontierReconciliationRequest | None
  target_resolve: MocReflectedDomainGlobalFrontierTargetResolveResult | None
  selected_closure: MocReflectedDomainGlobalPhysicalClosureResult | None
  downstream_feedback_verified: bool = False
  source_lineage_verified: bool = False
  target_lineage_verified: bool = False
  fresh_global_solve_verified: bool = False
  target_consumption_verified: bool = False
  target_match_verified: bool = False
  fidelity_isolation_verified: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if (
      isinstance(self.iteration_index, bool)
      or not isinstance(self.iteration_index, int)
      or self.iteration_index < 0
    ):
      raise ValueError('iteration_index must be a nonnegative integer')
    ####
    if not isinstance(
      self.source_closure,
      MocReflectedDomainGlobalPhysicalClosureResult,
    ):
      raise TypeError(
        'source_closure must be a '
        'MocReflectedDomainGlobalPhysicalClosureResult'
      )
    ####
    if self.downstream_feedback is not None and not isinstance(
      self.downstream_feedback,
      MocReflectedDomainGlobalCoupledDownstreamFeedbackRun,
    ):
      raise TypeError(
        'downstream_feedback must be a '
        'MocReflectedDomainGlobalCoupledDownstreamFeedbackRun or None'
      )
    ####
    if self.frontier_request is not None and not isinstance(
      self.frontier_request,
      MocReflectedDomainGlobalFrontierReconciliationRequest,
    ):
      raise TypeError(
        'frontier_request must be a '
        'MocReflectedDomainGlobalFrontierReconciliationRequest or None'
      )
    ####
    if self.target_resolve is not None and not isinstance(
      self.target_resolve,
      MocReflectedDomainGlobalFrontierTargetResolveResult,
    ):
      raise TypeError(
        'target_resolve must be a '
        'MocReflectedDomainGlobalFrontierTargetResolveResult or None'
      )
    ####
    if self.selected_closure is not None and not isinstance(
      self.selected_closure,
      MocReflectedDomainGlobalPhysicalClosureResult,
    ):
      raise TypeError(
        'selected_closure must be a '
        'MocReflectedDomainGlobalPhysicalClosureResult or None'
      )
    ####
    for name in (
      'downstream_feedback_verified',
      'source_lineage_verified',
      'target_lineage_verified',
      'fresh_global_solve_verified',
      'target_consumption_verified',
      'target_match_verified',
      'fidelity_isolation_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if self.target_match_verified and self.selected_closure is None:
      raise ValueError(
        'target_match_verified requires a selected fresh global closure'
      )
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def source_closure_fingerprint(self) -> str:
    return moc_reflected_domain_global_physical_closure_fingerprint(
      self.source_closure
    )
  ####

  @property
  def selected_closure_fingerprint(self) -> str | None:
    return (
      None
      if self.selected_closure is None
      else moc_reflected_domain_global_physical_closure_fingerprint(
        self.selected_closure
      )
    )
  ####

  @property
  def research_step_verified(self) -> bool:
    """Whether this step completed an exact, non-promoted target handoff."""

    return bool(
      self.downstream_feedback_verified
      and self.source_lineage_verified
      and self.target_lineage_verified
      and self.fresh_global_solve_verified
      and self.target_consumption_verified
      and self.target_match_verified
      and self.fidelity_isolation_verified
      and self.selected_closure is not None
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'iteration_index': self.iteration_index,
      'source_closure_fingerprint': self.source_closure_fingerprint,
      'selected_closure_fingerprint': self.selected_closure_fingerprint,
      'downstream_feedback_verified': self.downstream_feedback_verified,
      'source_lineage_verified': self.source_lineage_verified,
      'target_lineage_verified': self.target_lineage_verified,
      'fresh_global_solve_verified': self.fresh_global_solve_verified,
      'target_consumption_verified': self.target_consumption_verified,
      'target_match_verified': self.target_match_verified,
      'fidelity_isolation_verified': self.fidelity_isolation_verified,
      'research_step_verified': self.research_step_verified,
      'proposal': (
        None
        if self.proposal is None
        else self.proposal.as_report()
      ),
      'frontier_request': (
        None
        if self.frontier_request is None
        else self.frontier_request.as_report()
      ),
      'downstream_feedback': (
        None
        if self.downstream_feedback is None
        else self.downstream_feedback.as_report()
      ),
      'target_resolve': (
        None
        if self.target_resolve is None
        else self.target_resolve.as_report()
      ),
      'message': self.message,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalCoupledFrontierFeedbackRun:
  """Audited outer feedback steps below the canonical promotion gate."""

  source_closure: MocReflectedDomainGlobalPhysicalClosureResult
  final_closure: MocReflectedDomainGlobalPhysicalClosureResult
  requested_iterations: int
  iterations: tuple[MocReflectedDomainGlobalCoupledFrontierFeedbackIteration, ...]
  status: MocReflectedDomainGlobalCoupledFrontierFeedbackStatus
  configuration: dict[str, Any]
  configuration_fingerprint: str
  downstream_feedback_verified: bool = False
  source_lineage_verified: bool = False
  target_lineage_verified: bool = False
  fresh_global_solve_verified: bool = False
  target_consumption_verified: bool = False
  target_match_verified: bool = False
  fidelity_isolation_verified: bool = False
  global_coupling_verified: bool = False
  downstream_boundary_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    for name in ('source_closure', 'final_closure'):
      if not isinstance(
        getattr(self, name),
        MocReflectedDomainGlobalPhysicalClosureResult,
      ):
        raise TypeError(
          f'{name} must be a '
          'MocReflectedDomainGlobalPhysicalClosureResult'
        )
      ####
    ####
    if (
      isinstance(self.requested_iterations, bool)
      or not isinstance(self.requested_iterations, int)
      or self.requested_iterations < 1
    ):
      raise ValueError('requested_iterations must be a positive integer')
    ####
    iterations = tuple(self.iterations)
    if any(
      not isinstance(
        iteration,
        MocReflectedDomainGlobalCoupledFrontierFeedbackIteration,
      )
      for iteration in iterations
    ):
      raise TypeError(
        'iterations must contain '
        'MocReflectedDomainGlobalCoupledFrontierFeedbackIteration values'
      )
    ####
    if len(iterations) > self.requested_iterations:
      raise ValueError('iterations cannot exceed requested_iterations')
    ####
    if tuple(item.iteration_index for item in iterations) != tuple(
      range(len(iterations))
    ):
      raise ValueError('iterations must have contiguous zero-based indices')
    ####
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalCoupledFrontierFeedbackStatus,
    ):
      raise TypeError(
        'status must be a '
        'MocReflectedDomainGlobalCoupledFrontierFeedbackStatus'
      )
    ####
    for name in (
      'downstream_feedback_verified',
      'source_lineage_verified',
      'target_lineage_verified',
      'fresh_global_solve_verified',
      'target_consumption_verified',
      'target_match_verified',
      'fidelity_isolation_verified',
      'global_coupling_verified',
      'downstream_boundary_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if self.global_coupling_verified or self.downstream_boundary_closure_verified:
      raise ValueError(
        'bounded frontier feedback cannot claim canonical global closure'
      )
    ####
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError(
        'bounded frontier feedback must remain blocked from production'
      )
    ####
    object.__setattr__(self, 'iterations', iterations)
    object.__setattr__(self, 'configuration', dict(self.configuration))
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def research_feedback_completed(self) -> bool:
    """Whether every requested outer step completed its exact target handoff."""

    return bool(
      self.status
      is MocReflectedDomainGlobalCoupledFrontierFeedbackStatus
      .COMPLETED_RESEARCH_GLOBAL_FRONTIER_FEEDBACK
      and len(self.iterations) == self.requested_iterations
      and self.downstream_feedback_verified
      and self.source_lineage_verified
      and self.target_lineage_verified
      and self.fresh_global_solve_verified
      and self.target_consumption_verified
      and self.target_match_verified
      and self.fidelity_isolation_verified
      and all(iteration.research_step_verified for iteration in self.iterations)
    )
  ####

  @property
  def converged(self) -> bool:
    """Alias for local research completion, never for canonical closure."""

    return self.research_feedback_completed
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_FRONTIER_FEEDBACK_OPERATOR_ID,
      'status': self.status.value,
      'research_feedback_completed': self.research_feedback_completed,
      'converged': self.converged,
      'requested_iterations': self.requested_iterations,
      'iteration_count': len(self.iterations),
      'source_closure_fingerprint': moc_reflected_domain_global_physical_closure_fingerprint(
        self.source_closure
      ),
      'final_closure_fingerprint': moc_reflected_domain_global_physical_closure_fingerprint(
        self.final_closure
      ),
      'downstream_feedback_verified': self.downstream_feedback_verified,
      'source_lineage_verified': self.source_lineage_verified,
      'target_lineage_verified': self.target_lineage_verified,
      'fresh_global_solve_verified': self.fresh_global_solve_verified,
      'target_consumption_verified': self.target_consumption_verified,
      'target_match_verified': self.target_match_verified,
      'fidelity_isolation_verified': self.fidelity_isolation_verified,
      'global_coupling_verified': self.global_coupling_verified,
      'downstream_boundary_closure_verified': (
        self.downstream_boundary_closure_verified
      ),
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'configuration': self.configuration,
      'configuration_fingerprint': self.configuration_fingerprint,
      'iterations': tuple(iteration.as_report() for iteration in self.iterations),
      'final_closure': self.final_closure.as_report(),
      'message': self.message,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalCoupledFrontierFeedbackAudit:
  """Independent evidence for one retained global frontier handoff.

  The runner records its own seam flags while it executes.  This audit is a
  second pass over the immutable handoff objects: it checks the source chain,
  exact proposal/request identity, fresh target-resolve lineage, aggregate
  flags, and the explicit research-only boundary.  It does not rerun the
  global equations and cannot promote the compression-envelope law.
  """

  status: MocReflectedDomainGlobalCoupledFrontierFeedbackAuditStatus
  candidate: MocReflectedDomainGlobalCoupledFrontierFeedbackRun | None
  iterations_rechecked: int = 0
  configuration_verified: bool = False
  iteration_index_verified: bool = False
  source_chain_lineage_verified: bool = False
  downstream_lineage_verified: bool = False
  target_request_lineage_verified: bool = False
  target_resolve_lineage_verified: bool = False
  fresh_global_solve_verified: bool = False
  target_consumption_verified: bool = False
  target_match_verified: bool = False
  iteration_flags_verified: bool = False
  aggregate_flags_verified: bool = False
  promotion_flags_verified: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalCoupledFrontierFeedbackAuditStatus,
    ):
      raise TypeError('status must be a typed frontier-feedback audit status')
    if self.candidate is not None and not isinstance(
      self.candidate,
      MocReflectedDomainGlobalCoupledFrontierFeedbackRun,
    ):
      raise TypeError('candidate must be a typed frontier-feedback run or None')
    if (
      isinstance(self.iterations_rechecked, bool)
      or not isinstance(self.iterations_rechecked, int)
      or self.iterations_rechecked < 0
    ):
      raise ValueError('iterations_rechecked must be a nonnegative integer')
    for name in (
      'configuration_verified',
      'iteration_index_verified',
      'source_chain_lineage_verified',
      'downstream_lineage_verified',
      'target_request_lineage_verified',
      'target_resolve_lineage_verified',
      'fresh_global_solve_verified',
      'target_consumption_verified',
      'target_match_verified',
      'iteration_flags_verified',
      'aggregate_flags_verified',
      'promotion_flags_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    if self.candidate is not None and self.candidate.production_claim_allowed:
      raise ValueError('frontier-feedback audit cannot accept production claims')
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status is (
      MocReflectedDomainGlobalCoupledFrontierFeedbackAuditStatus
      .AUDITED_RESEARCH_EVIDENCE
    )
  ####

  @property
  def research_evidence_verified(self) -> bool:
    """Whether the retained frontier handoff passed the second-pass audit."""

    candidate = self.candidate
    return bool(
      self.converged
      and candidate is not None
      and candidate.research_feedback_completed
      and self.configuration_verified
      and self.iteration_index_verified
      and self.source_chain_lineage_verified
      and self.downstream_lineage_verified
      and self.target_request_lineage_verified
      and self.target_resolve_lineage_verified
      and self.fresh_global_solve_verified
      and self.target_consumption_verified
      and self.target_match_verified
      and self.iteration_flags_verified
      and self.aggregate_flags_verified
      and self.promotion_flags_verified
      and candidate.chain_promotion_blocked
      and not candidate.global_coupling_verified
      and not candidate.downstream_boundary_closure_verified
      and not candidate.production_claim_allowed
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_FRONTIER_FEEDBACK_OPERATOR_ID,
      'status': self.status.value,
      'converged': self.converged,
      'research_evidence_verified': self.research_evidence_verified,
      'iterations_rechecked': self.iterations_rechecked,
      'configuration_verified': self.configuration_verified,
      'iteration_index_verified': self.iteration_index_verified,
      'source_chain_lineage_verified': self.source_chain_lineage_verified,
      'downstream_lineage_verified': self.downstream_lineage_verified,
      'target_request_lineage_verified': self.target_request_lineage_verified,
      'target_resolve_lineage_verified': self.target_resolve_lineage_verified,
      'fresh_global_solve_verified': self.fresh_global_solve_verified,
      'target_consumption_verified': self.target_consumption_verified,
      'target_match_verified': self.target_match_verified,
      'iteration_flags_verified': self.iteration_flags_verified,
      'aggregate_flags_verified': self.aggregate_flags_verified,
      'promotion_flags_verified': self.promotion_flags_verified,
      'candidate': (
        None if self.candidate is None else self.candidate.as_report()
      ),
      'claim_status': (
        'independent research handoff audit only; canonical mixed-regime '
        'closure, physical shock-cell fitting, external validation, and '
        'production claims remain blocked'
      ),
      'message': self.message,
    }
  ####
####


def audit_reflected_domain_global_coupled_frontier_feedback(
  candidate: MocReflectedDomainGlobalCoupledFrontierFeedbackRun,
) -> MocReflectedDomainGlobalCoupledFrontierFeedbackAudit:
  """Independently recheck one retained global/downstream feedback run."""

  audit_status = MocReflectedDomainGlobalCoupledFrontierFeedbackAuditStatus
  if not isinstance(
    candidate,
    MocReflectedDomainGlobalCoupledFrontierFeedbackRun,
  ):
    return MocReflectedDomainGlobalCoupledFrontierFeedbackAudit(
      status=audit_status.INVALID_INPUT,
      candidate=None,
      message='candidate must be a typed global frontier feedback run',
    )
  ####

  iterations = tuple(candidate.iterations)
  configuration_verified = bool(
    candidate.configuration_fingerprint
    == _configuration_fingerprint(candidate.configuration)
  )
  iteration_index_verified = bool(
    iterations
    and len(iterations) == candidate.requested_iterations
    and tuple(item.iteration_index for item in iterations)
    == tuple(range(len(iterations)))
  )
  source_chain_lineage_verified = True
  downstream_lineage_verified = True
  target_request_lineage_verified = True
  target_resolve_lineage_verified = True
  fresh_global_solve_verified = True
  target_consumption_verified = True
  target_match_verified = True
  iteration_flags_verified = True
  promotion_flags_verified = True

  independent_steps: list[bool] = []
  selected_closures: list[MocReflectedDomainGlobalPhysicalClosureResult] = []
  for index, item in enumerate(iterations):
    expected_source = (
      candidate.source_closure
      if index == 0
      else iterations[index - 1].selected_closure
    )
    source_fingerprint = moc_reflected_domain_global_physical_closure_fingerprint(
      item.source_closure
    )
    expected_source_fingerprint = (
      None
      if expected_source is None
      else moc_reflected_domain_global_physical_closure_fingerprint(
        expected_source
      )
    )
    source_ok = bool(
      expected_source is not None
      and item.source_closure is expected_source
      and source_fingerprint == expected_source_fingerprint
    )
    source_chain_lineage_verified = bool(
      source_chain_lineage_verified and source_ok
    )

    downstream = item.downstream_feedback
    proposal = item.proposal
    proposals = () if downstream is None else downstream.upstream_feedback_proposals
    downstream_ok = bool(
      downstream is not None
      and downstream.closure is item.source_closure
      and downstream.closure_lineage_verified
      and downstream.fresh_solver_invocation_verified
      and downstream.upstream_feedback_proposal_verified
      and proposal is not None
      and proposals
      and proposals[-1] is proposal
      and proposal.ready_for_global_resolve
      and proposal.source_closure_fingerprint == source_fingerprint
      and not proposal.consumed_by_global_solver
    )
    downstream_lineage_verified = bool(
      downstream_lineage_verified and downstream_ok
    )

    request = item.frontier_request
    proposal_fingerprint = (
      None
      if proposal is None
      else moc_reflected_domain_global_frontier_proposal_fingerprint(proposal)
    )
    request_ok = bool(
      request is not None
      and proposal is not None
      and request.proposal is proposal
      and request.lineage_verified
      and request.global_resolve_required
      and request.source_closure_fingerprint == source_fingerprint
      and request.source_proposal_fingerprint == proposal_fingerprint
      and request.target_x_stations_m == proposal.matched_x_stations_m
      and request.target_boundary_points_m == proposal.proposed_boundary_points_m
      and request.target_tangent_rad == proposal.proposed_tangent_rad
      and request.target_static_pressure_Pa
      == proposal.proposed_static_pressure_Pa
    )
    target_request_lineage_verified = bool(
      target_request_lineage_verified and request_ok
    )

    target_resolve = item.target_resolve
    selected = None if target_resolve is None else target_resolve.selected_candidate
    selected_closure = None if selected is None else selected.closure
    target_resolve_ok = bool(
      target_resolve is not None
      and request is not None
      and target_resolve.request is request
      and target_resolve.source_closure is item.source_closure
      and target_resolve.target_lineage_verified
      and target_resolve.source_closure
      and moc_reflected_domain_global_physical_closure_fingerprint(
        target_resolve.source_closure
      )
      == source_fingerprint
    )
    target_resolve_lineage_verified = bool(
      target_resolve_lineage_verified and target_resolve_ok
    )
    fresh_ok = bool(
      target_resolve_ok
      and target_resolve is not None
      and target_resolve.fresh_global_solve_invocation_verified
      and selected is not None
      and selected.fresh_global_solve_attempted
      and selected_closure is item.selected_closure
      and selected_closure is not None
      and selected_closure is not item.source_closure
    )
    fresh_global_solve_verified = bool(
      fresh_global_solve_verified and fresh_ok
    )
    consumption_ok = bool(
      target_resolve_ok
      and target_resolve is not None
      and target_resolve.target_consumption_verified
      and target_resolve.target_coverage_verified
      and selected is not None
      and selected.target_coverage_verified
      and selected.target_residuals_finite
    )
    target_consumption_verified = bool(
      target_consumption_verified and consumption_ok
    )
    match_ok = bool(
      consumption_ok
      and target_resolve is not None
      and target_resolve.target_match_verified
      and selected is not None
      and selected.target_match_verified
      and item.selected_closure is selected.closure
    )
    target_match_verified = bool(target_match_verified and match_ok)

    fidelity_ok = bool(
      downstream_ok
      and target_resolve is not None
      and not target_resolve.global_coupling_verified
      and not target_resolve.downstream_boundary_closure_verified
      and target_resolve.chain_promotion_blocked
      and not target_resolve.production_claim_allowed
      and (
        selected_closure is None
        or not selected_closure.production_claim_allowed
      )
    )
    step_ok = bool(
      downstream_ok
      and source_ok
      and target_resolve_ok
      and fresh_ok
      and consumption_ok
      and match_ok
      and fidelity_ok
      and item.selected_closure is not None
    )
    stored_step_flags_match = bool(
      item.downstream_feedback_verified == downstream_ok
      and item.source_lineage_verified == source_ok
      and item.target_lineage_verified == target_resolve_ok
      and item.fresh_global_solve_verified == fresh_ok
      and item.target_consumption_verified == consumption_ok
      and item.target_match_verified == match_ok
      and item.fidelity_isolation_verified == fidelity_ok
      and item.research_step_verified == step_ok
    )
    iteration_flags_verified = bool(
      iteration_flags_verified and stored_step_flags_match
    )
    promotion_flags_verified = bool(
      promotion_flags_verified
      and fidelity_ok
      and item.selected_closure is not None
      and item.selected_closure.downstream_boundary_closure_verified is False
      and item.selected_closure.production_claim_allowed is False
    )
    independent_steps.append(step_ok)
    if selected_closure is not None:
      selected_closures.append(selected_closure)
  ####

  expected_final = (
    selected_closures[-1] if selected_closures else candidate.source_closure
  )
  expected_aggregate = bool(
    iteration_index_verified
    and independent_steps
    and all(independent_steps)
  )
  aggregate_flags_verified = bool(
    candidate.final_closure is expected_final
    and candidate.downstream_feedback_verified == downstream_lineage_verified
    and candidate.source_lineage_verified == source_chain_lineage_verified
    and candidate.target_lineage_verified == target_request_lineage_verified
    and candidate.fresh_global_solve_verified == fresh_global_solve_verified
    and candidate.target_consumption_verified == target_consumption_verified
    and candidate.target_match_verified == target_match_verified
    and candidate.fidelity_isolation_verified
    == (downstream_lineage_verified and promotion_flags_verified)
    and candidate.research_feedback_completed == expected_aggregate
    and configuration_verified
  )
  promotion_flags_verified = bool(
    promotion_flags_verified
    and candidate.chain_promotion_blocked
    and not candidate.global_coupling_verified
    and not candidate.downstream_boundary_closure_verified
    and not candidate.production_claim_allowed
  )

  if not iteration_index_verified or not source_chain_lineage_verified:
    status = audit_status.ITERATION_LINEAGE_FAILURE
    message = (
      'frontier feedback did not retain a contiguous iteration chain from '
      'the source closure through each selected closure'
    )
  elif not downstream_lineage_verified:
    status = audit_status.DOWNSTREAM_LINEAGE_FAILURE
    message = (
      'one or more downstream feedback runs did not retain the exact source '
      'closure and final ready proposal'
    )
  elif not target_request_lineage_verified:
    status = audit_status.TARGET_REQUEST_FAILURE
    message = (
      'one or more frontier requests did not retain the exact proposal, '
      'source fingerprint, or target channels'
    )
  elif not target_resolve_lineage_verified:
    status = audit_status.TARGET_RESOLVE_FAILURE
    message = (
      'one or more target-guided resolves did not retain the exact request '
      'and source closure lineage'
    )
  elif not fresh_global_solve_verified:
    status = audit_status.TARGET_RESOLVE_FAILURE
    message = (
      'one or more selected frontier candidates were not produced by a '
      'fresh global solve'
    )
  elif not target_consumption_verified:
    status = audit_status.TARGET_RESOLVE_FAILURE
    message = (
      'one or more target-guided resolves did not verify covered finite '
      'target consumption'
    )
  elif not target_match_verified:
    status = audit_status.TARGET_MATCH_FAILURE
    message = (
      'one or more selected global candidates did not retain the verified '
      'frontier target match'
    )
  elif not aggregate_flags_verified:
    status = audit_status.AGGREGATE_FLAG_FAILURE
    message = (
      'frontier feedback aggregate flags or final-closure lineage do not '
      'match the independently rechecked iterations'
    )
  elif not promotion_flags_verified:
    status = audit_status.PROMOTION_FLAG_FAILURE
    message = (
      'frontier feedback did not preserve its explicit research-only '
      'global-coupling and production-promotion boundary'
    )
  else:
    status = audit_status.AUDITED_RESEARCH_EVIDENCE
    message = (
      'independent source, proposal, request, fresh-resolve, target-match, '
      'and promotion checks passed; canonical closure remains blocked'
    )
  ####
  return MocReflectedDomainGlobalCoupledFrontierFeedbackAudit(
    status=status,
    candidate=candidate,
    iterations_rechecked=len(iterations),
    configuration_verified=configuration_verified,
    iteration_index_verified=iteration_index_verified,
    source_chain_lineage_verified=source_chain_lineage_verified,
    downstream_lineage_verified=downstream_lineage_verified,
    target_request_lineage_verified=target_request_lineage_verified,
    target_resolve_lineage_verified=target_resolve_lineage_verified,
    fresh_global_solve_verified=fresh_global_solve_verified,
    target_consumption_verified=target_consumption_verified,
    target_match_verified=target_match_verified,
    iteration_flags_verified=iteration_flags_verified,
    aggregate_flags_verified=aggregate_flags_verified,
    promotion_flags_verified=promotion_flags_verified,
    message=message,
  )
####


def _run_result(
  source_closure: MocReflectedDomainGlobalPhysicalClosureResult,
  final_closure: MocReflectedDomainGlobalPhysicalClosureResult,
  requested_iterations: int,
  iterations: tuple[MocReflectedDomainGlobalCoupledFrontierFeedbackIteration, ...],
  status: MocReflectedDomainGlobalCoupledFrontierFeedbackStatus,
  configuration: Mapping[str, Any],
  message: str,
) -> MocReflectedDomainGlobalCoupledFrontierFeedbackRun:
  downstream_feedback_verified = bool(
    iterations and all(item.downstream_feedback_verified for item in iterations)
  )
  source_lineage_verified = bool(
    iterations and all(item.source_lineage_verified for item in iterations)
  )
  target_lineage_verified = bool(
    iterations and all(item.target_lineage_verified for item in iterations)
  )
  fresh_global_solve_verified = bool(
    iterations and all(item.fresh_global_solve_verified for item in iterations)
  )
  target_consumption_verified = bool(
    iterations and all(item.target_consumption_verified for item in iterations)
  )
  target_match_verified = bool(
    iterations and all(item.target_match_verified for item in iterations)
  )
  fidelity_isolation_verified = bool(
    iterations and all(item.fidelity_isolation_verified for item in iterations)
  )
  return MocReflectedDomainGlobalCoupledFrontierFeedbackRun(
    source_closure=source_closure,
    final_closure=final_closure,
    requested_iterations=requested_iterations,
    iterations=iterations,
    status=status,
    configuration=dict(configuration),
    configuration_fingerprint=_configuration_fingerprint(configuration),
    downstream_feedback_verified=downstream_feedback_verified,
    source_lineage_verified=source_lineage_verified,
    target_lineage_verified=target_lineage_verified,
    fresh_global_solve_verified=fresh_global_solve_verified,
    target_consumption_verified=target_consumption_verified,
    target_match_verified=target_match_verified,
    fidelity_isolation_verified=fidelity_isolation_verified,
    message=message,
  )
####


def run_reflected_domain_global_coupled_frontier_feedback(
  closure: MocReflectedDomainGlobalPhysicalClosureResult,
  *,
  reference_total_temperature_K: float,
  maximum_iterations: int = 1,
  downstream_feedback_iterations: int = 2,
  consumer_id: str = 'moc-global-coupled-frontier-feedback-v1',
  downstream_options: Mapping[str, Any] | None = None,
  target_resolve_options: Mapping[str, Any] | None = None,
) -> MocReflectedDomainGlobalCoupledFrontierFeedbackRun:
  """Execute bounded downstream-to-global frontier feedback steps.

  ``downstream_options`` are passed to the existing downstream feedback
  ladder, while ``target_resolve_options`` are passed to the fresh global
  target-guided resolver.  The two positional closure/request inputs are
  protected so an options mapping cannot silently replace the retained
  lineage object.
  """

  if not isinstance(closure, MocReflectedDomainGlobalPhysicalClosureResult):
    raise TypeError(
      'closure must be a MocReflectedDomainGlobalPhysicalClosureResult'
    )
  ####
  if (
    isinstance(maximum_iterations, bool)
    or not isinstance(maximum_iterations, int)
    or maximum_iterations < 1
  ):
    raise ValueError('maximum_iterations must be a positive integer')
  ####
  if (
    isinstance(downstream_feedback_iterations, bool)
    or not isinstance(downstream_feedback_iterations, int)
    or downstream_feedback_iterations < 2
  ):
    raise ValueError('downstream_feedback_iterations must be at least two')
  ####
  try:
    reference_temperature = float(reference_total_temperature_K)
  except (TypeError, ValueError) as error:
    raise ValueError('reference_total_temperature_K must be numeric') from error
  ####
  if not isfinite(reference_temperature) or reference_temperature <= 0.0:
    raise ValueError(
      'reference_total_temperature_K must be finite and positive'
    )
  ####
  resolved_consumer_id = str(consumer_id)
  if not resolved_consumer_id:
    raise ValueError('consumer_id must be non-empty')
  ####
  resolved_downstream_options = _options(
    downstream_options,
    'downstream_options',
    reserved=(
      'closure',
      'reference_total_temperature_K',
      'maximum_iterations',
    ),
  )
  resolved_target_options = _options(
    target_resolve_options,
    'target_resolve_options',
    reserved=('request', 'source_closure'),
  )
  configuration: dict[str, Any] = {
    'source_closure_fingerprint': (
      moc_reflected_domain_global_physical_closure_fingerprint(closure)
    ),
    'reference_total_temperature_K': reference_temperature,
    'maximum_iterations': maximum_iterations,
    'downstream_feedback_iterations': downstream_feedback_iterations,
    'consumer_id': resolved_consumer_id,
    'downstream_options': resolved_downstream_options,
    'target_resolve_options': resolved_target_options,
    'global_feedback_policy': (
      'downstream-response-exact-proposal-fresh-global-target-guided-resolve-v1'
    ),
  }
  if not closure.converged or not closure.physical_closure_verified:
    return _run_result(
      closure,
      closure,
      maximum_iterations,
      (),
      MocReflectedDomainGlobalCoupledFrontierFeedbackStatus.INVALID_INPUT,
      configuration,
      'global frontier feedback requires a locally verified source closure',
    )
  ####
  current = closure
  iterations: list[MocReflectedDomainGlobalCoupledFrontierFeedbackIteration] = []
  failure_status: MocReflectedDomainGlobalCoupledFrontierFeedbackStatus | None = None
  failure_message: str | None = None
  for iteration_index in range(maximum_iterations):
    source_fingerprint = moc_reflected_domain_global_physical_closure_fingerprint(
      current
    )
    try:
      downstream = run_reflected_domain_global_coupled_downstream_feedback(
        current,
        reference_total_temperature_K=reference_temperature,
        maximum_iterations=downstream_feedback_iterations,
        **resolved_downstream_options,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      iterations.append(
        MocReflectedDomainGlobalCoupledFrontierFeedbackIteration(
          iteration_index=iteration_index,
          source_closure=current,
          downstream_feedback=None,
          proposal=None,
          frontier_request=None,
          target_resolve=None,
          selected_closure=None,
          source_lineage_verified=(
            source_fingerprint
            == moc_reflected_domain_global_physical_closure_fingerprint(current)
          ),
          fidelity_isolation_verified=True,
          message=f'downstream feedback raised: {error}',
        )
      )
      failure_status = (
        MocReflectedDomainGlobalCoupledFrontierFeedbackStatus
        .DOWNSTREAM_FEEDBACK_FAILURE
      )
      failure_message = f'downstream feedback raised: {error}'
      break
    ####
    proposals = downstream.upstream_feedback_proposals
    proposal = proposals[-1] if proposals else None
    downstream_feedback_verified = bool(
      downstream.fresh_solver_invocation_verified
      and downstream.upstream_feedback_proposal_verified
      and proposal is not None
      and proposal.ready_for_global_resolve
    )
    if not downstream_feedback_verified or proposal is None:
      iterations.append(
        MocReflectedDomainGlobalCoupledFrontierFeedbackIteration(
          iteration_index=iteration_index,
          source_closure=current,
          downstream_feedback=downstream,
          proposal=proposal,
          frontier_request=None,
          target_resolve=None,
          selected_closure=None,
          downstream_feedback_verified=downstream_feedback_verified,
          source_lineage_verified=(
            downstream.closure is current
            and downstream.closure_lineage_verified
          ),
          fidelity_isolation_verified=downstream.fidelity_isolation_verified,
          message=(
            'downstream feedback did not retain a ready exact frontier '
            'proposal for the global consumer'
          ),
        )
      )
      failure_status = (
        MocReflectedDomainGlobalCoupledFrontierFeedbackStatus
        .DOWNSTREAM_FEEDBACK_FAILURE
      )
      failure_message = (
        'downstream feedback did not retain a ready exact frontier proposal '
        'for the global consumer'
      )
      break
    ####
    request: MocReflectedDomainGlobalFrontierReconciliationRequest | None = None
    try:
      request = build_reflected_domain_global_frontier_reconciliation_request(
        current,
        proposal,
        consumer_id=f'{resolved_consumer_id}-iteration-{iteration_index}',
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      iterations.append(
        MocReflectedDomainGlobalCoupledFrontierFeedbackIteration(
          iteration_index=iteration_index,
          source_closure=current,
          downstream_feedback=downstream,
          proposal=proposal,
          frontier_request=None,
          target_resolve=None,
          selected_closure=None,
          downstream_feedback_verified=downstream_feedback_verified,
          source_lineage_verified=(
            downstream.closure is current
            and downstream.closure_lineage_verified
          ),
          fidelity_isolation_verified=downstream.fidelity_isolation_verified,
          message=f'frontier request construction failed: {error}',
        )
      )
      failure_status = (
        MocReflectedDomainGlobalCoupledFrontierFeedbackStatus
        .FRONTIER_REQUEST_FAILURE
      )
      failure_message = f'frontier request construction failed: {error}'
      break
    ####
    try:
      target_resolve = run_reflected_domain_global_frontier_target_guided_resolve(
        request,
        current,
        **resolved_target_options,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      iterations.append(
        MocReflectedDomainGlobalCoupledFrontierFeedbackIteration(
          iteration_index=iteration_index,
          source_closure=current,
          downstream_feedback=downstream,
          proposal=proposal,
          frontier_request=request,
          target_resolve=None,
          selected_closure=None,
          downstream_feedback_verified=downstream_feedback_verified,
          source_lineage_verified=(
            request.source_closure_fingerprint == source_fingerprint
            and request.lineage_verified
          ),
          fidelity_isolation_verified=downstream.fidelity_isolation_verified,
          message=f'target-guided global resolve raised: {error}',
        )
      )
      failure_status = (
        MocReflectedDomainGlobalCoupledFrontierFeedbackStatus
        .TARGET_RESOLVE_FAILURE
      )
      failure_message = f'target-guided global resolve raised: {error}'
      break
    ####
    selected = target_resolve.selected_candidate
    selected_closure = (
      None
      if not target_resolve.converged_research_resolve or selected is None
      else selected.closure
    )
    source_lineage_verified = bool(
      request.source_closure_fingerprint == source_fingerprint
      and request.lineage_verified
      and target_resolve.source_closure is current
    )
    target_lineage_verified = bool(
      target_resolve.target_lineage_verified
      and target_resolve.fresh_global_solve_invocation_verified
    )
    fresh_global_solve_verified = bool(
      target_resolve.fresh_global_solve_invocation_verified
      and selected is not None
      and selected.fresh_global_solve_attempted
      and selected.closure is not current
    )
    target_consumption_verified = bool(
      target_resolve.target_consumption_verified
      and target_resolve.target_coverage_verified
    )
    target_match_verified = bool(
      target_resolve.target_match_verified and selected_closure is not None
    )
    fidelity_isolation_verified = bool(
      downstream.fidelity_isolation_verified
      and not target_resolve.global_coupling_verified
      and not target_resolve.downstream_boundary_closure_verified
      and target_resolve.chain_promotion_blocked
      and not target_resolve.production_claim_allowed
      and (
        selected_closure is None or selected_closure.production_claim_allowed is False
      )
    )
    step_verified = bool(
      downstream_feedback_verified
      and source_lineage_verified
      and target_lineage_verified
      and fresh_global_solve_verified
      and target_consumption_verified
      and target_match_verified
      and fidelity_isolation_verified
      and selected_closure is not None
    )
    iterations.append(
      MocReflectedDomainGlobalCoupledFrontierFeedbackIteration(
        iteration_index=iteration_index,
        source_closure=current,
        downstream_feedback=downstream,
        proposal=proposal,
        frontier_request=request,
        target_resolve=target_resolve,
        selected_closure=selected_closure,
        downstream_feedback_verified=downstream_feedback_verified,
        source_lineage_verified=source_lineage_verified,
        target_lineage_verified=target_lineage_verified,
        fresh_global_solve_verified=fresh_global_solve_verified,
        target_consumption_verified=target_consumption_verified,
        target_match_verified=target_match_verified,
        fidelity_isolation_verified=fidelity_isolation_verified,
        message=(
          'downstream response was handed to a fresh global target-guided '
          'solve; canonical global closure remains closed'
          if step_verified
          else target_resolve.message
        ),
      )
    )
    if not step_verified:
      failure_status = (
        MocReflectedDomainGlobalCoupledFrontierFeedbackStatus.FIDELITY_FAILURE
        if not fidelity_isolation_verified
        else MocReflectedDomainGlobalCoupledFrontierFeedbackStatus
        .TARGET_RESOLVE_FAILURE
      )
      failure_message = (
        'the exact frontier target did not produce a fresh, matched global '
        'research closure with preserved promotion gates'
      )
      break
    ####
    assert selected_closure is not None
    current = selected_closure
  ####
  retained_iterations = tuple(iterations)
  if failure_status is None:
    status = (
      MocReflectedDomainGlobalCoupledFrontierFeedbackStatus
      .COMPLETED_RESEARCH_GLOBAL_FRONTIER_FEEDBACK
      if len(retained_iterations) == maximum_iterations
      and all(item.research_step_verified for item in retained_iterations)
      else MocReflectedDomainGlobalCoupledFrontierFeedbackStatus.ITERATION_LIMIT
    )
    message = (
      'downstream exact frontier responses were consumed by fresh global '
      'candidate resolves for every requested research step; canonical '
      'mixed-regime/free-boundary closure, refinement, validation, and '
      'production promotion remain open'
      if status
      is MocReflectedDomainGlobalCoupledFrontierFeedbackStatus
      .COMPLETED_RESEARCH_GLOBAL_FRONTIER_FEEDBACK
      else 'global frontier feedback stopped before all requested steps completed'
    )
  else:
    status = failure_status
    message = failure_message or 'global frontier feedback stopped'
  ####
  return _run_result(
    closure,
    current,
    maximum_iterations,
    retained_iterations,
    status,
    configuration,
    message,
  )
####
