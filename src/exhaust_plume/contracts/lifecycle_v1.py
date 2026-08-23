"""Generic provider/session/immutable-snapshot lifecycle for v1 products."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Generic, Mapping, Protocol, TypeVar, runtime_checkable

from exhaust_plume.contracts.common_v1 import (
  ApiModel,
  CapabilityIdentity,
  ProviderDescriptor,
  SessionMetadata,
  SnapshotMetadata,
)
from exhaust_plume.contracts.errors import (
  InvalidProductRequestError,
  UnsupportedProductCapabilityError,
  UnsupportedProductVersionError,
)

RequestT = TypeVar('RequestT', bound=ApiModel)
ResultT = TypeVar('ResultT', bound=ApiModel)
EvaluatorRequestT = TypeVar('EvaluatorRequestT', bound=ApiModel, contravariant=True)
EvaluatorResultT = TypeVar('EvaluatorResultT', bound=ApiModel, covariant=True)
####


@dataclass(frozen=True, slots=True)
class CapabilitySpec(Generic[RequestT, ResultT]):
  """Request/result types associated with one versioned capability."""

  capability: CapabilityIdentity
  request_type: type[RequestT]
  result_type: type[ResultT]
  ####
####


class CapabilityEvaluator(Protocol[EvaluatorRequestT, EvaluatorResultT]):
  def evaluate(self, request: EvaluatorRequestT, snapshot: SnapshotMetadata) -> EvaluatorResultT:
    ...
  ####
####


@runtime_checkable
class ProductSnapshot(Protocol):
  @property
  def metadata(self) -> SnapshotMetadata:
    ...
  ####

  def supports(self, capability: CapabilityIdentity) -> bool:
    ...
  ####

  def evaluate(self, capability: CapabilitySpec[RequestT, ResultT], request: RequestT) -> ResultT:
    ...
  ####
####


@runtime_checkable
class ProductSession(Protocol):
  @property
  def metadata(self) -> SessionMetadata:
    ...
  ####

  def create_snapshot(
      self,
      *,
      time_s: float,
      source_pose: Any,
      dynamic_state: Mapping[str, Any],
      ambient_state: Mapping[str, Any],
  ) -> ProductSnapshot:
    ...
  ####

  def close(self) -> None:
    ...
  ####
####


@runtime_checkable
class ProductProvider(Protocol):
  @property
  def descriptor(self) -> ProviderDescriptor:
    ...
  ####

  def create_session(
      self,
      *,
      definition: Mapping[str, Any],
      configuration: Mapping[str, Any],
  ) -> ProductSession:
    ...
  ####
####


@dataclass(frozen=True, slots=True)
class ImmutableProductSnapshot:
  """Small provider-neutral snapshot dispatcher used by contract providers."""

  metadata: SnapshotMetadata
  _evaluators: Mapping[CapabilityIdentity, CapabilityEvaluator[Any, Any]]

  def __post_init__(self) -> None:
    object.__setattr__(self, '_evaluators', MappingProxyType(dict(self._evaluators)))
  ####

  def supports(self, capability: CapabilityIdentity) -> bool:
    return capability in self._evaluators
  ####

  def evaluate(self, capability: CapabilitySpec[RequestT, ResultT], request: RequestT) -> ResultT:
    if not self.supports(capability.capability):
      if any(candidate.name == capability.capability.name for candidate in self._evaluators):
        raise UnsupportedProductVersionError(
            f'unsupported major version for {capability.capability.name}: {capability.capability.major}'
        )
      raise UnsupportedProductCapabilityError(f'unsupported capability: {capability.capability.wire_id}')
    if not isinstance(request, capability.request_type):
      raise InvalidProductRequestError(
          f'{capability.capability.wire_id} requires {capability.request_type.__name__}'
      )
    result = self._evaluators[capability.capability].evaluate(request, self.metadata)
    if not isinstance(result, capability.result_type):
      raise TypeError(
          f'{capability.capability.wire_id} evaluator returned {type(result).__name__}, '
          f'expected {capability.result_type.__name__}'
      )
    return result
  ####
####


VISUAL_SECTIONED_TUBE_V1: CapabilitySpec[Any, Any]
SPECTRAL_RADIANT_INTENSITY_V1: CapabilitySpec[Any, Any]
SPECTRAL_RAY_TRANSFER_V1: CapabilitySpec[Any, Any]
####


__all__ = (
  'CapabilityEvaluator',
  'CapabilitySpec',
  'ImmutableProductSnapshot',
  'ProductProvider',
  'ProductSession',
  'ProductSnapshot',
  'RequestT',
  'ResultT',
)
####
