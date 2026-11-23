"""Static views for canonical axisymmetric zone-field contracts.

These views retain the supplied axial/radial polygons and zone values. They
do not revolve a meridional field into 3-D geometry or infer source provenance
that the zone-field capability does not carry.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any

from exhaust_plume.contracts.common_v1 import canonical_digest
from exhaust_plume.contracts.spatial import AxisymmetricZone, AxisymmetricZoneField
from exhaust_plume.contracts.spatial_v1 import AxisymmetricZoneFieldResult
from exhaust_plume.contracts.visualization import (
  CanonicalAxisymmetricZoneFieldData,
  extract_canonical_visualization_data,
)

__all__ = (
  'AXISYMMETRIC_ZONE_GALLERY_SCHEMA',
  'AxisymmetricZoneGalleryArtifact',
  'AxisymmetricZoneGalleryManifest',
  'AxisymmetricZoneGallerySpec',
  'render_axisymmetric_zone_gallery',
  'write_axisymmetric_zone_gallery_manifest',
)

AXISYMMETRIC_ZONE_GALLERY_SCHEMA = 'plume.visualization.axisymmetric-zone-gallery@1'
_HASH = re.compile(r'^[0-9a-f]{64}$')
_FIELDS = {
  'static_pressure_Pa': ('Static pressure', 'Pa'),
  'static_temperature_K': ('Static temperature', 'K'),
  'density_kgpm3': ('Density', 'kg/m³'),
  'mach': ('Mach number', '1'),
  'shock_angle_rad': ('Declared shock angle', 'rad'),
  'turn_angle_rad': ('Declared flow turn angle', 'rad'),
}
_DEFAULT_FIELDS = tuple(name for name in _FIELDS if name not in {
  'shock_angle_rad',
  'turn_angle_rad',
})


def _field_data(
  value: AxisymmetricZoneField
  | AxisymmetricZone
  | AxisymmetricZoneFieldResult
  | CanonicalAxisymmetricZoneFieldData,
) -> CanonicalAxisymmetricZoneFieldData:
  if isinstance(value, CanonicalAxisymmetricZoneFieldData):
    return value
  ####
  if isinstance(value, (AxisymmetricZoneField, AxisymmetricZone, AxisymmetricZoneFieldResult)):
    result = extract_canonical_visualization_data(value)
    if not isinstance(result, CanonicalAxisymmetricZoneFieldData):
      raise TypeError('zone input did not produce canonical zone-field data')
    ####
    return result
  ####
  raise TypeError(
    'value must be an AxisymmetricZoneField, AxisymmetricZone, AxisymmetricZoneFieldResult, or '
    'CanonicalAxisymmetricZoneFieldData'
  )
####


@dataclass(frozen=True, slots=True)
class AxisymmetricZoneGallerySpec:
  """Exact field selection bound to one canonical zone-field payload."""

  zone_field_digest_sha256: str
  display_fields: tuple[str, ...] = _DEFAULT_FIELDS
  color_map: str = 'viridis'

  def __post_init__(self) -> None:
    if not isinstance(self.zone_field_digest_sha256, str) or not _HASH.fullmatch(
      self.zone_field_digest_sha256
    ):
      raise ValueError('zone_field_digest_sha256 must be a lowercase SHA-256 digest')
    ####
    fields = tuple(str(value) for value in self.display_fields)
    if not fields or len(fields) != len(set(fields)):
      raise ValueError('display_fields must be non-empty and unique')
    ####
    if any(value not in _FIELDS for value in fields):
      raise ValueError(f'display_fields must use declared zone fields: {tuple(_FIELDS)}')
    ####
    if not isinstance(self.color_map, str) or not self.color_map:
      raise ValueError('color_map must be a non-empty string')
    ####
    object.__setattr__(self, 'display_fields', fields)
  ####

  @classmethod
  def for_data(
    cls,
    data: CanonicalAxisymmetricZoneFieldData,
    **overrides: Any,
  ) -> AxisymmetricZoneGallerySpec:
    if not isinstance(data, CanonicalAxisymmetricZoneFieldData):
      raise TypeError('data must be CanonicalAxisymmetricZoneFieldData')
    ####
    if 'display_fields' not in overrides:
      optional_fields = tuple(
        field_id
        for field_id in ('shock_angle_rad', 'turn_angle_rad')
        if any(getattr(zone, field_id) is not None for zone in data.zones)
      )
      overrides['display_fields'] = (*_DEFAULT_FIELDS, *optional_fields)
    ####
    return cls(zone_field_digest_sha256=canonical_digest(data.model_dump()), **overrides)
  ####

  def validate_for_data(self, data: CanonicalAxisymmetricZoneFieldData) -> None:
    if not isinstance(data, CanonicalAxisymmetricZoneFieldData):
      raise TypeError('data must be CanonicalAxisymmetricZoneFieldData')
    ####
    if self.zone_field_digest_sha256 != canonical_digest(data.model_dump()):
      raise ValueError('zone gallery spec is bound to a different zone-field payload')
    ####
  ####

  def model_dump(self) -> dict[str, Any]:
    return {
      'schema': 'plume.visualization.axisymmetric-zone-view-spec@1',
      'zone_field_digest_sha256': self.zone_field_digest_sha256,
      'display_fields': list(self.display_fields),
      'color_map': self.color_map,
    }
  ####

  def digest_sha256(self) -> str:
    return canonical_digest(self.model_dump())
  ####
####


@dataclass(frozen=True, slots=True)
class AxisymmetricZoneGalleryArtifact:
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
class AxisymmetricZoneGalleryManifest:
  spec: AxisymmetricZoneGallerySpec
  zone_field: dict[str, Any]
  artifacts: tuple[AxisymmetricZoneGalleryArtifact, ...]
  guardrails: tuple[str, ...]
  manifest_path: Path

  def model_dump(self) -> dict[str, Any]:
    return {
      'schema': AXISYMMETRIC_ZONE_GALLERY_SCHEMA,
      'zone_field_digest_sha256': self.spec.zone_field_digest_sha256,
      'view_spec': self.spec.model_dump(),
      'view_spec_digest_sha256': self.spec.digest_sha256(),
      'zone_field': dict(self.zone_field),
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


def _plot_dependencies() -> tuple[Any, Any]:
  try:
    from matplotlib import pyplot as plt
    from matplotlib.colors import Normalize
    from matplotlib.patches import Patch
  except ImportError as error:
    raise RuntimeError(
      'axisymmetric zone galleries require the optional plot dependency: '
      'pip install .[plot]'
    ) from error
  ####
  return plt, (Normalize, Patch)
####


def _axes_style(axis: Any, data: CanonicalAxisymmetricZoneFieldData) -> None:
  minimum, maximum = data.bounds_xr_m
  axis.set_xlim(minimum[0], maximum[0])
  axis.set_ylim(minimum[1], maximum[1])
  axis.set_aspect('equal', adjustable='box')
  axis.set_xlabel('Axial coordinate x [m]')
  axis.set_ylabel('Radial coordinate r [m]')
  axis.grid(True, alpha=0.2)
####


def _figure_size(data: CanonicalAxisymmetricZoneFieldData) -> tuple[float, float]:
  minimum, maximum = data.bounds_xr_m
  x_span = maximum[0] - minimum[0]
  r_span = maximum[1] - minimum[1]
  width = 9.0
  height = max(3.2, min(10.0, 2.25 + 0.72 * width * r_span / x_span))
  return width, height
####


def _render_scalar_field(
  plt: Any,
  Normalize: Any,
  Patch: Any,
  data: CanonicalAxisymmetricZoneFieldData,
  field_id: str,
  color_map: str,
  output: Path,
) -> AxisymmetricZoneGalleryArtifact:
  semantic, unit = _FIELDS[field_id]
  raw_values = tuple(getattr(zone, field_id) for zone in data.zones)
  values = tuple(None if value is None else float(value) for value in raw_values)
  finite_values = tuple(value for value in values if value is not None)
  if not finite_values:
    raise ValueError(f'zone field {field_id!r} has no declared values to render')
  ####
  minimum = min(finite_values)
  maximum = max(finite_values)
  scale = max(abs(minimum), abs(maximum), 1.0)
  if maximum - minimum <= 1.0e-6 * scale:
    width = max(1.0e-3 * scale, 1.0e-6)
    normalization = Normalize(vmin=minimum - width, vmax=maximum + width)
  else:
    normalization = Normalize(vmin=minimum, vmax=maximum)
  ####
  cmap = plt.get_cmap(color_map)
  figure, axis = plt.subplots(figsize=_figure_size(data))
  missing_zones = False
  for zone, value in zip(data.zones, values, strict=True):
    if value is None:
      missing_zones = True
      facecolor = '#cbd2d9'
    else:
      facecolor = cmap(normalization(value))
    ####
    axis.fill(
      [point[0] for point in zone.polygon_xr_m],
      [point[1] for point in zone.polygon_xr_m],
      facecolor=facecolor,
      edgecolor='#263746',
      linewidth=0.45,
      alpha=0.88,
    )
  ####
  _axes_style(axis, data)
  axis.set_title(f'{semantic} by declared zone')
  figure.colorbar(
    plt.cm.ScalarMappable(norm=normalization, cmap=color_map),
    ax=axis,
    label=f'{semantic} [{unit}]',
    format='%.6g',
  )
  if missing_zones:
    axis.legend(
      handles=(Patch(facecolor='#cbd2d9', edgecolor='#263746', label='not supplied'),),
      loc='best',
      fontsize=8,
    )
  ####
  figure.suptitle(
    f"{data.capability_id.value} v{data.major_version} | {data.axis_definition}"
  )
  figure.tight_layout(rect=(0.0, 0.0, 1.0, 0.93))
  path = output / f'axisymmetric_zone_{field_id}.png'
  figure.savefig(path, dpi=150, bbox_inches='tight')
  plt.close(figure)
  return AxisymmetricZoneGalleryArtifact(
    f'zone.field.{field_id}',
    path.name,
    'image/png',
  )
####


def _render_zone_phases(
  plt: Any,
  Patch: Any,
  data: CanonicalAxisymmetricZoneFieldData,
  output: Path,
) -> AxisymmetricZoneGalleryArtifact:
  phases = tuple(sorted({zone.phase for zone in data.zones}))
  cmap = plt.get_cmap('tab20')
  phase_colors = {phase: cmap(index % cmap.N) for index, phase in enumerate(phases)}
  status_counts: dict[str, int] = {}
  for zone in data.zones:
    status_counts[zone.geometry_status] = status_counts.get(zone.geometry_status, 0) + 1
  ####
  figure, axis = plt.subplots(figsize=_figure_size(data))
  for zone in data.zones:
    axis.fill(
      [point[0] for point in zone.polygon_xr_m],
      [point[1] for point in zone.polygon_xr_m],
      facecolor=phase_colors[zone.phase],
      edgecolor='#263746',
      linewidth=0.45,
      alpha=0.72,
    )
  ####
  _axes_style(axis, data)
  handles = tuple(
    Patch(
      facecolor=phase_colors[phase],
      edgecolor='#263746',
      label=phase if phase else '(empty phase)',
    )
    for phase in phases
  )
  figure.legend(
    handles=handles,
    title='Declared phase',
    loc='upper center',
    bbox_to_anchor=(0.5, 0.94),
    ncol=max(1, len(handles)),
    fontsize=8,
  )
  axis.set_title(
    'Zone geometry by declared phase; geometry status: '
    + ', '.join(f'{name}={count}' for name, count in sorted(status_counts.items()))
  )
  figure.suptitle(
    f"{data.capability_id.value} v{data.major_version} | {data.axis_definition}"
  )
  figure.tight_layout(rect=(0.0, 0.0, 1.0, 0.86))
  path = output / 'axisymmetric_zone_phases.png'
  figure.savefig(path, dpi=150, bbox_inches='tight')
  plt.close(figure)
  return AxisymmetricZoneGalleryArtifact(
    'zone.phase-map',
    path.name,
    'image/png',
  )
####


def _write_zone_values_csv(
  data: CanonicalAxisymmetricZoneFieldData,
  data_digest: str,
  output: Path,
) -> Path:
  path = output / 'axisymmetric_zone_values.csv'
  with path.open('w', encoding='utf-8', newline='') as handle:
    writer = csv.writer(handle, lineterminator='\n')
    writer.writerow((
      'zone_field_digest_sha256',
      'capability_id',
      'major_version',
      'axis_definition',
      'zone_id',
      'cell_index',
      'phase',
      'region_type',
      'region_label',
      'geometry_status',
      'polygon_xr_m_json',
      'static_pressure_Pa',
      'static_temperature_K',
      'density_kgpm3',
      'mach',
      'shock_angle_rad',
      'turn_angle_rad',
    ))
    for zone in data.zones:
      writer.writerow((
        data_digest,
        data.capability_id.value,
        data.major_version,
        data.axis_definition,
        zone.zone_id,
        zone.cell_index,
        zone.phase,
        zone.region_type or '',
        zone.region_label or '',
        zone.geometry_status,
        json.dumps(zone.model_dump()['polygon_xr_m'], separators=(',', ':')),
        zone.static_pressure_Pa,
        zone.static_temperature_K,
        zone.density_kgpm3,
        zone.mach,
        '' if zone.shock_angle_rad is None else zone.shock_angle_rad,
        '' if zone.turn_angle_rad is None else zone.turn_angle_rad,
      ))
  return path
####


def write_axisymmetric_zone_gallery_manifest(
  manifest: AxisymmetricZoneGalleryManifest,
  path: str | Path | None = None,
) -> Path:
  output = manifest.manifest_path if path is None else Path(path)
  output.parent.mkdir(parents=True, exist_ok=True)
  output.write_text(manifest.canonical_json(), encoding='utf-8')
  return output
####


def render_axisymmetric_zone_gallery(
  value: AxisymmetricZoneField
  | AxisymmetricZone
  | AxisymmetricZoneFieldResult
  | CanonicalAxisymmetricZoneFieldData,
  output_dir: str | Path,
  *,
  spec: AxisymmetricZoneGallerySpec | None = None,
  render_plots: bool = True,
) -> AxisymmetricZoneGalleryManifest:
  """Write exact zone data and separate scalar/phase views in the x-r plane."""

  if not isinstance(render_plots, bool):
    raise TypeError('render_plots must be bool')
  ####
  data = _field_data(value)
  data_payload = data.model_dump()
  data_digest = canonical_digest(data_payload)
  resolved = spec or AxisymmetricZoneGallerySpec.for_data(data)
  resolved.validate_for_data(data)
  output = Path(output_dir)
  output.mkdir(parents=True, exist_ok=True)

  data_path = output / 'axisymmetric_zone_field.json'
  data_path.write_text(
    json.dumps(data_payload, allow_nan=False, ensure_ascii=True, indent=2, sort_keys=True)
    + '\n',
    encoding='utf-8',
  )
  csv_path = _write_zone_values_csv(data, data_digest, output)
  artifacts = [
    AxisymmetricZoneGalleryArtifact(
      'metadata.axisymmetric-zone-field',
      data_path.name,
      'application/json',
    ),
    AxisymmetricZoneGalleryArtifact(
      'zone.values',
      csv_path.name,
      'text/csv',
    ),
  ]

  if render_plots:
    plt, helpers = _plot_dependencies()
    Normalize, Patch = helpers
    for field_id in resolved.display_fields:
      artifacts.append(
        _render_scalar_field(
          plt,
          Normalize,
          Patch,
          data,
          field_id,
          resolved.color_map,
          output,
        )
      )
    artifacts.append(_render_zone_phases(plt, Patch, data, output))
  ####

  manifest = AxisymmetricZoneGalleryManifest(
    spec=resolved,
    zone_field={
      'capability_id': data.capability_id.value,
      'major_version': data.major_version,
      'axis_definition': data.axis_definition,
      'zone_count': len(data.zones),
      'data_digest_sha256': data_digest,
      'source_provenance': (
        data.source_context.model_dump()
        if data.source_context is not None
        else 'not supplied by the axisymmetric-zone-field contract'
      ),
    },
    artifacts=tuple(artifacts),
    guardrails=(
      'each polygon and scalar is copied from its declared zone; no scalar field is interpolated',
      'views remain in the declared two-dimensional axial/radial plane',
      'the renderer does not revolve zones into three-dimensional plume geometry',
      'source provenance and physical validation claims are not added by visualization',
    ),
    manifest_path=output / 'axisymmetric_zone_gallery_manifest.json',
  )
  write_axisymmetric_zone_gallery_manifest(manifest)
  return manifest
####
