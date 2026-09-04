"""Solver-owned ambient-boundary coupling for the exact Euler shock lane.

The locally conservative Euler shock curve is not, by itself, a downstream
field.  This module adds the next narrow coupling step: it marches a
pressure-matched streamline boundary from the exact post-shock states and
uses that boundary as the second characteristic source for the existing
one-layer Euler strip.

The result remains intentionally open.  A reflected/free-boundary closure,
variable-entropy transport, and a continued physical shock-cell perimeter
are separate gates and are never inferred from the open strip topology.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Any, Sequence

from exhaust_plume.models.moc.ambient_boundary import (
  MocAmbientBoundarySample,
  MocAmbientBoundaryStatus,
  MocAmbientPressureBoundaryResult,
  validate_ambient_pressure_boundary,
)
from exhaust_plume.models.moc.boundary import (
  MocFreeBoundaryPointResult,
  solve_ambient_pressure_free_boundary_point,
)
from exhaust_plume.models.moc.chain import (
  MocChainBoundarySample,
  MocChainTerminationDecision,
  MocChainTerminationReason,
)
from exhaust_plume.models.moc.euler_characteristic_field import (
  MocEulerAmbientCompanionBoundaryResult,
  MocEulerCompanionFieldResult,
  assemble_euler_consistent_companion_characteristic_strip,
)
from exhaust_plume.models.moc.euler_shock_boundary import (
  MocEulerShockBoundaryCurveResult,
  MocEulerShockBoundaryOrientation,
)
from exhaust_plume.models.moc.primitives import (
  CharacteristicFamily,
  CharacteristicPointResult,
  CharacteristicState,
  MocPrimitiveStatus,
  interior_characteristic_point,
)

__all__ = (
  'MocEulerAmbientBoundaryMarchStatus',
  'MocEulerAmbientBoundaryMarchResult',
  'march_euler_ambient_boundary',
  'MocEulerAmbientAttachmentWedgeStatus',
  'MocEulerAmbientAttachmentWedgeTrial',
  'MocEulerAmbientAttachmentWedgeResult',
  'solve_euler_ambient_attachment_wedge',
  'MocEulerAmbientShockFieldStatus',
  'MocEulerAmbientShockFieldResult',
  'assemble_euler_ambient_shock_field',
  'assemble_euler_ambient_shock_field_from_companion',
)


class MocEulerAmbientBoundaryMarchStatus(str, Enum):
  """Outcome of marching an exact Euler shock trace to ambient pressure."""

  CONVERGED = 'converged_euler_ambient_boundary'
  INVALID_INPUT = 'invalid_input'
  SHOCK_BOUNDARY_REQUIRED = 'euler_shock_boundary_required'
  SHOCK_ORIENTATION_FAILURE = 'euler_shock_orientation_failure'
  ATTACHMENT_FAILURE = 'euler_ambient_attachment_failure'
  BOUNDARY_FAILURE = 'euler_ambient_boundary_failure'
  GEOMETRY_FAILURE = 'euler_ambient_boundary_geometry_failure'
  PRESSURE_FAILURE = 'euler_ambient_boundary_pressure_failure'
  INVARIANT_FAILURE = 'euler_ambient_boundary_invariant_failure'
####


class MocEulerAmbientAttachmentWedgeStatus(str, Enum):
  """Outcome of the one-sided first-wedge characteristic probe."""

  CONVERGED_FIRST_WEDGE = 'converged_euler_ambient_first_wedge'
  NO_FORWARD_INTERSECTION = 'euler_ambient_first_wedge_no_forward_intersection'
  INVALID_INPUT = 'invalid_input'
####


@dataclass(frozen=True, slots=True)
class MocEulerAmbientAttachmentWedgeTrial:
  """One ordered ``C+``/``C-`` source pairing tested at the attachment."""

  plus_source_index: int
  minus_source_index: int
  point_result: CharacteristicPointResult
  forward_margin_m: float | None
  accepted: bool

  def __post_init__(self) -> None:
    for name in ('plus_source_index', 'minus_source_index'):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer')
      ####
    ####
    if not isinstance(self.point_result, CharacteristicPointResult):
      raise TypeError('point_result must be a CharacteristicPointResult')
    ####
    if self.forward_margin_m is not None:
      margin = float(self.forward_margin_m)
      if not isfinite(margin):
        raise ValueError('forward_margin_m must be finite when supplied')
      ####
      object.__setattr__(self, 'forward_margin_m', margin)
    ####
    if not isinstance(self.accepted, bool):
      raise TypeError('accepted must be a bool')
    ####
  ####

  def as_report(self) -> dict[str, Any]:
    result = self.point_result
    return {
      'plus_source_index': self.plus_source_index,
      'minus_source_index': self.minus_source_index,
      'status': result.status.value,
      'point_m': None if result.point_m is None else list(result.point_m),
      'intersection_status': result.intersection_status,
      'forward_margin_m': self.forward_margin_m,
      'accepted': self.accepted,
      'message': result.message,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocEulerAmbientAttachmentWedgeResult:
  """Solver-owned evidence for the first interior wedge at a shared corner."""

  status: MocEulerAmbientAttachmentWedgeStatus
  trials: tuple[MocEulerAmbientAttachmentWedgeTrial, ...]
  accepted_plus_source_index: int | None = None
  accepted_minus_source_index: int | None = None
  accepted_point_m: tuple[float, float] | None = None
  accepted_state: CharacteristicState | None = None
  accepted_forward_margin_m: float | None = None
  position_tolerance_m: float = 1.0e-10
  invariant_tolerance: float = 1.0e-10
  physical_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocEulerAmbientAttachmentWedgeStatus):
      raise TypeError(
        'status must be a MocEulerAmbientAttachmentWedgeStatus'
      )
    ####
    trials = tuple(self.trials)
    if any(
      not isinstance(trial, MocEulerAmbientAttachmentWedgeTrial)
      for trial in trials
    ):
      raise TypeError(
        'trials must contain MocEulerAmbientAttachmentWedgeTrial values'
      )
    ####
    if (
      not trials
      and self.status is not MocEulerAmbientAttachmentWedgeStatus.INVALID_INPUT
    ):
      raise ValueError('trials must retain at least one source pairing')
    ####
    object.__setattr__(self, 'trials', trials)
    for name in ('position_tolerance_m', 'invariant_tolerance'):
      value = float(getattr(self, name))
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      ####
      object.__setattr__(self, name, value)
    ####
    for name in ('accepted_plus_source_index', 'accepted_minus_source_index'):
      value = getattr(self, name)
      if value is not None and (
        isinstance(value, bool) or not isinstance(value, int) or value < 0
      ):
        raise ValueError(f'{name} must be a nonnegative integer or None')
      ####
    ####
    if self.accepted_point_m is not None:
      if len(self.accepted_point_m) != 2 or not all(
        isfinite(float(value)) for value in self.accepted_point_m
      ):
        raise ValueError('accepted_point_m must contain two finite coordinates')
      ####
      object.__setattr__(
        self,
        'accepted_point_m',
        (float(self.accepted_point_m[0]), float(self.accepted_point_m[1])),
      )
    ####
    if self.accepted_state is not None and not isinstance(
      self.accepted_state,
      CharacteristicState,
    ):
      raise TypeError('accepted_state must be a CharacteristicState or None')
    ####
    if self.accepted_forward_margin_m is not None:
      margin = float(self.accepted_forward_margin_m)
      if not isfinite(margin) or margin <= 0.0:
        raise ValueError(
          'accepted_forward_margin_m must be finite and positive when supplied'
        )
      ####
      object.__setattr__(self, 'accepted_forward_margin_m', margin)
    ####
    if self.status is MocEulerAmbientAttachmentWedgeStatus.CONVERGED_FIRST_WEDGE:
      if (
        self.accepted_plus_source_index is None
        or self.accepted_minus_source_index is None
        or self.accepted_point_m is None
        or self.accepted_state is None
        or self.accepted_forward_margin_m is None
      ):
        raise ValueError(
          'a converged first wedge must retain its accepted source pairing, '
          'state, point, and forward margin'
        )
      ####
    ####
    for name in (
      'physical_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status is MocEulerAmbientAttachmentWedgeStatus.CONVERGED_FIRST_WEDGE
  ####

  @property
  def accepted_trial(self) -> MocEulerAmbientAttachmentWedgeTrial | None:
    for trial in self.trials:
      if trial.accepted:
        return trial
      ####
    ####
    return None
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'trial_count': len(self.trials),
      'trials': [trial.as_report() for trial in self.trials],
      'accepted_plus_source_index': self.accepted_plus_source_index,
      'accepted_minus_source_index': self.accepted_minus_source_index,
      'accepted_point_m': (
        None
        if self.accepted_point_m is None
        else list(self.accepted_point_m)
      ),
      'accepted_forward_margin_m': self.accepted_forward_margin_m,
      'position_tolerance_m': self.position_tolerance_m,
      'invariant_tolerance': self.invariant_tolerance,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'message': self.message,
    }
  ####
####


def solve_euler_ambient_attachment_wedge(
  shock_boundary: MocEulerShockBoundaryCurveResult,
  ambient_march: MocEulerAmbientBoundaryMarchResult,
  *,
  candidate_span: int = 2,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
) -> MocEulerAmbientAttachmentWedgeResult:
  """Probe one-sided characteristic pairings at a shared boundary corner.

  The generic companion strip pairs shock and companion samples by the same
  index.  That pairing is singular at a shared attachment, where both source
  states and points coincide.  This probe searches nearby cross-index pairs
  and retains their exact characteristic results and forward margins.  It is
  evidence for a future remesh, not a completed physical cell.
  """

  if not isinstance(shock_boundary, MocEulerShockBoundaryCurveResult):
    return MocEulerAmbientAttachmentWedgeResult(
      status=MocEulerAmbientAttachmentWedgeStatus.INVALID_INPUT,
      trials=(),
      message='shock_boundary must be a MocEulerShockBoundaryCurveResult',
    )
  ####
  if not isinstance(ambient_march, MocEulerAmbientBoundaryMarchResult):
    return MocEulerAmbientAttachmentWedgeResult(
      status=MocEulerAmbientAttachmentWedgeStatus.INVALID_INPUT,
      trials=(),
      message=(
        'ambient_march must be a MocEulerAmbientBoundaryMarchResult'
      ),
    )
  ####
  if (
    isinstance(candidate_span, bool)
    or not isinstance(candidate_span, int)
    or candidate_span < 1
  ):
    raise ValueError('candidate_span must be a positive integer')
  ####
  try:
    position_tolerance = float(position_tolerance_m)
    invariant_tolerance_value = float(invariant_tolerance)
  except (TypeError, ValueError):
    return MocEulerAmbientAttachmentWedgeResult(
      status=MocEulerAmbientAttachmentWedgeStatus.INVALID_INPUT,
      trials=(),
      message='attachment-wedge tolerances must be numeric',
    )
  ####
  for name, value in (
    ('position_tolerance_m', position_tolerance),
    ('invariant_tolerance', invariant_tolerance_value),
  ):
    if not isfinite(value) or value <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
    ####
  ####
  if not (
    shock_boundary.converged
    and shock_boundary.local_euler_verified
    and ambient_march.converged
  ):
    return MocEulerAmbientAttachmentWedgeResult(
      status=MocEulerAmbientAttachmentWedgeStatus.INVALID_INPUT,
      trials=(),
      position_tolerance_m=position_tolerance,
      invariant_tolerance=invariant_tolerance_value,
      message=(
        'attachment-wedge probe requires converged exact shock and ambient '
        'boundary results'
      ),
    )
  ####
  shock_points = tuple(shock_boundary.shock_points_m)
  samples = tuple(ambient_march.boundary_samples)
  if len(shock_points) < 2 or len(samples) != len(shock_points):
    return MocEulerAmbientAttachmentWedgeResult(
      status=MocEulerAmbientAttachmentWedgeStatus.INVALID_INPUT,
      trials=(),
      position_tolerance_m=position_tolerance,
      invariant_tolerance=invariant_tolerance_value,
      message=(
        'attachment-wedge probe requires aligned shock and ambient samples'
      ),
    )
  ####
  first_shock = shock_points[0]
  first_ambient = samples[0].point_m
  if any(
    abs(first_shock[axis] - first_ambient[axis]) > position_tolerance
    for axis in (0, 1)
  ):
    return MocEulerAmbientAttachmentWedgeResult(
      status=MocEulerAmbientAttachmentWedgeStatus.INVALID_INPUT,
      trials=(),
      position_tolerance_m=position_tolerance,
      invariant_tolerance=invariant_tolerance_value,
      message=(
        'attachment-wedge probe requires the first shock and ambient '
        'samples to share a physical attachment point'
      ),
    )
  ####

  pairs: list[tuple[int, int]] = []
  maximum_index = len(samples) - 1
  for distance in range(1, candidate_span + 1):
    for plus_index in range(distance + 1):
      minus_index = distance - plus_index
      if plus_index <= maximum_index and minus_index <= maximum_index:
        pairs.append((plus_index, minus_index))
      ####
    ####
  ####
  trials: list[MocEulerAmbientAttachmentWedgeTrial] = []
  accepted_plus_index: int | None = None
  accepted_minus_index: int | None = None
  accepted_point: tuple[float, float] | None = None
  accepted_state: CharacteristicState | None = None
  accepted_margin: float | None = None
  for plus_index, minus_index in pairs:
    point_result = interior_characteristic_point(
      shock_boundary.downstream_states[plus_index],
      samples[minus_index].state,
      position_tolerance_m=position_tolerance,
      invariant_tolerance=invariant_tolerance_value,
    )
    margin = None
    if point_result.point_m is not None:
      margin = point_result.point_m[0] - max(
        shock_boundary.downstream_states[plus_index].x_m,
        samples[minus_index].state.x_m,
      )
    ####
    accepted = bool(
      point_result.converged
      and point_result.point_m is not None
      and point_result.state is not None
      and margin is not None
      and margin > position_tolerance
    )
    trials.append(
      MocEulerAmbientAttachmentWedgeTrial(
        plus_source_index=plus_index,
        minus_source_index=minus_index,
        point_result=point_result,
        forward_margin_m=margin,
        accepted=accepted,
      )
    )
    if accepted:
      accepted_plus_index = plus_index
      accepted_minus_index = minus_index
      accepted_point = point_result.point_m
      accepted_state = point_result.state
      accepted_margin = margin
      break
    ####
  ####

  if accepted_plus_index is not None:
    return MocEulerAmbientAttachmentWedgeResult(
      status=MocEulerAmbientAttachmentWedgeStatus.CONVERGED_FIRST_WEDGE,
      trials=tuple(trials),
      accepted_plus_source_index=accepted_plus_index,
      accepted_minus_source_index=accepted_minus_index,
      accepted_point_m=accepted_point,
      accepted_state=accepted_state,
      accepted_forward_margin_m=accepted_margin,
      position_tolerance_m=position_tolerance,
      invariant_tolerance=invariant_tolerance_value,
      message=(
        'attachment-aware first characteristic wedge found a forward '
        'C+/C- intersection; full reflected field remesh remains pending'
      ),
    )
  ####
  return MocEulerAmbientAttachmentWedgeResult(
    status=MocEulerAmbientAttachmentWedgeStatus.NO_FORWARD_INTERSECTION,
    trials=tuple(trials),
    position_tolerance_m=position_tolerance,
    invariant_tolerance=invariant_tolerance_value,
    message=(
      'attachment-aware first-wedge probe found no admissible forward '
      'C+/C- intersection in its candidate source span'
    ),
  )
####


def _empty_ambient_boundary(
  ambient_pressure_Pa: float | None,
  *,
  message: str,
) -> MocAmbientPressureBoundaryResult:
  return MocAmbientPressureBoundaryResult(
    status=MocAmbientBoundaryStatus.INVALID_INPUT,
    points_m=(),
    states=(),
    total_pressure_Pa=(),
    static_pressure_Pa=(),
    pressure_residuals=(),
    tangent_residuals=(),
    ambient_pressure_Pa=ambient_pressure_Pa,
    maximum_absolute_pressure_residual=None,
    maximum_absolute_tangent_residual=None,
    message=message,
  )
####


@dataclass(frozen=True, slots=True)
class MocEulerAmbientBoundaryMarchResult:
  """Exact-Euler shock-to-ambient boundary evidence.

  The first sample is a shared shock/ambient attachment.  Later samples are
  obtained by preserving the shock-sourced ``C+`` invariant while solving for
  ambient static pressure and streamline tangency.  This is a physical
  boundary march, but it is not the downstream reflected closure.
  """

  status: MocEulerAmbientBoundaryMarchStatus
  shock_boundary: MocEulerShockBoundaryCurveResult | None
  ambient_pressure_Pa: float | None
  boundary_samples: tuple[MocAmbientBoundarySample, ...]
  point_results: tuple[MocFreeBoundaryPointResult, ...]
  ambient_boundary: MocAmbientPressureBoundaryResult
  incoming_k_plus_residuals: tuple[float, ...]
  attachment_relative_pressure_residual: float | None
  maximum_geometry_residual_m: float | None
  maximum_absolute_pressure_residual: float | None
  maximum_absolute_invariant_residual: float | None
  physical_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocEulerAmbientBoundaryMarchStatus):
      raise TypeError(
        'status must be a MocEulerAmbientBoundaryMarchStatus'
      )
    ####
    if self.shock_boundary is not None and not isinstance(
      self.shock_boundary,
      MocEulerShockBoundaryCurveResult,
    ):
      raise TypeError(
        'shock_boundary must be a MocEulerShockBoundaryCurveResult or None'
      )
    ####
    if self.ambient_pressure_Pa is not None:
      ambient_pressure = float(self.ambient_pressure_Pa)
      if not isfinite(ambient_pressure) or ambient_pressure <= 0.0:
        raise ValueError(
          'ambient_pressure_Pa must be finite and positive when supplied'
        )
      ####
      object.__setattr__(self, 'ambient_pressure_Pa', ambient_pressure)
    ####
    if not isinstance(
      self.ambient_boundary,
      MocAmbientPressureBoundaryResult,
    ):
      raise TypeError(
        'ambient_boundary must be a MocAmbientPressureBoundaryResult'
      )
    ####
    samples = tuple(self.boundary_samples)
    point_results = tuple(self.point_results)
    residuals = tuple(float(value) for value in self.incoming_k_plus_residuals)
    if any(
      not isinstance(sample, MocAmbientBoundarySample)
      for sample in samples
    ):
      raise TypeError(
        'boundary_samples must contain MocAmbientBoundarySample values'
      )
    ####
    if any(
      not isinstance(result, MocFreeBoundaryPointResult)
      for result in point_results
    ):
      raise TypeError(
        'point_results must contain MocFreeBoundaryPointResult values'
      )
    ####
    if len(samples) != len(point_results) or len(samples) != len(residuals):
      raise ValueError(
        'boundary samples, point results, and invariant residuals must align'
      )
    ####
    if any(not isfinite(value) or value < 0.0 for value in residuals):
      raise ValueError(
        'incoming_k_plus_residuals must contain finite nonnegative values'
      )
    ####
    object.__setattr__(self, 'boundary_samples', samples)
    object.__setattr__(self, 'point_results', point_results)
    object.__setattr__(self, 'incoming_k_plus_residuals', residuals)
    for name in (
      'attachment_relative_pressure_residual',
      'maximum_geometry_residual_m',
      'maximum_absolute_pressure_residual',
      'maximum_absolute_invariant_residual',
    ):
      value = getattr(self, name)
      if value is None:
        continue
      ####
      numeric = float(value)
      if not isfinite(numeric):
        raise ValueError(f'{name} must be finite when supplied')
      ####
      if name != 'attachment_relative_pressure_residual' and numeric < 0.0:
        raise ValueError(f'{name} must be nonnegative when supplied')
      ####
      object.__setattr__(self, name, numeric)
    ####
    for name in (
      'physical_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    """Whether the exact-Euler ambient boundary passed its local gates."""

    return self.status is MocEulerAmbientBoundaryMarchStatus.CONVERGED
  ####

  @property
  def state_sampling_available(self) -> bool:
    return bool(self.converged and len(self.boundary_samples) >= 2)
  ####

  @property
  def points_m(self) -> tuple[tuple[float, float], ...]:
    return tuple(sample.point_m for sample in self.boundary_samples)
  ####

  @property
  def boundary_handoff(self) -> tuple[MocChainBoundarySample, ...]:
    """Return the marched boundary as an explicit state-carrying trace."""

    if not self.state_sampling_available:
      return ()
    ####
    return tuple(
      MocChainBoundarySample(
        state=sample.state,
        total_pressure_Pa=sample.total_pressure_Pa,
      )
      for sample in self.boundary_samples
    )
  ####

  def as_chain_termination_decision(self) -> MocChainTerminationDecision:
    """Expose the open physical boundary to a continued-chain planner."""

    if self.converged:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE,
        message=(
          'exact-Euler ambient shock field has a local pressure-matched '
          'boundary, but reflected/free-boundary closure remains open'
        ),
        diagnostics={
          'ambient_boundary_status': self.status.value,
          'chain_promotion_blocked': True,
          'physical_closure_verified': False,
        },
      )
    ####
    if self.status is MocEulerAmbientBoundaryMarchStatus.INVALID_INPUT:
      reason = MocChainTerminationReason.INVALID_INPUT
    elif self.status in (
      MocEulerAmbientBoundaryMarchStatus.SHOCK_BOUNDARY_REQUIRED,
      MocEulerAmbientBoundaryMarchStatus.SHOCK_ORIENTATION_FAILURE,
    ):
      reason = MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
    elif self.status is MocEulerAmbientBoundaryMarchStatus.INVARIANT_FAILURE:
      reason = MocChainTerminationReason.FIDELITY_NOT_ALLOWED
    else:
      reason = MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
    ####
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=reason,
      message=self.message,
      diagnostics={
        'ambient_boundary_status': self.status.value,
        'chain_promotion_blocked': True,
        'physical_closure_verified': False,
      },
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'state_sampling_available': self.state_sampling_available,
      'ambient_pressure_Pa': self.ambient_pressure_Pa,
      'sample_count': len(self.boundary_samples),
      'points_m': [list(point) for point in self.points_m],
      'mach': [sample.state.mach for sample in self.boundary_samples],
      'flow_angles_rad': [
        sample.state.theta_rad for sample in self.boundary_samples
      ],
      'total_pressure_Pa': [
        sample.total_pressure_Pa for sample in self.boundary_samples
      ],
      'incoming_k_plus_residuals': list(self.incoming_k_plus_residuals),
      'attachment_relative_pressure_residual': (
        self.attachment_relative_pressure_residual
      ),
      'maximum_geometry_residual_m': self.maximum_geometry_residual_m,
      'maximum_absolute_pressure_residual': (
        self.maximum_absolute_pressure_residual
      ),
      'maximum_absolute_invariant_residual': (
        self.maximum_absolute_invariant_residual
      ),
      'ambient_boundary': self.ambient_boundary.as_report(),
      'point_statuses': [result.status.value for result in self.point_results],
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'chain_termination_decision': (
        self.as_chain_termination_decision().as_report()
      ),
      'message': self.message,
    }
  ####
####


def _march_failure(
  status: MocEulerAmbientBoundaryMarchStatus,
  shock_boundary: MocEulerShockBoundaryCurveResult | None,
  ambient_pressure_Pa: float | None,
  *,
  samples: Sequence[MocAmbientBoundarySample] = (),
  point_results: Sequence[MocFreeBoundaryPointResult] = (),
  incoming_k_plus_residuals: Sequence[float] = (),
  attachment_relative_pressure_residual: float | None = None,
  ambient_boundary: MocAmbientPressureBoundaryResult | None = None,
  message: str,
) -> MocEulerAmbientBoundaryMarchResult:
  resolved_samples = tuple(samples)
  resolved_results = tuple(point_results)
  resolved_residuals = tuple(float(value) for value in incoming_k_plus_residuals)
  return MocEulerAmbientBoundaryMarchResult(
    status=status,
    shock_boundary=shock_boundary,
    ambient_pressure_Pa=ambient_pressure_Pa,
    boundary_samples=resolved_samples,
    point_results=resolved_results,
    ambient_boundary=(
      _empty_ambient_boundary(ambient_pressure_Pa, message=message)
      if ambient_boundary is None
      else ambient_boundary
    ),
    incoming_k_plus_residuals=resolved_residuals,
    attachment_relative_pressure_residual=attachment_relative_pressure_residual,
    maximum_geometry_residual_m=max(
      (
        abs(result.geometry_residual)
        for result in resolved_results
        if result.geometry_residual is not None
      ),
      default=None,
    ),
    maximum_absolute_pressure_residual=max(
      (
        abs(result.pressure_residual)
        for result in resolved_results
        if result.pressure_residual is not None
      ),
      default=None,
    ),
    maximum_absolute_invariant_residual=max(resolved_residuals, default=None),
    message=message,
  )
####


def _static_pressure_from_total(
  state: CharacteristicState,
  total_pressure_Pa: float,
) -> float:
  return float(total_pressure_Pa) / (
    1.0 + 0.5 * (state.gamma - 1.0) * state.mach * state.mach
  ) ** (state.gamma / (state.gamma - 1.0))
####


def march_euler_ambient_boundary(
  shock_boundary: MocEulerShockBoundaryCurveResult,
  ambient_pressure_Pa: float,
  *,
  target_centerline_y_m: float = 0.0,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  pressure_tolerance: float = 1.0e-8,
  maximum_iterations: int = 16,
) -> MocEulerAmbientBoundaryMarchResult:
  """March the exact post-shock ``C+`` sources to an ambient boundary.

  The attachment is strict: the first downstream shock static pressure must
  equal ``ambient_pressure_Pa``.  This prevents a low-pressure companion
  fixture from being mistaken for a physical shock/ambient corner.
  """

  if not isinstance(shock_boundary, MocEulerShockBoundaryCurveResult):
    return _march_failure(
      MocEulerAmbientBoundaryMarchStatus.INVALID_INPUT,
      None,
      None,
      message='shock_boundary must be a MocEulerShockBoundaryCurveResult',
    )
  ####
  try:
    ambient_pressure = float(ambient_pressure_Pa)
    target_y = float(target_centerline_y_m)
    position_tolerance = float(position_tolerance_m)
    invariant_tolerance_value = float(invariant_tolerance)
    pressure_tolerance_value = float(pressure_tolerance)
  except (TypeError, ValueError):
    return _march_failure(
      MocEulerAmbientBoundaryMarchStatus.INVALID_INPUT,
      shock_boundary,
      None,
      message=(
        'ambient pressure, target ordinate, and tolerances must be numeric'
      ),
    )
  ####
  if not isfinite(ambient_pressure) or ambient_pressure <= 0.0:
    raise ValueError('ambient_pressure_Pa must be finite and positive')
  ####
  if not isfinite(target_y):
    raise ValueError('target_centerline_y_m must be finite')
  ####
  for name, value in (
    ('position_tolerance_m', position_tolerance),
    ('invariant_tolerance', invariant_tolerance_value),
    ('pressure_tolerance', pressure_tolerance_value),
  ):
    if not isfinite(value) or value <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
    ####
  ####
  if isinstance(maximum_iterations, bool) or maximum_iterations < 1:
    raise ValueError('maximum_iterations must be a positive integer')
  ####
  if not shock_boundary.converged or not shock_boundary.local_euler_verified:
    return _march_failure(
      MocEulerAmbientBoundaryMarchStatus.SHOCK_BOUNDARY_REQUIRED,
      shock_boundary,
      ambient_pressure,
      message=(
        'exact Euler ambient march requires a locally Euler-verified shock '
        f'curve: {shock_boundary.message}'
      ),
    )
  ####
  if shock_boundary.orientation is not MocEulerShockBoundaryOrientation.MIXED_CHARACTERISTIC_BOUNDARY:
    return _march_failure(
      MocEulerAmbientBoundaryMarchStatus.SHOCK_ORIENTATION_FAILURE,
      shock_boundary,
      ambient_pressure,
      message=(
        'exact Euler ambient march requires the mixed-characteristic shock '
        'orientation so the shock supplies C+ sources'
      ),
    )
  ####
  points = tuple(shock_boundary.shock_points_m)
  states = tuple(shock_boundary.downstream_states)
  pressures = tuple(shock_boundary.downstream_total_pressure_Pa)
  if len(points) < 2 or not (len(points) == len(states) == len(pressures)):
    return _march_failure(
      MocEulerAmbientBoundaryMarchStatus.INVALID_INPUT,
      shock_boundary,
      ambient_pressure,
      message=(
        'exact Euler ambient march requires aligned shock points, states, '
        'and total pressures'
      ),
    )
  ####
  if any(
    abs(state.x_m - point[0]) > position_tolerance
    or abs(state.y_m - point[1]) > position_tolerance
    for state, point in zip(states, points, strict=True)
  ):
    return _march_failure(
      MocEulerAmbientBoundaryMarchStatus.INVALID_INPUT,
      shock_boundary,
      ambient_pressure,
      message='exact Euler shock states must lie on their shock sample points',
    )
  ####
  if any(
    points[index + 1][0] <= points[index][0] + position_tolerance
    or points[index + 1][1] > points[index][1] + position_tolerance
    for index in range(len(points) - 1)
  ):
    return _march_failure(
      MocEulerAmbientBoundaryMarchStatus.GEOMETRY_FAILURE,
      shock_boundary,
      ambient_pressure,
      message=(
        'exact Euler shock samples must advance downstream and not increase '
        'in ordinate'
      ),
    )
  ####
  if any(point[1] < target_y - position_tolerance for point in points):
    return _march_failure(
      MocEulerAmbientBoundaryMarchStatus.GEOMETRY_FAILURE,
      shock_boundary,
      ambient_pressure,
      message='exact Euler shock samples cross below the target centerline',
    )
  ####

  first_static_pressure = _static_pressure_from_total(states[0], pressures[0])
  attachment_residual = (
    first_static_pressure - ambient_pressure
  ) / ambient_pressure
  if abs(attachment_residual) > pressure_tolerance_value:
    first_result = MocFreeBoundaryPointResult(
      status=MocPrimitiveStatus.INVARIANT_FAILURE,
      family=CharacteristicFamily.PLUS,
      state=states[0],
      point_m=points[0],
      pressure_residual=attachment_residual,
      tangent_residual=None,
      geometry_residual=0.0,
      iterations=0,
      intersection_status='shared-shock-ambient-attachment',
      message='exact post-shock attachment static pressure does not match ambient',
    )
    first_sample = MocAmbientBoundarySample(
      point_m=points[0],
      state=states[0],
      total_pressure_Pa=pressures[0],
    )
    return _march_failure(
      MocEulerAmbientBoundaryMarchStatus.ATTACHMENT_FAILURE,
      shock_boundary,
      ambient_pressure,
      samples=(first_sample,),
      point_results=(first_result,),
      incoming_k_plus_residuals=(0.0,),
      attachment_relative_pressure_residual=attachment_residual,
      message=(
        'exact post-shock attachment static pressure does not match ambient: '
        f'relative residual={attachment_residual}'
      ),
    )
  ####

  samples: list[MocAmbientBoundarySample] = [
    MocAmbientBoundarySample(
      point_m=points[0],
      state=states[0],
      total_pressure_Pa=pressures[0],
    )
  ]
  point_results: list[MocFreeBoundaryPointResult] = [
    MocFreeBoundaryPointResult(
      status=MocPrimitiveStatus.CONVERGED,
      family=CharacteristicFamily.PLUS,
      state=states[0],
      point_m=points[0],
      pressure_residual=attachment_residual,
      tangent_residual=None,
      geometry_residual=0.0,
      iterations=0,
      intersection_status='shared-shock-ambient-attachment',
    )
  ]
  k_plus_residuals: list[float] = [0.0]
  previous_boundary = states[0]
  for index, (state, total_pressure, shock_point) in enumerate(
    zip(states[1:], pressures[1:], points[1:], strict=True),
    start=1,
  ):
    result = solve_ambient_pressure_free_boundary_point(
      state,
      previous_boundary,
      CharacteristicFamily.PLUS,
      total_pressure_Pa=float(total_pressure),
      ambient_pressure_Pa=ambient_pressure,
      position_tolerance_m=position_tolerance,
      pressure_tolerance=pressure_tolerance_value,
      maximum_iterations=maximum_iterations,
    )
    point_results.append(result)
    if not result.converged or result.state is None or result.point_m is None:
      return _march_failure(
        MocEulerAmbientBoundaryMarchStatus.BOUNDARY_FAILURE,
        shock_boundary,
        ambient_pressure,
        samples=samples,
        point_results=point_results,
        incoming_k_plus_residuals=k_plus_residuals,
        attachment_relative_pressure_residual=attachment_residual,
        message=f'exact Euler ambient boundary sample {index} failed: {result.message}',
      )
    ####
    if result.point_m[0] <= previous_boundary.x_m + position_tolerance:
      return _march_failure(
        MocEulerAmbientBoundaryMarchStatus.GEOMETRY_FAILURE,
        shock_boundary,
        ambient_pressure,
        samples=samples,
        point_results=point_results,
        incoming_k_plus_residuals=k_plus_residuals,
        attachment_relative_pressure_residual=attachment_residual,
        message=(
          f'exact Euler ambient boundary sample {index} is not strictly '
          'downstream'
        ),
      )
    ####
    if result.point_m[1] < target_y - position_tolerance:
      return _march_failure(
        MocEulerAmbientBoundaryMarchStatus.GEOMETRY_FAILURE,
        shock_boundary,
        ambient_pressure,
        samples=samples,
        point_results=point_results,
        incoming_k_plus_residuals=k_plus_residuals,
        attachment_relative_pressure_residual=attachment_residual,
        message=(
          f'exact Euler ambient boundary sample {index} crossed below the '
          'target centerline'
        ),
      )
    ####
    k_plus_residual = abs(result.state.k_plus - state.k_plus)
    k_plus_residuals.append(k_plus_residual)
    if k_plus_residual > invariant_tolerance_value:
      return _march_failure(
        MocEulerAmbientBoundaryMarchStatus.INVARIANT_FAILURE,
        shock_boundary,
        ambient_pressure,
        samples=samples,
        point_results=point_results,
        incoming_k_plus_residuals=k_plus_residuals,
        attachment_relative_pressure_residual=attachment_residual,
        message=(
          f'exact Euler ambient boundary sample {index} did not preserve '
          'the shock-sourced C+ invariant'
        ),
      )
    ####
    samples.append(
      MocAmbientBoundarySample(
        point_m=result.point_m,
        state=result.state,
        total_pressure_Pa=float(total_pressure),
      )
    )
    previous_boundary = result.state
  ####

  ambient_boundary = validate_ambient_pressure_boundary(
    samples,
    ambient_pressure,
    position_tolerance_m=position_tolerance,
    pressure_tolerance=pressure_tolerance_value,
    tangent_tolerance=pressure_tolerance_value,
  )
  if not ambient_boundary.converged:
    status = (
      MocEulerAmbientBoundaryMarchStatus.PRESSURE_FAILURE
      if ambient_boundary.status is MocAmbientBoundaryStatus.PRESSURE_FAILURE
      else MocEulerAmbientBoundaryMarchStatus.GEOMETRY_FAILURE
    )
    return _march_failure(
      status,
      shock_boundary,
      ambient_pressure,
      samples=samples,
      point_results=point_results,
      incoming_k_plus_residuals=k_plus_residuals,
      attachment_relative_pressure_residual=attachment_residual,
      ambient_boundary=ambient_boundary,
      message=(
        'exact Euler ambient boundary failed independent pressure/tangent '
        f'acceptance: {ambient_boundary.message}'
      ),
    )
  ####
  return MocEulerAmbientBoundaryMarchResult(
    status=MocEulerAmbientBoundaryMarchStatus.CONVERGED,
    shock_boundary=shock_boundary,
    ambient_pressure_Pa=ambient_pressure,
    boundary_samples=tuple(samples),
    point_results=tuple(point_results),
    ambient_boundary=ambient_boundary,
    incoming_k_plus_residuals=tuple(k_plus_residuals),
    attachment_relative_pressure_residual=attachment_residual,
    maximum_geometry_residual_m=max(
      (
        abs(result.geometry_residual)
        for result in point_results
        if result.geometry_residual is not None
      ),
      default=None,
    ),
    maximum_absolute_pressure_residual=(
      ambient_boundary.maximum_absolute_pressure_residual
    ),
    maximum_absolute_invariant_residual=max(k_plus_residuals, default=None),
    message=(
      'exact Euler shock-sourced C+ characteristics generated an accepted '
      'ambient-pressure, streamline-tangent boundary; downstream reflected '
      'closure remains pending'
    ),
  )
####


class MocEulerAmbientShockFieldStatus(str, Enum):
  """Outcome of coupling an exact shock to an ambient open strip."""

  CONVERGED_OPEN = 'converged_open_euler_ambient_shock_field'
  INVALID_INPUT = 'invalid_input'
  SHOCK_BOUNDARY_REQUIRED = 'euler_shock_boundary_required'
  AMBIENT_BOUNDARY_FAILURE = 'euler_ambient_boundary_failure'
  ENTROPY_TRANSPORT_REQUIRED = 'euler_entropy_transport_required'
  ATTACHMENT_GEOMETRY_FAILURE = 'euler_attachment_geometry_failure'
  FIELD_FAILURE = 'euler_ambient_shock_field_failure'
####


@dataclass(frozen=True, slots=True)
class MocEulerAmbientShockFieldResult:
  """An exact-Euler ambient-coupled one-layer field with an open stop."""

  status: MocEulerAmbientShockFieldStatus
  shock_boundary: MocEulerShockBoundaryCurveResult | None
  ambient_march: MocEulerAmbientBoundaryMarchResult | None
  field: MocEulerCompanionFieldResult | None
  ambient_pressure_Pa: float | None
  entropy_residuals: tuple[float, ...]
  maximum_entropy_residual: float | None
  ambient_boundary_verified: bool
  entropy_lineage_verified: bool
  local_field_verified: bool
  attachment_wedge: MocEulerAmbientAttachmentWedgeResult | None = None
  ambient_companion_boundary: MocEulerAmbientCompanionBoundaryResult | None = None
  physical_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocEulerAmbientShockFieldStatus):
      raise TypeError('status must be a MocEulerAmbientShockFieldStatus')
    ####
    if self.shock_boundary is not None and not isinstance(
      self.shock_boundary,
      MocEulerShockBoundaryCurveResult,
    ):
      raise TypeError(
        'shock_boundary must be a MocEulerShockBoundaryCurveResult or None'
      )
    ####
    if self.ambient_march is not None and not isinstance(
      self.ambient_march,
      MocEulerAmbientBoundaryMarchResult,
    ):
      raise TypeError(
        'ambient_march must be a MocEulerAmbientBoundaryMarchResult or None'
      )
    ####
    if self.attachment_wedge is not None and not isinstance(
      self.attachment_wedge,
      MocEulerAmbientAttachmentWedgeResult,
    ):
      raise TypeError(
        'attachment_wedge must be a MocEulerAmbientAttachmentWedgeResult or None'
      )
    ####
    if self.ambient_companion_boundary is not None and not isinstance(
      self.ambient_companion_boundary,
      MocEulerAmbientCompanionBoundaryResult,
    ):
      raise TypeError(
        'ambient_companion_boundary must be a '
        'MocEulerAmbientCompanionBoundaryResult or None'
      )
    ####
    if self.ambient_march is not None and self.ambient_companion_boundary is not None:
      raise ValueError(
        'ambient_march and ambient_companion_boundary are mutually exclusive '
        'ambient-boundary sources'
      )
    ####
    if self.field is not None and not isinstance(
      self.field,
      MocEulerCompanionFieldResult,
    ):
      raise TypeError(
        'field must be a MocEulerCompanionFieldResult or None'
      )
    ####
    if self.ambient_pressure_Pa is not None:
      ambient_pressure = float(self.ambient_pressure_Pa)
      if not isfinite(ambient_pressure) or ambient_pressure <= 0.0:
        raise ValueError(
          'ambient_pressure_Pa must be finite and positive when supplied'
        )
      ####
      object.__setattr__(self, 'ambient_pressure_Pa', ambient_pressure)
    ####
    residuals = tuple(float(value) for value in self.entropy_residuals)
    if any(not isfinite(value) or value < 0.0 for value in residuals):
      raise ValueError('entropy_residuals must contain finite nonnegative values')
    ####
    object.__setattr__(self, 'entropy_residuals', residuals)
    if self.maximum_entropy_residual is not None:
      maximum = float(self.maximum_entropy_residual)
      if not isfinite(maximum) or maximum < 0.0:
        raise ValueError(
          'maximum_entropy_residual must be finite and nonnegative when supplied'
        )
      ####
      object.__setattr__(self, 'maximum_entropy_residual', maximum)
    ####
    for name in (
      'ambient_boundary_verified',
      'entropy_lineage_verified',
      'local_field_verified',
      'physical_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status is MocEulerAmbientShockFieldStatus.CONVERGED_OPEN
      and self.ambient_boundary_verified
      and self.entropy_lineage_verified
      and self.local_field_verified
      and self.field is not None
      and self.field.converged
    )
  ####

  @property
  def state_sampling_available(self) -> bool:
    return bool(self.converged and self.field is not None and self.field.state_sampling_available)
  ####

  @property
  def downstream_handoff(self) -> tuple[MocChainBoundarySample, ...]:
    if not self.state_sampling_available or self.field is None:
      return ()
    ####
    return self.field.downstream_handoff
  ####

  def as_chain_termination_decision(self) -> MocChainTerminationDecision:
    if self.converged:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE,
        message=(
          'exact-Euler ambient shock field is locally coupled but its '
          'reflected/free-boundary closure is open'
        ),
        diagnostics={
          'ambient_shock_field_status': self.status.value,
          'chain_promotion_blocked': True,
          'physical_closure_verified': False,
        },
      )
    ####
    if self.status is MocEulerAmbientShockFieldStatus.INVALID_INPUT:
      reason = MocChainTerminationReason.INVALID_INPUT
    elif self.status in (
      MocEulerAmbientShockFieldStatus.ENTROPY_TRANSPORT_REQUIRED,
      MocEulerAmbientShockFieldStatus.ATTACHMENT_GEOMETRY_FAILURE,
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
        'ambient_shock_field_status': self.status.value,
        'chain_promotion_blocked': True,
        'physical_closure_verified': False,
      },
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'state_sampling_available': self.state_sampling_available,
      'ambient_pressure_Pa': self.ambient_pressure_Pa,
      'shock_boundary': (
        None
        if self.shock_boundary is None
        else self.shock_boundary.as_report()
      ),
      'ambient_march': (
        None if self.ambient_march is None else self.ambient_march.as_report()
      ),
      'ambient_companion_boundary': (
        None
        if self.ambient_companion_boundary is None
        else self.ambient_companion_boundary.as_report()
      ),
      'attachment_wedge': (
        None
        if self.attachment_wedge is None
        else self.attachment_wedge.as_report()
      ),
      'field': None if self.field is None else self.field.as_report(),
      'entropy_residuals': list(self.entropy_residuals),
      'maximum_entropy_residual': self.maximum_entropy_residual,
      'ambient_boundary_verified': self.ambient_boundary_verified,
      'entropy_lineage_verified': self.entropy_lineage_verified,
      'local_field_verified': self.local_field_verified,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'downstream_handoff_sample_count': len(self.downstream_handoff),
      'chain_termination_decision': (
        self.as_chain_termination_decision().as_report()
      ),
      'message': self.message,
    }
  ####
####


def _field_failure(
  status: MocEulerAmbientShockFieldStatus,
  shock_boundary: MocEulerShockBoundaryCurveResult | None,
  ambient_march: MocEulerAmbientBoundaryMarchResult | None,
  ambient_pressure_Pa: float | None,
  *,
  entropy_residuals: Sequence[float] = (),
  attachment_wedge: MocEulerAmbientAttachmentWedgeResult | None = None,
  ambient_companion_boundary: MocEulerAmbientCompanionBoundaryResult | None = None,
  ambient_boundary_verified: bool = False,
  entropy_lineage_verified: bool = False,
  local_field_verified: bool = False,
  message: str,
) -> MocEulerAmbientShockFieldResult:
  residuals = tuple(float(value) for value in entropy_residuals)
  return MocEulerAmbientShockFieldResult(
    status=status,
    shock_boundary=shock_boundary,
    ambient_march=ambient_march,
    attachment_wedge=attachment_wedge,
    ambient_companion_boundary=ambient_companion_boundary,
    field=None,
    ambient_pressure_Pa=ambient_pressure_Pa,
    entropy_residuals=residuals,
    maximum_entropy_residual=max(residuals, default=None),
    ambient_boundary_verified=ambient_boundary_verified,
    entropy_lineage_verified=entropy_lineage_verified,
    local_field_verified=local_field_verified,
    message=message,
  )
####


def assemble_euler_ambient_shock_field_from_companion(
  shock_boundary: MocEulerShockBoundaryCurveResult,
  companion_boundary: MocEulerAmbientCompanionBoundaryResult,
  *,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  pressure_tolerance: float = 1.0e-8,
) -> MocEulerAmbientShockFieldResult:
  """Assemble an exact open field from an explicit companion trace.

  This is the separated-boundary counterpart to
  :func:`assemble_euler_ambient_shock_field`.  The companion trace is a
  solver-owned research reference with a nonzero shock clearance; it is not
  the shared shock/ambient attachment returned by the physical ambient
  marcher.  Keeping the two entry points separate prevents a prescribed
  companion boundary from being mistaken for a solved first-cell free
  boundary while still allowing planner and handoff code to exercise a
  state-carrying exact open field.

  The narrow strip remains limited to a constant downstream total-pressure
  lineage.  Variable shock entropy is retained as an explicit
  ``ENTROPY_TRANSPORT_REQUIRED`` stop rather than being silently assigned to
  the companion cells.
  """

  if not isinstance(shock_boundary, MocEulerShockBoundaryCurveResult):
    return _field_failure(
      MocEulerAmbientShockFieldStatus.INVALID_INPUT,
      None,
      None,
      None,
      message='shock_boundary must be a MocEulerShockBoundaryCurveResult',
    )
  ####
  if not isinstance(companion_boundary, MocEulerAmbientCompanionBoundaryResult):
    return _field_failure(
      MocEulerAmbientShockFieldStatus.INVALID_INPUT,
      shock_boundary,
      None,
      None,
      message=(
        'companion_boundary must be a '
        'MocEulerAmbientCompanionBoundaryResult'
      ),
    )
  ####
  try:
    position_tolerance = float(position_tolerance_m)
    invariant_tolerance_value = float(invariant_tolerance)
    pressure_tolerance_value = float(pressure_tolerance)
  except (TypeError, ValueError):
    return _field_failure(
      MocEulerAmbientShockFieldStatus.INVALID_INPUT,
      shock_boundary,
      None,
      companion_boundary.ambient_pressure_Pa,
      ambient_companion_boundary=companion_boundary,
      message='explicit companion field tolerances must be numeric',
    )
  ####
  for name, value in (
    ('position_tolerance_m', position_tolerance),
    ('invariant_tolerance', invariant_tolerance_value),
    ('pressure_tolerance', pressure_tolerance_value),
  ):
    if not isfinite(value) or value <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
    ####
  ####

  ambient_pressure = companion_boundary.ambient_pressure_Pa
  if ambient_pressure is None:
    return _field_failure(
      MocEulerAmbientShockFieldStatus.AMBIENT_BOUNDARY_FAILURE,
      shock_boundary,
      None,
      None,
      ambient_companion_boundary=companion_boundary,
      message='explicit companion boundary does not retain ambient pressure',
    )
  ####
  if not shock_boundary.converged or not shock_boundary.local_euler_verified:
    return _field_failure(
      MocEulerAmbientShockFieldStatus.SHOCK_BOUNDARY_REQUIRED,
      shock_boundary,
      None,
      ambient_pressure,
      ambient_companion_boundary=companion_boundary,
      message=(
        'explicit companion field requires a locally Euler-verified shock '
        f'curve: {shock_boundary.message}'
      ),
    )
  ####
  if companion_boundary.shock_boundary is not shock_boundary:
    return _field_failure(
      MocEulerAmbientShockFieldStatus.AMBIENT_BOUNDARY_FAILURE,
      shock_boundary,
      None,
      ambient_pressure,
      ambient_companion_boundary=companion_boundary,
      message=(
        'explicit companion boundary must be derived from the exact shock '
        'boundary object supplied to this field assembly'
      ),
    )
  ####
  samples = tuple(companion_boundary.samples)
  shock_count = len(shock_boundary.shock_points_m)
  if (
    not companion_boundary.converged
    or not companion_boundary.state_sampling_available
    or len(samples) != shock_count
    or shock_count < 2
  ):
    return _field_failure(
      MocEulerAmbientShockFieldStatus.AMBIENT_BOUNDARY_FAILURE,
      shock_boundary,
      None,
      ambient_pressure,
      ambient_companion_boundary=companion_boundary,
      message=(
        'explicit companion boundary must be converged, state-carrying, and '
        'aligned with every shock sample'
      ),
    )
  ####
  if any(
    abs(sample.state.gamma - shock_boundary.downstream_states[0].gamma)
    > invariant_tolerance_value
    for sample in samples
  ):
    return _field_failure(
      MocEulerAmbientShockFieldStatus.AMBIENT_BOUNDARY_FAILURE,
      shock_boundary,
      None,
      ambient_pressure,
      ambient_companion_boundary=companion_boundary,
      message='explicit companion boundary uses a different gamma',
    )
  ####
  if any(
    sample.total_pressure_Pa <= 0.0
    or not isfinite(sample.total_pressure_Pa)
    or abs(
      sample.total_pressure_Pa
      - shock_boundary.downstream_total_pressure_Pa[index]
    )
    > pressure_tolerance_value
    * max(1.0, abs(shock_boundary.downstream_total_pressure_Pa[index]))
    for index, sample in enumerate(samples)
  ):
    return _field_failure(
      MocEulerAmbientShockFieldStatus.AMBIENT_BOUNDARY_FAILURE,
      shock_boundary,
      None,
      ambient_pressure,
      ambient_companion_boundary=companion_boundary,
      message=(
        'explicit companion boundary total pressure does not match the '
        'shock downstream pressure lineage'
      ),
    )
  ####

  shock_pressures = tuple(shock_boundary.downstream_total_pressure_Pa)
  baseline_pressure = shock_pressures[0]
  entropy_residuals = tuple(
    abs(pressure - baseline_pressure) / baseline_pressure
    for pressure in shock_pressures
  )
  maximum_entropy_residual = max(entropy_residuals, default=0.0)
  if maximum_entropy_residual > pressure_tolerance_value:
    return _field_failure(
      MocEulerAmbientShockFieldStatus.ENTROPY_TRANSPORT_REQUIRED,
      shock_boundary,
      None,
      ambient_pressure,
      ambient_companion_boundary=companion_boundary,
      entropy_residuals=entropy_residuals,
      ambient_boundary_verified=True,
      entropy_lineage_verified=False,
      message=(
        'explicit companion field received variable downstream total '
        'pressure; entropy transport is required before this strip can be '
        f'assembled (maximum relative residual={maximum_entropy_residual})'
      ),
    )
  ####

  field = assemble_euler_consistent_companion_characteristic_strip(
    shock_boundary,
    samples,
    position_tolerance_m=position_tolerance,
    invariant_tolerance=invariant_tolerance_value,
    pressure_tolerance=pressure_tolerance_value,
  )
  if not field.converged:
    return _field_failure(
      MocEulerAmbientShockFieldStatus.FIELD_FAILURE,
      shock_boundary,
      None,
      ambient_pressure,
      ambient_companion_boundary=companion_boundary,
      entropy_residuals=entropy_residuals,
      ambient_boundary_verified=True,
      entropy_lineage_verified=True,
      local_field_verified=False,
      message=f'explicit companion strip assembly failed: {field.message}',
    )
  ####
  return MocEulerAmbientShockFieldResult(
    status=MocEulerAmbientShockFieldStatus.CONVERGED_OPEN,
    shock_boundary=shock_boundary,
    ambient_march=None,
    ambient_companion_boundary=companion_boundary,
    field=field,
    ambient_pressure_Pa=ambient_pressure,
    entropy_residuals=entropy_residuals,
    maximum_entropy_residual=maximum_entropy_residual,
    ambient_boundary_verified=True,
    entropy_lineage_verified=True,
    local_field_verified=bool(
      field.shock_boundary_local_euler_verified
      and field.companion_boundary_contract_verified
      and field.pressure_lineage_verified
      and field.state_sampling_available
    ),
    message=(
      'exact Euler shock and an explicit separated companion boundary formed '
      'a state-carrying open characteristic strip; shared-attachment '
      'remeshing, reflected closure, and continued-cell promotion remain '
      'pending'
    ),
  )
####


def assemble_euler_ambient_shock_field(
  shock_boundary: MocEulerShockBoundaryCurveResult,
  ambient_pressure_Pa: float,
  *,
  target_centerline_y_m: float = 0.0,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  pressure_tolerance: float = 1.0e-8,
  maximum_iterations: int = 16,
) -> MocEulerAmbientShockFieldResult:
  """Couple an exact shock curve to a pressure-matched open Euler strip.

  The one-layer strip is only accepted when the shock carries one constant
  total-pressure lineage.  A variable post-shock total pressure requires an
  entropy-aware characteristic field, so this function returns a typed
  ``ENTROPY_TRANSPORT_REQUIRED`` result instead of using the constant-
  entropy assembler outside its domain.
  """

  if not isinstance(shock_boundary, MocEulerShockBoundaryCurveResult):
    return _field_failure(
      MocEulerAmbientShockFieldStatus.INVALID_INPUT,
      None,
      None,
      None,
      message='shock_boundary must be a MocEulerShockBoundaryCurveResult',
    )
  ####
  try:
    ambient_pressure = float(ambient_pressure_Pa)
    pressure_tolerance_value = float(pressure_tolerance)
  except (TypeError, ValueError):
    return _field_failure(
      MocEulerAmbientShockFieldStatus.INVALID_INPUT,
      shock_boundary,
      None,
      None,
      message='ambient pressure and pressure tolerance must be numeric',
    )
  ####
  if not isfinite(ambient_pressure) or ambient_pressure <= 0.0:
    raise ValueError('ambient_pressure_Pa must be finite and positive')
  ####
  if not isfinite(pressure_tolerance_value) or pressure_tolerance_value <= 0.0:
    raise ValueError('pressure_tolerance must be finite and positive')
  ####
  if not shock_boundary.converged or not shock_boundary.local_euler_verified:
    return _field_failure(
      MocEulerAmbientShockFieldStatus.SHOCK_BOUNDARY_REQUIRED,
      shock_boundary,
      None,
      ambient_pressure,
      message=(
        'exact Euler ambient shock field requires a locally Euler-verified '
        f'shock curve: {shock_boundary.message}'
      ),
    )
  ####
  march = march_euler_ambient_boundary(
    shock_boundary,
    ambient_pressure,
    target_centerline_y_m=target_centerline_y_m,
    position_tolerance_m=position_tolerance_m,
    invariant_tolerance=invariant_tolerance,
    pressure_tolerance=pressure_tolerance_value,
    maximum_iterations=maximum_iterations,
  )
  if not march.converged:
    return _field_failure(
      MocEulerAmbientShockFieldStatus.AMBIENT_BOUNDARY_FAILURE,
      shock_boundary,
      march,
      ambient_pressure,
      ambient_boundary_verified=False,
      message=f'exact Euler ambient boundary did not converge: {march.message}',
    )
  ####
  shock_pressures = tuple(shock_boundary.downstream_total_pressure_Pa)
  baseline_pressure = shock_pressures[0]
  entropy_residuals = tuple(
    abs(pressure - baseline_pressure) / baseline_pressure
    for pressure in shock_pressures
  )
  maximum_entropy_residual = max(entropy_residuals, default=0.0)
  entropy_verified = maximum_entropy_residual <= pressure_tolerance_value
  if not entropy_verified:
    return _field_failure(
      MocEulerAmbientShockFieldStatus.ENTROPY_TRANSPORT_REQUIRED,
      shock_boundary,
      march,
      ambient_pressure,
      entropy_residuals=entropy_residuals,
      ambient_boundary_verified=True,
      entropy_lineage_verified=False,
      message=(
        'exact Euler shock has variable downstream total pressure; the '
        'constant-entropy one-layer field is blocked until entropy transport '
        f'is implemented (maximum relative residual={maximum_entropy_residual})'
      ),
    )
  ####
  companion = tuple(
    MocChainBoundarySample(
      state=sample.state,
      total_pressure_Pa=sample.total_pressure_Pa,
    )
    for sample in march.boundary_samples
  )
  if len(companion) < 2:
    return _field_failure(
      MocEulerAmbientShockFieldStatus.FIELD_FAILURE,
      shock_boundary,
      march,
      ambient_pressure,
      entropy_residuals=entropy_residuals,
      ambient_boundary_verified=True,
      entropy_lineage_verified=True,
      local_field_verified=False,
      message='exact Euler ambient boundary did not retain two samples',
    )
  ####
  attachment = companion[0].state
  shock_attachment = shock_boundary.shock_points_m[0]
  if (
    abs(attachment.x_m - shock_attachment[0]) <= position_tolerance_m
    and abs(attachment.y_m - shock_attachment[1]) <= position_tolerance_m
  ):
    attachment_wedge = solve_euler_ambient_attachment_wedge(
      shock_boundary,
      march,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
    )
    return _field_failure(
      MocEulerAmbientShockFieldStatus.ATTACHMENT_GEOMETRY_FAILURE,
      shock_boundary,
      march,
      ambient_pressure,
      entropy_residuals=entropy_residuals,
      attachment_wedge=attachment_wedge,
      ambient_boundary_verified=True,
      entropy_lineage_verified=True,
      local_field_verified=False,
      message=(
        'the exact ambient boundary shares the shock attachment point; '
        'the generic paired-node strip requires an attachment-aware first '
        'interior characteristic wedge and cannot promote this field '
        f'({attachment_wedge.status.value})'
      ),
    )
  ####
  field = assemble_euler_consistent_companion_characteristic_strip(
    shock_boundary,
    companion,
    position_tolerance_m=position_tolerance_m,
    invariant_tolerance=invariant_tolerance,
    pressure_tolerance=pressure_tolerance_value,
  )
  if not field.converged:
    status = (
      MocEulerAmbientShockFieldStatus.ATTACHMENT_GEOMETRY_FAILURE
      if 'no forward margin' in field.message
      else MocEulerAmbientShockFieldStatus.FIELD_FAILURE
    )
    return _field_failure(
      status,
      shock_boundary,
      march,
      ambient_pressure,
      entropy_residuals=entropy_residuals,
      ambient_boundary_verified=True,
      entropy_lineage_verified=True,
      local_field_verified=False,
      message=f'exact Euler ambient strip assembly failed: {field.message}',
    )
  ####
  return MocEulerAmbientShockFieldResult(
    status=MocEulerAmbientShockFieldStatus.CONVERGED_OPEN,
    shock_boundary=shock_boundary,
    ambient_march=march,
    field=field,
    ambient_pressure_Pa=ambient_pressure,
    entropy_residuals=entropy_residuals,
    maximum_entropy_residual=maximum_entropy_residual,
    ambient_boundary_verified=True,
    entropy_lineage_verified=True,
    local_field_verified=bool(
      field.shock_boundary_local_euler_verified
      and field.companion_boundary_contract_verified
      and field.pressure_lineage_verified
      and field.state_sampling_available
    ),
    message=(
      'exact Euler shock and solver-owned ambient boundary form a local '
      'open characteristic strip; reflected/free-boundary closure and '
      'continued physical cell promotion remain pending'
    ),
  )
####
