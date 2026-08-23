"""Provider execution and snapshot lifetime metadata."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TimeAccessMode(str, Enum):
  RANDOM_ACCESS = 'random-access'
  MONOTONIC_FORWARD = 'monotonic-forward'
####


class ConcurrencyMode(str, Enum):
  SERIAL = 'serial'
  REENTRANT = 'reentrant'
  BATCHED = 'batched'
####


class SnapshotRetention(str, Enum):
  INDEPENDENT = 'independent'
  UNTIL_NEXT_SNAPSHOT = 'until-next-snapshot'
  UNTIL_SESSION_CLOSE = 'until-session-close'
####


@dataclass(frozen=True, slots=True)
class ProviderExecutionProfile:
  """Execution constraints independent of physical fidelity."""

  time_access: TimeAccessMode
  concurrency: ConcurrencyMode
  deterministic: bool
  supports_direction_batching: bool
  maximum_direction_batch_size: int | None
  checkpointable: bool
  preferred_device: str
  snapshot_retention: SnapshotRetention

  def __post_init__(self) -> None:
    if not self.preferred_device:
      raise ValueError('preferred_device must not be empty')
    ####
    if self.maximum_direction_batch_size is not None and self.maximum_direction_batch_size < 1:
      raise ValueError('maximum_direction_batch_size must be positive when supplied')
    ####
    if self.supports_direction_batching and self.maximum_direction_batch_size == 0:
      raise ValueError('direction batching cannot have a zero maximum size')
    ####
  ####
####
