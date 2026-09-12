"""Disjoint case/resolution coverage for characteristic pressure correction.

The single-case pressure consumer demonstrates that a local characteristic
pressure trace can influence a freshly solved global physical field.  This
module checks whether that behavior survives a named source-closure and
solver-resolution ladder.  It keeps selection, strict residual descent,
independent replay, and fidelity isolation as separate gates; cross-case
coverage never promotes the pressure-only consumer to a canonical boundary.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any

from exhaust_plume.models.moc.global_physical_closure import (
  MocReflectedDomainGlobalPhysicalClosureResult,
)
from exhaust_plume.validation.moc_global_mixed_regime_characteristic_free_boundary_pressure_correction import (
  DEFAULT_PRESSURE_CORRECTION_FRACTIONS,
  MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionAudit,
  MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionRequest,
  MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionResult,
  audit_reflected_domain_global_mixed_regime_characteristic_free_boundary_pressure_correction,
  run_reflected_domain_global_mixed_regime_characteristic_free_boundary_pressure_correction,
)
from exhaust_plume.validation.moc_global_mixed_regime_shock_frontier_refinement import (
  MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementStep,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_CHARACTERISTIC_FREE_BOUNDARY_PRESSURE_CORRECTION_REFINEMENT_OPERATOR_ID',
  'MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionRefinementStatus',
  'MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionRefinementCase',
  'MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionRefinementStep',
  'MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionRefinementMeasurement',
  'run_reflected_domain_global_mixed_regime_characteristic_free_boundary_pressure_correction_refinement',
  'measure_reflected_domain_global_mixed_regime_characteristic_free_boundary_pressure_correction_refinement',
)


MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_CHARACTERISTIC_FREE_BOUNDARY_PRESSURE_CORRECTION_REFINEMENT_OPERATOR_ID = (
  'op.moc.reflected-domain.global-mixed-regime-characteristic-free-boundary-pressure-correction-refinement-v1'
)
MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_CHARACTERISTIC_FREE_BOUNDARY_PRESSURE_CORRECTION_REFINEMENT_MODEL = (
  'research-global-mixed-regime-characteristic-free-boundary-pressure-correction-refinement-v1'
)


class MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionRefinementStatus(
  str,
  Enum,
):
  """Typed outcomes of disjoint pressure-correction coverage."""

  CONVERGED_LOCAL_RESEARCH_COVERAGE = (
    'converged-local-characteristic-pressure-correction-coverage'
  )
  CONVERGED_CROSS_CASE_RESEARCH_COVERAGE = (
    'converged-cross-case-characteristic-pressure-correction-coverage'
  )
  COMPLETED_RESEARCH_COVERAGE_WITH_OPEN_GATE = (
    'completed-characteristic-pressure-correction-coverage-with-open-gate'
  )
  INVALID_INPUT = 'invalid_input'
  CORRECTION_FAILURE = (
    'characteristic-pressure-correction-refinement-correction-failure'
  )
####


def _strictly_increasing(values: Sequence[int]) -> bool:
  return bool(
    len(values) >= 2
    and all(right > left for left, right in zip(values, values[1:]))
  )
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionRefinementCase:
  """One source closure and exact frontier resolution in the ladder."""

  case_id: str
  source_closure: MocReflectedDomainGlobalPhysicalClosureResult
  source_frontier_step: MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementStep
  fractions: tuple[float, ...] = DEFAULT_PRESSURE_CORRECTION_FRACTIONS
  seam_pressure_tolerance_fraction: float = 0.25
  position_tolerance_m: float = 1.0e-9
  shock_angle_tolerance_rad: float = 0.02
  maximum_boundary_iterations: int = 16
  source: str = (
    MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_CHARACTERISTIC_FREE_BOUNDARY_PRESSURE_CORRECTION_REFINEMENT_MODEL
  )

  def __post_init__(self) -> None:
    case_id = str(self.case_id)
    if not case_id:
      raise ValueError('case_id must be non-empty')
    ####
    if not isinstance(
      self.source_closure,
      MocReflectedDomainGlobalPhysicalClosureResult,
    ):
      raise TypeError('source_closure must be a typed global physical closure')
    ####
    if not isinstance(
      self.source_frontier_step,
      MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementStep,
    ):
      raise TypeError('source_frontier_step must be a typed frontier step')
    ####
    if self.source_frontier_step.closure is not self.source_closure:
      raise ValueError(
        'source_frontier_step must retain the exact source_closure object'
      )
    ####
    if not self.source_frontier_step.locally_verified:
      raise ValueError('source_frontier_step must be locally verified')
    ####
    if self.source_frontier_step.case_id != case_id:
      raise ValueError('case_id must match source_frontier_step.case_id')
    ####
    request = MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionRequest(
      source_closure=self.source_closure,
      source_frontier_step=self.source_frontier_step,
      fractions=self.fractions,
      seam_pressure_tolerance_fraction=self.seam_pressure_tolerance_fraction,
      position_tolerance_m=self.position_tolerance_m,
      shock_angle_tolerance_rad=self.shock_angle_tolerance_rad,
      maximum_boundary_iterations=self.maximum_boundary_iterations,
      source=self.source,
    )
    object.__setattr__(self, 'case_id', case_id)
    object.__setattr__(self, 'fractions', request.fractions)
    object.__setattr__(
      self,
      'seam_pressure_tolerance_fraction',
      request.seam_pressure_tolerance_fraction,
    )
    object.__setattr__(self, 'position_tolerance_m', request.position_tolerance_m)
    object.__setattr__(
      self,
      'shock_angle_tolerance_rad',
      request.shock_angle_tolerance_rad,
    )
    object.__setattr__(
      self,
      'maximum_boundary_iterations',
      request.maximum_boundary_iterations,
    )
    object.__setattr__(self, 'source', request.source)
  ####

  @property
  def frontier_sample_count(self) -> int:
    return self.source_frontier_step.frontier_sample_count
  ####

  @property
  def source_closure_fingerprint(self) -> str:
    return self.source_frontier_step.source_closure_fingerprint
  ####

  def as_request(
    self,
  ) -> MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionRequest:
    return MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionRequest(
      source_closure=self.source_closure,
      source_frontier_step=self.source_frontier_step,
      fractions=self.fractions,
      seam_pressure_tolerance_fraction=self.seam_pressure_tolerance_fraction,
      position_tolerance_m=self.position_tolerance_m,
      shock_angle_tolerance_rad=self.shock_angle_tolerance_rad,
      maximum_boundary_iterations=self.maximum_boundary_iterations,
      source=self.source,
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_CHARACTERISTIC_FREE_BOUNDARY_PRESSURE_CORRECTION_REFINEMENT_OPERATOR_ID,
      'case_id': self.case_id,
      'frontier_sample_count': self.frontier_sample_count,
      'source_closure_fingerprint': self.source_closure_fingerprint,
      'fractions': self.fractions,
      'seam_pressure_tolerance_fraction': self.seam_pressure_tolerance_fraction,
      'position_tolerance_m': self.position_tolerance_m,
      'shock_angle_tolerance_rad': self.shock_angle_tolerance_rad,
      'maximum_boundary_iterations': self.maximum_boundary_iterations,
      'source': self.source,
      'research_only': True,
      'production_claim_allowed': False,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionRefinementStep:
  """One independently executed pressure-correction case."""

  case: MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionRefinementCase
  result: MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionResult
  audit: MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionAudit

  def __post_init__(self) -> None:
    if not isinstance(
      self.case,
      MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionRefinementCase,
    ):
      raise TypeError('case must be a typed pressure-correction case')
    ####
    if not isinstance(
      self.result,
      MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionResult,
    ):
      raise TypeError('result must be a typed pressure-correction result')
    ####
    if not isinstance(
      self.audit,
      MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionAudit,
    ):
      raise TypeError('audit must be a typed pressure-correction audit')
    ####
  ####

  @property
  def source_lineage_verified(self) -> bool:
    return bool(
      self.result.source_closure is self.case.source_closure
      and self.result.source_frontier_step is self.case.source_frontier_step
      and self.result.request is not None
      and self.result.request.source_closure is self.case.source_closure
      and self.result.request.source_frontier_step is self.case.source_frontier_step
      and self.result.request.source_closure_fingerprint
      == self.case.source_closure_fingerprint
    )
  ####

  @property
  def correction_consumed(self) -> bool:
    return bool(
      self.result.converged_research_pressure_correction
      and self.result.pressure_trace_consumed
      and self.result.pressure_target_consumption_verified
      and self.result.selected_closure is not None
    )
  ####

  @property
  def strict_residual_descent_verified(self) -> bool:
    return bool(
      self.result.strict_cell_residual_descent_verified
      and self.result.baseline_max_cell_euler_residual is not None
      and self.result.selected_max_cell_euler_residual is not None
      and self.result.selected_max_cell_euler_residual
      < self.result.baseline_max_cell_euler_residual
    )
  ####

  @property
  def independent_replay_verified(self) -> bool:
    return bool(
      self.audit.converged
      and self.audit.request_replayed
      and self.audit.source_lineage_replayed
      and self.audit.frontier_lineage_replayed
      and self.audit.base_target_replayed
      and self.audit.trial_ladder_replayed
      and self.audit.selected_closure_replayed
      and self.audit.independent_pressure_correction_verified
    )
  ####

  @property
  def fidelity_isolation_verified(self) -> bool:
    return bool(
      self.result.characteristic_geometry_segregated
      and self.result.global_coupling_verified is False
      and self.result.canonical_free_boundary_verified is False
      and self.result.chain_promotion_blocked
      and self.result.production_claim_allowed is False
      and self.audit.characteristic_geometry_segregated
      and self.audit.global_coupling_verified is False
      and self.audit.chain_promotion_blocked
      and self.audit.production_claim_allowed is False
    )
  ####

  @property
  def locally_verified(self) -> bool:
    return bool(
      self.source_lineage_verified
      and self.correction_consumed
      and self.strict_residual_descent_verified
      and self.independent_replay_verified
      and self.fidelity_isolation_verified
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_CHARACTERISTIC_FREE_BOUNDARY_PRESSURE_CORRECTION_REFINEMENT_OPERATOR_ID,
      'case': self.case.as_report(),
      'result': self.result.as_report(),
      'audit': self.audit.as_report(),
      'checks': {
        'source_lineage_verified': self.source_lineage_verified,
        'correction_consumed': self.correction_consumed,
        'strict_residual_descent_verified': self.strict_residual_descent_verified,
        'independent_replay_verified': self.independent_replay_verified,
        'fidelity_isolation_verified': self.fidelity_isolation_verified,
        'locally_verified': self.locally_verified,
      },
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionRefinementMeasurement:
  """Disjoint pressure-correction evidence below canonical promotion."""

  status: MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionRefinementStatus
  steps: tuple[MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionRefinementStep, ...] = ()
  case_ids: tuple[str, ...] = ()
  frontier_sample_counts: tuple[int, ...] = ()
  source_closure_fingerprints: tuple[str, ...] = ()
  local_case_resolution_ladders_verified: bool = False
  distinct_source_closures_verified: bool = False
  source_lineage_verified: bool = False
  correction_consumed_verified: bool = False
  strict_residual_descent_verified: bool = False
  independent_replay_verified: bool = False
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
      MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionRefinementStatus,
    ):
      raise TypeError('status must be a typed refinement status')
    ####
    steps = tuple(self.steps)
    if any(
      not isinstance(
        step,
        MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionRefinementStep,
      )
      for step in steps
    ):
      raise TypeError('steps must contain typed refinement steps')
    ####
    case_ids = tuple(step.case.case_id for step in steps)
    counts = tuple(step.case.frontier_sample_count for step in steps)
    fingerprints = tuple(step.case.source_closure_fingerprint for step in steps)
    if self.case_ids and tuple(self.case_ids) != case_ids:
      raise ValueError('case_ids must match retained refinement steps')
    ####
    if self.frontier_sample_counts and tuple(self.frontier_sample_counts) != counts:
      raise ValueError('frontier_sample_counts must match retained refinement steps')
    ####
    if self.source_closure_fingerprints and tuple(self.source_closure_fingerprints) != fingerprints:
      raise ValueError(
        'source_closure_fingerprints must match retained refinement steps'
      )
    ####
    for name in (
      'local_case_resolution_ladders_verified',
      'distinct_source_closures_verified',
      'source_lineage_verified',
      'correction_consumed_verified',
      'strict_residual_descent_verified',
      'independent_replay_verified',
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
    object.__setattr__(self, 'frontier_sample_counts', counts)
    object.__setattr__(self, 'source_closure_fingerprints', fingerprints)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      in {
        MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionRefinementStatus
        .CONVERGED_LOCAL_RESEARCH_COVERAGE,
        MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionRefinementStatus
        .CONVERGED_CROSS_CASE_RESEARCH_COVERAGE,
      }
      and self.local_coverage_verified
      and self.fidelity_isolation_verified
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_CHARACTERISTIC_FREE_BOUNDARY_PRESSURE_CORRECTION_REFINEMENT_OPERATOR_ID,
      'status': self.status.value,
      'converged': self.converged,
      'case_ids': self.case_ids,
      'frontier_sample_counts': self.frontier_sample_counts,
      'source_closure_fingerprints': self.source_closure_fingerprints,
      'checks': {
        'local_case_resolution_ladders_verified': self.local_case_resolution_ladders_verified,
        'distinct_source_closures_verified': self.distinct_source_closures_verified,
        'source_lineage_verified': self.source_lineage_verified,
        'correction_consumed_verified': self.correction_consumed_verified,
        'strict_residual_descent_verified': self.strict_residual_descent_verified,
        'independent_replay_verified': self.independent_replay_verified,
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
  status: MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionRefinementStatus,
  message: str,
  *,
  steps: Sequence[MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionRefinementStep] = (),
  **flags: bool,
) -> MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionRefinementMeasurement:
  retained = tuple(steps)
  return MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionRefinementMeasurement(
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
####


def measure_reflected_domain_global_mixed_regime_characteristic_free_boundary_pressure_correction_refinement(
  steps: Sequence[MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionRefinementStep],
  *,
  expected_case_ids: Sequence[str] | None = None,
) -> MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionRefinementMeasurement:
  """Measure case/resolution coverage without promoting the consumer."""

  status_type = MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionRefinementStatus
  try:
    retained = tuple(steps)
  except TypeError:
    return _measurement(status_type.INVALID_INPUT, 'steps must be iterable')
  ####
  if len(retained) < 2 or any(
    not isinstance(
      step,
      MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionRefinementStep,
    )
    for step in retained
  ):
    return _measurement(
      status_type.INVALID_INPUT,
      'refinement requires at least two typed pressure-correction steps',
    )
  ####
  grouped: dict[str, list[MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionRefinementStep]] = {}
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
      _strictly_increasing(
        tuple(step.case.frontier_sample_count for step in case_steps)
      )
      for case_steps in grouped.values()
    )
  )
  fingerprints = tuple(step.case.source_closure_fingerprint for step in retained)
  distinct_sources = bool(len(grouped) >= 2 and len(set(fingerprints)) >= 2)
  source_lineage = all(step.source_lineage_verified for step in retained)
  correction_consumed = all(step.correction_consumed for step in retained)
  strict_descent = all(step.strict_residual_descent_verified for step in retained)
  independent_replay = all(step.independent_replay_verified for step in retained)
  fidelity_isolation = all(step.fidelity_isolation_verified for step in retained)
  local_coverage = bool(
    case_ids_verified
    and source_lineage
    and correction_consumed
    and strict_descent
    and independent_replay
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
    (ladders, 'strict frontier-resolution ladders'),
    (distinct_sources, 'distinct source closures'),
    (source_lineage, 'source lineage'),
    (correction_consumed, 'pressure correction consumption'),
    (strict_descent, 'strict cell-residual descent'),
    (independent_replay, 'independent replay'),
    (fidelity_isolation, 'fidelity isolation'),
  ):
    if not verified:
      open_gates.append(label)
    ####
  ####
  message = (
    'characteristic pressure correction passed independent replay across '
    'distinct source closures and strictly increasing exact frontier '
    'resolutions; canonical/global and production promotion remain open'
    if cross_case
    else 'characteristic pressure correction evidence was retained, but open '
    f'gates remain: {", ".join(open_gates) if open_gates else "cross-case coverage"}'
  )
  return _measurement(
    status,
    message,
    steps=retained,
    local_case_resolution_ladders_verified=ladders,
    distinct_source_closures_verified=distinct_sources,
    source_lineage_verified=source_lineage,
    correction_consumed_verified=correction_consumed,
    strict_residual_descent_verified=strict_descent,
    independent_replay_verified=independent_replay,
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


def run_reflected_domain_global_mixed_regime_characteristic_free_boundary_pressure_correction_refinement(
  cases: Sequence[MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionRefinementCase],
  *,
  expected_case_ids: Sequence[str] | None = None,
) -> MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionRefinementMeasurement:
  """Run and independently audit each declared case/resolution point."""

  status_type = MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionRefinementStatus
  try:
    retained_cases = tuple(cases)
  except TypeError:
    return _measurement(status_type.INVALID_INPUT, 'cases must be iterable')
  ####
  if len(retained_cases) < 2 or any(
    not isinstance(
      case,
      MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionRefinementCase,
    )
    for case in retained_cases
  ):
    return _measurement(
      status_type.INVALID_INPUT,
      'cases must contain at least two typed pressure-correction cases',
    )
  ####
  steps: list[MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionRefinementStep] = []
  for case in retained_cases:
    try:
      request = case.as_request()
      result = run_reflected_domain_global_mixed_regime_characteristic_free_boundary_pressure_correction(
        request
      )
      audit = audit_reflected_domain_global_mixed_regime_characteristic_free_boundary_pressure_correction(
        result
      )
      steps.append(
        MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionRefinementStep(
          case=case,
          result=result,
          audit=audit,
        )
      )
    except (ArithmeticError, FloatingPointError, RuntimeError, TypeError, ValueError) as error:
      return _measurement(
        status_type.CORRECTION_FAILURE,
        f'characteristic pressure-correction refinement failed: {error}',
        steps=steps,
      )
    ####
  ####
  return measure_reflected_domain_global_mixed_regime_characteristic_free_boundary_pressure_correction_refinement(
    steps,
    expected_case_ids=expected_case_ids,
  )
####
