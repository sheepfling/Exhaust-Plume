"""Refinement and cross-case evidence for the global pressure consumer.

The pressure-conditioned global boundary operator proves one fresh solve.  It
does not, by itself, prove that the solver-owned field is stable under a
declared resolution change or that the result transfers across disjoint
cases.  This module provides those two independent evidence surfaces while
keeping the canonical global/free-boundary and production gates closed.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from math import isfinite
from typing import Any

from exhaust_plume.models.moc.global_frontier_reconciliation import (
  MocReflectedDomainGlobalFrontierReconciliationRequest,
  moc_reflected_domain_global_frontier_proposal_fingerprint,
)
from exhaust_plume.models.moc.global_physical_closure import (
  MocReflectedDomainGlobalPhysicalClosureResult,
  moc_reflected_domain_global_physical_closure_fingerprint,
)
from exhaust_plume.validation.moc_global_frontier_boundary_condition import (
  MocReflectedDomainGlobalFrontierBoundaryConditionResult,
  run_reflected_domain_global_frontier_boundary_conditioned_resolve,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_FRONTIER_BOUNDARY_CONDITION_REFINEMENT_OPERATOR_ID',
  'MOC_REFLECTED_DOMAIN_GLOBAL_FRONTIER_BOUNDARY_CONDITION_CROSS_CASE_REFINEMENT_OPERATOR_ID',
  'MocReflectedDomainGlobalFrontierBoundaryConditionRefinementStatus',
  'MocReflectedDomainGlobalFrontierBoundaryConditionRefinementStep',
  'MocReflectedDomainGlobalFrontierBoundaryConditionRefinementMeasurement',
  'MocReflectedDomainGlobalFrontierBoundaryConditionRefinementResult',
  'run_reflected_domain_global_frontier_boundary_condition_refinement',
  'MocReflectedDomainGlobalFrontierBoundaryConditionCrossCase',
  'MocReflectedDomainGlobalFrontierBoundaryConditionCrossCaseMeasurement',
  'MocReflectedDomainGlobalFrontierBoundaryConditionCrossCaseRun',
  'run_reflected_domain_global_frontier_boundary_condition_cross_case_refinement',
)


MOC_REFLECTED_DOMAIN_GLOBAL_FRONTIER_BOUNDARY_CONDITION_REFINEMENT_OPERATOR_ID = (
  'op.moc.reflected-domain.global-frontier-boundary-condition-refinement'
)
MOC_REFLECTED_DOMAIN_GLOBAL_FRONTIER_BOUNDARY_CONDITION_CROSS_CASE_REFINEMENT_OPERATOR_ID = (
  'op.moc.reflected-domain.global-frontier-boundary-condition-cross-case-refinement'
)


class MocReflectedDomainGlobalFrontierBoundaryConditionRefinementStatus(
  str, Enum
):
  """Outcome of global pressure-consumer refinement evidence."""

  CONVERGED_RESEARCH_LADDER = (
    'converged-research-global-frontier-boundary-condition-refinement'
  )
  INVALID_INPUT = 'invalid_input'
  SOURCE_CLOSURE_FAILURE = (
    'global-frontier-boundary-condition-refinement-source-failure'
  )
  RESOLVE_FAILURE = (
    'global-frontier-boundary-condition-refinement-resolve-failure'
  )
  TARGET_COVERAGE_FAILURE = (
    'global-frontier-boundary-condition-refinement-target-coverage-failure'
  )
  TARGET_MISMATCH = (
    'global-frontier-boundary-condition-refinement-target-mismatch'
  )
  FIDELITY_FAILURE = (
    'global-frontier-boundary-condition-refinement-fidelity-failure'
  )
  CONVERGED_RESEARCH_CROSS_CASE = (
    'converged-research-global-frontier-boundary-condition-cross-case'
  )
  CROSS_CASE_FAILURE = (
    'global-frontier-boundary-condition-cross-case-failure'
  )
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


def _sample_counts(values: Sequence[int]) -> tuple[int, ...]:
  resolved = tuple(values)
  if len(resolved) < 2:
    raise ValueError('sample_counts must contain at least two resolutions')
  ####
  if any(
    isinstance(value, bool) or not isinstance(value, int) or value < 3
    for value in resolved
  ):
    raise ValueError('sample_counts must contain integers >= 3')
  ####
  if any(right <= left for left, right in zip(resolved, resolved[1:])):
    raise ValueError('sample_counts must be strictly increasing')
  ####
  return resolved
####


def _finite_channels(
  result: MocReflectedDomainGlobalFrontierBoundaryConditionResult,
) -> bool:
  channels = (
    result.coordinate_residuals_m,
    result.tangent_residuals_rad,
    result.pressure_residuals_Pa,
  )
  return bool(channels[0]) and all(
    isfinite(value)
    for channel in channels
    for value in channel
  )
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalFrontierBoundaryConditionRefinementStep:
  """One fresh pressure-conditioned global solve at one sample resolution."""

  sample_count: int
  result: MocReflectedDomainGlobalFrontierBoundaryConditionResult | None
  fresh_global_solve_verified: bool = False
  source_lineage_verified: bool = False
  target_lineage_verified: bool = False
  target_consumption_verified: bool = False
  target_coverage_verified: bool = False
  target_match_verified: bool = False
  residuals_finite: bool = False
  solver_owned_geometry_verified: bool = False
  fidelity_isolation_verified: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if (
      isinstance(self.sample_count, bool)
      or not isinstance(self.sample_count, int)
      or self.sample_count < 3
    ):
      raise ValueError('sample_count must be an integer >= 3')
    ####
    if self.result is not None and not isinstance(
      self.result,
      MocReflectedDomainGlobalFrontierBoundaryConditionResult,
    ):
      raise TypeError(
        'result must be a '
        'MocReflectedDomainGlobalFrontierBoundaryConditionResult or None'
      )
    ####
    for name in (
      'fresh_global_solve_verified',
      'source_lineage_verified',
      'target_lineage_verified',
      'target_consumption_verified',
      'target_coverage_verified',
      'target_match_verified',
      'residuals_finite',
      'solver_owned_geometry_verified',
      'fidelity_isolation_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def research_step_verified(self) -> bool:
    return bool(
      self.result is not None
      and self.result.converged_research_resolve
      and self.fresh_global_solve_verified
      and self.source_lineage_verified
      and self.target_lineage_verified
      and self.target_consumption_verified
      and self.target_coverage_verified
      and self.target_match_verified
      and self.residuals_finite
      and self.solver_owned_geometry_verified
      and self.fidelity_isolation_verified
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'sample_count': self.sample_count,
      'research_step_verified': self.research_step_verified,
      'fresh_global_solve_verified': self.fresh_global_solve_verified,
      'source_lineage_verified': self.source_lineage_verified,
      'target_lineage_verified': self.target_lineage_verified,
      'target_consumption_verified': self.target_consumption_verified,
      'target_coverage_verified': self.target_coverage_verified,
      'target_match_verified': self.target_match_verified,
      'residuals_finite': self.residuals_finite,
      'solver_owned_geometry_verified': self.solver_owned_geometry_verified,
      'fidelity_isolation_verified': self.fidelity_isolation_verified,
      'result': None if self.result is None else self.result.as_report(),
      'message': self.message,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalFrontierBoundaryConditionRefinementMeasurement:
  """Independent aggregate evidence for one resolution ladder."""

  status: MocReflectedDomainGlobalFrontierBoundaryConditionRefinementStatus
  requested_sample_counts: tuple[int, ...]
  steps: tuple[
    MocReflectedDomainGlobalFrontierBoundaryConditionRefinementStep, ...
  ] = ()
  resolution_order_verified: bool = False
  fresh_global_solves_verified: bool = False
  source_lineage_verified: bool = False
  target_lineage_verified: bool = False
  target_consumption_verified: bool = False
  target_coverage_verified: bool = False
  target_match_verified: bool = False
  residuals_finite: bool = False
  solver_owned_geometry_verified: bool = False
  fidelity_isolation_verified: bool = False
  global_coupling_verified: bool = False
  downstream_boundary_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  external_validation_required: bool = True
  operator_id: str = (
    MOC_REFLECTED_DOMAIN_GLOBAL_FRONTIER_BOUNDARY_CONDITION_REFINEMENT_OPERATOR_ID
  )
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalFrontierBoundaryConditionRefinementStatus,
    ):
      raise TypeError(
        'status must be a '
        'MocReflectedDomainGlobalFrontierBoundaryConditionRefinementStatus'
      )
    ####
    counts = _sample_counts(self.requested_sample_counts)
    steps = tuple(self.steps)
    if any(
      not isinstance(
        step,
        MocReflectedDomainGlobalFrontierBoundaryConditionRefinementStep,
      )
      for step in steps
    ):
      raise TypeError('steps must contain typed refinement steps')
    ####
    if steps and tuple(step.sample_count for step in steps) != counts:
      raise ValueError('steps must match requested_sample_counts')
    ####
    for name in (
      'resolution_order_verified',
      'fresh_global_solves_verified',
      'source_lineage_verified',
      'target_lineage_verified',
      'target_consumption_verified',
      'target_coverage_verified',
      'target_match_verified',
      'residuals_finite',
      'solver_owned_geometry_verified',
      'fidelity_isolation_verified',
      'global_coupling_verified',
      'downstream_boundary_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
      'external_validation_required',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if self.global_coupling_verified or self.downstream_boundary_closure_verified:
      raise ValueError(
        'global boundary-condition refinement cannot claim canonical closure'
      )
    ####
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError(
        'global boundary-condition refinement must remain promotion-blocked'
      )
    ####
    if not self.external_validation_required:
      raise ValueError(
        'global boundary-condition refinement must retain external validation'
      )
    ####
    object.__setattr__(self, 'requested_sample_counts', counts)
    object.__setattr__(self, 'steps', steps)
    object.__setattr__(self, 'operator_id', str(self.operator_id))
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalFrontierBoundaryConditionRefinementStatus
      .CONVERGED_RESEARCH_LADDER
      and self.resolution_order_verified
      and len(self.steps) >= 2
      and self.fresh_global_solves_verified
      and self.source_lineage_verified
      and self.target_lineage_verified
      and self.target_consumption_verified
      and self.target_coverage_verified
      and self.target_match_verified
      and self.residuals_finite
      and self.solver_owned_geometry_verified
      and self.fidelity_isolation_verified
      and self.external_validation_required
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
      and all(step.research_step_verified for step in self.steps)
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': self.operator_id,
      'status': self.status.value,
      'converged': self.converged,
      'requested_sample_counts': self.requested_sample_counts,
      'checks': {
        'resolution_order_verified': self.resolution_order_verified,
        'fresh_global_solves_verified': self.fresh_global_solves_verified,
        'source_lineage_verified': self.source_lineage_verified,
        'target_lineage_verified': self.target_lineage_verified,
        'target_consumption_verified': self.target_consumption_verified,
        'target_coverage_verified': self.target_coverage_verified,
        'target_match_verified': self.target_match_verified,
        'residuals_finite': self.residuals_finite,
        'solver_owned_geometry_verified': self.solver_owned_geometry_verified,
        'fidelity_isolation_verified': self.fidelity_isolation_verified,
        'external_validation_required': self.external_validation_required,
        'chain_promotion_blocked': self.chain_promotion_blocked,
        'production_claim_allowed': self.production_claim_allowed,
      },
      'global_coupling_verified': self.global_coupling_verified,
      'downstream_boundary_closure_verified': (
        self.downstream_boundary_closure_verified
      ),
      'canonical_free_boundary_verified': False,
      'canonical_euler_verified': False,
      'external_validation_verified': False,
      'steps': tuple(step.as_report() for step in self.steps),
      'message': self.message,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalFrontierBoundaryConditionRefinementResult:
  """One source-bound resolution ladder for the pressure consumer."""

  request: MocReflectedDomainGlobalFrontierReconciliationRequest
  source_closure: MocReflectedDomainGlobalPhysicalClosureResult
  requested_sample_counts: tuple[int, ...]
  measurement: MocReflectedDomainGlobalFrontierBoundaryConditionRefinementMeasurement
  configuration: dict[str, Any]
  configuration_fingerprint: str
  fresh_solver_invocation_verified: bool = False
  fidelity_isolation_verified: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.request,
      MocReflectedDomainGlobalFrontierReconciliationRequest,
    ):
      raise TypeError(
        'request must be a '
        'MocReflectedDomainGlobalFrontierReconciliationRequest'
      )
    ####
    if not isinstance(
      self.source_closure,
      MocReflectedDomainGlobalPhysicalClosureResult,
    ):
      raise TypeError(
        'source_closure must be a MocReflectedDomainGlobalPhysicalClosureResult'
      )
    ####
    counts = _sample_counts(self.requested_sample_counts)
    if not isinstance(
      self.measurement,
      MocReflectedDomainGlobalFrontierBoundaryConditionRefinementMeasurement,
    ):
      raise TypeError(
        'measurement must be a '
        'MocReflectedDomainGlobalFrontierBoundaryConditionRefinementMeasurement'
      )
    ####
    if counts != self.measurement.requested_sample_counts:
      raise ValueError('requested_sample_counts must match the measurement')
    ####
    configuration = dict(self.configuration)
    expected_fingerprint = _configuration_fingerprint(configuration)
    if self.configuration_fingerprint != expected_fingerprint:
      raise ValueError('configuration_fingerprint does not match configuration')
    ####
    if not isinstance(self.fresh_solver_invocation_verified, bool):
      raise TypeError('fresh_solver_invocation_verified must be a bool')
    ####
    if not isinstance(self.fidelity_isolation_verified, bool):
      raise TypeError('fidelity_isolation_verified must be a bool')
    ####
    object.__setattr__(self, 'requested_sample_counts', counts)
    object.__setattr__(self, 'configuration', configuration)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.measurement.converged
      and self.fresh_solver_invocation_verified
      and self.fidelity_isolation_verified
    )
  ####

  @property
  def production_claim_allowed(self) -> bool:
    return False
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': self.measurement.operator_id,
      'converged': self.converged,
      'requested_sample_counts': self.requested_sample_counts,
      'fresh_solver_invocation_verified': self.fresh_solver_invocation_verified,
      'fidelity_isolation_verified': self.fidelity_isolation_verified,
      'source_closure_fingerprint': (
        moc_reflected_domain_global_physical_closure_fingerprint(
          self.source_closure
        )
      ),
      'source_proposal_fingerprint': (
        moc_reflected_domain_global_frontier_proposal_fingerprint(
          self.request.proposal
        )
      ),
      'configuration': self.configuration,
      'configuration_fingerprint': self.configuration_fingerprint,
      'measurement': self.measurement.as_report(),
      'message': self.message,
    }
  ####
####


def measure_reflected_domain_global_frontier_boundary_condition_refinement(
  request: MocReflectedDomainGlobalFrontierReconciliationRequest,
  source_closure: MocReflectedDomainGlobalPhysicalClosureResult,
  steps: Sequence[
    MocReflectedDomainGlobalFrontierBoundaryConditionRefinementStep
  ],
) -> MocReflectedDomainGlobalFrontierBoundaryConditionRefinementMeasurement:
  """Independently aggregate typed pressure-consumer refinement steps."""

  if not isinstance(
    request,
    MocReflectedDomainGlobalFrontierReconciliationRequest,
  ):
    raise TypeError(
      'request must be a '
      'MocReflectedDomainGlobalFrontierReconciliationRequest'
    )
  ####
  if not isinstance(
    source_closure,
    MocReflectedDomainGlobalPhysicalClosureResult,
  ):
    raise TypeError(
      'source_closure must be a MocReflectedDomainGlobalPhysicalClosureResult'
    )
  ####
  resolved_steps = tuple(steps)
  counts = tuple(step.sample_count for step in resolved_steps)
  requested = _sample_counts(counts)
  source_fingerprint = moc_reflected_domain_global_physical_closure_fingerprint(
    source_closure
  )
  source_lineage = bool(
    request.lineage_verified
    and request.source_closure_fingerprint == source_fingerprint
  )
  resolution_order = bool(
    len(counts) >= 2
    and all(right > left for left, right in zip(counts, counts[1:]))
  )
  fresh_solves = bool(
    resolved_steps
    and all(step.fresh_global_solve_verified for step in resolved_steps)
  )
  target_lineage = bool(
    resolved_steps
    and all(step.target_lineage_verified for step in resolved_steps)
  )
  target_consumption = bool(
    resolved_steps
    and all(step.target_consumption_verified for step in resolved_steps)
  )
  target_coverage = bool(
    resolved_steps
    and all(step.target_coverage_verified for step in resolved_steps)
  )
  target_match = bool(
    resolved_steps
    and all(step.target_match_verified for step in resolved_steps)
  )
  residuals_finite = bool(
    resolved_steps and all(step.residuals_finite for step in resolved_steps)
  )
  solver_owned_geometry = bool(
    resolved_steps
    and all(step.solver_owned_geometry_verified for step in resolved_steps)
  )
  fidelity = bool(
    resolved_steps
    and all(step.fidelity_isolation_verified for step in resolved_steps)
  )
  local = bool(
    source_lineage
    and resolution_order
    and fresh_solves
    and target_lineage
    and target_consumption
    and target_coverage
    and target_match
    and residuals_finite
    and solver_owned_geometry
    and fidelity
  )
  if local:
    status = (
      MocReflectedDomainGlobalFrontierBoundaryConditionRefinementStatus
      .CONVERGED_RESEARCH_LADDER
    )
  elif not resolution_order:
    status = (
      MocReflectedDomainGlobalFrontierBoundaryConditionRefinementStatus
      .INVALID_INPUT
    )
  elif not fresh_solves:
    status = (
      MocReflectedDomainGlobalFrontierBoundaryConditionRefinementStatus
      .RESOLVE_FAILURE
    )
  elif not target_coverage:
    status = (
      MocReflectedDomainGlobalFrontierBoundaryConditionRefinementStatus
      .TARGET_COVERAGE_FAILURE
    )
  elif not target_match:
    status = (
      MocReflectedDomainGlobalFrontierBoundaryConditionRefinementStatus
      .TARGET_MISMATCH
    )
  else:
    status = (
      MocReflectedDomainGlobalFrontierBoundaryConditionRefinementStatus
      .FIDELITY_FAILURE
    )
  ####
  return MocReflectedDomainGlobalFrontierBoundaryConditionRefinementMeasurement(
    status=status,
    requested_sample_counts=requested,
    steps=resolved_steps,
    resolution_order_verified=resolution_order,
    fresh_global_solves_verified=fresh_solves,
    source_lineage_verified=source_lineage,
    target_lineage_verified=target_lineage,
    target_consumption_verified=target_consumption,
    target_coverage_verified=target_coverage,
    target_match_verified=target_match,
    residuals_finite=residuals_finite,
    solver_owned_geometry_verified=solver_owned_geometry,
    fidelity_isolation_verified=fidelity,
    message=(
      'solver-owned global pressure-consumer refinement passed local '
      'resolution, residual, and lineage checks; canonical closure remains '
      'blocked'
      if local
      else 'solver-owned global pressure-consumer refinement did not pass '
      'every local resolution, residual, or lineage check'
    ),
  )
####


def run_reflected_domain_global_frontier_boundary_condition_refinement(
  request: MocReflectedDomainGlobalFrontierReconciliationRequest,
  source_closure: MocReflectedDomainGlobalPhysicalClosureResult,
  *,
  sample_counts: Sequence[int],
  position_tolerance_m: float = 5.0e-3,
  tangent_tolerance_rad: float = 5.0e-3,
  pressure_tolerance_fraction: float = 0.02,
  shock_angle_tolerance_rad: float = 0.02,
  maximum_boundary_iterations: int = 16,
) -> MocReflectedDomainGlobalFrontierBoundaryConditionRefinementResult:
  """Fresh-solve a source-bound global pressure-consumer resolution ladder."""

  if not isinstance(
    request,
    MocReflectedDomainGlobalFrontierReconciliationRequest,
  ):
    raise TypeError(
      'request must be a '
      'MocReflectedDomainGlobalFrontierReconciliationRequest'
    )
  ####
  if not isinstance(
    source_closure,
    MocReflectedDomainGlobalPhysicalClosureResult,
  ):
    raise TypeError(
      'source_closure must be a MocReflectedDomainGlobalPhysicalClosureResult'
    )
  ####
  requested = _sample_counts(sample_counts)
  configuration: dict[str, Any] = {
    'sample_counts': requested,
    'position_tolerance_m': float(position_tolerance_m),
    'tangent_tolerance_rad': float(tangent_tolerance_rad),
    'pressure_tolerance_fraction': float(pressure_tolerance_fraction),
    'shock_angle_tolerance_rad': float(shock_angle_tolerance_rad),
    'maximum_boundary_iterations': maximum_boundary_iterations,
    'geometry_policy': 'solver-owned-global-march-no-target-geometry-injection-v1',
  }
  source_fingerprint = moc_reflected_domain_global_physical_closure_fingerprint(
    source_closure
  )
  if not request.lineage_verified or request.source_closure_fingerprint != source_fingerprint:
    measurement = MocReflectedDomainGlobalFrontierBoundaryConditionRefinementMeasurement(
      status=(
        MocReflectedDomainGlobalFrontierBoundaryConditionRefinementStatus
        .INVALID_INPUT
      ),
      requested_sample_counts=requested,
      message='frontier request does not retain the exact source closure lineage',
    )
    return MocReflectedDomainGlobalFrontierBoundaryConditionRefinementResult(
      request=request,
      source_closure=source_closure,
      requested_sample_counts=requested,
      measurement=measurement,
      configuration=configuration,
      configuration_fingerprint=_configuration_fingerprint(configuration),
      message=measurement.message,
    )
  ####
  if not source_closure.converged or not source_closure.physical_closure_verified:
    measurement = MocReflectedDomainGlobalFrontierBoundaryConditionRefinementMeasurement(
      status=(
        MocReflectedDomainGlobalFrontierBoundaryConditionRefinementStatus
        .SOURCE_CLOSURE_FAILURE
      ),
      requested_sample_counts=requested,
      message='refinement requires a locally verified source closure',
    )
    return MocReflectedDomainGlobalFrontierBoundaryConditionRefinementResult(
      request=request,
      source_closure=source_closure,
      requested_sample_counts=requested,
      measurement=measurement,
      configuration=configuration,
      configuration_fingerprint=_configuration_fingerprint(configuration),
      message=measurement.message,
    )
  ####
  steps: list[MocReflectedDomainGlobalFrontierBoundaryConditionRefinementStep] = []
  for count in requested:
    result = run_reflected_domain_global_frontier_boundary_conditioned_resolve(
      request,
      source_closure,
      position_tolerance_m=position_tolerance_m,
      tangent_tolerance_rad=tangent_tolerance_rad,
      pressure_tolerance_fraction=pressure_tolerance_fraction,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      maximum_boundary_iterations=maximum_boundary_iterations,
      sample_count=count,
    )
    conditioned = result.conditioned_closure
    fresh = bool(conditioned is not None and conditioned is not source_closure)
    steps.append(
      MocReflectedDomainGlobalFrontierBoundaryConditionRefinementStep(
        sample_count=count,
        result=result,
        fresh_global_solve_verified=fresh,
        source_lineage_verified=(
          result.source_closure is source_closure
          and result.request is request
        ),
        target_lineage_verified=result.target_lineage_verified,
        target_consumption_verified=result.target_boundary_condition_consumed,
        target_coverage_verified=result.target_coverage_verified,
        target_match_verified=result.target_match_verified,
        residuals_finite=_finite_channels(result),
        solver_owned_geometry_verified=result.solver_owned_geometry_verified,
        fidelity_isolation_verified=result.fidelity_isolation_verified,
        message=result.message,
      )
    )
  ####
  resolved_steps = tuple(steps)
  measurement = (
    measure_reflected_domain_global_frontier_boundary_condition_refinement(
      request,
      source_closure,
      resolved_steps,
    )
  )
  message = measurement.message
  return MocReflectedDomainGlobalFrontierBoundaryConditionRefinementResult(
    request=request,
    source_closure=source_closure,
    requested_sample_counts=requested,
    measurement=measurement,
    configuration=configuration,
    configuration_fingerprint=_configuration_fingerprint(configuration),
    fresh_solver_invocation_verified=(
      measurement.fresh_global_solves_verified
    ),
    fidelity_isolation_verified=measurement.fidelity_isolation_verified,
    message=message,
  )
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalFrontierBoundaryConditionCrossCase:
  """One disjoint source/request binding for cross-case refinement."""

  case_id: str
  regime: str
  source_closure: MocReflectedDomainGlobalPhysicalClosureResult
  request: MocReflectedDomainGlobalFrontierReconciliationRequest
  sample_counts: tuple[int, ...]

  def __post_init__(self) -> None:
    case_id = str(self.case_id)
    regime = str(self.regime)
    if not case_id or not regime:
      raise ValueError('case_id and regime must be non-empty')
    ####
    if not isinstance(
      self.source_closure,
      MocReflectedDomainGlobalPhysicalClosureResult,
    ):
      raise TypeError(
        'source_closure must be a MocReflectedDomainGlobalPhysicalClosureResult'
      )
    ####
    if not isinstance(
      self.request,
      MocReflectedDomainGlobalFrontierReconciliationRequest,
    ):
      raise TypeError(
        'request must be a '
        'MocReflectedDomainGlobalFrontierReconciliationRequest'
      )
    ####
    object.__setattr__(self, 'case_id', case_id)
    object.__setattr__(self, 'regime', regime)
    object.__setattr__(self, 'sample_counts', _sample_counts(self.sample_counts))
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalFrontierBoundaryConditionCrossCaseMeasurement:
  """Independent aggregate evidence for disjoint pressure-consumer cases."""

  status: MocReflectedDomainGlobalFrontierBoundaryConditionRefinementStatus
  case_ids: tuple[str, ...]
  source_closure_fingerprints: tuple[str, ...]
  results: tuple[
    MocReflectedDomainGlobalFrontierBoundaryConditionRefinementResult, ...
  ] = ()
  case_bindings_verified: bool = False
  distinct_source_closures_verified: bool = False
  resolution_ladders_verified: bool = False
  fresh_global_solves_verified: bool = False
  target_lineage_verified: bool = False
  target_consumption_verified: bool = False
  target_coverage_verified: bool = False
  target_match_verified: bool = False
  residuals_finite: bool = False
  solver_owned_geometry_verified: bool = False
  fidelity_isolation_verified: bool = False
  global_coupling_verified: bool = False
  downstream_boundary_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  external_validation_required: bool = True
  operator_id: str = (
    MOC_REFLECTED_DOMAIN_GLOBAL_FRONTIER_BOUNDARY_CONDITION_CROSS_CASE_REFINEMENT_OPERATOR_ID
  )
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalFrontierBoundaryConditionRefinementStatus,
    ):
      raise TypeError('status must be a typed boundary-condition status')
    ####
    ids = tuple(str(value) for value in self.case_ids)
    fingerprints = tuple(str(value) for value in self.source_closure_fingerprints)
    results = tuple(self.results)
    if len(ids) != len(fingerprints) or len(ids) != len(results):
      raise ValueError('case IDs, fingerprints, and results must align')
    ####
    if len(set(ids)) != len(ids):
      raise ValueError('case IDs must be unique')
    ####
    if len(set(fingerprints)) != len(fingerprints):
      raise ValueError('source closure fingerprints must be distinct')
    ####
    if any(
      not isinstance(
        result,
        MocReflectedDomainGlobalFrontierBoundaryConditionRefinementResult,
      )
      for result in results
    ):
      raise TypeError('results must contain typed refinement results')
    ####
    for name in (
      'case_bindings_verified',
      'distinct_source_closures_verified',
      'resolution_ladders_verified',
      'fresh_global_solves_verified',
      'target_lineage_verified',
      'target_consumption_verified',
      'target_coverage_verified',
      'target_match_verified',
      'residuals_finite',
      'solver_owned_geometry_verified',
      'fidelity_isolation_verified',
      'global_coupling_verified',
      'downstream_boundary_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
      'external_validation_required',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if self.global_coupling_verified or self.downstream_boundary_closure_verified:
      raise ValueError('cross-case refinement cannot claim canonical closure')
    ####
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError('cross-case refinement must remain promotion-blocked')
    ####
    if not self.external_validation_required:
      raise ValueError('cross-case refinement must retain external validation')
    ####
    object.__setattr__(self, 'case_ids', ids)
    object.__setattr__(self, 'source_closure_fingerprints', fingerprints)
    object.__setattr__(self, 'results', results)
    object.__setattr__(self, 'operator_id', str(self.operator_id))
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalFrontierBoundaryConditionRefinementStatus
      .CONVERGED_RESEARCH_CROSS_CASE
      and len(self.results) >= 2
      and self.case_bindings_verified
      and self.distinct_source_closures_verified
      and self.resolution_ladders_verified
      and self.fresh_global_solves_verified
      and self.target_lineage_verified
      and self.target_consumption_verified
      and self.target_coverage_verified
      and self.target_match_verified
      and self.residuals_finite
      and self.solver_owned_geometry_verified
      and self.fidelity_isolation_verified
      and self.external_validation_required
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
      and all(result.converged for result in self.results)
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': self.operator_id,
      'status': self.status.value,
      'converged': self.converged,
      'case_ids': self.case_ids,
      'source_closure_fingerprints': self.source_closure_fingerprints,
      'checks': {
        'case_bindings_verified': self.case_bindings_verified,
        'distinct_source_closures_verified': (
          self.distinct_source_closures_verified
        ),
        'resolution_ladders_verified': self.resolution_ladders_verified,
        'fresh_global_solves_verified': self.fresh_global_solves_verified,
        'target_lineage_verified': self.target_lineage_verified,
        'target_consumption_verified': self.target_consumption_verified,
        'target_coverage_verified': self.target_coverage_verified,
        'target_match_verified': self.target_match_verified,
        'residuals_finite': self.residuals_finite,
        'solver_owned_geometry_verified': self.solver_owned_geometry_verified,
        'fidelity_isolation_verified': self.fidelity_isolation_verified,
        'external_validation_required': self.external_validation_required,
        'chain_promotion_blocked': self.chain_promotion_blocked,
        'production_claim_allowed': self.production_claim_allowed,
      },
      'global_coupling_verified': self.global_coupling_verified,
      'downstream_boundary_closure_verified': (
        self.downstream_boundary_closure_verified
      ),
      'canonical_free_boundary_verified': False,
      'canonical_euler_verified': False,
      'external_validation_verified': False,
      'results': tuple(result.as_report() for result in self.results),
      'message': self.message,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalFrontierBoundaryConditionCrossCaseRun:
  """Fresh execution record for disjoint pressure-consumer ladders."""

  cases: tuple[MocReflectedDomainGlobalFrontierBoundaryConditionCrossCase, ...]
  results: tuple[
    MocReflectedDomainGlobalFrontierBoundaryConditionRefinementResult, ...
  ]
  measurement: MocReflectedDomainGlobalFrontierBoundaryConditionCrossCaseMeasurement
  configuration: dict[str, Any]
  configuration_fingerprint: str
  fresh_solver_invocation_verified: bool = False
  fidelity_isolation_verified: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    cases = tuple(self.cases)
    results = tuple(self.results)
    if any(
      not isinstance(
        case,
        MocReflectedDomainGlobalFrontierBoundaryConditionCrossCase,
      )
      for case in cases
    ):
      raise TypeError('cases must contain typed cross-case bindings')
    ####
    if any(
      not isinstance(
        result,
        MocReflectedDomainGlobalFrontierBoundaryConditionRefinementResult,
      )
      for result in results
    ):
      raise TypeError('results must contain typed refinement results')
    ####
    if len(cases) != len(results) or len(cases) != len(self.measurement.results):
      raise ValueError('cases, results, and measurement results must align')
    ####
    configuration = dict(self.configuration)
    if self.configuration_fingerprint != _configuration_fingerprint(configuration):
      raise ValueError('configuration_fingerprint does not match configuration')
    ####
    if not isinstance(self.fresh_solver_invocation_verified, bool):
      raise TypeError('fresh_solver_invocation_verified must be a bool')
    ####
    if not isinstance(self.fidelity_isolation_verified, bool):
      raise TypeError('fidelity_isolation_verified must be a bool')
    ####
    object.__setattr__(self, 'cases', cases)
    object.__setattr__(self, 'results', results)
    object.__setattr__(self, 'configuration', configuration)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.measurement.converged
      and self.fresh_solver_invocation_verified
      and self.fidelity_isolation_verified
    )
  ####

  @property
  def production_claim_allowed(self) -> bool:
    return False
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': (
        MOC_REFLECTED_DOMAIN_GLOBAL_FRONTIER_BOUNDARY_CONDITION_CROSS_CASE_REFINEMENT_OPERATOR_ID
      ),
      'converged': self.converged,
      'case_ids': tuple(case.case_id for case in self.cases),
      'fresh_solver_invocation_verified': self.fresh_solver_invocation_verified,
      'fidelity_isolation_verified': self.fidelity_isolation_verified,
      'configuration': self.configuration,
      'configuration_fingerprint': self.configuration_fingerprint,
      'results': tuple(result.as_report() for result in self.results),
      'measurement': self.measurement.as_report(),
      'message': self.message,
    }
  ####
####


def run_reflected_domain_global_frontier_boundary_condition_cross_case_refinement(
  cases: Sequence[MocReflectedDomainGlobalFrontierBoundaryConditionCrossCase],
  *,
  position_tolerance_m: float = 5.0e-3,
  tangent_tolerance_rad: float = 5.0e-3,
  pressure_tolerance_fraction: float = 0.02,
  shock_angle_tolerance_rad: float = 0.02,
  maximum_boundary_iterations: int = 16,
) -> MocReflectedDomainGlobalFrontierBoundaryConditionCrossCaseRun:
  """Freshly execute separate pressure-consumer ladders per case."""

  resolved_cases = tuple(cases)
  if len(resolved_cases) < 2:
    raise ValueError('cross-case refinement requires at least two cases')
  ####
  if any(
    not isinstance(
      case,
      MocReflectedDomainGlobalFrontierBoundaryConditionCrossCase,
    )
    for case in resolved_cases
  ):
    raise TypeError('cases must contain typed cross-case bindings')
  ####
  case_ids = tuple(case.case_id for case in resolved_cases)
  fingerprints = tuple(
    moc_reflected_domain_global_physical_closure_fingerprint(
      case.source_closure
    )
    for case in resolved_cases
  )
  configuration: dict[str, Any] = {
    'case_ids': case_ids,
    'source_closure_fingerprints': fingerprints,
    'position_tolerance_m': float(position_tolerance_m),
    'tangent_tolerance_rad': float(tangent_tolerance_rad),
    'pressure_tolerance_fraction': float(pressure_tolerance_fraction),
    'shock_angle_tolerance_rad': float(shock_angle_tolerance_rad),
    'maximum_boundary_iterations': maximum_boundary_iterations,
    'case_policy': 'distinct-source-closure-fingerprint-per-ladder-v1',
  }
  case_bindings = bool(
    len(set(case_ids)) == len(case_ids)
    and all(
      case.request.lineage_verified
      and case.request.source_closure_fingerprint == fingerprint
      and case.request.source_proposal_fingerprint
      == moc_reflected_domain_global_frontier_proposal_fingerprint(
        case.request.proposal
      )
      for case, fingerprint in zip(resolved_cases, fingerprints, strict=True)
    )
  )
  distinct_sources = len(set(fingerprints)) == len(fingerprints)
  results = tuple(
    run_reflected_domain_global_frontier_boundary_condition_refinement(
      case.request,
      case.source_closure,
      sample_counts=case.sample_counts,
      position_tolerance_m=position_tolerance_m,
      tangent_tolerance_rad=tangent_tolerance_rad,
      pressure_tolerance_fraction=pressure_tolerance_fraction,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      maximum_boundary_iterations=maximum_boundary_iterations,
    )
    for case in resolved_cases
  )
  ladders_verified = bool(results and all(result.measurement.converged for result in results))
  aggregate = bool(
    case_bindings
    and distinct_sources
    and ladders_verified
  )
  measurement = MocReflectedDomainGlobalFrontierBoundaryConditionCrossCaseMeasurement(
    status=(
      MocReflectedDomainGlobalFrontierBoundaryConditionRefinementStatus
      .CONVERGED_RESEARCH_CROSS_CASE
      if aggregate
      else MocReflectedDomainGlobalFrontierBoundaryConditionRefinementStatus
      .CROSS_CASE_FAILURE
    ),
    case_ids=case_ids,
    source_closure_fingerprints=fingerprints,
    results=results,
    case_bindings_verified=case_bindings,
    distinct_source_closures_verified=distinct_sources,
    resolution_ladders_verified=ladders_verified,
    fresh_global_solves_verified=bool(
      results and all(result.fresh_solver_invocation_verified for result in results)
    ),
    target_lineage_verified=bool(
      results and all(result.measurement.target_lineage_verified for result in results)
    ),
    target_consumption_verified=bool(
      results and all(result.measurement.target_consumption_verified for result in results)
    ),
    target_coverage_verified=bool(
      results and all(result.measurement.target_coverage_verified for result in results)
    ),
    target_match_verified=bool(
      results and all(result.measurement.target_match_verified for result in results)
    ),
    residuals_finite=bool(
      results and all(result.measurement.residuals_finite for result in results)
    ),
    solver_owned_geometry_verified=bool(
      results
      and all(
        result.measurement.solver_owned_geometry_verified
        for result in results
      )
    ),
    fidelity_isolation_verified=bool(
      results and all(result.fidelity_isolation_verified for result in results)
    ),
    message=(
      'disjoint global pressure-consumer refinement ladders passed source, '
      'resolution, residual, and fidelity checks; canonical closure remains '
      'blocked'
      if aggregate
      else 'cross-case global pressure-consumer refinement did not pass '
      'distinct-source, ladder, or local fidelity checks'
    ),
  )
  return MocReflectedDomainGlobalFrontierBoundaryConditionCrossCaseRun(
    cases=resolved_cases,
    results=results,
    measurement=measurement,
    configuration=configuration,
    configuration_fingerprint=_configuration_fingerprint(configuration),
    fresh_solver_invocation_verified=measurement.fresh_global_solves_verified,
    fidelity_isolation_verified=measurement.fidelity_isolation_verified,
    message=measurement.message,
  )
####
