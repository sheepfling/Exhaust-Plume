# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Union

from numpy import asarray, concatenate, cos, ndarray, newaxis, sin, zeros

from exhaust_plume.util.numpy_util import unitize

__all__ = (
    'applyUnitQuaternion',
    'applyUnitQuaternionInv',
    'getUnitQuaternionMatrix',
    'getUnitQuaternionMatrixInv',
    ####
    'axisAngleToQuaternion',
)

################


def axisAngleToQuaternion(axis: ndarray, angles_rad: Union[float, ndarray]) -> ndarray:
  """ Converts axis angle to quaternion scalar-LAST """
  # Assumes axis is norma
  # axis (...,3)
  # angle_rad (...,)
  axis = unitize(axis)
  th2 = asarray(angles_rad / 2)
  if th2.size == 1:
    th2 = th2 + zeros(axis.shape[:-1] + (1,))
  else:
    th2 = th2[..., newaxis]
  ##
  quat = concatenate([
      sin(th2) * axis,
      cos(th2),  # scalar LAST
  ], axis=-1)
  return quat
##


def applyUnitQuaternion(vec: ndarray, quat: ndarray) -> ndarray:
  """ Apply Scalar last Unit-Quaternion
  Same as..
  from scipy.spatial.transform import Rotation
  out = Rotation.from_quat(quat).apply(vec)
  Derivation:
  ```python
  from sympy import symbols, simplify
  def applyQuat(a1,b1,c1,d1,a2,b2,c2,d2):
    return (
      a1*a2 - b1*b2 - c1*c2 - d1*d2,
      a1*b2 + b1*a2 + c1*d2 - d1*c2,
      a1*c2 - b1*d2 + c1*a2 + d1*b2,
      a1*d2 + b1*c2 - c1*b2 + d1*a2,
    )
  ##

  def applyUnitQuat(vx,vy,vz,qw,qx,qy,qz):
    # q * p * inv(q)
    tw,tx,ty,tz = applyQuat(0,vx,vy,vz,qw,-qx,-qy,-qz)
    sw,sx,sy,sz = applyQuat(qw,qx,qy,qz,tw,tx,ty,tz)
    out = (sx, sy, sz, )
    return tuple(simplify(x) for x in out)
  ##

  vx,vy,vz,qw,qx,qy,qz = symbols('vx,vy,vz,qw,qx,qy,qz')

  fx,fy,fz = applyUnitQuat(vx,vy,vz,qw,qx,qy,qz)
  >> fx
  qw*(qw*vx + qy*vz - qz*vy) + qx*(qx*vx + qy*vy + qz*vz) + qy*(qw*vz + qx*vy - qy*vx) - qz*(qw*vy - qx*vz + qz*vx)
  >> fy
  qw*(qw*vy - qx*vz + qz*vx) - qx*(qw*vz + qx*vy - qy*vx) + qy*(qx*vx + qy*vy + qz*vz) + qz*(qw*vx + qy*vz - qz*vy)
  >> fz
  qw*(qw*vz + qx*vy - qy*vx) + qx*(qw*vy - qx*vz + qz*vx) - qy*(qw*vx + qy*vz - qz*vy) + qz*(qx*vx + qy*vy + qz*vz)
  ```"""
  vx = vec[..., 0]
  vy = vec[..., 1]
  vz = vec[..., 2]
  qx = quat[..., 0]
  qy = quat[..., 1]
  qz = quat[..., 2]
  qw = quat[..., 3]
  out = concatenate([
      (qw * (qw * vx + qy * vz - qz * vy) + qx * (qx * vx + qy * vy + qz * vz) + qy * (qw * vz + qx * vy - qy * vx) - qz * (qw * vy - qx * vz + qz * vx))[..., newaxis],
      (qw * (qw * vy - qx * vz + qz * vx) - qx * (qw * vz + qx * vy - qy * vx) + qy * (qx * vx + qy * vy + qz * vz) + qz * (qw * vx + qy * vz - qz * vy))[..., newaxis],
      (qw * (qw * vz + qx * vy - qy * vx) + qx * (qw * vy - qx * vz + qz * vx) - qy * (qw * vx + qy * vz - qz * vy) + qz * (qx * vx + qy * vy + qz * vz))[..., newaxis],
  ], axis=-1)
  return out
##


def applyUnitQuaternionInv(vec: ndarray, quat: ndarray) -> ndarray:
  f""" Applies inverse {applyUnitQuaternion.__name__} """
  vx = vec[..., 0]
  vy = vec[..., 1]
  vz = vec[..., 2]
  qx = -quat[..., 0]
  qy = -quat[..., 1]
  qz = -quat[..., 2]
  qw = quat[..., 3]
  out = concatenate([
      (qw * (qw * vx + qy * vz - qz * vy) + qx * (qx * vx + qy * vy + qz * vz) + qy * (qw * vz + qx * vy - qy * vx) - qz * (qw * vy - qx * vz + qz * vx))[..., newaxis],
      (qw * (qw * vy - qx * vz + qz * vx) - qx * (qw * vz + qx * vy - qy * vx) + qy * (qx * vx + qy * vy + qz * vz) + qz * (qw * vx + qy * vz - qz * vy))[..., newaxis],
      (qw * (qw * vz + qx * vy - qy * vx) + qx * (qw * vy - qx * vz + qz * vx) - qy * (qw * vx + qy * vz - qz * vy) + qz * (qx * vx + qy * vy + qz * vz))[..., newaxis],
  ], axis=-1)
  return out
##


def getUnitQuaternionMatrix(quat: ndarray) -> ndarray:
  """ Apply Scalar last Unit-Quaternion
  Same as..
  from scipy.spatial.transform import Rotation
  out = Rotation.from_quat(quat).as_matrix()
  Derivation:
  ```python
  from sympy import symbols, simplify
  def applyQuat(a1,b1,c1,d1,a2,b2,c2,d2):
    return (
      a1*a2 - b1*b2 - c1*c2 - d1*d2,
      a1*b2 + b1*a2 + c1*d2 - d1*c2,
      a1*c2 - b1*d2 + c1*a2 + d1*b2,
      a1*d2 + b1*c2 - c1*b2 + d1*a2,
    )
  ##

  def applyUnitQuat(vx,vy,vz,qw,qx,qy,qz):
    # q * p * inv(q)
    tw,tx,ty,tz = applyQuat(0,vx,vy,vz,qw,-qx,-qy,-qz)
    sw,sx,sy,sz = applyQuat(qw,qx,qy,qz,tw,tx,ty,tz)
    out = (sx, sy, sz, )
    return tuple(simplify(x) for x in out)
  ##

  qw,qx,qy,qz = symbols('qw,qx,qy,qz')

  m00,m10,m20 = applyUnitQuat(1,0,0,qw,qx,qy,qz)  # xhat
  m01,m11,m21 = applyUnitQuat(0,1,0,qw,qx,qy,qz)  # yhat
  m02,m12,m22 = applyUnitQuat(0,0,1,qw,qx,qy,qz)  # zhat
  >> ((m00,m10,m20),(m01,m11,m21),(m02,m12,m22))
  (
    (qw**2 + qx**2 - qy**2 - qz**2, 2*qw*qz + 2*qx*qy, -2*qw*qy + 2*qx*qz),
    (-2*qw*qz + 2*qx*qy, qw**2 - qx**2 + qy**2 - qz**2, 2*qw*qx + 2*qy*qz),
    (2*qw*qy + 2*qx*qz, -2*qw*qx + 2*qy*qz, qw**2 - qx**2 - qy**2 + qz**2),
  )
  ```"""
  out_shape = (quat.shape[0:1] if (len(quat.shape) > 1 and quat.shape[0] > 1) else tuple()) + (3, 3,)
  out = zeros(out_shape)
  qx = quat[..., 0]
  qy = quat[..., 1]
  qz = quat[..., 2]
  qw = quat[..., 3]
  qw2 = qw**2
  qx2 = qx**2
  qy2 = qy**2
  qz2 = qz**2
  qxqy = qx * qy
  qxqz = qx * qz
  qyqz = qy * qz
  qwqx = qw * qx
  qwqy = qw * qy
  qwqz = qw * qz
  # xhat
  out[..., 0, 0] = qw2 + qx2 - qy2 - qz2
  out[..., 1, 0] = 2 * (qwqz + qxqy)
  out[..., 2, 0] = 2 * (qxqz - qwqy)
  # yhat
  out[..., 0, 1] = 2 * (qxqy - qwqz)
  out[..., 1, 1] = qw2 - qx2 + qy2 - qz2
  out[..., 2, 1] = 2 * (qwqx + qyqz)
  # zhat
  out[..., 0, 2] = 2 * (qwqy + qxqz)
  out[..., 1, 2] = 2 * (qyqz - qwqx)
  out[..., 2, 2] = qw2 - qx2 - qy2 + qz2
  return out
##


def getUnitQuaternionMatrixInv(quat: ndarray) -> ndarray:
  """ Inverse of getUnitQuaternionMatrix """
  out_shape = (quat.shape[0:1] if (len(quat.shape) > 1 and quat.shape[0] > 1) else tuple()) + (3, 3,)
  out = zeros(out_shape)
  qx = -quat[..., 0]
  qy = -quat[..., 1]
  qz = -quat[..., 2]
  qw = quat[..., 3]
  qw2 = qw**2
  qx2 = qx**2
  qy2 = qy**2
  qz2 = qz**2
  qxqy = qx * qy
  qxqz = qx * qz
  qyqz = qy * qz
  qwqx = qw * qx
  qwqy = qw * qy
  qwqz = qw * qz
  # xhat
  out[..., 0, 0] = qw2 + qx2 - qy2 - qz2
  out[..., 1, 0] = 2 * (qwqz + qxqy)
  out[..., 2, 0] = 2 * (qxqz - qwqy)
  # yhat
  out[..., 0, 1] = 2 * (qxqy - qwqz)
  out[..., 1, 1] = qw2 - qx2 + qy2 - qz2
  out[..., 2, 1] = 2 * (qwqx + qyqz)
  # zhat
  out[..., 0, 2] = 2 * (qwqy + qxqz)
  out[..., 1, 2] = 2 * (qyqz - qwqx)
  out[..., 2, 2] = qw2 - qx2 - qy2 + qz2
  return out
##
