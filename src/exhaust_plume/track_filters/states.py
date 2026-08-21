# -*- coding: utf-8 -*-
# DOCME
from __future__ import annotations

from typing import Any, ClassVar, Optional

from numpy import asarray, concatenate, ndarray, zeros, zeros_like

from exhaust_plume.log.log import getCleanLogger

__all__ = (
    'EcefState_PVA',
    'EcefState_PV',
    'EcefStateCovariance_PVA',
    'EcefStateCovariance_PV',
)

################################
log = getCleanLogger(__name__)


class EcefState_PVA(ndarray):
  position_slice: ClassVar[slice] = slice(0, 3)
  velocity_slice: ClassVar[slice] = slice(3, 6)
  acceleration_slice: ClassVar[slice] = slice(6, 9)

  def __new__(cls, input_array: ndarray, info: Optional[Any] = None) -> EcefState_PVA:
    # Input array is an already formed ndarray instance; from numpy docs
    obj = asarray(input_array).view(cls)
    obj.info = info
    return obj
  #

  def __array_finalize__(self, obj: Optional[ndarray], *args: Any, **kwargs: Any) -> None:
    if obj is None:
      return
    ##
    self.info = getattr(obj, 'info', None)
  ##

  @property
  def position(self) -> ndarray:
    return self[..., self.position_slice]
  ##

  @property
  def velocity(self) -> ndarray:
    return self[..., self.velocity_slice]
  ##

  @property
  def acceleration(self) -> ndarray:
    return self[..., self.acceleration_slice]
  ##

  def asPVA(self) -> EcefState_PVA:
    return self
  ##

  def asPV(self) -> EcefState_PV:
    return EcefState_PV.fromComponents(
        position=self.position,
        velocity=self.velocity,
    )
  ##

  @classmethod
  def fromComponents(cls, *, position: ndarray, velocity: ndarray, acceleration: ndarray) -> EcefState_PVA:
    out = EcefState_PVA(concatenate([x for x in (position, velocity, acceleration)], axis=-1))
    return out
  ##

##


class EcefState_PV(ndarray):
  position_slice: ClassVar[slice] = slice(0, 3)
  velocity_slice: ClassVar[slice] = slice(3, 6)

  def __new__(cls, input_array: ndarray, info: Optional[Any] = None) -> EcefState_PV:
    # Input array is an already formed ndarray instance; from numpy docs
    obj = asarray(input_array).view(cls)
    obj.info = info
    return obj
  ##

  def __array_finalize__(self, obj: Optional[ndarray], *args: Any, **kwargs: Any) -> None:
    if obj is None:
      return
    ##
    self.info = getattr(obj, 'info', None)
  ##

  @property
  def position(self) -> ndarray:
    return self[..., self.position_slice]
  ##

  @property
  def velocity(self) -> ndarray:
    return self[..., self.velocity_slice]
  ##

  def asPVA(self) -> EcefState_PVA:
    """ Fills acceleration data with zeros."""
    out = EcefState_PVA.fromComponents(
        position=self.position,
        velocity=self.velocity,
        acceleration=zeros_like(self.position),
    )
    return out
  ##

  def asPV(self) -> EcefState_PV:
    return self
  ##

  @classmethod
  def fromComponents(cls, *, position: ndarray, velocity: ndarray, ) -> EcefState_PV:
    out = EcefState_PV(concatenate((position, velocity,), axis=-1))
    return out
  ##

##


class EcefStateCovariance_PVA(ndarray):
  position_slice: ClassVar[slice] = slice(0, 3)
  velocity_slice: ClassVar[slice] = slice(3, 6)
  acceleration_slice: ClassVar[slice] = slice(6, 9)

  def __new__(cls, input_array: ndarray, info: Optional[Any] = None) -> EcefStateCovariance_PVA:
    # Input array is an already formed ndarray instance; from numpy docs
    obj = asarray(input_array).view(cls)
    obj.info = info
    return obj
  ##

  def __array_finalize__(self, obj: Optional[ndarray], *args: Any, **kwargs: Any) -> None:
    if obj is None:
      return
    ##
    self.info = getattr(obj, 'info', None)
  ##

  @property
  def position_covar(self) -> ndarray:
    return self[..., self.position_slice, self.position_slice]
  ##

  @property
  def velocity_covar(self) -> ndarray:
    return self[..., self.velocity_slice, self.velocity_slice]
  ##

  @property
  def acceleration_covar(self) -> ndarray:
    return self[..., self.acceleration_slice, self.acceleration_slice]
  ##

  def asPVA(self) -> EcefStateCovariance_PVA:
    return self
  ##

  def asPV(self) -> EcefStateCovariance_PV:
    return EcefStateCovariance_PV(self[..., 0:6, 0:6])
  ##

##


class EcefStateCovariance_PV(ndarray):
  position_slice: ClassVar[slice] = slice(0, 3)
  velocity_slice: ClassVar[slice] = slice(3, 6)

  def __new__(cls, input_array: ndarray, info: Optional[Any] = None) -> EcefStateCovariance_PV:
    # Input array is an already formed ndarray instance; from numpy docs
    obj = asarray(input_array).view(cls)
    obj.info = info
    return obj
  #

  def __array_finalize__(self, obj: Optional[ndarray], *args: Any, **kwargs: Any) -> None:
    if obj is None:
      return
    ##
    self.info = getattr(obj, 'info', None)
  ##

  @property
  def position_covar(self) -> ndarray:
    return self[..., self.position_slice, self.position_slice]
  ##

  @property
  def velocity_covar(self) -> ndarray:
    return self[..., self.velocity_slice, self.velocity_slice]
  ##

  def asPVA(self) -> EcefStateCovariance_PVA:
    """ Fills acceleration data with zeros."""
    pva = zeros(self.shape[:-2] + (9, 9,))
    pva[..., :6, 0:6] = self[..., :6, :6]
    return EcefStateCovariance_PVA(pva)
  ##

  def asPV(self) -> EcefStateCovariance_PV:
    return self
  ##

##
