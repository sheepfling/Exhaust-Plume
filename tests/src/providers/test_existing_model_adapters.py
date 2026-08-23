from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pytest

from exhaust_plume.products import (
    CapabilityId,
    ENGINEERING_FLUX_SECTION_V1,
    ProductMetadata,
    VISUAL_SECTIONED_TUBE_V1,
)
from exhaust_plume.providers import (
    engineeringFluxSectionsFromCurvedPlume,
    sectionedTubeFromAxisymmetricZones,
    sectionedTubeFromCurvedPlume,
)

MetadataFactory = Callable[[CapabilityId, str, str, float], ProductMetadata]


@dataclass(frozen=True)
class DummyStation:
  position_m: np.ndarray
  velocity_mps: np.ndarray
  radius_m: float
  area_m2: float
  temperature_K: float
  pressure_Pa: float
  density_kgpm3: float
  speed_mps: float
  mass_flow_kgps: float
  momentum_flux_N: np.ndarray
  total_energy_flow_W: float
  exhaust_mass_flow_kgps: float
  exhaust_mass_fraction: float

  @property
  def tangent(self) -> np.ndarray:
    return self.velocity_mps / np.linalg.norm(self.velocity_mps)
  ####
####


@dataclass(frozen=True)
class DummyCurvedResult:
  stations: tuple[DummyStation, ...]
####


@dataclass(frozen=True)
class DummyCoordinates:
  corners_ru: np.ndarray
####


@dataclass(frozen=True)
class DummyZone:
  coordinates: DummyCoordinates
####


def makeCurvedResult() -> DummyCurvedResult:
  stations = (
      DummyStation(
          position_m=np.asarray((0., 0., 0.)),
          velocity_mps=np.asarray((100., 0., 0.)),
          radius_m=.5,
          area_m2=np.pi * .5 ** 2,
          temperature_K=1000.,
          pressure_Pa=101325.,
          density_kgpm3=.5,
          speed_mps=100.,
          mass_flow_kgps=10.,
          momentum_flux_N=np.asarray((1000., 0., 0.)),
          total_energy_flow_W=1.e7,
          exhaust_mass_flow_kgps=10.,
          exhaust_mass_fraction=1.,
      ),
      DummyStation(
          position_m=np.asarray((1., .2, 0.)),
          velocity_mps=np.asarray((90., 18., 0.)),
          radius_m=.7,
          area_m2=np.pi * .7 ** 2,
          temperature_K=800.,
          pressure_Pa=101325.,
          density_kgpm3=.7,
          speed_mps=float(np.linalg.norm((90., 18., 0.))),
          mass_flow_kgps=12.,
          momentum_flux_N=np.asarray((1080., 216., 0.)),
          total_energy_flow_W=1.05e7,
          exhaust_mass_flow_kgps=10.,
          exhaust_mass_fraction=10. / 12.,
      ),
      DummyStation(
          position_m=np.asarray((2., .6, .1)),
          velocity_mps=np.asarray((80., 32., 8.)),
          radius_m=.9,
          area_m2=np.pi * .9 ** 2,
          temperature_K=650.,
          pressure_Pa=101325.,
          density_kgpm3=.9,
          speed_mps=float(np.linalg.norm((80., 32., 8.))),
          mass_flow_kgps=15.,
          momentum_flux_N=np.asarray((1200., 480., 120.)),
          total_energy_flow_W=1.1e7,
          exhaust_mass_flow_kgps=10.,
          exhaust_mass_fraction=2. / 3.,
      ),
  )
  return DummyCurvedResult(stations=stations)
####


def testCurvedResultMapsToVisualAndEngineeringProducts(
    metadata_factory: MetadataFactory,
) -> None:
  result = makeCurvedResult()
  visual_metadata = metadata_factory(
      VISUAL_SECTIONED_TUBE_V1,
      'visual-derived',
      'snapshot-1',
      0.,
  )
  flux_metadata = metadata_factory(
      ENGINEERING_FLUX_SECTION_V1,
      'flux-derived',
      'snapshot-1',
      0.,
  )

  visual = sectionedTubeFromCurvedPlume(result, metadata=visual_metadata)
  flux = engineeringFluxSectionsFromCurvedPlume(result, metadata=flux_metadata)

  assert visual.metadata.capability == VISUAL_SECTIONED_TUBE_V1
  assert len(visual.centerline_m) == 3
  assert visual.feature_channels[-1].name == 'exhaust-mass-fraction'
  assert visual.bounds.minimum_m[1] < -.49
  assert visual.bounds.maximum_m[1] > 1.

  assert flux.metadata.capability == ENGINEERING_FLUX_SECTION_V1
  assert flux.mass_flow_kgps == (10., 12., 15.)
  assert flux.area_m2 == pytest.approx(tuple(station.area_m2 for station in result.stations))
  assert flux.stagnation_enthalpy_flow_W == (1.e7, 1.05e7, 1.1e7)
  assert flux.exhaust_mass_flow_kgps == (10., 10., 10.)
####


def testZoneAdapterIsExplicitlyVisualOnly(metadata_factory: MetadataFactory) -> None:
  zones = (
      DummyZone(DummyCoordinates(np.asarray(((0., 0.), (0., 1.), (1., .8))))),
      DummyZone(DummyCoordinates(np.asarray(((1., 0.), (1., .8), (2., .4))))),
  )
  visual = sectionedTubeFromAxisymmetricZones(
      zones,
      metadata=metadata_factory(VISUAL_SECTIONED_TUBE_V1),
  )
  assert visual.geometry_role == 'visualization'
  assert visual.centerline_m == ((0., 0., 0.), (1., 0., 0.), (2., 0., 0.))
  assert visual.semi_major_axis_m == pytest.approx((1., .8, .4))
  assert visual.feature_channels == ()
####


def testZoneAdapterRejectsInvalidOrDegenerateInputs(
    metadata_factory: MetadataFactory,
) -> None:
  with pytest.raises(ValueError, match='No finite'):
    sectionedTubeFromAxisymmetricZones(
        (DummyZone(DummyCoordinates(np.full((3, 2), np.nan))),),
        metadata=metadata_factory(VISUAL_SECTIONED_TUBE_V1),
    )
  ####
  with pytest.raises(ValueError, match='at least two'):
    sectionedTubeFromAxisymmetricZones(
        (DummyZone(DummyCoordinates(np.asarray(((0., 0.), (0., 1.), (1., 0.))))),),
        metadata=metadata_factory(VISUAL_SECTIONED_TUBE_V1),
    )
  ####
####
