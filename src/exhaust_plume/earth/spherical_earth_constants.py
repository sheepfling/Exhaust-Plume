# -*- coding: utf-8 -*-
from __future__ import annotations

from exhaust_plume.earth.wgs84 import Wgs84Constants
from exhaust_plume.log.log import getCleanLogger

__all__ = (
    'SPHERICAL_EARTH_RADIUS_m',
    'SPHERICAL_EARTH_NOMINAL_GRAVITY_mps2',
)
###############################################################################
log = getCleanLogger(__name__)

SPHERICAL_EARTH_RADIUS_m = Wgs84Constants.radius_of_sphere_of_equal_volume
SPHERICAL_EARTH_NOMINAL_GRAVITY_mps2 = 9.81
