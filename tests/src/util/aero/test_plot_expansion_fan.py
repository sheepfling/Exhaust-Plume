# -*- coding: utf-8 -*-

from typing import ClassVar, List, Sequence
from unittest import TestCase, main as ut_main

import matplotlib
from matplotlib.figure import Figure as FigureType
from matplotlib import pyplot as plt
from numpy import linspace, meshgrid

from exhaust_plume.log.extra_log_levels import NOTSET
from exhaust_plume.log.log import configureLogging, getCleanLogger, getLogger, getRootLogger
from exhaust_plume.util.aero.expansion_fan import calcPmExpansionAngle, calcPrandtlMeyerAngle

######################################
log = getCleanLogger(__name__)
SHOW_PLOTS: bool = False


class TestObliqueShock(TestCase):
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

  def test_calculatePrandtlMeyerAngle(self) -> None:
    gamma = 4. / 3.
    mach_min = 1.
    mach_max = 4.
    with self.subTest('plot PM angle'):
      machs = linspace(mach_min, mach_max, self.num_linear_points)
      nu_deg = calcPrandtlMeyerAngle(mach=machs, gamma=gamma)
      fig, ax = plt.subplots(1, 1)
      ax.plot(machs, nu_deg)
      ax.set_xlabel('Mach #')
      ax.set_ylabel(r'Angle, $\nu$ [deg]')
      ax.grid()
      ax.set_title('Prandtl-Meyer Angle')
      self._closeOrAppendFigs([fig, ])
    ##
  ##

  def test_calcPmExpansionAngle(self) -> None:
    gamma = 4. / 3.
    mach_min = 1.
    mach_max = 4.
    num_levels = int((self.num_axis_points**.5) * 4 + 1)
    num_levels += num_levels % 2 == 0
    levels = linspace(0., 90., num_levels)
    with self.subTest('plot PM angle'):
      machs = linspace(mach_min, mach_max, self.num_axis_points)
      m_up, m_down = meshgrid(machs, machs)
      th_deg = calcPmExpansionAngle(
          mach_upstream=m_up,
          mach_downstream=m_down,
          gamma=gamma,
      )
      fig, ax = plt.subplots(1, 1)
      h_contours = ax.contourf(m_up, m_down, th_deg, levels=levels, cmap="RdBu", )
      ax.set_xlabel(r'Upstream Mach #')
      ax.set_ylabel(r'Downstream Mach #')
      ax.grid()
      h = plt.colorbar(h_contours, ax=ax)
      h.set_label(r'Expansion Angle, $\theta$ [deg]')
      ax.set_title('Prandtl-Meyer Expansion Angle')
      self._closeOrAppendFigs([fig, ])
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
