# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import ClassVar
from unittest import TestCase, main as ut_main

from numpy import isclose
from numpy.random import exponential

from exhaust_plume.log.extra_log_levels import NOTSET
from exhaust_plume.log.log import configureLogging, getCleanLogger, getLogger, getRootLogger
from exhaust_plume.util.aero.normal_shock import (
    calcNormalShockMach, calcNormalShockStaticDensity, calcNormalShockStaticDensityRatio, calcNormalShockStaticPressure, calcNormalShockStaticPressureRatio, calcNormalShockStaticTemperature, calcNormalShockStaticTemperatureRatio,
)

######################################
log = getCleanLogger(__name__)

# Selected entries from Table A.2
table_a2 = [
    {'mach': 0.1000e+01, 'pressure_ratio': 0.1000e+01, 'density_ratio': 0.1000e+01, 'temperature_ratio': 0.1000e+01, 'mach2': 0.1000e+01},
    {'mach': 0.1400e+01, 'pressure_ratio': 0.2120e+01, 'density_ratio': 0.1690e+01, 'temperature_ratio': 0.1255e+01, 'mach2': 0.7397e+00},
    {'mach': 0.4500e+01, 'pressure_ratio': 0.2346e+02, 'density_ratio': 0.4812e+01, 'temperature_ratio': 0.4875e+01, 'mach2': 0.4236e+00},
    {'mach': 0.7000e+01, 'pressure_ratio': 0.5700e+02, 'density_ratio': 0.5444e+01, 'temperature_ratio': 0.1047e+02, 'mach2': 0.3974e+00},
    {'mach': 0.1700e+02, 'pressure_ratio': 0.3370e+03, 'density_ratio': 0.5898e+01, 'temperature_ratio': 0.5714e+02, 'mach2': 0.3813e+00},
]


class TestNormalShock(TestCase):
  num_linear_points: ClassVar[int] = 101
  num_axis_points: ClassVar[int] = 201
  num_monte: ClassVar[int] = 30
  gamma: ClassVar[float] = 1.4

  @classmethod
  def setUpClass(cls) -> None:
    root_logger = getRootLogger(log)
    root_logger.setLevel(NOTSET)
  ##

  def test_Example35(self) -> None:
    m1 = 3.
    p1_atm = .5

    expected_p2_atm = 5.165
    expected_p2_p1_ratio = 10.33
    p2 = calcNormalShockStaticPressure(mach=m1, gamma=self.gamma, static_pressure=p1_atm)
    self.assertTrue(isclose(expected_p2_atm, p2, rtol=1e-2),
                    f'Expected values to be close'
                    f'\nGot     :{p2}'
                    f'\nExpected:{expected_p2_atm}')
    p2_p1 = calcNormalShockStaticPressureRatio(mach=m1, gamma=self.gamma, )
    self.assertTrue(isclose(expected_p2_p1_ratio, p2_p1, rtol=1e-2),
                    f'Expected values to be close'
                    f'\nGot     :{p2_p1}'
                    f'\nExpected:{expected_p2_p1_ratio}')

    expected_T2_T1_ratio = 2.679
    T2_T1 = calcNormalShockStaticTemperatureRatio(mach=m1, gamma=self.gamma)
    self.assertTrue(isclose(expected_T2_T1_ratio, T2_T1, rtol=1e-2),
                    f'Expected values to be close'
                    f'\nGot     :{T2_T1}')

    T1 = 200.  # K
    expected_T2 = 535.8
    T2 = calcNormalShockStaticTemperature(mach=m1, gamma=self.gamma, static_temperature=T1)
    self.assertTrue(isclose(expected_T2, T2, rtol=1e-2),
                    f'Expected values to be close'
                    f'\nGot     :{T2}'
                    f'\nExpected:{expected_T2}')

    expected_m2 = .4752
    m2 = calcNormalShockMach(mach=m1, gamma=self.gamma)
    self.assertTrue(isclose(expected_m2, m2, rtol=1e-2),
                    f'Expected values to be close'
                    f'\nGot     :{m2}'
                    f'\nExpected:{expected_m2}')
  ##

  def test_TableA2(self) -> None:
    with self.subTest('pressure ratio'):
      for row in table_a2:
        mach = row['mach']
        expected_pressure_ratio = row['pressure_ratio']
        pressure_ratio = calcNormalShockStaticPressureRatio(mach=mach, gamma=self.gamma)
        self.assertTrue(isclose(expected_pressure_ratio, pressure_ratio, rtol=1e-2),
                        f'Should to be close for mach:{mach:#.4g}:'
                        f'\nGot     :{pressure_ratio:#.4g}'
                        f'\nExpected:{expected_pressure_ratio:#.4g}')
      ##
    ##
    with self.subTest('temperature ratio'):
      for row in table_a2:
        mach = row['mach']
        expected_temperature_ratio = row['temperature_ratio']
        temperature_ratio = calcNormalShockStaticTemperatureRatio(mach=mach, gamma=self.gamma)
        self.assertTrue(isclose(expected_temperature_ratio, temperature_ratio, rtol=1e-2),
                        f'Should to be close for mach:{mach:#.4g}:'
                        f'\nGot     :{temperature_ratio:#.4g}'
                        f'\nExpected:{expected_temperature_ratio:#.4g}')
      ##
    ##
    with self.subTest('density ratio'):
      for row in table_a2:
        mach = row['mach']
        expected_density_ratio = row['density_ratio']
        density_ratio = calcNormalShockStaticDensityRatio(mach=mach, gamma=self.gamma)
        self.assertTrue(isclose(expected_density_ratio, density_ratio, rtol=1e-2),
                        f'Should to be close for mach:{mach:#.4g}:'
                        f'\nGot     :{density_ratio:#.4g}'
                        f'\nExpected:{expected_density_ratio:#.4g}')
      ##
    ##
    with self.subTest('downstream mach'):
      for row in table_a2:
        mach = row['mach']
        expected_mach2 = row['mach2']
        mach2 = calcNormalShockMach(mach=mach, gamma=self.gamma)
        self.assertTrue(isclose(expected_mach2, mach2, rtol=1e-2),
                        f'Should to be close for mach:{mach:#.4g}:'
                        f'\nGot     :{mach2:#.4g}'
                        f'\nExpected:{expected_mach2:#.4g}')
      ##
    ##
  ##

  def test_monte(self) -> None:
    for monte in range(self.num_monte):
      mach = exponential() * 2. + 1.
      mach2 = calcNormalShockMach(mach=mach, gamma=self.gamma)
      self.assertLess(0., mach2)
      self.assertLess(mach2, 1.)

      rho_ratio = calcNormalShockStaticDensityRatio(mach=mach, gamma=self.gamma)
      self.assertLess(1., rho_ratio)
      T_ratio = calcNormalShockStaticTemperatureRatio(mach=mach, gamma=self.gamma)
      self.assertLess(1., T_ratio)
      p_ratio = calcNormalShockStaticPressureRatio(mach=mach, gamma=self.gamma)
      self.assertLess(1., p_ratio)

      expected_T_ratio = T_ratio
      T_up = exponential()
      T_down = calcNormalShockStaticTemperature(mach=mach, gamma=self.gamma, static_temperature=T_up)
      calc_T_ratio = T_down / T_up
      self.assertTrue(isclose(expected_T_ratio, calc_T_ratio))

      expected_p_ratio = p_ratio
      p_up = exponential()
      p_down = calcNormalShockStaticPressure(mach=mach, gamma=self.gamma, static_pressure=p_up)
      calc_p_ratio = p_down / p_up
      self.assertTrue(isclose(expected_p_ratio, calc_p_ratio))

      expected_rho_ratio = rho_ratio
      rho_up = exponential()
      rho_down = calcNormalShockStaticDensity(mach=mach, gamma=self.gamma, static_density=rho_up)
      calc_rho_ratio = rho_down / rho_up
      self.assertTrue(isclose(expected_rho_ratio, calc_rho_ratio))
    ##
  ##
##


if __name__ == "__main__":
  ####
  # Boilerplate to load log config file when this module is run as main
  if not configureLogging():
    print('Could not configure log')
  ##
  log = getLogger(__name__)
  ####
  ut_result = ut_main()
  print(ut_result)
##
