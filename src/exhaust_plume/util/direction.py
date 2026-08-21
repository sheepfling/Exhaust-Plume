# -*- coding: utf-8 -*-
# DOCME
from __future__ import annotations

from copy import deepcopy
from typing import Optional, Union

from numpy import allclose, arccos, arcsin, arctan2, asarray, concatenate, cos, isfinite, logical_not, logical_or, ndarray, newaxis, rad2deg, sin, zeros_like
from numpy.linalg import norm
from scipy.spatial.transform import Rotation

from exhaust_plume.log.log import getCleanLogger
from exhaust_plume.util.cached_property import cached_property
from exhaust_plume.util.direction_interface import FrozenDirectionGenericInterface
from exhaust_plume.util.numpy_util import ATOL_DEFAULT, EQUAL_NAN_DEFAULT, RTOL_DEFAULT

__all__ = (
    'Direction',
    'DirectionArray',
)
####################################################
log = getCleanLogger(__name__)


class Direction(FrozenDirectionGenericInterface[float]):
  """ A single frozen direction vector in Nose-Starboard-Down """

  def __init__(self, nose: float, starboard: float, down: float):
    super().__init__()
    self.__nsd = asarray([nose, starboard, down, ], 'float')
    nrm = norm(self.__nsd, axis=-1)
    invalid_norm = logical_or(nrm == 0., logical_not(isfinite(nrm)))
    if any(invalid_norm.ravel()):
      log.debug('Some Direction data is invalid. Defaulting invalid directions to nose==1.')
      self.__nsd[invalid_norm, ...] = 0.
      self.__nsd[invalid_norm, 0] = 1.
      valid_norm = ~invalid_norm
      self.__nsd[valid_norm, ...] = self.__nsd[valid_norm, ...] / nrm[valid_norm, newaxis]
    else:
      self.__nsd /= nrm[..., newaxis]
    ##
    self.__nsd.flags.writeable = False
  ##

  @property
  def nose(self) -> float:
    """ Returns Nose component of direction. """
    return float(self.__nsd[..., 0])
  ##

  @property
  def starboard(self) -> float:
    """ Returns Starboard component of direction. """
    return float(self.__nsd[..., 1])
  ##

  @property
  def down(self) -> float:
    """ Returns Down component of direction. """
    return float(self.__nsd[..., 2])
  ##

  @cached_property
  def azimuth_rad(self) -> float:
    """ Returns azimuth of direction (nose->starboard) in radians. """
    return arctan2(self.starboard, self.nose)
  ##

  @cached_property
  def azimuth_deg(self) -> float:
    """ Returns azimuth of direction (nose->starboard) in degrees. """
    return rad2deg(self.azimuth_rad)
  ##

  @cached_property
  def elevation_rad(self) -> float:
    """ Returns elevation of direction ((nose-starboard plane)->up) in radians. """
    return -arcsin(self.down)
  ##

  @cached_property
  def elevation_deg(self) -> float:
    """ Returns elevation of direction ((nose-starboard plane)->up) in degrees. """
    return rad2deg(self.elevation_rad)
  ##

  @cached_property
  def tmss_aspect_rad(self) -> float:
    """ Returns tmss_aspect of direction (aspect from nose) in radians. """
    return arccos(self.nose)
  ##

  @cached_property
  def tmss_aspect_deg(self) -> float:
    """ Returns tmss_aspect of direction (nose->starboard) in degrees. """
    return rad2deg(self.tmss_aspect_rad)
  ##

  @cached_property
  def tmss_roll_rad(self) -> float:
    """ Returns tmss_roll of direction (polar angle Up->Port) in radians. """
    return arctan2(-self.starboard, -self.down)
  ##

  @cached_property
  def tmss_roll_deg(self) -> float:
    """ Returns tmss_roll of direction (polar angle Up->Port) in degrees. """
    return rad2deg(self.tmss_roll_rad)
  ##

  def __neg__(self) -> Direction:
    out = deepcopy(self)
    out.__nsd *= -1
    return out
  ##

  def asMatrixNSD(self) -> ndarray:
    return self.__nsd
  ##

  def isClose(self, other: object, rtol: float = RTOL_DEFAULT, atol: float = ATOL_DEFAULT, equal_nan: bool = EQUAL_NAN_DEFAULT) -> bool:
    """ Checks if other object is close within a tolerance. """
    if not isinstance(other, type(self)):
      return False
    ##
    return allclose(self.__nsd, other.__nsd, rtol=rtol, atol=atol, equal_nan=equal_nan)
  ##

  def applyRotation(self, rotation: Rotation) -> Direction:
    """ Applies a rotation to the direction. """
    out = Direction.fromMatrixNSD(rotation.apply(self.__nsd))
    return out
  ##

  def __eq__(self, other: object) -> bool:
    if not isinstance(other, type(self)):
      return False
    ##
    out = (
        (self.__nsd.shape == other.__nsd.shape) and
        all((self.__nsd == other.__nsd).ravel())
    )
    return out
  ##

  def __hash__(self) -> int:
    return hash((self.__nsd.shape, self.__nsd.data.tobytes()))
  ##

  def __repr__(self) -> str:
    return f'{type(self).__name__}(nose={self.__nsd[..., 0]}, starboard={self.__nsd[..., 1]}, down={self.__nsd[..., 2]})'
  ##

  def getWorldFromBody(self, roll_rad: Optional[float] = None) -> Rotation:
    """ direction == getWorldFromBody( [1., 0., 0.,] )
    :return: Rotation that transforms [1, 0, 0] into the forward direction
    """
    az_rad = self.azimuth_rad
    el_rad = self.elevation_rad
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

  @classmethod
  def fromAzimuthElevation(cls, azimuth_rad: float, elevation_rad: float) -> Direction:
    ca = cos(azimuth_rad)
    sa = sin(azimuth_rad)
    ce = cos(elevation_rad)
    se = sin(elevation_rad)
    return cls.fromNoseStarboardDown(
        nose=ce * ca,
        starboard=ce * sa,
        down=-se,
    )
  ##

  @classmethod
  def fromTmssAspectRoll(cls, aspect_rad: float, roll_rad: float) -> Direction:
    """ Aspect here is angle from NOSE; Roll is polar angle in Starboard-Down plane, where 0 roll is at Up and 90' roll is at Port(-Starboard).`
    """
    sa = sin(aspect_rad)
    return cls.fromNoseStarboardDown(
        nose=cos(aspect_rad),
        starboard=sa * -sin(roll_rad),
        down=sa * -cos(roll_rad),
    )
  ##

  @classmethod
  def fromNoseStarboardDown(cls, nose: float, starboard: float, down: float) -> Direction:
    out = cls(nose=nose, starboard=starboard, down=down)
    return out
  ##

##


class DirectionArray(FrozenDirectionGenericInterface[ndarray]):
  """ frozen Array of Directions """

  def __init__(self, nose: ndarray, starboard: ndarray, down: ndarray):
    super().__init__()
    self.__nsd = concatenate([
        asarray(x, 'float')[..., newaxis] for x in  # promote to at least float
        (nose, starboard, down,)
    ], axis=-1)
    nrm = norm(self.__nsd, axis=-1)
    invalid_norm = logical_or(nrm == 0., logical_not(isfinite(nrm)))
    if any(invalid_norm.ravel()):
      log.debug('Some Direction data is invalid. Defaulting invalid directions to nose==1.')
      self.__nsd[invalid_norm, ...] = 0.
      self.__nsd[invalid_norm, 0] = 1.
      valid_norm = ~invalid_norm
      self.__nsd[valid_norm, ...] = self.__nsd[valid_norm, ...] / nrm[valid_norm, newaxis]
    else:
      self.__nsd /= nrm[..., newaxis]
    ##
    self.__nsd.flags.writeable = False
    self.__cache_hash: Optional[int] = None
  ##

  @property
  def nose(self) -> ndarray:
    """ Returns Nose component of direction. """
    return self.__nsd[..., 0]
  ##

  @property
  def starboard(self) -> ndarray:
    """ Returns Starboard component of direction. """
    return self.__nsd[..., 1]
  ##

  @property
  def down(self) -> ndarray:
    """ Returns Down component of direction. """
    return self.__nsd[..., 2]
  ##

  @cached_property
  def azimuth_rad(self) -> ndarray:
    """ Returns azimuth of direction (nose->starboard) in radians. """
    return arctan2(self.starboard, self.nose)
  ##

  @cached_property
  def azimuth_deg(self) -> ndarray:
    """ Returns azimuth of direction (nose->starboard) in degrees. """
    return rad2deg(self.azimuth_rad)
  ##

  @cached_property
  def elevation_rad(self) -> ndarray:
    """ Returns azimuth of elevation ((nose-starboard plane)->up) in radians. """
    return -arcsin(self.down)
  ##

  @cached_property
  def elevation_deg(self) -> ndarray:
    """ Returns azimuth of elevation ((nose-starboard plane)->up) in degrees. """
    return rad2deg(self.elevation_rad)
  ##

  @cached_property
  def tmss_aspect_rad(self) -> ndarray:
    """ Returns tmss_aspect of direction (aspect from nose) in radians. """
    return arccos(self.nose)
  ##

  @cached_property
  def tmss_aspect_deg(self) -> ndarray:
    """ Returns tmss_aspect of direction (nose->starboard) in degrees. """
    return rad2deg(self.tmss_aspect_rad)
  ##

  @cached_property
  def tmss_roll_rad(self) -> ndarray:
    """ Returns tmss_roll of direction (polar angle Up->Port) in radians. """
    return arctan2(-self.starboard, -self.down)
  ##

  @cached_property
  def tmss_roll_deg(self) -> ndarray:
    """ Returns tmss_roll of direction (polar angle Up->Port) in degrees. """
    return rad2deg(self.tmss_roll_rad)
  ##

  def __neg__(self) -> DirectionArray:
    out = deepcopy(self)
    out.__nsd *= -1
    return out
  ##

  def asMatrixNSD(self) -> ndarray:
    return self.__nsd
  ##

  def isClose(self, other: object, rtol: float = RTOL_DEFAULT, atol: float = ATOL_DEFAULT, equal_nan: bool = EQUAL_NAN_DEFAULT) -> bool:
    """ Checks if other object is close within a tolerance. """
    if not isinstance(other, type(self)):
      return False
    ##
    return allclose(self.__nsd, other.__nsd, rtol=rtol, atol=atol, equal_nan=equal_nan)
  ##

  def applyRotation(self, rotation: Rotation) -> DirectionArray:
    """ Applies a rotation to the direction. """
    out = deepcopy(self)
    out.__nsd = rotation.apply(out.__nsd)
    out.__cache_hash = None
    return out
  ##

  def __eq__(self, other: object) -> bool:
    if not isinstance(other, type(self)):
      return False
    ##
    out = (
        (self.__nsd.shape == other.__nsd.shape) and
        all((self.__nsd == other.__nsd).ravel())
    )
    return out
  ##

  def __hash__(self) -> int:
    if self.__cache_hash is not None:
      return self.__cache_hash
    ##
    self.__cache_hash = hash((self.__nsd.shape, self.__nsd.data.tobytes()))
    return self.__cache_hash
  ##

  def __repr__(self) -> str:
    return f'{type(self).__name__}(nose={self.__nsd[..., 0]!r}, starboard={self.__nsd[..., 1]!r}, down={self.__nsd[..., 2]!r})'
  ##

  def getWorldFromBody(self, roll_rad: Optional[float] = None) -> Rotation:
    """ direction == getWorldFromBody( [1., 0., 0.,] )
    :return: Rotation that transforms [1, 0, 0] into the forward direction
    """
    az_rad = self.azimuth_rad
    el_rad = self.elevation_rad
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

  @classmethod
  def fromAzimuthElevation(cls, azimuth_rad: Union[float, ndarray], elevation_rad: Union[float, ndarray]) -> DirectionArray:
    azimuth_rad = asarray(azimuth_rad)
    elevation_rad = asarray(elevation_rad)
    ca = cos(azimuth_rad)
    sa = sin(azimuth_rad)
    ce = cos(elevation_rad)
    se = sin(elevation_rad)
    return cls.fromNoseStarboardDown(
        nose=ce * ca,
        starboard=ce * sa,
        down=-se + zeros_like(azimuth_rad),
    )
  ##

  @classmethod
  def fromTmssAspectRoll(cls, aspect_rad: Union[float, ndarray], roll_rad: Union[float, ndarray]) -> DirectionArray:
    """ Aspect here is angle from NOSE; Roll is polar angle in Starboard-Down plane, where 0 roll is at Up and 90' roll is at Port(-Starboard).
    """
    aspect_rad = asarray(aspect_rad)
    roll_rad = asarray(roll_rad)
    sa = sin(aspect_rad)
    return cls.fromNoseStarboardDown(
        nose=cos(aspect_rad) + zeros_like(roll_rad),
        starboard=sa * -sin(roll_rad),
        down=sa * -cos(roll_rad),
    )
  ##

  @classmethod
  def fromNoseStarboardDown(cls, nose: ndarray, starboard: ndarray, down: ndarray) -> DirectionArray:
    out = cls(nose=nose, starboard=starboard, down=down)
    return out
  ##

##
