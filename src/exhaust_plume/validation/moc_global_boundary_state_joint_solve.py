"""Fail-closed joint consumption of a global boundary-state handoff.

The boundary-state handoff contains two different solver frames: a downstream
pressure/geometry proposal and a conservative residual response on the moving
shock.  This module deliberately does not interpolate one frame onto the
other.  It consumes the exact extended target frame in a fresh global solve,
then replays the conservative state solver on that fresh closure and compares
the independently audited residual vector with the retained baseline.

The result is research evidence only.  A fresh state update that does not
strictly reduce the retained conservative residual is a typed failure, even
when the global solve and state replay both converge locally.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import Enum
from math import isfinite
from typing import Any

from exhaust_plume.models.moc.global_frontier_reconciliation import (
  MocReflectedDomainGlobalFrontierReconciliationRequest,
  moc_reflected_domain_global_frontier_proposal_fingerprint,
)
from exhaust_plume.models.moc.global_physical_closure import (
  MocReflectedDomainGlobalPhysicalClosureResult,
  consume_reflected_domain_global_shock_geometry_response,
  moc_reflected_domain_global_physical_closure_fingerprint,
)
from exhaust_plume.models.moc.global_two_sided_moving_interface import (
  MocReflectedDomainGlobalTwoSidedMovingInterfaceRequest,
  MocReflectedDomainGlobalTwoSidedMovingInterfaceResult,
  MocReflectedDomainGlobalTwoSidedMovingInterfaceStatus,
  solve_reflected_domain_global_two_sided_moving_interface,
)
from exhaust_plume.models.moc.physical_field_euler_reconciliation import (
  MocPhysicalFieldEulerBoundaryPressureTarget,
)
from exhaust_plume.validation.moc_euler_two_sided_conservative_residual import (
  MocEulerTwoSidedConservativeResidualAudit,
)
from exhaust_plume.validation.moc_global_boundary_state_feedback import (
  MocReflectedDomainGlobalBoundaryStateFeedbackHandoff,
)
from exhaust_plume.validation.moc_global_frontier_boundary_condition import (
  MocReflectedDomainGlobalFrontierBoundaryConditionResult,
  MocReflectedDomainGlobalFrontierBoundaryConditionStatus,
  run_reflected_domain_global_frontier_boundary_conditioned_resolve,
)
from exhaust_plume.models.moc.euler_two_sided_moving_interface import (
  MocEulerTwoSidedInterfaceResponse,
)
from exhaust_plume.models.moc.euler_shock_boundary import (
  MocEulerShockBoundaryCurveResult,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_BOUNDARY_STATE_JOINT_SOLVE_OPERATOR_ID',
  'MocReflectedDomainGlobalBoundaryStateJointSolveStatus',
  'MocReflectedDomainGlobalBoundaryStateJointSolveResult',
  'run_reflected_domain_global_boundary_state_joint_solve',
)


MOC_REFLECTED_DOMAIN_GLOBAL_BOUNDARY_STATE_JOINT_SOLVE_OPERATOR_ID = (
  'op.moc.reflected-domain.global-boundary-state-joint-solve-v1'
)


class MocReflectedDomainGlobalBoundaryStateJointSolveStatus(str, Enum):
  """Typed outcomes of one exact handoff-consuming joint attempt."""

  CONVERGED_RESEARCH_JOINT_STATE_UPDATE = (
    'converged-research-global-boundary-state-joint-update'
  )
  INVALID_INPUT = 'invalid_input'
  HANDOFF_LINEAGE_FAILURE = (
    'global-boundary-state-joint-handoff-lineage-failure'
  )
  GLOBAL_CONSUMER_FAILURE = (
    'global-boundary-state-joint-global-consumer-failure'
  )
  STATE_REPLAY_FAILURE = 'global-boundary-state-joint-state-replay-failure'
  RESIDUAL_AUDIT_FAILURE = (
    'global-boundary-state-joint-residual-audit-failure'
  )
  RESIDUAL_DESCENT_FAILURE = (
    'global-boundary-state-joint-residual-descent-failure'
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


def _dimensioned_channel_maxima(
  response: MocEulerTwoSidedInterfaceResponse | None,
  request: MocReflectedDomainGlobalTwoSidedMovingInterfaceRequest | None,
) -> tuple[float, float, float] | None:
  """Return normalized maxima for the three signed conservative channels."""

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
    max((abs(float(value)) / tolerance for value in channel), default=float('inf'))
    for channel, tolerance in zip(channels, tolerances, strict=True)
  )
  if any(not isfinite(value) for value in maxima):
    return None
  return maxima


def _dimensioned_channel_descent(
  before: tuple[float, float, float] | None,
  after: tuple[float, float, float] | None,
) -> bool:
  """Require no normalized channel worsening and one strict decrease."""

  if before is None or after is None:
    return False
  numerical_tolerance = 1.0e-12
  nonincreasing = all(
    next_value
    <= current_value + numerical_tolerance * max(1.0, abs(current_value))
    for current_value, next_value in zip(before, after, strict=True)
  )
  strict = any(
    next_value
    < current_value - numerical_tolerance * max(1.0, abs(current_value))
    for current_value, next_value in zip(before, after, strict=True)
  )
  return bool(nonincreasing and strict)


def _options(value: Mapping[str, Any] | None) -> dict[str, Any]:
  if value is None:
    return {'consume_target_geometry': True}
  if not isinstance(value, Mapping):
    raise TypeError('boundary_condition_options must be a mapping when supplied')
  resolved = dict(value)
  reserved = ('request', 'source_closure', 'base_target')
  collisions = tuple(key for key in reserved if key in resolved)
  if collisions:
    raise ValueError(
      'boundary_condition_options cannot override positional controls: '
      f'{", ".join(collisions)}'
    )
  if resolved.get('consume_target_geometry', True) is not True:
    raise ValueError(
      'joint boundary-state consumption requires consume_target_geometry=True'
    )
  resolved['consume_target_geometry'] = True
  return resolved


def _strict_descent(
  before: float,
  after: float,
  minimum_fraction: float,
) -> bool:
  if not isfinite(before) or not isfinite(after):
    return False
  if not isfinite(minimum_fraction) or minimum_fraction < 0.0:
    return False
  if before <= 0.0:
    return after < before
  return after < before * (1.0 - minimum_fraction)


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalBoundaryStateJointSolveResult:
  """Evidence from one handoff-consuming global/state replay."""

  status: MocReflectedDomainGlobalBoundaryStateJointSolveStatus
  handoff: MocReflectedDomainGlobalBoundaryStateFeedbackHandoff | None
  source_closure: MocReflectedDomainGlobalPhysicalClosureResult | None = None
  frontier_request: MocReflectedDomainGlobalFrontierReconciliationRequest | None = None
  consumed_target: MocPhysicalFieldEulerBoundaryPressureTarget | None = None
  boundary_condition: MocReflectedDomainGlobalFrontierBoundaryConditionResult | None = None
  state_request: MocReflectedDomainGlobalTwoSidedMovingInterfaceRequest | None = None
  state_result: MocReflectedDomainGlobalTwoSidedMovingInterfaceResult | None = None
  conservative_residual_audit: MocEulerTwoSidedConservativeResidualAudit | None = None
  shock_geometry_response: MocEulerShockBoundaryCurveResult | None = None
  geometry_response_closure: MocReflectedDomainGlobalPhysicalClosureResult | None = None
  baseline_residual_norm: float | None = None
  refreshed_residual_norm: float | None = None
  baseline_dimensioned_channel_maxima: tuple[float, ...] = ()
  refreshed_dimensioned_channel_maxima: tuple[float, ...] = ()
  handoff_lineage_verified: bool = False
  global_consumer_invoked: bool = False
  fresh_global_solve_verified: bool = False
  target_consumption_verified: bool = False
  target_geometry_consumption_verified: bool = False
  shock_geometry_response_consumed: bool = False
  shock_geometry_response_lineage_verified: bool = False
  dimensioned_channels_verified: bool = False
  dimensioned_channel_descent_verified: bool = False
  state_solver_invoked: bool = False
  state_lineage_verified: bool = False
  signed_residuals_verified: bool = False
  moving_state_verified: bool = False
  independent_residual_audit_verified: bool = False
  residual_descent_verified: bool = False
  handoff_consumed: bool = False
  joint_state_update_verified: bool = False
  global_coupling_verified: bool = False
  downstream_boundary_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalBoundaryStateJointSolveStatus,
    ):
      raise TypeError('status must be a typed joint-solve status')
    if self.handoff is not None and not isinstance(
      self.handoff,
      MocReflectedDomainGlobalBoundaryStateFeedbackHandoff,
    ):
      raise TypeError('handoff must be typed or None')
    if self.source_closure is not None and not isinstance(
      self.source_closure,
      MocReflectedDomainGlobalPhysicalClosureResult,
    ):
      raise TypeError('source_closure must be typed or None')
    if self.frontier_request is not None and not isinstance(
      self.frontier_request,
      MocReflectedDomainGlobalFrontierReconciliationRequest,
    ):
      raise TypeError('frontier_request must be typed or None')
    if self.consumed_target is not None and not isinstance(
      self.consumed_target,
      MocPhysicalFieldEulerBoundaryPressureTarget,
    ):
      raise TypeError('consumed_target must be typed or None')
    if self.boundary_condition is not None and not isinstance(
      self.boundary_condition,
      MocReflectedDomainGlobalFrontierBoundaryConditionResult,
    ):
      raise TypeError('boundary_condition must be typed or None')
    if self.state_request is not None and not isinstance(
      self.state_request,
      MocReflectedDomainGlobalTwoSidedMovingInterfaceRequest,
    ):
      raise TypeError('state_request must be typed or None')
    if self.state_result is not None and not isinstance(
      self.state_result,
      MocReflectedDomainGlobalTwoSidedMovingInterfaceResult,
    ):
      raise TypeError('state_result must be typed or None')
    if self.conservative_residual_audit is not None and not isinstance(
      self.conservative_residual_audit,
      MocEulerTwoSidedConservativeResidualAudit,
    ):
      raise TypeError('conservative_residual_audit must be typed or None')
    if self.shock_geometry_response is not None and not isinstance(
      self.shock_geometry_response,
      MocEulerShockBoundaryCurveResult,
    ):
      raise TypeError('shock_geometry_response must be typed or None')
    if self.geometry_response_closure is not None and not isinstance(
      self.geometry_response_closure,
      MocReflectedDomainGlobalPhysicalClosureResult,
    ):
      raise TypeError('geometry_response_closure must be typed or None')
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
      'handoff_lineage_verified',
      'global_consumer_invoked',
      'fresh_global_solve_verified',
      'target_consumption_verified',
      'target_geometry_consumption_verified',
      'shock_geometry_response_consumed',
      'shock_geometry_response_lineage_verified',
      'dimensioned_channels_verified',
      'dimensioned_channel_descent_verified',
      'state_solver_invoked',
      'state_lineage_verified',
      'signed_residuals_verified',
      'moving_state_verified',
      'independent_residual_audit_verified',
      'residual_descent_verified',
      'handoff_consumed',
      'joint_state_update_verified',
      'global_coupling_verified',
      'downstream_boundary_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    if self.global_coupling_verified or self.downstream_boundary_closure_verified:
      raise ValueError('joint research state solve cannot claim canonical coupling')
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError('joint research state solve must remain promotion-blocked')
    for name in ('baseline_residual_norm', 'refreshed_residual_norm'):
      value = getattr(self, name)
      if value is not None:
        numeric = float(value)
        if not isfinite(numeric) or numeric < 0.0:
          raise ValueError(f'{name} must be finite and nonnegative when supplied')
        object.__setattr__(self, name, numeric)
    if self.status is (
      MocReflectedDomainGlobalBoundaryStateJointSolveStatus
      .CONVERGED_RESEARCH_JOINT_STATE_UPDATE
    ) and not (
      self.handoff_consumed
      and self.joint_state_update_verified
      and self.residual_descent_verified
    ):
      raise ValueError('converged joint update must pass consumption and descent gates')
    if self.dimensioned_channels_verified and not (
      len(self.baseline_dimensioned_channel_maxima) == 3
      and len(self.refreshed_dimensioned_channel_maxima) == 3
    ):
      raise ValueError(
        'dimensioned_channels_verified requires three baseline and refreshed '
        'channel maxima'
      )
    if self.dimensioned_channel_descent_verified and not (
      self.dimensioned_channels_verified
    ):
      raise ValueError(
        'dimensioned_channel_descent_verified requires verified dimensioned channels'
      )
    object.__setattr__(self, 'message', str(self.message))

  @property
  def converged_research_joint_update(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalBoundaryStateJointSolveStatus
      .CONVERGED_RESEARCH_JOINT_STATE_UPDATE
      and self.handoff_consumed
      and self.joint_state_update_verified
      and self.residual_descent_verified
    )

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': MOC_REFLECTED_DOMAIN_GLOBAL_BOUNDARY_STATE_JOINT_SOLVE_OPERATOR_ID,
      'status': self.status.value,
      'converged_research_joint_update': self.converged_research_joint_update,
      'handoff_lineage_verified': self.handoff_lineage_verified,
      'global_consumer_invoked': self.global_consumer_invoked,
      'fresh_global_solve_verified': self.fresh_global_solve_verified,
      'target_consumption_verified': self.target_consumption_verified,
      'target_geometry_consumption_verified': self.target_geometry_consumption_verified,
      'shock_geometry_response_consumed': self.shock_geometry_response_consumed,
      'shock_geometry_response_lineage_verified': (
        self.shock_geometry_response_lineage_verified
      ),
      'dimensioned_channels_verified': self.dimensioned_channels_verified,
      'dimensioned_channel_descent_verified': (
        self.dimensioned_channel_descent_verified
      ),
      'state_solver_invoked': self.state_solver_invoked,
      'state_lineage_verified': self.state_lineage_verified,
      'signed_residuals_verified': self.signed_residuals_verified,
      'moving_state_verified': self.moving_state_verified,
      'independent_residual_audit_verified': self.independent_residual_audit_verified,
      'residual_descent_verified': self.residual_descent_verified,
      'handoff_consumed': self.handoff_consumed,
      'joint_state_update_verified': self.joint_state_update_verified,
      'global_coupling_verified': False,
      'downstream_boundary_closure_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'source_closure_fingerprint': (
        None if self.source_closure is None else _fingerprint(self.source_closure)
      ),
      'baseline_residual_norm': self.baseline_residual_norm,
      'refreshed_residual_norm': self.refreshed_residual_norm,
      'baseline_dimensioned_channel_maxima': list(
        self.baseline_dimensioned_channel_maxima
      ),
      'refreshed_dimensioned_channel_maxima': list(
        self.refreshed_dimensioned_channel_maxima
      ),
      'frontier_request': (
        None if self.frontier_request is None else self.frontier_request.as_report()
      ),
      'consumed_target': (
        None if self.consumed_target is None else self.consumed_target.as_report()
      ),
      'boundary_condition': (
        None
        if self.boundary_condition is None
        else self.boundary_condition.as_report()
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
      'shock_geometry_response': (
        None
        if self.shock_geometry_response is None
        else self.shock_geometry_response.as_report()
      ),
      'geometry_response_closure_fingerprint': (
        None
        if self.geometry_response_closure is None
        else _fingerprint(self.geometry_response_closure)
      ),
      'handoff': None if self.handoff is None else self.handoff.as_report(),
      'claim_status': (
        'research-only joint state update; strict residual descent, canonical '
        'global coupling, shock-cell promotion, Signature/FPA production, and '
        'external validation remain separate gates'
      ),
      'message': self.message,
    }


def _result(
  status: MocReflectedDomainGlobalBoundaryStateJointSolveStatus,
  handoff: MocReflectedDomainGlobalBoundaryStateFeedbackHandoff | None,
  message: str,
  **kwargs: Any,
) -> MocReflectedDomainGlobalBoundaryStateJointSolveResult:
  return MocReflectedDomainGlobalBoundaryStateJointSolveResult(
    status=status,
    handoff=handoff,
    message=message,
    **kwargs,
  )


def _handoff_inputs(
  handoff: MocReflectedDomainGlobalBoundaryStateFeedbackHandoff,
) -> tuple[
  MocReflectedDomainGlobalPhysicalClosureResult,
  MocReflectedDomainGlobalFrontierReconciliationRequest,
  MocPhysicalFieldEulerBoundaryPressureTarget,
]:
  """Recover the exact source/request/extended target triple."""

  run = handoff.boundary_feedback_run
  if not run.iterations:
    raise ValueError('handoff retained no boundary feedback iteration')
  iteration = run.iterations[-1]
  if iteration.proposal is not handoff.proposal:
    raise ValueError('handoff proposal is not the final retained proposal')
  request = iteration.frontier_request
  if request is None or not request.lineage_verified:
    raise ValueError('handoff retained no lineage-verified frontier request')
  source = iteration.source_closure
  if request.source_closure_fingerprint != _fingerprint(source):
    raise ValueError('frontier request source fingerprint does not match iteration')
  proposal_fingerprint = moc_reflected_domain_global_frontier_proposal_fingerprint(
    handoff.proposal
  )
  if request.source_proposal_fingerprint != proposal_fingerprint:
    raise ValueError('frontier request proposal fingerprint does not match handoff')
  target: MocPhysicalFieldEulerBoundaryPressureTarget | None = None
  if iteration.frame_extension is not None:
    target = iteration.frame_extension.extended_target
  if target is None:
    target = iteration.base_target
  if target is None:
    raise ValueError('handoff retained no exact target frame for the joint consumer')
  if (
    target.source_closure_fingerprint != _fingerprint(source)
    or target.source_proposal_fingerprint != proposal_fingerprint
  ):
    raise ValueError('extended target does not retain exact source/proposal lineage')
  if run.final_closure is not iteration.next_closure:
    raise ValueError('handoff final closure is not the iteration output closure')
  if _fingerprint(run.final_closure) != handoff.state_source_closure_fingerprint:
    raise ValueError('handoff state closure fingerprint does not match final closure')
  if not handoff.ready_for_joint_global_resolve:
    raise ValueError('handoff is not ready for joint global consumption')
  return source, request, target


def run_reflected_domain_global_boundary_state_joint_solve(
  handoff: MocReflectedDomainGlobalBoundaryStateFeedbackHandoff | None,
  *,
  boundary_condition_options: Mapping[str, Any] | None = None,
  consumer_id: str = 'moc-global-boundary-state-joint-consumer-v1',
) -> MocReflectedDomainGlobalBoundaryStateJointSolveResult:
  """Consume one exact handoff through a fresh global/stateful solve.

  The extended target is the only frame passed to the fresh global consumer.
  The conservative residual channels are not interpolated into that target;
  they are retained as the baseline against which the fresh state replay is
  independently measured.
  """

  if not isinstance(
    handoff,
    MocReflectedDomainGlobalBoundaryStateFeedbackHandoff,
  ):
    return _result(
      MocReflectedDomainGlobalBoundaryStateJointSolveStatus.INVALID_INPUT,
      None,
      'handoff must be a typed global boundary-state feedback handoff',
    )
  try:
    options = _options(boundary_condition_options)
    resolved_consumer_id = str(consumer_id)
    if not resolved_consumer_id:
      raise ValueError('consumer_id must be non-empty')
    source, request, target = _handoff_inputs(handoff)
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _result(
      MocReflectedDomainGlobalBoundaryStateJointSolveStatus.HANDOFF_LINEAGE_FAILURE,
      handoff,
      f'joint handoff setup failed closed: {error}',
    )

  try:
    boundary_condition = run_reflected_domain_global_frontier_boundary_conditioned_resolve(
      request,
      source,
      base_target=target,
      **options,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _result(
      MocReflectedDomainGlobalBoundaryStateJointSolveStatus.GLOBAL_CONSUMER_FAILURE,
      handoff,
      f'fresh global boundary-state consumer raised: {error}',
      source_closure=source,
      frontier_request=request,
      consumed_target=target,
      handoff_lineage_verified=True,
      global_consumer_invoked=True,
    )
  candidate = boundary_condition.conditioned_closure
  candidate_fingerprint = None if candidate is None else _fingerprint(candidate)
  target_consumed = bool(
    boundary_condition.target_boundary_condition_consumed
    and boundary_condition.target_lineage_verified
    and boundary_condition.target_composition_verified
    and boundary_condition.target_coverage_verified
  )
  target_geometry_consumed = bool(
    target_consumed
    and boundary_condition.target_geometry_consumed
    and boundary_condition.geometry_conditioning_verified
  )
  fresh_global = bool(
    boundary_condition.status
    is MocReflectedDomainGlobalFrontierBoundaryConditionStatus
    .CONVERGED_RESEARCH_BOUNDARY_CONDITION
    and candidate is not None
    and candidate is not source
    and candidate.converged
    and candidate.physical_closure_verified
    and candidate_fingerprint == handoff.state_source_closure_fingerprint
    and boundary_condition.fidelity_isolation_verified
  )
  if not target_consumed or not target_geometry_consumed or not fresh_global:
    return _result(
      MocReflectedDomainGlobalBoundaryStateJointSolveStatus.GLOBAL_CONSUMER_FAILURE,
      handoff,
      'fresh global consumer did not retain exact target geometry consumption '
      'and the expected state closure lineage: '
      f'{boundary_condition.message}',
      source_closure=source,
      frontier_request=request,
      consumed_target=target,
      boundary_condition=boundary_condition,
      handoff_lineage_verified=True,
      global_consumer_invoked=True,
      fresh_global_solve_verified=fresh_global,
      target_consumption_verified=target_consumed,
      target_geometry_consumption_verified=target_geometry_consumed,
    )
  assert candidate is not None
  initial_response = _response(handoff.two_sided_result)
  geometry_response = (
    None if initial_response is None else initial_response.next_shock_boundary
  )
  if geometry_response is None:
    return _result(
      MocReflectedDomainGlobalBoundaryStateJointSolveStatus.GLOBAL_CONSUMER_FAILURE,
      handoff,
      'fresh global target consumption retained no solver-owned shock geometry '
      'response for the global closure consumer',
      source_closure=source,
      frontier_request=request,
      consumed_target=target,
      boundary_condition=boundary_condition,
      shock_geometry_response=geometry_response,
      handoff_lineage_verified=True,
      global_consumer_invoked=True,
      fresh_global_solve_verified=False,
      target_consumption_verified=target_consumed,
      target_geometry_consumption_verified=target_geometry_consumed,
    )
  try:
    geometry_response_closure = (
      consume_reflected_domain_global_shock_geometry_response(
        candidate,
        geometry_response,
      )
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _result(
      MocReflectedDomainGlobalBoundaryStateJointSolveStatus.GLOBAL_CONSUMER_FAILURE,
      handoff,
      f'global shock geometry response consumer raised: {error}',
      source_closure=source,
      frontier_request=request,
      consumed_target=target,
      boundary_condition=boundary_condition,
      shock_geometry_response=geometry_response,
      handoff_lineage_verified=True,
      global_consumer_invoked=True,
      fresh_global_solve_verified=False,
      target_consumption_verified=target_consumed,
      target_geometry_consumption_verified=target_geometry_consumed,
    )
  corrected_global_euler = geometry_response_closure.global_euler
  shock_geometry_response_consumed = bool(
    geometry_response_closure.converged
    and geometry_response_closure.physical_closure_verified
    and geometry_response_closure is not candidate
    and corrected_global_euler is not None
    and corrected_global_euler.shock_boundary is not None
    and corrected_global_euler.shock_boundary is not geometry_response
    and tuple(corrected_global_euler.remeshed_shock_points_m)
    == tuple(geometry_response.shock_points_m)
  )
  shock_geometry_response_lineage_verified = bool(
    shock_geometry_response_consumed
    and geometry_response_closure.source_band is candidate.source_band
    and geometry_response_closure.global_remesh is candidate.global_remesh
    and geometry_response_closure.source_pressure_target_source
    == candidate.source_pressure_target_source
  )
  if not shock_geometry_response_consumed or not shock_geometry_response_lineage_verified:
    return _result(
      MocReflectedDomainGlobalBoundaryStateJointSolveStatus.GLOBAL_CONSUMER_FAILURE,
      handoff,
      'solver-owned shock geometry response was not independently consumed '
      'with the exact source-band/global-remesh lineage: '
      f'{geometry_response_closure.message}',
      source_closure=source,
      frontier_request=request,
      consumed_target=target,
      boundary_condition=boundary_condition,
      shock_geometry_response=geometry_response,
      geometry_response_closure=geometry_response_closure,
      handoff_lineage_verified=True,
      global_consumer_invoked=True,
      fresh_global_solve_verified=False,
      target_consumption_verified=target_consumed,
      target_geometry_consumption_verified=target_geometry_consumed,
      shock_geometry_response_consumed=shock_geometry_response_consumed,
      shock_geometry_response_lineage_verified=shock_geometry_response_lineage_verified,
    )
  fresh_global_with_geometry = bool(
    fresh_global
    and shock_geometry_response_consumed
    and shock_geometry_response_lineage_verified
  )
  baseline_norm = float(handoff.final_residual_norm)
  state_request = replace(
    handoff.two_sided_result.request,
    closure=geometry_response_closure,
    source=f'{resolved_consumer_id}-state-replay-v1',
  )
  try:
    state_result = solve_reflected_domain_global_two_sided_moving_interface(
      state_request
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _result(
      MocReflectedDomainGlobalBoundaryStateJointSolveStatus.STATE_REPLAY_FAILURE,
      handoff,
      f'fresh conservative state replay raised: {error}',
      source_closure=source,
      frontier_request=request,
      consumed_target=target,
      boundary_condition=boundary_condition,
      state_request=state_request,
      shock_geometry_response=geometry_response,
      geometry_response_closure=geometry_response_closure,
      handoff_lineage_verified=True,
      global_consumer_invoked=True,
      fresh_global_solve_verified=fresh_global_with_geometry,
      target_consumption_verified=target_consumed,
      target_geometry_consumption_verified=target_geometry_consumed,
      shock_geometry_response_consumed=shock_geometry_response_consumed,
      shock_geometry_response_lineage_verified=shock_geometry_response_lineage_verified,
      baseline_dimensioned_channel_maxima=(
        _dimensioned_channel_maxima(initial_response, state_request) or ()
      ),
      state_solver_invoked=True,
      baseline_residual_norm=baseline_norm,
    )
  residual = state_result.conservative_residual_result
  audit = state_result.conservative_residual_audit
  response = _response(state_result)
  baseline_dimensioned_channel_maxima = (
    _dimensioned_channel_maxima(initial_response, state_request)
  )
  refreshed_dimensioned_channel_maxima = _dimensioned_channel_maxima(
    response,
    state_request,
  )
  dimensioned_channels_verified = bool(
    baseline_dimensioned_channel_maxima is not None
    and refreshed_dimensioned_channel_maxima is not None
  )
  dimensioned_channel_descent_verified = _dimensioned_channel_descent(
    baseline_dimensioned_channel_maxima,
    refreshed_dimensioned_channel_maxima,
  )
  state_lineage = bool(
    state_result.request is state_request
    and state_result.source_closure_fingerprint
    == _fingerprint(geometry_response_closure)
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
      MocReflectedDomainGlobalBoundaryStateJointSolveStatus.RESIDUAL_AUDIT_FAILURE,
      handoff,
      'fresh state replay retained no final conservative residual norm',
      source_closure=source,
      frontier_request=request,
      consumed_target=target,
      boundary_condition=boundary_condition,
      state_request=state_request,
      state_result=state_result,
      conservative_residual_audit=audit,
      shock_geometry_response=geometry_response,
      geometry_response_closure=geometry_response_closure,
      handoff_lineage_verified=True,
      global_consumer_invoked=True,
      fresh_global_solve_verified=fresh_global_with_geometry,
      target_consumption_verified=target_consumed,
      target_geometry_consumption_verified=target_geometry_consumed,
      shock_geometry_response_consumed=shock_geometry_response_consumed,
      shock_geometry_response_lineage_verified=shock_geometry_response_lineage_verified,
      baseline_dimensioned_channel_maxima=(
        baseline_dimensioned_channel_maxima or ()
      ),
      refreshed_dimensioned_channel_maxima=(
        refreshed_dimensioned_channel_maxima or ()
      ),
      dimensioned_channels_verified=dimensioned_channels_verified,
      dimensioned_channel_descent_verified=dimensioned_channel_descent_verified,
      state_solver_invoked=True,
      state_lineage_verified=state_lineage,
      signed_residuals_verified=signed,
      moving_state_verified=moving,
      independent_residual_audit_verified=independent_audit,
      baseline_residual_norm=baseline_norm,
    )
  descent = _strict_descent(
    baseline_norm,
    float(refreshed_norm),
    state_request.minimum_residual_descent_fraction,
  )
  common = dict(
    source_closure=source,
    frontier_request=request,
    consumed_target=target,
    boundary_condition=boundary_condition,
    state_request=state_request,
    state_result=state_result,
    conservative_residual_audit=audit,
    shock_geometry_response=geometry_response,
    geometry_response_closure=geometry_response_closure,
    handoff_lineage_verified=True,
    global_consumer_invoked=True,
    fresh_global_solve_verified=fresh_global_with_geometry,
    target_consumption_verified=target_consumed,
    target_geometry_consumption_verified=target_geometry_consumed,
    shock_geometry_response_consumed=shock_geometry_response_consumed,
    shock_geometry_response_lineage_verified=shock_geometry_response_lineage_verified,
    baseline_dimensioned_channel_maxima=(
      baseline_dimensioned_channel_maxima or ()
    ),
    refreshed_dimensioned_channel_maxima=(
      refreshed_dimensioned_channel_maxima or ()
    ),
    dimensioned_channels_verified=dimensioned_channels_verified,
    dimensioned_channel_descent_verified=dimensioned_channel_descent_verified,
    state_solver_invoked=True,
    state_lineage_verified=state_lineage,
    signed_residuals_verified=signed,
    moving_state_verified=moving,
    independent_residual_audit_verified=independent_audit,
    residual_descent_verified=descent,
    handoff_consumed=bool(
      state_lineage
      and signed
      and moving
      and shock_geometry_response_consumed
      and shock_geometry_response_lineage_verified
      and dimensioned_channels_verified
      and dimensioned_channel_descent_verified
    ),
    joint_state_update_verified=bool(
      state_lineage
      and signed
      and moving
      and independent_audit
      and shock_geometry_response_consumed
      and shock_geometry_response_lineage_verified
      and dimensioned_channels_verified
      and dimensioned_channel_descent_verified
    ),
    baseline_residual_norm=baseline_norm,
    refreshed_residual_norm=float(refreshed_norm),
  )
  if (
    not signed
    or not independent_audit
    or not moving
    or not state_lineage
    or not dimensioned_channels_verified
    or not dimensioned_channel_descent_verified
  ):
    return _result(
      MocReflectedDomainGlobalBoundaryStateJointSolveStatus.RESIDUAL_AUDIT_FAILURE,
      handoff,
      'fresh global target consumption completed, but the replayed '
      'conservative state did not pass every independent or dimensioned '
      'channel audit gate',
      **common,
    )
  if not descent:
    return _result(
      MocReflectedDomainGlobalBoundaryStateJointSolveStatus.RESIDUAL_DESCENT_FAILURE,
      handoff,
      'fresh global/stateful consumption completed, but the independently '
      'remeasured conservative residual did not strictly descend from the '
      f'retained baseline ({baseline_norm:.12g} -> {float(refreshed_norm):.12g})',
      **common,
    )
  return _result(
    MocReflectedDomainGlobalBoundaryStateJointSolveStatus
    .CONVERGED_RESEARCH_JOINT_STATE_UPDATE,
    handoff,
    'fresh global target consumption and independently audited conservative '
    'state replay achieved strict residual descent; canonical coupling and '
    'production gates remain closed',
    **common,
  )
