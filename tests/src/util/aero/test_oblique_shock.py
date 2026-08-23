# -*- coding: utf-8 -*-
from __future__ import annotations

import pickle
from dataclasses import fields
from itertools import product
from typing import ClassVar, Optional
from unittest import TestCase, main as ut_main

from numpy import allclose, arcsin, deg2rad, inf, isclose, isfinite, linspace, meshgrid, nan, rad2deg
from numpy.random import exponential, uniform

from exhaust_plume.log.extra_log_levels import NOTSET
from exhaust_plume.log.log import configureLogging, getCleanLogger, getLogger, getRootLogger
from exhaust_plume.util.aero.oblique_shock import ObliqueShockState, calcShockObliqueAngle, calcStrongShockObliqueAngle, calcWeakShockObliqueAngle

log = getCleanLogger(__name__)


def random_ObliqueShockState(N: Optional[int] = 0, gamma: float = 1.4) -> ObliqueShockState:
  if N is None:
    N = int(exponential() + 1)
  ####
  if N == 0:
    def converter(x):
      return float(x)
    ####
    shp = tuple()
  else:
    def converter(x):
      return x
    ####
    shp = (N,)
  ####
  mach = converter(exponential(size=shp) + 1)
  oblique_angle_deg = converter(uniform(size=shp, low=0., high=15., ))  # conservative
  out = ObliqueShockState(
      mach=mach,
      oblique_angle_deg=oblique_angle_deg,
      static_pressure=converter(exponential(size=shp)),
      static_temperature=converter(exponential(size=shp)),
      gamma=gamma,
      shock_angle_deg=calcWeakShockObliqueAngle(mach=mach, theta_deg=oblique_angle_deg, gamma=gamma),
      static_density=converter(exponential(size=shp)),
  )
  return out
####


class TestObliqueShock(TestCase):
  num_linear_points: ClassVar[int] = 101
  num_axis_points: ClassVar[int] = 201
  num_monte: ClassVar[int] = 30
  gamma: ClassVar[float] = 1.4

  @classmethod
  def setUpClass(cls) -> None:
    root_logger = getRootLogger(log)
    root_logger.setLevel(NOTSET)
  ####

  def test_calcObliqueAngle(self) -> None:
    deltas = (0., 1.,)
    num_levels = int((self.num_axis_points ** .5) * 4 + 1)
    num_levels += num_levels % 2 == 0
    with self.subTest('bad values'):
      machs = (0., 1., inf,)
      thetas_degs = (0., 90.,)
      for mach, thetas_deg, delta in product(machs, thetas_degs, deltas):
        calcShockObliqueAngle(mach=mach, theta_deg=thetas_deg, gamma=self.gamma, delta=delta)
      ####
      machs, thetas_degs = meshgrid(linspace(0., 2., self.num_axis_points), linspace(0., 90., self.num_axis_points))
      for delta, (mach, thetas_deg) in product(deltas, zip(machs.ravel(), thetas_degs.ravel())):
        calcShockObliqueAngle(mach=mach, theta_deg=thetas_deg, gamma=self.gamma, delta=delta)
      ####
    ####
    with self.subTest('specific values'):
      machs = (1., 2., 3.,)
      thetas = (0.,)
      for mach, theta, delta in product(machs, thetas, deltas):
        beta = calcShockObliqueAngle(mach=mach, theta_deg=theta, gamma=self.gamma, delta=delta)
        expected = 90. if delta == 0. or mach <= 1. else rad2deg(arcsin(1. / mach))
        self.assertTrue(isclose(expected, beta), f'Unexpected zero-turn shock angle for M={mach}, delta={delta}: {beta}')
      ####
    ####
    with self.subTest('example 4.1,4.2,4.3,4.4,4.5'):
      machs = (3., 3., 5., 2.8, 2.8, 3., 6., 4.)
      theta_degs = (20., 30, 20., 15., 30., 28., 28., 32.,)
      expected_weak_beta_deg = (37.8, 52., 30., 33.8, 54.7, 48.5, 38.0, 48.2,)
      for mach, theta_deg, expected_weak_beta_deg in zip(machs, theta_degs, expected_weak_beta_deg):
        weak_beta_deg = calcWeakShockObliqueAngle(mach=mach, theta_deg=theta_deg, gamma=self.gamma)
        self.assertTrue(isclose(expected_weak_beta_deg, weak_beta_deg, rtol=5e-2),
                        f'Angles to be close.'
                        f'\nGot     :{weak_beta_deg}'
                        f'\nExpected:{expected_weak_beta_deg}')
        strong_beta_deg = calcStrongShockObliqueAngle(mach=mach, theta_deg=theta_deg, gamma=self.gamma)
        self.assertLess(weak_beta_deg, strong_beta_deg)
      ####
    ####
  ####


  def test_calcObliqueShockMachProperties(self) -> None:
    with self.subTest('Example 4.5'):
      machs = (3., 6.)
      betas = (48.5, 38.0,)
      thetas = (28., 28.,)
      expecteds_p2_div_p1 = (5.74, 15.8,)
      P1 = 1.
      T1 = 1.
      d1 = 1.
      for mach, beta, theta, expected_p2_div_p1 in zip(machs, betas, thetas, expecteds_p2_div_p1):
        upstream_state = ObliqueShockState(
            mach=mach,
            oblique_angle_deg=theta,
            static_temperature=T1,
            static_pressure=P1,
            gamma=self.gamma,
            shock_angle_deg=nan,
            static_density=d1,
        )
        downstream_state = ObliqueShockState.fromUpstreamState(upstream_state, oblique_angle_deg=theta)
        P2_div_P1 = downstream_state.static_pressure / P1
        self.assertTrue(isclose(beta, downstream_state.shock_angle_deg, rtol=5e-2),
                        f'Shock anles to be close:'
                        f'\nGot     :{downstream_state.shock_angle_deg}'
                        f'\nExpected:{beta}')
        self.assertTrue(isclose(expected_p2_div_p1, P2_div_P1, rtol=5e-1),
                        f'Pressure ratios to be close:'
                        f'\nGot     :{P2_div_P1}'
                        f'\nExpected:{expected_p2_div_p1}')
      ####
    ####
  ####

  def test_random_ObliqueShockState_properties(self) -> None:
    for scalar in (False, True,):
      state = random_ObliqueShockState(N=None if not scalar else 0)
      self.assertEqual(state, state)
      self.assertTrue(state.isClose(state))
      self.assertNotEqual(state, 3.)
      self.assertFalse(state.isClose(3.))
      beta = state.oblique_angle_deg
      self.assertTrue(all(isfinite(beta).ravel()))
      p = state.total_pressure
      self.assertTrue(all(isfinite(p).ravel()))

      self.assertTrue(allclose(state.oblique_angle_deg, rad2deg(state.oblique_angle_rad)))
      self.assertTrue(allclose(deg2rad(state.oblique_angle_deg), state.oblique_angle_rad))

      self.assertTrue(allclose(state.shock_angle_deg, rad2deg(state.shock_angle_rad), equal_nan=True))
      self.assertTrue(allclose(deg2rad(state.shock_angle_deg), state.shock_angle_rad, equal_nan=True))
    ####
  ####

  def testDunder(self) -> None:
    for monte, scalar in product(range(self.num_monte), (False, True,)):
      data = random_ObliqueShockState(N=None if not scalar else 0)
      if scalar:
        self.assertIsInstance(data.mach, float)
      else:
        self.assertNotIsInstance(data.mach, float)
        self.assertTrue(len(data.mach) > 0)
      ####
      hash_val = hash(data)
      self.assertIsInstance(hash_val, int)
      self.assertEqual(hash_val, hash(data))
      repr_val = repr(data)
      self.assertIsInstance(repr_val, str)
      self.assertEqual(repr_val, repr(data))
    ####
  ####

  def testPickleCycle(self) -> None:
    for monte, scalar in product(range(self.num_monte), (False, True,)):
      data = random_ObliqueShockState(N=None if not scalar else 0)
      post_pickle = pickle.loads(pickle.dumps(data))
      self.assertTrue(data.isClose(post_pickle, equal_nan=True))
    ####
  ####

  def test_ShockForEqulizedPressure(self) -> None:
    gamma = 1.33
    expected_downstream_state = ObliqueShockState(
        oblique_angle_deg=5.80,
        shock_angle_deg=18.0,
        static_pressure=54479.2,
        static_temperature=602.2,
        mach=3.77,
        gamma=gamma,
        static_density=1.49,
    )
    upstream_state = ObliqueShockState(
        mach=4.13,
        oblique_angle_deg=5.88,
        shock_angle_deg=nan,
        static_pressure=31713.7,
        static_temperature=524.3,
        gamma=gamma,
        static_density=1.,
    )

    p_atmos = expected_downstream_state.static_pressure
    downstream = ObliqueShockState.fromUpstreamStateToEqualizedPressureState(
        upstream=upstream_state,
        downstream_static_pressure=p_atmos,
    )

    for f in fields(downstream):
      v_expected = getattr(expected_downstream_state, f.name)
      v_got = getattr(downstream, f.name)
      self.assertTrue(allclose(v_expected, v_got, rtol=1e-2),
                      f'Expected field:{f.name} to be equal:'
                      f'\nExpected:{v_expected}'
                      f'\nGot     :{v_got}'
                      )
    ####
  ####
####


if __name__ == "__main__":
  # Boilerplate to load log config file when this module is run as main
  if not configureLogging():
    print('Could not configure log')
  ####
  log = getLogger(__name__)
  ut_result = ut_main()
  print(ut_result)
####
