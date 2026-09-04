"""Residual-driven free-boundary correction for the planar MOC first cell.

The geometry-owned first-cell candidate is deliberately useful as a local
research field, but its shock curve is still seeded by caller geometry.  This
module adds the next bounded solve without pretending that a global reflected
Euler/free-boundary problem has been completed: it searches a one-parameter
axial-shape family around the seed and uses the carried ambient-to-centerline
static-pressure mismatch as the residual.

The correction is intentionally narrow.  It preserves the attachment point,
sample ordinates, and centerline target while scaling the downstream shock
abscissae about the attachment.  Every trial is re-solved through the
geometry-owned RH/ambient/characteristic-field candidate, and trials that
leave the bounded upstream source retain a typed failure rather than falling
back to the last valid state.  A scalar root is not a canonical free-boundary
or Euler result; canonical, external-validation, chain-promotion, and
production gates remain false.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Sequence

from exhaust_plume.models.moc.ambient_shock_strip import (
  MocAmbientAxisClosureResult,
  probe_post_shock_ambient_axis_closure,
)
from exhaust_plume.models.moc.chain import (
  MocChainBoundarySample,
  MocChainTerminationDecision,
  MocChainTerminationReason,
)
from exhaust_plume.models.moc.first_cell_candidate import (
  MocFirstCellCandidateResult,
  MocFirstCellCandidateStatus,
  solve_first_cell_geometry_owned_candidate,
)
from exhaust_plume.util.aero.shock_validity import ShockBranch

__all__ = (
  'MocFirstCellFreeBoundaryCorrectionStatus',
  'MocFirstCellFreeBoundaryCorrectionTrial',
  'MocFirstCellFreeBoundaryCorrectionResult',
  'solve_first_cell_free_boundary_correction',
)


class MocFirstCellFreeBoundaryCorrectionStatus(str, Enum):
  """Outcome for the bounded first-cell shock-shape correction."""

  CONVERGED_LOCAL_PHYSICAL_BOUNDARY = (
    'converged-local-physical-boundary-correction'
  )
  CONVERGED_SCALAR_AXIS_PRESSURE = 'converged-scalar-axis-pressure-correction'
  INVALID_INPUT = 'invalid_input'
  UPSTREAM_FIELD_FAILURE = 'upstream_field_failure'
  CANDIDATE_FAILURE = 'candidate_failure'
  NO_BRACKET = 'axis_pressure_no_bracket'
  ITERATION_LIMIT = 'correction_iteration_limit'
####


@dataclass(frozen=True, slots=True)
class MocFirstCellFreeBoundaryCorrectionTrial:
  """One independently auditable axial-shape trial."""

  shape_scale: float
  shock_points_m: tuple[tuple[float, float], ...]
  candidate: MocFirstCellCandidateResult | None
  axis_closure: MocAmbientAxisClosureResult | None
  residual: float | None
  message: str = ''

  def __post_init__(self) -> None:
    scale = float(self.shape_scale)
    if not isfinite(scale) or scale <= 0.0:
      raise ValueError('shape_scale must be finite and positive')
    ####
    object.__setattr__(self, 'shape_scale', scale)
    object.__setattr__(
      self,
      'shock_points_m',
      tuple((float(point[0]), float(point[1])) for point in self.shock_points_m),
    )
    if self.candidate is not None and not isinstance(
      self.candidate,
      MocFirstCellCandidateResult,
    ):
      raise TypeError(
        'candidate must be a MocFirstCellCandidateResult or None'
      )
    ####
    if self.axis_closure is not None and not isinstance(
      self.axis_closure,
      MocAmbientAxisClosureResult,
    ):
      raise TypeError(
        'axis_closure must be a MocAmbientAxisClosureResult or None'
      )
    ####
    if self.residual is not None:
      residual = float(self.residual)
      if not isfinite(residual):
        raise ValueError('residual must be finite when supplied')
      ####
      object.__setattr__(self, 'residual', residual)
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def residual_verified(self) -> bool:
    """Whether this trial produced a usable axis-pressure residual."""

    return bool(
      self.residual is not None
      and self.axis_closure is not None
      and self.axis_closure.axis_candidate_verified
    )
  ####

  @property
  def local_candidate_verified(self) -> bool:
    """Whether the trial retained the locally closed candidate field."""

    return bool(
      self.candidate is not None
      and self.candidate.local_physical_closure_verified
    )
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'shape_scale': self.shape_scale,
      'shock_points_m': self.shock_points_m,
      'candidate_status': (
        None if self.candidate is None else self.candidate.status.value
      ),
      'candidate_local_physical_closure_verified': self.local_candidate_verified,
      'axis_closure': (
        None if self.axis_closure is None else self.axis_closure.as_report()
      ),
      'residual': self.residual,
      'residual_verified': self.residual_verified,
      'message': self.message,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocFirstCellFreeBoundaryCorrectionResult:
  """Result of a bounded residual-driven shock-shape correction.

  ``CONVERGED_SCALAR_AXIS_PRESSURE`` means that the scalar centerline
  pressure residual reached tolerance, but the appended ambient-to-axis
  perimeter still failed its full pressure/tangency gate.  Only
  ``CONVERGED_LOCAL_PHYSICAL_BOUNDARY`` has that local perimeter gate, and
  neither status authorizes canonical or production promotion.
  """

  status: MocFirstCellFreeBoundaryCorrectionStatus
  initial_shock_points_m: tuple[tuple[float, float], ...]
  shape_parameter_name: str
  shape_parameter_bracket: tuple[float, float] | None
  selected_shape_scale: float | None
  initial_candidate: MocFirstCellCandidateResult | None
  selected_candidate: MocFirstCellCandidateResult | None
  selected_axis_closure: MocAmbientAxisClosureResult | None
  trials: tuple[MocFirstCellFreeBoundaryCorrectionTrial, ...]
  source_model: str
  closure_pressure_tolerance: float
  shape_parameter_tolerance: float
  maximum_iterations: int
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocFirstCellFreeBoundaryCorrectionStatus,
    ):
      raise TypeError(
        'status must be a MocFirstCellFreeBoundaryCorrectionStatus'
      )
    ####
    object.__setattr__(
      self,
      'initial_shock_points_m',
      tuple(
        (float(point[0]), float(point[1]))
        for point in self.initial_shock_points_m
      ),
    )
    if not isinstance(self.shape_parameter_name, str) or not self.shape_parameter_name:
      raise ValueError('shape_parameter_name must be a non-empty string')
    ####
    if self.shape_parameter_bracket is not None:
      bracket = tuple(float(value) for value in self.shape_parameter_bracket)
      if (
        len(bracket) != 2
        or not all(isfinite(value) and value > 0.0 for value in bracket)
        or bracket[0] >= bracket[1]
      ):
        raise ValueError(
          'shape_parameter_bracket must contain two ordered positive values'
        )
      ####
      object.__setattr__(self, 'shape_parameter_bracket', bracket)
    ####
    if self.selected_shape_scale is not None:
      selected_scale = float(self.selected_shape_scale)
      if not isfinite(selected_scale) or selected_scale <= 0.0:
        raise ValueError('selected_shape_scale must be finite and positive')
      ####
      object.__setattr__(self, 'selected_shape_scale', selected_scale)
    ####
    for name in (
      'initial_candidate',
      'selected_candidate',
    ):
      candidate = getattr(self, name)
      if candidate is not None and not isinstance(
        candidate,
        MocFirstCellCandidateResult,
      ):
        raise TypeError(
          f'{name} must be a MocFirstCellCandidateResult or None'
        )
      ####
    ####
    if self.selected_axis_closure is not None and not isinstance(
      self.selected_axis_closure,
      MocAmbientAxisClosureResult,
    ):
      raise TypeError(
        'selected_axis_closure must be a MocAmbientAxisClosureResult or None'
      )
    ####
    object.__setattr__(self, 'trials', tuple(self.trials))
    if any(
      not isinstance(trial, MocFirstCellFreeBoundaryCorrectionTrial)
      for trial in self.trials
    ):
      raise TypeError(
        'trials must contain MocFirstCellFreeBoundaryCorrectionTrial values'
      )
    ####
    if not isinstance(self.source_model, str) or not self.source_model:
      raise ValueError('source_model must be a non-empty string')
    ####
    for name in (
      'closure_pressure_tolerance',
      'shape_parameter_tolerance',
    ):
      value = float(getattr(self, name))
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      ####
      object.__setattr__(self, name, value)
    ####
    if (
      isinstance(self.maximum_iterations, bool)
      or not isinstance(self.maximum_iterations, int)
      or self.maximum_iterations < 1
    ):
      raise ValueError('maximum_iterations must be a positive integer')
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status in (
      MocFirstCellFreeBoundaryCorrectionStatus.CONVERGED_LOCAL_PHYSICAL_BOUNDARY,
      MocFirstCellFreeBoundaryCorrectionStatus.CONVERGED_SCALAR_AXIS_PRESSURE,
    )
  ####

  @property
  def scalar_axis_pressure_verified(self) -> bool:
    """Whether the selected trial reaches the scalar axis-pressure root."""

    return bool(
      self.converged
      and self.selected_axis_closure is not None
      and self.selected_axis_closure.axis_candidate_verified
      and self.selected_axis_closure.relative_pressure_residual is not None
      and abs(self.selected_axis_closure.relative_pressure_residual)
      <= self.closure_pressure_tolerance
    )
  ####

  @property
  def local_physical_closure_verified(self) -> bool:
    """Whether the candidate and appended ambient-to-axis perimeter close."""

    return bool(
      self.status
      is MocFirstCellFreeBoundaryCorrectionStatus.CONVERGED_LOCAL_PHYSICAL_BOUNDARY
      and self.scalar_axis_pressure_verified
      and self.selected_candidate is not None
      and self.selected_candidate.local_physical_closure_verified
      and self.selected_axis_closure is not None
      and self.selected_axis_closure.axis_boundary_verified
    )
  ####

  @property
  def physical_closure_verified(self) -> bool:
    """Expose only the local correction gate, never the canonical gate."""

    return self.local_physical_closure_verified
  ####

  @property
  def canonical_free_boundary_verified(self) -> bool:
    """The global reflected free-boundary solve remains pending."""

    return False
  ####

  @property
  def canonical_euler_verified(self) -> bool:
    """This one-parameter correction does not solve the 2-D Euler system."""

    return False
  ####

  @property
  def external_validation_verified(self) -> bool:
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
    """Keep a corrected research result out of continued-cell promotion."""

    if self.converged:
      reason = MocChainTerminationReason.FIDELITY_NOT_ALLOWED
      message = (
        'first-cell shock-shape correction reached its bounded local residual '
        'gate, but canonical reflected free-boundary and Euler evidence is '
        'still required before chain promotion'
      )
    elif self.status is MocFirstCellFreeBoundaryCorrectionStatus.INVALID_INPUT:
      reason = MocChainTerminationReason.INVALID_INPUT
      message = 'first-cell free-boundary correction rejected its inputs'
    elif self.status is MocFirstCellFreeBoundaryCorrectionStatus.UPSTREAM_FIELD_FAILURE:
      reason = MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
      message = (
        'first-cell free-boundary correction left its bounded upstream source; '
        'no state extrapolation or physical endpoint was inferred'
      )
    else:
      reason = MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
      message = (
        'first-cell free-boundary correction did not close its bounded scalar '
        'or local physical residual; continued-cell promotion remains blocked'
      )
    ####
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=reason,
      message=message,
      diagnostics={
        'correction_status': self.status.value,
        'shape_parameter_name': self.shape_parameter_name,
        'selected_shape_scale': self.selected_shape_scale,
        'scalar_axis_pressure_verified': self.scalar_axis_pressure_verified,
        'local_physical_closure_verified': self.local_physical_closure_verified,
        'canonical_free_boundary_verified': self.canonical_free_boundary_verified,
        'canonical_euler_verified': self.canonical_euler_verified,
        'external_validation_verified': self.external_validation_verified,
        'chain_promotion_blocked': self.chain_promotion_blocked,
        'production_claim_allowed': self.production_claim_allowed,
      },
    )
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'physical_closure_verified': self.physical_closure_verified,
      'scalar_axis_pressure_verified': self.scalar_axis_pressure_verified,
      'local_physical_closure_verified': self.local_physical_closure_verified,
      'canonical_free_boundary_verified': self.canonical_free_boundary_verified,
      'canonical_euler_verified': self.canonical_euler_verified,
      'external_validation_verified': self.external_validation_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'shape_parameter_name': self.shape_parameter_name,
      'shape_parameter_bracket': self.shape_parameter_bracket,
      'selected_shape_scale': self.selected_shape_scale,
      'source_model': self.source_model,
      'initial_shock_points_m': self.initial_shock_points_m,
      'initial_candidate': (
        None
        if self.initial_candidate is None
        else self.initial_candidate.as_report()
      ),
      'selected_candidate': (
        None
        if self.selected_candidate is None
        else self.selected_candidate.as_report()
      ),
      'selected_axis_closure': (
        None
        if self.selected_axis_closure is None
        else self.selected_axis_closure.as_report()
      ),
      'trial_count': len(self.trials),
      'trials': tuple(trial.as_report() for trial in self.trials),
      'maximum_iterations': self.maximum_iterations,
      'correction_decision': self.as_chain_termination_decision().as_report(),
      'message': self.message,
    }
  ####
####


def _source_model(upstream_source: object) -> str:
  model = str(getattr(upstream_source, 'model', type(upstream_source).__name__))
  return model or 'unknown'
####


def _normalize_seed_points(
  shock_points_m: Sequence[tuple[float, float]],
  *,
  target_centerline_y_m: float,
  position_tolerance_m: float,
) -> tuple[tuple[float, float], ...] | None:
  try:
    points = tuple(
      (float(point[0]), float(point[1]))
      for point in shock_points_m
    )
  except (IndexError, TypeError, ValueError):
    return None
  ####
  if len(points) < 3 or any(
    not all(isfinite(value) for value in point)
    for point in points
  ):
    return None
  ####
  if any(
    second[0] <= first[0] + position_tolerance_m
    or second[1] > first[1] + position_tolerance_m
    for first, second in zip(points, points[1:])
  ):
    return None
  ####
  if any(point[1] < target_centerline_y_m - position_tolerance_m for point in points):
    return None
  ####
  if abs(points[-1][1] - target_centerline_y_m) > position_tolerance_m:
    return None
  ####
  return (*points[:-1], (points[-1][0], target_centerline_y_m))
####


def _scaled_seed_points(
  points: Sequence[tuple[float, float]],
  shape_scale: float,
) -> tuple[tuple[float, float], ...]:
  anchor_x = points[0][0]
  return tuple(
    (anchor_x + shape_scale * (point[0] - anchor_x), point[1])
    for point in points
  )
####


def _result(
  status: MocFirstCellFreeBoundaryCorrectionStatus,
  *,
  initial_points: Sequence[tuple[float, float]],
  shape_bracket: tuple[float, float] | None,
  selected_scale: float | None,
  initial_candidate: MocFirstCellCandidateResult | None,
  selected_candidate: MocFirstCellCandidateResult | None,
  selected_axis: MocAmbientAxisClosureResult | None,
  trials: Sequence[MocFirstCellFreeBoundaryCorrectionTrial],
  source_model: str,
  closure_pressure_tolerance: float,
  shape_parameter_tolerance: float,
  maximum_iterations: int,
  message: str,
) -> MocFirstCellFreeBoundaryCorrectionResult:
  return MocFirstCellFreeBoundaryCorrectionResult(
    status=status,
    initial_shock_points_m=tuple(initial_points),
    shape_parameter_name='axial-shock-shape-scale-about-attachment',
    shape_parameter_bracket=shape_bracket,
    selected_shape_scale=selected_scale,
    initial_candidate=initial_candidate,
    selected_candidate=selected_candidate,
    selected_axis_closure=selected_axis,
    trials=tuple(trials),
    source_model=source_model,
    closure_pressure_tolerance=closure_pressure_tolerance,
    shape_parameter_tolerance=shape_parameter_tolerance,
    maximum_iterations=maximum_iterations,
    message=message,
  )
####


def solve_first_cell_free_boundary_correction(
  upstream_source: object,
  shock_points_m: Sequence[tuple[float, float]],
  ambient_pressure_Pa: float,
  *,
  target_centerline_y_m: float = 0.0,
  target_centerline_flow_angle_rad: float = 0.0,
  incoming_handoff: Sequence[MocChainBoundarySample] | None = None,
  branch: ShockBranch = ShockBranch.WEAK,
  shape_scale_lower: float = 0.8,
  shape_scale_upper: float = 1.2,
  shape_parameter_tolerance: float = 1.0e-6,
  closure_pressure_tolerance: float = 1.0e-8,
  position_tolerance_m: float = 1.0e-9,
  invariant_tolerance: float = 1.0e-10,
  attachment_pressure_tolerance: float = 1.0e-8,
  pressure_tolerance: float = 1.0e-8,
  tangent_tolerance: float = 1.0e-8,
  shock_angle_tolerance_rad: float = 1.0e-8,
  maximum_iterations: int = 12,
  candidate_maximum_iterations: int = 8,
  allow_zero_strength_attachment: bool = False,
  allow_zero_strength_endpoints: bool = False,
) -> MocFirstCellFreeBoundaryCorrectionResult:
  """Correct a seeded shock shape against the ambient-to-axis pressure residual.

  The one-dimensional family is

  ``x_i(s) = x_attachment + s * (x_i(seed) - x_attachment)``

  with all sample ordinates fixed.  A trial is accepted only when the bounded
  upstream source can be sampled at every point, the geometry-owned candidate
  closes its local characteristic field, and the independently exposed axis
  residual reaches tolerance.  The full ambient-to-axis tangent gate is
  reported separately; a scalar pressure root is never silently promoted.
  """

  source_model = _source_model(upstream_source)
  try:
    ambient_pressure = float(ambient_pressure_Pa)
    target_y = float(target_centerline_y_m)
    target_angle = float(target_centerline_flow_angle_rad)
  except (TypeError, ValueError):
    return _result(
      MocFirstCellFreeBoundaryCorrectionStatus.INVALID_INPUT,
      initial_points=(),
      shape_bracket=None,
      selected_scale=None,
      initial_candidate=None,
      selected_candidate=None,
      selected_axis=None,
      trials=(),
      source_model=source_model,
      closure_pressure_tolerance=1.0e-8,
      shape_parameter_tolerance=1.0e-6,
      maximum_iterations=1,
      message='ambient pressure and centerline targets must be numeric',
    )
  ####
  try:
    position_tolerance = float(position_tolerance_m)
    invariant = float(invariant_tolerance)
    attachment_tolerance = float(attachment_pressure_tolerance)
    pressure = float(pressure_tolerance)
    tangent = float(tangent_tolerance)
    shock_angle_tolerance = float(shock_angle_tolerance_rad)
    lower_scale = float(shape_scale_lower)
    upper_scale = float(shape_scale_upper)
    shape_tolerance = float(shape_parameter_tolerance)
    closure_tolerance = float(closure_pressure_tolerance)
  except (TypeError, ValueError):
    return _result(
      MocFirstCellFreeBoundaryCorrectionStatus.INVALID_INPUT,
      initial_points=(),
      shape_bracket=None,
      selected_scale=None,
      initial_candidate=None,
      selected_candidate=None,
      selected_axis=None,
      trials=(),
      source_model=source_model,
      closure_pressure_tolerance=1.0e-8,
      shape_parameter_tolerance=1.0e-6,
      maximum_iterations=1,
      message='correction tolerances and shape bracket must be numeric',
    )
  ####
  if not isfinite(ambient_pressure) or ambient_pressure <= 0.0:
    return _result(
      MocFirstCellFreeBoundaryCorrectionStatus.INVALID_INPUT,
      initial_points=(),
      shape_bracket=None,
      selected_scale=None,
      initial_candidate=None,
      selected_candidate=None,
      selected_axis=None,
      trials=(),
      source_model=source_model,
      closure_pressure_tolerance=closure_tolerance,
      shape_parameter_tolerance=shape_tolerance,
      maximum_iterations=max(1, maximum_iterations) if isinstance(maximum_iterations, int) else 1,
      message='ambient_pressure_Pa must be finite and positive',
    )
  ####
  if not all(
    isfinite(value) and value > 0.0
    for value in (
      position_tolerance,
      invariant,
      attachment_tolerance,
      pressure,
      tangent,
      shock_angle_tolerance,
      lower_scale,
      upper_scale,
      shape_tolerance,
      closure_tolerance,
    )
  ) or lower_scale >= upper_scale or not (
    lower_scale <= 1.0 <= upper_scale
  ):
    return _result(
      MocFirstCellFreeBoundaryCorrectionStatus.INVALID_INPUT,
      initial_points=(),
      shape_bracket=None,
      selected_scale=None,
      initial_candidate=None,
      selected_candidate=None,
      selected_axis=None,
      trials=(),
      source_model=source_model,
      closure_pressure_tolerance=closure_tolerance,
      shape_parameter_tolerance=shape_tolerance,
      maximum_iterations=max(1, maximum_iterations) if isinstance(maximum_iterations, int) else 1,
      message=(
        'shape scale bounds and correction tolerances must be finite and '
        'positive, with lower <= 1 <= upper'
      ),
    )
  ####
  if not isinstance(branch, ShockBranch):
    return _result(
      MocFirstCellFreeBoundaryCorrectionStatus.INVALID_INPUT,
      initial_points=(),
      shape_bracket=(lower_scale, upper_scale),
      selected_scale=None,
      initial_candidate=None,
      selected_candidate=None,
      selected_axis=None,
      trials=(),
      source_model=source_model,
      closure_pressure_tolerance=closure_tolerance,
      shape_parameter_tolerance=shape_tolerance,
      maximum_iterations=max(1, maximum_iterations) if isinstance(maximum_iterations, int) else 1,
      message='branch must be a ShockBranch',
    )
  ####
  if (
    isinstance(maximum_iterations, bool)
    or not isinstance(maximum_iterations, int)
    or maximum_iterations < 1
    or isinstance(candidate_maximum_iterations, bool)
    or not isinstance(candidate_maximum_iterations, int)
    or candidate_maximum_iterations < 1
  ):
    raise ValueError(
      'maximum_iterations and candidate_maximum_iterations must be positive integers'
    )
  ####
  if not isinstance(allow_zero_strength_attachment, bool):
    raise TypeError('allow_zero_strength_attachment must be a bool')
  ####
  if not isinstance(allow_zero_strength_endpoints, bool):
    raise TypeError('allow_zero_strength_endpoints must be a bool')
  ####
  initial_points = _normalize_seed_points(
    shock_points_m,
    target_centerline_y_m=target_y,
    position_tolerance_m=position_tolerance,
  )
  if initial_points is None:
    return _result(
      MocFirstCellFreeBoundaryCorrectionStatus.INVALID_INPUT,
      initial_points=(),
      shape_bracket=(lower_scale, upper_scale),
      selected_scale=None,
      initial_candidate=None,
      selected_candidate=None,
      selected_axis=None,
      trials=(),
      source_model=source_model,
      closure_pressure_tolerance=closure_tolerance,
      shape_parameter_tolerance=shape_tolerance,
      maximum_iterations=maximum_iterations,
      message=(
        'shock geometry must contain at least three finite downstream points '
        'ending on the target centerline'
      ),
    )
  ####

  trials: list[MocFirstCellFreeBoundaryCorrectionTrial] = []

  def evaluate(scale: float) -> MocFirstCellFreeBoundaryCorrectionTrial:
    points = _scaled_seed_points(initial_points, scale)
    try:
      candidate = solve_first_cell_geometry_owned_candidate(
        upstream_source,
        points,
        ambient_pressure,
        target_centerline_y_m=target_y,
        target_centerline_flow_angle_rad=target_angle,
        incoming_handoff=incoming_handoff,
        branch=branch,
        position_tolerance_m=position_tolerance,
        invariant_tolerance=invariant,
        attachment_pressure_tolerance=attachment_tolerance,
        pressure_tolerance=pressure,
        tangent_tolerance=tangent,
        shock_angle_tolerance_rad=shock_angle_tolerance,
        maximum_iterations=candidate_maximum_iterations,
        allow_zero_strength_attachment=allow_zero_strength_attachment,
        allow_zero_strength_endpoints=allow_zero_strength_endpoints,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      return MocFirstCellFreeBoundaryCorrectionTrial(
        shape_scale=scale,
        shock_points_m=points,
        candidate=None,
        axis_closure=None,
        residual=None,
        message=f'candidate trial raised: {error}',
      )
    ####
    axis: MocAmbientAxisClosureResult | None = None
    residual: float | None = None
    message = candidate.message
    if candidate.ambient_march is not None and candidate.ambient_march.converged:
      try:
        axis = probe_post_shock_ambient_axis_closure(
          candidate.ambient_march,
          ambient_pressure,
          position_tolerance_m=position_tolerance,
          invariant_tolerance=invariant,
          pressure_tolerance=closure_tolerance,
        )
      except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
        message = f'axis-closure trial raised: {error}'
      else:
        if axis.axis_candidate_verified:
          residual = axis.relative_pressure_residual
        ####
        message = axis.message
      ####
    ####
    return MocFirstCellFreeBoundaryCorrectionTrial(
      shape_scale=scale,
      shock_points_m=points,
      candidate=candidate,
      axis_closure=axis,
      residual=residual,
      message=message,
    )
  ####

  lower_trial = evaluate(lower_scale)
  trials.append(lower_trial)
  upper_trial = evaluate(upper_scale)
  trials.append(upper_trial)
  baseline_trial = (
    lower_trial
    if lower_scale == 1.0
    else upper_trial
    if upper_scale == 1.0
    else evaluate(1.0)
  )
  if baseline_trial is not lower_trial and baseline_trial is not upper_trial:
    trials.append(baseline_trial)
  ####

  initial_candidate = baseline_trial.candidate
  usable_endpoints = (
    lower_trial.residual,
    upper_trial.residual,
  )
  if any(value is None for value in usable_endpoints):
    upstream_failure = any(
      trial.candidate is not None
      and trial.candidate.status is MocFirstCellCandidateStatus.UPSTREAM_FIELD_FAILURE
      for trial in (lower_trial, upper_trial)
    )
    return _result(
      MocFirstCellFreeBoundaryCorrectionStatus.UPSTREAM_FIELD_FAILURE
      if upstream_failure
      else MocFirstCellFreeBoundaryCorrectionStatus.CANDIDATE_FAILURE,
      initial_points=initial_points,
      shape_bracket=(lower_scale, upper_scale),
      selected_scale=baseline_trial.shape_scale,
      initial_candidate=initial_candidate,
      selected_candidate=baseline_trial.candidate,
      selected_axis=baseline_trial.axis_closure,
      trials=trials,
      source_model=source_model,
      closure_pressure_tolerance=closure_tolerance,
      shape_parameter_tolerance=shape_tolerance,
      maximum_iterations=maximum_iterations,
      message=(
        'shape correction requires a valid ambient-to-axis residual at both '
        'bracket endpoints; bounded upstream or candidate closure failed'
      ),
    )
  ####
  lower_residual = lower_trial.residual
  upper_residual = upper_trial.residual
  assert lower_residual is not None and upper_residual is not None
  best_trial = min(
    (trial for trial in trials if trial.residual is not None),
    key=lambda trial: abs(trial.residual),
  )

  def converged_result(
    trial: MocFirstCellFreeBoundaryCorrectionTrial,
  ) -> MocFirstCellFreeBoundaryCorrectionResult | None:
    if trial.residual is None or abs(trial.residual) > closure_tolerance:
      return None
    ####
    if not trial.local_candidate_verified:
      return _result(
        MocFirstCellFreeBoundaryCorrectionStatus.CANDIDATE_FAILURE,
        initial_points=initial_points,
        shape_bracket=(lower_scale, upper_scale),
        selected_scale=trial.shape_scale,
        initial_candidate=initial_candidate,
        selected_candidate=trial.candidate,
        selected_axis=trial.axis_closure,
        trials=trials,
        source_model=source_model,
        closure_pressure_tolerance=closure_tolerance,
        shape_parameter_tolerance=shape_tolerance,
        maximum_iterations=maximum_iterations,
        message=(
          'axis-pressure residual reached tolerance, but the same trial did '
          'not retain a locally closed characteristic field'
        ),
      )
    ####
    status = (
      MocFirstCellFreeBoundaryCorrectionStatus.CONVERGED_LOCAL_PHYSICAL_BOUNDARY
      if trial.axis_closure is not None and trial.axis_closure.axis_boundary_verified
      else MocFirstCellFreeBoundaryCorrectionStatus.CONVERGED_SCALAR_AXIS_PRESSURE
    )
    return _result(
      status,
      initial_points=initial_points,
      shape_bracket=(lower_scale, upper_scale),
      selected_scale=trial.shape_scale,
      initial_candidate=initial_candidate,
      selected_candidate=trial.candidate,
      selected_axis=trial.axis_closure,
      trials=trials,
      source_model=source_model,
      closure_pressure_tolerance=closure_tolerance,
      shape_parameter_tolerance=shape_tolerance,
      maximum_iterations=maximum_iterations,
      message=(
        'bounded axial shock-shape correction reached the scalar axis-pressure '
        + (
          'and appended ambient-to-axis physical-boundary gates'
          if status
          is MocFirstCellFreeBoundaryCorrectionStatus.CONVERGED_LOCAL_PHYSICAL_BOUNDARY
          else 'gate; full ambient-to-axis tangency remains open'
        )
      ),
    )
  ####

  for endpoint in (lower_trial, upper_trial):
    result = converged_result(endpoint)
    if result is not None:
      return result
    ####
    if endpoint.residual is not None and abs(endpoint.residual) <= closure_tolerance:
      return result if result is not None else _result(
        MocFirstCellFreeBoundaryCorrectionStatus.CANDIDATE_FAILURE,
        initial_points=initial_points,
        shape_bracket=(lower_scale, upper_scale),
        selected_scale=endpoint.shape_scale,
        initial_candidate=initial_candidate,
        selected_candidate=endpoint.candidate,
        selected_axis=endpoint.axis_closure,
        trials=trials,
        source_model=source_model,
        closure_pressure_tolerance=closure_tolerance,
        shape_parameter_tolerance=shape_tolerance,
        maximum_iterations=maximum_iterations,
        message='endpoint residual reached tolerance without local field closure',
      )
    ####
  ####

  if lower_residual * upper_residual > 0.0:
    return _result(
      MocFirstCellFreeBoundaryCorrectionStatus.NO_BRACKET,
      initial_points=initial_points,
      shape_bracket=(lower_scale, upper_scale),
      selected_scale=best_trial.shape_scale,
      initial_candidate=initial_candidate,
      selected_candidate=best_trial.candidate,
      selected_axis=best_trial.axis_closure,
      trials=trials,
      source_model=source_model,
      closure_pressure_tolerance=closure_tolerance,
      shape_parameter_tolerance=shape_tolerance,
      maximum_iterations=maximum_iterations,
      message=(
        'bounded axial shock-shape family does not straddle the signed '
        f'ambient-to-axis pressure residual: lower={lower_residual}, '
        f'upper={upper_residual}'
      ),
    )
  ####

  current_lower = lower_trial
  current_upper = upper_trial
  for _iteration in range(1, maximum_iterations + 1):
    if abs(current_upper.shape_scale - current_lower.shape_scale) <= shape_tolerance:
      break
    ####
    midpoint_scale = 0.5 * (
      current_lower.shape_scale + current_upper.shape_scale
    )
    midpoint_trial = evaluate(midpoint_scale)
    trials.append(midpoint_trial)
    if midpoint_trial.residual is None:
      upstream_failure = bool(
        midpoint_trial.candidate is not None
        and midpoint_trial.candidate.status
        is MocFirstCellCandidateStatus.UPSTREAM_FIELD_FAILURE
      )
      return _result(
        MocFirstCellFreeBoundaryCorrectionStatus.UPSTREAM_FIELD_FAILURE
        if upstream_failure
        else MocFirstCellFreeBoundaryCorrectionStatus.CANDIDATE_FAILURE,
        initial_points=initial_points,
        shape_bracket=(current_lower.shape_scale, current_upper.shape_scale),
        selected_scale=best_trial.shape_scale,
        initial_candidate=initial_candidate,
        selected_candidate=best_trial.candidate,
        selected_axis=best_trial.axis_closure,
        trials=trials,
        source_model=source_model,
        closure_pressure_tolerance=closure_tolerance,
        shape_parameter_tolerance=shape_tolerance,
        maximum_iterations=maximum_iterations,
        message='shape correction midpoint left the bounded residual domain',
      )
    ####
    if abs(midpoint_trial.residual) < abs(best_trial.residual):
      best_trial = midpoint_trial
    ####
    result = converged_result(midpoint_trial)
    if result is not None:
      return result
    ####
    if abs(midpoint_trial.residual) <= closure_tolerance:
      return _result(
        MocFirstCellFreeBoundaryCorrectionStatus.CANDIDATE_FAILURE,
        initial_points=initial_points,
        shape_bracket=(current_lower.shape_scale, current_upper.shape_scale),
        selected_scale=midpoint_trial.shape_scale,
        initial_candidate=initial_candidate,
        selected_candidate=midpoint_trial.candidate,
        selected_axis=midpoint_trial.axis_closure,
        trials=trials,
        source_model=source_model,
        closure_pressure_tolerance=closure_tolerance,
        shape_parameter_tolerance=shape_tolerance,
        maximum_iterations=maximum_iterations,
        message='midpoint residual reached tolerance without local field closure',
      )
    ####
    if current_lower.residual * midpoint_trial.residual <= 0.0:
      current_upper = midpoint_trial
    else:
      current_lower = midpoint_trial
    ####
  ####

  return _result(
    MocFirstCellFreeBoundaryCorrectionStatus.ITERATION_LIMIT,
    initial_points=initial_points,
    shape_bracket=(current_lower.shape_scale, current_upper.shape_scale),
    selected_scale=best_trial.shape_scale,
    initial_candidate=initial_candidate,
    selected_candidate=best_trial.candidate,
    selected_axis=best_trial.axis_closure,
    trials=trials,
    source_model=source_model,
    closure_pressure_tolerance=closure_tolerance,
    shape_parameter_tolerance=shape_tolerance,
    maximum_iterations=maximum_iterations,
    message=(
      'bounded axial shock-shape correction reached its iteration or '
      f'parameter-width limit; best residual={best_trial.residual}'
    ),
  )
####
