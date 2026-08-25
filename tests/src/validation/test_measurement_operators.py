from __future__ import annotations

import pytest

from exhaust_plume.validation.measurement_operators import (
  integrate_spectral_band_rows,
  peak_normalize_spectral_rows,
  sample_spectral_rows,
)


def test_sampling_is_linear_and_does_not_extrapolate() -> None:
  result = sample_spectral_rows(
    (1.0e-6, 3.0e-6),
    ((2.0, 6.0),),
    (1.5e-6, 2.5e-6),
  )

  assert result.values == ((3.0, 5.0),)
  assert result.validity_mask == ((True, True),)
  with pytest.raises(ValueError, match='outside the source spectral domain'):
    sample_spectral_rows((1.0e-6, 3.0e-6), ((2.0, 6.0),), (0.5e-6,))
####


def test_peak_normalization_preserves_invalid_samples_and_records_factor() -> None:
  result = peak_normalize_spectral_rows(
    (1.0e-6, 2.0e-6, 3.0e-6),
    ((2.0, 0.0, 4.0), (1.0, 2.0, 3.0)),
    validity_mask=((True, False, True), (False, False, False)),
  )

  assert result.values == ((0.5, 0.0, 1.0), (0.0, 0.0, 0.0))
  assert result.validity_mask == ((True, False, True), (False, False, False))
  assert result.normalization_factors == (4.0, None)
  assert result.peak_indices == (2, None)
####


def test_band_integration_interpolates_endpoints_and_rejects_invalid_spans() -> None:
  result = integrate_spectral_band_rows(
    (1.0e-6, 2.0e-6, 3.0e-6),
    ((1.0, 2.0, 3.0), (1.0, 2.0, 3.0)),
    1.5e-6,
    2.5e-6,
  )

  assert result.values == pytest.approx((2.0e-6, 2.0e-6))
  assert result.validity_mask == (True, True)

  invalid = integrate_spectral_band_rows(
    (1.0e-6, 2.0e-6, 3.0e-6),
    ((1.0, 2.0, 3.0),),
    1.5e-6,
    2.5e-6,
    validity_mask=((True, False, True),),
  )
  assert invalid.values == (0.0,)
  assert invalid.validity_mask == (False,)
####
