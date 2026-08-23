"""Common provider/session/snapshot lifecycle and capability discovery."""

from __future__ import annotations

from enum import Enum
from typing import Protocol, TypeVar, runtime_checkable

from pydantic import Field, field_validator, model_validator

from exhaust_plume.products import (
    CapabilityId,
    EngineeringFluxSectionProduct,
    SectionedTubeProduct,
    SpectralRadiantIntensityProduct,
    SpectralRayTransferProduct,
)
from exhaust_plume.products._base import ContractModel, Provenance


class TimeAccessMode(str, Enum):
  STATIC = 'static'
  RANDOM_ACCESS = 'random-access'
  MONOTONIC = 'monotonic'
####


class ExecutionBackend(str, Enum):
  AUTO = 'auto'
  CPU = 'cpu'
  GPU = 'gpu'
####


class ProviderDescriptor(ContractModel):
  provider_id: str = Field(min_length=1)
  provider_version: str = Field(min_length=1)
  display_name: str = Field(min_length=1)
  capabilities: tuple[CapabilityId, ...] = Field(min_length=1)
  time_access_mode: TimeAccessMode
  supported_backends: tuple[ExecutionBackend, ...] = (ExecutionBackend.CPU,)
  thread_safe_sessions: bool = False
  retained_snapshots: int | None = None
  provenance: Provenance

  @field_validator('capabilities')
  @classmethod
  def validateCapabilities(cls, values: tuple[CapabilityId, ...]) -> tuple[CapabilityId, ...]:
    identities = tuple(str(value) for value in values)
    if len(set(identities)) != len(identities):
      raise ValueError('Provider capabilities must be unique.')
    ####
    return values
  ####

  @model_validator(mode='after')
  def validateDescriptor(self) -> ProviderDescriptor:
    if self.retained_snapshots is not None and self.retained_snapshots < 0:
      raise ValueError('retained_snapshots must be nonnegative when present.')
    ####
    if not self.supported_backends:
      raise ValueError('Expected at least one supported execution backend.')
    ####
    return self
  ####

  def supports(self, capability: CapabilityId) -> bool:
    return capability in self.capabilities
  ####
####


class SessionRequest(ContractModel):
  backend: ExecutionBackend = ExecutionBackend.AUTO
  deterministic_seed: int | None = None
  context_id: str | None = None
####


class UnsupportedCapabilityError(LookupError):
  def __init__(self, *, provider_id: str, capability: CapabilityId) -> None:
    self.provider_id = provider_id
    self.capability = capability
    super().__init__(
        f'Provider {provider_id!r} does not expose capability {capability} for this snapshot.'
    )
  ####
####


class ClosedSessionError(RuntimeError):
  """Raised when a closed session is used."""
####


@runtime_checkable
class CapabilityBinding(Protocol):
  @property
  def capability_id(self) -> CapabilityId:
    ...
####


@runtime_checkable
class VisualSectionedTubeCapability(CapabilityBinding, Protocol):
  def getSectionedTube(self) -> SectionedTubeProduct:
    ...
####


@runtime_checkable
class SpectralRadiantIntensityCapability(CapabilityBinding, Protocol):
  def getSpectralRadiantIntensity(self) -> SpectralRadiantIntensityProduct:
    ...
####


@runtime_checkable
class SpectralRayTransferCapability(CapabilityBinding, Protocol):
  def getSpectralRayTransfer(self) -> SpectralRayTransferProduct:
    ...
####


@runtime_checkable
class EngineeringFluxSectionCapability(CapabilityBinding, Protocol):
  def getEngineeringFluxSections(self) -> EngineeringFluxSectionProduct:
    ...
####


@runtime_checkable
class PlumeSnapshot(Protocol):
  @property
  def descriptor(self) -> ProviderDescriptor:
    ...

  @property
  def snapshot_id(self) -> str:
    ...

  @property
  def time_s(self) -> float:
    ...

  @property
  def capabilities(self) -> tuple[CapabilityId, ...]:
    ...

  def resolveCapability(self, capability: CapabilityId) -> CapabilityBinding:
    ...
####


@runtime_checkable
class PlumeSession(Protocol):
  @property
  def descriptor(self) -> ProviderDescriptor:
    ...

  @property
  def is_closed(self) -> bool:
    ...

  def snapshot(self, time_s: float) -> PlumeSnapshot:
    ...

  def close(self) -> None:
    ...
####


@runtime_checkable
class PlumeProvider(Protocol):
  @property
  def descriptor(self) -> ProviderDescriptor:
    ...

  def createSession(self, request: SessionRequest = SessionRequest()) -> PlumeSession:
    ...
####


CapabilityT = TypeVar('CapabilityT', bound=CapabilityBinding)


def requireCapability(
    snapshot: PlumeSnapshot,
    capability: CapabilityId,
    capability_type: type[CapabilityT],
) -> CapabilityT:
  binding = snapshot.resolveCapability(capability)
  if not isinstance(binding, capability_type):
    raise TypeError(
        f'Capability {capability} resolved to {type(binding).__name__}; '
        f'expected {capability_type.__name__}.'
    )
  ####
  return binding
####
