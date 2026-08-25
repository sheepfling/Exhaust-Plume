from __future__ import annotations

import math

import pytest

from exhaust_plume.validation import (
  apply_atmospheric_path_transfer,
  integrate_bandpass_detector_rows,
  integrate_los_fov_spectrum,
)


def test_atmospheric_path_transfer_keeps_path_radiance_explicit() -> None:
  result = apply_atmospheric_path_transfer(
    (1.0e-6, 2.0e-6),
    ((10.0, 20.0),),
    ((0.5, 0.25),),
    path_radiance=((1.0, 2.0),),
  )

  assert result.values == ((6.0, 7.0),)
  assert result.validity_mask == ((True, True),)
  assert result.source_semantics == 'source-plus-path-radiance'
  assert result.operator_id == 'op.atmosphere.path-transfer'
####


def test_atmospheric_path_transfer_invalid_rows_are_zeroed() -> None:
  result = apply_atmospheric_path_transfer(
    (1.0e-6, 2.0e-6),
    ((10.0, 20.0),),
    ((0.5, 0.25),),
    validity_mask=((True, False),),
  )

  assert result.values == ((5.0, 0.0),)
  assert result.validity_mask == ((True, False),)
####


def test_los_fov_average_selects_only_declared_view_rays() -> None:
  result = integrate_los_fov_spectrum(
    (1.0e-6, 2.0e-6),
    (
      (1.0, 0.0, 0.0),
      (math.cos(0.2), math.sin(0.2), 0.0),
      (0.0, 1.0, 0.0),
    ),
    ((2.0, 4.0), (4.0, 8.0), (100.0, 100.0)),
    observer_direction=(1.0, 0.0, 0.0),
    solid_angle_weights_sr=(0.25, 0.25, 1.0),
    fov_half_angle_rad=0.3,
  )

  assert result.values == pytest.approx((3.0, 6.0))
  assert result.validity_mask == (True, True)
  assert result.selected_ray_indices == (0, 1)
  assert result.selected_solid_angle_sr == pytest.approx(0.5)
  assert result.output_units == 'W m^-2 sr^-1 m^-1'
####


def test_los_fov_invalid_samples_cannot_be_used_as_valid_evidence() -> None:
  kwargs = {
    'observer_direction': (1.0, 0.0, 0.0),
    'solid_angle_weights_sr': (1.0, 1.0),
    'fov_half_angle_rad': 0.3,
    'validity_mask': ((True, True), (False, False)),
  }
  with pytest.raises(ValueError, match='invalid ray samples'):
    integrate_los_fov_spectrum(
      (1.0e-6, 2.0e-6),
      ((1.0, 0.0, 0.0), (math.cos(0.2), math.sin(0.2), 0.0)),
      ((2.0, 4.0), (4.0, 8.0)),
      **kwargs,
    )
  ####
  partial = integrate_los_fov_spectrum(
    (1.0e-6, 2.0e-6),
    ((1.0, 0.0, 0.0), (math.cos(0.2), math.sin(0.2), 0.0)),
    ((2.0, 4.0), (4.0, 8.0)),
    allow_partial_results=True,
    **kwargs,
  )
  assert partial.values == (0.0, 0.0)
  assert partial.validity_mask == (False, False)
####


def test_bandpass_detector_integrates_and_can_normalize_response() -> None:
  kwargs = {
    'wavelengths_m': (1.0e-6, 2.0e-6, 3.0e-6),
    'values': ((1.0, 2.0, 3.0),),
    'response_wavelengths_m': (1.0e-6, 2.0e-6, 3.0e-6),
    'response': (0.0, 1.0, 0.0),
    'band_min_m': 1.5e-6,
    'band_max_m': 2.5e-6,
    'response_id': 'synthetic-bandpass-v1',
  }
  integrated = integrate_bandpass_detector_rows(**kwargs)
  normalized = integrate_bandpass_detector_rows(normalized_response=True, **kwargs)

  assert integrated.values == pytest.approx((1.5e-6,))
  assert normalized.values == pytest.approx((2.0,))
  assert integrated.validity_mask == (True,)
  assert normalized.response_integral_m == pytest.approx(0.75e-6)
  assert integrated.operator_id == 'op.sensor.bandpass-detector'
####


def test_bandpass_detector_rejects_response_extrapolation() -> None:
  with pytest.raises(ValueError, match='outside the detector response domain'):
    integrate_bandpass_detector_rows(
      (1.0e-6, 2.0e-6, 3.0e-6),
      ((1.0, 2.0, 3.0),),
      (1.5e-6, 2.5e-6),
      (1.0, 1.0),
      band_min_m=1.0e-6,
      band_max_m=3.0e-6,
    )
