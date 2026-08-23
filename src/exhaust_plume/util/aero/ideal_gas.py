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

from typing import TypeVar, Union, cast

from numpy import log as ln, ndarray

from exhaust_plume.log.log import getCleanLogger
from exhaust_plume.util.physical_constants import R_GAS_CONSTANT

__all__ = (
    'calcIdealGasWorkFromPressureVolume',
    'calcIdealGasVolumeFromPressureWork',
    'calcIdealGasPressureFromVolumeWork',
    'calcIdealGasWorkFromMolsTemperature',
    'calcIdealGasMolFromTemperatureWork',
    'calcIdealGasTemperatureFromMolWork',
    'calcIdealGasSpecificWorkFromPressureSpecificVolume',
    'calcIdealGasPressureFromSpecificVolumeSpecificWork',
    'calcIdealGasSpecificVolumeFromPressureSpecificWork',
    'calcIdealGasSpecificWorkFromMolarMassTemperature',
    'calcIdealGasMolarMassFromTemperatureSpecificWork',
    'calcIdealGasTemperatureFromMolarMassSpecificWork',
    'calcDensityFromSpecificVolume',
    'calcSpecificVolumeFromDensity',
)
log = getCleanLogger(__name__)

T = TypeVar('T', float, ndarray, Union[float, ndarray])


def calcIdealGasWorkFromPressureVolume(pressure_Pa: T, volume_m3: T) -> T:
  """ Returns Gas Work in J
  P * V
  """
  return pressure_Pa * volume_m3
####


def calcIdealGasPressureFromVolumeWork(volume_m3: T, work_J: T) -> T:
  """
  P * V = W
  P = W / V
  """
  pressure_Pa = work_J / volume_m3
  return pressure_Pa
####


def calcIdealGasVolumeFromPressureWork(pressure_Pa: T, work_J: T) -> T:
  """
  P * V = W
  V = W / P
  """
  volume_m3 = work_J / pressure_Pa
  return volume_m3
####


def calcIdealGasWorkFromMolsTemperature(n_mol: T, temperature_K: T) -> T:
  """ Returns Gas Work in J
  n * R * T
  """
  return n_mol * R_GAS_CONSTANT * temperature_K
####


def calcIdealGasMolFromTemperatureWork(temperature_K: T, work_J: T) -> T:
  """ Returns number of mols of gas
  W = n * R * T
  n = W / (R * T)
  """
  n_mol = work_J / (R_GAS_CONSTANT * temperature_K)
  return n_mol
####


def calcIdealGasTemperatureFromMolWork(n_mol: T, work_J: T) -> T:
  """ Returns Gas Work in J
  W = n * R * T
  T = W / (n * T)
  """
  temperature_K = work_J / (R_GAS_CONSTANT * n_mol)
  return temperature_K
####



def calcIdealGasSpecificWorkFromPressureSpecificVolume(pressure_Pa: T, specific_volume_m3pkg: T) -> T:
  """ Returns Gas Specific Work in J/kg
  P * (V/m)
  """
  return pressure_Pa * specific_volume_m3pkg
####


def calcIdealGasPressureFromSpecificVolumeSpecificWork(specific_volume_m3pkg: T, specific_work_Jpkg: T) -> T:
  """
  P * (V/m) = (W/m)
  P = (W/m) / (V/m)
  """
  pressure_Pa = specific_work_Jpkg / specific_volume_m3pkg
  return pressure_Pa
####


def calcIdealGasSpecificVolumeFromPressureSpecificWork(pressure_Pa: T, specific_work_Jpkg: T) -> T:
  """
  P * (V/m) = (W/m)
  (V/m) = (W/m) / P
  """
  specific_volume_m3pkg = specific_work_Jpkg / pressure_Pa
  return specific_volume_m3pkg
####


def calcIdealGasSpecificWorkFromMolarMassTemperature(molar_mass_kg: T, temperature_K: T) -> T:
  """ Returns Gas Specific Work in J/kg
  (1/M) * R * T
  """
  return (1. / molar_mass_kg) * R_GAS_CONSTANT * temperature_K
####


def calcIdealGasMolarMassFromTemperatureSpecificWork(temperature_K: T, specific_work_Jpkg: T) -> T:
  """ Returns molar mass in kg of gas
  (W/m) = (1/M) * R * T
  (1/M) = (W/m) / (R * T)
  """
  inv_molar_mass_kg = specific_work_Jpkg / (R_GAS_CONSTANT * temperature_K)
  molar_mass_kg = 1. / inv_molar_mass_kg
  return molar_mass_kg
####


def calcIdealGasTemperatureFromMolarMassSpecificWork(molar_mass_kg: T, specific_work_Jpkg: T) -> T:
  """ Returns Gas Specific Work in J/kg
  (W/m) = (1/M) * R * T
  T = (W/m) / ((1/M) * T)
  T = (W/m) * M / T
  """
  temperature_K = specific_work_Jpkg * molar_mass_kg / (R_GAS_CONSTANT)
  return temperature_K
####



def calcDensityFromSpecificVolume(specific_volume_m3pkg: T) -> T:
  return 1. / specific_volume_m3pkg
####


def calcSpecificVolumeFromDensity(density_kgpm3: T) -> T:
  return 1. / density_kgpm3
####



def calcSpecificGasConstant(molar_mass_kg: T) -> T:
  """ Returns specfic gas constant in
  Joules / (kilogram * Kelvin) = (meters^2)/(seconds^2 * Kelvin)
  """
  specific_gas_R = (R_GAS_CONSTANT / molar_mass_kg)
  return specific_gas_R
####


def calcSpecificHeatPressure(gamma: T, molar_mass_kg: T) -> T:
  """ Returns specific heat at constant pressure c_p (J/(kg K))
  Assuming a calorically / thermally perfect gas

  Eq 1.22 $ c_p = \frac{γ}{γ-1}(R/M) $
  """
  specific_gas_R = calcSpecificGasConstant(molar_mass_kg=molar_mass_kg)
  cp = (gamma / (gamma - 1)) * specific_gas_R
  return cp
####


def calcSpecificHeatVolume(gamma: T, molar_mass_kg: T) -> T:
  """ Returns specific heat at constant volume c_v (J/(kg K))
  Assuming a calorically / thermally perfect gas

  Eq 1.23 $ c_v = \frac{1}{γ-1}(R/M) $
  """
  specific_gas_R = calcSpecificGasConstant(molar_mass_kg=molar_mass_kg)
  cv = (1. / (gamma - 1)) * specific_gas_R
  return cv
####



def calcIdealGasSpecificEntropyChange(
        temperature_ratio: T, pressure_ratio: T,
        gamma: float, molar_mass_kg: float) -> T:
  """
  Assumes calorically perfect gas & that heat addition/subtraction is reversible
  """
  specific_gas_R = calcSpecificGasConstant(molar_mass_kg=molar_mass_kg)
  cp = calcSpecificHeatPressure(gamma=gamma, molar_mass_kg=molar_mass_kg)
  delta_s = cp * ln(temperature_ratio) - specific_gas_R * ln(pressure_ratio)
  return cast(T, delta_s)
####
