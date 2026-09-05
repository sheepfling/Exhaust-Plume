"""Explicit LTE line-source radiation primitives.

This module supplies a narrow physical radiation seam for the Signature
product.  A caller provides line-integrated optical depths and broadening
parameters, or explicitly binds a declared transition and LTE population
closure to a frozen mixture state.  The source function is the LTE Planck
function and the line shape is a normalized wavelength-domain Voigt profile.
The result is therefore spectral-engineering evidence, not an inferred
reaction chemistry or a validated molecular-radiation model.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import exp, isfinite, pi, sqrt
from typing import Any, Sequence, cast

import numpy as np
from scipy.special import wofz

from exhaust_plume.models.gas import FrozenMixtureState
from exhaust_plume.radiation.planck import planck_spectral_radiance_W_m2_sr_m

__all__ = (
  'BOLTZMANN_J_K',
  'LtePopulationClosure',
  'LteTransition',
  'SPEED_OF_LIGHT_M_S',
  'SpectralLine',
  'LineRadiationProfile',
  'SectionedLineRadiationProfile',
  'voigt_line_shape_per_m',
)


BOLTZMANN_J_K = 1.380649e-23
SPEED_OF_LIGHT_M_S = 299792458.0


def _finite_positive(name: str, value: object) -> float:
  numeric = float(cast(Any, value))
  if not isfinite(numeric) or numeric <= 0.0:
    raise ValueError(f'{name} must be finite and positive')
  ####
  return numeric
####


def _finite_nonnegative(name: str, value: object) -> float:
  numeric = float(cast(Any, value))
  if not isfinite(numeric) or numeric < 0.0:
    raise ValueError(f'{name} must be finite and nonnegative')
  ####
  return numeric
####


def _strict_wavelength_axis(values: Sequence[float]) -> tuple[float, ...]:
  axis = tuple(_finite_positive(f'wavelengths_m[{index}]', value) for index, value in enumerate(values))
  if len(axis) < 2:
    raise ValueError('wavelengths_m must contain at least two values')
  ####
  if any(second <= first for first, second in zip(axis, axis[1:])):
    raise ValueError('wavelengths_m must be strictly increasing')
  ####
  return axis
####


@dataclass(frozen=True, slots=True)
class LteTransition:
  """Caller-supplied transition data for a bounded LTE population closure.

  ``integrated_absorption_cross_section_m3`` is the wavelength-integrated
  absorption cross-section for one molecule in the lower state, expressed as
  ``m^3``.  It is deliberately an input: this contract does not look up
  spectroscopy data or infer line strengths from a species name.
  """

  species: str
  center_wavelength_m: float
  lower_state_energy_J: float
  upper_state_energy_J: float
  lower_degeneracy: float
  upper_degeneracy: float
  integrated_absorption_cross_section_m3: float
  molecular_mass_kg: float
  label: str = 'lte-transition'

  def __post_init__(self) -> None:
    species = str(self.species)
    if not species:
      raise ValueError('species must not be empty')
    ####
    center = _finite_positive('center_wavelength_m', self.center_wavelength_m)
    lower_energy = _finite_nonnegative('lower_state_energy_J', self.lower_state_energy_J)
    upper_energy = _finite_positive('upper_state_energy_J', self.upper_state_energy_J)
    if upper_energy <= lower_energy:
      raise ValueError('upper_state_energy_J must exceed lower_state_energy_J')
    ####
    lower_degeneracy = _finite_positive('lower_degeneracy', self.lower_degeneracy)
    upper_degeneracy = _finite_positive('upper_degeneracy', self.upper_degeneracy)
    cross_section = _finite_positive(
      'integrated_absorption_cross_section_m3',
      self.integrated_absorption_cross_section_m3,
    )
    molecular_mass = _finite_positive('molecular_mass_kg', self.molecular_mass_kg)
    label = str(self.label)
    if not label:
      raise ValueError('label must not be empty')
    ####
    object.__setattr__(self, 'species', species)
    object.__setattr__(self, 'center_wavelength_m', center)
    object.__setattr__(self, 'lower_state_energy_J', lower_energy)
    object.__setattr__(self, 'upper_state_energy_J', upper_energy)
    object.__setattr__(self, 'lower_degeneracy', lower_degeneracy)
    object.__setattr__(self, 'upper_degeneracy', upper_degeneracy)
    object.__setattr__(self, 'integrated_absorption_cross_section_m3', cross_section)
    object.__setattr__(self, 'molecular_mass_kg', molecular_mass)
    object.__setattr__(self, 'label', label)
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'species': self.species,
      'label': self.label,
      'center_wavelength_m': self.center_wavelength_m,
      'lower_state_energy_J': self.lower_state_energy_J,
      'upper_state_energy_J': self.upper_state_energy_J,
      'lower_degeneracy': self.lower_degeneracy,
      'upper_degeneracy': self.upper_degeneracy,
      'integrated_absorption_cross_section_m3': self.integrated_absorption_cross_section_m3,
      'molecular_mass_kg': self.molecular_mass_kg,
    }
  ####
####


def _transition_species_mole_fraction(
  transition: LteTransition,
  mixture_state: FrozenMixtureState,
) -> float:
  """Return the unique frozen-mixture fraction used by one transition."""

  matching_species = tuple(
    item.mole_fraction
    for item in mixture_state.species_mole_fractions
    if item.species == transition.species
  )
  if len(matching_species) != 1:
    raise ValueError(
      f"transition species {transition.species!r} is not present exactly once in the mixture state"
    )
  ####
  return float(matching_species[0])
####


@dataclass(frozen=True, slots=True)
class LtePopulationClosure:
  """One explicit LTE population calculation bound to a CHEM-0 state.

  The partition function and transition cross-section are caller-supplied at
  the state temperature.  The closure uses only the declared frozen-mixture
  mole fraction, ideal-gas number density, Boltzmann weights, and the
  stimulated-emission factor.  It does not model reactions, dissociation,
  non-LTE populations, or any unprovided spectroscopic data.
  """

  transition: LteTransition
  mixture_state: FrozenMixtureState
  partition_function: float
  path_length_m: float
  lower_population_fraction: float
  upper_population_fraction: float
  lower_number_density_per_m3: float
  upper_number_density_per_m3: float
  stimulated_emission_factor: float
  integrated_optical_depth_m: float

  def __post_init__(self) -> None:
    if not isinstance(self.transition, LteTransition):
      raise TypeError('transition must be an LteTransition')
    ####
    if not isinstance(self.mixture_state, FrozenMixtureState):
      raise TypeError('mixture_state must be a FrozenMixtureState')
    ####
    partition = _finite_positive('partition_function', self.partition_function)
    path_length = _finite_positive('path_length_m', self.path_length_m)
    lower_fraction = _finite_nonnegative(
      'lower_population_fraction',
      self.lower_population_fraction,
    )
    upper_fraction = _finite_nonnegative(
      'upper_population_fraction',
      self.upper_population_fraction,
    )
    lower_density = _finite_nonnegative(
      'lower_number_density_per_m3',
      self.lower_number_density_per_m3,
    )
    upper_density = _finite_nonnegative(
      'upper_number_density_per_m3',
      self.upper_number_density_per_m3,
    )
    stimulated = float(self.stimulated_emission_factor)
    if not isfinite(stimulated) or not 0.0 < stimulated <= 1.0:
      raise ValueError('stimulated_emission_factor must be finite and in (0, 1]')
    ####
    integrated = _finite_nonnegative(
      'integrated_optical_depth_m',
      self.integrated_optical_depth_m,
    )
    if lower_fraction > 1.0 or upper_fraction > 1.0:
      raise ValueError('population fractions must not exceed one')
    ####
    species_mole_fraction = _transition_species_mole_fraction(
      self.transition,
      self.mixture_state,
    )
    temperature = self.mixture_state.temperature_K
    lower_weight = self.transition.lower_degeneracy * exp(
      -self.transition.lower_state_energy_J / (BOLTZMANN_J_K * temperature)
    )
    upper_weight = self.transition.upper_degeneracy * exp(
      -self.transition.upper_state_energy_J / (BOLTZMANN_J_K * temperature)
    )
    weight_sum = lower_weight + upper_weight
    if partition + 1.0e-14 * max(partition, weight_sum, 1.0) < weight_sum:
      raise ValueError(
        'partition_function must include at least the declared lower and upper state weights'
      )
    ####
    expected_lower_fraction = lower_weight / partition
    expected_upper_fraction = upper_weight / partition
    total_number_density = self.mixture_state.pressure_Pa / (
      BOLTZMANN_J_K * temperature
    )
    species_number_density = total_number_density * species_mole_fraction
    expected_lower_density = species_number_density * expected_lower_fraction
    expected_upper_density = species_number_density * expected_upper_fraction
    expected_stimulated = 1.0 - exp(
      -(self.transition.upper_state_energy_J - self.transition.lower_state_energy_J)
      / (BOLTZMANN_J_K * temperature)
    )
    expected_integrated = (
      expected_lower_density
      * self.transition.integrated_absorption_cross_section_m3
      * expected_stimulated
      * path_length
    )
    derived_values = (
      ('lower_population_fraction', lower_fraction, expected_lower_fraction),
      ('upper_population_fraction', upper_fraction, expected_upper_fraction),
      ('lower_number_density_per_m3', lower_density, expected_lower_density),
      ('upper_number_density_per_m3', upper_density, expected_upper_density),
      ('stimulated_emission_factor', stimulated, expected_stimulated),
      ('integrated_optical_depth_m', integrated, expected_integrated),
    )
    for name, actual, expected in derived_values:
      tolerance = 1.0e-12 * max(abs(actual), abs(expected), 1.0)
      if abs(actual - expected) > tolerance:
        raise ValueError(f'{name} does not match the declared LTE source state')
      ####
    ####
    object.__setattr__(self, 'partition_function', partition)
    object.__setattr__(self, 'path_length_m', path_length)
    object.__setattr__(self, 'lower_population_fraction', lower_fraction)
    object.__setattr__(self, 'upper_population_fraction', upper_fraction)
    object.__setattr__(self, 'lower_number_density_per_m3', lower_density)
    object.__setattr__(self, 'upper_number_density_per_m3', upper_density)
    object.__setattr__(self, 'stimulated_emission_factor', stimulated)
    object.__setattr__(self, 'integrated_optical_depth_m', integrated)
  ####

  @classmethod
  def from_state(
    cls,
    transition: LteTransition,
    mixture_state: FrozenMixtureState,
    *,
    partition_function: float,
    path_length_m: float,
  ) -> 'LtePopulationClosure':
    """Derive lower/upper LTE populations from one explicit mixture state."""

    if not isinstance(transition, LteTransition):
      raise TypeError('transition must be an LteTransition')
    ####
    if not isinstance(mixture_state, FrozenMixtureState):
      raise TypeError('mixture_state must be a FrozenMixtureState')
    ####
    partition = _finite_positive('partition_function', partition_function)
    path_length = _finite_positive('path_length_m', path_length_m)
    species_mole_fraction = _transition_species_mole_fraction(transition, mixture_state)
    temperature = mixture_state.temperature_K
    lower_weight = transition.lower_degeneracy * exp(
      -transition.lower_state_energy_J / (BOLTZMANN_J_K * temperature)
    )
    upper_weight = transition.upper_degeneracy * exp(
      -transition.upper_state_energy_J / (BOLTZMANN_J_K * temperature)
    )
    weight_sum = lower_weight + upper_weight
    if partition + 1.0e-14 * max(partition, weight_sum, 1.0) < weight_sum:
      raise ValueError(
        'partition_function must include at least the declared lower and upper state weights'
      )
    ####
    lower_fraction = lower_weight / partition
    upper_fraction = upper_weight / partition
    total_number_density = mixture_state.pressure_Pa / (BOLTZMANN_J_K * temperature)
    species_number_density = total_number_density * species_mole_fraction
    lower_density = species_number_density * lower_fraction
    upper_density = species_number_density * upper_fraction
    stimulated = 1.0 - exp(
      -(transition.upper_state_energy_J - transition.lower_state_energy_J)
      / (BOLTZMANN_J_K * temperature)
    )
    integrated_optical_depth = (
      lower_density
      * transition.integrated_absorption_cross_section_m3
      * stimulated
      * path_length
    )
    return cls(
      transition=transition,
      mixture_state=mixture_state,
      partition_function=partition,
      path_length_m=path_length,
      lower_population_fraction=lower_fraction,
      upper_population_fraction=upper_fraction,
      lower_number_density_per_m3=lower_density,
      upper_number_density_per_m3=upper_density,
      stimulated_emission_factor=stimulated,
      integrated_optical_depth_m=integrated_optical_depth,
    )
  ####

  def to_spectral_line(
    self,
    *,
    lorentz_half_width_m: float = 0.0,
    label: str | None = None,
  ) -> 'SpectralLine':
    """Convert the closure into the existing Voigt-transfer line primitive."""

    return SpectralLine(
      center_wavelength_m=self.transition.center_wavelength_m,
      integrated_optical_depth_m=self.integrated_optical_depth_m,
      doppler_sigma_m=(
        self.transition.center_wavelength_m
        * sqrt(BOLTZMANN_J_K * self.mixture_state.temperature_K / self.transition.molecular_mass_kg)
        / SPEED_OF_LIGHT_M_S
      ),
      lorentz_half_width_m=lorentz_half_width_m,
      label=label or self.transition.label,
      population_closure=self,
    )
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'model': 'lte-boltzmann-population-closure-v1',
      'transition': self.transition.as_report(),
      'mixture_id': self.mixture_state.mixture_id,
      'temperature_K': self.mixture_state.temperature_K,
      'pressure_Pa': self.mixture_state.pressure_Pa,
      'species_mole_fraction': next(
        item.mole_fraction
        for item in self.mixture_state.species_mole_fractions
        if item.species == self.transition.species
      ),
      'partition_function': self.partition_function,
      'path_length_m': self.path_length_m,
      'lower_population_fraction': self.lower_population_fraction,
      'upper_population_fraction': self.upper_population_fraction,
      'lower_number_density_per_m3': self.lower_number_density_per_m3,
      'upper_number_density_per_m3': self.upper_number_density_per_m3,
      'stimulated_emission_factor': self.stimulated_emission_factor,
      'integrated_optical_depth_m': self.integrated_optical_depth_m,
      'claim_status': (
        'caller-bound-LTE-population-engineering; no reactions, non-LTE '
        'closure, inferred spectroscopy, or external validation'
      ),
    }
  ####
####


@dataclass(frozen=True, slots=True)
class SpectralLine:
  """One caller-supplied spectral line optical-depth primitive.

  ``integrated_optical_depth_m`` is the wavelength integral of optical depth
  along ``LineRadiationProfile.path_length_m`` and therefore has metre units.
  ``doppler_sigma_m`` is the Gaussian standard deviation and
  ``lorentz_half_width_m`` is the Lorentz half-width at half-maximum.  These
  conventions make the Voigt profile integrate to one over wavelength.
  """

  center_wavelength_m: float
  integrated_optical_depth_m: float
  doppler_sigma_m: float
  lorentz_half_width_m: float = 0.0
  label: str = 'unlabelled-line'
  population_closure: LtePopulationClosure | None = None

  def __post_init__(self) -> None:
    center = _finite_positive('center_wavelength_m', self.center_wavelength_m)
    integrated = float(self.integrated_optical_depth_m)
    if not isfinite(integrated) or integrated < 0.0:
      raise ValueError('integrated_optical_depth_m must be finite and nonnegative')
    ####
    sigma = _finite_positive('doppler_sigma_m', self.doppler_sigma_m)
    lorentz = float(self.lorentz_half_width_m)
    if not isfinite(lorentz) or lorentz < 0.0:
      raise ValueError('lorentz_half_width_m must be finite and nonnegative')
    ####
    label = str(self.label)
    if not label:
      raise ValueError('label must not be empty')
    ####
    population_closure = self.population_closure
    if population_closure is not None:
      if not isinstance(population_closure, LtePopulationClosure):
        raise TypeError('population_closure must be an LtePopulationClosure or None')
      ####
      if abs(center - population_closure.transition.center_wavelength_m) > 1.0e-14 * center:
        raise ValueError('line center must match population_closure.transition.center_wavelength_m')
      ####
      if abs(integrated - population_closure.integrated_optical_depth_m) > (
          1.0e-12 * max(abs(integrated), abs(population_closure.integrated_optical_depth_m), 1.0)
      ):
        raise ValueError('integrated optical depth must match population_closure')
      ####
    ####
    object.__setattr__(self, 'center_wavelength_m', center)
    object.__setattr__(self, 'integrated_optical_depth_m', integrated)
    object.__setattr__(self, 'doppler_sigma_m', sigma)
    object.__setattr__(self, 'lorentz_half_width_m', lorentz)
    object.__setattr__(self, 'label', label)
    object.__setattr__(self, 'population_closure', population_closure)
  ####

  @classmethod
  def from_thermal_width(
    cls,
    center_wavelength_m: float,
    integrated_optical_depth_m: float,
    temperature_K: float,
    molecular_mass_kg: float,
    *,
    lorentz_half_width_m: float = 0.0,
    label: str = 'thermal-line',
  ) -> 'SpectralLine':
    """Construct the Doppler width from an explicit LTE temperature/mass.

    The line optical depth and molecular mass remain caller-owned.  This
    helper only applies the one-dimensional thermal velocity width
    ``sqrt(k T / m)`` and does not calculate populations, line strengths, or
    chemical composition.
    """

    temperature = _finite_positive('temperature_K', temperature_K)
    mass = _finite_positive('molecular_mass_kg', molecular_mass_kg)
    center = _finite_positive('center_wavelength_m', center_wavelength_m)
    sigma = center * sqrt(BOLTZMANN_J_K * temperature / mass) / SPEED_OF_LIGHT_M_S
    return cls(
      center_wavelength_m=center,
      integrated_optical_depth_m=integrated_optical_depth_m,
      doppler_sigma_m=sigma,
      lorentz_half_width_m=lorentz_half_width_m,
      label=label,
    )
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'label': self.label,
      'center_wavelength_m': self.center_wavelength_m,
      'integrated_optical_depth_m': self.integrated_optical_depth_m,
      'doppler_sigma_m': self.doppler_sigma_m,
      'lorentz_half_width_m': self.lorentz_half_width_m,
      'population_closure': (
        None
        if self.population_closure is None
        else self.population_closure.as_report()
      ),
    }
  ####
####


def voigt_line_shape_per_m(
  wavelength_m: float,
  line: SpectralLine,
) -> float:
  """Return a normalized wavelength-domain Voigt line shape in ``m^-1``."""

  if not isinstance(line, SpectralLine):
    raise TypeError('line must be a SpectralLine')
  ####
  wavelength = _finite_positive('wavelength_m', wavelength_m)
  sigma = line.doppler_sigma_m
  lorentz = line.lorentz_half_width_m
  z = (
    (wavelength - line.center_wavelength_m) + 1j * lorentz
  ) / (sigma * sqrt(2.0))
  value = float(np.real(wofz(z))) / (sigma * sqrt(2.0 * pi))
  if not isfinite(value):
    raise FloatingPointError('Voigt line-shape evaluation was not finite')
  ####
  return max(0.0, value)
####


def _population_closure_count(lines: Sequence[SpectralLine]) -> int:
  return sum(line.population_closure is not None for line in lines)
####


@dataclass(frozen=True, slots=True)
class LineRadiationProfile:
  """A caller-bound LTE Planck source plus explicit line optical depths.

  The derived arrays have the same shape as the existing optical-transfer
  bridge: source function in ``W m^-2 sr^-1 m^-1`` and absorption coefficient
  in ``m^-1``.  The profile is homogeneous over its declared path length.
  """

  wavelengths_m: tuple[float, ...]
  lines: tuple[SpectralLine, ...]
  source_temperature_K: float
  path_length_m: float
  profile_id: str = 'explicit-lte-line-profile'
  source_mixture_state: FrozenMixtureState | None = None

  def __post_init__(self) -> None:
    wavelengths = _strict_wavelength_axis(self.wavelengths_m)
    lines = tuple(self.lines)
    if not lines:
      raise ValueError('lines must contain at least one SpectralLine')
    ####
    if any(not isinstance(line, SpectralLine) for line in lines):
      raise TypeError('lines must contain SpectralLine values')
    ####
    temperature = _finite_positive('source_temperature_K', self.source_temperature_K)
    path_length = _finite_positive('path_length_m', self.path_length_m)
    profile_id = str(self.profile_id)
    if not profile_id:
      raise ValueError('profile_id must not be empty')
    ####
    mixture_state = self.source_mixture_state
    for line in lines:
      closure = line.population_closure
      if closure is None:
        continue
      ####
      closure_scale = max(path_length, closure.path_length_m, 1.0)
      if abs(path_length - closure.path_length_m) > 1.0e-12 * closure_scale:
        raise ValueError('population-closure path length must match profile path_length_m')
      ####
      if abs(temperature - closure.mixture_state.temperature_K) > 1.0e-12 * max(temperature, 1.0):
        raise ValueError('population-closure state temperature must match source_temperature_K')
      ####
      if mixture_state is not None and mixture_state != closure.mixture_state:
        raise ValueError('population-closure mixture state must match source_mixture_state')
      ####
    ####
    if mixture_state is not None:
      if not isinstance(mixture_state, FrozenMixtureState):
        raise TypeError('source_mixture_state must be a FrozenMixtureState or None')
      ####
      temperature_scale = max(temperature, mixture_state.temperature_K, 1.0)
      if abs(temperature - mixture_state.temperature_K) > 1.0e-12 * temperature_scale:
        raise ValueError('source_temperature_K must match source_mixture_state.temperature_K')
      ####
    ####
    object.__setattr__(self, 'wavelengths_m', wavelengths)
    object.__setattr__(self, 'lines', lines)
    object.__setattr__(self, 'source_temperature_K', temperature)
    object.__setattr__(self, 'path_length_m', path_length)
    object.__setattr__(self, 'profile_id', profile_id)
    object.__setattr__(self, 'source_mixture_state', mixture_state)
  ####

  @classmethod
  def from_frozen_mixture_state(
    cls,
    wavelengths_m: Sequence[float],
    lines: Sequence[SpectralLine],
    mixture_state: FrozenMixtureState,
    path_length_m: float,
    *,
    profile_id: str = 'chem-0-lte-line-profile',
  ) -> 'LineRadiationProfile':
    """Bind an explicit CHEM-0 state to the LTE Planck source temperature.

    The mixture state supplies source-state provenance only.  This constructor
    does not infer line populations, optical depths, pressure broadening, or
    species-specific line widths.
    """

    if not isinstance(mixture_state, FrozenMixtureState):
      raise TypeError('mixture_state must be a FrozenMixtureState')
    ####
    return cls(
      wavelengths_m=tuple(wavelengths_m),
      lines=tuple(lines),
      source_temperature_K=mixture_state.temperature_K,
      path_length_m=path_length_m,
      profile_id=profile_id,
      source_mixture_state=mixture_state,
    )
  ####

  @property
  def source_function_w_sr_m(self) -> tuple[float, ...]:
    """Return the LTE Planck source function on the declared grid."""

    return planck_spectral_radiance_W_m2_sr_m(
      self.wavelengths_m,
      self.source_temperature_K,
    )
  ####

  @property
  def absorption_coefficient_per_m(self) -> tuple[float, ...]:
    """Return the line-summed absorption coefficient on the grid."""

    return tuple(
      sum(
        line.integrated_optical_depth_m
        * voigt_line_shape_per_m(wavelength, line)
        for line in self.lines
      ) / self.path_length_m
      for wavelength in self.wavelengths_m
    )
  ####

  def as_report(self) -> dict[str, object]:
    population_closure_count = _population_closure_count(self.lines)
    return {
      'profile_id': self.profile_id,
      'wavelengths_m': self.wavelengths_m,
      'line_count': len(self.lines),
      'population_closure_count': population_closure_count,
      'lines': tuple(line.as_report() for line in self.lines),
      'source_temperature_K': self.source_temperature_K,
      'path_length_m': self.path_length_m,
      'source_thermochemistry': (
        None
        if self.source_mixture_state is None
        else {
          'model': 'chem-0-explicit-frozen-mixture-v1',
          'mixture_id': self.source_mixture_state.mixture_id,
          'temperature_K': self.source_mixture_state.temperature_K,
          'species_mass_fractions': tuple(
            (item.species, item.mass_fraction)
            for item in self.source_mixture_state.species_mass_fractions
          ),
          'species_mole_fractions': tuple(
            (item.species, item.mole_fraction)
            for item in self.source_mixture_state.species_mole_fractions
          ),
        }
      ),
      'source_model': 'LTE-Planck-source',
      'line_shape_model': 'normalized-wavelength-domain-Voigt',
      'claim_status': (
        (
          'spectral-engineering-with-explicit-lte-population-closure; '
          'caller-bound-transition-data-and-no-reactions-or-external-validation'
        )
        if population_closure_count
        else (
          'spectral-engineering-with-explicit-line-optical-depths; '
          'CHEM-0-source-state-bound-but-no-population-closure-or-external-validation'
        )
      ),
    }
  ####
####


@dataclass(frozen=True, slots=True)
class SectionedLineRadiationProfile:
  """Explicit LTE line sources resolved independently by axial section.

  Each section retains its own caller-owned line optical depths, path length,
  and optional CHEM-0 source state.  The section arrays are consumed by the
  existing piecewise straight-support transfer operator; no line population,
  pressure-broadening, or interpolation between source states is inferred.
  """

  wavelengths_m: tuple[float, ...]
  profiles_by_section: tuple[LineRadiationProfile, ...]
  profile_id: str = 'explicit-sectioned-lte-line-profile'

  def __post_init__(self) -> None:
    wavelengths = _strict_wavelength_axis(self.wavelengths_m)
    profiles = tuple(self.profiles_by_section)
    if not profiles:
      raise ValueError('profiles_by_section must contain at least one LineRadiationProfile')
    ####
    if any(not isinstance(profile, LineRadiationProfile) for profile in profiles):
      raise TypeError('profiles_by_section must contain LineRadiationProfile values')
    ####
    if any(profile.wavelengths_m != wavelengths for profile in profiles):
      raise ValueError('every section profile must use the same wavelengths_m axis')
    ####
    profile_id = str(self.profile_id)
    if not profile_id:
      raise ValueError('profile_id must not be empty')
    ####
    object.__setattr__(self, 'wavelengths_m', wavelengths)
    object.__setattr__(self, 'profiles_by_section', profiles)
    object.__setattr__(self, 'profile_id', profile_id)
  ####

  @classmethod
  def from_frozen_mixture_states(
    cls,
    wavelengths_m: Sequence[float],
    lines_by_section: Sequence[Sequence[SpectralLine]],
    mixture_states: Sequence[FrozenMixtureState],
    path_lengths_m: Sequence[float],
    *,
    profile_id: str = 'chem-0-sectioned-lte-line-profile',
  ) -> 'SectionedLineRadiationProfile':
    """Build section sources from explicit CHEM-0 states and line inputs.

    This factory binds source temperature and composition provenance to each
    section only.  Every line list and optical-depth primitive remains
    caller-owned; missing population or species spectroscopy data is rejected
    by omission rather than synthesized here.
    """

    lines = tuple(tuple(section) for section in lines_by_section)
    states = tuple(mixture_states)
    path_lengths = tuple(float(value) for value in path_lengths_m)
    if not lines or len(lines) != len(states) or len(lines) != len(path_lengths):
      raise ValueError(
        'lines_by_section, mixture_states, and path_lengths_m must have equal nonzero lengths'
      )
    ####
    if any(not isinstance(state, FrozenMixtureState) for state in states):
      raise TypeError('mixture_states must contain FrozenMixtureState values')
    ####
    profiles = tuple(
      LineRadiationProfile.from_frozen_mixture_state(
        wavelengths_m=wavelengths_m,
        lines=section_lines,
        mixture_state=state,
        path_length_m=path_length,
        profile_id=f'{profile_id}:section-{index}',
      )
      for index, (section_lines, state, path_length) in enumerate(
        zip(lines, states, path_lengths, strict=True)
      )
    )
    return cls(
      wavelengths_m=tuple(wavelengths_m),
      profiles_by_section=profiles,
      profile_id=profile_id,
    )
  ####

  @property
  def source_function_w_sr_m_by_section(self) -> tuple[tuple[float, ...], ...]:
    """Return the explicit LTE Planck source spectrum for every section."""

    return tuple(profile.source_function_w_sr_m for profile in self.profiles_by_section)
  ####

  @property
  def absorption_coefficient_per_m_by_section(self) -> tuple[tuple[float, ...], ...]:
    """Return the explicit Voigt line opacity spectrum for every section."""

    return tuple(
      profile.absorption_coefficient_per_m
      for profile in self.profiles_by_section
    )
  ####

  @property
  def source_temperature_K_by_section(self) -> tuple[float, ...]:
    """Return the source temperatures without interpolating between sections."""

    return tuple(profile.source_temperature_K for profile in self.profiles_by_section)
  ####

  def as_report(self) -> dict[str, object]:
    population_closure_count = sum(
      _population_closure_count(profile.lines)
      for profile in self.profiles_by_section
    )
    return {
      'profile_id': self.profile_id,
      'wavelengths_m': self.wavelengths_m,
      'section_count': len(self.profiles_by_section),
      'population_closure_count': population_closure_count,
      'source_temperature_K_by_section': self.source_temperature_K_by_section,
      'profiles_by_section': tuple(
        profile.as_report() for profile in self.profiles_by_section
      ),
      'source_model': 'LTE-Planck-source-by-section',
      'line_shape_model': 'normalized-wavelength-domain-Voigt',
      'claim_status': (
        (
          'spectral-engineering-with-explicit-section-lte-population-closure; '
          'caller-bound-transition-data-and-no-reactions-or-external-validation'
        )
        if population_closure_count
        else (
          'spectral-engineering-with-explicit-section-line-optical-depths; '
          'no-population-closure-or-external-validation'
        )
      ),
    }
  ####
####
