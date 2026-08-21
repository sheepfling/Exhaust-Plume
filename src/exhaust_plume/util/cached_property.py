# - * - coding: utf - 8 - *-
"""
Provides a built-in cache wrapper or the patched cached_property if python <=3.7
"""
from __future__ import annotations

HAS_BUILTIN_FUNCTOOLS_CACHED_PROPERTY: bool = False
try:
  from functools import cached_property  # type: ignore

  # In python <=3.7 this doesn't exist

  HAS_BUILTIN_FUNCTOOLS_CACHED_PROPERTY = True
except (ImportError, ModuleNotFoundError):  # pragma: no cover
  from exhaust_plume.util.cached_property_patch import cached_property  # type: ignore[misc,assignment] # pragma: no cover
##


__all__ = (
    'cached_property',
    'HAS_BUILTIN_FUNCTOOLS_CACHED_PROPERTY',
)
