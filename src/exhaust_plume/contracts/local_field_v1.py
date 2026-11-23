"""Point-query contract for provider-declared local spatial fields."""

from __future__ import annotations

from math import isfinite
from typing import Any, Literal

from pydantic import Field, StrictBool, field_validator, model_validator

from exhaust_plume.contracts.capability import SPATIAL_LOCAL_FIELD_CAPABILITY
from exhaust_plume.contracts.common_v1 import (
  ApiModel,
  ResultMetadata,
  SampleStatus,
  SampleStatusCode,
)
from exhaust_plume.contracts._validation import contains_boolean

LocalFieldSamplingMethod = Literal[
  'point-evaluation',
  'exact-node',
  'nearest-cell',
  'provider-interpolated',
]


class SpatialLocalFieldRequest(ApiModel):
  """Query selected provider-declared channels at ordered points in one frame."""

  coordinate_frame_id: str = Field(min_length=1)
  points_m: tuple[tuple[float, float, float], ...] = Field(min_length=1)
  field_ids: tuple[str, ...] = Field(min_length=1)
  allow_partial_results: StrictBool = False

  @field_validator('points_m', mode='before')
  @classmethod
  def reject_boolean_coordinates(cls, value: Any) -> Any:
    if contains_boolean(value):
      raise ValueError('local-field query coordinates must not be booleans')
    return value
  ####

  @field_validator('points_m')
  @classmethod
  def validate_points(
      cls,
      points: tuple[tuple[float, float, float], ...],
  ) -> tuple[tuple[float, float, float], ...]:
    if any(not isfinite(value) for point in points for value in point):
      raise ValueError('local-field query coordinates must be finite')
    return points
  ####

  @field_validator('field_ids')
  @classmethod
  def validate_field_ids(cls, field_ids: tuple[str, ...]) -> tuple[str, ...]:
    if any(not field_id.strip() for field_id in field_ids):
      raise ValueError('local-field IDs must not be blank')
    if len(field_ids) != len(set(field_ids)):
      raise ValueError('local-field IDs must be unique within a request')
    return field_ids
  ####
####


class SpatialLocalFieldChannel(ApiModel):
  """One named physical quantity sampled at each requested point."""

  field_id: str = Field(min_length=1)
  semantic: str = Field(min_length=1)
  unit: str = Field(min_length=1)
  sampling_method: LocalFieldSamplingMethod
  values: tuple[float | None, ...] = Field(min_length=1)
  sample_status: tuple[SampleStatus, ...] = Field(min_length=1)
  absolute_standard_uncertainty: tuple[float | None, ...] | None = None

  @field_validator('values', 'absolute_standard_uncertainty', mode='before')
  @classmethod
  def reject_boolean_samples(cls, value: Any) -> Any:
    if contains_boolean(value):
      raise ValueError('local-field numeric samples must not be booleans')
    return value
  ####

  @model_validator(mode='after')
  def validate_samples(self) -> 'SpatialLocalFieldChannel':
    sample_count = len(self.values)
    if len(self.sample_status) != sample_count:
      raise ValueError('local-field values and statuses must have matching lengths')
    if self.absolute_standard_uncertainty is not None and len(self.absolute_standard_uncertainty) != sample_count:
      raise ValueError('local-field uncertainty must match the value count')
    for index, (value, status) in enumerate(zip(self.values, self.sample_status, strict=True)):
      if value is not None and not isfinite(value):
        raise ValueError('local-field values must be finite when present')
      if status.code is SampleStatusCode.OK and value is None:
        raise ValueError('an OK local-field sample must contain a value')
      if status.code is not SampleStatusCode.OK and value is not None:
        raise ValueError('a failed local-field sample must not contain a value')
      if self.absolute_standard_uncertainty is not None:
        uncertainty = self.absolute_standard_uncertainty[index]
        if uncertainty is not None and (not isfinite(uncertainty) or uncertainty < 0.0):
          raise ValueError('local-field uncertainty must be finite and nonnegative')
        if value is None and uncertainty is not None:
          raise ValueError('a failed local-field sample must not contain uncertainty')
    return self
  ####
####


class SpatialLocalFieldResult(ApiModel):
  """Point samples with exact result lineage and explicit method per channel."""

  metadata: ResultMetadata
  coordinate_frame_id: str = Field(min_length=1)
  points_m: tuple[tuple[float, float, float], ...] = Field(min_length=1)
  field_ids: tuple[str, ...] = Field(min_length=1)
  channels: tuple[SpatialLocalFieldChannel, ...] = Field(min_length=1)

  @field_validator('points_m', mode='before')
  @classmethod
  def reject_boolean_coordinates(cls, value: Any) -> Any:
    if contains_boolean(value):
      raise ValueError('local-field result coordinates must not be booleans')
    return value
  ####

  @field_validator('points_m')
  @classmethod
  def validate_points(
      cls,
      points: tuple[tuple[float, float, float], ...],
  ) -> tuple[tuple[float, float, float], ...]:
    if any(not isfinite(value) for point in points for value in point):
      raise ValueError('local-field result coordinates must be finite')
    return points
  ####

  @model_validator(mode='after')
  def validate_result(self) -> 'SpatialLocalFieldResult':
    if self.metadata.capability != SPATIAL_LOCAL_FIELD_CAPABILITY:
      raise ValueError('local-field metadata must identify plume.spatial.local-field@1')
    if self.metadata.output_frame_id != self.coordinate_frame_id:
      raise ValueError('local-field output frame must match coordinate_frame_id')
    if len(self.field_ids) != len(set(self.field_ids)):
      raise ValueError('local-field result IDs must be unique')
    channel_ids = tuple(channel.field_id for channel in self.channels)
    if channel_ids != self.field_ids:
      raise ValueError('local-field channel IDs must match field_ids in order')
    if any(len(channel.values) != len(self.points_m) for channel in self.channels):
      raise ValueError('each local-field channel must have one sample per query point')
    return self
  ####
####


__all__ = (
  'LocalFieldSamplingMethod',
  'SpatialLocalFieldChannel',
  'SpatialLocalFieldRequest',
  'SpatialLocalFieldResult',
)
