"""Bounded iterative feedback for the global state/frontier joint solver.

Each iteration rebuilds the downstream/global boundary-state handoff from the
fresh closure produced by the previous iteration.  The physical shock
frontier is then consumed by the joint state solver and rechecked on its fresh
closure.  Completing a bounded sequence is not itself a fixed-point claim;
the result exposes separate geometry, pressure, joint-residual, and frontier-
residual convergence gates and remains research-only.  An explicit opt-in can
also consume the bounded five-channel frontier residual exchange after each
joint solve; a rejected exchange stops the chain rather than falling back to
an unexchanged closure.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from math import hypot, isfinite, log
from types import MappingProxyType
from typing import Any

from exhaust_plume.models.moc.global_physical_closure import (
  MocReflectedDomainGlobalPhysicalClosureResult,
  moc_reflected_domain_global_physical_closure_fingerprint,
)
from exhaust_plume.validation.moc_global_boundary_state_feedback import (
  MocReflectedDomainGlobalBoundaryStateFeedbackResult,
  run_reflected_domain_global_boundary_state_feedback,
)
from exhaust_plume.validation.moc_global_mixed_regime_joint_state_frontier_solve import (
  MocReflectedDomainGlobalMixedRegimeJointStateFrontierSolveRequest,
  MocReflectedDomainGlobalMixedRegimeJointStateFrontierSolveResult,
  run_reflected_domain_global_mixed_regime_joint_state_frontier_solve,
)
from exhaust_plume.validation.moc_global_mixed_regime_frontier_residual_exchange import (
  MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeRequest,
  MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeResult,
  run_reflected_domain_global_mixed_regime_frontier_residual_exchange,
)
from exhaust_plume.validation.moc_global_mixed_regime_shock_frontier_refinement import (
  MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementCase,
  MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementStep,
  run_reflected_domain_global_mixed_regime_shock_frontier_step,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_JOINT_STATE_FRONTIER_FEEDBACK_OPERATOR_ID',
  'MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackStatus',
  'MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackRequest',
  'MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackIteration',
  'MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackResult',
  'MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackAuditStatus',
  'MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackAudit',
  'run_reflected_domain_global_mixed_regime_joint_state_frontier_feedback',
  'audit_reflected_domain_global_mixed_regime_joint_state_frontier_feedback',
)


MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_JOINT_STATE_FRONTIER_FEEDBACK_OPERATOR_ID = (
  'op.moc.reflected-domain.global-mixed-regime-joint-state-frontier-feedback-v1'
)


class MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackStatus(
  str,
  Enum,
):
  """Typed outcomes of the bounded joint feedback sequence."""

  CONVERGED_RESEARCH_JOINT_STATE_FRONTIER_FEEDBACK = (
    'converged-research-joint-state-frontier-feedback'
  )
  COMPLETED_RESEARCH_JOINT_STATE_FRONTIER_FEEDBACK_WITH_OPEN_CONVERGENCE = (
    'completed-research-joint-state-frontier-feedback-with-open-convergence'
  )
  INVALID_INPUT = 'invalid_input'
  FEEDBACK_FAILURE = 'joint-state-frontier-feedback-boundary-state-failure'
  FRONTIER_FAILURE = 'joint-state-frontier-feedback-frontier-failure'
  JOINT_SOLVE_FAILURE = 'joint-state-frontier-feedback-joint-solve-failure'
  RESIDUAL_EXCHANGE_FAILURE = (
    'joint-state-frontier-feedback-residual-exchange-failure'
  )
  RESIDUAL_DESCENT_FAILURE = (
    'joint-state-frontier-feedback-residual-descent-failure'
  )
  AUDIT_REQUIRED = 'joint-state-frontier-feedback-audit-required'


class MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackAuditStatus(
  str,
  Enum,
):
  """Typed outcomes of the independent feedback replay."""

  VERIFIED_RESEARCH_JOINT_STATE_FRONTIER_FEEDBACK = (
    'verified-research-joint-state-frontier-feedback'
  )
  INVALID_INPUT = 'invalid_input'
  REPLAY_FAILURE = 'joint-state-frontier-feedback-audit-replay-failure'
  LINEAGE_FAILURE = 'joint-state-frontier-feedback-audit-lineage-failure'


def _mapping(
  value: Mapping[str, Any] | None,
  name: str,
) -> MappingProxyType[str, Any]:
  if value is None:
    return MappingProxyType({})
  if not isinstance(value, Mapping):
    raise TypeError(f'{name} must be a mapping when supplied')
  return MappingProxyType(dict(value))


def _positive(value: Any, name: str) -> float:
  numeric = float(value)
  if not isfinite(numeric) or numeric <= 0.0:
    raise ValueError(f'{name} must be finite and positive')
  return numeric


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackRequest:
  """Controls for a bounded sequence of frontier-integrated solves."""

  source_closure: MocReflectedDomainGlobalPhysicalClosureResult
  reference_total_temperature_K: float
  maximum_iterations: int = 2
  downstream_feedback_iterations: int = 2
  maximum_frame_extension_m: float = 0.5
  downstream_options: Mapping[str, Any] | None = None
  two_sided_request_options: Mapping[str, Any] | None = None
  frontier_component_tolerance: float = 1.0e-5
  fixed_point_geometry_tolerance_m: float = 1.0e-3
  fixed_point_pressure_log_tolerance: float = 1.0e-3
  fixed_point_residual_tolerance: float = 1.0e-3
  require_fixed_point: bool = False
  require_residual_descent: bool = False
  source: str = 'research-global-mixed-regime-joint-state-frontier-feedback-v1'
  consume_frontier_residual_exchange: bool = False
  frontier_residual_exchange_options: Mapping[str, Any] | None = None

  def __post_init__(self) -> None:
    if not isinstance(
      self.source_closure,
      MocReflectedDomainGlobalPhysicalClosureResult,
    ):
      raise TypeError('source_closure must be a typed global physical closure')
    for name in ('maximum_iterations', 'downstream_feedback_iterations'):
      value = getattr(self, name)
      minimum = 1 if name == 'maximum_iterations' else 2
      if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f'{name} must be an integer >= {minimum}')
    object.__setattr__(
      self,
      'reference_total_temperature_K',
      _positive(self.reference_total_temperature_K, 'reference_total_temperature_K'),
    )
    object.__setattr__(
      self,
      'maximum_frame_extension_m',
      _positive(self.maximum_frame_extension_m, 'maximum_frame_extension_m'),
    )
    for name in (
      'frontier_component_tolerance',
      'fixed_point_geometry_tolerance_m',
      'fixed_point_pressure_log_tolerance',
      'fixed_point_residual_tolerance',
    ):
      object.__setattr__(self, name, _positive(getattr(self, name), name))
    for name in ('require_fixed_point', 'require_residual_descent'):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    if not isinstance(self.consume_frontier_residual_exchange, bool):
      raise TypeError('consume_frontier_residual_exchange must be a bool')
    object.__setattr__(
      self,
      'downstream_options',
      _mapping(self.downstream_options, 'downstream_options'),
    )
    resolved_two_sided = dict(
      _mapping(self.two_sided_request_options, 'two_sided_request_options')
    )
    resolved_two_sided.setdefault('normal_momentum_tolerance_Pa', 100.0)
    object.__setattr__(
      self,
      'two_sided_request_options',
      MappingProxyType(resolved_two_sided),
    )
    object.__setattr__(
      self,
      'frontier_residual_exchange_options',
      _mapping(
        self.frontier_residual_exchange_options,
        'frontier_residual_exchange_options',
      ),
    )
    source = str(self.source)
    if not source:
      raise ValueError('source must be non-empty')
    object.__setattr__(self, 'source', source)

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': (
        MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_JOINT_STATE_FRONTIER_FEEDBACK_OPERATOR_ID
      ),
      'source': self.source,
      'reference_total_temperature_K': self.reference_total_temperature_K,
      'maximum_iterations': self.maximum_iterations,
      'downstream_feedback_iterations': self.downstream_feedback_iterations,
      'maximum_frame_extension_m': self.maximum_frame_extension_m,
      'frontier_component_tolerance': self.frontier_component_tolerance,
      'fixed_point_geometry_tolerance_m': self.fixed_point_geometry_tolerance_m,
      'fixed_point_pressure_log_tolerance': self.fixed_point_pressure_log_tolerance,
      'fixed_point_residual_tolerance': self.fixed_point_residual_tolerance,
      'require_fixed_point': self.require_fixed_point,
      'require_residual_descent': self.require_residual_descent,
      'consume_frontier_residual_exchange': (
        self.consume_frontier_residual_exchange
      ),
      'frontier_residual_exchange_options': dict(
        self.frontier_residual_exchange_options or {}
      ),
      'source_closure_fingerprint': moc_reflected_domain_global_physical_closure_fingerprint(
        self.source_closure
      ),
      'downstream_options': dict(self.downstream_options or {}),
      'two_sided_request_options': dict(self.two_sided_request_options or {}),
      'research_only': True,
      'production_claim_allowed': False,
    }


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackIteration:
  """One rebuilt handoff and frontier-integrated global update."""

  iteration_index: int
  source_closure: MocReflectedDomainGlobalPhysicalClosureResult
  boundary_state_feedback: MocReflectedDomainGlobalBoundaryStateFeedbackResult
  source_frontier_step: MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementStep | None = None
  joint_solve: MocReflectedDomainGlobalMixedRegimeJointStateFrontierSolveResult | None = None
  next_closure: MocReflectedDomainGlobalPhysicalClosureResult | None = None
  geometry_delta_m: float | None = None
  pressure_log_delta: float | None = None
  joint_residual_norm: float | None = None
  source_lineage_verified: bool = False
  boundary_state_feedback_verified: bool = False
  frontier_step_verified: bool = False
  joint_solve_verified: bool = False
  next_closure_lineage_verified: bool = False
  fixed_point_verified: bool = False
  residual_descent_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''
  frontier_residual_exchange: MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeResult | None = None
  frontier_residual_norm: float | None = None
  frontier_residual_exchange_verified: bool = False

  def __post_init__(self) -> None:
    if isinstance(self.iteration_index, bool) or not isinstance(self.iteration_index, int) or self.iteration_index < 0:
      raise ValueError('iteration_index must be a nonnegative integer')
    if not isinstance(self.source_closure, MocReflectedDomainGlobalPhysicalClosureResult):
      raise TypeError('source_closure must be a typed global physical closure')
    if not isinstance(self.boundary_state_feedback, MocReflectedDomainGlobalBoundaryStateFeedbackResult):
      raise TypeError('boundary_state_feedback must be a typed result')
    for name, expected in (
      ('source_frontier_step', MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementStep),
      ('joint_solve', MocReflectedDomainGlobalMixedRegimeJointStateFrontierSolveResult),
      (
        'frontier_residual_exchange',
        MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeResult,
      ),
      ('next_closure', MocReflectedDomainGlobalPhysicalClosureResult),
    ):
      value = getattr(self, name)
      if value is not None and not isinstance(value, expected):
        raise TypeError(f'{name} must retain its typed result or None')
    for name in (
      'source_lineage_verified',
      'boundary_state_feedback_verified',
      'frontier_step_verified',
      'joint_solve_verified',
      'frontier_residual_exchange_verified',
      'next_closure_lineage_verified',
      'fixed_point_verified',
      'residual_descent_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    for name in (
      'geometry_delta_m',
      'pressure_log_delta',
      'joint_residual_norm',
      'frontier_residual_norm',
    ):
      value = getattr(self, name)
      if value is not None:
        numeric = float(value)
        if not isfinite(numeric) or numeric < 0.0:
          raise ValueError(f'{name} must be finite and nonnegative')
        object.__setattr__(self, name, numeric)
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError('feedback iterations must remain promotion-blocked')
    object.__setattr__(self, 'message', str(self.message))

  @property
  def research_step_verified(self) -> bool:
    return bool(
      self.source_lineage_verified
      and self.boundary_state_feedback_verified
      and self.frontier_step_verified
      and self.joint_solve_verified
      and (
        (
          self.frontier_residual_exchange is None
          and not self.frontier_residual_exchange_verified
        )
        or (
          self.frontier_residual_exchange is not None
          and self.frontier_residual_exchange_verified
          and self.frontier_residual_exchange.converged
        )
      )
      and self.next_closure_lineage_verified
      and self.next_closure is not None
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
    )

  def as_report(self) -> dict[str, Any]:
    return {
      'iteration_index': self.iteration_index,
      'source_closure_fingerprint': moc_reflected_domain_global_physical_closure_fingerprint(
        self.source_closure
      ),
      'next_closure_fingerprint': (
        None
        if self.next_closure is None
        else moc_reflected_domain_global_physical_closure_fingerprint(self.next_closure)
      ),
      'geometry_delta_m': self.geometry_delta_m,
      'pressure_log_delta': self.pressure_log_delta,
      'joint_residual_norm': self.joint_residual_norm,
      'frontier_residual_norm': self.frontier_residual_norm,
      'source_lineage_verified': self.source_lineage_verified,
      'boundary_state_feedback_verified': self.boundary_state_feedback_verified,
      'frontier_step_verified': self.frontier_step_verified,
      'joint_solve_verified': self.joint_solve_verified,
      'frontier_residual_exchange_verified': (
        self.frontier_residual_exchange_verified
      ),
      'next_closure_lineage_verified': self.next_closure_lineage_verified,
      'fixed_point_verified': self.fixed_point_verified,
      'residual_descent_verified': self.residual_descent_verified,
      'research_step_verified': self.research_step_verified,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'boundary_state_feedback': self.boundary_state_feedback.as_report(),
      'source_frontier_step': (
        None
        if self.source_frontier_step is None
        else self.source_frontier_step.as_report()
      ),
      'joint_solve': None if self.joint_solve is None else self.joint_solve.as_report(),
      'frontier_residual_exchange': (
        None
        if self.frontier_residual_exchange is None
        else self.frontier_residual_exchange.as_report()
      ),
      'message': self.message,
    }


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackResult:
  """Bounded iterative research result with separate convergence gates."""

  status: MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackStatus
  request: MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackRequest | None
  source_closure: MocReflectedDomainGlobalPhysicalClosureResult | None = None
  final_closure: MocReflectedDomainGlobalPhysicalClosureResult | None = None
  iterations: tuple[MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackIteration, ...] = ()
  feedback_completed: bool = False
  frontier_chain_verified: bool = False
  joint_solve_chain_verified: bool = False
  fixed_point_verified: bool = False
  residual_descent_verified: bool = False
  independent_audit_verified: bool = False
  global_coupling_verified: bool = False
  canonical_free_boundary_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''
  frontier_residual_exchange_chain_verified: bool = False

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackStatus):
      raise TypeError('status must be a typed joint-feedback status')
    if self.request is not None and not isinstance(
      self.request,
      MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackRequest,
    ):
      raise TypeError('request must be a typed joint-feedback request')
    for name, expected in (
      ('source_closure', MocReflectedDomainGlobalPhysicalClosureResult),
      ('final_closure', MocReflectedDomainGlobalPhysicalClosureResult),
    ):
      value = getattr(self, name)
      if value is not None and not isinstance(value, expected):
        raise TypeError(f'{name} must retain a typed closure or None')
    iterations = tuple(self.iterations)
    if any(
      not isinstance(
        iteration,
        MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackIteration,
      )
      for iteration in iterations
    ):
      raise TypeError('iterations must contain typed joint-feedback iterations')
    if tuple(item.iteration_index for item in iterations) != tuple(range(len(iterations))):
      raise ValueError('iterations must have contiguous zero-based indices')
    object.__setattr__(self, 'iterations', iterations)
    for name in (
      'feedback_completed',
      'frontier_chain_verified',
      'joint_solve_chain_verified',
      'frontier_residual_exchange_chain_verified',
      'fixed_point_verified',
      'residual_descent_verified',
      'independent_audit_verified',
      'global_coupling_verified',
      'canonical_free_boundary_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    if self.global_coupling_verified or self.canonical_free_boundary_verified:
      raise ValueError('joint feedback cannot claim canonical closure')
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError('joint feedback must remain promotion-blocked')
    object.__setattr__(self, 'message', str(self.message))

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackStatus
      .CONVERGED_RESEARCH_JOINT_STATE_FRONTIER_FEEDBACK
      and self.feedback_completed
      and self.frontier_chain_verified
      and self.joint_solve_chain_verified
      and self.frontier_residual_exchange_chain_verified
      and self.fixed_point_verified
      and self.residual_descent_verified
      and self.independent_audit_verified
      and self.chain_promotion_blocked
      and not self.global_coupling_verified
      and not self.canonical_free_boundary_verified
      and not self.production_claim_allowed
    )

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': (
        MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_JOINT_STATE_FRONTIER_FEEDBACK_OPERATOR_ID
      ),
      'status': self.status.value,
      'converged': self.converged,
      'feedback_completed': self.feedback_completed,
      'frontier_chain_verified': self.frontier_chain_verified,
      'joint_solve_chain_verified': self.joint_solve_chain_verified,
      'frontier_residual_exchange_chain_verified': (
        self.frontier_residual_exchange_chain_verified
      ),
      'fixed_point_verified': self.fixed_point_verified,
      'residual_descent_verified': self.residual_descent_verified,
      'independent_audit_verified': self.independent_audit_verified,
      'global_coupling_verified': False,
      'canonical_free_boundary_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'source_closure': (
        None
        if self.source_closure is None
        else self.source_closure.as_report()
      ),
      'final_closure': (
        None
        if self.final_closure is None
        else self.final_closure.as_report()
      ),
      'iterations': tuple(item.as_report() for item in self.iterations),
      'request': None if self.request is None else self.request.as_report(),
      'claim_status': (
        'research-only bounded joint state/frontier feedback; a finite '
        'iteration sequence is not a canonical global fixed point or a '
        'production product source'
      ),
      'message': self.message,
    }


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackAudit:
  """Independent replay audit for the bounded feedback sequence."""

  status: MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackAuditStatus
  candidate: MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackResult | None
  request_replayed: bool = False
  iteration_count_replayed: bool = False
  closure_lineage_replayed: bool = False
  frontier_chain_replayed: bool = False
  joint_chain_replayed: bool = False
  convergence_flags_replayed: bool = False
  independent_joint_feedback_verified: bool = False
  global_coupling_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''
  residual_exchange_chain_replayed: bool = False

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackAuditStatus,
    ):
      raise TypeError('status must be a typed joint-feedback audit status')
    if self.candidate is not None and not isinstance(
      self.candidate,
      MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackResult,
    ):
      raise TypeError('candidate must be a typed joint-feedback result')
    for name in (
      'request_replayed',
      'iteration_count_replayed',
      'closure_lineage_replayed',
      'frontier_chain_replayed',
      'joint_chain_replayed',
      'residual_exchange_chain_replayed',
      'convergence_flags_replayed',
      'independent_joint_feedback_verified',
      'global_coupling_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    if self.global_coupling_verified or not self.chain_promotion_blocked:
      raise ValueError('joint-feedback audit must remain promotion-blocked')
    if self.production_claim_allowed:
      raise ValueError('joint-feedback audit cannot allow production claims')
    object.__setattr__(self, 'message', str(self.message))

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackAuditStatus
      .VERIFIED_RESEARCH_JOINT_STATE_FRONTIER_FEEDBACK
      and self.independent_joint_feedback_verified
    )

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': (
        MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_JOINT_STATE_FRONTIER_FEEDBACK_OPERATOR_ID
      ),
      'audit_status': self.status.value,
      'converged': self.converged,
      'request_replayed': self.request_replayed,
      'iteration_count_replayed': self.iteration_count_replayed,
      'closure_lineage_replayed': self.closure_lineage_replayed,
      'frontier_chain_replayed': self.frontier_chain_replayed,
      'joint_chain_replayed': self.joint_chain_replayed,
      'residual_exchange_chain_replayed': (
        self.residual_exchange_chain_replayed
      ),
      'convergence_flags_replayed': self.convergence_flags_replayed,
      'independent_joint_feedback_verified': (
        self.independent_joint_feedback_verified
      ),
      'global_coupling_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'candidate': (
        None if self.candidate is None else self.candidate.as_report()
      ),
      'message': self.message,
    }


def _failure(
  status: MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackStatus,
  message: str,
  *,
  request: MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackRequest | None = None,
  source_closure: MocReflectedDomainGlobalPhysicalClosureResult | None = None,
  final_closure: MocReflectedDomainGlobalPhysicalClosureResult | None = None,
  iterations: tuple[MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackIteration, ...] = (),
  **values: Any,
) -> MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackResult:
  return MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackResult(
    status=status,
    request=request,
    source_closure=source_closure,
    final_closure=final_closure,
    iterations=iterations,
    message=message,
    **values,
  )


def _closure_deltas(
  source: MocReflectedDomainGlobalPhysicalClosureResult,
  candidate: MocReflectedDomainGlobalPhysicalClosureResult,
) -> tuple[float, float]:
  source_euler = source.global_euler
  candidate_euler = candidate.global_euler
  source_shock = None if source_euler is None else source_euler.shock_boundary
  candidate_shock = None if candidate_euler is None else candidate_euler.shock_boundary
  if source_shock is None or candidate_shock is None:
    return float('inf'), float('inf')
  if len(source_shock.shock_points_m) != len(candidate_shock.shock_points_m):
    return float('inf'), float('inf')
  geometry = max(
    (
      hypot(
        first[0] - second[0],
        first[1] - second[1],
      )
      for first, second in zip(
        source_shock.shock_points_m,
        candidate_shock.shock_points_m,
        strict=True,
      )
    ),
    default=float('inf'),
  )
  source_pressure = source_shock.downstream_total_pressure_Pa
  candidate_pressure = candidate_shock.downstream_total_pressure_Pa
  if len(source_pressure) != len(candidate_pressure):
    return geometry, float('inf')
  pressure = max(
    (
      abs(log(float(left) / float(right)))
      if left > 0.0 and right > 0.0
      else float('inf')
      for left, right in zip(source_pressure, candidate_pressure, strict=True)
    ),
    default=float('inf'),
  )
  return float(geometry), float(pressure)


def _residual_descent(
  values: tuple[float, ...],
  *,
  required: bool,
) -> bool:
  if any(not isfinite(value) or value < 0.0 for value in values):
    return False
  if not required:
    return bool(values)
  if len(values) < 2:
    return False
  return bool(all(right < left for left, right in zip(values, values[1:])))


def run_reflected_domain_global_mixed_regime_joint_state_frontier_feedback(
  request: MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackRequest,
) -> MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackResult:
  """Run bounded feedback with a fresh physical frontier at every step."""

  status_type = MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackStatus
  if not isinstance(
    request,
    MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackRequest,
  ):
    return _failure(
      status_type.INVALID_INPUT,
      'request must be a typed joint state/frontier feedback request',
    )
  current = request.source_closure
  retained: list[
    MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackIteration
  ] = []
  for iteration_index in range(request.maximum_iterations):
    try:
      feedback = run_reflected_domain_global_boundary_state_feedback(
        current,
        reference_total_temperature_K=request.reference_total_temperature_K,
        downstream_feedback_iterations=request.downstream_feedback_iterations,
        maximum_frame_extension_m=request.maximum_frame_extension_m,
        consumer_id=(
          'moc-global-mixed-regime-joint-state-frontier-feedback-'
          f'{iteration_index}'
        ),
        downstream_options=dict(request.downstream_options or {}),
        boundary_condition_options={'consume_target_geometry': True},
        two_sided_request_options=dict(request.two_sided_request_options or {}),
      )
    except (ArithmeticError, FloatingPointError, RuntimeError, TypeError, ValueError) as error:
      return _failure(
        status_type.FEEDBACK_FAILURE,
        f'boundary-state feedback iteration {iteration_index} raised: {error}',
        request=request,
        source_closure=request.source_closure,
        final_closure=current,
        iterations=tuple(retained),
        feedback_completed=False,
        frontier_chain_verified=False,
        joint_solve_chain_verified=False,
        independent_audit_verified=False,
      )
    source_lineage = bool(
      feedback.source_closure is current
      and feedback.boundary_feedback_run is not None
      and feedback.boundary_feedback_run.source_closure is current
    )
    if not feedback.handoff_ready or not source_lineage:
      return _failure(
        status_type.FEEDBACK_FAILURE,
        'boundary-state feedback did not return a ready handoff with exact '
        f'source closure lineage: {feedback.message}',
        request=request,
        source_closure=request.source_closure,
        final_closure=current,
        iterations=tuple(retained),
        feedback_completed=False,
        frontier_chain_verified=False,
        joint_solve_chain_verified=False,
        independent_audit_verified=False,
      )
    assert feedback.handoff is not None
    handoff_source = feedback.handoff.boundary_feedback_run.iterations[-1].source_closure
    if handoff_source is not current:
      return _failure(
        status_type.FEEDBACK_FAILURE,
        'boundary-state handoff source closure did not retain the exact '
        'current feedback closure',
        request=request,
        source_closure=request.source_closure,
        final_closure=current,
        iterations=tuple(retained),
        feedback_completed=False,
        frontier_chain_verified=False,
        joint_solve_chain_verified=False,
        independent_audit_verified=False,
      )
    try:
      frontier_step = run_reflected_domain_global_mixed_regime_shock_frontier_step(
        MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementCase(
          case_id=f'joint-feedback-{iteration_index}',
          closure=handoff_source,
          reference_total_temperature_K=request.reference_total_temperature_K,
          component_tolerance=request.frontier_component_tolerance,
        )
      )
    except (ArithmeticError, FloatingPointError, RuntimeError, TypeError, ValueError) as error:
      return _failure(
        status_type.FRONTIER_FAILURE,
        f'physical frontier iteration {iteration_index} raised: {error}',
        request=request,
        source_closure=request.source_closure,
        final_closure=current,
        iterations=tuple(retained),
        feedback_completed=False,
        frontier_chain_verified=False,
        joint_solve_chain_verified=False,
        independent_audit_verified=False,
      )
    frontier_verified = bool(
      frontier_step.closure is handoff_source
      and frontier_step.locally_verified
    )
    if not frontier_verified:
      return _failure(
        status_type.FRONTIER_FAILURE,
        'physical frontier iteration did not pass its local lineage and '
        'independent audit gates',
        request=request,
        source_closure=request.source_closure,
        final_closure=current,
        iterations=tuple(retained),
        feedback_completed=False,
        frontier_chain_verified=False,
        joint_solve_chain_verified=False,
        independent_audit_verified=False,
      )
    try:
      joint = run_reflected_domain_global_mixed_regime_joint_state_frontier_solve(
        MocReflectedDomainGlobalMixedRegimeJointStateFrontierSolveRequest(
          handoff=feedback.handoff,
          source_frontier_step=frontier_step,
          reference_total_temperature_K=request.reference_total_temperature_K,
          component_tolerance=request.frontier_component_tolerance,
        )
      )
    except (ArithmeticError, FloatingPointError, RuntimeError, TypeError, ValueError) as error:
      return _failure(
        status_type.JOINT_SOLVE_FAILURE,
        f'joint state/frontier solve iteration {iteration_index} raised: {error}',
        request=request,
        source_closure=request.source_closure,
        final_closure=current,
        iterations=tuple(retained),
        feedback_completed=False,
        frontier_chain_verified=False,
        joint_solve_chain_verified=False,
        independent_audit_verified=False,
      )
    next_closure = (
      None
      if joint.joint_state_solve is None
      else joint.joint_state_solve.geometry_response_closure
    )
    joint_verified = bool(joint.converged and next_closure is not None)
    if not joint_verified:
      return _failure(
        status_type.JOINT_SOLVE_FAILURE,
        f'joint state/frontier solve did not pass its research gates: {joint.message}',
        request=request,
        source_closure=request.source_closure,
        final_closure=current,
        iterations=tuple(retained),
        feedback_completed=False,
        frontier_chain_verified=False,
        joint_solve_chain_verified=False,
        independent_audit_verified=False,
      )
    assert next_closure is not None
    frontier_residual_exchange = None
    frontier_residual_exchange_verified = False
    if request.consume_frontier_residual_exchange:
      exchange_options = dict(
        request.frontier_residual_exchange_options or {}
      )
      collisions = tuple(
        key
        for key in (
          'source_frontier_step',
          'target_closure',
          'reference_total_temperature_K',
        )
        if key in exchange_options
      )
      if collisions:
        return _failure(
          status_type.RESIDUAL_EXCHANGE_FAILURE,
          'frontier residual exchange options cannot override positional '
          f'controls: {", ".join(collisions)}',
          request=request,
          source_closure=request.source_closure,
          final_closure=current,
          iterations=tuple(retained),
          feedback_completed=False,
          frontier_chain_verified=False,
          joint_solve_chain_verified=False,
          independent_audit_verified=False,
        )
      try:
        frontier_residual_exchange = (
          run_reflected_domain_global_mixed_regime_frontier_residual_exchange(
            MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeRequest(
              source_frontier_step=frontier_step,
              target_closure=next_closure,
              reference_total_temperature_K=(
                request.reference_total_temperature_K
              ),
              **exchange_options,
            )
          )
        )
      except (
        ArithmeticError,
        FloatingPointError,
        RuntimeError,
        TypeError,
        ValueError,
      ) as error:
        return _failure(
          status_type.RESIDUAL_EXCHANGE_FAILURE,
          f'frontier residual exchange iteration {iteration_index} raised: '
          f'{error}',
          request=request,
          source_closure=request.source_closure,
          final_closure=current,
          iterations=tuple(retained),
          feedback_completed=False,
          frontier_chain_verified=False,
          joint_solve_chain_verified=False,
          independent_audit_verified=False,
        )
      frontier_residual_exchange_verified = (
        frontier_residual_exchange.converged
      )
      if frontier_residual_exchange.final_closure is not None:
        next_closure = frontier_residual_exchange.final_closure
    geometry_delta, pressure_delta = _closure_deltas(current, next_closure)
    residual_norm = (
      None
      if joint.joint_state_solve is None
      else joint.joint_state_solve.refreshed_residual_norm
    )
    frontier_residual_norm = (
      None
      if frontier_residual_exchange is None
      or frontier_residual_exchange.final_packet is None
      else frontier_residual_exchange.final_packet.residual_norm
    )
    previous_residuals = tuple(
      item.joint_residual_norm
      for item in retained
      if item.joint_residual_norm is not None
    )
    residual_descent = bool(
      joint.joint_state_solve is not None
      and joint.joint_state_solve.residual_descent_verified
      and (
        not previous_residuals
        or residual_norm is not None and residual_norm < previous_residuals[-1]
      )
    )
    fixed = bool(
      isfinite(geometry_delta)
      and isfinite(pressure_delta)
      and residual_norm is not None
      and isfinite(float(residual_norm))
      and geometry_delta <= request.fixed_point_geometry_tolerance_m
      and pressure_delta <= request.fixed_point_pressure_log_tolerance
      and float(residual_norm) <= request.fixed_point_residual_tolerance
    )
    iteration = MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackIteration(
      iteration_index=iteration_index,
      source_closure=current,
      boundary_state_feedback=feedback,
      source_frontier_step=frontier_step,
      joint_solve=joint,
      frontier_residual_exchange=frontier_residual_exchange,
      next_closure=next_closure,
      geometry_delta_m=geometry_delta,
      pressure_log_delta=pressure_delta,
      joint_residual_norm=residual_norm,
      frontier_residual_norm=frontier_residual_norm,
      source_lineage_verified=source_lineage,
      boundary_state_feedback_verified=feedback.handoff_ready,
      frontier_step_verified=frontier_verified,
      joint_solve_verified=joint_verified,
      frontier_residual_exchange_verified=frontier_residual_exchange_verified,
      next_closure_lineage_verified=(
        (
          next_closure is frontier_residual_exchange.final_closure
          if frontier_residual_exchange is not None
          else next_closure is joint.joint_state_solve.geometry_response_closure
        )
      ),
      fixed_point_verified=fixed,
      residual_descent_verified=residual_descent,
      chain_promotion_blocked=True,
      production_claim_allowed=False,
      message=(
        'fresh boundary-state feedback, physical frontier, and joint global '
        'state solve completed'
        + (
          '; bounded frontier residual exchange was independently admitted; '
          'fixed-point residuals remain open'
          if frontier_residual_exchange is not None
          and frontier_residual_exchange_verified
          else '; fixed-point residuals remain open'
        )
      ),
    )
    retained.append(iteration)
    if (
      request.consume_frontier_residual_exchange
      and not frontier_residual_exchange_verified
    ):
      return _failure(
        status_type.RESIDUAL_EXCHANGE_FAILURE,
        'joint state/frontier solve completed, but the required bounded '
        'frontier residual exchange did not pass its admission and replay '
        f'gates: {frontier_residual_exchange.message if frontier_residual_exchange is not None else "no result"}',
        request=request,
        source_closure=request.source_closure,
        final_closure=next_closure,
        iterations=tuple(retained),
        feedback_completed=False,
        frontier_chain_verified=bool(
          retained and all(item.frontier_step_verified for item in retained)
        ),
        joint_solve_chain_verified=False,
        frontier_residual_exchange_chain_verified=False,
        independent_audit_verified=False,
      )
    current = next_closure
  ####
  iterations = tuple(retained)
  frontier_chain = bool(iterations and all(item.frontier_step_verified for item in iterations))
  joint_chain = bool(iterations and all(item.research_step_verified for item in iterations))
  frontier_residual_exchange_chain = bool(
    not request.consume_frontier_residual_exchange
    or (
      iterations
      and all(
        item.frontier_residual_exchange_verified
        and item.frontier_residual_exchange is not None
        and item.frontier_residual_exchange.converged
        for item in iterations
      )
    )
  )
  fixed = bool(iterations and all(item.fixed_point_verified for item in iterations))
  residuals = tuple(
    item.joint_residual_norm
    for item in iterations
    if item.joint_residual_norm is not None
  )
  residual_descent = bool(
    iterations
    and all(item.residual_descent_verified for item in iterations)
    and _residual_descent(residuals, required=request.require_residual_descent)
  )
  independent = bool(
    iterations
    and all(
      item.joint_solve is not None
      and item.joint_solve.independent_audit_verified
      for item in iterations
    )
  )
  if request.require_residual_descent and not residual_descent:
    status = status_type.RESIDUAL_DESCENT_FAILURE
    message = 'joint feedback residuals did not satisfy the declared descent policy'
  elif request.require_fixed_point and not fixed:
    status = status_type.COMPLETED_RESEARCH_JOINT_STATE_FRONTIER_FEEDBACK_WITH_OPEN_CONVERGENCE
    message = 'all bounded joint feedback steps completed, but fixed-point residuals remain open'
  elif fixed and residual_descent and independent:
    status = status_type.CONVERGED_RESEARCH_JOINT_STATE_FRONTIER_FEEDBACK
    message = 'bounded joint state/frontier feedback met the declared research fixed-point and residual gates'
  else:
    status = status_type.COMPLETED_RESEARCH_JOINT_STATE_FRONTIER_FEEDBACK_WITH_OPEN_CONVERGENCE
    message = 'all bounded joint state/frontier feedback steps completed; fixed-point or residual convergence remains open'
  return MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackResult(
    status=status,
    request=request,
    source_closure=request.source_closure,
    final_closure=current,
    iterations=iterations,
    feedback_completed=bool(len(iterations) == request.maximum_iterations),
    frontier_chain_verified=frontier_chain,
    joint_solve_chain_verified=joint_chain,
    frontier_residual_exchange_chain_verified=frontier_residual_exchange_chain,
    fixed_point_verified=fixed,
    residual_descent_verified=residual_descent,
    independent_audit_verified=independent,
    global_coupling_verified=False,
    canonical_free_boundary_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    message=message,
  )


def audit_reflected_domain_global_mixed_regime_joint_state_frontier_feedback(
  result: MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackResult,
) -> MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackAudit:
  """Replay the exact bounded sequence and compare its lineage and gates."""

  audit_status = (
    MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackAuditStatus
  )
  if not isinstance(
    result,
    MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackResult,
  ):
    return MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackAudit(
      status=audit_status.INVALID_INPUT,
      candidate=None,
      message='result must be a typed joint-feedback result',
    )
  if result.request is None:
    return MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackAudit(
      status=audit_status.REPLAY_FAILURE,
      candidate=result,
      message='joint-feedback replay requires the retained request',
    )
  try:
    replay = run_reflected_domain_global_mixed_regime_joint_state_frontier_feedback(
      result.request
    )
  except (ArithmeticError, FloatingPointError, RuntimeError, TypeError, ValueError) as error:
    return MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackAudit(
      status=audit_status.REPLAY_FAILURE,
      candidate=result,
      message=f'joint-feedback replay raised: {error}',
    )
  request_replayed = replay.request is result.request
  count_replayed = len(replay.iterations) == len(result.iterations)
  source_fingerprints = tuple(
    moc_reflected_domain_global_physical_closure_fingerprint(item.source_closure)
    for item in result.iterations
  )
  replay_source_fingerprints = tuple(
    moc_reflected_domain_global_physical_closure_fingerprint(item.source_closure)
    for item in replay.iterations
  )
  next_fingerprints = tuple(
    None
    if item.next_closure is None
    else moc_reflected_domain_global_physical_closure_fingerprint(item.next_closure)
    for item in result.iterations
  )
  replay_next_fingerprints = tuple(
    None
    if item.next_closure is None
    else moc_reflected_domain_global_physical_closure_fingerprint(item.next_closure)
    for item in replay.iterations
  )
  closure_lineage = bool(
    source_fingerprints == replay_source_fingerprints
    and next_fingerprints == replay_next_fingerprints
    and (
      result.final_closure is None
      or replay.final_closure is not None
      and moc_reflected_domain_global_physical_closure_fingerprint(result.final_closure)
      == moc_reflected_domain_global_physical_closure_fingerprint(replay.final_closure)
    )
  )
  frontier_chain = bool(
    count_replayed
    and all(
      replay_item.frontier_step_verified == result_item.frontier_step_verified
      and replay_item.source_frontier_step is not None
      and replay_item.source_frontier_step.locally_verified
      for replay_item, result_item in zip(
        replay.iterations,
        result.iterations,
        strict=True,
      )
    )
  )
  joint_chain = bool(
    count_replayed
    and all(
      replay_item.joint_solve_verified == result_item.joint_solve_verified
      and replay_item.joint_solve is not None
      and replay_item.joint_solve.converged
      for replay_item, result_item in zip(
        replay.iterations,
        result.iterations,
        strict=True,
      )
    )
  )
  residual_exchange_chain = bool(
    count_replayed
    and all(
      replay_item.frontier_residual_exchange_verified
      == result_item.frontier_residual_exchange_verified
      and (
        (
          replay_item.frontier_residual_exchange is None
          and result_item.frontier_residual_exchange is None
        )
        or (
          replay_item.frontier_residual_exchange is not None
          and result_item.frontier_residual_exchange is not None
          and replay_item.frontier_residual_exchange.status
          is result_item.frontier_residual_exchange.status
          and replay_item.frontier_residual_exchange.final_packet is not None
          and result_item.frontier_residual_exchange.final_packet is not None
          and replay_item.frontier_residual_exchange.final_packet.fingerprint
          == result_item.frontier_residual_exchange.final_packet.fingerprint
          and replay_item.frontier_residual_exchange.final_closure is not None
          and result_item.frontier_residual_exchange.final_closure is not None
          and moc_reflected_domain_global_physical_closure_fingerprint(
            replay_item.frontier_residual_exchange.final_closure
          )
          == moc_reflected_domain_global_physical_closure_fingerprint(
            result_item.frontier_residual_exchange.final_closure
          )
        )
      )
      for replay_item, result_item in zip(
        replay.iterations,
        result.iterations,
        strict=True,
      )
    )
  )
  convergence_flags = bool(
    replay.status is result.status
    and replay.feedback_completed == result.feedback_completed
    and replay.frontier_chain_verified == result.frontier_chain_verified
    and replay.joint_solve_chain_verified == result.joint_solve_chain_verified
    and replay.frontier_residual_exchange_chain_verified
    == result.frontier_residual_exchange_chain_verified
    and replay.fixed_point_verified == result.fixed_point_verified
    and replay.residual_descent_verified == result.residual_descent_verified
    and replay.independent_audit_verified == result.independent_audit_verified
  )
  independent = bool(
    request_replayed
    and count_replayed
    and closure_lineage
    and frontier_chain
    and joint_chain
    and residual_exchange_chain
    and convergence_flags
    and replay.independent_audit_verified
    and replay.chain_promotion_blocked
    and not replay.production_claim_allowed
  )
  return MocReflectedDomainGlobalMixedRegimeJointStateFrontierFeedbackAudit(
    status=(
      audit_status.VERIFIED_RESEARCH_JOINT_STATE_FRONTIER_FEEDBACK
      if independent
      else audit_status.LINEAGE_FAILURE
    ),
    candidate=result,
    request_replayed=request_replayed,
    iteration_count_replayed=count_replayed,
    closure_lineage_replayed=closure_lineage,
    frontier_chain_replayed=frontier_chain,
    joint_chain_replayed=joint_chain,
    residual_exchange_chain_replayed=residual_exchange_chain,
    convergence_flags_replayed=convergence_flags,
    independent_joint_feedback_verified=independent,
    global_coupling_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    message=(
      'independent replay reproduced the bounded joint state/frontier feedback chain'
      if independent
      else 'independent replay did not reproduce the bounded joint state/frontier chain'
    ),
  )
