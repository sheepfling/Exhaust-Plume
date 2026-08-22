# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import ClassVar, List, Sequence, Union
from unittest import TestCase, main as ut_main

import matplotlib
from matplotlib.figure import Figure as FigureType
from matplotlib import pyplot as plt
from numpy import linspace, meshgrid, ndarray

from exhaust_plume.log.extra_log_levels import NOTSET
from exhaust_plume.log.log import configureLogging, getCleanLogger, getLogger, getRootLogger
from exhaust_plume.util.aero.oblique_shock import calcShockObliqueAngle

######################################
log = getCleanLogger(__name__)

SHOW_PLOTS: bool = False


def plotObliqueAngleContourDelta(mach_min: float, mach_max: float,
                                 theta_deg_min: float, theta_deg_max: float,
                                 num_axis_points: int,
                                 delta: float, gamma: float,
                                 levels: Union[int, ndarray] = 20,
                                 ) -> FigureType:
  machs = linspace(mach_min, mach_max, num_axis_points)
  thetas = linspace(theta_deg_min, theta_deg_max, num_axis_points)

  tt, mm = meshgrid(thetas, machs)
  aa = calcShockObliqueAngle(
      theta_deg=tt,
      mach=mm,
      gamma=gamma,
      delta=delta,
  )
  fig, ax = plt.subplots(1, 1)
  h_contours = ax.contourf(thetas, machs, aa, levels=levels, cmap="RdBu", )
  ax.set_xlabel(r'Oblique Angle, $\theta$ [deg]')
  ax.set_ylabel(r'Mach #')
  ax.grid()
  title_str = 'Shock Angle'
  if delta == 1.:
    title_str += ' (Weak)'
  elif delta == 0.:
    title_str += ' (Strong)'
  ##
  title_str += rf' $\delta={delta:.1f}$'
  h = plt.colorbar(h_contours, ax=ax)
  h.set_label(r'Oblique Shock Angle, $\beta$ [deg]')
  ax.set_title(title_str)
  return fig
##


class TestPlotObliqueShock(TestCase):
  figs: ClassVar[List[FigureType]]
  num_linear_points: ClassVar[int] = 101
  num_axis_points: ClassVar[int] = 201

  @classmethod
  def setUpClass(cls) -> None:
    cls.figs = []
    root_logger = getRootLogger(log)
    root_logger.setLevel(NOTSET)
    if not SHOW_PLOTS:
      matplotlib.use('Agg')
      cls.num_linear_points = 11
      cls.num_axis_points = 11
    ##
  ##

  def test_calcObliqueAngle(self) -> None:
    gamma = 4 / 3.
    deltas = (0., 1.,)
    theta_deg_min = 0.0
    num_levels = int((self.num_axis_points**.5) * 4 + 1)
    num_levels += num_levels % 2 == 0
    max_shock_angle = 90
    mach_min = 1.0
    mach_max = 2.0
    theta_deg_max = 25.
    with self.subTest('plot'):
      levels = linspace(0., max_shock_angle, num_levels)
      for delta in deltas:
        fig = plotObliqueAngleContourDelta(
            gamma=gamma,
            delta=delta,
            mach_min=mach_min,
            mach_max=mach_max,
            num_axis_points=self.num_axis_points,
            theta_deg_min=theta_deg_min,
            theta_deg_max=theta_deg_max,
            levels=levels,
        )
        self._closeOrAppendFigs([fig, ])
      ##
    ##
  ##

  def _closeOrAppendFigs(self, figs: Sequence[FigureType]) -> None:
    if SHOW_PLOTS:
      self.figs.extend(figs)
    else:
      for fig in figs:
        plt.close(fig)
      ##
    ##
  ##

  @classmethod
  def tearDownClass(cls) -> None:
    if SHOW_PLOTS:
      plt.show()
    ##
    for fig in cls.figs:
      plt.close(fig)
    ##
  ##
##


if __name__ == "__main__":
  SHOW_PLOTS = True
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
