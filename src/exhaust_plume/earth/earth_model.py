# -*- coding: utf-8 -*-
# DOCME
from __future__ import annotations

from enum import Enum
from functools import total_ordering
from typing import ClassVar, Mapping, Optional

from numpy import ndarray
from numpy.linalg import norm

from exhaust_plume.earth.constants import EARTH_SEMI_MAJOR_AXIS, EARTH_SEMI_MINOR_AXIS
from exhaust_plume.interface_messages import PositionType
from exhaust_plume.settings.settings_interface import ChoiceFieldMetadata
from exhaust_plume.util.direction import DirectionArray
from exhaust_plume.util.ellipsoid_util import Ellipsoid
from exhaust_plume.util.enum_util import normalizeEnumNameForMapping
from exhaust_plume.util.ray import RayArray

__all__ = (
    'EarthModel',
    'isInsideEarth',
    'getEarthRayIntersection',
    'isTargetOccludedFromSource',
)
######################################


@total_ordering
class EarthModel(Enum):
  """ List of supported earth models """
  str2enum: ClassVar[Mapping[str, EarthModel]]  # case-nonword insensitive
  Flat = 'Flat'
  Sphere = 'Sphere'
  WGS84 = 'WGS84'

  @classmethod
  def fromString(cls, value: str) -> EarthModel:
    try:
      return cls.str2enum[normalizeEnumNameForMapping(value)]  # type: ignore[index,attr-defined]
    except KeyError as e:
      raise ValueError(f'Unknown {cls.__name__} value:{value}. Valid options are:{list(cls.str2enum.keys())}') from e  # type: ignore[index,attr-defined]
    ##
  ##

  def __lt__(self, other: object) -> bool:
    if isinstance(other, type(self)):
      return self.name < other.name
    ##
    return NotImplemented
  ##

  @classmethod
  def getConfigMetadata(cls) -> ChoiceFieldMetadata:
    return _earth_md
  ##

  @classmethod
  def getConfigMetadataNonFlatEarth(cls) -> ChoiceFieldMetadata:
    return _earth_nonflat_md
  ##
##


EarthModel.str2enum = {normalizeEnumNameForMapping(e.value): e for e in EarthModel}

_earth_md = ChoiceFieldMetadata(
    label='Earth Model',
    description='Determines which earth model to use.',
    default=None,
    optional=False,
    choice2label={normalizeEnumNameForMapping(e.name): e.name for e in EarthModel},
)
_earth_nonflat_md = _earth_md.replace(
    choice2label={choice: label for choice, label in _earth_md.choice2label.items() if label != EarthModel.Flat.name},
)
_round_earth = Ellipsoid(rx=EARTH_SEMI_MAJOR_AXIS, ry=EARTH_SEMI_MAJOR_AXIS, rz=EARTH_SEMI_MAJOR_AXIS)
_wgs84_earth = Ellipsoid(rx=EARTH_SEMI_MAJOR_AXIS, ry=EARTH_SEMI_MAJOR_AXIS, rz=EARTH_SEMI_MINOR_AXIS)


def isInsideEarth(position: PositionType, earth_model: EarthModel) -> bool:
  # DOCME
  if earth_model == EarthModel.Sphere:
    return bool(_round_earth.isInside(position))
  elif earth_model == EarthModel.WGS84:
    return bool(_wgs84_earth.isInside(position))
  else:
    return False
  ##
##


def getEarthRayIntersection(ray: RayArray, earth_model: EarthModel) -> Optional[ndarray]:
  # DOCME
  if earth_model == EarthModel.Sphere:
    return _round_earth.getRayIntersection(ray)
  elif earth_model == EarthModel.WGS84:
    return _wgs84_earth.getRayIntersection(ray)
  else:
    return None
  ##
##


def isTargetOccludedFromSource(source_position: PositionType, target_position: PositionType, earth_model: EarthModel) -> bool:
  # DOCME
  if isInsideEarth(source_position, earth_model):
    return True
  elif isInsideEarth(target_position, earth_model):
    return True
  ##
  ray = RayArray(origin=source_position, direction=DirectionArray.fromMatrixNSD(target_position - source_position))
  intersections = getEarthRayIntersection(ray, earth_model)
  if intersections is None:
    return False
  ##
  if all(intersections < 0):
    return False
  ##
  target_source_distance = norm(source_position - target_position)
  if any(intersections[intersections >= 0] < target_source_distance):
    # If one of the positive intersections is less than the target source distance,
    # then it is occluded
    return True
  ##
  return False
##
