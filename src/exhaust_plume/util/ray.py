# -*- coding: utf-8 -*-
# DOCME
from __future__ import annotations

from pprint import pformat
from typing import Any, Dict, List, Mapping, Optional, Sequence, Union

from numpy import allclose, asarray, ndarray, zeros_like
from scipy.spatial.transform import Rotation

from exhaust_plume.loader.ignorable_config import getNonIgnorableConfig, hasNonIgnorableConfig
from exhaust_plume.log.extra_log_levels import CONFIG, TRACE_EXTRA
from exhaust_plume.log.log import getCleanLogger
from exhaust_plume.settings.settings_interface import CallerIds
from exhaust_plume.util.direction import Direction, DirectionArray
from exhaust_plume.util.numpy_util import ATOL_DEFAULT, EQUAL_NAN_DEFAULT, RTOL_DEFAULT, makeReadOnly
from exhaust_plume.util.ray_interface import FrozenRayGenericInterface

__all__ = (
    'RayArray',
    'Ray',
)
###########################
log = getCleanLogger(__name__)

ArrayLike = Union[Sequence[float], Sequence[Sequence[float]], ndarray]


class RayArray(FrozenRayGenericInterface[ndarray, ndarray, List[Rotation]]):
  """ Array of Rays """

  def __init__(self, origin: ndarray, direction: DirectionArray):
    super().__init__()
    self.__origin = asarray(origin, 'float')
    self.__direction = direction
    self.__cache_hash: Optional[int] = None
    if self.__origin.shape != self.__direction.asMatrixNSD().shape:
      raise ValueError(f'Expected `origin` and `direction` to have the same shape. '
                       f'origin.shape={self.__origin.shape}; '
                       f'direction data shape:{self.__direction.asMatrixNSD().shape}')
    ##
  ##

  @property
  def direction(self) -> DirectionArray:
    return self.__direction
  ##

  @property
  def origin(self) -> ndarray:
    return self.__origin
  ##

  def isClose(self, other: object, rtol: float = RTOL_DEFAULT, atol: float = ATOL_DEFAULT, equal_nan: bool = EQUAL_NAN_DEFAULT) -> bool:
    if not isinstance(other, type(self)):
      return False
    ##
    out = (
        allclose(self.__origin, other.__origin, rtol=rtol, atol=atol, equal_nan=equal_nan) and
        self.__direction.isClose(other.__direction, rtol=rtol, atol=atol, equal_nan=equal_nan)
    )
    return out
  ##

  def getWorldFromBody(self, roll_rad: Optional[ndarray] = None) -> List[Rotation]:
    """ ray direction == getWorldFromBody( [1., 0., 0.,] )
    :return: Rotation that transforms [1, 0, 0] into the forward direction
    """
    az_rad = self.__direction.azimuth_rad.ravel()
    el_rad = self.__direction.elevation_rad.ravel()
    roll_rad = zeros_like(az_rad) if roll_rad is None else roll_rad.ravel()
    out = [Rotation.from_euler('ZYX', (az, el, roll,)) for az, el, roll in zip(az_rad, el_rad, roll_rad.ravel())]
    return out
  ##

  def getBodyFromWorld(self, roll_rad: Optional[ndarray] = None) -> List[Rotation]:
    """ [1, 0, 0] == getBodyFromWorld( direction )
    :return: Rotation that transforms direction into the unit forward direction
    """
    world_from_body = self.getWorldFromBody(roll_rad=roll_rad)
    out = [wfb.inv() for wfb in world_from_body]
    return out
  ##

  def __eq__(self, other: object) -> bool:
    if not isinstance(other, type(self)):
      return False
    ##
    out = (
        (self.__origin.shape == other.__origin.shape) and
        all((self.__origin == other.__origin).ravel()) and
        (self.__direction == other.__direction)
    )
    return out
  ##

  def __repr__(self) -> str:
    out = f'{type(self).__name__}(origin={self.__origin!r}, direction={self.__direction!r})'
    return out
  ##

  def __hash__(self) -> int:
    if self.__cache_hash is not None:
      return self.__cache_hash
    ##
    self.__cache_hash = hash((
        self.__origin.shape,
        self.__origin.data.tobytes(),
        self.__direction,
    ))
    return self.__cache_hash
  ##

  def asConfig(self, caller_ids: Optional[CallerIds] = None) -> Dict[str, Any]:
    out = {
        'origin': self.origin.tolist(),
        'direction': self.direction.asMatrixNSD().tolist(),
    }
    return out
  ##

  @classmethod
  def fromConfig(cls, config: Mapping[str, Any], debug_config_prefix: str = '') -> RayArray:
    """ Loads settings from config dictionary """
    if not config:
      raise ValueError(f'{debug_config_prefix}: config must be a dictionary of values. Got:{config}')
    ##
    config = {**config}
    out = cls(
        origin=asarray(config.pop('origin'), 'float'),
        direction=DirectionArray.fromMatrixNSD(asarray(config.pop('direction'), 'float')),
    )
    if hasNonIgnorableConfig(config):
      log.info(f'{debug_config_prefix}: Unused Parameters in {cls.__name__} config: {getNonIgnorableConfig(config)}', extra={})
    ##
    log.log(CONFIG, f'{debug_config_prefix}: loaded {pformat(out)}', extra={})
    if log.isEnabledFor(TRACE_EXTRA):
      log.log(TRACE_EXTRA, f'{debug_config_prefix}: Loaded config:\n{pformat(out.asConfig(tuple()))}')
    ##
    return out
  ##

##


# inherit from settings interface?
class Ray(FrozenRayGenericInterface[float, ndarray, Rotation]):
  """ Scalar Frozen Ray """

  def __init__(self, origin: ArrayLike, direction: Direction):
    super().__init__()
    self.__origin = makeReadOnly(asarray(origin, 'float'))
    self.__direction = direction
    self.__cache_hash: Optional[int] = None
    if self.__origin.shape != self.__direction.asMatrixNSD().shape:
      raise ValueError(f'Expected `origin` and `direction` to have the same shape. '
                       f'origin.shape={self.__origin.shape}; '
                       f'direction data shape:{self.__direction.asMatrixNSD().shape}')
    ##
  ##

  @property
  def direction(self) -> Direction:
    return self.__direction
  ##

  @property
  def origin(self) -> ndarray:
    return self.__origin
  ##

  def replace(self, *,
              origin: Optional[ndarray] = None,
              direction: Optional[Direction] = None,
              ) -> Ray:
    out = Ray(
        origin=self.origin if origin is None else origin,
        direction=self.direction if direction is None else direction,
    )
    return out
  ##

  def isClose(self, other: object, rtol: float = RTOL_DEFAULT, atol: float = ATOL_DEFAULT, equal_nan: bool = EQUAL_NAN_DEFAULT) -> bool:
    if not isinstance(other, type(self)):
      return False
    ##
    out = (
        allclose(self.__origin, other.__origin, rtol=rtol, atol=atol, equal_nan=equal_nan) and
        self.__direction.isClose(other.__direction, rtol=rtol, atol=atol, equal_nan=equal_nan)
    )
    return out
  ##

  def getWorldFromBody(self, roll_rad: Optional[float] = None) -> Rotation:
    """ ray direction == getWorldFromBody( [1., 0., 0.,] )
    :return: Rotation that transforms [1, 0, 0] into the forward direction
    """
    az_rad = self.__direction.azimuth_rad
    el_rad = self.__direction.elevation_rad
    roll_rad = 0. if roll_rad is None else roll_rad
    out = Rotation.from_euler('ZYX', (az_rad, el_rad, roll_rad,))
    return out
  ##

  def getBodyFromWorld(self, roll_rad: Optional[float] = None) -> Rotation:
    """ [1, 0, 0] == getBodyFromWorld( direction )
    :return: Rotation that transforms direction into the unit forward direction
    """
    world_from_body = self.getWorldFromBody(roll_rad=roll_rad)
    return world_from_body.inv()
  ##

  def __eq__(self, other: object) -> bool:
    if not isinstance(other, type(self)):
      return False
    ##
    out = (
        (self.__origin.shape == other.__origin.shape) and
        all((self.__origin == other.__origin).ravel()) and
        (self.__direction == other.__direction)
    )
    return out
  ##

  def __repr__(self) -> str:
    out = f'{type(self).__name__}(origin={self.__origin!r}, direction={self.__direction!r})'
    return out
  ##

  def __hash__(self) -> int:
    if self.__cache_hash is not None:
      return self.__cache_hash
    ##
    self.__cache_hash = hash((
        self.__origin.shape,
        self.__origin.data.tobytes(),
        self.__direction,
    ))
    return self.__cache_hash
  ##

  def asConfig(self, caller_ids: Optional[CallerIds] = None) -> Dict[str, Any]:
    out = {
        'origin': self.origin.tolist(),
        'direction': self.direction.asMatrixNSD().tolist(),
    }
    return out
  ##

  @classmethod
  def fromSourceDestination(cls, source: ArrayLike, destination: ArrayLike) -> Ray:
    source = asarray(source, 'float')
    destination = asarray(destination, 'float')
    out = Ray(
        origin=source,
        direction=Direction.fromSourceDirection(source=source, destination=destination)
    )
    return out
  ##

  @classmethod
  def fromConfig(cls, config: Mapping[str, Any], debug_config_prefix: str = '') -> Ray:
    """ Loads settings from config dictionary """
    if not config:
      raise ValueError(f'{debug_config_prefix}: config must be a dictionary of values. Got:{config}')
    ##
    config = {**config}
    out = cls(
        origin=asarray(config.pop('origin'), 'float'),
        direction=Direction.fromMatrixNSD(asarray(config.pop('direction'), 'float')),
    )
    if hasNonIgnorableConfig(config):
      log.info(f'{debug_config_prefix}: Unused Parameters in {cls.__name__} config: {getNonIgnorableConfig(config)}', extra={})
    ##
    log.log(CONFIG, f'{debug_config_prefix}: loaded {pformat(out)}', extra={})
    if log.isEnabledFor(TRACE_EXTRA):
      log.log(TRACE_EXTRA, f'{debug_config_prefix}: Loaded config:\n{pformat(out.asConfig(tuple()))}')
    ##
    return out
  ##

##
