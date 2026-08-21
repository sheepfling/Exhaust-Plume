# -*- coding: utf-8 -*-
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Union, overload

from numpy import ndarray

from exhaust_plume.util.position_interface import PositionEcefArrayInterface, PositionEcefScalarInterface

__all__ = (
    'AtmosphereStateInterface',
    'AtmosphereScalarStateInterface',
    'AtmosphereArrayStateInterface',
    ####
    'AtmosphericInterpolatorInterface',
)
##################################################

T = TypeVar('T')
B = TypeVar('B')


class AtmosphereStateInterface(Generic[T, B], ABC):
  @abstractmethod
  def getIsValid(self) -> B:
    """ Returns true/false (or sequence of true/false) if query was valid / within limits of the interpolator's table. """
  ##

  @abstractmethod
  def getDensity_kgpm3(self) -> T:
    ...
  ##

  @abstractmethod
  def getTemperature_K(self) -> T:
    ...
  ##

  @abstractmethod
  def getPressure_Pa(self) -> T:
    ...
  ##
##


AtmosphereScalarStateInterface = AtmosphereStateInterface[float, bool]
AtmosphereArrayStateInterface = AtmosphereStateInterface[ndarray, ndarray]


class AtmosphericInterpolatorInterface(ABC):

  @abstractmethod
  @overload
  def calculateState(self, position_ecef: PositionEcefScalarInterface) -> AtmosphereScalarStateInterface:
    pass
  ##

  @abstractmethod
  @overload
  def calculateState(self, position_ecef: PositionEcefArrayInterface) -> AtmosphereArrayStateInterface:
    pass
  ##

  @abstractmethod
  def calculateState(self, position_ecef: Union[PositionEcefScalarInterface, PositionEcefArrayInterface]) -> Union[AtmosphereScalarStateInterface, AtmosphereArrayStateInterface]:
    pass
  ##
##
