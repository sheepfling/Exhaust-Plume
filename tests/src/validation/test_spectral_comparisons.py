from __future__ import annotations

import pytest

from exhaust_plume.validation import compare_peak_normalized_spectral_shape


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
