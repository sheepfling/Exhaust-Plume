"""Developing shear and forced-crossflow entrainment closures."""

from __future__ import annotations

from dataclasses import dataclass
from math import exp, hypot, pi, sqrt

import numpy as np

from exhaust_plume.models.plume._curved_plume_common import (
    _validateNonnegativeFinite,
    _validatePositiveFinite,
)
from exhaust_plume.models.plume.curved_plume_state import (
    CurvedPlumeSource,
    CurvedPlumeStation,
)


@dataclass(frozen=True)
class CurvedPlumeEntrainmentComponents:
  """Resolved components of a round top-hat entrainment closure."""

  development_factor: float
  axial_relative_speed_mps: float
  crossflow_speed_mps: float
  shear_mass_rate_kgpspm: float
  forced_mass_rate_kgpspm: float
  total_mass_rate_kgpspm: float

  def __post_init__(self) -> None:
    _validateNonnegativeFinite('development_factor', self.development_factor)
    _validateNonnegativeFinite('axial_relative_speed_mps', self.axial_relative_speed_mps)
    _validateNonnegativeFinite('crossflow_speed_mps', self.crossflow_speed_mps)
    _validateNonnegativeFinite('shear_mass_rate_kgpspm', self.shear_mass_rate_kgpspm)
    _validateNonnegativeFinite('forced_mass_rate_kgpspm', self.forced_mass_rate_kgpspm)
    _validateNonnegativeFinite('total_mass_rate_kgpspm', self.total_mass_rate_kgpspm)
  ####
####


@dataclass(frozen=True)
class DevelopingShearForcedEntrainment:
  """Round top-hat entrainment with development and crossflow components.

  The shear component uses plume perimeter, axial relative speed, and the
  geometric-mean density ``sqrt(rho * rho_a)``. The forced component uses the
  circular cross-section width presented to ambient flow normal to the plume.
  Components are combined by a configurable p-norm so calibration can test a
  direct sum, root-sum-square, or an intermediate rule without changing the
  conservation kernel.
  """

  shear_coefficient: float
  forced_coefficient: float = 0.
  initial_development_fraction: float = 1.
  development_length_m: float = 1.
  combination_exponent: float = 1.

  def __post_init__(self) -> None:
    _validateNonnegativeFinite('shear_coefficient', self.shear_coefficient)
    _validateNonnegativeFinite('forced_coefficient', self.forced_coefficient)
    _validateNonnegativeFinite(
        'initial_development_fraction', self.initial_development_fraction
    )
    if self.initial_development_fraction > 1.:
      raise ValueError(
          'Expected `initial_development_fraction` to be less than or equal to 1.'
      )
    ####
    _validatePositiveFinite('development_length_m', self.development_length_m)
    _validatePositiveFinite('combination_exponent', self.combination_exponent)
    if self.combination_exponent < 1.:
      raise ValueError('Expected `combination_exponent` to be greater than or equal to 1.')
    ####
  ####

  def calculateDevelopmentFactor(self, arc_length_m: float) -> float:
    _validateNonnegativeFinite('arc_length_m', arc_length_m)
    factor = 1. - (
        1. - self.initial_development_fraction
    ) * exp(-arc_length_m / self.development_length_m)
    return float(factor)
  ####

  def calculateComponents(
      self,
      *,
      arc_length_m: float,
      station: CurvedPlumeStation,
      source: CurvedPlumeSource,
  ) -> CurvedPlumeEntrainmentComponents:
    del source
    development_factor = self.calculateDevelopmentFactor(arc_length_m)
    relative_velocity_mps = station.velocity_mps - station.ambient_velocity_mps
    axial_relative_speed_mps = abs(float(relative_velocity_mps @ station.tangent))
    ambient_crossflow_mps = (
        station.ambient_velocity_mps
        - float(station.ambient_velocity_mps @ station.tangent) * station.tangent
    )
    crossflow_speed_mps = float(np.linalg.norm(ambient_crossflow_mps))
    shear_mass_rate_kgpspm = (
        2. * pi * station.radius_m
        * self.shear_coefficient
        * development_factor
        * sqrt(station.density_kgpm3 * station.ambient_density_kgpm3)
        * axial_relative_speed_mps
    )
    forced_mass_rate_kgpspm = (
        2. * station.radius_m
        * self.forced_coefficient
        * station.ambient_density_kgpm3
        * crossflow_speed_mps
    )
    if self.combination_exponent == 1.:
      total_mass_rate_kgpspm = (
          shear_mass_rate_kgpspm + forced_mass_rate_kgpspm
      )
    elif self.combination_exponent == 2.:
      total_mass_rate_kgpspm = hypot(
          shear_mass_rate_kgpspm,
          forced_mass_rate_kgpspm,
      )
    else:
      exponent = self.combination_exponent
      total_mass_rate_kgpspm = (
          shear_mass_rate_kgpspm ** exponent
          + forced_mass_rate_kgpspm ** exponent
      ) ** (1. / exponent)
    ####
    return CurvedPlumeEntrainmentComponents(
        development_factor=development_factor,
        axial_relative_speed_mps=axial_relative_speed_mps,
        crossflow_speed_mps=crossflow_speed_mps,
        shear_mass_rate_kgpspm=shear_mass_rate_kgpspm,
        forced_mass_rate_kgpspm=forced_mass_rate_kgpspm,
        total_mass_rate_kgpspm=total_mass_rate_kgpspm,
    )
  ####

  def calculateEntrainmentRate(
      self,
      *,
      arc_length_m: float,
      station: CurvedPlumeStation,
      source: CurvedPlumeSource,
  ) -> float:
    components = self.calculateComponents(
        arc_length_m=arc_length_m,
        station=station,
        source=source,
    )
    return components.total_mass_rate_kgpspm
  ####
####


__all__ = (
    'CurvedPlumeEntrainmentComponents',
    'DevelopingShearForcedEntrainment',
)
