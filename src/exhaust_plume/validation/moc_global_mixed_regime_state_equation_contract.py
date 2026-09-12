"""Explicit admission contract for upstream mixed-regime state equations.

The downstream coupled-Euler lane can produce and consume a complete
conservative boundary state.  The current reflected global MOC lane still
accepts characteristic state plus pressure/geometry targets, so that packet
must not be silently cast into a ``CharacteristicState``.  This module binds
the exact state target frame and records the remaining equation-level blocker
as a typed, fail-closed handoff.

The result is deliberately useful before the future upstream solver exists:
it proves that the state packet is complete, lineaged, and frame-aligned,
while making it impossible to report it as consumed by the global equations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import isfinite
from types import MappingProxyType
from typing import Any

from exhaust_plume.models.moc.global_mixed_regime_state_consumer import (
  MocReflectedDomainGlobalMixedRegimeStateConsumerResult,
  build_reflected_domain_global_mixed_regime_conservative_boundary_state_frame,
)
from exhaust_plume.models.moc.global_physical_closure import (
  MocReflectedDomainGlobalPhysicalClosureResult,
  moc_reflected_domain_global_physical_closure_fingerprint,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_STATE_EQUATION_CONTRACT_OPERATOR_ID',
  'MocReflectedDomainGlobalMixedRegimeStateEquationContractStatus',
  'MocReflectedDomainGlobalMixedRegimeStateEquationContract',
  'prepare_reflected_domain_global_mixed_regime_state_equation_contract',
)


MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_STATE_EQUATION_CONTRACT_OPERATOR_ID = (
  'op.moc.reflected-domain.global-mixed-regime-state-equation-contract-v1'
)
_STATE_CHANNEL_NAMES = (
  'mass',
  'streamwise_momentum',
  'transverse_momentum',
  'energy',
  'entropy',
)


class MocReflectedDomainGlobalMixedRegimeStateEquationContractStatus(
  str,
  Enum,
):
  """Typed outcomes of upstream state-equation admission."""

  UPSTREAM_EQUATION_CONTRACT_UNAVAILABLE = (
    'upstream-global-conservative-state-equation-contract-unavailable'
  )
  INVALID_INPUT = 'invalid_input'
  CONSUMER_NOT_READY = (
    'upstream-global-state-equation-contract-consumer-not-ready'
  )
  LINEAGE_FAILURE = 'upstream-global-state-equation-contract-lineage-failure'
  STATE_FRAME_FAILURE = 'upstream-global-state-equation-contract-frame-failure'


def _empty_channels() -> MappingProxyType:
  return MappingProxyType({name: False for name in _STATE_CHANNEL_NAMES})


def _finite_state_profile(
  values: Any,
  name: str,
) -> tuple[tuple[float, float, float, float], ...]:
  profile = tuple(
    tuple(float(component) for component in state)
    for state in values
  )
  if any(
    len(state) != 4
    or any(not isfinite(component) for component in state)
    for state in profile
  ):
    raise ValueError(f'{name} must contain finite four-component states')
  return profile


def _ordered_stations(values: Any, name: str) -> tuple[float, ...]:
  stations = tuple(float(value) for value in values)
  if any(not isfinite(value) for value in stations):
    raise ValueError(f'{name} must contain finite stations')
  if any(
    second <= first
    for first, second in zip(stations, stations[1:])
  ):
    raise ValueError(f'{name} must be strictly ordered')
  return stations


def _ordered_points(
  values: Any,
  name: str,
) -> tuple[tuple[float, float], ...]:
  points = tuple(
    tuple(float(coordinate) for coordinate in point)
    for point in values
  )
  if any(
    len(point) != 2 or any(not isfinite(value) for value in point)
    for point in points
  ):
    raise ValueError(f'{name} must contain finite 2-D points')
  if any(
    second[0] <= first[0]
    for first, second in zip(points, points[1:])
  ):
    raise ValueError(f'{name} must be strictly ordered in x')
  return points


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeStateEquationContract:
  """A complete state handoff that the current upstream MOC lane rejects."""

  status: MocReflectedDomainGlobalMixedRegimeStateEquationContractStatus
  closure: MocReflectedDomainGlobalPhysicalClosureResult | None
  consumer: MocReflectedDomainGlobalMixedRegimeStateConsumerResult | None
  source_closure_fingerprint: str | None = None
  conservative_state_profile: tuple[tuple[float, float, float, float], ...] = ()
  conservative_state_profile_x_stations_m: tuple[float, ...] = ()
  conservative_state_profile_points_m: tuple[tuple[float, float], ...] = ()
  available_channels: MappingProxyType = field(default_factory=_empty_channels)
  consumed_channels: MappingProxyType = field(default_factory=_empty_channels)
  closure_lineage_verified: bool = False
  state_target_frame_verified: bool = False
  state_target_ready: bool = False
  upstream_equation_contract_available: bool = False
  upstream_equation_consumed: bool = False
  global_coupling_verified: bool = False
  canonical_free_boundary_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalMixedRegimeStateEquationContractStatus,
    ):
      raise TypeError('status must be a typed state-equation contract status')
    ####
    if self.closure is not None and not isinstance(
      self.closure,
      MocReflectedDomainGlobalPhysicalClosureResult,
    ):
      raise TypeError('closure must be a typed global physical closure or None')
    ####
    if self.consumer is not None and not isinstance(
      self.consumer,
      MocReflectedDomainGlobalMixedRegimeStateConsumerResult,
    ):
      raise TypeError('consumer must be a typed state consumer or None')
    ####
    profile = _finite_state_profile(
      self.conservative_state_profile,
      'conservative_state_profile',
    )
    stations = _ordered_stations(
      self.conservative_state_profile_x_stations_m,
      'conservative_state_profile_x_stations_m',
    )
    points = _ordered_points(
      self.conservative_state_profile_points_m,
      'conservative_state_profile_points_m',
    )
    if len(profile) != len(stations) or len(profile) != len(points):
      raise ValueError(
        'conservative state profile, station frame, and 2-D point frame must '
        'have equal lengths'
      )
    ####
    available = dict(self.available_channels)
    consumed = dict(self.consumed_channels)
    expected = set(_STATE_CHANNEL_NAMES)
    if set(available) != expected or set(consumed) != expected:
      raise ValueError(
        'available_channels and consumed_channels must expose every declared '
        'mass, momentum, energy, and entropy channel'
      )
    ####
    if any(
      not isinstance(value, bool)
      for value in (*available.values(), *consumed.values())
    ):
      raise TypeError('state-equation channel maps must contain bool values')
    ####
    for name in (
      'closure_lineage_verified',
      'state_target_frame_verified',
      'state_target_ready',
      'upstream_equation_contract_available',
      'upstream_equation_consumed',
      'global_coupling_verified',
      'canonical_free_boundary_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    ####
    if self.upstream_equation_consumed or any(consumed.values()):
      raise ValueError(
        'the current upstream state-equation contract cannot claim channel '
        'consumption'
      )
    ####
    if (
      self.global_coupling_verified
      or self.canonical_free_boundary_verified
      or not self.chain_promotion_blocked
      or self.production_claim_allowed
    ):
      raise ValueError(
        'upstream state-equation admission must remain research-only and '
        'promotion-blocked'
      )
    ####
    if self.state_target_ready and not (
      profile
      and len(profile) >= 1
      and points
      and self.closure_lineage_verified
      and self.state_target_frame_verified
      and all(available.values())
    ):
      raise ValueError(
        'state_target_ready requires exact lineage, frame, and channel coverage'
      )
    ####
    object.__setattr__(self, 'conservative_state_profile', profile)
    object.__setattr__(self, 'conservative_state_profile_x_stations_m', stations)
    object.__setattr__(self, 'conservative_state_profile_points_m', points)
    object.__setattr__(self, 'available_channels', MappingProxyType(available))
    object.__setattr__(self, 'consumed_channels', MappingProxyType(consumed))
    if self.source_closure_fingerprint is not None:
      object.__setattr__(
        self,
        'source_closure_fingerprint',
        str(self.source_closure_fingerprint),
      )
    object.__setattr__(self, 'message', str(self.message))
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': (
        MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_STATE_EQUATION_CONTRACT_OPERATOR_ID
      ),
      'status': self.status.value,
      'source_closure_fingerprint': self.source_closure_fingerprint,
      'conservative_state_profile': self.conservative_state_profile,
      'conservative_state_profile_x_stations_m': (
        self.conservative_state_profile_x_stations_m
      ),
      'conservative_state_profile_points_m': (
        self.conservative_state_profile_points_m
      ),
      'available_channels': dict(self.available_channels),
      'consumed_channels': dict(self.consumed_channels),
      'closure_lineage_verified': self.closure_lineage_verified,
      'state_target_frame_verified': self.state_target_frame_verified,
      'state_target_ready': self.state_target_ready,
      'upstream_equation_contract_available': (
        self.upstream_equation_contract_available
      ),
      'upstream_equation_consumed': self.upstream_equation_consumed,
      'global_coupling_verified': self.global_coupling_verified,
      'canonical_free_boundary_verified': self.canonical_free_boundary_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'message': self.message,
      'claim_status': (
        'research-only-conservative-state-handoff; current global MOC equations '
        'do not consume the packet; canonical coupling and production promotion '
        'remain blocked'
      ),
    }
  ####
####


def _failure(
  status: MocReflectedDomainGlobalMixedRegimeStateEquationContractStatus,
  message: str,
  *,
  closure: MocReflectedDomainGlobalPhysicalClosureResult | None = None,
  consumer: MocReflectedDomainGlobalMixedRegimeStateConsumerResult | None = None,
) -> MocReflectedDomainGlobalMixedRegimeStateEquationContract:
  return MocReflectedDomainGlobalMixedRegimeStateEquationContract(
    status=status,
    closure=closure,
    consumer=consumer,
    message=message,
  )


def prepare_reflected_domain_global_mixed_regime_state_equation_contract(
  closure: MocReflectedDomainGlobalPhysicalClosureResult,
  consumer: MocReflectedDomainGlobalMixedRegimeStateConsumerResult,
) -> MocReflectedDomainGlobalMixedRegimeStateEquationContract:
  """Bind an exact conservative target while refusing unsafe upstream casts."""

  if not isinstance(closure, MocReflectedDomainGlobalPhysicalClosureResult):
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateEquationContractStatus.INVALID_INPUT,
      'closure must be a MocReflectedDomainGlobalPhysicalClosureResult',
    )
  ####
  if not isinstance(
    consumer,
    MocReflectedDomainGlobalMixedRegimeStateConsumerResult,
  ):
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateEquationContractStatus.INVALID_INPUT,
      'consumer must be a '
      'MocReflectedDomainGlobalMixedRegimeStateConsumerResult',
      closure=closure,
    )
  ####
  fingerprint = moc_reflected_domain_global_physical_closure_fingerprint(closure)
  if not closure.converged or not closure.physical_closure_verified:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateEquationContractStatus.CONSUMER_NOT_READY,
      'upstream state-equation admission requires a locally verified global '
      'physical closure',
      closure=closure,
      consumer=consumer,
    )
  ####
  if not consumer.consumed_local_research_state:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateEquationContractStatus.CONSUMER_NOT_READY,
      'upstream state-equation admission requires a consumed local state packet',
      closure=closure,
      consumer=consumer,
    )
  ####
  if not (
    consumer.closure is closure
    and consumer.source_closure_fingerprint == fingerprint
    and consumer.closure_lineage_verified
  ):
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateEquationContractStatus.LINEAGE_FAILURE,
      'state packet does not retain the exact global closure identity',
      closure=closure,
      consumer=consumer,
    )
  ####
  if not all(
    (
      consumer.mass_channel_verified,
      consumer.streamwise_momentum_channel_verified,
      consumer.transverse_momentum_channel_verified,
      consumer.energy_channel_verified,
      consumer.entropy_channel_verified,
    )
  ):
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateEquationContractStatus.CONSUMER_NOT_READY,
      'state packet did not pass every mass, momentum, energy, and entropy '
      'channel audit',
      closure=closure,
      consumer=consumer,
    )
  ####
  try:
    profile, points = (
      build_reflected_domain_global_mixed_regime_conservative_boundary_state_frame(
        consumer
      )
    )
    profile = _finite_state_profile(profile, 'conservative state profile')
    points = _ordered_points(points, 'conservative state profile points')
    stations = tuple(point[0] for point in points)
    stations = _ordered_stations(stations, 'conservative state profile stations')
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateEquationContractStatus.STATE_FRAME_FAILURE,
      f'conservative state target frame could not be built: {error}',
      closure=closure,
      consumer=consumer,
    )
  ####
  if len(profile) < 1 or len(profile) != len(stations):
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateEquationContractStatus.STATE_FRAME_FAILURE,
      'conservative state target frame is empty or misaligned',
      closure=closure,
      consumer=consumer,
    )
  ####
  available = MappingProxyType({name: True for name in _STATE_CHANNEL_NAMES})
  consumed = _empty_channels()
  return MocReflectedDomainGlobalMixedRegimeStateEquationContract(
    status=(
      MocReflectedDomainGlobalMixedRegimeStateEquationContractStatus
      .UPSTREAM_EQUATION_CONTRACT_UNAVAILABLE
    ),
    closure=closure,
    consumer=consumer,
    source_closure_fingerprint=fingerprint,
    conservative_state_profile=profile,
    conservative_state_profile_x_stations_m=stations,
    conservative_state_profile_points_m=points,
    available_channels=available,
    consumed_channels=consumed,
    closure_lineage_verified=True,
    state_target_frame_verified=True,
    state_target_ready=True,
    upstream_equation_contract_available=False,
    upstream_equation_consumed=False,
    global_coupling_verified=False,
    canonical_free_boundary_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    message=(
      'exact conservative state target is ready with complete mass, momentum, '
      'energy, and entropy lineage, but the current characteristic global MOC '
      'solver has no conservative-state boundary equation; no cast, pressure '
      'projection, or global solve was used to claim consumption'
    ),
  )
