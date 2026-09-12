"""Research-only transonic interface admission for a mixed-regime frame.

The conservative-to-characteristic bridge retains a dimensional trace that may
be subsonic, sonic, or supersonic.  This module gives that trace an explicit
interface-facing decomposition without coercing subsonic data into a
supersonic MOC state.  It measures moving-control-volume mass, normal and
tangential momentum, total-energy, and entropy-proxy flux channels along the
declared interface frame.

The along-interface differences retained here are profile diagnostics and
component-wise admission evidence.  They are not Rankine-Hugoniot closure,
normal-shock fitting, a free-boundary solve, or a global fixed point.  The
result therefore remains research-only even when every local contract check
passes.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import hypot, isfinite, log
from typing import Any

from exhaust_plume.models.moc.global_mixed_regime_upstream_characteristic_frame import (
  MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicFrameResult,
  MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicFrameSample,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_TRANSONIC_INTERFACE_OPERATOR_ID',
  'MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_TRANSONIC_INTERFACE_MODEL',
  'MocReflectedDomainGlobalMixedRegimeTransonicInterfaceStatus',
  'MocReflectedDomainGlobalMixedRegimeTransonicInterfaceRequest',
  'MocReflectedDomainGlobalMixedRegimeTransonicInterfaceFluxSample',
  'MocReflectedDomainGlobalMixedRegimeTransonicInterfaceSegment',
  'MocReflectedDomainGlobalMixedRegimeTransonicInterfaceResult',
  'MocReflectedDomainGlobalMixedRegimeTransonicInterfaceAuditStatus',
  'MocReflectedDomainGlobalMixedRegimeTransonicInterfaceAudit',
  'solve_reflected_domain_global_mixed_regime_transonic_interface',
  'audit_reflected_domain_global_mixed_regime_transonic_interface',
)


MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_TRANSONIC_INTERFACE_OPERATOR_ID = (
  'op.moc.reflected-domain.global-mixed-regime-transonic-interface-v1'
)
MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_TRANSONIC_INTERFACE_MODEL = (
  'research-global-mixed-regime-transonic-interface-admission-v1'
)
_COMPONENT_NAMES = (
  'mass',
  'normal_momentum',
  'tangential_momentum',
  'total_energy',
  'entropy_proxy',
)


class MocReflectedDomainGlobalMixedRegimeTransonicInterfaceStatus(
  str,
  Enum,
):
  """Typed outcomes of one mixed-regime interface admission attempt."""

  CONVERGED_LOCAL_RESEARCH_INTERFACE = (
    'converged-local-research-transonic-interface'
  )
  COMPLETED_RESEARCH_INTERFACE_WITH_OPEN_COMPONENTS = (
    'completed-research-transonic-interface-with-open-components'
  )
  INVALID_INPUT = 'invalid_input'
  CHARACTERISTIC_FRAME_REQUIRED = (
    'transonic-interface-characteristic-frame-required'
  )
  INTERFACE_GEOMETRY_FAILURE = (
    'transonic-interface-interface-geometry-failure'
  )
  REGIME_SEPARATION_FAILURE = (
    'transonic-interface-regime-separation-failure'
  )
  STATE_FLUX_FAILURE = 'transonic-interface-state-flux-failure'
  CHARACTERISTIC_DATA_REQUIRED = (
    'transonic-interface-characteristic-data-required'
  )
####


class MocReflectedDomainGlobalMixedRegimeTransonicInterfaceAuditStatus(
  str,
  Enum,
):
  """Typed outcomes of an independent interface replay."""

  VERIFIED_LOCAL_RESEARCH_INTERFACE = (
    'verified-local-research-transonic-interface'
  )
  INVALID_INPUT = 'invalid_input'
  REPLAY_FAILURE = 'transonic-interface-audit-replay-failure'
  LINEAGE_FAILURE = 'transonic-interface-audit-lineage-failure'
####


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


def _unit_normal(value: object, name: str, tolerance: float) -> tuple[float, float]:
  normal = _point(value, name)
  length = hypot(*normal)
  if length <= 0.0 or abs(length - 1.0) > tolerance:
    raise ValueError(f'{name} must be a unit vector')
  ####
  return normal
####


def _relative_residual(actual: float, expected: float) -> float:
  return abs(actual - expected) / max(abs(actual), abs(expected), 1.0e-12)
####


def _normalise(value: tuple[float, float]) -> tuple[float, float]:
  length = hypot(*value)
  if length <= 0.0:
    raise ValueError('interface vector must have nonzero length')
  ####
  return value[0] / length, value[1] / length
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeTransonicInterfaceRequest:
  """Inputs for a typed transonic interface admission.

  ``interface_normals_m`` are caller-owned solver-frame normals.  They are
  checked, never inferred or reoriented.  ``interface_normal_speed_m_s`` is a
  scalar control-volume speed shared by the retained samples; zero is an
  explicit stationary-interface case.
  """

  characteristic_frame: (
    MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicFrameResult
  )
  interface_normals_m: tuple[tuple[float, float], ...]
  ambient_pressure_Pa: float
  interface_normal_speed_m_s: float = 0.0
  normal_tolerance: float = 1.0e-8
  state_tolerance: float = 1.0e-8
  sonic_tolerance: float = 1.0e-8
  component_tolerance: float = 1.0e-6
  require_supersonic_characteristic_data: bool = False
  source: str = MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_TRANSONIC_INTERFACE_MODEL

  def __post_init__(self) -> None:
    if not isinstance(
      self.characteristic_frame,
      MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicFrameResult,
    ):
      raise TypeError(
        'characteristic_frame must be a typed upstream characteristic frame'
      )
    ####
    normals = tuple(
      _unit_normal(normal, f'interface_normals_m[{index}]', self.normal_tolerance)
      for index, normal in enumerate(self.interface_normals_m)
    )
    if len(normals) < 2:
      raise ValueError('interface_normals_m must contain at least two normals')
    ####
    object.__setattr__(self, 'interface_normals_m', normals)
    for name in (
      'ambient_pressure_Pa',
      'normal_tolerance',
      'state_tolerance',
      'sonic_tolerance',
      'component_tolerance',
    ):
      object.__setattr__(self, name, _positive(name, getattr(self, name)))
    ####
    object.__setattr__(
      self,
      'interface_normal_speed_m_s',
      _finite('interface_normal_speed_m_s', self.interface_normal_speed_m_s),
    )
    if not isinstance(self.require_supersonic_characteristic_data, bool):
      raise TypeError('require_supersonic_characteristic_data must be a bool')
    ####
    source = str(self.source)
    if not source:
      raise ValueError('source must be non-empty')
    ####
    object.__setattr__(self, 'source', source)
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': (
        MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_TRANSONIC_INTERFACE_OPERATOR_ID
      ),
      'model': MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_TRANSONIC_INTERFACE_MODEL,
      'characteristic_frame_status': self.characteristic_frame.status.value,
      'characteristic_frame_converged': self.characteristic_frame.converged,
      'interface_normals_m': [list(normal) for normal in self.interface_normals_m],
      'ambient_pressure_Pa': self.ambient_pressure_Pa,
      'interface_normal_speed_m_s': self.interface_normal_speed_m_s,
      'normal_tolerance': self.normal_tolerance,
      'state_tolerance': self.state_tolerance,
      'sonic_tolerance': self.sonic_tolerance,
      'component_tolerance': self.component_tolerance,
      'require_supersonic_characteristic_data': (
        self.require_supersonic_characteristic_data
      ),
      'source': self.source,
      'research_only': True,
      'production_claim_allowed': False,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeTransonicInterfaceFluxSample:
  """Moving-control-volume flux channels at one exact frame sample."""

  sample_index: int
  frame_sample: (
    MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicFrameSample
  )
  normal_m: tuple[float, float]
  tangent_m: tuple[float, float]
  normal_velocity_m_s: float
  relative_normal_velocity_m_s: float
  tangential_velocity_m_s: float
  density_kg_m3: float
  static_pressure_Pa: float
  ambient_pressure_ratio: float
  mass_flux_kg_m2_s: float
  normal_momentum_flux_Pa: float
  tangential_momentum_flux_Pa: float
  total_energy_flux_W_m2: float
  entropy_proxy_flux: float
  entropy_log_proxy: float
  characteristic_data_admitted: bool = False

  def __post_init__(self) -> None:
    if (
      isinstance(self.sample_index, bool)
      or not isinstance(self.sample_index, int)
      or self.sample_index < 0
    ):
      raise ValueError('sample_index must be a nonnegative integer')
    ####
    if not isinstance(
      self.frame_sample,
      MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicFrameSample,
    ):
      raise TypeError('frame_sample must be a typed characteristic-frame sample')
    ####
    normal = _unit_normal(self.normal_m, 'normal_m', 1.0e-7)
    tangent = _point(self.tangent_m, 'tangent_m')
    tangent = _normalise(tangent)
    if abs(normal[0] * tangent[0] + normal[1] * tangent[1]) > 1.0e-7:
      raise ValueError('normal_m and tangent_m must be orthogonal')
    ####
    object.__setattr__(self, 'normal_m', normal)
    object.__setattr__(self, 'tangent_m', tangent)
    for name in (
      'normal_velocity_m_s',
      'relative_normal_velocity_m_s',
      'tangential_velocity_m_s',
      'density_kg_m3',
      'static_pressure_Pa',
      'ambient_pressure_ratio',
      'mass_flux_kg_m2_s',
      'normal_momentum_flux_Pa',
      'tangential_momentum_flux_Pa',
      'total_energy_flux_W_m2',
      'entropy_proxy_flux',
      'entropy_log_proxy',
    ):
      object.__setattr__(self, name, _finite(name, getattr(self, name)))
    ####
    if self.density_kg_m3 <= 0.0 or self.static_pressure_Pa <= 0.0:
      raise ValueError('interface flux sample density and pressure must be positive')
    ####
    if not isinstance(self.characteristic_data_admitted, bool):
      raise TypeError('characteristic_data_admitted must be a bool')
    ####
  ####
  @property
  def point_m(self) -> tuple[float, float]:
    return self.frame_sample.point_m
  ####

  @property
  def mach(self) -> float:
    return self.frame_sample.mach
  ####

  @property
  def regime(self) -> str:
    return self.frame_sample.regime
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'sample_index': self.sample_index,
      'point_m': list(self.point_m),
      'normal_m': list(self.normal_m),
      'tangent_m': list(self.tangent_m),
      'mach': self.mach,
      'regime': self.regime,
      'normal_velocity_m_s': self.normal_velocity_m_s,
      'relative_normal_velocity_m_s': self.relative_normal_velocity_m_s,
      'tangential_velocity_m_s': self.tangential_velocity_m_s,
      'density_kg_m3': self.density_kg_m3,
      'static_pressure_Pa': self.static_pressure_Pa,
      'ambient_pressure_ratio': self.ambient_pressure_ratio,
      'mass_flux_kg_m2_s': self.mass_flux_kg_m2_s,
      'normal_momentum_flux_Pa': self.normal_momentum_flux_Pa,
      'tangential_momentum_flux_Pa': self.tangential_momentum_flux_Pa,
      'total_energy_flux_W_m2': self.total_energy_flux_W_m2,
      'entropy_proxy_flux': self.entropy_proxy_flux,
      'entropy_log_proxy': self.entropy_log_proxy,
      'characteristic_data_admitted': self.characteristic_data_admitted,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeTransonicInterfaceSegment:
  """Component-wise along-interface variation between two exact samples."""

  segment_index: int
  start_sample_index: int
  end_sample_index: int
  frame_alignment_residual: float
  mass_residual: float
  normal_momentum_residual: float
  tangential_momentum_residual: float
  total_energy_residual: float
  entropy_proxy_residual: float
  entropy_log_proxy_jump: float

  def __post_init__(self) -> None:
    for name in ('segment_index', 'start_sample_index', 'end_sample_index'):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer')
      ####
    ####
    if self.end_sample_index != self.start_sample_index + 1:
      raise ValueError('interface segment sample indices must be consecutive')
    ####
    for name in (
      'frame_alignment_residual',
      'mass_residual',
      'normal_momentum_residual',
      'tangential_momentum_residual',
      'total_energy_residual',
      'entropy_proxy_residual',
      'entropy_log_proxy_jump',
    ):
      value = _finite(name, getattr(self, name))
      if value < 0.0:
        raise ValueError(f'{name} must be nonnegative')
      ####
      object.__setattr__(self, name, value)
    ####
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
      'segment_index': self.segment_index,
      'start_sample_index': self.start_sample_index,
      'end_sample_index': self.end_sample_index,
      'frame_alignment_residual': self.frame_alignment_residual,
      'mass_residual': self.mass_residual,
      'normal_momentum_residual': self.normal_momentum_residual,
      'tangential_momentum_residual': self.tangential_momentum_residual,
      'total_energy_residual': self.total_energy_residual,
      'entropy_proxy_residual': self.entropy_proxy_residual,
      'entropy_log_proxy_jump': self.entropy_log_proxy_jump,
      'component_residuals': self.component_residuals,
      'maximum_component_residual': self.maximum_component_residual,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeTransonicInterfaceResult:
  """Audited interface admission with all physical claims still closed."""

  status: MocReflectedDomainGlobalMixedRegimeTransonicInterfaceStatus
  request: MocReflectedDomainGlobalMixedRegimeTransonicInterfaceRequest | None
  flux_samples: tuple[
    MocReflectedDomainGlobalMixedRegimeTransonicInterfaceFluxSample, ...
  ] = ()
  segments: tuple[MocReflectedDomainGlobalMixedRegimeTransonicInterfaceSegment, ...] = ()
  frame_lineage_verified: bool = False
  interface_geometry_verified: bool = False
  normal_tangent_decomposition_verified: bool = False
  regime_separation_verified: bool = False
  component_fluxes_measured: bool = False
  entropy_channel_measured: bool = False
  ambient_pressure_context_verified: bool = False
  subsonic_interface_condition_admitted: bool = False
  supersonic_characteristic_data_admitted: bool = False
  componentwise_residual_gate_verified: bool = False
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
      MocReflectedDomainGlobalMixedRegimeTransonicInterfaceStatus,
    ):
      raise TypeError('status must be a typed transonic-interface status')
    ####
    if self.request is not None and not isinstance(
      self.request,
      MocReflectedDomainGlobalMixedRegimeTransonicInterfaceRequest,
    ):
      raise TypeError('request must be a typed transonic-interface request')
    ####
    samples = tuple(self.flux_samples)
    segments = tuple(self.segments)
    if any(
      not isinstance(
        sample,
        MocReflectedDomainGlobalMixedRegimeTransonicInterfaceFluxSample,
      )
      for sample in samples
    ):
      raise TypeError('flux_samples must contain typed interface samples')
    ####
    if any(
      not isinstance(
        segment,
        MocReflectedDomainGlobalMixedRegimeTransonicInterfaceSegment,
      )
      for segment in segments
    ):
      raise TypeError('segments must contain typed interface segments')
    ####
    if segments and len(segments) != len(samples) - 1:
      raise ValueError('interface segments must span every adjacent sample pair')
    ####
    object.__setattr__(self, 'flux_samples', samples)
    object.__setattr__(self, 'segments', segments)
    for name in (
      'frame_lineage_verified',
      'interface_geometry_verified',
      'normal_tangent_decomposition_verified',
      'regime_separation_verified',
      'component_fluxes_measured',
      'entropy_channel_measured',
      'ambient_pressure_context_verified',
      'subsonic_interface_condition_admitted',
      'supersonic_characteristic_data_admitted',
      'componentwise_residual_gate_verified',
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
      raise ValueError('transonic interface cannot claim upstream or global closure')
    ####
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError('transonic interface must remain promotion-blocked')
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      in {
        MocReflectedDomainGlobalMixedRegimeTransonicInterfaceStatus
        .CONVERGED_LOCAL_RESEARCH_INTERFACE,
        MocReflectedDomainGlobalMixedRegimeTransonicInterfaceStatus
        .COMPLETED_RESEARCH_INTERFACE_WITH_OPEN_COMPONENTS,
      }
      and self.frame_lineage_verified
      and self.interface_geometry_verified
      and self.normal_tangent_decomposition_verified
      and self.regime_separation_verified
      and self.component_fluxes_measured
      and self.entropy_channel_measured
      and self.ambient_pressure_context_verified
      and self.flux_samples
      and len(self.segments) == len(self.flux_samples) - 1
    )
  ####

  @property
  def component_names(self) -> tuple[str, ...]:
    return _COMPONENT_NAMES
  ####

  @property
  def supersonic_sample_count(self) -> int:
    return sum(sample.characteristic_data_admitted for sample in self.flux_samples)
  ####

  @property
  def subsonic_or_sonic_sample_count(self) -> int:
    return len(self.flux_samples) - self.supersonic_sample_count
  ####

  @property
  def mixed_regime(self) -> bool:
    return bool(self.supersonic_sample_count and self.subsonic_or_sonic_sample_count)
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': (
        MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_TRANSONIC_INTERFACE_OPERATOR_ID
      ),
      'model': MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_TRANSONIC_INTERFACE_MODEL,
      'status': self.status.value,
      'converged': self.converged,
      'component_names': self.component_names,
      'flux_samples': [sample.as_report() for sample in self.flux_samples],
      'segments': [segment.as_report() for segment in self.segments],
      'supersonic_sample_count': self.supersonic_sample_count,
      'subsonic_or_sonic_sample_count': self.subsonic_or_sonic_sample_count,
      'mixed_regime': self.mixed_regime,
      'frame_lineage_verified': self.frame_lineage_verified,
      'interface_geometry_verified': self.interface_geometry_verified,
      'normal_tangent_decomposition_verified': (
        self.normal_tangent_decomposition_verified
      ),
      'regime_separation_verified': self.regime_separation_verified,
      'component_fluxes_measured': self.component_fluxes_measured,
      'entropy_channel_measured': self.entropy_channel_measured,
      'ambient_pressure_context_verified': self.ambient_pressure_context_verified,
      'subsonic_interface_condition_admitted': (
        self.subsonic_interface_condition_admitted
      ),
      'supersonic_characteristic_data_admitted': (
        self.supersonic_characteristic_data_admitted
      ),
      'componentwise_residual_gate_verified': (
        self.componentwise_residual_gate_verified
      ),
      'upstream_characteristic_equation_consumed': False,
      'free_boundary_equation_consumed': False,
      'global_coupling_verified': False,
      'canonical_free_boundary_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'request': None if self.request is None else self.request.as_report(),
      'claim_status': (
        'research-only transonic interface admission; subsonic data remain a '
        'primitive interface condition, supersonic characteristic data are '
        'admitted only from the exact frame, and global/free-boundary closure '
        'remains open'
      ),
      'message': self.message,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeTransonicInterfaceAudit:
  """Independent replay of interface geometry, regimes, and flux channels."""

  status: MocReflectedDomainGlobalMixedRegimeTransonicInterfaceAuditStatus
  candidate: MocReflectedDomainGlobalMixedRegimeTransonicInterfaceResult | None
  replay: MocReflectedDomainGlobalMixedRegimeTransonicInterfaceResult | None
  frame_lineage_replayed: bool = False
  interface_geometry_replayed: bool = False
  regime_separation_replayed: bool = False
  component_fluxes_replayed: bool = False
  entropy_channel_replayed: bool = False
  independent_interface_verified: bool = False
  upstream_characteristic_equation_consumed: bool = False
  free_boundary_equation_consumed: bool = False
  global_coupling_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalMixedRegimeTransonicInterfaceAuditStatus,
    ):
      raise TypeError('status must be a typed transonic-interface audit status')
    ####
    for name in ('candidate', 'replay'):
      value = getattr(self, name)
      if value is not None and not isinstance(
        value,
        MocReflectedDomainGlobalMixedRegimeTransonicInterfaceResult,
      ):
        raise TypeError(f'{name} must be a typed transonic-interface result')
      ####
    ####
    for name in (
      'frame_lineage_replayed',
      'interface_geometry_replayed',
      'regime_separation_replayed',
      'component_fluxes_replayed',
      'entropy_channel_replayed',
      'independent_interface_verified',
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
      raise ValueError('transonic-interface audit cannot claim equation closure')
    ####
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError('transonic-interface audit must remain promotion-blocked')
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalMixedRegimeTransonicInterfaceAuditStatus
      .VERIFIED_LOCAL_RESEARCH_INTERFACE
      and self.independent_interface_verified
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': (
        MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_TRANSONIC_INTERFACE_OPERATOR_ID
      ),
      'audit_status': self.status.value,
      'converged': self.converged,
      'frame_lineage_replayed': self.frame_lineage_replayed,
      'interface_geometry_replayed': self.interface_geometry_replayed,
      'regime_separation_replayed': self.regime_separation_replayed,
      'component_fluxes_replayed': self.component_fluxes_replayed,
      'entropy_channel_replayed': self.entropy_channel_replayed,
      'independent_interface_verified': self.independent_interface_verified,
      'upstream_characteristic_equation_consumed': False,
      'free_boundary_equation_consumed': False,
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
  status: MocReflectedDomainGlobalMixedRegimeTransonicInterfaceStatus,
  message: str,
  *,
  request: MocReflectedDomainGlobalMixedRegimeTransonicInterfaceRequest | None = None,
  **values: Any,
) -> MocReflectedDomainGlobalMixedRegimeTransonicInterfaceResult:
  return MocReflectedDomainGlobalMixedRegimeTransonicInterfaceResult(
    status=status,
    request=request,
    message=message,
    **values,
  )
####


def _moving_flux_sample(
  sample_index: int,
  frame_sample: MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicFrameSample,
  normal: tuple[float, float],
  interface_normal_speed_m_s: float,
  ambient_pressure_Pa: float,
) -> MocReflectedDomainGlobalMixedRegimeTransonicInterfaceFluxSample:
  tangent = (-normal[1], normal[0])
  density = frame_sample.density_kg_m3
  velocity = (frame_sample.velocity_u_m_s, frame_sample.velocity_v_m_s)
  normal_velocity = velocity[0] * normal[0] + velocity[1] * normal[1]
  tangential_velocity = velocity[0] * tangent[0] + velocity[1] * tangent[1]
  relative_normal_velocity = normal_velocity - interface_normal_speed_m_s
  total_energy = frame_sample.conservative_state[3]
  mass_flux = density * relative_normal_velocity
  normal_momentum_flux = (
    density * normal_velocity * relative_normal_velocity
    + frame_sample.static_pressure_Pa
  )
  tangential_momentum_flux = density * tangential_velocity * relative_normal_velocity
  total_energy_flux = (
    (total_energy + frame_sample.static_pressure_Pa) * normal_velocity
    - interface_normal_speed_m_s * total_energy
  )
  entropy_log_proxy = frame_sample.entropy_log_residual
  entropy_proxy_flux = mass_flux * frame_sample.entropy_proxy
  return MocReflectedDomainGlobalMixedRegimeTransonicInterfaceFluxSample(
    sample_index=sample_index,
    frame_sample=frame_sample,
    normal_m=normal,
    tangent_m=tangent,
    normal_velocity_m_s=normal_velocity,
    relative_normal_velocity_m_s=relative_normal_velocity,
    tangential_velocity_m_s=tangential_velocity,
    density_kg_m3=density,
    static_pressure_Pa=frame_sample.static_pressure_Pa,
    ambient_pressure_ratio=frame_sample.static_pressure_Pa / ambient_pressure_Pa,
    mass_flux_kg_m2_s=mass_flux,
    normal_momentum_flux_Pa=normal_momentum_flux,
    tangential_momentum_flux_Pa=tangential_momentum_flux,
    total_energy_flux_W_m2=total_energy_flux,
    entropy_proxy_flux=entropy_proxy_flux,
    entropy_log_proxy=entropy_log_proxy,
    characteristic_data_admitted=frame_sample.characteristic_state is not None,
  )
####


def _segment(
  index: int,
  start: MocReflectedDomainGlobalMixedRegimeTransonicInterfaceFluxSample,
  end: MocReflectedDomainGlobalMixedRegimeTransonicInterfaceFluxSample,
) -> MocReflectedDomainGlobalMixedRegimeTransonicInterfaceSegment:
  chord = (
    end.point_m[0] - start.point_m[0],
    end.point_m[1] - start.point_m[1],
  )
  length = hypot(*chord)
  if length <= 0.0:
    raise ValueError('transonic interface samples must have positive separation')
  ####
  average_normal = _normalise(
    (
      start.normal_m[0] + end.normal_m[0],
      start.normal_m[1] + end.normal_m[1],
    )
  )
  frame_alignment = abs(chord[0] * average_normal[0] + chord[1] * average_normal[1]) / length
  return MocReflectedDomainGlobalMixedRegimeTransonicInterfaceSegment(
    segment_index=index,
    start_sample_index=start.sample_index,
    end_sample_index=end.sample_index,
    frame_alignment_residual=frame_alignment,
    mass_residual=_relative_residual(
      start.mass_flux_kg_m2_s,
      end.mass_flux_kg_m2_s,
    ),
    normal_momentum_residual=_relative_residual(
      start.normal_momentum_flux_Pa,
      end.normal_momentum_flux_Pa,
    ),
    tangential_momentum_residual=_relative_residual(
      start.tangential_momentum_flux_Pa,
      end.tangential_momentum_flux_Pa,
    ),
    total_energy_residual=_relative_residual(
      start.total_energy_flux_W_m2,
      end.total_energy_flux_W_m2,
    ),
    entropy_proxy_residual=_relative_residual(
      start.entropy_proxy_flux,
      end.entropy_proxy_flux,
    ),
    entropy_log_proxy_jump=abs(
      log(end.frame_sample.entropy_proxy / start.frame_sample.entropy_proxy)
    ),
  )
####


def solve_reflected_domain_global_mixed_regime_transonic_interface(
  request: MocReflectedDomainGlobalMixedRegimeTransonicInterfaceRequest,
) -> MocReflectedDomainGlobalMixedRegimeTransonicInterfaceResult:
  """Admit exact mixed-regime frame data without solving the global field."""

  status_type = MocReflectedDomainGlobalMixedRegimeTransonicInterfaceStatus
  if not isinstance(
    request,
    MocReflectedDomainGlobalMixedRegimeTransonicInterfaceRequest,
  ):
    return _failure(
      status_type.INVALID_INPUT,
      'request must be a typed transonic-interface request',
    )
  ####
  frame = request.characteristic_frame
  if not frame.converged:
    return _failure(
      status_type.CHARACTERISTIC_FRAME_REQUIRED,
      'transonic interface requires a converged exact primitive boundary frame',
      request=request,
    )
  ####
  frame_samples = tuple(frame.samples)
  if len(frame_samples) != len(request.interface_normals_m) or len(frame_samples) < 2:
    return _failure(
      status_type.INTERFACE_GEOMETRY_FAILURE,
      'interface normals must cover every exact characteristic-frame sample',
      request=request,
      frame_lineage_verified=True,
    )
  ####
  if any(
    second.point_m[0] <= first.point_m[0]
    for first, second in zip(frame_samples, frame_samples[1:])
  ):
    return _failure(
      status_type.INTERFACE_GEOMETRY_FAILURE,
      'characteristic-frame points must remain strictly ordered in x',
      request=request,
      frame_lineage_verified=True,
    )
  ####
  flux_samples: list[
    MocReflectedDomainGlobalMixedRegimeTransonicInterfaceFluxSample
  ] = []
  try:
    for index, (frame_sample, normal) in enumerate(
      zip(frame_samples, request.interface_normals_m, strict=True)
    ):
      characteristic = frame_sample.characteristic_state
      genuinely_supersonic = frame_sample.mach > 1.0 + request.sonic_tolerance
      if genuinely_supersonic != (characteristic is not None):
        return _failure(
          status_type.REGIME_SEPARATION_FAILURE,
          'characteristic data must be present exactly for genuinely supersonic '
          f'samples; sample {index} has Mach={frame_sample.mach}',
          request=request,
          frame_lineage_verified=True,
          interface_geometry_verified=True,
        )
      ####
      if characteristic is not None:
        if (
          abs(characteristic.x_m - frame_sample.point_m[0])
          > request.state_tolerance
          or abs(characteristic.y_m - frame_sample.point_m[1])
          > request.state_tolerance
          or abs(characteristic.mach - frame_sample.mach)
          > request.state_tolerance
          or abs(characteristic.theta_rad - frame_sample.flow_angle_rad)
          > request.state_tolerance
          or characteristic.gamma <= 1.0
        ):
          return _failure(
            status_type.REGIME_SEPARATION_FAILURE,
            f'supersonic characteristic sample {index} does not retain exact '
            'frame coordinates or primitive state',
            request=request,
            frame_lineage_verified=True,
            interface_geometry_verified=True,
          )
        ####
      ####
      flux_samples.append(
        _moving_flux_sample(
          index,
          frame_sample,
          normal,
          request.interface_normal_speed_m_s,
          request.ambient_pressure_Pa,
        )
      )
    ####
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      status_type.STATE_FLUX_FAILURE,
      f'transonic interface flux decomposition failed: {error}',
      request=request,
      frame_lineage_verified=True,
      interface_geometry_verified=True,
    )
  ####
  samples = tuple(flux_samples)
  segments: tuple[MocReflectedDomainGlobalMixedRegimeTransonicInterfaceSegment, ...]
  try:
    segments = tuple(
      _segment(index, start, end)
      for index, (start, end) in enumerate(zip(samples, samples[1:]))
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      status_type.INTERFACE_GEOMETRY_FAILURE,
      f'transonic interface segment residuals failed: {error}',
      request=request,
      flux_samples=samples,
      frame_lineage_verified=True,
      interface_geometry_verified=False,
      normal_tangent_decomposition_verified=True,
      regime_separation_verified=True,
      component_fluxes_measured=True,
      entropy_channel_measured=True,
      ambient_pressure_context_verified=True,
    )
  ####
  subsonic_admitted = any(not sample.characteristic_data_admitted for sample in samples)
  supersonic_admitted = all(
    sample.characteristic_data_admitted == (
      sample.frame_sample.mach > 1.0 + request.sonic_tolerance
    )
    for sample in samples
  ) and any(sample.characteristic_data_admitted for sample in samples)
  component_gate = bool(
    segments
    and all(
      segment.frame_alignment_residual <= request.normal_tolerance
      and segment.entropy_log_proxy_jump <= request.component_tolerance
      and segment.maximum_component_residual <= request.component_tolerance
      for segment in segments
    )
  )
  if request.require_supersonic_characteristic_data and not supersonic_admitted:
    return _failure(
      status_type.CHARACTERISTIC_DATA_REQUIRED,
      'the interface request requires an exact genuinely supersonic '
      'characteristic sample, but the retained frame has none',
      request=request,
      flux_samples=samples,
      segments=segments,
      frame_lineage_verified=True,
      interface_geometry_verified=True,
      normal_tangent_decomposition_verified=True,
      regime_separation_verified=True,
      component_fluxes_measured=True,
      entropy_channel_measured=True,
      ambient_pressure_context_verified=True,
      subsonic_interface_condition_admitted=subsonic_admitted,
      supersonic_characteristic_data_admitted=False,
      componentwise_residual_gate_verified=component_gate,
    )
  ####
  status = (
    status_type.CONVERGED_LOCAL_RESEARCH_INTERFACE
    if component_gate
    else status_type.COMPLETED_RESEARCH_INTERFACE_WITH_OPEN_COMPONENTS
  )
  message = (
    'exact mixed-regime boundary frame was decomposed into moving-interface '
    'mass, normal/tangential momentum, energy, and entropy-proxy channels; '
    'the upstream characteristic/free-boundary equation remains separate'
    if component_gate
    else 'exact mixed-regime boundary frame was admitted and decomposed, but '
    'one or more along-interface component residuals remain open; no flux '
    'continuity or global closure claim is made'
  )
  return MocReflectedDomainGlobalMixedRegimeTransonicInterfaceResult(
    status=status,
    request=request,
    flux_samples=samples,
    segments=segments,
    frame_lineage_verified=True,
    interface_geometry_verified=True,
    normal_tangent_decomposition_verified=True,
    regime_separation_verified=True,
    component_fluxes_measured=True,
    entropy_channel_measured=True,
    ambient_pressure_context_verified=True,
    subsonic_interface_condition_admitted=subsonic_admitted,
    supersonic_characteristic_data_admitted=supersonic_admitted,
    componentwise_residual_gate_verified=component_gate,
    upstream_characteristic_equation_consumed=False,
    free_boundary_equation_consumed=False,
    global_coupling_verified=False,
    canonical_free_boundary_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    message=message,
  )
####


def audit_reflected_domain_global_mixed_regime_transonic_interface(
  result: MocReflectedDomainGlobalMixedRegimeTransonicInterfaceResult,
) -> MocReflectedDomainGlobalMixedRegimeTransonicInterfaceAudit:
  """Replay the exact interface admission and compare every retained channel."""

  audit_status = MocReflectedDomainGlobalMixedRegimeTransonicInterfaceAuditStatus
  if not isinstance(
    result,
    MocReflectedDomainGlobalMixedRegimeTransonicInterfaceResult,
  ):
    return MocReflectedDomainGlobalMixedRegimeTransonicInterfaceAudit(
      status=audit_status.INVALID_INPUT,
      candidate=None,
      replay=None,
      message='result must be a typed transonic-interface result',
    )
  ####
  if result.request is None or not result.converged:
    return MocReflectedDomainGlobalMixedRegimeTransonicInterfaceAudit(
      status=audit_status.REPLAY_FAILURE,
      candidate=result,
      replay=None,
      message=(
        'independent replay requires a locally converged transonic interface '
        'with its exact request retained'
      ),
    )
  ####
  try:
    replay = solve_reflected_domain_global_mixed_regime_transonic_interface(
      result.request
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return MocReflectedDomainGlobalMixedRegimeTransonicInterfaceAudit(
      status=audit_status.REPLAY_FAILURE,
      candidate=result,
      replay=None,
      message=f'independent transonic-interface replay raised: {error}',
    )
  ####
  lineage = bool(
    replay.request is result.request
    and replay.frame_lineage_verified == result.frame_lineage_verified
    and replay.interface_geometry_verified == result.interface_geometry_verified
  )
  regimes = bool(
    replay.regime_separation_verified == result.regime_separation_verified
    and replay.supersonic_characteristic_data_admitted
    == result.supersonic_characteristic_data_admitted
    and replay.subsonic_interface_condition_admitted
    == result.subsonic_interface_condition_admitted
  )
  channels = bool(
    replay.flux_samples == result.flux_samples
    and replay.segments == result.segments
    and replay.component_fluxes_measured == result.component_fluxes_measured
  )
  entropy = bool(
    replay.entropy_channel_measured == result.entropy_channel_measured
    and all(
      sample.entropy_log_proxy == replay_sample.entropy_log_proxy
      for sample, replay_sample in zip(
        result.flux_samples,
        replay.flux_samples,
        strict=True,
      )
    )
  )
  independent = bool(lineage and regimes and channels and entropy)
  return MocReflectedDomainGlobalMixedRegimeTransonicInterfaceAudit(
    status=(
      audit_status.VERIFIED_LOCAL_RESEARCH_INTERFACE
      if independent
      else audit_status.LINEAGE_FAILURE
    ),
    candidate=result,
    replay=replay,
    frame_lineage_replayed=lineage,
    interface_geometry_replayed=lineage,
    regime_separation_replayed=regimes,
    component_fluxes_replayed=channels,
    entropy_channel_replayed=entropy,
    independent_interface_verified=independent,
    upstream_characteristic_equation_consumed=False,
    free_boundary_equation_consumed=False,
    global_coupling_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    message=(
      'independent replay reproduced the exact interface frame, regime gate, '
      'component flux channels, and entropy-proxy channel'
      if independent
      else 'independent replay did not reproduce every retained interface channel'
    ),
  )
####
