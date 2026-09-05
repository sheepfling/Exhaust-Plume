"""Independent measurement for bounded transonic characteristic transport."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import cos, exp, hypot, isclose, isfinite, log, sin, sqrt
from typing import Any

from exhaust_plume.models.moc.euler_entropy_characteristic_transport import (
  MocTransonicCharacteristicTransportResult,
  MocTransonicCharacteristicTransportStatus,
  MocTransonicCharacteristicTransportTermination,
  solve_moc_transonic_characteristic_transport,
)
from exhaust_plume.models.moc.primitives import (
  CharacteristicFamily,
  CharacteristicState,
)

__all__ = (
  'MocTransonicCharacteristicTransportAuditStatus',
  'MocTransonicCharacteristicTransportAudit',
  'measure_moc_transonic_characteristic_transport',
)


class MocTransonicCharacteristicTransportAuditStatus(str, Enum):
  """Independent audit outcome for bounded characteristic transport."""

  VERIFIED = 'verified-transonic-characteristic-transport-audit'
  RESULT_FAILURE = 'transonic-characteristic-transport-result-failure'
####


@dataclass(frozen=True, slots=True)
class MocTransonicCharacteristicTransportAudit:
  """Re-derived path, field samples, and transport residual evidence."""

  status: MocTransonicCharacteristicTransportAuditStatus
  result_status: MocTransonicCharacteristicTransportStatus
  rederived: bool
  sample_count: int
  segment_count: int
  sample_lineage_verified: bool
  geometry_verified: bool
  compatibility_verified: bool
  pressure_lineage_verified: bool
  boundary_stop_verified: bool
  maximum_geometry_residual: float | None
  maximum_compatibility_residual: float | None
  maximum_pressure_residual: float | None
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocTransonicCharacteristicTransportAuditStatus,
    ):
      raise TypeError(
        'status must be a MocTransonicCharacteristicTransportAuditStatus'
      )
    ####
    if not isinstance(
      self.result_status,
      MocTransonicCharacteristicTransportStatus,
    ):
      raise TypeError(
        'result_status must be a MocTransonicCharacteristicTransportStatus'
      )
    ####
    for name in ('rederived', 'sample_lineage_verified', 'geometry_verified',
                 'compatibility_verified', 'pressure_lineage_verified',
                 'boundary_stop_verified'):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    for name in ('sample_count', 'segment_count'):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer')
      ####
    ####
    for name in (
      'maximum_geometry_residual',
      'maximum_compatibility_residual',
      'maximum_pressure_residual',
    ):
      value = getattr(self, name)
      if value is None:
        continue
      ####
      numeric = float(value)
      if not isfinite(numeric) or numeric < 0.0:
        raise ValueError(f'{name} must be finite and nonnegative when supplied')
      ####
      object.__setattr__(self, name, numeric)
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status is MocTransonicCharacteristicTransportAuditStatus.VERIFIED
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
      'sample_count': self.sample_count,
      'segment_count': self.segment_count,
      'sample_lineage_verified': self.sample_lineage_verified,
      'geometry_verified': self.geometry_verified,
      'compatibility_verified': self.compatibility_verified,
      'pressure_lineage_verified': self.pressure_lineage_verified,
      'boundary_stop_verified': self.boundary_stop_verified,
      'maximum_geometry_residual': self.maximum_geometry_residual,
      'maximum_compatibility_residual': self.maximum_compatibility_residual,
      'maximum_pressure_residual': self.maximum_pressure_residual,
      'physical_closure_verified': False,
      'production_claim_allowed': False,
      'claim_status': (
        'research-only-bounded-transport-audit; shock placement, mixed-regime '
        'closure, chain promotion, and external validation remain open'
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


def _state_matches(actual: CharacteristicState, expected: CharacteristicState) -> bool:
  return bool(
    _close(actual.x_m, expected.x_m)
    and _close(actual.y_m, expected.y_m)
    and _close(actual.theta_rad, expected.theta_rad)
    and _close(actual.mach, expected.mach)
    and _close(actual.gamma, expected.gamma)
  )
####


def _point_matches(
  actual: tuple[float, float] | None,
  expected: tuple[float, float] | None,
) -> bool:
  if actual is None or expected is None:
    return actual is expected
  ####
  return bool(_close(actual[0], expected[0]) and _close(actual[1], expected[1]))
####


def _compatibility_source(
  start: CharacteristicState,
  end: CharacteristicState,
  gradient: tuple[float, float],
) -> float:
  length = hypot(end.x_m - start.x_m, end.y_m - start.y_m)
  average_theta = 0.5 * (start.theta_rad + end.theta_rad)
  normal_gradient = (
    gradient[0] * -sin(average_theta)
    + gradient[1] * cos(average_theta)
  )
  average_mach = 0.5 * (start.mach + end.mach)
  average_gamma = 0.5 * (start.gamma + end.gamma)
  return (
    -sqrt(max(average_mach * average_mach - 1.0, 0.0))
    / (average_gamma * average_mach**3)
    * normal_gradient
    * length
  )
####


def _geometry_residual(
  start: CharacteristicState,
  end: CharacteristicState,
  family: CharacteristicFamily,
) -> float:
  displacement = (end.x_m - start.x_m, end.y_m - start.y_m)
  length = hypot(*displacement)
  start_direction = start.direction(family)
  end_direction = end.direction(family)
  average_direction = (
    0.5 * (start_direction[0] + end_direction[0]),
    0.5 * (start_direction[1] + end_direction[1]),
  )
  average_length = hypot(*average_direction)
  if length <= 0.0 or average_length <= 0.0:
    return float('inf')
  ####
  return abs(
    displacement[0] * average_direction[1]
    - displacement[1] * average_direction[0]
  ) / (length * average_length)
####


def _forward_margin(
  start: CharacteristicState,
  end: CharacteristicState,
  family: CharacteristicFamily,
) -> float:
  displacement = (end.x_m - start.x_m, end.y_m - start.y_m)
  start_direction = start.direction(family)
  end_direction = end.direction(family)
  average_direction = (
    0.5 * (start_direction[0] + end_direction[0]),
    0.5 * (start_direction[1] + end_direction[1]),
  )
  average_length = hypot(*average_direction)
  if average_length <= 0.0:
    return float('-inf')
  ####
  return (
    displacement[0] * average_direction[0]
    + displacement[1] * average_direction[1]
  ) / average_length
####


def _reported_result_matches(
  result: MocTransonicCharacteristicTransportResult,
  expected: MocTransonicCharacteristicTransportResult,
) -> bool:
  if result.status is not expected.status or result.termination is not expected.termination:
    return False
  ####
  if len(result.samples) != len(expected.samples) or len(result.segments) != len(expected.segments):
    return False
  ####
  if not _point_matches(result.first_unavailable_point_m, expected.first_unavailable_point_m):
    return False
  ####
  if not all(
    _close(getattr(result, name), getattr(expected, name))
    for name in (
      'maximum_geometry_residual',
      'maximum_compatibility_residual',
      'maximum_pressure_residual',
    )
  ):
    return False
  ####
  for actual, expected_sample in zip(result.samples, expected.samples, strict=True):
    if (
      actual.sample_index != expected_sample.sample_index
      or not _point_matches(actual.point_m, expected_sample.point_m)
      or not _state_matches(actual.state, expected_sample.state)
      or not _close(actual.total_pressure_Pa, expected_sample.total_pressure_Pa)
    ):
      return False
    ####
  ####
  for actual, expected_segment in zip(result.segments, expected.segments, strict=True):
    if (
      actual.segment_index != expected_segment.segment_index
      or actual.family is not expected_segment.family
      or actual.start_sample_index != expected_segment.start_sample_index
      or actual.end_sample_index != expected_segment.end_sample_index
      or not _close(actual.geometry_residual, expected_segment.geometry_residual)
      or not _close(actual.compatibility_residual, expected_segment.compatibility_residual)
      or not _close(actual.pressure_residual, expected_segment.pressure_residual)
      or not _close(actual.forward_margin_m, expected_segment.forward_margin_m)
    ):
      return False
    ####
  ####
  return True
####


def measure_moc_transonic_characteristic_transport(
  result: MocTransonicCharacteristicTransportResult,
) -> MocTransonicCharacteristicTransportAudit:
  """Re-solve and independently remeasure one bounded transport result."""

  if not isinstance(result, MocTransonicCharacteristicTransportResult):
    raise TypeError(
      'result must be a MocTransonicCharacteristicTransportResult'
    )
  ####
  expected = solve_moc_transonic_characteristic_transport(result.request)
  rederived = _reported_result_matches(result, expected)
  request = result.request
  attachment = request.attachment
  field = attachment.request.upstream_field
  sample_lineage_verified = bool(
    attachment.attachment_verified
    and result.samples
    and getattr(field, 'state_sampling_available', False)
  )
  if sample_lineage_verified:
    for sample in result.samples:
      state = field.state_at(
        sample.point_m,
        position_tolerance_m=request.position_tolerance_m,
      )
      pressure = field.total_pressure_at(
        sample.point_m,
        position_tolerance_m=request.position_tolerance_m,
      )
      if (
        state is None
        or pressure is None
        or not _state_matches(sample.state, state)
        or not _close(sample.total_pressure_Pa, pressure)
      ):
        sample_lineage_verified = False
        break
      ####
    ####
  ####
  gradient = getattr(field, 'source_pressure_gradient', None)
  geometry_verified = bool(result.segments)
  compatibility_verified = bool(result.segments)
  pressure_lineage_verified = bool(result.segments)
  if (
    gradient is None
    or len(gradient) != 2
    or not all(isfinite(float(value)) for value in gradient)
  ):
    geometry_verified = False
    compatibility_verified = False
    pressure_lineage_verified = False
  else:
    for segment in result.segments:
      start = result.samples[segment.start_sample_index].state
      end = result.samples[segment.end_sample_index].state
      geometry = _geometry_residual(start, end, request.family)
      compatibility = abs(
        (
          end.k_plus - start.k_plus
          if request.family is CharacteristicFamily.PLUS
          else end.k_minus - start.k_minus
        )
        - _compatibility_source(start, end, tuple(float(value) for value in gradient))
      )
      expected_pressure = result.samples[segment.start_sample_index].total_pressure_Pa * exp(
        gradient[0] * (end.x_m - start.x_m)
        + gradient[1] * (end.y_m - start.y_m)
      )
      pressure = abs(
        log(result.samples[segment.end_sample_index].total_pressure_Pa / expected_pressure)
      )
      forward_margin = _forward_margin(start, end, request.family)
      geometry_verified = bool(
        geometry_verified
        and _close(segment.geometry_residual, geometry)
        and geometry <= request.geometry_tolerance
      )
      compatibility_verified = bool(
        compatibility_verified
        and _close(segment.compatibility_residual, compatibility)
        and compatibility <= request.compatibility_tolerance
      )
      pressure_lineage_verified = bool(
        pressure_lineage_verified
        and _close(segment.pressure_residual, pressure)
        and pressure <= request.pressure_tolerance
        and forward_margin > request.position_tolerance_m
      )
    ####
  ####
  boundary_stop_verified = bool(
    result.termination is MocTransonicCharacteristicTransportTermination.FIELD_BOUNDARY
    and result.first_unavailable_point_m is not None
    and (
      field.state_at(
        result.first_unavailable_point_m,
        position_tolerance_m=request.position_tolerance_m,
      ) is None
      or field.total_pressure_at(
        result.first_unavailable_point_m,
        position_tolerance_m=request.position_tolerance_m,
      ) is None
    )
  )
  verified = bool(
    expected.status is MocTransonicCharacteristicTransportStatus.CONVERGED_BOUNDED_TRANSPORT
    and rederived
    and result.bounded_transport_verified
    and sample_lineage_verified
    and geometry_verified
    and compatibility_verified
    and pressure_lineage_verified
    and boundary_stop_verified
  )
  return MocTransonicCharacteristicTransportAudit(
    status=(
      MocTransonicCharacteristicTransportAuditStatus.VERIFIED
      if verified
      else MocTransonicCharacteristicTransportAuditStatus.RESULT_FAILURE
    ),
    result_status=result.status,
    rederived=rederived,
    sample_count=len(result.samples),
    segment_count=len(result.segments),
    sample_lineage_verified=sample_lineage_verified,
    geometry_verified=geometry_verified,
    compatibility_verified=compatibility_verified,
    pressure_lineage_verified=pressure_lineage_verified,
    boundary_stop_verified=boundary_stop_verified,
    maximum_geometry_residual=result.maximum_geometry_residual,
    maximum_compatibility_residual=result.maximum_compatibility_residual,
    maximum_pressure_residual=result.maximum_pressure_residual,
    message=(
      'bounded transport path, field samples, residuals, and boundary stop '
      'were independently remeasured'
      if verified
      else 'reported bounded transport does not match independent remeasurement'
    ),
  )
####
