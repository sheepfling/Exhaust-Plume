"""Small runtime guards shared by public contract models."""

from __future__ import annotations

from typing import Any


def iter_nested_values(value: Any):
  if isinstance(value, (tuple, list)):
    for item in value:
      yield from iter_nested_values(item)
  else:
    yield value
####


def contains_boolean(value: Any) -> bool:
  """Return whether a nested tuple/list contains a Python boolean."""

  return any(isinstance(item, bool) for item in iter_nested_values(value))
####


def contains_non_boolean(value: Any) -> bool:
  """Return whether a nested tuple/list contains a non-boolean leaf."""

  return any(not isinstance(item, bool) for item in iter_nested_values(value))
####


__all__ = ('contains_boolean', 'contains_non_boolean', 'iter_nested_values')
