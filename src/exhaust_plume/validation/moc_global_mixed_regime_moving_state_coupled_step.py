"""Research-only moving/global composition for the reflected MOC lane.

This module composes the currently verified research seams into one explicit
end-to-end step:

``full-state downstream solve -> strict moving conservative/entropy response
-> fresh global shock-geometry reconciliation -> fresh downstream trace``.

Every front movement is owned by the conservative residual solver and every
updated global field is independently rebuilt from the retained source band.
The characteristic upstream state equation and the canonical free-boundary
fixed point are still unavailable, so this operator remains promotion-blocked
even when all local research gates pass.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Any

from exhaust_plume.models.moc.global_coupled_downstream import (
  MocReflectedDomainGlobalCoupledDownstreamResult,
  solve_reflected_domain_global_coupled_downstream,
)
from exhaust_plume.models.moc.global_mixed_regime_state_consumer import (
  MocReflectedDomainGlobalMixedRegimeStateConsumerResult,
  consume_reflected_domain_global_mixed_regime_state,
)
from exhaust_plume.models.moc.global_physical_closure import (
  MocReflectedDomainGlobalPhysicalClosureResult,
  consume_reflected_domain_global_shock_geometry_response,
  moc_reflected_domain_global_physical_closure_fingerprint,
)
from exhaust_plume.models.moc.global_two_sided_moving_interface import (
  MocReflectedDomainGlobalTwoSidedMovingInterfaceRequest,
  MocReflectedDomainGlobalTwoSidedMovingInterfaceResult,
  solve_reflected_domain_global_two_sided_moving_interface,
)
from exhaust_plume.models.moc.euler_shock_boundary import (
  MocEulerShockBoundaryCurveResult,
)
from exhaust_plume.models.moc.euler_two_sided_moving_interface import (
  MocEulerTwoSidedInterfaceResponse,
)
from exhaust_plume.validation.moc_global_mixed_regime_state_coupled_step import (
  MocReflectedDomainGlobalMixedRegimeStateCoupledStepResult,
  run_reflected_domain_global_mixed_regime_state_coupled_step,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_MOVING_STATE_COUPLED_STEP_OPERATOR_ID',
  'MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepStatus',
  'MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepResult',
  'run_reflected_domain_global_mixed_regime_moving_state_coupled_step',
)


MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_MOVING_STATE_COUPLED_STEP_OPERATOR_ID = (
  'op.moc.reflected-domain.global-mixed-regime-moving-state-coupled-step-v1'
)


class MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepStatus(
  str,
  Enum,
):
  """Typed outcomes of one moving/global research composition."""

  CONVERGED_RESEARCH_MOVING_GLOBAL_STATE_STEP = (
    'converged-research-global-mixed-regime-moving-state-coupled-step'
  )
  COMPLETED_RESEARCH_MOVING_GLOBAL_STATE_STEP_WITH_OPEN_RESIDUAL = (
    'completed-research-global-mixed-regime-moving-state-coupled-step-with-open-residual'
  )
  INVALID_INPUT = 'invalid_input'
  STATE_COUPLED_STEP_FAILURE = (
    'global-mixed-regime-moving-state-coupled-step-state-step-failure'
  )
  MOVING_INTERFACE_FAILURE = (
    'global-mixed-regime-moving-state-coupled-step-moving-interface-failure'
  )
  GEOMETRY_RESPONSE_FAILURE = (
    'global-mixed-regime-moving-state-coupled-step-geometry-response-failure'
  )
  GLOBAL_RECONCILIATION_FAILURE = (
    'global-mixed-regime-moving-state-coupled-step-global-reconciliation-failure'
  )
  DOWNSTREAM_REFRESH_FAILURE = (
    'global-mixed-regime-moving-state-coupled-step-downstream-refresh-failure'
  )
  FINAL_STATE_AUDIT_FAILURE = (
    'global-mixed-regime-moving-state-coupled-step-final-state-audit-failure'
  )
  RESIDUAL_DESCENT_FAILURE = (
    'global-mixed-regime-moving-state-coupled-step-residual-descent-failure'
  )
####


def _options(
  value: Mapping[str, Any] | None,
  name: str,
  *,
  reserved: tuple[str, ...],
) -> dict[str, Any]:
  if value is None:
    return {}
  ####
  if not isinstance(value, Mapping):
    raise TypeError(f'{name} must be a mapping when supplied')
  ####
  resolved = dict(value)
  collisions = tuple(key for key in reserved if key in resolved)
  if collisions:
    raise ValueError(
      f'{name} cannot override composed controls: {", ".join(collisions)}'
    )
  ####
  return resolved
####


def _componentwise_descent(
  before: tuple[float, ...],
  after: tuple[float, ...],
) -> bool:
  """Require equal-width finite vectors with no worsening component."""

  if not before or len(before) != len(after):
    return False
  ####
  if any(
    not isfinite(value) or value < 0.0
    for value in (*before, *after)
  ):
    return False
  ####
  tolerance = 1.0e-12
  nonincreasing = all(
    next_value
    <= current_value + tolerance * max(1.0, abs(current_value))
    for current_value, next_value in zip(before, after, strict=True)
  )
  strict = any(
    next_value
    < current_value - tolerance * max(1.0, abs(current_value))
    for current_value, next_value in zip(before, after, strict=True)
  )
  return bool(nonincreasing and strict)
####


def _vector(
  downstream: MocReflectedDomainGlobalCoupledDownstreamResult | None,
) -> tuple[float, ...]:
  if downstream is None:
    return ()
  ####
  value = downstream.normalized_coupled_state_residual_vector
  return () if value is None else tuple(float(item) for item in value)
####


def _ambient_pressure(
  closure: MocReflectedDomainGlobalPhysicalClosureResult,
  downstream: MocReflectedDomainGlobalCoupledDownstreamResult,
  supplied: float | None,
) -> float | None:
  if supplied is not None:
    return float(supplied)
  ####
  request = downstream.mixed_regime_request
  if request is not None:
    value = getattr(request, 'ambient_pressure_Pa', None)
    if value is not None:
      return float(value)
    ####
  ####
  source_band = closure.source_band
  if source_band is None or source_band.ambient_pressure_Pa is None:
    return None
  ####
  return float(source_band.ambient_pressure_Pa)
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepResult:
  """Evidence from one strict moving/global research composition."""

  status: MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepStatus
  source_closure: MocReflectedDomainGlobalPhysicalClosureResult | None
  source_downstream: MocReflectedDomainGlobalCoupledDownstreamResult | None
  state_step: MocReflectedDomainGlobalMixedRegimeStateCoupledStepResult | None = None
  moving_interface: MocReflectedDomainGlobalTwoSidedMovingInterfaceResult | None = None
  moving_response: MocEulerTwoSidedInterfaceResponse | None = None
  shock_geometry_response: MocEulerShockBoundaryCurveResult | None = None
  geometry_closure: MocReflectedDomainGlobalPhysicalClosureResult | None = None
  final_downstream: MocReflectedDomainGlobalCoupledDownstreamResult | None = None
  final_state_consumer: (
    MocReflectedDomainGlobalMixedRegimeStateConsumerResult | None
  ) = None
  initial_residual_vector: tuple[float, ...] = ()
  final_residual_vector: tuple[float, ...] = ()
  state_target_consumed_by_downstream_equations: bool = False
  moving_lineage_verified: bool = False
  moving_conservative_flux_closure_verified: bool = False
  moving_entropy_transition_verified: bool = False
  moving_global_physical_field_consumed: bool = False
  moving_geometry_reconciliation_verified: bool = False
  final_trace_audit_verified: bool = False
  componentwise_residual_descent_verified: bool = False
  require_componentwise_residual_descent: bool = True
  upstream_state_equation_consumed: bool = False
  global_coupling_verified: bool = False
  canonical_free_boundary_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepStatus,
    ):
      raise TypeError('status must be a typed moving/global state-step status')
    ####
    for name, expected in (
      ('source_closure', MocReflectedDomainGlobalPhysicalClosureResult),
      ('source_downstream', MocReflectedDomainGlobalCoupledDownstreamResult),
      (
        'state_step',
        MocReflectedDomainGlobalMixedRegimeStateCoupledStepResult,
      ),
      (
        'moving_interface',
        MocReflectedDomainGlobalTwoSidedMovingInterfaceResult,
      ),
      ('moving_response', MocEulerTwoSidedInterfaceResponse),
      ('shock_geometry_response', MocEulerShockBoundaryCurveResult),
      ('geometry_closure', MocReflectedDomainGlobalPhysicalClosureResult),
      ('final_downstream', MocReflectedDomainGlobalCoupledDownstreamResult),
      (
        'final_state_consumer',
        MocReflectedDomainGlobalMixedRegimeStateConsumerResult,
      ),
    ):
      value = getattr(self, name)
      if value is not None and not isinstance(value, expected):
        raise TypeError(f'{name} must retain its typed research result')
      ####
    ####
    for name in ('initial_residual_vector', 'final_residual_vector'):
      values = tuple(float(value) for value in getattr(self, name))
      if any(not isfinite(value) or value < 0.0 for value in values):
        raise ValueError(f'{name} must contain finite nonnegative values')
      ####
      object.__setattr__(self, name, values)
    ####
    for name in (
      'state_target_consumed_by_downstream_equations',
      'moving_lineage_verified',
      'moving_conservative_flux_closure_verified',
      'moving_entropy_transition_verified',
      'moving_global_physical_field_consumed',
      'moving_geometry_reconciliation_verified',
      'final_trace_audit_verified',
      'componentwise_residual_descent_verified',
      'require_componentwise_residual_descent',
      'upstream_state_equation_consumed',
      'global_coupling_verified',
      'canonical_free_boundary_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if self.upstream_state_equation_consumed or self.global_coupling_verified:
      raise ValueError(
        'moving/global research composition cannot claim upstream global coupling'
      )
    ####
    if self.canonical_free_boundary_verified:
      raise ValueError(
        'moving/global research composition cannot claim canonical closure'
      )
    ####
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError(
        'moving/global research composition must remain promotion-blocked'
      )
    ####
    if self.status is (
      MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepStatus
      .CONVERGED_RESEARCH_MOVING_GLOBAL_STATE_STEP
    ) and not (
      self.state_target_consumed_by_downstream_equations
      and self.moving_lineage_verified
      and self.moving_conservative_flux_closure_verified
      and self.moving_entropy_transition_verified
      and self.moving_global_physical_field_consumed
      and self.moving_geometry_reconciliation_verified
      and self.final_trace_audit_verified
      and self.componentwise_residual_descent_verified
    ):
      raise ValueError(
        'converged moving/global step must pass state, front, geometry, trace, '
        'and component-wise residual gates'
      )
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def research_moving_global_state_step_verified(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepStatus
      .CONVERGED_RESEARCH_MOVING_GLOBAL_STATE_STEP
      and self.state_target_consumed_by_downstream_equations
      and self.moving_lineage_verified
      and self.moving_conservative_flux_closure_verified
      and self.moving_entropy_transition_verified
      and self.moving_global_physical_field_consumed
      and self.moving_geometry_reconciliation_verified
      and self.final_trace_audit_verified
      and self.componentwise_residual_descent_verified
    )
  ####

  @property
  def source_closure_fingerprint(self) -> str | None:
    if self.source_closure is None:
      return None
    ####
    return moc_reflected_domain_global_physical_closure_fingerprint(
      self.source_closure
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': (
        MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_MOVING_STATE_COUPLED_STEP_OPERATOR_ID
      ),
      'status': self.status.value,
      'research_moving_global_state_step_verified': (
        self.research_moving_global_state_step_verified
      ),
      'source_closure_fingerprint': self.source_closure_fingerprint,
      'initial_residual_vector': self.initial_residual_vector,
      'final_residual_vector': self.final_residual_vector,
      'state_target_consumed_by_downstream_equations': (
        self.state_target_consumed_by_downstream_equations
      ),
      'moving_lineage_verified': self.moving_lineage_verified,
      'moving_conservative_flux_closure_verified': (
        self.moving_conservative_flux_closure_verified
      ),
      'moving_entropy_transition_verified': (
        self.moving_entropy_transition_verified
      ),
      'moving_global_physical_field_consumed': (
        self.moving_global_physical_field_consumed
      ),
      'moving_geometry_reconciliation_verified': (
        self.moving_geometry_reconciliation_verified
      ),
      'final_trace_audit_verified': self.final_trace_audit_verified,
      'componentwise_residual_descent_verified': (
        self.componentwise_residual_descent_verified
      ),
      'require_componentwise_residual_descent': (
        self.require_componentwise_residual_descent
      ),
      'upstream_state_equation_consumed': False,
      'global_coupling_verified': False,
      'canonical_free_boundary_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'source_closure': (
        None if self.source_closure is None else self.source_closure.as_report()
      ),
      'source_downstream': (
        None
        if self.source_downstream is None
        else self.source_downstream.as_report()
      ),
      'state_step': None if self.state_step is None else self.state_step.as_report(),
      'moving_interface': (
        None
        if self.moving_interface is None
        else self.moving_interface.as_report()
      ),
      'moving_response': (
        None if self.moving_response is None else self.moving_response.as_report()
      ),
      'shock_geometry_response': (
        None
        if self.shock_geometry_response is None
        else self.shock_geometry_response.as_report()
      ),
      'geometry_closure': (
        None
        if self.geometry_closure is None
        else self.geometry_closure.as_report()
      ),
      'final_downstream': (
        None
        if self.final_downstream is None
        else self.final_downstream.as_report()
      ),
      'final_state_consumer': (
        None
        if self.final_state_consumer is None
        else self.final_state_consumer.as_report()
      ),
      'claim_status': (
        'research-only full-state moving/global composition; conservative and '
        'entropy front gates plus fresh global geometry reconciliation passed '
        'locally, but the upstream characteristic state equation, canonical '
        'free-boundary fixed point, shock-cell promotion, external validation, '
        'and production claims remain open'
      ),
      'message': self.message,
    }
  ####
####


def _failure(
  status: MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepStatus,
  message: str,
  *,
  source_closure: MocReflectedDomainGlobalPhysicalClosureResult | None = None,
  source_downstream: MocReflectedDomainGlobalCoupledDownstreamResult | None = None,
  require_componentwise_residual_descent: bool = True,
  **kwargs: Any,
) -> MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepResult:
  return MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepResult(
    status=status,
    source_closure=source_closure,
    source_downstream=source_downstream,
    require_componentwise_residual_descent=require_componentwise_residual_descent,
    message=message,
    **kwargs,
  )
####


def run_reflected_domain_global_mixed_regime_moving_state_coupled_step(
  closure: MocReflectedDomainGlobalPhysicalClosureResult,
  downstream: MocReflectedDomainGlobalCoupledDownstreamResult,
  *,
  reference_total_temperature_K: float,
  ambient_pressure_Pa: float | None = None,
  correction_fraction: float = 0.005,
  consumer_id: str = (
    'research-global-mixed-regime-moving-state-coupled-step-v1'
  ),
  require_componentwise_residual_descent: bool = True,
  state_resolve_options: Mapping[str, Any] | None = None,
  state_boundary_condition_options: Mapping[str, Any] | None = None,
  moving_interface_options: Mapping[str, Any] | None = None,
  downstream_options: Mapping[str, Any] | None = None,
  geometry_response_options: Mapping[str, Any] | None = None,
) -> MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepResult:
  """Run one state-consuming moving-front/global-geometry research step.

  The strict moving-interface controls are composed and cannot be disabled:
  the conservative residual line search, conservative flux closure, entropy
  transition, and solver-owned global physical-field consumption are all
  mandatory.  Typed handoff profiles are rejected for the final downstream
  refresh so a stale field cannot cross the updated shock-geometry frame.
  """

  if not isinstance(closure, MocReflectedDomainGlobalPhysicalClosureResult):
    return _failure(
      MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepStatus.INVALID_INPUT,
      'closure must be a MocReflectedDomainGlobalPhysicalClosureResult',
    )
  ####
  if not isinstance(downstream, MocReflectedDomainGlobalCoupledDownstreamResult):
    return _failure(
      MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepStatus.INVALID_INPUT,
      'downstream must be a MocReflectedDomainGlobalCoupledDownstreamResult',
      source_closure=closure,
    )
  ####
  if not isinstance(require_componentwise_residual_descent, bool):
    return _failure(
      MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepStatus.INVALID_INPUT,
      'require_componentwise_residual_descent must be a bool',
      source_closure=closure,
      source_downstream=downstream,
    )
  ####
  try:
    temperature = float(reference_total_temperature_K)
    supplied_ambient = (
      None if ambient_pressure_Pa is None else float(ambient_pressure_Pa)
    )
    moving_options = _options(
      moving_interface_options,
      'moving_interface_options',
      reserved=(
        'closure',
        'reference_total_temperature_K',
        'use_conservative_residual_line_search',
        'require_conservative_flux_closure',
        'require_entropy_transition',
        'consume_global_physical_field_for_downstream_probes',
      ),
    )
    downstream_options_resolved = _options(
      downstream_options,
      'downstream_options',
      reserved=(
        'closure',
        'reference_total_temperature_K',
        'ambient_pressure_Pa',
        'physical_field_continuation_profile',
        'physical_field_shock_front_condition',
        'transonic_shock_interface_field_placement',
        'boundary_pressure_profile',
        'boundary_geometry_profile',
      ),
    )
    geometry_options = _options(
      geometry_response_options,
      'geometry_response_options',
      reserved=('closure', 'shock_geometry_response'),
    )
    resolved_consumer_id = str(consumer_id)
  except (TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepStatus.INVALID_INPUT,
      f'moving/global state-step controls are invalid: {error}',
      source_closure=closure,
      source_downstream=downstream,
    )
  ####
  if not isfinite(temperature) or temperature <= 0.0:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepStatus.INVALID_INPUT,
      'reference_total_temperature_K must be finite and positive',
      source_closure=closure,
      source_downstream=downstream,
      require_componentwise_residual_descent=require_componentwise_residual_descent,
    )
  ####
  if supplied_ambient is not None and (
    not isfinite(supplied_ambient) or supplied_ambient <= 0.0
  ):
    return _failure(
      MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepStatus.INVALID_INPUT,
      'ambient_pressure_Pa must be finite and positive when supplied',
      source_closure=closure,
      source_downstream=downstream,
      require_componentwise_residual_descent=require_componentwise_residual_descent,
    )
  ####
  if not resolved_consumer_id:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepStatus.INVALID_INPUT,
      'consumer_id must be non-empty',
      source_closure=closure,
      source_downstream=downstream,
      require_componentwise_residual_descent=require_componentwise_residual_descent,
    )
  ####
  try:
    state_step = run_reflected_domain_global_mixed_regime_state_coupled_step(
      closure,
      downstream,
      correction_fraction=correction_fraction,
      consumer_id=f'{resolved_consumer_id}:state',
      require_componentwise_residual_descent=False,
      state_resolve_options=state_resolve_options,
      boundary_condition_options=state_boundary_condition_options,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepStatus.STATE_COUPLED_STEP_FAILURE,
      f'full-state coupled step raised: {error}',
      source_closure=closure,
      source_downstream=downstream,
      require_componentwise_residual_descent=require_componentwise_residual_descent,
    )
  ####
  common_state = dict(
    source_closure=closure,
    source_downstream=downstream,
    state_step=state_step,
    initial_residual_vector=_vector(downstream),
    state_target_consumed_by_downstream_equations=bool(
      state_step.state_target_consumed_by_downstream_equations
      and state_step.state_target_frame_verified
    ),
    require_componentwise_residual_descent=require_componentwise_residual_descent,
  )
  moving_closure = state_step.refreshed_closure
  if moving_closure is None or not (
    state_step.state_target_consumed_by_downstream_equations
    and state_step.refreshed_trace_audit_verified
    and state_step.global_pressure_geometry_projection_verified
    and moving_closure.converged
    and moving_closure.physical_closure_verified
  ):
    return _failure(
      MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepStatus.STATE_COUPLED_STEP_FAILURE,
      'full-state state/global step did not retain a locally verified refreshed '
      f'closure: {state_step.message}',
      **common_state,
    )
  ####
  moving_options.update({
    'use_conservative_residual_line_search': True,
    'require_conservative_flux_closure': True,
    'require_entropy_transition': True,
    'consume_global_physical_field_for_downstream_probes': True,
  })
  try:
    moving_request = MocReflectedDomainGlobalTwoSidedMovingInterfaceRequest(
      closure=moving_closure,
      reference_total_temperature_K=temperature,
      **moving_options,
    )
    moving_interface = solve_reflected_domain_global_two_sided_moving_interface(
      moving_request
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepStatus.MOVING_INTERFACE_FAILURE,
      f'strict moving-interface solve raised: {error}',
      **common_state,
    )
  ####
  moving_residual = moving_interface.conservative_residual_result
  moving_response = (
    None if moving_residual is None else moving_residual.final_response
  )
  moving_lineage_verified = bool(
    moving_interface.request is not None
    and moving_interface.request.closure is moving_closure
    and moving_interface.shock_boundary is not None
    and moving_closure.global_euler is not None
    and moving_interface.shock_boundary
    is moving_closure.global_euler.shock_boundary
    and moving_response is not None
    and moving_response.prior_shock_boundary is moving_interface.shock_boundary
  )
  moving_flux_verified = bool(
    moving_interface.converged
    and moving_residual is not None
    and moving_residual.converged
    and moving_residual.conservative_flux_closure_verified
    and moving_residual.final_response is not None
    and moving_residual.final_response.conservative_flux_closure_verified
  )
  moving_entropy_verified = bool(
    moving_flux_verified
    and moving_response is not None
    and moving_response.entropy_transition_verified
    and moving_response.entropy_transition_log_ratios is not None
  )
  moving_field_consumed = bool(
    moving_interface.converged
    and moving_interface.global_physical_field_consumed
  )
  common_moving = dict(
    **common_state,
    moving_interface=moving_interface,
    moving_response=moving_response,
    moving_lineage_verified=moving_lineage_verified,
    moving_conservative_flux_closure_verified=moving_flux_verified,
    moving_entropy_transition_verified=moving_entropy_verified,
    moving_global_physical_field_consumed=moving_field_consumed,
  )
  if not (
    moving_lineage_verified
    and moving_flux_verified
    and moving_entropy_verified
    and moving_field_consumed
  ):
    return _failure(
      MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepStatus.MOVING_INTERFACE_FAILURE,
      'strict moving-interface evidence did not pass conservative-flux, '
      'entropy-transition, and global-physical-field gates',
      **common_moving,
    )
  ####
  if moving_response is None or not moving_response.next_shock_boundary.converged:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepStatus.GEOMETRY_RESPONSE_FAILURE,
      'strict moving-interface result retained no locally verified next shock '
      'geometry response',
      **common_moving,
    )
  ####
  shock_geometry_response = moving_response.next_shock_boundary
  try:
    geometry_closure = consume_reflected_domain_global_shock_geometry_response(
      moving_closure,
      shock_geometry_response,
      **geometry_options,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepStatus.GEOMETRY_RESPONSE_FAILURE,
      f'fresh shock-geometry response consumer raised: {error}',
      shock_geometry_response=shock_geometry_response,
      **common_moving,
    )
  ####
  geometry_verified = bool(
    geometry_closure is not moving_closure
    and geometry_closure.converged
    and geometry_closure.physical_closure_verified
    and geometry_closure.global_euler is not None
    and geometry_closure.global_euler.shock_boundary is not shock_geometry_response
    and geometry_closure.source_band is moving_closure.source_band
  )
  common_geometry = dict(
    **common_moving,
    shock_geometry_response=shock_geometry_response,
    geometry_closure=geometry_closure,
    moving_geometry_reconciliation_verified=geometry_verified,
  )
  if not geometry_verified:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepStatus.GLOBAL_RECONCILIATION_FAILURE,
      'fresh global shock-geometry reconciliation did not retain a locally '
      'verified closure with the exact source-band lineage',
      **common_geometry,
    )
  ####
  resolved_ambient = _ambient_pressure(closure, downstream, supplied_ambient)
  if resolved_ambient is None or not isfinite(resolved_ambient) or resolved_ambient <= 0.0:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepStatus.INVALID_INPUT,
      'no finite positive ambient pressure was available for the fresh '
      'post-geometry downstream solve',
      **common_geometry,
    )
  ####
  try:
    final_downstream = solve_reflected_domain_global_coupled_downstream(
      geometry_closure,
      reference_total_temperature_K=temperature,
      ambient_pressure_Pa=resolved_ambient,
      **downstream_options_resolved,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepStatus.DOWNSTREAM_REFRESH_FAILURE,
      f'fresh post-geometry downstream solve raised: {error}',
      **common_geometry,
    )
  ####
  final_fingerprint = moc_reflected_domain_global_physical_closure_fingerprint(
    geometry_closure
  )
  final_downstream_verified = bool(
    final_downstream.converged
    and final_downstream.closure_lineage_verified
    and final_downstream.source_closure_fingerprint == final_fingerprint
    and final_downstream.closure is geometry_closure
  )
  common_downstream = dict(
    **common_geometry,
    final_downstream=final_downstream,
    final_residual_vector=_vector(final_downstream),
  )
  if not final_downstream_verified:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepStatus.DOWNSTREAM_REFRESH_FAILURE,
      'post-geometry downstream solve did not retain exact fresh closure '
      f'lineage: {final_downstream.message}',
      **common_downstream,
    )
  ####
  try:
    final_state_consumer = consume_reflected_domain_global_mixed_regime_state(
      geometry_closure,
      final_downstream,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepStatus.FINAL_STATE_AUDIT_FAILURE,
      f'final downstream state audit raised: {error}',
      **common_downstream,
    )
  ####
  final_trace_verified = bool(
    final_state_consumer.consumed_local_research_state
    and final_state_consumer.closure_lineage_verified
    and final_state_consumer.downstream is final_downstream
    and final_state_consumer.trace is final_downstream.downstream_boundary_trace
  )
  common_final = dict(
    **common_downstream,
    final_state_consumer=final_state_consumer,
    final_trace_audit_verified=final_trace_verified,
  )
  if not final_trace_verified:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepStatus.FINAL_STATE_AUDIT_FAILURE,
      'fresh post-geometry downstream trace did not pass its independent '
      'full-state replay audit',
      **common_final,
    )
  ####
  initial_vector = _vector(downstream)
  final_vector = _vector(final_downstream)
  descent_verified = _componentwise_descent(initial_vector, final_vector)
  common_complete = dict(
    **common_final,
    componentwise_residual_descent_verified=descent_verified,
  )
  if require_componentwise_residual_descent and not descent_verified:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepStatus.RESIDUAL_DESCENT_FAILURE,
      'moving/global evidence completed, but at least one normalized '
      'coupled-state residual component did not descend; scalar-only evidence '
      'was not accepted',
      **common_complete,
    )
  ####
  status = (
    MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepStatus
    .CONVERGED_RESEARCH_MOVING_GLOBAL_STATE_STEP
    if descent_verified
    else (
      MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepStatus
      .COMPLETED_RESEARCH_MOVING_GLOBAL_STATE_STEP_WITH_OPEN_RESIDUAL
    )
  )
  return MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepResult(
    status=status,
    message=(
      'full-state downstream equations consumed the conservative/entropy '
      'target; the strict moving solver closed its conservative and entropy '
      'front response using the global physical field; the solver-owned shock '
      'geometry was independently reconciled into a fresh global closure; and '
      'a fresh downstream trace passed its independent audit'
      if descent_verified
      else (
        'state, strict moving-front, global geometry, and final trace evidence '
        'completed, but the component-wise residual gate remains open; no '
        'scalar-only descent or production claim was accepted'
      )
    ),
    **common_complete,
  )
####
