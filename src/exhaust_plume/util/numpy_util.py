# -*- coding: utf-8 -*-
""" This module contains some numpy utilities"""
from __future__ import annotations

import warnings
from itertools import chain, product
from typing import Any, List, Optional, Sequence, Tuple, TypeVar, Union

import numpy as np
from numpy import allclose, asarray, concatenate, isclose, ndarray, newaxis, nonzero, prod, sqrt, vstack, zeros
from numpy.linalg import LinAlgError, cholesky, norm
from scipy.spatial.transform import Rotation

from exhaust_plume.log.log import getCleanLogger
from exhaust_plume.util.geometry_util import getSignedAreaOfTriangle
from exhaust_plume.util.type_hints import ArrayLike, ComplexArrayLike, ComplexArrayOrComplexNumberLike

__all__ = (
    'numpyEqual',
    'numpyAllClose',
    'unitize',
    'isGrid',
    'getOrthonormalBasis',
    'getBarycentricTriangleCoordinates2D',
    'isPointWithinTriangle2D',
    'dot2',
    'find0',
    'areRotationsClose',
    'fullCovarianceFromUpperTriangularVector',
    'upperTriangularVectorFromFullCovariance',
    'RTOL_DEFAULT',
    'ATOL_DEFAULT',
    'EQUAL_NAN_DEFAULT',
    'isHermitian',
    'isPositiveSemiDefinite',
    'makeReadOnly',
)
############################
log = getCleanLogger(__name__)

RTOL_DEFAULT: float = 1.e-5
ATOL_DEFAULT: float = 1.e-8
EQUAL_NAN_DEFAULT: bool = False

T = TypeVar('T', bound=ndarray)


def makeReadOnly(x: T) -> T:
  """ Sets array writeable Flag to false and returns same instance. """
  x.flags.writeable = False
  return x
##


def numpyEqual(lhs: Union[ndarray, Rotation, Any], rhs: Union[ndarray, Rotation, Any]) -> bool:
  """ Module private helper function that checks that both of the objects have all their elements equal.
  This ensures that ndarray's and other are compared without throwing a Type or Attribute error

  Parameters
  ----------
  lhs : left value for comparison
  rhs : right value for comparison

  Returns
  -------
  bool : True if the same type and all elements are equal, False otherwise

  """
  if not isinstance(lhs, type(rhs)):
    return False
  elif isinstance(lhs, ndarray):
    if isinstance(rhs, ndarray):
      out = (lhs.shape == rhs.shape) and all((lhs == rhs).ravel())
      return out
    else:
      # one is array and the other is not
      return False
    ##
  elif isinstance(lhs, Rotation) and isinstance(rhs, Rotation):
    return all((lhs.as_quat() == rhs.as_quat()).ravel())
  else:
    out = (lhs == rhs)
    return out
  ##
##


def numpyAllClose(lhs: ComplexArrayOrComplexNumberLike, rhs: ComplexArrayOrComplexNumberLike, rtol: float = RTOL_DEFAULT, atol: float = ATOL_DEFAULT, equal_nan: bool = EQUAL_NAN_DEFAULT) -> bool:
  """ Module private function that checks that both of the objects have all their elements close within a tolerance.
  This ensures that ndarray's and other are compared without throwing a Type or Attribute error

  Parameters
  ----------
  lhs : ComplexArrayOrComplexNumberLike
    left value for comparison
  rhs : ComplexArrayOrComplexNumberLike
    right value for comparison
  rtol : float
    relative tolerance
  atol: float
    absolute tolerance
  equal_nan: bool
   Whether to compare NaN's as equal.  If True, NaN's in `a` will be
   considered equal to NaN's in `b` in the output array.

  Returns
  -------
  bool
   True if the same type and all elements are equal, False otherwise

  Notes
  -----
  If the following equation is element-wise True, then allclose returns
  True.

   absolute(`a` - `b`) <= (`atol` + `rtol` * absolute(`b`))

  The above equation is not symmetric in `a` and `b`, so that
  ``allclose(a, b)`` might be different from ``allclose(b, a)`` in
  some rare cases.

  The comparison of `a` and `b` uses standard broadcasting, which
  means that `a` and `b` need not have the same shape in order for
  ``allclose(a, b)`` to evaluate to True.  The same is true for
  `equal` but not `array_equal`.

  `allclose` is not defined for non-numeric data types.
  `bool` is considered a numeric data-type for this purpose.
  """
  if rtol is None:
    rtol = RTOL_DEFAULT
  ##
  if atol is None:
    atol = ATOL_DEFAULT
  ##
  if equal_nan is None:
    equal_nan = EQUAL_NAN_DEFAULT
  ##
  if isinstance(lhs, ndarray):
    if isinstance(rhs, ndarray):
      out = (lhs.shape == rhs.shape) and allclose(lhs, rhs, rtol=rtol, atol=atol, equal_nan=equal_nan)
      return out
    else:
      # one is array and the other is not
      return False
    ##
  ##
  try:
    return allclose(lhs, rhs, rtol=rtol, atol=atol, equal_nan=equal_nan)
  except (TypeError, ValueError,):
    return lhs == rhs
  ##
##


def unitize(X: ComplexArrayLike) -> ndarray:
  """ Scales the last dimension of X by the norm. If the norm is zero then sets the first value to 1 and the rest to zeros.

  Parameters
  ----------
  X : An N-dimensional numpy array

  Returns
  -------
  ndarray: Output array of unit vectors the same size array as input.

  """
  # unitizes along last dimension
  X = asarray(X)
  nrm = norm(X, axis=-1)
  lgc = (nrm == 0.)
  nrm += lgc  # prevent divide by zeros
  with warnings.catch_warnings():
    warnings.filterwarnings('ignore', category=RuntimeWarning)
    Y = X / (nrm[..., newaxis])
  ##
  if Y.shape == (0,):
    Y[...] = 1.
  elif not any(x == 0 for x in Y.shape):
    Y[lgc, :] = 0
    Y[lgc, 0] = 1
  ##
  return asarray(Y)
##


def isGrid(points: Sequence[ArrayLike]) -> bool:
  # DOCME
  if points is None or len(points) == 0:
    return False
  ##
  N = len(points[0])
  all_same_size = all(len(point) == N for point in points)
  if not all_same_size:
    return False
  ##
  lol = [frozenset(point[n] for point in points) for n in range(N)]
  grid_size = prod([len(dim) for dim in lol])
  if len(points) != grid_size:
    return False
  ##
  original_set = frozenset(tuple(point) for point in points)
  for point in product(*lol):
    if point not in original_set:
      return False
    ##
  ##
  return True
##


def getOrthonormalBasis(vectors: Union[Sequence[ndarray], ndarray]) -> ndarray:
  """ Receives a list of vectors (as rows) and returns a new orthonormal basis as a list of vectors

  @param vectors: list of vectors
  @return: list of orthonormal vectors
  """
  dim_size = len(vectors[0])
  out: List[ndarray] = []
  for vi, v in enumerate(vectors):
    v = v.copy()
    for u in out:
      v -= (v @ u) * u
    ##
    v_norm = norm(v, axis=-1, keepdims=True)
    if v_norm == 0:
      continue
    ##
    vn = v / v_norm
    out.append(vn)
    if len(out) >= dim_size:
      break
    ##
  ##
  return vstack(out)
##


def getBarycentricTriangleCoordinates2D(query: ndarray, point0: ndarray, point1: ndarray, point2: ndarray) -> ndarray:
  """ Returns barycentric triangle coordinates given a query point and triangle points in 2D (N,2)
  https://stackoverflow.com/a/14382692
  https://web.archive.org/web/20160527153322/https://stackoverflow.com/questions/2049582/how-to-determine-a-point-in-a-2d-triangle/14382692#14382692

  @param query: query point
  @param point0: Triangle Point 0
  @param point1: Triangle Point 1
  @param point2: Triangle Point 2
  @return: ndarray (N,2)
  """
  signed_area = getSignedAreaOfTriangle(point0, point1, point2)
  inv_half_signed_area = 1. / (2 * signed_area)
  s = inv_half_signed_area * (point0[..., 1] * point2[..., 0] - point0[..., 0] * point2[..., 1] + (point2[..., 1] - point0[..., 1]) * query[..., 0] + (point0[..., 0] - point2[..., 0]) * query[..., 1])
  t = inv_half_signed_area * (point0[..., 0] * point1[..., 1] - point0[..., 1] * point1[..., 0] + (point0[..., 1] - point1[..., 1]) * query[..., 0] + (point1[..., 0] - point0[..., 0]) * query[..., 1])
  return concatenate([x[..., newaxis] for x in [s, t]], axis=-1)
##


def isPointWithinTriangle2D(query: ndarray, point0: ndarray, point1: ndarray, point2: ndarray) -> ndarray:
  st = getBarycentricTriangleCoordinates2D(query, point0, point1, point2)
  within = np.all(np.all((0 <= st) & (st <= 1), axis=-1) & (np.sum(st, axis=-1) <= 1), axis=0)
  return within
##


def dot2(a: ndarray) -> ndarray:
  return (a**2).sum(axis=-1)
##


def find0(lgc: Union[ndarray, Sequence[Union[float, int, bool]]]) -> ndarray:
  """ Finds the locations of the nonzero elements in a flat array.
  It is assumed that the array has been flattened/raveled. Outputs are unspecified otherwise. """
  return nonzero(lgc)[0]
##


def areQuaternionsClose(q1: ndarray, q2: ndarray, rtol: float = RTOL_DEFAULT, atol: float = ATOL_DEFAULT, equal_nan: bool = EQUAL_NAN_DEFAULT) -> ndarray:
  """ Checks if the unit-quaternions are close. Assuming scalar last notation """
  if rtol is None:
    rtol = RTOL_DEFAULT
  ##
  if atol is None:
    atol = ATOL_DEFAULT
  ##
  if equal_nan is None:
    equal_nan = EQUAL_NAN_DEFAULT
  ##
  q1 = q1.copy()
  q2 = q2.copy()
  q1[q1[..., -1] < 0, ...] *= -1
  q2[q2[..., -1] < 0, ...] *= -1
  return np.all(isclose(q1, q2, rtol=rtol, atol=atol, equal_nan=equal_nan), axis=-1)
##


def areRotationsClose(rot1: Rotation, rot2: Rotation, rtol: float = RTOL_DEFAULT, atol: float = ATOL_DEFAULT, equal_nan: bool = EQUAL_NAN_DEFAULT) -> bool:
  if rtol is None:
    rtol = RTOL_DEFAULT
  ##
  if atol is None:
    atol = ATOL_DEFAULT
  ##
  if equal_nan is None:
    equal_nan = EQUAL_NAN_DEFAULT
  ##
  rv1 = rot1.as_rotvec()
  rv2 = rot2.as_rotvec()
  return allclose(rv1, rv2, rtol=rtol, atol=atol, equal_nan=equal_nan)
##


def fullCovarianceFromUpperTriangularVector(ut: Union[ndarray, Sequence[float]]) -> ndarray:
  """ Converts upper triangular (including the diagonal.)
  Assumes data is read from original covariance matrix row by row. """
  M = len(ut)
  N = int(sqrt(M * 8 + 1) // 2)
  if 2 * M - N != N * N:
    raise ValueError(f'Sequence does not have enough elements for a {N} square matrix. Received {M} elements')
  ##
  out = zeros((N, N,))
  index = 0
  for row_index in range(N):
    row_length = N - row_index
    row = ut[index:index + row_length]
    out[row_index, row_index:] = row
    if row_index + 1 != N:
      out[row_index + 1:, row_index] = row[1:]
    ##
    index += row_length
  ##
  return out
##


def upperTriangularVectorFromFullCovariance(cov: ndarray) -> List[float]:
  """ Converts covariance matrix to sequence. Only stores the upper triangular values.
  Assumes data is read from matrix row by row. """
  out = chain(*(row[i:] for i, row in enumerate(cov)))
  return list(out)
##


def isHermitian(matrix: ndarray, rtol: float = RTOL_DEFAULT, atol: float = ATOL_DEFAULT, equal_nan: bool = EQUAL_NAN_DEFAULT) -> bool:
  if len(matrix.shape) == 1 and matrix.shape[0] > 1:
    # vectors are not hermitian - only possible for squares
    return False
  ##
  out = allclose(matrix, matrix.T.conj(), rtol=rtol, atol=atol, equal_nan=equal_nan)
  return out
##


def isPositiveSemiDefinite(matrix: ndarray, rtol: float = RTOL_DEFAULT, atol: float = ATOL_DEFAULT, equal_nan: bool = EQUAL_NAN_DEFAULT,) -> Tuple[bool, Optional[str]]:
  # All positive-semi-definite matrices have cholesky decompositions,
  # but not all cholesky decomposable matrices are psd.
  # Therefore, an extra hermitian check is required to ensure psd
  if not isHermitian(matrix, rtol=rtol, atol=atol, equal_nan=equal_nan):
    return (False, f'Matrix is not hermitian. Matrix:{matrix!r}',)
  ##
  try:
    cholesky(matrix)
    return (True, None,)
  except LinAlgError as e:
    return (False, f'Matrix cholesky factor could not be calculated with exception:{e}')
  ##
##
