# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import ClassVar, List
from unittest import TestCase, main as ut_main

from numpy.random import exponential, uniform

from exhaust_plume.log.extra_log_levels import NOTSET
from exhaust_plume.log.log import configureLogging, getCleanLogger, getLogger, getRootLogger
from exhaust_plume.models.plume.motor_parameters import EngineParameters
from exhaust_plume.util.atmosphere.constants import MOLAR_MASS_DRY_AIR_kg
from exhaust_plume.util.physical_constants import PASCAL_PER_ATM
from exhaust_plume.util.plot_types import FigureType

######################################
log = getCleanLogger(__name__)


def random_EngineParameters() -> EngineParameters:
  out = EngineParameters(
      mass_flow_rate_kgps=exponential(),
      exit_radius_m=exponential(),
      total_pressure_Pa=(1 + exponential()) * PASCAL_PER_ATM,
      total_temperature_K=500 + 200. * exponential(),
      gamma=uniform(1.3, 1.5),
      molar_mass_kg=(1 + exponential()) * MOLAR_MASS_DRY_AIR_kg,
  )
  return out
##


class TestEngineParameters(TestCase):
  figs: ClassVar[List[FigureType]]
  num_monte: ClassVar[int] = 30

  @classmethod
  def setUpClass(cls) -> None:
    root_logger = getRootLogger(log)
    root_logger.setLevel(NOTSET)
  ##

  def test_properties(self) -> None:
    for monte in range(self.num_monte):
      data = random_EngineParameters()
      self.assertLess(0., data.exit_area_m2)
      self.assertLess(0., data.throat_area_m2)
      area_exit_div_area_throat = data.exit_area_m2 / data.throat_area_m2
      if area_exit_div_area_throat < 1.:
        with self.assertRaises(ValueError):
          data.exit_mach  # noqa
        ##
        continue
      ##
      self.assertLess(1., data.exit_mach)
      self.assertLess(data.static_density_kpgs, data.total_density_kgps)
      self.assertLess(data.static_temperature_K, data.total_temperature_K)
      self.assertLess(data.static_density_kpgs, data.total_density_kgps)
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
