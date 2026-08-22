"""Conservative integral model for pressure-matched curved exhaust plumes.

The solver advances mass flow, vector momentum flux, total-energy flux, and an
inert exhaust-origin tracer along plume-centerline arc length. Ambient-flow and
entrainment behavior are supplied through replaceable closures.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from math import exp, pi, sqrt
from numbers import Integral
from typing import Protocol, TypeAlias

import numpy as np
from numpy import ndarray
from numpy.typing import ArrayLike, NDArray
from scipy.integrate import solve_ivp

FloatArray: TypeAlias = NDArray[np.float64]

_POSITION = slice(0, 3)
_MASS_FLOW = 3
_MOMENTUM = slice(4, 7)
_TOTAL_ENERGY_FLOW = 7
_EXHAUST_MASS_FLOW = 8
_STATE_SIZE = 9


def _validateFinite(name: str, value: float) -> float:
  value_float = float(value)
  if not np.isfinite(value_float):
    raise ValueError(f'Expected `{name}` to be finite. Got:{value}')
  ####
  return value_float
####


def _validatePositiveFinite(name: str, value: float) -> float:
  value_float = _validateFinite(name, value)
  if value_float <= 0.:
    raise ValueError(f'Expected `{name}` to be greater than zero. Got:{value}')
  ####
  return value_float
####


def _validateNonnegativeFinite(name: str, value: float) -> float:
  value_float = _validateFinite(name, value)
  if value_float < 0.:
    raise ValueError(f'Expected `{name}` to be nonnegative. Got:{value}')
  ####
  return value_float
####


def _asReadOnlyVector3(name: str, value: ArrayLike) -> FloatArray:
  array = np.asarray(value, dtype=float)
  if array.shape != (3,):
    raise ValueError(f'Expected `{name}` to have shape (3,). Got:{array.shape}')
  ####
  if not np.isfinite(array).all():
    raise ValueError(f'Expected `{name}` to contain finite values. Got:{array}')
  ####
  out = np.array(array, dtype=float, copy=True)
  out.flags.writeable = False
  return out
####


def _asReadOnlyArray(name: str, value: ArrayLike) -> FloatArray:
  array = np.asarray(value, dtype=float)
  if not np.isfinite(array).all():
    raise ValueError(f'Expected `{name}` to contain finite values.')
  ####
  out = np.array(array, dtype=float, copy=True)
  out.flags.writeable = False
  return out
####


def _unitVector(name: str, value: ArrayLike) -> FloatArray:
  vector = _asReadOnlyVector3(name, value)
  magnitude = float(np.linalg.norm(vector))
  if magnitude <= 0.:
    raise ValueError(f'Expected `{name}` to be non-zero.')
  ####
  return _asReadOnlyVector3(name, vector / magnitude)
####


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
    for name in ('position_m', 'momentum_flux_N', 'velocity_mps', 'ambient_velocity_mps', 'relative_velocity_mps'):
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


def _reconstructStation(
    *,
    arc_length_m: float,
    state: FloatArray,
    source: CurvedPlumeSource,
    ambient_field: AmbientStateField,
    thermodynamics: MixtureThermodynamics,
    entrainment_kgpspm: float,
    minimum_speed_mps: float,
) -> CurvedPlumeStation:
  if state.shape != (_STATE_SIZE,):
    raise ValueError(f'Expected conserved state shape ({_STATE_SIZE},). Got:{state.shape}')
  ####
  position = _asReadOnlyVector3('position_m', state[_POSITION])
  mass_flow = _validatePositiveFinite('mass_flow_kgps', state[_MASS_FLOW])
  momentum = _asReadOnlyVector3('momentum_flux_N', state[_MOMENTUM])
  velocity = _asReadOnlyVector3('velocity_mps', momentum / mass_flow)
  speed = float(np.linalg.norm(velocity))
  if speed < minimum_speed_mps:
    raise ValueError(f'Plume speed fell below the supported minimum:{speed}')
  ####
  total_energy_flow = _validatePositiveFinite('total_energy_flow_W', state[_TOTAL_ENERGY_FLOW])
  exhaust_mass_flow = _validateNonnegativeFinite('exhaust_mass_flow_kgps', state[_EXHAUST_MASS_FLOW])
  exhaust_mass_fraction = exhaust_mass_flow / mass_flow
  ambient = ambient_field.sample(position)
  mixture = thermodynamics.reconstruct(
      source=source,
      ambient=ambient,
      mass_flow_kgps=mass_flow,
      velocity_mps=velocity,
      total_energy_flow_W=total_energy_flow,
  )
  area = mass_flow / (mixture.density_kgpm3 * speed)
  radius = sqrt(area / pi)
  relative_velocity = _asReadOnlyVector3('relative_velocity_mps', velocity - ambient.velocity_mps)
  tangent = velocity / speed
  normal_ambient_momentum = ambient.velocity_mps - float(ambient.velocity_mps @ tangent) * tangent
  curvature = entrainment_kgpspm * float(np.linalg.norm(normal_ambient_momentum)) / float(np.linalg.norm(momentum))
  return CurvedPlumeStation(
      arc_length_m=arc_length_m,
      position_m=position,
      mass_flow_kgps=mass_flow,
      momentum_flux_N=momentum,
      velocity_mps=velocity,
      total_energy_flow_W=total_energy_flow,
      exhaust_mass_flow_kgps=exhaust_mass_flow,
      exhaust_mass_fraction=exhaust_mass_fraction,
      temperature_K=mixture.temperature_K,
      pressure_Pa=ambient.pressure_Pa,
      density_kgpm3=mixture.density_kgpm3,
      specific_heat_JpkgK=mixture.specific_heat_JpkgK,
      gas_constant_JpkgK=mixture.gas_constant_JpkgK,
      area_m2=area,
      radius_m=radius,
      ambient_velocity_mps=ambient.velocity_mps,
      ambient_temperature_K=ambient.temperature_K,
      ambient_density_kgpm3=ambient.density_kgpm3,
      relative_velocity_mps=relative_velocity,
      entrainment_kgpspm=entrainment_kgpspm,
      curvature_per_m=curvature,
      slenderness_ratio=curvature * radius,
  )
####


def _calculateInitialConservedState(source: CurvedPlumeSource) -> FloatArray:
  state = np.empty((_STATE_SIZE,), dtype=float)
  state[_POSITION] = source.position_m
  state[_MASS_FLOW] = source.mass_flow_kgps
  state[_MOMENTUM] = source.mass_flow_kgps * source.velocity_mps
  state[_TOTAL_ENERGY_FLOW] = source.mass_flow_kgps * (
      source.specific_heat_JpkgK * source.temperature_K + .5 * float(source.velocity_mps @ source.velocity_mps)
  )
  state[_EXHAUST_MASS_FLOW] = source.exhaust_mass_flow_kgps
  return state
####


def _isEquilibrated(station: CurvedPlumeStation, options: CurvedPlumeOptions) -> bool:
  return (
      station.exhaust_mass_fraction <= options.equilibrium_exhaust_mass_fraction
      and abs(station.temperature_K - station.ambient_temperature_K) <= options.equilibrium_temperature_excess_K
      and station.relative_speed_mps <= options.equilibrium_relative_speed_mps
  )
####


def solveCurvedPlume(
    *,
    source: CurvedPlumeSource,
    ambient_field: AmbientStateField,
    entrainment_model: EntrainmentModel,
    options: CurvedPlumeOptions,
    thermodynamics: MixtureThermodynamics | None = None,
) -> CurvedPlumeResult:
  """Integrate the conservative curved-plume equations along arc length."""
  thermodynamic_model = thermodynamics if thermodynamics is not None else IdealGasMixtureThermodynamics()
  source_ambient = ambient_field.sample(source.position_m)
  pressure_relative_error = abs(source.static_pressure_Pa - source_ambient.pressure_Pa) / source_ambient.pressure_Pa
  if pressure_relative_error > options.pressure_match_relative_tolerance:
    raise ValueError(
        'The curved-plume source must be pressure matched to the local ambient. '
        f'Relative error:{pressure_relative_error}'
    )
  ####
  initial_state = _calculateInitialConservedState(source)

  def derivative(arc_length_m: float, state: ndarray) -> ndarray:
    provisional = _reconstructStation(
        arc_length_m=arc_length_m,
        state=np.asarray(state, dtype=float),
        source=source,
        ambient_field=ambient_field,
        thermodynamics=thermodynamic_model,
        entrainment_kgpspm=0.,
        minimum_speed_mps=options.minimum_speed_mps,
    )
    entrainment = entrainment_model.calculateMassEntrainmentPerLength(
        arc_length_m=arc_length_m,
        station=provisional,
        source=source,
    )
    entrainment = _validateNonnegativeFinite('entrainment_kgpspm', entrainment)
    ambient = ambient_field.sample(provisional.position_m)
    tangent = provisional.tangent
    derivative_state = np.zeros((_STATE_SIZE,), dtype=float)
    derivative_state[_POSITION] = tangent
    derivative_state[_MASS_FLOW] = entrainment
    derivative_state[_MOMENTUM] = entrainment * ambient.velocity_mps
    derivative_state[_TOTAL_ENERGY_FLOW] = entrainment * (
        ambient.specific_heat_JpkgK * ambient.temperature_K
        + .5 * float(ambient.velocity_mps @ ambient.velocity_mps)
    )
    derivative_state[_EXHAUST_MASS_FLOW] = 0.
    return derivative_state
  ####

  output_arc_lengths = np.linspace(0., options.max_arc_length_m, options.number_of_stations)
  solution = solve_ivp(
      derivative,
      (0., options.max_arc_length_m),
      initial_state,
      t_eval=output_arc_lengths,
      rtol=options.relative_tolerance,
      atol=options.absolute_tolerance,
      max_step=options.max_step_m,
  )
  stations: list[CurvedPlumeStation] = []
  for arc_length_m, state in zip(solution.t, solution.y.T):
    provisional = _reconstructStation(
        arc_length_m=float(arc_length_m),
        state=np.asarray(state, dtype=float),
        source=source,
        ambient_field=ambient_field,
        thermodynamics=thermodynamic_model,
        entrainment_kgpspm=0.,
        minimum_speed_mps=options.minimum_speed_mps,
    )
    entrainment = entrainment_model.calculateMassEntrainmentPerLength(
        arc_length_m=float(arc_length_m),
        station=provisional,
        source=source,
    )
    station = _reconstructStation(
        arc_length_m=float(arc_length_m),
        state=np.asarray(state, dtype=float),
        source=source,
        ambient_field=ambient_field,
        thermodynamics=thermodynamic_model,
        entrainment_kgpspm=_validateNonnegativeFinite('entrainment_kgpspm', entrainment),
        minimum_speed_mps=options.minimum_speed_mps,
    )
    stations.append(station)
  ####

  if not solution.success:
    termination = CurvedPlumeTermination.NUMERICAL_FAILURE
  else:
    termination = CurvedPlumeTermination.DOMAIN_LIMIT
    if options.enable_equilibrium_termination:
      for index, station in enumerate(stations[1:], start=1):
        if _isEquilibrated(station, options):
          stations = stations[:index + 1]
          termination = CurvedPlumeTermination.EQUILIBRIUM
          break
        ####
      ####
    ####
  ####
  return CurvedPlumeResult(
      stations=tuple(stations),
      termination=termination,
      solver_message=str(solution.message),
      function_evaluations=int(solution.nfev),
  )
####


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


__all__ = (
    'AmbientState',
    'AmbientStateField',
    'ConstantDensityFreeJetExactSolution',
    'ConstantDensityMixtureThermodynamics',
    'ConstantEntrainment',
    'CurvedPlumeOptions',
    'CurvedPlumeResult',
    'CurvedPlumeSource',
    'CurvedPlumeStation',
    'CurvedPlumeTermination',
    'DevelopingShearForcedEntrainment',
    'EntrainmentModel',
    'IdealGasMixtureThermodynamics',
    'MixtureState',
    'MixtureThermodynamics',
    'OrthogonalUniformCrossflowExactSolution',
    'UniformAmbientField',
    'calculateConstantDensityFreeJetExact',
    'calculateOrthogonalUniformCrossflowExact',
    'solveCurvedPlume',
)
