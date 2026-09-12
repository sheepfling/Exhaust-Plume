"""Research-only characteristic/free-boundary march for a mixed-regime trace.

The mixed-regime characteristic contracts stop after admitting one contiguous
supersonic family.  This module consumes that exact family and applies the
existing ambient-pressure characteristic-intersection primitive to a seeded
boundary.  It makes the local free-boundary equation observable as a typed
operator instead of leaving it as an unconnected helper.

The first admitted state is the solver-owned anchor for this local march; the
remaining admitted samples are marched in their declared order.  The ambient
pressure profile is an explicit boundary condition and is checked against the
same sample coordinates.  This is a local pressure/tangency equation only. It
does not close the conservative state, entropy, centerline, second-family,
global feedback, or production shock-cell equations, and therefore cannot
make a canonical or production claim.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from math import atan2, hypot, isfinite, sin
from typing import Any

from exhaust_plume.models.moc.boundary import (
  MocFreeBoundaryPointResult,
  solve_ambient_pressure_free_boundary_point,
)
from exhaust_plume.models.moc.global_mixed_regime_upstream_characteristic_compatibility import (
  MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityAudit,
  MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityResult,
)
from exhaust_plume.models.moc.primitives import CharacteristicFamily, CharacteristicState

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_CHARACTERISTIC_FREE_BOUNDARY_OPERATOR_ID',
  'MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_CHARACTERISTIC_FREE_BOUNDARY_MODEL',
  'MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryStatus',
  'MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureSample',
  'MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryRequest',
  'MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryResult',
  'MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryAuditStatus',
  'MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryAudit',
  'solve_reflected_domain_global_mixed_regime_characteristic_free_boundary',
  'audit_reflected_domain_global_mixed_regime_characteristic_free_boundary',
)


MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_CHARACTERISTIC_FREE_BOUNDARY_OPERATOR_ID = (
  'op.moc.reflected-domain.global-mixed-regime-characteristic-free-boundary-v1'
)
MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_CHARACTERISTIC_FREE_BOUNDARY_MODEL = (
  'research-global-mixed-regime-characteristic-free-boundary-march-v1'
)


class MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryStatus(
  str,
  Enum,
):
  """Typed outcomes of the local characteristic/free-boundary march."""

  CONVERGED_LOCAL_RESEARCH_FREE_BOUNDARY = (
    'converged-local-research-characteristic-free-boundary'
  )
  COMPLETED_RESEARCH_FREE_BOUNDARY_WITH_OPEN_RESIDUAL = (
    'completed-research-characteristic-free-boundary-with-open-residual'
  )
  INVALID_INPUT = 'invalid_input'
  COMPATIBILITY_REQUIRED = (
    'characteristic-free-boundary-compatibility-required'
  )
  COMPATIBILITY_AUDIT_REQUIRED = (
    'characteristic-free-boundary-compatibility-audit-required'
  )
  COMPATIBILITY_LINEAGE_FAILURE = (
    'characteristic-free-boundary-compatibility-lineage-failure'
  )
  PRESSURE_PROFILE_REQUIRED = (
    'characteristic-free-boundary-pressure-profile-required'
  )
  PRESSURE_PROFILE_LINEAGE_FAILURE = (
    'characteristic-free-boundary-pressure-profile-lineage-failure'
  )
  SEED_REQUIRED = 'characteristic-free-boundary-seed-required'
  COVERAGE_FAILURE = 'characteristic-free-boundary-coverage-failure'
  POINT_FAILURE = 'characteristic-free-boundary-point-failure'
  GEOMETRY_FAILURE = 'characteristic-free-boundary-geometry-failure'
####


class MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryAuditStatus(
  str,
  Enum,
):
  """Typed outcomes of an independent local free-boundary replay."""

  VERIFIED_LOCAL_RESEARCH_FREE_BOUNDARY = (
    'verified-local-research-characteristic-free-boundary'
  )
  INVALID_INPUT = 'invalid_input'
  REPLAY_FAILURE = 'characteristic-free-boundary-audit-replay-failure'
  LINEAGE_FAILURE = 'characteristic-free-boundary-audit-lineage-failure'
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
    raise ValueError(f'{name} must be finite and positive')
  ####
  return numeric
####


def _segment_tangent_residual(
  previous_boundary: CharacteristicState,
  point_result: MocFreeBoundaryPointResult,
) -> float | None:
  """Measure the solved segment against its predicted boundary tangent."""

  if point_result.point_m is None or point_result.state is None:
    return None
  ####
  delta_x = point_result.point_m[0] - previous_boundary.x_m
  delta_y = point_result.point_m[1] - previous_boundary.y_m
  length = hypot(delta_x, delta_y)
  if not isfinite(length) or length <= 0.0:
    return float('inf')
  ####
  segment_angle = atan2(delta_y, delta_x)
  predicted_angle = 0.5 * (
    previous_boundary.theta_rad + point_result.state.theta_rad
  )
  residual = abs(sin(segment_angle - predicted_angle))
  return residual if isfinite(residual) else float('inf')
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


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureSample:
  """Ambient static pressure at one exact admitted-family coordinate."""

  sample_index: int
  point_m: tuple[float, float]
  ambient_pressure_Pa: float

  def __post_init__(self) -> None:
    if (
      isinstance(self.sample_index, bool)
      or not isinstance(self.sample_index, int)
      or self.sample_index < 0
    ):
      raise ValueError('sample_index must be a nonnegative integer')
    ####
    object.__setattr__(self, 'point_m', _point(self.point_m, 'point_m'))
    object.__setattr__(
      self,
      'ambient_pressure_Pa',
      _positive('ambient_pressure_Pa', self.ambient_pressure_Pa),
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'sample_index': self.sample_index,
      'point_m': list(self.point_m),
      'ambient_pressure_Pa': self.ambient_pressure_Pa,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryRequest:
  """Exact inputs for a seeded, explicitly oriented free-boundary march."""

  characteristic_compatibility: (
    MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityResult
  )
  characteristic_compatibility_audit: (
    MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityAudit
  )
  ambient_pressure_profile: tuple[
    MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureSample,
    ...
  ] | None = None
  seed_boundary_state: CharacteristicState | None = None
  boundary_family: CharacteristicFamily = CharacteristicFamily.PLUS
  position_tolerance_m: float = 1.0e-10
  pressure_tolerance: float = 1.0e-10
  tangent_tolerance_rad: float = 1.0e-8
  geometry_tolerance: float = 1.0e-8
  maximum_iterations: int = 16
  source: str = (
    MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_CHARACTERISTIC_FREE_BOUNDARY_MODEL
  )

  def __post_init__(self) -> None:
    if not isinstance(
      self.characteristic_compatibility,
      MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityResult,
    ):
      raise TypeError(
        'characteristic_compatibility must be a typed compatibility result'
      )
    ####
    if not isinstance(
      self.characteristic_compatibility_audit,
      MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityAudit,
    ):
      raise TypeError(
        'characteristic_compatibility_audit must be a typed compatibility audit'
      )
    ####
    if self.ambient_pressure_profile is not None:
      profile = tuple(self.ambient_pressure_profile)
      if any(
        not isinstance(
          sample,
          MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureSample,
        )
        for sample in profile
      ):
        raise TypeError(
          'ambient_pressure_profile must contain typed pressure samples'
        )
      ####
      object.__setattr__(self, 'ambient_pressure_profile', profile)
    ####
    if self.seed_boundary_state is not None and not isinstance(
      self.seed_boundary_state,
      CharacteristicState,
    ):
      raise TypeError('seed_boundary_state must be a CharacteristicState or None')
    ####
    if not isinstance(self.boundary_family, CharacteristicFamily):
      raise TypeError('boundary_family must be a CharacteristicFamily')
    ####
    for name in (
      'position_tolerance_m',
      'pressure_tolerance',
      'tangent_tolerance_rad',
      'geometry_tolerance',
    ):
      object.__setattr__(self, name, _positive(name, getattr(self, name)))
    ####
    if (
      isinstance(self.maximum_iterations, bool)
      or not isinstance(self.maximum_iterations, int)
      or self.maximum_iterations < 1
    ):
      raise ValueError('maximum_iterations must be a positive integer')
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
        MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_CHARACTERISTIC_FREE_BOUNDARY_OPERATOR_ID
      ),
      'model': (
        MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_CHARACTERISTIC_FREE_BOUNDARY_MODEL
      ),
      'characteristic_compatibility_status': (
        self.characteristic_compatibility.status.value
      ),
      'characteristic_compatibility_audit_status': (
        self.characteristic_compatibility_audit.status.value
      ),
      'incoming_sample_indices': (
        self.characteristic_compatibility.incoming_sample_indices
      ),
      'family': (
        None
        if self.characteristic_compatibility.family is None
        else self.characteristic_compatibility.family.value
      ),
      'ambient_pressure_profile': (
        None
        if self.ambient_pressure_profile is None
        else [sample.as_report() for sample in self.ambient_pressure_profile]
      ),
      'seed_boundary_state': (
        None
        if self.seed_boundary_state is None
        else {
          'x_m': self.seed_boundary_state.x_m,
          'y_m': self.seed_boundary_state.y_m,
          'theta_rad': self.seed_boundary_state.theta_rad,
          'mach': self.seed_boundary_state.mach,
          'gamma': self.seed_boundary_state.gamma,
        }
      ),
      'boundary_family': self.boundary_family.value,
      'position_tolerance_m': self.position_tolerance_m,
      'pressure_tolerance': self.pressure_tolerance,
      'tangent_tolerance_rad': self.tangent_tolerance_rad,
      'geometry_tolerance': self.geometry_tolerance,
      'maximum_iterations': self.maximum_iterations,
      'source': self.source,
      'research_only': True,
      'production_claim_allowed': False,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryResult:
  """Local free-boundary equation evidence below canonical promotion."""

  status: MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryStatus
  request: MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryRequest | None
  seed_boundary_state: CharacteristicState | None = None
  boundary_family: CharacteristicFamily | None = None
  solved_sample_indices: tuple[int, ...] = ()
  point_results: tuple[MocFreeBoundaryPointResult, ...] = ()
  boundary_states: tuple[CharacteristicState, ...] = ()
  boundary_points_m: tuple[tuple[float, float], ...] = ()
  compatibility_consumed: bool = False
  compatibility_audit_verified: bool = False
  boundary_family_state_consumed: bool = False
  pressure_profile_consumed: bool = False
  pressure_boundary_equation_consumed: bool = False
  free_boundary_equation_consumed: bool = False
  pressure_residual_gate_verified: bool = False
  tangent_residual_gate_verified: bool = False
  geometry_residual_gate_verified: bool = False
  forward_geometry_verified: bool = False
  canonical_free_boundary_verified: bool = False
  global_coupling_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryStatus,
    ):
      raise TypeError('status must be a typed free-boundary status')
    ####
    if self.request is not None and not isinstance(
      self.request,
      MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryRequest,
    ):
      raise TypeError('request must be a typed free-boundary request')
    ####
    if self.seed_boundary_state is not None and not isinstance(
      self.seed_boundary_state,
      CharacteristicState,
    ):
      raise TypeError('seed_boundary_state must be a CharacteristicState or None')
    ####
    if self.boundary_family is not None and not isinstance(
      self.boundary_family,
      CharacteristicFamily,
    ):
      raise TypeError('boundary_family must be a CharacteristicFamily or None')
    ####
    indices = tuple(int(index) for index in self.solved_sample_indices)
    if any(index < 0 for index in indices):
      raise ValueError('solved_sample_indices must be nonnegative')
    ####
    if len(set(indices)) != len(indices):
      raise ValueError('solved_sample_indices must be unique')
    ####
    point_results = tuple(self.point_results)
    if any(
      not isinstance(point, MocFreeBoundaryPointResult)
      for point in point_results
    ):
      raise TypeError('point_results must contain typed free-boundary points')
    ####
    states = tuple(self.boundary_states)
    if any(not isinstance(state, CharacteristicState) for state in states):
      raise TypeError('boundary_states must contain CharacteristicState values')
    ####
    points = tuple(_point(point, 'boundary_points_m') for point in self.boundary_points_m)
    if len(point_results) != len(indices):
      raise ValueError('point results must match solved sample indices')
    ####
    if len(states) != len(points):
      raise ValueError('boundary states and points must have equal lengths')
    ####
    if states and any(
      hypot(state.x_m - point[0], state.y_m - point[1]) > 1.0e-12
      for state, point in zip(states, points, strict=True)
    ):
      raise ValueError('boundary states must match boundary points')
    ####
    object.__setattr__(self, 'solved_sample_indices', indices)
    object.__setattr__(self, 'point_results', point_results)
    object.__setattr__(self, 'boundary_states', states)
    object.__setattr__(self, 'boundary_points_m', points)
    for name in (
      'compatibility_consumed',
      'compatibility_audit_verified',
      'boundary_family_state_consumed',
      'pressure_profile_consumed',
      'pressure_boundary_equation_consumed',
      'free_boundary_equation_consumed',
      'pressure_residual_gate_verified',
      'tangent_residual_gate_verified',
      'geometry_residual_gate_verified',
      'forward_geometry_verified',
      'canonical_free_boundary_verified',
      'global_coupling_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if self.boundary_family_state_consumed and self.boundary_family is None:
      raise ValueError(
        'a consumed boundary-family state requires an explicit boundary family'
      )
    ####
    if self.canonical_free_boundary_verified or self.global_coupling_verified:
      raise ValueError(
        'local characteristic free-boundary evidence cannot claim global closure'
      )
    ####
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError(
        'local characteristic free-boundary evidence must remain promotion-blocked'
      )
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def completed(self) -> bool:
    return bool(
      self.compatibility_consumed
      and self.compatibility_audit_verified
      and self.pressure_profile_consumed
      and self.boundary_family_state_consumed
      and self.pressure_boundary_equation_consumed
      and self.free_boundary_equation_consumed
      and self.point_results
      and len(self.point_results) == len(self.solved_sample_indices)
    )
  ####

  @property
  def equation_consumption_verified(self) -> bool:
    return bool(
      self.completed
      and self.pressure_residual_gate_verified
      and self.tangent_residual_gate_verified
      and self.geometry_residual_gate_verified
      and self.forward_geometry_verified
    )
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryStatus
      .CONVERGED_LOCAL_RESEARCH_FREE_BOUNDARY
      and self.equation_consumption_verified
    )
  ####

  @property
  def maximum_absolute_pressure_residual(self) -> float | None:
    values = tuple(
      abs(point.pressure_residual)
      for point in self.point_results
      if point.pressure_residual is not None
    )
    return max(values) if values else None
  ####

  @property
  def maximum_absolute_tangent_residual(self) -> float | None:
    values = tuple(
      abs(point.tangent_residual)
      for point in self.point_results
      if point.tangent_residual is not None
    )
    return max(values) if values else None
  ####

  @property
  def maximum_geometry_residual(self) -> float | None:
    values = tuple(
      point.geometry_residual
      for point in self.point_results
      if point.geometry_residual is not None
    )
    return max(values) if values else None
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': (
        MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_CHARACTERISTIC_FREE_BOUNDARY_OPERATOR_ID
      ),
      'model': (
        MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_CHARACTERISTIC_FREE_BOUNDARY_MODEL
      ),
      'status': self.status.value,
      'converged': self.converged,
      'completed': self.completed,
      'equation_consumption_verified': self.equation_consumption_verified,
      'seed_boundary_state': (
        None
        if self.seed_boundary_state is None
        else {
          'x_m': self.seed_boundary_state.x_m,
          'y_m': self.seed_boundary_state.y_m,
          'theta_rad': self.seed_boundary_state.theta_rad,
          'mach': self.seed_boundary_state.mach,
          'gamma': self.seed_boundary_state.gamma,
        }
      ),
      'boundary_family': (
        None if self.boundary_family is None else self.boundary_family.value
      ),
      'solved_sample_indices': self.solved_sample_indices,
      'point_results': [
        {
          'status': point.status.value,
          'family': point.family.value,
          'point_m': None if point.point_m is None else list(point.point_m),
          'pressure_residual': point.pressure_residual,
          'tangent_residual': point.tangent_residual,
          'geometry_residual': point.geometry_residual,
          'iterations': point.iterations,
          'intersection_status': point.intersection_status,
          'message': point.message,
        }
        for point in self.point_results
      ],
      'boundary_points_m': [list(point) for point in self.boundary_points_m],
      'maximum_absolute_pressure_residual': self.maximum_absolute_pressure_residual,
      'maximum_absolute_tangent_residual': self.maximum_absolute_tangent_residual,
      'maximum_geometry_residual': self.maximum_geometry_residual,
      'compatibility_consumed': self.compatibility_consumed,
      'compatibility_audit_verified': self.compatibility_audit_verified,
      'boundary_family_state_consumed': self.boundary_family_state_consumed,
      'pressure_profile_consumed': self.pressure_profile_consumed,
      'pressure_boundary_equation_consumed': self.pressure_boundary_equation_consumed,
      'free_boundary_equation_consumed': self.free_boundary_equation_consumed,
      'pressure_residual_gate_verified': self.pressure_residual_gate_verified,
      'tangent_residual_gate_verified': self.tangent_residual_gate_verified,
      'geometry_residual_gate_verified': self.geometry_residual_gate_verified,
      'forward_geometry_verified': self.forward_geometry_verified,
      'canonical_free_boundary_verified': False,
      'global_coupling_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'request': None if self.request is None else self.request.as_report(),
      'claim_status': (
        'research-only local pressure/tangency characteristic free-boundary '
        'march; conservative state, entropy, centerline, second-family, '
        'global fixed-point, physical shock-cell, and production gates remain open'
      ),
      'message': self.message,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryAudit:
  """Independent replay evidence for the local free-boundary equation."""

  status: MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryAuditStatus
  candidate: MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryResult | None
  replay: MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryResult | None
  request_lineage_replayed: bool = False
  compatibility_replayed: bool = False
  boundary_family_replayed: bool = False
  pressure_profile_replayed: bool = False
  point_replay_verified: bool = False
  boundary_replay_verified: bool = False
  independent_equation_verified: bool = False
  canonical_free_boundary_verified: bool = False
  global_coupling_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryAuditStatus,
    ):
      raise TypeError('status must be a typed free-boundary audit status')
    ####
    for name in ('candidate', 'replay'):
      value = getattr(self, name)
      if value is not None and not isinstance(
        value,
        MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryResult,
      ):
        raise TypeError(f'{name} must be a typed free-boundary result')
      ####
    ####
    for name in (
      'request_lineage_replayed',
      'compatibility_replayed',
      'boundary_family_replayed',
      'pressure_profile_replayed',
      'point_replay_verified',
      'boundary_replay_verified',
      'independent_equation_verified',
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
      raise ValueError('free-boundary audit cannot claim global closure')
    ####
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError('free-boundary audit must remain promotion-blocked')
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryAuditStatus
      .VERIFIED_LOCAL_RESEARCH_FREE_BOUNDARY
      and self.independent_equation_verified
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': (
        MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_CHARACTERISTIC_FREE_BOUNDARY_OPERATOR_ID
      ),
      'audit_status': self.status.value,
      'converged': self.converged,
      'request_lineage_replayed': self.request_lineage_replayed,
      'compatibility_replayed': self.compatibility_replayed,
      'boundary_family_replayed': self.boundary_family_replayed,
      'pressure_profile_replayed': self.pressure_profile_replayed,
      'point_replay_verified': self.point_replay_verified,
      'boundary_replay_verified': self.boundary_replay_verified,
      'independent_equation_verified': self.independent_equation_verified,
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
  status: MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryStatus,
  message: str,
  *,
  request: MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryRequest
  | None = None,
  **values: Any,
) -> MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryResult:
  return MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryResult(
    status=status,
    request=request,
    message=message,
    **values,
  )
####


def _interface_and_samples(
  compatibility: MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityResult,
) -> tuple[object, dict[int, Any]] | None:
  compatibility_request = compatibility.request
  if compatibility_request is None:
    return None
  ####
  equation_request = compatibility_request.equation_request
  if equation_request is None:
    return None
  ####
  if compatibility.family is None:
    return None
  ####
  interface = equation_request.transonic_interface
  interface_samples = {
    sample.sample_index: sample for sample in interface.flux_samples
  }
  return interface, interface_samples
####


def solve_reflected_domain_global_mixed_regime_characteristic_free_boundary(
  request: MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryRequest,
) -> MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryResult:
  """March the declared boundary family against an explicit pressure trace."""

  status_type = MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryStatus
  if not isinstance(
    request,
    MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryRequest,
  ):
    return _failure(
      status_type.INVALID_INPUT,
      'request must be a typed characteristic free-boundary request',
    )
  ####
  compatibility = request.characteristic_compatibility
  if not compatibility.converged:
    return _failure(
      status_type.COMPATIBILITY_REQUIRED,
      'characteristic free-boundary march requires a converged incoming-family '
      'compatibility result',
      request=request,
    )
  ####
  compatibility_audit = request.characteristic_compatibility_audit
  if (
    not compatibility_audit.converged
    or compatibility_audit.candidate is not compatibility
  ):
    return _failure(
      status_type.COMPATIBILITY_AUDIT_REQUIRED,
      'characteristic free-boundary march requires an independent compatibility '
      'audit of the exact supplied result',
      request=request,
      compatibility_consumed=True,
    )
  ####
  resolved = _interface_and_samples(compatibility)
  if resolved is None:
    return _failure(
      status_type.COMPATIBILITY_LINEAGE_FAILURE,
      'compatibility must retain the exact interface request and one declared '
      'incoming family',
      request=request,
      compatibility_consumed=True,
      compatibility_audit_verified=True,
    )
  ####
  interface, interface_samples = resolved
  del interface  # The exact interface is retained through the compatibility request.
  boundary_family = request.boundary_family
  incoming_indices = tuple(compatibility.incoming_sample_indices)
  compatibility_samples = tuple(compatibility.samples)
  if len(incoming_indices) < 2 or len(compatibility_samples) != len(incoming_indices):
    return _failure(
      status_type.COVERAGE_FAILURE,
      'at least two admitted incoming characteristic samples are required for '
      'a seeded free-boundary march',
      request=request,
      compatibility_consumed=True,
      compatibility_audit_verified=True,
    )
  ####
  if tuple(sample.sample_index for sample in compatibility_samples) != incoming_indices:
    return _failure(
      status_type.COMPATIBILITY_LINEAGE_FAILURE,
      'compatibility samples must retain the declared incoming sample order',
      request=request,
      compatibility_consumed=True,
      compatibility_audit_verified=True,
    )
  ####
  if request.seed_boundary_state is None:
    return _failure(
      status_type.SEED_REQUIRED,
      'the local free-boundary equation requires an explicit characteristic seed '
      'from the caller-owned solver frame',
      request=request,
      compatibility_consumed=True,
      compatibility_audit_verified=True,
    )
  ####
  seed = request.seed_boundary_state
  first_state = compatibility_samples[0].state
  seed_matches_anchor = bool(
    abs(seed.x_m - first_state.x_m) <= request.position_tolerance_m
    and abs(seed.y_m - first_state.y_m) <= request.position_tolerance_m
    and abs(seed.theta_rad - first_state.theta_rad) <= request.tangent_tolerance_rad
    and abs(seed.mach - first_state.mach) <= request.pressure_tolerance
    and abs(seed.gamma - first_state.gamma) <= request.pressure_tolerance
  )
  if not seed_matches_anchor:
    return _failure(
      status_type.COMPATIBILITY_LINEAGE_FAILURE,
      'the seeded local march must anchor at the first exact incoming '
      'characteristic state; an arbitrary boundary seed is not admitted',
      request=request,
      compatibility_consumed=True,
      compatibility_audit_verified=True,
    )
  ####
  pressure_profile = request.ambient_pressure_profile
  if pressure_profile is None or not pressure_profile:
    return _failure(
      status_type.PRESSURE_PROFILE_REQUIRED,
      'the free-boundary equation requires an explicit ambient-pressure profile '
      'at every admitted incoming sample',
      request=request,
      seed_boundary_state=seed,
      compatibility_consumed=True,
      compatibility_audit_verified=True,
    )
  ####
  if len(pressure_profile) != len(incoming_indices):
    return _failure(
      status_type.PRESSURE_PROFILE_LINEAGE_FAILURE,
      'ambient-pressure profile must cover every incoming sample exactly once',
      request=request,
      seed_boundary_state=seed,
      compatibility_consumed=True,
      compatibility_audit_verified=True,
    )
  ####
  for expected_index, pressure_sample, compatibility_sample in zip(
    incoming_indices,
    pressure_profile,
    compatibility_samples,
    strict=True,
  ):
    if pressure_sample.sample_index != expected_index:
      return _failure(
        status_type.PRESSURE_PROFILE_LINEAGE_FAILURE,
        'ambient-pressure samples must retain the exact incoming sample order',
        request=request,
        seed_boundary_state=seed,
        compatibility_consumed=True,
        compatibility_audit_verified=True,
        pressure_profile_consumed=False,
      )
    ####
    if (
      hypot(
        pressure_sample.point_m[0] - compatibility_sample.state.x_m,
        pressure_sample.point_m[1] - compatibility_sample.state.y_m,
      )
      > request.position_tolerance_m
    ):
      return _failure(
        status_type.PRESSURE_PROFILE_LINEAGE_FAILURE,
        'ambient-pressure sample coordinates must match the exact incoming '
        'characteristic coordinates',
        request=request,
        seed_boundary_state=seed,
        compatibility_consumed=True,
        compatibility_audit_verified=True,
        pressure_profile_consumed=False,
      )
    ####
  ####
  point_results: list[MocFreeBoundaryPointResult] = []
  boundary_states: list[CharacteristicState] = [seed]
  boundary_points: list[tuple[float, float]] = [(seed.x_m, seed.y_m)]
  solved_indices: list[int] = []
  previous_boundary = seed
  for compatibility_sample, pressure_sample in zip(
    compatibility_samples[1:],
    pressure_profile[1:],
    strict=True,
  ):
    interface_sample = interface_samples.get(compatibility_sample.sample_index)
    if interface_sample is None:
      return _failure(
        status_type.COMPATIBILITY_LINEAGE_FAILURE,
        'the exact interface is missing an admitted compatibility sample',
        request=request,
        seed_boundary_state=seed,
        solved_sample_indices=tuple(solved_indices),
        point_results=tuple(point_results),
        boundary_states=tuple(boundary_states),
        boundary_points_m=tuple(boundary_points),
        compatibility_consumed=True,
        compatibility_audit_verified=True,
        pressure_profile_consumed=True,
      )
    ####
    try:
      point_result = solve_ambient_pressure_free_boundary_point(
        compatibility_sample.state,
        previous_boundary,
        boundary_family,
        total_pressure_Pa=float(interface_sample.frame_sample.total_pressure_Pa),
        ambient_pressure_Pa=pressure_sample.ambient_pressure_Pa,
        position_tolerance_m=request.position_tolerance_m,
        pressure_tolerance=request.pressure_tolerance,
        maximum_iterations=request.maximum_iterations,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      return _failure(
        status_type.POINT_FAILURE,
        f'characteristic free-boundary point solve failed: {error}',
        request=request,
        seed_boundary_state=seed,
        solved_sample_indices=tuple(solved_indices),
        point_results=tuple(point_results),
        boundary_states=tuple(boundary_states),
        boundary_points_m=tuple(boundary_points),
        compatibility_consumed=True,
        compatibility_audit_verified=True,
        pressure_profile_consumed=True,
      )
    ####
    point_result = replace(
      point_result,
      tangent_residual=_segment_tangent_residual(
        previous_boundary,
        point_result,
      ),
    )
    point_results.append(point_result)
    solved_indices.append(compatibility_sample.sample_index)
    if not point_result.converged or point_result.state is None or point_result.point_m is None:
      return _failure(
        status_type.POINT_FAILURE,
        f'characteristic free-boundary point {compatibility_sample.sample_index} '
        f'did not converge: {point_result.message}',
        request=request,
        seed_boundary_state=seed,
        solved_sample_indices=tuple(solved_indices),
        point_results=tuple(point_results),
        boundary_states=tuple(boundary_states),
        boundary_points_m=tuple(boundary_points),
        compatibility_consumed=True,
        compatibility_audit_verified=True,
        pressure_profile_consumed=True,
      )
    ####
    if point_result.point_m[0] <= previous_boundary.x_m + request.position_tolerance_m:
      return _failure(
        status_type.GEOMETRY_FAILURE,
        f'characteristic free-boundary point {compatibility_sample.sample_index} '
        'is not strictly downstream of the previous boundary point',
        request=request,
        seed_boundary_state=seed,
        solved_sample_indices=tuple(solved_indices),
        point_results=tuple(point_results),
        boundary_states=tuple(boundary_states),
        boundary_points_m=tuple(boundary_points),
        compatibility_consumed=True,
        compatibility_audit_verified=True,
        pressure_profile_consumed=True,
      )
    ####
    boundary_states.append(point_result.state)
    boundary_points.append(point_result.point_m)
    previous_boundary = point_result.state
  ####
  pressure_gate = bool(
    all(
      point.pressure_residual is not None
      and abs(point.pressure_residual) <= request.pressure_tolerance
      for point in point_results
    )
  )
  tangent_gate = bool(
    all(
      point.tangent_residual is not None
      and abs(point.tangent_residual) <= request.tangent_tolerance_rad
      for point in point_results
    )
  )
  geometry_gate = bool(
    all(
      point.geometry_residual is not None
      and point.geometry_residual <= request.geometry_tolerance
      for point in point_results
    )
  )
  forward_gate = bool(
    len(boundary_points) == len(boundary_states) == len(solved_indices) + 1
    and all(
      right[0] > left[0] + request.position_tolerance_m
      for left, right in zip(boundary_points, boundary_points[1:])
    )
  )
  gates = bool(pressure_gate and tangent_gate and geometry_gate and forward_gate)
  status = (
    status_type.CONVERGED_LOCAL_RESEARCH_FREE_BOUNDARY
    if gates
    else status_type.COMPLETED_RESEARCH_FREE_BOUNDARY_WITH_OPEN_RESIDUAL
  )
  return MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryResult(
    status=status,
    request=request,
    seed_boundary_state=seed,
    solved_sample_indices=tuple(solved_indices),
    point_results=tuple(point_results),
    boundary_states=tuple(boundary_states),
    boundary_points_m=tuple(boundary_points),
    compatibility_consumed=True,
    compatibility_audit_verified=True,
    boundary_family=boundary_family,
    boundary_family_state_consumed=True,
    pressure_profile_consumed=True,
    pressure_boundary_equation_consumed=True,
    free_boundary_equation_consumed=True,
    pressure_residual_gate_verified=pressure_gate,
    tangent_residual_gate_verified=tangent_gate,
    geometry_residual_gate_verified=geometry_gate,
    forward_geometry_verified=forward_gate,
    canonical_free_boundary_verified=False,
    global_coupling_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    message=(
      'exact admitted incoming-family characteristics were marched against the '
      'explicit ambient-pressure boundary with local pressure, tangent, '
      'intersection, and forward-order gates; conservative/entropy/centerline '
      'and global closure remain open'
      if gates
      else 'the local characteristic/free-boundary march completed, but one or '
      'more pressure, tangent, intersection, or forward-order gates remain open; '
      'no global closure claim is made'
    ),
  )
####


def audit_reflected_domain_global_mixed_regime_characteristic_free_boundary(
  result: MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryResult,
) -> MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryAudit:
  """Replay the exact local march and compare every retained result field."""

  audit_status = (
    MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryAuditStatus
  )
  if not isinstance(
    result,
    MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryResult,
  ):
    return MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryAudit(
      status=audit_status.INVALID_INPUT,
      candidate=None,
      replay=None,
      message='result must be a typed characteristic free-boundary result',
    )
  ####
  if result.request is None:
    return MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryAudit(
      status=audit_status.REPLAY_FAILURE,
      candidate=result,
      replay=None,
      message='free-boundary replay requires the exact request frame',
    )
  ####
  try:
    replay = solve_reflected_domain_global_mixed_regime_characteristic_free_boundary(
      result.request
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryAudit(
      status=audit_status.REPLAY_FAILURE,
      candidate=result,
      replay=None,
      message=f'independent free-boundary replay raised: {error}',
    )
  ####
  request_lineage = bool(replay.request is result.request)
  compatibility_replayed = bool(
    replay.compatibility_consumed == result.compatibility_consumed
    and replay.compatibility_audit_verified == result.compatibility_audit_verified
  )
  boundary_family_replayed = bool(
    replay.boundary_family is result.boundary_family
    and replay.boundary_family_state_consumed
    == result.boundary_family_state_consumed
  )
  pressure_replayed = bool(
    replay.pressure_profile_consumed == result.pressure_profile_consumed
    and replay.pressure_boundary_equation_consumed
    == result.pressure_boundary_equation_consumed
  )
  point_replayed = bool(
    replay.point_results == result.point_results
    and replay.solved_sample_indices == result.solved_sample_indices
  )
  boundary_replayed = bool(
    replay.seed_boundary_state == result.seed_boundary_state
    and replay.boundary_states == result.boundary_states
    and replay.boundary_points_m == result.boundary_points_m
    and replay.free_boundary_equation_consumed
    == result.free_boundary_equation_consumed
    and replay.pressure_residual_gate_verified
    == result.pressure_residual_gate_verified
    and replay.tangent_residual_gate_verified
    == result.tangent_residual_gate_verified
    and replay.geometry_residual_gate_verified
    == result.geometry_residual_gate_verified
    and replay.forward_geometry_verified == result.forward_geometry_verified
  )
  independent = bool(
    request_lineage
    and compatibility_replayed
    and boundary_family_replayed
    and pressure_replayed
    and point_replayed
    and boundary_replayed
    and replay.status is result.status
    and replay.equation_consumption_verified == result.equation_consumption_verified
  )
  return MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryAudit(
    status=(
      audit_status.VERIFIED_LOCAL_RESEARCH_FREE_BOUNDARY
      if independent
      else audit_status.LINEAGE_FAILURE
    ),
    candidate=result,
    replay=replay,
    request_lineage_replayed=request_lineage,
    compatibility_replayed=compatibility_replayed,
    boundary_family_replayed=boundary_family_replayed,
    pressure_profile_replayed=pressure_replayed,
    point_replay_verified=point_replayed,
    boundary_replay_verified=boundary_replayed,
    independent_equation_verified=independent,
    canonical_free_boundary_verified=False,
    global_coupling_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    message=(
      'independent replay reproduced the exact seeded characteristic/free-boundary '
      'march, pressure profile lineage, points, states, and residual gates'
      if independent
      else 'independent replay did not reproduce the exact characteristic '
      'free-boundary equation evidence'
    ),
  )
####
