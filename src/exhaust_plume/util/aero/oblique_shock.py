# -*- coding: utf-8 -*-
"""
@author: nathan.tendick

Equations from Chapter 4: Oblique Shock & Expansion Waves

Modern Compressible Flow: With Historical Perspective 3rd Edition
- https://archive.org/details/5f-36b-7c-4ded-79bb-3e-90754d-0f-81682f-7a-68014be
- https://web.archive.org/web/20221006024847/https://icourse.club/uploads/files/5f36b7c4ded79bb3e90754d0f81682f7a68014be.pdf
- https://icourse.club/uploads/files/5f36b7c4ded79bb3e90754d0f81682f7a68014be.pdf
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass
from functools import cached_property
from typing import Optional, TypeVar, Union, cast

from numpy import arccos, arctan, cos, deg2rad, isclose, ndarray, pi, rad2deg, sin, sqrt, tan

from exhaust_plume.log.extra_log_levels import VERBOSE
from exhaust_plume.log.log import getCleanLogger
from exhaust_plume.util.aero.constants import MAX_ITER_DEFAULT
from exhaust_plume.util.aero.flow_state import FlowState
from exhaust_plume.util.aero.normal_shock import calcNormalShockMach, calcNormalShockStaticDensity, calcNormalShockStaticPressure, calcNormalShockStaticTemperature
from exhaust_plume.util.numeric import ATOL_DEFAULT, RTOL_DEFAULT

__all__ = (
    'calcShockObliqueAngle',
    'calcWeakShockObliqueAngle',
    'calcStrongShockObliqueAngle',
    'ObliqueShockState',
)
###########################################
log = getCleanLogger(__name__)

OBLIQUE_DELTA_WEAK = 1.
OBLIQUE_DELTA_STRONG = 0.

T = TypeVar('T', float, ndarray)


def calcShockObliqueAngle(*, theta_deg: T, mach: T, gamma: Union[float, T], delta: float) -> T:
  r""" Calculates Oblique Shock angle

  Theta, input, is the angle in degrees between the horizontal and the ramp
  Beta, output, is the angle in degrees between the horizontal and the tilted shock waves (for θ=0 no wedge, β=90')
  Delta,
   when delta=0., then it is the strong chock wave
   when delta=1., then it is the weak shock wave

  Eqn. 4.19, 4.20, 4.21 Anderson Modern Compressible Flow 3rd Edition"

  (4.20) $ λ = \sqrt{\left[\left( mach^2-1 \right)^2 - 3\left(1 + \frac{γ-1}{2}mach^2\right)\left(1 + \frac{γ+1}{2}Μ^2\right)\tan^2\left(\theta\right) \right] }$

  (4.21) $ χ = \frac{1}{λ^3} \left( \left(mach^2-1\right)^3 - 9\left(1 +\frac{γ-1}{2}mach^2\right) \left(1+\frac{γ-1}{2}mach^2 + \frac{γ+1}{4}mach^4\right)\tan^2\left(θ\right) \right) $

  (4.19) $ \tan\left(β\right) = \frac{mach^2 - 1 + 2λ\cos\left[\left(4πδ+\acos\left(χ\right)\right)/3\right]}{3\left(1+\frac{γ-1}{2}mach^2\right)\tan\left(θ\right)} $
  """
  M2 = mach**2
  theta_rad = deg2rad(theta_deg)
  gm12_M2 = ((gamma - 1) / 2) * M2
  gp12_M2 = ((gamma + 1) / 2) * M2
  M2_m1 = M2 - 1
  tan_th = tan(theta_rad)

  with warnings.catch_warnings():
    warnings.filterwarnings('ignore', category=RuntimeWarning)
    lamb = sqrt(M2_m1**2 - 3 * (1 + gm12_M2) * (1 + gp12_M2) * tan_th**2)
    chi = (M2_m1**3 - 9 * (1 + gm12_M2) * (1 + gm12_M2 + gp12_M2 / 2. * M2) * tan_th**2) / (lamb**3.)

    tanb = (M2_m1 + 2 * lamb * cos((4 * pi * delta + arccos(chi)) / 3)) / (3 * (1 + gm12_M2) * tan_th)
    beta = rad2deg(arctan(tanb))
  ##
  # Check for exact values
  shp = beta.shape
  beta = beta.ravel()
  beta[theta_rad.ravel() == 0.] = 90.
  beta = beta.reshape(shp)
  if isinstance(mach, float):
    beta = float(beta)
  ##
  return cast(T, beta)
##


def calcWeakShockObliqueAngle(*, theta_deg: T, mach: T, gamma: Union[float, T]) -> T:
  r""" Weak Oblique Shock
  Eqn. 4.19, 4.20, 4.21 Anderson Modern Compressible Flow 3rd Edition
  """
  return calcShockObliqueAngle(theta_deg=theta_deg, mach=mach, gamma=gamma, delta=OBLIQUE_DELTA_WEAK)
##


def calcStrongShockObliqueAngle(*, theta_deg: T, mach: T, gamma: Union[float, T]) -> T:
  r""" Strong Oblique Shock
  Eqn. 4.19, 4.20, 4.21 Anderson Modern Compressible Flow 3rd Edition
  """
  return calcShockObliqueAngle(theta_deg=theta_deg, mach=mach, gamma=gamma, delta=OBLIQUE_DELTA_STRONG)
##


@dataclass(frozen=True)
class ObliqueShockState(FlowState):
  oblique_angle_deg: float  # degrees
  shock_angle_deg: float  # degrees

  def __post_init__(self) -> None:
    super().__post_init__()
  ##

  @cached_property
  def oblique_angle_rad(self) -> float:
    return deg2rad(self.oblique_angle_deg)
  ##

  @cached_property
  def shock_angle_rad(self) -> float:
    return deg2rad(self.shock_angle_deg)
  ##

  @classmethod
  def fromUpstreamState(cls, upstream: FlowState, oblique_angle_deg: float, shock_angle_deg: Optional[float] = None, ) -> ObliqueShockState:
    r""" Oblique Shock mach properties
    Eqn. 3.30, 4.7, 4.10, 4.12 Anderson Modern Compressible Flow 3rd Edition

    Given the upstream mach, oblique angle (theta_deg), and shock angle (beta)

    Returns the downstream state:

    (4.7) $ M_{n_1} = M_1 \sin\left(β\right) $ the normal upstream mach

    M_downstream normal, Static Temperature, Static Pressure are calculated from Normal Shock Relations

    (4.12) $ M_2 = \frac{M_{n_2}}{\sin\left(β-θ\right)} $
    """
    gamma = upstream.gamma
    if shock_angle_deg is None:
      shock_angle_deg = calcWeakShockObliqueAngle(theta_deg=oblique_angle_deg, mach=upstream.mach, gamma=upstream.gamma, )
    ##
    mach_normal_up = upstream.mach * sin(deg2rad(shock_angle_deg))  # Eqn 4.7
    mach_normal_downstream = calcNormalShockMach(mach=mach_normal_up, gamma=gamma)
    mach_down = mach_normal_downstream / sin(deg2rad(shock_angle_deg - oblique_angle_deg))  # Eqn 4.12
    out = ObliqueShockState(
        gamma=gamma,
        oblique_angle_deg=oblique_angle_deg,
        shock_angle_deg=shock_angle_deg,
        mach=mach_down,
        static_pressure=calcNormalShockStaticPressure(mach=mach_normal_up, gamma=gamma, static_pressure=upstream.static_pressure),
        static_temperature=calcNormalShockStaticTemperature(mach=mach_normal_up, gamma=gamma, static_temperature=upstream.static_temperature),
        static_density=calcNormalShockStaticDensity(mach=mach_normal_up, gamma=gamma, static_density=upstream.static_density),
    )
    return out
  ##

  @classmethod
  def fromUpstreamStateToEqualizedPressureState(cls, upstream: FlowState, downstream_static_pressure: float,
                                                rtol: float = RTOL_DEFAULT, atol: float = ATOL_DEFAULT,
                                                max_iter: int = MAX_ITER_DEFAULT) -> ObliqueShockState:
    if upstream.static_pressure > downstream_static_pressure:
      raise ValueError(f'Cannot calculate oblique shock state because downstream pressure:{downstream_static_pressure:g} is lower than current pressure{upstream.static_pressure:g}. Oblique shocks increase pressure')
    ##
    max_iter = max(1, max_iter)
    beta_low_deg = 0.
    beta_high_deg = 90.

    theta_deg = 0.  # start at zero
    beta_deg = (beta_low_deg + beta_high_deg) / 2.
    init_downstream = cls.fromUpstreamState(upstream=upstream, oblique_angle_deg=theta_deg, shock_angle_deg=beta_deg)
    num_beta_iter = 0
    for num_beta_iter in range(max_iter):
      if isclose(init_downstream.static_pressure, downstream_static_pressure, rtol=rtol, atol=atol):
        break
      ##
      if init_downstream.static_pressure > downstream_static_pressure:
        # Pressure is too high, so increase angle
        beta_high_deg = beta_deg
      else:
        beta_low_deg = beta_deg
      ##
      beta_deg = (beta_low_deg + beta_high_deg) / 2.
      init_downstream = cls.fromUpstreamState(upstream=upstream, oblique_angle_deg=theta_deg, shock_angle_deg=beta_deg)
    ##
    if not isclose(init_downstream.static_pressure, downstream_static_pressure, rtol=rtol, atol=atol):
      log.error(f'Unable to determine oblique shock angle that gets desired pressure. Desired pressure:{downstream_static_pressure}. Got:{init_downstream.static_pressure} after {num_beta_iter} iterations.')
    ##
    # Now adjust the oblique angle so that the oblique weak shock aligns with the beta calculated from the first part

    theta_low_deg = 0.
    theta_high_deg = init_downstream.shock_angle_deg
    desired_beta_deg = init_downstream.shock_angle_deg
    theta_deg = (theta_low_deg + theta_high_deg) / 2.
    weak_beta_deg = calcWeakShockObliqueAngle(theta_deg=theta_deg, mach=upstream.mach, gamma=upstream.gamma)
    num_theta_iter = 0
    for num_theta_iter in range(max_iter):
      if isclose(weak_beta_deg, desired_beta_deg, rtol=rtol, atol=atol):
        break
      ##
      if weak_beta_deg < desired_beta_deg:
        # calculated beta too low, so increase lower theta range
        theta_low_deg = theta_deg
      else:
        theta_high_deg = theta_deg
      ##
      theta_deg = (theta_low_deg + theta_high_deg) / 2.
      weak_beta_deg = calcWeakShockObliqueAngle(theta_deg=theta_deg, mach=upstream.mach, gamma=upstream.gamma)
      num_theta_iter += 1
    ##
    if not isclose(weak_beta_deg, desired_beta_deg, rtol=rtol, atol=atol):
      log.error(f'Unable to determine oblique angle that gets desired shock angle. Desired beta:{desired_beta_deg}. Got:{weak_beta_deg} after {num_theta_iter} iterations.')
    ##

    # Now with correct beta and theta, calculate final downstream state
    final_downstream = cls.fromUpstreamState(
        upstream=upstream,
        shock_angle_deg=init_downstream.shock_angle_deg,
        oblique_angle_deg=theta_deg,
    )
    log.log(VERBOSE, f'Calculated Oblique shock at pressure in {num_beta_iter} β and {num_theta_iter} θ iterations. Upstream state:{upstream} Desired pressure:{downstream_static_pressure}.')
    return final_downstream
  ##

  def __hash__(self) -> int:
    return super().__hash__()
  ##

##
