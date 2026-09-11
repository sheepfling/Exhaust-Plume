"""Bounded outer state update after global boundary-state consumption.

The joint consumer can prove that one exact target frame was consumed, but a
replay of that same frame is not an update direction.  This module starts
from the consumed global closure, runs one fresh downstream-response/global
feedback step, and then remeasures the conservative moving-state response on
the new closure.  It accepts no direct shock-frame-to-downstream interpolation.

The operator remains research-only.  A changed closure is not enough: the
updated conservative residual must be independently audited and strictly
lower than the retained handoff baseline before the operator reports a
converged research update.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import Enum
from math import isfinite
from typing import Any

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
from exhaust_plume.models.moc.euler_two_sided_moving_interface import (
  MocEulerTwoSidedInterfaceResponse,
)
from exhaust_plume.validation.moc_euler_two_sided_conservative_residual import (
  MocEulerTwoSidedConservativeResidualAudit,
)
from exhaust_plume.validation.moc_global_boundary_state_feedback import (
  MocReflectedDomainGlobalBoundaryStateFeedbackHandoff,
)
from exhaust_plume.validation.moc_global_coupled_boundary_condition_feedback import (
  MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRun,
  run_reflected_domain_global_coupled_boundary_condition_feedback,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_BOUNDARY_STATE_OUTER_UPDATE_OPERATOR_ID',
  'MocReflectedDomainGlobalBoundaryStateOuterUpdateStatus',
  'MocReflectedDomainGlobalBoundaryStateOuterUpdateResult',
  'run_reflected_domain_global_boundary_state_outer_update',
)


MOC_REFLECTED_DOMAIN_GLOBAL_BOUNDARY_STATE_OUTER_UPDATE_OPERATOR_ID = (
  'op.moc.reflected-domain.global-boundary-state-outer-update-v1'
)


class MocReflectedDomainGlobalBoundaryStateOuterUpdateStatus(str, Enum):
  """Typed outcomes of one bounded outer update attempt."""

  CONVERGED_RESEARCH_OUTER_UPDATE = (
    'converged-research-global-boundary-state-outer-update'
  )
  INVALID_INPUT = 'invalid_input'
  HANDOFF_LINEAGE_FAILURE = (
    'global-boundary-state-outer-update-handoff-lineage-failure'
  )
  OUTER_FEEDBACK_FAILURE = (
    'global-boundary-state-outer-update-feedback-failure'
  )
  STATE_UPDATE_FAILURE = 'global-boundary-state-outer-update-state-failure'
  RESIDUAL_AUDIT_FAILURE = (
    'global-boundary-state-outer-update-residual-audit-failure'
  )
  RESIDUAL_DESCENT_FAILURE = (
    'global-boundary-state-outer-update-residual-descent-failure'
  )
####


def _fingerprint(closure: MocReflectedDomainGlobalPhysicalClosureResult) -> str:
  return moc_reflected_domain_global_physical_closure_fingerprint(closure)
####


def _response(
  result: MocReflectedDomainGlobalTwoSidedMovingInterfaceResult | None,
) -> MocEulerTwoSidedInterfaceResponse | None:
  if result is None or result.conservative_residual_result is None:
    return None
  ####
  return result.conservative_residual_result.final_response
####


def _signed_channels_finite(response: MocEulerTwoSidedInterfaceResponse | None) -> bool:
  if response is None or not response.signed_residuals_available:
    return False
  ####
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
####


def _strict_descent(before: float, after: float, minimum_fraction: float) -> bool:
  if not isfinite(before) or not isfinite(after):
    return False
  ####
  if not isfinite(minimum_fraction) or minimum_fraction < 0.0:
    return False
  ####
  if before <= 0.0:
    return after < before
  ####
  return after < before * (1.0 - minimum_fraction)
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalBoundaryStateOuterUpdateResult:
  """Research evidence from one new outer global/state update."""

  status: MocReflectedDomainGlobalBoundaryStateOuterUpdateStatus
  handoff: MocReflectedDomainGlobalBoundaryStateFeedbackHandoff | None
  source_closure: MocReflectedDomainGlobalPhysicalClosureResult | None = None
  updated_closure: MocReflectedDomainGlobalPhysicalClosureResult | None = None
  outer_feedback_run: MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRun | None = None
  state_request: MocReflectedDomainGlobalTwoSidedMovingInterfaceRequest | None = None
  state_result: MocReflectedDomainGlobalTwoSidedMovingInterfaceResult | None = None
  conservative_residual_audit: MocEulerTwoSidedConservativeResidualAudit | None = None
  baseline_residual_norm: float | None = None
  refreshed_residual_norm: float | None = None
  handoff_lineage_verified: bool = False
  outer_feedback_invoked: bool = False
  outer_feedback_verified: bool = False
  updated_closure_lineage_verified: bool = False
  state_solver_invoked: bool = False
  state_lineage_verified: bool = False
  signed_residuals_verified: bool = False
  moving_state_verified: bool = False
  independent_residual_audit_verified: bool = False
  residual_descent_verified: bool = False
  outer_state_update_verified: bool = False
  global_coupling_verified: bool = False
  downstream_boundary_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalBoundaryStateOuterUpdateStatus,
    ):
      raise TypeError('status must be a typed outer-update status')
    ####
    for name, expected_type in (
      (
        'handoff',
        MocReflectedDomainGlobalBoundaryStateFeedbackHandoff,
      ),
      (
        'source_closure',
        MocReflectedDomainGlobalPhysicalClosureResult,
      ),
      (
        'updated_closure',
        MocReflectedDomainGlobalPhysicalClosureResult,
      ),
      (
        'outer_feedback_run',
        MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRun,
      ),
      (
        'state_request',
        MocReflectedDomainGlobalTwoSidedMovingInterfaceRequest,
      ),
      (
        'state_result',
        MocReflectedDomainGlobalTwoSidedMovingInterfaceResult,
      ),
      (
        'conservative_residual_audit',
        MocEulerTwoSidedConservativeResidualAudit,
      ),
    ):
      value = getattr(self, name)
      if value is not None and not isinstance(value, expected_type):
        raise TypeError(f'{name} must be typed or None')
      ####
    ####
    for name in (
      'handoff_lineage_verified',
      'outer_feedback_invoked',
      'outer_feedback_verified',
      'updated_closure_lineage_verified',
      'state_solver_invoked',
      'state_lineage_verified',
      'signed_residuals_verified',
      'moving_state_verified',
      'independent_residual_audit_verified',
      'residual_descent_verified',
      'outer_state_update_verified',
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
      raise ValueError('outer research updates cannot claim canonical coupling')
    ####
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError('outer research updates must remain promotion-blocked')
    ####
    for name in ('baseline_residual_norm', 'refreshed_residual_norm'):
      value = getattr(self, name)
      if value is not None:
        numeric = float(value)
        if not isfinite(numeric) or numeric < 0.0:
          raise ValueError(f'{name} must be finite and nonnegative when supplied')
        ####
        object.__setattr__(self, name, numeric)
      ####
    ####
    if self.status is (
      MocReflectedDomainGlobalBoundaryStateOuterUpdateStatus
      .CONVERGED_RESEARCH_OUTER_UPDATE
    ) and not (
      self.outer_state_update_verified
      and self.residual_descent_verified
    ):
      raise ValueError('converged outer update must pass state and descent gates')
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged_research_outer_update(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalBoundaryStateOuterUpdateStatus
      .CONVERGED_RESEARCH_OUTER_UPDATE
      and self.outer_state_update_verified
      and self.residual_descent_verified
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': MOC_REFLECTED_DOMAIN_GLOBAL_BOUNDARY_STATE_OUTER_UPDATE_OPERATOR_ID,
      'status': self.status.value,
      'converged_research_outer_update': self.converged_research_outer_update,
      'handoff_lineage_verified': self.handoff_lineage_verified,
      'outer_feedback_invoked': self.outer_feedback_invoked,
      'outer_feedback_verified': self.outer_feedback_verified,
      'updated_closure_lineage_verified': self.updated_closure_lineage_verified,
      'state_solver_invoked': self.state_solver_invoked,
      'state_lineage_verified': self.state_lineage_verified,
      'signed_residuals_verified': self.signed_residuals_verified,
      'moving_state_verified': self.moving_state_verified,
      'independent_residual_audit_verified': self.independent_residual_audit_verified,
      'residual_descent_verified': self.residual_descent_verified,
      'outer_state_update_verified': self.outer_state_update_verified,
      'global_coupling_verified': False,
      'downstream_boundary_closure_verified': False,
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
      'outer_feedback_run': (
        None
        if self.outer_feedback_run is None
        else self.outer_feedback_run.as_report()
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
      'handoff': None if self.handoff is None else self.handoff.as_report(),
      'claim_status': (
        'research-only outer global/state update; strict residual descent, '
        'canonical coupling, physical shock-cell acceptance, Signature/FPA '
        'production, external validation, and release remain open'
      ),
      'message': self.message,
    }
  ####
####


def _result(
  status: MocReflectedDomainGlobalBoundaryStateOuterUpdateStatus,
  handoff: MocReflectedDomainGlobalBoundaryStateFeedbackHandoff | None,
  message: str,
  **kwargs: Any,
) -> MocReflectedDomainGlobalBoundaryStateOuterUpdateResult:
  return MocReflectedDomainGlobalBoundaryStateOuterUpdateResult(
    status=status,
    handoff=handoff,
    message=message,
    **kwargs,
  )
####


def run_reflected_domain_global_boundary_state_outer_update(
  handoff: MocReflectedDomainGlobalBoundaryStateFeedbackHandoff | None,
) -> MocReflectedDomainGlobalBoundaryStateOuterUpdateResult:
  """Run one new downstream/global/state update from a ready handoff."""

  if not isinstance(
    handoff,
    MocReflectedDomainGlobalBoundaryStateFeedbackHandoff,
  ):
    return _result(
      MocReflectedDomainGlobalBoundaryStateOuterUpdateStatus.INVALID_INPUT,
      None,
      'handoff must be a typed global boundary-state feedback handoff',
    )
  ####
  try:
    if not handoff.ready_for_joint_global_resolve:
      raise ValueError('handoff is not ready for joint global consumption')
    ####
    source = handoff.boundary_feedback_run.final_closure
    if _fingerprint(source) != handoff.state_source_closure_fingerprint:
      raise ValueError('handoff state fingerprint does not match its final closure')
    ####
    configuration = handoff.boundary_feedback_run.configuration
    downstream_options = configuration.get('downstream_options')
    if not isinstance(downstream_options, Mapping):
      raise ValueError('handoff did not retain downstream solver options')
    ####
    reference_temperature = float(
      configuration['reference_total_temperature_K']
    )
    downstream_iterations = int(
      configuration['downstream_feedback_iterations']
    )
    maximum_frame_extension = float(
      configuration['maximum_frame_extension_m']
    )
    if not isfinite(reference_temperature) or reference_temperature <= 0.0:
      raise ValueError('handoff retained an invalid reference temperature')
    ####
    if downstream_iterations < 2:
      raise ValueError('handoff retained too few downstream feedback iterations')
    ####
    if not isfinite(maximum_frame_extension) or maximum_frame_extension < 0.0:
      raise ValueError('handoff retained an invalid frame-extension budget')
    ####
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _result(
      MocReflectedDomainGlobalBoundaryStateOuterUpdateStatus.HANDOFF_LINEAGE_FAILURE,
      handoff,
      f'outer-update handoff setup failed closed: {error}',
    )
  ####

  try:
    outer_feedback = run_reflected_domain_global_coupled_boundary_condition_feedback(
      source,
      reference_total_temperature_K=reference_temperature,
      maximum_iterations=1,
      downstream_feedback_iterations=downstream_iterations,
      downstream_options=downstream_options,
      boundary_condition_options={'consume_target_geometry': True},
      maximum_frame_extension_m=maximum_frame_extension,
      require_terminal_fixed_point=True,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _result(
      MocReflectedDomainGlobalBoundaryStateOuterUpdateStatus.OUTER_FEEDBACK_FAILURE,
      handoff,
      f'outer downstream/global feedback raised: {error}',
      source_closure=source,
      handoff_lineage_verified=True,
      outer_feedback_invoked=True,
    )
  ####
  outer_verified = bool(
    outer_feedback.outer_feedback_completed
    and outer_feedback.source_closure is source
    and outer_feedback.final_closure is not source
    and outer_feedback.final_closure.converged
    and outer_feedback.final_closure.physical_closure_verified
    and not outer_feedback.global_coupling_verified
    and not outer_feedback.downstream_boundary_closure_verified
    and outer_feedback.chain_promotion_blocked
    and not outer_feedback.production_claim_allowed
  )
  updated = outer_feedback.final_closure
  updated_lineage = bool(
    updated is not None
    and outer_feedback.iterations
    and outer_feedback.iterations[-1].source_closure is source
    and outer_feedback.iterations[-1].next_closure is updated
    and _fingerprint(updated) != _fingerprint(source)
  )
  if not outer_verified or not updated_lineage:
    return _result(
      MocReflectedDomainGlobalBoundaryStateOuterUpdateStatus.OUTER_FEEDBACK_FAILURE,
      handoff,
      'outer feedback did not retain a fresh, locally verified, promotion-blocked '
      'closure with exact source lineage',
      source_closure=source,
      updated_closure=updated,
      outer_feedback_run=outer_feedback,
      handoff_lineage_verified=True,
      outer_feedback_invoked=True,
      outer_feedback_verified=outer_verified,
      updated_closure_lineage_verified=updated_lineage,
    )
  ####
  state_request = replace(
    handoff.two_sided_result.request,
    closure=updated,
    source='moc-global-boundary-state-outer-update-state-v1',
  )
  try:
    state_result = solve_reflected_domain_global_two_sided_moving_interface(
      state_request
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _result(
      MocReflectedDomainGlobalBoundaryStateOuterUpdateStatus.STATE_UPDATE_FAILURE,
      handoff,
      f'outer-update conservative state solve raised: {error}',
      source_closure=source,
      updated_closure=updated,
      outer_feedback_run=outer_feedback,
      state_request=state_request,
      handoff_lineage_verified=True,
      outer_feedback_invoked=True,
      outer_feedback_verified=True,
      updated_closure_lineage_verified=True,
      state_solver_invoked=True,
      baseline_residual_norm=handoff.final_residual_norm,
    )
  ####
  residual = state_result.conservative_residual_result
  audit = state_result.conservative_residual_audit
  response = _response(state_result)
  state_lineage = bool(
    state_result.request is state_request
    and state_result.source_closure_fingerprint == _fingerprint(updated)
  )
  signed = _signed_channels_finite(response)
  independent_audit = bool(
    isinstance(audit, MocEulerTwoSidedConservativeResidualAudit)
    and audit.local_consistency_verified
  )
  moving = bool(
    residual is not None
    and residual.converged
    and state_result.status
    is MocReflectedDomainGlobalTwoSidedMovingInterfaceStatus
    .CONVERGED_RESEARCH_INTERFACE
    and response is not None
    and state_request.require_interface_motion
    and not state_request.allow_stationary_equilibrium
    and not response.stationary_equilibrium_candidate
    and response.maximum_normal_displacement_m > state_request.position_tolerance_m
  )
  refreshed_norm = None if residual is None else residual.final_residual_norm
  if refreshed_norm is None:
    return _result(
      MocReflectedDomainGlobalBoundaryStateOuterUpdateStatus.RESIDUAL_AUDIT_FAILURE,
      handoff,
      'outer-update state solve retained no final residual norm',
      source_closure=source,
      updated_closure=updated,
      outer_feedback_run=outer_feedback,
      state_request=state_request,
      state_result=state_result,
      conservative_residual_audit=audit,
      handoff_lineage_verified=True,
      outer_feedback_invoked=True,
      outer_feedback_verified=True,
      updated_closure_lineage_verified=True,
      state_solver_invoked=True,
      state_lineage_verified=state_lineage,
      signed_residuals_verified=signed,
      moving_state_verified=moving,
      independent_residual_audit_verified=independent_audit,
      baseline_residual_norm=handoff.final_residual_norm,
    )
  ####
  baseline_norm = float(handoff.final_residual_norm)
  refreshed_value = float(refreshed_norm)
  descent = _strict_descent(
    baseline_norm,
    refreshed_value,
    state_request.minimum_residual_descent_fraction,
  )
  common = dict(
    source_closure=source,
    updated_closure=updated,
    outer_feedback_run=outer_feedback,
    state_request=state_request,
    state_result=state_result,
    conservative_residual_audit=audit,
    baseline_residual_norm=baseline_norm,
    refreshed_residual_norm=refreshed_value,
    handoff_lineage_verified=True,
    outer_feedback_invoked=True,
    outer_feedback_verified=True,
    updated_closure_lineage_verified=True,
    state_solver_invoked=True,
    state_lineage_verified=state_lineage,
    signed_residuals_verified=signed,
    moving_state_verified=moving,
    independent_residual_audit_verified=independent_audit,
    residual_descent_verified=descent,
    outer_state_update_verified=bool(
      state_lineage and signed and moving and independent_audit
    ),
  )
  if not state_lineage or not signed or not moving or not independent_audit:
    return _result(
      MocReflectedDomainGlobalBoundaryStateOuterUpdateStatus.RESIDUAL_AUDIT_FAILURE,
      handoff,
      'outer global update produced a state, but its independent conservative '
      'audit did not pass every retained gate',
      **common,
    )
  ####
  if not descent:
    return _result(
      MocReflectedDomainGlobalBoundaryStateOuterUpdateStatus.RESIDUAL_DESCENT_FAILURE,
      handoff,
      'outer global/state update changed the fresh closure but did not strictly '
      f'descend the conservative residual ({baseline_norm:.12g} -> {refreshed_value:.12g})',
      **common,
    )
  ####
  return _result(
    MocReflectedDomainGlobalBoundaryStateOuterUpdateStatus
    .CONVERGED_RESEARCH_OUTER_UPDATE,
    handoff,
    'outer global/state update changed the fresh closure and achieved strict '
    'independently audited conservative residual descent; production remains closed',
    **common,
  )
####
