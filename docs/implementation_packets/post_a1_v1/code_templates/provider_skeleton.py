"""Reference-only skeleton for a canonical product provider."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class CanonicalSnapshot(Protocol):
  def get_product(self, capability_id: str, request: object) -> object:
    """Evaluate one independently versioned product."""
    ...
  ####
####


@dataclass(frozen=True, slots=True)
class ProviderDefinition:
  source_frame_id: str
####


@dataclass(frozen=True, slots=True)
class ProviderConfiguration:
  deterministic: bool = True
####


class ProviderSession:
  """Own reusable setup; snapshots remain immutable."""

  def __init__(self, definition: ProviderDefinition, configuration: ProviderConfiguration) -> None:
    self._definition = definition
    self._configuration = configuration
    self._closed = False
  ####

  def snapshot(self, operating_state: object) -> CanonicalSnapshot:
    if self._closed:
      raise RuntimeError('session is closed')
    ####
    raise NotImplementedError
  ####

  def close(self) -> None:
    self._closed = True
  ####
####
