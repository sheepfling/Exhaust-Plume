"""Resolution evidence for the global/coupled downstream response seam.

The coupled-Euler refinement ladder already measures local conservative-field
residuals.  This operator adds the missing upstream/downstream evidence: every
declared mesh is solved from the same exact global closure, the retained
boundary response is independently remeasured, and the overlap channels are
reported without turning a local mesh result into global feedback or a
production shock-cell claim.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from math import isfinite
from typing import Any, Sequence

from exhaust_plume.models.moc.coupled_euler_free_boundary import (
  MocReflectedDomainCoupledEulerInletBoundaryMode,
)
from exhaust_plume.models.moc.global_coupled_downstream import (
  MocReflectedDomainGlobalCoupledDownstreamBoundaryResponse,
  MocReflectedDomainGlobalCoupledDownstreamUpstreamFeedbackProposal,
  MocReflectedDomainGlobalCoupledDownstreamResult,
  MocReflectedDomainGlobalCoupledDownstreamStatus,
  build_reflected_domain_global_coupled_downstream_boundary_profiles_from_pressure_target,
  build_reflected_domain_global_solver_owned_physical_field_handoff,
  build_reflected_domain_global_coupled_downstream_upstream_feedback_proposal,
  measure_reflected_domain_global_coupled_downstream_boundary_response,
  solve_reflected_domain_global_coupled_downstream,
)
from exhaust_plume.models.moc.global_physical_closure import (
  MocReflectedDomainGlobalPhysicalClosureResult,
  moc_reflected_domain_global_physical_closure_fingerprint,
)
from exhaust_plume.models.moc.physical_field_euler_reconciliation import (
  MocPhysicalFieldEulerBoundaryPressureTarget,
)
from exhaust_plume.models.moc.reflected_domain_mixed_regime import (
  build_reflected_domain_mixed_regime_boundary_request,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_DOWNSTREAM_REFINEMENT_OPERATOR_ID',
  'MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_DOWNSTREAM_TARGET_BOUND_REFINEMENT_OPERATOR_ID',
  'MocReflectedDomainGlobalCoupledDownstreamRefinementStatus',
  'MocReflectedDomainGlobalCoupledDownstreamRefinementCase',
  'MocReflectedDomainGlobalCoupledDownstreamRefinementMeasurement',
  'measure_reflected_domain_global_coupled_downstream_refinement',
  'MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_DOWNSTREAM_REFINEMENT_RUN_OPERATOR_ID',
  'MocReflectedDomainGlobalCoupledDownstreamRefinementRun',
  'run_reflected_domain_global_coupled_downstream_refinement',
  'MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_DOWNSTREAM_TARGET_BOUND_REFINEMENT_RUN_OPERATOR_ID',
  'MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_DOWNSTREAM_CROSS_CASE_REFINEMENT_OPERATOR_ID',
  'MocReflectedDomainGlobalCoupledDownstreamCrossCaseStatus',
  'MocReflectedDomainGlobalCoupledDownstreamCrossCase',
  'MocReflectedDomainGlobalCoupledDownstreamCrossCaseMeasurement',
  'measure_reflected_domain_global_coupled_downstream_cross_case_refinement',
  'MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_DOWNSTREAM_CROSS_CASE_REFINEMENT_RUN_OPERATOR_ID',
  'MocReflectedDomainGlobalCoupledDownstreamCrossCaseRun',
  'run_reflected_domain_global_coupled_downstream_cross_case_refinement',
)


MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_DOWNSTREAM_REFINEMENT_OPERATOR_ID = (
  'op.moc.reflected-domain.global-coupled-downstream-refinement'
)
MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_DOWNSTREAM_REFINEMENT_RUN_OPERATOR_ID = (
  'op.moc.reflected-domain.global-coupled-downstream-refinement-run'
)
MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_DOWNSTREAM_TARGET_BOUND_REFINEMENT_OPERATOR_ID = (
  'op.moc.reflected-domain.global-coupled-downstream-target-bound-refinement'
)
MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_DOWNSTREAM_TARGET_BOUND_REFINEMENT_RUN_OPERATOR_ID = (
  'op.moc.reflected-domain.global-coupled-downstream-target-bound-refinement-run'
)
MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_DOWNSTREAM_CROSS_CASE_REFINEMENT_OPERATOR_ID = (
  'op.moc.reflected-domain.global-coupled-downstream-cross-case-refinement'
)
MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_DOWNSTREAM_CROSS_CASE_REFINEMENT_RUN_OPERATOR_ID = (
  'op.moc.reflected-domain.global-coupled-downstream-cross-case-refinement-run'
)


class MocReflectedDomainGlobalCoupledDownstreamRefinementStatus(str, Enum):
  """Outcome of an independently measured global/coupled response ladder."""

  CONVERGED_RESEARCH_LADDER = (
    'converged-research-global-coupled-downstream-ladder'
  )
  INVALID_INPUT = 'invalid_input'
  RESOLUTION_FAILURE = 'global-coupled-downstream-refinement-resolution-failure'
  CASE_FAILURE = 'global-coupled-downstream-refinement-case-failure'
  RESPONSE_FAILURE = 'global-coupled-downstream-refinement-response-failure'
  FIDELITY_FAILURE = 'global-coupled-downstream-refinement-fidelity-failure'
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalCoupledDownstreamRefinementCase:
  """One fresh coupled solve and an independent boundary-response measure."""

  resolution: tuple[int, int]
  result: MocReflectedDomainGlobalCoupledDownstreamResult
  solver_response: MocReflectedDomainGlobalCoupledDownstreamBoundaryResponse | None
  response: MocReflectedDomainGlobalCoupledDownstreamBoundaryResponse | None
  upstream_feedback_proposal: (
    MocReflectedDomainGlobalCoupledDownstreamUpstreamFeedbackProposal | None
  ) = None
  response_lineage_verified: bool = False
  boundary_target: MocPhysicalFieldEulerBoundaryPressureTarget | None = None
  target_lineage_verified: bool = False
  target_profiles_consumed_verified: bool = False

  def __post_init__(self) -> None:
    resolution = tuple(self.resolution)
    if len(resolution) != 2 or any(
      isinstance(value, bool) or not isinstance(value, int)
      for value in resolution
    ):
      raise ValueError('resolution must contain two integer counts')
    ####
    if resolution[0] < 4 or resolution[1] < 3:
      raise ValueError(
        'axial resolution must be at least four and transverse resolution '
        'must be at least three'
      )
    ####
    if not isinstance(
      self.result,
      MocReflectedDomainGlobalCoupledDownstreamResult,
    ):
      raise TypeError(
        'result must be a '
        'MocReflectedDomainGlobalCoupledDownstreamResult'
      )
    ####
    for name in ('solver_response', 'response'):
      value = getattr(self, name)
      if value is not None and not isinstance(
        value,
        MocReflectedDomainGlobalCoupledDownstreamBoundaryResponse,
      ):
        raise TypeError(
          f'{name} must be a '
          'MocReflectedDomainGlobalCoupledDownstreamBoundaryResponse or None'
        )
      ####
    ####
    if self.upstream_feedback_proposal is not None and not isinstance(
      self.upstream_feedback_proposal,
      MocReflectedDomainGlobalCoupledDownstreamUpstreamFeedbackProposal,
    ):
      raise TypeError(
        'upstream_feedback_proposal must be a typed global feedback proposal '
        'or None'
      )
    ####
    if not isinstance(self.response_lineage_verified, bool):
      raise TypeError('response_lineage_verified must be a bool')
    ####
    if self.boundary_target is not None and not isinstance(
      self.boundary_target,
      MocPhysicalFieldEulerBoundaryPressureTarget,
    ):
      raise TypeError(
        'boundary_target must be a '
        'MocPhysicalFieldEulerBoundaryPressureTarget or None'
      )
    ####
    for name in ('target_lineage_verified', 'target_profiles_consumed_verified'):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    object.__setattr__(self, 'resolution', resolution)
  ####

  @property
  def local_coupled_field_verified(self) -> bool:
    return bool(self.result.local_coupled_field_verified)
  ####

  @property
  def response_coverage_verified(self) -> bool:
    return bool(
      self.response is not None and self.response.overlap_coverage_verified
    )
  ####

  @property
  def response_residuals_verified(self) -> bool:
    return bool(self.response is not None and self.response.residuals_verified)
  ####

  @property
  def upstream_feedback_proposal_verified(self) -> bool:
    proposal = self.upstream_feedback_proposal
    return bool(
      proposal is not None
      and proposal.ready_for_global_resolve
      and self.response is not None
      and proposal.source_response_status == self.response.status.value
    )
  ####

  @property
  def fidelity_isolation_verified(self) -> bool:
    return bool(
      not self.result.global_coupling_verified
      and not self.result.downstream_boundary_closure_verified
      and self.result.chain_promotion_blocked
      and not self.result.production_claim_allowed
      and (self.response is None or not self.response.production_claim_allowed)
      and (
        self.upstream_feedback_proposal is None
        or (
          not self.upstream_feedback_proposal.consumed_by_global_solver
          and not self.upstream_feedback_proposal.production_claim_allowed
          and not self.upstream_feedback_proposal.global_coupling_verified
          and not self.upstream_feedback_proposal.downstream_boundary_closure_verified
        )
      )
    )
  ####

  @property
  def target_binding_requested(self) -> bool:
    """Whether this case consumed a typed target-bound profile pair."""

    return self.boundary_target is not None
  ####

  @property
  def target_binding_verified(self) -> bool:
    """Whether target lineage and both solver profile consumers are verified."""

    return bool(
      not self.target_binding_requested
      or (
        self.target_lineage_verified
        and self.target_profiles_consumed_verified
        and self.result.boundary_pressure_profile is not None
        and self.result.boundary_geometry_profile is not None
        and self.result.coupled_field is not None
        and self.result.coupled_field.free_boundary_pressure_profile_consumed
        and self.result.coupled_field.free_boundary_geometry_profile_consumed
      )
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'resolution': self.resolution,
      'cell_count': self.resolution[0] * self.resolution[1],
      'solver_status': self.result.status.value,
      'local_coupled_field_verified': self.local_coupled_field_verified,
      'response_lineage_verified': self.response_lineage_verified,
      'response_coverage_verified': self.response_coverage_verified,
      'response_residuals_verified': self.response_residuals_verified,
      'upstream_feedback_proposal_verified': (
        self.upstream_feedback_proposal_verified
      ),
      'target_binding_requested': self.target_binding_requested,
      'target_lineage_verified': self.target_lineage_verified,
      'target_profiles_consumed_verified': (
        self.target_profiles_consumed_verified
      ),
      'target_binding_verified': self.target_binding_verified,
      'boundary_target': (
        None
        if self.boundary_target is None
        else self.boundary_target.as_report()
      ),
      'upstream_feedback_proposal': (
        None
        if self.upstream_feedback_proposal is None
        else self.upstream_feedback_proposal.as_report()
      ),
      'fidelity_isolation_verified': self.fidelity_isolation_verified,
      'solver_response': (
        None if self.solver_response is None else self.solver_response.as_report()
      ),
      'response': None if self.response is None else self.response.as_report(),
      'result': self.result.as_report(),
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalCoupledDownstreamRefinementMeasurement:
  """Independent response-ladder evidence below the physical gate."""

  status: MocReflectedDomainGlobalCoupledDownstreamRefinementStatus
  cases: tuple[MocReflectedDomainGlobalCoupledDownstreamRefinementCase, ...] = ()
  resolutions: tuple[tuple[int, int], ...] = ()
  cell_counts: tuple[int, ...] = ()
  maximum_coordinate_residuals_m: tuple[float, ...] = ()
  maximum_tangent_residuals_rad: tuple[float, ...] = ()
  maximum_pressure_residuals_Pa: tuple[float, ...] = ()
  maximum_normal_velocity_residuals_m_s: tuple[float, ...] = ()
  resolution_order_verified: bool = False
  mesh_growth_verified: bool = False
  case_audits_verified: bool = False
  response_lineage_verified: bool = False
  response_channels_finite: bool = False
  overlap_coverage_verified: bool = False
  overlap_residuals_verified: bool = False
  upstream_feedback_proposals_verified: bool = False
  upstream_feedback_source_lineage_verified: bool = False
  upstream_feedback_common_station_domain_verified: bool = False
  upstream_feedback_station_domains_m: tuple[tuple[float, float], ...] = ()
  upstream_feedback_common_station_domain_m: tuple[float, float] | None = None
  local_coupled_field_verified: bool = False
  fidelity_isolation_verified: bool = False
  target_binding_requested: bool = False
  target_lineage_verified: bool = False
  target_profiles_consumed_verified: bool = False
  global_coupling_verified: bool = False
  downstream_boundary_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  operator_id: str = (
    MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_DOWNSTREAM_REFINEMENT_OPERATOR_ID
  )
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalCoupledDownstreamRefinementStatus,
    ):
      raise TypeError(
        'status must be a '
        'MocReflectedDomainGlobalCoupledDownstreamRefinementStatus'
      )
    ####
    cases = tuple(self.cases)
    if any(
      not isinstance(
        case,
        MocReflectedDomainGlobalCoupledDownstreamRefinementCase,
      )
      for case in cases
    ):
      raise TypeError(
        'cases must contain typed global/coupled downstream refinement cases'
      )
    ####
    object.__setattr__(self, 'cases', cases)
    resolutions = tuple(tuple(value) for value in self.resolutions)
    if len(resolutions) != len(cases):
      raise ValueError('resolutions must match cases')
    ####
    object.__setattr__(self, 'resolutions', resolutions)
    cell_counts = tuple(int(value) for value in self.cell_counts)
    if len(cell_counts) != len(cases):
      raise ValueError('cell_counts must match cases')
    ####
    object.__setattr__(self, 'cell_counts', cell_counts)
    station_domains = tuple(
      (float(domain[0]), float(domain[1]))
      for domain in self.upstream_feedback_station_domains_m
    )
    if len(station_domains) != len(cases) or any(
      not all(isfinite(value) for value in domain)
      or domain[1] < domain[0]
      for domain in station_domains
    ):
      raise ValueError(
        'upstream_feedback_station_domains_m must contain one ordered '
        'finite domain per case'
      )
    ####
    common_domain = self.upstream_feedback_common_station_domain_m
    if common_domain is not None:
      common_domain = (
        float(common_domain[0]),
        float(common_domain[1]),
      )
      if (
        not all(isfinite(value) for value in common_domain)
        or common_domain[1] <= common_domain[0]
      ):
        raise ValueError(
          'upstream_feedback_common_station_domain_m must be a finite '
          'strictly ordered domain when supplied'
        )
      ####
    ####
    object.__setattr__(
      self,
      'upstream_feedback_station_domains_m',
      station_domains,
    )
    object.__setattr__(
      self,
      'upstream_feedback_common_station_domain_m',
      common_domain,
    )
    for name in (
      'maximum_coordinate_residuals_m',
      'maximum_tangent_residuals_rad',
      'maximum_pressure_residuals_Pa',
      'maximum_normal_velocity_residuals_m_s',
    ):
      values = tuple(float(value) for value in getattr(self, name))
      if len(values) != len(cases) or any(
        not isfinite(value) or value < 0.0 for value in values
      ):
        raise ValueError(f'{name} must contain one finite nonnegative value per case')
      ####
      object.__setattr__(self, name, values)
    ####
    for name in (
      'resolution_order_verified',
      'mesh_growth_verified',
      'case_audits_verified',
      'response_lineage_verified',
      'response_channels_finite',
      'overlap_coverage_verified',
      'overlap_residuals_verified',
      'upstream_feedback_proposals_verified',
      'upstream_feedback_source_lineage_verified',
      'upstream_feedback_common_station_domain_verified',
      'local_coupled_field_verified',
      'fidelity_isolation_verified',
      'target_binding_requested',
      'target_lineage_verified',
      'target_profiles_consumed_verified',
      'global_coupling_verified',
      'downstream_boundary_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if self.global_coupling_verified or self.downstream_boundary_closure_verified:
      raise ValueError(
        'research response refinement cannot claim global or downstream closure'
      )
    ####
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError(
        'research response refinement must retain its promotion block'
      )
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalCoupledDownstreamRefinementStatus
      .CONVERGED_RESEARCH_LADDER
      and self.resolution_order_verified
      and self.mesh_growth_verified
      and self.case_audits_verified
      and self.response_lineage_verified
      and self.response_channels_finite
      and self.overlap_coverage_verified
      and self.overlap_residuals_verified
      and self.upstream_feedback_proposals_verified
      and self.upstream_feedback_source_lineage_verified
      and self.upstream_feedback_common_station_domain_verified
      and self.local_coupled_field_verified
      and self.fidelity_isolation_verified
      and (
        not self.target_binding_requested
        or (
          self.target_lineage_verified
          and self.target_profiles_consumed_verified
        )
      )
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'resolutions': self.resolutions,
      'cell_counts': self.cell_counts,
      'maximum_coordinate_residuals_m': self.maximum_coordinate_residuals_m,
      'maximum_tangent_residuals_rad': self.maximum_tangent_residuals_rad,
      'maximum_pressure_residuals_Pa': self.maximum_pressure_residuals_Pa,
      'maximum_normal_velocity_residuals_m_s': (
        self.maximum_normal_velocity_residuals_m_s
      ),
      'resolution_order_verified': self.resolution_order_verified,
      'mesh_growth_verified': self.mesh_growth_verified,
      'case_audits_verified': self.case_audits_verified,
      'response_lineage_verified': self.response_lineage_verified,
      'response_channels_finite': self.response_channels_finite,
      'overlap_coverage_verified': self.overlap_coverage_verified,
      'overlap_residuals_verified': self.overlap_residuals_verified,
      'upstream_feedback_proposals_verified': (
        self.upstream_feedback_proposals_verified
      ),
      'upstream_feedback_source_lineage_verified': (
        self.upstream_feedback_source_lineage_verified
      ),
      'upstream_feedback_common_station_domain_verified': (
        self.upstream_feedback_common_station_domain_verified
      ),
      'upstream_feedback_station_domains_m': (
        self.upstream_feedback_station_domains_m
      ),
      'upstream_feedback_common_station_domain_m': (
        self.upstream_feedback_common_station_domain_m
      ),
      'local_coupled_field_verified': self.local_coupled_field_verified,
      'fidelity_isolation_verified': self.fidelity_isolation_verified,
      'target_binding_requested': self.target_binding_requested,
      'target_lineage_verified': self.target_lineage_verified,
      'target_profiles_consumed_verified': (
        self.target_profiles_consumed_verified
      ),
      'global_coupling_verified': self.global_coupling_verified,
      'downstream_boundary_closure_verified': (
        self.downstream_boundary_closure_verified
      ),
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'cases': tuple(case.as_report() for case in self.cases),
      'message': self.message,
    }
  ####
####


def _measurement_status(
  *,
  resolution_order_verified: bool,
  mesh_growth_verified: bool,
  case_audits_verified: bool,
  response_lineage_verified: bool,
  response_channels_finite: bool,
  overlap_coverage_verified: bool,
  overlap_residuals_verified: bool,
  upstream_feedback_proposals_verified: bool,
  upstream_feedback_source_lineage_verified: bool,
  upstream_feedback_common_station_domain_verified: bool,
  fidelity_isolation_verified: bool,
  target_binding_requested: bool,
  target_lineage_verified: bool,
  target_profiles_consumed_verified: bool,
) -> tuple[
  MocReflectedDomainGlobalCoupledDownstreamRefinementStatus,
  str,
]:
  if not resolution_order_verified or not mesh_growth_verified:
    return (
      MocReflectedDomainGlobalCoupledDownstreamRefinementStatus.RESOLUTION_FAILURE,
      'declared coupled-Euler resolutions are not strictly ordered with mesh growth',
    )
  ####
  if not fidelity_isolation_verified:
    return (
      MocReflectedDomainGlobalCoupledDownstreamRefinementStatus.FIDELITY_FAILURE,
      'a response-ladder case changed the global or production claim ceiling',
    )
  ####
  if target_binding_requested and not (
    target_lineage_verified and target_profiles_consumed_verified
  ):
    return (
      MocReflectedDomainGlobalCoupledDownstreamRefinementStatus.RESPONSE_FAILURE,
      'the target-bound coupled-Euler ladder did not retain exact target '
      'lineage or consume both pressure and geometry profiles at every '
      'declared resolution',
    )
  ####
  if not case_audits_verified:
    return (
      MocReflectedDomainGlobalCoupledDownstreamRefinementStatus.CASE_FAILURE,
      'at least one fresh coupled-Euler case did not pass its local audit',
    )
  ####
  if not (
    response_lineage_verified
    and response_channels_finite
    and overlap_coverage_verified
    and overlap_residuals_verified
    and upstream_feedback_proposals_verified
    and upstream_feedback_source_lineage_verified
    and upstream_feedback_common_station_domain_verified
  ):
    return (
      MocReflectedDomainGlobalCoupledDownstreamRefinementStatus.RESPONSE_FAILURE,
      'the coupled-Euler ladder is locally measured, but global-boundary '
      'overlap or cross-resolution frontier evidence is incomplete or '
      'exceeds its declared tolerances',
    )
  ####
  return (
    MocReflectedDomainGlobalCoupledDownstreamRefinementStatus
    .CONVERGED_RESEARCH_LADDER,
    'fresh global/coupled downstream response ladder passed its local '
    'overlap checks; global feedback and production promotion remain blocked',
  )
####


def measure_reflected_domain_global_coupled_downstream_refinement(
  cases: Sequence[MocReflectedDomainGlobalCoupledDownstreamRefinementCase],
) -> MocReflectedDomainGlobalCoupledDownstreamRefinementMeasurement:
  """Independently measure response evidence across fresh mesh cases."""

  retained_cases = tuple(cases)
  if not retained_cases:
    raise ValueError('cases must not be empty')
  ####
  resolutions = tuple(case.resolution for case in retained_cases)
  cell_counts = tuple(
    resolution[0] * resolution[1] for resolution in resolutions
  )
  resolution_order_verified = all(
    second[0] > first[0] and second[1] > first[1]
    for first, second in zip(resolutions, resolutions[1:])
  )
  mesh_growth_verified = all(
    second > first for first, second in zip(cell_counts, cell_counts[1:])
  )
  responses = tuple(case.response for case in retained_cases)
  response_channels_finite = bool(
    responses
    and all(
      response is not None
      and all(
        isfinite(value)
        for channel in (
          response.coordinate_residuals_m,
          response.tangent_residuals_rad,
          response.pressure_residuals_Pa,
          response.normal_velocity_residuals_m_s,
          response.coordinate_offsets_m,
          response.tangent_offsets_rad,
          response.pressure_offsets_Pa,
          response.normal_velocity_values_m_s,
        )
        for value in channel
      )
      for response in responses
    )
  )
  maximum_coordinate = tuple(
    0.0 if response is None else response.maximum_coordinate_residual_m
    for response in responses
  )
  maximum_tangent = tuple(
    0.0 if response is None else response.maximum_tangent_residual_rad
    for response in responses
  )
  maximum_pressure = tuple(
    0.0 if response is None else response.maximum_pressure_residual_Pa
    for response in responses
  )
  maximum_normal_velocity = tuple(
    0.0 if response is None else response.maximum_normal_velocity_residual_m_s
    for response in responses
  )
  case_audits_verified = all(
    case.local_coupled_field_verified and case.response is not None
    for case in retained_cases
  )
  response_lineage_verified = all(
    case.response_lineage_verified for case in retained_cases
  )
  overlap_coverage_verified = all(
    case.response_coverage_verified for case in retained_cases
  )
  overlap_residuals_verified = all(
    case.response_residuals_verified for case in retained_cases
  )
  upstream_feedback_proposals_verified = all(
    case.upstream_feedback_proposal_verified for case in retained_cases
  )
  proposals = tuple(
    case.upstream_feedback_proposal for case in retained_cases
  )
  upstream_feedback_source_lineage_verified = bool(
    upstream_feedback_proposals_verified
    and proposals
    and len({
      proposal.source_closure_fingerprint
      for proposal in proposals
      if proposal is not None
    }) == 1
  )
  upstream_feedback_station_domains = tuple(
    (
      proposal.matched_x_stations_m[0],
      proposal.matched_x_stations_m[-1],
    )
    if proposal is not None and proposal.ready_for_global_resolve
    else (0.0, 0.0)
    for proposal in proposals
  )
  common_station_domain: tuple[float, float] | None = None
  if upstream_feedback_station_domains and all(
    domain[1] > domain[0] for domain in upstream_feedback_station_domains
  ):
    common_start = max(
      domain[0] for domain in upstream_feedback_station_domains
    )
    common_end = min(
      domain[1] for domain in upstream_feedback_station_domains
    )
    if common_end > common_start:
      common_station_domain = (common_start, common_end)
    ####
  ####
  upstream_feedback_common_station_domain_verified = bool(
    upstream_feedback_source_lineage_verified
    and common_station_domain is not None
  )
  fidelity_isolation_verified = all(
    case.fidelity_isolation_verified for case in retained_cases
  )
  target_binding_requested = any(
    case.target_binding_requested for case in retained_cases
  )
  target_lineage_verified = bool(
    not target_binding_requested
    or all(
      case.target_lineage_verified
      for case in retained_cases
      if case.target_binding_requested
    )
  )
  target_profiles_consumed_verified = bool(
    not target_binding_requested
    or all(
      case.target_binding_verified
      for case in retained_cases
      if case.target_binding_requested
    )
  )
  status, message = _measurement_status(
    resolution_order_verified=resolution_order_verified,
    mesh_growth_verified=mesh_growth_verified,
    case_audits_verified=case_audits_verified,
    response_lineage_verified=response_lineage_verified,
    response_channels_finite=response_channels_finite,
    overlap_coverage_verified=overlap_coverage_verified,
    overlap_residuals_verified=overlap_residuals_verified,
    upstream_feedback_proposals_verified=upstream_feedback_proposals_verified,
    upstream_feedback_source_lineage_verified=(
      upstream_feedback_source_lineage_verified
    ),
    upstream_feedback_common_station_domain_verified=(
      upstream_feedback_common_station_domain_verified
    ),
    fidelity_isolation_verified=fidelity_isolation_verified,
    target_binding_requested=target_binding_requested,
    target_lineage_verified=target_lineage_verified,
    target_profiles_consumed_verified=target_profiles_consumed_verified,
  )
  return MocReflectedDomainGlobalCoupledDownstreamRefinementMeasurement(
    status=status,
    cases=retained_cases,
    resolutions=resolutions,
    cell_counts=cell_counts,
    maximum_coordinate_residuals_m=maximum_coordinate,
    maximum_tangent_residuals_rad=maximum_tangent,
    maximum_pressure_residuals_Pa=maximum_pressure,
    maximum_normal_velocity_residuals_m_s=maximum_normal_velocity,
    resolution_order_verified=resolution_order_verified,
    mesh_growth_verified=mesh_growth_verified,
    case_audits_verified=case_audits_verified,
    response_lineage_verified=response_lineage_verified,
    response_channels_finite=response_channels_finite,
    overlap_coverage_verified=overlap_coverage_verified,
    overlap_residuals_verified=overlap_residuals_verified,
    upstream_feedback_proposals_verified=upstream_feedback_proposals_verified,
    upstream_feedback_source_lineage_verified=(
      upstream_feedback_source_lineage_verified
    ),
    upstream_feedback_common_station_domain_verified=(
      upstream_feedback_common_station_domain_verified
    ),
    upstream_feedback_station_domains_m=upstream_feedback_station_domains,
    upstream_feedback_common_station_domain_m=common_station_domain,
    local_coupled_field_verified=all(
      case.local_coupled_field_verified for case in retained_cases
    ),
    fidelity_isolation_verified=fidelity_isolation_verified,
    target_binding_requested=target_binding_requested,
    target_lineage_verified=target_lineage_verified,
    target_profiles_consumed_verified=target_profiles_consumed_verified,
    operator_id=(
      MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_DOWNSTREAM_TARGET_BOUND_REFINEMENT_OPERATOR_ID
      if target_binding_requested
      else MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_DOWNSTREAM_REFINEMENT_OPERATOR_ID
    ),
    message=message,
  )
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalCoupledDownstreamRefinementRun:
  """Fresh execution record for one exact global closure and mesh ladder."""

  closure: MocReflectedDomainGlobalPhysicalClosureResult
  requested_resolutions: tuple[tuple[int, int], ...]
  cases: tuple[MocReflectedDomainGlobalCoupledDownstreamRefinementCase, ...]
  measurement: MocReflectedDomainGlobalCoupledDownstreamRefinementMeasurement
  configuration: dict[str, Any]
  configuration_fingerprint: str
  fresh_solver_invocation_verified: bool = False
  fidelity_isolation_verified: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.closure,
      MocReflectedDomainGlobalPhysicalClosureResult,
    ):
      raise TypeError(
        'closure must be a MocReflectedDomainGlobalPhysicalClosureResult'
      )
    ####
    requested = tuple(tuple(value) for value in self.requested_resolutions)
    cases = tuple(self.cases)
    if requested != tuple(case.resolution for case in cases):
      raise ValueError('requested_resolutions must match case resolutions')
    ####
    if self.measurement.cases != cases:
      raise ValueError('measurement must retain the exact cases')
    ####
    if len(self.configuration_fingerprint) != 64:
      raise ValueError('configuration_fingerprint must be a SHA-256 digest')
    ####
    if not isinstance(self.fresh_solver_invocation_verified, bool):
      raise TypeError('fresh_solver_invocation_verified must be a bool')
    ####
    if not isinstance(self.fidelity_isolation_verified, bool):
      raise TypeError('fidelity_isolation_verified must be a bool')
    ####
    if self.measurement.production_claim_allowed:
      raise ValueError('response refinement cannot claim production validity')
    ####
    object.__setattr__(self, 'requested_resolutions', requested)
    object.__setattr__(self, 'cases', cases)
    object.__setattr__(self, 'configuration', dict(self.configuration))
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
        MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_DOWNSTREAM_TARGET_BOUND_REFINEMENT_RUN_OPERATOR_ID
        if self.measurement.target_binding_requested
        else MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_DOWNSTREAM_REFINEMENT_RUN_OPERATOR_ID
      ),
      'converged': self.converged,
      'requested_resolutions': self.requested_resolutions,
      'fresh_solver_invocation_verified': self.fresh_solver_invocation_verified,
      'fidelity_isolation_verified': self.fidelity_isolation_verified,
      'production_claim_allowed': self.production_claim_allowed,
      'configuration': self.configuration,
      'configuration_fingerprint': self.configuration_fingerprint,
      'cases': tuple(case.as_report() for case in self.cases),
      'measurement': self.measurement.as_report(),
      'message': self.message,
    }
  ####
####


def _failed_result(
  closure: MocReflectedDomainGlobalPhysicalClosureResult,
  message: str,
) -> MocReflectedDomainGlobalCoupledDownstreamResult:
  return MocReflectedDomainGlobalCoupledDownstreamResult(
    status=MocReflectedDomainGlobalCoupledDownstreamStatus.COUPLED_SOLVER_FAILURE,
    closure=closure,
    mixed_regime_request=None,
    coupled_request=None,
    coupled_field=None,
    coupled_field_audit=None,
    message=message,
  )
####


def _target_bound_profiles_for_resolution(
  closure: MocReflectedDomainGlobalPhysicalClosureResult,
  target: MocPhysicalFieldEulerBoundaryPressureTarget,
  *,
  resolution: tuple[int, int],
  ambient_pressure_Pa: float | None,
  downstream_length_m: float,
  initial_outlet_height_m: float,
  control_section_x_offset_m: float,
  control_section_height_m: float,
  control_section_sample_count: int,
  solver_inlet_x_start_m: float | None = None,
  solver_inlet_lower_ordinate_m: float | None = None,
) -> tuple[Any, Any]:
  """Build exact pressure-center and geometry-node profiles for one mesh."""

  mixed_request = build_reflected_domain_mixed_regime_boundary_request(
    closure,
    ambient_pressure_Pa=ambient_pressure_Pa,
    downstream_length_m=downstream_length_m,
    initial_outlet_height_m=initial_outlet_height_m,
    control_section_x_offset_m=control_section_x_offset_m,
    control_section_height_m=control_section_height_m,
    control_section_sample_count=control_section_sample_count,
    axial_station_count=resolution[0],
  )
  x_start = float(mixed_request.control_section.points_m[0][0])
  lower_ordinate = float(mixed_request.control_section.points_m[0][1])
  if solver_inlet_x_start_m is not None:
    x_start = float(solver_inlet_x_start_m)
  ####
  if solver_inlet_lower_ordinate_m is not None:
    lower_ordinate = float(solver_inlet_lower_ordinate_m)
  ####
  axial_count = resolution[0]
  x_nodes = tuple(
    x_start + float(downstream_length_m) * index / axial_count
    for index in range(axial_count + 1)
  )
  x_centers = tuple(
    0.5 * (first + second)
    for first, second in zip(x_nodes, x_nodes[1:])
  )
  return build_reflected_domain_global_coupled_downstream_boundary_profiles_from_pressure_target(
    closure,
    target,
    x_centers,
    x_nodes,
    lower_ordinate_m=lower_ordinate,
  )
####


def _target_bound_lineage_verified(
  closure: MocReflectedDomainGlobalPhysicalClosureResult,
  target: MocPhysicalFieldEulerBoundaryPressureTarget,
  result: MocReflectedDomainGlobalCoupledDownstreamResult,
) -> bool:
  """Verify that both consumed profiles retain target and closure identity."""

  pressure_profile = result.boundary_pressure_profile
  geometry_profile = result.boundary_geometry_profile
  if pressure_profile is None or geometry_profile is None:
    return False
  ####
  closure_fingerprint = moc_reflected_domain_global_physical_closure_fingerprint(
    closure
  )
  target_source = f'{target.source_id}:{target.composition_mode}'
  return bool(
    pressure_profile.source == (
      'research-global-frontier-target-coupled-pressure-v1:'
      f'{target_source}'
    )
    and geometry_profile.source == (
      'research-global-frontier-target-coupled-geometry-v1:'
      f'{target_source}'
    )
    and pressure_profile.source_closure_fingerprint == closure_fingerprint
    and geometry_profile.source_closure_fingerprint == closure_fingerprint
  )
####


def _target_bound_profiles_consumed_verified(
  result: MocReflectedDomainGlobalCoupledDownstreamResult,
) -> bool:
  """Verify that the coupled 2-D field consumed both target profile types."""

  field = result.coupled_field
  return bool(
    result.boundary_pressure_profile is not None
    and result.boundary_geometry_profile is not None
    and field is not None
    and field.free_boundary_pressure_profile_consumed
    and field.free_boundary_geometry_profile_consumed
  )
####


def run_reflected_domain_global_coupled_downstream_refinement(
  closure: MocReflectedDomainGlobalPhysicalClosureResult,
  *,
  reference_total_temperature_K: float,
  resolutions: Sequence[tuple[int, int]],
  ambient_pressure_Pa: float | None = None,
  downstream_length_m: float = 0.2,
  initial_outlet_height_m: float = 0.05,
  control_section_x_offset_m: float = 0.02,
  control_section_height_m: float = 0.05,
  control_section_sample_count: int = 4,
  max_pseudo_iterations: int = 1200,
  max_shape_iterations: int = 18,
  inlet_boundary_mode: MocReflectedDomainCoupledEulerInletBoundaryMode = (
    MocReflectedDomainCoupledEulerInletBoundaryMode.FULL_STATE_RUSANOV
  ),
  outlet_static_pressure_Pa: float | None = None,
  physical_field_continuation_profile: Any | None = None,
  physical_field_shock_front_condition: Any | None = None,
  boundary_pressure_target: MocPhysicalFieldEulerBoundaryPressureTarget | None = None,
) -> MocReflectedDomainGlobalCoupledDownstreamRefinementRun:
  """Freshly solve and independently measure each declared mesh resolution.

  When ``boundary_pressure_target`` is supplied, each resolution receives a
  freshly sampled pressure profile at cell centers and geometry profile at
  free-boundary nodes.  The exact target and closure lineage are retained in
  every case; profile construction or coverage failure never falls back to an
  unbound solve.
  """

  if not isinstance(closure, MocReflectedDomainGlobalPhysicalClosureResult):
    raise TypeError(
      'closure must be a MocReflectedDomainGlobalPhysicalClosureResult'
    )
  ####
  if boundary_pressure_target is not None and not isinstance(
    boundary_pressure_target,
    MocPhysicalFieldEulerBoundaryPressureTarget,
  ):
    raise TypeError(
      'boundary_pressure_target must be a '
      'MocPhysicalFieldEulerBoundaryPressureTarget or None'
    )
  ####
  requested_resolutions = tuple(tuple(value) for value in resolutions)
  if not requested_resolutions:
    raise ValueError('resolutions must not be empty')
  ####
  if any(
    len(resolution) != 2
    or any(
      isinstance(value, bool) or not isinstance(value, int)
      for value in resolution
    )
    or resolution[0] < 4
    or resolution[1] < 3
    for resolution in requested_resolutions
  ):
    raise ValueError(
      'resolutions must contain (axial, transverse) integer pairs with '
      'axial >= 4 and transverse >= 3'
    )
  ####
  if any(
    second[0] <= first[0] or second[1] <= first[1]
    for first, second in zip(requested_resolutions, requested_resolutions[1:])
  ):
    raise ValueError('resolutions must strictly increase in both dimensions')
  ####
  target_solver_x_start_m: float | None = None
  target_solver_lower_ordinate_m: float | None = None
  target_frame_failure: str | None = None
  if (
    boundary_pressure_target is not None
    and inlet_boundary_mode
    is MocReflectedDomainCoupledEulerInletBoundaryMode
    .SOLVER_OWNED_PHYSICAL_FIELD_CONTINUATION_PROFILE
  ):
    coupled_inlet_profile = None
    if physical_field_shock_front_condition is not None:
      coupled_inlet_profile = getattr(
        physical_field_shock_front_condition,
        'coupled_inlet_profile',
        None,
      )
    ####
    if (
      coupled_inlet_profile is None
      and physical_field_continuation_profile is None
      and physical_field_shock_front_condition is None
    ):
      try:
        handoff = build_reflected_domain_global_solver_owned_physical_field_handoff(
          closure
        )
        coupled_inlet_profile = handoff.shock_front_condition.coupled_inlet_profile
      except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
        target_frame_failure = (
          'target-bound solver inlet frame construction failed: '
          f'{error}'
        )
      ####
    ####
    if coupled_inlet_profile is not None:
      target_solver_x_start_m = float(coupled_inlet_profile.cross_section_x_m)
      target_solver_lower_ordinate_m = float(
        coupled_inlet_profile.lower_ordinate_m
      )
    elif target_frame_failure is None:
      target_frame_failure = (
        'target-bound physical-field continuation retained no coupled inlet '
        'profile for exact station construction'
      )
    ####
  ####
  configuration = {
    'closure_fingerprint': closure.as_report()['closure_fingerprint'],
    'reference_total_temperature_K': float(reference_total_temperature_K),
    'ambient_pressure_Pa': ambient_pressure_Pa,
    'downstream_length_m': float(downstream_length_m),
    'initial_outlet_height_m': float(initial_outlet_height_m),
    'control_section_x_offset_m': float(control_section_x_offset_m),
    'control_section_height_m': float(control_section_height_m),
    'control_section_sample_count': int(control_section_sample_count),
    'max_pseudo_iterations': int(max_pseudo_iterations),
    'max_shape_iterations': int(max_shape_iterations),
    'inlet_boundary_mode': inlet_boundary_mode.value,
    'outlet_static_pressure_Pa': outlet_static_pressure_Pa,
    'resolutions': requested_resolutions,
    'boundary_target': (
      None
      if boundary_pressure_target is None
      else boundary_pressure_target.as_report()
    ),
    'target_profile_policy': (
      'unbound-baseline-v1'
      if boundary_pressure_target is None
      else 'typed-target-cell-centers-and-boundary-nodes-no-extrapolation-v1'
    ),
    'target_solver_inlet_frame': (
      None
      if boundary_pressure_target is None
      else {
        'x_start_m': target_solver_x_start_m,
        'lower_ordinate_m': target_solver_lower_ordinate_m,
      }
    ),
    'upstream_feedback_proposal_policy': (
      'bounded-global-resolve-handoff-unconsumed-v1'
    ),
  }
  configuration_fingerprint = sha256(
    json.dumps(
      configuration,
      sort_keys=True,
      separators=(',', ':'),
      default=str,
    ).encode('utf-8')
  ).hexdigest()
  cases: list[MocReflectedDomainGlobalCoupledDownstreamRefinementCase] = []
  fresh_solver_invocations: list[bool] = []
  for resolution in requested_resolutions:
    boundary_pressure_profile = None
    boundary_geometry_profile = None
    target_profile_failure: str | None = None
    if boundary_pressure_target is not None:
      if target_frame_failure is not None:
        target_profile_failure = target_frame_failure
      else:
        try:
          boundary_pressure_profile, boundary_geometry_profile = (
            _target_bound_profiles_for_resolution(
              closure,
              boundary_pressure_target,
              resolution=resolution,
              ambient_pressure_Pa=ambient_pressure_Pa,
              downstream_length_m=downstream_length_m,
              initial_outlet_height_m=initial_outlet_height_m,
              control_section_x_offset_m=control_section_x_offset_m,
              control_section_height_m=control_section_height_m,
              control_section_sample_count=control_section_sample_count,
              solver_inlet_x_start_m=target_solver_x_start_m,
              solver_inlet_lower_ordinate_m=target_solver_lower_ordinate_m,
            )
          )
        except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
          target_profile_failure = f'target-bound profile construction failed: {error}'
        ####
      ####
    ####
    try:
      if target_profile_failure is not None:
        result = _failed_result(closure, target_profile_failure)
        fresh_solver_invocations.append(False)
      else:
        result = solve_reflected_domain_global_coupled_downstream(
          closure,
          reference_total_temperature_K=reference_total_temperature_K,
          ambient_pressure_Pa=ambient_pressure_Pa,
          downstream_length_m=downstream_length_m,
          initial_outlet_height_m=initial_outlet_height_m,
          control_section_x_offset_m=control_section_x_offset_m,
          control_section_height_m=control_section_height_m,
          control_section_sample_count=control_section_sample_count,
          axial_station_count=resolution[0],
          axial_cell_count=resolution[0],
          transverse_cell_count=resolution[1],
          max_pseudo_iterations=max_pseudo_iterations,
          max_shape_iterations=max_shape_iterations,
          inlet_boundary_mode=inlet_boundary_mode,
          outlet_static_pressure_Pa=outlet_static_pressure_Pa,
          physical_field_continuation_profile=physical_field_continuation_profile,
          physical_field_shock_front_condition=physical_field_shock_front_condition,
          boundary_pressure_profile=boundary_pressure_profile,
          boundary_geometry_profile=boundary_geometry_profile,
        )
        fresh_solver_invocations.append(True)
      ####
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      result = _failed_result(
        closure,
        f'fresh global/coupled downstream solve raised: {error}',
      )
      fresh_solver_invocations.append(False)
    ####
    solver_response = result.downstream_boundary_response
    response = None
    if result.coupled_field is not None:
      try:
        response = measure_reflected_domain_global_coupled_downstream_boundary_response(
          closure,
          result.coupled_field,
        )
      except (ArithmeticError, FloatingPointError, TypeError, ValueError):
        response = None
      ####
    ####
    upstream_feedback_proposal = None
    if response is not None:
      try:
        upstream_feedback_proposal = (
          build_reflected_domain_global_coupled_downstream_upstream_feedback_proposal(
            closure,
            response,
          )
        )
      except (ArithmeticError, FloatingPointError, TypeError, ValueError):
        upstream_feedback_proposal = None
      ####
    ####
    response_lineage_verified = bool(
      solver_response is not None
      and response is not None
      and solver_response.as_report() == response.as_report()
    )
    target_lineage_verified = bool(
      boundary_pressure_target is None
      or _target_bound_lineage_verified(
        closure,
        boundary_pressure_target,
        result,
      )
    )
    target_profiles_consumed_verified = bool(
      boundary_pressure_target is None
      or _target_bound_profiles_consumed_verified(result)
    )
    cases.append(
      MocReflectedDomainGlobalCoupledDownstreamRefinementCase(
        resolution=resolution,
        result=result,
        solver_response=solver_response,
        response=response,
        upstream_feedback_proposal=upstream_feedback_proposal,
        response_lineage_verified=response_lineage_verified,
        boundary_target=boundary_pressure_target,
        target_lineage_verified=target_lineage_verified,
        target_profiles_consumed_verified=target_profiles_consumed_verified,
      )
    )
  ####
  retained_cases = tuple(cases)
  measurement = measure_reflected_domain_global_coupled_downstream_refinement(
    retained_cases
  )
  fidelity_isolation_verified = all(
    case.fidelity_isolation_verified for case in retained_cases
  )
  return MocReflectedDomainGlobalCoupledDownstreamRefinementRun(
    closure=closure,
    requested_resolutions=requested_resolutions,
    cases=retained_cases,
    measurement=measurement,
    configuration=configuration,
    configuration_fingerprint=configuration_fingerprint,
    fresh_solver_invocation_verified=(
      len(retained_cases) == len(requested_resolutions)
      and all(fresh_solver_invocations)
    ),
    fidelity_isolation_verified=fidelity_isolation_verified,
    message=(
      'fresh global/coupled downstream response refinement completed; '
      'global feedback, canonical boundary closure, physical chain promotion, '
      'and external validation remain separate gates'
    ),
  )
####


class MocReflectedDomainGlobalCoupledDownstreamCrossCaseStatus(str, Enum):
  """Outcome of independent coupled-downstream ladders across named cases."""

  CONVERGED_LOCAL_CROSS_CASE = (
    'converged-local-global-coupled-downstream-cross-case'
  )
  INVALID_INPUT = 'invalid_input'
  CASE_ID_FAILURE = 'global-coupled-downstream-cross-case-id-failure'
  CLOSURE_FAILURE = 'global-coupled-downstream-cross-case-closure-failure'
  RESOLUTION_FAILURE = (
    'global-coupled-downstream-cross-case-resolution-failure'
  )
  CASE_FAILURE = 'global-coupled-downstream-cross-case-case-failure'
  FIDELITY_FAILURE = 'global-coupled-downstream-cross-case-fidelity-failure'
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalCoupledDownstreamCrossCase:
  """One named closure with its own downstream resolution ladder.

  A cross-case study never treats physically distinct closures as adjacent
  mesh resolutions.  The case owns its closure fingerprint and ladder; the
  aggregate operator only checks identity, lineage, and each nested ladder's
  local result.
  """

  case_id: str
  regime: str
  closure: MocReflectedDomainGlobalPhysicalClosureResult
  resolutions: tuple[tuple[int, int], ...]
  boundary_target: MocPhysicalFieldEulerBoundaryPressureTarget | None = None

  def __post_init__(self) -> None:
    case_id = str(self.case_id)
    regime = str(self.regime)
    if not case_id:
      raise ValueError('case_id must be non-empty')
    ####
    if not regime:
      raise ValueError('regime must be non-empty')
    ####
    if not isinstance(
      self.closure,
      MocReflectedDomainGlobalPhysicalClosureResult,
    ):
      raise TypeError(
        'closure must be a MocReflectedDomainGlobalPhysicalClosureResult'
      )
    ####
    try:
      resolutions = tuple(tuple(value) for value in self.resolutions)
    except TypeError as error:
      raise ValueError(
        'resolutions must contain (axial, transverse) integer pairs'
      ) from error
    ####
    if not resolutions:
      raise ValueError('resolutions must not be empty')
    ####
    if any(
      len(resolution) != 2
      or any(
        isinstance(value, bool) or not isinstance(value, int)
        for value in resolution
      )
      or resolution[0] < 4
      or resolution[1] < 3
      for resolution in resolutions
    ):
      raise ValueError(
        'resolutions must contain (axial, transverse) integer pairs with '
        'axial >= 4 and transverse >= 3'
      )
    ####
    if self.boundary_target is not None and not isinstance(
      self.boundary_target,
      MocPhysicalFieldEulerBoundaryPressureTarget,
    ):
      raise TypeError(
        'boundary_target must be a '
        'MocPhysicalFieldEulerBoundaryPressureTarget or None'
      )
    ####
    object.__setattr__(self, 'case_id', case_id)
    object.__setattr__(self, 'regime', regime)
    object.__setattr__(self, 'resolutions', resolutions)
  ####

  @property
  def closure_fingerprint(self) -> str:
    """Return the exact physical-closure identity owned by this case."""

    return moc_reflected_domain_global_physical_closure_fingerprint(
      self.closure
    )
  ####

  @property
  def resolution_ladder_verified(self) -> bool:
    """Whether this case declares a strict two-or-more-point ladder."""

    return bool(
      len(self.resolutions) >= 2
      and all(
        right[0] > left[0] and right[1] > left[1]
        for left, right in zip(self.resolutions, self.resolutions[1:])
      )
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'case_id': self.case_id,
      'regime': self.regime,
      'closure_fingerprint': self.closure_fingerprint,
      'resolutions': self.resolutions,
      'resolution_ladder_verified': self.resolution_ladder_verified,
      'boundary_target': (
        None
        if self.boundary_target is None
        else self.boundary_target.as_report()
      ),
      'closure_status': self.closure.status.value,
      'closure_converged': self.closure.converged,
      'physical_closure_verified': self.closure.physical_closure_verified,
      'downstream_boundary_model': self.closure.downstream_boundary_model,
      'downstream_boundary_closure_verified': (
        self.closure.downstream_boundary_closure_verified
      ),
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalCoupledDownstreamCrossCaseMeasurement:
  """Independent aggregate evidence for distinct coupled-downstream cases."""

  status: MocReflectedDomainGlobalCoupledDownstreamCrossCaseStatus
  cases: tuple[MocReflectedDomainGlobalCoupledDownstreamCrossCase, ...] = ()
  runs: tuple[MocReflectedDomainGlobalCoupledDownstreamRefinementRun, ...] = ()
  case_ids: tuple[str, ...] = ()
  regimes: tuple[str, ...] = ()
  closure_fingerprints: tuple[str, ...] = ()
  requested_resolutions: tuple[tuple[tuple[int, int], ...], ...] = ()
  run_statuses: tuple[str, ...] = ()
  case_ids_verified: bool = False
  closure_bindings_verified: bool = False
  distinct_closure_fingerprints_verified: bool = False
  resolution_ladders_verified: bool = False
  target_bindings_verified: bool = False
  case_runs_verified: bool = False
  local_coupled_field_verified: bool = False
  fidelity_isolation_verified: bool = False
  global_coupling_verified: bool = False
  downstream_boundary_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  external_validation_required: bool = True
  message: str = ''
  operator_id: str = (
    MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_DOWNSTREAM_CROSS_CASE_REFINEMENT_OPERATOR_ID
  )

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalCoupledDownstreamCrossCaseStatus,
    ):
      raise TypeError(
        'status must be a '
        'MocReflectedDomainGlobalCoupledDownstreamCrossCaseStatus'
      )
    ####
    cases = tuple(self.cases)
    runs = tuple(self.runs)
    if len(cases) != len(runs):
      raise ValueError('cases and runs must have equal lengths')
    ####
    if any(
      not isinstance(
        case,
        MocReflectedDomainGlobalCoupledDownstreamCrossCase,
      )
      for case in cases
    ):
      raise TypeError(
        'cases must contain typed global/coupled downstream cross-case values'
      )
    ####
    if any(
      not isinstance(
        run,
        MocReflectedDomainGlobalCoupledDownstreamRefinementRun,
      )
      for run in runs
    ):
      raise TypeError(
        'runs must contain typed global/coupled downstream refinement runs'
      )
    ####
    object.__setattr__(self, 'cases', cases)
    object.__setattr__(self, 'runs', runs)
    derived_case_ids = tuple(case.case_id for case in cases)
    if self.case_ids and tuple(self.case_ids) != derived_case_ids:
      raise ValueError('case_ids must match the supplied cases')
    ####
    object.__setattr__(self, 'case_ids', derived_case_ids)
    derived_regimes = tuple(case.regime for case in cases)
    if self.regimes and tuple(self.regimes) != derived_regimes:
      raise ValueError('regimes must match the supplied cases')
    ####
    object.__setattr__(self, 'regimes', derived_regimes)
    derived_fingerprints = tuple(case.closure_fingerprint for case in cases)
    if (
      self.closure_fingerprints
      and tuple(self.closure_fingerprints) != derived_fingerprints
    ):
      raise ValueError(
        'closure_fingerprints must match the supplied cases'
      )
    ####
    object.__setattr__(self, 'closure_fingerprints', derived_fingerprints)
    derived_resolutions = tuple(case.resolutions for case in cases)
    if (
      self.requested_resolutions
      and tuple(tuple(value) for value in self.requested_resolutions)
      != derived_resolutions
    ):
      raise ValueError('requested_resolutions must match the supplied cases')
    ####
    object.__setattr__(self, 'requested_resolutions', derived_resolutions)
    derived_statuses = tuple(run.measurement.status.value for run in runs)
    if self.run_statuses and tuple(self.run_statuses) != derived_statuses:
      raise ValueError('run_statuses must match the supplied runs')
    ####
    object.__setattr__(self, 'run_statuses', derived_statuses)
    for name in (
      'case_ids_verified',
      'closure_bindings_verified',
      'distinct_closure_fingerprints_verified',
      'resolution_ladders_verified',
      'target_bindings_verified',
      'case_runs_verified',
      'local_coupled_field_verified',
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
        'cross-case downstream refinement cannot claim global or downstream closure'
      )
    ####
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError(
        'cross-case downstream refinement must retain its promotion block'
      )
    ####
    if not self.external_validation_required:
      raise ValueError(
        'cross-case downstream refinement must retain the external-validation gate'
      )
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status is (
      MocReflectedDomainGlobalCoupledDownstreamCrossCaseStatus
      .CONVERGED_LOCAL_CROSS_CASE
    )
  ####

  @property
  def local_consistency_verified(self) -> bool:
    return bool(
      self.converged
      and len(self.cases) >= 2
      and self.case_ids_verified
      and self.closure_bindings_verified
      and self.distinct_closure_fingerprints_verified
      and self.resolution_ladders_verified
      and self.target_bindings_verified
      and self.case_runs_verified
      and self.local_coupled_field_verified
      and self.fidelity_isolation_verified
      and self.external_validation_required
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
      'case_ids': self.case_ids,
      'regimes': self.regimes,
      'closure_fingerprints': self.closure_fingerprints,
      'requested_resolutions': self.requested_resolutions,
      'run_statuses': self.run_statuses,
      'cases': tuple(case.as_report() for case in self.cases),
      'runs': tuple(run.as_report() for run in self.runs),
      'checks': {
        'case_ids_verified': self.case_ids_verified,
        'closure_bindings_verified': self.closure_bindings_verified,
        'distinct_closure_fingerprints_verified': (
          self.distinct_closure_fingerprints_verified
        ),
        'resolution_ladders_verified': self.resolution_ladders_verified,
        'target_bindings_verified': self.target_bindings_verified,
        'case_runs_verified': self.case_runs_verified,
        'local_coupled_field_verified': self.local_coupled_field_verified,
        'fidelity_isolation_verified': self.fidelity_isolation_verified,
        'global_coupling_verified': self.global_coupling_verified,
        'downstream_boundary_closure_verified': (
          self.downstream_boundary_closure_verified
        ),
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
      'external_validation_required': self.external_validation_required,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'claim_status': (
        'independent-global-coupled-downstream-cross-case-refinement; '
        'local-research-field-only'
      ),
      'message': self.message,
    }
  ####
####


def _cross_case_measurement_failure(
  status: MocReflectedDomainGlobalCoupledDownstreamCrossCaseStatus,
  message: str,
  *,
  cases: Sequence[MocReflectedDomainGlobalCoupledDownstreamCrossCase] = (),
  runs: Sequence[MocReflectedDomainGlobalCoupledDownstreamRefinementRun] = (),
) -> MocReflectedDomainGlobalCoupledDownstreamCrossCaseMeasurement:
  case_values = tuple(cases)
  run_values = tuple(runs)
  paired = min(len(case_values), len(run_values))
  return MocReflectedDomainGlobalCoupledDownstreamCrossCaseMeasurement(
    status=status,
    cases=case_values[:paired],
    runs=run_values[:paired],
    message=message,
  )
####


def measure_reflected_domain_global_coupled_downstream_cross_case_refinement(
  cases: Sequence[MocReflectedDomainGlobalCoupledDownstreamCrossCase],
  runs: Sequence[MocReflectedDomainGlobalCoupledDownstreamRefinementRun],
  *,
  expected_case_ids: Sequence[str] | None = None,
) -> MocReflectedDomainGlobalCoupledDownstreamCrossCaseMeasurement:
  """Independently audit named coupled-downstream resolution ladders.

  The operator deliberately does not compare residual magnitudes between
  physically distinct cases.  It verifies that every nested run is bound to
  the exact case closure and retains its own ordered local ladder.
  """

  try:
    case_values = tuple(cases)
    run_values = tuple(runs)
  except TypeError:
    return _cross_case_measurement_failure(
      MocReflectedDomainGlobalCoupledDownstreamCrossCaseStatus.INVALID_INPUT,
      'cross-case cases and runs must be iterable',
    )
  ####
  if len(case_values) < 2 or len(run_values) < 2:
    return _cross_case_measurement_failure(
      MocReflectedDomainGlobalCoupledDownstreamCrossCaseStatus.INVALID_INPUT,
      'cross-case refinement requires at least two named cases',
    )
  ####
  if len(case_values) != len(run_values):
    return _cross_case_measurement_failure(
      MocReflectedDomainGlobalCoupledDownstreamCrossCaseStatus.INVALID_INPUT,
      'cross-case cases and runs must have equal lengths',
      cases=tuple(
        value for value in case_values
        if isinstance(value, MocReflectedDomainGlobalCoupledDownstreamCrossCase)
      ),
      runs=tuple(
        value for value in run_values
        if isinstance(
          value,
          MocReflectedDomainGlobalCoupledDownstreamRefinementRun,
        )
      ),
    )
  ####
  if any(
    not isinstance(
      case,
      MocReflectedDomainGlobalCoupledDownstreamCrossCase,
    )
    for case in case_values
  ):
    return _cross_case_measurement_failure(
      MocReflectedDomainGlobalCoupledDownstreamCrossCaseStatus.INVALID_INPUT,
      'cases must contain typed global/coupled downstream cross-case values',
    )
  ####
  if any(
    not isinstance(
      run,
      MocReflectedDomainGlobalCoupledDownstreamRefinementRun,
    )
    for run in run_values
  ):
    return _cross_case_measurement_failure(
      MocReflectedDomainGlobalCoupledDownstreamCrossCaseStatus.INVALID_INPUT,
      'runs must contain typed global/coupled downstream refinement runs',
    )
  ####
  case_ids = tuple(case.case_id for case in case_values)
  case_ids_verified = bool(
    len(set(case_ids)) == len(case_ids)
    and (
      expected_case_ids is None
      or case_ids == tuple(str(value) for value in expected_case_ids)
    )
  )
  closure_fingerprints = tuple(
    case.closure_fingerprint for case in case_values
  )
  closure_bindings_verified = all(
    run.closure is not None
    and moc_reflected_domain_global_physical_closure_fingerprint(run.closure)
    == fingerprint
    for case, run, fingerprint in zip(
      case_values,
      run_values,
      closure_fingerprints,
      strict=True,
    )
  )
  distinct_closure_fingerprints_verified = bool(
    len(set(closure_fingerprints)) == len(closure_fingerprints)
  )
  resolution_ladders_verified = bool(
    all(case.resolution_ladder_verified for case in case_values)
    and all(
      run.requested_resolutions == case.resolutions
      for case, run in zip(case_values, run_values, strict=True)
    )
  )
  target_bindings_verified = all(
    all(
      nested_case.boundary_target == case.boundary_target
      and (
        not case.boundary_target
        or nested_case.target_binding_verified
      )
      for nested_case in run.cases
    )
    for case, run in zip(case_values, run_values, strict=True)
  )
  case_runs_verified = all(
    run.converged and run.measurement.converged
    for run in run_values
  )
  local_coupled_field_verified = all(
    run.measurement.local_coupled_field_verified for run in run_values
  )
  fidelity_isolation_verified = all(
    run.fidelity_isolation_verified
    and run.measurement.chain_promotion_blocked
    and not run.measurement.production_claim_allowed
    for run in run_values
  )
  if not case_ids_verified:
    status = (
      MocReflectedDomainGlobalCoupledDownstreamCrossCaseStatus
      .CASE_ID_FAILURE
    )
    message = 'cross-case IDs are duplicated or do not match expected order'
  elif (
    not closure_bindings_verified
    or not distinct_closure_fingerprints_verified
  ):
    status = (
      MocReflectedDomainGlobalCoupledDownstreamCrossCaseStatus
      .CLOSURE_FAILURE
    )
    message = (
      'cross-case runs are not bound to distinct declared global-closure '
      'fingerprints'
    )
  elif not resolution_ladders_verified:
    status = (
      MocReflectedDomainGlobalCoupledDownstreamCrossCaseStatus
      .RESOLUTION_FAILURE
    )
    message = (
      'one or more named cases does not retain the same strict resolution '
      'ladder used by its run'
    )
  elif not target_bindings_verified:
    status = (
      MocReflectedDomainGlobalCoupledDownstreamCrossCaseStatus.CASE_FAILURE
    )
    message = (
      'one or more named cases did not retain its exact target binding or '
      'target-bound profile consumption across the nested ladder'
    )
  elif not case_runs_verified or not local_coupled_field_verified:
    status = (
      MocReflectedDomainGlobalCoupledDownstreamCrossCaseStatus.CASE_FAILURE
    )
    message = (
      'one or more named global/coupled downstream case ladders failed its '
      'local response audit'
    )
  elif not fidelity_isolation_verified:
    status = (
      MocReflectedDomainGlobalCoupledDownstreamCrossCaseStatus.FIDELITY_FAILURE
    )
    message = (
      'cross-case aggregation weakened the coupled-downstream fidelity or '
      'promotion boundary'
    )
  else:
    status = (
      MocReflectedDomainGlobalCoupledDownstreamCrossCaseStatus
      .CONVERGED_LOCAL_CROSS_CASE
    )
    message = (
      'named global/coupled downstream ladders passed independently; '
      'cross-case evidence remains local research evidence below canonical, '
      'physical shock-cell, and external promotion gates'
    )
  ####
  return MocReflectedDomainGlobalCoupledDownstreamCrossCaseMeasurement(
    status=status,
    cases=case_values,
    runs=run_values,
    case_ids=case_ids,
    regimes=tuple(case.regime for case in case_values),
    closure_fingerprints=closure_fingerprints,
    requested_resolutions=tuple(case.resolutions for case in case_values),
    run_statuses=tuple(run.measurement.status.value for run in run_values),
    case_ids_verified=case_ids_verified,
    closure_bindings_verified=closure_bindings_verified,
    distinct_closure_fingerprints_verified=(
      distinct_closure_fingerprints_verified
    ),
    resolution_ladders_verified=resolution_ladders_verified,
    target_bindings_verified=target_bindings_verified,
    case_runs_verified=case_runs_verified,
    local_coupled_field_verified=local_coupled_field_verified,
    fidelity_isolation_verified=fidelity_isolation_verified,
    message=message,
  )
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalCoupledDownstreamCrossCaseRun:
  """Fresh execution of every named coupled-downstream case ladder."""

  cases: tuple[MocReflectedDomainGlobalCoupledDownstreamCrossCase, ...]
  runs: tuple[MocReflectedDomainGlobalCoupledDownstreamRefinementRun, ...]
  measurement: MocReflectedDomainGlobalCoupledDownstreamCrossCaseMeasurement
  configuration: tuple[tuple[str, Any], ...]
  configuration_fingerprint: str
  fresh_solver_invocation_verified: bool
  local_coupled_field_verified: bool
  fidelity_isolation_verified: bool
  message: str = ''

  def __post_init__(self) -> None:
    cases = tuple(self.cases)
    runs = tuple(self.runs)
    if len(cases) != len(runs):
      raise ValueError('cases and runs must have equal lengths')
    ####
    if any(
      not isinstance(
        case,
        MocReflectedDomainGlobalCoupledDownstreamCrossCase,
      )
      for case in cases
    ):
      raise TypeError('cases must contain typed downstream cross-case values')
    ####
    if any(
      not isinstance(
        run,
        MocReflectedDomainGlobalCoupledDownstreamRefinementRun,
      )
      for run in runs
    ):
      raise TypeError('runs must contain typed downstream refinement runs')
    ####
    if not isinstance(
      self.measurement,
      MocReflectedDomainGlobalCoupledDownstreamCrossCaseMeasurement,
    ):
      raise TypeError('measurement must be a typed downstream cross-case measurement')
    ####
    if self.measurement.cases and tuple(self.measurement.cases) != cases:
      raise ValueError('measurement cases must match retained cross-case values')
    ####
    if self.measurement.runs and tuple(self.measurement.runs) != runs:
      raise ValueError('measurement runs must match retained run values')
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
    if len(fingerprint) != 64:
      raise ValueError('configuration_fingerprint must be a SHA-256 digest')
    ####
    for name in (
      'fresh_solver_invocation_verified',
      'local_coupled_field_verified',
      'fidelity_isolation_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    object.__setattr__(self, 'cases', cases)
    object.__setattr__(self, 'runs', runs)
    object.__setattr__(self, 'configuration', configuration)
    object.__setattr__(self, 'configuration_fingerprint', fingerprint)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.measurement.converged
      and self.fresh_solver_invocation_verified
      and self.local_coupled_field_verified
      and self.fidelity_isolation_verified
    )
  ####

  @property
  def local_consistency_verified(self) -> bool:
    return bool(
      self.measurement.local_consistency_verified
      and len(self.cases) >= 2
      and len(self.runs) == len(self.cases)
      and self.fresh_solver_invocation_verified
      and self.local_coupled_field_verified
      and self.fidelity_isolation_verified
    )
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    return bool(
      self.runs and all(run.measurement.chain_promotion_blocked for run in self.runs)
    )
  ####

  @property
  def production_claim_allowed(self) -> bool:
    return False
  ####

  @property
  def downstream_boundary_closure_verified(self) -> bool:
    return False
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.measurement.status.value,
      'operator_id': (
        MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_DOWNSTREAM_CROSS_CASE_REFINEMENT_RUN_OPERATOR_ID
      ),
      'converged': self.converged,
      'local_consistency_verified': self.local_consistency_verified,
      'configuration': dict(self.configuration),
      'configuration_fingerprint': self.configuration_fingerprint,
      'cases': tuple(case.as_report() for case in self.cases),
      'runs': tuple(run.as_report() for run in self.runs),
      'measurement': self.measurement.as_report(),
      'checks': {
        'fresh_solver_invocation_verified': self.fresh_solver_invocation_verified,
        'local_coupled_field_verified': self.local_coupled_field_verified,
        'fidelity_isolation_verified': self.fidelity_isolation_verified,
        'global_coupling_verified': False,
        'downstream_boundary_closure_verified': False,
        'canonical_free_boundary_verified': False,
        'canonical_euler_verified': False,
        'external_validation_verified': False,
        'chain_promotion_blocked': self.chain_promotion_blocked,
        'production_claim_allowed': self.production_claim_allowed,
      },
      'global_coupling_verified': False,
      'downstream_boundary_closure_verified': False,
      'canonical_free_boundary_verified': False,
      'canonical_euler_verified': False,
      'external_validation_verified': False,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'claim_status': (
        'fresh-global-coupled-downstream-cross-case-refinement; '
        'local-research-field-only'
      ),
      'message': self.message,
    }
  ####
####


def run_reflected_domain_global_coupled_downstream_cross_case_refinement(
  cases: Sequence[MocReflectedDomainGlobalCoupledDownstreamCrossCase],
  **runner_options: Any,
) -> MocReflectedDomainGlobalCoupledDownstreamCrossCaseRun:
  """Run every named closure through a separate fresh response ladder.

  The closure and resolution ladder belong to each case and cannot be
  overridden through ``runner_options``.  This prevents a cross-case study
  from silently reusing one physical placement or treating cases as one mesh
  sequence.
  """

  try:
    case_values = tuple(cases)
  except TypeError as error:
    raise ValueError('cases must be an iterable of typed cross-case values') from error
  ####
  if len(case_values) < 2:
    raise ValueError('cross-case refinement requires at least two named cases')
  ####
  if any(
    not isinstance(
      case,
      MocReflectedDomainGlobalCoupledDownstreamCrossCase,
    )
    for case in case_values
  ):
    raise TypeError('cases must contain typed global/coupled downstream cross-case values')
  ####
  forbidden = {'closure', 'resolutions', 'boundary_pressure_target'}
  if forbidden.intersection(runner_options):
    raise ValueError(
      'runner_options cannot override closure or resolutions owned by a case'
    )
  ####
  runs = tuple(
    run_reflected_domain_global_coupled_downstream_refinement(
      case.closure,
      resolutions=case.resolutions,
      boundary_pressure_target=case.boundary_target,
      **runner_options,
    )
    for case in case_values
  )
  measurement = (
    measure_reflected_domain_global_coupled_downstream_cross_case_refinement(
      case_values,
      runs,
    )
  )
  configuration_payload: dict[str, Any] = {
    'operator_id': (
      MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_DOWNSTREAM_CROSS_CASE_REFINEMENT_RUN_OPERATOR_ID
    ),
    'cases': [
      {
        'case_id': case.case_id,
        'regime': case.regime,
        'closure_fingerprint': case.closure_fingerprint,
        'resolutions': list(case.resolutions),
        'boundary_target': (
          None
          if case.boundary_target is None
          else case.boundary_target.as_report()
        ),
      }
      for case in case_values
    ],
    'runner_options': runner_options,
  }
  configuration = tuple(
    (name, configuration_payload[name])
    for name in sorted(configuration_payload)
  )
  configuration_fingerprint = sha256(
    json.dumps(
      configuration_payload,
      sort_keys=True,
      separators=(',', ':'),
      default=str,
    ).encode('utf-8')
  ).hexdigest()
  local_coupled_field_verified = bool(
    runs and all(run.measurement.local_coupled_field_verified for run in runs)
  )
  fidelity_isolation_verified = bool(
    runs
    and all(
      run.fidelity_isolation_verified
      and run.measurement.chain_promotion_blocked
      and not run.measurement.production_claim_allowed
      for run in runs
    )
  )
  return MocReflectedDomainGlobalCoupledDownstreamCrossCaseRun(
    cases=case_values,
    runs=runs,
    measurement=measurement,
    configuration=configuration,
    configuration_fingerprint=configuration_fingerprint,
    fresh_solver_invocation_verified=all(
      run.fresh_solver_invocation_verified for run in runs
    ),
    local_coupled_field_verified=local_coupled_field_verified,
    fidelity_isolation_verified=fidelity_isolation_verified,
    message=(
      'fresh global/coupled downstream ladders executed independently for '
      'every named closure; global feedback, canonical closure, physical '
      'shock-cell fitting, and external promotion gates remain pending'
    ),
  )
####
