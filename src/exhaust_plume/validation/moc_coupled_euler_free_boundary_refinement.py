"""Resolution evidence for the coupled Euler/free-boundary research lane.

Each ladder member is a fresh solver invocation followed by the independent
conservative-field audit.  The ladder records mesh growth and local evidence,
but it does not infer convergence from a single field and never promotes a
research result into a canonical reflected-MOC chain.
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
  'MOC_REFLECTED_DOMAIN_COUPLED_EULER_FREE_BOUNDARY_REFINEMENT_OPERATOR_ID',
  'MocReflectedDomainCoupledEulerFreeBoundaryRefinementStatus',
  'MocReflectedDomainCoupledEulerFreeBoundaryRefinementCase',
  'MocReflectedDomainCoupledEulerFreeBoundaryRefinementMeasurement',
  'measure_reflected_domain_coupled_euler_free_boundary_refinement',
  'MOC_REFLECTED_DOMAIN_COUPLED_EULER_FREE_BOUNDARY_REFINEMENT_RUN_OPERATOR_ID',
  'MocReflectedDomainCoupledEulerFreeBoundaryRefinementRun',
  'run_reflected_domain_coupled_euler_free_boundary_refinement',
)


MOC_REFLECTED_DOMAIN_COUPLED_EULER_FREE_BOUNDARY_REFINEMENT_OPERATOR_ID = (
  'op.moc.reflected-domain.coupled-euler-free-boundary-refinement'
)
MOC_REFLECTED_DOMAIN_COUPLED_EULER_FREE_BOUNDARY_REFINEMENT_RUN_OPERATOR_ID = (
  'op.moc.reflected-domain.coupled-euler-free-boundary-refinement-run'
)


class MocReflectedDomainCoupledEulerFreeBoundaryRefinementStatus(str, Enum):
  """Outcome for one independently measured coupled-field ladder."""

  CONVERGED_RESEARCH_LADDER = (
    'converged-research-coupled-euler-free-boundary-ladder'
  )
  INVALID_INPUT = 'invalid_input'
  RESOLUTION_FAILURE = 'coupled-euler-refinement-resolution-failure'
  CASE_FAILURE = 'coupled-euler-refinement-case-failure'
  AUDIT_FAILURE = 'coupled-euler-refinement-audit-failure'
  FIDELITY_FAILURE = 'coupled-euler-refinement-fidelity-failure'
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainCoupledEulerFreeBoundaryRefinementCase:
  """One fresh coupled-field solve and its independent audit."""

  resolution: tuple[int, int]
  request: MocReflectedDomainCoupledEulerFreeBoundaryRequest
  result: MocReflectedDomainCoupledEulerFreeBoundaryResult
  audit: MocReflectedDomainCoupledEulerFreeBoundaryAudit

  def __post_init__(self) -> None:
    resolution = tuple(self.resolution)
    if len(resolution) != 2:
      raise ValueError('resolution must contain axial and transverse counts')
    ####
    if any(isinstance(value, bool) or not isinstance(value, int) for value in resolution):
      raise ValueError('resolution counts must be integers')
    ####
    if resolution[0] < 4 or resolution[1] < 3:
      raise ValueError(
        'axial resolution must be at least four and transverse resolution '
        'must be at least three'
      )
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
    if self.request.axial_cell_count != resolution[0]:
      raise ValueError('request axial count must match resolution')
    ####
    if self.request.transverse_cell_count != resolution[1]:
      raise ValueError('request transverse count must match resolution')
    ####
    if self.result.request != self.request:
      raise ValueError('result must retain the exact resolution request')
    ####
    if self.audit.candidate is not None and self.audit.candidate != self.result:
      raise ValueError('audit must retain the exact resolved case')
    ####
    object.__setattr__(self, 'resolution', resolution)
  ####

  @property
  def cell_count(self) -> int:
    return self.resolution[0] * self.resolution[1]
  ####

  @property
  def local_closure_verified(self) -> bool:
    return bool(self.result.converged and self.audit.local_consistency_verified)
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'resolution': self.resolution,
      'cell_count': self.cell_count,
      'solver_status': self.result.status.value,
      'solver_converged': self.result.converged,
      'audit_status': self.audit.status.value,
      'audit_converged': self.audit.converged,
      'local_closure_verified': self.local_closure_verified,
      'maximum_conservative_euler_residual': (
        self.result.maximum_conservative_euler_residual
      ),
      'maximum_free_boundary_pressure_residual_Pa': (
        self.result.maximum_free_boundary_pressure_residual_Pa
      ),
      'maximum_free_boundary_normal_velocity_residual_fraction': (
        self.result.maximum_free_boundary_normal_velocity_residual_fraction
      ),
      'result': self.result.as_report(),
      'audit': self.audit.as_report(),
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainCoupledEulerFreeBoundaryRefinementMeasurement:
  """Independent ladder evidence below the canonical promotion ceiling."""

  status: MocReflectedDomainCoupledEulerFreeBoundaryRefinementStatus
  cases: tuple[MocReflectedDomainCoupledEulerFreeBoundaryRefinementCase, ...] = ()
  audits: tuple[MocReflectedDomainCoupledEulerFreeBoundaryAudit, ...] = ()
  resolutions: tuple[tuple[int, int], ...] = ()
  cell_counts: tuple[int, ...] = ()
  maximum_conservative_euler_residuals: tuple[float, ...] = ()
  maximum_free_boundary_pressure_residuals_Pa: tuple[float, ...] = ()
  maximum_free_boundary_normal_velocity_residual_fractions: tuple[float, ...] = ()
  maximum_entropy_production_fractions: tuple[float, ...] = ()
  outlet_heights_m: tuple[float, ...] = ()
  resolution_order_verified: bool = False
  mesh_growth_verified: bool = False
  case_audits_verified: bool = False
  conservative_residuals_finite: bool = False
  boundary_diagnostics_finite: bool = False
  pressure_budget_diagnostics_verified: bool = False
  entropy_production_maps_verified: bool = False
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
    MOC_REFLECTED_DOMAIN_COUPLED_EULER_FREE_BOUNDARY_REFINEMENT_OPERATOR_ID
  )
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainCoupledEulerFreeBoundaryRefinementStatus,
    ):
      raise TypeError(
        'status must be a '
        'MocReflectedDomainCoupledEulerFreeBoundaryRefinementStatus'
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
        MocReflectedDomainCoupledEulerFreeBoundaryRefinementCase,
      )
      for case in cases
    ):
      raise TypeError('cases must contain typed coupled Euler refinement cases')
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
    resolutions = tuple(tuple(value) for value in self.resolutions)
    if resolutions and resolutions != tuple(case.resolution for case in cases):
      raise ValueError('resolutions must match case resolutions')
    ####
    resolutions = tuple(case.resolution for case in cases)
    object.__setattr__(self, 'resolutions', resolutions)
    for name in (
      'cell_counts',
      'maximum_conservative_euler_residuals',
      'maximum_free_boundary_pressure_residuals_Pa',
      'maximum_free_boundary_normal_velocity_residual_fractions',
      'maximum_entropy_production_fractions',
      'outlet_heights_m',
    ):
      values = tuple(getattr(self, name))
      if len(values) != len(cases):
        raise ValueError(f'{name} must match the case count')
      ####
      numeric_values = tuple(float(value) for value in values)
      if any(not isfinite(value) or value < 0.0 for value in numeric_values):
        raise ValueError(f'{name} must contain finite nonnegative values')
      ####
      object.__setattr__(self, name, numeric_values)
    ####
    tolerance = float(self.residual_tolerance)
    if not isfinite(tolerance) or tolerance <= 0.0:
      raise ValueError('residual_tolerance must be finite and positive')
    ####
    object.__setattr__(self, 'residual_tolerance', tolerance)
    for name in (
      'resolution_order_verified',
      'mesh_growth_verified',
      'case_audits_verified',
      'conservative_residuals_finite',
      'boundary_diagnostics_finite',
      'local_closure_verified',
      'fidelity_isolation_verified',
      'entropy_production_maps_verified',
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
      raise ValueError('refinement evidence cannot claim canonical physical closure')
    ####
    if not self.chain_promotion_blocked:
      raise ValueError('refinement evidence must block chain promotion')
    ####
    if self.production_claim_allowed:
      raise ValueError('refinement evidence cannot allow production claims')
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
    return self.status is (
      MocReflectedDomainCoupledEulerFreeBoundaryRefinementStatus
      .CONVERGED_RESEARCH_LADDER
    )
  ####

  @property
  def local_consistency_verified(self) -> bool:
    """Whether the ladder passed local gates without promotion."""

    return bool(
      self.converged
      and self.resolution_order_verified
      and self.mesh_growth_verified
      and self.case_audits_verified
      and self.conservative_residuals_finite
      and self.boundary_diagnostics_finite
      and self.pressure_budget_diagnostics_verified
      and self.entropy_production_maps_verified
      and self.local_closure_verified
      and self.fidelity_isolation_verified
      and not self.physical_closure_verified
      and not self.canonical_free_boundary_verified
      and not self.canonical_euler_verified
      and not self.external_validation_verified
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'local_consistency_verified': self.local_consistency_verified,
      'resolutions': self.resolutions,
      'cell_counts': self.cell_counts,
      'maximum_conservative_euler_residuals': (
        self.maximum_conservative_euler_residuals
      ),
      'maximum_free_boundary_pressure_residuals_Pa': (
        self.maximum_free_boundary_pressure_residuals_Pa
      ),
      'maximum_free_boundary_normal_velocity_residual_fractions': (
        self.maximum_free_boundary_normal_velocity_residual_fractions
      ),
      'maximum_entropy_production_fractions': (
        self.maximum_entropy_production_fractions
      ),
      'outlet_heights_m': self.outlet_heights_m,
      'resolution_order_verified': self.resolution_order_verified,
      'mesh_growth_verified': self.mesh_growth_verified,
      'case_audits_verified': self.case_audits_verified,
      'conservative_residuals_finite': self.conservative_residuals_finite,
      'boundary_diagnostics_finite': self.boundary_diagnostics_finite,
      'pressure_budget_diagnostics_verified': self.pressure_budget_diagnostics_verified,
      'entropy_production_maps_verified': self.entropy_production_maps_verified,
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
        'independent-coupled-euler-free-boundary-resolution-evidence-only; '
        'canonical reflected closure and production promotion remain blocked'
      ),
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainCoupledEulerFreeBoundaryRefinementRun:
  """Fresh solver executions and their typed ladder measurement."""

  base_request: MocReflectedDomainCoupledEulerFreeBoundaryRequest
  requested_resolutions: tuple[tuple[int, int], ...]
  cases: tuple[MocReflectedDomainCoupledEulerFreeBoundaryRefinementCase, ...]
  measurement: MocReflectedDomainCoupledEulerFreeBoundaryRefinementMeasurement
  configuration: tuple[tuple[str, Any], ...]
  configuration_fingerprint: str
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
    resolutions = tuple(tuple(value) for value in self.requested_resolutions)
    if not resolutions:
      raise ValueError('requested_resolutions must not be empty')
    ####
    if len(resolutions) != len(self.cases):
      raise ValueError('requested_resolutions must match cases')
    ####
    if any(
      case.resolution != resolution
      for case, resolution in zip(self.cases, resolutions, strict=True)
    ):
      raise ValueError('case resolutions must match requested_resolutions')
    ####
    if any(
      not isinstance(
        case,
        MocReflectedDomainCoupledEulerFreeBoundaryRefinementCase,
      )
      for case in self.cases
    ):
      raise TypeError('cases must contain typed coupled Euler refinement cases')
    ####
    if not isinstance(
      self.measurement,
      MocReflectedDomainCoupledEulerFreeBoundaryRefinementMeasurement,
    ):
      raise TypeError('measurement must be a typed coupled Euler refinement measurement')
    ####
    if tuple(self.measurement.cases) != tuple(self.cases):
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
    object.__setattr__(self, 'requested_resolutions', resolutions)
    object.__setattr__(self, 'configuration', configuration)
    fingerprint = str(self.configuration_fingerprint)
    if not fingerprint:
      raise ValueError('configuration_fingerprint must be non-empty')
    ####
    object.__setattr__(self, 'configuration_fingerprint', fingerprint)
    for name in ('fresh_solver_invocation_verified', 'fidelity_isolation_verified'):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.measurement.converged
  ####

  @property
  def production_claim_allowed(self) -> bool:
    return False
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': MOC_REFLECTED_DOMAIN_COUPLED_EULER_FREE_BOUNDARY_REFINEMENT_RUN_OPERATOR_ID,
      'requested_resolutions': self.requested_resolutions,
      'fresh_solver_invocation_verified': self.fresh_solver_invocation_verified,
      'fidelity_isolation_verified': self.fidelity_isolation_verified,
      'configuration': self.configuration,
      'configuration_fingerprint': self.configuration_fingerprint,
      'converged': self.converged,
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
  resolutions: tuple[tuple[int, int], ...],
) -> tuple[tuple[tuple[str, Any], ...], str]:
  payload: dict[str, Any] = {
    'base_request': request.as_report(),
    'requested_resolutions': resolutions,
  }
  serialized = json.dumps(payload, sort_keys=True, default=str)
  configuration = tuple(
    (name, payload[name]) for name in sorted(payload)
  )
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


def _measurement_status(
  cases: tuple[MocReflectedDomainCoupledEulerFreeBoundaryRefinementCase, ...],
  *,
  resolution_order_verified: bool,
  mesh_growth_verified: bool,
  case_audits_verified: bool,
  conservative_residuals_finite: bool,
  boundary_diagnostics_finite: bool,
  pressure_budget_diagnostics_verified: bool,
  entropy_production_maps_verified: bool,
  local_closure_verified: bool,
  fidelity_isolation_verified: bool,
) -> tuple[MocReflectedDomainCoupledEulerFreeBoundaryRefinementStatus, str]:
  if not resolution_order_verified or not mesh_growth_verified:
    return (
      MocReflectedDomainCoupledEulerFreeBoundaryRefinementStatus.RESOLUTION_FAILURE,
      'requested coupled Euler resolutions are not a strictly growing ladder',
    )
  ####
  if (
    not case_audits_verified
    or not conservative_residuals_finite
    or not boundary_diagnostics_finite
    or not pressure_budget_diagnostics_verified
    or not entropy_production_maps_verified
  ):
    return (
      MocReflectedDomainCoupledEulerFreeBoundaryRefinementStatus.AUDIT_FAILURE,
      'independent coupled Euler audits did not cover finite field, boundary, and entropy-map diagnostics',
    )
  ####
  if not fidelity_isolation_verified:
    return (
      MocReflectedDomainCoupledEulerFreeBoundaryRefinementStatus.FIDELITY_FAILURE,
      'a coupled Euler refinement case weakened the research-only promotion stop',
    )
  ####
  if not local_closure_verified:
    failed = tuple(
      case.resolution for case in cases if not case.local_closure_verified
    )
    return (
      MocReflectedDomainCoupledEulerFreeBoundaryRefinementStatus.CASE_FAILURE,
      f'coupled Euler/free-boundary local closure was not reached at {failed}',
    )
  ####
  return (
    MocReflectedDomainCoupledEulerFreeBoundaryRefinementStatus.CONVERGED_RESEARCH_LADDER,
    'independent coupled Euler/free-boundary ladder passed local checks; promotion remains blocked',
  )
####


def _diagnostic_value(value: float | None) -> float:
  """Keep missing diagnostics representable while retaining their absence."""

  return 0.0 if value is None else float(value)
####


def _diagnostic_is_finite(value: float | None) -> bool:
  return value is not None and isfinite(float(value))
####


def measure_reflected_domain_coupled_euler_free_boundary_refinement(
  cases: Sequence[MocReflectedDomainCoupledEulerFreeBoundaryRefinementCase],
) -> MocReflectedDomainCoupledEulerFreeBoundaryRefinementMeasurement:
  """Measure mesh growth, independent audits, and promotion isolation."""

  try:
    retained_cases = tuple(cases)
  except TypeError:
    return MocReflectedDomainCoupledEulerFreeBoundaryRefinementMeasurement(
      status=MocReflectedDomainCoupledEulerFreeBoundaryRefinementStatus.INVALID_INPUT,
      message='coupled Euler refinement cases must be iterable',
    )
  ####
  if not retained_cases:
    return MocReflectedDomainCoupledEulerFreeBoundaryRefinementMeasurement(
      status=MocReflectedDomainCoupledEulerFreeBoundaryRefinementStatus.INVALID_INPUT,
      message='coupled Euler refinement requires at least one case',
    )
  ####
  if len(retained_cases) < 2:
    return MocReflectedDomainCoupledEulerFreeBoundaryRefinementMeasurement(
      status=MocReflectedDomainCoupledEulerFreeBoundaryRefinementStatus.INVALID_INPUT,
      message='at least two coupled Euler refinement cases are required',
    )
  ####
  if any(
    not isinstance(
      case,
      MocReflectedDomainCoupledEulerFreeBoundaryRefinementCase,
    )
    for case in retained_cases
  ):
    return MocReflectedDomainCoupledEulerFreeBoundaryRefinementMeasurement(
      status=MocReflectedDomainCoupledEulerFreeBoundaryRefinementStatus.INVALID_INPUT,
      message='refinement cases must contain typed coupled Euler refinement cases',
    )
  ####
  resolutions = tuple(case.resolution for case in retained_cases)
  cell_counts = tuple(case.cell_count for case in retained_cases)
  euler_residuals = tuple(
    _diagnostic_value(case.audit.maximum_conservative_euler_residual)
    for case in retained_cases
  )
  pressure_residuals = tuple(
    _diagnostic_value(case.audit.maximum_free_boundary_pressure_residual_Pa)
    for case in retained_cases
  )
  normal_residuals = tuple(
    _diagnostic_value(
      case.audit.maximum_free_boundary_normal_velocity_residual_fraction
    )
    for case in retained_cases
  )
  entropy_production_fractions = tuple(
    _diagnostic_value(case.audit.maximum_entropy_production_fraction)
    for case in retained_cases
  )
  outlet_heights = tuple(
    float(case.result.free_boundary_points_m[-1][1])
    if case.result.free_boundary_points_m
    else 0.0
    for case in retained_cases
  )
  resolution_order_verified = all(
    second[0] > first[0] and second[1] > first[1]
    for first, second in zip(resolutions, resolutions[1:])
  )
  mesh_growth_verified = all(
    second > first for first, second in zip(cell_counts, cell_counts[1:])
  )
  case_audits_verified = all(
    case.audit.residual_channels_recomputed
    and case.audit.residual_report_verified
    and case.audit.promotion_flags_verified
    for case in retained_cases
  )
  conservative_residuals_finite = all(
    _diagnostic_is_finite(case.audit.maximum_conservative_euler_residual)
    for case in retained_cases
  )
  boundary_diagnostics_finite = all(
    _diagnostic_is_finite(case.audit.maximum_free_boundary_pressure_residual_Pa)
    and _diagnostic_is_finite(
      case.audit.maximum_free_boundary_normal_velocity_residual_fraction
    )
    and bool(case.result.free_boundary_points_m)
    and all(isfinite(value) for value in case.result.free_boundary_points_m[-1])
    for case in retained_cases
  )
  pressure_budget_diagnostics_verified = all(
    case.audit.pressure_budget_verified for case in retained_cases
  )
  entropy_production_maps_verified = all(
    case.audit.entropy_production_map_verified for case in retained_cases
  )
  local_closure_verified = all(
    case.local_closure_verified for case in retained_cases
  )
  fidelity_isolation_verified = all(
    case.result.chain_promotion_blocked
    and not case.result.production_claim_allowed
    and case.audit.chain_promotion_blocked
    and not case.audit.production_claim_allowed
    for case in retained_cases
  )
  status, message = _measurement_status(
    retained_cases,
    resolution_order_verified=resolution_order_verified,
    mesh_growth_verified=mesh_growth_verified,
    case_audits_verified=case_audits_verified,
    conservative_residuals_finite=conservative_residuals_finite,
    boundary_diagnostics_finite=boundary_diagnostics_finite,
    pressure_budget_diagnostics_verified=pressure_budget_diagnostics_verified,
    entropy_production_maps_verified=entropy_production_maps_verified,
    local_closure_verified=local_closure_verified,
    fidelity_isolation_verified=fidelity_isolation_verified,
  )
  return MocReflectedDomainCoupledEulerFreeBoundaryRefinementMeasurement(
    status=status,
    cases=retained_cases,
    audits=tuple(case.audit for case in retained_cases),
    resolutions=resolutions,
    cell_counts=cell_counts,
    maximum_conservative_euler_residuals=euler_residuals,
    maximum_free_boundary_pressure_residuals_Pa=pressure_residuals,
    maximum_free_boundary_normal_velocity_residual_fractions=normal_residuals,
    maximum_entropy_production_fractions=entropy_production_fractions,
    outlet_heights_m=outlet_heights,
    resolution_order_verified=resolution_order_verified,
    mesh_growth_verified=mesh_growth_verified,
    case_audits_verified=case_audits_verified,
    conservative_residuals_finite=conservative_residuals_finite,
    boundary_diagnostics_finite=boundary_diagnostics_finite,
    pressure_budget_diagnostics_verified=pressure_budget_diagnostics_verified,
    entropy_production_maps_verified=entropy_production_maps_verified,
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


def run_reflected_domain_coupled_euler_free_boundary_refinement(
  request: MocReflectedDomainCoupledEulerFreeBoundaryRequest,
  resolutions: Sequence[tuple[int, int]],
) -> MocReflectedDomainCoupledEulerFreeBoundaryRefinementRun:
  """Freshly solve and independently audit every declared mesh resolution."""

  if not isinstance(
    request,
    MocReflectedDomainCoupledEulerFreeBoundaryRequest,
  ):
    raise TypeError(
      'request must be a '
      'MocReflectedDomainCoupledEulerFreeBoundaryRequest'
    )
  ####
  requested_resolutions = tuple(tuple(value) for value in resolutions)
  if not requested_resolutions:
    raise ValueError('resolutions must not be empty')
  ####
  if any(len(resolution) != 2 for resolution in requested_resolutions):
    raise ValueError('resolutions must contain (axial, transverse) pairs')
  ####
  if any(
    isinstance(value, bool) or not isinstance(value, int)
    for resolution in requested_resolutions
    for value in resolution
  ):
    raise ValueError('resolution counts must be integers')
  ####
  if any(
    resolution[0] < 4 or resolution[1] < 3
    for resolution in requested_resolutions
  ):
    raise ValueError(
      'axial resolutions must be at least four and transverse resolutions '
      'must be at least three'
    )
  ####
  configuration, configuration_fingerprint = _configuration_fingerprint(
    request,
    requested_resolutions,
  )
  cases: list[MocReflectedDomainCoupledEulerFreeBoundaryRefinementCase] = []
  for resolution in requested_resolutions:
    case_request = replace(
      request,
      axial_cell_count=resolution[0],
      transverse_cell_count=resolution[1],
    )
    try:
      result = solve_reflected_domain_coupled_euler_free_boundary(case_request)
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      result = _failed_result(case_request, f'fresh coupled Euler solve raised: {error}')
    ####
    audit = measure_reflected_domain_coupled_euler_free_boundary(result)
    cases.append(
      MocReflectedDomainCoupledEulerFreeBoundaryRefinementCase(
        resolution=resolution,
        request=case_request,
        result=result,
        audit=audit,
      )
    )
  ####
  retained_cases = tuple(cases)
  measurement = measure_reflected_domain_coupled_euler_free_boundary_refinement(
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
  return MocReflectedDomainCoupledEulerFreeBoundaryRefinementRun(
    base_request=request,
    requested_resolutions=requested_resolutions,
    cases=retained_cases,
    measurement=measurement,
    configuration=configuration,
    configuration_fingerprint=configuration_fingerprint,
    fresh_solver_invocation_verified=(len(retained_cases) == len(requested_resolutions)),
    fidelity_isolation_verified=fidelity_isolation_verified,
    message=(
      'fresh coupled Euler/free-boundary refinement run completed; local '
      'and canonical promotion gates remain separately reported'
    ),
  )
####
