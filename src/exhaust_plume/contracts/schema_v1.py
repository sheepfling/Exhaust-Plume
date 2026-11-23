"""Schema registry and deterministic JSON Schema export for public v1 DTOs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Type

from pydantic import BaseModel

from exhaust_plume.contracts.common_v1 import ProviderDescriptor, ResultMetadata
from exhaust_plume.contracts.ray_transfer_v1 import SpectralRayTransferRequest, SpectralRayTransferResult
from exhaust_plume.contracts.signature_v1 import SpectralSignatureRequest, SpectralSignatureResult
from exhaust_plume.contracts.spatial_v1 import (
  AxisymmetricZoneFieldRequest,
  AxisymmetricZoneFieldResult,
  ProjectedAreaRequest,
  ProjectedAreaResult,
  SpatialSupportRequest,
  SpatialSupportResult,
)
from exhaust_plume.contracts.model_lane_visualization_v1 import (
  ModelLaneVisualizationRequest,
  ModelLaneVisualizationResult,
)
from exhaust_plume.contracts.visual_v1 import VisualSectionedTubeRequest, VisualSectionedTubeResult
from exhaust_plume.contracts.spectral_radiance_image_v1 import (
  SpectralRadianceImageRequest,
  SpectralRadianceImageResult,
)
from exhaust_plume.contracts.local_field_v1 import (
  SpatialLocalFieldRequest,
  SpatialLocalFieldResult,
)
from exhaust_plume.contracts.handoff_v1 import PlumeFluxSectionV1
from exhaust_plume.contracts.engineering_flux_v1 import (
  EngineeringFluxSectionRequest,
  EngineeringFluxSectionResult,
)

PUBLIC_CONTRACT_MODELS: tuple[tuple[str, Type[BaseModel]], ...] = (
  ('provider_descriptor_v1', ProviderDescriptor),
  ('result_metadata_v1', ResultMetadata),
  ('visual_sectioned_tube_v1', VisualSectionedTubeRequest),
  ('visual_sectioned_tube_result_v1', VisualSectionedTubeResult),
  ('model_lane_visualization_v1', ModelLaneVisualizationRequest),
  ('model_lane_visualization_result_v1', ModelLaneVisualizationResult),
  ('spectral_signature_v1', SpectralSignatureRequest),
  ('spectral_signature_result_v1', SpectralSignatureResult),
  ('spectral_ray_transfer_v1', SpectralRayTransferRequest),
  ('spectral_ray_transfer_result_v1', SpectralRayTransferResult),
  ('axisymmetric_zone_field_v1', AxisymmetricZoneFieldRequest),
  ('axisymmetric_zone_field_result_v1', AxisymmetricZoneFieldResult),
  ('spatial_support_v1', SpatialSupportRequest),
  ('spatial_support_result_v1', SpatialSupportResult),
  ('projected_area_v1', ProjectedAreaRequest),
  ('projected_area_result_v1', ProjectedAreaResult),
  ('spectral_radiance_image_v1', SpectralRadianceImageRequest),
  ('spectral_radiance_image_result_v1', SpectralRadianceImageResult),
  ('spatial_local_field_v1', SpatialLocalFieldRequest),
  ('spatial_local_field_result_v1', SpatialLocalFieldResult),
  ('plume_flux_section_v1', PlumeFluxSectionV1),
  ('engineering_flux_section_v1', EngineeringFluxSectionRequest),
  ('engineering_flux_section_result_v1', EngineeringFluxSectionResult),
)


def export_public_schemas(directory: str | Path) -> tuple[Path, ...]:
  """Write the public schema registry and return the generated paths."""

  output_directory = Path(directory)
  output_directory.mkdir(parents=True, exist_ok=True)
  generated: list[Path] = []
  for name, model in PUBLIC_CONTRACT_MODELS:
    path = output_directory / f'{name}.schema.json'
    path.write_text(
      json.dumps(model.model_json_schema(), indent=2, sort_keys=True) + '\n',
      encoding='utf-8',
    )
    generated.append(path)
  ####
  return tuple(generated)
####


__all__ = ('PUBLIC_CONTRACT_MODELS', 'export_public_schemas')
