"""Provenance carried by every provider snapshot."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True, slots=True)
class PlumeProvenance:
  """Identity of the provider and source artifacts behind a snapshot."""

  provider_id: str
  provider_version: str
  source_references: tuple[str, ...] = ()
  calibration_id: str | None = None
  metadata: Mapping[str, str] = field(default_factory=dict)

  def __post_init__(self) -> None:
    if not self.provider_id or not self.provider_version:
      raise ValueError('provenance provider identity must not be empty')
    ####
    object.__setattr__(self, 'source_references', tuple(self.source_references))
    object.__setattr__(self, 'metadata', MappingProxyType(dict(self.metadata)))
  ####
####
