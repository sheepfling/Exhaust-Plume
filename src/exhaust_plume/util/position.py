# -*- coding: utf-8 -*-
# DOCME
from __future__ import annotations

from pprint import pformat
from typing import Any, Dict, Mapping, Optional, Sequence, Union

from numpy import allclose, array, asarray, concatenate, inf, ndarray, newaxis, rad2deg, zeros

from exhaust_plume.earth.earth_model import EarthModel
from exhaust_plume.earth.spherical_earth_constants import SPHERICAL_EARTH_RADIUS_m
from exhaust_plume.earth.wgs84 import Wgs84Constants
from exhaust_plume.loader.ignorable_config import getNonIgnorableConfig, hasNonIgnorableConfig
from exhaust_plume.log.extra_log_levels import CONFIG, TRACE_EXTRA
from exhaust_plume.log.log import getCleanLogger
from exhaust_plume.settings.settings_interface import AggregateFieldMetadata, CallerIds, Degree, FloatFieldMetadata, IntFieldMetadata, Meter, RepeatedFieldMetadata, SwitchFieldMetadata
from exhaust_plume.util.misc import popOrNone
from exhaust_plume.util.numpy_util import ATOL_DEFAULT, EQUAL_NAN_DEFAULT, RTOL_DEFAULT, makeReadOnly
from exhaust_plume.util.position_interface import PositionEcefGenericInterface, PositionLatLonGenericInterface, PositionLlaGenericInterface, PositionNedGenericInterface
from exhaust_plume.util.robust_geocentric_conversion import ecef2lla_geocentric, lla_geocentric2ecef, ned_geocentric2ecef
from exhaust_plume.util.robust_geodetic_conversion import ecef2enu, ecef2lla, enu2ned, lla2ecef, ned2ecef

__all__ = (
    'PositionArrayECEF',
    'PositionECEF',
    #####
    'PositionArrayLLA',
    'PositionLLA',
    #####
    'PositionArrayNED',
    'PositionNED',
    #####
    'robustPositionEcefFromConfig',
    #####
    'PositionArrayLatLon',
    'PositionLatLon',
    #####
    'position_offset_robust_metadata',
    'robustLoadPositionOffsetFromConfig',
)
#####################
log = getCleanLogger(__name__)


class PositionArrayECEF(PositionEcefGenericInterface[ndarray]):
  """ ECEF Position """

  def __init__(self, ecef_xyz: ndarray):
    super().__init__()
    ecef_xyz = asarray(ecef_xyz, 'float')
    if len(ecef_xyz.shape) < 1 or ecef_xyz.shape[-1] != 3:
      raise ValueError(f'Input array must be shape (...,3). Got:{ecef_xyz.shape}')
    ##
    self.__xyz = makeReadOnly(ecef_xyz)
    self.__cache_hash: Optional[int] = None
  ##

  @property
  def x(self) -> ndarray:
    return self.__xyz[..., 0]
  ##

  @property
  def y(self) -> ndarray:
    return self.__xyz[..., 1]
  ##

  @property
  def z(self) -> ndarray:
    return self.__xyz[..., 2]
  ##

  def isClose(self, other: object, rtol: float = RTOL_DEFAULT, atol: float = ATOL_DEFAULT, equal_nan: bool = EQUAL_NAN_DEFAULT) -> bool:
    """ Checks if other object is close within a tolerance. """
    if not isinstance(other, type(self)):
      return False
    ##
    return allclose(self.__xyz, other.__xyz, rtol=rtol, atol=atol, equal_nan=equal_nan)
  ##

  def asMatrixECEF(self) -> ndarray:
    """ Returns numpy array of XYZ as (N,3) shaped array """
    return self.__xyz
  ##

  def replace(self, *,
              x: Optional[ndarray] = None,
              y: Optional[ndarray] = None,
              z: Optional[ndarray] = None,
              ) -> PositionArrayECEF:
    in_xyz = (x, y, z,)
    data_xyz = self.__xyz
    if any(a is not None for a in in_xyz):
      data_xyz = data_xyz.copy()
      data_xyz.flags.writeable = True
      for i, a in enumerate(in_xyz):
        if a is not None:
          data_xyz[..., i] = asarray(a, 'float')
        ##
      ##
    ##
    out = type(self)(data_xyz)
    return out
  ##

  def _asConfig(self, caller_ids: CallerIds) -> Dict[str, Any]:
    """ Returns object as a dictionary """
    out = {
        'x': [float(x) for x in self.x.ravel()],
        'y': [float(y) for y in self.y.ravel()],
        'z': [float(z) for z in self.z.ravel()],
    }
    if len(self.__xyz.shape) > 2:
      out['shape'] = [int(x) for x in self.__xyz.shape[:-1]]
    ##
    return out
  ##

  def __eq__(self, other: object) -> bool:
    if not isinstance(other, type(self)):
      return False
    ##
    out = (
        (self.__xyz.shape == other.__xyz.shape) and
        all((self.__xyz == other.__xyz).ravel())
    )
    return out
  ##

  def __hash__(self) -> int:
    if self.__cache_hash is not None:
      return self.__cache_hash
    ##
    self.__cache_hash = hash((self.__xyz.shape, self.__xyz.data.tobytes()))
    return self.__cache_hash
  ##

  def __repr__(self) -> str:
    return f'{type(self).__name__}({self.__xyz!r})'
  ##

  @classmethod
  def fromMatrixECEF(cls, ecef_xyz: Union[Sequence[float], ndarray]) -> PositionArrayECEF:
    f""" Creates {cls.__name__} object from XYZ (N,3) matrix"""
    out = cls(asarray(ecef_xyz))
    return out
  ##

  @classmethod
  def getConfigMetadata(cls) -> AggregateFieldMetadata:
    # TODO[future] - possibly revisit to pack as list-of-dicts instead of dict-of-lists (which seems more natural and enforces equal counts)
    return _metadata_ecef_arr
  ##

  @classmethod
  def fromConfig(cls, config: Union[Sequence[float], ndarray, Mapping[str, Any]], debug_config_prefix: str = '') -> PositionArrayECEF:
    """ Loads settings from config dictionary

    :param config: dictionary of settings or sequence of floats
    :param debug_config_prefix: Config prefix for debugging/logging
    :return: settings
    """
    data_xyz: Optional[ndarray] = None
    if isinstance(config, ndarray):
      data_xyz = config
    ##
    if data_xyz is None:
      try:
        data_xyz = asarray(config, 'float')
      except (ValueError, TypeError,):
        pass
      ##
    ##
    if data_xyz is None:
      try:
        config = {**config}  # type: ignore[dict-item,list-item]
        xyz = [asarray(config.pop(k), 'float') for k in 'xyz']
        if 'shape' in config:
          shape = tuple(int(x) for x in config.pop('shape'))
          xyz = [a.reshape(shape) for a in xyz]
        ##
        data_xyz = concatenate([a[..., newaxis] for a in xyz], axis=-1)
        if hasNonIgnorableConfig(config):
          log.info(f'{debug_config_prefix}: Unused Parameters in {cls.__name__} config: {getNonIgnorableConfig(config)}', extra={})
        ##
      except Exception as e:
        raise ValueError(f'Unable to construct {cls.__name__} from {config}') from e
      ##
    ##
    out = cls(data_xyz)
    log.log(CONFIG, f'{debug_config_prefix}: loaded {pformat(out)}', extra={})
    if log.isEnabledFor(TRACE_EXTRA):
      log.log(TRACE_EXTRA, f'{debug_config_prefix}: Loaded config:\n{pformat(out.asConfig(tuple()))}')
    ##
    return out
  ##

  def asLLA(self, earth_model: EarthModel = EarthModel.WGS84) -> PositionArrayLLA:
    """ converts position to Geo-DETIC Latitude(deg), Longitude(deg), Altitude(m) """
    if earth_model == EarthModel.Sphere:
      return self.asLLA_geocentric()
    elif earth_model != EarthModel.WGS84:
      log.info(f'Cannot convert to ECEF with earth model:{earth_model}. Defaulting to {EarthModel.WGS84}')
    ##
    return PositionArrayLLA(ecef2lla(self.asMatrixECEF()))
  ##

  def asLLA_geocentric(self, earth_radius_m: float = SPHERICAL_EARTH_RADIUS_m) -> PositionArrayLLA:
    """ converts position to Geo-centric Latitude(deg), Longitude(deg), Altitude(m) """
    lla_gc = ecef2lla_geocentric(self.asMatrixECEF(), earth_radius_m=earth_radius_m)
    out = PositionArrayLLA.fromMatrixLLA(lla_gc)
    return out
  ##
##


class PositionECEF(PositionEcefGenericInterface[float]):
  """ ECEF Position """

  def __init__(self, ecef_xyz: ndarray):
    super().__init__()
    ecef_xyz = asarray(ecef_xyz, 'float').ravel()
    if len(ecef_xyz.shape) < 1 or ecef_xyz.shape != (3,):
      raise ValueError(f'Input array must be shape (3,). Got:{ecef_xyz.shape}')
    ##
    self.__xyz: ndarray = makeReadOnly(ecef_xyz)
    self.__cache_hash: Optional[int] = None
  ##

  @property
  def x(self) -> float:
    return float(self.__xyz[..., 0])
  ##

  @property
  def y(self) -> float:
    return float(self.__xyz[..., 1])
  ##

  @property
  def z(self) -> float:
    return float(self.__xyz[..., 2])
  ##

  def isClose(self, other: object, rtol: float = RTOL_DEFAULT, atol: float = ATOL_DEFAULT, equal_nan: bool = EQUAL_NAN_DEFAULT) -> bool:
    """ Checks if other object is close within a tolerance. """
    if not isinstance(other, type(self)):
      return False
    ##
    return allclose(self.__xyz, other.__xyz, rtol=rtol, atol=atol, equal_nan=equal_nan)
  ##

  def asMatrixECEF(self) -> ndarray:
    """ Returns numpy array of XYZ as (N,3) shaped array """
    return self.__xyz
  ##

  def replace(self, *,
              x: Optional[float] = None,
              y: Optional[float] = None,
              z: Optional[float] = None,
              ) -> PositionECEF:
    in_xyz = (x, y, z,)
    data_xyz = self.__xyz
    if any(a is not None for a in in_xyz):
      data_xyz = data_xyz.copy()
      data_xyz.flags.writeable = True
      for i, a in enumerate(in_xyz):
        if a is not None:
          data_xyz[..., i] = asarray(a, 'float')
        ##
      ##
    ##
    out = type(self)(data_xyz)
    return out
  ##

  def _asConfig(self, caller_ids: CallerIds) -> Dict[str, Any]:
    """ Returns object as a dictionary """
    out = {
        'x': float(self.__xyz[0]),
        'y': float(self.__xyz[1]),
        'z': float(self.__xyz[2]),
    }
    return out
  ##

  @classmethod
  def getConfigMetadata(cls) -> AggregateFieldMetadata:
    return _metadata_ecef_scalar
  ##

  def __eq__(self, other: object) -> bool:
    if not isinstance(other, type(self)):
      return False
    ##
    out = (
        (self.__xyz.shape == other.__xyz.shape) and
        all((self.__xyz == other.__xyz).ravel())
    )
    return out
  ##

  def __hash__(self) -> int:
    if self.__cache_hash is not None:
      return self.__cache_hash
    ##
    self.__cache_hash = hash((self.__xyz.shape, self.__xyz.data.tobytes()))
    return self.__cache_hash
  ##

  def __repr__(self) -> str:
    return f'{type(self).__name__}({self.__xyz!r})'
  ##

  @classmethod
  def fromMatrixECEF(cls, ecef_xyz: Union[Sequence[float], ndarray]) -> PositionECEF:
    f""" Creates {cls.__name__} object from XYZ (3,) matrix"""
    out = cls(asarray(ecef_xyz))
    return out
  ##

  @classmethod
  def fromConfig(cls, config: Union[Sequence[float], ndarray, Mapping[str, Any]], debug_config_prefix: str = '') -> PositionECEF:
    """ Loads settings from config dictionary

    :param config: dictionary of settings or sequence of floats
    :param debug_config_prefix: Config prefix for debugging/logging
    :return: settings
    """
    data_xyz: Optional[ndarray] = None
    if isinstance(config, ndarray):
      data_xyz = config
    ##
    # Check dict first (lists can't **)
    if data_xyz is None:
      is_dict = False
      try:
        config = {**config}  # type: ignore[dict-item,list-item]
        is_dict = True
      except (TypeError,):
        pass
      ##
      if is_dict:
        try:
          data_xyz = concatenate([a[..., newaxis] for a in (asarray(config.pop(k), 'float') for k in 'xyz')], axis=-1)  # type: ignore[union-attr]
          if hasNonIgnorableConfig(config):  # type: ignore[arg-type]
            log.info(f'{debug_config_prefix}: Unused Parameters in {cls.__name__} config: {getNonIgnorableConfig(config)}', extra={})  # type: ignore[arg-type]
          ##
        except Exception as e:
          raise ValueError(f'Unable to construct {PositionArrayECEF.__name__} from {config}') from e
        ##
      ##
    ##
    if data_xyz is None:
      try:
        data_xyz = asarray(config, 'float')
      except (ValueError,):
        pass
      except (TypeError,) as e:
        log.exception(f'Caught exception while trying to unpack config:{config} with exception:{e}')
        raise
      ##
    ##
    out = PositionECEF(ecef_xyz=asarray(data_xyz, 'float'))
    log.log(CONFIG, f'{debug_config_prefix}: loaded {pformat(out)}', extra={})
    if log.isEnabledFor(TRACE_EXTRA):
      log.log(TRACE_EXTRA, f'{debug_config_prefix}: Loaded config:\n{pformat(out.asConfig(tuple()))}')
    ##
    return out
  ##

  def asLLA(self, earth_model: EarthModel = EarthModel.WGS84) -> PositionLLA:
    """ converts position to Geo-DETIC Latitude(deg), Longitude(deg), Altitude(m) """
    if earth_model == EarthModel.Sphere:
      return self.asLLA_geocentric()
    elif earth_model != EarthModel.WGS84:
      log.info(f'Cannot convert to ECEF with earth model:{earth_model}. Defaulting to {EarthModel.WGS84}')
    ##
    return PositionLLA(ecef2lla(self.asMatrixECEF()))
  ##

  def asLLA_geocentric(self, earth_radius_m: float = SPHERICAL_EARTH_RADIUS_m) -> PositionLLA:
    """ converts position to Geo-centric Latitude(deg), Longitude(deg), Altitude(m) """
    return PositionLLA(ecef2lla_geocentric(self.asMatrixECEF(), earth_radius_m=earth_radius_m))
  ##
##

##############################################################################


class PositionArrayLLA(PositionLlaGenericInterface[ndarray]):
  def __init__(self, lat_lon_alt: ndarray):
    super().__init__()
    data_lla = asarray(lat_lon_alt, 'float')
    if len(data_lla.shape) < 1 or data_lla.shape[-1] != 3:
      raise ValueError(f'Input array must be shape (...,3). Got:{data_lla.shape}')
    ##
    self.__lla = makeReadOnly(data_lla)
    self.__cache_hash: Optional[int] = None
  ##

  @property
  def latitude_deg(self) -> ndarray:
    """ Returns Latitude in degrees"""
    return self.__lla[..., 0]
  ##

  @property
  def longitude_deg(self) -> ndarray:
    """ Returns Longitude in degrees"""
    return self.__lla[..., 1]
  ##

  @property
  def altitude_m(self) -> ndarray:
    """ Returns Altitude from ellipsoid in meters """
    return self.__lla[..., 2]
  ##

  def isClose(self, other: object, rtol: float = RTOL_DEFAULT, atol: float = ATOL_DEFAULT, equal_nan: bool = EQUAL_NAN_DEFAULT) -> bool:
    """ Checks if other object is close within a tolerance. """
    if not isinstance(other, type(self)):
      return False
    ##
    return allclose(self.__lla, other.__lla, rtol=rtol, atol=atol, equal_nan=equal_nan)
  ##

  def asMatrixLLA(self) -> ndarray:
    """ Returns numpy array of Latitude (deg), Longitude (deg), Altitude (m) as (N,3) shaped array """
    return self.__lla
  ##

  def replace(self, *,
              latitude_deg: Optional[ndarray] = None,
              longitude_deg: Optional[ndarray] = None,
              altitude_m: Optional[ndarray] = None,
              ) -> PositionArrayLLA:
    new_lla = (latitude_deg, longitude_deg, altitude_m,)
    data_lla = self.__lla
    if any(a is not None for a in new_lla):
      data_lla = data_lla.copy()
      data_lla.flags.writeable = True
      for i, a in enumerate(new_lla):
        if a is not None:
          data_lla[..., i] = asarray(a, 'float')
        ##
      ##
    ##
    out = type(self)(data_lla)
    return out
  ##

  def _asConfig(self, caller_ids: CallerIds) -> Dict[str, Any]:
    """ Returns object as a dictionary """
    out = {
        'latitude_deg': self.latitude_deg.ravel().tolist(),
        'longitude_deg': self.longitude_deg.ravel().tolist(),
        'altitude_m': self.altitude_m.ravel().tolist(),
    }
    if len(self.__lla.shape) > 2:
      out['shape'] = [int(x) for x in self.__lla.shape[:-1]]
    ##
    return out
  ##

  def __eq__(self, other: object) -> bool:
    if not isinstance(other, type(self)):
      return False
    ##
    out = (
        (self.__lla.shape == other.__lla.shape) and
        all((self.__lla == other.__lla).ravel())
    )
    return out
  ##

  def __hash__(self) -> int:
    if self.__cache_hash is not None:
      return self.__cache_hash
    ##
    self.__cache_hash = hash((self.__lla.shape, self.__lla.data.tobytes()))
    return self.__cache_hash
  ##

  def __repr__(self) -> str:
    return f'{type(self).__name__}({self.__lla!r})'
  ##

  @classmethod
  def fromMatrixLLA(cls, lat_lon_alt: Union[Sequence[float], ndarray]) -> PositionArrayLLA:
    f""" Creates {PositionArrayLLA} object from Latitude (deg), Longitude (deg), Altitude matrix"""
    out = cls(asarray(lat_lon_alt))
    return out
  ##

  @classmethod
  def getConfigMetadata(cls) -> AggregateFieldMetadata:
    return _metadata_lla_arr
  ##

  @classmethod
  def fromConfig(cls, config: Mapping[str, Any], debug_config_prefix: str = '') -> PositionArrayLLA:
    """ Loads settings from dictionary

    :param config: dictionary of settings
    :param debug_config_prefix: Config prefix for debugging/logging
    :return: settings
    """
    if not config:
      raise ValueError(f'{debug_config_prefix}: config must be a dictionary of values. Got:{config}')
    ##
    config = {**config}
    latitude_deg = popOrNone(config, 'latitude_deg')
    if latitude_deg is None:
      latitude_rad = popOrNone(config, 'latitude_rad')
      if latitude_rad is not None:
        latitude_deg = rad2deg(latitude_rad)
      ##
    ##
    longitude_deg = popOrNone(config, 'longitude_deg')
    if longitude_deg is None:
      longitude_rad = popOrNone(config, 'longitude_rad')
      if longitude_rad is not None:
        longitude_deg = rad2deg(longitude_rad)
      ##
    ##
    for k in ('altitude', 'altitude_m', 'height',):
      altitude = popOrNone(config, k)
      if altitude is not None:
        break
      ##
    ##
    if (latitude_deg is None) or (longitude_deg is None) or (altitude is None):
      raise ValueError('All "latitude_(rad|deg)", "longitude_(rad|deg)", and "altitude(_m)?|height" must be specified')
    ##
    lla = [asarray(a, 'float').ravel() for a in (latitude_deg, longitude_deg, altitude,)]
    if 'shape' in config:
      shape = tuple(int(x) for x in config.pop('shape'))
      lla = [a.reshape(shape) for a in lla]
    ##
    data_lla = concatenate([a[..., newaxis] for a in lla], axis=-1)
    out = cls.fromMatrixLLA(data_lla)
    if hasNonIgnorableConfig(config):
      log.info(f'{debug_config_prefix}: Unused parameters in {cls.__name__}: {config}', extra={})
    ##
    log.log(CONFIG, f'{debug_config_prefix}: loaded {pformat(out)}', extra={})
    if log.isEnabledFor(TRACE_EXTRA):
      log.log(TRACE_EXTRA, f'{debug_config_prefix}: Loaded config:\n{pformat(out.asConfig(tuple()))}')
    ##
    return out
  ##

  def asECEF(self, earth_model: EarthModel = EarthModel.WGS84) -> PositionArrayECEF:
    """ Converts to ECEF assuming LLA coordinates refer to geo-DETIC values. """
    if earth_model == EarthModel.Sphere:
      return self.asECEF_geocentric()
    elif earth_model != EarthModel.WGS84:
      log.info(f'Cannot convert to ECEF with earth model:{earth_model}. Defaulting to {EarthModel.WGS84}')
    ##
    return PositionArrayECEF(lla2ecef(self.asMatrixLLA()))
  ##

  def asECEF_geocentric(self, earth_radius_m: float = SPHERICAL_EARTH_RADIUS_m) -> PositionArrayECEF:
    """ Converts to ECEF assuming LLA coordinates refer to geocentric values. """
    return PositionArrayECEF(lla_geocentric2ecef(self.asMatrixLLA(), earth_radius_m=earth_radius_m))
  ##

  def asPositionLatLon(self) -> PositionArrayLatLon:
    return PositionArrayLatLon.fromMatrixLatLon(lat_lon_deg=self.__lla[..., :2])
  ##
##


class PositionLLA(PositionLlaGenericInterface[float]):
  def __init__(self, lat_lon_alt: ndarray):
    super().__init__()
    data_lla = asarray(lat_lon_alt, 'float').ravel()
    if len(data_lla.shape) < 1 or data_lla.shape[-1] != 3:
      raise ValueError(f'Input array must be shape (3,). Got:{data_lla.shape}')
    ##
    self.__lla: ndarray = makeReadOnly(data_lla)
    self.__cache_hash: Optional[int] = None
  ##

  @property
  def latitude_deg(self) -> float:
    """ Returns Latitude in degrees"""
    return float(self.__lla[..., 0])
  ##

  @property
  def longitude_deg(self) -> float:
    """ Returns Longitude in degrees"""
    return float(self.__lla[..., 1])
  ##

  @property
  def altitude_m(self) -> float:
    """ Returns Altitude from ellipsoid in meters """
    return float(self.__lla[..., 2])
  ##

  def isClose(self, other: object, rtol: float = RTOL_DEFAULT, atol: float = ATOL_DEFAULT, equal_nan: bool = EQUAL_NAN_DEFAULT) -> bool:
    """ Checks if other object is close within a tolerance. """
    if not isinstance(other, type(self)):
      return False
    ##
    return allclose(self.__lla, other.__lla, rtol=rtol, atol=atol, equal_nan=equal_nan)
  ##

  def asMatrixLLA(self) -> ndarray:
    """ Returns numpy array of Latitude (deg), Longitude (deg), Altitude (m) as (N,3) shaped array """
    return self.__lla
  ##

  def asPositionLatLon(self) -> PositionLatLon:
    return PositionLatLon.fromScalarDeg(
        latitude_deg=self.latitude_deg,
        longitude_deg=self.longitude_deg,
    )
  ##

  def replace(self, *,
              latitude_deg: Optional[float] = None,
              longitude_deg: Optional[float] = None,
              altitude_m: Optional[float] = None,
              ) -> PositionLLA:
    new_lla = (latitude_deg, longitude_deg, altitude_m,)
    data_lla = self.__lla
    if any(a is not None for a in new_lla):
      data_lla = data_lla.copy()
      data_lla.flags.writeable = True
      for i, a in enumerate(new_lla):
        if a is not None:
          data_lla[..., i] = asarray(a, 'float')
        ##
      ##
    ##
    out = type(self)(data_lla)
    return out
  ##

  def _asConfig(self, caller_ids: CallerIds) -> Dict[str, Any]:
    """ Returns object as a dictionary """
    out = {
        'latitude_deg': float(self.latitude_deg),
        'longitude_deg': float(self.longitude_deg),
        'altitude_m': float(self.altitude_m),
    }
    return out
  ##

  @classmethod
  def getConfigMetadata(cls) -> AggregateFieldMetadata:
    return _metadata_lla_scalar
  ##

  def __eq__(self, other: object) -> bool:
    if not isinstance(other, type(self)):
      return False
    ##
    out = (
        (self.__lla.shape == other.__lla.shape) and
        all((self.__lla == other.__lla).ravel())
    )
    return out
  ##

  def __hash__(self) -> int:
    if self.__cache_hash is not None:
      return self.__cache_hash
    ##
    self.__cache_hash = hash((self.__lla.shape, self.__lla.data.tobytes()))
    return self.__cache_hash
  ##

  def __repr__(self) -> str:
    return f'{type(self).__name__}({self.__lla!r})'
  ##

  @classmethod
  def fromScalar(cls, latitude_deg: float, longitude_deg: float, altitude_m: float) -> PositionLLA:
    f""" Creates {cls.__name__} object from Latitude (deg), Longitude (deg), Altitude matrix"""
    out = cls(asarray([latitude_deg, longitude_deg, altitude_m, ]))
    return out
  ##

  @classmethod
  def fromMatrixLLA(cls, lat_lon_alt: Union[Sequence[float], ndarray]) -> PositionLLA:
    f""" Creates {cls.__name__} object from Latitude (deg), Longitude (deg), Altitude matrix"""
    out = cls(asarray(lat_lon_alt))
    return out
  ##

  @classmethod
  def fromConfig(cls, config: Mapping[str, Any], debug_config_prefix: str = '') -> PositionLLA:
    """ Loads settings from dictionary

    :param config: dictionary of settings
    :param debug_config_prefix: Config prefix for debugging/logging
    :return: settings
    """
    if not config:
      raise ValueError(f'{debug_config_prefix}: config must be a dictionary of values. Got:{config}')
    ##
    config = {**config}
    latitude_deg = popOrNone(config, 'latitude_deg')
    if latitude_deg is None:
      latitude_rad = popOrNone(config, 'latitude_rad')
      if latitude_rad is not None:
        latitude_deg = rad2deg(latitude_rad)
      ##
    ##
    longitude_deg = popOrNone(config, 'longitude_deg')
    if longitude_deg is None:
      longitude_rad = popOrNone(config, 'longitude_rad')
      if longitude_rad is not None:
        longitude_deg = rad2deg(longitude_rad)
      ##
    ##
    for k in ('altitude', 'altitude_m', 'height',):
      altitude = popOrNone(config, k)
      if altitude is not None:
        break
      ##
    ##
    if (latitude_deg is None) or (longitude_deg is None) or (altitude is None):
      raise ValueError('If position is not specified as ECEF [X,Y,Z] vector, then "latitude_(rad|deg)", "longitude_(rad|deg)", and "height" must be specified')
    ##
    data_lla = concatenate([asarray(x, 'float')[..., newaxis] for x in (latitude_deg, longitude_deg, altitude,)], -1)
    out = cls.fromMatrixLLA(data_lla)
    if hasNonIgnorableConfig(config):
      log.info(f'{debug_config_prefix}: Unused Parameters in {cls.__name__} config: {getNonIgnorableConfig(config)}', extra={})
    ##
    log.log(CONFIG, f'{debug_config_prefix}: loaded {pformat(out)}', extra={})
    if log.isEnabledFor(TRACE_EXTRA):
      log.log(TRACE_EXTRA, f'{debug_config_prefix}: Loaded config:\n{pformat(out.asConfig(tuple()))}')
    ##
    return out
  ##

  def asECEF(self, earth_model: EarthModel = EarthModel.WGS84) -> PositionECEF:
    """ Converts to ECEF assuming LLA coordinates refer to geo-DETIC values. """
    if earth_model == EarthModel.Sphere:
      return self.asECEF_geocentric()
    elif earth_model != EarthModel.WGS84:
      log.info(f'Cannot convert to ECEF with earth model:{earth_model}. Defaulting to {EarthModel.WGS84}')
    ##
    return PositionECEF(lla2ecef(self.asMatrixLLA()))
  ##

  def asECEF_geocentric(self, earth_radius_m: float = SPHERICAL_EARTH_RADIUS_m) -> PositionECEF:
    """ Converts to ECEF assuming LLA coordinates refer to geocentric values. """
    return PositionECEF(lla_geocentric2ecef(self.asMatrixLLA(), earth_radius_m=earth_radius_m))
  ##
##
##############################################################################

##############################################################################


class PositionArrayNED(PositionNedGenericInterface[ndarray, PositionEcefGenericInterface[float]]):

  def __init__(self, data_ned: ndarray, ecef_reference: PositionEcefGenericInterface[float]):
    super().__init__()
    data_ned = asarray(data_ned, 'float')
    if len(data_ned.shape) < 1 or data_ned.shape[-1] != 3:
      raise ValueError(f'Input array must be shape (...,3). Got:{data_ned.shape}')
    ##
    self.__data_ned = makeReadOnly(data_ned)
    self.__ecef_ref = ecef_reference
    self.__cache_hash: Optional[int] = None
  ##

  @property
  def north(self) -> ndarray:
    """ Returns North component of NED position. """
    return self.__data_ned[..., 0]
  ##

  @property
  def east(self) -> ndarray:
    """ Returns East component of NED position. """
    return self.__data_ned[..., 1]
  ##

  @property
  def down(self) -> ndarray:
    """ Returns Down component of NED position. """
    return self.__data_ned[..., 2]
  ##

  @property
  def reference(self) -> PositionEcefGenericInterface[float]:
    """ Returns ECEF NED reference point """
    return self.__ecef_ref
  ##

  def isClose(self, other: object, rtol: float = RTOL_DEFAULT, atol: float = ATOL_DEFAULT, equal_nan: bool = EQUAL_NAN_DEFAULT) -> bool:
    """ Checks if other object is close within a tolerance. """
    if not isinstance(other, type(self)):
      return False
    ##
    self_ref_xyz = self.__ecef_ref.asMatrixECEF()
    other_ref_xyz = other.__ecef_ref.asMatrixECEF()
    out = (
        allclose(self.__data_ned, other.__data_ned, rtol=rtol, atol=atol, equal_nan=equal_nan) and
        allclose(self_ref_xyz, other_ref_xyz, rtol=rtol, atol=atol, equal_nan=equal_nan)
    )
    return out
  ##

  def asMatrixNED(self) -> ndarray:
    """ Returns numpy array of NED as (N,3) shaped array """
    return self.__data_ned
  ##

  def replace(self, *,
              north: Optional[ndarray] = None,
              east: Optional[ndarray] = None,
              down: Optional[ndarray] = None,
              reference: Optional[PositionEcefGenericInterface[float]] = None,
              ) -> PositionArrayNED:
    new_ned = (north, east, down,)
    data_ned = self.__data_ned
    if any(a is not None for a in new_ned):
      data_ned = data_ned.copy()
      data_ned.flags.writeable = True
      for i, a in enumerate(new_ned):
        data_ned[..., i] = asarray(a, 'float')
      ##
    ##
    out = type(self)(
        data_ned,
        self.__ecef_ref if reference is None else reference,
    )
    return out
  ##

  def __eq__(self, other: object) -> bool:
    """ Checks equality compared to other object """
    if not isinstance(other, type(self)):
      return False
    ##
    out = (
        (self.__data_ned.shape == other.__data_ned.shape) and
        all((self.__data_ned == other.__data_ned).ravel()) and
        (self.__ecef_ref == other.__ecef_ref)
    )
    return out
  ##

  def __hash__(self) -> int:
    """ Returns hash of object """
    if self.__cache_hash is not None:
      return self.__cache_hash
    ##
    self.__cache_hash = hash((
        self.__data_ned.shape,
        self.__data_ned.data.tobytes(),
        self.__ecef_ref,
    ))
    return self.__cache_hash
  ##

  def __repr__(self) -> str:
    """ Returns representation of the object. """
    out = f'{type(self).__name__}({self.__data_ned!r}, {self.__ecef_ref!r})'
    return out
  ##

  def _asConfig(self, caller_ids: CallerIds) -> Dict[str, Any]:
    """ Returns object as a dictionary """
    out = {
        'north': self.north.ravel().tolist(),
        'east': self.east.ravel().tolist(),
        'down': self.down.ravel().tolist(),
        'reference': self.reference.asConfig(tuple()),
    }
    if len(self.__data_ned.shape) > 2:
      out['shape'] = [int(x) for x in self.__data_ned.shape[:-1]]
    ##
    return out
  ##

  @classmethod
  def getConfigMetadata(cls) -> AggregateFieldMetadata:
    return _metadata_ned_arr
  ##

  @classmethod
  def fromConfig(cls, config: Mapping[str, Any], debug_config_prefix: str = '') -> PositionArrayNED:
    """ Loads settings from dictionary

       :param config: dictionary of settings
       :param debug_config_prefix: Config prefix for debugging/logging
       :return: settings
       """
    if not config:
      raise ValueError(f'{debug_config_prefix}: config must be a dictionary of values. Got:{config}')
    ##
    config = {**config}
    ecef_ref = PositionECEF.fromConfig(config.pop('reference'), debug_config_prefix=f'{debug_config_prefix}.reference')
    north = asarray(config.pop('north'), 'float')
    east = asarray(config.pop('east'), 'float')
    down = asarray(config.pop('down'), 'float')
    if 'shape' in config:
      shape = tuple(int(x) for x in config.pop('shape'))
    else:
      shape = north.shape
    ##
    shape += (1,)  # for newaxis at end
    ned = concatenate([a.reshape(shape) for a in (north, east, down,)], axis=-1)
    out = PositionArrayNED(ned, ecef_ref)
    if hasNonIgnorableConfig(config):
      log.info(f'{debug_config_prefix}: Unused Parameters in {cls.__name__} config: {getNonIgnorableConfig(config)}', extra={})
    ##
    log.log(CONFIG, f'{debug_config_prefix}: loaded {pformat(out)}', extra={})
    if log.isEnabledFor(TRACE_EXTRA):
      log.log(TRACE_EXTRA, f'{debug_config_prefix}: Loaded config:\n{pformat(out.asConfig(tuple()))}')
    ##
    return out
  ##

  def asECEF(self, earth_model: EarthModel = EarthModel.WGS84) -> PositionArrayECEF:
    """ Converts to ECEF assuming coordinates refer to geo-DETIC values. """
    if earth_model == EarthModel.Sphere:
      return self.asECEF_geocentric()
    elif earth_model != EarthModel.WGS84:
      log.info(f'Cannot convert to ECEF with earth model:{earth_model}. Defaulting to {EarthModel.WGS84}')
    ##
    out = PositionArrayECEF.fromMatrixECEF(ned2ecef(
        position_ned=self.__data_ned,
        reference_ecef=self.__ecef_ref.asMatrixECEF(),
    ))
    return out
  ##

  def asECEF_geocentric(self, earth_radius_m: float = SPHERICAL_EARTH_RADIUS_m) -> PositionArrayECEF:
    """ Converts to ECEF assuming NED coordinates refer to geocentric values. """
    out = PositionArrayECEF.fromMatrixECEF(ned_geocentric2ecef(
        position_ned=self.__data_ned,
        reference_ecef=self.__ecef_ref.asMatrixECEF(),
        earth_radius_m=earth_radius_m,
    ))
    return out
  ##

  def asLLA(self) -> PositionArrayLLA:
    """ Converts to ECEF assuming coordinates refer to geo-DETIC values. """
    return self.asECEF().asLLA()
  ##

  def asLLA_geocentric(self, earth_radius_m: float = SPHERICAL_EARTH_RADIUS_m) -> PositionArrayLLA:
    """ Converts to ECEF assuming coordinates refer to geocentric values. """
    return self.asECEF_geocentric(earth_radius_m=earth_radius_m).asLLA_geocentric(earth_radius_m=earth_radius_m)
  ##
##


class PositionNED(PositionNedGenericInterface[float, PositionEcefGenericInterface[float]]):

  def __init__(self, data_ned: ndarray, ecef_reference: PositionEcefGenericInterface[float]):
    super().__init__()
    data_ned = asarray(data_ned, 'float').ravel()
    if len(data_ned.shape) < 1 or data_ned.shape != (3,):
      raise ValueError(f'Input array must be shape (3,). Got:{data_ned.shape}')
    ##
    self.__data_ned: ndarray = makeReadOnly(data_ned)
    self.__ecef_ref = ecef_reference
    self.__cache_hash: Optional[int] = None
  ##

  @property
  def north(self) -> float:
    """ Returns North component of NED position. """
    return float(self.__data_ned[..., 0])
  ##

  @property
  def east(self) -> float:
    """ Returns East component of NED position. """
    return float(self.__data_ned[..., 1])
  ##

  @property
  def down(self) -> float:
    """ Returns Down component of NED position. """
    return float(self.__data_ned[..., 2])
  ##

  @property
  def reference(self) -> PositionEcefGenericInterface[float]:
    """ Returns ECEF NED reference point """
    return self.__ecef_ref
  ##

  def isClose(self, other: object, rtol: float = RTOL_DEFAULT, atol: float = ATOL_DEFAULT, equal_nan: bool = EQUAL_NAN_DEFAULT) -> bool:
    """ Checks if other object is close within a tolerance. """
    if not isinstance(other, type(self)):
      return False
    ##
    self_ref_xyz = self.__ecef_ref.asMatrixECEF()
    other_ref_xyz = other.__ecef_ref.asMatrixECEF()
    out = (
        allclose(self.__data_ned, other.__data_ned, rtol=rtol, atol=atol, equal_nan=equal_nan) and
        allclose(self_ref_xyz, other_ref_xyz, rtol=rtol, atol=atol, equal_nan=equal_nan)
    )
    return out
  ##

  def asMatrixNED(self) -> ndarray:
    """ Returns numpy array of NED as (N,3) shaped array """
    return self.__data_ned
  ##

  def replace(self, *,
              north: Optional[float] = None,
              east: Optional[float] = None,
              down: Optional[float] = None,
              reference: Optional[PositionEcefGenericInterface[float]] = None,
              ) -> PositionNED:
    new_ned = (north, east, down,)
    data_ned = self.__data_ned
    if any(a is not None for a in new_ned):
      data_ned = data_ned.copy()
      data_ned.flags.writeable = True
      for i, a in enumerate(new_ned):
        data_ned[..., i] = asarray(a, 'float')
      ##
    ##
    out = type(self)(
        data_ned,
        self.__ecef_ref if reference is None else reference,
    )
    return out
  ##

  def __eq__(self, other: object) -> bool:
    """ Checks equality compared to other object """
    if not isinstance(other, type(self)):
      return False
    ##
    out = (
        (self.__data_ned.shape == other.__data_ned.shape) and
        all((self.__data_ned == other.__data_ned).ravel()) and
        (self.__ecef_ref == other.__ecef_ref)
    )
    return out
  ##

  def __hash__(self) -> int:
    """ Returns hash of object """
    if self.__cache_hash is not None:
      return self.__cache_hash
    ##
    self.__cache_hash = hash((
        self.__data_ned.shape,
        self.__data_ned.data.tobytes(),
        self.__ecef_ref,
    ))
    return self.__cache_hash
  ##

  def __repr__(self) -> str:
    """ Returns representation of the object. """
    out = f'{type(self).__name__}({self.__data_ned!r}, {self.__ecef_ref!r})'
    return out
  ##

  @classmethod
  def getConfigMetadata(cls) -> AggregateFieldMetadata:
    return _metadata_ned_scalar
  ##

  def _asConfig(self, caller_ids: CallerIds) -> Dict[str, Any]:
    """ Returns object as a dictionary """
    out = {
        'north': float(self.north),
        'east': float(self.east),
        'down': float(self.down),
        'reference': self.reference.asConfig(tuple()),
    }
    return out
  ##

  @classmethod
  def fromPositionECEF(cls, position_ecef: PositionEcefGenericInterface[float], reference_ecef: PositionEcefGenericInterface[float]) -> PositionNED:
    position_enu = ecef2enu(position_ecef=position_ecef.asMatrixECEF(), reference_ecef=reference_ecef.asMatrixECEF())
    position_ned = enu2ned(enu=position_enu)
    out = PositionNED(data_ned=position_ned, ecef_reference=reference_ecef)
    return out
  ##

  @classmethod
  def fromPositionLLA(cls, position_lla: PositionLlaGenericInterface[float], reference_ecef: PositionEcefGenericInterface[float]) -> PositionNED:
    return cls.fromPositionECEF(position_ecef=position_lla.asECEF(), reference_ecef=reference_ecef)
  ##

  @classmethod
  def fromConfig(cls, config: Mapping[str, Any], debug_config_prefix: str = '') -> PositionNED:
    """ Loads settings from dictionary

       :param config: dictionary of settings
       :param debug_config_prefix: Config prefix for debugging/logging
       :return: settings
       """
    if not config:
      raise ValueError(f'{debug_config_prefix}: config must be a dictionary of values. Got:{config}')
    ##
    config = {**config}
    north = asarray(config.pop('north'), 'float')
    east = asarray(config.pop('east'), 'float')
    down = asarray(config.pop('down'), 'float')
    ecef_ref = PositionECEF.fromConfig(config.pop('reference'), debug_config_prefix=f'{debug_config_prefix}.reference')
    ned = concatenate([a[..., newaxis] for a in (north, east, down,)], axis=-1)
    out = PositionNED(ned, ecef_ref)
    if hasNonIgnorableConfig(config):
      log.info(f'{debug_config_prefix}: Unused parameters in {cls.__name__}: {config}', extra={})
    ##
    log.log(CONFIG, f'{debug_config_prefix}: loaded {pformat(out)}', extra={})
    if log.isEnabledFor(TRACE_EXTRA):
      log.log(TRACE_EXTRA, f'{debug_config_prefix}: Loaded config:\n{pformat(out.asConfig(tuple()))}')
    ##
    return out
  ##

  def asECEF(self, earth_model: EarthModel = EarthModel.WGS84) -> PositionECEF:
    """ Converts to ECEF assuming the NED coordinates refer to geo-DETIC values. """
    if earth_model == EarthModel.Sphere:
      return self.asECEF_geocentric()
    elif earth_model != EarthModel.WGS84:
      log.info(f'Cannot convert to ECEF with earth model:{earth_model}. Defaulting to {EarthModel.WGS84}')
    ##
    out = PositionECEF.fromMatrixECEF(ned2ecef(
        position_ned=self.__data_ned,
        reference_ecef=self.__ecef_ref.asMatrixECEF(),
    ))
    return out
  ##

  def asECEF_geocentric(self, earth_radius_m: float = SPHERICAL_EARTH_RADIUS_m) -> PositionECEF:
    """ Converts to ECEF assuming NED coordinates refer to geocentric values. """
    out = PositionECEF.fromMatrixECEF(ned_geocentric2ecef(
        position_ned=self.__data_ned,
        reference_ecef=self.__ecef_ref.asMatrixECEF(),
        earth_radius_m=earth_radius_m,
    ))
    return out
  ##

  def asLLA(self) -> PositionLLA:
    """ Converts to ECEF assuming coordinates refer to geo-DETIC values. """
    return self.asECEF().asLLA()
  ##

  def asLLA_geocentric(self, earth_radius_m: float = SPHERICAL_EARTH_RADIUS_m) -> PositionLLA:
    """ Converts to ECEF assuming coordinates refer to geocentric values. """
    return self.asECEF_geocentric(earth_radius_m=earth_radius_m).asLLA_geocentric(earth_radius_m=earth_radius_m)
  ##
##


##############################################################################
# Non-full rank positions


class PositionArrayLatLon(PositionLatLonGenericInterface[ndarray]):
  def __init__(self, lat_lon_deg: ndarray):
    super().__init__()
    data_latlon = asarray(lat_lon_deg, 'float')
    if len(data_latlon.shape) < 1 or data_latlon.shape[-1] != 2:
      raise ValueError(f'Input array must be shape (...,2). Got:{data_latlon.shape}')
    ##
    self.__latlon = makeReadOnly(data_latlon)  # shape (...,2)
    self.__cache_hash: Optional[int] = None
  ##

  @property
  def latitude_deg(self) -> ndarray:
    """ Returns Latitude in degrees"""
    return self.__latlon[..., 0]
  ##

  @property
  def longitude_deg(self) -> ndarray:
    """ Returns Longitude in degrees"""
    return self.__latlon[..., 1]
  ##

  def isClose(self, other: object, rtol: float = RTOL_DEFAULT, atol: float = ATOL_DEFAULT, equal_nan: bool = EQUAL_NAN_DEFAULT) -> bool:
    """ Checks if other object is close within a tolerance. """
    if not isinstance(other, type(self)):
      return False
    ##
    return allclose(self.__latlon, other.__latlon, rtol=rtol, atol=atol, equal_nan=equal_nan)
  ##

  def asMatrixLatLon(self) -> ndarray:
    """ Returns numpy array of Latitude (deg), Longitude (deg) as (N,2) shaped array """
    return self.__latlon
  ##

  def replace(self, *,
              latitude_deg: Optional[ndarray] = None,
              longitude_deg: Optional[ndarray] = None,
              ) -> PositionArrayLatLon:
    new_lla = (latitude_deg, longitude_deg,)
    data_lla = self.__latlon
    if any(a is not None for a in new_lla):
      data_lla = data_lla.copy()
      data_lla.flags.writeable = True
      for i, a in enumerate(new_lla):
        if a is not None:
          data_lla[..., i] = asarray(a, 'float')
        ##
      ##
    ##
    out = type(self)(data_lla)
    return out
  ##

  def _asConfig(self, caller_ids: CallerIds) -> Dict[str, Any]:
    """ Returns object as a dictionary """
    out = {
        'latitude_deg': [float(x) for x in self.latitude_deg.ravel()],
        'longitude_deg': [float(x) for x in self.longitude_deg.ravel()],
    }
    if len(self.__latlon.shape) > 2:
      out['shape'] = [int(x) for x in self.__latlon.shape[:-1]]
    ##
    return out
  ##

  def __eq__(self, other: object) -> bool:
    if not isinstance(other, type(self)):
      return False
    ##
    out = (
        (self.__latlon.shape == other.__latlon.shape) and
        all((self.__latlon == other.__latlon).ravel())
    )
    return out
  ##

  def __hash__(self) -> int:
    if self.__cache_hash is not None:
      return self.__cache_hash
    ##
    self.__cache_hash = hash((self.__latlon.shape, self.__latlon.data.tobytes()))
    return self.__cache_hash
  ##

  def __repr__(self) -> str:
    return f'{type(self).__name__}({self.__latlon!r})'
  ##

  @classmethod
  def fromMatrixLatLon(cls, lat_lon_deg: Union[Sequence[float], ndarray]) -> PositionArrayLatLon:
    f""" Creates {PositionArrayLLA} object from Latitude (deg), Longitude (deg) matrix"""
    out = cls(asarray(lat_lon_deg))
    return out
  ##

  @classmethod
  def getConfigMetadata(cls) -> AggregateFieldMetadata:
    return _metadata_lla_scalar
  ##

  @classmethod
  def fromConfig(cls, config: Mapping[str, Any], debug_config_prefix: str = '') -> PositionArrayLatLon:
    """ Loads settings from dictionary

    :param config: dictionary of settings
    :param debug_config_prefix: Config prefix for debugging/logging
    :return: settings
    """
    if not config:
      raise ValueError(f'{debug_config_prefix}: config must be a dictionary of values. Got:{config}')
    ##
    config = {**config}
    latitude_deg = popOrNone(config, 'latitude_deg')
    if latitude_deg is None:
      latitude_rad = popOrNone(config, 'latitude_rad')
      if latitude_rad is not None:
        latitude_deg = rad2deg(latitude_rad)
      ##
    ##
    longitude_deg = popOrNone(config, 'longitude_deg')
    if longitude_deg is None:
      longitude_rad = popOrNone(config, 'longitude_rad')
      if longitude_rad is not None:
        longitude_deg = rad2deg(longitude_rad)
      ##
    ##
    if (latitude_deg is None) or (longitude_deg is None):
      raise ValueError('All "latitude_(rad|deg)", "longitude_(rad|deg)", and "altitude(_m)?|height" must be specified')
    ##
    lla = [asarray(a, 'float').ravel() for a in (latitude_deg, longitude_deg,)]
    if 'shape' in config:
      shape = tuple(int(x) for x in config.pop('shape'))
      lla = [a.reshape(shape) for a in lla]
    ##
    data_lla = concatenate([a[..., newaxis] for a in lla], axis=-1)
    out = cls.fromMatrixLatLon(data_lla)
    if hasNonIgnorableConfig(config):
      log.info(f'{debug_config_prefix}: Unused parameters in {cls.__name__}: {config}', extra={})
    ##
    log.log(CONFIG, f'{debug_config_prefix}: loaded {pformat(out)}', extra={})
    if log.isEnabledFor(TRACE_EXTRA):
      log.log(TRACE_EXTRA, f'{debug_config_prefix}: Loaded config:\n{pformat(out.asConfig(tuple()))}')
    ##
    return out
  ##

  def asECEF(self, earth_model: EarthModel = EarthModel.WGS84) -> PositionArrayECEF:
    """ Converts to ECEF assuming LLA coordinates refer to geo-DETIC values. Altitude is assumed to be zero. """
    if earth_model == EarthModel.Sphere:
      return self.asECEF_geocentric()
    elif earth_model != EarthModel.WGS84:
      log.info(f'Cannot convert to ECEF with earth model:{earth_model}. Defaulting to {EarthModel.WGS84}')
    ##
    latlon = self.asMatrixLatLon()
    lla = concatenate((
        latlon,
        zeros(latlon.shape[:-1] + (1,)),
    ), axis=-1)
    return PositionArrayECEF(lla2ecef(lla))
  ##

  def asECEF_geocentric(self, earth_radius_m: float = SPHERICAL_EARTH_RADIUS_m) -> PositionArrayECEF:
    """ Converts to ECEF assuming LLA coordinates refer to geocentric values. Altitude is assumed to be zero. """
    latlon = self.asMatrixLatLon()
    lla = concatenate((
        latlon,
        zeros(latlon.shape[:-1] + (1,)),
    ), axis=-1)
    return PositionArrayECEF(lla_geocentric2ecef(lla, earth_radius_m=earth_radius_m))
  ##

##


class PositionLatLon(PositionLatLonGenericInterface[float]):
  def __init__(self, lat_lon_deg: ndarray):
    super().__init__()
    data_latlon = asarray(lat_lon_deg, 'float').ravel()
    if len(data_latlon.shape) < 1 or data_latlon.shape[-1] != 2:
      raise ValueError(f'Input array must be shape (2,). Got:{data_latlon.shape}')
    ##
    self.__latlon: ndarray = makeReadOnly(data_latlon)
    self.__cache_hash: Optional[int] = None
  ##

  @property
  def latitude_deg(self) -> float:
    """ Returns Latitude in degrees"""
    return float(self.__latlon[..., 0])
  ##

  @property
  def longitude_deg(self) -> float:
    """ Returns Longitude in degrees"""
    return float(self.__latlon[..., 1])
  ##

  def getHumanReadable(self, fmt: str = '{:g}') -> str:
    out = ''.join([
        ''.join((fmt.format(abs(self.latitude_deg)), '°', 'N' if self.latitude_deg >= 0 else 'S')),
        ' ',
        ''.join((fmt.format(abs(self.longitude_deg)), '°', 'E' if self.longitude_deg >= 0 else 'W')),
    ])
    return out
  ##

  def isClose(self, other: object, rtol: float = RTOL_DEFAULT, atol: float = ATOL_DEFAULT, equal_nan: bool = EQUAL_NAN_DEFAULT) -> bool:
    """ Checks if other object is close within a tolerance. """
    if not isinstance(other, type(self)):
      return False
    ##
    return allclose(self.__latlon, other.__latlon, rtol=rtol, atol=atol, equal_nan=equal_nan)
  ##

  def asMatrixLatLon(self) -> ndarray:
    """ Returns numpy array of Latitude (deg), Longitude (deg) as (2,) shaped array """
    return self.__latlon
  ##

  def replace(self, *,
              latitude_deg: Optional[float] = None,
              longitude_deg: Optional[float] = None,
              ) -> PositionLatLon:
    new_lla = (latitude_deg, longitude_deg,)
    data_lla = self.__latlon
    if any(a is not None for a in new_lla):
      data_lla = data_lla.copy()
      data_lla.flags.writeable = True
      for i, a in enumerate(new_lla):
        if a is not None:
          data_lla[..., i] = asarray(a, 'float')
        ##
      ##
    ##
    out = type(self)(data_lla)
    return out
  ##

  @classmethod
  def getConfigMetadata(cls) -> AggregateFieldMetadata:
    out = AggregateFieldMetadata(
        label='Position Latitude-Longitude',
        description='A position given in Latitude, Longitude, but leaving altitude unspecified.',
        optional=False,
        fields={
            'latitude_deg': _metadata_latitude_scalar,
            'longitude_deg': _metadata_longitude_scalar,
        },
    )
    return out
  ##

  def _asConfig(self, caller_ids: CallerIds) -> Dict[str, Any]:
    """ Returns object as a dictionary """
    out = {
        'latitude_deg': float(self.latitude_deg),
        'longitude_deg': float(self.longitude_deg),
    }
    return out
  ##

  def __eq__(self, other: object) -> bool:
    if not isinstance(other, type(self)):
      return False
    ##
    out = (
        (self.__latlon.shape == other.__latlon.shape) and
        all((self.__latlon == other.__latlon).ravel())
    )
    return out
  ##

  def __hash__(self) -> int:
    if self.__cache_hash is not None:
      return self.__cache_hash
    ##
    self.__cache_hash = hash((self.__latlon.shape, self.__latlon.data.tobytes()))
    return self.__cache_hash
  ##

  def __repr__(self) -> str:
    return f'{type(self).__name__}({self.__latlon!r})'
  ##

  @classmethod
  def fromScalarRad(cls, latitude_rad: float, longitude_rad: float) -> PositionLatLon:
    return cls.fromMatrixLatLon(rad2deg([latitude_rad, longitude_rad]))
  ##

  @classmethod
  def fromScalarDeg(cls, latitude_deg: float, longitude_deg: float) -> PositionLatLon:
    return cls.fromMatrixLatLon(array([latitude_deg, longitude_deg]))
  ##

  @classmethod
  def fromMatrixLatLon(cls, lat_lon_deg: Union[Sequence[float], ndarray]) -> PositionLatLon:
    f""" Creates {cls.__name__} object from Latitude (deg), Longitude (deg) matrix"""
    out = cls(asarray(lat_lon_deg))
    return out
  ##

  @classmethod
  def getConfigMeta(cls) -> AggregateFieldMetadata:
    return _metadata_ned_scalar
  ##

  @classmethod
  def fromConfig(cls, config: Mapping[str, Any], debug_config_prefix: str = '') -> PositionLatLon:
    """ Loads settings from dictionary

    :param config: dictionary of settings
    :param debug_config_prefix: Config prefix for debugging/logging
    :return: settings
    """
    if not config:
      raise ValueError(f'{debug_config_prefix}: config must be a dictionary of values. Got:{config}')
    ##
    config = {**config}
    latitude_deg = popOrNone(config, 'latitude_deg')
    if latitude_deg is None:
      latitude_rad = popOrNone(config, 'latitude_rad')
      if latitude_rad is not None:
        latitude_deg = rad2deg(latitude_rad)
      ##
    ##
    longitude_deg = popOrNone(config, 'longitude_deg')
    if longitude_deg is None:
      longitude_rad = popOrNone(config, 'longitude_rad')
      if longitude_rad is not None:
        longitude_deg = rad2deg(longitude_rad)
      ##
    ##
    if (latitude_deg is None) or (longitude_deg is None):
      raise ValueError('If position is not specified as ECEF [X,Y,Z] vector, then "latitude_(rad|deg)", "longitude_(rad|deg)", and "height" must be specified')
    ##
    data_lla = concatenate([asarray(x, 'float')[..., newaxis] for x in (latitude_deg, longitude_deg,)], -1)
    out = cls.fromMatrixLatLon(data_lla)
    if hasNonIgnorableConfig(config):
      log.info(f'{debug_config_prefix}: Unused Parameters in {cls.__name__} config: {getNonIgnorableConfig(config)}', extra={})
    ##
    log.log(CONFIG, f'{debug_config_prefix}: loaded {pformat(out)}', extra={})
    if log.isEnabledFor(TRACE_EXTRA):
      log.log(TRACE_EXTRA, f'{debug_config_prefix}: Loaded config:\n{pformat(out.asConfig(tuple()))}')
    ##
    return out
  ##

  def asECEF(self, earth_model: EarthModel = EarthModel.WGS84) -> PositionECEF:
    """ Converts to ECEF assuming LLA coordinates refer to geo-DETIC values. Altitude is assumed to be zero. """
    if earth_model == EarthModel.Sphere:
      return self.asECEF_geocentric()
    elif earth_model != EarthModel.WGS84:
      log.info(f'Cannot convert to ECEF with earth model:{earth_model}. Defaulting to {EarthModel.WGS84}')
    ##
    lla = concatenate((self.asMatrixLatLon(), asarray([0.]),))
    return PositionECEF(lla2ecef(lla))
  ##

  def asECEF_geocentric(self, earth_radius_m: float = SPHERICAL_EARTH_RADIUS_m) -> PositionECEF:
    """ Converts to ECEF assuming LLA coordinates refer to geocentric values. Altitude is assumed to be zero. """
    lla = concatenate((self.asMatrixLatLon(), asarray([0.]),))
    return PositionECEF(lla_geocentric2ecef(lla, earth_radius_m=earth_radius_m))
  ##
##


#################################################

_metadata_ecef_x = FloatFieldMetadata(
    label='X',
    default=None,
    description=(
        'ECEF x coordinate. The positive X-axis emerges intersection of the equator'
        ' and the prime-meridian'
    ),
    optional=False,
    units=Meter,
    min_value=-inf,
    min_is_valid=False,
    max_value=inf,
    max_is_valid=False,
)

_metadata_ecef_y = _metadata_ecef_x.replace(
    label='Y',
    description=(
        'ECEF Y coordinate. The positive Y-axis is equal to the +Z axis cross +X axis.'
    ),
)

_metadata_ecef_z = _metadata_ecef_x.replace(
    label='Z',
    description=(
        'ECEF Z coordinate. The positive Z-axis emerges from the North pole'
    ),
)

_metadata_ned_n = _metadata_ecef_x.replace(
    label='N',
    description='NED North coordinate.',
)
_metadata_ned_e = _metadata_ned_n.replace(
    label='E',
    description='NED East coordinate.',
)
_metadata_ned_d = _metadata_ned_n.replace(
    label='D',
    description='NED Down coordinate.',
)

_metadata_latitude_scalar = FloatFieldMetadata(
    label='Latitude',
    description=(
        'Latitude coordinate.'
        ' Starts at zero at the equator and increases towards the North pole to +90°'
        ' and decreases to -90° at the South Pole.'
    ),
    optional=False,
    default=None,
    units=Degree,
    min_value=-90.,
    min_is_valid=True,
    max_value=+90.,
    max_is_valid=True,
)

_metadata_longitude_scalar = FloatFieldMetadata(
    label='Longitude',
    description=(
        'Longitude coordinate.'
        ' Starts at zero at the prime-merdian and increases in the Eastward direction to +180°'
        ' and decreases to -180° in the Westward meeting at the international date line.'
    ),
    optional=False,
    default=None,
    units=Degree,
    min_value=-180.,
    min_is_valid=True,
    max_value=+180.,
    max_is_valid=True,
)

_min_reasonable_altitude = -min(Wgs84Constants.semi_minor_axis, Wgs84Constants.semi_major_axis) / 2.

_metadata_altitude_scalar = FloatFieldMetadata(
    label='Altitude',
    optional=False,
    description=(
        'Altitude is the distance vertically from the ellipsoid.'
    ),
    default=None,
    units=Meter,
    min_value=_min_reasonable_altitude,
    min_is_valid=True,
    max_value=inf,
    max_is_valid=False,
)

_metadata_latlon_scalar = AggregateFieldMetadata(
    label='Position LatLong',
    description='A position given in Latitude, Longitude, but leaving altitude unspecified.',
    optional=False,
    fields={
        'latitude_deg': _metadata_latitude_scalar,
        'longitude_deg': _metadata_longitude_scalar,
    },
)

_metadata_ecef_scalar = AggregateFieldMetadata(
    label='ECEF Position',
    description='A position given in the Earth-Centered-Earth-Fixed (ECEF) frame',
    optional=False,
    fields={
        'x': _metadata_ecef_x,
        'y': _metadata_ecef_y,
        'z': _metadata_ecef_z,
    },
)

_metadata_ned_scalar = AggregateFieldMetadata(
    label='NED Position',
    description='A position given in the North-East-Down (NED) coordinate frame. The reference point is given as an ECEF point',
    optional=False,
    fields={
        'north': _metadata_ned_n,
        'east': _metadata_ned_e,
        'down': _metadata_ned_d,
        'reference': _metadata_ecef_scalar,
    },
)

_metadata_lla_scalar = _metadata_latlon_scalar.replace(
    label='Position LLA',
    description='A position given in Latitude, Longitude, but leaving altitude unspecified.',
    fields={
        **_metadata_latlon_scalar.fields,
        'altitude_m': _metadata_altitude_scalar,
    },
)

_arr_shape_metadata = RepeatedFieldMetadata.createOneOrMoreRepeat(
    label='Shape of Array',
    description='Dimensions of array.',
    repeat_label='Dimensions',
    repeat_description='Number of dimensions of array',
    optional=True,
    value=IntFieldMetadata(
        label='Length',
        description='Dimension Length',
        optional=False,
        default=1,
        min_value=1,
        max_value=None,
    ),
)

# TODO[minor,future] - possibly revisit to pack as list-of-dicts instead of dict-of-lists (which seems more natural and enforces equal counts)
_metadata_ecef_arr = AggregateFieldMetadata(
    label='ECEF Positions',
    description='An array of positions given in the Earth-Centered-Earth-Fixed (ECEF) frame',
    optional=False,
    fields={
        'shape': _arr_shape_metadata,
        'x': RepeatedFieldMetadata.createOneOrMoreRepeat(
            label='Array of X coordinates',
            description=None,
            optional=False,
            repeat_label='Number of points',
            repeat_description=None,
            value=_metadata_ecef_x,
        ),
        'y': RepeatedFieldMetadata.createOneOrMoreRepeat(
            label='Array of Y coordinates',
            description=None,
            optional=False,
            repeat_label='Number of points',
            repeat_description=None,
            value=_metadata_ecef_y,
        ),
        'z': RepeatedFieldMetadata.createOneOrMoreRepeat(
            label='Array of Z coordinates',
            description=None,
            optional=False,
            repeat_label='Number of points',
            repeat_description=None,
            value=_metadata_ecef_z,
        ),
    },
)

_metadata_ned_arr = _metadata_ned_scalar.replace(
    label='NED Positions',
    description='An array of position given in the North-East-Down (NED) coordinate frame. The reference point is given as an ECEF point',
    fields={
        'shape': _arr_shape_metadata,
        'north': RepeatedFieldMetadata.createOneOrMoreRepeat(
            label='Array of North coordinates',
            description=None,
            optional=False,
            repeat_label='Number of points',
            repeat_description=None,
            value=_metadata_ned_n,
        ),
        'east': RepeatedFieldMetadata.createOneOrMoreRepeat(
            label='Array of East coordinates',
            description=None,
            optional=False,
            repeat_label='Number of points',
            repeat_description=None,
            value=_metadata_ned_e,
        ),
        'down': RepeatedFieldMetadata.createOneOrMoreRepeat(
            label='Array of Down coordinates',
            description=None,
            optional=False,
            repeat_label='Number of points',
            repeat_description=None,
            value=_metadata_ned_d,
        ),
        'reference': _metadata_ecef_scalar,
    },
)

_metadata_latlon_arr = AggregateFieldMetadata(
    label='Position LatLong Array',
    description='An array of positions given in Latitude, Longitude, but leaving Altitude unspecified.',
    optional=False,
    fields={
        'shape': _arr_shape_metadata,
        'latitude_deg': RepeatedFieldMetadata.createOneOrMoreRepeat(
            label='Array of Latitudes',
            description=None,
            optional=False,
            repeat_label='Number of points',
            repeat_description=None,
            value=_metadata_latitude_scalar,
        ),
        'longitude_deg': RepeatedFieldMetadata.createOneOrMoreRepeat(
            label='Array of Longitudes',
            description=None,
            optional=False,
            repeat_label='Number of points',
            repeat_description=None,
            value=_metadata_longitude_scalar,
        ),
    },
)

_metadata_lla_arr = _metadata_latlon_arr.replace(
    label='Position LLA Array',
    description='An array of positions given in Latitude, Longitude, and Altitude.',
    fields={
        **_metadata_latlon_arr.fields,
        'altitude_m': RepeatedFieldMetadata.createOneOrMoreRepeat(
            label='Array of Altitudes',
            description=None,
            repeat_label='Number of points',
            repeat_description=None,
            value=_metadata_longitude_scalar,
            optional=False,
        ),
    },
)

position_robust_metadata = SwitchFieldMetadata(
    label='Position',
    description='Position of the object',
    optional=False,
    default=None,
    switch_label='Position Type',
    switch_description='Determines method of construction',
    switch_key=None,  # UNTAGGED
    switch_key_is_intrusive=False,
    choice2value={
        'ecef_array': RepeatedFieldMetadata.createFixedRepeat(
            label='ECEF XYZ Array',
            description='ECEF Array in XYZ',
            optional=False,
            count=3,
            value=FloatFieldMetadata.createFinite(
                label='Coordinate',
                description=None,
                optional=False,
                default=None,
                units=Meter,
            ),
        ),
        'ecef': PositionECEF.getConfigMetadata(),
        'lla': PositionLLA.getConfigMetadata(),
        'ned': PositionNED.getConfigMetadata(),
    },
)

position_offset_robust_metadata = SwitchFieldMetadata(
    label='Position Offset',
    description='Position offset given in body coordinates (Nose-Starboard-Down)',
    optional=False,
    default=None,
    switch_label='Constructor Type',
    switch_description='Determines method of construction',
    switch_key=None,  # UNTAGGED
    switch_key_is_intrusive=False,
    choice2value={
        'array': RepeatedFieldMetadata.createFixedRepeat(
            count=3,
            label='Array XYZ',
            description='A position position offset given in body coordinates (Nose-Starboard-Down)',
            value=_metadata_ecef_x.replace(
                label='NSD coordinate',
                description='Offset in NSD coordinates',
            ),
        ),
        'mapping': AggregateFieldMetadata(
            label='Mapping XYZ',
            description='A position position offset given in body coordinates (Nose-Starboard-Down)',
            optional=False,
            fields={
                'nose': _metadata_ecef_x.replace(
                    label='Nose',
                    description='Offset in the Nose direction',
                ),
                'starboard': _metadata_ecef_x.replace(
                    label='Starbaord',
                    description='Offset in the Starboard direction',
                ),
                'down': _metadata_ecef_x.replace(
                    label='Down',
                    description='Offset in the Down direction',
                ),
            },
        ),
    },
)


def robustLoadPositionOffsetFromConfig(
    config: Union[Mapping[str, Any], Sequence[float], ndarray],
    debug_config_prefix: str = '',
) -> ndarray:
  """ Loads position offset from config robustly. Returns offset in NSD. """
  try:
    config = {**config}  # type: ignore[dict-item,list-item]
    out = asarray([
        config.pop('nose'),
        config.pop('starboard'),
        config.pop('down'),
    ], 'float')
    if hasNonIgnorableConfig(config):
      log.info(f'{debug_config_prefix}: Unused parameters in config: {config}', extra={})
    ##
  except (AttributeError, TypeError,):
    out = asarray(config, 'float')
  ##
  log.log(CONFIG, f'{debug_config_prefix}: loaded {pformat(out)}', extra={})
  return out
##


def robustPositionEcefFromConfig(
    config: Union[Mapping[str, Any], Sequence[float], ndarray],
    earth_model: EarthModel = EarthModel.WGS84,
    debug_config_prefix: str = '',
) -> PositionECEF:
  """ Loads absolute position from config robustly. Returns position in ECEF."""
  try:
    return PositionECEF.fromConfig(config, debug_config_prefix=debug_config_prefix)
  except (ValueError, KeyError,):
    pass
  ##
  try:
    return PositionLLA.fromConfig(config, debug_config_prefix=debug_config_prefix).asECEF(earth_model=earth_model)  # type: ignore[arg-type]
  except (ValueError, KeyError,):
    pass
  ##
  try:
    return PositionNED.fromConfig(config, debug_config_prefix=debug_config_prefix).asECEF(earth_model=earth_model)  # type: ignore[arg-type]
  except (ValueError, KeyError,):
    pass
  ##
  raise ValueError(
      f'{debug_config_prefix}: Unable to robustly determine position from config.'
      f' It is not {PositionECEF.__name__}, {PositionLLA.__name__}, nor {PositionNED.__name__} config.'
      f' Got:{config!r}'
  )
##
