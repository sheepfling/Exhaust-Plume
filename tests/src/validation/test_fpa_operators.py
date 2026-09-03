from __future__ import annotations

from math import nan

import pytest

from exhaust_plume.validation import (
  DetectorResponse,
  FpaCameraOptics,
  FpaDigitizedExpectation,
  FpaDigitizationPolicy,
  FpaPixelImage,
  FpaPixelGeometry,
  digitize_expected_electrons,
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


def test_fpa_operator_preserves_declared_camera_optics_identity() -> None:
  camera = FpaCameraOptics(
    camera_id='camera-synthetic-01',
    focal_length_m=0.05,
    pixel_pitch_m=(5.0e-6, 5.0e-6),
    principal_point_px=(0.5, 0.5),
    aperture_area_m2=1.0e-4,
  )
  geometry = FpaPixelGeometry(
    width_px=1,
    height_px=1,
    ray_pixel_indices_row_col=((0, 0),),
    ray_collection_weights_m2_sr=(1.0e-6,),
    camera_optics=camera,
  )
  result = integrate_ray_transfer_to_fpa(
    (1.0e-6, 2.0e-6, 3.0e-6),
    ((1.0, 1.0, 1.0),),
    geometry=geometry,
    detector=DetectorResponse(
      wavelengths_m=(1.0e-6, 2.0e-6, 3.0e-6),
      quantum_efficiency=(1.0, 1.0, 1.0),
      optical_throughput=(1.0, 1.0, 1.0),
    ),
    exposure_s=1.0,
  )
  assert result.camera_optics_id == 'camera-synthetic-01'
  assert result.camera_mapping_model_id == 'declared-ray-to-pixel-mapping-v1'


def test_fpa_pixel_geometry_rejects_coercible_shape_and_index_values() -> None:
  with pytest.raises(ValueError, match='positive integer'):
    FpaPixelGeometry(
      width_px=1.5,
      height_px=1,
      ray_pixel_indices_row_col=((0, 0),),
      ray_collection_weights_m2_sr=(1.0,),
    )
  with pytest.raises(ValueError, match='indices must contain integers'):
    FpaPixelGeometry(
      width_px=1,
      height_px=1,
      ray_pixel_indices_row_col=((0.5, 0),),
      ray_collection_weights_m2_sr=(1.0,),
    )
  with pytest.raises(ValueError, match='indices must contain integers'):
    FpaPixelGeometry(
      width_px=1,
      height_px=1,
      ray_pixel_indices_row_col=((True, 0),),
      ray_collection_weights_m2_sr=(1.0,),
    )


def test_fpa_digitization_is_deterministic_and_preserves_invalid_pixels() -> None:
  image = FpaPixelImage(
    width_px=4,
    height_px=1,
    wavelengths_m=(1.0e-6, 2.0e-6),
    exposure_s=1.0,
    expected_electrons=((0.5, 2.5, 300.0, 5.0),),
    dark_electrons=((0.0, 0.0, 0.0, 0.0),),
    noise_variance_e2=((0.5, 2.5, 300.0, 5.0),),
    validity_mask=((True, True, True, False),),
    source_semantics='source-only',
    detector_response_id='detector-test',
    camera_optics_id='camera-synthetic-01',
    camera_mapping_model_id='declared-ray-to-pixel-mapping-v1',
  )
  policy = FpaDigitizationPolicy(
    electrons_per_count=1.0,
    bit_depth=8,
    invalid_count=9,
  )
  first = digitize_expected_electrons(image, policy=policy)
  second = digitize_expected_electrons(image, policy=policy)
  assert first == second
  assert first.counts == ((0, 2, 255, 9),)
  assert first.saturated_mask == ((False, False, True, False),)
  assert first.validity_mask == image.validity_mask
  assert first.camera_optics_id == 'camera-synthetic-01'
  assert first.camera_mapping_model_id == 'declared-ray-to-pixel-mapping-v1'


def test_fpa_digitization_rejects_unsupported_adc_conventions() -> None:
  with pytest.raises(ValueError, match='nearest_even'):
    FpaDigitizationPolicy(electrons_per_count=1.0, rounding_mode='floor')
  with pytest.raises(ValueError, match='clip'):
    FpaDigitizationPolicy(electrons_per_count=1.0, saturation_mode='wrap')


def test_fpa_images_reject_malformed_direct_construction() -> None:
  common = {
    'width_px': 1,
    'height_px': 1,
    'wavelengths_m': (1.0e-6, 2.0e-6),
    'exposure_s': 1.0,
    'expected_electrons': ((0.0,),),
    'dark_electrons': ((0.0,),),
    'noise_variance_e2': ((0.0,),),
    'validity_mask': ((True,),),
    'source_semantics': 'source-only',
    'detector_response_id': 'detector-test',
  }
  with pytest.raises(ValueError, match='finite'):
    FpaPixelImage(**{**common, 'expected_electrons': ((nan,),)})
  with pytest.raises(ValueError, match='shape'):
    FpaPixelImage(**{**common, 'validity_mask': ((True, False),)})
  with pytest.raises(ValueError, match='positive integer'):
    FpaPixelImage(**{**common, 'width_px': 0})


def test_fpa_digitized_expectation_rejects_malformed_direct_construction() -> None:
  common = {
    'width_px': 1,
    'height_px': 1,
    'counts': ((0,),),
    'validity_mask': ((True,),),
    'saturated_mask': ((False,),),
    'source_operator_id': 'op.sensor.fpa-pixel-detector',
    'digitization_policy_id': 'policy-test',
  }
  with pytest.raises(ValueError, match='nonnegative integers'):
    FpaDigitizedExpectation(**{**common, 'counts': ((-1,),)})
  with pytest.raises(ValueError, match='boolean'):
    FpaDigitizedExpectation(**{**common, 'saturated_mask': ((0,),)})
  with pytest.raises(ValueError, match='operator_id'):
    FpaDigitizedExpectation(**{**common, 'operator_id': 'other'})
