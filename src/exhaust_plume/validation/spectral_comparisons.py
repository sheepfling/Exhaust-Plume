"""Measurement-space spectral-shape comparison diagnostics.

These routines execute the numerical part of a peak-normalized spectral-shape
comparison when the model and observation domains overlap.  They deliberately
report incomplete-domain diagnostics instead of extrapolating.  A computed
residual is not an accepted product claim: source scenario, calibration, and
operator provenance remain separate validation gates.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import fsum, isfinite, sqrt

from exhaust_plume.validation.measurement_operators import (
  peak_normalize_spectral_rows,
  sample_spectral_rows,
)


def _axis(values: tuple[float, ...] | list[float], field_name: str) -> tuple[float, ...]:
  axis = tuple(float(value) for value in values)
  if len(axis) < 2 or not all(isfinite(value) and value > 0.0 for value in axis):
    raise ValueError(f'{field_name} must contain at least two finite positive values')
  ####
  if any(right <= left for left, right in zip(axis, axis[1:])):
    raise ValueError(f'{field_name} must be strictly increasing')
  ####
  return axis
####


def _values(values: tuple[float, ...] | list[float], field_name: str) -> tuple[float, ...]:
  normalized = tuple(float(value) for value in values)
  if not normalized or any(not isfinite(value) or value < 0.0 for value in normalized):
    raise ValueError(f'{field_name} must contain finite nonnegative values')
  ####
  return normalized
####


@dataclass(frozen=True, slots=True)
class SpectralShapeComparison:
  """Residual and coverage diagnostics for one spectral-shape comparison."""

  status: str
  model_domain_m: tuple[float, float]
  observed_domain_m: tuple[float, float]
  overlap_domain_m: tuple[float, float] | None
  observed_sample_count: int
  overlap_sample_count: int
  coverage_fraction: float
  overlap_relative_shape_rmse: float | None
  overlap_peak_location_error_m: float | None
  full_domain_relative_shape_rmse: float | None
  full_domain_peak_location_error_m: float | None
  reason: str | None = None


def _shape_metrics(
    wavelengths_m: tuple[float, ...],
    model_values: tuple[float, ...],
    observed_values: tuple[float, ...],
) -> tuple[float | None, float | None]:
  model = peak_normalize_spectral_rows(wavelengths_m, (model_values,))
  observed = peak_normalize_spectral_rows(wavelengths_m, (observed_values,))
  if not all(model.validity_mask[0]) or not all(observed.validity_mask[0]):
    return None, None
  ####
  model_row = model.values[0]
  observed_row = observed.values[0]
  rmse = sqrt(fsum((left - right) ** 2 for left, right in zip(model_row, observed_row)) / len(model_row))
  model_peak = wavelengths_m[model.peak_indices[0]] if model.peak_indices[0] is not None else None
  observed_peak = wavelengths_m[observed.peak_indices[0]] if observed.peak_indices[0] is not None else None
  peak_error = None if model_peak is None or observed_peak is None else abs(model_peak - observed_peak)
  return rmse, peak_error
####


def compare_peak_normalized_spectral_shape(
    model_wavelengths_m: tuple[float, ...] | list[float],
    model_values: tuple[float, ...] | list[float],
    observed_wavelengths_m: tuple[float, ...] | list[float],
    observed_values: tuple[float, ...] | list[float],
) -> SpectralShapeComparison:
  """Compare model and observed relative spectra without extrapolation.

  The full-domain metric is populated only when the model covers the complete
  observation domain.  A partial-overlap metric is still useful as a named
  diagnostic, but its normalization is restricted to the overlap and it must
  not be used as full-band validation evidence.
  """

  model_axis = _axis(model_wavelengths_m, 'model_wavelengths_m')
  observed_axis = _axis(observed_wavelengths_m, 'observed_wavelengths_m')
  model_row = _values(model_values, 'model_values')
  observed_row = _values(observed_values, 'observed_values')
  if len(model_axis) != len(model_row) or len(observed_axis) != len(observed_row):
    raise ValueError('wavelength and spectral-value arrays must have matching lengths')
  ####
  overlap_lower = max(model_axis[0], observed_axis[0])
  overlap_upper = min(model_axis[-1], observed_axis[-1])
  observed_span = observed_axis[-1] - observed_axis[0]
  if overlap_lower > overlap_upper:
    return SpectralShapeComparison(
      status='no-overlap',
      model_domain_m=(model_axis[0], model_axis[-1]),
      observed_domain_m=(observed_axis[0], observed_axis[-1]),
      overlap_domain_m=None,
      observed_sample_count=len(observed_axis),
      overlap_sample_count=0,
      coverage_fraction=0.0,
      overlap_relative_shape_rmse=None,
      overlap_peak_location_error_m=None,
      full_domain_relative_shape_rmse=None,
      full_domain_peak_location_error_m=None,
      reason='model and observed wavelength domains do not overlap',
    )
  ####
  overlap_axis = tuple(
    wavelength for wavelength in observed_axis
    if overlap_lower <= wavelength <= overlap_upper
  )
  overlap_values = tuple(
    value for wavelength, value in zip(observed_axis, observed_row, strict=True)
    if overlap_lower <= wavelength <= overlap_upper
  )
  coverage_fraction = (overlap_upper - overlap_lower) / observed_span
  if len(overlap_axis) < 2:
    return SpectralShapeComparison(
      status='insufficient-overlap-samples',
      model_domain_m=(model_axis[0], model_axis[-1]),
      observed_domain_m=(observed_axis[0], observed_axis[-1]),
      overlap_domain_m=(overlap_lower, overlap_upper),
      observed_sample_count=len(observed_axis),
      overlap_sample_count=len(overlap_axis),
      coverage_fraction=coverage_fraction,
      overlap_relative_shape_rmse=None,
      overlap_peak_location_error_m=None,
      full_domain_relative_shape_rmse=None,
      full_domain_peak_location_error_m=None,
      reason='fewer than two observed samples lie in the model domain',
    )
  ####
  sampled_model = sample_spectral_rows(model_axis, (model_row,), overlap_axis)
  overlap_rmse, overlap_peak_error = _shape_metrics(
    overlap_axis,
    sampled_model.values[0],
    overlap_values,
  )
  full_domain = model_axis[0] <= observed_axis[0] and model_axis[-1] >= observed_axis[-1]
  full_rmse = None
  full_peak_error = None
  status = 'partial-overlap-diagnostic'
  reason = 'model does not cover the complete observed wavelength domain'
  if full_domain:
    full_sampled_model = sample_spectral_rows(model_axis, (model_row,), observed_axis)
    full_rmse, full_peak_error = _shape_metrics(
      observed_axis,
      full_sampled_model.values[0],
      observed_row,
    )
    status = 'full-domain-computed' if full_rmse is not None else 'invalid-spectrum'
    reason = None if full_rmse is not None else 'model or observed spectrum has no valid positive peak'
  ####
  return SpectralShapeComparison(
    status=status,
    model_domain_m=(model_axis[0], model_axis[-1]),
    observed_domain_m=(observed_axis[0], observed_axis[-1]),
    overlap_domain_m=(overlap_lower, overlap_upper),
    observed_sample_count=len(observed_axis),
    overlap_sample_count=len(overlap_axis),
    coverage_fraction=coverage_fraction,
    overlap_relative_shape_rmse=overlap_rmse,
    overlap_peak_location_error_m=overlap_peak_error,
    full_domain_relative_shape_rmse=full_rmse,
    full_domain_peak_location_error_m=full_peak_error,
    reason=reason,
  )
####


__all__ = ('SpectralShapeComparison', 'compare_peak_normalized_spectral_shape')
