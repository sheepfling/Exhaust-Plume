"""State, ambient-field, and thermodynamic types for curved plumes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np
from numpy.typing import ArrayLike

from exhaust_plume.models.plume._curved_plume_common import (
    FloatArray,
    _asReadOnlyVector3,
    _validateFinite,
    _validateNonnegativeFinite,
    _validatePositiveFinite,
)


@dataclass(frozen=True)
class AmbientState:
  """Local pressure-matched ambient state sampled by the plume solver."""

  velocity_mps: FloatArray
  pressure_Pa: float
  temperature_K: float
  density_kgpm3: float
  specific_heat_JpkgK: float = 1004.5
  gas_constant_JpkgK: float = 287.05

  def __post_init__(self) -> None:
    object.__setattr__(self, 'velocity_mps', _asReadOnlyVector3('velocity_mps', self.velocity_mps))
    object.__setattr__(self, 'pressure_Pa', _validatePositiveFinite('pressure_Pa', self.pressure_Pa))
    object.__setattr__(self, 'temperature_K', _validatePositiveFinite('temperature_K', self.temperature_K))
    object.__setattr__(self, 'density_kgpm3', _validatePositiveFinite('density_kgpm3', self.density_kgpm3))
    object.__setattr__(self, 'specific_heat_JpkgK', _validatePositiveFinite('specific_heat_JpkgK', self.specific_heat_JpkgK))
    object.__setattr__(self, 'gas_constant_JpkgK', _validatePositiveFinite('gas_constant_JpkgK', self.gas_constant_JpkgK))
  ####

  @classmethod
  def fromIdealGas(
      cls,
      *,
      velocity_mps: ArrayLike,
      pressure_Pa: float,
      temperature_K: float,
      specific_heat_JpkgK: float = 1004.5,
      gas_constant_JpkgK: float = 287.05,
  ) -> AmbientState:
    pressure = _validatePositiveFinite('pressure_Pa', pressure_Pa)
    temperature = _validatePositiveFinite('temperature_K', temperature_K)
    gas_constant = _validatePositiveFinite('gas_constant_JpkgK', gas_constant_JpkgK)
    return cls(
        velocity_mps=_asReadOnlyVector3('velocity_mps', velocity_mps),
        pressure_Pa=pressure,
        temperature_K=temperature,
        density_kgpm3=pressure / (gas_constant * temperature),
        specific_heat_JpkgK=specific_heat_JpkgK,
        gas_constant_JpkgK=gas_constant,
    )
  ####
####


class AmbientStateField(Protocol):
  """Spatial ambient-state provider."""

  def sample(self, position_m: FloatArray) -> AmbientState:
    """Return the local ambient state at ``position_m``."""
    ...
####


def _validateAmbientCaloricProperties(
    *,
    ambient: AmbientState,
    reference: AmbientState,
) -> None:
  """Reject spatial caloric changes that the current conserved state cannot represent.

  The integral state conserves total mass, momentum, energy, and exhaust mass,
  but it does not yet conserve the caloric composition of entrained ambient
  parcels. Applying a later ambient ``specific_heat_JpkgK`` or
  ``gas_constant_JpkgK`` to all accumulated ambient mass would therefore alter
  previously entrained material retroactively. Until those composition moments
  are added to the conserved state, require these ambient properties to remain
  constant along a trajectory.
  """
  differing_properties: list[str] = []
  if not np.isclose(
      ambient.specific_heat_JpkgK,
      reference.specific_heat_JpkgK,
      rtol=1.e-12,
      atol=1.e-12,
  ):
    differing_properties.append('specific_heat_JpkgK')
  ####
  if not np.isclose(
      ambient.gas_constant_JpkgK,
      reference.gas_constant_JpkgK,
      rtol=1.e-12,
      atol=1.e-12,
  ):
    differing_properties.append('gas_constant_JpkgK')
  ####
  if differing_properties:
    properties = ', '.join(differing_properties)
    raise ValueError(
        'Spatial variation of ambient caloric properties is unsupported by '
        'the current curved-plume conserved state. The following properties '
        f'must remain constant: {properties}. '
        'Use a caloric-composition-conserving thermodynamics closure before '
        'supplying a spatially varying field.'
    )
  ####
####


@dataclass(frozen=True)
class UniformAmbientField:
  """Ambient field whose state is constant throughout the study domain."""

  state: AmbientState

  def sample(self, position_m: FloatArray) -> AmbientState:
    _asReadOnlyVector3('position_m', position_m)
    return self.state
  ####
####


@dataclass(frozen=True)
class CurvedPlumeSource:
  """Pressure-matched source state for the integral curved-plume model."""

  position_m: FloatArray
  velocity_mps: FloatArray
  mass_flow_kgps: float
  temperature_K: float
  static_pressure_Pa: float
  specific_heat_JpkgK: float = 1150.
  gas_constant_JpkgK: float = 287.05
  exhaust_mass_fraction: float = 1.

  def __post_init__(self) -> None:
    position = _asReadOnlyVector3('position_m', self.position_m)
    velocity = _asReadOnlyVector3('velocity_mps', self.velocity_mps)
    if float(np.linalg.norm(velocity)) <= 0.:
      raise ValueError('Expected `velocity_mps` to be non-zero.')
    ####
    exhaust_mass_fraction = _validateFinite('exhaust_mass_fraction', self.exhaust_mass_fraction)
    if not 0. <= exhaust_mass_fraction <= 1.:
      raise ValueError(f'Expected `exhaust_mass_fraction` in [0, 1]. Got:{self.exhaust_mass_fraction}')
    ####
    object.__setattr__(self, 'position_m', position)
    object.__setattr__(self, 'velocity_mps', velocity)
    object.__setattr__(self, 'mass_flow_kgps', _validatePositiveFinite('mass_flow_kgps', self.mass_flow_kgps))
    object.__setattr__(self, 'temperature_K', _validatePositiveFinite('temperature_K', self.temperature_K))
    object.__setattr__(self, 'static_pressure_Pa', _validatePositiveFinite('static_pressure_Pa', self.static_pressure_Pa))
    object.__setattr__(self, 'specific_heat_JpkgK', _validatePositiveFinite('specific_heat_JpkgK', self.specific_heat_JpkgK))
    object.__setattr__(self, 'gas_constant_JpkgK', _validatePositiveFinite('gas_constant_JpkgK', self.gas_constant_JpkgK))
    object.__setattr__(self, 'exhaust_mass_fraction', exhaust_mass_fraction)
  ####

  @property
  def speed_mps(self) -> float:
    return float(np.linalg.norm(self.velocity_mps))
  ####

  @property
  def exhaust_mass_flow_kgps(self) -> float:
    return self.mass_flow_kgps * self.exhaust_mass_fraction
  ####
####


@dataclass(frozen=True)
class MixtureState:
  """Thermodynamic state reconstructed from the conserved plume variables."""

  temperature_K: float
  density_kgpm3: float
  specific_heat_JpkgK: float
  gas_constant_JpkgK: float

  def __post_init__(self) -> None:
    object.__setattr__(self, 'temperature_K', _validatePositiveFinite('temperature_K', self.temperature_K))
    object.__setattr__(self, 'density_kgpm3', _validatePositiveFinite('density_kgpm3', self.density_kgpm3))
    object.__setattr__(self, 'specific_heat_JpkgK', _validatePositiveFinite('specific_heat_JpkgK', self.specific_heat_JpkgK))
    object.__setattr__(self, 'gas_constant_JpkgK', _validatePositiveFinite('gas_constant_JpkgK', self.gas_constant_JpkgK))
  ####
####


class MixtureThermodynamics(Protocol):
  """Closure used to reconstruct plume temperature and density."""

  def reconstruct(
      self,
      *,
      source: CurvedPlumeSource,
      ambient: AmbientState,
      mass_flow_kgps: float,
      velocity_mps: FloatArray,
      total_energy_flow_W: float,
  ) -> MixtureState:
    """Reconstruct the local thermodynamic state."""
    ...
####


def _calculateMixedCaloricProperties(
    *,
    source: CurvedPlumeSource,
    ambient: AmbientState,
    mass_flow_kgps: float,
) -> tuple[float, float]:
  source_fraction = source.mass_flow_kgps / mass_flow_kgps
  if not 0. < source_fraction <= 1. + 1.e-10:
    raise ValueError(f'Invalid source-origin mass fraction:{source_fraction}')
  ####
  source_fraction = min(source_fraction, 1.)
  ambient_fraction = 1. - source_fraction
  specific_heat = source_fraction * source.specific_heat_JpkgK + ambient_fraction * ambient.specific_heat_JpkgK
  gas_constant = source_fraction * source.gas_constant_JpkgK + ambient_fraction * ambient.gas_constant_JpkgK
  return specific_heat, gas_constant
####


@dataclass(frozen=True)
class IdealGasMixtureThermodynamics:
  """Two-stream calorically perfect, pressure-matched ideal-gas closure."""

  def reconstruct(
      self,
      *,
      source: CurvedPlumeSource,
      ambient: AmbientState,
      mass_flow_kgps: float,
      velocity_mps: FloatArray,
      total_energy_flow_W: float,
  ) -> MixtureState:
    mass_flow = _validatePositiveFinite('mass_flow_kgps', mass_flow_kgps)
    total_energy_flow = _validatePositiveFinite('total_energy_flow_W', total_energy_flow_W)
    velocity = _asReadOnlyVector3('velocity_mps', velocity_mps)
    specific_heat, gas_constant = _calculateMixedCaloricProperties(
        source=source,
        ambient=ambient,
        mass_flow_kgps=mass_flow,
    )
    specific_total_energy = total_energy_flow / mass_flow
    specific_kinetic_energy = .5 * float(velocity @ velocity)
    temperature = (specific_total_energy - specific_kinetic_energy) / specific_heat
    if temperature <= 0. or not np.isfinite(temperature):
      raise ValueError(f'Reconstructed a nonphysical plume temperature:{temperature}')
    ####
    density = ambient.pressure_Pa / (gas_constant * temperature)
    return MixtureState(
        temperature_K=temperature,
        density_kgpm3=density,
        specific_heat_JpkgK=specific_heat,
        gas_constant_JpkgK=gas_constant,
    )
  ####
####


@dataclass(frozen=True)
class ConstantDensityMixtureThermodynamics:
  """Caloric mixing closure with a fixed density for analytical tests."""

  density_kgpm3: float

  def __post_init__(self) -> None:
    object.__setattr__(self, 'density_kgpm3', _validatePositiveFinite('density_kgpm3', self.density_kgpm3))
  ####

  def reconstruct(
      self,
      *,
      source: CurvedPlumeSource,
      ambient: AmbientState,
      mass_flow_kgps: float,
      velocity_mps: FloatArray,
      total_energy_flow_W: float,
  ) -> MixtureState:
    mass_flow = _validatePositiveFinite('mass_flow_kgps', mass_flow_kgps)
    total_energy_flow = _validatePositiveFinite('total_energy_flow_W', total_energy_flow_W)
    velocity = _asReadOnlyVector3('velocity_mps', velocity_mps)
    specific_heat, gas_constant = _calculateMixedCaloricProperties(
        source=source,
        ambient=ambient,
        mass_flow_kgps=mass_flow,
    )
    specific_total_energy = total_energy_flow / mass_flow
    specific_kinetic_energy = .5 * float(velocity @ velocity)
    temperature = (specific_total_energy - specific_kinetic_energy) / specific_heat
    if temperature <= 0. or not np.isfinite(temperature):
      raise ValueError(f'Reconstructed a nonphysical plume temperature:{temperature}')
    ####
    return MixtureState(
        temperature_K=temperature,
        density_kgpm3=self.density_kgpm3,
        specific_heat_JpkgK=specific_heat,
        gas_constant_JpkgK=gas_constant,
    )
  ####
####


@dataclass(frozen=True)
class CurvedPlumeStation:
  """Derived flow and geometry at one plume-centerline station."""

  arc_length_m: float
  position_m: FloatArray
  mass_flow_kgps: float
  momentum_flux_N: FloatArray
  momentum_derivative_Npm: FloatArray
  velocity_mps: FloatArray
  total_energy_flow_W: float
  exhaust_mass_flow_kgps: float
  exhaust_mass_fraction: float
  temperature_K: float
  pressure_Pa: float
  density_kgpm3: float
  specific_heat_JpkgK: float
  gas_constant_JpkgK: float
  area_m2: float
  radius_m: float
  ambient_velocity_mps: FloatArray
  ambient_temperature_K: float
  ambient_density_kgpm3: float
  relative_velocity_mps: FloatArray
  entrainment_kgpspm: float
  curvature_per_m: float
  slenderness_ratio: float

  def __post_init__(self) -> None:
    for name in (
        'position_m',
        'momentum_flux_N',
        'momentum_derivative_Npm',
        'velocity_mps',
        'ambient_velocity_mps',
        'relative_velocity_mps',
    ):
      object.__setattr__(self, name, _asReadOnlyVector3(name, getattr(self, name)))
    ####
    object.__setattr__(self, 'arc_length_m', _validateNonnegativeFinite('arc_length_m', self.arc_length_m))
    for name in (
        'mass_flow_kgps',
        'total_energy_flow_W',
        'temperature_K',
        'pressure_Pa',
        'density_kgpm3',
        'specific_heat_JpkgK',
        'gas_constant_JpkgK',
        'area_m2',
        'radius_m',
        'ambient_temperature_K',
        'ambient_density_kgpm3',
    ):
      object.__setattr__(self, name, _validatePositiveFinite(name, getattr(self, name)))
    ####
    for name in ('exhaust_mass_flow_kgps', 'entrainment_kgpspm', 'curvature_per_m', 'slenderness_ratio'):
      object.__setattr__(self, name, _validateNonnegativeFinite(name, getattr(self, name)))
    ####
    exhaust_mass_fraction = _validateFinite('exhaust_mass_fraction', self.exhaust_mass_fraction)
    if not 0. <= exhaust_mass_fraction <= 1. + 1.e-10:
      raise ValueError(f'Invalid exhaust mass fraction:{exhaust_mass_fraction}')
    ####
    object.__setattr__(self, 'exhaust_mass_fraction', min(exhaust_mass_fraction, 1.))
  ####

  @property
  def speed_mps(self) -> float:
    return float(np.linalg.norm(self.velocity_mps))
  ####

  @property
  def tangent(self) -> FloatArray:
    return _asReadOnlyVector3('tangent', self.velocity_mps / self.speed_mps)
  ####

  @property
  def relative_speed_mps(self) -> float:
    return float(np.linalg.norm(self.relative_velocity_mps))
  ####
####
