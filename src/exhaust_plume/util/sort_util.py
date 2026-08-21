# -*- coding: utf-8 -*-
# DOCME
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Generic, Iterable, Iterator, List, Optional, Sequence, Tuple, TypeVar

from exhaust_plume.log.log import getCleanLogger
from exhaust_plume.util.misc import tryIntOrDefault

__all__ = (
    'argsorted',
    'SortedIntablesAndOtherResult',
    'getSortedIntablesAndOther',
    'isSorted',
    'isStrictlyIncreasing',
    'binarySearchSortedArray',
)
##########################
log = getCleanLogger(__name__)

# If python >=3.7 then typing.Protocol is available otherwise just using generic type var T
T = TypeVar('T')


def _wrapKey(key: Callable[[T], Any]) -> Callable[[Tuple[int, T]], Any]:
  # wrap in closure where key is not optional (for type checker)
  def key_wrapped(idx_value: Tuple[int, T]) -> Any:
    # DOCME
    return key(idx_value[1])
  ##
  return key_wrapped
##


def argsorted(values: Iterable[T], key: Optional[Callable[[T], Any]] = None, reverse: bool = False) -> Tuple[List[T], List[int]]:
  # DOCME
  if key is None:
    def unpackIndexValue(idx_value: Tuple[int, T]) -> Any:
      # DOCME
      return idx_value[1]
    ##
    key_wrapped: Callable[[Tuple[int, T]], Any] = unpackIndexValue
  else:
    key_wrapped = _wrapKey(key)
  ##
  sorted_enumeration = sorted(((idx, v) for idx, v in enumerate(values)), key=key_wrapped, reverse=reverse)
  sorted_values = [val for index, val in sorted_enumeration]
  sorted_index = [index for index, value in sorted_enumeration]
  out = (sorted_values, sorted_index,)
  return out
##


@dataclass
class SortedIntablesAndOtherResult(Generic[T]):
  # DOCME
  intable: List[T]
  other: List[T]

  def __iter__(self) -> Iterator[T]:
    yield from self.intable
    yield from self.other
  ##
##


def getSortedIntablesAndOther(values: Iterable[T], key: Optional[Callable[[T], Any]] = None, reverse: bool = False) -> SortedIntablesAndOtherResult[T]:
  # DOCME
  actual_int_list: List[int] = []
  could_be_int_list: List[T] = []
  other_list: List[T] = []
  for item in values:
    int_val = tryIntOrDefault(item, None)
    if int_val is None:
      other_list.append(item)
    else:
      actual_int_list.append(int_val)
      could_be_int_list.append(item)
    ##
  ##
  other_list.sort(key=key, reverse=reverse)
  _, argidx = argsorted(actual_int_list, reverse=reverse)
  could_be_int_list = [could_be_int_list[idx] for idx in argidx]
  out = SortedIntablesAndOtherResult(
      intable=could_be_int_list,
      other=other_list
  )
  return out
##


def isSorted(x: Iterable, key: Optional[Callable] = None, reverse: bool = False) -> bool:
  x = tuple(x)
  if key is None:
    sorted_x = tuple(sorted(x, reverse=reverse))
  else:
    sorted_x = tuple(sorted(x, key=key, reverse=reverse))
  ##
  return x == sorted_x
##


def isStrictlyIncreasing(x: Iterable) -> bool:
  """ Every element must be greater than previous element """
  x = tuple(x)
  for x0, x1 in zip(x[:-1], x[1:]):
    if x0 >= x1:
      return False
    ##
  ##
  return True
##


def binarySearchSortedArray(value: object, sorted_table: Sequence) -> Optional[int]:
  """ Binary searches ascended sorted table.
  Returns the left edge index. That is for (1.5, range(10)) -> 1
  Returns None if table is None or value is beyond edges of tale. """
  if len(sorted_table) <= 0 or (value < sorted_table[0]) or (value > sorted_table[-1]):
    return None
  ##
  if value == sorted_table[0]:
    return 0
  elif value == sorted_table[-1]:
    return len(sorted_table) - 1
  ##
  lb = 0
  rb = len(sorted_table) - 1
  mid_idx = (lb + rb) // 2
  while lb + 1 < rb:
    if value < sorted_table[mid_idx]:
      rb = mid_idx
    else:
      lb = mid_idx
    ##
    mid_idx = (lb + rb) // 2
  ##
  return mid_idx
##
