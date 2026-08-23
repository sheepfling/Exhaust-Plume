from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pytest

from exhaust_plume.contracts import (
    AngularDomainError,
    CapabilityId,
    CapabilityVersionMismatchError,
    ConcurrencyMode,
    DirectionalSpectralIntensityQuery,
    DirectionalSpectralIntensityResult,
    PlumeMorphology,
  PlumeProviderDescriptor,
  PlumeProvenance,
  PlumeSnapshot,
  ProviderClosedError,
    ProviderApplicability,
    ProviderExecutionProfile,
    ProviderFidelity,
    SnapshotInvalidatedError,
    SnapshotRetention,
    SpatialSupport,
    SpectralRayTransferQuery,
    SpectralRayTransferResult,
    SpectralDomainError,
    TimeAccessMode,
    UnsupportedCapabilityError,
)


@dataclass(frozen=True, slots=True)
class _FixtureDefinition:
  name: str = 'fixture'
  ####


@dataclass(frozen=True, slots=True)
class _FixtureConfiguration:
  scale: float = 1.0
  ####


@dataclass(frozen=True, slots=True)
class _FixtureOperatingState:
  epoch_s: float = 0.0
  ####


def _descriptor(*capability_ids: CapabilityId, retention: SnapshotRetention = SnapshotRetention.INDEPENDENT) -> PlumeProviderDescriptor:
  return PlumeProviderDescriptor(
      provider_id='fixture.provider',
      provider_version='1.0.0',
      core_contract_major_version=1,
      capability_versions={capability_id: 1 for capability_id in capability_ids},
      definition_schema_id='fixture.definition.v1',
      configuration_schema_id='fixture.configuration.v1',
      operating_state_schema_id='fixture.operating-state.v1',
      morphology=PlumeMorphology.STRAIGHT,
      fidelity=ProviderFidelity(
          geometry_model='fixture',
          spatial_dimensionality='planar',
          temporal_model='steady',
          flow_model='fixture',
          mixing_model='none',
          thermochemistry_model='frozen',
          radiation_model='fixture',
          environmental_coupling='none',
          validation_level='contract-fixture',
      ),
      execution=ProviderExecutionProfile(
          time_access=TimeAccessMode.RANDOM_ACCESS,
          concurrency=ConcurrencyMode.REENTRANT,
          deterministic=True,
          supports_direction_batching=True,
          maximum_direction_batch_size=64,
          checkpointable=False,
          preferred_device='cpu',
          snapshot_retention=retention,
      ),
      applicability=ProviderApplicability(
          summary='finite fixture domain',
          bounds={'wavelength_m': (1.0e-6, 20.0e-6)},
          supported_species=('fixture-gas',),
      ),
  )
####


def _provenance() -> PlumeProvenance:
  return PlumeProvenance(
      provider_id='fixture.provider',
      provider_version='1.0.0',
      source_references=('fixture://contract',),
      calibration_id='fixture-calibration-v1',
  )
####


@dataclass(frozen=True, slots=True)
class _SignatureOnlyCapability:
  capability_id: CapabilityId = CapabilityId.DIRECTIONAL_SPECTRAL_INTENSITY
  major_version: int = 1

  def evaluate(self, query: DirectionalSpectralIntensityQuery) -> DirectionalSpectralIntensityResult:
    values = np.full((query.source_to_observer_direction_plume.shape[0], 1), 2.0)
    intensity = np.repeat(values, query.wavelength_m.shape[0], axis=1)
    return DirectionalSpectralIntensityResult(
        wavelength_m=query.wavelength_m,
        source_to_observer_direction_plume=query.source_to_observer_direction_plume,
        spectral_radiant_intensity_w_sr_m=intensity,
        quality_flags=(),
        provenance_id='fixture-signature',
    )
  ####
####


@dataclass(frozen=True, slots=True)
class _SpatialOnlyCapability:
  support: SpatialSupport
  capability_id: CapabilityId = CapabilityId.SPATIAL_SUPPORT
  major_version: int = 1
  ####


@dataclass(frozen=True, slots=True)
class _RayCapability:
  capability_id: CapabilityId = CapabilityId.SPECTRAL_RAY_TRANSFER
  major_version: int = 1

  def transfer(self, query: SpectralRayTransferQuery) -> SpectralRayTransferResult:
    shape = (query.observer_origin_plume_m.shape[0], query.wavelength_m.shape[0])
    return SpectralRayTransferResult(
        source_spectral_radiance_w_sr_m=np.full(shape, 2.0),
        background_transmittance=np.full(shape, 0.5),
        provenance_id='fixture-ray',
    )
  ####
####


class _FixtureSession:
  def __init__(self, snapshot: PlumeSnapshot) -> None:
    self._snapshot = snapshot
    self._closed = False
    ####

  def snapshot(self, operating_state: _FixtureOperatingState) -> PlumeSnapshot:
    if self._closed:
      raise ProviderClosedError('fixture session closed')
    assert operating_state.epoch_s >= 0
    return self._snapshot
  ####

  def close(self) -> None:
    self._closed = True
    ####
####


class _SignatureOnlyProvider:
  descriptor = _descriptor(CapabilityId.DIRECTIONAL_SPECTRAL_INTENSITY)

  def create_session(self, definition: _FixtureDefinition, configuration: _FixtureConfiguration) -> _FixtureSession:
    assert definition.name
    assert configuration.scale > 0
    snapshot = PlumeSnapshot(
        descriptor=self.descriptor,
        provenance=_provenance(),
        capabilities={CapabilityId.DIRECTIONAL_SPECTRAL_INTENSITY: _SignatureOnlyCapability()},
    )
    return _FixtureSession(snapshot)
  ####
####


class _SpatialOnlyProvider:
  descriptor = _descriptor(CapabilityId.SPATIAL_SUPPORT)

  def create_session(self, definition: _FixtureDefinition, configuration: _FixtureConfiguration) -> _FixtureSession:
    assert definition.name
    assert configuration.scale > 0
    snapshot = PlumeSnapshot(
        descriptor=self.descriptor,
        provenance=_provenance(),
        capabilities={CapabilityId.SPATIAL_SUPPORT: _SpatialOnlyCapability(
            support=SpatialSupport(
                plume_frame_aabb_min_m=(0.0, -1.0, -1.0),
                plume_frame_aabb_max_m=(10.0, 1.0, 1.0),
                characteristic_extent_m=10.0,
                support_definition='fixture bounds',
                is_conservative=True,
            )
        )},
    )
    return _FixtureSession(snapshot)
  ####
####


class _RichProvider:
  descriptor = _descriptor(
      CapabilityId.DIRECTIONAL_SPECTRAL_INTENSITY,
      CapabilityId.SPECTRAL_RAY_TRANSFER,
  )

  def create_session(self, definition: _FixtureDefinition, configuration: _FixtureConfiguration) -> _FixtureSession:
    assert definition.name
    assert configuration.scale > 0
    snapshot = PlumeSnapshot(
        descriptor=self.descriptor,
        provenance=_provenance(),
        capabilities={
            CapabilityId.DIRECTIONAL_SPECTRAL_INTENSITY: _SignatureOnlyCapability(),
            CapabilityId.SPECTRAL_RAY_TRANSFER: _RayCapability(),
        },
    )
    return _FixtureSession(snapshot)
  ####
####


class _InvalidatableSnapshot:
  def __init__(self, snapshot: PlumeSnapshot) -> None:
    self._snapshot = snapshot
    self._valid = True
    ####

  def invalidate(self) -> None:
    self._valid = False
    ####

  def get_capability(self, capability_id: CapabilityId, major_version: int) -> object:
    if not self._valid:
      raise SnapshotInvalidatedError('fixture snapshot was invalidated by the next snapshot')
    return self._snapshot.get_capability(capability_id, major_version)
  ####
####


def _signature_query() -> DirectionalSpectralIntensityQuery:
  return DirectionalSpectralIntensityQuery(
      wavelength_m=np.array([2.0e-6, 4.0e-6]),
      source_to_observer_direction_plume=np.array([[0.6, 0.8, 0.0], [0.6, 0.0, 0.8]]),
  )
####


def _ray_query() -> SpectralRayTransferQuery:
  return SpectralRayTransferQuery(
      observer_origin_plume_m=np.array([[100.0, 0.0, 0.0]]),
      observer_to_scene_direction_plume=np.array([[-1.0, 0.0, 0.0]]),
      maximum_distance_m=np.array([200.0]),
      wavelength_m=np.array([2.0e-6, 4.0e-6]),
  )
####


def test_signature_only_provider_does_not_advertise_geometry() -> None:
  provider = _SignatureOnlyProvider()
  session = provider.create_session(_FixtureDefinition(), _FixtureConfiguration())
  snapshot = session.snapshot(_FixtureOperatingState())
  capability = snapshot.get_capability(CapabilityId.DIRECTIONAL_SPECTRAL_INTENSITY, 1)
  assert capability.capability_id is CapabilityId.DIRECTIONAL_SPECTRAL_INTENSITY
  assert CapabilityId.SPATIAL_SUPPORT not in snapshot.capabilities
  ####
####


def test_spatial_only_provider_does_not_advertise_radiation() -> None:
  provider = _SpatialOnlyProvider()
  snapshot = provider.create_session(_FixtureDefinition(), _FixtureConfiguration()).snapshot(_FixtureOperatingState())
  support = snapshot.get_capability(CapabilityId.SPATIAL_SUPPORT, 1)
  assert support.capability_id is CapabilityId.SPATIAL_SUPPORT
  with pytest.raises(UnsupportedCapabilityError):
    snapshot.get_capability(CapabilityId.DIRECTIONAL_SPECTRAL_INTENSITY, 1)
  ####
####


def test_capability_version_mismatch_is_explicit() -> None:
  snapshot = _SignatureOnlyProvider().create_session(_FixtureDefinition(), _FixtureConfiguration()).snapshot(_FixtureOperatingState())
  with pytest.raises(CapabilityVersionMismatchError):
    snapshot.get_capability(CapabilityId.DIRECTIONAL_SPECTRAL_INTENSITY, 2)
  ####
####


def test_signature_query_validates_and_defensively_copies_arrays() -> None:
  query = _signature_query()
  assert not query.wavelength_m.flags.writeable
  assert not query.source_to_observer_direction_plume.flags.writeable
  with pytest.raises(ValueError):
    query.wavelength_m[0] = 1.0
  with pytest.raises(SpectralDomainError):
    DirectionalSpectralIntensityQuery(np.array([4.0e-6, 2.0e-6]), query.source_to_observer_direction_plume)
  with pytest.raises(AngularDomainError):
    DirectionalSpectralIntensityQuery(query.wavelength_m, np.array([[1.0, 0.0, 0.1]]))
  ####
####


def test_deterministic_signature_and_axisymmetric_directional_symmetry() -> None:
  provider = _SignatureOnlyProvider()
  snapshot = provider.create_session(_FixtureDefinition(), _FixtureConfiguration()).snapshot(_FixtureOperatingState())
  capability = snapshot.get_capability(CapabilityId.DIRECTIONAL_SPECTRAL_INTENSITY, 1)
  result_a = capability.evaluate(_signature_query())
  result_b = capability.evaluate(_signature_query())
  np.testing.assert_array_equal(result_a.spectral_radiant_intensity_w_sr_m, result_b.spectral_radiant_intensity_w_sr_m)
  np.testing.assert_array_equal(result_a.spectral_radiant_intensity_w_sr_m[0], result_a.spectral_radiant_intensity_w_sr_m[1])
  ####
####


def test_rich_provider_ray_transfer_and_snapshot_provenance() -> None:
  provider = _RichProvider()
  snapshot = provider.create_session(_FixtureDefinition(), _FixtureConfiguration()).snapshot(_FixtureOperatingState())
  ray = snapshot.get_capability(CapabilityId.SPECTRAL_RAY_TRANSFER, 1)
  result = ray.transfer(_ray_query())
  np.testing.assert_array_equal(result.source_spectral_radiance_w_sr_m, np.full((1, 2), 2.0))
  np.testing.assert_array_equal(result.background_transmittance, np.full((1, 2), 0.5))
  assert snapshot.provenance.calibration_id == 'fixture-calibration-v1'
  ####
####


def test_ray_miss_returns_zero_source_and_unit_transmittance() -> None:
  result = SpectralRayTransferResult(
      source_spectral_radiance_w_sr_m=np.zeros((1, 2)),
      background_transmittance=np.ones((1, 2)),
      provenance_id='fixture-miss',
  )
  np.testing.assert_array_equal(result.source_spectral_radiance_w_sr_m, np.zeros((1, 2)))
  np.testing.assert_array_equal(result.background_transmittance, np.ones((1, 2)))
  ####
####


def test_rich_to_simple_fixture_equivalence() -> None:
  provider = _RichProvider()
  snapshot = provider.create_session(_FixtureDefinition(), _FixtureConfiguration()).snapshot(_FixtureOperatingState())
  signature = snapshot.get_capability(CapabilityId.DIRECTIONAL_SPECTRAL_INTENSITY, 1).evaluate(_signature_query())
  ray = snapshot.get_capability(CapabilityId.SPECTRAL_RAY_TRANSFER, 1).transfer(_ray_query())
  orthographic_integral = ray.source_spectral_radiance_w_sr_m[:, 0] * 1.0
  np.testing.assert_allclose(signature.spectral_radiant_intensity_w_sr_m[:, 0], np.full(2, orthographic_integral[0]))
  ####
####


def test_invalidatable_snapshot_semantics_are_declared() -> None:
  descriptor = _descriptor(
      CapabilityId.SPATIAL_SUPPORT,
      retention=SnapshotRetention.UNTIL_NEXT_SNAPSHOT,
  )
  assert descriptor.execution.snapshot_retention is SnapshotRetention.UNTIL_NEXT_SNAPSHOT
  snapshot = PlumeSnapshot(
      descriptor=descriptor,
      provenance=_provenance(),
      capabilities={CapabilityId.SPATIAL_SUPPORT: _SpatialOnlyCapability(
          support=SpatialSupport(
              plume_frame_aabb_min_m=(0.0, -1.0, -1.0),
              plume_frame_aabb_max_m=(1.0, 1.0, 1.0),
              characteristic_extent_m=1.0,
              support_definition='fixture bounds',
              is_conservative=True,
          )
      )},
  )
  invalidatable = _InvalidatableSnapshot(snapshot)
  invalidatable.get_capability(CapabilityId.SPATIAL_SUPPORT, 1)
  invalidatable.invalidate()
  with pytest.raises(SnapshotInvalidatedError):
    invalidatable.get_capability(CapabilityId.SPATIAL_SUPPORT, 1)
  ####
####


def test_descriptor_separates_morphology_fidelity_and_execution() -> None:
  descriptor = _SignatureOnlyProvider.descriptor
  assert descriptor.morphology is PlumeMorphology.STRAIGHT
  assert descriptor.fidelity.flow_model == 'fixture'
  assert descriptor.execution.preferred_device == 'cpu'
  assert descriptor.execution.deterministic
  ####
####


def test_session_close_raises_typed_failure() -> None:
  session = _SignatureOnlyProvider().create_session(_FixtureDefinition(), _FixtureConfiguration())
  session.close()
  with pytest.raises(ProviderClosedError):
    session.snapshot(_FixtureOperatingState())
  ####
####
