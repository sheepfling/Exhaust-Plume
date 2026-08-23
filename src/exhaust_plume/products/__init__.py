"""Versioned plume-product contracts.

The three primary MVP products are intentionally independent:

* visual sectioned geometry;
* unresolved intrinsic spectral radiant intensity;
* resolved spectral source-radiance/background-transmittance transfer.

Supporting engineering and spatial products compose providers but do not
replace those primary product semantics.
"""

from __future__ import annotations

from typing import TypeAlias

from exhaust_plume.products._base import (
    Aabb3,
    Applicability,
    BatchValidity,
    CapabilityId,
    CompletionStatus,
    ContractModel,
    CoordinateFrame,
    DirectionConvention,
    ENGINEERING_FLUX_SECTION_V1,
    Fidelity,
    OPTICAL_SPECTRAL_RAY_TRANSFER_V1,
    ProductMetadata,
    ProductReference,
    Provenance,
    SIGNATURE_SPECTRAL_RADIANT_INTENSITY_V1,
    SPATIAL_CONSERVATIVE_SUPPORT_V1,
    SpectralAxis,
    SpectralCoordinateKind,
    VISUAL_SECTIONED_TUBE_V1,
)
from exhaust_plume.products.ray_transfer import RayDefinition, SpectralRayTransferProduct
from exhaust_plume.products.signature import SpectralRadiantIntensityProduct
from exhaust_plume.products.supporting import EngineeringFluxSectionProduct
from exhaust_plume.products.visual import (
    ConservativeSupportProduct,
    SectionedTubeProduct,
    VisualFeatureChannel,
)

PlumeProduct: TypeAlias = (
    ConservativeSupportProduct
    | EngineeringFluxSectionProduct
    | SectionedTubeProduct
    | SpectralRadiantIntensityProduct
    | SpectralRayTransferProduct
)

__all__ = (
    'Aabb3',
    'Applicability',
    'BatchValidity',
    'CapabilityId',
    'CompletionStatus',
    'ContractModel',
    'ConservativeSupportProduct',
    'CoordinateFrame',
    'DirectionConvention',
    'ENGINEERING_FLUX_SECTION_V1',
    'EngineeringFluxSectionProduct',
    'Fidelity',
    'OPTICAL_SPECTRAL_RAY_TRANSFER_V1',
    'PlumeProduct',
    'ProductMetadata',
    'ProductReference',
    'Provenance',
    'RayDefinition',
    'SIGNATURE_SPECTRAL_RADIANT_INTENSITY_V1',
    'SPATIAL_CONSERVATIVE_SUPPORT_V1',
    'SectionedTubeProduct',
    'SpectralAxis',
    'SpectralCoordinateKind',
    'SpectralRadiantIntensityProduct',
    'SpectralRayTransferProduct',
    'VISUAL_SECTIONED_TUBE_V1',
    'VisualFeatureChannel',
)
