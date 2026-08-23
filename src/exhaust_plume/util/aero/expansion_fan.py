# -*- coding: utf-8 -*-
"""
Equations from Chapter 4: Oblique Shock & Expansion Waves

Modern Compressible Flow: With Historical Perspective 3rd Edition
- https://archive.org/details/5f-36b-7c-4ded-79bb-3e-90754d-0f-81682f-7a-68014be
- https://web.archive.org/web/20221006024847/https://icourse.club/uploads/files/5f36b7c4ded79bb3e90754d0f81682f7a68014be.pdf
- https://icourse.club/uploads/files/5f36b7c4ded79bb3e90754d0f81682f7a68014be.pdf
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from typing import List, Optional, TypeVar, Union

from numpy import arctan, deg2rad, inf, isclose, nan, ndarray, rad2deg, sqrt

from exhaust_plume.log.extra_log_levels import TRACE, VERBOSE
from exhaust_plume.log.log import getCleanLogger
from exhaust_plume.util.aero.constants import MAX_ITER_DEFAULT
from exhaust_plume.util.aero.flow_state import FlowState
from exhaust_plume.util.aero.isentropic_flow import calcIsentropicMachFromPressure, calcIsentropicTotalStaticDensityRatio, calcIsentropicTotalStaticPressureRatio, calcIsentropicTotalStaticTemperatureRatio
from exhaust_plume.util.numeric import ATOL_DEFAULT, RTOL_DEFAULT

__all__ = (
    'calcIsentropicPmPressure',
    'calcIsentropicPmPressureRatio',
    'calcIsentropicPmTemperature',
    'calcIsentropicPmTemperatureRatio',
    'calcPmDownstreamMach',
    'calcPmExpansionAngle',
    'calcPrandtlMeyerAngle',
)
log = getCleanLogger(__name__)

T = TypeVar('T', float, ndarray)


def calcPrandtlMeyerAngle(*, mach: float, gamma: Union[float, T]) -> T:
  r""" Prandtl-Meyer function
  Calculates, the angle Nu, in degrees

  Eqn. 4.44 Anderson Modern Compressible Flow 3rd Edition

  $ a = \sqrt{\frac{γ + 1}{γ -1}} $
  $ b = \sqrt{mach^2 - 1} $
  $ ν\left(mach\right) = a \atan\left( b / a \right) - \atan\left(b\right) $
  """
  a = sqrt((gamma + 1) / (gamma - 1))
  b = sqrt(mach**2 - 1)
  nu = a * arctan(b / a) - arctan(b)
  return rad2deg(nu)
####


def calcPmExpansionAngle(*, mach_upstream: float, mach_downstream: float, gamma: Union[float, T]) -> T:
  r""" Calculates the angle Theta from two mach numbers in PM flow (difference in nu)
  Eqn. 4.45 Anderson Modern Compressible Flow 3rd Edition

  $ θ(mach) = ν\left(Μ_2\right) - v\left(M_1\right) $
  """
  theta = calcPrandtlMeyerAngle(mach=mach_downstream, gamma=gamma) - calcPrandtlMeyerAngle(mach=mach_upstream, gamma=gamma)
  return theta
####


def calcPmDownstreamMach(*,
                         mach_initial: float,
                         nu: float,
                         gamma: float,
                         initial_nu: float = 0.,
                         tol: float = 1e-10,
                         rtol: float = RTOL_DEFAULT,
                         atol: float = ATOL_DEFAULT,
                         max_iter: int = MAX_ITER_DEFAULT,
                         max_mach_search_scale: float = 2.,
                         ) -> float:
  """  Calculates inverse of prandtl-meyer equation.
  Given a desired angle and start (lower than desired), this function calculates the mach.
  PM from Anderson Modern Compressible Flow 3rd Edition
  """
  nu_desired = nu
  if nu_desired <= initial_nu:
    raise ValueError(f'Decreasing angle, expected an increase. Got Desired:{nu} [deg] - Start:{initial_nu} [deg] <= 0.')
  ####
  nu_inf = calcPrandtlMeyerAngle(mach=inf, gamma=gamma)
  if nu_desired > nu_inf:
    log.warning(f'Desired nu:{nu_desired} is not attainable. It is greater than mach=∞ nu={nu_inf}. Returning inf')
    return inf
  ####
  max_iter = max(1, max_iter)
  # Search upwards first for high mach
  mach_high = mach_initial * max_mach_search_scale
  num_high_iter = 0
  for num_high_iter in range(max_iter):
    nu = calcPrandtlMeyerAngle(mach=mach_high, gamma=gamma)
    if nu_desired <= nu:
      break
    ####
    mach_high *= max_mach_search_scale
  ####
  mach_low = 0.
  mach = mach_initial
  nu = initial_nu
  num_refine_iter = 0
  for num_refine_iter in range(max_iter):
    if isclose(nu_desired, nu, rtol=rtol, atol=atol):
      break
    ####
    mach = (mach_low + mach_high) / 2.
    nu = calcPrandtlMeyerAngle(mach=mach, gamma=gamma)
    if nu_desired < nu:
      mach_high = mach
    else:
      mach_low = mach
    ####
  ####
  log.log(TRACE, f'Calculated PM^-1(ν={nu:g}, γ) = mach:{mach:g} in {num_high_iter} upper mach search and {num_refine_iter} refinement iterations')
  if not isclose(nu_desired, nu, rtol=rtol, atol=atol):
    raise ValueError(f'Unable to calculate Prandtl-Meyer mach number given initial_mach:{mach_initial}, desired angle:{nu}, start_angle:{initial_nu}, within the tolerance:{tol} and max iterations:{max_iter}')
  ####
  return mach
####


def calcIsentropicPmTemperatureRatio(*, M1: T, M2: T, gamma: Union[float, T]) -> T:
  r""" Isentropic T
  Recognizing that the expansion is isentropic, and hence that T, and p, are constant through the wave,
  Eqs. (3.28) and (3.30) yield

  $ \frac{T_1}{T_2} = \frac{1 + \frac{γ-1}{2} M_2^2}{1 + \frac{γ-1}{2} M_1^2} $

  $ \frac{T_2}{T_1} = \frac{1 + \frac{γ-1}{2} M_1^2}{1 + \frac{γ-1}{2} M_2^2} $
  """
  T2_div_T1 = (
      calcIsentropicTotalStaticTemperatureRatio(mach=M1, gamma=gamma) /
      calcIsentropicTotalStaticTemperatureRatio(mach=M2, gamma=gamma)
  )
  return T2_div_T1
####


def calcIsentropicPmTemperature(*, M1: T, M2: T, static_temperature1: float, gamma: Union[float, T]) -> T:
  r""" Isentropic T
  Recognizing that the expansion is isentropic, and hence that T, and p, are constant through the wave,
  Eqs. (3.28) and (3.30) yield

  $ \frac{T_1}{T_2} = \frac{1 + \frac{γ-1}{2} M_2^2}{1 + \frac{γ-1}{2} M_1^2} $

  $ \frac{T_2}{T_1} = \frac{1 + \frac{γ-1}{2} M_1^2}{1 + \frac{γ-1}{2} M_2^2} $
  """
  T2_div_T1 = calcIsentropicPmTemperatureRatio(M1=M1, M2=M2, gamma=gamma)
  T2 = static_temperature1 * T2_div_T1
  return T2
####


def calcIsentropicPmPressureRatio(*, M1: T, M2: T, gamma: Union[float, T]) -> T:
  r""" Isentropic Pressure
  Recognizing that the expansion is isentropic, and hence that T, and p, are constant through the wave,
  Eqs. (3.28) and (3.30) yield

  $ \frac{p_1}{p_2} = \left[\frac{1 + \frac{γ-1}{2} M_2^2}{1 + \frac{γ-1}{2} M_1^2}\right]^{γ/\left(γ-1\right)} $

  $ \frac{p_2}{p_1} = \left[\frac{1 + \frac{γ-1}{2} M_1^2}{1 + \frac{γ-1}{2} M_2^2}\right]^{γ/\left(γ-1\right)} $
  """
  p2_div_p1 = (
      calcIsentropicTotalStaticPressureRatio(mach=M1, gamma=gamma) /
      calcIsentropicTotalStaticPressureRatio(mach=M2, gamma=gamma)
  )
  return p2_div_p1
####


def calcIsentropicPmPressure(*, M1: T, M2: T, static_pressure1: float, gamma: Union[float, T]) -> T:
  r""" Isentropic Pressure
  Recognizing that the expansion is isentropic, and hence that T, and p, are constant through the wave,
  Eqs. (3.28) and (3.30) yield

  $ \frac{p_1}{p_2} = \left[\frac{1 + \frac{γ-1}{2} M_2^2}{1 + \frac{γ-1}{2} M_1^2}\right]^{γ/\left(γ-1\right)} $

  $ \frac{p_2}{p_1} = \left[\frac{1 + \frac{γ-1}{2} M_1^2}{1 + \frac{γ-1}{2} M_2^2}\right]^{γ/\left(γ-1\right)} $
  """
  p2_div_p1 = calcIsentropicPmPressureRatio(M1=M1, M2=M2, gamma=gamma)
  p2 = p2_div_p1 * static_pressure1
  return p2
####


def calcIsentropicPmDensityRatio(*, M1: T, M2: T, gamma: Union[float, T]) -> T:
  r""" Isentropic Density
  Recognizing that the expansion is isentropic, and hence that T, and p, are constant through the wave,
  """
  rho2_div_rho1 = (
      calcIsentropicTotalStaticDensityRatio(mach=M1, gamma=gamma) /
      calcIsentropicTotalStaticDensityRatio(mach=M2, gamma=gamma)
  )
  return rho2_div_rho1
####


def calcIsentropicPmDensity(*, M1: T, M2: T, static_density1: float, gamma: Union[float, T]) -> T:
  r""" Isentropic Density
  Recognizing that the expansion is isentropic, and hence that T, and p, are constant through the wave,
  """
  rho2_div_rho1 = calcIsentropicPmDensityRatio(M1=M1, M2=M2, gamma=gamma)
  rho2 = rho2_div_rho1 * static_density1
  return rho2
####


@dataclass(frozen=True)
class ExpansionFanState(FlowState):
  turn_deg: float  # degrees, theta
  upstream_mach_line_deg: float  # mu_1; mu_1 + theta = location of upstream mach line

  def __post_init__(self) -> None:
    super().__post_init__()
  ####

  @cached_property
  def turn_rad(self) -> float:
    return deg2rad(self.turn_deg)
  ####

  @cached_property
  def upstream_mach_line_rad(self) -> float:
    return deg2rad(self.upstream_mach_line_deg)
  ####

  @classmethod
  def fromTurnedUpstreamState(cls, upstream: FlowState,
                              turn_deg: float,
                              nu_start: Optional[float] = None,
                              rtol: float = RTOL_DEFAULT, atol: float = ATOL_DEFAULT,
                              max_iter: int = MAX_ITER_DEFAULT,
                              ) -> ExpansionFanState:
    if nu_start is None:
      nu_start = calcPrandtlMeyerAngle(mach=upstream.mach, gamma=upstream.gamma)
    ####
    mach = calcPmDownstreamMach(
        mach_initial=upstream.mach,
        nu=nu_start + turn_deg,
        initial_nu=nu_start,
        gamma=upstream.gamma,
        rtol=rtol, atol=atol,
        max_iter=max_iter,
    )
    # EF are isentropic
    out = ExpansionFanState(
        mach=mach,
        turn_deg=turn_deg,
        gamma=upstream.gamma,
        upstream_mach_line_deg=upstream.mach_line_deg,
        static_pressure=calcIsentropicPmPressure(M1=upstream.mach, M2=mach, gamma=upstream.gamma, static_pressure1=upstream.static_pressure, ),
        static_temperature=calcIsentropicPmTemperature(M1=upstream.mach, M2=mach, gamma=upstream.gamma, static_temperature1=upstream.static_temperature, ),
        static_density=calcIsentropicPmDensity(M1=upstream.mach, M2=mach, gamma=upstream.gamma, static_density1=upstream.static_density, ),
    )
    return out
  ####

  @classmethod
  def fromUpstreamStateToEqualizedPressureState(cls, upstream: FlowState,
                                                downstream_static_pressure: float,
                                                num_fan_lines: int = 1,
                                                rtol: float = RTOL_DEFAULT, atol: float = ATOL_DEFAULT,
                                                max_iter: int = MAX_ITER_DEFAULT) -> List[ExpansionFanState]:
    if upstream.static_pressure < downstream_static_pressure:
      raise ValueError(f'Cannot calculate expansion fan state because downstream pressure:{downstream_static_pressure:g} is greater than current pressure{upstream.static_pressure:g}.'
                       f' Expansion fan decreases pressure')
    ####
    if num_fan_lines < 1:
      raise ValueError(f'Number of lines must be greater than or equal to 1. Got:{num_fan_lines}')
    ####
    max_iter = max(1, max_iter)
    final_mach_downstream = calcIsentropicMachFromPressure(
        static_pressure=downstream_static_pressure,
        total_pressure=upstream.total_pressure,
        gamma=upstream.gamma,
    )
    total_turn_deg = calcPmExpansionAngle(
        mach_upstream=upstream.mach,
        mach_downstream=final_mach_downstream,
        gamma=upstream.gamma,
    )
    turn_deg = total_turn_deg / num_fan_lines
    fans: List[ExpansionFanState] = [
        # first state is to prime the loop, will be removed afterward
        ExpansionFanState(
            mach=upstream.mach,
            gamma=upstream.gamma,
            turn_deg=nan,
            upstream_mach_line_deg=upstream.mach_line_deg,
            static_pressure=upstream.static_pressure,
            static_temperature=upstream.static_temperature,
            static_density=upstream.static_density,
        ),
    ]
    nu_start = calcPrandtlMeyerAngle(mach=upstream.mach, gamma=upstream.gamma)
    for idx in range(num_fan_lines - 1):
      fans.append(ExpansionFanState.fromTurnedUpstreamState(
          upstream=fans[-1],
          nu_start=nu_start,
          turn_deg=turn_deg,
      ))
      nu_start += turn_deg
    ####
    # Discard initial fan, keep middle fans, last fan will be adjusted to get equal pressure
    fans = fans[1:]

    min_turn_deg = 0.
    max_turn_deg = min(360., 2. * turn_deg)
    turn_deg = (max_turn_deg + min_turn_deg) / 2.
    last_fan = fans[-1] if len(fans) > 0 else upstream
    # Start over expanded to make sure fan starts below the threshold pressure
    eq_pressure_fan = ExpansionFanState.fromTurnedUpstreamState(
        upstream=last_fan,
        nu_start=nu_start,
        turn_deg=turn_deg,
    )
    # calculating the Expansion fan requires inverting PM eq. which requires a tolerance
    # if the inner loop tolerance is not decreased the outer loop will not be able to converge to the
    # required and will cycle above / below the solution
    final_ef_rtol = rtol * 1e-1
    final_ef_atol = atol * 1e-1
    tolerance_reduction_factor = .5
    num_iter = 0
    prev_delta_p = nan
    for num_iter in range(max_iter):
      if isclose(eq_pressure_fan.static_pressure, downstream_static_pressure, rtol=rtol, atol=atol):
        break
      ####
      # log.debug(f'{num_iter}: {eq_pressure_fan.static_pressure - downstream_static_pressure:#8.4g}; {turn_deg}∈[{min_turn_deg},{max_turn_deg}]')
      delta_p = eq_pressure_fan.static_pressure - downstream_static_pressure
      if prev_delta_p == delta_p:
        # tolerance is not small enough
        log.log(
            VERBOSE,
            f'Reducing tolerance by a meet downstream pressure. Last fan Pressure:{eq_pressure_fan.static_pressure:g}, Downstream Pressure:{downstream_static_pressure:g} '
            f'(Δ {delta_p:g}) (prev Δ {prev_delta_p:g}).'
            f' Rtol:{final_ef_rtol:g} Atol:{final_ef_atol:g} Turn:∈{turn_deg:g}ε[{min_turn_deg:g},{max_turn_deg:g}] (Δ{max_turn_deg - min_turn_deg}). ',
        )
        final_ef_rtol *= tolerance_reduction_factor
        final_ef_atol *= tolerance_reduction_factor
      else:
        if eq_pressure_fan.static_pressure < downstream_static_pressure:
          # Decrease turn to increase pressure
          max_turn_deg = turn_deg
        else:
          min_turn_deg = turn_deg
        ####
        turn_deg = (min_turn_deg + max_turn_deg) / 2.
        prev_delta_p = delta_p
      ####
      eq_pressure_fan = ExpansionFanState.fromTurnedUpstreamState(
          upstream=last_fan,
          nu_start=nu_start,
          turn_deg=turn_deg,
          rtol=final_ef_rtol,
          atol=final_ef_atol,
      )
    ####
    if not isclose(eq_pressure_fan.static_pressure, downstream_static_pressure, rtol=rtol, atol=atol):
      log.error(f'Unable to determine expansion fan that gets desired pressure. Desired pressure:{downstream_static_pressure}. Got:{eq_pressure_fan.static_pressure} after {num_iter} iterations.')
    ####
    log.log(VERBOSE, f'Calculated {num_fan_lines} Expansion fan lines to equalized pressure in {num_iter} iterations. Upstream state:{upstream}.'
                     f' Final pressure:{eq_pressure_fan.static_pressure:g}. Desired pressure:{downstream_static_pressure:g}.'
                     f' (Δ {eq_pressure_fan.static_pressure - downstream_static_pressure:g}) '
            )
    fans.append(eq_pressure_fan)
    return fans
  ####

  def __hash__(self) -> int:
    return super().__hash__()
  ####
####
