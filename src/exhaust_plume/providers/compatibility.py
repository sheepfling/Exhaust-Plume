"""Compatibility-only provider ABI retained for the 0.1.x release line.

New providers and consumers must use ``exhaust_plume.api.v1`` and the typed
``ProductProvider``/``ProductSession``/``ProductSnapshot`` lifecycle. These
exports exist so existing fixture and alpha callers can migrate without a
wire-contract break.
"""

from __future__ import annotations

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
  'requireCapability',
)
