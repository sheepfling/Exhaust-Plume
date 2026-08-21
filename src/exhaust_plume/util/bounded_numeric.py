# -*- coding: utf-8 -*-
# DOCME
from __future__ import annotations

from typing import ClassVar, Optional, Type, Union

from numpy import inf

from exhaust_plume.log.log import getCleanLogger
from exhaust_plume.util.type_hints import FullComparable

__all__ = (
    'PositiveFiniteFloat',
    'NonNegativeFiniteFloat',
    'PositiveInt',
)
#########################
log = getCleanLogger(__name__)


def _generateDocString(base_type: Type[FullComparable], *,
                       min_value: Optional[FullComparable], min_is_valid: bool,
                       max_value: Optional[FullComparable], max_is_valid: bool, ) -> str:
  min_is_valid = bool(min_is_valid)
  max_is_valid = bool(max_is_valid)
  docstring = f'Class that acts like `{base_type.__name__}`'
  has_either = min_value is not None or max_value is not None
  has_both = min_value is not None and max_value is not None
  if has_either:
    docstring += ' but'
  ##
  if min_value is not None:
    docstring += ' has an ' + ('inclusive' if min_is_valid else 'exclusive') + f' lower bound of {min_value}'
  ##
  if has_both:
    docstring += ' and'
  ##
  if max_value is not None:
    docstring += ' has an ' + ('inclusive' if max_is_valid else 'exclusive') + f' upper bound of {max_value}'
  ##
  return docstring
##


def checkBounds(value: FullComparable,
                min_value: Optional[FullComparable], min_is_valid: bool,
                max_value: Optional[FullComparable], max_is_valid: bool,
                class_name: Optional[str] = '', ) -> None:
  if min_value is not None:
    if min_is_valid:
      if not (value >= min_value):  # done this way to catch nan's
        raise ValueError(f'{class_name + ":" if class_name else ""}Expected value:{value} to be greater than or equal to the lower bound:{min_value}')
      ##
    else:
      if not (value > min_value):
        raise ValueError(f'{class_name + ":" if class_name else ""}Expected value:{value} to be greater than the lower bound:{min_value}')
      ##
    ##
  ##
  if max_value is not None:
    if max_is_valid:
      if not (value <= max_value):  # done this way to catch nan's
        raise ValueError(f'{class_name + ":" if class_name else ""}Expected value:{value} to be less than or equal to the upper bound:{max_value}')
      ##
    else:
      if not (value < max_value):
        raise ValueError(f'{class_name + ":" if class_name else ""}Expected value:{value} to be less than the upper bound:{max_value}')
      ##
    ##
  ##
##

########################################################


class PositiveFiniteFloat(float):
  min_value: ClassVar[float] = 0.
  min_is_valid: ClassVar[bool] = False
  max_value: ClassVar[float] = inf
  max_is_valid: ClassVar[bool] = False

  def __new__(cls, value: Union[PositiveFiniteFloat, float]) -> PositiveFiniteFloat:
    return float.__new__(cls, float(value))
  ##

  def __init__(self, value: Union[PositiveFiniteFloat, float]) -> None:
    value = float(value)
    checkBounds(value, min_value=0., min_is_valid=False, max_value=inf, max_is_valid=False, class_name=type(self).__name__)
  ##

##


PositiveFiniteFloat.__doc__ = _generateDocString(
    PositiveFiniteFloat.__base__,
    min_value=PositiveFiniteFloat.min_value,
    min_is_valid=PositiveFiniteFloat.min_is_valid,
    max_value=PositiveFiniteFloat.max_value,
    max_is_valid=PositiveFiniteFloat.max_is_valid,
)
########################################################


class NonNegativeFiniteFloat(float):
  min_value: ClassVar[float] = 0.
  min_is_valid: ClassVar[bool] = True
  max_value: ClassVar[float] = inf
  max_is_valid: ClassVar[bool] = False

  def __new__(cls, value: Union[NonNegativeFiniteFloat, float]) -> NonNegativeFiniteFloat:
    return float.__new__(cls, float(value))
  ##

  def __init__(self, value: Union[NonNegativeFiniteFloat, float]) -> None:
    value = float(value)
    checkBounds(value, min_value=0., min_is_valid=False, max_value=inf, max_is_valid=False, class_name=type(self).__name__)
  ##

##


NonNegativeFiniteFloat.__doc__ = _generateDocString(
    NonNegativeFiniteFloat.__base__,
    min_value=NonNegativeFiniteFloat.min_value,
    min_is_valid=NonNegativeFiniteFloat.min_is_valid,
    max_value=NonNegativeFiniteFloat.max_value,
    max_is_valid=NonNegativeFiniteFloat.max_is_valid,
)

########################################################


class PositiveInt(int):
  min_value: ClassVar[int] = 0
  min_is_valid: ClassVar[bool] = False
  max_value: ClassVar[None] = None
  max_is_valid: ClassVar[bool] = False

  def __new__(cls, value: Union[PositiveInt, int]) -> PositiveInt:
    return int.__new__(cls, int(value))
  ##

  def __init__(self, value: Union[PositiveInt, int]) -> None:
    value = int(value)
    checkBounds(value, min_value=0., min_is_valid=False, max_value=None, max_is_valid=False, class_name=type(self).__name__)
  ##

##


PositiveInt.__doc__ = _generateDocString(
    PositiveInt.__base__,
    min_value=PositiveInt.min_value,
    min_is_valid=PositiveInt.min_is_valid,
    max_value=PositiveInt.max_value,
    max_is_valid=PositiveInt.max_is_valid,
)
