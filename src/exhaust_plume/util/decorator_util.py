# -*- coding: utf-8 -*-
# DOCME
from __future__ import annotations

from functools import wraps
from typing import Callable, TypeVar, cast

from exhaust_plume.log.log import getCleanLogger
from exhaust_plume.util.type_hints import ParamSpec

__all__ = (
    'doublewrap',
)
######################
log = getCleanLogger(__name__)

P = ParamSpec('P')
T = TypeVar('T')


def doublewrap(decorator: Callable[P, T]) -> Callable[P, T]:  # type: ignore[misc,valid-type] # as of mypy 0.991 ParamSpec is not supported in Callable
  """ Decorates a decorator, allowing the decorator to be used as
  @decorator
    or
  @decorator(*args, **kwargs)

  With one caveat: The decorator assumes that when given positional arguments,
  the argument is not a callable, As that would be indistinguishable from the no arguments case.

  The doublewrap'd decorator should have the signature
  def decorator(func: C, *args, **kwargs) -> C:
  """
  @wraps(decorator)
  def wrapped_decorator(*args: object, **kwargs: object) -> Callable[P, T]:  # type: ignore[misc,valid-type] # as of mypy 0.991 ParamSpec is not supported in Callable
    if len(args) == 1 and len(kwargs) == 0 and callable(args[0]):
      # @decorator => decorator(func)
      # args[0] = function to be decorated
      inner_decorator = cast(Callable[P, T], decorator(args[0]))  # type: ignore[misc,valid-type] # as of mypy 0.991 ParamSpec is not supported in Callable
      return inner_decorator
    else:
      # @decorator(*a, **kw) => decorator(*a,**kw)(func)
      def outer_decorator(f: Callable[P, T]) -> Callable[P, T]:  # type: ignore[misc,valid-type] # as of mypy 0.991 ParamSpec is not supported in Callable
        return decorator(f, *args, **kwargs)
      ##
      return outer_decorator
    ##
  ##
  return wrapped_decorator
##
