from __future__ import annotations

from math import tan

from numpy import isfinite
from numpy.testing import assert_allclose

from exhaust_plume import ZoneType, calculatePlumeZones
from exhaust_plume.util.physical_constants import PASCAL_PER_ATM


def test_overexpanded_precursor_centerline_uses_radial_drop_relation() -> None:
  zones, _ = calculatePlumeZones(
      nozzle_mach=4.13,
      nozzle_total_temperature=2000.0,
      nozzle_total_pressure=50.0 * PASCAL_PER_ATM,
      nozzle_radius=1.0,
      atmospheric_pressure=PASCAL_PER_ATM,
      gamma=1.33,
      num_expansion_lines=2,
      num_compression_lines=1,
      num_plumes=1,
  )
  assert zones[1].type is ZoneType.ObliqueShock
  point_b = zones[0].coordinates.bottom_left_corner
  point_c = zones[0].coordinates.bottom_right_corner
  radius = zones[0].coordinates.height
  beta_rad = zones[1].asObliqueShockState().shock_angle_rad
  assert_allclose(point_c[1], point_b[1])
  assert_allclose(point_c[0] - point_b[0], radius / tan(beta_rad), rtol=1.0e-10)
  assert all(isfinite(zone.coordinates.corners_ru).all() for zone in zones)
  ####
