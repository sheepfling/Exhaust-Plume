# -*- coding: utf-8 -*-
# Robustly determines Geo-CENTRIC coordinates
from __future__ import annotations

from numpy import arcsin, arctan2, clip, concatenate, cos, deg2rad, einsum, inf, ndarray, newaxis, rad2deg, sin, zeros
from numpy.linalg import norm

from exhaust_plume.earth.spherical_earth_constants import SPHERICAL_EARTH_RADIUS_m
from exhaust_plume.log.log import getCleanLogger
from exhaust_plume.util.robust_geodetic_conversion import _ecef2enu_transform, _enu2ecef_transform, ned2enu

__all__ = (
    'ecef2lla_geocentric',
    'lla_geocentric2ecef',
    ####
    'ecef2enu_geocentric',
    'enu_geocentric2ecef',
    ####
    'ned_geocentric2ecef',
    'ecef2ned_geocentric',
)
##########################
log = getCleanLogger(__name__)


def ecef2lla_geocentric(ecef_xyz: ndarray, earth_radius_m: float = SPHERICAL_EARTH_RADIUS_m) -> ndarray:
  """ Returns geocentric Latitude (deg), Longitude (deg), Altitude for a given spherical earth radius. """
  r_m = norm(ecef_xyz, axis=-1)
  longitude_deg = rad2deg(arctan2(ecef_xyz[..., 1], ecef_xyz[..., 0]))
  latitude_deg = zeros(shape=r_m.shape)
  valid_r = r_m != 0.
  latitude_deg[valid_r] = rad2deg(arcsin(ecef_xyz[valid_r, 2] / r_m[valid_r]))
  altitude_m = r_m - earth_radius_m
  out = concatenate([x[..., newaxis] for x in (
      latitude_deg,
      longitude_deg,
      altitude_m,
  )], axis=-1)
  return out
##


def lla_geocentric2ecef(lla_geocentric: ndarray, earth_radius_m: float = SPHERICAL_EARTH_RADIUS_m) -> ndarray:
  """ Returns ECEF coordinates XYZ from a geocentric Latitude (deg), Longitude (deg), Altitude coordinates with a given spherical earth radius.
  If the altitude component is less than -earth_radius, then it will be treated as the minimum altitude (the core/ radius=0)
  """
  latitude_rad = deg2rad(lla_geocentric[..., 0])
  longitude_rad = deg2rad(lla_geocentric[..., 1])
  clat = cos(latitude_rad)
  slat = sin(latitude_rad)
  clon = cos(longitude_rad)
  slon = sin(longitude_rad)
  direction = concatenate([x[..., newaxis] for x in (
      clat * clon,
      clat * slon,
      slat,
  )], axis=-1)
  radius_m = clip(lla_geocentric[..., 2] + earth_radius_m, 0., inf)
  ecef_xyz = radius_m[..., newaxis] * direction
  return ecef_xyz
##


def ecef2enu_geocentric(position_ecef: ndarray, reference_ecef: ndarray, earth_radius_m: float = SPHERICAL_EARTH_RADIUS_m) -> ndarray:
  lla_ref = ecef2lla_geocentric(ecef_xyz=reference_ecef, earth_radius_m=earth_radius_m)
  T = _ecef2enu_transform(lla_ref)
  return einsum('...ij,...j->...i', T, position_ecef - reference_ecef)
##


def enu_geocentric2ecef(position_enu: ndarray, reference_ecef: ndarray, earth_radius_m: float = SPHERICAL_EARTH_RADIUS_m) -> ndarray:
  lla_ref = ecef2lla_geocentric(ecef_xyz=reference_ecef, earth_radius_m=earth_radius_m)
  T = _enu2ecef_transform(lla_ref)
  return einsum('...ij,...j->...i', T, position_enu) + reference_ecef
##


def ecef2ned_geocentric(position_ecef: ndarray, reference_ecef: ndarray, earth_radius_m: float = SPHERICAL_EARTH_RADIUS_m) -> ndarray:
  enu = ecef2enu_geocentric(position_ecef=position_ecef, reference_ecef=reference_ecef, earth_radius_m=earth_radius_m)
  enu[..., (0, 1)] = enu[..., (1, 0)]
  enu[..., 2] *= -1
  return enu
##


def ned_geocentric2ecef(position_ned: ndarray, reference_ecef: ndarray, earth_radius_m: float = SPHERICAL_EARTH_RADIUS_m) -> ndarray:
  position_enu = ned2enu(ned=position_ned)
  lla_ref = ecef2lla_geocentric(ecef_xyz=reference_ecef, earth_radius_m=earth_radius_m)
  T = _enu2ecef_transform(lla_ref)
  out = einsum('...ij,...j->...i', T, position_enu) + reference_ecef
  return out
##
