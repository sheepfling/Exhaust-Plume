"""Versioned product DTOs plus compatibility workflows.

The strict product contracts are independent from the older local
visualization and signature workflow helpers. Both remain importable while
consumers migrate to ``exhaust_plume.api``.
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
from exhaust_plume.products.workflow_gallery import (
    GALLERY_MANIFEST_SCHEMA,
    GalleryArtifact,
    VisualizationGalleryManifest,
    render_plume_flux_gallery,
    render_product_gallery,
    render_sectioned_tube_gallery,
    render_spectral_radiant_intensity_gallery,
    render_spectral_ray_transfer_gallery,
    write_gallery_manifest,
)
from exhaust_plume.products.workflow_interactive import (
    INTERACTIVE_GALLERY_SCHEMA,
    write_interactive_product_gallery,
)
from exhaust_plume.products.workflow_comparison import (
    COMPARISON_REPORT_SCHEMA,
    ProductComparisonArtifacts,
    ProductComparisonReport,
    compare_product_results,
    render_product_comparison,
    write_product_comparison_report,
)
from exhaust_plume.products.workflow_fpa import (
    FPA_GALLERY_MANIFEST_SCHEMA,
    FpaVisualizationGalleryManifest,
    render_fpa_gallery,
    write_fpa_gallery_manifest,
)
from exhaust_plume.products.workflow_fpa_interactive import (
    FPA_INTERACTIVE_GALLERY_SCHEMA,
    write_interactive_fpa_gallery,
)
from exhaust_plume.products.model_visualization import (
    MODEL_VISUALIZATION_LANES,
    MODEL_VISUALIZATION_SCHEMA,
    ModelVisualizationClaims,
    ModelVisualizationLane,
    ModelVisualChannel,
    ModelVisualField,
    ModelVisualPath,
    StandardizedModelVisualization,
    evaluate_standardized_model_visualization,
    standardize_all_model_visualizations,
    standardize_model_result,
    standardize_model_visualization,
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
    'COMPARISON_REPORT_SCHEMA',
    'CompletionStatus',
    'ContractModel',
    'ConservativeSupportProduct',
    'CoordinateFrame',
    'DirectionConvention',
    'ENGINEERING_FLUX_SECTION_V1',
    'EngineeringFluxSectionProduct',
    'Fidelity',
    'FPA_GALLERY_MANIFEST_SCHEMA',
    'FPA_INTERACTIVE_GALLERY_SCHEMA',
    'FpaVisualizationGalleryManifest',
    'GALLERY_MANIFEST_SCHEMA',
    'GalleryArtifact',
    'INTERACTIVE_GALLERY_SCHEMA',
    'MODEL_VISUALIZATION_LANES',
    'MODEL_VISUALIZATION_SCHEMA',
    'ModelVisualizationClaims',
    'ModelVisualizationLane',
    'ModelVisualChannel',
    'ModelVisualField',
    'ModelVisualPath',
    'OPTICAL_SPECTRAL_RAY_TRANSFER_V1',
    'PlumeProduct',
    'ProductComparisonReport',
    'ProductComparisonArtifacts',
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
    'StandardizedModelVisualization',
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
    'render_plume_flux_gallery',
    'render_product_gallery',
    'render_fpa_gallery',
    'render_sectioned_tube_gallery',
    'render_spectral_radiant_intensity_gallery',
    'render_spectral_ray_transfer_gallery',
    'render_visual_preview',
    'visual_definition_from_shock_cells',
    'visual_definition_from_zone_results',
    'write_signature_result_csv',
    'write_signature_result_json',
    'write_signature_table_asset',
    'write_gallery_manifest',
    'write_interactive_product_gallery',
    'write_interactive_fpa_gallery',
    'write_fpa_gallery_manifest',
    'write_product_comparison_report',
    'compare_product_results',
    'render_product_comparison',
    'write_straight_visual_asset',
    'write_visual_mesh_json',
    'write_visual_obj',
    'write_visual_result_json',
    'evaluate_standardized_model_visualization',
    'standardize_all_model_visualizations',
    'standardize_model_result',
    'standardize_model_visualization',
    'VisualizationGalleryManifest',
)
