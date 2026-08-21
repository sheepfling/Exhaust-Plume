# -*- coding: utf-8 -*-
""" Simplistic Atmospheric interpolator, assuming Spherical earth
Adapted from Public Domain Aeronautical Software (PDAS) - Atmospheric Interpolator
- https://www.pdas.com/atmostables.html
-- Archive: https://web.archive.org/web/20220508223203/https://www.pdas.com/atmostables.html
- US Standard 1976 atmosphere: https://archive.org/details/us_standard_atmosphere_1976
-- Alternate: https://drive.google.com/file/d/0B2UKsBO-ZMVgWG9mWEJGMlFacDQ/view?resourcekey=0-jjKqejg9Rxw-__VYiXe6Ag
- Geopotential & Geometric Altitud: https://www.pdas.com/hydro.pdf
-- Archive: https://web.archive.org/web/20220710000533/https://www.pdas.com/hydro.pdf
- Python version of Public domain atmosphere: https://www.pdas.com/programs/atmos.py
-- Archive: https://web.archive.org/web/20220702040124/https://www.pdas.com/programs/atmos.py
-- Archive: https://archive.is/4co5d
- Revised Tables of Airspeed, Altitude, and Mach Number in SI units: https://www.pdas.com/refs/sp3082.pdf
-- Archive: https://web.archive.org/web/20220504183058/https://www.pdas.com/refs/sp3082.pdf
- https://www.pdas.com/refs/tm104237.pdf
-- Archive: https://web.archive.org/web/20220504183058/https://www.pdas.com/refs/tm104237.pdf
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Optional, Sequence, TypeVar, Union, overload

from numpy import array, exp, ndarray

from exhaust_plume.earth.earth_model import EarthModel
from exhaust_plume.earth.gravity import calculateGeopotentialAltitudeFromECEF
from exhaust_plume.earth.spherical_earth_constants import SPHERICAL_EARTH_RADIUS_m
from exhaust_plume.log.log import getCleanLogger
from exhaust_plume.util.atmosphere.atmosphere_interpolator_interface import AtmosphereArrayStateInterface, AtmosphereScalarStateInterface, AtmosphericInterpolatorInterface
from exhaust_plume.util.atmosphere.speed_of_sound import calculateSpeedOfSoundInAir
from exhaust_plume.util.cached_property import cached_property
from exhaust_plume.util.numpy_util import makeReadOnly
from exhaust_plume.util.physical_constants import PASCAL_PER_ATM
from exhaust_plume.util.position_interface import PositionEcefArrayInterface, PositionEcefGenericInterface, PositionEcefScalarInterface
from exhaust_plume.util.sort_util import binarySearchSortedArray

__all__ = (
    'PdasAtmosphereScalarState',
    'PdasAtmosphereArrayState',
    'PdasAtmosphericInterpolator',
    'calculateAtmosphereStateFromGeopotentialAltitude',
)

##############################################
log = getCleanLogger(__name__)

FloatXorNdarray = TypeVar('FloatXorNdarray', float, ndarray)

# https://web.archive.org/web/20220702040124/https://www.pdas.com/programs/atmos.py
_DEFAULT_EARTH_RADIUS_m = SPHERICAL_EARTH_RADIUS_m  # radius of the Earth (km)
_DEFAULT_GMR_Kpkm = 34.163195  # hydrostatic constant Kelvin / km
_DEFAULT_TEMPERATURE_SEA_K = 288.15  # Temperature at sea level in K
_DEFAULT_RHO_SEA_kgpm3 = 1.225  # Density at sea level in kg/m^3
_DEFAULT_PRESSURE_SEA_Pa = 1. * PASCAL_PER_ATM  # Pressure at sea level in Pa

_HEIGHT_TABLE_km: Sequence[float] = (0.0, 11.0, 20.0, 32.0, 47.0, 51.0, 71.0, 84.852,)  # km
_PRESSURE_TABLE_unitless: Sequence[float] = (1.0, 2.2336110E-1, 5.4032950E-2, 8.5666784E-3, 1.0945601E-3, 6.6063531E-4, 3.9046834E-5, 3.68501E-6,)
_TEMPERATURE_TABLE_K: Sequence[float] = (288.15, 216.65, 216.65, 228.65, 270.65, 270.65, 214.65, 186.946,)
_TEMPERATURE_GRADIENT_TABLE_Kpkm: Sequence[float] = (-6.5, 0.0, 1.0, 2.8, 0, -2.8, -2.0, 0.0,)


@dataclass(frozen=True)
class PdasAtmosphereScalarState(AtmosphereScalarStateInterface):
  is_valid: bool
  geopotential_altitude_m: float
  density_kgpm3: float
  temperature_K: float
  pressure_Pa: float

  def getIsValid(self) -> bool:
    return self.is_valid
  ##

  def getDensity_kgpm3(self) -> float:
    return self.density_kgpm3
  ##

  def getTemperature_K(self) -> float:
    return self.temperature_K
  ##

  def getPressure_Pa(self) -> float:
    return self.pressure_Pa
  ##

  @cached_property
  def speed_of_sound_mps(self) -> float:
    return calculateSpeedOfSoundInAir(pressure_Pa=self.getPressure_Pa(), density_kgpm3=self.getDensity_kgpm3())
  ##

  def replace(self, *,
              is_valid: Optional[bool] = None,
              geopotential_altitude_m: Optional[float] = None,
              density_kgpm3: Optional[float] = None,
              temperature_K: Optional[float] = None,
              pressure_Pa: Optional[float] = None,
              ) -> PdasAtmosphereScalarState:
    out = PdasAtmosphereScalarState(
        is_valid=self.is_valid if is_valid is None else is_valid,
        geopotential_altitude_m=self.geopotential_altitude_m if geopotential_altitude_m is None else geopotential_altitude_m,
        density_kgpm3=self.density_kgpm3 if density_kgpm3 is None else density_kgpm3,
        temperature_K=self.temperature_K if temperature_K is None else temperature_K,
        pressure_Pa=self.pressure_Pa if pressure_Pa is None else pressure_Pa,
    )
    return out
  ##
##


@dataclass(frozen=True)
class PdasAtmosphereArrayState(AtmosphereArrayStateInterface):
  is_valid: ndarray
  geopotential_altitude_m: ndarray
  density_kgpm3: ndarray
  temperature_K: ndarray
  pressure_Pa: ndarray

  def __post_init__(self) -> None:
    for f in fields(self):
      v = getattr(self, f.name)
      if isinstance(v, ndarray):
        v.flags.writeable = False
      ##
    ##
  ##

  def getIsValid(self) -> ndarray:
    return self.is_valid
  ##

  def getDensity_kgpm3(self) -> ndarray:
    return self.density_kgpm3
  ##

  def getTemperature_K(self) -> ndarray:
    return self.temperature_K
  ##

  def getPressure_Pa(self) -> ndarray:
    return self.pressure_Pa
  ##

  @cached_property
  def speed_of_sound_mps(self) -> ndarray:
    out = makeReadOnly(calculateSpeedOfSoundInAir(pressure_Pa=self.getPressure_Pa(), density_kgpm3=self.getDensity_kgpm3()))
    return out
  ##

  def replace(self, *,
              is_valid: Optional[ndarray] = None,
              geopotential_altitude_m: Optional[ndarray] = None,
              density_kgpm3: Optional[ndarray] = None,
              temperature_K: Optional[ndarray] = None,
              pressure_Pa: Optional[ndarray] = None,
              ) -> PdasAtmosphereArrayState:
    out = PdasAtmosphereArrayState(
        is_valid=self.is_valid if is_valid is None else is_valid,
        geopotential_altitude_m=self.geopotential_altitude_m if geopotential_altitude_m is None else geopotential_altitude_m,
        density_kgpm3=self.density_kgpm3 if density_kgpm3 is None else density_kgpm3,
        temperature_K=self.temperature_K if temperature_K is None else temperature_K,
        pressure_Pa=self.pressure_Pa if pressure_Pa is None else pressure_Pa,
    )
    return out
  ##
##


class PdasAtmosphericInterpolator(AtmosphericInterpolatorInterface):
  """ Calculates Atmospheric state assuming a spherical earth. """

  def __init__(self,
               earth_model: EarthModel,
               earth_radius_m: float = SPHERICAL_EARTH_RADIUS_m,
               GMR_Kpkm: float = _DEFAULT_GMR_Kpkm,
               temperature_sealevel_K: float = _DEFAULT_TEMPERATURE_SEA_K,
               density_sealevel_kgpm3: float = _DEFAULT_RHO_SEA_kgpm3,
               pressure_sealevel_Pa: float = _DEFAULT_PRESSURE_SEA_Pa,
               height_table_km: Sequence[float] = _HEIGHT_TABLE_km,
               pressures_unitless: Sequence[float] = _PRESSURE_TABLE_unitless,
               temperatures_K: Sequence[float] = _TEMPERATURE_TABLE_K,
               temperature_gradients_Kpkm: Sequence[float] = _TEMPERATURE_GRADIENT_TABLE_Kpkm,
               ):
    """
    :param earth_model: determines how geopotential altitude is calculated.
    :param earth_radius_m: Earth radius for determining geopotential altitude
    :param GMR_Kpkm: hydrostatic constant Kelvin / km
                     = (gravity m/s^2) * (molecular weight of air kg/mol) / (R gas constant Joule-mol/K) = Kelvin/m
    :param temperature_sealevel_K: Temperature of atmosphere at sealevel in Kelvin
    :param density_sealevel_kgpm3:  Density of atmosphere at sealevel in kg/m^3
    :param pressure_sealevel_Pa:  Pressure of atmosphere at sealevel in Pa
    :param height_table_km: Geopotential height table in km
    :param pressures_unitless:  Pressure table in unitless units (1.0= 1 atm)
    :param temperatures_K: Temperature table in Kelvin
    :param temperature_gradients_Kpkm:  Temperature Gradient table in Kelvin/km
    """
    super().__init__()
    self.__earth_radius_m = earth_radius_m
    self.__GMR_Kpkm = GMR_Kpkm
    self.__temperature_sealevel_K = temperature_sealevel_K
    self.__density_sealevel_kgpm3 = density_sealevel_kgpm3
    self.__pressure_sealevel_Pa = pressure_sealevel_Pa
    self.__heights_km = tuple(float(x) for x in height_table_km)
    self.__pressures_unitless = tuple(float(x) for x in pressures_unitless)
    self.__temperatures_K = tuple(float(x) for x in temperatures_K)
    self.__temperature_gradients_Kpkm = tuple(float(x) for x in temperature_gradients_Kpkm)
    height_table_length = len(self.__heights_km)
    for table in (self.__temperatures_K, self.__temperature_gradients_Kpkm, self.__pressures_unitless,):
      if len(table) != height_table_length:
        raise ValueError(f'Unable to construct {type(self).__name__} not all input tables have same length. Expected {height_table_length}')
      ##
    ##
    if self.__temperatures_K[0] == 0:
      raise ValueError(f'Expected first entry in temperatures table to be non-zero. Got:{self.__temperatures_K[0]}')
    ##
    self.__earth_model = earth_model
    if self.__earth_model == EarthModel.Flat:
      log.debug(f'{type(self).__name__} is using earth model {self.__earth_model}', extra={'object': self})
    ##
    self.__min_height_m = min(self.__heights_km) * 1e3
    self.__max_height_m = max(self.__heights_km) * 1e3
    self.__min_height_state = self.calculateAtmosphereStateFromGeopotentialAltitude(geopotential_alt_m=self.__min_height_m).replace(is_valid=False)
    self.__max_height_state = self.calculateAtmosphereStateFromGeopotentialAltitude(geopotential_alt_m=self.__max_height_m).replace(is_valid=False)
  ##

  @overload
  def calculateState(self, position_ecef: PositionEcefScalarInterface) -> PdasAtmosphereScalarState:
    ...

  @overload
  def calculateState(self, position_ecef: PositionEcefArrayInterface) -> PdasAtmosphereArrayState:
    ...

  def calculateState(self, position_ecef: PositionEcefGenericInterface[FloatXorNdarray]) -> Union[PdasAtmosphereScalarState, PdasAtmosphereArrayState]:
    geopotential_alt_m = calculateGeopotentialAltitudeFromECEF(position_ecef=position_ecef, earth_model=self.__earth_model, spherical_earth_radius_m=self.__earth_radius_m)
    return self.calculateAtmosphereStateFromGeopotentialAltitude(geopotential_alt_m=geopotential_alt_m)
  ##

  @overload
  def calculateAtmosphereStateFromGeopotentialAltitude(self, geopotential_alt_m: float) -> PdasAtmosphereScalarState:
    ...

  @overload
  def calculateAtmosphereStateFromGeopotentialAltitude(self, geopotential_alt_m: ndarray) -> PdasAtmosphereArrayState:
    ...

  def calculateAtmosphereStateFromGeopotentialAltitude(self, geopotential_alt_m: FloatXorNdarray) -> Union[PdasAtmosphereScalarState, PdasAtmosphereArrayState]:
    if isinstance(geopotential_alt_m, float):
      return self._calculateAtmosphereStateFromGeopotentialAltitude(geopotential_alt_m=geopotential_alt_m)
    else:
      shape = geopotential_alt_m.shape
      out_states = [self._calculateAtmosphereStateFromGeopotentialAltitude(geopotential_alt_m=geop_alt) for geop_alt in geopotential_alt_m.ravel()]
      out = PdasAtmosphereArrayState(
          is_valid=array([x.is_valid for x in out_states], 'bool').reshape(shape),
          geopotential_altitude_m=array([x.geopotential_altitude_m for x in out_states]).reshape(shape),
          density_kgpm3=array([x.density_kgpm3 for x in out_states]).reshape(shape),
          temperature_K=array([x.temperature_K for x in out_states]).reshape(shape),
          pressure_Pa=array([x.pressure_Pa for x in out_states]).reshape(shape),
      )
      return out
    ##
  ##

  def _calculateAtmosphereStateFromGeopotentialAltitude(self, geopotential_alt_m: float) -> PdasAtmosphereScalarState:
    # Guaranteed to be within bounds.
    if geopotential_alt_m < self.__min_height_m:
      return self.__min_height_state
    elif geopotential_alt_m > self.__max_height_m:
      return self.__max_height_state
    else:
      geopotential_alt_km = geopotential_alt_m * 1e-3
    ##
    idx = binarySearchSortedArray(value=geopotential_alt_km, sorted_table=self.__heights_km)
    if idx is None:
      # log debug
      return self.__min_height_state
    ##
    temp_base_K = self.__temperatures_K[idx]  # base  temp. of local layer
    temp_gradient_Kpkm = self.__temperature_gradients_Kpkm[idx]  # temp. gradient of local layer
    delta_h_km = geopotential_alt_km - self.__heights_km[idx]  # height above local base
    temp_local_K = temp_base_K + temp_gradient_Kpkm * delta_h_km  # local temperature K
    theta = temp_local_K / self.__temperatures_K[0]  # temperature ratio

    delta = self.__pressures_unitless[idx]
    valid = True
    if 0.0 == temp_gradient_Kpkm:
      if temp_base_K != 0.:
        delta *= exp(-self.__GMR_Kpkm * delta_h_km / temp_base_K)
      else:
        log.debug(f'Base temperature (K) {temp_base_K} is invalid, unable to calculate valid atmosphere state')
        valid = False
      ##
    else:
      if temp_local_K != 0 and temp_gradient_Kpkm != 0:
        delta *= (temp_base_K / temp_local_K)**(self.__GMR_Kpkm / temp_gradient_Kpkm)
      else:
        log.debug(f'Local temperature (K) {temp_local_K} or Temperature Gradient (K/km) {temp_gradient_Kpkm} is invalid. Unable to calculate valid atmosphere state')
        valid = False
      ##
    ##

    if theta != 0:
      sigma = delta / theta
    else:
      log.debug(f'Sigma (delta / theta) is invalid (delta:{delta}; theta:{theta}). Unable to calculate valid atmosphere state')
      sigma = 1.
    ##

    out = PdasAtmosphereScalarState(
        geopotential_altitude_m=geopotential_alt_m,
        # sigma = density/sea-level standard density
        density_kgpm3=sigma * self.__density_sealevel_kgpm3,
        # delta = pressure/sea-level standard pressure
        pressure_Pa=delta * self.__pressure_sealevel_Pa,
        # theta = temperature/sea-level std. temperature
        temperature_K=theta * self.__temperature_sealevel_K,
        is_valid=valid,
    )
    return out
  ##

##


_default_pdas_interpolator = PdasAtmosphericInterpolator(earth_model=EarthModel.Sphere)


@overload
def calculateAtmosphereStateFromGeopotentialAltitude(geopotential_altitude_m: float) -> PdasAtmosphereScalarState:
  ...


@overload
def calculateAtmosphereStateFromGeopotentialAltitude(geopotential_altitude_m: ndarray) -> PdasAtmosphereArrayState:
  ...


def calculateAtmosphereStateFromGeopotentialAltitude(geopotential_altitude_m: FloatXorNdarray) -> Union[PdasAtmosphereScalarState, PdasAtmosphereArrayState]:
  """ Uses default PDAS Atmospheric tables and assumes 0 Latitude, 0 longitude
  Altitude is either geodetic or geocentric, depending on how it was calculated prior to this function.
  """
  # Earth model doesn't matter because geopotential altitude has already been calculated.
  out = _default_pdas_interpolator.calculateAtmosphereStateFromGeopotentialAltitude(geopotential_alt_m=geopotential_altitude_m)
  return out
##
