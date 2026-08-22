"""Small numeric helpers shared by the plume model."""

from __future__ import annotations

from typing import Any, TypeVar

import numpy as np
from numpy import ndarray

RTOL_DEFAULT = 1.0e-5
ATOL_DEFAULT = 1.0e-8
EQUAL_NAN_DEFAULT = False

T = TypeVar('T', bound=ndarray)


def makeReadOnly(value: T) -> T:
  """Mark a NumPy array read-only and return the same array."""
  value.flags.writeable = False
  return value


def unitize(value: Any) -> ndarray:
  """Normalize vectors along the final axis, using +x for zero vectors."""
  vectors = np.asarray(value, dtype=float)
  lengths = np.linalg.norm(vectors, axis=-1)
  safe_lengths = lengths + (lengths == 0.0)
  out = vectors / safe_lengths[..., np.newaxis]
  zero = lengths == 0.0
  if out.ndim > 0 and out.shape[-1] > 0:
    out[zero] = 0.0
    out[zero, 0] = 1.0
  return np.asarray(out)


def valuesEqual(lhs: Any, rhs: Any) -> bool:
  """Compare model values without NumPy's ambiguous array truth values."""
  if type(lhs) is not type(rhs):
    return False
  if isinstance(lhs, ndarray):
    return lhs.shape == rhs.shape and bool(np.array_equal(lhs, rhs, equal_nan=False))
  if isinstance(lhs, (list, tuple)):
    return len(lhs) == len(rhs) and all(valuesEqual(a, b) for a, b in zip(lhs, rhs))
  try:
    result = lhs == rhs
  except (TypeError, ValueError):
    return False
  return bool(result) if not isinstance(result, ndarray) else bool(np.all(result))


def valuesClose(lhs: Any, rhs: Any, *, rtol: float, atol: float, equal_nan: bool) -> bool:
  """Compare scalar, array, and nested model values within a tolerance."""
  if type(lhs) is not type(rhs):
    return False
  if isinstance(lhs, ndarray):
    return lhs.shape == rhs.shape and bool(np.allclose(lhs, rhs, rtol=rtol, atol=atol, equal_nan=equal_nan))
  if isinstance(lhs, (list, tuple)):
    return len(lhs) == len(rhs) and all(valuesClose(a, b, rtol=rtol, atol=atol, equal_nan=equal_nan) for a, b in zip(lhs, rhs))
  try:
    return bool(np.isclose(lhs, rhs, rtol=rtol, atol=atol, equal_nan=equal_nan))
  except (TypeError, ValueError):
    return valuesEqual(lhs, rhs)
