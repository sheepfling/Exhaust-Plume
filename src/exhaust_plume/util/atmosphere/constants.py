# -*- coding: utf-8 -*-

""" References:
- Adiabatic Index: https://en.wikipedia.org/wiki/Heat_capacity_ratio
-- Archive: https://web.archive.org/web/20220918081956/https://en.wikipedia.org/wiki/Heat_capacity_ratio
-- Archive:
- STP Standard NTP Standard: https://www.engineeringtoolbox.com/stp-standard-ntp-normal-air-d_772.html
-- Archive: https://web.archive.org/web/20220707070201/https://www.engineeringtoolbox.com/stp-standard-ntp-normal-air-d_772.html
-- Archive:https://archive.is/ZgHHH
- Air Composition: https://www.engineeringtoolbox.com/air-composition-d_212.html
-- Archive: https://web.archive.org/web/20230000000000*/https://www.engineeringtoolbox.com/air-composition-d_212.html
-- Archive: https://archive.is/y1U9D
"""
from __future__ import annotations

__all__ = (
    'ADIABATIC_INDEX_DRY_AIR_NTP',
    'MOLAR_MASS_DRY_AIR_kg',
)


# Adiabatic index is ratio of Cp / Cv, where
# Cp is the heat capacity at a constant pressure
# Cv is the heat capacity at a constant volume
ADIABATIC_INDEX_DRY_AIR_NTP = 1.4  # adiabatic index of air at normal temperature and pressure (1atm, 20'C)

MOLAR_MASS_DRY_AIR_kg = 28.9647e-3
