"""Geometry-owned first-cell candidate for the planar MOC research lane.

The existing marched-shock helpers accept a downstream flow-angle callback.
That is useful for fixtures, but it leaves the shock shape and the shock
state law in caller hands.  This module closes the next narrow seam: it takes
an explicitly bounded upstream field and a geometry seed, derives the local
downstream state from the candidate shock tangent, corrects the ambient
attachment and centerline endpoint, and assembles the shock/ambient/axis
characteristic field.

This is a candidate solve, not a production free-boundary solver.  The
geometry seed is still an initial Cauchy guess, and the global reflected
Euler/free-boundary problem and external validation are not solved here.  The
result therefore reports local physical-field closure separately from the
canonical and promotion gates.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import asin, atan, atan2, cos, isfinite, pi, sin, tan
from typing import Callable, Sequence

from exhaust_plume.models.moc.ambient_shock_strip import (
  MocAmbientShockBoundaryMarchResult,
  march_post_shock_ambient_boundary,
)
from exhaust_plume.models.moc.chain import (
  MocChainBoundarySample,
  MocChainTerminationDecision,
  MocChainTerminationReason,
)
from exhaust_plume.models.moc.compression import (
  solve_attached_compression_to_pressure,
  solve_attached_compression_to_turn,
)
from exhaust_plume.models.moc.physical_cell import (
  MocPhysicalPostShockFieldResult,
  assemble_ambient_boundary_post_shock_field_with_centerline_reflection,
)
from exhaust_plume.models.moc.post_shock import (
  MocShockBoundaryFitResult,
  fit_attached_shock_boundary,
)
from exhaust_plume.models.moc.primitives import CharacteristicState
from exhaust_plume.util.aero.shock_validity import ShockBranch

__all__ = (
  'MocFirstCellCandidateStatus',
  'MocFirstCellCandidateResult',
  'solve_first_cell_geometry_owned_candidate',
)


class MocFirstCellCandidateStatus(str, Enum):
  """Structured outcome for the geometry-owned first-cell candidate."""

  CONVERGED_LOCAL_PHYSICAL_FIELD = 'converged-local-physical-first-cell-field'
  INVALID_INPUT = 'invalid_input'
  UPSTREAM_FIELD_FAILURE = 'upstream_field_failure'
  ATTACHMENT_FAILURE = 'ambient_attachment_failure'
  SHOCK_GEOMETRY_FAILURE = 'shock_geometry_failure'
  AMBIENT_BOUNDARY_FAILURE = 'ambient_boundary_failure'
  FIELD_FAILURE = 'physical_field_failure'
  ITERATION_LIMIT = 'candidate_iteration_limit'
####


@dataclass(frozen=True, slots=True)
class MocFirstCellCandidateResult:
  """Auditable result of a local geometry-owned first-cell solve.

  ``local_physical_closure_verified`` means that the bounded upstream source,
  local shock relations, ambient boundary, centerline perimeter, and finite
  characteristic topology all passed their local gates.  It does not mean the
  candidate is the canonical reflected free boundary: the initial geometry
  seed and the global upstream remesh are still external to this solve.
  """

  status: MocFirstCellCandidateStatus
  shock_fit: MocShockBoundaryFitResult | None
  ambient_march: MocAmbientShockBoundaryMarchResult | None
  field: MocPhysicalPostShockFieldResult | None
  initial_shock_points_m: tuple[tuple[float, float], ...]
  shock_points_m: tuple[tuple[float, float], ...]
  upstream_states: tuple[CharacteristicState, ...]
  upstream_pressure_Pa: tuple[float, ...]
  downstream_flow_angles_rad: tuple[float, ...]
  shock_angle_residuals_rad: tuple[float, ...]
  start_attachment_pressure_residual: float | None
  centerline_flow_angle_residual_rad: float | None
  centerline_geometry_residual_m: float | None
  maximum_ambient_pressure_residual: float | None
  maximum_ambient_tangent_residual: float | None
  iteration_count: int
  iteration_history: tuple[dict[str, object], ...]
  upstream_source_model: str
  shock_angle_tolerance_rad: float
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocFirstCellCandidateStatus):
      raise TypeError('status must be a MocFirstCellCandidateStatus')
    ####
    if (
      isinstance(self.iteration_count, bool)
      or not isinstance(self.iteration_count, int)
      or self.iteration_count < 0
    ):
      raise ValueError('iteration_count must be a nonnegative integer')
    ####
    if not isfinite(float(self.shock_angle_tolerance_rad)) or self.shock_angle_tolerance_rad <= 0.0:
      raise ValueError('shock_angle_tolerance_rad must be finite and positive')
    ####
    if not self.upstream_source_model:
      raise ValueError('upstream_source_model must be non-empty')
    ####
    for name, value in (
      ('start_attachment_pressure_residual', self.start_attachment_pressure_residual),
      ('centerline_flow_angle_residual_rad', self.centerline_flow_angle_residual_rad),
      ('centerline_geometry_residual_m', self.centerline_geometry_residual_m),
      ('maximum_ambient_pressure_residual', self.maximum_ambient_pressure_residual),
      ('maximum_ambient_tangent_residual', self.maximum_ambient_tangent_residual),
    ):
      if value is not None and not isfinite(float(value)):
        raise ValueError(f'{name} must be finite when supplied')
      ####
    ####
    object.__setattr__(
      self,
      'initial_shock_points_m',
      tuple((float(point[0]), float(point[1])) for point in self.initial_shock_points_m),
    )
    object.__setattr__(
      self,
      'shock_points_m',
      tuple((float(point[0]), float(point[1])) for point in self.shock_points_m),
    )
    object.__setattr__(self, 'upstream_states', tuple(self.upstream_states))
    object.__setattr__(
      self,
      'upstream_pressure_Pa',
      tuple(float(value) for value in self.upstream_pressure_Pa),
    )
    object.__setattr__(
      self,
      'downstream_flow_angles_rad',
      tuple(float(value) for value in self.downstream_flow_angles_rad),
    )
    object.__setattr__(
      self,
      'shock_angle_residuals_rad',
      tuple(float(value) for value in self.shock_angle_residuals_rad),
    )
    object.__setattr__(self, 'iteration_history', tuple(self.iteration_history))
  ####

  @property
  def converged(self) -> bool:
    """Whether the local physical-field candidate assembled successfully."""

    return self.status is MocFirstCellCandidateStatus.CONVERGED_LOCAL_PHYSICAL_FIELD
  ####

  @property
  def local_physical_closure_verified(self) -> bool:
    """Whether the retained candidate passed all local closure evidence."""

    return bool(
      self.converged
      and self.shock_fit is not None
      and self.shock_fit.converged
      and self.ambient_march is not None
      and self.ambient_march.converged
      and self.field is not None
      and self.field.physical_closure_verified
      and self.field.state_sampling_available
      and self.field.upstream_shock_coupling_verified
    )
  ####

  @property
  def physical_closure_verified(self) -> bool:
    """Expose local closure while preserving the separate canonical gate."""

    return self.local_physical_closure_verified
  ####

  @property
  def canonical_free_boundary_verified(self) -> bool:
    """The geometry seed/global reflected free boundary remains pending."""

    return False
  ####

  @property
  def canonical_euler_verified(self) -> bool:
    """This candidate does not solve the coupled 2-D Euler residual system."""

    return False
  ####

  @property
  def external_validation_verified(self) -> bool:
    """Indexed external observations have not yet been attached."""

    return False
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    """Keep the candidate out of the continued-chain promotion path."""

    return True
  ####

  @property
  def production_claim_allowed(self) -> bool:
    """The candidate is research evidence only."""

    return False
  ####

  def as_chain_termination_decision(self) -> MocChainTerminationDecision:
    """Return the explicit chain-boundary decision for this candidate.

    A locally closed candidate is not silently converted into a chain cell:
    the seeded global shock topology and canonical free-boundary gates remain
    unresolved.  Failed candidates retain their most specific non-physical
    stop reason so callers cannot infer a physical termination from a local
    solver failure.
    """

    if self.converged:
      reason = MocChainTerminationReason.FIDELITY_NOT_ALLOWED
      message = (
        'geometry-owned first-cell candidate is locally closed but remains a '
        'research seed; canonical reflected free-boundary and Euler gates '
        'must pass before chain promotion'
      )
    elif self.status is MocFirstCellCandidateStatus.INVALID_INPUT:
      reason = MocChainTerminationReason.INVALID_INPUT
      message = 'geometry-owned first-cell candidate rejected its inputs'
    elif self.status is MocFirstCellCandidateStatus.UPSTREAM_FIELD_FAILURE:
      reason = MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
      message = (
        'geometry-owned first-cell candidate left its bounded upstream source; '
        'no extrapolation or chain endpoint was inferred'
      )
    else:
      reason = MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
      message = (
        'geometry-owned first-cell candidate did not produce a complete local '
        'physical field; chain promotion remains blocked'
      )
    ####
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=reason,
      message=message,
      diagnostics={
        'candidate_status': self.status.value,
        'local_physical_closure_verified': self.local_physical_closure_verified,
        'canonical_free_boundary_verified': self.canonical_free_boundary_verified,
        'canonical_euler_verified': self.canonical_euler_verified,
        'external_validation_verified': self.external_validation_verified,
        'chain_promotion_blocked': self.chain_promotion_blocked,
        'production_claim_allowed': self.production_claim_allowed,
      },
    )
  ####

  @property
  def sample_count(self) -> int:
    return len(self.shock_points_m)
  ####

  def as_report(self) -> dict[str, object]:
    """Serialize local residuals and all fidelity gates."""

    return {
      'status': self.status.value,
      'converged': self.converged,
      'local_physical_closure_verified': self.local_physical_closure_verified,
      'physical_closure_verified': self.physical_closure_verified,
      'canonical_free_boundary_verified': self.canonical_free_boundary_verified,
      'canonical_euler_verified': self.canonical_euler_verified,
      'external_validation_verified': self.external_validation_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'chain_promotion_decision': self.as_chain_termination_decision().as_report(),
      'upstream_source_model': self.upstream_source_model,
      'sample_count': self.sample_count,
      'initial_shock_points_m': self.initial_shock_points_m,
      'shock_points_m': self.shock_points_m,
      'upstream_pressure_Pa': self.upstream_pressure_Pa,
      'downstream_flow_angles_rad': self.downstream_flow_angles_rad,
      'shock_angle_residuals_rad': self.shock_angle_residuals_rad,
      'maximum_shock_angle_residual_rad': (
        max((abs(value) for value in self.shock_angle_residuals_rad), default=None)
      ),
      'start_attachment_pressure_residual': self.start_attachment_pressure_residual,
      'centerline_flow_angle_residual_rad': self.centerline_flow_angle_residual_rad,
      'centerline_geometry_residual_m': self.centerline_geometry_residual_m,
      'maximum_ambient_pressure_residual': self.maximum_ambient_pressure_residual,
      'maximum_ambient_tangent_residual': self.maximum_ambient_tangent_residual,
      'iteration_count': self.iteration_count,
      'iteration_history': self.iteration_history,
      'shock_fit': None if self.shock_fit is None else self.shock_fit.converged,
      'ambient_march': (
        None
        if self.ambient_march is None
        else self.ambient_march.as_report()
      ),
      'field': None if self.field is None else self.field.as_report(),
      'message': self.message,
    }
  ####
####


def _failure(
  status: MocFirstCellCandidateStatus,
  *,
  initial_points: Sequence[tuple[float, float]],
  points: Sequence[tuple[float, float]] = (),
  states: Sequence[CharacteristicState] = (),
  pressures: Sequence[float] = (),
  downstream_angles: Sequence[float] = (),
  shock_fit: MocShockBoundaryFitResult | None = None,
  ambient_march: MocAmbientShockBoundaryMarchResult | None = None,
  field: MocPhysicalPostShockFieldResult | None = None,
  shock_residuals: Sequence[float] = (),
  attachment_residual: float | None = None,
  centerline_angle_residual: float | None = None,
  centerline_geometry_residual: float | None = None,
  iteration_count: int = 0,
  iteration_history: Sequence[dict[str, object]] = (),
  source_model: str = 'unknown',
  shock_angle_tolerance_rad: float = 1.0e-8,
  message: str,
) -> MocFirstCellCandidateResult:
  return MocFirstCellCandidateResult(
    status=status,
    shock_fit=shock_fit,
    ambient_march=ambient_march,
    field=field,
    initial_shock_points_m=tuple(initial_points),
    shock_points_m=tuple(points),
    upstream_states=tuple(states),
    upstream_pressure_Pa=tuple(float(value) for value in pressures),
    downstream_flow_angles_rad=tuple(float(value) for value in downstream_angles),
    shock_angle_residuals_rad=tuple(float(value) for value in shock_residuals),
    start_attachment_pressure_residual=attachment_residual,
    centerline_flow_angle_residual_rad=centerline_angle_residual,
    centerline_geometry_residual_m=centerline_geometry_residual,
    maximum_ambient_pressure_residual=(
      None
      if ambient_march is None
      else ambient_march.maximum_absolute_pressure_residual
    ),
    maximum_ambient_tangent_residual=(
      None
      if ambient_march is None
      else ambient_march.ambient_boundary.maximum_absolute_tangent_residual
    ),
    iteration_count=iteration_count,
    iteration_history=tuple(iteration_history),
    upstream_source_model=source_model,
    shock_angle_tolerance_rad=shock_angle_tolerance_rad,
    message=message,
  )
####


def _turn_from_shock_angle(
  beta_rad: float,
  mach: float,
  gamma: float,
) -> float:
  """Return the attached theta-beta-M turn for a supplied shock angle."""

  numerator = 2.0 / tan(beta_rad) * (mach * mach * sin(beta_rad) ** 2 - 1.0)
  denominator = mach * mach * (gamma + cos(2.0 * beta_rad)) + 2.0
  return atan(numerator / denominator)
####


def _finite_points(
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
  if len(points) < 3 or any(not all(isfinite(value) for value in point) for point in points):
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
  return (*points[:-1], (points[-1][0], float(target_centerline_y_m)))
####


def _source_callbacks(
  upstream_source: object,
) -> tuple[
  Callable[[tuple[float, float]], CharacteristicState | None],
  Callable[[tuple[float, float]], float | None],
  str,
] | None:
  state_at = getattr(upstream_source, 'state_at', None)
  pressure_at = getattr(upstream_source, 'static_pressure_at', None)
  if not callable(state_at) or not callable(pressure_at):
    return None
  ####
  model = str(getattr(upstream_source, 'model', type(upstream_source).__name__))
  if not model:
    return None
  ####
  return state_at, pressure_at, model
####


def _sample_upstream(
  state_at: Callable[[tuple[float, float]], CharacteristicState | None],
  pressure_at: Callable[[tuple[float, float]], float | None],
  point: tuple[float, float],
  *,
  index: int,
  position_tolerance_m: float,
) -> tuple[CharacteristicState | None, float | None, str | None]:
  try:
    state = state_at(point)
    pressure = pressure_at(point)
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return None, None, f'upstream source failed at shock sample {index}: {error}'
  ####
  if not isinstance(state, CharacteristicState):
    return None, None, f'upstream source returned no CharacteristicState at sample {index}'
  ####
  if (
    abs(state.x_m - point[0]) > position_tolerance_m
    or abs(state.y_m - point[1]) > position_tolerance_m
  ):
    return None, None, f'upstream state {index} does not lie at the candidate shock point'
  ####
  state = CharacteristicState(
    x_m=point[0],
    y_m=point[1],
    theta_rad=state.theta_rad,
    mach=state.mach,
    gamma=state.gamma,
  )
  if pressure is None or not isfinite(float(pressure)) or float(pressure) <= 0.0:
    return None, None, f'upstream pressure {index} is not finite and positive'
  ####
  return state, float(pressure), None
####


def _shock_tangent(
  points: Sequence[tuple[float, float]],
  index: int,
) -> float:
  if index == 0:
    first, second = points[0], points[1]
  elif index == len(points) - 1:
    first, second = points[-2], points[-1]
  else:
    first, second = points[index - 1], points[index + 1]
  ####
  return atan2(second[1] - first[1], second[0] - first[0])
####


def _adjust_attachment_segment(
  points: list[tuple[float, float]],
  state: CharacteristicState,
  pressure_Pa: float,
  ambient_pressure_Pa: float,
  *,
  branch: ShockBranch,
  allow_zero_strength_attachment: bool,
  attachment_pressure_tolerance: float,
  position_tolerance_m: float,
) -> tuple[bool, float | None, str]:
  """Set the first shock segment to the ambient-matched RH tangent."""

  pressure_difference = (pressure_Pa - ambient_pressure_Pa) / ambient_pressure_Pa
  if abs(pressure_difference) <= attachment_pressure_tolerance:
    if not allow_zero_strength_attachment:
      return False, pressure_difference, (
        'ambient attachment is zero strength; enable '
        'allow_zero_strength_attachment for a Mach-wave start'
      )
    ####
    beta = asin(1.0 / state.mach)
  else:
    if ambient_pressure_Pa < pressure_Pa:
      return False, pressure_difference, (
        'an attached compression cannot reduce the upstream static pressure '
        'to the requested ambient value'
      )
    ####
    try:
      compression = solve_attached_compression_to_pressure(
        upstream_mach=state.mach,
        gamma=state.gamma,
        upstream_pressure_Pa=pressure_Pa,
        target_pressure_Pa=ambient_pressure_Pa,
        branch=branch,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      return False, pressure_difference, f'ambient attachment compression raised: {error}'
    ####
    if not compression.converged or compression.beta_rad is None:
      return False, pressure_difference, (
        f'ambient attachment compression failed: {compression.message}'
      )
    ####
    beta = float(compression.beta_rad)
    # The pressure-inversion primitive has already solved the requested
    # downstream static pressure; retain the normalized residual explicitly
    # rather than recovering it from a total-pressure sample.
    pressure_difference = 0.0
  ####
  tangent = state.theta_rad - beta
  if not isfinite(tangent) or abs(tan(tangent)) <= position_tolerance_m:
    return False, pressure_difference, 'ambient-matched shock tangent is not finite'
  ####
  dy = points[1][1] - points[0][1]
  if dy >= -position_tolerance_m:
    return False, pressure_difference, 'candidate shock must descend on its first segment'
  ####
  next_x = points[0][0] + dy / tan(tangent)
  if not isfinite(next_x) or next_x <= points[0][0] + position_tolerance_m:
    return False, pressure_difference, 'ambient-matched first shock segment has no forward margin'
  ####
  points[1] = (float(next_x), points[1][1])
  return True, pressure_difference, ''
####


def _adjust_centerline_endpoint(
  points: list[tuple[float, float]],
  state: CharacteristicState,
  pressure_Pa: float,
  *,
  target_centerline_y_m: float,
  target_centerline_flow_angle_rad: float,
  branch: ShockBranch,
  allow_zero_strength_endpoints: bool,
  invariant_tolerance: float,
  position_tolerance_m: float,
) -> tuple[bool, float | None, float | None, str]:
  """Correct the final shock point to the centerline RH target angle."""

  target_turn = target_centerline_flow_angle_rad - state.theta_rad
  if target_turn < -invariant_tolerance:
    return False, target_turn, None, 'centerline target requires an expansion at the shock endpoint'
  ####
  if abs(target_turn) <= invariant_tolerance:
    if not allow_zero_strength_endpoints:
      return False, target_turn, None, (
        'centerline endpoint is zero strength; enable '
        'allow_zero_strength_endpoints for a Mach-wave endpoint'
      )
    ####
    beta = asin(1.0 / state.mach)
  else:
    try:
      compression = solve_attached_compression_to_turn(
        upstream_mach=state.mach,
        gamma=state.gamma,
        upstream_pressure_Pa=pressure_Pa,
        target_turn_rad=target_turn,
        branch=branch,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      return False, target_turn, None, f'centerline endpoint compression raised: {error}'
    ####
    if not compression.converged or compression.beta_rad is None:
      return False, target_turn, None, (
        f'centerline endpoint compression failed: {compression.message}'
      )
    ####
    beta = float(compression.beta_rad)
  ####
  tangent = state.theta_rad - beta
  previous = points[-2]
  dy = target_centerline_y_m - previous[1]
  if dy >= -position_tolerance_m:
    return False, target_turn, None, 'candidate shock has no descending final segment'
  ####
  if abs(tan(tangent)) <= position_tolerance_m:
    return False, target_turn, None, 'centerline-matched shock tangent is not finite'
  ####
  end_x = previous[0] + dy / tan(tangent)
  if not isfinite(end_x) or end_x <= previous[0] + position_tolerance_m:
    return False, target_turn, None, 'centerline-matched endpoint has no forward margin'
  ####
  old_x = points[-1][0]
  points[-1] = (float(end_x), float(target_centerline_y_m))
  return True, target_turn, abs(end_x - old_x), ''
####


def _fit_from_geometry(
  points: Sequence[tuple[float, float]],
  states: Sequence[CharacteristicState],
  pressures: Sequence[float],
  *,
  branch: ShockBranch,
  position_tolerance_m: float,
  invariant_tolerance: float,
  shock_angle_tolerance_rad: float,
  allow_zero_strength_attachment: bool,
  allow_zero_strength_endpoints: bool,
) -> tuple[MocShockBoundaryFitResult | None, tuple[float, ...], str | None]:
  """Derive all downstream angles from the candidate geometry and RH."""

  angles: list[float] = []
  for index, state in enumerate(states):
    tangent = _shock_tangent(points, index)
    beta = state.theta_rad - tangent
    mach_angle = asin(1.0 / state.mach)
    if beta < mach_angle - shock_angle_tolerance_rad or beta > pi / 2.0 + shock_angle_tolerance_rad:
      return None, tuple(angles), (
        f'candidate shock sample {index} has an invalid attached angle '
        f'beta={beta}; expected [{mach_angle}, {pi / 2.0}]'
      )
    ####
    beta = min(pi / 2.0, max(mach_angle, beta))
    try:
      turn = _turn_from_shock_angle(beta, state.mach, state.gamma)
    except (ArithmeticError, FloatingPointError, ValueError) as error:
      return None, tuple(angles), f'candidate shock sample {index} turn failed: {error}'
    ####
    zero_strength = (
      (allow_zero_strength_attachment and index == 0)
      or (allow_zero_strength_endpoints and index == len(states) - 1)
    ) and abs(turn) <= invariant_tolerance
    if turn < -invariant_tolerance or (abs(turn) <= invariant_tolerance and not zero_strength):
      return None, tuple(angles), (
        f'candidate shock sample {index} does not carry a positive compression turn'
      )
    ####
    if zero_strength:
      downstream_angle = state.theta_rad
    else:
      try:
        compression = solve_attached_compression_to_turn(
          upstream_mach=state.mach,
          gamma=state.gamma,
          upstream_pressure_Pa=pressures[index],
          target_turn_rad=turn,
          branch=branch,
        )
      except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
        return None, tuple(angles), f'candidate shock sample {index} compression raised: {error}'
      ####
      if not compression.converged or compression.downstream_flow_angle_rad is None:
        return None, tuple(angles), (
          f'candidate shock sample {index} compression failed: {compression.message}'
        )
      ####
      downstream_angle = float(compression.downstream_flow_angle_rad) + state.theta_rad
    ####
    angles.append(float(downstream_angle))
  ####
  fit = fit_attached_shock_boundary(
    states,
    pressures,
    points,
    angles,
    branch=branch,
    position_tolerance_m=position_tolerance_m,
    shock_angle_tolerance_rad=shock_angle_tolerance_rad,
    allow_zero_strength_start=allow_zero_strength_attachment,
    allow_zero_strength_endpoints=allow_zero_strength_endpoints,
  )
  return fit, tuple(angles), None
####


def solve_first_cell_geometry_owned_candidate(
  upstream_source: object,
  shock_points_m: Sequence[tuple[float, float]],
  ambient_pressure_Pa: float,
  *,
  target_centerline_y_m: float = 0.0,
  target_centerline_flow_angle_rad: float = 0.0,
  incoming_handoff: Sequence[MocChainBoundarySample] | None = None,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-9,
  invariant_tolerance: float = 1.0e-10,
  attachment_pressure_tolerance: float = 1.0e-8,
  pressure_tolerance: float = 1.0e-8,
  tangent_tolerance: float = 1.0e-8,
  shock_angle_tolerance_rad: float = 1.0e-8,
  maximum_iterations: int = 8,
  allow_zero_strength_attachment: bool = False,
  allow_zero_strength_endpoints: bool = False,
) -> MocFirstCellCandidateResult:
  """Solve a geometry-owned first-cell physical-field candidate.

  ``upstream_source`` must expose bounded ``state_at`` and
  ``static_pressure_at`` callbacks, such as a converged reflected zone or a
  ``MocBoundedUpstreamFieldSource``.  The shock points are an initial
  geometry seed only.  No downstream flow-angle callback is accepted: local
  downstream angles are derived from the candidate shock tangent and the
  attached theta-beta-Mach / Rankine-Hugoniot relation.

  The first segment is corrected so its local post-shock static pressure
  matches ``ambient_pressure_Pa``.  The final segment is corrected so the
  post-shock flow angle reaches the requested centerline target.  The
  resulting shock fit feeds the solver-owned ambient boundary march and the
  full centerline-reflected physical-field assembler.  Global reflected
  free-boundary closure and external validation remain explicit gates.
  """

  callbacks = _source_callbacks(upstream_source)
  source_model = 'unknown'
  if callbacks is not None:
    _state_at, _pressure_at, source_model = callbacks
  else:
    _state_at = None
    _pressure_at = None
  ####
  try:
    requested_ambient = float(ambient_pressure_Pa)
    target_y = float(target_centerline_y_m)
    target_angle = float(target_centerline_flow_angle_rad)
  except (TypeError, ValueError):
    return _failure(
      MocFirstCellCandidateStatus.INVALID_INPUT,
      initial_points=(),
      source_model=source_model,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      message='ambient pressure and centerline targets must be numeric',
    )
  ####
  initial_points = _finite_points(
    shock_points_m,
    target_centerline_y_m=target_y,
    position_tolerance_m=float(position_tolerance_m),
  )
  if initial_points is None:
    return _failure(
      MocFirstCellCandidateStatus.INVALID_INPUT,
      initial_points=(),
      source_model=source_model,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      message=(
        'shock geometry must contain at least three finite, downstream points '
        'ending on the target centerline'
      ),
    )
  ####
  if callbacks is None:
    return _failure(
      MocFirstCellCandidateStatus.INVALID_INPUT,
      initial_points=initial_points,
      source_model=source_model,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      message='upstream_source must expose callable state_at and static_pressure_at methods',
    )
  ####
  if not isfinite(requested_ambient) or requested_ambient <= 0.0:
    return _failure(
      MocFirstCellCandidateStatus.INVALID_INPUT,
      initial_points=initial_points,
      source_model=source_model,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      message='ambient_pressure_Pa must be finite and positive',
    )
  ####
  if not isfinite(target_angle):
    return _failure(
      MocFirstCellCandidateStatus.INVALID_INPUT,
      initial_points=initial_points,
      source_model=source_model,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      message='target_centerline_flow_angle_rad must be finite',
    )
  ####
  if not isinstance(branch, ShockBranch):
    return _failure(
      MocFirstCellCandidateStatus.INVALID_INPUT,
      initial_points=initial_points,
      source_model=source_model,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      message='branch must be a ShockBranch',
    )
  ####
  for name, value in (
    ('position_tolerance_m', position_tolerance_m),
    ('invariant_tolerance', invariant_tolerance),
    ('attachment_pressure_tolerance', attachment_pressure_tolerance),
    ('pressure_tolerance', pressure_tolerance),
    ('tangent_tolerance', tangent_tolerance),
    ('shock_angle_tolerance_rad', shock_angle_tolerance_rad),
  ):
    if not isfinite(float(value)) or float(value) <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
    ####
  ####
  if (
    isinstance(maximum_iterations, bool)
    or not isinstance(maximum_iterations, int)
    or maximum_iterations < 1
  ):
    raise ValueError('maximum_iterations must be a positive integer')
  ####
  if not isinstance(allow_zero_strength_attachment, bool):
    raise TypeError('allow_zero_strength_attachment must be a bool')
  ####
  if not isinstance(allow_zero_strength_endpoints, bool):
    raise TypeError('allow_zero_strength_endpoints must be a bool')
  ####
  try:
    incoming_samples = () if incoming_handoff is None else tuple(incoming_handoff)
  except TypeError:
    incoming_samples = ()
  ####
  if any(not isinstance(sample, MocChainBoundarySample) for sample in incoming_samples):
    return _failure(
      MocFirstCellCandidateStatus.INVALID_INPUT,
      initial_points=initial_points,
      source_model=source_model,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      message='incoming_handoff must contain MocChainBoundarySample values',
    )
  ####
  if incoming_handoff is not None and len(incoming_samples) < 3:
    return _failure(
      MocFirstCellCandidateStatus.INVALID_INPUT,
      initial_points=initial_points,
      source_model=source_model,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      message='incoming_handoff requires at least three state samples',
    )
  ####

  points = list(initial_points)
  history: list[dict[str, object]] = []
  last_fit: MocShockBoundaryFitResult | None = None
  last_march: MocAmbientShockBoundaryMarchResult | None = None
  last_field: MocPhysicalPostShockFieldResult | None = None
  last_states: tuple[CharacteristicState, ...] = ()
  last_pressures: tuple[float, ...] = ()
  last_angles: tuple[float, ...] = ()
  last_attachment_residual: float | None = None
  last_centerline_residual: float | None = None
  last_centerline_geometry: float | None = None

  for iteration in range(1, maximum_iterations + 1):
    sampled_states: list[CharacteristicState] = []
    sampled_pressures: list[float] = []
    for index, point in enumerate(points):
      state, pressure, error = _sample_upstream(
        _state_at,
        _pressure_at,
        point,
        index=index,
        position_tolerance_m=float(position_tolerance_m),
      )
      if state is None or pressure is None:
        return _failure(
          MocFirstCellCandidateStatus.UPSTREAM_FIELD_FAILURE,
          initial_points=initial_points,
          points=points[: index + 1],
          states=sampled_states,
          pressures=sampled_pressures,
          iteration_count=iteration - 1,
          iteration_history=history,
          source_model=source_model,
          shock_angle_tolerance_rad=float(shock_angle_tolerance_rad),
          message=error or f'upstream source failed at shock sample {index}',
        )
      ####
      sampled_states.append(state)
      sampled_pressures.append(pressure)
    ####
    states = tuple(sampled_states)
    pressures = tuple(sampled_pressures)
    first_ok, attachment_residual, attachment_error = _adjust_attachment_segment(
      points,
      states[0],
      pressures[0],
      requested_ambient,
      branch=branch,
      allow_zero_strength_attachment=allow_zero_strength_attachment,
      attachment_pressure_tolerance=float(attachment_pressure_tolerance),
      position_tolerance_m=float(position_tolerance_m),
    )
    if not first_ok:
      return _failure(
        MocFirstCellCandidateStatus.ATTACHMENT_FAILURE,
        initial_points=initial_points,
        points=points,
        states=states,
        pressures=pressures,
        attachment_residual=attachment_residual,
        iteration_count=iteration - 1,
        iteration_history=history,
        source_model=source_model,
        shock_angle_tolerance_rad=float(shock_angle_tolerance_rad),
        message=attachment_error,
      )
    ####
    # The first point is fixed, but the corrected first segment changes the
    # second sampling point.  Re-sample before deriving any shock states.
    if points[1] != initial_points[1]:
      state, pressure, error = _sample_upstream(
        _state_at,
        _pressure_at,
        points[1],
        index=1,
        position_tolerance_m=float(position_tolerance_m),
      )
      if state is None or pressure is None:
        return _failure(
          MocFirstCellCandidateStatus.UPSTREAM_FIELD_FAILURE,
          initial_points=initial_points,
          points=points[:2],
          states=states[:1],
          pressures=pressures[:1],
          attachment_residual=attachment_residual,
          iteration_count=iteration - 1,
          iteration_history=history,
          source_model=source_model,
          shock_angle_tolerance_rad=float(shock_angle_tolerance_rad),
          message=error or 'upstream source failed after ambient attachment correction',
        )
      ####
      states = (states[0], state, *states[2:])
      pressures = (pressures[0], pressure, *pressures[2:])
    ####

    endpoint_ok, endpoint_residual, endpoint_delta, endpoint_error = _adjust_centerline_endpoint(
      points,
      states[-1],
      pressures[-1],
      target_centerline_y_m=target_y,
      target_centerline_flow_angle_rad=target_angle,
      branch=branch,
      allow_zero_strength_endpoints=allow_zero_strength_endpoints,
      invariant_tolerance=float(invariant_tolerance),
      position_tolerance_m=float(position_tolerance_m),
    )
    if not endpoint_ok:
      return _failure(
        MocFirstCellCandidateStatus.SHOCK_GEOMETRY_FAILURE,
        initial_points=initial_points,
        points=points,
        states=states,
        pressures=pressures,
        attachment_residual=attachment_residual,
        centerline_angle_residual=endpoint_residual,
        iteration_count=iteration - 1,
        iteration_history=history,
        source_model=source_model,
        shock_angle_tolerance_rad=float(shock_angle_tolerance_rad),
        message=endpoint_error,
      )
    ####
    # Correcting the final point changes only its source sample in the usual
    # bounded field, but re-sample it unconditionally so no stale state can
    # enter the fit.
    state, pressure, error = _sample_upstream(
      _state_at,
      _pressure_at,
      points[-1],
      index=len(points) - 1,
      position_tolerance_m=float(position_tolerance_m),
    )
    if state is None or pressure is None:
      return _failure(
        MocFirstCellCandidateStatus.UPSTREAM_FIELD_FAILURE,
        initial_points=initial_points,
        points=points,
        states=states[:-1],
        pressures=pressures[:-1],
        attachment_residual=attachment_residual,
        centerline_angle_residual=endpoint_residual,
        iteration_count=iteration - 1,
        iteration_history=history,
        source_model=source_model,
        shock_angle_tolerance_rad=float(shock_angle_tolerance_rad),
        message=error or 'upstream source failed after centerline endpoint correction',
      )
    ####
    states = (*states[:-1], state)
    pressures = (*pressures[:-1], pressure)

    fit, angles, fit_error = _fit_from_geometry(
      points,
      states,
      pressures,
      branch=branch,
      position_tolerance_m=float(position_tolerance_m),
      invariant_tolerance=float(invariant_tolerance),
      shock_angle_tolerance_rad=float(shock_angle_tolerance_rad),
      allow_zero_strength_attachment=allow_zero_strength_attachment,
      allow_zero_strength_endpoints=allow_zero_strength_endpoints,
    )
    centerline_angle_residual = (
      None
      if not angles
      else float(angles[-1] - target_angle)
    )
    if fit is None or not fit.converged:
      return _failure(
        MocFirstCellCandidateStatus.SHOCK_GEOMETRY_FAILURE,
        initial_points=initial_points,
        points=points,
        states=states,
        pressures=pressures,
        downstream_angles=angles,
        shock_fit=fit,
        shock_residuals=() if fit is None else fit.shock_angle_residuals_rad,
        attachment_residual=attachment_residual,
        centerline_angle_residual=centerline_angle_residual,
        centerline_geometry_residual=endpoint_delta,
        iteration_count=iteration - 1,
        iteration_history=history,
        source_model=source_model,
        shock_angle_tolerance_rad=float(shock_angle_tolerance_rad),
        message=fit_error or (fit.message if fit is not None else 'shock fit failed'),
      )
    ####
    try:
      march = march_post_shock_ambient_boundary(
        fit,
        requested_ambient,
        target_centerline_y_m=target_y,
        position_tolerance_m=float(position_tolerance_m),
        invariant_tolerance=float(invariant_tolerance),
        pressure_tolerance=float(pressure_tolerance),
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      return _failure(
        MocFirstCellCandidateStatus.AMBIENT_BOUNDARY_FAILURE,
        initial_points=initial_points,
        points=points,
        states=states,
        pressures=pressures,
        downstream_angles=angles,
        shock_fit=fit,
        shock_residuals=fit.shock_angle_residuals_rad,
        attachment_residual=attachment_residual,
        centerline_angle_residual=endpoint_residual,
        centerline_geometry_residual=endpoint_delta,
        iteration_count=iteration - 1,
        iteration_history=history,
        source_model=source_model,
        shock_angle_tolerance_rad=float(shock_angle_tolerance_rad),
        message=f'ambient boundary march raised: {error}',
      )
    ####
    field: MocPhysicalPostShockFieldResult | None = None
    field_error: str | None = None
    if march.converged:
      field_handoff = None if incoming_handoff is None else incoming_samples
      try:
        field = assemble_ambient_boundary_post_shock_field_with_centerline_reflection(
          fit,
          march.boundary_samples,
          requested_ambient,
          incoming_handoff=field_handoff,
          position_tolerance_m=float(position_tolerance_m),
          invariant_tolerance=float(invariant_tolerance),
          pressure_tolerance=float(pressure_tolerance),
          tangent_tolerance=float(tangent_tolerance),
          allow_zero_strength_shock_start=allow_zero_strength_attachment,
          allow_zero_strength_endpoints=allow_zero_strength_endpoints,
        )
      except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
        field_error = f'physical field assembly raised: {error}'
      ####
    ####
    history.append({
      'iteration': iteration,
      'shock_points_m': tuple(points),
      'attachment_pressure_residual': attachment_residual,
      'centerline_flow_angle_residual_rad': centerline_angle_residual,
      'centerline_endpoint_delta_m': endpoint_delta,
      'shock_angle_residual_rad': fit.shock_angle_residuals_rad,
      'ambient_march_status': march.status.value,
      'field_status': None if field is None else field.status.value,
      'field_physical_closure_verified': (
        False if field is None else field.physical_closure_verified
      ),
    })
    last_fit = fit
    last_march = march
    last_field = field
    last_states = states
    last_pressures = pressures
    last_angles = angles
    last_attachment_residual = attachment_residual
    last_centerline_residual = centerline_angle_residual
    last_centerline_geometry = endpoint_delta
    if not march.converged:
      return _failure(
        MocFirstCellCandidateStatus.AMBIENT_BOUNDARY_FAILURE,
        initial_points=initial_points,
        points=points,
        states=states,
        pressures=pressures,
        downstream_angles=angles,
        shock_fit=fit,
        ambient_march=march,
        shock_residuals=fit.shock_angle_residuals_rad,
        attachment_residual=attachment_residual,
        centerline_angle_residual=centerline_angle_residual,
        centerline_geometry_residual=endpoint_delta,
        iteration_count=iteration,
        iteration_history=history,
        source_model=source_model,
        shock_angle_tolerance_rad=float(shock_angle_tolerance_rad),
        message=f'ambient boundary did not converge: {march.message}',
      )
    ####
    if field is not None and field.physical_closure_verified:
      return _failure(
        MocFirstCellCandidateStatus.CONVERGED_LOCAL_PHYSICAL_FIELD,
        initial_points=initial_points,
        points=points,
        states=states,
        pressures=pressures,
        downstream_angles=angles,
        shock_fit=fit,
        ambient_march=march,
        field=field,
        shock_residuals=fit.shock_angle_residuals_rad,
        attachment_residual=attachment_residual,
        centerline_angle_residual=centerline_angle_residual,
        centerline_geometry_residual=endpoint_delta,
        iteration_count=iteration,
        iteration_history=history,
        source_model=source_model,
        shock_angle_tolerance_rad=float(shock_angle_tolerance_rad),
        message=(
          'geometry-owned local RH shock fit, ambient-pressure boundary, '
          'centerline reflection, and physical characteristic topology converged; '
          'canonical reflected free-boundary and external validation remain pending'
        ),
      )
    ####
    if iteration == maximum_iterations:
      return _failure(
        MocFirstCellCandidateStatus.ITERATION_LIMIT,
        initial_points=initial_points,
        points=points,
        states=last_states,
        pressures=last_pressures,
        downstream_angles=last_angles,
        shock_fit=last_fit,
        ambient_march=last_march,
        field=last_field,
        shock_residuals=() if last_fit is None else last_fit.shock_angle_residuals_rad,
        attachment_residual=last_attachment_residual,
        centerline_angle_residual=last_centerline_residual,
        centerline_geometry_residual=last_centerline_geometry,
        iteration_count=iteration,
        iteration_history=history,
        source_model=source_model,
        shock_angle_tolerance_rad=float(shock_angle_tolerance_rad),
        message=field_error or (
          'candidate iterations reached their limit before the physical field '
          'closure gate passed'
        ),
      )
    ####
  ####

  return _failure(
    MocFirstCellCandidateStatus.ITERATION_LIMIT,
    initial_points=initial_points,
    points=points,
    states=last_states,
    pressures=last_pressures,
    downstream_angles=last_angles,
    shock_fit=last_fit,
    ambient_march=last_march,
    field=last_field,
    shock_residuals=() if last_fit is None else last_fit.shock_angle_residuals_rad,
    attachment_residual=last_attachment_residual,
    centerline_angle_residual=last_centerline_residual,
    centerline_geometry_residual=last_centerline_geometry,
    iteration_count=maximum_iterations,
    iteration_history=history,
    source_model=source_model,
    shock_angle_tolerance_rad=float(shock_angle_tolerance_rad),
    message='candidate iteration limit reached',
  )
####
