# -*- coding: utf-8 -*-
"""
"""
from __future__ import annotations

import warnings
from typing import TypeVar, Union

from numpy import arccos, asarray, clip, concatenate, cos, einsum, ndarray, newaxis, sin, tan

__all__ = (
    'calculateRevolvedProjectedAreas',
)
###########################################
T = TypeVar('T', ndarray, float)


def calculateRevolvedProjectedAreas(
        normal_aspect_rad: Union[float, ndarray],
        R_left: Union[float, ndarray],
        R_right: Union[float, ndarray],
        H: Union[float, ndarray],
) -> ndarray:
  """
  In 2D:
  - If R_left< R_right then facing at -X / left
  - If R_left==R_right then facing up (no X)
  - If R_left> R_right then facing at +X / right

  normal_aspect_rad: (M,2)
  R_left : (M,)
  R_right: (M,)
  H      : (M,)
  """
  R_left = asarray(R_left, 'float')
  R_right = asarray(R_right, 'float')
  H = asarray(H, 'float')
  R_left = R_left.reshape((1,) + (R_left.shape if len(R_left.shape) > 0 else (1,)))
  R_right = R_right.reshape((1,) + (R_right.shape if len(R_right.shape) > 0 else (1,)))
  H = H.reshape((1,) + (H.shape if len(H.shape) > 0 else (1,)))
  # (1, M shapes)

  normal_aspect_rad = asarray(normal_aspect_rad, 'float')
  if len(normal_aspect_rad.shape) == 0:
    normal_aspect_rad = normal_aspect_rad.reshape((1,))
  ##
  normal_aspect_rad = normal_aspect_rad[:, newaxis, ...]
  # (N views, 1)

  phi0 = calcPolarExclusionAngle(R_left=R_left, R_right=R_right, H=H, normal_aspect_rad=normal_aspect_rad)
  # (N views, M shapes)
  # phi0 *= sign(H)

  # Ahat = [dR,H]/L
  # dA = (L/2*(R_left+R_right))*[dR,H]/L = (R_left+R_right)/2*[dR,H]
  # after integration:
  # (R_left+R_right)/2*(dR*(2*phi0)*vx + H*(2*sin(phi0)*vz)
  # (R_left+R_right)  *(dR   *phi0 *vx + H*   sin(phi0)*vz)
  dA = (R_left + R_right)[..., newaxis] * concatenate([x[..., newaxis] for x in ((R_left - R_right), abs(H))], axis=-1)
  view = concatenate([x[..., newaxis] for x in (sin(normal_aspect_rad) * phi0, cos(normal_aspect_rad) * sin(phi0),)], axis=-1)

  total_A_proj = einsum('...ij,...ij->...', view, dA)
  return total_A_proj
##


def calcPolarExclusionAngle(R_left: Union[float, ndarray], R_right: Union[float, ndarray],
                            H: Union[float, ndarray], normal_aspect_rad: Union[float, ndarray]) -> ndarray:
  """
  In 2D:
  - If R_left< R_right then facing at -X / left
  - If R_left==R_right then facing up (no X)
  - If R_left> R_right then facing at +X / right
  - If H < 0, then facing down
  """
  R_left = asarray(R_left, 'float')
  R_right = asarray(R_right, 'float')
  H = asarray(H, 'float')
  dR = R_left - R_right
  with warnings.catch_warnings():
    warnings.filterwarnings('ignore', category=RuntimeWarning)
    Ax_div_Az = dR / H  # (Ax=dR/L); (Az=H/L); (Ax/Az=(dR/L)/(H/L)=dR/H)
  ##
  phi0 = arccos(clip(-(Ax_div_Az) * tan(normal_aspect_rad), -1, 1))
  return phi0
##
