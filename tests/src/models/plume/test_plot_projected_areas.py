# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import ClassVar, List, Mapping, Sequence
from unittest import TestCase, main as ut_main

import matplotlib
from matplotlib.figure import Figure as FigureType
from matplotlib import pyplot as plt
from numpy import asarray, linspace, pi, rad2deg

from exhaust_plume.log.extra_log_levels import NOTSET
from exhaust_plume.log.log import configureLogging, getCleanLogger, getLogger, getRootLogger
from exhaust_plume.models.plume.projected_areas import calcPolarExclusionAngle, calculateRevolvedProjectedAreas

log = getCleanLogger(__name__)

SHOW_PLOTS: bool = False


class TestPlotProjectdAreas(TestCase):
  figs: ClassVar[List[FigureType]]
  num_linear_points: ClassVar[int] = 101
  data: ClassVar[Mapping[str, Mapping[str, float]]] = {
      'Slender Cone': {
          'R_left': 0.,
          'R_right': 1.,
          'H': 2.,
      },
      'Right Cone': {
          'R_left': 0.,
          'R_right': 1.,
          'H': 1.,
      },
      'Cylinder Lateral Area': {
          'R_left': 1.,
          'R_right': 1.,
          'H': 1.,
      },
      'Circle': {
          'R_left': 0.,
          'R_right': 1.,
          'H': 0.,
      }
  }

  @classmethod
  def setUpClass(cls) -> None:
    cls.figs = []
    root_logger = getRootLogger(log)
    root_logger.setLevel(NOTSET)
    if not SHOW_PLOTS:
      matplotlib.use('Agg')
      cls.num_linear_points = 11
      cls.num_axis_points = 11
    ####
  ####

  def test_plotOcclusionAngles(self) -> None:
    shapes = self.data
    normal_angle_rad = linspace(-pi / 2, pi / 2, self.num_linear_points)

    fig, axs = plt.subplots(1, 2, sharex='all', sharey='all')
    for ax, swap_R in zip(axs, (False, True,)):
      for name, values in shapes.items():
        R_left = values['R_left']
        R_right = values['R_right']
        if swap_R:
          R_right, R_left = (R_left, R_right)
        ####
        H = values['H']
        phi0 = calcPolarExclusionAngle(R_left=R_left, R_right=R_right, H=H, normal_aspect_rad=normal_angle_rad)
        ax.plot(rad2deg(normal_angle_rad), rad2deg(phi0), label=name)
      ####
      ax.grid()
      ax.set_xlabel(r'Normal Aspect, $\theta$, $\left[\mathrm{deg}\right]$')
      ax.set_ylabel(r'Occlusion Angle, $\phi_0$, $\left[\mathrm{deg}\right]$')
      ax.legend()
      ax.set_title(('Left' if not swap_R else 'Right') + ' Facing')
    ####
    fig.suptitle('Polar Occulsion Angles for Various Shapes')
    self._closeOrAppendFigs([fig, ])
  ####

  def test_plotProjectedAreas(self) -> None:
    shapes = self.data
    normal_angle_rad = linspace(-pi / 2, pi / 2, self.num_linear_points)
    for show_total in (False, True,):
      fig, axs = plt.subplots(1, 2, sharex='all', sharey='all')
      for ax, swap_R in zip(axs, (False, True,)):
        for name, values in shapes.items():
          R_left = values['R_left']
          R_right = values['R_right']
          if swap_R:
            R_right, R_left = (R_left, R_right)
          ####
          H = values['H']
          Aproj = calculateRevolvedProjectedAreas(R_left=R_left, R_right=R_right, H=H, normal_aspect_rad=normal_angle_rad)
          ax.plot(rad2deg(normal_angle_rad), Aproj, label=name)
        ####
        if show_total:
          R_left = asarray([v['R_left'] for v in shapes.values()])
          R_right = asarray([v['R_right'] for v in shapes.values()])
          if swap_R:
            R_left, R_right = (R_right, R_left,)
          ####
          Aproj = calculateRevolvedProjectedAreas(
              R_left=R_left, R_right=R_right,
              H=asarray([v['H'] for v in shapes.values()]),
              normal_aspect_rad=normal_angle_rad,
          )
          ax.plot(rad2deg(normal_angle_rad), Aproj, label='Total')
        ####
        ax.grid()
        ax.set_xlabel(r'Normal Aspect, $\theta$, $\left[\mathrm{deg}\right]$')
        ax.set_ylabel(r'Projected Area, $\left[\mathrm{m}^2\right]$')
        ax.legend()
        ax.set_title(('Left' if not swap_R else 'Right') + ' Facing')
      ####
      fig.suptitle('Revolved Projected Areas for Various Shapes' + (' with Total' if show_total else ''))
      self._closeOrAppendFigs([fig, ])
    ####
  ####

  def _closeOrAppendFigs(self, figs: Sequence[FigureType]) -> None:
    if SHOW_PLOTS:
      self.figs.extend(figs)
    else:
      for fig in figs:
        plt.close(fig)
      ####
    ####
  ####

  @classmethod
  def tearDownClass(cls) -> None:
    if SHOW_PLOTS:
      plt.show()
    ####
    for fig in cls.figs:
      plt.close(fig)
    ####
  ####
####


if __name__ == "__main__":
  SHOW_PLOTS = True
  # Boilerplate to load log config file when this module is run as main
  if not configureLogging():
    print('Could not configure log')
  ####
  log = getLogger(__name__)
  ut_result = ut_main()
  print(ut_result)
####
