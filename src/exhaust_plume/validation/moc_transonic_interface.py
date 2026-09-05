"""Independent audit for the bounded transonic shock-interface handoff."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import hypot, isclose, log, pi, sqrt
from typing import Any

from exhaust_plume.models.moc.primitives import CharacteristicState
from exhaust_plume.models.moc.transonic_interface import (
  MocTransonicShockInterfaceSample,
  MocTransonicShockInterfaceProfile,
  MocTransonicShockInterfaceProfileBuildResult,
  MocTransonicShockInterfaceProfileBuildStatus,
  MocTransonicShockInterfaceResult,
  MocTransonicShockInterfaceStatus,
)
from exhaust_plume.models.moc.transonic_placement import (
  MocTransonicPlacementStatus,
)
from exhaust_plume.models.moc.transonic_transition import (
  MocTransonicShockGeometryAudit,
  measure_moc_transonic_shock_geometry,
)
from exhaust_plume.validation.moc_transonic_placement import (
  measure_moc_transonic_placement,
)

__all__ = (
  'MocTransonicShockInterfaceAuditStatus',
  'MocTransonicShockInterfaceAudit',
  'measure_moc_transonic_shock_interface',
  'MocTransonicShockInterfaceProfileAuditStatus',
  'MocTransonicShockInterfaceProfileAudit',
  'measure_moc_transonic_shock_interface_profile',
  'MocTransonicShockInterfaceProfileBuildAuditStatus',
  'MocTransonicShockInterfaceProfileBuildAudit',
  'measure_moc_transonic_shock_interface_profile_build',
)


class MocTransonicShockInterfaceAuditStatus(str, Enum):
  """Independent audit outcome for one local interface handoff."""

  VERIFIED = 'verified-transonic-shock-interface-audit'
  RESULT_FAILURE = 'transonic-shock-interface-result-failure'
####


class MocTransonicShockInterfaceProfileAuditStatus(str, Enum):
  """Independent audit outcome for a cross-section interface profile."""

  VERIFIED = 'verified-transonic-shock-interface-profile-audit'
  RESULT_FAILURE = 'transonic-shock-interface-profile-result-failure'
####


class MocTransonicShockInterfaceProfileBuildAuditStatus(str, Enum):
  """Independent audit outcome for a solver-owned profile derivation."""

  VERIFIED = 'verified-normal-shock-interface-profile-build-audit'
  RESULT_FAILURE = 'normal-shock-interface-profile-build-result-failure'
####


@dataclass(frozen=True, slots=True)
class MocTransonicShockInterfaceProfileAudit:
  """Re-derived profile geometry, regimes, and scalar thermodynamics."""

  status: MocTransonicShockInterfaceProfileAuditStatus
  profile: MocTransonicShockInterfaceProfile | None
  sample_count: int = 0
  cross_section_verified: bool = False
  ordinate_verified: bool = False
  regime_verified: bool = False
  thermodynamics_verified: bool = False
  shock_loss_verified: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocTransonicShockInterfaceProfileAuditStatus,
    ):
      raise TypeError(
        'status must be a MocTransonicShockInterfaceProfileAuditStatus'
      )
    ####
    if self.profile is not None and not isinstance(
      self.profile,
      MocTransonicShockInterfaceProfile,
    ):
      raise TypeError(
        'profile must be a MocTransonicShockInterfaceProfile or None'
      )
    ####
    if (
      isinstance(self.sample_count, bool)
      or not isinstance(self.sample_count, int)
      or self.sample_count < 0
    ):
      raise ValueError('sample_count must be a nonnegative integer')
    ####
    for name in (
      'cross_section_verified',
      'ordinate_verified',
      'regime_verified',
      'thermodynamics_verified',
      'shock_loss_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status is MocTransonicShockInterfaceProfileAuditStatus.VERIFIED
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'sample_count': self.sample_count,
      'cross_section_verified': self.cross_section_verified,
      'ordinate_verified': self.ordinate_verified,
      'regime_verified': self.regime_verified,
      'thermodynamics_verified': self.thermodynamics_verified,
      'shock_loss_verified': self.shock_loss_verified,
      'profile_id': None if self.profile is None else self.profile.profile_id,
      'physical_closure_verified': False,
      'production_claim_allowed': False,
      'message': self.message,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocTransonicShockInterfaceProfileBuildAudit:
  """Re-derive the normal-shock mapping behind a built profile."""

  status: MocTransonicShockInterfaceProfileBuildAuditStatus
  result_status: MocTransonicShockInterfaceProfileBuildStatus
  profile_audit: MocTransonicShockInterfaceProfileAudit | None
  rederived: bool
  upstream_profile_verified: bool
  normal_alignment_verified: bool
  downstream_state_verified: bool
  maximum_state_residual: float | None
  maximum_pressure_residual: float | None
  maximum_total_pressure_residual: float | None
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocTransonicShockInterfaceProfileBuildAuditStatus,
    ):
      raise TypeError(
        'status must be a MocTransonicShockInterfaceProfileBuildAuditStatus'
      )
    ####
    if not isinstance(
      self.result_status,
      MocTransonicShockInterfaceProfileBuildStatus,
    ):
      raise TypeError(
        'result_status must be a MocTransonicShockInterfaceProfileBuildStatus'
      )
    ####
    if self.profile_audit is not None and not isinstance(
      self.profile_audit,
      MocTransonicShockInterfaceProfileAudit,
    ):
      raise TypeError(
        'profile_audit must be a MocTransonicShockInterfaceProfileAudit or None'
      )
    ####
    for name in (
      'rederived',
      'upstream_profile_verified',
      'normal_alignment_verified',
      'downstream_state_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    for name in (
      'maximum_state_residual',
      'maximum_pressure_residual',
      'maximum_total_pressure_residual',
    ):
      value = getattr(self, name)
      if value is None:
        continue
      ####
      numeric = float(value)
      if numeric < 0.0:
        raise ValueError(f'{name} must be nonnegative when supplied')
      ####
      object.__setattr__(self, name, numeric)
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status is MocTransonicShockInterfaceProfileBuildAuditStatus.VERIFIED
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'result_status': self.result_status.value,
      'converged': self.converged,
      'rederived': self.rederived,
      'upstream_profile_verified': self.upstream_profile_verified,
      'normal_alignment_verified': self.normal_alignment_verified,
      'downstream_state_verified': self.downstream_state_verified,
      'maximum_state_residual': self.maximum_state_residual,
      'maximum_pressure_residual': self.maximum_pressure_residual,
      'maximum_total_pressure_residual': self.maximum_total_pressure_residual,
      'profile_audit': (
        None
        if self.profile_audit is None
        else self.profile_audit.as_report()
      ),
      'physical_closure_verified': False,
      'production_claim_allowed': False,
      'message': self.message,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocTransonicShockInterfaceAudit:
  """Re-derived placement, geometry, and state-handoff evidence."""

  status: MocTransonicShockInterfaceAuditStatus
  result_status: MocTransonicShockInterfaceStatus
  rederived: bool
  placement_verified: bool
  geometry_verified: bool
  upstream_state_verified: bool
  frontier_state_verified: bool
  upstream_pressure_verified: bool
  frontier_pressure_verified: bool
  downstream_state_verified: bool
  upstream_state_residual: float | None
  frontier_state_residual: float | None
  upstream_pressure_residual: float | None
  frontier_pressure_residual: float | None
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocTransonicShockInterfaceAuditStatus):
      raise TypeError(
        'status must be a MocTransonicShockInterfaceAuditStatus'
      )
    ####
    if not isinstance(self.result_status, MocTransonicShockInterfaceStatus):
      raise TypeError(
        'result_status must be a MocTransonicShockInterfaceStatus'
      )
    ####
    for name in (
      'rederived',
      'placement_verified',
      'geometry_verified',
      'upstream_state_verified',
      'frontier_state_verified',
      'upstream_pressure_verified',
      'frontier_pressure_verified',
      'downstream_state_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    for name in (
      'upstream_state_residual',
      'frontier_state_residual',
      'upstream_pressure_residual',
      'frontier_pressure_residual',
    ):
      value = getattr(self, name)
      if value is None:
        continue
      ####
      numeric = float(value)
      if numeric < 0.0:
        raise ValueError(f'{name} must be nonnegative when supplied')
      ####
      object.__setattr__(self, name, numeric)
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status is MocTransonicShockInterfaceAuditStatus.VERIFIED
  ####

  @property
  def physical_closure_verified(self) -> bool:
    return False
  ####

  @property
  def production_claim_allowed(self) -> bool:
    return False
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'result_status': self.result_status.value,
      'converged': self.converged,
      'rederived': self.rederived,
      'placement_verified': self.placement_verified,
      'geometry_verified': self.geometry_verified,
      'upstream_state_verified': self.upstream_state_verified,
      'frontier_state_verified': self.frontier_state_verified,
      'upstream_pressure_verified': self.upstream_pressure_verified,
      'frontier_pressure_verified': self.frontier_pressure_verified,
      'downstream_state_verified': self.downstream_state_verified,
      'upstream_state_residual': self.upstream_state_residual,
      'frontier_state_residual': self.frontier_state_residual,
      'upstream_pressure_residual': self.upstream_pressure_residual,
      'frontier_pressure_residual': self.frontier_pressure_residual,
      'physical_closure_verified': False,
      'production_claim_allowed': False,
      'claim_status': (
        'research-only-transonic-interface-audit; mixed-regime closure, '
        'physical shock-cell length, and external validation remain open'
      ),
      'message': self.message,
    }
  ####
####


def _close(actual: float | None, expected: float | None) -> bool:
  if actual is None or expected is None:
    return actual is expected
  ####
  return bool(isclose(float(actual), float(expected), rel_tol=3.0e-6, abs_tol=1.0e-10))
####


def _state_close(
  actual: CharacteristicState | None,
  expected: CharacteristicState | None,
) -> bool:
  if actual is None or expected is None:
    return actual is expected
  ####
  return bool(
    _close(actual.x_m, expected.x_m)
    and _close(actual.y_m, expected.y_m)
    and _close(actual.theta_rad, expected.theta_rad)
    and _close(actual.mach, expected.mach)
    and _close(actual.gamma, expected.gamma)
  )
####


def _sample_close(
  actual: MocTransonicShockInterfaceSample | None,
  expected: MocTransonicShockInterfaceSample | None,
) -> bool:
  if actual is None or expected is None:
    return actual is expected
  ####
  return bool(
    _close(actual.point_m[0], expected.point_m[0])
    and _close(actual.point_m[1], expected.point_m[1])
    and _close(actual.mach, expected.mach)
    and _close(actual.flow_angle_rad, expected.flow_angle_rad)
    and _close(actual.static_pressure_Pa, expected.static_pressure_Pa)
    and _close(actual.total_pressure_Pa, expected.total_pressure_Pa)
    and _close(actual.gamma, expected.gamma)
  )
####


def _state_residual(
  actual: CharacteristicState | None,
  expected: CharacteristicState | None,
) -> float | None:
  if actual is None or expected is None:
    return None
  ####
  return max(
    abs(actual.x_m - expected.x_m),
    abs(actual.y_m - expected.y_m),
    abs(actual.theta_rad - expected.theta_rad),
    abs(actual.mach - expected.mach),
    abs(actual.gamma - expected.gamma),
  )
####


def _pressure_residual(actual: float | None, expected: float | None) -> float | None:
  if actual is None or expected is None:
    return None
  ####
  if actual <= 0.0 or expected <= 0.0:
    return None
  ####
  return abs(log(float(actual) / float(expected)))
####


def measure_moc_transonic_shock_interface(
  result: MocTransonicShockInterfaceResult,
) -> MocTransonicShockInterfaceAudit:
  """Re-derive the placement-bound interface without trusting its fields."""

  if not isinstance(result, MocTransonicShockInterfaceResult):
    raise TypeError('result must be a MocTransonicShockInterfaceResult')
  ####
  placement = result.request.placement
  placement_audit = measure_moc_transonic_placement(placement)
  placement_verified = bool(
    placement_audit.converged
    and placement.status is MocTransonicPlacementStatus
    .CONVERGED_BOUNDED_PLACEMENT
    and placement.placement_verified
  )
  geometry = result.shock_geometry
  geometry_audit = result.shock_geometry_audit
  point = placement.intersection_point_m
  shock_state = None if geometry is None else geometry.request.shock_state
  expected_upstream = None
  expected_upstream_sample = None
  expected_downstream_sample = None
  if shock_state is not None and point is not None:
    expected_upstream = CharacteristicState(
      x_m=point[0],
      y_m=point[1],
      theta_rad=shock_state.upstream_flow_angle_rad,
      mach=shock_state.upstream_mach,
      gamma=shock_state.gamma,
    )
    expected_upstream_sample = MocTransonicShockInterfaceSample(
      point_m=point,
      mach=shock_state.upstream_mach,
      flow_angle_rad=shock_state.upstream_flow_angle_rad,
      static_pressure_Pa=shock_state.upstream_static_pressure_Pa,
      total_pressure_Pa=shock_state.upstream_total_pressure_Pa,
      gamma=shock_state.gamma,
    )
    expected_downstream_sample = MocTransonicShockInterfaceSample(
      point_m=point,
      mach=shock_state.downstream_mach,
      flow_angle_rad=shock_state.upstream_flow_angle_rad,
      static_pressure_Pa=shock_state.downstream_static_pressure_Pa,
      total_pressure_Pa=shock_state.downstream_total_pressure_Pa,
      gamma=shock_state.gamma,
    )
  ####
  upstream_state_residual = _state_residual(
    placement.transport_state,
    expected_upstream,
  )
  frontier_state_residual = _state_residual(
    placement.frontier_state,
    expected_upstream,
  )
  upstream_pressure_residual = _pressure_residual(
    placement.transport_total_pressure_Pa,
    None if shock_state is None else shock_state.upstream_total_pressure_Pa,
  )
  frontier_pressure_residual = _pressure_residual(
    placement.frontier_total_pressure_Pa,
    None if shock_state is None else shock_state.upstream_total_pressure_Pa,
  )
  upstream_state_verified = bool(
    expected_upstream is not None
    and _state_close(placement.transport_state, expected_upstream)
  )
  frontier_state_verified = bool(
    expected_upstream is not None
    and _state_close(placement.frontier_state, expected_upstream)
  )
  upstream_pressure_verified = bool(
    upstream_pressure_residual is not None
    and upstream_pressure_residual <= result.request.pressure_tolerance
  )
  frontier_pressure_verified = bool(
    frontier_pressure_residual is not None
    and frontier_pressure_residual <= result.request.pressure_tolerance
  )
  geometry_rederived = False
  if geometry is not None and geometry_audit is not None:
    independent_geometry_audit: MocTransonicShockGeometryAudit = (
      measure_moc_transonic_shock_geometry(geometry)
    )
    geometry_rederived = bool(
      independent_geometry_audit.converged
      and geometry_audit.converged
      and geometry_audit.geometry_binding_verified
      and independent_geometry_audit.geometry_binding_verified
      and point is not None
      and hypot(
        geometry.shock_point_m[0] - point[0],
        geometry.shock_point_m[1] - point[1],
      ) <= result.request.position_tolerance_m
    )
  ####
  downstream_state_verified = bool(
    shock_state is not None
    and result.downstream_sample is not None
    and _sample_close(result.downstream_sample, expected_downstream_sample)
    and shock_state.upstream_supersonic
    and shock_state.downstream_subsonic
    and 0.0 < shock_state.total_pressure_ratio < 1.0
  )
  rederived = bool(
    result.upstream_sample is not None
    and _sample_close(result.upstream_sample, expected_upstream_sample)
    and result.status is MocTransonicShockInterfaceStatus
    .CONVERGED_BOUNDED_INTERFACE
  )
  verified = bool(
    placement_verified
    and geometry_rederived
    and upstream_state_verified
    and frontier_state_verified
    and upstream_pressure_verified
    and frontier_pressure_verified
    and downstream_state_verified
    and rederived
  )
  return MocTransonicShockInterfaceAudit(
    status=(
      MocTransonicShockInterfaceAuditStatus.VERIFIED
      if verified
      else MocTransonicShockInterfaceAuditStatus.RESULT_FAILURE
    ),
    result_status=result.status,
    rederived=rederived,
    placement_verified=placement_verified,
    geometry_verified=geometry_rederived,
    upstream_state_verified=upstream_state_verified,
    frontier_state_verified=frontier_state_verified,
    upstream_pressure_verified=upstream_pressure_verified,
    frontier_pressure_verified=frontier_pressure_verified,
    downstream_state_verified=downstream_state_verified,
    upstream_state_residual=upstream_state_residual,
    frontier_state_residual=frontier_state_residual,
    upstream_pressure_residual=upstream_pressure_residual,
    frontier_pressure_residual=frontier_pressure_residual,
    message=(
      'placement, scalar geometry, upstream/frontier lineage, and downstream '
      'state were independently rederived'
      if verified
      else 'reported shock-interface handoff does not match independent remeasurement'
    ),
  )
####


def measure_moc_transonic_shock_interface_profile(
  profile: MocTransonicShockInterfaceProfile,
) -> MocTransonicShockInterfaceProfileAudit:
  """Re-derive a cross-section profile without trusting reported fields."""

  if not isinstance(profile, MocTransonicShockInterfaceProfile):
    raise TypeError(
      'profile must be a MocTransonicShockInterfaceProfile'
    )
  ####
  upstream = profile.upstream_samples
  downstream = profile.downstream_samples
  count = len(upstream)
  tolerance = profile.position_tolerance_m
  cross_section_verified = bool(
    all(
      abs(sample.point_m[0] - profile.cross_section_x_m) <= tolerance
      for sample in (*upstream, *downstream)
    )
  )
  ordinate_verified = bool(
    len(downstream) == count
    and all(
      abs(left.point_m[1] - right.point_m[1]) <= tolerance
      for left, right in zip(upstream, downstream)
    )
    and all(
      right.point_m[1] > left.point_m[1] + tolerance
      for left, right in zip(upstream, upstream[1:])
    )
  )
  regime_verified = bool(
    all(sample.mach > 1.0 for sample in upstream)
    and all(sample.mach < 1.0 for sample in downstream)
    and all(
      abs(left.gamma - right.gamma) <= profile.state_tolerance
      for left, right in zip(upstream, downstream)
    )
  )
  thermodynamics_verified = True
  for sample in (*upstream, *downstream):
    pressure_factor = 1.0 + 0.5 * (sample.gamma - 1.0) * sample.mach**2
    expected_static_pressure = sample.total_pressure_Pa / pressure_factor ** (
      sample.gamma / (sample.gamma - 1.0)
    )
    scale = max(expected_static_pressure, sample.static_pressure_Pa, 1.0)
    if abs(expected_static_pressure - sample.static_pressure_Pa) / scale > 1.0e-8:
      thermodynamics_verified = False
      break
    ####
  ####
  shock_loss_verified = bool(
    all(
      downstream_sample.total_pressure_Pa < upstream_sample.total_pressure_Pa
      and downstream_sample.static_pressure_Pa > upstream_sample.static_pressure_Pa
      for upstream_sample, downstream_sample in zip(upstream, downstream)
    )
  )
  verified = bool(
    cross_section_verified
    and ordinate_verified
    and regime_verified
    and thermodynamics_verified
    and shock_loss_verified
  )
  return MocTransonicShockInterfaceProfileAudit(
    status=(
      MocTransonicShockInterfaceProfileAuditStatus.VERIFIED
      if verified
      else MocTransonicShockInterfaceProfileAuditStatus.RESULT_FAILURE
    ),
    profile=profile,
    sample_count=count,
    cross_section_verified=cross_section_verified,
    ordinate_verified=ordinate_verified,
    regime_verified=regime_verified,
    thermodynamics_verified=thermodynamics_verified,
    shock_loss_verified=shock_loss_verified,
    message=(
      'cross-section geometry, regime ordering, thermodynamic identities, and '
      'shock total-pressure loss were independently rederived'
      if verified
      else 'shock-interface profile does not match independent remeasurement'
    ),
  )
####


def _line_angle_residual(actual: float, expected: float) -> float:
  return abs((actual - expected + 0.5 * pi) % pi - 0.5 * pi)
####


def _normal_shock_profile_expected(
  upstream: MocTransonicShockInterfaceSample,
) -> MocTransonicShockInterfaceSample:
  """Re-derive one normal-shock sample without using the model builder."""

  gamma = upstream.gamma
  mach = upstream.mach
  upstream_factor = 1.0 + 0.5 * (gamma - 1.0) * mach**2
  upstream_static = upstream.total_pressure_Pa / upstream_factor ** (
    gamma / (gamma - 1.0)
  )
  static_pressure_ratio = 1.0 + 2.0 * gamma / (gamma + 1.0) * (mach**2 - 1.0)
  downstream_static = upstream_static * static_pressure_ratio
  downstream_mach = sqrt(
    (1.0 + 0.5 * (gamma - 1.0) * mach**2)
    / (gamma * mach**2 - 0.5 * (gamma - 1.0))
  )
  downstream_factor = 1.0 + 0.5 * (gamma - 1.0) * downstream_mach**2
  downstream_total = downstream_static * downstream_factor ** (
    gamma / (gamma - 1.0)
  )
  return MocTransonicShockInterfaceSample(
    point_m=upstream.point_m,
    mach=downstream_mach,
    flow_angle_rad=upstream.flow_angle_rad,
    static_pressure_Pa=downstream_static,
    total_pressure_Pa=downstream_total,
    gamma=gamma,
  )
####


def measure_moc_transonic_shock_interface_profile_build(
  result: MocTransonicShockInterfaceProfileBuildResult,
) -> MocTransonicShockInterfaceProfileBuildAudit:
  """Independently rederive a normal-shock profile build result."""

  if not isinstance(result, MocTransonicShockInterfaceProfileBuildResult):
    raise TypeError(
      'result must be a MocTransonicShockInterfaceProfileBuildResult'
    )
  ####
  profile = result.profile
  request = result.request
  profile_audit = (
    None
    if profile is None
    else measure_moc_transonic_shock_interface_profile(profile)
  )
  if profile is None:
    return MocTransonicShockInterfaceProfileBuildAudit(
      status=MocTransonicShockInterfaceProfileBuildAuditStatus.RESULT_FAILURE,
      result_status=result.status,
      profile_audit=None,
      rederived=False,
      upstream_profile_verified=False,
      normal_alignment_verified=False,
      downstream_state_verified=False,
      maximum_state_residual=None,
      maximum_pressure_residual=None,
      maximum_total_pressure_residual=None,
      message='profile build result retained no profile to audit',
    )
  ####
  upstream = request.upstream_samples
  downstream = profile.downstream_samples
  upstream_profile_verified = bool(
    len(upstream) >= 2
    and len(downstream) == len(upstream)
    and profile_audit is not None
    and profile_audit.cross_section_verified
    and profile_audit.ordinate_verified
    and profile_audit.regime_verified
    and profile_audit.thermodynamics_verified
  )
  normal_alignment_verified = bool(
    all(
      _line_angle_residual(
        sample.flow_angle_rad,
        request.interface_normal_angle_rad,
      ) <= request.normal_alignment_tolerance_rad
      for sample in upstream
    )
  )
  state_residuals: list[float] = []
  pressure_residuals: list[float] = []
  total_pressure_residuals: list[float] = []
  downstream_state_verified = True
  for upstream_sample, actual in zip(upstream, downstream):
    expected = _normal_shock_profile_expected(upstream_sample)
    state_residual = max(
      abs(actual.point_m[0] - expected.point_m[0]),
      abs(actual.point_m[1] - expected.point_m[1]),
      abs(actual.mach - expected.mach),
      abs(actual.flow_angle_rad - expected.flow_angle_rad),
      abs(actual.gamma - expected.gamma),
    )
    pressure_residual = _pressure_residual(
      actual.static_pressure_Pa,
      expected.static_pressure_Pa,
    )
    total_pressure_residual = _pressure_residual(
      actual.total_pressure_Pa,
      expected.total_pressure_Pa,
    )
    if pressure_residual is None or total_pressure_residual is None:
      downstream_state_verified = False
    else:
      pressure_residuals.append(pressure_residual)
      total_pressure_residuals.append(total_pressure_residual)
    ####
    state_residuals.append(state_residual)
    if (
      state_residual > request.state_tolerance
      or pressure_residual is None
      or pressure_residual > request.pressure_tolerance
      or total_pressure_residual is None
      or total_pressure_residual > request.pressure_tolerance
    ):
      downstream_state_verified = False
    ####
  ####
  maximum_state_residual = max(state_residuals) if state_residuals else None
  maximum_pressure_residual = (
    max(pressure_residuals) if pressure_residuals else None
  )
  maximum_total_pressure_residual = (
    max(total_pressure_residuals) if total_pressure_residuals else None
  )
  verified = bool(
    result.status is (
      MocTransonicShockInterfaceProfileBuildStatus
      .CONVERGED_NORMAL_SHOCK_PROFILE
    )
    and upstream_profile_verified
    and normal_alignment_verified
    and downstream_state_verified
    and profile_audit is not None
    and profile_audit.converged
  )
  return MocTransonicShockInterfaceProfileBuildAudit(
    status=(
      MocTransonicShockInterfaceProfileBuildAuditStatus.VERIFIED
      if verified
      else MocTransonicShockInterfaceProfileBuildAuditStatus.RESULT_FAILURE
    ),
    result_status=result.status,
    profile_audit=profile_audit,
    rederived=True,
    upstream_profile_verified=upstream_profile_verified,
    normal_alignment_verified=normal_alignment_verified,
    downstream_state_verified=downstream_state_verified,
    maximum_state_residual=maximum_state_residual,
    maximum_pressure_residual=maximum_pressure_residual,
    maximum_total_pressure_residual=maximum_total_pressure_residual,
    message=(
      'upstream geometry, normal alignment, Rankine--Hugoniot profile states, '
      'and scalar thermodynamic identities were independently rederived'
      if verified
      else 'normal-shock interface profile build does not match independent '
      'rederivation'
    ),
  )
####
