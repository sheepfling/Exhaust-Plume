"""Research-only two-sided normal closure for a mixed-regime interface.

The upstream characteristic contracts deliberately stop before the normal or
free-boundary closure.  This module defines that next boundary without
inventing an ambient state from pressure alone.  It consumes the exact
transonic interface, an independently replayed incoming-family compatibility
result, and a solver-owned ambient primitive state at every interface sample.

The closure compares moving-control-volume mass, normal momentum, tangential
momentum, total energy, and entropy-proxy fluxes on both sides.  It is a local
two-sided conservation admission, not a global free-boundary fixed point, a
shock fit, or a production validation result.  In particular, a copied
pressure target cannot satisfy this contract when ambient density, velocity,
temperature, gas law, and entropy orientation are absent.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import hypot, isfinite, log
from typing import Any

from exhaust_plume.models.moc.global_mixed_regime_transonic_interface import (
  MocReflectedDomainGlobalMixedRegimeTransonicInterfaceAudit,
  MocReflectedDomainGlobalMixedRegimeTransonicInterfaceAuditStatus,
  MocReflectedDomainGlobalMixedRegimeTransonicInterfaceFluxSample,
  MocReflectedDomainGlobalMixedRegimeTransonicInterfaceResult,
)
from exhaust_plume.models.moc.global_mixed_regime_upstream_characteristic_compatibility import (
  MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityAudit,
  MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityResult,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_NORMAL_CLOSURE_OPERATOR_ID',
  'MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_NORMAL_CLOSURE_MODEL',
  'MocReflectedDomainGlobalMixedRegimeNormalClosureStatus',
  'MocReflectedDomainGlobalMixedRegimeNormalClosureRequest',
  'MocReflectedDomainGlobalMixedRegimeNormalClosureAmbientState',
  'MocReflectedDomainGlobalMixedRegimeNormalClosureSample',
  'MocReflectedDomainGlobalMixedRegimeNormalClosureResult',
  'MocReflectedDomainGlobalMixedRegimeNormalClosureAuditStatus',
  'MocReflectedDomainGlobalMixedRegimeNormalClosureAudit',
  'solve_reflected_domain_global_mixed_regime_normal_closure',
  'audit_reflected_domain_global_mixed_regime_normal_closure',
)


MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_NORMAL_CLOSURE_OPERATOR_ID = (
  'op.moc.reflected-domain.global-mixed-regime-normal-closure-v1'
)
MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_NORMAL_CLOSURE_MODEL = (
  'research-global-mixed-regime-two-sided-normal-closure-v1'
)


class MocReflectedDomainGlobalMixedRegimeNormalClosureStatus(str, Enum):
  """Typed outcomes of a two-sided local normal-closure attempt."""

  CONVERGED_LOCAL_RESEARCH_NORMAL_CLOSURE = (
    'converged-local-research-normal-closure'
  )
  COMPLETED_RESEARCH_NORMAL_CLOSURE_WITH_OPEN_RESIDUAL = (
    'completed-research-normal-closure-with-open-residual'
  )
  INVALID_INPUT = 'invalid_input'
  INTERFACE_REQUIRED = 'normal-closure-transonic-interface-required'
  INTERFACE_AUDIT_REQUIRED = 'normal-closure-transonic-interface-audit-required'
  INTERFACE_LINEAGE_FAILURE = 'normal-closure-transonic-interface-lineage-failure'
  CHARACTERISTIC_COMPATIBILITY_REQUIRED = (
    'normal-closure-characteristic-compatibility-required'
  )
  CHARACTERISTIC_COMPATIBILITY_AUDIT_REQUIRED = (
    'normal-closure-characteristic-compatibility-audit-required'
  )
  CHARACTERISTIC_COMPATIBILITY_LINEAGE_FAILURE = (
    'normal-closure-characteristic-compatibility-lineage-failure'
  )
  AMBIENT_STATE_REQUIRED = 'normal-closure-ambient-state-required'
  AMBIENT_STATE_LINEAGE_FAILURE = 'normal-closure-ambient-state-lineage-failure'
  AMBIENT_STATE_EQUATION_FAILURE = 'normal-closure-ambient-state-equation-failure'
  FLUX_DECOMPOSITION_FAILURE = 'normal-closure-flux-decomposition-failure'


class MocReflectedDomainGlobalMixedRegimeNormalClosureAuditStatus(str, Enum):
  """Typed outcomes of an independent normal-closure replay."""

  VERIFIED_LOCAL_RESEARCH_NORMAL_CLOSURE = (
    'verified-local-research-normal-closure'
  )
  INVALID_INPUT = 'invalid_input'
  REPLAY_FAILURE = 'normal-closure-audit-replay-failure'
  LINEAGE_FAILURE = 'normal-closure-audit-lineage-failure'


def _finite(name: str, value: object) -> float:
  try:
    numeric = float(value)
  except (TypeError, ValueError) as error:
    raise ValueError(f'{name} must be numeric') from error
  ####
  if not isfinite(numeric):
    raise ValueError(f'{name} must be finite')
  ####
  return numeric
####


def _positive(name: str, value: object) -> float:
  numeric = _finite(name, value)
  if numeric <= 0.0:
    raise ValueError(f'{name} must be positive')
  ####
  return numeric
####


def _point(value: object, name: str) -> tuple[float, float]:
  try:
    point = (float(value[0]), float(value[1]))  # type: ignore[index]
  except (IndexError, TypeError, ValueError) as error:
    raise ValueError(f'{name} must contain two coordinates') from error
  ####
  if any(not isfinite(component) for component in point):
    raise ValueError(f'{name} must contain finite coordinates')
  ####
  return point
####


def _relative_residual(actual: float, expected: float) -> float:
  return abs(actual - expected) / max(abs(actual), abs(expected), 1.0e-12)
####


def _entropy_log(pressure: float, density: float, gamma: float) -> float:
  proxy = pressure / density**gamma
  if proxy <= 0.0 or not isfinite(proxy):
    raise ValueError('entropy proxy must be finite and positive')
  ####
  return log(proxy)
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeNormalClosureAmbientState:
  """One solver-owned ambient primitive state at an exact interface point."""

  sample_index: int
  point_m: tuple[float, float]
  density_kg_m3: float
  velocity_u_m_s: float
  velocity_v_m_s: float
  static_pressure_Pa: float
  static_temperature_K: float
  gamma: float
  specific_gas_constant_J_kg_K: float

  def __post_init__(self) -> None:
    if (
      isinstance(self.sample_index, bool)
      or not isinstance(self.sample_index, int)
      or self.sample_index < 0
    ):
      raise ValueError('sample_index must be a nonnegative integer')
    ####
    object.__setattr__(self, 'point_m', _point(self.point_m, 'point_m'))
    for name in (
      'density_kg_m3',
      'velocity_u_m_s',
      'velocity_v_m_s',
      'static_pressure_Pa',
      'static_temperature_K',
      'gamma',
      'specific_gas_constant_J_kg_K',
    ):
      object.__setattr__(self, name, _finite(name, getattr(self, name)))
    ####
    if self.density_kg_m3 <= 0.0:
      raise ValueError('density_kg_m3 must be positive')
    if self.static_pressure_Pa <= 0.0:
      raise ValueError('static_pressure_Pa must be positive')
    if self.static_temperature_K <= 0.0:
      raise ValueError('static_temperature_K must be positive')
    if self.gamma <= 1.0:
      raise ValueError('gamma must be greater than one')
    if self.specific_gas_constant_J_kg_K <= 0.0:
      raise ValueError('specific_gas_constant_J_kg_K must be positive')
  ####

  @property
  def velocity_m_s(self) -> tuple[float, float]:
    return self.velocity_u_m_s, self.velocity_v_m_s
  ####

  @property
  def total_energy_density_J_m3(self) -> float:
    kinetic = 0.5 * self.density_kg_m3 * (
      self.velocity_u_m_s**2 + self.velocity_v_m_s**2
    )
    return self.static_pressure_Pa / (self.gamma - 1.0) + kinetic
  ####

  @property
  def entropy_proxy(self) -> float:
    return self.static_pressure_Pa / self.density_kg_m3**self.gamma
  ####

  @property
  def entropy_log_proxy(self) -> float:
    return _entropy_log(
      self.static_pressure_Pa,
      self.density_kg_m3,
      self.gamma,
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'sample_index': self.sample_index,
      'point_m': list(self.point_m),
      'density_kg_m3': self.density_kg_m3,
      'velocity_u_m_s': self.velocity_u_m_s,
      'velocity_v_m_s': self.velocity_v_m_s,
      'static_pressure_Pa': self.static_pressure_Pa,
      'static_temperature_K': self.static_temperature_K,
      'gamma': self.gamma,
      'specific_gas_constant_J_kg_K': self.specific_gas_constant_J_kg_K,
      'total_energy_density_J_m3': self.total_energy_density_J_m3,
      'entropy_proxy': self.entropy_proxy,
      'entropy_log_proxy': self.entropy_log_proxy,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeNormalClosureRequest:
  """Inputs for a solver-owned two-sided moving-interface closure."""

  transonic_interface: MocReflectedDomainGlobalMixedRegimeTransonicInterfaceResult
  transonic_interface_audit: MocReflectedDomainGlobalMixedRegimeTransonicInterfaceAudit
  characteristic_compatibility: (
    MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityResult
  ) | None = None
  characteristic_compatibility_audit: (
    MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityAudit
  ) | None = None
  ambient_state_profile: tuple[
    MocReflectedDomainGlobalMixedRegimeNormalClosureAmbientState, ...
  ] | None = None
  state_tolerance: float = 1.0e-8
  point_tolerance_m: float = 1.0e-8
  component_tolerance: float = 1.0e-6
  entropy_tolerance: float = 1.0e-8
  entropy_increase_sign: int = 1
  source: str = MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_NORMAL_CLOSURE_MODEL

  def __post_init__(self) -> None:
    if not isinstance(
      self.transonic_interface,
      MocReflectedDomainGlobalMixedRegimeTransonicInterfaceResult,
    ):
      raise TypeError('transonic_interface must be a typed interface result')
    ####
    if not isinstance(
      self.transonic_interface_audit,
      MocReflectedDomainGlobalMixedRegimeTransonicInterfaceAudit,
    ):
      raise TypeError('transonic_interface_audit must be a typed interface audit')
    ####
    if self.characteristic_compatibility is not None and not isinstance(
      self.characteristic_compatibility,
      MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityResult,
    ):
      raise TypeError('characteristic_compatibility must be a typed result or None')
    ####
    if self.characteristic_compatibility_audit is not None and not isinstance(
      self.characteristic_compatibility_audit,
      MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityAudit,
    ):
      raise TypeError(
        'characteristic_compatibility_audit must be a typed audit or None'
      )
    ####
    if self.ambient_state_profile is not None:
      profile = tuple(self.ambient_state_profile)
      if any(
        not isinstance(
          state,
          MocReflectedDomainGlobalMixedRegimeNormalClosureAmbientState,
        )
        for state in profile
      ):
        raise TypeError('ambient_state_profile must contain typed ambient states')
      ####
      object.__setattr__(self, 'ambient_state_profile', profile)
    ####
    for name in (
      'state_tolerance',
      'point_tolerance_m',
      'component_tolerance',
      'entropy_tolerance',
    ):
      object.__setattr__(self, name, _positive(name, getattr(self, name)))
    ####
    if (
      isinstance(self.entropy_increase_sign, bool)
      or not isinstance(self.entropy_increase_sign, int)
      or abs(self.entropy_increase_sign) != 1
    ):
      raise ValueError('entropy_increase_sign must be either -1 or +1')
    ####
    source = str(self.source)
    if not source:
      raise ValueError('source must be non-empty')
    ####
    object.__setattr__(self, 'source', source)
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_NORMAL_CLOSURE_OPERATOR_ID,
      'model': MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_NORMAL_CLOSURE_MODEL,
      'interface_status': self.transonic_interface.status.value,
      'interface_audit_status': self.transonic_interface_audit.status.value,
      'characteristic_compatibility': (
        None
        if self.characteristic_compatibility is None
        else self.characteristic_compatibility.as_report()
      ),
      'characteristic_compatibility_audit': (
        None
        if self.characteristic_compatibility_audit is None
        else self.characteristic_compatibility_audit.as_report()
      ),
      'ambient_state_profile': (
        None
        if self.ambient_state_profile is None
        else [state.as_report() for state in self.ambient_state_profile]
      ),
      'state_tolerance': self.state_tolerance,
      'point_tolerance_m': self.point_tolerance_m,
      'component_tolerance': self.component_tolerance,
      'entropy_tolerance': self.entropy_tolerance,
      'entropy_increase_sign': self.entropy_increase_sign,
      'source': self.source,
      'research_only': True,
      'production_claim_allowed': False,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeNormalClosureSample:
  """Two-sided flux comparison at one exact interface sample."""

  sample_index: int
  interface_flux: MocReflectedDomainGlobalMixedRegimeTransonicInterfaceFluxSample
  ambient_state: MocReflectedDomainGlobalMixedRegimeNormalClosureAmbientState
  ambient_normal_velocity_m_s: float
  ambient_relative_normal_velocity_m_s: float
  ambient_tangential_velocity_m_s: float
  ambient_mass_flux_kg_m2_s: float
  ambient_normal_momentum_flux_Pa: float
  ambient_tangential_momentum_flux_Pa: float
  ambient_total_energy_flux_W_m2: float
  ambient_entropy_proxy_flux: float
  mass_residual: float
  normal_momentum_residual: float
  tangential_momentum_residual: float
  total_energy_residual: float
  entropy_proxy_residual: float
  entropy_log_jump: float
  entropy_inequality_violation: float

  def __post_init__(self) -> None:
    if (
      isinstance(self.sample_index, bool)
      or not isinstance(self.sample_index, int)
      or self.sample_index < 0
    ):
      raise ValueError('sample_index must be a nonnegative integer')
    ####
    if not isinstance(
      self.interface_flux,
      MocReflectedDomainGlobalMixedRegimeTransonicInterfaceFluxSample,
    ):
      raise TypeError('interface_flux must be a typed interface flux sample')
    if not isinstance(
      self.ambient_state,
      MocReflectedDomainGlobalMixedRegimeNormalClosureAmbientState,
    ):
      raise TypeError('ambient_state must be a typed ambient state')
    ####
    for name in (
      'ambient_normal_velocity_m_s',
      'ambient_relative_normal_velocity_m_s',
      'ambient_tangential_velocity_m_s',
      'ambient_mass_flux_kg_m2_s',
      'ambient_normal_momentum_flux_Pa',
      'ambient_tangential_momentum_flux_Pa',
      'ambient_total_energy_flux_W_m2',
      'ambient_entropy_proxy_flux',
      'mass_residual',
      'normal_momentum_residual',
      'tangential_momentum_residual',
      'total_energy_residual',
      'entropy_proxy_residual',
      'entropy_log_jump',
      'entropy_inequality_violation',
    ):
      object.__setattr__(self, name, _finite(name, getattr(self, name)))
    ####
    for name in (
      'mass_residual',
      'normal_momentum_residual',
      'tangential_momentum_residual',
      'total_energy_residual',
      'entropy_proxy_residual',
      'entropy_inequality_violation',
    ):
      if getattr(self, name) < 0.0:
        raise ValueError(f'{name} must be nonnegative')
    ####
    if self.sample_index != self.interface_flux.sample_index:
      raise ValueError('normal-closure sample index must match interface flux index')
    if self.sample_index != self.ambient_state.sample_index:
      raise ValueError('normal-closure sample index must match ambient state index')
  ####

  @property
  def component_residuals(self) -> tuple[float, ...]:
    return (
      self.mass_residual,
      self.normal_momentum_residual,
      self.tangential_momentum_residual,
      self.total_energy_residual,
      self.entropy_proxy_residual,
    )
  ####

  @property
  def maximum_component_residual(self) -> float:
    return max(self.component_residuals)
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'sample_index': self.sample_index,
      'point_m': list(self.interface_flux.point_m),
      'normal_m': list(self.interface_flux.normal_m),
      'tangent_m': list(self.interface_flux.tangent_m),
      'mach': self.interface_flux.mach,
      'regime': self.interface_flux.regime,
      'ambient_state': self.ambient_state.as_report(),
      'ambient_normal_velocity_m_s': self.ambient_normal_velocity_m_s,
      'ambient_relative_normal_velocity_m_s': (
        self.ambient_relative_normal_velocity_m_s
      ),
      'ambient_tangential_velocity_m_s': self.ambient_tangential_velocity_m_s,
      'ambient_mass_flux_kg_m2_s': self.ambient_mass_flux_kg_m2_s,
      'ambient_normal_momentum_flux_Pa': self.ambient_normal_momentum_flux_Pa,
      'ambient_tangential_momentum_flux_Pa': (
        self.ambient_tangential_momentum_flux_Pa
      ),
      'ambient_total_energy_flux_W_m2': self.ambient_total_energy_flux_W_m2,
      'ambient_entropy_proxy_flux': self.ambient_entropy_proxy_flux,
      'mass_residual': self.mass_residual,
      'normal_momentum_residual': self.normal_momentum_residual,
      'tangential_momentum_residual': self.tangential_momentum_residual,
      'total_energy_residual': self.total_energy_residual,
      'entropy_proxy_residual': self.entropy_proxy_residual,
      'entropy_log_jump': self.entropy_log_jump,
      'entropy_inequality_violation': self.entropy_inequality_violation,
      'component_residuals': self.component_residuals,
      'maximum_component_residual': self.maximum_component_residual,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeNormalClosureResult:
  """Local normal-closure evidence with global promotion explicitly closed."""

  status: MocReflectedDomainGlobalMixedRegimeNormalClosureStatus
  request: MocReflectedDomainGlobalMixedRegimeNormalClosureRequest | None
  closure_samples: tuple[MocReflectedDomainGlobalMixedRegimeNormalClosureSample, ...] = ()
  interface_lineage_verified: bool = False
  interface_audit_verified: bool = False
  characteristic_compatibility_consumed: bool = False
  characteristic_compatibility_audit_verified: bool = False
  ambient_state_profile_consumed: bool = False
  ambient_state_equation_verified: bool = False
  component_fluxes_measured: bool = False
  entropy_inequality_checked: bool = False
  entropy_inequality_verified: bool = False
  componentwise_residual_gate_verified: bool = False
  normal_closure_equation_consumed: bool = False
  normal_closure_verified: bool = False
  canonical_free_boundary_verified: bool = False
  global_coupling_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalMixedRegimeNormalClosureStatus,
    ):
      raise TypeError('status must be a typed normal-closure status')
    ####
    if self.request is not None and not isinstance(
      self.request,
      MocReflectedDomainGlobalMixedRegimeNormalClosureRequest,
    ):
      raise TypeError('request must be a typed normal-closure request')
    ####
    samples = tuple(self.closure_samples)
    if any(
      not isinstance(
        sample,
        MocReflectedDomainGlobalMixedRegimeNormalClosureSample,
      )
      for sample in samples
    ):
      raise TypeError('closure_samples must contain typed normal-closure samples')
    ####
    object.__setattr__(self, 'closure_samples', samples)
    for name in (
      'interface_lineage_verified',
      'interface_audit_verified',
      'characteristic_compatibility_consumed',
      'characteristic_compatibility_audit_verified',
      'ambient_state_profile_consumed',
      'ambient_state_equation_verified',
      'component_fluxes_measured',
      'entropy_inequality_checked',
      'entropy_inequality_verified',
      'componentwise_residual_gate_verified',
      'normal_closure_equation_consumed',
      'normal_closure_verified',
      'canonical_free_boundary_verified',
      'global_coupling_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    ####
    if self.canonical_free_boundary_verified or self.global_coupling_verified:
      raise ValueError('normal closure cannot claim canonical or global closure')
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError('normal closure must remain promotion-blocked')
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalMixedRegimeNormalClosureStatus
      .CONVERGED_LOCAL_RESEARCH_NORMAL_CLOSURE
      and self.interface_lineage_verified
      and self.interface_audit_verified
      and self.characteristic_compatibility_consumed
      and self.characteristic_compatibility_audit_verified
      and self.ambient_state_profile_consumed
      and self.ambient_state_equation_verified
      and self.component_fluxes_measured
      and self.entropy_inequality_checked
      and self.entropy_inequality_verified
      and self.componentwise_residual_gate_verified
      and self.normal_closure_equation_consumed
      and self.normal_closure_verified
      and self.closure_samples
    )
  ####

  @property
  def maximum_component_residual(self) -> float | None:
    if not self.closure_samples:
      return None
    return max(sample.maximum_component_residual for sample in self.closure_samples)
  ####

  @property
  def maximum_entropy_inequality_violation(self) -> float | None:
    if not self.closure_samples:
      return None
    return max(
      sample.entropy_inequality_violation for sample in self.closure_samples
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_NORMAL_CLOSURE_OPERATOR_ID,
      'model': MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_NORMAL_CLOSURE_MODEL,
      'status': self.status.value,
      'converged': self.converged,
      'closure_samples': [sample.as_report() for sample in self.closure_samples],
      'maximum_component_residual': self.maximum_component_residual,
      'maximum_entropy_inequality_violation': (
        self.maximum_entropy_inequality_violation
      ),
      'interface_lineage_verified': self.interface_lineage_verified,
      'interface_audit_verified': self.interface_audit_verified,
      'characteristic_compatibility_consumed': (
        self.characteristic_compatibility_consumed
      ),
      'characteristic_compatibility_audit_verified': (
        self.characteristic_compatibility_audit_verified
      ),
      'ambient_state_profile_consumed': self.ambient_state_profile_consumed,
      'ambient_state_equation_verified': self.ambient_state_equation_verified,
      'component_fluxes_measured': self.component_fluxes_measured,
      'entropy_inequality_checked': self.entropy_inequality_checked,
      'entropy_inequality_verified': self.entropy_inequality_verified,
      'componentwise_residual_gate_verified': (
        self.componentwise_residual_gate_verified
      ),
      'normal_closure_equation_consumed': self.normal_closure_equation_consumed,
      'normal_closure_verified': self.normal_closure_verified,
      'canonical_free_boundary_verified': False,
      'global_coupling_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'request': None if self.request is None else self.request.as_report(),
      'claim_status': (
        'research-only two-sided moving-interface normal closure; explicit '
        'ambient primitive state and gas-law lineage are required, while '
        'global/free-boundary closure and production promotion remain open'
      ),
      'message': self.message,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeNormalClosureAudit:
  """Independent replay of the local two-sided normal closure."""

  status: MocReflectedDomainGlobalMixedRegimeNormalClosureAuditStatus
  candidate: MocReflectedDomainGlobalMixedRegimeNormalClosureResult | None
  replay: MocReflectedDomainGlobalMixedRegimeNormalClosureResult | None
  interface_lineage_replayed: bool = False
  compatibility_lineage_replayed: bool = False
  ambient_profile_replayed: bool = False
  flux_replay_verified: bool = False
  entropy_replay_verified: bool = False
  independent_normal_closure_verified: bool = False
  canonical_free_boundary_verified: bool = False
  global_coupling_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalMixedRegimeNormalClosureAuditStatus,
    ):
      raise TypeError('status must be a typed normal-closure audit status')
    ####
    for name in ('candidate', 'replay'):
      value = getattr(self, name)
      if value is not None and not isinstance(
        value,
        MocReflectedDomainGlobalMixedRegimeNormalClosureResult,
      ):
        raise TypeError(f'{name} must be a typed normal-closure result')
    ####
    for name in (
      'interface_lineage_replayed',
      'compatibility_lineage_replayed',
      'ambient_profile_replayed',
      'flux_replay_verified',
      'entropy_replay_verified',
      'independent_normal_closure_verified',
      'canonical_free_boundary_verified',
      'global_coupling_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    ####
    if self.canonical_free_boundary_verified or self.global_coupling_verified:
      raise ValueError('normal-closure audit cannot claim global closure')
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError('normal-closure audit must remain promotion-blocked')
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalMixedRegimeNormalClosureAuditStatus
      .VERIFIED_LOCAL_RESEARCH_NORMAL_CLOSURE
      and self.independent_normal_closure_verified
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_NORMAL_CLOSURE_OPERATOR_ID,
      'audit_status': self.status.value,
      'converged': self.converged,
      'interface_lineage_replayed': self.interface_lineage_replayed,
      'compatibility_lineage_replayed': self.compatibility_lineage_replayed,
      'ambient_profile_replayed': self.ambient_profile_replayed,
      'flux_replay_verified': self.flux_replay_verified,
      'entropy_replay_verified': self.entropy_replay_verified,
      'independent_normal_closure_verified': (
        self.independent_normal_closure_verified
      ),
      'canonical_free_boundary_verified': False,
      'global_coupling_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'candidate': None if self.candidate is None else self.candidate.as_report(),
      'replay': None if self.replay is None else self.replay.as_report(),
      'message': self.message,
    }
  ####
####


def _failure(
  status: MocReflectedDomainGlobalMixedRegimeNormalClosureStatus,
  message: str,
  *,
  request: MocReflectedDomainGlobalMixedRegimeNormalClosureRequest | None = None,
  **values: Any,
) -> MocReflectedDomainGlobalMixedRegimeNormalClosureResult:
  return MocReflectedDomainGlobalMixedRegimeNormalClosureResult(
    status=status,
    request=request,
    message=message,
    **values,
  )
####


def _ambient_fluxes(
  state: MocReflectedDomainGlobalMixedRegimeNormalClosureAmbientState,
  interface_flux: MocReflectedDomainGlobalMixedRegimeTransonicInterfaceFluxSample,
  interface_normal_speed_m_s: float,
) -> tuple[float, float, float, float, float, float, float, float]:
  normal = interface_flux.normal_m
  tangent = interface_flux.tangent_m
  normal_velocity = (
    state.velocity_u_m_s * normal[0] + state.velocity_v_m_s * normal[1]
  )
  tangential_velocity = (
    state.velocity_u_m_s * tangent[0] + state.velocity_v_m_s * tangent[1]
  )
  relative_normal_velocity = normal_velocity - interface_normal_speed_m_s
  density = state.density_kg_m3
  pressure = state.static_pressure_Pa
  total_energy = state.total_energy_density_J_m3
  mass_flux = density * relative_normal_velocity
  normal_momentum_flux = (
    density * normal_velocity * relative_normal_velocity + pressure
  )
  tangential_momentum_flux = density * tangential_velocity * relative_normal_velocity
  total_energy_flux = (
    (total_energy + pressure) * normal_velocity
    - interface_normal_speed_m_s * total_energy
  )
  entropy_proxy_flux = mass_flux * state.entropy_proxy
  return (
    normal_velocity,
    relative_normal_velocity,
    tangential_velocity,
    mass_flux,
    normal_momentum_flux,
    tangential_momentum_flux,
    total_energy_flux,
    entropy_proxy_flux,
  )
####


def _interface_gamma(
  interface: MocReflectedDomainGlobalMixedRegimeTransonicInterfaceResult,
) -> float:
  request = interface.request
  if request is None:
    raise ValueError('interface request is required to recover exact gamma')
  frame_request = request.characteristic_frame.request
  if frame_request is None:
    raise ValueError(
      'characteristic-frame request is required to recover exact gamma'
    )
  equation_result = frame_request.upstream_state_equation
  if equation_result.request is None:
    raise ValueError(
      'upstream state-equation request is required to recover exact gamma'
    )
  gamma = _finite('interface_gamma', equation_result.request.target_gamma)
  if gamma <= 1.0:
    raise ValueError('interface_gamma must be greater than one')
  ####
  return gamma
####


def solve_reflected_domain_global_mixed_regime_normal_closure(
  request: MocReflectedDomainGlobalMixedRegimeNormalClosureRequest,
) -> MocReflectedDomainGlobalMixedRegimeNormalClosureResult:
  """Measure a strict two-sided local closure without global promotion."""

  status_type = MocReflectedDomainGlobalMixedRegimeNormalClosureStatus
  if not isinstance(request, MocReflectedDomainGlobalMixedRegimeNormalClosureRequest):
    return _failure(
      status_type.INVALID_INPUT,
      'request must be a typed normal-closure request',
    )
  ####
  interface = request.transonic_interface
  if not interface.converged:
    return _failure(
      status_type.INTERFACE_REQUIRED,
      'normal closure requires a converged transonic interface',
      request=request,
    )
  ####
  interface_audit = request.transonic_interface_audit
  if (
    interface_audit.status
    is not MocReflectedDomainGlobalMixedRegimeTransonicInterfaceAuditStatus
    .VERIFIED_LOCAL_RESEARCH_INTERFACE
    or not interface_audit.converged
  ):
    return _failure(
      status_type.INTERFACE_AUDIT_REQUIRED,
      'normal closure requires an independently replayed interface audit',
      request=request,
      interface_lineage_verified=interface_audit.candidate is interface,
    )
  ####
  if interface_audit.candidate is not interface:
    return _failure(
      status_type.INTERFACE_LINEAGE_FAILURE,
      'interface audit candidate must be the exact supplied interface object',
      request=request,
      interface_lineage_verified=False,
      interface_audit_verified=True,
    )
  ####
  compatibility = request.characteristic_compatibility
  if compatibility is None or not compatibility.converged:
    return _failure(
      status_type.CHARACTERISTIC_COMPATIBILITY_REQUIRED,
      'normal closure requires a converged admitted incoming-family '
      'compatibility result; subsonic data cannot be coerced into it',
      request=request,
      interface_lineage_verified=True,
      interface_audit_verified=True,
    )
  ####
  compatibility_audit = request.characteristic_compatibility_audit
  if compatibility_audit is None or not compatibility_audit.converged:
    return _failure(
      status_type.CHARACTERISTIC_COMPATIBILITY_AUDIT_REQUIRED,
      'normal closure requires an independently replayed compatibility audit',
      request=request,
      interface_lineage_verified=True,
      interface_audit_verified=True,
      characteristic_compatibility_consumed=True,
    )
  ####
  compatibility_request = compatibility.request
  equation_request = (
    None
    if compatibility_request is None
    else compatibility_request.equation_request
  )
  compatibility_interface = (
    None if equation_request is None else equation_request.transonic_interface
  )
  compatibility_interface_audit = (
    None
    if equation_request is None
    else equation_request.transonic_interface_audit
  )
  if (
    compatibility_audit.candidate is not compatibility
    or compatibility_interface is not interface
    or compatibility_interface_audit is not interface_audit
  ):
    return _failure(
      status_type.CHARACTERISTIC_COMPATIBILITY_LINEAGE_FAILURE,
      'compatibility must retain the exact interface and interface-audit '
      'objects supplied to normal closure',
      request=request,
      interface_lineage_verified=True,
      interface_audit_verified=True,
      characteristic_compatibility_consumed=True,
      characteristic_compatibility_audit_verified=False,
    )
  ####
  ambient_profile = request.ambient_state_profile
  if ambient_profile is None or not ambient_profile:
    return _failure(
      status_type.AMBIENT_STATE_REQUIRED,
      'normal closure requires an explicit ambient density, velocity, '
      'pressure, temperature, gamma, and gas-law state at every sample',
      request=request,
      interface_lineage_verified=True,
      interface_audit_verified=True,
      characteristic_compatibility_consumed=True,
      characteristic_compatibility_audit_verified=True,
    )
  ####
  interface_samples = tuple(interface.flux_samples)
  if len(ambient_profile) != len(interface_samples):
    return _failure(
      status_type.AMBIENT_STATE_LINEAGE_FAILURE,
      'ambient state profile must cover every exact interface sample once',
      request=request,
      interface_lineage_verified=True,
      interface_audit_verified=True,
      characteristic_compatibility_consumed=True,
      characteristic_compatibility_audit_verified=True,
    )
  ####
  closure_samples: list[MocReflectedDomainGlobalMixedRegimeNormalClosureSample] = []
  try:
    interface_gamma = _interface_gamma(interface)
    for interface_flux, ambient in zip(
      interface_samples,
      ambient_profile,
      strict=True,
    ):
      if ambient.sample_index != interface_flux.sample_index:
        return _failure(
          status_type.AMBIENT_STATE_LINEAGE_FAILURE,
          'ambient sample indices must exactly match interface sample indices',
          request=request,
          interface_lineage_verified=True,
          interface_audit_verified=True,
          characteristic_compatibility_consumed=True,
          characteristic_compatibility_audit_verified=True,
          ambient_state_profile_consumed=True,
        )
      ####
      point_delta = hypot(
        ambient.point_m[0] - interface_flux.point_m[0],
        ambient.point_m[1] - interface_flux.point_m[1],
      )
      if point_delta > request.point_tolerance_m:
        return _failure(
          status_type.AMBIENT_STATE_LINEAGE_FAILURE,
          'ambient state points must match exact interface points within the '
          'declared tolerance',
          request=request,
          interface_lineage_verified=True,
          interface_audit_verified=True,
          characteristic_compatibility_consumed=True,
          characteristic_compatibility_audit_verified=True,
          ambient_state_profile_consumed=True,
        )
      ####
      interior_frame = interface_flux.frame_sample
      gamma_residual = _relative_residual(ambient.gamma, interface_gamma)
      interior_gas_constant = (
        interior_frame.static_pressure_Pa
        / (interior_frame.density_kg_m3 * interior_frame.static_temperature_K)
      )
      gas_constant_residual = _relative_residual(
        ambient.specific_gas_constant_J_kg_K,
        interior_gas_constant,
      )
      ambient_eos_pressure = (
        ambient.density_kg_m3
        * ambient.specific_gas_constant_J_kg_K
        * ambient.static_temperature_K
      )
      eos_residual = _relative_residual(
        ambient.static_pressure_Pa,
        ambient_eos_pressure,
      )
      if (
        gamma_residual > request.state_tolerance
        or gas_constant_residual > request.state_tolerance
        or eos_residual > request.state_tolerance
      ):
        return _failure(
          status_type.AMBIENT_STATE_EQUATION_FAILURE,
          'ambient state must satisfy the supplied gas law and exact interior '
          'gamma/gas-constant lineage before flux closure',
          request=request,
          interface_lineage_verified=True,
          interface_audit_verified=True,
          characteristic_compatibility_consumed=True,
          characteristic_compatibility_audit_verified=True,
          ambient_state_profile_consumed=True,
          ambient_state_equation_verified=False,
        )
      ####
      (
        ambient_normal_velocity,
        ambient_relative_normal_velocity,
        ambient_tangential_velocity,
        ambient_mass_flux,
        ambient_normal_momentum_flux,
        ambient_tangential_momentum_flux,
        ambient_total_energy_flux,
        ambient_entropy_proxy_flux,
      ) = _ambient_fluxes(
        ambient,
        interface_flux,
        interface.request.interface_normal_speed_m_s,  # type: ignore[union-attr]
      )
      ####
      entropy_log_jump = ambient.entropy_log_proxy - _entropy_log(
        interface_flux.static_pressure_Pa,
        interface_flux.density_kg_m3,
        interface_gamma,
      )
      entropy_inequality_violation = max(
        0.0,
        -request.entropy_increase_sign * entropy_log_jump,
      )
      closure_samples.append(
        MocReflectedDomainGlobalMixedRegimeNormalClosureSample(
          sample_index=interface_flux.sample_index,
          interface_flux=interface_flux,
          ambient_state=ambient,
          ambient_normal_velocity_m_s=ambient_normal_velocity,
          ambient_relative_normal_velocity_m_s=ambient_relative_normal_velocity,
          ambient_tangential_velocity_m_s=ambient_tangential_velocity,
          ambient_mass_flux_kg_m2_s=ambient_mass_flux,
          ambient_normal_momentum_flux_Pa=ambient_normal_momentum_flux,
          ambient_tangential_momentum_flux_Pa=ambient_tangential_momentum_flux,
          ambient_total_energy_flux_W_m2=ambient_total_energy_flux,
          ambient_entropy_proxy_flux=ambient_entropy_proxy_flux,
          mass_residual=_relative_residual(
            interface_flux.mass_flux_kg_m2_s,
            ambient_mass_flux,
          ),
          normal_momentum_residual=_relative_residual(
            interface_flux.normal_momentum_flux_Pa,
            ambient_normal_momentum_flux,
          ),
          tangential_momentum_residual=_relative_residual(
            interface_flux.tangential_momentum_flux_Pa,
            ambient_tangential_momentum_flux,
          ),
          total_energy_residual=_relative_residual(
            interface_flux.total_energy_flux_W_m2,
            ambient_total_energy_flux,
          ),
          entropy_proxy_residual=_relative_residual(
            interface_flux.entropy_proxy_flux,
            ambient_entropy_proxy_flux,
          ),
          entropy_log_jump=entropy_log_jump,
          entropy_inequality_violation=entropy_inequality_violation,
        )
      )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      status_type.FLUX_DECOMPOSITION_FAILURE,
      f'two-sided normal-closure flux decomposition failed: {error}',
      request=request,
      interface_lineage_verified=True,
      interface_audit_verified=True,
      characteristic_compatibility_consumed=True,
      characteristic_compatibility_audit_verified=True,
      ambient_state_profile_consumed=True,
      ambient_state_equation_verified=False,
    )
  ####
  samples = tuple(closure_samples)
  component_gate = bool(
    samples
    and all(
      sample.maximum_component_residual <= request.component_tolerance
      for sample in samples
    )
  )
  entropy_gate = bool(
    samples
    and all(
      sample.entropy_inequality_violation <= request.entropy_tolerance
      for sample in samples
    )
  )
  normal_closure_verified = bool(component_gate and entropy_gate)
  status = (
    status_type.CONVERGED_LOCAL_RESEARCH_NORMAL_CLOSURE
    if normal_closure_verified
    else status_type.COMPLETED_RESEARCH_NORMAL_CLOSURE_WITH_OPEN_RESIDUAL
  )
  message = (
    'explicit ambient primitive state closed moving-interface mass, normal '
    'and tangential momentum, energy, entropy-proxy, and oriented entropy '
    'channels locally; global/free-boundary closure remains open'
    if normal_closure_verified
    else 'two-sided fluxes were measured, but one or more component or entropy '
    'gates remain open; no normal or global closure claim is made'
  )
  return MocReflectedDomainGlobalMixedRegimeNormalClosureResult(
    status=status,
    request=request,
    closure_samples=samples,
    interface_lineage_verified=True,
    interface_audit_verified=True,
    characteristic_compatibility_consumed=True,
    characteristic_compatibility_audit_verified=True,
    ambient_state_profile_consumed=True,
    ambient_state_equation_verified=True,
    component_fluxes_measured=True,
    entropy_inequality_checked=True,
    entropy_inequality_verified=entropy_gate,
    componentwise_residual_gate_verified=component_gate,
    normal_closure_equation_consumed=True,
    normal_closure_verified=normal_closure_verified,
    canonical_free_boundary_verified=False,
    global_coupling_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    message=message,
  )
####


def audit_reflected_domain_global_mixed_regime_normal_closure(
  result: MocReflectedDomainGlobalMixedRegimeNormalClosureResult,
) -> MocReflectedDomainGlobalMixedRegimeNormalClosureAudit:
  """Replay the exact normal-closure request and compare every channel."""

  audit_status = MocReflectedDomainGlobalMixedRegimeNormalClosureAuditStatus
  if not isinstance(
    result,
    MocReflectedDomainGlobalMixedRegimeNormalClosureResult,
  ):
    return MocReflectedDomainGlobalMixedRegimeNormalClosureAudit(
      status=audit_status.INVALID_INPUT,
      candidate=None,
      replay=None,
      message='result must be a typed normal-closure result',
    )
  ####
  if result.request is None or not result.converged:
    return MocReflectedDomainGlobalMixedRegimeNormalClosureAudit(
      status=audit_status.REPLAY_FAILURE,
      candidate=result,
      replay=None,
      message=(
        'independent replay requires a locally converged normal closure with '
        'its exact request retained'
      ),
    )
  ####
  try:
    replay = solve_reflected_domain_global_mixed_regime_normal_closure(
      result.request
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return MocReflectedDomainGlobalMixedRegimeNormalClosureAudit(
      status=audit_status.REPLAY_FAILURE,
      candidate=result,
      replay=None,
      message=f'independent normal-closure replay raised: {error}',
    )
  ####
  interface_lineage = bool(
    replay.request is result.request
    and replay.interface_lineage_verified == result.interface_lineage_verified
    and replay.interface_audit_verified == result.interface_audit_verified
  )
  compatibility_lineage = bool(
    replay.characteristic_compatibility_consumed
    == result.characteristic_compatibility_consumed
    and replay.characteristic_compatibility_audit_verified
    == result.characteristic_compatibility_audit_verified
  )
  ambient_profile = bool(
    replay.ambient_state_profile_consumed == result.ambient_state_profile_consumed
    and replay.ambient_state_equation_verified
    == result.ambient_state_equation_verified
  )
  fluxes = bool(
    replay.closure_samples == result.closure_samples
    and replay.component_fluxes_measured == result.component_fluxes_measured
    and replay.componentwise_residual_gate_verified
    == result.componentwise_residual_gate_verified
  )
  entropy = bool(
    replay.entropy_inequality_checked == result.entropy_inequality_checked
    and replay.entropy_inequality_verified == result.entropy_inequality_verified
    and replay.maximum_entropy_inequality_violation
    == result.maximum_entropy_inequality_violation
  )
  independent = bool(
    interface_lineage
    and compatibility_lineage
    and ambient_profile
    and fluxes
    and entropy
    and replay.normal_closure_verified == result.normal_closure_verified
  )
  return MocReflectedDomainGlobalMixedRegimeNormalClosureAudit(
    status=(
      audit_status.VERIFIED_LOCAL_RESEARCH_NORMAL_CLOSURE
      if independent
      else audit_status.LINEAGE_FAILURE
    ),
    candidate=result,
    replay=replay,
    interface_lineage_replayed=interface_lineage,
    compatibility_lineage_replayed=compatibility_lineage,
    ambient_profile_replayed=ambient_profile,
    flux_replay_verified=fluxes,
    entropy_replay_verified=entropy,
    independent_normal_closure_verified=independent,
    canonical_free_boundary_verified=False,
    global_coupling_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    message=(
      'independent replay reproduced the exact two-sided ambient state, '
      'moving flux channels, component residuals, and entropy inequality'
      if independent
      else 'independent replay did not reproduce every retained normal-closure '
      'channel'
    ),
  )
####
