"""Reusable checks for providers implementing the visual v1 capability."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, cast

from exhaust_plume.contracts.common_v1 import ProviderDescriptor
from exhaust_plume.contracts.errors import (
  UnsupportedProductCapabilityError,
  UnsupportedProductVersionError,
)
from exhaust_plume.contracts.lifecycle_v1 import ProductSnapshot
from exhaust_plume.contracts.ray_transfer_v1 import SPECTRAL_RAY_TRANSFER_CAPABILITY, SpectralRayTransferRequest
from exhaust_plume.contracts.signature_v1 import (
  SPECTRAL_RADIANT_INTENSITY_CAPABILITY,
  SpectralSignatureRequest,
)
from exhaust_plume.contracts.specs_v1 import (
  SPECTRAL_RADIANT_INTENSITY_V1,
  SPECTRAL_RAY_TRANSFER_V1,
  VISUAL_SECTIONED_TUBE_V1,
)
from exhaust_plume.contracts.visual_v1 import VisualSectionedTubeRequest

__all__ = (
  'VisualProviderConformanceReport',
  'run_visual_provider_conformance',
)
####


@dataclass(frozen=True, slots=True)
class VisualProviderConformanceReport:
  """Evidence returned by the common visual-provider checks."""

  provider_id: str
  capability_wire_id: str
  result_id: str
  deterministic_serialization: bool
  unsupported_capabilities: tuple[str, ...]
  section_count: int
  passed: bool = True
####


def run_visual_provider_conformance(
    descriptor: ProviderDescriptor,
    snapshot_factory: Callable[[], ProductSnapshot],
    request: VisualSectionedTubeRequest,
) -> VisualProviderConformanceReport:
  """Exercise lifecycle-independent invariants shared by visual providers.

  The caller supplies a fresh immutable snapshot factory so the same checks
  can run against prescribed and analytical providers without knowing their
  provider-specific definition or operating-state types.
  """

  if VISUAL_SECTIONED_TUBE_V1.capability not in descriptor.supported_capabilities:
    raise AssertionError('provider descriptor must advertise visual sectioned-tube v1')
  first_snapshot = snapshot_factory()
  second_snapshot = snapshot_factory()
  if not first_snapshot.supports(VISUAL_SECTIONED_TUBE_V1.capability):
    raise AssertionError('snapshot must advertise the descriptor visual capability')
  first_result = first_snapshot.evaluate(VISUAL_SECTIONED_TUBE_V1, request)
  second_result = second_snapshot.evaluate(VISUAL_SECTIONED_TUBE_V1, request)
  first_serialized = first_result.model_dump(mode='json')
  second_serialized = second_result.model_dump(mode='json')
  deterministic = first_serialized == second_serialized
  if not deterministic:
    raise AssertionError('steady visual provider serialization must be deterministic')
  unsupported: list[str] = []
  spectral_requests = (
    (
      SPECTRAL_RADIANT_INTENSITY_CAPABILITY.wire_id,
      SPECTRAL_RADIANT_INTENSITY_V1,
      SpectralSignatureRequest(
        direction_frame_id=request.output_frame_id,
        source_to_observer_directions=((1.0, 0.0, 0.0),),
        wavelengths_m=(1.0e-6,),
      ),
    ),
    (
      SPECTRAL_RAY_TRANSFER_CAPABILITY.wire_id,
      SPECTRAL_RAY_TRANSFER_V1,
      SpectralRayTransferRequest(
        ray_frame_id=request.output_frame_id,
        ray_origins_m=((0.0, 0.0, 0.0),),
        ray_directions=((1.0, 0.0, 0.0),),
        ray_t_min_m=(0.0,),
        ray_t_max_m=(1.0,),
        wavelengths_m=(1.0e-6,),
      ),
    ),
  )
  for wire_id, capability, spectral_request in spectral_requests:
    try:
      first_snapshot.evaluate(cast(Any, capability), cast(Any, spectral_request))
    except (UnsupportedProductCapabilityError, UnsupportedProductVersionError):
      unsupported.append(wire_id)
    else:
      raise AssertionError(f'visual-only provider unexpectedly served {wire_id}')
  return VisualProviderConformanceReport(
    provider_id=descriptor.provider_id,
    capability_wire_id=VISUAL_SECTIONED_TUBE_V1.capability.wire_id,
    result_id=first_result.metadata.result_id,
    deterministic_serialization=deterministic,
    unsupported_capabilities=tuple(unsupported),
    section_count=len(first_result.sections),
  )
####
