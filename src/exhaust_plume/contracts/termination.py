"""Provider-neutral termination metadata shared by solver and product layers."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Mapping


class TerminationReason(str, Enum):
  """Structured reason a bounded plume construction stopped."""

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


__all__ = ('TerminationReason', 'TerminationReport')
