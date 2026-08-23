# -*- coding: utf-8 -*-
"""
References:
  - Speed of Sounds: https://en.wikipedia.org/wiki/Speed_of_sound
  -- Archive: https://web.archive.org/web/20230117125145/https://en.wikipedia.org/wiki/Speed_of_sound
  -- Archive: https://archive.is/OhmYk
"""
from __future__ import annotations

from typing import TypeVar

from numpy import ndarray

from exhaust_plume.log.log import getCleanLogger
from exhaust_plume.util.aero.speed_of_sound import calculateSpeedOfSoundInGas
from exhaust_plume.util.atmosphere.constants import ADIABATIC_INDEX_DRY_AIR_NTP

__all__ = (
    'calculateSpeedOfSoundInAir',
)

log = getCleanLogger(__name__)

T = TypeVar('T', float, ndarray)


def calculateSpeedOfSoundInAir(pressure_Pa: T, density_kgpm3: T, adiabatic_index: float = ADIABATIC_INDEX_DRY_AIR_NTP) -> T:
  """ Returns speed of sound in m/s air at a given pressure and density
  adiabatic_index is also known as gamma (γ)
  """
  return calculateSpeedOfSoundInGas(
      pressure_Pa=pressure_Pa,
      density_kgpm3=density_kgpm3,
      adiabatic_index=adiabatic_index,
  )
####
