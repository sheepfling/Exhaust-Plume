# -*- coding: utf-8 -*-
from __future__ import annotations

import warnings
from typing import TypeVar, Union, overload

from numpy import arccos, arcsin, arctan2, asarray, clip, column_stack, concatenate, cos, cross, inf, logical_not, ndarray, newaxis, sin, sum as np_sum, zeros, zeros_like
from numpy.linalg import norm

from exhaust_plume.earth.spherical_earth_constants import SPHERICAL_EARTH_NOMINAL_GRAVITY_mps2, SPHERICAL_EARTH_RADIUS_m
from exhaust_plume.log.log import getCleanLogger
from exhaust_plume.util.position import PositionArrayECEF, PositionArrayNED
from exhaust_plume.util.position_interface import (
    PositionEcefArrayInterface, PositionEcefGenericInterface, PositionEcefScalarInterface, PositionLatLonArrayInterface, PositionLatLonGenericInterface, PositionLatLonScalarInterface, PositionLlaArrayInterface, PositionLlaGenericInterface,
    PositionLlaScalarInterface,
)
from exhaust_plume.util.quaternion_util import applyUnitQuaternion, axisAngleToQuaternion

__all__ = (
    'getGeocentricDirection',
    'calculateGreatCircleRange',
    'calculateGreatCircleBearing',
    'calculateGreatCircleCrossRange',
    'calculateGeometricAltitudeFromRadius',
    'calculateRadiusFromGeometricAltitude',
    'calculateGeopotentialAltitudeFromGeometricAltitude',
    'calculateGeometricAltitudeFromGeopotentialAltitude',
    'calculateGravity',
    'calculateGeopotentialAltitudeFromECEF',
)
###############################################################################
log = getCleanLogger(__name__)

T_ScalarLatLon = Union[PositionLatLonScalarInterface, PositionLlaScalarInterface]
T_ArrayLatLon = Union[PositionLatLonArrayInterface, PositionLlaArrayInterface]


def getGeocentricDirection(point: Union[T_ScalarLatLon, T_ArrayLatLon, PositionEcefScalarInterface, PositionEcefArrayInterface]) -> ndarray:
  """ Gets direction from origin to point. """
  if isinstance(point, (PositionLatLonGenericInterface, PositionLlaGenericInterface,)):
    lat_rad = point.latitude_rad
    cla = cos(lat_rad)
    sla = sin(lat_rad)
    lon_rad = point.longitude_rad
    clo = cos(lon_rad)
    slo = sin(lon_rad)
    out = concatenate([asarray(x)[..., newaxis] for x in (
        cla * clo,
        cla * slo,
        sla,
    )], axis=-1)
  else:
    ecef_xyz = point.asMatrixECEF()
    radius_m = norm(ecef_xyz, axis=-1)
    out = zeros(ecef_xyz.shape)
    valid_radius = radius_m != 0
    out[valid_radius, ...] = ecef_xyz[valid_radius, ...] / radius_m[valid_radius, newaxis]
    out[logical_not(valid_radius), 0] = 1.
  ##
  return out
##


@overload
def calculateGreatCircleRange(point1: T_ScalarLatLon, point2: T_ScalarLatLon, earth_radius_m: float = SPHERICAL_EARTH_RADIUS_m) -> float:
  """ Calculates Great circle range in meters from one point to another. Assumes spherical earth with the given radius. """


@overload
def calculateGreatCircleRange(point1: T_ScalarLatLon, point2: T_ArrayLatLon, earth_radius_m: float = SPHERICAL_EARTH_RADIUS_m) -> ndarray:
  """ Calculates Great circle range in meters from one point to another. Assumes spherical earth with the given radius. """


@overload
def calculateGreatCircleRange(point1: T_ArrayLatLon, point2: T_ScalarLatLon, earth_radius_m: float = SPHERICAL_EARTH_RADIUS_m) -> ndarray:
  """ Calculates Great circle range in meters from one point to another. Assumes spherical earth with the given radius. """


@overload
def calculateGreatCircleRange(point1: T_ArrayLatLon, point2: T_ArrayLatLon, earth_radius_m: float = SPHERICAL_EARTH_RADIUS_m) -> ndarray:
  """ Calculates Great circle range in meters from one point to another. Assumes spherical earth with the given radius. """


def calculateGreatCircleRange(point1: Union[T_ScalarLatLon, T_ArrayLatLon], point2: Union[T_ScalarLatLon, T_ArrayLatLon],
                              earth_radius_m: float = SPHERICAL_EARTH_RADIUS_m) -> Union[float, ndarray]:
  """ Calculates Great circle range in meters from one point to another. Assumes spherical earth with the given radius. """
  v1 = getGeocentricDirection(point1)
  v2 = getGeocentricDirection(point2)
  dotp = np_sum(v1 * v2, axis=-1)
  norm_v1 = norm(v1, axis=-1)
  norm_v2 = norm(v2, axis=-1)
  th = arccos(clip(dotp / (norm_v1 * norm_v2), -1, 1))  # sometimes argument is slightly above 1 (due to precision) so a clip is necessary
  dist_m = earth_radius_m * th
  if isinstance(point1.latitude_deg, float) and isinstance(point2.latitude_deg, float):
    return float(dist_m)
  else:
    return dist_m
  ##
##

#####################################################################################


@overload
def calculateGreatCircleBearing(origin: T_ScalarLatLon, aimpoint: T_ScalarLatLon) -> float:
  """ This function calculates the initial bearing (in radians) you need to head to travel a
  Great Circle from current location to a desired aimpoint
  """


@overload
def calculateGreatCircleBearing(origin: T_ArrayLatLon, aimpoint: T_ScalarLatLon) -> ndarray:
  """ This function calculates the initial bearing (in radians) you need to head to travel a
  Great Circle from current location to a desired aimpoint
  """


@overload
def calculateGreatCircleBearing(origin: T_ScalarLatLon, aimpoint: T_ArrayLatLon) -> ndarray:
  """ This function calculates the initial bearing (in radians) you need to head to travel a
  Great Circle from current location to a desired aimpoint
  """


@overload
def calculateGreatCircleBearing(origin: T_ArrayLatLon, aimpoint: T_ArrayLatLon) -> ndarray:
  """ This function calculates the initial bearing (in radians) you need to head to travel a
  Great Circle from current location to a desired aimpoint
  """


def calculateGreatCircleBearing(origin: Union[T_ScalarLatLon, T_ArrayLatLon], aimpoint: Union[T_ScalarLatLon, T_ArrayLatLon]) -> Union[float, ndarray]:
  """ This function calculates the initial bearing (in radians) you need to head to travel a
  Great Circle from current location to a desired aimpoint

  Reference:
  https://web.archive.org/web/20221205232037/https://www.movable-type.co.uk/scripts/latlong.html
  https://archive.vn/q6r9q
  """
  lat_origin = asarray(origin.latitude_rad)
  lat_aimpoint = asarray(aimpoint.latitude_rad)
  lon_origin = asarray(origin.longitude_rad)
  lon_aimpoint = asarray(aimpoint.longitude_rad)
  y_origin = sin(lon_aimpoint - lon_origin) * cos(lat_aimpoint)
  x_origin = cos(lat_origin) * sin(lat_aimpoint) - sin(lat_origin) * cos(lat_aimpoint) * cos(lon_aimpoint - lon_origin)
  bearing_rad = arctan2(y_origin, x_origin)  # Bearing in radians
  if isinstance(origin.latitude_rad, float) and isinstance(aimpoint.latitude_rad, float):
    return float(bearing_rad)
  else:
    return bearing_rad
  ##
##

#####################################################################################


@overload
def calculateGreatCircleCrossRange(origin: T_ScalarLatLon, current_point: T_ScalarLatLon,
                                   aimpoint: T_ScalarLatLon, earth_radius_m: float = SPHERICAL_EARTH_RADIUS_m, ) -> float:
  """ This function calculates the crossrange error of current position form a Great
  Circle based on start point and final aimpoint in meters.
  """


@overload
def calculateGreatCircleCrossRange(origin: T_ScalarLatLon, current_point: T_ScalarLatLon, aimpoint: T_ArrayLatLon, earth_radius_m: float = SPHERICAL_EARTH_RADIUS_m, ) -> ndarray:
  """ calculates cross range distance from a great circle """


@overload
def calculateGreatCircleCrossRange(origin: T_ScalarLatLon, current_point: T_ArrayLatLon, aimpoint: T_ScalarLatLon, earth_radius_m: float = SPHERICAL_EARTH_RADIUS_m, ) -> ndarray:
  """ calculates cross range distance from a great circle """


@overload
def calculateGreatCircleCrossRange(origin: T_ScalarLatLon, current_point: T_ArrayLatLon, aimpoint: T_ArrayLatLon, earth_radius_m: float = SPHERICAL_EARTH_RADIUS_m, ) -> ndarray:
  """ calculates cross range distance from a great circle """


@overload
def calculateGreatCircleCrossRange(origin: T_ArrayLatLon, current_point: T_ScalarLatLon, aimpoint: T_ScalarLatLon, earth_radius_m: float = SPHERICAL_EARTH_RADIUS_m, ) -> ndarray:
  """ calculates cross range distance from a great circle """


@overload
def calculateGreatCircleCrossRange(origin: T_ArrayLatLon, current_point: T_ScalarLatLon, aimpoint: T_ArrayLatLon, earth_radius_m: float = SPHERICAL_EARTH_RADIUS_m, ) -> ndarray:
  """ calculates cross range distance from a great circle """


@overload
def calculateGreatCircleCrossRange(origin: T_ArrayLatLon, current_point: T_ArrayLatLon, aimpoint: T_ScalarLatLon, earth_radius_m: float = SPHERICAL_EARTH_RADIUS_m, ) -> ndarray:
  """ calculates cross range distance from a great circle """


@overload
def calculateGreatCircleCrossRange(origin: T_ArrayLatLon, current_point: T_ArrayLatLon, aimpoint: T_ArrayLatLon, earth_radius_m: float = SPHERICAL_EARTH_RADIUS_m, ) -> ndarray:
  """ calculates cross range distance from a great circle """


def calculateGreatCircleCrossRange(origin: Union[T_ScalarLatLon, T_ArrayLatLon], current_point: Union[T_ScalarLatLon, T_ArrayLatLon],
                                   aimpoint: Union[T_ScalarLatLon, T_ArrayLatLon], earth_radius_m: float = SPHERICAL_EARTH_RADIUS_m, ) -> Union[float, ndarray]:
  """ This function calculates the crossrange error of current position form a Great
  Circle based on start point and final aimpoint in meters.
  """
  range_m = calculateGreatCircleRange(point1=origin, point2=current_point)
  delta13_rad = range_m / earth_radius_m  # arc length / radius = radians
  theta13_rad = calculateGreatCircleBearing(origin=origin, aimpoint=current_point)  # Bearing angle to current point
  theta12_rad = calculateGreatCircleBearing(origin=origin, aimpoint=aimpoint)  # Bearing angle to aimpoint
  crsrng = (arcsin(sin(delta13_rad) * sin(theta13_rad - theta12_rad))) * earth_radius_m
  return crsrng
##

######################################


FloatXorNdarray = TypeVar('FloatXorNdarray', float, ndarray)


@overload
def calculateGeometricAltitudeFromRadius(r_m: float, earth_radius_m: float = SPHERICAL_EARTH_RADIUS_m, ) -> float:
  """ Calculates geometric altitude from a geocentric radius. """
##


@overload
def calculateGeometricAltitudeFromRadius(r_m: ndarray, earth_radius_m: float = SPHERICAL_EARTH_RADIUS_m, ) -> ndarray:
  """ Calculates geometric altitude from a geocentric radius. """
##


def calculateGeometricAltitudeFromRadius(r_m: FloatXorNdarray, earth_radius_m: float = SPHERICAL_EARTH_RADIUS_m, ) -> FloatXorNdarray:
  """ Calculates geometric altitude from a geocentric radius. """
  out = r_m - earth_radius_m
  return out
##


@overload
def calculateRadiusFromGeometricAltitude(altitude_m: float, earth_radius_m: float = SPHERICAL_EARTH_RADIUS_m, ) -> float:
  """ Calculates geocentric radius from geometric altitude """
##


@overload
def calculateRadiusFromGeometricAltitude(altitude_m: ndarray, earth_radius_m: float = SPHERICAL_EARTH_RADIUS_m, ) -> ndarray:
  """ Calculates geocentric radius from geometric altitude """
##


def calculateRadiusFromGeometricAltitude(altitude_m: FloatXorNdarray, earth_radius_m: float = SPHERICAL_EARTH_RADIUS_m, ) -> FloatXorNdarray:
  """ Calculates geocentric radius from geometric altitude """
  out = altitude_m + earth_radius_m
  return out
##

#################


@overload
def calculateGeopotentialAltitudeFromGeometricAltitude(geometric_altitude_m: float, earth_radius_m: float = SPHERICAL_EARTH_RADIUS_m, ) -> float:
  """ Calculates geopotential altitude assuming a given spherical earth radius """


@overload
def calculateGeopotentialAltitudeFromGeometricAltitude(geometric_altitude_m: ndarray, earth_radius_m: float = SPHERICAL_EARTH_RADIUS_m, ) -> ndarray:
  """ Calculates geopotential altitude assuming a given spherical earth radius """


def calculateGeopotentialAltitudeFromGeometricAltitude(geometric_altitude_m: FloatXorNdarray, earth_radius_m: float = SPHERICAL_EARTH_RADIUS_m, ) -> FloatXorNdarray:
  r""" Calculates geopotential altitude assuming a given spherical earth radius

  Z = geometric    altitude
  H = geopotential altitude
  R = earth radius

  H = \frac{R \cdot Z}{R + Z}
  Z = \frac{R \cdot H}{R - H}

  Reference: https://www.pdas.com/hydro.pdf
  - https://web.archive.org/web/20220128085402/https://www.pdas.com/hydro.pdf
  - https://archive.ph/qEy39
  """
  Z_geometric_alt = asarray(geometric_altitude_m, 'float').ravel()
  with warnings.catch_warnings():
    warnings.filterwarnings('ignore', category=RuntimeWarning)
    H_geopotential_alt = earth_radius_m * Z_geometric_alt / (earth_radius_m + Z_geometric_alt)
  ##
  H_geopotential_alt[Z_geometric_alt <= -earth_radius_m] = -inf
  H_geopotential_alt[Z_geometric_alt == inf] = earth_radius_m
  if isinstance(geometric_altitude_m, ndarray):
    return H_geopotential_alt.reshape(geometric_altitude_m.shape)
  else:
    return float(H_geopotential_alt)
  ##
##


@overload
def calculateGeometricAltitudeFromGeopotentialAltitude(geopotential_altitude_m: float, earth_radius_m: float = SPHERICAL_EARTH_RADIUS_m, ) -> float:
  """ Calculates geometric altitude assuming a given spherical earth radius """


@overload
def calculateGeometricAltitudeFromGeopotentialAltitude(geopotential_altitude_m: ndarray, earth_radius_m: float = SPHERICAL_EARTH_RADIUS_m, ) -> ndarray:
  """ Calculates geometric altitude assuming a given spherical earth radius """


def calculateGeometricAltitudeFromGeopotentialAltitude(geopotential_altitude_m: FloatXorNdarray, earth_radius_m: float = SPHERICAL_EARTH_RADIUS_m, ) -> FloatXorNdarray:
  r""" Calculates geometric altitude assuming a given spherical earth radius

  Z = geometric    altitude
  H = geopotential altitude
  R = earth radius

  H = \frac{R \cdot Z}{R + Z}
  Z = \frac{R \cdot H}{R - H}

  Reference: https://www.pdas.com/hydro.pdf
  - https://web.archive.org/web/20220128085402/https://www.pdas.com/hydro.pdf
  - https://archive.ph/qEy39
  """
  H_geopotential_alt = asarray(geopotential_altitude_m, 'float').ravel()
  with warnings.catch_warnings():
    warnings.filterwarnings('ignore', category=RuntimeWarning)
    Z_geometric_alt = earth_radius_m * H_geopotential_alt / (earth_radius_m - H_geopotential_alt)
  ##
  Z_geometric_alt[H_geopotential_alt == -inf] = -earth_radius_m
  Z_geometric_alt[H_geopotential_alt >= earth_radius_m] = inf
  if isinstance(geopotential_altitude_m, ndarray):
    return Z_geometric_alt.reshape(geopotential_altitude_m.shape)
  else:
    return float(Z_geometric_alt)
  ##
##

######################


def calculateGeopotentialAltitudeFromECEF(position_ecef: PositionEcefGenericInterface[FloatXorNdarray], earth_radius_m: float = SPHERICAL_EARTH_RADIUS_m, ) -> FloatXorNdarray:
  """ Calculates geopotential altitude assuming a given spherical earth radius
  """
  geometric_altitude_m = calculateGeometricAltitudeFromRadius(
      r_m=norm(position_ecef.asMatrixECEF(), axis=-1),
      earth_radius_m=earth_radius_m,
  )
  geopotential_alt_m = calculateGeopotentialAltitudeFromGeometricAltitude(geometric_altitude_m=geometric_altitude_m, earth_radius_m=earth_radius_m)
  return geopotential_alt_m
##

######################


def calculateGravity(position_ecef: PositionEcefGenericInterface[FloatXorNdarray], nominal_gravity_mps2: float = SPHERICAL_EARTH_NOMINAL_GRAVITY_mps2, earth_radius_m: float = SPHERICAL_EARTH_RADIUS_m, ) -> ndarray:
  """ Calculates gravity assuming earth is a perfect sphere with uniformly distributed mass.

  Reference:
  - https://en.wikipedia.org/wiki/Gravity_of_Earth#Altitude
  - https://web.archive.org/web/20221204043447/https://en.wikipedia.org/wiki/Gravity_of_Earth
  -
  """
  geometric_altitude_m = calculateGeometricAltitudeFromRadius(
      r_m=norm(position_ecef.asMatrixECEF(), axis=-1),
      earth_radius_m=earth_radius_m,
  )
  gravity_magnitude_denom = earth_radius_m + geometric_altitude_m
  valid_denom = gravity_magnitude_denom != 0.
  direction = getGeocentricDirection(position_ecef)
  gravity_mps2 = zeros(shape=direction.shape)
  gravity_mps2[valid_denom, ...] = direction[valid_denom, ...] * (nominal_gravity_mps2 * (earth_radius_m / gravity_magnitude_denom[valid_denom]))[..., newaxis]
  return gravity_mps2
##

######################


@overload
def calculateTravelPoints(point: PositionLatLonScalarInterface, headings_rad: ndarray, distance_m: float) -> PositionLatLonArrayInterface:
  ...


@overload
def calculateTravelPoints(point: PositionLlaScalarInterface, headings_rad: ndarray, distance_m: float) -> PositionLlaArrayInterface:
  ...


def calculateTravelPoints(point: Union[PositionLatLonScalarInterface, PositionLlaScalarInterface], headings_rad: ndarray, distance_m: float) -> Union[PositionLatLonArrayInterface, PositionLlaArrayInterface]:
  ecef_reference = point.asECEF_geocentric()
  headings_rad = asarray(headings_rad).ravel()
  reference_xyz = ecef_reference.asMatrixECEF()
  radius_m = norm(reference_xyz)
  ned_arr = PositionArrayNED(
      data_ned=column_stack([
          cos(headings_rad),
          sin(headings_rad),
          zeros_like(headings_rad)
      ]) * radius_m,
      ecef_reference=ecef_reference,
  )
  points_xyz = ned_arr.asECEF_geocentric().asMatrixECEF()
  rotation_axes = cross(
      reference_xyz,
      points_xyz - reference_xyz,
      axis=-1,
  )
  quats = axisAngleToQuaternion(
      axis=rotation_axes,
      angles_rad=float(distance_m / radius_m),
  )
  rotated_ecef_xyz = applyUnitQuaternion(
      vec=reference_xyz,
      quat=quats,
  )
  rotated_lla = PositionArrayECEF.fromMatrixECEF(rotated_ecef_xyz).asLLA_geocentric()
  if hasattr(point, 'altitude_m'):
    # Replace with original altitude
    out_lla = rotated_lla.replace(
        altitude_m=zeros_like(rotated_lla.altitude_m) + point.altitude_m,
    )
    return out_lla
  ##
  # otherwise strip the atltitude and return
  out_latlon = rotated_lla.asPositionLatLon()
  return out_latlon
##
