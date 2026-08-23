"""Provider/session/snapshot lifecycle protocols and capability lookup."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Generic, Mapping, Protocol, TypeVar

from exhaust_plume.contracts.capability import CapabilityId
from exhaust_plume.contracts.descriptor import PlumeProviderDescriptor
from exhaust_plume.contracts.errors import CapabilityVersionMismatchError, ContractViolationError, UnsupportedCapabilityError
from exhaust_plume.contracts.provenance import PlumeProvenance

DefinitionT = TypeVar('DefinitionT', contravariant=True)
ConfigurationT = TypeVar('ConfigurationT', contravariant=True)
OperatingStateT = TypeVar('OperatingStateT', contravariant=True)


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


class TerminationReason(str, Enum):
  NO_PRESSURE_MISMATCH = 'no-pressure-mismatch'
  WEAK_WAVE_CUTOFF = 'weak-wave-cutoff'
  PRESSURE_OSCILLATION_DECAYED = 'pressure-oscillation-decayed'
  MIXING_LAYER_REACHED_AXIS = 'mixing-layer-reached-axis'
  CORE_BECAME_SUBSONIC = 'core-became-subsonic'
  AMBIENT_EQUILIBRIUM = 'ambient-equilibrium'
  MACH_DISK_REQUIRED = 'mach-disk-required'
  NOZZLE_SEPARATION_NOT_MODELED = 'nozzle-separation-not-modeled'
  SPATIAL_DOMAIN_LIMIT = 'spatial-domain-limit'
  TEMPORAL_DOMAIN_LIMIT = 'temporal-domain-limit'
  REQUESTED_CONSTRUCTION_LIMIT = 'requested-construction-limit'
  MAX_CELL_LIMIT = 'max-cell-limit'
  DETACHED_SHOCK_REQUIRED = 'detached-shock-required'
  NUMERICAL_FAILURE = 'numerical-failure'
  PROVIDER_FAILURE = 'provider-failure'
####


@dataclass(frozen=True, slots=True)
class TerminationReport:
  """Structured endpoint metadata separate from snapshot validity."""

  reason: TerminationReason
  is_physical: bool
  message: str
  diagnostics: Mapping[str, float | str] = field(default_factory=dict)

  def __post_init__(self) -> None:
    if not self.message:
      raise ValueError('termination message must not be empty')
    ####
    object.__setattr__(self, 'diagnostics', MappingProxyType(dict(self.diagnostics)))
  ####
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
