# -*- coding: utf-8 -*-
# DOCME
from __future__ import annotations

from typing import Any, Dict, Hashable, Iterable, List, Mapping, Optional, Sequence, TypeVar, Union, overload

from numpy import allclose, arctan2, cos, cross, eye, finfo, inf, isfinite, isnan, logical_and, logical_or, nan, ndarray, nextafter, sin
from numpy.linalg import norm
from scipy.spatial.transform import Rotation

from exhaust_plume.log.log import getCleanLogger
from exhaust_plume.util.numpy_util import ATOL_DEFAULT, EQUAL_NAN_DEFAULT, RTOL_DEFAULT, getOrthonormalBasis, numpyAllClose

__all__ = (
    'tryFloatOrNan',
    'tryFloatOrDefault',
    'tryIntOrDefault',
    'popOrNone',
    'popOrThrow',
    'listIsClose',
    'dictIsClose',
    'deduplicateStable',
    'getVectorRotation',
    'isPositionStationary',
    'isOrientationStationary',
    'getEps',
    'getEpsAbove',
    'getEpsBelow',
    'isEqualOrBothNan',
    'makeOdd',
    'makeEven',
)
####################################################
log = getCleanLogger(__name__)

T = TypeVar('T')
K = TypeVar('K')
V = TypeVar('V')


def popOrThrow(d: Dict[K, V], k: K, debug_config_prefix: str = '') -> V:
  if k not in d:
    raise ValueError(f'{debug_config_prefix}: `{k}` must be supplied.')
  ##
  return d.pop(k)
##


def popOrNone(d: Dict[K, V], k: K) -> Optional[V]:
  # DOCME
  # pop'ing from defaultdict throws a KeyError, so this is done instead
  return d.pop(k) if k in d else None
##


@overload
def tryFloatOrDefault(x: Any, val: None = None) -> Optional[float]:
  """ tryFloatOrDefault overload for defaulted value None """


@overload
def tryFloatOrDefault(x: Any, val: T) -> Optional[Union[float, T]]:
  """ tryFloatOrDefault overload for specified value """


def tryFloatOrDefault(x: Any, val: Optional[T] = None) -> Optional[Union[float, T]]:
  # DOCME
  try:
    return float(x)
  except (ValueError, TypeError,):
    return val
  ##
##


@overload
def tryIntOrDefault(x: Any, val: None = None) -> Optional[int]:
  """ tryIntOrDefault overload for defaulted value None """


@overload
def tryIntOrDefault(x: Any, val: T) -> Optional[Union[int, T]]:
  """ tryIntOrDefault overload for specified value """


def tryIntOrDefault(x: Any, val: Optional[T] = None) -> Optional[Union[int, T]]:
  # DOCME
  try:
    return int(x)
  except (ValueError, TypeError,):
    return val
  ##
##


def isIntable(x: Any) -> bool:
  try:
    int(x)
    return True
  except (ValueError, TypeError,):
    return False
  ##
##


def tryFloatOrNan(x: Any) -> float:
  # DOCME
  out = tryFloatOrDefault(x)
  if out is None:
    return nan
  else:
    return out
  ##
##


def _isClose(lhs: Any, rhs: Any, rtol: float = RTOL_DEFAULT, atol: float = ATOL_DEFAULT, equal_nan: bool = EQUAL_NAN_DEFAULT) -> bool:
  # DOCME
  if lhs == rhs:
    return True
  ##
  if not isinstance(lhs, type(rhs)):
    return False
  ##
  if hasattr(lhs, 'isClose'):
    try:
      if lhs.isClose(rhs, rtol=rtol, atol=atol, equal_nan=equal_nan):
        return True
      ##
    except (TypeError,):
      # Can fail
      pass
    ##
  ##
  if isinstance(lhs, (float, complex, int, ndarray)):
    if numpyAllClose(lhs, rhs, rtol=rtol, atol=atol, equal_nan=equal_nan):
      return True
    ##
  ##
  try:
    if dictIsClose(lhs, rhs, rtol=rtol, atol=atol, equal_nan=equal_nan):
      return True
    ##
  except (TypeError, AttributeError,):
    # Type or Attribute means one of them was not a dict
    pass
  ##
  try:
    if listIsClose(lhs, rhs, rtol=rtol, atol=atol, equal_nan=equal_nan):
      return True
    ##
  except (TypeError, AttributeError,):
    # Type or Attribute means one of them was not a dict
    pass
  ##
  # Nothing compared close, so False
  return False
##


def listIsClose(lhs: Sequence[Any], rhs: Sequence[Any], rtol: float = RTOL_DEFAULT, atol: float = ATOL_DEFAULT, equal_nan: bool = EQUAL_NAN_DEFAULT) -> bool:
  # DOCME
  if lhs == rhs:
    return True
  ##
  if len(lhs) != len(rhs):
    return False
  ##
  for lhs_val, rhs_val in zip(lhs, rhs):
    if lhs_val == rhs_val:
      continue
    ##
    if not isinstance(lhs_val, type(rhs_val)):
      return False
    ##
    if hasattr(lhs_val, 'isClose'):
      try:
        if not lhs_val.isClose(rhs_val, rtol=rtol, atol=atol, equal_nan=equal_nan):
          return False
        ##
      except (TypeError,):
        # Can fail
        pass
      ##
      continue
    ##
    if isinstance(lhs_val, (float, complex, int, ndarray)):
      if not numpyAllClose(lhs_val, rhs_val, rtol=rtol, atol=atol, equal_nan=equal_nan):
        return False
      ##
      continue
    ##
    try:
      if not dictIsClose(lhs_val, rhs_val, rtol=rtol, atol=atol, equal_nan=equal_nan):
        return False
      ##
      continue
    except (TypeError, AttributeError,):
      pass
    ##
    try:
      if not listIsClose(lhs_val, rhs_val, rtol=rtol, atol=atol, equal_nan=equal_nan):
        return False
      ##
      continue
    except (TypeError, AttributeError,):
      pass
    ##
  ##
  return True
##


def dictIsClose(lhs: Mapping[Hashable, Any], rhs: Mapping[Hashable, Any], rtol: float = RTOL_DEFAULT, atol: float = ATOL_DEFAULT, equal_nan: bool = EQUAL_NAN_DEFAULT) -> bool:
  """ Returns True if all fields are close within a tolerance, False otherwise
  """
  if lhs == rhs:
    return True
  elif not isinstance(rhs, type(lhs)) or len(lhs) != len(rhs):
    return False
  ##
  keys = lhs.keys()
  for k in keys:
    if k not in rhs:
      return False
    ##
    lhs_val = lhs[k]
    rhs_val = rhs[k]
    if not isinstance(lhs_val, type(rhs_val)):
      return False
    ##
    if hasattr(lhs_val, 'isClose'):
      try:
        if not lhs_val.isClose(rhs_val, rtol=rtol, atol=atol, equal_nan=equal_nan):
          return False
        ##
        continue
      except (TypeError,):
        # Can fail
        pass
      ##
    ##
    if isinstance(lhs_val, (ndarray, float)):
      if not numpyAllClose(lhs_val, rhs_val, rtol=rtol, atol=atol, equal_nan=equal_nan):
        return False
      ##
      continue
    ##
    try:
      if not dictIsClose(lhs_val, rhs_val, rtol=rtol, atol=atol, equal_nan=equal_nan):
        return False
      ##
      continue
    except (TypeError, AttributeError,):
      # If can't
      pass
    ##
    try:
      if not listIsClose(lhs_val, rhs_val, rtol=rtol, atol=atol, equal_nan=equal_nan):
        return False
      ##
      continue
    except (TypeError, AttributeError,):
      # If can't
      pass
    ##
    return False
  ##
  return True
##


def deduplicateStable(values: Iterable[T]) -> List[T]:
  """ De-duplicates values while keeping them in order
  tuple(set(list(values))) is not stable sorting-wise and also requires the values to be hashable
  """
  out: List[T] = []
  for val in values:
    if val not in out:
      out.append(val)
    ##
  ##
  return out
##


def getVectorRotation(v_start: ndarray, v_end: ndarray) -> Rotation:
  """ Gets q Rotation so that
  v_end = q.apply(v_start)
  """
  if allclose(v_start, v_end):
    return Rotation.identity()
  ##
  crs = cross(v_start, v_end)
  dt = v_start @ v_end
  crs_norm = norm(crs)
  if crs_norm == 0.:
    # co-axial
    if dt >= 0:
      # Identity
      return Rotation.identity()
    else:
      # TODO - recheck this - check for negated (and scaled) and check
      # 180', pick an axis that's not v_start, so it's necessary to find
      # a new axis
      new_basis = getOrthonormalBasis([v_start, *eye(3)])
      q = Rotation.from_quat([*new_basis[1], 0.])
    ##
  else:
    n = crs / norm(crs, axis=-1, keepdims=True)
    th = arctan2(crs_norm, dt)
    im = n * sin(th / 2.)
    re = cos(th / 2.)
    q = Rotation.from_quat([*im, re])
  ##
  return q
##


def isPositionStationary(positions_m: ndarray, threshold_m: float = 100.) -> bool:
  avg_position_m = positions_m.mean(axis=0)
  position_offsets = norm(positions_m - avg_position_m, axis=-1).ravel()
  return all(isfinite(position_offsets)) and all(position_offsets <= threshold_m)
##


def isOrientationStationary(orientations: ndarray, threshold_m: float = 1e-8) -> bool:
  if orientations.size == 4:
    return True
  ##
  orientations = orientations.copy()
  # Flip all quats to be the same sign for scalar portion
  # this probably isn't 100% correct, but it's close enough
  orientations[orientations[..., -1] < 0, ...] *= -1
  avg_ori = orientations.mean(axis=0)
  ori_offsets = norm(orientations - avg_ori, axis=-1).ravel()
  return all(isfinite(ori_offsets)) and all(ori_offsets <= threshold_m)
##


float_info = finfo(float)
EPS1 = float(float_info.eps)
SMALLEST_NORMAL = float(finfo(float).tiny)


def getEps(f: float) -> float:
  if f != 0:
    return float(abs(f) * EPS1)
  else:
    return SMALLEST_NORMAL
  ##
##


def getEpsAbove(f: float) -> float:
  return nextafter(f, inf)
##


def getEpsBelow(f: float) -> float:
  return nextafter(f, -inf)
##


def isEqualOrBothNan(lhs: Union[int, float, complex, ndarray], rhs: Union[int, float, complex, ndarray]) -> bool:
  if isinstance(lhs, int) and isinstance(rhs, int):
    return lhs == rhs
  ##
  if isinstance(lhs, (float, complex,)) and isinstance(rhs, (float, complex,)):
    return (lhs == rhs) or bool(isnan(lhs) and isnan(rhs))
  ##
  if isinstance(lhs, ndarray) and isinstance(rhs, ndarray):
    if lhs.shape != rhs.shape:
      return False
    ##
    lgc = logical_or((lhs == rhs), logical_and(isnan(lhs), isnan(rhs)))
    return all(lgc.ravel())
  ##
  return False
##


def makeOdd(n: Union[int, float]) -> int:
  n = int(n)
  return n + (n % 2 == 0)
##


def makeEven(n: Union[int, float]) -> int:
  n = int(n)
  return n + (n % 2 != 0)
##
