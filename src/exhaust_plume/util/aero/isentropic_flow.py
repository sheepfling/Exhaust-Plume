# -*- coding: utf-8 -*-
r"""
These functions calculate the total and static properties of a gas assuming isentropic expansion/compression

The Total
- pressure, $ p_0 $ and
- temperature, $ T_0 $
- density, $ρ_0 $ (rho)
are the properties of the gas if the flow was isentropically slowed to $ V = 0 $

The actual properties of the gas are called the static values. They do not have the 0 subscript

Modern Compressible Flow: With Historical Perspective 3rd Edition
- https://archive.org/details/5f-36b-7c-4ded-79bb-3e-90754d-0f-81682f-7a-68014be
- https://web.archive.org/web/20221006024847/https://icourse.club/uploads/files/5f36b7c4ded79bb3e90754d0f81682f7a68014be.pdf
- https://icourse.club/uploads/files/5f36b7c4ded79bb3e90754d0f81682f7a68014be.pdf
"""
from __future__ import annotations

import warnings
from typing import TypeVar, Union, cast

from numpy import asarray, ndarray, sqrt

from exhaust_plume.log.log import getCleanLogger

__all__ = (
    'calcIsentropicTotalStaticPressureRatio',
    'calcIsentropicStaticPressure',
    'calcIsentropicTotalPressure',
    'calcIsentropicMachFromPressure',
    'calcIsentropicTotalStaticTemperatureRatio',
    'calcIsentropicStaticTemperature',
    'calcIsentropicTotalTemperature',
    'calcIsentropicMachFromTemperature',
    'calcIsentropicTotalStaticDensityRatio',
    'calcIsentropicStaticDensity',
    'calcIsentropicTotalDensity',
    'calcIsentropicMachFromDensity',
)
log = getCleanLogger(__name__)

T = TypeVar('T', float, ndarray)


def calcIsentropicTotalStaticTemperatureRatio(*, mach: T, gamma: Union[float, T]) -> T:
  r""" Provides the static temperature of the nozzle
  Eqn. 3.28 Anderson Modern Compressible Flow 3rd Edition

  $ \frac{T_0}{T} = 1 + \frac{γ - 1}{2}mach^2 $
  $ T = T_0 / \left(\frac{T_0}{T}\right) $
  """
  Ttotal_div_Tstatic = (1 + ((gamma - 1) / 2) * mach**2)
  return Ttotal_div_Tstatic
####


def calcIsentropicStaticTemperature(*, mach: T, total_temperature: T, gamma: Union[float, T]) -> T:
  r""" Provides the static temperature of the nozzle
  Eqn. 3.28 Anderson Modern Compressible Flow 3rd Edition

  $ \frac{T_0}{T} = 1 + \frac{γ - 1}{2}mach^2 $
  $ T = T_0 / \left(\frac{T_0}{T}\right) $
  """
  Ttotal_div_Tstatic = calcIsentropicTotalStaticTemperatureRatio(mach=mach, gamma=gamma)
  static_temperature = total_temperature / Ttotal_div_Tstatic
  return static_temperature
####


def calcIsentropicTotalTemperature(*, mach: T, static_temperature: T, gamma: Union[float, T]) -> T:
  r""" Provides the static temperature of the nozzle
  Eqn. 3.28 Anderson Modern Compressible Flow 3rd Edition

  $ \frac{T_0}{T} = 1 + \frac{γ - 1}{2}mach^2 $
  $ T_0 = T \cdot \left(\frac{T_0}{T}\right) $
  """
  Ttotal_div_Tstatic = asarray(calcIsentropicTotalStaticTemperatureRatio(mach=mach, gamma=gamma))
  static_temperature_arr = asarray(static_temperature)
  static0_lgc = (static_temperature_arr == 0.).ravel()
  if any(static0_lgc):
    shp = Ttotal_div_Tstatic.shape
    Ttotal_div_Tstatic = Ttotal_div_Tstatic.ravel()
    Ttotal_div_Tstatic[static0_lgc] = 0.
    Ttotal_div_Tstatic = Ttotal_div_Tstatic.reshape(shp)
  ####
  total_temperature = static_temperature_arr * Ttotal_div_Tstatic
  if isinstance(mach, float):
    return float(total_temperature)
  ####
  return total_temperature
####


def calcIsentropicMachFromTemperature(*, static_temperature: T, total_temperature: T, gamma: Union[float, T]) -> T:
  r""" Rearranged Isentropic T
  Eqn. 3.28 Anderson Modern Compressible Flow 3rd Edition

  Solve Eqn 3.28 for mach
  $ \frac{T_0}{T} = 1 + \frac{γ - 1}{2}mach^2 $
  """
  total_temperature_arr = asarray(total_temperature)
  with warnings.catch_warnings():
    warnings.filterwarnings('ignore', category=RuntimeWarning)
    mach2 = ((total_temperature_arr / static_temperature) - 1) * (2. / (gamma - 1))
  ####
  mach = sqrt(mach2)
  total0_lgc = (total_temperature_arr == 0.).ravel()
  if any(total0_lgc):
    shp = mach.shape
    mach = mach.ravel()
    mach[total0_lgc] = 0.
    mach = mach.reshape(shp)
  ####
  #
  if isinstance(total_temperature_arr, float):
    return cast(T, float(mach))
  ####
  return cast(T, mach)
####



def calcIsentropicTotalStaticDensityRatio(*, mach: T, gamma: Union[float, T]) -> T:
  r""" Provides the static density of the nozzle
  Eqn. 3.31 Anderson Modern Compressible Flow 3rd Edition

  $ \frac{ρ_0}{ρ} = \left(1 + \frac{γ-1}{2} M^2\right)^{1/\left(γ-1\right)} $
  """
  rhoTotal_div_rhoStatic = calcIsentropicTotalStaticTemperatureRatio(mach=mach, gamma=gamma)**(1. / (gamma - 1))
  return cast(T, rhoTotal_div_rhoStatic)
####


def calcIsentropicStaticDensity(*, mach: T, total_density: T, gamma: Union[float, T]) -> T:
  r""" Provides the static density of the nozzle
  Eqn. 3.31 Anderson Modern Compressible Flow 3rd Edition

  $ \frac{ρ_0}{ρ} = \left(1 + \frac{γ-1}{2} M^2\right)^{1/\left(γ-1\right)} $
  $ ρ = ρ_0 \cdot \left(\frac{ρ_0}{ρ}\right) $
  """
  rhoTotal_div_rhoStatic = calcIsentropicTotalStaticDensityRatio(mach=mach, gamma=gamma)
  static_density = total_density / rhoTotal_div_rhoStatic
  return static_density
####


def calcIsentropicTotalDensity(*, mach: T, static_density: T, gamma: Union[float, T]) -> T:
  r""" Provides the static density of the nozzle
  Eqn. 3.31 Anderson Modern Compressible Flow 3rd Edition

  $ \frac{ρ_0}{ρ} = \left(1 + \frac{γ-1}{2} M^2\right)^{1/\left(γ-1\right)} $
  $ ρ_0 = ρ / \left(\frac{ρ_0}{ρ}\right) $
  """
  rhoTotal_div_rhoStatic = asarray(calcIsentropicTotalStaticDensityRatio(mach=mach, gamma=gamma))
  static_density_arr = asarray(static_density)
  static0_lgc = (static_density_arr == 0.).ravel()
  if any(static0_lgc):
    shp = rhoTotal_div_rhoStatic.shape
    rhoTotal_div_rhoStatic = rhoTotal_div_rhoStatic.ravel()
    rhoTotal_div_rhoStatic[static0_lgc] = 0.
    rhoTotal_div_rhoStatic = rhoTotal_div_rhoStatic.reshape(shp)
  ####
  total_density = static_density_arr * rhoTotal_div_rhoStatic
  if isinstance(mach, float):
    return cast(T, float(total_density))
  ####
  return cast(T, total_density)
####


def calcIsentropicMachFromDensity(*, static_density: T, total_density: T, gamma: Union[float, T]) -> T:
  r""" Rearranged Isentropic Density
  Eqn. 3.31 Anderson Modern Compressible Flow 3rd Edition

  Solve Eqn 3.31 for T
  $ \frac{ρ_0}{ρ} = \left(1 + \frac{γ-1}{2} M^2\right)^{1/\left(γ-1\right)} $
  """
  total_density_arr = asarray(total_density)
  with warnings.catch_warnings():
    warnings.filterwarnings('ignore', category=RuntimeWarning)
    r = (total_density_arr / static_density)**((gamma - 1))
  ####
  mach = sqrt(2. * (r - 1) / (gamma - 1))
  total0_lgc = (total_density_arr == 0.).ravel()
  if any(total0_lgc):
    shp = mach.shape
    mach = mach.ravel()
    mach[total0_lgc] = 0.
    mach = mach.reshape(shp)
  ####
  if isinstance(static_density, float):
    return float(mach)
  ####
  return mach
####



def calcIsentropicTotalStaticPressureRatio(*, mach: T, gamma: Union[float, T]) -> T:
  r""" Isentropic T Ratio
  Eqn. 3.30 Anderson Modern Compressible Flow 3rd Edition

  $ \frac{p_0}{p} = \left(1 + \frac{γ - 1}{2} mach^2\right)^{γ / \left(γ - 1\right)} $
  """
  pTotal_div_pStatic = (1 + ((gamma - 1) / 2) * mach**2)**((gamma) / (gamma - 1))  # Pa
  return cast(T, pTotal_div_pStatic)
####


def calcIsentropicStaticPressure(*, mach: T, total_pressure: T, gamma: Union[float, T]) -> T:
  r""" Isentropic Static T
  Eqn. 3.30 Anderson Modern Compressible Flow 3rd Edition

  $ p_0 = \frac{p_0}{p} \cdot p $
  """
  pTotal_div_pStatic = calcIsentropicTotalStaticPressureRatio(mach=mach, gamma=gamma)
  p_static = total_pressure / pTotal_div_pStatic
  return p_static
####


def calcIsentropicTotalPressure(*, mach: T, static_pressure: T, gamma: Union[float, T]) -> T:
  r""" Isentropic Total T
  Eqn. 3.30 Anderson Modern Compressible Flow 3rd Edition

  $ p = p_0 / \left(\frac{p_0}{p}\right) $
  """
  pTotal_div_pStatic = asarray(calcIsentropicTotalStaticPressureRatio(mach=mach, gamma=gamma))
  static_pressure_arr = asarray(static_pressure)
  static0_lgc = (static_pressure_arr == 0.).ravel()
  if any(static0_lgc):
    shp = pTotal_div_pStatic.shape
    pTotal_div_pStatic = pTotal_div_pStatic.ravel()
    pTotal_div_pStatic[static0_lgc] = 0.
    pTotal_div_pStatic = pTotal_div_pStatic.reshape(shp)
  ####
  p_total = static_pressure_arr * pTotal_div_pStatic
  if isinstance(mach, float):
    return float(p_total)
  ####
  return p_total
####


def calcIsentropicMachFromPressure(*, static_pressure: T, total_pressure: T, gamma: Union[float, T]) -> T:
  r""" Rearranged Isentropic P
  Eqn. 3.30 Anderson Modern Compressible Flow 3rd Edition

  Solve Eqn 3.30 for T, where $r = \left(\frac{p_0}{p}\right)^{\left(γ-1\right) / γ} $
  ```
  from sympy import latex, solve, symbols
  r,γ,mach = symbols('r,γ,mach',positive=True)
  soln = solve(r-(1+(γ-1)/2*(mach**2)),mach)
  latex(abs(soln[0])))
  ```
  $ mach = \sqrt{\frac{2}{γ-1}\left(\left(\frac{p_0}{p}\right)^{\left(γ-1\right)/γ}\right)} $
  """
  # Total T over Static T
  # Total pressure = P0
  # Static pressure  = P
  total_pressure_arr = asarray(total_pressure)
  with warnings.catch_warnings():
    warnings.filterwarnings('ignore', category=RuntimeWarning)
    r = (total_pressure_arr / static_pressure)**((gamma - 1) / gamma)
  ####
  mach2 = 2. * (r - 1) / (gamma - 1)
  mach = sqrt(mach2)
  total0_lgc = (total_pressure_arr == 0.).ravel()
  if any(total0_lgc):
    shp = mach.shape
    mach = mach.ravel()
    mach[total0_lgc] = 0.
    mach = mach.reshape(shp)
  ####
  #
  if isinstance(static_pressure, float):
    return float(mach)
  ####
  return mach
####
