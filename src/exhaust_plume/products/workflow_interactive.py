"""Standalone linked galleries for canonical product and capability results.

This module writes a self-contained HTML evaluation page.  The page uses only
embedded contract data and inline SVG, so it can be opened from a file without
network access.  It is intentionally an evaluation utility: it does not
create a provider, infer missing geometry/ray paths, or manufacture an FPA.
"""

from __future__ import annotations

import json
from math import sqrt
from pathlib import Path
from typing import Any, Mapping

from exhaust_plume.api import (
  PlumeFluxSectionResult,
  ProductResult,
  SectionedTubeResult,
  SpectralRadiantIntensityResult,
  SpectralRayTransferResult,
  VisualizationSpec,
  WavelengthDisplayUnit,
  project_plume_flux_view,
  project_sectioned_tube_view,
  project_spectral_radiant_intensity_view,
  project_spectral_ray_transfer_view,
)
from exhaust_plume.contracts.spectral_radiance_image_v1 import SpectralRadianceImageResult
from exhaust_plume.contracts.common_v1 import canonical_digest
from exhaust_plume.contracts.engineering_flux_v1 import EngineeringFluxSectionResult
from exhaust_plume.contracts.local_field_v1 import SpatialLocalFieldResult
from exhaust_plume.contracts.spatial import AxisymmetricZone, AxisymmetricZoneField
from exhaust_plume.contracts.spatial_v1 import AxisymmetricZoneFieldResult
from exhaust_plume.contracts.visualization import (
  CanonicalAxisymmetricZoneFieldData,
  CanonicalSpectralRayTransferData,
  extract_canonical_visualization_data,
)
from exhaust_plume.products.workflow_gallery import (
  CanonicalSpectralRayTransferGallerySpec,
  EngineeringFluxSectionGallerySpec,
  SpectralRadianceImageGallerySpec,
  SpatialLocalFieldGallerySpec,
  _canonical_ray_transfer_source,
  _source_metadata,
  _spectral_radiance_image_source,
)
from exhaust_plume.products.workflow_zone_gallery import AxisymmetricZoneGallerySpec

__all__ = (
  'INTERACTIVE_GALLERY_SCHEMA',
  'write_interactive_product_gallery',
)

INTERACTIVE_GALLERY_SCHEMA = 'plume.visualization.interactive-gallery@1'
_ZONE_FIELDS = {
  'static_pressure_Pa': ('Static pressure', 'Pa'),
  'static_temperature_K': ('Static temperature', 'K'),
  'density_kgpm3': ('Density', 'kg/m³'),
  'mach': ('Mach number', '1'),
  'shock_angle_rad': ('Declared shock angle', 'rad'),
  'turn_angle_rad': ('Declared flow turn angle', 'rad'),
}


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
  if resolved.wavelength_display_unit is None and product_prefix in {'signature', 'ray-transfer'}:
    resolved = resolved.model_copy(update={'wavelength_display_unit': WavelengthDisplayUnit.UM})
  ####
  return resolved
####


def _common_payload(result: ProductResult, spec: VisualizationSpec, product: str) -> dict[str, Any]:
  return {
    'schema': INTERACTIVE_GALLERY_SCHEMA,
    'product': product,
    'source': _source_metadata(result),
    'view_spec': spec.model_dump(mode='json'),
    'view_spec_digest_sha256': spec.digest_sha256(),
  }
####


def _visual_payload(result: SectionedTubeResult, spec: VisualizationSpec) -> dict[str, Any]:
  projection = project_sectioned_tube_view(result, spec)
  geometry = projection.data.geometry
  return {
    **_common_payload(result, spec, 'visual'),
    'geometry': {
      'arc_length_m': list(geometry.arc_length_m),
      'centerline_m': [list(point) for point in geometry.centerline_m],
      'tangent': [list(point) for point in geometry.tangent],
      'normal_1': [list(point) for point in geometry.normal_1],
      'normal_2': [list(point) for point in geometry.normal_2],
      'semi_axis_1_m': list(geometry.semi_axis_1_m),
      'semi_axis_2_m': list(geometry.semi_axis_2_m),
    },
    'channels': [
      {
        'channel_id': channel.channel_id,
        'semantic': channel.semantic,
        'unit': channel.unit,
        'component_index': channel.component_index,
        'values': list(channel.values),
      }
      for channel in projection.data.channels
    ],
    'initial_selection': {
      'station_index': projection.station_index,
      'channel_key': (
        None
        if projection.selected_channel is None
        else f'{projection.selected_channel.channel_id}:{projection.selected_channel.component_index}'
      ),
    },
  }
####


def _signature_payload(result: SpectralRadiantIntensityResult, spec: VisualizationSpec) -> dict[str, Any]:
  projection = project_spectral_radiant_intensity_view(result, spec)
  grid = projection.grid
  return {
    **_common_payload(result, spec, 'signature'),
    'directions': [list(direction) for direction in grid.directions],
    'wavelengths_m': list(grid.wavelengths_m),
    'values': [list(row) for row in grid.radiant_intensity_W_sr_m],
    'validity_mask': [list(row) for row in grid.validity_mask],
    'initial_selection': {
      'direction_index': projection.direction_index,
      'wavelength_index': projection.wavelength_index,
    },
  }
####


def _ray_payload(result: SpectralRayTransferResult, spec: VisualizationSpec) -> dict[str, Any]:
  projection = project_spectral_ray_transfer_view(result, spec)
  data = projection.data
  return {
    **_common_payload(result, spec, 'ray-transfer'),
    'wavelengths_m': list(data.wavelengths_m),
    'rays': [
      {
        'ray_id': line.ray_id,
        'origin_m': list(line.origin_m),
        'direction': list(line.direction),
        'source_radiance': list(line.source_radiance_W_m2_sr_m),
        'background_transmittance': list(line.background_transmittance),
        'validity_mask': list(line.validity_mask),
        'item_status': line.item_status.value,
      }
      for line in data.lines
    ],
    'initial_selection': {
      'ray_id': projection.selected_line.ray_id,
      'wavelength_index': projection.wavelength_index,
    },
  }
####


def _canonical_ray_payload(
  data: CanonicalSpectralRayTransferData,
  spec: CanonicalSpectralRayTransferGallerySpec,
) -> dict[str, Any]:
  spec.validate_for_data(data)
  rays = []
  for index, line in enumerate(data.lines):
    direction = data.request.ray_directions[index]
    origin = data.request.ray_origins_m[index]
    t_min = data.request.ray_t_min_m[index]
    t_max = data.request.ray_t_max_m[index]
    rays.append({
      'ray_id': str(index),
      'origin_m': list(origin),
      'direction': list(direction),
      'segment_start_m': [origin[axis] + t_min * direction[axis] for axis in range(3)],
      'segment_end_m': [origin[axis] + t_max * direction[axis] for axis in range(3)],
      'source_radiance': [
        value if line.validity_mask[wavelength_index] else None
        for wavelength_index, value in enumerate(line.source_spectral_radiance_W_m2_sr_m)
      ],
      'absolute_standard_uncertainty': (
        None
        if line.absolute_standard_uncertainty_W_m2_sr_m is None
        else [
          value if line.validity_mask[wavelength_index] else None
          for wavelength_index, value in enumerate(line.absolute_standard_uncertainty_W_m2_sr_m)
        ]
      ),
      'background_transmittance': [
        value if line.validity_mask[wavelength_index] else None
        for wavelength_index, value in enumerate(line.background_transmittance)
      ],
      'validity_mask': list(line.validity_mask),
      'item_status': line.ray_status.code.value,
    })
  return {
    'schema': INTERACTIVE_GALLERY_SCHEMA,
    'product': 'ray-transfer',
    'canonical_v1': True,
    'source': _canonical_ray_transfer_source(data),
    'view_spec': spec.model_dump(mode='json'),
    'view_spec_digest_sha256': spec.digest_sha256(),
    'wavelengths_m': list(data.wavelengths_m),
    'uncertainty_matrix_supplied': data.result.absolute_standard_uncertainty is not None,
    'rays': rays,
    'initial_selection': {
      'ray_id': str(spec.selected_ray_index),
      'wavelength_index': spec.wavelength_index,
    },
  }
####


def _spectral_radiance_image_payload(
  result: SpectralRadianceImageResult,
  spec: SpectralRadianceImageGallerySpec,
) -> dict[str, Any]:
  return {
    'schema': INTERACTIVE_GALLERY_SCHEMA,
    'product': 'spectral-radiance-image',
    'source': _spectral_radiance_image_source(result),
    'view_spec': spec.model_dump(mode='json'),
    'view_spec_digest_sha256': spec.digest_sha256(),
    'image': {
      'width_px': result.width_px,
      'height_px': result.height_px,
      'pixel_frame_id': result.pixel_frame_id,
      'wavelengths_m': list(result.wavelengths_m),
      'source_spectral_radiance_W_m2_sr_m': [
        [list(pixel) for pixel in row]
        for row in result.source_spectral_radiance_W_m2_sr_m
      ],
      'background_transmittance': [
        [list(pixel) for pixel in row]
        for row in result.background_transmittance
      ],
      'validity_mask': [list(row) for row in result.validity_mask],
      'pixel_status': [
        [
          {
            'code': status.code.value,
            'message': status.message,
            'retryable': status.retryable,
          }
          for status in row
        ]
        for row in result.pixel_status
      ],
    },
    'initial_selection': {
      'field': 'source_spectral_radiance',
      'wavelength_index': spec.wavelength_index,
      'pixel_row': spec.selected_pixel_row,
      'pixel_column': spec.selected_pixel_column,
    },
  }
####


def _flux_payload(result: PlumeFluxSectionResult, spec: VisualizationSpec) -> dict[str, Any]:
  projection = project_plume_flux_view(result, spec)
  glyph = projection.glyph
  return {
    **_common_payload(result, spec, 'flux'),
    'translation_m': list(glyph.section_translation_m),
    'normal': list(glyph.normal),
    'momentum_flux_N': list(glyph.momentum_flux_N),
    'area_m2': glyph.area_m2,
    'mass_flow_kgps': glyph.mass_flow_kgps,
    'total_energy_flow_W': glyph.total_energy_flow_W,
    'pressure_Pa': glyph.pressure_Pa,
    'ambient_pressure_Pa': glyph.ambient_pressure_Pa,
    'pressure_match_relative_residual': glyph.pressure_match_relative_residual,
    'species': [
      {'species_id': species_id, 'mass_flow_kgps': value}
      for species_id, value in glyph.species_mass_flows_kgps
    ],
    'second_moment_m2': [list(row) for row in glyph.cross_section_second_moment_m2],
    'initial_selection': {'species_index': projection.species_index},
  }
####


def _engineering_flux_payload(
  result: EngineeringFluxSectionResult,
  spec: EngineeringFluxSectionGallerySpec,
) -> dict[str, Any]:
  """Build an exact-station interactive view without filling failed samples."""

  canonical = extract_canonical_visualization_data(result)
  spec.validate_for_result(result)
  samples = result.samples
  series: list[dict[str, Any]] = []

  def add_series(series_id: str, label: str, unit: str, values: list[float | None]) -> None:
    series.append({'series_id': series_id, 'label': label, 'unit': unit, 'values': values})

  def scalar_values(field: str) -> list[float | None]:
    return [None if sample.section is None else getattr(sample.section, field) for sample in samples]

  add_series('mass_flow_kg_s', 'Mass flow', 'kg/s', scalar_values('mass_flow_kg_s'))
  add_series(
    'momentum_flux_magnitude_N',
    'Momentum-flux magnitude (vector norm)',
    'N',
    [
      None if sample.section is None else sqrt(sum(value * value for value in sample.section.momentum_flux_N))
      for sample in samples
    ],
  )
  for vector_name, label in (
    ('momentum_flux_N', 'Total momentum flux'),
    ('advective_momentum_flux_N', 'Advective momentum flux'),
    ('pressure_thrust_N', 'Pressure-thrust flux'),
  ):
    for component, axis in enumerate(('x', 'y', 'z')):
      add_series(
        f'{vector_name}_{axis}', f'{label} {axis}', 'N',
        [None if sample.section is None else getattr(sample.section, vector_name)[component] for sample in samples],
      )

  for field, label, unit in (
    ('stagnation_enthalpy_flux_W', 'Stagnation-enthalpy flux', 'W'),
    ('total_energy_flow_W', 'Legacy total-energy flow (not enthalpy flux)', 'W'),
    ('pressure_Pa', 'Static pressure', 'Pa'),
    ('ambient_pressure_Pa', 'Ambient pressure', 'Pa'),
    ('pressure_match_relative_residual', 'Pressure-match relative residual', '1'),
    ('area_m2', 'Cross-section area', 'm²'),
    ('characteristic_radius_m', 'Characteristic radius', 'm'),
  ):
    add_series(field, label, unit, scalar_values(field))

  for row_index, row_name in ((0, 'xx'), (0, 'xy'), (1, 'yx'), (1, 'yy')):
    column_index = 0 if row_name.endswith('x') else 1
    add_series(
      f'cross_section_second_moment_{row_name}_m2',
      f'Cross-section second moment {row_name}',
      'm²',
      [
        None if sample.section is None
        else sample.section.cross_section_second_moment_m2[row_index][column_index]
        for sample in samples
      ],
    )

  species_ids = tuple(dict.fromkeys(
    species.species_id
    for sample in samples
    if sample.section is not None
    for species in sample.section.species_mass_flows_kg_s
  ))
  for species_id in species_ids:
    add_series(
      f'species_mass_flow_kg_s:{species_id}',
      f'Species mass flow — {species_id}',
      'kg/s',
      [
        None if sample.section is None else next(
          (species.mass_flow_kg_s for species in sample.section.species_mass_flows_kg_s
           if species.species_id == species_id),
          None,
        )
        for sample in samples
      ],
    )

  metadata = result.metadata
  return {
    'schema': INTERACTIVE_GALLERY_SCHEMA,
    'product': 'engineering-flux-series',
    'source': {
      'capability_id': metadata.capability.wire_id,
      'schema_version': metadata.capability.major,
      'result_id': metadata.result_id,
      'request_digest_sha256': metadata.request_digest_sha256,
      'snapshot_id': metadata.snapshot.snapshot_id,
      'requested_time_s': metadata.snapshot.time_s,
      'content_sha256': canonical_digest(result),
      'frame': {'frame_id': metadata.output_frame_id},
      'claims': metadata.claims.model_dump(mode='json'),
      'applicability': metadata.applicability.model_dump(mode='json'),
      'provenance': metadata.provenance.model_dump(mode='json'),
      'warnings': list(metadata.warnings),
      'source_context': canonical.source_context.model_dump(),
    },
    'view_spec': spec.model_dump(mode='json'),
    'view_spec_digest_sha256': spec.digest_sha256(),
    'request': result.request.model_dump(mode='json'),
    'result_digest_sha256': canonical.result_digest_sha256,
    'samples': [
      {
        'station_arclength_m': sample.station_arclength_m,
        'centerline_position_m': None if sample.centerline_position_m is None else list(sample.centerline_position_m),
        'centerline_tangent': None if sample.centerline_tangent is None else list(sample.centerline_tangent),
        'sampling_method': sample.sampling_method,
        'status': sample.status.model_dump(mode='json'),
        'section': None if sample.section is None else sample.section.model_dump(mode='json'),
      }
      for sample in samples
    ],
    'series': series,
    'initial_selection': {'series_id': 'mass_flow_kg_s', 'station_index': 0},
    'interpolation_performed': False,
    'missing_species_policy': 'masked-null-no-zero-inference',
  }
####


def _spatial_local_field_payload(
  result: SpatialLocalFieldResult,
  spec: SpatialLocalFieldGallerySpec,
) -> dict[str, Any]:
  """Build an exact-point interactive map without a reconstructed field."""

  canonical = extract_canonical_visualization_data(result)
  spec.validate_for_data(canonical)
  metadata = result.metadata
  canonical_payload = canonical.model_dump()
  channels_by_id = {channel.field_id: channel for channel in result.channels}
  channels = []
  for field_id in spec.display_field_ids:
    channel = channels_by_id[field_id]
    channels.append({
      'field_id': channel.field_id,
      'semantic': channel.semantic,
      'unit': channel.unit,
      'sampling_method': channel.sampling_method,
      'values': list(channel.values),
      'sample_status': [status.model_dump(mode='json') for status in channel.sample_status],
      'absolute_standard_uncertainty': (
        None
        if channel.absolute_standard_uncertainty is None
        else list(channel.absolute_standard_uncertainty)
      ),
    })

  return {
    'schema': INTERACTIVE_GALLERY_SCHEMA,
    'product': 'spatial-local-field',
    'source': {
      'capability_id': metadata.capability.wire_id,
      'schema_version': metadata.capability.major,
      'result_id': metadata.result_id,
      'request_digest_sha256': metadata.request_digest_sha256,
      'snapshot_id': metadata.snapshot.snapshot_id,
      'requested_time_s': metadata.snapshot.time_s,
      'content_sha256': canonical_digest(result),
      'frame': {'frame_id': metadata.output_frame_id},
      'claims': metadata.claims.model_dump(mode='json'),
      'applicability': metadata.applicability.model_dump(mode='json'),
      'provenance': metadata.provenance.model_dump(mode='json'),
      'warnings': list(metadata.warnings),
      'source_context': canonical.source_context.model_dump(),
    },
    'view_spec': spec.model_dump(mode='json'),
    'view_spec_digest_sha256': spec.digest_sha256(),
    'result_digest_sha256': canonical_payload['result_digest_sha256'],
    'coordinate_frame_id': result.coordinate_frame_id,
    'points_m': [list(point) for point in result.points_m],
    'channels': channels,
    'projections': list(spec.projections),
    'initial_selection': {
      'field_id': spec.display_field_ids[0],
      'projection': spec.projections[0],
      'point_index': 0,
    },
    'interpolation_performed': False,
    'query_order_is_path_or_time': False,
  }
####


def _axisymmetric_zone_payload(
  value: AxisymmetricZoneField
  | AxisymmetricZone
  | AxisymmetricZoneFieldResult
  | CanonicalAxisymmetricZoneFieldData,
  spec: AxisymmetricZoneGallerySpec,
) -> dict[str, Any]:
  """Build a source-aware exact-zone view without interpolating the field."""

  if isinstance(value, CanonicalAxisymmetricZoneFieldData):
    data = value
  else:
    canonical = extract_canonical_visualization_data(value)
    if not isinstance(canonical, CanonicalAxisymmetricZoneFieldData):
      raise TypeError('zone input did not produce canonical zone-field data')
    data = canonical
  ####
  spec.validate_for_data(data)
  metadata = None if data.source_context is None else data.source_context.metadata
  result_digest = canonical_digest(value) if isinstance(value, AxisymmetricZoneFieldResult) else None
  data_digest = canonical_digest(data.model_dump())
  source = {
    'capability_id': data.capability_id.value,
    'schema_version': data.major_version,
    'result_id': None if metadata is None else metadata.result_id,
    'request_digest_sha256': None if metadata is None else metadata.request_digest_sha256,
    'snapshot_id': None if metadata is None else metadata.snapshot.snapshot_id,
    'requested_time_s': None if metadata is None else metadata.snapshot.time_s,
    'content_sha256': result_digest or data_digest,
    'content_digest_basis': 'source result' if result_digest is not None else 'canonical zone-field data',
    'frame': {'frame_id': None if metadata is None else metadata.output_frame_id},
    'claims': None if metadata is None else metadata.claims.model_dump(mode='json'),
    'applicability': None if metadata is None else metadata.applicability.model_dump(mode='json'),
    'provenance': None if metadata is None else metadata.provenance.model_dump(mode='json'),
    'warnings': [] if metadata is None else list(metadata.warnings),
    'source_context': None if data.source_context is None else data.source_context.model_dump(),
    'source_metadata_available': metadata is not None,
  }
  fields = [
    {'field_id': field_id, 'label': _ZONE_FIELDS[field_id][0], 'unit': _ZONE_FIELDS[field_id][1]}
    for field_id in spec.display_fields
  ]
  fields.append({'field_id': 'phase', 'label': 'Declared phase', 'unit': 'category'})
  return {
    'schema': INTERACTIVE_GALLERY_SCHEMA,
    'product': 'axisymmetric-zone-field',
    'source': source,
    'view_spec': spec.model_dump(),
    'view_spec_digest_sha256': spec.digest_sha256(),
    'zone_field_digest_sha256': data_digest,
    'capability_id': data.capability_id.value,
    'major_version': data.major_version,
    'axis_definition': data.axis_definition,
    'zones': [zone.model_dump() for zone in data.zones],
    'fields': fields,
    'initial_selection': {'field_id': fields[0]['field_id'], 'zone_index': 0},
    'interpolation_performed': False,
    'revolution_performed': False,
  }
####


def _page_shell(payload: Mapping[str, Any]) -> str:
  data_literal = json.dumps(payload, allow_nan=False, ensure_ascii=True, separators=(',', ':')).replace('</', '<\\/')
  title = f"Exhaust-plume linked gallery — {payload['product']}"
  return (
    '<!doctype html>\n'
    '<html lang="en"><head><meta charset="utf-8">'
    '<meta name="viewport" content="width=device-width,initial-scale=1">'
    f'<title>{title}</title>'
    '<style>'
    ':root{color-scheme:light dark;--fg:#17202a;--muted:#59636e;--bg:#f7f8fa;--line:#b8c0c8;--accent:#c9273f;--blue:#3f73a8;}'
    '@media(prefers-color-scheme:dark){:root{--fg:#edf2f7;--muted:#aeb9c4;--bg:#171a1f;--line:#53606d;--accent:#ff7585;--blue:#82b7e8;}}'
    'body{margin:0;padding:22px;background:var(--bg);color:var(--fg);font:14px system-ui,sans-serif;}'
    'main{max-width:1240px;margin:auto;}h1{font-size:22px;margin:0 0 4px;}h2{font-size:16px;margin:16px 0 6px;}'
    'code,pre,select,button{font:12px ui-monospace,SFMono-Regular,Menlo,monospace;}code{color:var(--muted);}#identity{display:block;overflow-wrap:anywhere;}'
    '.toolbar{display:flex;gap:14px;flex-wrap:wrap;align-items:end;margin:16px 0 8px;padding:10px 0;border-top:1px solid var(--line);border-bottom:1px solid var(--line);}'
    'label{display:flex;flex-direction:column;gap:4px;color:var(--muted);}select,button{padding:5px 7px;border:1px solid var(--line);background:transparent;color:var(--fg);}'
    'button{cursor:pointer;}button:hover{border-color:var(--accent);}.selection{white-space:pre-wrap;color:var(--muted);min-height:34px;}.selection.zone-selection{white-space:normal;}'
    '.zone-inspector{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:6px;margin:8px 0 12px;}'
    '.zone-inspector .item{border:1px solid var(--line);padding:6px 8px;min-width:0;}'
    '.zone-inspector strong{display:block;font-size:11px;color:var(--muted);font-weight:500;}'
    '.zone-inspector span{display:block;margin-top:3px;color:var(--fg);overflow-wrap:anywhere;}'
    '.zone-inspector .zone-note{grid-column:1/-1;margin:0;color:var(--muted);font-size:12px;}'
    '.zone-inspector details{grid-column:1/-1;}'
    'svg{display:block;width:100%;height:auto;border:1px solid var(--line);background:transparent;}'
    'canvas{display:block;max-width:100%;height:auto;image-rendering:pixelated;border:1px solid var(--line);background:transparent;margin:8px 0 14px;}'
    '[hidden]{display:none!important;}'
    '.meta{margin-top:14px;border-top:1px solid var(--line);padding-top:8px;}summary{cursor:pointer;color:var(--muted);}pre{white-space:pre-wrap;overflow:auto;max-height:340px;}'
    '</style></head><body><main>'
    f'<h1>{title}</h1><code id="identity"></code>'
    '<div id="controls" class="toolbar"></div><div id="selection" class="selection" role="status" aria-live="polite"></div>'
    '<canvas id="raster" hidden aria-label="source-bound spectral-radiance image view"></canvas>'
    '<p id="rasterAxes" hidden></p>'
    '<svg id="plot" viewBox="0 0 1200 720" role="img" aria-label="linked exhaust-plume product views"></svg>'
    '<details class="meta"><summary>source metadata and provenance</summary><pre id="metadata"></pre></details>'
    '<script>const DATA='
    + data_literal
    + r''';
const SVG_NS='http://www.w3.org/2000/svg';
const svg=document.getElementById('plot');
const controls=document.getElementById('controls');
const selectionBox=document.getElementById('selection');
document.getElementById('identity').textContent=DATA.canonical_v1
  ? DATA.source.capability_id+' | provider='+DATA.source.provenance.provider_id+' | frame='+DATA.source.output_frame_id+' | result='+DATA.source.result_id+' | content='+DATA.source.content_sha256
  : DATA.product==='spectral-radiance-image'
  ? DATA.source.capability_id+' | frame='+DATA.source.output_frame_id+' | result='+DATA.source.result_id+' | content='+DATA.source.content_sha256
  : DATA.product==='engineering-flux-series'
    ? DATA.source.capability_id+' | provider='+DATA.source.provenance.provider_id+' | model='+DATA.source.provenance.model_lineage_id+' | frame='+DATA.source.frame.frame_id+' | content='+DATA.source.content_sha256
    : DATA.product==='spatial-local-field'
      ? DATA.source.capability_id+' | provider='+DATA.source.provenance.provider_id+' | model='+DATA.source.provenance.model_lineage_id+' | frame='+DATA.source.frame.frame_id+' | content='+DATA.source.content_sha256
      : DATA.product==='axisymmetric-zone-field'
        ? DATA.source.capability_id+' | '+(DATA.source.result_id||'source metadata unavailable')+' | frame='+(DATA.source.frame.frame_id||'not supplied')+' | content='+DATA.source.content_sha256
      : DATA.source.capability_id+' | '+DATA.source.fidelity.model_fidelity+' | '+DATA.source.fidelity.validation_level+' | frame='+DATA.source.frame.frame_id+' | content='+DATA.source.content_sha256;
document.getElementById('metadata').textContent=JSON.stringify({source:DATA.source,view_spec:DATA.view_spec,view_spec_digest_sha256:DATA.view_spec_digest_sha256},null,2);
const state=JSON.parse(JSON.stringify(DATA.initial_selection));
const esc=value=>String(value).replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const finite=value=>value!==null&&Number.isFinite(value);
const colors=['#c9273f','#3f73a8','#54a24b','#f58518','#9467bd','#17becf'];
function addControl(label,id,options,selected,onChange){
  const wrap=document.createElement('label'); wrap.textContent=label;
  const select=document.createElement('select'); select.id=id;
  for(const option of options){const node=document.createElement('option');node.value=option.value;node.textContent=option.label;select.appendChild(node);}
  select.value=String(selected); select.addEventListener('change',()=>{onChange(select.value);draw();}); wrap.appendChild(select); controls.appendChild(wrap);
}
function addNumberControl(label,id,min,max,selected,onChange){
  const wrap=document.createElement('label'); wrap.textContent=label;
  const input=document.createElement('input'); input.type='number'; input.id=id; input.min=String(min); input.max=String(max); input.step='1'; input.value=String(selected); input.style.width='100px';
  input.addEventListener('change',()=>{const value=Math.max(min,Math.min(max,Number(input.value)));input.value=String(value);onChange(value);draw();}); wrap.appendChild(input); controls.appendChild(wrap);
}
function addButton(label,onClick){const button=document.createElement('button');button.type='button';button.textContent=label;button.addEventListener('click',onClick);controls.appendChild(button);}
function currentSelection(){return JSON.parse(JSON.stringify(state));}
function installControls(){
  if(DATA.product==='visual'){
    addControl('station','station',DATA.geometry.arc_length_m.map((value,index)=>({value:index,label:index+' — s='+value+' m'})),state.station_index,value=>{state.station_index=Number(value);});
    const channelOptions=[{value:'none',label:'all declared channels'}].concat(DATA.channels.map(channel=>({value:channel.channel_id+':'+channel.component_index,label:channel.channel_id+'['+channel.component_index+'] — '+channel.semantic})));
    addControl('channel','channel',channelOptions,state.channel_key??'none',value=>{state.channel_key=value==='none'?null:value;});
  }
  if(DATA.product==='signature'){
    addControl('direction','direction',DATA.directions.map((value,index)=>({value:index,label:index+' — ('+value.map(item=>item.toFixed(3)).join(', ')+')'})),state.direction_index,value=>{state.direction_index=Number(value);});
    addControl('wavelength','wavelength',DATA.wavelengths_m.map((value,index)=>({value:index,label:index+' — '+(value*1e6).toPrecision(5)+' μm'})),state.wavelength_index,value=>{state.wavelength_index=Number(value);});
  }
  if(DATA.product==='ray-transfer'){
    addControl('ray','ray',DATA.rays.map((value,index)=>({value:index,label:value.ray_id+' — '+value.item_status})),DATA.rays.findIndex(value=>value.ray_id===state.ray_id),value=>{state.ray_id=DATA.rays[Number(value)].ray_id;});
    addControl('wavelength','wavelength',DATA.wavelengths_m.map((value,index)=>({value:index,label:index+' — '+(value*1e6).toPrecision(5)+' μm'})),state.wavelength_index,value=>{state.wavelength_index=Number(value);});
  }
  if(DATA.product==='spectral-radiance-image'){
    addControl('image layer','image-layer',[
      {value:'source_spectral_radiance',label:'source spectral radiance'},
      {value:'background_transmittance',label:'background transmittance'},
      {value:'validity',label:'pixel validity'},
    ],state.field,value=>{state.field=value;});
    addControl('wavelength','image-wavelength',DATA.image.wavelengths_m.map((value,index)=>({value:index,label:index+' — '+(value*1e6).toPrecision(5)+' μm'})),state.wavelength_index,value=>{state.wavelength_index=Number(value);});
    addNumberControl('pixel row','pixel-row',0,DATA.image.height_px-1,state.pixel_row,value=>{state.pixel_row=value;});
    addNumberControl('pixel column','pixel-column',0,DATA.image.width_px-1,state.pixel_column,value=>{state.pixel_column=value;});
  }
  if(DATA.product==='flux'){
    const options=[{value:'none',label:'no species selection'}].concat(DATA.species.map((value,index)=>({value:index,label:index+' — '+value.species_id})));
    addControl('species','species',options,state.species_index??'none',value=>{state.species_index=value==='none'?null:Number(value);});
  }
  if(DATA.product==='engineering-flux-series'){
    addControl('quantity','quantity',DATA.series.map(value=>({value:value.series_id,label:value.label+' ['+value.unit+']'})),state.series_id,value=>{state.series_id=value;});
    addControl('requested station','station',DATA.samples.map((value,index)=>({value:index,label:index+' — s='+value.station_arclength_m+' m — '+value.status.code})),state.station_index,value=>{state.station_index=Number(value);});
  }
  if(DATA.product==='spatial-local-field'){
    addControl('field','field',DATA.channels.map(value=>({value:value.field_id,label:value.field_id+' — '+value.semantic+' ['+value.unit+']'})),state.field_id,value=>{state.field_id=value;});
    addControl('projection','projection',DATA.projections.map(value=>({value:value,label:value})),state.projection,value=>{state.projection=value;});
    addControl('exact query point','point',DATA.points_m.map((value,index)=>({value:index,label:index+' — ('+value.map(item=>item.toPrecision(4)).join(', ')+') m'})),state.point_index,value=>{state.point_index=Number(value);});
  }
  if(DATA.product==='axisymmetric-zone-field'){
    addControl('declared quantity','zone-field',DATA.fields.map(value=>({value:value.field_id,label:value.label+' ['+value.unit+']'})),state.field_id,value=>{state.field_id=value;});
    addControl('exact zone','zone',DATA.zones.map((value,index)=>({value:index,label:value.zone_id+' — cell '+value.cell_index+' — '+value.phase})),state.zone_index,value=>{state.zone_index=Number(value);});
    addButton('Export exact zone data JSON',()=>{
      const payload={schema:'plume.visualization.axisymmetric-zone-field-export@1',zone_field_digest_sha256:DATA.zone_field_digest_sha256,capability_id:DATA.capability_id,major_version:DATA.major_version,axis_definition:DATA.axis_definition,source:DATA.source,zones:DATA.zones};
      const blob=new Blob([JSON.stringify(payload,null,2)+'\n'],{type:'application/json'});const link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download='axisymmetric_zone_field.json';link.click();URL.revokeObjectURL(link.href);
    });
    addButton('Export exact zone values CSV',()=>{
      const columns=['zone_field_digest_sha256','capability_id','major_version','axis_definition','zone_id','cell_index','phase','region_type','region_label','geometry_status','polygon_xr_m_json','static_pressure_Pa','static_temperature_K','density_kgpm3','mach','shock_angle_rad','turn_angle_rad'];
      const cell=value=>{const textValue=value===null||value===undefined?'':typeof value==='object'?JSON.stringify(value):String(value);return '"'+textValue.replace(/"/g,'""')+'"';};
      const rows=[columns.join(',')].concat(DATA.zones.map(zone=>[DATA.zone_field_digest_sha256,DATA.capability_id,DATA.major_version,DATA.axis_definition,zone.zone_id,zone.cell_index,zone.phase,zone.region_type,zone.region_label,zone.geometry_status,zone.polygon_xr_m,zone.static_pressure_Pa,zone.static_temperature_K,zone.density_kgpm3,zone.mach,zone.shock_angle_rad,zone.turn_angle_rad].map(cell).join(',')));
      const blob=new Blob([rows.join('\n')+'\n'],{type:'text/csv'});const link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download='axisymmetric_zone_values.csv';link.click();URL.revokeObjectURL(link.href);
    });
  }
  addButton('Export current view spec',()=>{
    const sourceFrameId=DATA.source.frame?.frame_id??DATA.source.output_frame_id??null;
    const exportPayload={schema:'plume.visualization.spec-export@1',view_spec:{...DATA.view_spec,selection:currentSelection()},view_spec_digest_sha256:DATA.view_spec_digest_sha256,source:{capability_id:DATA.source.capability_id,schema_version:DATA.source.schema_version,snapshot_id:DATA.source.snapshot_id,content_sha256:DATA.source.content_sha256,frame_id:sourceFrameId}};
    const blob=new Blob([JSON.stringify(exportPayload,null,2)+'\n'],{type:'application/json'});const link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download='visualization_spec.json';link.click();URL.revokeObjectURL(link.href);
  });
}
function range(values){const valid=values.filter(finite);if(!valid.length)return [0,1];let lo=Math.min(...valid),hi=Math.max(...valid);if(lo===hi){const pad=Math.max(Math.abs(lo)*.1,1);lo-=pad;hi+=pad;}return [lo,hi];}
function sx(value,lo,hi,x,w){return x+(value-lo)/(hi-lo)*w;}
function sy(value,lo,hi,y,h){return y+h-(value-lo)/(hi-lo)*h;}
function text(parts,x,y,value,size=12,anchor='start',fill='var(--fg)'){parts.push('<text x="'+x+'" y="'+y+'" font-size="'+size+'" text-anchor="'+anchor+'" fill="'+fill+'">'+esc(value)+'</text>');}
function frame(parts,x,y,w,h,title,xlabel,ylabel){parts.push('<rect x="'+x+'" y="'+y+'" width="'+w+'" height="'+h+'" fill="none" stroke="var(--line)"/>');text(parts,x+5,y+16,title,13);text(parts,x+w/2,y+h+22,xlabel,11,'middle','var(--muted)');text(parts,x-8,y+h/2,ylabel,11,'middle','var(--muted)');}
function pathFor(points,xf,yf){let d='',open=false;for(const point of points){if(point[1]===null||!finite(point[1])){open=false;continue;}const command=open?'L':'M';d+=command+xf(point[0])+','+yf(point[1])+' ';open=true;}return d;}
function lineChart(parts,x,y,w,h,title,xs,series,xlabel,ylabel,selectedIndex=-1){
  const pad={l:48,r:12,t:28,b:30},px=x+pad.l,py=y+pad.t,pw=w-pad.l-pad.r,ph=h-pad.t-pad.b;
  const xr=range(xs),all=series.flatMap(item=>item.values.flatMap((value,column)=>{
    if(!finite(value))return [];
    const uncertainty=item.uncertainty&&item.uncertainty[column];
    return finite(uncertainty)?[value,value-uncertainty,value+uncertainty]:[value];
  })),yr=range(all);
  frame(parts,x,y,w,h,title,xlabel,ylabel);
  for(let i=0;i<=4;i++){
    const gx=px+pw*i/4,gy=py+ph*i/4;
    parts.push('<path d="M'+gx+' '+py+'V'+(py+ph)+' M'+px+' '+gy+'H'+(px+pw)+'" stroke="var(--line)" opacity=".35"/>');
    text(parts,gx,py+ph+15,(xr[0]+(xr[1]-xr[0])*i/4).toPrecision(4),9,'middle','var(--muted)');
    text(parts,px-6,gy+3,(yr[1]-(yr[1]-yr[0])*i/4).toPrecision(4),9,'end','var(--muted)');
  }
  series.forEach((item,index)=>{
    const color=colors[index%colors.length],points=xs.map((value,column)=>[value,item.values[column]]);
    const d=pathFor(points,value=>sx(value,xr[0],xr[1],px,pw),value=>sy(value,yr[0],yr[1],py,ph));
    if(d)parts.push('<path d="'+d+'" fill="none" stroke="'+color+'" stroke-width="'+(index===selectedIndex?2.8:1.4)+'"/>');
    points.forEach((point,column)=>{
      if(!finite(point[1]))return;
      const pxValue=sx(point[0],xr[0],xr[1],px,pw),pyValue=sy(point[1],yr[0],yr[1],py,ph);
      parts.push('<circle cx="'+pxValue+'" cy="'+pyValue+'" r="'+(index===selectedIndex?4:2.5)+'" fill="'+color+'"/>');
      const uncertainty=item.uncertainty&&item.uncertainty[column];
      if(finite(uncertainty)){
        const upper=sy(point[1]+uncertainty,yr[0],yr[1],py,ph),lower=sy(point[1]-uncertainty,yr[0],yr[1],py,ph);
        parts.push('<path d="M'+pxValue+' '+upper+'V'+lower+' M'+(pxValue-3)+' '+upper+'H'+(pxValue+3)+' M'+(pxValue-3)+' '+lower+'H'+(pxValue+3)+'" stroke="'+color+'" stroke-width="1.1"/>');
      }
    });
    text(parts,px+8+index*105,py+12,item.label,9,'start',color);
  });
}
function scatterChart(parts,x,y,w,h,title,points,xlabel,ylabel,selectedIndex=-1){const pad={l:45,r:12,t:28,b:30},px=x+pad.l,py=y+pad.t,pw=w-pad.l-pad.r,ph=h-pad.t-pad.b;const xr=range(points.map(item=>item[0])),yr=range(points.map(item=>item[1]));frame(parts,x,y,w,h,title,xlabel,ylabel);for(let index=0;index<points.length;index++){const point=points[index];parts.push('<circle cx="'+sx(point[0],xr[0],xr[1],px,pw)+'" cy="'+sy(point[1],yr[0],yr[1],py,ph)+'" r="'+(index===selectedIndex?7:4)+'" fill="'+(index===selectedIndex?'var(--accent)':'var(--blue)')+'"/>');text(parts,sx(point[0],xr[0],xr[1],px,pw)+6,sy(point[1],yr[0],yr[1],py,ph)-5,String(index),9);}}
function barChart(parts,x,y,w,h,title,labels,values,ylabel,selectedIndex=null){const pad={l:48,r:12,t:30,b:45},px=x+pad.l,py=y+pad.t,pw=w-pad.l-pad.r,ph=h-pad.t-pad.b;const yr=range(values);frame(parts,x,y,w,h,title,'',''+ylabel);const step=pw/Math.max(values.length,1);values.forEach((value,index)=>{const top=sy(value,yr[0],yr[1],py,ph);const bottom=sy(0,yr[0],yr[1],py,ph);const height=Math.max(1,bottom-top);parts.push('<rect x="'+(px+step*index+step*.14)+'" y="'+top+'" width="'+step*.72+'" height="'+height+'" fill="'+(index===selectedIndex?'var(--accent)':'var(--blue)')+'"/>');text(parts,px+step*(index+.5),py+ph+16,labels[index],10,'middle');text(parts,px+step*(index+.5),top-5,Number(value).toPrecision(4),9,'middle');});}
function drawVisual(){const g=DATA.geometry,parts=[];svg.setAttribute('viewBox','0 0 1200 720');const projections=[[0,1,'XY'],[0,2,'XZ'],[1,2,'YZ']];projections.forEach((item,index)=>{const points=g.centerline_m.map(point=>[point[item[0]],point[item[1]]]);const station=[points[state.station_index]];scatterChart(parts,20+index*395,20,370,260,item[2]+' projection',points,item[0]===0?'x [m]':'y [m]',item[1]===1?'y [m]':'z [m]',state.station_index);});const channelKey=state.channel_key;const selectedChannels=channelKey?DATA.channels.filter(channel=>channel.channel_id+':'+channel.component_index===channelKey):DATA.channels;lineChart(parts,20,315,760,370,'axial declared feature channels',g.arc_length_m,selectedChannels.map(channel=>({label:channel.channel_id+'['+channel.component_index+']',values:channel.values})), 'arc length [m]','value',channelKey?0:-1);const station=state.station_index,semi1=g.semi_axis_1_m[station],semi2=g.semi_axis_2_m[station],cross=[];for(let i=0;i<=96;i++){const t=2*Math.PI*i/96;cross.push([semi1*Math.cos(t),semi2*Math.sin(t)]);}scatterChart(parts,810,315,370,370,'station '+station+' cross-section',cross,'local normal_1 [m]','local normal_2 [m]',-1);text(parts,825,695,'center='+g.centerline_m[station].map(value=>value.toFixed(3)).join(', ')+' m | tangent='+g.tangent[station].map(value=>value.toFixed(3)).join(', '),9,'start','var(--muted)');svg.innerHTML=parts.join('');}
function drawSignature(){const parts=[],xs=DATA.wavelengths_m.map(value=>value*1e6),series=DATA.values.map((values,index)=>({label:'dir '+index,values:values}));svg.setAttribute('viewBox','0 0 1200 720');lineChart(parts,20,20,740,670,'spectral radiant intensity by direction',xs,series,'wavelength [μm]','Jλ [W sr⁻¹ m⁻¹]',state.direction_index);const points=DATA.directions.map((direction,index)=>[direction[0],direction[1]]);scatterChart(parts,785,20,395,670,'direction x/y projection at λ '+xs[state.wavelength_index].toPrecision(5)+' μm',points,'direction x [1]','direction y [1]',state.direction_index);points.forEach((point,index)=>text(parts,sx(point[0],...range(points.map(item=>item[0])),830,330)+6,sy(point[1],...range(points.map(item=>item[1])),48,580)-5,'z='+DATA.directions[index][2].toFixed(3),9));svg.innerHTML=parts.join('');}
function rayProjection(parts,x,y,w,h,title,rays,axes,selectedIndex){
  const [horizontal,vertical]=axes;
  const names=['x','y','z'];
  const length=DATA.view_spec.ray_display_length_m??1;
  const segments=rays.map(ray=>{
    const start=ray.segment_start_m??ray.origin_m;
    const end=ray.segment_end_m??ray.origin_m.map((value,index)=>value+length*ray.direction[index]);
    return {origin:[start[horizontal],start[vertical]],end:[end[horizontal],end[vertical]],rayOrigin:[ray.origin_m[horizontal],ray.origin_m[vertical]]};
  });
  const coordinates=segments.flatMap(segment=>[segment.origin,segment.end]);
  const rawX=range(coordinates.map(point=>point[0])),rawY=range(coordinates.map(point=>point[1]));
  const span=Math.max(rawX[1]-rawX[0],rawY[1]-rawY[0]);
  const centerX=(rawX[0]+rawX[1])/2,centerY=(rawY[0]+rawY[1])/2;
  const xr=[centerX-span/2,centerX+span/2],yr=[centerY-span/2,centerY+span/2];
  const pad={l:43,r:10,t:27,b:28},px=x+pad.l,py=y+pad.t,pw=w-pad.l-pad.r,ph=h-pad.t-pad.b;
  const plotSize=Math.min(pw,ph),plotX=px+(pw-plotSize)/2,plotY=py+(ph-plotSize)/2;
  frame(parts,x,y,w,h,title,names[horizontal]+' [m]',names[vertical]+' [m]');
  for(let tick=0;tick<=4;tick++){
    const gx=plotX+plotSize*tick/4,gy=plotY+plotSize*tick/4;
    parts.push('<path d="M'+gx+' '+plotY+'V'+(plotY+plotSize)+' M'+plotX+' '+gy+'H'+(plotX+plotSize)+'" stroke="var(--line)" opacity=".35"/>');
    text(parts,gx,plotY+plotSize+12,(xr[0]+span*tick/4).toPrecision(3),8,'middle','var(--muted)');
    text(parts,plotX-4,gy+3,(yr[1]-span*tick/4).toPrecision(3),8,'end','var(--muted)');
  }
  segments.forEach((segment,index)=>{
    const x1=sx(segment.origin[0],xr[0],xr[1],plotX,plotSize),y1=sy(segment.origin[1],yr[0],yr[1],plotY,plotSize);
    const x2=sx(segment.end[0],xr[0],xr[1],plotX,plotSize),y2=sy(segment.end[1],yr[0],yr[1],plotY,plotSize);
    const selected=index===selectedIndex;
    parts.push('<path d="M'+x1+' '+y1+'L'+x2+' '+y2+'" fill="none" stroke="'+(selected?'var(--accent)':'var(--blue)')+'" stroke-width="'+(selected?2.8:1.4)+'" opacity="'+(selected?1:.72)+'"/>');
    parts.push('<circle cx="'+x1+'" cy="'+y1+'" r="'+(selected?4.5:2.8)+'" fill="'+(selected?'var(--accent)':'var(--blue)')+'"/>');
    if(DATA.canonical_v1){const ox=sx(segment.rayOrigin[0],xr[0],xr[1],plotX,plotSize),oy=sy(segment.rayOrigin[1],yr[0],yr[1],plotY,plotSize);parts.push('<path d="M'+(ox-3)+' '+(oy-3)+'L'+(ox+3)+' '+(oy+3)+' M'+(ox-3)+' '+(oy+3)+'L'+(ox+3)+' '+(oy-3)+'" stroke="'+(selected?'var(--accent)':'var(--muted)')+'" stroke-width="1.2"/>');}
  });
  text(parts,x+w-8,y+16,DATA.canonical_v1?'segments use exact requested t intervals':'direction display length '+length+' m',9,'end','var(--muted)');
}
function drawRay(){
  const parts=[],rayIndex=DATA.rays.findIndex(ray=>ray.ray_id===state.ray_id),xs=DATA.wavelengths_m.map(value=>value*1e6),rays=DATA.rays;
  svg.setAttribute('viewBox','0 0 1200 720');
  rayProjection(parts,20,20,380,300,'ray direction projection (XY)',rays,[0,1],rayIndex);
  rayProjection(parts,410,20,380,300,'ray direction projection (XZ)',rays,[0,2],rayIndex);
  rayProjection(parts,800,20,380,300,'ray direction projection (YZ)',rays,[1,2],rayIndex);
  const hasUncertainty=DATA.canonical_v1&&rays.some(ray=>ray.absolute_standard_uncertainty&&ray.absolute_standard_uncertainty.some(finite));
  const sourceTitle=!DATA.canonical_v1?'source radiance':hasUncertainty?'source radiance — bars show supplied standard uncertainty':DATA.uncertainty_matrix_supplied?'source radiance — no sample uncertainty estimate available':'source radiance — no uncertainty estimate supplied';
  lineChart(parts,20,360,575,320,sourceTitle,xs,rays.map(ray=>({label:ray.ray_id,values:ray.source_radiance,uncertainty:ray.absolute_standard_uncertainty})), 'wavelength [μm]','source radiance',rayIndex);
  lineChart(parts,610,360,570,320,'background transmittance',xs,rays.map(ray=>({label:ray.ray_id,values:ray.background_transmittance})), 'wavelength [μm]','transmittance',rayIndex);
  svg.innerHTML=parts.join('');
}
function drawSpectralRadianceImage(){
  const image=DATA.image,canvas=document.getElementById('raster'),context=canvas.getContext('2d');
  const scale=Math.min(1,1000/image.width_px,520/image.height_px);
  canvas.width=Math.max(1,Math.round(image.width_px*scale));
  canvas.height=Math.max(1,Math.round(image.height_px*scale));
  canvas.hidden=false; canvas.style.width='min(100%, 1000px)'; canvas.style.height='auto';
  context.imageSmoothingEnabled=false;
  const layer=state.field,wave=state.wavelength_index;
  const layerValues=layer==='source_spectral_radiance'
    ? image.source_spectral_radiance_W_m2_sr_m
    : image.background_transmittance;
  let minimum=Infinity,maximum=-Infinity;
  if(layer==='source_spectral_radiance'||layer==='background_transmittance'){
    for(let row=0;row<image.height_px;row++)for(let column=0;column<image.width_px;column++){
      if(!image.validity_mask[row][column])continue;
      const value=layerValues[row][column][wave];minimum=Math.min(minimum,value);maximum=Math.max(maximum,value);
    }
  }
  if(layer==='background_transmittance'){minimum=0;maximum=1;}
  if(!Number.isFinite(minimum)){minimum=0;maximum=1;}
  if(maximum<=minimum)maximum=minimum+Math.max(Math.abs(minimum)*0.1,1e-12);
  const pixels=context.createImageData(canvas.width,canvas.height);
  for(let y=0;y<canvas.height;y++)for(let x=0;x<canvas.width;x++){
    const row=Math.min(image.height_px-1,Math.floor((y+0.5)*image.height_px/canvas.height));
    const column=Math.min(image.width_px-1,Math.floor((x+0.5)*image.width_px/canvas.width));
    const offset=(y*canvas.width+x)*4,valid=image.validity_mask[row][column];
    let red,green,blue;
    if(layer==='validity'){
      [red,green,blue]=valid?[84,162,75]:[184,192,200];
    }else if(!valid){
      [red,green,blue]=[184,192,200];
    }else{
      const value=layerValues[row][column][wave],t=Math.max(0,Math.min(1,(value-minimum)/(maximum-minimum)));
      [red,green,blue]=layer==='background_transmittance'
        ? [Math.round(40+205*t),Math.round(70+150*t),Math.round(190-150*t)]
        : [Math.round(68+180*t),Math.round(1+140*t),Math.round(84+80*t)];
    }
    pixels.data[offset]=red;pixels.data[offset+1]=green;pixels.data[offset+2]=blue;pixels.data[offset+3]=255;
  }
  context.putImageData(pixels,0,0);
  context.strokeStyle='#ffffff';context.lineWidth=Math.max(1,Math.min(3,canvas.width/image.width_px));
  context.strokeRect(Math.floor(state.pixel_column*canvas.width/image.width_px)+.5,Math.floor(state.pixel_row*canvas.height/image.height_px)+.5,Math.max(1,canvas.width/image.width_px-1),Math.max(1,canvas.height/image.height_px-1));
  canvas.setAttribute('aria-label',layer+' at wavelength index '+wave+'; pixel row and column axes; nearest-source-pixel raster display');
  canvas.title='Pixel rows and columns only; no angular or physical coordinates are inferred.';
  const axes=document.getElementById('rasterAxes');axes.hidden=false;axes.textContent='Image axes: horizontal = pixel column [zero-based index]; vertical = pixel row [zero-based index]. Display uses nearest source pixels without interpolation; no camera angles or physical coordinates are inferred.';
  canvas.onclick=event=>{
    const rect=canvas.getBoundingClientRect();
    state.pixel_column=Math.min(image.width_px-1,Math.floor((event.clientX-rect.left)*image.width_px/rect.width));
    state.pixel_row=Math.min(image.height_px-1,Math.floor((event.clientY-rect.top)*image.height_px/rect.height));
    document.getElementById('pixel-row').value=String(state.pixel_row);document.getElementById('pixel-column').value=String(state.pixel_column);draw();
  };
  const status=image.pixel_status[state.pixel_row][state.pixel_column],valid=image.validity_mask[state.pixel_row][state.pixel_column];
  selectionBox.textContent='Selected pixel ('+state.pixel_row+', '+state.pixel_column+') — '+status.code+(status.message?': '+status.message:'')+'\n'+(valid?'Valid samples;':'Invalid pixel; values remain masked;')+' wavelength '+(image.wavelengths_m[wave]*1e6).toPrecision(6)+' μm. Raster uses nearest source pixels; click a pixel to inspect it.';
  const spectrum=valid?image.source_spectral_radiance_W_m2_sr_m[state.pixel_row][state.pixel_column]:image.wavelengths_m.map(()=>null);
  const transmittance=valid?image.background_transmittance[state.pixel_row][state.pixel_column]:image.wavelengths_m.map(()=>null);
  const xs=image.wavelengths_m.map(value=>value*1e6),parts=[];
  svg.hidden=false;svg.setAttribute('viewBox','0 0 1200 700');
  lineChart(parts,20,20,1160,315,'source spectral radiance at selected pixel',xs,[{label:'source radiance',values:spectrum}],'wavelength [μm]','W m⁻² sr⁻¹ m⁻¹');
  lineChart(parts,20,360,1160,315,'background transmittance at selected pixel',xs,[{label:'transmittance',values:transmittance}],'wavelength [μm]','transmittance [1]');
  svg.innerHTML=parts.join('');
}
function drawFlux(){const parts=[];svg.setAttribute('viewBox','0 0 1200 720');barChart(parts,20,20,370,300,'section normal components',['x','y','z'],DATA.normal,'component [1]',null);barChart(parts,410,20,370,300,'momentum-flux components',['x','y','z'],DATA.momentum_flux_N,'N',null);barChart(parts,800,20,380,300,'species mass flow',DATA.species.map(value=>value.species_id),DATA.species.map(value=>value.mass_flow_kgps), 'kg/s',state.species_index);const labels=['area [m²]','mass [kg/s]','energy [W]','pressure [Pa]','ambient [Pa]','residual [1]'];const values=[DATA.area_m2,DATA.mass_flow_kgps,DATA.total_energy_flow_W,DATA.pressure_Pa,DATA.ambient_pressure_Pa,DATA.pressure_match_relative_residual];barChart(parts,20,350,760,330,'declared engineering scalars',labels,values,'value',null);text(parts,820,410,'section translation [m]: '+DATA.translation_m.map(value=>value.toFixed(4)).join(', '),12);text(parts,820,440,'selected species: '+(state.species_index===null?'none':DATA.species[state.species_index].species_id),12);text(parts,820,480,'second moment [m²]:',12);text(parts,820,505,JSON.stringify(DATA.second_moment_m2),11,'start','var(--muted)');svg.innerHTML=parts.join('');}
function drawEngineeringFluxSeries(){
  const sample=DATA.samples[state.station_index],series=DATA.series.find(value=>value.series_id===state.series_id)||DATA.series[0],xs=DATA.samples.map(value=>value.station_arclength_m),parts=[];
  svg.setAttribute('viewBox','0 0 1200 700');
  lineChart(parts,20,20,1160,620,series.label+' by exact requested station',xs,[{label:series.label,values:series.values}],'centerline arc length [m]',series.unit);
  const xr=range(xs),yr=range(series.values),px=68,py=48,pw=1100,ph=562,x=sx(xs[state.station_index],xr[0],xr[1],px,pw);
  parts.push('<path d="M'+x+' '+py+'V'+(py+ph)+'" stroke="var(--accent)" stroke-dasharray="5 4" stroke-width="1.5"/>');
  if(finite(series.values[state.station_index])){const y=sy(series.values[state.station_index],yr[0],yr[1],py,ph);parts.push('<circle cx="'+x+'" cy="'+y+'" r="7" fill="var(--accent)" stroke="var(--bg)" stroke-width="2"/>');}
  svg.innerHTML=parts.join('');
  const details={
    station_index:state.station_index,
    station_arclength_m:sample.station_arclength_m,
    status:sample.status,
    sampling_method:sample.sampling_method,
    centerline_position_m:sample.centerline_position_m,
    centerline_tangent:sample.centerline_tangent,
    selected_quantity:{series_id:series.series_id,label:series.label,unit:series.unit,value:series.values[state.station_index]},
    section:sample.section===null?null:{mass_flow_kg_s:sample.section.mass_flow_kg_s,momentum_flux_N:sample.section.momentum_flux_N,stagnation_enthalpy_flux_W:sample.section.stagnation_enthalpy_flux_W,total_energy_flow_W:sample.section.total_energy_flow_W,pressure_Pa:sample.section.pressure_Pa,ambient_pressure_Pa:sample.section.ambient_pressure_Pa,pressure_match_relative_residual:sample.section.pressure_match_relative_residual,area_m2:sample.section.area_m2,characteristic_radius_m:sample.section.characteristic_radius_m,species_mass_flows_kg_s:sample.section.species_mass_flows_kg_s,cross_section_second_moment_m2:sample.section.cross_section_second_moment_m2,uncertainty:sample.section.uncertainty},
    interpolation_performed:false,
    absent_species_values:'masked; not treated as zero',
  };
  selectionBox.textContent=JSON.stringify(details,null,2);
}
function drawSpatialLocalField(){
  const channel=DATA.channels.find(value=>value.field_id===state.field_id)||DATA.channels[0],axes={XY:[0,1,'x','y'],XZ:[0,2,'x','z'],YZ:[1,2,'y','z']}[state.projection],points=DATA.points_m,values=channel.values,statuses=channel.sample_status,validValues=values.filter((value,index)=>value!==null&&statuses[index].code==='ok'&&finite(value)),valueRange=range(validValues),coordinates=points.map(point=>[point[axes[0]],point[axes[1]]]),rawX=range(coordinates.map(point=>point[0])),rawY=range(coordinates.map(point=>point[1])),span=Math.max(rawX[1]-rawX[0],rawY[1]-rawY[0],1e-12),centerX=(rawX[0]+rawX[1])/2,centerY=(rawY[0]+rawY[1])/2,plotX=145,plotY=92,plotSize=500,parts=[];
  svg.setAttribute('viewBox','0 0 1200 720');
  text(parts,26,28,channel.semantic+' — '+channel.field_id+' ['+channel.unit+']',15);
  text(parts,26,48,'Exact point samples in '+DATA.coordinate_frame_id+'; no connecting surface or spatial interpolation.',10,'start','var(--muted)');
  parts.push('<rect x="'+plotX+'" y="'+plotY+'" width="'+plotSize+'" height="'+plotSize+'" fill="none" stroke="var(--line)"/>');
  for(let tick=0;tick<=4;tick++){
    const gx=plotX+plotSize*tick/4,gy=plotY+plotSize*tick/4,coordinateX=centerX-span/2+span*tick/4,coordinateY=centerY+span/2-span*tick/4;
    parts.push('<path d="M'+gx+' '+plotY+'V'+(plotY+plotSize)+' M'+plotX+' '+gy+'H'+(plotX+plotSize)+'" stroke="var(--line)" opacity=".35"/>');
    text(parts,gx,plotY+plotSize+17,coordinateX.toPrecision(4),9,'middle','var(--muted)');
    text(parts,plotX-8,gy+3,coordinateY.toPrecision(4),9,'end','var(--muted)');
  }
  text(parts,plotX+plotSize/2,plotY+plotSize+37,axes[2]+' [m]',11,'middle','var(--muted)');
  text(parts,plotX-44,plotY+plotSize/2,axes[3]+' [m]',11,'middle','var(--muted)');
  const toX=value=>plotX+(value-(centerX-span/2))/span*plotSize,toY=value=>plotY+plotSize-(value-(centerY-span/2))/span*plotSize;
  for(let index=0;index<points.length;index++){
    const value=values[index],valid=value!==null&&statuses[index].code==='ok'&&finite(value),normalized=valid?(value-valueRange[0])/(valueRange[1]-valueRange[0]):0,color=valid?'rgb('+Math.round(45+200*normalized)+','+Math.round(95+80*(1-Math.abs(2*normalized-1)))+','+Math.round(205-165*normalized)+')':'#aeb9c4',x=toX(coordinates[index][0]),y=toY(coordinates[index][1]),selected=index===state.point_index;
    if(selected)parts.push('<circle cx="'+x+'" cy="'+y+'" r="10" fill="none" stroke="var(--accent)" stroke-width="3"/>');
    parts.push('<circle cx="'+x+'" cy="'+y+'" r="'+(selected?6:5)+'" fill="'+color+'" stroke="var(--fg)" stroke-width="1" data-point-index="'+index+'" tabindex="0" role="button" aria-label="query point '+index+'; '+axes[2]+'='+coordinates[index][0]+' m; '+axes[3]+'='+coordinates[index][1]+' m; status '+esc(statuses[index].code)+'" style="cursor:pointer"/>');
  }
  const legendX=760,legendY=125,legendHeight=300;
  text(parts,legendX,legendY-12,'Value ['+channel.unit+']',12);
  for(let step=0;step<24;step++){
    const normalized=1-step/23,color='rgb('+Math.round(45+200*normalized)+','+Math.round(95+80*(1-Math.abs(2*normalized-1)))+','+Math.round(205-165*normalized)+')';
    parts.push('<rect x="'+legendX+'" y="'+(legendY+step*legendHeight/24)+'" width="22" height="'+(legendHeight/24+1)+'" fill="'+color+'"/>');
  }
  text(parts,legendX+32,legendY+9,valueRange[1].toPrecision(5),10);
  text(parts,legendX+32,legendY+legendHeight,valueRange[0].toPrecision(5),10);
  parts.push('<circle cx="'+(legendX+11)+'" cy="'+(legendY+legendHeight+35)+'" r="5" fill="#aeb9c4" stroke="var(--fg)"/>');
  text(parts,legendX+32,legendY+legendHeight+39,'invalid or unavailable sample',10);
  text(parts,legendX,legendY+legendHeight+78,'Coordinates are plotted at equal metric scale.',10,'start','var(--muted)');
  svg.innerHTML=parts.join('');
  svg.querySelectorAll('[data-point-index]').forEach(node=>{
    const selectPoint=()=>{state.point_index=Number(node.getAttribute('data-point-index'));const input=document.getElementById('point');if(input)input.value=String(state.point_index);draw();};
    node.addEventListener('click',selectPoint);node.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();selectPoint();}});
  });
  const index=state.point_index,status=statuses[index],uncertainty=channel.absolute_standard_uncertainty;
  selectionBox.textContent=JSON.stringify({point_index:index,coordinates_m:points[index],coordinate_frame_id:DATA.coordinate_frame_id,field_id:channel.field_id,semantic:channel.semantic,unit:channel.unit,value:values[index],status,sampling_method:channel.sampling_method,absolute_standard_uncertainty:uncertainty===null?null:uncertainty[index],spatial_interpolation_performed:false,query_order_is_path_or_time:false},null,2);
}
function zonePaletteColor(value,paletteName){
  const palettes={
    viridis:['#440154','#414487','#2a788e','#22a884','#7ad151','#fde725'],
    plasma:['#0d0887','#7e03a8','#cc4778','#f89540','#f0f921'],
    inferno:['#000004','#57106e','#bc3754','#f98e09','#fcffa4'],
    magma:['#000004','#51127c','#b73779','#fc8961','#fcfdbf'],
    cividis:['#00204c','#414d6b','#7c7b78','#bcae6c','#fee838'],
    coolwarm:['#3b4cc0','#8db0fe','#dddddd','#f4987a','#b40426'],
  };
  const stops=palettes[paletteName]||palettes.viridis,t=Math.max(0,Math.min(1,value))*(stops.length-1),index=Math.min(stops.length-2,Math.floor(t)),fraction=t-index;
  const left=stops[index].slice(1),right=stops[index+1].slice(1),parts=[];
  for(let channel=0;channel<3;channel++){const a=parseInt(left.slice(channel*2,channel*2+2),16),b=parseInt(right.slice(channel*2,channel*2+2),16);parts.push(Math.round(a+(b-a)*fraction).toString(16).padStart(2,'0'));}
  return '#'+parts.join('');
}
function drawAxisymmetricZoneField(){
  const zones=DATA.zones,field=DATA.fields.find(value=>value.field_id===state.field_id)||DATA.fields[0],selectedIndex=state.zone_index,selected=zones[selectedIndex],allPoints=zones.flatMap(zone=>zone.polygon_xr_m),xs=allPoints.map(point=>point[0]),rs=allPoints.map(point=>point[1]),xMin=Math.min(...xs),xMax=Math.max(...xs),rMin=Math.min(...rs),rMax=Math.max(...rs),span=Math.max(xMax-xMin,rMax-rMin,1e-12),plot={x:105,y:76,w:800,h:560},scale=Math.min((plot.w-36)/span,(plot.h-36)/span),drawW=(xMax-xMin)*scale,drawH=(rMax-rMin)*scale,left=plot.x+(plot.w-drawW)/2,top=plot.y+(plot.h-drawH)/2,valid=field.field_id==='phase'?[]:zones.map(zone=>zone[field.field_id]).filter(value=>value!==null&&finite(value)),valueRange=range(valid),phases=[...new Set(zones.map(zone=>zone.phase))].sort(),parts=[];
  const requestedPalette=DATA.view_spec.color_map,paletteKnown=['viridis','plasma','inferno','magma','cividis','coolwarm'].includes(requestedPalette),usedPalette=paletteKnown?requestedPalette:'viridis';
  const toX=value=>left+(value-xMin)*scale,toY=value=>top+(rMax-value)*scale;
  svg.setAttribute('viewBox','0 0 1200 720');
  text(parts,28,28,field.label+' ['+field.unit+'] by exact declared zone',15);
  text(parts,28,49,DATA.axis_definition+'; supplied polygons only; no between-zone interpolation or 3-D revolution.',10,'start','var(--muted)');
  parts.push('<rect x="'+plot.x+'" y="'+plot.y+'" width="'+plot.w+'" height="'+plot.h+'" fill="none" stroke="var(--line)"/>');
  for(let tick=0;tick<=4;tick++){
    const gx=plot.x+plot.w*tick/4,gy=plot.y+plot.h*tick/4;
    parts.push('<path d="M'+gx+' '+plot.y+'V'+(plot.y+plot.h)+' M'+plot.x+' '+gy+'H'+(plot.x+plot.w)+'" stroke="var(--line)" opacity=".25"/>');
    text(parts,gx,plot.y+plot.h+17,(xMin+(xMax-xMin)*tick/4).toPrecision(4),9,'middle','var(--muted)');
    text(parts,plot.x-8,gy+3,(rMax-(rMax-rMin)*tick/4).toPrecision(4),9,'end','var(--muted)');
  }
  text(parts,plot.x+plot.w/2,plot.y+plot.h+37,'axial coordinate x [m]',11,'middle','var(--muted)');
  const radialLabelY=plot.y+plot.h/2;
  parts.push('<text x="27" y="'+radialLabelY+'" transform="rotate(-90 27 '+radialLabelY+')" font-size="11" text-anchor="middle" fill="var(--muted)">radial coordinate r [m]</text>');
  for(let index=0;index<zones.length;index++){
    const zone=zones[index],raw=field.field_id==='phase'?zone.phase:zone[field.field_id],value=typeof raw==='number'&&finite(raw)?raw:null,normalized=value===null?null:(value-valueRange[0])/(valueRange[1]-valueRange[0]),phaseIndex=phases.indexOf(zone.phase),fill=field.field_id==='phase'?colors[phaseIndex%colors.length]:value===null?'#aeb9c4':zonePaletteColor(normalized,usedPalette),selectedZone=index===selectedIndex,points=zone.polygon_xr_m.map(point=>toX(point[0])+','+toY(point[1])).join(' '),label=zone.zone_id+'; cell '+zone.cell_index+'; '+field.label+'='+(raw===null?'not supplied':raw)+'; phase '+zone.phase+'; geometry '+zone.geometry_status;
    parts.push('<polygon points="'+points+'" fill="'+fill+'" fill-opacity=".88" stroke="'+(selectedZone?'var(--accent)':'#263746')+'" stroke-width="'+(selectedZone?3:1)+'" data-zone-index="'+index+'" tabindex="0" role="button" aria-label="'+esc(label)+'" style="cursor:pointer"><title>'+esc(label)+'</title></polygon>');
  }
  const legendX=960;
  if(field.field_id==='phase'){
    text(parts,legendX,plot.y+2,'Declared phase',12);
    phases.forEach((phase,index)=>{const y=plot.y+28+index*26;parts.push('<rect x="'+legendX+'" y="'+(y-12)+'" width="16" height="16" fill="'+colors[index%colors.length]+'"/>');text(parts,legendX+25,y,phase,10);});
  }else{
    text(parts,legendX,plot.y+2,'Value ['+field.unit+']',12);
    for(let step=0;step<24;step++)parts.push('<rect x="'+legendX+'" y="'+(plot.y+20+step*10)+'" width="20" height="11" fill="'+zonePaletteColor(1-step/23,usedPalette)+'"/>');
    text(parts,legendX+29,plot.y+29,valueRange[1].toPrecision(5),10);
    text(parts,legendX+29,plot.y+253,valueRange[0].toPrecision(5),10);
    parts.push('<rect x="'+legendX+'" y="'+(plot.y+276)+'" width="16" height="16" fill="#aeb9c4"/>');text(parts,legendX+25,plot.y+289,'not supplied',10);
    text(parts,legendX,plot.y+326,'Color map: '+usedPalette+(paletteKnown?'':' (fallback; requested '+requestedPalette+')'),9,'start',paletteKnown?'var(--muted)':'var(--accent)');
  }
  text(parts,legendX,plot.y+390,'Select a polygon or exact zone',10,'start','var(--muted)');
  text(parts,legendX,plot.y+410,'Equal metric scale',10,'start','var(--muted)');
  svg.innerHTML=parts.join('');
  svg.querySelectorAll('[data-zone-index]').forEach(node=>{
    const selectZone=()=>{state.zone_index=Number(node.getAttribute('data-zone-index'));const control=document.getElementById('zone');if(control)control.value=String(state.zone_index);draw();};
    node.addEventListener('click',selectZone);node.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();selectZone();}});
  });
  const rawValue=field.field_id==='phase'?selected.phase:selected[field.field_id];
  const valueText=(value,unit='')=>{
    if(value===null||value===undefined)return 'not supplied';
    if(typeof value==='number')return Number.isFinite(value)?(Number.isInteger(value)?String(value):Number(value).toPrecision(6))+(unit&&unit!=='1'?' '+unit:''):'not supplied';
    return String(value);
  };
  const heading=document.createElement('strong');
  heading.textContent='Selected zone '+selected.zone_id;
  selectionBox.classList.add('zone-selection');
  selectionBox.replaceChildren(heading);
  const inspector=document.createElement('div');
  inspector.className='zone-inspector';
  const addInspectorItem=(label,value)=>{
    const item=document.createElement('div');item.className='item';
    const name=document.createElement('strong');name.textContent=label;
    const content=document.createElement('span');content.textContent=value;
    item.append(name,content);inspector.appendChild(item);
  };
  addInspectorItem('Selected quantity',field.label+': '+valueText(rawValue,field.unit));
  addInspectorItem('Cell',valueText(selected.cell_index));
  addInspectorItem('Region',selected.region_label||selected.region_type||'not declared');
  addInspectorItem('Phase',selected.phase||'not declared');
  addInspectorItem('Geometry status',selected.geometry_status);
  addInspectorItem('Static pressure',valueText(selected.static_pressure_Pa,'Pa'));
  addInspectorItem('Static temperature',valueText(selected.static_temperature_K,'K'));
  addInspectorItem('Density',valueText(selected.density_kgpm3,'kg/m³'));
  addInspectorItem('Mach',valueText(selected.mach));
  addInspectorItem('Shock angle',valueText(selected.shock_angle_rad,'rad'));
  addInspectorItem('Turn angle',valueText(selected.turn_angle_rad,'rad'));
  const note=document.createElement('p');note.className='zone-note';
  note.textContent=DATA.axis_definition+'; supplied polygon only; no between-zone interpolation or 3-D revolution.';
  inspector.appendChild(note);
  const polygonDetails=document.createElement('details');
  const polygonSummary=document.createElement('summary');polygonSummary.textContent='Exact polygon vertices (x, r) [m]';
  const polygonValues=document.createElement('pre');polygonValues.textContent=JSON.stringify(selected.polygon_xr_m,null,2);
  polygonDetails.append(polygonSummary,polygonValues);
  inspector.appendChild(polygonDetails);
  selectionBox.appendChild(inspector);
}
function draw(){
  if(DATA.product==='visual')drawVisual();
  if(DATA.product==='signature')drawSignature();
  if(DATA.product==='ray-transfer')drawRay();
  if(DATA.product==='spectral-radiance-image')drawSpectralRadianceImage();
  if(DATA.product==='flux')drawFlux();
  if(DATA.product==='engineering-flux-series'){drawEngineeringFluxSeries();return;}
  if(DATA.product==='spatial-local-field'){drawSpatialLocalField();return;}
  if(DATA.product==='axisymmetric-zone-field'){drawAxisymmetricZoneField();return;}
  if(DATA.canonical_v1&&DATA.product==='ray-transfer'){
    const selected=DATA.rays.find(ray=>ray.ray_id===state.ray_id),wavelength=state.wavelength_index;
    const uncertainty=selected.absolute_standard_uncertainty&&selected.absolute_standard_uncertainty[wavelength];
    const uncertaintyText=!selected.validity_mask[wavelength]?'invalid sample; uncertainty unavailable':finite(uncertainty)?uncertainty+' W m⁻² sr⁻¹ m⁻¹':DATA.uncertainty_matrix_supplied?'no estimate available for this sample':'no uncertainty matrix supplied';
    selectionBox.textContent='Current linked selection:\n'+JSON.stringify(currentSelection(),null,2)+'\nAbsolute standard uncertainty: '+uncertaintyText;
    return;
  }
  if(DATA.product!=='spectral-radiance-image')selectionBox.textContent='Current linked selection:\n'+JSON.stringify(currentSelection(),null,2);
}
installControls();draw();
</script></main></body></html>'''
  )
####


def write_interactive_product_gallery(
  result: ProductResult
  | SpectralRadianceImageResult
  | EngineeringFluxSectionResult
  | SpatialLocalFieldResult
  | AxisymmetricZoneFieldResult
  | AxisymmetricZoneField
  | AxisymmetricZone
  | CanonicalAxisymmetricZoneFieldData
  | CanonicalSpectralRayTransferData,
  path: str | Path,
  *,
  spec: VisualizationSpec
  | SpectralRadianceImageGallerySpec
  | EngineeringFluxSectionGallerySpec
  | SpatialLocalFieldGallerySpec
  | AxisymmetricZoneGallerySpec
  | CanonicalSpectralRayTransferGallerySpec
  | None = None,
) -> Path:
  """Write one standalone linked HTML gallery for a supported product result."""

  if isinstance(
    result,
    (
      AxisymmetricZoneFieldResult,
      AxisymmetricZoneField,
      AxisymmetricZone,
      CanonicalAxisymmetricZoneFieldData,
    ),
  ):
    if spec is not None and not isinstance(spec, AxisymmetricZoneGallerySpec):
      raise TypeError('axisymmetric-zone galleries require AxisymmetricZoneGallerySpec')
    zone_data = (
      result
      if isinstance(result, CanonicalAxisymmetricZoneFieldData)
      else extract_canonical_visualization_data(result)
    )
    if not isinstance(zone_data, CanonicalAxisymmetricZoneFieldData):
      raise TypeError('zone input did not produce canonical zone-field data')
    resolved_zone_spec = spec or AxisymmetricZoneGallerySpec.for_data(zone_data)
    payload = _axisymmetric_zone_payload(result, resolved_zone_spec)
  elif isinstance(result, SpectralRadianceImageResult):
    if spec is not None and not isinstance(spec, SpectralRadianceImageGallerySpec):
      raise TypeError('spectral-radiance image galleries require SpectralRadianceImageGallerySpec')
    resolved_image_spec = spec or SpectralRadianceImageGallerySpec.for_result(result)
    resolved_image_spec.validate_for_result(result)
    payload = _spectral_radiance_image_payload(result, resolved_image_spec)
  elif isinstance(result, EngineeringFluxSectionResult):
    if spec is not None and not isinstance(spec, EngineeringFluxSectionGallerySpec):
      raise TypeError('engineering-flux galleries require EngineeringFluxSectionGallerySpec')
    resolved_flux_spec = spec or EngineeringFluxSectionGallerySpec.for_result(result)
    payload = _engineering_flux_payload(result, resolved_flux_spec)
  elif isinstance(result, SpatialLocalFieldResult):
    if spec is not None and not isinstance(spec, SpatialLocalFieldGallerySpec):
      raise TypeError('spatial local-field galleries require SpatialLocalFieldGallerySpec')
    local_field_data = extract_canonical_visualization_data(result)
    resolved_local_field_spec = spec or SpatialLocalFieldGallerySpec.for_data(local_field_data)
    payload = _spatial_local_field_payload(result, resolved_local_field_spec)
  elif isinstance(result, CanonicalSpectralRayTransferData):
    if spec is not None and not isinstance(spec, CanonicalSpectralRayTransferGallerySpec):
      raise TypeError('canonical ray-transfer galleries require CanonicalSpectralRayTransferGallerySpec')
    resolved_canonical_ray_spec = spec or CanonicalSpectralRayTransferGallerySpec.for_data(result)
    payload = _canonical_ray_payload(result, resolved_canonical_ray_spec)
  elif isinstance(result, SectionedTubeResult):
    if spec is not None and not isinstance(spec, VisualizationSpec):
      raise TypeError('standard product galleries require VisualizationSpec')
    resolved = _resolve_spec(result, spec, default_view_kind='visual.interactive', product_prefix='visual')
    payload = _visual_payload(result, resolved)
  elif isinstance(result, SpectralRadiantIntensityResult):
    if spec is not None and not isinstance(spec, VisualizationSpec):
      raise TypeError('standard product galleries require VisualizationSpec')
    resolved = _resolve_spec(result, spec, default_view_kind='signature.interactive', product_prefix='signature')
    payload = _signature_payload(result, resolved)
  elif isinstance(result, SpectralRayTransferResult):
    if spec is not None and not isinstance(spec, VisualizationSpec):
      raise TypeError('standard product galleries require VisualizationSpec')
    resolved = _resolve_spec(result, spec, default_view_kind='ray-transfer.interactive', product_prefix='ray-transfer')
    payload = _ray_payload(result, resolved)
  elif isinstance(result, PlumeFluxSectionResult):
    if spec is not None and not isinstance(spec, VisualizationSpec):
      raise TypeError('standard product galleries require VisualizationSpec')
    resolved = _resolve_spec(result, spec, default_view_kind='flux.interactive', product_prefix='flux')
    payload = _flux_payload(result, resolved)
  else:
    raise TypeError('result must be a supported canonical Visualization result')
  ####
  output = Path(path)
  output.parent.mkdir(parents=True, exist_ok=True)
  output.write_text(_page_shell(payload), encoding='utf-8')
  return output
####
