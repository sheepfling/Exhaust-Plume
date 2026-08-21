# -*- coding: utf-8 -*-
# DOCME
from __future__ import annotations

import sys
from dataclasses import dataclass, field as Field
from traceback import format_exception
from types import TracebackType
from typing import Any, Dict, Tuple, Type, Union

__all__ = (
    'ExceptionInfo',
    'SysExcInfo',
)
#######################
SysExcInfo = Union[Tuple[Type[BaseException], BaseException, TracebackType], Tuple[None, None, None]]
# auto generated / inferred from sys.exc_info


@dataclass(frozen=True)
class ExceptionInfo:
  """ Helper class to hold exceptions and grab traceback information for debugging purposes """
  exception: Exception
  exc_info: SysExcInfo = Field(init=False, default_factory=sys.exc_info)

  def __str__(self) -> str:
    out = f'{type(self).__name__}(exception={self.exception!r}, exc_info={self.getFormattedException()!r})'
    return out
  ##

  def getFormattedException(self) -> str:
    """ Helper function to get formatted traceback & exception info

    @return: formatted string
    """
    return ''.join(format_exception(*self.exc_info))
  ##

  def __getstate__(self) -> Dict[str, Any]:
    """ Gets the state dictionary for pickling.
    Traceback objects are not pickle-able, so remove from exc_info tuple

    @return: dictionary of class states
    """
    state = self.__dict__.copy()
    if 'exc_info' in state:
      state['exc_info'] = state['exc_info'][:2] + (None,)
    ##
    return state
  ##
##
