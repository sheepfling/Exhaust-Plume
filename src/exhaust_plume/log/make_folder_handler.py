# -*- coding: utf-8 -*-
# DOCME
from __future__ import annotations

from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from exhaust_plume.util.type_hints import PathLike

#############################
__all__ = (
    'MakeFolderHandler',
)


class MakeFolderHandler(RotatingFileHandler):
  """ Wraps RotatingFileHandler with a mkdir call to ensure that the parent directory exists. """

  def __init__(self, filename: PathLike, mode: str = 'a', maxBytes: int = 0, backupCount: int = 0,
               encoding: Optional[str] = None, delay: bool = False, errors: Optional[str] = None, ):
    f""" Args are same as {RotatingFileHandler.__name__} and are just passed along """
    filename = Path(filename)
    filename.parent.mkdir(exist_ok=True, parents=True)
    try:
      RotatingFileHandler.__init__(
          self, filename, mode=mode, maxBytes=maxBytes, backupCount=backupCount,
          encoding=encoding, delay=delay, errors=errors, )
    except TypeError:
      # errors arg added in python 3.9
      RotatingFileHandler.__init__(
          self, filename, mode=mode, maxBytes=maxBytes, backupCount=backupCount,
          encoding=encoding, delay=delay, )
    ##
  ##
##
