# -*- coding: utf-8 -*-
# DOCME
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Generic, Optional, TypeVar

from exhaust_plume.util.direction_interface import DirectionGenericInterface, FrozenDirectionGenericInterface
from exhaust_plume.util.numpy_util import ATOL_DEFAULT, EQUAL_NAN_DEFAULT, RTOL_DEFAULT

__all__ = (
    'RayGenericInterface',
    'FrozenRayGenericInterface',
)
###########################

T = TypeVar('T')
P = TypeVar('P')
R = TypeVar('R')


class RayGenericInterface(Generic[T, P, R], ABC):
  """ Generic Ray interface with added stipulations that the object is frozen
  T is the type for the DirectionGenericInterface
  P is the type for the origin Point
  R is the return type for the Rotation
  """

  @property
  @abstractmethod
  def direction(self) -> DirectionGenericInterface[T]:
    pass
  ##

  @property
  @abstractmethod
  def origin(self) -> P:
    ...
  ##

  @abstractmethod
  def isClose(self, other: object, rtol: float = RTOL_DEFAULT, atol: float = ATOL_DEFAULT, equal_nan: bool = EQUAL_NAN_DEFAULT) -> bool:
    ...
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
  def getWorldFromBody(self, roll_rad: Optional[T] = None) -> R:
    """ ray direction == getWorldFromBody( [1., 0., 0.,] )
    :return: Rotation that transforms [1, 0, 0] into the forward direction
    """
  ##

  @abstractmethod
  def getBodyFromWorld(self, roll_rad: Optional[T] = None) -> R:
    """ [1, 0, 0] == getBodyFromWorld( direction )
    :return: Rotation that transforms direction into the unit forward direction
    """
  ##

  @abstractmethod
  def asConfig(self) -> Dict[str, ABC]:
    ...
  ##

##


class FrozenRayGenericInterface(RayGenericInterface[T, P, R], ABC):
  """ Generic Ray interface with added stipulations that the object is frozen
  T is the type for the DirectionGenericInterface
  P is the type for the origin Point
  R is the return type for the Rotation
  """

  @property
  @abstractmethod
  def direction(self) -> FrozenDirectionGenericInterface[T]:
    pass
  ##

  @abstractmethod
  def __hash__(self) -> int:
    pass
  ##
##
