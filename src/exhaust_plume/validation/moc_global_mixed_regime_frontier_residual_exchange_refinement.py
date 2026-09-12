"""Disjoint case/resolution coverage for frontier residual exchange.

The single-case residual exchange is useful only if the same solver-owned
constraint survives changes in source closure and exact shock-frontier
resolution.  This module runs that exchange independently for each declared
case, audits every response, and keeps component-wise admission separate from
mere replayability.  It remains a research gate and cannot promote a rejected
or unvalidated response into canonical/global or production claims.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any

from exhaust_plume.models.moc.global_physical_closure import (
  MocReflectedDomainGlobalPhysicalClosureResult,
)
from exhaust_plume.validation.moc_global_mixed_regime_frontier_residual_exchange import (
  MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeAudit,
  MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeRequest,
  MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeResult,
  audit_reflected_domain_global_mixed_regime_frontier_residual_exchange,
  run_reflected_domain_global_mixed_regime_frontier_residual_exchange,
)
from exhaust_plume.validation.moc_global_mixed_regime_shock_frontier_refinement import (
  MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementStep,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_FRONTIER_RESIDUAL_EXCHANGE_REFINEMENT_OPERATOR_ID',
  'MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeRefinementStatus',
  'MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeRefinementCase',
  'MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeRefinementStep',
  'MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeRefinementMeasurement',
  'run_reflected_domain_global_mixed_regime_frontier_residual_exchange_refinement',
  'measure_reflected_domain_global_mixed_regime_frontier_residual_exchange_refinement',
)


MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_FRONTIER_RESIDUAL_EXCHANGE_REFINEMENT_OPERATOR_ID = (
  'op.moc.reflected-domain.global-mixed-regime-frontier-residual-exchange-refinement-v1'
)


class MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeRefinementStatus(
  str,
  Enum,
):
  """Typed outcomes of disjoint frontier residual-exchange coverage."""

  CONVERGED_LOCAL_RESEARCH_COVERAGE = (
    'converged-local-research-frontier-residual-exchange-coverage'
  )
  CONVERGED_CROSS_CASE_RESEARCH_COVERAGE = (
    'converged-cross-case-research-frontier-residual-exchange-coverage'
  )
  COMPLETED_RESEARCH_COVERAGE_WITH_OPEN_GATE = (
    'completed-research-frontier-residual-exchange-coverage-with-open-gate'
  )
  INVALID_INPUT = 'invalid_input'
  EXCHANGE_FAILURE = 'frontier-residual-exchange-refinement-exchange-failure'


def _positive(value: object, name: str) -> float:
  numeric = float(value)
  if numeric != numeric or numeric in (float('inf'), float('-inf')) or numeric <= 0.0:
    raise ValueError(f'{name} must be finite and positive')
  return numeric


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeRefinementCase:
  """One named source closure/resolution point in the exchange ladder."""

  case_id: str
  source_frontier_step: MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementStep
  target_closure: MocReflectedDomainGlobalPhysicalClosureResult
  reference_total_temperature_K: float
  maximum_iterations: int = 1
  probe_displacement_m: float = 1.0e-4
  maximum_displacement_m: float = 1.0e-3
  relaxation: float = 0.5
  source: str = 'research-global-mixed-regime-frontier-residual-exchange-refinement-v1'

  def __post_init__(self) -> None:
    case_id = str(self.case_id)
    if not case_id:
      raise ValueError('case_id must be non-empty')
    if not isinstance(
      self.source_frontier_step,
      MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementStep,
    ):
      raise TypeError('source_frontier_step must be a typed frontier step')
    if not self.source_frontier_step.locally_verified:
      raise ValueError('source_frontier_step must be locally verified')
    if self.source_frontier_step.case_id != case_id:
      raise ValueError('case_id must match source_frontier_step.case_id')
    if not isinstance(
      self.target_closure,
      MocReflectedDomainGlobalPhysicalClosureResult,
    ):
      raise TypeError('target_closure must be a typed global physical closure')
    if (
      isinstance(self.maximum_iterations, bool)
      or not isinstance(self.maximum_iterations, int)
      or self.maximum_iterations < 1
    ):
      raise ValueError('maximum_iterations must be a positive integer')
    source = str(self.source)
    if not source:
      raise ValueError('source must be non-empty')
    object.__setattr__(self, 'case_id', case_id)
    object.__setattr__(
      self,
      'reference_total_temperature_K',
      _positive(self.reference_total_temperature_K, 'reference_total_temperature_K'),
    )
    for name in (
      'probe_displacement_m',
      'maximum_displacement_m',
    ):
      object.__setattr__(self, name, _positive(getattr(self, name), name))
    relaxation = _positive(self.relaxation, 'relaxation')
    if relaxation > 1.0:
      raise ValueError('relaxation must be no greater than one')
    if self.probe_displacement_m > self.maximum_displacement_m:
      raise ValueError('probe_displacement_m cannot exceed maximum_displacement_m')
    object.__setattr__(self, 'relaxation', relaxation)
    object.__setattr__(self, 'source', source)

  @property
  def frontier_sample_count(self) -> int:
    return self.source_frontier_step.frontier_sample_count

  @property
  def source_closure_fingerprint(self) -> str:
    return self.source_frontier_step.source_closure_fingerprint

  def as_request(self) -> MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeRequest:
    return MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeRequest(
      source_frontier_step=self.source_frontier_step,
      target_closure=self.target_closure,
      reference_total_temperature_K=self.reference_total_temperature_K,
      maximum_iterations=self.maximum_iterations,
      probe_displacement_m=self.probe_displacement_m,
      maximum_displacement_m=self.maximum_displacement_m,
      relaxation=self.relaxation,
      source=self.source,
    )

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_FRONTIER_RESIDUAL_EXCHANGE_REFINEMENT_OPERATOR_ID,
      'case_id': self.case_id,
      'frontier_sample_count': self.frontier_sample_count,
      'source_closure_fingerprint': self.source_closure_fingerprint,
      'target_closure_fingerprint': self.as_request().as_report()['target_closure_fingerprint'],
      'reference_total_temperature_K': self.reference_total_temperature_K,
      'maximum_iterations': self.maximum_iterations,
      'probe_displacement_m': self.probe_displacement_m,
      'maximum_displacement_m': self.maximum_displacement_m,
      'relaxation': self.relaxation,
      'source': self.source,
      'research_only': True,
      'production_claim_allowed': False,
    }


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeRefinementStep:
  """One independently executed and audited refinement case."""

  case: MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeRefinementCase
  result: MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeResult
  audit: MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeAudit

  def __post_init__(self) -> None:
    if not isinstance(
      self.case,
      MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeRefinementCase,
    ):
      raise TypeError('case must be a typed refinement case')
    if not isinstance(
      self.result,
      MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeResult,
    ):
      raise TypeError('result must be a typed residual-exchange result')
    if not isinstance(
      self.audit,
      MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeAudit,
    ):
      raise TypeError('audit must be a typed residual-exchange audit')

  @property
  def exchange_consumed(self) -> bool:
    return bool(
      self.result.geometry_update_attempted
      and self.result.geometry_update_consumed
    )

  @property
  def independent_replay_verified(self) -> bool:
    return bool(
      self.audit.converged
      and self.audit.request_replayed
      and self.audit.packet_replayed
      and self.audit.update_replayed
      and self.audit.response_replayed
      and self.audit.independent_exchange_verified
    )

  @property
  def componentwise_admission_verified(self) -> bool:
    return bool(
      self.result.componentwise_non_worsening
      and self.result.strict_component_descent
    )

  @property
  def accepted_update_verified(self) -> bool:
    return bool(self.result.converged and self.independent_replay_verified)

  @property
  def source_lineage_verified(self) -> bool:
    return bool(
      self.result.source_packet is not None
      and self.result.source_packet.source_closure_fingerprint
      == self.case.source_closure_fingerprint
      and self.result.source_packet.sample_count
      == self.case.frontier_sample_count - self.case.source_frontier_step.sample_start_index
    )

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
    )

  @property
  def locally_verified(self) -> bool:
    return bool(
      self.exchange_consumed
      and self.source_lineage_verified
      and self.independent_replay_verified
      and self.componentwise_admission_verified
      and self.accepted_update_verified
      and self.fidelity_isolation_verified
    )

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_FRONTIER_RESIDUAL_EXCHANGE_REFINEMENT_OPERATOR_ID,
      'case': self.case.as_report(),
      'result': self.result.as_report(),
      'audit': self.audit.as_report(),
      'checks': {
        'exchange_consumed': self.exchange_consumed,
        'source_lineage_verified': self.source_lineage_verified,
        'independent_replay_verified': self.independent_replay_verified,
        'componentwise_admission_verified': self.componentwise_admission_verified,
        'accepted_update_verified': self.accepted_update_verified,
        'fidelity_isolation_verified': self.fidelity_isolation_verified,
        'locally_verified': self.locally_verified,
      },
    }


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeRefinementMeasurement:
  """Disjoint frontier residual-exchange evidence below promotion ceilings."""

  status: MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeRefinementStatus
  steps: tuple[MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeRefinementStep, ...] = ()
  case_ids: tuple[str, ...] = ()
  frontier_sample_counts: tuple[int, ...] = ()
  source_closure_fingerprints: tuple[str, ...] = ()
  local_case_resolution_ladders_verified: bool = False
  distinct_source_closures_verified: bool = False
  source_lineage_verified: bool = False
  exchange_consumed_verified: bool = False
  independent_replay_verified: bool = False
  componentwise_admission_verified: bool = False
  accepted_update_verified: bool = False
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
      MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeRefinementStatus,
    ):
      raise TypeError('status must be a typed refinement status')
    steps = tuple(self.steps)
    if any(
      not isinstance(
        step,
        MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeRefinementStep,
      )
      for step in steps
    ):
      raise TypeError('steps must contain typed refinement steps')
    case_ids = tuple(str(step.case.case_id) for step in steps)
    counts = tuple(step.case.frontier_sample_count for step in steps)
    fingerprints = tuple(step.case.source_closure_fingerprint for step in steps)
    if self.case_ids and tuple(self.case_ids) != case_ids:
      raise ValueError('case_ids must match retained refinement steps')
    if self.frontier_sample_counts and tuple(self.frontier_sample_counts) != counts:
      raise ValueError('frontier_sample_counts must match retained refinement steps')
    if self.source_closure_fingerprints and tuple(self.source_closure_fingerprints) != fingerprints:
      raise ValueError('source_closure_fingerprints must match retained refinement steps')
    for name in (
      'local_case_resolution_ladders_verified',
      'distinct_source_closures_verified',
      'source_lineage_verified',
      'exchange_consumed_verified',
      'independent_replay_verified',
      'componentwise_admission_verified',
      'accepted_update_verified',
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
    if self.canonical_free_boundary_verified or self.global_coupling_verified:
      raise ValueError('refinement cannot claim canonical/global closure')
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError('refinement must remain promotion-blocked')
    object.__setattr__(self, 'steps', steps)
    object.__setattr__(self, 'case_ids', case_ids)
    object.__setattr__(self, 'frontier_sample_counts', counts)
    object.__setattr__(self, 'source_closure_fingerprints', fingerprints)
    object.__setattr__(self, 'message', str(self.message))

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      in {
        MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeRefinementStatus
        .CONVERGED_LOCAL_RESEARCH_COVERAGE,
        MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeRefinementStatus
        .CONVERGED_CROSS_CASE_RESEARCH_COVERAGE,
      }
      and self.local_coverage_verified
      and self.fidelity_isolation_verified
    )

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_FRONTIER_RESIDUAL_EXCHANGE_REFINEMENT_OPERATOR_ID,
      'status': self.status.value,
      'converged': self.converged,
      'case_ids': self.case_ids,
      'frontier_sample_counts': self.frontier_sample_counts,
      'source_closure_fingerprints': self.source_closure_fingerprints,
      'checks': {
        'local_case_resolution_ladders_verified': self.local_case_resolution_ladders_verified,
        'distinct_source_closures_verified': self.distinct_source_closures_verified,
        'source_lineage_verified': self.source_lineage_verified,
        'exchange_consumed_verified': self.exchange_consumed_verified,
        'independent_replay_verified': self.independent_replay_verified,
        'componentwise_admission_verified': self.componentwise_admission_verified,
        'accepted_update_verified': self.accepted_update_verified,
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


def _measurement(
  status: MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeRefinementStatus,
  message: str,
  *,
  steps: Sequence[MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeRefinementStep] = (),
  **flags: bool,
) -> MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeRefinementMeasurement:
  retained = tuple(steps)
  return MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeRefinementMeasurement(
    status=status,
    steps=retained,
    case_ids=tuple(step.case.case_id for step in retained),
    frontier_sample_counts=tuple(step.case.frontier_sample_count for step in retained),
    source_closure_fingerprints=tuple(
      step.case.source_closure_fingerprint for step in retained
    ),
    **flags,
    message=message,
  )


def _strictly_increasing(values: Sequence[int]) -> bool:
  return bool(
    len(values) >= 2
    and all(right > left for left, right in zip(values, values[1:]))
  )


def measure_reflected_domain_global_mixed_regime_frontier_residual_exchange_refinement(
  steps: Sequence[MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeRefinementStep],
  *,
  expected_case_ids: Sequence[str] | None = None,
) -> MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeRefinementMeasurement:
  """Measure disjoint residual-exchange evidence without promoting it."""

  status_type = MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeRefinementStatus
  try:
    retained = tuple(steps)
  except TypeError:
    return _measurement(status_type.INVALID_INPUT, 'steps must be iterable')
  if len(retained) < 2 or any(
    not isinstance(
      step,
      MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeRefinementStep,
    )
    for step in retained
  ):
    return _measurement(
      status_type.INVALID_INPUT,
      'refinement requires at least two typed residual-exchange steps',
    )
  ####
  grouped: dict[str, list[MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeRefinementStep]] = {}
  for step in retained:
    grouped.setdefault(step.case.case_id, []).append(step)
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
      _strictly_increasing(
        tuple(step.case.frontier_sample_count for step in case_steps)
      )
      for case_steps in grouped.values()
    )
  )
  fingerprints = tuple(step.case.source_closure_fingerprint for step in retained)
  distinct_sources = bool(len(grouped) >= 2 and len(set(fingerprints)) >= 2)
  source_lineage = all(step.source_lineage_verified for step in retained)
  exchange_consumed = all(step.exchange_consumed for step in retained)
  independent_replay = all(step.independent_replay_verified for step in retained)
  componentwise_admission = all(
    step.componentwise_admission_verified for step in retained
  )
  accepted_update = all(step.accepted_update_verified for step in retained)
  fidelity_isolation = all(step.fidelity_isolation_verified for step in retained)
  local_coverage = bool(
    case_ids_verified
    and source_lineage
    and exchange_consumed
    and independent_replay
    and componentwise_admission
    and accepted_update
    and fidelity_isolation
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
    (source_lineage, 'source lineage'),
    (exchange_consumed, 'solver-owned exchange consumption'),
    (independent_replay, 'independent replay'),
    (componentwise_admission, 'component-wise non-worsening and descent'),
    (accepted_update, 'accepted residual update'),
    (fidelity_isolation, 'fidelity isolation'),
  ):
    if not verified:
      open_gates.append(label)
  message = (
    'frontier residual exchange passed independent replay across distinct '
    'source closures and strictly increasing exact shock resolutions; '
    'canonical/global and production promotion remain open'
    if cross_case
    else 'frontier residual exchange evidence was retained, but open gates '
    f'remain: {", ".join(open_gates) if open_gates else "cross-case coverage"}'
  )
  return _measurement(
    status,
    message,
    steps=retained,
    local_case_resolution_ladders_verified=ladders,
    distinct_source_closures_verified=distinct_sources,
    source_lineage_verified=source_lineage,
    exchange_consumed_verified=exchange_consumed,
    independent_replay_verified=independent_replay,
    componentwise_admission_verified=componentwise_admission,
    accepted_update_verified=accepted_update,
    fidelity_isolation_verified=fidelity_isolation,
    local_coverage_verified=local_coverage,
    cross_case_coverage_verified=cross_case,
    canonical_free_boundary_verified=False,
    global_coupling_verified=False,
    external_validation_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
  )


def run_reflected_domain_global_mixed_regime_frontier_residual_exchange_refinement(
  cases: Sequence[MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeRefinementCase],
  *,
  expected_case_ids: Sequence[str] | None = None,
) -> MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeRefinementMeasurement:
  """Run and independently audit each declared exchange-ladder case."""

  status_type = MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeRefinementStatus
  try:
    retained_cases = tuple(cases)
  except TypeError:
    return _measurement(status_type.INVALID_INPUT, 'cases must be iterable')
  if len(retained_cases) < 2 or any(
    not isinstance(
      case,
      MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeRefinementCase,
    )
    for case in retained_cases
  ):
    return _measurement(
      status_type.INVALID_INPUT,
      'cases must contain at least two typed refinement cases',
    )
  ####
  steps: list[MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeRefinementStep] = []
  for case in retained_cases:
    try:
      request = case.as_request()
      result = run_reflected_domain_global_mixed_regime_frontier_residual_exchange(
        request
      )
      audit = audit_reflected_domain_global_mixed_regime_frontier_residual_exchange(
        result
      )
      steps.append(
        MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeRefinementStep(
          case=case,
          result=result,
          audit=audit,
        )
      )
    except (ArithmeticError, FloatingPointError, RuntimeError, TypeError, ValueError) as error:
      return _measurement(
        status_type.EXCHANGE_FAILURE,
        f'frontier residual-exchange refinement failed: {error}',
        steps=steps,
      )
  return measure_reflected_domain_global_mixed_regime_frontier_residual_exchange_refinement(
    steps,
    expected_case_ids=expected_case_ids,
  )
