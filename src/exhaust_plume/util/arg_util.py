# -*- coding: utf-8 -*-
# DOCME
from __future__ import annotations

from argparse import ArgumentParser, ArgumentTypeError, Namespace
from typing import Any, Callable, Optional, Type, TypeVar

from exhaust_plume.log.log import getCleanLogger

__all__ = (
    'ArgumentParser',
    'Namespace',
    'getRangeLimitedType',
    'ArgumentTypeError',
)
log = getCleanLogger(__name__)

T = TypeVar('T')


def getRangeLimitedType(typ: Type[T], min_val: Optional[Any] = None, max_val: Optional[Any] = None,
                        min_is_valid: bool = True, max_is_valid: bool = True
                        ) -> Callable[[Any], T]:
  # DOCME
  def limited_type(arg: object) -> T:
    """ Type function for argparse - a float within some predefined bounds """
    try:
      f = typ(arg)  # type: ignore
    except Exception as e:
      raise ArgumentTypeError(f"Argument:{arg} must be convertible using:{typ}") from e
    ####
    min_valid = min_val is None or (f >= min_val if min_is_valid else f > min_val)
    max_valid = max_val is None or (f <= max_val if max_is_valid else f < max_val)
    min_violation = not min_valid
    max_violation = not max_valid
    if min_violation or max_violation:
      msg = [f"Argument:{arg} must be", ]
      if max_val is not None:
        if max_is_valid:
          msg.append(f" <={max_val}")
        else:
          msg.append(f" <{max_val}")
        ####
      ####
      if min_val is not None:
        if len(msg) > 1:
          msg.append(" and")
        ####
        if min_is_valid:
          msg.append(f" >={min_val}")
        else:
          msg.append(f" >{min_val}")
        ####
      ####
      raise ArgumentTypeError(''.join(msg))
    ####
    return f
  ####
  return limited_type
####
