"""Static evaluation galleries for the five standardized model lanes.

The strict product gallery consumes public ``ProductResult`` objects.  Model
lane bundles are deliberately a separate evaluation surface because they also
retain field polygons, named paths, and lane-specific promotion metadata.
This module renders those additional diagnostics without turning them into a
new product contract or inferring missing physical features.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from math import cos, pi, sin
from pathlib import Path
import re
from collections.abc import Mapping, Sequence
from typing import Any

from exhaust_plume.api import AxisScale
from exhaust_plume.contracts.common_v1 import canonical_digest
from exhaust_plume.products.model_visualization import (
  MODEL_VISUALIZATION_LANES,
  ModelVisualField,
  ModelVisualPath,
  ModelVisualizationLane,
  StandardizedModelVisualization,
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

  def __post_init__(self) -> None:
    if not isinstance(self.bundle_digest_sha256, str) or not _HASH.fullmatch(self.bundle_digest_sha256):
      raise ValueError('bundle_digest_sha256 must be a lowercase SHA-256 digest')
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
    **overrides: Any,
  ) -> ModelVisualizationGallerySpec:
    """Create a view spec bound to the exact serialized bundle."""

    if not isinstance(bundle, StandardizedModelVisualization):
      raise TypeError('bundle must be StandardizedModelVisualization')
    ####
    return cls(bundle_digest_sha256=bundle.digest_sha256(), **overrides)
  ####

  def validate_for_bundle(self, bundle: StandardizedModelVisualization) -> None:
    """Reject reuse of a model view spec against another bundle."""

    if not isinstance(bundle, StandardizedModelVisualization):
      raise TypeError('bundle must be StandardizedModelVisualization')
    ####
    if self.bundle_digest_sha256 != bundle.digest_sha256():
      raise ValueError('model visualization spec is bound to a different bundle')
    ####
  ####

  def model_dump(self) -> dict[str, Any]:
    return {
      'spec_schema': MODEL_GALLERY_SPEC_SCHEMA,
      'bundle_digest_sha256': self.bundle_digest_sha256,
      'view_kind': self.view_kind,
      'station_index': self.station_index,
      'field_id': self.field_id,
      'field_channel_id': self.field_channel_id,
      'path_ids': list(self.path_ids),
      'x_scale': self.x_scale.value,
      'y_scale': self.y_scale.value,
      'color_map': self.color_map,
      'radial_segments': self.radial_segments,
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


def _source(bundle: StandardizedModelVisualization) -> dict[str, Any]:
  return {
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


def _set_3d_bounds(axis: Any, points: Sequence[tuple[float, float, float]]) -> None:
  lower, upper = _bounds(points)
  extents = tuple(max(upper[index] - lower[index], 1.0e-6) for index in range(3))
  extent = max(extents)
  center = tuple((lower[index] + upper[index]) / 2.0 for index in range(3))
  axis.set_xlim(center[0] - extent / 2.0, center[0] + extent / 2.0)
  axis.set_ylim(center[1] - extent / 2.0, center[1] + extent / 2.0)
  axis.set_zlim(center[2] - extent / 2.0, center[2] + extent / 2.0)
  axis.set_box_aspect(extents)
####


def _set_equal(axis: Any) -> None:
  axis.set_aspect('equal', adjustable='datalim')
  axis.grid(True, alpha=0.22)
####


def _save(figure: Any, path: Path, *, title: str, bundle: StandardizedModelVisualization, spec: ModelVisualizationGallerySpec) -> None:
  figure.suptitle(
    f'{title}\n{bundle.lane_id} | {bundle.claims.model_fidelity} | '
    f'{bundle.claims.validation_level} | frame={bundle.frame_id}',
    fontsize=10,
  )
  figure.tight_layout(rect=(0.0, 0.0, 1.0, 0.91))
  figure.savefig(path, dpi=140, metadata={
    'SourceBundleSHA256': bundle.digest_sha256(),
    'VisualizationSpecSHA256': spec.digest_sha256(),
  })
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
  figure = plt.figure(figsize=(8.5, 6.5))
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
  _set_3d_bounds(axis, vertices + centerline + tuple(point for path in selected_paths for point in path.points_m))
  axis.set_xlabel('x [m]')
  axis.set_ylabel('y [m]')
  axis.set_zlabel('z [m]')
  axis.legend(loc='upper left', fontsize=7)
  if normalizer is not None and channel is not None:
    figure.colorbar(plt.cm.ScalarMappable(norm=normalizer, cmap=spec.color_map), ax=axis, label=f'{channel.channel_id} [{channel.unit}]')
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
    _set_equal(target)
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
    _set_equal(axis)
    field_channel_id = spec.field_channel_id
    if field_normalizer is not None and field_cmap is not None and field_channel_id is not None:
      figure.colorbar(plt.cm.ScalarMappable(norm=field_normalizer, cmap=spec.color_map), ax=axis, label=f'{field_channel_id} [{selected_field.channel_units[field_channel_id]}]')
    ####
    if selected_paths:
      axis.legend(loc='best', fontsize=8)
    ####
  ####
  _save(figure, fields_path, title='Standardized model-lane fields and paths', bundle=bundle, spec=spec)
  plt.close(figure)

  return (
    ModelGalleryArtifact('model.overview', overview_path.name, 'image/png'),
    ModelGalleryArtifact('model.projections', projections_path.name, 'image/png'),
    ModelGalleryArtifact('model.channels', channels_path.name, 'image/png'),
    ModelGalleryArtifact('model.fields', fields_path.name, 'image/png'),
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
    manifest_path=output / 'model_gallery_set_manifest.json',
  )
  write_model_gallery_set_manifest(manifest)
  return manifest
####


def render_model_visualization_gallery(
  bundle: StandardizedModelVisualization,
  output_dir: str | Path,
  *,
  spec: ModelVisualizationGallerySpec | None = None,
  render_plots: bool = True,
) -> ModelVisualizationGalleryManifest:
  """Write JSON and optional static views for one standardized model lane."""

  if not isinstance(bundle, StandardizedModelVisualization):
    raise TypeError('bundle must be StandardizedModelVisualization')
  ####
  if not isinstance(render_plots, bool):
    raise TypeError('render_plots must be bool')
  ####
  resolved = spec or ModelVisualizationGallerySpec.for_bundle(bundle)
  resolved.validate_for_bundle(bundle)
  output = Path(output_dir)
  output.mkdir(parents=True, exist_ok=True)
  station_index = _selected_station(bundle, resolved)
  selected_field = _selected_field(bundle, resolved)
  selected_paths = _selected_paths(bundle, resolved)

  bundle_path = output / 'model_bundle.json'
  bundle_path.write_text(json.dumps(bundle.model_dump(), indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + '\n', encoding='utf-8')
  spec_path = output / 'model_gallery_spec.json'
  spec_path.write_text(json.dumps({
    'schema': MODEL_GALLERY_SPEC_SCHEMA,
    'spec': resolved.model_dump(),
    'spec_digest_sha256': resolved.digest_sha256(),
    'source': _source(bundle),
  }, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + '\n', encoding='utf-8')

  artifacts: list[ModelGalleryArtifact] = [
    ModelGalleryArtifact('metadata.model-bundle', bundle_path.name, 'application/json'),
    ModelGalleryArtifact('metadata.model-gallery-spec', spec_path.name, 'application/json'),
  ]
  if render_plots:
    artifacts.extend(_render_plots(bundle, resolved, output, station_index, selected_field, selected_paths))
  ####
  guardrails = (
    'model-lane gallery is an evaluation surface and does not create a new product capability',
    'shock diamonds, regions, endpoints, and paths are shown only when explicitly retained by the model bundle',
    'fidelity, validation, and production-claim metadata remain lane-specific and are not promoted by rendering',
    'masked field values remain uncolored rather than being converted to zero',
  )
  manifest = ModelVisualizationGalleryManifest(
    schema=MODEL_GALLERY_MANIFEST_SCHEMA,
    lane_id=bundle.lane_id,
    spec=resolved,
    source=_source(bundle),
    artifacts=tuple(artifacts),
    guardrails=guardrails,
    manifest_path=output / 'model_gallery_manifest.json',
  )
  write_model_gallery_manifest(manifest)
  return manifest
####
