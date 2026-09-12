"""One fail-closed outer state-coupled step for the reflected MOC lane.

The repository has separate, audited pieces for a global reflected closure,
the downstream conservative trace, the entropy-compatible free-boundary law,
and the pressure/geometry global response consumer.  This module composes
those pieces into one explicit research step:

``global closure -> full downstream trace -> live conservative/entropy
re-solve -> independent trace replay -> fresh global response solve``.

The complete state target is genuinely consumed by the downstream finite-
volume equations and its produced trace is independently remeasured before
the global response is used.  The current characteristic MOC solver still
does not accept conservative state or entropy equations directly, so the
result never claims an upstream state-equation fixed point, canonical global
coupling, or production validity.  An open component of the normalized
residual vector is retained as a typed result rather than being hidden by a
scalar norm.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import Enum
from math import isfinite
from typing import Any

from exhaust_plume.models.moc.global_coupled_downstream import (
  MocReflectedDomainGlobalCoupledDownstreamResult,
  MocReflectedDomainGlobalCoupledDownstreamStatus,
  build_reflected_domain_global_coupled_downstream_boundary_trace,
  measure_reflected_domain_global_coupled_downstream_boundary_response,
)
from exhaust_plume.models.moc.global_mixed_regime_state_consumer import (
  MocReflectedDomainGlobalMixedRegimeStateConsumerResult,
  MocReflectedDomainGlobalMixedRegimeStateResolveResult,
  consume_reflected_domain_global_mixed_regime_state,
  solve_reflected_domain_global_mixed_regime_state_consumer,
)
from exhaust_plume.models.moc.global_physical_closure import (
  MocReflectedDomainGlobalPhysicalClosureResult,
  moc_reflected_domain_global_physical_closure_fingerprint,
)
from exhaust_plume.validation.moc_global_mixed_regime_state_feedback import (
  MocReflectedDomainGlobalMixedRegimeStateFeedbackRun,
  measure_reflected_domain_global_mixed_regime_state_feedback,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_STATE_COUPLED_STEP_OPERATOR_ID',
  'MocReflectedDomainGlobalMixedRegimeStateCoupledStepStatus',
  'MocReflectedDomainGlobalMixedRegimeStateCoupledStepResult',
  'run_reflected_domain_global_mixed_regime_state_coupled_step',
)


MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_STATE_COUPLED_STEP_OPERATOR_ID = (
  'op.moc.reflected-domain.global-mixed-regime-state-coupled-step-v1'
)


class MocReflectedDomainGlobalMixedRegimeStateCoupledStepStatus(str, Enum):
  """Typed outcomes of one state-consuming outer research step."""

  CONVERGED_RESEARCH_STATE_COUPLED_STEP = (
    'converged-research-global-mixed-regime-state-coupled-step'
  )
  COMPLETED_RESEARCH_STATE_COUPLED_STEP_WITH_OPEN_RESIDUAL = (
    'completed-research-global-mixed-regime-state-coupled-step-with-open-residual'
  )
  INVALID_INPUT = 'invalid_input'
  STATE_CONSUMER_FAILURE = (
    'global-mixed-regime-state-coupled-step-state-consumer-failure'
  )
  STATE_RESOLVE_FAILURE = (
    'global-mixed-regime-state-coupled-step-state-resolve-failure'
  )
  TRACE_REBIND_FAILURE = (
    'global-mixed-regime-state-coupled-step-trace-rebind-failure'
  )
  FRESH_TRACE_AUDIT_FAILURE = (
    'global-mixed-regime-state-coupled-step-fresh-trace-audit-failure'
  )
  GLOBAL_FEEDBACK_FAILURE = (
    'global-mixed-regime-state-coupled-step-global-feedback-failure'
  )
  RESIDUAL_DESCENT_FAILURE = (
    'global-mixed-regime-state-coupled-step-residual-descent-failure'
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
      f'{name} cannot override positional controls: {", ".join(collisions)}'
    )
  ####
  return resolved
####


def _componentwise_descent(
  before: tuple[float, ...],
  after: tuple[float, ...],
) -> bool:
  """Require equal-width residual vectors with no worsening component."""

  if not before or len(before) != len(after):
    return False
  ####
  if any(
    not isfinite(value) or value < 0.0
    for value in (*before, *after)
  ):
    return False
  ####
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


def _rebind_downstream_result(
  source: MocReflectedDomainGlobalCoupledDownstreamResult,
  state_resolve: MocReflectedDomainGlobalMixedRegimeStateResolveResult,
) -> tuple[MocReflectedDomainGlobalCoupledDownstreamResult | None, str]:
  """Attach a fresh state-resolved field to the exact downstream envelope."""

  field = state_resolve.field
  request = state_resolve.request
  if (
    not state_resolve.fresh_local_research_state_resolve_verified
    or field is None
    or request is None
    or state_resolve.field_audit is None
  ):
    return None, (
      'state resolve did not retain a locally verified field, request, and '
      'independent audit for downstream rebinding'
    )
  ####
  closure = source.closure
  if closure is None:
    return None, 'source downstream result retained no global closure'
  ####
  response = measure_reflected_domain_global_coupled_downstream_boundary_response(
    closure,
    field,
  )
  if not response.overlap_coverage_verified:
    return None, (
      'state-resolved downstream field did not retain coverage of the exact '
      f'global boundary: {response.message}'
    )
  ####
  candidate = replace(
    source,
    status=MocReflectedDomainGlobalCoupledDownstreamStatus
    .CONVERGED_LOCAL_COUPLED_FIELD,
    coupled_request=request,
    coupled_field=field,
    coupled_field_audit=state_resolve.field_audit,
    downstream_boundary_response=response,
    downstream_boundary_trace=None,
    # The state-resolve request owns the exact state/geometry profile.  The
    # optional wrapper profiles from the predecessor may refer to a different
    # request frame, so they are not copied across the rebind.
    boundary_pressure_profile=None,
    boundary_geometry_profile=None,
    message=(
      'fresh entropy-compatible full-state field rebound to the exact global '
      'downstream result frame; overlap response retained as research evidence'
    ),
  )
  trace = build_reflected_domain_global_coupled_downstream_boundary_trace(
    candidate
  )
  if not trace.local_trace_verified:
    return None, (
      'state-resolved downstream field could not produce an independently '
      f'verified full-state trace: {trace.message}'
    )
  ####
  candidate = replace(candidate, downstream_boundary_trace=trace)
  if not candidate.converged:
    return None, (
      'state-resolved downstream result failed its exact closure lineage '
      'after rebinding'
    )
  ####
  return candidate, response.message
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeStateCoupledStepResult:
  """Evidence from one full-state downstream/global research step."""

  status: MocReflectedDomainGlobalMixedRegimeStateCoupledStepStatus
  source_closure: MocReflectedDomainGlobalPhysicalClosureResult | None
  source_downstream: MocReflectedDomainGlobalCoupledDownstreamResult | None
  state_consumer: MocReflectedDomainGlobalMixedRegimeStateConsumerResult | None = None
  state_resolve: MocReflectedDomainGlobalMixedRegimeStateResolveResult | None = None
  refreshed_state_consumer: (
    MocReflectedDomainGlobalMixedRegimeStateConsumerResult | None
  ) = None
  refreshed_downstream: MocReflectedDomainGlobalCoupledDownstreamResult | None = None
  global_feedback: MocReflectedDomainGlobalMixedRegimeStateFeedbackRun | None = None
  refreshed_closure: MocReflectedDomainGlobalPhysicalClosureResult | None = None
  initial_residual_vector: tuple[float, ...] = ()
  refreshed_residual_vector: tuple[float, ...] = ()
  state_target_frame_verified: bool = False
  state_target_consumed_by_downstream_equations: bool = False
  refreshed_trace_audit_verified: bool = False
  global_pressure_geometry_projection_verified: bool = False
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
      MocReflectedDomainGlobalMixedRegimeStateCoupledStepStatus,
    ):
      raise TypeError('status must be a typed state-coupled-step status')
    ####
    for name, expected in (
      ('source_closure', MocReflectedDomainGlobalPhysicalClosureResult),
      ('source_downstream', MocReflectedDomainGlobalCoupledDownstreamResult),
      (
        'state_consumer',
        MocReflectedDomainGlobalMixedRegimeStateConsumerResult,
      ),
      (
        'state_resolve',
        MocReflectedDomainGlobalMixedRegimeStateResolveResult,
      ),
      (
        'refreshed_state_consumer',
        MocReflectedDomainGlobalMixedRegimeStateConsumerResult,
      ),
      (
        'refreshed_downstream',
        MocReflectedDomainGlobalCoupledDownstreamResult,
      ),
      ('global_feedback', MocReflectedDomainGlobalMixedRegimeStateFeedbackRun),
      ('refreshed_closure', MocReflectedDomainGlobalPhysicalClosureResult),
    ):
      value = getattr(self, name)
      if value is not None and not isinstance(value, expected):
        raise TypeError(f'{name} must retain its typed research result')
      ####
    ####
    for name in ('initial_residual_vector', 'refreshed_residual_vector'):
      values = tuple(float(value) for value in getattr(self, name))
      if any(not isfinite(value) or value < 0.0 for value in values):
        raise ValueError(f'{name} must contain finite nonnegative values')
      ####
      object.__setattr__(self, name, values)
    ####
    for name in (
      'state_target_frame_verified',
      'state_target_consumed_by_downstream_equations',
      'refreshed_trace_audit_verified',
      'global_pressure_geometry_projection_verified',
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
        'state-coupled research step cannot claim upstream global coupling'
      )
    ####
    if self.canonical_free_boundary_verified:
      raise ValueError(
        'state-coupled research step cannot claim canonical free-boundary closure'
      )
    ####
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError('state-coupled research step must remain promotion-blocked')
    ####
    if self.status is (
      MocReflectedDomainGlobalMixedRegimeStateCoupledStepStatus
      .CONVERGED_RESEARCH_STATE_COUPLED_STEP
    ) and not (
      self.state_target_frame_verified
      and self.state_target_consumed_by_downstream_equations
      and self.refreshed_trace_audit_verified
      and self.global_pressure_geometry_projection_verified
      and self.componentwise_residual_descent_verified
    ):
      raise ValueError(
        'converged state-coupled step must pass state, trace, global, and '
        'component-wise descent gates'
      )
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def research_state_coupled_step_verified(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalMixedRegimeStateCoupledStepStatus
      .CONVERGED_RESEARCH_STATE_COUPLED_STEP
      and self.state_target_frame_verified
      and self.state_target_consumed_by_downstream_equations
      and self.refreshed_trace_audit_verified
      and self.global_pressure_geometry_projection_verified
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
        MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_STATE_COUPLED_STEP_OPERATOR_ID
      ),
      'status': self.status.value,
      'research_state_coupled_step_verified': (
        self.research_state_coupled_step_verified
      ),
      'source_closure_fingerprint': self.source_closure_fingerprint,
      'initial_residual_vector': self.initial_residual_vector,
      'refreshed_residual_vector': self.refreshed_residual_vector,
      'state_target_frame_verified': self.state_target_frame_verified,
      'state_target_consumed_by_downstream_equations': (
        self.state_target_consumed_by_downstream_equations
      ),
      'refreshed_trace_audit_verified': self.refreshed_trace_audit_verified,
      'global_pressure_geometry_projection_verified': (
        self.global_pressure_geometry_projection_verified
      ),
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
      'state_consumer': (
        None if self.state_consumer is None else self.state_consumer.as_report()
      ),
      'state_resolve': (
        None if self.state_resolve is None else self.state_resolve.as_report()
      ),
      'refreshed_state_consumer': (
        None
        if self.refreshed_state_consumer is None
        else self.refreshed_state_consumer.as_report()
      ),
      'refreshed_downstream': (
        None
        if self.refreshed_downstream is None
        else self.refreshed_downstream.as_report()
      ),
      'global_feedback': (
        None if self.global_feedback is None else self.global_feedback.as_report()
      ),
      'refreshed_closure': (
        None
        if self.refreshed_closure is None
        else self.refreshed_closure.as_report()
      ),
      'claim_status': (
        'research-only-state-coupled-downstream-to-global-response-step; the '
        'conservative and entropy target was consumed by downstream equations '
        'but the upstream characteristic state equation, canonical fixed point, '
        'shock-cell promotion, external validation, and production claims '
        'remain open'
      ),
      'message': self.message,
    }
  ####
####


def _failure(
  status: MocReflectedDomainGlobalMixedRegimeStateCoupledStepStatus,
  message: str,
  *,
  source_closure: MocReflectedDomainGlobalPhysicalClosureResult | None = None,
  source_downstream: MocReflectedDomainGlobalCoupledDownstreamResult | None = None,
  require_componentwise_residual_descent: bool = True,
  **kwargs: Any,
) -> MocReflectedDomainGlobalMixedRegimeStateCoupledStepResult:
  return MocReflectedDomainGlobalMixedRegimeStateCoupledStepResult(
    status=status,
    source_closure=source_closure,
    source_downstream=source_downstream,
    require_componentwise_residual_descent=require_componentwise_residual_descent,
    message=message,
    **kwargs,
  )
####


def run_reflected_domain_global_mixed_regime_state_coupled_step(
  closure: MocReflectedDomainGlobalPhysicalClosureResult,
  downstream: MocReflectedDomainGlobalCoupledDownstreamResult,
  *,
  correction_fraction: float = 0.005,
  consumer_id: str = 'research-global-mixed-regime-state-coupled-step-v1',
  require_componentwise_residual_descent: bool = True,
  state_resolve_options: Mapping[str, Any] | None = None,
  boundary_condition_options: Mapping[str, Any] | None = None,
) -> MocReflectedDomainGlobalMixedRegimeStateCoupledStepResult:
  """Consume one full state target, then route its response to a fresh global solve.

  The entropy-compatible live trace law is mandatory for this operator.  The
  global part intentionally remains the existing pressure/geometry response
  consumer; the result makes that limitation explicit instead of claiming
  that the characteristic upstream equations consumed the state vector.
  """

  if not isinstance(closure, MocReflectedDomainGlobalPhysicalClosureResult):
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateCoupledStepStatus.INVALID_INPUT,
      'closure must be a MocReflectedDomainGlobalPhysicalClosureResult',
    )
  ####
  if not isinstance(downstream, MocReflectedDomainGlobalCoupledDownstreamResult):
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateCoupledStepStatus.INVALID_INPUT,
      'downstream must be a MocReflectedDomainGlobalCoupledDownstreamResult',
      source_closure=closure,
    )
  ####
  if not isinstance(require_componentwise_residual_descent, bool):
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateCoupledStepStatus.INVALID_INPUT,
      'require_componentwise_residual_descent must be a bool',
      source_closure=closure,
      source_downstream=downstream,
    )
  ####
  try:
    fraction = float(correction_fraction)
    resolved_consumer_id = str(consumer_id)
    state_options = _options(
      state_resolve_options,
      'state_resolve_options',
      reserved=('consumer',),
    )
    _options(
      boundary_condition_options,
      'boundary_condition_options',
      reserved=('request', 'source_closure', 'base_target'),
    )
  except (TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateCoupledStepStatus.INVALID_INPUT,
      f'state-coupled-step controls are invalid: {error}',
      source_closure=closure,
      source_downstream=downstream,
    )
  ####
  if (
    not resolved_consumer_id
    or not isfinite(fraction)
    or fraction <= 0.0
    or fraction > 1.0
  ):
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateCoupledStepStatus.INVALID_INPUT,
      'consumer_id must be non-empty and correction_fraction must be in (0, 1]',
      source_closure=closure,
      source_downstream=downstream,
      require_componentwise_residual_descent=require_componentwise_residual_descent,
    )
  ####
  fingerprint = moc_reflected_domain_global_physical_closure_fingerprint(closure)
  if not closure.converged or not closure.physical_closure_verified:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateCoupledStepStatus.INVALID_INPUT,
      'state-coupled step requires a locally verified global physical closure',
      source_closure=closure,
      source_downstream=downstream,
      require_componentwise_residual_descent=require_componentwise_residual_descent,
    )
  ####
  if not (
    downstream.converged
    and downstream.source_closure_fingerprint == fingerprint
    and downstream.closure_lineage_verified
  ):
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateCoupledStepStatus.STATE_CONSUMER_FAILURE,
      'state-coupled step requires a locally verified downstream result with '
      'the exact closure lineage',
      source_closure=closure,
      source_downstream=downstream,
      require_componentwise_residual_descent=require_componentwise_residual_descent,
    )
  ####
  if state_options.get('apply_entropy_compatible_flux', True) is not True:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateCoupledStepStatus.INVALID_INPUT,
      'state-coupled step requires apply_entropy_compatible_flux=True',
      source_closure=closure,
      source_downstream=downstream,
      require_componentwise_residual_descent=require_componentwise_residual_descent,
    )
  ####
  state_options['apply_entropy_compatible_flux'] = True
  try:
    state_consumer = consume_reflected_domain_global_mixed_regime_state(
      closure,
      downstream,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateCoupledStepStatus.STATE_CONSUMER_FAILURE,
      f'full-state consumer raised: {error}',
      source_closure=closure,
      source_downstream=downstream,
      require_componentwise_residual_descent=require_componentwise_residual_descent,
    )
  ####
  if not state_consumer.consumed_local_research_state:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateCoupledStepStatus.STATE_CONSUMER_FAILURE,
      'full-state consumer did not pass its exact mass, momentum, energy, '
      'entropy, ambient, and centerline gates',
      source_closure=closure,
      source_downstream=downstream,
      state_consumer=state_consumer,
      require_componentwise_residual_descent=require_componentwise_residual_descent,
    )
  ####
  try:
    state_resolve = solve_reflected_domain_global_mixed_regime_state_consumer(
      state_consumer,
      **state_options,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateCoupledStepStatus.STATE_RESOLVE_FAILURE,
      f'full-state entropy-compatible resolve raised: {error}',
      source_closure=closure,
      source_downstream=downstream,
      state_consumer=state_consumer,
      require_componentwise_residual_descent=require_componentwise_residual_descent,
    )
  ####
  state_target_frame_verified = bool(
    state_resolve.consumer_lineage_verified
    and state_resolve.profile_frame_verified
    and state_resolve.conservative_state_profile
    and state_resolve.conservative_state_profile_points_m
    and len(state_resolve.conservative_state_profile)
    == len(state_resolve.entropy_proxy_profile)
  )
  state_target_consumed = bool(
    state_resolve.fresh_local_research_state_resolve_verified
    and state_target_frame_verified
    and state_resolve.request is not None
    and state_resolve.field is not None
    and state_resolve.field.free_boundary_conservative_state_profile_consumed
    and state_resolve.request.free_boundary_conservative_state_profile_source
    is not None
    and state_resolve.request.free_boundary_flux_mode.value
    == 'conservative-state-trace-entropy-compatible-rusanov-v1'
  )
  if not state_target_consumed:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateCoupledStepStatus.STATE_RESOLVE_FAILURE,
      'fresh state solve did not consume the exact conservative/entropy target '
      'with the live entropy-compatible boundary law',
      source_closure=closure,
      source_downstream=downstream,
      state_consumer=state_consumer,
      state_resolve=state_resolve,
      initial_residual_vector=_vector(downstream),
      state_target_frame_verified=state_target_frame_verified,
      require_componentwise_residual_descent=require_componentwise_residual_descent,
    )
  ####
  refreshed_downstream, rebind_message = _rebind_downstream_result(
    downstream,
    state_resolve,
  )
  if refreshed_downstream is None:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateCoupledStepStatus.TRACE_REBIND_FAILURE,
      rebind_message,
      source_closure=closure,
      source_downstream=downstream,
      state_consumer=state_consumer,
      state_resolve=state_resolve,
      initial_residual_vector=_vector(downstream),
      state_target_frame_verified=state_target_frame_verified,
      state_target_consumed_by_downstream_equations=state_target_consumed,
      require_componentwise_residual_descent=require_componentwise_residual_descent,
    )
  ####
  try:
    refreshed_state_consumer = consume_reflected_domain_global_mixed_regime_state(
      closure,
      refreshed_downstream,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateCoupledStepStatus.FRESH_TRACE_AUDIT_FAILURE,
      f'fresh produced-trace consumer raised: {error}',
      source_closure=closure,
      source_downstream=downstream,
      state_consumer=state_consumer,
      state_resolve=state_resolve,
      refreshed_downstream=refreshed_downstream,
      initial_residual_vector=_vector(downstream),
      refreshed_residual_vector=_vector(refreshed_downstream),
      state_target_frame_verified=state_target_frame_verified,
      state_target_consumed_by_downstream_equations=state_target_consumed,
      require_componentwise_residual_descent=require_componentwise_residual_descent,
    )
  ####
  refreshed_trace_verified = bool(
    refreshed_state_consumer.consumed_local_research_state
    and refreshed_state_consumer.closure_lineage_verified
    and refreshed_state_consumer.downstream is refreshed_downstream
  )
  if not refreshed_trace_verified:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateCoupledStepStatus.FRESH_TRACE_AUDIT_FAILURE,
      'fresh entropy-compatible downstream trace did not pass its independent '
      'full-state replay audit',
      source_closure=closure,
      source_downstream=downstream,
      state_consumer=state_consumer,
      state_resolve=state_resolve,
      refreshed_state_consumer=refreshed_state_consumer,
      refreshed_downstream=refreshed_downstream,
      initial_residual_vector=_vector(downstream),
      refreshed_residual_vector=_vector(refreshed_downstream),
      state_target_frame_verified=state_target_frame_verified,
      state_target_consumed_by_downstream_equations=state_target_consumed,
      require_componentwise_residual_descent=require_componentwise_residual_descent,
    )
  ####
  initial_vector = _vector(downstream)
  refreshed_vector = _vector(refreshed_downstream)
  componentwise_descent = _componentwise_descent(
    initial_vector,
    refreshed_vector,
  )
  try:
    global_feedback = measure_reflected_domain_global_mixed_regime_state_feedback(
      closure,
      refreshed_downstream,
      consumer=refreshed_state_consumer,
      correction_fraction=fraction,
      consumer_id=resolved_consumer_id,
      boundary_condition_options=boundary_condition_options,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateCoupledStepStatus.GLOBAL_FEEDBACK_FAILURE,
      f'fresh global response solve raised: {error}',
      source_closure=closure,
      source_downstream=downstream,
      state_consumer=state_consumer,
      state_resolve=state_resolve,
      refreshed_state_consumer=refreshed_state_consumer,
      refreshed_downstream=refreshed_downstream,
      initial_residual_vector=initial_vector,
      refreshed_residual_vector=refreshed_vector,
      state_target_frame_verified=state_target_frame_verified,
      state_target_consumed_by_downstream_equations=state_target_consumed,
      refreshed_trace_audit_verified=refreshed_trace_verified,
      componentwise_residual_descent_verified=componentwise_descent,
      require_componentwise_residual_descent=require_componentwise_residual_descent,
    )
  ####
  global_projection_verified = bool(
    global_feedback.research_feedback_completed
    and global_feedback.boundary_condition is not None
    and global_feedback.boundary_condition.conditioned_closure is not None
    and global_feedback.fidelity_isolation_verified
  )
  refreshed_closure = (
    None
    if global_feedback.boundary_condition is None
    else global_feedback.boundary_condition.conditioned_closure
  )
  common = dict(
    source_closure=closure,
    source_downstream=downstream,
    state_consumer=state_consumer,
    state_resolve=state_resolve,
    refreshed_state_consumer=refreshed_state_consumer,
    refreshed_downstream=refreshed_downstream,
    global_feedback=global_feedback,
    refreshed_closure=refreshed_closure,
    initial_residual_vector=initial_vector,
    refreshed_residual_vector=refreshed_vector,
    state_target_frame_verified=state_target_frame_verified,
    state_target_consumed_by_downstream_equations=state_target_consumed,
    refreshed_trace_audit_verified=refreshed_trace_verified,
    global_pressure_geometry_projection_verified=global_projection_verified,
    componentwise_residual_descent_verified=componentwise_descent,
    require_componentwise_residual_descent=require_componentwise_residual_descent,
  )
  if not global_projection_verified:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateCoupledStepStatus.GLOBAL_FEEDBACK_FAILURE,
      'state target and produced trace were consumed, but the fresh global '
      f'pressure/geometry response solve did not complete: {global_feedback.message}',
      **common,
    )
  ####
  if require_componentwise_residual_descent and not componentwise_descent:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateCoupledStepStatus.RESIDUAL_DESCENT_FAILURE,
      'fresh state consumption and global response completed, but at least one '
      'normalized coupled-state residual component did not descend; scalar '
      'maximum-norm evidence was not accepted',
      **common,
    )
  ####
  status = (
    MocReflectedDomainGlobalMixedRegimeStateCoupledStepStatus
    .CONVERGED_RESEARCH_STATE_COUPLED_STEP
    if componentwise_descent
    else (
      MocReflectedDomainGlobalMixedRegimeStateCoupledStepStatus
      .COMPLETED_RESEARCH_STATE_COUPLED_STEP_WITH_OPEN_RESIDUAL
    )
  )
  return MocReflectedDomainGlobalMixedRegimeStateCoupledStepResult(
    status=status,
    message=(
      'complete conservative and entropy target was consumed by a fresh '
      'downstream finite-volume free-boundary solve, its produced trace was '
      'independently replayed, and its response was routed to a fresh global '
      'pressure/geometry solve; upstream characteristic state equations and '
      'canonical coupling remain unavailable'
      if componentwise_descent
      else (
        'downstream state/entropy consumption and fresh global response solve '
        'completed, but the component-wise residual gate remains open; no '
        'scalar-only descent or production claim was accepted'
      )
    ),
    **common,
  )
####
