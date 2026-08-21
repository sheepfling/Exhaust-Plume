# -*- coding: utf-8 -*-
# DOCME
from __future__ import annotations

import re
from typing import AbstractSet, Any, Dict, Mapping

__all__ = (
    'isFieldnameIgnorable',
    'hasNonIgnorableConfig',
    'getNonIgnorableConfig',
)
#####################

_config_fieldname_ignore_extra_pattern = '^_'
_config_fieldname_ignore_extra_rgx = re.compile(_config_fieldname_ignore_extra_pattern)


def isFieldnameIgnorable(fieldname: str) -> bool:
  # DOCME
  match = _config_fieldname_ignore_extra_rgx.match(fieldname)
  out = bool(match)
  return out
##


def hasNonIgnorableConfig(config: Mapping[str, Any], keys_used: AbstractSet[str] = frozenset()) -> bool:
  # DOCME
  try:
    for k, v in config.items():
      if isFieldnameIgnorable(k) or k in keys_used:
        continue
      ##
      return True
    ##
  except AttributeError:
    pass
  ##
  return False
##


def getNonIgnorableConfig(config: Mapping[str, Any]) -> Dict[str, Any]:
  # DOCME
  out = {}
  for k, v in config.items():
    if isFieldnameIgnorable(k):
      continue
    ##
    out[k] = v
  ##
  return out
##
