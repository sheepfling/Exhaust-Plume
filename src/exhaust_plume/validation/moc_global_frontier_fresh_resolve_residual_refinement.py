"""Case/refinement audit for fresh-frontier conservative residual evidence.

The fresh-frontier residual adapter validates one exact candidate at a time.
This module adds the next evidence boundary: independently compare those
results across declared cases and increasing resolutions.  It never creates
or repairs a candidate, and a locally refining research ladder remains below
canonical free-boundary, shock-cell, product, and release claims.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Any, Sequence

from exhaust_plume.validation.moc_global_frontier_fresh_resolve_residual import (
  MocReflectedDomainGlobalFrontierFreshResolveResidualResult,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_FRONTIER_FRESH_RESOLVE_RESIDUAL_REFINEMENT_OPERATOR_ID',
  'MocReflectedDomainGlobalFrontierFreshResolveResidualRefinementCase',
  'MocReflectedDomainGlobalFrontierFreshResolveResidualRefinementStatus',
  'MocReflectedDomainGlobalFrontierFreshResolveResidualRefinementMeasurement',
  'measure_moc_global_frontier_fresh_resolve_residual_refinement',
)


MOC_REFLECTED_DOMAIN_GLOBAL_FRONTIER_FRESH_RESOLVE_RESIDUAL_REFINEMENT_OPERATOR_ID = (
  'op.moc.reflected-domain.global-frontier-fresh-resolve-residual-refinement-v1'
)


class MocReflectedDomainGlobalFrontierFreshResolveResidualRefinementStatus(
  str,
  Enum,
):
  """Typed outcomes of the fresh-frontier residual refinement audit."""

  CONVERGED_LOCAL_REFINEMENT = (
    'converged-global-frontier-fresh-resolve-residual-local-refinement'
  )
  CONVERGED_CROSS_CASE_REFINEMENT = (
    'converged-global-frontier-fresh-resolve-residual-cross-case-refinement'
  )
  INVALID_INPUT = 'invalid_input'
  CASE_FAILURE = 'global-frontier-fresh-resolve-residual-case-failure'
  FRESH_AUDIT_FAILURE = (
    'global-frontier-fresh-resolve-residual-fresh-audit-failure'
  )
  LINEAGE_FAILURE = (
    'global-frontier-fresh-resolve-residual-refinement-lineage-failure'
  )
  RESOLUTION_ORDER_FAILURE = (
    'global-frontier-fresh-resolve-residual-refinement-resolution-order-failure'
  )
  RESPONSE_MODE_FAILURE = (
    'global-frontier-fresh-resolve-residual-refinement-response-mode-failure'
  )
  RESIDUAL_FAILURE = (
    'global-frontier-fresh-resolve-residual-refinement-residual-failure'
  )
  FLAG_FAILURE = (
    'global-frontier-fresh-resolve-residual-refinement-flag-failure'
  )
####


def _candidate_resolution_sample_count(
  result: MocReflectedDomainGlobalFrontierFreshResolveResidualResult,
) -> int | None:
  candidate = result.fresh_resolve.candidate_closure
  if candidate is None:
    return None
  ####
  global_euler = candidate.global_euler
  physical_field = None if global_euler is None else global_euler.physical_field
  field = None if physical_field is None else physical_field.field
  if field is not None:
    return len(field.ambient_boundary.points_m)
  ####
  boundary = candidate.downstream_boundary
  if boundary is None:
    return None
  ####
  return len(boundary.boundary_points_m)
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalFrontierFreshResolveResidualRefinementCase:
  """One independently audited fresh-frontier result at a declared resolution."""

  case_id: str
  resolution_sample_count: int
  result: MocReflectedDomainGlobalFrontierFreshResolveResidualResult

  def __post_init__(self) -> None:
    case_id = str(self.case_id)
    if not case_id:
      raise ValueError('case_id must be non-empty')
    ####
    if (
      isinstance(self.resolution_sample_count, bool)
      or not isinstance(self.resolution_sample_count, int)
      or self.resolution_sample_count < 3
    ):
      raise ValueError('resolution_sample_count must be an integer >= 3')
    ####
    if not isinstance(
      self.result,
      MocReflectedDomainGlobalFrontierFreshResolveResidualResult,
    ):
      raise TypeError(
        'result must be a '
        'MocReflectedDomainGlobalFrontierFreshResolveResidualResult'
      )
    ####
    retained_count = _candidate_resolution_sample_count(self.result)
    if retained_count is not None and retained_count != self.resolution_sample_count:
      raise ValueError(
        'resolution_sample_count must match the exact retained fresh candidate '
        'sample count'
      )
    ####
    object.__setattr__(self, 'case_id', case_id)
  ####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalFrontierFreshResolveResidualRefinementMeasurement:
  """Independent per-channel refinement evidence below production promotion."""

  status: MocReflectedDomainGlobalFrontierFreshResolveResidualRefinementStatus
  cases: tuple[
    MocReflectedDomainGlobalFrontierFreshResolveResidualRefinementCase,
    ...
  ]
  case_ids: tuple[str, ...]
  resolution_sample_counts: tuple[int, ...]
  source_closure_fingerprints: tuple[str | None, ...]
  candidate_closure_fingerprints: tuple[str | None, ...]
  initial_residual_norms: tuple[float | None, ...]
  final_residual_norms: tuple[float | None, ...]
  maximum_mass_flux_residuals_kg_m2_s: tuple[float | None, ...]
  maximum_normal_momentum_residuals_Pa: tuple[float | None, ...]
  maximum_energy_flux_residuals_W_m2: tuple[float | None, ...]
  response_mode_ids: tuple[str | None, ...]
  fresh_audit_verified: tuple[bool, ...]
  strict_residual_descent_verified: tuple[bool, ...]
  independent_residual_audit_verified: tuple[bool, ...]
  case_audits_verified: bool
  case_identity_verified: bool
  candidate_identity_verified: bool
  resolution_order_verified: bool
  response_mode_identity_verified: bool
  residuals_finite: bool
  residuals_nonincreasing_verified: bool
  residual_reduction_verified: bool
  cross_case_verified: bool
  local_refinement_verified: bool
  refinement_convergence_verified: bool
  fidelity_flags_verified: bool
  canonical_free_boundary_verified: bool = False
  canonical_euler_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  refinement_tolerance: float = 1.0e-8
  message: str = ''
  operator_id: str = (
    MOC_REFLECTED_DOMAIN_GLOBAL_FRONTIER_FRESH_RESOLVE_RESIDUAL_REFINEMENT_OPERATOR_ID
  )

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalFrontierFreshResolveResidualRefinementStatus,
    ):
      raise TypeError('status must be a fresh-frontier residual refinement status')
    ####
    cases = tuple(self.cases)
    if any(
      not isinstance(
        case,
        MocReflectedDomainGlobalFrontierFreshResolveResidualRefinementCase,
      )
      for case in cases
    ):
      raise TypeError('cases must contain typed fresh-frontier residual cases')
    ####
    case_ids = tuple(str(value) for value in self.case_ids)
    resolutions = tuple(self.resolution_sample_counts)
    source_fingerprints = tuple(self.source_closure_fingerprints)
    candidate_fingerprints = tuple(self.candidate_closure_fingerprints)
    initial_norms = tuple(self.initial_residual_norms)
    final_norms = tuple(self.final_residual_norms)
    mass = tuple(self.maximum_mass_flux_residuals_kg_m2_s)
    momentum = tuple(self.maximum_normal_momentum_residuals_Pa)
    energy = tuple(self.maximum_energy_flux_residuals_W_m2)
    response_modes = tuple(self.response_mode_ids)
    fresh_audits = tuple(self.fresh_audit_verified)
    strict_descent = tuple(self.strict_residual_descent_verified)
    independent_audits = tuple(self.independent_residual_audit_verified)
    lengths = {
      len(cases),
      len(case_ids),
      len(resolutions),
      len(source_fingerprints),
      len(candidate_fingerprints),
      len(initial_norms),
      len(final_norms),
      len(mass),
      len(momentum),
      len(energy),
      len(response_modes),
      len(fresh_audits),
      len(strict_descent),
      len(independent_audits),
    }
    if len(lengths) != 1:
      raise ValueError('refinement summaries must match the case count')
    ####
    if any(
      isinstance(value, bool) or not isinstance(value, int) or value < 0
      for value in resolutions
    ):
      raise ValueError('resolution sample counts must be nonnegative integers')
    ####
    for name, values in (
      ('initial_residual_norms', initial_norms),
      ('final_residual_norms', final_norms),
      ('maximum_mass_flux_residuals_kg_m2_s', mass),
      ('maximum_normal_momentum_residuals_Pa', momentum),
      ('maximum_energy_flux_residuals_W_m2', energy),
    ):
      for value in values:
        if value is None:
          continue
        numeric = float(value)
        if not isfinite(numeric) or numeric < 0.0:
          raise ValueError(f'{name} must contain finite nonnegative values')
    ####
    for name, values in (
      ('fresh_audit_verified', fresh_audits),
      ('strict_residual_descent_verified', strict_descent),
      ('independent_residual_audit_verified', independent_audits),
    ):
      if any(not isinstance(value, bool) for value in values):
        raise TypeError(f'{name} must contain bool values')
    ####
    for name in (
      'case_audits_verified',
      'case_identity_verified',
      'candidate_identity_verified',
      'resolution_order_verified',
      'response_mode_identity_verified',
      'residuals_finite',
      'residuals_nonincreasing_verified',
      'residual_reduction_verified',
      'cross_case_verified',
      'local_refinement_verified',
      'refinement_convergence_verified',
      'fidelity_flags_verified',
      'canonical_free_boundary_verified',
      'canonical_euler_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    ####
    tolerance = float(self.refinement_tolerance)
    if not isfinite(tolerance) or tolerance <= 0.0:
      raise ValueError('refinement_tolerance must be finite and positive')
    ####
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError(
        'fresh-frontier residual refinement must remain promotion-blocked'
      )
    ####
    object.__setattr__(self, 'cases', cases)
    object.__setattr__(self, 'case_ids', case_ids)
    object.__setattr__(self, 'resolution_sample_counts', resolutions)
    object.__setattr__(self, 'source_closure_fingerprints', source_fingerprints)
    object.__setattr__(self, 'candidate_closure_fingerprints', candidate_fingerprints)
    object.__setattr__(self, 'initial_residual_norms', initial_norms)
    object.__setattr__(self, 'final_residual_norms', final_norms)
    object.__setattr__(self, 'maximum_mass_flux_residuals_kg_m2_s', mass)
    object.__setattr__(self, 'maximum_normal_momentum_residuals_Pa', momentum)
    object.__setattr__(self, 'maximum_energy_flux_residuals_W_m2', energy)
    object.__setattr__(self, 'response_mode_ids', response_modes)
    object.__setattr__(self, 'fresh_audit_verified', fresh_audits)
    object.__setattr__(self, 'strict_residual_descent_verified', strict_descent)
    object.__setattr__(self, 'independent_residual_audit_verified', independent_audits)
    object.__setattr__(self, 'refinement_tolerance', tolerance)
    object.__setattr__(self, 'message', str(self.message))
    object.__setattr__(self, 'operator_id', str(self.operator_id))
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      in (
        MocReflectedDomainGlobalFrontierFreshResolveResidualRefinementStatus
        .CONVERGED_LOCAL_REFINEMENT,
        MocReflectedDomainGlobalFrontierFreshResolveResidualRefinementStatus
        .CONVERGED_CROSS_CASE_REFINEMENT,
      )
      and self.local_refinement_verified
      and self.refinement_convergence_verified
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': self.operator_id,
      'status': self.status.value,
      'converged': self.converged,
      'case_ids': self.case_ids,
      'resolution_sample_counts': self.resolution_sample_counts,
      'source_closure_fingerprints': self.source_closure_fingerprints,
      'candidate_closure_fingerprints': self.candidate_closure_fingerprints,
      'initial_residual_norms': self.initial_residual_norms,
      'final_residual_norms': self.final_residual_norms,
      'maximum_mass_flux_residuals_kg_m2_s': (
        self.maximum_mass_flux_residuals_kg_m2_s
      ),
      'maximum_normal_momentum_residuals_Pa': (
        self.maximum_normal_momentum_residuals_Pa
      ),
      'maximum_energy_flux_residuals_W_m2': (
        self.maximum_energy_flux_residuals_W_m2
      ),
      'response_mode_ids': self.response_mode_ids,
      'fresh_audit_verified': self.fresh_audit_verified,
      'strict_residual_descent_verified': self.strict_residual_descent_verified,
      'independent_residual_audit_verified': (
        self.independent_residual_audit_verified
      ),
      'case_audits_verified': self.case_audits_verified,
      'case_identity_verified': self.case_identity_verified,
      'candidate_identity_verified': self.candidate_identity_verified,
      'resolution_order_verified': self.resolution_order_verified,
      'response_mode_identity_verified': self.response_mode_identity_verified,
      'residuals_finite': self.residuals_finite,
      'residuals_nonincreasing_verified': self.residuals_nonincreasing_verified,
      'residual_reduction_verified': self.residual_reduction_verified,
      'cross_case_verified': self.cross_case_verified,
      'local_refinement_verified': self.local_refinement_verified,
      'refinement_convergence_verified': self.refinement_convergence_verified,
      'fidelity_flags_verified': self.fidelity_flags_verified,
      'canonical_free_boundary_verified': False,
      'canonical_euler_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'refinement_tolerance': self.refinement_tolerance,
      'cases': tuple(case.result.as_report() for case in self.cases),
      'message': self.message,
    }
####


def _source_fingerprint(
  case: MocReflectedDomainGlobalFrontierFreshResolveResidualRefinementCase,
) -> str | None:
  value = case.result.fresh_resolve.source_closure_fingerprint
  return value if value else None
####


def _candidate_fingerprint(
  case: MocReflectedDomainGlobalFrontierFreshResolveResidualRefinementCase,
) -> str | None:
  value = case.result.fresh_resolve.candidate_closure_fingerprint
  return value if value else None
####


def _residual_metrics(
  case: MocReflectedDomainGlobalFrontierFreshResolveResidualRefinementCase,
) -> tuple[float, float, float] | None:
  result = case.result
  values = (
    result.maximum_mass_flux_residual_kg_m2_s,
    result.maximum_normal_momentum_residual_Pa,
    result.maximum_energy_flux_residual_W_m2,
  )
  if any(value is None for value in values):
    return None
  ####
  resolved = tuple(float(value) for value in values if value is not None)
  if len(resolved) != 3 or any(not isfinite(value) or value < 0.0 for value in resolved):
    return None
  ####
  return resolved  # type: ignore[return-value]
####


def _response_mode_id(
  case: MocReflectedDomainGlobalFrontierFreshResolveResidualRefinementCase,
) -> str | None:
  result = case.result
  two_sided = result.two_sided_result
  residual = None if two_sided is None else two_sided.conservative_residual_result
  if two_sided is None or residual is None or residual.request is None:
    return None
  ####
  request = two_sided.request
  response = residual.final_response
  if request is None or response is None:
    return None
  ####
  correction = residual.request
  mode = (
    response.response_source,
    response.law_id,
    request.branch.value,
    round(request.downstream_probe_fraction, 12),
    request.anchor_endpoint_samples,
    correction.require_strict_descent,
    correction.use_directional_residual_correction,
  )
  return repr(mode)
####


def _grouped_indices(
  cases: Sequence[
    MocReflectedDomainGlobalFrontierFreshResolveResidualRefinementCase
  ],
) -> dict[str, list[int]]:
  grouped: dict[str, list[int]] = {}
  for index, case in enumerate(cases):
    grouped.setdefault(case.case_id, []).append(index)
  return grouped
####


def _nonincreasing(
  values: tuple[float | None, ...],
  indices: Sequence[int],
  tolerance: float,
) -> bool:
  resolved = tuple(values[index] for index in indices)
  if any(value is None for value in resolved):
    return False
  ####
  numeric = tuple(float(value) for value in resolved if value is not None)
  return all(
    right <= left * (1.0 + tolerance)
    for left, right in zip(numeric, numeric[1:])
  )
####


def _strict_reduction(
  values: tuple[float | None, ...],
  indices: Sequence[int],
) -> bool:
  resolved = tuple(values[index] for index in indices)
  if len(resolved) < 2 or any(value is None for value in resolved):
    return False
  ####
  numeric = tuple(float(value) for value in resolved if value is not None)
  return numeric[-1] < numeric[0]
####


def _failure(
  status: MocReflectedDomainGlobalFrontierFreshResolveResidualRefinementStatus,
  message: str,
  *,
  cases: Sequence[
    MocReflectedDomainGlobalFrontierFreshResolveResidualRefinementCase
  ] = (),
  refinement_tolerance: float = 1.0e-8,
  **kwargs: object,
) -> MocReflectedDomainGlobalFrontierFreshResolveResidualRefinementMeasurement:
  case_values = tuple(cases)
  result_values = tuple(case.result for case in case_values)
  return MocReflectedDomainGlobalFrontierFreshResolveResidualRefinementMeasurement(
    status=status,
    cases=case_values,
    case_ids=tuple(case.case_id for case in case_values),
    resolution_sample_counts=tuple(
      case.resolution_sample_count for case in case_values
    ),
    source_closure_fingerprints=tuple(
      _source_fingerprint(case) for case in case_values
    ),
    candidate_closure_fingerprints=tuple(
      _candidate_fingerprint(case) for case in case_values
    ),
    initial_residual_norms=tuple(
      result.initial_residual_norm for result in result_values
    ),
    final_residual_norms=tuple(
      result.final_residual_norm for result in result_values
    ),
    maximum_mass_flux_residuals_kg_m2_s=tuple(
      result.maximum_mass_flux_residual_kg_m2_s for result in result_values
    ),
    maximum_normal_momentum_residuals_Pa=tuple(
      result.maximum_normal_momentum_residual_Pa for result in result_values
    ),
    maximum_energy_flux_residuals_W_m2=tuple(
      result.maximum_energy_flux_residual_W_m2 for result in result_values
    ),
    response_mode_ids=tuple(_response_mode_id(case) for case in case_values),
    fresh_audit_verified=tuple(
      result.fresh_audit_verified for result in result_values
    ),
    strict_residual_descent_verified=tuple(
      result.strict_residual_descent_verified for result in result_values
    ),
    independent_residual_audit_verified=tuple(
      result.independent_residual_audit_verified for result in result_values
    ),
    case_audits_verified=bool(kwargs.pop('case_audits_verified', False)),
    case_identity_verified=bool(kwargs.pop('case_identity_verified', False)),
    candidate_identity_verified=bool(
      kwargs.pop('candidate_identity_verified', False)
    ),
    resolution_order_verified=bool(
      kwargs.pop('resolution_order_verified', False)
    ),
    response_mode_identity_verified=bool(
      kwargs.pop('response_mode_identity_verified', False)
    ),
    residuals_finite=bool(kwargs.pop('residuals_finite', False)),
    residuals_nonincreasing_verified=bool(
      kwargs.pop('residuals_nonincreasing_verified', False)
    ),
    residual_reduction_verified=bool(
      kwargs.pop('residual_reduction_verified', False)
    ),
    cross_case_verified=bool(kwargs.pop('cross_case_verified', False)),
    local_refinement_verified=bool(
      kwargs.pop('local_refinement_verified', False)
    ),
    refinement_convergence_verified=bool(
      kwargs.pop('refinement_convergence_verified', False)
    ),
    fidelity_flags_verified=bool(kwargs.pop('fidelity_flags_verified', False)),
    canonical_free_boundary_verified=False,
    canonical_euler_verified=False,
    chain_promotion_blocked=bool(kwargs.pop('chain_promotion_blocked', True)),
    production_claim_allowed=bool(kwargs.pop('production_claim_allowed', False)),
    refinement_tolerance=refinement_tolerance,
    message=message,
  )
####


def measure_moc_global_frontier_fresh_resolve_residual_refinement(
  cases: Sequence[
    MocReflectedDomainGlobalFrontierFreshResolveResidualRefinementCase
  ],
  *,
  refinement_tolerance: float = 1.0e-8,
) -> MocReflectedDomainGlobalFrontierFreshResolveResidualRefinementMeasurement:
  """Independently audit fresh residual results by case and resolution."""

  try:
    tolerance = float(refinement_tolerance)
  except (TypeError, ValueError):
    return _failure(
      MocReflectedDomainGlobalFrontierFreshResolveResidualRefinementStatus
      .INVALID_INPUT,
      'refinement_tolerance must be numeric',
    )
  ####
  if not isfinite(tolerance) or tolerance <= 0.0:
    return _failure(
      MocReflectedDomainGlobalFrontierFreshResolveResidualRefinementStatus
      .INVALID_INPUT,
      'refinement_tolerance must be finite and positive',
      refinement_tolerance=tolerance,
    )
  ####
  case_values = tuple(cases)
  if len(case_values) < 2:
    return _failure(
      MocReflectedDomainGlobalFrontierFreshResolveResidualRefinementStatus
      .INVALID_INPUT,
      'fresh-frontier residual refinement requires at least two cases',
      refinement_tolerance=tolerance,
    )
  ####
  if any(
    not isinstance(
      case,
      MocReflectedDomainGlobalFrontierFreshResolveResidualRefinementCase,
    )
    for case in case_values
  ):
    return _failure(
      MocReflectedDomainGlobalFrontierFreshResolveResidualRefinementStatus
      .INVALID_INPUT,
      'cases must contain typed fresh-frontier residual refinement cases',
      refinement_tolerance=tolerance,
    )
  ####
  grouped = _grouped_indices(case_values)
  source_fingerprints = tuple(_source_fingerprint(case) for case in case_values)
  candidate_fingerprints = tuple(
    _candidate_fingerprint(case) for case in case_values
  )
  metrics = tuple(_residual_metrics(case) for case in case_values)
  mass = tuple(None if metric is None else metric[0] for metric in metrics)
  momentum = tuple(None if metric is None else metric[1] for metric in metrics)
  energy = tuple(None if metric is None else metric[2] for metric in metrics)
  response_modes = tuple(_response_mode_id(case) for case in case_values)
  fresh_audits = tuple(case.result.fresh_audit_verified for case in case_values)
  ####
  case_audits_verified = bool(
    all(
      case.result.converged_research_residual
      and case.result.fresh_audit_verified
      and case.result.residual_solver_invoked
      and case.result.residual_vector_verified
      and case.result.strict_residual_descent_verified
      and case.result.independent_residual_audit_verified
      for case in case_values
    )
  )
  case_identity_verified = bool(
    all(
      case.result.fresh_resolve.candidate_closure is not None
      and case.result.fresh_resolve.candidate_is_fresh
      and case.result.fresh_resolve.source_lineage_verified
      and case.result.fresh_resolve.source_closure_fingerprint
      for case in case_values
    )
  )
  candidate_identity_verified = bool(
    case_identity_verified
    and all(candidate_fingerprints)
    and all(
      case.result.two_sided_result is not None
      and case.result.two_sided_result.request is not None
      and case.result.two_sided_result.request.closure
      is case.result.fresh_resolve.candidate_closure
      for case in case_values
    )
  )
  resolution_order_verified = bool(
    all(
      all(
        case_values[right].resolution_sample_count
        > case_values[left].resolution_sample_count
        for left, right in zip(indices, indices[1:])
      )
      for indices in grouped.values()
    )
  )
  response_mode_identity_verified = bool(
    all(mode is not None for mode in response_modes)
    and all(
      len({response_modes[index] for index in indices}) == 1
      for indices in grouped.values()
    )
  )
  residuals_finite = bool(
    all(metric is not None for metric in metrics)
    and all(
      isfinite(value) and value >= 0.0
      for metric in metrics
      if metric is not None
      for value in metric
    )
  )
  residuals_nonincreasing_verified = bool(
    residuals_finite
    and all(
      all(
        _nonincreasing(channel, indices, tolerance)
        for channel in (mass, momentum, energy)
      )
      for indices in grouped.values()
    )
  )
  residual_reduction_verified = bool(
    residuals_finite
    and all(
      all(
        _strict_reduction(channel, indices)
        for channel in (mass, momentum, energy)
      )
      for indices in grouped.values()
    )
  )
  fidelity_flags_verified = bool(
    all(case.result.fidelity_isolation_verified for case in case_values)
    and all(case.result.chain_promotion_blocked for case in case_values)
    and all(not case.result.production_claim_allowed for case in case_values)
    and all(
      not case.result.fresh_resolve.global_coupling_verified
      and not case.result.fresh_resolve.downstream_boundary_closure_verified
      for case in case_values
    )
  )
  local_refinement_verified = bool(
    case_audits_verified
    and case_identity_verified
    and candidate_identity_verified
    and resolution_order_verified
    and response_mode_identity_verified
    and residuals_finite
    and residuals_nonincreasing_verified
    and residual_reduction_verified
    and fidelity_flags_verified
  )
  refinement_convergence_verified = bool(
    local_refinement_verified
    and all(len(indices) >= 3 for indices in grouped.values())
  )
  group_source_fingerprints = tuple(
    tuple(source_fingerprints[index] for index in indices)
    for indices in grouped.values()
  )
  cross_case_verified = bool(
    refinement_convergence_verified
    and len(grouped) >= 2
    and len(set(group_source_fingerprints)) == len(group_source_fingerprints)
  )
  ####
  status_type = (
    MocReflectedDomainGlobalFrontierFreshResolveResidualRefinementStatus
  )
  if not all(fresh_audits):
    status = status_type.FRESH_AUDIT_FAILURE
    message = 'one or more fresh frontier cases failed their independent target audit'
  elif not case_identity_verified or not candidate_identity_verified:
    status = status_type.LINEAGE_FAILURE
    message = (
      'fresh frontier residual cases did not retain unique source/candidate '
      'identity through the exact downstream handoff'
    )
  elif not case_audits_verified:
    status = status_type.CASE_FAILURE
    message = (
      'one or more fresh frontier residual cases failed the strict independent '
      'descent or residual audit gate'
    )
  elif not resolution_order_verified:
    status = status_type.RESOLUTION_ORDER_FAILURE
    message = 'fresh frontier residual cases are not strictly resolution ordered'
  elif not response_mode_identity_verified:
    status = status_type.RESPONSE_MODE_FAILURE
    message = 'fresh frontier residual cases mix response modes within a case ladder'
  elif not (residuals_finite and residuals_nonincreasing_verified and residual_reduction_verified):
    status = status_type.RESIDUAL_FAILURE
    message = (
      'fresh frontier signed mass, momentum, and energy channels did not '
      'satisfy the declared refinement trend'
    )
  elif not fidelity_flags_verified:
    status = status_type.FLAG_FAILURE
    message = 'fresh frontier residual refinement weakened its non-promotion flags'
  elif cross_case_verified:
    status = status_type.CONVERGED_CROSS_CASE_REFINEMENT
    message = (
      'independent fresh-frontier residual audits verified locally refining '
      'signed conservative channels across distinct cases; canonical closure '
      'and production gates remain open'
    )
  else:
    status = status_type.CONVERGED_LOCAL_REFINEMENT
    message = (
      'independent fresh-frontier residual audits verified a local resolution '
      'ladder; cross-case, canonical closure, and production gates remain open'
    )
  ####
  return _failure(
    status,
    message,
    cases=case_values,
    refinement_tolerance=tolerance,
    case_audits_verified=case_audits_verified,
    case_identity_verified=case_identity_verified,
    candidate_identity_verified=candidate_identity_verified,
    resolution_order_verified=resolution_order_verified,
    response_mode_identity_verified=response_mode_identity_verified,
    residuals_finite=residuals_finite,
    residuals_nonincreasing_verified=residuals_nonincreasing_verified,
    residual_reduction_verified=residual_reduction_verified,
    cross_case_verified=cross_case_verified,
    local_refinement_verified=local_refinement_verified,
    refinement_convergence_verified=refinement_convergence_verified,
    fidelity_flags_verified=fidelity_flags_verified,
  )
####
