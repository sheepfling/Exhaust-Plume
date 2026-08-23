"""Closed-form curved-plume limits used as regression oracles."""

from __future__ import annotations

from dataclasses import dataclass
from math import pi

import numpy as np
from numpy.typing import ArrayLike

from exhaust_plume.models.plume._curved_plume_common import (
    FloatArray,
    _asReadOnlyArray,
    _asReadOnlyVector3,
    _unitVector,
    _validateFinite,
    _validateNonnegativeFinite,
    _validatePositiveFinite,
)


@dataclass(frozen=True)
class ConstantDensityFreeJetExactSolution:
  """Closed-form top-hat free-jet solution used for regression tests."""

  arc_lengths_m: FloatArray
  mass_flow_kgps: FloatArray
  radius_m: FloatArray
  speed_mps: FloatArray
  temperature_K: FloatArray
  exhaust_mass_fraction: FloatArray

  def __post_init__(self) -> None:
    for name in (
        'arc_lengths_m',
        'mass_flow_kgps',
        'radius_m',
        'speed_mps',
        'temperature_K',
        'exhaust_mass_fraction',
    ):
      object.__setattr__(self, name, _asReadOnlyArray(name, getattr(self, name)))
    ####
  ####
####


def calculateConstantDensityFreeJetExact(
    *,
    arc_lengths_m: ArrayLike,
    initial_radius_m: float,
    initial_speed_mps: float,
    density_kgpm3: float,
    entrainment_coefficient: float,
    initial_temperature_K: float,
    ambient_temperature_K: float,
    specific_heat_JpkgK: float,
    initial_exhaust_mass_fraction: float = 1.,
) -> ConstantDensityFreeJetExactSolution:
  """Return the exact constant-density, quiescent-ambient free-jet solution."""
  arc_lengths = np.asarray(arc_lengths_m, dtype=float)
  if arc_lengths.ndim != 1 or not np.isfinite(arc_lengths).all() or np.any(arc_lengths < 0.):
    raise ValueError('Expected finite nonnegative one-dimensional `arc_lengths_m`.')
  ####
  radius_0 = _validatePositiveFinite('initial_radius_m', initial_radius_m)
  speed_0 = _validatePositiveFinite('initial_speed_mps', initial_speed_mps)
  density = _validatePositiveFinite('density_kgpm3', density_kgpm3)
  alpha = _validateNonnegativeFinite('entrainment_coefficient', entrainment_coefficient)
  temperature_0 = _validatePositiveFinite('initial_temperature_K', initial_temperature_K)
  ambient_temperature = _validatePositiveFinite('ambient_temperature_K', ambient_temperature_K)
  specific_heat = _validatePositiveFinite('specific_heat_JpkgK', specific_heat_JpkgK)
  exhaust_fraction_0 = _validateFinite('initial_exhaust_mass_fraction', initial_exhaust_mass_fraction)
  if not 0. <= exhaust_fraction_0 <= 1.:
    raise ValueError(f'Expected `initial_exhaust_mass_fraction` in [0, 1]. Got:{exhaust_fraction_0}')
  ####
  mass_flow_0 = density * pi * radius_0 ** 2 * speed_0
  dilution = 1. + 2. * alpha * arc_lengths / radius_0
  mass_flow = mass_flow_0 * dilution
  radius = radius_0 + 2. * alpha * arc_lengths
  speed = speed_0 / dilution
  temperature = (
      ambient_temperature
      + (temperature_0 - ambient_temperature + speed_0 ** 2 / (2. * specific_heat)) / dilution
      - speed ** 2 / (2. * specific_heat)
  )
  exhaust_mass_fraction = exhaust_fraction_0 / dilution
  return ConstantDensityFreeJetExactSolution(
      arc_lengths_m=arc_lengths,
      mass_flow_kgps=mass_flow,
      radius_m=radius,
      speed_mps=speed,
      temperature_K=temperature,
      exhaust_mass_fraction=exhaust_mass_fraction,
  )
####


@dataclass(frozen=True)
class OrthogonalUniformCrossflowExactSolution:
  """Exact constant-entrainment trajectory for an orthogonal uniform crossflow."""

  arc_lengths_m: FloatArray
  positions_m: FloatArray
  mass_flow_kgps: FloatArray
  momentum_flux_N: FloatArray
  velocity_mps: FloatArray
  turning_length_m: float

  def __post_init__(self) -> None:
    for name in ('arc_lengths_m', 'positions_m', 'mass_flow_kgps', 'momentum_flux_N', 'velocity_mps'):
      object.__setattr__(self, name, _asReadOnlyArray(name, getattr(self, name)))
    ####
    object.__setattr__(self, 'turning_length_m', _validatePositiveFinite('turning_length_m', self.turning_length_m))
  ####
####


def calculateOrthogonalUniformCrossflowExact(
    *,
    arc_lengths_m: ArrayLike,
    source_position_m: ArrayLike,
    jet_direction: ArrayLike,
    crossflow_direction: ArrayLike,
    initial_speed_mps: float,
    crossflow_speed_mps: float,
    initial_mass_flow_kgps: float,
    mass_entrainment_kgpspm: float,
) -> OrthogonalUniformCrossflowExactSolution:
  """Return the exact trajectory for constant entrainment and uniform crossflow."""
  arc_lengths = np.asarray(arc_lengths_m, dtype=float)
  if arc_lengths.ndim != 1 or not np.isfinite(arc_lengths).all() or np.any(arc_lengths < 0.):
    raise ValueError('Expected finite nonnegative one-dimensional `arc_lengths_m`.')
  ####
  source_position = _asReadOnlyVector3('source_position_m', source_position_m)
  jet_axis = _unitVector('jet_direction', jet_direction)
  crossflow_axis = _unitVector('crossflow_direction', crossflow_direction)
  if abs(float(jet_axis @ crossflow_axis)) > 1.e-12:
    raise ValueError('Expected orthogonal jet and crossflow directions.')
  ####
  initial_speed = _validatePositiveFinite('initial_speed_mps', initial_speed_mps)
  crossflow_speed = _validatePositiveFinite('crossflow_speed_mps', crossflow_speed_mps)
  initial_mass_flow = _validatePositiveFinite('initial_mass_flow_kgps', initial_mass_flow_kgps)
  entrainment = _validatePositiveFinite('mass_entrainment_kgpspm', mass_entrainment_kgpspm)
  turning_length = initial_mass_flow * initial_speed / (entrainment * crossflow_speed)
  crossflow_displacement = np.sqrt(arc_lengths ** 2 + turning_length ** 2) - turning_length
  jet_displacement = turning_length * np.arcsinh(arc_lengths / turning_length)
  positions = (
      source_position[np.newaxis, :]
      + crossflow_displacement[:, np.newaxis] * crossflow_axis[np.newaxis, :]
      + jet_displacement[:, np.newaxis] * jet_axis[np.newaxis, :]
  )
  mass_flow = initial_mass_flow + entrainment * arc_lengths
  initial_velocity = initial_speed * jet_axis
  ambient_velocity = crossflow_speed * crossflow_axis
  momentum = (
      initial_mass_flow * initial_velocity[np.newaxis, :]
      + (entrainment * arc_lengths)[:, np.newaxis] * ambient_velocity[np.newaxis, :]
  )
  velocity = momentum / mass_flow[:, np.newaxis]
  return OrthogonalUniformCrossflowExactSolution(
      arc_lengths_m=arc_lengths,
      positions_m=positions,
      mass_flow_kgps=mass_flow,
      momentum_flux_N=momentum,
      velocity_mps=velocity,
      turning_length_m=turning_length,
  )
####
