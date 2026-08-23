# -*- coding: utf-8 -*-
# DOCME
from __future__ import annotations

import logging
from logging import CRITICAL, DEBUG, ERROR, INFO, NOTSET, WARNING
from typing import Dict, Optional

__all__ = (
    'CRITICAL',
    'ERROR',
    'WARNING',
    'INFO',
    'DEBUG',
    'NOTE',
    'CONFIG',
    'STATUS',
    'VERBOSE',
    'TRACE',
    'TRACE_EXTRA',
    'NOTSET',
    'getNameFromLevel',
    'setDefaultLogLevels',
)

# Initial desired levels, but if already defined by logger then these are updated to whatever already exists.
STATUS = max(1, logging.DEBUG - 1)
NOTE = max(1, STATUS - 1)
CONFIG = max(1, NOTE - 1)
VERBOSE = max(1, CONFIG - 1)
TRACE = max(1, VERBOSE - 1)
TRACE_EXTRA = max(1, TRACE - 1)

_name2level = {
    'STATUS': STATUS,
    'NOTE': NOTE,
    'CONFIG': CONFIG,
    'VERBOSE': VERBOSE,
    'TRACE': TRACE,
    'TRACE_EXTRA': TRACE_EXTRA,
}
_level2name: Dict[int, str] = {}


def getNameFromLevel(level: int) -> Optional[str]:
  try:
    return _level2name[level]
  except KeyError:
    return None
  ####
####


def setDefaultLogLevels() -> None:
  # Forces log levels to be default
  global STATUS
  global NOTE
  global CONFIG
  global VERBOSE
  global TRACE
  global TRACE_EXTRA
  STATUS = max(1, logging.DEBUG - 1)
  NOTE = max(1, STATUS - 1)
  CONFIG = max(1, NOTE - 1)
  VERBOSE = max(1, CONFIG - 1)
  TRACE = max(1, VERBOSE - 1)
  TRACE_EXTRA = max(1, TRACE - 1)
  _name2level.update({
      'STATUS': STATUS,
      'NOTE': NOTE,
      'CONFIG': CONFIG,
      'VERBOSE': VERBOSE,
      'TRACE': TRACE,
      'TRACE_EXTRA': TRACE_EXTRA,
  })
  _createExtraLevels(override_existing=True)
####


def _createExtraLevels(override_existing: bool = False) -> None:
  for name, level in _name2level.items():
    logging_level = logging.getLevelName(name)
    # If already exists, then returns a number(int), otherwise it returns a string
    if not isinstance(logging_level, int) or override_existing:
      # does not exist, so add new level name
      logging.addLevelName(level, name)
    else:
      # already exists, so update
      _name2level[name] = logging_level
    ####
  ####
  # Re-adjust _level2name
  _level2name.update({level: name for name, level in _name2level.items()})
####


_createExtraLevels()

# Re-pull constants back out of mapping
STATUS = _name2level['STATUS']
NOTE = _name2level['NOTE']
CONFIG = _name2level['CONFIG']
VERBOSE = _name2level['VERBOSE']
TRACE = _name2level['TRACE']
TRACE_EXTRA = _name2level['TRACE_EXTRA']
