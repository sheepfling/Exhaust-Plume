"""Equation-level dimensioned correction for the global boundary-state lane.

The joint consumer proves that a solver-owned shock geometry response can be
replayed on a fresh global physical field.  This module takes the next
physical step: it sends that fresh field through a terminal downstream ->
global -> downstream recheck, then runs the complete signed conservative
mass/normal-momentum/energy solver on the resulting closure.

The operator is deliberately fail-closed.  A terminal downstream response or
locally converged conservative replay is not enough; the new response must
retain exact lineage and strictly improve both the dimensioned channels and
the aggregate residual relative to the preceding joint result.  The result
is research evidence only and cannot authorize canonical closure or product
promotion.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import Enum
from math import isfinite, sqrt
from typing import Any

from exhaust_plume.models.moc.euler_two_sided_moving_interface import (
  MocEulerTwoSidedInterfaceResponse,
)
from exhaust_plume.models.moc.global_physical_closure import (
  MocReflectedDomainGlobalPhysicalClosureResult,
  moc_reflected_domain_global_physical_closure_fingerprint,
)
from exhaust_plume.models.moc.global_two_sided_moving_interface import (
  MocReflectedDomainGlobalTwoSidedMovingInterfaceRequest,
  MocReflectedDomainGlobalTwoSidedMovingInterfaceResult,
  solve_reflected_domain_global_two_sided_moving_interface,
)
from exhaust_plume.validation.moc_euler_two_sided_conservative_residual import (
  MocEulerTwoSidedConservativeResidualAudit,
)
from exhaust_plume.validation.moc_global_boundary_state_joint_solve import (
  MocReflectedDomainGlobalBoundaryStateJointSolveResult,
)
from exhaust_plume.validation.moc_global_coupled_boundary_condition_feedback import (
  MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRun,
  run_reflected_domain_global_coupled_boundary_condition_feedback,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_BOUNDARY_STATE_DIMENSIONED_CORRECTOR_OPERATOR_ID',
  'MocReflectedDomainGlobalBoundaryStateDimensionedCorrectorStatus',
  'MocReflectedDomainGlobalBoundaryStateDimensionedCorrectorResult',
  'run_reflected_domain_global_boundary_state_dimensioned_corrector',
)


MOC_REFLECTED_DOMAIN_GLOBAL_BOUNDARY_STATE_DIMENSIONED_CORRECTOR_OPERATOR_ID = (
  'op.moc.reflected-domain.global-boundary-state-dimensioned-corrector-v1'
)


class MocReflectedDomainGlobalBoundaryStateDimensionedCorrectorStatus(
  str, Enum
):
  """Typed outcomes of the equation-level research corrector."""

  CONVERGED_RESEARCH_DIMENSIONED_CORRECTOR = (
    'converged-research-global-boundary-state-dimensioned-corrector'
  )
  INVALID_INPUT = 'invalid_input'
  JOINT_RESULT_FAILURE = (
    'global-boundary-state-dimensioned-corrector-joint-result-failure'
  )
  TERMINAL_BOUNDARY_FAILURE = (
    'global-boundary-state-dimensioned-corrector-terminal-boundary-failure'
  )
  STATE_FAILURE = (
    'global-boundary-state-dimensioned-corrector-state-failure'
  )
  LINEAGE_FAILURE = (
    'global-boundary-state-dimensioned-corrector-lineage-failure'
  )
  CHANNEL_FAILURE = (
    'global-boundary-state-dimensioned-corrector-channel-failure'
  )
  RESIDUAL_DESCENT_FAILURE = (
    'global-boundary-state-dimensioned-corrector-residual-descent-failure'
  )


def _fingerprint(closure: MocReflectedDomainGlobalPhysicalClosureResult) -> str:
  return moc_reflected_domain_global_physical_closure_fingerprint(closure)


def _response(
  result: MocReflectedDomainGlobalTwoSidedMovingInterfaceResult | None,
) -> MocEulerTwoSidedInterfaceResponse | None:
  if result is None or result.conservative_residual_result is None:
    return None
  return result.conservative_residual_result.final_response


def _normalized_channel_maxima(
  response: MocEulerTwoSidedInterfaceResponse | None,
  request: MocReflectedDomainGlobalTwoSidedMovingInterfaceRequest | None,
) -> tuple[float, float, float] | None:
  """Return finite mass/momentum/energy maxima in declared units."""

  if response is None or request is None or not response.signed_residuals_available:
    return None
  channels = (
    response.signed_mass_flux_residuals_kg_m2_s,
    response.signed_normal_momentum_residuals_Pa,
    response.signed_energy_flux_residuals_W_m2,
  )
  tolerances = (
    request.mass_flux_tolerance_kg_m2_s,
    request.normal_momentum_tolerance_Pa,
    request.energy_flux_tolerance_W_m2,
  )
  if any(channel is None for channel in channels):
    return None
  assert all(channel is not None for channel in channels)
  if not (len(channels[0]) == len(channels[1]) == len(channels[2])):
    return None
  if any(not isfinite(float(value)) or value <= 0.0 for value in tolerances):
    return None
  maxima = tuple(
    max(
      (abs(float(value)) / tolerance for value in channel),
      default=float('inf'),
    )
    for channel, tolerance in zip(channels, tolerances, strict=True)
  )
  if any(not isfinite(value) for value in maxima):
    return None
  return maxima


def _dimensioned_descent(
  before: tuple[float, float, float] | None,
  after: tuple[float, float, float] | None,
) -> bool:
  """Require active-channel descent while retaining closed channels.

  A channel already inside its declared tolerance may move within that strict
  accepted band while an open equation is corrected.  Open channels may not
  worsen and at least one open channel must strictly decrease.  No tolerance
  is widened by this active-set rule.
  """

  if before is None or after is None:
    return False
  numerical_tolerance = 1.0e-12
  closed_limit = 1.0 + numerical_tolerance
  nonincreasing = all(
    (
      next_value
      <= current_value + numerical_tolerance * max(1.0, abs(current_value))
      if current_value > 1.0
      else next_value <= closed_limit
    )
    for current_value, next_value in zip(before, after, strict=True)
  )
  strict = any(
    current_value > 1.0
    and next_value
    < current_value - numerical_tolerance * max(1.0, abs(current_value))
    for current_value, next_value in zip(before, after, strict=True)
  )
  return bool(nonincreasing and (strict or all(value <= closed_limit for value in after)))


def _strict_descent(before: float | None, after: float | None, fraction: float) -> bool:
  if before is None or after is None:
    return False
  if not isfinite(before) or not isfinite(after):
    return False
  if not isfinite(fraction) or fraction < 0.0:
    return False
  if before <= 0.0:
    return after < before
  return after < before * (1.0 - fraction)


def _normalized_residual_norm(
  response: MocEulerTwoSidedInterfaceResponse | None,
  request: MocReflectedDomainGlobalTwoSidedMovingInterfaceRequest | None,
) -> float | None:
  """Return the RMS norm in the same strict units as the channel maxima."""

  if response is None or request is None or not response.signed_residuals_available:
    return None
  channels = (
    response.signed_mass_flux_residuals_kg_m2_s,
    response.signed_normal_momentum_residuals_Pa,
    response.signed_energy_flux_residuals_W_m2,
  )
  tolerances = (
    request.mass_flux_tolerance_kg_m2_s,
    request.normal_momentum_tolerance_Pa,
    request.energy_flux_tolerance_W_m2,
  )
  if any(channel is None for channel in channels):
    return None
  assert all(channel is not None for channel in channels)
  terms = tuple(
    abs(float(value)) / tolerance
    for channel, tolerance in zip(channels, tolerances, strict=True)
    for value in channel
  )
  if not terms or any(not isfinite(value) for value in terms):
    return None
  result = sqrt(sum(value * value for value in terms) / len(terms))
  return result if isfinite(result) else None


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalBoundaryStateDimensionedCorrectorResult:
  """Evidence from one terminal equation-level correction attempt."""

  status: MocReflectedDomainGlobalBoundaryStateDimensionedCorrectorStatus
  joint_result: MocReflectedDomainGlobalBoundaryStateJointSolveResult | None
  source_closure: MocReflectedDomainGlobalPhysicalClosureResult | None = None
  terminal_feedback_run: (
    MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRun | None
  ) = None
  state_request: MocReflectedDomainGlobalTwoSidedMovingInterfaceRequest | None = None
  state_result: MocReflectedDomainGlobalTwoSidedMovingInterfaceResult | None = None
  conservative_residual_audit: MocEulerTwoSidedConservativeResidualAudit | None = None
  baseline_residual_norm: float | None = None
  refreshed_residual_norm: float | None = None
  baseline_dimensioned_channel_maxima: tuple[float, ...] = ()
  refreshed_dimensioned_channel_maxima: tuple[float, ...] = ()
  joint_consumption_verified: bool = False
  terminal_boundary_equations_verified: bool = False
  terminal_global_recheck_verified: bool = False
  state_solver_invoked: bool = False
  complete_conservative_response_verified: bool = False
  state_lineage_verified: bool = False
  independent_residual_audit_verified: bool = False
  dimensioned_channel_descent_verified: bool = False
  residual_descent_verified: bool = False
  corrector_update_verified: bool = False
  global_coupling_verified: bool = False
  downstream_boundary_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''
  operator_id: str = (
    MOC_REFLECTED_DOMAIN_GLOBAL_BOUNDARY_STATE_DIMENSIONED_CORRECTOR_OPERATOR_ID
  )

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalBoundaryStateDimensionedCorrectorStatus,
    ):
      raise TypeError('status must be a typed dimensioned-corrector status')
    if self.joint_result is not None and not isinstance(
      self.joint_result,
      MocReflectedDomainGlobalBoundaryStateJointSolveResult,
    ):
      raise TypeError('joint_result must be typed or None')
    for name, expected_type in (
      ('source_closure', MocReflectedDomainGlobalPhysicalClosureResult),
      (
        'terminal_feedback_run',
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
    for name in (
      'baseline_dimensioned_channel_maxima',
      'refreshed_dimensioned_channel_maxima',
    ):
      values = tuple(float(value) for value in getattr(self, name))
      if values and (
        len(values) != 3
        or any(not isfinite(value) or value < 0.0 for value in values)
      ):
        raise ValueError(f'{name} must contain three finite nonnegative values')
      object.__setattr__(self, name, values)
    for name in (
      'joint_consumption_verified',
      'terminal_boundary_equations_verified',
      'terminal_global_recheck_verified',
      'state_solver_invoked',
      'complete_conservative_response_verified',
      'state_lineage_verified',
      'independent_residual_audit_verified',
      'dimensioned_channel_descent_verified',
      'residual_descent_verified',
      'corrector_update_verified',
      'global_coupling_verified',
      'downstream_boundary_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    if self.global_coupling_verified or self.downstream_boundary_closure_verified:
      raise ValueError('dimensioned corrector cannot claim canonical closure')
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError('dimensioned corrector must remain promotion-blocked')
    for name in ('baseline_residual_norm', 'refreshed_residual_norm'):
      value = getattr(self, name)
      if value is not None:
        numeric = float(value)
        if not isfinite(numeric) or numeric < 0.0:
          raise ValueError(f'{name} must be finite and nonnegative when supplied')
        object.__setattr__(self, name, numeric)
    if self.status is (
      MocReflectedDomainGlobalBoundaryStateDimensionedCorrectorStatus
      .CONVERGED_RESEARCH_DIMENSIONED_CORRECTOR
    ) and not (self.corrector_update_verified and self.residual_descent_verified):
      raise ValueError('converged dimensioned correction must pass update gates')
    object.__setattr__(self, 'message', str(self.message))

  @property
  def converged_research_dimensioned_corrector(self) -> bool:
    return bool(
      self.status is (
        MocReflectedDomainGlobalBoundaryStateDimensionedCorrectorStatus
        .CONVERGED_RESEARCH_DIMENSIONED_CORRECTOR
      )
      and self.corrector_update_verified
      and self.residual_descent_verified
    )

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': self.operator_id,
      'status': self.status.value,
      'converged_research_dimensioned_corrector': (
        self.converged_research_dimensioned_corrector
      ),
      'source_closure_fingerprint': (
        None if self.source_closure is None else _fingerprint(self.source_closure)
      ),
      'baseline_residual_norm': self.baseline_residual_norm,
      'refreshed_residual_norm': self.refreshed_residual_norm,
      'baseline_dimensioned_channel_maxima': (
        self.baseline_dimensioned_channel_maxima
      ),
      'refreshed_dimensioned_channel_maxima': (
        self.refreshed_dimensioned_channel_maxima
      ),
      'joint_consumption_verified': self.joint_consumption_verified,
      'terminal_boundary_equations_verified': (
        self.terminal_boundary_equations_verified
      ),
      'terminal_global_recheck_verified': self.terminal_global_recheck_verified,
      'state_solver_invoked': self.state_solver_invoked,
      'complete_conservative_response_verified': (
        self.complete_conservative_response_verified
      ),
      'state_lineage_verified': self.state_lineage_verified,
      'independent_residual_audit_verified': (
        self.independent_residual_audit_verified
      ),
      'dimensioned_channel_descent_verified': (
        self.dimensioned_channel_descent_verified
      ),
      'residual_descent_verified': self.residual_descent_verified,
      'corrector_update_verified': self.corrector_update_verified,
      'global_coupling_verified': False,
      'downstream_boundary_closure_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'terminal_feedback_run': (
        None
        if self.terminal_feedback_run is None
        else self.terminal_feedback_run.as_report()
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
      'joint_result': (
        None if self.joint_result is None else self.joint_result.as_report()
      ),
      'message': self.message,
    }


def _result(
  status: MocReflectedDomainGlobalBoundaryStateDimensionedCorrectorStatus,
  joint_result: MocReflectedDomainGlobalBoundaryStateJointSolveResult | None,
  message: str,
  **kwargs: Any,
) -> MocReflectedDomainGlobalBoundaryStateDimensionedCorrectorResult:
  return MocReflectedDomainGlobalBoundaryStateDimensionedCorrectorResult(
    status=status,
    joint_result=joint_result,
    message=message,
    **kwargs,
  )


def run_reflected_domain_global_boundary_state_dimensioned_corrector(
  joint_result: MocReflectedDomainGlobalBoundaryStateJointSolveResult | None,
  *,
  accepted_mass_flux_tolerance_kg_m2_s: float = 1.0e-3,
  accepted_normal_momentum_tolerance_Pa: float = 1.0e-2,
  accepted_energy_flux_tolerance_W_m2: float = 1.0e-1,
) -> MocReflectedDomainGlobalBoundaryStateDimensionedCorrectorResult:
  """Exercise the terminal equation-level global/downstream corrector."""

  if not isinstance(
    joint_result,
    MocReflectedDomainGlobalBoundaryStateJointSolveResult,
  ):
    return _result(
      MocReflectedDomainGlobalBoundaryStateDimensionedCorrectorStatus.INVALID_INPUT,
      None,
      'joint_result must be a typed global boundary-state joint result',
    )
  try:
    accepted_tolerances = tuple(
      float(value)
      for value in (
        accepted_mass_flux_tolerance_kg_m2_s,
        accepted_normal_momentum_tolerance_Pa,
        accepted_energy_flux_tolerance_W_m2,
      )
    )
  except (TypeError, ValueError):
    return _result(
      MocReflectedDomainGlobalBoundaryStateDimensionedCorrectorStatus.INVALID_INPUT,
      joint_result,
      'accepted conservative tolerances must be numeric',
    )
  if any(not isfinite(value) or value <= 0.0 for value in accepted_tolerances):
    return _result(
      MocReflectedDomainGlobalBoundaryStateDimensionedCorrectorStatus.INVALID_INPUT,
      joint_result,
      'accepted conservative tolerances must be finite and positive',
    )
  accepted_mass_tolerance, accepted_momentum_tolerance, accepted_energy_tolerance = (
    accepted_tolerances
  )
  joint_consumption_verified = bool(
    joint_result.converged_research_joint_update
    and joint_result.handoff_consumed
    and joint_result.joint_state_update_verified
    and joint_result.shock_geometry_response_consumed
    and joint_result.shock_geometry_response_lineage_verified
    and joint_result.dimensioned_channels_verified
    and joint_result.dimensioned_channel_descent_verified
  )
  source = joint_result.geometry_response_closure
  handoff = joint_result.handoff
  reported_baseline = joint_result.refreshed_residual_norm
  reported_baseline_channels = tuple(
    joint_result.refreshed_dimensioned_channel_maxima
  )
  if not joint_consumption_verified or source is None or handoff is None:
    return _result(
      MocReflectedDomainGlobalBoundaryStateDimensionedCorrectorStatus
      .JOINT_RESULT_FAILURE,
      joint_result,
      'joint result did not retain a converged, dimensioned, lineage-verified '
      'source for the equation-level corrector',
      source_closure=source,
      baseline_residual_norm=reported_baseline,
      baseline_dimensioned_channel_maxima=reported_baseline_channels,
      joint_consumption_verified=joint_consumption_verified,
    )
  ####
  try:
    configuration = handoff.boundary_feedback_run.configuration
    downstream_options = configuration.get('downstream_options')
    boundary_options = configuration.get('boundary_condition_options', {})
    reference_temperature = float(
      configuration['reference_total_temperature_K']
    )
    downstream_iterations = int(
      configuration['downstream_feedback_iterations']
    )
    maximum_frame_extension = float(
      configuration['maximum_frame_extension_m']
    )
    if not isinstance(downstream_options, Mapping):
      raise ValueError('handoff did not retain mapping-valued downstream options')
    if not isinstance(boundary_options, Mapping):
      raise ValueError('handoff did not retain mapping-valued boundary options')
    if downstream_iterations < 2:
      raise ValueError('handoff retained too few downstream feedback iterations')
    if not isfinite(reference_temperature) or reference_temperature <= 0.0:
      raise ValueError('handoff retained an invalid reference temperature')
    if not isfinite(maximum_frame_extension) or maximum_frame_extension < 0.0:
      raise ValueError('handoff retained an invalid frame-extension budget')
    downstream_options = dict(downstream_options)
    boundary_options = dict(boundary_options)
    boundary_options['consume_target_geometry'] = True
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _result(
      MocReflectedDomainGlobalBoundaryStateDimensionedCorrectorStatus.INVALID_INPUT,
      joint_result,
      f'equation-level corrector setup failed: {error}',
      source_closure=source,
      baseline_residual_norm=reported_baseline,
      baseline_dimensioned_channel_maxima=reported_baseline_channels,
      joint_consumption_verified=True,
    )
  ####
  try:
    terminal_feedback = (
      run_reflected_domain_global_coupled_boundary_condition_feedback(
        source,
        reference_total_temperature_K=reference_temperature,
        maximum_iterations=1,
        downstream_feedback_iterations=downstream_iterations,
        downstream_options=downstream_options,
        boundary_condition_options=boundary_options,
        maximum_frame_extension_m=maximum_frame_extension,
        require_terminal_fixed_point=True,
        require_terminal_global_fixed_point=True,
        require_terminal_global_downstream_recheck=True,
      )
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _result(
      MocReflectedDomainGlobalBoundaryStateDimensionedCorrectorStatus
      .TERMINAL_BOUNDARY_FAILURE,
      joint_result,
      f'terminal equation-level downstream/global recheck raised: {error}',
      source_closure=source,
      baseline_residual_norm=reported_baseline,
      baseline_dimensioned_channel_maxima=reported_baseline_channels,
      joint_consumption_verified=True,
    )
  terminal_global_recheck_verified = bool(
    terminal_feedback.terminal_global_downstream_recheck_verified
    and terminal_feedback.terminal_global_fixed_point_verified
    and terminal_feedback.terminal_fixed_point_verified
  )
  terminal_boundary_verified = bool(
    terminal_feedback.research_feedback_completed
    and terminal_feedback.outer_feedback_completed
    and terminal_feedback.source_closure is source
    and terminal_feedback.final_closure is not source
    and terminal_feedback.final_closure.converged
    and terminal_feedback.final_closure.physical_closure_verified
    and terminal_feedback.fidelity_isolation_verified
    and not terminal_feedback.global_coupling_verified
    and not terminal_feedback.downstream_boundary_closure_verified
  )
  if not terminal_boundary_verified:
    return _result(
      MocReflectedDomainGlobalBoundaryStateDimensionedCorrectorStatus
      .TERMINAL_BOUNDARY_FAILURE,
      joint_result,
      'terminal downstream/global equations did not pass their complete '
      'research-only boundary, frame, coverage, and downstream-recheck gates',
      source_closure=source,
      terminal_feedback_run=terminal_feedback,
      baseline_residual_norm=reported_baseline,
      baseline_dimensioned_channel_maxima=reported_baseline_channels,
      joint_consumption_verified=True,
      terminal_boundary_equations_verified=False,
      terminal_global_recheck_verified=terminal_global_recheck_verified,
    )
  ####
  if joint_result.state_request is None:
    return _result(
      MocReflectedDomainGlobalBoundaryStateDimensionedCorrectorStatus.STATE_FAILURE,
      joint_result,
      'joint result retained no conservative state request for the terminal '
      'equation-level correction',
      source_closure=source,
      terminal_feedback_run=terminal_feedback,
      baseline_residual_norm=reported_baseline,
      baseline_dimensioned_channel_maxima=reported_baseline_channels,
      joint_consumption_verified=True,
      terminal_boundary_equations_verified=True,
      terminal_global_recheck_verified=terminal_global_recheck_verified,
    )
  state_request = replace(
    joint_result.state_request,
    closure=terminal_feedback.final_closure,
    mass_flux_tolerance_kg_m2_s=min(
      joint_result.state_request.mass_flux_tolerance_kg_m2_s,
      accepted_mass_tolerance,
    ),
    normal_momentum_tolerance_Pa=min(
      joint_result.state_request.normal_momentum_tolerance_Pa,
      accepted_momentum_tolerance,
    ),
    energy_flux_tolerance_W_m2=min(
      joint_result.state_request.energy_flux_tolerance_W_m2,
      accepted_energy_tolerance,
    ),
    require_dimensioned_conservative_channel_descent=True,
    use_conservative_residual_shape_jacobian_correction=True,
    source='solver-owned-global-boundary-state-dimensioned-corrector-v1',
  )
  baseline_response = _response(joint_result.state_result)
  baseline_channels = _normalized_channel_maxima(
    baseline_response,
    state_request,
  )
  baseline = _normalized_residual_norm(baseline_response, state_request)
  if baseline is None or baseline_channels is None:
    return _result(
      MocReflectedDomainGlobalBoundaryStateDimensionedCorrectorStatus
      .LINEAGE_FAILURE,
      joint_result,
      'joint result did not retain a complete signed response for the strict '
      'accepted conservative tolerance space',
      source_closure=source,
      terminal_feedback_run=terminal_feedback,
      state_request=state_request,
      baseline_residual_norm=baseline,
      baseline_dimensioned_channel_maxima=baseline_channels or (),
      joint_consumption_verified=True,
      terminal_boundary_equations_verified=True,
      terminal_global_recheck_verified=terminal_global_recheck_verified,
    )
  try:
    state_result = solve_reflected_domain_global_two_sided_moving_interface(
      state_request
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _result(
      MocReflectedDomainGlobalBoundaryStateDimensionedCorrectorStatus.STATE_FAILURE,
      joint_result,
      f'terminal dimensioned conservative state solve raised: {error}',
      source_closure=source,
      terminal_feedback_run=terminal_feedback,
      state_request=state_request,
      baseline_residual_norm=baseline,
      baseline_dimensioned_channel_maxima=baseline_channels,
      joint_consumption_verified=True,
      terminal_boundary_equations_verified=True,
      terminal_global_recheck_verified=terminal_global_recheck_verified,
      state_solver_invoked=True,
    )
  residual_result = state_result.conservative_residual_result
  audit = state_result.conservative_residual_audit
  response = _response(state_result)
  refreshed = None if residual_result is None else residual_result.final_residual_norm
  after_channels = _normalized_channel_maxima(response, state_request)
  state_lineage = bool(
    state_result.request is state_request
    and state_result.source_closure_fingerprint
    == _fingerprint(terminal_feedback.final_closure)
  )
  signed = bool(response is not None and response.signed_residuals_available)
  complete_response = bool(
    residual_result is not None
    and residual_result.final_response is response
    and residual_result.residual_vector_verified
    and residual_result.field_re_solve_verified
    and state_request.use_conservative_residual_line_search
    and state_request.require_conservative_flux_closure
    and state_request.require_dimensioned_conservative_channel_descent
    and signed
  )
  independent = bool(
    isinstance(audit, MocEulerTwoSidedConservativeResidualAudit)
    and audit.local_consistency_verified
  )
  channel_descent = _dimensioned_descent(baseline_channels, after_channels)
  residual_descent = _strict_descent(
    baseline,
    refreshed,
    state_request.minimum_residual_descent_fraction,
  )
  corrector_update = bool(
    terminal_boundary_verified
    and terminal_global_recheck_verified
    and state_lineage
    and complete_response
    and independent
    and channel_descent
    and residual_descent
  )
  common = dict(
    source_closure=source,
    terminal_feedback_run=terminal_feedback,
    state_request=state_request,
    state_result=state_result,
    conservative_residual_audit=audit,
    baseline_residual_norm=baseline,
    refreshed_residual_norm=refreshed,
    baseline_dimensioned_channel_maxima=baseline_channels,
    refreshed_dimensioned_channel_maxima=after_channels or (),
    joint_consumption_verified=True,
    terminal_boundary_equations_verified=terminal_boundary_verified,
    terminal_global_recheck_verified=terminal_global_recheck_verified,
    state_solver_invoked=True,
    complete_conservative_response_verified=complete_response,
    state_lineage_verified=state_lineage,
    independent_residual_audit_verified=independent,
    dimensioned_channel_descent_verified=channel_descent,
    residual_descent_verified=residual_descent,
    corrector_update_verified=corrector_update,
  )
  if residual_result is None or not residual_result.converged:
    return _result(
      MocReflectedDomainGlobalBoundaryStateDimensionedCorrectorStatus.STATE_FAILURE,
      joint_result,
      'strict accepted conservative tolerances retained a typed non-converged '
      'state solve after exact field re-solves; canonical closure was not claimed',
      **common,
    )
  if not state_lineage or not complete_response or not independent:
    return _result(
      MocReflectedDomainGlobalBoundaryStateDimensionedCorrectorStatus.LINEAGE_FAILURE,
      joint_result,
      'terminal equations ran, but the complete conservative response did not '
      'retain the exact state, field re-solve, or independent-audit lineage',
      **common,
    )
  if not channel_descent:
    return _result(
      MocReflectedDomainGlobalBoundaryStateDimensionedCorrectorStatus.CHANNEL_FAILURE,
      joint_result,
      'terminal equations and complete conservative response ran, but the '
      'dimensioned mass/normal-momentum/energy channels did not strictly descend',
      **common,
    )
  if not residual_descent:
    return _result(
      MocReflectedDomainGlobalBoundaryStateDimensionedCorrectorStatus
      .RESIDUAL_DESCENT_FAILURE,
      joint_result,
      'terminal equations and complete conservative response ran, but the '
      'aggregate residual did not strictly descend from the joint result',
      **common,
    )
  return _result(
    MocReflectedDomainGlobalBoundaryStateDimensionedCorrectorStatus
    .CONVERGED_RESEARCH_DIMENSIONED_CORRECTOR,
    joint_result,
    'terminal downstream/global equations and complete dimensioned conservative '
    'state correction achieved strict channel and residual descent; canonical '
    'coupling and production gates remain closed',
    **common,
  )
