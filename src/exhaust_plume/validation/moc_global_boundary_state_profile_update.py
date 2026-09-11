"""Bounded global compression-profile response for the reflected-state lane.

The boundary-state handoff now has a real update direction.  This module
perturbs only the explicit, solver-owned compression-envelope shape parameter,
re-solves the complete global physical closure for every candidate, and then
remeasures the conservative moving-interface response on the fresh closure.
It is therefore different from replaying a target frame or changing a
tolerance.  The parameter remains a research boundary condition, however;
the operator never claims canonical mixed-regime coupling or promotion.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from enum import Enum
from math import hypot, isfinite
from typing import Any

from exhaust_plume.models.moc.euler_two_sided_moving_interface import (
  MocEulerTwoSidedInterfaceResponse,
)
from exhaust_plume.models.moc.global_physical_closure import (
  MocReflectedDomainGlobalPhysicalClosureResult,
  moc_reflected_domain_global_physical_closure_fingerprint,
  solve_reflected_domain_global_physical_closure,
)
from exhaust_plume.models.moc.global_two_sided_moving_interface import (
  MocReflectedDomainGlobalTwoSidedMovingInterfaceRequest,
  MocReflectedDomainGlobalTwoSidedMovingInterfaceResult,
  MocReflectedDomainGlobalTwoSidedMovingInterfaceStatus,
  solve_reflected_domain_global_two_sided_moving_interface,
)
from exhaust_plume.util.aero.shock_validity import ShockBranch
from exhaust_plume.validation.moc_euler_two_sided_conservative_residual import (
  MocEulerTwoSidedConservativeResidualAudit,
)
from exhaust_plume.validation.moc_global_boundary_state_feedback import (
  MocReflectedDomainGlobalBoundaryStateFeedbackHandoff,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_BOUNDARY_STATE_PROFILE_UPDATE_OPERATOR_ID',
  'MOC_REFLECTED_DOMAIN_GLOBAL_BOUNDARY_STATE_PROFILE_REFINEMENT_OPERATOR_ID',
  'MOC_REFLECTED_DOMAIN_GLOBAL_BOUNDARY_STATE_PROFILE_CROSS_CASE_OPERATOR_ID',
  'MocReflectedDomainGlobalBoundaryStateProfileUpdateStatus',
  'MocReflectedDomainGlobalBoundaryStateProfileTrial',
  'MocReflectedDomainGlobalBoundaryStateProfileUpdateResult',
  'MocReflectedDomainGlobalBoundaryStateProfileRefinementStatus',
  'MocReflectedDomainGlobalBoundaryStateProfileCase',
  'MocReflectedDomainGlobalBoundaryStateProfileRefinementCase',
  'MocReflectedDomainGlobalBoundaryStateProfileRefinementMeasurement',
  'run_reflected_domain_global_boundary_state_profile_refinement',
  'run_reflected_domain_global_boundary_state_profile_update',
)


MOC_REFLECTED_DOMAIN_GLOBAL_BOUNDARY_STATE_PROFILE_UPDATE_OPERATOR_ID = (
  'op.moc.reflected-domain.global-boundary-state-profile-update-v1'
)
MOC_REFLECTED_DOMAIN_GLOBAL_BOUNDARY_STATE_PROFILE_REFINEMENT_OPERATOR_ID = (
  'op.moc.reflected-domain.global-boundary-state-profile-refinement-v1'
)
MOC_REFLECTED_DOMAIN_GLOBAL_BOUNDARY_STATE_PROFILE_CROSS_CASE_OPERATOR_ID = (
  'op.moc.reflected-domain.global-boundary-state-profile-cross-case-v1'
)


class MocReflectedDomainGlobalBoundaryStateProfileUpdateStatus(str, Enum):
  """Typed outcomes of a bounded compression-profile update."""

  CONVERGED_RESEARCH_PROFILE_UPDATE = (
    'converged-research-global-boundary-state-profile-update'
  )
  INVALID_INPUT = 'invalid_input'
  HANDOFF_LINEAGE_FAILURE = (
    'global-boundary-state-profile-update-handoff-lineage-failure'
  )
  PROFILE_SWEEP_FAILURE = (
    'global-boundary-state-profile-update-profile-sweep-failure'
  )
  CANDIDATE_CLOSURE_FAILURE = (
    'global-boundary-state-profile-update-candidate-closure-failure'
  )
  STATE_SOLVER_FAILURE = (
    'global-boundary-state-profile-update-state-solver-failure'
  )
  RESIDUAL_AUDIT_FAILURE = (
    'global-boundary-state-profile-update-residual-audit-failure'
  )
  RESIDUAL_DESCENT_FAILURE = (
    'global-boundary-state-profile-update-residual-descent-failure'
  )


class MocReflectedDomainGlobalBoundaryStateProfileRefinementStatus(str, Enum):
  """Typed outcomes of disjoint profile-update refinement evidence."""

  CONVERGED_RESEARCH_CROSS_CASE = (
    'converged-research-global-boundary-state-profile-cross-case'
  )
  INVALID_INPUT = 'invalid_input'
  CASE_BINDING_FAILURE = (
    'global-boundary-state-profile-refinement-case-binding-failure'
  )
  RESOLUTION_FAILURE = (
    'global-boundary-state-profile-refinement-resolution-failure'
  )
  UPDATE_FAILURE = (
    'global-boundary-state-profile-refinement-update-failure'
  )
  STABILITY_FAILURE = (
    'global-boundary-state-profile-refinement-stability-failure'
  )
  FIDELITY_FAILURE = (
    'global-boundary-state-profile-refinement-fidelity-failure'
  )


def _fingerprint(closure: MocReflectedDomainGlobalPhysicalClosureResult) -> str:
  return moc_reflected_domain_global_physical_closure_fingerprint(closure)


def _response(
  result: MocReflectedDomainGlobalTwoSidedMovingInterfaceResult | None,
) -> MocEulerTwoSidedInterfaceResponse | None:
  if result is None or result.conservative_residual_result is None:
    return None
  return result.conservative_residual_result.final_response


def _signed_channels_finite(response: MocEulerTwoSidedInterfaceResponse | None) -> bool:
  if response is None or not response.signed_residuals_available:
    return False
  channels = (
    response.signed_mass_flux_residuals_kg_m2_s,
    response.signed_normal_momentum_residuals_Pa,
    response.signed_energy_flux_residuals_W_m2,
  )
  assert all(channel is not None for channel in channels)
  return bool(
    all(channel for channel in channels)
    and all(isfinite(value) for channel in channels for value in channel)
  )


def _strict_descent(before: float, after: float, minimum_fraction: float) -> bool:
  if not isfinite(before) or not isfinite(after):
    return False
  if not isfinite(minimum_fraction) or minimum_fraction < 0.0:
    return False
  if before <= 0.0:
    return after < before
  return after < before * (1.0 - minimum_fraction)


def _geometry_changed(
  source: MocReflectedDomainGlobalPhysicalClosureResult,
  candidate: MocReflectedDomainGlobalPhysicalClosureResult,
  tolerance_m: float,
) -> bool:
  source_euler = source.global_euler
  candidate_euler = candidate.global_euler
  if source_euler is None or candidate_euler is None:
    return False
  source_points = tuple(source_euler.remeshed_shock_points_m)
  candidate_points = tuple(candidate_euler.remeshed_shock_points_m)
  if len(source_points) != len(candidate_points) or not source_points:
    return False
  return bool(
    max(
      hypot(first[0] - second[0], first[1] - second[1])
      for first, second in zip(source_points, candidate_points, strict=True)
    ) > tolerance_m
  )


def _candidate_skews(
  current: float,
  step: float,
  maximum_steps: int,
  explicit: Sequence[float] | None,
) -> tuple[float, ...]:
  values = tuple(float(value) for value in explicit) if explicit is not None else (
    max(-1.0, min(1.0, current + step * offset))
    for offset in range(-maximum_steps, maximum_steps + 1)
    if offset != 0
  )
  result: list[float] = []
  for value in values:
    if not isfinite(value) or abs(value) > 1.0:
      raise ValueError('candidate compression-envelope skews must be finite in [-1, 1]')
    if abs(value - current) <= 1.0e-12:
      continue
    if not any(abs(value - retained) <= 1.0e-12 for retained in result):
      result.append(value)
  return tuple(result)


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalBoundaryStateProfileTrial:
  """One fresh closure/state measurement for a candidate profile shape."""

  compression_envelope_skew: float
  candidate_closure: MocReflectedDomainGlobalPhysicalClosureResult | None
  state_request: MocReflectedDomainGlobalTwoSidedMovingInterfaceRequest | None
  state_result: MocReflectedDomainGlobalTwoSidedMovingInterfaceResult | None
  conservative_residual_audit: MocEulerTwoSidedConservativeResidualAudit | None
  residual_norm: float | None
  closure_fingerprint: str | None = None
  geometry_changed: bool = False
  closure_verified: bool = False
  state_solver_invoked: bool = False
  state_lineage_verified: bool = False
  signed_residuals_verified: bool = False
  moving_state_verified: bool = False
  independent_residual_audit_verified: bool = False
  residual_descent_verified: bool = False
  accepted: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    skew = float(self.compression_envelope_skew)
    if not isfinite(skew) or abs(skew) > 1.0:
      raise ValueError('compression_envelope_skew must be finite and within [-1, 1]')
    object.__setattr__(self, 'compression_envelope_skew', skew)
    for name, expected_type in (
      ('candidate_closure', MocReflectedDomainGlobalPhysicalClosureResult),
      (
        'state_request',
        MocReflectedDomainGlobalTwoSidedMovingInterfaceRequest,
      ),
      ('state_result', MocReflectedDomainGlobalTwoSidedMovingInterfaceResult),
      ('conservative_residual_audit', MocEulerTwoSidedConservativeResidualAudit),
    ):
      value = getattr(self, name)
      if value is not None and not isinstance(value, expected_type):
        raise TypeError(f'{name} must be typed or None')
    if self.residual_norm is not None:
      residual = float(self.residual_norm)
      if not isfinite(residual) or residual < 0.0:
        raise ValueError('residual_norm must be finite and nonnegative')
      object.__setattr__(self, 'residual_norm', residual)
    if self.closure_fingerprint is not None:
      if not isinstance(self.closure_fingerprint, str) or len(self.closure_fingerprint) != 64:
        raise ValueError('closure_fingerprint must be a SHA-256 digest when supplied')
    for name in (
      'geometry_changed',
      'closure_verified',
      'state_solver_invoked',
      'state_lineage_verified',
      'signed_residuals_verified',
      'moving_state_verified',
      'independent_residual_audit_verified',
      'residual_descent_verified',
      'accepted',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    if self.accepted and not (
      self.geometry_changed
      and self.closure_verified
      and self.state_lineage_verified
      and self.signed_residuals_verified
      and self.moving_state_verified
      and self.independent_residual_audit_verified
      and self.residual_descent_verified
    ):
      raise ValueError('accepted profile trials must pass every retained gate')
    object.__setattr__(self, 'message', str(self.message))

  def as_report(self) -> dict[str, Any]:
    return {
      'compression_envelope_skew': self.compression_envelope_skew,
      'closure_fingerprint': self.closure_fingerprint,
      'residual_norm': self.residual_norm,
      'geometry_changed': self.geometry_changed,
      'closure_verified': self.closure_verified,
      'state_solver_invoked': self.state_solver_invoked,
      'state_lineage_verified': self.state_lineage_verified,
      'signed_residuals_verified': self.signed_residuals_verified,
      'moving_state_verified': self.moving_state_verified,
      'independent_residual_audit_verified': (
        self.independent_residual_audit_verified
      ),
      'residual_descent_verified': self.residual_descent_verified,
      'accepted': self.accepted,
      'candidate_closure': (
        None
        if self.candidate_closure is None
        else self.candidate_closure.as_report()
      ),
      'state_request': (
        None if self.state_request is None else self.state_request.as_report()
      ),
      'state_result': (
        None if self.state_result is None else self.state_result.as_report()
      ),
      'conservative_residual_audit': (
        None
        if self.conservative_residual_audit is None
        else self.conservative_residual_audit.as_report()
      ),
      'message': self.message,
    }


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalBoundaryStateProfileUpdateResult:
  """Audited result of a fresh globally coupled profile update."""

  status: MocReflectedDomainGlobalBoundaryStateProfileUpdateStatus
  handoff: MocReflectedDomainGlobalBoundaryStateFeedbackHandoff | None
  source_closure: MocReflectedDomainGlobalPhysicalClosureResult | None = None
  updated_closure: MocReflectedDomainGlobalPhysicalClosureResult | None = None
  trials: tuple[MocReflectedDomainGlobalBoundaryStateProfileTrial, ...] = ()
  selected_trial_index: int | None = None
  state_request: MocReflectedDomainGlobalTwoSidedMovingInterfaceRequest | None = None
  state_result: MocReflectedDomainGlobalTwoSidedMovingInterfaceResult | None = None
  conservative_residual_audit: MocEulerTwoSidedConservativeResidualAudit | None = None
  baseline_residual_norm: float | None = None
  refreshed_residual_norm: float | None = None
  current_compression_envelope_skew: float | None = None
  candidate_compression_envelope_skews: tuple[float, ...] = ()
  handoff_lineage_verified: bool = False
  profile_sweep_invoked: bool = False
  profile_sweep_verified: bool = False
  closure_lineage_verified: bool = False
  state_solver_invoked: bool = False
  state_lineage_verified: bool = False
  signed_residuals_verified: bool = False
  moving_state_verified: bool = False
  independent_residual_audit_verified: bool = False
  geometry_update_verified: bool = False
  residual_descent_verified: bool = False
  physical_profile_update_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalBoundaryStateProfileUpdateStatus,
    ):
      raise TypeError('status must be a typed profile-update status')
    for name, expected_type in (
      ('handoff', MocReflectedDomainGlobalBoundaryStateFeedbackHandoff),
      ('source_closure', MocReflectedDomainGlobalPhysicalClosureResult),
      ('updated_closure', MocReflectedDomainGlobalPhysicalClosureResult),
      (
        'state_request',
        MocReflectedDomainGlobalTwoSidedMovingInterfaceRequest,
      ),
      ('state_result', MocReflectedDomainGlobalTwoSidedMovingInterfaceResult),
      ('conservative_residual_audit', MocEulerTwoSidedConservativeResidualAudit),
    ):
      value = getattr(self, name)
      if value is not None and not isinstance(value, expected_type):
        raise TypeError(f'{name} must be typed or None')
    trials = tuple(self.trials)
    if any(
      not isinstance(trial, MocReflectedDomainGlobalBoundaryStateProfileTrial)
      for trial in trials
    ):
      raise TypeError('trials must contain typed profile trials')
    object.__setattr__(self, 'trials', trials)
    if self.selected_trial_index is not None and (
      isinstance(self.selected_trial_index, bool)
      or not isinstance(self.selected_trial_index, int)
      or self.selected_trial_index < 0
      or self.selected_trial_index >= len(trials)
    ):
      raise ValueError('selected_trial_index must select a retained trial')
    for name in (
      'baseline_residual_norm',
      'refreshed_residual_norm',
      'current_compression_envelope_skew',
    ):
      value = getattr(self, name)
      if value is not None:
        numeric = float(value)
        if not isfinite(numeric) or (
          name.endswith('residual_norm') and numeric < 0.0
        ) or (
          name.endswith('skew') and abs(numeric) > 1.0
        ):
          raise ValueError(f'{name} is outside its finite domain')
        object.__setattr__(self, name, numeric)
    skews = tuple(float(value) for value in self.candidate_compression_envelope_skews)
    if any(not isfinite(value) or abs(value) > 1.0 for value in skews):
      raise ValueError('candidate skews must be finite values within [-1, 1]')
    object.__setattr__(self, 'candidate_compression_envelope_skews', skews)
    for name in (
      'handoff_lineage_verified',
      'profile_sweep_invoked',
      'profile_sweep_verified',
      'closure_lineage_verified',
      'state_solver_invoked',
      'state_lineage_verified',
      'signed_residuals_verified',
      'moving_state_verified',
      'independent_residual_audit_verified',
      'geometry_update_verified',
      'residual_descent_verified',
      'physical_profile_update_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError('profile updates must remain promotion-blocked')
    if self.status is (
      MocReflectedDomainGlobalBoundaryStateProfileUpdateStatus
      .CONVERGED_RESEARCH_PROFILE_UPDATE
    ) and not (
      self.physical_profile_update_verified
      and self.geometry_update_verified
      and self.residual_descent_verified
    ):
      raise ValueError('converged profile updates must pass geometry and descent gates')
    object.__setattr__(self, 'message', str(self.message))

  @property
  def converged_research_profile_update(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalBoundaryStateProfileUpdateStatus
      .CONVERGED_RESEARCH_PROFILE_UPDATE
      and self.physical_profile_update_verified
      and self.geometry_update_verified
      and self.residual_descent_verified
    )

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': (
        MOC_REFLECTED_DOMAIN_GLOBAL_BOUNDARY_STATE_PROFILE_UPDATE_OPERATOR_ID
      ),
      'status': self.status.value,
      'converged_research_profile_update': self.converged_research_profile_update,
      'handoff_lineage_verified': self.handoff_lineage_verified,
      'profile_sweep_invoked': self.profile_sweep_invoked,
      'profile_sweep_verified': self.profile_sweep_verified,
      'closure_lineage_verified': self.closure_lineage_verified,
      'state_solver_invoked': self.state_solver_invoked,
      'state_lineage_verified': self.state_lineage_verified,
      'signed_residuals_verified': self.signed_residuals_verified,
      'moving_state_verified': self.moving_state_verified,
      'independent_residual_audit_verified': (
        self.independent_residual_audit_verified
      ),
      'geometry_update_verified': self.geometry_update_verified,
      'residual_descent_verified': self.residual_descent_verified,
      'physical_profile_update_verified': self.physical_profile_update_verified,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'source_closure_fingerprint': (
        None if self.source_closure is None else _fingerprint(self.source_closure)
      ),
      'updated_closure_fingerprint': (
        None if self.updated_closure is None else _fingerprint(self.updated_closure)
      ),
      'baseline_residual_norm': self.baseline_residual_norm,
      'refreshed_residual_norm': self.refreshed_residual_norm,
      'current_compression_envelope_skew': self.current_compression_envelope_skew,
      'candidate_compression_envelope_skews': self.candidate_compression_envelope_skews,
      'selected_trial_index': self.selected_trial_index,
      'trials': tuple(trial.as_report() for trial in self.trials),
      'state_request': (
        None if self.state_request is None else self.state_request.as_report()
      ),
      'state_result': (
        None if self.state_result is None else self.state_result.as_report()
      ),
      'conservative_residual_audit': (
        None
        if self.conservative_residual_audit is None
        else self.conservative_residual_audit.as_report()
      ),
      'handoff': None if self.handoff is None else self.handoff.as_report(),
      'claim_status': (
        'research-only solver-owned compression-profile response; canonical '
        'mixed-regime closure, refinement, shock-cell promotion, Signature, '
        'FPA, external validation, and release remain open'
      ),
      'message': self.message,
    }


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalBoundaryStateProfileCase:
  """One disjoint handoff and source resolution for profile refinement."""

  case_id: str
  regime: str
  handoff: MocReflectedDomainGlobalBoundaryStateFeedbackHandoff
  resolution_sample_count: int

  def __post_init__(self) -> None:
    case_id = str(self.case_id)
    regime = str(self.regime)
    if not case_id or not regime:
      raise ValueError('case_id and regime must be non-empty')
    if not isinstance(
      self.handoff,
      MocReflectedDomainGlobalBoundaryStateFeedbackHandoff,
    ):
      raise TypeError('handoff must be a typed global boundary-state handoff')
    if (
      isinstance(self.resolution_sample_count, bool)
      or not isinstance(self.resolution_sample_count, int)
      or self.resolution_sample_count < 3
    ):
      raise ValueError('resolution_sample_count must be an integer >= 3')
    object.__setattr__(self, 'case_id', case_id)
    object.__setattr__(self, 'regime', regime)

  @property
  def source_closure(self) -> MocReflectedDomainGlobalPhysicalClosureResult:
    return self.handoff.boundary_feedback_run.final_closure

  @property
  def source_closure_fingerprint(self) -> str:
    return _fingerprint(self.source_closure)

  def as_report(self) -> dict[str, Any]:
    return {
      'case_id': self.case_id,
      'regime': self.regime,
      'resolution_sample_count': self.resolution_sample_count,
      'source_closure_fingerprint': self.source_closure_fingerprint,
      'handoff': self.handoff.as_report(),
    }


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalBoundaryStateProfileRefinementCase:
  """One retained profile update and its independent case gates."""

  case: MocReflectedDomainGlobalBoundaryStateProfileCase
  result: MocReflectedDomainGlobalBoundaryStateProfileUpdateResult
  source_lineage_verified: bool = False
  fresh_update_invocations_verified: bool = False
  geometry_update_verified: bool = False
  residual_descent_verified: bool = False
  independent_residual_audit_verified: bool = False
  fidelity_isolation_verified: bool = False
  residual_reduction_fraction: float | None = None
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.case,
      MocReflectedDomainGlobalBoundaryStateProfileCase,
    ):
      raise TypeError('case must be a typed profile refinement case')
    if not isinstance(
      self.result,
      MocReflectedDomainGlobalBoundaryStateProfileUpdateResult,
    ):
      raise TypeError('result must be a typed profile update result')
    if self.residual_reduction_fraction is not None:
      reduction = float(self.residual_reduction_fraction)
      if not isfinite(reduction) or reduction < 0.0:
        raise ValueError(
          'residual_reduction_fraction must be finite and nonnegative'
        )
      object.__setattr__(self, 'residual_reduction_fraction', reduction)
    for name in (
      'source_lineage_verified',
      'fresh_update_invocations_verified',
      'geometry_update_verified',
      'residual_descent_verified',
      'independent_residual_audit_verified',
      'fidelity_isolation_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    object.__setattr__(self, 'message', str(self.message))

  @property
  def local_research_verified(self) -> bool:
    return bool(
      self.result.converged_research_profile_update
      and self.source_lineage_verified
      and self.fresh_update_invocations_verified
      and self.geometry_update_verified
      and self.residual_descent_verified
      and self.independent_residual_audit_verified
      and self.fidelity_isolation_verified
    )

  def as_report(self) -> dict[str, Any]:
    return {
      'case': self.case.as_report(),
      'source_closure_fingerprint': self.case.source_closure_fingerprint,
      'local_research_verified': self.local_research_verified,
      'source_lineage_verified': self.source_lineage_verified,
      'fresh_update_invocations_verified': (
        self.fresh_update_invocations_verified
      ),
      'geometry_update_verified': self.geometry_update_verified,
      'residual_descent_verified': self.residual_descent_verified,
      'independent_residual_audit_verified': (
        self.independent_residual_audit_verified
      ),
      'fidelity_isolation_verified': self.fidelity_isolation_verified,
      'residual_reduction_fraction': self.residual_reduction_fraction,
      'result': self.result.as_report(),
      'message': self.message,
    }


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalBoundaryStateProfileRefinementMeasurement:
  """Aggregate disjoint-case and increasing-resolution profile evidence."""

  status: MocReflectedDomainGlobalBoundaryStateProfileRefinementStatus
  cases: tuple[
    MocReflectedDomainGlobalBoundaryStateProfileRefinementCase, ...
  ] = ()
  case_ids: tuple[str, ...] = ()
  source_closure_fingerprints: tuple[str, ...] = ()
  resolution_sample_counts: tuple[int, ...] = ()
  response_mode_identity: tuple[str, ...] = ()
  resolution_order_verified: bool = False
  distinct_cases_verified: bool = False
  distinct_source_closures_verified: bool = False
  case_bindings_verified: bool = False
  fresh_update_invocations_verified: bool = False
  geometry_updates_verified: bool = False
  strict_residual_descent_verified: bool = False
  independent_residual_audits_verified: bool = False
  residuals_finite: bool = False
  fidelity_isolation_verified: bool = False
  minimum_residual_reduction_fraction: float | None = None
  maximum_residual_reduction_fraction: float | None = None
  external_validation_required: bool = True
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  operator_id: str = (
    MOC_REFLECTED_DOMAIN_GLOBAL_BOUNDARY_STATE_PROFILE_CROSS_CASE_OPERATOR_ID
  )
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalBoundaryStateProfileRefinementStatus,
    ):
      raise TypeError('status must be a typed profile-refinement status')
    cases = tuple(self.cases)
    ids = tuple(str(value) for value in self.case_ids)
    fingerprints = tuple(str(value) for value in self.source_closure_fingerprints)
    resolutions = tuple(int(value) for value in self.resolution_sample_counts)
    if not (len(cases) == len(ids) == len(fingerprints) == len(resolutions)):
      raise ValueError('profile refinement case metadata must align')
    if any(
      not isinstance(
        case,
        MocReflectedDomainGlobalBoundaryStateProfileRefinementCase,
      )
      for case in cases
    ):
      raise TypeError('cases must contain typed profile refinement cases')
    if len(set(ids)) != len(ids):
      raise ValueError('profile refinement case IDs must be unique')
    if len(set(fingerprints)) != len(fingerprints):
      raise ValueError('profile refinement source closures must be distinct')
    if any(value < 3 for value in resolutions):
      raise ValueError('profile refinement resolutions must be >= 3')
    mode_identity = tuple(str(value) for value in self.response_mode_identity)
    if any(not value for value in mode_identity):
      raise ValueError('response_mode_identity values must be non-empty')
    for name in (
      'resolution_order_verified',
      'distinct_cases_verified',
      'distinct_source_closures_verified',
      'case_bindings_verified',
      'fresh_update_invocations_verified',
      'geometry_updates_verified',
      'strict_residual_descent_verified',
      'independent_residual_audits_verified',
      'residuals_finite',
      'fidelity_isolation_verified',
      'external_validation_required',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    if self.minimum_residual_reduction_fraction is not None:
      minimum = float(self.minimum_residual_reduction_fraction)
      if not isfinite(minimum) or minimum < 0.0:
        raise ValueError('minimum residual reduction must be finite and nonnegative')
      object.__setattr__(self, 'minimum_residual_reduction_fraction', minimum)
    if self.maximum_residual_reduction_fraction is not None:
      maximum = float(self.maximum_residual_reduction_fraction)
      if not isfinite(maximum) or maximum < 0.0:
        raise ValueError('maximum residual reduction must be finite and nonnegative')
      object.__setattr__(self, 'maximum_residual_reduction_fraction', maximum)
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError('profile refinement must remain promotion-blocked')
    if not self.external_validation_required:
      raise ValueError('profile refinement must retain external validation')
    object.__setattr__(self, 'cases', cases)
    object.__setattr__(self, 'case_ids', ids)
    object.__setattr__(self, 'source_closure_fingerprints', fingerprints)
    object.__setattr__(self, 'resolution_sample_counts', resolutions)
    object.__setattr__(self, 'response_mode_identity', mode_identity)
    object.__setattr__(self, 'operator_id', str(self.operator_id))
    object.__setattr__(self, 'message', str(self.message))

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalBoundaryStateProfileRefinementStatus
      .CONVERGED_RESEARCH_CROSS_CASE
      and len(self.cases) >= 2
      and self.resolution_order_verified
      and self.distinct_cases_verified
      and self.distinct_source_closures_verified
      and self.case_bindings_verified
      and self.fresh_update_invocations_verified
      and self.geometry_updates_verified
      and self.strict_residual_descent_verified
      and self.independent_residual_audits_verified
      and self.residuals_finite
      and self.fidelity_isolation_verified
      and self.external_validation_required
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
      and all(case.local_research_verified for case in self.cases)
    )

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': self.operator_id,
      'refinement_operator_id': (
        MOC_REFLECTED_DOMAIN_GLOBAL_BOUNDARY_STATE_PROFILE_REFINEMENT_OPERATOR_ID
      ),
      'status': self.status.value,
      'converged': self.converged,
      'case_ids': self.case_ids,
      'source_closure_fingerprints': self.source_closure_fingerprints,
      'resolution_sample_counts': self.resolution_sample_counts,
      'response_mode_identity': self.response_mode_identity,
      'resolution_order_verified': self.resolution_order_verified,
      'distinct_cases_verified': self.distinct_cases_verified,
      'distinct_source_closures_verified': self.distinct_source_closures_verified,
      'case_bindings_verified': self.case_bindings_verified,
      'fresh_update_invocations_verified': self.fresh_update_invocations_verified,
      'geometry_updates_verified': self.geometry_updates_verified,
      'strict_residual_descent_verified': self.strict_residual_descent_verified,
      'independent_residual_audits_verified': (
        self.independent_residual_audits_verified
      ),
      'residuals_finite': self.residuals_finite,
      'fidelity_isolation_verified': self.fidelity_isolation_verified,
      'minimum_residual_reduction_fraction': (
        self.minimum_residual_reduction_fraction
      ),
      'maximum_residual_reduction_fraction': (
        self.maximum_residual_reduction_fraction
      ),
      'external_validation_required': True,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'cases': tuple(case.as_report() for case in self.cases),
      'claim_status': (
        'research-only disjoint global profile-update evidence; canonical '
        'free-boundary closure, shock-cell promotion, Signature/FPA production, '
        'external validation, and release remain open'
      ),
      'message': self.message,
    }


def _result(
  status: MocReflectedDomainGlobalBoundaryStateProfileUpdateStatus,
  handoff: MocReflectedDomainGlobalBoundaryStateFeedbackHandoff | None,
  message: str,
  **kwargs: Any,
) -> MocReflectedDomainGlobalBoundaryStateProfileUpdateResult:
  return MocReflectedDomainGlobalBoundaryStateProfileUpdateResult(
    status=status,
    handoff=handoff,
    message=message,
    **kwargs,
  )


def _refinement_measurement(
  status: MocReflectedDomainGlobalBoundaryStateProfileRefinementStatus,
  message: str,
  **kwargs: Any,
) -> MocReflectedDomainGlobalBoundaryStateProfileRefinementMeasurement:
  return MocReflectedDomainGlobalBoundaryStateProfileRefinementMeasurement(
    status=status,
    message=message,
    **kwargs,
  )


def run_reflected_domain_global_boundary_state_profile_refinement(
  cases: Sequence[MocReflectedDomainGlobalBoundaryStateProfileCase],
  *,
  compression_profile_step: float = 0.25,
  maximum_profile_steps: int = 2,
) -> MocReflectedDomainGlobalBoundaryStateProfileRefinementMeasurement:
  """Run the same bounded profile policy on disjoint cases and resolutions.

  The caller supplies only already verified handoffs and their source
  resolutions.  Profile controls are owned by this runner and must be
  identical across cases.  Every case is solved afresh; reusing one profile
  result to manufacture refinement evidence is not permitted.
  """

  try:
    resolved_cases = tuple(cases)
  except TypeError:
    return _refinement_measurement(
      MocReflectedDomainGlobalBoundaryStateProfileRefinementStatus.INVALID_INPUT,
      'cases must be an iterable of typed profile refinement cases',
    )
  if len(resolved_cases) < 2:
    return _refinement_measurement(
      MocReflectedDomainGlobalBoundaryStateProfileRefinementStatus.INVALID_INPUT,
      'profile refinement requires at least two disjoint cases',
    )
  if any(
    not isinstance(case, MocReflectedDomainGlobalBoundaryStateProfileCase)
    for case in resolved_cases
  ):
    return _refinement_measurement(
      MocReflectedDomainGlobalBoundaryStateProfileRefinementStatus.INVALID_INPUT,
      'cases must contain typed profile refinement cases',
    )
  try:
    step = float(compression_profile_step)
    if not isfinite(step) or step <= 0.0 or step > 1.0:
      raise ValueError('compression_profile_step must be finite in (0, 1]')
    if (
      isinstance(maximum_profile_steps, bool)
      or not isinstance(maximum_profile_steps, int)
      or maximum_profile_steps < 1
    ):
      raise ValueError('maximum_profile_steps must be a positive integer')
  except (TypeError, ValueError) as error:
    return _refinement_measurement(
      MocReflectedDomainGlobalBoundaryStateProfileRefinementStatus.INVALID_INPUT,
      f'profile refinement setup failed: {error}',
    )
  ####

  case_ids = tuple(case.case_id for case in resolved_cases)
  fingerprints = tuple(
    case.source_closure_fingerprint for case in resolved_cases
  )
  resolutions = tuple(
    case.resolution_sample_count for case in resolved_cases
  )
  distinct_cases = len(set(case_ids)) == len(case_ids)
  distinct_sources = len(set(fingerprints)) == len(fingerprints)
  resolution_order = all(
    previous < current
    for previous, current in zip(resolutions, resolutions[1:])
  )
  mode_identity = (
    'profile-policy=solver-owned-symmetric-skew-sweep-v1',
    f'compression_profile_step={step:.12g}',
    f'maximum_profile_steps={maximum_profile_steps}',
    'candidate_closure=exact-global-physical-re-solve-v1',
    'candidate_state=exact-global-two-sided-re-solve-v1',
  )
  if not distinct_cases or not distinct_sources:
    return _refinement_measurement(
      MocReflectedDomainGlobalBoundaryStateProfileRefinementStatus
      .CASE_BINDING_FAILURE,
      'profile refinement requires unique case IDs and distinct source closure fingerprints',
      response_mode_identity=mode_identity,
      distinct_cases_verified=distinct_cases,
      distinct_source_closures_verified=distinct_sources,
      resolution_order_verified=resolution_order,
    )
  if not resolution_order:
    return _refinement_measurement(
      MocReflectedDomainGlobalBoundaryStateProfileRefinementStatus
      .RESOLUTION_FAILURE,
      'profile refinement resolutions must be strictly increasing',
      response_mode_identity=mode_identity,
      distinct_cases_verified=True,
      distinct_source_closures_verified=True,
      resolution_order_verified=False,
    )
  ####

  retained_cases: list[
    MocReflectedDomainGlobalBoundaryStateProfileRefinementCase
  ] = []
  for case in resolved_cases:
    result = run_reflected_domain_global_boundary_state_profile_update(
      case.handoff,
      compression_profile_step=step,
      maximum_profile_steps=maximum_profile_steps,
    )
    source = case.source_closure
    source_lineage = bool(
      result.handoff_lineage_verified
      and result.source_closure is source
      and result.source_closure is case.handoff.boundary_feedback_run.final_closure
      and result.as_report()['source_closure_fingerprint']
      == case.source_closure_fingerprint
    )
    fresh_update = bool(
      result.profile_sweep_invoked
      and result.profile_sweep_verified
      and result.trials
      and all(
        trial.candidate_closure is not None
        and trial.closure_fingerprint is not None
        and trial.closure_fingerprint != case.source_closure_fingerprint
        and trial.candidate_closure is not source
        and trial.closure_verified
        for trial in result.trials
      )
    )
    fidelity = bool(
      result.chain_promotion_blocked
      and not result.production_claim_allowed
      and result.state_request is not None
      and result.state_request.consume_global_physical_field_for_downstream_probes
      and result.updated_closure is not None
      and result.updated_closure is not source
    )
    reduction: float | None = None
    if (
      result.baseline_residual_norm is not None
      and result.refreshed_residual_norm is not None
      and result.baseline_residual_norm > 0.0
      and isfinite(result.baseline_residual_norm)
      and isfinite(result.refreshed_residual_norm)
    ):
      reduction = (
        result.baseline_residual_norm - result.refreshed_residual_norm
      ) / result.baseline_residual_norm
      reduction = max(0.0, reduction)
    retained_cases.append(
      MocReflectedDomainGlobalBoundaryStateProfileRefinementCase(
        case=case,
        result=result,
        source_lineage_verified=source_lineage,
        fresh_update_invocations_verified=fresh_update,
        geometry_update_verified=result.geometry_update_verified,
        residual_descent_verified=result.residual_descent_verified,
        independent_residual_audit_verified=(
          result.independent_residual_audit_verified
        ),
        fidelity_isolation_verified=fidelity,
        residual_reduction_fraction=reduction,
        message=(
          'case retained a fresh exact profile closure and independently '
          'audited strict residual descent'
          if result.converged_research_profile_update
          else 'case did not pass the complete profile-update evidence bundle'
        ),
      )
    )
  ####

  retained = tuple(retained_cases)
  reductions = tuple(
    case.residual_reduction_fraction
    for case in retained
    if case.residual_reduction_fraction is not None
  )
  residuals_finite = bool(
    len(reductions) == len(retained)
    and all(isfinite(value) and value > 0.0 for value in reductions)
  )
  common = dict(
    cases=retained,
    case_ids=case_ids,
    source_closure_fingerprints=fingerprints,
    resolution_sample_counts=resolutions,
    response_mode_identity=mode_identity,
    resolution_order_verified=True,
    distinct_cases_verified=True,
    distinct_source_closures_verified=True,
    case_bindings_verified=all(case.source_lineage_verified for case in retained),
    fresh_update_invocations_verified=all(
      case.fresh_update_invocations_verified for case in retained
    ),
    geometry_updates_verified=all(
      case.geometry_update_verified for case in retained
    ),
    strict_residual_descent_verified=all(
      case.residual_descent_verified for case in retained
    ),
    independent_residual_audits_verified=all(
      case.independent_residual_audit_verified for case in retained
    ),
    residuals_finite=residuals_finite,
    fidelity_isolation_verified=all(
      case.fidelity_isolation_verified for case in retained
    ),
    minimum_residual_reduction_fraction=(
      min(reductions) if reductions else None
    ),
    maximum_residual_reduction_fraction=(
      max(reductions) if reductions else None
    ),
  )
  if all(case.local_research_verified for case in retained):
    return _refinement_measurement(
      MocReflectedDomainGlobalBoundaryStateProfileRefinementStatus
      .CONVERGED_RESEARCH_CROSS_CASE,
      'disjoint profile-update cases passed fresh closure, geometry, audit, '
      'and strict-descent gates; external validation and promotion remain open',
      **common,
    )
  if not common['fresh_update_invocations_verified']:
    status = (
      MocReflectedDomainGlobalBoundaryStateProfileRefinementStatus
      .UPDATE_FAILURE
    )
    message = 'one or more cases did not retain a fresh profile-update sweep'
  elif not common['fidelity_isolation_verified']:
    status = (
      MocReflectedDomainGlobalBoundaryStateProfileRefinementStatus
      .FIDELITY_FAILURE
    )
    message = 'one or more cases did not retain the required fidelity isolation gates'
  else:
    status = (
      MocReflectedDomainGlobalBoundaryStateProfileRefinementStatus
      .STABILITY_FAILURE
    )
    message = (
      'one or more disjoint profile-update cases failed geometry, independent '
      'audit, or strict-descent evidence'
    )
  return _refinement_measurement(status, message, **common)


def run_reflected_domain_global_boundary_state_profile_update(
  handoff: MocReflectedDomainGlobalBoundaryStateFeedbackHandoff | None,
  *,
  compression_profile_step: float = 0.25,
  maximum_profile_steps: int = 2,
  candidate_compression_envelope_skews: Sequence[float] | None = None,
  branch: ShockBranch = ShockBranch.WEAK,
  closure_tolerance_m: float = 1.0e-6,
  maximum_boundary_iterations: int = 16,
) -> MocReflectedDomainGlobalBoundaryStateProfileUpdateResult:
  """Try fresh exact global closures along the bounded profile direction.

  The retained global remesh determines the source/target pair, amplitude
  bracket, sample count, and trace mode.  Only the compression-envelope skew
  is varied.  Each candidate is a new exact global closure and a new
  conservative moving-interface solve; the best accepted candidate must change
  the shock geometry and strictly lower the retained signed residual norm.
  """

  if not isinstance(
    handoff,
    MocReflectedDomainGlobalBoundaryStateFeedbackHandoff,
  ):
    return _result(
      MocReflectedDomainGlobalBoundaryStateProfileUpdateStatus.INVALID_INPUT,
      None,
      'handoff must be a typed global boundary-state feedback handoff',
    )
  try:
    if not handoff.ready_for_joint_global_resolve:
      raise ValueError('handoff is not ready for global profile consumption')
    source = handoff.boundary_feedback_run.final_closure
    if _fingerprint(source) != handoff.state_source_closure_fingerprint:
      raise ValueError('handoff state fingerprint does not match its final closure')
    if source.global_remesh is None or source.global_euler is None:
      raise ValueError('handoff closure did not retain a global remesh and Euler field')
    selected = source.global_remesh.selected_attempt
    if selected is None or selected.first_cell_result.compression_amplitude_bracket is None:
      raise ValueError('handoff closure did not retain a selected amplitude bracket')
    if selected.first_cell_result.selected_physical_field is None:
      raise ValueError('handoff closure did not retain a selected physical field')
    current_skew = float(selected.compression_envelope_skew)
    profile_step = float(compression_profile_step)
    if not isfinite(profile_step) or profile_step <= 0.0 or profile_step > 1.0:
      raise ValueError('compression_profile_step must be finite in (0, 1]')
    if (
      isinstance(maximum_profile_steps, bool)
      or not isinstance(maximum_profile_steps, int)
      or maximum_profile_steps < 1
    ):
      raise ValueError('maximum_profile_steps must be a positive integer')
    if not isinstance(branch, ShockBranch):
      raise ValueError('branch must be a ShockBranch')
    closure_tolerance = float(closure_tolerance_m)
    if not isfinite(closure_tolerance) or closure_tolerance <= 0.0:
      raise ValueError('closure_tolerance_m must be finite and positive')
    if (
      isinstance(maximum_boundary_iterations, bool)
      or not isinstance(maximum_boundary_iterations, int)
      or maximum_boundary_iterations < 1
    ):
      raise ValueError('maximum_boundary_iterations must be a positive integer')
    candidates = _candidate_skews(
      current_skew,
      profile_step,
      maximum_profile_steps,
      candidate_compression_envelope_skews,
    )
    if not candidates:
      raise ValueError('profile update requires at least one skew distinct from the source')
    baseline = float(handoff.final_residual_norm)
    base_request = handoff.two_sided_result.request
    if base_request is None:
      raise ValueError('handoff did not retain its two-sided request')
    source_band = source.source_band
    if source_band is None:
      raise ValueError('handoff closure did not retain its source band')
    selected_field = selected.first_cell_result.selected_physical_field
    amplitude_bracket = selected.first_cell_result.compression_amplitude_bracket
    sample_count = int(selected_field.sample_count)
    if sample_count < 3:
      raise ValueError('selected physical field did not retain a valid sample count')
    position_tolerance = float(selected_field.position_tolerance_m)
    shock_angle_tolerance = float(selected_field.shock_angle_tolerance_rad)
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _result(
      MocReflectedDomainGlobalBoundaryStateProfileUpdateStatus.HANDOFF_LINEAGE_FAILURE,
      handoff,
      f'profile-update handoff setup failed closed: {error}',
    )

  trials: list[MocReflectedDomainGlobalBoundaryStateProfileTrial] = []
  state_solver_invoked = False
  any_closure = False
  any_state = False
  any_independent = False
  for skew in candidates:
    candidate: MocReflectedDomainGlobalPhysicalClosureResult | None = None
    try:
      candidate = solve_reflected_domain_global_physical_closure(
        source_band,
        outer_source_indices=(selected.outer_source_index,),
        target_centerline_indices=(selected.target_centerline_index,),
        compression_amplitude_lower_rad=amplitude_bracket[0],
        compression_amplitude_upper_rad=amplitude_bracket[1],
        compression_envelope_skews=(skew,),
        use_trace_referenced_profile=source.global_remesh.use_trace_referenced_profile,
        closure_tolerance_m=closure_tolerance,
        incoming_handoff=source_band.incoming_handoff,
        sample_count=sample_count,
        branch=branch,
        position_tolerance_m=position_tolerance,
        maximum_boundary_iterations=maximum_boundary_iterations,
        shock_angle_tolerance_rad=shock_angle_tolerance,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      trials.append(
        MocReflectedDomainGlobalBoundaryStateProfileTrial(
          compression_envelope_skew=skew,
          candidate_closure=None,
          state_request=None,
          state_result=None,
          conservative_residual_audit=None,
          residual_norm=None,
          message=f'candidate global closure raised: {error}',
        )
      )
      continue
    any_closure = True
    candidate_fingerprint = _fingerprint(candidate)
    closure_verified = bool(
      candidate is not source
      and candidate_fingerprint != _fingerprint(source)
      and candidate.converged
      and candidate.physical_closure_verified
    )
    geometry_changed = _geometry_changed(source, candidate, position_tolerance)
    if not closure_verified:
      trials.append(
        MocReflectedDomainGlobalBoundaryStateProfileTrial(
          compression_envelope_skew=skew,
          candidate_closure=candidate,
          state_request=None,
          state_result=None,
          conservative_residual_audit=None,
          residual_norm=None,
          closure_fingerprint=candidate_fingerprint,
          geometry_changed=geometry_changed,
          closure_verified=False,
          message=(
            'candidate global closure did not pass its exact local physical '
            'gates; no lower-fidelity fallback was attempted'
          ),
        )
      )
      continue
    state_request = replace(
      base_request,
      closure=candidate,
      source='moc-global-boundary-state-profile-update-v1',
    )
    state_solver_invoked = True
    any_state = True
    try:
      state_result = solve_reflected_domain_global_two_sided_moving_interface(
        state_request
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      trials.append(
        MocReflectedDomainGlobalBoundaryStateProfileTrial(
          compression_envelope_skew=skew,
          candidate_closure=candidate,
          state_request=state_request,
          state_result=None,
          conservative_residual_audit=None,
          residual_norm=None,
          closure_fingerprint=candidate_fingerprint,
          geometry_changed=geometry_changed,
          closure_verified=True,
          state_solver_invoked=True,
          message=f'candidate conservative state solve raised: {error}',
        )
      )
      continue
    residual_result = state_result.conservative_residual_result
    audit = state_result.conservative_residual_audit
    response = _response(state_result)
    state_lineage = bool(
      state_result.request is state_request
      and state_request.closure is candidate
      and state_result.global_physical_field_consumed
    )
    signed = _signed_channels_finite(response)
    independent = bool(
      isinstance(audit, MocEulerTwoSidedConservativeResidualAudit)
      and audit.local_consistency_verified
    )
    moving = bool(
      residual_result is not None
      and residual_result.converged
      and state_result.status
      is MocReflectedDomainGlobalTwoSidedMovingInterfaceStatus
      .CONVERGED_RESEARCH_INTERFACE
      and response is not None
      and state_request.require_interface_motion
      and not state_request.allow_stationary_equilibrium
      and not response.stationary_equilibrium_candidate
      and response.maximum_normal_displacement_m > state_request.position_tolerance_m
    )
    refreshed = None if residual_result is None else residual_result.final_residual_norm
    descent = bool(
      refreshed is not None
      and _strict_descent(
        baseline,
        float(refreshed),
        state_request.minimum_residual_descent_fraction,
      )
    )
    any_independent = any_independent or independent
    accepted = bool(
      closure_verified
      and geometry_changed
      and state_lineage
      and signed
      and moving
      and independent
      and descent
    )
    trials.append(
      MocReflectedDomainGlobalBoundaryStateProfileTrial(
        compression_envelope_skew=skew,
        candidate_closure=candidate,
        state_request=state_request,
        state_result=state_result,
        conservative_residual_audit=audit,
        residual_norm=refreshed,
        closure_fingerprint=candidate_fingerprint,
        geometry_changed=geometry_changed,
        closure_verified=closure_verified,
        state_solver_invoked=True,
        state_lineage_verified=state_lineage,
        signed_residuals_verified=signed,
        moving_state_verified=moving,
        independent_residual_audit_verified=independent,
        residual_descent_verified=descent,
        accepted=accepted,
        message=(
          'fresh global profile candidate passed all geometry, state, audit, '
          'and strict-descent gates'
          if accepted
          else 'candidate retained typed evidence but did not pass every update gate'
        ),
      )
    )
  ####

  accepted_trials = tuple(
    (index, trial)
    for index, trial in enumerate(trials)
    if trial.accepted and trial.residual_norm is not None
  )
  selected_index: int | None = None
  selected_trial: MocReflectedDomainGlobalBoundaryStateProfileTrial | None = None
  if accepted_trials:
    selected_index, selected_trial = min(
      accepted_trials,
      key=lambda item: float(item[1].residual_norm),
    )
  profile_sweep_verified = bool(
    len(trials) == len(candidates)
    and any_closure
    and all(trial.candidate_closure is not None for trial in trials)
  )
  common = dict(
    source_closure=source,
    trials=tuple(trials),
    selected_trial_index=selected_index,
    baseline_residual_norm=baseline,
    current_compression_envelope_skew=current_skew,
    candidate_compression_envelope_skews=candidates,
    handoff_lineage_verified=True,
    profile_sweep_invoked=True,
    profile_sweep_verified=profile_sweep_verified,
    closure_lineage_verified=bool(any_closure),
    state_solver_invoked=state_solver_invoked,
    independent_residual_audit_verified=any_independent,
  )
  if selected_trial is not None:
    assert selected_trial.candidate_closure is not None
    assert selected_trial.state_request is not None
    assert selected_trial.state_result is not None
    return _result(
      MocReflectedDomainGlobalBoundaryStateProfileUpdateStatus
      .CONVERGED_RESEARCH_PROFILE_UPDATE,
      handoff,
      'fresh solver-owned compression-profile update changed the exact global '
      'shock geometry and strictly reduced the independently audited residual; '
      'canonical coupling and production promotion remain blocked',
      **common,
      updated_closure=selected_trial.candidate_closure,
      state_request=selected_trial.state_request,
      state_result=selected_trial.state_result,
      conservative_residual_audit=selected_trial.conservative_residual_audit,
      refreshed_residual_norm=selected_trial.residual_norm,
      state_lineage_verified=selected_trial.state_lineage_verified,
      signed_residuals_verified=selected_trial.signed_residuals_verified,
      moving_state_verified=selected_trial.moving_state_verified,
      geometry_update_verified=selected_trial.geometry_changed,
      residual_descent_verified=selected_trial.residual_descent_verified,
      physical_profile_update_verified=True,
    )
  ####
  if not any_closure:
    status = (
      MocReflectedDomainGlobalBoundaryStateProfileUpdateStatus
      .CANDIDATE_CLOSURE_FAILURE
    )
    message = 'no candidate global closure completed its typed solve'
  elif not any_state:
    status = (
      MocReflectedDomainGlobalBoundaryStateProfileUpdateStatus
      .STATE_SOLVER_FAILURE
    )
    message = 'no physically closed candidate reached the conservative state solver'
  elif not any_independent:
    status = (
      MocReflectedDomainGlobalBoundaryStateProfileUpdateStatus
      .RESIDUAL_AUDIT_FAILURE
    )
    message = 'candidate profile responses did not retain an independent residual audit'
  else:
    status = (
      MocReflectedDomainGlobalBoundaryStateProfileUpdateStatus
      .RESIDUAL_DESCENT_FAILURE
    )
    message = (
      'candidate profile closures changed or re-solved the physical state, but '
      'none changed geometry and strictly reduced the retained residual'
    )
  return _result(status, handoff, message, **common)
