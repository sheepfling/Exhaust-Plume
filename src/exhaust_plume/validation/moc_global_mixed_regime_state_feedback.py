"""Research-only feedback from a full downstream state trace.

This operator is the first outer feedback seam for the full mixed-regime
state packet.  It requires the downstream conservative trace to pass its
independent replay audit, packages the exact pressure/geometry response, and
consumes that projection in a fresh global physical closure solve.

The conservative mass, momentum, energy, and entropy channels are retained
and reported as audit evidence only.  The current global closure equations do
not accept those channels as conservative source or boundary equations, so
this module never claims a globally coupled fixed point or production
validity.  A deliberately small 0.5% outer correction is the default because
larger relaxed projections can leave the current global march outside its
local physical closure envelope.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Any

from exhaust_plume.models.moc.global_coupled_downstream import (
  MocReflectedDomainGlobalCoupledDownstreamResult,
  MocReflectedDomainGlobalCoupledDownstreamUpstreamFeedbackProposal,
  build_reflected_domain_global_coupled_downstream_upstream_feedback_proposal,
  solve_reflected_domain_global_coupled_downstream,
)
from exhaust_plume.models.moc.global_frontier_reconciliation import (
  MocReflectedDomainGlobalFrontierReconciliationRequest,
  build_reflected_domain_global_frontier_reconciliation_request,
)
from exhaust_plume.models.moc.global_mixed_regime_state_consumer import (
  MocReflectedDomainGlobalMixedRegimeStateConsumerResult,
  consume_reflected_domain_global_mixed_regime_state,
)
from exhaust_plume.models.moc.global_physical_closure import (
  MocReflectedDomainGlobalPhysicalClosureResult,
  moc_reflected_domain_global_physical_closure_fingerprint,
)
from exhaust_plume.models.moc.physical_field_euler_reconciliation import (
  MocPhysicalFieldEulerBoundaryPressureTarget,
)
from exhaust_plume.validation.moc_global_frontier_boundary_condition import (
  MocReflectedDomainGlobalFrontierBoundaryConditionResult,
  MocReflectedDomainGlobalFrontierBoundaryConditionStatus,
  run_reflected_domain_global_frontier_boundary_conditioned_resolve,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_STATE_FEEDBACK_OPERATOR_ID',
  'MocReflectedDomainGlobalMixedRegimeStateFeedbackStatus',
  'MocReflectedDomainGlobalMixedRegimeStateFeedbackRun',
  'measure_reflected_domain_global_mixed_regime_state_feedback',
  'run_reflected_domain_global_mixed_regime_state_feedback',
)


MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_STATE_FEEDBACK_OPERATOR_ID = (
  'op.moc.reflected-domain.global-mixed-regime-state-feedback-v1'
)
_DEFAULT_OUTER_CORRECTION_FRACTION = 0.005


class MocReflectedDomainGlobalMixedRegimeStateFeedbackStatus(str, Enum):
  """Typed outcomes of one full-state/global feedback attempt."""

  COMPLETED_RESEARCH_PRESSURE_GEOMETRY_FEEDBACK = (
    'completed-research-global-mixed-regime-state-pressure-geometry-feedback'
  )
  INVALID_INPUT = 'invalid_input'
  DOWNSTREAM_FAILURE = 'global-mixed-regime-state-feedback-downstream-failure'
  STATE_CONSUMER_FAILURE = (
    'global-mixed-regime-state-feedback-state-consumer-failure'
  )
  PROPOSAL_FAILURE = 'global-mixed-regime-state-feedback-proposal-failure'
  FRONTIER_REQUEST_FAILURE = (
    'global-mixed-regime-state-feedback-frontier-request-failure'
  )
  BASE_TARGET_FAILURE = (
    'global-mixed-regime-state-feedback-base-target-failure'
  )
  GLOBAL_RESOLVE_FAILURE = (
    'global-mixed-regime-state-feedback-global-resolve-failure'
  )
  PRESSURE_GEOMETRY_CONSUMPTION_FAILURE = (
    'global-mixed-regime-state-feedback-pressure-geometry-consumption-failure'
  )
  FIDELITY_FAILURE = 'global-mixed-regime-state-feedback-fidelity-failure'


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


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeStateFeedbackRun:
  """Evidence from one conservative-trace feedback projection.

  ``boundary_condition`` contains the fresh global closure generated from the
  pressure/geometry projection.  The full conservative trace remains beside
  it, rather than being silently represented as a pressure target.
  """

  status: MocReflectedDomainGlobalMixedRegimeStateFeedbackStatus
  closure: MocReflectedDomainGlobalPhysicalClosureResult | None
  downstream: MocReflectedDomainGlobalCoupledDownstreamResult | None
  consumer: MocReflectedDomainGlobalMixedRegimeStateConsumerResult | None
  proposal: MocReflectedDomainGlobalCoupledDownstreamUpstreamFeedbackProposal | None = None
  frontier_request: MocReflectedDomainGlobalFrontierReconciliationRequest | None = None
  base_target: MocPhysicalFieldEulerBoundaryPressureTarget | None = None
  boundary_condition: MocReflectedDomainGlobalFrontierBoundaryConditionResult | None = None
  consumer_id: str = ''
  correction_fraction: float = _DEFAULT_OUTER_CORRECTION_FRACTION
  full_state_lineage_verified: bool = False
  full_state_channels_audit_verified: bool = False
  pressure_geometry_projection_requested: bool = False
  pressure_geometry_projection_consumed_verified: bool = False
  fresh_global_resolve_verified: bool = False
  fidelity_isolation_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalMixedRegimeStateFeedbackStatus,
    ):
      raise TypeError('status must be a typed mixed-regime feedback status')
    for name, expected in (
      ('closure', MocReflectedDomainGlobalPhysicalClosureResult),
      ('downstream', MocReflectedDomainGlobalCoupledDownstreamResult),
      (
        'consumer',
        MocReflectedDomainGlobalMixedRegimeStateConsumerResult,
      ),
      (
        'proposal',
        MocReflectedDomainGlobalCoupledDownstreamUpstreamFeedbackProposal,
      ),
      (
        'frontier_request',
        MocReflectedDomainGlobalFrontierReconciliationRequest,
      ),
      ('base_target', MocPhysicalFieldEulerBoundaryPressureTarget),
      (
        'boundary_condition',
        MocReflectedDomainGlobalFrontierBoundaryConditionResult,
      ),
    ):
      value = getattr(self, name)
      if value is not None and not isinstance(value, expected):
        raise TypeError(f'{name} must retain its typed research result')
    ####
    consumer_id = str(self.consumer_id)
    if not consumer_id and self.status is not (
      MocReflectedDomainGlobalMixedRegimeStateFeedbackStatus.INVALID_INPUT
    ):
      raise ValueError('consumer_id must be non-empty for a feedback result')
    ####
    correction_fraction = float(self.correction_fraction)
    if (
      not isfinite(correction_fraction)
      or correction_fraction <= 0.0
      or correction_fraction > 1.0
    ):
      raise ValueError('correction_fraction must be finite and in (0, 1]')
    ####
    for name in (
      'full_state_lineage_verified',
      'full_state_channels_audit_verified',
      'pressure_geometry_projection_requested',
      'pressure_geometry_projection_consumed_verified',
      'fresh_global_resolve_verified',
      'fidelity_isolation_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    ####
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError('mixed-regime state feedback must remain promotion-blocked')
    ####
    if self.pressure_geometry_projection_consumed_verified and (
      self.boundary_condition is None
    ):
      raise ValueError(
        'consumed pressure/geometry projection requires a boundary result'
      )
    ####
    object.__setattr__(self, 'consumer_id', consumer_id)
    object.__setattr__(self, 'correction_fraction', correction_fraction)
    object.__setattr__(self, 'message', str(self.message))

  @property
  def source_closure_fingerprint(self) -> str | None:
    if self.closure is None:
      return None
    return moc_reflected_domain_global_physical_closure_fingerprint(
      self.closure
    )

  @property
  def full_state_consumer_ready(self) -> bool:
    return bool(
      self.consumer is not None
      and self.consumer.consumed_local_research_state
      and self.full_state_lineage_verified
      and self.full_state_channels_audit_verified
    )

  @property
  def global_coupling_verified(self) -> bool:
    """The upstream conservative equations have not consumed the state packet."""

    return False

  @property
  def canonical_free_boundary_verified(self) -> bool:
    return False

  @property
  def downstream_boundary_closure_verified(self) -> bool:
    return False

  @property
  def research_feedback_completed(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalMixedRegimeStateFeedbackStatus
      .COMPLETED_RESEARCH_PRESSURE_GEOMETRY_FEEDBACK
      and self.full_state_consumer_ready
      and self.pressure_geometry_projection_consumed_verified
      and self.fresh_global_resolve_verified
      and self.fidelity_isolation_verified
    )

  def as_report(self) -> dict[str, Any]:
    consumer = self.consumer
    state_channel_audit = {
      'mass': bool(
        consumer is not None and consumer.mass_channel_verified
      ),
      'streamwise_momentum': bool(
        consumer is not None and consumer.streamwise_momentum_channel_verified
      ),
      'transverse_momentum': bool(
        consumer is not None and consumer.transverse_momentum_channel_verified
      ),
      'energy': bool(
        consumer is not None and consumer.energy_channel_verified
      ),
      'entropy': bool(
        consumer is not None and consumer.entropy_channel_verified
      ),
    }
    state_channel_consumption = {
      'mass': False,
      'streamwise_momentum': False,
      'transverse_momentum': False,
      'energy': False,
      'entropy': False,
    }
    boundary_condition = self.boundary_condition
    return {
      'operator_id': MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_STATE_FEEDBACK_OPERATOR_ID,
      'status': self.status.value,
      'research_feedback_completed': self.research_feedback_completed,
      'consumer_id': self.consumer_id,
      'source_closure_fingerprint': self.source_closure_fingerprint,
      'correction_fraction': self.correction_fraction,
      'full_state_consumer_ready': self.full_state_consumer_ready,
      'full_state_lineage_verified': self.full_state_lineage_verified,
      'full_state_channels_audit_verified': (
        self.full_state_channels_audit_verified
      ),
      'full_state_channel_audit': state_channel_audit,
      'full_state_channel_consumed_by_global_equations': state_channel_consumption,
      'pressure_geometry_projection_requested': (
        self.pressure_geometry_projection_requested
      ),
      'pressure_geometry_projection_consumed_verified': (
        self.pressure_geometry_projection_consumed_verified
      ),
      'fresh_global_resolve_verified': self.fresh_global_resolve_verified,
      'fidelity_isolation_verified': self.fidelity_isolation_verified,
      'global_coupling_verified': self.global_coupling_verified,
      'canonical_free_boundary_verified': self.canonical_free_boundary_verified,
      'downstream_boundary_closure_verified': (
        self.downstream_boundary_closure_verified
      ),
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'closure': None if self.closure is None else self.closure.as_report(),
      'downstream': (
        None if self.downstream is None else self.downstream.as_report()
      ),
      'consumer': None if consumer is None else consumer.as_report(),
      'proposal': None if self.proposal is None else self.proposal.as_report(),
      'frontier_request': (
        None
        if self.frontier_request is None
        else self.frontier_request.as_report()
      ),
      'base_target': (
        None if self.base_target is None else self.base_target.as_report()
      ),
      'boundary_condition': (
        None
        if boundary_condition is None
        else boundary_condition.as_report()
      ),
      'claim_status': (
        'research-only-pressure-geometry-projection-from-full-state-trace; '
        'mass, momentum, energy, and entropy remain audit-only; canonical '
        'global coupling, external validation, and production promotion remain open'
      ),
      'message': self.message,
    }


def _failure(
  status: MocReflectedDomainGlobalMixedRegimeStateFeedbackStatus,
  message: str,
  *,
  closure: MocReflectedDomainGlobalPhysicalClosureResult | None = None,
  downstream: MocReflectedDomainGlobalCoupledDownstreamResult | None = None,
  consumer: MocReflectedDomainGlobalMixedRegimeStateConsumerResult | None = None,
  consumer_id: str = 'research-global-mixed-regime-state-feedback-v1',
  correction_fraction: float = _DEFAULT_OUTER_CORRECTION_FRACTION,
  **kwargs: Any,
) -> MocReflectedDomainGlobalMixedRegimeStateFeedbackRun:
  return MocReflectedDomainGlobalMixedRegimeStateFeedbackRun(
    status=status,
    closure=closure,
    downstream=downstream,
    consumer=consumer,
    consumer_id=consumer_id,
    correction_fraction=correction_fraction,
    message=message,
    **kwargs,
  )


def _build_solver_owned_base_target(
  closure: MocReflectedDomainGlobalPhysicalClosureResult,
  request: MocReflectedDomainGlobalFrontierReconciliationRequest,
  *,
  consumer_id: str,
) -> MocPhysicalFieldEulerBoundaryPressureTarget:
  if closure.global_euler is None or closure.global_euler.physical_field is None:
    raise ValueError('source closure retained no physical field for base target')
  field = closure.global_euler.physical_field.field
  if field is None:
    raise ValueError('source closure retained no physical field geometry')
  boundary = field.ambient_boundary
  points = tuple(boundary.points_m)
  states = tuple(boundary.states)
  pressures = tuple(boundary.static_pressure_Pa)
  if not (len(points) == len(states) == len(pressures) >= 2):
    raise ValueError(
      'source closure ambient boundary must retain aligned solver-owned '
      'points, states, and pressure samples'
    )
  return MocPhysicalFieldEulerBoundaryPressureTarget(
    x_stations_m=tuple(point[0] for point in points),
    static_pressure_Pa=pressures,
    boundary_points_m=points,
    tangent_rad=tuple(state.theta_rad for state in states),
    source_id=f'{consumer_id}:base:{request.source_closure_fingerprint}',
    source_closure_fingerprint=request.source_closure_fingerprint,
    source_proposal_fingerprint=request.source_proposal_fingerprint,
  )


def _state_lineage_and_channels_verified(
  closure: MocReflectedDomainGlobalPhysicalClosureResult,
  downstream: MocReflectedDomainGlobalCoupledDownstreamResult,
  consumer: MocReflectedDomainGlobalMixedRegimeStateConsumerResult,
) -> tuple[bool, bool]:
  fingerprint = moc_reflected_domain_global_physical_closure_fingerprint(closure)
  lineage = bool(
    consumer.closure is closure
    and consumer.downstream is downstream
    and consumer.source_closure_fingerprint == fingerprint
    and downstream.source_closure_fingerprint == fingerprint
    and downstream.closure_lineage_verified
    and consumer.closure_lineage_verified
    and consumer.trace is downstream.downstream_boundary_trace
  )
  channels = bool(
    consumer.mass_channel_verified
    and consumer.streamwise_momentum_channel_verified
    and consumer.transverse_momentum_channel_verified
    and consumer.energy_channel_verified
    and consumer.entropy_channel_verified
  )
  return lineage, channels


def measure_reflected_domain_global_mixed_regime_state_feedback(
  closure: MocReflectedDomainGlobalPhysicalClosureResult,
  downstream: MocReflectedDomainGlobalCoupledDownstreamResult,
  *,
  consumer: MocReflectedDomainGlobalMixedRegimeStateConsumerResult | None = None,
  correction_fraction: float = _DEFAULT_OUTER_CORRECTION_FRACTION,
  consumer_id: str = 'research-global-mixed-regime-state-feedback-v1',
  boundary_condition_options: Mapping[str, Any] | None = None,
) -> MocReflectedDomainGlobalMixedRegimeStateFeedbackRun:
  """Consume one audited full-state response and re-solve its projection.

  The function deliberately separates the full-state consumer from the
  pressure/geometry target consumed by the existing global solver.  This
  makes it impossible for a pressure-only global equation to be reported as
  if it had consumed the conservative state vector.
  """

  if not isinstance(closure, MocReflectedDomainGlobalPhysicalClosureResult):
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateFeedbackStatus.INVALID_INPUT,
      'closure must be a MocReflectedDomainGlobalPhysicalClosureResult',
      consumer_id=str(consumer_id),
    )
  if not isinstance(downstream, MocReflectedDomainGlobalCoupledDownstreamResult):
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateFeedbackStatus.INVALID_INPUT,
      'downstream must be a MocReflectedDomainGlobalCoupledDownstreamResult',
      closure=closure,
      consumer_id=str(consumer_id),
    )
  try:
    fraction = float(correction_fraction)
    resolved_consumer_id = str(consumer_id)
    boundary_options = _options(
      boundary_condition_options,
      'boundary_condition_options',
      reserved=('request', 'source_closure', 'base_target'),
    )
  except (TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateFeedbackStatus.INVALID_INPUT,
      f'feedback controls are invalid: {error}',
      closure=closure,
      downstream=downstream,
      consumer_id=str(consumer_id),
    )
  if (
    not resolved_consumer_id
    or not isfinite(fraction)
    or fraction <= 0.0
    or fraction > 1.0
  ):
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateFeedbackStatus.INVALID_INPUT,
      'consumer_id must be non-empty and correction_fraction must be in (0, 1]',
      closure=closure,
      downstream=downstream,
      consumer_id=resolved_consumer_id,
      correction_fraction=(
        fraction if isfinite(fraction) else _DEFAULT_OUTER_CORRECTION_FRACTION
      ),
    )
  ####
  source_fingerprint = moc_reflected_domain_global_physical_closure_fingerprint(
    closure
  )
  if not closure.converged or not closure.physical_closure_verified:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateFeedbackStatus.INVALID_INPUT,
      'feedback requires a locally verified source global physical closure',
      closure=closure,
      downstream=downstream,
      consumer_id=resolved_consumer_id,
      correction_fraction=fraction,
    )
  if (
    not downstream.converged
    or not downstream.local_coupled_field_verified
    or downstream.source_closure_fingerprint != source_fingerprint
  ):
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateFeedbackStatus.DOWNSTREAM_FAILURE,
      'feedback requires a locally verified downstream result with exact '
      'source closure lineage',
      closure=closure,
      downstream=downstream,
      consumer_id=resolved_consumer_id,
      correction_fraction=fraction,
    )
  ####
  if consumer is None:
    try:
      consumer = consume_reflected_domain_global_mixed_regime_state(
        closure,
        downstream,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      return _failure(
        MocReflectedDomainGlobalMixedRegimeStateFeedbackStatus.STATE_CONSUMER_FAILURE,
        f'full-state consumer raised: {error}',
        closure=closure,
        downstream=downstream,
        consumer_id=resolved_consumer_id,
        correction_fraction=fraction,
      )
  if not isinstance(
    consumer,
    MocReflectedDomainGlobalMixedRegimeStateConsumerResult,
  ):
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateFeedbackStatus.INVALID_INPUT,
      'consumer must be a typed mixed-regime state consumer result',
      closure=closure,
      downstream=downstream,
      consumer_id=resolved_consumer_id,
      correction_fraction=fraction,
    )
  lineage_verified, channels_verified = _state_lineage_and_channels_verified(
    closure,
    downstream,
    consumer,
  )
  if not consumer.consumed_local_research_state or not (
    lineage_verified and channels_verified
  ):
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateFeedbackStatus.STATE_CONSUMER_FAILURE,
      'full-state consumer did not pass its exact lineage and mass/momentum/'
      'energy/entropy audit gates',
      closure=closure,
      downstream=downstream,
      consumer=consumer,
      consumer_id=resolved_consumer_id,
      correction_fraction=fraction,
      full_state_lineage_verified=lineage_verified,
      full_state_channels_audit_verified=channels_verified,
    )
  ####
  response = downstream.downstream_boundary_response
  if response is None:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateFeedbackStatus.PROPOSAL_FAILURE,
      'downstream result retained no boundary response for pressure/geometry '
      'projection',
      closure=closure,
      downstream=downstream,
      consumer=consumer,
      consumer_id=resolved_consumer_id,
      correction_fraction=fraction,
      full_state_lineage_verified=lineage_verified,
      full_state_channels_audit_verified=channels_verified,
    )
  try:
    proposal = build_reflected_domain_global_coupled_downstream_upstream_feedback_proposal(
      closure,
      response,
      correction_fraction=fraction,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateFeedbackStatus.PROPOSAL_FAILURE,
      f'pressure/geometry projection proposal failed: {error}',
      closure=closure,
      downstream=downstream,
      consumer=consumer,
      consumer_id=resolved_consumer_id,
      correction_fraction=fraction,
      full_state_lineage_verified=lineage_verified,
      full_state_channels_audit_verified=channels_verified,
    )
  if not proposal.ready_for_global_resolve:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateFeedbackStatus.PROPOSAL_FAILURE,
      'pressure/geometry projection proposal is not ready for a global '
      're-solve',
      closure=closure,
      downstream=downstream,
      consumer=consumer,
      proposal=proposal,
      consumer_id=resolved_consumer_id,
      correction_fraction=fraction,
      full_state_lineage_verified=lineage_verified,
      full_state_channels_audit_verified=channels_verified,
    )
  ####
  try:
    request = build_reflected_domain_global_frontier_reconciliation_request(
      closure,
      proposal,
      consumer_id=resolved_consumer_id,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateFeedbackStatus.FRONTIER_REQUEST_FAILURE,
      f'frontier request construction failed: {error}',
      closure=closure,
      downstream=downstream,
      consumer=consumer,
      proposal=proposal,
      consumer_id=resolved_consumer_id,
      correction_fraction=fraction,
      full_state_lineage_verified=lineage_verified,
      full_state_channels_audit_verified=channels_verified,
    )
  try:
    base_target = _build_solver_owned_base_target(
      closure,
      request,
      consumer_id=resolved_consumer_id,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateFeedbackStatus.BASE_TARGET_FAILURE,
      f'solver-owned base target construction failed: {error}',
      closure=closure,
      downstream=downstream,
      consumer=consumer,
      proposal=proposal,
      frontier_request=request,
      consumer_id=resolved_consumer_id,
      correction_fraction=fraction,
      full_state_lineage_verified=lineage_verified,
      full_state_channels_audit_verified=channels_verified,
    )
  ####
  boundary_options.setdefault('consume_target_geometry', True)
  try:
    boundary_condition = run_reflected_domain_global_frontier_boundary_conditioned_resolve(
      request,
      closure,
      base_target=base_target,
      **boundary_options,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateFeedbackStatus.GLOBAL_RESOLVE_FAILURE,
      f'fresh global feedback resolve raised: {error}',
      closure=closure,
      downstream=downstream,
      consumer=consumer,
      proposal=proposal,
      frontier_request=request,
      base_target=base_target,
      consumer_id=resolved_consumer_id,
      correction_fraction=fraction,
      full_state_lineage_verified=lineage_verified,
      full_state_channels_audit_verified=channels_verified,
      pressure_geometry_projection_requested=bool(
        boundary_options.get('consume_target_geometry', False)
      ),
    )
  ####
  conditioned = boundary_condition.conditioned_closure
  fresh_global_resolve_verified = bool(
    conditioned is not None
    and conditioned is not closure
    and conditioned.converged
    and conditioned.physical_closure_verified
  )
  pressure_geometry_consumed_verified = bool(
    boundary_condition.status
    is MocReflectedDomainGlobalFrontierBoundaryConditionStatus
    .CONVERGED_RESEARCH_BOUNDARY_CONDITION
    and boundary_condition.target_lineage_verified
    and boundary_condition.target_composition_verified
    and boundary_condition.target_boundary_condition_consumed
    and boundary_condition.target_coverage_verified
    and boundary_condition.target_match_verified
    and boundary_condition.geometry_conditioning_verified
  )
  fidelity_isolation_verified = bool(
    boundary_condition.fidelity_isolation_verified
    and boundary_condition.chain_promotion_blocked
    and not boundary_condition.production_claim_allowed
    and (conditioned is None or not conditioned.production_claim_allowed)
  )
  status = (
    MocReflectedDomainGlobalMixedRegimeStateFeedbackStatus
    .COMPLETED_RESEARCH_PRESSURE_GEOMETRY_FEEDBACK
    if (
      fresh_global_resolve_verified
      and pressure_geometry_consumed_verified
      and fidelity_isolation_verified
    )
    else (
      MocReflectedDomainGlobalMixedRegimeStateFeedbackStatus
      .PRESSURE_GEOMETRY_CONSUMPTION_FAILURE
      if fresh_global_resolve_verified and not pressure_geometry_consumed_verified
      else (
        MocReflectedDomainGlobalMixedRegimeStateFeedbackStatus.GLOBAL_RESOLVE_FAILURE
        if not fresh_global_resolve_verified
        else MocReflectedDomainGlobalMixedRegimeStateFeedbackStatus
        .FIDELITY_FAILURE
      )
    )
  )
  return MocReflectedDomainGlobalMixedRegimeStateFeedbackRun(
    status=status,
    closure=closure,
    downstream=downstream,
    consumer=consumer,
    proposal=proposal,
    frontier_request=request,
    base_target=base_target,
    boundary_condition=boundary_condition,
    consumer_id=resolved_consumer_id,
    correction_fraction=fraction,
    full_state_lineage_verified=lineage_verified,
    full_state_channels_audit_verified=channels_verified,
    pressure_geometry_projection_requested=bool(
      boundary_options.get('consume_target_geometry', False)
    ),
    pressure_geometry_projection_consumed_verified=(
      pressure_geometry_consumed_verified
    ),
    fresh_global_resolve_verified=fresh_global_resolve_verified,
    fidelity_isolation_verified=fidelity_isolation_verified,
    message=(
      'full conservative downstream trace passed its independent audit; its '
      'pressure/geometry projection was consumed by a fresh global physical '
      'closure solve; mass, momentum, energy, and entropy remain audit-only '
      'because the upstream global equations do not yet consume those channels'
      if status
      is MocReflectedDomainGlobalMixedRegimeStateFeedbackStatus
      .COMPLETED_RESEARCH_PRESSURE_GEOMETRY_FEEDBACK
      else boundary_condition.message
    ),
  )


def run_reflected_domain_global_mixed_regime_state_feedback(
  closure: MocReflectedDomainGlobalPhysicalClosureResult,
  *,
  reference_total_temperature_K: float,
  ambient_pressure_Pa: float | None = None,
  correction_fraction: float = _DEFAULT_OUTER_CORRECTION_FRACTION,
  consumer_id: str = 'research-global-mixed-regime-state-feedback-v1',
  downstream_options: Mapping[str, Any] | None = None,
  boundary_condition_options: Mapping[str, Any] | None = None,
) -> MocReflectedDomainGlobalMixedRegimeStateFeedbackRun:
  """Run a fresh downstream trace, consume it, and re-solve its projection."""

  if not isinstance(closure, MocReflectedDomainGlobalPhysicalClosureResult):
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateFeedbackStatus.INVALID_INPUT,
      'closure must be a MocReflectedDomainGlobalPhysicalClosureResult',
      consumer_id=str(consumer_id),
    )
  try:
    options = _options(
      downstream_options,
      'downstream_options',
      reserved=('closure', 'reference_total_temperature_K', 'ambient_pressure_Pa'),
    )
    temperature = float(reference_total_temperature_K)
  except (TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateFeedbackStatus.INVALID_INPUT,
      f'downstream feedback inputs are invalid: {error}',
      closure=closure,
      consumer_id=str(consumer_id),
    )
  if not isfinite(temperature) or temperature <= 0.0:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateFeedbackStatus.INVALID_INPUT,
      'reference_total_temperature_K must be finite and positive',
      closure=closure,
      consumer_id=str(consumer_id),
    )
  try:
    downstream = solve_reflected_domain_global_coupled_downstream(
      closure,
      reference_total_temperature_K=temperature,
      ambient_pressure_Pa=ambient_pressure_Pa,
      **options,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateFeedbackStatus.DOWNSTREAM_FAILURE,
      f'fresh downstream solve raised: {error}',
      closure=closure,
      consumer_id=str(consumer_id),
    )
  return measure_reflected_domain_global_mixed_regime_state_feedback(
    closure,
    downstream,
    correction_fraction=correction_fraction,
    consumer_id=consumer_id,
    boundary_condition_options=boundary_condition_options,
  )
