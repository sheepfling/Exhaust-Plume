"""Capability specifications for the three primary v1 products."""

from __future__ import annotations

from types import MappingProxyType
from typing import Any, Mapping

from exhaust_plume.contracts.lifecycle_v1 import CapabilitySpec
from exhaust_plume.contracts.common_v1 import CapabilityIdentity
from exhaust_plume.contracts.errors import (
  UnsupportedProductCapabilityError,
  UnsupportedProductVersionError,
)
from exhaust_plume.contracts.ray_transfer_v1 import (
  SPECTRAL_RAY_TRANSFER_CAPABILITY,
  SpectralRayTransferRequest,
  SpectralRayTransferResult,
)
from exhaust_plume.contracts.signature_v1 import (
  SPECTRAL_RADIANT_INTENSITY_CAPABILITY,
  SpectralSignatureRequest,
  SpectralSignatureResult,
)
from exhaust_plume.contracts.spatial_v1 import (
  AxisymmetricZoneFieldRequest,
  AxisymmetricZoneFieldResult,
  ProjectedAreaRequest,
  ProjectedAreaResult,
  SpatialSupportRequest,
  SpatialSupportResult,
)
from exhaust_plume.contracts.local_field_v1 import SpatialLocalFieldRequest, SpatialLocalFieldResult
from exhaust_plume.contracts.engineering_flux_v1 import (
  EngineeringFluxSectionRequest,
  EngineeringFluxSectionResult,
)
from exhaust_plume.contracts.model_lane_visualization_v1 import (
  MODEL_LANE_VISUALIZATION_CAPABILITY,
  ModelLaneVisualizationRequest,
  ModelLaneVisualizationResult,
)
from exhaust_plume.contracts.capability import (
  ENGINEERING_FLUX_SECTION_CAPABILITY,
  IMAGE_SPECTRAL_RADIANCE_CAPABILITY,
  SPATIAL_AXISYMMETRIC_ZONE_FIELD_CAPABILITY,
  SPATIAL_PROJECTED_AREA_CAPABILITY,
  SPATIAL_SUPPORT_CAPABILITY,
  SPATIAL_LOCAL_FIELD_CAPABILITY,
)
from exhaust_plume.contracts.spectral_radiance_image_v1 import (
  SpectralRadianceImageRequest,
  SpectralRadianceImageResult,
)
from exhaust_plume.contracts.visual_v1 import (
  VISUAL_SECTIONED_TUBE_CAPABILITY,
  VisualSectionedTubeRequest,
  VisualSectionedTubeResult,
)

VISUAL_SECTIONED_TUBE_V1 = CapabilitySpec(
  capability=VISUAL_SECTIONED_TUBE_CAPABILITY,
  request_type=VisualSectionedTubeRequest,
  result_type=VisualSectionedTubeResult,
)

SPECTRAL_RADIANT_INTENSITY_V1 = CapabilitySpec(
  capability=SPECTRAL_RADIANT_INTENSITY_CAPABILITY,
  request_type=SpectralSignatureRequest,
  result_type=SpectralSignatureResult,
)

SPECTRAL_RAY_TRANSFER_V1 = CapabilitySpec(
  capability=SPECTRAL_RAY_TRANSFER_CAPABILITY,
  request_type=SpectralRayTransferRequest,
  result_type=SpectralRayTransferResult,
)

SPATIAL_SUPPORT_V1 = CapabilitySpec(
  capability=SPATIAL_SUPPORT_CAPABILITY,
  request_type=SpatialSupportRequest,
  result_type=SpatialSupportResult,
)

SPATIAL_AXISYMMETRIC_ZONE_FIELD_V1 = CapabilitySpec(
  capability=SPATIAL_AXISYMMETRIC_ZONE_FIELD_CAPABILITY,
  request_type=AxisymmetricZoneFieldRequest,
  result_type=AxisymmetricZoneFieldResult,
)

SPATIAL_PROJECTED_AREA_V1 = CapabilitySpec(
  capability=SPATIAL_PROJECTED_AREA_CAPABILITY,
  request_type=ProjectedAreaRequest,
  result_type=ProjectedAreaResult,
)

MODEL_LANE_VISUALIZATION_V1 = CapabilitySpec(
  capability=MODEL_LANE_VISUALIZATION_CAPABILITY,
  request_type=ModelLaneVisualizationRequest,
  result_type=ModelLaneVisualizationResult,
)

IMAGE_SPECTRAL_RADIANCE_V1 = CapabilitySpec(
  capability=IMAGE_SPECTRAL_RADIANCE_CAPABILITY,
  request_type=SpectralRadianceImageRequest,
  result_type=SpectralRadianceImageResult,
)

SPATIAL_LOCAL_FIELD_V1 = CapabilitySpec(
  capability=SPATIAL_LOCAL_FIELD_CAPABILITY,
  request_type=SpatialLocalFieldRequest,
  result_type=SpatialLocalFieldResult,
)

ENGINEERING_FLUX_SECTION_V1 = CapabilitySpec(
  capability=ENGINEERING_FLUX_SECTION_CAPABILITY,
  request_type=EngineeringFluxSectionRequest,
  result_type=EngineeringFluxSectionResult,
)

PRIMARY_PRODUCT_CAPABILITY_SPECS: Mapping[str, CapabilitySpec[Any, Any]] = MappingProxyType({
  VISUAL_SECTIONED_TUBE_V1.capability.wire_id: VISUAL_SECTIONED_TUBE_V1,
  SPECTRAL_RADIANT_INTENSITY_V1.capability.wire_id: SPECTRAL_RADIANT_INTENSITY_V1,
  SPECTRAL_RAY_TRANSFER_V1.capability.wire_id: SPECTRAL_RAY_TRANSFER_V1,
})

SUPPORTING_CAPABILITY_SPECS: Mapping[str, CapabilitySpec[Any, Any]] = MappingProxyType({
  MODEL_LANE_VISUALIZATION_V1.capability.wire_id: MODEL_LANE_VISUALIZATION_V1,
  SPATIAL_AXISYMMETRIC_ZONE_FIELD_V1.capability.wire_id: SPATIAL_AXISYMMETRIC_ZONE_FIELD_V1,
  SPATIAL_SUPPORT_V1.capability.wire_id: SPATIAL_SUPPORT_V1,
  SPATIAL_PROJECTED_AREA_V1.capability.wire_id: SPATIAL_PROJECTED_AREA_V1,
  IMAGE_SPECTRAL_RADIANCE_V1.capability.wire_id: IMAGE_SPECTRAL_RADIANCE_V1,
  SPATIAL_LOCAL_FIELD_V1.capability.wire_id: SPATIAL_LOCAL_FIELD_V1,
  ENGINEERING_FLUX_SECTION_V1.capability.wire_id: ENGINEERING_FLUX_SECTION_V1,
})


def get_product_capability_spec(
    capability: CapabilityIdentity | str,
) -> CapabilitySpec[Any, Any]:
  """Resolve one supported v1 product or raise a typed negotiation error."""

  identity = CapabilityIdentity.parse(capability) if isinstance(capability, str) else capability
  try:
    return PRIMARY_PRODUCT_CAPABILITY_SPECS[identity.wire_id]
  except KeyError as error:
    if any(candidate.split('@', 1)[0] == identity.name for candidate in PRIMARY_PRODUCT_CAPABILITY_SPECS):
      raise UnsupportedProductVersionError(
        f'unsupported major version for {identity.name}: {identity.major}'
      ) from error
    ####
    raise UnsupportedProductCapabilityError(
      f'unsupported capability: {identity.wire_id}'
    ) from error
  ####
####


def get_supporting_capability_spec(
    capability: CapabilityIdentity | str,
) -> CapabilitySpec[Any, Any]:
  """Resolve a supporting spatial v1 result capability."""

  identity = CapabilityIdentity.parse(capability) if isinstance(capability, str) else capability
  try:
    return SUPPORTING_CAPABILITY_SPECS[identity.wire_id]
  except KeyError as error:
    if any(candidate.split('@', 1)[0] == identity.name for candidate in SUPPORTING_CAPABILITY_SPECS):
      raise UnsupportedProductVersionError(
        f'unsupported major version for {identity.name}: {identity.major}'
      ) from error
    ####
    raise UnsupportedProductCapabilityError(
      f'unsupported supporting capability: {identity.wire_id}'
    ) from error
  ####
####

__all__ = (
  'PRIMARY_PRODUCT_CAPABILITY_SPECS',
  'SPATIAL_AXISYMMETRIC_ZONE_FIELD_V1',
  'SPATIAL_PROJECTED_AREA_V1',
  'SPATIAL_SUPPORT_V1',
  'SPATIAL_LOCAL_FIELD_V1',
  'ENGINEERING_FLUX_SECTION_V1',
  'SUPPORTING_CAPABILITY_SPECS',
  'SPECTRAL_RADIANT_INTENSITY_V1',
  'SPECTRAL_RAY_TRANSFER_V1',
  'VISUAL_SECTIONED_TUBE_V1',
  'get_product_capability_spec',
  'get_supporting_capability_spec',
  'IMAGE_SPECTRAL_RADIANCE_V1',
)
