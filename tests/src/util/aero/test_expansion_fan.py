# -*- coding: utf-8 -*-
from __future__ import annotations

import pickle
from dataclasses import fields
from itertools import product
from typing import ClassVar, Optional
from unittest import TestCase, main as ut_main

from numpy import allclose, deg2rad, isclose, linspace, meshgrid, rad2deg
from numpy.random import exponential, uniform

from exhaust_plume.log.extra_log_levels import NOTSET
from exhaust_plume.log.log import configureLogging, getCleanLogger, getLogger, getRootLogger
from exhaust_plume.util.aero.expansion_fan import (
    ExpansionFanState, calcIsentropicPmPressure, calcIsentropicPmPressureRatio, calcIsentropicPmTemperature, calcIsentropicPmTemperatureRatio, calcPmDownstreamMach, calcPmExpansionAngle, calcPrandtlMeyerAngle,
)
from exhaust_plume.util.aero.flow_state import FlowState
from exhaust_plume.util.aero.isentropic_flow import (calcIsentropicStaticDensity, calcIsentropicTotalPressure, calcIsentropicTotalStaticPressureRatio, calcIsentropicTotalStaticTemperatureRatio, calcIsentropicTotalTemperature)
from exhaust_plume.util.aero.misc import calcMachAngle

######################################
log = getCleanLogger(__name__)


def random_ExpansionFanState(N: Optional[int] = 0, gamma: float = 1.4) -> ExpansionFanState:
  if N is None:
    N = int(exponential() + 1)
  ##
  if N == 0:
    def converter(x):
      return float(x)
    ##
    shp = tuple()
  else:
    def converter(x):
      return x
    ##
    shp = (N,)
  ##
  mach = converter(exponential(size=shp) + 1)
  turn_deg = converter(uniform(size=shp, low=0., high=15., ))  # conservative
  out = ExpansionFanState(
      mach=mach,
      turn_deg=turn_deg,
      static_pressure=converter(exponential(size=shp)),
      static_temperature=converter(exponential(size=shp)),
      gamma=gamma,
      upstream_mach_line_deg=converter(uniform(low=0., high=30., size=shp)),
      static_density=converter(exponential(size=shp)),
  )
  return out
##


class TestExpansionFan(TestCase):
  num_linear_points: ClassVar[int] = 101
  num_axis_points: ClassVar[int] = 201
  gamma: ClassVar[float] = 1.4
  num_monte: ClassVar[int] = 30

  @classmethod
  def setUpClass(cls) -> None:
    cls.figs = []
    root_logger = getRootLogger(log)
    root_logger.setLevel(NOTSET)
  ##

  def test_calculatePrandtlMeyerAngle(self) -> None:
    gamma = 4. / 3.
    mach_min = 1.
    mach_max = 4.
    with self.subTest('plot PM angle'):
      machs = linspace(mach_min, mach_max, self.num_linear_points)
      calcPrandtlMeyerAngle(mach=machs, gamma=gamma)
    ##
  ##

  def test_calcPmExpansionAngle(self) -> None:
    gamma = 4. / 3.
    mach_min = 1.
    mach_max = 4.
    num_levels = int((self.num_axis_points**.5) * 4 + 1)
    num_levels += num_levels % 2 == 0
    with self.subTest('plot PM angle'):
      machs = linspace(mach_min, mach_max, self.num_axis_points)
      m_up, m_down = meshgrid(machs, machs)
      calcPmExpansionAngle(
          mach_upstream=m_up,
          mach_downstream=m_down,
          gamma=gamma,
      )
    ##
  ##

  def test_Example4_13(self) -> None:
    M1 = 1.5
    th_deg = 20.

    expected_nu1 = 11.91
    nu1 = calcPrandtlMeyerAngle(mach=M1, gamma=self.gamma)
    self.assertTrue(isclose(expected_nu1, nu1, rtol=1e-2),
                    f'Expected values to be close:'
                    f'\nExpected:{expected_nu1}'
                    f'\nGot     :{nu1}')

    expected_mu1 = 41.81
    mu1 = calcMachAngle(mach=M1)
    self.assertTrue(isclose(expected_mu1, mu1, rtol=1e-2),
                    f'Expected values to be close:'
                    f'\nExpected:{expected_mu1}'
                    f'\nGot     :{mu1}')

    expected_nu2 = 31.91
    # th = nu2 - nu1
    # nu2 = nu1 + th
    nu2 = nu1 + th_deg
    self.assertTrue(isclose(expected_nu2, nu2, rtol=1e-2),
                    f'Expected values to be close:'
                    f'\nExpected:{expected_nu2}'
                    f'\nGot     :{nu2}')

    expected_M2 = 2.207
    M2 = calcPmDownstreamMach(
        mach_initial=M1,
        nu=nu2,
        initial_nu=1e0,  # nu1,
        gamma=self.gamma,
    )
    self.assertTrue(isclose(expected_M2, M2, rtol=1e-2),
                    f'Expected values to be close:'
                    f'\nExpected:{expected_M2}'
                    f'\nGot     :{M2}')

    expected_mu2_deg = 26.95
    mu2 = calcMachAngle(expected_M2)
    self.assertTrue(isclose(expected_mu2_deg, mu2, rtol=1e-2),
                    f'Expected values to be close:'
                    f'\nExpected:{expected_mu2_deg}'
                    f'\nGot     :{mu2}')

    expected_pressure_total_static_ratio_1 = 3.671
    expected_temperature_total_static_ratio_1 = 1.45

    pressure_total_static_ratio_1 = calcIsentropicTotalStaticPressureRatio(
        mach=M1, gamma=self.gamma,
    )
    temperature_total_static_ratio_1 = calcIsentropicTotalStaticTemperatureRatio(
        mach=M1, gamma=self.gamma,
    )
    self.assertTrue(isclose(expected_pressure_total_static_ratio_1, pressure_total_static_ratio_1, rtol=1e-2),
                    f'Expected values to be close:'
                    f'\nExpected:{expected_pressure_total_static_ratio_1}'
                    f'\nGot     :{pressure_total_static_ratio_1}')
    self.assertTrue(isclose(expected_temperature_total_static_ratio_1, temperature_total_static_ratio_1, rtol=1e-2),
                    f'Expected values to be close:'
                    f'\nExpected:{expected_temperature_total_static_ratio_1}'
                    f'\nGot     :{temperature_total_static_ratio_1}')

    M2 = expected_M2
    expected_pressure_total_static_ratio_2 = 10.81
    expected_temperature_total_static_ratio_2 = 1.974
    pressure_total_static_ratio_2 = calcIsentropicTotalStaticPressureRatio(
        mach=M2, gamma=self.gamma,
    )
    temperature_total_static_ratio_2 = calcIsentropicTotalStaticTemperatureRatio(
        mach=M2, gamma=self.gamma,
    )
    self.assertTrue(isclose(expected_pressure_total_static_ratio_2, pressure_total_static_ratio_2, rtol=1e-2),
                    f'Expected values to be close:'
                    f'\nExpected:{expected_pressure_total_static_ratio_2}'
                    f'\nGot     :{pressure_total_static_ratio_2}')
    self.assertTrue(isclose(expected_temperature_total_static_ratio_2, temperature_total_static_ratio_2, rtol=1e-2),
                    f'Expected values to be close:'
                    f'\nExpected:{expected_temperature_total_static_ratio_2}'
                    f'\nGot     :{temperature_total_static_ratio_2}')

    expected_p2_p1_ratio = 3.671 / 10.81
    expected_T2_T1_ratio = 1.45 / 1.975
    p2_p1_ratio = calcIsentropicPmPressureRatio(M1=M1, M2=M2, gamma=self.gamma)
    T2_T1_ratio = calcIsentropicPmTemperatureRatio(M1=M1, M2=M2, gamma=self.gamma)
    self.assertTrue(isclose(expected_p2_p1_ratio, p2_p1_ratio, rtol=1e-2),
                    f'Expected values to be close:'
                    f'\nExpected:{expected_p2_p1_ratio}'
                    f'\nGot     :{p2_p1_ratio}')
    self.assertTrue(isclose(expected_T2_T1_ratio, T2_T1_ratio, rtol=1e-2),
                    f'Expected values to be close:'
                    f'\nExpected:{expected_T2_T1_ratio}'
                    f'\nGot     :{T2_T1_ratio}')

    expected_static_p2_lbfft2 = 577.3
    expected_static_T2_R = 337.9
    static_p1_lbfft2 = 1700.
    static_T1_R = 460.

    static_P2_lbfft2 = calcIsentropicPmPressure(M1=M1, M2=M2, static_pressure1=static_p1_lbfft2, gamma=self.gamma)
    self.assertTrue(isclose(expected_static_p2_lbfft2, static_P2_lbfft2, rtol=1e-2),
                    f'Expected values to be close:'
                    f'\nExpected:{expected_static_p2_lbfft2}'
                    f'\nGot     :{static_P2_lbfft2}')
    static_T2_R = calcIsentropicPmTemperature(M1=M1, M2=M2, static_temperature1=static_T1_R, gamma=self.gamma)
    self.assertTrue(isclose(expected_static_T2_R, static_T2_R, rtol=1e-2),
                    f'Expected values to be close:'
                    f'\nExpected:{expected_static_T2_R}'
                    f'\nGot     :{static_T2_R}')

    expected_total_pressure2_lbfft2 = 6241.0
    expected_total_temperature2_R = 667.

    total_pressure2_lbfft2 = calcIsentropicTotalPressure(mach=M2, gamma=self.gamma, static_pressure=expected_static_p2_lbfft2)
    self.assertTrue(isclose(expected_total_pressure2_lbfft2, total_pressure2_lbfft2, rtol=1e-2),
                    f'Expected values to be close:'
                    f'\nExpected:{expected_total_pressure2_lbfft2}'
                    f'\nGot     :{total_pressure2_lbfft2}')
    total_temperature2_R = calcIsentropicTotalTemperature(mach=M2, gamma=self.gamma, static_temperature=expected_static_T2_R)
    self.assertTrue(isclose(expected_total_temperature2_R, total_temperature2_R, rtol=1e-2),
                    f'Expected values to be close:'
                    f'\nExpected:{expected_total_temperature2_R}'
                    f'\nGot     :{total_temperature2_R}')

    expected_rearward_mach_angle_deg = 6.95
    rearward_mach_angle_deg = expected_mu2_deg - th_deg
    self.assertTrue(isclose(expected_rearward_mach_angle_deg, rearward_mach_angle_deg, rtol=1e-2),
                    f'Expected values to be close:'
                    f'\nExpected:{expected_rearward_mach_angle_deg}'
                    f'\nGot     :{rearward_mach_angle_deg}')

    with self.subTest('Test ExpansionFan class'):
      upstream = FlowState(
          mach=M1,
          static_pressure=static_p1_lbfft2,
          static_temperature=static_T1_R,
          gamma=self.gamma,
          static_density=1.,
      )
      downstream = ExpansionFanState.fromTurnedUpstreamState(
          upstream=upstream,
          turn_deg=th_deg,
      )
      expected_downstream = ExpansionFanState(
          mach=M2,
          static_pressure=expected_static_p2_lbfft2,
          static_temperature=expected_static_T2_R,
          gamma=self.gamma,
          turn_deg=th_deg,
          upstream_mach_line_deg=upstream.mach_line_deg,
          static_density=calcIsentropicStaticDensity(
              mach=M2,
              total_density=upstream.total_density,
              gamma=self.gamma,
          ),
      )
      for f in fields(downstream):
        v_expected = getattr(expected_downstream, f.name)
        v_got = getattr(downstream, f.name)
        self.assertTrue(isclose(v_expected, v_got, rtol=1e-3),
                        f'Expected values {f.name!r} to be close:'
                        f'\nExpected:{v_expected}'
                        f'\nGot     :{v_got}')
      ##
    ##
  ##

  def testDunder(self) -> None:
    for monte, scalar in product(range(self.num_monte), (False, True,)):
      data = random_ExpansionFanState(N=None if not scalar else 0)
      if scalar:
        self.assertIsInstance(data.mach, float)
      else:
        self.assertNotIsInstance(data.mach, float)
        self.assertTrue(len(data.mach) > 0)
      ##
      hash_val = hash(data)
      self.assertIsInstance(hash_val, int)
      self.assertEqual(hash_val, hash(data))
      repr_val = repr(data)
      self.assertIsInstance(repr_val, str)
      self.assertEqual(repr_val, repr(data))
    ##
  ##

  def test_properties(self) -> None:
    for monte, scalar in product(range(self.num_monte), (False, True,)):
      data = random_ExpansionFanState(N=None if not scalar else 0)

      self.assertTrue(allclose(data.upstream_mach_line_rad, deg2rad(data.upstream_mach_line_deg)))
      self.assertTrue(allclose(rad2deg(data.upstream_mach_line_rad), data.upstream_mach_line_deg))

      self.assertTrue(allclose(data.mach_line_rad, deg2rad(data.mach_line_deg)))
      self.assertTrue(allclose(rad2deg(data.mach_line_rad), data.mach_line_deg))
    ##
  ##

  def testPickleCycle(self) -> None:
    for monte, scalar in product(range(self.num_monte), (False, True,)):
      data = random_ExpansionFanState(N=None if not scalar else 0)
      post_pickle = pickle.loads(pickle.dumps(data))
      self.assertTrue(data.isClose(post_pickle, equal_nan=True),
                      f'Expected data to be equal:'
                      f'\nGot     :{post_pickle}'
                      f'\nExpected:{data}')
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
