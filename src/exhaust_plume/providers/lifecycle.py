"""Common provider/session/snapshot lifecycle and capability discovery."""

from __future__ import annotations

from enum import Enum
from typing import Protocol, TypeVar, runtime_checkable

from pydantic import Field, field_validator, model_validator

from exhaust_plume.products import CapabilityId, ContractModel, PlumeProduct, Provenance


class TimeAccessMode(str, Enum):
  """Allowed ordering of requested snapshot times."""

  STATIC = 'static'
  RANDOM_ACCESS = 'random-access'
  MONOTONIC = 'monotonic'
####


class ExecutionBackend(str, Enum):
  """Requested execution location."""

  AUTO = 'auto'
  CPU = 'cpu'
  GPU = 'gpu'
####


class ProviderDescriptor(ContractModel):
  """Construction-time provider identity, capabilities, and execution semantics."""

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
  """Execution request that creates one provider-owned session."""

  backend: ExecutionBackend = ExecutionBackend.AUTO
  deterministic_seed: int | None = None
  context_id: str | None = None
####


class UnsupportedCapabilityError(LookupError):
  """Raised when a snapshot does not expose the requested capability."""

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
class PlumeSnapshot(Protocol):
  """Immutable state at one requested time with capability-scoped products."""

  @property
  def descriptor(self) -> ProviderDescriptor:
    ...
  ####

  @property
  def snapshot_id(self) -> str:
    ...
  ####

  @property
  def time_s(self) -> float:
    ...
  ####

  @property
  def capabilities(self) -> tuple[CapabilityId, ...]:
    ...
  ####

  def getProduct(self, capability: CapabilityId) -> PlumeProduct:
    """Return one capability-specific product, never a universal plume result."""
    ...
  ####
####


@runtime_checkable
class PlumeSession(Protocol):
  """Provider-owned execution context with explicit closure semantics."""

  @property
  def descriptor(self) -> ProviderDescriptor:
    ...
  ####

  @property
  def is_closed(self) -> bool:
    ...
  ####

  def snapshot(self, time_s: float) -> PlumeSnapshot:
    ...
  ####

  def close(self) -> None:
    ...
  ####
####


@runtime_checkable
class PlumeProvider(Protocol):
  """Construction-time provider definition and capability declaration."""

  @property
  def descriptor(self) -> ProviderDescriptor:
    ...
  ####

  def createSession(self, request: SessionRequest = SessionRequest()) -> PlumeSession:
    ...
  ####
####


ProductT = TypeVar('ProductT', bound=PlumeProduct)


def requireProduct(
    snapshot: PlumeSnapshot,
    capability: CapabilityId,
    product_type: type[ProductT],
) -> ProductT:
  """Resolve and type-check one product without implying a universal DTO."""
  product = snapshot.getProduct(capability)
  if not isinstance(product, product_type):
    raise TypeError(
        f'Capability {capability} returned {type(product).__name__}; '
        f'expected {product_type.__name__}.'
    )
  ####
  return product
####
