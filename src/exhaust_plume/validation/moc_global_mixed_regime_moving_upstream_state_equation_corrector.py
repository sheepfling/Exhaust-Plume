"""Research-only moving corrector for the upstream state/entropy equation.

The upstream interface-strip equation is now an executable, independently
audited research seam.  This module makes it part of a moving/global
correction attempt without changing the canonical claim ceiling:

``exact downstream trace -> upstream state/entropy equation -> strict
moving/global front correction -> fresh downstream trace -> upstream
state/entropy equation``.

The initial and final upstream equation residual vectors are retained beside
the downstream coupled-state vector.  Acceptance requires component-wise
descent of the combined vector; a scalar norm or a successful geometry
handoff cannot hide a worsening state or entropy channel.  The moving solver
still owns only the currently available research front response, so this
operator remains below canonical global/free-boundary closure and production
promotion until the actual characteristic/free-boundary equations and
external physical comparisons are closed.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Any

from exhaust_plume.models.moc.global_coupled_downstream import (
  MocReflectedDomainGlobalCoupledDownstreamResult,
)
from exhaust_plume.models.moc.global_mixed_regime_state_consumer import (
  MocReflectedDomainGlobalMixedRegimeStateConsumerResult,
  consume_reflected_domain_global_mixed_regime_state,
)
from exhaust_plume.models.moc.global_mixed_regime_upstream_state_equation import (
  MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationAudit,
  MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRequest,
  MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationResult,
  audit_reflected_domain_global_mixed_regime_upstream_state_equation,
  solve_reflected_domain_global_mixed_regime_upstream_state_equation,
)
from exhaust_plume.models.moc.global_physical_closure import (
  MocReflectedDomainGlobalPhysicalClosureResult,
  moc_reflected_domain_global_physical_closure_fingerprint,
)
from exhaust_plume.validation.moc_global_mixed_regime_moving_state_coupled_step import (
  MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepResult,
  run_reflected_domain_global_mixed_regime_moving_state_coupled_step,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_MOVING_UPSTREAM_STATE_EQUATION_CORRECTOR_OPERATOR_ID',
  'MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_MOVING_UPSTREAM_STATE_EQUATION_RESIDUAL_NAMES',
  'MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationCorrectorStatus',
  'MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationCorrectorResult',
  'run_reflected_domain_global_mixed_regime_moving_upstream_state_equation_corrector',
)


MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_MOVING_UPSTREAM_STATE_EQUATION_CORRECTOR_OPERATOR_ID = (
  'op.moc.reflected-domain.global-mixed-regime-moving-upstream-state-equation-corrector-v1'
)
MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_MOVING_UPSTREAM_STATE_EQUATION_RESIDUAL_NAMES = (
  'upstream_mass',
  'upstream_streamwise_momentum',
  'upstream_transverse_momentum',
  'upstream_energy',
  'upstream_euler',
  'upstream_target_entropy',
  'upstream_entropy_flux',
  'downstream_density',
  'downstream_streamwise_momentum',
  'downstream_transverse_momentum',
  'downstream_energy',
  'downstream_euler',
  'downstream_pressure',
  'downstream_normal_velocity',
  'downstream_centerline_normal_velocity',
  'downstream_shape',
  'downstream_entropy',
)
_ENTROPY_FLUX_TOLERANCE = 1.0e-8


class MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationCorrectorStatus(
  str,
  Enum,
):
  """Typed outcomes of one moving upstream-equation correction attempt."""

  CONVERGED_RESEARCH_MOVING_UPSTREAM_STATE_EQUATION_CORRECTOR = (
    'converged-research-moving-upstream-state-equation-corrector'
  )
  COMPLETED_RESEARCH_MOVING_UPSTREAM_STATE_EQUATION_CORRECTOR_WITH_OPEN_RESIDUAL = (
    'completed-research-moving-upstream-state-equation-corrector-with-open-residual'
  )
  INVALID_INPUT = 'invalid_input'
  INITIAL_STATE_EQUATION_FAILURE = (
    'moving-upstream-state-equation-corrector-initial-equation-failure'
  )
  MOVING_GLOBAL_FAILURE = (
    'moving-upstream-state-equation-corrector-moving-global-failure'
  )
  FINAL_STATE_EQUATION_FAILURE = (
    'moving-upstream-state-equation-corrector-final-equation-failure'
  )
  RESIDUAL_DESCENT_FAILURE = (
    'moving-upstream-state-equation-corrector-residual-descent-failure'
  )
  LINEAGE_FAILURE = (
    'moving-upstream-state-equation-corrector-lineage-failure'
  )
####


def _options(value: Mapping[str, Any] | None, name: str) -> dict[str, Any]:
  if value is None:
    return {}
  ####
  if not isinstance(value, Mapping):
    raise TypeError(f'{name} must be a mapping when supplied')
  ####
  return dict(value)
####


def _componentwise_descent(
  before: tuple[float, ...],
  after: tuple[float, ...],
) -> bool:
  """Require no component worsening and at least one strict decrease."""

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


def _downstream_vector(
  downstream: MocReflectedDomainGlobalCoupledDownstreamResult | None,
) -> tuple[float, ...]:
  if downstream is None:
    return ()
  ####
  value = downstream.normalized_coupled_state_residual_vector
  if value is None:
    return ()
  ####
  vector = tuple(float(item) for item in value)
  if any(not isfinite(item) or item < 0.0 for item in vector):
    return ()
  ####
  return vector
####


def _upstream_vector(
  equation: MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationResult | None,
) -> tuple[float, ...]:
  """Aggregate the exact upstream equation channels in declared units."""

  if (
    equation is None
    or equation.request is None
    or not equation.research_state_equation_consumed
    or not equation.residual_channels_by_cell
  ):
    return ()
  ####
  rows = tuple(tuple(float(value) for value in row) for row in equation.residual_channels_by_cell)
  if any(
    len(row) != 5 or any(not isfinite(value) or value < 0.0 for value in row)
    for row in rows
  ):
    return ()
  ####
  conservative = tuple(
    max(row[index] for row in rows)
    for index in range(5)
  )
  entropy_log = equation.maximum_target_boundary_entropy_log_residual
  entropy_defect = equation.maximum_entropy_flux_defect
  if entropy_log is None or entropy_defect is None:
    return ()
  ####
  entropy_log_value = float(entropy_log) / equation.request.target_entropy_consistency_tolerance
  entropy_defect_value = float(entropy_defect) / _ENTROPY_FLUX_TOLERANCE
  vector = (*conservative, entropy_log_value, entropy_defect_value)
  if any(not isfinite(value) or value < 0.0 for value in vector):
    return ()
  ####
  return tuple(float(value) for value in vector)
####


def _combined_vector(
  upstream: tuple[float, ...],
  downstream: tuple[float, ...],
) -> tuple[float, ...]:
  if len(upstream) != 7 or len(downstream) != 10:
    return ()
  ####
  return (*upstream, *downstream)
####


def _equation_request(
  closure: MocReflectedDomainGlobalPhysicalClosureResult,
  consumer: MocReflectedDomainGlobalMixedRegimeStateConsumerResult,
  reference_total_temperature_K: float,
  equation_options: Mapping[str, Any] | None,
  *,
  max_pseudo_iterations: int,
) -> MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRequest:
  """Build a target request only from the exact consumer-owned trace."""

  if consumer.closure is not closure or consumer.trace is None:
    raise ValueError('state consumer did not retain the exact closure and trace')
  ####
  if not consumer.consumed_local_research_state:
    raise ValueError('state consumer did not pass its local full-state gates')
  ####
  samples = tuple(consumer.trace.samples)
  if len(samples) < 2:
    raise ValueError('state consumer trace must contain at least two samples')
  ####
  gamma = float(samples[0].gamma)
  if any(abs(float(sample.gamma) - gamma) > 1.0e-12 for sample in samples):
    raise ValueError('state consumer trace gamma must be constant')
  ####
  options = _options(equation_options, 'equation_options')
  reserved = (
    'closure',
    'target_points_m',
    'target_conservative_state_profile',
    'target_entropy_proxy_profile',
    'target_gamma',
    'reference_total_temperature_K',
  )
  collisions = tuple(key for key in reserved if key in options)
  if collisions:
    raise ValueError(
      'equation_options cannot override the exact target frame: '
      + ', '.join(collisions)
    )
  ####
  options.setdefault('max_pseudo_iterations', max_pseudo_iterations)
  return MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRequest(
    closure=closure,
    target_points_m=tuple(sample.point_m for sample in samples),
    target_conservative_state_profile=tuple(
      sample.conservative_state for sample in samples
    ),
    target_entropy_proxy_profile=tuple(
      sample.entropy_proxy for sample in samples
    ),
    target_gamma=gamma,
    reference_total_temperature_K=reference_total_temperature_K,
    **options,
  )
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationCorrectorResult:
  """Evidence from one exact moving/global upstream-equation correction."""

  status: MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationCorrectorStatus
  source_closure: MocReflectedDomainGlobalPhysicalClosureResult | None
  source_downstream: MocReflectedDomainGlobalCoupledDownstreamResult | None
  initial_state_consumer: (
    MocReflectedDomainGlobalMixedRegimeStateConsumerResult | None
  ) = None
  initial_equation: (
    MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationResult | None
  ) = None
  initial_equation_audit: (
    MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationAudit | None
  ) = None
  moving_global_step: (
    MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepResult | None
  ) = None
  final_closure: MocReflectedDomainGlobalPhysicalClosureResult | None = None
  final_downstream: MocReflectedDomainGlobalCoupledDownstreamResult | None = None
  final_state_consumer: (
    MocReflectedDomainGlobalMixedRegimeStateConsumerResult | None
  ) = None
  final_equation: (
    MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationResult | None
  ) = None
  final_equation_audit: (
    MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationAudit | None
  ) = None
  initial_upstream_residual_vector: tuple[float, ...] = ()
  final_upstream_residual_vector: tuple[float, ...] = ()
  initial_downstream_residual_vector: tuple[float, ...] = ()
  final_downstream_residual_vector: tuple[float, ...] = ()
  initial_combined_residual_vector: tuple[float, ...] = ()
  final_combined_residual_vector: tuple[float, ...] = ()
  source_lineage_verified: bool = False
  initial_equation_consumption_verified: bool = False
  initial_equation_replay_verified: bool = False
  moving_global_corrector_verified: bool = False
  final_lineage_verified: bool = False
  final_equation_consumption_verified: bool = False
  final_equation_replay_verified: bool = False
  upstream_componentwise_residual_descent_verified: bool = False
  combined_componentwise_residual_descent_verified: bool = False
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
      MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationCorrectorStatus,
    ):
      raise TypeError('status must be a typed moving upstream-corrector status')
    ####
    for name, expected in (
      ('source_closure', MocReflectedDomainGlobalPhysicalClosureResult),
      ('source_downstream', MocReflectedDomainGlobalCoupledDownstreamResult),
      (
        'initial_state_consumer',
        MocReflectedDomainGlobalMixedRegimeStateConsumerResult,
      ),
      (
        'initial_equation',
        MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationResult,
      ),
      (
        'initial_equation_audit',
        MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationAudit,
      ),
      (
        'moving_global_step',
        MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepResult,
      ),
      ('final_closure', MocReflectedDomainGlobalPhysicalClosureResult),
      ('final_downstream', MocReflectedDomainGlobalCoupledDownstreamResult),
      (
        'final_state_consumer',
        MocReflectedDomainGlobalMixedRegimeStateConsumerResult,
      ),
      (
        'final_equation',
        MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationResult,
      ),
      (
        'final_equation_audit',
        MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationAudit,
      ),
    ):
      value = getattr(self, name)
      if value is not None and not isinstance(value, expected):
        raise TypeError(f'{name} must retain its typed research result')
      ####
    ####
    for name in (
      'initial_upstream_residual_vector',
      'final_upstream_residual_vector',
      'initial_downstream_residual_vector',
      'final_downstream_residual_vector',
      'initial_combined_residual_vector',
      'final_combined_residual_vector',
    ):
      values = tuple(float(value) for value in getattr(self, name))
      if any(not isfinite(value) or value < 0.0 for value in values):
        raise ValueError(f'{name} must contain finite nonnegative values')
      ####
      object.__setattr__(self, name, values)
    ####
    for name in (
      'source_lineage_verified',
      'initial_equation_consumption_verified',
      'initial_equation_replay_verified',
      'moving_global_corrector_verified',
      'final_lineage_verified',
      'final_equation_consumption_verified',
      'final_equation_replay_verified',
      'upstream_componentwise_residual_descent_verified',
      'combined_componentwise_residual_descent_verified',
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
    if self.global_coupling_verified or self.canonical_free_boundary_verified:
      raise ValueError(
        'moving upstream state-equation corrector cannot claim canonical closure'
      )
    ####
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError(
        'moving upstream state-equation corrector must remain promotion-blocked'
      )
    ####
    if self.status is (
      MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationCorrectorStatus
      .CONVERGED_RESEARCH_MOVING_UPSTREAM_STATE_EQUATION_CORRECTOR
    ) and not (
      self.source_lineage_verified
      and self.initial_equation_consumption_verified
      and self.initial_equation_replay_verified
      and self.moving_global_corrector_verified
      and self.final_lineage_verified
      and self.final_equation_consumption_verified
      and self.final_equation_replay_verified
      and self.upstream_componentwise_residual_descent_verified
      and self.combined_componentwise_residual_descent_verified
      and self.upstream_state_equation_consumed
    ):
      raise ValueError(
        'converged moving upstream corrector must pass both equation and descent gates'
      )
    ####
    object.__setattr__(self, 'message', str(self.message))
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

  @property
  def research_corrector_verified(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationCorrectorStatus
      .CONVERGED_RESEARCH_MOVING_UPSTREAM_STATE_EQUATION_CORRECTOR
      and self.source_lineage_verified
      and self.initial_equation_consumption_verified
      and self.initial_equation_replay_verified
      and self.moving_global_corrector_verified
      and self.final_lineage_verified
      and self.final_equation_consumption_verified
      and self.final_equation_replay_verified
      and self.upstream_componentwise_residual_descent_verified
      and self.combined_componentwise_residual_descent_verified
      and self.upstream_state_equation_consumed
    )
  ####

  @property
  def converged(self) -> bool:
    return self.research_corrector_verified
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': (
        MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_MOVING_UPSTREAM_STATE_EQUATION_CORRECTOR_OPERATOR_ID
      ),
      'residual_channel_names': (
        MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_MOVING_UPSTREAM_STATE_EQUATION_RESIDUAL_NAMES
      ),
      'status': self.status.value,
      'converged': self.converged,
      'research_corrector_verified': self.research_corrector_verified,
      'source_closure_fingerprint': self.source_closure_fingerprint,
      'initial_upstream_residual_vector': self.initial_upstream_residual_vector,
      'final_upstream_residual_vector': self.final_upstream_residual_vector,
      'initial_downstream_residual_vector': self.initial_downstream_residual_vector,
      'final_downstream_residual_vector': self.final_downstream_residual_vector,
      'initial_combined_residual_vector': self.initial_combined_residual_vector,
      'final_combined_residual_vector': self.final_combined_residual_vector,
      'source_lineage_verified': self.source_lineage_verified,
      'initial_equation_consumption_verified': (
        self.initial_equation_consumption_verified
      ),
      'initial_equation_replay_verified': self.initial_equation_replay_verified,
      'moving_global_corrector_verified': self.moving_global_corrector_verified,
      'final_lineage_verified': self.final_lineage_verified,
      'final_equation_consumption_verified': (
        self.final_equation_consumption_verified
      ),
      'final_equation_replay_verified': self.final_equation_replay_verified,
      'upstream_componentwise_residual_descent_verified': (
        self.upstream_componentwise_residual_descent_verified
      ),
      'combined_componentwise_residual_descent_verified': (
        self.combined_componentwise_residual_descent_verified
      ),
      'require_componentwise_residual_descent': (
        self.require_componentwise_residual_descent
      ),
      'upstream_state_equation_consumed': self.upstream_state_equation_consumed,
      'global_coupling_verified': False,
      'canonical_free_boundary_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'initial_state_consumer': (
        None
        if self.initial_state_consumer is None
        else self.initial_state_consumer.as_report()
      ),
      'initial_equation': (
        None if self.initial_equation is None else self.initial_equation.as_report()
      ),
      'initial_equation_audit': (
        None
        if self.initial_equation_audit is None
        else self.initial_equation_audit.as_report()
      ),
      'moving_global_step': (
        None
        if self.moving_global_step is None
        else self.moving_global_step.as_report()
      ),
      'final_closure': (
        None if self.final_closure is None else self.final_closure.as_report()
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
      'final_equation': (
        None if self.final_equation is None else self.final_equation.as_report()
      ),
      'final_equation_audit': (
        None
        if self.final_equation_audit is None
        else self.final_equation_audit.as_report()
      ),
      'claim_status': (
        'research-only moving upstream state/entropy equation correction; the '
        'combined residual gate is local evidence, not canonical global '
        'free-boundary closure, physical shock-cell acceptance, external '
        'validation, or a production claim'
      ),
      'message': self.message,
    }
  ####
####


def _failure(
  status: MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationCorrectorStatus,
  message: str,
  *,
  source_closure: MocReflectedDomainGlobalPhysicalClosureResult | None = None,
  source_downstream: MocReflectedDomainGlobalCoupledDownstreamResult | None = None,
  require_componentwise_residual_descent: bool = True,
  **kwargs: Any,
) -> MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationCorrectorResult:
  return MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationCorrectorResult(
    status=status,
    source_closure=source_closure,
    source_downstream=source_downstream,
    require_componentwise_residual_descent=require_componentwise_residual_descent,
    message=message,
    **kwargs,
  )
####


def run_reflected_domain_global_mixed_regime_moving_upstream_state_equation_corrector(
  closure: MocReflectedDomainGlobalPhysicalClosureResult,
  downstream: MocReflectedDomainGlobalCoupledDownstreamResult,
  *,
  reference_total_temperature_K: float,
  correction_fraction: float = 0.005,
  equation_options: Mapping[str, Any] | None = None,
  moving_interface_options: Mapping[str, Any] | None = None,
  state_resolve_options: Mapping[str, Any] | None = None,
  state_boundary_condition_options: Mapping[str, Any] | None = None,
  downstream_options: Mapping[str, Any] | None = None,
  geometry_response_options: Mapping[str, Any] | None = None,
  max_equation_pseudo_iterations: int = 80,
  consumer_id: str = (
    'research-global-mixed-regime-moving-upstream-state-equation-corrector-v1'
  ),
  require_componentwise_residual_descent: bool = True,
) -> MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationCorrectorResult:
  """Run one exact upstream-equation-aware moving/global research correction."""

  status_type = (
    MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationCorrectorStatus
  )
  if not isinstance(closure, MocReflectedDomainGlobalPhysicalClosureResult):
    return _failure(status_type.INVALID_INPUT, 'closure must be a typed global physical closure')
  ####
  if not isinstance(downstream, MocReflectedDomainGlobalCoupledDownstreamResult):
    return _failure(
      status_type.INVALID_INPUT,
      'downstream must be a typed global coupled-downstream result',
      source_closure=closure,
    )
  ####
  if not isinstance(require_componentwise_residual_descent, bool):
    return _failure(
      status_type.INVALID_INPUT,
      'require_componentwise_residual_descent must be a bool',
      source_closure=closure,
      source_downstream=downstream,
    )
  ####
  try:
    temperature = float(reference_total_temperature_K)
    resolved_correction_fraction = float(correction_fraction)
    resolved_equation_options = _options(equation_options, 'equation_options')
    resolved_moving_options = _options(
      moving_interface_options,
      'moving_interface_options',
    )
    resolved_state_options = _options(state_resolve_options, 'state_resolve_options')
    resolved_boundary_options = _options(
      state_boundary_condition_options,
      'state_boundary_condition_options',
    )
    resolved_downstream_options = _options(downstream_options, 'downstream_options')
    resolved_geometry_options = _options(
      geometry_response_options,
      'geometry_response_options',
    )
    resolved_consumer_id = str(consumer_id)
  except (TypeError, ValueError) as error:
    return _failure(
      status_type.INVALID_INPUT,
      f'moving upstream corrector controls are invalid: {error}',
      source_closure=closure,
      source_downstream=downstream,
      require_componentwise_residual_descent=require_componentwise_residual_descent,
    )
  ####
  if not isfinite(temperature) or temperature <= 0.0:
    return _failure(
      status_type.INVALID_INPUT,
      'reference_total_temperature_K must be finite and positive',
      source_closure=closure,
      source_downstream=downstream,
      require_componentwise_residual_descent=require_componentwise_residual_descent,
    )
  ####
  if (
    not isfinite(resolved_correction_fraction)
    or resolved_correction_fraction <= 0.0
    or resolved_correction_fraction > 1.0
  ):
    return _failure(
      status_type.INVALID_INPUT,
      'correction_fraction must be finite and in (0, 1]',
      source_closure=closure,
      source_downstream=downstream,
      require_componentwise_residual_descent=require_componentwise_residual_descent,
    )
  ####
  if not resolved_consumer_id:
    return _failure(
      status_type.INVALID_INPUT,
      'consumer_id must be non-empty',
      source_closure=closure,
      source_downstream=downstream,
      require_componentwise_residual_descent=require_componentwise_residual_descent,
    )
  ####
  if (
    isinstance(max_equation_pseudo_iterations, bool)
    or not isinstance(max_equation_pseudo_iterations, int)
    or max_equation_pseudo_iterations < 1
  ):
    return _failure(
      status_type.INVALID_INPUT,
      'max_equation_pseudo_iterations must be a positive integer',
      source_closure=closure,
      source_downstream=downstream,
      require_componentwise_residual_descent=require_componentwise_residual_descent,
    )
  ####
  fingerprint = moc_reflected_domain_global_physical_closure_fingerprint(closure)
  source_lineage = bool(
    closure.converged
    and closure.physical_closure_verified
    and downstream.closure is closure
    and downstream.closure_lineage_verified
    and downstream.source_closure_fingerprint == fingerprint
  )
  if not source_lineage:
    return _failure(
      status_type.LINEAGE_FAILURE,
      'source downstream result did not retain the exact verified closure identity',
      source_closure=closure,
      source_downstream=downstream,
      require_componentwise_residual_descent=require_componentwise_residual_descent,
    )
  ####
  try:
    initial_consumer = consume_reflected_domain_global_mixed_regime_state(
      closure,
      downstream,
    )
    initial_request = _equation_request(
      closure,
      initial_consumer,
      temperature,
      resolved_equation_options,
      max_pseudo_iterations=max_equation_pseudo_iterations,
    )
    initial_equation = solve_reflected_domain_global_mixed_regime_upstream_state_equation(
      initial_request
    )
    initial_audit = audit_reflected_domain_global_mixed_regime_upstream_state_equation(
      initial_equation
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      status_type.INITIAL_STATE_EQUATION_FAILURE,
      f'initial upstream state/entropy equation raised: {error}',
      source_closure=closure,
      source_downstream=downstream,
      source_lineage_verified=source_lineage,
      require_componentwise_residual_descent=require_componentwise_residual_descent,
    )
  ####
  initial_consumption = bool(
    initial_consumer.consumed_local_research_state
    and initial_equation.research_state_equation_consumed
  )
  initial_replay = bool(initial_audit.converged)
  initial_upstream = _upstream_vector(initial_equation)
  initial_downstream = _downstream_vector(downstream)
  initial_combined = _combined_vector(initial_upstream, initial_downstream)
  if not (initial_consumption and initial_replay and initial_combined):
    return _failure(
      status_type.INITIAL_STATE_EQUATION_FAILURE,
      'initial state/entropy equation did not retain an independently audited '
      'combined residual vector',
      source_closure=closure,
      source_downstream=downstream,
      initial_state_consumer=initial_consumer,
      initial_equation=initial_equation,
      initial_equation_audit=initial_audit,
      initial_upstream_residual_vector=initial_upstream,
      initial_downstream_residual_vector=initial_downstream,
      initial_combined_residual_vector=initial_combined,
      source_lineage_verified=source_lineage,
      initial_equation_consumption_verified=initial_consumption,
      initial_equation_replay_verified=initial_replay,
      require_componentwise_residual_descent=require_componentwise_residual_descent,
    )
  ####
  try:
    moving_global_step = run_reflected_domain_global_mixed_regime_moving_state_coupled_step(
      closure,
      downstream,
      reference_total_temperature_K=temperature,
      correction_fraction=resolved_correction_fraction,
      consumer_id=f'{resolved_consumer_id}:moving',
      require_componentwise_residual_descent=False,
      state_resolve_options=resolved_state_options,
      state_boundary_condition_options=resolved_boundary_options,
      moving_interface_options=resolved_moving_options,
      downstream_options=resolved_downstream_options,
      geometry_response_options=resolved_geometry_options,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      status_type.MOVING_GLOBAL_FAILURE,
      f'moving/global state correction raised: {error}',
      source_closure=closure,
      source_downstream=downstream,
      initial_state_consumer=initial_consumer,
      initial_equation=initial_equation,
      initial_equation_audit=initial_audit,
      initial_upstream_residual_vector=initial_upstream,
      initial_downstream_residual_vector=initial_downstream,
      initial_combined_residual_vector=initial_combined,
      source_lineage_verified=source_lineage,
      initial_equation_consumption_verified=initial_consumption,
      initial_equation_replay_verified=initial_replay,
      require_componentwise_residual_descent=require_componentwise_residual_descent,
    )
  ####
  final_closure = moving_global_step.geometry_closure
  final_downstream = moving_global_step.final_downstream
  final_consumer = moving_global_step.final_state_consumer
  moving_verified = bool(
    moving_global_step.state_target_consumed_by_downstream_equations
    and moving_global_step.moving_lineage_verified
    and moving_global_step.moving_conservative_flux_closure_verified
    and moving_global_step.moving_entropy_transition_verified
    and moving_global_step.moving_global_physical_field_consumed
    and moving_global_step.moving_geometry_reconciliation_verified
    and moving_global_step.final_trace_audit_verified
    and final_closure is not None
    and final_downstream is not None
    and final_consumer is not None
  )
  if not moving_verified:
    return _failure(
      status_type.MOVING_GLOBAL_FAILURE,
      'moving/global correction did not retain all strict front, geometry, '
      'and final-trace gates',
      source_closure=closure,
      source_downstream=downstream,
      initial_state_consumer=initial_consumer,
      initial_equation=initial_equation,
      initial_equation_audit=initial_audit,
      moving_global_step=moving_global_step,
      final_closure=final_closure,
      final_downstream=final_downstream,
      final_state_consumer=final_consumer,
      initial_upstream_residual_vector=initial_upstream,
      initial_downstream_residual_vector=initial_downstream,
      initial_combined_residual_vector=initial_combined,
      source_lineage_verified=source_lineage,
      initial_equation_consumption_verified=initial_consumption,
      initial_equation_replay_verified=initial_replay,
      moving_global_corrector_verified=False,
      require_componentwise_residual_descent=require_componentwise_residual_descent,
    )
  ####
  assert final_closure is not None
  assert final_downstream is not None
  assert final_consumer is not None
  final_fingerprint = moc_reflected_domain_global_physical_closure_fingerprint(
    final_closure
  )
  final_lineage = bool(
    final_closure is not closure
    and final_downstream.closure is final_closure
    and final_downstream.closure_lineage_verified
    and final_downstream.source_closure_fingerprint == final_fingerprint
    and final_consumer.closure is final_closure
    and final_consumer.downstream is final_downstream
    and final_consumer.consumed_local_research_state
  )
  if not final_lineage:
    return _failure(
      status_type.LINEAGE_FAILURE,
      'fresh post-correction downstream trace did not retain exact closure lineage',
      source_closure=closure,
      source_downstream=downstream,
      initial_state_consumer=initial_consumer,
      initial_equation=initial_equation,
      initial_equation_audit=initial_audit,
      moving_global_step=moving_global_step,
      final_closure=final_closure,
      final_downstream=final_downstream,
      final_state_consumer=final_consumer,
      initial_upstream_residual_vector=initial_upstream,
      initial_downstream_residual_vector=initial_downstream,
      initial_combined_residual_vector=initial_combined,
      source_lineage_verified=source_lineage,
      initial_equation_consumption_verified=initial_consumption,
      initial_equation_replay_verified=initial_replay,
      moving_global_corrector_verified=moving_verified,
      final_lineage_verified=False,
      require_componentwise_residual_descent=require_componentwise_residual_descent,
    )
  ####
  try:
    final_request = _equation_request(
      final_closure,
      final_consumer,
      temperature,
      resolved_equation_options,
      max_pseudo_iterations=max_equation_pseudo_iterations,
    )
    final_equation = solve_reflected_domain_global_mixed_regime_upstream_state_equation(
      final_request
    )
    final_audit = audit_reflected_domain_global_mixed_regime_upstream_state_equation(
      final_equation
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      status_type.FINAL_STATE_EQUATION_FAILURE,
      f'final upstream state/entropy equation raised: {error}',
      source_closure=closure,
      source_downstream=downstream,
      initial_state_consumer=initial_consumer,
      initial_equation=initial_equation,
      initial_equation_audit=initial_audit,
      moving_global_step=moving_global_step,
      final_closure=final_closure,
      final_downstream=final_downstream,
      final_state_consumer=final_consumer,
      initial_upstream_residual_vector=initial_upstream,
      initial_downstream_residual_vector=initial_downstream,
      initial_combined_residual_vector=initial_combined,
      source_lineage_verified=source_lineage,
      initial_equation_consumption_verified=initial_consumption,
      initial_equation_replay_verified=initial_replay,
      moving_global_corrector_verified=moving_verified,
      final_lineage_verified=final_lineage,
      require_componentwise_residual_descent=require_componentwise_residual_descent,
    )
  ####
  final_consumption = bool(
    final_equation.research_state_equation_consumed
    and final_consumer.consumed_local_research_state
  )
  final_replay = bool(final_audit.converged)
  final_upstream = _upstream_vector(final_equation)
  final_downstream_vector = _downstream_vector(final_downstream)
  final_combined = _combined_vector(final_upstream, final_downstream_vector)
  if not (final_consumption and final_replay and final_combined):
    return _failure(
      status_type.FINAL_STATE_EQUATION_FAILURE,
      'final state/entropy equation did not retain an independently audited '
      'combined residual vector',
      source_closure=closure,
      source_downstream=downstream,
      initial_state_consumer=initial_consumer,
      initial_equation=initial_equation,
      initial_equation_audit=initial_audit,
      moving_global_step=moving_global_step,
      final_closure=final_closure,
      final_downstream=final_downstream,
      final_state_consumer=final_consumer,
      final_equation=final_equation,
      final_equation_audit=final_audit,
      initial_upstream_residual_vector=initial_upstream,
      final_upstream_residual_vector=final_upstream,
      initial_downstream_residual_vector=initial_downstream,
      final_downstream_residual_vector=final_downstream_vector,
      initial_combined_residual_vector=initial_combined,
      final_combined_residual_vector=final_combined,
      source_lineage_verified=source_lineage,
      initial_equation_consumption_verified=initial_consumption,
      initial_equation_replay_verified=initial_replay,
      moving_global_corrector_verified=moving_verified,
      final_lineage_verified=final_lineage,
      final_equation_consumption_verified=final_consumption,
      final_equation_replay_verified=final_replay,
      upstream_state_equation_consumed=bool(initial_consumption and final_consumption),
      require_componentwise_residual_descent=require_componentwise_residual_descent,
    )
  ####
  upstream_descent = _componentwise_descent(initial_upstream, final_upstream)
  combined_descent = _componentwise_descent(initial_combined, final_combined)
  common = dict(
    source_closure=closure,
    source_downstream=downstream,
    initial_state_consumer=initial_consumer,
    initial_equation=initial_equation,
    initial_equation_audit=initial_audit,
    moving_global_step=moving_global_step,
    final_closure=final_closure,
    final_downstream=final_downstream,
    final_state_consumer=final_consumer,
    final_equation=final_equation,
    final_equation_audit=final_audit,
    initial_upstream_residual_vector=initial_upstream,
    final_upstream_residual_vector=final_upstream,
    initial_downstream_residual_vector=initial_downstream,
    final_downstream_residual_vector=final_downstream_vector,
    initial_combined_residual_vector=initial_combined,
    final_combined_residual_vector=final_combined,
    source_lineage_verified=source_lineage,
    initial_equation_consumption_verified=initial_consumption,
    initial_equation_replay_verified=initial_replay,
    moving_global_corrector_verified=moving_verified,
    final_lineage_verified=final_lineage,
    final_equation_consumption_verified=final_consumption,
    final_equation_replay_verified=final_replay,
    upstream_componentwise_residual_descent_verified=upstream_descent,
    combined_componentwise_residual_descent_verified=combined_descent,
    upstream_state_equation_consumed=bool(initial_consumption and final_consumption),
    require_componentwise_residual_descent=require_componentwise_residual_descent,
  )
  if require_componentwise_residual_descent and not combined_descent:
    return _failure(
      status_type.RESIDUAL_DESCENT_FAILURE,
      'moving/global correction completed, but the exact combined upstream '
      'state/entropy and downstream residual vector did not descend '
      'component-wise; scalar-only evidence was not accepted',
      **common,
    )
  ####
  status = (
    status_type.CONVERGED_RESEARCH_MOVING_UPSTREAM_STATE_EQUATION_CORRECTOR
    if combined_descent
    else status_type.COMPLETED_RESEARCH_MOVING_UPSTREAM_STATE_EQUATION_CORRECTOR_WITH_OPEN_RESIDUAL
  )
  return MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationCorrectorResult(
    status=status,
    message=(
      'the exact downstream state/entropy trace was consumed before and after '
      'a strict moving/global front correction; both equation reports were '
      'independently replayed and the combined residual vector descended '
      'component-wise'
      if combined_descent
      else (
        'the exact upstream state/entropy equation and strict moving/global '
        'front correction completed with independent replays, but the '
        'component-wise combined residual gate remains open; no canonical or '
        'production claim is made'
      )
    ),
    **common,
  )
####
