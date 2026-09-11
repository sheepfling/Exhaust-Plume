"""Research-only downstream pressure/geometry-feedback iteration evidence.

The boundary-pressure consumer can now apply a measured downstream response to
another coupled solve.  This module makes that handoff repeatable across fresh
solver calls, records the exact profile lineage, and reports pressure-update
convergence separately from physical closure.  It never re-solves the upstream
global field and therefore cannot authorize a global-coupling or production
claim.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from math import isfinite
from typing import Any, Sequence

from exhaust_plume.models.moc.coupled_euler_free_boundary import (
  PHYSICAL_FIELD_EXACT_INITIAL_STATE_SOURCE,
  MocReflectedDomainCoupledEulerFreeBoundaryUpdateMode,
  MocReflectedDomainCoupledEulerInletBoundaryMode,
)
from exhaust_plume.models.moc.global_coupled_downstream import (
  MocReflectedDomainGlobalCoupledDownstreamBoundaryTrace,
  MocReflectedDomainGlobalCoupledDownstreamBoundaryGeometryProfile,
  MocReflectedDomainGlobalCoupledDownstreamBoundaryPressureProfile,
  MocReflectedDomainGlobalCoupledDownstreamBoundaryResponse,
  MocReflectedDomainGlobalCoupledDownstreamUpstreamFeedbackProposal,
  MocReflectedDomainGlobalCoupledDownstreamResult,
  MocReflectedDomainGlobalCoupledDownstreamStatus,
  build_reflected_domain_global_coupled_downstream_feedback_geometry_profile,
  build_reflected_domain_global_coupled_downstream_feedback_pressure_profile,
  build_reflected_domain_global_coupled_downstream_signed_free_boundary_pressure_profile,
  build_reflected_domain_global_coupled_downstream_signed_free_boundary_geometry_profile,
  build_reflected_domain_global_coupled_downstream_upstream_feedback_proposal,
  measure_reflected_domain_global_coupled_downstream_boundary_response,
  solve_reflected_domain_global_coupled_downstream,
)
from exhaust_plume.models.moc.global_physical_closure import (
  MocReflectedDomainGlobalPhysicalClosureResult,
  moc_reflected_domain_global_physical_closure_fingerprint,
)
from exhaust_plume.validation.moc_global_transonic_interface import (
  MocReflectedDomainGlobalTransonicInterfaceAudit,
  measure_reflected_domain_global_transonic_interface,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_DOWNSTREAM_FEEDBACK_OPERATOR_ID',
  'MocReflectedDomainGlobalCoupledDownstreamFeedbackStatus',
  'MocReflectedDomainGlobalCoupledDownstreamFeedbackIteration',
  'MocReflectedDomainGlobalCoupledDownstreamFeedbackRun',
  'run_reflected_domain_global_coupled_downstream_feedback',
  'MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_DOWNSTREAM_FEEDBACK_REFINEMENT_OPERATOR_ID',
  'MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_DOWNSTREAM_FEEDBACK_REFINEMENT_RUN_OPERATOR_ID',
  'MocReflectedDomainGlobalCoupledDownstreamFeedbackRefinementStatus',
  'MocReflectedDomainGlobalCoupledDownstreamFeedbackRefinementCase',
  'MocReflectedDomainGlobalCoupledDownstreamFeedbackRefinementCaseRun',
  'MocReflectedDomainGlobalCoupledDownstreamFeedbackRefinementMeasurement',
  'MocReflectedDomainGlobalCoupledDownstreamFeedbackRefinementRun',
  'measure_reflected_domain_global_coupled_downstream_feedback_refinement',
  'run_reflected_domain_global_coupled_downstream_feedback_refinement',
)


MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_DOWNSTREAM_FEEDBACK_OPERATOR_ID = (
  'op.moc.reflected-domain.global-coupled-downstream-feedback'
)
MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_DOWNSTREAM_FEEDBACK_REFINEMENT_OPERATOR_ID = (
  'op.moc.reflected-domain.global-coupled-downstream-feedback-refinement'
)
MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_DOWNSTREAM_FEEDBACK_REFINEMENT_RUN_OPERATOR_ID = (
  'op.moc.reflected-domain.global-coupled-downstream-feedback-refinement-run'
)
_PHYSICAL_FIELD_AMBIENT_NEIGHBOR_PRESSURE_PROFILE_SOURCE = (
  'solver-owned-physical-field-ambient-neighbor-pressure-profile-v1'
)
_PHYSICAL_FIELD_AMBIENT_NEIGHBOR_GEOMETRY_PROFILE_SOURCE = (
  'solver-owned-physical-field-ambient-neighbor-geometry-profile-v1'
)


class MocReflectedDomainGlobalCoupledDownstreamFeedbackStatus(str, Enum):
  """Outcome of a fresh downstream pressure/geometry feedback study."""

  CONVERGED_RESEARCH_PRESSURE_UPDATE = (
    'converged-research-global-coupled-downstream-pressure-update'
  )
  INVALID_INPUT = 'invalid_input'
  SOLVER_FAILURE = 'global-coupled-downstream-feedback-solver-failure'
  PROFILE_FAILURE = 'global-coupled-downstream-feedback-profile-failure'
  RESPONSE_FAILURE = 'global-coupled-downstream-feedback-response-failure'
  TRANSONIC_INTERFACE_FAILURE = (
    'global-coupled-downstream-feedback-transonic-interface-failure'
  )
  ITERATION_LIMIT = 'global-coupled-downstream-feedback-iteration-limit'
  FIDELITY_FAILURE = 'global-coupled-downstream-feedback-fidelity-failure'
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalCoupledDownstreamFeedbackIteration:
  """One fresh solve, independent response measure, and next profile."""

  iteration_index: int
  input_pressure_profile: (
    MocReflectedDomainGlobalCoupledDownstreamBoundaryPressureProfile | None
  )
  result: MocReflectedDomainGlobalCoupledDownstreamResult
  solver_response: MocReflectedDomainGlobalCoupledDownstreamBoundaryResponse | None
  response: MocReflectedDomainGlobalCoupledDownstreamBoundaryResponse | None
  boundary_trace: MocReflectedDomainGlobalCoupledDownstreamBoundaryTrace | None = None
  input_geometry_profile: (
    MocReflectedDomainGlobalCoupledDownstreamBoundaryGeometryProfile | None
  ) = None
  next_pressure_profile: (
    MocReflectedDomainGlobalCoupledDownstreamBoundaryPressureProfile | None
  ) = None
  next_geometry_profile: (
    MocReflectedDomainGlobalCoupledDownstreamBoundaryGeometryProfile | None
  ) = None
  upstream_feedback_proposal: (
    MocReflectedDomainGlobalCoupledDownstreamUpstreamFeedbackProposal | None
  ) = None
  transonic_interface_audit: (
    MocReflectedDomainGlobalTransonicInterfaceAudit | None
  ) = None
  maximum_pressure_update_Pa: float | None = None
  pressure_profile_lineage_verified: bool = False
  geometry_profile_lineage_verified: bool = False
  response_lineage_verified: bool = False
  boundary_trace_lineage_verified: bool = False
  boundary_trace_verified: bool = False
  pressure_profile_consumption_verified: bool = False
  geometry_profile_consumption_verified: bool = False
  initial_state_lineage_verified: bool = True

  def __post_init__(self) -> None:
    index = self.iteration_index
    if isinstance(index, bool) or not isinstance(index, int) or index < 0:
      raise ValueError('iteration_index must be a nonnegative integer')
    ####
    if self.input_pressure_profile is not None and not isinstance(
      self.input_pressure_profile,
      MocReflectedDomainGlobalCoupledDownstreamBoundaryPressureProfile,
    ):
      raise TypeError(
        'input_pressure_profile must be a typed downstream pressure profile '
        'or None'
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
          f'{name} must be a typed downstream boundary response or None'
        )
      ####
    ####
    if self.boundary_trace is not None and not isinstance(
      self.boundary_trace,
      MocReflectedDomainGlobalCoupledDownstreamBoundaryTrace,
    ):
      raise TypeError(
        'boundary_trace must be a typed coupled-Euler boundary trace or None'
      )
    ####
    if self.input_geometry_profile is not None and not isinstance(
      self.input_geometry_profile,
      MocReflectedDomainGlobalCoupledDownstreamBoundaryGeometryProfile,
    ):
      raise TypeError(
        'input_geometry_profile must be a typed downstream geometry profile '
        'or None'
      )
    ####
    if self.next_pressure_profile is not None and not isinstance(
      self.next_pressure_profile,
      MocReflectedDomainGlobalCoupledDownstreamBoundaryPressureProfile,
    ):
      raise TypeError(
        'next_pressure_profile must be a typed downstream pressure profile '
        'or None'
      )
    ####
    if self.next_geometry_profile is not None and not isinstance(
      self.next_geometry_profile,
      MocReflectedDomainGlobalCoupledDownstreamBoundaryGeometryProfile,
    ):
      raise TypeError(
        'next_geometry_profile must be a typed downstream geometry profile '
        'or None'
      )
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
    if self.transonic_interface_audit is not None and not isinstance(
      self.transonic_interface_audit,
      MocReflectedDomainGlobalTransonicInterfaceAudit,
    ):
      raise TypeError(
        'transonic_interface_audit must be a typed global transonic '
        'interface audit or None'
      )
    ####
    if self.maximum_pressure_update_Pa is not None:
      update = float(self.maximum_pressure_update_Pa)
      if not isfinite(update) or update < 0.0:
        raise ValueError(
          'maximum_pressure_update_Pa must be finite and nonnegative when '
          'supplied'
        )
      ####
      object.__setattr__(self, 'maximum_pressure_update_Pa', update)
    ####
    for name in (
      'pressure_profile_lineage_verified',
      'geometry_profile_lineage_verified',
      'response_lineage_verified',
      'boundary_trace_lineage_verified',
      'boundary_trace_verified',
      'pressure_profile_consumption_verified',
      'geometry_profile_consumption_verified',
      'initial_state_lineage_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    object.__setattr__(self, 'iteration_index', index)
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
  def response_channels_finite(self) -> bool:
    response = self.response
    if response is None:
      return False
    ####
    return all(
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
        response.free_boundary_signed_pressure_residuals_Pa,
        response.free_boundary_signed_normal_velocity_residuals_m_s,
      )
      for value in channel
    )
  ####

  @property
  def upstream_feedback_proposal_verified(self) -> bool:
    proposal = self.upstream_feedback_proposal
    return bool(
      proposal is not None
      and proposal.ready_for_global_resolve
      and proposal.source_response_status
      == (self.response.status.value if self.response is not None else '')
    )
  ####

  @property
  def transonic_interface_audit_verified(self) -> bool:
    """Whether an attached transonic seam audit passed independently."""

    return bool(
      self.transonic_interface_audit is None
      or self.transonic_interface_audit.converged
    )
  ####

  @property
  def fidelity_isolation_verified(self) -> bool:
    return bool(
      not self.result.global_coupling_verified
      and not self.result.downstream_boundary_closure_verified
      and self.result.chain_promotion_blocked
      and not self.result.production_claim_allowed
      and (
        self.input_pressure_profile is None
        or not self.input_pressure_profile.production_claim_allowed
      )
      and (
        self.next_pressure_profile is None
        or not self.next_pressure_profile.production_claim_allowed
      )
      and (
        self.input_geometry_profile is None
        or not self.input_geometry_profile.production_claim_allowed
      )
      and (
        self.next_geometry_profile is None
        or not self.next_geometry_profile.production_claim_allowed
      )
      and (
        self.response is None or not self.response.production_claim_allowed
      )
      and (
        self.boundary_trace is None
        or (
          not self.boundary_trace.canonical_free_boundary_verified
          and not self.boundary_trace.downstream_boundary_closure_verified
          and self.boundary_trace.chain_promotion_blocked
          and not self.boundary_trace.production_claim_allowed
        )
      )
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

  def as_report(self) -> dict[str, Any]:
    return {
      'iteration_index': self.iteration_index,
      'input_pressure_profile': (
        None
        if self.input_pressure_profile is None
        else self.input_pressure_profile.as_report()
      ),
      'input_geometry_profile': (
        None
        if self.input_geometry_profile is None
        else self.input_geometry_profile.as_report()
      ),
      'solver_status': self.result.status.value,
      'local_coupled_field_verified': self.local_coupled_field_verified,
      'pressure_profile_lineage_verified': self.pressure_profile_lineage_verified,
      'geometry_profile_lineage_verified': (
        self.geometry_profile_lineage_verified
      ),
      'response_lineage_verified': self.response_lineage_verified,
      'boundary_trace_lineage_verified': (
        self.boundary_trace_lineage_verified
      ),
      'boundary_trace_verified': self.boundary_trace_verified,
      'pressure_profile_consumption_verified': (
        self.pressure_profile_consumption_verified
      ),
      'geometry_profile_consumption_verified': (
        self.geometry_profile_consumption_verified
      ),
      'initial_state_lineage_verified': self.initial_state_lineage_verified,
      'response_coverage_verified': self.response_coverage_verified,
      'response_residuals_verified': self.response_residuals_verified,
      'response_channels_finite': self.response_channels_finite,
      'upstream_feedback_proposal_verified': (
        self.upstream_feedback_proposal_verified
      ),
      'transonic_interface_audit_verified': (
        self.transonic_interface_audit_verified
      ),
      'transonic_interface_audit': (
        None
        if self.transonic_interface_audit is None
        else self.transonic_interface_audit.as_report()
      ),
      'maximum_pressure_update_Pa': self.maximum_pressure_update_Pa,
      'next_pressure_profile': (
        None
        if self.next_pressure_profile is None
        else self.next_pressure_profile.as_report()
      ),
      'next_geometry_profile': (
        None
        if self.next_geometry_profile is None
        else self.next_geometry_profile.as_report()
      ),
      'upstream_feedback_proposal': (
        None
        if self.upstream_feedback_proposal is None
        else self.upstream_feedback_proposal.as_report()
      ),
      'fidelity_isolation_verified': self.fidelity_isolation_verified,
      'result': self.result.as_report(),
      'solver_response': (
        None if self.solver_response is None else self.solver_response.as_report()
      ),
      'response': None if self.response is None else self.response.as_report(),
      'boundary_trace': (
        None if self.boundary_trace is None else self.boundary_trace.as_report()
      ),
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalCoupledDownstreamFeedbackRun:
  """Audited downstream pressure/geometry updates below the global gate."""

  closure: MocReflectedDomainGlobalPhysicalClosureResult
  requested_iterations: int
  iterations: tuple[MocReflectedDomainGlobalCoupledDownstreamFeedbackIteration, ...]
  status: MocReflectedDomainGlobalCoupledDownstreamFeedbackStatus
  pressure_update_tolerance_Pa: float
  pressure_correction_fraction: float
  configuration: dict[str, Any]
  configuration_fingerprint: str
  transonic_interface_audit_required: bool = False
  transonic_interface_audit_verified: bool = True
  fresh_solver_invocation_verified: bool = False
  closure_lineage_verified: bool = False
  pressure_profile_lineage_verified: bool = False
  pressure_profile_alignment_verified: bool = False
  geometry_profile_lineage_verified: bool = False
  geometry_profile_alignment_verified: bool = False
  geometry_profile_consumption_verified: bool = False
  response_lineage_verified: bool = False
  response_channels_finite: bool = False
  response_coverage_verified: bool = False
  normal_velocity_residual_descent_required: bool = False
  normal_velocity_residual_descent_verified: bool = False
  response_residuals_verified: bool = False
  boundary_trace_verified: bool = False
  local_coupled_field_verified: bool = False
  initial_state_lineage_verified: bool = False
  pressure_update_convergence_verified: bool = False
  fidelity_isolation_verified: bool = False
  global_coupling_verified: bool = False
  downstream_boundary_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
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
    requested = self.requested_iterations
    if isinstance(requested, bool) or not isinstance(requested, int):
      raise TypeError('requested_iterations must be an integer')
    ####
    if requested < 2:
      raise ValueError('requested_iterations must be at least two')
    ####
    iterations = tuple(self.iterations)
    if any(
      not isinstance(
        item,
        MocReflectedDomainGlobalCoupledDownstreamFeedbackIteration,
      )
      for item in iterations
    ):
      raise TypeError('iterations must contain typed feedback iterations')
    ####
    if len(iterations) > requested:
      raise ValueError('iterations cannot exceed requested_iterations')
    ####
    if tuple(item.iteration_index for item in iterations) != tuple(
      range(len(iterations))
    ):
      raise ValueError('iterations must have contiguous zero-based indices')
    ####
    tolerance = float(self.pressure_update_tolerance_Pa)
    if not isfinite(tolerance) or tolerance <= 0.0:
      raise ValueError('pressure_update_tolerance_Pa must be finite and positive')
    ####
    fraction = float(self.pressure_correction_fraction)
    if not isfinite(fraction) or fraction <= 0.0 or fraction > 1.0:
      raise ValueError('pressure_correction_fraction must be in (0, 1]')
    ####
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalCoupledDownstreamFeedbackStatus,
    ):
      raise TypeError(
        'status must be a '
        'MocReflectedDomainGlobalCoupledDownstreamFeedbackStatus'
      )
    ####
    if len(self.configuration_fingerprint) != 64:
      raise ValueError('configuration_fingerprint must be a SHA-256 digest')
    ####
    for name in (
      'fresh_solver_invocation_verified',
      'closure_lineage_verified',
      'pressure_profile_lineage_verified',
      'pressure_profile_alignment_verified',
      'geometry_profile_lineage_verified',
      'geometry_profile_alignment_verified',
      'geometry_profile_consumption_verified',
      'response_lineage_verified',
      'response_channels_finite',
      'response_coverage_verified',
      'normal_velocity_residual_descent_required',
      'normal_velocity_residual_descent_verified',
      'response_residuals_verified',
      'boundary_trace_verified',
      'local_coupled_field_verified',
      'initial_state_lineage_verified',
      'pressure_update_convergence_verified',
      'fidelity_isolation_verified',
      'transonic_interface_audit_required',
      'transonic_interface_audit_verified',
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
        'downstream pressure feedback cannot claim global or boundary closure'
      )
    ####
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError(
        'downstream pressure feedback must retain its promotion block'
      )
    ####
    object.__setattr__(self, 'requested_iterations', requested)
    object.__setattr__(self, 'iterations', iterations)
    object.__setattr__(self, 'pressure_update_tolerance_Pa', tolerance)
    object.__setattr__(self, 'pressure_correction_fraction', fraction)
    object.__setattr__(self, 'configuration', dict(self.configuration))
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalCoupledDownstreamFeedbackStatus
      .CONVERGED_RESEARCH_PRESSURE_UPDATE
      and self.fresh_solver_invocation_verified
      and self.closure_lineage_verified
      and self.pressure_profile_lineage_verified
      and self.pressure_profile_alignment_verified
      and self.geometry_profile_lineage_verified
      and self.geometry_profile_alignment_verified
      and self.geometry_profile_consumption_verified
      and self.response_lineage_verified
      and self.response_channels_finite
      and self.response_coverage_verified
      and (
        not self.normal_velocity_residual_descent_required
        or self.normal_velocity_residual_descent_verified
      )
      and self.response_residuals_verified
      and self.boundary_trace_verified
      and self.local_coupled_field_verified
      and self.initial_state_lineage_verified
      and self.pressure_update_convergence_verified
      and self.fidelity_isolation_verified
      and self.transonic_interface_audit_verified
    )
  ####

  @property
  def pressure_update_converged(self) -> bool:
    """Whether the relaxed pressure profile itself reached its tolerance."""

    return self.pressure_update_convergence_verified
  ####

  @property
  def upstream_feedback_proposals(
    self,
  ) -> tuple[MocReflectedDomainGlobalCoupledDownstreamUpstreamFeedbackProposal, ...]:
    """Return the covered proposals retained by the feedback iterations."""

    return tuple(
      item.upstream_feedback_proposal
      for item in self.iterations
      if item.upstream_feedback_proposal is not None
    )
  ####

  @property
  def upstream_feedback_proposal_verified(self) -> bool:
    """Whether every measured covered response has a ready handoff packet."""

    measured_iterations = tuple(
      item for item in self.iterations if item.response is not None
    )
    return bool(
      measured_iterations
      and all(item.upstream_feedback_proposal_verified for item in measured_iterations)
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_DOWNSTREAM_FEEDBACK_OPERATOR_ID,
      'status': self.status.value,
      'converged': self.converged,
      'requested_iterations': self.requested_iterations,
      'fresh_solver_invocation_verified': self.fresh_solver_invocation_verified,
      'closure_lineage_verified': self.closure_lineage_verified,
      'pressure_profile_lineage_verified': self.pressure_profile_lineage_verified,
      'pressure_profile_alignment_verified': self.pressure_profile_alignment_verified,
      'geometry_profile_lineage_verified': self.geometry_profile_lineage_verified,
      'geometry_profile_alignment_verified': (
        self.geometry_profile_alignment_verified
      ),
      'geometry_profile_consumption_verified': (
        self.geometry_profile_consumption_verified
      ),
      'response_lineage_verified': self.response_lineage_verified,
      'response_channels_finite': self.response_channels_finite,
      'response_coverage_verified': self.response_coverage_verified,
      'normal_velocity_residual_descent_required': (
        self.normal_velocity_residual_descent_required
      ),
      'normal_velocity_residual_descent_verified': (
        self.normal_velocity_residual_descent_verified
      ),
      'response_residuals_verified': self.response_residuals_verified,
      'boundary_trace_verified': self.boundary_trace_verified,
      'upstream_feedback_proposal_verified': (
        self.upstream_feedback_proposal_verified
      ),
      'upstream_feedback_proposal_count': len(self.upstream_feedback_proposals),
      'local_coupled_field_verified': self.local_coupled_field_verified,
      'initial_state_lineage_verified': self.initial_state_lineage_verified,
      'transonic_interface_audit_required': (
        self.transonic_interface_audit_required
      ),
      'transonic_interface_audit_verified': (
        self.transonic_interface_audit_verified
      ),
      'pressure_update_convergence_verified': (
        self.pressure_update_convergence_verified
      ),
      'pressure_update_tolerance_Pa': self.pressure_update_tolerance_Pa,
      'pressure_correction_fraction': self.pressure_correction_fraction,
      'fidelity_isolation_verified': self.fidelity_isolation_verified,
      'global_coupling_verified': self.global_coupling_verified,
      'downstream_boundary_closure_verified': (
        self.downstream_boundary_closure_verified
      ),
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'configuration': self.configuration,
      'configuration_fingerprint': self.configuration_fingerprint,
      'iterations': tuple(item.as_report() for item in self.iterations),
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


def _solver_owned_neighbor_profile_consumed(
  result: MocReflectedDomainGlobalCoupledDownstreamResult,
  *,
  pressure: bool,
) -> bool:
  """Verify an exact-field profile materialized by the coupled solver."""

  request = result.coupled_request
  field = result.coupled_field
  audit = result.coupled_field_audit
  if request is None or field is None or audit is None:
    return False
  ####
  if request.inlet_boundary_mode is not (
    MocReflectedDomainCoupledEulerInletBoundaryMode
    .SOLVER_OWNED_PHYSICAL_FIELD_CONTINUATION_PROFILE
  ):
    return False
  ####
  if field.request is not request:
    return False
  ####
  if not getattr(audit, 'physical_field_neighbor_profiles_verified', False):
    return False
  ####
  if pressure:
    return bool(
      field.free_boundary_pressure_profile_consumed
      and request.free_boundary_pressure_profile_Pa is not None
      and request.free_boundary_pressure_profile_x_stations_m is not None
      and request.free_boundary_pressure_profile_source
      == _PHYSICAL_FIELD_AMBIENT_NEIGHBOR_PRESSURE_PROFILE_SOURCE
    )
  ####
  return bool(
    field.free_boundary_geometry_profile_consumed
    and request.free_boundary_geometry_profile_y_m is not None
    and request.free_boundary_geometry_profile_x_stations_m is not None
    and request.free_boundary_geometry_profile_source
    == _PHYSICAL_FIELD_AMBIENT_NEIGHBOR_GEOMETRY_PROFILE_SOURCE
  )
####


def _profiles_aligned(
  first: MocReflectedDomainGlobalCoupledDownstreamBoundaryPressureProfile,
  second: MocReflectedDomainGlobalCoupledDownstreamBoundaryPressureProfile,
  *,
  position_tolerance_m: float,
) -> bool:
  return bool(
    first.source_closure_fingerprint == second.source_closure_fingerprint
    and len(first.x_stations_m) == len(second.x_stations_m)
    and all(
      abs(left - right) <= position_tolerance_m
      for left, right in zip(first.x_stations_m, second.x_stations_m)
    )
  )
####


def _geometry_profiles_aligned(
  first: MocReflectedDomainGlobalCoupledDownstreamBoundaryGeometryProfile,
  second: MocReflectedDomainGlobalCoupledDownstreamBoundaryGeometryProfile,
  *,
  position_tolerance_m: float,
) -> bool:
  """Verify geometry profiles retain the same exact boundary-node stations."""

  return bool(
    first.source_closure_fingerprint == second.source_closure_fingerprint
    and len(first.x_stations_m) == len(second.x_stations_m)
    and all(
      abs(left - right) <= position_tolerance_m
      for left, right in zip(first.x_stations_m, second.x_stations_m)
    )
  )
####


def _maximum_profile_update(
  first: MocReflectedDomainGlobalCoupledDownstreamBoundaryPressureProfile,
  second: MocReflectedDomainGlobalCoupledDownstreamBoundaryPressureProfile,
) -> float:
  if len(first.pressure_Pa) != len(second.pressure_Pa):
    return float('inf')
  ####
  return max(
    (abs(left - right) for left, right in zip(first.pressure_Pa, second.pressure_Pa)),
    default=float('inf'),
  )
####


def _strict_normal_velocity_residual_descent(
  before: float,
  after: float,
) -> bool:
  """Require a finite, strictly smaller fresh normal-response residual."""

  before_value = float(before)
  after_value = float(after)
  return bool(
    isfinite(before_value)
    and isfinite(after_value)
    and before_value >= 0.0
    and after_value >= 0.0
    and after_value < before_value
  )
####


def _normal_velocity_residual_descent_verified(
  iterations: tuple[MocReflectedDomainGlobalCoupledDownstreamFeedbackIteration, ...],
  *,
  required: bool,
) -> bool:
  """Audit strict descent across consecutive fresh downstream responses."""

  if not required:
    return True
  ####
  responses = tuple(
    item.response for item in iterations if item.response is not None
  )
  if len(responses) < 2:
    return False
  ####
  return all(
    _strict_normal_velocity_residual_descent(
      before.maximum_normal_velocity_residual_m_s,
      after.maximum_normal_velocity_residual_m_s,
    )
    for before, after in zip(responses, responses[1:])
  )
####


def _status_for_run(
  *,
  iterations: tuple[MocReflectedDomainGlobalCoupledDownstreamFeedbackIteration, ...],
  fresh_solver_invocation_verified: bool,
  closure_lineage_verified: bool,
  pressure_profile_lineage_verified: bool,
  pressure_profile_alignment_verified: bool,
  geometry_profile_lineage_verified: bool,
  geometry_profile_alignment_verified: bool,
  geometry_profile_consumption_verified: bool,
  response_lineage_verified: bool,
  response_channels_finite: bool,
  response_coverage_verified: bool,
  normal_velocity_residual_descent_required: bool,
  normal_velocity_residual_descent_verified: bool,
  response_residuals_verified: bool,
  boundary_trace_verified: bool,
  local_coupled_field_verified: bool,
  initial_state_lineage_verified: bool,
  pressure_update_convergence_verified: bool,
  fidelity_isolation_verified: bool,
  transonic_interface_audit_verified: bool,
) -> tuple[MocReflectedDomainGlobalCoupledDownstreamFeedbackStatus, str]:
  if not transonic_interface_audit_verified:
    return (
      MocReflectedDomainGlobalCoupledDownstreamFeedbackStatus
      .TRANSONIC_INTERFACE_FAILURE,
      'the solver-owned transonic interface placement or inlet seam failed '
      'its independent audit; no lower-fidelity fallback was attempted',
    )
  ####
  if not fresh_solver_invocation_verified or not local_coupled_field_verified:
    return (
      MocReflectedDomainGlobalCoupledDownstreamFeedbackStatus.SOLVER_FAILURE,
      'the feedback ladder did not retain a locally audited fresh coupled '
      'field for every attempted step',
    )
  ####
  if not boundary_trace_verified:
    return (
      MocReflectedDomainGlobalCoupledDownstreamFeedbackStatus.SOLVER_FAILURE,
      'the feedback ladder did not retain a locally audited full-state '
      'coupled-Euler boundary trace for every attempted step',
    )
  ####
  if not initial_state_lineage_verified:
    return (
      MocReflectedDomainGlobalCoupledDownstreamFeedbackStatus.FIDELITY_FAILURE,
      'exact physical-field feedback iterations did not retain the solver-owned '
      'initial-state lineage',
    )
  ####
  if not fidelity_isolation_verified:
    return (
      MocReflectedDomainGlobalCoupledDownstreamFeedbackStatus.FIDELITY_FAILURE,
      'a feedback iteration changed the global or production claim ceiling',
    )
  ####
  if not (
    closure_lineage_verified
    and pressure_profile_lineage_verified
    and pressure_profile_alignment_verified
    and geometry_profile_lineage_verified
    and geometry_profile_alignment_verified
    and geometry_profile_consumption_verified
  ):
    return (
      MocReflectedDomainGlobalCoupledDownstreamFeedbackStatus.PROFILE_FAILURE,
      'pressure/geometry profile lineage or exact solver-station alignment '
      'was not verified across the feedback steps',
    )
  ####
  if not (
    response_lineage_verified
    and response_channels_finite
    and response_coverage_verified
  ):
    return (
      MocReflectedDomainGlobalCoupledDownstreamFeedbackStatus.RESPONSE_FAILURE,
      'the independently measured downstream response is incomplete or '
      'cannot be tied to the solver-retained response',
    )
  ####
  if (
    normal_velocity_residual_descent_required
    and not normal_velocity_residual_descent_verified
  ):
    return (
      MocReflectedDomainGlobalCoupledDownstreamFeedbackStatus.RESPONSE_FAILURE,
      'signed geometry feedback did not produce strict fresh normal-velocity '
      'residual descent; no profile step was promoted',
    )
  ####
  if not pressure_update_convergence_verified:
    return (
      MocReflectedDomainGlobalCoupledDownstreamFeedbackStatus.ITERATION_LIMIT,
      'the bounded feedback ladder reached its iteration limit before the '
      'relaxed pressure update tolerance was met',
    )
  ####
  if not response_residuals_verified:
    return (
      MocReflectedDomainGlobalCoupledDownstreamFeedbackStatus.RESPONSE_FAILURE,
      'the pressure update reached a research fixed point, but the retained '
      'global/coupled overlap residual gate remains open',
    )
  ####
  return (
    MocReflectedDomainGlobalCoupledDownstreamFeedbackStatus
    .CONVERGED_RESEARCH_PRESSURE_UPDATE,
    'fresh downstream pressure feedback reached its declared research '
    'tolerance; upstream global feedback, canonical closure, external '
    'validation, and production promotion remain closed',
  )
####


def run_reflected_domain_global_coupled_downstream_feedback(
  closure: MocReflectedDomainGlobalPhysicalClosureResult,
  *,
  reference_total_temperature_K: float,
  maximum_iterations: int = 3,
  pressure_correction_fraction: float = 0.25,
  use_signed_free_boundary_pressure_response: bool = False,
  use_signed_free_boundary_geometry_response: bool = False,
  signed_normal_response_time_s: float | None = None,
  geometry_correction_fraction: float = 0.25,
  signed_normal_max_displacement_fraction: float = 0.25,
  pressure_update_tolerance_Pa: float = 1.0e3,
  position_tolerance_m: float = 1.0e-9,
  ambient_pressure_Pa: float | None = None,
  downstream_length_m: float = 0.2,
  initial_outlet_height_m: float = 0.05,
  control_section_x_offset_m: float = 0.02,
  control_section_height_m: float = 0.05,
  control_section_sample_count: int = 4,
  axial_station_count: int = 7,
  axial_cell_count: int = 12,
  transverse_cell_count: int = 6,
  max_pseudo_iterations: int = 1200,
  max_shape_iterations: int = 18,
  shape_relaxation: float = 0.35,
  pressure_shape_relaxation: float = 0.20,
  free_boundary_update_mode: MocReflectedDomainCoupledEulerFreeBoundaryUpdateMode = (
    MocReflectedDomainCoupledEulerFreeBoundaryUpdateMode.PRESSURE_SLOPE_RESEARCH
  ),
  inlet_boundary_mode: MocReflectedDomainCoupledEulerInletBoundaryMode = (
    MocReflectedDomainCoupledEulerInletBoundaryMode.FULL_STATE_RUSANOV
  ),
  outlet_static_pressure_Pa: float | None = None,
  physical_field_continuation_profile: Any | None = None,
  physical_field_shock_front_condition: Any | None = None,
) -> MocReflectedDomainGlobalCoupledDownstreamFeedbackRun:
  """Run bounded pressure/geometry feedback without an upstream re-solve."""

  if not isinstance(closure, MocReflectedDomainGlobalPhysicalClosureResult):
    raise TypeError(
      'closure must be a MocReflectedDomainGlobalPhysicalClosureResult'
    )
  ####
  if isinstance(maximum_iterations, bool) or not isinstance(
    maximum_iterations,
    int,
  ):
    raise TypeError('maximum_iterations must be an integer')
  ####
  if maximum_iterations < 2:
    raise ValueError('maximum_iterations must be at least two')
  ####
  fraction = float(pressure_correction_fraction)
  if not isfinite(fraction) or fraction <= 0.0 or fraction > 1.0:
    raise ValueError('pressure_correction_fraction must be in (0, 1]')
  ####
  if not isinstance(use_signed_free_boundary_pressure_response, bool):
    raise TypeError('use_signed_free_boundary_pressure_response must be a bool')
  ####
  if not isinstance(use_signed_free_boundary_geometry_response, bool):
    raise TypeError('use_signed_free_boundary_geometry_response must be a bool')
  ####
  if not isinstance(
    free_boundary_update_mode,
    MocReflectedDomainCoupledEulerFreeBoundaryUpdateMode,
  ):
    raise TypeError(
      'free_boundary_update_mode must be a '
      'MocReflectedDomainCoupledEulerFreeBoundaryUpdateMode'
    )
  ####
  kinematic_update_mode = free_boundary_update_mode is (
    MocReflectedDomainCoupledEulerFreeBoundaryUpdateMode.KINEMATIC_STREAMLINE
  )
  if kinematic_update_mode and use_signed_free_boundary_geometry_response:
    raise ValueError(
      'kinematic-streamline free-boundary updates cannot consume a signed '
      'geometry feedback profile'
    )
  ####
  response_time = (
    None
    if signed_normal_response_time_s is None
    else float(signed_normal_response_time_s)
  )
  if use_signed_free_boundary_geometry_response and (
    response_time is None
    or not isfinite(response_time)
    or response_time <= 0.0
  ):
    raise ValueError(
      'signed_normal_response_time_s must be finite and positive when signed '
      'free-boundary geometry response is enabled'
    )
  ####
  if response_time is not None and (
    not isfinite(response_time) or response_time <= 0.0
  ):
    raise ValueError(
      'signed_normal_response_time_s must be finite and positive when supplied'
    )
  ####
  geometry_fraction = float(geometry_correction_fraction)
  if not isfinite(geometry_fraction) or geometry_fraction <= 0.0 or geometry_fraction > 1.0:
    raise ValueError('geometry_correction_fraction must be in (0, 1]')
  ####
  maximum_geometry_fraction = float(signed_normal_max_displacement_fraction)
  if (
    not isfinite(maximum_geometry_fraction)
    or maximum_geometry_fraction <= 0.0
    or maximum_geometry_fraction > 1.0
  ):
    raise ValueError(
      'signed_normal_max_displacement_fraction must be in (0, 1]'
    )
  ####
  update_tolerance = float(pressure_update_tolerance_Pa)
  if not isfinite(update_tolerance) or update_tolerance <= 0.0:
    raise ValueError('pressure_update_tolerance_Pa must be finite and positive')
  ####
  position_tolerance = float(position_tolerance_m)
  if not isfinite(position_tolerance) or position_tolerance <= 0.0:
    raise ValueError('position_tolerance_m must be finite and positive')
  ####
  transonic_interface_audit_required = inlet_boundary_mode is (
    MocReflectedDomainCoupledEulerInletBoundaryMode
    .SOLVER_OWNED_INTERIOR_SHOCK_INTERFACE_PROFILE
  )
  configuration = {
    'closure_fingerprint': moc_reflected_domain_global_physical_closure_fingerprint(
      closure
    ),
    'reference_total_temperature_K': float(reference_total_temperature_K),
    'maximum_iterations': maximum_iterations,
    'pressure_correction_fraction': fraction,
    'use_signed_free_boundary_pressure_response': (
      use_signed_free_boundary_pressure_response
    ),
    'use_signed_free_boundary_geometry_response': (
      use_signed_free_boundary_geometry_response
    ),
    'signed_normal_response_time_s': response_time,
    'geometry_correction_fraction': geometry_fraction,
    'signed_normal_max_displacement_fraction': maximum_geometry_fraction,
    'normal_velocity_residual_descent_policy': (
      'strict-fresh-response-descent-required-v1'
      if use_signed_free_boundary_geometry_response
      else 'not-required-for-selected-geometry-response-mode-v1'
    ),
    'pressure_update_tolerance_Pa': update_tolerance,
    'position_tolerance_m': position_tolerance,
    'ambient_pressure_Pa': ambient_pressure_Pa,
    'downstream_length_m': float(downstream_length_m),
    'initial_outlet_height_m': float(initial_outlet_height_m),
    'control_section_x_offset_m': float(control_section_x_offset_m),
    'control_section_height_m': float(control_section_height_m),
    'control_section_sample_count': int(control_section_sample_count),
    'axial_station_count': int(axial_station_count),
    'axial_cell_count': int(axial_cell_count),
    'transverse_cell_count': int(transverse_cell_count),
    'max_pseudo_iterations': int(max_pseudo_iterations),
    'max_shape_iterations': int(max_shape_iterations),
    'shape_relaxation': float(shape_relaxation),
    'pressure_shape_relaxation': float(pressure_shape_relaxation),
    'free_boundary_update_mode': free_boundary_update_mode.value,
    'geometry_update_policy': (
      'solver-owned-kinematic-tangent-no-overlay-v1'
      if kinematic_update_mode
      else 'bounded-response-geometry-profile-v1'
    ),
    'inlet_boundary_mode': inlet_boundary_mode.value,
    'transonic_interface_audit_policy': (
      'independent-global-transonic-interface-seam-required-v1'
      if transonic_interface_audit_required
      else 'not-applicable-for-selected-inlet-mode-v1'
    ),
    'geometry_feedback_frame_policy': (
      'solver-owned-first-ordinate-anchor-v1'
    ),
    'upstream_feedback_proposal_policy': (
      'bounded-global-resolve-handoff-unconsumed-v1'
    ),
    'outlet_static_pressure_Pa': outlet_static_pressure_Pa,
    'physical_field_continuation_profile_supplied': (
      physical_field_continuation_profile is not None
    ),
    'physical_field_shock_front_condition_supplied': (
      physical_field_shock_front_condition is not None
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
  iterations: list[
    MocReflectedDomainGlobalCoupledDownstreamFeedbackIteration
  ] = []
  input_profile: (
    MocReflectedDomainGlobalCoupledDownstreamBoundaryPressureProfile | None
  ) = None
  input_geometry_profile: (
    MocReflectedDomainGlobalCoupledDownstreamBoundaryGeometryProfile | None
  ) = None
  pressure_update_convergence_verified = False
  initial_state_lineage_verified = True
  pressure_profile_alignment_verified = True
  geometry_profile_alignment_verified = True
  stop_reason: str | None = None
  for iteration_index in range(maximum_iterations):
    try:
      result = solve_reflected_domain_global_coupled_downstream(
        closure,
        reference_total_temperature_K=reference_total_temperature_K,
        ambient_pressure_Pa=ambient_pressure_Pa,
        downstream_length_m=downstream_length_m,
        initial_outlet_height_m=initial_outlet_height_m,
        control_section_x_offset_m=control_section_x_offset_m,
        control_section_height_m=control_section_height_m,
        control_section_sample_count=control_section_sample_count,
        axial_station_count=axial_station_count,
        axial_cell_count=axial_cell_count,
        transverse_cell_count=transverse_cell_count,
        shape_relaxation=shape_relaxation,
        pressure_shape_relaxation=pressure_shape_relaxation,
        free_boundary_update_mode=free_boundary_update_mode,
        max_pseudo_iterations=max_pseudo_iterations,
        max_shape_iterations=max_shape_iterations,
        inlet_boundary_mode=inlet_boundary_mode,
        outlet_static_pressure_Pa=outlet_static_pressure_Pa,
        physical_field_continuation_profile=physical_field_continuation_profile,
        physical_field_shock_front_condition=physical_field_shock_front_condition,
        boundary_pressure_profile=input_profile,
        boundary_geometry_profile=input_geometry_profile,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      result = _failed_result(
        closure,
        f'fresh global/coupled downstream feedback solve raised: {error}',
      )
    ####
    transonic_interface_audit = None
    iteration_transonic_interface_audit_verified = True
    if transonic_interface_audit_required:
      try:
        transonic_interface_audit = (
          measure_reflected_domain_global_transonic_interface(result)
        )
      except (ArithmeticError, FloatingPointError, TypeError, ValueError):
        transonic_interface_audit = None
      ####
      iteration_transonic_interface_audit_verified = bool(
        transonic_interface_audit is not None
        and transonic_interface_audit.converged
      )
      if not iteration_transonic_interface_audit_verified:
        stop_reason = (
          'solver-owned transonic interface placement or inlet seam failed '
          'its independent audit; no lower-fidelity fallback was attempted'
        )
      ####
    ####
    solver_response = result.downstream_boundary_response
    boundary_trace = result.downstream_boundary_trace
    boundary_trace_lineage_verified = bool(
      result.closure_lineage_verified
      and boundary_trace is not None
      and boundary_trace.source_closure_fingerprint
      == moc_reflected_domain_global_physical_closure_fingerprint(closure)
    )
    boundary_trace_verified = bool(
      boundary_trace_lineage_verified
      and boundary_trace is not None
      and boundary_trace.local_trace_verified
    )
    response = None
    if result.coupled_field is not None:
      try:
        response = measure_reflected_domain_global_coupled_downstream_boundary_response(
          closure,
          result.coupled_field,
          position_tolerance_m=position_tolerance,
        )
      except (ArithmeticError, FloatingPointError, TypeError, ValueError):
        response = None
      ####
    ####
    iteration_initial_state_lineage_verified = True
    if inlet_boundary_mode is (
      MocReflectedDomainCoupledEulerInletBoundaryMode
      .SOLVER_OWNED_PHYSICAL_FIELD_CONTINUATION_PROFILE
    ) or inlet_boundary_mode is (
      MocReflectedDomainCoupledEulerInletBoundaryMode
      .SOLVER_OWNED_PHYSICAL_FIELD_AMBIENT_PRESSURE_FREE_BOUNDARY
    ):
      field = result.coupled_field
      iteration_initial_state_lineage_verified = bool(
        field is not None
        and field.initial_state_field_bound
        and field.initial_state_source == PHYSICAL_FIELD_EXACT_INITIAL_STATE_SOURCE
      )
      if not iteration_initial_state_lineage_verified:
        initial_state_lineage_verified = False
        stop_reason = (
          'exact physical-field feedback iteration did not retain the '
          'solver-owned exact initial-state source'
        )
      ####
    ####
    response_lineage_verified = bool(
      solver_response is not None
      and response is not None
      and solver_response.as_report() == response.as_report()
    )
    next_profile = None
    next_geometry_profile = None
    upstream_feedback_proposal = None
    pressure_profile_lineage_verified = bool(
      result.closure_lineage_verified
      and (
        input_profile is None
        or result.boundary_pressure_profile == input_profile
      )
    )
    pressure_profile_consumption_verified = bool(
      (
        input_profile is None
        and result.boundary_pressure_profile is None
        and (
          result.coupled_request is None
          or (
            result.coupled_request.free_boundary_pressure_profile_Pa is None
            and result.coupled_request.free_boundary_pressure_profile_x_stations_m
            is None
            and result.coupled_request.free_boundary_pressure_profile_source
            is None
          )
        )
        or (
          input_profile is None
          and result.boundary_pressure_profile is None
          and _solver_owned_neighbor_profile_consumed(result, pressure=True)
        )
      )
      or (
        input_profile is not None
        and result.boundary_pressure_profile == input_profile
        and result.coupled_field is not None
        and result.coupled_field.free_boundary_pressure_profile_consumed
      )
    )
    geometry_profile_lineage_verified = bool(
      result.closure_lineage_verified
      and (
        input_geometry_profile is None
        or result.boundary_geometry_profile == input_geometry_profile
      )
    )
    geometry_profile_consumption_verified = bool(
      (
        input_geometry_profile is None
        and result.boundary_geometry_profile is None
        and (
          result.coupled_request is None
          or (
            result.coupled_request.free_boundary_geometry_profile_y_m is None
            and result.coupled_request.free_boundary_geometry_profile_x_stations_m
            is None
            and result.coupled_request.free_boundary_geometry_profile_source
            is None
          )
        )
        or (
          input_geometry_profile is None
          and result.boundary_geometry_profile is None
          and _solver_owned_neighbor_profile_consumed(result, pressure=False)
        )
      )
      or (
        input_geometry_profile is not None
        and result.boundary_geometry_profile == input_geometry_profile
        and result.coupled_field is not None
        and result.coupled_field.free_boundary_geometry_profile_consumed
      )
    )
    maximum_pressure_update = None
    if response is not None:
      try:
        if use_signed_free_boundary_pressure_response:
          next_profile = (
            build_reflected_domain_global_coupled_downstream_signed_free_boundary_pressure_profile(
              closure,
              response,
              pressure_correction_fraction=fraction,
              position_tolerance_m=position_tolerance,
            )
          )
        else:
          next_profile = (
            build_reflected_domain_global_coupled_downstream_feedback_pressure_profile(
              closure,
              response,
              pressure_correction_fraction=fraction,
              position_tolerance_m=position_tolerance,
            )
          )
      except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
        stop_reason = f'pressure feedback profile construction failed: {error}'
      ####
      try:
        if kinematic_update_mode:
          next_geometry_profile = None
        elif use_signed_free_boundary_geometry_response:
          if response_time is None:
            raise ValueError(
              'signed_normal_response_time_s is required for signed geometry '
              'feedback'
            )
          next_geometry_profile = (
            build_reflected_domain_global_coupled_downstream_signed_free_boundary_geometry_profile(
              closure,
              response,
              signed_normal_response_time_s=response_time,
              geometry_correction_fraction=geometry_fraction,
              maximum_displacement_fraction=maximum_geometry_fraction,
              position_tolerance_m=position_tolerance,
            )
          )
        else:
          next_geometry_profile = (
            build_reflected_domain_global_coupled_downstream_feedback_geometry_profile(
              closure,
              response,
              position_tolerance_m=position_tolerance,
            )
          )
      except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
        stop_reason = (
          stop_reason
          or f'geometry feedback profile construction failed: {error}'
        )
      ####
      try:
        upstream_feedback_proposal = (
          build_reflected_domain_global_coupled_downstream_upstream_feedback_proposal(
            closure,
            response,
            correction_fraction=fraction,
            position_tolerance_m=position_tolerance,
          )
        )
      except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
        if response.converged:
          stop_reason = (
            stop_reason
            or 'upstream/global feedback proposal construction failed: '
            f'{error}'
          )
        ####
      ####
    ####
    if next_profile is not None and not (
      next_profile.profile_verified
      and next_profile.source_closure_fingerprint
      == moc_reflected_domain_global_physical_closure_fingerprint(closure)
    ):
      pressure_profile_lineage_verified = False
    ####
    if next_geometry_profile is not None and not (
      next_geometry_profile.profile_verified
      and next_geometry_profile.source_closure_fingerprint
      == moc_reflected_domain_global_physical_closure_fingerprint(closure)
    ):
      geometry_profile_lineage_verified = False
    ####
    if input_profile is not None and next_profile is not None:
      if not _profiles_aligned(
        input_profile,
        next_profile,
        position_tolerance_m=position_tolerance,
      ):
        pressure_profile_alignment_verified = False
        stop_reason = (
          'pressure feedback profile cell-center stations changed between '
          'fresh solves; no regridding or extrapolation was attempted'
        )
      else:
        maximum_pressure_update = _maximum_profile_update(
          input_profile,
          next_profile,
        )
        if (
          result.local_coupled_field_verified
          and maximum_pressure_update <= update_tolerance
        ):
          pressure_update_convergence_verified = True
        ####
      ####
    ####
    if input_geometry_profile is not None and next_geometry_profile is not None:
      if not _geometry_profiles_aligned(
        input_geometry_profile,
        next_geometry_profile,
        position_tolerance_m=position_tolerance,
      ):
        geometry_profile_alignment_verified = False
        stop_reason = (
          stop_reason
          or 'geometry feedback boundary-node stations changed between fresh '
          'solves; no regridding or extrapolation was attempted'
        )
      ####
    ####
    iterations.append(
      MocReflectedDomainGlobalCoupledDownstreamFeedbackIteration(
        iteration_index=iteration_index,
        input_pressure_profile=input_profile,
        result=result,
        solver_response=solver_response,
        response=response,
        boundary_trace=boundary_trace,
        input_geometry_profile=input_geometry_profile,
        next_pressure_profile=next_profile,
        next_geometry_profile=next_geometry_profile,
        upstream_feedback_proposal=upstream_feedback_proposal,
        transonic_interface_audit=transonic_interface_audit,
        maximum_pressure_update_Pa=maximum_pressure_update,
        pressure_profile_lineage_verified=pressure_profile_lineage_verified,
        geometry_profile_lineage_verified=geometry_profile_lineage_verified,
        response_lineage_verified=response_lineage_verified,
        boundary_trace_lineage_verified=boundary_trace_lineage_verified,
        boundary_trace_verified=boundary_trace_verified,
        pressure_profile_consumption_verified=(
          pressure_profile_consumption_verified
        ),
        geometry_profile_consumption_verified=(
          geometry_profile_consumption_verified
        ),
        initial_state_lineage_verified=iteration_initial_state_lineage_verified,
      )
    )
    if not result.local_coupled_field_verified:
      stop_reason = stop_reason or (
        'fresh coupled field did not pass its local solver and independent '
        'audit; no lower-fidelity fallback was attempted'
      )
      break
    ####
    if not iteration_transonic_interface_audit_verified:
      break
    ####
    if next_profile is None:
      stop_reason = stop_reason or (
        'independently measured response did not produce a covered pressure '
        'profile for the next fresh solve'
      )
      break
    ####
    if next_geometry_profile is None and not kinematic_update_mode:
      stop_reason = stop_reason or (
        'independently measured response did not produce a covered geometry '
        'profile for the next fresh solve'
      )
      break
    ####
    if pressure_update_convergence_verified:
      break
    ####
    input_profile = next_profile
    input_geometry_profile = next_geometry_profile
  ####
  retained_iterations = tuple(iterations)
  fresh_solver_invocation_verified = bool(
    retained_iterations
    and len({id(item.result) for item in retained_iterations})
    == len(retained_iterations)
  )
  closure_lineage_verified = bool(
    retained_iterations
    and all(item.result.closure_lineage_verified for item in retained_iterations)
  )
  pressure_profile_lineage_verified = bool(
    retained_iterations
    and all(
      item.pressure_profile_lineage_verified
      and item.pressure_profile_consumption_verified
      for item in retained_iterations
    )
  )
  geometry_profile_lineage_verified = bool(
    retained_iterations
    and all(
      item.geometry_profile_lineage_verified
      for item in retained_iterations
    )
  )
  geometry_profile_consumption_verified = bool(
    retained_iterations
    and all(
      item.geometry_profile_consumption_verified
      for item in retained_iterations
    )
  )
  response_lineage_verified = bool(
    retained_iterations
    and all(item.response_lineage_verified for item in retained_iterations)
  )
  response_channels_finite = bool(
    retained_iterations
    and all(item.response_channels_finite for item in retained_iterations)
  )
  response_coverage_verified = bool(
    retained_iterations
    and all(item.response_coverage_verified for item in retained_iterations)
  )
  normal_velocity_residual_descent_required = bool(
    use_signed_free_boundary_geometry_response
  )
  normal_velocity_residual_descent_verified = (
    _normal_velocity_residual_descent_verified(
      retained_iterations,
      required=normal_velocity_residual_descent_required,
    )
  )
  response_residuals_verified = bool(
    retained_iterations
    and all(item.response_residuals_verified for item in retained_iterations)
  )
  boundary_trace_verified = bool(
    retained_iterations
    and all(
      item.boundary_trace_lineage_verified and item.boundary_trace_verified
      for item in retained_iterations
    )
  )
  local_coupled_field_verified = bool(
    retained_iterations
    and all(item.local_coupled_field_verified for item in retained_iterations)
  )
  transonic_interface_audit_verified = bool(
    not transonic_interface_audit_required
    or (
      retained_iterations
      and all(
        item.transonic_interface_audit_verified
        for item in retained_iterations
      )
    )
  )
  fidelity_isolation_verified = bool(
    retained_iterations
    and all(item.fidelity_isolation_verified for item in retained_iterations)
  )
  status, message = _status_for_run(
    iterations=retained_iterations,
    fresh_solver_invocation_verified=fresh_solver_invocation_verified,
    closure_lineage_verified=closure_lineage_verified,
    pressure_profile_lineage_verified=pressure_profile_lineage_verified,
    pressure_profile_alignment_verified=pressure_profile_alignment_verified,
    geometry_profile_lineage_verified=geometry_profile_lineage_verified,
    geometry_profile_alignment_verified=geometry_profile_alignment_verified,
    geometry_profile_consumption_verified=geometry_profile_consumption_verified,
    response_lineage_verified=response_lineage_verified,
    response_channels_finite=response_channels_finite,
    response_coverage_verified=response_coverage_verified,
    normal_velocity_residual_descent_required=(
      normal_velocity_residual_descent_required
    ),
    normal_velocity_residual_descent_verified=(
      normal_velocity_residual_descent_verified
    ),
    response_residuals_verified=response_residuals_verified,
    boundary_trace_verified=boundary_trace_verified,
    local_coupled_field_verified=local_coupled_field_verified,
    initial_state_lineage_verified=initial_state_lineage_verified,
    pressure_update_convergence_verified=pressure_update_convergence_verified,
    fidelity_isolation_verified=fidelity_isolation_verified,
    transonic_interface_audit_verified=transonic_interface_audit_verified,
  )
  if stop_reason is not None:
    message = f'{message}; {stop_reason}'
  ####
  return MocReflectedDomainGlobalCoupledDownstreamFeedbackRun(
    closure=closure,
    requested_iterations=maximum_iterations,
    iterations=retained_iterations,
    status=status,
    pressure_update_tolerance_Pa=update_tolerance,
    pressure_correction_fraction=fraction,
    configuration=configuration,
    configuration_fingerprint=configuration_fingerprint,
    transonic_interface_audit_required=transonic_interface_audit_required,
    transonic_interface_audit_verified=transonic_interface_audit_verified,
    fresh_solver_invocation_verified=fresh_solver_invocation_verified,
    closure_lineage_verified=closure_lineage_verified,
    pressure_profile_lineage_verified=pressure_profile_lineage_verified,
    pressure_profile_alignment_verified=pressure_profile_alignment_verified,
    geometry_profile_lineage_verified=geometry_profile_lineage_verified,
    geometry_profile_alignment_verified=geometry_profile_alignment_verified,
    geometry_profile_consumption_verified=geometry_profile_consumption_verified,
    response_lineage_verified=response_lineage_verified,
    response_channels_finite=response_channels_finite,
    response_coverage_verified=response_coverage_verified,
    normal_velocity_residual_descent_required=(
      normal_velocity_residual_descent_required
    ),
    normal_velocity_residual_descent_verified=(
      normal_velocity_residual_descent_verified
    ),
    response_residuals_verified=response_residuals_verified,
    boundary_trace_verified=boundary_trace_verified,
    local_coupled_field_verified=local_coupled_field_verified,
    initial_state_lineage_verified=initial_state_lineage_verified,
    pressure_update_convergence_verified=pressure_update_convergence_verified,
    fidelity_isolation_verified=fidelity_isolation_verified,
    message=message,
  )
####


class MocReflectedDomainGlobalCoupledDownstreamFeedbackRefinementStatus(
  str,
  Enum,
):
  """Outcome of disjoint signed-response case and mesh evidence."""

  CONVERGED_RESEARCH_SIGNED_RESPONSE_LADDER = (
    'converged-research-global-coupled-downstream-signed-response-ladder'
  )
  INVALID_INPUT = 'invalid_input'
  CASE_ID_FAILURE = (
    'global-coupled-downstream-feedback-refinement-case-id-failure'
  )
  CLOSURE_FAILURE = (
    'global-coupled-downstream-feedback-refinement-closure-failure'
  )
  RESOLUTION_FAILURE = (
    'global-coupled-downstream-feedback-refinement-resolution-failure'
  )
  CASE_FAILURE = (
    'global-coupled-downstream-feedback-refinement-case-failure'
  )
  RESPONSE_FAILURE = (
    'global-coupled-downstream-feedback-refinement-response-failure'
  )
  FIDELITY_FAILURE = (
    'global-coupled-downstream-feedback-refinement-fidelity-failure'
  )
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalCoupledDownstreamFeedbackRefinementCase:
  """One named closure and its independent signed-response mesh ladder."""

  case_id: str
  regime: str
  closure: MocReflectedDomainGlobalPhysicalClosureResult
  resolutions: tuple[tuple[int, int], ...]

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
    object.__setattr__(self, 'case_id', case_id)
    object.__setattr__(self, 'regime', regime)
    object.__setattr__(self, 'resolutions', resolutions)
  ####

  @property
  def closure_fingerprint(self) -> str:
    """Return the exact physical closure identity owned by this case."""

    return moc_reflected_domain_global_physical_closure_fingerprint(
      self.closure
    )
  ####

  @property
  def resolution_ladder_verified(self) -> bool:
    """Whether the case declares a strict two-point-or-more mesh ladder."""

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
class MocReflectedDomainGlobalCoupledDownstreamFeedbackRefinementCaseRun:
  """Fresh signed-response runs retained for one named case."""

  case: MocReflectedDomainGlobalCoupledDownstreamFeedbackRefinementCase
  runs: tuple[MocReflectedDomainGlobalCoupledDownstreamFeedbackRun, ...]
  fresh_solver_invocation_verified: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.case,
      MocReflectedDomainGlobalCoupledDownstreamFeedbackRefinementCase,
    ):
      raise TypeError(
        'case must be a '
        'MocReflectedDomainGlobalCoupledDownstreamFeedbackRefinementCase'
      )
    ####
    runs = tuple(self.runs)
    if any(
      not isinstance(
        run,
        MocReflectedDomainGlobalCoupledDownstreamFeedbackRun,
      )
      for run in runs
    ):
      raise TypeError(
        'runs must contain '
        'MocReflectedDomainGlobalCoupledDownstreamFeedbackRun values'
      )
    ####
    if not isinstance(self.fresh_solver_invocation_verified, bool):
      raise TypeError('fresh_solver_invocation_verified must be a bool')
    ####
    object.__setattr__(self, 'runs', runs)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    """Whether this case has local signed-response evidence only."""

    return bool(
      self.fresh_solver_invocation_verified
      and len(self.runs) == len(self.case.resolutions)
      and all(
        run.closure is self.case.closure
        and run.fresh_solver_invocation_verified
        and run.local_coupled_field_verified
        and run.normal_velocity_residual_descent_required
        and run.normal_velocity_residual_descent_verified
        and run.chain_promotion_blocked
        and not run.production_claim_allowed
        for run in self.runs
      )
    )
  ####

  @property
  def production_claim_allowed(self) -> bool:
    return False
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'case': self.case.as_report(),
      'converged': self.converged,
      'fresh_solver_invocation_verified': (
        self.fresh_solver_invocation_verified
      ),
      'production_claim_allowed': self.production_claim_allowed,
      'runs': tuple(run.as_report() for run in self.runs),
      'message': self.message,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalCoupledDownstreamFeedbackRefinementMeasurement:
  """Independent aggregate evidence for disjoint signed-response ladders."""

  status: MocReflectedDomainGlobalCoupledDownstreamFeedbackRefinementStatus
  cases: tuple[
    MocReflectedDomainGlobalCoupledDownstreamFeedbackRefinementCase,
    ...
  ] = ()
  case_runs: tuple[
    MocReflectedDomainGlobalCoupledDownstreamFeedbackRefinementCaseRun,
    ...
  ] = ()
  case_ids: tuple[str, ...] = ()
  regimes: tuple[str, ...] = ()
  closure_fingerprints: tuple[str, ...] = ()
  requested_resolutions: tuple[tuple[tuple[int, int], ...], ...] = ()
  run_statuses: tuple[tuple[str, ...], ...] = ()
  maximum_normal_velocity_residuals_m_s: tuple[tuple[float, ...], ...] = ()
  case_ids_verified: bool = False
  closure_bindings_verified: bool = False
  distinct_closure_fingerprints_verified: bool = False
  resolution_ladders_verified: bool = False
  fresh_solver_invocation_verified: bool = False
  signed_response_configuration_verified: bool = False
  closure_lineage_verified: bool = False
  profile_lineage_verified: bool = False
  response_lineage_verified: bool = False
  response_channels_finite: bool = False
  response_coverage_verified: bool = False
  geometry_profile_consumption_verified: bool = False
  normal_velocity_residual_descent_verified: bool = False
  local_coupled_field_verified: bool = False
  fidelity_isolation_verified: bool = False
  global_coupling_verified: bool = False
  downstream_boundary_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  external_validation_required: bool = True
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalCoupledDownstreamFeedbackRefinementStatus,
    ):
      raise TypeError(
        'status must be a '
        'MocReflectedDomainGlobalCoupledDownstreamFeedbackRefinementStatus'
      )
    ####
    cases = tuple(self.cases)
    case_runs = tuple(self.case_runs)
    if any(
      not isinstance(
        case,
        MocReflectedDomainGlobalCoupledDownstreamFeedbackRefinementCase,
      )
      for case in cases
    ):
      raise TypeError('cases must contain typed refinement cases')
    ####
    if any(
      not isinstance(
        case_run,
        MocReflectedDomainGlobalCoupledDownstreamFeedbackRefinementCaseRun,
      )
      for case_run in case_runs
    ):
      raise TypeError('case_runs must contain typed refinement case runs')
    ####
    if len(cases) != len(case_runs):
      raise ValueError('cases and case_runs must have matching lengths')
    ####
    for name in (
      'case_ids_verified',
      'closure_bindings_verified',
      'distinct_closure_fingerprints_verified',
      'resolution_ladders_verified',
      'fresh_solver_invocation_verified',
      'signed_response_configuration_verified',
      'closure_lineage_verified',
      'profile_lineage_verified',
      'response_lineage_verified',
      'response_channels_finite',
      'response_coverage_verified',
      'geometry_profile_consumption_verified',
      'normal_velocity_residual_descent_verified',
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
        'signed-response refinement cannot claim global or downstream closure'
      )
    ####
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError(
        'signed-response refinement must retain its promotion block'
      )
    ####
    object.__setattr__(self, 'cases', cases)
    object.__setattr__(self, 'case_runs', case_runs)
    object.__setattr__(self, 'case_ids', tuple(str(value) for value in self.case_ids))
    object.__setattr__(self, 'regimes', tuple(str(value) for value in self.regimes))
    object.__setattr__(
      self,
      'closure_fingerprints',
      tuple(str(value) for value in self.closure_fingerprints),
    )
    object.__setattr__(
      self,
      'requested_resolutions',
      tuple(tuple(tuple(value) for value in item) for item in self.requested_resolutions),
    )
    object.__setattr__(
      self,
      'run_statuses',
      tuple(tuple(str(value) for value in item) for item in self.run_statuses),
    )
    object.__setattr__(
      self,
      'maximum_normal_velocity_residuals_m_s',
      tuple(
        tuple(float(value) for value in item)
        for item in self.maximum_normal_velocity_residuals_m_s
      ),
    )
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def operator_id(self) -> str:
    return MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_DOWNSTREAM_FEEDBACK_REFINEMENT_OPERATOR_ID
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalCoupledDownstreamFeedbackRefinementStatus
      .CONVERGED_RESEARCH_SIGNED_RESPONSE_LADDER
      and self.case_ids_verified
      and self.closure_bindings_verified
      and self.distinct_closure_fingerprints_verified
      and self.resolution_ladders_verified
      and self.fresh_solver_invocation_verified
      and self.signed_response_configuration_verified
      and self.closure_lineage_verified
      and self.profile_lineage_verified
      and self.response_lineage_verified
      and self.response_channels_finite
      and self.response_coverage_verified
      and self.geometry_profile_consumption_verified
      and self.normal_velocity_residual_descent_verified
      and self.local_coupled_field_verified
      and self.fidelity_isolation_verified
      and not self.global_coupling_verified
      and not self.downstream_boundary_closure_verified
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': self.operator_id,
      'status': self.status.value,
      'converged': self.converged,
      'case_ids': self.case_ids,
      'regimes': self.regimes,
      'closure_fingerprints': self.closure_fingerprints,
      'requested_resolutions': self.requested_resolutions,
      'run_statuses': self.run_statuses,
      'maximum_normal_velocity_residuals_m_s': (
        self.maximum_normal_velocity_residuals_m_s
      ),
      'case_ids_verified': self.case_ids_verified,
      'closure_bindings_verified': self.closure_bindings_verified,
      'distinct_closure_fingerprints_verified': (
        self.distinct_closure_fingerprints_verified
      ),
      'resolution_ladders_verified': self.resolution_ladders_verified,
      'fresh_solver_invocation_verified': self.fresh_solver_invocation_verified,
      'signed_response_configuration_verified': (
        self.signed_response_configuration_verified
      ),
      'closure_lineage_verified': self.closure_lineage_verified,
      'profile_lineage_verified': self.profile_lineage_verified,
      'response_lineage_verified': self.response_lineage_verified,
      'response_channels_finite': self.response_channels_finite,
      'response_coverage_verified': self.response_coverage_verified,
      'geometry_profile_consumption_verified': (
        self.geometry_profile_consumption_verified
      ),
      'normal_velocity_residual_descent_verified': (
        self.normal_velocity_residual_descent_verified
      ),
      'local_coupled_field_verified': self.local_coupled_field_verified,
      'fidelity_isolation_verified': self.fidelity_isolation_verified,
      'global_coupling_verified': self.global_coupling_verified,
      'downstream_boundary_closure_verified': (
        self.downstream_boundary_closure_verified
      ),
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'external_validation_required': self.external_validation_required,
      'cases': tuple(case.as_report() for case in self.cases),
      'case_runs': tuple(case_run.as_report() for case_run in self.case_runs),
      'message': self.message,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalCoupledDownstreamFeedbackRefinementRun:
  """Fresh execution record for disjoint signed-response case ladders."""

  cases: tuple[
    MocReflectedDomainGlobalCoupledDownstreamFeedbackRefinementCase,
    ...
  ]
  case_runs: tuple[
    MocReflectedDomainGlobalCoupledDownstreamFeedbackRefinementCaseRun,
    ...
  ]
  measurement: (
    MocReflectedDomainGlobalCoupledDownstreamFeedbackRefinementMeasurement
  )
  configuration: dict[str, Any]
  configuration_fingerprint: str
  fresh_solver_invocation_verified: bool = False
  fidelity_isolation_verified: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    cases = tuple(self.cases)
    case_runs = tuple(self.case_runs)
    if self.measurement.cases != cases:
      raise ValueError('measurement must retain the exact cases')
    ####
    if self.measurement.case_runs != case_runs:
      raise ValueError('measurement must retain the exact case runs')
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
      raise ValueError('signed-response refinement cannot claim production validity')
    ####
    object.__setattr__(self, 'cases', cases)
    object.__setattr__(self, 'case_runs', case_runs)
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
        MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_DOWNSTREAM_FEEDBACK_REFINEMENT_RUN_OPERATOR_ID
      ),
      'converged': self.converged,
      'fresh_solver_invocation_verified': (
        self.fresh_solver_invocation_verified
      ),
      'fidelity_isolation_verified': self.fidelity_isolation_verified,
      'production_claim_allowed': self.production_claim_allowed,
      'configuration': self.configuration,
      'configuration_fingerprint': self.configuration_fingerprint,
      'cases': tuple(case.as_report() for case in self.cases),
      'case_runs': tuple(case_run.as_report() for case_run in self.case_runs),
      'measurement': self.measurement.as_report(),
      'message': self.message,
    }
  ####
####


def measure_reflected_domain_global_coupled_downstream_feedback_refinement(
  cases: Sequence[
    MocReflectedDomainGlobalCoupledDownstreamFeedbackRefinementCase
  ],
  case_runs: Sequence[
    MocReflectedDomainGlobalCoupledDownstreamFeedbackRefinementCaseRun
  ],
  *,
  signed_normal_response_time_s: float,
) -> MocReflectedDomainGlobalCoupledDownstreamFeedbackRefinementMeasurement:
  """Measure disjoint signed-response evidence without promoting closure."""

  retained_cases = tuple(cases)
  retained_case_runs = tuple(case_runs)
  if not retained_cases:
    raise ValueError('cases must not be empty')
  ####
  if len(retained_cases) != len(retained_case_runs):
    raise ValueError('cases and case_runs must have matching lengths')
  ####
  response_time = float(signed_normal_response_time_s)
  if not isfinite(response_time) or response_time <= 0.0:
    raise ValueError(
      'signed_normal_response_time_s must be finite and positive'
    )
  ####
  case_ids = tuple(case.case_id for case in retained_cases)
  regimes = tuple(case.regime for case in retained_cases)
  closure_fingerprints = tuple(
    case.closure_fingerprint for case in retained_cases
  )
  requested_resolutions = tuple(
    case.resolutions for case in retained_cases
  )
  case_ids_verified = bool(
    len(retained_cases) >= 2
    and all(case_ids)
    and len(set(case_ids)) == len(case_ids)
  )
  closure_bindings_verified = bool(
    all(
      case_run.case is case
      and all(run.closure is case.closure for run in case_run.runs)
      for case, case_run in zip(retained_cases, retained_case_runs)
    )
  )
  distinct_closure_fingerprints_verified = bool(
    len(retained_cases) >= 2
    and len(set(closure_fingerprints)) == len(closure_fingerprints)
  )
  resolution_ladders_verified = bool(
    retained_cases
    and all(case.resolution_ladder_verified for case in retained_cases)
  )
  fresh_solver_invocation_verified = bool(
    retained_case_runs
    and all(
      case_run.fresh_solver_invocation_verified
      and len(case_run.runs) == len(case_run.case.resolutions)
      and all(run.fresh_solver_invocation_verified for run in case_run.runs)
      for case_run in retained_case_runs
    )
  )
  all_runs = tuple(
    run
    for case_run in retained_case_runs
    for run in case_run.runs
  )
  signed_response_configuration_verified = bool(
    all_runs
    and all(
      run.configuration.get('use_signed_free_boundary_pressure_response') is True
      and run.configuration.get('use_signed_free_boundary_geometry_response')
      is True
      and run.configuration.get('signed_normal_response_time_s')
      == response_time
      and run.configuration.get('normal_velocity_residual_descent_policy')
      == 'strict-fresh-response-descent-required-v1'
      for run in all_runs
    )
  )
  closure_lineage_verified = bool(
    all_runs and all(run.closure_lineage_verified for run in all_runs)
  )
  profile_lineage_verified = bool(
    all_runs
    and all(
      run.pressure_profile_lineage_verified
      and run.pressure_profile_alignment_verified
      and run.geometry_profile_lineage_verified
      and run.geometry_profile_alignment_verified
      for run in all_runs
    )
  )
  response_lineage_verified = bool(
    all_runs and all(run.response_lineage_verified for run in all_runs)
  )
  response_channels_finite = bool(
    all_runs and all(run.response_channels_finite for run in all_runs)
  )
  response_coverage_verified = bool(
    all_runs and all(run.response_coverage_verified for run in all_runs)
  )
  geometry_profile_consumption_verified = bool(
    all_runs
    and all(run.geometry_profile_consumption_verified for run in all_runs)
  )
  normal_velocity_residual_descent_verified = bool(
    all_runs
    and all(
      run.normal_velocity_residual_descent_required
      and run.normal_velocity_residual_descent_verified
      for run in all_runs
    )
  )
  local_coupled_field_verified = bool(
    all_runs and all(run.local_coupled_field_verified for run in all_runs)
  )
  fidelity_isolation_verified = bool(
    all_runs and all(run.fidelity_isolation_verified for run in all_runs)
  )
  global_coupling_verified = any(
    run.global_coupling_verified for run in all_runs
  )
  downstream_boundary_closure_verified = any(
    run.downstream_boundary_closure_verified for run in all_runs
  )
  chain_promotion_blocked = bool(
    all_runs
    and all(
      run.chain_promotion_blocked and not run.production_claim_allowed
      for run in all_runs
    )
  )
  production_claim_allowed = any(
    run.production_claim_allowed for run in all_runs
  )
  run_statuses = tuple(
    tuple(run.status.value for run in case_run.runs)
    for case_run in retained_case_runs
  )
  maximum_normal_velocity_residuals = tuple(
    tuple(
      response.maximum_normal_velocity_residual_m_s
      for run in case_run.runs
      for item in run.iterations
      for response in (item.response,)
      if response is not None
    )
    for case_run in retained_case_runs
  )
  if not case_ids_verified:
    status = (
      MocReflectedDomainGlobalCoupledDownstreamFeedbackRefinementStatus
      .CASE_ID_FAILURE
    )
    message = 'signed-response evidence requires at least two unique case IDs'
  elif not (
    closure_bindings_verified and distinct_closure_fingerprints_verified
  ):
    status = (
      MocReflectedDomainGlobalCoupledDownstreamFeedbackRefinementStatus
      .CLOSURE_FAILURE
    )
    message = (
      'signed-response cases must retain distinct exact closure fingerprints; '
      'closures are never treated as mesh refinements'
    )
  elif not resolution_ladders_verified:
    status = (
      MocReflectedDomainGlobalCoupledDownstreamFeedbackRefinementStatus
      .RESOLUTION_FAILURE
    )
    message = (
      'each signed-response case must retain a strictly increasing axial and '
      'transverse resolution ladder'
    )
  elif not (fresh_solver_invocation_verified and local_coupled_field_verified):
    status = (
      MocReflectedDomainGlobalCoupledDownstreamFeedbackRefinementStatus
      .CASE_FAILURE
    )
    message = (
      'at least one signed-response mesh point did not retain a fresh locally '
      'audited coupled field'
    )
  elif not fidelity_isolation_verified or not chain_promotion_blocked:
    status = (
      MocReflectedDomainGlobalCoupledDownstreamFeedbackRefinementStatus
      .FIDELITY_FAILURE
    )
    message = (
      'signed-response refinement changed its fidelity ceiling or lost its '
      'promotion block'
    )
  elif not (
    signed_response_configuration_verified
    and closure_lineage_verified
    and profile_lineage_verified
    and response_lineage_verified
    and response_channels_finite
    and response_coverage_verified
    and geometry_profile_consumption_verified
    and normal_velocity_residual_descent_verified
  ):
    status = (
      MocReflectedDomainGlobalCoupledDownstreamFeedbackRefinementStatus
      .RESPONSE_FAILURE
    )
    message = (
      'signed pressure/geometry response configuration, lineage, coverage, '
      'or strict fresh normal-residual descent is incomplete'
    )
  else:
    status = (
      MocReflectedDomainGlobalCoupledDownstreamFeedbackRefinementStatus
      .CONVERGED_RESEARCH_SIGNED_RESPONSE_LADDER
    )
    message = (
      'disjoint signed-response case and resolution ladders passed local '
      'fresh-field evidence; global feedback, canonical closure, external '
      'validation, and production promotion remain blocked'
    )
  ####
  return MocReflectedDomainGlobalCoupledDownstreamFeedbackRefinementMeasurement(
    status=status,
    cases=retained_cases,
    case_runs=retained_case_runs,
    case_ids=case_ids,
    regimes=regimes,
    closure_fingerprints=closure_fingerprints,
    requested_resolutions=requested_resolutions,
    run_statuses=run_statuses,
    maximum_normal_velocity_residuals_m_s=(
      maximum_normal_velocity_residuals
    ),
    case_ids_verified=case_ids_verified,
    closure_bindings_verified=closure_bindings_verified,
    distinct_closure_fingerprints_verified=(
      distinct_closure_fingerprints_verified
    ),
    resolution_ladders_verified=resolution_ladders_verified,
    fresh_solver_invocation_verified=fresh_solver_invocation_verified,
    signed_response_configuration_verified=(
      signed_response_configuration_verified
    ),
    closure_lineage_verified=closure_lineage_verified,
    profile_lineage_verified=profile_lineage_verified,
    response_lineage_verified=response_lineage_verified,
    response_channels_finite=response_channels_finite,
    response_coverage_verified=response_coverage_verified,
    geometry_profile_consumption_verified=(
      geometry_profile_consumption_verified
    ),
    normal_velocity_residual_descent_verified=(
      normal_velocity_residual_descent_verified
    ),
    local_coupled_field_verified=local_coupled_field_verified,
    fidelity_isolation_verified=fidelity_isolation_verified,
    global_coupling_verified=global_coupling_verified,
    downstream_boundary_closure_verified=downstream_boundary_closure_verified,
    chain_promotion_blocked=chain_promotion_blocked,
    production_claim_allowed=production_claim_allowed,
    message=message,
  )
####


def run_reflected_domain_global_coupled_downstream_feedback_refinement(
  cases: Sequence[
    MocReflectedDomainGlobalCoupledDownstreamFeedbackRefinementCase
  ],
  *,
  reference_total_temperature_K: float,
  maximum_iterations: int = 2,
  pressure_correction_fraction: float = 0.25,
  signed_normal_response_time_s: float = 1.0e-6,
  geometry_correction_fraction: float = 0.25,
  signed_normal_max_displacement_fraction: float = 0.25,
  pressure_update_tolerance_Pa: float = 1.0e3,
  position_tolerance_m: float = 1.0e-9,
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
) -> MocReflectedDomainGlobalCoupledDownstreamFeedbackRefinementRun:
  """Run fresh signed pressure/geometry feedback across disjoint ladders.

  ``resolutions`` are owned by each named case and map to
  ``(axial_station_count, transverse_cell_count)``; the axial cell count is
  set to the same declared axial value so every feedback step has a fully
  specified fresh mesh.  This operator intentionally requires both signed
  response consumers and never reports canonical global closure.
  """

  retained_cases = tuple(cases)
  if not retained_cases:
    raise ValueError('cases must not be empty')
  ####
  if any(
    not isinstance(
      case,
      MocReflectedDomainGlobalCoupledDownstreamFeedbackRefinementCase,
    )
    for case in retained_cases
  ):
    raise TypeError(
      'cases must contain '
      'MocReflectedDomainGlobalCoupledDownstreamFeedbackRefinementCase values'
    )
  ####
  response_time = float(signed_normal_response_time_s)
  if not isfinite(response_time) or response_time <= 0.0:
    raise ValueError(
      'signed_normal_response_time_s must be finite and positive'
    )
  ####
  configuration = {
    'case_ids': tuple(case.case_id for case in retained_cases),
    'regimes': tuple(case.regime for case in retained_cases),
    'closure_fingerprints': tuple(
      case.closure_fingerprint for case in retained_cases
    ),
    'resolutions': tuple(case.resolutions for case in retained_cases),
    'reference_total_temperature_K': float(reference_total_temperature_K),
    'maximum_iterations': int(maximum_iterations),
    'pressure_correction_fraction': float(pressure_correction_fraction),
    'use_signed_free_boundary_pressure_response': True,
    'use_signed_free_boundary_geometry_response': True,
    'signed_normal_response_time_s': response_time,
    'geometry_correction_fraction': float(geometry_correction_fraction),
    'signed_normal_max_displacement_fraction': float(
      signed_normal_max_displacement_fraction
    ),
    'normal_velocity_residual_descent_policy': (
      'strict-fresh-response-descent-required-v1'
    ),
    'pressure_update_tolerance_Pa': float(pressure_update_tolerance_Pa),
    'position_tolerance_m': float(position_tolerance_m),
    'ambient_pressure_Pa': ambient_pressure_Pa,
    'downstream_length_m': float(downstream_length_m),
    'initial_outlet_height_m': float(initial_outlet_height_m),
    'control_section_x_offset_m': float(control_section_x_offset_m),
    'control_section_height_m': float(control_section_height_m),
    'control_section_sample_count': int(control_section_sample_count),
    'max_pseudo_iterations': int(max_pseudo_iterations),
    'max_shape_iterations': int(max_shape_iterations),
    'inlet_boundary_mode': getattr(
      inlet_boundary_mode,
      'value',
      str(inlet_boundary_mode),
    ),
    'outlet_static_pressure_Pa': outlet_static_pressure_Pa,
    'feedback_refinement_policy': (
      'disjoint-closure-two-dimensional-resolution-ladder-v1'
    ),
    'promotion_policy': (
      'research-local-signed-response-only-no-global-or-production-claim-v1'
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
  case_runs: list[
    MocReflectedDomainGlobalCoupledDownstreamFeedbackRefinementCaseRun
  ] = []
  for case in retained_cases:
    runs: list[MocReflectedDomainGlobalCoupledDownstreamFeedbackRun] = []
    failures: list[str] = []
    for axial_count, transverse_count in case.resolutions:
      try:
        run = run_reflected_domain_global_coupled_downstream_feedback(
          case.closure,
          reference_total_temperature_K=reference_total_temperature_K,
          maximum_iterations=maximum_iterations,
          pressure_correction_fraction=pressure_correction_fraction,
          use_signed_free_boundary_pressure_response=True,
          use_signed_free_boundary_geometry_response=True,
          signed_normal_response_time_s=response_time,
          geometry_correction_fraction=geometry_correction_fraction,
          signed_normal_max_displacement_fraction=(
            signed_normal_max_displacement_fraction
          ),
          pressure_update_tolerance_Pa=pressure_update_tolerance_Pa,
          position_tolerance_m=position_tolerance_m,
          ambient_pressure_Pa=ambient_pressure_Pa,
          downstream_length_m=downstream_length_m,
          initial_outlet_height_m=initial_outlet_height_m,
          control_section_x_offset_m=control_section_x_offset_m,
          control_section_height_m=control_section_height_m,
          control_section_sample_count=control_section_sample_count,
          axial_station_count=axial_count,
          axial_cell_count=axial_count,
          transverse_cell_count=transverse_count,
          max_pseudo_iterations=max_pseudo_iterations,
          max_shape_iterations=max_shape_iterations,
          inlet_boundary_mode=inlet_boundary_mode,
          outlet_static_pressure_Pa=outlet_static_pressure_Pa,
          physical_field_continuation_profile=(
            physical_field_continuation_profile
          ),
          physical_field_shock_front_condition=(
            physical_field_shock_front_condition
          ),
        )
        runs.append(run)
      except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
        failures.append(
          f'resolution {(axial_count, transverse_count)} failed: {error}'
        )
      ####
    ####
    case_runs.append(
      MocReflectedDomainGlobalCoupledDownstreamFeedbackRefinementCaseRun(
        case=case,
        runs=tuple(runs),
        fresh_solver_invocation_verified=(
          len(runs) == len(case.resolutions)
          and all(run.fresh_solver_invocation_verified for run in runs)
        ),
        message=(
          'fresh signed-response mesh ladder completed'
          if not failures
          else '; '.join(failures)
        ),
      )
    )
  ####
  retained_case_runs = tuple(case_runs)
  measurement = (
    measure_reflected_domain_global_coupled_downstream_feedback_refinement(
      retained_cases,
      retained_case_runs,
      signed_normal_response_time_s=response_time,
    )
  )
  fresh_solver_invocation_verified = bool(
    retained_case_runs
    and all(
      case_run.fresh_solver_invocation_verified
      for case_run in retained_case_runs
    )
  )
  fidelity_isolation_verified = bool(
    retained_case_runs
    and all(
      case_run.runs
      and all(run.fidelity_isolation_verified for run in case_run.runs)
      for case_run in retained_case_runs
    )
  )
  return MocReflectedDomainGlobalCoupledDownstreamFeedbackRefinementRun(
    cases=retained_cases,
    case_runs=retained_case_runs,
    measurement=measurement,
    configuration=configuration,
    configuration_fingerprint=configuration_fingerprint,
    fresh_solver_invocation_verified=fresh_solver_invocation_verified,
    fidelity_isolation_verified=fidelity_isolation_verified,
    message=(
      'fresh signed-response refinement completed; global feedback, '
      'canonical closure, external validation, and production promotion '
      'remain separate gates'
    ),
  )
####
