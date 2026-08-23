"""Capability specifications for the three primary v1 products."""

from __future__ import annotations

from exhaust_plume.contracts.lifecycle_v1 import CapabilitySpec
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
####

__all__ = (
  'SPECTRAL_RADIANT_INTENSITY_V1',
  'SPECTRAL_RAY_TRANSFER_V1',
  'VISUAL_SECTIONED_TUBE_V1',
)
####
