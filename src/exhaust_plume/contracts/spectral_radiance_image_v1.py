"""Source-bound pre-detector spectral-radiance image contract, version 1."""

from __future__ import annotations

from math import isfinite
from typing import Any, Literal, TypeAlias

from pydantic import Field, StrictInt, field_validator, model_validator

from exhaust_plume.contracts.capability import IMAGE_SPECTRAL_RADIANCE_CAPABILITY
from exhaust_plume.contracts.common_v1 import (
  ApiModel,
  Derivation,
  MatrixBool,
  MatrixFloat,
  ResultMetadata,
  SampleStatus,
  SampleStatusCode,
)
from exhaust_plume.contracts._validation import contains_boolean, contains_non_boolean

SpectralRadianceImageTensor: TypeAlias = tuple[tuple[tuple[float, ...], ...], ...]
PixelIndices = tuple[tuple[StrictInt, StrictInt], ...]
PixelCounts = tuple[tuple[StrictInt, ...], ...]


class SpectralRadianceImageRequest(ApiModel):
  """Bind a pixel grid to one exact ray result and pixel quadrature."""

  pixel_frame_id: str = Field(min_length=1)
  ray_frame_id: str = Field(min_length=1)
  ray_transfer_request_digest_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
  ray_transfer_result_id: str = Field(min_length=1)
  ray_transfer_result_digest_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
  pixel_geometry_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
  width_px: StrictInt = Field(gt=0)
  height_px: StrictInt = Field(gt=0)
  pixel_indexing: Literal['zero-based-row-column'] = 'zero-based-row-column'
  ray_pixel_indices_row_col: PixelIndices = Field(min_length=1)
  ray_collection_weights_m2_sr: tuple[float, ...] = Field(min_length=1)
  aggregation_policy: Literal['normalized-collection-weighted-mean'] = (
    'normalized-collection-weighted-mean'
  )

  @field_validator('ray_collection_weights_m2_sr', mode='before')
  @classmethod
  def reject_boolean_weights(cls, value: Any) -> Any:
    if contains_boolean(value):
      raise ValueError('ray collection weights must be numeric, not booleans')
    ####
    return value
  ####

  @model_validator(mode='after')
  def validate_pixel_mapping(self) -> 'SpectralRadianceImageRequest':
    if len(self.ray_pixel_indices_row_col) != len(self.ray_collection_weights_m2_sr):
      raise ValueError('each mapped ray must have exactly one collection weight')
    ####
    for index, (row, column) in enumerate(self.ray_pixel_indices_row_col):
      if row < 0 or row >= self.height_px or column < 0 or column >= self.width_px:
        raise ValueError(f'ray_pixel_indices_row_col[{index}] is outside the declared image grid')
      ####
    ####
    if any(not isfinite(weight) or weight <= 0.0 for weight in self.ray_collection_weights_m2_sr):
      raise ValueError('ray collection weights must be finite and positive')
    ####
    return self
  ####
####


class SpectralRadianceImageResult(ApiModel):
  """Per-pixel source radiance and background transmittance before detection.

  For each pixel, source radiance and background transmittance are the
  normalized collection-weighted means of its exact contributing ray samples.
  A pixel is invalid if any mapped ray is invalid. Detector response, exposure
  integration, dark current, noise, and digitization belong to the separate
  FPA detector-frame contract.
  """

  metadata: ResultMetadata
  pixel_frame_id: str = Field(min_length=1)
  ray_frame_id: str = Field(min_length=1)
  ray_transfer_request_digest_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
  ray_transfer_result_id: str = Field(min_length=1)
  ray_transfer_result_digest_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
  pixel_geometry_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
  width_px: StrictInt = Field(gt=0)
  height_px: StrictInt = Field(gt=0)
  pixel_indexing: Literal['zero-based-row-column'] = 'zero-based-row-column'
  wavelengths_m: tuple[float, ...] = Field(min_length=1)
  source_spectral_radiance_W_m2_sr_m: SpectralRadianceImageTensor
  background_transmittance: SpectralRadianceImageTensor
  validity_mask: MatrixBool
  pixel_status: tuple[tuple[SampleStatus, ...], ...]
  ray_sample_count: PixelCounts
  pixel_collection_weight_m2_sr: MatrixFloat
  aggregation_policy: Literal['normalized-collection-weighted-mean'] = (
    'normalized-collection-weighted-mean'
  )
  source_component: Literal['plume-source-only'] = 'plume-source-only'

  @field_validator(
    'wavelengths_m',
    'source_spectral_radiance_W_m2_sr_m',
    'background_transmittance',
    'pixel_collection_weight_m2_sr',
    mode='before',
  )
  @classmethod
  def reject_boolean_numeric_values(cls, value: Any) -> Any:
    if contains_boolean(value):
      raise ValueError('spectral-image numeric values must not be booleans')
    ####
    return value
  ####

  @field_validator('validity_mask', mode='before')
  @classmethod
  def require_boolean_validity_mask(cls, value: Any) -> Any:
    if contains_non_boolean(value):
      raise ValueError('validity_mask must contain booleans')
    ####
    return value
  ####

  @model_validator(mode='after')
  def validate_image(self) -> 'SpectralRadianceImageResult':
    if self.metadata.capability != IMAGE_SPECTRAL_RADIANCE_CAPABILITY:
      raise ValueError('image metadata must identify plume.image.spectral-radiance@1')
    ####
    if self.metadata.output_frame_id != self.pixel_frame_id:
      raise ValueError('image metadata output frame must match pixel_frame_id')
    ####
    if self.metadata.claims.derivation is not Derivation.ADAPTED:
      raise ValueError('spectral-radiance image derivation must be adapted')
    ####
    if self.ray_transfer_result_id not in self.metadata.provenance.parent_result_ids:
      raise ValueError('image provenance must retain the exact ray-transfer result ID')
    ####
    provenance_metadata = self.metadata.provenance.metadata
    expected_lineage = {
      'pixel_geometry_sha256': self.pixel_geometry_sha256,
      'ray_transfer_request_digest_sha256': self.ray_transfer_request_digest_sha256,
      'ray_transfer_result_digest_sha256': self.ray_transfer_result_digest_sha256,
    }
    if any(provenance_metadata.get(key) != value for key, value in expected_lineage.items()):
      raise ValueError('image provenance metadata must match the exact ray and pixel lineage fields')
    ####
    if (
        provenance_metadata.get('spectral_radiance_image_request_digest_sha256')
        != self.metadata.request_digest_sha256
    ):
      raise ValueError('image provenance must retain its exact request digest')
    ####
    wavelengths = self.wavelengths_m
    if not all(isfinite(value) and value > 0.0 for value in wavelengths):
      raise ValueError('image wavelengths must be finite and positive')
    ####
    if any(right <= left for left, right in zip(wavelengths, wavelengths[1:])):
      raise ValueError('image wavelengths must be strictly increasing')
    ####
    for name, image in (
      ('source_spectral_radiance_W_m2_sr_m', self.source_spectral_radiance_W_m2_sr_m),
      ('background_transmittance', self.background_transmittance),
    ):
      if len(image) != self.height_px or any(len(row) != self.width_px for row in image):
        raise ValueError(f'{name} must have shape (height_px, width_px, wavelength_count)')
      ####
      if any(len(pixel) != len(wavelengths) for row in image for pixel in row):
        raise ValueError(f'{name} wavelength dimension must match wavelengths_m')
      ####
    ####
    expected_shape = (self.height_px, self.width_px)
    for name, grid in (
      ('validity_mask', self.validity_mask),
      ('pixel_status', self.pixel_status),
      ('ray_sample_count', self.ray_sample_count),
      ('pixel_collection_weight_m2_sr', self.pixel_collection_weight_m2_sr),
    ):
      if len(grid) != expected_shape[0] or any(len(row) != expected_shape[1] for row in grid):
        raise ValueError(f'{name} must have shape (height_px, width_px)')
      ####
    ####
    for row_index in range(self.height_px):
      for column_index in range(self.width_px):
        valid = self.validity_mask[row_index][column_index]
        status = self.pixel_status[row_index][column_index]
        sample_count = self.ray_sample_count[row_index][column_index]
        weight = self.pixel_collection_weight_m2_sr[row_index][column_index]
        source = self.source_spectral_radiance_W_m2_sr_m[row_index][column_index]
        transmittance = self.background_transmittance[row_index][column_index]
        if sample_count < 0 or not isfinite(weight) or weight < 0.0:
          raise ValueError('ray sample counts and pixel collection weights must be nonnegative')
        ####
        if valid:
          if status.code is not SampleStatusCode.OK:
            raise ValueError('valid pixels must have an OK sample status')
          ####
          if sample_count == 0 or weight <= 0.0:
            raise ValueError('a valid pixel requires contributing rays and positive collection weight')
          ####
        else:
          if status.code is SampleStatusCode.OK:
            raise ValueError('invalid pixels must have a non-OK sample status')
          ####
          if any(value != 0.0 for value in source):
            raise ValueError('an invalid pixel must use zero source-radiance placeholders')
          ####
          if any(value != 1.0 for value in transmittance):
            raise ValueError('an invalid pixel must use unit transmittance placeholders')
          ####
        ####
        if any(not isfinite(value) or value < 0.0 for value in source):
          raise ValueError('source spectral radiance must be finite and nonnegative')
        ####
        if any(not isfinite(value) or value < 0.0 or value > 1.0 for value in transmittance):
          raise ValueError('background transmittance must be finite and in [0, 1]')
        ####
      ####
    ####
    return self
  ####
####


__all__ = (
  'IMAGE_SPECTRAL_RADIANCE_CAPABILITY',
  'SpectralRadianceImageRequest',
  'SpectralRadianceImageResult',
)
