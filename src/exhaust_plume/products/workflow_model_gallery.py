"""Static evaluation galleries for the five standardized model lanes.

The strict product gallery consumes public ``ProductResult`` objects.  Model
lane bundles are deliberately a separate evaluation surface because they also
retain field polygons, named paths, and lane-specific promotion metadata.
This module renders those additional diagnostics without turning them into a
new product contract or inferring missing physical features.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
import json
from math import cos, isfinite, pi, sin
from pathlib import Path
import re
from collections.abc import Mapping, Sequence
import textwrap
from typing import Any

from exhaust_plume.api import AxisScale
from exhaust_plume.contracts.common_v1 import canonical_digest
from exhaust_plume.contracts.model_lane_visualization_v1 import ModelLaneVisualizationResult
from exhaust_plume.products.model_visualization import (
  MODEL_VISUALIZATION_LANES,
  ModelVisualField,
  ModelVisualPath,
  ModelVisualizationLane,
  StandardizedModelVisualization,
  standardize_model_lane_visualization_result,
)
from exhaust_plume.validation.visual_comparisons import (
  VISUAL_FEATURE_COMPARISON_OPERATOR_ID,
  VISUAL_FEATURE_SERIES_SCHEMA,
)

__all__ = (
  'MODEL_GALLERY_MANIFEST_SCHEMA',
  'MODEL_GALLERY_SET_MANIFEST_SCHEMA',
  'MODEL_GALLERY_SPEC_SCHEMA',
  'ModelGalleryArtifact',
  'ModelVisualizationGalleryManifest',
  'ModelVisualizationGallerySetManifest',
  'ModelVisualizationGallerySpec',
  'render_model_visualization_gallery',
  'render_model_visualization_gallery_set',
  'write_model_gallery_manifest',
  'write_model_gallery_set_manifest',
)

MODEL_GALLERY_MANIFEST_SCHEMA = 'plume.visualization.model-gallery@1'
MODEL_GALLERY_SET_MANIFEST_SCHEMA = 'plume.visualization.model-gallery-set@1'
MODEL_GALLERY_SPEC_SCHEMA = 'plume.visualization.model-spec@1'
_HASH = re.compile(r'^[0-9a-f]{64}$')
_VIEW_KIND = re.compile(r'^model\.[a-z][a-z0-9_.-]*$')


@dataclass(frozen=True, slots=True)
class ModelVisualizationGallerySpec:
  """Deterministic view state bound to one standardized model bundle."""

  bundle_digest_sha256: str
  view_kind: str = 'model.gallery'
  station_index: int | None = None
  field_id: str | None = None
  field_channel_id: str | None = None
  path_ids: tuple[str, ...] = ()
  x_scale: AxisScale = AxisScale.LINEAR
  y_scale: AxisScale = AxisScale.LINEAR
  color_map: str = 'viridis'
  radial_segments: int = 24
  axial_station_fractions: tuple[float, ...] = (0.25, 0.5, 0.75)
  spatial_bounds_m: tuple[
    tuple[float, float],
    tuple[float, float],
    tuple[float, float],
  ] | None = None
  source_result_digest_sha256: str | None = None

  def __post_init__(self) -> None:
    if not isinstance(self.bundle_digest_sha256, str) or not _HASH.fullmatch(self.bundle_digest_sha256):
      raise ValueError('bundle_digest_sha256 must be a lowercase SHA-256 digest')
    ####
    if self.source_result_digest_sha256 is not None and not _HASH.fullmatch(self.source_result_digest_sha256):
      raise ValueError('source_result_digest_sha256 must be a lowercase SHA-256 digest when supplied')
    ####
    if not _VIEW_KIND.fullmatch(self.view_kind):
      raise ValueError('view_kind must start with model. and contain a valid name')
    ####
    if self.station_index is not None:
      if isinstance(self.station_index, bool) or not isinstance(self.station_index, int) or self.station_index < 0:
        raise ValueError('station_index must be a nonnegative integer or None')
      ####
    ####
    if self.field_id is not None and not self.field_id:
      raise ValueError('field_id must not be empty')
    ####
    if self.field_channel_id is not None:
      if not self.field_channel_id:
        raise ValueError('field_channel_id must not be empty')
      ####
      if self.field_id is None:
        raise ValueError('field_channel_id requires field_id')
      ####
    ####
    if not isinstance(self.x_scale, AxisScale) or not isinstance(self.y_scale, AxisScale):
      raise TypeError('x_scale and y_scale must be AxisScale values')
    ####
    if not self.color_map:
      raise ValueError('color_map must not be empty')
    ####
    if isinstance(self.radial_segments, bool) or not isinstance(self.radial_segments, int):
      raise TypeError('radial_segments must be an integer')
    ####
    if self.radial_segments < 3:
      raise ValueError('radial_segments must be at least three')
    ####
    try:
      fractions = tuple(float(value) for value in self.axial_station_fractions)
    except (TypeError, ValueError) as error:
      raise ValueError(
        'axial_station_fractions must be unique values strictly between zero and one'
      ) from error
    ####
    if (
      not fractions
      or any(not isfinite(value) or not 0.0 < value < 1.0 for value in fractions)
      or len(fractions) != len(set(fractions))
    ):
      raise ValueError(
        'axial_station_fractions must be unique values strictly between zero and one'
      )
    ####
    object.__setattr__(self, 'axial_station_fractions', fractions)
    ####
    if self.spatial_bounds_m is not None:
      try:
        bounds = tuple(
          tuple(float(value) for value in axis_bounds)
          for axis_bounds in self.spatial_bounds_m
        )
      except (TypeError, ValueError) as error:
        raise ValueError(
          'spatial_bounds_m must contain three finite increasing intervals'
        ) from error
      ####
      if (
        len(bounds) != 3
        or any(len(axis_bounds) != 2 for axis_bounds in bounds)
        or any(
          not isfinite(value)
          for axis_bounds in bounds
          for value in axis_bounds
        )
        or any(lower >= upper for lower, upper in bounds)
      ):
        raise ValueError(
          'spatial_bounds_m must contain three finite increasing intervals'
        )
      ####
      object.__setattr__(self, 'spatial_bounds_m', bounds)
    ####
    paths = tuple(str(path_id) for path_id in self.path_ids)
    if any(not path_id for path_id in paths):
      raise ValueError('path_ids must not contain empty IDs')
    ####
    if len(paths) != len(set(paths)):
      raise ValueError('path_ids must be unique')
    ####
    object.__setattr__(self, 'path_ids', paths)
  ####

  @classmethod
  def for_bundle(
    cls,
    bundle: StandardizedModelVisualization,
      *,
      source_result_digest_sha256: str | None = None,
    **overrides: Any,
  ) -> ModelVisualizationGallerySpec:
    """Create a view spec bound to the exact serialized bundle."""

    if not isinstance(bundle, StandardizedModelVisualization):
      raise TypeError('bundle must be StandardizedModelVisualization')
    ####
    defaults: dict[str, Any] = {}
    if bundle.fields:
      defaults['field_id'] = bundle.fields[0].field_id
      if bundle.fields[0].channels:
        defaults['field_channel_id'] = next(iter(bundle.fields[0].channels))
      ####
    ####
    defaults.update(overrides)
    return cls(
      bundle_digest_sha256=bundle.digest_sha256(),
      source_result_digest_sha256=source_result_digest_sha256,
      **defaults,
    )
  ####

  def validate_for_bundle(
      self,
      bundle: StandardizedModelVisualization,
      *,
      source_result_digest_sha256: str | None = None,
  ) -> None:
    """Reject reuse of a model view spec against another bundle."""

    if not isinstance(bundle, StandardizedModelVisualization):
      raise TypeError('bundle must be StandardizedModelVisualization')
    ####
    if self.bundle_digest_sha256 != bundle.digest_sha256():
      raise ValueError('model visualization spec is bound to a different bundle')
    ####
    if self.source_result_digest_sha256 != source_result_digest_sha256:
      raise ValueError('model visualization spec is bound to a different source result')
    ####
    if self.spatial_bounds_m is not None:
      vertices, _faces, _face_sections = _mesh(bundle, self.radial_segments)
      display_points = (
        *vertices,
        *(
          tuple(float(value) for value in section.center_m)
          for section in bundle.sectioned_tube.sections
        ),
        *(
          tuple(float(value) for value in point)
          for path in bundle.paths
          for point in path.points_m
        ),
        *(
          (float(x), float(radius), 0.0)
          for field in bundle.fields
          for polygon in field.polygons_xr_m
          for x, radius in polygon
        ),
      )
      if any(
        point[axis] < self.spatial_bounds_m[axis][0]
        or point[axis] > self.spatial_bounds_m[axis][1]
        for point in display_points
        for axis in range(3)
      ):
        raise ValueError('spatial_bounds_m must enclose all bundle geometry')
      ####
    ####
  ####

  def model_dump(self) -> dict[str, Any]:
    return {
      'spec_schema': MODEL_GALLERY_SPEC_SCHEMA,
      'bundle_digest_sha256': self.bundle_digest_sha256,
      'source_result_digest_sha256': self.source_result_digest_sha256,
      'view_kind': self.view_kind,
      'station_index': self.station_index,
      'field_id': self.field_id,
      'field_channel_id': self.field_channel_id,
      'path_ids': list(self.path_ids),
      'x_scale': self.x_scale.value,
      'y_scale': self.y_scale.value,
      'color_map': self.color_map,
      'radial_segments': self.radial_segments,
      'axial_station_fractions': list(self.axial_station_fractions),
      'spatial_bounds_m': (
        None
        if self.spatial_bounds_m is None
        else [list(axis_bounds) for axis_bounds in self.spatial_bounds_m]
      ),
    }
  ####

  def canonical_json(self) -> str:
    return json.dumps(
      self.model_dump(),
      sort_keys=True,
      separators=(',', ':'),
      ensure_ascii=True,
      allow_nan=False,
    )
  ####

  def digest_sha256(self) -> str:
    return canonical_digest(self.model_dump())
  ####
####


@dataclass(frozen=True, slots=True)
class ModelGalleryArtifact:
  """One file emitted by the model-lane gallery."""

  view_id: str
  path: str
  mime_type: str

  def model_dump(self) -> dict[str, str]:
    return {
      'view_id': self.view_id,
      'path': self.path,
      'mime_type': self.mime_type,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class ModelVisualizationGalleryManifest:
  """Bundle-bound manifest for a model-lane evaluation gallery."""

  schema: str
  lane_id: str
  spec: ModelVisualizationGallerySpec
  source: dict[str, Any]
  artifacts: tuple[ModelGalleryArtifact, ...]
  guardrails: tuple[str, ...]
  manifest_path: Path

  def model_dump(self) -> dict[str, Any]:
    return {
      'schema': self.schema,
      'lane_id': self.lane_id,
      'spec': self.spec.model_dump(),
      'spec_digest_sha256': self.spec.digest_sha256(),
      'source': dict(self.source),
      'artifacts': [artifact.model_dump() for artifact in self.artifacts],
      'guardrails': list(self.guardrails),
    }
  ####

  def canonical_json(self) -> str:
    return json.dumps(
      self.model_dump(),
      sort_keys=True,
      indent=2,
      ensure_ascii=True,
      allow_nan=False,
    ) + '\n'
  ####
####


@dataclass(frozen=True, slots=True)
class ModelVisualizationGallerySetManifest:
  """Top-level manifest for an independent gallery of all five model lanes."""

  schema: str
  lane_manifests: tuple[ModelVisualizationGalleryManifest, ...]
  guardrails: tuple[str, ...]
  comparison_intake: dict[str, Any]
  manifest_path: Path

  def model_dump(self) -> dict[str, Any]:
    lanes: list[dict[str, Any]] = []
    for manifest in self.lane_manifests:
      prefix = Path(manifest.lane_id)
      lanes.append({
        'lane_id': manifest.lane_id,
        'bundle_digest_sha256': manifest.source['bundle_digest_sha256'],
        'manifest_path': (prefix / manifest.manifest_path.name).as_posix(),
        'artifacts': [
          {
            **artifact.model_dump(),
            'path': (prefix / artifact.path).as_posix(),
          }
          for artifact in manifest.artifacts
        ],
        'source': dict(manifest.source),
        'spec_digest_sha256': manifest.spec.digest_sha256(),
      })
    ####
    return {
      'schema': self.schema,
      'lane_ids': [lane['lane_id'] for lane in lanes],
      'lane_count': len(lanes),
      'lanes': lanes,
      'comparison_intake': dict(self.comparison_intake),
      'guardrails': list(self.guardrails),
    }
  ####

  def canonical_json(self) -> str:
    return json.dumps(
      self.model_dump(),
      sort_keys=True,
      indent=2,
      ensure_ascii=True,
      allow_nan=False,
    ) + '\n'
  ####
####


def _source(
    bundle: StandardizedModelVisualization,
    source_result: ModelLaneVisualizationResult | None = None,
) -> dict[str, Any]:
  source = {
    'schema': bundle.schema,
    'bundle_digest_sha256': bundle.digest_sha256(),
    'lane_id': bundle.lane_id,
    'model': {
      'id': bundle.model_id,
      'version': bundle.model_version,
    },
    'frame_id': bundle.frame_id,
    'source_status': bundle.source_status,
    'applicability': {
      'status': bundle.applicability_status.value,
      'reasons': list(bundle.applicability_reasons),
    },
    'claims': bundle.claims.model_dump(),
    'diagnostics': dict(bundle.diagnostics),
    'warnings': list(bundle.warnings),
  }
  if source_result is not None:
    metadata = source_result.metadata
    source['source_result'] = {
      'capability_id': metadata.capability.wire_id,
      'result_id': metadata.result_id,
      'result_digest_sha256': canonical_digest(source_result),
      'request_digest_sha256': metadata.request_digest_sha256,
      'visual_request_digest_sha256': source_result.visual_request_digest_sha256,
      'snapshot_id': metadata.snapshot.snapshot_id,
      'time_s': metadata.snapshot.time_s,
      'output_frame_id': metadata.output_frame_id,
      'provider_id': metadata.provenance.provider_id,
      'provider_version': metadata.provenance.provider_version,
      'configuration_digest_sha256': metadata.provenance.configuration_digest_sha256,
    }
  ####
  return source
####


def _write_station_inspector(
  bundle: StandardizedModelVisualization,
  spec: ModelVisualizationGallerySpec,
  station_index: int,
  selected_paths: tuple[ModelVisualPath, ...],
  output: Path,
  source_result_digest_sha256: str | None = None,
) -> ModelGalleryArtifact:
  """Write the exact selected station as a renderer-neutral view artifact.

  The PNG views show the station in context, but a renderer should not have
  to recover the selected section values from pixels.  This artifact keeps
  the section pose, radii, every declared section channel, and the selected
  path identities together with both source and view-spec digests.
  """

  section = bundle.sectioned_tube.sections[station_index]
  channel_values = []
  for channel in bundle.section_channels:
    channel_values.append({
      'channel_id': channel.channel_id,
      'semantic': channel.semantic,
      'unit': channel.unit,
      'value': channel.values[station_index],
      'uncertainty': (
        None
        if channel.uncertainties is None
        else channel.uncertainties[station_index]
      ),
    })
  ####
  payload = {
    'schema': 'plume.visualization.model-station-inspector@1',
    'lane_id': bundle.lane_id,
    'bundle_digest_sha256': bundle.digest_sha256(),
    'source_result_digest_sha256': source_result_digest_sha256,
    'spec_digest_sha256': spec.digest_sha256(),
    'station_index': station_index,
    'section': section.model_dump(mode='json'),
    'section_channels': channel_values,
    'selected_path_ids': [path.path_id for path in selected_paths],
    'claims': bundle.claims.model_dump(),
    'guardrails': [
      'station values are copied from the declared model bundle; no values are inferred from rendered pixels',
      'missing field or channel values remain missing and are never converted to zero',
      'the station inspector does not widen the source lane claim ceiling',
    ],
  }
  ####
  path = output / 'model_station_inspector.json'
  path.write_text(
    json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False)
    + '\n',
    encoding='utf-8',
  )
  return ModelGalleryArtifact(
    'model.station-inspector',
    path.name,
    'application/json',
  )
####


def _selected_station(bundle: StandardizedModelVisualization, spec: ModelVisualizationGallerySpec) -> int:
  count = len(bundle.sectioned_tube.sections)
  selected = count // 2 if spec.station_index is None else spec.station_index
  if selected >= count:
    raise IndexError(f'station_index out of range: {selected}')
  ####
  return selected
####


def _selected_field(bundle: StandardizedModelVisualization, spec: ModelVisualizationGallerySpec) -> ModelVisualField | None:
  if not bundle.fields:
    if spec.field_id is not None or spec.field_channel_id is not None:
      raise KeyError('the bundle has no fields to select')
    ####
    return None
  ####
  if spec.field_id is None:
    selected = bundle.fields[0]
  else:
    matching = tuple(field for field in bundle.fields if field.field_id == spec.field_id)
    if not matching:
      raise KeyError(f'unknown field_id {spec.field_id!r}')
    ####
    selected = matching[0]
  ####
  if spec.field_channel_id is not None and spec.field_channel_id not in selected.channels:
    raise KeyError(f'unknown field channel {spec.field_channel_id!r} for {selected.field_id!r}')
  ####
  return selected
####


def _selected_paths(bundle: StandardizedModelVisualization, spec: ModelVisualizationGallerySpec) -> tuple[ModelVisualPath, ...]:
  if not spec.path_ids:
    return bundle.paths
  ####
  by_id = {path.path_id: path for path in bundle.paths}
  missing = tuple(path_id for path_id in spec.path_ids if path_id not in by_id)
  if missing:
    raise KeyError(f'unknown model visualization path(s): {missing!r}')
  ####
  return tuple(by_id[path_id] for path_id in spec.path_ids)
####


def _rotate_vector(quaternion: Sequence[float], vector: Sequence[float]) -> tuple[float, float, float]:
  x, y, z, w = (float(value) for value in quaternion)
  vx, vy, vz = (float(value) for value in vector)
  tx = 2.0 * (y * vz - z * vy)
  ty = 2.0 * (z * vx - x * vz)
  tz = 2.0 * (x * vy - y * vx)
  return (
    vx + w * tx + y * tz - z * ty,
    vy + w * ty + z * tx - x * tz,
    vz + w * tz + x * ty - y * tx,
  )
####


def _mesh(bundle: StandardizedModelVisualization, radial_segments: int) -> tuple[tuple[tuple[float, float, float], ...], tuple[tuple[int, int, int], ...], tuple[int, ...]]:
  sections = bundle.sectioned_tube.sections
  vertices: list[tuple[float, float, float]] = []
  faces: list[tuple[int, int, int]] = []
  face_sections: list[int] = []
  for section in sections:
    for radial_index in range(radial_segments):
      angle = 2.0 * pi * radial_index / radial_segments
      offset = _rotate_vector(
        section.section_to_output_xyzw,
        (section.radius_major_m * cos(angle), section.radius_minor_m * sin(angle), 0.0),
      )
      vertices.append((
        float(section.center_m[0] + offset[0]),
        float(section.center_m[1] + offset[1]),
        float(section.center_m[2] + offset[2]),
      ))
    ####
  ####
  for section_index in range(len(sections) - 1):
    first = section_index * radial_segments
    second = (section_index + 1) * radial_segments
    for radial_index in range(radial_segments):
      next_index = (radial_index + 1) % radial_segments
      a, b, c, d = first + radial_index, first + next_index, second + radial_index, second + next_index
      faces.extend(((a, c, b), (b, c, d)))
      face_sections.extend((section_index, section_index))
    ####
  ####
  return tuple(vertices), tuple(faces), tuple(face_sections)
####


def _bounds(points: Sequence[tuple[float, float, float]]) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
  if not points:
    return (0.0, 0.0, 0.0), (1.0, 1.0, 1.0)
  ####
  lower = (
    min(point[0] for point in points),
    min(point[1] for point in points),
    min(point[2] for point in points),
  )
  upper = (
    max(point[0] for point in points),
    max(point[1] for point in points),
    max(point[2] for point in points),
  )
  return lower, upper
####


def _set_3d_bounds(
  axis: Any,
  points: Sequence[tuple[float, float, float]],
  spatial_bounds_m: tuple[
    tuple[float, float],
    tuple[float, float],
    tuple[float, float],
  ] | None = None,
) -> None:
  if spatial_bounds_m is None:
    lower, upper = _bounds(points)
  else:
    lower = tuple(axis_bounds[0] for axis_bounds in spatial_bounds_m)
    upper = tuple(axis_bounds[1] for axis_bounds in spatial_bounds_m)
  ####
  extents = tuple(max(upper[index] - lower[index], 1.0e-6) for index in range(3))
  if spatial_bounds_m is None:
    extent = max(extents)
    center = tuple((lower[index] + upper[index]) / 2.0 for index in range(3))
    limits = tuple(
      (center[index] - extent / 2.0, center[index] + extent / 2.0)
      for index in range(3)
    )
  else:
    limits = spatial_bounds_m
  ####
  axis.set_xlim(*limits[0])
  axis.set_ylim(*limits[1])
  axis.set_zlim(*limits[2])
  axis.set_box_aspect(extents)
####


def _set_equal(axis: Any) -> None:
  axis.set_aspect('equal', adjustable='datalim')
  axis.grid(True, alpha=0.22)
####


def _set_equal_spatial_bounds(
  axis: Any,
  x_bounds: tuple[float, float],
  y_bounds: tuple[float, float],
) -> None:
  axis.set_xlim(*x_bounds)
  axis.set_ylim(*y_bounds)
  axis.set_aspect('equal', adjustable='box')
  axis.grid(True, alpha=0.22)
####


def _save(
  figure: Any,
  path: Path,
  *,
  title: str,
  bundle: StandardizedModelVisualization,
  spec: ModelVisualizationGallerySpec,
  layout_rect: tuple[float, float, float, float] = (0.0, 0.0, 1.0, 0.91),
) -> None:
  figure.suptitle(
    f'{title}\n{bundle.lane_id} | {bundle.claims.model_fidelity} | '
    f'{bundle.claims.validation_level} | frame={bundle.frame_id}',
    fontsize=10,
  )
  figure.tight_layout(rect=layout_rect)
  figure.savefig(path, dpi=140, metadata={
    'SourceBundleSHA256': bundle.digest_sha256(),
    'VisualizationSpecSHA256': spec.digest_sha256(),
  })
####


def _render_region_map(
  plt: Any,
  Patch: Any,
  bundle: StandardizedModelVisualization,
  spec: ModelVisualizationGallerySpec,
  selected_field: ModelVisualField | None,
  output: Path,
) -> ModelGalleryArtifact:
  path = output / 'model_regions.png'
  if selected_field is None:
    figure, axis = plt.subplots(figsize=(9.0, 6.0))
    axis.text(
      0.5,
      0.5,
      'No polygonal regions retained by this model lane',
      ha='center',
      va='center',
    )
    axis.set_axis_off()
  else:
    polygons = selected_field.polygons_xr_m
    if spec.spatial_bounds_m is None:
      x_bounds = (
        min(point[0] for polygon in polygons for point in polygon),
        max(point[0] for polygon in polygons for point in polygon),
      )
      radial_bounds = (
        min(point[1] for polygon in polygons for point in polygon),
        max(point[1] for polygon in polygons for point in polygon),
      )
    else:
      x_bounds, radial_bounds = spec.spatial_bounds_m[:2]
    ####
    x_span = x_bounds[1] - x_bounds[0]
    radial_span = radial_bounds[1] - radial_bounds[0]
    if x_span > 0.0 and radial_span > 0.0:
      figure_height = max(2.4, min(8.0, 1.4 + 12.0 * radial_span / x_span))
    else:
      figure_height = 6.0
    ####
    figure, axis = plt.subplots(figsize=(14.0, figure_height))
    region_types = selected_field.region_types or (None,) * len(polygons)
    region_labels = selected_field.region_labels or (None,) * len(polygons)
    categories = tuple(sorted({value for value in region_types if value is not None}))
    palette = plt.get_cmap('tab20')
    category_colors = {
      category: palette(index % palette.N)
      for index, category in enumerate(categories)
    }
    for polygon, region_type in zip(polygons, region_types, strict=True):
      axis.fill(
        [point[0] for point in polygon],
        [point[1] for point in polygon],
        facecolor=(
          '#cbd2d9'
          if region_type is None
          else category_colors[region_type]
        ),
        edgecolor='#263746',
        linewidth=0.6,
        alpha=0.82,
      )
    ####
    legend_handles = [
      Patch(
        facecolor=category_colors[category],
        edgecolor='#263746',
        label=category,
      )
      for category in categories
    ]
    if any(value is None for value in region_types):
      legend_handles.append(
        Patch(
          facecolor='#cbd2d9',
          edgecolor='#263746',
          label='region type not supplied',
        )
      )
    ####
    if legend_handles:
      figure.legend(
        handles=legend_handles,
        title='Declared region type',
        loc='center left',
        bbox_to_anchor=(0.84, 0.5),
        fontsize=8,
      )
    ####
    labels_available = any(value is not None for value in region_labels)
    labels_drawn = labels_available and len(polygons) <= 24
    if labels_drawn:
      label_anchors: dict[str, list[tuple[float, float]]] = {}
      for polygon, label in zip(polygons, region_labels, strict=True):
        if label is None:
          continue
        ####
        anchor_x = sum(point[0] for point in polygon) / len(polygon)
        anchor_y = sum(point[1] for point in polygon) / len(polygon)
        label_anchors.setdefault(label, []).append((anchor_x, anchor_y))
      ####
      for label, anchors in sorted(label_anchors.items()):
        anchor_x = sum(point[0] for point in anchors) / len(anchors)
        anchor_y = sum(point[1] for point in anchors) / len(anchors)
        axis.text(
          anchor_x,
          anchor_y,
          label,
          ha='center',
          va='center',
          fontsize=7,
          color='#17212b',
          bbox={'facecolor': 'white', 'alpha': 0.72, 'edgecolor': 'none', 'pad': 1.2},
        )
      ####
    ####
    axis.set_xlabel('x [m]')
    axis.set_ylabel('r / y [m]')
    if labels_available and not labels_drawn:
      note = f'Labels omitted for readability; all {len(polygons)} remain in model_bundle.json.'
    elif categories and labels_drawn:
      note = 'Fill: declared region type | Text: declared region label'
    elif categories:
      note = 'Fill: declared region type | No region labels supplied'
    elif labels_available:
      note = 'Fill: untyped region | Text: declared region label'
    else:
      note = 'Polygon geometry only | No region types or labels supplied'
    axis.set_title(f'{selected_field.field_id}: declared region map\n{note}', fontsize=9)
    axis.set_xlim(*x_bounds)
    axis.set_ylim(*radial_bounds)
    axis.set_aspect('equal', adjustable='box')
    axis.grid(True, alpha=0.22)
  ####
  _save(
    figure,
    path,
    title='Declared model regions',
    bundle=bundle,
    spec=spec,
    layout_rect=(0.0, 0.0, 0.82 if selected_field is not None else 1.0, 0.88),
  )
  plt.close(figure)
  return ModelGalleryArtifact('model.regions', path.name, 'image/png')
####


def _polygon_radial_intervals(
  polygon: tuple[tuple[float, float], ...],
  station_x_m: float,
) -> tuple[tuple[float, float], ...]:
  """Intersect one retained x-r polygon using half-open axial boundaries."""

  crossings: list[float] = []
  for start, end in zip(polygon, (*polygon[1:], polygon[0]), strict=True):
    x0, r0 = start
    x1, r1 = end
    if x0 == x1:
      continue
    ####
    lower_x = min(x0, x1)
    upper_x = max(x0, x1)
    if lower_x <= station_x_m < upper_x:
      fraction = (station_x_m - x0) / (x1 - x0)
      crossings.append(r0 + fraction * (r1 - r0))
    ####
  ####
  crossings.sort()
  if len(crossings) % 2:
    raise ValueError(
      'axial station produced an odd polygon intersection count; '
      'the retained region geometry is not sliceable'
    )
  ####
  return tuple(
    (lower, upper)
    for lower, upper in zip(crossings[::2], crossings[1::2], strict=True)
    if upper > lower
  )
####


def _axial_slice_records(
  selected_field: ModelVisualField | None,
  spec: ModelVisualizationGallerySpec,
) -> tuple[
  tuple[float, ...],
  tuple[dict[str, float | int | str | None], ...],
  tuple[float, float],
]:
  if selected_field is None:
    return (), (), (0.0, 1.0)
  ####
  x_bounds = (
    min(point[0] for polygon in selected_field.polygons_xr_m for point in polygon),
    max(point[0] for polygon in selected_field.polygons_xr_m for point in polygon),
  )
  radial_bounds = (
    min(point[1] for polygon in selected_field.polygons_xr_m for point in polygon),
    max(point[1] for polygon in selected_field.polygons_xr_m for point in polygon),
  )
  station_positions = tuple(
    x_bounds[0] + fraction * (x_bounds[1] - x_bounds[0])
    for fraction in spec.axial_station_fractions
  )
  records: list[dict[str, float | int | str | None]] = []
  for station_index, (fraction, station_x_m) in enumerate(
    zip(spec.axial_station_fractions, station_positions, strict=True)
  ):
    station_record_start = len(records)
    for polygon_index, polygon in enumerate(selected_field.polygons_xr_m):
      for interval_index, (radial_min_m, radial_max_m) in enumerate(
        _polygon_radial_intervals(polygon, station_x_m)
      ):
        for channel_id, values in selected_field.channels.items():
          uncertainties = selected_field.channel_uncertainties.get(channel_id)
          records.append({
            'station_index': station_index,
            'station_fraction': fraction,
            'station_x_m': station_x_m,
            'polygon_index': polygon_index,
            'interval_index': interval_index,
            'radial_min_m': radial_min_m,
            'radial_max_m': radial_max_m,
            'channel_id': channel_id,
            'unit': selected_field.channel_units[channel_id],
            'region_type': (
              selected_field.region_types[polygon_index]
              if selected_field.region_types
              else None
            ),
            'region_label': (
              selected_field.region_labels[polygon_index]
              if selected_field.region_labels
              else None
            ),
            'value': values[polygon_index],
            'uncertainty': (
              None if uncertainties is None else uncertainties[polygon_index]
            ),
            'validity_status': (
              'masked' if values[polygon_index] is None else 'valid'
            ),
          })
        ####
      ####
    ####
    if len(records) == station_record_start:
      for channel_id in selected_field.channels:
        records.append({
          'station_index': station_index,
          'station_fraction': fraction,
          'station_x_m': station_x_m,
          'polygon_index': None,
          'interval_index': None,
          'radial_min_m': None,
          'radial_max_m': None,
          'channel_id': channel_id,
          'unit': selected_field.channel_units[channel_id],
          'region_type': None,
          'region_label': None,
          'value': None,
          'uncertainty': None,
          'validity_status': 'no_region_intersection',
        })
      ####
    ####
  ####
  return station_positions, tuple(records), radial_bounds
####


def _render_axial_slices(
  plt: Any,
  bundle: StandardizedModelVisualization,
  spec: ModelVisualizationGallerySpec,
  selected_field: ModelVisualField | None,
  output: Path,
) -> tuple[ModelGalleryArtifact, ModelGalleryArtifact]:
  """Render exact geometric cuts through lane-associated polygon fields."""

  station_positions, records, radial_bounds = _axial_slice_records(
    selected_field,
    spec,
  )
  table_path = output / 'model_axial_slice_values.csv'
  with table_path.open('w', encoding='utf-8', newline='') as stream:
    writer = csv.writer(stream, lineterminator='\n')
    writer.writerow((
      'bundle_digest_sha256',
      'visualization_spec_digest_sha256',
      'field_id',
      'station_index',
      'station_fraction',
      'station_x_m',
      'channel_id',
      'unit',
      'polygon_index',
      'interval_index',
      'radial_min_m',
      'radial_max_m',
      'region_type',
      'region_label',
      'value',
      'uncertainty',
      'validity_status',
    ))
    for record in records:
      writer.writerow((
        bundle.digest_sha256(),
        spec.digest_sha256(),
        '' if selected_field is None else selected_field.field_id,
        record['station_index'],
        record['station_fraction'],
        record['station_x_m'],
        record['channel_id'],
        record['unit'],
        record['polygon_index'],
        record['interval_index'],
        record['radial_min_m'],
        record['radial_max_m'],
        record['region_type'] or '',
        record['region_label'] or '',
        '' if record['value'] is None else record['value'],
        '' if record['uncertainty'] is None else record['uncertainty'],
        record['validity_status'],
      ))
    ####
  ####

  path = output / 'model_axial_slices.png'
  channels = () if selected_field is None else tuple(selected_field.channels)
  station_count = max(len(station_positions), 1)
  row_count = max(len(channels), 1)
  figure, axes = plt.subplots(
    row_count,
    station_count,
    figsize=(4.2 * station_count, max(2.8, 2.5 * row_count)),
    squeeze=False,
    sharex='col',
    sharey='row',
  )
  ####
  if selected_field is None:
    axes[0, 0].text(
      0.5,
      0.5,
      'No polygon field retained by this model lane',
      ha='center',
      va='center',
      transform=axes[0, 0].transAxes,
    )
    for axis in axes.flat:
      axis.set_axis_off()
    ####
  elif not channels:
    axes[0, 0].text(
      0.5,
      0.5,
      'No source-declared field channels are available for axial slices',
      ha='center',
      va='center',
      transform=axes[0, 0].transAxes,
    )
    for axis in axes.flat:
      axis.set_axis_off()
    ####
  else:
    for row_index, channel_id in enumerate(channels):
      unit = selected_field.channel_units[channel_id]
      channel_records = tuple(
        record for record in records if record['channel_id'] == channel_id
      )
      value_records = tuple(
        record
        for record in channel_records
        if record['value'] is not None
      )
      lower_candidates = tuple(
        float(record['value'])
        - (0.0 if record['uncertainty'] is None else float(record['uncertainty']))
        for record in value_records
      )
      upper_candidates = tuple(
        float(record['value'])
        + (0.0 if record['uncertainty'] is None else float(record['uncertainty']))
        for record in value_records
      )
      if value_records:
        lower_value = min(lower_candidates)
        upper_value = max(upper_candidates)
        value_span = upper_value - lower_value
        padding = 0.08 * value_span if value_span > 0.0 else max(abs(lower_value) * 0.05, 1.0)
        y_bounds = (lower_value - padding, upper_value + padding)
      else:
        y_bounds = (0.0, 1.0)
      ####
      for column_index in range(station_count):
        axis = axes[row_index, column_index]
        axis.set_xlim(*radial_bounds)
        axis.set_ylim(*y_bounds)
        station_x_m = (
          station_positions[column_index]
          if column_index < len(station_positions)
          else None
        )
        fraction = (
          spec.axial_station_fractions[column_index]
          if column_index < len(spec.axial_station_fractions)
          else None
        )
        if station_x_m is not None:
          if row_index == 0:
            axis.set_title(f'x={station_x_m:.6g} m  (f={fraction:.3g})')
          ####
        ####
        axis.grid(True, alpha=0.2)
        if row_index == row_count - 1:
          axis.set_xlabel('Radial coordinate r / y [m]')
        ####
        if column_index == 0:
          axis.set_ylabel(f'{channel_id} [{unit}]', fontsize=8, labelpad=8)
        ####
        entries = tuple(
          record
          for record in channel_records
          if (
            record['station_index'] == column_index
            and record['radial_min_m'] is not None
          )
        )
        if not entries:
          axis.text(
            0.5,
            0.5,
            'No retained zone intersects this station',
            ha='center',
            va='center',
            transform=axis.transAxes,
            fontsize=8,
          )
        ####
        for record in entries:
          radial_min = float(record['radial_min_m'])
          radial_max = float(record['radial_max_m'])
          value = record['value']
          if value is None:
            axis.axvspan(
              radial_min,
              radial_max,
              facecolor='#d2d7dc',
              edgecolor='#747d86',
              hatch='///',
              alpha=0.55,
            )
            continue
          ####
          numeric_value = float(value)
          axis.hlines(
            numeric_value,
            radial_min,
            radial_max,
            color='#4c78a8',
            linewidth=2.8,
          )
          uncertainty = record['uncertainty']
          if uncertainty is not None:
            axis.errorbar(
              (radial_min + radial_max) / 2.0,
              numeric_value,
              yerr=float(uncertainty),
              fmt='o',
              markersize=2.5,
              capsize=2,
              color='#d62728',
            )
          ####
        ####
      ####
    ####
    axes[-1, 0].set_xlabel('Radial coordinate r / y [m]')
    figure.text(
      0.5,
      0.005,
      'Values are assigned per polygon by the lane adapter; no interpolation between polygons. Hatched spans are masked.',
      ha='center',
      fontsize=8,
    )
  ####
  _save(
    figure,
    path,
    title='Axial station slices from retained model polygons',
    bundle=bundle,
    spec=spec,
  )
  plt.close(figure)
  return (
    ModelGalleryArtifact('model.axial-slices', path.name, 'image/png'),
    ModelGalleryArtifact('model.axial-slice-values', table_path.name, 'text/csv'),
  )
####


def _render_diagnostics_panel(
  plt: Any,
  bundle: StandardizedModelVisualization,
  spec: ModelVisualizationGallerySpec,
  output: Path,
) -> ModelGalleryArtifact:
  """Render the source claims and exact view settings as a readable panel."""

  claims = bundle.claims
  left = (
    ('Lane', bundle.lane_id),
    ('Model', f'{bundle.model_id} v{bundle.model_version}'),
    ('Frame', bundle.frame_id),
    ('Source status', bundle.source_status),
    ('Applicability', bundle.applicability_status.value),
    ('Applicability reasons', '; '.join(bundle.applicability_reasons) or 'none'),
    ('Fidelity', claims.model_fidelity),
    ('Validation level', claims.validation_level),
    ('Geometry claim', claims.geometry_claim.value),
    ('Production claim allowed', str(claims.production_claim_allowed).lower()),
    ('Bundle SHA-256', bundle.digest_sha256()),
  )
  right = (
    ('View kind', spec.view_kind),
    ('View spec SHA-256', spec.digest_sha256()),
    ('Selected station', str(_selected_station(bundle, spec))),
    ('Selected field', spec.field_id or 'default / none'),
    ('Selected field channel', spec.field_channel_id or 'all / none'),
    ('Selected paths', ', '.join(spec.path_ids) or 'all declared paths'),
    ('Axis scales', f'x={spec.x_scale.value}, y={spec.y_scale.value}'),
    ('Color map / radial segments', f'{spec.color_map} / {spec.radial_segments}'),
    (
      'Spatial bounds [m]',
      'automatic'
      if spec.spatial_bounds_m is None
      else json.dumps(spec.spatial_bounds_m, separators=(',', ':')),
    ),
    ('Claim notes', '; '.join(claims.claim_notes) or 'none'),
    ('Warnings', '; '.join(bundle.warnings) or 'none'),
    ('Diagnostics', json.dumps(dict(sorted(bundle.diagnostics.items())), sort_keys=True)),
  )

  def render_column(items: Sequence[tuple[str, str]], width: int = 72) -> str:
    lines: list[str] = []
    for label, value in items:
      prefix = f'{label}: '
      lines.extend(textwrap.wrap(
        prefix + value,
        width=width,
        subsequent_indent=' ' * len(prefix),
        break_long_words=True,
        break_on_hyphens=False,
      ) or [prefix])
    return '\n'.join(lines)

  left_text = render_column(left)
  right_text = render_column(right)
  height = max(3.5, 0.18 * max(
    len(left_text.splitlines()),
    len(right_text.splitlines()),
  ) + 0.9)
  figure, axis = plt.subplots(figsize=(14.0, height))
  axis.set_axis_off()
  axis.text(
    0.02,
    0.91,
    left_text,
    transform=axis.transAxes,
    va='top',
    fontsize=9,
    family='monospace',
    color='#263746',
  )
  axis.text(
    0.52,
    0.91,
    right_text,
    transform=axis.transAxes,
    va='top',
    fontsize=9,
    family='monospace',
    color='#263746',
  )
  path = output / 'model_diagnostics_and_claims.png'
  _save(
    figure,
    path,
    title='Source diagnostics and claim boundary',
    bundle=bundle,
    spec=spec,
  )
  plt.close(figure)
  return ModelGalleryArtifact(
    'model.diagnostics-and-claims',
    path.name,
    'image/png',
  )
####


def _render_plots(
  bundle: StandardizedModelVisualization,
  spec: ModelVisualizationGallerySpec,
  output: Path,
  station_index: int,
  selected_field: ModelVisualField | None,
  selected_paths: tuple[ModelVisualPath, ...],
) -> tuple[ModelGalleryArtifact, ...]:
  try:
    from matplotlib import pyplot as plt
    from matplotlib.colors import Normalize
    from matplotlib.patches import Patch
    from matplotlib.ticker import MaxNLocator
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
  except ImportError as error:
    raise RuntimeError('model visualization galleries require the optional plot dependency: pip install .[plot]') from error
  ####

  vertices, faces, face_sections = _mesh(bundle, spec.radial_segments)
  channel = None
  if bundle.section_channels:
    channel = bundle.section_channels[0]
  ####
  colors: Any = '#4c78a8'
  normalizer: Any | None = None
  if channel is not None:
    minimum, maximum = min(channel.values), max(channel.values)
    normalizer = Normalize(vmin=minimum, vmax=maximum if maximum > minimum else minimum + 1.0)
    cmap = plt.get_cmap(spec.color_map)
    colors = [cmap(normalizer(channel.values[index])) for index in face_sections]
  ####

  overview_path = output / 'model_overview.png'
  figure = plt.figure(figsize=(9.5, 7.0))
  axis: Any = figure.add_subplot(111, projection='3d')
  polygons = [[vertices[index] for index in face] for face in faces]
  axis.add_collection3d(Poly3DCollection(polygons, facecolor=colors, edgecolor='none', alpha=0.84))
  centerline: tuple[tuple[float, float, float], ...] = tuple(
    (
      float(section.center_m[0]),
      float(section.center_m[1]),
      float(section.center_m[2]),
    )
    for section in bundle.sectioned_tube.sections
  )
  axis.plot([point[0] for point in centerline], [point[1] for point in centerline], [point[2] for point in centerline], color='black', linewidth=1.2, label='centerline')
  selected_center = centerline[station_index]
  axis.scatter([selected_center[0]], [selected_center[1]], [selected_center[2]], color='crimson', s=32, label=f'station {station_index}')
  for path in selected_paths:
    axis.plot([point[0] for point in path.points_m], [point[1] for point in path.points_m], [point[2] for point in path.points_m], linewidth=1.0, label=path.path_id)
  ####
  _set_3d_bounds(
    axis,
    vertices + centerline + tuple(point for path in selected_paths for point in path.points_m),
    spec.spatial_bounds_m,
  )
  axis.set_xlabel('x [m]', labelpad=8)
  axis.set_ylabel('y [m]', labelpad=8)
  axis.set_zlabel('z [m]', labelpad=8)
  axis.zaxis.set_major_locator(MaxNLocator(nbins=3))
  axis.tick_params(pad=2, labelsize=8)
  axis.legend(loc='upper left', fontsize=7)
  if normalizer is not None and channel is not None:
    colorbar = figure.colorbar(
      plt.cm.ScalarMappable(norm=normalizer, cmap=spec.color_map),
      ax=axis,
      orientation='horizontal',
      fraction=0.045,
      pad=0.14,
      aspect=36,
      label=f'{channel.channel_id} [{channel.unit}]',
    )
    colorbar.ax.tick_params(labelsize=8)
  ####
  _save(figure, overview_path, title='Standardized model-lane overview', bundle=bundle, spec=spec)
  plt.close(figure)

  projections_path = output / 'model_projections.png'
  figure, axes = plt.subplots(2, 2, figsize=(9.0, 8.0))
  pairs = ((0, 1, 'XY'), (0, 2, 'XZ'), (1, 2, 'YZ'))
  axis_names = ('x', 'y', 'z')
  for target, (first, second, name) in zip(axes.flat[:3], pairs, strict=True):
    target = target  # keep the renderer boundary dynamically typed
    target.plot([point[first] for point in centerline], [point[second] for point in centerline], color='#4c78a8', marker='o', markersize=2.5)
    target.scatter([selected_center[first]], [selected_center[second]], color='crimson', s=30)
    for path in selected_paths:
      target.plot([point[first] for point in path.points_m], [point[second] for point in path.points_m], linewidth=0.9, label=path.path_id)
    ####
    target.set_xlabel(f'{axis_names[first]} [m]')
    target.set_ylabel(f'{axis_names[second]} [m]')
    target.set_title(f'{name} projection')
    if spec.spatial_bounds_m is None:
      _set_equal(target)
    else:
      _set_equal_spatial_bounds(
        target,
        spec.spatial_bounds_m[first],
        spec.spatial_bounds_m[second],
      )
  ####
  cross_axis: Any = axes[1, 1]
  section = bundle.sectioned_tube.sections[station_index]
  theta = tuple(2.0 * pi * index / 128.0 for index in range(129))
  cross_axis.plot([section.radius_major_m * cos(value) for value in theta], [section.radius_minor_m * sin(value) for value in theta], color='#f58518')
  cross_axis.set_xlabel('local section axis 1 [m]')
  cross_axis.set_ylabel('local section axis 2 [m]')
  cross_axis.set_title(f'station {station_index} cross-section')
  _set_equal(cross_axis)
  _save(figure, projections_path, title='Standardized model-lane projections', bundle=bundle, spec=spec)
  plt.close(figure)

  channels_path = output / 'model_channels.png'
  channel_count = max(len(bundle.section_channels), 1)
  figure, channel_axes = plt.subplots(channel_count, 1, figsize=(9.0, max(3.5, 2.6 * channel_count)), squeeze=False, sharex=True)
  arc_length = tuple(float(section.arc_length_m) for section in bundle.sectioned_tube.sections)
  if not bundle.section_channels:
    channel_axes[0, 0].text(0.5, 0.5, 'No section channels declared', ha='center', va='center')
    channel_axes[0, 0].set_axis_off()
  else:
    for target, item in zip(channel_axes[:, 0], bundle.section_channels, strict=True):
      target.plot(arc_length, item.values, marker='o', markersize=2.5, label=f'{item.channel_id} — {item.semantic} [{item.unit}]')
      if item.uncertainties is not None:
        lower = tuple(
          float(value - uncertainty)
          if uncertainty is not None else float('nan')
          for value, uncertainty in zip(item.values, item.uncertainties, strict=True)
        )
        upper = tuple(
          float(value + uncertainty)
          if uncertainty is not None else float('nan')
          for value, uncertainty in zip(item.values, item.uncertainties, strict=True)
        )
        target.fill_between(
          arc_length,
          lower,
          upper,
          color='tab:orange',
          alpha=0.20,
          linewidth=0.0,
          label='source-declared absolute uncertainty',
        )
      ####
      target.axvline(arc_length[station_index], color='crimson', linewidth=0.8)
      target.set_ylabel(item.unit)
      target.grid(True, alpha=0.22)
      target.legend(loc='best', fontsize=8)
      if spec.x_scale is AxisScale.LOG10:
        if any(value <= 0.0 for value in arc_length):
          raise ValueError('log10 x-axis requires positive model arc lengths')
        ####
        target.set_xscale('log')
      ####
      if spec.y_scale is AxisScale.LOG10:
        if any(value <= 0.0 for value in item.values):
          raise ValueError(f'log10 y-axis requires positive values for {item.channel_id!r}')
        ####
        target.set_yscale('log')
      ####
    ####
    channel_axes[-1, 0].set_xlabel('arc length [m]')
  ####
  _save(figure, channels_path, title='Standardized model-lane channels', bundle=bundle, spec=spec)
  plt.close(figure)

  fields_path = output / 'model_fields.png'
  figure, axis = plt.subplots(figsize=(9.0, 6.0))
  if selected_field is None:
    axis.text(0.5, 0.5, 'No polygonal fields declared by this model lane', ha='center', va='center')
    axis.set_axis_off()
  else:
    values = selected_field.channels.get(spec.field_channel_id, ()) if spec.field_channel_id is not None else ()
    finite_values = tuple(value for value in values if value is not None)
    field_normalizer = None
    field_cmap: Any | None = None
    if finite_values:
      field_normalizer = Normalize(vmin=min(finite_values), vmax=max(finite_values) if max(finite_values) > min(finite_values) else min(finite_values) + 1.0)
      field_cmap = plt.get_cmap(spec.color_map)
    ####
    for index, polygon in enumerate(selected_field.polygons_xr_m):
      value = values[index] if index < len(values) else None
      color = '#bdbdbd' if value is None or field_normalizer is None or field_cmap is None else field_cmap(field_normalizer(value))
      axis.fill([point[0] for point in polygon], [point[1] for point in polygon], facecolor=color, edgecolor='#555555', linewidth=0.6, alpha=0.78)
    ####
    for path in selected_paths:
      axis.plot([point[0] for point in path.points_m], [point[1] for point in path.points_m], linewidth=1.1, label=path.path_id)
    ####
    axis.set_xlabel('x [m]')
    axis.set_ylabel('r / y [m]')
    axis.set_title(f'{selected_field.field_id}: {selected_field.semantic}' + (f' — {spec.field_channel_id}' if spec.field_channel_id else ''))
    if spec.spatial_bounds_m is None:
      _set_equal(axis)
    else:
      _set_equal_spatial_bounds(
        axis,
        spec.spatial_bounds_m[0],
        spec.spatial_bounds_m[1],
      )
    field_channel_id = spec.field_channel_id
    if field_normalizer is not None and field_cmap is not None and field_channel_id is not None:
      figure.colorbar(plt.cm.ScalarMappable(norm=field_normalizer, cmap=spec.color_map), ax=axis, label=f'{field_channel_id} [{selected_field.channel_units[field_channel_id]}]')
    ####
    missing_field_status = (
      'No field channel selected'
      if spec.field_channel_id is None
      else 'Unavailable field value'
    )
    has_missing_field_status = (
      spec.field_channel_id is None
      or any(value is None for value in values)
    )
    if has_missing_field_status:
      axis.plot(
        [],
        [],
        marker='s',
        linestyle='none',
        color='#bdbdbd',
        label=missing_field_status,
      )
    ####
    if selected_paths or has_missing_field_status:
      axis.legend(loc='best', fontsize=8)
    ####
  ####
  _save(figure, fields_path, title='Standardized model-lane fields and paths', bundle=bundle, spec=spec)
  plt.close(figure)

  field_uncertainty_path = output / 'model_field_uncertainty.png'
  figure, axis = plt.subplots(figsize=(9.0, 6.0))
  if selected_field is None:
    axis.text(0.5, 0.5, 'No polygonal field selected', ha='center', va='center')
    axis.set_axis_off()
  elif spec.field_channel_id is None:
    axis.text(
      0.5,
      0.5,
      'Select a field channel to inspect its declared uncertainty',
      ha='center',
      va='center',
    )
    axis.set_axis_off()
  else:
    channel_id = spec.field_channel_id
    channel_values = selected_field.channels[channel_id]
    uncertainties = selected_field.channel_uncertainties.get(channel_id)
    if uncertainties is None:
      axis.text(
        0.5,
        0.5,
        f'No source-declared uncertainty for {channel_id}',
        ha='center',
        va='center',
      )
      axis.set_axis_off()
    else:
      visible_uncertainties = tuple(
        uncertainty
        if index < len(channel_values) and channel_values[index] is not None
        else None
        for index, uncertainty in enumerate(uncertainties)
      )
      finite_uncertainties = tuple(
        value for value in visible_uncertainties if value is not None
      )
      has_unavailable_uncertainty = any(
        value is None for value in visible_uncertainties
      )
      uncertainty_normalizer = None
      constant_uncertainty = None
      if finite_uncertainties:
        minimum = min(finite_uncertainties)
        maximum = max(finite_uncertainties)
        if maximum == minimum:
          constant_uncertainty = minimum
        else:
          uncertainty_normalizer = Normalize(vmin=minimum, vmax=maximum)
        ####
      ####
      uncertainty_cmap = plt.get_cmap(spec.color_map)
      for index, polygon in enumerate(selected_field.polygons_xr_m):
        uncertainty = (
          visible_uncertainties[index]
          if index < len(visible_uncertainties)
          else None
        )
        if uncertainty is None:
          color = '#bdbdbd'
        elif uncertainty_normalizer is None:
          color = uncertainty_cmap(0.5)
        else:
          color = uncertainty_cmap(uncertainty_normalizer(uncertainty))
        ####
        axis.fill(
          [point[0] for point in polygon],
          [point[1] for point in polygon],
          facecolor=color,
          edgecolor='#555555',
          linewidth=0.6,
          alpha=0.82,
        )
      ####
      for path in selected_paths:
        axis.plot(
          [point[0] for point in path.points_m],
          [point[1] for point in path.points_m],
          linewidth=1.1,
          label=path.path_id,
        )
      ####
      axis.set_xlabel('x [m]')
      axis.set_ylabel('r / y [m]')
      axis.set_title(
        f'{selected_field.field_id}: absolute uncertainty of {channel_id}'
      )
      _set_equal(axis)
      if uncertainty_normalizer is not None:
        axis.figure.colorbar(
          plt.cm.ScalarMappable(
            norm=uncertainty_normalizer,
            cmap=spec.color_map,
          ),
          ax=axis,
          label=(
            f'{channel_id} absolute uncertainty '
            f'[{selected_field.channel_units[channel_id]}]'
          ),
        )
      elif constant_uncertainty is not None:
        axis.plot(
          [],
          [],
          marker='s',
          linestyle='none',
          color=uncertainty_cmap(0.5),
          label=(
            f'{constant_uncertainty:.6g} '
            f'[{selected_field.channel_units[channel_id]}]'
          ),
        )
      ####
      if has_unavailable_uncertainty:
        axis.plot(
          [],
          [],
          marker='s',
          linestyle='none',
          color='#bdbdbd',
          label='unavailable uncertainty',
        )
      ####
      if (
        selected_paths
        or constant_uncertainty is not None
        or has_unavailable_uncertainty
      ):
        axis.legend(
          loc='best',
          fontsize=8,
          title=(
            f'{channel_id} absolute uncertainty'
            if constant_uncertainty is not None
            else None
          ),
        )
      ####
      axis.text(
        0.01,
        0.01,
        'Source-declared absolute uncertainty; confidence meaning is not inferred',
        transform=axis.transAxes,
        fontsize=8,
        verticalalignment='bottom',
      )
    ####
  ####
  _save(
    figure,
    field_uncertainty_path,
    title='Standardized model-lane field uncertainty',
    bundle=bundle,
    spec=spec,
  )
  plt.close(figure)

  return (
    ModelGalleryArtifact('model.overview', overview_path.name, 'image/png'),
    ModelGalleryArtifact('model.projections', projections_path.name, 'image/png'),
    ModelGalleryArtifact('model.channels', channels_path.name, 'image/png'),
    ModelGalleryArtifact('model.fields', fields_path.name, 'image/png'),
    *_render_axial_slices(
      plt,
      bundle,
      spec,
      selected_field,
      output,
    ),
    _render_region_map(
      plt,
      Patch,
      bundle,
      spec,
      selected_field,
      output,
    ),
    ModelGalleryArtifact(
      'model.field-uncertainty',
      field_uncertainty_path.name,
      'image/png',
    ),
    _render_diagnostics_panel(plt, bundle, spec, output),
  )
####


def write_model_gallery_manifest(
  manifest: ModelVisualizationGalleryManifest,
  path: str | Path | None = None,
) -> Path:
  """Write a model gallery manifest to a chosen path."""

  output = manifest.manifest_path if path is None else Path(path)
  output.parent.mkdir(parents=True, exist_ok=True)
  output.write_text(manifest.canonical_json(), encoding='utf-8')
  return output
####


def _coerce_model_lane(value: ModelVisualizationLane | str) -> ModelVisualizationLane:
  if isinstance(value, ModelVisualizationLane):
    return value
  ####
  try:
    return ModelVisualizationLane(value)
  except (TypeError, ValueError) as error:
    raise ValueError(f'unknown model visualization lane: {value!r}') from error
  ####
####


def _normalize_gallery_bundles(
  bundles: Sequence[StandardizedModelVisualization]
  | Mapping[ModelVisualizationLane | str, StandardizedModelVisualization],
) -> dict[ModelVisualizationLane, StandardizedModelVisualization]:
  if isinstance(bundles, Mapping):
    entries = tuple(bundles.items())
  else:
    entries = tuple((None, bundle) for bundle in bundles)
  ####
  if not entries:
    raise ValueError('model visualization gallery set requires at least one bundle')
  ####
  normalized: dict[ModelVisualizationLane, StandardizedModelVisualization] = {}
  for key, bundle in entries:
    if not isinstance(bundle, StandardizedModelVisualization):
      raise TypeError('gallery set bundles must be StandardizedModelVisualization values')
    ####
    lane = bundle.lane if key is None else _coerce_model_lane(key)
    if key is not None and lane is not bundle.lane:
      raise ValueError(
        f'gallery set key {lane.value!r} does not match bundle lane {bundle.lane.value!r}'
      )
    ####
    if lane in normalized:
      raise ValueError(f'duplicate model visualization lane: {lane.value}')
    ####
    normalized[lane] = bundle
  ####
  missing = tuple(lane.value for lane in MODEL_VISUALIZATION_LANES if lane not in normalized)
  unexpected = tuple(lane.value for lane in normalized if lane not in MODEL_VISUALIZATION_LANES)
  if missing or unexpected:
    details = []
    if missing:
      details.append(f'missing={missing!r}')
    ####
    if unexpected:
      details.append(f'unexpected={unexpected!r}')
    ####
    raise ValueError('gallery set requires exactly the five model lanes: ' + ', '.join(details))
  ####
  return normalized
####


def _normalize_gallery_specs(
  specs: Mapping[ModelVisualizationLane | str, ModelVisualizationGallerySpec] | None,
  bundles: Mapping[ModelVisualizationLane, StandardizedModelVisualization],
) -> dict[ModelVisualizationLane, ModelVisualizationGallerySpec]:
  if specs is None:
    return {}
  ####
  normalized: dict[ModelVisualizationLane, ModelVisualizationGallerySpec] = {}
  for key, spec in specs.items():
    lane = _coerce_model_lane(key)
    if lane in normalized:
      raise ValueError(f'duplicate model gallery spec lane: {lane.value}')
    ####
    if not isinstance(spec, ModelVisualizationGallerySpec):
      raise TypeError('gallery set specs must be ModelVisualizationGallerySpec values')
    ####
    if lane not in bundles:
      raise ValueError(f'model gallery spec has no matching bundle: {lane.value}')
    ####
    spec.validate_for_bundle(bundles[lane])
    normalized[lane] = spec
  ####
  return normalized
####


def write_model_gallery_set_manifest(
  manifest: ModelVisualizationGallerySetManifest,
  path: str | Path | None = None,
) -> Path:
  """Write the deterministic top-level five-lane gallery manifest."""

  if not isinstance(manifest, ModelVisualizationGallerySetManifest):
    raise TypeError('manifest must be ModelVisualizationGallerySetManifest')
  ####
  output = manifest.manifest_path if path is None else Path(path)
  output.parent.mkdir(parents=True, exist_ok=True)
  output.write_text(manifest.canonical_json(), encoding='utf-8')
  return output
####


def render_model_visualization_gallery_set(
  bundles: Sequence[StandardizedModelVisualization]
  | Mapping[ModelVisualizationLane | str, StandardizedModelVisualization],
  output_dir: str | Path,
  *,
  specs: Mapping[ModelVisualizationLane | str, ModelVisualizationGallerySpec] | None = None,
  render_plots: bool = True,
) -> ModelVisualizationGallerySetManifest:
  """Render one independent gallery and manifest for each of the five lanes.

  The set wrapper provides navigation and completeness evidence only. It does
  not merge bundle geometry, channels, fields, or claims across lanes.
  """

  if not isinstance(render_plots, bool):
    raise TypeError('render_plots must be bool')
  ####
  normalized = _normalize_gallery_bundles(bundles)
  normalized_specs = _normalize_gallery_specs(specs, normalized)
  output = Path(output_dir)
  output.mkdir(parents=True, exist_ok=True)
  manifests: list[ModelVisualizationGalleryManifest] = []
  for lane in MODEL_VISUALIZATION_LANES:
    bundle = normalized[lane]
    lane_manifest = render_model_visualization_gallery(
      bundle,
      output / lane.value,
      spec=normalized_specs.get(lane),
      render_plots=render_plots,
    )
    manifests.append(lane_manifest)
  ####
  manifest = ModelVisualizationGallerySetManifest(
    schema=MODEL_GALLERY_SET_MANIFEST_SCHEMA,
    lane_manifests=tuple(manifests),
    guardrails=(
      'the set contains exactly one independently rendered bundle for each declared model lane',
      'lane digests, provenance, fidelity, validation, and claim ceilings remain independent',
      'the set manifest is navigation/completeness evidence and is not a merged physical result',
      'rendering a lane cannot promote a research, approximate, or unvalidated model',
    ),
    comparison_intake={
      'status': 'contract-ready-provider-data-pending',
      'series_schema': VISUAL_FEATURE_SERIES_SCHEMA,
      'comparison_operator_id': VISUAL_FEATURE_COMPARISON_OPERATOR_ID,
      'lane_count': len(MODEL_VISUALIZATION_LANES),
      'required_series_metadata': [
        'feature_id',
        'coordinate_id_and_unit',
        'feature_unit',
        'source_id_and_digest',
        'scenario_id',
        'coordinate_frame_id',
        'measurement_space',
        'operator_id',
        'validity_mask',
        'branch_ids_for_hysteretic_features',
        'one_sigma_uncertainty_when_available',
      ],
      'guardrails': [
        'each lane remains an independent bundle and claim ceiling',
        'provider observations and output assets are not synthesized by the gallery',
        'comparison requires explicit frame/operator/scenario compatibility',
      ],
    },
    manifest_path=output / 'model_gallery_set_manifest.json',
  )
  write_model_gallery_set_manifest(manifest)
  return manifest
####


def render_model_visualization_gallery(
  bundle: StandardizedModelVisualization | ModelLaneVisualizationResult,
  output_dir: str | Path,
  *,
  spec: ModelVisualizationGallerySpec | None = None,
  render_plots: bool = True,
) -> ModelVisualizationGalleryManifest:
  """Write JSON and optional static views for one standardized model lane."""

  source_result = bundle if isinstance(bundle, ModelLaneVisualizationResult) else None
  if source_result is not None:
    bundle = standardize_model_lane_visualization_result(source_result)
  ####
  if not isinstance(bundle, StandardizedModelVisualization):
    raise TypeError('bundle must be StandardizedModelVisualization or ModelLaneVisualizationResult')
  ####
  if not isinstance(render_plots, bool):
    raise TypeError('render_plots must be bool')
  ####
  source_result_digest = None if source_result is None else canonical_digest(source_result)
  resolved = spec or ModelVisualizationGallerySpec.for_bundle(
    bundle,
    source_result_digest_sha256=source_result_digest,
  )
  resolved.validate_for_bundle(
    bundle,
    source_result_digest_sha256=source_result_digest,
  )
  output = Path(output_dir)
  output.mkdir(parents=True, exist_ok=True)
  station_index = _selected_station(bundle, resolved)
  selected_field = _selected_field(bundle, resolved)
  selected_paths = _selected_paths(bundle, resolved)

  bundle_path = output / 'model_bundle.json'
  bundle_path.write_text(json.dumps(bundle.model_dump(), indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + '\n', encoding='utf-8')
  source = _source(bundle, source_result)
  spec_path = output / 'model_gallery_spec.json'
  spec_path.write_text(json.dumps({
    'schema': MODEL_GALLERY_SPEC_SCHEMA,
    'spec': resolved.model_dump(),
    'spec_digest_sha256': resolved.digest_sha256(),
    'source': source,
  }, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + '\n', encoding='utf-8')

  artifacts: list[ModelGalleryArtifact] = [
    ModelGalleryArtifact('metadata.model-bundle', bundle_path.name, 'application/json'),
    ModelGalleryArtifact('metadata.model-gallery-spec', spec_path.name, 'application/json'),
  ]
  if source_result is not None:
    source_result_path = output / 'model_lane_result.json'
    source_result_path.write_text(
      source_result.model_dump_json(indent=2) + '\n',
      encoding='utf-8',
    )
    artifacts.append(ModelGalleryArtifact(
      'metadata.model-lane-result',
      source_result_path.name,
      'application/json',
    ))
  ####
  artifacts.append(_write_station_inspector(
    bundle,
    resolved,
    station_index,
    selected_paths,
    output,
    source_result_digest,
  ))
  if render_plots:
    artifacts.extend(_render_plots(bundle, resolved, output, station_index, selected_field, selected_paths))
  ####
  guardrails = (
    'model-lane gallery is an evaluation surface and does not add physics or validation claims',
    'shock diamonds, regions, endpoints, and paths are shown only when explicitly retained by the model bundle',
    'axial slices use exact polygon intersections and lane-specific channel semantics; no interpolation between polygon values is performed',
    'axial slice stations are bound by fractions of each selected field extent; shared x faces use half-open intervals',
    'fidelity, validation, and production-claim metadata remain lane-specific and are not promoted by rendering',
    'masked field values remain uncolored rather than being converted to zero',
  )
  manifest = ModelVisualizationGalleryManifest(
    schema=MODEL_GALLERY_MANIFEST_SCHEMA,
    lane_id=bundle.lane_id,
    spec=resolved,
    source=source,
    artifacts=tuple(artifacts),
    guardrails=guardrails,
    manifest_path=output / 'model_gallery_manifest.json',
  )
  write_model_gallery_manifest(manifest)
  return manifest
####
