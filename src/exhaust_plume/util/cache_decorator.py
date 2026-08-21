# - * - coding: utf - 8 - *-
"""
Provides a built-in cache wrapper or the patched cache if python <=3.7
"""
from __future__ import annotations

try:
  from functools import cache  # type: ignore  # In python <=3.7 this doesn't exist
except (ImportError, ModuleNotFoundError):  # pragma: no cover
  from exhaust_plume.util.cache_decorator_patch import cache  # pragma: no cover
##


__all__ = (
    'cache',
)
################
