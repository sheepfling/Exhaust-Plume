# -*- coding: utf-8 -*-
# DOCME
from __future__ import annotations

__all__ = (
    'UnsetType',
    'Unset',
)
#################################


class UnsetType:

  def __copy__(self) -> UnsetType:
    return Unset
  ##

  def __deepcopy__(self, memo: object) -> UnsetType:
    return Unset
  ##
##


Unset = UnsetType()
