# -*- coding: utf-8 -*-
# DOCME
from __future__ import annotations

from exhaust_plume.util.regex_util import nonword_rgx, whitespace_rgx

__all__ = (
    'normalizeEnumNameForMapping',
)
#######################


def normalizeEnumNameForMapping(s: str) -> str:
  # Removes all non word characters and whitespaces and lowers the case
  out = ''.join(whitespace_rgx.split(''.join(nonword_rgx.split(s)))).lower()
  return out
##
