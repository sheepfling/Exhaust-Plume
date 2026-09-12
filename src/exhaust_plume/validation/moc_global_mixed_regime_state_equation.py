"""Research-only audit of the full mixed-regime state-equation handoff.

The downstream mixed-regime solver already accepts a four-component
conservative state profile and applies it through its Rusanov free-boundary
flux.  This module verifies that the profile was actually bound to the
solver-owned cell frame and records the resulting conservative state
residuals.  It does not reinterpret the packet as a pressure target and it
does not claim that the upstream global MOC equations have consumed it.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite, sqrt
from typing import Any

from exhaust_plume.models.moc.coupled_euler_free_boundary import (
  MocReflectedDomainCoupledEulerFreeBoundaryFluxMode,
)
from exhaust_plume.models.moc.global_mixed_regime_state_consumer import (
  MocReflectedDomainGlobalMixedRegimeStateConsumerResult,
  MocReflectedDomainGlobalMixedRegimeStateResolveResult,
  build_reflected_domain_global_mixed_regime_conservative_boundary_profile,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_STATE_EQUATION_AUDIT_OPERATOR_ID',
  'MocReflectedDomainGlobalMixedRegimeStateEquationAuditStatus',
  'MocReflectedDomainGlobalMixedRegimeStateEquationAudit',
  'measure_reflected_domain_global_mixed_regime_state_equations',
)


MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_STATE_EQUATION_AUDIT_OPERATOR_ID = (
  'op.moc.reflected-domain.global-mixed-regime-state-equation-audit-v1'
)
_STATE_COMPONENT_NAMES = (
  'density',
  'streamwise_momentum',
  'transverse_momentum',
  'total_energy',
)


class MocReflectedDomainGlobalMixedRegimeStateEquationAuditStatus(str, Enum):
  """Typed result of one full-state equation-consumption audit."""

  CONSUMED_RESEARCH_STATE_EQUATIONS = (
    'consumed-research-global-mixed-regime-state-equations'
  )
  INVALID_INPUT = 'invalid_input'
  CONSUMER_NOT_READY = 'global-mixed-regime-state-equation-consumer-not-ready'
  RESOLVE_NOT_READY = 'global-mixed-regime-state-equation-resolve-not-ready'
  FRAME_FAILURE = 'global-mixed-regime-state-equation-frame-failure'
  CONSUMPTION_FAILURE = 'global-mixed-regime-state-equation-consumption-failure'
####


def _as_state_profile(
  values: tuple[tuple[float, float, float, float], ...] | Any,
  name: str,
) -> tuple[tuple[float, float, float, float], ...]:
  profile = tuple(
    tuple(float(value) for value in state)
    for state in values
  )
  if any(
    len(state) != 4 or any(not isfinite(value) for value in state)
    for state in profile
  ):
    raise ValueError(f'{name} must contain finite four-component states')
  ####
  return profile
####


def _as_stations(values: tuple[float, ...] | Any, name: str) -> tuple[float, ...]:
  stations = tuple(float(value) for value in values)
  if any(not isfinite(value) for value in stations):
    raise ValueError(f'{name} must contain finite stations')
  ####
  if any(second <= first for first, second in zip(stations, stations[1:])):
    raise ValueError(f'{name} must be strictly ordered')
  ####
  return stations
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeStateEquationAudit:
  """Evidence that the complete conservative profile entered the equations."""

  status: MocReflectedDomainGlobalMixedRegimeStateEquationAuditStatus
  consumer: MocReflectedDomainGlobalMixedRegimeStateConsumerResult | None
  resolved: MocReflectedDomainGlobalMixedRegimeStateResolveResult | None
  target_profile: tuple[tuple[float, float, float, float], ...] = ()
  target_x_stations_m: tuple[float, ...] = ()
  produced_profile: tuple[tuple[float, float, float, float], ...] = ()
  produced_x_stations_m: tuple[float, ...] = ()
  signed_state_residuals: tuple[tuple[float, float, float, float], ...] = ()
  relative_state_residuals: tuple[tuple[float, float, float, float], ...] = ()
  maximum_absolute_residual_by_component: tuple[float, float, float, float] = ()
  maximum_relative_residual_by_component: tuple[float, float, float, float] = ()
  maximum_relative_state_residual_norm: float | None = None
  consumer_lineage_verified: bool = False
  target_frame_verified: bool = False
  target_profile_consumed: bool = False
  produced_frame_verified: bool = False
  state_equation_residuals_measured: bool = False
  density_equation_verified: bool = False
  streamwise_momentum_equation_verified: bool = False
  transverse_momentum_equation_verified: bool = False
  total_energy_equation_verified: bool = False
  full_state_equation_consumed: bool = False
  canonical_free_boundary_verified: bool = False
  global_coupling_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalMixedRegimeStateEquationAuditStatus,
    ):
      raise TypeError('status must be a typed state-equation audit status')
    ####
    if self.consumer is not None and not isinstance(
      self.consumer,
      MocReflectedDomainGlobalMixedRegimeStateConsumerResult,
    ):
      raise TypeError('consumer must be a typed mixed-regime consumer result')
    ####
    if self.resolved is not None and not isinstance(
      self.resolved,
      MocReflectedDomainGlobalMixedRegimeStateResolveResult,
    ):
      raise TypeError('resolved must be a typed mixed-regime resolve result')
    ####
    target_profile = _as_state_profile(self.target_profile, 'target_profile')
    produced_profile = _as_state_profile(
      self.produced_profile,
      'produced_profile',
    )
    target_stations = _as_stations(
      self.target_x_stations_m,
      'target_x_stations_m',
    )
    produced_stations = _as_stations(
      self.produced_x_stations_m,
      'produced_x_stations_m',
    )
    if len(target_profile) != len(target_stations):
      raise ValueError('target profile and stations must align')
    ####
    if len(produced_profile) != len(produced_stations):
      raise ValueError('produced profile and stations must align')
    ####
    signed = tuple(
      tuple(float(value) for value in residual)
      for residual in self.signed_state_residuals
    )
    relative = tuple(
      tuple(float(value) for value in residual)
      for residual in self.relative_state_residuals
    )
    if any(
      len(residual) != 4 or any(not isfinite(value) for value in residual)
      for residual in (*signed, *relative)
    ):
      raise ValueError('state residuals must contain finite four-tuples')
    ####
    if len(signed) != len(relative):
      raise ValueError('signed and relative state residuals must align')
    ####
    object.__setattr__(self, 'target_profile', target_profile)
    object.__setattr__(self, 'produced_profile', produced_profile)
    object.__setattr__(self, 'target_x_stations_m', target_stations)
    object.__setattr__(self, 'produced_x_stations_m', produced_stations)
    object.__setattr__(self, 'signed_state_residuals', signed)
    object.__setattr__(self, 'relative_state_residuals', relative)
    for name in (
      'maximum_absolute_residual_by_component',
      'maximum_relative_residual_by_component',
    ):
      values = tuple(float(value) for value in getattr(self, name))
      if len(values) not in (0, 4) or any(
        not isfinite(value) or value < 0.0 for value in values
      ):
        raise ValueError(f'{name} must be empty or contain four finite values')
      ####
      object.__setattr__(self, name, values)
    ####
    if self.maximum_relative_state_residual_norm is not None:
      norm = float(self.maximum_relative_state_residual_norm)
      if not isfinite(norm) or norm < 0.0:
        raise ValueError(
          'maximum_relative_state_residual_norm must be finite and nonnegative'
        )
      ####
      object.__setattr__(self, 'maximum_relative_state_residual_norm', norm)
    ####
    for name in (
      'consumer_lineage_verified',
      'target_frame_verified',
      'target_profile_consumed',
      'produced_frame_verified',
      'state_equation_residuals_measured',
      'density_equation_verified',
      'streamwise_momentum_equation_verified',
      'transverse_momentum_equation_verified',
      'total_energy_equation_verified',
      'full_state_equation_consumed',
      'canonical_free_boundary_verified',
      'global_coupling_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if self.canonical_free_boundary_verified or self.global_coupling_verified:
      raise ValueError('state-equation audit cannot claim global closure')
    ####
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError('state-equation audit must remain promotion-blocked')
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def component_names(self) -> tuple[str, ...]:
    return _STATE_COMPONENT_NAMES
  ####

  @property
  def research_state_equation_consumed(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalMixedRegimeStateEquationAuditStatus
      .CONSUMED_RESEARCH_STATE_EQUATIONS
      and self.consumer_lineage_verified
      and self.target_frame_verified
      and self.target_profile_consumed
      and self.produced_frame_verified
      and self.state_equation_residuals_measured
      and self.density_equation_verified
      and self.streamwise_momentum_equation_verified
      and self.transverse_momentum_equation_verified
      and self.total_energy_equation_verified
      and self.full_state_equation_consumed
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': (
        MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_STATE_EQUATION_AUDIT_OPERATOR_ID
      ),
      'status': self.status.value,
      'research_state_equation_consumed': self.research_state_equation_consumed,
      'component_names': self.component_names,
      'target_profile': self.target_profile,
      'target_x_stations_m': self.target_x_stations_m,
      'produced_profile': self.produced_profile,
      'produced_x_stations_m': self.produced_x_stations_m,
      'signed_state_residuals': self.signed_state_residuals,
      'relative_state_residuals': self.relative_state_residuals,
      'maximum_absolute_residual_by_component': (
        self.maximum_absolute_residual_by_component
      ),
      'maximum_relative_residual_by_component': (
        self.maximum_relative_residual_by_component
      ),
      'maximum_relative_state_residual_norm': (
        self.maximum_relative_state_residual_norm
      ),
      'consumer_lineage_verified': self.consumer_lineage_verified,
      'target_frame_verified': self.target_frame_verified,
      'target_profile_consumed': self.target_profile_consumed,
      'produced_frame_verified': self.produced_frame_verified,
      'state_equation_residuals_measured': self.state_equation_residuals_measured,
      'state_equation_channels': {
        'density': self.density_equation_verified,
        'streamwise_momentum': self.streamwise_momentum_equation_verified,
        'transverse_momentum': self.transverse_momentum_equation_verified,
        'total_energy': self.total_energy_equation_verified,
      },
      'full_state_equation_consumed': self.full_state_equation_consumed,
      'canonical_free_boundary_verified': False,
      'global_coupling_verified': False,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'message': self.message,
    }
  ####
####


def _failure(
  status: MocReflectedDomainGlobalMixedRegimeStateEquationAuditStatus,
  message: str,
  *,
  consumer: MocReflectedDomainGlobalMixedRegimeStateConsumerResult | None = None,
  resolved: MocReflectedDomainGlobalMixedRegimeStateResolveResult | None = None,
  **kwargs: Any,
) -> MocReflectedDomainGlobalMixedRegimeStateEquationAudit:
  return MocReflectedDomainGlobalMixedRegimeStateEquationAudit(
    status=status,
    consumer=consumer,
    resolved=resolved,
    message=message,
    **kwargs,
  )
####


def _frame_matches(
  target: tuple[float, ...],
  produced: tuple[float, ...],
) -> bool:
  return bool(
    len(target) == len(produced)
    and all(
      abs(actual - expected) <= 1.0e-8 * max(1.0, abs(expected), abs(actual))
      for expected, actual in zip(target, produced, strict=True)
    )
  )
####


def measure_reflected_domain_global_mixed_regime_state_equations(
  consumer: MocReflectedDomainGlobalMixedRegimeStateConsumerResult,
  resolved: MocReflectedDomainGlobalMixedRegimeStateResolveResult,
) -> MocReflectedDomainGlobalMixedRegimeStateEquationAudit:
  """Verify actual four-component state-equation consumption downstream.

  The produced profile is the top-row conservative state in the fresh coupled
  Euler field.  It is compared directly with the exact trace-derived target
  profile in the same cell-column frame.  No interpolation, pressure-only
  projection, or upstream global feedback is performed here.
  """

  if not isinstance(
    consumer,
    MocReflectedDomainGlobalMixedRegimeStateConsumerResult,
  ) or not isinstance(
    resolved,
    MocReflectedDomainGlobalMixedRegimeStateResolveResult,
  ):
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateEquationAuditStatus.INVALID_INPUT,
      'consumer and resolved must be their typed mixed-regime results',
      consumer=consumer if isinstance(
        consumer,
        MocReflectedDomainGlobalMixedRegimeStateConsumerResult,
      ) else None,
      resolved=resolved if isinstance(
        resolved,
        MocReflectedDomainGlobalMixedRegimeStateResolveResult,
      ) else None,
    )
  ####
  if not consumer.consumed_local_research_state:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateEquationAuditStatus.CONSUMER_NOT_READY,
      'state-equation audit requires a locally consumed full-state trace',
      consumer=consumer,
      resolved=resolved,
    )
  ####
  if not resolved.fresh_local_research_state_resolve_verified:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateEquationAuditStatus.RESOLVE_NOT_READY,
      'state-equation audit requires a converged fresh downstream state resolve',
      consumer=consumer,
      resolved=resolved,
    )
  ####
  if resolved.consumer is not consumer:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateEquationAuditStatus.CONSUMPTION_FAILURE,
      'resolved state solve does not retain the exact consumer object',
      consumer=consumer,
      resolved=resolved,
      consumer_lineage_verified=False,
    )
  ####
  request = resolved.request
  field = resolved.field
  if request is None or field is None:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateEquationAuditStatus.RESOLVE_NOT_READY,
      'resolved state solve retained no request and field pair',
      consumer=consumer,
      resolved=resolved,
      consumer_lineage_verified=True,
    )
  ####
  try:
    expected_profile, expected_stations = (
      build_reflected_domain_global_mixed_regime_conservative_boundary_profile(
        consumer
      )
    )
    target_profile = _as_state_profile(
      resolved.conservative_state_profile,
      'resolved.conservative_state_profile',
    )
    target_stations = _as_stations(
      resolved.conservative_state_profile_x_stations_m,
      'resolved.conservative_state_profile_x_stations_m',
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateEquationAuditStatus.CONSUMPTION_FAILURE,
      f'full-state target profile reconstruction failed: {error}',
      consumer=consumer,
      resolved=resolved,
      consumer_lineage_verified=True,
    )
  ####
  target_frame_verified = bool(
    target_profile == expected_profile
    and target_stations == expected_stations
    and resolved.profile_frame_verified
  )
  if not target_frame_verified:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateEquationAuditStatus.FRAME_FAILURE,
      'resolved full-state target profile does not exactly match the trace-derived frame',
      consumer=consumer,
      resolved=resolved,
      target_profile=target_profile,
      target_x_stations_m=target_stations,
      consumer_lineage_verified=True,
      target_frame_verified=False,
    )
  ####
  axial_count = request.axial_cell_count
  transverse_count = request.transverse_cell_count
  expected_cell_count = axial_count * transverse_count
  if len(field.conservative_states_by_cell) != expected_cell_count:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateEquationAuditStatus.FRAME_FAILURE,
      'fresh state field does not retain one conservative state per cell',
      consumer=consumer,
      resolved=resolved,
      target_profile=target_profile,
      target_x_stations_m=target_stations,
      consumer_lineage_verified=True,
      target_frame_verified=True,
    )
  ####
  produced_profile = tuple(
    tuple(
      float(value)
      for value in field.conservative_states_by_cell[
        axial_index * transverse_count + transverse_count - 1
      ]
    )
    for axial_index in range(axial_count)
  )
  produced_stations = tuple(
    float(
      field.cell_centers_m[
        axial_index * transverse_count + transverse_count - 1
      ][0]
    )
    for axial_index in range(axial_count)
  )
  produced_frame_verified = _frame_matches(target_stations, produced_stations)
  if not produced_frame_verified:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateEquationAuditStatus.FRAME_FAILURE,
      'fresh coupled field top-row cell centers do not match the target state frame',
      consumer=consumer,
      resolved=resolved,
      target_profile=target_profile,
      target_x_stations_m=target_stations,
      produced_profile=produced_profile,
      produced_x_stations_m=produced_stations,
      consumer_lineage_verified=True,
      target_frame_verified=True,
      target_profile_consumed=False,
      produced_frame_verified=False,
    )
  ####
  signed = tuple(
    tuple(
      actual - target
      for actual, target in zip(produced, expected, strict=True)
    )
    for produced, expected in zip(produced_profile, target_profile, strict=True)
  )
  relative = tuple(
    tuple(
      residual / max(abs(target), 1.0e-12)
      for residual, target in zip(signed_residual, target, strict=True)
    )
    for signed_residual, target in zip(signed, target_profile, strict=True)
  )
  maximum_absolute = tuple(
    max((abs(residual[index]) for residual in signed), default=0.0)
    for index in range(4)
  )
  maximum_relative = tuple(
    max((abs(residual[index]) for residual in relative), default=0.0)
    for index in range(4)
  )
  maximum_norm = max(
    (
      sqrt(sum(value * value for value in residual) / 4.0)
      for residual in relative
    ),
    default=0.0,
  )
  residuals_measured = bool(
    len(signed) == len(target_profile) == axial_count
    and all(isfinite(value) for residual in signed for value in residual)
    and all(isfinite(value) for residual in relative for value in residual)
  )
  target_consumed = bool(
    request.free_boundary_flux_mode
    is MocReflectedDomainCoupledEulerFreeBoundaryFluxMode
    .CONSERVATIVE_STATE_TRACE_RUSANOV
    and request.free_boundary_conservative_state_profile == target_profile
    and request.free_boundary_conservative_state_profile_x_stations_m
    == target_stations
    and field.request is request
    and field.free_boundary_conservative_state_profile_consumed
    and resolved.fresh_field_lineage_verified
  )
  channel_verified = tuple(
    bool(residuals_measured and all(isfinite(value[index]) for value in relative))
    for index in range(4)
  )
  full_state_consumed = bool(
    consumer.closure_lineage_verified
    and resolved.consumer_lineage_verified
    and target_frame_verified
    and target_consumed
    and produced_frame_verified
    and residuals_measured
    and all(channel_verified)
  )
  status = (
    MocReflectedDomainGlobalMixedRegimeStateEquationAuditStatus
    .CONSUMED_RESEARCH_STATE_EQUATIONS
    if full_state_consumed
    else MocReflectedDomainGlobalMixedRegimeStateEquationAuditStatus
    .CONSUMPTION_FAILURE
  )
  return MocReflectedDomainGlobalMixedRegimeStateEquationAudit(
    status=status,
    consumer=consumer,
    resolved=resolved,
    target_profile=target_profile,
    target_x_stations_m=target_stations,
    produced_profile=produced_profile,
    produced_x_stations_m=produced_stations,
    signed_state_residuals=signed,
    relative_state_residuals=relative,
    maximum_absolute_residual_by_component=maximum_absolute,
    maximum_relative_residual_by_component=maximum_relative,
    maximum_relative_state_residual_norm=maximum_norm,
    consumer_lineage_verified=bool(
      consumer.closure_lineage_verified and resolved.consumer_lineage_verified
    ),
    target_frame_verified=target_frame_verified,
    target_profile_consumed=target_consumed,
    produced_frame_verified=produced_frame_verified,
    state_equation_residuals_measured=residuals_measured,
    density_equation_verified=channel_verified[0],
    streamwise_momentum_equation_verified=channel_verified[1],
    transverse_momentum_equation_verified=channel_verified[2],
    total_energy_equation_verified=channel_verified[3],
    full_state_equation_consumed=full_state_consumed,
    message=(
      'fresh coupled Euler equations consumed the exact four-component trace '
      'profile through the conservative Rusanov boundary flux; residuals are '
      'reported for research comparison and upstream global coupling remains open'
      if full_state_consumed
      else 'full-state profile was available, but exact equation-consumption '
      'lineage or one of its four conservative channels did not pass'
    ),
  )
####
