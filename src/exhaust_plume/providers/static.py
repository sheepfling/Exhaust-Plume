"""Compatibility-only static providers for legacy fixtures and tests.

Production providers use the canonical v1 lifecycle. This module remains
available for 0.1.x callers that exchange the pre-v1 product DTOs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from typing import Mapping

from exhaust_plume.products import (
    CapabilityId,
    ENGINEERING_FLUX_SECTION_V1,
    EngineeringFluxSectionProduct,
    OPTICAL_SPECTRAL_RAY_TRANSFER_V1,
    SIGNATURE_SPECTRAL_RADIANT_INTENSITY_V1,
    SectionedTubeProduct,
    SpectralRadiantIntensityProduct,
    SpectralRayTransferProduct,
    VISUAL_SECTIONED_TUBE_V1,
)
from exhaust_plume.providers.lifecycle import (
    CapabilityBinding,
    ClosedSessionError,
    ExecutionBackend,
    PlumeSnapshot,
    ProviderDescriptor,
    SessionRequest,
    TimeAccessMode,
    UnsupportedCapabilityError,
)


@dataclass(frozen=True)
class StaticVisualCapability:
  product: SectionedTubeProduct

  @property
  def product_metadata(self):
    return self.product.metadata
  ####

  @property
  def capability_id(self) -> CapabilityId:
    return VISUAL_SECTIONED_TUBE_V1
  ####

  def getSectionedTube(self) -> SectionedTubeProduct:
    return self.product
  ####
####


@dataclass(frozen=True)
class StaticSignatureCapability:
  product: SpectralRadiantIntensityProduct

  @property
  def product_metadata(self):
    return self.product.metadata
  ####

  @property
  def capability_id(self) -> CapabilityId:
    return SIGNATURE_SPECTRAL_RADIANT_INTENSITY_V1
  ####

  def getSpectralRadiantIntensity(self) -> SpectralRadiantIntensityProduct:
    return self.product
  ####
####


@dataclass(frozen=True)
class StaticRayTransferCapability:
  product: SpectralRayTransferProduct

  @property
  def product_metadata(self):
    return self.product.metadata
  ####

  @property
  def capability_id(self) -> CapabilityId:
    return OPTICAL_SPECTRAL_RAY_TRANSFER_V1
  ####

  def getSpectralRayTransfer(self) -> SpectralRayTransferProduct:
    return self.product
  ####
####


@dataclass(frozen=True)
class StaticEngineeringFluxCapability:
  product: EngineeringFluxSectionProduct

  @property
  def product_metadata(self):
    return self.product.metadata
  ####

  @property
  def capability_id(self) -> CapabilityId:
    return ENGINEERING_FLUX_SECTION_V1
  ####

  def getEngineeringFluxSections(self) -> EngineeringFluxSectionProduct:
    return self.product
  ####
####


@dataclass(frozen=True)
class StaticPlumeSnapshot:
  descriptor: ProviderDescriptor
  snapshot_id: str
  time_s: float
  _bindings: Mapping[CapabilityId, CapabilityBinding] = field(repr=False)

  def __post_init__(self) -> None:
    if not self.snapshot_id:
      raise ValueError('Expected a non-empty snapshot_id.')
    ####
    if not isfinite(self.time_s):
      raise ValueError('Expected finite time_s.')
    ####
    bindings = dict(self._bindings)
    if not bindings:
      raise ValueError('Expected at least one static capability binding.')
    ####
    advertised = set(self.descriptor.capabilities)
    supplied = set(bindings)
    if supplied != advertised:
      raise ValueError(
          f'Static bindings {sorted(map(str, supplied))} do not match advertised '
          f'capabilities {sorted(map(str, advertised))}.'
      )
    ####
    for capability, binding in bindings.items():
      if binding.capability_id != capability:
        raise ValueError(f'Binding identity {binding.capability_id} does not match {capability}.')
      ####
      metadata = getattr(binding, 'product_metadata', None)
      if metadata is not None and (
          metadata.snapshot_id != self.snapshot_id or metadata.time_s != self.time_s
      ):
        raise ValueError(
            'Static product metadata must match the owning snapshot identifier and time.'
        )
      ####
    ####
    object.__setattr__(self, '_bindings', bindings)
  ####

  @property
  def capabilities(self) -> tuple[CapabilityId, ...]:
    return self.descriptor.capabilities
  ####

  def resolveCapability(self, capability: CapabilityId) -> CapabilityBinding:
    try:
      return self._bindings[capability]
    except KeyError as exc:
      raise UnsupportedCapabilityError(
          provider_id=self.descriptor.provider_id,
          capability=capability,
      ) from exc
    ####
  ####
####


@dataclass
class StaticPlumeSession:
  descriptor: ProviderDescriptor
  _snapshot: StaticPlumeSnapshot
  _is_closed: bool = False

  @property
  def is_closed(self) -> bool:
    return self._is_closed
  ####

  def snapshot(self, time_s: float) -> PlumeSnapshot:
    if self._is_closed:
      raise ClosedSessionError('Cannot obtain a snapshot from a closed session.')
    ####
    if self.descriptor.time_access_mode is TimeAccessMode.STATIC and time_s != self._snapshot.time_s:
      raise ValueError(f'Static provider only supports time {self._snapshot.time_s}. Got:{time_s}')
    ####
    return self._snapshot
  ####

  def close(self) -> None:
    self._is_closed = True
  ####

  def __enter__(self) -> StaticPlumeSession:
    if self._is_closed:
      raise ClosedSessionError('Cannot enter a closed session.')
    ####
    return self
  ####

  def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
    del exc_type, exc, traceback
    self.close()
  ####
####


@dataclass(frozen=True)
class StaticPlumeProvider:
  descriptor: ProviderDescriptor
  binding_by_capability: Mapping[CapabilityId, CapabilityBinding] = field(repr=False)
  snapshot_id: str = 'static-snapshot'
  time_s: float = 0.

  def __post_init__(self) -> None:
    if self.descriptor.time_access_mode is not TimeAccessMode.STATIC:
      raise ValueError('StaticPlumeProvider requires TimeAccessMode.STATIC.')
    ####
    bindings = dict(self.binding_by_capability)
    object.__setattr__(self, 'binding_by_capability', bindings)
    StaticPlumeSnapshot(
        descriptor=self.descriptor,
        snapshot_id=self.snapshot_id,
        time_s=self.time_s,
        _bindings=bindings,
    )
  ####

  def createSession(self, request: SessionRequest = SessionRequest()) -> StaticPlumeSession:
    backend = request.backend
    if backend is ExecutionBackend.AUTO:
      backend = self.descriptor.supported_backends[0]
    ####
    if backend not in self.descriptor.supported_backends:
      raise ValueError(f'Backend {backend.value!r} is not supported.')
    ####
    snapshot = StaticPlumeSnapshot(
        descriptor=self.descriptor,
        snapshot_id=self.snapshot_id,
        time_s=self.time_s,
        _bindings=self.binding_by_capability,
    )
    return StaticPlumeSession(descriptor=self.descriptor, _snapshot=snapshot)
  ####
####
