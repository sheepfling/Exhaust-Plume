"""Lifecycle and existing-solver adapter tests."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pytest

from exhaust_plume.products import (
    Aabb3,
    CoordinateFrame,
    Fidelity,
    ProductMetadata,
    Provenance,
    SIGNATURE_SPECTRAL_RADIANT_INTENSITY_V1,
    SectionedTubeProduct,
    VISUAL_SECTIONED_TUBE_V1,
)
from exhaust_plume.providers import (
    ClosedSessionError,
    ProviderDescriptor,
    StaticPlumeProvider,
    StaticVisualCapability,
    TimeAccessMode,
    UnsupportedCapabilityError,
    VisualSectionedTubeCapability,
    engineeringFluxSectionsFromCurvedPlume,
    requireCapability,
    sectionedTubeFromAxisymmetricZones,
    sectionedTubeFromCurvedPlume,
)


def makeMetadata() -> ProductMetadata:
  return ProductMetadata(
      product_id='derived-product',
      capability=VISUAL_SECTIONED_TUBE_V1,
      snapshot_id='snapshot-001',
      time_s=0.,
      frame=CoordinateFrame(
          frame_id='vehicle',
          axis_convention='+X downstream, +Y right, +Z up',
      ),
      provenance=Provenance(
          provider_id='analytical-fixture',
          provider_version='0.1.0',
          model_name='test-model',
          model_revision='test',
      ),
      fidelity=Fidelity(
          morphology='axisymmetric-or-curved',
          flow='integral',
          radiation='none',
          time='steady',
          validation='unit-test',
      ),
  )
####


def makeVisualProduct() -> SectionedTubeProduct:
  return SectionedTubeProduct(
      metadata=makeMetadata(),
      centerline_m=((0., 0., 0.), (1., 0., 0.)),
      tangents_unit=((1., 0., 0.), (1., 0., 0.)),
      normals_unit=((0., 1., 0.), (0., 1., 0.)),
      binormals_unit=((0., 0., 1.), (0., 0., 1.)),
      semi_major_axis_m=(.2, .2),
      semi_minor_axis_m=(.2, .2),
      bounds=Aabb3(minimum_m=(0., -.2, -.2), maximum_m=(1., .2, .2)),
  )
####


def makeDescriptor() -> ProviderDescriptor:
  return ProviderDescriptor(
      provider_id='static-visual',
      provider_version='0.1.0',
      display_name='Static visual fixture',
      capabilities=(VISUAL_SECTIONED_TUBE_V1,),
      time_access_mode=TimeAccessMode.STATIC,
      provenance=makeMetadata().provenance,
  )
####


def testStaticProviderExposesOnlyAdvertisedCapability() -> None:
  binding = StaticVisualCapability(makeVisualProduct())
  provider = StaticPlumeProvider(
      descriptor=makeDescriptor(),
      binding_by_capability={VISUAL_SECTIONED_TUBE_V1: binding},
      snapshot_id='snapshot-001',
      time_s=0.,
  )
  with provider.createSession() as session:
    snapshot = session.snapshot(0.)
    visual = requireCapability(
        snapshot,
        VISUAL_SECTIONED_TUBE_V1,
        VisualSectionedTubeCapability,
    ).getSectionedTube()
    assert visual.metadata.capability == VISUAL_SECTIONED_TUBE_V1
    with pytest.raises(UnsupportedCapabilityError):
      snapshot.resolveCapability(SIGNATURE_SPECTRAL_RADIANT_INTENSITY_V1)
    ####
  ####
  with pytest.raises(ClosedSessionError):
    session.snapshot(0.)
  ####
####


@dataclass(frozen=True)
class DummyStation:
  position_m: np.ndarray
  tangent: np.ndarray
  radius_m: float
  temperature_K: float
  pressure_Pa: float
  density_kgpm3: float
  speed_mps: float
  mass_flow_kgps: float
  momentum_flux_N: np.ndarray
  total_energy_flow_W: float
  exhaust_mass_flow_kgps: float
  exhaust_mass_fraction: float
####


@dataclass(frozen=True)
class DummyResult:
  stations: tuple[DummyStation, ...]
####


def makeCurvedResult() -> DummyResult:
  return DummyResult(stations=(
      DummyStation(
          position_m=np.asarray((0., 0., 0.)),
          tangent=np.asarray((1., 0., 0.)),
          radius_m=.2,
          temperature_K=1200.,
          pressure_Pa=101325.,
          density_kgpm3=.3,
          speed_mps=1000.,
          mass_flow_kgps=10.,
          momentum_flux_N=np.asarray((10000., 0., 0.)),
          total_energy_flow_W=1.e7,
          exhaust_mass_flow_kgps=10.,
          exhaust_mass_fraction=1.,
      ),
      DummyStation(
          position_m=np.asarray((1., .2, 0.)),
          tangent=np.asarray((.98, .2, 0.)) / np.linalg.norm((.98, .2, 0.)),
          radius_m=.3,
          temperature_K=900.,
          pressure_Pa=101325.,
          density_kgpm3=.5,
          speed_mps=700.,
          mass_flow_kgps=14.,
          momentum_flux_N=np.asarray((9600., 1950., 0.)),
          total_energy_flow_W=1.e7,
          exhaust_mass_flow_kgps=10.,
          exhaust_mass_fraction=10. / 14.,
      ),
  ))
####


def testCurvedResultMapsToVisualAndEngineeringProducts() -> None:
  result = makeCurvedResult()
  visual = sectionedTubeFromCurvedPlume(result, metadata=makeMetadata())
  flux = engineeringFluxSectionsFromCurvedPlume(result, metadata=makeMetadata())
  assert visual.geometry_role == 'visualization'
  assert tuple(channel.name for channel in visual.feature_channels) == (
      'temperature', 'pressure', 'density', 'speed', 'exhaust-mass-fraction',
  )
  assert flux.mass_flow_kgps == (10., 14.)
  assert flux.exhaust_mass_flow_kgps == (10., 10.)
####


@dataclass(frozen=True)
class DummyCoordinates:
  corners_ru: np.ndarray
####


@dataclass(frozen=True)
class DummyZone:
  coordinates: DummyCoordinates
####


def testAxisymmetricZonesMapOnlyToCoarseVisualEnvelope() -> None:
  zones = (
      DummyZone(DummyCoordinates(np.asarray(((0., 0.), (0., .2), (1., .3))))),
      DummyZone(DummyCoordinates(np.asarray(((1., 0.), (1., .3), (2., .1))))),
  )
  visual = sectionedTubeFromAxisymmetricZones(zones, metadata=makeMetadata())
  assert visual.geometry_role == 'visualization'
  assert visual.feature_channels == ()
  assert visual.centerline_m == ((0., 0., 0.), (1., 0., 0.), (2., 0., 0.))
####
