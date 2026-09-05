from __future__ import annotations

import numpy as np
import pytest

from exhaust_plume.models.gas import FrozenMixtureGas, SpeciesDefinition, SpeciesMassFraction
from exhaust_plume.radiation import (
  BOLTZMANN_J_K,
  LtePopulationClosure,
  LteTransition,
  SPEED_OF_LIGHT_M_S,
  LineRadiationProfile,
  SectionedLineRadiationProfile,
  SpectralLine,
  planck_spectral_radiance_W_m2_sr_m,
  voigt_line_shape_per_m,
)


def test_thermal_line_width_uses_explicit_lte_temperature_and_mass() -> None:
  line = SpectralLine.from_thermal_width(
    center_wavelength_m=5.0e-6,
    integrated_optical_depth_m=2.0e-7,
    temperature_K=1_000.0,
    molecular_mass_kg=4.65e-26,
    label='test-line',
  )
  expected = 5.0e-6 * np.sqrt(BOLTZMANN_J_K * 1_000.0 / 4.65e-26) / SPEED_OF_LIGHT_M_S
  assert line.doppler_sigma_m == pytest.approx(expected, rel=1.0e-14)
  assert line.label == 'test-line'
####


def test_voigt_profile_is_nonnegative_and_normalized_over_a_resolved_grid() -> None:
  line = SpectralLine(
    center_wavelength_m=5.0e-6,
    integrated_optical_depth_m=2.0e-7,
    doppler_sigma_m=2.0e-8,
    lorentz_half_width_m=5.0e-9,
  )
  wavelengths = np.linspace(4.5e-6, 5.5e-6, 4_001)
  values = np.asarray(
    [voigt_line_shape_per_m(float(wavelength), line) for wavelength in wavelengths],
  )
  assert np.all(np.isfinite(values))
  assert np.all(values >= 0.0)
  assert np.trapezoid(values, wavelengths) == pytest.approx(1.0, rel=2.0e-2)
####


def test_lte_line_profile_derives_planck_source_and_line_opacity() -> None:
  line = SpectralLine(
    center_wavelength_m=2.0e-6,
    integrated_optical_depth_m=4.0e-7,
    doppler_sigma_m=5.0e-8,
    label='test-line',
  )
  profile = LineRadiationProfile(
    wavelengths_m=(1.0e-6, 2.0e-6, 3.0e-6),
    lines=(line,),
    source_temperature_K=1_200.0,
    path_length_m=2.0,
    profile_id='test-lte-lines',
  )
  assert profile.source_function_w_sr_m == pytest.approx(
    planck_spectral_radiance_W_m2_sr_m(profile.wavelengths_m, 1_200.0),
  )
  assert profile.absorption_coefficient_per_m[1] > profile.absorption_coefficient_per_m[0]
  assert profile.absorption_coefficient_per_m[1] > profile.absorption_coefficient_per_m[2]
  report = profile.as_report()
  assert report['source_model'] == 'LTE-Planck-source'
  assert report['line_shape_model'] == 'normalized-wavelength-domain-Voigt'
  assert report['claim_status'].startswith('spectral-engineering')
####


def test_lte_line_profile_can_bind_a_chem0_source_state_without_inferencing_lines() -> None:
  mixture = FrozenMixtureGas(
    mixture_id='test-chem0-source',
    species=(
      SpeciesDefinition(
        species='test-gas',
        molecular_weight_kg_per_mol=0.020,
        cp_JpkgK=1_000.0,
      ),
    ),
    species_mass_fractions=(SpeciesMassFraction(species='test-gas', mass_fraction=1.0),),
    valid_temperature_range_K=(300.0, 2_000.0),
  )
  state = mixture.state_at(120_000.0, 1_200.0)
  line = SpectralLine(
    center_wavelength_m=2.0e-6,
    integrated_optical_depth_m=4.0e-7,
    doppler_sigma_m=5.0e-8,
    label='chem0-bound-line',
  )

  profile = LineRadiationProfile.from_frozen_mixture_state(
    wavelengths_m=(1.0e-6, 2.0e-6, 3.0e-6),
    lines=(line,),
    mixture_state=state,
    path_length_m=2.0,
  )
  report = profile.as_report()

  assert profile.source_temperature_K == pytest.approx(state.temperature_K)
  assert profile.source_mixture_state == state
  assert report['source_thermochemistry']['model'] == 'chem-0-explicit-frozen-mixture-v1'  # type: ignore[index]
  assert report['source_thermochemistry']['mixture_id'] == 'test-chem0-source'  # type: ignore[index]
  assert 'no-population-closure' in report['claim_status']
  with pytest.raises(ValueError, match='must match'):
    LineRadiationProfile(
      wavelengths_m=(1.0e-6, 2.0e-6),
      lines=(line,),
      source_temperature_K=1_100.0,
      path_length_m=1.0,
      source_mixture_state=state,
    )
  ####
####


def test_lte_population_closure_derives_a_source_bound_line_without_inventing_spectroscopy() -> None:
  mixture = FrozenMixtureGas(
    mixture_id='test-lte-population-source',
    species=(
      SpeciesDefinition(
        species='test-gas',
        molecular_weight_kg_per_mol=0.020,
        cp_JpkgK=1_000.0,
      ),
    ),
    species_mass_fractions=(SpeciesMassFraction(species='test-gas', mass_fraction=1.0),),
    valid_temperature_range_K=(300.0, 2_000.0),
  )
  state = mixture.state_at(120_000.0, 1_200.0)
  transition = LteTransition(
    species='test-gas',
    center_wavelength_m=2.0e-6,
    lower_state_energy_J=0.0,
    upper_state_energy_J=1.0e-20,
    lower_degeneracy=1.0,
    upper_degeneracy=1.0,
    integrated_absorption_cross_section_m3=4.0e-28,
    molecular_mass_kg=3.32e-26,
    label='caller-supplied-transition',
  )
  partition_function = 4.0
  closure = LtePopulationClosure.from_state(
    transition,
    state,
    partition_function=partition_function,
    path_length_m=2.0,
  )
  line = closure.to_spectral_line(lorentz_half_width_m=2.0e-9)
  profile = LineRadiationProfile(
    wavelengths_m=(1.0e-6, 2.0e-6, 3.0e-6),
    lines=(line,),
    source_temperature_K=state.temperature_K,
    path_length_m=2.0,
    source_mixture_state=state,
  )

  assert line.population_closure == closure
  assert closure.lower_population_fraction > closure.upper_population_fraction
  assert closure.stimulated_emission_factor < 1.0
  assert closure.integrated_optical_depth_m > 0.0
  assert profile.as_report()['population_closure_count'] == 1
  assert profile.as_report()['claim_status'].startswith(
    'spectral-engineering-with-explicit-lte-population-closure'
  )
  assert line.as_report()['population_closure']['model'] == 'lte-boltzmann-population-closure-v1'  # type: ignore[index]
####


def test_lte_population_closure_rejects_missing_species_and_incomplete_partition_function() -> None:
  mixture = FrozenMixtureGas(
    mixture_id='test-lte-population-validation',
    species=(
      SpeciesDefinition(
        species='test-gas',
        molecular_weight_kg_per_mol=0.020,
        cp_JpkgK=1_000.0,
      ),
    ),
    species_mass_fractions=(SpeciesMassFraction(species='test-gas', mass_fraction=1.0),),
    valid_temperature_range_K=(300.0, 2_000.0),
  )
  state = mixture.state_at(120_000.0, 1_200.0)
  transition = LteTransition(
    species='missing-gas',
    center_wavelength_m=2.0e-6,
    lower_state_energy_J=0.0,
    upper_state_energy_J=1.0e-20,
    lower_degeneracy=1.0,
    upper_degeneracy=1.0,
    integrated_absorption_cross_section_m3=4.0e-28,
    molecular_mass_kg=3.32e-26,
  )
  with pytest.raises(ValueError, match='not present exactly once'):
    LtePopulationClosure.from_state(
      transition,
      state,
      partition_function=2.0,
      path_length_m=1.0,
    )
  ####
  present = LteTransition(
    species='test-gas',
    center_wavelength_m=2.0e-6,
    lower_state_energy_J=0.0,
    upper_state_energy_J=1.0e-20,
    lower_degeneracy=1.0,
    upper_degeneracy=2.0,
    integrated_absorption_cross_section_m3=4.0e-28,
    molecular_mass_kg=3.32e-26,
  )
  with pytest.raises(ValueError, match='must include at least'):
    LtePopulationClosure.from_state(
      present,
      state,
      partition_function=1.0,
      path_length_m=1.0,
    )
  ####
####


def test_sectioned_lte_line_profile_preserves_position_varying_sources() -> None:
  mixture = FrozenMixtureGas(
    mixture_id='test-chem0-sectioned-source',
    species=(
      SpeciesDefinition(
        species='test-gas',
        molecular_weight_kg_per_mol=0.020,
        cp_JpkgK=1_000.0,
      ),
    ),
    species_mass_fractions=(SpeciesMassFraction(species='test-gas', mass_fraction=1.0),),
    valid_temperature_range_K=(300.0, 2_000.0),
  )
  states = (
    mixture.state_at(120_000.0, 900.0),
    mixture.state_at(110_000.0, 1_200.0),
  )
  line = SpectralLine(
    center_wavelength_m=2.0e-6,
    integrated_optical_depth_m=4.0e-7,
    doppler_sigma_m=5.0e-8,
    label='sectioned-line',
  )

  profile = SectionedLineRadiationProfile.from_frozen_mixture_states(
    wavelengths_m=(1.0e-6, 2.0e-6, 3.0e-6),
    lines_by_section=((line,), (line,)),
    mixture_states=states,
    path_lengths_m=(1.0, 2.0),
  )

  assert profile.source_temperature_K_by_section == pytest.approx((900.0, 1_200.0))
  assert profile.source_function_w_sr_m_by_section[1][0] > profile.source_function_w_sr_m_by_section[0][0]
  assert profile.absorption_coefficient_per_m_by_section[0][1] == pytest.approx(
    2.0 * profile.absorption_coefficient_per_m_by_section[1][1],
  )
  report = profile.as_report()
  assert report['source_model'] == 'LTE-Planck-source-by-section'
  assert report['section_count'] == 2
  assert report['profiles_by_section'][0]['source_thermochemistry']['mixture_id'] == 'test-chem0-sectioned-source'  # type: ignore[index]
####


def test_line_profile_rejects_empty_or_invalid_lines() -> None:
  with pytest.raises(ValueError, match='at least one'):
    LineRadiationProfile(
      wavelengths_m=(1.0e-6, 2.0e-6),
      lines=(),
      source_temperature_K=1_000.0,
      path_length_m=1.0,
    )
  ####
  with pytest.raises(ValueError, match='doppler_sigma_m'):
    SpectralLine(
      center_wavelength_m=2.0e-6,
      integrated_optical_depth_m=1.0e-7,
      doppler_sigma_m=0.0,
    )
  ####
####
