"""Replaceable entrainment, source-term, and termination closures."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from math import exp, pi, sqrt
from numbers import Integral
from typing import Protocol

import numpy as np

from exhaust_plume.models.plume._curved_plume_common import (
    FloatArray,
    _asReadOnlyArray,
    _asReadOnlyVector3,
    _validateFinite,
    _validateNonnegativeFinite,
    _validatePositiveFinite,
)
from exhaust_plume.models.plume.curved_plume_state import (
    CurvedPlumeSource,
    CurvedPlumeStation,
)


@dataclass(frozen=True)
class CurvedPlumeSourceTerms:
  """External force and energy source per unit centerline length."""

  force_Npm: FloatArray
  energy_source_Wpm: float = 0.

  def __post_init__(self) -> None:
    object.__setattr__(self, 'force_Npm', _asReadOnlyVector3('force_Npm', self.force_Npm))
    object.__setattr__(self, 'energy_source_Wpm', _validateFinite('energy_source_Wpm', self.energy_source_Wpm))
  ####
####


class CurvedPlumeSourceTermModel(Protocol):
  """Closure for forces and energy exchange not caused by entrainment."""

  def calculateSourceTerms(
      self,
      *,
      arc_length_m: float,
      station: CurvedPlumeStation,
      source: CurvedPlumeSource,
  ) -> CurvedPlumeSourceTerms:
    """Return external source terms per unit centerline length."""
    ...
####


@dataclass(frozen=True)
class ZeroCurvedPlumeSourceTermModel:
  """Default closure with no body force, drag, heat loss, or chemistry."""

  def calculateSourceTerms(
      self,
      *,
      arc_length_m: float,
      station: CurvedPlumeStation,
      source: CurvedPlumeSource,
  ) -> CurvedPlumeSourceTerms:
    _validateNonnegativeFinite('arc_length_m', arc_length_m)
    del station, source
    return CurvedPlumeSourceTerms(force_Npm=np.zeros(3), energy_source_Wpm=0.)
  ####
####


class EntrainmentModel(Protocol):
  """Closure for ambient mass entrained per unit plume length."""

  def calculateMassEntrainmentPerLength(
      self,
      *,
      arc_length_m: float,
      station: CurvedPlumeStation,
      source: CurvedPlumeSource,
  ) -> float:
    """Return entrained ambient mass per unit centerline length."""
    ...
####


@dataclass(frozen=True)
class ConstantEntrainment:
  """Constant entrainment closure used for analytical regression tests."""

  mass_entrainment_kgpspm: float

  def __post_init__(self) -> None:
    object.__setattr__(
        self,
        'mass_entrainment_kgpspm',
        _validateNonnegativeFinite('mass_entrainment_kgpspm', self.mass_entrainment_kgpspm),
    )
  ####

  def calculateMassEntrainmentPerLength(
      self,
      *,
      arc_length_m: float,
      station: CurvedPlumeStation,
      source: CurvedPlumeSource,
  ) -> float:
    _validateNonnegativeFinite('arc_length_m', arc_length_m)
    del station, source
    return self.mass_entrainment_kgpspm
  ####
####


@dataclass(frozen=True)
class DevelopingShearForcedEntrainment:
  """Candidate shear-plus-crossflow entrainment closure.

  The generalized-mean exponent exposes the uncertain combination rule rather
  than embedding one unvalidated choice in the conservation solver.
  """

  shear_coefficient: float = .06
  forced_coefficient: float = 0.
  combination_exponent: float = 2.
  initial_development_fraction: float = 1.
  development_length_m: float = 1.

  def __post_init__(self) -> None:
    object.__setattr__(self, 'shear_coefficient', _validateNonnegativeFinite('shear_coefficient', self.shear_coefficient))
    object.__setattr__(self, 'forced_coefficient', _validateNonnegativeFinite('forced_coefficient', self.forced_coefficient))
    combination_exponent = _validatePositiveFinite('combination_exponent', self.combination_exponent)
    if combination_exponent < 1.:
      raise ValueError(f'Expected `combination_exponent` to be at least 1. Got:{combination_exponent}')
    ####
    initial_development_fraction = _validateFinite('initial_development_fraction', self.initial_development_fraction)
    if not 0. <= initial_development_fraction <= 1.:
      raise ValueError(
          'Expected `initial_development_fraction` in [0, 1]. '
          f'Got:{initial_development_fraction}'
      )
    ####
    object.__setattr__(self, 'combination_exponent', combination_exponent)
    object.__setattr__(self, 'initial_development_fraction', initial_development_fraction)
    object.__setattr__(self, 'development_length_m', _validatePositiveFinite('development_length_m', self.development_length_m))
  ####

  def calculateMassEntrainmentPerLength(
      self,
      *,
      arc_length_m: float,
      station: CurvedPlumeStation,
      source: CurvedPlumeSource,
  ) -> float:
    del source
    arc_length = _validateNonnegativeFinite('arc_length_m', arc_length_m)
    development_factor = self.initial_development_fraction + (1. - self.initial_development_fraction) * (
        1. - exp(-arc_length / self.development_length_m)
    )
    tangent = station.tangent
    relative_velocity = station.relative_velocity_mps
    parallel_speed = abs(float(relative_velocity @ tangent))
    ambient_crossflow = station.ambient_velocity_mps - float(station.ambient_velocity_mps @ tangent) * tangent
    crossflow_speed = float(np.linalg.norm(ambient_crossflow))
    shear_entrainment = (
        2. * pi * station.radius_m * self.shear_coefficient * development_factor
        * sqrt(station.density_kgpm3 * station.ambient_density_kgpm3) * parallel_speed
    )
    forced_entrainment = (
        2. * station.radius_m * self.forced_coefficient * station.ambient_density_kgpm3 * crossflow_speed
    )
    exponent = self.combination_exponent
    return float((shear_entrainment ** exponent + forced_entrainment ** exponent) ** (1. / exponent))
  ####
####


class CurvedPlumeTermination(Enum):
  """Reason the curved-plume integration ended."""

  DOMAIN_LIMIT = auto()
  EQUILIBRIUM = auto()
  NUMERICAL_FAILURE = auto()
####


@dataclass(frozen=True)
class CurvedPlumeOptions:
  """Numerical domain, tolerance, and equilibrium settings."""

  max_arc_length_m: float
  number_of_stations: int = 201
  relative_tolerance: float = 1.e-8
  absolute_tolerance: float = 1.e-10
  max_step_m: float = np.inf
  pressure_match_relative_tolerance: float = .05
  minimum_speed_mps: float = 1.e-6
  enable_equilibrium_termination: bool = False
  equilibrium_exhaust_mass_fraction: float = 1.e-3
  equilibrium_temperature_excess_K: float = 1.
  equilibrium_relative_speed_mps: float = .5

  def __post_init__(self) -> None:
    object.__setattr__(self, 'max_arc_length_m', _validatePositiveFinite('max_arc_length_m', self.max_arc_length_m))
    if isinstance(self.number_of_stations, bool) or not isinstance(self.number_of_stations, Integral) or self.number_of_stations < 2:
      raise ValueError(f'Expected `number_of_stations` to be an integer at least 2. Got:{self.number_of_stations}')
    ####
    object.__setattr__(self, 'number_of_stations', int(self.number_of_stations))
    object.__setattr__(self, 'relative_tolerance', _validatePositiveFinite('relative_tolerance', self.relative_tolerance))
    object.__setattr__(self, 'absolute_tolerance', _validatePositiveFinite('absolute_tolerance', self.absolute_tolerance))
    max_step = float(self.max_step_m)
    if max_step <= 0. or np.isnan(max_step):
      raise ValueError(f'Expected `max_step_m` to be positive. Got:{self.max_step_m}')
    ####
    object.__setattr__(self, 'max_step_m', max_step)
    object.__setattr__(
        self,
        'pressure_match_relative_tolerance',
        _validateNonnegativeFinite('pressure_match_relative_tolerance', self.pressure_match_relative_tolerance),
    )
    object.__setattr__(self, 'minimum_speed_mps', _validatePositiveFinite('minimum_speed_mps', self.minimum_speed_mps))
    object.__setattr__(
        self,
        'equilibrium_exhaust_mass_fraction',
        _validatePositiveFinite('equilibrium_exhaust_mass_fraction', self.equilibrium_exhaust_mass_fraction),
    )
    object.__setattr__(
        self,
        'equilibrium_temperature_excess_K',
        _validatePositiveFinite('equilibrium_temperature_excess_K', self.equilibrium_temperature_excess_K),
    )
    object.__setattr__(
        self,
        'equilibrium_relative_speed_mps',
        _validatePositiveFinite('equilibrium_relative_speed_mps', self.equilibrium_relative_speed_mps),
    )
  ####
####


@dataclass(frozen=True)
class CurvedPlumeResult:
  """Calculated centerline stations and solver termination metadata."""

  stations: tuple[CurvedPlumeStation, ...]
  termination: CurvedPlumeTermination
  solver_message: str
  function_evaluations: int

  def __post_init__(self) -> None:
    if not self.stations:
      raise ValueError('Expected at least one curved-plume station.')
    ####
    if self.function_evaluations < 0:
      raise ValueError(f'Expected nonnegative function evaluations. Got:{self.function_evaluations}')
    ####
  ####

  @property
  def positions_m(self) -> FloatArray:
    return _asReadOnlyArray('positions_m', np.vstack([station.position_m for station in self.stations]))
  ####

  @property
  def arc_lengths_m(self) -> FloatArray:
    return _asReadOnlyArray('arc_lengths_m', [station.arc_length_m for station in self.stations])
  ####
####
