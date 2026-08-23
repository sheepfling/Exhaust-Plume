"""Explicit gas-property contracts for plume state construction."""

from __future__ import annotations

from exhaust_plume.models.gas.calorically_perfect import CaloricallyPerfectGas
from exhaust_plume.models.gas.contracts import (
    FrozenMixtureConfig,
    GasModelKind,
    GasProperties,
    GasPropertiesConfig,
    SpeciesMassFraction,
)

__all__ = (
    'CaloricallyPerfectGas',
    'FrozenMixtureConfig',
    'GasModelKind',
    'GasProperties',
    'GasPropertiesConfig',
    'SpeciesMassFraction',
)
