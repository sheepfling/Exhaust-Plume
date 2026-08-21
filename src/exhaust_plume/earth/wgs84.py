# -*- coding: utf-8 -*-
# WGS information sourced from NGA.STND.0036_1.0.0_WGS84.pdf
# Link: https://archive.org/details/nga.-stnd.-0036-1.0.0-wgs-84
from __future__ import annotations

import warnings
from dataclasses import dataclass, fields
from typing import ClassVar

from numpy import arctan2, column_stack, concatenate, cos, einsum, logical_not, ndarray, sin, sqrt, zeros
from numpy.linalg import norm

from exhaust_plume.log.log import getCleanLogger

__all__ = (
    'Wgs84Constants',
    'calculateWgs84Gravity',
    'calculateWgs84GravityEcef',
)

########################################
log = getCleanLogger(__name__)


class Wgs84Constants:
  # Table 3.1 WGS 84 Defining Parameters
  semi_major_axis: ClassVar[float] = 6378137.0  # m
  inverse_flattening_factor: ClassVar[float] = 298.257223563  # unitless
  geocentric_gravitational_factor: ClassVar[float] = 3.986004418e14  # m^3/s^2
  nominal_mean_angular_velocity: ClassVar[float] = 7.292115e-5  # rad/s

  a: ClassVar[float] = semi_major_axis
  GM: ClassVar[float] = geocentric_gravitational_factor
  omega: ClassVar[float] = nominal_mean_angular_velocity

  # Table 3.3 Other Fundamental Constants and Best Accepted Values
  mean_mass_atmosphere: ClassVar[float] = 5.148e18  # kg
  dynamic_ellipticity: ClassVar[float] = 3.273795e-3  # unitless

  M_A: ClassVar[float] = mean_mass_atmosphere
  H: ClassVar[float] = dynamic_ellipticity

  # Table 3.5 WGS 84 Ellipsoid Derived Geometric Constants
  flattening_factor: ClassVar[float] = 1 / inverse_flattening_factor
  f: ClassVar[float] = flattening_factor
  semi_minor_axis: ClassVar[float] = 6356752.3142  # m
  b: ClassVar[float] = semi_minor_axis
  first_eccentricity: ClassVar[float] = 8.1819190842622e-2  # unitless
  first_eccentricity_squared: ClassVar[float] = first_eccentricity**2
  e: ClassVar[float] = first_eccentricity
  second_eccentricity: ClassVar[float] = 8.2094437949696e-2
  second_eccentricity_squared: ClassVar[float] = second_eccentricity**2
  ep: ClassVar[float] = second_eccentricity
  linear_eccentricity: ClassVar[float] = 5.2185400842339e5  # m
  E: ClassVar[float] = linear_eccentricity
  polar_radius_of_curvature: ClassVar[float] = 6399593.6258  # m
  Rp: ClassVar[float] = polar_radius_of_curvature
  axis_ratio: ClassVar[float] = b / a
  mean_radius_of_three_semi_axes: ClassVar[float] = 6371008.7714  # m
  radius_of_sphere_of_equal_area: ClassVar[float] = 6371007.1810  # m
  radius_of_sphere_of_equal_volume: ClassVar[float] = 6371000.7900  # m
  R1: ClassVar[float] = mean_radius_of_three_semi_axes
  R2: ClassVar[float] = radius_of_sphere_of_equal_area
  R3: ClassVar[float] = radius_of_sphere_of_equal_volume
  second_degree_zonal_harmonic: ClassVar[float] = -4.84166774985e-4  # unitless
  Cbar_2_0geo: ClassVar[float] = second_degree_zonal_harmonic
  dynamical_form_factor: ClassVar[float] = 1.082629821313e-3  # unitless
  J_2geo: ClassVar[float] = dynamical_form_factor

  # Table 3.6 WGS 84 Derived Physical Constants
  normal_gravity_potential_ellipsoid: ClassVar[float] = 6.26368517146e7  # m^2/s^2
  U0: ClassVar[float] = normal_gravity_potential_ellipsoid
  normal_gravity_ellipsoid_equator: ClassVar[float] = 9.7803253359  # m/s^2
  gamma_e: ClassVar[float] = normal_gravity_ellipsoid_equator
  normal_gravity_ellipsoid_pole: ClassVar[float] = 9.8321849379  # m/s^2
  gamma_p: ClassVar[float] = normal_gravity_ellipsoid_pole
  normal_gravity_ellipsoid_mean: ClassVar[float] = 9.7976432223  # m/s^2
  gamma_bar: ClassVar[float] = normal_gravity_ellipsoid_mean
  somigliana_normal_gravity_constant: ClassVar[float] = 1.931852652458e-3  # m
  k: ClassVar[float] = somigliana_normal_gravity_constant
  normal_gravity_formula_constant: ClassVar[float] = 3.449786506841e-3  # unitless
  m: ClassVar[float] = normal_gravity_formula_constant
  mass_of_earth: ClassVar[float] = 5.9721864e24  # kg (including atmosphere)
  M: ClassVar[float] = mass_of_earth
  gravitation_constant_geocentric_no_atmos: ClassVar[float] = 3.986000982e14  # m^3/s^2
  GMp: ClassVar[float] = gravitation_constant_geocentric_no_atmos
  gravitation_constant_geocentric_atmos: ClassVar[float] = 3.4359e8  # m^3/s^2
  GM_A: ClassVar[float] = gravitation_constant_geocentric_atmos
##


@dataclass(frozen=True)
class GravityCalculationOutput:
  valid: ndarray
  beta: ndarray
  longitude_rad: ndarray
  u: ndarray
  total: ndarray
  gravity_ellipsoid_u_beta_longitude: ndarray  #
  gravity_ecef: ndarray

  def __post_init__(self) -> None:
    for f in fields(self):
      v = getattr(self, f.name)
      if isinstance(v, ndarray):
        v.flags.writeable = False
      ##
    ##
  ##
##


@dataclass(frozen=True)
class EllipsoidalCoordinates:
  beta: ndarray
  longitude_rad: ndarray
  u: ndarray
  valid: ndarray

  def __post_init__(self) -> None:
    for f in fields(self):
      v = getattr(self, f.name)
      if isinstance(v, ndarray):
        v.flags.writeable = False
      ##
    ##
  ##
##


def ecef2ellipsoidal(ecef_xyz: ndarray) -> EllipsoidalCoordinates:
  """ Assumes ECEF XYZ is (...,3) """
  z = ecef_xyz[..., 2].ravel()
  z2 = z**2
  rho = norm(ecef_xyz[..., (0, 1)], axis=-1)
  r = norm(ecef_xyz, axis=-1)
  r2 = r**2

  E = Wgs84Constants.E  # Equation 4-7
  E2 = E**2

  # Equation 4-8
  u2 = 0.5 * (r2 - E2) * (1 + sqrt(1 + (4 * E2 * z2) / ((r2 - E2)**2)))
  u = zeros(shape=u2.shape)
  valid = u2 >= 0
  u[valid] = sqrt(u2[valid])
  # Equation 4-9
  u2_E2 = (u**2 + E2)
  sqrt_u2_E2 = sqrt(u2_E2)
  beta = arctan2(z * sqrt_u2_E2, u * rho)

  out = EllipsoidalCoordinates(
      u=u,
      beta=beta,
      longitude_rad=arctan2(ecef_xyz[..., 1], ecef_xyz[..., 0]),  # arctan(Y,X)
      valid=valid,
  )
  return out
##


def calculateWgs84Gravity(ecef_xyz: ndarray) -> GravityCalculationOutput:
  """ If Latitude(deg), Longitude(deg), Altitude is supplied,
   then the values must be within normal bounds for those variables ie
   Latitude  within [-90, 90]
   Longitude within [-180, 180]
  """
  # Ellipsodal coordinates (lamb,beta,u)
  # Cartesian coordinates (x,y,z) (aligned with ellipsoidal axes)
  shape = ecef_xyz.shape
  if len(shape) > 2:
    ecef_xyz = column_stack([
        ecef_xyz[..., 0].ravel(),
        ecef_xyz[..., 1].ravel(),
        ecef_xyz[..., 2].ravel(),
    ])
  ##
  ellipsoidal = ecef2ellipsoidal(ecef_xyz=ecef_xyz)

  a = Wgs84Constants.a
  b = Wgs84Constants.b
  GM = Wgs84Constants.GM
  omega = Wgs84Constants.omega

  E = Wgs84Constants.E  # Equation 4-7
  E2 = E**2

  u = ellipsoidal.u
  beta = ellipsoidal.beta
  sbeta = sin(beta)
  cbeta = cos(beta)
  u2_E2 = (u**2 + E2)
  sqrt_u2_E2 = sqrt(u2_E2)
  # Equation 4-10
  w = sqrt((u**2 + (E * sbeta)**2) / u2_E2)

  # Equation 4-11
  u_div_E = (u / E)
  u_div_E_2 = u_div_E**2
  atan_E_u = arctan2(E, u)
  q = 0.5 * ((1 + 3 * u_div_E_2) * atan_E_u - 3 * u_div_E)
  # Equation 4-12
  q0 = 0.5 * ((1 + 3 * ((b / E)**2)) * arctan2(E, b) - 3 * b / E)
  # Equation 4-13
  qp = 3 * (1 + u_div_E_2) * (1 - u / E * atan_E_u) - 1

  # Equation 4-5
  omega2 = omega**2
  with warnings.catch_warnings():
    warnings.filterwarnings('ignore', 'divide by zero encountered in divide')
    div_w = 1. / w
  ##
  with warnings.catch_warnings():
    warnings.filterwarnings('ignore', 'invalid value encountered in multiply')
    gamma_u = div_w * (
        -(GM / u2_E2 + ((omega2 * (a**2) * E) / u2_E2) * (qp / q0) * (0.5 * (sbeta)**2 - 1 / 6.)) +
        (omega2 * u * (cbeta**2))
    )
    # Equation 4-6
    gamma_beta = div_w * (
        (omega2 * (a**2) / sqrt_u2_E2) * (q / q0) * sbeta * cbeta -
        (omega2 * sqrt_u2_E2 * sbeta * cbeta)
    )
    u_div_w_sqrt_u2_E2_cbeta = div_w * u / sqrt_u2_E2 * cbeta
    div_w_sbeta = div_w * sbeta
  ##

  gamma_ellipsoid = column_stack([
      gamma_u.ravel(),
      gamma_beta.ravel(),
      zeros(gamma_beta.shape),
  ])
  gamma_total = norm(gamma_ellipsoid, axis=-1)  # Equation 4-4

  # Equation 4-18
  # gamma[x,y,z] = R1 * gamma_ellipsoid[u,beta,lambda=longitude]
  R1 = zeros(shape=(u.size, 3, 3))
  clon = cos(ellipsoidal.longitude_rad)
  slon = sin(ellipsoidal.longitude_rad)
  R1[..., 0, 0] = u_div_w_sqrt_u2_E2_cbeta * clon
  R1[..., 0, 1] = -div_w_sbeta * clon
  R1[..., 0, 2] = -slon
  R1[..., 1, 0] = u_div_w_sqrt_u2_E2_cbeta * slon
  R1[..., 1, 1] = -div_w_sbeta * slon
  R1[..., 1, 2] = clon
  R1[..., 2, 0] = div_w_sbeta
  R1[..., 2, 1] = u_div_w_sqrt_u2_E2_cbeta
  gamma_ecef = einsum('nij,nj->ni', R1, gamma_ellipsoid)

  not_valid = logical_not(ellipsoidal.valid)
  if any(not_valid.ravel()):
    # Invalid occurs when u=0., at that point gravity is zero.
    gamma_total[not_valid] = 0.
    gamma_ellipsoid[not_valid, ...] = 0.
    gamma_ecef[not_valid, ...] = 0.
  ##

  if len(shape) == 1:
    gamma_total = gamma_total.ravel()
    valid = ellipsoidal.valid.ravel()
    gamma_ellipsoid = gamma_ellipsoid.ravel()
    gamma_ecef = gamma_ecef.ravel()
    longitude_rad = ellipsoidal.longitude_rad.ravel()
  else:
    begin_shape = shape[:-1]
    gamma_total = gamma_total.reshape(begin_shape)
    valid = ellipsoidal.valid.reshape(begin_shape)
    u = u.reshape(begin_shape)
    beta = beta.reshape(begin_shape)
    longitude_rad = ellipsoidal.longitude_rad.reshape(begin_shape)
    gamma_ellipsoid = concatenate([gamma_ellipsoid[..., i].reshape(begin_shape + (1,)) for i in range(3)], axis=-1)
    gamma_ecef = concatenate([gamma_ecef[..., i].reshape(begin_shape + (1,)) for i in range(3)], axis=-1)
  ##
  out = GravityCalculationOutput(
      valid=valid,
      beta=beta,
      longitude_rad=longitude_rad,
      u=u,
      total=gamma_total,
      gravity_ellipsoid_u_beta_longitude=gamma_ellipsoid,
      gravity_ecef=gamma_ecef,
  )
  return out
##


def calculateWgs84GravityEcef(ecef_xyz: ndarray) -> ndarray:
  """ Returns just the ECEF components of the gravity """
  gravity_values = calculateWgs84Gravity(ecef_xyz=ecef_xyz)
  return gravity_values.gravity_ecef
##
