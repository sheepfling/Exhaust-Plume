"""Reproducible view-state primitives shared by visualization consumers."""

from __future__ import annotations

import hashlib
import json
from enum import Enum
from math import isfinite
from typing import Any, Literal

from pydantic import Field, model_validator

from exhaust_plume.api.contracts import ProductResult, StrictFrozenModel

VISUALIZATION_SPEC_SCHEMA = 'plume.visualization.spec@1'


class AxisScale(str, Enum):
  LINEAR = 'LINEAR'
  LOG10 = 'LOG10'
####


class InvalidSamplePolicy(str, Enum):
  GAP = 'GAP'
  TRANSPARENT = 'TRANSPARENT'
  REJECT = 'REJECT'
####


class WavelengthDisplayUnit(str, Enum):
  M = 'm'
  UM = 'um'
  NM = 'nm'
####


class ViewSelection(StrictFrozenModel):
  """Linked indices used by product-specific views."""

  station_index: int | None = Field(default=None, ge=0)
  direction_index: int | None = Field(default=None, ge=0)
  ray_id: str | None = Field(default=None, min_length=1)
  wavelength_index: int | None = Field(default=None, ge=0)
  channel_id: str | None = Field(default=None, min_length=1)
  component_index: int | None = Field(default=None, ge=0)
####


class CameraSpec(StrictFrozenModel):
  """Explicit display camera settings for 3-D geometry views."""

  azimuth_deg: float = Field(allow_inf_nan=False)
  elevation_deg: float = Field(allow_inf_nan=False)
  distance_m: float = Field(gt=0., allow_inf_nan=False)
  target_m: tuple[float, float, float]

  @model_validator(mode='after')
  def validate_target(self) -> CameraSpec:
    if not all(isfinite(value) for value in self.target_m):
      raise ValueError('camera target must contain finite values')
    ####
    return self
  ####
####


class VisualizationSpec(StrictFrozenModel):
  """Source-bound, deterministic settings for one visualization view."""

  spec_schema: Literal['plume.visualization.spec@1'] = VISUALIZATION_SPEC_SCHEMA
  capability_id: str = Field(min_length=1)
  schema_version: str = Field(min_length=1)
  provider_id: str = Field(min_length=1)
  snapshot_id: str = Field(min_length=1)
  content_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
  frame_id: str = Field(min_length=1)
  view_kind: str = Field(pattern=r'^[a-z][a-z0-9_.-]*$')
  selection: ViewSelection = Field(default_factory=ViewSelection)
  x_scale: AxisScale = AxisScale.LINEAR
  y_scale: AxisScale = AxisScale.LINEAR
  invalid_sample_policy: InvalidSamplePolicy = InvalidSamplePolicy.GAP
  wavelength_display_unit: WavelengthDisplayUnit | None = None
  color_map: str = Field(default='viridis', min_length=1)
  mesh_radial_segments: int = Field(default=24, ge=3)
  camera: CameraSpec | None = None

  @classmethod
  def for_result(
    cls,
    result: ProductResult,
    *,
    view_kind: str,
    selection: ViewSelection | None = None,
    **overrides: Any,
  ) -> VisualizationSpec:
    """Bind a view spec to a validated standard API result."""

    envelope = result.envelope
    return cls(
      capability_id=envelope.capability_id,
      schema_version=envelope.schema_version,
      provider_id=str(envelope.provider_id),
      snapshot_id=str(envelope.snapshot_id),
      content_sha256=envelope.content_sha256,
      frame_id=envelope.frame.frame_id,
      view_kind=view_kind,
      selection=selection or ViewSelection(),
      **overrides,
    )
  ####

  def validate_for_result(self, result: ProductResult) -> None:
    """Reject reuse of a view spec against a different source result."""

    envelope = result.envelope
    expected = {
      'capability_id': envelope.capability_id,
      'schema_version': envelope.schema_version,
      'provider_id': str(envelope.provider_id),
      'snapshot_id': str(envelope.snapshot_id),
      'content_sha256': envelope.content_sha256,
      'frame_id': envelope.frame.frame_id,
    }
    actual = {
      'capability_id': self.capability_id,
      'schema_version': self.schema_version,
      'provider_id': self.provider_id,
      'snapshot_id': self.snapshot_id,
      'content_sha256': self.content_sha256,
      'frame_id': self.frame_id,
    }
    if actual != expected:
      raise ValueError('visualization spec is bound to a different product result')
    ####
  ####

  def canonical_json(self) -> str:
    """Return deterministic JSON for storage, comparison, or export."""

    return json.dumps(
      self.model_dump(mode='json'),
      sort_keys=True,
      separators=(',', ':'),
      ensure_ascii=True,
      allow_nan=False,
    )
  ####

  def digest_sha256(self) -> str:
    """Return the deterministic identity of this view configuration."""

    return hashlib.sha256(self.canonical_json().encode('utf-8')).hexdigest()
  ####
####


__all__ = (
  'AxisScale',
  'CameraSpec',
  'InvalidSamplePolicy',
  'VISUALIZATION_SPEC_SCHEMA',
  'ViewSelection',
  'VisualizationSpec',
  'WavelengthDisplayUnit',
)
