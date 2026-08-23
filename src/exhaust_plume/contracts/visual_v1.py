"""Renderer-neutral sectioned-tube geometry contract, version 1."""

from __future__ import annotations

from enum import Enum
from math import isfinite, sqrt
import re
from typing import Mapping

from pydantic import Field, field_validator, model_validator

from exhaust_plume.contracts.capability import VISUAL_SECTIONED_TUBE_CAPABILITY
from exhaust_plume.contracts.common_v1 import (
  ApiModel,
  QuaternionXyzw,
  ResultMetadata,
  Vector3,
)

class LodProfile(str, Enum):
  PREVIEW = 'preview'
  STANDARD = 'standard'
  DETAILED = 'detailed'
####


class VisualChannelId(str, Enum):
  CORE_RADIUS_FRACTION = 'core_radius_fraction'
  EMISSION_WEIGHT = 'emission_weight'
  OPACITY_WEIGHT = 'opacity_weight'
  MIXING_WEIGHT = 'mixing_weight'
  SHOCK_WEIGHT = 'shock_weight'
  SHOCK_PHASE_RAD = 'shock_phase_rad'
  TURBULENCE_WEIGHT = 'turbulence_weight'
####


class VisualSampling(ApiModel):
  maximum_section_count: int = Field(ge=2)
  maximum_chord_error_m: float | None = Field(default=None, gt=0.0)
  maximum_axial_extent_m: float | None = Field(default=None, gt=0.0)
  lod_profile: LodProfile = LodProfile.STANDARD

  @field_validator('maximum_chord_error_m', 'maximum_axial_extent_m')
  @classmethod
  def validate_finite_limits(cls, value: float | None) -> float | None:
    if value is not None and not isfinite(value):
      raise ValueError('visual sampling limits must be finite')
    ####
    return value
  ####
####


_CHANNEL_NAME = re.compile(r'^[a-z0-9][a-z0-9_-]*$')
_NORMALIZED_CHANNELS = frozenset({
  VisualChannelId.CORE_RADIUS_FRACTION.value,
  VisualChannelId.EMISSION_WEIGHT.value,
  VisualChannelId.OPACITY_WEIGHT.value,
  VisualChannelId.MIXING_WEIGHT.value,
  VisualChannelId.SHOCK_WEIGHT.value,
  VisualChannelId.TURBULENCE_WEIGHT.value,
})


class VisualSectionedTubeRequest(ApiModel):
  output_frame_id: str = Field(min_length=1)
  sampling: VisualSampling
  requested_channels: tuple[str, ...] = ()
  include_visual_bounds: bool = True

  @field_validator('requested_channels')
  @classmethod
  def validate_channel_names(cls, value: tuple[str, ...]) -> tuple[str, ...]:
    if len(value) != len(set(value)):
      raise ValueError('requested channels must be unique')
    ####
    if any(not _CHANNEL_NAME.fullmatch(channel) for channel in value):
      raise ValueError('channel names must use lowercase letters, digits, underscores, or hyphens')
    ####
    return value
  ####
####


class VisualSection(ApiModel):
  """One oriented elliptical section in the requested output frame."""

  arc_length_m: float = Field(ge=0.0)
  center_m: Vector3 = Field(min_length=3, max_length=3)
  section_to_output_xyzw: QuaternionXyzw = Field(min_length=4, max_length=4)
  radius_major_m: float = Field(gt=0.0)
  radius_minor_m: float = Field(gt=0.0)

  @model_validator(mode='after')
  def validate_finite_geometry(self) -> 'VisualSection':
    values = (
      self.arc_length_m,
      *self.center_m,
      *self.section_to_output_xyzw,
      self.radius_major_m,
      self.radius_minor_m,
    )
    if not all(isfinite(value) for value in values):
      raise ValueError('visual section values must be finite')
    ####
    norm = sqrt(sum(component * component for component in self.section_to_output_xyzw))
    if abs(norm - 1.0) > 1.0e-6:
      raise ValueError('section quaternion must be unit length')
    ####
    return self
  ####
####


class VisualBounds(ApiModel):
  minimum_m: Vector3 = Field(min_length=3, max_length=3)
  maximum_m: Vector3 = Field(min_length=3, max_length=3)

  @model_validator(mode='after')
  def validate_bounds(self) -> 'VisualBounds':
    values = (*self.minimum_m, *self.maximum_m)
    if not all(isfinite(value) for value in values):
      raise ValueError('visual bounds must be finite')
    ####
    if any(high < low for low, high in zip(self.minimum_m, self.maximum_m, strict=True)):
      raise ValueError('visual bounds maximum must be greater than or equal to minimum')
    ####
    return self
  ####
####


class VisualTubeSummary(ApiModel):
  length_m: float = Field(ge=0.0)
  maximum_radius_m: float = Field(gt=0.0)
  nominal_divergence_angle_rad: float | None = None

  @model_validator(mode='after')
  def validate_summary(self) -> 'VisualTubeSummary':
    values = (self.length_m, self.maximum_radius_m)
    if not all(isfinite(value) for value in values):
      raise ValueError('visual summary values must be finite')
    ####
    if self.nominal_divergence_angle_rad is not None and not isfinite(self.nominal_divergence_angle_rad):
      raise ValueError('nominal_divergence_angle_rad must be finite')
    ####
    return self
  ####
####


class VisualSectionedTubeResult(ApiModel):
  metadata: ResultMetadata
  sections: tuple[VisualSection, ...] = Field(min_length=2)
  channels: Mapping[str, tuple[float, ...]] = Field(default_factory=dict)
  visual_bounds: VisualBounds | None = None
  summary: VisualTubeSummary

  @field_validator('channels')
  @classmethod
  def copy_channels(cls, value: Mapping[str, tuple[float, ...]]) -> Mapping[str, tuple[float, ...]]:
    return dict(value)
  ####

  @model_validator(mode='after')
  def validate_sections_and_channels(self) -> 'VisualSectionedTubeResult':
    if self.metadata.capability != VISUAL_SECTIONED_TUBE_CAPABILITY:
      raise ValueError('visual result metadata must identify plume.visual.sectioned-tube@1')
    ####
    arc_lengths = [section.arc_length_m for section in self.sections]
    if any(next_value <= value for value, next_value in zip(arc_lengths, arc_lengths[1:])):
      raise ValueError('section arc lengths must be strictly increasing')
    ####
    for first, second in zip(self.sections, self.sections[1:]):
      dot = sum(left * right for left, right in zip(
        first.section_to_output_xyzw,
        second.section_to_output_xyzw,
        strict=True,
      ))
      if dot < 0.0:
        raise ValueError('neighboring quaternions must use a continuous sign convention')
      ####
    ####
    section_count = len(self.sections)
    for channel_name, channel_values in self.channels.items():
      if not _CHANNEL_NAME.fullmatch(channel_name):
        raise ValueError('channel names must use lowercase letters, digits, underscores, or hyphens')
      ####
      if len(channel_values) != section_count:
        raise ValueError(f'channel {channel_name!r} length must equal section count')
      ####
      if not all(isfinite(value) for value in channel_values):
        raise ValueError(f'channel {channel_name!r} must contain finite values')
      ####
      if channel_name in _NORMALIZED_CHANNELS and any(value < 0.0 or value > 1.0 for value in channel_values):
        raise ValueError(f'normalized channel {channel_name!r} must be within [0, 1]')
      ####
    ####
    final_arc_length = self.sections[-1].arc_length_m
    if self.summary.length_m + 1.0e-9 < final_arc_length:
      raise ValueError('summary length must contain the final arc-length station')
    ####
    actual_max_radius = max(
      max(section.radius_major_m, section.radius_minor_m)
      for section in self.sections
    )
    if self.summary.maximum_radius_m + 1.0e-9 < actual_max_radius:
      raise ValueError('summary maximum radius must contain every section')
    ####
    if self.visual_bounds is not None:
      for section in self.sections:
        radius = max(section.radius_major_m, section.radius_minor_m)
        for axis in range(3):
          if section.center_m[axis] - radius < self.visual_bounds.minimum_m[axis] - 1.0e-9:
            raise ValueError('visual bounds do not contain a section cross-section')
          ####
          if section.center_m[axis] + radius > self.visual_bounds.maximum_m[axis] + 1.0e-9:
            raise ValueError('visual bounds do not contain a section cross-section')
          ####
        ####
      ####
    ####
    return self
  ####
####


# Short aliases retain the terminology used by the reference contract while the
# capability name remains the canonical public identifier.
VisualTubeRequest = VisualSectionedTubeRequest
VisualTubeSection = VisualSection
VisualTubeResult = VisualSectionedTubeResult


__all__ = (
  'LodProfile',
  'VISUAL_SECTIONED_TUBE_CAPABILITY',
  'VisualBounds',
  'VisualChannelId',
  'VisualSampling',
  'VisualSection',
  'VisualSectionedTubeRequest',
  'VisualSectionedTubeResult',
  'VisualTubeRequest',
  'VisualTubeResult',
  'VisualTubeSection',
  'VisualTubeSummary',
)
