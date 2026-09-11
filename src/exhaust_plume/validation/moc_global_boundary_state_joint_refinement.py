"""Cross-case refinement audit for the global boundary-state joint consumer.

The joint consumer now proves one dimensioned, solver-owned response update.
This module checks that evidence on fresh closure identities across an ordered
resolution ladder and distinct cases.  It never treats a locally converged
joint result as canonical global coupling or as a production shock-cell
source.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Any, Sequence

from exhaust_plume.models.moc.global_physical_closure import (
  moc_reflected_domain_global_physical_closure_fingerprint,
)
from exhaust_plume.validation.moc_global_boundary_state_joint_solve import (
  MocReflectedDomainGlobalBoundaryStateJointSolveResult,
  MocReflectedDomainGlobalBoundaryStateJointSolveStatus,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_BOUNDARY_STATE_JOINT_REFINEMENT_OPERATOR_ID',
  'MocReflectedDomainGlobalBoundaryStateJointRefinementCase',
  'MocReflectedDomainGlobalBoundaryStateJointRefinementStatus',
  'MocReflectedDomainGlobalBoundaryStateJointRefinementMeasurement',
  'measure_moc_global_boundary_state_joint_refinement',
)


MOC_REFLECTED_DOMAIN_GLOBAL_BOUNDARY_STATE_JOINT_REFINEMENT_OPERATOR_ID = (
  'op.moc.reflected-domain.global-boundary-state-joint-refinement-v1'
)


class MocReflectedDomainGlobalBoundaryStateJointRefinementStatus(str, Enum):
  """Typed outcomes of the joint-consumer refinement audit."""

  CONVERGED_LOCAL_REFINEMENT = (
    'converged-global-boundary-state-joint-local-refinement'
  )
  CONVERGED_CROSS_CASE_REFINEMENT = (
    'converged-global-boundary-state-joint-cross-case-refinement'
  )
  INVALID_INPUT = 'invalid_input'
  CASE_FAILURE = 'global-boundary-state-joint-refinement-case-failure'
  CLOSURE_IDENTITY_FAILURE = (
    'global-boundary-state-joint-refinement-closure-identity-failure'
  )
  RESOLUTION_ORDER_FAILURE = (
    'global-boundary-state-joint-refinement-resolution-order-failure'
  )
  CHANNEL_FAILURE = (
    'global-boundary-state-joint-refinement-dimensioned-channel-failure'
  )
  RESIDUAL_FAILURE = (
    'global-boundary-state-joint-refinement-residual-failure'
  )
  FLAG_FAILURE = 'global-boundary-state-joint-refinement-flag-failure'
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalBoundaryStateJointRefinementCase:
  """One fresh joint-consumer result at a declared resolution."""

  case_id: str
  resolution_sample_count: int
  result: MocReflectedDomainGlobalBoundaryStateJointSolveResult

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
      MocReflectedDomainGlobalBoundaryStateJointSolveResult,
    ):
      raise TypeError(
        'result must be a '
        'MocReflectedDomainGlobalBoundaryStateJointSolveResult'
      )
    ####
    object.__setattr__(self, 'case_id', case_id)
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalBoundaryStateJointRefinementMeasurement:
  """Independent refinement evidence below the production ceiling."""

  status: MocReflectedDomainGlobalBoundaryStateJointRefinementStatus
  cases: tuple[MocReflectedDomainGlobalBoundaryStateJointRefinementCase, ...]
  case_ids: tuple[str, ...]
  resolution_sample_counts: tuple[int, ...]
  source_closure_fingerprints: tuple[str | None, ...]
  baseline_residual_norms: tuple[float, ...]
  refreshed_residual_norms: tuple[float, ...]
  baseline_dimensioned_channel_maxima: tuple[tuple[float, ...], ...]
  refreshed_dimensioned_channel_maxima: tuple[tuple[float, ...], ...]
  case_audits_verified: bool
  case_identity_verified: bool
  closure_identity_verified: bool
  resolution_order_verified: bool
  dimensioned_channels_verified: bool
  dimensioned_channel_descent_verified: bool
  residual_descent_verified: bool
  cross_case_verified: bool
  local_refinement_verified: bool
  refinement_convergence_verified: bool
  canonical_free_boundary_verified: bool
  canonical_euler_verified: bool
  downstream_boundary_closure_verified: bool
  chain_promotion_blocked: bool
  production_claim_allowed: bool
  fidelity_flags_verified: bool
  refinement_tolerance: float = 1.0e-10
  message: str = ''
  operator_id: str = (
    MOC_REFLECTED_DOMAIN_GLOBAL_BOUNDARY_STATE_JOINT_REFINEMENT_OPERATOR_ID
  )

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalBoundaryStateJointRefinementStatus,
    ):
      raise TypeError('status must be a typed joint-refinement status')
    ####
    cases = tuple(self.cases)
    if any(
      not isinstance(
        case,
        MocReflectedDomainGlobalBoundaryStateJointRefinementCase,
      )
      for case in cases
    ):
      raise TypeError('cases must contain typed joint-refinement cases')
    ####
    case_ids = tuple(str(value) for value in self.case_ids)
    resolutions = tuple(self.resolution_sample_counts)
    fingerprints = tuple(self.source_closure_fingerprints)
    baseline = tuple(float(value) for value in self.baseline_residual_norms)
    refreshed = tuple(float(value) for value in self.refreshed_residual_norms)
    baseline_channels = tuple(
      tuple(float(value) for value in values)
      for values in self.baseline_dimensioned_channel_maxima
    )
    refreshed_channels = tuple(
      tuple(float(value) for value in values)
      for values in self.refreshed_dimensioned_channel_maxima
    )
    if not (
      len(cases)
      == len(case_ids)
      == len(resolutions)
      == len(fingerprints)
      == len(baseline)
      == len(refreshed)
      == len(baseline_channels)
      == len(refreshed_channels)
    ):
      raise ValueError('refinement summaries must match the case count')
    ####
    if any(not value for value in case_ids):
      raise ValueError('case_ids must be non-empty')
    ####
    if any(
      isinstance(value, bool) or not isinstance(value, int) or value < 0
      for value in resolutions
    ):
      raise ValueError('resolution sample counts must be nonnegative integers')
    ####
    for name, values in (
      ('baseline_residual_norms', baseline),
      ('refreshed_residual_norms', refreshed),
    ):
      if any(not isfinite(value) or value < 0.0 for value in values):
        raise ValueError(f'{name} must contain finite nonnegative values')
      ####
    ####
    for name, values in (
      ('baseline_dimensioned_channel_maxima', baseline_channels),
      ('refreshed_dimensioned_channel_maxima', refreshed_channels),
    ):
      if any(
        len(channel_values) != 3
        or any(not isfinite(value) or value < 0.0 for value in channel_values)
        for channel_values in values
      ):
        raise ValueError(f'{name} must contain three finite channels per case')
      ####
    ####
    for name in (
      'case_audits_verified',
      'case_identity_verified',
      'closure_identity_verified',
      'resolution_order_verified',
      'dimensioned_channels_verified',
      'dimensioned_channel_descent_verified',
      'residual_descent_verified',
      'cross_case_verified',
      'local_refinement_verified',
      'refinement_convergence_verified',
      'canonical_free_boundary_verified',
      'canonical_euler_verified',
      'downstream_boundary_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
      'fidelity_flags_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if (
      self.canonical_free_boundary_verified
      or self.canonical_euler_verified
      or self.downstream_boundary_closure_verified
    ):
      raise ValueError('joint refinement cannot claim canonical closure')
    ####
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError('joint refinement must remain promotion-blocked')
    ####
    tolerance = float(self.refinement_tolerance)
    if not isfinite(tolerance) or tolerance <= 0.0:
      raise ValueError('refinement_tolerance must be finite and positive')
    ####
    if self.status in (
      MocReflectedDomainGlobalBoundaryStateJointRefinementStatus
      .CONVERGED_LOCAL_REFINEMENT,
      MocReflectedDomainGlobalBoundaryStateJointRefinementStatus
      .CONVERGED_CROSS_CASE_REFINEMENT,
    ) and not (
      self.local_refinement_verified
      and self.refinement_convergence_verified
    ):
      raise ValueError('converged refinement must pass every local refinement gate')
    ####
    object.__setattr__(self, 'cases', cases)
    object.__setattr__(self, 'case_ids', case_ids)
    object.__setattr__(self, 'resolution_sample_counts', resolutions)
    object.__setattr__(self, 'source_closure_fingerprints', fingerprints)
    object.__setattr__(self, 'baseline_residual_norms', baseline)
    object.__setattr__(self, 'refreshed_residual_norms', refreshed)
    object.__setattr__(self, 'baseline_dimensioned_channel_maxima', baseline_channels)
    object.__setattr__(self, 'refreshed_dimensioned_channel_maxima', refreshed_channels)
    object.__setattr__(self, 'refinement_tolerance', tolerance)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status in (
        MocReflectedDomainGlobalBoundaryStateJointRefinementStatus
        .CONVERGED_LOCAL_REFINEMENT,
        MocReflectedDomainGlobalBoundaryStateJointRefinementStatus
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
      'baseline_residual_norms': self.baseline_residual_norms,
      'refreshed_residual_norms': self.refreshed_residual_norms,
      'baseline_dimensioned_channel_maxima': (
        self.baseline_dimensioned_channel_maxima
      ),
      'refreshed_dimensioned_channel_maxima': (
        self.refreshed_dimensioned_channel_maxima
      ),
      'case_audits_verified': self.case_audits_verified,
      'case_identity_verified': self.case_identity_verified,
      'closure_identity_verified': self.closure_identity_verified,
      'resolution_order_verified': self.resolution_order_verified,
      'dimensioned_channels_verified': self.dimensioned_channels_verified,
      'dimensioned_channel_descent_verified': (
        self.dimensioned_channel_descent_verified
      ),
      'residual_descent_verified': self.residual_descent_verified,
      'cross_case_verified': self.cross_case_verified,
      'local_refinement_verified': self.local_refinement_verified,
      'refinement_convergence_verified': self.refinement_convergence_verified,
      'canonical_free_boundary_verified': False,
      'canonical_euler_verified': False,
      'downstream_boundary_closure_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'fidelity_flags_verified': self.fidelity_flags_verified,
      'refinement_tolerance': self.refinement_tolerance,
      'cases': tuple(case.result.as_report() for case in self.cases),
      'message': self.message,
    }
  ####
####


def _failure(
  status: MocReflectedDomainGlobalBoundaryStateJointRefinementStatus,
  message: str,
  *,
  cases: Sequence[MocReflectedDomainGlobalBoundaryStateJointRefinementCase] = (),
  refinement_tolerance: float = 1.0e-10,
  **kwargs: object,
) -> MocReflectedDomainGlobalBoundaryStateJointRefinementMeasurement:
  case_values = tuple(cases)
  return MocReflectedDomainGlobalBoundaryStateJointRefinementMeasurement(
    status=status,
    cases=case_values,
    case_ids=tuple(case.case_id for case in case_values),
    resolution_sample_counts=tuple(
      case.resolution_sample_count for case in case_values
    ),
    source_closure_fingerprints=tuple(
      (
        None
        if case.result.source_closure is None
        else moc_reflected_domain_global_physical_closure_fingerprint(
          case.result.source_closure
        )
      )
      for case in case_values
    ),
    baseline_residual_norms=tuple(
      float(value) for value in kwargs.pop('baseline', ())
    ),
    refreshed_residual_norms=tuple(
      float(value) for value in kwargs.pop('refreshed', ())
    ),
    baseline_dimensioned_channel_maxima=tuple(
      tuple(float(value) for value in values)
      for values in kwargs.pop('baseline_channels', ())
    ),
    refreshed_dimensioned_channel_maxima=tuple(
      tuple(float(value) for value in values)
      for values in kwargs.pop('refreshed_channels', ())
    ),
    case_audits_verified=bool(kwargs.pop('case_audits_verified', False)),
    case_identity_verified=bool(kwargs.pop('case_identity_verified', False)),
    closure_identity_verified=bool(
      kwargs.pop('closure_identity_verified', False)
    ),
    resolution_order_verified=bool(kwargs.pop('resolution_order_verified', False)),
    dimensioned_channels_verified=bool(
      kwargs.pop('dimensioned_channels_verified', False)
    ),
    dimensioned_channel_descent_verified=bool(
      kwargs.pop('dimensioned_channel_descent_verified', False)
    ),
    residual_descent_verified=bool(
      kwargs.pop('residual_descent_verified', False)
    ),
    cross_case_verified=bool(kwargs.pop('cross_case_verified', False)),
    local_refinement_verified=bool(kwargs.pop('local_refinement_verified', False)),
    refinement_convergence_verified=bool(
      kwargs.pop('refinement_convergence_verified', False)
    ),
    canonical_free_boundary_verified=False,
    canonical_euler_verified=False,
    downstream_boundary_closure_verified=False,
    chain_promotion_blocked=bool(kwargs.pop('chain_promotion_blocked', True)),
    production_claim_allowed=bool(kwargs.pop('production_claim_allowed', False)),
    fidelity_flags_verified=bool(kwargs.pop('fidelity_flags_verified', False)),
    refinement_tolerance=refinement_tolerance,
    message=message,
  )
####


def _group_indices(case_ids: Sequence[str]) -> dict[str, list[int]]:
  grouped: dict[str, list[int]] = {}
  for index, case_id in enumerate(case_ids):
    grouped.setdefault(case_id, []).append(index)
  ####
  return grouped
####


def measure_moc_global_boundary_state_joint_refinement(
  cases: Sequence[MocReflectedDomainGlobalBoundaryStateJointRefinementCase],
  *,
  refinement_tolerance: float = 1.0e-10,
) -> MocReflectedDomainGlobalBoundaryStateJointRefinementMeasurement:
  """Audit fresh joint-consumer results across cases and resolutions."""

  try:
    tolerance = float(refinement_tolerance)
  except (TypeError, ValueError):
    return _failure(
      MocReflectedDomainGlobalBoundaryStateJointRefinementStatus.INVALID_INPUT,
      'refinement_tolerance must be numeric',
    )
  ####
  if not isfinite(tolerance) or tolerance <= 0.0:
    return _failure(
      MocReflectedDomainGlobalBoundaryStateJointRefinementStatus.INVALID_INPUT,
      'refinement_tolerance must be finite and positive',
      refinement_tolerance=tolerance,
    )
  ####
  case_values = tuple(cases)
  if len(case_values) < 2:
    return _failure(
      MocReflectedDomainGlobalBoundaryStateJointRefinementStatus.INVALID_INPUT,
      'joint refinement requires at least two cases',
      refinement_tolerance=tolerance,
    )
  ####
  if any(
    not isinstance(
      case,
      MocReflectedDomainGlobalBoundaryStateJointRefinementCase,
    )
    for case in case_values
  ):
    return _failure(
      MocReflectedDomainGlobalBoundaryStateJointRefinementStatus.INVALID_INPUT,
      'cases must contain typed joint-refinement cases',
      refinement_tolerance=tolerance,
    )
  ####

  case_ids = tuple(case.case_id for case in case_values)
  grouped = _group_indices(case_ids)
  results = tuple(case.result for case in case_values)
  case_audits_verified = bool(
    all(
      result.status
      is MocReflectedDomainGlobalBoundaryStateJointSolveStatus
      .CONVERGED_RESEARCH_JOINT_STATE_UPDATE
      and result.converged_research_joint_update
      and result.independent_residual_audit_verified
      for result in results
    )
  )
  case_identity_verified = bool(
    all(
      result.handoff_lineage_verified
      and result.global_consumer_invoked
      and result.state_solver_invoked
      and result.state_lineage_verified
      for result in results
    )
  )
  fingerprints = tuple(
    (
      None
      if result.source_closure is None
      else moc_reflected_domain_global_physical_closure_fingerprint(
        result.source_closure
      )
    )
    for result in results
  )
  closure_identity_verified = bool(
    case_identity_verified
    and all(fingerprint is not None for fingerprint in fingerprints)
    and all(
      len({fingerprints[index] for index in indices}) == len(indices)
      for indices in grouped.values()
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
  baseline = tuple(
    result.baseline_residual_norm
    for result in results
    if result.baseline_residual_norm is not None
  )
  refreshed = tuple(
    result.refreshed_residual_norm
    for result in results
    if result.refreshed_residual_norm is not None
  )
  baseline_channels = tuple(
    result.baseline_dimensioned_channel_maxima
    for result in results
  )
  refreshed_channels = tuple(
    result.refreshed_dimensioned_channel_maxima
    for result in results
  )
  dimensioned_channels_verified = bool(
    all(result.dimensioned_channels_verified for result in results)
    and all(len(values) == 3 for values in baseline_channels)
    and all(len(values) == 3 for values in refreshed_channels)
  )
  dimensioned_channel_descent_verified = bool(
    dimensioned_channels_verified
    and all(result.dimensioned_channel_descent_verified for result in results)
  )
  residuals_complete = bool(
    len(baseline) == len(results)
    and len(refreshed) == len(results)
  )
  residual_descent_verified = bool(
    residuals_complete
    and all(result.residual_descent_verified for result in results)
    and all(
      after < before
      for before, after in zip(baseline, refreshed, strict=True)
    )
  )
  fidelity_flags_verified = bool(
    all(result.global_coupling_verified is False for result in results)
    and all(result.downstream_boundary_closure_verified is False for result in results)
    and all(result.chain_promotion_blocked for result in results)
    and all(result.production_claim_allowed is False for result in results)
  )
  cross_case_verified = bool(
    len(grouped) >= 2
    and all(len(indices) >= 2 for indices in grouped.values())
    and len(
      {
        tuple(fingerprints[index] for index in indices)
        for indices in grouped.values()
      }
    )
    == len(grouped)
  )
  local_refinement_verified = bool(
    case_audits_verified
    and case_identity_verified
    and closure_identity_verified
    and resolution_order_verified
    and dimensioned_channels_verified
    and dimensioned_channel_descent_verified
    and residual_descent_verified
    and fidelity_flags_verified
  )
  refinement_convergence_verified = bool(
    local_refinement_verified
    and all(len(indices) >= 2 for indices in grouped.values())
  )

  if not case_audits_verified or not case_identity_verified:
    status = MocReflectedDomainGlobalBoundaryStateJointRefinementStatus.CASE_FAILURE
    message = 'one or more joint-consumer cases failed its retained audit or lineage gates'
  elif not closure_identity_verified:
    status = (
      MocReflectedDomainGlobalBoundaryStateJointRefinementStatus
      .CLOSURE_IDENTITY_FAILURE
    )
    message = 'joint-consumer closure fingerprints are missing or reused within a case ladder'
  elif not resolution_order_verified:
    status = (
      MocReflectedDomainGlobalBoundaryStateJointRefinementStatus
      .RESOLUTION_ORDER_FAILURE
    )
    message = 'joint-consumer cases are not strictly resolution ordered'
  elif not dimensioned_channel_descent_verified:
    status = (
      MocReflectedDomainGlobalBoundaryStateJointRefinementStatus
      .CHANNEL_FAILURE
    )
    message = 'one or more joint-consumer cases failed the dimensioned channel gate'
  elif not residual_descent_verified:
    status = MocReflectedDomainGlobalBoundaryStateJointRefinementStatus.RESIDUAL_FAILURE
    message = 'joint-consumer residual descent was not independently retained on every case'
  elif not fidelity_flags_verified:
    status = MocReflectedDomainGlobalBoundaryStateJointRefinementStatus.FLAG_FAILURE
    message = 'joint-consumer refinement weakened its research-only flags'
  elif cross_case_verified:
    status = (
      MocReflectedDomainGlobalBoundaryStateJointRefinementStatus
      .CONVERGED_CROSS_CASE_REFINEMENT
    )
    message = (
      'fresh joint-consumer results passed dimensioned channel, closure-lineage, '
      'and strict-descent checks across distinct cases and ordered resolutions; '
      'canonical coupling and production gates remain open'
    )
  else:
    status = (
      MocReflectedDomainGlobalBoundaryStateJointRefinementStatus
      .CONVERGED_LOCAL_REFINEMENT
    )
    message = (
      'fresh joint-consumer results passed local dimensioned-channel and '
      'strict-descent checks; a disjoint cross-case ladder remains incomplete'
    )
  ####

  return _failure(
    status,
    message,
    cases=case_values,
    baseline=baseline,
    refreshed=refreshed,
    baseline_channels=baseline_channels,
    refreshed_channels=refreshed_channels,
    case_audits_verified=case_audits_verified,
    case_identity_verified=case_identity_verified,
    closure_identity_verified=closure_identity_verified,
    resolution_order_verified=resolution_order_verified,
    dimensioned_channels_verified=dimensioned_channels_verified,
    dimensioned_channel_descent_verified=dimensioned_channel_descent_verified,
    residual_descent_verified=residual_descent_verified,
    cross_case_verified=cross_case_verified,
    local_refinement_verified=local_refinement_verified,
    refinement_convergence_verified=refinement_convergence_verified,
    fidelity_flags_verified=fidelity_flags_verified,
    refinement_tolerance=tolerance,
  )
####
