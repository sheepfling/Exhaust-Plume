# -*- coding: utf-8 -*-
""" This module contains some numpy utilities"""
from __future__ import annotations

import numpy as np
from numpy import cross, ndarray

from exhaust_plume.log.log import getCleanLogger

__all__ = (
    'getSignedAreaOfTriangle',
)
############################
log = getCleanLogger(__name__)


def getSignedAreaOfTriangle(point0: ndarray, point1: ndarray, point2: ndarray) -> ndarray:
  area = .5 * np.sum(cross(point1 - point0, point2 - point0), axis=-1)
  return area
##
