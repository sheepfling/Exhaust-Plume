"""Source-bound v1 result contracts for supporting spatial capabilities."""

from __future__ import annotations

from math import isfinite
from typing import Literal

import numpy as np
from pydantic import Field, field_validator, model_validator

from exhaust_plume.contracts.capability import (
  CapabilityId,
  SPATIAL_AXISYMMETRIC_ZONE_FIELD_CAPABILITY,
  SPATIAL_PROJECTED_AREA_CAPABILITY,
  SPATIAL_SUPPORT_CAPABILITY,
)
from exhaust_plume.contracts.common_v1 import ApiModel, ResultMetadata
from exhaust_plume.contracts.spatial import (
  AxisymmetricZoneField,
  ProjectedAreaCapability,
  SpatialSupport,
)


class SpatialSupportRequest(ApiModel):
  """Request the snapshot's declared support in its native output frame."""


class ProjectedAreaRequest(ApiModel):
  """Request the provider-declared reference area for this snapshot."""


class AxisymmetricZoneFieldRequest(ApiModel):
  """Request the finite axisymmetric zones retained by this exact snapshot."""


class AxisymmetricZoneData(ApiModel):
  """One finite axial/radial region with its declared state and annotations."""

  zone_id: str = Field(min_length=1)
  polygon_xr_m: tuple[tuple[float, float], ...] = Field(min_length=3)
  static_pressure_Pa: float = Field(gt=0.0)
  static_temperature_K: float = Field(gt=0.0)
  density_kgpm3: float = Field(gt=0.0)
  mach: float = Field(ge=0.0)
  phase: str = Field(min_length=1)
  cell_index: int = Field(ge=0)
  geometry_status: Literal['valid'] = 'valid'
  region_type: str | None = Field(default=None, min_length=1)
  region_label: str | None = Field(default=None, min_length=1)
  shock_angle_rad: float | None = None
  turn_angle_rad: float | None = None

  @field_validator('polygon_xr_m')
  @classmethod
  def validate_polygon_xr_m(
      cls,
      polygon: tuple[tuple[float, float], ...],
  ) -> tuple[tuple[float, float], ...]:
    if any(not isfinite(value) for point in polygon for value in point):
      raise ValueError('zone polygon coordinates must be finite')
    ####
    from exhaust_plume.geometry.polygons import validate_polygon

    if not validate_polygon(np.asarray(polygon, dtype=float)).is_valid:
      raise ValueError('zone polygon must be simple and non-degenerate')
    ####
    return polygon
  ####

  @field_validator('static_pressure_Pa', 'static_temperature_K', 'density_kgpm3', 'mach')
  @classmethod
  def validate_finite_state(cls, value: float) -> float:
    if not isfinite(value):
      raise ValueError('zone state values must be finite')
    ####
    return value
  ####

  @field_validator('shock_angle_rad', 'turn_angle_rad')
  @classmethod
  def validate_optional_angles(cls, value: float | None) -> float | None:
    if value is not None and not isfinite(value):
      raise ValueError('declared zone angles must be finite when supplied')
    ####
    return value
  ####
####


class AxisymmetricZoneFieldResult(ApiModel):
  """Finite zone field with exact provider, request, frame, and snapshot lineage."""

  metadata: ResultMetadata
  axis_definition: str = Field(min_length=1)
  zones: tuple[AxisymmetricZoneData, ...] = Field(min_length=1)

  @model_validator(mode='after')
  def validate_zone_field(self) -> 'AxisymmetricZoneFieldResult':
    if self.metadata.capability != SPATIAL_AXISYMMETRIC_ZONE_FIELD_CAPABILITY:
      raise ValueError(
        'axisymmetric zone result metadata must identify '
        'plume.spatial.axisymmetric-zone-field@1'
      )
    ####
    zone_ids = tuple(zone.zone_id for zone in self.zones)
    if len(zone_ids) != len(set(zone_ids)):
      raise ValueError('axisymmetric zone IDs must be unique within one field')
    ####
    return self
  ####
####


class SpatialSupportResult(ApiModel):
  """Conservative support bounds with exact provider and snapshot lineage."""

  metadata: ResultMetadata
  plume_frame_aabb_min_m: tuple[float, float, float]
  plume_frame_aabb_max_m: tuple[float, float, float]
  characteristic_extent_m: float = Field(gt=0.0)
  support_definition: str = Field(min_length=1)
  is_conservative: bool

  @model_validator(mode='after')
  def validate_support(self) -> 'SpatialSupportResult':
    if self.metadata.capability != SPATIAL_SUPPORT_CAPABILITY:
      raise ValueError('spatial support result metadata must identify plume.spatial.support@1')
    ####
    coordinates = (*self.plume_frame_aabb_min_m, *self.plume_frame_aabb_max_m)
    if any(not isfinite(value) for value in coordinates):
      raise ValueError('spatial support bounds must be finite')
    ####
    if any(
      lower > upper
      for lower, upper in zip(
        self.plume_frame_aabb_min_m,
        self.plume_frame_aabb_max_m,
        strict=True,
      )
    ):
      raise ValueError('spatial support minimum must not exceed maximum')
    ####
    if not isfinite(self.characteristic_extent_m):
      raise ValueError('characteristic_extent_m must be finite and positive')
    ####
    return self
  ####
####


class ProjectedAreaResult(ApiModel):
  """Reference projected area with exact provider and snapshot lineage."""

  metadata: ResultMetadata
  reference_area_m2: float = Field(gt=0.0)
  closed_zone_count: int = Field(ge=0)

  @model_validator(mode='after')
  def validate_projected_area(self) -> 'ProjectedAreaResult':
    if self.metadata.capability != SPATIAL_PROJECTED_AREA_CAPABILITY:
      raise ValueError('projected-area result metadata must identify plume.spatial.projected-area@1')
    ####
    if not isfinite(self.reference_area_m2):
      raise ValueError('reference_area_m2 must be finite and positive')
    ####
    return self
  ####
####


def bind_spatial_support_result(
    support: SpatialSupport,
    metadata: ResultMetadata,
) -> SpatialSupportResult:
  """Bind a legacy provider payload to caller-supplied exact result metadata."""

  if not isinstance(support, SpatialSupport):
    raise TypeError('support must be a SpatialSupport payload')
  ####
  if not isinstance(metadata, ResultMetadata):
    raise TypeError('metadata must be canonical ResultMetadata')
  ####
  if support.capability_id is not CapabilityId.SPATIAL_SUPPORT:
    raise ValueError('support payload must identify the spatial-support capability')
  ####
  if support.major_version != SPATIAL_SUPPORT_CAPABILITY.major:
    raise ValueError('support payload major version is not supported by the v1 result adapter')
  ####
  return SpatialSupportResult(
    metadata=metadata,
    plume_frame_aabb_min_m=support.plume_frame_aabb_min_m,
    plume_frame_aabb_max_m=support.plume_frame_aabb_max_m,
    characteristic_extent_m=support.characteristic_extent_m,
    support_definition=support.support_definition,
    is_conservative=support.is_conservative,
  )
####


def bind_axisymmetric_zone_field_result(
    field: AxisymmetricZoneField,
    metadata: ResultMetadata,
) -> AxisymmetricZoneFieldResult:
  """Bind retained finite zones to caller-supplied exact result metadata."""

  if not isinstance(field, AxisymmetricZoneField):
    raise TypeError('field must be an AxisymmetricZoneField payload')
  ####
  if not isinstance(metadata, ResultMetadata):
    raise TypeError('metadata must be canonical ResultMetadata')
  ####
  if field.capability_id is not CapabilityId.AXISYMMETRIC_ZONE_FIELD:
    raise ValueError('field payload must identify the axisymmetric-zone-field capability')
  ####
  if field.major_version != SPATIAL_AXISYMMETRIC_ZONE_FIELD_CAPABILITY.major:
    raise ValueError('field payload major version is not supported by the v1 result adapter')
  ####
  if not field.zones:
    raise ValueError('axisymmetric zone-field result requires at least one retained zone')
  ####
  return AxisymmetricZoneFieldResult(
    metadata=metadata,
    axis_definition=field.axis_definition,
    zones=tuple(
      AxisymmetricZoneData(
        zone_id=zone.zone_id,
        polygon_xr_m=tuple(
          (float(point[0]), float(point[1]))
          for point in zone.polygon_xr_m
        ),
        static_pressure_Pa=zone.static_pressure_Pa,
        static_temperature_K=zone.static_temperature_K,
        density_kgpm3=zone.density_kgpm3,
        mach=zone.mach,
        phase=zone.phase,
        cell_index=zone.cell_index,
        geometry_status='valid',
        region_type=zone.region_type,
        region_label=zone.region_label,
        shock_angle_rad=zone.shock_angle_rad,
        turn_angle_rad=zone.turn_angle_rad,
      )
      for zone in field.zones
    ),
  )
####


def bind_projected_area_result(
    projected_area: ProjectedAreaCapability,
    metadata: ResultMetadata,
) -> ProjectedAreaResult:
  """Bind a legacy provider payload to caller-supplied exact result metadata."""

  if not isinstance(projected_area, ProjectedAreaCapability):
    raise TypeError('projected_area must be a ProjectedAreaCapability payload')
  ####
  if not isinstance(metadata, ResultMetadata):
    raise TypeError('metadata must be canonical ResultMetadata')
  ####
  if projected_area.capability_id is not CapabilityId.PROJECTED_AREA:
    raise ValueError('projected-area payload must identify the projected-area capability')
  ####
  if projected_area.major_version != SPATIAL_PROJECTED_AREA_CAPABILITY.major:
    raise ValueError('projected-area payload major version is not supported by the v1 result adapter')
  ####
  return ProjectedAreaResult(
    metadata=metadata,
    reference_area_m2=projected_area.reference_area_m2,
    closed_zone_count=projected_area.closed_zone_count,
  )
####


__all__ = (
  'AxisymmetricZoneData',
  'AxisymmetricZoneFieldRequest',
  'AxisymmetricZoneFieldResult',
  'ProjectedAreaRequest',
  'ProjectedAreaResult',
  'SpatialSupportRequest',
  'SpatialSupportResult',
  'bind_axisymmetric_zone_field_result',
  'bind_projected_area_result',
  'bind_spatial_support_result',
)
