"""Optional static galleries for the strict standard product results.

The gallery is an evaluation surface, not another product model.  It consumes
the renderer-neutral projections from :mod:`exhaust_plume.api.visualization`,
keeps invalid samples masked, and writes a JSON manifest that binds every
image/table to its source result and exact :class:`VisualizationSpec`.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
import json
from math import atan2, cos, isfinite, pi, sin, sqrt
from pathlib import Path
from typing import Any, Mapping, Sequence

from exhaust_plume.api import (
  PlumeFluxSectionResult,
  ProductResult,
  SectionedTubeResult,
  SpectralRadiantIntensityResult,
  SpectralRayTransferResult,
  VisualizationSpec,
  WavelengthDisplayUnit,
  build_sectioned_tube_render_mesh,
  project_plume_flux_view,
  project_sectioned_tube_view,
  project_spectral_radiant_intensity_view,
  project_spectral_ray_transfer_view,
)
from exhaust_plume.api.visualization import (
  PlumeFluxSectionGlyph,
  SectionedTubeChannelLine,
  SectionedTubeRenderMesh,
  SpectralRadiantIntensityGrid,
  SpectralRayTransferLine,
)
from exhaust_plume.api.visualization_spec import AxisScale, InvalidSamplePolicy

__all__ = (
  'GALLERY_MANIFEST_SCHEMA',
  'GalleryArtifact',
  'VisualizationGalleryManifest',
  'render_plume_flux_gallery',
  'render_product_gallery',
  'render_sectioned_tube_gallery',
  'render_spectral_radiant_intensity_gallery',
  'render_spectral_ray_transfer_gallery',
  'write_gallery_manifest',
)

GALLERY_MANIFEST_SCHEMA = 'plume.visualization.gallery@1'


@dataclass(frozen=True, slots=True)
class GalleryArtifact:
  """One deterministic file emitted by a product gallery."""

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
class VisualizationGalleryManifest:
  """Source-bound manifest for a static evaluation gallery."""

  schema: str
  product: str
  view_spec: VisualizationSpec
  source: Mapping[str, Any]
  product_metadata: Mapping[str, Any]
  artifacts: tuple[GalleryArtifact, ...]
  guardrails: tuple[str, ...]
  manifest_path: Path

  def model_dump(self) -> dict[str, Any]:
    return {
      'schema': self.schema,
      'product': self.product,
      'view_spec': self.view_spec.model_dump(mode='json'),
      'view_spec_digest_sha256': self.view_spec.digest_sha256(),
      'source': dict(self.source),
      'product_metadata': dict(self.product_metadata),
      'artifacts': [artifact.model_dump() for artifact in self.artifacts],
      'guardrails': list(self.guardrails),
    }
  ####

  def canonical_json(self) -> str:
    """Return deterministic manifest JSON without the local manifest path."""

    return json.dumps(
      self.model_dump(),
      allow_nan=False,
      ensure_ascii=True,
      indent=2,
      sort_keys=True,
    ) + '\n'
  ####
####


def _matplotlib() -> tuple[Any, Any, Any]:
  try:
    from matplotlib import pyplot as plt
    from matplotlib.colors import Normalize
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
  except ImportError as error:
    raise RuntimeError('visualization galleries require the optional plot dependency: pip install .[plot]') from error
  ####
  return plt, Normalize, Poly3DCollection
####


def _resolve_spec(
  result: ProductResult,
  spec: VisualizationSpec | None,
  *,
  default_view_kind: str,
  product_prefix: str,
) -> VisualizationSpec:
  resolved = spec or VisualizationSpec.for_result(result, view_kind=default_view_kind)
  resolved.validate_for_result(result)
  if not resolved.view_kind.startswith(f'{product_prefix}.'):
    raise ValueError(
      f'view spec {resolved.view_kind!r} is not valid for the {product_prefix} product'
    )
  ####
  return resolved
####


def _source_metadata(result: ProductResult) -> dict[str, Any]:
  envelope = result.envelope
  payload_metadata: dict[str, Any] = {}
  for name in ('provenance', 'applicability', 'uncertainty'):
    value = getattr(result.payload, name, None)
    if value is None:
      continue
    ####
    payload_metadata[name] = value.model_dump(mode='json') if hasattr(value, 'model_dump') else value
  ####
  return {
    'capability_id': envelope.capability_id,
    'schema_version': envelope.schema_version,
    'provider_id': str(envelope.provider_id),
    'session_id': str(envelope.session_id),
    'snapshot_id': str(envelope.snapshot_id),
    'content_sha256': envelope.content_sha256,
    'requested_time_s': envelope.requested_time_s,
    'actual_time_s': envelope.actual_time_s,
    'frame': envelope.frame.model_dump(mode='json'),
    'status': envelope.status.value,
    'fidelity': envelope.fidelity.model_dump(mode='json'),
    'applicability': envelope.applicability.model_dump(mode='json'),
    'provenance': envelope.provenance.model_dump(mode='json'),
    'derivation': [step.model_dump(mode='json') for step in envelope.derivation],
    'warnings': list(envelope.warnings),
    'payload_metadata': payload_metadata,
  }
####


def _write_gallery_manifest(manifest: VisualizationGalleryManifest) -> Path:
  manifest.manifest_path.parent.mkdir(parents=True, exist_ok=True)
  manifest.manifest_path.write_text(manifest.canonical_json(), encoding='utf-8')
  return manifest.manifest_path
####


def write_gallery_manifest(manifest: VisualizationGalleryManifest, path: str | Path | None = None) -> Path:
  """Write a gallery manifest to a chosen path."""

  output = manifest.manifest_path if path is None else Path(path)
  rewritten = VisualizationGalleryManifest(
    schema=manifest.schema,
    product=manifest.product,
    view_spec=manifest.view_spec,
    source=manifest.source,
    product_metadata=manifest.product_metadata,
    artifacts=manifest.artifacts,
    guardrails=manifest.guardrails,
    manifest_path=output,
  )
  return _write_gallery_manifest(rewritten)
####


def _manifest(
  result: ProductResult,
  spec: VisualizationSpec,
  output: Path,
  product: str,
  product_metadata: Mapping[str, Any],
  artifacts: Sequence[GalleryArtifact],
  guardrails: Sequence[str],
) -> VisualizationGalleryManifest:
  spec_path = output / 'visualization_spec.json'
  spec_path.write_text(json.dumps({
    'schema': 'plume.visualization.spec-export@1',
    'view_spec': spec.model_dump(mode='json'),
    'view_spec_digest_sha256': spec.digest_sha256(),
    'source': {
      'capability_id': result.envelope.capability_id,
      'schema_version': result.envelope.schema_version,
      'snapshot_id': str(result.envelope.snapshot_id),
      'content_sha256': result.envelope.content_sha256,
      'frame_id': result.envelope.frame.frame_id,
    },
  }, indent=2, sort_keys=True) + '\n', encoding='utf-8')
  all_artifacts = (GalleryArtifact('metadata.visualization-spec', spec_path.name, 'application/json'), *artifacts)
  manifest = VisualizationGalleryManifest(
    schema=GALLERY_MANIFEST_SCHEMA,
    product=product,
    view_spec=spec,
    source=_source_metadata(result),
    product_metadata=product_metadata,
    artifacts=all_artifacts,
    guardrails=tuple(guardrails),
    manifest_path=output / 'gallery_manifest.json',
  )
  _write_gallery_manifest(manifest)
  return manifest
####


def _save(figure: Any, path: Path, *, title: str, result: ProductResult, spec: VisualizationSpec) -> None:
  envelope = result.envelope
  figure.suptitle(
    f'{title}\n{envelope.capability_id} | {envelope.fidelity.model_fidelity.value} | '
    f'{envelope.fidelity.validation_level.value} | frame={envelope.frame.frame_id}',
    fontsize=10,
  )
  figure.tight_layout(rect=(0.0, 0.0, 1.0, 0.91))
  figure.savefig(path, dpi=140, metadata={
    'SourceCapability': envelope.capability_id,
    'SourceContentSHA256': envelope.content_sha256,
    'VisualizationSpecSHA256': spec.digest_sha256(),
  })
####


def _prepare_values(
  values: Sequence[float | None],
  spec: VisualizationSpec,
  *,
  label: str,
) -> tuple[float | None, ...]:
  prepared: list[float | None] = []
  for value in values:
    if value is None:
      if spec.invalid_sample_policy is InvalidSamplePolicy.REJECT:
        raise ValueError(f'{label} contains an invalid sample')
      ####
      prepared.append(None)
      continue
    ####
    if spec.y_scale is AxisScale.LOG10 and value <= 0.:
      if spec.invalid_sample_policy is InvalidSamplePolicy.REJECT:
        raise ValueError(f'{label} contains a non-positive sample for a log10 axis')
      ####
      prepared.append(None)
      continue
    ####
    prepared.append(float(value))
  ####
  return tuple(prepared)
####


def _apply_x_scale(axis: Any, spec: VisualizationSpec, values: Sequence[float]) -> None:
  if spec.x_scale is AxisScale.LOG10:
    if any(value <= 0. for value in values):
      raise ValueError('log10 x-axis requires strictly positive x samples')
    ####
    axis.set_xscale('log')
  ####
####


def _apply_y_scale(axis: Any, spec: VisualizationSpec, values: Sequence[float | None]) -> None:
  if spec.y_scale is AxisScale.LOG10:
    finite_values = tuple(value for value in values if value is not None and value > 0.)
    if not finite_values:
      raise ValueError('log10 y-axis requires at least one positive sample')
    ####
    axis.set_yscale('log')
  ####
####


def _wavelength_axis(grid: SpectralRadiantIntensityGrid | Any, spec: VisualizationSpec) -> tuple[tuple[float, ...], str, float]:
  unit = spec.wavelength_display_unit or WavelengthDisplayUnit.UM
  if unit is WavelengthDisplayUnit.M:
    return tuple(grid.wavelengths_m), 'Wavelength [m]', 1.0
  ####
  if unit is WavelengthDisplayUnit.NM:
    return tuple(value * 1.0e9 for value in grid.wavelengths_m), 'Wavelength [nm]', 1.0e9
  ####
  return tuple(value * 1.0e6 for value in grid.wavelengths_m), 'Wavelength [μm]', 1.0e6
####


def _masked_matrix(
  rows: Sequence[Sequence[float | None]],
  spec: VisualizationSpec,
  *,
  label: str,
) -> list[list[float]]:
  matrix: list[list[float]] = []
  for row in rows:
    prepared = _prepare_values(row, spec, label=label)
    matrix.append([float('nan') if value is None else value for value in prepared])
  ####
  return matrix
####


def _set_equal_2d(axis: Any) -> None:
  axis.set_aspect('equal', adjustable='datalim')
  axis.grid(True, alpha=0.22)
####


def _set_3d_bounds(axis: Any, points: Sequence[tuple[float, float, float]]) -> None:
  if not points:
    return
  ####
  lower = tuple(min(point[index] for point in points) for index in range(3))
  upper = tuple(max(point[index] for point in points) for index in range(3))
  extents = tuple(max(upper[index] - lower[index], 1.0e-6) for index in range(3))
  extent = max(extents)
  center = tuple((lower[index] + upper[index]) / 2. for index in range(3))
  axis.set_xlim(center[0] - extent / 2., center[0] + extent / 2.)
  axis.set_ylim(center[1] - extent / 2., center[1] + extent / 2.)
  axis.set_zlim(center[2] - extent / 2., center[2] + extent / 2.)
  axis.set_box_aspect(extents)
####


def _apply_camera(axis: Any, spec: VisualizationSpec) -> None:
  if spec.camera is not None:
    axis.view_init(elev=spec.camera.elevation_deg, azim=spec.camera.azimuth_deg)
  ####
####


def _visual_channel_colors(
  plt: Any,
  normalize_type: Any,
  mesh: SectionedTubeRenderMesh,
  channel: SectionedTubeChannelLine | None,
  spec: VisualizationSpec,
) -> tuple[Any, Any | None]:
  if channel is None:
    return '#4c78a8', None
  ####
  prepared = _prepare_values(channel.values, spec, label=f'channel {channel.channel_id}')
  finite_values = tuple(value for value in prepared if value is not None)
  if not finite_values:
    return '#bdbdbd', None
  ####
  minimum = min(finite_values)
  maximum = max(finite_values)
  normalizer = normalize_type(vmin=minimum, vmax=maximum if maximum > minimum else minimum + 1.0)
  cmap = plt.get_cmap(spec.color_map)
  colors = [
    '#bdbdbd' if prepared[index] is None else cmap(normalizer(prepared[index]))
    for index in mesh.face_section_indices
  ]
  return colors, normalizer
####


def render_sectioned_tube_gallery(
  result: SectionedTubeResult,
  output_dir: str | Path,
  *,
  spec: VisualizationSpec | None = None,
) -> VisualizationGalleryManifest:
  """Render geometry overview, orthographic projections, channels, and mesh QA."""

  resolved = _resolve_spec(
    result,
    spec,
    default_view_kind='visual.gallery',
    product_prefix='visual',
  )
  projection = project_sectioned_tube_view(result, resolved)
  mesh = build_sectioned_tube_render_mesh(result, radial_segments=resolved.mesh_radial_segments)
  output = Path(output_dir)
  output.mkdir(parents=True, exist_ok=True)
  plt, normalize_type, poly_collection_type = _matplotlib()

  overview_path = output / 'visual_overview.png'
  figure = plt.figure(figsize=(8.5, 6.5))
  axis = figure.add_subplot(111, projection='3d')
  polygons = [[mesh.vertices[index] for index in face] for face in mesh.faces]
  colors, normalizer = _visual_channel_colors(plt, normalize_type, mesh, projection.selected_channel, resolved)
  axis.add_collection3d(poly_collection_type(polygons, facecolor=colors, edgecolor='none', alpha=0.84))
  centerline = projection.data.geometry.centerline_m
  axis.plot(
    [point[0] for point in centerline],
    [point[1] for point in centerline],
    [point[2] for point in centerline],
    color='black',
    linewidth=1.2,
    label='contract centerline',
  )
  selected_center = projection.station_center_m
  axis.scatter([selected_center[0]], [selected_center[1]], [selected_center[2]], color='crimson', s=32, label=f'station {projection.station_index}')
  _set_3d_bounds(axis, tuple(mesh.vertices) + (selected_center,))
  axis.set_xlabel('x [m]')
  axis.set_ylabel('y [m]')
  axis.set_zlabel('z [m]')
  axis.legend(loc='upper left', fontsize=8)
  _apply_camera(axis, resolved)
  if normalizer is not None:
    figure.colorbar(plt.cm.ScalarMappable(norm=normalizer, cmap=resolved.color_map), ax=axis, label=projection.selected_channel.unit if projection.selected_channel else '')
  _save(figure, overview_path, title='Sectioned-tube geometry overview', result=result, spec=resolved)
  plt.close(figure)

  projections_path = output / 'visual_projections.png'
  figure, axes = plt.subplots(2, 2, figsize=(9.0, 8.0))
  pairs = ((0, 1, 'XY'), (0, 2, 'XZ'), (1, 2, 'YZ'))
  axis_names = ('x', 'y', 'z')
  for axis, (first, second, name) in zip(axes.flat[:3], pairs, strict=True):
    axis.plot(
      [point[first] for point in centerline],
      [point[second] for point in centerline],
      color='#4c78a8',
      marker='o',
      markersize=3,
    )
    axis.scatter([selected_center[first]], [selected_center[second]], color='crimson', s=32)
    axis.set_xlabel(f'{axis_names[first]} [m]')
    axis.set_ylabel(f'{axis_names[second]} [m]')
    axis.set_title(f'{name} projection')
    _set_equal_2d(axis)
  ####
  cross_axis = axes[1, 1]
  semi_axis_1, semi_axis_2 = projection.station_semi_axes_m
  theta = tuple(2. * pi * index / 128. for index in range(129))
  cross_axis.plot(
    [semi_axis_1 * cos(value) for value in theta],
    [semi_axis_2 * sin(value) for value in theta],
    color='#f58518',
  )
  cross_axis.axhline(0., color='black', linewidth=0.6)
  cross_axis.axvline(0., color='black', linewidth=0.6)
  cross_axis.set_xlabel('local normal_1 [m]')
  cross_axis.set_ylabel('local normal_2 [m]')
  cross_axis.set_title(f'station {projection.station_index} cross-section')
  station_values = tuple(
    f'{channel.channel_id}[{channel.component_index}]: '
    f'{channel.values[projection.station_index]!s} {channel.unit}'
    for channel in projection.data.channels
  )
  inspector_lines = (
    f'center [m]: {tuple(round(value, 4) for value in projection.station_center_m)}',
    f'tangent: {tuple(round(value, 4) for value in projection.data.geometry.tangent[projection.station_index])}',
    f'normal_1: {tuple(round(value, 4) for value in projection.station_normal_1)}',
    f'normal_2: {tuple(round(value, 4) for value in projection.station_normal_2)}',
    f'radii [m]: ({semi_axis_1:g}, {semi_axis_2:g})',
    'feature values:',
    *station_values,
  )
  cross_axis.text(
    0.02,
    0.98,
    '\n'.join(inspector_lines),
    transform=cross_axis.transAxes,
    va='top',
    fontsize=6.5,
    bbox={'facecolor': 'white', 'alpha': 0.72, 'edgecolor': 'none'},
  )
  _set_equal_2d(cross_axis)
  _save(figure, projections_path, title='Sectioned-tube orthographic projections', result=result, spec=resolved)
  plt.close(figure)

  channels_path = output / 'visual_channels.png'
  channel_count = max(len(projection.data.channels), 1)
  figure, channel_axes = plt.subplots(channel_count, 1, figsize=(9.0, max(3.5, 2.6 * channel_count)), squeeze=False, sharex=True)
  if not projection.data.channels:
    channel_axes[0, 0].text(0.5, 0.5, 'No feature channels declared by the contract', ha='center', va='center')
    channel_axes[0, 0].set_axis_off()
  else:
    for axis, channel in zip(channel_axes[:, 0], projection.data.channels, strict=True):
      values = _prepare_values(channel.values, resolved, label=f'channel {channel.channel_id}')
      color = '#d62728' if projection.selected_channel is channel else '#4c78a8'
      axis.plot(channel.arc_length_m, values, marker='o', color=color, label=f'{channel.channel_id}[{channel.component_index}] — {channel.semantic} [{channel.unit}]')
      _apply_x_scale(axis, resolved, channel.arc_length_m)
      _apply_y_scale(axis, resolved, values)
      axis.set_ylabel(channel.unit)
      axis.grid(True, alpha=0.22)
      axis.legend(loc='best', fontsize=8)
    ####
    channel_axes[-1, 0].set_xlabel('Arc length [m]')
  ####
  _save(figure, channels_path, title='Sectioned-tube feature channels', result=result, spec=resolved)
  plt.close(figure)

  qa_path = output / 'visual_mesh_qa.png'
  figure, qa_axis = plt.subplots(figsize=(8.5, 5.0))
  qa_axis.set_axis_off()
  finite_vertices = all(all(isfinite(value) for value in vertex) for vertex in mesh.vertices)
  valid_faces = all(len(face) == 3 and all(0 <= index < len(mesh.vertices) for index in face) for face in mesh.faces)
  degenerate_faces = sum(1 for face in mesh.faces if len(set(face)) < 3)
  qa_lines = (
    f'finite vertices: {finite_vertices}',
    f'valid face indices: {valid_faces}',
    f'degenerate faces: {degenerate_faces}',
    f'sections: {mesh.section_count}   radial segments: {mesh.radial_segments}',
    f'vertices: {len(mesh.vertices)}   faces: {len(mesh.faces)}',
    f'bounds min [m]: {tuple(round(value, 6) for value in mesh.minimum_m)}',
    f'bounds max [m]: {tuple(round(value, 6) for value in mesh.maximum_m)}',
    f'declared feature channels: {len(mesh.feature_channels)}',
    'shock diamonds/regions/endpoints: not inferred from geometry',
  )
  qa_axis.text(0.03, 0.96, '\n'.join(qa_lines), va='top', family='monospace', fontsize=10)
  _save(figure, qa_path, title='Sectioned-tube mesh and contract QA', result=result, spec=resolved)
  plt.close(figure)

  artifacts = (
    GalleryArtifact('visual.overview', overview_path.name, 'image/png'),
    GalleryArtifact('visual.projections', projections_path.name, 'image/png'),
    GalleryArtifact('visual.channels', channels_path.name, 'image/png'),
    GalleryArtifact('visual.mesh-qa', qa_path.name, 'image/png'),
  )
  return _manifest(
    result,
    resolved,
    output,
    'sectioned-tube-visual',
    {
      'section_count': mesh.section_count,
      'radial_segments': mesh.radial_segments,
      'channel_count': len(mesh.feature_channels),
      'selected_station_index': projection.station_index,
      'selected_channel_id': projection.selected_channel.channel_id if projection.selected_channel else None,
      'selected_component_index': projection.selected_channel.component_index if projection.selected_channel else None,
    },
    artifacts,
    (
      'shock_diamonds_regions_and_physical_endpoints_are_not_inferred_from_geometry',
      'radiance_ray_transfer_and_focal_plane_values_are_not_derived_from_geometry',
    ),
  )
####


def _signature_direction_table(grid: SpectralRadiantIntensityGrid, output: Path) -> Path:
  path = output / 'signature_direction_table.csv'
  with path.open('w', encoding='utf-8', newline='') as stream:
    writer = csv.writer(stream)
    writer.writerow(('direction_index', 'direction_x', 'direction_y', 'direction_z', 'valid_sample_count'))
    for index, (direction, values, mask) in enumerate(zip(grid.directions, grid.radiant_intensity_W_sr_m, grid.validity_mask, strict=True)):
      writer.writerow((index, *direction, sum(1 for value, valid in zip(values, mask, strict=True) if valid)))
    ####
  ####
  return path
####


def render_spectral_radiant_intensity_gallery(
  result: SpectralRadiantIntensityResult,
  output_dir: str | Path,
  *,
  spec: VisualizationSpec | None = None,
) -> VisualizationGalleryManifest:
  """Render spectra, exact direction-index heatmaps, and a direction sphere."""

  resolved = _resolve_spec(
    result,
    spec,
    default_view_kind='signature.gallery',
    product_prefix='signature',
  )
  if resolved.wavelength_display_unit is None:
    resolved = resolved.model_copy(update={'wavelength_display_unit': WavelengthDisplayUnit.UM})
  ####
  projection = project_spectral_radiant_intensity_view(result, resolved)
  grid = projection.grid
  output = Path(output_dir)
  output.mkdir(parents=True, exist_ok=True)
  plt, normalize_type, _ = _matplotlib()
  wavelengths, wavelength_label, _ = _wavelength_axis(grid, resolved)
  rows = [_prepare_values(row, resolved, label='spectral radiant intensity') for row in grid.radiant_intensity_W_sr_m]

  spectrum_path = output / 'signature_spectra.png'
  figure, axis = plt.subplots(figsize=(9.0, 5.5))
  for direction_index, (direction, values) in enumerate(zip(grid.directions, rows, strict=True)):
    color = '#d62728' if direction_index == projection.direction_index else '#4c78a8'
    linewidth = 2.2 if direction_index == projection.direction_index else 1.0
    axis.plot(wavelengths, values, marker='o', color=color, linewidth=linewidth, label=f'direction {direction_index}: ({direction[0]:.3f}, {direction[1]:.3f}, {direction[2]:.3f})')
  _apply_x_scale(axis, resolved, wavelengths)
  all_values = tuple(value for row in rows for value in row)
  _apply_y_scale(axis, resolved, all_values)
  axis.set_xlabel(wavelength_label)
  axis.set_ylabel('Jλ [W sr⁻¹ m⁻¹]')
  axis.grid(True, alpha=0.22)
  axis.legend(loc='best', fontsize=8)
  _save(figure, spectrum_path, title='Spectral radiant intensity by exact direction', result=result, spec=resolved)
  plt.close(figure)

  heatmap_path = output / 'signature_heatmap.png'
  figure, axis = plt.subplots(figsize=(9.0, 5.5))
  matrix = _masked_matrix(grid.radiant_intensity_W_sr_m, resolved, label='spectral radiant intensity')
  cmap = plt.get_cmap(resolved.color_map).copy()
  cmap.set_bad(alpha=0.0)
  image = axis.imshow(matrix, aspect='auto', interpolation='nearest', origin='lower', cmap=cmap)
  axis.set_xlabel(wavelength_label)
  axis.set_ylabel('Direction index [1] — not an inferred angle')
  axis.set_xticks(range(len(wavelengths)))
  axis.set_xticklabels([f'{value:g}' for value in wavelengths], rotation=35, ha='right')
  axis.set_yticks(range(len(grid.directions)))
  axis.axhline(projection.direction_index, color='white', linewidth=1.3)
  figure.colorbar(image, ax=axis, label='Jλ [W sr⁻¹ m⁻¹]')
  _save(figure, heatmap_path, title='Spectral radiant-intensity direction/wavelength heatmap', result=result, spec=resolved)
  plt.close(figure)

  sphere_path = output / 'signature_direction_sphere.png'
  figure = plt.figure(figsize=(8.0, 6.5))
  axis = figure.add_subplot(111, projection='3d')
  values_at_wavelength = tuple(row[projection.wavelength_index] for row in grid.radiant_intensity_W_sr_m)
  finite_values = tuple(value for value in values_at_wavelength if value is not None)
  if finite_values:
    normalizer = normalize_type(vmin=min(finite_values), vmax=max(finite_values) if max(finite_values) > min(finite_values) else min(finite_values) + 1.0)
    cmap = plt.get_cmap(resolved.color_map)
    colors = ['#bdbdbd' if value is None else cmap(normalizer(value)) for value in values_at_wavelength]
  else:
    normalizer = None
    colors = ['#bdbdbd'] * len(grid.directions)
  ####
  for direction, color in zip(grid.directions, colors, strict=True):
    axis.scatter([direction[0]], [direction[1]], [direction[2]], color=[color], s=42)
  ####
  selected = projection.selected_direction
  axis.scatter([selected[0]], [selected[1]], [selected[2]], color='crimson', s=75, marker='x', label=f'direction {projection.direction_index}')
  _set_3d_bounds(axis, tuple(grid.directions))
  axis.set_xlabel('x direction cosine [1]')
  axis.set_ylabel('y direction cosine [1]')
  axis.set_zlabel('z direction cosine [1]')
  axis.legend(loc='upper left', fontsize=8)
  if normalizer is not None:
    figure.colorbar(plt.cm.ScalarMappable(norm=normalizer, cmap=resolved.color_map), ax=axis, label=f'Jλ at {wavelengths[projection.wavelength_index]:g}')
  _save(figure, sphere_path, title='Direction-unit-sphere view at selected wavelength', result=result, spec=resolved)
  plt.close(figure)

  table_path = _signature_direction_table(grid, output)
  artifacts = (
    GalleryArtifact('signature.spectra', spectrum_path.name, 'image/png'),
    GalleryArtifact('signature.heatmap', heatmap_path.name, 'image/png'),
    GalleryArtifact('signature.direction-sphere', sphere_path.name, 'image/png'),
    GalleryArtifact('signature.direction-table', table_path.name, 'text/csv'),
  )
  return _manifest(
    result,
    resolved,
    output,
    'spectral-radiant-intensity',
    {
      'direction_count': len(grid.directions),
      'wavelength_count': len(grid.wavelengths_m),
      'selected_direction_index': projection.direction_index,
      'selected_direction': projection.selected_direction,
      'selected_wavelength_index': projection.wavelength_index,
      'selected_wavelength_m': projection.selected_wavelength_m,
      'uncertainty_metadata': grid.uncertainty,
    },
    artifacts,
    (
      'direction_index_and_exact_3d_direction_are_used; no scalar_angle_is_invented',
      'invalid_signature_samples_remain_masked_or_gapped',
      'numeric_uncertainty_bands_require_a_declared_uncertainty_schema',
      'geometry_and_focal_plane_values_are_not_derived_from_signature_data',
    ),
  )
####


def _ray_table(data: Any, output: Path) -> Path:
  path = output / 'ray_transfer_table.csv'
  with path.open('w', encoding='utf-8', newline='') as stream:
    writer = csv.writer(stream)
    writer.writerow(('ray_id', 'origin_x_m', 'origin_y_m', 'origin_z_m', 'direction_x', 'direction_y', 'direction_z', 'item_status', 'valid_sample_count'))
    for line in data.lines:
      writer.writerow((line.ray_id, *line.origin_m, *line.direction, line.item_status.value, sum(1 for valid in line.validity_mask if valid)))
    ####
  ####
  return path
####


def _plot_ray_spectral_lines(
  axis: Any,
  lines: Sequence[SpectralRayTransferLine],
  wavelengths: Sequence[float],
  spec: VisualizationSpec,
  field: str,
  selected_ray_id: str,
) -> None:
  for index, line in enumerate(lines):
    raw_values = getattr(line, field)
    values = _prepare_values(raw_values, spec, label=f'{field} for ray {line.ray_id}')
    selected = line.ray_id == selected_ray_id
    color = '#d62728' if selected else '#4c78a8'
    axis.plot(wavelengths, values, marker='o', color=color, linewidth=2.0 if selected else 1.0, label=line.ray_id)
  ####
  _apply_x_scale(axis, spec, wavelengths)
####


def render_spectral_ray_transfer_gallery(
  result: SpectralRayTransferResult,
  output_dir: str | Path,
  *,
  spec: VisualizationSpec | None = None,
) -> VisualizationGalleryManifest:
  """Render ray geometry, separate spectra, heatmaps, and a ray table."""

  resolved = _resolve_spec(
    result,
    spec,
    default_view_kind='ray-transfer.gallery',
    product_prefix='ray-transfer',
  )
  if resolved.wavelength_display_unit is None:
    resolved = resolved.model_copy(update={'wavelength_display_unit': WavelengthDisplayUnit.UM})
  ####
  projection = project_spectral_ray_transfer_view(result, resolved)
  data = projection.data
  output = Path(output_dir)
  output.mkdir(parents=True, exist_ok=True)
  plt, _, _ = _matplotlib()
  wavelengths, wavelength_label, _ = _wavelength_axis(data, resolved)

  bundle_path = output / 'ray_transfer_bundle.png'
  figure = plt.figure(figsize=(8.5, 6.5))
  axis = figure.add_subplot(111, projection='3d')
  display_length = resolved.ray_display_length_m
  points: list[tuple[float, float, float]] = []
  for index, line in enumerate(data.lines):
    end = (
      line.origin_m[0] + display_length * line.direction[0],
      line.origin_m[1] + display_length * line.direction[1],
      line.origin_m[2] + display_length * line.direction[2],
    )
    points.extend((line.origin_m, end))
    color = 'crimson' if index == projection.ray_index else '#4c78a8'
    axis.plot((line.origin_m[0], end[0]), (line.origin_m[1], end[1]), (line.origin_m[2], end[2]), color=color, linewidth=2.0 if index == projection.ray_index else 1.0)
    axis.scatter([line.origin_m[0]], [line.origin_m[1]], [line.origin_m[2]], color=color, s=30)
  ####
  _set_3d_bounds(axis, points)
  axis.set_xlabel('x [m]')
  axis.set_ylabel('y [m]')
  axis.set_zlabel('z [m]')
  axis.set_title(f'Ray display length = {display_length:g} m; length is a visualization setting')
  _apply_camera(axis, resolved)
  _save(figure, bundle_path, title='Spectral ray-transfer origin/direction bundle', result=result, spec=resolved)
  plt.close(figure)

  spectra_path = output / 'ray_transfer_spectra.png'
  figure, axes = plt.subplots(2, 1, figsize=(9.0, 8.0), sharex=True)
  selected_ray_id = projection.selected_line.ray_id
  _plot_ray_spectral_lines(axes[0], data.lines, wavelengths, resolved, 'source_radiance_W_m2_sr_m', selected_ray_id)
  _plot_ray_spectral_lines(axes[1], data.lines, wavelengths, resolved, 'background_transmittance', selected_ray_id)
  axes[0].set_ylabel('Source radiance [W m⁻² sr⁻¹ m⁻¹]')
  axes[1].set_ylabel('Background transmittance [1]')
  axes[1].set_xlabel(wavelength_label)
  axes[0].set_title('Source radiance')
  axes[1].set_title('Background transmittance — separate field')
  for axis in axes:
    axis.grid(True, alpha=0.22)
    axis.legend(loc='best', fontsize=8)
  ####
  _save(figure, spectra_path, title='Spectral ray-transfer fields', result=result, spec=resolved)
  plt.close(figure)

  heatmap_path = output / 'ray_transfer_heatmaps.png'
  figure, axes = plt.subplots(2, 1, figsize=(9.0, 8.0), sharex=True)
  source_matrix = _masked_matrix([line.source_radiance_W_m2_sr_m for line in data.lines], resolved, label='source radiance')
  transmittance_matrix = _masked_matrix([line.background_transmittance for line in data.lines], resolved, label='background transmittance')
  source_image = axes[0].imshow(source_matrix, aspect='auto', interpolation='nearest', origin='lower', cmap=resolved.color_map)
  transmittance_image = axes[1].imshow(transmittance_matrix, aspect='auto', interpolation='nearest', origin='lower', cmap=resolved.color_map, vmin=0., vmax=1.)
  axes[0].set_ylabel('Ray index [1]')
  axes[1].set_ylabel('Ray index [1]')
  axes[1].set_xlabel(wavelength_label)
  for axis in axes:
    axis.set_xticks(range(len(wavelengths)))
    axis.set_xticklabels([f'{value:g}' for value in wavelengths], rotation=35, ha='right')
    axis.set_yticks(range(len(data.lines)))
    axis.set_yticklabels([line.ray_id for line in data.lines])
  axes[0].set_title('Source radiance heatmap')
  axes[1].set_title('Background transmittance heatmap')
  figure.colorbar(source_image, ax=axes[0], label='source radiance')
  figure.colorbar(transmittance_image, ax=axes[1], label='transmittance')
  _save(figure, heatmap_path, title='Ray-transfer field heatmaps', result=result, spec=resolved)
  plt.close(figure)

  table_path = _ray_table(data, output)
  artifacts = (
    GalleryArtifact('ray-transfer.bundle', bundle_path.name, 'image/png'),
    GalleryArtifact('ray-transfer.spectra', spectra_path.name, 'image/png'),
    GalleryArtifact('ray-transfer.heatmaps', heatmap_path.name, 'image/png'),
    GalleryArtifact('ray-transfer.table', table_path.name, 'text/csv'),
  )
  selected_line = projection.selected_line
  return _manifest(
    result,
    resolved,
    output,
    'spectral-ray-transfer',
    {
      'ray_count': len(data.lines),
      'wavelength_count': len(data.wavelengths_m),
      'selected_ray_index': projection.ray_index,
      'selected_ray_id': selected_line.ray_id,
      'selected_wavelength_index': projection.wavelength_index,
      'selected_wavelength_m': projection.selected_wavelength_m,
      'ray_display_length_m': display_length,
      'item_statuses': {line.ray_id: line.item_status.value for line in data.lines},
    },
    artifacts,
    (
      'source_radiance_and_background_transmittance_are_rendered_as_separate_fields',
      'hit_miss_intersections_and_optical_depth_are_not_inferred_from_returned_values',
      'ray_display_length_is_not_a_physical_intersection_or_path_length',
      'focal_plane_values_are_not_derived_without_an_explicit_detector_operator',
    ),
  )
####


def _flux_values_table(glyph: PlumeFluxSectionGlyph, output: Path) -> Path:
  path = output / 'flux_values.csv'
  with path.open('w', encoding='utf-8', newline='') as stream:
    writer = csv.writer(stream)
    writer.writerow(('quantity', 'component', 'value', 'unit'))
    writer.writerow(('area', '', glyph.area_m2, 'm^2'))
    writer.writerow(('mass_flow', '', glyph.mass_flow_kgps, 'kg/s'))
    writer.writerow(('total_energy_flow', '', glyph.total_energy_flow_W, 'W'))
    writer.writerow(('pressure', '', glyph.pressure_Pa, 'Pa'))
    writer.writerow(('ambient_pressure', '', glyph.ambient_pressure_Pa, 'Pa'))
    writer.writerow(('pressure_match_relative_residual', '', glyph.pressure_match_relative_residual, '1'))
    for component, value in enumerate(glyph.momentum_flux_N):
      writer.writerow(('momentum_flux', component, value, 'N'))
    for species_id, value in glyph.species_mass_flows_kgps:
      writer.writerow(('species_mass_flow', species_id, value, 'kg/s'))
    ####
  ####
  return path
####


def _ellipse_points(moment: tuple[tuple[float, float], tuple[float, float]]) -> tuple[tuple[float, float], ...]:
  a, b = moment[0]
  _, d = moment[1]
  trace = a + d
  discriminant = sqrt(max(0., (a - d) * (a - d) + 4. * b * b))
  eigen_1 = max(0., (trace + discriminant) / 2.)
  eigen_2 = max(0., (trace - discriminant) / 2.)
  angle = 0.5 * atan2(2. * b, a - d) if abs(b) > 0. or abs(a - d) > 0. else 0.
  radius_1 = sqrt(eigen_1)
  radius_2 = sqrt(eigen_2)
  return tuple(
    (
      radius_1 * cos(value) * cos(angle) - radius_2 * sin(value) * sin(angle),
      radius_1 * cos(value) * sin(angle) + radius_2 * sin(value) * cos(angle),
    )
    for value in tuple(2. * pi * index / 128. for index in range(129))
  )
####


def render_plume_flux_gallery(
  result: PlumeFluxSectionResult,
  output_dir: str | Path,
  *,
  spec: VisualizationSpec | None = None,
) -> VisualizationGalleryManifest:
  """Render section pose/normal, momentum, scalars, species, and moments."""

  resolved = _resolve_spec(
    result,
    spec,
    default_view_kind='flux.gallery',
    product_prefix='flux',
  )
  projection = project_plume_flux_view(result, resolved)
  glyph = projection.glyph
  output = Path(output_dir)
  output.mkdir(parents=True, exist_ok=True)
  plt, _, _ = _matplotlib()

  vectors_path = output / 'flux_vectors.png'
  figure = plt.figure(figsize=(10.0, 4.5))
  normal_axis = figure.add_subplot(121, projection='3d')
  normal_axis.quiver(0., 0., 0., glyph.normal[0], glyph.normal[1], glyph.normal[2], length=1.0, normalize=True, color='#54a24b')
  normal_axis.scatter([0.], [0.], [0.], color='black', s=25)
  normal_axis.set_xlim(-1.2, 1.2)
  normal_axis.set_ylim(-1.2, 1.2)
  normal_axis.set_zlim(-1.2, 1.2)
  normal_axis.set_box_aspect((1., 1., 1.))
  normal_axis.set_title('section normal glyph\n(normalized display)')
  normal_axis.set_xlabel('normal x [1]')
  normal_axis.set_ylabel('normal y [1]')
  normal_axis.set_zlabel('normal z [1]')
  momentum_axis = figure.add_subplot(122)
  momentum_axis.bar(('x', 'y', 'z'), glyph.momentum_flux_N, color=('#4c78a8', '#f58518', '#e45756'))
  momentum_axis.set_ylabel('Momentum flux [N]')
  momentum_axis.set_title('momentum-flux vector components')
  momentum_axis.grid(True, axis='y', alpha=0.22)
  _save(figure, vectors_path, title='Engineering flux vectors and pose direction', result=result, spec=resolved)
  plt.close(figure)

  scalar_path = output / 'flux_scalars.png'
  figure, axes = plt.subplots(2, 3, figsize=(12.0, 7.0))
  scalar_specs = (
    (axes[0, 0], 'area', glyph.area_m2, 'm²'),
    (axes[0, 1], 'mass flow', glyph.mass_flow_kgps, 'kg/s'),
    (axes[0, 2], 'total energy flow', glyph.total_energy_flow_W, 'W'),
    (axes[1, 0], 'pressure', glyph.pressure_Pa, 'Pa'),
    (axes[1, 1], 'ambient pressure', glyph.ambient_pressure_Pa, 'Pa'),
    (axes[1, 2], 'pressure residual', glyph.pressure_match_relative_residual, '1'),
  )
  for axis, title, value, unit in scalar_specs:
    axis.bar((title,), (value,), color='#4c78a8')
    axis.set_ylabel(unit)
    axis.set_title(f'{title}: {value:.6g} {unit}')
    axis.grid(True, axis='y', alpha=0.22)
  ####
  _save(figure, scalar_path, title='Engineering flux scalar summary', result=result, spec=resolved)
  plt.close(figure)

  cross_path = output / 'flux_cross_section.png'
  figure, axes = plt.subplots(1, 2, figsize=(10.0, 4.5))
  ellipse = _ellipse_points(glyph.cross_section_second_moment_m2)
  axes[0].plot([point[0] for point in ellipse], [point[1] for point in ellipse], color='#f58518')
  axes[0].scatter([0.], [0.], color='black', s=20)
  axes[0].set_aspect('equal', adjustable='datalim')
  axes[0].set_xlabel('local section axis 1 [m]')
  axes[0].set_ylabel('local section axis 2 [m]')
  axes[0].set_title('second-moment ellipse\n(sqrt-eigenvalue display)')
  axes[0].grid(True, alpha=0.22)
  species_ids = [species_id for species_id, _ in glyph.species_mass_flows_kgps]
  species_values = [value for _, value in glyph.species_mass_flows_kgps]
  colors = ['#d62728' if index == projection.species_index else '#4c78a8' for index in range(len(species_ids))]
  axes[1].bar(species_ids, species_values, color=colors)
  axes[1].set_ylabel('Mass flow [kg/s]')
  axes[1].set_title('species mass flows')
  axes[1].tick_params(axis='x', rotation=35)
  axes[1].grid(True, axis='y', alpha=0.22)
  _save(figure, cross_path, title='Engineering flux cross-section and species', result=result, spec=resolved)
  plt.close(figure)

  table_path = _flux_values_table(glyph, output)
  artifacts = (
    GalleryArtifact('flux.vectors', vectors_path.name, 'image/png'),
    GalleryArtifact('flux.scalars', scalar_path.name, 'image/png'),
    GalleryArtifact('flux.cross-section-species', cross_path.name, 'image/png'),
    GalleryArtifact('flux.values', table_path.name, 'text/csv'),
  )
  return _manifest(
    result,
    resolved,
    output,
    'engineering-flux-section',
    {
      'time_s': glyph.time_s,
      'section_frame_id': glyph.section_frame_id,
      'section_translation_m': glyph.section_translation_m,
      'species_count': len(glyph.species_mass_flows_kgps),
      'selected_species_index': projection.species_index,
      'selected_species': projection.selected_species,
      'uncertainty_metadata': result.payload.uncertainty,
    },
    artifacts,
    (
      'normal_glyph_is_a_display_vector_and_not_a_new_geometry_result',
      'second_moment_ellipse_is_derived_only_from_the_declared_second_moment',
      'ordered_section_or_time_trends_require_an_explicit_collection_contract',
      'visual_geometry_radiance_and_focal_plane_values_are_not_derived_from_flux',
    ),
  )
####


def render_product_gallery(
  result: ProductResult,
  output_dir: str | Path,
  *,
  spec: VisualizationSpec | None = None,
) -> VisualizationGalleryManifest:
  """Dispatch a strict ProductResult to its independent gallery."""

  if isinstance(result, SectionedTubeResult):
    return render_sectioned_tube_gallery(result, output_dir, spec=spec)
  ####
  if isinstance(result, SpectralRadiantIntensityResult):
    return render_spectral_radiant_intensity_gallery(result, output_dir, spec=spec)
  ####
  if isinstance(result, SpectralRayTransferResult):
    return render_spectral_ray_transfer_gallery(result, output_dir, spec=spec)
  ####
  if isinstance(result, PlumeFluxSectionResult):
    return render_plume_flux_gallery(result, output_dir, spec=spec)
  ####
  raise TypeError('result must be one of the standard exhaust_plume.api product results')
####
