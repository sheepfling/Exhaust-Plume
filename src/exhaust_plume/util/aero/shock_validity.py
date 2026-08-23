"""Scalar oblique-shock branches, validity checks, and pressure inversion.

The public functions in this module use radians.  The older degree-based
wrappers remain in :mod:`oblique_shock` for compatibility with the original
plume solver.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import asin, atan, cos, isfinite, pi, sin, sqrt, tan
from typing import Optional

__all__ = (
    "ShockAngleSolution",
    "ShockBranch",
    "ShockPressureSolution",
    "ShockSolveStatus",
    "calculate_max_attached_turn",
    "calculate_oblique_shock_pressure_ratio",
    "calculate_normal_shock_pressure_ratio",
    "solve_shock_angle",
    "solve_shock_to_pressure",
    "theta_beta_mach_residual",
)


class ShockBranch(str, Enum):
  """The two attached solutions of the theta-beta-M relation."""

  WEAK = "weak"
  STRONG = "strong"
####


class ShockSolveStatus(str, Enum):
  """Structured outcome for an oblique-shock solve."""

  ATTACHED = "attached"
  DETACHED_SHOCK_REQUIRED = "detached_shock_required"
  PRESSURE_BELOW_UPSTREAM = "pressure_below_upstream"
  PRESSURE_ABOVE_NORMAL_SHOCK_LIMIT = "pressure_above_normal_shock_limit"
  STRONG_BRANCH_REQUIRED = "strong_branch_required"
  WEAK_BRANCH_REQUIRED = "weak_branch_required"
####


@dataclass(frozen=True)
class ShockAngleSolution:
  """Result of solving the theta-beta-M relation."""

  status: ShockSolveStatus
  branch: ShockBranch
  theta_rad: float
  beta_rad: Optional[float]
  theta_max_rad: float
  residual: Optional[float]
  message: str = ""

  @property
  def is_attached(self) -> bool:
    return self.status is ShockSolveStatus.ATTACHED
  ####
####


@dataclass(frozen=True)
class ShockPressureSolution:
  """Result of constructing an oblique shock from a target static pressure."""

  status: ShockSolveStatus
  branch: ShockBranch
  upstream_pressure_Pa: float
  target_pressure_Pa: float
  pressure_ratio: float
  max_normal_pressure_ratio: float
  theta_rad: Optional[float]
  beta_rad: Optional[float]
  theta_max_rad: float
  residual: Optional[float]
  message: str = ""

  @property
  def is_attached(self) -> bool:
    return self.status is ShockSolveStatus.ATTACHED
  ####
####


def _validate_mach_gamma(mach: float, gamma: float) -> None:
  if not isfinite(mach) or mach <= 1.0:
    raise ValueError(f"Oblique shocks require a finite upstream Mach number > 1; got {mach!r}")
  ####
  if not isfinite(gamma) or gamma <= 1.0:
    raise ValueError(f"Oblique shocks require a finite gamma > 1; got {gamma!r}")
  ####
####


def _mach_angle_rad(mach: float) -> float:
  return asin(1.0 / mach)
####


def calculate_oblique_shock_pressure_ratio(*, mach: float, beta_rad: float, gamma: float) -> float:
  """Return ``p2/p1`` from the upstream normal Mach component."""

  _validate_mach_gamma(mach, gamma)
  if not isfinite(beta_rad) or not 0.0 < beta_rad <= pi / 2.0:
    raise ValueError(f"Shock angle must be in (0, pi/2]; got {beta_rad!r}")
  ####
  normal_mach = mach * sin(beta_rad)
  if normal_mach < 1.0:
    raise ValueError("An attached oblique shock must have a normal Mach component >= 1")
  ####
  return calculate_normal_shock_pressure_ratio(mach=normal_mach, gamma=gamma)
####


def calculate_normal_shock_pressure_ratio(*, mach: float, gamma: float) -> float:
  """Return the normal-shock static pressure ratio for a normal Mach number."""

  if not isfinite(mach) or mach < 1.0:
    raise ValueError(f"Normal-shock Mach number must be finite and >= 1; got {mach!r}")
  ####
  if not isfinite(gamma) or gamma <= 1.0:
    raise ValueError(f"Normal shocks require a finite gamma > 1; got {gamma!r}")
  ####
  return 1.0 + (2.0 * gamma / (gamma + 1.0)) * (mach**2 - 1.0)
####


def _theta_from_beta(beta_rad: float, mach: float, gamma: float) -> float:
  numerator = 2.0 / tan(beta_rad) * (mach**2 * sin(beta_rad)**2 - 1.0)
  denominator = mach**2 * (gamma + cos(2.0 * beta_rad)) + 2.0
  return atan(numerator / denominator)
####


def theta_beta_mach_residual(*, theta_rad: float, beta_rad: float, mach: float, gamma: float) -> float:
  r"""Return the theta-beta-M residual in radians.

  The returned value is

  ``tan(theta) - 2*cot(beta)*(M**2*sin(beta)**2 - 1) /``
  ``(M**2*(gamma + cos(2*beta)) + 2)``.
  """

  _validate_mach_gamma(mach, gamma)
  if not isfinite(theta_rad) or not isfinite(beta_rad):
    raise ValueError("Shock angles and turns must be finite")
  ####
  return tan(theta_rad) - 2.0 / tan(beta_rad) * (mach**2 * sin(beta_rad)**2 - 1.0) / (mach**2 * (gamma + cos(2.0 * beta_rad)) + 2.0)
####


def _beta_at_max_attached_turn(*, mach: float, gamma: float) -> tuple[float, float]:
  """Locate the interior maximum of theta(beta) deterministically."""

  _validate_mach_gamma(mach, gamma)
  mach_angle = _mach_angle_rad(mach)
  span = pi / 2.0 - mach_angle
  # The endpoints are limiting points where theta is zero.  Keeping them a
  # tiny distance away avoids evaluating cot(pi/2) or a subsonic normal
  # component due solely to floating-point roundoff.
  epsilon = max(1.0e-12, span * 1.0e-10)
  lower = mach_angle + epsilon
  upper = pi / 2.0 - epsilon
  sample_count = 257
  step = (upper - lower) / (sample_count - 1)
  samples = [lower + index * step for index in range(sample_count)]
  values = [_theta_from_beta(beta, mach, gamma) for beta in samples]
  best_index = max(range(sample_count), key=values.__getitem__)
  left_index = max(0, best_index - 1)
  right_index = min(sample_count - 1, best_index + 1)
  left = samples[left_index]
  right = samples[right_index]

  # Golden-section maximization of the local peak identified by the scan.
  golden = (sqrt(5.0) - 1.0) / 2.0
  x1 = right - golden * (right - left)
  x2 = left + golden * (right - left)
  f1 = _theta_from_beta(x1, mach, gamma)
  f2 = _theta_from_beta(x2, mach, gamma)
  for _ in range(96):
    if f1 < f2:
      left = x1
      x1 = x2
      f1 = f2
      x2 = left + golden * (right - left)
      f2 = _theta_from_beta(x2, mach, gamma)
    else:
      right = x2
      x2 = x1
      f2 = f1
      x1 = right - golden * (right - left)
      f1 = _theta_from_beta(x1, mach, gamma)
    ####
  ####
  beta_peak = (left + right) / 2.0
  return beta_peak, _theta_from_beta(beta_peak, mach, gamma)
####


def calculate_max_attached_turn(*, mach: float, gamma: float) -> float:
  """Return the maximum attached positive turn in radians."""

  return _beta_at_max_attached_turn(mach=mach, gamma=gamma)[1]
####


def _bisect_beta(*, theta_rad: float, mach: float, gamma: float, branch: ShockBranch, beta_peak: float, theta_max_rad: float) -> float:
  mach_angle = _mach_angle_rad(mach)
  if branch is ShockBranch.WEAK:
    lower = mach_angle
    upper = beta_peak
  else:
    lower = beta_peak
    upper = pi / 2.0
  ####
  lower_value = _theta_from_beta(lower, mach, gamma) - theta_rad
  if abs(theta_rad - theta_max_rad) <= 1.0e-13:
    return beta_peak
  ####
  for _ in range(160):
    middle = (lower + upper) / 2.0
    middle_value = _theta_from_beta(middle, mach, gamma) - theta_rad
    if abs(middle_value) <= 1.0e-14:
      return middle
    ####
    if lower_value * middle_value <= 0.0:
      upper = middle
    else:
      lower = middle
      lower_value = middle_value
    ####
  ####
  return (lower + upper) / 2.0
####


def solve_shock_angle(*, theta_rad: float, mach: float, gamma: float, branch: ShockBranch = ShockBranch.WEAK) -> ShockAngleSolution:
  """Solve an explicit weak or strong attached oblique-shock branch."""

  _validate_mach_gamma(mach, gamma)
  if not isfinite(theta_rad) or theta_rad < 0.0:
    raise ValueError(f"Turn angle must be finite and non-negative; got {theta_rad!r}")
  ####
  beta_peak, theta_max = _beta_at_max_attached_turn(mach=mach, gamma=gamma)
  tolerance = max(1.0e-12, theta_max * 1.0e-10)
  if theta_rad > theta_max + tolerance:
    return ShockAngleSolution(
        status=ShockSolveStatus.DETACHED_SHOCK_REQUIRED,
        branch=branch,
        theta_rad=theta_rad,
        beta_rad=None,
        theta_max_rad=theta_max,
        residual=None,
        message=f"Requested turn {theta_rad:g} rad exceeds attached maximum {theta_max:g} rad",
    )
  ####
  if theta_rad == 0.0:
    beta = _mach_angle_rad(mach) if branch is ShockBranch.WEAK else pi / 2.0
  elif theta_rad >= theta_max - tolerance:
    beta = beta_peak
  else:
    beta = _bisect_beta(theta_rad=theta_rad, mach=mach, gamma=gamma, branch=branch, beta_peak=beta_peak, theta_max_rad=theta_max)
  ####
  residual = theta_beta_mach_residual(theta_rad=theta_rad, beta_rad=beta, mach=mach, gamma=gamma)
  return ShockAngleSolution(
      status=ShockSolveStatus.ATTACHED,
      branch=branch,
      theta_rad=theta_rad,
      beta_rad=beta,
      theta_max_rad=theta_max,
      residual=residual,
  )
####


def solve_shock_to_pressure(*, mach: float, gamma: float, upstream_pressure_Pa: float, target_pressure_Pa: float,
                            branch: Optional[ShockBranch] = None, weak_only: bool = False) -> ShockPressureSolution:
  """Construct an attached shock directly from a target static pressure.

  Pressure inversion is performed through the upstream normal Mach number
  ``M_n1`` and then ``beta = asin(M_n1/M)``.  A target above the normal-shock
  limit is reported as unattainable rather than being returned as a nominal
  oblique state.
  """

  _validate_mach_gamma(mach, gamma)
  if not isfinite(upstream_pressure_Pa) or upstream_pressure_Pa <= 0.0:
    raise ValueError("Upstream pressure must be finite and positive")
  ####
  if not isfinite(target_pressure_Pa) or target_pressure_Pa <= 0.0:
    raise ValueError("Target pressure must be finite and positive")
  ####
  beta_peak, theta_max = _beta_at_max_attached_turn(mach=mach, gamma=gamma)
  max_pressure_ratio = calculate_normal_shock_pressure_ratio(mach=mach, gamma=gamma)
  pressure_ratio = target_pressure_Pa / upstream_pressure_Pa
  pressure_tolerance = max(1.0e-12, max_pressure_ratio * 1.0e-10)
  if pressure_ratio < 1.0 - pressure_tolerance:
    return ShockPressureSolution(
        status=ShockSolveStatus.PRESSURE_BELOW_UPSTREAM,
        branch=branch or ShockBranch.WEAK,
        upstream_pressure_Pa=upstream_pressure_Pa,
        target_pressure_Pa=target_pressure_Pa,
        pressure_ratio=pressure_ratio,
        max_normal_pressure_ratio=max_pressure_ratio,
        theta_rad=None,
        beta_rad=None,
        theta_max_rad=theta_max,
        residual=None,
        message="An attached compression shock cannot reduce static pressure",
    )
  ####
  if pressure_ratio > max_pressure_ratio + pressure_tolerance:
    return ShockPressureSolution(
        status=ShockSolveStatus.PRESSURE_ABOVE_NORMAL_SHOCK_LIMIT,
        branch=branch or ShockBranch.STRONG,
        upstream_pressure_Pa=upstream_pressure_Pa,
        target_pressure_Pa=target_pressure_Pa,
        pressure_ratio=pressure_ratio,
        max_normal_pressure_ratio=max_pressure_ratio,
        theta_rad=None,
        beta_rad=None,
        theta_max_rad=theta_max,
        residual=None,
        message=f"Target pressure ratio {pressure_ratio:g} exceeds normal-shock limit {max_pressure_ratio:g}",
    )
  ####

  pressure_ratio = min(max(1.0, pressure_ratio), max_pressure_ratio)
  normal_mach_squared = 1.0 + (pressure_ratio - 1.0) * (gamma + 1.0) / (2.0 * gamma)
  normal_mach = sqrt(normal_mach_squared)
  beta = asin(min(1.0, normal_mach / mach))
  actual_branch = ShockBranch.WEAK if beta <= beta_peak else ShockBranch.STRONG
  if weak_only or (branch is ShockBranch.WEAK and actual_branch is ShockBranch.STRONG):
    return ShockPressureSolution(
        status=ShockSolveStatus.STRONG_BRANCH_REQUIRED,
        branch=actual_branch,
        upstream_pressure_Pa=upstream_pressure_Pa,
        target_pressure_Pa=target_pressure_Pa,
        pressure_ratio=pressure_ratio,
        max_normal_pressure_ratio=max_pressure_ratio,
        theta_rad=None,
        beta_rad=beta,
        theta_max_rad=theta_max,
        residual=None,
        message="The requested pressure requires the strong attached branch",
    )
  ####
  if branch is ShockBranch.STRONG and actual_branch is ShockBranch.WEAK:
    return ShockPressureSolution(
        status=ShockSolveStatus.WEAK_BRANCH_REQUIRED,
        branch=actual_branch,
        upstream_pressure_Pa=upstream_pressure_Pa,
        target_pressure_Pa=target_pressure_Pa,
        pressure_ratio=pressure_ratio,
        max_normal_pressure_ratio=max_pressure_ratio,
        theta_rad=None,
        beta_rad=beta,
        theta_max_rad=theta_max,
        residual=None,
        message="The requested pressure lies on the weak attached branch",
    )
  ####
  theta = _theta_from_beta(beta, mach, gamma)
  residual = theta_beta_mach_residual(theta_rad=theta, beta_rad=beta, mach=mach, gamma=gamma)
  return ShockPressureSolution(
      status=ShockSolveStatus.ATTACHED,
      branch=actual_branch,
      upstream_pressure_Pa=upstream_pressure_Pa,
      target_pressure_Pa=target_pressure_Pa,
      pressure_ratio=pressure_ratio,
      max_normal_pressure_ratio=max_pressure_ratio,
      theta_rad=theta,
      beta_rad=beta,
      theta_max_rad=theta_max,
      residual=residual,
  )
####
