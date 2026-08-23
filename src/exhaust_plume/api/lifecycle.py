"""Provider, session, snapshot, and capability lifecycle contracts."""

from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from pydantic import Field, model_validator

from exhaust_plume.api.contracts import ProductResult, SnapshotRequest, StrictFrozenModel


class CapabilityAdvertisement(StrictFrozenModel):
  capability_id: str = Field(min_length=1)
  schema_version: str = Field(pattern=r'^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$')
####


class ProviderDescriptor(StrictFrozenModel):
  provider_id: UUID
  provider_type: str = Field(min_length=1)
  provider_version: str = Field(min_length=1)
  capabilities: tuple[CapabilityAdvertisement, ...]
  static_time: bool

  @model_validator(mode='after')
  def validate_capabilities(self) -> ProviderDescriptor:
    identities = [(capability.capability_id, capability.schema_version) for capability in self.capabilities]
    if len(set(identities)) != len(identities):
      raise ValueError('provider capabilities must be unique')
    ####
    return self
  ####
####


class ProductRequest(StrictFrozenModel):
  capability_id: str = Field(min_length=1)
  schema_version: str = Field(pattern=r'^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$')
####


@runtime_checkable
class PlumeSnapshot(Protocol):
  @property
  def snapshot_id(self) -> UUID:
    ...
  ####

  @property
  def requested_time_s(self) -> float:
    ...
  ####

  @property
  def actual_time_s(self) -> float:
    ...
  ####

  def get_product(self, request: ProductRequest) -> ProductResult:
    ...
  ####
####


@runtime_checkable
class PlumeSession(Protocol):
  @property
  def session_id(self) -> UUID:
    ...
  ####

  def snapshot(self, request: SnapshotRequest) -> PlumeSnapshot:
    ...
  ####

  def close(self) -> None:
    ...
  ####
####


@runtime_checkable
class PlumeProvider(Protocol):
  @property
  def descriptor(self) -> ProviderDescriptor:
    ...
  ####

  def create_session(self) -> PlumeSession:
    ...
  ####
####
