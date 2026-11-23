"""Optional static galleries for the strict standard product results.

The gallery is an evaluation surface, not another product model.  It consumes
the renderer-neutral projections from :mod:`exhaust_plume.api.visualization`,
keeps invalid samples masked, and writes a JSON manifest that binds every
image/table to its source result and exact :class:`VisualizationSpec`.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
import hashlib
import json
from math import atan2, cos, isfinite, pi, sin, sqrt
from pathlib import Path
import re
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
from exhaust_plume.contracts.capability import (
  SPATIAL_PROJECTED_AREA_CAPABILITY,
  SPATIAL_SUPPORT_CAPABILITY,
)
from exhaust_plume.contracts.common_v1 import canonical_digest
from exhaust_plume.contracts.engineering_flux_v1 import EngineeringFluxSectionResult
from exhaust_plume.contracts.spectral_radiance_image_v1 import SpectralRadianceImageResult
from exhaust_plume.contracts.spatial import AxisymmetricZone, AxisymmetricZoneField
from exhaust_plume.contracts.spatial_v1 import AxisymmetricZoneFieldResult
from exhaust_plume.contracts.visualization import (
  CanonicalAxisymmetricZoneFieldData,
  CanonicalEngineeringFluxSeriesData,
  CanonicalProjectedAreaData,
  CanonicalSpectralRayTransferData,
  CanonicalSpatialLocalFieldData,
  CanonicalSpatialSupportData,
  extract_canonical_visualization_data,
)
from exhaust_plume.contracts.local_field_v1 import SpatialLocalFieldResult
from exhaust_plume.products.workflow_zone_gallery import (
  AxisymmetricZoneGalleryManifest,
  AxisymmetricZoneGallerySpec,
  render_axisymmetric_zone_gallery,
)

__all__ = (
  'GALLERY_MANIFEST_SCHEMA',
  'CapabilityGalleryViewSpec',
  'EngineeringFluxSectionGallerySpec',
  'SpectralRadianceImageGallerySpec',
  'SpatialLocalFieldGallerySpec',
  'GalleryArtifact',
  'VisualizationGalleryManifest',
  'render_plume_flux_gallery',
  'render_capability_gallery',
  'render_projected_area_gallery',
  'render_engineering_flux_section_gallery',
  'render_product_gallery',
  'render_sectioned_tube_gallery',
  'render_spatial_support_gallery',
  'render_spatial_local_field_gallery',
  'render_spectral_radiance_image_gallery',
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
class CapabilityGalleryViewSpec:
  """View state bound to the exact payload of a supporting capability."""

  capability_id: str
  major_version: int
  content_sha256: str
  view_kind: str
  axes: tuple[str, ...]
  projections: tuple[str, ...] = ()
  source_context_sha256: str | None = None

  def __post_init__(self) -> None:
    if (
      not self.capability_id
      or isinstance(self.major_version, bool)
      or not isinstance(self.major_version, int)
      or self.major_version < 1
    ):
      raise ValueError('capability identity must be non-empty and versioned')
    ####
    if len(self.content_sha256) != 64 or any(
      character not in '0123456789abcdef' for character in self.content_sha256
    ):
      raise ValueError('content_sha256 must be a lowercase SHA-256 digest')
    ####
    if self.source_context_sha256 is not None and (
      len(self.source_context_sha256) != 64
      or any(character not in '0123456789abcdef' for character in self.source_context_sha256)
    ):
      raise ValueError('source_context_sha256 must be a lowercase SHA-256 digest or None')
    ####
    if not self.view_kind or not self.axes or any(not axis for axis in self.axes):
      raise ValueError('capability gallery view must declare a kind and axes')
    ####
    object.__setattr__(self, 'axes', tuple(self.axes))
    object.__setattr__(self, 'projections', tuple(self.projections))
  ####

  def model_dump(self, mode: str = 'python') -> dict[str, Any]:
    del mode
    return {
      'schema': 'plume.visualization.capability-view-spec@1',
      'capability_id': self.capability_id,
      'major_version': self.major_version,
      'content_sha256': self.content_sha256,
      'view_kind': self.view_kind,
      'axes': list(self.axes),
      'projections': list(self.projections),
      'source_context_sha256': self.source_context_sha256,
    }
  ####

  def digest_sha256(self) -> str:
    canonical = json.dumps(
      self.model_dump(mode='json'),
      allow_nan=False,
      ensure_ascii=True,
      separators=(',', ':'),
      sort_keys=True,
    )
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()
  ####
####


@dataclass(frozen=True, slots=True)
class CanonicalSpectralRayTransferGallerySpec:
  """Exact ray, wavelength, and projection selection for the canonical v1 API."""

  request_digest_sha256: str
  result_digest_sha256: str
  selected_ray_index: int = 0
  wavelength_index: int = 0
  projections: tuple[str, ...] = ('XY', 'XZ', 'YZ')

  def __post_init__(self) -> None:
    for name, value in (
      ('request_digest_sha256', self.request_digest_sha256),
      ('result_digest_sha256', self.result_digest_sha256),
    ):
      if len(value) != 64 or any(character not in '0123456789abcdef' for character in value):
        raise ValueError(f'{name} must be a lowercase SHA-256 digest')
    for name, value in (
      ('selected_ray_index', self.selected_ray_index),
      ('wavelength_index', self.wavelength_index),
    ):
      if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer')
    projections = tuple(self.projections)
    supported = {'XY', 'XZ', 'YZ'}
    if not projections or len(projections) != len(set(projections)) or not set(projections) <= supported:
      raise ValueError('projections must be a non-empty unique subset of XY, XZ, and YZ')
    object.__setattr__(self, 'projections', projections)
  ####

  @classmethod
  def for_data(
    cls,
    data: CanonicalSpectralRayTransferData,
    **overrides: Any,
  ) -> 'CanonicalSpectralRayTransferGallerySpec':
    if not isinstance(data, CanonicalSpectralRayTransferData):
      raise TypeError('data must be CanonicalSpectralRayTransferData')
    return cls(
      request_digest_sha256=data.result.metadata.request_digest_sha256,
      result_digest_sha256=canonical_digest(data.result),
      **overrides,
    )
  ####

  def validate_for_data(self, data: CanonicalSpectralRayTransferData) -> None:
    if not isinstance(data, CanonicalSpectralRayTransferData):
      raise TypeError('data must be CanonicalSpectralRayTransferData')
    if self.request_digest_sha256 != data.result.metadata.request_digest_sha256:
      raise ValueError('ray-transfer gallery spec is bound to a different request')
    if self.result_digest_sha256 != canonical_digest(data.result):
      raise ValueError('ray-transfer gallery spec is bound to a different result')
    if self.selected_ray_index >= len(data.lines):
      raise ValueError('selected_ray_index is outside the exact ray bundle')
    if self.wavelength_index >= len(data.wavelengths_m):
      raise ValueError('wavelength_index is outside the exact spectral axis')
  ####

  def model_dump(self, mode: str = 'python') -> dict[str, Any]:
    del mode
    return {
      'schema': 'plume.visualization.canonical-spectral-ray-transfer-view-spec@1',
      'request_digest_sha256': self.request_digest_sha256,
      'result_digest_sha256': self.result_digest_sha256,
      'selected_ray_index': self.selected_ray_index,
      'wavelength_index': self.wavelength_index,
      'projections': list(self.projections),
      'ray_geometry': 'exact-requested-t-min-to-t-max-segment',
      'uncertainty_policy': 'show-only-provider-supplied-absolute-standard-uncertainty',
      'invalid_sample_policy': 'mask-and-preserve',
    }
  ####

  def digest_sha256(self) -> str:
    canonical = json.dumps(
      self.model_dump(mode='json'),
      allow_nan=False,
      ensure_ascii=True,
      separators=(',', ':'),
      sort_keys=True,
    )
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()
  ####
####


@dataclass(frozen=True, slots=True)
class SpatialLocalFieldGallerySpec:
  """Field and projection selection bound to one exact point-query result."""

  local_field_digest_sha256: str
  display_field_ids: tuple[str, ...]
  projections: tuple[str, ...] = ('XY', 'XZ', 'YZ')
  color_map: str = 'viridis'

  def __post_init__(self) -> None:
    if len(self.local_field_digest_sha256) != 64 or any(
      value not in '0123456789abcdef' for value in self.local_field_digest_sha256
    ):
      raise ValueError('local_field_digest_sha256 must be a lowercase SHA-256 digest')
    fields = tuple(self.display_field_ids)
    if not fields or len(fields) != len(set(fields)) or any(not value.strip() for value in fields):
      raise ValueError('display_field_ids must be non-empty, unique, and non-blank')
    projections = tuple(self.projections)
    supported = {'XY', 'XZ', 'YZ'}
    if not projections or len(projections) != len(set(projections)) or not set(projections) <= supported:
      raise ValueError('projections must be a non-empty unique subset of XY, XZ, and YZ')
    if not isinstance(self.color_map, str) or not self.color_map:
      raise ValueError('color_map must be a non-empty string')
    object.__setattr__(self, 'display_field_ids', fields)
    object.__setattr__(self, 'projections', projections)
  ####

  @classmethod
  def for_data(
    cls,
    data: CanonicalSpatialLocalFieldData,
    **overrides: Any,
  ) -> 'SpatialLocalFieldGallerySpec':
    if not isinstance(data, CanonicalSpatialLocalFieldData):
      raise TypeError('data must be CanonicalSpatialLocalFieldData')
    overrides.setdefault('display_field_ids', tuple(data.result.field_ids))
    return cls(
      local_field_digest_sha256=_local_field_data_digest(data),
      **overrides,
    )
  ####

  def validate_for_data(self, data: CanonicalSpatialLocalFieldData) -> None:
    if not isinstance(data, CanonicalSpatialLocalFieldData):
      raise TypeError('data must be CanonicalSpatialLocalFieldData')
    if self.local_field_digest_sha256 != _local_field_data_digest(data):
      raise ValueError('local-field gallery spec is bound to a different result')
    if not set(self.display_field_ids) <= set(data.result.field_ids):
      raise ValueError('display_field_ids must be declared by the exact source result')
  ####

  def model_dump(self, mode: str = 'python') -> dict[str, Any]:
    del mode
    return {
      'schema': 'plume.visualization.spatial-local-field-view-spec@1',
      'local_field_digest_sha256': self.local_field_digest_sha256,
      'display_field_ids': list(self.display_field_ids),
      'projections': list(self.projections),
      'color_map': self.color_map,
      'sample_order_view': 'query-order-no-time-interpolation',
    }
  ####

  def digest_sha256(self) -> str:
    canonical = json.dumps(self.model_dump(mode='json'), allow_nan=False, ensure_ascii=True, separators=(',', ':'), sort_keys=True)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()
  ####
####


@dataclass(frozen=True, slots=True)
class EngineeringFluxSectionGallerySpec:
  """Station-series views bound to one exact engineering-flux result."""

  result_digest_sha256: str

  def __post_init__(self) -> None:
    if len(self.result_digest_sha256) != 64 or any(
      value not in '0123456789abcdef' for value in self.result_digest_sha256
    ):
      raise ValueError('result_digest_sha256 must be a lowercase SHA-256 digest')
  ####

  @classmethod
  def for_result(cls, result: EngineeringFluxSectionResult) -> 'EngineeringFluxSectionGallerySpec':
    if not isinstance(result, EngineeringFluxSectionResult):
      raise TypeError('result must be EngineeringFluxSectionResult')
    return cls(result_digest_sha256=canonical_digest(result))
  ####

  def validate_for_result(self, result: EngineeringFluxSectionResult) -> None:
    if not isinstance(result, EngineeringFluxSectionResult):
      raise TypeError('result must be EngineeringFluxSectionResult')
    if self.result_digest_sha256 != canonical_digest(result):
      raise ValueError('engineering-flux gallery spec is bound to a different result')
  ####

  def model_dump(self, mode: str = 'python') -> dict[str, Any]:
    del mode
    return {
      'schema': 'plume.visualization.engineering-flux-section-view-spec@1',
      'result_digest_sha256': self.result_digest_sha256,
      'view_kind': 'engineering-flux.station-series',
      'station_policy': 'exact-requested-stations-scatter-no-interpolation',
      'quantities': [
        'mass-flow',
        'species-mass-flow',
        'momentum-flux-magnitude',
        'stagnation-enthalpy-flux',
        'static-and-ambient-pressure',
        'pressure-match-relative-residual',
        'cross-section-area',
        'characteristic-radius',
        'sample-status',
      ],
    }
  ####

  def digest_sha256(self) -> str:
    canonical = json.dumps(
      self.model_dump(mode='json'),
      allow_nan=False,
      ensure_ascii=True,
      separators=(',', ':'),
      sort_keys=True,
    )
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()
  ####
####


@dataclass(frozen=True, slots=True)
class SpectralRadianceImageGallerySpec:
  """Display selection bound to one exact pre-detector spectral image."""

  image_result_digest_sha256: str
  wavelength_index: int = 0
  selected_pixel_row: int = 0
  selected_pixel_column: int = 0
  color_map: str = 'magma'

  def __post_init__(self) -> None:
    if len(self.image_result_digest_sha256) != 64 or any(
      value not in '0123456789abcdef' for value in self.image_result_digest_sha256
    ):
      raise ValueError('image_result_digest_sha256 must be a lowercase SHA-256 digest')
    for name, value in (
      ('wavelength_index', self.wavelength_index),
      ('selected_pixel_row', self.selected_pixel_row),
      ('selected_pixel_column', self.selected_pixel_column),
    ):
      if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer')
    if not isinstance(self.color_map, str) or not self.color_map.strip():
      raise ValueError('color_map must be a non-empty string')
  ####

  @classmethod
  def for_result(
    cls,
    result: SpectralRadianceImageResult,
    **overrides: Any,
  ) -> 'SpectralRadianceImageGallerySpec':
    if not isinstance(result, SpectralRadianceImageResult):
      raise TypeError('result must be SpectralRadianceImageResult')
    defaults: dict[str, Any] = {
      'wavelength_index': 0,
      'selected_pixel_row': 0,
      'selected_pixel_column': 0,
    }
    for row_index, row in enumerate(result.validity_mask):
      for column_index, valid in enumerate(row):
        if valid:
          defaults['selected_pixel_row'] = row_index
          defaults['selected_pixel_column'] = column_index
          break
      else:
        continue
      break
    defaults.update(overrides)
    return cls(
      image_result_digest_sha256=canonical_digest(result),
      **defaults,
    )
  ####

  def validate_for_result(self, result: SpectralRadianceImageResult) -> None:
    if not isinstance(result, SpectralRadianceImageResult):
      raise TypeError('result must be SpectralRadianceImageResult')
    if self.image_result_digest_sha256 != canonical_digest(result):
      raise ValueError('spectral-radiance image view spec is bound to a different result')
    if self.wavelength_index >= len(result.wavelengths_m):
      raise ValueError('wavelength_index is outside the exact source image')
    if self.selected_pixel_row >= result.height_px:
      raise ValueError('selected_pixel_row is outside the exact source image')
    if self.selected_pixel_column >= result.width_px:
      raise ValueError('selected_pixel_column is outside the exact source image')
  ####

  def model_dump(self, mode: str = 'python') -> dict[str, Any]:
    del mode
    return {
      'schema': 'plume.visualization.spectral-radiance-image-view-spec@1',
      'image_result_digest_sha256': self.image_result_digest_sha256,
      'wavelength_index': self.wavelength_index,
      'selected_pixel_row': self.selected_pixel_row,
      'selected_pixel_column': self.selected_pixel_column,
      'color_map': self.color_map,
      'pixel_coordinate_convention': 'zero-based row-column; no angular coordinates inferred',
      'invalid_pixel_policy': 'mask samples and preserve declared status',
      'map_sampling': 'exact source pixels; nearest display rasterization; no interpolation',
    }
  ####

  def digest_sha256(self) -> str:
    canonical = json.dumps(
      self.model_dump(mode='json'),
      allow_nan=False,
      ensure_ascii=True,
      separators=(',', ':'),
      sort_keys=True,
    )
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()
  ####
####


@dataclass(frozen=True, slots=True)
class VisualizationGalleryManifest:
  """Source-bound manifest for a static evaluation gallery."""

  schema: str
  product: str
  view_spec: (
    VisualizationSpec
    | CapabilityGalleryViewSpec
    | CanonicalSpectralRayTransferGallerySpec
    | SpatialLocalFieldGallerySpec
    | EngineeringFluxSectionGallerySpec
    | SpectralRadianceImageGallerySpec
  )
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


def _capability_payload_digest(data: CanonicalSpatialSupportData | CanonicalProjectedAreaData) -> str:
  canonical = json.dumps(
    data.payload_model_dump(),
    allow_nan=False,
    ensure_ascii=True,
    separators=(',', ':'),
    sort_keys=True,
  )
  return hashlib.sha256(canonical.encode('utf-8')).hexdigest()
####


def _local_field_data_digest(data: CanonicalSpatialLocalFieldData) -> str:
  canonical = json.dumps(
    data.model_dump(),
    allow_nan=False,
    ensure_ascii=True,
    separators=(',', ':'),
    sort_keys=True,
  )
  return hashlib.sha256(canonical.encode('utf-8')).hexdigest()
####


def _spectral_radiance_image_source(result: SpectralRadianceImageResult) -> dict[str, Any]:
  metadata = result.metadata
  return {
    'capability_id': metadata.capability.wire_id,
    'schema_version': str(metadata.capability.major),
    'result_id': metadata.result_id,
    'content_sha256': canonical_digest(result),
    'request_digest_sha256': metadata.request_digest_sha256,
    'output_frame_id': metadata.output_frame_id,
    'snapshot': metadata.snapshot.model_dump(mode='json'),
    'claims': metadata.claims.model_dump(mode='json'),
    'applicability': metadata.applicability.model_dump(mode='json'),
    'provenance': metadata.provenance.model_dump(mode='json'),
    'warnings': list(metadata.warnings),
    'ray_transfer_request_digest_sha256': result.ray_transfer_request_digest_sha256,
    'ray_transfer_result_id': result.ray_transfer_result_id,
    'ray_transfer_result_digest_sha256': result.ray_transfer_result_digest_sha256,
    'pixel_geometry_sha256': result.pixel_geometry_sha256,
  }
####


def _canonical_ray_transfer_source(data: CanonicalSpectralRayTransferData) -> dict[str, Any]:
  metadata = data.result.metadata
  return {
    'capability_id': metadata.capability.wire_id,
    'schema_version': str(metadata.capability.major),
    'result_id': metadata.result_id,
    'request_digest_sha256': metadata.request_digest_sha256,
    'content_sha256': canonical_digest(data.result),
    'snapshot_id': metadata.snapshot.snapshot_id,
    'requested_time_s': metadata.snapshot.time_s,
    'output_frame_id': metadata.output_frame_id,
    'frame': {'frame_id': metadata.output_frame_id},
    'claims': metadata.claims.model_dump(mode='json'),
    'applicability': metadata.applicability.model_dump(mode='json'),
    'provenance': metadata.provenance.model_dump(mode='json'),
    'warnings': list(metadata.warnings),
  }
####


def _capability_view_spec(
  data: CanonicalSpatialSupportData | CanonicalProjectedAreaData,
  spec: CapabilityGalleryViewSpec | None,
) -> CapabilityGalleryViewSpec:
  source_context = data.source_context
  source_context_digest = None
  if source_context is not None:
    context_payload = json.dumps(
      source_context.model_dump(),
      allow_nan=False,
      ensure_ascii=True,
      separators=(',', ':'),
      sort_keys=True,
    )
    source_context_digest = hashlib.sha256(context_payload.encode('utf-8')).hexdigest()
  ####
  if isinstance(data, CanonicalSpatialSupportData):
    frame_label = 'plume-frame' if source_context is None else source_context.frame_id
    expected = CapabilityGalleryViewSpec(
      capability_id=SPATIAL_SUPPORT_CAPABILITY.wire_id,
      major_version=data.support.major_version,
      content_sha256=_capability_payload_digest(data),
      view_kind='spatial-support.orthographic-aabb',
      axes=(f'{frame_label} x [m]', f'{frame_label} y [m]', f'{frame_label} z [m]'),
      projections=('XY', 'XZ', 'YZ'),
      source_context_sha256=source_context_digest,
    )
  else:
    expected = CapabilityGalleryViewSpec(
      capability_id=SPATIAL_PROJECTED_AREA_CAPABILITY.wire_id,
      major_version=data.projected_area.major_version,
      content_sha256=_capability_payload_digest(data),
      view_kind='projected-area.numeric-summary',
      axes=('reference projected area [m²]', 'closed-zone count [1]'),
      source_context_sha256=source_context_digest,
    )
  ####
  if spec is None:
    return expected
  ####
  if not isinstance(spec, CapabilityGalleryViewSpec):
    raise TypeError('supporting capability galleries require CapabilityGalleryViewSpec')
  ####
  if spec != expected:
    raise ValueError('capability gallery view spec does not match the exact capability payload')
  ####
  return spec
####


def _capability_manifest(
  data: CanonicalSpatialSupportData | CanonicalProjectedAreaData,
  spec: CapabilityGalleryViewSpec,
  output: Path,
  product: str,
  artifacts: Sequence[GalleryArtifact],
  guardrails: Sequence[str],
) -> VisualizationGalleryManifest:
  output.mkdir(parents=True, exist_ok=True)
  source_context = data.source_context
  source: dict[str, Any] = {
    'capability_id': spec.capability_id,
    'major_version': spec.major_version,
    'content_sha256': spec.content_sha256,
    'identity_scope': 'canonical supporting-capability payload',
    'source_context_sha256': spec.source_context_sha256,
    'provider_provenance_available': source_context is not None,
  }
  if source_context is None:
    source.update({
      'provider_id': None,
      'snapshot_id': None,
      'lineage_note': 'No canonical result context was supplied for this capability payload.',
    })
  else:
    metadata = source_context.metadata
    source.update({
      'provider_id': metadata.provenance.provider_id,
      'provider_version': metadata.provenance.provider_version,
      'snapshot_id': metadata.snapshot.snapshot_id,
      'result_id': metadata.result_id,
      'frame_id': metadata.output_frame_id,
      'time_s': metadata.snapshot.time_s,
      'provenance_id': metadata.provenance.model_lineage_id,
      'result_metadata': metadata.model_dump(mode='json'),
    })
  ####
  spec_path = output / 'visualization_spec.json'
  spec_path.write_text(json.dumps({
    'schema': 'plume.visualization.capability-spec-export@1',
    'view_spec': spec.model_dump(mode='json'),
    'view_spec_digest_sha256': spec.digest_sha256(),
    'source': source,
  }, indent=2, sort_keys=True) + '\n', encoding='utf-8')
  all_artifacts = (
    GalleryArtifact('metadata.visualization-spec', spec_path.name, 'application/json'),
    *artifacts,
  )
  product_metadata = data.model_dump()
  product_metadata['provider_provenance_available'] = source_context is not None
  lineage_guardrail = (
    'provider_snapshot_and_provenance_are_not_available_without_source_context'
    if source_context is None
    else 'canonical_result_metadata_and_payload_digest_are_bound_in_view_spec'
  )
  manifest = VisualizationGalleryManifest(
    schema=GALLERY_MANIFEST_SCHEMA,
    product=product,
    view_spec=spec,
    source=source,
    product_metadata=product_metadata,
    artifacts=all_artifacts,
    guardrails=(*guardrails, lineage_guardrail),
    manifest_path=output / 'gallery_manifest.json',
  )
  _write_gallery_manifest(manifest)
  return manifest
####


def _save_capability_figure(
  figure: Any,
  path: Path,
  *,
  title: str,
  spec: CapabilityGalleryViewSpec,
) -> None:
  figure.suptitle(title, fontsize=12)
  figure.tight_layout(rect=(0.0, 0.09, 1.0, 0.92))
  figure.savefig(path, dpi=140, metadata={
    'CapabilityId': spec.capability_id,
    'CapabilityContentSHA256': spec.content_sha256,
    'VisualizationSpecSHA256': spec.digest_sha256(),
  })
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


def _numeric_signature_uncertainty(
  grid: SpectralRadiantIntensityGrid,
) -> tuple[tuple[float | None, ...], ...] | None:
  """Read the one explicitly supported numeric Signature uncertainty schema."""

  raw = grid.uncertainty.get('absolute_standard_uncertainty_W_sr_m')
  if raw is None:
    raw = grid.uncertainty.get('absolute_standard_uncertainty_w_sr_m')
  ####
  if raw is None:
    return None
  ####
  try:
    rows = tuple(tuple(row) for row in raw)
  except (TypeError, ValueError) as error:
    raise ValueError(
      'numeric Signature uncertainty must be a direction-by-wavelength matrix'
    ) from error
  ####
  if len(rows) != len(grid.directions) or any(
    len(row) != len(grid.wavelengths_m) for row in rows
  ):
    raise ValueError(
      'numeric Signature uncertainty matrix must match the direction and '
      'wavelength axes'
    )
  ####
  normalized: list[tuple[float | None, ...]] = []
  for direction_index, (row, validity) in enumerate(
    zip(rows, grid.validity_mask, strict=True)
  ):
    values: list[float | None] = []
    for wavelength_index, (value, valid) in enumerate(
      zip(row, validity, strict=True)
    ):
      if value is None:
        if valid:
          raise ValueError(
            'numeric Signature uncertainty cannot be missing at a valid '
            f'sample ({direction_index}, {wavelength_index})'
          )
        ####
        values.append(None)
        continue
      ####
      try:
        numeric = float(value)
      except (TypeError, ValueError) as error:
        raise ValueError(
          'numeric Signature uncertainty must contain finite nonnegative '
          'values'
        ) from error
      ####
      if not isfinite(numeric) or numeric < 0.0:
        raise ValueError(
          'numeric Signature uncertainty must contain finite nonnegative '
          'values'
        )
      ####
      if not valid:
        raise ValueError(
          'numeric Signature uncertainty must use null values at invalid '
          f'samples ({direction_index}, {wavelength_index})'
        )
      ####
      values.append(numeric)
    ####
    normalized.append(tuple(values))
  ####
  return tuple(normalized)
####


def _uncertainty_matrix_for_display(
  rows: Sequence[Sequence[float | None]],
  spec: VisualizationSpec,
) -> list[list[float]]:
  matrix: list[list[float]] = []
  for row in rows:
    prepared: list[float] = []
    for value in row:
      if value is None:
        if spec.invalid_sample_policy is InvalidSamplePolicy.REJECT:
          raise ValueError('numeric Signature uncertainty contains an invalid sample')
        ####
        prepared.append(float('nan'))
      else:
        prepared.append(float(value))
      ####
    ####
    matrix.append(prepared)
  ####
  return matrix
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
  ####
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
  ####
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

  uncertainty = _numeric_signature_uncertainty(grid)
  uncertainty_path: Path | None = None
  if uncertainty is not None:
    uncertainty_path = output / 'signature_uncertainty_heatmap.png'
    figure, axis = plt.subplots(figsize=(9.0, 5.5))
    uncertainty_matrix = _uncertainty_matrix_for_display(uncertainty, resolved)
    cmap = plt.get_cmap(resolved.color_map).copy()
    cmap.set_bad(alpha=0.0)
    uncertainty_image = axis.imshow(
      uncertainty_matrix,
      aspect='auto',
      interpolation='nearest',
      origin='lower',
      cmap=cmap,
    )
    axis.set_xlabel(wavelength_label)
    axis.set_ylabel('Direction index [1] — exact direction rows')
    axis.set_xticks(range(len(wavelengths)))
    axis.set_xticklabels([f'{value:g}' for value in wavelengths], rotation=35, ha='right')
    axis.set_yticks(range(len(grid.directions)))
    figure.colorbar(
      uncertainty_image,
      ax=axis,
      label='absolute standard uncertainty [W sr⁻¹ m⁻¹]',
    )
    _save(
      figure,
      uncertainty_path,
      title='Declared Signature uncertainty heatmap',
      result=result,
      spec=resolved,
    )
    plt.close(figure)
  ####

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
  ####
  _save(figure, sphere_path, title='Direction-unit-sphere view at selected wavelength', result=result, spec=resolved)
  plt.close(figure)

  table_path = _signature_direction_table(grid, output)
  artifacts = (
    GalleryArtifact('signature.spectra', spectrum_path.name, 'image/png'),
    GalleryArtifact('signature.heatmap', heatmap_path.name, 'image/png'),
    *(() if uncertainty_path is None else (
      GalleryArtifact('signature.uncertainty-heatmap', uncertainty_path.name, 'image/png'),
    )),
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
      'numeric_uncertainty_declared': uncertainty is not None,
    },
    artifacts,
    (
      'direction_index_and_exact_3d_direction_are_used; no scalar_angle_is_invented',
      'invalid_signature_samples_remain_masked_or_gapped',
      'numeric_uncertainty_heatmaps_require_a_declared_aligned_uncertainty_schema',
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
  ####
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


def render_canonical_spectral_ray_transfer_gallery(
  data: CanonicalSpectralRayTransferData,
  output_dir: str | Path,
  *,
  spec: CanonicalSpectralRayTransferGallerySpec | None = None,
) -> VisualizationGalleryManifest:
  """Render the exact canonical v1 ray request/result, including supplied uncertainty."""

  if not isinstance(data, CanonicalSpectralRayTransferData):
    raise TypeError('data must be CanonicalSpectralRayTransferData')
  resolved = spec or CanonicalSpectralRayTransferGallerySpec.for_data(data)
  if not isinstance(resolved, CanonicalSpectralRayTransferGallerySpec):
    raise TypeError('canonical ray-transfer galleries require CanonicalSpectralRayTransferGallerySpec')
  resolved.validate_for_data(data)

  output = Path(output_dir)
  output.mkdir(parents=True, exist_ok=True)
  plt, _, _ = _matplotlib()
  import numpy as np

  request = data.request
  result = data.result
  source = _canonical_ray_transfer_source(data)
  source_digest = source['content_sha256']
  spec_digest = resolved.digest_sha256()
  uncertainty_count = sum(
    1
    for line in data.lines
    for value in (line.absolute_standard_uncertainty_W_m2_sr_m or ())
    if value is not None
  )

  def save_figure(figure: Any, path: Path, title: str) -> None:
    figure.tight_layout()
    figure.savefig(path, dpi=160, metadata={
      'Title': title,
      'SourceContentSHA256': source_digest,
      'VisualizationSpecSHA256': spec_digest,
    })
    plt.close(figure)
  ####

  projection_axes = {'XY': (0, 1), 'XZ': (0, 2), 'YZ': (1, 2)}
  coordinate_names = ('x', 'y', 'z')
  geometry_path = output / 'canonical_ray_transfer_geometry.png'
  figure, axes = plt.subplots(1, len(resolved.projections), figsize=(5.0 * len(resolved.projections), 5.0), squeeze=False)
  for axis, projection in zip(axes[0], resolved.projections, strict=True):
    horizontal, vertical = projection_axes[projection]
    for index, line in enumerate(data.lines):
      direction = request.ray_directions[index]
      origin = request.ray_origins_m[index]
      t_min = request.ray_t_min_m[index]
      t_max = request.ray_t_max_m[index]
      start = tuple(origin[dim] + t_min * direction[dim] for dim in range(3))
      end = tuple(origin[dim] + t_max * direction[dim] for dim in range(3))
      selected = index == resolved.selected_ray_index
      color = '#d62728' if selected else '#4c78a8'
      axis.plot(
        (start[horizontal], end[horizontal]),
        (start[vertical], end[vertical]),
        color=color,
        linewidth=2.2 if selected else 1.1,
        label=f'ray {index}' if projection == resolved.projections[0] else None,
      )
      axis.scatter(
        (origin[horizontal],),
        (origin[vertical],),
        color=color,
        marker='x',
        s=30,
      )
    axis.set_xlabel(f'{coordinate_names[horizontal]} [m]')
    axis.set_ylabel(f'{coordinate_names[vertical]} [m]')
    axis.set_title(f'{projection} projection — exact requested ray interval')
    axis.set_aspect('equal', adjustable='datalim')
    axis.grid(True, alpha=0.22)
  axes[0][0].legend(loc='best', fontsize=8)
  save_figure(figure, geometry_path, 'Canonical ray-transfer exact interval projections')

  wavelengths_um = np.asarray(data.wavelengths_m, dtype=float) * 1.0e6
  spectra_path = output / 'canonical_ray_transfer_spectra.png'
  figure, axes = plt.subplots(2, 1, figsize=(9.0, 8.0), sharex=True)
  for index, line in enumerate(data.lines):
    selected = index == resolved.selected_ray_index
    color = '#d62728' if selected else '#4c78a8'
    values = np.asarray([
      value if line.validity_mask[wavelength_index] else np.nan
      for wavelength_index, value in enumerate(line.source_spectral_radiance_W_m2_sr_m)
    ], dtype=float)
    axes[0].plot(
      wavelengths_um,
      values,
      marker='o',
      color=color,
      linewidth=2.0 if selected else 1.0,
      label=f'ray {index}',
    )
    uncertainty = line.absolute_standard_uncertainty_W_m2_sr_m
    if uncertainty is not None:
      samples = [
        wavelength_index
        for wavelength_index, value in enumerate(uncertainty)
        if line.validity_mask[wavelength_index] and value is not None
      ]
      if samples:
        axes[0].errorbar(
          wavelengths_um[samples],
          values[samples],
          yerr=np.asarray([uncertainty[wavelength_index] for wavelength_index in samples]),
          fmt='none',
          ecolor=color,
          capsize=3,
          linewidth=1.0,
        )
    ####
    transmittance = np.asarray([
      value if line.validity_mask[wavelength_index] else np.nan
      for wavelength_index, value in enumerate(line.background_transmittance)
    ], dtype=float)
    axes[1].plot(
      wavelengths_um,
      transmittance,
      marker='o',
      color=color,
      linewidth=2.0 if selected else 1.0,
      label=f'ray {index}',
    )
  for axis in axes:
    axis.axvline(wavelengths_um[resolved.wavelength_index], color='#777777', linestyle=':', linewidth=1.0)
    axis.grid(True, alpha=0.22)
    axis.legend(loc='best', fontsize=8)
  axes[0].set_ylabel('Source radiance [W m⁻² sr⁻¹ m⁻¹]')
  axes[0].set_title(
    'Source radiance — supplied absolute standard uncertainty shown as error bars'
    if uncertainty_count
    else 'Source radiance — no sample uncertainty estimate available'
    if result.absolute_standard_uncertainty is not None
    else 'Source radiance — no uncertainty estimate supplied'
  )
  axes[1].set_ylabel('Background transmittance [1]')
  axes[1].set_xlabel('Wavelength [μm]')
  axes[1].set_title('Background transmittance — separate field')
  save_figure(figure, spectra_path, 'Canonical ray-transfer spectra and supplied uncertainty')

  fields_path = output / 'canonical_ray_transfer_fields.png'
  figure, axes = plt.subplots(1, 3, figsize=(15.0, 5.0), squeeze=False)
  source_matrix = np.asarray([
    [value if line.validity_mask[wavelength_index] else np.nan
     for wavelength_index, value in enumerate(line.source_spectral_radiance_W_m2_sr_m)]
    for line in data.lines
  ], dtype=float)
  transmittance_matrix = np.asarray([
    [value if line.validity_mask[wavelength_index] else np.nan
     for wavelength_index, value in enumerate(line.background_transmittance)]
    for line in data.lines
  ], dtype=float)
  image = axes[0][0].imshow(source_matrix, aspect='auto', interpolation='nearest', origin='lower')
  figure.colorbar(image, ax=axes[0][0], label='Source radiance [W m⁻² sr⁻¹ m⁻¹]')
  image = axes[0][1].imshow(transmittance_matrix, aspect='auto', interpolation='nearest', origin='lower', vmin=0.0, vmax=1.0)
  figure.colorbar(image, ax=axes[0][1], label='Background transmittance [1]')
  axes[0][0].set_title('Source radiance by ray and wavelength')
  axes[0][1].set_title('Background transmittance by ray and wavelength')
  if result.absolute_standard_uncertainty is None:
    axes[0][2].text(0.5, 0.5, 'No uncertainty matrix supplied', ha='center', va='center', transform=axes[0][2].transAxes)
    axes[0][2].set_title('Absolute standard uncertainty')
  else:
    uncertainty_matrix = np.asarray([
      [
        value if line.validity_mask[wavelength_index] and value is not None else np.nan
        for wavelength_index, value in enumerate(line.absolute_standard_uncertainty_W_m2_sr_m or ())
      ]
      for line in data.lines
    ], dtype=float)
    uncertainty_count = int(np.count_nonzero(np.isfinite(uncertainty_matrix)))
    if uncertainty_count:
      image = axes[0][2].imshow(uncertainty_matrix, aspect='auto', interpolation='nearest', origin='lower')
      figure.colorbar(image, ax=axes[0][2], label='Absolute standard uncertainty [W m⁻² sr⁻¹ m⁻¹]')
      axes[0][2].set_title('Provider-supplied uncertainty')
    else:
      axes[0][2].text(0.5, 0.5, 'No sample estimate available', ha='center', va='center', transform=axes[0][2].transAxes)
      axes[0][2].set_title('Absolute standard uncertainty')
  for axis in axes[0]:
    axis.set_xlabel('Wavelength index [1]')
    axis.set_ylabel('Ray index [1]')
  save_figure(figure, fields_path, 'Canonical ray-transfer radiance, transmittance, and uncertainty fields')

  table_path = output / 'canonical_ray_transfer_samples.csv'
  with table_path.open('w', encoding='utf-8', newline='') as stream:
    writer = csv.writer(stream)
    writer.writerow((
      'ray_index', 'wavelength_index', 'wavelength_m', 'valid', 'ray_status',
      'source_spectral_radiance_W_m2_sr_m', 'absolute_standard_uncertainty_W_m2_sr_m',
      'uncertainty_status', 'background_transmittance', 'hit', 'optical_depth',
    ))
    for ray_index, line in enumerate(data.lines):
      for wavelength_index, wavelength_m in enumerate(data.wavelengths_m):
        valid = line.validity_mask[wavelength_index]
        uncertainty = line.absolute_standard_uncertainty_W_m2_sr_m
        sample_uncertainty = None if uncertainty is None else uncertainty[wavelength_index]
        uncertainty_status = (
          'invalid_sample' if not valid else
          'not_supplied' if uncertainty is None else
          'not_estimated' if sample_uncertainty is None else 'supplied'
        )
        optical_depth = None if line.optical_depth is None else line.optical_depth[wavelength_index]
        writer.writerow((
          ray_index,
          wavelength_index,
          f'{wavelength_m:.17g}',
          str(valid).lower(),
          line.ray_status.code.value,
          '' if not valid else f'{line.source_spectral_radiance_W_m2_sr_m[wavelength_index]:.17g}',
          '' if not valid or sample_uncertainty is None else f'{sample_uncertainty:.17g}',
          uncertainty_status,
          '' if not valid else f'{line.background_transmittance[wavelength_index]:.17g}',
          str(line.hit).lower(),
          '' if not valid or optical_depth is None else f'{optical_depth:.17g}',
        ))

  source_path = output / 'canonical_ray_transfer_source.json'
  source_path.write_text(json.dumps({
    'schema': 'plume.visualization.canonical-spectral-ray-transfer-data@1',
    'source': source,
    'request': request.model_dump(mode='json'),
    'result': result.model_dump(mode='json'),
    'canonical_visualization_data': data.model_dump(),
    'view_spec': resolved.model_dump(mode='json'),
    'view_spec_digest_sha256': spec_digest,
  }, allow_nan=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')

  artifacts = (
    GalleryArtifact('canonical-ray-transfer.geometry-projections', geometry_path.name, 'image/png'),
    GalleryArtifact('canonical-ray-transfer.spectra', spectra_path.name, 'image/png'),
    GalleryArtifact('canonical-ray-transfer.ray-wavelength-fields', fields_path.name, 'image/png'),
    GalleryArtifact('canonical-ray-transfer.samples', table_path.name, 'text/csv'),
    GalleryArtifact('canonical-ray-transfer.source-data', source_path.name, 'application/json'),
  )
  metadata = result.metadata
  manifest = VisualizationGalleryManifest(
    schema=GALLERY_MANIFEST_SCHEMA,
    product='spectral-ray-transfer',
    view_spec=resolved,
    source=source,
    product_metadata={
      'api_contract': 'canonical-v1',
      'frame_id': data.frame_id,
      'ray_count': len(data.lines),
      'wavelength_count': len(data.wavelengths_m),
      'selected_ray_index': resolved.selected_ray_index,
      'selected_wavelength_index': resolved.wavelength_index,
      'selected_wavelength_m': data.wavelengths_m[resolved.wavelength_index],
      'valid_sample_count': sum(sum(line.validity_mask) for line in data.lines),
      'uncertainty_matrix_supplied': result.absolute_standard_uncertainty is not None,
      'uncertainty_sample_count': uncertainty_count,
      'result_metadata': metadata.model_dump(mode='json'),
    },
    artifacts=artifacts,
    guardrails=(
      'ray_geometry_uses_exact_requested_t_min_and_t_max',
      'invalid_radiance_transmittance_and_uncertainty_samples_are_masked',
      'only_provider_supplied_absolute_standard_uncertainty_is_rendered',
      'missing_uncertainty_is_reported_as_unavailable_and_is_never_inferred',
      'source_radiance_and_background_transmittance_remain_separate_fields',
      'focal_plane_values_are_not_derived_without_an_explicit_detector_operator',
    ),
    manifest_path=output / 'gallery_manifest.json',
  )
  _write_gallery_manifest(manifest)
  return manifest
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
    ####
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


def render_spatial_support_gallery(
  data: CanonicalSpatialSupportData,
  output_dir: str | Path,
  *,
  spec: CapabilityGalleryViewSpec | None = None,
) -> VisualizationGalleryManifest:
  """Render only the three declared orthographic projections of an AABB."""

  if not isinstance(data, CanonicalSpatialSupportData):
    raise TypeError('data must be CanonicalSpatialSupportData')
  ####
  resolved = _capability_view_spec(data, spec)
  output = Path(output_dir)
  output.mkdir(parents=True, exist_ok=True)
  plt, _, _ = _matplotlib()
  from matplotlib.patches import Rectangle

  support = data.support
  lower = support.plume_frame_aabb_min_m
  upper = support.plume_frame_aabb_max_m
  frame_label = 'plume-frame' if data.source_context is None else data.source_context.frame_id
  figure, axes = plt.subplots(1, 3, figsize=(12.0, 4.4))
  projections = (
    ('XY', 0, 1),
    ('XZ', 0, 2),
    ('YZ', 1, 2),
  )
  for axis, (plane, first, second) in zip(axes, projections):
    first_min, first_max = lower[first], upper[first]
    second_min, second_max = lower[second], upper[second]
    first_width = first_max - first_min
    second_width = second_max - second_min
    first_pad = max((first_max - first_min) * 0.04, support.characteristic_extent_m * 0.015, 1.0e-9)
    second_pad = max((second_max - second_min) * 0.04, support.characteristic_extent_m * 0.015, 1.0e-9)
    axis.set_xlim(first_min - first_pad, first_max + first_pad)
    axis.set_ylim(second_min - second_pad, second_max + second_pad)
    if first_width == 0.0 and second_width == 0.0:
      axis.scatter((first_min,), (second_min,), color='#4c78a8', s=42)
      axis.set_xticks(())
      axis.set_yticks(())
      axis.set_aspect('auto')
      axis.set_title(f'{plane} projection of declared AABB\npoint at ({first_min:.6g}, {second_min:.6g}) m')
    elif first_width == 0.0:
      axis.plot((first_min, first_min), (second_min, second_max), color='#4c78a8', linewidth=3.0)
      axis.set_xticks(())
      axis.set_aspect('auto')
      axis.set_title(f'{plane} projection of declared AABB\n{resolved.axes[first]} is zero-width')
    elif second_width == 0.0:
      axis.plot((first_min, first_max), (second_min, second_min), color='#4c78a8', linewidth=3.0)
      axis.set_yticks(())
      axis.set_aspect('auto')
      axis.set_title(f'{plane} projection of declared AABB\n{resolved.axes[second]} is zero-width')
    else:
      axis.add_patch(Rectangle(
        (first_min, second_min),
        first_width,
        second_width,
        fill=False,
        linewidth=2.0,
        edgecolor='#4c78a8',
      ))
      axis.set_aspect('equal', adjustable='box')
      axis.set_title(f'{plane} projection of declared AABB')
    ####
    axis.set_xlabel(resolved.axes[first])
    axis.set_ylabel(resolved.axes[second])
    axis.grid(True, alpha=0.22)
  ####
  figure.text(
    0.5,
    0.012,
    f'Zero-width bounds are lines or points, not added thickness. Conservative support: '
    f'{support.is_conservative} | {support.support_definition}',
    ha='center',
    fontsize=8,
    wrap=True,
  )
  image_path = output / 'spatial_support_orthographic_bounds.png'
  _save_capability_figure(
    figure,
    image_path,
    title=f'Declared {frame_label} axis-aligned support bounds',
    spec=resolved,
  )
  plt.close(figure)

  table_path = output / 'spatial_support_bounds.csv'
  with table_path.open('w', encoding='utf-8', newline='') as stream:
    writer = csv.writer(stream)
    writer.writerow(('axis', 'minimum_m', 'maximum_m'))
    for axis_name, minimum, maximum in zip(('x', 'y', 'z'), lower, upper):
      writer.writerow((f'{frame_label} {axis_name}', f'{minimum:.17g}', f'{maximum:.17g}'))
  ####
  return _capability_manifest(
    data,
    resolved,
    output,
    'spatial-support',
    (
      GalleryArtifact('spatial-support.orthographic-aabb', image_path.name, 'image/png'),
      GalleryArtifact('spatial-support.bounds', table_path.name, 'text/csv'),
    ),
    (
      'orthographic_projections_show_only_the_declared_axis_aligned_bounds',
      'zero_width_bounds_remain_degenerate_lines_or_points',
      'the_bounds_are_not_a_plume_surface_or_a_reconstructed_flow_field',
    ),
  )
####


def render_projected_area_gallery(
  data: CanonicalProjectedAreaData,
  output_dir: str | Path,
  *,
  spec: CapabilityGalleryViewSpec | None = None,
) -> VisualizationGalleryManifest:
  """Render declared projected-area scalars without inventing geometry."""

  if not isinstance(data, CanonicalProjectedAreaData):
    raise TypeError('data must be CanonicalProjectedAreaData')
  ####
  resolved = _capability_view_spec(data, spec)
  output = Path(output_dir)
  output.mkdir(parents=True, exist_ok=True)
  plt, _, _ = _matplotlib()
  projected = data.projected_area

  figure, axes = plt.subplots(1, 2, figsize=(9.0, 4.0))
  axes[0].barh(('reference area',), (projected.reference_area_m2,), color='#4c78a8')
  axes[0].set_xlim(0.0, projected.reference_area_m2 * 1.15)
  axes[0].set_xlabel('Reference projected area [m²]')
  axes[0].set_title(f'{projected.reference_area_m2:.6g} m²')
  axes[0].grid(True, axis='x', alpha=0.22)
  axes[1].axis('off')
  axes[1].text(
    0.5,
    0.55,
    f'{projected.closed_zone_count}',
    ha='center',
    va='center',
    fontsize=30,
    color='#4c78a8',
  )
  axes[1].text(0.5, 0.30, 'closed-zone count [1]', ha='center', va='center', fontsize=11)
  axes[1].set_title('Declared zone count')
  ####
  image_path = output / 'projected_area_summary.png'
  _save_capability_figure(
    figure,
    image_path,
    title='Projected-area capability values',
    spec=resolved,
  )
  plt.close(figure)

  table_path = output / 'projected_area_values.csv'
  with table_path.open('w', encoding='utf-8', newline='') as stream:
    writer = csv.writer(stream)
    writer.writerow(('quantity', 'value', 'unit'))
    writer.writerow(('reference_projected_area', f'{projected.reference_area_m2:.17g}', 'm^2'))
    writer.writerow(('closed_zone_count', str(projected.closed_zone_count), '1'))
  ####
  return _capability_manifest(
    data,
    resolved,
    output,
    'projected-area',
    (
      GalleryArtifact('projected-area.numeric-summary', image_path.name, 'image/png'),
      GalleryArtifact('projected-area.values', table_path.name, 'text/csv'),
    ),
    (
      'reference_area_is_a_declared_scalar_and_not_a_geometry_or_viewing_projection',
      'no_plume_shape_orientation_radiance_or_detector_image_is_inferred',
    ),
  )
####


def render_spatial_local_field_gallery(
  data: CanonicalSpatialLocalFieldData | SpatialLocalFieldResult,
  output_dir: str | Path,
  *,
  spec: SpatialLocalFieldGallerySpec | None = None,
) -> VisualizationGalleryManifest:
  """Render exact point samples in orthographic views and query-order plots."""

  if isinstance(data, SpatialLocalFieldResult):
    data = extract_canonical_visualization_data(data)  # type: ignore[assignment]
  if not isinstance(data, CanonicalSpatialLocalFieldData):
    raise TypeError('data must be a SpatialLocalFieldResult or its canonical visualization data')
  resolved = spec or SpatialLocalFieldGallerySpec.for_data(data)
  if not isinstance(resolved, SpatialLocalFieldGallerySpec):
    raise TypeError('spec must be a SpatialLocalFieldGallerySpec')
  resolved.validate_for_data(data)

  output = Path(output_dir)
  output.mkdir(parents=True, exist_ok=True)
  plt, Normalize, _ = _matplotlib()
  result = data.result
  data_payload = data.model_dump()
  result_digest = data_payload['result_digest_sha256']
  source = {
    'capability_id': result.metadata.capability.wire_id,
    'result_id': result.metadata.result_id,
    'request_digest_sha256': result.metadata.request_digest_sha256,
    'result_digest_sha256': result_digest,
    'provider_id': result.metadata.provenance.provider_id,
    'provider_version': result.metadata.provenance.provider_version,
    'snapshot_id': result.metadata.snapshot.snapshot_id,
    'time_s': result.metadata.snapshot.time_s,
    'frame_id': result.metadata.output_frame_id,
    'provenance_id': result.metadata.provenance.model_lineage_id,
  }

  data_path = output / 'spatial_local_field.json'
  data_path.write_text(json.dumps(data_payload, indent=2, sort_keys=True, allow_nan=False) + '\n', encoding='utf-8')
  csv_path = output / 'spatial_local_field_points.csv'
  csv_columns = ['point_index', 'coordinate_frame_id', 'x_m', 'y_m', 'z_m']
  for channel in result.channels:
    prefix = channel.field_id
    csv_columns.extend((
      f'{prefix}.value[{channel.unit}]',
      f'{prefix}.status',
      f'{prefix}.status_message',
      f'{prefix}.sampling_method',
      f'{prefix}.absolute_standard_uncertainty[{channel.unit}]',
    ))
  with csv_path.open('w', encoding='utf-8', newline='') as stream:
    writer = csv.writer(stream)
    writer.writerow(csv_columns)
    for point_index, point in enumerate(result.points_m):
      row: list[Any] = [point_index, result.coordinate_frame_id, *point]
      for channel in result.channels:
        status = channel.sample_status[point_index]
        uncertainty = (
          None
          if channel.absolute_standard_uncertainty is None
          else channel.absolute_standard_uncertainty[point_index]
        )
        row.extend((
          channel.values[point_index],
          status.code.value,
          status.message,
          channel.sampling_method,
          uncertainty,
        ))
      writer.writerow(row)

  artifact_records = [
    GalleryArtifact('metadata.visualization-spec', 'visualization_spec.json', 'application/json'),
    GalleryArtifact('spatial-local-field.samples', data_path.name, 'application/json'),
    GalleryArtifact('spatial-local-field.samples-table', csv_path.name, 'text/csv'),
  ]
  field_by_id = {channel.field_id: channel for channel in result.channels}
  point_indices = tuple(range(len(result.points_m)))
  projection_axes = {
    'XY': (0, 1, 'x', 'y'),
    'XZ': (0, 2, 'x', 'z'),
    'YZ': (1, 2, 'y', 'z'),
  }
  for field_id in resolved.display_field_ids:
    channel = field_by_id[field_id]
    valid_indices = tuple(
      index
      for index, (value, status) in enumerate(zip(channel.values, channel.sample_status, strict=True))
      if value is not None and status.code.value == 'ok'
    )
    invalid_indices = tuple(index for index in point_indices if index not in set(valid_indices))
    valid_values = tuple(float(channel.values[index]) for index in valid_indices)
    if valid_values:
      lower, upper = min(valid_values), max(valid_values)
      if upper - lower <= 1.0e-12 * max(abs(lower), abs(upper), 1.0):
        padding = max(abs(lower) * 1.0e-6, 1.0e-9)
        normalization = Normalize(lower - padding, upper + padding)
      else:
        normalization = Normalize(lower, upper)
    else:
      normalization = None

    figure = plt.figure(figsize=(13.2, 8.0))
    grid = figure.add_gridspec(
      2,
      3,
      width_ratios=(1.0, 1.0, 0.075),
      left=0.08,
      right=0.89,
      bottom=0.12,
      top=0.86,
      wspace=0.40,
      hspace=0.38,
    )
    projection_slots = ((0, 0), (0, 1), (1, 0))
    for panel_index, projection in enumerate(resolved.projections):
      axis = figure.add_subplot(grid[projection_slots[panel_index]])
      first, second, first_axis_name, second_axis_name = projection_axes[projection]
      if valid_indices:
        axis.scatter(
          tuple(result.points_m[index][first] for index in valid_indices),
          tuple(result.points_m[index][second] for index in valid_indices),
          c=valid_values,
          cmap=resolved.color_map,
          norm=normalization,
          s=38,
          edgecolors='black',
          linewidths=0.25,
        )
      if invalid_indices:
        axis.scatter(
          tuple(result.points_m[index][first] for index in invalid_indices),
          tuple(result.points_m[index][second] for index in invalid_indices),
          color='#d62728',
          marker='x',
          s=42,
          label='invalid / unavailable',
        )
        axis.legend(loc='best', fontsize=8)
      axis.set_xlabel(f'{result.coordinate_frame_id} {first_axis_name} [m]')
      axis.set_ylabel(f'{result.coordinate_frame_id} {second_axis_name} [m]')
      axis.set_title(f'{projection} queried points')
      axis.grid(True, alpha=0.22)
      axis.margins(0.08)
      axis.set_aspect('equal', adjustable='datalim')
    ####

    profile_axis = figure.add_subplot(grid[1, 1])
    if valid_indices:
      profile_axis.scatter(
        valid_indices,
        valid_values,
        color='#4c78a8',
        s=34,
        label='valid samples',
      )
      if channel.absolute_standard_uncertainty is not None:
        for index in valid_indices:
          uncertainty = channel.absolute_standard_uncertainty[index]
          if uncertainty is not None:
            profile_axis.errorbar(
              index,
              channel.values[index],
              yerr=uncertainty,
              color='#4c78a8',
              capsize=2,
              linewidth=1,
            )
      profile_axis.legend(loc='best', fontsize=8)
    else:
      profile_axis.text(0.5, 0.5, 'No valid samples', ha='center', va='center', transform=profile_axis.transAxes)
    profile_axis.set_xlabel('Request order index [1] (not time)')
    profile_axis.set_ylabel(f'{channel.semantic} [{channel.unit}]')
    profile_axis.set_title(f'Query-order samples; {len(valid_indices)} valid / {len(point_indices)}')
    profile_axis.grid(True, alpha=0.22)
    if valid_values and normalization is not None:
      scalar = plt.cm.ScalarMappable(norm=normalization, cmap=resolved.color_map)
      colorbar_axis = figure.add_subplot(grid[:, 2])
      colorbar = figure.colorbar(scalar, cax=colorbar_axis)
      colorbar.set_label(f'{channel.semantic} [{channel.unit}]')
      colorbar.formatter.set_useOffset(False)
      colorbar.update_ticks()
    else:
      colorbar_axis = figure.add_subplot(grid[:, 2])
      colorbar_axis.set_visible(False)
    ####

    figure.suptitle(
      f"{channel.semantic} ({field_id}) | sampling: {channel.sampling_method} | "
      f"{source['provider_id']} / snapshot {source['snapshot_id']} / {result.coordinate_frame_id}",
      fontsize=10,
    )
    figure.text(
      0.5,
      0.01,
      'Spatial panels show only queried points. No connecting surface, plume boundary, or interpolation is added.',
      ha='center',
      fontsize=8,
    )
    slug = re.sub(r'[^A-Za-z0-9._-]+', '_', field_id).strip('._-') or 'field'
    slug += '-' + hashlib.sha256(field_id.encode('utf-8')).hexdigest()[:8]
    image_name = f'field_{slug}_views.png'
    figure.savefig(output / image_name, dpi=140, metadata={
      'CapabilityId': result.metadata.capability.wire_id,
      'ResultDigestSHA256': result_digest,
      'VisualizationSpecSHA256': resolved.digest_sha256(),
      'FieldId': field_id,
    })
    plt.close(figure)
    artifact_records.append(GalleryArtifact(
      f'spatial-local-field.field.{field_id}.orthographic-and-query-order',
      image_name,
      'image/png',
    ))
  ####

  spec_path = output / 'visualization_spec.json'
  spec_path.write_text(json.dumps({
    'schema': 'plume.visualization.spec-export@1',
    'view_spec': resolved.model_dump(mode='json'),
    'view_spec_digest_sha256': resolved.digest_sha256(),
    'source': source,
  }, indent=2, sort_keys=True) + '\n', encoding='utf-8')
  product_metadata = {
    'coordinate_frame_id': result.coordinate_frame_id,
    'point_count': len(result.points_m),
    'field_ids': list(result.field_ids),
    'channels': [
      {
        'field_id': channel.field_id,
        'semantic': channel.semantic,
        'unit': channel.unit,
        'sampling_method': channel.sampling_method,
        'valid_sample_count': sum(status.code.value == 'ok' for status in channel.sample_status),
        'uncertainty_available': channel.absolute_standard_uncertainty is not None,
      }
      for channel in result.channels
    ],
  }
  manifest = VisualizationGalleryManifest(
    schema=GALLERY_MANIFEST_SCHEMA,
    product='spatial-local-field',
    view_spec=resolved,
    source=source,
    product_metadata=product_metadata,
    artifacts=tuple(artifact_records),
    guardrails=(
      'spatial_views_plot_only_exact_provider_query_points',
      'invalid_samples_remain_marked_and_are_not_replaced_with_values',
      'query_order_is_not_a_time_axis_or_physical_path',
      'no_interpolation_surface_or_plume_boundary_is_inferred',
    ),
    manifest_path=output / 'gallery_manifest.json',
  )
  _write_gallery_manifest(manifest)
  return manifest
####


def render_engineering_flux_section_gallery(
  data: CanonicalEngineeringFluxSeriesData | EngineeringFluxSectionResult,
  output_dir: str | Path,
  *,
  spec: EngineeringFluxSectionGallerySpec | None = None,
) -> VisualizationGalleryManifest:
  """Render exact conservative section samples as station-indexed views.

  The renderer uses scatter markers at requested stations, leaves failed or
  absent values blank, and does not interpolate between samples.
  """

  if isinstance(data, EngineeringFluxSectionResult):
    data = extract_canonical_visualization_data(data)  # type: ignore[assignment]
  if not isinstance(data, CanonicalEngineeringFluxSeriesData):
    raise TypeError('data must be an EngineeringFluxSectionResult or its canonical visualization data')
  result = data.result
  resolved = spec or EngineeringFluxSectionGallerySpec.for_result(result)
  if not isinstance(resolved, EngineeringFluxSectionGallerySpec):
    raise TypeError('spec must be an EngineeringFluxSectionGallerySpec')
  resolved.validate_for_result(result)

  output = Path(output_dir)
  output.mkdir(parents=True, exist_ok=True)
  plt, _, _ = _matplotlib()

  stations = tuple(sample.station_arclength_m for sample in result.samples)
  valid_samples = tuple(
    sample for sample in result.samples if sample.status.code.value == 'ok'
  )
  station_label = 'Centerline arc length [m]'
  figure, axes_grid = plt.subplots(3, 3, figsize=(15.0, 11.0), sharex=True)
  axes = tuple(axes_grid.flat)

  def scatter_quantity(
    axis: Any,
    values: Sequence[float | None],
    *,
    title: str,
    unit: str,
    color: str = '#4c78a8',
  ) -> None:
    points = tuple(
      (station, value)
      for station, value in zip(stations, values, strict=True)
      if value is not None and isfinite(value)
    )
    if points:
      axis.scatter(
        tuple(point[0] for point in points),
        tuple(point[1] for point in points),
        color=color,
        s=28,
        zorder=3,
      )
    else:
      axis.text(0.5, 0.5, 'No successful values', transform=axis.transAxes, ha='center', va='center')
    axis.set_title(title)
    axis.set_ylabel(unit)
    axis.grid(True, alpha=0.22)
  ####

  scatter_quantity(
    axes[0],
    tuple(sample.section.mass_flow_kg_s if sample.section is not None else None for sample in result.samples),
    title='Mass flow',
    unit='kg/s',
  )
  scatter_quantity(
    axes[1],
    tuple(
      sqrt(sum(component * component for component in sample.section.momentum_flux_N))
      if sample.section is not None else None
      for sample in result.samples
    ),
    title='Momentum flux magnitude',
    unit='N',
  )
  scatter_quantity(
    axes[2],
    tuple(
      sample.section.stagnation_enthalpy_flux_W if sample.section is not None else None
      for sample in result.samples
    ),
    title='Stagnation-enthalpy flux',
    unit='W',
  )

  pressure_axis = axes[3]
  pressure_axis.scatter(
    tuple(sample.station_arclength_m for sample in valid_samples),
    tuple(sample.section.pressure_Pa for sample in valid_samples if sample.section is not None),
    color='#4c78a8',
    s=28,
    label='static pressure',
  )
  pressure_axis.scatter(
    tuple(sample.station_arclength_m for sample in valid_samples),
    tuple(sample.section.ambient_pressure_Pa for sample in valid_samples if sample.section is not None),
    color='#f58518',
    marker='s',
    s=24,
    label='ambient pressure',
  )
  if not valid_samples:
    pressure_axis.text(0.5, 0.5, 'No successful values', transform=pressure_axis.transAxes, ha='center', va='center')
  pressure_axis.set_title('Section and ambient pressure')
  pressure_axis.set_ylabel('Pa')
  pressure_axis.grid(True, alpha=0.22)
  if valid_samples:
    pressure_axis.legend(fontsize=8)
  ####

  scatter_quantity(
    axes[4],
    tuple(
      sample.section.pressure_match_relative_residual if sample.section is not None else None
      for sample in result.samples
    ),
    title='Pressure-match relative residual',
    unit='1',
    color='#e45756',
  )
  scatter_quantity(
    axes[5],
    tuple(sample.section.area_m2 if sample.section is not None else None for sample in result.samples),
    title='Cross-section area',
    unit='m²',
    color='#72b7b2',
  )
  scatter_quantity(
    axes[6],
    tuple(
      sample.section.characteristic_radius_m if sample.section is not None else None
      for sample in result.samples
    ),
    title='Characteristic radius',
    unit='m',
    color='#b279a2',
  )

  species_axis = axes[7]
  species_ids = tuple(sorted({
    item.species_id
    for sample in valid_samples
    if sample.section is not None
    for item in sample.section.species_mass_flows_kg_s
  }))
  if species_ids:
    palette = plt.get_cmap('tab10')
    for species_index, species_id in enumerate(species_ids):
      points = []
      for sample in result.samples:
        if sample.section is None:
          continue
        species_values = {
          item.species_id: item.mass_flow_kg_s
          for item in sample.section.species_mass_flows_kg_s
        }
        if species_id in species_values:
          points.append((sample.station_arclength_m, species_values[species_id]))
      if points:
        species_axis.scatter(
          tuple(point[0] for point in points),
          tuple(point[1] for point in points),
          color=palette(species_index % 10),
          s=26,
          label=species_id,
        )
    species_axis.legend(fontsize=7, title='species', loc='best')
  else:
    species_axis.text(0.5, 0.5, 'No successful species values', transform=species_axis.transAxes, ha='center', va='center')
  species_axis.set_title('Species mass flow')
  species_axis.set_ylabel('kg/s')
  species_axis.grid(True, alpha=0.22)
  ####

  status_axis = axes[8]
  status_codes = tuple(dict.fromkeys(sample.status.code.value for sample in result.samples))
  status_y = {status: index for index, status in enumerate(status_codes)}
  for sample in result.samples:
    status = sample.status.code.value
    is_ok = status == 'ok'
    status_axis.scatter(
      sample.station_arclength_m,
      status_y[status],
      marker='o' if is_ok else 'x',
      color='#2a9d8f' if is_ok else '#c44536',
      s=38,
      zorder=3,
    )
  status_axis.set_yticks(tuple(range(len(status_codes))))
  status_axis.set_yticklabels(status_codes)
  status_axis.set_title('Sample status')
  status_axis.grid(True, axis='x', alpha=0.22)
  ####

  for axis in axes:
    axis.set_xlabel(station_label)
  figure.suptitle(
    'Engineering flux sections — exact requested stations; no interpolation',
    fontsize=13,
  )
  figure.tight_layout(rect=(0.0, 0.0, 1.0, 0.95))
  image_path = output / 'engineering_flux_station_series.png'
  figure.savefig(image_path, dpi=140, metadata={
    'CapabilityId': result.metadata.capability.wire_id,
    'ResultSHA256': data.result_digest_sha256,
    'RequestSHA256': result.metadata.request_digest_sha256,
    'VisualizationSpecSHA256': resolved.digest_sha256(),
  })
  plt.close(figure)

  data_payload = data.model_dump()
  json_path = output / 'engineering_flux_station_series.json'
  json_path.write_text(
    json.dumps(data_payload, indent=2, sort_keys=True, allow_nan=False) + '\n',
    encoding='utf-8',
  )

  csv_path = output / 'engineering_flux_station_series.csv'
  vector_fields = (
    ('centerline_position', 'centerline_position_m', 'sample'),
    ('centerline_tangent', 'centerline_tangent', 'sample'),
    ('section_center', 'center_m', 'section'),
    ('section_normal', 'normal', 'section'),
    ('momentum_flux', 'momentum_flux_N', 'section'),
    ('advective_momentum_flux', 'advective_momentum_flux_N', 'section'),
    ('pressure_thrust', 'pressure_thrust_N', 'section'),
  )
  columns = [
    'station_arclength_m',
    'sampling_method',
    'status_code',
    'status_message',
    'status_retryable',
    'section_time_s',
    'mass_flow_kg_s',
    'momentum_flux_magnitude_N',
    'stagnation_enthalpy_flux_W',
    'total_energy_flow_W',
    'pressure_Pa',
    'ambient_pressure_Pa',
    'pressure_match_relative_residual',
    'area_m2',
    'characteristic_radius_m',
    'second_moment_yy_m2',
    'second_moment_yz_m2',
    'second_moment_zz_m2',
    'species_mass_flows_kg_s_json',
    'uncertainty_json',
    'section_provenance_json',
    'applicability_json',
  ]
  for prefix, _, _ in vector_fields:
    columns.extend(f'{prefix}_{axis}' for axis in ('x', 'y', 'z'))
  ####
  with csv_path.open('w', encoding='utf-8', newline='') as stream:
    writer = csv.DictWriter(stream, fieldnames=columns)
    writer.writeheader()
    for sample in result.samples:
      section = sample.section
      row: dict[str, Any] = {
        'station_arclength_m': f'{sample.station_arclength_m:.17g}',
        'sampling_method': sample.sampling_method or '',
        'status_code': sample.status.code.value,
        'status_message': sample.status.message or '',
        'status_retryable': str(sample.status.retryable).lower(),
      }
      for prefix, attribute, owner in vector_fields:
        source = sample if owner == 'sample' else section
        vector = getattr(source, attribute) if source is not None else None
        for axis_index, axis_name in enumerate(('x', 'y', 'z')):
          row[f'{prefix}_{axis_name}'] = (
            f'{vector[axis_index]:.17g}' if vector is not None else ''
          )
      if section is not None:
        momentum_magnitude = sqrt(sum(value * value for value in section.momentum_flux_N))
        row.update({
          'section_time_s': f'{section.time_s:.17g}',
          'mass_flow_kg_s': f'{section.mass_flow_kg_s:.17g}',
          'momentum_flux_magnitude_N': f'{momentum_magnitude:.17g}',
          'stagnation_enthalpy_flux_W': (
            f'{section.stagnation_enthalpy_flux_W:.17g}'
            if section.stagnation_enthalpy_flux_W is not None else ''
          ),
          'total_energy_flow_W': (
            f'{section.total_energy_flow_W:.17g}'
            if section.total_energy_flow_W is not None else ''
          ),
          'pressure_Pa': f'{section.pressure_Pa:.17g}',
          'ambient_pressure_Pa': f'{section.ambient_pressure_Pa:.17g}',
          'pressure_match_relative_residual': f'{section.pressure_match_relative_residual:.17g}',
          'area_m2': f'{section.area_m2:.17g}',
          'characteristic_radius_m': (
            f'{section.characteristic_radius_m:.17g}'
            if section.characteristic_radius_m is not None else ''
          ),
          'second_moment_yy_m2': f'{section.cross_section_second_moment_m2[0][0]:.17g}',
          'second_moment_yz_m2': f'{section.cross_section_second_moment_m2[0][1]:.17g}',
          'second_moment_zz_m2': f'{section.cross_section_second_moment_m2[1][1]:.17g}',
          'species_mass_flows_kg_s_json': json.dumps(
            [item.model_dump(mode='json') for item in section.species_mass_flows_kg_s],
            sort_keys=True,
            separators=(',', ':'),
            allow_nan=False,
          ),
          'uncertainty_json': json.dumps(
            section.uncertainty,
            sort_keys=True,
            separators=(',', ':'),
            allow_nan=False,
          ),
          'section_provenance_json': json.dumps(
            section.provenance.model_dump(mode='json'),
            sort_keys=True,
            separators=(',', ':'),
            allow_nan=False,
          ),
          'applicability_json': json.dumps(
            section.applicability.model_dump(mode='json'),
            sort_keys=True,
            separators=(',', ':'),
            allow_nan=False,
          ),
        })
      else:
        row.update({column: '' for column in columns if column not in row})
      writer.writerow(row)
  ####

  metadata = result.metadata
  status_counts: dict[str, int] = {}
  for sample in result.samples:
    code = sample.status.code.value
    status_counts[code] = status_counts.get(code, 0) + 1
  source = {
    'capability_id': metadata.capability.wire_id,
    'result_id': metadata.result_id,
    'result_digest_sha256': data.result_digest_sha256,
    'request_digest_sha256': metadata.request_digest_sha256,
    'snapshot_id': metadata.snapshot.snapshot_id,
    'session_id': metadata.snapshot.session_id,
    'time_s': metadata.snapshot.time_s,
    'frame_id': metadata.output_frame_id,
    'centerline_reference_id': result.request.centerline_reference_id,
    'provider_id': metadata.provenance.provider_id,
    'provider_version': metadata.provenance.provider_version,
    'provenance_id': metadata.provenance.model_lineage_id,
    'claims': metadata.claims.model_dump(mode='json'),
    'applicability': metadata.applicability.model_dump(mode='json'),
    'provenance': metadata.provenance.model_dump(mode='json'),
  }
  spec_path = output / 'visualization_spec.json'
  spec_path.write_text(json.dumps({
    'schema': 'plume.visualization.engineering-flux-spec-export@1',
    'view_spec': resolved.model_dump(mode='json'),
    'view_spec_digest_sha256': resolved.digest_sha256(),
    'source': source,
  }, indent=2, sort_keys=True, allow_nan=False) + '\n', encoding='utf-8')
  artifacts = (
    GalleryArtifact('metadata.visualization-spec', spec_path.name, 'application/json'),
    GalleryArtifact('engineering-flux.station-series', image_path.name, 'image/png'),
    GalleryArtifact('engineering-flux.station-samples', csv_path.name, 'text/csv'),
    GalleryArtifact('engineering-flux.source-result', json_path.name, 'application/json'),
  )
  manifest = VisualizationGalleryManifest(
    schema=GALLERY_MANIFEST_SCHEMA,
    product='engineering-flux-section',
    view_spec=resolved,
    source=source,
    product_metadata={
      'station_count': len(result.samples),
      'successful_sample_count': len(valid_samples),
      'failed_sample_count': len(result.samples) - len(valid_samples),
      'status_counts': status_counts,
      'requested_stations_m': list(stations),
      'sample_order': 'exact request order',
      'station_interpolation_performed': False,
    },
    artifacts=artifacts,
    guardrails=(
      'plots_show_exact_requested_stations_without_interpolation',
      'failed_sample_quantities_are_masked_and_exported_as_blank',
      'momentum_flux_magnitude_is_derived_only_from_the_declared_vector',
      'section_series_does_not_define_plume_boundaries_or_physical_validation',
      'stagnation_enthalpy_flux_is_not_total_energy_flow',
    ),
    manifest_path=output / 'gallery_manifest.json',
  )
  _write_gallery_manifest(manifest)
  return manifest
####


def render_capability_gallery(
  data: CanonicalAxisymmetricZoneFieldData
  | CanonicalSpatialSupportData
  | CanonicalProjectedAreaData
  | CanonicalSpatialLocalFieldData,
  output_dir: str | Path,
  *,
  spec: AxisymmetricZoneGallerySpec | CapabilityGalleryViewSpec | SpatialLocalFieldGallerySpec | None = None,
) -> VisualizationGalleryManifest | AxisymmetricZoneGalleryManifest:
  """Dispatch canonical supporting capabilities to their static galleries."""

  if isinstance(data, CanonicalAxisymmetricZoneFieldData):
    if spec is not None and not isinstance(spec, AxisymmetricZoneGallerySpec):
      raise TypeError('axisymmetric-zone galleries require AxisymmetricZoneGallerySpec')
    return render_axisymmetric_zone_gallery(data, output_dir, spec=spec)
  ####
  if isinstance(data, CanonicalSpatialSupportData):
    return render_spatial_support_gallery(data, output_dir, spec=spec)
  ####
  if isinstance(data, CanonicalProjectedAreaData):
    return render_projected_area_gallery(data, output_dir, spec=spec)
  ####
  if isinstance(data, CanonicalSpatialLocalFieldData):
    if spec is not None and not isinstance(spec, SpatialLocalFieldGallerySpec):
      raise TypeError('local-field galleries require SpatialLocalFieldGallerySpec')
    return render_spatial_local_field_gallery(
      data,
      output_dir,
      spec=spec,
    )
  ####
  raise TypeError('data must be a canonical spatial supporting-capability result')
####


def render_spectral_radiance_image_gallery(
  result: SpectralRadianceImageResult,
  output_dir: str | Path,
  *,
  spec: SpectralRadianceImageGallerySpec | None = None,
) -> VisualizationGalleryManifest:
  """Render source radiance, transmittance, validity, and selected-pixel views."""

  if not isinstance(result, SpectralRadianceImageResult):
    raise TypeError('result must be SpectralRadianceImageResult')
  resolved = spec or SpectralRadianceImageGallerySpec.for_result(result)
  if not isinstance(resolved, SpectralRadianceImageGallerySpec):
    raise TypeError('spec must be SpectralRadianceImageGallerySpec')
  resolved.validate_for_result(result)
  output = Path(output_dir)
  output.mkdir(parents=True, exist_ok=True)
  plt, _, _ = _matplotlib()
  import numpy as np
  from matplotlib.colors import ListedColormap
  from matplotlib.patches import Patch

  wave_index = resolved.wavelength_index
  wavelength_m = result.wavelengths_m[wave_index]
  wavelength_um = wavelength_m * 1.0e6
  selected_row = resolved.selected_pixel_row
  selected_column = resolved.selected_pixel_column
  validity = np.asarray(result.validity_mask, dtype=bool)
  source_values = np.asarray([
    [pixel[wave_index] for pixel in row]
    for row in result.source_spectral_radiance_W_m2_sr_m
  ], dtype=float)
  transmittance_values = np.asarray([
    [pixel[wave_index] for pixel in row]
    for row in result.background_transmittance
  ], dtype=float)
  source_map = np.ma.masked_where(~validity, source_values)
  transmittance_map = np.ma.masked_where(~validity, transmittance_values)
  valid_source_values = source_values[validity]
  if valid_source_values.size:
    source_min = float(np.min(valid_source_values))
    source_max = float(np.max(valid_source_values))
    if source_min == source_max:
      delta = max(abs(source_min) * 0.05, 1.0e-12)
      source_min = max(0.0, source_min - delta)
      source_max += delta
  else:
    source_min, source_max = 0.0, 1.0
  ####
  source_metadata = _spectral_radiance_image_source(result)
  view_spec_digest = resolved.digest_sha256()

  def save_figure(figure: Any, path: Path, *, title: str) -> None:
    figure.tight_layout()
    figure.savefig(path, dpi=160, metadata={
      'Title': title,
      'SourceContentSHA256': source_metadata['content_sha256'],
      'VisualizationSpecSHA256': view_spec_digest,
    })
    plt.close(figure)
  ####

  source_path = output / 'spectral_radiance_map.png'
  figure, axis = plt.subplots(figsize=(8.5, 5.5))
  source_cmap = plt.get_cmap(resolved.color_map).copy()
  source_cmap.set_bad('#b8c0c8')
  source_image = axis.imshow(
    source_map,
    origin='upper',
    interpolation='nearest',
    aspect='auto',
    cmap=source_cmap,
    vmin=source_min,
    vmax=source_max,
  )
  axis.scatter(
    (selected_column,),
    (selected_row,),
    marker='x',
    s=70,
    linewidths=2,
    color='cyan',
    label='selected pixel',
  )
  axis.set_xlabel('Pixel column [zero-based index]')
  axis.set_ylabel('Pixel row [zero-based index]')
  axis.set_title(f'Pre-detector source spectral radiance at {wavelength_um:.6g} μm')
  axis.legend(loc='best')
  figure.colorbar(source_image, ax=axis, label='Source spectral radiance [W m⁻² sr⁻¹ m⁻¹]')
  save_figure(figure, source_path, title='Pre-detector source spectral radiance map')

  transmittance_path = output / 'background_transmittance_map.png'
  figure, axis = plt.subplots(figsize=(8.5, 5.5))
  transmittance_cmap = plt.get_cmap('viridis').copy()
  transmittance_cmap.set_bad('#b8c0c8')
  transmittance_image = axis.imshow(
    transmittance_map,
    origin='upper',
    interpolation='nearest',
    aspect='auto',
    cmap=transmittance_cmap,
    vmin=0.0,
    vmax=1.0,
  )
  axis.scatter(
    (selected_column,),
    (selected_row,),
    marker='x',
    s=70,
    linewidths=2,
    color='red',
    label='selected pixel',
  )
  axis.set_xlabel('Pixel column [zero-based index]')
  axis.set_ylabel('Pixel row [zero-based index]')
  axis.set_title(f'Background transmittance at {wavelength_um:.6g} μm')
  axis.legend(loc='best')
  figure.colorbar(transmittance_image, ax=axis, label='Background transmittance [1]')
  save_figure(figure, transmittance_path, title='Background transmittance map')

  validity_path = output / 'pixel_validity_map.png'
  figure, axis = plt.subplots(figsize=(8.5, 5.5))
  axis.imshow(
    validity.astype(float),
    origin='upper',
    interpolation='nearest',
    aspect='auto',
    cmap=ListedColormap(('#b8c0c8', '#54a24b')),
    vmin=0.0,
    vmax=1.0,
  )
  axis.set_xlabel('Pixel column [zero-based index]')
  axis.set_ylabel('Pixel row [zero-based index]')
  axis.set_title(
    f'Pixel validity — {int(np.count_nonzero(validity))} valid, '
    f'{int(validity.size - np.count_nonzero(validity))} invalid'
  )
  axis.legend(handles=(
    Patch(facecolor='#54a24b', label='valid sample'),
    Patch(facecolor='#b8c0c8', label='invalid; see status export'),
  ), loc='best')
  save_figure(figure, validity_path, title='Pixel validity map')

  wavelengths_um = np.asarray(result.wavelengths_m, dtype=float) * 1.0e6
  selected_valid = result.validity_mask[selected_row][selected_column]
  selected_status = result.pixel_status[selected_row][selected_column]
  spectrum_path = output / 'selected_pixel_spectrum.png'
  figure, axis = plt.subplots(figsize=(8.5, 5.0))
  if selected_valid:
    axis.plot(
      wavelengths_um,
      result.source_spectral_radiance_W_m2_sr_m[selected_row][selected_column],
      marker='o',
      color='#c9273f',
    )
  else:
    axis.text(
      0.5,
      0.5,
      f'Pixel invalid: {selected_status.code.value}',
      transform=axis.transAxes,
      ha='center',
      va='center',
    )
  axis.set_xlabel('Wavelength [μm]')
  axis.set_ylabel('Source spectral radiance [W m⁻² sr⁻¹ m⁻¹]')
  axis.set_title(f'Source spectrum at pixel (row {selected_row}, column {selected_column})')
  axis.grid(True, alpha=0.22)
  save_figure(figure, spectrum_path, title='Selected pixel source-radiance spectrum')

  selected_transmittance_path = output / 'selected_pixel_transmittance.png'
  figure, axis = plt.subplots(figsize=(8.5, 5.0))
  if selected_valid:
    axis.plot(
      wavelengths_um,
      result.background_transmittance[selected_row][selected_column],
      marker='o',
      color='#3f73a8',
    )
    axis.set_ylim(0.0, 1.0)
  else:
    axis.text(
      0.5,
      0.5,
      f'Pixel invalid: {selected_status.code.value}',
      transform=axis.transAxes,
      ha='center',
      va='center',
    )
  axis.set_xlabel('Wavelength [μm]')
  axis.set_ylabel('Background transmittance [1]')
  axis.set_title(f'Background transmittance at pixel (row {selected_row}, column {selected_column})')
  axis.grid(True, alpha=0.22)
  save_figure(figure, selected_transmittance_path, title='Selected pixel background transmittance')

  table_path = output / 'spectral_radiance_image.csv'
  with table_path.open('w', encoding='utf-8', newline='') as stream:
    writer = csv.writer(stream)
    writer.writerow((
      'pixel_row', 'pixel_column', 'wavelength_index', 'wavelength_m',
      'source_spectral_radiance_W_m2_sr_m', 'background_transmittance',
      'valid', 'status_code', 'status_message', 'ray_sample_count',
      'pixel_collection_weight_m2_sr',
    ))
    for row_index in range(result.height_px):
      for column_index in range(result.width_px):
        valid = result.validity_mask[row_index][column_index]
        status = result.pixel_status[row_index][column_index]
        for index, wavelength in enumerate(result.wavelengths_m):
          writer.writerow((
            row_index,
            column_index,
            index,
            f'{wavelength:.17g}',
            f'{result.source_spectral_radiance_W_m2_sr_m[row_index][column_index][index]:.17g}' if valid else '',
            f'{result.background_transmittance[row_index][column_index][index]:.17g}' if valid else '',
            str(valid).lower(),
            status.code.value,
            status.message or '',
            result.ray_sample_count[row_index][column_index],
            f'{result.pixel_collection_weight_m2_sr[row_index][column_index]:.17g}',
          ))
  ####

  spec_path = output / 'visualization_spec.json'
  spec_path.write_text(json.dumps({
    'schema': 'plume.visualization.spec-export@1',
    'view_spec': resolved.model_dump(mode='json'),
    'view_spec_digest_sha256': view_spec_digest,
    'source': source_metadata,
  }, allow_nan=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
  data_path = output / 'spectral_radiance_image.json'
  data_path.write_text(json.dumps({
    'schema': 'plume.visualization.spectral-radiance-image-data@1',
    'source': source_metadata,
    'result_digest_sha256': source_metadata['content_sha256'],
    'result': result.model_dump(mode='json'),
    'view_spec': resolved.model_dump(mode='json'),
    'view_spec_digest_sha256': view_spec_digest,
  }, allow_nan=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')

  artifacts = (
    GalleryArtifact('spectral-radiance-image.source-map', source_path.name, 'image/png'),
    GalleryArtifact('spectral-radiance-image.transmittance-map', transmittance_path.name, 'image/png'),
    GalleryArtifact('spectral-radiance-image.validity-map', validity_path.name, 'image/png'),
    GalleryArtifact('spectral-radiance-image.selected-spectrum', spectrum_path.name, 'image/png'),
    GalleryArtifact('spectral-radiance-image.selected-transmittance', selected_transmittance_path.name, 'image/png'),
    GalleryArtifact('spectral-radiance-image.values', table_path.name, 'text/csv'),
    GalleryArtifact('spectral-radiance-image.source-result', data_path.name, 'application/json'),
    GalleryArtifact('metadata.visualization-spec', spec_path.name, 'application/json'),
  )
  manifest = VisualizationGalleryManifest(
    schema=GALLERY_MANIFEST_SCHEMA,
    product='spectral-radiance-image',
    view_spec=resolved,
    source=source_metadata,
    product_metadata={
      'pixel_frame_id': result.pixel_frame_id,
      'ray_frame_id': result.ray_frame_id,
      'width_px': result.width_px,
      'height_px': result.height_px,
      'pixel_indexing': result.pixel_indexing,
      'wavelength_count': len(result.wavelengths_m),
      'selected_wavelength_index': wave_index,
      'selected_wavelength_m': wavelength_m,
      'selected_pixel_row_column': [selected_row, selected_column],
      'selected_pixel_valid': selected_valid,
      'selected_pixel_status': selected_status.model_dump(mode='json'),
      'valid_pixel_count': int(np.count_nonzero(validity)),
      'invalid_pixel_count': int(validity.size - np.count_nonzero(validity)),
      'source_component': result.source_component,
      'aggregation_policy': result.aggregation_policy,
    },
    artifacts=artifacts,
    guardrails=(
      'source_radiance_and_background_transmittance_are_separate_fields_and_views',
      'invalid_pixels_remain_masked_and_csv_values_are_blank_for_invalid_samples',
      'pixel_rows_and_columns_are_not_inferred_angular_or_spatial_coordinates',
      'nearest_raster_display_does_not_interpolate_source_pixels',
      'detector_response_exposure_electrons_and_ADC_counts_are_not_in_this_result',
    ),
    manifest_path=output / 'gallery_manifest.json',
  )
  _write_gallery_manifest(manifest)
  return manifest
####


def render_product_gallery(
  result: ProductResult
  | AxisymmetricZoneFieldResult
  | AxisymmetricZoneField
  | AxisymmetricZone
  | CanonicalAxisymmetricZoneFieldData
  | CanonicalSpatialSupportData
  | CanonicalProjectedAreaData
  | CanonicalSpectralRayTransferData
  | CanonicalSpatialLocalFieldData
  | CanonicalEngineeringFluxSeriesData
  | SpatialLocalFieldResult
  | EngineeringFluxSectionResult
  | SpectralRadianceImageResult,
  output_dir: str | Path,
  *,
  spec: VisualizationSpec
  | AxisymmetricZoneGallerySpec
  | CapabilityGalleryViewSpec
  | CanonicalSpectralRayTransferGallerySpec
  | SpatialLocalFieldGallerySpec
  | EngineeringFluxSectionGallerySpec
  | SpectralRadianceImageGallerySpec
  | None = None,
) -> VisualizationGalleryManifest | AxisymmetricZoneGalleryManifest:
  """Dispatch a standard product result or supporting capability gallery."""

  if isinstance(result, CanonicalSpectralRayTransferData):
    if spec is not None and not isinstance(spec, CanonicalSpectralRayTransferGallerySpec):
      raise TypeError('canonical ray-transfer galleries require CanonicalSpectralRayTransferGallerySpec')
    return render_canonical_spectral_ray_transfer_gallery(result, output_dir, spec=spec)
  ####
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
    return render_axisymmetric_zone_gallery(result, output_dir, spec=spec)
  ####
  if isinstance(result, SpatialLocalFieldResult):
    result = extract_canonical_visualization_data(result)
  if isinstance(result, EngineeringFluxSectionResult):
    result = extract_canonical_visualization_data(result)
  if isinstance(result, CanonicalEngineeringFluxSeriesData):
    if spec is not None and not isinstance(spec, EngineeringFluxSectionGallerySpec):
      raise TypeError('engineering-flux galleries require EngineeringFluxSectionGallerySpec')
    return render_engineering_flux_section_gallery(result, output_dir, spec=spec)
  if isinstance(result, SpectralRadianceImageResult):
    if spec is not None and not isinstance(spec, SpectralRadianceImageGallerySpec):
      raise TypeError('spectral-radiance image galleries require SpectralRadianceImageGallerySpec')
    return render_spectral_radiance_image_gallery(result, output_dir, spec=spec)
  ####
  if isinstance(result, (CanonicalSpatialSupportData, CanonicalProjectedAreaData, CanonicalSpatialLocalFieldData)):
    if isinstance(result, CanonicalSpatialLocalFieldData):
      if spec is not None and not isinstance(spec, SpatialLocalFieldGallerySpec):
        raise TypeError('local-field galleries require SpatialLocalFieldGallerySpec')
    elif spec is not None and not isinstance(spec, CapabilityGalleryViewSpec):
      raise TypeError('supporting capability galleries require CapabilityGalleryViewSpec')
    ####
    return render_capability_gallery(result, output_dir, spec=spec)
  ####
  if spec is not None and not isinstance(spec, VisualizationSpec):
    raise TypeError('standard product galleries require VisualizationSpec')
  ####

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
  raise TypeError('result must be a standard product result or canonical supporting capability')
####
