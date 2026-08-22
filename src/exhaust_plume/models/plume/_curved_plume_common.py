"""Shared validation and NumPy typing helpers for curved-plume modules."""

from __future__ import annotations

from typing import TypeAlias

import numpy as np
from numpy.typing import ArrayLike, NDArray

FloatArray: TypeAlias = NDArray[np.float64]


def _validateFinite(name: str, value: float) -> float:
  value_float = float(value)
  if not np.isfinite(value_float):
    raise ValueError(f'Expected `{name}` to be finite. Got:{value}')
  ####
  return value_float
####


def _validatePositiveFinite(name: str, value: float) -> float:
  value_float = _validateFinite(name, value)
  if value_float <= 0.:
    raise ValueError(f'Expected `{name}` to be greater than zero. Got:{value}')
  ####
  return value_float
####


def _validateNonnegativeFinite(name: str, value: float) -> float:
  value_float = _validateFinite(name, value)
  if value_float < 0.:
    raise ValueError(f'Expected `{name}` to be nonnegative. Got:{value}')
  ####
  return value_float
####


def _asReadOnlyVector3(name: str, value: ArrayLike) -> FloatArray:
  array = np.asarray(value, dtype=float)
  if array.shape != (3,):
    raise ValueError(f'Expected `{name}` to have shape (3,). Got:{array.shape}')
  ####
  if not np.isfinite(array).all():
    raise ValueError(f'Expected `{name}` to contain finite values. Got:{array}')
  ####
  out = np.array(array, dtype=float, copy=True)
  out.flags.writeable = False
  return out
####


def _asReadOnlyArray(name: str, value: ArrayLike) -> FloatArray:
  array = np.asarray(value, dtype=float)
  if not np.isfinite(array).all():
    raise ValueError(f'Expected `{name}` to contain finite values.')
  ####
  out = np.array(array, dtype=float, copy=True)
  out.flags.writeable = False
  return out
####


def _unitVector(name: str, value: ArrayLike) -> FloatArray:
  vector = _asReadOnlyVector3(name, value)
  magnitude = float(np.linalg.norm(vector))
  if magnitude <= 0.:
    raise ValueError(f'Expected `{name}` to be non-zero.')
  ####
  return _asReadOnlyVector3(name, vector / magnitude)
####
