# -*- coding: utf-8 -*-
""" References:
    - Mole Unit: https://en.wikipedia.org/wiki/Mole_(unit)
    -- Archive: https://web.archive.org/web/20230124054427/https://en.wikipedia.org/wiki/Mole_(unit)
    -- Archive: https://archive.is/dHh7s
    - "General Tables of Units of Measurementv": https://www.nist.gov/system/files/documents/2016/11/10/appc-17-hb44-final.pdf
    -- Archive: https://web.archive.org/web/20230302222733/https://www.nist.gov/system/files/documents/2016/11/10/appc-17-hb44-final.pdf
    -- Archive: https://archive.is/KF4gI
"""
from __future__ import annotations

from numpy import pi
from scipy.constants import Boltzmann, Planck, atm, foot, gas_constant, mmHg, pound, pound_force, sigma, speed_of_light

__all__ = (
    'BOLTZMANNS_CONSTANT',
    'MOLE',
    'PLANCK_CONSTANT',
    'R_GAS_CONSTANT',
    'SPEED_OF_LIGHT',
    'STANDARD_NOISE_TEMPERATURE',
    ####
    'FEET2_PER_METER2',
    'FEET_PER_METER',
    'FEET_PER_MILE',
    'METER2_PER_FEET2',
    'METER_PER_FEET',
    'METER_PER_MILE',
    'METER_PER_NAUTICAL_MILE',
    ####
    'KG_PER_POUND_MASS',
    ####
    'NEWTONS_PER_POUND_FORCE',
    'POUND_FORCE_PER_NEWTON',
    'POUND_MASS_PER_KG',
    ####
    'ATM_PER_PASCAL',
    'PASCAL_PER_ATM',
    'PASCAL_PER_PSF',
    'PASCAL_PER_mmHg',
    'PSF_PER_PASCAL',
    'mmHg_PER_PASCAL',
    ####
    'KG_PER_AMU_MOL',
    ###
    'pi',
)
#########################

METER_PER_FEET: float = foot
FEET_PER_METER = 1. / METER_PER_FEET
FEET2_PER_METER2 = FEET_PER_METER**2
METER2_PER_FEET2 = METER_PER_FEET**2

NEWTONS_PER_POUND_FORCE = pound_force
POUND_FORCE_PER_NEWTON = 1. / NEWTONS_PER_POUND_FORCE

KG_PER_POUND_MASS = pound
POUND_MASS_PER_KG = 1. / KG_PER_POUND_MASS

PSF_PER_PASCAL = foot * foot / pound_force
PASCAL_PER_PSF = 1. / PSF_PER_PASCAL

STANDARD_NOISE_TEMPERATURE: float = 290.  # Kelvin
BOLTZMANNS_CONSTANT: float = Boltzmann  # J/(K); typically denoted as k
PLANCK_CONSTANT: float = Planck  # J/(Hz); typically denoted as h

STEFAN_BOLTZMANN: float = sigma  # W / (m^2 K^4); typically denoted as sigma, σ

SPEED_OF_LIGHT: float = speed_of_light

R_GAS_CONSTANT = gas_constant  # Universal Gas Constant for Air in SI units

MOLE = 6.022_140_76e23

FEET_PER_MILE = 5280
METER_PER_MILE = FEET_PER_MILE * METER_PER_FEET

METER_PER_NAUTICAL_MILE = 1852

PASCAL_PER_ATM = atm
ATM_PER_PASCAL = 1. / PASCAL_PER_ATM

PASCAL_PER_mmHg = mmHg
mmHg_PER_PASCAL = 1. / PASCAL_PER_mmHg

# One unified atomic mass unit, typically expressed as u or AMU
# is equal to the 1/12 mass of a C(12) carbon atom
# one mol of C(12) is 12 grams, so 1 amu = 1/(mol)*1e-3 [kg]
KG_PER_AMU_MOL = 1e-3
