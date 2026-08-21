# -*- coding: utf-8 -*-
""" This module contains some dataclass utilities"""
from __future__ import annotations

import inspect
from dataclasses import MISSING, fields
from fractions import Fraction
from pathlib import Path
from typing import AbstractSet, Any, Dict, List, Optional, Sequence, Tuple, TypeVar, Union, overload

from numpy import ndarray
from numpy.random import BitGenerator
from scipy.spatial.transform import Rotation

from exhaust_plume.log.log import getCleanLogger
from exhaust_plume.util.numpy_util import ATOL_DEFAULT, EQUAL_NAN_DEFAULT, RTOL_DEFAULT, areRotationsClose, numpyAllClose, numpyEqual

__all__ = (
    'dataclassIsEqual',
    'dataclassIsClose',
    'dataclassRepr',
    'replaceWithNoneIfMissing',
)
#############################
log = getCleanLogger(__name__)

ArrayLike = Union[ndarray, Sequence[Union[float, complex]]]
T = TypeVar('T')


@overload
def replaceWithNoneIfMissing(x: Optional[T]) -> Optional[T]:
  """ typing overload """


@overload
def replaceWithNoneIfMissing(x: Any) -> None:
  """ typing overload """


def replaceWithNoneIfMissing(x: Union[Optional[T], Any]) -> Optional[T]:
  if x is MISSING:
    return None
  else:
    return x
  ##
##


def _robustGetKeyValuePairings(
    lhs: Any,
    rhs: Any,
    ignore_underscores: bool = True,
) -> List[Tuple[Union[str, int], Tuple[Any, Any]]]:
  # Handle dicts/mappings and iterables
  attr_pairs: List[Tuple[Union[str, int], Tuple[Any, Any]]]
  try:
    attr_pairs = []
    for f in fields(lhs):
      k = f.name
      if not hasattr(rhs, k):
        raise ValueError('Objects are not equal')
      ##
      try:
        attr_pairs.append((k, (getattr(lhs, k), getattr(rhs, k))))
      except (AttributeError,):
        continue
      ##
    ##
    return attr_pairs
  except (TypeError,):
    pass
  ##

  try:
    if len(lhs) != len(rhs):
      raise ValueError('Objects are not equal')
    elif len(lhs) == 0:
      return []
    ##
    # Try dict first
    attr_pairs = []
    for k, lv in lhs.items():
      if k not in rhs:
        raise ValueError('Objects are not equal')
      ##
      rv = rhs[k]
      attr_pairs.append((k, (lv, rv,)))
    ##
    return attr_pairs
  except (TypeError, AttributeError,):
    pass
  ##

  # Try iterable next
  try:
    attr_pairs = [(idx, (lv, rv)) for idx, (lv, rv) in enumerate(zip(lhs, rhs))]
    return attr_pairs
  except (TypeError, AttributeError,):
    pass
  ##

  # Fallback to regular equality if all else fails -
  # this is risky as it loses track of the possible recursion
  attr_names = dir(lhs)
  if dir(rhs) != attr_names:
    raise ValueError('Objects are not equal')
  ##
  attr_pairs = []
  for k in attr_names:
    if ignore_underscores and k.startswith('_'):
      continue
    ##
    try:
      attr_pairs.append((k, (getattr(lhs, k), getattr(rhs, k))))
    except Exception as e:
      raise ValueError(f'hello : {e}')
    ##
  ##
  return attr_pairs

##


def _getNamedAttributes(obj: Any,
                        ignore_underscores: bool = True,
                        ignore_methods: bool = True,
                        ) -> Dict[str, Any]:
  # Try dataclass first
  try:
    return {f.name: getattr(obj, f.name) for f in fields(obj)}
  except (TypeError,):
    pass
  ##
  out = {}
  for k in dir(obj):
    if ignore_underscores and k.startswith('_'):
      continue
    ##
    try:
      v = getattr(obj, k)
    except (AttributeError,):
      continue
    ##
    if ignore_methods and inspect.ismethod(v):
      continue
    ##
    out[k] = v
  ##
  return out
##


def dataclassIsEqual(lhs: Any, rhs: Any, ignore_underscore_fields: bool = True) -> bool:
  return _dataclassIsEqual(
      lhs=lhs,
      rhs=rhs,
      ignore_underscore_fields=ignore_underscore_fields,
      ignore_methods=True,
      id_stack=[],
  )
##


_nonaggregate_comparison_types = (type, type(None), bool, str, bytes, bytearray, Fraction, Path, BitGenerator, int, float, complex,)


def _compareSetsWithoutEquality(lhs: AbstractSet[T], rhs: AbstractSet[T]) -> bool:
  if len(lhs) != len(rhs):
    return False
  ##
  for lv in lhs:
    if lv not in rhs:
      return False
    ##
  ##
  return True
##


def _dataclassIsEqual(
    lhs: Any,
    rhs: Any,
    ignore_underscore_fields: bool,
    ignore_methods: bool,
    id_stack: List[Tuple[int, int]],
) -> bool:
  """ Determines if the other value is of the same type and all the fields are exactly equal to each other.

  Parameters
  ----------
  lhs : A dataclass of some type
  rhs: Another value of the same type as lhs or some other type
  ignore_underscore_fields: ignores underscore prefixed fields

  Returns
  -------
  bool : returns True if same type and all the fields are exactly equal, False otherwise

  """
  # Quick upfront checks
  if lhs is rhs:
    return True
  elif not isinstance(rhs, type(lhs)):
    return False
  elif isinstance(lhs, ndarray):
    return numpyEqual(lhs, lhs)
  elif isinstance(lhs, _nonaggregate_comparison_types):
    return lhs == rhs
  elif isinstance(lhs, (set, frozenset,)):
    return _compareSetsWithoutEquality(lhs, rhs)
  elif isinstance(lhs, Rotation) and isinstance(rhs, Rotation):
    return all((lhs.as_quat() == lhs.as_quat()).ravel())
  ##

  # Check for recursion
  id_stack.append((id(lhs), id(rhs)))
  last_ids = id_stack[-1]
  for id_lr in id_stack[:-1]:
    if last_ids == id_lr:
      return True
    ##
    if id_lr[0] == last_ids[0] or id_lr[1] == last_ids[1]:
      # one recurred, but other did not
      return False
    ##
  ##

  try:
    attr_pairs = _robustGetKeyValuePairings(lhs, rhs)
  except ValueError:
    return False
  ##

  # Compare Dataclass fields
  for attr_key, (lhs_val, rhs_val) in attr_pairs:
    if ignore_underscore_fields and isinstance(attr_key, str) and attr_key.startswith('_'):
      continue
    ##
    if lhs_val is rhs_val:
      continue
    ##
    if ignore_methods:
      lhs_is_func = inspect.ismethod(lhs_val)
      rhs_is_func = inspect.ismethod(rhs_val)
      if lhs_is_func and rhs_is_func:
        continue
      elif lhs_is_func or rhs_is_func:
        return False
      ##
    ##
    if isinstance(lhs_val, _nonaggregate_comparison_types):
      is_eq = lhs_val == rhs_val
    elif isinstance(lhs_val, ndarray):
      is_eq = numpyEqual(lhs_val, rhs_val)
    elif isinstance(lhs_val, Rotation) and isinstance(rhs_val, Rotation):
      is_eq = all((lhs_val.as_quat() == rhs_val.as_quat()).ravel())
    else:
      is_eq = _dataclassIsEqual(
          lhs=lhs_val,
          rhs=rhs_val,
          ignore_methods=ignore_methods,
          ignore_underscore_fields=ignore_underscore_fields,
          id_stack=id_stack
      )
    ##
    if not is_eq:
      return False
    ##
  ##
  return True
##


def dataclassIsClose(
    lhs: Any,
    rhs: Any,
    rtol: float = RTOL_DEFAULT,
    atol: float = ATOL_DEFAULT,
    equal_nan: bool = EQUAL_NAN_DEFAULT,
    ignore_underscore_fields: bool = True,
    ignore_methods: bool = True,
) -> bool:
  """ Determines if the other value is the same type and if all the fields are close within a tolerance to each other.

  Parameters
  ----------
  lhs: Any
    A dataclass of some type
  rhs: Any
    Another value of the same type as lhs or some other type
  rtol: float
    Relative tolerance for comparison. Default exhaust_plume.util.numpy_util.RTOL_DEFAULT.
  atol: float
    Absolute tolerance for comparison. Default exhaust_plume.util.numpy_util.ATOL_DEFAULT.
  equal_nan: bool
    Consider NaN values to be equal. Default False.
  ignore_underscore_fields: bool
    ignores underscore prefixed fields when doing comparisons
  ignore_methods: bool
    ignores bound functions

  Returns
  -------
  bool
    True if all fields are close within a tolerance, False otherwise

  """
  if rhs is lhs:
    return True
  elif not isinstance(rhs, type(lhs)):
    return False
  elif isinstance(lhs, (set, frozenset,)):
    return _compareSetsWithoutEquality(lhs, rhs)
  ##
  if rtol is None:
    rtol = RTOL_DEFAULT
  ##
  if atol is None:
    atol = ATOL_DEFAULT
  ##
  if equal_nan is None:
    equal_nan = EQUAL_NAN_DEFAULT
  ##
  try:
    attr_pairs = _robustGetKeyValuePairings(lhs, rhs)
  except ValueError:
    return False
  ##

  for attr_key, (lhs_val, rhs_val) in attr_pairs:
    if ignore_underscore_fields and isinstance(attr_key, str) and attr_key.startswith('_'):
      continue
    ##
    if lhs_val is rhs_val:
      continue
    ##
    if ignore_methods:
      lhs_is_func = inspect.ismethod(lhs_val)
      rhs_is_func = inspect.ismethod(rhs_val)
      if lhs_is_func and rhs_is_func:
        continue
      elif lhs_is_func or rhs_is_func:
        return False
      ##
    ##
    if isinstance(lhs_val, _nonaggregate_comparison_types):
      if rhs_val is None:
        is_close = lhs_val is None
      elif isinstance(lhs_val, (int, float, complex, ndarray,)):
        # all close doesn't like comparing to None
        is_close = numpyAllClose(lhs_val, rhs_val, rtol=rtol, atol=atol, equal_nan=equal_nan)
      else:
        is_close = lhs_val == rhs_val
      ##
    elif isinstance(lhs_val, ndarray):
      is_close = numpyAllClose(lhs_val, rhs_val, rtol=rtol, atol=atol, equal_nan=equal_nan)
    elif isinstance(lhs_val, Rotation) and isinstance(rhs_val, Rotation):
      is_close = areRotationsClose(lhs_val, rhs_val, rtol=rtol, atol=atol, equal_nan=equal_nan)
    else:
      is_close = dataclassIsClose(
          lhs=lhs_val,
          rhs=rhs_val,
          ignore_methods=ignore_methods,
          ignore_underscore_fields=ignore_underscore_fields,
      )
    ##
    if not is_close:
      return False
    ##
  ##
  return True
##


def dataclassRepr(obj: Any) -> str:
  # Really should use a typing extension: Union[DataclassInstance, Type[DataclassInstance]]
  # but I'd really rather not use that dependency here at the moment.
  name2value = _getNamedAttributes(obj)
  args = []
  for k, v in name2value.items():
    args.append(f'{k}={v!r}')
  ##
  out = f'{type(obj).__name__}(' + ", ".join(args) + ")"
  return out
##
