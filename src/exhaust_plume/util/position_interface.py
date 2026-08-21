# -*- coding: utf-8 -*-
# DOCME
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Generic, Mapping, Optional, Sequence, TypeVar, Union

from numpy import deg2rad, ndarray

from exhaust_plume.earth.earth_model import EarthModel
from exhaust_plume.earth.spherical_earth_constants import SPHERICAL_EARTH_RADIUS_m
from exhaust_plume.log.log import getCleanLogger
from exhaust_plume.settings.settings_interface import SettingsInterface
from exhaust_plume.util.numpy_util import ATOL_DEFAULT, EQUAL_NAN_DEFAULT, RTOL_DEFAULT

__all__ = (
    'PositionGenericInterface',
    ##########
    # Generic Interfaces
    'PositionLatLonGenericInterface',
    'PositionLlaGenericInterface',
    'PositionEcefGenericInterface',
    'PositionNedGenericInterface',
    ##########
    # Typed Interfaces
    'PositionLatLonScalarInterface',
    'PositionLatLonArrayInterface',
    'PositionLlaScalarInterface',
    'PositionLlaArrayInterface',
    'PositionEcefScalarInterface',
    'PositionEcefArrayInterface',
)
#####################
log = getCleanLogger(__name__)

T = TypeVar('T')


class PositionGenericInterface(Generic[T], SettingsInterface, ABC):

  @abstractmethod
  def isClose(self, other: object, rtol: float = RTOL_DEFAULT, atol: float = ATOL_DEFAULT, equal_nan: bool = EQUAL_NAN_DEFAULT) -> bool:
    """ Checks if other object is close within a tolerance. """
  ##
  @abstractmethod
  def __hash__(self) -> int:
    """ Returns hash of object """
  ##

##

###################################################################


class PositionLatLonGenericInterface(PositionGenericInterface[T], ABC):
  """ Latitude (deg), Longitude(deg) Position using  """
  @property
  @abstractmethod
  def latitude_deg(self) -> T:
    """ Returns Latitude in degrees"""
  ##

  @property
  @abstractmethod
  def longitude_deg(self) -> T:
    """ Returns Longitude in degrees"""
  ##

  @property
  def latitude_rad(self) -> T:
    return deg2rad(self.latitude_deg)  # type: ignore[call-overload]
  ##

  @property
  def longitude_rad(self) -> T:
    return deg2rad(self.longitude_deg)  # type: ignore[call-overload]
  ##

  @abstractmethod
  def replace(self, *,
              latitude_deg: Optional[T] = None,
              longitude_deg: Optional[T] = None,
              ) -> PositionLatLonGenericInterface[T]:
    pass
  ##

  @classmethod
  @abstractmethod
  def fromConfig(cls, config: Mapping[str, Any], debug_config_prefix: str = '') -> PositionLatLonGenericInterface[T]:
    """ Loads settings from dictionary

    :param config: dictionary of settings
    :param debug_config_prefix: Config prefix for debugging/logging
    :return: settings
    """
  ##

  @abstractmethod
  def asECEF(self, earth_model: EarthModel = EarthModel.WGS84) -> PositionEcefGenericInterface[T]:
    """ Converts to ECEF assuming LL coordinates refer to geo-DETIC values. Altitude is assumed to be zero. """
  ##

  @abstractmethod
  def asECEF_geocentric(self, earth_radius_m: float = SPHERICAL_EARTH_RADIUS_m) -> PositionEcefGenericInterface[T]:
    """ Converts to ECEF assuming LLA coordinates refer to geocentric values. Altitude is assumed to be zero. """
  ##

##


PositionLatLonScalarInterface = PositionLatLonGenericInterface[float]
PositionLatLonArrayInterface = PositionLatLonGenericInterface[ndarray]
###################################################################


class PositionLlaGenericInterface(PositionGenericInterface[T], ABC):
  """ Latitude (deg), Longitude(deg), Altitude (m) Position using  """
  @property
  @abstractmethod
  def latitude_deg(self) -> T:
    """ Returns Latitude in degrees"""
  ##

  @property
  @abstractmethod
  def longitude_deg(self) -> T:
    """ Returns Longitude in degrees"""
  ##

  @property
  @abstractmethod
  def altitude_m(self) -> T:
    """ Returns Altitude from ellipsoid in meters """
  ##

  @property
  def latitude_rad(self) -> T:
    return deg2rad(self.latitude_deg)  # type: ignore[call-overload]
  ##

  @property
  def longitude_rad(self) -> T:
    return deg2rad(self.longitude_deg)  # type: ignore[call-overload]
  ##

  @abstractmethod
  def asMatrixLLA(self) -> ndarray:
    """ Returns numpy array of Latitude (deg), Longitude (deg), Altitude (m) as (N,3) shaped array """
  ##

  @abstractmethod
  def replace(self, *,
              latitude_deg: Optional[T] = None,
              longitude_deg: Optional[T] = None,
              altitude_m: Optional[T] = None,
              ) -> PositionLlaGenericInterface[T]:
    pass
  ##

  @classmethod
  @abstractmethod
  def fromMatrixLLA(cls, lat_lon_alt: Union[Sequence[float], ndarray]) -> PositionLlaGenericInterface[T]:
    """ Creates object from Latitude (deg), Longitude (deg), Altitude matrix"""
  ##

  @classmethod
  @abstractmethod
  def fromConfig(cls, config: Mapping[str, Any], debug_config_prefix: str = '') -> PositionLlaGenericInterface[T]:
    """ Loads settings from dictionary

    :param config: dictionary of settings
    :param debug_config_prefix: Config prefix for debugging/logging
    :return: settings
    """
  ##

  @abstractmethod
  def asECEF(self, earth_model: EarthModel = EarthModel.WGS84) -> PositionEcefGenericInterface[T]:
    """ Converts to ECEF assuming LLA coordinates refer to geo-DETIC values. """
  ##

  @abstractmethod
  def asECEF_geocentric(self, earth_radius_m: float = SPHERICAL_EARTH_RADIUS_m) -> PositionEcefGenericInterface[T]:
    """ Converts to ECEF assuming LLA coordinates refer to geocentric values. """
  ##

##


PositionLlaScalarInterface = PositionLlaGenericInterface[float]
PositionLlaArrayInterface = PositionLlaGenericInterface[ndarray]
###################################################################


class PositionEcefGenericInterface(PositionGenericInterface[T], ABC):
  """ ECEF Position using - WGS84 ellipsoid parameters """

  @property
  @abstractmethod
  def x(self) -> T:
    """ Returns X component of ECEF position. """
  ##
  @property
  @abstractmethod
  def y(self) -> T:
    """ Returns Y component of ECEF position. """
  ##
  @property
  @abstractmethod
  def z(self) -> T:
    """ Returns Z component of ECEF position. """
  ##

  @abstractmethod
  def asMatrixECEF(self) -> ndarray:
    """ Returns numpy array of XYZ as (N,3) shaped array """
  ##

  @abstractmethod
  def replace(self, *,
              x: Optional[T] = None,
              y: Optional[T] = None,
              z: Optional[T] = None,
              ) -> PositionEcefGenericInterface[T]:
    pass
  ##

  @classmethod
  @abstractmethod
  def fromMatrixECEF(cls, ecef_xyz: Union[Sequence[float], ndarray]) -> PositionEcefGenericInterface[T]:
    """ Creates object from XYZ (N,3) matrix"""
  ##

  @classmethod
  @abstractmethod
  def fromConfig(cls, config: Union[Sequence[float], ndarray, Mapping[str, Any]], debug_config_prefix: str = '') -> PositionEcefGenericInterface[T]:
    """ Loads settings from dictionary

    :param config: dictionary of settings
    :param debug_config_prefix: Config prefix for debugging/logging
    :return: settings
    """
  ##

  @abstractmethod
  def asLLA(self) -> PositionLlaGenericInterface[T]:
    """ converts position to Geo-DETIC Latitude(deg), Longitude(deg), Altitude(m) """
  ##

  @abstractmethod
  def asLLA_geocentric(self, earth_radius_m: float = SPHERICAL_EARTH_RADIUS_m) -> PositionLlaGenericInterface[T]:
    """ converts position to Geo-centric Latitude(deg), Longitude(deg) """
  ##

##


PositionEcefScalarInterface = PositionEcefGenericInterface[float]
PositionEcefArrayInterface = PositionEcefGenericInterface[ndarray]
###################################################################

S = TypeVar('S', bound=PositionEcefScalarInterface)


class PositionNedGenericInterface(PositionGenericInterface[T], Generic[T, S], ABC):
  """ North,East,Down Local Tangent Plane position. Referenced from a given ECEF position """

  @property
  @abstractmethod
  def north(self) -> T:
    """ Returns North component of NED position. """
  ##
  @property
  @abstractmethod
  def east(self) -> T:
    """ Returns East component of NED position. """
  ##
  @property
  @abstractmethod
  def down(self) -> T:
    """ Returns Down component of NED position. """
  ##

  @property
  @abstractmethod
  def reference(self) -> S:
    """ Returns ECEF NED reference point """
  ##
  @property
  def up(self) -> T:
    """ Returns Up component of NED position. """
    return -self.down  # type: ignore[operator]
  ##

  @property
  def west(self) -> float:
    """ Returns West component of NED position. """
    return -self.east  # type: ignore[operator]
  ##

  @property
  def south(self) -> float:
    """ Returns South component of NED position. """
    return -self.north  # type: ignore[operator]
  ##

  @abstractmethod
  def asMatrixNED(self) -> ndarray:
    """ Returns numpy array of NED as (N,3) shaped array """
  ##

  @abstractmethod
  def replace(self, *,
              north: Optional[T] = None,
              east: Optional[T] = None,
              down: Optional[T] = None,
              reference: Optional[S] = None,
              ) -> PositionNedGenericInterface[T, S]:
    pass
  ##

  @abstractmethod
  def asECEF(self, earth_model: EarthModel = EarthModel.WGS84) -> PositionEcefGenericInterface[T]:
    """ Converts to ECEF assuming LL coordinates refer to geo-DETIC values. Altitude is assumed to be zero. """
  ##

  @abstractmethod
  def asECEF_geocentric(self, earth_radius_m: float = SPHERICAL_EARTH_RADIUS_m) -> PositionEcefGenericInterface[T]:
    """ Converts to ECEF assuming LLA coordinates refer to geocentric values. Altitude is assumed to be zero. """
  ##

  @classmethod
  @abstractmethod
  def fromConfig(cls, config: Mapping[str, Any], debug_config_prefix: str = '') -> PositionNedGenericInterface[T, S]:
    """ Loads settings from dictionary

    :param config: dictionary of settings
    :param debug_config_prefix: Config prefix for debugging/logging
    :return: settings
    """
  ##

##
