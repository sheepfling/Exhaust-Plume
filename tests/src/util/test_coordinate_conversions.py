from __future__ import annotations

from unittest import TestCase

from numpy import array
from numpy.testing import assert_allclose

from exhaust_plume.util.robust_geocentric_conversion import ecef2lla_geocentric, lla_geocentric2ecef
from exhaust_plume.util.robust_geodetic_conversion import ecef2enu, ecef2lla, enu2ecef, lla2ecef


class TestCoordinateConversions(TestCase):
  def test_wgs84_lla_ecef_round_trip(self) -> None:
    lla = array([45., 30., 1000.])
    assert_allclose(ecef2lla(lla2ecef(lla)), lla, atol=1.e-3)

  def test_wgs84_enu_ecef_round_trip(self) -> None:
    reference = lla2ecef(array([45., 30., 1000.]))
    position = reference + array([10., 20., 30.])
    enu = ecef2enu(position, reference)
    assert_allclose(enu2ecef(enu, reference), position, atol=1.e-8)

  def test_spherical_lla_ecef_round_trip(self) -> None:
    lla = array([20., -70., 5000.])
    assert_allclose(lla_geocentric2ecef(ecef2lla_geocentric(lla_geocentric2ecef(lla))), lla_geocentric2ecef(lla), atol=1.e-8)
