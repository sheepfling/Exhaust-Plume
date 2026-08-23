# -*- coding: utf-8 -*-
r"""
These functions calculate the state of a gas after a Normal Shock assuming a calorically perfect gas with a given γ

Modern Compressible Flow: With Historical Perspective 3rd Edition
- https://archive.org/details/5f-36b-7c-4ded-79bb-3e-90754d-0f-81682f-7a-68014be
- https://web.archive.org/web/20221006024847/https://icourse.club/uploads/files/5f36b7c4ded79bb3e90754d0f81682f7a68014be.pdf
- https://icourse.club/uploads/files/5f36b7c4ded79bb3e90754d0f81682f7a68014be.pdf
"""
from __future__ import annotations

from typing import TypeVar, Union, cast

from numpy import ndarray, sqrt

from exhaust_plume.log.log import getCleanLogger

__all__ = (
    'calcNormalShockMach',
    'calcNormalShockStaticDensity',
    'calcNormalShockStaticDensityRatio',
    'calcNormalShockStaticPressure',
    'calcNormalShockStaticPressureRatio',
    'calcNormalShockStaticTemperature',
    'calcNormalShockStaticTemperatureRatio',
)
log = getCleanLogger(__name__)

T = TypeVar('T', float, ndarray)


def calcNormalShockMach(*, mach: T, gamma: Union[float, T]) -> T:
  r""" Normal Shock
  Eqn. 3.51 Anderson Modern Compressible Flow 3rd Edition
  $ M_2^2 = \frac{1+\left[\left(γ-1\right)/2\right]M_1^2}{γ M_1^2-\left(γ-1\right)/2} $
  """
  a = (gamma - 1) / 2.
  M2 = mach**2.
  mach_downstream2 = (1 + a * M2) / (gamma * M2 - a)
  mach_downstream = sqrt(mach_downstream2)
  return cast(T, mach_downstream)
####


def calcNormalShockStaticDensityRatio(*, mach: T, gamma: Union[float, T]) -> T:
  r""" Normal Shock static density ratio
  Returns P2 / P1
  Eqn. 3.53 Anderson Modern Compressible Flow 3rd Edition
  $ \frac{ρ_2}{ρ_1} = \frac{\left(γ+1\right) M_1^2}{2 + \left(γ-1\right)M_1^2} $
  """
  M2 = mach**2
  rho2_div_rho1 = ((gamma + 1) * M2) / (2 + (gamma - 1) * M2)
  return rho2_div_rho1
####


def calcNormalShockStaticPressureRatio(*, mach: T, gamma: Union[float, T]) -> T:
  r""" Normal Shock static pressure ratio
  Returns P2 / P1
  Eqn. 3.57 Anderson Modern Compressible Flow 3rd Edition
  $ \frac{p_2}{p_1} = 1 + \frac{2γ}{γ+1}\left(M_1^2 - 1\right) $
  """
  P2_div_P1 = 1 + ((2 * gamma) / (gamma + 1)) * (mach**2 - 1)
  return P2_div_P1
####


def calcNormalShockStaticTemperatureRatio(*, mach: T, gamma: Union[float, T]) -> T:
  r""" Normal Shock static temperature ratio
  Eqn. 3.59 Anderson Modern Compressible Flow 3rd Edition
  $ \frac{T_2}{T_1} = \frac{h_2}{h_1} = \left[1 + \frac{2γ}{γ+1}\left(M_1^2 -1\right)\right] \left[\frac{2 + \left(γ-1\right)M_1^2}{\left(\gamma+1\right)M_1^2}\right] $
  """
  P2_div_P1 = calcNormalShockStaticPressureRatio(mach=mach, gamma=gamma)
  rho2_div_rho1 = calcNormalShockStaticDensityRatio(mach=mach, gamma=gamma)
  T2_div_T1 = P2_div_P1 / rho2_div_rho1
  return T2_div_T1
####


def calcNormalShockStaticPressure(*, mach: T, static_pressure: T, gamma: Union[float, T]) -> T:
  r""" Normal Shock static pressure ratio
  Eqn. 3.57 Anderson Modern Compressible Flow 3rd Edition
  $ \frac{p_2}{p_1} = 1+ \frac{2γ}{γ+1}\left(M_1^2 - 1\right) $
  """
  P2_div_P1 = calcNormalShockStaticPressureRatio(mach=mach, gamma=gamma)
  P2 = P2_div_P1 * static_pressure
  return P2
####


def calcNormalShockStaticTemperature(*, mach: T, static_temperature: T, gamma: Union[float, T]) -> T:
  r""" Normal Shock static temperature ratio
  Eqn. 3.59 Anderson Modern Compressible Flow 3rd Edition
  $ \frac{T_2}{T_1} = \frac{h_2}{h_1} = \left[1 + \frac{2γ}{γ+1}\left(M_1^2 -1\right)\right] \left[\frac{2 + \left(γ-1\right)M_1^2}{\left(\gamma+1\right)M_1^2}\right] $
  """
  T2_div_T1 = calcNormalShockStaticTemperatureRatio(mach=mach, gamma=gamma)
  T2 = static_temperature * T2_div_T1
  return T2
####


def calcNormalShockStaticDensity(*, mach: T, static_density: T, gamma: Union[float, T]) -> T:
  r""" Normal Shock static Density ratio
  Eqn. 3.59 Anderson Modern Compressible Flow 3rd Edition

  $ ρ_2 = ρ_1 \cdot \left(\frac{ρ_2}{ρ_1}\right) $
  """
  rho2_div_rho1 = calcNormalShockStaticDensityRatio(mach=mach, gamma=gamma)
  rho2 = static_density * rho2_div_rho1
  return rho2
####
