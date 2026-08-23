"""Resolved wavelength-resolved spectral ray-transfer contract, version 1."""

from __future__ import annotations

from math import isfinite, sqrt

from pydantic import Field, model_validator

from exhaust_plume.contracts.capability import SPECTRAL_RAY_TRANSFER_CAPABILITY
from exhaust_plume.contracts.common_v1 import (
  ApiModel,
  MatrixBool,
  MatrixFloat,
  ResultMetadata,
  SampleStatus,
  validate_rectangular_matrix,
)

class SpectralRayTransferRequest(ApiModel):
  ray_frame_id: str = Field(min_length=1)
  ray_origins_m: tuple[tuple[float, float, float], ...] = Field(min_length=1)
  ray_directions: tuple[tuple[float, float, float], ...] = Field(min_length=1)
  ray_t_min_m: tuple[float, ...] = Field(min_length=1)
  ray_t_max_m: tuple[float, ...] = Field(min_length=1)
  wavelengths_m: tuple[float, ...] = Field(min_length=1)
  quality_profile: str = Field(default='standard', min_length=1)
  allow_partial_results: bool = False

  @model_validator(mode='after')
  def validate_rays(self) -> 'SpectralRayTransferRequest':
    ray_count = len(self.ray_origins_m)
    if not (
        len(self.ray_directions) == ray_count
        and len(self.ray_t_min_m) == ray_count
        and len(self.ray_t_max_m) == ray_count
    ):
      raise ValueError('ray origins, directions, and interval arrays must have matching lengths')
    for origin in self.ray_origins_m:
      if not all(isfinite(value) for value in origin):
        raise ValueError('ray origins must be finite')
    for direction in self.ray_directions:
      if not all(isfinite(value) for value in direction):
        raise ValueError('ray directions must be finite')
      norm = sqrt(sum(value * value for value in direction))
      if abs(norm - 1.0) > 1.0e-6:
        raise ValueError('ray directions must be unit length')
    for t_min, t_max in zip(self.ray_t_min_m, self.ray_t_max_m, strict=True):
      if not (isfinite(t_min) and isfinite(t_max) and 0.0 <= t_min < t_max):
        raise ValueError('each ray interval must satisfy 0 <= t_min < t_max')
    if not all(isfinite(value) and value > 0.0 for value in self.wavelengths_m):
      raise ValueError('wavelengths must be finite and positive')
    if any(next_value <= value for value, next_value in zip(self.wavelengths_m, self.wavelengths_m[1:])):
      raise ValueError('wavelengths must be strictly increasing')
    return self
  ####
####


class SpectralRayTransferResult(ApiModel):
  metadata: ResultMetadata
  source_spectral_radiance: MatrixFloat
  background_transmittance: MatrixFloat
  validity_mask: MatrixBool
  ray_status: tuple[SampleStatus, ...] = Field(min_length=1)
  hit_mask: tuple[bool, ...] = Field(min_length=1)
  optical_depth: MatrixFloat | None = None
  plume_intersection_t_m: tuple[tuple[float, float] | None, ...] | None = None

  @model_validator(mode='after')
  def validate_result(self) -> 'SpectralRayTransferResult':
    if self.metadata.capability != SPECTRAL_RAY_TRANSFER_CAPABILITY:
      raise ValueError('ray result metadata must identify plume.optical.spectral-ray-transfer@1')
    ray_count, wavelength_count = validate_rectangular_matrix(
      self.source_spectral_radiance,
      'source_spectral_radiance',
    )
    for field_name, matrix in (
      ('background_transmittance', self.background_transmittance),
      ('validity_mask', self.validity_mask),
    ):
      if validate_rectangular_matrix(matrix, field_name) != (ray_count, wavelength_count):
        raise ValueError('ray matrices must have matching rectangular shapes')
    if self.optical_depth is not None and validate_rectangular_matrix(
        self.optical_depth,
        'optical_depth',
    ) != (ray_count, wavelength_count):
      raise ValueError('ray matrices must have matching rectangular shapes')
    if len(self.ray_status) != ray_count or len(self.hit_mask) != ray_count:
      raise ValueError('ray status and hit-mask counts must equal ray count')
    if self.plume_intersection_t_m is not None:
      if len(self.plume_intersection_t_m) != ray_count:
        raise ValueError('intersection interval count must equal ray count')
      for interval in self.plume_intersection_t_m:
        if interval is None:
          continue
        t_enter, t_exit = interval
        if not (isfinite(t_enter) and isfinite(t_exit) and 0.0 <= t_enter < t_exit):
          raise ValueError('each plume intersection interval must satisfy 0 <= t_enter < t_exit')
    if any(
        not isfinite(value) or value < 0.0
        for row in self.source_spectral_radiance
        for value in row
    ):
      raise ValueError('source spectral radiance must be finite and nonnegative')
    if any(
        not isfinite(value) or value < 0.0 or value > 1.0
        for row in self.background_transmittance
        for value in row
    ):
      raise ValueError('background transmittance must be finite and in [0, 1]')
    if self.optical_depth is not None and any(
        not isfinite(value) or value < 0.0
        for row in self.optical_depth
        for value in row
    ):
      raise ValueError('optical depth must be finite and nonnegative')
    for index, hit in enumerate(self.hit_mask):
      status = self.ray_status[index]
      validity_row = self.validity_mask[index]
      source_row = self.source_spectral_radiance[index]
      transmittance_row = self.background_transmittance[index]
      interval = None if self.plume_intersection_t_m is None else self.plume_intersection_t_m[index]
      if status.code.value != 'ok':
        if any(validity_row) or hit:
          raise ValueError('a failed ray must be invalid and cannot report a hit')
        if any(abs(value) > 1.0e-12 for value in source_row):
          raise ValueError('a failed ray must use zero placeholder source radiance')
        if any(abs(value - 1.0) > 1.0e-12 for value in transmittance_row):
          raise ValueError('a failed ray must use unit placeholder transmittance')
        if self.optical_depth is not None and any(
            abs(value) > 1.0e-12 for value in self.optical_depth[index]
        ):
          raise ValueError('a failed ray must use zero placeholder optical depth')
        if interval is not None:
          raise ValueError('a failed ray cannot have a plume intersection interval')
        continue
      if not all(validity_row):
        raise ValueError('an OK ray must mark all wavelengths valid')
      if hit:
        if self.plume_intersection_t_m is not None and interval is None:
          raise ValueError('a hit ray must have an intersection interval when intervals are returned')
        continue
      if any(abs(value) > 1.0e-12 for value in source_row):
        raise ValueError('a miss ray must have zero source radiance')
      if any(abs(value - 1.0) > 1.0e-12 for value in transmittance_row):
        raise ValueError('a miss ray must have unit transmittance')
      if self.optical_depth is not None and any(abs(value) > 1.0e-12 for value in self.optical_depth[index]):
        raise ValueError('a miss ray must have zero optical depth')
      if interval is not None:
        raise ValueError('a miss ray cannot have a plume intersection interval')
    return self
  ####
####


__all__ = (
  'SPECTRAL_RAY_TRANSFER_CAPABILITY',
  'SpectralRayTransferRequest',
  'SpectralRayTransferResult',
)
####
