"""Compatibility provider/session/snapshot lifecycle and capability lookup.

The canonical lifecycle is in ``contracts.lifecycle_v1``. This module keeps
the older solver-facing snapshot ABI available for 0.1.x consumers.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Generic, Mapping, Protocol, TypeVar

from exhaust_plume.contracts.capability import CapabilityId
from exhaust_plume.contracts.descriptor import PlumeProviderDescriptor
from exhaust_plume.contracts.errors import CapabilityVersionMismatchError, ContractViolationError, UnsupportedCapabilityError
from exhaust_plume.contracts.provenance import PlumeProvenance
from exhaust_plume.contracts.termination import TerminationReason as _TerminationReason, TerminationReport

DefinitionT = TypeVar('DefinitionT', contravariant=True)
ConfigurationT = TypeVar('ConfigurationT', contravariant=True)
OperatingStateT = TypeVar('OperatingStateT', contravariant=True)

TerminationReason = _TerminationReason


class PlumeCapability(Protocol):
  """Minimum metadata required of a capability object."""

  @property
  def capability_id(self) -> CapabilityId:
    ...

  @property
  def major_version(self) -> int:
    ...
####


class PlumeProvider(Protocol, Generic[DefinitionT, ConfigurationT, OperatingStateT]):
  """Provider-specific definition/configuration with generic outputs."""

  @property
  def descriptor(self) -> PlumeProviderDescriptor:
    ...

  def create_session(self, definition: DefinitionT, configuration: ConfigurationT) -> PlumeSession[OperatingStateT]:
    ...
####


class PlumeSession(Protocol, Generic[OperatingStateT]):
  """Session that turns an operating state into a retained snapshot."""

  def snapshot(self, operating_state: OperatingStateT) -> PlumeSnapshot:
    ...

  def close(self) -> None:
    ...
####


@dataclass(frozen=True, slots=True)
class PlumeSnapshot:
  """Immutable capability registry and provenance for one operating state."""

  descriptor: PlumeProviderDescriptor
  provenance: PlumeProvenance
  capabilities: Mapping[CapabilityId, PlumeCapability]
  termination: TerminationReport | None = None
  snapshot_id: str = 'snapshot-0'

  def __post_init__(self) -> None:
    if not self.snapshot_id:
      raise ValueError('snapshot_id must not be empty')
    ####
    normalized = dict(self.capabilities)
    if set(normalized) != set(self.descriptor.capability_versions):
      raise ContractViolationError('descriptor capability registry must equal snapshot capability objects')
    ####
    for capability_id, capability in normalized.items():
      if capability.capability_id != capability_id:
        raise ContractViolationError(f'capability object has wrong id: {capability_id}')
      ####
      expected_version = self.descriptor.capability_versions[capability_id]
      if capability.major_version != expected_version:
        raise ContractViolationError(f'capability object has wrong major version: {capability_id}')
      ####
    ####
    object.__setattr__(self, 'capabilities', MappingProxyType(normalized))
  ####

  def get_capability(self, capability_id: CapabilityId, major_version: int) -> PlumeCapability:
    """Return an advertised capability or raise an explicit typed error."""

    if capability_id not in self.capabilities:
      raise UnsupportedCapabilityError(f'Unsupported capability: {capability_id.value}')
    ####
    supported_version = self.descriptor.capability_versions[capability_id]
    if supported_version != major_version:
      raise CapabilityVersionMismatchError(
          f'Capability {capability_id.value} supports major version {supported_version}, requested {major_version}'
      )
    ####
    return self.capabilities[capability_id]
  ####
####
