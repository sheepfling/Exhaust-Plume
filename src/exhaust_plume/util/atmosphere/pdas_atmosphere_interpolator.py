"""US Standard Atmosphere 1976 lookup used by the plume study runner.

The runner already has altitude in hand, so this module intentionally exposes an
altitude-only interface. Coordinate systems and vehicle-state abstractions do not
belong in the plume model.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass, replace
from functools import cached_property
from typing import Sequence, TypeVar, Union, overload

import numpy as np
from numpy import ndarray

from exhaust_plume.util.atmosphere.constants import ADIABATIC_INDEX_DRY_AIR_NTP
from exhaust_plume.util.atmosphere.speed_of_sound import calculateSpeedOfSoundInAir
from exhaust_plume.util.physical_constants import PASCAL_PER_ATM

__all__ = (
    'PdasAtmosphereScalarState',
    'PdasAtmosphereArrayState',
    'PdasAtmosphericInterpolator',
    'calculateAtmosphereStateFromGeopotentialAltitude',
)

FloatOrArray = TypeVar('FloatOrArray', float, ndarray)

_HEIGHT_TABLE_KM: Sequence[float] = (0.0, 11.0, 20.0, 32.0, 47.0, 51.0, 71.0, 84.852)
_PRESSURE_TABLE: Sequence[float] = (1.0, 2.2336110e-1, 5.4032950e-2, 8.5666784e-3, 1.0945601e-3, 6.6063531e-4, 3.9046834e-5, 3.68501e-6)
_TEMPERATURE_TABLE_K: Sequence[float] = (288.15, 216.65, 216.65, 228.65, 270.65, 270.65, 214.65, 186.946)
_TEMPERATURE_GRADIENT_TABLE_K_PER_KM: Sequence[float] = (-6.5, 0.0, 1.0, 2.8, 0.0, -2.8, -2.0, 0.0)

_GMR_K_PER_KM = 34.163195
_TEMPERATURE_SEA_LEVEL_K = 288.15
_DENSITY_SEA_LEVEL_KG_PER_M3 = 1.225
_PRESSURE_SEA_LEVEL_PA = PASCAL_PER_ATM


@dataclass(frozen=True)
class PdasAtmosphereScalarState:
  """Atmospheric properties at one geopotential altitude."""

  is_valid: bool
  geopotential_altitude_m: float
  density_kgpm3: float
  temperature_K: float
  pressure_Pa: float

  def getIsValid(self) -> bool:
    return self.is_valid
  ####

  def getDensity_kgpm3(self) -> float:
    return self.density_kgpm3
  ####

  def getTemperature_K(self) -> float:
    return self.temperature_K
  ####

  def getPressure_Pa(self) -> float:
    return self.pressure_Pa
  ####

  @cached_property
  def speed_of_sound_mps(self) -> float:
    return float(calculateSpeedOfSoundInAir(
        pressure_Pa=self.pressure_Pa,
        density_kgpm3=self.density_kgpm3,
        adiabatic_index=ADIABATIC_INDEX_DRY_AIR_NTP,
    ))
  ####

  def replace(self, **changes: object) -> 'PdasAtmosphereScalarState':
    return replace(self, **changes)
  ####
####


@dataclass(frozen=True)
class PdasAtmosphereArrayState:
  """Atmospheric properties evaluated over an altitude array."""

  is_valid: ndarray
  geopotential_altitude_m: ndarray
  density_kgpm3: ndarray
  temperature_K: ndarray
  pressure_Pa: ndarray

  def getIsValid(self) -> ndarray:
    return self.is_valid
  ####

  def getDensity_kgpm3(self) -> ndarray:
    return self.density_kgpm3
  ####

  def getTemperature_K(self) -> ndarray:
    return self.temperature_K
  ####

  def getPressure_Pa(self) -> ndarray:
    return self.pressure_Pa
  ####

  @cached_property
  def speed_of_sound_mps(self) -> ndarray:
    return calculateSpeedOfSoundInAir(
        pressure_Pa=self.pressure_Pa,
        density_kgpm3=self.density_kgpm3,
        adiabatic_index=ADIABATIC_INDEX_DRY_AIR_NTP,
    )
  ####
####


class PdasAtmosphericInterpolator:
  """Piecewise standard-atmosphere interpolator in geopotential altitude."""

  def __init__(
      self,
      height_table_km: Sequence[float] = _HEIGHT_TABLE_KM,
      pressures_unitless: Sequence[float] = _PRESSURE_TABLE,
      temperatures_K: Sequence[float] = _TEMPERATURE_TABLE_K,
      temperature_gradients_K_per_km: Sequence[float] = _TEMPERATURE_GRADIENT_TABLE_K_PER_KM,
  ) -> None:
    lengths = {len(height_table_km), len(pressures_unitless), len(temperatures_K), len(temperature_gradients_K_per_km)}
    if len(lengths) != 1:
      raise ValueError('Atmosphere lookup tables must have equal lengths.')
    ####
    if len(height_table_km) < 2:
      raise ValueError('Atmosphere lookup requires at least two layers.')
    ####
    self._heights_km = tuple(float(value) for value in height_table_km)
    self._pressures = tuple(float(value) for value in pressures_unitless)
    self._temperatures_K = tuple(float(value) for value in temperatures_K)
    self._gradients = tuple(float(value) for value in temperature_gradients_K_per_km)
    self._min_height_m = self._heights_km[0] * 1.0e3
    self._max_height_m = self._heights_km[-1] * 1.0e3
  ####

  @overload
  def calculateAtmosphereStateFromGeopotentialAltitude(self, geopotential_alt_m: float) -> PdasAtmosphereScalarState:
    ...

  @overload
  def calculateAtmosphereStateFromGeopotentialAltitude(self, geopotential_alt_m: ndarray) -> PdasAtmosphereArrayState:
    ...

  def calculateAtmosphereStateFromGeopotentialAltitude(self, geopotential_alt_m: FloatOrArray) -> Union[PdasAtmosphereScalarState, PdasAtmosphereArrayState]:
    values = np.asarray(geopotential_alt_m, dtype=float)
    if values.ndim == 0:
      return self._calculate_scalar(float(values))
    ####
    states = [self._calculate_scalar(float(value)) for value in values.ravel()]
    shape = values.shape
    return PdasAtmosphereArrayState(
        is_valid=np.asarray([state.is_valid for state in states], dtype=bool).reshape(shape),
        geopotential_altitude_m=np.asarray([state.geopotential_altitude_m for state in states]).reshape(shape),
        density_kgpm3=np.asarray([state.density_kgpm3 for state in states]).reshape(shape),
        temperature_K=np.asarray([state.temperature_K for state in states]).reshape(shape),
        pressure_Pa=np.asarray([state.pressure_Pa for state in states]).reshape(shape),
    )
  ####

  def _calculate_scalar(self, altitude_m: float) -> PdasAtmosphereScalarState:
    if altitude_m < self._min_height_m:
      return self._calculate_scalar(self._min_height_m).replace(is_valid=False, geopotential_altitude_m=altitude_m)
    ####
    if altitude_m > self._max_height_m:
      return self._calculate_scalar(self._max_height_m).replace(is_valid=False, geopotential_altitude_m=altitude_m)
    ####

    altitude_km = altitude_m * 1.0e-3
    layer = min(bisect_right(self._heights_km, altitude_km) - 1, len(self._heights_km) - 1)
    base_temperature_K = self._temperatures_K[layer]
    gradient_K_per_km = self._gradients[layer]
    delta_height_km = altitude_km - self._heights_km[layer]
    local_temperature_K = base_temperature_K + gradient_K_per_km * delta_height_km
    theta = local_temperature_K / self._temperatures_K[0]

    pressure_ratio = self._pressures[layer]
    if gradient_K_per_km == 0.0:
      pressure_ratio *= np.exp(-_GMR_K_PER_KM * delta_height_km / base_temperature_K)
    else:
      pressure_ratio *= (base_temperature_K / local_temperature_K) ** (_GMR_K_PER_KM / gradient_K_per_km)
    ####
    density_ratio = pressure_ratio / theta
    return PdasAtmosphereScalarState(
        is_valid=bool(np.isfinite(local_temperature_K) and np.isfinite(pressure_ratio)),
        geopotential_altitude_m=altitude_m,
        density_kgpm3=float(density_ratio * _DENSITY_SEA_LEVEL_KG_PER_M3),
        temperature_K=float(theta * _TEMPERATURE_SEA_LEVEL_K),
        pressure_Pa=float(pressure_ratio * _PRESSURE_SEA_LEVEL_PA),
    )
  ####
####


_DEFAULT_INTERPOLATOR = PdasAtmosphericInterpolator()


@overload
def calculateAtmosphereStateFromGeopotentialAltitude(geopotential_altitude_m: float) -> PdasAtmosphereScalarState:
  ...


@overload
def calculateAtmosphereStateFromGeopotentialAltitude(geopotential_altitude_m: ndarray) -> PdasAtmosphereArrayState:
  ...


def calculateAtmosphereStateFromGeopotentialAltitude(geopotential_altitude_m: FloatOrArray) -> Union[PdasAtmosphereScalarState, PdasAtmosphereArrayState]:
  return _DEFAULT_INTERPOLATOR.calculateAtmosphereStateFromGeopotentialAltitude(geopotential_alt_m=geopotential_altitude_m)
####
