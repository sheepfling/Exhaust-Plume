"""Renderer-neutral adapters for the canonical v1 product contracts.

The compatibility adapters in :mod:`exhaust_plume.api.visualization` consume
the legacy envelope DTOs.  This module covers the canonical contract
authority directly, without manufacturing an envelope, a frame, or a
measurement result that the source contract did not provide.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, sqrt
from typing import TYPE_CHECKING, Any, TypeAlias

from exhaust_plume.contracts.capability import (
  CapabilityId,
  ENGINEERING_FLUX_SECTION_CAPABILITY,
  SPATIAL_LOCAL_FIELD_CAPABILITY,
  SPATIAL_PROJECTED_AREA_CAPABILITY,
  SPATIAL_SUPPORT_CAPABILITY,
)
from exhaust_plume.contracts.common_v1 import (
  ResultMetadata,
  SampleStatus,
  canonical_digest,
)
from exhaust_plume.contracts.engineering_flux_v1 import EngineeringFluxSectionResult
from exhaust_plume.contracts.handoff import PlumeFluxSection
from exhaust_plume.contracts.ray_transfer_v1 import (
  SpectralRayTransferRequest,
  SpectralRayTransferResult,
)
from exhaust_plume.contracts.signature_v1 import (
  SpectralSignatureRequest,
  SpectralSignatureResult,
)
from exhaust_plume.contracts.spectral_radiance_image_v1 import SpectralRadianceImageResult
from exhaust_plume.contracts.spatial_v1 import (
  AxisymmetricZoneFieldResult,
  ProjectedAreaResult,
  SpatialSupportResult,
)
from exhaust_plume.contracts.local_field_v1 import SpatialLocalFieldResult
from exhaust_plume.contracts.model_lane_visualization_v1 import ModelLaneVisualizationResult
from exhaust_plume.contracts.spatial import (
  AxisymmetricZone,
  AxisymmetricZoneField,
  ProjectedAreaCapability,
  SpatialSupport,
)
from exhaust_plume.contracts.visual_v1 import (
  VisualBounds,
  VisualSection,
  VisualSectionedTubeResult,
  VisualTubeSummary,
)

if TYPE_CHECKING:
  from exhaust_plume.validation.fpa_visualization import (
    FpaViewProjection,
    FpaVisualizationInput,
    FpaVisualizationSpec,
  )

__all__ = (
  'CanonicalVisualizationSourceContext',
  'CanonicalVisualSectionedTubeData',
  'CanonicalAxisymmetricZoneData',
  'CanonicalAxisymmetricZoneFieldData',
  'CanonicalSpatialLocalFieldData',
  'CanonicalEngineeringFluxSectionData',
  'CanonicalEngineeringFluxSeriesData',
  'CanonicalSpatialSupportData',
  'CanonicalProjectedAreaData',
  'CanonicalSpectralIntensityLine',
  'CanonicalSpectralIntensityData',
  'CanonicalSpectralRayTransferLine',
  'CanonicalSpectralRayTransferData',
  'CanonicalFpaVisualizationData',
  'CanonicalProductVisualizationData',
  'CanonicalSpatialVisualizationData',
  'CanonicalSupportingVisualizationData',
  'CanonicalVisualizationData',
  'extract_visual_sectioned_tube_data',
  'extract_axisymmetric_zone_field_data',
  'extract_axisymmetric_zone_result_data',
  'extract_spatial_local_field_data',
  'extract_engineering_flux_section_data',
  'extract_engineering_flux_series_data',
  'extract_spatial_support_data',
  'extract_projected_area_data',
  'extract_spectral_signature_data',
  'extract_spectral_ray_transfer_data',
  'extract_fpa_visualization_data',
  'extract_canonical_product_visualization_data',
  'extract_canonical_visualization_data',
)


def _vector3(values: Any, name: str) -> tuple[float, float, float]:
  vector = tuple(float(value) for value in values)
  if len(vector) != 3 or any(not isfinite(value) for value in vector):
    raise ValueError(f'{name} must be a finite three-vector')
  ####
  return vector  # type: ignore[return-value]
####


@dataclass(frozen=True, slots=True)
class CanonicalVisualizationSourceContext:
  """Exact metadata retained by a canonical renderer adapter."""

  metadata: ResultMetadata

  def __post_init__(self) -> None:
    if not isinstance(self.metadata, ResultMetadata):
      raise TypeError('metadata must be canonical ResultMetadata')
    ####
  ####

  @property
  def capability_id(self) -> str:
    return self.metadata.capability.wire_id
  ####

  @property
  def frame_id(self) -> str:
    return self.metadata.output_frame_id
  ####

  @property
  def result_id(self) -> str:
    return self.metadata.result_id
  ####

  @property
  def snapshot_id(self) -> str:
    return self.metadata.snapshot.snapshot_id
  ####

  @property
  def provenance_id(self) -> str:
    return self.metadata.provenance.model_lineage_id
  ####

  def model_dump(self) -> dict[str, Any]:
    """Return the unchanged canonical metadata plus display identity."""

    return {
      'metadata': self.metadata.model_dump(mode='json'),
      'capability_id': self.capability_id,
      'frame_id': self.frame_id,
      'result_id': self.result_id,
      'snapshot_id': self.snapshot_id,
      'provenance_id': self.provenance_id,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class CanonicalVisualSectionedTubeData:
  """Line- and mesh-friendly data from ``VisualSectionedTubeResult``."""

  source_context: CanonicalVisualizationSourceContext
  sections: tuple[VisualSection, ...]
  channels: tuple[tuple[str, tuple[float, ...]], ...]
  visual_bounds: VisualBounds | None
  summary: VisualTubeSummary

  def __post_init__(self) -> None:
    if not isinstance(self.source_context, CanonicalVisualizationSourceContext):
      raise TypeError('source_context must be canonical visualization metadata')
    ####
    sections = tuple(self.sections)
    if len(sections) < 2 or any(not isinstance(section, VisualSection) for section in sections):
      raise ValueError('canonical visual data requires at least two typed sections')
    ####
    normalized_channels = tuple(
      (str(name), tuple(float(value) for value in values))
      for name, values in self.channels
    )
    names = tuple(name for name, _values in normalized_channels)
    if len(names) != len(set(names)) or any(not name for name in names):
      raise ValueError('canonical visual channel names must be unique and non-empty')
    ####
    if any(
      len(values) != len(sections)
      or any(not isfinite(value) for value in values)
      for _name, values in normalized_channels
    ):
      raise ValueError('canonical visual channels must align with finite sections')
    ####
    if self.source_context.capability_id != 'plume.visual.sectioned-tube@1':
      raise ValueError('source metadata must identify the canonical visual capability')
    ####
    object.__setattr__(self, 'sections', sections)
    object.__setattr__(self, 'channels', normalized_channels)
  ####

  @property
  def frame_id(self) -> str:
    return self.source_context.frame_id
  ####

  @property
  def arc_length_m(self) -> tuple[float, ...]:
    return tuple(section.arc_length_m for section in self.sections)
  ####

  def channel_values(self, channel_name: str) -> tuple[float, ...]:
    for name, values in self.channels:
      if name == channel_name:
        return values
      ####
    ####
    raise KeyError(f'unknown canonical visual channel {channel_name!r}')
  ####

  def model_dump(self) -> dict[str, Any]:
    return {
      'schema': 'plume.visualization.canonical.sectioned-tube@1',
      'frame_id': self.frame_id,
      'sections': [section.model_dump(mode='json') for section in self.sections],
      'channels': {name: list(values) for name, values in self.channels},
      'visual_bounds': (
        None
        if self.visual_bounds is None
        else self.visual_bounds.model_dump(mode='json')
      ),
      'summary': self.summary.model_dump(mode='json'),
      'source_context': self.source_context.model_dump(),
    }
  ####
####


@dataclass(frozen=True, slots=True)
class CanonicalAxisymmetricZoneData:
  """Immutable polygon/scalar data for one canonical spatial zone."""

  zone_id: str
  polygon_xr_m: tuple[tuple[float, float], ...]
  static_pressure_Pa: float
  static_temperature_K: float
  density_kgpm3: float
  mach: float
  phase: str
  cell_index: int
  geometry_status: str
  region_type: str | None = None
  region_label: str | None = None
  shock_angle_rad: float | None = None
  turn_angle_rad: float | None = None

  @classmethod
  def from_zone(cls, zone: AxisymmetricZone) -> 'CanonicalAxisymmetricZoneData':
    if not isinstance(zone, AxisymmetricZone):
      raise TypeError('zone must be a canonical AxisymmetricZone')
    ####
    polygon = tuple(
      (float(point[0]), float(point[1]))
      for point in zone.polygon_xr_m
    )
    return cls(
      zone_id=zone.zone_id,
      polygon_xr_m=polygon,
      static_pressure_Pa=float(zone.static_pressure_Pa),
      static_temperature_K=float(zone.static_temperature_K),
      density_kgpm3=float(zone.density_kgpm3),
      mach=float(zone.mach),
      phase=zone.phase,
      cell_index=zone.cell_index,
      geometry_status=zone.geometry_status.value,
      region_type=zone.region_type,
      region_label=zone.region_label,
      shock_angle_rad=zone.shock_angle_rad,
      turn_angle_rad=zone.turn_angle_rad,
    )
  ####

  @classmethod
  def from_result_zone(cls, zone: Any) -> 'CanonicalAxisymmetricZoneData':
    """Adapt one source-bound zone DTO without dropping its annotations."""

    return cls(
      zone_id=zone.zone_id,
      polygon_xr_m=zone.polygon_xr_m,
      static_pressure_Pa=zone.static_pressure_Pa,
      static_temperature_K=zone.static_temperature_K,
      density_kgpm3=zone.density_kgpm3,
      mach=zone.mach,
      phase=zone.phase,
      cell_index=zone.cell_index,
      geometry_status=zone.geometry_status,
      region_type=zone.region_type,
      region_label=zone.region_label,
      shock_angle_rad=zone.shock_angle_rad,
      turn_angle_rad=zone.turn_angle_rad,
    )
  ####

  def __post_init__(self) -> None:
    polygon = tuple(
      (float(point[0]), float(point[1]))
      for point in self.polygon_xr_m
    )
    if len(polygon) < 3 or any(
      len(point) != 2 or any(not isfinite(value) for value in point)
      for point in polygon
    ):
      raise ValueError('canonical zone polygon must contain finite 2-D points')
    ####
    if any(
      not isfinite(value) or value <= 0.0
      for value in (
        self.static_pressure_Pa,
        self.static_temperature_K,
        self.density_kgpm3,
      )
    ) or not isfinite(self.mach) or self.mach < 0.0:
      raise ValueError('canonical zone scalar fields are outside their domains')
    ####
    if self.cell_index < 0 or not self.zone_id or not self.geometry_status:
      raise ValueError('canonical zone identity and cell index are invalid')
    ####
    if any(
      value is not None and not isfinite(value)
      for value in (self.shock_angle_rad, self.turn_angle_rad)
    ):
      raise ValueError('canonical zone angles must be finite when supplied')
    ####
    for name in ('region_type', 'region_label'):
      value = getattr(self, name)
      if value is not None and not value:
        raise ValueError(f'{name} must be non-empty when supplied')
      ####
    ####
    object.__setattr__(self, 'polygon_xr_m', polygon)
  ####

  def model_dump(self) -> dict[str, Any]:
    return {
      'zone_id': self.zone_id,
      'polygon_xr_m': [list(point) for point in self.polygon_xr_m],
      'static_pressure_Pa': self.static_pressure_Pa,
      'static_temperature_K': self.static_temperature_K,
      'density_kgpm3': self.density_kgpm3,
      'mach': self.mach,
      'phase': self.phase,
      'cell_index': self.cell_index,
      'geometry_status': self.geometry_status,
      'region_type': self.region_type,
      'region_label': self.region_label,
      'shock_angle_rad': self.shock_angle_rad,
      'turn_angle_rad': self.turn_angle_rad,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class CanonicalAxisymmetricZoneFieldData:
  """Renderer-neutral finite-zone field with explicit axial/radial axes."""

  zones: tuple[CanonicalAxisymmetricZoneData, ...]
  axis_definition: str
  capability_id: CapabilityId
  major_version: int
  source_context: CanonicalVisualizationSourceContext | None = None

  def __post_init__(self) -> None:
    zones = tuple(self.zones)
    if any(not isinstance(zone, CanonicalAxisymmetricZoneData) for zone in zones):
      raise TypeError('zones must contain canonical zone data')
    ####
    if not zones:
      raise ValueError('canonical zone visualization requires at least one zone')
    ####
    if not self.axis_definition or self.major_version < 1:
      raise ValueError('canonical zone-field identity is invalid')
    ####
    if self.capability_id is not CapabilityId.AXISYMMETRIC_ZONE_FIELD:
      raise ValueError('canonical zone data must identify the axisymmetric-zone-field capability')
    ####
    if self.source_context is not None and (
      self.source_context.capability_id != 'plume.spatial.axisymmetric-zone-field@1'
    ):
      raise ValueError('source metadata must identify the axisymmetric zone-field capability')
    ####
    object.__setattr__(self, 'zones', zones)
  ####

  @property
  def bounds_xr_m(self) -> tuple[tuple[float, float], tuple[float, float]]:
    points = tuple(point for zone in self.zones for point in zone.polygon_xr_m)
    return (
      (min(point[0] for point in points), min(point[1] for point in points)),
      (max(point[0] for point in points), max(point[1] for point in points)),
    )
  ####

  def model_dump(self) -> dict[str, Any]:
    bounds = self.bounds_xr_m
    payload = {
      'schema': 'plume.visualization.canonical.axisymmetric-zone-field@1',
      'capability_id': self.capability_id.value,
      'major_version': self.major_version,
      'axis_definition': self.axis_definition,
      'zones': [zone.model_dump() for zone in self.zones],
      'bounds_xr_m': [list(bounds[0]), list(bounds[1])],
    }
    if self.source_context is not None:
      payload['source_context'] = self.source_context.model_dump()
    ####
    return payload
  ####
####


@dataclass(frozen=True, slots=True)
class CanonicalSpatialLocalFieldData:
  """Source-bound point samples ready for renderer-neutral views."""

  result: SpatialLocalFieldResult
  source_context: CanonicalVisualizationSourceContext

  def __post_init__(self) -> None:
    if not isinstance(self.result, SpatialLocalFieldResult):
      raise TypeError('result must be a canonical SpatialLocalFieldResult')
    if not isinstance(self.source_context, CanonicalVisualizationSourceContext):
      raise TypeError('source_context must be canonical visualization metadata')
    if self.result.metadata.capability != SPATIAL_LOCAL_FIELD_CAPABILITY:
      raise ValueError('local-field result metadata identifies a different capability')
    if self.source_context.metadata != self.result.metadata:
      raise ValueError('local-field source context must retain exact result metadata')
    if self.result.coordinate_frame_id != self.source_context.frame_id:
      raise ValueError('local-field coordinates must use the exact output frame')
  ####

  @property
  def frame_id(self) -> str:
    return self.result.coordinate_frame_id
  ####

  def model_dump(self) -> dict[str, Any]:
    result = self.result.model_dump(mode='json')
    return {
      'schema': 'plume.visualization.canonical.spatial-local-field@1',
      'result_digest_sha256': canonical_digest(result),
      'frame_id': self.frame_id,
      'result': result,
      'source_context': self.source_context.model_dump(),
      'interpolation_performed_by_visualizer': False,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class CanonicalEngineeringFluxSectionData:
  """Renderer-neutral conservative handoff data for one flux section.

  ``PlumeFluxSection`` is a supporting handoff contract rather than a
  canonical ``ResultMetadata`` envelope.  This adapter therefore carries the
  exact section object and its declared provider metadata, but does not infer
  a frame, a mesh, a plume boundary, or a stronger validation claim.
  """

  section: PlumeFluxSection

  def __post_init__(self) -> None:
    if not isinstance(self.section, PlumeFluxSection):
      raise TypeError('section must be a canonical PlumeFluxSection')
    ####
  ####

  @property
  def capability_id(self) -> str:
    return ENGINEERING_FLUX_SECTION_CAPABILITY.wire_id
  ####

  @property
  def momentum_flux_magnitude_N(self) -> float:
    return sqrt(sum(value * value for value in self.section.momentum_flux_plume_n))
  ####

  def model_dump(self) -> dict[str, Any]:
    section = self.section
    return {
      'schema': 'plume.visualization.canonical.engineering-flux-section@1',
      'capability_id': self.capability_id,
      'center_plume_m': list(section.center_plume_m),
      'normal_plume': list(section.normal_plume),
      'area_m2': section.area_m2,
      'mass_flow_kg_s': section.mass_flow_kg_s,
      'momentum_flux_plume_n': list(section.momentum_flux_plume_n),
      'momentum_flux_magnitude_N': self.momentum_flux_magnitude_N,
      'total_enthalpy_flux_w': section.total_enthalpy_flux_w,
      'species_mass_flow_rates_kg_s': [
        {'species_id': species_id, 'mass_flow_kg_s': mass_flow}
        for species_id, mass_flow in section.species_mass_flow_rates_kg_s
      ],
      'pressure_Pa': section.pressure_Pa,
      'ambient_pressure_Pa': section.ambient_pressure_Pa,
      'pressure_match_relative_residual': section.pressure_match_relative_residual,
      'advective_momentum_flux_plume_n': (
        list(section.advective_momentum_flux_plume_n)
        if section.advective_momentum_flux_plume_n is not None
        else None
      ),
      'pressure_thrust_flux_plume_n': (
        list(section.pressure_thrust_flux_plume_n)
        if section.pressure_thrust_flux_plume_n is not None
        else None
      ),
      'characteristic_radius_m': section.characteristic_radius_m,
      'provider_metadata': dict(section.provider_metadata),
    }
  ####
####


@dataclass(frozen=True, slots=True)
class CanonicalEngineeringFluxSeriesData:
  """Renderer-neutral station samples from one exact flux-section result."""

  result: EngineeringFluxSectionResult
  source_context: CanonicalVisualizationSourceContext

  def __post_init__(self) -> None:
    if not isinstance(self.result, EngineeringFluxSectionResult):
      raise TypeError('result must be a canonical EngineeringFluxSectionResult')
    if not isinstance(self.source_context, CanonicalVisualizationSourceContext):
      raise TypeError('source_context must be canonical visualization metadata')
    if self.result.metadata.capability != ENGINEERING_FLUX_SECTION_CAPABILITY:
      raise ValueError('flux-section result metadata identifies a different capability')
    if self.source_context.metadata != self.result.metadata:
      raise ValueError('flux-section source context must retain exact result metadata')
  ####

  @property
  def result_digest_sha256(self) -> str:
    return canonical_digest(self.result)
  ####

  @property
  def frame_id(self) -> str:
    return self.result.metadata.output_frame_id
  ####

  def model_dump(self) -> dict[str, Any]:
    result = self.result.model_dump(mode='json')
    return {
      'schema': 'plume.visualization.canonical.engineering-flux-series@1',
      'result_digest_sha256': self.result_digest_sha256,
      'request_digest_sha256': self.result.metadata.request_digest_sha256,
      'frame_id': self.frame_id,
      'snapshot_time_s': self.result.metadata.snapshot.time_s,
      'centerline_reference_id': self.result.request.centerline_reference_id,
      'requested_stations_m': list(self.result.request.centerline_arclength_m),
      'result': result,
      'source_context': self.source_context.model_dump(),
      'visualizer_interpolation_performed': False,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class CanonicalSpatialSupportData:
  """Display metadata for a support capability; no geometry is inferred."""

  support: SpatialSupport
  source_context: CanonicalVisualizationSourceContext | None = None

  def __post_init__(self) -> None:
    if not isinstance(self.support, SpatialSupport):
      raise TypeError('support must be a canonical SpatialSupport')
    ####
    if self.support.capability_id is not CapabilityId.SPATIAL_SUPPORT:
      raise ValueError('support metadata must identify the spatial-support capability')
    ####
    if self.support.major_version != SPATIAL_SUPPORT_CAPABILITY.major:
      raise ValueError('spatial-support payload major version is not supported by the canonical adapter')
    ####
    if self.source_context is not None:
      if not isinstance(self.source_context, CanonicalVisualizationSourceContext):
        raise TypeError('source_context must be canonical visualization metadata')
      ####
      if self.source_context.capability_id != SPATIAL_SUPPORT_CAPABILITY.wire_id:
        raise ValueError('source metadata must identify the canonical spatial-support capability')
      ####
    ####
  ####

  def payload_model_dump(self) -> dict[str, Any]:
    """Return only the capability payload, excluding its source context."""

    return {
      'schema': 'plume.visualization.canonical.spatial-support@1',
      'capability_id': self.support.capability_id.value,
      'major_version': self.support.major_version,
      'plume_frame_aabb_min_m': list(self.support.plume_frame_aabb_min_m),
      'plume_frame_aabb_max_m': list(self.support.plume_frame_aabb_max_m),
      'characteristic_extent_m': self.support.characteristic_extent_m,
      'support_definition': self.support.support_definition,
      'is_conservative': self.support.is_conservative,
    }
  ####

  def model_dump(self) -> dict[str, Any]:
    return {
      **self.payload_model_dump(),
      'source_context': (
        None if self.source_context is None else self.source_context.model_dump()
      ),
    }
  ####
####


@dataclass(frozen=True, slots=True)
class CanonicalProjectedAreaData:
  """Display metadata for projected-area support."""

  projected_area: ProjectedAreaCapability
  source_context: CanonicalVisualizationSourceContext | None = None

  def __post_init__(self) -> None:
    if not isinstance(self.projected_area, ProjectedAreaCapability):
      raise TypeError('projected_area must be a canonical ProjectedAreaCapability')
    ####
    if self.projected_area.capability_id is not CapabilityId.PROJECTED_AREA:
      raise ValueError('projected-area metadata must identify the projected-area capability')
    ####
    if self.projected_area.major_version != SPATIAL_PROJECTED_AREA_CAPABILITY.major:
      raise ValueError('projected-area payload major version is not supported by the canonical adapter')
    ####
    if self.source_context is not None:
      if not isinstance(self.source_context, CanonicalVisualizationSourceContext):
        raise TypeError('source_context must be canonical visualization metadata')
      ####
      if self.source_context.capability_id != SPATIAL_PROJECTED_AREA_CAPABILITY.wire_id:
        raise ValueError('source metadata must identify the canonical projected-area capability')
      ####
    ####
  ####

  def payload_model_dump(self) -> dict[str, Any]:
    """Return only the capability payload, excluding its source context."""

    return {
      'schema': 'plume.visualization.canonical.projected-area@1',
      'capability_id': self.projected_area.capability_id.value,
      'major_version': self.projected_area.major_version,
      'reference_area_m2': self.projected_area.reference_area_m2,
      'closed_zone_count': self.projected_area.closed_zone_count,
      'geometry_inferred': False,
    }
  ####

  def model_dump(self) -> dict[str, Any]:
    return {
      **self.payload_model_dump(),
      'source_context': (
        None if self.source_context is None else self.source_context.model_dump()
      ),
    }
  ####
####


@dataclass(frozen=True, slots=True)
class CanonicalSpectralIntensityLine:
  """One exact direction row from a canonical Signature result."""

  frame_id: str
  direction_index: int
  direction: tuple[float, float, float]
  wavelengths_m: tuple[float, ...]
  values_W_sr_m: tuple[float, ...]
  validity_mask: tuple[bool, ...]
  status: SampleStatus
  uncertainty_W_sr_m: tuple[float, ...] | None
  source_context: CanonicalVisualizationSourceContext

  def __post_init__(self) -> None:
    if self.direction_index < 0:
      raise ValueError('direction_index must be nonnegative')
    ####
    direction = _vector3(self.direction, 'direction')
    wavelengths = tuple(float(value) for value in self.wavelengths_m)
    values = tuple(float(value) for value in self.values_W_sr_m)
    validity = tuple(bool(value) for value in self.validity_mask)
    uncertainty = (
      None
      if self.uncertainty_W_sr_m is None
      else tuple(float(value) for value in self.uncertainty_W_sr_m)
    )
    if not (
      len(wavelengths) == len(values) == len(validity)
      and (uncertainty is None or len(uncertainty) == len(wavelengths))
    ):
      raise ValueError('canonical Signature line axes must match')
    ####
    if any(not isfinite(value) for value in (*wavelengths, *values)):
      raise ValueError('canonical Signature line values must be finite')
    ####
    if uncertainty is not None and any(
      not isfinite(value) or value < 0.0 for value in uncertainty
    ):
      raise ValueError('canonical Signature uncertainty must be finite and nonnegative')
    ####
    if not isinstance(self.status, SampleStatus):
      raise TypeError('canonical Signature line status must be typed')
    ####
    object.__setattr__(self, 'direction', direction)
    object.__setattr__(self, 'wavelengths_m', wavelengths)
    object.__setattr__(self, 'values_W_sr_m', values)
    object.__setattr__(self, 'validity_mask', validity)
    object.__setattr__(self, 'uncertainty_W_sr_m', uncertainty)
  ####
####


@dataclass(frozen=True, slots=True)
class CanonicalSpectralIntensityData:
  """Renderer-neutral Signature grid bound to its exact request axes."""

  request: SpectralSignatureRequest
  result: SpectralSignatureResult
  source_context: CanonicalVisualizationSourceContext
  lines: tuple[CanonicalSpectralIntensityLine, ...]

  def __post_init__(self) -> None:
    if not isinstance(self.request, SpectralSignatureRequest):
      raise TypeError('request must be a canonical SpectralSignatureRequest')
    ####
    if not isinstance(self.result, SpectralSignatureResult):
      raise TypeError('result must be a canonical SpectralSignatureResult')
    ####
    if not isinstance(self.source_context, CanonicalVisualizationSourceContext):
      raise TypeError('source_context must be canonical visualization metadata')
    ####
    if self.source_context.metadata != self.result.metadata:
      raise ValueError('Signature source context must retain result metadata')
    ####
    if self.result.metadata.request_digest_sha256 != canonical_digest(self.request):
      raise ValueError(
        'Signature result metadata must identify the exact visualization request'
      )
    ####
    if self.result.metadata.output_frame_id != self.request.direction_frame_id:
      raise ValueError('Signature request and result output frames must match')
    ####
    expected = len(self.request.source_to_observer_directions)
    if len(self.result.spectral_radiant_intensity) != expected:
      raise ValueError('Signature request and result direction axes must match')
    ####
    if any(
      len(row) != len(self.request.wavelengths_m)
      for row in (
        *self.result.spectral_radiant_intensity,
        *self.result.validity_mask,
      )
    ):
      raise ValueError('Signature request and result wavelength axes must match')
    ####
    if len(self.result.validity_mask) != expected or len(self.result.direction_status) != expected:
      raise ValueError('Signature result status and mask axes must match the request')
    ####
    lines = tuple(self.lines)
    if len(lines) != expected or any(
      line.source_context != self.source_context
      or line.frame_id != self.request.direction_frame_id
      or line.direction_index != index
      or line.direction != self.request.source_to_observer_directions[index]
      or line.wavelengths_m != self.request.wavelengths_m
      or line.values_W_sr_m != self.result.spectral_radiant_intensity[index]
      or line.validity_mask != self.result.validity_mask[index]
      or line.status != self.result.direction_status[index]
      or line.uncertainty_W_sr_m
      != (
        None
        if self.result.absolute_standard_uncertainty is None
        else self.result.absolute_standard_uncertainty[index]
      )
      for index, line in enumerate(lines)
    ):
      raise ValueError('Signature lines must match the request and exact result data')
    ####
    object.__setattr__(self, 'lines', lines)
  ####

  @property
  def frame_id(self) -> str:
    return self.request.direction_frame_id
  ####

  @property
  def directions(self) -> tuple[tuple[float, float, float], ...]:
    return self.request.source_to_observer_directions
  ####

  @property
  def wavelengths_m(self) -> tuple[float, ...]:
    return self.request.wavelengths_m
  ####

  def line_for_direction(self, direction_index: int) -> CanonicalSpectralIntensityLine:
    if direction_index < 0 or direction_index >= len(self.lines):
      raise IndexError(f'direction_index out of range: {direction_index}')
    ####
    return self.lines[direction_index]
  ####

  def model_dump(self) -> dict[str, Any]:
    return {
      'schema': 'plume.visualization.canonical.spectral-intensity@1',
      'frame_id': self.frame_id,
      'directions': [list(direction) for direction in self.directions],
      'wavelengths_m': list(self.wavelengths_m),
      'lines': [
        {
          'direction_index': line.direction_index,
          'direction': list(line.direction),
          'values_W_sr_m': list(line.values_W_sr_m),
          'validity_mask': list(line.validity_mask),
          'status': line.status.model_dump(mode='json'),
          'uncertainty_W_sr_m': (
            None
            if line.uncertainty_W_sr_m is None
            else list(line.uncertainty_W_sr_m)
          ),
        }
        for line in self.lines
      ],
      'source_context': self.source_context.model_dump(),
    }
  ####
####


@dataclass(frozen=True, slots=True)
class CanonicalSpectralRayTransferLine:
  """One exact ray row from a canonical ray-transfer result."""

  frame_id: str
  ray_index: int
  origin_m: tuple[float, float, float]
  direction: tuple[float, float, float]
  t_min_m: float
  t_max_m: float
  wavelengths_m: tuple[float, ...]
  source_spectral_radiance_W_m2_sr_m: tuple[float, ...]
  background_transmittance: tuple[float, ...]
  validity_mask: tuple[bool, ...]
  ray_status: SampleStatus
  hit: bool
  optical_depth: tuple[float, ...] | None
  plume_intersection_t_m: tuple[float, float] | None
  source_context: CanonicalVisualizationSourceContext
  absolute_standard_uncertainty_W_m2_sr_m: tuple[float | None, ...] | None = None

  def __post_init__(self) -> None:
    if self.ray_index < 0:
      raise ValueError('ray_index must be nonnegative')
    ####
    origin = _vector3(self.origin_m, 'origin_m')
    direction = _vector3(self.direction, 'direction')
    wavelengths = tuple(float(value) for value in self.wavelengths_m)
    source = tuple(float(value) for value in self.source_spectral_radiance_W_m2_sr_m)
    transmittance = tuple(float(value) for value in self.background_transmittance)
    validity = tuple(bool(value) for value in self.validity_mask)
    optical_depth = (
      None
      if self.optical_depth is None
      else tuple(float(value) for value in self.optical_depth)
    )
    uncertainty = (
      None
      if self.absolute_standard_uncertainty_W_m2_sr_m is None
      else tuple(
        None if value is None else float(value)
        for value in self.absolute_standard_uncertainty_W_m2_sr_m
      )
    )
    if not (
      len(wavelengths) == len(source) == len(transmittance) == len(validity)
      and (optical_depth is None or len(optical_depth) == len(wavelengths))
      and (uncertainty is None or len(uncertainty) == len(wavelengths))
    ):
      raise ValueError('canonical ray line axes must match')
    ####
    if not isfinite(self.t_min_m) or not isfinite(self.t_max_m) or self.t_min_m >= self.t_max_m:
      raise ValueError('canonical ray interval must be finite and ordered')
    ####
    if any(not isfinite(value) for value in (*wavelengths, *source, *transmittance)):
      raise ValueError('canonical ray line values must be finite')
    ####
    if optical_depth is not None and any(
      not isfinite(value) for value in optical_depth
    ):
      raise ValueError('canonical optical-depth values must be finite')
    ####
    if uncertainty is not None and any(
      value is not None and (not isfinite(value) or value < 0.0)
      for value in uncertainty
    ):
      raise ValueError(
        'canonical standard uncertainty must be finite and nonnegative'
      )
    ####
    if uncertainty is not None and any(
      not is_valid and value is not None
      for is_valid, value in zip(validity, uncertainty, strict=True)
    ):
      raise ValueError('invalid canonical ray samples must not report uncertainty')
    ####
    if not isinstance(self.ray_status, SampleStatus):
      raise TypeError('canonical ray status must be typed')
    ####
    object.__setattr__(self, 'origin_m', origin)
    object.__setattr__(self, 'direction', direction)
    object.__setattr__(self, 'wavelengths_m', wavelengths)
    object.__setattr__(self, 'source_spectral_radiance_W_m2_sr_m', source)
    object.__setattr__(self, 'background_transmittance', transmittance)
    object.__setattr__(self, 'validity_mask', validity)
    object.__setattr__(self, 'optical_depth', optical_depth)
    object.__setattr__(
      self,
      'absolute_standard_uncertainty_W_m2_sr_m',
      uncertainty,
    )
  ####
####


@dataclass(frozen=True, slots=True)
class CanonicalSpectralRayTransferData:
  """Renderer-neutral ray bundle bound to its exact request/result pair."""

  request: SpectralRayTransferRequest
  result: SpectralRayTransferResult
  source_context: CanonicalVisualizationSourceContext
  lines: tuple[CanonicalSpectralRayTransferLine, ...]

  def __post_init__(self) -> None:
    if not isinstance(self.request, SpectralRayTransferRequest):
      raise TypeError('request must be a canonical SpectralRayTransferRequest')
    ####
    if not isinstance(self.result, SpectralRayTransferResult):
      raise TypeError('result must be a canonical SpectralRayTransferResult')
    ####
    if not isinstance(self.source_context, CanonicalVisualizationSourceContext):
      raise TypeError('source_context must be canonical visualization metadata')
    ####
    if self.source_context.metadata != self.result.metadata:
      raise ValueError('ray source context must retain result metadata')
    ####
    if self.result.metadata.request_digest_sha256 != canonical_digest(self.request):
      raise ValueError(
        'ray result metadata must identify the exact visualization request'
      )
    ####
    if self.result.metadata.output_frame_id != self.request.ray_frame_id:
      raise ValueError('ray request and result output frames must match')
    ####
    if len(self.result.source_spectral_radiance) != len(self.request.ray_origins_m):
      raise ValueError('ray request and result ray axes must match')
    ####
    ray_count = len(self.request.ray_origins_m)
    wavelength_count = len(self.request.wavelengths_m)
    if len(self.result.background_transmittance) != ray_count or len(self.result.validity_mask) != ray_count:
      raise ValueError('ray result matrices must match the request ray axes')
    ####
    if any(
      len(row) != wavelength_count
      for row in (
        *self.result.source_spectral_radiance,
        *self.result.background_transmittance,
        *self.result.validity_mask,
      )
    ):
      raise ValueError('ray request and result wavelength axes must match')
    ####
    if len(self.result.ray_status) != ray_count or len(self.result.hit_mask) != ray_count:
      raise ValueError('ray status and hit-mask axes must match the request')
    ####
    lines = tuple(self.lines)
    if len(lines) != len(self.request.ray_origins_m) or any(
      line.source_context != self.source_context
      or line.frame_id != self.request.ray_frame_id
      or line.ray_index != index
      or line.origin_m != self.request.ray_origins_m[index]
      or line.direction != self.request.ray_directions[index]
      or line.t_min_m != self.request.ray_t_min_m[index]
      or line.t_max_m != self.request.ray_t_max_m[index]
      or line.wavelengths_m != self.request.wavelengths_m
      or line.source_spectral_radiance_W_m2_sr_m
      != self.result.source_spectral_radiance[index]
      or line.background_transmittance
      != self.result.background_transmittance[index]
      or line.validity_mask != self.result.validity_mask[index]
      or line.absolute_standard_uncertainty_W_m2_sr_m
      != (
        None
        if self.result.absolute_standard_uncertainty is None
        else self.result.absolute_standard_uncertainty[index]
      )
      or line.ray_status != self.result.ray_status[index]
      or line.hit != self.result.hit_mask[index]
      or line.optical_depth
      != (
        None
        if self.result.optical_depth is None
        else self.result.optical_depth[index]
      )
      or line.plume_intersection_t_m
      != (
        None
        if self.result.plume_intersection_t_m is None
        else self.result.plume_intersection_t_m[index]
      )
      for index, line in enumerate(lines)
    ):
      raise ValueError('ray lines must match the request and exact result data')
    ####
    object.__setattr__(self, 'lines', lines)
  ####

  @property
  def frame_id(self) -> str:
    return self.request.ray_frame_id
  ####

  @property
  def wavelengths_m(self) -> tuple[float, ...]:
    return self.request.wavelengths_m
  ####

  def line_for_ray(self, ray_index: int) -> CanonicalSpectralRayTransferLine:
    if ray_index < 0 or ray_index >= len(self.lines):
      raise IndexError(f'ray_index out of range: {ray_index}')
    ####
    return self.lines[ray_index]
  ####

  def model_dump(self) -> dict[str, Any]:
    return {
      'schema': 'plume.visualization.canonical.spectral-ray-transfer@1',
      'frame_id': self.frame_id,
      'wavelengths_m': list(self.wavelengths_m),
      'lines': [
        {
          'ray_index': line.ray_index,
          'origin_m': list(line.origin_m),
          'direction': list(line.direction),
          't_min_m': line.t_min_m,
          't_max_m': line.t_max_m,
          'source_spectral_radiance_W_m2_sr_m': list(
            line.source_spectral_radiance_W_m2_sr_m
          ),
          'absolute_standard_uncertainty_W_m2_sr_m': (
            None
            if line.absolute_standard_uncertainty_W_m2_sr_m is None
            else list(line.absolute_standard_uncertainty_W_m2_sr_m)
          ),
          'background_transmittance': list(line.background_transmittance),
          'validity_mask': list(line.validity_mask),
          'ray_status': line.ray_status.model_dump(mode='json'),
          'hit': line.hit,
          'optical_depth': (
            None if line.optical_depth is None else list(line.optical_depth)
          ),
          'plume_intersection_t_m': (
            None
            if line.plume_intersection_t_m is None
            else list(line.plume_intersection_t_m)
          ),
        }
        for line in self.lines
      ],
      'source_context': self.source_context.model_dump(),
    }
  ####
####


@dataclass(frozen=True, slots=True)
class CanonicalFpaVisualizationData:
  """Canonical wrapper for a source-bound FPA renderer projection."""

  view_spec: FpaVisualizationSpec
  projection: FpaViewProjection

  def __post_init__(self) -> None:
    from exhaust_plume.validation.fpa_visualization import (
      FpaViewProjection,
      FpaVisualizationSpec,
    )

    if not isinstance(self.view_spec, FpaVisualizationSpec):
      raise TypeError('view_spec must be an FpaVisualizationSpec')
    ####
    if not isinstance(self.projection, FpaViewProjection):
      raise TypeError('projection must be an FpaViewProjection')
    ####
    if self.projection.source != self.view_spec.source:
      raise ValueError('FPA projection and view spec must retain the same source')
    ####
    if self.projection.input_content_sha256 != self.view_spec.input_content_sha256:
      raise ValueError('FPA projection and view spec must bind the same input content')
    ####
    if self.projection.view_spec_digest_sha256 != self.view_spec.digest_sha256():
      raise ValueError('FPA projection must retain the exact view spec identity')
    ####
  ####

  def model_dump(self) -> dict[str, Any]:
    """Include exact FPA view identity and its renderer-neutral projection."""

    return {
      'schema': 'plume.visualization.canonical.fpa@1',
      'view_spec': self.view_spec.model_dump(mode='json'),
      'view_spec_digest_sha256': self.view_spec.digest_sha256(),
      'projection': self.projection.model_dump(),
    }
  ####
####


CanonicalProductVisualizationData: TypeAlias = (
  CanonicalVisualSectionedTubeData
  | CanonicalSpectralIntensityData
  | CanonicalSpectralRayTransferData
  | CanonicalFpaVisualizationData
)
CanonicalSpatialVisualizationData: TypeAlias = (
  CanonicalAxisymmetricZoneFieldData
  | CanonicalSpatialLocalFieldData
  | CanonicalSpatialSupportData
  | CanonicalProjectedAreaData
)
CanonicalSupportingVisualizationData: TypeAlias = (
  CanonicalSpatialVisualizationData
  | CanonicalEngineeringFluxSectionData
  | CanonicalEngineeringFluxSeriesData
  | ModelLaneVisualizationResult
  | SpectralRadianceImageResult
)
CanonicalVisualizationData: TypeAlias = (
  CanonicalProductVisualizationData | CanonicalSupportingVisualizationData
)


def extract_visual_sectioned_tube_data(
  result: VisualSectionedTubeResult,
) -> CanonicalVisualSectionedTubeData:
  """Adapt canonical visual geometry without changing its frame or claims."""

  if not isinstance(result, VisualSectionedTubeResult):
    raise TypeError('result must be a canonical VisualSectionedTubeResult')
  ####
  context = CanonicalVisualizationSourceContext(result.metadata)
  return CanonicalVisualSectionedTubeData(
    source_context=context,
    sections=tuple(result.sections),
    channels=tuple(
      (name, tuple(values))
      for name, values in sorted(result.channels.items())
    ),
    visual_bounds=result.visual_bounds,
    summary=result.summary,
  )
####


def extract_axisymmetric_zone_field_data(
  field: AxisymmetricZoneField,
) -> CanonicalAxisymmetricZoneFieldData:
  """Adapt finite zone polygons; do not infer a continuous medium."""

  if not isinstance(field, AxisymmetricZoneField):
    raise TypeError('field must be a canonical AxisymmetricZoneField')
  ####
  return CanonicalAxisymmetricZoneFieldData(
    zones=tuple(CanonicalAxisymmetricZoneData.from_zone(zone) for zone in field.zones),
    axis_definition=field.axis_definition,
    capability_id=field.capability_id,
    major_version=field.major_version,
  )
####


def extract_axisymmetric_zone_result_data(
  result: AxisymmetricZoneFieldResult,
) -> CanonicalAxisymmetricZoneFieldData:
  """Adapt a source-bound zone result while retaining its exact metadata."""

  if not isinstance(result, AxisymmetricZoneFieldResult):
    raise TypeError('result must be a canonical AxisymmetricZoneFieldResult')
  ####
  return CanonicalAxisymmetricZoneFieldData(
    zones=tuple(
      CanonicalAxisymmetricZoneData.from_result_zone(zone)
      for zone in result.zones
    ),
    axis_definition=result.axis_definition,
    capability_id=CapabilityId.AXISYMMETRIC_ZONE_FIELD,
    major_version=result.metadata.capability.major,
    source_context=CanonicalVisualizationSourceContext(result.metadata),
  )
####


def extract_spatial_local_field_data(
  result: SpatialLocalFieldResult,
) -> CanonicalSpatialLocalFieldData:
  """Adapt exact point samples without creating a continuous field."""

  if not isinstance(result, SpatialLocalFieldResult):
    raise TypeError('result must be a canonical SpatialLocalFieldResult')
  return CanonicalSpatialLocalFieldData(
    result=result,
    source_context=CanonicalVisualizationSourceContext(result.metadata),
  )
####


def extract_engineering_flux_section_data(
  section: PlumeFluxSection,
) -> CanonicalEngineeringFluxSectionData:
  """Adapt exact handoff quantities without creating visual geometry."""

  if not isinstance(section, PlumeFluxSection):
    raise TypeError('section must be a canonical PlumeFluxSection')
  ####
  return CanonicalEngineeringFluxSectionData(section=section)
####


def extract_engineering_flux_series_data(
    result: EngineeringFluxSectionResult,
) -> CanonicalEngineeringFluxSeriesData:
  """Adapt ordered source-bound sections without inferring between stations."""

  if not isinstance(result, EngineeringFluxSectionResult):
    raise TypeError('result must be a canonical EngineeringFluxSectionResult')
  return CanonicalEngineeringFluxSeriesData(
    result=result,
    source_context=CanonicalVisualizationSourceContext(result.metadata),
  )
####


def extract_spatial_support_data(
  support: SpatialSupport | SpatialSupportResult,
  *,
  source_context: CanonicalVisualizationSourceContext | None = None,
) -> CanonicalSpatialSupportData:
  """Adapt conservative support metadata without creating a mesh.

  Canonical results carry their own source metadata. For legacy payloads,
  ``source_context`` can bind exact metadata explicitly; calls without it
  remain payload-only and carry no provider/snapshot lineage.
  """

  if isinstance(support, SpatialSupportResult):
    if source_context is not None:
      raise TypeError('source_context is already carried by SpatialSupportResult')
    ####
    return CanonicalSpatialSupportData(
      support=SpatialSupport(
        plume_frame_aabb_min_m=support.plume_frame_aabb_min_m,
        plume_frame_aabb_max_m=support.plume_frame_aabb_max_m,
        characteristic_extent_m=support.characteristic_extent_m,
        support_definition=support.support_definition,
        is_conservative=support.is_conservative,
      ),
      source_context=CanonicalVisualizationSourceContext(support.metadata),
    )
  ####
  return CanonicalSpatialSupportData(support=support, source_context=source_context)
####


def extract_projected_area_data(
  projected_area: ProjectedAreaCapability | ProjectedAreaResult,
  *,
  source_context: CanonicalVisualizationSourceContext | None = None,
) -> CanonicalProjectedAreaData:
  """Adapt projected-area metadata without treating it as plume geometry.

  Canonical results carry their own source metadata. For legacy payloads,
  ``source_context`` can bind exact metadata explicitly; calls without it
  remain payload-only and carry no provider/snapshot lineage.
  """

  if isinstance(projected_area, ProjectedAreaResult):
    if source_context is not None:
      raise TypeError('source_context is already carried by ProjectedAreaResult')
    ####
    return CanonicalProjectedAreaData(
      projected_area=ProjectedAreaCapability(
        reference_area_m2=projected_area.reference_area_m2,
        closed_zone_count=projected_area.closed_zone_count,
      ),
      source_context=CanonicalVisualizationSourceContext(projected_area.metadata),
    )
  ####
  return CanonicalProjectedAreaData(
    projected_area=projected_area,
    source_context=source_context,
  )
####


def extract_spectral_signature_data(
  request: SpectralSignatureRequest,
  result: SpectralSignatureResult,
) -> CanonicalSpectralIntensityData:
  """Adapt a canonical Signature result while retaining exact request axes."""

  if not isinstance(request, SpectralSignatureRequest):
    raise TypeError('request must be a canonical SpectralSignatureRequest')
  ####
  if not isinstance(result, SpectralSignatureResult):
    raise TypeError('result must be a canonical SpectralSignatureResult')
  ####
  direction_count = len(request.source_to_observer_directions)
  wavelength_count = len(request.wavelengths_m)
  if len(result.spectral_radiant_intensity) != direction_count:
    raise ValueError('Signature request and result direction axes must match')
  ####
  if len(result.validity_mask) != direction_count or len(result.direction_status) != direction_count:
    raise ValueError('Signature result status and mask axes must match the request')
  ####
  if any(
    len(row) != wavelength_count
    for row in (*result.spectral_radiant_intensity, *result.validity_mask)
  ):
    raise ValueError('Signature request and result wavelength axes must match')
  ####
  if result.absolute_standard_uncertainty is not None:
    if len(result.absolute_standard_uncertainty) != direction_count or any(
      len(row) != wavelength_count
      for row in result.absolute_standard_uncertainty
    ):
      raise ValueError('Signature uncertainty axes must match the request')
    ####
  ####
  context = CanonicalVisualizationSourceContext(result.metadata)
  uncertainty = result.absolute_standard_uncertainty
  lines = tuple(
    CanonicalSpectralIntensityLine(
      frame_id=request.direction_frame_id,
      direction_index=index,
      direction=request.source_to_observer_directions[index],
      wavelengths_m=request.wavelengths_m,
      values_W_sr_m=result.spectral_radiant_intensity[index],
      validity_mask=result.validity_mask[index],
      status=result.direction_status[index],
      uncertainty_W_sr_m=(
        None if uncertainty is None else uncertainty[index]
      ),
      source_context=context,
    )
    for index in range(len(request.source_to_observer_directions))
  )
  return CanonicalSpectralIntensityData(
    request=request,
    result=result,
    source_context=context,
    lines=lines,
  )
####


def extract_spectral_ray_transfer_data(
  request: SpectralRayTransferRequest,
  result: SpectralRayTransferResult,
) -> CanonicalSpectralRayTransferData:
  """Adapt canonical ray transfer with intervals, hits, and masks intact."""

  if not isinstance(request, SpectralRayTransferRequest):
    raise TypeError('request must be a canonical SpectralRayTransferRequest')
  ####
  if not isinstance(result, SpectralRayTransferResult):
    raise TypeError('result must be a canonical SpectralRayTransferResult')
  ####
  ray_count = len(request.ray_origins_m)
  wavelength_count = len(request.wavelengths_m)
  if len(result.source_spectral_radiance) != ray_count:
    raise ValueError('ray request and result ray axes must match')
  ####
  if len(result.ray_status) != ray_count or len(result.hit_mask) != ray_count:
    raise ValueError('ray status and hit-mask axes must match the request')
  ####
  if any(
    len(row) != wavelength_count
    for row in (
      *result.source_spectral_radiance,
      *result.background_transmittance,
      *result.validity_mask,
    )
  ):
    raise ValueError('ray request and result wavelength axes must match')
  ####
  if result.optical_depth is not None and (
    len(result.optical_depth) != ray_count
    or any(len(row) != wavelength_count for row in result.optical_depth)
  ):
    raise ValueError('ray optical-depth axes must match the request')
  ####
  if result.plume_intersection_t_m is not None and len(result.plume_intersection_t_m) != ray_count:
    raise ValueError('ray intersection axes must match the request')
  ####
  context = CanonicalVisualizationSourceContext(result.metadata)
  lines = tuple(
    CanonicalSpectralRayTransferLine(
      frame_id=request.ray_frame_id,
      ray_index=index,
      origin_m=request.ray_origins_m[index],
      direction=request.ray_directions[index],
      t_min_m=request.ray_t_min_m[index],
      t_max_m=request.ray_t_max_m[index],
      wavelengths_m=request.wavelengths_m,
      source_spectral_radiance_W_m2_sr_m=result.source_spectral_radiance[index],
      absolute_standard_uncertainty_W_m2_sr_m=(
        None
        if result.absolute_standard_uncertainty is None
        else result.absolute_standard_uncertainty[index]
      ),
      background_transmittance=result.background_transmittance[index],
      validity_mask=result.validity_mask[index],
      ray_status=result.ray_status[index],
      hit=result.hit_mask[index],
      optical_depth=(
        None if result.optical_depth is None else result.optical_depth[index]
      ),
      plume_intersection_t_m=(
        None
        if result.plume_intersection_t_m is None
        else result.plume_intersection_t_m[index]
      ),
      source_context=context,
    )
    for index in range(len(request.ray_origins_m))
  )
  return CanonicalSpectralRayTransferData(
    request=request,
    result=result,
    source_context=context,
    lines=lines,
  )
####


def extract_fpa_visualization_data(
  inputs: FpaVisualizationInput,
  *,
  view_spec: FpaVisualizationSpec,
) -> CanonicalFpaVisualizationData:
  """Adapt an FPA frame and its exact view request for shared renderers."""

  from exhaust_plume.validation.fpa_visualization import (
    FpaVisualizationInput,
    FpaVisualizationSpec,
    project_fpa_view,
  )

  if not isinstance(inputs, FpaVisualizationInput):
    raise TypeError('inputs must be an FpaVisualizationInput')
  ####
  if not isinstance(view_spec, FpaVisualizationSpec):
    raise TypeError('view_spec must be an FpaVisualizationSpec')
  ####
  return CanonicalFpaVisualizationData(
    view_spec=view_spec,
    projection=project_fpa_view(inputs, view_spec),
  )
####


def extract_canonical_product_visualization_data(
  result: VisualSectionedTubeResult | SpectralSignatureResult | SpectralRayTransferResult,
  *,
  request: SpectralSignatureRequest | SpectralRayTransferRequest | None = None,
) -> CanonicalProductVisualizationData:
  """Dispatch a canonical primary product to its typed visual data."""

  if isinstance(result, VisualSectionedTubeResult):
    if request is not None:
      raise TypeError('visual geometry does not consume a spectral request')
    ####
    return extract_visual_sectioned_tube_data(result)
  ####
  if isinstance(result, SpectralSignatureResult):
    if not isinstance(request, SpectralSignatureRequest):
      raise TypeError('Signature visualization requires its exact request')
    ####
    return extract_spectral_signature_data(request, result)
  ####
  if isinstance(result, SpectralRayTransferResult):
    if not isinstance(request, SpectralRayTransferRequest):
      raise TypeError('ray visualization requires its exact request')
    ####
    return extract_spectral_ray_transfer_data(request, result)
  ####
  raise TypeError('result must be a canonical primary product result')
####


def extract_canonical_visualization_data(
  value: object,
  *,
  request: SpectralSignatureRequest | SpectralRayTransferRequest | None = None,
  fpa_view_spec: FpaVisualizationSpec | None = None,
  source_context: CanonicalVisualizationSourceContext | None = None,
) -> CanonicalVisualizationData:
  """Dispatch canonical product/supporting data with no inference.

  FPA frames require their exact ``FpaVisualizationSpec`` through
  ``fpa_view_spec`` so selection, layer, and display policy remain explicit.
  Supporting spatial capabilities may receive exact result metadata through
  ``source_context``; all other adapters already retain their result metadata
  or explicitly carry no source context.
  """

  if source_context is not None:
    if not isinstance(source_context, CanonicalVisualizationSourceContext):
      raise TypeError('source_context must be canonical visualization metadata')
    ####
    if not isinstance(value, (SpatialSupport, ProjectedAreaCapability)):
      raise TypeError('source_context is only accepted for spatial-support or projected-area capabilities')
    ####
  ####

  if isinstance(value, PlumeFluxSection):
    if request is not None or fpa_view_spec is not None:
      raise TypeError('engineering flux does not consume a product visualization request')
    ####
    return extract_engineering_flux_section_data(value)
  ####

  if isinstance(value, EngineeringFluxSectionResult):
    if request is not None or fpa_view_spec is not None or source_context is not None:
      raise TypeError('engineering flux results already carry their exact request and source metadata')
    return extract_engineering_flux_series_data(value)
  ####

  if isinstance(value, ModelLaneVisualizationResult):
    if request is not None or fpa_view_spec is not None or source_context is not None:
      raise TypeError('model-lane visualization results already carry exact source metadata')
    ####
    return value
  ####

  if isinstance(value, SpectralRadianceImageResult):
    if request is not None or fpa_view_spec is not None or source_context is not None:
      raise TypeError(
        'spectral-radiance image results already carry exact source axes and metadata'
      )
    ####
    return value
  ####

  if isinstance(value, (SpatialSupport, SpatialSupportResult)):
    if request is not None or fpa_view_spec is not None:
      raise TypeError('spatial support does not consume a product visualization request')
    ####
    return extract_spatial_support_data(value, source_context=source_context)
  ####
  if isinstance(value, (ProjectedAreaCapability, ProjectedAreaResult)):
    if request is not None or fpa_view_spec is not None:
      raise TypeError('projected area does not consume a product visualization request')
    ####
    return extract_projected_area_data(value, source_context=source_context)
  ####
  if isinstance(value, AxisymmetricZoneField):
    if request is not None or fpa_view_spec is not None:
      raise TypeError('zone fields do not consume a product visualization request')
    ####
    return extract_axisymmetric_zone_field_data(value)
  ####
  if isinstance(value, AxisymmetricZoneFieldResult):
    if request is not None or fpa_view_spec is not None or source_context is not None:
      raise TypeError('source-bound zone results retain their own metadata and do not take view requests')
    ####
    return extract_axisymmetric_zone_result_data(value)
  ####
  if isinstance(value, SpatialLocalFieldResult):
    if request is not None or fpa_view_spec is not None or source_context is not None:
      raise TypeError('source-bound local-field results retain their own metadata and query axes')
    return extract_spatial_local_field_data(value)
  ####
  if isinstance(value, AxisymmetricZone):
    if request is not None or fpa_view_spec is not None:
      raise TypeError('zone geometry does not consume a product visualization request')
    ####
    return extract_axisymmetric_zone_field_data(AxisymmetricZoneField(zones=(value,)))
  ####
  from exhaust_plume.validation.fpa_visualization import FpaVisualizationInput

  if isinstance(value, FpaVisualizationInput):
    if request is not None:
      raise TypeError('FPA visualization does not consume a spectral product request')
    ####
    if fpa_view_spec is None:
      raise TypeError('FPA visualization requires its exact view spec')
    ####
    return extract_fpa_visualization_data(value, view_spec=fpa_view_spec)
  ####
  if fpa_view_spec is not None:
    raise TypeError('fpa_view_spec is only supported for FPA visualization')
  ####
  return extract_canonical_product_visualization_data(value, request=request)  # type: ignore[arg-type]
####
