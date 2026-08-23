"""Reusable pytest checks for canonical v1 provider lifecycle semantics.

Provider-specific construction belongs in a small :class:`ProviderFixture`.
The checks below deliberately know only the canonical lifecycle and product
contracts, so a new provider can opt in without changing this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import FrozenInstanceError
from math import isfinite
from typing import Any, Callable

import pytest

from exhaust_plume.api import v1
from exhaust_plume.contracts.errors import (
  ProviderClosedError,
  UnsupportedProductCapabilityError,
  UnsupportedProductVersionError,
)
from exhaust_plume.contracts.handoff import PlumeFluxSection

ProviderFactory = Callable[[], Any]
SessionFactory = Callable[[Any], v1.ProductSession]
SnapshotFactory = Callable[[v1.ProductSession, float], v1.ProductSnapshot]


@dataclass(frozen=True, slots=True)
class ProductConformanceCase:
  """One typed request plus optional partial-batch coverage."""

  capability: v1.CapabilitySpec[Any, Any]
  request: v1.ApiModel
  expected_frame_id: str
  partial_request: v1.ApiModel | None = None
  partial_invalid_indices: tuple[int, ...] = ()
####


@dataclass(frozen=True, slots=True)
class ProviderFixture:
  """Provider-specific construction data consumed by the common harness."""

  name: str
  provider_factory: ProviderFactory
  session_factory: SessionFactory
  snapshot_factory: SnapshotFactory
  products: tuple[ProductConformanceCase, ...]
  unsupported_capabilities: tuple[v1.CapabilityIdentity, ...] = ()
  probe_times_s: tuple[float, ...] = (0.0, 1.0)
  engineering_sections: tuple[PlumeFluxSection, ...] = ()
####


@dataclass(frozen=True, slots=True)
class ConformanceReport:
  """Small evidence record returned after a fixture passes."""

  provider_name: str
  provider_id: str
  supported_capabilities: tuple[str, ...]
  result_ids: tuple[str, ...]
  deterministic_serialization: bool
  immutable_snapshot: bool
  session_closure: bool
  unsupported_capabilities_checked: tuple[str, ...]
  unsupported_versions_checked: tuple[str, ...]
  partial_batch_checked: bool
  engineering_sections_checked: int
  passed: bool = True
####


def run_provider_conformance(fixture: ProviderFixture) -> ConformanceReport:
  """Run lifecycle, negotiation, and product checks for one provider fixture."""

  if not fixture.products:
    raise AssertionError(f'{fixture.name} must declare at least one product request')
  ####
  provider = fixture.provider_factory()
  descriptor = provider.descriptor
  expected_capabilities = tuple(product.capability.capability for product in fixture.products)
  expected_wire_ids = {capability.wire_id for capability in expected_capabilities}
  advertised_wire_ids = {capability.wire_id for capability in descriptor.supported_capabilities}
  if advertised_wire_ids != expected_wire_ids:
    raise AssertionError(
      f'{fixture.name} descriptor capabilities {sorted(advertised_wire_ids)!r} do not match '
      f'fixture products {sorted(expected_wire_ids)!r}'
    )
  ####

  session = fixture.session_factory(provider)
  assert session.metadata.provider_id == descriptor.provider_id
  assert session.metadata.provider_version == descriptor.provider_version

  snapshots: list[v1.ProductSnapshot] = []
  for time_s in fixture.probe_times_s:
    snapshot = fixture.snapshot_factory(session, time_s)
    snapshots.append(snapshot)
    assert snapshot.metadata.session_id == session.metadata.session_id
    assert snapshot.metadata.time_s == time_s
    for capability in descriptor.supported_capabilities:
      if not snapshot.supports(capability):
        raise AssertionError(
          f'{fixture.name} advertises {capability.wire_id} but its snapshot does not support it'
        )
      ####
    ####
  ####

  snapshot = snapshots[0]
  immutable_snapshot = _assert_snapshot_immutability(snapshot)
  result_ids: list[str] = []
  partial_batch_checked = False
  for product in fixture.products:
    result = _evaluate_and_check(snapshot, product, descriptor)
    result_ids.append(result.metadata.result_id)
    repeated = _evaluate_and_check(snapshot, product, descriptor)
    assert result.model_dump(mode='json') == repeated.model_dump(mode='json')
    if product.partial_request is not None:
      partial = _evaluate_and_check(
        snapshot,
        ProductConformanceCase(
          capability=product.capability,
          request=product.partial_request,
          expected_frame_id=product.expected_frame_id,
          partial_invalid_indices=product.partial_invalid_indices,
        ),
        descriptor,
      )
      _assert_partial_semantics(partial, product.partial_invalid_indices)
      partial_batch_checked = True
    ####
  ####

  if descriptor.deterministic:
    fresh_provider = fixture.provider_factory()
    fresh_session = fixture.session_factory(fresh_provider)
    fresh_snapshot = fixture.snapshot_factory(fresh_session, fixture.probe_times_s[0])
    for product in fixture.products:
      fresh_result = _evaluate_and_check(fresh_snapshot, product, fresh_provider.descriptor)
      first_result = _evaluate_and_check(snapshot, product, descriptor)
      assert first_result.model_dump(mode='json') == fresh_result.model_dump(mode='json')
    ####
  ####

  unsupported_checked: list[str] = []
  unsupported_versions_checked: list[str] = []
  for capability in fixture.unsupported_capabilities:
    assert capability.wire_id not in advertised_wire_ids
    specification = v1.get_product_capability_spec(capability)
    with pytest.raises(UnsupportedProductCapabilityError):
      snapshot.evaluate(specification, _default_request(specification))
    ####
    unsupported_checked.append(capability.wire_id)
  ####

  for product in fixture.products:
    capability = product.capability.capability
    unsupported_version = v1.CapabilityIdentity(name=capability.name, major=capability.major + 1)
    unsupported_specification = v1.CapabilitySpec(
      capability=unsupported_version,
      request_type=product.capability.request_type,
      result_type=product.capability.result_type,
    )
    with pytest.raises(UnsupportedProductVersionError):
      snapshot.evaluate(unsupported_specification, product.request)
    ####
    unsupported_versions_checked.append(unsupported_version.wire_id)
  ####

  session.close()
  with pytest.raises(ProviderClosedError):
    fixture.snapshot_factory(session, fixture.probe_times_s[0])
  ####

  for section in fixture.engineering_sections:
    assert_engineering_flux_section(section)
  ####

  return ConformanceReport(
    provider_name=fixture.name,
    provider_id=descriptor.provider_id,
    supported_capabilities=tuple(sorted(advertised_wire_ids)),
    result_ids=tuple(result_ids),
    deterministic_serialization=True,
    immutable_snapshot=immutable_snapshot,
    session_closure=True,
    unsupported_capabilities_checked=tuple(unsupported_checked),
    unsupported_versions_checked=tuple(unsupported_versions_checked),
    partial_batch_checked=partial_batch_checked,
    engineering_sections_checked=len(fixture.engineering_sections),
  )
####


def _assert_snapshot_immutability(snapshot: v1.ProductSnapshot) -> bool:
  before = snapshot.metadata.model_dump(mode='json')
  try:
    setattr(snapshot, 'metadata', snapshot.metadata)
  except (AttributeError, FrozenInstanceError, TypeError):
    pass
  else:
    raise AssertionError('canonical snapshots must reject metadata mutation')
  ####
  assert snapshot.metadata.model_dump(mode='json') == before
  return True
####


def _evaluate_and_check(
    snapshot: v1.ProductSnapshot,
    product: ProductConformanceCase,
    descriptor: v1.ProviderDescriptor,
) -> Any:
  result = snapshot.evaluate(product.capability, product.request)
  if not isinstance(result, product.capability.result_type):
    raise AssertionError(
      f'{descriptor.provider_id} returned {type(result).__name__} for '
      f'{product.capability.capability.wire_id}; expected {product.capability.result_type.__name__}'
    )
  ####
  assert result.metadata.capability == product.capability.capability
  assert result.metadata.snapshot == snapshot.metadata
  assert result.metadata.output_frame_id == product.expected_frame_id
  assert result.metadata.provenance.provider_id == descriptor.provider_id
  assert result.metadata.provenance.provider_version == descriptor.provider_version
  _assert_product_result(result, product.request)
  return result
####


def _assert_product_result(result: Any, request: v1.ApiModel) -> None:
  if isinstance(result, v1.VisualSectionedTubeResult):
    assert len(result.sections) >= 2
    assert all(
      next_section.arc_length_m > section.arc_length_m
      for section, next_section in zip(result.sections, result.sections[1:])
    )
    for values in result.channels.values():
      assert len(values) == len(result.sections)
    ####
    return
  ####
  if isinstance(result, v1.SpectralSignatureResult):
    direction_count = len(result.spectral_radiant_intensity)
    wavelength_count = len(request.wavelengths_m)  # type: ignore[attr-defined]
    assert direction_count == len(request.source_to_observer_directions)  # type: ignore[attr-defined]
    assert all(len(row) == wavelength_count for row in result.spectral_radiant_intensity)
    assert len(result.direction_status) == direction_count
    assert len(result.validity_mask) == direction_count
    return
  ####
  if isinstance(result, v1.VersionedSpectralRayTransferResult):
    ray_count = len(request.ray_origins_m)  # type: ignore[attr-defined]
    wavelength_count = len(request.wavelengths_m)  # type: ignore[attr-defined]
    assert len(result.source_spectral_radiance) == ray_count
    assert all(len(row) == wavelength_count for row in result.source_spectral_radiance)
    assert len(result.ray_status) == ray_count
    assert len(result.hit_mask) == ray_count
    for index, status in enumerate(result.ray_status):
      if status.code is v1.SampleStatusCode.OK:
        assert all(result.validity_mask[index])
        continue
      ####
      assert not result.hit_mask[index]
      assert not any(result.validity_mask[index])
    ####
    return
  ####
  raise AssertionError(f'no canonical product checks registered for {type(result).__name__}')
####


def _assert_partial_semantics(result: Any, invalid_indices: tuple[int, ...]) -> None:
  if isinstance(result, v1.SpectralSignatureResult):
    invalid = set(invalid_indices)
    for index, status in enumerate(result.direction_status):
      if index in invalid:
        assert status.code is v1.SampleStatusCode.OUTSIDE_APPLICABILITY
        assert not any(result.validity_mask[index])
        assert all(value == 0.0 for value in result.spectral_radiant_intensity[index])
      else:
        assert status.code is v1.SampleStatusCode.OK
        assert all(result.validity_mask[index])
      ####
    ####
    return
  ####
  if isinstance(result, v1.VersionedSpectralRayTransferResult):
    invalid = set(invalid_indices)
    for index, status in enumerate(result.ray_status):
      if index in invalid:
        assert status.code is not v1.SampleStatusCode.OK
        assert not result.hit_mask[index]
      else:
        assert status.code is v1.SampleStatusCode.OK
      ####
    ####
    return
  ####
  raise AssertionError(f'partial results are not defined for {type(result).__name__}')
####


def _default_request(specification: v1.CapabilitySpec[Any, Any]) -> v1.ApiModel:
  if specification is v1.VISUAL_SECTIONED_TUBE_V1:
    return v1.VisualSectionedTubeRequest(
      output_frame_id='source-local',
      sampling=v1.VisualSampling(maximum_section_count=2),
    )
  ####
  if specification is v1.SPECTRAL_RADIANT_INTENSITY_V1:
    return v1.SpectralSignatureRequest(
      direction_frame_id='source-local',
      source_to_observer_directions=((0.0, 1.0, 0.0),),
      wavelengths_m=(1.0e-6,),
    )
  ####
  if specification is v1.SPECTRAL_RAY_TRANSFER_V1:
    return v1.SpectralRayTransferRequest(
      ray_frame_id='source-local',
      ray_origins_m=((0.0, 0.0, 0.0),),
      ray_directions=((1.0, 0.0, 0.0),),
      ray_t_min_m=(0.0,),
      ray_t_max_m=(1.0,),
      wavelengths_m=(1.0e-6,),
    )
  ####
  raise AssertionError(f'no default request for {specification.capability.wire_id}')
####


def assert_engineering_flux_section(section: PlumeFluxSection) -> None:
  """Check the neutral engineering handoff without asserting solver physics."""

  assert len(section.center_plume_m) == 3
  assert len(section.normal_plume) == 3
  assert len(section.momentum_flux_plume_n) == 3
  assert all(isfinite(value) for value in (
    *section.center_plume_m,
    *section.normal_plume,
    *section.momentum_flux_plume_n,
  ))
  assert section.area_m2 > 0.0
  assert section.mass_flow_kg_s > 0.0
  assert section.total_enthalpy_flux_w > 0.0
  assert section.pressure_Pa > 0.0
  assert section.characteristic_radius_m > 0.0
  assert all(rate >= 0.0 for _, rate in section.species_mass_flow_rates_kg_s)
####


__all__ = (
  'ConformanceReport',
  'ProductConformanceCase',
  'ProviderFixture',
  'assert_engineering_flux_section',
  'run_provider_conformance',
)
