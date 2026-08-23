"""Canonical public v1 facade for the shipped plume product contracts.

``exhaust_plume.contracts`` remains the implementation and serialization
authority for the v1 wire models.  This module is the supported public import
surface for new consumers, so a consumer can use one namespace without
depending on the compatibility location that owns the model definitions.

The facade deliberately contains aliases rather than a second model tree.
``PUBLIC_CONTRACT_MODELS`` and ``export_public_schemas`` are the same registry
and generator used for the checked-in schemas and fixtures.
"""

from __future__ import annotations

from exhaust_plume.contracts.capability import CAPABILITY_MAJOR_VERSIONS, CapabilityId
from exhaust_plume.contracts.common_v1 import (
  ApiError,
  ApiModel,
  ApplicabilityReport,
  ApplicabilityStatus,
  CapabilityIdentity,
  ConsistencyLevel,
  Derivation,
  ErrorCode,
  GeometryClaim,
  Pose,
  ProductClaims,
  ProviderDescriptor,
  RadiationClaim,
  ResultMetadata,
  ResultProvenance,
  SampleStatus,
  SampleStatusCode,
  SessionMetadata,
  SnapshotMetadata,
  TimeModel,
  Vector3,
  canonical_digest,
)
from exhaust_plume.contracts.conformance_v1 import (
  VisualProviderConformanceReport,
  run_visual_provider_conformance,
)
from exhaust_plume.contracts.descriptor import (
  PlumeMorphology,
  PlumeProviderDescriptor,
  ProviderApplicability,
  ProviderFidelity,
)
from exhaust_plume.contracts.errors import (
  AngularDomainError,
  CapabilityVersionMismatchError,
  ContractViolationError,
  InvalidProductRequestError,
  OperatingStateDomainError,
  ProductOutsideApplicabilityError,
  ProductSnapshotExpiredError,
  PublicContractError,
  ProviderClosedError,
  ProviderConfigurationError,
  ProviderError,
  SnapshotInvalidatedError,
  SpatialDomainError,
  SpectralDomainError,
  TemporalDomainError,
  UnsupportedCapabilityError,
  UnsupportedProductCapabilityError,
  UnsupportedProductVersionError,
)
from exhaust_plume.contracts.execution import (
  ConcurrencyMode,
  ProviderExecutionProfile,
  SnapshotRetention,
  TimeAccessMode,
)
from exhaust_plume.contracts.handoff import PlumeFluxSection
from exhaust_plume.contracts.lifecycle_v1 import (
  CapabilityEvaluator,
  CapabilitySpec,
  ImmutableProductSnapshot,
  ProductProvider,
  ProductSession,
  ProductSnapshot,
)
from exhaust_plume.contracts.provenance import PlumeProvenance
from exhaust_plume.contracts.radiometry import (
  DirectionalSpectralIntensityQuery,
  DirectionalSpectralIntensityResult,
  SpectralRayTransferQuery,
  SpectralRayTransferResult as RadiometrySpectralRayTransferResult,
)
from exhaust_plume.contracts.ray_transfer_v1 import (
  SPECTRAL_RAY_TRANSFER_CAPABILITY,
  SpectralRayTransferRequest,
  SpectralRayTransferResult,
)
from exhaust_plume.contracts.schema_v1 import PUBLIC_CONTRACT_MODELS, export_public_schemas
from exhaust_plume.contracts.signature_v1 import (
  SPECTRAL_RADIANT_INTENSITY_CAPABILITY,
  SpectralSignatureRequest,
  SpectralSignatureResult,
)
from exhaust_plume.contracts.specs_v1 import (
  SPECTRAL_RADIANT_INTENSITY_V1,
  SPECTRAL_RAY_TRANSFER_V1,
  VISUAL_SECTIONED_TUBE_V1,
)
from exhaust_plume.contracts.spatial import (
  AxisymmetricZone,
  AxisymmetricZoneField,
  ProjectedAreaCapability,
  SpatialSupport,
)
from exhaust_plume.contracts.snapshot import (
  PlumeCapability,
  PlumeProvider,
  PlumeSession,
  PlumeSnapshot,
  TerminationReason,
  TerminationReport,
)
from exhaust_plume.contracts.visual_v1 import (
  LodProfile,
  VISUAL_SECTIONED_TUBE_CAPABILITY,
  VisualBounds,
  VisualChannelId,
  VisualSampling,
  VisualSection,
  VisualSectionedTubeRequest,
  VisualSectionedTubeResult,
  VisualTubeRequest,
  VisualTubeResult,
  VisualTubeSection,
  VisualTubeSummary,
)

VersionedSpectralRayTransferResult = SpectralRayTransferResult

__all__ = (
  'AngularDomainError',
  'ApiError',
  'ApiModel',
  'ApplicabilityReport',
  'ApplicabilityStatus',
  'AxisymmetricZone',
  'AxisymmetricZoneField',
  'CAPABILITY_MAJOR_VERSIONS',
  'CapabilityEvaluator',
  'CapabilityIdentity',
  'CapabilitySpec',
  'CapabilityVersionMismatchError',
  'CapabilityId',
  'ConcurrencyMode',
  'ConsistencyLevel',
  'ContractViolationError',
  'Derivation',
  'DirectionalSpectralIntensityQuery',
  'DirectionalSpectralIntensityResult',
  'ErrorCode',
  'GeometryClaim',
  'ImmutableProductSnapshot',
  'InvalidProductRequestError',
  'LodProfile',
  'OperatingStateDomainError',
  'PlumeCapability',
  'PlumeFluxSection',
  'PlumeMorphology',
  'PlumeProvider',
  'PlumeProviderDescriptor',
  'PlumeProvenance',
  'PlumeSession',
  'PlumeSnapshot',
  'Pose',
  'ProductClaims',
  'ProductOutsideApplicabilityError',
  'ProductProvider',
  'ProductSession',
  'ProductSnapshot',
  'ProductSnapshotExpiredError',
  'ProviderApplicability',
  'ProviderClosedError',
  'ProviderConfigurationError',
  'ProviderDescriptor',
  'ProviderError',
  'ProviderExecutionProfile',
  'ProviderFidelity',
  'ProjectedAreaCapability',
  'PublicContractError',
  'RadiationClaim',
  'RadiometrySpectralRayTransferResult',
  'ResultMetadata',
  'ResultProvenance',
  'SampleStatus',
  'SampleStatusCode',
  'SessionMetadata',
  'SnapshotInvalidatedError',
  'SnapshotMetadata',
  'SnapshotRetention',
  'SpatialDomainError',
  'SpatialSupport',
  'SPECTRAL_RADIANT_INTENSITY_CAPABILITY',
  'SPECTRAL_RADIANT_INTENSITY_V1',
  'SPECTRAL_RAY_TRANSFER_CAPABILITY',
  'SPECTRAL_RAY_TRANSFER_V1',
  'SpectralDomainError',
  'SpectralRayTransferQuery',
  'SpectralRayTransferRequest',
  'SpectralRayTransferResult',
  'SpectralSignatureRequest',
  'SpectralSignatureResult',
  'TemporalDomainError',
  'TerminationReason',
  'TerminationReport',
  'TimeAccessMode',
  'TimeModel',
  'UnsupportedCapabilityError',
  'UnsupportedProductCapabilityError',
  'UnsupportedProductVersionError',
  'Vector3',
  'VersionedSpectralRayTransferResult',
  'VISUAL_SECTIONED_TUBE_CAPABILITY',
  'VISUAL_SECTIONED_TUBE_V1',
  'VisualBounds',
  'VisualChannelId',
  'VisualProviderConformanceReport',
  'VisualSampling',
  'VisualSection',
  'VisualSectionedTubeRequest',
  'VisualSectionedTubeResult',
  'VisualTubeRequest',
  'VisualTubeResult',
  'VisualTubeSection',
  'VisualTubeSummary',
  'canonical_digest',
  'export_public_schemas',
  'PUBLIC_CONTRACT_MODELS',
  'run_visual_provider_conformance',
)
