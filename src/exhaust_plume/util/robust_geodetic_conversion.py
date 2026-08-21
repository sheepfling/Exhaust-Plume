# -*- coding: utf-8 -*-
# Robustly determines geodetic coordinates
from __future__ import annotations

import warnings

from numpy import any as np_any, arcsin, arctan2, array, clip, column_stack, cos, deg2rad, einsum, inf, isfinite, ndarray, rad2deg, sin, sqrt, sum as np_sum, zeros
from numpy.linalg import norm
from radar_tools.geov import ecef2enuT, ecef2llh as rt_ecef2llh, enu2ecefT

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

_EARTH_XYZ = array([[EARTH_SEMI_MAJOR_AXIS, EARTH_SEMI_MAJOR_AXIS, EARTH_SEMI_MINOR_AXIS, ]])


def _backup_ecef2lla(position_xyz: ndarray) -> ndarray:
  # Finds approximate radius at point and then assumes spherical
  # Returns lat (deg), lon(deg), height (m)
  if all((position_xyz == 0.).ravel()):
    return array([0., 0., -EARTH_SEMI_MINOR_AXIS])
  ##
  lgc = np_any(position_xyz != 0., axis=-1)
  r_xyz = norm(position_xyz, axis=-1, keepdims=True)
  dir_xyz = zeros(position_xyz.shape)
  dir_xyz[lgc] = position_xyz[lgc] / r_xyz
  dir_xyz[~lgc] = array([1., 0., 0.])
  approx_rad = np_sum(_EARTH_XYZ * (dir_xyz**2), axis=-1)
  altitude_m = r_xyz - approx_rad
  latitude_deg = zeros(altitude_m.shape)
  latitude_deg[lgc] = rad2deg(arcsin(position_xyz[lgc, 2] / r_xyz[lgc]))
  longitude_deg = rad2deg(arctan2(position_xyz[..., 1], position_xyz[..., 0]))
  out = column_stack([latitude_deg, longitude_deg, altitude_m])
  return out
##


def ecef2lla(ecef_xyz: ndarray) -> ndarray:
  """ Robustly gets the LatLongHeight of the position - for plotting purposes only
  Radar tools is nice, but it gives errors and warnings pretty easily / returns NaN's at the poles
  This function catches and handles the ValueError due to the alg limit which for plotting purposes is invalid in this case
  Flat-earth mode can place objects at 0.0.0., which is invalid according to ecef2lla
  """
  out_lla = zeros(shape=ecef_xyz.shape)
  no_value_error = False
  with warnings.catch_warnings():
    warnings.filterwarnings('ignore', 'invalid value encountered in sqrt')
    # Also, there are divide by zero errors which can cause runtime warnings which are unnecessary especially for plotting purposes.
    # The for loop is necessary because geov throws a ValueError if any one of the rows is invalid
    try:
      # Try vectorized first to see if it works
      out_lla = rt_ecef2llh(ecef_xyz)
      no_value_error = True
    except ValueError:
      # vectorized failed, so do one row at a time
      pass
    ##
  ##
  if no_value_error and all(isfinite(out_lla).ravel()):
    return out_lla
  ##
  # Reshape intermediate be a matrix / each point is a row
  if out_lla.shape == (3,):
    flat_output = True
    out_lla = out_lla.reshape((1, 3,))
    ecef_xyz = ecef_xyz.reshape((1, 3,))
  else:
    flat_output = False
  ##
  with warnings.catch_warnings():
    warnings.filterwarnings('ignore', 'invalid value encountered in sqrt')
    for row_idx, xyz in enumerate(ecef_xyz):
      try:
        out_lla[row_idx, ...] = rt_ecef2llh(xyz)
      except ValueError:
        # probably the alg limit, ie inside the earth's core
        pass
      ##
      out_lla[row_idx, ...] = _backup_ecef2lla(xyz)
    ##
  ##
  if flat_output:
    out_lla = out_lla.ravel()
  ##
  return out_lla
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
  # radar tools was mostly good, but needs to clip radii when the altitude is less than the minimum
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
  T = ecef2enuT(lla_ref)
  return einsum('...ij,...j->...i', T, position_ecef - reference_ecef)
##


def enu2ecef(position_enu: ndarray, reference_ecef: ndarray) -> ndarray:
  lla_ref = ecef2lla(reference_ecef)
  T = enu2ecefT(lla_ref)
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
  T = enu2ecefT(lla_ref)
  out = einsum('...ij,...j->...i', T, position_enu) + reference_ecef
  return out
##
