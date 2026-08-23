"""Visual sectioned-tube and conservative-support plume products."""

from __future__ import annotations

from math import isclose, isfinite, sqrt
from typing import Literal

from pydantic import Field, field_validator, model_validator

from exhaust_plume.products._base import (
    Aabb3,
    ContractModel,
    ProductMetadata,
    SPATIAL_CONSERVATIVE_SUPPORT_V1,
    VISUAL_SECTIONED_TUBE_V1,
    Vector3,
    normalizeFiniteSequence,
    normalizeVector3,
)


class VisualFeatureChannel(ContractModel):
  """One named station-wise visual or diagnostic channel."""

  name: str = Field(min_length=1)
  unit: str = Field(min_length=1)
  meaning: str = Field(min_length=1)
  values: tuple[float, ...] = Field(min_length=2)
  interpolation: Literal['linear', 'step'] = 'linear'

  @field_validator('values', mode='before')
  @classmethod
  def normalizeValues(cls, value: object) -> tuple[float, ...]:
    values = normalizeFiniteSequence(value, name='feature-channel value')
    if any(not isfinite(item) for item in values):
      raise ValueError('Feature-channel values must be finite.')
    ####
    return values
  ####
####


class ConservativeSupportProduct(ContractModel):
  """Conservative spatial support independent of visual rendering geometry."""

  metadata: ProductMetadata
  bounds: Aabb3

  @model_validator(mode='after')
  def validateCapability(self) -> ConservativeSupportProduct:
    if self.metadata.capability != SPATIAL_CONSERVATIVE_SUPPORT_V1:
      raise ValueError(
          f'Expected capability {SPATIAL_CONSERVATIVE_SUPPORT_V1}. '
          f'Got:{self.metadata.capability}'
      )
    ####
    return self
  ####
####


class SectionedTubeProduct(ContractModel):
  """Centerline sections for visualization, support, and coarse scene composition.

  The product is intentionally not a radiometric claim. Named feature channels
  may carry provider-derived quantities, but every channel declares its unit
  and surrogate meaning.
  """

  metadata: ProductMetadata
  centerline_m: tuple[Vector3, ...] = Field(min_length=2)
  tangents_unit: tuple[Vector3, ...] = Field(min_length=2)
  normals_unit: tuple[Vector3, ...] = Field(min_length=2)
  binormals_unit: tuple[Vector3, ...] = Field(min_length=2)
  semi_major_axis_m: tuple[float, ...] = Field(min_length=2)
  semi_minor_axis_m: tuple[float, ...] = Field(min_length=2)
  bounds: Aabb3
  geometry_role: Literal['visualization', 'conservative-support'] = 'visualization'
  feature_channels: tuple[VisualFeatureChannel, ...] = ()

  @field_validator(
      'centerline_m',
      'tangents_unit',
      'normals_unit',
      'binormals_unit',
      mode='before',
  )
  @classmethod
  def normalizeVectors(cls, value: object) -> tuple[Vector3, ...]:
    try:
      return tuple(normalizeVector3(item, name='section vector') for item in value)  # type: ignore[arg-type]
    except TypeError as exc:
      raise ValueError('Expected a sequence of finite three-vectors.') from exc
    ####
  ####

  @field_validator('semi_major_axis_m', 'semi_minor_axis_m', mode='before')
  @classmethod
  def normalizeAxes(cls, value: object) -> tuple[float, ...]:
    values = normalizeFiniteSequence(value, name='section axis')
    if any(not isfinite(item) or item <= 0. for item in values):
      raise ValueError('Section axes must be finite and positive.')
    ####
    return values
  ####

  @model_validator(mode='after')
  def validateProduct(self) -> SectionedTubeProduct:
    if self.metadata.capability != VISUAL_SECTIONED_TUBE_V1:
      raise ValueError(
          f'Expected capability {VISUAL_SECTIONED_TUBE_V1}. '
          f'Got:{self.metadata.capability}'
      )
    ####
    count = len(self.centerline_m)
    for name, values in (
        ('tangents_unit', self.tangents_unit),
        ('normals_unit', self.normals_unit),
        ('binormals_unit', self.binormals_unit),
        ('semi_major_axis_m', self.semi_major_axis_m),
        ('semi_minor_axis_m', self.semi_minor_axis_m),
    ):
      if len(values) != count:
        raise ValueError(f'Expected `{name}` to have {count} entries. Got:{len(values)}')
      ####
    ####
    for index, (tangent, normal, binormal) in enumerate(
        zip(self.tangents_unit, self.normals_unit, self.binormals_unit)
    ):
      for name, vector in (
          ('tangent', tangent),
          ('normal', normal),
          ('binormal', binormal),
      ):
        magnitude = sqrt(sum(component * component for component in vector))
        if not isclose(magnitude, 1., rel_tol=1.e-7, abs_tol=1.e-9):
          raise ValueError(f'Section {index} {name} is not unit length:{magnitude}')
        ####
      ####
      if not isclose(sum(a * b for a, b in zip(tangent, normal)), 0., abs_tol=1.e-8):
        raise ValueError(f'Section {index} tangent and normal are not orthogonal.')
      ####
      if not isclose(sum(a * b for a, b in zip(tangent, binormal)), 0., abs_tol=1.e-8):
        raise ValueError(f'Section {index} tangent and binormal are not orthogonal.')
      ####
      if not isclose(sum(a * b for a, b in zip(normal, binormal)), 0., abs_tol=1.e-8):
        raise ValueError(f'Section {index} normal and binormal are not orthogonal.')
      ####
    ####
    for index, (major, minor) in enumerate(zip(self.semi_major_axis_m, self.semi_minor_axis_m)):
      if major < minor:
        raise ValueError(f'Expected semi-major axis >= semi-minor axis at section {index}.')
      ####
    ####
    names = tuple(channel.name for channel in self.feature_channels)
    if len(set(names)) != len(names):
      raise ValueError('Visual feature-channel names must be unique.')
    ####
    for channel in self.feature_channels:
      if len(channel.values) != count:
        raise ValueError(
            f'Feature channel {channel.name!r} has {len(channel.values)} values; '
            f'expected {count}.'
        )
      ####
    ####
    for index, (center, normal, binormal, major, minor) in enumerate(zip(
        self.centerline_m,
        self.normals_unit,
        self.binormals_unit,
        self.semi_major_axis_m,
        self.semi_minor_axis_m,
    )):
      extents = tuple(
          sqrt((major * normal[axis]) ** 2 + (minor * binormal[axis]) ** 2)
          for axis in range(3)
      )
      for axis in range(3):
        minimum = center[axis] - extents[axis]
        maximum = center[axis] + extents[axis]
        if minimum < self.bounds.minimum_m[axis] - 1.e-9:
          raise ValueError(f'Bounds do not enclose section {index} minimum on axis {axis}.')
        ####
        if maximum > self.bounds.maximum_m[axis] + 1.e-9:
          raise ValueError(f'Bounds do not enclose section {index} maximum on axis {axis}.')
        ####
      ####
    ####
    return self
  ####
####


_WORKFLOW_EXPORTS = frozenset({
  'VisualMesh',
  'build_sectioned_tube_mesh',
  'evaluate_nozzle_geometry_visual',
  'evaluate_shock_cell_visual',
  'evaluate_visual_definition',
  'load_straight_visual_definition',
  'render_visual_preview',
  'visual_definition_from_shock_cells',
  'visual_definition_from_zone_results',
  'write_straight_visual_asset',
  'write_visual_mesh_json',
  'write_visual_obj',
  'write_visual_result_json',
})


def __getattr__(name: str) -> object:
  """Lazily preserve the pre-contract workflow module surface."""

  if name in _WORKFLOW_EXPORTS:
    from exhaust_plume.products import workflow_visual

    return getattr(workflow_visual, name)
  raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
