"""Unresolved wavelength-resolved spectral intensity contract, version 1."""

from __future__ import annotations

from math import isfinite, sqrt

from pydantic import Field, model_validator

from exhaust_plume.contracts.capability import SIGNATURE_SPECTRAL_RADIANT_INTENSITY_CAPABILITY
from exhaust_plume.contracts.common_v1 import (
  ApiModel,
  ApplicabilityReport,
  MatrixBool,
  MatrixFloat,
  ResultMetadata,
  SampleStatus,
  SampleStatusCode,
  validate_rectangular_matrix,
)

SPECTRAL_RADIANT_INTENSITY_CAPABILITY = SIGNATURE_SPECTRAL_RADIANT_INTENSITY_CAPABILITY

class SpectralSignatureRequest(ApiModel):
  direction_frame_id: str = Field(min_length=1)
  operating_point_id: str | None = Field(default=None, min_length=1)
  source_to_observer_directions: tuple[tuple[float, float, float], ...] = Field(min_length=1)
  wavelengths_m: tuple[float, ...] = Field(min_length=1)
  allow_partial_results: bool = False

  @model_validator(mode='after')
  def validate_axes(self) -> 'SpectralSignatureRequest':
    for direction in self.source_to_observer_directions:
      if not all(isfinite(value) for value in direction):
        raise ValueError('source-to-observer directions must be finite')
      ####
      norm = sqrt(sum(value * value for value in direction))
      if abs(norm - 1.0) > 1.0e-6:
        raise ValueError('source-to-observer directions must be unit length')
      ####
    ####
    if not all(isfinite(value) and value > 0.0 for value in self.wavelengths_m):
      raise ValueError('wavelengths must be finite and positive')
    ####
    if any(next_value <= value for value, next_value in zip(self.wavelengths_m, self.wavelengths_m[1:])):
      raise ValueError('wavelengths must be strictly increasing')
    ####
    return self
  ####
####


class SpectralSignatureResult(ApiModel):
  metadata: ResultMetadata
  spectral_radiant_intensity: MatrixFloat
  validity_mask: MatrixBool
  direction_status: tuple[SampleStatus, ...] = Field(min_length=1)
  absolute_standard_uncertainty: MatrixFloat | None = None

  @model_validator(mode='after')
  def validate_values(self) -> 'SpectralSignatureResult':
    if self.metadata.capability != SPECTRAL_RADIANT_INTENSITY_CAPABILITY:
      raise ValueError('signature result metadata must identify plume.signature.spectral-radiant-intensity@1')
    ####
    row_count, column_count = validate_rectangular_matrix(
      self.spectral_radiant_intensity,
      'spectral_radiant_intensity',
    )
    validity_rows, validity_columns = validate_rectangular_matrix(self.validity_mask, 'validity_mask')
    if (validity_rows, validity_columns) != (row_count, column_count):
      raise ValueError('signature matrices must have matching rectangular shapes')
    ####
    if self.absolute_standard_uncertainty is not None:
      uncertainty_rows, uncertainty_columns = validate_rectangular_matrix(
        self.absolute_standard_uncertainty,
        'absolute_standard_uncertainty',
      )
      if (uncertainty_rows, uncertainty_columns) != (row_count, column_count):
        raise ValueError('signature matrices must have matching rectangular shapes')
      ####
    ####
    if any(not isfinite(value) or value < 0.0 for row in self.spectral_radiant_intensity for value in row):
      raise ValueError('spectral intensity must be finite and nonnegative')
    ####
    if self.absolute_standard_uncertainty is not None and any(
        not isfinite(value) or value < 0.0
        for row in self.absolute_standard_uncertainty
        for value in row
    ):
      raise ValueError('absolute standard uncertainty must be finite and nonnegative')
    ####
    if len(self.direction_status) != row_count:
      raise ValueError('direction status count must equal direction count')
    ####
    for index, status in enumerate(self.direction_status):
      valid_row = self.validity_mask[index]
      intensity_row = self.spectral_radiant_intensity[index]
      if status.code is SampleStatusCode.OK:
        if not all(valid_row):
          raise ValueError('an OK signature direction must mark all wavelengths valid')
        ####
        continue
      ####
      if any(valid_row):
        raise ValueError('a failed signature direction must mark all wavelengths invalid')
      ####
      if any(abs(value) > 1.0e-12 for value in intensity_row):
        raise ValueError('a failed signature direction must use zero placeholder intensity')
      ####
      if self.absolute_standard_uncertainty is not None and any(
          abs(value) > 1.0e-12 for value in self.absolute_standard_uncertainty[index]
      ):
        raise ValueError('a failed signature direction must use zero placeholder uncertainty')
      ####
    ####
    return self
  ####

  @property
  def applicability(self) -> ApplicabilityReport:
    """Expose common metadata without requiring a product-specific wrapper."""

    return self.metadata.applicability
  ####
####


__all__ = (
  'SPECTRAL_RADIANT_INTENSITY_CAPABILITY',
  'SpectralSignatureRequest',
  'SpectralSignatureResult',
)
