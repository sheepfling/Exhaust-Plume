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
from math import cos, hypot, isfinite, sin, sqrt, tan
from typing import Any

from exhaust_plume.models.moc.compression import solve_attached_compression_to_turn
from exhaust_plume.models.moc.primitives import CharacteristicState
from exhaust_plume.util.aero.shock_validity import ShockBranch

__all__ = (
  'MocEulerShockBoundaryStatus',
  'MocEulerShockBoundaryResult',
  'solve_euler_consistent_attached_shock_segment',
)


class MocEulerShockBoundaryStatus(str, Enum):
  """Outcome of one locally Euler-consistent attached-shock segment."""

  CONVERGED_LOCAL_SHOCK = 'converged_local_euler_shock'
  INVALID_INPUT = 'invalid_input'
  NONCOMPRESSIVE_TURN = 'noncompressive_turn'
  COMPRESSION_FAILURE = 'compression_failure'
  GEOMETRY_FAILURE = 'geometry_failure'
  EULER_RESIDUAL_FAILURE = 'euler_residual_failure'


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
