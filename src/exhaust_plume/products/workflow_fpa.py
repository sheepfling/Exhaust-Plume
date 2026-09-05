"""Static evaluation gallery for the downstream focal-plane-array lane.

This module is intentionally separate from ``render_product_gallery`` because
an FPA image is a deterministic downstream operator result, not a fifth public
plume provider product.  Every artifact keeps the upstream ray identity,
operator chain, validity masks, and claim ceiling visible.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping

from exhaust_plume.products.workflow_gallery import GalleryArtifact
from exhaust_plume.validation.fpa_visualization import (
  FPA_CLAIM_CEILING,
  FpaDisplayLayer,
  FpaVisualizationInput,
  FpaVisualizationSpec,
  project_fpa_view,
)


FPA_GALLERY_MANIFEST_SCHEMA = 'plume.visualization.fpa-gallery@1'


@dataclass(frozen=True, slots=True)
class FpaVisualizationGalleryManifest:
  """Source-bound manifest for a downstream FPA evaluation gallery."""

  schema: str
  product: str
  view_spec: FpaVisualizationSpec
  view_specs: tuple[FpaVisualizationSpec, ...]
  source: Mapping[str, Any]
  fpa_metadata: Mapping[str, Any]
  artifacts: tuple[GalleryArtifact, ...]
  guardrails: tuple[str, ...]
  manifest_path: Path

  def model_dump(self) -> dict[str, Any]:
    return {
      'schema': self.schema,
      'product': self.product,
      'view_spec': self.view_spec.model_dump(mode='json'),
      'view_spec_digest_sha256': self.view_spec.digest_sha256(),
      'view_specs': [
        {
          'view_kind': spec.view_kind,
          'display_layer': spec.display_layer.value,
          'digest_sha256': spec.digest_sha256(),
        }
        for spec in self.view_specs
      ],
      'source': dict(self.source),
      'fpa_metadata': dict(self.fpa_metadata),
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


def _matplotlib() -> tuple[Any, Any]:
  try:
    from matplotlib import pyplot as plt
    import numpy as np
  except ImportError as error:
    raise RuntimeError('FPA galleries require the optional plot dependency: pip install .[plot]') from error
  ####
  return plt, np
####


def _write_json(path: Path, payload: Mapping[str, Any]) -> Path:
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(
    json.dumps(payload, allow_nan=False, ensure_ascii=True, indent=2, sort_keys=True) + '\n',
    encoding='utf-8',
  )
  return path
####


def _source_metadata(inputs: FpaVisualizationInput) -> dict[str, Any]:
  return {
    'source': inputs.source.model_dump(mode='json'),
    'operator_ids': list(inputs.operator_ids),
    'image': {
      'width_px': inputs.image.width_px,
      'height_px': inputs.image.height_px,
      'wavelengths_m': list(inputs.image.wavelengths_m),
      'exposure_s': inputs.image.exposure_s,
      'source_semantics': inputs.image.source_semantics,
      'detector_response_id': inputs.image.detector_response_id,
      'camera_optics_id': inputs.image.camera_optics_id,
      'camera_mapping_model_id': inputs.image.camera_mapping_model_id,
      'operator_id': inputs.image.operator_id,
      'atmospheric_path_operator_id': inputs.image.atmospheric_path_operator_id,
      'atmospheric_path_layer_digest': inputs.image.atmospheric_path_layer_digest,
      'atmospheric_path_layer_ids': list(inputs.image.atmospheric_path_layer_ids),
      'valid_pixel_count': sum(
        1 for row in inputs.image.validity_mask for valid in row if valid
      ),
      'invalid_pixel_count': sum(
        1 for row in inputs.image.validity_mask for valid in row if not valid
      ),
    },
    'detector_response': None if inputs.detector_response is None else {
      'response_id': inputs.detector_response.response_id,
      'wavelengths_m': list(inputs.detector_response.wavelengths_m),
      'dark_current_e_per_s': inputs.detector_response.dark_current_e_per_s,
      'read_noise_std_e': inputs.detector_response.read_noise_std_e,
    },
    'camera_optics': None if inputs.camera_optics is None else {
      'camera_id': inputs.camera_optics.camera_id,
      'focal_length_m': inputs.camera_optics.focal_length_m,
      'pixel_pitch_m': list(inputs.camera_optics.pixel_pitch_m),
      'principal_point_px': list(inputs.camera_optics.principal_point_px),
      'aperture_area_m2': inputs.camera_optics.aperture_area_m2,
      'mapping_model_id': inputs.camera_optics.mapping_model_id,
    },
    'digitization': None if inputs.digitization_policy is None else {
      'policy_id': inputs.digitization_policy.policy_id,
      'electrons_per_count': inputs.digitization_policy.electrons_per_count,
      'offset_counts': inputs.digitization_policy.offset_counts,
      'bit_depth': inputs.digitization_policy.bit_depth,
      'rounding_mode': inputs.digitization_policy.rounding_mode,
      'saturation_mode': inputs.digitization_policy.saturation_mode,
      'invalid_count': inputs.digitization_policy.invalid_count,
    },
    'claim_ceiling': inputs.claim_ceiling,
    'validation_status': inputs.validation_status,
  }
####


def _masked_array(values: Any, mask: Any, np: Any) -> Any:
  return np.ma.masked_where(np.logical_not(np.asarray(mask, dtype=bool)), np.asarray(values, dtype=float))
####


def _save_figure(
  figure: Any,
  path: Path,
  *,
  source_content_sha256: str,
  spec: FpaVisualizationSpec,
) -> None:
  figure.tight_layout()
  figure.savefig(path, dpi=140, metadata={
    'SourceContentSHA256': source_content_sha256,
    'VisualizationSpecSHA256': spec.digest_sha256(),
    'ClaimCeiling': FPA_CLAIM_CEILING,
  })
  figure.clf()
####


def _render_pixel_grid(
  inputs: FpaVisualizationInput,
  spec: FpaVisualizationSpec,
  output: Path,
  *,
  title: str,
  file_name: str,
) -> Path:
  plt, np = _matplotlib()
  projection = project_fpa_view(inputs, spec)
  values = _masked_array(projection.layer_values, projection.validity_mask, np)
  figure, axis = plt.subplots(figsize=(7.4, 5.8))
  image = axis.imshow(values, origin='upper', cmap=spec.color_map, interpolation='nearest')
  axis.set_title(
    f'{title}\n{projection.width_px}×{projection.height_px} px | '
    f'exposure={projection.exposure_s:g} s | {projection.validation_status}'
  )
  axis.set_xlabel('pixel column [index]')
  axis.set_ylabel('pixel row [index]')
  figure.colorbar(image, ax=axis, label=spec.display_layer.value)
  selected = projection.selected_pixel
  axis.scatter([selected.column_index], [selected.row_index], marker='+', color='cyan', s=100, linewidths=1.5)
  _save_figure(
    figure,
    output / file_name,
    source_content_sha256=projection.source.content_sha256,
    spec=spec,
  )
  return output / file_name
####


def _render_validity(
  inputs: FpaVisualizationInput,
  spec: FpaVisualizationSpec,
  output: Path,
) -> Path:
  plt, np = _matplotlib()
  projection = project_fpa_view(
    inputs,
    spec.model_copy(update={
      'view_kind': 'fpa.validity',
      'display_layer': FpaDisplayLayer.VALIDITY_MASK,
    }),
  )
  figure, axes = plt.subplots(1, 2, figsize=(9.4, 4.4))
  validity = axes[0].imshow(np.asarray(projection.validity_mask, dtype=int), origin='upper', cmap='Greens', vmin=0, vmax=1)
  axes[0].set_title('valid pixel mask')
  axes[0].set_xlabel('pixel column [index]')
  axes[0].set_ylabel('pixel row [index]')
  figure.colorbar(validity, ax=axes[0], ticks=[0, 1], label='valid')
  saturation = (
    np.zeros((projection.height_px, projection.width_px), dtype=int)
    if projection.saturated_mask is None
    else np.asarray(projection.saturated_mask, dtype=int)
  )
  saturated = axes[1].imshow(saturation, origin='upper', cmap='Reds', vmin=0, vmax=1)
  axes[1].set_title('deterministic ADC saturation mask')
  axes[1].set_xlabel('pixel column [index]')
  axes[1].set_ylabel('pixel row [index]')
  figure.colorbar(saturated, ax=axes[1], ticks=[0, 1], label='saturated')
  _save_figure(
    figure,
    output / 'fpa_validity_and_saturation.png',
    source_content_sha256=projection.source.content_sha256,
    spec=spec,
  )
  return output / 'fpa_validity_and_saturation.png'
####


def _render_detector_response(
  inputs: FpaVisualizationInput,
  spec: FpaVisualizationSpec,
  output: Path,
) -> Path | None:
  if inputs.detector_response is None:
    return None
  ####
  plt, _ = _matplotlib()
  projection = project_fpa_view(
    inputs,
    spec.model_copy(update={
      'view_kind': 'fpa.detector-response',
      'display_layer': FpaDisplayLayer.DETECTOR_RESPONSE,
    }),
  )
  wavelengths_um = tuple(value * 1.0e6 for value in projection.detector_wavelengths_m or ())
  figure, axes = plt.subplots(3, 1, figsize=(8.0, 8.0), sharex=True)
  axes[0].plot(wavelengths_um, projection.quantum_efficiency, marker='o', label='quantum efficiency')
  axes[0].set_ylabel('QE [1]')
  axes[0].legend(loc='best')
  axes[1].plot(wavelengths_um, projection.optical_throughput, marker='o', color='tab:orange', label='optical throughput')
  axes[1].set_ylabel('throughput [1]')
  axes[1].legend(loc='best')
  axes[2].plot(wavelengths_um, projection.electron_response_per_joule, marker='o', color='tab:green', label='electrons / joule')
  axes[2].set_ylabel('e⁻ / J')
  axes[2].set_xlabel('wavelength [μm]')
  axes[2].legend(loc='best')
  figure.suptitle(
    f'declared detector response: {projection.detector_response_id}\n'
    'response metadata only; no calibrated measured-image claim'
  )
  _save_figure(
    figure,
    output / 'fpa_detector_response.png',
    source_content_sha256=projection.source.content_sha256,
    spec=spec,
  )
  return output / 'fpa_detector_response.png'
####


def _write_pixel_table(inputs: FpaVisualizationInput, output: Path) -> Path:
  path = output / 'fpa_pixel_values.csv'
  with path.open('w', newline='', encoding='utf-8') as stream:
    writer = csv.writer(stream)
    writer.writerow((
      'row_index',
      'column_index',
      'valid',
      'expected_electrons',
      'dark_electrons',
      'noise_variance_e2',
      'digitized_count',
      'saturated',
      'image_plane_x_m',
      'image_plane_y_m',
    ))
    for row in range(inputs.image.height_px):
      for column in range(inputs.image.width_px):
        plane = None
        if inputs.camera_optics is not None:
          plane = (
            (column - inputs.camera_optics.principal_point_px[0]) * inputs.camera_optics.pixel_pitch_m[0],
            (row - inputs.camera_optics.principal_point_px[1]) * inputs.camera_optics.pixel_pitch_m[1],
          )
        ####
        digitized = None if inputs.digitized is None else inputs.digitized.counts[row][column]
        saturated = None if inputs.digitized is None else inputs.digitized.saturated_mask[row][column]
        writer.writerow((
          row,
          column,
          inputs.image.validity_mask[row][column],
          inputs.image.expected_electrons[row][column],
          inputs.image.dark_electrons[row][column],
          inputs.image.noise_variance_e2[row][column],
          digitized,
          saturated,
          None if plane is None else plane[0],
          None if plane is None else plane[1],
        ))
      ####
    ####
  ####
  return path
####


def write_fpa_gallery_manifest(
  manifest: FpaVisualizationGalleryManifest,
  path: str | Path | None = None,
) -> Path:
  """Write a deterministic downstream FPA gallery manifest."""

  target = Path(path) if path is not None else manifest.manifest_path
  target.parent.mkdir(parents=True, exist_ok=True)
  target.write_text(manifest.canonical_json(), encoding='utf-8')
  return target
####


def render_fpa_gallery(
  inputs: FpaVisualizationInput,
  output_dir: str | Path,
  *,
  spec: FpaVisualizationSpec | None = None,
) -> FpaVisualizationGalleryManifest:
  """Render deterministic detector views and write their source manifest."""

  if not isinstance(inputs, FpaVisualizationInput):
    raise TypeError('inputs must be FpaVisualizationInput')
  ####
  output = Path(output_dir)
  output.mkdir(parents=True, exist_ok=True)
  base_spec = spec or FpaVisualizationSpec.for_source(inputs.source, view_kind='fpa.overview')
  base_spec.validate_for_source(inputs.source)
  view_specs: list[FpaVisualizationSpec] = []
  artifacts: list[GalleryArtifact] = []
  expected_spec = base_spec.model_copy(update={
    'view_kind': 'fpa.expected-electrons',
    'display_layer': FpaDisplayLayer.EXPECTED_ELECTRONS,
  })
  _render_pixel_grid(
    inputs,
    expected_spec,
    output,
    title='expected detector electrons (deterministic, not measured)',
    file_name='fpa_expected_electrons.png',
  )
  view_specs.append(expected_spec)
  artifacts.append(GalleryArtifact('fpa.expected-electrons', 'fpa_expected_electrons.png', 'image/png'))
  if inputs.digitized is not None:
    counts_spec = base_spec.model_copy(update={
      'view_kind': 'fpa.digitized-counts',
      'display_layer': FpaDisplayLayer.DIGITIZED_COUNTS,
    })
    _render_pixel_grid(
      inputs,
      counts_spec,
      output,
      title='expected ADC counts (deterministic policy, not measured)',
      file_name='fpa_digitized_counts.png',
    )
    view_specs.append(counts_spec)
    artifacts.append(GalleryArtifact('fpa.digitized-counts', 'fpa_digitized_counts.png', 'image/png'))
  ####
  _render_validity(inputs, base_spec, output)
  validity_spec = base_spec.model_copy(update={
    'view_kind': 'fpa.validity',
    'display_layer': FpaDisplayLayer.VALIDITY_MASK,
  })
  view_specs.append(validity_spec)
  artifacts.append(GalleryArtifact('fpa.validity-and-saturation', 'fpa_validity_and_saturation.png', 'image/png'))
  response_path = _render_detector_response(inputs, base_spec, output)
  if response_path is not None:
    response_spec = base_spec.model_copy(update={
      'view_kind': 'fpa.detector-response',
      'display_layer': FpaDisplayLayer.DETECTOR_RESPONSE,
    })
    view_specs.append(response_spec)
    artifacts.append(GalleryArtifact('fpa.detector-response', response_path.name, 'image/png'))
  ####
  pixel_table = _write_pixel_table(inputs, output)
  artifacts.append(GalleryArtifact('fpa.pixel-values', pixel_table.name, 'text/csv'))
  spec_path = _write_json(output / 'visualization_spec.json', {
    'schema': FPA_GALLERY_MANIFEST_SCHEMA,
    'view_spec': base_spec.model_dump(mode='json'),
    'view_spec_digest_sha256': base_spec.digest_sha256(),
    'view_specs': [
      {
        'view_kind': view.view_kind,
        'display_layer': view.display_layer.value,
        'digest_sha256': view.digest_sha256(),
      }
      for view in view_specs
    ],
  })
  artifacts.append(GalleryArtifact('fpa.visualization-spec', spec_path.name, 'application/json'))
  guards = (
    'fpa_is_a_downstream_adapter_not_a_public_provider',
    'expected_electrons_are_not_measured_detector_counts',
    'digitized_counts_are_deterministic_expectations_under_the_declared_adc_policy',
    'noise_variance_is_expected_variance_only_no_random_realization',
    'camera_coordinates_are_declared_image_plane_metadata_only_no_ray_inference',
    'source_and_operator_lineage_are_preserved_in_the_manifest',
    'diagnostic_visualization_is_not_external_validation_evidence',
  )
  manifest = FpaVisualizationGalleryManifest(
    schema=FPA_GALLERY_MANIFEST_SCHEMA,
    product='focal-plane-array-downstream',
    view_spec=base_spec,
    view_specs=tuple(view_specs),
    source=_source_metadata(inputs),
    fpa_metadata={
      'claim_ceiling': inputs.claim_ceiling,
      'validation_status': inputs.validation_status,
      'source_semantics': inputs.image.source_semantics,
      'operator_ids': list(inputs.operator_ids),
    },
    artifacts=tuple(artifacts),
    guardrails=guards,
    manifest_path=output / 'gallery_manifest.json',
  )
  write_fpa_gallery_manifest(manifest)
  return manifest
####


__all__ = (
  'FPA_GALLERY_MANIFEST_SCHEMA',
  'FpaVisualizationGalleryManifest',
  'render_fpa_gallery',
  'write_fpa_gallery_manifest',
)
