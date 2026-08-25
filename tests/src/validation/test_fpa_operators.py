from __future__ import annotations

import pytest

from exhaust_plume.validation import (
  DetectorResponse,
  FpaPixelGeometry,
  integrate_ray_transfer_to_fpa,
)


def _geometry() -> FpaPixelGeometry:
  return FpaPixelGeometry(
    width_px=2,
    height_px=1,
    ray_pixel_indices_row_col=((0, 0), (0, 0), (0, 1)),
    ray_collection_weights_m2_sr=(0.25, 0.75, 1.0),
  )


def _detector() -> DetectorResponse:
  return DetectorResponse(
    wavelengths_m=(1.0e-6, 2.0e-6, 3.0e-6),
    quantum_efficiency=(1.0, 1.0, 1.0),
    optical_throughput=(1.0, 1.0, 1.0),
    dark_current_e_per_s=2.0,
    read_noise_std_e=3.0,
  )


def test_fpa_operator_integrates_rays_exposure_and_noise_policy() -> None:
  result = integrate_ray_transfer_to_fpa(
    (1.0e-6, 2.0e-6, 3.0e-6),
    ((2.0, 2.0, 2.0), (2.0, 2.0, 2.0), (1.0, 1.0, 1.0)),
    geometry=_geometry(),
    detector=_detector(),
    exposure_s=2.0,
  )

  expected_pixel_zero_signal = 2.0 * 2.0 * 4.0e-12 / (
    6.62607015e-34 * 299792458.0
  )
  expected_pixel_one_signal = 2.0 * 1.0 * 4.0e-12 / (
    6.62607015e-34 * 299792458.0
  )
  assert result.source_semantics == 'source-only'
  assert result.validity_mask == ((True, True),)
  assert result.expected_electrons[0][0] == pytest.approx(expected_pixel_zero_signal + 4.0)
  assert result.expected_electrons[0][1] == pytest.approx(expected_pixel_one_signal + 4.0)
  assert result.dark_electrons == ((4.0, 4.0),)
  assert result.noise_variance_e2[0][0] == pytest.approx(expected_pixel_zero_signal + 4.0 + 9.0)
  assert result.noise_variance_e2[0][1] == pytest.approx(expected_pixel_one_signal + 4.0 + 9.0)


def test_fpa_operator_composes_background_only_when_explicitly_requested() -> None:
  result = integrate_ray_transfer_to_fpa(
    (1.0e-6, 2.0e-6, 3.0e-6),
    ((1.0, 1.0, 1.0), (1.0, 1.0, 1.0), (1.0, 1.0, 1.0)),
    geometry=_geometry(),
    detector=DetectorResponse(
      wavelengths_m=(1.0e-6, 2.0e-6, 3.0e-6),
      quantum_efficiency=(1.0, 1.0, 1.0),
      optical_throughput=(1.0, 1.0, 1.0),
    ),
    exposure_s=1.0,
    background_transmittance=((0.5, 0.5, 0.5),) * 3,
    background_spectral_radiance=((2.0, 2.0, 2.0),) * 3,
  )
  source_only = integrate_ray_transfer_to_fpa(
    (1.0e-6, 2.0e-6, 3.0e-6),
    ((2.0, 2.0, 2.0),) * 3,
    geometry=_geometry(),
    detector=DetectorResponse(
      wavelengths_m=(1.0e-6, 2.0e-6, 3.0e-6),
      quantum_efficiency=(1.0, 1.0, 1.0),
      optical_throughput=(1.0, 1.0, 1.0),
    ),
    exposure_s=1.0,
  )
  assert result.source_semantics == 'source-plus-transmitted-background'
  assert result.expected_electrons[0][0] == pytest.approx(source_only.expected_electrons[0][0])
  assert result.expected_electrons[0][1] == pytest.approx(source_only.expected_electrons[0][1])


def test_fpa_operator_propagates_invalid_rays_and_rejects_partial_background() -> None:
  invalid = integrate_ray_transfer_to_fpa(
    (1.0e-6, 2.0e-6, 3.0e-6),
    ((1.0, 1.0, 1.0), (1.0, 1.0, 1.0), (1.0, 1.0, 1.0)),
    geometry=_geometry(),
    detector=_detector(),
    exposure_s=1.0,
    validity_mask=((True, True, True), (False, False, False), (True, True, True)),
  )
  assert invalid.validity_mask == ((False, True),)
  assert invalid.expected_electrons[0][0] == 0.0
  with pytest.raises(ValueError, match='must be supplied together'):
    integrate_ray_transfer_to_fpa(
      (1.0e-6, 2.0e-6, 3.0e-6),
      ((1.0, 1.0, 1.0),) * 3,
      geometry=_geometry(),
      detector=_detector(),
      exposure_s=1.0,
      background_transmittance=((1.0, 1.0, 1.0),) * 3,
    )


def test_fpa_operator_requires_detector_response_coverage() -> None:
  with pytest.raises(ValueError, match='does not cover'):
    integrate_ray_transfer_to_fpa(
      (1.0e-6, 2.0e-6, 3.0e-6),
      ((1.0, 1.0, 1.0),) * 3,
      geometry=_geometry(),
      detector=DetectorResponse(
        wavelengths_m=(1.5e-6, 2.5e-6),
        quantum_efficiency=(1.0, 1.0),
        optical_throughput=(1.0, 1.0),
      ),
      exposure_s=1.0,
    )


def test_fpa_operator_is_deterministic() -> None:
  kwargs = {
    'geometry': _geometry(),
    'detector': _detector(),
    'exposure_s': 1.0,
  }
  first = integrate_ray_transfer_to_fpa(
    (1.0e-6, 2.0e-6, 3.0e-6),
    ((1.0, 2.0, 3.0),) * 3,
    **kwargs,
  )
  second = integrate_ray_transfer_to_fpa(
    (1.0e-6, 2.0e-6, 3.0e-6),
    ((1.0, 2.0, 3.0),) * 3,
    **kwargs,
  )
  assert first == second
