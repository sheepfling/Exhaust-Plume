"""Deterministic static providers used for fixtures and conformance tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from types import MappingProxyType, TracebackType
from typing import Mapping

from exhaust_plume.products import CapabilityId, PlumeProduct
from exhaust_plume.providers.lifecycle import (
    ClosedSessionError,
    ExecutionBackend,
    PlumeSnapshot,
    ProviderDescriptor,
    SessionRequest,
    TimeAccessMode,
    UnsupportedCapabilityError,
)


@dataclass(frozen=True)
class StaticPlumeSnapshot:
  """Immutable product mapping at one deterministic time."""

  descriptor: ProviderDescriptor
  snapshot_id: str
  time_s: float
  _products: Mapping[CapabilityId, PlumeProduct] = field(repr=False)

  def __post_init__(self) -> None:
    if not self.snapshot_id:
      raise ValueError('Expected a non-empty snapshot_id.')
    ####
    if not isfinite(self.time_s):
      raise ValueError('Expected finite time_s.')
    ####
    products = dict(self._products)
    if not products:
      raise ValueError('Expected at least one static product.')
    ####
    advertised = set(self.descriptor.capabilities)
    supplied = set(products)
    if supplied != advertised:
      raise ValueError(
          f'Static products {sorted(map(str, supplied))} do not match advertised '
          f'capabilities {sorted(map(str, advertised))}.'
      )
    ####
    for capability, product in products.items():
      if product.metadata.capability != capability:
        raise ValueError(
            f'Product metadata capability {product.metadata.capability} does not match '
            f'its static binding {capability}.'
        )
      ####
      if product.metadata.snapshot_id != self.snapshot_id:
        raise ValueError('Every static product must reference the snapshot_id that owns it.')
      ####
      if product.metadata.time_s != self.time_s:
        raise ValueError('Every static product must reference the snapshot time that owns it.')
      ####
    ####
    object.__setattr__(self, '_products', MappingProxyType(products))
  ####

  @property
  def capabilities(self) -> tuple[CapabilityId, ...]:
    return self.descriptor.capabilities
  ####

  def getProduct(self, capability: CapabilityId) -> PlumeProduct:
    try:
      return self._products[capability]
    except KeyError as exc:
      raise UnsupportedCapabilityError(
          provider_id=self.descriptor.provider_id,
          capability=capability,
      ) from exc
    ####
  ####
####


@dataclass
class StaticPlumeSession:
  """Session that returns one immutable static snapshot."""

  descriptor: ProviderDescriptor
  _snapshot: StaticPlumeSnapshot
  _is_closed: bool = False

  @property
  def is_closed(self) -> bool:
    return self._is_closed
  ####

  def snapshot(self, time_s: float) -> PlumeSnapshot:
    if self._is_closed:
      raise ClosedSessionError('Cannot obtain a snapshot from a closed session.')
    ####
    if self.descriptor.time_access_mode is TimeAccessMode.STATIC and time_s != self._snapshot.time_s:
      raise ValueError(
          f'Static provider only supports time {self._snapshot.time_s}. Got:{time_s}'
      )
    ####
    return self._snapshot
  ####

  def close(self) -> None:
    self._is_closed = True
  ####

  def __enter__(self) -> StaticPlumeSession:
    if self._is_closed:
      raise ClosedSessionError('Cannot enter a closed session.')
    ####
    return self
  ####

  def __exit__(
      self,
      exc_type: type[BaseException] | None,
      exc: BaseException | None,
      traceback: TracebackType | None,
  ) -> None:
    del exc_type, exc, traceback
    self.close()
  ####
####


@dataclass(frozen=True)
class StaticPlumeProvider:
  """Prescribed product provider for static fixtures and consumer integration."""

  descriptor: ProviderDescriptor
  product_by_capability: Mapping[CapabilityId, PlumeProduct] = field(repr=False)
  snapshot_id: str = 'static-snapshot'
  time_s: float = 0.

  def __post_init__(self) -> None:
    if self.descriptor.time_access_mode is not TimeAccessMode.STATIC:
      raise ValueError('StaticPlumeProvider requires TimeAccessMode.STATIC.')
    ####
    object.__setattr__(self, 'product_by_capability', MappingProxyType(dict(self.product_by_capability)))
    StaticPlumeSnapshot(
        descriptor=self.descriptor,
        snapshot_id=self.snapshot_id,
        time_s=self.time_s,
        _products=self.product_by_capability,
    )
  ####

  def createSession(self, request: SessionRequest = SessionRequest()) -> StaticPlumeSession:
    backend = request.backend
    if backend is ExecutionBackend.AUTO:
      backend = self.descriptor.supported_backends[0]
    ####
    if backend not in self.descriptor.supported_backends:
      raise ValueError(
          f'Backend {backend.value!r} is not supported by provider '
          f'{self.descriptor.provider_id!r}.'
      )
    ####
    snapshot = StaticPlumeSnapshot(
        descriptor=self.descriptor,
        snapshot_id=self.snapshot_id,
        time_s=self.time_s,
        _products=self.product_by_capability,
    )
    return StaticPlumeSession(descriptor=self.descriptor, _snapshot=snapshot)
  ####
####
