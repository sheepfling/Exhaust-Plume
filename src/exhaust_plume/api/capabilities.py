"""Versioned capability identities for public exhaust-plume products."""

from __future__ import annotations

VISUAL_SECTIONED_TUBE_V1 = 'plume.visual.sectioned-tube@1'
SIGNATURE_SPECTRAL_RADIANT_INTENSITY_V1 = 'plume.signature.spectral-radiant-intensity@1'
OPTICAL_SPECTRAL_RAY_TRANSFER_V1 = 'plume.optical.spectral-ray-transfer@1'

ENGINEERING_FLUX_SECTION_V1 = 'plume.engineering.flux-section@1'
SPATIAL_SUPPORT_V1 = 'plume.spatial.support@1'
SPATIAL_LOCAL_FIELD_V1 = 'plume.spatial.local-field@1'
SPATIAL_AXISYMMETRIC_ZONE_FIELD_V1 = 'plume.spatial.axisymmetric-zone-field@1'
SPATIAL_PROJECTED_AREA_V1 = 'plume.spatial.projected-area@1'
IMAGE_SPECTRAL_RADIANCE_V1 = 'plume.image.spectral-radiance@1'

PRIMARY_CAPABILITY_IDS = (
    VISUAL_SECTIONED_TUBE_V1,
    SIGNATURE_SPECTRAL_RADIANT_INTENSITY_V1,
    OPTICAL_SPECTRAL_RAY_TRANSFER_V1,
)

SUPPORTING_CAPABILITY_IDS = (
    ENGINEERING_FLUX_SECTION_V1,
    SPATIAL_SUPPORT_V1,
    SPATIAL_LOCAL_FIELD_V1,
    SPATIAL_AXISYMMETRIC_ZONE_FIELD_V1,
    SPATIAL_PROJECTED_AREA_V1,
    IMAGE_SPECTRAL_RADIANCE_V1,
)
####
