from __future__ import annotations

import math

import pytest

from exhaust_plume.products import GrayRadiationProfile
from exhaust_plume.radiation import (
  PLANCK_C1_W_M2,
  PLANCK_C2_M_K,
  planck_spectral_radiance_W_m2_sr_m,
)


def test_planck_radiance_matches_the_declared_si_formula() -> None:
  wavelength = 5.0e-6
  temperature = 1_200.0
  expected = PLANCK_C1_W_M2 / (
    wavelength**5 * math.expm1(PLANCK_C2_M_K / (wavelength * temperature))
  )
  value = planck_spectral_radiance_W_m2_sr_m((wavelength,), temperature)[0]
  assert value == pytest.approx(expected, rel=1.0e-14)
####


def test_planck_gray_emissivity_scales_the_source_and_overflow_is_finite() -> None:
  full = planck_spectral_radiance_W_m2_sr_m((5.0e-6,), 1_200.0)[0]
  half = planck_spectral_radiance_W_m2_sr_m((5.0e-6,), 1_200.0, emissivity=0.5)[0]
  short_wave = planck_spectral_radiance_W_m2_sr_m((1.0e-12,), 200.0)[0]
  assert half == pytest.approx(0.5 * full)
  assert short_wave == 0.0
####


def test_planck_rejects_invalid_thermal_inputs() -> None:
  with pytest.raises(ValueError, match='wavelengths_m'):
    planck_spectral_radiance_W_m2_sr_m((0.0,), 1_000.0)
  ####
  with pytest.raises(ValueError, match='temperature_K'):
    planck_spectral_radiance_W_m2_sr_m((5.0e-6,), 0.0)
  ####
  with pytest.raises(ValueError, match='emissivity'):
    planck_spectral_radiance_W_m2_sr_m((5.0e-6,), 1_000.0, emissivity=1.1)
  ####
####


def test_gray_profile_can_be_constructed_from_explicit_thermal_source() -> None:
  profile = GrayRadiationProfile.from_blackbody(
    (2.0e-6, 5.0e-6),
    1_000.0,
    (0.5, 1.0),
    emissivity=0.7,
    profile_id='thermal-fixture',
  )
  assert profile.profile_id == 'thermal-fixture'
  assert profile.source_function_w_sr_m == pytest.approx(
    planck_spectral_radiance_W_m2_sr_m(profile.wavelengths_m, 1_000.0, emissivity=0.7),
  )
  assert profile.absorption_coefficient_per_m == (0.5, 1.0)
####
