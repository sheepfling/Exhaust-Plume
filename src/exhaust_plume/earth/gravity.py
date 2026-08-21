# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import TypeVar

from numpy import ndarray, zeros

from exhaust_plume.earth.earth_model import EarthModel
from exhaust_plume.earth.spherical_earth_constants import SPHERICAL_EARTH_NOMINAL_GRAVITY_mps2, SPHERICAL_EARTH_RADIUS_m
from exhaust_plume.earth.spherical_earth_util import calculateGeopotentialAltitudeFromECEF as calculateSphereEarthGeopotentialAltitudeFromECEF, calculateGeopotentialAltitudeFromGeometricAltitude, calculateGravity as calculateSphericalGravity
from exhaust_plume.earth.wgs84 import calculateWgs84GravityEcef
from exhaust_plume.log.log import getCleanLogger
from exhaust_plume.util.position_interface import PositionEcefGenericInterface
from exhaust_plume.util.robust_geodetic_conversion import ecef2lla

__all__ = (
    'calculateGravity',
    #####
    'calculateFlatEarthGeopotentialAltitudeFromECEF',
    'calculateWgs84EarthGeopotentialAltitudeFromECEF',
    'calculateGeopotentialAltitudeFromECEF',
)

########################################
log = getCleanLogger(__name__)

FloatXorNdarray = TypeVar('FloatXorNdarray', float, ndarray)


def calculateGravity(position_ecef: PositionEcefGenericInterface[FloatXorNdarray], earth_model: EarthModel,
                     spherical_earth_radius_m: float = SPHERICAL_EARTH_RADIUS_m, ) -> ndarray:
  """ Returns gravity in m/s^2 as same shape as input.

  If flat earth, then assumes ECEF (XYZ)≈North-East-Down, so gravity is Positive Down with magnitude the same as sea-level spherical.
  """
  if earth_model == EarthModel.WGS84:
    return calculateWgs84GravityEcef(ecef_xyz=position_ecef.asMatrixECEF())
  elif earth_model == EarthModel.Sphere:
    return calculateSphericalGravity(position_ecef=position_ecef, earth_radius_m=spherical_earth_radius_m)
  else:  # EarthModel.Flat:
    # Assumes North - East - Down like coordinates, Gravity is positive down
    out = zeros(position_ecef.asMatrixECEF().shape)
    out[..., 2] = SPHERICAL_EARTH_NOMINAL_GRAVITY_mps2
    return out
  ##
##

############################


def calculateFlatEarthGeopotentialAltitudeFromECEF(position_ecef: PositionEcefGenericInterface[FloatXorNdarray]) -> FloatXorNdarray:
  out = position_ecef.z
  return out
##


def calculateWgs84EarthGeopotentialAltitudeFromECEF(position_ecef: PositionEcefGenericInterface[FloatXorNdarray]) -> FloatXorNdarray:
  # Not sure how to properly calculate geopotential altitude for the WGS84 ellipsoid as opposed to a spherical earth.
  # this will at least be very close.
  geometric_altitude_m = ecef2lla(ecef_xyz=position_ecef.asMatrixECEF())[..., 2]
  geopotential_altitude_m = calculateGeopotentialAltitudeFromGeometricAltitude(geometric_altitude_m=geometric_altitude_m)
  if isinstance(position_ecef.x, float):
    return float(geopotential_altitude_m)
  else:
    return geopotential_altitude_m
  ##
##


def calculateGeopotentialAltitudeFromECEF(position_ecef: PositionEcefGenericInterface[FloatXorNdarray], earth_model: EarthModel, spherical_earth_radius_m: float = SPHERICAL_EARTH_RADIUS_m, ) -> FloatXorNdarray:
  if earth_model == EarthModel.WGS84:
    out = calculateWgs84EarthGeopotentialAltitudeFromECEF(position_ecef=position_ecef)
  elif earth_model == EarthModel.Sphere:
    out = calculateSphereEarthGeopotentialAltitudeFromECEF(position_ecef=position_ecef, earth_radius_m=spherical_earth_radius_m)
  else:
    out = calculateFlatEarthGeopotentialAltitudeFromECEF(position_ecef=position_ecef)
  ##
  return out
##
