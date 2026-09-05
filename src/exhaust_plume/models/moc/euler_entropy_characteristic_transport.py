"""Bounded solver-owned transport from a transonic field attachment.

The local transonic attachment binds a scalar shock branch to one retained
upstream node, but it does not show whether a characteristic can carry that
state toward the bounded reflected frontier.  This module advances one
declared characteristic family through the retained entropy field using the
field's own state sampler and pressure gradient.  It stops at the first
unavailable point; it never extrapolates, invents a downstream state, or
claims a globally placed shock.

The result is therefore a transport/coverage seam for the next MOC-1 packet,
not a mixed-regime closure or a production shock-cell input.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import cos, exp, hypot, isfinite, log, sin, sqrt
from typing import Any

from exhaust_plume.models.moc.chain import (
  MocChainTerminationDecision,
  MocChainTerminationReason,
)
from exhaust_plume.models.moc.euler_entropy_characteristic_field import (
  MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult,
)
from exhaust_plume.models.moc.primitives import (
  CharacteristicFamily,
  CharacteristicState,
)
from exhaust_plume.models.moc.transonic_attachment import (
  MocTransonicShockFieldAttachmentResult,
)

__all__ = (
  'MocTransonicCharacteristicTransportStatus',
  'MocTransonicCharacteristicTransportTermination',
  'MocTransonicCharacteristicTransportSample',
  'MocTransonicCharacteristicTransportSegment',
  'MocTransonicCharacteristicTransportRequest',
  'MocTransonicCharacteristicTransportResult',
  'solve_moc_transonic_characteristic_transport',
)


class MocTransonicCharacteristicTransportStatus(str, Enum):
  """Outcome of one bounded solver-owned characteristic transport."""

  CONVERGED_BOUNDED_TRANSPORT = (
    'converged-bounded-transonic-characteristic-transport'
  )
  INVALID_INPUT = 'invalid_input'
  ATTACHMENT_REQUIRED = 'transonic-transport-attachment-required'
  FIELD_REQUIRED = 'transonic-transport-field-required'
  PRESSURE_GRADIENT_REQUIRED = 'transonic-transport-pressure-gradient-required'
  START_SAMPLE_FAILURE = 'transonic-transport-start-sample-failure'
  DOMAIN_BOUNDARY = 'transonic-transport-reached-bounded-field-boundary'
  GEOMETRY_FAILURE = 'transonic-transport-geometry-failure'
  COMPATIBILITY_FAILURE = 'transonic-transport-compatibility-failure'
  PRESSURE_LINEAGE_FAILURE = 'transonic-transport-pressure-lineage-failure'
  MAXIMUM_STEPS = 'transonic-transport-maximum-steps'
####


class MocTransonicCharacteristicTransportTermination(str, Enum):
  """Why a bounded transport stopped."""

  FIELD_BOUNDARY = 'bounded-field-boundary'
  MAXIMUM_STEPS = 'maximum-step-count'
  FAILURE = 'transport-failure'
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


@dataclass(frozen=True, slots=True)
class MocTransonicCharacteristicTransportSample:
  """One exact state/pressure sample retained by bounded transport."""

  sample_index: int
  point_m: tuple[float, float]
  state: CharacteristicState
  total_pressure_Pa: float

  def __post_init__(self) -> None:
    if (
      isinstance(self.sample_index, bool)
      or not isinstance(self.sample_index, int)
      or self.sample_index < 0
    ):
      raise ValueError('sample_index must be a nonnegative integer')
    ####
    point = tuple(_finite(f'point_m[{index}]', value) for index, value in enumerate(self.point_m))
    if len(point) != 2:
      raise ValueError('point_m must contain two coordinates')
    ####
    if not isinstance(self.state, CharacteristicState):
      raise TypeError('state must be a CharacteristicState')
    ####
    if hypot(self.state.x_m - point[0], self.state.y_m - point[1]) > 1.0e-10:
      raise ValueError('state must lie on point_m')
    ####
    pressure = _finite('total_pressure_Pa', self.total_pressure_Pa)
    if pressure <= 0.0:
      raise ValueError('total_pressure_Pa must be positive')
    ####
    object.__setattr__(self, 'point_m', point)
    object.__setattr__(self, 'total_pressure_Pa', pressure)
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'sample_index': self.sample_index,
      'point_m': list(self.point_m),
      'mach': self.state.mach,
      'flow_angle_rad': self.state.theta_rad,
      'gamma': self.state.gamma,
      'total_pressure_Pa': self.total_pressure_Pa,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocTransonicCharacteristicTransportSegment:
  """Residuals for one transported characteristic segment."""

  segment_index: int
  family: CharacteristicFamily
  start_sample_index: int
  end_sample_index: int
  geometry_residual: float
  compatibility_residual: float
  pressure_residual: float
  forward_margin_m: float

  def __post_init__(self) -> None:
    if not isinstance(self.family, CharacteristicFamily):
      raise TypeError('family must be a CharacteristicFamily')
    ####
    for name in ('segment_index', 'start_sample_index', 'end_sample_index'):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer')
      ####
    ####
    if self.end_sample_index != self.start_sample_index + 1:
      raise ValueError('transport segment sample indices must be consecutive')
    ####
    for name in (
      'geometry_residual',
      'compatibility_residual',
      'pressure_residual',
    ):
      value = _finite(name, getattr(self, name))
      if value < 0.0:
        raise ValueError(f'{name} must be nonnegative')
      ####
      object.__setattr__(self, name, value)
    ####
    object.__setattr__(self, 'forward_margin_m', _finite('forward_margin_m', self.forward_margin_m))
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'segment_index': self.segment_index,
      'family': self.family.value,
      'start_sample_index': self.start_sample_index,
      'end_sample_index': self.end_sample_index,
      'geometry_residual': self.geometry_residual,
      'compatibility_residual': self.compatibility_residual,
      'pressure_residual': self.pressure_residual,
      'forward_margin_m': self.forward_margin_m,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocTransonicCharacteristicTransportRequest:
  """Inputs for advancing one attached characteristic inside the field."""

  attachment: MocTransonicShockFieldAttachmentResult
  family: CharacteristicFamily
  step_length_m: float = 1.0e-2
  maximum_steps: int = 64
  geometry_tolerance: float = 1.0e-2
  compatibility_tolerance: float = 1.0e-2
  pressure_tolerance: float = 1.0e-8
  position_tolerance_m: float = 1.0e-10

  def __post_init__(self) -> None:
    if not isinstance(
      self.attachment,
      MocTransonicShockFieldAttachmentResult,
    ):
      raise TypeError(
        'attachment must be a MocTransonicShockFieldAttachmentResult'
      )
    ####
    if not isinstance(self.family, CharacteristicFamily):
      raise TypeError('family must be a CharacteristicFamily')
    ####
    if (
      isinstance(self.maximum_steps, bool)
      or not isinstance(self.maximum_steps, int)
      or self.maximum_steps < 1
    ):
      raise ValueError('maximum_steps must be a positive integer')
    ####
    for name in (
      'step_length_m',
      'geometry_tolerance',
      'compatibility_tolerance',
      'pressure_tolerance',
      'position_tolerance_m',
    ):
      value = _finite(name, getattr(self, name))
      if value <= 0.0:
        raise ValueError(f'{name} must be positive')
      ####
      object.__setattr__(self, name, value)
    ####
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'attachment_status': self.attachment.status.value,
      'attachment_verified': self.attachment.attachment_verified,
      'family': self.family.value,
      'step_length_m': self.step_length_m,
      'maximum_steps': self.maximum_steps,
      'geometry_tolerance': self.geometry_tolerance,
      'compatibility_tolerance': self.compatibility_tolerance,
      'pressure_tolerance': self.pressure_tolerance,
      'position_tolerance_m': self.position_tolerance_m,
      'model': 'research-solver-owned-transonic-characteristic-transport-v1',
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocTransonicCharacteristicTransportResult:
  """A bounded characteristic path with explicit non-promotion gates."""

  status: MocTransonicCharacteristicTransportStatus
  request: MocTransonicCharacteristicTransportRequest
  termination: MocTransonicCharacteristicTransportTermination
  samples: tuple[MocTransonicCharacteristicTransportSample, ...]
  segments: tuple[MocTransonicCharacteristicTransportSegment, ...]
  first_unavailable_point_m: tuple[float, float] | None
  maximum_geometry_residual: float | None
  maximum_compatibility_residual: float | None
  maximum_pressure_residual: float | None
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocTransonicCharacteristicTransportStatus):
      raise TypeError('status must be a transport status')
    ####
    if not isinstance(self.request, MocTransonicCharacteristicTransportRequest):
      raise TypeError('request must be a transport request')
    ####
    if not isinstance(self.termination, MocTransonicCharacteristicTransportTermination):
      raise TypeError('termination must be a transport termination')
    ####
    samples = tuple(self.samples)
    segments = tuple(self.segments)
    if any(not isinstance(sample, MocTransonicCharacteristicTransportSample) for sample in samples):
      raise TypeError('samples must contain typed transport samples')
    ####
    if any(not isinstance(segment, MocTransonicCharacteristicTransportSegment) for segment in segments):
      raise TypeError('segments must contain typed transport segments')
    ####
    if tuple(sample.sample_index for sample in samples) != tuple(range(len(samples))):
      raise ValueError('transport samples must have contiguous indices')
    ####
    if len(segments) > 0 and len(segments) != len(samples) - 1:
      raise ValueError('transport segments must join every adjacent sample')
    ####
    if self.first_unavailable_point_m is not None:
      point = tuple(_finite(f'first_unavailable_point_m[{index}]', value) for index, value in enumerate(self.first_unavailable_point_m))
      if len(point) != 2:
        raise ValueError('first_unavailable_point_m must contain two coordinates')
      ####
      object.__setattr__(self, 'first_unavailable_point_m', point)
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
      numeric = _finite(name, value)
      if numeric < 0.0:
        raise ValueError(f'{name} must be nonnegative')
      ####
      object.__setattr__(self, name, numeric)
    ####
    object.__setattr__(self, 'samples', samples)
    object.__setattr__(self, 'segments', segments)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status is MocTransonicCharacteristicTransportStatus.CONVERGED_BOUNDED_TRANSPORT
  ####

  @property
  def bounded_transport_verified(self) -> bool:
    return bool(
      self.converged
      and self.request.attachment.attachment_verified
      and len(self.samples) >= 2
      and len(self.segments) == len(self.samples) - 1
      and self.termination is MocTransonicCharacteristicTransportTermination.FIELD_BOUNDARY
      and self.maximum_geometry_residual is not None
      and self.maximum_geometry_residual <= self.request.geometry_tolerance
      and self.maximum_compatibility_residual is not None
      and self.maximum_compatibility_residual <= self.request.compatibility_tolerance
      and self.maximum_pressure_residual is not None
      and self.maximum_pressure_residual <= self.request.pressure_tolerance
      and all(segment.forward_margin_m > self.request.position_tolerance_m for segment in self.segments)
    )
  ####

  @property
  def placement_verified(self) -> bool:
    """A bounded path does not solve a free-boundary shock placement."""

    return False
  ####

  @property
  def physical_closure_verified(self) -> bool:
    return False
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    return True
  ####

  @property
  def production_claim_allowed(self) -> bool:
    return False
  ####

  def as_chain_termination_decision(self) -> MocChainTerminationDecision:
    reason = (
      MocChainTerminationReason.INVALID_INPUT
      if self.status is MocTransonicCharacteristicTransportStatus.INVALID_INPUT
      else MocChainTerminationReason.FIDELITY_NOT_ALLOWED
    )
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=reason,
      message=self.message,
      diagnostics={
        'transport_status': self.status.value,
        'transport_termination': self.termination.value,
        'bounded_transport_verified': self.bounded_transport_verified,
        'placement_verified': False,
        'physical_closure_verified': False,
        'chain_promotion_blocked': True,
        'production_claim_allowed': False,
        'required_next_gate': (
          'solver-owned-shock-placement-neighboring-field-and-mixed-regime-'
          'closure-before-continued-shock-cell-chain'
        ),
      },
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'termination': self.termination.value,
      'bounded_transport_verified': self.bounded_transport_verified,
      'placement_verified': False,
      'physical_closure_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'sample_count': len(self.samples),
      'segment_count': len(self.segments),
      'first_unavailable_point_m': (
        None if self.first_unavailable_point_m is None else list(self.first_unavailable_point_m)
      ),
      'maximum_geometry_residual': self.maximum_geometry_residual,
      'maximum_compatibility_residual': self.maximum_compatibility_residual,
      'maximum_pressure_residual': self.maximum_pressure_residual,
      'samples': [sample.as_report() for sample in self.samples],
      'segments': [segment.as_report() for segment in self.segments],
      'request': self.request.as_report(),
      'chain_termination_decision': self.as_chain_termination_decision().as_report(),
      'claim_status': (
        'research-only-bounded-characteristic-transport; shock placement, '
        'mixed-regime closure, chain promotion, and external validation remain open'
      ),
      'message': self.message,
    }
  ####
####


def _failure(
  status: MocTransonicCharacteristicTransportStatus,
  request: MocTransonicCharacteristicTransportRequest,
  *,
  termination: MocTransonicCharacteristicTransportTermination = MocTransonicCharacteristicTransportTermination.FAILURE,
  samples: tuple[MocTransonicCharacteristicTransportSample, ...] = (),
  segments: tuple[MocTransonicCharacteristicTransportSegment, ...] = (),
  first_unavailable_point_m: tuple[float, float] | None = None,
  maximum_geometry_residual: float | None = None,
  maximum_compatibility_residual: float | None = None,
  maximum_pressure_residual: float | None = None,
  message: str,
) -> MocTransonicCharacteristicTransportResult:
  return MocTransonicCharacteristicTransportResult(
    status=status,
    request=request,
    termination=termination,
    samples=samples,
    segments=segments,
    first_unavailable_point_m=first_unavailable_point_m,
    maximum_geometry_residual=maximum_geometry_residual,
    maximum_compatibility_residual=maximum_compatibility_residual,
    maximum_pressure_residual=maximum_pressure_residual,
    message=message,
  )
####


def solve_moc_transonic_characteristic_transport(
  request: MocTransonicCharacteristicTransportRequest,
) -> MocTransonicCharacteristicTransportResult:
  """Advance one characteristic family until the retained field ends."""

  if not isinstance(request, MocTransonicCharacteristicTransportRequest):
    raise TypeError('request must be a MocTransonicCharacteristicTransportRequest')
  ####
  attachment = request.attachment
  if not attachment.attachment_verified or attachment.selected_point_m is None:
    return _failure(
      MocTransonicCharacteristicTransportStatus.ATTACHMENT_REQUIRED,
      request,
      message='transport requires a verified transonic field attachment with a selected point',
    )
  ####
  field = attachment.request.upstream_field
  if not isinstance(field, MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult):
    return _failure(
      MocTransonicCharacteristicTransportStatus.FIELD_REQUIRED,
      request,
      message='transport requires the retained entropy-characteristic field',
    )
  ####
  if not field.state_sampling_available:
    return _failure(
      MocTransonicCharacteristicTransportStatus.FIELD_REQUIRED,
      request,
      message='transport requires a locally consistent field with bounded sampling',
    )
  ####
  gradient = field.source_pressure_gradient
  if gradient is None or len(gradient) != 2 or not all(isfinite(value) for value in gradient):
    return _failure(
      MocTransonicCharacteristicTransportStatus.PRESSURE_GRADIENT_REQUIRED,
      request,
      message='transport requires the field-owned variable-entropy pressure gradient',
    )
  ####
  start_point = attachment.selected_point_m
  start_state = field.state_at(
    start_point,
    position_tolerance_m=request.position_tolerance_m,
  )
  start_pressure = field.total_pressure_at(
    start_point,
    position_tolerance_m=request.position_tolerance_m,
  )
  if start_state is None or start_pressure is None:
    return _failure(
      MocTransonicCharacteristicTransportStatus.START_SAMPLE_FAILURE,
      request,
      message='field sampler could not reproduce the attached shock point',
    )
  ####
  if attachment.sampled_upstream_state is not None and max(
    abs(start_state.theta_rad - attachment.sampled_upstream_state.theta_rad),
    abs(start_state.mach - attachment.sampled_upstream_state.mach),
    abs(start_state.gamma - attachment.sampled_upstream_state.gamma),
  ) > request.position_tolerance_m:
    return _failure(
      MocTransonicCharacteristicTransportStatus.START_SAMPLE_FAILURE,
      request,
      message='field sampler and attachment state disagree at the transport start',
    )
  ####

  samples = [
    MocTransonicCharacteristicTransportSample(
      sample_index=0,
      point_m=start_point,
      state=start_state,
      total_pressure_Pa=start_pressure,
    )
  ]
  segments: list[MocTransonicCharacteristicTransportSegment] = []
  point = start_point
  state = start_state
  pressure = start_pressure
  maximum_geometry = 0.0
  maximum_compatibility = 0.0
  maximum_pressure = 0.0
  for _step_index in range(request.maximum_steps):
    direction = state.direction(request.family)
    candidate = (
      point[0] + request.step_length_m * direction[0],
      point[1] + request.step_length_m * direction[1],
    )
    next_state = field.state_at(
      candidate,
      position_tolerance_m=request.position_tolerance_m,
    )
    next_pressure = field.total_pressure_at(
      candidate,
      position_tolerance_m=request.position_tolerance_m,
    )
    if next_state is None or next_pressure is None:
      if len(samples) < 2:
        return _failure(
          MocTransonicCharacteristicTransportStatus.DOMAIN_BOUNDARY,
          request,
          samples=tuple(samples),
          first_unavailable_point_m=candidate,
          message='attached characteristic leaves the bounded field before one segment is transported',
        )
      ####
      return _failure(
        MocTransonicCharacteristicTransportStatus.CONVERGED_BOUNDED_TRANSPORT,
        request,
        termination=MocTransonicCharacteristicTransportTermination.FIELD_BOUNDARY,
        samples=tuple(samples),
        segments=tuple(segments),
        first_unavailable_point_m=candidate,
        maximum_geometry_residual=maximum_geometry,
        maximum_compatibility_residual=maximum_compatibility,
        maximum_pressure_residual=maximum_pressure,
        message='characteristic transport reached the retained field boundary without extrapolation',
      )
    ####
    geometry = _geometry_residual(state, next_state, request.family)
    compatibility = abs(
      (
        next_state.k_plus - state.k_plus
        if request.family is CharacteristicFamily.PLUS
        else next_state.k_minus - state.k_minus
      )
      - _compatibility_source(state, next_state, gradient)
    )
    expected_pressure = pressure * exp(
      gradient[0] * (candidate[0] - state.x_m)
      + gradient[1] * (candidate[1] - state.y_m)
    )
    pressure_residual = abs(log(next_pressure / expected_pressure))
    forward_margin = _forward_margin(state, next_state, request.family)
    maximum_geometry = max(maximum_geometry, geometry)
    maximum_compatibility = max(maximum_compatibility, compatibility)
    maximum_pressure = max(maximum_pressure, pressure_residual)
    segment = MocTransonicCharacteristicTransportSegment(
      segment_index=len(segments),
      family=request.family,
      start_sample_index=len(samples) - 1,
      end_sample_index=len(samples),
      geometry_residual=geometry,
      compatibility_residual=compatibility,
      pressure_residual=pressure_residual,
      forward_margin_m=forward_margin,
    )
    segments.append(segment)
    samples.append(
      MocTransonicCharacteristicTransportSample(
        sample_index=len(samples),
        point_m=candidate,
        state=next_state,
        total_pressure_Pa=next_pressure,
      )
    )
    if forward_margin <= request.position_tolerance_m:
      return _failure(
        MocTransonicCharacteristicTransportStatus.GEOMETRY_FAILURE,
        request,
        samples=tuple(samples),
        segments=tuple(segments),
        maximum_geometry_residual=maximum_geometry,
        maximum_compatibility_residual=maximum_compatibility,
        maximum_pressure_residual=maximum_pressure,
        message='transport segment did not advance in the characteristic direction',
      )
    ####
    if geometry > request.geometry_tolerance:
      return _failure(
        MocTransonicCharacteristicTransportStatus.GEOMETRY_FAILURE,
        request,
        samples=tuple(samples),
        segments=tuple(segments),
        maximum_geometry_residual=maximum_geometry,
        maximum_compatibility_residual=maximum_compatibility,
        maximum_pressure_residual=maximum_pressure,
        message='transport characteristic geometry residual exceeded tolerance',
      )
    ####
    if compatibility > request.compatibility_tolerance:
      return _failure(
        MocTransonicCharacteristicTransportStatus.COMPATIBILITY_FAILURE,
        request,
        samples=tuple(samples),
        segments=tuple(segments),
        maximum_geometry_residual=maximum_geometry,
        maximum_compatibility_residual=maximum_compatibility,
        maximum_pressure_residual=maximum_pressure,
        message='transport variable-entropy compatibility residual exceeded tolerance',
      )
    ####
    if pressure_residual > request.pressure_tolerance:
      return _failure(
        MocTransonicCharacteristicTransportStatus.PRESSURE_LINEAGE_FAILURE,
        request,
        samples=tuple(samples),
        segments=tuple(segments),
        maximum_geometry_residual=maximum_geometry,
        maximum_compatibility_residual=maximum_compatibility,
        maximum_pressure_residual=maximum_pressure,
        message='transport total-pressure lineage residual exceeded tolerance',
      )
    ####
    point = candidate
    state = next_state
    pressure = next_pressure
  ####
  return _failure(
    MocTransonicCharacteristicTransportStatus.MAXIMUM_STEPS,
    request,
    termination=MocTransonicCharacteristicTransportTermination.MAXIMUM_STEPS,
    samples=tuple(samples),
    segments=tuple(segments),
    maximum_geometry_residual=maximum_geometry,
    maximum_compatibility_residual=maximum_compatibility,
    maximum_pressure_residual=maximum_pressure,
    message='transport reached maximum_steps before the retained field boundary',
  )
####
