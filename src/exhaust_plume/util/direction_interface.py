# -*- coding: utf-8 -*-
""" """
# DOCME
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, Type, TypeVar

from numpy import ndarray
from scipy.spatial.transform import Rotation

from exhaust_plume.log.log import getCleanLogger

__all__ = (
    'DirectionGenericInterface',
    'FrozenDirectionGenericInterface',
)
####################################################
log = getCleanLogger(__name__)

T = TypeVar('T')
D = TypeVar('D', bound='DirectionGenericInterface')


class DirectionGenericInterface(Generic[T], ABC):
  """ """

  @property
  @abstractmethod
  def nose(self) -> T:
    """ Nose(forward) component of the direction """
  ##

  @property
  @abstractmethod
  def starboard(self) -> T:
    """ Starboard(right) component of the direction """
  ##

  @property
  @abstractmethod
  def down(self) -> T:
    """ Down component of the direction """
  ##

  @property
  @abstractmethod
  def azimuth_rad(self) -> T:
    """ Outward azimuth in radians """
  ##

  @property
  @abstractmethod
  def azimuth_deg(self) -> T:
    """ Outward azimuth in degrees """
  ##

  @property
  @abstractmethod
  def elevation_rad(self) -> T:
    """ Outward elevation in radians """
  ##

  @property
  @abstractmethod
  def elevation_deg(self) -> T:
    """ Outward elevation in degrees """
  ##

  @property
  @abstractmethod
  def tmss_aspect_rad(self) -> T:
    """ Returns tmss_aspect of direction (aspect from nose) in radians. """
  ##

  @property
  @abstractmethod
  def tmss_aspect_deg(self) -> T:
    """ Returns tmss_aspect of direction (nose->starboard) in degrees. """
  ##

  @property
  @abstractmethod
  def tmss_roll_rad(self) -> T:
    """ Returns tmss_roll of direction (polar angle Up->Port) in radians. """
    # tmss roll = arctan2(PORT, UP) = arctan2(-STARBOARD, -DOWN) = -1*-1 arctan2(STARBOARD, DOWN)
  ##

  @property
  @abstractmethod
  def tmss_roll_deg(self) -> T:
    """ Returns tmss_roll of direction (polar angle Up->Port) in degrees. """
  ##

  @abstractmethod
  def asMatrixNSD(self) -> ndarray:
    """ Constructs matrix as nose-starboard-direction matrix shape (...,3) """
  ##

  @abstractmethod
  def applyRotation(self: D, rotation: Rotation) -> D:
    """ Applies a rotation to the direction. """
  ##

  @abstractmethod
  def __eq__(self, other: object) -> bool:
    ...
  ##

  @abstractmethod
  def __repr__(self) -> str:
    ...
  ##

  @abstractmethod
  def __neg__(self: D) -> D:
    """ Flips/Negates direction """
  ##

  @classmethod
  @abstractmethod
  def fromNoseStarboardDown(cls: Type[D], nose: T, starboard: T, down: T) -> D:
    """ Constructs direction from nose-starboard-direction """
  ##

  @classmethod
  @abstractmethod
  def fromAzimuthElevation(cls: Type[D], azimuth_rad: T, elevation_rad: T) -> D:
    """ Constructs direction from outward direction indicated azimuth and elevation"""
  ##

  @classmethod
  def fromSourceDirection(cls: Type[D], source: ndarray, destination: ndarray) -> D:
    """ Constructs direction from source to direction assumes shape (...,3) nose-starboard-direction"""
    direction = destination - source
    return cls.fromNoseStarboardDown(
        nose=direction[..., 0],
        starboard=direction[..., 1],
        down=direction[..., 2],
    )
  ##

  @classmethod
  def fromMatrixNSD(cls: Type[D], nsd: ndarray) -> D:
    """ Constructs direction from nose-starboard-direction assumes shape (...,3) """
    return cls.fromNoseStarboardDown(
        nose=nsd[..., 0],
        starboard=nsd[..., 1],
        down=nsd[..., 2],
    )
  ##

  @classmethod
  @abstractmethod
  def fromTmssAspectRoll(cls: Type[D], aspect_rad: T, roll_rad: T) -> D:
    """ Constructs direction from outward TMSS angles indicated by aspect and roll"""
  ##

##


class FrozenDirectionGenericInterface(DirectionGenericInterface[T], ABC):
  """ Frozen/Hashable version of generic direction. """
  @abstractmethod
  def __hash__(self) -> int:
    ...
  ##
##
