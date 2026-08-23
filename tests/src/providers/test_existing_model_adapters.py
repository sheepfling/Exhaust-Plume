from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

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


@dataclass(frozen=True)
class DummyStation:
  position_m: np.ndarray
  tangent: np.ndarray
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
####


@dataclass(frozen=True)
class DummyResult:
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


def _curvedResult() -> DummyResult:
  return DummyResult(stations=(
      DummyStation(
          position_m=np.asarray((0., 0., 0.)),
          tangent=np.asarray((1., 0., 0.)),
          radius_m=.2,
          area_m2=np.pi * .2 ** 2,
          temperature_K=1200.,
          pressure_Pa=101325.,
          density_kgpm3=.3,
          speed_mps=600.,
          mass_flow_kgps=10.,
          momentum_flux_N=np.asarray((6000., 0., 0.)),
          total_energy_flow_W=1.e7,
          exhaust_mass_flow_kgps=10.,
          exhaust_mass_fraction=1.,
      ),
      DummyStation(
          position_m=np.asarray((1., .1, 0.)),
          tangent=np.asarray((.9950371902, .0995037190, 0.)),
          radius_m=.3,
          area_m2=np.pi * .3 ** 2,
          temperature_K=900.,
          pressure_Pa=101325.,
          density_kgpm3=.4,
          speed_mps=400.,
          mass_flow_kgps=14.,
          momentum_flux_N=np.asarray((5572.2, 557.2, 0.)),
          total_energy_flow_W=1.2e7,
          exhaust_mass_flow_kgps=10.,
          exhaust_mass_fraction=10. / 14.,
      ),
  ))
####


def testCurvedResultMapsToVisualAndFluxProducts(
    metadata_factory: Callable[[CapabilityId, str], ProductMetadata],
) -> None:
  result = _curvedResult()
  visual = sectionedTubeFromCurvedPlume(
      result,
      metadata=metadata_factory(VISUAL_SECTIONED_TUBE_V1, 'visual-1'),
  )
  flux = engineeringFluxSectionsFromCurvedPlume(
      result,
      metadata=metadata_factory(ENGINEERING_FLUX_SECTION_V1, 'flux-1'),
  )
  assert visual.metadata.capability == VISUAL_SECTIONED_TUBE_V1
  assert tuple(channel.name for channel in visual.feature_channels) == (
      'temperature',
      'pressure',
      'density',
      'speed',
      'exhaust-mass-fraction',
  )
  assert flux.mass_flow_kgps == (10., 14.)
  assert flux.exhaust_mass_flow_kgps == (10., 10.)
####


def testAxisymmetricZoneAdapterProducesVisualSurrogate(
    metadata_factory: Callable[[CapabilityId, str], ProductMetadata],
) -> None:
  zones = (
      DummyZone(DummyCoordinates(np.asarray(((0., 0.), (0., .5), (1., .4), (1., 0.))))),
      DummyZone(DummyCoordinates(np.asarray(((1., 0.), (1., .4), (2., .2), (2., 0.))))),
  )
  product = sectionedTubeFromAxisymmetricZones(
      zones,
      metadata=metadata_factory(VISUAL_SECTIONED_TUBE_V1),
  )
  assert product.geometry_role == 'visualization'
  assert product.centerline_m == ((0., 0., 0.), (1., 0., 0.), (2., 0., 0.))
  assert product.semi_major_axis_m == (.5, .4, .2)
  assert product.feature_channels == ()
####
