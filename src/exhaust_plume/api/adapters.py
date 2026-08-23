"""Downward adapters from solver-private plume states into MVP product payloads."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

import numpy as np
from numpy import ndarray

from exhaust_plume.api.contracts import SectionedTubePayload, SupportDefinition, TubeSection

_AXIAL_TOLERANCE_M = 1.e-12
_RADIAL_TOLERANCE_M = 1.e-12


class ZoneCoordinatesLike(Protocol):
  """Structural contract for the current axisymmetric zone coordinates."""

  corners_ru: ndarray
####


class AxisymmetricZoneLike(Protocol):
  """Structural contract required by the visual zone adapter."""

  coordinates: ZoneCoordinatesLike
####


def _validate_zone_corners(
    zone: AxisymmetricZoneLike,
    *,
    zone_index: int,
) -> ndarray:
  corners = np.asarray(zone.coordinates.corners_ru, dtype=float)
  if corners.ndim != 2 or corners.shape[1] != 2:
    raise ValueError(
        f'Expected zone {zone_index} corners_ru to have shape (N, 2). '
        f'Got:{corners.shape}'
    )
  ####
  if len(corners) < 3:
    raise ValueError(f'Expected zone {zone_index} to contain at least three corners.')
  ####
  if not bool(np.isfinite(corners).all()):
    raise ValueError(
        f'Zone {zone_index} contains non-finite geometry. '
        'Complete or remove placeholder polygons before publishing a visual product.'
    )
  ####
  if bool(np.any(corners[:, 1] < -_RADIAL_TOLERANCE_M)):
    raise ValueError(f'Zone {zone_index} contains a negative axisymmetric radius.')
  ####
  normalized = corners.copy()
  normalized[:, 1] = np.maximum(normalized[:, 1], 0.)
  return normalized
####


def _merge_axial_samples(
    samples: list[tuple[float, float]],
) -> tuple[tuple[float, float], ...]:
  ordered = sorted(samples)
  merged: list[tuple[float, float]] = []
  for axial_m, radius_m in ordered:
    if merged:
      previous_axial_m, previous_radius_m = merged[-1]
      tolerance_m = _AXIAL_TOLERANCE_M * max(
          1.,
          abs(previous_axial_m),
          abs(axial_m),
      )
      if abs(axial_m - previous_axial_m) <= tolerance_m:
        merged[-1] = (previous_axial_m, max(previous_radius_m, radius_m))
        continue
      ####
    ####
    merged.append((axial_m, radius_m))
  ####
  return tuple(merged)
####


def sectioned_tube_payload_from_axisymmetric_zones(
    zones: Iterable[AxisymmetricZoneLike],
) -> SectionedTubePayload:
  """Create a visual-only sectioned tube from finite axisymmetric zone polygons.

  The adapter samples the maximum stored radius at each distinct axial vertex.
  It does not infer radiance, species, opacity, conservative fluxes, or a
  continuous optical medium from the zone geometry.
  """

  samples: list[tuple[float, float]] = []
  for zone_index, zone in enumerate(zones):
    corners = _validate_zone_corners(zone, zone_index=zone_index)
    samples.extend(
        (float(axial_m), float(radius_m))
        for axial_m, radius_m in corners
    )
  ####

  sections_by_axial = tuple(
      (axial_m, radius_m)
      for axial_m, radius_m in _merge_axial_samples(samples)
      if radius_m > 0.
  )
  if len(sections_by_axial) < 2:
    raise ValueError(
        'Expected at least two distinct positive-radius axial sections '
        'to construct a sectioned-tube payload.'
    )
  ####

  first_axial_m = sections_by_axial[0][0]
  sections = tuple(
      TubeSection(
          arc_length_m=axial_m - first_axial_m,
          center_m=(axial_m, 0., 0.),
          tangent=(1., 0., 0.),
          normal_1=(0., 1., 0.),
          normal_2=(0., 0., 1.),
          semi_axis_1_m=radius_m,
          semi_axis_2_m=radius_m,
      )
      for axial_m, radius_m in sections_by_axial
  )
  return SectionedTubePayload(
      sections=sections,
      support_definition=SupportDefinition(kind='PHYSICAL_ZONE_BOUNDARY'),
  )
####
