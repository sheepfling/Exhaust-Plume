"""Disjoint case and resolution coverage for the P3.43 consumer gate.

The canonical-consumer result is still research-only, but one successful
fixture is not enough evidence to exercise it across source closures and mesh
resolutions.  This module runs the existing P3.43 request/audit pair over an
explicit case/resolution set, checks that the feedback configuration really
retains the declared resolution, and keeps the global/free-boundary promotion
flags closed.

The runner is a coverage gate, not a global convergence claim.  In particular,
it rejects a repeated request relabeled with a different resolution and does
not infer a second physical closure from a changed case identifier.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
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

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_CANONICAL_CONSUMER_REFINEMENT_OPERATOR_ID',
  'MocReflectedDomainGlobalMixedRegimeCanonicalConsumerRefinementStatus',
  'MocReflectedDomainGlobalMixedRegimeCanonicalConsumerRefinementCase',
  'MocReflectedDomainGlobalMixedRegimeCanonicalConsumerRefinementStep',
  'MocReflectedDomainGlobalMixedRegimeCanonicalConsumerRefinementMeasurement',
  'measure_reflected_domain_global_mixed_regime_canonical_consumer_refinement',
  'run_reflected_domain_global_mixed_regime_canonical_consumer_refinement',
)


MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_CANONICAL_CONSUMER_REFINEMENT_OPERATOR_ID = (
  'op.moc.reflected-domain.global-mixed-regime-canonical-consumer-refinement-v1'
)


class MocReflectedDomainGlobalMixedRegimeCanonicalConsumerRefinementStatus(
  str,
  Enum,
):
  """Typed outcomes of the P3.43 coverage gate."""

  CONVERGED_LOCAL_RESEARCH_COVERAGE = (
    'converged-local-research-canonical-consumer-coverage'
  )
  CONVERGED_CROSS_CASE_RESEARCH_COVERAGE = (
    'converged-cross-case-research-canonical-consumer-coverage'
  )
  COMPLETED_RESEARCH_COVERAGE_WITH_OPEN_GATE = (
    'completed-research-canonical-consumer-coverage-with-open-gate'
  )
  INVALID_INPUT = 'invalid_input'
  CASE_ID_FAILURE = 'canonical-consumer-refinement-case-id-failure'
  RESOLUTION_FAILURE = 'canonical-consumer-refinement-resolution-failure'
  SOURCE_LINEAGE_FAILURE = 'canonical-consumer-refinement-source-lineage-failure'
  CONSUMER_FAILURE = 'canonical-consumer-refinement-consumer-failure'
  AUDIT_FAILURE = 'canonical-consumer-refinement-audit-failure'
  FEEDBACK_RESOLUTION_FAILURE = (
    'canonical-consumer-refinement-feedback-resolution-failure'
  )
  FIDELITY_FAILURE = 'canonical-consumer-refinement-fidelity-failure'


def _resolution(value: object, name: str) -> tuple[int, int]:
  try:
    pair = tuple(value)  # type: ignore[arg-type]
  except TypeError as error:
    raise ValueError(f'{name} must contain axial/transverse counts') from error
  ####
  if (
    len(pair) != 2
    or any(isinstance(item, bool) or not isinstance(item, int) for item in pair)
    or pair[0] < 8
    or pair[1] < 4
  ):
    raise ValueError(
      f'{name} must contain integer counts with axial >= 8 and transverse >= 4'
    )
  ####
  return int(pair[0]), int(pair[1])
####


def _increasing(resolutions: Sequence[tuple[int, int]]) -> bool:
  return bool(
    len(resolutions) >= 2
    and all(
      right[0] > left[0] and right[1] > left[1]
      for left, right in zip(resolutions, resolutions[1:])
    )
  )
####


def _source_closure(
  request: MocReflectedDomainGlobalMixedRegimeCanonicalConsumerRequest,
) -> MocReflectedDomainGlobalPhysicalClosureResult | None:
  equation = request.upstream_state_equation
  if equation.source_closure is not None:
    return equation.source_closure
  ####
  if equation.request is not None:
    return equation.request.closure
  ####
  return None
####


def _feedback_resolution(
  feedback: MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRun | None,
) -> tuple[int, int] | None:
  if feedback is None:
    return None
  ####
  options = feedback.configuration.get('downstream_options')
  if not isinstance(options, Mapping):
    return None
  ####
  axial = options.get('axial_cell_count')
  transverse = options.get('transverse_cell_count')
  if (
    isinstance(axial, bool)
    or not isinstance(axial, int)
    or isinstance(transverse, bool)
    or not isinstance(transverse, int)
  ):
    return None
  ####
  return axial, transverse
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeCanonicalConsumerRefinementCase:
  """One canonical-consumer request at one declared resolution."""

  case_id: str
  resolution: tuple[int, int]
  request: MocReflectedDomainGlobalMixedRegimeCanonicalConsumerRequest

  def __post_init__(self) -> None:
    case_id = str(self.case_id)
    if not case_id:
      raise ValueError('case_id must be non-empty')
    ####
    if not isinstance(
      self.request,
      MocReflectedDomainGlobalMixedRegimeCanonicalConsumerRequest,
    ):
      raise TypeError('request must be a typed canonical-consumer request')
    ####
    object.__setattr__(self, 'case_id', case_id)
    object.__setattr__(
      self,
      'resolution',
      _resolution(self.resolution, 'resolution'),
    )
  ####

  @property
  def source_closure(self) -> MocReflectedDomainGlobalPhysicalClosureResult | None:
    return _source_closure(self.request)
  ####

  @property
  def source_closure_fingerprint(self) -> str | None:
    closure = self.source_closure
    if closure is None:
      return None
    ####
    return moc_reflected_domain_global_physical_closure_fingerprint(closure)
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'case_id': self.case_id,
      'resolution': self.resolution,
      'source_closure_fingerprint': self.source_closure_fingerprint,
      'request_operator_id': (
        'op.moc.reflected-domain.global-mixed-regime-canonical-consumer-gate-v1'
      ),
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeCanonicalConsumerRefinementStep:
  """One consumed canonical request and independent replay audit."""

  case_id: str
  resolution: tuple[int, int]
  request: MocReflectedDomainGlobalMixedRegimeCanonicalConsumerRequest
  result: MocReflectedDomainGlobalMixedRegimeCanonicalConsumerResult
  audit: MocReflectedDomainGlobalMixedRegimeCanonicalConsumerAudit

  def __post_init__(self) -> None:
    case_id = str(self.case_id)
    if not case_id:
      raise ValueError('case_id must be non-empty')
    ####
    if not isinstance(
      self.request,
      MocReflectedDomainGlobalMixedRegimeCanonicalConsumerRequest,
    ):
      raise TypeError('request must be a typed canonical-consumer request')
    if not isinstance(
      self.result,
      MocReflectedDomainGlobalMixedRegimeCanonicalConsumerResult,
    ):
      raise TypeError('result must be a typed canonical-consumer result')
    if not isinstance(
      self.audit,
      MocReflectedDomainGlobalMixedRegimeCanonicalConsumerAudit,
    ):
      raise TypeError('audit must be a typed canonical-consumer audit')
    ####
    if self.result.request is not self.request:
      raise ValueError('result must retain the exact case request')
    if self.audit.candidate is not self.result:
      raise ValueError('audit must retain the exact canonical-consumer result')
    ####
    object.__setattr__(self, 'case_id', case_id)
    object.__setattr__(
      self,
      'resolution',
      _resolution(self.resolution, 'resolution'),
    )
  ####

  @property
  def source_closure_fingerprint(self) -> str | None:
    return self.result.source_closure_fingerprint
  ####

  @property
  def source_lineage_verified(self) -> bool:
    closure = _source_closure(self.request)
    return bool(
      closure is not None
      and self.result.source_closure is closure
      and self.result.source_closure_fingerprint
      == moc_reflected_domain_global_physical_closure_fingerprint(closure)
      and self.result.characteristic_compatibility_consumed
      and self.result.upstream_state_equation_consumed
    )
  ####

  @property
  def feedback_resolution_verified(self) -> bool:
    return _feedback_resolution(self.result.global_feedback) == self.resolution
  ####

  @property
  def fidelity_isolation_verified(self) -> bool:
    feedback = self.result.global_feedback
    return bool(
      self.result.chain_promotion_blocked
      and not self.result.production_claim_allowed
      and not self.result.canonical_free_boundary_verified
      and not self.result.global_coupling_verified
      and feedback is not None
      and feedback.chain_promotion_blocked
      and not feedback.production_claim_allowed
      and not feedback.global_coupling_verified
      and not feedback.downstream_boundary_closure_verified
    )
  ####

  @property
  def independent_audit_verified(self) -> bool:
    return bool(
      self.audit.converged
      and self.audit.candidate is self.result
      and self.audit.independent_research_consumption_verified
    )
  ####

  @property
  def locally_verified(self) -> bool:
    return bool(
      self.result.converged
      and self.source_lineage_verified
      and self.feedback_resolution_verified
      and self.independent_audit_verified
      and self.fidelity_isolation_verified
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'case_id': self.case_id,
      'resolution': self.resolution,
      'source_closure_fingerprint': self.source_closure_fingerprint,
      'source_lineage_verified': self.source_lineage_verified,
      'feedback_resolution_verified': self.feedback_resolution_verified,
      'independent_audit_verified': self.independent_audit_verified,
      'fidelity_isolation_verified': self.fidelity_isolation_verified,
      'locally_verified': self.locally_verified,
      'result_status': self.result.status.value,
      'audit_status': self.audit.status.value,
      'result': self.result.as_report(),
      'audit': self.audit.as_report(),
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeCanonicalConsumerRefinementMeasurement:
  """Coverage evidence below the canonical and production claim ceilings."""

  status: MocReflectedDomainGlobalMixedRegimeCanonicalConsumerRefinementStatus
  steps: tuple[
    MocReflectedDomainGlobalMixedRegimeCanonicalConsumerRefinementStep,
    ...,
  ] = ()
  case_ids: tuple[str, ...] = ()
  resolutions: tuple[tuple[int, int], ...] = ()
  source_closure_fingerprints: tuple[str | None, ...] = ()
  result_statuses: tuple[str, ...] = ()
  audit_statuses: tuple[str, ...] = ()
  case_ids_verified: bool = False
  source_closure_bindings_verified: bool = False
  distinct_source_closures_verified: bool = False
  resolution_ladders_verified: bool = False
  feedback_resolutions_verified: bool = False
  research_consumption_verified: bool = False
  independent_audits_verified: bool = False
  fidelity_isolation_verified: bool = False
  local_coverage_verified: bool = False
  cross_case_coverage_verified: bool = False
  canonical_free_boundary_verified: bool = False
  global_coupling_verified: bool = False
  external_validation_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  operator_id: str = (
    MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_CANONICAL_CONSUMER_REFINEMENT_OPERATOR_ID
  )
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalMixedRegimeCanonicalConsumerRefinementStatus,
    ):
      raise TypeError('status must be a typed canonical-consumer refinement status')
    ####
    steps = tuple(self.steps)
    if any(
      not isinstance(
        step,
        MocReflectedDomainGlobalMixedRegimeCanonicalConsumerRefinementStep,
      )
      for step in steps
    ):
      raise TypeError('steps must contain typed canonical-consumer refinement steps')
    ####
    fields = {
      'case_ids': tuple(str(value) for value in self.case_ids),
      'resolutions': tuple(
        _resolution(value, 'resolution') for value in self.resolutions
      ),
      'source_closure_fingerprints': tuple(self.source_closure_fingerprints),
      'result_statuses': tuple(str(value) for value in self.result_statuses),
      'audit_statuses': tuple(str(value) for value in self.audit_statuses),
    }
    if any(len(value) != len(steps) for value in fields.values()):
      raise ValueError('refinement summaries must match the step count')
    ####
    for name in (
      'case_ids_verified',
      'source_closure_bindings_verified',
      'distinct_source_closures_verified',
      'resolution_ladders_verified',
      'feedback_resolutions_verified',
      'research_consumption_verified',
      'independent_audits_verified',
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
    if self.canonical_free_boundary_verified or self.global_coupling_verified:
      raise ValueError('canonical-consumer refinement cannot claim global closure')
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError(
        'canonical-consumer refinement must remain promotion-blocked'
      )
    ####
    object.__setattr__(self, 'steps', steps)
    for name, value in fields.items():
      object.__setattr__(self, name, value)
    ####
    object.__setattr__(self, 'operator_id', str(self.operator_id))
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      in {
        MocReflectedDomainGlobalMixedRegimeCanonicalConsumerRefinementStatus
        .CONVERGED_LOCAL_RESEARCH_COVERAGE,
        MocReflectedDomainGlobalMixedRegimeCanonicalConsumerRefinementStatus
        .CONVERGED_CROSS_CASE_RESEARCH_COVERAGE,
      }
      and self.local_coverage_verified
      and self.fidelity_isolation_verified
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': self.operator_id,
      'status': self.status.value,
      'converged': self.converged,
      'case_ids': self.case_ids,
      'resolutions': self.resolutions,
      'source_closure_fingerprints': self.source_closure_fingerprints,
      'result_statuses': self.result_statuses,
      'audit_statuses': self.audit_statuses,
      'checks': {
        'case_ids_verified': self.case_ids_verified,
        'source_closure_bindings_verified': (
          self.source_closure_bindings_verified
        ),
        'distinct_source_closures_verified': (
          self.distinct_source_closures_verified
        ),
        'resolution_ladders_verified': self.resolution_ladders_verified,
        'feedback_resolutions_verified': self.feedback_resolutions_verified,
        'research_consumption_verified': self.research_consumption_verified,
        'independent_audits_verified': self.independent_audits_verified,
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
      'claim_status': (
        'research-only canonical-consumer coverage; disjoint closure and '
        'resolution evidence does not imply a global fixed point, normal '
        'closure, external validation, or production promotion'
      ),
    }
  ####
####


def _summary(
  steps: Sequence[
    MocReflectedDomainGlobalMixedRegimeCanonicalConsumerRefinementStep
  ],
) -> dict[str, tuple[Any, ...]]:
  return {
    'case_ids': tuple(step.case_id for step in steps),
    'resolutions': tuple(step.resolution for step in steps),
    'source_closure_fingerprints': tuple(
      step.source_closure_fingerprint for step in steps
    ),
    'result_statuses': tuple(step.result.status.value for step in steps),
    'audit_statuses': tuple(step.audit.status.value for step in steps),
  }
####


def _measurement(
  status: MocReflectedDomainGlobalMixedRegimeCanonicalConsumerRefinementStatus,
  message: str,
  *,
  steps: Sequence[
    MocReflectedDomainGlobalMixedRegimeCanonicalConsumerRefinementStep
  ] = (),
  **flags: bool,
) -> MocReflectedDomainGlobalMixedRegimeCanonicalConsumerRefinementMeasurement:
  retained = tuple(steps)
  return MocReflectedDomainGlobalMixedRegimeCanonicalConsumerRefinementMeasurement(
    status=status,
    steps=retained,
    **_summary(retained),
    **flags,
    message=message,
  )
####


def measure_reflected_domain_global_mixed_regime_canonical_consumer_refinement(
  steps: Sequence[
    MocReflectedDomainGlobalMixedRegimeCanonicalConsumerRefinementStep
  ],
  *,
  expected_case_ids: Sequence[str] | None = None,
) -> MocReflectedDomainGlobalMixedRegimeCanonicalConsumerRefinementMeasurement:
  """Audit exact canonical-consumer evidence by case and resolution."""

  status_type = MocReflectedDomainGlobalMixedRegimeCanonicalConsumerRefinementStatus
  try:
    retained = tuple(steps)
  except TypeError:
    return _measurement(status_type.INVALID_INPUT, 'steps must be iterable')
  ####
  if len(retained) < 2:
    return _measurement(
      status_type.INVALID_INPUT,
      'canonical-consumer refinement requires at least two steps',
    )
  ####
  if any(
    not isinstance(
      step,
      MocReflectedDomainGlobalMixedRegimeCanonicalConsumerRefinementStep,
    )
    for step in retained
  ):
    return _measurement(
      status_type.INVALID_INPUT,
      'steps must contain typed canonical-consumer refinement steps',
    )
  ####
  grouped: dict[str, list[MocReflectedDomainGlobalMixedRegimeCanonicalConsumerRefinementStep]] = defaultdict(list)
  for step in retained:
    grouped[step.case_id].append(step)
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
    and len(actual_case_ids) == len(set(actual_case_ids))
    and (expected is None or actual_case_ids == expected)
  )
  ####
  resolution_ladders_verified = bool(
    grouped
    and all(
      _increasing(tuple(step.resolution for step in case_steps))
      for case_steps in grouped.values()
    )
  )
  source_bindings = all(step.source_lineage_verified for step in retained)
  fingerprints = tuple(
    step.source_closure_fingerprint for step in retained
  )
  distinct_sources = bool(
    len(grouped) >= 2
    and all(fingerprint is not None for fingerprint in fingerprints)
    and len({
      fingerprint
      for fingerprint in fingerprints
      if fingerprint is not None
    })
    >= len(grouped)
  )
  feedback_resolutions = all(
    step.feedback_resolution_verified for step in retained
  )
  research_consumption = all(step.result.converged for step in retained)
  independent_audits = all(step.independent_audit_verified for step in retained)
  fidelity_isolation = all(step.fidelity_isolation_verified for step in retained)
  local_coverage = bool(
    len(retained) >= 2
    and case_ids_verified
    and resolution_ladders_verified
    and source_bindings
    and feedback_resolutions
    and research_consumption
    and independent_audits
    and fidelity_isolation
  )
  cross_case = bool(local_coverage and distinct_sources)
  status = (
    status_type.CONVERGED_CROSS_CASE_RESEARCH_COVERAGE
    if cross_case
    else status_type.CONVERGED_LOCAL_RESEARCH_COVERAGE
    if local_coverage
    else status_type.COMPLETED_RESEARCH_COVERAGE_WITH_OPEN_GATE
  )
  message = (
    'canonical-consumer evidence passed independent replay across distinct '
    'source closures and strictly increasing resolutions; global and normal '
    'closure promotion remains open'
    if cross_case
    else 'canonical-consumer evidence passed independent replay across a '
    'strictly increasing resolution ladder for one source case; a disjoint '
    'source-closure gate remains open'
    if local_coverage
    else 'canonical-consumer evidence was retained, but case, resolution, '
    'lineage, feedback, audit, or fidelity-isolation gates remain open'
  )
  return _measurement(
    status,
    message,
    steps=retained,
    case_ids_verified=case_ids_verified,
    source_closure_bindings_verified=source_bindings,
    distinct_source_closures_verified=distinct_sources,
    resolution_ladders_verified=resolution_ladders_verified,
    feedback_resolutions_verified=feedback_resolutions,
    research_consumption_verified=research_consumption,
    independent_audits_verified=independent_audits,
    fidelity_isolation_verified=fidelity_isolation,
    local_coverage_verified=local_coverage,
    cross_case_coverage_verified=cross_case,
    canonical_free_boundary_verified=False,
    global_coupling_verified=False,
    external_validation_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
  )
####


def run_reflected_domain_global_mixed_regime_canonical_consumer_refinement(
  cases: Sequence[
    MocReflectedDomainGlobalMixedRegimeCanonicalConsumerRefinementCase
  ],
  *,
  expected_case_ids: Sequence[str] | None = None,
) -> MocReflectedDomainGlobalMixedRegimeCanonicalConsumerRefinementMeasurement:
  """Consume and independently audit each declared case/resolution input."""

  status_type = MocReflectedDomainGlobalMixedRegimeCanonicalConsumerRefinementStatus
  try:
    retained_cases = tuple(cases)
  except TypeError:
    return _measurement(status_type.INVALID_INPUT, 'cases must be iterable')
  ####
  if len(retained_cases) < 2:
    return _measurement(
      status_type.INVALID_INPUT,
      'canonical-consumer refinement requires at least two cases/resolutions',
    )
  ####
  if any(
    not isinstance(
      case,
      MocReflectedDomainGlobalMixedRegimeCanonicalConsumerRefinementCase,
    )
    for case in retained_cases
  ):
    return _measurement(
      status_type.INVALID_INPUT,
      'cases must contain typed canonical-consumer refinement cases',
    )
  ####
  steps: list[
    MocReflectedDomainGlobalMixedRegimeCanonicalConsumerRefinementStep
  ] = []
  try:
    for case in retained_cases:
      result = consume_reflected_domain_global_mixed_regime_canonical_source(
        case.request
      )
      audit = audit_reflected_domain_global_mixed_regime_canonical_source(result)
      steps.append(
        MocReflectedDomainGlobalMixedRegimeCanonicalConsumerRefinementStep(
          case_id=case.case_id,
          resolution=case.resolution,
          request=case.request,
          result=result,
          audit=audit,
        )
      )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _measurement(
      status_type.CONSUMER_FAILURE,
      f'canonical-consumer refinement execution failed: {error}',
      steps=steps,
    )
  ####
  return measure_reflected_domain_global_mixed_regime_canonical_consumer_refinement(
    steps,
    expected_case_ids=expected_case_ids,
  )
####
