"""Deterministic planar MOC state and compatibility primitives.

This module implements the numerical foundation for a future validated first
cell.  It deliberately stops at scalar thermodynamic inversion and planar
characteristic compatibility; it does not assemble a public plume provider or
relabel the existing low-order shock-cell construction as MOC geometry.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from math import asin, atan, cos, inf, isfinite, pi, sin, sqrt

import numpy as np

from exhaust_plume.geometry.contracts import RayIntersectionStatus
from exhaust_plume.geometry.contracts import Ray2D
from exhaust_plume.geometry.intersections import intersect_rays

__all__ = (
  'CharacteristicFamily',
  'CharacteristicPointResult',
  'CharacteristicState',
  'MocPrimitiveStatus',
  'ScalarRootResult',
  'centerline_characteristic_point',
  'characteristic_invariants',
  'interior_characteristic_point',
  'inverse_prandtl_meyer_angle_rad',
  'mach_angle_rad',
  'maximum_prandtl_meyer_angle_rad',
  'prandtl_meyer_angle_rad',
  'supersonic_mach_from_stagnation_pressure_ratio',
)


class MocPrimitiveStatus(str, Enum):
  """Structured outcomes shared by MOC scalar and geometry primitives."""

  CONVERGED = 'converged'
  INVALID_INPUT = 'invalid_input'
  OUTSIDE_DOMAIN = 'outside_domain'
  MAX_ITERATIONS = 'max_iterations'
  GEOMETRY_FAILURE = 'geometry_failure'
  INVARIANT_FAILURE = 'invariant_failure'
####


class CharacteristicFamily(str, Enum):
  """Planar characteristic families in the ``x``-downstream frame."""

  PLUS = 'C+'
  MINUS = 'C-'
####


@dataclass(frozen=True, slots=True)
class ScalarRootResult:
  """A bracketed scalar inversion result with its residual and bracket."""

  status: MocPrimitiveStatus
  value: float | None
  residual: float | None
  iterations: int
  lower_bound: float
  upper_bound: float
  message: str = ''

  @property
  def converged(self) -> bool:
    return self.status is MocPrimitiveStatus.CONVERGED
####


@dataclass(frozen=True, slots=True)
class CharacteristicState:
  """A planar supersonic state and its geometric location.

  ``theta_rad`` is the flow angle measured counter-clockwise from +x.  The
  state carries no thermodynamic units beyond ``gamma`` and Mach because the
  first MOC tranche only needs compatibility invariants.
  """

  x_m: float
  y_m: float
  theta_rad: float
  mach: float
  gamma: float = 1.4

  def __post_init__(self) -> None:
    values = (self.x_m, self.y_m, self.theta_rad, self.mach, self.gamma)
    if any(not isfinite(float(value)) for value in values):
      raise ValueError('characteristic state values must be finite')
    if self.mach <= 1.0:
      raise ValueError('characteristic state Mach number must be greater than one')
    if self.gamma <= 1.0:
      raise ValueError('characteristic state gamma must be greater than one')
  ####

  @property
  def nu_rad(self) -> float:
    return prandtl_meyer_angle_rad(self.mach, self.gamma)
  ####

  @property
  def mu_rad(self) -> float:
    return mach_angle_rad(self.mach)
  ####

  @property
  def k_plus(self) -> float:
    return self.theta_rad - self.nu_rad
  ####

  @property
  def k_minus(self) -> float:
    return self.theta_rad + self.nu_rad
  ####

  def direction(self, family: CharacteristicFamily) -> tuple[float, float]:
    """Return a unit direction for the requested characteristic family."""

    angle = self.theta_rad + self.mu_rad if family is CharacteristicFamily.PLUS else self.theta_rad - self.mu_rad
    return cos(angle), sin(angle)
  ####
####


@dataclass(frozen=True, slots=True)
class CharacteristicPointResult:
  """Result of a compatibility point construction.

  Both compatibility residuals and the normalized line-intersection residual
  are retained.  A finite coordinate alone is never considered a successful
  MOC point.
  """

  status: MocPrimitiveStatus
  state: CharacteristicState | None
  point_m: tuple[float, float] | None
  invariant_residual_plus: float | None
  invariant_residual_minus: float | None
  geometry_residual: float | None
  iterations: int
  intersection_status: str | None = None
  message: str = ''

  @property
  def converged(self) -> bool:
    return self.status is MocPrimitiveStatus.CONVERGED
####


def _validate_gamma(gamma: float) -> float:
  value = float(gamma)
  if not isfinite(value) or value <= 1.0:
    raise ValueError(f'gamma must be finite and greater than one; got {gamma!r}')
  return value
####


def _validate_mach(mach: float) -> float:
  value = float(mach)
  if not isfinite(value) or value < 1.0:
    raise ValueError(f'Mach number must be finite and at least one; got {mach!r}')
  return value
####


def prandtl_meyer_angle_rad(mach: float, gamma: float) -> float:
  r"""Return the Prandtl--Meyer angle in radians for ``M >= 1``."""

  mach_value = _validate_mach(mach)
  gamma_value = _validate_gamma(gamma)
  if mach_value == 1.0:
    return 0.0
  root = sqrt(mach_value * mach_value - 1.0)
  coefficient = sqrt((gamma_value + 1.0) / (gamma_value - 1.0))
  return coefficient * atan(root / coefficient) - atan(root)
####


def maximum_prandtl_meyer_angle_rad(gamma: float) -> float:
  """Return the finite asymptotic Prandtl--Meyer angle."""

  gamma_value = _validate_gamma(gamma)
  return 0.5 * pi * (sqrt((gamma_value + 1.0) / (gamma_value - 1.0)) - 1.0)
####


def mach_angle_rad(mach: float) -> float:
  """Return ``asin(1/M)`` for a supersonic Mach number."""

  mach_value = float(mach)
  if not isfinite(mach_value) or mach_value <= 1.0:
    raise ValueError(f'Mach angle requires a finite Mach number greater than one; got {mach!r}')
  return asin(1.0 / mach_value)
####


def inverse_prandtl_meyer_angle_rad(
    nu_rad: float,
    gamma: float,
    *,
    absolute_tolerance: float = 1.0e-12,
    relative_tolerance: float = 1.0e-12,
    maximum_iterations: int = 160,
) -> ScalarRootResult:
  """Invert ``nu(M)`` with a deterministic bracketed bisection.

  The asymptotic angle is not returned as a finite Mach number.  Requests at
  or above that limit are reported as ``OUTSIDE_DOMAIN`` rather than silently
  returning an arbitrary large Mach number.
  """

  gamma_value = _validate_gamma(gamma)
  target = float(nu_rad)
  if not isfinite(target) or target < 0.0:
    raise ValueError(f'nu_rad must be finite and non-negative; got {nu_rad!r}')
  if not isfinite(absolute_tolerance) or absolute_tolerance <= 0.0:
    raise ValueError('absolute_tolerance must be finite and positive')
  if not isfinite(relative_tolerance) or relative_tolerance <= 0.0:
    raise ValueError('relative_tolerance must be finite and positive')
  if isinstance(maximum_iterations, bool) or maximum_iterations < 1:
    raise ValueError('maximum_iterations must be a positive integer')
  ####
  maximum = maximum_prandtl_meyer_angle_rad(gamma_value)
  tolerance = absolute_tolerance + relative_tolerance * abs(target)
  if target >= maximum:
    return ScalarRootResult(
      status=MocPrimitiveStatus.OUTSIDE_DOMAIN,
      value=None,
      residual=None,
      iterations=0,
      lower_bound=1.0,
      upper_bound=inf,
      message='the requested angle requires Mach approaching infinity',
    )
  if target <= tolerance:
    return ScalarRootResult(
      status=MocPrimitiveStatus.CONVERGED,
      value=1.0,
      residual=-target,
      iterations=0,
      lower_bound=1.0,
      upper_bound=1.0,
    )
  ####
  lower = 1.0
  upper = 2.0
  bracket_iterations = 0
  while prandtl_meyer_angle_rad(upper, gamma_value) < target:
    upper *= 2.0
    bracket_iterations += 1
    if bracket_iterations >= maximum_iterations or not isfinite(upper):
      return ScalarRootResult(
        status=MocPrimitiveStatus.MAX_ITERATIONS,
        value=None,
        residual=None,
        iterations=bracket_iterations,
        lower_bound=lower,
        upper_bound=upper,
        message='could not bracket the requested Prandtl--Meyer angle',
      )
  ####
  iterations = bracket_iterations
  midpoint = upper
  residual = prandtl_meyer_angle_rad(midpoint, gamma_value) - target
  for _ in range(maximum_iterations):
    midpoint = 0.5 * (lower + upper)
    residual = prandtl_meyer_angle_rad(midpoint, gamma_value) - target
    iterations += 1
    if abs(residual) <= tolerance:
      return ScalarRootResult(
        status=MocPrimitiveStatus.CONVERGED,
        value=midpoint,
        residual=residual,
        iterations=iterations,
        lower_bound=lower,
        upper_bound=upper,
      )
    if residual > 0.0:
      upper = midpoint
    else:
      lower = midpoint
    if abs(upper - lower) <= absolute_tolerance * max(1.0, abs(midpoint)):
      return ScalarRootResult(
        status=MocPrimitiveStatus.CONVERGED,
        value=midpoint,
        residual=residual,
        iterations=iterations,
        lower_bound=lower,
        upper_bound=upper,
      )
  ####
  return ScalarRootResult(
    status=MocPrimitiveStatus.MAX_ITERATIONS,
    value=None,
    residual=residual,
    iterations=iterations,
    lower_bound=lower,
    upper_bound=upper,
    message='Prandtl--Meyer inversion did not meet its residual tolerance',
  )
####


def supersonic_mach_from_stagnation_pressure_ratio(
    pressure_ratio_p0_over_p: float,
    gamma: float,
) -> ScalarRootResult:
  """Invert the isentropic ``p0/p`` relation on the supersonic branch."""

  gamma_value = _validate_gamma(gamma)
  ratio = float(pressure_ratio_p0_over_p)
  if not isfinite(ratio) or ratio <= 1.0:
    raise ValueError('pressure_ratio_p0_over_p must be finite and greater than one')
  mach_squared = 2.0 / (gamma_value - 1.0) * (
    ratio ** ((gamma_value - 1.0) / gamma_value) - 1.0
  )
  if mach_squared <= 1.0 or not isfinite(mach_squared):
    return ScalarRootResult(
      status=MocPrimitiveStatus.OUTSIDE_DOMAIN,
      value=None,
      residual=None,
      iterations=0,
      lower_bound=1.0,
      upper_bound=inf,
      message='stagnation pressure ratio does not produce a supersonic state',
    )
  mach = sqrt(mach_squared)
  reconstructed = (1.0 + 0.5 * (gamma_value - 1.0) * mach * mach) ** (gamma_value / (gamma_value - 1.0))
  return ScalarRootResult(
    status=MocPrimitiveStatus.CONVERGED,
    value=mach,
    residual=reconstructed - ratio,
    iterations=0,
    lower_bound=mach,
    upper_bound=mach,
  )
####


def characteristic_invariants(state: CharacteristicState) -> tuple[float, float]:
  """Return ``(K_plus, K_minus) = (theta-nu, theta+nu)``."""

  return state.k_plus, state.k_minus
####


def _state_from_compatibility(
    *,
    x_m: float,
    y_m: float,
    theta_rad: float,
    nu_rad: float,
    gamma: float,
) -> tuple[CharacteristicState | None, MocPrimitiveStatus, str]:
  if nu_rad < -1.0e-12:
    return None, MocPrimitiveStatus.OUTSIDE_DOMAIN, 'characteristic compatibility produced a negative Prandtl--Meyer angle'
  inversion = inverse_prandtl_meyer_angle_rad(max(0.0, nu_rad), gamma)
  if not inversion.converged or inversion.value is None:
    return None, inversion.status, inversion.message
  return (
    CharacteristicState(
      x_m=x_m,
      y_m=y_m,
      theta_rad=theta_rad,
      mach=inversion.value,
      gamma=gamma,
    ),
    MocPrimitiveStatus.CONVERGED,
    '',
  )
####


def _characteristic_ray(
    state: CharacteristicState,
    family: CharacteristicFamily,
    *,
    target_state: CharacteristicState | None = None,
) -> Ray2D:
  if target_state is None:
    direction = state.direction(family)
  else:
    start_angle = state.theta_rad + state.mu_rad if family is CharacteristicFamily.PLUS else state.theta_rad - state.mu_rad
    end_angle = target_state.theta_rad + target_state.mu_rad if family is CharacteristicFamily.PLUS else target_state.theta_rad - target_state.mu_rad
    direction = (cos(0.5 * (start_angle + end_angle)), sin(0.5 * (start_angle + end_angle)))
  return Ray2D(
    origin=np.asarray((state.x_m, state.y_m), dtype=float),
    direction=np.asarray(direction, dtype=float),
  )
####


def _intersection_failure(result: object) -> tuple[MocPrimitiveStatus, str]:
  status = getattr(result, 'status', None)
  if status is RayIntersectionStatus.BEHIND_FIRST_RAY or status is RayIntersectionStatus.BEHIND_SECOND_RAY or status is RayIntersectionStatus.BEHIND_RAY:
    return MocPrimitiveStatus.GEOMETRY_FAILURE, f'characteristic intersection is not forward: {status.value}'
  return MocPrimitiveStatus.GEOMETRY_FAILURE, f'characteristic rays do not intersect robustly: {getattr(status, "value", status)}'
####


def interior_characteristic_point(
    plus_source: CharacteristicState,
    minus_source: CharacteristicState,
    *,
    position_tolerance_m: float = 1.0e-10,
    invariant_tolerance: float = 1.0e-10,
    condition_limit: float = 1.0e10,
    maximum_iterations: int = 16,
) -> CharacteristicPointResult:
  """Construct an interior point from one incoming ``C+`` and ``C-``.

  Compatibility determines the state; the averaged characteristic directions
  determine the geometry.  The result is rejected when either ray is not
  forward or the invariant residuals exceed the declared tolerance.
  """

  if not isfinite(position_tolerance_m) or position_tolerance_m <= 0.0:
    raise ValueError('position_tolerance_m must be finite and positive')
  if not isfinite(invariant_tolerance) or invariant_tolerance <= 0.0:
    raise ValueError('invariant_tolerance must be finite and positive')
  if not isfinite(condition_limit) or condition_limit <= 1.0:
    raise ValueError('condition_limit must be finite and greater than one')
  if isinstance(maximum_iterations, bool) or maximum_iterations < 1:
    raise ValueError('maximum_iterations must be a positive integer')
  if abs(plus_source.gamma - minus_source.gamma) > invariant_tolerance:
    return CharacteristicPointResult(
      status=MocPrimitiveStatus.INVALID_INPUT,
      state=None,
      point_m=None,
      invariant_residual_plus=None,
      invariant_residual_minus=None,
      geometry_residual=None,
      iterations=0,
      message='incoming characteristic states must use the same gamma',
    )
  ####
  gamma = plus_source.gamma
  k_plus = plus_source.k_plus
  k_minus = minus_source.k_minus
  theta = 0.5 * (k_plus + k_minus)
  nu = 0.5 * (k_minus - k_plus)
  state, status, message = _state_from_compatibility(
    x_m=0.0,
    y_m=0.0,
    theta_rad=theta,
    nu_rad=nu,
    gamma=gamma,
  )
  if state is None:
    return CharacteristicPointResult(
      status=status,
      state=None,
      point_m=None,
      invariant_residual_plus=None,
      invariant_residual_minus=None,
      geometry_residual=None,
      iterations=0,
      message=message,
    )
  ####
  previous_point: tuple[float, float] | None = None
  last_intersection_status: str | None = None
  last_geometry_residual: float | None = None
  for iteration in range(1, maximum_iterations + 1):
    plus_ray = _characteristic_ray(plus_source, CharacteristicFamily.PLUS, target_state=state)
    minus_ray = _characteristic_ray(minus_source, CharacteristicFamily.MINUS, target_state=state)
    intersection = intersect_rays(
      plus_ray,
      minus_ray,
      condition_limit=condition_limit,
      parameter_tolerance=position_tolerance_m,
    )
    last_intersection_status = intersection.status.value
    last_geometry_residual = intersection.residual
    if not intersection.is_success or intersection.point is None:
      failure_status, failure_message = _intersection_failure(intersection)
      return CharacteristicPointResult(
        status=failure_status,
        state=None,
        point_m=None,
        invariant_residual_plus=None,
        invariant_residual_minus=None,
        geometry_residual=intersection.residual,
        iterations=iteration,
        intersection_status=intersection.status.value,
        message=failure_message,
      )
    point = (float(intersection.point[0]), float(intersection.point[1]))
    state = replace(state, x_m=point[0], y_m=point[1])
    if previous_point is not None:
      displacement = sqrt((point[0] - previous_point[0]) ** 2 + (point[1] - previous_point[1]) ** 2)
      if displacement <= position_tolerance_m:
        break
    previous_point = point
  else:
    return CharacteristicPointResult(
      status=MocPrimitiveStatus.MAX_ITERATIONS,
      state=state,
      point_m=(state.x_m, state.y_m),
      invariant_residual_plus=state.k_plus - k_plus,
      invariant_residual_minus=state.k_minus - k_minus,
      geometry_residual=last_geometry_residual,
      iterations=maximum_iterations,
      intersection_status=last_intersection_status,
      message='interior characteristic geometry did not converge',
    )
  ####
  residual_plus = state.k_plus - k_plus
  residual_minus = state.k_minus - k_minus
  if max(abs(residual_plus), abs(residual_minus)) > invariant_tolerance:
    return CharacteristicPointResult(
      status=MocPrimitiveStatus.INVARIANT_FAILURE,
      state=state,
      point_m=(state.x_m, state.y_m),
      invariant_residual_plus=residual_plus,
      invariant_residual_minus=residual_minus,
      geometry_residual=last_geometry_residual,
      iterations=iteration,
      intersection_status=last_intersection_status,
      message='interior characteristic compatibility residual exceeded tolerance',
    )
  return CharacteristicPointResult(
    status=MocPrimitiveStatus.CONVERGED,
    state=state,
    point_m=(state.x_m, state.y_m),
    invariant_residual_plus=residual_plus,
    invariant_residual_minus=residual_minus,
    geometry_residual=last_geometry_residual,
    iterations=iteration,
    intersection_status=last_intersection_status,
  )
####


def centerline_characteristic_point(
    source: CharacteristicState,
    family: CharacteristicFamily,
    *,
    position_tolerance_m: float = 1.0e-10,
    invariant_tolerance: float = 1.0e-10,
    condition_limit: float = 1.0e10,
) -> CharacteristicPointResult:
  """Intersect one compatible characteristic with ``y=0``."""

  if not isfinite(position_tolerance_m) or position_tolerance_m <= 0.0:
    raise ValueError('position_tolerance_m must be finite and positive')
  if not isfinite(invariant_tolerance) or invariant_tolerance <= 0.0:
    raise ValueError('invariant_tolerance must be finite and positive')
  if family is CharacteristicFamily.PLUS:
    target_nu = -source.k_plus
  else:
    target_nu = source.k_minus
  state, status, message = _state_from_compatibility(
    x_m=source.x_m,
    y_m=0.0,
    theta_rad=0.0,
    nu_rad=target_nu,
    gamma=source.gamma,
  )
  if state is None:
    return CharacteristicPointResult(
      status=status,
      state=None,
      point_m=None,
      invariant_residual_plus=None,
      invariant_residual_minus=None,
      geometry_residual=None,
      iterations=0,
      message=message,
    )
  ####
  characteristic_ray = _characteristic_ray(source, family, target_state=state)
  centerline_ray = Ray2D(
    origin=np.asarray((source.x_m, 0.0), dtype=float),
    direction=np.asarray((1.0, 0.0), dtype=float),
  )
  intersection = intersect_rays(
    characteristic_ray,
    centerline_ray,
    condition_limit=condition_limit,
    parameter_tolerance=position_tolerance_m,
  )
  if not intersection.is_success or intersection.point is None:
    failure_status, failure_message = _intersection_failure(intersection)
    return CharacteristicPointResult(
      status=failure_status,
      state=None,
      point_m=None,
      invariant_residual_plus=None,
      invariant_residual_minus=None,
      geometry_residual=intersection.residual,
      iterations=1,
      intersection_status=intersection.status.value,
      message=failure_message,
    )
  ####
  point = (float(intersection.point[0]), 0.0)
  state = replace(state, x_m=point[0], y_m=point[1])
  residual_plus = state.k_plus - source.k_plus
  residual_minus = state.k_minus - source.k_minus
  family_residual = residual_plus if family is CharacteristicFamily.PLUS else residual_minus
  if abs(family_residual) > invariant_tolerance:
    return CharacteristicPointResult(
      status=MocPrimitiveStatus.INVARIANT_FAILURE,
      state=state,
      point_m=point,
      invariant_residual_plus=(residual_plus if family is CharacteristicFamily.PLUS else None),
      invariant_residual_minus=(residual_minus if family is CharacteristicFamily.MINUS else None),
      geometry_residual=intersection.residual,
      iterations=1,
      intersection_status=intersection.status.value,
      message='centerline characteristic compatibility residual exceeded tolerance',
    )
  return CharacteristicPointResult(
    status=MocPrimitiveStatus.CONVERGED,
    state=state,
    point_m=point,
    invariant_residual_plus=(residual_plus if family is CharacteristicFamily.PLUS else None),
    invariant_residual_minus=(residual_minus if family is CharacteristicFamily.MINUS else None),
    geometry_residual=intersection.residual,
    iterations=1,
    intersection_status=intersection.status.value,
  )
####
