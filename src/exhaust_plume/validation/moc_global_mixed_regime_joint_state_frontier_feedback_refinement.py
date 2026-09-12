"""Disjoint case/resolution coverage for joint frontier feedback.

The joint state/frontier feedback runner can now optionally consume the
bounded five-channel frontier residual exchange after each global update.
This module measures that nested cursor across named source closures and
strictly increasing exact frontier resolutions.  It retains nested exchange
audits and typed rejection evidence, but remains below canonical closure and
production claim ceilings.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any

from exhaust_plume.models.moc.global_physical_closure import (
  MocReflectedDomainGlobalPhysicalClosureResult,
  moc_reflected_domain_global_physical_closure_fingerprint,
)
from exhaust_plume.validation.moc_global_mixed_regime_frontier_residual_exchange import (
  MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeAudit,
  MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeResult,
  audit_reflected_domain_global_mixed_regime_frontier_residual_exchange,
)
from exhaust_plume.validation.moc_global_mixed_regime_joint_state_frontier_feedback import (
  MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackAudit,
  MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackRequest,
  MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackResult,
  MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackStatus,
  audit_reflected_domain_global_mixed_regime_joint_state_frontier_feedback,
  run_reflected_domain_global_mixed_regime_joint_state_frontier_feedback,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_JOINT_STATE_FRONTIER_FEEDBACK_REFINEMENT_OPERATOR_ID',
  'MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackRefinementStatus',
  'MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackRefinementCase',
  'MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackRefinementStep',
  'MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackRefinementMeasurement',
  'run_reflected_domain_global_mixed_regime_joint_state_frontier_feedback_refinement',
  'measure_reflected_domain_global_mixed_regime_joint_state_frontier_feedback_refinement',
)


MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_JOINT_STATE_FRONTIER_FEEDBACK_REFINEMENT_OPERATOR_ID = (
  'op.moc.reflected-domain.global-mixed-regime-joint-state-frontier-feedback-refinement-v1'
)


class MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackRefinementStatus(
  str,
  Enum,
):
  """Typed outcomes of nested joint-feedback coverage."""

  CONVERGED_LOCAL_RESEARCH_COVERAGE = (
    'converged-local-research-joint-state-frontier-feedback-coverage'
  )
  CONVERGED_CROSS_CASE_RESEARCH_COVERAGE = (
    'converged-cross-case-research-joint-state-frontier-feedback-coverage'
  )
  COMPLETED_RESEARCH_COVERAGE_WITH_OPEN_GATE = (
    'completed-research-joint-state-frontier-feedback-coverage-with-open-gate'
  )
  INVALID_INPUT = 'invalid_input'
  FEEDBACK_FAILURE = (
    'joint-state-frontier-feedback-refinement-feedback-failure'
  )
####

@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackRefinementCase:
  """One named source closure/resolution point in the nested feedback ladder."""

  case_id: str
  request: MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackRequest
  source: str = (
    'research-global-mixed-regime-joint-state-frontier-feedback-refinement-v1'
  )

  def __post_init__(self) -> None:
    case_id = str(self.case_id)
    if not case_id:
      raise ValueError('case_id must be non-empty')
    ####
    if not isinstance(
      self.request,
      MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackRequest,
    ):
      raise TypeError('request must be a typed joint-feedback request')
    ####
    if not self.request.consume_frontier_residual_exchange:
      raise ValueError(
        'refinement cases must explicitly consume frontier residual exchange'
      )
    ####
    source = str(self.source)
    if not source:
      raise ValueError('source must be non-empty')
    ####
    object.__setattr__(self, 'case_id', case_id)
    object.__setattr__(self, 'source', source)
  ####

  @property
  def source_closure(self) -> MocReflectedDomainGlobalPhysicalClosureResult:
    return self.request.source_closure
  ####

  @property
  def source_closure_fingerprint(self) -> str:
    return moc_reflected_domain_global_physical_closure_fingerprint(
      self.source_closure
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': (
        MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_JOINT_STATE_FRONTIER_FEEDBACK_REFINEMENT_OPERATOR_ID
      ),
      'case_id': self.case_id,
      'source': self.source,
      'source_closure_fingerprint': self.source_closure_fingerprint,
      'request': self.request.as_report(),
      'research_only': True,
      'production_claim_allowed': False,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackRefinementStep:
  """One independently executed nested feedback case."""

  case: MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackRefinementCase
  result: MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackResult
  audit: MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackAudit
  nested_exchange_audits: tuple[
    MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeAudit,
    ...,
  ] = ()

  def __post_init__(self) -> None:
    if not isinstance(
      self.case,
      MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackRefinementCase,
    ):
      raise TypeError('case must be a typed refinement case')
    ####
    if not isinstance(
      self.result,
      MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackResult,
    ):
      raise TypeError('result must be a typed joint-feedback result')
    ####
    if not isinstance(
      self.audit,
      MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackAudit,
    ):
      raise TypeError('audit must be a typed joint-feedback audit')
    ####
    audits = tuple(self.nested_exchange_audits)
    if any(
      not isinstance(
        audit,
        MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeAudit,
      )
      for audit in audits
    ):
      raise TypeError('nested_exchange_audits must contain typed audits')
    ####
    object.__setattr__(self, 'nested_exchange_audits', audits)
  ####

  @property
  def frontier_sample_counts(self) -> tuple[int, ...]:
    return tuple(
      item.source_frontier_step.frontier_sample_count
      for item in self.result.iterations
      if item.source_frontier_step is not None
    )
  ####

  @property
  def exchange_results(
    self,
  ) -> tuple[MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeResult, ...]:
    return tuple(
      item.frontier_residual_exchange
      for item in self.result.iterations
      if item.frontier_residual_exchange is not None
    )
  ####

  @property
  def exact_closure_lineage_verified(self) -> bool:
    expected = self.result.source_closure
    if expected is not self.case.source_closure:
      return False
    ####
    for item in self.result.iterations:
      if item.source_closure is not expected:
        return False
      ####
      if item.boundary_state_feedback.source_closure is not expected:
        return False
      ####
      if item.source_frontier_step is None or item.joint_solve is None:
        return False
      ####
      if item.joint_solve.joint_state_solve is None:
        return False
      ####
      handoff = item.boundary_state_feedback.handoff
      if handoff is None or item.source_frontier_step.closure is not handoff.boundary_feedback_run.iterations[-1].source_closure:
        return False
      ####
      if item.joint_solve.source_frontier_step is not item.source_frontier_step:
        return False
      ####
      expected = item.next_closure
      if expected is None:
        return False
      ####
      if item.frontier_residual_exchange is not None:
        if expected is not item.frontier_residual_exchange.final_closure:
          return False
        ####
      elif expected is not item.joint_solve.joint_state_solve.geometry_response_closure:
        return False
      ####
    ####
    return bool(
      expected is not None
      and self.result.final_closure is expected
    )
  ####

  @property
  def nested_exchange_replay_verified(self) -> bool:
    return bool(
      self.result.frontier_residual_exchange_chain_verified
      and self.audit.residual_exchange_chain_replayed
      and self.nested_exchange_audits
      and all(audit.converged for audit in self.nested_exchange_audits)
    )
  ####

  @property
  def componentwise_admission_verified(self) -> bool:
    return bool(
      self.exchange_results
      and all(
        result.componentwise_non_worsening and result.strict_component_descent
        for result in self.exchange_results
      )
    )
  ####

  @property
  def feedback_chain_verified(self) -> bool:
    return bool(
      self.result.feedback_completed
      and self.result.frontier_chain_verified
      and self.result.joint_solve_chain_verified
      and self.result.independent_audit_verified
      and all(item.research_step_verified for item in self.result.iterations)
    )
  ####

  @property
  def fail_closed_rejection_verified(self) -> bool:
    if self.result.status is not MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackStatus.RESIDUAL_EXCHANGE_FAILURE:
      return False
    ####
    if not self.result.iterations:
      return False
    ####
    exchange = self.result.iterations[-1].frontier_residual_exchange
    return bool(
      exchange is not None
      and not exchange.converged
      and not self.result.iterations[-1].research_step_verified
      and self.result.final_closure is self.result.iterations[-1].next_closure
    )
  ####

  @property
  def fidelity_isolation_verified(self) -> bool:
    return bool(
      self.result.global_coupling_verified is False
      and self.result.canonical_free_boundary_verified is False
      and self.result.chain_promotion_blocked
      and self.result.production_claim_allowed is False
      and self.audit.global_coupling_verified is False
      and self.audit.chain_promotion_blocked
      and self.audit.production_claim_allowed is False
      and all(
        audit.global_coupling_verified is False
        and audit.chain_promotion_blocked
        and audit.production_claim_allowed is False
        for audit in self.nested_exchange_audits
      )
    )
  ####

  @property
  def locally_verified(self) -> bool:
    return bool(
      self.feedback_chain_verified
      and self.exact_closure_lineage_verified
      and self.nested_exchange_replay_verified
      and self.componentwise_admission_verified
      and self.fidelity_isolation_verified
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': (
        MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_JOINT_STATE_FRONTIER_FEEDBACK_REFINEMENT_OPERATOR_ID
      ),
      'case': self.case.as_report(),
      'result': self.result.as_report(),
      'audit': self.audit.as_report(),
      'nested_exchange_audits': tuple(
        audit.as_report() for audit in self.nested_exchange_audits
      ),
      'checks': {
        'frontier_sample_counts': self.frontier_sample_counts,
        'feedback_chain_verified': self.feedback_chain_verified,
        'exact_closure_lineage_verified': self.exact_closure_lineage_verified,
        'nested_exchange_replay_verified': self.nested_exchange_replay_verified,
        'componentwise_admission_verified': self.componentwise_admission_verified,
        'fail_closed_rejection_verified': self.fail_closed_rejection_verified,
        'fidelity_isolation_verified': self.fidelity_isolation_verified,
        'locally_verified': self.locally_verified,
      },
    }
  ####
####


def _grouped_frontier_sample_count_ladders(
  steps: Sequence[
    MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackRefinementStep
  ],
) -> tuple[tuple[int, ...], ...]:
  grouped: dict[
    str,
    list[
      MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackRefinementStep
    ],
  ] = {}
  for step in steps:
    grouped.setdefault(step.case.case_id, []).append(step)
  ####
  return tuple(
    tuple(
      count
      for step in case_steps
      for count in step.frontier_sample_counts
    )
    for case_steps in grouped.values()
  )
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackRefinementMeasurement:
  """Disjoint nested feedback evidence below promotion ceilings."""

  status: MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackRefinementStatus
  steps: tuple[
    MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackRefinementStep,
    ...,
  ] = ()
  case_ids: tuple[str, ...] = ()
  frontier_sample_count_ladders: tuple[tuple[int, ...], ...] = ()
  source_closure_fingerprints: tuple[str, ...] = ()
  local_case_resolution_ladders_verified: bool = False
  distinct_source_closures_verified: bool = False
  exact_closure_lineage_verified: bool = False
  feedback_chain_verified: bool = False
  nested_exchange_replay_verified: bool = False
  componentwise_admission_verified: bool = False
  fail_closed_rejection_verified: bool = False
  fidelity_isolation_verified: bool = False
  local_coverage_verified: bool = False
  cross_case_coverage_verified: bool = False
  canonical_free_boundary_verified: bool = False
  global_coupling_verified: bool = False
  external_validation_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackRefinementStatus,
    ):
      raise TypeError('status must be a typed refinement status')
    ####
    steps = tuple(self.steps)
    if any(
      not isinstance(
        step,
        MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackRefinementStep,
      )
      for step in steps
    ):
      raise TypeError('steps must contain typed refinement steps')
    ####
    case_ids = tuple(step.case.case_id for step in steps)
    ladders = _grouped_frontier_sample_count_ladders(steps)
    fingerprints = tuple(step.case.source_closure_fingerprint for step in steps)
    if self.case_ids and tuple(self.case_ids) != case_ids:
      raise ValueError('case_ids must match retained refinement steps')
    ####
    if self.frontier_sample_count_ladders and tuple(self.frontier_sample_count_ladders) != ladders:
      raise ValueError('frontier_sample_count_ladders must match retained steps')
    ####
    if self.source_closure_fingerprints and tuple(self.source_closure_fingerprints) != fingerprints:
      raise ValueError('source_closure_fingerprints must match retained steps')
    ####
    for name in (
      'local_case_resolution_ladders_verified',
      'distinct_source_closures_verified',
      'exact_closure_lineage_verified',
      'feedback_chain_verified',
      'nested_exchange_replay_verified',
      'componentwise_admission_verified',
      'fail_closed_rejection_verified',
      'fidelity_isolation_verified',
      'local_coverage_verified',
      'cross_case_coverage_verified',
      'canonical_free_boundary_verified',
      'global_coupling_verified',
      'external_validation_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if self.canonical_free_boundary_verified or self.global_coupling_verified:
      raise ValueError('refinement cannot claim canonical/global closure')
    ####
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError('refinement must remain promotion-blocked')
    ####
    object.__setattr__(self, 'steps', steps)
    object.__setattr__(self, 'case_ids', case_ids)
    object.__setattr__(self, 'frontier_sample_count_ladders', ladders)
    object.__setattr__(self, 'source_closure_fingerprints', fingerprints)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      in {
        MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackRefinementStatus
        .CONVERGED_LOCAL_RESEARCH_COVERAGE,
        MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackRefinementStatus
        .CONVERGED_CROSS_CASE_RESEARCH_COVERAGE,
      }
      and self.local_coverage_verified
      and self.fidelity_isolation_verified
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': (
        MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_JOINT_STATE_FRONTIER_FEEDBACK_REFINEMENT_OPERATOR_ID
      ),
      'status': self.status.value,
      'converged': self.converged,
      'case_ids': self.case_ids,
      'frontier_sample_count_ladders': self.frontier_sample_count_ladders,
      'source_closure_fingerprints': self.source_closure_fingerprints,
      'checks': {
        'local_case_resolution_ladders_verified': self.local_case_resolution_ladders_verified,
        'distinct_source_closures_verified': self.distinct_source_closures_verified,
        'exact_closure_lineage_verified': self.exact_closure_lineage_verified,
        'feedback_chain_verified': self.feedback_chain_verified,
        'nested_exchange_replay_verified': self.nested_exchange_replay_verified,
        'componentwise_admission_verified': self.componentwise_admission_verified,
        'fail_closed_rejection_verified': self.fail_closed_rejection_verified,
        'fidelity_isolation_verified': self.fidelity_isolation_verified,
        'local_coverage_verified': self.local_coverage_verified,
        'cross_case_coverage_verified': self.cross_case_coverage_verified,
        'canonical_free_boundary_verified': False,
        'global_coupling_verified': False,
        'external_validation_verified': False,
        'chain_promotion_blocked': True,
        'production_claim_allowed': False,
      },
      'steps': tuple(step.as_report() for step in self.steps),
      'message': self.message,
    }
  ####
####


def _measurement(
  status: MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackRefinementStatus,
  message: str,
  *,
  steps: Sequence[
    MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackRefinementStep
  ] = (),
  **flags: bool,
) -> MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackRefinementMeasurement:
  retained = tuple(steps)
  return MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackRefinementMeasurement(
    status=status,
    steps=retained,
    case_ids=tuple(step.case.case_id for step in retained),
    frontier_sample_count_ladders=_grouped_frontier_sample_count_ladders(
      retained
    ),
    source_closure_fingerprints=tuple(
      step.case.source_closure_fingerprint for step in retained
    ),
    **flags,
    message=message,
  )
####


def _strictly_increasing(values: Sequence[int]) -> bool:
  return bool(
    len(values) >= 2
    and all(right > left for left, right in zip(values, values[1:]))
  )
####


def _resolution_ladder(
  steps: Sequence[
    MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackRefinementStep
  ],
) -> bool:
  counts: list[int] = []
  for step in steps:
    if not step.frontier_sample_counts:
      return False
    ####
    counts.append(step.frontier_sample_counts[0])
  ####
  return _strictly_increasing(counts)
####


def measure_reflected_domain_global_mixed_regime_joint_state_frontier_feedback_refinement(
  steps: Sequence[
    MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackRefinementStep
  ],
  *,
  expected_case_ids: Sequence[str] | None = None,
) -> MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackRefinementMeasurement:
  """Measure nested feedback coverage without promoting it."""

  status_type = (
    MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackRefinementStatus
  )
  try:
    retained = tuple(steps)
  except TypeError:
    return _measurement(status_type.INVALID_INPUT, 'steps must be iterable')
  ####
  if len(retained) < 2 or any(
    not isinstance(
      step,
      MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackRefinementStep,
    )
    for step in retained
  ):
    return _measurement(
      status_type.INVALID_INPUT,
      'refinement requires at least two typed joint-feedback steps',
    )
  ####
  grouped: dict[str, list[MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackRefinementStep]] = {}
  for step in retained:
    grouped.setdefault(step.case.case_id, []).append(step)
  ####
  actual_case_ids = tuple(grouped)
  expected = (
    None
    if expected_case_ids is None
    else tuple(str(value) for value in expected_case_ids)
  )
  case_ids_verified = bool(
    actual_case_ids
    and all(actual_case_ids)
    and (expected is None or actual_case_ids == expected)
  )
  ladders = bool(
    grouped
    and all(
      _resolution_ladder(case_steps)
      for case_steps in grouped.values()
    )
  )
  distinct_sources = bool(
    len(grouped) >= 2
    and len({step.case.source_closure_fingerprint for step in retained}) >= 2
  )
  exact_lineage = all(step.exact_closure_lineage_verified for step in retained)
  feedback_chain = all(step.feedback_chain_verified for step in retained)
  nested_replay = all(
    step.nested_exchange_replay_verified for step in retained
  )
  componentwise = all(
    step.componentwise_admission_verified for step in retained
  )
  fail_closed = any(step.fail_closed_rejection_verified for step in retained)
  fidelity = all(step.fidelity_isolation_verified for step in retained)
  local_coverage = bool(
    case_ids_verified
    and exact_lineage
    and feedback_chain
    and nested_replay
    and componentwise
    and fidelity
  )
  cross_case = bool(local_coverage and ladders and distinct_sources)
  status = (
    status_type.CONVERGED_CROSS_CASE_RESEARCH_COVERAGE
    if cross_case
    else status_type.CONVERGED_LOCAL_RESEARCH_COVERAGE
    if local_coverage
    else status_type.COMPLETED_RESEARCH_COVERAGE_WITH_OPEN_GATE
  )
  open_gates: list[str] = []
  for verified, label in (
    (case_ids_verified, 'case identity'),
    (ladders, 'strict resolution ladders'),
    (distinct_sources, 'distinct source closures'),
    (exact_lineage, 'exact closure lineage'),
    (feedback_chain, 'joint feedback chain'),
    (nested_replay, 'nested exchange replay'),
    (componentwise, 'component-wise frontier admission'),
    (fidelity, 'fidelity isolation'),
  ):
    if not verified:
      open_gates.append(label)
    ####
  ####
  message = (
    'joint state/frontier feedback consumed the bounded five-channel frontier '
    'exchange across distinct source closures and increasing exact resolutions; '
    'canonical/global and production promotion remain open'
    if cross_case
    else 'joint state/frontier feedback evidence was retained, but open gates '
    f'remain: {", ".join(open_gates) if open_gates else "cross-case coverage"}'
  )
  return _measurement(
    status,
    message,
    steps=retained,
    local_case_resolution_ladders_verified=ladders,
    distinct_source_closures_verified=distinct_sources,
    exact_closure_lineage_verified=exact_lineage,
    feedback_chain_verified=feedback_chain,
    nested_exchange_replay_verified=nested_replay,
    componentwise_admission_verified=componentwise,
    fail_closed_rejection_verified=fail_closed,
    fidelity_isolation_verified=fidelity,
    local_coverage_verified=local_coverage,
    cross_case_coverage_verified=cross_case,
    canonical_free_boundary_verified=False,
    global_coupling_verified=False,
    external_validation_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
  )
####


def run_reflected_domain_global_mixed_regime_joint_state_frontier_feedback_refinement(
  cases: Sequence[
    MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackRefinementCase
  ],
  *,
  expected_case_ids: Sequence[str] | None = None,
) -> MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackRefinementMeasurement:
  """Run and independently audit each nested joint-feedback case."""

  status_type = (
    MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackRefinementStatus
  )
  try:
    retained_cases = tuple(cases)
  except TypeError:
    return _measurement(status_type.INVALID_INPUT, 'cases must be iterable')
  ####
  if len(retained_cases) < 2 or any(
    not isinstance(
      case,
      MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackRefinementCase,
    )
    for case in retained_cases
  ):
    return _measurement(
      status_type.INVALID_INPUT,
      'cases must contain at least two typed refinement cases',
    )
  ####
  steps: list[
    MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackRefinementStep
  ] = []
  for case in retained_cases:
    try:
      result = run_reflected_domain_global_mixed_regime_joint_state_frontier_feedback(
        case.request
      )
      audit = audit_reflected_domain_global_mixed_regime_joint_state_frontier_feedback(
        result
      )
      nested_audits = tuple(
        audit_reflected_domain_global_mixed_regime_frontier_residual_exchange(
          item.frontier_residual_exchange
        )
        for item in result.iterations
        if item.frontier_residual_exchange is not None
      )
      steps.append(
        MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackRefinementStep(
          case=case,
          result=result,
          audit=audit,
          nested_exchange_audits=nested_audits,
        )
      )
    except (ArithmeticError, FloatingPointError, RuntimeError, TypeError, ValueError) as error:
      return _measurement(
        status_type.FEEDBACK_FAILURE,
        f'joint state/frontier feedback refinement failed: {error}',
        steps=steps,
      )
    ####
  ####
  return measure_reflected_domain_global_mixed_regime_joint_state_frontier_feedback_refinement(
    steps,
    expected_case_ids=expected_case_ids,
  )
####
