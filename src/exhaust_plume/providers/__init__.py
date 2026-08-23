"""Plume provider lifecycle, static fixtures, and product adapters."""

from __future__ import annotations

from exhaust_plume.providers.adapters import (
    engineeringFluxSectionsFromCurvedPlume,
    sectionedTubeFromAxisymmetricZones,
    sectionedTubeFromCurvedPlume,
)
from exhaust_plume.providers.lifecycle import (
    CapabilityBinding,
    ClosedSessionError,
    EngineeringFluxSectionCapability,
    ExecutionBackend,
    PlumeProvider,
    PlumeSession,
    PlumeSnapshot,
    ProviderDescriptor,
    SessionRequest,
    SpectralRadiantIntensityCapability,
    SpectralRayTransferCapability,
    TimeAccessMode,
    UnsupportedCapabilityError,
    VisualSectionedTubeCapability,
    requireCapability,
)
from exhaust_plume.providers.static import (
    StaticEngineeringFluxCapability,
    StaticPlumeProvider,
    StaticPlumeSession,
    StaticPlumeSnapshot,
    StaticRayTransferCapability,
    StaticSignatureCapability,
    StaticVisualCapability,
)

__all__ = (
    'CapabilityBinding',
    'ClosedSessionError',
    'EngineeringFluxSectionCapability',
    'ExecutionBackend',
    'PlumeProvider',
    'PlumeSession',
    'PlumeSnapshot',
    'ProviderDescriptor',
    'SessionRequest',
    'SpectralRadiantIntensityCapability',
    'SpectralRayTransferCapability',
    'StaticEngineeringFluxCapability',
    'StaticPlumeProvider',
    'StaticPlumeSession',
    'StaticPlumeSnapshot',
    'StaticRayTransferCapability',
    'StaticSignatureCapability',
    'StaticVisualCapability',
    'TimeAccessMode',
    'UnsupportedCapabilityError',
    'VisualSectionedTubeCapability',
    'engineeringFluxSectionsFromCurvedPlume',
    'requireCapability',
    'sectionedTubeFromAxisymmetricZones',
    'sectionedTubeFromCurvedPlume',
)
