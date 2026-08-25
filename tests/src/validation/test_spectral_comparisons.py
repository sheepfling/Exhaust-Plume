from __future__ import annotations

import pytest

from exhaust_plume.validation import (
  INTRINSIC_SPECTRAL_RADIANT_INTENSITY_UNITS,
  SENSOR_SPACE_SPECTRAL_RADIANCE_UNITS,
  SpectralCurve,
  SpectralMeasurementSpace,
  compare_declared_peak_normalized_spectral_shape,
  compare_peak_normalized_spectral_shape,
)


def test_full_domain_spectral_shape_comparison_computes_residuals() -> None:
  result = compare_peak_normalized_spectral_shape(
    (1.0, 2.0, 3.0),
    (1.0, 2.0, 1.0),
    (1.0, 1.5, 2.0, 3.0),
    (2.0, 3.0, 4.0, 2.0),
  )

  assert result.status == 'full-domain-computed'
  assert result.coverage_fraction == pytest.approx(1.0)
  assert result.overlap_sample_count == 4
  assert result.full_domain_relative_shape_rmse == pytest.approx(0.0)
  assert result.full_domain_peak_location_error_m == pytest.approx(0.0)


def test_partial_domain_comparison_reports_diagnostic_without_full_claim() -> None:
  result = compare_peak_normalized_spectral_shape(
    (1.0, 2.0, 3.0),
    (1.0, 2.0, 1.0),
    (2.0, 2.5, 3.0, 4.0),
    (2.0, 1.0, 0.5, 0.25),
  )

  assert result.status == 'partial-overlap-diagnostic'
  assert result.coverage_fraction == pytest.approx(1.0 / 2.0)
  assert result.overlap_sample_count == 3
  assert result.overlap_relative_shape_rmse is not None
  assert result.full_domain_relative_shape_rmse is None
  assert 'complete observed wavelength domain' in (result.reason or '')


def test_no_overlap_is_explicit_and_never_extrapolated() -> None:
  result = compare_peak_normalized_spectral_shape(
    (1.0, 2.0, 3.0),
    (1.0, 2.0, 1.0),
    (4.0, 5.0, 6.0),
    (1.0, 2.0, 1.0),
  )

  assert result.status == 'no-overlap'
  assert result.overlap_domain_m is None
  assert result.coverage_fraction == 0.0
  assert result.overlap_relative_shape_rmse is None


def test_spectral_shape_comparison_rejects_mismatched_or_invalid_inputs() -> None:
  with pytest.raises(ValueError, match='matching lengths'):
    compare_peak_normalized_spectral_shape((1.0, 2.0), (1.0,), (1.0, 2.0), (1.0, 2.0))
  with pytest.raises(ValueError, match='nonnegative'):
    compare_peak_normalized_spectral_shape((1.0, 2.0), (1.0, -1.0), (1.0, 2.0), (1.0, 2.0))


def test_declared_spectral_comparison_blocks_cross_space_residuals() -> None:
  model = SpectralCurve(
    wavelengths_m=(1.0e-6, 2.0e-6, 3.0e-6),
    values=(1.0, 2.0, 1.0),
    measurement_space=SpectralMeasurementSpace.INTRINSIC_RADIANT_INTENSITY,
    units=INTRINSIC_SPECTRAL_RADIANT_INTENSITY_UNITS,
    source_semantics='unresolved source table',
  )
  observed = SpectralCurve(
    wavelengths_m=(1.0e-6, 2.0e-6, 3.0e-6),
    values=(10.0, 20.0, 10.0),
    measurement_space=SpectralMeasurementSpace.SENSOR_SPACE_RADIANCE,
    units=SENSOR_SPACE_SPECTRAL_RADIANCE_UNITS,
    source_semantics='sensor-space observation',
  )

  result = compare_declared_peak_normalized_spectral_shape(model, observed)

  assert result.status == 'blocked-measurement-space-mismatch'
  assert result.shape_comparison is None
  assert result.model_space == 'intrinsic-radiant-intensity'
  assert result.observed_space == 'sensor-space-radiance'


def test_declared_spectral_comparison_runs_only_for_matching_space() -> None:
  model = SpectralCurve(
    wavelengths_m=(1.0e-6, 2.0e-6, 3.0e-6),
    values=(1.0, 2.0, 1.0),
    measurement_space=SpectralMeasurementSpace.SENSOR_SPACE_RADIANCE,
    units=SENSOR_SPACE_SPECTRAL_RADIANCE_UNITS,
  )
  observed = SpectralCurve(
    wavelengths_m=(1.0e-6, 2.0e-6, 3.0e-6),
    values=(10.0, 20.0, 10.0),
    measurement_space=SpectralMeasurementSpace.SENSOR_SPACE_RADIANCE,
    units=SENSOR_SPACE_SPECTRAL_RADIANCE_UNITS,
  )

  result = compare_declared_peak_normalized_spectral_shape(model, observed)

  assert result.status == 'full-domain-computed'
  assert result.shape_comparison is not None
  assert result.shape_comparison.full_domain_relative_shape_rmse == pytest.approx(0.0)


def test_spectral_curve_rejects_units_that_do_not_match_declared_space() -> None:
  with pytest.raises(ValueError, match='requires units'):
    SpectralCurve(
      wavelengths_m=(1.0e-6, 2.0e-6),
      values=(1.0, 2.0),
      measurement_space=SpectralMeasurementSpace.INTRINSIC_RADIANT_INTENSITY,
      units=SENSOR_SPACE_SPECTRAL_RADIANCE_UNITS,
    )
