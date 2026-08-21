# -*- coding: utf-8 -*-
# Contains aliases to WGS84 constants
from __future__ import annotations

from exhaust_plume.earth.wgs84 import Wgs84Constants

__all__ = (
    'EARTH_SEMI_MINOR_AXIS',
    'EARTH_SEMI_MAJOR_AXIS',
    'EARTH_OMEGA_RPS',
)
#######################################
EARTH_SEMI_MAJOR_AXIS = Wgs84Constants.semi_major_axis  # a (m)
EARTH_SEMI_MINOR_AXIS = Wgs84Constants.semi_minor_axis  # b  (m)
EARTH_OMEGA_RPS = Wgs84Constants.nominal_mean_angular_velocity  # omega (rad/s)
