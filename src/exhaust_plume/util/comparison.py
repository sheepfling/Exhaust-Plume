"""Focused dataclass comparisons for immutable scientific result types."""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from typing import Any

from exhaust_plume.util.numeric import ATOL_DEFAULT, EQUAL_NAN_DEFAULT, RTOL_DEFAULT, valuesClose, valuesEqual


def _field_pairs(lhs: Any, rhs: Any) -> tuple[tuple[Any, Any], ...] | None:
  if not is_dataclass(lhs) or not is_dataclass(rhs) or type(lhs) is not type(rhs):
    return None
  ####
  return tuple((getattr(lhs, field.name), getattr(rhs, field.name)) for field in fields(lhs))
####


def dataclassIsEqual(lhs: Any, rhs: Any) -> bool:
  if lhs is rhs:
    return True
  ####
  pairs = _field_pairs(lhs, rhs)
  if pairs is None:
    return valuesEqual(lhs, rhs)
  ####
  return all(valuesEqual(left, right) for left, right in pairs)
####


def dataclassIsClose(lhs: Any, rhs: Any, *, rtol: float = RTOL_DEFAULT, atol: float = ATOL_DEFAULT, equal_nan: bool = EQUAL_NAN_DEFAULT) -> bool:
  if lhs is rhs:
    return True
  ####
  pairs = _field_pairs(lhs, rhs)
  if pairs is None:
    return valuesClose(lhs, rhs, rtol=rtol, atol=atol, equal_nan=equal_nan)
  ####
  return all(valuesClose(left, right, rtol=rtol, atol=atol, equal_nan=equal_nan) for left, right in pairs)
####
