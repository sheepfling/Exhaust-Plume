"""Reflected/free-boundary coupling for the entropy-characteristic lane.

The internal entropy-characteristic field exposes a finite, solver-owned
post-shock perimeter.  This module feeds that perimeter into the existing
ambient-attachment and centerline-reflection solve while retaining the
upstream field as a bounded source.  A field boundary is a typed result, not
an invitation to extrapolate a state.  Even a successful reflected field is
kept below continued-chain promotion until its independent Euler and external
validation gates are accepted.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import Enum
from math import hypot, isfinite
from typing import Any

from exhaust_plume.models.moc.chain import (
  MocChainBoundarySample,
  MocChainTerminationDecision,
  MocChainTerminationReason,
)
from exhaust_plume.models.moc.coupled import (
  MocAmbientPhysicalFieldResult,
  MocAmbientPhysicalFieldStatus,
  solve_marched_attached_shock_with_ambient_centerline_physical_field,
)
from exhaust_plume.models.moc.euler_entropy_characteristic_field import (
  MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult,
)
from exhaust_plume.models.moc.free_boundary import (
  MocFreeBoundaryShockResult,
  MocFreeBoundaryShockStatus,
)
from exhaust_plume.models.moc.primitives import CharacteristicState
from exhaust_plume.util.aero.shock_validity import ShockBranch

__all__ = (
  'MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryStatus',
  'MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryResult',
  'solve_euler_ambient_first_wedge_entropy_characteristic_free_boundary',
)


class MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryStatus(
  str,
  Enum,
):
  """Outcome of a bounded reflected/free-boundary coupling attempt."""

  CONVERGED_LOCAL_PHYSICAL_FIELD = (
    'converged_euler_ambient_first_wedge_entropy_characteristic_free_boundary'
  )
  INVALID_INPUT = 'invalid_input'
  FIELD_REQUIRED = 'entropy_characteristic_field_required'
  HANDOFF_FAILURE = 'entropy_characteristic_free_boundary_handoff_failure'
  UPSTREAM_FIELD_BOUNDARY = (
    'entropy_characteristic_free_boundary_upstream_field_boundary'
  )
  AMBIENT_ATTACHMENT_FAILURE = (
    'entropy_characteristic_free_boundary_ambient_attachment_failure'
  )
  REFLECTED_FIELD_FAILURE = (
    'entropy_characteristic_free_boundary_reflected_field_failure'
  )
####


def _finite_point(point_m: Sequence[float]) -> tuple[float, float] | None:
  try:
    point = (float(point_m[0]), float(point_m[1]))
  except (IndexError, TypeError, ValueError):
    return None
  ####
  if not all(isfinite(value) for value in point):
    return None
  ####
  return point
####


def _state_matches(
  actual: CharacteristicState,
  expected: CharacteristicState,
  *,
  position_tolerance_m: float,
  state_tolerance: float,
) -> bool:
  scale = max(1.0, abs(actual.mach), abs(expected.mach))
  return bool(
    abs(actual.x_m - expected.x_m) <= position_tolerance_m
    and abs(actual.y_m - expected.y_m) <= position_tolerance_m
    and abs(actual.theta_rad - expected.theta_rad)
    <= state_tolerance * max(1.0, abs(actual.theta_rad), abs(expected.theta_rad))
    and abs(actual.mach - expected.mach) <= state_tolerance * scale
    and abs(actual.gamma - expected.gamma)
    <= state_tolerance * max(1.0, abs(actual.gamma), abs(expected.gamma))
  )
####


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryResult:
  """A bounded ambient/centerline reflection attempt from an entropy field.

  ``CONVERGED_LOCAL_PHYSICAL_FIELD`` means that the existing reflected-field
  assembler returned a physically closed candidate.  It does not authorize a
  continued shock-cell chain: this lane still requires the independent field,
  conservative-Euler, refinement, and external-validation gates.
  """

  status: MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryStatus
  field: MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult | None
  physical_field: MocAmbientPhysicalFieldResult | None
  incoming_handoff: tuple[MocChainBoundarySample, ...]
  start_point_m: tuple[float, float] | None
  ambient_pressure_Pa: float | None
  outer_flow_angle_bracket: tuple[float, float] | None
  target_centerline_y_m: float | None
  target_centerline_flow_angle_rad: float | None
  allow_zero_strength_attachment: bool
  shock_sample_count: int
  covered_sample_count: int
  first_missing_sample_index: int | None
  maximum_state_residual: float | None
  maximum_pressure_residual: float | None
  ambient_boundary_sample_count: int
  position_tolerance_m: float
  state_tolerance: float
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryStatus,
    ):
      raise TypeError(
        'status must be a '
        'MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryStatus'
      )
    ####
    if self.field is not None and not isinstance(
      self.field,
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult,
    ):
      raise TypeError(
        'field must be a '
        'MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult or None'
      )
    ####
    if self.physical_field is not None and not isinstance(
      self.physical_field,
      MocAmbientPhysicalFieldResult,
    ):
      raise TypeError(
        'physical_field must be a MocAmbientPhysicalFieldResult or None'
      )
    ####
    handoff = tuple(self.incoming_handoff)
    if any(not isinstance(sample, MocChainBoundarySample) for sample in handoff):
      raise TypeError(
        'incoming_handoff must contain MocChainBoundarySample values'
      )
    ####
    object.__setattr__(self, 'incoming_handoff', handoff)
    if self.start_point_m is not None:
      point = _finite_point(self.start_point_m)
      if point is None:
        raise ValueError('start_point_m must contain two finite coordinates')
      ####
      object.__setattr__(self, 'start_point_m', point)
    ####
    if self.ambient_pressure_Pa is not None:
      pressure = float(self.ambient_pressure_Pa)
      if not isfinite(pressure) or pressure <= 0.0:
        raise ValueError('ambient_pressure_Pa must be finite and positive')
      ####
      object.__setattr__(self, 'ambient_pressure_Pa', pressure)
    ####
    if self.outer_flow_angle_bracket is not None:
      bracket = tuple(float(value) for value in self.outer_flow_angle_bracket)
      if len(bracket) != 2 or not all(isfinite(value) for value in bracket):
        raise ValueError(
          'outer_flow_angle_bracket must contain two finite values'
        )
      ####
      object.__setattr__(self, 'outer_flow_angle_bracket', bracket)
    ####
    for name in (
      'target_centerline_y_m',
      'target_centerline_flow_angle_rad',
    ):
      value = getattr(self, name)
      if value is not None:
        numeric = float(value)
        if not isfinite(numeric):
          raise ValueError(f'{name} must be finite when supplied')
        ####
        object.__setattr__(self, name, numeric)
      ####
    ####
    if not isinstance(self.allow_zero_strength_attachment, bool):
      raise TypeError('allow_zero_strength_attachment must be a bool')
    ####
    for name in (
      'shock_sample_count',
      'covered_sample_count',
      'ambient_boundary_sample_count',
    ):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer')
      ####
    ####
    if self.first_missing_sample_index is not None and (
      isinstance(self.first_missing_sample_index, bool)
      or not isinstance(self.first_missing_sample_index, int)
      or self.first_missing_sample_index < 0
    ):
      raise ValueError(
        'first_missing_sample_index must be a nonnegative integer or None'
      )
    ####
    for name in ('maximum_state_residual', 'maximum_pressure_residual'):
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
    for name in ('position_tolerance_m', 'state_tolerance'):
      value = float(getattr(self, name))
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      ####
      object.__setattr__(self, name, value)
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def shock(self) -> MocFreeBoundaryShockResult | None:
    """Return the retained attached-shock march, when one was attempted."""

    if self.physical_field is None or self.physical_field.ambient_attachment is None:
      return None
    ####
    return self.physical_field.ambient_attachment.shock
  ####

  @property
  def attachment_status(self) -> str | None:
    if self.physical_field is None or self.physical_field.ambient_attachment is None:
      return None
    ####
    return self.physical_field.ambient_attachment.status.value
  ####

  @property
  def physical_field_status(self) -> str | None:
    return None if self.physical_field is None else self.physical_field.status.value
  ####

  @property
  def path_coverage_verified(self) -> bool:
    return bool(
      self.shock is not None
      and self.shock.converged
      and self.shock_sample_count == self.covered_sample_count
      and self.first_missing_sample_index is None
    )
  ####

  @property
  def converged(self) -> bool:
    return self.reflected_free_boundary_verified
  ####

  @property
  def reflected_free_boundary_verified(self) -> bool:
    return bool(
      self.status
      is MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryStatus
      .CONVERGED_LOCAL_PHYSICAL_FIELD
      and self.physical_field is not None
      and self.physical_field.physical_closure_verified
    )
  ####

  @property
  def physical_closure_verified(self) -> bool:
    return self.reflected_free_boundary_verified
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    """Keep this entropy-lineage lane below chain promotion."""

    return True
  ####

  @property
  def production_claim_allowed(self) -> bool:
    return False
  ####

  @property
  def external_validation_required(self) -> bool:
    return True
  ####

  @property
  def local_consistency_verified(self) -> bool:
    return bool(
      self.field is not None
      and self.field.local_consistency_verified
      and self.incoming_handoff == self.field.continuation_boundary
      and (
        self.path_coverage_verified
        or self.status
        is MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryStatus
        .UPSTREAM_FIELD_BOUNDARY
      )
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
    )
  ####

  def as_chain_termination_decision(self) -> MocChainTerminationDecision:
    """Map closure progress to a non-promoting typed chain decision."""

    if self.status is (
      MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryStatus
      .INVALID_INPUT
    ):
      reason = MocChainTerminationReason.INVALID_INPUT
    elif self.status is (
      MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryStatus
      .FIELD_REQUIRED
    ):
      reason = MocChainTerminationReason.STATE_NOT_CARRIED
    elif self.status is (
      MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryStatus
      .HANDOFF_FAILURE
    ):
      reason = MocChainTerminationReason.STATE_NOT_CARRIED
    elif self.status is (
      MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryStatus
      .UPSTREAM_FIELD_BOUNDARY
    ):
      reason = MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
    elif self.status is (
      MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryStatus
      .CONVERGED_LOCAL_PHYSICAL_FIELD
    ):
      reason = MocChainTerminationReason.FIDELITY_NOT_ALLOWED
    else:
      reason = MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
    ####
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=reason,
      message=self.message,
      diagnostics={
        'free_boundary_status': self.status.value,
        'physical_field_status': self.physical_field_status,
        'attachment_status': self.attachment_status,
        'shock_sample_count': self.shock_sample_count,
        'covered_sample_count': self.covered_sample_count,
        'first_missing_sample_index': self.first_missing_sample_index,
        'path_coverage_verified': self.path_coverage_verified,
        'ambient_boundary_sample_count': self.ambient_boundary_sample_count,
        'reflected_free_boundary_verified': self.reflected_free_boundary_verified,
        'physical_closure_verified': self.physical_closure_verified,
        'chain_promotion_blocked': True,
        'production_claim_allowed': False,
        'external_validation_required': self.external_validation_required,
        'synthetic_downstream_field_created': False,
        'required_next_gate': (
          'independent-euler-refinement-and-external-validation-before-'
          'continued-shock-cell-chain'
        ),
      },
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'local_consistency_verified': self.local_consistency_verified,
      'path_coverage_verified': self.path_coverage_verified,
      'reflected_free_boundary_verified': self.reflected_free_boundary_verified,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'external_validation_required': self.external_validation_required,
      'incoming_handoff_sample_count': len(self.incoming_handoff),
      'start_point_m': self.start_point_m,
      'ambient_pressure_Pa': self.ambient_pressure_Pa,
      'outer_flow_angle_bracket': self.outer_flow_angle_bracket,
      'target_centerline_y_m': self.target_centerline_y_m,
      'target_centerline_flow_angle_rad': self.target_centerline_flow_angle_rad,
      'allow_zero_strength_attachment': self.allow_zero_strength_attachment,
      'shock_sample_count': self.shock_sample_count,
      'covered_sample_count': self.covered_sample_count,
      'first_missing_sample_index': self.first_missing_sample_index,
      'maximum_state_residual': self.maximum_state_residual,
      'maximum_pressure_residual': self.maximum_pressure_residual,
      'ambient_boundary_sample_count': self.ambient_boundary_sample_count,
      'attachment_status': self.attachment_status,
      'physical_field_status': self.physical_field_status,
      'shock': None if self.shock is None else self.shock.as_report(),
      'physical_field': (
        None if self.physical_field is None else self.physical_field.as_report()
      ),
      'chain_termination_decision': self.as_chain_termination_decision().as_report(),
      'message': self.message,
    }
  ####
####


def _failure(
  status: MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryStatus,
  field: MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult | None,
  *,
  physical_field: MocAmbientPhysicalFieldResult | None = None,
  incoming_handoff: Sequence[MocChainBoundarySample] = (),
  start_point_m: tuple[float, float] | None = None,
  ambient_pressure_Pa: float | None = None,
  outer_flow_angle_bracket: tuple[float, float] | None = None,
  target_centerline_y_m: float | None = None,
  target_centerline_flow_angle_rad: float | None = None,
  allow_zero_strength_attachment: bool = False,
  shock_sample_count: int = 0,
  covered_sample_count: int = 0,
  first_missing_sample_index: int | None = None,
  maximum_state_residual: float | None = None,
  maximum_pressure_residual: float | None = None,
  ambient_boundary_sample_count: int = 0,
  position_tolerance_m: float = 1.0e-10,
  state_tolerance: float = 1.0e-8,
  message: str,
) -> MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryResult:
  return MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryResult(
    status=status,
    field=field,
    physical_field=physical_field,
    incoming_handoff=tuple(incoming_handoff),
    start_point_m=start_point_m,
    ambient_pressure_Pa=ambient_pressure_Pa,
    outer_flow_angle_bracket=outer_flow_angle_bracket,
    target_centerline_y_m=target_centerline_y_m,
    target_centerline_flow_angle_rad=target_centerline_flow_angle_rad,
    allow_zero_strength_attachment=allow_zero_strength_attachment,
    shock_sample_count=shock_sample_count,
    covered_sample_count=covered_sample_count,
    first_missing_sample_index=first_missing_sample_index,
    maximum_state_residual=maximum_state_residual,
    maximum_pressure_residual=maximum_pressure_residual,
    ambient_boundary_sample_count=ambient_boundary_sample_count,
    position_tolerance_m=position_tolerance_m,
    state_tolerance=state_tolerance,
    message=message,
  )
####


def solve_euler_ambient_first_wedge_entropy_characteristic_free_boundary(
  field: MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult,
  incoming_handoff: Sequence[MocChainBoundarySample],
  start_point_m: tuple[float, float],
  ambient_pressure_Pa: float,
  outer_downstream_flow_angle_lower_rad: float,
  outer_downstream_flow_angle_upper_rad: float,
  *,
  target_centerline_y_m: float = 0.0,
  target_centerline_flow_angle_rad: float = 0.0,
  downstream_flow_angle_at: Callable[[int, tuple[float, float]], float] | None = None,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-10,
  state_tolerance: float = 1.0e-8,
  invariant_tolerance: float = 1.0e-10,
  attachment_pressure_tolerance: float = 1.0e-8,
  pressure_tolerance: float = 1.0e-8,
  tangent_tolerance: float = 1.0e-8,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
  maximum_boundary_iterations: int = 16,
  maximum_shooting_iterations: int = 40,
  allow_zero_strength_attachment: bool = False,
  allow_zero_strength_endpoints: bool = False,
  zero_strength_start_trace: Sequence[MocChainBoundarySample] | None = None,
) -> MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryResult:
  """Attempt reflected ambient/centerline closure on a bounded entropy field.

  The ambient pressure and outer-angle bracket are explicit inputs because
  this lane must not invent a plume environment or an attachment law.  The
  upstream callbacks are bounded samplers over ``field``; the wrapper returns
  ``UPSTREAM_FIELD_BOUNDARY`` as soon as the shock march leaves that domain.
  """

  if not isinstance(
    field,
    MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult,
  ):
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryStatus
      .INVALID_INPUT,
      None,
      message='field must be a MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult',
    )
  ####
  try:
    handoff = tuple(incoming_handoff)
  except TypeError:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryStatus
      .INVALID_INPUT,
      field,
      message='incoming_handoff must be an iterable of MocChainBoundarySample values',
    )
  ####
  if any(not isinstance(sample, MocChainBoundarySample) for sample in handoff):
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryStatus
      .INVALID_INPUT,
      field,
      incoming_handoff=handoff,
      message='incoming_handoff must contain MocChainBoundarySample values',
    )
  ####
  if not field.local_consistency_verified or not field.state_sampling_available:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryStatus
      .FIELD_REQUIRED,
      field,
      incoming_handoff=handoff,
      message=(
        'reflected/free-boundary coupling requires a locally consistent '
        'entropy-characteristic field with a bounded sampler'
      ),
    )
  ####
  if handoff != field.continuation_boundary or not handoff:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryStatus
      .HANDOFF_FAILURE,
      field,
      incoming_handoff=handoff,
      message=(
        'incoming_handoff must exactly match the non-empty solver-owned '
        'entropy-characteristic continuation perimeter'
      ),
    )
  ####
  point = _finite_point(start_point_m)
  if point is None:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryStatus
      .INVALID_INPUT,
      field,
      incoming_handoff=handoff,
      message='start_point_m must contain two finite coordinates',
    )
  ####
  try:
    ambient_pressure = float(ambient_pressure_Pa)
    lower_angle = float(outer_downstream_flow_angle_lower_rad)
    upper_angle = float(outer_downstream_flow_angle_upper_rad)
    target_y = float(target_centerline_y_m)
    target_angle = float(target_centerline_flow_angle_rad)
    position_tolerance = float(position_tolerance_m)
    state_tolerance_value = float(state_tolerance)
  except (TypeError, ValueError):
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryStatus
      .INVALID_INPUT,
      field,
      incoming_handoff=handoff,
      start_point_m=point,
      message='free-boundary coordinates, pressure, bracket, and tolerances must be numeric',
    )
  ####
  bracket = (lower_angle, upper_angle)
  if not all(
    isfinite(value)
    for value in (
      *point,
      ambient_pressure,
      lower_angle,
      upper_angle,
      target_y,
      target_angle,
      position_tolerance,
      state_tolerance_value,
    )
  ) or ambient_pressure <= 0.0:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryStatus
      .INVALID_INPUT,
      field,
      incoming_handoff=handoff,
      start_point_m=point,
      ambient_pressure_Pa=ambient_pressure,
      outer_flow_angle_bracket=bracket,
      target_centerline_y_m=target_y,
      target_centerline_flow_angle_rad=target_angle,
      position_tolerance_m=position_tolerance,
      state_tolerance=state_tolerance_value,
      message='free-boundary inputs must be finite and ambient pressure must be positive',
    )
  ####
  if lower_angle >= upper_angle or target_y >= point[1]:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryStatus
      .INVALID_INPUT,
      field,
      incoming_handoff=handoff,
      start_point_m=point,
      ambient_pressure_Pa=ambient_pressure,
      outer_flow_angle_bracket=bracket,
      target_centerline_y_m=target_y,
      target_centerline_flow_angle_rad=target_angle,
      position_tolerance_m=position_tolerance,
      state_tolerance=state_tolerance_value,
      message=(
        'outer angle bracket must be ordered and target centerline y must '
        'be below the shock start'
      ),
    )
  ####
  if hypot(point[0] - handoff[0].state.x_m, point[1] - handoff[0].state.y_m) > (
    position_tolerance
  ):
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryStatus
      .HANDOFF_FAILURE,
      field,
      incoming_handoff=handoff,
      start_point_m=point,
      ambient_pressure_Pa=ambient_pressure,
      outer_flow_angle_bracket=bracket,
      target_centerline_y_m=target_y,
      target_centerline_flow_angle_rad=target_angle,
      position_tolerance_m=position_tolerance,
      state_tolerance=state_tolerance_value,
      message='start_point_m must coincide with the first continuation perimeter sample',
    )
  ####
  if not isinstance(allow_zero_strength_attachment, bool):
    raise ValueError('allow_zero_strength_attachment must be a bool')
  ####
  if not isinstance(allow_zero_strength_endpoints, bool):
    raise ValueError('allow_zero_strength_endpoints must be a bool')
  ####
  if downstream_flow_angle_at is not None and not callable(downstream_flow_angle_at):
    raise ValueError('downstream_flow_angle_at must be callable when supplied')
  ####
  if not isinstance(branch, ShockBranch):
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryStatus
      .INVALID_INPUT,
      field,
      incoming_handoff=handoff,
      start_point_m=point,
      ambient_pressure_Pa=ambient_pressure,
      outer_flow_angle_bracket=bracket,
      target_centerline_y_m=target_y,
      target_centerline_flow_angle_rad=target_angle,
      allow_zero_strength_attachment=allow_zero_strength_attachment,
      position_tolerance_m=position_tolerance,
      state_tolerance=state_tolerance_value,
      message='branch must be a ShockBranch',
    )
  ####
  for name, value in (
    ('position_tolerance_m', position_tolerance),
    ('state_tolerance', state_tolerance_value),
    ('invariant_tolerance', invariant_tolerance),
    ('attachment_pressure_tolerance', attachment_pressure_tolerance),
    ('pressure_tolerance', pressure_tolerance),
    ('tangent_tolerance', tangent_tolerance),
    ('shock_angle_tolerance_rad', shock_angle_tolerance_rad),
  ):
    numeric = float(value)
    if not isfinite(numeric) or numeric <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
    ####
  ####
  for name, value in (
    ('sample_count', sample_count),
    ('maximum_segment_iterations', maximum_segment_iterations),
    ('maximum_boundary_iterations', maximum_boundary_iterations),
    ('maximum_shooting_iterations', maximum_shooting_iterations),
  ):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
      raise ValueError(f'{name} must be a positive integer')
    ####
  ####
  if sample_count < 3:
    raise ValueError('sample_count must be an integer of at least three')
  ####

  start_state = field.state_at(
    point,
    position_tolerance_m=position_tolerance,
  )
  start_pressure = field.static_pressure_at(
    point,
    position_tolerance_m=position_tolerance,
  )
  if start_state is None or start_pressure is None:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryStatus
      .UPSTREAM_FIELD_BOUNDARY,
      field,
      incoming_handoff=handoff,
      start_point_m=point,
      ambient_pressure_Pa=ambient_pressure,
      outer_flow_angle_bracket=bracket,
      target_centerline_y_m=target_y,
      target_centerline_flow_angle_rad=target_angle,
      allow_zero_strength_attachment=allow_zero_strength_attachment,
      position_tolerance_m=position_tolerance,
      state_tolerance=state_tolerance_value,
      message='shock start point is outside the bounded entropy-characteristic field',
    )
  ####

  def upstream_state_at(
    sample_point: tuple[float, float],
  ) -> CharacteristicState | None:
    return field.state_at(
      sample_point,
      position_tolerance_m=position_tolerance,
    )
  ####

  def upstream_pressure_at(
    sample_point: tuple[float, float],
  ) -> float | None:
    return field.static_pressure_at(
      sample_point,
      position_tolerance_m=position_tolerance,
    )
  ####

  try:
    physical_field = solve_marched_attached_shock_with_ambient_centerline_physical_field(
      upstream_state_at,
      upstream_pressure_at,
      point,
      ambient_pressure,
      lower_angle,
      upper_angle,
      target_centerline_y_m=target_y,
      target_centerline_flow_angle_rad=target_angle,
      incoming_handoff=handoff,
      sample_count=sample_count,
      branch=branch,
      position_tolerance_m=position_tolerance,
      invariant_tolerance=invariant_tolerance,
      attachment_pressure_tolerance=attachment_pressure_tolerance,
      pressure_tolerance=pressure_tolerance,
      tangent_tolerance=tangent_tolerance,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      maximum_segment_iterations=maximum_segment_iterations,
      maximum_boundary_iterations=maximum_boundary_iterations,
      maximum_shooting_iterations=maximum_shooting_iterations,
      allow_zero_strength_attachment=allow_zero_strength_attachment,
      zero_strength_start_trace=zero_strength_start_trace,
      allow_zero_strength_endpoints=allow_zero_strength_endpoints,
      downstream_flow_angle_at=downstream_flow_angle_at,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryStatus
      .REFLECTED_FIELD_FAILURE,
      field,
      incoming_handoff=handoff,
      start_point_m=point,
      ambient_pressure_Pa=ambient_pressure,
      outer_flow_angle_bracket=bracket,
      target_centerline_y_m=target_y,
      target_centerline_flow_angle_rad=target_angle,
      allow_zero_strength_attachment=allow_zero_strength_attachment,
      position_tolerance_m=position_tolerance,
      state_tolerance=state_tolerance_value,
      message=f'reflected/free-boundary coupling raised: {error}',
    )
  ####

  shock = (
    None
    if physical_field.ambient_attachment is None
    else physical_field.ambient_attachment.shock
  )
  shock_sample_count = 0 if shock is None else len(shock.shock_points_m)
  covered_count = 0
  first_missing: int | None = None
  state_residuals: list[float] = []
  pressure_residuals: list[float] = []
  if shock is not None:
    for index, (sample_point, expected_state, expected_pressure) in enumerate(
      zip(
        shock.shock_points_m,
        shock.upstream_states,
        shock.upstream_pressure_Pa,
        strict=True,
      )
    ):
      actual_state = field.state_at(
        sample_point,
        position_tolerance_m=position_tolerance,
      )
      actual_pressure = field.static_pressure_at(
        sample_point,
        position_tolerance_m=position_tolerance,
      )
      if actual_state is None or actual_pressure is None:
        first_missing = index
        break
      ####
      state_residuals.append(
        max(
          abs(actual_state.x_m - expected_state.x_m),
          abs(actual_state.y_m - expected_state.y_m),
          abs(actual_state.theta_rad - expected_state.theta_rad),
          abs(actual_state.mach - expected_state.mach),
          abs(actual_state.gamma - expected_state.gamma),
        )
      )
      pressure_residuals.append(abs(actual_pressure - expected_pressure))
      if not _state_matches(
        actual_state,
        expected_state,
        position_tolerance_m=position_tolerance,
        state_tolerance=state_tolerance_value,
      ) or abs(actual_pressure - expected_pressure) > state_tolerance_value * max(
        1.0,
        abs(actual_pressure),
        abs(expected_pressure),
      ):
        first_missing = index
        break
      ####
      covered_count += 1
    ####
  ####
  ambient_boundary_sample_count = 0
  if physical_field.ambient_attachment is not None:
    ambient_march = physical_field.ambient_attachment.ambient_march
    if ambient_march is not None:
      ambient_boundary_sample_count = len(ambient_march.boundary_samples)
    ####
  ####

  if shock is not None and shock.status is MocFreeBoundaryShockStatus.UPSTREAM_FIELD_FAILURE:
    if first_missing is None:
      first_missing = shock.failed_sample_index
    ####
    status = (
      MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryStatus
      .UPSTREAM_FIELD_BOUNDARY
    )
    message = (
      'reflected/free-boundary shock march reached the finite entropy-'
      'characteristic field boundary; no upstream extrapolation was used'
    )
  elif first_missing is not None:
    status = (
      MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryStatus
      .UPSTREAM_FIELD_BOUNDARY
    )
    message = (
      'independent shock-path sampling found a point outside or inconsistent '
      'with the bounded entropy-characteristic field'
    )
  elif physical_field.status is MocAmbientPhysicalFieldStatus.INVALID_INPUT:
    status = (
      MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryStatus
      .INVALID_INPUT
    )
    message = physical_field.message
  elif physical_field.ambient_attachment is None or not physical_field.ambient_attachment.converged:
    status = (
      MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryStatus
      .AMBIENT_ATTACHMENT_FAILURE
    )
    message = (
      'ambient attachment did not produce the boundary required for reflected '
      f'closure: {physical_field.message}'
    )
  elif not physical_field.converged or not physical_field.physical_closure_verified:
    status = (
      MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryStatus
      .REFLECTED_FIELD_FAILURE
    )
    message = (
      'ambient attachment completed, but the reflected physical field did not '
      f'pass its immutable closure gates: {physical_field.message}'
    )
  else:
    status = (
      MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryStatus
      .CONVERGED_LOCAL_PHYSICAL_FIELD
    )
    message = (
      'ambient attachment and centerline reflection produced a local physical '
      'field candidate; independent Euler refinement and external validation '
      'remain required before chain promotion'
    )
  ####
  return MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryResult(
    status=status,
    field=field,
    physical_field=physical_field,
    incoming_handoff=handoff,
    start_point_m=point,
    ambient_pressure_Pa=ambient_pressure,
    outer_flow_angle_bracket=bracket,
    target_centerline_y_m=target_y,
    target_centerline_flow_angle_rad=target_angle,
    allow_zero_strength_attachment=allow_zero_strength_attachment,
    shock_sample_count=shock_sample_count,
    covered_sample_count=covered_count,
    first_missing_sample_index=first_missing,
    maximum_state_residual=max(state_residuals, default=None),
    maximum_pressure_residual=max(pressure_residuals, default=None),
    ambient_boundary_sample_count=ambient_boundary_sample_count,
    position_tolerance_m=position_tolerance,
    state_tolerance=state_tolerance_value,
    message=message,
  )
####
