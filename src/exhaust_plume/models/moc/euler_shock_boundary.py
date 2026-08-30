"""Locally Euler-consistent attached-shock boundary primitives.

The older attached-shock reference in :mod:`free_boundary` is retained for
compatibility and research fixtures.  This module is a separate, narrower
physics lane: it uses a downstream turn toward a descending shock, places the
shock segment from its actual tangent, and checks the normalized Euler flux
jump before reporting a locally usable segment.  It deliberately stops before
post-shock characteristic-field closure or continued-cell promotion.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import atan, atan2, cos, hypot, isfinite, pi, sin, sqrt, tan
from typing import Any, Sequence

from exhaust_plume.models.moc.compression import solve_attached_compression_to_turn
from exhaust_plume.models.moc.primitives import CharacteristicState
from exhaust_plume.util.aero.shock_validity import ShockBranch

__all__ = (
  'MocEulerShockBoundaryStatus',
  'MocEulerShockBoundaryOrientation',
  'MocEulerShockBoundaryResult',
  'MocEulerShockBoundaryCurveResult',
  'solve_euler_consistent_attached_shock_segment',
  'fit_euler_consistent_shock_boundary',
  'fit_euler_consistent_shock_boundary_from_geometry',
)


class MocEulerShockBoundaryStatus(str, Enum):
  """Outcome of one locally Euler-consistent attached-shock segment."""

  CONVERGED_LOCAL_SHOCK = 'converged_local_euler_shock'
  INVALID_INPUT = 'invalid_input'
  NONCOMPRESSIVE_TURN = 'noncompressive_turn'
  COMPRESSION_FAILURE = 'compression_failure'
  GEOMETRY_FAILURE = 'geometry_failure'
  EULER_RESIDUAL_FAILURE = 'euler_residual_failure'
  CHARACTERISTIC_ORIENTATION_FAILURE = 'characteristic_orientation_failure'


class MocEulerShockBoundaryOrientation(str, Enum):
  """How a fitted shock tangent sits relative to the downstream Mach cone."""

  MIXED_CHARACTERISTIC_BOUNDARY = 'mixed-characteristic-boundary'
  TWO_FAMILY_FORWARD_CAUCHY = 'two-family-forward-cauchy'
  CHARACTERISTIC_DEGENERATE = 'characteristic-degenerate'


@dataclass(frozen=True, slots=True)
class MocEulerShockBoundaryResult:
  """A positioned shock segment with local Rankine--Hugoniot evidence.

  The downstream state is carried at the segment endpoint.  The three stored
  flux residuals are dimensionless and use ``R*T0 = 1``; this removes the
  unavailable total-temperature scale while preserving the local jump ratios.
  A converged result is still only a boundary primitive: the post-shock MOC
  field, reflected free boundary, and continued-cell handoff remain blocked.
  """

  status: MocEulerShockBoundaryStatus
  upstream_state: CharacteristicState | None = None
  downstream_state: CharacteristicState | None = None
  shock_start_m: tuple[float, float] | None = None
  shock_end_m: tuple[float, float] | None = None
  shock_angle_rad: float | None = None
  beta_rad: float | None = None
  target_downstream_flow_angle_rad: float | None = None
  upstream_pressure_Pa: float | None = None
  downstream_pressure_Pa: float | None = None
  upstream_total_pressure_Pa: float | None = None
  downstream_total_pressure_Pa: float | None = None
  shock_jump_mass_residual: float | None = None
  shock_jump_momentum_residual: float | None = None
  shock_jump_energy_residual: float | None = None
  maximum_shock_jump_residual: float | None = None
  geometry_residual_m: float | None = None
  residual_tolerance: float = 1.0e-8
  canonical_free_boundary_verified: bool = False
  canonical_euler_verified: bool = False
  physical_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocEulerShockBoundaryStatus):
      raise TypeError('status must be a MocEulerShockBoundaryStatus')
    tolerance = float(self.residual_tolerance)
    if not isfinite(tolerance) or tolerance <= 0.0:
      raise ValueError('residual_tolerance must be finite and positive')
    object.__setattr__(self, 'residual_tolerance', tolerance)
    for name in (
      'shock_angle_rad',
      'beta_rad',
      'target_downstream_flow_angle_rad',
      'upstream_pressure_Pa',
      'downstream_pressure_Pa',
      'upstream_total_pressure_Pa',
      'downstream_total_pressure_Pa',
      'shock_jump_mass_residual',
      'shock_jump_momentum_residual',
      'shock_jump_energy_residual',
      'maximum_shock_jump_residual',
      'geometry_residual_m',
    ):
      value = getattr(self, name)
      if value is None:
        continue
      numeric = float(value)
      if not isfinite(numeric):
        raise ValueError(f'{name} must be finite when supplied')
      if 'residual' in name and 'geometry' not in name and numeric < 0.0:
        raise ValueError(f'{name} must be nonnegative when supplied')
      object.__setattr__(self, name, numeric)
    if self.shock_start_m is not None:
      start = (float(self.shock_start_m[0]), float(self.shock_start_m[1]))
      if not all(isfinite(value) for value in start):
        raise ValueError('shock_start_m must contain finite coordinates')
      object.__setattr__(self, 'shock_start_m', start)
    if self.shock_end_m is not None:
      end = (float(self.shock_end_m[0]), float(self.shock_end_m[1]))
      if not all(isfinite(value) for value in end):
        raise ValueError('shock_end_m must contain finite coordinates')
      object.__setattr__(self, 'shock_end_m', end)
    for name in (
      'canonical_free_boundary_verified',
      'canonical_euler_verified',
      'physical_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    object.__setattr__(self, 'message', str(self.message))

  @property
  def converged(self) -> bool:
    """Whether the local shock segment and its Euler jump passed."""

    return self.status is MocEulerShockBoundaryStatus.CONVERGED_LOCAL_SHOCK

  @property
  def local_euler_verified(self) -> bool:
    """Whether every stored shock flux residual is within tolerance."""

    return bool(
      self.converged
      and self.maximum_shock_jump_residual is not None
      and self.maximum_shock_jump_residual <= self.residual_tolerance
    )

  def as_report(self) -> dict[str, Any]:
    def state_report(state: CharacteristicState | None) -> dict[str, float] | None:
      return (
        None
        if state is None
        else {
          'x_m': state.x_m,
          'y_m': state.y_m,
          'theta_rad': state.theta_rad,
          'mach': state.mach,
          'gamma': state.gamma,
        }
      )

    return {
      'status': self.status.value,
      'converged': self.converged,
      'local_euler_verified': self.local_euler_verified,
      'upstream_state': state_report(self.upstream_state),
      'downstream_state': state_report(self.downstream_state),
      'shock_start_m': self.shock_start_m,
      'shock_end_m': self.shock_end_m,
      'shock_angle_rad': self.shock_angle_rad,
      'beta_rad': self.beta_rad,
      'target_downstream_flow_angle_rad': self.target_downstream_flow_angle_rad,
      'upstream_pressure_Pa': self.upstream_pressure_Pa,
      'downstream_pressure_Pa': self.downstream_pressure_Pa,
      'upstream_total_pressure_Pa': self.upstream_total_pressure_Pa,
      'downstream_total_pressure_Pa': self.downstream_total_pressure_Pa,
      'shock_jump_mass_residual': self.shock_jump_mass_residual,
      'shock_jump_momentum_residual': self.shock_jump_momentum_residual,
      'shock_jump_energy_residual': self.shock_jump_energy_residual,
      'maximum_shock_jump_residual': self.maximum_shock_jump_residual,
      'geometry_residual_m': self.geometry_residual_m,
      'residual_tolerance': self.residual_tolerance,
      'canonical_free_boundary_verified': self.canonical_free_boundary_verified,
      'canonical_euler_verified': self.canonical_euler_verified,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'message': self.message,
    }


@dataclass(frozen=True, slots=True)
class MocEulerShockBoundaryCurveResult:
  """A sampled locally conservative shock curve for a future field solve.

  The curve carries downstream states at the shock samples, rather than only
  a geometric envelope.  This is enough to audit local shock jumps and the
  characteristic orientation, but it is not enough to determine both
  characteristic families downstream when the shock lies inside the Mach
  cone.  That missing companion boundary is kept explicit in the result.
  """

  status: MocEulerShockBoundaryStatus
  upstream_states: tuple[CharacteristicState, ...] = ()
  downstream_states: tuple[CharacteristicState, ...] = ()
  shock_points_m: tuple[tuple[float, float], ...] = ()
  shock_angles_rad: tuple[float, ...] = ()
  beta_rad: tuple[float, ...] = ()
  target_downstream_flow_angles_rad: tuple[float, ...] = ()
  upstream_static_pressure_Pa: tuple[float, ...] = ()
  upstream_total_pressure_Pa: tuple[float, ...] = ()
  downstream_static_pressure_Pa: tuple[float, ...] = ()
  downstream_total_pressure_Pa: tuple[float, ...] = ()
  shock_jump_mass_residuals: tuple[float, ...] = ()
  shock_jump_momentum_residuals: tuple[float, ...] = ()
  shock_jump_energy_residuals: tuple[float, ...] = ()
  tangent_residuals_rad: tuple[float, ...] = ()
  orientations: tuple[MocEulerShockBoundaryOrientation, ...] = ()
  orientation: MocEulerShockBoundaryOrientation | None = None
  maximum_shock_jump_residual: float | None = None
  maximum_tangent_residual_rad: float | None = None
  residual_tolerance: float = 1.0e-8
  shock_angle_tolerance_rad: float = 1.0e-8
  canonical_free_boundary_verified: bool = False
  canonical_euler_verified: bool = False
  physical_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocEulerShockBoundaryStatus):
      raise TypeError('status must be a MocEulerShockBoundaryStatus')
    for name in ('residual_tolerance', 'shock_angle_tolerance_rad'):
      value = float(getattr(self, name))
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      object.__setattr__(self, name, value)
    state_sequences = (
      ('upstream_states', self.upstream_states),
      ('downstream_states', self.downstream_states),
    )
    if any(
      not isinstance(state, CharacteristicState)
      for _name, states in state_sequences
      for state in states
    ):
      raise TypeError('shock curve states must contain CharacteristicState values')
    sequence_fields = (
      ('downstream_states', self.downstream_states),
      ('shock_points_m', self.shock_points_m),
      ('shock_angles_rad', self.shock_angles_rad),
      ('beta_rad', self.beta_rad),
      ('target_downstream_flow_angles_rad', self.target_downstream_flow_angles_rad),
      ('upstream_static_pressure_Pa', self.upstream_static_pressure_Pa),
      ('upstream_total_pressure_Pa', self.upstream_total_pressure_Pa),
      ('downstream_static_pressure_Pa', self.downstream_static_pressure_Pa),
      ('downstream_total_pressure_Pa', self.downstream_total_pressure_Pa),
      ('shock_jump_mass_residuals', self.shock_jump_mass_residuals),
      ('shock_jump_momentum_residuals', self.shock_jump_momentum_residuals),
      ('shock_jump_energy_residuals', self.shock_jump_energy_residuals),
      ('tangent_residuals_rad', self.tangent_residuals_rad),
      ('orientations', self.orientations),
    )
    if self.upstream_states:
      expected = len(self.upstream_states)
      if any(len(values) != expected for _name, values in sequence_fields):
        raise ValueError('shock curve evidence sequences must have equal lengths')
    elif any(values for _name, values in sequence_fields):
      raise ValueError('shock curve evidence cannot exist without upstream states')
    for point in self.shock_points_m:
      if len(point) != 2 or not all(isfinite(float(value)) for value in point):
        raise ValueError('shock curve points must contain finite coordinate pairs')
    for name, values in (
      ('upstream_static_pressure_Pa', self.upstream_static_pressure_Pa),
      ('upstream_total_pressure_Pa', self.upstream_total_pressure_Pa),
      ('downstream_static_pressure_Pa', self.downstream_static_pressure_Pa),
      ('downstream_total_pressure_Pa', self.downstream_total_pressure_Pa),
    ):
      if any(not isfinite(float(value)) or value <= 0.0 for value in values):
        raise ValueError(f'{name} must contain finite positive values')
    for name, values in (
      ('shock_jump_mass_residuals', self.shock_jump_mass_residuals),
      ('shock_jump_momentum_residuals', self.shock_jump_momentum_residuals),
      ('shock_jump_energy_residuals', self.shock_jump_energy_residuals),
    ):
      if any(not isfinite(float(value)) or value < 0.0 for value in values):
        raise ValueError(f'{name} must contain finite nonnegative values')
    for name, values in (
      ('shock_angles_rad', self.shock_angles_rad),
      ('beta_rad', self.beta_rad),
      ('target_downstream_flow_angles_rad', self.target_downstream_flow_angles_rad),
      ('tangent_residuals_rad', self.tangent_residuals_rad),
    ):
      if any(not isfinite(float(value)) for value in values):
        raise ValueError(f'{name} must contain finite values')
    if any(not isinstance(value, MocEulerShockBoundaryOrientation) for value in self.orientations):
      raise TypeError('orientations must contain MocEulerShockBoundaryOrientation values')
    if self.orientation is not None and not isinstance(
      self.orientation,
      MocEulerShockBoundaryOrientation,
    ):
      raise TypeError('orientation must be a MocEulerShockBoundaryOrientation')
    for name in ('maximum_shock_jump_residual', 'maximum_tangent_residual_rad'):
      value = getattr(self, name)
      if value is None:
        continue
      numeric = float(value)
      if not isfinite(numeric) or numeric < 0.0:
        raise ValueError(f'{name} must be finite and nonnegative when supplied')
      object.__setattr__(self, name, numeric)
    for name in (
      'canonical_free_boundary_verified',
      'canonical_euler_verified',
      'physical_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    object.__setattr__(self, 'message', str(self.message))

  @property
  def converged(self) -> bool:
    """Whether every sampled shock segment passed its local checks."""

    return self.status is MocEulerShockBoundaryStatus.CONVERGED_LOCAL_SHOCK

  @property
  def local_euler_verified(self) -> bool:
    """Whether every sampled Rankine--Hugoniot residual is within tolerance."""

    return bool(
      self.converged
      and self.maximum_shock_jump_residual is not None
      and self.maximum_shock_jump_residual <= self.residual_tolerance
    )

  @property
  def companion_boundary_required(self) -> bool:
    """Whether shock data alone cannot seed both forward characteristic families."""

    return self.orientation is MocEulerShockBoundaryOrientation.MIXED_CHARACTERISTIC_BOUNDARY

  @property
  def two_family_cauchy_geometry_verified(self) -> bool:
    """Whether the curve is outside the downstream Mach cone."""

    return bool(
      self.converged
      and self.orientation is MocEulerShockBoundaryOrientation.TWO_FAMILY_FORWARD_CAUCHY
    )

  def as_report(self) -> dict[str, Any]:
    def state_report(state: CharacteristicState) -> dict[str, float]:
      return {
        'x_m': state.x_m,
        'y_m': state.y_m,
        'theta_rad': state.theta_rad,
        'mach': state.mach,
        'gamma': state.gamma,
      }

    return {
      'status': self.status.value,
      'converged': self.converged,
      'local_euler_verified': self.local_euler_verified,
      'sample_count': len(self.shock_points_m),
      'upstream_states': [state_report(state) for state in self.upstream_states],
      'downstream_states': [state_report(state) for state in self.downstream_states],
      'shock_points_m': [list(point) for point in self.shock_points_m],
      'shock_angles_rad': list(self.shock_angles_rad),
      'beta_rad': list(self.beta_rad),
      'target_downstream_flow_angles_rad': list(self.target_downstream_flow_angles_rad),
      'upstream_static_pressure_Pa': list(self.upstream_static_pressure_Pa),
      'upstream_total_pressure_Pa': list(self.upstream_total_pressure_Pa),
      'downstream_static_pressure_Pa': list(self.downstream_static_pressure_Pa),
      'downstream_total_pressure_Pa': list(self.downstream_total_pressure_Pa),
      'shock_jump_mass_residuals': list(self.shock_jump_mass_residuals),
      'shock_jump_momentum_residuals': list(self.shock_jump_momentum_residuals),
      'shock_jump_energy_residuals': list(self.shock_jump_energy_residuals),
      'tangent_residuals_rad': list(self.tangent_residuals_rad),
      'orientations': [value.value for value in self.orientations],
      'orientation': None if self.orientation is None else self.orientation.value,
      'companion_boundary_required': self.companion_boundary_required,
      'two_family_cauchy_geometry_verified': self.two_family_cauchy_geometry_verified,
      'maximum_shock_jump_residual': self.maximum_shock_jump_residual,
      'maximum_tangent_residual_rad': self.maximum_tangent_residual_rad,
      'residual_tolerance': self.residual_tolerance,
      'shock_angle_tolerance_rad': self.shock_angle_tolerance_rad,
      'canonical_free_boundary_verified': self.canonical_free_boundary_verified,
      'canonical_euler_verified': self.canonical_euler_verified,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'message': self.message,
    }


@dataclass(frozen=True, slots=True)
class _Primitive:
  density: float
  pressure: float
  velocity_x: float
  velocity_y: float
  total_energy: float


def _primitive(state: CharacteristicState, total_pressure_Pa: float) -> _Primitive:
  temperature_ratio = 1.0 / (
    1.0 + 0.5 * (state.gamma - 1.0) * state.mach * state.mach
  )
  pressure = float(total_pressure_Pa) * temperature_ratio ** (
    state.gamma / (state.gamma - 1.0)
  )
  density = pressure / temperature_ratio
  sound_speed = sqrt(state.gamma * temperature_ratio)
  speed = state.mach * sound_speed
  velocity_x = speed * cos(state.theta_rad)
  velocity_y = speed * sin(state.theta_rad)
  total_energy = pressure / (state.gamma - 1.0) + 0.5 * density * speed * speed
  values = (density, pressure, velocity_x, velocity_y, total_energy)
  if not all(isfinite(value) for value in values):
    raise ValueError('normalized Euler primitive contains a non-finite value')
  return _Primitive(*values)


def _normal_flux(
  primitive: _Primitive,
  normal_x: float,
  normal_y: float,
) -> tuple[float, float, float, float]:
  normal_speed = (
    primitive.velocity_x * normal_x
    + primitive.velocity_y * normal_y
  )
  return (
    primitive.density * normal_speed,
    primitive.density * primitive.velocity_x * normal_speed
    + primitive.pressure * normal_x,
    primitive.density * primitive.velocity_y * normal_speed
    + primitive.pressure * normal_y,
    (primitive.total_energy + primitive.pressure) * normal_speed,
  )


def _relative(actual: float, scale: float) -> float:
  return abs(float(actual)) / max(1.0, abs(float(scale)))


def _jump_residuals(
  upstream_state: CharacteristicState,
  upstream_total_pressure_Pa: float,
  downstream_state: CharacteristicState,
  downstream_total_pressure_Pa: float,
  shock_angle_rad: float,
) -> tuple[float, float, float]:
  normal = (-sin(shock_angle_rad), cos(shock_angle_rad))
  upstream_flux = _normal_flux(
    _primitive(upstream_state, upstream_total_pressure_Pa),
    *normal,
  )
  downstream_flux = _normal_flux(
    _primitive(downstream_state, downstream_total_pressure_Pa),
    *normal,
  )
  return (
    _relative(
      upstream_flux[0] - downstream_flux[0],
      max(abs(upstream_flux[0]), abs(downstream_flux[0])),
    ),
    _relative(
      hypot(
        upstream_flux[1] - downstream_flux[1],
        upstream_flux[2] - downstream_flux[2],
      ),
      max(
        hypot(upstream_flux[1], upstream_flux[2]),
        hypot(downstream_flux[1], downstream_flux[2]),
      ),
    ),
    _relative(
      upstream_flux[3] - downstream_flux[3],
      max(abs(upstream_flux[3]), abs(downstream_flux[3])),
    ),
  )


def _wrapped_angle_difference(first: float, second: float) -> float:
  difference = float(first) - float(second)
  while difference > pi:
    difference -= 2.0 * pi
  while difference < -pi:
    difference += 2.0 * pi
  return difference


def _classify_characteristic_orientation(
  downstream_state: CharacteristicState,
  shock_angle_rad: float,
  *,
  tolerance_rad: float,
) -> MocEulerShockBoundaryOrientation:
  relative_angle = _wrapped_angle_difference(
    shock_angle_rad,
    downstream_state.theta_rad,
  )
  mach_angle = downstream_state.mu_rad
  if abs(abs(relative_angle) - mach_angle) <= tolerance_rad:
    return MocEulerShockBoundaryOrientation.CHARACTERISTIC_DEGENERATE
  if -mach_angle < relative_angle < mach_angle:
    return MocEulerShockBoundaryOrientation.MIXED_CHARACTERISTIC_BOUNDARY
  return MocEulerShockBoundaryOrientation.TWO_FAMILY_FORWARD_CAUCHY


def _failure(
  status: MocEulerShockBoundaryStatus,
  message: str,
  *,
  residual_tolerance: float = 1.0e-8,
  **values: Any,
) -> MocEulerShockBoundaryResult:
  return MocEulerShockBoundaryResult(
    status=status,
    residual_tolerance=residual_tolerance,
    message=message,
    **values,
  )


def _curve_failure(
  status: MocEulerShockBoundaryStatus,
  message: str,
  *,
  residual_tolerance: float,
  shock_angle_tolerance_rad: float,
  **values: Any,
) -> MocEulerShockBoundaryCurveResult:
  return MocEulerShockBoundaryCurveResult(
    status=status,
    residual_tolerance=residual_tolerance,
    shock_angle_tolerance_rad=shock_angle_tolerance_rad,
    message=message,
    **values,
  )


def solve_euler_consistent_attached_shock_segment(
  upstream_state: CharacteristicState,
  upstream_pressure_Pa: float,
  target_downstream_flow_angle_rad: float,
  *,
  target_centerline_y_m: float = 0.0,
  branch: ShockBranch = ShockBranch.WEAK,
  residual_tolerance: float = 1.0e-8,
) -> MocEulerShockBoundaryResult:
  """Solve one descending attached shock segment with a conservative jump.

  The physical orientation used here is explicit: the downstream flow angle
  must be smaller than the upstream angle, so the flow turns toward a shock
  whose tangent is ``theta_upstream - beta`` and which descends to the target
  ordinate.  This is intentionally not a replacement for the compatibility
  reference's opposite-sign turn convention.
  """

  if not isinstance(upstream_state, CharacteristicState):
    return _failure(
      MocEulerShockBoundaryStatus.INVALID_INPUT,
      'upstream_state must be a CharacteristicState',
    )
  try:
    upstream_pressure = float(upstream_pressure_Pa)
    target_angle = float(target_downstream_flow_angle_rad)
    target_y = float(target_centerline_y_m)
    tolerance = float(residual_tolerance)
  except (TypeError, ValueError):
    return _failure(
      MocEulerShockBoundaryStatus.INVALID_INPUT,
      'shock segment pressures, angles, ordinate, and tolerance must be numeric',
    )
  if not isfinite(upstream_pressure) or upstream_pressure <= 0.0:
    return _failure(
      MocEulerShockBoundaryStatus.INVALID_INPUT,
      'upstream_pressure_Pa must be finite and positive',
      residual_tolerance=tolerance,
    )
  if not isfinite(target_angle) or not isfinite(target_y):
    return _failure(
      MocEulerShockBoundaryStatus.INVALID_INPUT,
      'target downstream angle and ordinate must be finite',
      residual_tolerance=tolerance,
    )
  if not isfinite(tolerance) or tolerance <= 0.0:
    raise ValueError('residual_tolerance must be finite and positive')
  if not isinstance(branch, ShockBranch):
    return _failure(
      MocEulerShockBoundaryStatus.INVALID_INPUT,
      'branch must be a ShockBranch',
      residual_tolerance=tolerance,
    )
  start = (upstream_state.x_m, upstream_state.y_m)
  if target_y >= start[1]:
    return _failure(
      MocEulerShockBoundaryStatus.GEOMETRY_FAILURE,
      'target shock ordinate must be below the upstream state',
      residual_tolerance=tolerance,
      upstream_state=upstream_state,
      shock_start_m=start,
      target_downstream_flow_angle_rad=target_angle,
      upstream_pressure_Pa=upstream_pressure,
    )
  turn = upstream_state.theta_rad - target_angle
  if turn <= 0.0:
    return _failure(
      MocEulerShockBoundaryStatus.NONCOMPRESSIVE_TURN,
      'Euler-consistent descending shock requires downstream angle below upstream angle',
      residual_tolerance=tolerance,
      upstream_state=upstream_state,
      shock_start_m=start,
      target_downstream_flow_angle_rad=target_angle,
      upstream_pressure_Pa=upstream_pressure,
    )
  try:
    compression = solve_attached_compression_to_turn(
      upstream_mach=upstream_state.mach,
      gamma=upstream_state.gamma,
      upstream_pressure_Pa=upstream_pressure,
      target_turn_rad=turn,
      branch=branch,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocEulerShockBoundaryStatus.COMPRESSION_FAILURE,
      f'attached Euler-consistent compression raised: {error}',
      residual_tolerance=tolerance,
      upstream_state=upstream_state,
      shock_start_m=start,
      target_downstream_flow_angle_rad=target_angle,
      upstream_pressure_Pa=upstream_pressure,
    )
  if (
    not compression.converged
    or compression.beta_rad is None
    or compression.downstream_mach is None
    or compression.downstream_pressure_Pa is None
    or compression.upstream_total_pressure_Pa is None
    or compression.downstream_total_pressure_Pa is None
  ):
    return _failure(
      MocEulerShockBoundaryStatus.COMPRESSION_FAILURE,
      f'attached Euler-consistent compression did not converge: {compression.message}',
      residual_tolerance=tolerance,
      upstream_state=upstream_state,
      shock_start_m=start,
      beta_rad=compression.beta_rad,
      target_downstream_flow_angle_rad=target_angle,
      upstream_pressure_Pa=upstream_pressure,
      upstream_total_pressure_Pa=compression.upstream_total_pressure_Pa,
      downstream_pressure_Pa=compression.downstream_pressure_Pa,
      downstream_total_pressure_Pa=compression.downstream_total_pressure_Pa,
    )
  beta = float(compression.beta_rad)
  shock_angle = upstream_state.theta_rad - beta
  shock_sine = sin(shock_angle)
  tangent = tan(shock_angle)
  if not isfinite(tangent) or shock_sine >= 0.0:
    return _failure(
      MocEulerShockBoundaryStatus.GEOMETRY_FAILURE,
      'Euler-consistent attached shock does not descend to the target ordinate',
      residual_tolerance=tolerance,
      upstream_state=upstream_state,
      shock_start_m=start,
      shock_angle_rad=shock_angle,
      beta_rad=beta,
      target_downstream_flow_angle_rad=target_angle,
      upstream_pressure_Pa=upstream_pressure,
      upstream_total_pressure_Pa=compression.upstream_total_pressure_Pa,
      downstream_pressure_Pa=compression.downstream_pressure_Pa,
      downstream_total_pressure_Pa=compression.downstream_total_pressure_Pa,
    )
  segment_parameter = (target_y - start[1]) / shock_sine
  end = (
    start[0] + segment_parameter * cos(shock_angle),
    start[1] + segment_parameter * shock_sine,
  )
  if (
    not isfinite(segment_parameter)
    or segment_parameter <= 0.0
    or not all(isfinite(value) for value in end)
    or end[0] <= start[0]
  ):
    return _failure(
      MocEulerShockBoundaryStatus.GEOMETRY_FAILURE,
      'Euler-consistent attached shock has no forward finite endpoint',
      residual_tolerance=tolerance,
      upstream_state=upstream_state,
      shock_start_m=start,
      shock_end_m=end,
      shock_angle_rad=shock_angle,
      beta_rad=beta,
      target_downstream_flow_angle_rad=target_angle,
      upstream_pressure_Pa=upstream_pressure,
      downstream_pressure_Pa=compression.downstream_pressure_Pa,
      upstream_total_pressure_Pa=compression.upstream_total_pressure_Pa,
      downstream_total_pressure_Pa=compression.downstream_total_pressure_Pa,
      geometry_residual_m=end[1] - target_y,
    )
  downstream_state = CharacteristicState(
    x_m=end[0],
    y_m=end[1],
    theta_rad=target_angle,
    mach=float(compression.downstream_mach),
    gamma=upstream_state.gamma,
  )
  try:
    mass, momentum, energy = _jump_residuals(
      upstream_state,
      float(compression.upstream_total_pressure_Pa),
      downstream_state,
      float(compression.downstream_total_pressure_Pa),
      shock_angle,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocEulerShockBoundaryStatus.EULER_RESIDUAL_FAILURE,
      f'Euler shock-jump reconstruction failed: {error}',
      residual_tolerance=tolerance,
      upstream_state=upstream_state,
      downstream_state=downstream_state,
      shock_start_m=start,
      shock_end_m=end,
      shock_angle_rad=shock_angle,
      beta_rad=beta,
      target_downstream_flow_angle_rad=target_angle,
      upstream_pressure_Pa=upstream_pressure,
      downstream_pressure_Pa=compression.downstream_pressure_Pa,
      upstream_total_pressure_Pa=compression.upstream_total_pressure_Pa,
      downstream_total_pressure_Pa=compression.downstream_total_pressure_Pa,
      geometry_residual_m=end[1] - target_y,
    )
  maximum = max(mass, momentum, energy)
  status = (
    MocEulerShockBoundaryStatus.CONVERGED_LOCAL_SHOCK
    if maximum <= tolerance
    else MocEulerShockBoundaryStatus.EULER_RESIDUAL_FAILURE
  )
  return MocEulerShockBoundaryResult(
    status=status,
    upstream_state=upstream_state,
    downstream_state=downstream_state,
    shock_start_m=start,
    shock_end_m=end,
    shock_angle_rad=shock_angle,
    beta_rad=beta,
    target_downstream_flow_angle_rad=target_angle,
    upstream_pressure_Pa=upstream_pressure,
    downstream_pressure_Pa=float(compression.downstream_pressure_Pa),
    upstream_total_pressure_Pa=float(compression.upstream_total_pressure_Pa),
    downstream_total_pressure_Pa=float(compression.downstream_total_pressure_Pa),
    shock_jump_mass_residual=mass,
    shock_jump_momentum_residual=momentum,
    shock_jump_energy_residual=energy,
    maximum_shock_jump_residual=maximum,
    geometry_residual_m=end[1] - target_y,
    residual_tolerance=tolerance,
    message=(
      'locally Euler-consistent attached-shock segment converged; post-shock '
      'MOC field and reflected free-boundary closure remain pending'
      if status is MocEulerShockBoundaryStatus.CONVERGED_LOCAL_SHOCK
      else 'local Euler shock-jump residual exceeded tolerance'
    ),
  )


def fit_euler_consistent_shock_boundary(
  upstream_states: Sequence[CharacteristicState],
  upstream_pressure_Pa: Sequence[float],
  shock_points_m: Sequence[tuple[float, float]],
  downstream_flow_angles_rad: Sequence[float],
  *,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-10,
  shock_angle_tolerance_rad: float = 1.0e-8,
  residual_tolerance: float = 1.0e-8,
) -> MocEulerShockBoundaryCurveResult:
  """Fit a sampled shock curve using the conservative turn orientation.

  The curve is ordered from the outer boundary toward the centerline: ``x``
  must increase and ``y`` must not increase.  Every sample is solved locally
  from the attached oblique-shock relation and checked against the actual
  tangent and normalized Rankine--Hugoniot flux jump.  A converged curve is
  still only a shock Cauchy boundary.  If its tangent lies inside the
  downstream Mach cone, a companion boundary is required before a two-family
  post-shock field can be assembled.
  """

  try:
    samples = tuple(upstream_states)
    pressures = tuple(float(value) for value in upstream_pressure_Pa)
    points = tuple(
      (float(point[0]), float(point[1]))
      for point in shock_points_m
    )
    target_angles = tuple(float(value) for value in downstream_flow_angles_rad)
    position_tolerance = float(position_tolerance_m)
    angle_tolerance = float(shock_angle_tolerance_rad)
    tolerance = float(residual_tolerance)
  except (TypeError, ValueError, IndexError):
    return _curve_failure(
      MocEulerShockBoundaryStatus.INVALID_INPUT,
      'shock curve inputs must contain finite numeric sequences',
      residual_tolerance=1.0e-8,
      shock_angle_tolerance_rad=1.0e-8,
    )
  if not isfinite(position_tolerance) or position_tolerance <= 0.0:
    raise ValueError('position_tolerance_m must be finite and positive')
  if not isfinite(angle_tolerance) or angle_tolerance <= 0.0:
    raise ValueError('shock_angle_tolerance_rad must be finite and positive')
  if not isfinite(tolerance) or tolerance <= 0.0:
    raise ValueError('residual_tolerance must be finite and positive')
  if not isinstance(branch, ShockBranch):
    return _curve_failure(
      MocEulerShockBoundaryStatus.INVALID_INPUT,
      'branch must be a ShockBranch',
      residual_tolerance=tolerance,
      shock_angle_tolerance_rad=angle_tolerance,
    )
  if len(samples) < 2:
    return _curve_failure(
      MocEulerShockBoundaryStatus.INVALID_INPUT,
      'shock curve requires at least two samples',
      residual_tolerance=tolerance,
      shock_angle_tolerance_rad=angle_tolerance,
    )
  if not (
    len(samples)
    == len(pressures)
    == len(points)
    == len(target_angles)
  ):
    return _curve_failure(
      MocEulerShockBoundaryStatus.INVALID_INPUT,
      'shock curve states, pressures, points, and target angles must have equal lengths',
      residual_tolerance=tolerance,
      shock_angle_tolerance_rad=angle_tolerance,
    )
  if not all(isinstance(state, CharacteristicState) for state in samples):
    return _curve_failure(
      MocEulerShockBoundaryStatus.INVALID_INPUT,
      'upstream_states must contain CharacteristicState values',
      residual_tolerance=tolerance,
      shock_angle_tolerance_rad=angle_tolerance,
    )
  gamma = samples[0].gamma
  for index, (state, pressure, point, target_angle) in enumerate(
    zip(samples, pressures, points, target_angles, strict=True)
  ):
    if abs(state.gamma - gamma) > tolerance:
      return _curve_failure(
        MocEulerShockBoundaryStatus.INVALID_INPUT,
        f'shock curve sample {index} uses a different gamma',
        residual_tolerance=tolerance,
        shock_angle_tolerance_rad=angle_tolerance,
      )
    if not all(isfinite(value) for value in point):
      return _curve_failure(
        MocEulerShockBoundaryStatus.INVALID_INPUT,
        f'shock curve sample {index} has non-finite coordinates',
        residual_tolerance=tolerance,
        shock_angle_tolerance_rad=angle_tolerance,
      )
    if (
      abs(state.x_m - point[0]) > position_tolerance
      or abs(state.y_m - point[1]) > position_tolerance
    ):
      return _curve_failure(
        MocEulerShockBoundaryStatus.INVALID_INPUT,
        f'upstream state {index} does not lie on its shock sample',
        residual_tolerance=tolerance,
        shock_angle_tolerance_rad=angle_tolerance,
      )
    if not isfinite(pressure) or pressure <= 0.0:
      return _curve_failure(
        MocEulerShockBoundaryStatus.INVALID_INPUT,
        f'upstream pressure {index} must be finite and positive',
        residual_tolerance=tolerance,
        shock_angle_tolerance_rad=angle_tolerance,
      )
    if not isfinite(target_angle):
      return _curve_failure(
        MocEulerShockBoundaryStatus.INVALID_INPUT,
        f'downstream flow angle {index} must be finite',
        residual_tolerance=tolerance,
        shock_angle_tolerance_rad=angle_tolerance,
      )
    if index:
      previous = points[index - 1]
      if (
        point[0] - previous[0] <= position_tolerance
        or point[1] - previous[1] > position_tolerance
      ):
        return _curve_failure(
          MocEulerShockBoundaryStatus.INVALID_INPUT,
          'shock curve samples must be strictly downstream in x and nonincreasing in y',
          residual_tolerance=tolerance,
          shock_angle_tolerance_rad=angle_tolerance,
        )
  ####

  completed_upstream: list[CharacteristicState] = []
  completed_downstream: list[CharacteristicState] = []
  completed_points: list[tuple[float, float]] = []
  completed_shock_angles: list[float] = []
  completed_beta: list[float] = []
  completed_target_angles: list[float] = []
  completed_upstream_static: list[float] = []
  completed_upstream_total: list[float] = []
  completed_downstream_static: list[float] = []
  completed_downstream_total: list[float] = []
  completed_mass: list[float] = []
  completed_momentum: list[float] = []
  completed_energy: list[float] = []
  completed_tangent: list[float] = []
  completed_orientations: list[MocEulerShockBoundaryOrientation] = []

  def failure(
    status: MocEulerShockBoundaryStatus,
    message: str,
  ) -> MocEulerShockBoundaryCurveResult:
    return _curve_failure(
      status,
      message,
      residual_tolerance=tolerance,
      shock_angle_tolerance_rad=angle_tolerance,
      upstream_states=tuple(completed_upstream),
      downstream_states=tuple(completed_downstream),
      shock_points_m=tuple(completed_points),
      shock_angles_rad=tuple(completed_shock_angles),
      beta_rad=tuple(completed_beta),
      target_downstream_flow_angles_rad=tuple(completed_target_angles),
      upstream_static_pressure_Pa=tuple(completed_upstream_static),
      upstream_total_pressure_Pa=tuple(completed_upstream_total),
      downstream_static_pressure_Pa=tuple(completed_downstream_static),
      downstream_total_pressure_Pa=tuple(completed_downstream_total),
      shock_jump_mass_residuals=tuple(completed_mass),
      shock_jump_momentum_residuals=tuple(completed_momentum),
      shock_jump_energy_residuals=tuple(completed_energy),
      tangent_residuals_rad=tuple(completed_tangent),
      orientations=tuple(completed_orientations),
      orientation=(
        completed_orientations[0]
        if completed_orientations
        and all(value is completed_orientations[0] for value in completed_orientations)
        else None
      ),
      maximum_shock_jump_residual=max(
        (*completed_mass, *completed_momentum, *completed_energy),
        default=None,
      ),
      maximum_tangent_residual_rad=max(
        (abs(value) for value in completed_tangent),
        default=None,
      ),
    )

  for index, (state, pressure, point, target_angle) in enumerate(
    zip(samples, pressures, points, target_angles, strict=True)
  ):
    turn = state.theta_rad - target_angle
    if turn <= 0.0:
      return failure(
        MocEulerShockBoundaryStatus.NONCOMPRESSIVE_TURN,
        f'shock curve sample {index} requires downstream angle below upstream angle',
      )
    try:
      compression = solve_attached_compression_to_turn(
        upstream_mach=state.mach,
        gamma=state.gamma,
        upstream_pressure_Pa=pressure,
        target_turn_rad=turn,
        branch=branch,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      return failure(
        MocEulerShockBoundaryStatus.COMPRESSION_FAILURE,
        f'shock curve sample {index} compression raised: {error}',
      )
    if (
      not compression.converged
      or compression.beta_rad is None
      or compression.downstream_mach is None
      or compression.downstream_pressure_Pa is None
      or compression.upstream_total_pressure_Pa is None
      or compression.downstream_total_pressure_Pa is None
    ):
      return failure(
        MocEulerShockBoundaryStatus.COMPRESSION_FAILURE,
        f'shock curve sample {index} compression did not converge: {compression.message}',
      )
    shock_angle = state.theta_rad - float(compression.beta_rad)
    if index == 0:
      tangent_angle = atan2(
        points[1][1] - point[1],
        points[1][0] - point[0],
      )
    elif index == len(points) - 1:
      tangent_angle = atan2(
        point[1] - points[index - 1][1],
        point[0] - points[index - 1][0],
      )
    else:
      tangent_angle = atan2(
        points[index + 1][1] - points[index - 1][1],
        points[index + 1][0] - points[index - 1][0],
      )
    tangent_residual = _wrapped_angle_difference(tangent_angle, shock_angle)
    downstream_state = CharacteristicState(
      x_m=point[0],
      y_m=point[1],
      theta_rad=target_angle,
      mach=float(compression.downstream_mach),
      gamma=state.gamma,
    )
    try:
      mass, momentum, energy = _jump_residuals(
        state,
        float(compression.upstream_total_pressure_Pa),
        downstream_state,
        float(compression.downstream_total_pressure_Pa),
        shock_angle,
      )
      upstream_static = _primitive(
        state,
        float(compression.upstream_total_pressure_Pa),
      ).pressure
      downstream_static = _primitive(
        downstream_state,
        float(compression.downstream_total_pressure_Pa),
      ).pressure
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      return failure(
        MocEulerShockBoundaryStatus.EULER_RESIDUAL_FAILURE,
        f'shock curve sample {index} Euler reconstruction raised: {error}',
      )
    orientation = _classify_characteristic_orientation(
      downstream_state,
      shock_angle,
      tolerance_rad=angle_tolerance,
    )
    completed_upstream.append(state)
    completed_downstream.append(downstream_state)
    completed_points.append(point)
    completed_shock_angles.append(shock_angle)
    completed_beta.append(float(compression.beta_rad))
    completed_target_angles.append(target_angle)
    completed_upstream_static.append(upstream_static)
    completed_upstream_total.append(float(compression.upstream_total_pressure_Pa))
    completed_downstream_static.append(downstream_static)
    completed_downstream_total.append(float(compression.downstream_total_pressure_Pa))
    completed_mass.append(mass)
    completed_momentum.append(momentum)
    completed_energy.append(energy)
    completed_tangent.append(tangent_residual)
    completed_orientations.append(orientation)
    if abs(tangent_residual) > angle_tolerance:
      return failure(
        MocEulerShockBoundaryStatus.GEOMETRY_FAILURE,
        f'shock curve sample {index} tangent disagrees with attached shock angle by {tangent_residual}',
      )
    if max(mass, momentum, energy) > tolerance:
      return failure(
        MocEulerShockBoundaryStatus.EULER_RESIDUAL_FAILURE,
        f'shock curve sample {index} Rankine--Hugoniot residual exceeded tolerance',
      )
  ####
  if any(value is MocEulerShockBoundaryOrientation.CHARACTERISTIC_DEGENERATE for value in completed_orientations):
    return failure(
      MocEulerShockBoundaryStatus.CHARACTERISTIC_ORIENTATION_FAILURE,
      'shock curve contains a characteristic-degenerate tangent; field orientation is not robust',
    )
  if not all(value is completed_orientations[0] for value in completed_orientations):
    return failure(
      MocEulerShockBoundaryStatus.CHARACTERISTIC_ORIENTATION_FAILURE,
      'shock curve crosses downstream characteristic orientations',
    )
  orientation = completed_orientations[0]
  return MocEulerShockBoundaryCurveResult(
    status=MocEulerShockBoundaryStatus.CONVERGED_LOCAL_SHOCK,
    upstream_states=tuple(completed_upstream),
    downstream_states=tuple(completed_downstream),
    shock_points_m=tuple(completed_points),
    shock_angles_rad=tuple(completed_shock_angles),
    beta_rad=tuple(completed_beta),
    target_downstream_flow_angles_rad=tuple(completed_target_angles),
    upstream_static_pressure_Pa=tuple(completed_upstream_static),
    upstream_total_pressure_Pa=tuple(completed_upstream_total),
    downstream_static_pressure_Pa=tuple(completed_downstream_static),
    downstream_total_pressure_Pa=tuple(completed_downstream_total),
    shock_jump_mass_residuals=tuple(completed_mass),
    shock_jump_momentum_residuals=tuple(completed_momentum),
    shock_jump_energy_residuals=tuple(completed_energy),
    tangent_residuals_rad=tuple(completed_tangent),
    orientations=tuple(completed_orientations),
    orientation=orientation,
    maximum_shock_jump_residual=max(
      (*completed_mass, *completed_momentum, *completed_energy),
    ),
    maximum_tangent_residual_rad=max(abs(value) for value in completed_tangent),
    residual_tolerance=tolerance,
    shock_angle_tolerance_rad=angle_tolerance,
    message=(
      'locally Euler-consistent shock boundary converged; '
      + (
        'a companion boundary is required because the shock lies inside the '
        'downstream Mach cone'
        if orientation is MocEulerShockBoundaryOrientation.MIXED_CHARACTERISTIC_BOUNDARY
        else 'the downstream characteristic orientation is outside the Mach cone'
      )
    ),
  )


def fit_euler_consistent_shock_boundary_from_geometry(
  upstream_states: Sequence[CharacteristicState],
  upstream_pressure_Pa: Sequence[float],
  shock_points_m: Sequence[tuple[float, float]],
  *,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-10,
  shock_angle_tolerance_rad: float = 1.0e-8,
  residual_tolerance: float = 1.0e-8,
) -> MocEulerShockBoundaryCurveResult:
  """Reconcile downstream turns to a retained shock geometry.

  ``fit_euler_consistent_shock_boundary`` takes downstream flow angles as
  boundary data and checks whether the supplied geometry agrees with them.
  This companion operation reverses that local question: it derives the
  downstream turn at each sample from the actual shock tangent, then delegates
  the conservative Rankine--Hugoniot and characteristic-orientation checks to
  the ordinary curve fitter.

  The operation is intentionally only a geometry-conditioned boundary solve.
  It does not infer an ambient attachment, a companion boundary, a reflected
  post-shock field, or a continued chain cell.  In particular, a successful
  curve is not evidence that the retained geometry came from a globally
  coupled free-boundary solution.
  """

  try:
    samples = tuple(upstream_states)
    pressures = tuple(float(value) for value in upstream_pressure_Pa)
    points = tuple(
      (float(point[0]), float(point[1]))
      for point in shock_points_m
    )
    position_tolerance = float(position_tolerance_m)
    angle_tolerance = float(shock_angle_tolerance_rad)
    tolerance = float(residual_tolerance)
  except (TypeError, ValueError, IndexError):
    return _curve_failure(
      MocEulerShockBoundaryStatus.INVALID_INPUT,
      'geometry-conditioned shock inputs must contain finite numeric sequences',
      residual_tolerance=1.0e-8,
      shock_angle_tolerance_rad=1.0e-8,
    )
  if not isfinite(position_tolerance) or position_tolerance <= 0.0:
    raise ValueError('position_tolerance_m must be finite and positive')
  if not isfinite(angle_tolerance) or angle_tolerance <= 0.0:
    raise ValueError('shock_angle_tolerance_rad must be finite and positive')
  if not isfinite(tolerance) or tolerance <= 0.0:
    raise ValueError('residual_tolerance must be finite and positive')
  if not isinstance(branch, ShockBranch):
    return _curve_failure(
      MocEulerShockBoundaryStatus.INVALID_INPUT,
      'branch must be a ShockBranch',
      residual_tolerance=tolerance,
      shock_angle_tolerance_rad=angle_tolerance,
    )
  if len(samples) < 2:
    return _curve_failure(
      MocEulerShockBoundaryStatus.INVALID_INPUT,
      'geometry-conditioned shock curve requires at least two samples',
      residual_tolerance=tolerance,
      shock_angle_tolerance_rad=angle_tolerance,
    )
  if not (
    len(samples)
    == len(pressures)
    == len(points)
  ):
    return _curve_failure(
      MocEulerShockBoundaryStatus.INVALID_INPUT,
      'geometry-conditioned states, pressures, and points must have equal lengths',
      residual_tolerance=tolerance,
      shock_angle_tolerance_rad=angle_tolerance,
    )
  if not all(isinstance(state, CharacteristicState) for state in samples):
    return _curve_failure(
      MocEulerShockBoundaryStatus.INVALID_INPUT,
      'upstream_states must contain CharacteristicState values',
      residual_tolerance=tolerance,
      shock_angle_tolerance_rad=angle_tolerance,
    )

  gamma = samples[0].gamma
  for index, (state, pressure, point) in enumerate(
    zip(samples, pressures, points, strict=True)
  ):
    if abs(state.gamma - gamma) > tolerance:
      return _curve_failure(
        MocEulerShockBoundaryStatus.INVALID_INPUT,
        f'geometry-conditioned sample {index} uses a different gamma',
        residual_tolerance=tolerance,
        shock_angle_tolerance_rad=angle_tolerance,
      )
    if (
      not all(isfinite(value) for value in point)
      or abs(state.x_m - point[0]) > position_tolerance
      or abs(state.y_m - point[1]) > position_tolerance
    ):
      return _curve_failure(
        MocEulerShockBoundaryStatus.INVALID_INPUT,
        f'geometry-conditioned sample {index} state does not lie on its shock point',
        residual_tolerance=tolerance,
        shock_angle_tolerance_rad=angle_tolerance,
      )
    if not isfinite(pressure) or pressure <= 0.0:
      return _curve_failure(
        MocEulerShockBoundaryStatus.INVALID_INPUT,
        f'geometry-conditioned upstream pressure {index} must be finite and positive',
        residual_tolerance=tolerance,
        shock_angle_tolerance_rad=angle_tolerance,
      )
    if index:
      previous = points[index - 1]
      if (
        point[0] - previous[0] <= position_tolerance
        or point[1] - previous[1] > position_tolerance
      ):
        return _curve_failure(
          MocEulerShockBoundaryStatus.INVALID_INPUT,
          'geometry-conditioned shock points must be strictly downstream in x and nonincreasing in y',
          residual_tolerance=tolerance,
          shock_angle_tolerance_rad=angle_tolerance,
        )

  target_angles: list[float] = []
  for index, state in enumerate(samples):
    point = points[index]
    if index == 0:
      tangent_angle = atan2(
        points[1][1] - point[1],
        points[1][0] - point[0],
      )
    elif index == len(points) - 1:
      tangent_angle = atan2(
        point[1] - points[index - 1][1],
        point[0] - points[index - 1][0],
      )
    else:
      tangent_angle = atan2(
        points[index + 1][1] - points[index - 1][1],
        points[index + 1][0] - points[index - 1][0],
      )
    shock_angle = float(tangent_angle)
    beta = state.theta_rad - shock_angle
    mach_angle = state.mu_rad
    if (
      not isfinite(beta)
      or beta <= mach_angle
      or beta >= 0.5 * pi
    ):
      return _curve_failure(
        MocEulerShockBoundaryStatus.GEOMETRY_FAILURE,
        (
          f'geometry-conditioned sample {index} has no positive attached '
          'turn on the selected shock branch'
        ),
        residual_tolerance=tolerance,
        shock_angle_tolerance_rad=angle_tolerance,
      )
    numerator = 2.0 / tan(beta) * (
      state.mach * state.mach * sin(beta) * sin(beta) - 1.0
    )
    denominator = state.mach * state.mach * (
      state.gamma + cos(2.0 * beta)
    ) + 2.0
    if not isfinite(numerator) or not isfinite(denominator) or denominator <= 0.0:
      return _curve_failure(
        MocEulerShockBoundaryStatus.GEOMETRY_FAILURE,
        f'geometry-conditioned sample {index} has an invalid beta-to-turn relation',
        residual_tolerance=tolerance,
        shock_angle_tolerance_rad=angle_tolerance,
      )
    turn = atan(numerator / denominator)
    if not isfinite(turn) or turn <= 0.0:
      return _curve_failure(
        MocEulerShockBoundaryStatus.NONCOMPRESSIVE_TURN,
        f'geometry-conditioned sample {index} does not require compression',
        residual_tolerance=tolerance,
        shock_angle_tolerance_rad=angle_tolerance,
      )
    target_angles.append(state.theta_rad - turn)

  return fit_euler_consistent_shock_boundary(
    samples,
    pressures,
    points,
    tuple(target_angles),
    branch=branch,
    position_tolerance_m=position_tolerance,
    shock_angle_tolerance_rad=angle_tolerance,
    residual_tolerance=tolerance,
  )
