from __future__ import annotations

from unittest import TestCase

from numpy import isfinite
from numpy.testing import assert_allclose

from exhaust_plume import ZoneType, calcNozzleExitFlowState, calculatePlumeZones
from exhaust_plume.util.physical_constants import PASCAL_PER_ATM


class TestPlumeSolver(TestCase):
  @staticmethod
  def calculate(total_pressure_atm: float):
    return calculatePlumeZones(
        nozzle_mach=4.13,
        nozzle_total_temperature=2000.,
        nozzle_total_pressure=total_pressure_atm * PASCAL_PER_ATM,
        nozzle_radius=1.,
        atmospheric_pressure=PASCAL_PER_ATM,
        gamma=1.33,
        num_expansion_lines=2,
        num_compression_lines=1,
        num_plumes=1,
    )

  def test_nozzle_exit_state_preserves_total_conditions(self) -> None:
    state = calcNozzleExitFlowState(
        mach=4.13,
        total_temperature=2000.,
        total_pressure=69. * PASCAL_PER_ATM,
        gamma=1.33,
    )

    self.assertGreater(state.mach, 1.)
    assert_allclose(state.total_temperature, 2000., rtol=1.e-12)
    assert_allclose(state.total_pressure, 69. * PASCAL_PER_ATM, rtol=1.e-12)
    self.assertGreater(state.static_temperature, 0.)
    self.assertGreater(state.static_pressure, 0.)

  def test_underexpanded_plume_has_finite_geometry_and_pressure_equalization(self) -> None:
    zones, details = self.calculate(total_pressure_atm=69.)

    self.assertEqual(len(zones), 9)
    self.assertEqual(zones[0].type, ZoneType.Isentropic)
    self.assertEqual(zones[-1].type, ZoneType.ObliqueShock)
    self.assertTrue({'points', 'plume_fit', 'solver_diagnostics_v1', 'regime', 'termination'} <= set(details))
    self.assertTrue(all(isfinite(zone.coordinates.corners_ru).all() for zone in zones))
    assert_allclose(zones[4].static_pressure, PASCAL_PER_ATM, rtol=2.e-5)
    assert_allclose(zones[7].static_pressure, PASCAL_PER_ATM, rtol=2.e-5)

  def test_overexpanded_plume_adds_precursor_shocks(self) -> None:
    zones, _ = self.calculate(total_pressure_atm=50.)

    self.assertLess(zones[0].static_pressure, PASCAL_PER_ATM)
    self.assertEqual(zones[1].type, ZoneType.ObliqueShock)
    self.assertEqual(zones[2].type, ZoneType.ObliqueShock)
    self.assertTrue(all(isfinite(zone.coordinates.corners_ru).all() for zone in zones))

  def test_invalid_plume_inputs_fail_early(self) -> None:
    parameters = dict(
        nozzle_mach=4.13,
        nozzle_total_temperature=2000.,
        nozzle_total_pressure=69. * PASCAL_PER_ATM,
        nozzle_radius=1.,
        atmospheric_pressure=PASCAL_PER_ATM,
        gamma=1.33,
        num_expansion_lines=2,
        num_compression_lines=1,
        num_plumes=1,
    )
    for name, value in (
        ('nozzle_mach', 1.),
        ('nozzle_total_temperature', 0.),
        ('gamma', 1.),
        ('num_expansion_lines', 1),
        ('num_compression_lines', 0),
        ('num_plumes', 0),
    ):
      with self.subTest(name=name):
        invalid = {**parameters, name: value}
        with self.assertRaises(ValueError):
          calculatePlumeZones(**invalid)
        ##
      ##
    ##
