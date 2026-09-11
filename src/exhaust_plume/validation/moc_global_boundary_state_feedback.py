"""Fail-closed global boundary-state feedback handoff evidence.

The bounded boundary-condition feedback runner already consumes a downstream
pressure/geometry proposal in a fresh global solve.  The moving-interface
solver measures a separate signed mass, normal-momentum, and energy response.
This module binds those exact artifacts into one lineage-checked handoff
packet without pretending that a pressure overlay is a conservative
free-boundary solve.

The handoff is ready only when the fresh global solve and the independently
audited, genuinely moving conservative response both pass.  The current
mixed-regime research case is expected to stop at the residual audit; that
stop is intentional and remains below canonical closure and production.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Any

from exhaust_plume.models.moc.coupled_euler_free_boundary import (
  MocReflectedDomainCoupledEulerInletBoundaryMode,
)
from exhaust_plume.models.moc.global_coupled_downstream import (
  MocReflectedDomainGlobalCoupledDownstreamUpstreamFeedbackProposal,
  build_reflected_domain_global_solver_owned_physical_field_handoff,
)
from exhaust_plume.models.moc.global_physical_closure import (
  MocReflectedDomainGlobalPhysicalClosureResult,
  moc_reflected_domain_global_physical_closure_fingerprint,
)
from exhaust_plume.models.moc.global_two_sided_moving_interface import (
  MocReflectedDomainGlobalTwoSidedMovingInterfaceRequest,
  MocReflectedDomainGlobalTwoSidedMovingInterfaceResult,
  MocReflectedDomainGlobalTwoSidedMovingInterfaceStatus,
  solve_reflected_domain_global_two_sided_moving_interface,
)
from exhaust_plume.models.moc.euler_two_sided_conservative_residual_solve import (
  MocEulerTwoSidedConservativeResidualSolveResult,
)
from exhaust_plume.models.moc.euler_two_sided_moving_interface import (
  MocEulerTwoSidedInterfaceResponse,
)
from exhaust_plume.validation.moc_euler_two_sided_conservative_residual import (
  MocEulerTwoSidedConservativeResidualAudit,
)
from exhaust_plume.validation.moc_global_coupled_boundary_condition_feedback import (
  MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRun,
  run_reflected_domain_global_coupled_boundary_condition_feedback,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_BOUNDARY_STATE_FEEDBACK_OPERATOR_ID',
  'MocReflectedDomainGlobalBoundaryStateFeedbackStatus',
  'MocReflectedDomainGlobalBoundaryStateFeedbackHandoff',
  'MocReflectedDomainGlobalBoundaryStateFeedbackResult',
  'build_reflected_domain_global_boundary_state_feedback_handoff',
  'run_reflected_domain_global_boundary_state_feedback',
)


MOC_REFLECTED_DOMAIN_GLOBAL_BOUNDARY_STATE_FEEDBACK_OPERATOR_ID = (
  'op.moc.reflected-domain.global-boundary-state-feedback-v1'
)


class MocReflectedDomainGlobalBoundaryStateFeedbackStatus(str, Enum):
  """Typed outcomes of the conservative state handoff packet."""

  READY_RESEARCH_STATE_HANDOFF = (
    'ready-research-global-boundary-state-feedback-handoff'
  )
  INVALID_INPUT = 'invalid_input'
  BOUNDARY_FEEDBACK_FAILURE = (
    'global-boundary-state-feedback-boundary-solve-failure'
  )
  PROPOSAL_LINEAGE_FAILURE = (
    'global-boundary-state-feedback-proposal-lineage-failure'
  )
  STATE_SOLVER_FAILURE = 'global-boundary-state-feedback-state-solver-failure'
  RESIDUAL_AUDIT_FAILURE = (
    'global-boundary-state-feedback-conservative-residual-audit-failure'
  )
  STATIONARY_STATE_FAILURE = (
    'global-boundary-state-feedback-stationary-state-rejected'
  )


def _options(
  value: Mapping[str, Any] | None,
  name: str,
  *,
  reserved: tuple[str, ...],
) -> dict[str, Any]:
  if value is None:
    return {}
  if not isinstance(value, Mapping):
    raise TypeError(f'{name} must be a mapping when supplied')
  resolved = dict(value)
  collisions = tuple(key for key in reserved if key in resolved)
  if collisions:
    raise ValueError(
      f'{name} cannot override positional controls: {", ".join(collisions)}'
    )
  return resolved


def _fingerprint(
  closure: MocReflectedDomainGlobalPhysicalClosureResult,
) -> str:
  return moc_reflected_domain_global_physical_closure_fingerprint(closure)


def _response(
  result: MocReflectedDomainGlobalTwoSidedMovingInterfaceResult | None,
) -> MocEulerTwoSidedInterfaceResponse | None:
  if result is None or result.conservative_residual_result is None:
    return None
  return result.conservative_residual_result.final_response


def _residual_result(
  result: MocReflectedDomainGlobalTwoSidedMovingInterfaceResult | None,
) -> MocEulerTwoSidedConservativeResidualSolveResult | None:
  return None if result is None else result.conservative_residual_result


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


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalBoundaryStateFeedbackHandoff:
  """Exact downstream-target plus moving-state packet awaiting a joint solver."""

  boundary_feedback_run: MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRun
  proposal: MocReflectedDomainGlobalCoupledDownstreamUpstreamFeedbackProposal
  two_sided_result: MocReflectedDomainGlobalTwoSidedMovingInterfaceResult
  conservative_residual_audit: MocEulerTwoSidedConservativeResidualAudit
  proposal_source_closure_fingerprint: str
  state_source_closure_fingerprint: str
  signed_mass_flux_residuals_kg_m2_s: tuple[float, ...]
  signed_normal_momentum_residuals_Pa: tuple[float, ...]
  signed_energy_flux_residuals_W_m2: tuple[float, ...]
  final_residual_norm: float
  consumed_by_global_solver: bool = False
  global_coupling_verified: bool = False
  downstream_boundary_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False

  def __post_init__(self) -> None:
    if not isinstance(
      self.boundary_feedback_run,
      MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRun,
    ):
      raise TypeError('boundary_feedback_run must be a typed boundary feedback run')
    if not isinstance(
      self.proposal,
      MocReflectedDomainGlobalCoupledDownstreamUpstreamFeedbackProposal,
    ):
      raise TypeError('proposal must be a typed downstream feedback proposal')
    if not isinstance(
      self.two_sided_result,
      MocReflectedDomainGlobalTwoSidedMovingInterfaceResult,
    ):
      raise TypeError('two_sided_result must be a typed two-sided result')
    if not isinstance(
      self.conservative_residual_audit,
      MocEulerTwoSidedConservativeResidualAudit,
    ):
      raise TypeError('conservative_residual_audit must be a typed audit')
    if not self.boundary_feedback_run.research_feedback_completed:
      raise ValueError('handoff requires a completed boundary feedback run')
    if not self.boundary_feedback_run.iterations:
      raise ValueError('handoff requires a retained boundary feedback iteration')
    if self.boundary_feedback_run.iterations[-1].proposal is not self.proposal:
      raise ValueError('handoff proposal must be the final retained proposal')
    if not self.proposal.ready_for_global_resolve:
      raise ValueError('handoff proposal must be ready for a global resolve')
    residual = self.two_sided_result.conservative_residual_result
    if residual is None or not residual.converged:
      raise ValueError('handoff requires a converged conservative residual result')
    response = residual.final_response
    if not _signed_channels_finite(response):
      raise ValueError('handoff requires finite signed residual channels')
    if not self.conservative_residual_audit.local_consistency_verified:
      raise ValueError('handoff requires an independently consistent residual audit')
    if self.two_sided_result.request is None:
      raise ValueError('handoff requires the retained two-sided request')
    state_fingerprint = _fingerprint(self.two_sided_result.request.closure)
    if state_fingerprint != self.state_source_closure_fingerprint:
      raise ValueError('state_source_closure_fingerprint does not match the request')
    if self.state_source_closure_fingerprint != _fingerprint(
      self.boundary_feedback_run.final_closure
    ):
      raise ValueError('state handoff must consume the final fresh global closure')
    if self.proposal_source_closure_fingerprint != self.proposal.source_closure_fingerprint:
      raise ValueError('proposal_source_closure_fingerprint does not match proposal')
    if self.proposal.global_coupling_verified or self.proposal.consumed_by_global_solver:
      raise ValueError('handoff proposal cannot claim global-solver consumption')
    if (
      self.consumed_by_global_solver
      or self.global_coupling_verified
      or self.downstream_boundary_closure_verified
      or not self.chain_promotion_blocked
      or self.production_claim_allowed
    ):
      raise ValueError('boundary state handoffs must remain promotion-blocked')
    channels = (
      tuple(float(value) for value in self.signed_mass_flux_residuals_kg_m2_s),
      tuple(float(value) for value in self.signed_normal_momentum_residuals_Pa),
      tuple(float(value) for value in self.signed_energy_flux_residuals_W_m2),
    )
    if not len(channels[0]) == len(channels[1]) == len(channels[2]):
      raise ValueError('signed residual channels must have equal lengths')
    if any(not isfinite(value) for channel in channels for value in channel):
      raise ValueError('signed residual channels must be finite')
    final_norm = float(self.final_residual_norm)
    if not isfinite(final_norm) or final_norm < 0.0:
      raise ValueError('final_residual_norm must be finite and nonnegative')
    object.__setattr__(self, 'signed_mass_flux_residuals_kg_m2_s', channels[0])
    object.__setattr__(self, 'signed_normal_momentum_residuals_Pa', channels[1])
    object.__setattr__(self, 'signed_energy_flux_residuals_W_m2', channels[2])
    object.__setattr__(self, 'final_residual_norm', final_norm)

  @property
  def ready_for_joint_global_resolve(self) -> bool:
    """Whether the packet is ready for a future joint upstream solver."""

    return bool(
      self.conservative_residual_audit.local_consistency_verified
      and self.two_sided_result.converged
      and not self.consumed_by_global_solver
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
    )

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': MOC_REFLECTED_DOMAIN_GLOBAL_BOUNDARY_STATE_FEEDBACK_OPERATOR_ID,
      'ready_for_joint_global_resolve': self.ready_for_joint_global_resolve,
      'proposal_source_closure_fingerprint': self.proposal_source_closure_fingerprint,
      'state_source_closure_fingerprint': self.state_source_closure_fingerprint,
      'signed_mass_flux_residuals_kg_m2_s': self.signed_mass_flux_residuals_kg_m2_s,
      'signed_normal_momentum_residuals_Pa': self.signed_normal_momentum_residuals_Pa,
      'signed_energy_flux_residuals_W_m2': self.signed_energy_flux_residuals_W_m2,
      'final_residual_norm': self.final_residual_norm,
      'consumed_by_global_solver': False,
      'global_coupling_verified': False,
      'downstream_boundary_closure_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'proposal': self.proposal.as_report(),
      'two_sided_result': self.two_sided_result.as_report(),
      'conservative_residual_audit': self.conservative_residual_audit.as_report(),
      'boundary_feedback_run': self.boundary_feedback_run.as_report(),
      'claim_status': (
        'research-only conservative boundary-state handoff; a future joint '
        'upstream/free-boundary solver must consume this packet before any '
        'canonical, shock-cell, Signature, FPA, or production claim'
      ),
    }


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalBoundaryStateFeedbackResult:
  """End-to-end boundary feedback plus conservative-state admission result."""

  status: MocReflectedDomainGlobalBoundaryStateFeedbackStatus
  source_closure: MocReflectedDomainGlobalPhysicalClosureResult | None
  boundary_feedback_run: MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRun | None = None
  proposal: MocReflectedDomainGlobalCoupledDownstreamUpstreamFeedbackProposal | None = None
  two_sided_request: MocReflectedDomainGlobalTwoSidedMovingInterfaceRequest | None = None
  two_sided_result: MocReflectedDomainGlobalTwoSidedMovingInterfaceResult | None = None
  conservative_residual_audit: MocEulerTwoSidedConservativeResidualAudit | None = None
  handoff: MocReflectedDomainGlobalBoundaryStateFeedbackHandoff | None = None
  boundary_feedback_verified: bool = False
  proposal_lineage_verified: bool = False
  state_solver_invoked: bool = False
  state_lineage_verified: bool = False
  signed_residuals_verified: bool = False
  moving_state_verified: bool = False
  independent_residual_audit_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocReflectedDomainGlobalBoundaryStateFeedbackStatus):
      raise TypeError('status must be a typed boundary-state feedback status')
    if self.source_closure is not None and not isinstance(
      self.source_closure,
      MocReflectedDomainGlobalPhysicalClosureResult,
    ):
      raise TypeError('source_closure must be a typed global closure or None')
    if self.boundary_feedback_run is not None and not isinstance(
      self.boundary_feedback_run,
      MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRun,
    ):
      raise TypeError('boundary_feedback_run must be typed or None')
    if self.proposal is not None and not isinstance(
      self.proposal,
      MocReflectedDomainGlobalCoupledDownstreamUpstreamFeedbackProposal,
    ):
      raise TypeError('proposal must be typed or None')
    if self.two_sided_request is not None and not isinstance(
      self.two_sided_request,
      MocReflectedDomainGlobalTwoSidedMovingInterfaceRequest,
    ):
      raise TypeError('two_sided_request must be typed or None')
    if self.two_sided_result is not None and not isinstance(
      self.two_sided_result,
      MocReflectedDomainGlobalTwoSidedMovingInterfaceResult,
    ):
      raise TypeError('two_sided_result must be typed or None')
    if self.conservative_residual_audit is not None and not isinstance(
      self.conservative_residual_audit,
      MocEulerTwoSidedConservativeResidualAudit,
    ):
      raise TypeError('conservative_residual_audit must be typed or None')
    if self.handoff is not None and not isinstance(
      self.handoff,
      MocReflectedDomainGlobalBoundaryStateFeedbackHandoff,
    ):
      raise TypeError('handoff must be typed or None')
    for name in (
      'boundary_feedback_verified',
      'proposal_lineage_verified',
      'state_solver_invoked',
      'state_lineage_verified',
      'signed_residuals_verified',
      'moving_state_verified',
      'independent_residual_audit_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError('boundary-state feedback must remain promotion-blocked')
    if self.status is (
      MocReflectedDomainGlobalBoundaryStateFeedbackStatus.READY_RESEARCH_STATE_HANDOFF
    ) and not (
      self.handoff is not None
      and self.boundary_feedback_verified
      and self.proposal_lineage_verified
      and self.state_lineage_verified
      and self.signed_residuals_verified
      and self.moving_state_verified
      and self.independent_residual_audit_verified
    ):
      raise ValueError('ready state handoff must pass every retained evidence gate')
    object.__setattr__(self, 'message', str(self.message))

  @property
  def handoff_ready(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalBoundaryStateFeedbackStatus.READY_RESEARCH_STATE_HANDOFF
      and self.handoff is not None
      and self.handoff.ready_for_joint_global_resolve
    )

  def as_report(self) -> dict[str, Any]:
    response = _response(self.two_sided_result)
    return {
      'operator_id': MOC_REFLECTED_DOMAIN_GLOBAL_BOUNDARY_STATE_FEEDBACK_OPERATOR_ID,
      'status': self.status.value,
      'handoff_ready': self.handoff_ready,
      'boundary_feedback_verified': self.boundary_feedback_verified,
      'proposal_lineage_verified': self.proposal_lineage_verified,
      'state_solver_invoked': self.state_solver_invoked,
      'state_lineage_verified': self.state_lineage_verified,
      'signed_residuals_verified': self.signed_residuals_verified,
      'moving_state_verified': self.moving_state_verified,
      'independent_residual_audit_verified': self.independent_residual_audit_verified,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'source_closure_fingerprint': (
        None if self.source_closure is None else _fingerprint(self.source_closure)
      ),
      'boundary_feedback_run': (
        None
        if self.boundary_feedback_run is None
        else self.boundary_feedback_run.as_report()
      ),
      'proposal': None if self.proposal is None else self.proposal.as_report(),
      'two_sided_request': (
        None
        if self.two_sided_request is None
        else self.two_sided_request.as_report()
      ),
      'two_sided_result': (
        None
        if self.two_sided_result is None
        else self.two_sided_result.as_report()
      ),
      'conservative_residual_audit': (
        None
        if self.conservative_residual_audit is None
        else self.conservative_residual_audit.as_report()
      ),
      'signed_residual_response': (
        None if response is None else response.as_report()
      ),
      'handoff': None if self.handoff is None else self.handoff.as_report(),
      'message': self.message,
    }


def _result(
  status: MocReflectedDomainGlobalBoundaryStateFeedbackStatus,
  source_closure: MocReflectedDomainGlobalPhysicalClosureResult | None,
  message: str,
  **kwargs: Any,
) -> MocReflectedDomainGlobalBoundaryStateFeedbackResult:
  return MocReflectedDomainGlobalBoundaryStateFeedbackResult(
    status=status,
    source_closure=source_closure,
    message=message,
    **kwargs,
  )


def build_reflected_domain_global_boundary_state_feedback_handoff(
  boundary_feedback_run: MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRun,
  proposal: MocReflectedDomainGlobalCoupledDownstreamUpstreamFeedbackProposal,
  two_sided_result: MocReflectedDomainGlobalTwoSidedMovingInterfaceResult,
  conservative_residual_audit: MocEulerTwoSidedConservativeResidualAudit,
) -> MocReflectedDomainGlobalBoundaryStateFeedbackHandoff:
  """Bind exact global-target and conservative-state artifacts for a future solver."""

  if not isinstance(
    boundary_feedback_run,
    MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRun,
  ):
    raise TypeError('boundary_feedback_run must be a typed boundary feedback run')
  if not isinstance(
    proposal,
    MocReflectedDomainGlobalCoupledDownstreamUpstreamFeedbackProposal,
  ):
    raise TypeError('proposal must be a typed downstream feedback proposal')
  if not isinstance(
    two_sided_result,
    MocReflectedDomainGlobalTwoSidedMovingInterfaceResult,
  ):
    raise TypeError('two_sided_result must be a typed two-sided result')
  if not isinstance(
    conservative_residual_audit,
    MocEulerTwoSidedConservativeResidualAudit,
  ):
    raise TypeError('conservative_residual_audit must be a typed residual audit')
  if two_sided_result.request is None:
    raise ValueError('two-sided result did not retain its request')
  residual = two_sided_result.conservative_residual_result
  if residual is None or residual.final_response is None:
    raise ValueError('two-sided result did not retain a final residual response')
  response = residual.final_response
  if not _signed_channels_finite(response):
    raise ValueError('two-sided result did not retain finite signed residual channels')
  if not two_sided_result.converged or not conservative_residual_audit.local_consistency_verified:
    raise ValueError('conservative state evidence is not independently ready')
  if (
    not two_sided_result.request.require_interface_motion
    or two_sided_result.request.allow_stationary_equilibrium
    or response.stationary_equilibrium_candidate
    or response.maximum_normal_displacement_m
    <= two_sided_result.request.position_tolerance_m
  ):
    raise ValueError('state handoff requires a genuinely moving interface response')
  assert response.signed_mass_flux_residuals_kg_m2_s is not None
  assert response.signed_normal_momentum_residuals_Pa is not None
  assert response.signed_energy_flux_residuals_W_m2 is not None
  residual_norm = residual.final_residual_norm
  if residual_norm is None:
    raise ValueError('two-sided result did not retain a final residual norm')
  state_fingerprint = _fingerprint(two_sided_result.request.closure)
  return MocReflectedDomainGlobalBoundaryStateFeedbackHandoff(
    boundary_feedback_run=boundary_feedback_run,
    proposal=proposal,
    two_sided_result=two_sided_result,
    conservative_residual_audit=conservative_residual_audit,
    proposal_source_closure_fingerprint=proposal.source_closure_fingerprint,
    state_source_closure_fingerprint=state_fingerprint,
    signed_mass_flux_residuals_kg_m2_s=response.signed_mass_flux_residuals_kg_m2_s,
    signed_normal_momentum_residuals_Pa=response.signed_normal_momentum_residuals_Pa,
    signed_energy_flux_residuals_W_m2=response.signed_energy_flux_residuals_W_m2,
    final_residual_norm=residual_norm,
  )


def run_reflected_domain_global_boundary_state_feedback(
  closure: MocReflectedDomainGlobalPhysicalClosureResult,
  *,
  reference_total_temperature_K: float,
  downstream_feedback_iterations: int = 2,
  maximum_frame_extension_m: float = 0.5,
  consumer_id: str = 'moc-global-boundary-state-feedback-v1',
  downstream_options: Mapping[str, Any] | None = None,
  boundary_condition_options: Mapping[str, Any] | None = None,
  two_sided_request_options: Mapping[str, Any] | None = None,
) -> MocReflectedDomainGlobalBoundaryStateFeedbackResult:
  """Fresh-solve downstream target state, then attempt conservative admission."""

  if not isinstance(closure, MocReflectedDomainGlobalPhysicalClosureResult):
    return _result(
      MocReflectedDomainGlobalBoundaryStateFeedbackStatus.INVALID_INPUT,
      None,
      'closure must be a MocReflectedDomainGlobalPhysicalClosureResult',
    )
  try:
    resolved_downstream = _options(
      downstream_options,
      'downstream_options',
      reserved=('closure', 'reference_total_temperature_K'),
    )
    resolved_boundary = _options(
      boundary_condition_options,
      'boundary_condition_options',
      reserved=('request', 'source_closure', 'base_target'),
    )
    resolved_two_sided = _options(
      two_sided_request_options,
      'two_sided_request_options',
      reserved=(
        'closure',
        'reference_total_temperature_K',
        'require_interface_motion',
        'allow_stationary_equilibrium',
        'require_conservative_flux_closure',
        'use_conservative_residual_line_search',
        'require_strict_residual_descent',
        'source',
      ),
    )
    reference_temperature = float(reference_total_temperature_K)
    if not isfinite(reference_temperature) or reference_temperature <= 0.0:
      raise ValueError('reference_total_temperature_K must be finite and positive')
    if resolved_boundary.get('consume_target_geometry', True) is not True:
      raise ValueError(
        'boundary-state feedback requires consume_target_geometry=True'
      )
    resolved_boundary['consume_target_geometry'] = True
    # Keep the state handoff on the strict residual-admission lane by default.
    # The global moving-interface adapter's broader 100 Pa default is useful for
    # exploratory response studies, but it must not silently turn the known
    # interior-probe mismatch into a ready state packet.
    resolved_two_sided.setdefault('normal_momentum_tolerance_Pa', 1.0e-2)
    resolved_two_sided.setdefault(
      'consume_global_physical_field_for_downstream_probes',
      True,
    )
    handoff = build_reflected_domain_global_solver_owned_physical_field_handoff(
      closure
    )
    resolved_downstream.setdefault(
      'inlet_boundary_mode',
      MocReflectedDomainCoupledEulerInletBoundaryMode
      .SOLVER_OWNED_PHYSICAL_FIELD_CONTINUATION_PROFILE,
    )
    resolved_downstream.setdefault(
      'physical_field_continuation_profile',
      handoff.continuation_profile,
    )
    resolved_downstream.setdefault(
      'physical_field_shock_front_condition',
      handoff.shock_front_condition,
    )
    feedback = run_reflected_domain_global_coupled_boundary_condition_feedback(
      closure,
      reference_total_temperature_K=reference_temperature,
      maximum_iterations=1,
      downstream_feedback_iterations=downstream_feedback_iterations,
      consumer_id=consumer_id,
      downstream_options=resolved_downstream,
      boundary_condition_options=resolved_boundary,
      maximum_frame_extension_m=maximum_frame_extension_m,
      require_terminal_fixed_point=True,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _result(
      MocReflectedDomainGlobalBoundaryStateFeedbackStatus.INVALID_INPUT,
      closure,
      f'boundary-state feedback setup failed: {error}',
    )
  ####
  if not feedback.research_feedback_completed or not feedback.iterations:
    return _result(
      MocReflectedDomainGlobalBoundaryStateFeedbackStatus.BOUNDARY_FEEDBACK_FAILURE,
      closure,
      f'fresh global boundary feedback did not complete: {feedback.message}',
      boundary_feedback_run=feedback,
      boundary_feedback_verified=False,
    )
  iteration = feedback.iterations[-1]
  proposal = iteration.proposal
  proposal_lineage = bool(
    proposal is not None
    and proposal.ready_for_global_resolve
    and iteration.proposal is proposal
    and proposal.source_closure_fingerprint
    == _fingerprint(iteration.source_closure)
    and iteration.next_closure is feedback.final_closure
  )
  if proposal is None or not proposal_lineage:
    return _result(
      MocReflectedDomainGlobalBoundaryStateFeedbackStatus.PROPOSAL_LINEAGE_FAILURE,
      closure,
      'fresh boundary feedback did not retain an exact final proposal/closure chain',
      boundary_feedback_run=feedback,
      proposal=proposal,
      boundary_feedback_verified=True,
      proposal_lineage_verified=False,
    )
  ####
  try:
    state_request = MocReflectedDomainGlobalTwoSidedMovingInterfaceRequest(
      closure=feedback.final_closure,
      reference_total_temperature_K=reference_temperature,
      require_interface_motion=True,
      allow_stationary_equilibrium=False,
      require_conservative_flux_closure=True,
      use_conservative_residual_line_search=True,
      require_strict_residual_descent=True,
      source='solver-owned-global-boundary-state-feedback-request-v1',
      **resolved_two_sided,
    )
    state_result = solve_reflected_domain_global_two_sided_moving_interface(
      state_request
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _result(
      MocReflectedDomainGlobalBoundaryStateFeedbackStatus.STATE_SOLVER_FAILURE,
      closure,
      f'conservative state solve raised: {error}',
      boundary_feedback_run=feedback,
      proposal=proposal,
      state_solver_invoked=True,
      boundary_feedback_verified=True,
      proposal_lineage_verified=True,
    )
  ####
  residual_result = _residual_result(state_result)
  audit = state_result.conservative_residual_audit
  response = _response(state_result)
  state_lineage = bool(
    state_result.request is state_request
    and state_result.source_closure_fingerprint == _fingerprint(feedback.final_closure)
  )
  signed = _signed_channels_finite(response)
  independent_audit = bool(
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
  if not signed or not independent_audit:
    status = (
      MocReflectedDomainGlobalBoundaryStateFeedbackStatus.RESIDUAL_AUDIT_FAILURE
    )
    message = (
      'fresh global boundary target was consumed, but the independent signed '
      'mass/normal-momentum/energy audit did not pass'
    )
  elif not moving:
    status = MocReflectedDomainGlobalBoundaryStateFeedbackStatus.STATIONARY_STATE_FAILURE
    message = 'conservative state evidence did not demonstrate a moving interface'
  else:
    try:
      assert audit is not None
      handoff_result = build_reflected_domain_global_boundary_state_feedback_handoff(
        feedback,
        proposal,
        state_result,
        audit,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      return _result(
        MocReflectedDomainGlobalBoundaryStateFeedbackStatus.RESIDUAL_AUDIT_FAILURE,
        closure,
        f'conservative state handoff failed closed: {error}',
        boundary_feedback_run=feedback,
        proposal=proposal,
        two_sided_request=state_request,
        two_sided_result=state_result,
        conservative_residual_audit=audit,
        boundary_feedback_verified=True,
        proposal_lineage_verified=True,
        state_solver_invoked=True,
        state_lineage_verified=state_lineage,
        signed_residuals_verified=signed,
        moving_state_verified=moving,
        independent_residual_audit_verified=independent_audit,
      )
    return _result(
      MocReflectedDomainGlobalBoundaryStateFeedbackStatus.READY_RESEARCH_STATE_HANDOFF,
      closure,
      'fresh global target geometry/pressure and independently audited moving '
      'conservative state are bound into an unconsumed research handoff',
      boundary_feedback_run=feedback,
      proposal=proposal,
      two_sided_request=state_request,
      two_sided_result=state_result,
      conservative_residual_audit=audit,
      handoff=handoff_result,
      boundary_feedback_verified=True,
      proposal_lineage_verified=True,
      state_solver_invoked=True,
      state_lineage_verified=state_lineage,
      signed_residuals_verified=signed,
      moving_state_verified=moving,
      independent_residual_audit_verified=independent_audit,
    )
  return _result(
    status,
    closure,
    message,
    boundary_feedback_run=feedback,
    proposal=proposal,
    two_sided_request=state_request,
    two_sided_result=state_result,
    conservative_residual_audit=audit,
    boundary_feedback_verified=True,
    proposal_lineage_verified=True,
    state_solver_invoked=True,
    state_lineage_verified=state_lineage,
    signed_residuals_verified=signed,
    moving_state_verified=moving,
    independent_residual_audit_verified=independent_audit,
  )
