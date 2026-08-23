"""Versioned product DTOs plus compatibility workflows.

The immutable product contracts are independent from the older local workflow
helpers.  Both remain importable while consumers move to the strict
``exhaust_plume.api`` boundary.
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
from exhaust_plume.products.workflow_signature import (
    evaluate_signature_table_asset,
    load_signature_table_asset,
    load_spectral_signature_request,
    render_signature_plots,
    write_signature_result_csv,
    write_signature_result_json,
    write_signature_table_asset,
)
from exhaust_plume.products.workflow_visual import (
    VisualMesh,
    build_sectioned_tube_mesh,
    evaluate_nozzle_geometry_visual,
    evaluate_shock_cell_visual,
    evaluate_visual_definition,
    load_straight_visual_definition,
    render_visual_preview,
    visual_definition_from_shock_cells,
    visual_definition_from_zone_results,
    write_straight_visual_asset,
    write_visual_mesh_json,
    write_visual_obj,
    write_visual_result_json,
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
    'VisualMesh',
    'build_sectioned_tube_mesh',
    'evaluate_nozzle_geometry_visual',
    'evaluate_signature_table_asset',
    'evaluate_shock_cell_visual',
    'evaluate_visual_definition',
    'load_signature_table_asset',
    'load_spectral_signature_request',
    'load_straight_visual_definition',
    'render_signature_plots',
    'render_visual_preview',
    'visual_definition_from_shock_cells',
    'visual_definition_from_zone_results',
    'write_signature_result_csv',
    'write_signature_result_json',
    'write_signature_table_asset',
    'write_straight_visual_asset',
    'write_visual_mesh_json',
    'write_visual_obj',
    'write_visual_result_json',
)
