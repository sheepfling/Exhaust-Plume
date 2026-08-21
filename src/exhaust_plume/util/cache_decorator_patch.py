# - * - coding: utf - 8 - *-
# DOCME
from __future__ import annotations

from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable, Dict, Hashable, Optional

__all__ = (
    'cache',
    'CacheInfo',
)
##################


@dataclass(frozen=True)
class CacheInfo:
  # DOCME
  hits: int
  misses: int
  maxsize: Optional[int]
  currsize: int
##


class _Cache:

  # DOCME

  def __init__(self, func: Callable):
    # DOCME
    self.__hits = 0
    self.__misses = 0
    self.__typed: bool = False  # Unsupported for py3.7 patch
    self.__maxsize = None  # Unsupported for py3.7 patch
    self.__cache: Dict[Hashable, Any] = {}
    self.__func = func
  ##

  def cache_clear(self) -> None:
    # DOCME
    self.__cache.clear()
    self.__hits = 0
    self.__misses = 0
  ##

  def cache_info(self) -> CacheInfo:
    # DOCME
    out = CacheInfo(
        hits=self.__hits,
        misses=self.__misses,
        maxsize=self.__maxsize,
        currsize=len(self.__cache)
    )
    return out
  ##

  def __call__(self, *args: object, **kwargs: object) -> Any:  # type: ignore[no-untyped-def]
    # This really would call for typing.ParamSpec, but that  isn't available until python >=3.10
    # DOCME
    key = (tuple(args), tuple(kwargs.items()),)
    if key in self.__cache:
      self.__hits += 1
      return self.__cache[key]
    ##
    self.__misses += 1
    out = self.__func(*args, **kwargs)
    self.__cache[key] = out
    return out
  ##
##


def cache(func):  # type: ignore[no-untyped-def]
  """ Decorator to add a simple cache for the function. Patches missing capability in python 3.7  """
  local_cache = _Cache(func)  # type: ignore[no-untyped-call]

  @wraps(func)
  def wrapper(*a, **kw: object):  # type: ignore[no-untyped-def]
    # DOCME
    return local_cache(*a, **kw)
  ##
  setattr(wrapper, 'cache_clear', local_cache.cache_clear)
  setattr(wrapper, 'cache_info', local_cache.cache_info)
  return wrapper
##
