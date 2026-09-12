"""Dimensional research probe for the future upstream state equation.

The reflected global MOC field currently exposes ``CharacteristicState`` and
total pressure, while the downstream mixed-regime trace exposes dimensional
conservative states.  This module makes the missing dimensional bridge
explicit: it samples the exact retained 2-D target frame and reconstructs a
conservative state only after the caller supplies the thermodynamic reference
values.

The result is a residual measurement, not upstream equation consumption.  It
does not cast a conservative state into ``CharacteristicState``, feed a
pressure-only target back into the global solver, or claim that the entropy
channel has been consumed.  Those remain requirements for the next solver
owned equation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import cos, isfinite, log, sin, sqrt
from typing import Any

from exhaust_plume.models.moc.primitives import CharacteristicState
from exhaust_plume.validation.moc_global_mixed_regime_state_equation_contract import (
  MocReflectedDomainGlobalMixedRegimeStateEquationContract,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_UPSTREAM_STATE_TARGET_OPERATOR_ID',
  'MocReflectedDomainGlobalMixedRegimeUpstreamStateTargetStatus',
  'MocReflectedDomainGlobalMixedRegimeUpstreamStateTargetRequest',
  'MocReflectedDomainGlobalMixedRegimeConservativeStateSample',
  'MocReflectedDomainGlobalMixedRegimeUpstreamStateTargetResult',
  'measure_reflected_domain_global_mixed_regime_upstream_state_target',
)


MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_UPSTREAM_STATE_TARGET_OPERATOR_ID = (
  'op.moc.reflected-domain.global-mixed-regime-upstream-state-target-v1'
)


class MocReflectedDomainGlobalMixedRegimeUpstreamStateTargetStatus(str, Enum):
  """Typed outcome of one dimensional state-target residual measurement."""

  MEASURED_LOCAL_RESEARCH_RESIDUALS = (
    'measured-local-global-mixed-regime-upstream-state-target-residuals'
  )
  INVALID_INPUT = 'invalid_input'
  CONTRACT_NOT_READY = 'upstream-state-target-contract-not-ready'
  FIELD_NOT_READY = 'upstream-state-target-global-field-not-ready'
  FRAME_FAILURE = 'upstream-state-target-frame-failure'
  TARGET_STATE_FAILURE = 'upstream-state-target-target-state-failure'
  SAMPLE_FAILURE = 'upstream-state-target-global-field-sample-failure'


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeUpstreamStateTargetRequest:
  """Explicit dimensionalization and residual-measurement parameters."""

  reference_total_temperature_K: float
  target_gamma: float
  gas_constant_J_kgK: float = 287.05
  position_tolerance_m: float = 1.0e-8
  residual_floor: float = 1.0e-12

  def __post_init__(self) -> None:
    for name in (
      'reference_total_temperature_K',
      'target_gamma',
      'gas_constant_J_kgK',
      'position_tolerance_m',
      'residual_floor',
    ):
      value = float(getattr(self, name))
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      object.__setattr__(self, name, value)
    if self.target_gamma <= 1.0:
      raise ValueError('target_gamma must be greater than one')

  def as_report(self) -> dict[str, Any]:
    return {
      'reference_total_temperature_K': self.reference_total_temperature_K,
      'target_gamma': self.target_gamma,
      'gas_constant_J_kgK': self.gas_constant_J_kgK,
      'position_tolerance_m': self.position_tolerance_m,
      'residual_floor': self.residual_floor,
    }


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeConservativeStateSample:
  """One dimensionalized global-field state at an exact target point."""

  point_m: tuple[float, float]
  characteristic_state: CharacteristicState
  total_pressure_Pa: float
  static_pressure_Pa: float
  static_temperature_K: float
  density_kg_m3: float
  velocity_u_m_s: float
  velocity_v_m_s: float
  mach: float
  entropy_proxy: float
  conservative_state: tuple[float, float, float, float]

  def __post_init__(self) -> None:
    point = tuple(float(value) for value in self.point_m)
    if len(point) != 2 or any(not isfinite(value) for value in point):
      raise ValueError('point_m must contain two finite coordinates')
    if not isinstance(self.characteristic_state, CharacteristicState):
      raise TypeError('characteristic_state must be a CharacteristicState')
    object.__setattr__(self, 'point_m', point)
    for name in (
      'total_pressure_Pa',
      'static_pressure_Pa',
      'static_temperature_K',
      'density_kg_m3',
      'entropy_proxy',
    ):
      value = float(getattr(self, name))
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      object.__setattr__(self, name, value)
    for name in ('velocity_u_m_s', 'velocity_v_m_s', 'mach'):
      value = float(getattr(self, name))
      if not isfinite(value) or (name == 'mach' and value <= 1.0):
        raise ValueError(f'{name} must be finite and valid')
      object.__setattr__(self, name, value)
    conservative = tuple(float(value) for value in self.conservative_state)
    if len(conservative) != 4 or any(not isfinite(value) for value in conservative):
      raise ValueError('conservative_state must contain four finite values')
    if conservative[0] <= 0.0 or conservative[3] <= 0.0:
      raise ValueError('conservative_state density and energy must be positive')
    object.__setattr__(self, 'conservative_state', conservative)

  def as_report(self) -> dict[str, Any]:
    return {
      'point_m': self.point_m,
      'characteristic_state': {
        'x_m': self.characteristic_state.x_m,
        'y_m': self.characteristic_state.y_m,
        'theta_rad': self.characteristic_state.theta_rad,
        'mach': self.characteristic_state.mach,
        'gamma': self.characteristic_state.gamma,
      },
      'total_pressure_Pa': self.total_pressure_Pa,
      'static_pressure_Pa': self.static_pressure_Pa,
      'static_temperature_K': self.static_temperature_K,
      'density_kg_m3': self.density_kg_m3,
      'velocity_u_m_s': self.velocity_u_m_s,
      'velocity_v_m_s': self.velocity_v_m_s,
      'mach': self.mach,
      'entropy_proxy': self.entropy_proxy,
      'conservative_state': self.conservative_state,
    }


def _state_profile(
  values: Any,
  name: str,
) -> tuple[tuple[float, float, float, float], ...]:
  profile = tuple(
    tuple(float(component) for component in state)
    for state in values
  )
  if any(
    len(state) != 4 or any(not isfinite(value) for value in state)
    for state in profile
  ):
    raise ValueError(f'{name} must contain finite four-component states')
  return profile


def _points(
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


def _entropy_profile(values: Any, name: str) -> tuple[float, ...]:
  profile = tuple(float(value) for value in values)
  if any(not isfinite(value) or value <= 0.0 for value in profile):
    raise ValueError(f'{name} must contain finite positive values')
  return profile


def _conservative_from_characteristic(
  state: CharacteristicState,
  total_pressure_Pa: float,
  request: MocReflectedDomainGlobalMixedRegimeUpstreamStateTargetRequest,
) -> MocReflectedDomainGlobalMixedRegimeConservativeStateSample:
  gamma = float(state.gamma)
  mach = float(state.mach)
  factor = 1.0 + 0.5 * (gamma - 1.0) * mach * mach
  static_pressure = total_pressure_Pa / factor ** (gamma / (gamma - 1.0))
  static_temperature = request.reference_total_temperature_K / factor
  density = static_pressure / (
    request.gas_constant_J_kgK * static_temperature
  )
  sound_speed = sqrt(
    gamma * request.gas_constant_J_kgK * static_temperature
  )
  speed = mach * sound_speed
  velocity_u = speed * cos(state.theta_rad)
  velocity_v = speed * sin(state.theta_rad)
  total_energy = (
    static_pressure / (gamma - 1.0)
    + 0.5 * density * (velocity_u * velocity_u + velocity_v * velocity_v)
  )
  conservative = (density, density * velocity_u, density * velocity_v, total_energy)
  entropy_proxy = static_pressure / density ** gamma
  return MocReflectedDomainGlobalMixedRegimeConservativeStateSample(
    point_m=(state.x_m, state.y_m),
    characteristic_state=state,
    total_pressure_Pa=total_pressure_Pa,
    static_pressure_Pa=static_pressure,
    static_temperature_K=static_temperature,
    density_kg_m3=density,
    velocity_u_m_s=velocity_u,
    velocity_v_m_s=velocity_v,
    mach=mach,
    entropy_proxy=entropy_proxy,
    conservative_state=conservative,
  )


def _validate_target_state(
  state: tuple[float, float, float, float],
  gamma: float,
  gas_constant: float,
  residual_floor: float,
) -> None:
  density, momentum_x, momentum_y, total_energy = state
  if density <= 0.0 or total_energy <= 0.0:
    raise ValueError('target conservative density and energy must be positive')
  velocity_u = momentum_x / density
  velocity_v = momentum_y / density
  static_pressure = (gamma - 1.0) * (
    total_energy
    - 0.5 * density * (velocity_u * velocity_u + velocity_v * velocity_v)
  )
  if not isfinite(static_pressure) or static_pressure <= residual_floor:
    raise ValueError('target conservative state must have positive pressure')
  static_temperature = static_pressure / (density * gas_constant)
  if not isfinite(static_temperature) or static_temperature <= residual_floor:
    raise ValueError('target conservative state must have positive temperature')


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeUpstreamStateTargetResult:
  """Research residual evidence with upstream consumption hard-disabled."""

  status: MocReflectedDomainGlobalMixedRegimeUpstreamStateTargetStatus
  contract: MocReflectedDomainGlobalMixedRegimeStateEquationContract | None
  request: MocReflectedDomainGlobalMixedRegimeUpstreamStateTargetRequest | None
  target_profile: tuple[tuple[float, float, float, float], ...] = ()
  target_points_m: tuple[tuple[float, float], ...] = ()
  target_entropy_proxy_profile: tuple[float, ...] = ()
  sampled_states: tuple[MocReflectedDomainGlobalMixedRegimeConservativeStateSample, ...] = ()
  sampled_profile: tuple[tuple[float, float, float, float], ...] = ()
  sampled_entropy_proxy_profile: tuple[float, ...] = ()
  signed_state_residuals: tuple[tuple[float, float, float, float], ...] = ()
  relative_state_residuals: tuple[tuple[float, float, float, float], ...] = ()
  signed_entropy_log_residuals: tuple[float, ...] = ()
  maximum_absolute_residual_by_component: tuple[float, float, float, float] = ()
  maximum_relative_residual_by_component: tuple[float, float, float, float] = ()
  maximum_absolute_entropy_log_residual: float | None = None
  target_frame_verified: bool = False
  dimensionalization_verified: bool = False
  global_field_sampling_verified: bool = False
  state_target_residuals_measured: bool = False
  entropy_proxy_residuals_measured: bool = False
  entropy_channel_available: bool = False
  entropy_channel_consumed: bool = False
  upstream_equation_consumed: bool = False
  global_coupling_verified: bool = False
  canonical_free_boundary_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalMixedRegimeUpstreamStateTargetStatus,
    ):
      raise TypeError('status must be a typed upstream state-target status')
    if self.contract is not None and not isinstance(
      self.contract,
      MocReflectedDomainGlobalMixedRegimeStateEquationContract,
    ):
      raise TypeError('contract must be a typed state-equation contract or None')
    if self.request is not None and not isinstance(
      self.request,
      MocReflectedDomainGlobalMixedRegimeUpstreamStateTargetRequest,
    ):
      raise TypeError('request must be a typed state-target request or None')
    target_profile = _state_profile(self.target_profile, 'target_profile')
    target_points = _points(self.target_points_m, 'target_points_m')
    target_entropy = _entropy_profile(
      self.target_entropy_proxy_profile,
      'target_entropy_proxy_profile',
    )
    sampled_profile = _state_profile(self.sampled_profile, 'sampled_profile')
    sampled_entropy = _entropy_profile(
      self.sampled_entropy_proxy_profile,
      'sampled_entropy_proxy_profile',
    )
    sampled_states = tuple(self.sampled_states)
    if any(
      not isinstance(
        sample,
        MocReflectedDomainGlobalMixedRegimeConservativeStateSample,
      )
      for sample in sampled_states
    ):
      raise TypeError('sampled_states must contain typed state samples')
    if len(target_profile) != len(target_points):
      raise ValueError('target profile and points must align')
    if len(target_profile) != len(target_entropy):
      raise ValueError('target profile and entropy profile must align')
    if len(sampled_profile) != len(sampled_states):
      raise ValueError('sampled profile and sampled states must align')
    if len(sampled_profile) != len(sampled_entropy):
      raise ValueError('sampled profile and sampled entropy must align')
    for name in (
      'signed_state_residuals',
      'relative_state_residuals',
    ):
      residuals = tuple(
        tuple(float(value) for value in residual)
        for residual in getattr(self, name)
      )
      if any(
        len(residual) != 4 or any(not isfinite(value) for value in residual)
        for residual in residuals
      ):
        raise ValueError(f'{name} must contain finite four-component residuals')
      object.__setattr__(self, name, residuals)
    for name in (
      'maximum_absolute_residual_by_component',
      'maximum_relative_residual_by_component',
    ):
      values = tuple(float(value) for value in getattr(self, name))
      if len(values) not in (0, 4) or any(
        not isfinite(value) or value < 0.0 for value in values
      ):
        raise ValueError(f'{name} must contain zero or four finite nonnegative values')
      object.__setattr__(self, name, values)
    entropy_logs = tuple(float(value) for value in self.signed_entropy_log_residuals)
    if any(not isfinite(value) for value in entropy_logs):
      raise ValueError('signed_entropy_log_residuals must be finite')
    if len(entropy_logs) not in (0, len(target_profile)):
      raise ValueError('signed_entropy_log_residuals must align with target profile')
    object.__setattr__(self, 'signed_entropy_log_residuals', entropy_logs)
    if self.maximum_absolute_entropy_log_residual is not None:
      maximum_entropy = float(self.maximum_absolute_entropy_log_residual)
      if not isfinite(maximum_entropy) or maximum_entropy < 0.0:
        raise ValueError(
          'maximum_absolute_entropy_log_residual must be finite and nonnegative'
        )
      object.__setattr__(self, 'maximum_absolute_entropy_log_residual', maximum_entropy)
    for name in (
      'target_frame_verified',
      'dimensionalization_verified',
      'global_field_sampling_verified',
      'state_target_residuals_measured',
      'entropy_proxy_residuals_measured',
      'entropy_channel_available',
      'entropy_channel_consumed',
      'upstream_equation_consumed',
      'global_coupling_verified',
      'canonical_free_boundary_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    if self.entropy_channel_consumed or self.upstream_equation_consumed:
      raise ValueError(
        'the dimensional state-target probe cannot claim entropy or upstream '
        'equation consumption'
      )
    if self.global_coupling_verified or self.canonical_free_boundary_verified:
      raise ValueError('the dimensional state-target probe cannot claim global coupling')
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError('the dimensional state-target probe must remain promotion-blocked')
    object.__setattr__(self, 'target_profile', target_profile)
    object.__setattr__(self, 'target_points_m', target_points)
    object.__setattr__(self, 'target_entropy_proxy_profile', target_entropy)
    object.__setattr__(self, 'sampled_states', sampled_states)
    object.__setattr__(self, 'sampled_profile', sampled_profile)
    object.__setattr__(self, 'sampled_entropy_proxy_profile', sampled_entropy)
    object.__setattr__(self, 'message', str(self.message))

  @property
  def local_research_residuals_verified(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalMixedRegimeUpstreamStateTargetStatus
      .MEASURED_LOCAL_RESEARCH_RESIDUALS
      and self.target_frame_verified
      and self.dimensionalization_verified
      and self.global_field_sampling_verified
      and self.state_target_residuals_measured
      and self.entropy_proxy_residuals_measured
      and len(self.target_profile) == len(self.sampled_profile)
      and len(self.target_profile) > 0
      and all(len(residual) == 4 for residual in self.signed_state_residuals)
    )

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': (
        MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_UPSTREAM_STATE_TARGET_OPERATOR_ID
      ),
      'status': self.status.value,
      'local_research_residuals_verified': self.local_research_residuals_verified,
      'target_profile': self.target_profile,
      'target_points_m': self.target_points_m,
      'target_entropy_proxy_profile': self.target_entropy_proxy_profile,
      'sampled_states': [sample.as_report() for sample in self.sampled_states],
      'sampled_profile': self.sampled_profile,
      'sampled_entropy_proxy_profile': self.sampled_entropy_proxy_profile,
      'signed_state_residuals': self.signed_state_residuals,
      'relative_state_residuals': self.relative_state_residuals,
      'signed_entropy_log_residuals': self.signed_entropy_log_residuals,
      'maximum_absolute_residual_by_component': (
        self.maximum_absolute_residual_by_component
      ),
      'maximum_relative_residual_by_component': (
        self.maximum_relative_residual_by_component
      ),
      'maximum_absolute_entropy_log_residual': (
        self.maximum_absolute_entropy_log_residual
      ),
      'target_frame_verified': self.target_frame_verified,
      'dimensionalization_verified': self.dimensionalization_verified,
      'global_field_sampling_verified': self.global_field_sampling_verified,
      'state_target_residuals_measured': self.state_target_residuals_measured,
      'entropy_proxy_residuals_measured': self.entropy_proxy_residuals_measured,
      'entropy_channel_available': self.entropy_channel_available,
      'entropy_channel_consumed': False,
      'upstream_equation_consumed': False,
      'global_coupling_verified': False,
      'canonical_free_boundary_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'request': None if self.request is None else self.request.as_report(),
      'message': self.message,
    }


def _failure(
  status: MocReflectedDomainGlobalMixedRegimeUpstreamStateTargetStatus,
  message: str,
  *,
  contract: MocReflectedDomainGlobalMixedRegimeStateEquationContract | None = None,
  request: MocReflectedDomainGlobalMixedRegimeUpstreamStateTargetRequest | None = None,
  target_profile: tuple[tuple[float, float, float, float], ...] = (),
  target_points: tuple[tuple[float, float], ...] = (),
  target_entropy: tuple[float, ...] = (),
) -> MocReflectedDomainGlobalMixedRegimeUpstreamStateTargetResult:
  return MocReflectedDomainGlobalMixedRegimeUpstreamStateTargetResult(
    status=status,
    contract=contract,
    request=request,
    target_profile=target_profile,
    target_points_m=target_points,
    target_entropy_proxy_profile=target_entropy,
    message=message,
  )


def measure_reflected_domain_global_mixed_regime_upstream_state_target(
  contract: MocReflectedDomainGlobalMixedRegimeStateEquationContract,
  request: MocReflectedDomainGlobalMixedRegimeUpstreamStateTargetRequest,
) -> MocReflectedDomainGlobalMixedRegimeUpstreamStateTargetResult:
  """Measure exact-frame state residuals without claiming upstream coupling."""

  if not isinstance(
    contract,
    MocReflectedDomainGlobalMixedRegimeStateEquationContract,
  ):
    return _failure(
      MocReflectedDomainGlobalMixedRegimeUpstreamStateTargetStatus.INVALID_INPUT,
      'contract must be a '
      'MocReflectedDomainGlobalMixedRegimeStateEquationContract',
    )
  if not isinstance(
    request,
    MocReflectedDomainGlobalMixedRegimeUpstreamStateTargetRequest,
  ):
    return _failure(
      MocReflectedDomainGlobalMixedRegimeUpstreamStateTargetStatus.INVALID_INPUT,
      'request must be a typed upstream state-target request',
      contract=contract,
    )
  if not contract.state_target_ready:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeUpstreamStateTargetStatus.CONTRACT_NOT_READY,
      'upstream state-target probe requires a ready conservative target frame',
      contract=contract,
      request=request,
    )
  try:
    target_profile = _state_profile(
      contract.conservative_state_profile,
      'contract.conservative_state_profile',
    )
    target_points = _points(
      contract.conservative_state_profile_points_m,
      'contract.conservative_state_profile_points_m',
    )
    target_entropy = _entropy_profile(
      contract.entropy_proxy_profile,
      'contract.entropy_proxy_profile',
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeUpstreamStateTargetStatus.FRAME_FAILURE,
      f'contract target frame could not be reconstructed: {error}',
      contract=contract,
      request=request,
    )
  if (
    len(target_profile) != len(target_points)
    or len(target_profile) != len(target_entropy)
    or not target_profile
  ):
    return _failure(
      MocReflectedDomainGlobalMixedRegimeUpstreamStateTargetStatus.FRAME_FAILURE,
      'contract target state, point, or entropy frame is empty or misaligned',
      contract=contract,
      request=request,
      target_profile=target_profile,
      target_points=target_points,
      target_entropy=target_entropy,
    )
  try:
    for state in target_profile:
      _validate_target_state(
        state,
        request.target_gamma,
        request.gas_constant_J_kgK,
        request.residual_floor,
      )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeUpstreamStateTargetStatus.TARGET_STATE_FAILURE,
      f'contract target state is not physically dimensionalizable: {error}',
      contract=contract,
      request=request,
      target_profile=target_profile,
      target_points=target_points,
      target_entropy=target_entropy,
    )
  ####
  closure = contract.closure
  global_euler = None if closure is None else closure.global_euler
  physical_field = None if global_euler is None else global_euler.physical_field
  field = None if physical_field is None else physical_field.field
  if (
    field is None
    or not physical_field.converged
    or not physical_field.physical_closure_verified
    or not field.state_sampling_available
  ):
    return _failure(
      MocReflectedDomainGlobalMixedRegimeUpstreamStateTargetStatus.FIELD_NOT_READY,
      'exact global characteristic field is not ready for state sampling',
      contract=contract,
      request=request,
      target_profile=target_profile,
      target_points=target_points,
      target_entropy=target_entropy,
    )
  ####
  sampled_states: list[MocReflectedDomainGlobalMixedRegimeConservativeStateSample] = []
  try:
    for point in target_points:
      characteristic = field.state_at(
        point,
        position_tolerance_m=request.position_tolerance_m,
      )
      total_pressure = field.total_pressure_at(
        point,
        position_tolerance_m=request.position_tolerance_m,
      )
      if characteristic is None or total_pressure is None:
        raise ValueError(f'global field did not sample target point {point!r}')
      sampled_states.append(
        _conservative_from_characteristic(
          characteristic,
          float(total_pressure),
          request,
        )
      )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeUpstreamStateTargetStatus.SAMPLE_FAILURE,
      f'exact global field state sampling failed: {error}',
      contract=contract,
      request=request,
      target_profile=target_profile,
      target_points=target_points,
      target_entropy=target_entropy,
    )
  ####
  sampled_profile = tuple(sample.conservative_state for sample in sampled_states)
  sampled_entropy = tuple(sample.entropy_proxy for sample in sampled_states)
  signed = tuple(
    tuple(
      actual - target
      for actual, target in zip(sampled, target, strict=True)
    )
    for sampled, target in zip(sampled_profile, target_profile, strict=True)
  )
  relative = tuple(
    tuple(
      residual / max(abs(target), request.residual_floor)
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
  signed_entropy = tuple(
    log(actual / target)
    for actual, target in zip(sampled_entropy, target_entropy, strict=True)
  )
  maximum_absolute_entropy = max(
    (abs(residual) for residual in signed_entropy),
    default=0.0,
  )
  dimensionalization_verified = bool(
    len(sampled_states) == len(target_points)
    and all(
      all(isfinite(value) for value in sample.conservative_state)
      for sample in sampled_states
    )
  )
  target_frame_verified = bool(
    contract.state_target_frame_verified
    and contract.conservative_state_profile == target_profile
    and contract.conservative_state_profile_points_m == target_points
    and contract.entropy_proxy_profile == target_entropy
  )
  global_field_sampling_verified = bool(
    len(sampled_states) == len(target_points)
    and all(
      max(
        abs(sample.point_m[0] - point[0]),
        abs(sample.point_m[1] - point[1]),
      ) <= request.position_tolerance_m
      for sample, point in zip(sampled_states, target_points, strict=True)
    )
  )
  entropy_proxy_residuals_measured = bool(
    len(sampled_entropy) == len(target_entropy) == len(target_profile)
    and len(signed_entropy) == len(target_entropy)
    and all(isfinite(value) for value in sampled_entropy)
    and all(isfinite(value) for value in signed_entropy)
  )
  measured = bool(
    target_frame_verified
    and dimensionalization_verified
    and global_field_sampling_verified
    and len(signed) == len(target_profile)
    and all(isfinite(value) for residual in signed for value in residual)
    and all(isfinite(value) for residual in relative for value in residual)
    and entropy_proxy_residuals_measured
  )
  entropy_available = bool(contract.available_channels.get('entropy', False))
  return MocReflectedDomainGlobalMixedRegimeUpstreamStateTargetResult(
    status=(
      MocReflectedDomainGlobalMixedRegimeUpstreamStateTargetStatus
      .MEASURED_LOCAL_RESEARCH_RESIDUALS
      if measured
      else MocReflectedDomainGlobalMixedRegimeUpstreamStateTargetStatus.SAMPLE_FAILURE
    ),
    contract=contract,
    request=request,
    target_profile=target_profile,
    target_points_m=target_points,
    target_entropy_proxy_profile=target_entropy,
    sampled_states=tuple(sampled_states),
    sampled_profile=sampled_profile,
    sampled_entropy_proxy_profile=sampled_entropy,
    signed_state_residuals=signed,
    relative_state_residuals=relative,
    signed_entropy_log_residuals=signed_entropy,
    maximum_absolute_residual_by_component=maximum_absolute,
    maximum_relative_residual_by_component=maximum_relative,
    maximum_absolute_entropy_log_residual=maximum_absolute_entropy,
    target_frame_verified=target_frame_verified,
    dimensionalization_verified=dimensionalization_verified,
    global_field_sampling_verified=global_field_sampling_verified,
    state_target_residuals_measured=measured,
    entropy_proxy_residuals_measured=entropy_proxy_residuals_measured,
    entropy_channel_available=entropy_available,
    entropy_channel_consumed=False,
    upstream_equation_consumed=False,
    global_coupling_verified=False,
    canonical_free_boundary_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    message=(
      'exact global characteristic states were dimensionalized and compared '
      'at the retained 2-D target frame; conservative and entropy-proxy '
      'residuals were measured, but the upstream equation, entropy channel, '
      'global feedback, and promotion remain unavailable'
    )
    if measured
    else 'global state-target residual measurement did not pass its local gates',
  )
