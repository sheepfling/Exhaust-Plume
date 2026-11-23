"""Source-bound renderer data for one computational plume-model lane."""

from __future__ import annotations

from enum import Enum
from math import isfinite
from typing import Literal, Mapping

from pydantic import Field, StrictBool, field_validator, model_validator

from exhaust_plume.contracts.capability import MODEL_LANE_VISUALIZATION_CAPABILITY
from exhaust_plume.contracts.common_v1 import (
  ApiModel,
  ApplicabilityReport,
  GeometryClaim,
  ResultMetadata,
)
from exhaust_plume.contracts.visual_v1 import VisualSectionedTubeRequest, VisualSectionedTubeResult
from exhaust_plume.contracts._validation import contains_boolean


class ModelVisualizationLaneId(str, Enum):
  BASIC_SHOCK_CELL = 'shock-cell-basic-v1'
  REDUCED_ORDER_SHOCK_TRAIN = 'shock-cell-reduced-order-v1'
  STRAIGHT_INTEGRAL = 'straight-integral-v1'
  CURVED_INTEGRAL = 'washed-integral-v1'
  PLANAR_MOC = 'planar-moc-primitives-v1'
####


class ModelLaneVisualizationRequest(ApiModel):
  """Request the retained fields and features associated with a visual result."""

  visual_request: VisualSectionedTubeRequest
####


class ModelLaneVisualizationClaims(ApiModel):
  """Lane-specific claim ceiling, separate from display geometry metadata."""

  model_fidelity: str = Field(min_length=1)
  validation_level: str = Field(min_length=1)
  geometry_claim: GeometryClaim
  production_claim_allowed: StrictBool
  claim_notes: tuple[str, ...] = ()

  @model_validator(mode='after')
  def validate_production_claim(self) -> 'ModelLaneVisualizationClaims':
    if self.production_claim_allowed and (
        self.validation_level != 'VALIDATED'
        or self.geometry_claim is not GeometryClaim.VALIDATED
    ):
      raise ValueError('production claims require validated evidence and validated geometry')
    ####
    return self
  ####
####


class ModelLaneSectionChannel(ApiModel):
  channel_id: str = Field(pattern=r'^[a-z0-9][a-z0-9_-]*$')
  semantic: str = Field(min_length=1)
  unit: str = Field(min_length=1)
  association: Literal['section'] = 'section'
  values: tuple[float, ...] = Field(min_length=2)
  uncertainties: tuple[float | None, ...] | None = None

  @field_validator('values', 'uncertainties', mode='before')
  @classmethod
  def reject_boolean_numeric_values(cls, value: object) -> object:
    if contains_boolean(value):
      raise ValueError('section channel numeric values must not be booleans')
    return value
  ####

  @model_validator(mode='after')
  def validate_values(self) -> 'ModelLaneSectionChannel':
    if any(not isfinite(value) for value in self.values):
      raise ValueError('section channel values must be finite')
    ####
    if self.uncertainties is not None:
      if len(self.uncertainties) != len(self.values):
        raise ValueError('section channel uncertainties must match values')
      ####
      if any(value is not None and (not isfinite(value) or value < 0.0) for value in self.uncertainties):
        raise ValueError('section channel uncertainties must be finite and nonnegative')
      ####
    ####
    return self
  ####
####


class ModelLanePath(ApiModel):
  path_id: str = Field(min_length=1)
  semantic: str = Field(min_length=1)
  points_m: tuple[tuple[float, float, float], ...] = Field(min_length=2)

  @field_validator('points_m', mode='before')
  @classmethod
  def reject_boolean_coordinates(cls, value: object) -> object:
    if contains_boolean(value):
      raise ValueError('path coordinates must not be booleans')
    return value
  ####

  @field_validator('points_m')
  @classmethod
  def validate_points(cls, value: tuple[tuple[float, float, float], ...]) -> tuple[tuple[float, float, float], ...]:
    if any(not isfinite(component) for point in value for component in point):
      raise ValueError('path coordinates must be finite')
    ####
    return value
  ####
####


class ModelLaneFieldChannel(ApiModel):
  semantic: str = Field(min_length=1)
  unit: str = Field(min_length=1)
  values: tuple[float | None, ...] = Field(min_length=1)
  uncertainties: tuple[float | None, ...] | None = None

  @field_validator('values', 'uncertainties', mode='before')
  @classmethod
  def reject_boolean_numeric_values(cls, value: object) -> object:
    if contains_boolean(value):
      raise ValueError('field channel numeric values must not be booleans')
    return value
  ####

  @model_validator(mode='after')
  def validate_values(self) -> 'ModelLaneFieldChannel':
    if any(value is not None and not isfinite(value) for value in self.values):
      raise ValueError('field channel values must be finite when present')
    ####
    if self.uncertainties is not None:
      if len(self.uncertainties) != len(self.values):
        raise ValueError('field uncertainties must match field values')
      ####
      if any(value is not None and (not isfinite(value) or value < 0.0) for value in self.uncertainties):
        raise ValueError('field uncertainties must be finite and nonnegative')
      ####
    ####
    return self
  ####
####


class ModelLaneField(ApiModel):
  field_id: str = Field(min_length=1)
  semantic: str = Field(min_length=1)
  coordinate_system: Literal['axial-radial-xr'] = 'axial-radial-xr'
  polygons_xr_m: tuple[tuple[tuple[float, float], ...], ...] = Field(min_length=1)
  channels: Mapping[str, ModelLaneFieldChannel] = Field(default_factory=dict)
  region_types: tuple[str | None, ...] = ()
  region_labels: tuple[str | None, ...] = ()

  @field_validator('polygons_xr_m', mode='before')
  @classmethod
  def reject_boolean_coordinates(cls, value: object) -> object:
    if contains_boolean(value):
      raise ValueError('field polygon coordinates must not be booleans')
    return value
  ####

  @field_validator('polygons_xr_m')
  @classmethod
  def validate_polygons(
      cls,
      value: tuple[tuple[tuple[float, float], ...], ...],
  ) -> tuple[tuple[tuple[float, float], ...], ...]:
    for polygon in value:
      if len(polygon) < 3:
        raise ValueError('field polygons require at least three vertices')
      ####
      if any(not isfinite(component) for point in polygon for component in point):
        raise ValueError('field polygon coordinates must be finite')
      ####
      twice_area = sum(
        polygon[index][0] * polygon[(index + 1) % len(polygon)][1]
        - polygon[(index + 1) % len(polygon)][0] * polygon[index][1]
        for index in range(len(polygon))
      )
      if abs(twice_area) <= 1.0e-18:
        raise ValueError('field polygons must have nonzero area')
      ####
    ####
    return value
  ####

  @field_validator('channels')
  @classmethod
  def validate_channel_ids(cls, value: Mapping[str, ModelLaneFieldChannel]) -> Mapping[str, ModelLaneFieldChannel]:
    if any(not channel_id or channel_id.strip() != channel_id for channel_id in value):
      raise ValueError('field channel IDs must be non-empty and trimmed')
    ####
    return dict(value)
  ####

  @model_validator(mode='after')
  def validate_alignment(self) -> 'ModelLaneField':
    count = len(self.polygons_xr_m)
    for channel_id, channel in self.channels.items():
      if len(channel.values) != count:
        raise ValueError(f'field channel {channel_id!r} must match polygon count')
      ####
    ####
    for name, values in (('region_types', self.region_types), ('region_labels', self.region_labels)):
      if values and len(values) != count:
        raise ValueError(f'{name} must match polygon count when supplied')
      ####
    ####
    return self
  ####
####


class ModelLaneVisualizationResult(ApiModel):
  """Complete renderer-neutral lane result with nested exact tube lineage."""

  metadata: ResultMetadata
  standardization_schema: Literal['plume.visual.model-lane@1'] = 'plume.visual.model-lane@1'
  lane_id: ModelVisualizationLaneId
  model_id: str = Field(min_length=1)
  model_version: str = Field(min_length=1)
  source_status: str = Field(min_length=1)
  applicability: ApplicabilityReport
  claims: ModelLaneVisualizationClaims
  visual_request_digest_sha256: str = Field(min_length=1)
  sectioned_tube: VisualSectionedTubeResult
  section_channels: tuple[ModelLaneSectionChannel, ...] = ()
  paths: tuple[ModelLanePath, ...] = ()
  fields: tuple[ModelLaneField, ...] = ()
  diagnostics: Mapping[str, bool | float | int | str | None] = Field(default_factory=dict)
  warnings: tuple[str, ...] = ()

  @field_validator('diagnostics')
  @classmethod
  def validate_diagnostics(cls, value: Mapping[str, bool | float | int | str | None]) -> Mapping[str, bool | float | int | str | None]:
    if any(not key for key in value):
      raise ValueError('diagnostic keys must not be empty')
    ####
    if any(isinstance(item, float) and not isfinite(item) for item in value.values()):
      raise ValueError('diagnostic values must be finite')
    ####
    return dict(value)
  ####

  @model_validator(mode='after')
  def validate_lineage_and_alignment(self) -> 'ModelLaneVisualizationResult':
    tube_metadata = self.sectioned_tube.metadata
    if self.metadata.capability != MODEL_LANE_VISUALIZATION_CAPABILITY:
      raise ValueError('model lane result metadata must identify plume.visual.model-lane@1')
    ####
    if tube_metadata.snapshot != self.metadata.snapshot:
      raise ValueError('model lane and sectioned-tube results must use the exact same snapshot')
    ####
    if tube_metadata.output_frame_id != self.metadata.output_frame_id:
      raise ValueError('model lane and sectioned-tube results must use the exact same output frame')
    ####
    if tube_metadata.request_digest_sha256 != self.visual_request_digest_sha256:
      raise ValueError('nested sectioned-tube result must bind the supplied visual request')
    ####
    if tube_metadata.provenance.provider_id != self.metadata.provenance.provider_id:
      raise ValueError('model lane and sectioned-tube provider identities must match')
    ####
    if (
        tube_metadata.provenance.provider_version != self.metadata.provenance.provider_version
        or tube_metadata.provenance.configuration_digest_sha256
        != self.metadata.provenance.configuration_digest_sha256
        or tube_metadata.provenance.model_lineage_id
        != self.metadata.provenance.model_lineage_id
    ):
      raise ValueError('model lane and sectioned-tube provider lineage must match')
    ####
    if self.metadata.claims != tube_metadata.claims or self.metadata.applicability != self.applicability:
      raise ValueError('model lane metadata must preserve the nested visual claims and applicability')
    ####
    if self.claims.geometry_claim is not self.metadata.claims.geometry:
      raise ValueError(
        'model lane geometry claim must match canonical result metadata'
      )
    ####
    if len({channel.channel_id for channel in self.section_channels}) != len(self.section_channels):
      raise ValueError('model lane section channel IDs must be unique')
    ####
    if {channel.channel_id for channel in self.section_channels} != set(self.sectioned_tube.channels):
      raise ValueError('model lane section channel metadata must match the nested tube channels')
    ####
    if any(len(channel.values) != len(self.sectioned_tube.sections) for channel in self.section_channels):
      raise ValueError('model lane section channels must match the nested section count')
    ####
    for channel in self.section_channels:
      if tuple(self.sectioned_tube.channels[channel.channel_id]) != channel.values:
        raise ValueError('model lane channel values must match the nested tube result')
      ####
    ####
    if len({path.path_id for path in self.paths}) != len(self.paths):
      raise ValueError('model lane path IDs must be unique')
    ####
    if len({field.field_id for field in self.fields}) != len(self.fields):
      raise ValueError('model lane field IDs must be unique')
    ####
    return self
  ####
####


__all__ = (
  'MODEL_LANE_VISUALIZATION_CAPABILITY',
  'ModelLaneField',
  'ModelLaneFieldChannel',
  'ModelLanePath',
  'ModelLaneSectionChannel',
  'ModelLaneVisualizationClaims',
  'ModelLaneVisualizationRequest',
  'ModelLaneVisualizationResult',
  'ModelVisualizationLaneId',
)
