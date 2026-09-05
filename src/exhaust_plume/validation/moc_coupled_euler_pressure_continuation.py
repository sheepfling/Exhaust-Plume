"""Pressure-target evidence for the coupled Euler/free-boundary research lane.

Each pressure point is a fresh solve with the same upstream global-closure
reference and the same numerical controls.  The ladder is ordered from a
pressure-compatible target toward lower ambient pressure so the pressure
budget and the physical closure seam are visible as separate diagnostics.
This operator does not reuse a prior field as an initial condition and never
turns a successful local case into canonical or production status.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from hashlib import sha256
import json
from math import isfinite
from typing import Any, Sequence

from exhaust_plume.models.moc.coupled_euler_free_boundary import (
  MocReflectedDomainCoupledEulerFreeBoundaryRequest,
  MocReflectedDomainCoupledEulerFreeBoundaryResult,
  MocReflectedDomainCoupledEulerFreeBoundaryStatus,
  solve_reflected_domain_coupled_euler_free_boundary,
)
from exhaust_plume.validation.moc_coupled_euler_free_boundary import (
  MocReflectedDomainCoupledEulerFreeBoundaryAudit,
  measure_reflected_domain_coupled_euler_free_boundary,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_COUPLED_EULER_PRESSURE_CONTINUATION_OPERATOR_ID',
  'MocReflectedDomainCoupledEulerPressureContinuationStatus',
  'MocReflectedDomainCoupledEulerPressureContinuationCase',
  'MocReflectedDomainCoupledEulerPressureContinuationMeasurement',
  'measure_reflected_domain_coupled_euler_pressure_continuation',
  'MOC_REFLECTED_DOMAIN_COUPLED_EULER_PRESSURE_CONTINUATION_RUN_OPERATOR_ID',
  'MocReflectedDomainCoupledEulerPressureContinuationRun',
  'run_reflected_domain_coupled_euler_pressure_continuation',
)


MOC_REFLECTED_DOMAIN_COUPLED_EULER_PRESSURE_CONTINUATION_OPERATOR_ID = (
  'op.moc.reflected-domain.coupled-euler-pressure-continuation'
)
MOC_REFLECTED_DOMAIN_COUPLED_EULER_PRESSURE_CONTINUATION_RUN_OPERATOR_ID = (
  'op.moc.reflected-domain.coupled-euler-pressure-continuation-run'
)


class MocReflectedDomainCoupledEulerPressureContinuationStatus(str, Enum):
  """Outcome for one independently measured pressure-target ladder."""

  CONVERGED_RESEARCH_PRESSURE_LADDER = (
    'converged-research-coupled-euler-pressure-continuation-ladder'
  )
  INVALID_INPUT = 'invalid_input'
  PRESSURE_ORDER_FAILURE = 'coupled-euler-pressure-continuation-order-failure'
  LINEAGE_FAILURE = 'coupled-euler-pressure-continuation-lineage-failure'
  AUDIT_FAILURE = 'coupled-euler-pressure-continuation-audit-failure'
  PRESSURE_BUDGET_FAILURE = (
    'coupled-euler-pressure-continuation-pressure-budget-failure'
  )
  FIDELITY_FAILURE = 'coupled-euler-pressure-continuation-fidelity-failure'
  CASE_FAILURE = 'coupled-euler-pressure-continuation-case-failure'
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainCoupledEulerPressureContinuationCase:
  """One fresh pressure-target solve and its independent audit."""

  target_ambient_pressure_Pa: float
  request: MocReflectedDomainCoupledEulerFreeBoundaryRequest
  result: MocReflectedDomainCoupledEulerFreeBoundaryResult
  audit: MocReflectedDomainCoupledEulerFreeBoundaryAudit

  def __post_init__(self) -> None:
    target = float(self.target_ambient_pressure_Pa)
    if not isfinite(target) or target <= 0.0:
      raise ValueError('target_ambient_pressure_Pa must be finite and positive')
    ####
    if not isinstance(
      self.request,
      MocReflectedDomainCoupledEulerFreeBoundaryRequest,
    ):
      raise TypeError(
        'request must be a '
        'MocReflectedDomainCoupledEulerFreeBoundaryRequest'
      )
    ####
    if not isinstance(
      self.result,
      MocReflectedDomainCoupledEulerFreeBoundaryResult,
    ):
      raise TypeError(
        'result must be a '
        'MocReflectedDomainCoupledEulerFreeBoundaryResult'
      )
    ####
    if not isinstance(
      self.audit,
      MocReflectedDomainCoupledEulerFreeBoundaryAudit,
    ):
      raise TypeError(
        'audit must be a '
        'MocReflectedDomainCoupledEulerFreeBoundaryAudit'
      )
    ####
    request_target = float(
      self.request.mixed_regime_request.ambient_pressure_Pa
    )
    if abs(request_target - target) > 1.0e-12 * max(target, request_target, 1.0):
      raise ValueError(
        'request ambient pressure must match target_ambient_pressure_Pa'
      )
    ####
    if self.result.request != self.request:
      raise ValueError('result must retain the exact pressure-target request')
    ####
    if self.audit.candidate is not None and self.audit.candidate != self.result:
      raise ValueError('audit must retain the exact resolved pressure case')
    ####
    object.__setattr__(self, 'target_ambient_pressure_Pa', target)
  ####

  @property
  def source_closure_fingerprint(self) -> str:
    """Return the upstream global-closure identity carried by this case."""

    return self.request.source_closure_fingerprint
  ####

  @property
  def local_closure_verified(self) -> bool:
    """Whether both solver and independent audit reached local closure."""

    return bool(self.result.converged and self.audit.local_consistency_verified)
  ####

  @property
  def independent_diagnostics_verified(self) -> bool:
    """Whether the case is auditable even when its physical boundary is open."""

    if self.result.status is (
      MocReflectedDomainCoupledEulerFreeBoundaryStatus.TRANSONIC_FRONTIER_FAILURE
    ):
      return bool(
        self.audit.transonic_frontier_compatibility_verified
        and self.result.subsonic_pressure_budget is not None
        and self.result.transonic_transition is not None
        and self.result.transonic_transition_audit is not None
        and self.audit.promotion_flags_verified
      )
    ####
    return bool(
      self.audit.geometry_verified
      and self.audit.state_samples_verified
      and self.audit.thermodynamics_verified
      and self.audit.residual_channels_recomputed
      and self.audit.residual_report_verified
      and self.audit.free_boundary_report_verified
      and self.audit.pressure_budget_verified
      and self.audit.transonic_transition_verified
      and self.audit.entropy_report_verified
      and self.audit.entropy_production_map_verified
      and self.audit.entropy_transport_verified
      and self.audit.promotion_flags_verified
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'target_ambient_pressure_Pa': self.target_ambient_pressure_Pa,
      'source_closure_fingerprint': self.source_closure_fingerprint,
      'solver_status': self.result.status.value,
      'solver_converged': self.result.converged,
      'audit_status': self.audit.status.value,
      'audit_converged': self.audit.converged,
      'local_closure_verified': self.local_closure_verified,
      'independent_diagnostics_verified': self.independent_diagnostics_verified,
      'maximum_free_boundary_pressure_residual_Pa': (
        self.audit.maximum_free_boundary_pressure_residual_Pa
      ),
      'maximum_free_boundary_normal_velocity_residual_fraction': (
        self.audit.maximum_free_boundary_normal_velocity_residual_fraction
      ),
      'minimum_additional_total_pressure_loss_fraction': (
        None
        if self.result.subsonic_pressure_budget is None
        else self.result.subsonic_pressure_budget.minimum_additional_total_pressure_loss_fraction
      ),
      'result': self.result.as_report(),
      'audit': self.audit.as_report(),
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainCoupledEulerPressureContinuationMeasurement:
  """Independent pressure-ladder evidence below the promotion ceiling."""

  status: MocReflectedDomainCoupledEulerPressureContinuationStatus
  cases: tuple[MocReflectedDomainCoupledEulerPressureContinuationCase, ...] = ()
  audits: tuple[MocReflectedDomainCoupledEulerFreeBoundaryAudit, ...] = ()
  target_ambient_pressures_Pa: tuple[float, ...] = ()
  source_closure_fingerprint: str = ''
  maximum_free_boundary_pressure_residuals_Pa: tuple[float, ...] = ()
  maximum_free_boundary_normal_velocity_residual_fractions: tuple[float, ...] = ()
  minimum_additional_total_pressure_loss_fractions: tuple[float, ...] = ()
  outlet_heights_m: tuple[float, ...] = ()
  pressure_order_verified: bool = False
  source_closure_identity_verified: bool = False
  case_audits_verified: bool = False
  diagnostics_finite: bool = False
  pressure_budget_trend_verified: bool = False
  local_closure_verified: bool = False
  fidelity_isolation_verified: bool = False
  physical_closure_verified: bool = False
  canonical_free_boundary_verified: bool = False
  canonical_euler_verified: bool = False
  external_validation_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  residual_tolerance: float = 5.0e-4
  operator_id: str = (
    MOC_REFLECTED_DOMAIN_COUPLED_EULER_PRESSURE_CONTINUATION_OPERATOR_ID
  )
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainCoupledEulerPressureContinuationStatus,
    ):
      raise TypeError(
        'status must be a '
        'MocReflectedDomainCoupledEulerPressureContinuationStatus'
      )
    ####
    cases = tuple(self.cases)
    audits = tuple(self.audits)
    if len(cases) != len(audits):
      raise ValueError('cases and audits must have equal lengths')
    ####
    if any(
      not isinstance(
        case,
        MocReflectedDomainCoupledEulerPressureContinuationCase,
      )
      for case in cases
    ):
      raise TypeError('cases must contain typed pressure-continuation cases')
    ####
    if any(
      not isinstance(
        audit,
        MocReflectedDomainCoupledEulerFreeBoundaryAudit,
      )
      for audit in audits
    ):
      raise TypeError('audits must contain typed coupled Euler audits')
    ####
    if tuple(case.audit for case in cases) != audits:
      raise ValueError('audits must retain the audits stored in cases')
    ####
    object.__setattr__(self, 'cases', cases)
    object.__setattr__(self, 'audits', audits)
    targets = tuple(float(value) for value in self.target_ambient_pressures_Pa)
    if len(targets) != len(cases):
      raise ValueError('target_ambient_pressures_Pa must match the case count')
    ####
    if any(not isfinite(value) or value <= 0.0 for value in targets):
      raise ValueError(
        'target_ambient_pressures_Pa must contain finite positive values'
      )
    ####
    if targets and targets != tuple(
      case.target_ambient_pressure_Pa for case in cases
    ):
      raise ValueError('target pressures must match case targets')
    ####
    object.__setattr__(self, 'target_ambient_pressures_Pa', targets)
    fingerprint = str(self.source_closure_fingerprint)
    if cases and not fingerprint:
      raise ValueError(
        'source_closure_fingerprint must be present for pressure cases'
      )
    ####
    object.__setattr__(self, 'source_closure_fingerprint', fingerprint)
    for name in (
      'maximum_free_boundary_pressure_residuals_Pa',
      'maximum_free_boundary_normal_velocity_residual_fractions',
      'minimum_additional_total_pressure_loss_fractions',
      'outlet_heights_m',
    ):
      values = tuple(float(value) for value in getattr(self, name))
      if len(values) != len(cases):
        raise ValueError(f'{name} must match the case count')
      ####
      if any(not isfinite(value) or value < 0.0 for value in values):
        raise ValueError(f'{name} must contain finite nonnegative values')
      ####
      object.__setattr__(self, name, values)
    ####
    tolerance = float(self.residual_tolerance)
    if not isfinite(tolerance) or tolerance <= 0.0:
      raise ValueError('residual_tolerance must be finite and positive')
    ####
    object.__setattr__(self, 'residual_tolerance', tolerance)
    for name in (
      'pressure_order_verified',
      'source_closure_identity_verified',
      'case_audits_verified',
      'diagnostics_finite',
      'pressure_budget_trend_verified',
      'local_closure_verified',
      'fidelity_isolation_verified',
      'physical_closure_verified',
      'canonical_free_boundary_verified',
      'canonical_euler_verified',
      'external_validation_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if self.physical_closure_verified:
      raise ValueError(
        'pressure-continuation evidence cannot claim physical closure'
      )
    ####
    if not self.chain_promotion_blocked:
      raise ValueError(
        'pressure-continuation evidence must block chain promotion'
      )
    ####
    if self.production_claim_allowed:
      raise ValueError(
        'pressure-continuation evidence cannot allow production claims'
      )
    ####
    operator_id = str(self.operator_id)
    if not operator_id:
      raise ValueError('operator_id must be a non-empty string')
    ####
    object.__setattr__(self, 'operator_id', operator_id)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    """Whether every pressure point reached local research closure."""

    return self.status is (
      MocReflectedDomainCoupledEulerPressureContinuationStatus
      .CONVERGED_RESEARCH_PRESSURE_LADDER
    )
  ####

  @property
  def independent_evidence_verified(self) -> bool:
    """Whether the ladder is independently auditable without being promoted."""

    return bool(
      self.pressure_order_verified
      and self.source_closure_identity_verified
      and self.case_audits_verified
      and self.diagnostics_finite
      and self.pressure_budget_trend_verified
      and self.fidelity_isolation_verified
      and not self.physical_closure_verified
      and not self.canonical_free_boundary_verified
      and not self.canonical_euler_verified
      and not self.external_validation_verified
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
    )
  ####

  @property
  def local_consistency_verified(self) -> bool:
    """Whether every case also passed the local physical closure gate."""

    return bool(self.converged and self.independent_evidence_verified and self.local_closure_verified)
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'independent_evidence_verified': self.independent_evidence_verified,
      'local_consistency_verified': self.local_consistency_verified,
      'target_ambient_pressures_Pa': self.target_ambient_pressures_Pa,
      'source_closure_fingerprint': self.source_closure_fingerprint,
      'maximum_free_boundary_pressure_residuals_Pa': (
        self.maximum_free_boundary_pressure_residuals_Pa
      ),
      'maximum_free_boundary_normal_velocity_residual_fractions': (
        self.maximum_free_boundary_normal_velocity_residual_fractions
      ),
      'minimum_additional_total_pressure_loss_fractions': (
        self.minimum_additional_total_pressure_loss_fractions
      ),
      'outlet_heights_m': self.outlet_heights_m,
      'pressure_order_verified': self.pressure_order_verified,
      'source_closure_identity_verified': self.source_closure_identity_verified,
      'case_audits_verified': self.case_audits_verified,
      'diagnostics_finite': self.diagnostics_finite,
      'pressure_budget_trend_verified': self.pressure_budget_trend_verified,
      'local_closure_verified': self.local_closure_verified,
      'fidelity_isolation_verified': self.fidelity_isolation_verified,
      'physical_closure_verified': self.physical_closure_verified,
      'canonical_free_boundary_verified': self.canonical_free_boundary_verified,
      'canonical_euler_verified': self.canonical_euler_verified,
      'external_validation_verified': self.external_validation_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'cases': [case.as_report() for case in self.cases],
      'message': self.message,
      'claim_status': (
        'independent-coupled-euler-pressure-continuation-evidence-only; '
        'canonical reflected closure and production promotion remain blocked'
      ),
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainCoupledEulerPressureContinuationRun:
  """Fresh pressure-target solves and their typed ladder measurement."""

  base_request: MocReflectedDomainCoupledEulerFreeBoundaryRequest
  requested_target_ambient_pressures_Pa: tuple[float, ...]
  cases: tuple[MocReflectedDomainCoupledEulerPressureContinuationCase, ...]
  measurement: MocReflectedDomainCoupledEulerPressureContinuationMeasurement
  configuration: tuple[tuple[str, Any], ...]
  configuration_fingerprint: str
  source_closure_fingerprint: str
  fresh_solver_invocation_verified: bool
  fidelity_isolation_verified: bool
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.base_request,
      MocReflectedDomainCoupledEulerFreeBoundaryRequest,
    ):
      raise TypeError(
        'base_request must be a '
        'MocReflectedDomainCoupledEulerFreeBoundaryRequest'
      )
    ####
    targets = tuple(float(value) for value in self.requested_target_ambient_pressures_Pa)
    if not targets:
      raise ValueError('requested_target_ambient_pressures_Pa must not be empty')
    ####
    if any(not isfinite(value) or value <= 0.0 for value in targets):
      raise ValueError(
        'requested_target_ambient_pressures_Pa must contain finite positive values'
      )
    ####
    cases = tuple(self.cases)
    if len(targets) != len(cases):
      raise ValueError('requested targets must match cases')
    ####
    if any(
      not isinstance(
        case,
        MocReflectedDomainCoupledEulerPressureContinuationCase,
      )
      for case in cases
    ):
      raise TypeError('cases must contain typed pressure-continuation cases')
    ####
    if tuple(case.target_ambient_pressure_Pa for case in cases) != targets:
      raise ValueError('case targets must match requested targets')
    ####
    if not isinstance(
      self.measurement,
      MocReflectedDomainCoupledEulerPressureContinuationMeasurement,
    ):
      raise TypeError('measurement must be a typed pressure-continuation measurement')
    ####
    if tuple(self.measurement.cases) != cases:
      raise ValueError('measurement must retain the exact run cases')
    ####
    configuration = tuple(self.configuration)
    if any(
      not isinstance(item, tuple)
      or len(item) != 2
      or not isinstance(item[0], str)
      for item in configuration
    ):
      raise ValueError('configuration must contain (name, value) pairs')
    ####
    fingerprint = str(self.configuration_fingerprint)
    source_fingerprint = str(self.source_closure_fingerprint)
    if not fingerprint or not source_fingerprint:
      raise ValueError('run fingerprints must be non-empty')
    ####
    if source_fingerprint != self.base_request.source_closure_fingerprint:
      raise ValueError('run source fingerprint must match the base request')
    ####
    if self.measurement.source_closure_fingerprint != source_fingerprint:
      raise ValueError('measurement must retain the run source fingerprint')
    ####
    for name in ('fresh_solver_invocation_verified', 'fidelity_isolation_verified'):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    object.__setattr__(self, 'requested_target_ambient_pressures_Pa', targets)
    object.__setattr__(self, 'cases', cases)
    object.__setattr__(self, 'configuration', configuration)
    object.__setattr__(self, 'configuration_fingerprint', fingerprint)
    object.__setattr__(self, 'source_closure_fingerprint', source_fingerprint)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.measurement.converged
  ####

  @property
  def independent_evidence_verified(self) -> bool:
    return self.measurement.independent_evidence_verified
  ####

  @property
  def production_claim_allowed(self) -> bool:
    return False
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': MOC_REFLECTED_DOMAIN_COUPLED_EULER_PRESSURE_CONTINUATION_RUN_OPERATOR_ID,
      'requested_target_ambient_pressures_Pa': self.requested_target_ambient_pressures_Pa,
      'source_closure_fingerprint': self.source_closure_fingerprint,
      'fresh_solver_invocation_verified': self.fresh_solver_invocation_verified,
      'fidelity_isolation_verified': self.fidelity_isolation_verified,
      'configuration': self.configuration,
      'configuration_fingerprint': self.configuration_fingerprint,
      'converged': self.converged,
      'independent_evidence_verified': self.independent_evidence_verified,
      'production_claim_allowed': self.production_claim_allowed,
      'base_request': self.base_request.as_report(),
      'cases': [case.as_report() for case in self.cases],
      'measurement': self.measurement.as_report(),
      'message': self.message,
    }
  ####
####


def _configuration_fingerprint(
  request: MocReflectedDomainCoupledEulerFreeBoundaryRequest,
  targets: tuple[float, ...],
) -> tuple[tuple[tuple[str, Any], ...], str]:
  payload: dict[str, Any] = {
    'base_request': request.as_report(),
    'requested_target_ambient_pressures_Pa': targets,
  }
  serialized = json.dumps(payload, sort_keys=True, default=str)
  configuration = tuple((name, payload[name]) for name in sorted(payload))
  return configuration, sha256(serialized.encode('utf-8')).hexdigest()
####


def _failed_result(
  request: MocReflectedDomainCoupledEulerFreeBoundaryRequest,
  message: str,
) -> MocReflectedDomainCoupledEulerFreeBoundaryResult:
  return MocReflectedDomainCoupledEulerFreeBoundaryResult(
    status=MocReflectedDomainCoupledEulerFreeBoundaryStatus.INVALID_INPUT,
    request=request,
    message=message,
  )
####


def _invalid_measurement(
  message: str,
) -> MocReflectedDomainCoupledEulerPressureContinuationMeasurement:
  return MocReflectedDomainCoupledEulerPressureContinuationMeasurement(
    status=MocReflectedDomainCoupledEulerPressureContinuationStatus.INVALID_INPUT,
    message=message,
  )
####


def _measurement_status(
  *,
  pressure_order_verified: bool,
  source_closure_identity_verified: bool,
  case_audits_verified: bool,
  diagnostics_finite: bool,
  pressure_budget_trend_verified: bool,
  local_closure_verified: bool,
  fidelity_isolation_verified: bool,
) -> tuple[MocReflectedDomainCoupledEulerPressureContinuationStatus, str]:
  if not pressure_order_verified:
    return (
      MocReflectedDomainCoupledEulerPressureContinuationStatus.PRESSURE_ORDER_FAILURE,
      'pressure-continuation targets must be strictly decreasing from the '
      'compatible boundary toward lower ambient pressure',
    )
  ####
  if not source_closure_identity_verified:
    return (
      MocReflectedDomainCoupledEulerPressureContinuationStatus.LINEAGE_FAILURE,
      'pressure cases did not retain one exact upstream global-closure fingerprint',
    )
  ####
  if not case_audits_verified or not diagnostics_finite:
    return (
      MocReflectedDomainCoupledEulerPressureContinuationStatus.AUDIT_FAILURE,
      'independent pressure-continuation audits did not cover finite field and '
      'boundary diagnostics',
    )
  ####
  if not pressure_budget_trend_verified:
    return (
      MocReflectedDomainCoupledEulerPressureContinuationStatus.PRESSURE_BUDGET_FAILURE,
      'subsonic pressure-budget evidence did not retain the expected ordered '
      'loss trend',
    )
  ####
  if not fidelity_isolation_verified:
    return (
      MocReflectedDomainCoupledEulerPressureContinuationStatus.FIDELITY_FAILURE,
      'a pressure-continuation case weakened the research-only promotion stop',
    )
  ####
  if not local_closure_verified:
    return (
      MocReflectedDomainCoupledEulerPressureContinuationStatus.CASE_FAILURE,
      'the pressure-continuation ladder retained an open physical closure case',
    )
  ####
  return (
    MocReflectedDomainCoupledEulerPressureContinuationStatus
    .CONVERGED_RESEARCH_PRESSURE_LADDER,
    'independent coupled Euler pressure-continuation ladder passed local checks; '
    'promotion remains blocked',
  )
####


def measure_reflected_domain_coupled_euler_pressure_continuation(
  cases: Sequence[MocReflectedDomainCoupledEulerPressureContinuationCase],
) -> MocReflectedDomainCoupledEulerPressureContinuationMeasurement:
  """Measure pressure ordering, closure lineage, and independent case evidence."""

  try:
    retained_cases = tuple(cases)
  except TypeError:
    return _invalid_measurement(
      'pressure-continuation cases must be iterable'
    )
  ####
  if len(retained_cases) < 2:
    return _invalid_measurement(
      'at least two pressure-continuation cases are required'
    )
  ####
  if any(
    not isinstance(
      case,
      MocReflectedDomainCoupledEulerPressureContinuationCase,
    )
    for case in retained_cases
  ):
    return _invalid_measurement(
      'pressure-continuation cases must contain typed pressure-continuation cases'
    )
  ####
  targets = tuple(case.target_ambient_pressure_Pa for case in retained_cases)
  source_fingerprints = tuple(
    case.source_closure_fingerprint for case in retained_cases
  )
  source_fingerprint = source_fingerprints[0]
  pressure_order_verified = all(
    second < first for first, second in zip(targets, targets[1:])
  )
  source_closure_identity_verified = bool(
    source_fingerprint
    and all(fingerprint == source_fingerprint for fingerprint in source_fingerprints)
  )
  case_audits_verified = all(
    case.independent_diagnostics_verified for case in retained_cases
  )
  pressure_residuals = tuple(
    0.0
    if case.audit.maximum_free_boundary_pressure_residual_Pa is None
    else float(case.audit.maximum_free_boundary_pressure_residual_Pa)
    for case in retained_cases
  )
  normal_residuals = tuple(
    0.0
    if case.audit.maximum_free_boundary_normal_velocity_residual_fraction is None
    else float(case.audit.maximum_free_boundary_normal_velocity_residual_fraction)
    for case in retained_cases
  )
  loss_fractions = tuple(
    0.0
    if case.result.subsonic_pressure_budget is None
    else float(
      case.result.subsonic_pressure_budget
      .minimum_additional_total_pressure_loss_fraction
    )
    for case in retained_cases
  )
  outlet_heights = tuple(
    0.0
    if not case.result.free_boundary_points_m
    else float(case.result.free_boundary_points_m[-1][1])
    for case in retained_cases
  )
  diagnostics_finite = all(
    (
      case.result.status
      is MocReflectedDomainCoupledEulerFreeBoundaryStatus.TRANSONIC_FRONTIER_FAILURE
      and case.independent_diagnostics_verified
    )
    or (
      case.independent_diagnostics_verified
      and case.audit.maximum_free_boundary_pressure_residual_Pa is not None
      and case.audit.maximum_free_boundary_normal_velocity_residual_fraction is not None
      and bool(case.result.free_boundary_points_m)
      and bool(case.result.free_boundary_pressure_residuals_Pa)
      and bool(case.result.free_boundary_normal_velocity_residuals_m_s)
      and all(
        isfinite(value)
        for value in (
          case.audit.maximum_free_boundary_pressure_residual_Pa,
          case.audit.maximum_free_boundary_normal_velocity_residual_fraction,
          case.result.free_boundary_points_m[-1][0],
          case.result.free_boundary_points_m[-1][1],
        )
      )
    )
    for case in retained_cases
  )
  budgets = tuple(
    case.result.subsonic_pressure_budget for case in retained_cases
  )
  pressure_budget_trend_verified = bool(
    all(budget is not None for budget in budgets)
    and all(
      second >= first - 1.0e-12
      for first, second in zip(loss_fractions, loss_fractions[1:])
    )
  )
  local_closure_verified = all(
    case.local_closure_verified for case in retained_cases
  )
  fidelity_isolation_verified = all(
    case.result.chain_promotion_blocked
    and not case.result.production_claim_allowed
    and not case.result.canonical_free_boundary_verified
    and not case.result.canonical_euler_verified
    and not case.result.external_validation_verified
    and case.audit.chain_promotion_blocked
    and not case.audit.production_claim_allowed
    for case in retained_cases
  )
  status, message = _measurement_status(
    pressure_order_verified=pressure_order_verified,
    source_closure_identity_verified=source_closure_identity_verified,
    case_audits_verified=case_audits_verified,
    diagnostics_finite=diagnostics_finite,
    pressure_budget_trend_verified=pressure_budget_trend_verified,
    local_closure_verified=local_closure_verified,
    fidelity_isolation_verified=fidelity_isolation_verified,
  )
  return MocReflectedDomainCoupledEulerPressureContinuationMeasurement(
    status=status,
    cases=retained_cases,
    audits=tuple(case.audit for case in retained_cases),
    target_ambient_pressures_Pa=targets,
    source_closure_fingerprint=source_fingerprint,
    maximum_free_boundary_pressure_residuals_Pa=pressure_residuals,
    maximum_free_boundary_normal_velocity_residual_fractions=normal_residuals,
    minimum_additional_total_pressure_loss_fractions=loss_fractions,
    outlet_heights_m=outlet_heights,
    pressure_order_verified=pressure_order_verified,
    source_closure_identity_verified=source_closure_identity_verified,
    case_audits_verified=case_audits_verified,
    diagnostics_finite=diagnostics_finite,
    pressure_budget_trend_verified=pressure_budget_trend_verified,
    local_closure_verified=local_closure_verified,
    fidelity_isolation_verified=fidelity_isolation_verified,
    physical_closure_verified=False,
    canonical_free_boundary_verified=False,
    canonical_euler_verified=False,
    external_validation_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    residual_tolerance=retained_cases[0].request.euler_residual_tolerance,
    message=message,
  )
####


def run_reflected_domain_coupled_euler_pressure_continuation(
  request: MocReflectedDomainCoupledEulerFreeBoundaryRequest,
  target_ambient_pressures_Pa: Sequence[float],
) -> MocReflectedDomainCoupledEulerPressureContinuationRun:
  """Freshly solve and independently audit every ambient-pressure target.

  Only ``mixed_regime_request.ambient_pressure_Pa`` changes between cases.
  All upstream closure data and numerical controls, including an optional
  outlet pressure condition, are retained exactly from ``request``.  This
  makes the sweep an ambient-target study rather than an implicit change to
  the outlet boundary model.
  """

  if not isinstance(
    request,
    MocReflectedDomainCoupledEulerFreeBoundaryRequest,
  ):
    raise TypeError(
      'request must be a '
      'MocReflectedDomainCoupledEulerFreeBoundaryRequest'
    )
  ####
  try:
    requested_targets = tuple(float(value) for value in target_ambient_pressures_Pa)
  except (TypeError, ValueError):
    raise ValueError(
      'target_ambient_pressures_Pa must be an iterable of numeric values'
    ) from None
  ####
  if len(requested_targets) < 2:
    raise ValueError(
      'at least two target ambient pressures are required for continuation'
    )
  ####
  if any(
    not isfinite(value) or value <= 0.0 for value in requested_targets
  ):
    raise ValueError(
      'target ambient pressures must be finite and positive'
    )
  ####
  configuration, configuration_fingerprint = _configuration_fingerprint(
    request,
    requested_targets,
  )
  cases: list[MocReflectedDomainCoupledEulerPressureContinuationCase] = []
  for target in requested_targets:
    mixed_request = replace(
      request.mixed_regime_request,
      ambient_pressure_Pa=target,
    )
    case_request = replace(request, mixed_regime_request=mixed_request)
    try:
      result = solve_reflected_domain_coupled_euler_free_boundary(case_request)
    except (ArithmeticError, FloatingPointError, RuntimeError, TypeError, ValueError) as error:
      result = _failed_result(
        case_request,
        f'fresh coupled Euler pressure case raised: {error}',
      )
    ####
    audit = measure_reflected_domain_coupled_euler_free_boundary(result)
    cases.append(
      MocReflectedDomainCoupledEulerPressureContinuationCase(
        target_ambient_pressure_Pa=target,
        request=case_request,
        result=result,
        audit=audit,
      )
    )
  ####
  retained_cases = tuple(cases)
  measurement = measure_reflected_domain_coupled_euler_pressure_continuation(
    retained_cases
  )
  fidelity_isolation_verified = bool(
    all(
      case.result.chain_promotion_blocked
      and not case.result.production_claim_allowed
      and case.audit.chain_promotion_blocked
      and not case.audit.production_claim_allowed
      for case in retained_cases
    )
  )
  return MocReflectedDomainCoupledEulerPressureContinuationRun(
    base_request=request,
    requested_target_ambient_pressures_Pa=requested_targets,
    cases=retained_cases,
    measurement=measurement,
    configuration=configuration,
    configuration_fingerprint=configuration_fingerprint,
    source_closure_fingerprint=request.source_closure_fingerprint,
    fresh_solver_invocation_verified=(
      len(retained_cases) == len(requested_targets)
    ),
    fidelity_isolation_verified=fidelity_isolation_verified,
    message=(
      'fresh coupled Euler pressure-continuation run completed; local and '
      'canonical promotion gates remain separately reported'
    ),
  )
####
