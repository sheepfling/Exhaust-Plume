# -*- coding: utf-8 -*-
"""
References:
  - Speed of Sounds: https://en.wikipedia.org/wiki/Speed_of_sound
  -- Archive: https://web.archive.org/web/20230117125145/https://en.wikipedia.org/wiki/Speed_of_sound
  -- Archive: https://archive.is/OhmYk
"""
from __future__ import annotations

from typing import TypeVar

from numpy import ndarray, sqrt

from exhaust_plume.log.log import getCleanLogger

__all__ = (
    'calculateSpeedOfSoundInGas',
)

##############################################
log = getCleanLogger(__name__)

T = TypeVar('T', float, ndarray)


def calculateSpeedOfSoundInGas(pressure_Pa: T, density_kgpm3: T, adiabatic_index: float) -> T:
  """ Returns speed of sound in m/s air at a given pressure and density
  adiabatic_index is also known as gamma (γ)
  """
  # speed = sqrt(gamma * Pressure / density)
  speed_mps = sqrt(adiabatic_index * pressure_Pa / density_kgpm3)
  return speed_mps
##
