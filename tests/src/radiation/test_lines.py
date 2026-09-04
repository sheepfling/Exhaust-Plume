from __future__ import annotations

import numpy as np
import pytest

from exhaust_plume.radiation import (
  BOLTZMANN_J_K,
  SPEED_OF_LIGHT_M_S,
  LineRadiationProfile,
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
