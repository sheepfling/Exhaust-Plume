"""Provider identity, fidelity, morphology, and applicability descriptors."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import isfinite
from types import MappingProxyType
from typing import Mapping

from exhaust_plume.contracts.capability import CapabilityId
from exhaust_plume.contracts.execution import ProviderExecutionProfile


class PlumeMorphology(str, Enum):
  STRAIGHT = 'straight'
  CURVED = 'curved'
  ROTOR_WASHED = 'rotor-washed'
  CROSSFLOW_DEFLECTED = 'crossflow-deflected'
  MULTI_SOURCE = 'multi-source'
  GENERAL_3D = 'general-3d'
  ####


@dataclass(frozen=True, slots=True)
class ProviderFidelity:
  """Orthogonal fidelity labels carried as metadata."""

  geometry_model: str
  spatial_dimensionality: str
  temporal_model: str
  flow_model: str
  mixing_model: str
  thermochemistry_model: str
  radiation_model: str
  environmental_coupling: str
  validation_level: str
  ####


@dataclass(frozen=True, slots=True)
class ProviderApplicability:
  """Human-readable and numeric applicability information."""

  summary: str
  bounds: Mapping[str, tuple[float | None, float | None]] = field(default_factory=dict)
  supported_species: tuple[str, ...] = ()

  def __post_init__(self) -> None:
    if not self.summary:
      raise ValueError('applicability summary must not be empty')
    normalized: dict[str, tuple[float | None, float | None]] = {}
    for name, bound in self.bounds.items():
      if len(bound) != 2:
        raise ValueError(f'applicability bound `{name}` must have two values')
      lower, upper = bound
      if lower is not None and not isfinite(lower):
        raise ValueError(f'applicability lower bound `{name}` must be finite')
      if upper is not None and not isfinite(upper):
        raise ValueError(f'applicability upper bound `{name}` must be finite')
      if lower is not None and upper is not None and lower > upper:
        raise ValueError(f'applicability lower bound `{name}` exceeds upper bound')
      normalized[name] = (lower, upper)
    object.__setattr__(self, 'bounds', MappingProxyType(normalized))
    object.__setattr__(self, 'supported_species', tuple(self.supported_species))
    ####
  ####
####


@dataclass(frozen=True, slots=True)
class PlumeProviderDescriptor:
  """Immutable descriptor used for provider selection before execution."""

  provider_id: str
  provider_version: str
  core_contract_major_version: int
  capability_versions: Mapping[CapabilityId, int]
  definition_schema_id: str
  configuration_schema_id: str
  operating_state_schema_id: str
  morphology: PlumeMorphology
  fidelity: ProviderFidelity
  execution: ProviderExecutionProfile
  applicability: ProviderApplicability

  def __post_init__(self) -> None:
    if not self.provider_id or not self.provider_version:
      raise ValueError('provider_id and provider_version must not be empty')
    if self.core_contract_major_version < 1:
      raise ValueError('core_contract_major_version must be positive')
    normalized: dict[CapabilityId, int] = {}
    for capability_id, major_version in self.capability_versions.items():
      if not isinstance(capability_id, CapabilityId):
        raise TypeError('capability_versions keys must be CapabilityId values')
      if major_version < 1:
        raise ValueError(f'capability major version must be positive: {capability_id}')
      normalized[capability_id] = int(major_version)
    object.__setattr__(self, 'capability_versions', MappingProxyType(normalized))
    ####
  ####
####
