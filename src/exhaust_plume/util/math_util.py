# -*- coding: utf-8 -*-
# DOCME
from __future__ import annotations

import warnings
from math import factorial
from typing import Dict, Optional, Tuple, TypeVar, Union, overload

from mpmath import polylog as mp_polylog
from numpy import (
    arange, arcsin, array, asarray, column_stack, concatenate, cos, cross, einsum, eye, full, inf, linspace, log as ln, log10, moveaxis, nan, ndarray, newaxis, ones, pi, roots, round as np_round, sin, sqrt, sum as np_sum, swapaxes, vstack,
    zeros, zeros_like,
)
from numpy.linalg import det, inv, norm, svd
from sympy.functions.combinatorial.numbers import stirling

from exhaust_plume.log.log import getCleanLogger
from exhaust_plume.util.numpy_util import unitize

__all__ = (
    'getUniformGridOnSphere', 'getFundamentalSpaces',
    'null_space', 'col_space', 'row_space', 'rnull_space', 'lnull_space',
    'getOrthogonalHyperplaneWithBias',
    'dbToLinPow', 'linPowToDb',
    'orthogonalizeBasis',
    'generateHexagonGrid',
    'applyRotationAboutAxis',
    'applyTwistDeformation',
    'solveCubic',
    'convertNonRealToNan',
)
####################################################
log = getCleanLogger(__name__)

FloatOrNdarray = Union[float, ndarray]

_SVD_RTOL_DEFAULT = 1e-14
_SVD_ATOL_DEFAULT = 0.
_TWO_PI = 2 * pi


def _decayNdarray(arr: ndarray) -> FloatOrNdarray:
  if isinstance(arr, ndarray) and arr.size == 1:
    return float(arr)
  else:
    return arr
  ##
##


def getUniformGridOnSphere(N: int) -> ndarray:
  # DOCME
  """ Attempts to place about N points on a sphere. Returns in NSD """
  if N <= 0:
    raise ValueError(f'Number of points must be greater than 0. Got:{N}')
  ##
  azel = []
  dA = 4 * pi / N
  d = sqrt(dA)
  M_el = int(np_round(pi / d))
  d_el = pi / M_el
  d_az = dA / d_el
  for m in range(M_el):
    el = pi * ((m + .5) / M_el - .5)
    M_az = int(np_round(2 * pi * cos(el) / d_az))
    for n in range(M_az):
      az = 2 * pi * (n * 1. / M_az)
      azel.append((az, el))
    ##
  ##
  rhat = vstack([(cos(el) * cos(az), cos(el) * sin(az), -sin(el),) for az, el in azel])
  return rhat
##


def getFundamentalSpaces(A: ndarray, rtol: float = _SVD_RTOL_DEFAULT, atol: float = _SVD_ATOL_DEFAULT) -> Dict[str, ndarray]:
  # DOCME
  # The rows of `vh` are the eigenvectors of `A^H A`
  # The cols of `u`  are the eigenvectors of `A^H A`
  # corresponding eigenvalues are given by s**2
  U, s, Vh = svd(A, full_matrices=True)
  if s.size == 0:
    N = A.shape[-1]
  else:
    tol = max(atol, rtol * s[0])
    N = sum(s >= tol)
  ##
  out = {
      'col': U[..., :N],
      'lnull': U[..., N:],
      'row': Vh[:N, ...],
      'rnull': Vh[N:, ...],
  }
  return out
##


def generateSphericalAngleGrid(num_longitude_lines: int, num_latitude_lines: int, equal_area: bool) -> Tuple[ndarray, ndarray]:
  """ Returns longitude/azimuth and latitude/elevation grid axis points
  num_latitude_lines: includes the poles as part of the count
  """
  num_longitude_lines = int(num_longitude_lines)
  if num_longitude_lines < 3:
    raise ValueError(f'Expected `num_longitude_lines` to be greater than or equal to 3. Got:{num_longitude_lines}')
  ##
  num_latitude_lines = int(num_latitude_lines)
  if num_latitude_lines < 2:
    raise ValueError(f'Expected `num_latitude_lines` to be greater than or equal to 1. Got:{num_latitude_lines}')
  ##
  if equal_area:
    latitudes = arcsin(linspace(-1, 1, num_latitude_lines))
  else:
    latitudes = linspace(-pi / 2, pi / 2, num_latitude_lines)
  ##
  longitudes = linspace(-pi, pi, num_longitude_lines + 1)[:-1]
  return (longitudes, latitudes,)
##


def null_space(A: ndarray, rtol: float = _SVD_RTOL_DEFAULT, atol: float = _SVD_ATOL_DEFAULT) -> ndarray:
  # DOCME
  return getFundamentalSpaces(A, rtol=rtol, atol=atol)['rnull']
##


rnull_space = null_space


def lnull_space(A: ndarray, rtol: float = _SVD_RTOL_DEFAULT, atol: float = _SVD_ATOL_DEFAULT) -> ndarray:
  # DOCME
  return getFundamentalSpaces(A, rtol=rtol, atol=atol)['lnull']
##


def col_space(A: ndarray, rtol: float = _SVD_RTOL_DEFAULT, atol: float = _SVD_ATOL_DEFAULT) -> ndarray:
  # DOCME
  return getFundamentalSpaces(A, rtol=rtol, atol=atol)['col']
##


def row_space(A: ndarray, rtol: float = _SVD_RTOL_DEFAULT, atol: float = _SVD_ATOL_DEFAULT) -> ndarray:
  # DOCME
  return getFundamentalSpaces(A, rtol=rtol, atol=atol)['row']
##


def getOrthogonalHyperplaneWithBias(A: ndarray, rtol: float = _SVD_RTOL_DEFAULT, atol: float = _SVD_ATOL_DEFAULT) -> ndarray:
  # DOCME
  # Gets nullspaces with possible bias
  shape = (1, *A.shape[1:],)
  Apad = concatenate((A, ones(shape),), axis=0)
  spaces = getFundamentalSpaces(Apad, rtol=rtol, atol=atol)
  lnull = spaces['lnull'].T
  lnull_norm = norm(lnull[:-1, ...], axis=0)
  lnull_norm[lnull_norm == 0.] = 1.
  lnull /= lnull_norm
  return lnull
##


@overload
def dbToLinPow(x: float) -> float:
  ...


@overload
def dbToLinPow(x: ndarray) -> ndarray:
  ...


def dbToLinPow(x: FloatOrNdarray) -> FloatOrNdarray:
  # DOCME
  return 10.**(x / 10.)
##


@overload
def linPowToDb(x: float) -> float:
  ...


@overload
def linPowToDb(x: ndarray) -> ndarray:
  ...


def linPowToDb(x: FloatOrNdarray) -> FloatOrNdarray:
  # DOCME
  initial_is_float = isinstance(x, float)
  out = 10. * log10(x)
  return float(out) if initial_is_float else out
##


def orthogonalizeBasis(V: ndarray) -> ndarray:
  # DOCME
  # Assumes rows are vectors to be orthogonalized
  U = zeros(shape=V.shape)
  for row_idx, v in enumerate(V):
    v = v / norm(v, axis=-1, keepdims=True)
    a = U[:row_idx, ...] @ v
    if a.size == 0:
      U[row_idx, ...] = v
    else:
      u = v - np_sum(U[:row_idx, ...] * a[:, newaxis], axis=0)
      u = u / norm(u, axis=-1, keepdims=True)
      U[row_idx, ...] = u
    ##
  ##
  if det(U) < 0:
    U[..., -1] *= -1
  ##
  return U
##


def generateHexagonGrid(dx: float, dy: float, Nx: int, Ny: int) -> ndarray:
  # DOCME
  # Generates a (Nx*Nx,2,) array of points
  rows = []
  for y_idx in range(Ny):
    x_offset = dx / 2. if y_idx % 2 != 0 else 0.
    row = vstack([arange(Nx) * dx + x_offset, zeros(Nx) + y_idx * dy]).T
    rows.append(row)
  ##
  out = vstack(rows)
  return out
##


def applyRotationAboutAxis(axis: ndarray, angles: Union[float, ndarray], points: ndarray) -> ndarray:
  """ Applies a rotation about an axis with angles on array points
  Assumes
  axis: (3,) and normalized
  angles: (N,)
  points: (N,3)
  """
  e = axis
  v = points
  cth = cos(angles)[..., newaxis]
  sth = sin(angles)[..., newaxis]
  out = (cth * v) + sth * cross(e, v, axis=-1) + (1 - cth) * ((v @ e)[..., newaxis]) * e
  return out
##


def calculateCrossProductMatrix(v: ndarray) -> ndarray:
  """ Assumes v is shape (...,3)
  Output size (...,3,3)
  """
  v = asarray(v)
  kx = v[..., 0]
  ky = v[..., 1]
  kz = v[..., 2]
  k0 = zeros_like(kx)
  K = moveaxis(array([
      [k0, -kz, ky],
      [kz, k0, -kx],
      [-ky, kx, k0],
  ]), (0, 1), (-2, -1))
  return K
##


def calculateAxisRotationMatrix(axis: ndarray, angles: Union[float, ndarray]) -> ndarray:
  """ Assumes
  axis is shape (...,3)
  angles is scalar or (...,)
  Output size (...,3,3)
  """
  K = calculateCrossProductMatrix(axis)
  angles = asarray(angles, 'float')[..., newaxis, newaxis]
  R = eye(3) + sin(angles) * K + (1 - cos(angles)) * (K @ K)
  return R
##


def calculateAxisRotationMatrixDerivative(axis: ndarray, angles: Union[float, ndarray]) -> ndarray:
  f""" Calculates derivative of {calculateAxisRotationMatrix.__name__} with respect to angles input
  axis is shape (...,3)
  angles is scalar or (...,)
  Output size (...,3,3)
  """
  K = calculateCrossProductMatrix(axis)
  angles = asarray(angles, 'float')[..., newaxis, newaxis]
  R = cos(angles) * K + sin(angles) * (K @ K)
  return R
##


@overload
def applyTwistDeformation(points: ndarray, twist_axis: ndarray, frequency: float,
                          normals: None, body_axis: Optional[ndarray] = None,
                          ) -> ndarray:
  """ None overload """


@overload
def applyTwistDeformation(points: ndarray, twist_axis: ndarray, frequency: float,
                          normals: ndarray, body_axis: Optional[ndarray] = None,
                          ) -> Tuple[ndarray, ndarray]:
  """ Normal supplied overlaad """


def applyTwistDeformation(points: ndarray, twist_axis: ndarray,
                          frequency: float,
                          normals: Optional[ndarray] = None,
                          body_axis: Optional[ndarray] = None,
                          ) -> Union[ndarray, Tuple[ndarray, ndarray]]:
  """ Applies a twist (body==twist) or bend deformation (if body!=twist) deformation on points and normals. Frequency can be positive or negative
  Assumes that points have already been centered
  Assumes twist axis is normalized.
  If body_axis is given, then it is also assumed to be normalized.
  Assumes
  points is shape (...,3)
  twist_axis and body_axis are (3,)
  """
  twist_axis = asarray(twist_axis)
  if body_axis is None:
    body_axis = twist_axis
  ##
  b = (_TWO_PI * frequency) * body_axis
  angles = (points @ b)
  R = calculateAxisRotationMatrix(axis=twist_axis, angles=angles)
  out = einsum('...ij,...j', R, points)
  if normals is not None:
    # Calculate jacobian of transformation and apply to normals
    # p' = R(θ)*p
    # θ=b^T*p
    # δ/δp θ = b^T
    # R(θ) = I + sin(θ)*K + (1-cos(θ))*K^2
    # d/dθ R(θ) = cos(θ)*K + sin(θ)*K^2
    #
    # δ/δp p' = δ/δp( R(θ)*p )
    #    = R(θ)*(δ/δp p) + p * (δ/δp R(θ))
    #    = R(θ) + p * (δ/δp R(θ))
    #
    # p * δ/δp R(θ=b^T*p) = d/dθ R(θ) δ/δp( θ )
    #                     = ( cos(θ)*K + sin(θ)*K^2 ) * p * b^T
    #
    # δ/δp p' = R(θ) + ( p*b^T * ( cos(θ)*K + sin(θ)*K^2 ) )`
    dRdu = calculateAxisRotationMatrixDerivative(axis=twist_axis, angles=angles)
    J = R + dRdu @ (einsum('...i,...j', points, b))
    invJT = swapaxes(inv(J), -2, -1)  # transpose of last two dimensions
    new_normals = unitize(einsum('...ij,...j', invJT, normals))
    out = (out, new_normals,)
  ##
  return out
##


def solveCubic(a: ndarray, b: ndarray, c: ndarray, d: ndarray) -> ndarray:
  abcd = column_stack([asarray(x) for x in [a, b, c, d]])
  out = vstack([roots(row) for row in abcd])
  return out
##


def convertNonRealToNan(x: ndarray, tol: float = 1e-6) -> ndarray:
  xrav = x.ravel()
  out = full((x.size,), nan)
  valid_lgc = abs(xrav.imag) <= tol
  out[valid_lgc] = xrav[valid_lgc].real
  out = out.reshape(x.shape)
  return out
##


T = TypeVar('T', float, complex, ndarray)


def _polylog_specint(s: int, z: T) -> T:
  """
  https://en.wikipedia.org/wiki/Polylogarithm
  - https://web.archive.org/web/20230129120151/https://en.wikipedia.org/wiki/Polylogarithm
  - https://archive.is/E0LAn
  """
  if s > 1 or int(s) != s:
    raise ValueError(f'Unable to calculate Polylog for special integer cases if s>1. Got:{s}')
  ##
  with warnings.catch_warnings():
    warnings.filterwarnings('ignore', category=RuntimeWarning)
    if s == 1:
      return -ln(1 - z)
    elif s == 0:
      if not isinstance(z, ndarray) and z == 1:
        return inf
      else:
        return z / (1 - z)
      ##
    ##
    n = -s
    if not isinstance(z, ndarray):
      if z == 1:
        return inf
      else:
        m1_div_1mz = (-1. / (1 - z))
      ##
    else:
      m1_div_1mz = (-1. / (1 - z))
    ##
    out = (0. * z)
    for k in range(n + 1):
      S = stirling(n=n + 1, k=k + 1)  # type: ignore[no-untyped-call]
      out += factorial(k) * float(S) * (m1_div_1mz**(k + 1))
    ##
  ##
  out *= (-1)**(n + 1)
  if isinstance(z, ndarray):
    # correct any z==1 to be inf
    out[z == 1] = inf
  ##
  return out
##


def polylog(s: Union[int, float, complex], z: T) -> ndarray:
  r""" Calculates polylogarithm as defined by references below:
  s is the order of the polylog
  z is the argument

  $ \mathrm{Li}_s(z) = \sum_{k}^{\infty}{\frac{z^k}{k^2}} $

  Returns complex ndarray

  https://mpmath.org/doc/current/functions/zeta.html#polylogarithms-and-clausen-functions
  - https://web.archive.org/web/20230407230435/https://mpmath.org/doc/current/functions/zeta.html#polylogarithms-and-clausen-functions
  - https://archive.is/MssrM

  https://reference.wolfram.com/language/ref/PolyLog.html
  - https://web.archive.org/web/20230218051823/https://reference.wolfram.com/language/ref/PolyLog.html
  - https://archive.is/draWb

  https://github.com/mpmath/mpmath/blob/dfc289289d3bf4f18657179288e7541a14fba981/mpmath/functions/zeta.py#L465
  -
  - https://archive.is/14q2a
  """
  if not isinstance(s, ndarray) or (isinstance(s, complex) and s.imag == 0.):
    if isinstance(s, complex):
      si = int(s.real)
    else:
      si = int(s)
    ##
    if si == s and si <= 1:
      return asarray(_polylog_specint(s=si, z=z))
    ##
  ##
  z_arr = asarray(z)
  shp = z_arr.shape
  z_arr = z_arr.ravel()
  y_arr = zeros(shp, 'complex').ravel()
  for i, zi in enumerate(z_arr):
    try:
      yi = mp_polylog(s=s, z=zi)
    except ValueError as e:
      if not e.args or 'pole' not in e.args[0].lower():
        raise
      ##
      yi = inf
    ##
    y_arr[i] = float(yi.real) + 1j * (yi.imag)
  ##
  y_arr = y_arr.reshape(shp)
  return y_arr
##
