"""Small, explicit measurement-space operators for validation comparisons.

These helpers deliberately operate on plain spectral arrays rather than
changing a product's meaning.  They model the numerical parts of a sensor
operator that are unambiguous from the available data: interpolation onto a
requested wavelength grid, peak normalization, and trapezoidal band
integration.  Detector response, line-of-sight geometry, atmosphere, and
source/path separation remain outside this module.
"""

from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass
from math import isfinite


SPECTRAL_SAMPLING_OPERATOR_ID = 'op.sensor.spectral-sampling'
PEAK_NORMALIZATION_OPERATOR_ID = 'op.sensor.peak-normalize-spectrum'
BAND_INTEGRATION_OPERATOR_ID = 'op.sensor.band-integral'

FloatMatrix = tuple[tuple[float, ...], ...]
BoolMatrix = tuple[tuple[bool, ...], ...]


@dataclass(frozen=True, slots=True)
class SampledSpectrum:
  """A spectrum sampled on a new wavelength grid with validity preserved."""

  wavelengths_m: tuple[float, ...]
  values: FloatMatrix
  validity_mask: BoolMatrix
####


@dataclass(frozen=True, slots=True)
class PeakNormalizedSpectrum:
  """Peak-normalized rows and the factors used to normalize them."""

  wavelengths_m: tuple[float, ...]
  values: FloatMatrix
  validity_mask: BoolMatrix
  normalization_factors: tuple[float | None, ...]
  peak_indices: tuple[int | None, ...]
####


@dataclass(frozen=True, slots=True)
class BandIntegratedSpectrum:
  """Band integrals with one validity flag per input row."""

  band_min_m: float
  band_max_m: float
  values: tuple[float, ...]
  validity_mask: tuple[bool, ...]
####


def _axis(values: tuple[float, ...] | list[float], field_name: str) -> tuple[float, ...]:
  axis = tuple(float(value) for value in values)
  if not axis or not all(isfinite(value) and value > 0.0 for value in axis):
    raise ValueError(f'{field_name} must be finite, positive, and non-empty')
  ####
  if any(next_value <= value for value, next_value in zip(axis, axis[1:])):
    raise ValueError(f'{field_name} must be strictly increasing')
  ####
  return axis
####


def _matrix(
    values: tuple[tuple[float, ...], ...] | list[tuple[float, ...]] | list[list[float]],
    *,
    column_count: int,
    field_name: str,
) -> FloatMatrix:
  matrix = tuple(tuple(float(value) for value in row) for row in values)
  if not matrix or any(len(row) != column_count for row in matrix):
    raise ValueError(f'{field_name} must be a non-empty rectangular matrix')
  ####
  if any(not isfinite(value) or value < 0.0 for row in matrix for value in row):
    raise ValueError(f'{field_name} must contain finite, nonnegative values')
  ####
  return matrix
####


def _mask(
    validity_mask: tuple[tuple[bool, ...], ...] | list[tuple[bool, ...]] | list[list[bool]] | None,
    *,
    row_count: int,
    column_count: int,
) -> BoolMatrix:
  if validity_mask is None:
    return tuple((True,) * column_count for _ in range(row_count))
  ####
  mask = tuple(tuple(value for value in row) for row in validity_mask)
  if len(mask) != row_count or any(len(row) != column_count for row in mask):
    raise ValueError('validity_mask must match the spectral matrix shape')
  ####
  if any(not isinstance(value, bool) for row in mask for value in row):
    raise ValueError('validity_mask must contain bool values')
  ####
  return mask
####


def _validated_inputs(
    wavelengths_m: tuple[float, ...] | list[float],
    values: tuple[tuple[float, ...], ...] | list[tuple[float, ...]] | list[list[float]],
    validity_mask: tuple[tuple[bool, ...], ...] | list[tuple[bool, ...]] | list[list[bool]] | None,
) -> tuple[tuple[float, ...], FloatMatrix, BoolMatrix]:
  wavelengths = _axis(wavelengths_m, 'wavelengths_m')
  matrix = _matrix(values, column_count=len(wavelengths), field_name='values')
  mask = _mask(validity_mask, row_count=len(matrix), column_count=len(wavelengths))
  return wavelengths, matrix, mask
####


def _sample_value(
    wavelengths_m: tuple[float, ...],
    row: tuple[float, ...],
    mask: tuple[bool, ...],
    wavelength_m: float,
) -> tuple[float, bool]:
  if wavelength_m < wavelengths_m[0] or wavelength_m > wavelengths_m[-1]:
    raise ValueError('requested wavelength is outside the source spectral domain')
  ####
  upper = bisect_left(wavelengths_m, wavelength_m)
  if upper < len(wavelengths_m) and wavelengths_m[upper] == wavelength_m:
    return (row[upper], mask[upper]) if mask[upper] else (0.0, False)
  ####
  if upper == 0 or upper == len(wavelengths_m):
    raise ValueError('requested wavelength is outside the source spectral domain')
  ####
  lower = upper - 1
  if not mask[lower] or not mask[upper]:
    return 0.0, False
  ####
  fraction = (wavelength_m - wavelengths_m[lower]) / (wavelengths_m[upper] - wavelengths_m[lower])
  return row[lower] + fraction * (row[upper] - row[lower]), True
####


def sample_spectral_rows(
    wavelengths_m: tuple[float, ...] | list[float],
    values: tuple[tuple[float, ...], ...] | list[tuple[float, ...]] | list[list[float]],
    requested_wavelengths_m: tuple[float, ...] | list[float],
    *,
    validity_mask: tuple[tuple[bool, ...], ...] | list[tuple[bool, ...]] | list[list[bool]] | None = None,
) -> SampledSpectrum:
  """Linearly sample every row without extrapolating or hiding invalid data."""

  source_wavelengths, matrix, source_mask = _validated_inputs(wavelengths_m, values, validity_mask)
  requested = _axis(requested_wavelengths_m, 'requested_wavelengths_m')
  sampled_values: list[tuple[float, ...]] = []
  sampled_mask: list[tuple[bool, ...]] = []
  for row, row_mask in zip(matrix, source_mask, strict=True):
    row_values: list[float] = []
    row_validity: list[bool] = []
    for wavelength in requested:
      value, valid = _sample_value(source_wavelengths, row, row_mask, wavelength)
      row_values.append(value if valid else 0.0)
      row_validity.append(valid)
    ####
    sampled_values.append(tuple(row_values))
    sampled_mask.append(tuple(row_validity))
  ####
  return SampledSpectrum(
    wavelengths_m=requested,
    values=tuple(sampled_values),
    validity_mask=tuple(sampled_mask),
  )
####


def peak_normalize_spectral_rows(
    wavelengths_m: tuple[float, ...] | list[float],
    values: tuple[tuple[float, ...], ...] | list[tuple[float, ...]] | list[list[float]],
    *,
    validity_mask: tuple[tuple[bool, ...], ...] | list[tuple[bool, ...]] | list[list[bool]] | None = None,
) -> PeakNormalizedSpectrum:
  """Normalize each valid row by its maximum sampled value.

  A row with no valid positive sample has no defined peak-normalized shape and
  is returned as an invalid zero row.  This prevents a missing or zero signal
  from becoming a deceptively perfect normalized comparison.
  """

  wavelengths, matrix, mask = _validated_inputs(wavelengths_m, values, validity_mask)
  normalized_values: list[tuple[float, ...]] = []
  normalized_mask: list[tuple[bool, ...]] = []
  factors: list[float | None] = []
  peak_indices: list[int | None] = []
  for row, row_mask in zip(matrix, mask, strict=True):
    valid_indices = tuple(index for index, valid in enumerate(row_mask) if valid and row[index] > 0.0)
    if not valid_indices:
      normalized_values.append((0.0,) * len(wavelengths))
      normalized_mask.append((False,) * len(wavelengths))
      factors.append(None)
      peak_indices.append(None)
      continue
    ####
    peak_index = max(valid_indices, key=lambda index: (row[index], -index))
    factor = row[peak_index]
    normalized_values.append(tuple(row[index] / factor if row_mask[index] else 0.0 for index in range(len(row))))
    normalized_mask.append(tuple(row_mask))
    factors.append(factor)
    peak_indices.append(peak_index)
  ####
  return PeakNormalizedSpectrum(
    wavelengths_m=wavelengths,
    values=tuple(normalized_values),
    validity_mask=tuple(normalized_mask),
    normalization_factors=tuple(factors),
    peak_indices=tuple(peak_indices),
  )
####


def integrate_spectral_band_rows(
    wavelengths_m: tuple[float, ...] | list[float],
    values: tuple[tuple[float, ...], ...] | list[tuple[float, ...]] | list[list[float]],
    band_min_m: float,
    band_max_m: float,
    *,
    validity_mask: tuple[tuple[bool, ...], ...] | list[tuple[bool, ...]] | list[list[bool]] | None = None,
) -> BandIntegratedSpectrum:
  """Integrate valid spectral rows over a closed band by linear interpolation."""

  source_wavelengths, matrix, source_mask = _validated_inputs(wavelengths_m, values, validity_mask)
  lower = float(band_min_m)
  upper = float(band_max_m)
  if not isfinite(lower) or not isfinite(upper) or lower <= 0.0 or upper <= lower:
    raise ValueError('band bounds must be finite, positive, and strictly increasing')
  ####
  if lower < source_wavelengths[0] or upper > source_wavelengths[-1]:
    raise ValueError('integration band is outside the source spectral domain')
  ####
  nodes = (lower, *(
    wavelength for wavelength in source_wavelengths if lower < wavelength < upper
  ), upper)
  integrated: list[float] = []
  integrated_mask: list[bool] = []
  for row, row_mask in zip(matrix, source_mask, strict=True):
    samples = tuple(_sample_value(source_wavelengths, row, row_mask, node) for node in nodes)
    valid = all(item[1] for item in samples)
    if not valid:
      integrated.append(0.0)
      integrated_mask.append(False)
      continue
    ####
    area = sum(
      0.5 * (right[0] + left[0]) * (right_node - left_node)
      for left_node, right_node, left, right in zip(
        nodes[:-1],
        nodes[1:],
        samples[:-1],
        samples[1:],
        strict=True,
      )
    )
    integrated.append(area)
    integrated_mask.append(isfinite(area) and area >= 0.0)
  ####
  return BandIntegratedSpectrum(
    band_min_m=lower,
    band_max_m=upper,
    values=tuple(value if valid else 0.0 for value, valid in zip(integrated, integrated_mask, strict=True)),
    validity_mask=tuple(integrated_mask),
  )
####


__all__ = (
  'BAND_INTEGRATION_OPERATOR_ID',
  'BandIntegratedSpectrum',
  'BoolMatrix',
  'FloatMatrix',
  'PEAK_NORMALIZATION_OPERATOR_ID',
  'PeakNormalizedSpectrum',
  'SPECTRAL_SAMPLING_OPERATOR_ID',
  'SampledSpectrum',
  'integrate_spectral_band_rows',
  'peak_normalize_spectral_rows',
  'sample_spectral_rows',
)
