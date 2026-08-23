"""Branch-explicit area--Mach and choked mass-flow relations."""

from __future__ import annotations

from enum import Enum
from math import isfinite, sqrt


class MachBranch(str, Enum):
  SUBSONIC = 'subsonic'
  SUPERSONIC = 'supersonic'
  ####


def _validate_gamma(gamma: float) -> None:
  if not isfinite(gamma) or gamma <= 1.0:
    raise ValueError(f'gamma must be finite and greater than one; got {gamma}')
  ####
####


def calc_mass_flow_parameter(mach: float, gamma: float) -> float:
  r"""Return ``M (1 + (gamma-1) M^2/2)^(-(gamma+1)/(2(gamma-1)))``."""

  _validate_gamma(gamma)
  if not isfinite(mach) or mach <= 0.0:
    raise ValueError(f'mach must be finite and positive; got {mach}')
  factor = 1.0 + (gamma - 1.0) * mach**2 / 2.0
  return mach * factor**(-(gamma + 1.0) / (2.0 * (gamma - 1.0)))
####


def calc_mass_flow_rate(
    *,
    area_m2: float,
    mach: float,
    total_pressure_Pa: float,
    total_temperature_K: float,
    gamma: float,
    specific_gas_constant_JpkgK: float,
) -> float:
  r"""Calculate ideal-gas mass flow from a uniform area and total state."""

  _validate_gamma(gamma)
  if not isfinite(area_m2) or area_m2 <= 0.0:
    raise ValueError(f'area_m2 must be finite and positive; got {area_m2}')
  if not isfinite(total_pressure_Pa) or total_pressure_Pa <= 0.0:
    raise ValueError(f'total_pressure_Pa must be finite and positive; got {total_pressure_Pa}')
  if not isfinite(total_temperature_K) or total_temperature_K <= 0.0:
    raise ValueError(f'total_temperature_K must be finite and positive; got {total_temperature_K}')
  if not isfinite(specific_gas_constant_JpkgK) or specific_gas_constant_JpkgK <= 0.0:
    raise ValueError(
        f'specific_gas_constant_JpkgK must be finite and positive; got {specific_gas_constant_JpkgK}'
    )
  return (
      area_m2
      * total_pressure_Pa
      * sqrt(gamma / (specific_gas_constant_JpkgK * total_temperature_K))
      * calc_mass_flow_parameter(mach, gamma)
  )
####


def calc_choked_throat_area(
    *,
    mass_flow_rate_kgps: float,
    total_pressure_Pa: float,
    total_temperature_K: float,
    gamma: float,
    specific_gas_constant_JpkgK: float,
) -> float:
  r"""Return the choked throat area using the corrected half exponent.

  The governing relation is
  ``A* = mdot/p0 * sqrt(R*T0/gamma) * ((gamma+1)/2)**((gamma+1)/(2*(gamma-1)))``.
  """

  _validate_gamma(gamma)
  if not isfinite(mass_flow_rate_kgps) or mass_flow_rate_kgps <= 0.0:
    raise ValueError(f'mass_flow_rate_kgps must be finite and positive; got {mass_flow_rate_kgps}')
  if not isfinite(total_pressure_Pa) or total_pressure_Pa <= 0.0:
    raise ValueError(f'total_pressure_Pa must be finite and positive; got {total_pressure_Pa}')
  if not isfinite(total_temperature_K) or total_temperature_K <= 0.0:
    raise ValueError(f'total_temperature_K must be finite and positive; got {total_temperature_K}')
  if not isfinite(specific_gas_constant_JpkgK) or specific_gas_constant_JpkgK <= 0.0:
    raise ValueError(
        f'specific_gas_constant_JpkgK must be finite and positive; got {specific_gas_constant_JpkgK}'
    )
  exponent = (gamma + 1.0) / (2.0 * (gamma - 1.0))
  return (
      mass_flow_rate_kgps
      / total_pressure_Pa
      * sqrt(total_temperature_K * specific_gas_constant_JpkgK / gamma)
      * ((gamma + 1.0) / 2.0)**exponent
  )
####


def calc_area_mach_ratio(mach: float, gamma: float) -> float:
  r"""Return ``A/A*`` for a positive Mach number."""

  _validate_gamma(gamma)
  if not isfinite(mach) or mach <= 0.0:
    raise ValueError(f'mach must be finite and positive; got {mach}')
  exponent = (gamma + 1.0) / (2.0 * (gamma - 1.0))
  factor = 2.0 / (gamma + 1.0) * (1.0 + (gamma - 1.0) * mach**2 / 2.0)
  return factor**exponent / mach
####


def solve_mach_from_area_ratio(
    area_ratio: float,
    gamma: float,
    branch: MachBranch = MachBranch.SUPERSONIC,
    *,
    rtol: float = 1.0e-10,
    atol: float = 1.0e-12,
    max_iter: int = 200,
) -> float:
  """Invert ``A/A*`` on an explicit subsonic or supersonic branch."""

  _validate_gamma(gamma)
  if not isfinite(area_ratio) or area_ratio < 1.0:
    raise ValueError(f'area_ratio must be finite and at least one; got {area_ratio}')
  if rtol <= 0.0 or atol <= 0.0 or max_iter < 1:
    raise ValueError('rtol, atol, and max_iter must be positive')
  branch = MachBranch(branch)
  if area_ratio == 1.0:
    return 1.0

  def residual(mach: float) -> float:
    return calc_area_mach_ratio(mach, gamma) - area_ratio
  ####

  if branch is MachBranch.SUBSONIC:
    lower = 1.0e-12
    upper = 1.0
    if residual(lower) < 0.0:
      raise ValueError('area_ratio is outside the supported subsonic bracket')
  else:
    lower = 1.0
    upper = 2.0
    for _ in range(max_iter):
      if residual(upper) >= 0.0:
        break
      upper *= 2.0
    else:
      raise ValueError(f'could not bracket supersonic Mach for area_ratio={area_ratio}')
  ####

  lower_residual = residual(lower)
  upper_residual = residual(upper)
  if lower_residual * upper_residual > 0.0:
    raise ValueError(f'area_ratio={area_ratio} is not bracketed on the {branch.value} branch')
  for _ in range(max_iter):
    midpoint = (lower + upper) / 2.0
    midpoint_residual = residual(midpoint)
    if abs(midpoint_residual) <= atol or abs(upper - lower) <= max(atol, rtol * abs(midpoint)):
      return midpoint
    if lower_residual * midpoint_residual <= 0.0:
      upper = midpoint
      upper_residual = midpoint_residual
    else:
      lower = midpoint
      lower_residual = midpoint_residual
  raise ValueError(f'could not converge Mach for area_ratio={area_ratio} after {max_iter} iterations')
####
