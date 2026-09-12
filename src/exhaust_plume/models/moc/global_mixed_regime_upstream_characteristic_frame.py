"""Explicit conservative-to-characteristic boundary-frame bridge.

The mixed-regime trace is a dimensional conservative state frame.  It cannot
be cast directly to :class:`CharacteristicState`: the trace may be subsonic,
while ``CharacteristicState`` is intentionally restricted to supersonic MOC
states.  This module performs the thermodynamic conversion explicitly and
retains an optional characteristic state only where the state is supersonic.

The bridge is a research seam.  It does not consume an upstream characteristic
equation, solve a moving free boundary, or promote a subsonic trace into a
supersonic MOC boundary.  Its purpose is to give the future solver an exact,
auditable boundary frame and to make the mixed-regime transition a typed gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import atan2, isfinite, log, sqrt
from typing import Any

from exhaust_plume.models.moc.global_mixed_regime_upstream_state_equation import (
  MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRequest,
  MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationResult,
)
from exhaust_plume.models.moc.global_physical_closure import (
  MocReflectedDomainGlobalPhysicalClosureResult,
  moc_reflected_domain_global_physical_closure_fingerprint,
)
from exhaust_plume.models.moc.primitives import CharacteristicState

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_UPSTREAM_CHARACTERISTIC_FRAME_OPERATOR_ID',
  'MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_UPSTREAM_CHARACTERISTIC_FRAME_MODEL',
  'MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicFrameStatus',
  'MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicFrameRequest',
  'MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicFrameSample',
  'MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicFrameResult',
  'MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicFrameAuditStatus',
  'MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicFrameAudit',
  'build_reflected_domain_global_mixed_regime_upstream_characteristic_frame',
  'audit_reflected_domain_global_mixed_regime_upstream_characteristic_frame',
)


MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_UPSTREAM_CHARACTERISTIC_FRAME_OPERATOR_ID = (
  'op.moc.reflected-domain.global-mixed-regime-upstream-characteristic-frame-v1'
)
MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_UPSTREAM_CHARACTERISTIC_FRAME_MODEL = (
  'research-global-mixed-regime-upstream-characteristic-frame-v1'
)

_STATE_COMPONENT_NAMES = (
  'density',
  'streamwise_momentum',
  'transverse_momentum',
  'total_energy',
)


class MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicFrameStatus(
  str,
  Enum,
):
  """Typed outcomes of one conservative boundary-frame conversion."""

  CONVERGED_LOCAL_RESEARCH_PRIMITIVE_FRAME = (
    'converged-local-research-mixed-regime-primitive-boundary-frame'
  )
  INVALID_INPUT = 'invalid_input'
  STATE_EQUATION_REQUIRED = (
    'upstream-characteristic-frame-state-equation-required'
  )
  TARGET_FRAME_FAILURE = 'upstream-characteristic-frame-target-frame-failure'
  THERMODYNAMIC_FAILURE = (
    'upstream-characteristic-frame-thermodynamic-failure'
  )
  ENTROPY_FAILURE = 'upstream-characteristic-frame-entropy-failure'
####


class MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicFrameAuditStatus(
  str,
  Enum,
):
  """Typed outcomes of an independent boundary-frame replay."""

  VERIFIED_LOCAL_RESEARCH_PRIMITIVE_FRAME = (
    'verified-local-research-mixed-regime-primitive-boundary-frame'
  )
  INVALID_INPUT = 'invalid_input'
  REPLAY_FAILURE = 'upstream-characteristic-frame-audit-replay-failure'
####


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
  ####
  return profile
####


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
    raise ValueError(f'{name} must contain finite two-dimensional points')
  ####
  if any(
    second[0] <= first[0]
    for first, second in zip(points, points[1:])
  ):
    raise ValueError(f'{name} must be strictly ordered in x')
  ####
  return points
####


def _positive_float(value: Any, name: str) -> float:
  numeric = float(value)
  if not isfinite(numeric) or numeric <= 0.0:
    raise ValueError(f'{name} must be finite and positive')
  ####
  return numeric
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicFrameRequest:
  """Controls for the exact conservative boundary-frame bridge."""

  upstream_state_equation: (
    MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationResult
  )
  entropy_tolerance: float = 1.0e-8
  state_tolerance: float = 1.0e-10
  sonic_tolerance: float = 1.0e-8
  source: str = (
    MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_UPSTREAM_CHARACTERISTIC_FRAME_MODEL
  )

  def __post_init__(self) -> None:
    if not isinstance(
      self.upstream_state_equation,
      MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationResult,
    ):
      raise TypeError(
        'upstream_state_equation must be a typed upstream state-equation result'
      )
    ####
    for name in ('entropy_tolerance', 'state_tolerance', 'sonic_tolerance'):
      object.__setattr__(self, name, _positive_float(getattr(self, name), name))
    ####
    object.__setattr__(self, 'source', str(self.source))
    if not self.source:
      raise ValueError('source must be non-empty')
    ####
  ####

  def as_report(self) -> dict[str, Any]:
    equation = self.upstream_state_equation
    closure = equation.source_closure
    return {
      'operator_id': (
        MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_UPSTREAM_CHARACTERISTIC_FRAME_OPERATOR_ID
      ),
      'model': MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_UPSTREAM_CHARACTERISTIC_FRAME_MODEL,
      'source_closure_fingerprint': (
        None
        if closure is None
        else moc_reflected_domain_global_physical_closure_fingerprint(closure)
      ),
      'upstream_state_equation_consumed': (
        equation.research_state_equation_consumed
      ),
      'entropy_tolerance': self.entropy_tolerance,
      'state_tolerance': self.state_tolerance,
      'sonic_tolerance': self.sonic_tolerance,
      'source': self.source,
      'research_only': True,
      'production_claim_allowed': False,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicFrameSample:
  """One exact dimensional state with an optional supersonic MOC state."""

  point_m: tuple[float, float]
  conservative_state: tuple[float, float, float, float]
  target_entropy_proxy: float
  density_kg_m3: float
  velocity_u_m_s: float
  velocity_v_m_s: float
  static_pressure_Pa: float
  static_temperature_K: float
  sound_speed_m_s: float
  mach: float
  flow_angle_rad: float
  total_pressure_Pa: float
  total_temperature_K: float
  entropy_proxy: float
  entropy_log_residual: float
  roundtrip_relative_residuals: tuple[float, float, float, float]
  characteristic_state: CharacteristicState | None = None

  def __post_init__(self) -> None:
    point = tuple(float(value) for value in self.point_m)
    if len(point) != 2 or any(not isfinite(value) for value in point):
      raise ValueError('point_m must contain two finite coordinates')
    ####
    conservative = tuple(float(value) for value in self.conservative_state)
    if len(conservative) != 4 or any(not isfinite(value) for value in conservative):
      raise ValueError('conservative_state must contain four finite values')
    ####
    if conservative[0] <= 0.0 or conservative[3] <= 0.0:
      raise ValueError('conservative density and energy must be positive')
    ####
    for name in (
      'target_entropy_proxy',
      'density_kg_m3',
      'static_pressure_Pa',
      'static_temperature_K',
      'sound_speed_m_s',
      'mach',
      'total_pressure_Pa',
      'total_temperature_K',
      'entropy_proxy',
    ):
      value = float(getattr(self, name))
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      ####
      object.__setattr__(self, name, value)
    ####
    for name in ('velocity_u_m_s', 'velocity_v_m_s', 'flow_angle_rad', 'entropy_log_residual'):
      value = float(getattr(self, name))
      if not isfinite(value):
        raise ValueError(f'{name} must be finite')
      ####
      object.__setattr__(self, name, value)
    ####
    residuals = tuple(float(value) for value in self.roundtrip_relative_residuals)
    if len(residuals) != 4 or any(not isfinite(value) for value in residuals):
      raise ValueError('roundtrip_relative_residuals must contain four finite values')
    ####
    if self.characteristic_state is not None and not isinstance(
      self.characteristic_state,
      CharacteristicState,
    ):
      raise TypeError('characteristic_state must be a CharacteristicState or None')
    ####
    object.__setattr__(self, 'point_m', point)
    object.__setattr__(self, 'conservative_state', conservative)
    object.__setattr__(self, 'roundtrip_relative_residuals', residuals)
  ####

  @property
  def supersonic(self) -> bool:
    return self.characteristic_state is not None
  ####

  @property
  def regime(self) -> str:
    if self.characteristic_state is not None:
      return 'supersonic'
    ####
    return 'subsonic_or_sonic'
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'point_m': self.point_m,
      'conservative_state': self.conservative_state,
      'target_entropy_proxy': self.target_entropy_proxy,
      'density_kg_m3': self.density_kg_m3,
      'velocity_u_m_s': self.velocity_u_m_s,
      'velocity_v_m_s': self.velocity_v_m_s,
      'static_pressure_Pa': self.static_pressure_Pa,
      'static_temperature_K': self.static_temperature_K,
      'sound_speed_m_s': self.sound_speed_m_s,
      'mach': self.mach,
      'flow_angle_rad': self.flow_angle_rad,
      'total_pressure_Pa': self.total_pressure_Pa,
      'total_temperature_K': self.total_temperature_K,
      'entropy_proxy': self.entropy_proxy,
      'entropy_log_residual': self.entropy_log_residual,
      'roundtrip_relative_residuals': self.roundtrip_relative_residuals,
      'regime': self.regime,
      'characteristic_state': (
        None
        if self.characteristic_state is None
        else {
          'x_m': self.characteristic_state.x_m,
          'y_m': self.characteristic_state.y_m,
          'theta_rad': self.characteristic_state.theta_rad,
          'mach': self.characteristic_state.mach,
          'gamma': self.characteristic_state.gamma,
        }
      ),
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicFrameResult:
  """Auditable primitive/characteristic frame below global promotion."""

  status: MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicFrameStatus
  request: MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicFrameRequest | None
  source_closure: MocReflectedDomainGlobalPhysicalClosureResult | None
  samples: tuple[MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicFrameSample, ...] = ()
  target_frame_verified: bool = False
  source_state_equation_consumed: bool = False
  primitive_frame_verified: bool = False
  state_roundtrip_verified: bool = False
  entropy_lineage_verified: bool = False
  characteristic_state_profile_available: bool = False
  upstream_characteristic_equation_consumed: bool = False
  free_boundary_equation_consumed: bool = False
  global_coupling_verified: bool = False
  canonical_free_boundary_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicFrameStatus,
    ):
      raise TypeError('status must be a typed characteristic-frame status')
    ####
    if self.request is not None and not isinstance(
      self.request,
      MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicFrameRequest,
    ):
      raise TypeError('request must be a typed characteristic-frame request')
    ####
    if self.source_closure is not None and not isinstance(
      self.source_closure,
      MocReflectedDomainGlobalPhysicalClosureResult,
    ):
      raise TypeError('source_closure must be a typed global physical closure')
    ####
    samples = tuple(self.samples)
    if any(
      not isinstance(
        sample,
        MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicFrameSample,
      )
      for sample in samples
    ):
      raise TypeError('samples must contain typed characteristic-frame samples')
    ####
    object.__setattr__(self, 'samples', samples)
    for name in (
      'target_frame_verified',
      'source_state_equation_consumed',
      'primitive_frame_verified',
      'state_roundtrip_verified',
      'entropy_lineage_verified',
      'characteristic_state_profile_available',
      'upstream_characteristic_equation_consumed',
      'free_boundary_equation_consumed',
      'global_coupling_verified',
      'canonical_free_boundary_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if (
      self.upstream_characteristic_equation_consumed
      or self.free_boundary_equation_consumed
      or self.global_coupling_verified
      or self.canonical_free_boundary_verified
    ):
      raise ValueError('characteristic boundary frame cannot claim equation closure')
    ####
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError('characteristic boundary frame must remain promotion-blocked')
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicFrameStatus
      .CONVERGED_LOCAL_RESEARCH_PRIMITIVE_FRAME
      and self.target_frame_verified
      and self.source_state_equation_consumed
      and self.primitive_frame_verified
      and self.state_roundtrip_verified
      and self.entropy_lineage_verified
      and self.samples
    )
  ####

  @property
  def characteristic_equation_ready(self) -> bool:
    """Whether every retained boundary state is valid for planar MOC."""

    return bool(self.converged and self.characteristic_state_profile_available)
  ####

  @property
  def supersonic_sample_count(self) -> int:
    return sum(sample.supersonic for sample in self.samples)
  ####

  @property
  def subsonic_or_sonic_sample_count(self) -> int:
    return len(self.samples) - self.supersonic_sample_count
  ####

  @property
  def component_names(self) -> tuple[str, ...]:
    return _STATE_COMPONENT_NAMES
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': (
        MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_UPSTREAM_CHARACTERISTIC_FRAME_OPERATOR_ID
      ),
      'model': MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_UPSTREAM_CHARACTERISTIC_FRAME_MODEL,
      'status': self.status.value,
      'converged': self.converged,
      'characteristic_equation_ready': self.characteristic_equation_ready,
      'component_names': self.component_names,
      'source_closure_fingerprint': (
        None
        if self.source_closure is None
        else moc_reflected_domain_global_physical_closure_fingerprint(
          self.source_closure
        )
      ),
      'sample_count': len(self.samples),
      'supersonic_sample_count': self.supersonic_sample_count,
      'subsonic_or_sonic_sample_count': self.subsonic_or_sonic_sample_count,
      'samples': [sample.as_report() for sample in self.samples],
      'target_frame_verified': self.target_frame_verified,
      'source_state_equation_consumed': self.source_state_equation_consumed,
      'primitive_frame_verified': self.primitive_frame_verified,
      'state_roundtrip_verified': self.state_roundtrip_verified,
      'entropy_lineage_verified': self.entropy_lineage_verified,
      'characteristic_state_profile_available': (
        self.characteristic_state_profile_available
      ),
      'upstream_characteristic_equation_consumed': False,
      'free_boundary_equation_consumed': False,
      'global_coupling_verified': False,
      'canonical_free_boundary_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'request': None if self.request is None else self.request.as_report(),
      'claim_status': (
        'research-only exact conservative mixed-regime boundary frame; a '
        'subsonic trace is retained as primitive data and is not cast into '
        'supersonic characteristic state or promoted into upstream closure'
      ),
      'message': self.message,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicFrameAudit:
  """Independent replay evidence for the primitive boundary-frame bridge."""

  status: MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicFrameAuditStatus
  result: MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicFrameResult | None
  replay: MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicFrameResult | None
  target_frame_replayed: bool = False
  primitive_frame_replayed: bool = False
  state_roundtrip_replayed: bool = False
  entropy_lineage_replayed: bool = False
  regime_classification_replayed: bool = False
  independent_frame_verified: bool = False
  upstream_characteristic_equation_consumed: bool = False
  free_boundary_equation_consumed: bool = False
  global_coupling_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicFrameAuditStatus,
    ):
      raise TypeError('status must be a typed characteristic-frame audit status')
    ####
    for name in ('result', 'replay'):
      value = getattr(self, name)
      if value is not None and not isinstance(
        value,
        MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicFrameResult,
      ):
        raise TypeError(f'{name} must be a typed characteristic-frame result')
      ####
    ####
    for name in (
      'target_frame_replayed',
      'primitive_frame_replayed',
      'state_roundtrip_replayed',
      'entropy_lineage_replayed',
      'regime_classification_replayed',
      'independent_frame_verified',
      'upstream_characteristic_equation_consumed',
      'free_boundary_equation_consumed',
      'global_coupling_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if (
      self.upstream_characteristic_equation_consumed
      or self.free_boundary_equation_consumed
      or self.global_coupling_verified
    ):
      raise ValueError('characteristic-frame audit cannot claim equation closure')
    ####
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError('characteristic-frame audit must remain promotion-blocked')
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicFrameAuditStatus
      .VERIFIED_LOCAL_RESEARCH_PRIMITIVE_FRAME
      and self.independent_frame_verified
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': (
        MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_UPSTREAM_CHARACTERISTIC_FRAME_OPERATOR_ID
      ),
      'audit_status': self.status.value,
      'converged': self.converged,
      'target_frame_replayed': self.target_frame_replayed,
      'primitive_frame_replayed': self.primitive_frame_replayed,
      'state_roundtrip_replayed': self.state_roundtrip_replayed,
      'entropy_lineage_replayed': self.entropy_lineage_replayed,
      'regime_classification_replayed': self.regime_classification_replayed,
      'independent_frame_verified': self.independent_frame_verified,
      'upstream_characteristic_equation_consumed': False,
      'free_boundary_equation_consumed': False,
      'global_coupling_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'result': None if self.result is None else self.result.as_report(),
      'replay': None if self.replay is None else self.replay.as_report(),
      'message': self.message,
    }
  ####
####


def _failure(
  status: MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicFrameStatus,
  message: str,
  *,
  request: MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicFrameRequest | None = None,
  source_closure: MocReflectedDomainGlobalPhysicalClosureResult | None = None,
  **values: Any,
) -> MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicFrameResult:
  return MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicFrameResult(
    status=status,
    request=request,
    source_closure=source_closure,
    message=message,
    **values,
  )
####


def _convert_state(
  point: tuple[float, float],
  state: tuple[float, float, float, float],
  target_entropy: float,
  gamma: float,
  gas_constant: float,
  sonic_tolerance: float,
) -> MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicFrameSample:
  density, momentum_x, momentum_y, total_energy = state
  if density <= 0.0 or total_energy <= 0.0:
    raise ValueError('conservative density and energy must be positive')
  ####
  velocity_u = momentum_x / density
  velocity_v = momentum_y / density
  speed_squared = velocity_u * velocity_u + velocity_v * velocity_v
  kinetic = 0.5 * density * speed_squared
  pressure = (gamma - 1.0) * (total_energy - kinetic)
  if not isfinite(pressure) or pressure <= 0.0:
    raise ValueError('conservative state has non-positive static pressure')
  ####
  temperature = pressure / (density * gas_constant)
  sound_speed = sqrt(gamma * pressure / density)
  speed = sqrt(speed_squared)
  mach = speed / sound_speed
  if not isfinite(temperature) or temperature <= 0.0 or not isfinite(mach):
    raise ValueError('conservative state produced invalid temperature or Mach')
  ####
  flow_angle = atan2(velocity_v, velocity_u) if speed > 0.0 else 0.0
  stagnation_factor = 1.0 + 0.5 * (gamma - 1.0) * mach * mach
  total_pressure = pressure * stagnation_factor ** (gamma / (gamma - 1.0))
  total_temperature = temperature * stagnation_factor
  entropy_proxy = pressure / density**gamma
  entropy_log_residual = log(entropy_proxy / target_entropy)
  reconstructed = (
    density,
    momentum_x,
    momentum_y,
    pressure / (gamma - 1.0) + kinetic,
  )
  roundtrip = tuple(
    (actual - expected) / max(abs(expected), 1.0e-12)
    for actual, expected in zip(reconstructed, state, strict=True)
  )
  characteristic = None
  if mach > 1.0 + sonic_tolerance:
    characteristic = CharacteristicState(
      x_m=point[0],
      y_m=point[1],
      theta_rad=flow_angle,
      mach=mach,
      gamma=gamma,
    )
  ####
  return MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicFrameSample(
    point_m=point,
    conservative_state=state,
    target_entropy_proxy=target_entropy,
    density_kg_m3=density,
    velocity_u_m_s=velocity_u,
    velocity_v_m_s=velocity_v,
    static_pressure_Pa=pressure,
    static_temperature_K=temperature,
    sound_speed_m_s=sound_speed,
    mach=mach,
    flow_angle_rad=flow_angle,
    total_pressure_Pa=total_pressure,
    total_temperature_K=total_temperature,
    entropy_proxy=entropy_proxy,
    entropy_log_residual=entropy_log_residual,
    roundtrip_relative_residuals=roundtrip,
    characteristic_state=characteristic,
  )
####


def build_reflected_domain_global_mixed_regime_upstream_characteristic_frame(
  request: MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicFrameRequest,
) -> MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicFrameResult:
  """Build an exact primitive frame without claiming MOC equation closure."""

  status_type = MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicFrameStatus
  if not isinstance(
    request,
    MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicFrameRequest,
  ):
    return _failure(
      status_type.INVALID_INPUT,
      'request must be a typed upstream characteristic-frame request',
    )
  ####
  equation = request.upstream_state_equation
  closure = equation.source_closure
  if not equation.research_state_equation_consumed:
    return _failure(
      status_type.STATE_EQUATION_REQUIRED,
      'characteristic boundary framing requires an independently consumed '
      'conservative/entropy upstream state-equation result',
      request=request,
      source_closure=closure,
    )
  ####
  equation_request = equation.request
  if not isinstance(
    equation_request,
    MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRequest,
  ):
    return _failure(
      status_type.TARGET_FRAME_FAILURE,
      'upstream state-equation result did not retain its typed request frame',
      request=request,
      source_closure=closure,
    )
  ####
  try:
    points = _points(equation_request.target_points_m, 'target_points_m')
    profile = _state_profile(
      equation_request.target_conservative_state_profile,
      'target_conservative_state_profile',
    )
    entropy = tuple(float(value) for value in equation_request.target_entropy_proxy_profile)
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      status_type.TARGET_FRAME_FAILURE,
      f'exact upstream state-equation frame could not be reconstructed: {error}',
      request=request,
      source_closure=closure,
    )
  ####
  target_frame_verified = bool(
    equation.target_frame_verified
    and len(points) == len(profile) == len(entropy)
    and len(points) >= 2
    and equation_request is equation.request
  )
  if not target_frame_verified:
    return _failure(
      status_type.TARGET_FRAME_FAILURE,
      'upstream state-equation target points, states, and entropy do not '
      'retain one exact ordered frame',
      request=request,
      source_closure=closure,
      target_frame_verified=False,
    )
  ####
  if any(not isfinite(value) or value <= 0.0 for value in entropy):
    return _failure(
      status_type.ENTROPY_FAILURE,
      'upstream state-equation target entropy must be finite and positive',
      request=request,
      source_closure=closure,
      target_frame_verified=True,
    )
  ####
  gamma = float(equation_request.target_gamma)
  gas_constant = float(equation_request.gas_constant_J_kgK)
  if not isfinite(gamma) or gamma <= 1.0 or not isfinite(gas_constant) or gas_constant <= 0.0:
    return _failure(
      status_type.THERMODYNAMIC_FAILURE,
      'upstream state-equation thermodynamic controls are invalid',
      request=request,
      source_closure=closure,
      target_frame_verified=True,
    )
  ####
  try:
    samples = tuple(
      _convert_state(
        point,
        state,
        target_entropy_value,
        gamma,
        gas_constant,
        request.sonic_tolerance,
      )
      for point, state, target_entropy_value in zip(
        points,
        profile,
        entropy,
        strict=True,
      )
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      status_type.THERMODYNAMIC_FAILURE,
      f'exact conservative target could not be dimensionalized: {error}',
      request=request,
      source_closure=closure,
      target_frame_verified=True,
      source_state_equation_consumed=True,
    )
  ####
  entropy_verified = bool(
    all(abs(sample.entropy_log_residual) <= request.entropy_tolerance for sample in samples)
  )
  if not entropy_verified:
    return _failure(
      status_type.ENTROPY_FAILURE,
      'exact conservative target and retained entropy proxy are inconsistent '
      'in the characteristic boundary frame',
      request=request,
      source_closure=closure,
      samples=samples,
      target_frame_verified=True,
      source_state_equation_consumed=True,
      primitive_frame_verified=True,
      state_roundtrip_verified=True,
      entropy_lineage_verified=False,
      characteristic_state_profile_available=False,
    )
  ####
  roundtrip_verified = bool(
    all(
      max(abs(value) for value in sample.roundtrip_relative_residuals)
      <= request.state_tolerance
      for sample in samples
    )
  )
  primitive_verified = bool(
    samples
    and all(
      all(
        isfinite(value)
        for value in (
          sample.density_kg_m3,
          sample.static_pressure_Pa,
          sample.static_temperature_K,
          sample.sound_speed_m_s,
          sample.mach,
          sample.total_pressure_Pa,
          sample.total_temperature_K,
          sample.entropy_proxy,
        )
      )
      for sample in samples
    )
  )
  characteristic_available = bool(
    primitive_verified and all(sample.characteristic_state is not None for sample in samples)
  )
  return MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicFrameResult(
    status=status_type.CONVERGED_LOCAL_RESEARCH_PRIMITIVE_FRAME,
    request=request,
    source_closure=closure,
    samples=samples,
    target_frame_verified=True,
    source_state_equation_consumed=True,
    primitive_frame_verified=primitive_verified,
    state_roundtrip_verified=roundtrip_verified,
    entropy_lineage_verified=entropy_verified,
    characteristic_state_profile_available=characteristic_available,
    upstream_characteristic_equation_consumed=False,
    free_boundary_equation_consumed=False,
    global_coupling_verified=False,
    canonical_free_boundary_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    message=(
      'exact four-component conservative target was converted to an audited '
      'primitive frame; the retained mixed-regime samples are subsonic or '
      'sonic and therefore remain unavailable to the supersonic characteristic '
      'equation'
      if not characteristic_available
      else 'exact conservative target was converted to an audited primitive '
      'and supersonic characteristic frame; the upstream equation and free '
      'boundary remain separate gates'
    ),
  )
####


def audit_reflected_domain_global_mixed_regime_upstream_characteristic_frame(
  result: MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicFrameResult,
) -> MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicFrameAudit:
  """Replay the exact frame conversion without widening its claim ceiling."""

  audit_status = (
    MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicFrameAuditStatus
  )
  if not isinstance(
    result,
    MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicFrameResult,
  ):
    return MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicFrameAudit(
      status=audit_status.INVALID_INPUT,
      result=None,
      replay=None,
      message='result must be a typed upstream characteristic-frame result',
    )
  ####
  if result.request is None or not result.converged:
    return MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicFrameAudit(
      status=audit_status.REPLAY_FAILURE,
      result=result,
      replay=None,
      message=(
        'independent characteristic-frame replay requires a locally converged '
        'primitive frame with its typed request retained'
      ),
    )
  ####
  try:
    replay = build_reflected_domain_global_mixed_regime_upstream_characteristic_frame(
      result.request
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicFrameAudit(
      status=audit_status.REPLAY_FAILURE,
      result=result,
      replay=None,
      message=f'independent characteristic-frame replay raised: {error}',
    )
  ####
  target_replayed = bool(
    replay.target_frame_verified == result.target_frame_verified
    and replay.source_state_equation_consumed
    == result.source_state_equation_consumed
    and replay.request is result.request
  )
  primitive_replayed = bool(
    replay.primitive_frame_verified == result.primitive_frame_verified
    and len(replay.samples) == len(result.samples)
    and replay.samples == result.samples
  )
  roundtrip_replayed = bool(
    replay.state_roundtrip_verified == result.state_roundtrip_verified
  )
  entropy_replayed = bool(
    replay.entropy_lineage_verified == result.entropy_lineage_verified
  )
  regime_replayed = bool(
    replay.characteristic_state_profile_available
    == result.characteristic_state_profile_available
    and tuple(sample.regime for sample in replay.samples)
    == tuple(sample.regime for sample in result.samples)
  )
  independent = bool(
    replay.converged
    and target_replayed
    and primitive_replayed
    and roundtrip_replayed
    and entropy_replayed
    and regime_replayed
  )
  return MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicFrameAudit(
    status=(
      audit_status.VERIFIED_LOCAL_RESEARCH_PRIMITIVE_FRAME
      if independent
      else audit_status.REPLAY_FAILURE
    ),
    result=result,
    replay=replay,
    target_frame_replayed=target_replayed,
    primitive_frame_replayed=primitive_replayed,
    state_roundtrip_replayed=roundtrip_replayed,
    entropy_lineage_replayed=entropy_replayed,
    regime_classification_replayed=regime_replayed,
    independent_frame_verified=independent,
    upstream_characteristic_equation_consumed=False,
    free_boundary_equation_consumed=False,
    global_coupling_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    message=(
      'independent replay reproduced the exact conservative primitive frame '
      'and its subsonic/supersonic classification; upstream characteristic '
      'and free-boundary equations remain open'
      if independent
      else 'independent replay did not reproduce every retained frame gate'
    ),
  )
####
