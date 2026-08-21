# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple, Union

import numpy as np
from numpy import array, asarray, isfinite, ndarray, sqrt, sum as asum

from exhaust_plume.util.cached_property import cached_property
from exhaust_plume.util.ray import RayArray

__all__ = (
    'Ellipsoid',
)
#######################


@dataclass(frozen=True)
class Ellipsoid:
  rx: float
  ry: float
  rz: float

  def __post_init__(self) -> None:
    if (self.rx is None) or (self.rx <= 0) or not isfinite(self.rx):
      raise ValueError(f'`rx` must be a positive float. Got:{self.rx}')
    ##
    if (self.ry is None) or (self.ry <= 0) or not isfinite(self.ry):
      raise ValueError(f'`ry` must be a positive float. Got:{self.ry}')
    ##
    if (self.rz is None) or (self.rz <= 0) or not isfinite(self.rz):
      raise ValueError(f'`rz` must be a positive float. Got:{self.rz}')
    ##
  ##

  @cached_property
  def axes(self) -> Tuple[float, float, float]:
    out = (self.rx, self.ry, self.rz,)
    return out
  ##

  def isInside(self, points: ndarray) -> Union[bool, ndarray]:
    # (x/a)^2 + (y/b)^2 .. <= 1
    out = np.sum((points / self.axes)**2, axis=-1) <= 1.
    if out.size == 1:
      return bool(out)
    ##
    return asarray(out, 'bool')
  ##

  def getRayIntersection(self, ray: RayArray) -> Optional[ndarray]:
    ocn = ray.origin / self.axes
    rdn = ray.direction.asMatrixNSD() / self.axes
    a = asum(rdn * rdn, axis=-1)
    b = asum(ocn * rdn, axis=-1)
    c = asum(ocn * ocn, axis=-1)
    h = b * b - a * (c - 1.)
    if h < 0.:
      return None
    ##
    h = sqrt(h)
    out = asarray(array([-b - h, -b + h]) / a, 'float')
    return out
  ##
##
