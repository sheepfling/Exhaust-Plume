"""Stable semantic capability identifiers and their major versions."""

from __future__ import annotations

from enum import Enum
from types import MappingProxyType
from typing import Mapping

from exhaust_plume.contracts.common_v1 import CapabilityIdentity


class CapabilityId(str, Enum):
  """Semantic products that a plume provider may advertise."""

  SPATIAL_SUPPORT = 'spatial-support'
  AXISYMMETRIC_ZONE_FIELD = 'axisymmetric-zone-field'
  CENTERLINE_TUBE_FIELD = 'centerline-tube-field'
  LOCAL_FLOW_STATE = 'local-flow-state'
  PROJECTED_AREA = 'projected-area'
  DIRECTIONAL_SPECTRAL_INTENSITY = 'directional-spectral-intensity'
  SPECTRAL_RAY_TRANSFER = 'spectral-ray-transfer'
  OPTICAL_MEDIUM = 'optical-medium'
  SCENE_RADIANCE_RENDERER = 'scene-radiance-renderer'
  UNCERTAINTY = 'uncertainty'
####


CAPABILITY_MAJOR_VERSIONS: Mapping[CapabilityId, int] = MappingProxyType({
    capability_id: 1 for capability_id in CapabilityId
})


# Canonical v1 product identities. Compatibility string constants are derived
# from this registry rather than maintaining a second list of wire IDs.
VISUAL_SECTIONED_TUBE_CAPABILITY = CapabilityIdentity(
    name='plume.visual.sectioned-tube',
    major=1,
)
SIGNATURE_SPECTRAL_RADIANT_INTENSITY_CAPABILITY = CapabilityIdentity(
    name='plume.signature.spectral-radiant-intensity',
    major=1,
)
SPECTRAL_RAY_TRANSFER_CAPABILITY = CapabilityIdentity(
    name='plume.optical.spectral-ray-transfer',
    major=1,
)
ENGINEERING_FLUX_SECTION_CAPABILITY = CapabilityIdentity(
    name='plume.engineering.flux-section',
    major=1,
)
SPATIAL_SUPPORT_CAPABILITY = CapabilityIdentity(
    name='plume.spatial.support',
    major=1,
)
SPATIAL_LOCAL_FIELD_CAPABILITY = CapabilityIdentity(
    name='plume.spatial.local-field',
    major=1,
)
SPATIAL_AXISYMMETRIC_ZONE_FIELD_CAPABILITY = CapabilityIdentity(
    name='plume.spatial.axisymmetric-zone-field',
    major=1,
)
SPATIAL_PROJECTED_AREA_CAPABILITY = CapabilityIdentity(
    name='plume.spatial.projected-area',
    major=1,
)
IMAGE_SPECTRAL_RADIANCE_CAPABILITY = CapabilityIdentity(
    name='plume.image.spectral-radiance',
    major=1,
)

PRIMARY_CAPABILITY_IDENTITIES = (
    VISUAL_SECTIONED_TUBE_CAPABILITY,
    SIGNATURE_SPECTRAL_RADIANT_INTENSITY_CAPABILITY,
    SPECTRAL_RAY_TRANSFER_CAPABILITY,
)
SUPPORTING_CAPABILITY_IDENTITIES = (
    ENGINEERING_FLUX_SECTION_CAPABILITY,
    SPATIAL_SUPPORT_CAPABILITY,
    SPATIAL_LOCAL_FIELD_CAPABILITY,
    SPATIAL_AXISYMMETRIC_ZONE_FIELD_CAPABILITY,
    SPATIAL_PROJECTED_AREA_CAPABILITY,
    IMAGE_SPECTRAL_RADIANCE_CAPABILITY,
)
CANONICAL_CAPABILITY_IDENTITIES = PRIMARY_CAPABILITY_IDENTITIES + SUPPORTING_CAPABILITY_IDENTITIES
CANONICAL_CAPABILITY_REGISTRY: Mapping[str, CapabilityIdentity] = MappingProxyType({
    capability.wire_id: capability for capability in CANONICAL_CAPABILITY_IDENTITIES
})


__all__ = (
    'CAPABILITY_MAJOR_VERSIONS',
    'CANONICAL_CAPABILITY_IDENTITIES',
    'CANONICAL_CAPABILITY_REGISTRY',
    'CapabilityId',
    'ENGINEERING_FLUX_SECTION_CAPABILITY',
    'IMAGE_SPECTRAL_RADIANCE_CAPABILITY',
    'PRIMARY_CAPABILITY_IDENTITIES',
    'SIGNATURE_SPECTRAL_RADIANT_INTENSITY_CAPABILITY',
    'SPATIAL_AXISYMMETRIC_ZONE_FIELD_CAPABILITY',
    'SPATIAL_LOCAL_FIELD_CAPABILITY',
    'SPATIAL_PROJECTED_AREA_CAPABILITY',
    'SPATIAL_SUPPORT_CAPABILITY',
    'SPECTRAL_RAY_TRANSFER_CAPABILITY',
    'SUPPORTING_CAPABILITY_IDENTITIES',
    'VISUAL_SECTIONED_TUBE_CAPABILITY',
)
