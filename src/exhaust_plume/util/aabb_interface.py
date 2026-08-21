# -*- coding: utf-8 -*-
# DOCME
from __future__ import annotations

import warnings
from abc import abstractmethod
from itertools import product
from typing import Sequence, Tuple, Type, TypeVar, Union

from numpy import abs, all as aall, amax, amin, asarray, inf, isinf, isnan, logical_and, maximum, minimum, nanmax, nanmin, ndarray, newaxis, vstack, zeros
from scipy.spatial.transform import Rotation

from exhaust_plume.log.log import getCleanLogger
from exhaust_plume.settings.settings_interface import SettingsInterface
from exhaust_plume.util.numpy_util import ATOL_DEFAULT, EQUAL_NAN_DEFAULT, RTOL_DEFAULT

__all__ = (
    'BoundsInterface',
    'FrozenBoundsInterface',
    'MutableBoundsInterface',
    'ArrayLike',
    'Point3d',
)
#################################
log = getCleanLogger(__name__)

ArrayLike = Union[Sequence[float], ndarray]
Point3d = ndarray
T = TypeVar('T', bound='BoundsInterface')

_CORNER_MAT = vstack(list(product(*((1, -1),) * 3)))


class BoundsInterface(SettingsInterface):
  """ An axis-aligned bounding box, or AABB for short, is a box aligned with coordinate
  axes and fully enclosing some object. Because the box is never rotated with respect to the
  axes, it can be defined by just its center and extents, or alternatively by min and max
  points. """

  @property
  @abstractmethod
  def center(self) -> Point3d:
    """ The center of the bounding box. """
  ##

  @property
  @abstractmethod
  def extents(self) -> Point3d:
    """ extents of the box. This is always half of the width. """
  ##

  @property
  @abstractmethod
  def max(self) -> Point3d:
    """ The maximal point of the box. This is always equal to center+extents. """
  ##

  @property
  @abstractmethod
  def min(self) -> Point3d:
    """ The minimal point of the box. This is always equal to center-extents. """
  ##

  @property
  @abstractmethod
  def size(self) -> Point3d:
    """ The total size of the box. This is always twice as large as the extents. """
  ##

  @property
  @abstractmethod
  def corners(self) -> ndarray:
    """ Returns corners in a matrix. (8,3) """
  ##

  @property
  @abstractmethod
  def volume(self) -> float:
    """ Returns volume of bounding cube. """
  ##

  @abstractmethod
  def isClose(self, other: object, rtol: float = RTOL_DEFAULT, atol: float = ATOL_DEFAULT, equal_nan: bool = EQUAL_NAN_DEFAULT) -> bool:
    """ Checks that bounds object is close within a tolerance to other object.
    If object is not a subclass of self, then not close.
    """
  ##

  @abstractmethod
  def __eq__(self, other: object) -> bool:
    """ Checks equality compared to other object. """
  ##

  @abstractmethod
  def __repr__(self) -> str:
    """ Returns string representation of the object. """
  ##

  def contains(self, points: ArrayLike) -> ndarray:
    """ Returns true/false array if a point is contained within the bounds.
    On the boundary is included as within
    Assumes that point array has shape (...,3)
    """
    within = aall(logical_and(self.min <= points, points <= self.max), axis=-1)
    return within
  ##

  def intersects(self, other: BoundsInterface) -> bool:
    """ Does another bounding box intersect with this bounding box.
    Counts intersection if boxes share an edge or face.
    https://gamedev.stackexchange.com/questions/586/what-is-the-fastest-way-to-work-out-2d-bounding-box-intersectionkk
    Archive Links:
    - https://web.archive.org/web/20220502192932/https://gamedev.stackexchange.com/questions/586/what-is-the-fastest-way-to-work-out-2d-bounding-box-intersection
    - https://archive.ph/4zB7Z
    """
    both_extents = self.extents + other.extents
    diff_center = self.center - other.center
    out = aall(diff_center <= both_extents, axis=-1)
    return out
  ##

  def asOffset(self: T, offset: ndarray) -> T:
    return type(self).fromCenterExtents(
        center=self.center + asarray(offset),
        extents=self.extents,
    )
  ##

  def asRotated(self: T, rotation: Rotation) -> T:
    return type(self).fromRotatedBounds(self, rotation)
  ##

  def asExpanded(self: T, amount: Union[Point3d, float]) -> T:
    """ Expand the bounds by adding the amount to the extents """
    out = self.fromCenterExtents(
        center=self.center,
        extents=self.extents + amount,
    )
    return out
  ##

  def asScaled(self: T, amount: Union[float, Point3d]) -> T:
    """ Multiplies extents by amount """
    out = self.fromCenterExtents(
        center=self.center,
        extents=self.extents * amount,
    )
    return out
  ##

  @classmethod
  @abstractmethod
  def fromCenterExtents(cls: Type[T], center: Point3d, extents: Point3d) -> T:
    """ Constructs Bounds object from center point and extents. """
  ##

  @classmethod
  @abstractmethod
  def fromMinMax(cls: Type[T], min_point: Point3d, max_point: Point3d) -> T:
    """ Creates a bounds from the min and max value of the box. """
  ##

  @classmethod
  def fromBounds(cls: Type[T], *bounds: BoundsInterface) -> T:
    """ Combines bounds to get all-encompassing bounds object for all the given bounds. """
    bounds = tuple(bounds)
    if len(bounds) == 0:
      return cls.fromCenterExtents(center=zeros((3,)), extents=zeros((3,)))
    elif len(bounds) == 1:
      return cls.fromCenterExtents(center=bounds[0].center, extents=bounds[0].extents)
    ##
    points = vstack([b.corners for b in bounds])
    out = cls.fromPoints(points)
    return out
  ##

  @classmethod
  def fromRotatedBounds(cls: Type[T], bounds: BoundsInterface, rotation: Rotation) -> T:
    """ Gets new axis-aligned bounding box that would contain the rotated version of this current box.
    Rotation is applied about the bounding box's center.
    The new bounds will, in general, be larger because the new bounds must enclose the rotated bounds.
    """
    rotated_corners = rotation.apply(_CORNER_MAT * bounds.extents[newaxis, ...])
    min_point = amin(rotated_corners, axis=0)
    max_point = amax(rotated_corners, axis=0)
    new_extents = (max_point - min_point) / 2.
    out = cls.fromCenterExtents(
        center=bounds.center,
        extents=new_extents,
    )
    return out
  ##

  @classmethod
  def fromPoints(cls: Type[T], points: ndarray) -> T:
    if len(points) == 0 or points.size == 0 or all(isnan(points).ravel()):
      min_point = zeros((3,))
      max_point = zeros((3,))
    else:
      min_point = nanmin(points, axis=0)
      max_point = nanmax(points, axis=0)
    ##
    return cls.fromMinMax(min_point=min_point, max_point=max_point)
  ##

  @classmethod
  def calculateCenterExtentsFromMinMax(cls, min_point: ArrayLike, max_point: ArrayLike) -> Tuple[ndarray, ndarray]:
    min_point = asarray(min_point, 'float')
    max_point = asarray(max_point, 'float')
    with warnings.catch_warnings():
      warnings.filterwarnings('ignore', category=RuntimeWarning)
      center = (max_point + min_point) / 2.
      extents = (max_point - min_point) / 2.
    ##
    inf_extents = logical_and(min_point == -inf, max_point == inf)
    extents[inf_extents] = inf
    center[inf_extents] = 0.
    same_point = min_point == max_point
    extents[same_point] = 0.
    out = (center, extents,)
    return out
  ##

  @classmethod
  def calculateMinMaxFromCenterExtents(cls, center: ArrayLike, extents: ArrayLike) -> Tuple[ndarray, ndarray]:
    center = asarray(center)
    extents = asarray(extents)
    min_point = center - extents
    max_point = center + extents
    inf_extents = isinf(extents)
    min_point[inf_extents] = -inf
    max_point[inf_extents] = inf
    out = (min_point, max_point,)
    return out
  ##

##

#####################################################


class FrozenBoundsInterface(BoundsInterface):
  @abstractmethod
  def __hash__(self) -> int:
    """ Calculates the hash of the object. """
  ##

##


class MutableBoundsInterface(BoundsInterface):

  @abstractmethod
  def setCenter(self, new_center: ArrayLike) -> None:
    ...
  ##

  @abstractmethod
  def setExtents(self, new_extents: ArrayLike) -> None:
    ...
  ##

  @abstractmethod
  def setMinimum(self, new_min: ArrayLike) -> None:
    ...
  ##

  @abstractmethod
  def setMaximum(self, new_max: ArrayLike) -> None:
    ...
  ##

  def encapsulate(self, points: Union[Point3d, ndarray]) -> None:
    """ Grows the Bounds to include the point. """
    points = asarray(points)
    if all(self.contains(points).ravel()):
      return
    ##
    new_min = minimum(self.min, amin(points, axis=0))
    new_max = maximum(self.max, amax(points, axis=0))
    self.setMinimum(new_min)
    self.setMaximum(new_max)
  ##

  def expand(self, amount: Point3d) -> None:
    """ Expands the bounds by increasing its size by an amount along each side.
    If amount is too negative value is clipped to 0.
    """
    self.setExtents(maximum(0., self.extents + asarray(amount)))
  ##

  def setMinMax(self, min_point: Point3d, max_point: Point3d) -> None:
    """ Sets the bounds to the min and max value of the box. """
    points = vstack([min_point, max_point])
    max_point = amax(points, axis=0)
    min_point = amin(points, axis=0)
    center = (max_point + min_point) / 2.
    initial_extents = (max_point - min_point) / 2.
    # Add a bit extra because of precision loss due to division
    extra = maximum(0., amax(abs(points - center) - initial_extents, axis=0))
    self.setCenter(center)
    self.setExtents(initial_extents + extra)
  ##
##
