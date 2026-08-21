# -*- coding: utf-8 -*-
# Robustly determines geodetic coordinates
from __future__ import annotations

from numpy import abs, arctan2, array, clip, cos, deg2rad, einsum, inf, ndarray, pi, rad2deg, sin, sqrt, stack, where, zeros

from exhaust_plume.earth.constants import EARTH_SEMI_MAJOR_AXIS, EARTH_SEMI_MINOR_AXIS
from exhaust_plume.earth.wgs84 import Wgs84Constants
from exhaust_plume.log.log import getCleanLogger

__all__ = (
    'ecef2lla',
    'lla2ecef',
    ###########
    'ecef2enu',
    'enu2ecef',
    ###########
    'ned2enu',
    'enu2ned',
    ###########
    'ecef2ned',
    'ned2ecef',
)
##########################
log = getCleanLogger(__name__)

_FIRST_ECCENTRICITY_SQUARED = 1. - (EARTH_SEMI_MINOR_AXIS / EARTH_SEMI_MAJOR_AXIS)**2
_SECOND_ECCENTRICITY_SQUARED = (EARTH_SEMI_MAJOR_AXIS / EARTH_SEMI_MINOR_AXIS)**2 - 1.


def _ecef2enu_transform(lla: ndarray) -> ndarray:
  """Return the ECEF-to-ENU rotation for geodetic latitude/longitude."""
  latitude_rad = deg2rad(lla[..., 0])
  longitude_rad = deg2rad(lla[..., 1])
  slat = sin(latitude_rad)
  clat = cos(latitude_rad)
  slon = sin(longitude_rad)
  clon = cos(longitude_rad)
  out = stack((
      stack((-slon, clon, 0. * slon), axis=-1),
      stack((-slat * clon, -slat * slon, clat), axis=-1),
      stack((clat * clon, clat * slon, slat), axis=-1),
  ), axis=-2)
  return out
##


def _enu2ecef_transform(lla: ndarray) -> ndarray:
  return _ecef2enu_transform(lla).swapaxes(-1, -2)
##


def ecef2lla(ecef_xyz: ndarray) -> ndarray:
  """Convert WGS84 ECEF coordinates to geodetic latitude, longitude, height."""
  xyz = array(ecef_xyz, dtype=float)
  if xyz.shape[-1] != 3:
    raise ValueError(f'Expected ECEF coordinates with final dimension 3. Got:{xyz.shape}')
  ##
  x, y, z = (xyz[..., i] for i in range(3))
  p = sqrt(x**2 + y**2)
  theta = arctan2(z * EARTH_SEMI_MAJOR_AXIS, p * EARTH_SEMI_MINOR_AXIS)
  st = sin(theta)
  ct = cos(theta)
  latitude_rad = arctan2(
      z + _SECOND_ECCENTRICITY_SQUARED * EARTH_SEMI_MINOR_AXIS * st**3,
      p - _FIRST_ECCENTRICITY_SQUARED * EARTH_SEMI_MAJOR_AXIS * ct**3,
  )
  longitude_rad = arctan2(y, x)
  sin_latitude = sin(latitude_rad)
  prime_vertical_radius = EARTH_SEMI_MAJOR_AXIS / sqrt(1. - _FIRST_ECCENTRICITY_SQUARED * sin_latitude**2)
  cos_latitude = cos(latitude_rad)
  altitude_m = p / cos_latitude - prime_vertical_radius
  pole = p == 0.
  latitude_rad = where(pole, where(z < 0., -0.5 * pi, 0.5 * pi), latitude_rad)
  longitude_rad = where(pole, 0., longitude_rad)
  altitude_m = where(pole, abs(z) - EARTH_SEMI_MINOR_AXIS, altitude_m)
  return stack((rad2deg(latitude_rad), rad2deg(longitude_rad), altitude_m), axis=-1)
##


def lla2ecef(lla: ndarray) -> ndarray:
  """
  Convert geodetic latitude, longitude, and ellipsoid height to
  Earth-Centered Earth-Fixed Cartesian.

  Parameters
  ----------
  lla: array-like, shape (...,3)
      Geodetic latitude (deg), longitude (deg) and ellipsoid height (m)

  Returns
  -------
  array, shape(...,3)
      Corresponding X,Y,Z ECEF coordinates (m)

  """
  # Clip radii when the requested altitude is below the ellipsoid center.
  lat_rad = deg2rad(lla[..., 0])
  lon_rad = deg2rad(lla[..., 1])
  slat = sin(lat_rad)
  N = EARTH_SEMI_MAJOR_AXIS / sqrt(1 - (Wgs84Constants.first_eccentricity * slat)**2)
  alt = lla[..., 2]
  xy_radius = clip(N + alt, 0., inf)
  clat = cos(lat_rad)
  slon = sin(lon_rad)
  clon = cos(lon_rad)
  XYZ = zeros(lla.shape)
  XYZ[..., 0] = xy_radius * clat * clon
  XYZ[..., 1] = xy_radius * clat * slon
  z_radius = clip((1 - Wgs84Constants.flattening_factor)**2 * N + alt, 0., inf)
  XYZ[..., 2] = z_radius * slat
  return XYZ
##


def ecef2enu(position_ecef: ndarray, reference_ecef: ndarray) -> ndarray:
  lla_ref = ecef2lla(ecef_xyz=reference_ecef)
  T = _ecef2enu_transform(lla_ref)
  return einsum('...ij,...j->...i', T, position_ecef - reference_ecef)
##


def enu2ecef(position_enu: ndarray, reference_ecef: ndarray) -> ndarray:
  lla_ref = ecef2lla(reference_ecef)
  T = _enu2ecef_transform(lla_ref)
  return einsum('...ij,...j->...i', T, position_enu) + reference_ecef
##


def enu2ned(enu: ndarray) -> ndarray:
  """ Assumes shape (...,3) input """
  ned = enu[..., (1, 0, 2,)]
  ned[..., 2] *= -1
  return ned
##


def ned2enu(ned: ndarray) -> ndarray:
  """ Assumes shape (...,3) input """
  enu = ned[..., (1, 0, 2,)]
  enu[..., 2] *= -1
  return enu
##


def ecef2ned(position_ecef: ndarray, reference_ecef: ndarray) -> ndarray:
  enu = ecef2enu(position_ecef=position_ecef, reference_ecef=reference_ecef)
  enu[..., (0, 1)] = enu[..., (1, 0)]
  enu[..., 2] *= -1
  return enu
##


def ned2ecef(position_ned: ndarray, reference_ecef: ndarray) -> ndarray:
  position_enu = ned2enu(ned=position_ned)
  lla_ref = ecef2lla(reference_ecef)
  T = _enu2ecef_transform(lla_ref)
  out = einsum('...ij,...j->...i', T, position_enu) + reference_ecef
  return out
##
