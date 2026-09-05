"""Exact physical-field cross-section continuation handoff.

The normal-shock interface profile is a separate scalar shock primitive.  A
resolved post-shock MOC field may instead remain supersonic behind an oblique
shock, so a downstream coupled field must be able to consume an exact sampled
cross-section without applying another normal-shock jump.  This module keeps
that handoff typed and independently remeasurable; it does not close the new
downstream free boundary or promote the field.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Any

from exhaust_plume.models.moc.physical_cell import (
  MocPhysicalPostShockFieldResult,
)
from exhaust_plume.models.moc.primitives import CharacteristicState
from exhaust_plume.models.moc.transonic_interface import (
  MocTransonicShockInterfaceSample,
)

__all__ = (
  'MocPhysicalFieldContinuationProfileStatus',
  'MocPhysicalFieldContinuationProfile',
  'MocPhysicalFieldContinuationProfileRequest',
  'MocPhysicalFieldContinuationProfileResult',
  'build_moc_physical_field_continuation_profile',
)


class MocPhysicalFieldContinuationProfileStatus(str, Enum):
  """Outcome of an exact physical-field continuation handoff."""

  CONVERGED_FIELD_CONTINUATION_PROFILE = (
    'converged-physical-field-continuation-profile'
  )
  INVALID_INPUT = 'invalid_input'
  FIELD_SAMPLING_UNAVAILABLE = (
    'physical-field-continuation-field-sampling-unavailable'
  )
  CROSS_SECTION_FAILURE = 'physical-field-continuation-cross-section-failure'
  FIELD_SAMPLE_FAILURE = 'physical-field-continuation-field-sample-failure'
  INDEPENDENT_AUDIT_FAILURE = (
    'physical-field-continuation-independent-audit-failure'
  )
####


def _finite_point(point: object) -> tuple[float, float]:
  try:
    values = (float(point[0]), float(point[1]))  # type: ignore[index]
  except (IndexError, TypeError, ValueError) as error:
    raise ValueError('continuation sample points must contain two coordinates') from error
  ####
  if not all(isfinite(value) for value in values):
    raise ValueError('continuation sample points must be finite')
  ####
  return values
####


@dataclass(frozen=True, slots=True)
class MocPhysicalFieldContinuationProfile:
  """One exact, ordered state/pressure profile on a physical-field section."""

  samples: tuple[MocTransonicShockInterfaceSample, ...]
  profile_id: str = 'solver-owned-physical-field-continuation-profile-v1'
  position_tolerance_m: float = 1.0e-9
  state_tolerance: float = 1.0e-6
  pressure_tolerance: float = 1.0e-8

  def __post_init__(self) -> None:
    samples = tuple(self.samples)
    if len(samples) < 2:
      raise ValueError('continuation profile requires at least two samples')
    ####
    if any(
      not isinstance(sample, MocTransonicShockInterfaceSample)
      for sample in samples
    ):
      raise TypeError(
        'continuation profile samples must contain '
        'MocTransonicShockInterfaceSample values'
      )
    ####
    for name in (
      'position_tolerance_m',
      'state_tolerance',
      'pressure_tolerance',
    ):
      value = float(getattr(self, name))
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      ####
      object.__setattr__(self, name, value)
    ####
    profile_id = str(self.profile_id)
    if not profile_id:
      raise ValueError('profile_id must not be empty')
    ####
    object.__setattr__(self, 'profile_id', profile_id)
    x_reference = samples[0].point_m[0]
    if any(
      abs(sample.point_m[0] - x_reference) > self.position_tolerance_m
      for sample in samples[1:]
    ):
      raise ValueError('continuation profile samples must share one section x')
    ####
    ordinates = tuple(sample.point_m[1] for sample in samples)
    if any(
      second <= first + self.position_tolerance_m
      for first, second in zip(ordinates, ordinates[1:])
    ):
      raise ValueError('continuation profile ordinates must be strictly increasing')
    ####
    gammas = tuple(sample.gamma for sample in samples)
    if max(gammas) - min(gammas) > self.state_tolerance:
      raise ValueError('continuation profile samples must use one gamma')
    ####
    object.__setattr__(self, 'samples', samples)
  ####

  @property
  def cross_section_x_m(self) -> float:
    """Return the exact retained section x coordinate."""

    return self.samples[0].point_m[0]
  ####

  @property
  def lower_ordinate_m(self) -> float:
    """Return the first sampled ordinate."""

    return self.samples[0].point_m[1]
  ####

  @property
  def upper_ordinate_m(self) -> float:
    """Return the last sampled ordinate."""

    return self.samples[-1].point_m[1]
  ####

  @property
  def gamma(self) -> float:
    """Return the common section gamma."""

    return self.samples[0].gamma
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'profile_id': self.profile_id,
      'cross_section_x_m': self.cross_section_x_m,
      'lower_ordinate_m': self.lower_ordinate_m,
      'upper_ordinate_m': self.upper_ordinate_m,
      'sample_count': len(self.samples),
      'samples': [sample.as_report() for sample in self.samples],
      'position_tolerance_m': self.position_tolerance_m,
      'state_tolerance': self.state_tolerance,
      'pressure_tolerance': self.pressure_tolerance,
      'claim_status': (
        'research-only-exact-physical-field-continuation-profile; downstream '
        'free-boundary closure, refinement, and external validation remain open'
      ),
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocPhysicalFieldContinuationProfileRequest:
  """Request to sample one physical field section without extrapolation."""

  field: MocPhysicalPostShockFieldResult
  sample_points_m: tuple[tuple[float, float], ...]
  profile_id: str = 'solver-owned-physical-field-continuation-profile-v1'
  position_tolerance_m: float = 1.0e-9
  state_tolerance: float = 1.0e-6
  pressure_tolerance: float = 1.0e-8

  def __post_init__(self) -> None:
    if not isinstance(self.field, MocPhysicalPostShockFieldResult):
      raise TypeError('field must be a MocPhysicalPostShockFieldResult')
    ####
    points = tuple(_finite_point(point) for point in self.sample_points_m)
    if len(points) < 2:
      raise ValueError('sample_points_m must contain at least two points')
    ####
    object.__setattr__(self, 'sample_points_m', points)
    for name in (
      'position_tolerance_m',
      'state_tolerance',
      'pressure_tolerance',
    ):
      value = float(getattr(self, name))
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      ####
      object.__setattr__(self, name, value)
    ####
    profile_id = str(self.profile_id)
    if not profile_id:
      raise ValueError('profile_id must not be empty')
    ####
    object.__setattr__(self, 'profile_id', profile_id)
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'model': 'research-physical-field-continuation-profile-v1',
      'profile_id': self.profile_id,
      'sample_points_m': [list(point) for point in self.sample_points_m],
      'position_tolerance_m': self.position_tolerance_m,
      'state_tolerance': self.state_tolerance,
      'pressure_tolerance': self.pressure_tolerance,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocPhysicalFieldContinuationProfileResult:
  """Audited exact-field continuation profile."""

  status: MocPhysicalFieldContinuationProfileStatus
  request: MocPhysicalFieldContinuationProfileRequest
  field: MocPhysicalPostShockFieldResult | None = None
  profile: MocPhysicalFieldContinuationProfile | None = None
  independent_measurement: Any | None = None
  field_lineage_verified: bool = False
  field_sampling_verified: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocPhysicalFieldContinuationProfileStatus,
    ):
      raise TypeError(
        'status must be a MocPhysicalFieldContinuationProfileStatus'
      )
    ####
    if not isinstance(
      self.request,
      MocPhysicalFieldContinuationProfileRequest,
    ):
      raise TypeError(
        'request must be a MocPhysicalFieldContinuationProfileRequest'
      )
    ####
    if self.field is not None and not isinstance(
      self.field,
      MocPhysicalPostShockFieldResult,
    ):
      raise TypeError(
        'field must be a MocPhysicalPostShockFieldResult or None'
      )
    ####
    if self.profile is not None and not isinstance(
      self.profile,
      MocPhysicalFieldContinuationProfile,
    ):
      raise TypeError(
        'profile must be a MocPhysicalFieldContinuationProfile or None'
      )
    ####
    for name in ('field_lineage_verified', 'field_sampling_verified'):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    """Whether the exact field sample and its independent audit passed."""

    audit = self.independent_measurement
    return bool(
      self.status is (
        MocPhysicalFieldContinuationProfileStatus
        .CONVERGED_FIELD_CONTINUATION_PROFILE
      )
      and self.field is not None
      and self.profile is not None
      and self.field_lineage_verified
      and self.field_sampling_verified
      and audit is not None
      and bool(getattr(audit, 'converged', False))
    )
  ####

  @property
  def physical_closure_verified(self) -> bool:
    """A section handoff does not close the downstream free boundary."""

    return False
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    """Keep the continuation below physical-chain promotion."""

    return True
  ####

  @property
  def production_claim_allowed(self) -> bool:
    """The continuation is research-only evidence."""

    return False
  ####

  def as_report(self) -> dict[str, Any]:
    audit = self.independent_measurement
    return {
      'status': self.status.value,
      'model': 'research-physical-field-continuation-profile-v1',
      'converged': self.converged,
      'field_lineage_verified': self.field_lineage_verified,
      'field_sampling_verified': self.field_sampling_verified,
      'field_status': None if self.field is None else self.field.status.value,
      'profile': None if self.profile is None else self.profile.as_report(),
      'independent_measurement': (
        None
        if audit is None or not hasattr(audit, 'as_report')
        else audit.as_report()
      ),
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'claim_status': (
        'research-only-exact-physical-field-continuation; downstream '
        'free-boundary closure, refinement, and external validation remain open'
      ),
      'request': self.request.as_report(),
      'message': self.message,
    }
  ####
####


def _static_pressure(
  state: CharacteristicState,
  total_pressure_Pa: float,
) -> float:
  factor = 1.0 + 0.5 * (state.gamma - 1.0) * state.mach**2
  return float(total_pressure_Pa) / factor ** (
    state.gamma / (state.gamma - 1.0)
  )
####


def _failure(
  status: MocPhysicalFieldContinuationProfileStatus,
  request: MocPhysicalFieldContinuationProfileRequest,
  *,
  field: MocPhysicalPostShockFieldResult | None = None,
  profile: MocPhysicalFieldContinuationProfile | None = None,
  independent_measurement: Any | None = None,
  field_lineage_verified: bool = False,
  field_sampling_verified: bool = False,
  message: str,
) -> MocPhysicalFieldContinuationProfileResult:
  return MocPhysicalFieldContinuationProfileResult(
    status=status,
    request=request,
    field=field,
    profile=profile,
    independent_measurement=independent_measurement,
    field_lineage_verified=field_lineage_verified,
    field_sampling_verified=field_sampling_verified,
    message=message,
  )
####


def build_moc_physical_field_continuation_profile(
  request: MocPhysicalFieldContinuationProfileRequest,
) -> MocPhysicalFieldContinuationProfileResult:
  """Sample one exact field section for downstream continuation."""

  if not isinstance(
    request,
    MocPhysicalFieldContinuationProfileRequest,
  ):
    raise TypeError(
      'request must be a MocPhysicalFieldContinuationProfileRequest'
    )
  ####
  field = request.field
  field_lineage_verified = bool(
    field.converged
    and field.physical_closure_verified
    and field.state_sampling_available
  )
  if not field_lineage_verified:
    return _failure(
      MocPhysicalFieldContinuationProfileStatus.FIELD_SAMPLING_UNAVAILABLE,
      request,
      field=field,
      message=(
        'physical-field continuation requires a converged, physically closed '
        'field with state sampling available'
      ),
    )
  ####
  points = request.sample_points_m
  if any(
    second[1] <= first[1] + request.position_tolerance_m
    for first, second in zip(points, points[1:])
  ) or any(
    abs(point[0] - points[0][0]) > request.position_tolerance_m
    for point in points[1:]
  ):
    return _failure(
      MocPhysicalFieldContinuationProfileStatus.CROSS_SECTION_FAILURE,
      request,
      field=field,
      field_lineage_verified=True,
      message=(
        'physical-field continuation points must share one x and have '
        'strictly increasing ordinates'
      ),
    )
  ####
  samples: list[MocTransonicShockInterfaceSample] = []
  try:
    for point in points:
      state = field.state_at(
        point,
        position_tolerance_m=request.position_tolerance_m,
      )
      total_pressure = field.total_pressure_at(
        point,
        position_tolerance_m=request.position_tolerance_m,
      )
      if state is None or total_pressure is None:
        return _failure(
          MocPhysicalFieldContinuationProfileStatus.FIELD_SAMPLE_FAILURE,
          request,
          field=field,
          field_lineage_verified=True,
          field_sampling_verified=bool(samples),
          message=(
            'physical-field continuation sampler returned no complete state '
            f'at {point}'
          ),
        )
      ####
      samples.append(
        MocTransonicShockInterfaceSample(
          point_m=point,
          mach=state.mach,
          flow_angle_rad=state.theta_rad,
          static_pressure_Pa=_static_pressure(state, total_pressure),
          total_pressure_Pa=total_pressure,
          gamma=state.gamma,
        )
      )
    ####
    profile = MocPhysicalFieldContinuationProfile(
      samples=tuple(samples),
      profile_id=request.profile_id,
      position_tolerance_m=request.position_tolerance_m,
      state_tolerance=request.state_tolerance,
      pressure_tolerance=request.pressure_tolerance,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocPhysicalFieldContinuationProfileStatus.FIELD_SAMPLE_FAILURE,
      request,
      field=field,
      field_lineage_verified=True,
      field_sampling_verified=True,
      message=f'physical-field continuation sampling raised: {error}',
    )
  ####
  result = MocPhysicalFieldContinuationProfileResult(
    status=(
      MocPhysicalFieldContinuationProfileStatus
      .CONVERGED_FIELD_CONTINUATION_PROFILE
    ),
    request=request,
    field=field,
    profile=profile,
    field_lineage_verified=True,
    field_sampling_verified=True,
    message=(
      'exact physical-field continuation profile was sampled without a '
      'second shock transform; downstream closure remains open'
    ),
  )
  try:
    from exhaust_plume.validation.moc_field_continuation import (
      measure_moc_physical_field_continuation_profile,
    )

    audit = measure_moc_physical_field_continuation_profile(result)
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocPhysicalFieldContinuationProfileStatus.INDEPENDENT_AUDIT_FAILURE,
      request,
      field=field,
      profile=profile,
      field_lineage_verified=True,
      field_sampling_verified=True,
      message=f'independent continuation-profile audit raised: {error}',
    )
  ####
  if not audit.converged:
    return _failure(
      MocPhysicalFieldContinuationProfileStatus.INDEPENDENT_AUDIT_FAILURE,
      request,
      field=field,
      profile=profile,
      independent_measurement=audit,
      field_lineage_verified=True,
      field_sampling_verified=True,
      message=(
        'exact physical-field continuation profile failed its independent '
        f'audit: {audit.message}'
      ),
    )
  ####
  return MocPhysicalFieldContinuationProfileResult(
    status=(
      MocPhysicalFieldContinuationProfileStatus
      .CONVERGED_FIELD_CONTINUATION_PROFILE
    ),
    request=request,
    field=field,
    profile=profile,
    independent_measurement=audit,
    field_lineage_verified=True,
    field_sampling_verified=True,
    message=(
      'exact physical-field continuation sampling and independent '
      'remeasurement passed; downstream closure remains open'
    ),
  )
####
