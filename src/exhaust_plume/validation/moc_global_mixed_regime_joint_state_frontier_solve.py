"""Consume a global state handoff together with a physical shock frontier.

The global boundary-state joint solver already consumes downstream geometry and
conservative residual state.  This module adds the mixed-regime frontier to
that same solve contract: its exact shock-point count drives the fresh global
boundary solve, and the resulting closure must pass a new physical frontier
handoff.  The result is still research evidence until the frontier equations,
downstream boundary, and canonical free boundary are solved together.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Any

from exhaust_plume.models.moc.global_physical_closure import (
  MocReflectedDomainGlobalPhysicalClosureResult,
  moc_reflected_domain_global_physical_closure_fingerprint,
)
from exhaust_plume.validation.moc_global_boundary_state_feedback import (
  MocReflectedDomainGlobalBoundaryStateFeedbackHandoff,
)
from exhaust_plume.validation.moc_global_boundary_state_joint_solve import (
  MocReflectedDomainGlobalBoundaryStateJointSolveResult,
  run_reflected_domain_global_boundary_state_joint_solve,
)
from exhaust_plume.validation.moc_global_mixed_regime_shock_frontier_refinement import (
  MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementCase,
  MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementStep,
  run_reflected_domain_global_mixed_regime_shock_frontier_step,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_JOINT_STATE_FRONTIER_SOLVE_OPERATOR_ID',
  'MocReflectedDomainGlobalMixedRegimeJointStateFrontierSolveStatus',
  'MocReflectedDomainGlobalMixedRegimeJointStateFrontierSolveRequest',
  'MocReflectedDomainGlobalMixedRegimeJointStateFrontierSolveResult',
  'MocReflectedDomainGlobalMixedRegimeJointStateFrontierSolveAuditStatus',
  'MocReflectedDomainGlobalMixedRegimeJointStateFrontierSolveAudit',
  'run_reflected_domain_global_mixed_regime_joint_state_frontier_solve',
  'audit_reflected_domain_global_mixed_regime_joint_state_frontier_solve',
)


MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_JOINT_STATE_FRONTIER_SOLVE_OPERATOR_ID = (
  'op.moc.reflected-domain.global-mixed-regime-joint-state-frontier-solve-v1'
)


class MocReflectedDomainGlobalMixedRegimeJointStateFrontierSolveStatus(
  str,
  Enum,
):
  """Typed outcomes of the joint state/frontier solve."""

  CONVERGED_RESEARCH_JOINT_STATE_FRONTIER = (
    'converged-research-joint-state-frontier-solve'
  )
  INVALID_INPUT = 'invalid_input'
  FRONTIER_INPUT_FAILURE = 'joint-state-frontier-input-failure'
  GLOBAL_JOINT_SOLVE_FAILURE = 'joint-state-frontier-global-joint-solve-failure'
  FRONTIER_RECHECK_FAILURE = 'joint-state-frontier-frontier-recheck-failure'
  FIDELITY_FAILURE = 'joint-state-frontier-fidelity-failure'
  AUDIT_REQUIRED = 'joint-state-frontier-audit-required'
####


class MocReflectedDomainGlobalMixedRegimeJointStateFrontierSolveAuditStatus(
  str,
  Enum,
):
  """Typed outcomes of the independent joint replay."""

  VERIFIED_RESEARCH_JOINT_STATE_FRONTIER = (
    'verified-research-joint-state-frontier-solve'
  )
  INVALID_INPUT = 'invalid_input'
  REPLAY_FAILURE = 'joint-state-frontier-audit-replay-failure'
  LINEAGE_FAILURE = 'joint-state-frontier-audit-lineage-failure'
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeJointStateFrontierSolveRequest:
  """Exact handoff and frontier state supplied to the joint solver."""

  handoff: MocReflectedDomainGlobalBoundaryStateFeedbackHandoff
  source_frontier_step: MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementStep
  reference_total_temperature_K: float = 1500.0
  component_tolerance: float = 1.0e-5
  source: str = 'research-global-mixed-regime-joint-state-frontier-solve-v1'

  def __post_init__(self) -> None:
    if not isinstance(
      self.handoff,
      MocReflectedDomainGlobalBoundaryStateFeedbackHandoff,
    ):
      raise TypeError('handoff must be a typed boundary-state handoff')
    ####
    if not isinstance(
      self.source_frontier_step,
      MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementStep,
    ):
      raise TypeError('source_frontier_step must be a typed frontier step')
    ####
    source_iterations = self.handoff.boundary_feedback_run.iterations
    if not source_iterations:
      raise ValueError('handoff must retain a source boundary-feedback iteration')
    ####
    if self.source_frontier_step.closure is not source_iterations[-1].source_closure:
      raise ValueError(
        'source_frontier_step must retain the exact closure consumed by the '
        'global boundary-state handoff'
      )
    ####
    temperature = float(self.reference_total_temperature_K)
    tolerance = float(self.component_tolerance)
    if not isfinite(temperature) or temperature <= 0.0:
      raise ValueError('reference_total_temperature_K must be finite and positive')
    ####
    if not isfinite(tolerance) or tolerance <= 0.0:
      raise ValueError('component_tolerance must be finite and positive')
    ####
    source = str(self.source)
    if not source:
      raise ValueError('source must be non-empty')
    ####
    object.__setattr__(self, 'reference_total_temperature_K', temperature)
    object.__setattr__(self, 'component_tolerance', tolerance)
    object.__setattr__(self, 'source', source)
  ####

  @property
  def source_closure(self) -> MocReflectedDomainGlobalPhysicalClosureResult:
    return self.source_frontier_step.closure
  ####

  @property
  def frontier_sample_count(self) -> int:
    return self.source_frontier_step.frontier_sample_count
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': (
        MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_JOINT_STATE_FRONTIER_SOLVE_OPERATOR_ID
      ),
      'source': self.source,
      'reference_total_temperature_K': self.reference_total_temperature_K,
      'component_tolerance': self.component_tolerance,
      'frontier_sample_count': self.frontier_sample_count,
      'source_closure_fingerprint': moc_reflected_domain_global_physical_closure_fingerprint(
        self.source_closure
      ),
      'handoff': self.handoff.as_report(),
      'source_frontier_step': self.source_frontier_step.as_report(),
      'research_only': True,
      'production_claim_allowed': False,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeJointStateFrontierSolveResult:
  """Research result from one state solve and physical frontier recheck."""

  status: MocReflectedDomainGlobalMixedRegimeJointStateFrontierSolveStatus
  request: MocReflectedDomainGlobalMixedRegimeJointStateFrontierSolveRequest | None
  source_frontier_step: MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementStep | None = None
  joint_state_solve: MocReflectedDomainGlobalBoundaryStateJointSolveResult | None = None
  refreshed_frontier_step: MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementStep | None = None
  source_frontier_lineage_verified: bool = False
  source_frontier_locally_verified: bool = False
  frontier_resolution_consumed: bool = False
  global_joint_solve_verified: bool = False
  refreshed_closure_lineage_verified: bool = False
  refreshed_frontier_verified: bool = False
  joint_state_frontier_verified: bool = False
  independent_audit_verified: bool = False
  global_coupling_verified: bool = False
  canonical_free_boundary_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalMixedRegimeJointStateFrontierSolveStatus,
    ):
      raise TypeError('status must be a typed joint state/frontier status')
    ####
    if self.request is not None and not isinstance(
      self.request,
      MocReflectedDomainGlobalMixedRegimeJointStateFrontierSolveRequest,
    ):
      raise TypeError('request must be a typed joint state/frontier request')
    ####
    for name, expected in (
      (
        'source_frontier_step',
        MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementStep,
      ),
      ('joint_state_solve', MocReflectedDomainGlobalBoundaryStateJointSolveResult),
      (
        'refreshed_frontier_step',
        MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementStep,
      ),
    ):
      value = getattr(self, name)
      if value is not None and not isinstance(value, expected):
        raise TypeError(f'{name} must retain its typed result or None')
      ####
    ####
    for name in (
      'source_frontier_lineage_verified',
      'source_frontier_locally_verified',
      'frontier_resolution_consumed',
      'global_joint_solve_verified',
      'refreshed_closure_lineage_verified',
      'refreshed_frontier_verified',
      'joint_state_frontier_verified',
      'independent_audit_verified',
      'global_coupling_verified',
      'canonical_free_boundary_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if self.global_coupling_verified or self.canonical_free_boundary_verified:
      raise ValueError('joint state/frontier result cannot claim canonical closure')
    ####
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError('joint state/frontier result must remain promotion-blocked')
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalMixedRegimeJointStateFrontierSolveStatus
      .CONVERGED_RESEARCH_JOINT_STATE_FRONTIER
      and self.source_frontier_lineage_verified
      and self.source_frontier_locally_verified
      and self.frontier_resolution_consumed
      and self.global_joint_solve_verified
      and self.refreshed_closure_lineage_verified
      and self.refreshed_frontier_verified
      and self.joint_state_frontier_verified
      and self.independent_audit_verified
      and self.chain_promotion_blocked
      and not self.global_coupling_verified
      and not self.canonical_free_boundary_verified
      and not self.production_claim_allowed
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': (
        MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_JOINT_STATE_FRONTIER_SOLVE_OPERATOR_ID
      ),
      'status': self.status.value,
      'converged': self.converged,
      'source_frontier_lineage_verified': self.source_frontier_lineage_verified,
      'source_frontier_locally_verified': self.source_frontier_locally_verified,
      'frontier_resolution_consumed': self.frontier_resolution_consumed,
      'global_joint_solve_verified': self.global_joint_solve_verified,
      'refreshed_closure_lineage_verified': self.refreshed_closure_lineage_verified,
      'refreshed_frontier_verified': self.refreshed_frontier_verified,
      'joint_state_frontier_verified': self.joint_state_frontier_verified,
      'independent_audit_verified': self.independent_audit_verified,
      'global_coupling_verified': False,
      'canonical_free_boundary_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'source_frontier_step': (
        None
        if self.source_frontier_step is None
        else self.source_frontier_step.as_report()
      ),
      'joint_state_solve': (
        None
        if self.joint_state_solve is None
        else self.joint_state_solve.as_report()
      ),
      'refreshed_frontier_step': (
        None
        if self.refreshed_frontier_step is None
        else self.refreshed_frontier_step.as_report()
      ),
      'request': None if self.request is None else self.request.as_report(),
      'claim_status': (
        'research-only joint global-state and physical-frontier solve; the '
        'frontier resolution is consumed by the fresh global solve, but '
        'canonical free-boundary closure, external validation, and production '
        'promotion remain open'
      ),
      'message': self.message,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeJointStateFrontierSolveAudit:
  """Independent replay audit for the joint state/frontier solve."""

  status: MocReflectedDomainGlobalMixedRegimeJointStateFrontierSolveAuditStatus
  candidate: MocReflectedDomainGlobalMixedRegimeJointStateFrontierSolveResult | None
  request_replayed: bool = False
  source_frontier_replayed: bool = False
  global_joint_solve_replayed: bool = False
  refreshed_frontier_replayed: bool = False
  independent_joint_state_frontier_verified: bool = False
  global_coupling_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalMixedRegimeJointStateFrontierSolveAuditStatus,
    ):
      raise TypeError('status must be a typed joint state/frontier audit status')
    ####
    if self.candidate is not None and not isinstance(
      self.candidate,
      MocReflectedDomainGlobalMixedRegimeJointStateFrontierSolveResult,
    ):
      raise TypeError('candidate must be a typed joint state/frontier result')
    ####
    for name in (
      'request_replayed',
      'source_frontier_replayed',
      'global_joint_solve_replayed',
      'refreshed_frontier_replayed',
      'independent_joint_state_frontier_verified',
      'global_coupling_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if self.global_coupling_verified or not self.chain_promotion_blocked:
      raise ValueError('joint state/frontier audit must remain promotion-blocked')
    ####
    if self.production_claim_allowed:
      raise ValueError('joint state/frontier audit cannot allow production claims')
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalMixedRegimeJointStateFrontierSolveAuditStatus
      .VERIFIED_RESEARCH_JOINT_STATE_FRONTIER
      and self.independent_joint_state_frontier_verified
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': (
        MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_JOINT_STATE_FRONTIER_SOLVE_OPERATOR_ID
      ),
      'audit_status': self.status.value,
      'converged': self.converged,
      'request_replayed': self.request_replayed,
      'source_frontier_replayed': self.source_frontier_replayed,
      'global_joint_solve_replayed': self.global_joint_solve_replayed,
      'refreshed_frontier_replayed': self.refreshed_frontier_replayed,
      'independent_joint_state_frontier_verified': (
        self.independent_joint_state_frontier_verified
      ),
      'global_coupling_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'candidate': (
        None if self.candidate is None else self.candidate.as_report()
      ),
      'message': self.message,
    }
  ####
####


def _failure(
  status: MocReflectedDomainGlobalMixedRegimeJointStateFrontierSolveStatus,
  message: str,
  *,
  request: MocReflectedDomainGlobalMixedRegimeJointStateFrontierSolveRequest | None = None,
  **values: Any,
) -> MocReflectedDomainGlobalMixedRegimeJointStateFrontierSolveResult:
  return MocReflectedDomainGlobalMixedRegimeJointStateFrontierSolveResult(
    status=status,
    request=request,
    message=message,
    **values,
  )
####


def run_reflected_domain_global_mixed_regime_joint_state_frontier_solve(
  request: MocReflectedDomainGlobalMixedRegimeJointStateFrontierSolveRequest,
) -> MocReflectedDomainGlobalMixedRegimeJointStateFrontierSolveResult:
  """Consume a frontier resolution in a fresh global state solve and recheck it."""

  status_type = MocReflectedDomainGlobalMixedRegimeJointStateFrontierSolveStatus
  if not isinstance(
    request,
    MocReflectedDomainGlobalMixedRegimeJointStateFrontierSolveRequest,
  ):
    return _failure(
      status_type.INVALID_INPUT,
      'request must be a typed joint state/frontier solve request',
    )
  ####
  step = request.source_frontier_step
  source_iterations = request.handoff.boundary_feedback_run.iterations
  source_lineage = bool(
    source_iterations
    and step.closure is source_iterations[-1].source_closure
    and step.source_lineage_verified
    and step.fidelity_isolation_verified
  )
  if not request.handoff.ready_for_joint_global_resolve or not source_lineage:
    return _failure(
      status_type.FRONTIER_INPUT_FAILURE,
      'joint solve requires a ready boundary-state handoff and an exact, '
      'locally promotion-blocked source frontier step',
      request=request,
      source_frontier_step=step,
      source_frontier_lineage_verified=source_lineage,
      source_frontier_locally_verified=step.locally_verified,
    )
  ####
  if not step.locally_verified:
    return _failure(
      status_type.FIDELITY_FAILURE,
      'source frontier step did not pass its independent local gates',
      request=request,
      source_frontier_step=step,
      source_frontier_lineage_verified=True,
      source_frontier_locally_verified=False,
    )
  ####
  try:
    joint = run_reflected_domain_global_boundary_state_joint_solve(
      request.handoff,
      boundary_condition_options={
        'consume_target_geometry': True,
        'sample_count': request.frontier_sample_count,
      },
      consumer_id=(
        'moc-global-mixed-regime-joint-state-frontier-solve-v1'
      ),
    )
  except (ArithmeticError, FloatingPointError, RuntimeError, TypeError, ValueError) as error:
    return _failure(
      status_type.GLOBAL_JOINT_SOLVE_FAILURE,
      f'global boundary-state joint solve raised: {error}',
      request=request,
      source_frontier_step=step,
      source_frontier_lineage_verified=True,
      source_frontier_locally_verified=True,
    )
  ####
  if not joint.converged_research_joint_update:
    return _failure(
      status_type.GLOBAL_JOINT_SOLVE_FAILURE,
      'global boundary-state joint solve did not pass its research gates: '
      f'{joint.message}',
      request=request,
      source_frontier_step=step,
      joint_state_solve=joint,
      source_frontier_lineage_verified=True,
      source_frontier_locally_verified=True,
      frontier_resolution_consumed=bool(
        joint.boundary_condition is not None
        and joint.boundary_condition.configuration.get('sample_count')
        == request.frontier_sample_count
      ),
    )
  ####
  candidate = joint.geometry_response_closure
  resolution_consumed = bool(
    candidate is not None
    and candidate.global_euler is not None
    and candidate.global_euler.shock_boundary is not None
    and len(candidate.global_euler.shock_boundary.shock_points_m)
    == request.frontier_sample_count
  )
  if candidate is None or not resolution_consumed:
    return _failure(
      status_type.GLOBAL_JOINT_SOLVE_FAILURE,
      'fresh global state solve did not retain a closure with the exact '
      'frontier-derived shock resolution',
      request=request,
      source_frontier_step=step,
      joint_state_solve=joint,
      source_frontier_lineage_verified=True,
      source_frontier_locally_verified=True,
      frontier_resolution_consumed=resolution_consumed,
      global_joint_solve_verified=False,
    )
  ####
  try:
    refreshed = run_reflected_domain_global_mixed_regime_shock_frontier_step(
      MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementCase(
        case_id=f'{step.case_id}-joint-state-output',
        closure=candidate,
        reference_total_temperature_K=request.reference_total_temperature_K,
        sample_start_index=step.sample_start_index,
        component_tolerance=request.component_tolerance,
      )
    )
  except (ArithmeticError, FloatingPointError, RuntimeError, TypeError, ValueError) as error:
    return _failure(
      status_type.FRONTIER_RECHECK_FAILURE,
      f'refreshed physical shock-frontier solve raised: {error}',
      request=request,
      source_frontier_step=step,
      joint_state_solve=joint,
      source_frontier_lineage_verified=True,
      source_frontier_locally_verified=True,
      frontier_resolution_consumed=True,
      global_joint_solve_verified=True,
    )
  ####
  refreshed_lineage = refreshed.closure is candidate
  refreshed_verified = bool(refreshed_lineage and refreshed.locally_verified)
  if not refreshed_verified:
    return _failure(
      status_type.FRONTIER_RECHECK_FAILURE,
      'fresh global state closure did not pass the physical frontier '
      'lineage and local audit gates',
      request=request,
      source_frontier_step=step,
      joint_state_solve=joint,
      refreshed_frontier_step=refreshed,
      source_frontier_lineage_verified=True,
      source_frontier_locally_verified=True,
      frontier_resolution_consumed=True,
      global_joint_solve_verified=True,
      refreshed_closure_lineage_verified=refreshed_lineage,
      refreshed_frontier_verified=False,
    )
  ####
  return MocReflectedDomainGlobalMixedRegimeJointStateFrontierSolveResult(
    status=status_type.CONVERGED_RESEARCH_JOINT_STATE_FRONTIER,
    request=request,
    source_frontier_step=step,
    joint_state_solve=joint,
    refreshed_frontier_step=refreshed,
    source_frontier_lineage_verified=True,
    source_frontier_locally_verified=True,
    frontier_resolution_consumed=True,
    global_joint_solve_verified=True,
    refreshed_closure_lineage_verified=True,
    refreshed_frontier_verified=True,
    joint_state_frontier_verified=True,
    independent_audit_verified=bool(
      joint.independent_residual_audit_verified
      and refreshed.independent_audits_verified
    ),
    global_coupling_verified=False,
    canonical_free_boundary_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    message=(
      'the frontier-derived resolution was consumed by a fresh global '
      'boundary-state joint solve and the resulting closure passed a new '
      'physical frontier replay; canonical global/free-boundary closure remains '
      'open'
    ),
  )
####


def audit_reflected_domain_global_mixed_regime_joint_state_frontier_solve(
  result: MocReflectedDomainGlobalMixedRegimeJointStateFrontierSolveResult,
) -> MocReflectedDomainGlobalMixedRegimeJointStateFrontierSolveAudit:
  """Replay the exact request and compare the joint state/frontier identity."""

  audit_status = (
    MocReflectedDomainGlobalMixedRegimeJointStateFrontierSolveAuditStatus
  )
  if not isinstance(
    result,
    MocReflectedDomainGlobalMixedRegimeJointStateFrontierSolveResult,
  ):
    return MocReflectedDomainGlobalMixedRegimeJointStateFrontierSolveAudit(
      status=audit_status.INVALID_INPUT,
      candidate=None,
      message='result must be a typed joint state/frontier solve result',
    )
  ####
  if result.request is None:
    return MocReflectedDomainGlobalMixedRegimeJointStateFrontierSolveAudit(
      status=audit_status.REPLAY_FAILURE,
      candidate=result,
      message='joint state/frontier replay requires the retained request',
    )
  ####
  try:
    replay = run_reflected_domain_global_mixed_regime_joint_state_frontier_solve(
      result.request
    )
  except (ArithmeticError, FloatingPointError, RuntimeError, TypeError, ValueError) as error:
    return MocReflectedDomainGlobalMixedRegimeJointStateFrontierSolveAudit(
      status=audit_status.REPLAY_FAILURE,
      candidate=result,
      message=f'joint state/frontier replay raised: {error}',
    )
  ####
  source_replayed = bool(
    replay.source_frontier_step is result.request.source_frontier_step
    and replay.source_frontier_lineage_verified
    == result.source_frontier_lineage_verified
    and replay.source_frontier_locally_verified
    == result.source_frontier_locally_verified
  )
  joint_replayed = bool(
    replay.joint_state_solve is not None
    and replay.joint_state_solve.converged_research_joint_update
    and replay.frontier_resolution_consumed
    == result.frontier_resolution_consumed
    and replay.global_joint_solve_verified
    == result.global_joint_solve_verified
  )
  refreshed_replayed = bool(
    replay.refreshed_frontier_step is not None
    and replay.joint_state_solve is not None
    and replay.refreshed_frontier_step.locally_verified
    and replay.refreshed_frontier_step.closure
    is replay.joint_state_solve.geometry_response_closure
    and replay.refreshed_closure_lineage_verified
    == result.refreshed_closure_lineage_verified
    and replay.refreshed_frontier_verified == result.refreshed_frontier_verified
  )
  request_replayed = bool(replay.request is result.request)
  independent = bool(
    request_replayed
    and replay.status is result.status
    and source_replayed
    and joint_replayed
    and refreshed_replayed
    and replay.joint_state_frontier_verified
    == result.joint_state_frontier_verified
    and replay.converged
    and not replay.global_coupling_verified
    and replay.chain_promotion_blocked
    and not replay.production_claim_allowed
  )
  return MocReflectedDomainGlobalMixedRegimeJointStateFrontierSolveAudit(
    status=(
      audit_status.VERIFIED_RESEARCH_JOINT_STATE_FRONTIER
      if independent
      else audit_status.LINEAGE_FAILURE
    ),
    candidate=result,
    request_replayed=request_replayed,
    source_frontier_replayed=source_replayed,
    global_joint_solve_replayed=joint_replayed,
    refreshed_frontier_replayed=refreshed_replayed,
    independent_joint_state_frontier_verified=independent,
    global_coupling_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    message=(
      'independent replay reproduced the frontier-derived global state solve '
      'and refreshed physical frontier'
      if independent
      else 'independent replay did not reproduce the exact joint state/frontier solve'
    ),
  )
####
