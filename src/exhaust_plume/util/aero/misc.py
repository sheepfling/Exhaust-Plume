# -*- coding: utf-8 -*-
r"""
These functions calculate the total and static properties of a gas assuming isentropic expansion/compression

Modern Compressible Flow: With Historical Perspective 3rd Edition
- https://archive.org/details/5f-36b-7c-4ded-79bb-3e-90754d-0f-81682f-7a-68014be
- https://web.archive.org/web/20221006024847/https://icourse.club/uploads/files/5f36b7c4ded79bb3e90754d0f81682f7a68014be.pdf
- https://icourse.club/uploads/files/5f36b7c4ded79bb3e90754d0f81682f7a68014be.pdf
"""
from __future__ import annotations

from typing import TypeVar

from numpy import arcsin, asarray, isinf, nan, ndarray, rad2deg

from exhaust_plume.log.log import getCleanLogger

__all__ = (
    'calcMachAngle',
)
log = getCleanLogger(__name__)

T = TypeVar('T', float, ndarray)


def calcMachAngle(mach: T) -> T:
  """ Calculates mach angle in degrees """
  mach_arr = asarray(mach)
  mu_deg = rad2deg(arcsin(1. / mach_arr))
  shp = mu_deg.shape
  mach_arr = mach_arr.ravel()
  mu_deg = mu_deg.ravel()
  mu_deg[isinf(mach_arr)] = 0.
  mu_deg[mach_arr < 1] = nan
  mu_deg[mach_arr == 1.] = 90
  if isinstance(mach, float):
    return float(mu_deg[0])
  ####
  mu_deg = mu_deg.reshape(shp)
  return mu_deg
####
