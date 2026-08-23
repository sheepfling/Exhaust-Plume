"""Integration tests for the current shock-zone to visual-product adapter."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pytest
from numpy import ndarray

from exhaust_plume.api import sectioned_tube_payload_from_axisymmetric_zones
from exhaust_plume.models.plume import calculatePlumeZones


@dataclass(frozen=True)
class _Coordinates:
  corners_ru: ndarray
####


@dataclass(frozen=True)
class _Zone:
  coordinates: _Coordinates
####


def test_axisymmetric_zone_adapter_builds_visual_only_sections() -> None:
  zones = (
      _Zone(_Coordinates(np.asarray(((0., 0.), (0., .2), (1., .3))))),
      _Zone(_Coordinates(np.asarray(((1., 0.), (1., .3), (2., .1))))),
  )
  payload = sectioned_tube_payload_from_axisymmetric_zones(zones)
  assert payload.support_definition.kind == 'PHYSICAL_ZONE_BOUNDARY'
  assert payload.feature_channels == ()
  assert tuple(section.center_m for section in payload.sections) == (
      (0., 0., 0.),
      (1., 0., 0.),
      (2., 0., 0.),
  )
  assert tuple(section.semi_axis_1_m for section in payload.sections) == pytest.approx(
      (.2, .3, .1)
  )
  assert tuple(section.arc_length_m for section in payload.sections) == pytest.approx(
      (0., 1., 2.)
  )
####


def test_axisymmetric_zone_adapter_rejects_placeholder_geometry() -> None:
  zones = (
      _Zone(_Coordinates(np.asarray(((0., 0.), (0., .2), (1., np.nan))))),
  )
  with pytest.raises(ValueError, match='non-finite geometry'):
    sectioned_tube_payload_from_axisymmetric_zones(zones)
  ####
####


def test_current_solver_zones_map_into_the_visual_mvp_payload() -> None:
  zones, _ = calculatePlumeZones(
      nozzle_mach=4.13,
      nozzle_total_temperature=2000.,
      nozzle_total_pressure=69. * 101325.,
      nozzle_radius=1.,
      atmospheric_pressure=101325.,
      gamma=1.33,
      num_expansion_lines=2,
      num_compression_lines=1,
      num_plumes=1,
  )
  payload = sectioned_tube_payload_from_axisymmetric_zones(zones)
  assert len(payload.sections) >= 2
  assert all(section.center_m[1:] == (0., 0.) for section in payload.sections)
  assert all(section.semi_axis_1_m > 0. for section in payload.sections)
  assert tuple(section.arc_length_m for section in payload.sections) == tuple(
      sorted(section.arc_length_m for section in payload.sections)
  )
####
