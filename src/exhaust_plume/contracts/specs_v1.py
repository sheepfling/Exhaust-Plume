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

PRIMARY_PRODUCT_CAPABILITY_SPECS: Mapping[str, CapabilitySpec[Any, Any]] = MappingProxyType({
  VISUAL_SECTIONED_TUBE_V1.capability.wire_id: VISUAL_SECTIONED_TUBE_V1,
  SPECTRAL_RADIANT_INTENSITY_V1.capability.wire_id: SPECTRAL_RADIANT_INTENSITY_V1,
  SPECTRAL_RAY_TRANSFER_V1.capability.wire_id: SPECTRAL_RAY_TRANSFER_V1,
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

__all__ = (
  'PRIMARY_PRODUCT_CAPABILITY_SPECS',
  'SPECTRAL_RADIANT_INTENSITY_V1',
  'SPECTRAL_RAY_TRANSFER_V1',
  'VISUAL_SECTIONED_TUBE_V1',
  'get_product_capability_spec',
)
