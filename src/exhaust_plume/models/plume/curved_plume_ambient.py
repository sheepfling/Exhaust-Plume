"""Composable ambient-velocity fields for curved-plume calculations."""

from __future__ import annotations

from dataclasses import dataclass
from math import exp, pi, sqrt
from typing import Protocol

import numpy as np

from exhaust_plume.models.plume._curved_plume_common import (
    FloatArray,
    _asReadOnlyVector3,
    _unitVector,
    _validateFinite,
    _validateNonnegativeFinite,
    _validatePositiveFinite,
)
from exhaust_plume.models.plume.curved_plume_state import (
    AmbientState,
    AmbientStateField,
)


class AmbientVelocityField(Protocol):
  """Spatial velocity contribution added to a background ambient state."""

  def sampleVelocity(self, position_m: FloatArray) -> FloatArray:
    """Return the velocity contribution at ``position_m`` in m/s."""
    ...
####


@dataclass(frozen=True)
class UniformVelocityField:
  """Constant velocity contribution throughout the study domain."""

  velocity_mps: FloatArray

  def __post_init__(self) -> None:
    object.__setattr__(self, 'velocity_mps', _asReadOnlyVector3('velocity_mps', self.velocity_mps))
  ####

  def sampleVelocity(self, position_m: FloatArray) -> FloatArray:
    _asReadOnlyVector3('position_m', position_m)
    return self.velocity_mps
  ####
####


@dataclass(frozen=True)
class CompositeVelocityField:
  """Vector sum of independent ambient-velocity contributions."""

  fields: tuple[AmbientVelocityField, ...]

  def __post_init__(self) -> None:
    object.__setattr__(self, 'fields', tuple(self.fields))
  ####

  def sampleVelocity(self, position_m: FloatArray) -> FloatArray:
    position = _asReadOnlyVector3('position_m', position_m)
    velocity = np.zeros(3, dtype=float)
    for field in self.fields:
      velocity += field.sampleVelocity(position)
    ####
    return _asReadOnlyVector3('velocity_mps', velocity)
  ####
####


@dataclass(frozen=True)
class VelocityAugmentedAmbientField:
  """Add a velocity field while preserving background thermodynamics."""

  background_field: AmbientStateField
  velocity_field: AmbientVelocityField

  def sample(self, position_m: FloatArray) -> AmbientState:
    position = _asReadOnlyVector3('position_m', position_m)
    background = self.background_field.sample(position)
    velocity = background.velocity_mps + self.velocity_field.sampleVelocity(position)
    return AmbientState(
        velocity_mps=velocity,
        pressure_Pa=background.pressure_Pa,
        temperature_K=background.temperature_K,
        density_kgpm3=background.density_kgpm3,
        specific_heat_JpkgK=background.specific_heat_JpkgK,
        gas_constant_JpkgK=background.gas_constant_JpkgK,
    )
  ####
####


@dataclass(frozen=True)
class ActuatorDiskWakeField:
  """Steady hover/axial-flight actuator-disk wake approximation.

  ``wake_axis`` points downstream into the rotor wake. The field returns the
  rotor-induced velocity contribution and is zero upstream of the disk and
  outside the compact wake boundary. Axial velocity is normalized to preserve
  the prescribed disk-average mass flux. Optional swirl is normalized so its
  angular-momentum flux equals ``torque_Nm`` at every downstream station.
  """

  rotor_center_m: FloatArray
  wake_axis: FloatArray
  rotor_radius_m: float
  thrust_N: float
  ambient_density_kgpm3: float
  torque_Nm: float = 0.
  wake_development_length_m: float | None = None
  radial_profile_exponent: float = 1.
  swirl_taper_exponent: float = 1.

  def __post_init__(self) -> None:
    rotor_center = _asReadOnlyVector3('rotor_center_m', self.rotor_center_m)
    wake_axis = _unitVector('wake_axis', self.wake_axis)
    rotor_radius = _validatePositiveFinite('rotor_radius_m', self.rotor_radius_m)
    thrust = _validatePositiveFinite('thrust_N', self.thrust_N)
    ambient_density = _validatePositiveFinite('ambient_density_kgpm3', self.ambient_density_kgpm3)
    torque = _validateFinite('torque_Nm', self.torque_Nm)
    development_length = self.wake_development_length_m
    if development_length is None:
      development_length = rotor_radius
    ####
    development_length = _validatePositiveFinite('wake_development_length_m', development_length)
    radial_exponent = _validateNonnegativeFinite('radial_profile_exponent', self.radial_profile_exponent)
    swirl_exponent = _validateNonnegativeFinite('swirl_taper_exponent', self.swirl_taper_exponent)
    object.__setattr__(self, 'rotor_center_m', rotor_center)
    object.__setattr__(self, 'wake_axis', wake_axis)
    object.__setattr__(self, 'rotor_radius_m', rotor_radius)
    object.__setattr__(self, 'thrust_N', thrust)
    object.__setattr__(self, 'ambient_density_kgpm3', ambient_density)
    object.__setattr__(self, 'torque_Nm', torque)
    object.__setattr__(self, 'wake_development_length_m', development_length)
    object.__setattr__(self, 'radial_profile_exponent', radial_exponent)
    object.__setattr__(self, 'swirl_taper_exponent', swirl_exponent)
  ####

  @property
  def rotor_area_m2(self) -> float:
    return pi * self.rotor_radius_m ** 2
  ####

  @property
  def induced_velocity_at_disk_mps(self) -> float:
    return sqrt(self.thrust_N / (2. * self.ambient_density_kgpm3 * self.rotor_area_m2))
  ####

  @property
  def ideal_far_wake_velocity_mps(self) -> float:
    return 2. * self.induced_velocity_at_disk_mps
  ####

  def calculateMeanAxialVelocityMps(self, downstream_distance_m: float) -> float:
    downstream_distance = _validateNonnegativeFinite('downstream_distance_m', downstream_distance_m)
    development_length = self.wake_development_length_m
    if development_length is None:
      raise RuntimeError('Wake development length was not initialized.')
    ####
    return self.induced_velocity_at_disk_mps * (2. - exp(-downstream_distance / development_length))
  ####

  def calculateWakeRadiusM(self, downstream_distance_m: float) -> float:
    mean_velocity = self.calculateMeanAxialVelocityMps(downstream_distance_m)
    return self.rotor_radius_m * sqrt(self.induced_velocity_at_disk_mps / mean_velocity)
  ####

  def _calculateAxialProfileFactor(self, normalized_radius: float) -> float:
    if normalized_radius < 0. or normalized_radius >= 1.:
      return 0.
    ####
    exponent = self.radial_profile_exponent
    return (exponent + 1.) * (1. - normalized_radius ** 2) ** exponent
  ####

  def _calculateSwirlAngularVelocityRadps(
      self,
      *,
      mean_axial_velocity_mps: float,
      wake_radius_m: float,
  ) -> float:
    if self.torque_Nm == 0.:
      return 0.
    ####
    axial_exponent = self.radial_profile_exponent
    swirl_exponent = self.swirl_taper_exponent
    normalization = (
        (axial_exponent + swirl_exponent + 1.)
        * (axial_exponent + swirl_exponent + 2.)
        / (axial_exponent + 1.)
    )
    return (
        self.torque_Nm * normalization
        / (
            pi
            * self.ambient_density_kgpm3
            * mean_axial_velocity_mps
            * wake_radius_m ** 4
        )
    )
  ####

  def sampleVelocity(self, position_m: FloatArray) -> FloatArray:
    position = _asReadOnlyVector3('position_m', position_m)
    displacement = position - self.rotor_center_m
    downstream_distance = float(displacement @ self.wake_axis)
    if downstream_distance < 0.:
      return _asReadOnlyVector3('velocity_mps', np.zeros(3))
    ####
    radial_vector = displacement - downstream_distance * self.wake_axis
    radial_distance = float(np.linalg.norm(radial_vector))
    mean_axial_velocity = self.calculateMeanAxialVelocityMps(downstream_distance)
    wake_radius = self.calculateWakeRadiusM(downstream_distance)
    normalized_radius = radial_distance / wake_radius
    axial_profile = self._calculateAxialProfileFactor(normalized_radius)
    if axial_profile == 0.:
      return _asReadOnlyVector3('velocity_mps', np.zeros(3))
    ####
    velocity = mean_axial_velocity * axial_profile * self.wake_axis
    if self.torque_Nm != 0. and radial_distance > 0.:
      radial_axis = radial_vector / radial_distance
      azimuthal_axis = np.cross(self.wake_axis, radial_axis)
      swirl_taper = (1. - normalized_radius ** 2) ** self.swirl_taper_exponent
      angular_velocity = self._calculateSwirlAngularVelocityRadps(
          mean_axial_velocity_mps=mean_axial_velocity,
          wake_radius_m=wake_radius,
      )
      velocity = velocity + angular_velocity * radial_distance * swirl_taper * azimuthal_axis
    ####
    return _asReadOnlyVector3('velocity_mps', velocity)
  ####
####


__all__ = (
    'ActuatorDiskWakeField',
    'AmbientVelocityField',
    'CompositeVelocityField',
    'UniformVelocityField',
    'VelocityAugmentedAmbientField',
)
