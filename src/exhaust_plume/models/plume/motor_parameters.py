# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, fields
from typing import TypeVar, Union, cast

from numpy import isclose, isfinite, ndarray, pi, sqrt

from exhaust_plume.log.log import getCleanLogger
from exhaust_plume.util.aero.constants import MAX_ITER_DEFAULT
from exhaust_plume.util.aero.ideal_gas import calcDensityFromSpecificVolume, calcIdealGasSpecificVolumeFromPressureSpecificWork, calcIdealGasSpecificWorkFromMolarMassTemperature, calcSpecificGasConstant
from exhaust_plume.util.aero.isentropic_flow import calcIsentropicStaticDensity, calcIsentropicStaticPressure, calcIsentropicStaticTemperature
from exhaust_plume.util.atmosphere.constants import MOLAR_MASS_DRY_AIR_kg
from exhaust_plume.util.cached_property import cached_property
from exhaust_plume.util.numpy_util import ATOL_DEFAULT, RTOL_DEFAULT

__all__ = (
    'calcAreaThroatGivenMassFlowRateTotalTemperaturePressure',
    'calcMachGivenAreaRatioGamma',
    'EngineParameters',
)
###########################################
log = getCleanLogger(__name__)

T = TypeVar('T', float, ndarray)


def calcMachGivenAreaRatioGamma(area_exit: float, area_throat: float,
                                gamma: float,
                                rtol: float = RTOL_DEFAULT, atol: float = ATOL_DEFAULT, max_iter: int = MAX_ITER_DEFAULT,
                                ) -> float:
  r""" Assumes areas have equal units
   area_ratio = (Area exit)/(Area throat)

  https://www.grc.nasa.gov/www/k-12/airplane/rktthsum.html

  $ \left(\frac{A_e}{A^*}\right)^2 = \left(\frac{γ+1}{2}\right)^{\frac{γ+1}{γ-1}}\frac{\left(1+\frac{γ-1}{2}M^2\right)^{\frac{γ+1}{γ-1}}}{M^2} $

  $ a = \frac{γ+1}{2} $
  $ b = \frac{γ-1}{2} $
  $ c = \frac{a}{b} = \frac{γ+1}{γ-1} $
  $ d = a^{-c} $

  $ \left(\frac{A_e}{A^*}\right)^2 = d \frac{\left(1+b M^2\right)^{c}}{M^2} $
  $ 0 = -\left(\frac{A_e}{A^*}\right)^2 M^2 +  d \left(1+b M^2\right)^{c} $
  """
  area_ratio = area_exit / area_throat
  if area_ratio < 1 or not isfinite(area_ratio):
    raise ValueError(f'Expected area ratio (exit/throat) to be greater than 1. Got:{area_ratio}')
  ##
  max_iter = max(1, int(max_iter))
  Ae_Astar_2 = area_ratio**2
  a = (gamma + 1) / 2.
  b = (gamma - 1) / 2.
  c = (gamma + 1) / (gamma - 1)  # a/b
  d = a**(-c)

  def eqn(M2: float) -> float:
    return -Ae_Astar_2 * M2 + d * (1 + b * M2)**c
  ##
  # if (Ae/A*) > 1, then M2_min can be guaranteed to be 1.
  # d*(1+b)**c = a**(-c) * (a)**c = 1.
  # -(Ae/A*)**2 * (1) + 1
  # Which is only negative if the area reatio is greater than 1.
  M2_min = 1.
  # Find an upper bound
  M2_max = 1.
  eqn_result = 0.
  for find_max_iter in range(max_iter):
    eqn_result = eqn(M2_max)
    if eqn_result == 0.:
      return sqrt(M2_max)
    elif eqn_result > 0:
      break
    ##
    M2_max *= 2.
  ##
  if eqn_result <= 0.:
    raise ValueError(f'Could not find maximum possible mach given area ratio:{area_ratio} and gamma:{gamma} in {max_iter} iterations')
  ##
  M2_est = (M2_min + M2_max) / 2.
  for find_mach_iter in range(max_iter):
    if isclose(M2_min, M2_max, rtol=rtol, atol=atol):
      break
    ##
    eqn_result = eqn(M2_est)
    if eqn_result > 0:
      M2_max = M2_est
    else:
      M2_min = M2_est
    ##
    M2_est = (M2_min + M2_max) / 2.
  ##
  if not isclose(M2_min, M2_max):
    raise ValueError(f'Could not converge on a mach solution given area ratio:{area_ratio} and gamma:{gamma} in {max_iter} iterations. M**2 min:{M2_min} M**2 max:{M2_max}')
  ##
  return sqrt(M2_est)
##


def calcAreaThroatGivenMassFlowRateTotalTemperaturePressure(mdot_kgps: T,
                                                            total_pressure_Pa: T,
                                                            total_temperature_K: T,
                                                            gamma: Union[float, T],
                                                            molar_mass_kg: Union[float, T]) -> T:
  r""" https://www.grc.nasa.gov/www/k-12/airplane/rktthsum.html

  $ \dot{m}^2 = \frac{\left(A^* p_t\right)^2}{T_t}\frac{γ}{R} \left(\frac{γ+1}{2}\right)^{-\frac{γ+1}{γ-1}} $
  $ A^* = \frac{\dot{m}}{p_t}\sqrt{\frac{T_t R}{γ}}\left(\frac{γ+1}{2}\right)^{\frac{γ+1}{γ-1}} $
  """
  R_specific_m2ps2K = calcSpecificGasConstant(molar_mass_kg=molar_mass_kg)
  Astar = (mdot_kgps / total_pressure_Pa) * sqrt(total_temperature_K * R_specific_m2ps2K / gamma) * ((gamma + 1) / 2.)**((gamma + 1) / (gamma - 1))
  return cast(T, Astar)
##


@dataclass(frozen=True)
class EngineParameters:
  mass_flow_rate_kgps: float
  exit_radius_m: float
  total_pressure_Pa: float
  total_temperature_K: float
  gamma: float
  molar_mass_kg: float

  def __post_init__(self) -> None:
    for f in fields(self):
      v = getattr(self, f.name)
      if v is None or v <= 0 or not isfinite(v):
        raise ValueError(f'Expected `{f.name}` to be positive. Got:{v}')
      ##
    ##
    if self.gamma <= 1.:
      raise ValueError(f'Expected `gamma` to be greater than 1. Got:{self.gamma}')
    ##
  ##

  @cached_property
  def exit_area_m2(self) -> float:
    return (pi * self.exit_radius_m**2.)
  ##

  @cached_property
  def throat_area_m2(self) -> float:
    throat_area = calcAreaThroatGivenMassFlowRateTotalTemperaturePressure(
        mdot_kgps=self.mass_flow_rate_kgps,
        total_pressure_Pa=self.total_pressure_Pa,
        total_temperature_K=self.total_temperature_K,
        molar_mass_kg=self.molar_mass_kg,
        gamma=self.gamma,
    )
    return throat_area
  ##

  @cached_property
  def exit_mach(self) -> float:
    exit_mach = calcMachGivenAreaRatioGamma(
        area_throat=self.throat_area_m2,
        area_exit=self.exit_area_m2,
        gamma=self.gamma,
    )
    return exit_mach
  ##

  @cached_property
  def total_density_kgps(self) -> float:
    total_density = calcDensityFromSpecificVolume(
        specific_volume_m3pkg=calcIdealGasSpecificVolumeFromPressureSpecificWork(
            pressure_Pa=self.total_pressure_Pa,
            specific_work_Jpkg=calcIdealGasSpecificWorkFromMolarMassTemperature(
                molar_mass_kg=MOLAR_MASS_DRY_AIR_kg,
                temperature_K=self.total_temperature_K,
            )
        )
    )
    return total_density
  ##

  @cached_property
  def static_pressure_Pa(self) -> float:
    static_pressure = calcIsentropicStaticPressure(
        mach=self.exit_mach,
        total_pressure=self.total_pressure_Pa,
        gamma=self.gamma,
    )
    return static_pressure
  ##

  @cached_property
  def static_temperature_K(self) -> float:
    static_temperature = calcIsentropicStaticTemperature(
        mach=self.exit_mach,
        total_temperature=self.total_temperature_K,
        gamma=self.gamma,
    )
    return static_temperature
  ##

  @cached_property
  def static_density_kpgs(self) -> float:
    static_density = calcIsentropicStaticDensity(
        mach=self.exit_mach,
        total_density=self.total_density_kgps,
        gamma=self.gamma,
    )
    return static_density
  ##

##
