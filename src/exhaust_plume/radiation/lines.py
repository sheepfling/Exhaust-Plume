"""Explicit LTE line-source radiation primitives.

This module supplies a narrow physical radiation seam for the Signature
product.  A caller provides line-integrated optical depths and broadening
parameters; the source function is the LTE Planck function and the line
shape is a normalized wavelength-domain Voigt profile.  The result is
therefore spectral-engineering evidence, not an inferred chemistry or a
validated molecular-radiation model.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, pi, sqrt
from typing import Any, Sequence, cast

import numpy as np
from scipy.special import wofz

from exhaust_plume.models.gas import FrozenMixtureState
from exhaust_plume.radiation.planck import planck_spectral_radiance_W_m2_sr_m

__all__ = (
  'BOLTZMANN_J_K',
  'SPEED_OF_LIGHT_M_S',
  'SpectralLine',
  'LineRadiationProfile',
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
    object.__setattr__(self, 'center_wavelength_m', center)
    object.__setattr__(self, 'integrated_optical_depth_m', integrated)
    object.__setattr__(self, 'doppler_sigma_m', sigma)
    object.__setattr__(self, 'lorentz_half_width_m', lorentz)
    object.__setattr__(self, 'label', label)
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
    return {
      'profile_id': self.profile_id,
      'wavelengths_m': self.wavelengths_m,
      'line_count': len(self.lines),
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
        'spectral-engineering-with-explicit-line-optical-depths; '
        'CHEM-0-source-state-bound-but-no-population-closure-or-external-validation'
      ),
    }
  ####
####
