# -*- coding: utf-8 -*-
# DOCME
from __future__ import annotations

from pprint import pformat
from typing import Dict, Mapping, Optional

from numpy import allclose, asarray, eye, isfinite, isnan, ndarray, ones, prod, vstack, zeros

from exhaust_plume.loader.ignorable_config import getNonIgnorableConfig, hasNonIgnorableConfig
from exhaust_plume.log.extra_log_levels import CONFIG, TRACE_EXTRA
from exhaust_plume.log.log import getCleanLogger
from exhaust_plume.settings.settings_interface import AggregateFieldMetadata, Any, CallerIds, FloatFieldMetadata, RepeatedFieldMetadata, SwitchFieldMetadata
from exhaust_plume.util.aabb_interface import ArrayLike, FrozenBoundsInterface, MutableBoundsInterface, Point3d
from exhaust_plume.util.cached_property import cached_property
from exhaust_plume.util.numpy_util import ATOL_DEFAULT, EQUAL_NAN_DEFAULT, RTOL_DEFAULT, makeReadOnly

__all__ = (
    'FrozenBounds',
    'Bounds',
)
#################################
log = getCleanLogger(__name__)

_CORNER_MAT_MNMX = makeReadOnly(vstack([zeros((3,)), eye(3), ones((3,)), 1 - eye(3)]))


def _checkPoint(point: ArrayLike, name: str, should_be_finite: bool = True) -> ndarray:
  point = asarray(point, 'float')
  if point.shape != (3,):
    raise ValueError(f'Expected `{name}` shape to be (3,). Got:{point.shape}')
  ##
  if any(isnan(point).ravel()):
    raise ValueError(f'Expected `{name}` to be non-nan. Got:{point}')
  ##
  if should_be_finite and not all(isfinite(point).ravel()):
    raise ValueError(f'Expected `{name}` shape to finite. Got:{point}')
  ##
  return point
##


def _checkExtents(extents: ArrayLike) -> ndarray:
  extents = asarray(extents, 'float')
  if extents.shape != (3,):
    raise ValueError(f'Expected `extents` shape to be (3,). Got:{extents.shape}')
  ##
  if any(isnan(extents).ravel()):
    raise ValueError(f'Expected `extents` shape to be have any nan. Got:{extents}')
  ##
  if any((extents < 0.).ravel()):
    raise ValueError(f'Expected `extents` shape to be non-negative. Got:{extents}')
  ##
  return extents
##


def _getCornersFromMinMax(min_point: ndarray, max_point: ndarray) -> ndarray:
  out = min_point * _CORNER_MAT_MNMX + (1 - _CORNER_MAT_MNMX) * max_point
  return out
##

##############################################################


class FrozenBounds(FrozenBoundsInterface):
  """ An axis-aligned bounding box, or AABB for short, is a box aligned with coordinate
  axes and fully enclosing some object. Because the box is never rotated with respect to the
  axes, it can be defined by just its center and extents, or alternatively by min and max
  points.
  This object is frozen / immutable
  """

  def __init__(self, min_point: ArrayLike, max_point: ArrayLike):
    super().__init__()
    self.__min = makeReadOnly(_checkPoint(min_point, 'min', should_be_finite=False))
    self.__max = makeReadOnly(_checkPoint(max_point, 'max', should_be_finite=False))
    self.__center, self.__exents = self.calculateCenterExtentsFromMinMax(
        min_point=min_point,
        max_point=max_point,
    )
    self.__center = makeReadOnly(_checkPoint(self.__center, 'center', should_be_finite=True))
    self.__extents = makeReadOnly(_checkExtents(self.__exents))
    self.__cache_hash: Optional[int] = None
  ##

  @property
  def center(self) -> Point3d:
    return self.__center
  ##

  @property
  def extents(self) -> Point3d:
    return self.__extents
  ##

  @cached_property
  def max(self) -> Point3d:
    # The maximal point of the box. This is always equal to center+extents.
    return self.__max
  ##

  @cached_property
  def min(self) -> Point3d:
    # The minimal point of the box. This is always equal to center-extents.
    return self.__min
  ##

  @cached_property
  def size(self) -> Point3d:
    # The total size of the box. This is always twice as large as the extents.
    out = makeReadOnly(self.extents * 2.)
    return out
  ##

  @cached_property
  def corners(self) -> ndarray:
    """ Returns corners in a matrix. """
    out = makeReadOnly(_getCornersFromMinMax(min_point=self.__min, max_point=self.__max))
    return out
  ##

  @cached_property
  def volume(self) -> float:
    """ Returns volume of bounding cube. """
    d = self.extents.size
    out = 2 ** d * prod(self.extents)
    return out
  ##

  def isClose(self, other: object, rtol: float = RTOL_DEFAULT, atol: float = ATOL_DEFAULT, equal_nan: bool = EQUAL_NAN_DEFAULT) -> bool:
    """ Checks that bounds object is close within a tolerance to other object.
    If object is not a subclass of self, then not close.
    """
    if not isinstance(other, (type(self), Bounds,)):
      return False
    ##
    out = (
        allclose(self.__min, other.__min, rtol=rtol, atol=atol, equal_nan=equal_nan) and
        allclose(self.__max, other.__max, rtol=rtol, atol=atol, equal_nan=equal_nan)
    )
    return out
  ##

  def _asConfig(self, caller_ids: CallerIds) -> Dict[str, Any]:
    out = {
        'min': self.__min.tolist(),
        'max': self.__max.tolist(),
    }
    return out
  ##

  def __eq__(self, other: object) -> bool:
    """ Checks equality compared to other object. """
    if not isinstance(other, type(self)):
      return False
    ##
    out = (
        (self.__min.shape == other.__min.shape) and
        all((self.__min == other.__min).ravel()) and
        (self.__max.shape == other.__max.shape) and
        all((self.__max == other.__max).ravel())
    )
    return out
  ##

  def __hash__(self) -> int:
    if self.__cache_hash is not None:
      return self.__cache_hash
    ##
    self.__cache_hash = hash((
        self.__min.data.tobytes(),
        self.__max.data.tobytes(),
    ))
    return self.__cache_hash
  ##

  def __repr__(self) -> str:
    """ Returns string representation of the object. """
    return f'{type(self).__name__}(min={self.__min!r}, max={self.__max!r})'
  ##

  @classmethod
  def fromCenterExtents(cls, center: Point3d, extents: Point3d) -> FrozenBounds:
    """ Constructs Bounds object from center point and extents. """
    minp, maxp = cls.calculateMinMaxFromCenterExtents(center=center, extents=extents)
    return FrozenBounds.fromMinMax(
        min_point=minp,
        max_point=maxp,
    )
  ##

  @classmethod
  def fromMinMax(cls, min_point: Point3d, max_point: Point3d) -> FrozenBounds:
    return cls(min_point=min_point, max_point=max_point)
  ##

  @classmethod
  def fromConfig(cls, config: Mapping[str, Any], debug_config_prefix: str = '') -> FrozenBounds:
    """ Loads settings from config dictionary

    :param config: dictionary of settings
    :param debug_config_prefix: Config prefix for debugging/logging
    :return: settings
    """
    if not config:
      raise ValueError(f'{debug_config_prefix}: config must be a dictionary of values. Got:{config}')
    ##
    config = {**config}
    if 'center' in config or 'extents' in config:
      center = asarray(config.pop('center'), 'float')
      extents = asarray(config.pop('extents'), 'float')
      min_point, max_point = cls.calculateMinMaxFromCenterExtents(
          center=center,
          extents=extents,
      )
    else:
      min_point = asarray(config.pop('min'), 'float')
      max_point = asarray(config.pop('max'), 'float')
    ##
    out = cls(
        min_point=min_point, max_point=max_point,
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

  @classmethod
  def getConfigMetadata(cls) -> SwitchFieldMetadata:
    return _bounds_config_metadata
  ##

##

################################################################


class Bounds(MutableBoundsInterface):
  """ A mutable axis-aligned bounding box, or AABB for short, is a box aligned with coordinate
  axes and fully enclosing some object. Because the box is never rotated with respect to the
  axes, it can be defined by just its center and extents, or alternatively by min and max
  points. """

  def __init__(self, min_point: ArrayLike, max_point: ArrayLike):
    super().__init__()
    self.__min = _checkPoint(min_point, 'min', should_be_finite=False)
    self.__max = _checkPoint(max_point, 'max', should_be_finite=False)
    if any(self.__max < self.__min):
      raise ValueError(f'Min points should be less than max points. Got min:{self.__min} max:{self.__max}')
    ##
  ##

  @property
  def center(self) -> Point3d:
    return (self.__max + self.__min) / 2.
  ##

  def setCenter(self, new_center: ArrayLike) -> None:
    self.__min, self.__max = self.calculateMinMaxFromCenterExtents(
        center=new_center,
        extents=self.extents,
    )
  ##

  @property
  def extents(self) -> Point3d:
    return (self.__max - self.__min) / 2.
  ##

  def setExtents(self, new_extents: ArrayLike) -> None:
    self.__min, self.__max = self.calculateMinMaxFromCenterExtents(
        center=self.center,
        extents=new_extents
    )
  ##

  @property
  def max(self) -> Point3d:
    # The maximal point of the box. This is always equal to center+extents.
    return self.__max
  ##

  def setMaximum(self, point: ArrayLike) -> None:
    self.__max = asarray(point, 'float')
  ##

  @property
  def min(self) -> Point3d:
    # The minimal point of the box. This is always equal to center-extents.
    return self.__min
  ##

  def setMinimum(self, point: ArrayLike) -> None:
    self.__min = asarray(point, 'float')
  ##

  @property
  def size(self) -> Point3d:
    # The total size of the box. This is always twice as large as the extents.
    out = self.extents * 2.
    return out
  ##

  @property
  def corners(self) -> ndarray:
    """ Returns corners in a matrix. """
    out = _getCornersFromMinMax(min_point=self.__min, max_point=self.__max)
    return out
  ##

  @property
  def volume(self) -> float:
    """ Returns volume of bounding cube. """
    d = self.extents.size
    out = 2 ** d * prod(self.extents)
    return out
  ##

  def isClose(self, other: object, rtol: float = RTOL_DEFAULT, atol: float = ATOL_DEFAULT, equal_nan: bool = EQUAL_NAN_DEFAULT) -> bool:
    """ Checks that bounds object is close within a tolerance to other object.
    If object is not a subclass of self, then not close.
    """
    if not isinstance(other, (type(self), FrozenBounds,)):
      return False
    ##
    out = (
        allclose(self.__min, other.__min, rtol=rtol, atol=atol, equal_nan=equal_nan) and
        allclose(self.__max, other.__max, rtol=rtol, atol=atol, equal_nan=equal_nan)
    )
    return out
  ##

  def _asConfig(self, caller_ids: CallerIds) -> Dict[str, Any]:
    out = {
        'min': self.__min.tolist(),
        'max': self.__max.tolist(),
    }
    return out
  ##

  def __eq__(self, other: object) -> bool:
    if not isinstance(other, type(self)):
      return False
    ##
    out = (
        (self.__min.shape == other.__min.shape) and
        all((self.__min == other.__min).ravel()) and
        (self.__max.shape == other.__max.shape) and
        all((self.__max == other.__max).ravel())
    )
    return out
  ##

  def __repr__(self) -> str:
    """ Returns string representation of the object. """
    return f'{type(self).__name__}(min={self.__min!r}, max={self.__max!r})'
  ##

  @classmethod
  def fromCenterExtents(cls, center: Point3d, extents: Point3d) -> Bounds:
    """ Constructs Bounds object from center point and extents. """
    minp, maxp = cls.calculateMinMaxFromCenterExtents(
        center=center,
        extents=extents,
    )
    return Bounds(min_point=minp, max_point=maxp)
  ##

  @classmethod
  def fromMinMax(cls, min_point: Point3d, max_point: Point3d) -> Bounds:
    return cls(min_point=min_point, max_point=max_point)
  ##

  @classmethod
  def fromConfig(cls, config: Mapping[str, Any], debug_config_prefix: str = '') -> Bounds:
    """ Loads settings from config dictionary

    :param config: dictionary of settings
    :param debug_config_prefix: Config prefix for debugging/logging
    :return: settings
    """
    if not config:
      raise ValueError(f'{debug_config_prefix}: config must be a dictionary of values. Got:{config}')
    ##
    config = {**config}
    if 'center' in config or 'extents' in config:
      center = asarray(config.pop('center'), 'float')
      extents = asarray(config.pop('extents'), 'float')
      min_point, max_point = cls.calculateMinMaxFromCenterExtents(
          center=center,
          extents=extents,
      )
    else:
      min_point = asarray(config.pop('min'), 'float')
      max_point = asarray(config.pop('max'), 'float')
    ##
    out = cls(
        min_point=min_point,
        max_point=max_point,
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

  @classmethod
  def getConfigMetadata(cls) -> SwitchFieldMetadata:
    return _bounds_config_metadata
  ##

##


_bounds_minmax_md = AggregateFieldMetadata(
    label='Bounds',
    description='Axis-Aligned Bounding Box (AABB)',
    optional=False,
    fields={
        'min': RepeatedFieldMetadata.createFixedRepeat(
          label='Minimum point',
          description=None,
          count=3,
          value=FloatFieldMetadata.createUnbound(
              label='Point',
              description=None,
              units=None,
              default=None,
              optional=False,
          )
        ),
        'max': RepeatedFieldMetadata.createFixedRepeat(
            label='Maximum point',
            description=None,
            count=3,
            value=FloatFieldMetadata.createUnbound(
                label='Point',
                description=None,
                units=None,
                default=None,
                optional=False,
            )
        ),
    },
)

_bounds_center_extents_md = AggregateFieldMetadata(
    label='Bounds',
    description='Axis-Aligned Bounding Box (AABB)',
    optional=False,
    fields={
        'center': RepeatedFieldMetadata.createFixedRepeat(
          label='Center point',
          description=None,
          count=3,
          value=FloatFieldMetadata.createUnbound(
              label='Point',
              description=None,
              units=None,
              default=None,
              optional=False,
          )
        ),
        'extents': RepeatedFieldMetadata.createFixedRepeat(
            label='Extents',
            description='The extents are distance from the center to the edge (half the width)',
            count=3,
            value=FloatFieldMetadata.createUnbound(
                label='Point',
                description=None,
                units=None,
                default=None,
                optional=False,
            )
        ),
    },
)

_bounds_config_metadata = SwitchFieldMetadata(
    label=_bounds_center_extents_md.label,
    description=_bounds_center_extents_md.description,
    optional=False,
    default=None,
    switch_label='Constructor Type',
    switch_description='Choice of methods to construct the object',
    switch_key=None,  # NO-TAG
    switch_key_is_intrusive=False,
    choice2value={
        'Min-Max': _bounds_minmax_md,
        'Center-Extents': _bounds_center_extents_md,
    },
    case_insensitive=True,
)
