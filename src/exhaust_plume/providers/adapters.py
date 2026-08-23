"""Downward adapters from existing solver states into neutral MVP products."""

from __future__ import annotations

from typing import Iterable, Protocol, Sequence

import numpy as np
from numpy.typing import ArrayLike, NDArray

from exhaust_plume.models.plume.curved_plume_geometry import calculateRotationMinimizingFrames
from exhaust_plume.products import (
    Aabb3,
    CapabilityId,
    ENGINEERING_FLUX_SECTION_V1,
    EngineeringFluxSectionProduct,
    ProductMetadata,
    SectionedTubeProduct,
    VISUAL_SECTIONED_TUBE_V1,
    VisualFeatureChannel,
)

FloatArray = NDArray[np.float64]


class CurvedStationLike(Protocol):
  position_m: ArrayLike
  tangent: ArrayLike
  radius_m: float
  temperature_K: float
  pressure_Pa: float
  density_kgpm3: float
  speed_mps: float
  mass_flow_kgps: float
  momentum_flux_N: ArrayLike
  total_energy_flow_W: float
  exhaust_mass_flow_kgps: float
  exhaust_mass_fraction: float
####


class CurvedResultLike(Protocol):
  stations: Sequence[CurvedStationLike]
####


class ZoneCoordinatesLike(Protocol):
  corners_ru: ArrayLike
####


class ZoneLike(Protocol):
  coordinates: ZoneCoordinatesLike
####


def _metadataForCapability(
    metadata: ProductMetadata,
    capability: CapabilityId,
) -> ProductMetadata:
  return metadata.model_copy(update={'capability': capability})
####


def _calculateBounds(
    *,
    centerline_m: FloatArray,
    normals: FloatArray,
    binormals: FloatArray,
    semi_major_axis_m: FloatArray,
    semi_minor_axis_m: FloatArray,
) -> Aabb3:
  extents = np.sqrt(
      (semi_major_axis_m[:, np.newaxis] * normals) ** 2
      + (semi_minor_axis_m[:, np.newaxis] * binormals) ** 2
  )
  minimum = np.min(centerline_m - extents, axis=0)
  maximum = np.max(centerline_m + extents, axis=0)
  return Aabb3(
      minimum_m=tuple(float(value) for value in minimum),
      maximum_m=tuple(float(value) for value in maximum),
  )
####


def sectionedTubeFromCurvedPlume(
    result: CurvedResultLike,
    *,
    metadata: ProductMetadata,
    initial_normal: ArrayLike | None = None,
) -> SectionedTubeProduct:
  """Derive a visual-only product from a curved integral-plume result."""
  if len(result.stations) < 2:
    raise ValueError('Expected at least two curved-plume stations.')
  ####
  centerline = np.asarray([station.position_m for station in result.stations], dtype=float)
  tangents = np.asarray([station.tangent for station in result.stations], dtype=float)
  radii = np.asarray([station.radius_m for station in result.stations], dtype=float)
  normals, binormals = calculateRotationMinimizingFrames(
      tangents=tangents,
      initial_normal=initial_normal,
  )
  bounds = _calculateBounds(
      centerline_m=centerline,
      normals=normals,
      binormals=binormals,
      semi_major_axis_m=radii,
      semi_minor_axis_m=radii,
  )
  channels = (
      VisualFeatureChannel(
          name='temperature', unit='K',
          meaning='Integral-model station temperature; not pixel radiance.',
          values=tuple(float(station.temperature_K) for station in result.stations),
      ),
      VisualFeatureChannel(
          name='pressure', unit='Pa', meaning='Integral-model static pressure.',
          values=tuple(float(station.pressure_Pa) for station in result.stations),
      ),
      VisualFeatureChannel(
          name='density', unit='kg m^-3', meaning='Integral-model mixture density.',
          values=tuple(float(station.density_kgpm3) for station in result.stations),
      ),
      VisualFeatureChannel(
          name='speed', unit='m s^-1', meaning='Integral-model centerline speed.',
          values=tuple(float(station.speed_mps) for station in result.stations),
      ),
      VisualFeatureChannel(
          name='exhaust-mass-fraction', unit='1',
          meaning='Source-origin exhaust mass fraction used as a mixing diagnostic.',
          values=tuple(float(station.exhaust_mass_fraction) for station in result.stations),
      ),
  )
  return SectionedTubeProduct(
      metadata=_metadataForCapability(metadata, VISUAL_SECTIONED_TUBE_V1),
      centerline_m=tuple(tuple(float(value) for value in row) for row in centerline),
      tangents_unit=tuple(tuple(float(value) for value in row) for row in tangents),
      normals_unit=tuple(tuple(float(value) for value in row) for row in normals),
      binormals_unit=tuple(tuple(float(value) for value in row) for row in binormals),
      semi_major_axis_m=tuple(float(value) for value in radii),
      semi_minor_axis_m=tuple(float(value) for value in radii),
      bounds=bounds,
      geometry_role='visualization',
      feature_channels=channels,
  )
####


def engineeringFluxSectionsFromCurvedPlume(
    result: CurvedResultLike,
    *,
    metadata: ProductMetadata,
) -> EngineeringFluxSectionProduct:
  """Expose conserved integral quantities without leaking solver classes."""
  if not result.stations:
    raise ValueError('Expected at least one curved-plume station.')
  ####
  return EngineeringFluxSectionProduct(
      metadata=_metadataForCapability(metadata, ENGINEERING_FLUX_SECTION_V1),
      position_m=tuple(
          tuple(float(value) for value in station.position_m)
          for station in result.stations
      ),
      area_m2=tuple(float(station.radius_m) ** 2 * np.pi for station in result.stations),
      mass_flow_kgps=tuple(float(station.mass_flow_kgps) for station in result.stations),
      momentum_flux_N=tuple(
          tuple(float(value) for value in station.momentum_flux_N)
          for station in result.stations
      ),
      total_energy_flow_W=tuple(float(station.total_energy_flow_W) for station in result.stations),
      exhaust_mass_flow_kgps=tuple(float(station.exhaust_mass_flow_kgps) for station in result.stations),
  )
####


def sectionedTubeFromAxisymmetricZones(
    zones: Iterable[ZoneLike],
    *,
    metadata: ProductMetadata,
) -> SectionedTubeProduct:
  """Derive a coarse visual envelope from private axisymmetric zone vertices.

  The result is not a radiative medium and does not claim conservative support
  between every sample.
  """
  point_rows: list[tuple[float, float]] = []
  for zone in zones:
    corners = np.asarray(zone.coordinates.corners_ru, dtype=float)
    if corners.ndim != 2 or corners.shape[1] != 2:
      raise ValueError(f'Expected zone corners with shape (N, 2). Got:{corners.shape}')
    ####
    for axial, radial in corners:
      if np.isfinite(axial) and np.isfinite(radial) and radial >= 0.:
        point_rows.append((float(axial), float(radial)))
      ####
    ####
  ####
  radial_by_axial: dict[float, float] = {}
  for axial, radial in point_rows:
    radial_by_axial[axial] = max(radial_by_axial.get(axial, 0.), radial)
  ####
  sections = tuple(sorted(
      (axial, radial)
      for axial, radial in radial_by_axial.items()
      if radial > 0.
  ))
  if len(sections) < 2:
    raise ValueError('Expected at least two positive-radius axial sections.')
  ####
  centerline = np.asarray([(axial, 0., 0.) for axial, _ in sections], dtype=float)
  radii = np.asarray([radial for _, radial in sections], dtype=float)
  tangents = np.repeat(np.asarray(((1., 0., 0.),)), len(sections), axis=0)
  normals = np.repeat(np.asarray(((0., 1., 0.),)), len(sections), axis=0)
  binormals = np.repeat(np.asarray(((0., 0., 1.),)), len(sections), axis=0)
  bounds = _calculateBounds(
      centerline_m=centerline,
      normals=normals,
      binormals=binormals,
      semi_major_axis_m=radii,
      semi_minor_axis_m=radii,
  )
  return SectionedTubeProduct(
      metadata=_metadataForCapability(metadata, VISUAL_SECTIONED_TUBE_V1),
      centerline_m=tuple(tuple(float(value) for value in row) for row in centerline),
      tangents_unit=tuple(tuple(float(value) for value in row) for row in tangents),
      normals_unit=tuple(tuple(float(value) for value in row) for row in normals),
      binormals_unit=tuple(tuple(float(value) for value in row) for row in binormals),
      semi_major_axis_m=tuple(float(value) for value in radii),
      semi_minor_axis_m=tuple(float(value) for value in radii),
      bounds=bounds,
      geometry_role='visualization',
  )
####
