"""User-facing MVP workflows for lookup-backed spectral signatures."""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass, replace
import hashlib
import json
from math import isfinite
from pathlib import Path
from typing import Any, Sequence

from exhaust_plume.api.v1 import (
  Pose,
  ProviderConfigurationError,
  SpectralSignatureRequest,
  SpectralSignatureResult,
  SPECTRAL_RADIANT_INTENSITY_V1,
)
from exhaust_plume.providers.signature_table import (
  SignatureTableConfiguration,
  SignatureTableDefinition,
  SignatureTableProvider,
)
from exhaust_plume.products.signature_timeline import (
  SignatureAngularBinning,
  SignatureTimeline,
  build_signature_angular_heatmap,
  build_signature_direction_series,
  direction_to_azimuth_elevation,
)
from exhaust_plume.products.workflow_gallery import GalleryArtifact

__all__ = (
  'evaluate_signature_table_asset',
  'load_signature_table_asset',
  'load_spectral_signature_request',
  'render_signature_plots',
  'render_signature_timeline_gallery',
  'SIGNATURE_TIMELINE_GALLERY_SCHEMA',
  'SignatureTimelineGalleryManifest',
  'write_signature_result_csv',
  'write_signature_result_json',
  'write_signature_table_asset',
)

_SIGNATURE_ASSET_SCHEMA = 'plume.signature.table-asset@1'
_SIGNATURE_REQUEST_SCHEMA = 'plume.signature.request@1'
SIGNATURE_TIMELINE_GALLERY_SCHEMA = 'plume.signature.angular-timeline-gallery@1'


@dataclass(frozen=True, slots=True)
class SignatureTimelineGalleryManifest:
  """Source-bound artifacts for an exact Signature time-series gallery."""

  schema: str
  product: str
  direction_frame_id: str
  wavelength_index: int
  wavelength_m: float
  times_s: tuple[float, ...]
  source_result_ids: tuple[str, ...]
  selected_direction_indices: tuple[int, ...]
  binning: SignatureAngularBinning
  artifacts: tuple[GalleryArtifact, ...]
  guardrails: tuple[str, ...]
  manifest_path: Path

  def model_dump(self) -> dict[str, Any]:
    return {
      'schema': self.schema,
      'product': self.product,
      'direction_frame_id': self.direction_frame_id,
      'wavelength_index': self.wavelength_index,
      'wavelength_m': self.wavelength_m,
      'times_s': list(self.times_s),
      'source_result_ids': list(self.source_result_ids),
      'selected_direction_indices': list(self.selected_direction_indices),
      'binning': {
        'azimuth_bin_count': self.binning.azimuth_bin_count,
        'elevation_bin_count': self.binning.elevation_bin_count,
      },
      'artifacts': [artifact.model_dump() for artifact in self.artifacts],
      'guardrails': list(self.guardrails),
    }
  ####

  def canonical_json(self) -> str:
    return json.dumps(
      self.model_dump(),
      allow_nan=False,
      ensure_ascii=True,
      indent=2,
      sort_keys=True,
    ) + '\n'
  ####
####


def _load_json(path: str | Path) -> dict[str, Any]:
  payload = json.loads(Path(path).read_text(encoding='utf-8'))
  if not isinstance(payload, dict):
    raise ValueError(f'{path} must contain a JSON object')
  ####
  return payload
####


def load_signature_table_asset(path: str | Path) -> SignatureTableDefinition:
  """Load a raw provider definition or the wrapped v1 signature asset."""

  asset_path = Path(path)
  raw_bytes = asset_path.read_bytes()
  payload = json.loads(raw_bytes.decode('utf-8'))
  if not isinstance(payload, dict):
    raise ValueError(f'{path} must contain a JSON object')
  ####
  if 'definition' in payload:
    schema = payload.get('asset_schema')
    if schema is not None and schema != _SIGNATURE_ASSET_SCHEMA:
      raise ValueError(f'unsupported signature asset schema: {schema}')
    ####
    payload = payload['definition']
  elif 'asset_schema' in payload:
    schema = payload.pop('asset_schema')
    if schema != _SIGNATURE_ASSET_SCHEMA:
      raise ValueError(f'unsupported signature asset schema: {schema}')
    ####
  ####
  if not isinstance(payload, dict):
    raise ValueError('signature table definition must be a JSON object')
  ####
  definition_payload = dict(payload)
  definition_payload.pop('asset_sha256', None)
  definition = SignatureTableDefinition(**definition_payload)
  return replace(definition, asset_sha256=hashlib.sha256(raw_bytes).hexdigest())
####


def write_signature_table_asset(definition: SignatureTableDefinition, path: str | Path) -> Path:
  """Write a canonical wrapped v1 signature asset."""

  if not isinstance(definition, SignatureTableDefinition):
    raise ProviderConfigurationError('definition must be SignatureTableDefinition')
  ####
  output = Path(path)
  output.parent.mkdir(parents=True, exist_ok=True)
  definition_payload = asdict(definition)
  definition_payload.pop('asset_sha256', None)
  payload = {
    'asset_schema': _SIGNATURE_ASSET_SCHEMA,
    'definition': definition_payload,
  }
  output.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')
  return output
####


def load_spectral_signature_request(path: str | Path) -> SpectralSignatureRequest:
  """Load a raw request or the wrapped v1 request asset."""

  payload = _load_json(path)
  if 'request' in payload:
    schema = payload.get('request_schema')
    if schema is not None and schema != _SIGNATURE_REQUEST_SCHEMA:
      raise ValueError(f'unsupported signature request schema: {schema}')
    ####
    payload = payload['request']
  elif 'request_schema' in payload:
    schema = payload.pop('request_schema')
    if schema != _SIGNATURE_REQUEST_SCHEMA:
      raise ValueError(f'unsupported signature request schema: {schema}')
    ####
  ####
  if not isinstance(payload, dict):
    raise ValueError('signature request must be a JSON object')
  ####
  return SpectralSignatureRequest(**payload)
####


def evaluate_signature_table_asset(
    definition: SignatureTableDefinition,
    request: SpectralSignatureRequest,
    *,
    configuration: SignatureTableConfiguration | None = None,
    time_s: float = 0.0,
) -> SpectralSignatureResult:
  """Evaluate one lookup asset through the public lifecycle."""

  if not isinstance(definition, SignatureTableDefinition):
    raise ProviderConfigurationError('definition must be SignatureTableDefinition')
  ####
  if not isinstance(request, SpectralSignatureRequest):
    raise ProviderConfigurationError('request must be SpectralSignatureRequest')
  ####
  provider = SignatureTableProvider(configuration)
  session = provider.create_session(definition=definition)
  snapshot = session.create_snapshot(
    time_s=time_s,
    source_pose=Pose(
      frame_id='world',
      translation_m=(0.0, 0.0, 0.0),
      rotation_xyzw=(0.0, 0.0, 0.0, 1.0),
    ),
    dynamic_state={},
    ambient_state={},
  )
  try:
    return snapshot.evaluate(SPECTRAL_RADIANT_INTENSITY_V1, request)
  finally:
    session.close()
  ####
####


def write_signature_result_json(result: SpectralSignatureResult, path: str | Path) -> Path:
  output = Path(path)
  output.parent.mkdir(parents=True, exist_ok=True)
  output.write_text(result.model_dump_json(indent=2), encoding='utf-8')
  return output
####


def _direction_cosines(definition: SignatureTableDefinition, request: SpectralSignatureRequest) -> tuple[float, ...]:
  return tuple(
    sum(direction[axis] * definition.axis_direction[axis] for axis in range(3))
    for direction in request.source_to_observer_directions
  )
####


def write_signature_result_csv(
    definition: SignatureTableDefinition,
    request: SpectralSignatureRequest,
    result: SpectralSignatureResult,
    path: str | Path,
) -> Path:
  """Write one long-form row per direction/wavelength sample."""

  if len(result.spectral_radiant_intensity) != len(request.source_to_observer_directions):
    raise ValueError('signature result and request direction counts do not match')
  ####
  output = Path(path)
  output.parent.mkdir(parents=True, exist_ok=True)
  direction_cosines = _direction_cosines(definition, request)
  with output.open('w', encoding='utf-8', newline='') as stream:
    writer = csv.writer(stream)
    writer.writerow((
      'direction_index',
      'direction_x',
      'direction_y',
      'direction_z',
      'direction_cosine',
      'wavelength_m',
      'spectral_radiant_intensity_w_sr_m',
      'valid',
      'status_code',
      'absolute_standard_uncertainty_w_sr_m',
    ))
    for direction_index, direction in enumerate(request.source_to_observer_directions):
      uncertainty_row = (
        result.absolute_standard_uncertainty[direction_index]
        if result.absolute_standard_uncertainty is not None
        else (None,) * len(request.wavelengths_m)
      )
      for wavelength_index, wavelength in enumerate(request.wavelengths_m):
        writer.writerow((
          direction_index,
          *direction,
          direction_cosines[direction_index],
          wavelength,
          result.spectral_radiant_intensity[direction_index][wavelength_index],
          result.validity_mask[direction_index][wavelength_index],
          result.direction_status[direction_index].code.value,
          uncertainty_row[wavelength_index],
        ))
      ####
    ####
  ####
  return output
####


def _matplotlib():
  try:
    from matplotlib import pyplot as plt
  except ImportError as error:
    raise RuntimeError('signature plots require the optional plot dependency: pip install .[plot]') from error
  ####
  return plt
####


def render_signature_plots(
    definition: SignatureTableDefinition,
    request: SpectralSignatureRequest,
    result: SpectralSignatureResult,
    output_dir: str | Path,
) -> tuple[Path, Path, Path]:
  """Render spectrum, angular-cut, and wavelength-angle heatmap PNGs."""

  plt = _matplotlib()
  output = Path(output_dir)
  output.mkdir(parents=True, exist_ok=True)
  wavelengths_um = tuple(wavelength * 1.0e6 for wavelength in request.wavelengths_m)
  direction_cosines = _direction_cosines(definition, request)
  valid_values = [
    [value if result.validity_mask[row_index][column_index] else float('nan') for column_index, value in enumerate(row)]
    for row_index, row in enumerate(result.spectral_radiant_intensity)
  ]

  spectrum_figure, spectrum_axes = plt.subplots(figsize=(8.0, 5.0))
  for row_index, (values, direction_cosine) in enumerate(zip(valid_values, direction_cosines, strict=True)):
    spectrum_axes.plot(wavelengths_um, values, marker='o', label=f'direction {row_index} (μ={direction_cosine:.3f})')
    if result.absolute_standard_uncertainty is not None:
      uncertainty = result.absolute_standard_uncertainty[row_index]
      lower = tuple(value - error if isfinite(value) else float('nan') for value, error in zip(values, uncertainty, strict=True))
      upper = tuple(value + error if isfinite(value) else float('nan') for value, error in zip(values, uncertainty, strict=True))
      spectrum_axes.fill_between(wavelengths_um, lower, upper, alpha=0.12)
    ####
  ####
  spectrum_axes.set_title('Spectral radiant intensity')
  spectrum_axes.set_xlabel('Wavelength [μm]')
  spectrum_axes.set_ylabel('Jλ [W sr⁻¹ m⁻¹]')
  spectrum_axes.grid(True, alpha=0.25)
  spectrum_axes.legend()
  spectrum_figure.tight_layout()
  spectrum_path = output / 'signature_spectrum.png'
  spectrum_figure.savefig(spectrum_path, dpi=140)
  plt.close(spectrum_figure)

  angular_figure, angular_axes = plt.subplots(figsize=(8.0, 5.0))
  sorted_indices = tuple(sorted(range(len(direction_cosines)), key=direction_cosines.__getitem__))
  if len(request.wavelengths_m) <= 4:
    angular_wavelength_indices = tuple(range(len(request.wavelengths_m)))
  else:
    angular_wavelength_indices = tuple(dict.fromkeys((0, len(request.wavelengths_m) // 2, len(request.wavelengths_m) - 1)))
  ####
  for wavelength_index in angular_wavelength_indices:
    angular_axes.plot(
      tuple(direction_cosines[index] for index in sorted_indices),
      tuple(valid_values[index][wavelength_index] for index in sorted_indices),
      marker='o',
      label=f'{wavelengths_um[wavelength_index]:g} μm',
    )
  ####
  angular_axes.set_title('Angular signature lookup')
  angular_axes.set_xlabel('Direction cosine to source axis [1]')
  angular_axes.set_ylabel('Jλ [W sr⁻¹ m⁻¹]')
  angular_axes.grid(True, alpha=0.25)
  angular_axes.legend()
  angular_figure.tight_layout()
  angular_path = output / 'signature_angular.png'
  angular_figure.savefig(angular_path, dpi=140)
  plt.close(angular_figure)

  heatmap_figure, heatmap_axes = plt.subplots(figsize=(8.0, 5.0))
  sorted_cosines = tuple(direction_cosines[index] for index in sorted_indices)
  matrix = tuple(tuple(valid_values[index]) for index in sorted_indices)
  image = heatmap_axes.pcolormesh(wavelengths_um, sorted_cosines, matrix, shading='auto')
  heatmap_figure.colorbar(image, ax=heatmap_axes, label='Jλ [W sr⁻¹ m⁻¹]')
  heatmap_axes.set_title('Spectral/angular lookup')
  heatmap_axes.set_xlabel('Wavelength [μm]')
  heatmap_axes.set_ylabel('Direction cosine to source axis [1]')
  heatmap_figure.tight_layout()
  heatmap_path = output / 'signature_heatmap.png'
  heatmap_figure.savefig(heatmap_path, dpi=140)
  plt.close(heatmap_figure)
  return spectrum_path, angular_path, heatmap_path
####


def _timeline_plot_dependencies() -> tuple[Any, Any]:
  try:
    from matplotlib import pyplot as plt
    import numpy as np
  except ImportError as error:
    raise RuntimeError(
      'signature timeline galleries require the optional plot dependency: pip install .[plot]'
    ) from error
  ####
  return plt, np
####


def _write_signature_timeline_tables(
  timeline: SignatureTimeline,
  selected_direction_indices: Sequence[int],
  wavelength_index: int,
  output: Path,
) -> tuple[Path, Path]:
  direction_path = output / 'signature_timeline_direction_series.csv'
  with direction_path.open('w', encoding='utf-8', newline='') as stream:
    writer = csv.writer(stream)
    writer.writerow((
      'time_s',
      'direction_index',
      'direction_x',
      'direction_y',
      'direction_z',
      'azimuth_deg',
      'elevation_deg',
      'wavelength_m',
      'spectral_radiant_intensity_w_sr_m',
      'absolute_standard_uncertainty_w_sr_m',
      'valid',
      'status_code',
      'source_result_id',
    ))
    for sample in timeline.samples:
      for direction_index in selected_direction_indices:
        series_value = sample.result.spectral_radiant_intensity[direction_index][wavelength_index]
        valid = sample.result.validity_mask[direction_index][wavelength_index]
        direction = timeline.directions[direction_index]
        coordinates = direction_to_azimuth_elevation(direction)
        uncertainty = (
          sample.result.absolute_standard_uncertainty[direction_index][wavelength_index]
          if valid and sample.result.absolute_standard_uncertainty is not None
          else None
        )
        writer.writerow((
          sample.time_s,
          direction_index,
          *direction,
          coordinates.azimuth_deg,
          coordinates.elevation_deg,
          timeline.wavelengths_m[wavelength_index],
          series_value if valid else None,
          uncertainty,
          valid,
          sample.result.direction_status[direction_index].code.value,
          sample.result.metadata.result_id,
        ))
      ####
    ####
  ####

  trajectory_path = output / 'signature_source_trajectory.csv'
  trajectory = timeline.source_trajectory()
  with trajectory_path.open('w', encoding='utf-8', newline='') as stream:
    writer = csv.writer(stream)
    writer.writerow(('time_s', 'frame_id', 'x_m', 'y_m', 'z_m', 'source_result_id'))
    for sample, position in zip(timeline.samples, trajectory.positions_m, strict=True):
      writer.writerow((sample.time_s, trajectory.frame_id, *position, sample.result.metadata.result_id))
    ####
  ####
  return direction_path, trajectory_path
####


def render_signature_timeline_gallery(
  timeline: SignatureTimeline,
  output_dir: str | Path,
  *,
  wavelength_index: int = 0,
  direction_indices: Sequence[int] | None = None,
  binning: SignatureAngularBinning | None = None,
) -> SignatureTimelineGalleryManifest:
  """Render exact-time angular, direction-series, and source-trajectory views.

  The gallery is a presentation layer over :class:`SignatureTimeline`.  It
  never interpolates time, fills an invalid sample with zero, or changes the
  direction frame.  Heatmap cells are display aggregates in the declared
  azimuth/elevation convention; the source-result IDs and CSV tables retain
  the exact product lineage behind every view.
  """

  if not isinstance(timeline, SignatureTimeline):
    raise TypeError('timeline must be SignatureTimeline')
  ####
  selected_binning = binning or SignatureAngularBinning()
  if not isinstance(selected_binning, SignatureAngularBinning):
    raise TypeError('binning must be SignatureAngularBinning or None')
  ####
  selected_direction_indices = tuple(
    range(len(timeline.directions))
    if direction_indices is None
    else direction_indices
  )
  if not selected_direction_indices:
    raise ValueError('direction_indices must contain at least one direction')
  ####
  series = tuple(
    build_signature_direction_series(
      timeline,
      direction_index=direction_index,
      wavelength_index=wavelength_index,
    )
    for direction_index in selected_direction_indices
  )
  heatmaps = tuple(
    build_signature_angular_heatmap(
      timeline,
      time_s=time_s,
      wavelength_index=wavelength_index,
      binning=selected_binning,
    )
    for time_s in timeline.times_s
  )
  output = Path(output_dir)
  output.mkdir(parents=True, exist_ok=True)
  plt, np = _timeline_plot_dependencies()

  finite_heatmap_values = tuple(
    cell.mean_spectral_radiant_intensity_w_sr_m
    for heatmap in heatmaps
    for cell in heatmap.cells
    if cell.mean_spectral_radiant_intensity_w_sr_m is not None
  )
  if finite_heatmap_values:
    heatmap_min = min(finite_heatmap_values)
    heatmap_max = max(finite_heatmap_values)
    if heatmap_min == heatmap_max:
      heatmap_max = heatmap_min + 1.0
    ####
  else:
    heatmap_min, heatmap_max = 0.0, 1.0
  ####

  heatmap_columns = min(4, len(heatmaps))
  heatmap_rows = (len(heatmaps) + heatmap_columns - 1) // heatmap_columns
  heatmap_figure, heatmap_axes = plt.subplots(
    heatmap_rows,
    heatmap_columns,
    figsize=(4.4 * heatmap_columns, 3.8 * heatmap_rows),
    squeeze=False,
    constrained_layout=True,
  )
  heatmap_axes_flat = tuple(axis for row in heatmap_axes for axis in row)
  heatmap_image = None
  for heatmap, axis in zip(heatmaps, heatmap_axes_flat, strict=True):
    matrix = np.asarray([
      [
        cell.mean_spectral_radiant_intensity_w_sr_m
        if cell.mean_spectral_radiant_intensity_w_sr_m is not None
        else float('nan')
        for cell in (
          heatmap.cell_at(azimuth_index, elevation_index)
          for azimuth_index in range(heatmap.binning.azimuth_bin_count)
        )
      ]
      for elevation_index in range(heatmap.binning.elevation_bin_count)
    ], dtype=float)
    heatmap_image = axis.imshow(
      np.ma.masked_invalid(matrix),
      origin='lower',
      extent=(-180.0, 180.0, -90.0, 90.0),
      aspect='auto',
      cmap='magma',
      vmin=heatmap_min,
      vmax=heatmap_max,
    )
    axis.set_title(
      f't={heatmap.time_s:g} s\n'
      f'valid={heatmap.valid_direction_count}, invalid={heatmap.invalid_direction_count}'
    )
    axis.set_xlabel('azimuth [deg]')
    axis.set_ylabel('elevation [deg]')
  ####
  for axis in heatmap_axes_flat[len(heatmaps):]:
    axis.set_visible(False)
  ####
  if heatmap_image is not None:
    heatmap_figure.colorbar(
      heatmap_image,
      ax=heatmap_axes_flat[:len(heatmaps)],
      label='Jλ [W sr⁻¹ m⁻¹]',
      shrink=0.88,
    )
  ####
  heatmap_figure.suptitle(
    f'Signature angular heatmaps | λ={timeline.wavelengths_m[wavelength_index] * 1.0e6:g} μm | '
    f'frame={timeline.direction_frame_id}'
  )
  heatmap_path = output / 'signature_timeline_heatmaps.png'
  heatmap_figure.savefig(heatmap_path, dpi=140)
  plt.close(heatmap_figure)

  series_figure, series_axis = plt.subplots(figsize=(9.0, 5.6))
  for direction_series in series:
    values = tuple(
      value if valid else float('nan')
      for value, valid in zip(
        direction_series.spectral_radiant_intensity_w_sr_m,
        direction_series.validity_mask,
        strict=True,
      )
    )
    label = (
      f'dir {direction_series.direction_index} '
      f'(az={direction_series.angular_coordinates.azimuth_deg:g}°, '
      f'el={direction_series.angular_coordinates.elevation_deg:g}°)'
    )
    series_axis.plot(direction_series.times_s, values, marker='o', label=label)
    uncertainty = direction_series.absolute_standard_uncertainty_w_sr_m
    if any(value is not None for value in uncertainty):
      lower = tuple(
        value - error if value is not None and error is not None else float('nan')
        for value, error in zip(values, uncertainty, strict=True)
      )
      upper = tuple(
        value + error if value is not None and error is not None else float('nan')
        for value, error in zip(values, uncertainty, strict=True)
      )
      series_axis.fill_between(direction_series.times_s, lower, upper, alpha=0.12)
    ####
  ####
  series_axis.set_title(
    f'Signature direction traces | λ={timeline.wavelengths_m[wavelength_index] * 1.0e6:g} μm | '
    f'frame={timeline.direction_frame_id}'
  )
  series_axis.set_xlabel('time [s]')
  series_axis.set_ylabel('Jλ [W sr⁻¹ m⁻¹]')
  series_axis.grid(True, alpha=0.25)
  series_axis.legend(loc='best', fontsize='small')
  series_figure.tight_layout()
  series_path = output / 'signature_timeline_direction_series.png'
  series_figure.savefig(series_path, dpi=140)
  plt.close(series_figure)

  trajectory = timeline.source_trajectory()
  trajectory_figure = plt.figure(figsize=(8.0, 6.0))
  trajectory_axis = trajectory_figure.add_subplot(111, projection='3d')
  x_values, y_values, z_values = zip(*trajectory.positions_m, strict=True)
  if len(trajectory.times_s) > 1:
    trajectory_axis.scatter(x_values, y_values, z_values, c=trajectory.times_s, cmap='viridis')
  else:
    trajectory_axis.scatter(x_values, y_values, z_values, color='tab:blue')
  ####
  trajectory_axis.plot(x_values, y_values, z_values, color='tab:blue', alpha=0.65)
  trajectory_axis.set_title(f'Signature source trajectory | frame={trajectory.frame_id}')
  trajectory_axis.set_xlabel('x [m]')
  trajectory_axis.set_ylabel('y [m]')
  trajectory_axis.set_zlabel('z [m]')
  trajectory_figure.tight_layout()
  trajectory_path = output / 'signature_source_trajectory.png'
  trajectory_figure.savefig(trajectory_path, dpi=140)
  plt.close(trajectory_figure)

  direction_table, trajectory_table = _write_signature_timeline_tables(
    timeline,
    selected_direction_indices,
    wavelength_index,
    output,
  )
  spec_path = output / 'visualization_spec.json'
  spec_path.write_text(json.dumps({
    'schema': SIGNATURE_TIMELINE_GALLERY_SCHEMA,
    'direction_frame_id': timeline.direction_frame_id,
    'wavelength_index': wavelength_index,
    'wavelength_m': timeline.wavelengths_m[wavelength_index],
    'selected_direction_indices': list(selected_direction_indices),
    'binning': {
      'azimuth_bin_count': selected_binning.azimuth_bin_count,
      'elevation_bin_count': selected_binning.elevation_bin_count,
    },
    'times_s': list(timeline.times_s),
    'source_result_ids': [sample.result.metadata.result_id for sample in timeline.samples],
  }, indent=2, sort_keys=True) + '\n', encoding='utf-8')

  artifacts = (
    GalleryArtifact('signature.timeline-heatmaps', heatmap_path.name, 'image/png'),
    GalleryArtifact('signature.timeline-direction-series', series_path.name, 'image/png'),
    GalleryArtifact('signature.source-trajectory', trajectory_path.name, 'image/png'),
    GalleryArtifact('signature.timeline-direction-table', direction_table.name, 'text/csv'),
    GalleryArtifact('signature.source-trajectory-table', trajectory_table.name, 'text/csv'),
    GalleryArtifact('signature.timeline-visualization-spec', spec_path.name, 'application/json'),
  )
  guards = (
    'exact_sample_times_only_no_temporal_interpolation',
    'invalid_signature_samples_are_masked_or_gapped_not_zero_filled',
    'angular_heatmaps_are_display_bins_in_the_declared_direction_frame',
    'spectral_radiant_intensity_is_not_atmosphere_corrected_or_detector_response',
    'source_result_ids_and_status_codes_are_retained_for_each_sample',
    'gallery_is_diagnostic_visualization_not_external_validation_evidence',
  )
  manifest = SignatureTimelineGalleryManifest(
    schema=SIGNATURE_TIMELINE_GALLERY_SCHEMA,
    product='signature-spectral-radiant-intensity-timeline',
    direction_frame_id=timeline.direction_frame_id,
    wavelength_index=wavelength_index,
    wavelength_m=timeline.wavelengths_m[wavelength_index],
    times_s=timeline.times_s,
    source_result_ids=tuple(sample.result.metadata.result_id for sample in timeline.samples),
    selected_direction_indices=selected_direction_indices,
    binning=selected_binning,
    artifacts=artifacts,
    guardrails=guards,
    manifest_path=output / 'gallery_manifest.json',
  )
  manifest.manifest_path.write_text(manifest.canonical_json(), encoding='utf-8')
  return manifest
####
